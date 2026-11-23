"""Talk to the running program instead of a show file (stage 1M, M2).

The program, when the teacher allows it, writes its local port and a token
to ``~/.config/blindcue/assistant.json`` (see ``ui/main_window/_assistant.py``).
``ProgramSession`` offers the same methods as ``ShowSession``; it checks the
allowed folders here and sends the call to the program, which applies it
to the open show (one Undo step each, only in the Preparation mode).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from mcp_server.show_tools import AccessPolicy, ToolError

TIMEOUT_SEC = 20.0


class ProgramSession:
    """The show open in BlindCue right now, changed through the program."""

    def __init__(self, policy: AccessPolicy, info_file: Path | None = None) -> None:
        self.policy = policy
        self._info_file = info_file or Path.home() / ".config" / "blindcue" / "assistant.json"
        try:
            info = json.loads(self._info_file.read_text(encoding="utf-8"))
            self._port, self._token = int(info["port"]), str(info["token"])
        except (OSError, ValueError, KeyError, TypeError):
            raise ToolError("BlindCue does not let an assistant in: in the program, tick Show menu → "
                            "'AI assistant may change the show' (the program must be running).") from None
        self._sock: socket.socket | None = None
        self._buffer = b""
        self.hello = self._request("ping", {})

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _connect(self) -> socket.socket:
        if self._sock is None:
            try:
                self._sock = socket.create_connection(("127.0.0.1", self._port), timeout=TIMEOUT_SEC)
            except OSError:
                raise ToolError("BlindCue does not answer: is it running with the assistant allowed?") from None
            self._buffer = b""
        return self._sock

    def _request(self, tool: str, args: dict[str, Any]) -> Any:
        payload = json.dumps({"token": self._token, "tool": tool, "args": args}).encode("utf-8") + b"\n"
        for attempt in range(2):  # the program may have closed an idle connection
            sock = self._connect()
            try:
                sock.sendall(payload)
                while b"\n" not in self._buffer:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("closed")
                    self._buffer += chunk
                line, self._buffer = self._buffer.split(b"\n", 1)
                reply = json.loads(line.decode("utf-8"))
                break
            except (OSError, ConnectionError, ValueError):
                self.close()
                if attempt:
                    raise ToolError("The connection to BlindCue broke: try use_program again.") from None
        if "error" in reply:
            raise ToolError(str(reply["error"]))
        return reply.get("result")

    # ── the same methods as ShowSession ──
    def summary(self) -> Any:
        return self._request("summary", {})

    def list_cues(self) -> Any:
        return self._request("list_cues", {})

    def get_cue(self, cue_id: int) -> Any:
        return self._request("get_cue", {"cue_id": cue_id})

    def validate_show(self) -> Any:
        return self._request("validate_show", {})

    def add_media_cue(self, path: str, after_cue_id: int | None = None,
                      fields: dict[str, Any] | None = None) -> Any:
        media = self.policy.check(path, must_exist=True)  # the allowed folders still apply
        return self._request("add_media_cue", {"path": str(media), "after_cue_id": after_cue_id, "fields": fields})

    def add_text_cue(self, text: str, after_cue_id: int | None = None, size: int = 90,
                     position: str = "bottom", color: str = "#ffffff",
                     fields: dict[str, Any] | None = None) -> Any:
        return self._request("add_text_cue", {"text": text, "after_cue_id": after_cue_id, "size": size,
                                              "position": position, "color": color, "fields": fields})

    def add_action_cue(self, kind: str, after_cue_id: int | None = None, spec: dict[str, Any] | None = None,
                       name: str | None = None, fields: dict[str, Any] | None = None) -> Any:
        return self._request("add_action_cue", {"kind": kind, "after_cue_id": after_cue_id, "spec": spec,
                                                "name": name, "fields": fields})

    def add_group(self, name: str, cue_ids: list[int] | None = None, mode: str = "STEP",
                  after_cue_id: int | None = None) -> Any:
        return self._request("add_group", {"name": name, "cue_ids": cue_ids, "mode": mode,
                                           "after_cue_id": after_cue_id})

    def update_cue(self, cue_id: int, fields: dict[str, Any]) -> Any:
        return self._request("update_cue", {"cue_id": cue_id, "fields": fields})

    def move_cue(self, cue_id: int, after_cue_id: int | None = None, to_top: bool = False,
                 into_group_id: int | None = None) -> Any:
        return self._request("move_cue", {"cue_id": cue_id, "after_cue_id": after_cue_id, "to_top": to_top,
                                          "into_group_id": into_group_id})

    def delete_cue(self, cue_id: int, with_items: bool = False) -> Any:
        return self._request("delete_cue", {"cue_id": cue_id, "with_items": with_items})

    def save_show(self, path: str | None = None) -> Any:
        if path:
            raise ToolError("Connected to the program: it saves the show under its own name "
                            "(the teacher can use File → Save as).")
        return self._request("save_show", {})

    def new_show(self, path: str) -> Any:
        raise ToolError("Connected to the program: call use_files first to work on show files.")

    open_show = new_show
