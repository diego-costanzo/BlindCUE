"""Regression: plugging a projector in while the program runs.

On Windows the output window went full screen on the laptop (director) screen
instead of the projector, covering the director window; the operator could not
close it during a show (2026-11-21). Needs two real screens, so it is skipped
on a single screen and with the offscreen platform.

Run on a machine with a second monitor (no QT_QPA_PLATFORM=offscreen):
    pytest -q tests/test_screen_switch.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _settle(seconds: float = 1.2) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def _two_real_screens(app) -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"
        and app.platformName() != "offscreen"
        and len(app.screens()) >= 2
    )


def test_output_follows_a_projector_plugged_in_later(qt_app) -> None:
    if not _two_real_screens(qt_app):
        pytest.skip("needs two real screens")
    from ui.output_window import OutputWindow

    primary = qt_app.primaryScreen()
    external = next(s for s in qt_app.screens() if s != primary)
    win = OutputWindow()
    try:
        win.configure_screen(primary, is_external=False)      # one monitor at start
        _settle()
        for _ in range(2):                                     # plug, unplug, plug again
            win.set_target_screen(external)
            _settle()
            assert win.screen() == external, "output must go to the projector"
            assert win.isFullScreen()
            assert external.geometry().contains(win.geometry().center())

            win.set_target_screen(primary)
            _settle()
            assert win.screen() == primary
            assert not win.isFullScreen(), "back to the preview window, director stays usable"
    finally:
        win.force_close()
        _settle(0.2)
