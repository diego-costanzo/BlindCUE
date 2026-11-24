"""Stage 5, item 5.6: before the show – list mistakes, clock, disk, version, backups, show info."""

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

from engine import list_check as lc
from engine.readiness import CLOCK, DISK, INFO, LIST, PROBLEM, VERSION, Facts, checks
from engine.show_stats import show_stats
from models.cue import Cue
from models.project_manager import BACKUP_DIR_SUFFIX, ProjectManager, keep_backup
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i, **extra):
    data = {"cue_id": 9601 + i, "name": f"c{i}", "media_type": "AUDIO", "file_path": f"/m/{i}.mp3"}
    data.update(extra)
    return Cue.from_dict(data)


def test_list_problems():
    cues = [_cue(0), _cue(1, start_rel_cue=4242, start_rel_when="end"),
            _cue(2, media_type="ACTION", file_path="", action_spec={"kind": "fade", "target": "cues",
                                                                     "cue_ids": [4243]}),
            _cue(3, media_type="ACTION", file_path="", action_spec={"kind": "goto", "cue_ids": []}),
            _cue(4, media_type="GROUP", file_path=""),
            _cue(5, call_only=True),
            _cue(6, media_type="ACTION", file_path="", action_spec={"kind": "stop", "target": "all"}),
            _cue(7, start_rel_cue=4242, start_rel_when="end", enabled=False)]   # off: never plays anyway
    assert lc.list_problems(cues) == [(1, lc.REL_MISSING), (2, lc.NO_TARGET), (3, lc.JUMP_NOWHERE),
                                      (4, lc.EMPTY_SCENE), (5, lc.NEVER_CALLED)]
    cues.append(_cue(8, media_type="ACTION", file_path="", action_spec={"kind": "call", "cue_ids": [9606]}))
    assert (5, lc.NEVER_CALLED) not in lc.list_problems(cues)


def test_readiness_rows():
    plain = [c.key for c in checks(Facts())]
    assert not {LIST, CLOCK, DISK, VERSION} & set(plain)                # nothing to say: no rows
    rows = {c.key: c for c in checks(Facts(list_problems=("#2 'x': gone",), timed=2, clock="19:40",
                                           disk_free_mb=120, version="short", switched_off=3))}
    assert rows[LIST].state == PROBLEM and rows[LIST].values["count"] == 1
    assert rows[CLOCK].state == INFO and rows[CLOCK].values == {"count": 2, "time": "19:40"}
    assert rows[DISK].state == PROBLEM and rows[VERSION].values == {"name": "short", "off": 3}
    assert DISK not in {c.key for c in checks(Facts(disk_free_mb=5000))}


def test_backups_keep_the_newest_five(tmp_path):
    show = tmp_path / "Play.blindcue"
    assert keep_backup(show) is None                                     # a new file: nothing to keep
    show.write_text("v0", encoding="utf-8")
    folder = tmp_path / f"Play{BACKUP_DIR_SUFFIX}"
    for n in range(1, 8):
        os.utime(show, (1_700_000_000 + n * 60, 1_700_000_000 + n * 60))
        assert keep_backup(show) is not None
        assert keep_backup(show) is None                                 # the same again: no second copy
        show.write_text(f"v{n}", encoding="utf-8")
    kept = sorted(p.read_text(encoding="utf-8") for p in folder.iterdir())
    assert kept == ["v2", "v3", "v4", "v5", "v6"]
    other = tmp_path / "autosave.json"
    other.write_text("{}", encoding="utf-8")
    assert keep_backup(other) is None                                    # only show files


def test_save_project_keeps_the_previous_file(tmp_path):
    show = tmp_path / "Play.blindcue"
    pm = ProjectManager(autosave_dir=tmp_path / "auto")
    assert pm.save_project(show, [_cue(0)])
    assert pm.save_project(show, [_cue(0), _cue(1)])
    copies = list((tmp_path / f"Play{BACKUP_DIR_SUFFIX}").iterdir())
    assert len(copies) == 1 and '"cues_count": 1' in copies[0].read_text(encoding="utf-8")


def test_show_stats():
    cues = [_cue(0), _cue(1, media_type="VIDEO", file_path="/m/v.mp4", follow_mode="SIMULTANEOUS"),
            _cue(2, adlib=True), _cue(3, enabled=False), _cue(4, media_type="GROUP", file_path="")]
    stats = show_stats(cues)
    assert stats["cues"] == 5 and stats["audio"] == 3 and stats["video"] == 1 and stats["scenes"] == 1
    assert stats["go"] == 2 and stats["effects"] == 1 and stats["off"] == 1 and stats["missing"] == 4


def test_window_show_info_and_list_row(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _show_info
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [_cue(0), _cue(1, media_type="GROUP", file_path="")]       # a scene with nothing in it
        win._refresh_cue_list(keep_selection=False)
        facts = win._readiness_facts()
        assert len(facts.list_problems) == 1 and "#2" in facts.list_problems[0]
        assert facts.disk_free_mb is not None and facts.clock

        def fill(dlg):
            edits = dlg.findChildren(_show_info.QLineEdit)
            edits[0].setText("Romeo")
            edits[1].setText("3b")
            return _show_info.QDialog.DialogCode.Accepted

        monkeypatch.setattr(_show_info.QDialog, "exec", fill)
        win._open_show_info()
        assert win._show_info["title"] == "Romeo" and win._show_title() == "Romeo"
        target = tmp_path / "romeo.blindcue"
        assert win._do_save(str(target))
        _cues, _index, settings = ProjectManager().load_project(target)
        assert settings["info"] == {"title": "Romeo", "author": "3b"}
        win._show_info_load({})
        win._show_info_load(settings)
        assert win._show_info["author"] == "3b"
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
