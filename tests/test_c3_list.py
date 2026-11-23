"""The show's list (stage 1 C3, 1.13): helper cues folded, next cue centred, Ctrl+arrows for pictures."""

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
from models.cue import Cue, CueStatus, FollowMode, MediaType
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


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    kinds = [MediaType.AUDIO, MediaType.AUDIO, MediaType.AUDIO, MediaType.IMAGE, MediaType.IMAGE, MediaType.IMAGE]
    win._cues = [Cue.from_dict({"cue_id": 9401 + i, "name": f"c{i}", "media_type": kinds[i].value,
                                "file_path": f"/nonexistent/c{i}"}) for i in range(6)]
    win._cues[0].follow_mode = FollowMode.SIMULTANEOUS.value   # #1 starts #2 with it
    win._cues[1].follow_mode = FollowMode.AUTO_FOLLOW.value    # #2 hands over to #3
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
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


def test_helper_cues_fold_under_their_head(window):
    window.set_live_mode(True)
    table = window._live_show_panel.live_table
    assert not table.isRowHidden(0) and table.isRowHidden(1) and table.isRowHidden(2)
    assert table.item(0, 2).text().endswith("⤵+2")
    window._live_show_panel._on_table_clicked(0, 0)          # click on its number
    assert not table.isRowHidden(1) and not table.isRowHidden(2)
    assert table.item(0, 2).text() == "c0"


def test_next_cue_stays_visible_even_inside_a_chain(window):
    window.set_live_mode(True)
    window._cue_list.setCurrentRow(2)                        # the operator set a helper as next
    window._sync_live_view()
    assert not window._live_show_panel.live_table.isRowHidden(2)


def test_ctrl_arrows_step_through_pictures(window):
    window.set_live_mode(True)
    window._go_picture(1)                                    # nothing on screen yet: the first picture
    assert window._cues[3].cue_id in window._played_ids
    window._cues[3].status = CueStatus.LIVE
    window._last_go_at = None                                # past the double-GO guard
    window._go_picture(1)
    assert window._cues[4].cue_id in window._played_ids
    window._cues[3].status = CueStatus.LOADED
    window._cues[4].status = CueStatus.LIVE
    window._last_go_at = None
    window._go_picture(-1)
    assert window._go_target_index() in (4, 5) and window._fired_at[window._cues[3].cue_id] > 0


def test_gate_waits_for_the_ok_and_lapses_when_another_cue_starts(window):
    window.set_live_mode(True)
    gated = window._cues[3]
    gated.confirm_start = True
    window._cue_list.setCurrentRow(3)
    window._on_go()                                          # arms, does not start
    assert gated.cue_id not in window._played_ids and window._gate_waiting() == gated.cue_id
    panel = window._live_show_panel
    assert panel.btn_gate_ok.isVisibleTo(panel) and "OK" in panel.lbl_standby_banner.text()
    window._last_go_at = None
    window._on_go()                                          # GO again is not the OK
    assert gated.cue_id not in window._played_ids
    panel.btn_gate_ok.click()                                # the OK
    assert gated.cue_id in window._played_ids and window._gate_waiting() < 0
    window._confirm_gate()                                   # an extra OK is refused with a word
    assert "OK" in window._status_label.text()
    gated.status = CueStatus.LOADED
    window._played_ids.discard(gated.cue_id)
    window._cue_list.setCurrentRow(3)
    window._last_go_at = None
    window._on_go()                                          # armed again …
    window._fire_cue_chain(5)                                # … another cue starts: the wait lapses
    assert window._gate_waiting() < 0 and gated.cue_id not in window._played_ids


def test_gate_is_saved_with_the_show():
    cue = Cue.from_dict({"cue_id": 1, "name": "x", "media_type": MediaType.AUDIO.value,
                         "file_path": "a.wav", "confirm_start": True})
    assert Cue.from_dict(cue.to_dict()).confirm_start
