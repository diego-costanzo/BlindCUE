"""Left-column Cue Sequence List panel widget (Scaletta Cue)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.cue import MediaType
from ui.cue_table import CueSequenceTable


class CueListPanel(QGroupBox):
    """Left panel displaying the 3-column Cue Sequence Table and list action buttons."""

    add_media_requested = Signal(object)  # MediaType
    move_up_requested = Signal()
    move_down_requested = Signal()
    delete_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("SCALETTA CUE (Sequence List)", parent)
        self.setMinimumWidth(260)
        self._build_ui()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(260, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(330, 560)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        cue_summary_bar = QHBoxLayout()
        self.lbl_count = QLabel("0 Cue caricate")
        self.lbl_count.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold;")
        self.lbl_standby = QLabel("Standby: Nessuna")
        self.lbl_standby.setMinimumWidth(0)
        self.lbl_standby.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        cue_summary_bar.addWidget(self.lbl_count)
        cue_summary_bar.addWidget(self.lbl_standby, stretch=1)
        layout.addLayout(cue_summary_bar)

        self.table = CueSequenceTable()
        layout.addWidget(self.table)

        btn_add_row = QHBoxLayout()
        btn_add_row.setSpacing(4)

        self.btn_add_video = QPushButton("+ Video")
        self.btn_add_video.setToolTip("Aggiungi file video alla scaletta")
        self.btn_add_video.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; } "
            "QPushButton:hover { border-color: #42a5f5; color: #42a5f5; }"
        )

        self.btn_add_audio = QPushButton("+ Audio")
        self.btn_add_audio.setToolTip("Aggiungi file audio alla scaletta")
        self.btn_add_audio.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; } "
            "QPushButton:hover { border-color: #26a69a; color: #26a69a; }"
        )

        self.btn_add_image = QPushButton("+ Immagine")
        self.btn_add_image.setToolTip("Aggiungi immagine statica (Layer 1-3)")
        self.btn_add_image.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; } "
            "QPushButton:hover { border-color: #ffa726; color: #ffa726; }"
        )

        self.btn_move_up = QPushButton("▲ Su")
        self.btn_move_up.setToolTip("Sposta la cue in alto (Alt+↑)")
        self.btn_move_up.setFixedHeight(26)

        self.btn_move_down = QPushButton("▼ Giù")
        self.btn_move_down.setToolTip("Sposta la cue in basso (Alt+↓)")
        self.btn_move_down.setFixedHeight(26)

        self.btn_delete = QPushButton("🗑 Elimina")
        self.btn_delete.setToolTip("Rimuovi la cue dalla scaletta (Canc)")
        self.btn_delete.setFixedHeight(26)
        self.btn_delete.setStyleSheet(
            "QPushButton { color: #ff8080; border: 1px solid #ff4444; background-color: #401818; font-weight: bold; } "
            "QPushButton:hover { background-color: #5c2222; }"
        )

        self.btn_add_video.clicked.connect(lambda: self.add_media_requested.emit(MediaType.VIDEO))
        self.btn_add_audio.clicked.connect(lambda: self.add_media_requested.emit(MediaType.AUDIO))
        self.btn_add_image.clicked.connect(lambda: self.add_media_requested.emit(MediaType.IMAGE))
        self.btn_move_up.clicked.connect(self.move_up_requested)
        self.btn_move_down.clicked.connect(self.move_down_requested)
        self.btn_delete.clicked.connect(self.delete_requested)

        for btn in (self.btn_add_video, self.btn_add_audio, self.btn_add_image):
            btn_add_row.addWidget(btn, stretch=1)
        layout.addLayout(btn_add_row)

        btn_edit_row = QHBoxLayout()
        btn_edit_row.setSpacing(4)
        btn_edit_row.addWidget(self.btn_move_up, stretch=1)
        btn_edit_row.addWidget(self.btn_move_down, stretch=1)
        btn_edit_row.addWidget(self.btn_delete, stretch=2)
        layout.addLayout(btn_edit_row)

