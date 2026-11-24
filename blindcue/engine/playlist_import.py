"""Playlists from other players (stage 3, item 3.3): .m3u / .m3u8 files.

A line is a file path (absolute, or relative to the playlist's folder) or a
``file://`` URL (also ``file://server/share/...``); ``#EXTM3U`` / ``#EXTINF``
and other ``#`` lines are comments, http(s) streams are skipped. The text
is UTF-16 when it has a BOM, otherwise UTF-8, the system's code page or a
Windows one - whichever finds the most files (an .m3u written by a Windows
player is in the ANSI code page of that computer).
"""

from __future__ import annotations

import locale
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

PLAYLIST_EXT = {".m3u", ".m3u8"}


def _texts(data: bytes) -> list[str]:
    """The playlist decoded every plausible way, the most likely first."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return [data.decode("utf-16")]
        except UnicodeDecodeError:
            pass
    out: list[str] = []
    for enc in ("utf-8-sig", locale.getpreferredencoding(False), "cp1250", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if text not in out:
            out.append(text)
    return out


def _target(line: str, base: Path) -> Path:
    if line.lower().startswith("file:"):
        parsed = urlparse(line)
        path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            path = "//" + parsed.netloc + path  # file://server/share/a.mp3 -> \\server\share\a.mp3
        elif len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]  # file:///C:/x.mp3 -> C:/x.mp3
        target = Path(path)
    else:
        target = Path(line)
    if not target.is_absolute() and not str(target).startswith(("\\\\", "//")):
        target = base / target
    return Path(os.path.normpath(target))


def _entries(text: str, base: Path) -> tuple[list[str], list[str]]:
    found: list[str] = []
    skipped: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("http://", "https://")):
            skipped.append(line)
            continue
        try:
            target = _target(line, base)
            ok = target.is_file()
        except (OSError, ValueError):
            ok = False
        if ok:
            found.append(str(target))
        else:
            skipped.append(line)
    return found, skipped


def read_m3u(path: str | Path) -> tuple[list[str], list[str]]:
    """(files that exist, entries that were skipped: missing files and streams), in playlist order."""
    path = Path(path)
    best: tuple[list[str], list[str]] | None = None
    for text in _texts(path.read_bytes()):
        found, skipped = _entries(text, path.parent)
        if best is None or len(found) > len(best[0]):
            best = (found, skipped)
        if not skipped:
            break
    return best or ([], [])
