"""LivePlayer.fade_out follows the clock: a 1 s fade reaches silence in ~1 s.

It used to count 33 ms timer ticks; Windows delivers them late, which made a
1 s fade last about 1.4 s (measured in the real program).
"""

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
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_fade_out_duration_follows_the_clock(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    _, audio = lp._deck_pair()
    audio.setVolume(0.8)
    done: list[float] = []
    t0 = time.monotonic()
    lp.fade_out(1.0, callback=lambda: done.append(time.monotonic() - t0))
    mid_level = None
    while not done and time.monotonic() - t0 < 3.0:
        QCoreApplication.processEvents()
        if mid_level is None and time.monotonic() - t0 >= 0.5:
            mid_level = audio.volume()
        time.sleep(0.002)
    assert done, "fade_out never finished"
    assert 0.95 <= done[0] <= 1.15, f"fade took {done[0]:.3f} s"
    assert audio.volume() == 0.0
    assert mid_level is not None and 0.3 <= mid_level <= 0.5, f"level at 0.5 s: {mid_level}"
    lp.deleteLater()
