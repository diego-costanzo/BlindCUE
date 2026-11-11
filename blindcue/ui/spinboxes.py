"""Precision decimal spinboxes resilient to locale separators, suffixes, and crisp +/- buttons."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QLocale, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QStyle, QStyleOptionSpinBox, QWidget

from ui.theme import CLR_ACCENT


class SmartDoubleSpinBox(QDoubleSpinBox):
    """Robust QDoubleSpinBox accepting both '.' and ',' decimal separators,
    resilient to suffixes (% / px / s), deferred tracking, and crisp vector '+' / '-' buttons.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setKeyboardTracking(False)

    def _strip_affixes(self, text: str) -> str:
        clean = text.replace(",", ".")
        prefix = self.prefix()
        suffix = self.suffix()
        if prefix and clean.startswith(prefix):
            clean = clean[len(prefix):]
        if suffix and clean.endswith(suffix):
            clean = clean[:-len(suffix)]
        return clean.strip()

    def validate(self, input_text: str, pos: int):  # noqa: N802
        clean_text = input_text.replace(",", ".")
        special = self.specialValueText()
        if special and (input_text == special or clean_text == special):
            return (QValidator.State.Acceptable, input_text, pos)

        val_str = self._strip_affixes(input_text)
        if not val_str or val_str in ("-", "+", "."):
            return (QValidator.State.Intermediate, input_text, pos)
        try:
            val = float(val_str)
            if self.minimum() <= val <= self.maximum():
                return (QValidator.State.Acceptable, input_text, pos)
            return (QValidator.State.Intermediate, input_text, pos)
        except ValueError:
            return (QValidator.State.Invalid, input_text, pos)

    def valueFromText(self, text: str) -> float:  # noqa: N802
        special = self.specialValueText()
        if special and text == special:
            return self.minimum()
        try:
            return float(self._strip_affixes(text))
        except ValueError:
            return self.minimum()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Paint default widget then draw crisp '+' and '-' glyphs on spin buttons."""
        super().paintEvent(event)

        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        style = self.style()
        up_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxUp, self
        )
        down_rect = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxDown, self
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        enabled = self.isEnabled()
        hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        base_color = QColor("#475569") if not enabled else (
            QColor(CLR_ACCENT) if hovered else QColor("#cbd5e1")
        )
        pen = QPen(base_color, 1.4)
        painter.setPen(pen)

        # Draw '+' in top button
        if up_rect.isValid() and up_rect.width() >= 8:
            c_up = up_rect.center()
            arm = 3.0
            painter.drawLine(QPointF(c_up.x() - arm, c_up.y()), QPointF(c_up.x() + arm, c_up.y()))
            painter.drawLine(QPointF(c_up.x(), c_up.y() - arm), QPointF(c_up.x(), c_up.y() + arm))

        # Draw '-' in bottom button
        if down_rect.isValid() and down_rect.width() >= 8:
            c_dn = down_rect.center()
            arm = 3.0
            painter.drawLine(QPointF(c_dn.x() - arm, c_dn.y()), QPointF(c_dn.x() + arm, c_dn.y()))

        painter.end()


class InPointSpinBox(SmartDoubleSpinBox):
    """High-precision (centesimi) spinbox for Cue IN point."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")


class OutPointSpinBox(SmartDoubleSpinBox):
    """Smart Out Point SpinBox with centesimi precision and end-of-file down-stepping."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")
        self.setSpecialValueText("Fine File")
        self._media_duration: float = 0.0

    def set_media_duration(self, duration_sec: float) -> None:
        self._media_duration = max(0.0, duration_sec)

    def stepBy(self, steps: int) -> None:  # noqa: N802
        cur = self.value()
        if cur == 0.0 and steps < 0 and self._media_duration > 0:
            target = max(0.05, self._media_duration + (steps * self.singleStep()))
            self.setValue(round(target, 2))
            return
        if cur == 0.0 and steps > 0 and self._media_duration > 0:
            return
        super().stepBy(steps)
