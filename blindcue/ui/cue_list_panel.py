"""Left-column Cue Sequence List panel widget (Scaletta Cue)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.cue import FollowMode, MediaType
from ui.cue_table import CueSequenceTable

_FOLLOW_SPECS = (
    (
        FollowMode.MANUAL.value,
        "⏹ Blocco",
        "⏹ Blocco (Default): esegue solo la cue selezionata (Pre+Durata+Post) e attende GO manuale.",
        "#065f46",
        "#10b981",
    ),
    (
        FollowMode.AUTO_FOLLOW.value,
        "⤵ Auto-GO",
        "⤵ GO Automatico: al termine di Pre-Delay + Durata + Post-Delay avvia automaticamente la cue successiva.",
        "#0c4a6e",
        "#38bdf8",
    ),
    (
        FollowMode.SIMULTANEOUS.value,
        "⇉ Simult.",
        "⇉ Simultanea: al GO avvia subito insieme la cue successiva (che rispetta comunque il proprio Pre-Delay).",
        "#78350f",
        "#f59e0b",
    ),
)


class CueListPanel(QGroupBox):
    """Left panel displaying the 3-column Cue Sequence Table and list action buttons."""

    add_media_requested = Signal(object)  # MediaType
    add_group_requested = Signal()
    ungroup_requested = Signal()
    extract_child_requested = Signal()
    move_up_requested = Signal()
    move_down_requested = Signal()
    delete_requested = Signal()
    go_live_mode_requested = Signal()
    follow_mode_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("SCALETTA CUE (Sequence List)", parent)
        self.setMinimumWidth(260)
        self._follow_buttons: dict[str, QPushButton] = {}
        self._follow_hints: dict[str, str] = {}
        self._active_follow_mode: Optional[str] = FollowMode.MANUAL.value
        self._build_ui()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(260, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(330, 560)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        cue_summary_bar = QHBoxLayout()
        cue_summary_bar.setSpacing(6)
        self.lbl_count = QLabel("0 Cue")
        self.lbl_count.setStyleSheet(
            "color: #38bdf8; background-color: #0e1c2b; border: 1px solid #1e3a5f; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 1px 6px;"
        )
        self.lbl_standby = QLabel("Standby: Nessuna")
        self.lbl_standby.setMinimumWidth(0)
        self.lbl_standby.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        self.btn_go_live = QPushButton("🎭 VAI IN LIVE")
        self.btn_go_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go_live.setFixedHeight(24)
        self.btn_go_live.setToolTip(
            "Apri la modalità semplificata LIVE (Show Mode) centrata su Scaletta, GO, PAUSA TUTTO e PANIC [F5 / Ctrl+L]"
        )
        self.btn_go_live.setStyleSheet(
            "QPushButton { background-color: #064e3b; color: #69f0ae; border: 1px solid #00e676; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 8px; } "
            "QPushButton:hover { background-color: #047857; color: #ffffff; }"
        )
        self.btn_go_live.clicked.connect(self.go_live_mode_requested)
        self.btn_go_live.setAccessibleName("Modalità LIVE Show")
        self.btn_go_live.setAccessibleDescription("Passa alla schermata di regia semplificata per il live.")
        cue_summary_bar.addWidget(self.lbl_count)
        cue_summary_bar.addWidget(self.lbl_standby, stretch=1)
        cue_summary_bar.addWidget(self.btn_go_live)
        layout.addLayout(cue_summary_bar)

        self.table = CueSequenceTable()
        self.table.setAccessibleName("Scaletta delle Cue")
        self.table.setAccessibleDescription("Elenco sequenziale delle scene e dei media. Naviga con freccia Su e Giù, premi Spazio per il GO.")
        self.table.group_requested.connect(self.add_group_requested)
        self.table.ungroup_requested.connect(self.ungroup_requested)
        self.table.extract_child_requested.connect(self.extract_child_requested)
        layout.addWidget(self.table)

        btn_add_row = QHBoxLayout()
        btn_add_row.setSpacing(4)

        self.btn_add_video = QPushButton("+ Video")
        self.btn_add_video.setToolTip("Aggiungi file video alla scaletta")
        self.btn_add_video.setAccessibleName("Aggiungi Video")
        self.btn_add_video.setAccessibleDescription("Apre la finestra di selezione per aggiungere un file video alla scaletta.")
        self.btn_add_video.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; font-size: 11px; padding: 0 4px; } "
            "QPushButton:hover { border-color: #42a5f5; color: #42a5f5; }"
        )

        self.btn_add_audio = QPushButton("+ Audio")
        self.btn_add_audio.setToolTip("Aggiungi file audio alla scaletta")
        self.btn_add_audio.setAccessibleName("Aggiungi Audio")
        self.btn_add_audio.setAccessibleDescription("Apre la finestra di selezione per aggiungere un file audio alla scaletta.")
        self.btn_add_audio.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; font-size: 11px; padding: 0 4px; } "
            "QPushButton:hover { border-color: #26a69a; color: #26a69a; }"
        )

        self.btn_add_image = QPushButton("+ Foto")
        self.btn_add_image.setToolTip("Aggiungi immagine / foto statica (Layer 1-3)")
        self.btn_add_image.setAccessibleName("Aggiungi Foto o Immagine")
        self.btn_add_image.setAccessibleDescription("Apre la finestra di selezione per aggiungere una foto o grafica statica alla scaletta.")
        self.btn_add_image.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; font-size: 11px; padding: 0 4px; } "
            "QPushButton:hover { border-color: #ffa726; color: #ffa726; }"
        )

        self.btn_add_group = QPushButton("+ Gruppo")
        self.btn_add_group.setToolTip("Crea un gruppo di cue / scena (Ctrl+G)")
        self.btn_add_group.setAccessibleName("Aggiungi Gruppo o Scena")
        self.btn_add_group.setAccessibleDescription("Crea un nuovo contenitore di gruppo o scena sincronizzata.")
        self.btn_add_group.setStyleSheet(
            "QPushButton { height: 26px; font-weight: bold; font-size: 11px; padding: 0 4px; border-color: #7c3aed; color: #c084fc; background-color: #1e1533; } "
            "QPushButton:hover { background-color: #2e1d52; border-color: #a855f7; color: #ffffff; }"
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
        self.btn_add_group.clicked.connect(self.add_group_requested)
        self.btn_move_up.clicked.connect(self.move_up_requested)
        self.btn_move_down.clicked.connect(self.move_down_requested)
        self.btn_delete.clicked.connect(self.delete_requested)

        for btn in (self.btn_add_video, self.btn_add_audio, self.btn_add_image, self.btn_add_group):
            btn_add_row.addWidget(btn, stretch=1)
        layout.addLayout(btn_add_row)

        btn_edit_row = QHBoxLayout()
        btn_edit_row.setSpacing(4)
        btn_edit_row.addWidget(self.btn_move_up, stretch=1)
        btn_edit_row.addWidget(self.btn_move_down, stretch=1)
        btn_edit_row.addWidget(self.btn_delete, stretch=2)
        layout.addLayout(btn_edit_row)

        # 3-State Sequencing Link Mode Selector (Blocco | Auto-GO | Simultanea) — Fixed height prevents hover jump!
        link_box = QFrame()
        link_box.setFixedHeight(74)
        link_box.setStyleSheet(
            "QFrame { background-color: #101620; border: 1px solid #1e293b; border-radius: 5px; }"
        )
        link_layout = QVBoxLayout(link_box)
        link_layout.setContentsMargins(6, 5, 6, 4)
        link_layout.setSpacing(4)

        follow_row = QHBoxLayout()
        follow_row.setSpacing(4)
        for mode_val, label, hint, chk_bg, chk_border in _FOLLOW_SPECS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setToolTip(hint)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: #182130; color: #94a3b8; border: 1px solid #2a374b; "
                f"border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 4px; }} "
                f"QPushButton:hover:!checked {{ background-color: #223044; border-color: {chk_border}; color: #ffffff; }} "
                f"QPushButton:checked {{ background-color: {chk_bg}; border: 1px solid {chk_border}; color: #ffffff; }} "
                f"QPushButton:disabled {{ color: #475569; border-color: #1a2230; background-color: #0e131b; }}"
            )
            btn.clicked.connect(lambda _=False, m=mode_val: self.follow_mode_selected.emit(m))
            btn.installEventFilter(self)
            self._follow_buttons[mode_val] = btn
            self._follow_hints[mode_val] = hint
            follow_row.addWidget(btn, 1)
        link_layout.addLayout(follow_row)

        self.lbl_follow_hint = QLabel("⏹ Blocco: attende il prossimo GO manuale")
        self.lbl_follow_hint.setWordWrap(True)
        self.lbl_follow_hint.setFixedHeight(34)
        self.lbl_follow_hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_follow_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.lbl_follow_hint.setStyleSheet("color: #64748b; font-size: 9px; border: none; background: transparent;")
        link_layout.addWidget(self.lbl_follow_hint)
        layout.addWidget(link_box)

        self.set_follow_mode_checked(FollowMode.MANUAL.value, enabled=False)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Enter:
            for m, btn in self._follow_buttons.items():
                if obj is btn:
                    self.lbl_follow_hint.setText(self._follow_hints[m])
                    self.lbl_follow_hint.setStyleSheet("color: #cbd5e1; font-size: 9px; border: none; background: transparent;")
                    break
        elif event.type() == QEvent.Type.Leave:
            self._refresh_follow_caption()
        return super().eventFilter(obj, event)

    def _refresh_follow_caption(self) -> None:
        if self._active_follow_mode and self._active_follow_mode in self._follow_hints:
            self.lbl_follow_hint.setText(self._follow_hints[self._active_follow_mode])
            self.lbl_follow_hint.setStyleSheet("color: #94a3b8; font-size: 9px; border: none; background: transparent;")
        else:
            self.lbl_follow_hint.setText("Selezione multipla mista — clicca una modalità per applicarla a tutte")
            self.lbl_follow_hint.setStyleSheet("color: #f59e0b; font-size: 9px; border: none; background: transparent;")

    def set_follow_mode_checked(self, mode: Optional[str], *, enabled: bool = True) -> None:
        self._active_follow_mode = mode if mode in self._follow_buttons else None
        for m, btn in self._follow_buttons.items():
            btn.blockSignals(True)
            btn.setEnabled(enabled)
            btn.setChecked(enabled and (m == self._active_follow_mode))
            btn.blockSignals(False)
        if not enabled:
            self.lbl_follow_hint.setText("Seleziona una o più cue per scegliere Blocco / Auto-GO / Simultanea")
            self.lbl_follow_hint.setStyleSheet("color: #475569; font-size: 9px; border: none; background: transparent;")
        else:
            self._refresh_follow_caption()

