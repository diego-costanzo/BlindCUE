"""Claude Desktop extension and client settings for the show assistant (stage 1M, M3).

``build_mcpb`` writes a ``.mcpb`` file (an MCP Bundle: a ZIP with
``manifest.json``, see github.com/modelcontextprotocol/mcpb): double-clicked,
Claude Desktop installs the assistant and asks which folders it may use.
The bundle holds no program: it starts the assistant installed with BlindCue,
whose path is written into it when the program makes the bundle, so a
custom installation folder works too.

``client_config`` gives the same command for other MCP clients
(``mcpServers`` JSON, as Claude Desktop and Claude Code read it).
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

BUNDLE_NAME = "blindcue-show-assistant"


def server_command() -> tuple[str, list[str]]:
    """How to start the assistant on this computer: (command, first arguments)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).with_name("BlindCue-Assistant.exe")
        return str(exe), []
    script = Path(__file__).resolve().with_name("server.py")
    return sys.executable, [str(script)]


def manifest(version: str, command: str, first_args: list[str]) -> dict[str, Any]:
    return {
        "manifest_version": "0.3",
        "name": BUNDLE_NAME,
        "display_name": "BlindCue – show assistant",
        "version": version,
        "description": "Prepare BlindCue theatre shows: cue lists from a folder of media, captions, "
                       "scenes, notes for the operator.",
        "long_description": (
            "Lets the assistant build and check BlindCue show files (.blindcue) anywhere on this "
            "computer (also on a USB stick) or only in the folders you choose, and - when allowed in "
            "BlindCue (Show menu) - change the show open in the program while you prepare it. It never "
            "plays anything, never deletes media and never changes a show that is running."),
        "author": {"name": "BlindCue"},
        "icon": "icon.png",
        "server": {
            "type": "binary",
            "entry_point": command,
            "mcp_config": {
                "command": command,
                "args": [*first_args, "--root", "${user_config.folders}"],
                "env": {},
            },
        },
        "user_config": {
            "folders": {
                "type": "directory",
                "title": "Limit to these folders (optional)",
                "description": "Leave empty: the assistant may use every drive of this computer, also a USB "
                               "stick. Choose folders only to keep it inside them.",
                "multiple": True,
                "required": False,
            },
        },
        "compatibility": {"platforms": ["win32"]},
        "tools": [{"name": n, "description": d} for n, d in (
            ("open_show", "Open a show file"), ("new_show", "Start a new show file"),
            ("list_media", "Media files in a folder"), ("add_media_cue", "Add a video, sound or picture"),
            ("add_text_cue", "Add a caption"), ("add_action_cue", "Add a note, a fade or a level change"),
            ("add_group", "Make a scene"), ("validate_show", "Check the show"),
            ("save_show", "Save the show"), ("use_program", "Work on the show open in BlindCue"))],
    }


def build_mcpb(out_file: Path, version: str, icon_png: bytes | None = None) -> Path:
    """Write the extension file *out_file* for the assistant installed on this computer."""
    command, first_args = server_command()
    data = manifest(version, command, first_args)
    if icon_png is None:
        data.pop("icon")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(data, indent=2, ensure_ascii=False))
        if icon_png is not None:
            bundle.writestr("icon.png", icon_png)
    out_file.write_bytes(buffer.getvalue())
    return out_file


def client_config(folders: list[str]) -> str:
    """``mcpServers`` settings for other MCP clients (Claude Code, Cursor, ...)."""
    command, first_args = server_command()
    limit = ["--root", *folders] if folders else []           # no folder: every drive (2026-11-24)
    config = {"mcpServers": {"blindcue": {"command": command, "args": [*first_args, *limit]}}}
    return json.dumps(config, indent=2, ensure_ascii=False)
