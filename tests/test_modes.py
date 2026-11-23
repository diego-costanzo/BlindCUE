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


def test_pause_all_has_a_key(window):
    from PySide6.QtGui import QKeySequence

    acts = [a for a in window.findChildren(type(window._act_end_show))
            if a.shortcut() == QKeySequence("Ctrl+P")]
    assert len(acts) == 1
    toggles: list[int] = []
    window.pause_all_toggled.connect(lambda: toggles.append(1))
    acts[0].trigger()
    assert toggles == [1]
