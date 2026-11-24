"""Left-column Cue Sequence List panel widget (Scaletta Cue)."""

from __future__ import annotations


from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.cue import (
    ACTION_CHECKLIST,
    ACTION_FADE,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_OPACITY,
    ACTION_RELEASE,
    ACTION_STOP,
    FollowMode,
    MediaType,
)
from ui.cue_table import CueSequenceTable
from ui.theme import get_active_theme

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
    add_text_requested = Signal()
    add_action_requested = Signal(str)  # action kind (models.cue.ACTION_*)
    edit_text_requested = Signal()
    ungroup_requested = Signal()
    extract_child_requested = Signal()
    move_up_requested = Signal()
    move_down_requested = Signal()
    delete_requested = Signal()
    go_live_mode_requested = Signal()
    follow_mode_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the rundown panel with its follow-mode buttons and hints."""
        super().__init__("SCALETTA CUE (Sequence List)", parent)
        self.setMinimumWidth(260)
        self._follow_buttons: dict[str, QPushButton] = {}
        self._follow_hints: dict[str, str] = {}
        self._active_follow_mode: str | None = FollowMode.MANUAL.value
        self._build_ui()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Minimum size that keeps the cue list and its columns readable."""
        return QSize(260, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Preferred size of the cue list panel."""
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

        self.btn_add_video = QPushButton("+ Video")
        self.btn_add_video.setToolTip("Aggiungi file video alla scaletta")
        self.btn_add_video.setAccessibleName("Aggiungi Video")
        self.btn_add_video.setAccessibleDescription("Apre la finestra di selezione per aggiungere un file video alla scaletta.")
        self.btn_add_video.setFixedHeight(26)

        self.btn_add_audio = QPushButton("+ Audio")
        self.btn_add_audio.setToolTip("Aggiungi file audio alla scaletta")
        self.btn_add_audio.setAccessibleName("Aggiungi Audio")
        self.btn_add_audio.setAccessibleDescription("Apre la finestra di selezione per aggiungere un file audio alla scaletta.")
        self.btn_add_audio.setFixedHeight(26)

        self.btn_add_image = QPushButton("+ Foto")
        self.btn_add_image.setToolTip("Aggiungi immagine / foto statica (Layer 1-3)")
        self.btn_add_image.setAccessibleName("Aggiungi Foto o Immagine")
        self.btn_add_image.setAccessibleDescription("Apre la finestra di selezione per aggiungere una foto o grafica statica alla scaletta.")
        self.btn_add_image.setFixedHeight(26)

        self.btn_add_text = QPushButton("+ Testo")
        self.btn_add_text.setToolTip("Aggiungi una didascalia sullo schermo (cue di testo, Layer 3)")
        self.btn_add_text.setAccessibleName("Aggiungi Testo")
        self.btn_add_text.setFixedHeight(26)

        self.btn_add_group = QPushButton("+ Gruppo")
        self.btn_add_group.setToolTip("Crea un gruppo di cue / scena (Ctrl+G)")
        self.btn_add_group.setAccessibleName("Aggiungi Gruppo o Scena")
        self.btn_add_group.setAccessibleDescription("Crea un nuovo contenitore di gruppo o scena sincronizzata.")
        self.btn_add_group.setFixedHeight(26)

        self.btn_add_action = QPushButton("+ Azione")
        self.btn_add_action.setToolTip(
            "Aggiungi una cue senza file: ferma, dissolve, cambia livello o opacità di altre cue, "
            "oppure mostra una nota per la regia"
        )
        self.btn_add_action.setAccessibleName("Aggiungi Azione")
        self.btn_add_action.setFixedHeight(26)
        action_menu = QMenu(self.btn_add_action)
        for kind, label in (
            (ACTION_FADE, "🔉 Dissolvi e ferma"),
            (ACTION_STOP, "⏹ Ferma subito"),
            (ACTION_RELEASE, "🔁 Rilascia loop"),
            (ACTION_LEVEL, "🎚 Cambio livello"),
            (ACTION_OPACITY, "🌓 Opacità layer"),
            (ACTION_NOTE, "📝 Nota per la regia"),
            (ACTION_CHECKLIST, "☑ Checklist prima dello spettacolo"),
        ):
            act = action_menu.addAction(label)
            act.triggered.connect(lambda _=False, k=kind: self.add_action_requested.emit(k))
        self.btn_add_action.setMenu(action_menu)

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
        self.btn_add_text.clicked.connect(self.add_text_requested)
        self.table.edit_text_requested.connect(self.edit_text_requested)
        self.btn_move_up.clicked.connect(self.move_up_requested)
        self.btn_move_down.clicked.connect(self.move_down_requested)
        self.btn_delete.clicked.connect(self.delete_requested)

        # Three rows of three. In one long row, longer (translated) labels were
        # cut to 3-4 letters at 125 % Windows scaling with the theme's 12 px
        # side padding, which the compact padding below also trims.
        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(4)
        btn_grid.setVerticalSpacing(4)
        # One button for all media, several files at once (evaluation 2026-11-24): a teacher
        # added a video, a sound and a picture through three dialogs, one file each.
        self.btn_add_files = QPushButton("＋ Aggiungi file…")
        self.btn_add_files.setToolTip("Video, suoni e immagini – anche più file insieme (o trascinali sulla lista)")
        self.btn_add_files.setAccessibleName("Aggiungi file")
        self.btn_add_files.setFixedHeight(28)
        self.btn_add_files.clicked.connect(lambda: self.add_media_requested.emit(None))
        btn_grid.addWidget(self.btn_add_files, 0, 0, 1, 3)
        for btn in (self.btn_add_video, self.btn_add_audio, self.btn_add_image):
            btn.setParent(self)
            btn.setVisible(False)  # still there for the keyboard map and old shortcuts
        for idx, btn in enumerate((
            self.btn_add_text, self.btn_add_group, self.btn_add_action,
            self.btn_move_up, self.btn_move_down, self.btn_delete,
        )):
            btn.setStyleSheet(btn.styleSheet() + " QPushButton { padding: 2px 3px; }")
            btn_grid.addWidget(btn, 1 + idx // 3, idx % 3)
        for col in range(3):
            btn_grid.setColumnStretch(col, 1)
        layout.addLayout(btn_grid)

        # 3-State Sequencing Link Mode Selector (Blocco | Auto-GO | Simultanea) — Fixed height prevents hover jump!
        self.link_box = QFrame()
        self.link_box.setFixedHeight(74)
        link_layout = QVBoxLayout(self.link_box)
        link_layout.setContentsMargins(6, 5, 6, 4)
        link_layout.setSpacing(4)

        follow_row = QHBoxLayout()
        follow_row.setSpacing(4)
        for mode_val, label, hint, *_ in _FOLLOW_SPECS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.setToolTip(hint)
            btn.clicked.connect(lambda _=False, m=mode_val: self.follow_mode_selected.emit(m))
            btn.installEventFilter(self)
            self._follow_buttons[mode_val] = btn
            self._follow_hints[mode_val] = hint
            follow_row.addWidget(btn, 1)
        link_layout.addLayout(follow_row)

        self.lbl_follow_hint = QLabel("⏹ Blocco: attende il prossimo GO manuale")
        self.lbl_follow_hint.setWordWrap(True)
        self.lbl_follow_hint.setFixedHeight(36)
        self.lbl_follow_hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_follow_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.lbl_follow_hint.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        link_layout.addWidget(self.lbl_follow_hint)
        layout.addWidget(self.link_box)

        self.set_follow_mode_checked(FollowMode.MANUAL.value, enabled=False)
        self.refresh_theme_styles()

    def refresh_theme_styles(self) -> None:
        """Apply theme-aware styling to cue list panel buttons and link boxes."""
        active_t = get_active_theme()
        is_mono = active_t.is_monochrome
        if is_mono:
            if hasattr(self, "lbl_count"):
                self.lbl_count.setStyleSheet(
                    "color: #ffffff; background-color: #1a1b1f; border: 1px solid #3f404d; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 1px 6px;"
                )
            if hasattr(self, "btn_go_live"):
                self.btn_go_live.setStyleSheet(
                    "QPushButton { background-color: #26272e; color: #ffffff; border: 1.5px solid #ffffff; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 8px; } "
                    "QPushButton:hover { background-color: #383946; }"
                )
            if hasattr(self, "link_box"):
                self.link_box.setStyleSheet(
                    "QFrame { background-color: #1a1b1f; border: 1px solid #33343e; border-radius: 5px; }"
                )
            if hasattr(self, "btn_delete"):
                self.btn_delete.setStyleSheet(
                    "QPushButton { color: #f4f4f5; border: 1.5px solid #525363; background-color: #22232a; font-weight: bold; border-radius: 4px; } "
                    "QPushButton:hover { background-color: #2d2f38; border-color: #f87171; color: #fca5a5; }"
                )
            for mode_val, btn in self._follow_buttons.items():
                btn.setStyleSheet(
                    "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1px solid #3f404d; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 4px; } "
                    "QPushButton:hover:!checked { background-color: #2d2f38; border-color: #525363; color: #ffffff; } "
                    "QPushButton:checked { background-color: #383946; border: 1.5px solid #ffffff; color: #ffffff; } "
                    "QPushButton:disabled { color: #525363; border-color: #27272a; background-color: #141518; }"
                )
        else:
            if hasattr(self, "lbl_count"):
                self.lbl_count.setStyleSheet(
                    f"color: {active_t.accent}; background-color: {active_t.input_bg}; border: 1px solid {active_t.border}; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 1px 6px;"
                )
            if hasattr(self, "btn_go_live"):
                self.btn_go_live.setStyleSheet(
                    "QPushButton { background-color: #064e3b; color: #69f0ae; border: 1px solid #00e676; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 8px; } "
                    "QPushButton:hover { background-color: #047857; color: #ffffff; }"
                )
            if hasattr(self, "link_box"):
                self.link_box.setStyleSheet(
                    f"QFrame {{ background-color: {active_t.input_bg}; border: 1px solid {active_t.border}; border-radius: 5px; }}"
                )
            if hasattr(self, "btn_delete"):
                self.btn_delete.setStyleSheet(
                    "QPushButton { color: #ff8080; border: 1px solid #ff4444; background-color: #401818; font-weight: bold; } "
                    "QPushButton:hover { background-color: #5c2222; }"
                )
            for mode_val, btn in self._follow_buttons.items():
                spec = next((s for s in _FOLLOW_SPECS if s[0] == mode_val), None)
                chk_bg = spec[3] if spec else "#065f46"
                chk_border = spec[4] if spec else "#10b981"
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {active_t.button_bg}; color: {active_t.text_muted}; border: 1px solid {active_t.button_border}; "
                    f"border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0px 4px; }} "
                    f"QPushButton:hover:!checked {{ background-color: {active_t.button_hover_bg}; border-color: {chk_border}; color: #ffffff; }} "
                    f"QPushButton:checked {{ background-color: {chk_bg}; border: 1px solid {chk_border}; color: #ffffff; }} "
                    f"QPushButton:disabled {{ color: #475569; border-color: {active_t.border_subtle}; background-color: {active_t.panel}; }}"
                )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Show the follow-mode hint while hovering a follow button."""
        if event.type() == QEvent.Type.Enter:
            for m, btn in self._follow_buttons.items():
                if obj is btn:
                    self.lbl_follow_hint.setText(self._follow_hints[m])
                    self.lbl_follow_hint.setStyleSheet("color: #cbd5e1; font-size: 11px; border: none; background: transparent;")
                    break
        elif event.type() == QEvent.Type.Leave:
            self._refresh_follow_caption()
        return super().eventFilter(obj, event)

    def _refresh_follow_caption(self) -> None:
        if self._active_follow_mode and self._active_follow_mode in self._follow_hints:
            self.lbl_follow_hint.setText(self._follow_hints[self._active_follow_mode])
            self.lbl_follow_hint.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        else:
            self.lbl_follow_hint.setText("Selezione multipla mista — clicca una modalità per applicarla a tutte")
            self.lbl_follow_hint.setStyleSheet("color: #f59e0b; font-size: 11px; border: none; background: transparent;")

    def set_follow_mode_checked(self, mode: str | None, *, enabled: bool = True) -> None:
        """Highlight the follow-mode button matching *mode*, without emitting.

        ``None`` shows the mixed-selection state; *enabled* disables the row
        when the current cue cannot auto-follow.
        """
        self._active_follow_mode = mode if mode in self._follow_buttons else None
        for m, btn in self._follow_buttons.items():
            btn.blockSignals(True)
            btn.setEnabled(enabled)
            btn.setChecked(enabled and (m == self._active_follow_mode))
            btn.blockSignals(False)
        if not enabled:
            self.lbl_follow_hint.setText("Seleziona una o più cue per scegliere Blocco / Auto-GO / Simultanea")
            self.lbl_follow_hint.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        else:
            self._refresh_follow_caption()

