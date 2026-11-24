"""Stage 5, item 5.3: take cues over from another show."""

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

from engine.show_engine import insert_position
from engine.show_import import take_over
from models.cue import Cue
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _other(tmp_path) -> list[Cue]:
    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")

    def cue(i, **extra):
        data = {"cue_id": 7700 + i, "name": f"o{i}", "media_type": "AUDIO", "file_path": str(song)}
        data.update(extra)
        return Cue.from_dict(data)

    return [cue(0, name="scene", media_type="GROUP", file_path=""), cue(1, parent_id=7700),
            cue(2, parent_id=7700, start_rel_cue=7701, start_rel_when="end"),
            cue(3, name="bell", file_path=str(tmp_path / "gone.wav")),
            cue(4, name="fade", media_type="ACTION", file_path="",
                action_spec={"kind": "fade", "target": "cues", "cue_ids": [7701, 7703]})]


def test_take_over_keeps_links_and_reports(tmp_path):
    other = _other(tmp_path)
    new, warnings = take_over(other, [7700, 7704])                  # the scene (with its cues) and the fade
    assert [c.name for c in new] == ["scene", "o1", "o2", "fade"]
    scene, o1, o2, fade = new
    assert not {c.cue_id for c in new} & {c.cue_id for c in other}  # fresh numbers
    assert o1.parent_id == scene.cue_id and o2.start_rel_cue == o1.cue_id
    assert fade.action_spec["cue_ids"] == [o1.cue_id]               # the bell was not taken over
    assert ("targets", "fade", 1) in warnings
    _new, warnings = take_over(other, [7702, 7703])
    kinds = sorted(w[0] for w in warnings)
    assert kinds == ["file", "relative"]                            # o2 alone; the bell's file is gone


def test_menu_imports_after_the_selection(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.main_window import _show_import
    from ui.output_window import OutputWindow

    show = tmp_path / "other.blindcue"        # loading is replaced below: the cues come from _other()
    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    try:
        win._cues = [Cue.from_dict({"cue_id": 7800 + i, "name": f"mine{i}", "media_type": "IMAGE",
                                    "file_path": "/x.png"}) for i in range(2)]
        win._refresh_cue_list(keep_selection=False)
        win._cue_list.setCurrentRow(0)
        win._commit_undo_point()
        monkeypatch.setattr(_show_import.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(show), "")))
        monkeypatch.setattr(_show_import.ProjectManager, "load_project", lambda self, p: (_other(tmp_path), -1, {}))
        monkeypatch.setattr(win, "_choose_cues_to_import", lambda other: [other[0].cue_id])
        monkeypatch.setattr(_show_import.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        win._import_from_show()
        assert [c.name for c in win._cues] == ["mine0", "scene", "o1", "o2", "mine1"]
        win._on_undo()
        assert [c.name for c in win._cues] == ["mine0", "mine1"]
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_ties_to_cues_left_behind_become_go(tmp_path):
    picture = tmp_path / "x.png"
    picture.write_bytes(b"png")

    def cue(i, **extra):
        data = {"cue_id": 7900 + i, "name": f"t{i}", "media_type": "IMAGE", "file_path": str(picture)}
        data.update(extra)
        return Cue.from_dict(data)

    other = [cue(0, follow_mode="AUTO_FOLLOW"), cue(1), cue(2, follow_mode="SIMULTANEOUS"), cue(3),
             cue(4, adlib=True, hotkey="A"), cue(5, start_clock="20:00"), cue(6, call_only=True),
             cue(7, enabled=False)]
    here = [Cue.from_dict({"cue_id": 7990, "name": "mine", "media_type": "AUDIO", "file_path": "/a.wav",
                           "adlib": True, "hotkey": "a"})]
    new, warnings = take_over(other, [7900, 7902, 7903, 7904, 7905, 7906, 7907], here)
    t0, t2 = new[:2]
    assert t0.follow_mode == "MANUAL" and ("tie", "t0", 1) in warnings    # its next cue stayed there
    assert t2.follow_mode == "SIMULTANEOUS"                                # t3 still comes next
    kinds = {w[0] for w in warnings}
    assert {"key", "clock", "call", "enabled"} <= kinds
    assert new[-1].enabled                                                  # that show's versions stay there
    _new, warnings = take_over(other, [7900, 7901], here)
    assert not warnings


def test_insert_position_after_tied_scene_and_effects():
    def cue(i, **extra):
        data = {"cue_id": 7950 + i, "name": f"p{i}", "media_type": "IMAGE", "file_path": "/x.png"}
        data.update(extra)
        return Cue.from_dict(data)

    tied_scene = [cue(0, media_type="GROUP", file_path=""), cue(1, parent_id=7950),
                  cue(2, parent_id=7950, follow_mode="SIMULTANEOUS"), cue(3), cue(4)]
    assert insert_position(tied_scene, 0) == (4, None)          # the last step pulls p3: after it
    cascade = [cue(0, media_type="GROUP", file_path="", group_mode="SEQUENCE"), cue(1, parent_id=7950),
               cue(2), cue(3)]
    assert insert_position(cascade, 0) == (3, None)             # a Cascata starts the row after it
    effect_between = [cue(0, follow_mode="AUTO_FOLLOW"), cue(1, adlib=True), cue(2), cue(3)]
    assert insert_position(effect_between, 0) == (3, None)      # p0's Auto-GO skips the effect to p2
