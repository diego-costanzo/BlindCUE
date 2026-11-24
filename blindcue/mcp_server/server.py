"""MCP server: an AI assistant prepares BlindCue show files (stage 1M, M1).

Run it from an MCP client (Claude Desktop, Claude Code, …) as a local
process over stdio, naming the folders it may use::

    python <blindcue>/mcp_server/server.py --root "D:/Shows" --root "D:/Media"

``BLINDCUE_MCP_ROOTS`` (folders separated by ``os.pathsep``) works too. The
server never listens on the network. It works on show files; a show open in
the running program can be read but not saved (see ``show_tools``).

This module is only the thin MCP layer: every rule lives in
``show_tools.ShowSession`` so it can be tested without an MCP client.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
# The installed program (PyInstaller): data files sit in its _internal folder.
DATA_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))

from mcp.server.fastmcp import FastMCP

from mcp_server.show_tools import (
    AccessPolicy,
    ShowSession,
    ToolError,
    cue_schema,
    ensure_qt_gui,
)

INSTRUCTIONS = """\
BlindCue runs school theatre shows: a list of cues (videos, sounds, pictures,
captions, actions) that the operator starts one by one with GO.

You help the teacher PREPARE a show file. Work like this:
1. open_show (or new_show) inside an allowed folder; list_media on the media folder.
2. Build the list in the order of the play: add_media_cue / add_text_cue /
   add_action_cue / add_group. Music goes on layer 2, pictures and videos on
   layer 1, captions on layer 3. Use follow_mode SIMULTANEOUS to start a cue
   together with the next one, AUTO_FOLLOW to start the next one at its end.
3. validate_show, fix what it reports, then save_show and tell the teacher to
   open the show in BlindCue and check it in the Rehearsal mode.
If the teacher has BlindCue open and allowed the assistant there (Show menu),
use_program works on the open show instead: every change appears at once and
Ctrl+Z undoes it; changes are possible only in the Preparation mode.
Never invent media files: use the paths list_media returns. Keep names short
and in the teacher's language. Ask before deleting cues."""

mcp = FastMCP("blindcue-show", instructions=INSTRUCTIONS)
FILES: ShowSession | None = None   # show files
SESSION: Any = None                # FILES, or a ProgramSession while connected to the program


def _session() -> Any:
    if SESSION is None:  # pragma: no cover - set by main()
        raise ToolError("The server was started without allowed folders.")
    return SESSION


def _call(fn, *args, **kwargs) -> Any:
    """Run a session method; a refusal becomes a plain message for the assistant."""
    try:
        return fn(*args, **kwargs)
    except ToolError as exc:
        return {"error": str(exc)}
    except (OSError, ValueError, TypeError) as exc:
        return {"error": f"Not possible: {exc}"}


# ── tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def allowed_folders() -> dict[str, Any]:
    """The folders this server may read and write (show files and media)."""
    return {"folders": _files().policy.describe()}


@mcp.tool()
def use_program() -> dict[str, Any]:
    """Work on the show open in BlindCue right now (the teacher must allow it in the Show menu).

    Changes appear in the program at once, each one is an Undo step, and they are
    possible only while the teacher is in the Preparation mode.
    """
    global SESSION
    from mcp_server.program_link import ProgramSession

    try:
        link = ProgramSession(_files().policy)
    except ToolError as exc:
        return {"error": str(exc)}
    if SESSION is not FILES and hasattr(SESSION, "close"):
        SESSION.close()
    SESSION = link
    return {"connected": True, **(link.hello or {})}


@mcp.tool()
def use_files() -> dict[str, Any]:
    """Work on show files again (new_show / open_show / save_show) instead of the program."""
    global SESSION
    if SESSION is not FILES and hasattr(SESSION, "close"):
        SESSION.close()
    SESSION = FILES
    return {"connected": False, "folders": _files().policy.describe()}


@mcp.tool()
def new_show(path: str) -> dict[str, Any]:
    """Start a new, empty show file at *path* (.blindcue; saved by save_show)."""
    return _call(_session().new_show, path)


@mcp.tool()
def open_show(path: str) -> dict[str, Any]:
    """Open an existing .blindcue show file to read or change it."""
    return _call(_session().open_show, path)


@mcp.tool()
def list_cues() -> dict[str, Any]:
    """Every cue of the open show in order: number, cue_id, name, type, layer, file, follow mode, notes."""
    return _call(lambda: {"cues": _session().list_cues()})


def _files() -> ShowSession:
    """The file side (media folders are always read here, also while connected to the program)."""
    if FILES is None:  # pragma: no cover - set by main()
        raise ToolError("The server was started without allowed folders.")
    return FILES


@mcp.tool()
def get_cue(cue_id: int) -> dict[str, Any]:
    """All settings of one cue."""
    return _call(_session().get_cue, cue_id)


@mcp.tool()
def list_media(folder: str, recursive: bool = False, durations: bool = True) -> dict[str, Any]:
    """Video, audio and picture files in *folder* with type, size and (with *durations*) length in seconds."""
    return _call(_files().list_media, folder, recursive, durations)


