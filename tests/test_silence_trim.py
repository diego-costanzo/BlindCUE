"""Stage 3, item 3.4: cut the silence at the start and the end of a sound."""

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

import numpy as np
import pytest
from engine.silence_trim import sound_bounds
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_bounds():
    peaks = [0.0] * 30 + [0.2, 1.0, 0.5] + [0.001] * 60 + [0.3] + [0.0] * 6   # 100 bins over 10 s
    assert sound_bounds(peaks, 10.0) == (2.95, 9.45)
    assert sound_bounds([0.5] * 100, 10.0) == (0.0, None)          # sound from the first to the last bin
    assert sound_bounds([0.0] * 100, 10.0) is None                 # a silent file: nothing to cut
    assert sound_bounds([], 10.0) is None and sound_bounds([1.0], 0.0) is None


@pytest.fixture()
def window(tmp_path):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    path = tmp_path / "song.wav"
    path.write_bytes(b"RIFF")
    win._cues = [Cue.from_dict({"cue_id": 9801, "name": "song", "media_type": MediaType.AUDIO.value,
                                "file_path": str(path)})]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    win._commit_undo_point()  # the show as loaded
    _pump()
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_button_sets_in_and_out(window):
    cue = window._cues[0]
    window._waveform_cache[os.path.abspath(cue.file_path)] = np.array([0.0] * 20 + [1.0] * 60 + [0.0] * 20,
                                                                    dtype=np.float32)
    window._active_test_duration = 100.0
    window._inspector.silence_trim_requested.emit()
    assert (cue.in_point, cue.out_point) == (19.95, 80.05)
    window._on_undo()
    assert window._cues[0].in_point == 0.0                          # one Ctrl+Z takes it back
