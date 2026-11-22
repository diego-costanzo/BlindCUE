"""Output and director windows after a display change (2026-11-22).

Windows "Second screen only" (or a laptop with its lid closed) leaves the
projector as the only, primary screen. The output window kept its full-screen,
always-on-top projector setup on it and Windows 11 minimised the director:
nothing could be clicked. These tests replay the decisions offscreen; the
real-screen check is tests/test_screen_switch.py and a manual Win+P run.
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

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import ui.output_window as output_module  # noqa: E402
from ui.output_window import OutputWindow  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def test_projector_that_becomes_primary_turns_into_the_preview(qt_app):
    """Same QScreen, but now it is the primary one: reconfigure as a preview."""
    primary = qt_app.primaryScreen()
    win = OutputWindow()
    calls: list[tuple[object, bool]] = []
    win.configure_screen = lambda screen, is_external=True: calls.append((screen, is_external))
    try:
        win._target_screen = primary
        win._is_external = True          # it was the projector until now
        win.set_target_screen(primary)
        assert calls == [(primary, False)]

        calls.clear()
        win._is_external = False         # already the preview: nothing to do
        win.set_target_screen(primary)
        assert calls == []
    finally:
        win.force_close()


def test_going_full_screen_stops_when_the_screen_changed_meanwhile(qt_app, monkeypatch):
    """processEvents() inside _show_fullscreen_on() can run a monitor change
    that re-targets the window (or deletes the screen): the newer setup wins."""
    primary = qt_app.primaryScreen()
    win = OutputWindow()
    shown: list[bool] = []
    win.showFullScreen = lambda: shown.append(True)
    try:
        class _Retarget:
            @staticmethod
            def processEvents(*_a, **_k):
                win._target_screen = None   # what a nested reconfiguration does

        monkeypatch.setattr(output_module, "QCoreApplication", _Retarget)
        win._target_screen = primary
        win._show_fullscreen_on(primary)
        assert shown == []

        class _Quiet:
            @staticmethod
            def processEvents(*_a, **_k):
                pass

        monkeypatch.setattr(output_module, "QCoreApplication", _Quiet)
        win._target_screen = primary
        win._show_fullscreen_on(primary)
        assert shown == [True]
    finally:
        win.force_close()


def test_output_moved_off_its_screen_by_the_system_is_placed_again(qt_app):
    """Windows restores window positions a moment after a display change and
    once moved the output onto the laptop, full screen over the director."""
    primary = qt_app.primaryScreen()
    win = OutputWindow()
    calls: list[tuple[object, bool]] = []
    try:
        win.configure_screen(primary, is_external=False)
        _pump(0.2)
        win.configure_screen = lambda screen, is_external=True: calls.append((screen, is_external))

        win.ensure_on_target_screen()          # where it belongs: nothing to do
        assert calls == []

        geo = primary.geometry()
        win.move(geo.right() + 500, geo.bottom() + 500)   # pushed off its screen
        _pump(0.2)
        win.ensure_on_target_screen()
        assert calls == [(primary, False)]
    finally:
        win.force_close()


def test_director_comes_back_after_a_display_change(qt_app, monkeypatch):
    from ui.main_window import MainWindow

    output = OutputWindow()
    win = MainWindow(output)
    rebound: list[bool] = []
    real_bind = win.bind_to_primary_screen

    def _bind(screen=None):
        rebound.append(True)
        real_bind(screen)

    monkeypatch.setattr(win, "bind_to_primary_screen", _bind)
    try:
        win.bind_to_primary_screen()
        win.show()
        _pump(0.2)
        rebound.clear()

        # Visible, on screen, output only a preview window: leave it alone.
        win._ensure_director_visible()
        assert rebound == []

        # Minimised by Windows when its monitor went away: bring it back.
        win.setWindowState(win.windowState() | Qt.WindowState.WindowMinimized)
        _pump(0.2)
        win._ensure_director_visible()
        _pump(0.2)
        assert rebound == [True]
        assert not win.isMinimized()

        # Under a full-screen, always-on-top output: move it to the primary screen.
        rebound.clear()
        output.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                              | Qt.WindowType.Window)
        output.setGeometry(win.frameGeometry().adjusted(-10, -10, 10, 10))
        output.show()
        _pump(0.2)
        win._ensure_director_visible()
        assert rebound == [True]
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        _pump(0.1)
