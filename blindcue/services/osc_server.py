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

import logging
import re
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QNetworkDatagram, QUdpSocket

from services.osc_protocol import build_osc_message, parse_osc_message

logger = logging.getLogger("blindcue.osc")


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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._socket: Optional[QUdpSocket] = None
        self._port: int = 53000
        self._is_running: bool = False
        self._last_sender_ip: str = ""
        self._last_command: str = ""
        self._packet_count: int = 0

    def is_running(self) -> bool:
        return self._is_running

    def get_port(self) -> int:
        return self._port

    def get_last_command_info(self) -> str:
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
                pass
            self._socket = None
        self._is_running = False
        logger.info("[OSC] Server stopped")

    def _on_ready_read(self) -> None:
        if not self._socket:
            return

        while self._socket.hasPendingDatagrams():
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
            self._dispatch_command(address, args)

    def _dispatch_command(self, address: str, args: list[Any]) -> None:
        """Route OSC address patterns to the corresponding playback action."""
        addr = address.lower().strip()

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
                self.volume_change_requested.emit(max(0.0, min(1.0, vol)))
            except (ValueError, TypeError):
                pass

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
