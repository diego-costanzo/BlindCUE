"""Master volume of the show with MUTE, in the top row of both views.

One knob for the whole hall: it multiplies every cue that plays or will play
(not the preview monitor). It starts at 100 % every time the program starts,
so a level left low yesterday never makes "the program does not play".
Keys (window-wide): Ctrl+Up / Ctrl+Down (±5 %), Ctrl+M (mute).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider, QVBoxLayout, QWidget

STEP = 0.05

_MUTE_OFF = (
    "QPushButton { background-color: #1c2636; color: #cbd5e1; border: 1px solid #3c4f6b; "
    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 10px; } "
    "QPushButton:hover { border-color: #38bdf8; } QPushButton:focus { border: 2px solid #38bdf8; }"
)
_MUTE_ON = (
    "QPushButton { background-color: #f59e0b; color: #1c1203; border: 2px solid #fde68a; "
    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 10px; } "
    "QPushButton:focus { border: 2px solid #ffffff; }"
)


class MasterVolume(QWidget):
    """Slider + percent + MUTE. Emits ``level_changed(level)`` and ``mute_changed(muted)``."""

    level_changed = Signal(float)
    mute_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.lbl = QLabel("🔊")
        self.lbl.setStyleSheet("color: #cbd5e1; font-size: 13px; background: transparent;")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setFixedWidth(110)
        self.slider.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.slider.setAccessibleName("Volume generale dello spettacolo")
        self.slider.setToolTip("Volume generale di tutto ciò che suona [Ctrl+↑ / Ctrl+↓]")
        self.pct = QLabel("100 %")
        self.pct.setFixedWidth(44)
        self.pct.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 12px; background: transparent;")
        self.btn_mute = QPushButton("Silenzia")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedHeight(30)
        self.btn_mute.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_mute.setToolTip("Silenzia tutto (l'anteprima resta) [Ctrl+M]")
        self.btn_mute.setStyleSheet(_MUTE_OFF)
        # The slider with a thin VU meter under it (1.14): how loud the show plays now.
        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(1)
        stack.addWidget(self.slider)
        self.vu = QProgressBar()
        self.vu.setRange(0, 100)
        self.vu.setValue(0)
        self.vu.setTextVisible(False)
        self.vu.setFixedSize(110, 5)
        self.vu.setAccessibleName("Livello di uscita")
        self.vu.setStyleSheet(
            "QProgressBar { background-color: #1e293b; border: none; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #4ade80; border-radius: 2px; }")
        stack.addWidget(self.vu)
        lay.addWidget(self.lbl)
        lay.addLayout(stack)
        for w in (self.pct, self.btn_mute):
            lay.addWidget(w)
        self._vu_hot = False
        self.slider.valueChanged.connect(self._on_slider)
        self.btn_mute.toggled.connect(self._on_mute)

    def set_vu(self, level: float) -> None:
        """Peak 0..1 shown on a dB-like scale (-48 dB .. 0); amber near the top."""
        import math

        db = 20.0 * math.log10(level) if level > 1e-5 else -100.0
        value = int(max(0.0, min(1.0, (db + 48.0) / 48.0)) * 100)
        self.vu.setValue(value)
        hot = db > -3.0
        if hot != self._vu_hot:
            self._vu_hot = hot
            colour = "#fbbf24" if hot else "#4ade80"
            self.vu.setStyleSheet(
                "QProgressBar { background-color: #1e293b; border: none; border-radius: 2px; } "
                f"QProgressBar::chunk {{ background-color: {colour}; border-radius: 2px; }}")

    def set_state(self, level: float, muted: bool) -> None:
        """Show *level* and *muted* without emitting (keeps two copies in step)."""
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(level * 100)))
        self.slider.blockSignals(False)
        self.btn_mute.blockSignals(True)
        self.btn_mute.setChecked(muted)
        self.btn_mute.blockSignals(False)
        self._paint(level, muted)

    def _paint(self, level: float, muted: bool) -> None:
        self.pct.setText(f"{int(round(level * 100))} %")
        self.btn_mute.setText("🔇 SILENZIATO" if muted else "Silenzia")
        self.btn_mute.setStyleSheet(_MUTE_ON if muted else _MUTE_OFF)

    def _on_slider(self, value: int) -> None:
        self._paint(value / 100.0, self.btn_mute.isChecked())
        self.level_changed.emit(value / 100.0)

    def _on_mute(self, muted: bool) -> None:
        self._paint(self.slider.value() / 100.0, muted)
        self.mute_changed.emit(muted)
