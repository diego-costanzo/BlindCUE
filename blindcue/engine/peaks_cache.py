"""Stage 3, item 3.4: waveform peaks kept on disk. No Qt (but for finding the folder).

Decoding a long file for its waveform takes seconds; a show opened again (or
a file used by several cues) now draws its waveform at once. One small
``.npz`` per file in the app data folder (``waveforms``), named by a hash of
the absolute path, the modification time and the size: a file changed or
replaced gets a new entry, an old entry is simply never read again. The
oldest entries go when there are more than ``MAX_FILES``.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

VERSION = 1          # bump when the peaks are computed differently (old entries are ignored)
MAX_FILES = 400      # ~13 KB each with 3200 bins: a few MB at most
_SUFFIX = ".npz"


def default_dir() -> str | None:
    """``<app data>/waveforms`` (``%LOCALAPPDATA%\\BlindCue\\BlindCue\\waveforms`` on Windows)."""
    try:
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    except Exception:  # noqa: BLE001 - no Qt: no cache, never an error
        return None
    return os.path.join(base, "waveforms") if base else None


def cache_key(media_path: str) -> str | None:
    """The entry name of *media_path* as it is now (None: the file is not there)."""
    try:
        st = os.stat(media_path)
    except OSError:
        return None
    raw = f"{VERSION}|{os.path.normcase(os.path.abspath(media_path))}|{st.st_mtime_ns}|{st.st_size}"
    return hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


def load(cache_dir: str | None, media_path: str) -> tuple[np.ndarray, float | None] | None:
    """(peaks 0..1, duration in s or None) kept for *media_path*, or None."""
    key = cache_key(media_path) if cache_dir else None
    if key is None:
        return None
    entry = Path(cache_dir) / f"{key}{_SUFFIX}"
    try:
        with np.load(entry, allow_pickle=False) as data:
            peaks = np.asarray(data["peaks"], dtype=np.float32)
            duration = float(data["duration"]) if "duration" in data.files else 0.0
    except (OSError, ValueError, KeyError, EOFError):
        return None
    if peaks.ndim != 1 or peaks.size == 0 or not np.all(np.isfinite(peaks)):
        return None
    with contextlib.suppress(OSError):
        os.utime(entry)  # recently used: kept by prune()
    return peaks, (duration if duration > 0 else None)


def store(cache_dir: str | None, media_path: str, peaks: np.ndarray, duration: float | None) -> bool:
    """Keep *peaks* for *media_path* (written to a temporary file, then moved in place)."""
    key = cache_key(media_path) if cache_dir else None
    if key is None or peaks is None or len(peaks) == 0:
        return False
    tmp_name = ""
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".tmp", delete=False) as fh:
            tmp_name = fh.name
            np.savez(fh, peaks=np.asarray(peaks, dtype=np.float32),
                     duration=np.float64(duration if duration and duration > 0 else 0.0))
        os.replace(tmp_name, os.path.join(cache_dir, f"{key}{_SUFFIX}"))
    except OSError as exc:
        logger.debug("[WAVEFORM] peaks not cached: %s", exc)
        if tmp_name:
            with contextlib.suppress(OSError):
                os.remove(tmp_name)
        return False
    prune(cache_dir)
    return True


def prune(cache_dir: str, keep: int = MAX_FILES) -> int:
    """Remove the entries used longest ago beyond *keep*; returns how many went."""
    try:
        entries = [p for p in Path(cache_dir).iterdir() if p.suffix == _SUFFIX]
    except OSError:
        return 0
    if len(entries) <= keep:
        return 0
    entries.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0)
    removed = 0
    for old in entries[: len(entries) - keep]:
        with contextlib.suppress(OSError):
            old.unlink()
            removed += 1
    return removed
