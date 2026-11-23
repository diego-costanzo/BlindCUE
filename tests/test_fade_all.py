"""Fade All (Shift+Esc) and the standby position after a stop.

Headless MainWindow; the engine side (``fade_all_requested`` → players) is
checked by the signal payload, the cursor by the cue list.
"""

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
from PySide6.QtCore import QCoreApplication, QSettings
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


@pytest.fixture()
def window(qt_app):
    from models.cue import Cue, MediaType
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
    win._cues = [
        Cue.from_dict({"cue_id": 9101 + i, "name": f"c{i}",
                       "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(4)
    ]
    win._refresh_cue_list()
    emitted: list[float] = []
    win.fade_all_requested.connect(emitted.append)
    win._emitted = emitted
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


def _set_live(win, *rows: int) -> None:
    from models.cue import CueStatus

    for r in rows:
        win._cues[r].status = CueStatus.LIVE


def test_fade_all_emits_duration_from_settings(window):
    from ui.main_window._transport import FADE_ALL_SETTINGS_KEY

    settings = QSettings("BlindCue", "BlindCue")
    try:
        settings.setValue(FADE_ALL_SETTINGS_KEY, 2.5)
        window._on_fade_all()
    finally:
        settings.remove(FADE_ALL_SETTINGS_KEY)
    assert window._emitted == [2.5]


def test_fade_all_default_is_one_second(window):
    window._on_fade_all()
    assert window._emitted == [1.0]


def test_fade_all_puts_standby_on_first_stopped_cue(window):
    from models.cue import CueStatus

    _set_live(window, 1, 2)
    window._cue_list.setCurrentRow(3)
    window._on_fade_all()
    assert window._cue_list.currentRow() == 1
    assert window._current_index == 1
    assert all(c.status != CueStatus.LIVE for c in window._cues)


def test_panic_puts_standby_on_first_stopped_cue(window):
    _set_live(window, 2)
    window._cue_list.setCurrentRow(3)
    window._on_panic()
    assert window._cue_list.currentRow() == 2


def test_cue_waiting_in_delay_counts_as_stopped(window):
    window._live_phase_tags[window._cues[0].cue_id] = "PRE"
    _set_live(window, 2)
    window._cue_list.setCurrentRow(3)
    window._on_fade_all()
    assert window._cue_list.currentRow() == 0


def test_nothing_running_keeps_standby(window):
    window._cue_list.setCurrentRow(3)
    window._on_fade_all()
    assert window._cue_list.currentRow() == 3
