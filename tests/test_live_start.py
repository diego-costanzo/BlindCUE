"""Entering LIVE asks where the GO starts when it would not continue the show.

GO fires the selected row, so a cue fixed in the editor used to open the
show. The pure choice logic is tested on its own, the question in a headless
MainWindow with ``QMessageBox.exec`` replaced by a click on a chosen button.
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
from engine.show_engine import (
    START_FROM_TOP,
    START_RESUME,
    START_SELECTED,
    live_start_choices,
)
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

# ── Pure choice logic ────────────────────────────────────────────────

def test_fresh_show_from_the_top_asks_nothing():
    assert live_start_choices(5, 0, None) == []


def test_fresh_show_from_a_later_cue_offers_top_first():
    assert live_start_choices(5, 3, None) == [(START_FROM_TOP, 0), (START_SELECTED, 3)]


def test_back_where_live_was_left_asks_nothing():
    assert live_start_choices(5, 2, 2) == []


def test_selection_moved_since_live_offers_resume_first():
    assert live_start_choices(5, 4, 2) == [
        (START_RESUME, 2), (START_SELECTED, 4), (START_FROM_TOP, 0)]


def test_row_zero_is_always_labelled_top():
    assert live_start_choices(5, 3, 0) == [(START_FROM_TOP, 0), (START_SELECTED, 3)]
    assert live_start_choices(5, 0, 3) == [(START_RESUME, 3), (START_FROM_TOP, 0)]


def test_running_show_counts_as_its_own_position():
    assert live_start_choices(5, 3, None, show_running=True) == []


def test_out_of_range_rows_are_safe():
    assert live_start_choices(0, 3, 1) == []
    assert live_start_choices(5, -1, None) == []          # no selection = top
    assert live_start_choices(5, 3, 9) == [(START_FROM_TOP, 0), (START_SELECTED, 3)]


# ── Where a new cue goes ─────────────────────────────────────────────

def _cues(*specs):
    """specs: (cue_id, follow_mode, parent_id, is_group)."""
    from models.cue import Cue, MediaType

    out = []
    for cid, follow, parent, group in specs:
        c = Cue(name=f"c{cid}", media_type=MediaType.GROUP if group else MediaType.AUDIO,
                file_path="" if group else f"/x{cid}.wav", cue_id=cid)
        c.follow_mode = follow
        c.parent_id = parent
        out.append(c)
    return out


def test_insert_after_a_plain_cue_and_at_the_end():
    from engine.show_engine import insert_position

    cues = _cues((1, "MANUAL", None, False), (2, "MANUAL", None, False))
    assert insert_position(cues, 0) == (1, None)
    assert insert_position(cues, -1) == (2, None)


def test_insert_skips_a_simultaneous_and_auto_go_chain():
    from engine.show_engine import insert_position

    cues = _cues((1, "SIMULTANEOUS", None, False), (2, "AUTO_FOLLOW", None, False),
                 (3, "MANUAL", None, False), (4, "MANUAL", None, False))
    assert insert_position(cues, 0) == (3, None)
    assert insert_position(cues, 1) == (3, None)
    assert insert_position(cues, 2) == (3, None)


def test_insert_after_a_group_goes_after_its_children():
    from engine.show_engine import insert_position

    cues = _cues((1, "MANUAL", None, True), (2, "MANUAL", 1, False), (3, "MANUAL", 1, False),
                 (4, "MANUAL", None, False))
    assert insert_position(cues, 0) == (3, None)


def test_insert_after_a_child_stays_in_its_group():
    from engine.show_engine import insert_position

    cues = _cues((1, "MANUAL", None, True), (2, "SIMULTANEOUS", 1, False), (3, "MANUAL", 1, False),
                 (4, "MANUAL", None, False))
    assert insert_position(cues, 2) == (3, 1)
    assert insert_position(cues, 1) == (3, 1)     # after the chain, still inside the group


def test_a_chain_leaving_a_group_is_followed_outside():
    from engine.show_engine import insert_position

    # the last child is tied to the row after its group: inserting there would split them
    cues = _cues((1, "MANUAL", None, True), (2, "MANUAL", 1, False), (3, "AUTO_FOLLOW", 1, False),
                 (4, "MANUAL", None, False), (5, "MANUAL", None, False))
    assert insert_position(cues, 2) == (4, None)
    assert insert_position(cues, 1) == (2, 1)       # an untied child: right after it, in the group


def test_a_chain_of_groups_is_skipped_whole():
    from engine.show_engine import insert_position

    cues = _cues((1, "SIMULTANEOUS", None, True), (2, "MANUAL", 1, False),
                 (3, "MANUAL", None, True), (4, "MANUAL", 3, False), (5, "MANUAL", None, False))
    assert insert_position(cues, 0) == (4, None)


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
        Cue.from_dict({"cue_id": 7001 + i, "name": f"c{i}",
                       "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(5)
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


@pytest.fixture()
def answer(monkeypatch):
    """Replace the modal question: click the button whose text starts with ``answer.pick``."""

    class _Answer:
        def __init__(self) -> None:
            self.pick: str | None = None
            self.asked: list[list[str]] = []

    state = _Answer()

    def fake_exec(box: QMessageBox) -> int:
        texts = [b.text() for b in box.buttons()]
        state.asked.append(texts)
        for b in box.buttons():
            if state.pick is not None and b.text().startswith(state.pick):
                b.click()
                break
        else:
            box.button(QMessageBox.StandardButton.Cancel).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return state


def test_fixed_cue_does_not_open_the_show(window, answer):
    window._cue_list.setCurrentRow(3)
    answer.pick = "Dall'inizio"
    window.set_live_mode(True)
    assert window.is_live_mode()
    assert len(answer.asked) == 1
    assert window._go_target_index() == 0


def test_starting_from_the_selected_cue_keeps_it(window, answer):
    window._cue_list.setCurrentRow(3)
    answer.pick = "Dalla cue selezionata"
    window.set_live_mode(True)
    assert window.is_live_mode()
    assert window._go_target_index() == 3


def test_cancel_stays_in_design_mode(window, answer):
    window._cue_list.setCurrentRow(3)
    answer.pick = None
    window.set_live_mode(True)
    assert not window.is_live_mode()
    assert not window._act_live_mode.isChecked()
    assert window._go_target_index() == 3


def test_top_of_list_asks_nothing(window, answer):
    window._cue_list.setCurrentRow(0)
    window.set_live_mode(True)
    assert window.is_live_mode()
    assert answer.asked == []


def test_round_trip_without_changes_asks_nothing(window, answer):
    window._cue_list.setCurrentRow(0)
    window.set_live_mode(True)
    window._cue_list.setCurrentRow(2)       # the show moved on in LIVE
    window.set_live_mode(False)
    window.set_live_mode(True)
    assert window.is_live_mode()
    assert answer.asked == []
    assert window._go_target_index() == 2


def test_selection_moved_in_design_offers_resume(window, answer):
    window._cue_list.setCurrentRow(0)
    window.set_live_mode(True)
    window._cue_list.setCurrentRow(2)
    window.set_live_mode(False)
    window._cue_list.setCurrentRow(4)       # a cue fixed in the editor
    answer.pick = "Riprendi da"
    window.set_live_mode(True)
    assert window.is_live_mode()
    assert answer.asked[0][:3] == ["Riprendi da: #3 'c2'",
                                   "Dalla cue selezionata: #5 'c4'",
                                   "Dall'inizio: #1 'c0'"]
    assert window._go_target_index() == 2


def test_new_show_forgets_where_live_was_left(window):
    window._live_resume_id = 7003
    window._released_groups.add(7001)
    window._is_modified = False
    window._on_new_show()
    assert window._live_resume_id is None
    assert window._released_groups == set()


def test_resume_follows_the_show_while_the_editor_is_open(window, answer):
    window._cue_list.setCurrentRow(0)
    window.set_live_mode(True)
    window._cue_list.setCurrentRow(1)
    window.set_live_mode(False)                    # LIVE left at #2
    window._fire_cue_chain(1)                      # the show goes on (e.g. an Auto-GO)
    assert window._go_target_index() == 2
    window.set_live_mode(True)                     # back at the show's own position: no question
    assert answer.asked == [] and window._go_target_index() == 2


def test_new_cue_goes_after_the_selected_one(window, tmp_path):
    from models.cue import Cue, FollowMode, MediaType

    new_file, late_file = tmp_path / "n.wav", tmp_path / "l.wav"
    new_file.write_bytes(b"x")       # validate() wants the file to exist
    late_file.write_bytes(b"x")
    window._cue_list.setCurrentRow(1)
    window._append_new_cue(Cue(name="new", media_type=MediaType.AUDIO, file_path=str(new_file)))
    assert [c.name for c in window._cues][:4] == ["c0", "c1", "new", "c2"]
    assert window._selected_cue().name == "new"
    assert window._inspector.edit_cue_name.text() == "new"   # the inspector follows

    window._cues[3].follow_mode = FollowMode.SIMULTANEOUS.value   # c2 pulls c3 into its GO
    window._cue_list.setCurrentRow(3)
    window._append_new_cue(Cue(name="late", media_type=MediaType.AUDIO, file_path=str(late_file)))
    assert [c.name for c in window._cues][3:6] == ["c2", "c3", "late"]
    assert "fine della catena" in window._status_label.text()


def test_files_dropped_on_the_list(window, tmp_path):
    """Files from the file manager dropped on a row go after it, in order (1.12)."""
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    files = []
    for name in ("d1.wav", "d2.wav"):
        p = tmp_path / name
        p.write_bytes(b"x")
        files.append(p)
    table = window._cue_list
    table.resize(400, 400)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(f)) for f in files])
    y = table.visualRect(table.model().index(1, 2)).center().y()
    event = QDropEvent(QPointF(20, y), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    table.dropEvent(event)
    assert [c.name for c in window._cues][:5] == ["c0", "c1", "d1.wav", "d2.wav", "c2"]

    window._on_files_dropped_on_list([str(files[0])], -1)   # below the last row: at the end
    assert window._cues[-1].name == "d1.wav" and len(window._cues) == 8


def test_go_button_names_its_cue(window):
    from models.cue import CueStatus

    window._cue_list.setCurrentRow(3)
    for c in window._cues:      # the fixture's files do not exist: selecting marks them OFFLINE
        c.status = CueStatus.LOADED
    window._refresh_cue_list()
    live_go = window._live_show_panel.btn_go
    assert window._btn_go.full_text() == "▶ GO: #4 'c3'"
    assert live_go.full_text() == "▶ GO: #4 'c3'" and not window._live_show_panel._go_warn

    window._cues[3].status = CueStatus.OFFLINE          # the file is gone
    window._refresh_cue_list()
    assert window._btn_go.full_text() == "⚠ GO: #4 'c3' — file mancante"
    assert window._live_show_panel._go_warn            # amber, never red

    window._cues[3].status = CueStatus.LIVE             # GO would restart it
    window._refresh_cue_list()
    assert window._btn_go.full_text().startswith("↻ GO: #4 'c3'")

    window._cues[3].status = CueStatus.LOADED
    window._cues[0].exclusive = True                    # an exclusive cue holds the GO
    window._cues[0].status = CueStatus.LIVE
    window._refresh_cue_list()
    assert window._btn_go.full_text().startswith("⏳ GO in attesa: 'c0'")

    window._cues[0].status = CueStatus.LOADED
    window._focus_lost_shown = True                     # keyboard in another window
    window._update_go_button_text()
    assert window._btn_go.full_text().startswith("⌨ GO: #4 'c3'")
    window._focus_lost_shown = False

    window._cues = []
    window._refresh_cue_list(keep_selection=False)
    assert window._btn_go.full_text() == "GO (Next Cue) — [ SPAZIO ]"
