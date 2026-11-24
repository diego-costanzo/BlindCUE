"""Show assistant link (stage 1M, M2) mixin for MainWindow.

When the teacher allows it (Show menu, off by default), the program listens
on 127.0.0.1 (a random port, never the network) for the MCP server of an AI
assistant. The port and a random token are written to
``~/.config/blindcue/assistant.json`` (only this user can read it); every
request must carry the token.

The assistant reads the show at any time but changes it only in the
Preparation mode, through the same rules as the file tools
(``mcp_server.show_tools.ShowSession``): every change is one Undo step, is
listed in "Changes from the assistant" and shows on the status line.
Requests are newline-separated JSON: {"token", "tool", "args"} ->
{"result"} or {"error"}.
"""

from __future__ import annotations

import hmac
import inspect
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from i18n import tr
from PySide6.QtNetwork import QHostAddress, QTcpServer

from ui.main_window._common import *  # noqa: F403,F401,F405

def info_file() -> Path:
    """Where the port and token are written (next to the autosave, outside AppData)."""
    return Path.home() / ".config" / "blindcue" / "assistant.json"

_MAX_LINE = 1_000_000
_CHANGE_WORDS = {
    "add_media_cue": "aggiunta la cue",
    "add_text_cue": "aggiunta la didascalia",
    "add_action_cue": "aggiunta l'azione",
    "add_group": "aggiunta la scena",
    "update_cue": "modificata la cue",
    "move_cue": "spostata la cue",
    "delete_cue": "eliminate le cue",
}
READ_TOOLS = ("list_cues", "get_cue", "validate_show", "summary")
WRITE_TOOLS = ("add_media_cue", "add_text_cue", "add_action_cue", "add_group", "update_cue",
               "move_cue", "delete_cue")


def _window_session(window):
    """A ShowSession working on the window's own cue list."""
    from mcp_server.show_tools import ShowSession, ToolError

    class _AnyFile:
        """The MCP server checks its allowed folders; here a file must just exist."""

        def check(self, raw, must_exist: bool = False) -> Path:
            path = Path(str(raw or "")).expanduser()
            if not path.is_absolute():
                raise ToolError("The program needs a full path.")
            path = path.resolve()
            if must_exist and not path.exists():
                raise ToolError(f"'{path}' does not exist.")
            return path

        def describe(self) -> list[str]:
            return []

        def contains(self, raw) -> bool:
            return True  # the program's own show: every file of it is the teacher's choice

    class WindowSession(ShowSession):
        def __init__(self) -> None:  # noqa: D107 - no ShowSession.__init__: it would empty the show
            self.policy = _AnyFile()
            self.autosave_file = None
            self.current_index = -1
            self.settings = {}
            self.bundled = False

        cues = property(lambda self: window._cues,
                        lambda self, value: setattr(window, "_cues", value))
        modified = property(lambda self: window._is_modified, lambda self, value: None)
        path = property(lambda self: Path(window._current_project_path)
                        if window._current_project_path else Path(tr("(nuovo spettacolo non salvato)")),
                        lambda self, value: None)

        def _need_show(self) -> None:
            return None

    return WindowSession()


