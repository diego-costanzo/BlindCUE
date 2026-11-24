"""Other programs for a cue's file (stage 5, item 5.15). No Qt.

"Open with…" a sound or picture editor from the cue's menu, a short list of
favourite programs per computer, and the files handed to them watched: when
one comes back changed, its waveform and length are read again.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

MAX_PROGRAMS = 8


def parse_programs(raw: object) -> list[dict[str, str]]:
    """The favourite programs from the settings value (JSON text); never raises."""
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    except (TypeError, ValueError):
        return []
    out: list[dict[str, str]] = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"].strip():
            path = item["path"].strip()
            out.append({"name": str(item.get("name") or Path(path).stem), "path": path})
    return out[:MAX_PROGRAMS]


def add_program(programs: list[dict[str, str]], path: str) -> list[dict[str, str]]:
    """*path* first in the list (a program already there moves up), at most MAX_PROGRAMS."""
    key = os.path.normcase(os.path.abspath(path))
    rest = [p for p in programs if os.path.normcase(os.path.abspath(p["path"])) != key]
    return ([{"name": Path(path).stem, "path": path}] + rest)[:MAX_PROGRAMS]


def to_setting(programs: list[dict[str, str]]) -> str:
    return json.dumps(programs[:MAX_PROGRAMS], ensure_ascii=False)


def changed_files(watched: dict[str, float],
                  mtime: Callable[[str], float] = os.path.getmtime) -> list[str]:
    """Files whose modification time differs from the one seen when they were handed over
    (updated in *watched*); a file that is gone is left alone."""
    out: list[str] = []
    for path, seen in list(watched.items()):
        try:
            now = mtime(path)
        except OSError:
            continue
        if now != seen:
            watched[path] = now
            out.append(path)
    return out
