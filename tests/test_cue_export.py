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
    assert data[0]["follow"] == "⇉ Simult." and data[2]["follow"] == "Auto-GO"
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


def _scene_show() -> list[Cue]:
    def cue(i, **extra):
        data = {"cue_id": 9871 + i, "name": f"k{i}", "media_type": "AUDIO", "file_path": f"/m/k{i}.mp3"}
        data.update(extra)
        return Cue.from_dict(data)

    return [cue(0, media_type="GROUP", file_path="", group_mode="STEP"), cue(1, parent_id=9871),
            cue(2, parent_id=9871), cue(3, parent_id=9871, follow_mode="AUTO_FOLLOW"),
            cue(4, name="started by the last step"),
            cue(5, media_type="GROUP", file_path="", group_mode="SEQUENCE"), cue(6, parent_id=9876),
            cue(7, parent_id=9876), cue(8, name="after the Cascata"), cue(9, name="next GO"),
            cue(10, name="off", enabled=False)]


def test_operator_list_follows_scenes():
    data = rows(_scene_show())
    by_hand = [r["name"] for r in data if r["_by_hand"]]
    # a step scene: one GO per step after the first; the last step's Auto-GO starts k4;
    # a Cascata that is not a playlist starts the row after it by itself
    assert by_hand == ["k0", "k2", "k3", "k5", "next GO"]
    assert data[-1]["off"] and not data[0]["off"]


def test_xlsx_is_a_workbook(tmp_path):
    import xml.etree.ElementTree as ET
    import zipfile

    from engine.cue_export import COLUMNS, to_xlsx

    show = _show()
    show[0].name = "=1+1 <&>"
    show[1].enabled = False
    show[2].pre_delay = 1.5
    target = tmp_path / "list.xlsx"
    to_xlsx(rows(show), target, {"name": "Nazwa"}, sheet="Lista: [1]", title="Show")
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(target) as zf:
        assert {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                "xl/styles.xml", "xl/worksheets/sheet1.xml"} <= set(zf.namelist())
        for part in zf.namelist():
            ET.fromstring(zf.read(part))                       # every part is well-formed XML
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        name = ET.fromstring(zf.read("xl/workbook.xml")).find(".//m:sheet", ns).get("name")
    assert name == "Lista   1"                                   # no []: in a sheet name
    table = {}
    main = "{" + ns["m"] + "}"
    for c in sheet.iter(main + "c"):
        text = "".join(t.text or "" for t in c.iter(main + "t")) or (c.findtext("m:v", "", ns))
        table[c.get("r")] = (text, c.get("s"), c.get("t"))
    col = {k: chr(65 + i) for i, k in enumerate(COLUMNS)}
    assert table[f"{col['name']}1"] == ("Nazwa", "1", "inlineStr")      # bold header
    assert table[f"{col['name']}2"][0] == "=1+1 <&>"                    # text, never a formula
    assert table[f"{col['pre']}4"][:2] == ("1.5", None) and table[f"{col['pre']}4"][2] is None  # a number
    assert table[f"{col['name']}3"][1] == "2"                           # a cue that is off: struck through
    assert table[f"{col['line']}2"][0] == "…and then the storm"


def test_pdf_and_show_columns(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.live_show_view import COL_LINE, COL_PAGE
    from ui.main_window import MainWindow, _export
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = _show()
        target = tmp_path / "op.pdf"
        monkeypatch.setattr(_export.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
        win._export_list_pdf("operator")
        assert target.read_bytes()[:5] == b"%PDF-" and target.stat().st_size > 1000
        win._export_list_pdf("prompter")
        assert target.read_bytes()[:5] == b"%PDF-"
        xlsx = tmp_path / "list"
        monkeypatch.setattr(_export.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(xlsx), "")))
        win._export_list_xlsx()
        assert (tmp_path / "list.xlsx").is_file()

        table = win._live_show_panel.live_table
        win._live_show_panel.sync_cues(win._cues, 0, {})
        assert not table.isColumnHidden(COL_PAGE) and not table.isColumnHidden(COL_LINE)
        assert table.item(0, COL_PAGE).text() == "3" and table.item(0, COL_LINE).text().endswith("storm")
        assert table.horizontalHeader().visualIndex(COL_PAGE) == 3      # next to the name, not at the end
        for cue in win._cues:
            cue.script_page = cue.script_line = ""
        win._live_show_panel.sync_cues(win._cues, 0, {})
        assert table.isColumnHidden(COL_PAGE) and table.isColumnHidden(COL_LINE)
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_csv_keeps_text_and_decimal_comma(tmp_path):
    show = _show()
    show[0].name = "=1+1"
    show[1].script_line = "-Yes?"
    show[2].pre_delay = 1.5
    target = tmp_path / "list.csv"
    to_csv(rows(show), target, {})
    with open(target, encoding="utf-8-sig") as fh:
        table = list(csv.reader(fh, delimiter=";"))
    head = table[0]
    assert table[1][head.index("name")] == "'=1+1"          # not a formula
    assert table[2][head.index("line")] == "'-Yes?"
    assert table[3][head.index("pre")] == "1,5"            # not the 1st of May