class _AssistantMixin:
    def _assistant_setup(self) -> None:
        self._assistant_server: QTcpServer | None = None
        self._assistant_token = ""
        self._assistant_buffers: dict[int, bytes] = {}
        self._assistant_changes: list[tuple[str, str]] = []
        self._assistant_session = None
        allowed = QSettings("BlindCue", "BlindCue").value("assistant/allow_live", False, type=bool)
        self._act_assistant.setChecked(bool(allowed))  # starts the link through toggled
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._assistant_stop)

    # ── switching on and off ──
    def _on_assistant_toggled(self, on: bool) -> None:
        QSettings("BlindCue", "BlindCue").setValue("assistant/allow_live", bool(on))
        if on:
            self._assistant_start()
        else:
            self._assistant_stop()

    def _assistant_start(self) -> None:
        if self._assistant_server is not None:
            return
        server = QTcpServer(self)
        if not server.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 0):
            self._status_label.setText(tr("Assistente AI: impossibile aprire il collegamento locale"))
            return
        server.newConnection.connect(self._on_assistant_connection)
        self._assistant_server = server
        self._assistant_token = secrets.token_urlsafe(32)
        info = {"port": server.serverPort(), "token": self._assistant_token, "pid": os.getpid()}
        target = info_file()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(info), encoding="utf-8")
            os.replace(tmp, target)
        except OSError as exc:
            logger.warning("[ASSISTANT] Cannot write %s: %s", target, exc)
        self._status_label.setText(tr("🤖 Assistente AI collegabile: può modificare lo spettacolo nella preparazione"))

    def _assistant_stop(self) -> None:
        server = getattr(self, "_assistant_server", None)
        if server is not None:
            server.close()
            server.deleteLater()
            self._assistant_server = None
            self._assistant_remove_info()
        self._assistant_token = ""

    def _assistant_remove_info(self) -> None:
        """Delete our own link file only (never one written by another copy)."""
        try:
            target = info_file()
            data = json.loads(target.read_text(encoding="utf-8"))
            if self._assistant_token and data.get("token") == self._assistant_token:
                target.unlink()
        except (OSError, ValueError):
            pass

    # ── requests ──
    def _on_assistant_connection(self) -> None:
        server = self._assistant_server
        while server is not None and server.hasPendingConnections():
            sock = server.nextPendingConnection()
            sock.readyRead.connect(self._on_assistant_ready_read)
            sock.disconnected.connect(sock.deleteLater)

    def _on_assistant_ready_read(self) -> None:
        sock = self.sender()  # never a lambda capturing the socket (PySide access violations)
        if sock is None:
            return
        key = id(sock)
        data = self._assistant_buffers.get(key, b"") + bytes(sock.readAll())
        while b"\n" in data:
            line, data = data.split(b"\n", 1)
            reply = self._assistant_reply(line)
            sock.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            sock.flush()
            if reply.get("error") == "bad token":
                sock.disconnectFromHost()
                data = b""
                break
        if len(data) > _MAX_LINE:
            sock.disconnectFromHost()
            data = b""
        self._assistant_buffers[key] = data

    def _assistant_reply(self, line: bytes) -> dict[str, Any]:
        from mcp_server.show_tools import ToolError

        try:
            request = json.loads(line.decode("utf-8"))
            token = str(request.get("token", ""))
            if not self._assistant_token or not hmac.compare_digest(token, self._assistant_token):
                return {"error": "bad token"}
            return {"result": self._assistant_call(str(request.get("tool", "")), dict(request.get("args") or {}))}
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - the show must never fall over a bad request
            logger.warning("[ASSISTANT] Request failed: %s", exc, exc_info=True)
            return {"error": f"The program could not do this: {type(exc).__name__}"}

    def _assistant_call(self, tool: str, args: dict[str, Any]) -> Any:
        from engine.show_mode import PREPARATION
        from mcp_server.show_tools import ToolError

        if self._assistant_session is None:
            self._assistant_session = _window_session(self)
        session = self._assistant_session
        if tool == "ping":
            return {"program": "BlindCue", "show": str(session.path), "mode": self._current_mode(),
                    "cues": len(self._cues)}
        if tool == "save_show":
            if self._current_mode() != PREPARATION:
                raise ToolError("The teacher is running the show: save it in Preparation.")
            if not self._current_project_path:
                raise ToolError("This show has no file yet: ask the teacher to save it once (Ctrl+S).")
            if not self._do_save(self._current_project_path):
                raise ToolError("The program could not save the show.")
            self._assistant_note(tr("salvato lo spettacolo"))
            return {"saved": self._current_project_path}
        if tool not in READ_TOOLS + WRITE_TOOLS:
            raise ToolError(f"'{tool}' is not available while connected to the program.")
        method = getattr(session, tool)
        accepted = set(inspect.signature(method).parameters)
        unknown = set(args) - accepted
        if unknown:
            raise ToolError(f"Unknown arguments for {tool}: {', '.join(sorted(unknown))}.")
        if tool in READ_TOOLS:
            return method(**args)
        if self._current_mode() != PREPARATION:
            raise ToolError("The teacher is running the show (Rehearsal or Show): the assistant changes it "
                            "only in Preparation. Try again later.")
        if self._readiness_visible():
            raise ToolError("The teacher is looking at the readiness page: try again in a moment.")
        if tool == "update_cue" and "q_label" in args and self._q_locked():
            raise ToolError("The cue labels (Q) are locked: the script is approved. Leave q_label out, "
                            "or ask the teacher to unlock them (Edit menu).")
        self._apply_inspector_to_cue()
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        result = method(**args)
        row = next((i for i, c in enumerate(self._cues)
                    if isinstance(result, dict) and c.cue_id == result.get("cue_id")), -1)
        self._refresh_cue_list(keep_selection=row < 0, select_row=row if row >= 0 else None)
        self._last_selection_sig = None
        self._sync_selection_state()  # the inspector shows the cue as it is now
        self._commit_undo_point()
        self._mark_modified(True)
        name = result.get("name", "") if isinstance(result, dict) else ""
        what = tr(_CHANGE_WORDS[tool])
        self._assistant_note(f"{what} '{name}'" if name else what)
        return result

    def _assistant_note(self, text: str) -> None:
        self._assistant_changes.append((time.strftime("%H:%M:%S"), text))
        self._status_label.setText(tr("🤖 Assistente AI: {}").format(text))

    def _open_assistant_dialog(self) -> None:
        """Show menu → AI assistant: add it to Claude Desktop, allow it, see its changes."""
        from ui.assistant_dialog import AssistantDialog

        AssistantDialog(self).exec()

    def _show_assistant_changes(self) -> None:
        """Show menu: what the assistant changed in this session (Ctrl+Z undoes it step by step)."""
        lines = [f"{t}  {what}" for t, what in self._assistant_changes] or [tr("Nessuna modifica dall'assistente.")]
        box = QMessageBox(self)
        box.setWindowTitle(tr("Modifiche dall'assistente AI"))
        box.setText(tr("Ogni modifica è un passo di Annulla (Ctrl+Z)."))
        box.setDetailedText("\n".join(lines))
        box.setInformativeText("\n".join(lines[-12:]))
        box.exec()
