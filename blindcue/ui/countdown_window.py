"""Big countdown for backstage or a second screen (stage 2, items 2.5 and 2.11).

Shows a title ("Interval") and the time left in large digits that grow with
the window. In the last minute the digits turn amber and blink; at zero they
stay red. Once the stopwatch was used it shows under the countdown, and on
its own (in large digits) when no countdown runs. The window only shows what
the main window tells it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def format_left(seconds: float) -> str:
    """"12:34" (or "1:02:03" for an hour or more); never negative."""
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class CountdownWindow(QWidget):
    """A plain window: title and the time left, sized to the window; the stopwatch below."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Conto alla rovescia")
        self.setStyleSheet("background-color: #000000;")
        self.resize(720, 360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 10, 20, 20)
        self.lbl_title = QLabel("")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("color: #cbd5e1; background: transparent;")
        lay.addWidget(self.lbl_title)
        self.lbl_time = QLabel("00:00")
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setAccessibleName("Tempo rimanente")
        lay.addWidget(self.lbl_time, 1)
        self.lbl_stopwatch = QLabel("")
        self.lbl_stopwatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_stopwatch.setAccessibleName("Cronometro")
        self.lbl_stopwatch.setVisible(False)
        lay.addWidget(self.lbl_stopwatch)
        self._blink = False
        self._countdown_on = True
        self._fit()

    def show_left(self, seconds: float, title: str) -> None:
        if not self._countdown_on:
            self._countdown_on = True
            self.lbl_title.setVisible(True)
            self.lbl_time.setVisible(True)
            self._fit()
        self.lbl_title.setText(title)
        self.lbl_time.setText(format_left(seconds))
        self._blink = not self._blink
        if seconds <= 0:
            colour = "#ef4444"
        elif seconds <= 60:
            colour = "#f59e0b" if self._blink else "#7c4a03"   # the last minute blinks
        else:
            colour = "#ffffff"
        self.lbl_time.setStyleSheet(f"color: {colour}; background: transparent;")

    def show_idle(self) -> None:
        """Nothing counts yet (no countdown, no stopwatch): grey dashes."""
        self.show_left(1.0e9, "")
        self.lbl_time.setText("--:--")
        self.lbl_time.setStyleSheet("color: #475569; background: transparent;")

    def show_countdown_off(self) -> None:
        """No countdown runs: only the stopwatch stays (in large digits)."""
        if self._countdown_on:
            self._countdown_on = False
            self.lbl_title.setVisible(False)
            self.lbl_time.setVisible(False)
            self._fit()

    def show_stopwatch(self, seconds: float | None, running: bool = True) -> None:
        """2.11: the stopwatch ("⏱ 12:34", "❚❚" when stopped); None hides it."""
        if seconds is None:
            self.lbl_stopwatch.setVisible(False)
            return
        self.lbl_stopwatch.setText(f"⏱ {format_left(seconds)}" + ("" if running else " ❚❚"))
        colour = "#7dd3fc" if running else "#94a3b8"
        self.lbl_stopwatch.setStyleSheet(f"color: {colour}; background: transparent;")
        self.lbl_stopwatch.setVisible(True)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        big = max(24, int(min(self.height() * 0.55, self.width() * 0.28)))
        digits = QFont("Segoe UI", 10, QFont.Weight.Bold)
        digits.setPixelSize(big)
        self.lbl_time.setFont(digits)
        title = QFont("Segoe UI", 10, QFont.Weight.Bold)
        title.setPixelSize(max(14, int(self.height() * 0.09)))
        self.lbl_title.setFont(title)
        watch = QFont("Segoe UI", 10, QFont.Weight.Bold)
        watch.setPixelSize(big if not self._countdown_on else max(16, int(big * 0.3)))
        self.lbl_stopwatch.setFont(watch)
