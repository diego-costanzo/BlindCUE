"""Undo the last GO (stage 1.18, C2a step 6).

The plan is pure logic; the window part runs a headless MainWindow and
checks what it asks main.py to do (``undo_go_requested``), the GO pointer,
the ✓ marks and when the offer ends.
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
from engine.undo_go import (
    CANCEL,
    CONTAINER,
    ENDED,
    FADE,
    KEEP,
    LIFT,
    RESTORE,
    UNDO_WINDOW_SECONDS,
    UndoRecord,
    can_undo,
    undo_plan,
)
from models.cue import Cue, CueStatus, FollowMode, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _cue(cid: int, kind: MediaType, status: CueStatus = CueStatus.LIVE, **extra) -> Cue:
    cue = Cue.from_dict({"cue_id": cid, "name": f"c{cid}", "media_type": kind.value,
                         "file_path": f"/nonexistent/{cid}", **extra})
    cue.status = status
    return cue


# ── Pure plan ────────────────────────────────────────────────────────


def test_sound_on_air_fades_and_an_ended_one_only_moves_the_pointer():
    cues = [_cue(1, MediaType.AUDIO), _cue(2, MediaType.VIDEO, CueStatus.LOADED)]
    rec = UndoRecord(first_id=1, started=0.0, ids=[1, 2])
    steps = undo_plan(cues, rec, waiting=set())
    assert [(s.cue_id, s.how) for s in steps] == [(1, FADE), (2, ENDED)]
    assert steps[0].seconds == 1.0


def test_picture_comes_back_or_is_taken_off():
    cues = [_cue(1, MediaType.IMAGE), _cue(2, MediaType.IMAGE), _cue(3, MediaType.IMAGE),
            _cue(4, MediaType.VIDEO)]
    rec = UndoRecord(first_id=2, started=0.0, ids=[2, 3], replaced={2: 1, 3: 4})
    steps = undo_plan(cues, rec, waiting=set())
    assert steps[0].how == RESTORE and steps[0].restore_id == 1 and steps[0].seconds == 0.5
    # A picture over a video: taken off, the video it cut off does not come back yet.
    assert steps[1].how == LIFT and steps[1].cut_id == 4


def test_waiting_start_is_cancelled_and_actions_stay():
    cues = [_cue(1, MediaType.AUDIO, CueStatus.LOADED), _cue(2, MediaType.ACTION),
            _cue(3, MediaType.GROUP)]
    rec = UndoRecord(first_id=3, started=0.0, ids=[3, 1, 2])
    steps = undo_plan(cues, rec, waiting={1})
    assert [s.how for s in steps] == [CONTAINER, CANCEL, KEEP]
    assert can_undo(steps)
    assert not can_undo([s for s in steps if s.how == KEEP])


def test_replaced_by_its_own_go_is_not_brought_back():
    cues = [_cue(1, MediaType.IMAGE), _cue(2, MediaType.IMAGE)]
    rec = UndoRecord(first_id=1, started=0.0, ids=[1, 2], replaced={2: 1})
    assert undo_plan(cues, rec, waiting=set())[1].how == LIFT


def test_pause_all_stops_the_countdown():
    rec = UndoRecord(first_id=1, started=100.0)
    rec.set_paused(True, 105.0)
    assert rec.seconds_left(200.0) == UNDO_WINDOW_SECONDS - 5.0
    rec.set_paused(False, 200.0)
    assert rec.seconds_left(203.0) == UNDO_WINDOW_SECONDS - 8.0


# ── Window ───────────────────────────────────────────────────────────


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
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        Cue.from_dict({"cue_id": 8001 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(4)
    ]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    asked: list = []
    win.undo_go_requested.connect(asked.append)
    win._undo_asked = asked
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


def test_go_offers_undo_and_one_click_takes_it_back(window):
    window._cues[1].follow_mode = FollowMode.SIMULTANEOUS.value  # #2 starts #3 with it
    window._fire_cue_chain(1)
    assert window._undo_go.ids == [8002, 8003]
    window._refresh_undo_go()
    panel = window._live_show_panel
    assert panel.btn_undo_go.isVisibleTo(panel) and "#2" in panel.btn_undo_go.text()
    assert window._act_undo_go.isEnabled()
    assert "#2" in panel.btn_undo_go.toolTip()          # says what it will do
    window._on_undo_go()
    steps = window._undo_asked[0]
    assert [s.cue_id for s in steps] == [8002, 8003]
    assert window._go_target_index() == 1                # back on the GO's first cue
    assert not ({8002, 8003} & window._played_ids)       # no ✓ for what was undone
    assert all(c.status != CueStatus.LIVE for c in window._cues)
    assert window._undo_go is None and not panel.btn_undo_go.isVisibleTo(panel)
    assert not window._act_undo_go.isEnabled()


def test_an_auto_go_of_that_go_is_undone_too_but_not_others(window):
    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value
    window._fire_cue_chain(0)                            # GO by hand on #1
    window.trigger_auto_follow_from(window._cues[0])     # #1 ends, #2 starts by itself
    assert window._undo_go.ids == [8001, 8002]
    window._cues[3].follow_mode = FollowMode.AUTO_FOLLOW.value
    window._undo_auto_source = None
    window._fire_cue_chain(3, auto=True)                 # an unrelated Auto-GO
    assert 8004 not in window._undo_go.ids


def test_offer_ends_after_15_s_and_on_panic_and_new_go(window):
    window._fire_cue_chain(0)
    window._undo_go.started -= UNDO_WINDOW_SECONDS + 1
    window._refresh_undo_go()
    assert window._undo_go is None
    window._fire_cue_chain(1)
    first = window._undo_go
    window._fire_cue_chain(2)                            # the next GO by hand replaces it
    assert window._undo_go is not first and window._undo_go.first_id == 8003
    window._on_panic()
    assert window._undo_go is None


def test_pause_all_holds_the_offer(window):
    window._fire_cue_chain(0)
    window.set_global_paused(True, silent=True)
    window._undo_go.started -= 20                        # paused right after the GO,
    window._undo_go.paused_since -= 20                   # 20 s ago
    window._refresh_undo_go()
    assert window._undo_go is not None
    window.set_global_paused(False, silent=True)


def test_action_only_go_cannot_be_undone(window):
    window._cues[0] = Cue.from_dict({"cue_id": 8001, "name": "note", "media_type": MediaType.ACTION.value,
                                     "file_path": "",
                                     "action_spec": {"kind": "note", "text": "x"}})
    window._refresh_cue_list(keep_selection=False)
    window._fire_cue_chain(0)
    window._refresh_undo_go()
    assert "(" in window._live_show_panel.btn_undo_go.toolTip()
    window._on_undo_go()
    assert window._undo_asked == [] and window._undo_go is not None


def test_replaced_picture_is_recorded(window):
    window._fire_cue_chain(0)
    window.note_replaced(window._cues[0], window._cues[3])
    window.note_replaced(window._cues[2], window._cues[3])   # not from this GO: ignored
    assert window._undo_go.replaced == {8001: 8004}
