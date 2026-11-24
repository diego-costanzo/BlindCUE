"""Stage 2, item 2.7: markers in a media cue and cues that start on a marker."""

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
from models.cue import Cue, MediaType, sanitize_markers
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _cue(i: int, **extra) -> Cue:
    data = {"cue_id": 9981 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_markers_are_sanitized_and_kept():
    raw = [{"id": 2, "name": "chorus", "sec": 30}, {"id": 1, "name": "x", "sec": 5}, {"id": 2, "sec": 1},
           {"id": -1, "sec": 3}, "junk"]
    assert [m["id"] for m in sanitize_markers(raw)] == [1, 2]                 # sorted, no duplicates
    music = _cue(0, markers=raw)
    back = Cue.from_dict(music.to_dict())
    assert [m["sec"] for m in back.markers] == [5.0, 30.0]
    dep = _cue(1, start_rel_cue=9981, start_rel_when="marker", start_rel_marker=2)
    assert Cue.from_dict(dep.to_dict()).start_rel_marker == 2


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        _cue(0, name="song", markers=[{"id": 1, "name": "◆1", "sec": 5.0}]),
        _cue(1, name="title", media_type="IMAGE", start_rel_cue=9981, start_rel_when="marker",
             start_rel_marker=1, start_rel_offset=0.5),
        _cue(2, name="next"),
    ]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[tuple[int, float]] = []
    cancelled: list[int] = []
    win.cue_fired.connect(lambda c: fired.append((c.cue_id, win.take_rel_extra(c.cue_id))))
    win.layer_cancel_start_requested.connect(cancelled.append)
    win.fired, win.cancelled = fired, cancelled
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


def test_start_on_a_marker_and_after_a_seek(window):
    song = window._cues[0]
    window.cue_launched(song, None, 0.0)
    assert window.fired == [(9982, 5.5)]                          # 5 s to the marker + 0.5 s
    window._live_phase_tags[9982] = "PRE -5.5s"                   # it waits
    window.cue_retimed(song, None, 3.0)                           # moved to 3 s: 2 s to the marker
    assert window.cancelled and window.fired[-1] == (9982, 2.5)
    window.fired.clear()
    window.cue_launched(song, None, 6.0)                          # started after the marker
    assert window.fired == []


def test_add_and_protected_delete(window, monkeypatch):
    insp = window._inspector
    window._cue_list.setCurrentRow(0)
    _pump()
    monkeypatch.setattr(window._waveform, "playhead_seconds", lambda: 12.25)
    window._marker_add()
    song = window._cues[0]
    assert [(m["id"], m["sec"]) for m in song.markers] == [(1, 5.0), (2, 12.25)]
    assert insp.combo_markers.count() == 2
    window._marker_delete(1)                                       # "title" starts on it
    assert len(song.markers) == 2 and "#2" in window._status_label.text()
    window._marker_delete(2)
    assert [m["id"] for m in song.markers] == [1]


def test_show_list_mark(qt_app):
    from ui.live_show_view import relative_mark

    dep = _cue(1, start_rel_cue=9981, start_rel_when="marker", start_rel_marker=3, start_rel_offset=1)
    assert relative_mark(dep, {9981: 0}) == "⏱ #1 ◆3+1s"


def test_review_pause_holds_and_end_sections_stop_marker_starts(window):
    song = window._cues[0]
    window.cue_launched(song, None, 0.0)
    window._live_phase_tags[9982] = "PRE -5.5s"
    window.cue_paused(song)                                        # paused at 1 s: the start waits
    assert window.cancelled and 9982 in window._rel_held
    window._live_phase_tags.pop(9982)
    window.fired.clear()
    window.cue_resumed(song, None, 1.0)
    assert window.fired == [(9982, 4.5)] and not window._rel_held   # timed again from 1 s
    window.fired.clear()
    window.cue_launched(song, 3.0, 0.0)                             # plays 3 s only: the marker at 5 s never comes
    assert window.fired == []
    from models.cue import CueSection

    song.sections = [CueSection("A", 0.0, 10.0, loops=2)]
    window.cue_launched(song, None, 0.0)                            # repeated / skipped parts: no file-time wait
    assert window.fired == []
    song.sections = []


def test_review_ctrl_k_in_the_rehearsal_marks_the_cue_that_plays(window, monkeypatch):
    from models.cue import CueStatus

    song, nxt = window._cues[0], window._cues[2]
    window.set_live_mode(True)
    song.status = CueStatus.LIVE
    window._fired_at[song.cue_id] = 5
    window._cue_list.setCurrentRow(2)                               # GO already points at "next"
    monkeypatch.setattr(window, "_change_allowed", lambda _p: True)
    monkeypatch.setattr(window._live_clocks, "layer_position", lambda _slot: 7.5)
    window._marker_add()
    assert [m["sec"] for m in song.markers] == [5.0, 7.5] and nxt.markers == []
