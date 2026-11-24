"""Stage 5, item 5.15: the cue's file in other programs, watched for changes."""

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

from engine.external_tools import MAX_PROGRAMS, add_program, changed_files, parse_programs, to_setting
from models.cue import Cue
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QMenu


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_programs_and_changed_files(tmp_path):
    assert parse_programs("") == [] and parse_programs("{bad") == [] and parse_programs('[{"x": 1}]') == []
    progs = add_program([], r"C:\Tools\Audacity\audacity.exe")
    progs = add_program(progs, r"C:\Tools\GIMP\gimp.exe")
    progs = add_program(progs, r"C:\Tools\Audacity\audacity.exe")          # moves up, no duplicate
    assert [p["name"] for p in progs] == ["audacity", "gimp"]
    assert parse_programs(to_setting(progs)) == progs
    many = []
    for i in range(MAX_PROGRAMS + 3):
        many = add_program(many, f"C:\\p{i}.exe")
    assert len(many) == MAX_PROGRAMS
    times = {"a.wav": 1.0, "b.png": 2.0, "gone.mp3": 3.0}
    stat = {"a.wav": 1.0, "b.png": 5.0}

    def mtime(path):
        if path not in stat:
            raise OSError(path)
        return stat[path]

    assert changed_files(times, mtime) == ["b.png"] and times["b.png"] == 5.0
    assert changed_files(times, mtime) == []                                 # seen once


def test_row_menu_open_with_and_refresh(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _external_tools as mod
    from ui.output_window import OutputWindow

    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    started, waved = [], []
    try:
        win._cues = [Cue(name="song", media_type=mod.MediaType.AUDIO, file_path=str(song))]
        win._refresh_cue_list(keep_selection=False)
        monkeypatch.setattr(mod.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *a, **k: (r"C:\Tools\Audacity\audacity.exe", "")))
        win._add_tool_program()
        menu = QMenu()
        win._extend_file_menu(menu, [0])
        sub = menu.actions()[0].menu()
        texts = [a.text() for a in sub.actions() if a.text()]
        assert len(texts) == 4 and "audacity" in texts[2]
        monkeypatch.setattr(mod.QProcess, "startDetached",
                            staticmethod(lambda prog, args: started.append((prog, args)) or True))
        sub.actions()[2].trigger()
        assert started == [(r"C:\Tools\Audacity\audacity.exe", [str(song)])]
        win._waveform_cache[os.path.abspath(str(song))] = "old peaks"
        win._known_file_durations[str(song)] = 9.0
        monkeypatch.setattr(win, "_request_waveform", lambda cue: waved.append(cue.name))
        os.utime(song, (time.time() + 60, time.time() + 60))                 # "saved in the editor"
        assert win._check_watched_files() == [str(song)]
        assert os.path.abspath(str(song)) not in win._waveform_cache and str(song) not in win._known_file_durations
        assert waved == ["song"] and "song.wav" in win._status_label.text()
        assert win._check_watched_files() == []
    finally:
        QSettings("BlindCue", "BlindCue").remove("tools")
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
