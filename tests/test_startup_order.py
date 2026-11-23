"""The "restore session?" question is asked only after the whole boot.

OutputWindow.configure_screen() calls processEvents(); a question scheduled
from the MainWindow constructor ran inside it, with the output already full
screen and on top and before the DeviceManager handled monitor hotplug.
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

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_restore_question_is_not_asked_from_the_constructor(qt_app, tmp_path, monkeypatch):
    """MainWindow must not schedule the restore question itself: main() does,
    after the whole boot (output windows, DeviceManager, hotplug)."""
    from models.project_manager import ProjectManager

    asked: list[str] = []
    monkeypatch.setattr(ProjectManager, "check_crash_recovery",
                        lambda self: {"saved_at": "now", "cues": [], "cues_count": 0})
    def answer_no(box):
        asked.append("q")
        box.button(QMessageBox.StandardButton.No).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", answer_no)
    monkeypatch.setattr(ProjectManager, "discard_autosave", lambda self: None)

    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow
    output = OutputWindow()
    win = MainWindow(output)
    try:
        _pump_until(lambda: bool(asked), timeout=0.6)
        assert asked == [], "restore question asked during construction"
        win._check_crash_recovery()
        assert asked == ["q"]
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        QCoreApplication.processEvents()
