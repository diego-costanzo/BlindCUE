"""The mouse wheel scrolls a panel and never changes an unfocused list / number / slider in it."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QScrollArea, QVBoxLayout, QWidget


def _wheel(widget, down=True):
    centre = QPointF(widget.rect().center())
    event = QWheelEvent(centre, QPointF(widget.mapToGlobal(centre.toPoint())), QPoint(0, 0),
                        QPoint(0, -120 if down else 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


def test_unfocused_controls_in_a_panel_keep_their_value_and_the_panel_scrolls():
    QApplication.instance() or QApplication([])
    from ui import wheel_guard

    wheel_guard.install()
    area = QScrollArea()
    inner = QWidget()
    lay = QVBoxLayout(inner)
    combo = QComboBox()
    combo.addItems(["native", "16:9", "4:3"])
    spin = QDoubleSpinBox()
    spin.setRange(0, 100)
    lay.addWidget(combo)
    lay.addWidget(spin)
    for _ in range(30):
        lay.addWidget(QComboBox())
    area.setWidget(inner)
    area.resize(200, 150)
    area.show()
    QApplication.processEvents()
    combo.clearFocus()
    spin.clearFocus()
    QApplication.processEvents()
    _wheel(combo)
    _wheel(spin.lineEdit() or spin)
    assert combo.currentIndex() == 0 and spin.value() == 0.0
    assert area.verticalScrollBar().value() > 0              # the panel scrolled instead
    spin.setFocus()
    QApplication.processEvents()
    if spin.hasFocus():                                      # offscreen may not give focus to a hidden window
        _wheel(spin, down=False)
        assert spin.value() != 0.0                           # with the focus the wheel still works
    area.close()


def test_controls_outside_a_scrolling_panel_keep_the_wheel():
    QApplication.instance() or QApplication([])
    from ui import wheel_guard

    wheel_guard.install()
    combo = QComboBox()
    combo.addItems(["a", "b", "c"])
    combo.show()
    QApplication.processEvents()
    _wheel(combo)
    assert combo.currentIndex() == 1
    combo.close()
