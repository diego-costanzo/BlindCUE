"""Live times in the cue lists (stage 1 phase C1).

The pure clock store and its text are tested on their own; the 10 Hz clock in
a headless MainWindow, fed the way main.py feeds the layer panels.
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
from engine.live_state import (
    PHASE_POST,
    PHASE_PRE,
    LiveClocks,
    ends_soon,
    fmt_clock,
    short_time_text,
)
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

# ── Pure store ───────────────────────────────────────────────────────


def test_playing_cue_reports_what_is_left():
    clocks = LiveClocks()
    clocks.start(2, 7, timed=True, duration=60.0)
    clocks.progress(2, 15.0, start=0.0, end=60.0, looping_inf=False)
    t = clocks.cue_time(7)
    assert t is not None
    assert t.elapsed == 15.0 and t.remaining == 45.0 and t.fraction == 0.25
    assert short_time_text(t) == "-0:45"
    assert not ends_soon(t)


def test_in_point_and_out_point_bound_the_clock():
    clocks = LiveClocks()
    clocks.start(1, 3, timed=True)
    clocks.progress(1, 12.0, start=10.0, end=20.0)
    t = clocks.cue_time(3)
    assert t.elapsed == 2.0 and t.remaining == 8.0 and abs(t.fraction - 0.2) < 1e-9


def test_last_seconds_warn():
    clocks = LiveClocks()
    clocks.start(2, 7, timed=True)
    clocks.progress(2, 56.2, start=0.0, end=60.0)
    t = clocks.cue_time(7)
    assert ends_soon(t)
    assert short_time_text(t) == "-0:04"   # a countdown rounds up


def test_endless_loop_never_warns():
    clocks = LiveClocks()
    clocks.start(2, 7, timed=True)
    clocks.progress(2, 9.0, start=0.0, end=10.0, looping_inf=True)
    t = clocks.cue_time(7)
    assert not ends_soon(t)
    assert short_time_text(t) == "-0:01∞"
    clocks.progress(2, 9.0, start=0.0, end=0.0)
    assert short_time_text(clocks.cue_time(7)) == "∞"


def test_unknown_length_shows_elapsed():
    clocks = LiveClocks()
    clocks.start(2, 7, timed=True)
    clocks.progress(2, 72.9)
    t = clocks.cue_time(7)
    assert t.remaining is None and t.fraction == -1.0
    assert short_time_text(t) == "1:12"


def test_waits_show_their_countdown():
    clocks = LiveClocks()
    clocks.phase(3, 9, PHASE_PRE, 1.0, 4.0)
    t = clocks.cue_time(9)
    assert t.phase == PHASE_PRE and t.remaining == 3.0
    assert short_time_text(t) == "⏳-0:03"
    assert not ends_soon(t)
    clocks.phase(3, 9, PHASE_POST, 0.5, 2.0)
    assert short_time_text(clocks.cue_time(9)) == "⏱-0:02"


def test_picture_without_hold_time_has_no_clock():
    clocks = LiveClocks()
    clocks.start(1, 4, timed=False)
    assert clocks.cue_time(4) is None


def test_forget_and_clear():
    clocks = LiveClocks()
    clocks.start(1, 4, timed=True)
    clocks.start(2, 5, timed=True)
    clocks.forget_cues({5})
    assert clocks.cue_ids() == {5}
    clocks.clear(2)
    assert clocks.is_empty()
    clocks.progress(2, 3.0)       # a report for an empty layer is ignored
    assert clocks.is_empty()


def test_fmt_clock():
    assert fmt_clock(0.0) == "0:00"
    assert fmt_clock(59.9) == "0:59"
    assert fmt_clock(59.1, up=True) == "1:00"
    assert fmt_clock(600.0, up=True) == "10:00"


# ── Director window ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture()
def window(qt_app):
    from models.cue import Cue, MediaType
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        Cue.from_dict({"cue_id": 8001 + i, "name": f"c{i}", "layer": 2,
                       "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(3)
    ]
    win._refresh_cue_list(keep_selection=False)
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


def _on_air(win, row: int, pos: float, end: float) -> None:
    """What main.py does when a cue starts and its player reports a position."""
    from models.cue import CueStatus

    cue = win._cues[row]
    cue.status = CueStatus.LIVE
    win._update_live_layer_label(cue)
    win.update_live_layer_progress(win._runtime_slot(cue), pos, end_sec=end, start_sec=0.0,
                                   is_looping_inf=False)


def test_clock_fills_only_the_time_cells(window):
    from ui.cue_table import ROLE_LIVE_FRACTION, ROLE_LIVE_TIME, ROLE_LIVE_WARN

    _on_air(window, 1, 15.0, 60.0)
    assert window._live_clock_timer.isActive()
    window._on_live_clock_tick()
    live_cell = window._live_show_panel.live_table.item(1, 4)
    assert live_cell.data(ROLE_LIVE_TIME) == "-0:45"
    assert not live_cell.data(ROLE_LIVE_WARN)
    assert abs(window._cue_list.item(1, 2).data(ROLE_LIVE_FRACTION) - 0.25) < 1e-6
    # the other rows keep their length
    assert window._live_show_panel.live_table.item(0, 4).data(ROLE_LIVE_TIME) == ""


def test_warning_only_when_the_next_go_is_manual(window):
    from models.cue import FollowMode
    from ui.cue_table import ROLE_LIVE_WARN

    _on_air(window, 0, 57.0, 60.0)
    window._on_live_clock_tick()
    assert window._live_show_panel.live_table.item(0, 4).data(ROLE_LIVE_WARN)
    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value
    window._on_live_clock_tick()
    assert not window._live_show_panel.live_table.item(0, 4).data(ROLE_LIVE_WARN)


def test_cue_off_air_clears_and_the_clock_stops(window):
    from models.cue import CueStatus
    from ui.cue_table import ROLE_LIVE_FRACTION, ROLE_LIVE_TIME

    _on_air(window, 1, 15.0, 60.0)
    window._on_live_clock_tick()
    window._cues[1].status = CueStatus.LOADED
    window._on_live_clock_tick()
    assert window._live_show_panel.live_table.item(1, 4).data(ROLE_LIVE_TIME) == ""
    assert window._cue_list.item(1, 2).data(ROLE_LIVE_FRACTION) == -1.0
    assert not window._live_clock_timer.isActive()


def test_live_time_survives_a_list_rebuild(window):
    from ui.cue_table import ROLE_LIVE_TIME

    _on_air(window, 1, 15.0, 60.0)
    window._on_live_clock_tick()
    window._refresh_cue_list()
    assert window._live_show_panel.live_table.item(1, 4).data(ROLE_LIVE_TIME) == "-0:45"


def test_played_cues_are_marked_until_a_run_from_the_top(window):
    from ui.cue_table import ROLE_PLAYED

    window._fire_cue_chain(0)
    window._fire_cue_chain(1)
    assert window._played_ids == {8001, 8002}
    table = window._live_show_panel.live_table
    assert table.item(0, 0).data(ROLE_PLAYED) and not table.item(2, 0).data(ROLE_PLAYED)

    window._on_panic()                                  # nothing plays any more
    window._cue_list.setCurrentRow(0)
    window.set_live_mode(True)                          # a run from the top
    assert window._played_ids == set()
    assert not table.item(0, 0).data(ROLE_PLAYED)
