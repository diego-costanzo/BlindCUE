"""Stage 5, item 5.6 (rest): the show diary, "why changed?", restoring a saved version."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine import run_report as rr
from engine.show_diff import differences
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QListWidget


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i, tmp_path=None, **extra):
    path = str(tmp_path / f"d{i}.mp3") if tmp_path else f"/m/d{i}.mp3"
    data = {"cue_id": 9701 + i, "name": f"d{i}", "media_type": "AUDIO", "file_path": path}
    data.update(extra)
    return Cue.from_dict(data)


def test_differences_list_everything():
    a = [_cue(0).to_dict(), _cue(1).to_dict(), _cue(2).to_dict()]
    b = [dict(a[1], fade_in=2.0, name="Bell"), dict(a[0], status="LIVE"), _cue(3).to_dict()]
    got = [(c.kind, c.name, c.field, c.old, c.new) for c in differences(a, b, {"info": {}}, {"info": {"title": "x"},
                                                                                         "output": {"m": 1}})]
    assert ("added", "d3", "", "", "") in got and ("removed", "d2", "", "", "") in got
    assert ("moved", "Bell", "", "", "") in got
    assert ("field", "Bell", "fade_in", "0", "2") in got and ("field", "Bell", "name", "d1", "Bell") in got
    assert ("setting", "", "info", "…", "…") in got
    assert not any(c[2] in ("status", "output") for c in got)              # runtime state, the computer's output
    assert differences(a, a) == []


def test_report_lists_notes():
    page = rr.to_html("Show", datetime(2026, 11, 24, 19, 0), [(5.0, rr.GO, "#1", "a"),
                                                              (9.0, rr.NOTE, "", "mic 2 crackled")],
                      {rr.NOTE: "Note"}, {"start": "S", "end": "E", "length": "L", rr.NOTE: "Notes"}, [],
                      ("a", "b", "c"), "f")
    assert "class='note'" in page and "mic 2 crackled" in page and "<td>Notes</td><td><b>1</b></td>" in page


@pytest.fixture()
def window(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow, _countdown
    from ui.output_window import OutputWindow

    monkeypatch.setattr(_countdown, "runs_dir", lambda show: tmp_path / "runs" / Path(show).stem if show else None)
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        yield win
    finally:
        if getattr(win, "_diary_window", None) is not None:
            win._diary_window.close()
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_diary_notes_go_into_the_run(window, tmp_path):
    win = window
    win._cues = [_cue(0, tmp_path, name="a"), _cue(1, tmp_path, name="b")]
    win._current_project_path = str(tmp_path / "play.blindcue")
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    win._open_show_diary()
    dlg = win._diary_window
    assert not dlg.edit_note.isEnabled()                               # only in the show
    assert not win.diary_note("too early")
    win.set_live_mode(True)
    win._on_go()
    dlg.refresh()
    assert dlg.edit_note.isEnabled()
    dlg.edit_note.setText("mic 2 crackled")
    dlg._add()
    entries = [dlg.listing.item(i).text() for i in range(dlg.listing.count())]
    assert any("#1" in e and "a" in e for e in entries) and any("mic 2 crackled" in e for e in entries)
    assert win._run_log[-1][4] == rr.NOTE and dlg.edit_note.text() == ""
    win.set_live_mode(False)                                             # writes the run and its report
    report = next((tmp_path / "runs" / "play").glob("*.html")).read_text(encoding="utf-8")
    assert "mic 2 crackled" in report


def test_why_changed_and_saved_versions(window, tmp_path, monkeypatch):
    from ui.main_window import _show_diary

    win = window
    win._cues = [_cue(0, tmp_path), _cue(1, tmp_path)]
    win._refresh_cue_list(keep_selection=False)
    win._reset_undo_history()
    show = tmp_path / "Play.blindcue"
    assert win._do_save(str(show))
    win._current_project_path = str(show)
    assert win._changes_since_save() == []
    win._cues[1].name = "Bell"
    win._cues.pop(0)
    win._refresh_cue_list(keep_selection=False)
    win._commit_undo_point()                                           # as an edit in the program does
    win._show_info = {"title": "Our play"}
    win._mark_modified(True)
    kinds = {(c.kind, c.field) for c in win._changes_since_save()}
    assert kinds == {("removed", ""), ("field", "name"), ("setting", "info")}
    seen = []

    def look(dlg):
        listing = dlg.findChild(QListWidget, "why_changed")
        seen.extend(listing.item(i).text() for i in range(listing.count()))
        return _show_diary.QDialog.DialogCode.Rejected

    monkeypatch.setattr(_show_diary.QDialog, "exec", look)
    win._why_modified()
    assert len(seen) == 3 and any("Bell" in s for s in seen)

    assert win._do_save(str(show))                                     # a backup of the first save
    aside = win._project_manager.autosave_file.with_name("autosave.discarded.json")
    aside.write_text(json.dumps({"active_project_path": str(show), "saved_at": "2026-11-24T20:00:00",
                                 "cues": [_cue(5, tmp_path, name="from the crash").to_dict()]}), encoding="utf-8")
    versions = win._saved_versions()
    assert [v[0] for v in versions] == ["file", "backup", "aside"]
    shown = {}

    def look_versions(dlg):
        details = dlg.findChild(QListWidget, "version_changes")
        shown["details"] = [details.item(i).text() for i in range(details.count())]
        return _show_diary.QDialog.DialogCode.Rejected

    monkeypatch.setattr(_show_diary.QDialog, "exec", look_versions)
    assert win._choose_saved_version(versions) is None
    assert shown["details"][0].startswith("1") and len(shown["details"]) == 1 + 1   # "1 cue", "same as now"
    monkeypatch.setattr(win, "_choose_saved_version", lambda vs: 2)
    win._restore_saved_version()
    assert [c.name for c in win._cues] == ["from the crash"]
    win._on_undo()
    assert [c.name for c in win._cues] == ["Bell"]
