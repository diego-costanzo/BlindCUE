"""Stage 3, item 3.4: a cue without a file yet (the script before the effects are recorded)."""

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
from engine.list_check import PLACEHOLDER, list_problems
from models.cue import Cue, CueStatus, FollowMode, MediaType, is_placeholder
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


def test_placeholder_model_save_and_load(tmp_path):
    from models.project_manager import ProjectManager

    hole = Cue(name="Thunder", media_type=MediaType.AUDIO, file_path="")
    text = Cue(name="caption", media_type=MediaType.IMAGE, file_path="", text_spec={"text": "x"})
    assert is_placeholder(hole) and not is_placeholder(text)
    assert hole.validate() == []                                   # it may be added to the list
    back = Cue.from_dict(hole.to_dict(), project_root=tmp_path)
    assert back.file_path == ""                                    # never "the show folder"
    pm = ProjectManager(autosave_dir=tmp_path / "auto")
    show = tmp_path / "show.blindcue"
    assert pm.save_project(show, [hole])
    cues, _idx, _settings = pm.load_project(show)
    assert cues[0].file_path == "" and cues[0].status == CueStatus.LOADED
    assert list_problems(cues) == [(0, PLACEHOLDER)]


@pytest.fixture()
def window(qt_app, tmp_path):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._clock_timer.stop()
    sound = tmp_path / "rain.wav"
    sound.write_bytes(b"RIFF")
    win.sound = str(sound)
    win.fired = []
    win.cue_fired.connect(lambda c: win.fired.append(c.cue_id))
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


def test_go_on_a_placeholder_plays_nothing_and_goes_on(window):
    window._on_add_placeholder()
    hole = window._cues[0]
    assert is_placeholder(hole) and hole.layer == 2
    window._add_cue_from_file(window.sound)
    after = window._cues[1]
    window._cue_list.setCurrentRow(0)
    label, warn = window._go_label()
    assert "🕳" in label and warn
    window._on_go()
    assert window.fired == []                                      # nothing reaches the players
    assert hole.cue_id in window._played_ids and hole.status != CueStatus.LIVE
    assert window._cue_list.currentRow() == 1                      # the next GO is the next cue
    _pump(0.05)
    assert hole.name in window._status_label.text()
    window._last_go_at = None
    window._on_go()
    assert window.fired == [after.cue_id]


def test_auto_go_after_a_placeholder_still_starts_the_next_cue(window):
    window._on_add_placeholder()
    window._cues[0].follow_mode = FollowMode.AUTO_FOLLOW.value
    window._add_cue_from_file(window.sound)
    window._cue_list.setCurrentRow(0)
    window._on_go()
    _pump(0.3)
    assert window.fired == [window._cues[1].cue_id]


def test_readiness_lists_it_but_not_as_a_missing_file(window):
    window._on_add_placeholder()
    facts = window._readiness_facts()
    assert facts.missing == () and len(facts.list_problems) == 1
    assert window._cues[0].name in facts.list_problems[0]
    row = window._readiness_view(next(c for c in window._readiness_rows() if c.key == "list"))
    assert "1" in row.text
