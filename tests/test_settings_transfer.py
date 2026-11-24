"""Stage 5, item 5.13: the settings of this computer to a file and back."""

from __future__ import annotations

import json
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
from engine.settings_transfer import changes, from_json, to_json, transferable
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_only_the_groups_that_travel():
    assert transferable("audio/master_name") and transferable("keys/map") and transferable("ui/view_variant")
    assert not transferable("live/exit_pin")                 # the lock stays on its computer
    assert not transferable("file/recent_projects") and not transferable("paths/show_dir")
    assert not transferable("audio") and not transferable("geometry/main")
    text = to_json({"audio/master_name": "JBL", "live/exit_pin": "1234", "recent/pinned": ["a"],
                    "live/fade_button_sec": 3.0, "ui/earcons_enabled": True}, "LAPTOP", "2026-11-24T12:00:00")
    data = json.loads(text)
    assert data["computer"] == "LAPTOP" and set(data["values"]) == {"audio/master_name", "live/fade_button_sec",
                                                                    "ui/earcons_enabled"}
    back = from_json(text)
    assert back == {"audio/master_name": "JBL", "live/fade_button_sec": 3.0, "ui/earcons_enabled": True}
    assert changes({"audio/master_name": "JBL", "ui/earcons_enabled": "true"}, back) == {
        "live": ["live/fade_button_sec"], "ui": ["ui/earcons_enabled"]}   # "true" vs True differ as text
    for bad in ("{", "[]", json.dumps({"format": "x"}), json.dumps({"format": "blindcue-computer-settings",
                                                                     "version": 99, "values": {}})):
        with pytest.raises(ValueError):
            from_json(bad)


def test_save_and_load_through_the_menu(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _settings_transfer as mod
    from ui.output_window import OutputWindow

    settings = QSettings("BlindCue", "BlindCue")
    settings.setValue("live/fade_button_sec", 4.0)
    settings.setValue("live/exit_pin", "9999")
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    target = tmp_path / "ustawienia.json"
    try:
        monkeypatch.setattr(mod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
        win._export_computer_settings()
        values = json.loads(target.read_text(encoding="utf-8"))["values"]
        assert "live/fade_button_sec" in values and "live/exit_pin" not in values
        settings.setValue("live/fade_button_sec", 1.0)          # "another computer"
        monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(target), "")))
        asked = []
        monkeypatch.setattr(mod.QMessageBox, "question",
                            staticmethod(lambda *a, **k: asked.append(a[2]) or mod.QMessageBox.StandardButton.Yes))
        win._import_computer_settings()
        assert asked and float(settings.value("live/fade_button_sec")) == 4.0
        assert settings.value("live/exit_pin") == "9999"         # never touched
    finally:
        for key in ("live/fade_button_sec", "live/exit_pin"):
            settings.remove(key)
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
