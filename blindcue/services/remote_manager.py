"""Unified Remote Control Coordinator (Web Remote + OSC UDP Server + LAN IP Detection).

Provides a single high-level interface to:
  - Detect host LAN IP addresses
  - Start/stop Web Server and OSC Server
  - Generate QR code for instant smartphone pairing
  - Forward incoming remote triggers into MainWindow
  - Broadcast live show state to all connected web clients
"""

from __future__ import annotations

import io
import logging
import secrets
import socket
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap

from services.osc_server import OscServer
from services.qr_generator import generate_qr_pixmap as native_qr_generate
from services.web_server import WebRemoteServer

logger = logging.getLogger("blindcue.remote")


def get_local_lan_ips() -> list[str]:
    """Detect non-loopback IPv4 addresses assigned to the local network interfaces."""
    ips: set[str] = set()

    # Strategy 0: Qt Network Interface discovery (rock-solid on Linux/macOS/Windows, even offline)
    try:
        from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if (flags & QNetworkInterface.InterfaceFlag.IsUp) and not (flags & QNetworkInterface.InterfaceFlag.IsLoopBack):
                for entry in iface.addressEntries():
                    ip_obj = entry.ip()
                    if ip_obj.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol and not ip_obj.isLoopback():
                        s_ip = ip_obj.toString().strip()
                        if s_ip and not s_ip.startswith("127."):
                            ips.add(s_ip)
    except Exception:
        pass

    # Strategy 1: Open temporary UDP socket to determine preferred outgoing route
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and not primary_ip.startswith("127."):
            ips.add(primary_ip)
    except Exception:
        pass

    # Strategy 2: Hostname resolution for additional physical/Wi-Fi interfaces
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    if not ips:
        ips.add("127.0.0.1")

    # Sort so that preferred IP (from private subnets) comes first if present
    res = list(ips)
    res.sort(key=lambda x: (x.startswith("127."), not x.startswith("192.168."), not x.startswith("10."), not x.startswith("172.")))
    return res


