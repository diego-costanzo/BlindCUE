"""Stage 5, item 5.11: undo steps in words, undo back to a step, a backup put back."""

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

from engine.undo_names import describe
from models.cue import Cue
from models.project_manager import ProjectManager, backups_of
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i, **extra):
    data = {"cue_id": 9301 + i, "name": f"h{i}", "media_type": "AUDIO", "file_path": f"/m/{i}.mp3"}
    data.update(extra)
    return Cue.from_dict(data)


def test_describe():
    a = [_cue(0).to_dict(), _cue(1).to_dict()]
    b = [_cue(0, fade_in=2.0, q_label="Q7").to_dict(), _cue(1).to_dict()]
    c = [dict(b[0], fade_in=0.0), b[1]]
    assert describe(a, a).kind == "none"
    one = describe(b, c)
    assert (one.kind, one.q, one.name, one.field, one.old, one.new) == ("field", "Q7", "h0", "fade_in", "2", "0")
    assert describe(a, a + [_cue(2).to_dict()]).kind == "added"
    assert describe(a, a[:1]).count == 1 and describe(a, a[:1]).kind == "removed"
    assert describe(a, list(reversed(a))).kind == "moved"
    many = describe(a, [dict(a[0], volume=0.5), dict(a[1], volume=0.5)])
    assert (many.kind, many.count, many.field) == ("many", 2, "volume")
    status_only = [dict(a[0], status="LIVE"), a[1]]
    assert describe(a, status_only).kind == "none"


def test_window_history_and_backup(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _history
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [_cue(i, file_path=str(tmp_path / f"{i}.mp3")) for i in range(2)]  # real paths on Windows
        win._refresh_cue_list(keep_selection=False)
        win._reset_undo_history()
        win._cues[0].name = "Bell"
        win._commit_undo_point()
        win._cues[1].fade_in = 3.0
        win._commit_undo_point()
        texts = win._undo_steps_text()
        assert len(texts) == 2 and "Fade In" in texts[0] and "Bell" in texts[1]
        monkeypatch.setattr(_history.QDialog, "exec", lambda self: _history.QDialog.DialogCode.Accepted)
        win._open_history()                       # the newest step is chosen by default
        assert win._cues[1].fade_in == 0.0 and win._cues[0].name == "Bell"
        win._undo_steps(1)
        assert win._cues[0].name == "h0"

        show = tmp_path / "Play.blindcue"
        assert win._do_save(str(show))
        win._current_project_path = str(show)
        win._cues[0].name = "Changed"
        win._last_selection_sig = None
        win._sync_selection_state()               # as after an edit in the inspector
        win._commit_undo_point()
        assert win._do_save(str(show))
        assert len(backups_of(show)) == 1
        versions = win._saved_versions()            # 5.6: the saved file first, then the backups
        assert [v[0] for v in versions] == ["file", "backup"]
        monkeypatch.setattr(win, "_choose_saved_version", lambda vs: 1)
        win._restore_backup()
        assert win._cues[0].name == "h0"          # the list as it was at the first save
        win._on_undo()
        assert win._cues[0].name == "Changed"     # one Ctrl+Z goes back
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_show_from_another_system_keeps_its_cues(tmp_path):
    """A show saved on Linux / macOS ("/home/...") opened on Windows (and back): the cues stay, OFFLINE."""
    import json

    show = tmp_path / "Play.blindcue"
    (tmp_path / "found.mp3").write_bytes(b"x")
    rows = [{"cue_id": 1, "name": "linux", "media_type": "AUDIO", "file_path": "/home/teacher/song.mp3"},
            {"cue_id": 2, "name": "windows", "media_type": "AUDIO", "file_path": "D:\\Show\\song.mp3"},
            {"cue_id": 3, "name": "here by name", "media_type": "AUDIO", "file_path": "/media/usb/found.mp3"},
            {"cue_id": 4, "name": "traversal", "media_type": "AUDIO", "file_path": "../../etc/passwd"}]
    show.write_text(json.dumps({"app": "BlindCue", "cues": rows}), encoding="utf-8")
    cues, _i, _s = ProjectManager(autosave_dir=tmp_path / "auto").load_project(show)
    by_name = {c.name: c for c in cues}
    assert set(by_name) == {"linux", "windows", "here by name"}           # the traversal is still refused
    assert by_name["linux"].status.value == "OFFLINE" and by_name["linux"].file_path == "/home/teacher/song.mp3"
    assert Path(by_name["here by name"].file_path) == (tmp_path / "found.mp3").resolve()


def test_backup_of_a_portable_show_finds_its_media(tmp_path):
    media = tmp_path / "Play_media"
    media.mkdir()
    (media / "a.wav").write_bytes(b"RIFF")
    show = tmp_path / "Play.blindcue"
    pm = ProjectManager(autosave_dir=tmp_path / "auto")
    cue = _cue(0, file_path=str(media / "a.wav"))
    assert pm.save_project(show, [cue], media_map={str((media / "a.wav").resolve()): "Play_media/a.wav"})
    assert pm.save_project(show, [cue, _cue(1)])
    copy = backups_of(show)[0]
    cues, _i, _s = pm.load_project(copy, as_path=show)
    assert Path(cues[0].file_path).resolve() == (media / "a.wav").resolve()
