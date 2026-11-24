"""Stage 5, item 5.9 (rest): the "School show" template, the sound library and the cue library."""

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

from engine.show_templates import (
    library_snippets,
    library_sounds,
    safe_file_name,
    school_show,
    with_scene_cues,
)
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_school_template(tmp_path):
    bell = tmp_path / "bell.mp3"
    bell.write_bytes(b"x")
    cues = school_show(bell=str(bell), caption_png=lambda spec: str(tmp_path / "cap.png"))
    names = [c.name for c in cues]
    assert names[0].startswith("Musica") and sum("Campanella" in n for n in names) == 3
    assert all(c.status.value == "LOADED" for c in cues if "Campanella" in c.name)
    waiting = [c for c in cues if c.status.value == "OFFLINE"]
    assert {c.media_type.value for c in waiting} == {"AUDIO", "IMAGE"} and all(not c.file_path for c in waiting)
    kinds = [c.action_spec.get("kind") for c in cues if c.media_type.value == "ACTION"]
    assert kinds == ["fade", "countdown", "fade", "fade"]
    phones = next(i for i, c in enumerate(cues) if c.text_spec)
    assert cues[phones - 1].follow_mode == "SIMULTANEOUS" and cues[phones].layer == 3
    no_files = school_show(caption_png=None)
    assert not any(c.text_spec for c in no_files)
    assert all(c.status.value == "OFFLINE" for c in no_files if "Campanella" in c.name)


def test_library_folders_and_names(tmp_path):
    (tmp_path / "Bells").mkdir()
    (tmp_path / "_unused").mkdir()
    for rel in ("b.mp3", "a 10.wav", "a 2.wav", "notes.txt", "Bells/big.ogg", "_unused/old.mp3", ".hidden.mp3"):
        (tmp_path / rel).write_bytes(b"x")
    groups = library_sounds(tmp_path)
    assert [(g, [p.name for p in files]) for g, files in groups] == [
        ("", ["a 2.wav", "a 10.wav", "b.mp3"]), ("Bells", ["big.ogg"])]
    (tmp_path / "Scene 2.blindcue").write_text("{}", encoding="utf-8")
    (tmp_path / "Scene 10.blindcue").write_text("{}", encoding="utf-8")
    assert [p.stem for p in library_snippets(tmp_path)] == ["Scene 2", "Scene 10"]
    assert safe_file_name('Bell: "big" / small?') == "Bell big small"
    assert safe_file_name("con") == "_con" and safe_file_name(" ... ") == "cue"
    cues = [Cue.from_dict({"cue_id": 9801 + i, "name": f"l{i}", "media_type": "AUDIO", "file_path": "/m.mp3"})
            for i in range(3)]
    cues[0].media_type = cues[0].media_type.GROUP
    cues[1].parent_id = 9801
    assert [c.name for c in with_scene_cues(cues, [0])] == ["l0", "l1"]


def test_window_libraries_and_template(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui import dialog_dirs
    from ui.main_window import MainWindow, _library
    from ui.output_window import OutputWindow

    monkeypatch.setattr(dialog_dirs, "show_dir", lambda: str(tmp_path))
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        sounds = win._sounds_dir()
        assert (sounds / "Campanella.mp3").is_file()          # the program's bell is put in a new library
        win._rebuild_sound_menu()
        texts = [a.text() for a in win._sound_menu.actions()]
        assert any("Campanella" in t for t in texts)
        win._add_library_sound(str(sounds / "Campanella.mp3"))
        assert len(win._cues) == 1 and win._cues[0].layer == 2 and win._cues[0].name == "Campanella"

        win._mark_modified(False)                              # else "save the changes?" waits for an answer
        assert win._new_show_from_template()
        assert len(win._cues) >= 10 and win._show_info["title"] == "Spettacolo scolastico"
        bells = [c for c in win._cues if "Campanella" in c.name]
        assert bells and all(Path(c.file_path) == sounds / "Campanella.mp3" for c in bells)

        win._cue_list.selectRow(1)
        _pump()
        monkeypatch.setattr(_library.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Bells: 3 min", True)))
        win._save_cues_to_library()
        saved = win._cues_dir() / "Bells 3 min.blindcue"
        assert saved.is_file() and (win._cues_dir() / "Bells 3 min_media").is_dir()   # with its media
        win._rebuild_snippet_menu()
        assert any("Bells 3 min" in a.text() for a in win._snippet_menu.actions())
        before = len(win._cues)
        ids = {c.cue_id for c in win._cues}
        win._insert_library_snippet(str(saved))
        new = [c for c in win._cues if c.cue_id not in ids]
        assert len(win._cues) == before + 1 and new[0].name == bells[0].name
        win._on_undo()
        assert len(win._cues) == before

        # A cue saved from inside a scene comes back at the top level (its scene is not in the file).
        from models.cue import MediaType

        scene = Cue(name="scene", media_type=MediaType.GROUP, file_path="")
        child = Cue(name="inside", media_type=MediaType.AUDIO, file_path=str(sounds / "Campanella.mp3"),
                    parent_id=scene.cue_id)
        win._cues = [scene, child]
        win._refresh_cue_list(keep_selection=False)
        win._cue_list.selectRow(1)
        _pump()
        monkeypatch.setattr(_library.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Inside", True)))
        win._save_cues_to_library()
        assert child.parent_id == scene.cue_id                 # the show itself is not changed
        win._insert_library_snippet(str(win._cues_dir() / "Inside.blindcue"))
        new = [c for c in win._cues if c.name == "inside" and c.cue_id != child.cue_id]
        assert len(new) == 1 and new[0].parent_id is None
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()