class RemoteManager(QObject):
    """High-level coordinator for Web Remote and OSC Server."""

    # Unified signals emitted to MainWindow
    go_requested = Signal()
    panic_requested = Signal()
    blackout_requested = Signal()
    pause_toggle_requested = Signal()
    next_cue_requested = Signal()
    prev_cue_requested = Signal()
    cue_go_requested = Signal(object)           # cue id or index
    cue_select_requested = Signal(object)       # cue id or index
    volume_change_requested = Signal(float)

    activity_updated = Signal()                 # emitted whenever clients or packets change

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._web_enabled: bool = False
        self._web_port: int = 8080
        self._osc_enabled: bool = False
        self._osc_port: int = 53000

        # Security PIN & Anti-Burlone Controls (6-digit cryptographically secure PIN)
        self._pin_enabled: bool = True
        self._pin: str = f"{secrets.SystemRandom().randint(100000, 999999)}"
        self._qr_includes_pin: bool = True
        self._osc_pin_required: bool = False
        self._osc_allowed_ips: list[str] = []

        self.web_server = WebRemoteServer(port=self._web_port)
        self.web_server.set_pin_protection(self._pin_enabled, self._pin)
        self.osc_server = OscServer(self)
        self.osc_server.set_security(self._osc_pin_required, self._pin, self._osc_allowed_ips)

        self._wire_bridges()

        # Periodic throttle timer for broadcasting live playhead progress (every 250ms when playing)
        self._broadcast_timer = QTimer(self)
        self._broadcast_timer.setInterval(250)
        self._broadcast_timer.timeout.connect(self._on_broadcast_tick)
        self._broadcast_timer.start()

    def _wire_bridges(self) -> None:
        # Wire Web Server bridge (Cross-thread QueuedConnection guarantees safe main-thread delivery)
        wb = self.web_server.bridge
        wb.go_requested.connect(self.go_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.panic_requested.connect(self.panic_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.blackout_requested.connect(self.blackout_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.pause_toggle_requested.connect(self.pause_toggle_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.next_cue_requested.connect(self.next_cue_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.prev_cue_requested.connect(self.prev_cue_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.cue_go_requested.connect(self.cue_go_requested.emit, Qt.ConnectionType.QueuedConnection)
        wb.cue_select_requested.connect(self.cue_select_requested.emit, Qt.ConnectionType.QueuedConnection)

        # Wire OSC Server bridge
        os_srv = self.osc_server
        os_srv.go_requested.connect(self.go_requested.emit)
        os_srv.panic_requested.connect(self.panic_requested.emit)
        os_srv.blackout_requested.connect(self.blackout_requested.emit)
        os_srv.pause_toggle_requested.connect(self.pause_toggle_requested.emit)
        os_srv.next_cue_requested.connect(self.next_cue_requested.emit)
        os_srv.prev_cue_requested.connect(self.prev_cue_requested.emit)
        os_srv.cue_go_requested.connect(self.cue_go_requested.emit)
        os_srv.cue_select_requested.connect(self.cue_select_requested.emit)
        os_srv.volume_change_requested.connect(self.volume_change_requested.emit)

    def set_state_provider(self, provider: Callable[[], dict[str, Any]]) -> None:
        """Register callback that provides full current show state snapshot."""
        self.web_server.set_state_provider(provider)

    def is_web_active(self) -> bool:
        return self._web_enabled and self.web_server.is_running()

    def is_osc_active(self) -> bool:
        return self._osc_enabled and self.osc_server.is_running()

    def get_web_port(self) -> int:
        return self._web_port

    def get_osc_port(self) -> int:
        return self._osc_port

    def is_pin_enabled(self) -> bool:
        return self._pin_enabled

    def get_pin(self) -> str:
        return self._pin

    def is_qr_pin_included(self) -> bool:
        return self._qr_includes_pin

    def is_osc_pin_required(self) -> bool:
        return self._osc_pin_required

    def get_osc_allowed_ips(self) -> list[str]:
        return list(self._osc_allowed_ips)

    def generate_new_pin(self) -> str:
        self._pin = f"{secrets.SystemRandom().randint(100000, 999999)}"
        self.web_server.set_pin_protection(self._pin_enabled, self._pin)
        self.osc_server.set_security(self._osc_pin_required, self._pin, self._osc_allowed_ips)
        self.revoke_all_sessions()
        self.activity_updated.emit()
        return self._pin

    def set_pin_security(self, enabled: bool, pin: str, qr_includes_pin: bool = True) -> None:
        self._pin_enabled = bool(enabled)
        self._pin = str(pin).strip()
        self._qr_includes_pin = bool(qr_includes_pin)
        self.web_server.set_pin_protection(self._pin_enabled, self._pin)
        self.osc_server.set_security(self._osc_pin_required, self._pin, self._osc_allowed_ips)
        self.activity_updated.emit()

    def set_osc_security(self, pin_required: bool, allowed_ips: Optional[list[str]] = None) -> None:
        self._osc_pin_required = bool(pin_required)
        self._osc_allowed_ips = [ip.strip() for ip in allowed_ips] if allowed_ips else []
        self.osc_server.set_security(self._osc_pin_required, self._pin, self._osc_allowed_ips)
        self.activity_updated.emit()

    def revoke_all_sessions(self) -> None:
        """Drop all active sessions and force re-authentication (Anti-Burlone emergency reset)."""
        self.web_server.revoke_all_sessions()
        self.osc_server.clear_authenticated_clients()
        self.activity_updated.emit()

    def get_primary_web_url(self, include_pin: bool = False) -> str:
        ips = get_local_lan_ips()
        ip = ips[0] if ips else "127.0.0.1"
        base = f"http://{ip}:{self._web_port}"
        if include_pin and self._pin_enabled:
            return f"{base}/?pin={self._pin}"
        return base

    def get_qr_url(self) -> str:
        """Return the URL to be encoded in the QR code (includes PIN if enabled for 1-tap camera scan)."""
        return self.get_primary_web_url(include_pin=self._qr_includes_pin)

    def get_monitor_url(self, include_pin: bool = False) -> str:
        """Return the dedicated read-only Director Monitor URL (no interactive controls)."""
        ips = get_local_lan_ips()
        ip = ips[0] if ips else "127.0.0.1"
        base = f"http://{ip}:{self._web_port}/monitor"
        if include_pin and self._pin_enabled:
            return f"{base}?pin={self._pin}"
        return base

    def get_monitor_qr_url(self) -> str:
        """Return the URL for the Director Monitor QR code (with PIN if enabled for 1-tap scan)."""
        return self.get_monitor_url(include_pin=self._qr_includes_pin)

    def get_all_web_urls(self) -> list[str]:
        ips = get_local_lan_ips()
        return [f"http://{ip}:{self._web_port}" for ip in ips]

    def get_osc_address(self) -> str:
        ips = get_local_lan_ips()
        ip = ips[0] if ips else "127.0.0.1"
        return f"udp://{ip}:{self._osc_port}"

    def start_all(self, web_port: int = 8080, osc_port: int = 53000) -> tuple[bool, bool]:
        """Start both Web and OSC servers with the given ports."""
        self._web_port = web_port
        self._osc_port = osc_port
        self._web_enabled = True
        self._osc_enabled = True

        web_ok = self.web_server.start(self._web_port)
        osc_ok = self.osc_server.start(self._osc_port)

        self.activity_updated.emit()
        return web_ok, osc_ok

    def stop_all(self) -> None:
        """Stop both Web and OSC servers."""
        self._web_enabled = False
        self._osc_enabled = False
        self.web_server.stop()
        self.osc_server.stop()
        self.activity_updated.emit()

    def set_web_enabled(self, enabled: bool) -> None:
        self._web_enabled = bool(enabled)
        if self._web_enabled:
            if not self.web_server.is_running():
                self.web_server.start(self._web_port)
        else:
            self.web_server.stop()
        self.activity_updated.emit()

    def set_osc_enabled(self, enabled: bool) -> None:
        self._osc_enabled = bool(enabled)
        if self._osc_enabled:
            if not self.osc_server.is_running():
                self.osc_server.start(self._osc_port)
        else:
            self.osc_server.stop()
        self.activity_updated.emit()

    def trigger_state_broadcast(self) -> None:
        """Immediately broadcast state update to all web clients (e.g. on GO or cue change)."""
        if self.is_web_active():
            self.web_server.broadcast_state()

    def _on_broadcast_tick(self) -> None:
        if self.is_web_active() and self.web_server.get_connected_clients_count() > 0:
            self.web_server.broadcast_state()

    def generate_qr_pixmap(self, url: Optional[str] = None, size: int = 220) -> Optional[QPixmap]:
        """Generate high-contrast QR code QPixmap for scanning with smartphones (100% cross-platform)."""
        target_url = url or self.get_qr_url()

        # 1. Pure-Python QR generation (qrcode library SVG -> QPixmap)
        try:
            import qrcode
            import qrcode.image.svg
            from PySide6.QtCore import QByteArray
            from PySide6.QtGui import QPainter
            from PySide6.QtSvg import QSvgRenderer

            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(target_url)
            qr.make(fit=True)

            img_svg = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
            stream = io.BytesIO()
            img_svg.save(stream)
            svg_data = stream.getvalue()

            renderer = QSvgRenderer(QByteArray(svg_data))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.white)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            if not pixmap.isNull():
                return pixmap
        except Exception as exc:
            logger.debug("[REMOTE] qrcode SVG generation failed: %s", exc)

        # 2. Native pure-Python QR fallback (zero-dependency matrix)
        try:
            pix = native_qr_generate(target_url, size=size)
            if pix is not None and not pix.isNull():
                return pix
        except Exception as exc:
            logger.debug("[REMOTE] Native QR fallback failed: %s", exc)

        return None

