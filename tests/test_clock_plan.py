"""Stage 2, item 2.6: cues that start at a time of day."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.clock_plan import due, next_timed, normalize_clock, parse_clock
from engine.show_engine import outside_go_order
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


def _cue(i: int, **extra) -> Cue:
    data = {"cue_id": 9951 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_parse_due_and_next():
    assert parse_clock("7:05").hour == 7 and parse_clock("19:55:30").second == 30
    assert parse_clock("24:00") is None and parse_clock("ab") is None and normalize_clock("7:5") == ""
    assert normalize_clock("7:05") == "07:05"
    assert Cue.from_dict(_cue(0, start_clock="25:00").to_dict()).start_clock == ""
    bell, music, late = _cue(0, start_clock="19:55"), _cue(1, start_clock="20:30"), _cue(2, start_clock="19:00")
    assert outside_go_order(bell)
    now = datetime(2026, 11, 24, 19, 55, 20)
    start, skip = due([bell, music, late], now, set())
    assert start == [bell] and skip == [late]                 # an hour late: skipped, never started
    assert next_timed([bell, music, late], now, {bell.cue_id})[0] is music
    assert due([_cue(3, start_clock="19:55", enabled=False)], now, set()) == ([], [])


class _At1955(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 24, 19, 55, 5)


@pytest.fixture()
def window(qt_app, monkeypatch):
    from ui.main_window import MainWindow
    from ui.main_window import _clock_plan
    from ui.output_window import OutputWindow

    monkeypatch.setattr(_clock_plan, "datetime", _At1955)  # ticks without a time use this one, not the real clock
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    win._cues = [_cue(0, name="music"), _cue(1, name="bell", start_clock="19:55"),
                 _cue(2, name="old", start_clock="18:00"), _cue(3, name="next")]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[int] = []
    win.cue_fired.connect(lambda c: fired.append(c.cue_id))
    win.fired = fired
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


def test_the_plan_runs_in_the_show_only_and_can_be_held(window):
    at = datetime(2026, 11, 24, 19, 55, 5)
    window._clock_tick(at)                                       # Preparation: only the clock
    assert window.fired == [] and "19:55" in window._lbl_clock.text()
    window.set_live_mode(True)
    window._toggle_clock_hold(True)
    window._clock_tick(at)
    assert window.fired == []                                    # held
    window._toggle_clock_hold(False)
    window._clock_tick(at)
    assert window.fired == [9952] and "18:00" not in str(window.fired)   # "old" skipped (too late)
    window._clock_tick(at)
    assert window.fired == [9952]                                # once a day
    assert window._cue_list.currentRow() == 0                    # GO untouched
    window._on_go()
    assert window.fired[-1] == 9951 and window._cue_list.currentRow() == 3   # GO skips the timed cues


def test_review_midnight_pause_all_and_started_by_hand(window):
    from engine.clock_plan import occurrence, parse_clock

    late_night = datetime(2026, 11, 24, 23, 30)
    assert occurrence(late_night, parse_clock("00:10")) == datetime(2026, 11, 25, 0, 10)  # tomorrow, not skipped
    assert occurrence(datetime(2026, 11, 25, 0, 5), parse_clock("23:50")) == datetime(2026, 11, 24, 23, 50)
    assert due([_cue(5, start_clock="00:10")], late_night, set()) == ([], [])
    window.set_live_mode(True)
    window._is_global_paused = True                             # Pause All holds the plan too
    window._clock_tick(datetime(2026, 11, 24, 19, 55, 5))
    assert window.fired == []
    window._is_global_paused = False
    window._clock_handled.clear()
    window._cue_list.setCurrentRow(1)                           # the bell started by hand before its time
    window._fire_cue_chain(1, auto=False, keep_pointer=True)
    assert window._cues[1].cue_id in window._clock_handled
    window._clock_tick(datetime(2026, 11, 24, 19, 55, 5))
    assert window.fired.count(9952) == 1                        # the clock does not start it again


def test_review_half_typed_time_and_one_way_to_start(window):
    insp = window._inspector
    window._cue_list.setCurrentRow(1)                           # "bell", 19:55
    _pump()
    bell = window._cues[1]
    insp.edit_clock.setText("19:5")                             # still typing
    insp.apply_to_cue(bell)
    assert bell.start_clock == "19:55"                          # half-typed text never reaches the cue
    music = window._cues[0]
    window._cue_list.setCurrentRow(3)                           # "next": relative to "music", then a time
    _pump()
    nxt = window._cues[3]
    nxt.start_rel_cue, nxt.start_rel_when = music.cue_id, "start"
    insp.load_cue(nxt, 3)
    insp.edit_clock.setText("7:05")
    insp._last_field = "start_clock"
    insp.apply_to_cue(nxt)
    assert nxt.start_clock == "07:05" and nxt.start_rel_cue is None   # the time set last wins
