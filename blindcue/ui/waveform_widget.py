"""Audio/Video waveform peak renderer with interactive IN/OUT handle dragging."""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QMouseEvent, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QWidget

from ui.theme import CLR_ACCENT, CLR_LIVE, CLR_PANEL


class WaveformWidget(QWidget):
    """Paints a waveform peak array with interactive mouse dragging of IN / OUT markers."""

    in_changed = Signal(float)   # In seconds
    out_changed = Signal(float)  # Out seconds (or 0.0 for End of File)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._peaks: Optional[np.ndarray] = None
        self._in_point: float = 0.0
        self._out_point: float = 1.0  # normalised 0-1
        self._in_sec: float = 0.0
        self._out_sec: Optional[float] = None
        self._duration_sec: float = 0.0
        self._playhead: Optional[float] = None
        self._dragging_handle: Optional[str] = None
        self.setMinimumHeight(100)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background-color: {CLR_PANEL};")

    def set_peaks(self, peaks: np.ndarray) -> None:
        self._peaks = peaks
        self.update()

    def set_in_out(self, in_norm: float, out_norm: float) -> None:
        self._in_point = in_norm
        self._out_point = out_norm
        self.update()

    def set_in_out_seconds(self, in_sec: float, out_sec: Optional[float], duration_sec: float) -> None:
        """Update IN and OUT points in seconds relative to total file duration."""
        self._in_sec = max(0.0, in_sec)
        self._out_sec = out_sec
        self._duration_sec = max(0.001, duration_sec) if duration_sec > 0 else 0.0

        if self._duration_sec > 0:
            self._in_point = min(1.0, max(0.0, self._in_sec / self._duration_sec))
            if self._out_sec is not None and self._out_sec > 0:
                self._out_point = min(1.0, max(0.0, self._out_sec / self._duration_sec))
            else:
                self._out_point = 1.0
        else:
            self._in_point = 0.0
            self._out_point = 1.0
        self.update()

    def set_playhead(self, norm_pos: Optional[float]) -> None:
        """Update active playhead position (0.0 to 1.0) or None to hide."""
        if self._playhead != norm_pos:
            self._playhead = norm_pos
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._duration_sec > 0:
            x = event.position().x()
            w = max(1, self.width())
            in_x = int(self._in_point * w)
            out_x = int(self._out_point * w)

            if abs(x - in_x) <= 15:
                self._dragging_handle = "IN"
            elif abs(x - out_x) <= 15:
                self._dragging_handle = "OUT"
            else:
                self._dragging_handle = "IN" if abs(x - in_x) < abs(x - out_x) else "OUT"
                self._handle_mouse_drag(x)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        if self._dragging_handle:
            self._handle_mouse_drag(x)
        else:
            w = max(1, self.width())
            in_x = int(self._in_point * w)
            out_x = int(self._out_point * w)
            if abs(x - in_x) <= 12 or abs(x - out_x) <= 12:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging_handle = None
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def leaveEvent(self, _event) -> None:  # noqa: N802
        if not self._dragging_handle:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _handle_mouse_drag(self, x: float) -> None:
        if self._duration_sec <= 0:
            return
        w = max(1, self.width())
        norm = max(0.0, min(1.0, x / w))
        sec = norm * self._duration_sec

        if self._dragging_handle == "IN":
            max_in = (self._out_sec - 0.05) if (self._out_sec is not None and self._out_sec > 0) else (self._duration_sec - 0.05)
            new_in = max(0.0, min(max_in, sec))
            self._in_sec = round(new_in, 2)
            self._in_point = self._in_sec / self._duration_sec
            self.in_changed.emit(self._in_sec)
            self.update()

        elif self._dragging_handle == "OUT":
            min_out = self._in_sec + 0.05
            new_out = max(min_out, min(self._duration_sec, sec))
            if new_out >= self._duration_sec - 0.05:
                self._out_sec = None
                self._out_point = 1.0
                self.out_changed.emit(0.0)
            else:
                self._out_sec = round(new_out, 2)
                self._out_point = self._out_sec / self._duration_sec
                self.out_changed.emit(self._out_sec)
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        painter.fillRect(0, 0, w, h, QColor(CLR_PANEL))

        if self._peaks is None or len(self._peaks) == 0:
            painter.setPen(QPen(QColor("#888"), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Nessuna forma d'onda caricata")
            painter.end()
            return

        n = len(self._peaks)
        bar_w = max(1.0, w / n)
        mid_y = h / 2

        painter.setPen(Qt.PenStyle.NoPen)
        for i, peak in enumerate(self._peaks):
            x = i * bar_w
            bar_h = peak * mid_y * 0.9
            frac = i / n
            if self._in_point <= frac <= self._out_point:
                painter.setBrush(QColor(CLR_LIVE))
            else:
                painter.setBrush(QColor("#444444"))
            painter.drawRect(int(x), int(mid_y - bar_h),
                             max(1, int(bar_w) - 1), int(bar_h * 2))

        in_x = int(self._in_point * w)
        painter.setPen(QPen(QColor(CLR_LIVE), 2))
        painter.drawLine(in_x, 0, in_x, h)

        painter.setBrush(QColor(CLR_LIVE))
        painter.drawPolygon([QPoint(in_x, 0), QPoint(in_x - 6, 8), QPoint(in_x + 6, 8)])
        painter.drawPolygon([QPoint(in_x, h), QPoint(in_x - 6, h - 8), QPoint(in_x + 6, h - 8)])

        in_txt = f"IN: {self._in_sec:.2f}s" if self._in_sec > 0 else "IN: 0.00s"
        painter.fillRect(in_x + 2, 2, len(in_txt) * 7 + 8, 16, QColor("#003314"))
        painter.setPen(QColor(CLR_LIVE))
        painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
        painter.drawText(in_x + 6, 14, in_txt)

        out_x = min(w - 1, int(self._out_point * w))
        painter.setPen(QPen(QColor("#ff5252"), 2))
        painter.drawLine(out_x, 0, out_x, h)

        painter.setBrush(QColor("#ff5252"))
        painter.drawPolygon([QPoint(out_x, 0), QPoint(out_x - 6, 8), QPoint(out_x + 6, 8)])
        painter.drawPolygon([QPoint(out_x, h), QPoint(out_x - 6, h - 8), QPoint(out_x + 6, h - 8)])

        out_txt = f"OUT: {self._out_sec:.2f}s" if (self._out_sec is not None and self._out_sec > 0) else "OUT: Fine"
        out_pill_w = len(out_txt) * 7 + 8
        out_pill_x = max(0, out_x - out_pill_w - 2) if out_x > w - 90 else out_x + 2
        painter.fillRect(out_pill_x, 2, out_pill_w, 16, QColor("#3a0d0d"))
        painter.setPen(QColor("#ff5252"))
        painter.drawText(out_pill_x + 5, 14, out_txt)

        if self._playhead is not None and 0.0 <= self._playhead <= 1.0:
            playhead_x = int(self._playhead * w)
            painter.setPen(QPen(QColor(CLR_ACCENT), 2))
            painter.drawLine(playhead_x, 0, playhead_x, h)
            painter.setBrush(QColor(CLR_ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            poly = [
                QPoint(playhead_x - 5, 0),
                QPoint(playhead_x + 5, 0),
                QPoint(playhead_x, 8),
            ]
            painter.drawPolygon(QPolygon(poly))

        painter.end()

