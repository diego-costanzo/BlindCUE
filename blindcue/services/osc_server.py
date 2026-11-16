"""Native Qt OSC UDP Server for BlindCUE remote control.

Supports theater automation standards (QLab, ETC Eos, TouchOSC, Stream Deck, Reaper, Yamaha/Behringer):
  - /go, /cue/go, /blindcue/go
  - /stop, /blackout, /cue/stop
  - /panic, /cue/panic
  - /pause, /resume, /pause_toggle
  - /next, /cue/next
  - /prev, /previous, /cue/prev
  - /cue/<number>/go, /cue/go <number>
  - /cue/<number>/select, /cue/select <number>
  - /volume <float>
"""

from __future__ import annotations

import hmac
import logging
import math
import re
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QNetworkDatagram, QUdpSocket

from services.osc_protocol import build_osc_message, parse_osc_message

logger = logging.getLogger("blindcue.osc")

# Hard cap on datagrams processed per event-loop turn (anti-flood / GUI starvation)
_MAX_DATAGRAMS_PER_TICK = 256


class OscServer(QObject):
    """High-performance non-blocking OSC UDP receiver running directly on the Qt event loop."""

    # Bridge signals emitted to MainWindow
    command_received = Signal(str, list, str)   # (address, args, sender_ip)
    go_requested = Signal()
    panic_requested = Signal()
    blackout_requested = Signal()
    pause_toggle_requested = Signal()
    next_cue_requested = Signal()
    prev_cue_requested = Signal()
    cue_go_requested = Signal(object)           # cue index or identifier (int or str)
    cue_select_requested = Signal(object)       # cue index or identifier (int or str)
    volume_change_requested = Signal(float)     # 0.0 .. 1.0

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the OSC UDP server (not listening until ``start`` is called)."""
        super().__init__(parent)
        self._socket: QUdpSocket | None = None
        self._port: int = 53000
        self._is_running: bool = False
        self._last_sender_ip: str = ""
        self._last_command: str = ""
        self._packet_count: int = 0
        self._pin_required: bool = False
        self._pin: str = "4821"
        self._allowed_ips: set[str] = set()
        self._authenticated_ips: set[str] = set()

    def set_security(self, pin_required: bool = False, pin: str = "4821", allowed_ips: list[str] | None = None) -> None:
        """Configure OSC authentication and optional IP whitelist."""
        self._pin_required = bool(pin_required)
        self._pin = str(pin).strip()
        self._allowed_ips = {ip.strip() for ip in allowed_ips} if allowed_ips else set()

    def clear_authenticated_clients(self) -> None:
        """Revoke all active client sessions."""
        self._authenticated_ips.clear()

    def is_running(self) -> bool:
        """True while the OSC listener thread is active."""
        return self._is_running

    def get_port(self) -> int:
        """UDP port the OSC listener is bound to."""
        return self._port

    def get_last_command_info(self) -> str:
        """Description of the last OSC message received (for the status bar)."""
        if not self._last_command:
            return "Nessun comando ricevuto"
        return f"{self._last_command} da {self._last_sender_ip} (tot: {self._packet_count})"

    def start(self, port: int = 53000) -> bool:
        """Start listening for incoming OSC packets on the specified UDP port."""
        self.stop()
        self._port = port
        self._socket = QUdpSocket(self)

        # Bind to all IPv4 interfaces
        ok = self._socket.bind(QHostAddress.SpecialAddress.AnyIPv4, self._port)
        if not ok:
            logger.error("[OSC] Could not bind UDP socket to port %d", self._port)
            self._socket.deleteLater()
            self._socket = None
            self._is_running = False
            return False

        self._socket.readyRead.connect(self._on_ready_read)
        self._is_running = True
        logger.info("[OSC] Server active and listening on UDP port %d", self._port)
        return True

    def stop(self) -> None:
        """Stop OSC UDP server and release the port."""
        if self._socket is not None:
            try:
                self._socket.close()
                self._socket.deleteLater()
            except Exception:
                logger.debug("[OSC] Error while closing UDP socket", exc_info=True)
            self._socket = None
        self._is_running = False
        logger.info("[OSC] Server stopped")

    def __del__(self) -> None:
        """Best-effort socket cleanup; never raises during interpreter shutdown."""
        try:
            self.stop()
        except Exception:
            logger.debug("[OSC] Error during destructor cleanup", exc_info=True)

    def _on_ready_read(self) -> None:
        if not self._socket:
            return

        processed = 0
        while self._socket.hasPendingDatagrams():
            if processed >= _MAX_DATAGRAMS_PER_TICK:
                # Defer the backlog to the next event-loop turn to avoid GUI starvation
                QTimer.singleShot(0, self._on_ready_read)
                break
            processed += 1
            try:
                datagram: QNetworkDatagram = self._socket.receiveDatagram()
                raw_data = bytes(datagram.data())
                sender_addr = datagram.senderAddress().toString()
                # Clean IPv6-mapped IPv4 address if present (e.g. "::ffff:192.168.1.10" -> "192.168.1.10")
                if sender_addr.startswith("::ffff:"):
                    sender_addr = sender_addr[7:]

                address, args = parse_osc_message(raw_data)
                if not address:
                    continue

                self._packet_count += 1
                self._last_sender_ip = sender_addr
                self._last_command = f"{address} {args if args else ''}".strip()
                logger.debug("[OSC] Received '%s' %s from %s", address, args, sender_addr)

                self.command_received.emit(address, args, sender_addr)
                self._dispatch_command(address, args, sender_addr)
            except Exception:
                logger.debug("[OSC] Dropped malformed datagram", exc_info=True)

    def _dispatch_command(self, address: str, args: list[Any], sender_addr: str = "") -> None:
        """Route OSC address patterns to the corresponding playback action."""
        addr = address.lower().strip()

        # 0. Check IP Whitelist
        if self._allowed_ips and sender_addr and sender_addr not in self._allowed_ips:
            logger.warning("[OSC] Dropped packet from non-whitelisted IP: %s", sender_addr)
            return

        # Check authentication handshake (/auth <pin>)
        if addr in ("/auth", "/login", "/blindcue/auth") and args:
            if hmac.compare_digest(str(args[0]).strip(), self._pin):
                self._authenticated_ips.add(sender_addr)
                logger.info("[OSC] Host %s authenticated successfully with PIN", sender_addr)
            else:
                logger.warning("[OSC] Authentication failed for host %s", sender_addr)
            return

        # Check PIN requirement
        if self._pin_required and sender_addr not in self._authenticated_ips:
            pin_prefix = f"/{self._pin}/"
            blindcue_pin_prefix = f"/blindcue/{self._pin}/"
            if addr.startswith(pin_prefix):
                addr = "/" + addr[len(pin_prefix):]
            elif addr.startswith(blindcue_pin_prefix):
                addr = "/blindcue/" + addr[len(blindcue_pin_prefix):]
            else:
                logger.warning("[OSC] Dropped unauthorized command '%s' from %s (PIN required)", address, sender_addr)
                return

        # 1. Transport GO
        if addr in ("/go", "/cue/go", "/blindcue/go"):
            if args:
                # If argument supplied (e.g. /cue/go 4), fire specific cue
                self.cue_go_requested.emit(args[0])
            else:
                self.go_requested.emit()
            return

        # 2. Blackout / Stop
        if addr in ("/stop", "/blackout", "/cue/stop", "/blindcue/stop", "/blindcue/blackout"):
            self.blackout_requested.emit()
            return

        # 3. Panic (0ms instant kill)
        if addr in ("/panic", "/cue/panic", "/blindcue/panic"):
            self.panic_requested.emit()
            return

        # 4. Pause / Resume / Toggle
        if addr in ("/pause", "/resume", "/pause_toggle", "/toggle_pause", "/cue/pause", "/blindcue/pause"):
            self.pause_toggle_requested.emit()
            return

        # 5. Next / Prev Standby Cue
        if addr in ("/next", "/cue/next", "/blindcue/next", "/step_next"):
            self.next_cue_requested.emit()
            return

        if addr in ("/prev", "/previous", "/cue/prev", "/cue/previous", "/blindcue/prev", "/step_prev"):
            self.prev_cue_requested.emit()
            return

        # 6. Specific Cue GO: /cue/<id_or_number>/go or /cue/<id_or_number>/start
        m_go = re.match(r"^/cue/([^/]+)/(?:go|start)$", addr)
        if m_go:
            val = m_go.group(1)
            # Try convert to int if numeric
            target = int(val) if val.isdigit() else val
            self.cue_go_requested.emit(target)
            return

        # 7. Specific Cue Select: /cue/<id_or_number>/select
        m_sel = re.match(r"^/cue/([^/]+)/select$", addr)
        if m_sel:
            val = m_sel.group(1)
            target = int(val) if val.isdigit() else val
            self.cue_select_requested.emit(target)
            return

        if addr in ("/cue/select", "/select") and args:
            self.cue_select_requested.emit(args[0])
            return

        # 8. Master volume: /volume or /master/volume <0.0..1.0>
        if addr in ("/volume", "/master/volume") and args:
            try:
                vol = float(args[0])
            except (ValueError, TypeError):
                logger.debug("[OSC] Ignored non-numeric volume argument: %r", args[0])
                return
            if not math.isfinite(vol):
                logger.debug("[OSC] Ignored non-finite volume argument: %r", vol)
                return
            self.volume_change_requested.emit(max(0.0, min(1.0, vol)))

    def send_feedback(self, ip: str, port: int, address: str, *args: Any) -> bool:
        """Send an OSC response or feedback datagram to a remote controller."""
        if not self._socket:
            return False
        try:
            data = build_osc_message(address, *args)
            host = QHostAddress(ip)
            sent = self._socket.writeDatagram(data, host, port)
            return sent > 0
        except Exception as exc:
            logger.error("[OSC] Error sending feedback to %s:%d: %s", ip, port, exc)
            return False

