"""Evaluation 2026-11-24: file dialogs open in Documents\\BlindCue / the last folder; "Add files…" takes many."""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models.cue import MediaType
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_show_and_media_folders(tmp_path):
    from ui import dialog_dirs

    settings = QSettings("BlindCue", "BlindCue")
    settings.remove("paths")
    first = dialog_dirs.show_dir()
    assert first.endswith(dialog_dirs.SHOWS_FOLDER) and os.path.isdir(first)
    assert "Programs" not in first and "BlindCue-PL" not in first          # never the install folder
    name = dialog_dirs.new_show_path("Przedstawienie")
    assert name.endswith(f"Przedstawienie {date.today().isoformat()}.blindcue")
    dialog_dirs.remember_show_dir(str(tmp_path / "x.blindcue"))
    assert dialog_dirs.show_dir() == str(tmp_path)
    dialog_dirs.remember_media_dir(str(tmp_path / "song.mp3"))
    assert dialog_dirs.media_dir("AUDIO") == str(tmp_path)
    settings.remove("paths")


def test_add_files_takes_many_in_name_order(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _cue_manip
    from ui.output_window import OutputWindow

    files = []
    for name in ("b.png", "10.png", "2.png"):
        (tmp_path / name).write_bytes(b"png")
        files.append(str(tmp_path / name))
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        monkeypatch.setattr(_cue_manip.QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: (files, "")))
        asked = []
        monkeypatch.setattr(win, "_ask_scene", lambda n, answer: asked.append(n))
        win._cue_list_panel.btn_add_files.click()
        assert [c.name for c in win._cues] == ["2", "10", "b"]
        assert all(c.media_type == MediaType.IMAGE for c in win._cues) and asked == [3]
        assert QSettings("BlindCue", "BlindCue").value("paths/media_dir") == str(tmp_path)
    finally:
        QSettings("BlindCue", "BlindCue").remove("paths")
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
