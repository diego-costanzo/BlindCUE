"""Mode tabs: entering the show is one action, leaving it never is (stage 1 C2a step 1)."""

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
from PySide6.QtWidgets import QApplication, QMessageBox


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
        Cue.from_dict({"cue_id": 5001 + i, "name": f"c{i}",
                       "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(3)
    ]
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


def test_f5_only_enters(window):
    window._act_live_mode.trigger()                 # F5
    assert window.is_live_mode()
    window._act_live_mode.trigger()                 # F5 again: stays, says how to leave
    assert window.is_live_mode() and window._act_live_mode.isChecked()
    assert "1,5 s" in window._status_label.text()


def test_ctrl_l_only_enters(window):
    window._enter_show_from_key()
    assert window.is_live_mode()
    window._enter_show_from_key()
    assert window.is_live_mode()


def test_tabs_follow_the_mode_and_the_hold_leaves(window):
    assert window._design_control_bar.isVisibleTo(window)
    assert not window._mode_tabs.is_live()
    window._mode_tabs.tab_show.click()              # one click enters
    assert window.is_live_mode()
    assert not window._design_control_bar.isVisibleTo(window)
    tabs = window._live_show_panel.mode_tabs
    assert tabs.is_live() and tabs.tab_prep_hold.isVisibleTo(tabs)
    tabs.tab_show.click()                           # clicking the active tab does nothing
    assert window.is_live_mode()
    tabs.tab_prep_hold.hold_completed.emit()        # the 1.5 s hold
    assert not window.is_live_mode()


def test_end_show_menu_stays_by_default(window, monkeypatch):
    window.set_live_mode(True)
    assert window._act_end_show.isEnabled()

    def press_esc(box):
        box.escapeButton().click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", press_esc)
    window._act_end_show.trigger()
    assert window.is_live_mode()                    # Esc / default = stay

    def leave(box):
        next(b for b in box.buttons() if b is not box.escapeButton()).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", leave)
    window._act_end_show.trigger()
    assert not window.is_live_mode()
    assert not window._act_end_show.isEnabled()


def _fingerprint(win) -> str:
    """The show document without runtime state (status, group folding)."""
    import json

    docs = []
    for c in win._cues:
        d = c.to_dict()
        d.pop("status", None)
        d.pop("collapsed", None)
        docs.append(d)
    return json.dumps(docs, sort_keys=True, default=str)


def test_in_the_show_nothing_changes_the_document(window, tmp_path):
    from models.cue import Cue, MediaType

    media = tmp_path / "x.wav"
    media.write_bytes(b"x")
    window._cue_list.setCurrentRow(0)               # the top: no start question
    window._inspector.slider_volume.setValue(13)    # an edit left in the hidden inspector
    window.set_live_mode(True)
    before = _fingerprint(window)

    window._on_go()                                  # GO, autosave, save use to apply the inspector
    window._auto_save()
    window._on_remote_volume_change(0.2)            # phone remote level
    window._on_delete_cue()
    window._on_move_up()
    window._on_undo()
    window._on_add_group()
    window._append_new_cue(Cue(name="new", media_type=MediaType.AUDIO, file_path=str(media)))
    window._on_files_dropped_on_list([str(media)], 0)
    assert _fingerprint(window) == before
    assert "preparazione" in window._status_label.text()   # said why, not ignored in silence


def test_in_preparation_the_same_edits_work(window, tmp_path):
    from models.cue import Cue, MediaType

    media = tmp_path / "x.wav"
    media.write_bytes(b"x")
    window._reset_undo_history()                    # the fixture's list is the starting point
    before = _fingerprint(window)
    window._append_new_cue(Cue(name="new", media_type=MediaType.AUDIO, file_path=str(media)))
    assert _fingerprint(window) != before
    window._on_undo()
    assert _fingerprint(window) == before
    window._on_remote_volume_change(0.4)            # in the editor the remote level edits the cue
    assert abs(window._selected_cue().volume - 0.4) < 1e-6


def test_master_volume_and_mute(window):
    gains: list[float] = []
    window.master_gain_changed.connect(gains.append)
    window._nudge_master(-0.05)                     # Ctrl+Down
    assert abs(gains[-1] - 0.95) < 1e-9
    live_copy = window._live_show_panel.master_volume
    assert live_copy.slider.value() == 95 and window._master_volume.slider.value() == 95
    window._toggle_master_mute()                    # Ctrl+M
    assert gains[-1] == 0.0 and live_copy.btn_mute.isChecked()
    window._live_show_panel.master_volume.slider.setValue(50)   # the LIVE copy drives it too
    assert window._master_volume.slider.value() == 50 and gains[-1] == 0.0   # still muted
    window._toggle_master_mute()
    assert abs(gains[-1] - 0.5) < 1e-9
    window._nudge_master(+1.0)
    assert gains[-1] == 1.0                         # clamped


def test_player_master_gain_multiplies_the_level(qt_app):
    from engine.player_live import LivePlayer

    lp = LivePlayer()
    lp.set_volume(80)
    _, audio = lp._deck_pair()
    assert abs(audio.volume() - 0.8) < 1e-3
    lp.set_master_gain(0.5)
    lp.set_volume(80)
    assert abs(audio.volume() - 0.4) < 1e-3          # 0.8 × 0.5
    lp.stop()
    lp.deleteLater()


def test_pause_all_has_a_key(window):
    from PySide6.QtGui import QKeySequence

    acts = [a for a in window.findChildren(type(window._act_end_show))
            if a.shortcut() == QKeySequence("Ctrl+P")]
    assert len(acts) == 1
    toggles: list[int] = []
    window.pause_all_toggled.connect(lambda: toggles.append(1))
    acts[0].trigger()
    assert toggles == [1]
