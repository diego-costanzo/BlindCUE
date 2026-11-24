"""Allow only one running copy of BlindCue per user.

Two copies share the same autosave, settings and log file, and each puts its
own output window on the projector. On 2026-11-21 a second copy, started by
a double launch, waited on its "restore session?" question with its output
full screen and always on top; when the projector was unplugged that window
covered the director screen and nothing could be clicked.

The first copy holds a lock file and listens on a local socket. A second
launch asks it to come to the front and then quits.
"""
from __future__ import annotations

import logging
import os
import re
import sys

from PySide6.QtCore import QDir, QLockFile, QObject, QStandardPaths, Qt, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

_ACTIVATE = b"activate\n"
_OPEN = b"open "        # 5.14: "open <path>\n" - a double-clicked show file
_ACK = b"ok\n"


def show_file_from_args(args: list[str]) -> str | None:
    """The show file the program was started with (a double-click on a .blindcue file), if any."""
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        if arg.lower().endswith(".blindcue") and os.path.isfile(arg):
            return os.path.abspath(arg)
    return None


def default_key() -> str:
    """Name shared by all copies of one user (lock file and socket)."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    return "BlindCue-" + re.sub(r"[^A-Za-z0-9_.-]", "_", user)


class SingleInstance(QObject):
    """Lock held by the running copy plus a socket to wake it up."""

    activation_requested = Signal()
    open_requested = Signal(str)        # 5.14: another launch got this show file

    def __init__(self, key: str | None = None, lock_dir: str | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key = key or default_key()
        if lock_dir is None:
            lock_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation) or QDir.tempPath()
        QDir().mkpath(lock_dir)
        self._lock = QLockFile(os.path.join(lock_dir, self._key + ".lock"))
        # 0 = a lock is stale only when the process that took it is gone.
        self._lock.setStaleLockTime(0)
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """True when no other copy runs (this one may start)."""
        if not self._lock.tryLock(100):
            if self._lock.error() == QLockFile.LockError.LockFailedError:
                return False
            # The lock file cannot be written: never block a show for that.
            logger.warning("[INSTANCE] Lock file unavailable (%s) - starting anyway",
                           self._lock.error())
            return True
        QLocalServer.removeServer(self._key)  # socket left by a crash (Unix)
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if server.listen(self._key):
            server.newConnection.connect(self._on_new_connection)
            self._server = server
        else:
            logger.warning("[INSTANCE] Cannot listen on '%s': %s",
                           self._key, server.errorString())
        return True

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        self._lock.unlock()

    def notify_running(self, timeout_ms: int = 3000, show_file: str | None = None) -> bool:
        """Ask the running copy to show its window (and open *show_file*). True if it answered."""
        if sys.platform == "win32":
            # The copy just started by the user may give the foreground away;
            # without this Windows only flashes the other copy's taskbar button.
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
            except Exception as exc:  # noqa: BLE001
                logger.debug("[INSTANCE] AllowSetForegroundWindow failed: %s", exc)
        sock = QLocalSocket()
        sock.connectToServer(self._key)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write(_OPEN + show_file.encode("utf-8") + b"\n" if show_file else _ACTIVATE)
        sock.flush()
        answered = sock.waitForReadyRead(timeout_ms) and bytes(sock.readAll().data()).startswith(_ACK)
        sock.disconnectFromServer()
        return answered

    def _on_new_connection(self) -> None:
        server = self._server
        while server is not None and server.hasPendingConnections():
            sock = server.nextPendingConnection()
            sock.readyRead.connect(self._on_ready_read)
            sock.disconnected.connect(sock.deleteLater)
            self._on_ready_read(sock)

    def _on_ready_read(self, sock: QLocalSocket | None = None) -> None:
        sock = sock or self.sender()
        if not isinstance(sock, QLocalSocket) or not sock.canReadLine():
            return
        line = bytes(sock.readLine().data())
        if line == _ACTIVATE or line.startswith(_OPEN):
            sock.write(_ACK)
            sock.flush()
            logger.info("[INSTANCE] Another launch asked for this window")
            self.activation_requested.emit()
            if line.startswith(_OPEN):
                path = line[len(_OPEN):].rstrip(b"\r\n").decode("utf-8", "replace")
                if path:
                    self.open_requested.emit(path)


def bring_to_front(window: QWidget) -> None:
    """Restore *window* (and an open modal dialog) and give it the focus."""
    state = window.windowState() & ~Qt.WindowState.WindowMinimized
    window.setWindowState(state | Qt.WindowState.WindowActive)
    window.show()
    window.raise_()
    window.activateWindow()
    modal = QApplication.activeModalWidget()
    if modal is not None and modal is not window:
        modal.raise_()
        modal.activateWindow()
