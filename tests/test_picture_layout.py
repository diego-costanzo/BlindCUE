"""Stage 4: copy / paste the picture layout (4.4), photos to music (4.3)."""

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
from models.cue import Cue, MediaType
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i: int, kind: str = "IMAGE", **extra) -> Cue:
    data = {"cue_id": 9871 + i, "name": f"p{i}", "media_type": kind, "file_path": f"/x/p{i}.jpg"}
    data.update(extra)
    return Cue.from_dict(data)


@pytest.fixture()
def window():
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    win._cues = [_cue(0, position_x=0.25, position_y=-0.1, scale=0.6, rotation=90.0,
                      crop={"x": 0.1, "y": 0.0, "w": 0.8, "h": 1.0}),
                 _cue(1), _cue(2, "VIDEO", file_path="/x/v.mp4"), _cue(3, "AUDIO", file_path="/x/a.wav")]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    win._commit_undo_point()
    _pump()
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_copy_and_paste_the_layout(window):
    window._cue_list.layout_copy_requested.emit()
    window._cue_list.select_rows([1, 2, 3], anchor_row=1)
    window._cue_list.layout_paste_requested.emit()
    photo, video, sound = window._cues[1:]
    for cue in (photo, video):
        assert (cue.position_x, cue.position_y, cue.scale, cue.rotation) == (0.25, -0.1, 0.6, 90.0)
        assert cue.crop["x"] == 0.1
    assert sound.scale == 1.0                                        # a sound has no picture layout
    photo.crop["x"] = 0.5
    assert window._cues[0].crop["x"] == 0.1                          # a copy, not the same dict
    window._on_undo()
    assert window._cues[1].scale == 1.0                              # one Ctrl+Z


def test_photos_to_music(window):
    from ui.main_window._slideshow import slideshow_holds

    assert slideshow_holds(3, 6.0) == 2.0 and slideshow_holds(10, 3.0) == 1.0     # never under a second
    window._cues.insert(2, _cue(9, "AUDIO", file_path="/x/song.mp3", name="song"))
    window._known_file_durations["/x/song.mp3"] = 9.0
    window._refresh_cue_list(keep_selection=False)
    window._commit_undo_point()
    window._cue_list.select_rows([0, 1, 2], anchor_row=0)
    window._cue_list.slideshow_requested.emit()
    song, group, a, b = window._cues[:4]
    assert song.name == "song" and song.follow_mode == "SIMULTANEOUS"
    assert group.media_type == MediaType.GROUP and group.playlist and group.group_mode == "SEQUENCE"
    assert [c.parent_id for c in (a, b)] == [group.cue_id] * 2 and a.hold_time == b.hold_time == 4.5
    assert b.crossfade == 0.0 and a.fade_in == b.fade_out == 0.5         # no crossfade: the layer is cleared first
    assert song.layer == 2 and a.layer == b.layer == 1                       # a picture never stops the music
    window._on_undo()
    assert [c.name for c in window._cues][:3] == ["p0", "p1", "song"]                 # one Ctrl+Z
