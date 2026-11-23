"""Exclusive cue: while it is live a manual GO is refused; Ctrl+Space forces it."""

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


def _cue(i: int, **extra):
    from models.cue import Cue, MediaType

    data = {"cue_id": 9201 + i, "name": f"c{i}", "media_type": MediaType.AUDIO.value,
            "file_path": f"/nonexistent/c{i}.wav"}
    data.update(extra)
    return Cue.from_dict(data)


def test_exclusive_round_trips_and_defaults_off():
    from models.cue import Cue

    assert _cue(0).exclusive is False
    c = _cue(1, exclusive=True)
    assert Cue.from_dict(c.to_dict()).exclusive is True


@pytest.fixture()
def window(qt_app):
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [_cue(0, exclusive=True), _cue(1), _cue(2)]
    fired: list[int] = []
    win._fire_cue_chain = lambda idx: fired.append(idx)  # type: ignore[method-assign]
    win._apply_inspector_to_cue = lambda: None  # type: ignore[method-assign]
    win._is_text_input_focused = lambda: False  # type: ignore[method-assign]
    win._go_guard_ms = 0
    win._fired = fired
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


def _make_live(win, row: int) -> None:
    from models.cue import CueStatus

    win._cues[row].status = CueStatus.LIVE


def test_go_refused_while_exclusive_cue_is_live(window):
    _make_live(window, 0)
    window._on_go()
    window._on_remote_go()
    assert window._fired == []


def test_forced_go_passes_once(window):
    _make_live(window, 0)
    window._on_go_forced()
    assert len(window._fired) == 1
    window._on_go()
    assert len(window._fired) == 1  # the force does not stick


def test_go_allowed_when_exclusive_cue_is_not_live(window):
    window._on_go()
    assert len(window._fired) == 1


def test_non_exclusive_live_cue_does_not_block(window):
    _make_live(window, 1)
    window._on_go()
    assert len(window._fired) == 1


def test_inspector_checkbox_writes_the_field(window):
    cue = window._cues[1]
    window._inspector.load_cue(cue, 1)
    window._inspector.chk_exclusive.setChecked(True)
    window._inspector.apply_to_cue(cue)
    assert cue.exclusive is True
