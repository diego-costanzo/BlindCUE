"""Stage 4, item 4.5: "Identify the screens" - a big number on every screen for a few seconds."""

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

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QLabel


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_numbers_show_and_close_by_themselves():
    app = QApplication.instance() or QApplication([])
    from ui.identify_screens import show_screen_numbers

    shown = show_screen_numbers(app.screens(), seconds=0.2)
    assert len(shown) == len(app.screens()) >= 1
    first = shown[0]
    assert first.isVisible() and first.findChildren(QLabel)[0].text() == "1"
    assert app.screens()[0].geometry().contains(first.geometry().center())   # in the middle of its screen
    _pump(0.5)
    assert not any(w.isVisible() for w in QApplication.topLevelWidgets() if type(w).__name__ == "ScreenNumber")


def test_dialog_refuses_while_on_air(monkeypatch):
    QApplication.instance() or QApplication([])
    from engine.device_manager import DeviceManager
    from ui import device_settings_dialog as dsd
    from ui import identify_screens

    told, shown = [], []
    monkeypatch.setattr(dsd.QMessageBox, "information", staticmethod(lambda *a, **k: told.append(a[1])))
    monkeypatch.setattr(identify_screens, "show_screen_numbers", lambda screens: shown.append(screens) or [])
    mgr = DeviceManager()
    dlg = dsd.DeviceSettingsDialog(mgr, busy=lambda: True)
    try:
        assert dlg._combo_screen.itemText(0).startswith("1. ")
        dlg._identify_screens()
        assert told and not shown
        dlg._busy = lambda: False
        dlg._identify_screens()
        assert shown
    finally:
        dlg.close()
        _pump()
