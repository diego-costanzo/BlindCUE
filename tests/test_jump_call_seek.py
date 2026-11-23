"""Stage 2, item 2.2: jump, call and seek actions; call-only cues."""

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
from engine.action_cues import describe_action
from engine.show_engine import outside_go_order
from models.cue import Cue, MediaType, action_names_one_cue, action_needs_target, sanitize_action_spec
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
    data = {"cue_id": 9601 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def _action(i: int, **spec) -> Cue:
    return _cue(i, media_type="ACTION", file_path="", action_spec=spec)


def test_model_rules():
    spec = sanitize_action_spec({"kind": "goto", "cue_ids": [5]})
    assert spec["goto_play"] is True and spec["goto_max"] == 0 and spec["seek_mode"] == "relative"
    assert sanitize_action_spec({"kind": "seek", "seek_mode": "warp"})["seek_mode"] == "relative"
    assert action_names_one_cue("goto") and action_names_one_cue("call") and not action_names_one_cue("seek")
    assert not action_needs_target("goto") and action_needs_target("seek")
    assert outside_go_order(_cue(0, call_only=True)) and not outside_go_order(_cue(0))
    assert Cue.from_dict(_cue(0, call_only=True).to_dict()).call_only
    assert describe_action({"kind": "seek", "seek_mode": "relative", "seek_sec": -10}).startswith("Sposta di -10.0 s")
    from engine.action_cues import target_layers

    music, picture = _cue(0), _cue(1, media_type="IMAGE")
    spec = {"kind": "seek", "target": "all"}
    assert target_layers(spec, [music, picture], {2: music, 1: picture}) == [2]   # only what plays moves


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        _cue(0, name="intro"),                                                  # row 0
        _action(1, kind="goto", cue_ids=[9604], goto_max=2),                     # row 1: jump to "song"
        _cue(2, name="skipped"),                                                # row 2
        _cue(3, name="song"),                                                   # row 3
        _cue(4, name="sting", call_only=True),                                  # row 4: only by a call
        _action(5, kind="call", cue_ids=[9605]),                                # row 5
        _cue(6, name="last"),                                                   # row 6
    ]
    win._refresh_cue_list(keep_selection=False)
    win._cue_list.setCurrentRow(0)
    fired: list[int] = []
    win.cue_fired.connect(lambda c: fired.append(c.cue_id))
    win.fired = fired
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


def test_jump_starts_the_cue_at_most_n_times(window):
    jump = window._cues[1]
    for _ in range(3):
        window.action_jump(jump)
        _pump()
    assert window.fired == [9604, 9604]                     # max 2, the third did nothing
    assert window._cue_list.currentRow() == 5               # GO goes on after "song" (call-only skipped)


def test_jump_only_as_next_go(window):
    jump = window._cues[1]
    jump.action_spec = sanitize_action_spec({**jump.action_spec, "goto_play": False})
    window.action_jump(jump)
    _pump()
    assert window.fired == [] and window._cue_list.currentRow() == 3


def test_call_keeps_the_pointer_and_go_skips_call_only(window):
    window._cue_list.setCurrentRow(3)
    window.action_jump(window._cues[5])
    _pump()
    assert window.fired == [9605] and window._cue_list.currentRow() == 3
    window._on_go()                                         # "song"
    assert window.fired[-1] == 9604 and window._cue_list.currentRow() == 5   # past "sting"


def test_editor_and_inspector(window):
    from ui.action_cue_editor import ActionCueEditor

    editor = ActionCueEditor()
    editor.set_catalog_provider(lambda: window._cues)
    editor.load({"kind": "goto", "cue_ids": [9604], "goto_play": False, "goto_max": 3}, cue_id=9602)
    assert editor.combo_goal.currentData() == 9604 and editor.lbl_goal.isVisibleTo(editor)
    spec = editor.spec()
    assert spec["cue_ids"] == [9604] and spec["goto_play"] is False and spec["goto_max"] == 3
    editor.load({"kind": "seek", "target": "cues", "cue_ids": [9604], "seek_mode": "before_end", "seek_sec": 5})
    assert editor.spec()["seek_mode"] == "before_end" and editor.lbl_cues.isVisibleTo(editor)
    assert not editor.lbl_goal.isVisibleTo(editor)
    window._cue_list.setCurrentRow(4)                       # "sting": called from row 6
    _pump()
    insp = window._inspector
    insp.set_lite(False)
    assert insp.chk_call_only.isChecked() and "#6" in insp.lbl_callers.text()


def test_review_jump_back_brings_go_back(window):
    back = _action(7, kind="goto", cue_ids=[9601])                # from the end back to "intro"
    window._cues.append(back)
    window._refresh_cue_list(keep_selection=False)
    window._cue_list.setCurrentRow(len(window._cues) - 1)
    window.action_jump(back)
    _pump()
    assert window.fired == [9601] and window._cue_list.currentRow() == 1   # GO goes on after "intro"