@mcp.tool()
def add_media_cue(path: str, after_cue_id: int | None = None,
                  fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add a cue playing a media file (from list_media) after *after_cue_id* (default: at the end).

    *fields* sets cue settings at once, e.g. {"name": "Overture", "fade_in": 2,
    "follow_mode": "SIMULTANEOUS"}; see the resource blindcue://schema/cue.
    """
    return _call(_session().add_media_cue, path, after_cue_id, fields)


@mcp.tool()
def add_text_cue(text: str, after_cue_id: int | None = None, size: int = 90, position: str = "bottom",
                 color: str = "#ffffff", fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add an on-screen caption (layer 3, soft fades). Several lines: separate them with newlines.

    *position*: top, center or bottom; *size*: pixels at 1920x1080 (12-400).
    """
    return _call(_session().add_text_cue, text, after_cue_id, size, position, color, fields)


@mcp.tool()
def add_action_cue(kind: str, after_cue_id: int | None = None, spec: dict[str, Any] | None = None,
                   name: str | None = None, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add a cue without a file that acts on other cues or speaks to the operator.

    *kind*: stop, fade, release, level, opacity, note (see describe_fields). *spec*
    examples: {"target": "cues", "cue_ids": [12], "duration": 3} (fade a cue),
    {"target": "layer", "layer": 2, "mode": "relative", "db": -12, "duration": 2}
    (music down under a dialogue), {"text": "Wait for the curtain"} (note).
    """
    return _call(_session().add_action_cue, kind, after_cue_id, spec, name, fields)


@mcp.tool()
def add_group(name: str, cue_ids: list[int] | None = None, mode: str = "STEP",
              after_cue_id: int | None = None) -> dict[str, Any]:
    """Make a scene: a group holding *cue_ids* (moved under it), or an empty one.

    *mode*: STEP (one GO per item), SEQUENCE (one GO plays all in a row),
    SIMULTANEOUS (all together), RANDOM, LOOP.
    """
    return _call(_session().add_group, name, cue_ids, mode, after_cue_id)


@mcp.tool()
def update_cue(cue_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    """Change settings of a cue, e.g. {"volume": 0.6, "fade_out": 3, "notes": "after the bow"}.

    Captions also take {"text": "..."}; action cues {"action": {...spec...}}.
    """
    return _call(_session().update_cue, cue_id, fields)


@mcp.tool()
def move_cue(cue_id: int, after_cue_id: int | None = None, to_top: bool = False,
             into_group_id: int | None = None) -> dict[str, Any]:
    """Move a cue (a group with its items) after another cue, to the top, to the end of a group
    (*into_group_id*), or with no target to the end of the show."""
    return _call(_session().move_cue, cue_id, after_cue_id, to_top, into_group_id)


@mcp.tool()
def delete_cue(cue_id: int, with_items: bool = False) -> dict[str, Any]:
    """Remove a cue from the show (its media file stays). A group's items stay unless *with_items*."""
    return _call(_session().delete_cue, cue_id, with_items)


@mcp.tool()
def validate_show() -> dict[str, Any]:
    """Check the show: missing files, actions without a target, layer conflicts, loose chains."""
    return _call(_session().validate_show)


@mcp.tool()
def save_show(path: str | None = None) -> dict[str, Any]:
    """Save the show (a .bak copy of the old file is kept). *path*: save under another name."""
    return _call(_session().save_show, path)


# ── resources and prompt ─────────────────────────────────────────────────────

@mcp.resource("blindcue://schema/cue", mime_type="application/json")
def schema_resource() -> dict[str, Any]:
    """What a cue can hold and which settings the tools accept."""
    return cue_schema()


@mcp.resource("blindcue://show/summary", mime_type="application/json")
def summary_resource() -> dict[str, Any]:
    """The open show: file, number of cues by type, unsaved changes."""
    return _call(_session().summary)


@mcp.resource("blindcue://manual/{lang}", mime_type="text/plain")
def manual_resource(lang: str) -> str:
    """The user manual as plain text (lang: pl, en or it)."""
    lang = lang if lang in ("pl", "en", "it") else "en"
    html = (DATA_DIR / "help" / f"manual_{lang}.html").read_text(encoding="utf-8")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>|</(p|li|h[1-6]|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


@mcp.prompt()
def prepare_show(script: str, media_folder: str, show_file: str) -> str:
    """Prepare a show from a script and a folder of media."""
    return (
        f"Prepare the BlindCue show '{show_file}' for this play.\n\n"
        f"Media folder: {media_folder}\n\nScript (with stage directions):\n{script}\n\n"
        "Open or create the show, list the media, then build the cues in the order of the "
        "script: pictures/videos for each scene (layer 1), music (layer 2, fade in/out), "
        "captions for titles or dialogue (layer 3), notes for the operator where the script "
        "says something must happen backstage, and a level action that lowers the music under "
        "spoken scenes. Group each scene. Run validate_show, fix the problems, save, and give me "
        "a short list of what you did and what I should check in the Rehearsal mode."
    )


# ── start ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BlindCue show assistant (MCP server, stdio)")
    # "--root A B" (what Claude Desktop passes for several folders) and "--root A --root B".
    parser.add_argument("--root", action="extend", nargs="+", default=[],
                        help="folders the assistant may use")
    args = parser.parse_args(argv)
    roots = list(args.root)
    env = os.environ.get("BLINDCUE_MCP_ROOTS", "")
    roots += [r for r in env.split(os.pathsep) if r.strip()]
    # stdout carries the protocol: logs go to stderr only.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    # Load numpy and Qt now, on the main thread: on Windows a first import of
    # numpy's DLLs while the stdio reader thread waits on stdin hung forever.
    from engine import audio_analyzer, text_render  # noqa: F401  (numpy, ffprobe; captions)
    ensure_qt_gui()
    global SESSION, FILES
    FILES = ShowSession(AccessPolicy(roots))
    SESSION = FILES
    mcp.run("stdio")


if __name__ == "__main__":
    main()
