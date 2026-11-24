"""Where file dialogs open (evaluation 2026-11-24).

Before, Save / Open / "New show from a folder" opened in the program's own
install folder and the "Add" dialogs at C:\\ - a teacher saved a show where
she would never find it again (and an uninstall could take it). Now:
shows: the folder used last, at first ``Documents\\Teatr POZA``; media: the
folder used last, at first the system Videos / Music / Pictures folder.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

SHOWS_FOLDER = "Teatr POZA"


def _settings() -> QSettings:
    return QSettings("BlindCue", "BlindCue")


def _existing(value) -> str:
    text = str(value or "")
    return text if text and os.path.isdir(text) else ""


def show_dir() -> str:
    """The folder for show files: the last one used, else Documents\\Teatr POZA (made if missing)."""
    last = _existing(_settings().value("paths/show_dir", ""))
    if last:
        return last
    docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
    folder = Path(docs) / SHOWS_FOLDER
    try:
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder)
    except OSError:
        return docs


def remember_show_dir(path: str) -> None:
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if folder:
        _settings().setValue("paths/show_dir", folder)


def media_dir(kind: str = "") -> str:
    """The folder for media files: the last one used, else Videos / Music / Pictures by *kind*."""
    last = _existing(_settings().value("paths/media_dir", ""))
    if last:
        return last
    where = {"VIDEO": QStandardPaths.StandardLocation.MoviesLocation,
             "AUDIO": QStandardPaths.StandardLocation.MusicLocation,
             "IMAGE": QStandardPaths.StandardLocation.PicturesLocation}.get(
        kind, QStandardPaths.StandardLocation.DocumentsLocation)
    return QStandardPaths.writableLocation(where) or str(Path.home())


def remember_media_dir(path: str) -> None:
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if folder:
        _settings().setValue("paths/media_dir", folder)


def new_show_path(title: str) -> str:
    """A name to offer for a new show: "<title> 2026-11-24.blindcue" in the shows folder."""
    return str(Path(show_dir()) / f"{title} {date.today().isoformat()}.blindcue")
