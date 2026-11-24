"""Emergency keys and reflex keystrokes never lose a show (stage 1 C2a, step 0).

- Esc in the crash-recovery question restores, "No" sets the autosave aside;
- closing the window during a show asks first, "stay" is the default;
- the Next banner translates each of its pieces.
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
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QCloseEvent
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
        Cue.from_dict({"cue_id": 6001 + i, "name": f"c{i}",
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


def test_recovery_esc_restores_and_no_keeps_a_copy(window, tmp_path, monkeypatch):
    from models.project_manager import ProjectManager

    pm = ProjectManager(autosave_dir=tmp_path)
    window._cues = []
    window._project_manager = pm
    pm.autosave(window._cues, -1)
    payload = {"saved_at": "now", "cues": [], "cues_count": 0}
    monkeypatch.setattr(ProjectManager, "check_crash_recovery", lambda self: payload)

    def press_esc(box):
        box.escapeButton().click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", press_esc)
    window._check_crash_recovery()
    assert pm.autosave_file.exists()                       # Esc restored: nothing set aside

    def answer_no(box):
        box.button(QMessageBox.StandardButton.No).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", answer_no)
    window._cues = []
    window._check_crash_recovery()
    assert not pm.autosave_file.exists()
    assert (tmp_path / "autosave.discarded.json").exists()  # set aside, never deleted


def test_closing_during_a_show_asks_and_stays_by_default(window, monkeypatch):
    asked: list[str] = []

    def press_esc(box):
        asked.append(box.windowTitle())
        box.escapeButton().click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", press_esc)
    window._live_mode = True
    event = QCloseEvent()
    window.closeEvent(event)
    assert asked and not event.isAccepted()                # still open
    window._live_mode = False


def test_next_banner_is_translated_piece_by_piece(window):
    import i18n
    from models.cue import FollowMode

    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value
    window._cues[0].notes = "uwaga"
    try:
        i18n.set_language("pl")
        window._cue_list.setCurrentRow(0)
        window._sync_live_view()
        text = window._live_show_panel.lbl_standby_banner.text()
        assert "Auto-GO na końcu" in text and "Uwagi:" in text
        assert "al termine" not in text and "Note:" not in text
    finally:
        i18n.set_language("it")
