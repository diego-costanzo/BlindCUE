"""Precision decimal spinboxes resilient to locale separators, suffixes, and crisp +/- buttons."""

from __future__ import annotations


from PySide6.QtCore import QLocale, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QSizePolicy, QStyle, QStyleOptionSpinBox, QWidget

from ui.theme import CLR_ACCENT


class SmartDoubleSpinBox(QDoubleSpinBox):
    """Robust QDoubleSpinBox accepting both '.' and ',' decimal separators,
    resilient to suffixes (% / px / s), deferred tracking, and crisp vector '+' / '-' buttons.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Use the C locale so typed decimals always parse with a dot."""
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setKeyboardTracking(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        le = self.lineEdit()
        if le is not None:
            le.setTextMargins(8, 0, 2, 0)

    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt override
        """A click or Tab into the field selects all of it: what is typed replaces the value.

        Before, a click put the cursor inside "0.00 s": typing 10 gave 0.10 s and
        "1:00" over "end of file" was refused (evaluation 2026-11-24).
        """
        super().focusInEvent(event)
        if event.reason() in (Qt.FocusReason.MouseFocusReason, Qt.FocusReason.TabFocusReason,
                              Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason):
            QTimer.singleShot(0, self.selectAll)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Keep the box narrow: four numeric fields often share one row."""
        sh = super().minimumSizeHint()
        return QSize(min(sh.width(), 76), max(26, sh.height()))

    def _strip_affixes(self, text: str) -> str:
        """Normalise ',' to '.', then remove the configured prefix/suffix."""
        clean = text.replace(",", ".")
        prefix = self.prefix()
        suffix = self.suffix()
        if prefix and clean.startswith(prefix):
            clean = clean[len(prefix):]
        if suffix and clean.endswith(suffix):
            clean = clean[:-len(suffix)]
        return clean.strip()

    def _is_time(self) -> bool:
        """A seconds field (suffix " s"): it also takes 1:23.5, 1m23s, 2m (2.9)."""
        return self.suffix().strip() == "s"

    def validate(self, input_text: str, pos: int):  # noqa: N802
        """Accept both '.' and ',' while typing; reject out-of-range values."""
        clean_text = input_text.replace(",", ".")
        special = self.specialValueText()
        if special and (input_text == special or clean_text == special):
            return (QValidator.State.Acceptable, input_text, pos)

        if self._is_time():
            from ui.time_text import could_become_time, parse_seconds

            body = input_text.removesuffix(self.suffix())
            seconds = parse_seconds(body)
            if seconds is not None:
                ok = self.minimum() <= seconds <= self.maximum()
                return (QValidator.State.Acceptable if ok else QValidator.State.Intermediate, input_text, pos)
            if could_become_time(body):
                return (QValidator.State.Intermediate, input_text, pos)
            return (QValidator.State.Invalid, input_text, pos)

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
        """Parse the edited text, falling back to the minimum on invalid input."""
        special = self.specialValueText()
        if special and text == special:
            return self.minimum()
        if self._is_time():
            from ui.time_text import parse_seconds

            body = text.removesuffix(self.suffix())
            seconds = parse_seconds(body)
            return self.minimum() if seconds is None else max(self.minimum(), min(self.maximum(), seconds))
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
        pen = QPen(base_color, 1)
        painter.setPen(pen)

        # Draw symmetric 7px '+' in top button
        if up_rect.isValid() and up_rect.width() >= 8:
            ux = (up_rect.left() + up_rect.right()) // 2
            uy = (up_rect.top() + up_rect.bottom()) // 2
            painter.drawLine(ux - 3, uy, ux + 3, uy)
            painter.drawLine(ux, uy - 3, ux, uy + 3)

        # Draw identical 7px '-' in bottom button
        if down_rect.isValid() and down_rect.width() >= 8:
            dx = (down_rect.left() + down_rect.right()) // 2
            dy = (down_rect.top() + down_rect.bottom()) // 2
            painter.drawLine(dx - 3, dy, dx + 3, dy)

        painter.end()


class InPointSpinBox(SmartDoubleSpinBox):
    """High-precision (centesimi) spinbox for Cue IN point."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """In point in seconds with 1/20 s steps."""
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")


class OutPointSpinBox(SmartDoubleSpinBox):
    """Smart Out Point SpinBox with centesimi precision and end-of-file down-stepping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Out point in seconds; the minimum value means "end of file"."""
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")
        self.setSpecialValueText("Fine File")
        self._media_duration: float = 0.0

    def set_media_duration(self, duration_sec: float) -> None:
        """Update the upper bound of the time spinbox from the media length."""
        self._media_duration = max(0.0, duration_sec)

    def stepBy(self, steps: int) -> None:  # noqa: N802
        """Step by seconds, clamping at the media duration instead of the sentinel."""
        cur = self.value()
        if cur == 0.0 and steps < 0 and self._media_duration > 0:
            target = max(0.05, self._media_duration + (steps * self.singleStep()))
            self.setValue(round(target, 2))
            return
        if cur == 0.0 and steps > 0 and self._media_duration > 0:
            return
        super().stepBy(steps)
