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
    window._is_modified = False
    window._on_new_show()
    assert window._live_resume_id is None


def test_go_button_names_its_cue(window):
    window._cue_list.setCurrentRow(3)
    assert window._btn_go.full_text() == "GO ▶ #4  c3"
    window._cues = []
    window._refresh_cue_list(keep_selection=False)
    assert window._btn_go.full_text() == "GO (Next Cue) — [ SPAZIO ]"
