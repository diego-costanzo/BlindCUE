"""Bottom Live Output Status panel (Layers 1-3 readout, Cut controls, Blackout, Layer 0 Tappo)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from models.cue import Cue
from ui.theme import CLR_LIVE, CLR_PREVIZ

_IDLE_LAYER_STYLE = """
    QLabel {
        background-color: #2b2b2b;
        border: 1px solid #555;
        border-radius: 3px;
        padding: 4px 8px;
        font-size: 12px;
        color: #777;
    }
"""

_LIVE_LAYER_STYLE = f"""
    QLabel {{
        background-color: #16361a;
        border: 1px solid {CLR_LIVE};
        border-radius: 3px;
        padding: 4px 8px;
        font-size: 12px;
        font-weight: bold;
        color: {CLR_LIVE};
    }}
"""


class LiveStatusPanel(QGroupBox):
    """Real-time monitor and Cut/Blackout controls for Layers 1-3 plus Layer 0 failsafe."""

    clear_layer_clicked = Signal(int)
    blackout_clicked = Signal()
    choose_layer0_clicked = Signal()
    reset_layer0_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Live Output Status (Monitor Uscita Schermo Esterno)", parent)
        self._layer_labels: dict[int, QLabel] = {}
        self._clear_buttons: dict[int, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        lbl_sub = QLabel("Controllo emissione in tempo reale sui 3 livelli live:")
        lbl_sub.setStyleSheet("color: #777; font-size: 10px;")
        layout.addWidget(lbl_sub)

        cut_style = (
            "QPushButton { background-color: #5c1d1d; color: #ff8080; border: 1px solid #ff4444; "
            "border-radius: 3px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background-color: #7a2727; }"
        )

        for layer in (1, 2, 3):
            row = QHBoxLayout()
            lbl = QLabel(f"Layer {layer}: —")
            lbl.setMinimumWidth(0)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            lbl.setStyleSheet(_IDLE_LAYER_STYLE)
            btn = QPushButton(f"✕ Cut L{layer}")
            btn.setToolTip(f"Rimuovi / arresta immediatamente il contenuto su Layer {layer}")
            btn.setStyleSheet(cut_style)
            btn.clicked.connect(lambda _=False, idx=layer: self.clear_layer_clicked.emit(idx))
            row.addWidget(lbl, stretch=1)
            row.addWidget(btn)
            layout.addLayout(row)
            self._layer_labels[layer] = lbl
            self._clear_buttons[layer] = btn

        self.btn_clear_all = QPushButton("⏹ Master Blackout (Tappo) — [ Ctrl+B ]")
        self.btn_clear_all.setToolTip(
            "Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B"
        )
        self.btn_clear_all.setStyleSheet(
            "QPushButton { background-color: #3a1111; color: #ff9999; border: 1px solid #882222; "
            "border-radius: 4px; font-weight: bold; padding: 6px; } "
            "QPushButton:hover { background-color: #5c1d1d; }"
        )
        self.btn_clear_all.clicked.connect(self.blackout_clicked)
        layout.addWidget(self.btn_clear_all)

        row_tappo = QHBoxLayout()
        self.lbl_tappo_info = QLabel("Tappo (L0): Logo BlindCue (Predefinito)")
        self.lbl_tappo_info.setMinimumWidth(0)
        self.lbl_tappo_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_tappo_info.setStyleSheet("color: #aaa; font-size: 11px; padding: 2px;")

        self.btn_choose_tappo = QPushButton("📁 Cambia Tappo…")
        self.btn_choose_tappo.setToolTip(
            "Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)"
        )
        self.btn_choose_tappo.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: {CLR_PREVIZ}; border: 1px solid {CLR_PREVIZ}; "
            f"border-radius: 3px; font-weight: bold; padding: 3px 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: #4d3800; }}"
        )
        self.btn_choose_tappo.clicked.connect(self.choose_layer0_clicked)

        self.btn_reset_tappo = QPushButton("🔄 Reset")
        self.btn_reset_tappo.setToolTip("Ripristina il logo predefinito di BlindCue come Layer 0")
        self.btn_reset_tappo.setStyleSheet(
            "QPushButton { background-color: #2b2b2b; color: #888; border: 1px solid #555; "
            "border-radius: 3px; padding: 3px 6px; font-size: 11px; } "
            "QPushButton:hover { background-color: #3a3a3a; }"
        )
        self.btn_reset_tappo.clicked.connect(self.reset_layer0_clicked)

        row_tappo.addWidget(self.lbl_tappo_info, stretch=1)
        row_tappo.addWidget(self.btn_choose_tappo)
        row_tappo.addWidget(self.btn_reset_tappo)
        layout.addLayout(row_tappo)
        layout.addStretch()

    def set_layer_live(self, cue: Cue) -> None:
        lbl = self._layer_labels.get(cue.layer)
        if lbl is not None:
            q_part = f"{cue.q_label} • " if cue.q_label else ""
            lbl.setText(f"LIVE: [{cue.media_type.value}] {q_part}{cue.name}  (Layer {cue.layer})")
            lbl.setStyleSheet(_LIVE_LAYER_STYLE)

    def reset_layer(self, layer: int) -> None:
        lbl = self._layer_labels.get(layer)
        if lbl is not None:
            lbl.setText(f"Layer {layer}: —")
            lbl.setStyleSheet(_IDLE_LAYER_STYLE)

    def reset_all_layers(self) -> None:
        for layer in (1, 2, 3):
            self.reset_layer(layer)

    def set_layer0_label(self, file_path: Optional[str]) -> None:
        name = Path(file_path).name if file_path else "Logo BlindCue (Predefinito)"
        self.lbl_tappo_info.setText(f"Tappo (L0): {name}")

