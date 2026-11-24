"""Accessibility W29: the safety holds last 1.5 s by default; each computer may set 0.6-3 s."""

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

import i18n  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ui.hold_button import (  # noqa: E402
    HOLD_SETTING,
    HoldProgressButton,
    hold_seconds,
    hold_text,
    scaled_hold_ms,
    seconds_text,
    set_hold_seconds,
)


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def default_hold():
    QSettings("BlindCue", "BlindCue").remove(HOLD_SETTING)
    yield
    QSettings("BlindCue", "BlindCue").remove(HOLD_SETTING)


def _pump(seconds: float = 0.05) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def _press_enter(btn: HoldProgressButton) -> int:
    btn.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    held = btn._current_hold_ms
    btn.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    return held


def test_setting_is_clamped_and_scales_the_holds():
    assert hold_seconds() == 1.5 and scaled_hold_ms(1500) == 1500 and hold_text() == "1,5 s"
    assert set_hold_seconds(3.0) == 3.0 and scaled_hold_ms(1500) == 3000 and scaled_hold_ms(1200) == 2400
    assert set_hold_seconds(10) == 3.0 and set_hold_seconds(0.1) == 0.6 and hold_text() == "0,6 s"
    QSettings("BlindCue", "BlindCue").setValue(HOLD_SETTING, "nonsense")
    assert hold_seconds() == 1.5                                     # a damaged value: the default
    assert seconds_text(2.0) == "2 s" and seconds_text(0.6) == "0,6 s"
    i18n.set_language("en")
    try:
        assert seconds_text(1.5) == "1.5 s"
    finally:
        i18n.set_language("it")


def test_scaled_buttons_follow_the_setting_others_do_not(qt_app):
    scaled = HoldProgressButton("x", hold_ms=1500, is_toggle=False, scaled=True)
    plain = HoldProgressButton("y", hold_ms=1500, is_toggle=False)
    set_hold_seconds(0.6)
    assert _press_enter(scaled) == 600 and _press_enter(plain) == 1500
    set_hold_seconds(3.0)
    assert _press_enter(scaled) == 3000                              # read at every press, no restart
    scaled.set_hold_ms(200, scaled=False)                            # the rehearsal: at once, always
    assert _press_enter(scaled) == 200
    scaled.set_hold_ms(1500, scaled=True)
    assert _press_enter(scaled) == 3000


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


def test_show_menu_sets_the_hold_time(window):
    acts = {a.data(): a for a in window._hold_group.actions()}
    assert set(acts) == {0.6, 1.0, 1.5, 2.0, 3.0} and acts[1.5].isChecked()
    acts[3.0].trigger()
    assert hold_seconds() == 3.0 and acts[3.0].isChecked()
    for tabs in (window._mode_tabs, window._live_show_panel.mode_tabs):
        assert "3 s" in tabs.tab_prep_hold.toolTip() and "3 s" in tabs.tab_reh_hold.accessibleName()
    window._hold_longer()
    assert "(3 s)" in window._status_label.text()
    window.set_live_mode(True)
    acts[0.6].trigger()                                              # not during the show
    assert hold_seconds() == 3.0 and acts[3.0].isChecked()
    window._explain_how_to_leave()
    assert "3 s" in window._status_label.text()
