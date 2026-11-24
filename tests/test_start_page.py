"""Stage 5, item 5.16: the start page with the first steps."""

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

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_start_page_choices_and_the_hidden_list(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from engine.show_mode import EDIT_LIST
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow
    from ui.start_page import SETTINGS_KEY

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    settings = QSettings("BlindCue", "BlindCue")
    try:
        show = tmp_path / "Jasełka.blindcue"
        show.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(win, "_recent_projects", lambda: [str(show), str(tmp_path / "gone.blindcue")])
        win._show_start_page_if_wanted()
        page = win._start_page
        assert win._start_page_visible() and page.chk_show.isChecked()
        assert page.recent_box.count() == 1                              # a missing show is not offered
        assert not win._change_allowed(EDIT_LIST)                       # Delete never hits the hidden list
        called = []
        monkeypatch.setattr(win, "_on_add_files", lambda: called.append("files"))
        page.add_files_requested.emit()
        assert called == ["files"] and not win._start_page_visible()
        page.chk_show.setChecked(False)
        assert settings.value(SETTINGS_KEY, type=bool) is False
        win._show_start_page_if_wanted()                                 # turned off: not shown
        assert not win._start_page_visible()
        win._show_start_page()                                           # File → Start page still works
        opened = []
        monkeypatch.setattr(win, "open_show_from_outside", lambda p: opened.append(p))
        page.recent_box.itemAt(0).widget().click()
        assert opened == [str(show)] and not win._start_page_visible()
    finally:
        settings.remove(SETTINGS_KEY)
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
