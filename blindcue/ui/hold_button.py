"""Specialized PushButton with continuous-hold safety progress animation.

Designed for high-stakes broadcast and live theater environments to prevent
accidental clicks on critical actions (Jam Mode global gain, layer unlock, layer cuts).
"""

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QPushButton, QWidget

from i18n import tr


class HoldProgressButton(QPushButton):
    """Button requiring continuous hold/press for *hold_ms* to trigger or toggle."""

    hold_completed = Signal()
    toggled_state = Signal(bool)

    def __init__(
        self,
        text_idle: str,
        hold_ms: int = 3000,
        parent: QWidget | None = None,
        *,
        is_toggle: bool = True,
        initial_state: bool = False,
        text_active: str | None = None,
        color_idle: str = "#16202e",
        border_idle: str = "#2d3e56",
        text_color_idle: str = "#94a3b8",
        color_active: str = "#064e3b",
        border_active: str = "#10b981",
        text_color_active: str = "#34d399",
        fill_color: str = "#38bdf8",
        deactivate_hold_ms: int = 0,  # 0 = instantaneous click to deactivate/relock
        fill_orientation: str = "horizontal",  # "horizontal" or "vertical"
    ) -> None:
        """Create a hold-to-confirm button; ``hold_ms`` is the time needed to trigger."""
        super().__init__("", parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._text_idle = text_idle
        self._text_active = text_active or text_idle
        self._hold_ms = max(200, hold_ms)
        self._deactivate_hold_ms = deactivate_hold_ms
        self._is_toggle = is_toggle
        self._is_active = initial_state
        self._fill_orientation = fill_orientation

        self._color_idle = QColor(color_idle)
        self._border_idle = QColor(border_idle)
        self._text_color_idle = QColor(text_color_idle)

        self._color_active = QColor(color_active)
        self._border_active = QColor(border_active)
        self._text_color_active = QColor(text_color_active)

        self._fill_color = QColor(fill_color)

        # Internal state
        self._is_pressed = False
        self._press_start_mono: float = 0.0
        self._progress: float = 0.0
        self._current_hold_ms: int = self._hold_ms
        self._hover = False

        self._timer = QTimer(self)
        self._timer.setInterval(25)  # 40 fps smooth animation
        self._timer.timeout.connect(self._on_tick)

    # ── State Accessors & Compatibility Helpers ───────────────────────

    def is_active(self) -> bool:
        """True while the button is held (or latched active)."""
        return self._is_active

    def isChecked(self) -> bool:  # noqa: N802
        """QAbstractButton-compatible accessor for the latched state."""
        return self._is_active

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """QAbstractButton-compatible setter (emits ``toggled_state``)."""
        self.set_active(checked, silent=False)

    def text(self) -> str:
        """Label currently drawn (active or idle variant)."""
        return self._text_active if self._is_active else self._text_idle

    def setText(self, text: str) -> None:  # noqa: N802
        """Update the label of the currently visible state."""
        if self._is_active:
            self._text_active = text
        else:
            self._text_idle = text
        self.update()

    def set_active(self, active: bool, silent: bool = False) -> None:
        """Latch/unlatch the button; *silent* skips the ``toggled_state`` signal."""
        if self._is_active != active:
            self._is_active = active
            self._progress = 0.0
            self.update()
            if not silent:
                self.toggled_state.emit(self._is_active)

    def set_idle_text(self, text: str) -> None:
        """Label shown while the button is not active."""
        self._text_idle = text
        self.update()

    def set_active_text(self, text: str) -> None:
        """Label shown while the button is active."""
        self._text_active = text
        self.update()

    def set_palette_colors(
        self,
        *,
        color_idle: str | None = None,
        border_idle: str | None = None,
        text_color_idle: str | None = None,
        color_active: str | None = None,
        border_active: str | None = None,
        text_color_active: str | None = None,
        fill_color: str | None = None,
    ) -> None:
        """Override the theme palette; ``None`` keeps the current value."""
        if color_idle is not None:
            self._color_idle = QColor(color_idle)
        if border_idle is not None:
            self._border_idle = QColor(border_idle)
        if text_color_idle is not None:
            self._text_color_idle = QColor(text_color_idle)
        if color_active is not None:
            self._color_active = QColor(color_active)
        if border_active is not None:
            self._border_active = QColor(border_active)
        if text_color_active is not None:
            self._text_color_active = QColor(text_color_active)
        if fill_color is not None:
            self._fill_color = QColor(fill_color)
        self.update()

    # ── Mouse & Timer Event Handlers ──────────────────────────────────

    def enterEvent(self, event) -> None:  # noqa: N802
        """Track hover to paint the subtle hover ring."""
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Clear the hover state when the pointer leaves the button."""
        self._hover = False
        self._cancel_hold()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Start the hold countdown (or relock an already active toggle instantly)."""
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            # If toggle button is already active and deactivate requires no hold (instant click to relock):
            if self._is_toggle and self._is_active and self._deactivate_hold_ms == 0:
                self._is_active = False
                self._cancel_hold()
                self.toggled_state.emit(False)
                self.update()
                event.accept()
                return

            self._is_pressed = True
            self._press_start_mono = time.monotonic()
            self._progress = 0.0
            if self._is_toggle and self._is_active and self._deactivate_hold_ms > 0:
                self._current_hold_ms = self._deactivate_hold_ms
            else:
                self._current_hold_ms = self._hold_ms
            self._timer.start()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Abort the hold when the button is released before completion."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._cancel_hold()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _cancel_hold(self) -> None:
        if self._is_pressed or self._timer.isActive():
            self._is_pressed = False
            self._timer.stop()
            self._progress = 0.0
            self.update()

    def _on_tick(self) -> None:
        if not self._is_pressed:
            self._timer.stop()
            return

        elapsed_ms = (time.monotonic() - self._press_start_mono) * 1000.0
        self._progress = min(1.0, max(0.0, elapsed_ms / float(self._current_hold_ms)))

        if self._progress >= 1.0:
            self._timer.stop()
            self._is_pressed = False
            self._progress = 0.0

            if self._is_toggle:
                self._is_active = not self._is_active
                self.toggled_state.emit(self._is_active)
            self.hold_completed.emit()
            self.update()
        else:
            self.update()

    # ── Custom Painting ───────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the hold progress fill and the button label."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        w, h = rect.width(), rect.height()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 5.0, 5.0)

        # 1. Base Background
        if self._is_active:
            bg_col = self._color_active
            border_col = self._border_active
            txt_col = self._text_color_active
        else:
            bg_col = self._color_idle
            border_col = self._border_idle
            txt_col = self._text_color_idle

        if self._hover and not self._is_pressed:
            bg_col = bg_col.lighter(118)
            border_col = border_col.lighter(125)

        p.fillPath(clip_path, bg_col)

        # 2. Progress fill animation
        if self._progress > 0.0:
            p.save()
            p.setClipPath(clip_path)

            if self._fill_orientation == "vertical":
                fill_h = h * self._progress
                fill_rect = QRectF(0.0, float(h - fill_h), float(w), fill_h)
                grad = QLinearGradient(0.0, float(h), 0.0, float(h - fill_h))
                c1 = QColor(self._fill_color)
                c1.setAlpha(130)
                c2 = QColor(self._fill_color)
                c2.setAlpha(235)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(1.0, c2)
                p.fillRect(fill_rect, grad)
                p.setPen(QPen(self._fill_color.lighter(130), 2.0))
                p.drawLine(QPointF(0.0, float(h - fill_h)), QPointF(float(w), float(h - fill_h)))
            else:
                fill_w = w * self._progress
                fill_rect = QRectF(0.0, 0.0, fill_w, float(h))
                grad = QLinearGradient(0.0, 0.0, max(1.0, fill_w), 0.0)
                c1 = QColor(self._fill_color)
                c1.setAlpha(120)
                c2 = QColor(self._fill_color)
                c2.setAlpha(225)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(1.0, c2)
                p.fillRect(fill_rect, grad)
                p.setPen(QPen(self._fill_color.lighter(130), 2.0))
                p.drawLine(QPointF(fill_w, 0.0), QPointF(fill_w, float(h)))
                strip_rect = QRectF(0.0, float(h - 3), fill_w, 3.0)
                p.fillRect(strip_rect, self._fill_color)

            p.restore()

        # 3. Outer border
        p.setPen(QPen(border_col, 1.4))
        p.drawPath(clip_path)

        # 4. Content Text / Countdown
        rem_s = max(0.0, (1.0 - self._progress) * (self._current_hold_ms / 1000.0))

        if self._progress > 0.0:
            txt_col = QColor("#ffffff")

        raw_text = tr(self._text_active if self._is_active else self._text_idle)
        lines = raw_text.split("\n")

        font = self.font()
        p.setFont(font)
        p.setPen(txt_col)
        fm = QFontMetrics(font)

        if len(lines) > 1:
            # Multi-line layout (used for vertical Safety Lock Pillar)
            line_count = len(lines)
            line_h = fm.height()
            total_text_h = line_count * line_h + (line_count - 1) * 3
            start_y = (h - total_text_h) / 2.0

            for i, line in enumerate(lines):
                cur_y = start_y + i * (line_h + 3)
                l_rect = QRectF(4.0, cur_y, float(w - 8), float(line_h))

                # If in progress and this is the sub-line (last line), show countdown
                if self._progress > 0.0 and i == line_count - 1:
                    disp = f"{rem_s:.1f}s"
                    p.setFont(QFont("monospace", 10, QFont.Weight.Bold))
                    p.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, disp)
                    p.setFont(font)
                elif i == 0 and len(line) <= 3:
                    # Emoji / Icon line (large)
                    p.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
                    p.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, line)
                    p.setFont(font)
                else:
                    elided = fm.elidedText(line, Qt.TextElideMode.ElideMiddle, int(w - 8))
                    p.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, elided)
        else:
            # Single-line layout
            if self._progress > 0.0:
                if self._is_toggle and self._is_active:
                    display_text = f"Disattivazione... {rem_s:.1f}s"
                else:
                    display_text = f"Attivazione... {rem_s:.1f}s"
            else:
                display_text = raw_text

            elided = fm.elidedText(display_text, Qt.TextElideMode.ElideMiddle, int(w - 10))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided)

        p.end()
