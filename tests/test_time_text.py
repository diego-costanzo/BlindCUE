"""Stage 2, item 2.9: one way to type a time in every seconds field."""

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
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication
from ui.time_text import could_become_time, parse_seconds


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("text,seconds", [
    ("83.5", 83.5), ("83,5", 83.5), ("1:23.5", 83.5), ("1:23,5", 83.5), ("01:02:03", 3723.0),
    ("1m23s", 83.0), ("1m 23,5s", 83.5), ("2m", 120.0), ("45s", 45.0), ("1h2m", 3720.0),
    ("-10", -10.0), ("0:05", 5.0), ("90", 90.0), (".8", 0.8), ("2.1.7", 121.7), ("1.02.03.5", 3723.5),
    ("83.", 83.0),
])
def test_parse(text, seconds):
    assert parse_seconds(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", ["", "a", "1:60", "1.5:2", "1:2:3:4", "1x", "1.60.0", ".", "m"])
def test_not_a_time(text):
    assert parse_seconds(text) is None


def test_partial_input():
    assert could_become_time("1:") and could_become_time("1m") and not could_become_time("abc")


def test_seconds_fields_take_every_form(qt_app):
    from ui.spinboxes import SmartDoubleSpinBox

    box = SmartDoubleSpinBox()
    box.setRange(0.0, 3600.0)
    box.setDecimals(2)
    box.setSuffix(" s")
    assert box.valueFromText("1:23.5 s") == pytest.approx(83.5)
    assert box.valueFromText("1m30s") == pytest.approx(90.0)
    assert box.validate("1:", 2)[0] == QValidator.State.Intermediate
    assert box.validate("2:30 s", 4)[0] == QValidator.State.Acceptable
    assert box.validate("abc", 3)[0] == QValidator.State.Invalid
    db = SmartDoubleSpinBox()                                   # not a seconds field: as before
    db.setRange(-60.0, 20.0)
    db.setSuffix(" dB")
    assert db.valueFromText("-12,5 dB") == pytest.approx(-12.5)
    assert db.validate("1:20", 4)[0] == QValidator.State.Invalid


def test_click_into_a_time_field_selects_it_so_typing_replaces_the_value():
    """Evaluation 2026-11-24: typing 10 into "0.00 s" gave 0.10 s, "1:00" over "end of file" was refused."""
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui.spinboxes import InPointSpinBox, OutPointSpinBox

    QApplication.instance() or QApplication([])
    for box, typed, expected in ((InPointSpinBox(), "10", 10.0), (OutPointSpinBox(), "1:00", 60.0)):
        box.setRange(0.0, 999.0)
        box.show()
        box.activateWindow()
        box.setFocus(Qt.FocusReason.MouseFocusReason)
        QApplication.sendEvent(box, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        assert box.lineEdit().selectedText() in (box.lineEdit().text(), box.cleanText())   # the number, not the unit
        QTest.keyClicks(box.lineEdit(), typed)
        QTest.keyClick(box.lineEdit(), Qt.Key.Key_Return)
        assert box.value() == expected
        box.close()
