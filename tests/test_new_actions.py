"""Stage 2, item 2.11: wait, pause / resume chosen cues, stopwatch."""

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
from engine.action_cues import action_duration, describe_action, target_layers
from models.cue import Cue, MediaType, action_needs_target, sanitize_action_spec
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
    data = {"cue_id": 9701 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_model_rules():
    wait = sanitize_action_spec({"kind": "wait", "duration": 4})
    assert wait["kind"] == "wait" and action_duration(wait) == 4.0 and not action_needs_target("wait")
    assert describe_action(wait).startswith("Attendi 4")
    assert sanitize_action_spec({"kind": "stopwatch"})["sw_mode"] == "start"
    assert sanitize_action_spec({"kind": "stopwatch", "sw_mode": "explode"})["sw_mode"] == "start"
    assert not action_needs_target("stopwatch") and action_duration({"kind": "stopwatch"}) == 0.0
    assert action_needs_target("pause") and action_needs_target("resume")
    music, video, picture = _cue(0), _cue(1, media_type="VIDEO"), _cue(2, media_type="IMAGE")
    live = {2: music, 1: video, 3: picture}
    for kind in ("pause", "resume"):
        assert target_layers({"kind": kind, "target": "all"}, [music, video, picture], live) == [1, 2]
        assert target_layers({"kind": kind, "target": "cues", "cue_ids": [music.cue_id]},
                             [music, video, picture], live) == [2]
    assert describe_action({"kind": "pause", "target": "cues", "cue_ids": [music.cue_id]}, [music]).startswith("Pausa")
    sleep = {"kind": "pause", "target": "all", "sleep_sec": 4}           # 3.3: music goes to sleep
    assert describe_action(sleep).startswith("Addormenta in 4.0 s") and action_duration(sleep) == 4.0
    old = {"kind": "pause", "target": "all", "duration": 3.0}            # saved by 2.11: still an instant pause
    assert describe_action(old).startswith("Pausa") and action_duration(old) == 0.0
    assert sanitize_action_spec({"kind": "resume"})["sleep_sec"] == 0.0
    for kind in ("wait", "pause", "resume", "stopwatch"):
        cue = Cue.from_dict({"cue_id": 1, "name": "a", "media_type": "ACTION", "file_path": "",
                             "action_spec": {"kind": kind}})
        assert Cue.from_dict(cue.to_dict()).action_spec["kind"] == kind


def test_stopwatch_in_the_window(qt_app, monkeypatch):
    from ui.main_window import MainWindow
    from ui.main_window import _countdown
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    clock = [1000.0]
    monkeypatch.setattr(_countdown.time, "monotonic", lambda: clock[0])
    try:
        assert win.stopwatch_seconds() == 0.0 and not win._lbl_stopwatch.isVisibleTo(win.statusBar())
        win.stopwatch("start")
        clock[0] += 75.0
        assert win.stopwatch_seconds() == pytest.approx(75.0)
        win._sw_tick()
        assert "01:15" in win._lbl_stopwatch.text() and win._lbl_stopwatch.isVisibleTo(win.statusBar())
        win.stopwatch("stop")
        clock[0] += 30.0
        assert win.stopwatch_seconds() == pytest.approx(75.0)      # stopped: it holds
        win.stopwatch("start")
        clock[0] += 5.0
        assert win.stopwatch_seconds() == pytest.approx(80.0)      # goes on from where it stopped
        win.stopwatch("reset")
        clock[0] += 2.0
        assert win.stopwatch_seconds() == pytest.approx(2.0)       # reset while running: from zero, still running
        win.stopwatch("stop")
        win.stopwatch("reset")
        assert win.stopwatch_seconds() == 0.0
    finally:
        monkeypatch.undo()          # time.monotonic is the real module's: _pump needs it back
        win._force_closing = True
        output.force_close()
        win.close()
        _pump()
        win.deleteLater()
        output.deleteLater()
        _pump()


def test_editor_shows_the_right_fields(qt_app):
    from ui.action_cue_editor import ActionCueEditor

    editor = ActionCueEditor()
    editor.load({"kind": "wait", "duration": 7})
    assert editor.spec()["kind"] == "wait" and editor.spec()["duration"] == 7.0
    assert editor.spin_duration.isVisibleTo(editor) and not editor.combo_target.isVisibleTo(editor)
    editor.load({"kind": "stopwatch", "sw_mode": "reset"})
    assert editor.spec()["sw_mode"] == "reset" and editor.combo_sw.isVisibleTo(editor)
    editor.load({"kind": "pause", "target": "all"})
    assert editor.combo_target.isVisibleTo(editor) and editor.spin_sleep.isVisibleTo(editor)  # sleep fade
    assert not editor.spin_duration.isVisibleTo(editor)
