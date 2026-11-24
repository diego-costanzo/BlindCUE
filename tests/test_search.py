"""Stage 2, item 2.8: find a cue (Ctrl+F)."""

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
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
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
    data = {"cue_id": 9991 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/media/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_matches():
    from ui.main_window._search import cue_matches

    cue = _cue(0, name="Overture", q_label="Q-12", notes="after the bow", file_path="/m/ALICE_theme.mp3")
    for text in ("overture", "q-12", "BOW", "alice", ""):
        assert cue_matches(cue, text)
    assert not cue_matches(cue, "finale")


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [_cue(0, name="Intro"), _cue(1, name="Rain", notes="thunder"), _cue(2, name="Finale"),
                 _cue(3, name="Applause")]
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


def test_filter_enter_and_escape(window):
    window._search_open()
    edit = window._search_edit
    assert edit.isVisibleTo(window._cue_list_panel)
    edit.setText("thun")
    hidden = [window._cue_list.isRowHidden(r) for r in range(4)]
    assert hidden == [True, False, True, True] and "1" in window._status_label.text()
    edit.returnPressed.emit()
    assert window._cue_list.currentRow() == 1
    QApplication.sendEvent(edit, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert not edit.isVisibleTo(window._cue_list_panel)
    assert not any(window._cue_list.isRowHidden(r) for r in range(4))


def test_in_the_show_only_the_pointer_moves(window, monkeypatch):
    window.set_live_mode(True)
    monkeypatch.setattr(window, "_search_ask", lambda: "fin")
    window._search_open()
    assert window._cue_list.currentRow() == 2 and not window._search_edit.isVisible()
    monkeypatch.setattr(window, "_search_ask", lambda: "nothing")
    window._search_open()
    assert window._cue_list.currentRow() == 2


def test_review_filter_survives_refresh_and_drops_hidden_selection(window):
    window._search_open()
    window._cue_list.select_rows([0, 1], anchor_row=0)
    window._search_edit.setText("rain")
    assert window._selected_rows() == [1]                       # "Intro" is hidden: no longer selected
    window._refresh_cue_list(keep_selection=True)               # e.g. an Undo while the search is open
    assert [window._cue_list.isRowHidden(r) for r in range(4)] == [True, False, True, True]


def test_review_jump_never_lands_on_a_timed_cue(window, monkeypatch):
    window._cues[2].start_clock = "19:55"                       # "Finale" starts by itself
    window.set_live_mode(True)
    monkeypatch.setattr(window, "_search_ask", lambda: "fin")
    window._search_open()
    assert window._cue_list.currentRow() == 0                   # not found among GO cues: pointer stays
