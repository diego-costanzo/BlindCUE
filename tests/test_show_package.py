"""Stage 5, item 5.10 (rest): ZIP package, unused media set aside, a media file renamed everywhere."""

from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine import show_package as sp
from models.cue import Cue
from models.project_manager import ProjectManager
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i, path, **extra):
    data = {"cue_id": 9901 + i, "name": f"p{i}", "media_type": "AUDIO", "file_path": str(path)}
    data.update(extra)
    return Cue.from_dict(data)


def _files(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    for rel, size in (("a/song.mp3", 10), ("b/song.mp3", 20), ("a/t1.mp3", 300), ("a/t2.mp3", 300),
                      ("a/logo.png", 5)):
        (tmp_path / rel).write_bytes(b"x" * size)
    return [_cue(0, tmp_path / "a" / "song.mp3"), _cue(1, tmp_path / "b" / "song.mp3"),
            _cue(2, tmp_path / "gone.mp3"),
            _cue(3, "", media_type="GROUP", group_mode="SEQUENCE", playlist=True),
            _cue(4, tmp_path / "a" / "t1.mp3", parent_id=9904), _cue(5, tmp_path / "a" / "t2.mp3", parent_id=9904)]


def test_zip_package_opens_elsewhere(tmp_path):
    cues = _files(tmp_path)
    assert [(g.name, total) for g, total, _f in sp.playlists(cues)] == [("p3", 600)]
    big = sp.big_playlist_files(cues, limit=500)
    assert big == {sp.path_key(tmp_path / "a" / "t1.mp3"), sp.path_key(tmp_path / "a" / "t2.mp3")}
    target = tmp_path / "out.zip"
    settings = {"layer0_kind": "image", "layer0_image": str(tmp_path / "a" / "logo.png"), "surfaces": []}
    result = sp.write_zip(target, "Our: play", cues, settings, exclude=big)
    assert (result.files, result.size) == (3, 35) and len(result.excluded) == 2 and "gone.mp3" in result.missing[0]
    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
        assert names == {"Our  play/Our  play.blindcue", "Our  play/Our  play_media/song.mp3",
                         "Our  play/Our  play_media/song_2.mp3", "Our  play/Our  play_media/logo.png"}
        elsewhere = tmp_path / "elsewhere"
        zf.extractall(elsewhere)
    loaded, _i, s = ProjectManager(autosave_dir=tmp_path / "auto").load_project(
        elsewhere / "Our  play" / "Our  play.blindcue")
    media = elsewhere / "Our  play" / "Our  play_media"
    assert Path(loaded[0].file_path) == (media / "song.mp3").resolve()
    assert Path(loaded[1].file_path) == (media / "song_2.mp3").resolve()
    assert Path(loaded[4].file_path) == tmp_path / "a" / "t1.mp3"       # left out: the path of this computer
    assert Path(s["layer0_image"]) == (media / "logo.png").resolve()
    assert not (tmp_path / "out.zip.part").exists()
    os.utime(tmp_path / "a" / "song.mp3", (0, 0))                      # dated 1970: no error, packed
    again = sp.write_zip(tmp_path / "old.zip", "Old", cues[:1])
    assert again.files == 1


def test_unused_and_rename(tmp_path):
    media = tmp_path / "Play_media"
    media.mkdir()
    for name in ("used.mp3", "old.mp3", ".hidden"):
        (media / name).write_bytes(b"x")
    show = tmp_path / "Play.blindcue"
    show.write_text(json.dumps({"cues": [{"file_path": "Play_media/used.mp3"}]}), encoding="utf-8")
    used = sp.references_in_show_file(show)
    assert used == {sp.path_key(media / "used.mp3")}
    (tmp_path / "Play_backups").mkdir()
    backup = tmp_path / "Play_backups" / "Play 2026-11-24 10-00-00.blindcue"
    backup.write_text(json.dumps({"cues": [{"file_path": "Play_media/old.mp3"}]}), encoding="utf-8")
    assert sp.references_in_show_file(backup, tmp_path) == {sp.path_key(media / "old.mp3")}  # as restored
    assert sp.references_in_show_file(backup) != {sp.path_key(media / "old.mp3")}
    used |= sp.references_in_show_file(backup, tmp_path)
    used.discard(sp.path_key(media / "old.mp3"))
    unused = sp.unused_media(media, used)
    assert unused == [media / "old.mp3"]
    (media / "_unused").mkdir()
    (media / "_unused" / "old.mp3").write_bytes(b"y")
    moved = sp.set_aside(media, unused)
    assert moved == [media / "_unused" / "old_2.mp3"] and not (media / "old.mp3").exists()
    assert sp.unused_media(media, used) == []                        # _unused is never listed again

    assert sp.rename_target(media / "used.mp3", 'Bell: "big".mp3').name == "Bell big.mp3"
    cues = [_cue(0, media / "used.mp3"), _cue(1, media / "used.mp3", original_file_path=str(media / "used.mp3"))]
    assert sp.rename_in_cues(cues, str(media / "used.mp3"), str(media / "new.mp3")) == 3
    rows = [{"file_path": str(media / "USED.mp3") if os.name == "nt" else str(media / "used.mp3")}]
    assert sp.rename_in_dicts(rows, str(media / "used.mp3"), "x") == 1 and rows[0]["file_path"] == "x"


def test_window_rename_tidy_and_zip(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow, _show_files
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        (tmp_path / "src").mkdir()
        song = tmp_path / "src" / "song.mp3"
        song.write_bytes(b"x" * 10)
        win._cues = [_cue(0, song), _cue(1, song, name="again")]
        win._refresh_cue_list(keep_selection=False)
        win._reset_undo_history()
        win._cues[1].fade_in = 2.0
        win._commit_undo_point()
        monkeypatch.setattr(_show_files.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Bell", True)))
        win._rename_media_file(0)
        bell = tmp_path / "src" / "Bell.mp3"
        assert bell.is_file() and not song.exists()
        assert all(Path(c.file_path) == bell for c in win._cues)
        win._on_undo()                                               # the older step names the new file too
        assert win._cues[1].fade_in == 0.0 and all(Path(c.file_path) == bell for c in win._cues)

        show = tmp_path / "Play.blindcue"
        win._project_bundled = True
        assert win._do_save(str(show))
        win._current_project_path = str(show)
        media = tmp_path / "Play_media"
        (media / "leftover.wav").write_bytes(b"y")
        monkeypatch.setattr(_show_files.QMessageBox, "question",
                            staticmethod(lambda *a, **k: _show_files.QMessageBox.StandardButton.Yes))
        monkeypatch.setattr(_show_files.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        win._tidy_media_folder()
        assert (media / "_unused" / "leftover.wav").is_file() and (media / "Bell.mp3").is_file()

        target = tmp_path / "pack"
        monkeypatch.setattr(_show_files.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        win._export_zip_package()
        with zipfile.ZipFile(tmp_path / "pack.zip") as zf:
            assert "Play/Play_media/Bell.mp3" in zf.namelist() and "Play/Play.blindcue" in zf.namelist()
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
