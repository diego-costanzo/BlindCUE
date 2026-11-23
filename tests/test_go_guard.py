"""Double-GO guard: a second GO within the guard window must not fire a cue.

Headless (offscreen) MainWindow; the cue chain itself is replaced by a
counter so the test checks only the guard in front of it.
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
        Cue.from_dict({"cue_id": 9001 + i, "name": f"c{i}",
                       "media_type": MediaType.AUDIO.value,
                       "file_path": f"/nonexistent/c{i}.wav"})
        for i in range(3)
    ]
    fired: list[int] = []
    win._fire_cue_chain = lambda idx: fired.append(idx)  # type: ignore[method-assign]
    win._apply_inspector_to_cue = lambda: None  # type: ignore[method-assign]
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


def test_second_go_within_window_is_ignored(window):
    window._go_guard_ms = 400
    window._on_go()
    window._on_go()
    assert len(window._fired) == 1


def test_go_after_window_fires_again(window):
    window._go_guard_ms = 400
    window._on_go()
    window._last_go_at -= 0.5  # pretend 500 ms passed
    window._on_go()
    assert len(window._fired) == 2


def test_guard_zero_disables_it(window):
    window._go_guard_ms = 0
    window._on_go()
    window._on_go()
    assert len(window._fired) == 2


def test_remote_go_shares_the_guard(window):
    window._go_guard_ms = 400
    window._on_go()
    window._on_remote_go()
    assert len(window._fired) == 1


def test_setting_is_read_and_clamped(qt_app):
    from ui.main_window._transport import GO_GUARD_SETTINGS_KEY, read_go_guard_ms

    settings = QSettings("BlindCue", "BlindCue")
    try:
        settings.setValue(GO_GUARD_SETTINGS_KEY, 250)
        assert read_go_guard_ms() == 250
        settings.setValue(GO_GUARD_SETTINGS_KEY, -5)
        assert read_go_guard_ms() == 0
        settings.setValue(GO_GUARD_SETTINGS_KEY, "nonsense")
        assert read_go_guard_ms() == 400
    finally:
        settings.remove(GO_GUARD_SETTINGS_KEY)
