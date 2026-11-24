"""Stage 3, item 3.7: tempo of a cue (playback rate), keeping the pitch."""

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

import pytest
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(**extra) -> Cue:
    data = {"cue_id": 9851, "name": "dance", "media_type": MediaType.AUDIO.value, "file_path": "/x/dance.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_model():
    cue = _cue(playback_rate=1.25, keep_pitch=False)
    back = Cue.from_dict(cue.to_dict())
    assert back.playback_rate == 1.25 and back.keep_pitch is False
    assert _cue(playback_rate=9).playback_rate == 2.0 and _cue().playback_rate == 1.0 and _cue().keep_pitch


def test_live_player_takes_the_tempo(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.set_rate(1.5, keep_pitch=True)
    assert lp._player.playbackRate() == pytest.approx(1.5)
    lp.set_rate(5.0)
    assert lp._player.playbackRate() == pytest.approx(2.0)          # clamped
    lp.shutdown()


def test_marker_wait_counts_in_real_time(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        song = _cue(playback_rate=2.0, markers=[{"id": 1, "name": "x", "sec": 10.0}])
        dep = _cue(cue_id=9852, start_rel_cue=9851, start_rel_when="marker", start_rel_marker=1)
        assert win._marker_wait(song, dep, 0.0) == pytest.approx(5.0)   # 10 s of the file at 200 % = 5 s
        insp = win._inspector
        insp.load_cue(song, 0)
        assert insp.spin_rate.value() == 200.0
        insp.spin_rate.setValue(80.0)
        insp.apply_to_cue(song)
        assert song.playback_rate == 0.8
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_second_deck_gets_the_tempo(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.set_rate(0.75)
    lp._ensure_standby_deck()                                       # created later (loops, sections)
    assert lp._standby_player.playbackRate() == pytest.approx(0.75)
    lp.shutdown()
