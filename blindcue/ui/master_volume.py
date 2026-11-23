"""Master volume of the show with MUTE, in the top row of both views.

One knob for the whole hall: it multiplies every cue that plays or will play
(not the preview monitor). It starts at 100 % every time the program starts,
so a level left low yesterday never makes "the program does not play".
Keys (window-wide): Ctrl+Up / Ctrl+Down (±5 %), Ctrl+M (mute).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

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
        for w in (self.lbl, self.slider, self.pct, self.btn_mute):
            lay.addWidget(w)
        self.slider.valueChanged.connect(self._on_slider)
        self.btn_mute.toggled.connect(self._on_mute)

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
