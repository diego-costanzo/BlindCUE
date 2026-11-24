"""Evaluation 2026-11-24: "Fade" is gentle (3 s unless the cue has its own fade-out) and a scene fades as one."""

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

import pytest
from models.cue import Cue, CueStatus
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


@pytest.fixture
def win():
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    window = MainWindow(output)
    window._clock_timer.stop()
    yield window
    window._force_closing = True
    output.force_close()
    window.close()
    _pump()
    window.deleteLater()
    output.deleteLater()
    _pump()


def _cue(i, **extra):
    data = {"cue_id": 9201 + i, "name": f"f{i}", "media_type": "AUDIO", "file_path": f"/m/{i}.mp3"}
    data.update(extra)
    return Cue.from_dict(data)


def test_fade_time_is_the_cues_own_or_the_setting(win):
    QSettings("BlindCue", "BlindCue").remove("live/fade_button_sec")
    assert win.button_fade_seconds(_cue(0, fade_out=2.0)) == 2.0
    assert win.button_fade_seconds(_cue(1)) == 3.0                     # not 0.2 s any more
    QSettings("BlindCue", "BlindCue").setValue("live/fade_button_sec", 5.0)
    assert win.button_fade_seconds(_cue(1)) == 5.0
    assert win.button_fade_seconds(None) == 5.0
    QSettings("BlindCue", "BlindCue").remove("live/fade_button_sec")


def test_a_scene_on_air_has_a_card_and_fades_as_one(win):
    from ui.now_playing import SCENE

    scene = _cue(0, media_type="GROUP", file_path="", group_mode="STEP")
    picture = _cue(1, media_type="IMAGE", file_path="/m/p.png", parent_id=9201, layer=1)
    music = _cue(2, parent_id=9201, layer=2)
    later = _cue(3, parent_id=9201, layer=3, media_type="IMAGE", file_path="/m/q.png")
    after = _cue(4, name="after")
    win._cues = [scene, picture, music, later, after]
    win._refresh_cue_list(keep_selection=False)
    picture.status = music.status = CueStatus.LIVE
    win._live_mode = True
    cards = win._now_playing_cards()
    assert cards[0].kind == SCENE and "f0" in cards[0].title
    win._cue_list.setCurrentRow(3)                                       # GO points at the scene's last step
    faded = []
    win.card_fade_requested.connect(faded.append)
    win.fade_scene(scene.cue_id)
    assert sorted(faded) == sorted({win._runtime_slot(picture), win._runtime_slot(music)})
    assert win._cue_list.currentRow() == 4                               # the next GO is after the scene
    picture.status = music.status = CueStatus.LOADED
    assert all(c.kind != SCENE for c in win._now_playing_cards())        # nothing on air: no scene card
    win._live_mode = False
