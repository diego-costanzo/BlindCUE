"""3.7: the "Now playing" cards and the list tell the time left in real seconds at a tempo != 100 %."""

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
from engine.live_state import PHASE_POST, LiveClocks, short_time_text
from models.cue import Cue, CueStatus, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_clock_counts_real_seconds_at_a_tempo():
    clocks = LiveClocks()
    clocks.start(2, 7, timed=True, duration=60.0)
    clocks.progress(2, 20.0, start=0.0, end=60.0)
    plain = clocks.cue_time(7)
    fast = clocks.cue_time(7, 2.0)
    slow = clocks.cue_time(7, 0.5)
    assert plain.remaining == 40.0 and fast.remaining == 20.0 and slow.remaining == 80.0
    assert fast.elapsed == 10.0 and fast.fraction == plain.fraction
    assert short_time_text(fast) == "-00:20"
    clocks.phase(2, 7, PHASE_POST, 1.0, 3.0)
    assert clocks.cue_time(7, 2.0).remaining == 2.0          # a wait is real time already


@pytest.fixture()
def window():
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
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


def test_now_playing_card_shows_the_real_time_left(window):
    cue = Cue(name="dance", media_type=MediaType.AUDIO, file_path="dance.wav", layer=2, playback_rate=2.0)
    cue.status = CueStatus.LIVE
    window._cues = [cue]
    window._live_clocks.start(2, cue.cue_id, timed=True, duration=60.0)
    window._live_clocks.progress(2, 20.0, start=0.0, end=60.0)
    card = next(c for c in window._now_playing_cards() if c.cue_id == cue.cue_id)
    assert card.remaining == "-00:20" and card.elapsed == "00:10"
    assert window._cue_tempo(Cue(name="p", media_type=MediaType.IMAGE, file_path="p.png")) == 1.0
