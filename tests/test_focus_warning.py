"""LIVE mode warns when the keyboard is not on the director window.

Offscreen windows are never "active", so the active-window lookup is
replaced per test.
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
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog


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
    from ui.main_window import MainWindow
    from ui.output_window import OutputWindow

    output = OutputWindow()
    win = MainWindow(output)
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


def _active(monkeypatch, widget) -> None:
    monkeypatch.setattr(QApplication, "activeWindow", staticmethod(lambda: widget))


def _banner(win) -> bool:
    return not win._live_show_panel.lbl_focus_warning.isHidden()


def test_banner_shown_in_live_when_another_window_is_active(window, monkeypatch):
    _active(monkeypatch, None)
    window.set_live_mode(True)
    assert _banner(window)


def test_no_banner_when_director_is_active(window, monkeypatch):
    _active(monkeypatch, window)
    window.set_live_mode(True)
    assert not _banner(window)


def test_dialog_of_the_director_counts_as_director(window, monkeypatch):
    dialog = QDialog(window)
    _active(monkeypatch, dialog)
    window.set_live_mode(True)
    assert not _banner(window)
    dialog.deleteLater()


def test_no_banner_outside_live(window, monkeypatch):
    _active(monkeypatch, None)
    window._update_focus_warning()
    assert not _banner(window)


def test_banner_clears_when_focus_returns_and_on_leaving_live(window, monkeypatch):
    _active(monkeypatch, None)
    window.set_live_mode(True)
    assert _banner(window)
    _active(monkeypatch, window)
    window._update_focus_warning()
    assert not _banner(window)
    _active(monkeypatch, None)
    window._update_focus_warning()
    assert _banner(window)
    window.set_live_mode(False)
    assert not _banner(window)


def test_banner_never_moves_the_page(window, monkeypatch):
    """The banner is an overlay: showing / hiding it keeps every button in place.

    In the layout it pushed the page down while the keyboard was elsewhere; the
    first click that brought the keyboard back hid it, the page jumped up between
    press and release and the click (e.g. "Fade" on a now-playing card) was lost.
    """
    panel = window._live_show_panel
    window.set_live_mode(True)
    _active(monkeypatch, window)
    window._update_focus_warning()
    QApplication.processEvents()
    before = (panel.live_table.geometry(), panel.btn_go.geometry())
    _active(monkeypatch, None)
    window._update_focus_warning()
    QApplication.processEvents()
    assert _banner(window)
    assert (panel.live_table.geometry(), panel.btn_go.geometry()) == before
    assert panel.lbl_focus_warning.geometry().top() >= panel.top_bar.geometry().bottom()


def test_a_mouse_click_never_leaves_the_keyboard_on_a_show_button(window):
    """Accessibility review 2026-11-24: Enter presses the focused button, so PANIC, Fade All, Pause All
    and the other show buttons take the focus only from Tab, never from a mouse click."""
    from PySide6.QtCore import Qt

    panel = window._live_show_panel
    for btn in (panel.btn_panic, panel.btn_fade_all, panel.btn_pause_all, panel.btn_stopwatch,
                panel.btn_stopwatch_reset, panel.btn_back_project, panel.btn_break_loop, panel.btn_layer_lock):
        assert btn.focusPolicy() == Qt.FocusPolicy.TabFocus, btn.text()
