"""Stage 2, item 2.1: cues that start by themselves relative to another cue."""

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
from engine.show_engine import ShowEngine, chain_indices, outside_go_order, relative_cycle
from models.cue import Cue, CueStatus, MediaType
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
    data = {"cue_id": 9501 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_model_and_engine():
    a = _cue(0)
    b = _cue(1, start_rel_cue=9501, start_rel_when="before_end", start_rel_offset=2)
    back = Cue.from_dict(b.to_dict())
    assert (back.start_rel_cue, back.start_rel_when, back.start_rel_offset) == (9501, "before_end", 2.0)
    assert Cue.from_dict({**b.to_dict(), "start_rel_when": "sometime"}).start_rel_when == "start"
    assert outside_go_order(b) and not outside_go_order(a)
    c = _cue(2)
    cues = [Cue.from_dict({**a.to_dict(), "follow_mode": "SIMULTANEOUS"}), b, c]
    assert chain_indices(cues, 0) == [0, 2]                       # "together" skips the relative cue
    assert ShowEngine.auto_follow_target([a, b, c], a) == 2
    assert relative_cycle([a, b], 9501, 9502)                      # a after b, b after a: a loop
    assert not relative_cycle([a, b, c], 9503, 9501)


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        _cue(0, name="music"),
        _cue(1, name="title", media_type="IMAGE", start_rel_cue=9501, start_rel_when="start", start_rel_offset=2),
        _cue(2, name="bell", start_rel_cue=9501, start_rel_when="before_end", start_rel_offset=1),
        _cue(3, name="applause", start_rel_cue=9501, start_rel_when="end", start_rel_offset=0.5),
        _cue(4, name="next"),
    ]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[tuple[int, float]] = []
    win.cue_fired.connect(lambda c: fired.append((c.cue_id, win.take_rel_extra(c.cue_id))))
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


def test_go_skips_relative_cues_and_they_start_on_their_moment(window):
    window._on_go()
    assert window.fired == [(9501, 0.0)] and window._cue_list.currentRow() == 4
    window.cue_launched(window._cues[0], 10.0)              # main.py: it really started, 10 s to go
    assert window.fired[1:] == [(9502, 2.0), (9503, 9.0)]
    assert window._cue_list.currentRow() == 4               # the GO pointer did not move
    window.cue_ended(window._cues[0])
    assert window.fired[3:] == [(9504, 0.5)]


def test_unknown_length_waits_for_it_or_for_the_end(window):
    window.cue_launched(window._cues[0], None)
    assert [cid for cid, _x in window.fired] == [9502]       # "before the end" waits for the length
    window.cue_duration_known(window._cues[0], 6.0)
    assert window.fired[-1] == (9503, 5.0)
    window.fired.clear()
    window.cue_launched(window._cues[0], None)
    window.cue_ended(window._cues[0])                         # never known: it starts at the end
    assert (9503, 0.0) in window.fired and (9504, 0.5) in window.fired


def test_stopped_by_hand_cancels_before_end_and_panic_resets(window):
    cancelled: list[int] = []
    window.layer_cancel_start_requested.connect(cancelled.append)
    music = window._cues[0]
    music.status = CueStatus.LIVE
    window.cue_launched(music, 10.0)
    window._live_phase_tags[9503] = "PRE -9.0s"               # the bell waits in its Pre-Delay
    window.mark_layer_stopped(window._runtime_slot(music))
    assert cancelled == [window._runtime_slot(window._cues[2])] and window._rel_before_end == {}
    window.cue_launched(music, None)
    window._on_panic()
    assert window._rel_until_known == {} and window._rel_extra == {}


def test_a_loop_is_refused_in_the_inspector_and_cut_off_at_run_time(window):
    insp = window._inspector
    window._cue_list.setCurrentRow(0)                         # music
    _pump()
    insp.combo_rel_when.setCurrentIndex(insp.combo_rel_when.findData("start"))
    insp.combo_rel_cue.setCurrentIndex(insp.combo_rel_cue.findData(9502))   # after "title", which follows music
    insp._apply_start_rel(window._cues[0])
    assert window._cues[0].start_rel_cue is None and insp.lbl_rel_hint.isVisibleTo(insp)
    window.fired.clear()
    for _ in range(25):
        window._rel_fire(4, window._cues[4], 0.0)
    assert len(window.fired) == 20                            # more than 20 a second: a loop, stopped


def test_show_list_mark(qt_app):
    from ui.live_show_view import relative_mark

    rows = {9501: 0}
    assert relative_mark(_cue(1, start_rel_cue=9501, start_rel_offset=2), rows) == "⏱ #1+2s"
    assert relative_mark(_cue(1, start_rel_cue=9501, start_rel_when="end"), rows) == "⏱ #1 ▸+0s"
    assert relative_mark(_cue(1, start_rel_cue=9501, start_rel_when="before_end", start_rel_offset=1.5),
                         rows) == "⏱ #1 −1.5s"
    assert relative_mark(_cue(1, start_rel_cue=4242), rows) == "⏱ ?" and relative_mark(_cue(1), rows) == ""


def test_review_lost_reference_and_group_items(window):
    from engine.show_engine import ShowEngine

    window._cues = [c for c in window._cues if c.cue_id != 9501]   # the music is deleted
    window._refresh_cue_list(keep_selection=False)
    assert all(c.start_rel_cue is None for c in window._cues)      # they wait for GO again
    assert "#" in window._status_label.text()
    group = _cue(9, media_type="GROUP", file_path="")
    items = [_cue(10, parent_id=9510), _cue(11, parent_id=9510, start_rel_cue=9511), _cue(12, parent_id=9510,
                                                                                          call_only=True)]
    assert [c.cue_id for c in ShowEngine.children_of([group, *items], 9510)] == [9511]
