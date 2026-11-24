"""Stage 5, item 5.10: missing files found again in a folder; another file for a cue."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine.relink import find_in_folder
from models.cue import Cue, CueStatus, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_find_in_folder_by_name(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "Bell.WAV").write_bytes(b"1")
    (tmp_path / "b" / "bell.wav").write_bytes(b"2")
    (tmp_path / "b" / "intro.mp4").write_bytes(b"3")
    found, twice = find_in_folder([r"D:\old\bell.wav", "/old/intro.mp4", "/old/gone.png", "/x/bell.wav"], tmp_path)
    assert found[r"D:\old\bell.wav"] == str(tmp_path / "a" / "Bell.WAV")       # the first folder wins
    assert found["/x/bell.wav"] == found[r"D:\old\bell.wav"]
    assert found["/old/intro.mp4"] == str(tmp_path / "b" / "intro.mp4")
    assert "/old/gone.png" not in found and twice == {"bell.wav"}


def test_window_finds_missing_and_chooses_a_file(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _relink
    from ui.output_window import OutputWindow

    (tmp_path / "song.mp3").write_bytes(b"ID3")
    (tmp_path / "clip.mp4").write_bytes(b"mp4")
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        song = Cue.from_dict({"cue_id": 9401, "name": "song", "media_type": "AUDIO",
                              "file_path": "/elsewhere/song.mp3"})
        song.status = CueStatus.OFFLINE
        empty = Cue(name="Film", file_path="", media_type=MediaType.AUDIO)
        empty.status = CueStatus.OFFLINE
        win._cues = [song, empty]
        win._refresh_cue_list(keep_selection=False)
        win._commit_undo_point()
        told = []
        monkeypatch.setattr(_relink.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
        monkeypatch.setattr(_relink.QMessageBox, "information", staticmethod(lambda *a, **k: told.append(a[2])))
        win._find_missing_files()
        assert win._cues[0].file_path == str(tmp_path / "song.mp3") and win._cues[0].status == CueStatus.LOADED
        assert "1" in told[0]
        win._on_undo()
        assert win._cues[0].file_path == "/elsewhere/song.mp3"                   # one Ctrl+Z
        win._cue_list.setCurrentRow(1)
        _pump()
        monkeypatch.setattr(_relink.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (str(tmp_path / "clip.mp4"), "")))
        win._choose_file_for_cue()
        film = win._cues[1]
        assert (film.file_path, film.media_type, film.status, film.name) == (
            str(tmp_path / "clip.mp4"), MediaType.VIDEO, CueStatus.LOADED, "Film")
        win._apply_inspector_to_cue()                                            # what the autosave does first
        assert win._cues[1].file_path == str(tmp_path / "clip.mp4")
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
