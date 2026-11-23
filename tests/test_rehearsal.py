"""Rehearsal: the show's screen with small fixes (stage 1 C2a step 9)."""

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
from engine.show_mode import PREPARATION, REHEARSAL, SHOW
from models.cue import Cue, CueStatus, MediaType
from PySide6.QtCore import QCoreApplication, QSettings
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
    win._cues = [Cue.from_dict({"cue_id": 9301 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
                                "file_path": f"/nonexistent/c{i}.wav", "volume": 0.8}) for i in range(3)]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    try:
        yield win
    finally:
        QSettings("BlindCue", "BlindCue").setValue("live/readiness_check", False)
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_preparation_rehearsal_show_and_back(window):
    window._enter_rehearsal()                                # Shift+F5
    assert window.is_live_mode() and window._current_mode() == REHEARSAL
    assert window._live_show_panel.mode_tabs.mode() == REHEARSAL
    assert window._live_show_panel.btn_edit_next.isVisibleTo(window._live_show_panel)
    window._enter_show_from_key()                            # F5 in the rehearsal: into the show
    assert window._current_mode() == SHOW
    assert not window._live_show_panel.btn_edit_next.isVisibleTo(window._live_show_panel)
    window._live_show_panel.mode_tabs.tab_reh_hold.hold_completed.emit()   # held 1.5 s
    assert window._current_mode() == REHEARSAL
    window._live_show_panel.mode_tabs.tab_prep.click()      # one click back to Preparation
    assert window._current_mode() == PREPARATION and not window.is_live_mode()


def test_rehearsal_to_show_goes_through_the_readiness_page(window):
    QSettings("BlindCue", "BlindCue").setValue("live/readiness_check", True)
    window._enter_rehearsal()                                # no readiness page for the rehearsal
    assert window._current_mode() == REHEARSAL and not window._readiness_visible()
    window._enter_show_from_key()
    assert window._readiness_visible() and window._design_control_bar.isVisibleTo(window)
    window._readiness_page.start_buttons[0].click()
    assert window._current_mode() == SHOW and window._central_stack.currentIndex() == 1
    assert not window._design_control_bar.isVisibleTo(window)


def test_drawer_fixes_one_cue_and_lists_the_change(window):
    window._enter_rehearsal()
    window._live_show_panel.btn_edit_next.click()           # ✎ on the NEXT bar
    drawer = window._live_show_panel.now_playing.drawer
    assert drawer.isVisibleTo(window._live_show_panel) and "#1" in drawer.lbl_title.text()
    assert not window._live_show_panel.now_playing.lbl_preview.isVisibleTo(window._live_show_panel)
    drawer.sl_volume.setValue(65)
    drawer.ed_notes.setText("CZEKAJ")
    drawer.ed_notes.editingFinished.emit()
    cue = window._cues[0]
    assert cue.volume == 0.65 and cue.notes == "CZEKAJ" and window._is_modified
    changes = window._rehearsal_changes()
    assert [(c.cue_id, f, b) for c, f, b, _ in changes] == [(9301, "volume", 0.8), (9301, "notes", "")]
    window._undo_rehearsal_change(cue, "volume", 0.8)        # "Undo" in the review list
    assert cue.volume == 0.8 and len(window._rehearsal_changes()) == 1
    drawer.btn_close.click()
    assert not drawer.isVisibleTo(window._live_show_panel)


def test_the_list_does_not_change_in_the_rehearsal(window):
    window._enter_rehearsal()
    n = len(window._cues)
    window._on_add_action_cue("note")
    assert len(window._cues) == n and "Preparazione" in window._status_label.text()


def test_then_changes_only_while_the_cue_does_not_play(window):
    window._enter_rehearsal()
    cue = window._cues[0]
    cue.status = CueStatus.LIVE
    assert not window._set_cue_field(cue, "follow_mode", "AUTO_FOLLOW")
    cue.status = CueStatus.LOADED
    assert window._set_cue_field(cue, "follow_mode", "AUTO_FOLLOW")


def test_save_level_keeps_what_is_heard(window):
    window._enter_rehearsal()
    cue = window._cues[0]
    cue.status = CueStatus.LIVE
    slot = window._runtime_slot(cue)
    window._trims[slot] = 0.5
    trims: list = []
    window.layer_trim_requested.connect(lambda layer, t: trims.append((layer, t)))
    window._on_card_save_level(cue.cue_id)
    assert cue.volume == 0.4 and window._trims[slot] == 1.0 and trims == [(slot, 1.0)]
