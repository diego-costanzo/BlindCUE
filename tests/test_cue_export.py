"""Stage 5, item 5.1: export the cue list (CSV) and print it for the operator / the prompter."""

from __future__ import annotations

import csv
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
from engine.cue_export import rows, to_csv, to_html
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _show() -> list[Cue]:
    def cue(i, **extra):
        data = {"cue_id": 9891 + i, "name": f"c{i}", "media_type": "AUDIO", "file_path": f"/m/c{i}.mp3"}
        data.update(extra)
        return Cue.from_dict(data)

    return [cue(0, q_label="Q1", script_page="3", script_line="…and then the storm", notes="slow",
                follow_mode="SIMULTANEOUS"),
            cue(1, name="with Q1"),
            cue(2, q_label="Q2", script_page="5", follow_mode="AUTO_FOLLOW"),
            cue(3, name="after Q2"),
            cue(4, q_label="Q3", start_clock="19:55")]


def test_rows_and_by_hand():
    data = rows(_show())
    assert [r["_by_hand"] for r in data] == [True, False, True, False, False]   # a time of day is not GO
    assert data[0]["page"] == "3" and data[0]["line"] == "…and then the storm" and data[0]["file"] == "c0.mp3"
    assert data[0]["follow"] == "+" and data[2]["follow"] == "Auto-GO"
    back = Cue.from_dict(_show()[0].to_dict())
    assert back.script_page == "3" and back.script_line.endswith("storm")


def test_csv_and_html(tmp_path):
    data = rows(_show())
    target = tmp_path / "list.csv"
    to_csv(data, target, {"name": "Nazwa"})
    with open(target, encoding="utf-8-sig") as fh:
        table = list(csv.reader(fh, delimiter=";"))
    assert table[0][2] == "Nazwa" and table[1][1] == "Q1" and len(table) == 6
    op = to_html(data, "Show <1>", "operator", {})
    assert op.count("<tr>") == 1 + 2 and "Show &lt;1&gt;" in op                  # header + two cues by hand
    pr = to_html(data, "Show", "prompter", {})
    assert pr.count("<tr>") == 1 + 5 and "…and then the storm" in pr


def test_menu_actions(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _export
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = _show()
        target = tmp_path / "out.csv"
        monkeypatch.setattr(_export.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
        win._export_list_csv()
        assert target.is_file() and "Q2" in target.read_text(encoding="utf-8-sig")
        opened = []
        monkeypatch.setattr(_export.QDesktopServices, "openUrl", staticmethod(opened.append))
        win._print_list("prompter")
        assert opened and Path(opened[0].toLocalFile()).read_text(encoding="utf-8").count("<tr>") == 6
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
