"""C2a side items: earcons by rhythm (W39, W42), hold from the keyboard (W29, W30), contrast (W23)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from engine.earcon import EARCON_NOTES, EarconManager, earcon_duration_ms
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_earcons_differ_in_rhythm_and_stay_short():
    counts = {name: len(notes) for name, (notes, _gap) in EARCON_NOTES.items()}
    assert counts["go"] == 2 and counts["alert"] == 2 and counts["undo"] == 2
    assert counts["enter_show"] == 3 and counts["exit_show"] == 3 and counts["stop"] == 1
    go, undo = EARCON_NOTES["go"][0], EARCON_NOTES["undo"][0]
    assert go[0][0] < go[1][0] and undo[0][0] > undo[1][0]          # up vs down
    alert = EARCON_NOTES["alert"][0]
    assert alert[0][0] == alert[1][0]                              # two equal
    assert all(80 <= earcon_duration_ms(n) <= 300 for n in EARCON_NOTES)


def test_earcons_never_on_the_audience_speakers(qt_app):
    mgr = EarconManager()
    mgr.enabled = True
    played: list = []
    for name, sound in mgr._sounds.items():
        sound.play = lambda n=name: played.append(n)
    mgr.play_go()                       # headphones = default = audience speakers: quiet
    assert mgr.on_audience_speakers() and played == []


def test_hold_by_enter_and_hold_longer(qt_app):
    from ui.hold_button import HoldProgressButton

    btn = HoldProgressButton("x", hold_ms=1500, is_toggle=False)
    early: list = []
    btn.released_early.connect(lambda: early.append(1))
    btn.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert btn._is_pressed
    btn.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
                                "", True))  # auto-repeat changes nothing
    btn.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert not btn._is_pressed and early == [1]


def _contrast(a: str, b: str) -> float:
    def lum(c: str) -> float:
        q = QColor(c)
        return 0.2126 * q.redF() ** 2.2 + 0.7152 * q.greenF() ** 2.2 + 0.0722 * q.blueF() ** 2.2
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_media_badges_read_at_4_5(qt_app):
    from ui.live_show_view import LiveCueRowDelegate

    for _tag, bg, fg in LiveCueRowDelegate._MEDIA_BADGE.values():
        assert _contrast(bg.name(), fg.name()) >= 4.5, (bg.name(), fg.name())
