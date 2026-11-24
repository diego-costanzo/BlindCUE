"""Thumbnails of pictures and videos in the editing list (stage 4.4).

A small picture in the name cell instead of the IMG / VID badge, so the
teacher recognises "the photo of the class" without opening it. Pictures are
read at a reduced size (``QImageReader.setScaledSize``); a video gives the
frame at 1 s through ffmpeg (no thumbnail when ffmpeg is missing). The work
runs on the background analysis pool, never during the show, and the result
is kept in memory (a few hundred small images).

On a weak computer they can be switched off (View menu); "auto", the default,
leaves them off with the Eco hardware profile (setting ``ui/list_thumbnails``:
``auto`` / ``on`` / ``off``).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections import OrderedDict

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap

from engine.runtime_limits import child_process_kwargs, low_priority_prefix

logger = logging.getLogger(__name__)

SETTINGS_KEY = "ui/list_thumbnails"
AUTO, ON, OFF = "auto", "on", "off"
THUMB_SIZE = QSize(128, 72)  # read size; drawn at the row height (16:9)
CACHE_LIMIT = 400


def thumbnails_wanted(setting: str, profile: str) -> bool:
    """Thumbnails shown for the *setting* and the effective hardware *profile*."""
    setting = str(setting or AUTO).lower()
    if setting == ON:
        return True
    if setting == OFF:
        return False
    return str(profile or "").lower() != "eco"


def _picture(path: str) -> QImage | None:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0:
        reader.setScaledSize(size.scaled(THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    return None if image.isNull() else image


def _video_frame(path: str) -> QImage | None:
    """The frame at 1 s (at 0 s for a shorter video), via ffmpeg; None without ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    for at in ("1", "0"):
        try:
            result = subprocess.run(
                [*low_priority_prefix(), ffmpeg, "-v", "quiet", "-ss", at, "-i", path, "-frames:v", "1",
                 "-vf", f"scale={THUMB_SIZE.width()}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                capture_output=True, timeout=15, stdin=subprocess.DEVNULL, check=False, **child_process_kwargs(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("[THUMB] ffmpeg failed for %s: %s", path, exc)
            return None
        if result.returncode == 0 and result.stdout:
            image = QImage.fromData(result.stdout, "PNG")
            if not image.isNull():
                return image
    return None


class _Signals(QObject):
    done = Signal(object, object)  # key, QImage | None


class _ThumbJob(QRunnable):
    def __init__(self, key: str, kind: str, signals: _Signals) -> None:
        super().__init__()
        self._key = key
        self._kind = kind
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # worker thread: QImage only, never QPixmap
        path = self._key
        try:
            if not os.path.isfile(path):  # a missing file (or a slow network path) only costs this thread
                image = None
            else:
                image = _video_frame(path) if self._kind == "VIDEO" else _picture(path)
        except Exception:  # noqa: BLE001 - a thumbnail never breaks the list
            logger.debug("[THUMB] %s failed", path, exc_info=True)
            image = None
        try:
            self._signals.done.emit(self._key, image)
        except RuntimeError:
            pass  # the window closed meanwhile


class ThumbnailCache(QObject):
    """Thumbnails by file path; made in the background (the list paint never touches the disk)."""

    ready = Signal()  # a new thumbnail can be drawn

    def __init__(self, pool: QThreadPool | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._pixmaps: OrderedDict[str, QPixmap | None] = OrderedDict()
        self._pending: set[str] = set()
        self._paused = False
        self._signals = _Signals(self)
        self._signals.done.connect(self._on_done, Qt.ConnectionType.QueuedConnection)

    def set_paused(self, paused: bool) -> None:
        """Nothing new is made (e.g. while a show runs)."""
        self._paused = bool(paused)

    def forget(self, path: str) -> None:
        """The file changed (another file chosen, edited outside): made again when drawn."""
        self._pixmaps.pop(path, None)

    def get(self, path: str, kind: str) -> QPixmap | None:
        """The thumbnail of *path* when it is ready; else None (and it gets made)."""
        if kind not in ("IMAGE", "VIDEO") or not path:
            return None
        if path in self._pixmaps:
            self._pixmaps.move_to_end(path)
            return self._pixmaps[path]
        if path not in self._pending and not self._paused:
            self._pending.add(path)
            self._pool.start(_ThumbJob(path, kind, self._signals))
        return None

    def _on_done(self, key: str, image: QImage | None) -> None:
        self._pending.discard(key)
        self._pixmaps[key] = QPixmap.fromImage(image) if image is not None and not image.isNull() else None
        while len(self._pixmaps) > CACHE_LIMIT:
            self._pixmaps.popitem(last=False)
        self.ready.emit()

    def pending(self) -> int:
        return len(self._pending)
