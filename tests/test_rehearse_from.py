"""Stage 2, item 2.4: rehearsal from a chosen moment."""

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
from engine.rehearse_from import state_before
from models.cue import Cue, MediaType
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
    data = {"cue_id": 9801 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def _show() -> list[Cue]:
    return [
        _cue(0, name="backdrop", media_type="IMAGE", layer=1),                    # stays (no hold time)
        _cue(1, name="loop", layer=2, loop=True, loop_count=0),                   # stays (endless)
        _cue(2, name="song", layer=3),                                            # plays to its end
        _cue(3, name="down", media_type="ACTION", file_path="",
             action_spec={"kind": "level", "target": "cues", "cue_ids": [9802], "mode": "relative", "db": -12}),
        _cue(4, name="dim", media_type="ACTION", file_path="",
             action_spec={"kind": "opacity", "target": "layer", "layer": 1, "level": 0.4}),
        _cue(5, name="flash", media_type="IMAGE", layer=3, hold_time=2),          # replaced, then gone
        _cue(6, name="scene 2"),
        _cue(7, name="stop all", media_type="ACTION", file_path="", action_spec={"kind": "stop", "target": "all"}),
        _cue(8, name="end"),
    ]


def test_what_stays_before_a_cue():
    cues = _show()
    state = state_before(cues, 6)
    assert {k: s.cue.name for k, s in state.items()} == {("A", 1): "backdrop", ("A", 2): "loop"}
    assert state[("A", 2)].level_db == -12 and state[("A", 1)].opacity == 0.4
    assert state_before(cues, 0) == {} and state_before(cues, 8) == {}     # "stop all" cleared it


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = _show()
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[int] = []
    trims: list[tuple[int, float]] = []
    win.cue_fired.connect(lambda c: fired.append(c.cue_id))
    win.layer_trim_requested.connect(lambda slot, t: trims.append((slot, round(t, 3))))
    win.fired, win.trims = fired, trims
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


def test_rehearse_from_scene_two(window):
    window._rehearse_apply(6, state_before(window._cues, 6))
    assert window.fired == [9801, 9802]                         # the backdrop, then the loop
    assert window.trims == [(2, round(10 ** (-12 / 20), 3))]    # the loop at -12 dB, as on the way
    assert window._cue_list.currentRow() == 6                   # GO: scene 2


def test_not_in_the_show(window):
    window.set_live_mode(True)
    window._rehearse_from(6)
    assert window.fired == [] and "spettacolo" in window._status_label.text()


def test_review_one_cue_alone_without_pre_delay(window):
    window._cues[0].follow_mode = "SIMULTANEOUS"                          # "backdrop" pulls "loop" with it
    window._cues[0].pre_delay = 5.0
    extras = []
    window.cue_fired.connect(lambda c: extras.append(window.take_rel_extra(c.cue_id)))
    window._fire_one_now(0)
    assert window.fired == [9801] and extras == [-5.0]                   # alone, and at once (5 - 5 = 0)
