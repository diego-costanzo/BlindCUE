"""Right-column Tabbed Cue Inspector panel (Cue & Timing tabs, Visual transform/crop, Audio/Loop/Fades)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from models.cue import (
    Cue,
    FollowMode,
    GroupMode,
    MediaType,
    _default_crop,
    _sanitize_hex_color,
    normalize_output_target,
    normalize_rotation,
    sanitize_mask_polygon,
)
from ui.cue_table import format_cue_ref
from ui.spinboxes import InPointSpinBox, OutPointSpinBox, SmartDoubleSpinBox
from ui.theme import CLR_ACCENT, CUE_COLOR_PALETTE, NUDGE_BTN_STYLE, get_active_theme

# Preset index <-> repetition count mapping (0 = infinite loop)
_ACTION_TAB = 4  # index of the "Azione" tab (after Cue·Tempi, Visual, Audio, Gruppo)
_LOOP_PRESET_COUNTS = (0, 2, 3, 4, 5, 10)
_COUNT_TO_PRESET_IDX = {count: idx for idx, count in enumerate(_LOOP_PRESET_COUNTS)}
_LOOP_CUSTOM_IDX = len(_LOOP_PRESET_COUNTS)

_ASPECT_OPTIONS: list[tuple[str, str | None]] = [
    ("Native (Automatico)", None),
    ("16:9 (Widescreen)", "16:9"),
    ("4:3 (Standard)", "4:3"),
    ("21:9 (Ultrawide)", "21:9"),
    ("1:1 (Quadrato)", "1:1"),
]

_LAYER_BTN_SPECS = (
    (1, "L1: Sfondo", "Layer 1 (Default): Livello di sfondo o base scena", "#065f46", "#10b981"),
    (2, "L2: Principale", "Layer 2: Livello multimediale intermedio (sopra L1)", "#075985", "#38bdf8"),
    (3, "L3: Overlay", "Layer 3: Livello superiore in primo piano (grafica, loghi, titoli)", "#78350f", "#f59e0b"),
)

_FOLLOW_MINI_SPECS = (
    (FollowMode.MANUAL.value, "⏹ Blocco", "Attende GO manuale (default)", "#065f46", "#10b981"),
    (FollowMode.AUTO_FOLLOW.value, "⤵ Auto-GO", "Avvia la successiva dopo Pre+Durata+Post", "#0c4a6e", "#38bdf8"),
    (FollowMode.SIMULTANEOUS.value, "⇉ Simult.", "Avvia insieme la successiva sul GO", "#78350f", "#f59e0b"),
)

_GROUP_MODE_SPECS = (
    ("SIMULTANEOUS", "⇉ Simultaneo", "Fire All: tutti i media del gruppo partono contemporaneamente sul GO.", "#065f46", "#10b981"),
    ("SEQUENCE", "⤵ Sequenziale", "Cascata: un solo GO lancia tutta la sequenza interna rispettando i ritardi Pre/Durata/Post.", "#0c4a6e", "#38bdf8"),
    ("STEP", "⏹ Passo-Passo", "Capitolo teatrale: ogni pressione manuale di GO avanza di un elemento all'interno della scena.", "#312e81", "#818cf8"),
    ("RANDOM", "🎲 Random / Var.", "Sceglie a caso un elemento del gruppo evitando la ripetizione immediata.", "#701a75", "#f472b6"),
    ("LOOP", "🔁 Loop Scena", "Cicla continuamente tutti gli elementi interni finché non viene dato lo stop.", "#78350f", "#f59e0b"),
)


def _make_layer_btn_style(checked_bg: str, checked_border: str, is_mono: bool = False) -> str:
    """Return tactile toggle button styling with clear hover and active selection border."""
    if is_mono:
        idle_bg = "#22232a"
        idle_color = "#d4d4d8"
        idle_border = "#3f404d"
        hover_bg = "#2d2f38"
        hover_border = "#525363"
        pressed_bg = "#18191f"
        checked_bg = "#383946"
        checked_border = "#ffffff"
    else:
        idle_bg = "#182231"
        idle_color = "#cbd5e1"
        idle_border = "#3c4f6b"
        hover_bg = "#24334a"
        hover_border = checked_border
        pressed_bg = "#111924"

    return f"""
        QPushButton {{
            background-color: {idle_bg};
            color: {idle_color};
            border: 1px solid {idle_border};
            border-bottom: 2px solid {idle_border};
            border-radius: 5px;
            padding: 3px 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        QPushButton:hover:!checked {{
            background-color: {hover_bg};
            border: 1px solid {hover_border};
            border-bottom: 2px solid {hover_border};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background-color: {pressed_bg};
        }}
        QPushButton:checked {{
            background-color: {checked_bg};
            border: 2px solid {checked_border};
            color: #ffffff;
        }}
        QPushButton:disabled, QPushButton:checked:disabled {{
            background-color: #0e131c;
            border: 1px solid #1e2736;
            color: #475569;
        }}
    """


def _make_swatch_style(hex_color: str) -> str:
    """Return circular/pill colour swatch button style with bright white active ring."""
    fill = hex_color if hex_color else "#1a2332"
    border_idle = hex_color if hex_color else "#475569"
    return f"""
        QPushButton {{
            background-color: {fill};
            border: 1px solid {border_idle};
            border-radius: 4px;
            color: #94a3b8;
            font-size: 10px;
            font-weight: bold;
            padding: 0px;
        }}
        QPushButton:hover:!checked {{
            border: 2px solid #cbd5e1;
        }}
        QPushButton:checked {{
            border: 2.5px solid #ffffff;
            color: #ffffff;
        }}
        QPushButton:disabled {{
            background-color: #111722;
            border-color: #1e293b;
            color: #334155;
        }}
    """


_UNIT_PILL_STYLE = f"""
    QPushButton {{
        background-color: #182230;
        color: #94a3b8;
        border: 1px solid #2b3b52;
        border-radius: 4px;
        padding: 1px 8px;
        font-size: 10px;
        font-weight: bold;
        min-width: 28px;
        height: 22px;
    }}
    QPushButton:hover:!checked {{
        background-color: #223146;
        border-color: {CLR_ACCENT};
        color: #ffffff;
    }}
    QPushButton:checked {{
        background-color: #075985;
        border: 1px solid {CLR_ACCENT};
        color: #ffffff;
    }}
    QPushButton:disabled {{
        background-color: #0e131c;
        border-color: #1e2736;
        color: #475569;
    }}
"""


class CueInspectorPanel(QGroupBox):
    """Tabbed Cue Properties Inspector organized into Cue & Timing, Visual Transform/Crop, and Audio/Loop."""

    value_changed = Signal()
    marker_delete_requested = Signal(int)  # 2.7: delete this marker of the cue
    batch_field_edited = Signal(str)
    layer_selected = Signal(int)
    output_target_selected = Signal(str)
    in_out_reset_requested = Signal()
    silence_trim_requested = Signal()  # 3.4: IN/OUT where the sound really starts and ends
    color_selected = Signal(str)
    follow_mode_selected = Signal(str)
    group_mode_selected = Signal(str)
    group_collapse_toggled = Signal()
    ungroup_requested = Signal()
    remove_child_requested = Signal(int)
    extract_child_requested = Signal()
    open_group_timeline_requested = Signal()
    scan_loudness_requested = Signal()
    normalize_cue_toggled = Signal(bool)
    optimize_dynamics_requested = Signal()
    restore_original_requested = Signal()
    open_surface_mapping_requested = Signal()
    mask_edit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the cue inspector in its empty (no selection) state."""
        super().__init__("ISPETTORE CUE (Nessuna cue selezionata)", parent)
        self._updating: bool = False
        self._multi_mode: bool = False
        self._crop_unit: str = "pct"   # "pct" (%) or "px" (pixels)
        self._crop_ref_w: int = 1920
        self._crop_ref_h: int = 1080
        self._norm_crop: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._mask_polygon: list[list[float]] = []
        self._current_media_type: MediaType | None = None
        self._layer_buttons: dict[int, QPushButton] = {}
        self._output_buttons: dict[str, QPushButton] = {}
        self._color_buttons: dict[str, QPushButton] = {}
        self._follow_buttons: dict[str, QPushButton] = {}
        self._group_color_buttons: dict[str, QPushButton] = {}
        self._group_mode_buttons: dict[str, QPushButton] = {}

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(360)
        self._build_ui()
        self._connect_signals()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Smallest size where the inspector controls stay usable."""
        return QSize(360, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Preferred size of the inspector panel."""
        return QSize(400, 560)

    def _set_elided_title(self, full_title: str) -> None:
        from i18n import tr

        # Translate before eliding: a cut title ("…") no longer matches its
        # translation template.
        full_title = tr(full_title)
        self.setToolTip(full_title)
        avail = max(260, self.width() - 32)
        elided = QFontMetrics(self.font()).elidedText(
            full_title, Qt.TextElideMode.ElideRight, avail
        )
        super().setTitle(elided)

    def setTitle(self, title: str) -> None:  # noqa: N802
        """Set the panel title, eliding it when it does not fit."""
        self._set_elided_title(title)

    # ── UI Construction Helpers ───────────────────────────────────────

    @staticmethod
    def _make_card(title: str, guide: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("inspCard")
        card.setMinimumWidth(0)
        is_mono = get_active_theme().is_monochrome
        card_bg = "#1a1b1f" if is_mono else "#101723"
        card_border = "#33343e" if is_mono else "#223044"
        card.setStyleSheet(
            f"QFrame#inspCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(5)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("inspCardTitle")
        lbl_title.setMinimumWidth(0)
        lbl_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        active_t = get_active_theme()
        lbl_title.setStyleSheet(
            f"color: {active_t.accent}; font-size: 10px; font-weight: bold; letter-spacing: 0.4px; border: none; background: transparent;"
        )
        lay.addWidget(lbl_title)
        if guide:
            lbl_guide = QLabel(guide)
            lbl_guide.setWordWrap(True)
            lbl_guide.setMinimumWidth(0)
            lbl_guide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            lbl_guide.setStyleSheet(
                "color: #7c8fa6; font-size: 9px; border: none; background: transparent;"
            )
            lay.addWidget(lbl_guide)
        return card, lay

    @staticmethod
    def _make_field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        return lbl

    @staticmethod
    def _wrap_tab_scroll(inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(inner)
        return scroll

    def _make_slider_row(
        self, title: str, min_v: int, max_v: int, init_v: int, label_init: str, reset_tip: str
    ) -> tuple[QHBoxLayout, QSlider, QLabel, QPushButton]:
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl_t = self._make_field_label(title)
        lbl_t.setFixedWidth(56)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_v)
        slider.setMinimumWidth(80)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        slider.setAccessibleName(f"Regolazione {title.rstrip(':')}")
        slider.setAccessibleDescription(f"Cursore orizzontale da {min_v} a {max_v}.")
        val_lbl = QLabel(label_init)
        val_lbl.setFixedWidth(40)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setStyleSheet("color: #e2e8f0; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent;")
        btn_rst = self._make_reset_icon_btn(reset_tip)
        btn_rst.setAccessibleName(f"Ripristina {title.rstrip(':')}")
        row.addWidget(lbl_t)
        row.addWidget(slider, 1)
        row.addWidget(val_lbl)
        row.addWidget(btn_rst)
        return row, slider, val_lbl, btn_rst

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 8, 6, 6)
        outer.setSpacing(6)

        self.lbl_multi_banner = QLabel()
        self.lbl_multi_banner.setWordWrap(True)
        self.lbl_multi_banner.setMinimumWidth(0)
        self.lbl_multi_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lbl_multi_banner.setVisible(False)
        outer.addWidget(self.lbl_multi_banner)

        self.tab_widget = QTabWidget()
        self.tab_widget.setAccessibleName("Pannello Ispettore Cue - Schede")
        self.tab_widget.setAccessibleDescription("Schede proprietà: Info e Tempi, Video e Foto, Audio e Tagli, Gruppo.")
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.tabBar().setExpanding(True)
        self.tab_widget.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        outer.addWidget(self.tab_widget, stretch=1)

        # Basic mode (view variant Lite, C2b): what is hidden but changes the
        # playback is said in one line; "More settings" opens the same inspector.
        self.lbl_also = QLabel()
        self.lbl_also.setWordWrap(True)
        self.lbl_also.setStyleSheet("QLabel { color: #cbd5e1; font-size: 12px; padding: 2px 4px; }")
        self.lbl_also.setVisible(False)
        outer.addWidget(self.lbl_also)
        self.btn_more = QPushButton("▾ Più impostazioni")
        self.btn_more.setFixedHeight(28)
        self.btn_more.setToolTip("Mostra tutte le schede di questa cue nello stesso posto. Il layout della finestra non cambia.")
        self.btn_more.clicked.connect(self._on_more_clicked)
        self.btn_more.setVisible(False)
        outer.addWidget(self.btn_more)
        self._lite = False          # the window's view variant is Lite
        self._expanded = False      # "More settings" opened in Lite
        self._last_enable_args: tuple = (False, None, False)

        self._build_tab_cue_and_timing()
        self._build_tab_visual()
        self._build_tab_audio_and_cuts()
        self._build_tab_group()
        self._build_tab_action()
        self.tab_widget.setTabVisible(3, False)
        self.tab_widget.setTabVisible(_ACTION_TAB, False)

    # ── Tab 5: Action cue (stop, fade, level, opacity, note) ─────────

    def _build_tab_action(self) -> None:
        from ui.action_cue_editor import ActionCueEditor

        self.action_editor = ActionCueEditor()
        self.action_editor.changed.connect(lambda: self._emit_change("action_spec"))
        self.tab_action = self._wrap_tab_scroll(self.action_editor)
        self.tab_widget.addTab(self.tab_action, "⚡ Azione")

    def set_cue_catalog_provider(self, provider) -> None:
        """Function returning the show's cues (targets offered by the action tab)."""
        self.action_editor.set_catalog_provider(provider)

    def show_action_tab(self) -> None:
        """Bring the action settings to the front (new action cue)."""
        if self.tab_widget.isTabVisible(_ACTION_TAB):
            self.tab_widget.setCurrentIndex(_ACTION_TAB)

    # ── Tab 1: Cue, Colore, Layer & Tempi (Pre / Durata / Post) ──────

    def _build_tab_cue_and_timing(self) -> None:
        page = QWidget()
        page.setMinimumWidth(0)
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(6)

        # Card 1: Identità in Copione & Colore Gruppo
        c1, l1 = self._make_card(
            "1 · IDENTITÀ IN COPIONE & COLORE GRUPPO",
            "I box scuri sono modificabili; usa un colore per dividere scene o atti in Scaletta.",
        )
        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(6)
        grid1.setVerticalSpacing(5)

        grid1.addWidget(self._make_field_label("Q (Copione):"), 0, 0)
        self.edit_cue_q = QLineEdit()
        self.edit_cue_q.setMinimumWidth(40)
        self.edit_cue_q.setPlaceholderText("es. Q-2, Q-9a, Sc.1...")
        self.edit_cue_q.setToolTip("Sigla di copione: resta legata alla cue anche se riordini la scaletta")
        self.edit_cue_q.setAccessibleName("Sigla Q Copione")
        self.edit_cue_q.setAccessibleDescription("Identificativo o sigla di copione della cue.")
        grid1.addWidget(self.edit_cue_q, 0, 1)

        grid1.addWidget(self._make_field_label("Nome Cue:"), 1, 0)
        self.edit_cue_name = QLineEdit()
        self.edit_cue_name.setMinimumWidth(40)
        self.edit_cue_name.setPlaceholderText("Titolo descrittivo in scaletta...")
        self.edit_cue_name.setAccessibleName("Nome Cue")
        self.edit_cue_name.setAccessibleDescription("Titolo o etichetta descrittiva della cue nella scaletta.")
        grid1.addWidget(self.edit_cue_name, 1, 1)

        grid1.addWidget(self._make_field_label("Note Regia:"), 2, 0)
        self.edit_cue_notes = QLineEdit()
        self.edit_cue_notes.setMinimumWidth(40)
        self.edit_cue_notes.setPlaceholderText("Attacco battuta, luci, note tecniche...")
        self.edit_cue_notes.setAccessibleName("Note di Regia")
        self.edit_cue_notes.setAccessibleDescription("Note tecniche o didascalie per l'operatore di regia.")
        grid1.addWidget(self.edit_cue_notes, 2, 1)
        grid1.addWidget(self._make_field_label("Copione:"), 3, 0)
        script_row = QHBoxLayout()
        self.edit_script_page = QLineEdit()
        self.edit_script_page.setMaxLength(20)
        self.edit_script_page.setFixedWidth(52)
        self.edit_script_page.setPlaceholderText("pag.")
        self.edit_script_page.setAccessibleName("Pagina del copione")
        self.edit_script_line = QLineEdit()
        self.edit_script_line.setMaxLength(300)
        self.edit_script_line.setPlaceholderText("Battuta su cui parte…")
        self.edit_script_line.setAccessibleName("Battuta su cui parte la cue")
        script_row.addWidget(self.edit_script_page)
        script_row.addWidget(self.edit_script_line, 1)
        grid1.addLayout(script_row, 3, 1)
        grid1.setColumnStretch(1, 1)
        l1.addLayout(grid1)

        color_row = QHBoxLayout()
        color_row.setSpacing(4)
        lbl_clr = self._make_field_label("Colore:")
        lbl_clr.setFixedWidth(48)
        color_row.addWidget(lbl_clr)
        for hex_val, clr_tip in CUE_COLOR_PALETTE:
            btn = QPushButton("✕" if not hex_val else "")
            btn.setCheckable(True)
            btn.setFixedSize(24, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"Colore Cue: {clr_tip}")
            btn.setStyleSheet(_make_swatch_style(hex_val))
            btn.clicked.connect(lambda _=False, hv=hex_val: self.color_selected.emit(hv))
            color_row.addWidget(btn)
            self._color_buttons[hex_val] = btn
        color_row.addStretch()
        l1.addLayout(color_row)

        # Banner for cues belonging to a parent group
        self.frame_group_membership = QFrame()
        self.frame_group_membership.setStyleSheet(
            "background-color: #1e1533; border: 1px solid #7c3aed; border-radius: 4px; padding: 2px;"
        )
        mbr_layout = QHBoxLayout(self.frame_group_membership)
        mbr_layout.setContentsMargins(6, 3, 6, 3)
        mbr_layout.setSpacing(6)

        self.lbl_group_membership = QLabel("📁 In Scena")
        self.lbl_group_membership.setStyleSheet("color: #c084fc; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        mbr_layout.addWidget(self.lbl_group_membership, stretch=1)

        self.btn_extract_from_group = QPushButton("⏏ Estrai dal Gruppo")
        self.btn_extract_from_group.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_extract_from_group.setToolTip("Rimuove questa cue dal gruppo e la sposta all'esterno della scena (Ctrl+Shift+G)")
        self.btn_extract_from_group.setStyleSheet(
            "QPushButton { background-color: #3b1d6e; color: #f3e8ff; border: 1px solid #a855f7; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px 6px; } "
            "QPushButton:hover { background-color: #581c87; color: #ffffff; border-color: #c084fc; }"
        )
        self.btn_extract_from_group.clicked.connect(self.extract_child_requested)
        mbr_layout.addWidget(self.btn_extract_from_group)

        self.frame_group_membership.setVisible(False)
        l1.addWidget(self.frame_group_membership)
        lay.addWidget(c1)

        # Card 2: Layer di Compositing
        c2, l2 = self._make_card(
            "2 · LAYER DI USCITA (SOVRAPPOSIZIONE)",
            "Ordine visivo sullo schermo: L3 (sopra) → L2 → L1 → L0 Tappo di sicurezza.",
        )
        layer_row = QHBoxLayout()
        layer_row.setSpacing(4)
        for layer_idx, label, tooltip, bg, border in _LAYER_BTN_SPECS:
            btn = QPushButton(label)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedHeight(27)
            btn.setMinimumWidth(0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_make_layer_btn_style(bg, border).replace("font-size: 11px;", "font-size: 10px;"))
            layer_row.addWidget(btn, 1)
            self._layer_buttons[layer_idx] = btn
        self.btn_layer1 = self._layer_buttons[1]
        self.btn_layer2 = self._layer_buttons[2]
        self.btn_layer3 = self._layer_buttons[3]
        l2.addLayout(layer_row)

        # Output routing (A = first projector, B = optional second projector).
        # Hidden unless the operator enables the "two independent outputs" mode.
        self.frame_output_target = QWidget()
        out_row = QHBoxLayout(self.frame_output_target)
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(4)
        lbl_out = QLabel("Proiettore:")
        lbl_out.setStyleSheet("color: #94a3b8; font-size: 10px; border: none; background: transparent;")
        out_row.addWidget(lbl_out)
        for target, text, tip in (
            ("A", "A · Schermo 1", "Questa cue viene proiettata dall'uscita A (primo proiettore)."),
            ("B", "B · Schermo 2", "Questa cue viene proiettata dall'uscita B (secondo proiettore indipendente)."),
        ):
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_make_layer_btn_style("#1e3a5f", "#38bdf8").replace("font-size: 11px;", "font-size: 10px;"))
            btn.clicked.connect(lambda _=False, t=target: self._on_output_target_clicked(t))
            out_row.addWidget(btn, 1)
            self._output_buttons[target] = btn
        self.frame_output_target.setVisible(False)
        l2.addWidget(self.frame_output_target)

        self.lbl_layer_conflict = QLabel()
        self.lbl_layer_conflict.setWordWrap(True)
        self.lbl_layer_conflict.setStyleSheet(
            "background-color: #3b1d07; color: #fde047; border: 1px solid #d97706; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px 6px;"
        )
        self.lbl_layer_conflict.setVisible(False)
        l2.addWidget(self.lbl_layer_conflict)

        self.card_layer = c2
        lay.addWidget(c2)

        # Card 3: Incastro Temporale (Pre · Durata · Post) & Sequenza
        c3, l3 = self._make_card("3 · TEMPI DI INCASTRO (PRE · DURATA · POST)")
        self._pipe_lbl = QLabel("GO  ▶  [⏳ Pre]  ▶  [▶ Media / Durata]  ▶  [⏱ Post]")
        self._pipe_lbl.setWordWrap(True)
        self._pipe_lbl.setMinimumWidth(0)
        self._pipe_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self._pipe_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l3.addWidget(self._pipe_lbl)

        timing_grid = QGridLayout()
        timing_grid.setHorizontalSpacing(6)
        timing_grid.setVerticalSpacing(5)

        self.lbl_pre_field = self._make_field_label("Pre-Delay:")
        timing_grid.addWidget(self.lbl_pre_field, 0, 0)
        self.spin_pre_delay = SmartDoubleSpinBox()
        self.spin_pre_delay.setMinimumWidth(68)
        self.spin_pre_delay.setRange(0.0, 3600.0)
        self.spin_pre_delay.setDecimals(1)
        self.spin_pre_delay.setSingleStep(0.5)
        self.spin_pre_delay.setSuffix(" s")
        self.spin_pre_delay.setToolTip("Ritardo di partenza dopo il GO per incastrare la cue con altri layer")
        self.spin_pre_delay.setAccessibleName("Ritardo di Partenza Pre-Delay")
        self.spin_pre_delay.setAccessibleDescription("Secondi di ritardo dopo il GO prima dell'avvio della cue.")
        timing_grid.addWidget(self.spin_pre_delay, 0, 1)

        self.lbl_post_field = self._make_field_label("Post-Delay:")
        timing_grid.addWidget(self.lbl_post_field, 0, 2)
        self.spin_post_delay = SmartDoubleSpinBox()
        self.spin_post_delay.setMinimumWidth(68)
        self.spin_post_delay.setRange(0.0, 3600.0)
        self.spin_post_delay.setDecimals(1)
        self.spin_post_delay.setSingleStep(0.5)
        self.spin_post_delay.setSuffix(" s")
        self.spin_post_delay.setToolTip("Attesa extra dopo la fine del media prima di uscire o passare alla successiva")
        self.spin_post_delay.setAccessibleName("Attesa Finale Post-Delay")
        self.spin_post_delay.setAccessibleDescription("Secondi di attesa dopo il termine del media.")
        timing_grid.addWidget(self.spin_post_delay, 0, 3)

        self.lbl_hold_field = self._make_field_label("Durata Img:")
        timing_grid.addWidget(self.lbl_hold_field, 1, 0)
        self.spin_hold_time = SmartDoubleSpinBox()
        self.spin_hold_time.setMinimumWidth(68)
        self.spin_hold_time.setRange(0.0, 99999.0)
        self.spin_hold_time.setDecimals(1)
        self.spin_hold_time.setSingleStep(0.5)
        self.spin_hold_time.setSuffix(" s")
        self.spin_hold_time.setSpecialValueText("0 s (∞)")
        self.spin_hold_time.setToolTip("Durata di permanenza in Live delle immagini statiche (0 = infinita)")
        self.spin_hold_time.setAccessibleName("Durata Immagine Hold Time")
        self.spin_hold_time.setAccessibleDescription("Durata in secondi per le immagini statiche (0 = infinita).")
        timing_grid.addWidget(self.spin_hold_time, 1, 1)

        self.lbl_hold_hint = QLabel("Solo immagini (0 = ∞)")
        self.lbl_hold_hint.setMinimumWidth(0)
        self.lbl_hold_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_hold_hint.setStyleSheet("color: #64748b; font-size: 10px; border: none; background: transparent;")
        timing_grid.addWidget(self.lbl_hold_hint, 1, 2, 1, 2)
        timing_grid.setColumnStretch(1, 1)
        timing_grid.setColumnStretch(3, 1)
        l3.addLayout(timing_grid)

        seq_row = QHBoxLayout()
        seq_row.setSpacing(4)
        seq_lbl = self._make_field_label("Dopo:")
        seq_row.addWidget(seq_lbl)
        for mode_val, label, tip, bg, border in _FOLLOW_MINI_SPECS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumWidth(0)
            btn.setFixedHeight(23)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: #161f2d; color: #94a3b8; border: 1px solid #2b3a4f; "
                f"border-radius: 4px; font-size: 9px; font-weight: bold; padding: 0px 3px; }} "
                f"QPushButton:hover:!checked {{ background-color: #202e42; border-color: {border}; color: #ffffff; }} "
                f"QPushButton:checked {{ background-color: {bg}; border: 1px solid {border}; color: #ffffff; }} "
                f"QPushButton:disabled {{ background-color: #0e131c; color: #475569; border-color: #1a2230; }}"
            )
            btn.clicked.connect(lambda _=False, m=mode_val: self.follow_mode_selected.emit(m))
            self._follow_buttons[mode_val] = btn
            seq_row.addWidget(btn, 1)
        l3.addLayout(seq_row)
        self.chk_exclusive = QCheckBox("⛔ Esclusiva: blocca il GO finché è in onda")
        self.chk_exclusive.setToolTip(
            "Mentre questa cue è in onda il GO manuale viene rifiutato (anche da remoto), "
            "così un GO dato per errore non la copre. Ctrl+Spazio forza comunque il GO.\n"
            "Attenzione: un'immagine senza durata resta in onda finché non viene fermata."
        )
        self.chk_exclusive.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_exclusive.toggled.connect(lambda _c: self._emit_change("exclusive"))
        l3.addWidget(self.chk_exclusive)
        self.chk_confirm = QCheckBox("✋ Aspetta l'OK: parte solo dopo la conferma")
        self.chk_confirm.setToolTip(
            "Il GO su questa cue la prepara e aspetta l'OK: Invio sulla lista, il pulsante OK "
            "o il GO del telecomando nel telefono. Se nel frattempo parte un'altra cue, l'attesa decade."
        )
        self.chk_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_confirm.toggled.connect(lambda _c: self._emit_change("confirm_start"))
        l3.addWidget(self.chk_confirm)
        # 1.16: change of music in one cue – what else plays fades out.
        fo_row = QHBoxLayout()
        self.lbl_fade_others = self._make_field_label("All'avvio sfuma le altre:")
        fo_row.addWidget(self.lbl_fade_others)
        self.spin_fade_others = SmartDoubleSpinBox()
        self.spin_fade_others.setRange(0.0, 60.0)
        self.spin_fade_others.setDecimals(1)
        self.spin_fade_others.setSingleStep(0.5)
        self.spin_fade_others.setSuffix(" s")
        self.spin_fade_others.setSpecialValueText("no")
        self.spin_fade_others.setToolTip(
            "Quando questa cue parte, gli altri suoni e video in onda sfumano in questi secondi "
            "(cambio di musica con una sola cue). Una musica sullo stesso layer sfuma invece di "
            "essere tagliata. 0 = no.")
        self.spin_fade_others.valueChanged.connect(lambda _v: self._emit_change("fade_others"))
        fo_row.addWidget(self.spin_fade_others)
        fo_row.addStretch(1)
        l3.addLayout(fo_row)
        # 1.7: an effect on demand (bell, thunder): outside the GO order, on a key or a tile.
        fx_row = QHBoxLayout()
        self.chk_adlib = QCheckBox("🎵 Effetto a richiesta (fuori dall'ordine del GO)")
        self.chk_adlib.setToolTip(
            "Il GO lo salta; parte dal suo tasto o dalla sua piastrella in «Ora in onda», "
            "su un lettore libero, senza spostare il GO e senza fermare ciò che suona.")
        self.chk_adlib.toggled.connect(lambda _c: self._emit_change("adlib"))
        fx_row.addWidget(self.chk_adlib)
        l3.addLayout(fx_row)
        key_row = QHBoxLayout()
        self.lbl_hotkey = self._make_field_label("Tasto:")
        key_row.addWidget(self.lbl_hotkey)
        self.edit_hotkey = QLineEdit()
        self.edit_hotkey.setMaxLength(1)
        self.edit_hotkey.setFixedWidth(40)
        self.edit_hotkey.setValidator(QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9]?"), self.edit_hotkey))
        self.edit_hotkey.setToolTip("Una lettera o una cifra; nella prova e nello spettacolo fa partire l'effetto. "
                                    "Più cue sullo stesso tasto partono una dopo l'altra (passi).")
        self.edit_hotkey.setAccessibleName("Tasto dell'effetto")
        self.edit_hotkey.editingFinished.connect(lambda: self._emit_change("hotkey"))
        key_row.addWidget(self.edit_hotkey)
        self.combo_hotkey_mode = QComboBox()
        for value, label in (("trigger", "Avvia (di nuovo = da capo)"), ("toggle", "Avvia / ferma"),
                             ("note", "Suona finché tieni premuto"),
                             ("once", "Avvia (di nuovo = niente finché suona)")):
            self.combo_hotkey_mode.addItem(label, value)
        self.combo_hotkey_mode.currentIndexChanged.connect(lambda _i: self._emit_change("hotkey_mode"))
        key_row.addWidget(self.combo_hotkey_mode, stretch=1)
        l3.addLayout(key_row)
        # 2.2: started only by a "call" action, never by GO.
        self.chk_call_only = QCheckBox("📞 Solo su chiamata (fuori dall'ordine del GO)")
        self.chk_call_only.setToolTip("La avvia soltanto un'azione «Chiama una cue» (o un salto); il GO la salta.")
        self.chk_call_only.toggled.connect(lambda _c: self._emit_change("call_only"))
        l3.addWidget(self.chk_call_only)
        self.lbl_callers = QLabel("")
        self.lbl_callers.setWordWrap(True)
        self.lbl_callers.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_callers.setVisible(False)
        l3.addWidget(self.lbl_callers)
        # 2.1: the cue starts by itself, relative to another cue (outside the GO order).
        rel_row = QHBoxLayout()
        self.lbl_rel = self._make_field_label("Partenza:")
        rel_row.addWidget(self.lbl_rel)
        self.combo_rel_when = QComboBox()
        for value, label in (("", "con il GO"), ("start", "dopo l'avvio di"), ("end", "dopo la fine di"),
                             ("before_end", "prima della fine di"), ("marker", "al segno di")):
            self.combo_rel_when.addItem(label, value)
        self.combo_rel_when.setAccessibleName("Partenza della cue")
        self.combo_rel_when.setToolTip(
            "Con il GO: come sempre. Le altre scelte fanno partire questa cue da sola rispetto a un'altra "
            "(il GO la salta): N s dopo il suo avvio, N s dopo la sua fine, o N s prima della sua fine.")
        self.combo_rel_when.currentIndexChanged.connect(lambda _i: self._on_rel_changed())
        rel_row.addWidget(self.combo_rel_when)
        self.combo_rel_cue = QComboBox()
        self.combo_rel_cue.setMinimumWidth(120)
        self.combo_rel_cue.setAccessibleName("Cue di riferimento")
        self.combo_rel_cue.currentIndexChanged.connect(lambda _i: self._on_rel_changed())
        rel_row.addWidget(self.combo_rel_cue, stretch=1)
        self.combo_rel_marker = QComboBox()  # 2.7: the marker of the reference cue
        self.combo_rel_marker.setAccessibleName("Segno della cue di riferimento")
        self.combo_rel_marker.currentIndexChanged.connect(lambda _i: self._on_rel_changed())
        rel_row.addWidget(self.combo_rel_marker)
        self.spin_rel_offset = SmartDoubleSpinBox()
        self.spin_rel_offset.setRange(0.0, 600.0)
        self.spin_rel_offset.setDecimals(1)
        self.spin_rel_offset.setSingleStep(0.5)
        self.spin_rel_offset.setSuffix(" s")
        self.spin_rel_offset.setAccessibleName("Secondi rispetto alla cue di riferimento")
        self.spin_rel_offset.valueChanged.connect(lambda _v: self._on_rel_changed())
        rel_row.addWidget(self.spin_rel_offset)
        l3.addLayout(rel_row)
        clock_row = QHBoxLayout()
        self.lbl_clock = self._make_field_label("Alle ore:")
        clock_row.addWidget(self.lbl_clock)
        self.edit_clock = QLineEdit()
        self.edit_clock.setPlaceholderText("19:55")
        self.edit_clock.setFixedWidth(80)
        self.edit_clock.setValidator(QRegularExpressionValidator(
            QRegularExpression(r"^$|^([01]?\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"), self.edit_clock))
        self.edit_clock.setToolTip("2.6: la cue parte da sola a quest'ora durante lo spettacolo (il GO la salta). "
                                   "Più di un minuto in ritardo: saltata. Vuoto = con il GO.")
        self.edit_clock.setAccessibleName("Ora di partenza della cue")
        self.edit_clock.editingFinished.connect(lambda: self._emit_change("start_clock"))
        clock_row.addWidget(self.edit_clock)
        clock_row.addStretch(1)
        l3.addLayout(clock_row)
        self.lbl_rel_hint = QLabel("")
        self.lbl_rel_hint.setWordWrap(True)
        self.lbl_rel_hint.setStyleSheet("color: #fbbf24;")
        self.lbl_rel_hint.setVisible(False)
        l3.addWidget(self.lbl_rel_hint)
        self._rel_choices: list[tuple[int, str]] = []
        # 2.7: the markers of this cue (added on the waveform or with Ctrl+K)
        mk_row = QHBoxLayout()
        self.lbl_markers = self._make_field_label("Segni:")
        mk_row.addWidget(self.lbl_markers)
        self.combo_markers = QComboBox()
        self.combo_markers.setAccessibleName("Segni della cue")
        mk_row.addWidget(self.combo_markers, stretch=1)
        self.btn_marker_delete = QPushButton("✕")
        self.btn_marker_delete.setFixedWidth(28)
        self.btn_marker_delete.setToolTip("Elimina il segno scelto (non se una cue parte da lì)")
        self.btn_marker_delete.clicked.connect(
            lambda: self.combo_markers.currentData() is not None
            and self.marker_delete_requested.emit(int(self.combo_markers.currentData())))
        mk_row.addWidget(self.btn_marker_delete)
        l3.addLayout(mk_row)
        self.relative_cycle_check = None  # set by the window: (cue_id, ref_id) -> True for a loop
        self._sync_rel_enabled()
        lay.addWidget(c3)
        lay.addStretch()

        self.tab_cue_timing = self._wrap_tab_scroll(page)
        self.tab_widget.addTab(self.tab_cue_timing, "🎯 Cue · Tempi")

    # ── Tab 2: Video & Immagine (Posizione, Scala, Opacità, Ritaglio) ──

    def _build_tab_visual(self) -> None:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(6, 7, 6, 7)
        lay.setSpacing(7)

        self.lbl_visual_guide = QLabel(
            "Suggerimento: puoi anche trascinare il riquadro o gli 8 bordi direttamente sull'Anteprima Pre-Viz 16:9."
        )
        self.lbl_visual_guide.setWordWrap(True)
        self.lbl_visual_guide.setMinimumWidth(0)
        self.lbl_visual_guide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lbl_visual_guide.setStyleSheet(
            "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; "
            "border-radius: 5px; font-size: 11px; padding: 6px 10px;"
        )
        lay.addWidget(self.lbl_visual_guide)

        c1, l1 = self._make_card("1 · POSIZIONAMENTO, ZOOM & TRASPARENZA")

        surf_row = QHBoxLayout()
        surf_row.setSpacing(8)
        lbl_surf = self._make_field_label("Superficie:")
        lbl_surf.setFixedWidth(64)
        surf_row.addWidget(lbl_surf)
        self.combo_surface = QComboBox()
        self.combo_surface.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_surface.setToolTip("Assegna la cue a uno schermo virtuale o superficie di proiezione/mapping")
        self.combo_surface.currentIndexChanged.connect(lambda: self._on_field_edited("surface_id"))
        surf_row.addWidget(self.combo_surface, stretch=1)
        self.btn_manage_surfaces = self._make_nudge_btn("📐 Gestisci...", "Apri lo Studio Superfici di Proiezione & Video Mapping (F7)")
        self.btn_manage_surfaces.clicked.connect(self.open_surface_mapping_requested.emit)
        surf_row.addWidget(self.btn_manage_surfaces)
        l1.addLayout(surf_row)

        pos_grid = QGridLayout()
        pos_grid.setHorizontalSpacing(8)
        pos_grid.addWidget(self._make_field_label("Pos X:"), 0, 0)
        self.spin_pos_x = SmartDoubleSpinBox()
        self.spin_pos_x.setRange(-2.0, 2.0)
        self.spin_pos_x.setSingleStep(0.01)
        self.spin_pos_x.setDecimals(2)
        self.spin_pos_x.setToolTip("Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx)")
        pos_grid.addWidget(self.spin_pos_x, 0, 1)

        pos_grid.addWidget(self._make_field_label("Pos Y:"), 0, 2)
        self.spin_pos_y = SmartDoubleSpinBox()
        self.spin_pos_y.setRange(-2.0, 2.0)
        self.spin_pos_y.setSingleStep(0.01)
        self.spin_pos_y.setDecimals(2)
        self.spin_pos_y.setToolTip("Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso)")
        pos_grid.addWidget(self.spin_pos_y, 0, 3)
        pos_grid.setColumnStretch(1, 1)
        pos_grid.setColumnStretch(3, 1)
        l1.addLayout(pos_grid)

        nudge_row = QHBoxLayout()
        nudge_row.setSpacing(4)
        self.btn_nudge_left = self._make_nudge_btn("◀", "Sposta a sinistra (-0.01)")
        self.btn_nudge_up = self._make_nudge_btn("▲", "Sposta in alto (-0.01)")
        self.btn_nudge_down = self._make_nudge_btn("▼", "Sposta in basso (+0.01)")
        self.btn_nudge_right = self._make_nudge_btn("▶", "Sposta a destra (+0.01)")
        self.btn_pos_center = self._make_nudge_btn("⌖ Centro", "Ripristina posizione al centro (0.00, 0.00)")
        for btn, st in (
            (self.btn_nudge_left, 1), (self.btn_nudge_up, 1),
            (self.btn_nudge_down, 1), (self.btn_nudge_right, 1), (self.btn_pos_center, 2),
        ):
            nudge_row.addWidget(btn, st)
        l1.addLayout(nudge_row)

        sc_row, self.slider_scale, self.lbl_scale, self.btn_scale_reset = self._make_slider_row(
            "Scala:", 10, 500, 100, "1.0x", "Ripristina scala a 1.0x"
        )
        l1.addLayout(sc_row)

        op_row, self.slider_opacity, self.lbl_opacity, self.btn_opacity_reset = self._make_slider_row(
            "Opacità:", 0, 100, 100, "100%", "Ripristina opacità al 100%"
        )
        l1.addLayout(op_row)

        ar_row = QHBoxLayout()
        ar_row.setSpacing(8)
        lbl_ar = self._make_field_label("Formato:")
        lbl_ar.setFixedWidth(56)
        ar_row.addWidget(lbl_ar)
        self.combo_aspect = QComboBox()
        self.combo_aspect.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_aspect.setMinimumContentsLength(10)
        self.combo_aspect.setMinimumWidth(80)
        self.combo_aspect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_aspect.setToolTip("Forza le proporzioni del riquadro in Anteprima e Live")
        for label, value in _ASPECT_OPTIONS:
            self.combo_aspect.addItem(label, value)
        ar_row.addWidget(self.combo_aspect, 1)
        l1.addLayout(ar_row)
        lay.addWidget(c1)

        c2, l2 = self._make_card(
            "2 · RITAGLIO BORDI (CROP)",
            "Scegli % oppure pixel reali della sorgente per tagliare i bordi.",
        )
        crop_unit_row = QHBoxLayout()
        crop_unit_row.setSpacing(4)
        crop_unit_row.addWidget(self._make_field_label("Unità:"))
        self.btn_crop_pct = QPushButton("%")
        self.btn_crop_pct.setCheckable(True)
        self.btn_crop_pct.setChecked(True)
        self.btn_crop_pct.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_crop_pct.setToolTip("Imposta il ritaglio in percentuale (0.0% – 99.0%)")
        self.btn_crop_pct.setStyleSheet(_UNIT_PILL_STYLE)

        self.btn_crop_px = QPushButton("px")
        self.btn_crop_px.setCheckable(True)
        self.btn_crop_px.setChecked(False)
        self.btn_crop_px.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_crop_px.setToolTip("Imposta il ritaglio esatto in pixel rispetto alla risoluzione del file")
        self.btn_crop_px.setStyleSheet(_UNIT_PILL_STYLE)

        self.lbl_crop_ref = QLabel("1920×1080 px")
        self.lbl_crop_ref.setStyleSheet("color: #64748b; font-size: 10px; font-family: monospace; background: transparent;")
        self.lbl_crop_ref.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.btn_crop_reset = self._make_nudge_btn("⟲ Reset", "Rimuove il ritaglio e mostra il fotogramma intero")
        crop_unit_row.addWidget(self.btn_crop_pct)
        crop_unit_row.addWidget(self.btn_crop_px)
        crop_unit_row.addStretch()
        crop_unit_row.addWidget(self.lbl_crop_ref)
        crop_unit_row.addSpacing(4)
        crop_unit_row.addWidget(self.btn_crop_reset)
        l2.addLayout(crop_unit_row)

        crop_grid = QGridLayout()
        crop_grid.setHorizontalSpacing(8)
        crop_grid.setVerticalSpacing(5)
        crop_grid.addWidget(self._make_field_label("Sinistra:"), 0, 0)
        self.spin_crop_l = self._make_crop_spin("Ritaglio bordo sinistro")
        crop_grid.addWidget(self.spin_crop_l, 0, 1)

        crop_grid.addWidget(self._make_field_label("Destra:"), 0, 2)
        self.spin_crop_r = self._make_crop_spin("Ritaglio bordo destro")
        crop_grid.addWidget(self.spin_crop_r, 0, 3)

        crop_grid.addWidget(self._make_field_label("Alto:"), 1, 0)
        self.spin_crop_t = self._make_crop_spin("Ritaglio bordo superiore")
        crop_grid.addWidget(self.spin_crop_t, 1, 1)

        crop_grid.addWidget(self._make_field_label("Basso:"), 1, 2)
        self.spin_crop_b = self._make_crop_spin("Ritaglio bordo inferiore")
        crop_grid.addWidget(self.spin_crop_b, 1, 3)
        crop_grid.setColumnStretch(1, 1)
        crop_grid.setColumnStretch(3, 1)
        l2.addLayout(crop_grid)
        lay.addWidget(c2)

        c3, l3 = self._make_card(
            "3 · ROTAZIONE",
            "Ruota immagine o video. Per le immagini compare anche il ritaglio poligonale.",
        )
        rot_row = QHBoxLayout()
        rot_row.setSpacing(6)
        lbl_rot = self._make_field_label("Rotazione:")
        lbl_rot.setFixedWidth(56)
        rot_row.addWidget(lbl_rot)
        self.spin_rotation = SmartDoubleSpinBox()
        self.spin_rotation.setRange(-180.0, 180.0)
        self.spin_rotation.setSingleStep(1.0)
        self.spin_rotation.setDecimals(1)
        self.spin_rotation.setSuffix(" °")
        self.spin_rotation.setToolTip(
            "Rotazione in gradi attorno al centro del riquadro (-180° … +180°). 0° = dritto."
        )
        rot_row.addWidget(self.spin_rotation, 1)
        self.btn_rot_left = self._make_nudge_btn("⟲ 90°", "Ruota di 90° in senso antiorario")
        self.btn_rot_zero = self._make_nudge_btn("0°", "Riporta l'immagine dritta (0°)")
        self.btn_rot_right = self._make_nudge_btn("90° ⟳", "Ruota di 90° in senso orario")
        rot_row.addWidget(self.btn_rot_left)
        rot_row.addWidget(self.btn_rot_zero)
        rot_row.addWidget(self.btn_rot_right)
        l3.addLayout(rot_row)

        # The polygon mask only makes sense for still images: the whole row is
        # wrapped in a widget so it can be hidden for video cues (crop is enough).
        self.mask_row_widget = QWidget()
        mask_row = QHBoxLayout(self.mask_row_widget)
        mask_row.setContentsMargins(0, 0, 0, 0)
        mask_row.setSpacing(6)
        self.btn_mask_edit = self._make_nudge_btn(
            "✂ Disegna maschera…",
            "Ritaglia l'immagine lungo un percorso poligonale disegnato a mano",
        )
        self.btn_mask_edit.setEnabled(False)  # enabled only for IMAGE cues
        self.btn_mask_clear = self._make_nudge_btn(
            "✖ Rimuovi", "Rimuove la maschera poligonale e mostra l'immagine intera"
        )
        self.lbl_mask_info = QLabel("Nessuna maschera")
        self.lbl_mask_info.setStyleSheet(
            "color: #64748b; font-size: 10px; font-family: monospace; background: transparent;"
        )
        mask_row.addWidget(self.btn_mask_edit, 1)
        mask_row.addWidget(self.btn_mask_clear)
        mask_row.addWidget(self.lbl_mask_info)
        l3.addWidget(self.mask_row_widget)
        lay.addWidget(c3)
        lay.addStretch()

        self.tab_visual = self._wrap_tab_scroll(page)
        self.tab_widget.addTab(self.tab_visual, "🖼 Video · Foto")

    # ── Tab 3: Audio, Fade, Tagli IN/OUT & Ripetizioni Loop ───────────

    def _build_tab_audio_and_cuts(self) -> None:
        page = QWidget()
        page.setMinimumWidth(0)
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(6)

        self.lbl_audio_guide = QLabel(
            "Suggerimento: Dissolvenze (Fade In/Out) attive anche sulle Immagini; inviluppi avanzati e Sezioni A/B/C nella Forma d'Onda."
        )
        self.lbl_audio_guide.setWordWrap(True)
        self.lbl_audio_guide.setMinimumWidth(0)
        self.lbl_audio_guide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lbl_audio_guide.setStyleSheet(
            "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; "
            "border-radius: 5px; font-size: 11px; padding: 6px 10px;"
        )
        lay.addWidget(self.lbl_audio_guide)

        # Card 1: Volume Master
        c1, l1 = self._make_card(
            "1 · VOLUME PRINCIPALE (AUDIO / VIDEO)",
            "Livello base del media; puoi disegnare variazioni nel tempo direttamente sulla Forma d'Onda.",
        )
        vol_row, self.slider_volume, self.lbl_volume, self.btn_volume_reset = self._make_slider_row(
            "Volume:", 0, 100, 100, "100%", "Ripristina volume al 100%"
        )
        l1.addLayout(vol_row)
        from engine.audio_routes import CUE_OUTPUTS, LABELS

        out_row = QHBoxLayout()
        self.lbl_audio_output = QLabel("Uscita:")
        self.combo_audio_output = QComboBox()
        for key in CUE_OUTPUTS:
            self.combo_audio_output.addItem(LABELS[key], key)
        self.combo_audio_output.setToolTip(
            "Dove suona questa cue. Quale altoparlante è Palco, Sala o Spie su questo computer si sceglie in "
            "Dispositivi → Uscite audio. Muto: un video senza il suo audio.")
        self.combo_audio_output.setAccessibleName("Uscita audio della cue")
        self.combo_audio_output.currentIndexChanged.connect(lambda _i: self._emit_change("audio_output"))
        out_row.addWidget(self.lbl_audio_output)
        out_row.addWidget(self.combo_audio_output, 1)
        l1.addLayout(out_row)
        rate_row = QHBoxLayout()
        self.lbl_rate = QLabel("Tempo:")
        self.spin_rate = SmartDoubleSpinBox()
        self.spin_rate.setRange(50.0, 200.0)
        self.spin_rate.setDecimals(0)
        self.spin_rate.setSingleStep(5.0)
        self.spin_rate.setSuffix(" %")
        self.spin_rate.setValue(100.0)
        self.spin_rate.setToolTip("Velocità di riproduzione: 100 % = come registrato (per adattare la musica "
                                  "a una coreografia).")
        self.spin_rate.setAccessibleName("Tempo della cue in percento")
        self.spin_rate.valueChanged.connect(lambda _v: self._emit_change("playback_rate"))
        self.chk_keep_pitch = QCheckBox("Mantieni l'intonazione")
        self.chk_keep_pitch.setChecked(True)
        self.chk_keep_pitch.setToolTip("Più veloce o più lento senza cambiare l'altezza delle note.")
        self.chk_keep_pitch.toggled.connect(lambda _c: self._emit_change("keep_pitch"))
        rate_row.addWidget(self.lbl_rate)
        rate_row.addWidget(self.spin_rate, 1)
        rate_row.addWidget(self.chk_keep_pitch)
        l1.addLayout(rate_row)
        # 3.2 / 3.9: pan, more outputs with their levels, EQ, reverb (sound cues; folded when unused).
        from ui.audio_mix_panel import AudioMixPanel

        self.mix_panel = AudioMixPanel()
        self.mix_panel.changed.connect(lambda: self._emit_change("audio_mix"))
        self.combo_audio_output.currentIndexChanged.connect(
            lambda _i: self.mix_panel.set_main_output(self.combo_audio_output.currentData() or "stage"))
        l1.addWidget(self.mix_panel)
        lay.addWidget(c1)

        # Card 2: Dissolvenze (Fade IN/OUT)
        c2, l2 = self._make_card(
            "2 · DISSOLVENZE (FADE IN / OUT)",
            "Applicate dolcemente all'ingresso e all'uscita su Audio, Video e Immagini a durata.",
        )
        fade_grid = QGridLayout()
        fade_grid.setHorizontalSpacing(6)
        fade_grid.addWidget(self._make_field_label("Fade In:"), 0, 0)
        self.spin_fade_in = SmartDoubleSpinBox()
        self.spin_fade_in.setMinimumWidth(68)
        self.spin_fade_in.setRange(0.0, 30.0)
        self.spin_fade_in.setDecimals(1)
        self.spin_fade_in.setSingleStep(0.2)
        self.spin_fade_in.setSuffix(" s")
        self.spin_fade_in.setAccessibleName("Dissolvenza in Entrata Fade-In")
        self.spin_fade_in.setAccessibleDescription("Durata in secondi della dissolvenza in ingresso da nero o silenzio.")
        fade_grid.addWidget(self.spin_fade_in, 0, 1)

        fade_grid.addWidget(self._make_field_label("Fade Out:"), 0, 2)
        self.spin_fade_out = SmartDoubleSpinBox()
        self.spin_fade_out.setMinimumWidth(68)
        self.spin_fade_out.setRange(0.0, 30.0)
        self.spin_fade_out.setDecimals(1)
        self.spin_fade_out.setSingleStep(0.2)
        self.spin_fade_out.setSuffix(" s")
        self.spin_fade_out.setAccessibleName("Dissolvenza in Uscita Fade-Out")
        self.spin_fade_out.setAccessibleDescription("Durata in secondi della dissolvenza in chiusura a nero o silenzio.")
        fade_grid.addWidget(self.spin_fade_out, 0, 3)

        # Crossfade: dissolve the previous picture on the same layer
        self.lbl_crossfade = self._make_field_label("Crossfade:")
        fade_grid.addWidget(self.lbl_crossfade, 1, 0)
        self.spin_crossfade = SmartDoubleSpinBox()
        self.spin_crossfade.setMinimumWidth(68)
        self.spin_crossfade.setRange(0.0, 10.0)
        self.spin_crossfade.setDecimals(1)
        self.spin_crossfade.setSingleStep(0.5)
        self.spin_crossfade.setSuffix(" s")
        self.spin_crossfade.setToolTip(
            "Dissolvenza incrociata: ciò che c'è ora sul layer di questo cue (immagine o suono) sfuma "
            "mentre questo cue entra, nel tempo indicato (0 = stacco netto)."
        )
        self.spin_crossfade.setAccessibleName("Crossfade")
        fade_grid.addWidget(self.spin_crossfade, 1, 1)
        # 4.4 (MultiPlay): how two pictures cross - dissolve or slide in.
        self.combo_crossfade_style = QComboBox()
        self.combo_crossfade_style.addItem("Dissolvenza", "dissolve")
        self.combo_crossfade_style.addItem("Scorrimento", "slide")
        self.combo_crossfade_style.setToolTip(
            "Come entra l'immagine: in dissolvenza sopra la precedente, oppure scorrendo da destra "
            "mentre la precedente esce a sinistra.")
        self.combo_crossfade_style.setAccessibleName("Tipo di passaggio dell'immagine")
        self.combo_crossfade_style.currentIndexChanged.connect(lambda _i: self._emit_change("crossfade_style"))
        fade_grid.addWidget(self.combo_crossfade_style, 1, 2, 1, 2)
        fade_grid.setColumnStretch(1, 1)
        fade_grid.setColumnStretch(3, 1)
        l2.addLayout(fade_grid)
        lay.addWidget(c2)

        # Card 3: Punti di taglio IN / OUT
        c3, l3 = self._make_card(
            "3 · TAGLIO TEMPORALE (PUNTI IN / OUT)",
            "Imposta dove inizia e finisce la traccia (tasti rapidi [I] / [O] sulla Testina della Timeline).",
        )
        io_row = QHBoxLayout()
        io_row.setSpacing(5)
        io_row.addWidget(self._make_field_label("IN:"))
        self.spin_in = InPointSpinBox()
        self.spin_in.setMinimumWidth(68)
        self.spin_in.setAccessibleName("Punto di Inizio In-Point")
        self.spin_in.setAccessibleDescription("Posizione iniziale di riproduzione in minuti, secondi e centesimi.")
        io_row.addWidget(self.spin_in, 1)
        io_row.addWidget(self._make_field_label("OUT:"))
        self.spin_out = OutPointSpinBox()
        self.spin_out.setMinimumWidth(78)
        self.spin_out.setAccessibleName("Punto di Fine Out-Point")
        self.spin_out.setAccessibleDescription("Posizione finale di taglio o fine riproduzione.")
        io_row.addWidget(self.spin_out, 1)
        self.btn_io_reset = self._make_reset_icon_btn("Ripristina IN a 0.00s e OUT a Fine")
        io_row.addWidget(self.btn_io_reset)
        self.btn_trim_silence = QPushButton("✂")
        self.btn_trim_silence.setFixedWidth(28)
        self.btn_trim_silence.setToolTip("Taglia il silenzio all'inizio e alla fine: IN e OUT dove il suono "
                                         "comincia e finisce davvero (sotto -40 dB rispetto al picco).")
        self.btn_trim_silence.setAccessibleName("Taglia il silenzio all'inizio e alla fine")
        self.btn_trim_silence.clicked.connect(self.silence_trim_requested.emit)
        io_row.addWidget(self.btn_trim_silence)
        l3.addLayout(io_row)
        # 4.4: a video can stay on its last frame instead of leaving the layer empty.
        self.chk_hold_last_frame = QCheckBox("Alla fine resta l'ultimo fotogramma")
        self.chk_hold_last_frame.setToolTip(
            "Il video si ferma sull'ultimo fotogramma, che resta sullo schermo finché un'altra cue "
            "prende il suo layer o lo sfumi (Sfuma, Sfuma tutto, Blackout). Non con il loop infinito.")
        self.chk_hold_last_frame.setAccessibleName("Alla fine resta l'ultimo fotogramma")
        self.chk_hold_last_frame.toggled.connect(lambda _c: self._emit_change("hold_last_frame"))
        l3.addWidget(self.chk_hold_last_frame)
        lay.addWidget(c3)

        # Card 4: Ripetizione Loop
        self.loop_card = QFrame()
        self.loop_card.setObjectName("loopCard")
        self.loop_card.setMinimumWidth(0)
        self.loop_card.setStyleSheet(
            "QFrame#loopCard { background-color: #101723; border: 1px solid #223044; border-radius: 6px; }"
        )
        loop_card_layout = QVBoxLayout(self.loop_card)
        loop_card_layout.setContentsMargins(8, 6, 8, 7)
        loop_card_layout.setSpacing(6)

        loop_top_row = QHBoxLayout()
        self.chk_loop = QCheckBox("🔁  4 · RIPETI CUE IN LOOP")
        self.chk_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_loop.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                font-size: 11px;
                color: #10b981;
                spacing: 8px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #10b981;
                background-color: #091310;
            }
            QCheckBox::indicator:checked { background-color: #10b981; }
            QCheckBox::indicator:hover { border-color: #34d399; }
        """)
        loop_top_row.addWidget(self.chk_loop)
        loop_top_row.addStretch()
        loop_card_layout.addLayout(loop_top_row)

        loop_options_row = QHBoxLayout()
        loop_options_row.addWidget(self._make_field_label("Ripetizioni:"))

        self.combo_loop_mode = QComboBox()
        self.combo_loop_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_loop_mode.setMinimumContentsLength(10)
        self.combo_loop_mode.setMinimumWidth(50)
        self.combo_loop_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_loop_mode.addItems([
            "∞ Continuo (Infinito)",
            "Ripeti 2 volte",
            "Ripeti 3 volte",
            "Ripeti 4 volte",
            "Ripeti 5 volte",
            "Ripeti 10 volte",
            "Personalizzato...",
        ])
        loop_options_row.addWidget(self.combo_loop_mode, 1)

        self.spin_loop_count = SmartDoubleSpinBox()
        self.spin_loop_count.setRange(1, 999)
        self.spin_loop_count.setDecimals(0)
        self.spin_loop_count.setSingleStep(1)
        self.spin_loop_count.setSuffix(" rip.")
        self.spin_loop_count.setFixedWidth(74)
        self.spin_loop_count.setVisible(False)
        loop_options_row.addWidget(self.spin_loop_count)
        loop_card_layout.addLayout(loop_options_row)
        xfade_row = QHBoxLayout()  # 3.4: a pass runs into the next one (sound)
        self.lbl_loop_xfade = self._make_field_label("Dissolvenza tra i giri:")
        xfade_row.addWidget(self.lbl_loop_xfade)
        self.spin_loop_xfade = SmartDoubleSpinBox()
        self.spin_loop_xfade.setRange(0.0, 30.0)
        self.spin_loop_xfade.setDecimals(1)
        self.spin_loop_xfade.setSingleStep(0.5)
        self.spin_loop_xfade.setSuffix(" s")
        self.spin_loop_xfade.setSpecialValueText("stacco")
        self.spin_loop_xfade.setFixedWidth(74)
        self.spin_loop_xfade.setAccessibleName("Dissolvenza tra i giri del loop")
        self.spin_loop_xfade.setToolTip("Suoni: ogni giro entra nel successivo con una dissolvenza incrociata "
                                        "di questi secondi, senza salto (0 = stacco).")
        xfade_row.addWidget(self.spin_loop_xfade)
        xfade_row.addStretch(1)
        loop_card_layout.addLayout(xfade_row)
        lay.addWidget(self.loop_card)

        # Card 5: Livellamento & Loudness EBU R128
        c5, l5 = self._make_card(
            "5 · LIVELLAMENTO & LOUDNESS (EBU R128)",
            "Calcola il volume percepito (LUFS) per livellare tracce troppo basse o troppo alte senza distorsione.",
        )
        self.card_loudness = c5

        loud_status_row = QHBoxLayout()
        loud_status_row.setSpacing(6)
        self.lbl_loudness_info = QLabel("📊 Loudness: Non analizzato")
        self.lbl_loudness_info.setWordWrap(True)
        self.lbl_loudness_info.setStyleSheet(
            "background-color: #0b111a; color: #94a3b8; border: 1px solid #1e293b; "
            "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
        )
        loud_status_row.addWidget(self.lbl_loudness_info, stretch=1)

        self.btn_scan_loudness = QPushButton("🔍 Analizza")
        self.btn_scan_loudness.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan_loudness.setToolTip("Analizza il volume percepito EBU R128 in background con FFmpeg")
        self.btn_scan_loudness.setStyleSheet(
            "QPushButton { background-color: #16202e; color: #38bdf8; border: 1px solid #2d3e56; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 3px 8px; } "
            "QPushButton:hover { background-color: #1e334d; border-color: #38bdf8; color: #ffffff; }"
        )
        self.btn_scan_loudness.clicked.connect(self.scan_loudness_requested)
        loud_status_row.addWidget(self.btn_scan_loudness)
        l5.addLayout(loud_status_row)

        self.chk_normalize_cue = QCheckBox("🎚 Applica Guadagno EBU R128 (-16 LUFS) per questo file")
        self.chk_normalize_cue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_normalize_cue.setToolTip("Applica l'offset di guadagno non distruttivo sul player per pareggiare il volume con le altre cue.")
        self.chk_normalize_cue.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                font-size: 11px;
                color: #38bdf8;
                spacing: 6px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #38bdf8;
                background-color: #09111b;
            }
            QCheckBox::indicator:checked { background-color: #0284c7; }
            QCheckBox::indicator:hover { border-color: #7dd3fc; }
        """)
        self.chk_normalize_cue.toggled.connect(self.normalize_cue_toggled)
        l5.addWidget(self.chk_normalize_cue)

        dyn_row = QHBoxLayout()
        dyn_row.setSpacing(6)
        self.btn_optimize_dynamics = QPushButton("🛠 Ottimizza Dinamica (Compressore / Limiter)")
        self.btn_optimize_dynamics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_optimize_dynamics.setToolTip(
            "Per file complessi o registrati male: applica il compressore broadcast EBU R128 "
            "a due passate con True-Peak Limiter per appiattire gli sbalzi e proteggere l'impianto."
        )
        self.btn_optimize_dynamics.setStyleSheet(
            "QPushButton { background-color: #1e293b; color: #fbbf24; border: 1px solid #d97706; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px 8px; } "
            "QPushButton:hover { background-color: #451a03; border-color: #f59e0b; color: #ffffff; }"
        )
        self.btn_optimize_dynamics.clicked.connect(self.optimize_dynamics_requested)
        dyn_row.addWidget(self.btn_optimize_dynamics, stretch=1)

        self.btn_restore_original = QPushButton("↺ Ripristina Originale")
        self.btn_restore_original.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore_original.setToolTip("Annulla l'ottimizzazione e torna al file media originale")
        self.btn_restore_original.setStyleSheet(
            "QPushButton { background-color: #1e2024; color: #94a3b8; border: 1px solid #334155; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px 8px; } "
            "QPushButton:hover { background-color: #2b3038; border-color: #64748b; color: #ffffff; }"
        )
        self.btn_restore_original.setVisible(False)
        self.btn_restore_original.clicked.connect(self.restore_original_requested)
        dyn_row.addWidget(self.btn_restore_original)
        l5.addLayout(dyn_row)

        lay.addWidget(c5)
        lay.addStretch()

        self.tab_audio_cuts = self._wrap_tab_scroll(page)
        self.tab_widget.addTab(self.tab_audio_cuts, "🎵 Audio · Tagli")

    # ── Tab 4: Gruppo · Scena ─────────────────────────────────────────

    def _build_tab_group(self) -> None:
        page = QWidget()
        page.setMinimumWidth(0)
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(6)

        # Card 1: Identità Gruppo / Scena & Colore
        c1, l1 = self._make_card(
            "1 · IDENTITÀ SCENA / GRUPPO & COLORE",
            "I gruppi organizzano più media in una singola riga collassabile in Scaletta e Live.",
        )
        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(6)
        grid1.setVerticalSpacing(5)

        grid1.addWidget(self._make_field_label("Q (Copione):"), 0, 0)
        self.edit_group_q = QLineEdit()
        self.edit_group_q.setMinimumWidth(40)
        self.edit_group_q.setPlaceholderText("es. G-1, Atto 1, Scena A...")
        self.edit_group_q.setToolTip("Sigla di copione del gruppo: resta legata al gruppo se riordini la scaletta")
        grid1.addWidget(self.edit_group_q, 0, 1)

        grid1.addWidget(self._make_field_label("Nome Gruppo:"), 1, 0)
        self.edit_group_name = QLineEdit()
        self.edit_group_name.setMinimumWidth(40)
        self.edit_group_name.setPlaceholderText("Titolo scena o sequenza...")
        grid1.addWidget(self.edit_group_name, 1, 1)

        grid1.addWidget(self._make_field_label("Note Regia:"), 2, 0)
        self.edit_group_notes = QLineEdit()
        self.edit_group_notes.setMinimumWidth(40)
        self.edit_group_notes.setPlaceholderText("Note di regia o indicazioni palco per il gruppo...")
        grid1.addWidget(self.edit_group_notes, 2, 1)
        grid1.setColumnStretch(1, 1)
        l1.addLayout(grid1)

        # Timing Gruppo: Pre-Wait e Post-Wait
        timing_row = QHBoxLayout()
        timing_row.setSpacing(8)

        lbl_pre = self._make_field_label("Pre-Wait:")
        self.spin_group_pre_delay = SmartDoubleSpinBox()
        self.spin_group_pre_delay.setRange(0.0, 3600.0)
        self.spin_group_pre_delay.setSingleStep(0.5)
        self.spin_group_pre_delay.setDecimals(1)
        self.spin_group_pre_delay.setSuffix(" s")
        self.spin_group_pre_delay.setToolTip("Attesa prima di avviare il gruppo alla pressione del GO.")

        lbl_post = self._make_field_label("Post-Wait:")
        self.spin_group_post_delay = SmartDoubleSpinBox()
        self.spin_group_post_delay.setRange(0.0, 3600.0)
        self.spin_group_post_delay.setSingleStep(0.5)
        self.spin_group_post_delay.setDecimals(1)
        self.spin_group_post_delay.setSuffix(" s")
        self.spin_group_post_delay.setToolTip("Attesa al termine dell'esecuzione prima di passare alla cue successiva.")

        timing_row.addWidget(lbl_pre)
        timing_row.addWidget(self.spin_group_pre_delay)
        timing_row.addWidget(lbl_post)
        timing_row.addWidget(self.spin_group_post_delay)
        timing_row.addStretch()
        l1.addLayout(timing_row)

        # Palette colore gruppo
        color_row = QHBoxLayout()
        color_row.setSpacing(4)
        lbl_clr = self._make_field_label("Colore:")
        lbl_clr.setFixedWidth(48)
        color_row.addWidget(lbl_clr)
        for hex_val, clr_tip in CUE_COLOR_PALETTE:
            btn = QPushButton("✕" if not hex_val else "")
            btn.setCheckable(True)
            btn.setFixedSize(24, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"Colore Scena: {clr_tip}")
            btn.setStyleSheet(_make_swatch_style(hex_val))
            btn.clicked.connect(lambda _=False, hv=hex_val: self.color_selected.emit(hv))
            color_row.addWidget(btn)
            self._group_color_buttons[hex_val] = btn
        color_row.addStretch()
        l1.addLayout(color_row)
        lay.addWidget(c1)

        # Card 2: Comportamento al GO (Modalità Scena)
        c2, l2 = self._make_card(
            "2 · COMPORTAMENTO AL GO (MODALITÀ SCENA)",
            "Determina come vengono eseguiti i media contenuti nel gruppo quando si preme GO.",
        )
        self.lbl_group_mode_desc = QLabel()
        self.lbl_group_mode_desc.setWordWrap(True)
        self.lbl_group_mode_desc.setStyleSheet(
            "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; "
            "border-radius: 5px; font-size: 10px; padding: 5px 7px;"
        )
        l2.addWidget(self.lbl_group_mode_desc)

        mode_btn_grid = QVBoxLayout()
        mode_btn_grid.setSpacing(4)
        for mode_key, label, desc, bg, border in _GROUP_MODE_SPECS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(desc)
            btn.setStyleSheet(_make_layer_btn_style(bg, border))
            btn.clicked.connect(lambda _=False, mk=mode_key: self._on_group_mode_clicked(mk))
            mode_btn_grid.addWidget(btn)
            self._group_mode_buttons[mode_key] = btn
        l2.addLayout(mode_btn_grid)

        self.lbl_group_layer_conflict = QLabel()
        self.lbl_group_layer_conflict.setWordWrap(True)
        self.lbl_group_layer_conflict.setStyleSheet(
            "background-color: #3b1d07; color: #fde047; border: 1px solid #d97706; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px 6px;"
        )
        self.lbl_group_layer_conflict.setVisible(False)
        l2.addWidget(self.lbl_group_layer_conflict)

        lay.addWidget(c2)

        from ui.playlist_settings import PlaylistSettingsBox

        self.playlist_box = PlaylistSettingsBox()  # 3.3: shown for a playlist only
        self.playlist_box.setVisible(False)
        lay.addWidget(self.playlist_box)

        # Card 3: Elementi del Gruppo
        c3, l3 = self._make_card(
            "3 · ELEMENTI INTERNI AL GRUPPO",
            "Lista dei media appartenenti a questo gruppo. Usa i pulsanti per espandere o gestire i membri.",
        )
        self.lbl_group_stats = QLabel("📁 0 cue nel gruppo")
        self.lbl_group_stats.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; background: transparent;")
        l3.addWidget(self.lbl_group_stats)

        self.list_group_children = QListWidget()
        self.list_group_children.setMinimumHeight(110)
        self.list_group_children.setMaximumHeight(180)
        self.list_group_children.setStyleSheet(
            "QListWidget { background-color: #0b111b; border: 1px solid #1f2d40; border-radius: 4px; color: #e2e8f0; font-size: 11px; padding: 2px; } "
            "QListWidget::item { padding: 4px; border-bottom: 1px solid #16202e; border-radius: 3px; } "
            "QListWidget::item:selected { background-color: #1e3a5f; color: #38bdf8; }"
        )
        l3.addWidget(self.list_group_children)

        grp_actions_row = QHBoxLayout()
        grp_actions_row.setSpacing(6)

        self.btn_group_collapse_toggle = QPushButton("▶ Collassa / ▼ Espandi")
        self.btn_group_collapse_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_group_collapse_toggle.setToolTip("Mostra o nascondi i figli del gruppo nella tabella Scaletta")
        self.btn_group_collapse_toggle.setStyleSheet(NUDGE_BTN_STYLE.replace("min-width: 30px;", "padding: 4px 8px;"))
        self.btn_group_collapse_toggle.clicked.connect(self.group_collapse_toggled)
        grp_actions_row.addWidget(self.btn_group_collapse_toggle)

        self.btn_group_remove_child = QPushButton("✕ Rimuovi Cue")
        self.btn_group_remove_child.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_group_remove_child.setToolTip("Rimuove la cue selezionata dalla lista dal gruppo (torna al livello principale)")
        self.btn_group_remove_child.setStyleSheet(NUDGE_BTN_STYLE.replace("min-width: 30px;", "padding: 4px 8px; color: #f87171;"))
        self.btn_group_remove_child.clicked.connect(self._on_remove_selected_child_clicked)
        grp_actions_row.addWidget(self.btn_group_remove_child)

        self.btn_group_ungroup = QPushButton("🔓 Sciogli Gruppo")
        self.btn_group_ungroup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_group_ungroup.setToolTip("Elimina il contenitore del gruppo e rilascia tutte le sue cue in scaletta")
        self.btn_group_ungroup.setStyleSheet(NUDGE_BTN_STYLE.replace("min-width: 30px;", "padding: 4px 8px; color: #fbbf24;"))
        self.btn_group_ungroup.clicked.connect(self.ungroup_requested)
        grp_actions_row.addWidget(self.btn_group_ungroup)

        l3.addLayout(grp_actions_row)

        self.btn_open_timeline_studio = QPushButton("🎬  APRI STUDIO TIMELINE DEL GRUPPO (3 LAYER)")
        self.btn_open_timeline_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_timeline_studio.setFixedHeight(34)
        self.btn_open_timeline_studio.setAccessibleName("Studio Timeline Multi-Track")
        self.btn_open_timeline_studio.setAccessibleDescription("Apre la finestra di composizione multi-traccia a 3 layer per sincronizzare i file del gruppo.")
        self.btn_open_timeline_studio.setToolTip(
            "Apre la finestra extra Studio Timeline per sincronizzare visivamente i file del gruppo\n"
            "sulle 3 tracce layer (L1, L2, L3) con righello millisecondi, tagli e anteprima multi-canale."
        )
        self.btn_open_timeline_studio.setStyleSheet("""
            QPushButton {
                background-color: #1e1b4b;
                color: #a5b4fc;
                border: 1.5px solid #6366f1;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                margin-top: 4px;
            }
            QPushButton:hover {
                background-color: #312e81;
                border-color: #818cf8;
                color: #ffffff;
            }
        """)
        self.btn_open_timeline_studio.clicked.connect(self.open_group_timeline_requested)
        l3.addWidget(self.btn_open_timeline_studio)
        lay.addWidget(c3)
        lay.addStretch()

        self.tab_group = self._wrap_tab_scroll(page)
        self.tab_widget.addTab(self.tab_group, "📁 Gruppo · Scena")

        self.refresh_theme_styles()

    def refresh_theme_styles(self) -> None:
        """Apply theme-appropriate palettes and styling to cards, buttons, banners, and toggles."""
        theme = get_active_theme()
        is_mono = theme.is_monochrome

        # 1. Update Card containers and card title labels
        card_bg = "#1a1b1f" if is_mono else "#101723"
        card_border = "#33343e" if is_mono else "#223044"
        for card in self.findChildren(QFrame, "inspCard"):
            card.setStyleSheet(
                f"QFrame#inspCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 6px; }}"
            )
        active_t = get_active_theme()
        for title_lbl in self.findChildren(QLabel, "inspCardTitle"):
            title_lbl.setStyleSheet(
                f"color: {active_t.accent}; font-size: 10px; font-weight: bold; letter-spacing: 0.4px; border: none; background: transparent;"
            )

        # 2. Timing Pipeline Banner
        if hasattr(self, "_pipe_lbl") and self._pipe_lbl is not None:
            if is_mono:
                self._pipe_lbl.setStyleSheet(
                    "background-color: #141518; color: #ffffff; border: 1px solid #525363; "
                    "border-radius: 4px; font-size: 9px; font-weight: bold; padding: 3px 4px;"
                )
            else:
                self._pipe_lbl.setStyleSheet(
                    "background-color: #09111b; color: #7dd3fc; border: 1px solid #1e3a5f; "
                    "border-radius: 4px; font-size: 9px; font-weight: bold; padding: 3px 4px;"
                )

        # 3. Layer buttons
        for layer_idx, btn in self._layer_buttons.items():
            spec = next((s for s in _LAYER_BTN_SPECS if s[0] == layer_idx), None)
            bg = spec[3] if spec else "#075985"
            border = spec[4] if spec else "#38bdf8"
            btn.setStyleSheet(_make_layer_btn_style(bg, border, is_mono).replace("font-size: 11px;", "font-size: 10px;"))

        # 4. Follow buttons
        for mode_val, btn in self._follow_buttons.items():
            spec = next((s for s in _FOLLOW_MINI_SPECS if s[0] == mode_val), None)
            bg = spec[3] if spec else "#0c4a6e"
            border = spec[4] if spec else "#38bdf8"
            if is_mono:
                btn.setStyleSheet(
                    "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1px solid #3f404d; "
                    "border-radius: 4px; font-size: 9px; font-weight: bold; padding: 0px 3px; } "
                    "QPushButton:hover:!checked { background-color: #2d2f38; border-color: #525363; color: #ffffff; } "
                    "QPushButton:checked { background-color: #383946; border: 1.5px solid #ffffff; color: #ffffff; } "
                    "QPushButton:disabled { background-color: #141518; color: #525363; border-color: #27272a; }"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: #161f2d; color: #94a3b8; border: 1px solid #2b3a4f; "
                    f"border-radius: 4px; font-size: 9px; font-weight: bold; padding: 0px 3px; }} "
                    f"QPushButton:hover:!checked {{ background-color: #202e42; border-color: {border}; color: #ffffff; }} "
                    f"QPushButton:checked {{ background-color: {bg}; border: 1px solid {border}; color: #ffffff; }} "
                    f"QPushButton:disabled {{ background-color: #0e131c; color: #475569; border-color: #1a2230; }}"
                )

        # 5. Group Mode buttons
        for g_mode, btn in self._group_mode_buttons.items():
            spec = next((s for s in _GROUP_MODE_SPECS if s[0] == g_mode), None)
            bg = spec[3] if spec else "#0c4a6e"
            border = spec[4] if spec else "#38bdf8"
            btn.setStyleSheet(_make_layer_btn_style(bg, border, is_mono))

        # 6. Group Membership Box
        if hasattr(self, "frame_group_membership") and self.frame_group_membership is not None:
            g_bg = "#1a1b1f" if is_mono else "#1e1430"
            g_border = "#3f404d" if is_mono else "#4c1d95"
            self.frame_group_membership.setStyleSheet(
                f"QFrame {{ background-color: {g_bg}; border: 1px solid {g_border}; border-radius: 5px; padding: 2px; }}"
            )
        if hasattr(self, "lbl_group_membership") and self.lbl_group_membership is not None:
            g_fg = "#e4e4e7" if is_mono else "#c084fc"
            self.lbl_group_membership.setStyleSheet(
                f"color: {g_fg}; font-size: 10px; font-weight: bold; border: none; background: transparent;"
            )

        # 7. Timeline Studio Button
        if hasattr(self, "btn_open_timeline_studio") and self.btn_open_timeline_studio is not None:
            if is_mono:
                self.btn_open_timeline_studio.setStyleSheet("""
                    QPushButton {
                        background-color: #26272e;
                        color: #f4f4f5;
                        border: 1.5px solid #ffffff;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px 12px;
                        margin-top: 4px;
                    }
                    QPushButton:hover {
                        background-color: #33343d;
                        border-color: #d4d4d8;
                        color: #ffffff;
                    }
                """)
            else:
                self.btn_open_timeline_studio.setStyleSheet("""
                    QPushButton {
                        background-color: #1e1b4b;
                        color: #a5b4fc;
                        border: 1.5px solid #6366f1;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px 12px;
                        margin-top: 4px;
                    }
                    QPushButton:hover {
                        background-color: #312e81;
                        border-color: #818cf8;
                        color: #ffffff;
                    }
                """)

        # 8. Loop Card
        if hasattr(self, "loop_card") and self.loop_card is not None:
            l_bg = "#1a1b1f" if is_mono else "#1a162b"
            l_border = "#33343e" if is_mono else "#3b2d54"
            self.loop_card.setStyleSheet(f"QFrame {{ background-color: {l_bg}; border: 1px solid {l_border}; border-radius: 6px; }}")

        # 9. Loudness Scan Button & Checkbox
        if hasattr(self, "btn_scan_loudness") and self.btn_scan_loudness is not None:
            if is_mono:
                self.btn_scan_loudness.setStyleSheet(
                    "QPushButton { background-color: #26272e; color: #f4f4f5; border: 1px solid #525363; "
                    "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 3px 8px; } "
                    "QPushButton:hover { background-color: #33343d; border-color: #ffffff; color: #ffffff; }"
                )
            else:
                self.btn_scan_loudness.setStyleSheet(
                    f"QPushButton {{ background-color: {active_t.button_bg}; color: {active_t.accent}; border: 1px solid {active_t.button_border}; "
                    f"border-radius: 4px; font-size: 10px; font-weight: bold; padding: 3px 8px; }} "
                    f"QPushButton:hover {{ background-color: {active_t.button_hover_bg}; border-color: {active_t.accent}; color: #ffffff; }}"
                )

        if hasattr(self, "chk_normalize_cue") and self.chk_normalize_cue is not None:
            if is_mono:
                self.chk_normalize_cue.setStyleSheet("""
                    QCheckBox {
                        font-weight: bold;
                        font-size: 11px;
                        color: #f4f4f5;
                        spacing: 6px;
                        background: transparent;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border-radius: 3px;
                        border: 1px solid #71717a;
                        background-color: #1a1b1f;
                    }
                    QCheckBox::indicator:checked { background-color: #ffffff; border-color: #ffffff; }
                    QCheckBox::indicator:hover { border-color: #ffffff; }
                """)
            else:
                self.chk_normalize_cue.setStyleSheet(f"""
                    QCheckBox {{
                        font-weight: bold;
                        font-size: 11px;
                        color: {active_t.accent};
                        spacing: 6px;
                        background: transparent;
                    }}
                    QCheckBox::indicator {{
                        width: 16px;
                        height: 16px;
                        border-radius: 3px;
                        border: 1px solid {active_t.accent};
                        background-color: {active_t.input_bg};
                    }}
                    QCheckBox::indicator:checked {{ background-color: {active_t.accent_muted}; }}
                    QCheckBox::indicator:hover {{ border-color: {active_t.accent_hover}; }}
                """)

    @staticmethod
    def _make_nudge_btn(text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(NUDGE_BTN_STYLE)
        return btn

    @staticmethod
    def _make_reset_icon_btn(tooltip: str) -> QPushButton:
        btn = QPushButton("⟲")
        btn.setToolTip(tooltip)
        btn.setFixedWidth(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(NUDGE_BTN_STYLE.replace("min-width: 30px;", "min-width: 24px; padding: 2px 4px;"))
        return btn

    @staticmethod
    def _make_crop_spin(tooltip: str) -> SmartDoubleSpinBox:
        spin = SmartDoubleSpinBox()
        spin.setRange(0.0, 99.0)
        spin.setSingleStep(1.0)
        spin.setDecimals(1)
        spin.setSuffix(" %")
        spin.setToolTip(tooltip)
        return spin

    def _connect_signals(self) -> None:
        for layer_idx, btn in self._layer_buttons.items():
            btn.clicked.connect(lambda _=False, idx=layer_idx: self._on_layer_clicked(idx))

        self.btn_crop_pct.clicked.connect(lambda: self.set_crop_unit("pct"))
        self.btn_crop_px.clicked.connect(lambda: self.set_crop_unit("px"))

        self.btn_nudge_left.clicked.connect(lambda: self.nudge_position(-0.01, 0.0))
        self.btn_nudge_up.clicked.connect(lambda: self.nudge_position(0.0, -0.01))
        self.btn_nudge_down.clicked.connect(lambda: self.nudge_position(0.0, 0.01))
        self.btn_nudge_right.clicked.connect(lambda: self.nudge_position(0.01, 0.0))
        self.btn_pos_center.clicked.connect(self.reset_position)

        self.slider_scale.valueChanged.connect(lambda v: self.lbl_scale.setText(f"{v / 100:.1f}x"))
        self.btn_scale_reset.clicked.connect(self.reset_scale)
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"{v}%"))
        self.btn_opacity_reset.clicked.connect(lambda: self.slider_opacity.setValue(100))
        self.btn_crop_reset.clicked.connect(self.reset_crop)
        self.btn_rot_left.clicked.connect(lambda: self.nudge_rotation(-90.0))
        self.btn_rot_zero.clicked.connect(self.reset_rotation)
        self.btn_rot_right.clicked.connect(lambda: self.nudge_rotation(90.0))
        self.btn_mask_edit.clicked.connect(self.mask_edit_requested.emit)
        self.btn_mask_clear.clicked.connect(self.clear_mask)
        self.slider_volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v}%"))
        self.btn_volume_reset.clicked.connect(lambda: self.slider_volume.setValue(100))
        self.btn_io_reset.clicked.connect(self.reset_in_out)

        field_widgets = (
            (self.spin_pos_x.valueChanged, "pos_x"),
            (self.spin_pos_y.valueChanged, "pos_y"),
            (self.spin_rotation.valueChanged, "rotation"),
            (self.spin_crop_l.valueChanged, "crop_l"),
            (self.spin_crop_r.valueChanged, "crop_r"),
            (self.spin_crop_t.valueChanged, "crop_t"),
            (self.spin_crop_b.valueChanged, "crop_b"),
            (self.spin_fade_in.valueChanged, "fade_in"),
            (self.spin_fade_out.valueChanged, "fade_out"),
            (self.spin_crossfade.valueChanged, "crossfade"),
            (self.spin_in.valueChanged, "in_point"),
            (self.spin_out.valueChanged, "out_point"),
            (self.spin_hold_time.valueChanged, "hold_time"),
            (self.spin_pre_delay.valueChanged, "pre_delay"),
            (self.spin_post_delay.valueChanged, "post_delay"),
            (self.slider_scale.valueChanged, "scale"),
            (self.slider_opacity.valueChanged, "opacity"),
            (self.slider_volume.valueChanged, "volume"),
            (self.spin_loop_count.valueChanged, "loop"),
            (self.spin_loop_xfade.valueChanged, "loop"),
            (self.combo_aspect.currentIndexChanged, "aspect_ratio"),
            (self.edit_cue_q.textEdited, "q_label"),
            (self.edit_cue_name.textEdited, "name"),
            (self.edit_cue_notes.textEdited, "notes"),
            (self.edit_script_page.textEdited, "script_page"),
            (self.edit_script_line.textEdited, "script_line"),
            (self.edit_group_q.textEdited, "group_q"),
            (self.edit_group_name.textEdited, "group_name"),
            (self.edit_group_notes.textEdited, "group_notes"),
            (self.spin_group_pre_delay.valueChanged, "group_pre_delay"),
            (self.spin_group_post_delay.valueChanged, "group_post_delay"),
        )
        for sig, field_key in field_widgets:
            sig.connect(lambda *_args, key=field_key: self._emit_change(key))

        self.chk_loop.toggled.connect(self._on_loop_chk_toggled)
        self.combo_loop_mode.currentIndexChanged.connect(self._on_loop_mode_changed)

    def _on_group_mode_clicked(self, mode_key: str) -> None:
        self.set_group_mode_checked(mode_key)
        self.group_mode_selected.emit(mode_key)

    def set_group_mode_checked(self, mode_key: str) -> None:
        """Highlight *mode_key* in the group playback-mode selector.

        Called when loading a group cue: it updates the buttons and the help
        text without emitting ``group_mode_selected`` (no feedback loop).
        """
        for mk, btn in self._group_mode_buttons.items():
            btn.setChecked(mk == mode_key)
        for mk, _label, desc, _, _ in _GROUP_MODE_SPECS:
            if mk == mode_key:
                self.lbl_group_mode_desc.setText(f"💡 {desc}")
                break

    def _on_remove_selected_child_clicked(self) -> None:
        item = self.list_group_children.currentItem()
        if item is not None:
            child_id = item.data(Qt.ItemDataRole.UserRole)
            if child_id is not None:
                self.remove_child_requested.emit(int(child_id))

    def load_group_children(self, children: list[Cue], group_cue: Cue | None = None) -> None:
        """Fill the child-cue list shown when a group cue is selected.

        Each row shows media type, Q reference, name and estimated duration;
        the total is displayed below so the operator can judge the group even
        when its children use manual (hold-time) durations.
        """
        self.list_group_children.clear()
        tot_dur = 0.0
        for child in children:
            if child.out_point is not None and child.out_point > child.in_point:
                dur = child.out_point - child.in_point
            elif child.hold_time > 0:
                dur = child.hold_time
            else:
                dur = getattr(child, "duration", 0.0) or 0.0
            tot_dur += dur
            dur_str = f"{int(dur // 60):02d}:{dur % 60:05.2f}" if dur > 0 else "Manuale"
            badge = f"[{child.media_type.value[:3]}]"
            q_str = f"Q-{child.q_label}" if child.q_label else f"#{child.cue_id}"
            item = QListWidgetItem(f"{badge} {q_str} · {child.name} ({dur_str})")
            item.setData(Qt.ItemDataRole.UserRole, child.cue_id)
            self.list_group_children.addItem(item)

        mins = int(tot_dur // 60)
        secs = tot_dur % 60
        dur_txt = f"{mins:02d}:{secs:05.2f}" if tot_dur > 0 else "Non definita"
        self.lbl_group_stats.setText(f"📁 {len(children)} cue nel gruppo · Durata stimata: {dur_txt}")

        if group_cue:
            if group_cue.collapsed:
                self.btn_group_collapse_toggle.setText("▼ Espandi Gruppo in Scaletta")
            else:
                self.btn_group_collapse_toggle.setText("▶ Collassa Gruppo in Scaletta")
        is_playlist = bool(group_cue is not None and getattr(group_cue, "playlist", False))
        self.playlist_box.setVisible(is_playlist)  # 3.3: how the playlist plays
        if is_playlist:
            self.playlist_box.load(group_cue)

    def _on_layer_clicked(self, layer: int) -> None:
        self.set_layer_checked(layer)
        self.layer_selected.emit(layer)

    def _sync_rel_enabled(self) -> None:
        on = bool(self.combo_rel_when.currentData())
        self.combo_rel_cue.setEnabled(on)
        self.spin_rel_offset.setEnabled(on)
        self.combo_rel_marker.setVisible(self.combo_rel_when.currentData() == "marker")
        if self.combo_rel_marker.isVisible():
            self._fill_rel_markers(self.combo_rel_marker.currentData())

    def _fill_rel_markers(self, chosen: int | None) -> None:
        """The markers of the reference cue chosen in the row."""
        ref_id = self.combo_rel_cue.currentData()
        ref = next((c for c in (self.action_editor._catalog() or []) if c.cue_id == ref_id), None)
        self.combo_rel_marker.blockSignals(True)
        self.combo_rel_marker.clear()
        for m in getattr(ref, "markers", []) if ref is not None else []:
            self.combo_rel_marker.addItem(f"{m['name']} ({m['sec']:.1f} s)", m["id"])
        self.combo_rel_marker.setCurrentIndex(max(0, self.combo_rel_marker.findData(chosen)))
        self.combo_rel_marker.blockSignals(False)

    def load_markers(self, cue) -> None:
        """2.7: this cue's own markers (to see and delete)."""
        self.combo_markers.clear()
        for m in getattr(cue, "markers", []) if cue is not None else []:
            self.combo_markers.addItem(f"{m['name']}  {m['sec']:.2f} s", m["id"])
        has = self.combo_markers.count() > 0
        self.combo_markers.setEnabled(has)
        self.btn_marker_delete.setEnabled(has)

    def _on_rel_changed(self) -> None:
        self._sync_rel_enabled()
        self._emit_change("start_rel")

    def set_cue_choices(self, items: list[tuple[int, str]]) -> None:
        """The cues a relative start can follow ("#3 Music"), kept up to date by the window."""
        if items == self._rel_choices:
            return
        self._rel_choices = list(items)
        current = self.combo_rel_cue.currentData()
        self.combo_rel_cue.blockSignals(True)
        self.combo_rel_cue.clear()
        for cue_id, label in items:
            self.combo_rel_cue.addItem(label, cue_id)
        self.combo_rel_cue.setCurrentIndex(max(0, self.combo_rel_cue.findData(current)))
        self.combo_rel_cue.blockSignals(False)

    def _load_call_only(self, cue) -> None:
        from i18n import tr

        self.chk_call_only.blockSignals(True)
        self.chk_call_only.setChecked(bool(getattr(cue, "call_only", False)))
        self.chk_call_only.blockSignals(False)
        cues = list(self.action_editor._catalog() or [])
        callers = [f"#{row + 1}" for row, c in enumerate(cues)
                   if c.media_type == MediaType.ACTION and c.action_spec.get("kind") in ("call", "goto")
                   and c.action_spec.get("cue_ids", [])[:1] == [cue.cue_id]]
        self.lbl_callers.setText(tr("Chiamata o salto da: {}").format(", ".join(callers)) if callers else "")
        self.lbl_callers.setVisible(bool(callers) and self.chk_call_only.isVisible())

    def _load_start_rel(self, cue) -> None:
        ref = getattr(cue, "start_rel_cue", None)
        for w in (self.combo_rel_when, self.combo_rel_cue, self.spin_rel_offset):
            w.blockSignals(True)
        self.combo_rel_when.setCurrentIndex(
            max(0, self.combo_rel_when.findData(getattr(cue, "start_rel_when", "start") if ref else "")))
        self.combo_rel_cue.setCurrentIndex(max(0, self.combo_rel_cue.findData(ref)) if ref else 0)
        self.spin_rel_offset.setValue(float(getattr(cue, "start_rel_offset", 0.0)))
        for w in (self.combo_rel_when, self.combo_rel_cue, self.spin_rel_offset):
            w.blockSignals(False)
        self.lbl_rel_hint.setVisible(False)
        self._sync_rel_enabled()
        self._fill_rel_markers(getattr(cue, "start_rel_marker", None))
        self.load_markers(cue)

    def _apply_start_rel(self, cue) -> None:
        from i18n import tr

        when = self.combo_rel_when.currentData() or ""
        ref = self.combo_rel_cue.currentData()
        self.lbl_rel_hint.setVisible(False)
        if not when or ref is None:
            cue.start_rel_cue = None
        elif int(ref) == cue.cue_id or (self.relative_cycle_check is not None
                                        and self.relative_cycle_check(cue.cue_id, int(ref))):
            self.lbl_rel_hint.setText(tr("Non possibile: quella cue parte già da questa (si avvierebbero "
                                         "a vicenda all'infinito)."))
            self.lbl_rel_hint.setVisible(True)
            return
        elif when == "marker" and self.combo_rel_marker.currentData() is None:
            self.lbl_rel_hint.setText(tr("Quella cue non ha segni: mettine uno sulla sua forma d'onda (◆ Segno)."))
            self.lbl_rel_hint.setVisible(True)
            return
        else:
            cue.start_rel_cue = int(ref)
            cue.start_rel_when = when
            cue.start_rel_marker = self.combo_rel_marker.currentData() if when == "marker" else None
        cue.start_rel_offset = round(self.spin_rel_offset.value(), 2)

    def _load_rate(self, cue) -> None:
        for w in (self.spin_rate, self.chk_keep_pitch):
            w.blockSignals(True)
        self.spin_rate.setValue(round(float(getattr(cue, "playback_rate", 1.0)) * 100.0))
        self.chk_keep_pitch.setChecked(bool(getattr(cue, "keep_pitch", True)))
        for w in (self.spin_rate, self.chk_keep_pitch):
            w.blockSignals(False)

    def _load_audio_output(self, key: str) -> None:
        self.combo_audio_output.blockSignals(True)
        self.combo_audio_output.setCurrentIndex(max(0, self.combo_audio_output.findData(key)))
        self.combo_audio_output.blockSignals(False)

    def _clock_value(self, cue) -> str:
        """2.6: the time in the field, or the cue's own while the field holds a half-typed one ("19:5")."""
        from engine.clock_plan import normalize_clock

        if not self.edit_clock.hasAcceptableInput():
            return getattr(cue, "start_clock", "")
        return normalize_clock(self.edit_clock.text())

    def _one_way_to_start(self, cue, reload: bool = True) -> None:
        """A cue starts at a time of day OR relative to another cue, never both: the last one set wins."""
        if not getattr(cue, "start_clock", "") or getattr(cue, "start_rel_cue", None) is None:
            return
        if getattr(self, "_last_field", "") == "start_rel":
            cue.start_clock = ""
            if reload:
                self.edit_clock.blockSignals(True)
                self.edit_clock.clear()
                self.edit_clock.blockSignals(False)
        else:
            cue.start_rel_cue = None
            if reload:
                self._load_start_rel(cue)

    def _refresh_hold_warning(self) -> None:
        """4.4: a timed picture shown shorter than its passages + 0.5 s is never seen still."""
        if getattr(self, "_current_media_type", None) != MediaType.IMAGE:
            return
        from engine.picture_timing import min_hold_seconds, too_short
        from i18n import tr

        args = (self.spin_fade_in.value(), self.spin_fade_out.value(), self.spin_crossfade.value())
        if too_short(self.spin_hold_time.value(), *args):
            least = f"{min_hold_seconds(*args):g}"
            self.lbl_hold_hint.setText(tr("⚠ almeno {} s").format(least))
            self.lbl_hold_hint.setToolTip(
                tr("⚠ Tempo sullo schermo troppo breve: almeno {} s (passaggi + 0,5 s)").format(least))
            self.lbl_hold_hint.setStyleSheet(
                "color: #fbbf24; font-size: 10px; font-weight: bold; border: none; background: transparent;")
        else:
            self.lbl_hold_hint.setText(tr("0 s = Infinita in Live"))
            self.lbl_hold_hint.setToolTip("")
            self.lbl_hold_hint.setStyleSheet("color: #64748b; font-size: 10px; border: none; background: transparent;")

    def _emit_change(self, field_key: str) -> None:
        self._last_field = field_key
        if field_key in ("hold_time", "fade_in", "fade_out", "crossfade"):
            self._refresh_hold_warning()  # 4.4 (also while the fields are being loaded)
        if field_key in ("crop_l", "crop_r", "crop_t", "crop_b"):
            self._refresh_cached_norm_from_spins()
        if not self._updating:
            self.batch_field_edited.emit(field_key)
            self.value_changed.emit()

    def _on_loop_chk_toggled(self, checked: bool) -> None:
        self.combo_loop_mode.setEnabled(checked)
        self.spin_loop_count.setEnabled(checked)
        self.spin_loop_xfade.setEnabled(checked)
        self._emit_change("loop")

    def _on_loop_mode_changed(self, index: int) -> None:
        self.spin_loop_count.setVisible(index == _LOOP_CUSTOM_IDX)
        self._emit_change("loop")

    # ── Crop Unit (% <-> px) Helpers ──────────────────────────────────

    def _spin_to_norm(self, spin: SmartDoubleSpinBox, is_horizontal: bool) -> float:
        if self._crop_unit == "px":
            ref = self._crop_ref_w if is_horizontal else self._crop_ref_h
            return round(max(0.0, min(0.99, spin.value() / max(1, ref))), 6)
        return round(max(0.0, min(0.99, spin.value() / 100.0)), 6)

    def _norm_to_spin_val(self, norm: float, is_horizontal: bool) -> float:
        if self._crop_unit == "px":
            ref = self._crop_ref_w if is_horizontal else self._crop_ref_h
            return float(round(max(0.0, min(0.99, norm)) * max(1, ref)))
        return round(max(0.0, min(0.99, norm)) * 100.0, 1)

    def _refresh_cached_norm_from_spins(self) -> None:
        self._norm_crop = (
            self._spin_to_norm(self.spin_crop_l, True),
            self._spin_to_norm(self.spin_crop_r, True),
            self._spin_to_norm(self.spin_crop_t, False),
            self._spin_to_norm(self.spin_crop_b, False),
        )

    def _reconfigure_crop_spins_display(self) -> None:
        """Update spinbox ranges/suffixes and re-render cached normalized margins cleanly."""
        was_updating = self._updating
        self._updating = True
        try:
            nl, nr, nt, nb = self._norm_crop
            is_px = (self._crop_unit == "px")
            specs = (
                (self.spin_crop_l, nl, True),
                (self.spin_crop_r, nr, True),
                (self.spin_crop_t, nt, False),
                (self.spin_crop_b, nb, False),
            )
            for spin, norm_val, horiz in specs:
                spin.blockSignals(True)
                if is_px:
                    ref = max(2, self._crop_ref_w if horiz else self._crop_ref_h)
                    spin.setDecimals(0)
                    spin.setRange(0.0, float(ref - 1))
                    spin.setSingleStep(1.0)
                    spin.setSuffix(" px")
                else:
                    spin.setDecimals(1)
                    spin.setRange(0.0, 99.0)
                    spin.setSingleStep(1.0)
                    spin.setSuffix(" %")
                spin.setValue(self._norm_to_spin_val(norm_val, horiz))
                spin.blockSignals(False)
        finally:
            self._updating = was_updating

    def set_crop_unit(self, unit: str) -> None:
        """Switch crop spinbox display between '%' ('pct') and pixels ('px')."""
        target = "px" if unit == "px" else "pct"
        self.btn_crop_pct.setChecked(target == "pct")
        self.btn_crop_px.setChecked(target == "px")
        if target == self._crop_unit:
            return
        self._refresh_cached_norm_from_spins()
        self._crop_unit = target
        self._reconfigure_crop_spins_display()

    def set_crop_reference_size(self, width: int, height: int) -> None:
        """Set pixel dimensions of the active media for accurate px cropping."""
        w = max(1, int(width)) if width > 0 else 1920
        h = max(1, int(height)) if height > 0 else 1080
        self._crop_ref_w = w
        self._crop_ref_h = h
        self.lbl_crop_ref.setText(f"{w}×{h} px")
        if self._crop_unit == "px":
            self._reconfigure_crop_spins_display()

    # ── Public Helpers & State Sync ───────────────────────────────────

    def nudge_position(self, dx: float, dy: float) -> None:
        """Move the video/image position by *dx*/*dy* normalised units.

        Used by the arrow-key shortcuts: the clamp is applied by the spinboxes
        so the value can never leave the valid range.
        """
        nx = round(max(-2.0, min(2.0, self.spin_pos_x.value() + dx)), 2)
        ny = round(max(-2.0, min(2.0, self.spin_pos_y.value() + dy)), 2)
        self.set_position_silent(nx, ny)
        self._emit_change("position")

    def reset_position(self) -> None:
        """Centre the media on screen (position 0,0)."""
        self.set_position_silent(0.0, 0.0)
        self._emit_change("position")

    def reset_scale(self) -> None:
        """Restore the scale slider to 100 %."""
        self.slider_scale.setValue(100)

    def reset_crop(self) -> None:
        """Remove every crop margin (left/right/top/bottom = 0)."""
        self.set_crop_silent(0.0, 0.0, 0.0, 0.0)
        self._emit_change("crop_reset")

    def nudge_rotation(self, delta: float) -> None:
        """Rotate by *delta* degrees (buttons use ±90°) and notify the controller."""
        self.spin_rotation.setValue(normalize_rotation(self.spin_rotation.value() + delta))

    def reset_rotation(self) -> None:
        """Bring the media back upright (0°)."""
        self.spin_rotation.setValue(0.0)

    def clear_mask(self) -> None:
        """Drop the polygon mask and restore the full rectangular image."""
        if not self._mask_polygon:
            return
        self._mask_polygon = []
        self._refresh_mask_label()
        self._emit_change("mask_polygon")

    def set_mask_silent(self, points: list[list[float]] | None) -> None:
        """Replace the mask polygon without emitting a change (used when loading a cue)."""
        self._mask_polygon = sanitize_mask_polygon(points)
        self._refresh_mask_label()

    def _refresh_mask_label(self) -> None:
        """Show the vertex count so the operator can tell a mask is active."""
        count = len(self._mask_polygon)
        self.btn_mask_clear.setEnabled(
            count >= 3 and self._current_media_type == MediaType.IMAGE
        )
        if count >= 3:
            self.lbl_mask_info.setText(f"Maschera: {count} punti")
            self.lbl_mask_info.setStyleSheet(
                "color: #7dd3fc; font-size: 10px; font-family: monospace; background: transparent;"
            )
        else:
            self.lbl_mask_info.setText("Nessuna maschera")
            self.lbl_mask_info.setStyleSheet(
                "color: #64748b; font-size: 10px; font-family: monospace; background: transparent;"
            )

    def reset_in_out(self) -> None:
        """Ask the controller to clear the in/out points of the selected cue."""
        self.in_out_reset_requested.emit()

    def set_layer_checked(self, layer: int | None) -> None:
        """Highlight the layer button matching *layer* (``None`` clears all)."""
        for idx, btn in self._layer_buttons.items():
            btn.setChecked(layer == idx)

    def _on_output_target_clicked(self, target: str) -> None:
        self.set_output_target_checked(target)
        self.output_target_selected.emit(target)

    def set_output_target_checked(self, target: str | None) -> None:
        """Check the A or B projector button; ``None`` clears both (mixed selection)."""
        for key, btn in self._output_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(key == target)
            btn.blockSignals(False)

    def set_dual_mode(self, enabled: bool) -> None:
        """Show the A/B projector selector only when two independent outputs are in use."""
        self.frame_output_target.setVisible(bool(enabled))

    def set_layer_conflict(self, conflict: Any | None = None) -> None:
        """Display or hide visual pre-flight layer collision alert in Card 2 and Group Tab."""
        if conflict:
            reason = conflict.reason if hasattr(conflict, "reason") else str(conflict)
            self.lbl_layer_conflict.setText(f"⚠️ {reason}")
            self.lbl_layer_conflict.setVisible(True)
            self.lbl_group_layer_conflict.setText(f"⚠️ {reason}")
            self.lbl_group_layer_conflict.setVisible(True)
        else:
            self.lbl_layer_conflict.setText("")
            self.lbl_layer_conflict.setVisible(False)
            self.lbl_group_layer_conflict.setText("")
            self.lbl_group_layer_conflict.setVisible(False)

    def set_loudness_result(self, lufs: float, peak: float, gain_db: float) -> None:
        """Update loudness readout card with analyzed EBU R128 values."""
        sign = "+" if gain_db > 0 else ""
        self.lbl_loudness_info.setText(
            f"📊 {lufs:.1f} LUFS | Picco: {peak:.1f} dBFS | Auto-Gain: {sign}{gain_db:.1f} dB"
        )
        self.lbl_loudness_info.setStyleSheet(
            "background-color: #0c2017; color: #34d399; border: 1px solid #059669; "
            "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
        )

    def set_color_silent(self, color_hex: str | None) -> None:
        """Set the cue colour without emitting a change signal.

        ``None`` selects the neutral (no colour) swatch.
        """
        clean = _sanitize_hex_color(color_hex) if color_hex is not None else "__MIXED__"
        for hv, btn in self._color_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(color_hex is not None and hv == clean)
            btn.blockSignals(False)
        for hv, btn in self._group_color_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(color_hex is not None and hv == clean)
            btn.blockSignals(False)

    def set_follow_mode_silent(self, mode: str | None, *, enabled: bool = True) -> None:
        """Set the follow-mode combo without emitting a change.

        ``None`` shows the mixed-selection state; *enabled* greys the control
        out when the selected cue cannot auto-follow (e.g. an image).
        """
        for m, btn in self._follow_buttons.items():
            btn.blockSignals(True)
            btn.setEnabled(enabled)
            btn.setChecked(enabled and (m == mode))
            btn.blockSignals(False)

    def set_position_silent(self, pos_x: float, pos_y: float) -> None:
        """Move the position spinboxes without emitting a change signal."""
        for w, val in ((self.spin_pos_x, pos_x), (self.spin_pos_y, pos_y)):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)

    def set_crop_silent(self, crop_l: float, crop_r: float, crop_t: float, crop_b: float) -> None:
        """Set the four crop margins without emitting a change signal."""
        self._norm_crop = (
            max(0.0, min(0.99, crop_l)),
            max(0.0, min(0.99, crop_r)),
            max(0.0, min(0.99, crop_t)),
            max(0.0, min(0.99, crop_b)),
        )
        for w, val, horiz in (
            (self.spin_crop_l, crop_l, True),
            (self.spin_crop_r, crop_r, True),
            (self.spin_crop_t, crop_t, False),
            (self.spin_crop_b, crop_b, False),
        ):
            w.blockSignals(True)
            w.setValue(self._norm_to_spin_val(val, horiz))
            w.blockSignals(False)

    def set_in_silent(self, new_in: float) -> None:
        """Update the in-point control without emitting a change signal."""
        self.spin_in.blockSignals(True)
        self.spin_in.setValue(new_in)
        self.spin_in.blockSignals(False)

    def set_out_silent(self, new_out: float) -> None:
        """Update the out-point control without emitting a change signal."""
        self.spin_out.blockSignals(True)
        self.spin_out.setValue(new_out)
        self.spin_out.blockSignals(False)

    def set_fades_silent(self, fade_in: float | None = None, fade_out: float | None = None) -> None:
        """Update the fade controls without emitting a change signal.

        A ``None`` argument leaves the corresponding control untouched, so
        callers can sync just one of the two fades.
        """
        if fade_in is not None:
            self.spin_fade_in.blockSignals(True)
            self.spin_fade_in.setValue(max(0.0, float(fade_in)))
            self.spin_fade_in.blockSignals(False)
        if fade_out is not None:
            self.spin_fade_out.blockSignals(True)
            self.spin_fade_out.setValue(max(0.0, float(fade_out)))
            self.spin_fade_out.blockSignals(False)

    def set_available_surfaces(self, surfaces: list[Any]) -> None:
        """Populate the surface selection combo box with available virtual surfaces."""
        cur_id = self.combo_surface.currentData()
        self.combo_surface.blockSignals(True)
        self.combo_surface.clear()
        for s in surfaces:
            s_id = getattr(s, "surface_id", None) or (s.get("surface_id", "default") if isinstance(s, dict) else "default")
            s_name = getattr(s, "name", None) or (s.get("name", "Schermo") if isinstance(s, dict) else "Schermo")
            s_mode = getattr(s, "mode", None) or (s.get("mode", "RECTANGLE") if isinstance(s, dict) else "RECTANGLE")
            icon = "⬛" if s_mode == "RECTANGLE" else "⬡"
            self.combo_surface.addItem(f"{icon} {s_name}", s_id)

        idx = self.combo_surface.findData(cur_id)
        if idx >= 0:
            self.combo_surface.setCurrentIndex(idx)
        elif self.combo_surface.count() > 0:
            self.combo_surface.setCurrentIndex(0)
        self.combo_surface.blockSignals(False)

    def sync_header_and_text(self, row: int, cue: Cue) -> None:
        """Refresh the header (Q/name/type) without reloading every control.

        Cheap path used while the cue list is being scrolled or reordered:
        the inspector must follow the selection without flickering.
        """
        ref = format_cue_ref(row, cue)
        self._updating = True
        try:
            self.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
            if cue.media_type == MediaType.GROUP:
                if self.edit_group_q.text() != cue.q_label:
                    self.edit_group_q.setText(cue.q_label)
                if self.edit_group_name.text() != cue.name:
                    self.edit_group_name.setText(cue.name)
                if self.edit_group_notes.text() != cue.notes:
                    self.edit_group_notes.setText(cue.notes)
            else:
                if self.edit_cue_q.text() != cue.q_label:
                    self.edit_cue_q.setText(cue.q_label)
                if self.edit_cue_name.text() != cue.name:
                    self.edit_cue_name.setText(cue.name)
                if self.edit_cue_notes.text() != cue.notes:
                    self.edit_cue_notes.setText(cue.notes)
        finally:
            self._updating = False

    def set_enabled_for_cue(self, enabled: bool, media_type: MediaType | None = None,
                            multi_mode: bool = False) -> None:
        """Enable only the controls that make sense for *media_type*.

        Images hide the audio/automation tabs, groups hide the geometry
        controls, and *multi_mode* (mixed selection) disables the fields whose
        value differs between the selected cues.
        """
        self._last_enable_args = (enabled, media_type, multi_mode)
        is_group = (media_type == MediaType.GROUP)
        is_action = enabled and media_type == MediaType.ACTION
        self._current_media_type = media_type if enabled else None
        self.btn_more.setVisible(False)
        self.lbl_also.setVisible(False)

        # Tab visibility: when GROUP, show tab 3 (Gruppo), hide tabs 0, 1, 2
        # when NOT GROUP, show tabs 0, 1, 2, hide tab 3
        # ACTION: Cue · Tempi and Azione only (no media, no layer)
        if is_group:
            self.tab_widget.setTabVisible(0, False)
            self.tab_widget.setTabVisible(1, False)
            self.tab_widget.setTabVisible(2, False)
            self.tab_widget.setTabVisible(3, True)
            self.tab_widget.setTabVisible(_ACTION_TAB, False)
            self.tab_widget.setCurrentIndex(3)
        elif is_action:
            self.tab_widget.setTabVisible(0, True)
            self.tab_widget.setTabVisible(1, False)
            self.tab_widget.setTabVisible(2, False)
            self.tab_widget.setTabVisible(3, False)
            self.tab_widget.setTabVisible(_ACTION_TAB, True)
            if self.tab_widget.currentIndex() not in (0, _ACTION_TAB):
                self.tab_widget.setCurrentIndex(_ACTION_TAB)
        else:
            self.tab_widget.setTabVisible(0, True)
            self.tab_widget.setTabVisible(1, True)
            self.tab_widget.setTabVisible(2, True)
            self.tab_widget.setTabVisible(3, False)
            self.tab_widget.setTabVisible(_ACTION_TAB, False)
            if self.tab_widget.currentIndex() in (3, _ACTION_TAB):
                self.tab_widget.setCurrentIndex(0)
        self.card_layer.setVisible(not is_action)
        self.chk_exclusive.setVisible(not is_action)
        self.lbl_hold_field.setVisible(not is_action)
        self.spin_hold_time.setVisible(not is_action)

        for btn in self._layer_buttons.values():
            btn.setEnabled(enabled and not is_group)
        for btn in self._color_buttons.values():
            btn.setEnabled(enabled and not is_group)
        for btn in self._follow_buttons.values():
            btn.setEnabled(enabled and not is_group)

        # Group controls
        group_controls = (
            self.edit_group_q, self.edit_group_name, self.edit_group_notes,
            self.spin_group_pre_delay, self.spin_group_post_delay,
            self.btn_group_collapse_toggle, self.btn_group_remove_child, self.btn_group_ungroup,
            self.list_group_children,
        )
        for w in group_controls:
            w.setEnabled(enabled and is_group and not multi_mode)
        for btn in self._group_mode_buttons.values():
            btn.setEnabled(enabled and is_group)
        for btn in self._group_color_buttons.values():
            btn.setEnabled(enabled and is_group)

        identity_enabled = enabled and not multi_mode and not is_group
        self.edit_cue_q.setEnabled(identity_enabled)
        self.edit_cue_name.setEnabled(identity_enabled)
        self.edit_cue_notes.setEnabled(identity_enabled)

        all_media_controls = (
            self.combo_surface, self.btn_manage_surfaces,
            self.spin_pos_x, self.spin_pos_y,
            self.btn_nudge_left, self.btn_nudge_up, self.btn_nudge_down,
            self.btn_nudge_right, self.btn_pos_center,
            self.slider_scale, self.btn_scale_reset,
            self.slider_opacity, self.btn_opacity_reset,
            self.btn_crop_pct, self.btn_crop_px,
            self.spin_crop_l, self.spin_crop_r, self.spin_crop_t, self.spin_crop_b,
            self.btn_crop_reset, self.spin_fade_in, self.spin_fade_out, self.spin_crossfade,
            self.combo_crossfade_style, self.chk_hold_last_frame,
            self.spin_rotation, self.btn_rot_left, self.btn_rot_zero, self.btn_rot_right,
            self.btn_mask_edit, self.btn_mask_clear,
            self.combo_aspect, self.slider_volume, self.btn_volume_reset, self.combo_audio_output,
            self.spin_rate, self.chk_keep_pitch, self.mix_panel,
            self.loop_card, self.chk_loop, self.combo_loop_mode, self.spin_loop_count, self.spin_loop_xfade,
            self.spin_in, self.spin_out, self.btn_io_reset, self.btn_trim_silence, self.spin_hold_time,
            self.spin_pre_delay, self.spin_post_delay,
            self.card_loudness, self.btn_scan_loudness, self.chk_normalize_cue,
            self.btn_optimize_dynamics, self.btn_restore_original,
        )

        if not enabled or media_type is None:
            self.frame_group_membership.setVisible(False)
            self.set_layer_checked(None)
            self.set_color_silent("")
            self.set_follow_mode_silent(FollowMode.MANUAL.value, enabled=False)
            self.edit_cue_q.clear()
            self.edit_cue_name.clear()
            self.edit_cue_notes.clear()
            self.edit_group_q.clear()
            self.edit_group_name.clear()
            self.edit_group_notes.clear()
            self.list_group_children.clear()
            self.lbl_group_stats.setText("📁 0 cue nel gruppo")
            self.lbl_hold_hint.setText("Seleziona una cue")
            self.set_mask_silent(None)
            self.mask_row_widget.setVisible(False)
            for w in all_media_controls:
                w.setEnabled(False)
            return

        if is_group:
            for w in all_media_controls:
                w.setEnabled(False)
            return

        if is_action:
            for w in all_media_controls:
                w.setEnabled(False)
            self.spin_pre_delay.setEnabled(True)
            self.spin_post_delay.setEnabled(True)
            # The action itself is edited one cue at a time.
            self.action_editor.setEnabled(not multi_mode)
            self.lbl_hold_hint.setText("Durata: scheda Azione")
            return

        self.spin_fade_in.setEnabled(True)
        self.spin_fade_out.setEnabled(True)
        self.spin_crossfade.setEnabled(True)
        self.spin_pre_delay.setEnabled(True)
        self.spin_post_delay.setEnabled(True)

        visual_controls = (
            self.combo_surface, self.btn_manage_surfaces,
            self.spin_pos_x, self.spin_pos_y,
            self.btn_nudge_left, self.btn_nudge_up, self.btn_nudge_down,
            self.btn_nudge_right, self.btn_pos_center,
            self.slider_scale, self.btn_scale_reset,
            self.slider_opacity, self.btn_opacity_reset,
            self.btn_crop_pct, self.btn_crop_px,
            self.spin_crop_l, self.spin_crop_r, self.spin_crop_t, self.spin_crop_b,
            self.btn_crop_reset, self.combo_aspect,
            self.spin_rotation, self.btn_rot_left, self.btn_rot_zero, self.btn_rot_right,
            self.btn_mask_edit, self.btn_mask_clear,
        )
        time_controls = (
            self.slider_volume, self.btn_volume_reset,
            self.loop_card, self.chk_loop, self.spin_in, self.spin_out, self.btn_io_reset, self.btn_trim_silence,
            self.card_loudness, self.btn_scan_loudness, self.chk_normalize_cue, self.btn_optimize_dynamics,
        )

        is_visual = media_type in (MediaType.VIDEO, MediaType.IMAGE)
        is_timed = media_type in (MediaType.VIDEO, MediaType.AUDIO)

        for w in visual_controls:
            w.setEnabled(is_visual)
        # The polygon mask only makes sense for still images: a video mask
        # would have to be re-composited on every frame.
        self.mask_row_widget.setVisible(media_type == MediaType.IMAGE)
        self.btn_mask_edit.setEnabled(media_type == MediaType.IMAGE)
        self.btn_mask_clear.setEnabled(media_type == MediaType.IMAGE and bool(self._mask_polygon))
        for w in time_controls:
            w.setEnabled(is_timed)
        self.card_loudness.setVisible(is_timed)

        self.spin_hold_time.setEnabled(media_type == MediaType.IMAGE)
        self.combo_crossfade_style.setEnabled(is_visual)  # 4.4
        self.chk_hold_last_frame.setEnabled(media_type == MediaType.VIDEO)
        self.combo_loop_mode.setEnabled(is_timed and self.chk_loop.isChecked())
        self.spin_loop_count.setEnabled(is_timed and self.chk_loop.isChecked())
        is_sound = media_type == MediaType.AUDIO  # 3.4: the loop crossfade is for sounds
        self.lbl_loop_xfade.setVisible(is_sound)
        self.spin_loop_xfade.setVisible(is_sound)
        self.spin_loop_xfade.setEnabled(is_sound and self.chk_loop.isChecked())

        if media_type == MediaType.IMAGE:
            self.lbl_hold_hint.setText("0 s = Infinita in Live")
            self._refresh_hold_warning()  # 4.4
            self.lbl_visual_guide.setText(
                "Immagine selezionata: trascina il riquadro o gli 8 bordi nell'Anteprima Pre-Viz 16:9."
            )
            self.lbl_visual_guide.setStyleSheet(
                "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
            self.lbl_audio_guide.setText(
                "Nota: Cue Immagine — Fade In/Out e inviluppo Opacità attivi. Volume, Tagli e Loop valgono per Audio/Video."
            )
            self.lbl_audio_guide.setStyleSheet(
                "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
        elif media_type == MediaType.AUDIO:
            self.lbl_hold_hint.setText("Usa IN / OUT o Forma d'Onda")
            self.lbl_visual_guide.setText(
                "Nota: Cue Audio selezionata — Posizione, Zoom, Opacità e Ritaglio sono attivi solo per Video e Immagini."
            )
            self.lbl_visual_guide.setStyleSheet(
                "background-color: #261b05; color: #fef08a; border: 1px solid #d97706; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
            self.lbl_audio_guide.setText(
                "Regola Volume, Fade, punti IN/OUT o Loop; usa la Forma d'Onda sotto per curve e Sezioni A/B/C."
            )
            self.lbl_audio_guide.setStyleSheet(
                "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
        else:
            self.lbl_hold_hint.setText("Usa IN / OUT del video")
            self.lbl_visual_guide.setText(
                "Video selezionato: trascina posizione/crop sull'Anteprima Pre-Viz e attiva MIRROR LIVE per calibrare sul proiettore."
            )
            self.lbl_visual_guide.setStyleSheet(
                "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
            self.lbl_audio_guide.setText(
                "Regola Volume traccia video, Fade In/Out, punti IN/OUT e Loop (o Sezioni nella Timeline)."
            )
            self.lbl_audio_guide.setStyleSheet(
                "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; border-radius: 5px; font-size: 11px; padding: 6px 10px;"
            )
        self._apply_field_visibility(media_type)

    # ── What shows for this type of cue (1.12) and in the basic mode (C2b) ─
    @staticmethod
    def _card_of(widget: QWidget) -> QWidget:
        w = widget
        while w is not None and w.objectName() != "inspCard":
            w = w.parentWidget()
        return w if w is not None else widget

    def _apply_field_visibility(self, media_type: MediaType | None) -> None:
        """A field that does nothing for this type of cue is hidden, not greyed out (1.12)."""
        is_image = media_type == MediaType.IMAGE
        is_audio = media_type == MediaType.AUDIO
        is_visual = media_type in (MediaType.VIDEO, MediaType.IMAGE)
        basic = self._lite and not self._expanded
        self.tab_widget.setTabVisible(1, is_visual and not basic)
        self.tab_widget.setTabText(2, "◐ Transizioni" if is_image else "🎵 Audio · Tagli")
        self.lbl_visual_guide.setVisible(media_type == MediaType.VIDEO)
        self.lbl_audio_guide.setVisible(not is_image and not basic)
        for w in (self.lbl_hold_field, self.spin_hold_time, self.lbl_hold_hint):
            w.setVisible(is_image)
        # Sound too: a new song on the layer of another one crossfades instead of cutting it.
        self.lbl_crossfade.setVisible(True)
        self.spin_crossfade.setVisible(True)
        self.combo_crossfade_style.setVisible(is_visual)  # 4.4: dissolve / slide, pictures only
        self.chk_hold_last_frame.setVisible(media_type == MediaType.VIDEO)
        for card in (self._card_of(self.slider_volume), self._card_of(self.spin_in)):
            card.setVisible(not is_image)
        self.loop_card.setVisible(not is_image and not basic)
        self.card_loudness.setVisible(not is_image and not basic)
        # Basic mode: name, notes, level, fades, from/to, where, then – the rest behind "More".
        for w in (self._pipe_lbl, self.lbl_pre_field, self.spin_pre_delay, self.lbl_post_field,
                  self.spin_post_delay, self.chk_exclusive, self.chk_confirm):
            w.setVisible(not basic)
        for w in (self.lbl_fade_others, self.spin_fade_others):
            w.setVisible(not basic and not is_image)
        for w in (self.chk_adlib, self.lbl_hotkey, self.edit_hotkey, self.combo_hotkey_mode):
            w.setVisible(not basic and not is_image)
        for w in (self.lbl_rel, self.combo_rel_when, self.combo_rel_cue, self.spin_rel_offset, self.chk_call_only,
                  self.lbl_clock, self.edit_clock):
            w.setVisible(not basic and media_type != MediaType.GROUP)
        self.combo_rel_marker.setVisible(not basic and self.combo_rel_when.currentData() == "marker")
        for w in (self.lbl_audio_output, self.combo_audio_output, self.lbl_rate, self.spin_rate,
                  self.chk_keep_pitch):
            w.setVisible(media_type in (MediaType.AUDIO, MediaType.VIDEO))
        self.mix_panel.setVisible(media_type == MediaType.AUDIO and not basic)  # 3.2: the mixer plays sound cues
        for w in (self.lbl_markers, self.combo_markers, self.btn_marker_delete):
            w.setVisible(not basic and media_type in (MediaType.AUDIO, MediaType.VIDEO))
        self.lbl_callers.setVisible(bool(self.lbl_callers.text()) and not basic)
        if self.tab_widget.currentIndex() >= 0 and not self.tab_widget.isTabVisible(self.tab_widget.currentIndex()):
            self.tab_widget.setCurrentIndex(0)
        self.btn_more.setVisible(self._lite)
        self.btn_more.setText("▴ Meno impostazioni" if self._expanded else "▾ Più impostazioni")
        self.lbl_also.setVisible(basic and bool(self.lbl_also.text()))

    def set_lite(self, lite: bool) -> None:
        """The window's view variant: Lite shows the basic inspector (folded)."""
        self._lite = bool(lite)
        self._expanded = False
        self.set_enabled_for_cue(*self._last_enable_args)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.set_enabled_for_cue(*self._last_enable_args)

    def _on_more_clicked(self) -> None:
        self.set_expanded(not self._expanded)

    def set_also(self, cue) -> None:
        """"This cue also has: …" – what the basic mode hides but changes the playback."""
        from i18n import tr

        parts = []
        if cue is not None:
            if cue.pre_delay > 0:
                parts.append(tr("parte {} s dopo il GO").format(f"{cue.pre_delay:.1f}"))
            if cue.post_delay > 0:
                parts.append(tr("aspetta {} s dopo la fine").format(f"{cue.post_delay:.1f}"))
            if getattr(cue, "exclusive", False):
                parts.append(tr("il GO aspetta che finisca"))
            if getattr(cue, "confirm_start", False):
                parts.append(tr("aspetta l'OK"))
            if getattr(cue, "adlib", False):
                parts.append(tr("effetto a richiesta (tasto {})").format(cue.hotkey or "—"))
            if getattr(cue, "fade_others", 0.0) > 0:
                parts.append(tr("all'avvio sfuma le altre in {} s").format(f"{cue.fade_others:.1f}"))
            if getattr(cue, "start_rel_cue", None) is not None:
                parts.append(tr("parte da sola rispetto a un'altra cue"))
            if getattr(cue, "call_only", False):
                parts.append(tr("solo su chiamata"))
            if getattr(cue, "start_clock", ""):
                parts.append(tr("parte alle {}").format(cue.start_clock))
            if cue.loop:
                parts.append(tr("suona in loop") if cue.loop_count <= 0 else tr("si ripete {}×").format(cue.loop_count))
            if cue.sections:
                parts.append(tr("sezioni: {}").format(len(cue.sections)))
            if cue.volume_points:
                parts.append(tr("il volume cambia nel tempo"))
            if getattr(cue, "normalize_audio", False):
                parts.append(tr("volume livellato"))
            changed_picture = (
                abs(cue.position_x) > 1e-6 or abs(cue.position_y) > 1e-6 or abs(cue.scale - 1.0) > 1e-6
                or abs(cue.rotation) > 1e-6 or cue.opacity < 0.999
                or (cue.crop or {}) != _default_crop()
                or bool(getattr(cue, "mask_polygon", None))
            )
            if cue.media_type != MediaType.AUDIO and changed_picture:
                parts.append(tr("immagine modificata (ritaglio, posizione o opacità)"))
            if getattr(cue, "output_target", "A") == "B":
                parts.append(tr("sul proiettore B"))
        self.lbl_also.setText(tr("Questa cue ha anche: {}").format(" · ".join(parts)) if parts else "")
        self.lbl_also.setVisible(self._lite and not self._expanded and bool(parts))

    def _populate_media_fields(self, cue: Cue) -> None:
        surf_idx = self.combo_surface.findData(getattr(cue, "surface_id", "default") or "default")
        self.combo_surface.blockSignals(True)
        if surf_idx >= 0:
            self.combo_surface.setCurrentIndex(surf_idx)
        elif self.combo_surface.count() > 0:
            self.combo_surface.setCurrentIndex(0)
        self.combo_surface.blockSignals(False)

        self.spin_pos_x.setValue(cue.position_x)
        self.spin_pos_y.setValue(cue.position_y)
        self.spin_rotation.setValue(cue.rotation)
        self.set_mask_silent(cue.mask_polygon)
        self.slider_scale.setValue(int(cue.scale * 100))
        self.lbl_scale.setText(f"{cue.scale:.1f}x")
        self.slider_opacity.setValue(int(cue.opacity * 100))
        self.lbl_opacity.setText(f"{int(cue.opacity * 100)}%")

        crop_x = cue.crop.get("x", 0.0)
        crop_y = cue.crop.get("y", 0.0)
        crop_w = cue.crop.get("w", 1.0)
        crop_h = cue.crop.get("h", 1.0)
        self.set_crop_silent(
            crop_x,
            max(0.0, 1.0 - crop_x - crop_w),
            crop_y,
            max(0.0, 1.0 - crop_y - crop_h),
        )

        self.spin_fade_in.setValue(cue.fade_in)
        self.spin_fade_out.setValue(cue.fade_out)
        self.spin_crossfade.setValue(float(getattr(cue, "crossfade", 0.0)))
        for w, set_value in (
            (self.combo_crossfade_style, lambda: self.combo_crossfade_style.setCurrentIndex(
                max(0, self.combo_crossfade_style.findData(getattr(cue, "crossfade_style", "dissolve"))))),
            (self.chk_hold_last_frame, lambda: self.chk_hold_last_frame.setChecked(
                bool(getattr(cue, "hold_last_frame", False)))),
        ):  # 4.4
            w.blockSignals(True)
            set_value()
            w.blockSignals(False)
        self.spin_hold_time.setValue(cue.hold_time)
        self.spin_pre_delay.setValue(getattr(cue, "pre_delay", 0.0))
        self.spin_post_delay.setValue(getattr(cue, "post_delay", 0.0))
        self.slider_volume.setValue(int(cue.volume * 100))

        self.chk_loop.setChecked(cue.loop)
        self.combo_loop_mode.setEnabled(cue.loop)
        self.spin_loop_count.setEnabled(cue.loop)
        self.spin_loop_xfade.setValue(float(getattr(cue, "loop_crossfade", 0.0)))
        self.spin_loop_xfade.setEnabled(cue.loop and cue.media_type == MediaType.AUDIO)

        count = getattr(cue, "loop_count", 0)
        preset_idx = _COUNT_TO_PRESET_IDX.get(count)
        if preset_idx is not None:
            self.combo_loop_mode.setCurrentIndex(preset_idx)
            self.spin_loop_count.setVisible(False)
        else:
            self.combo_loop_mode.setCurrentIndex(_LOOP_CUSTOM_IDX)
            self.spin_loop_count.setValue(count)
            self.spin_loop_count.setVisible(True)

        self.spin_in.setValue(cue.in_point)
        self.spin_out.setValue(cue.out_point if cue.out_point else 0.0)

        aspect_idx = 0
        for idx, (label, val) in enumerate(_ASPECT_OPTIONS):
            if cue.aspect_ratio is not None and cue.aspect_ratio in (val, label):
                aspect_idx = idx
                break
        self.combo_aspect.setCurrentIndex(aspect_idx)

        # Loudness & EBU R128 Normalization
        if cue.loudness_lufs is not None:
            sign = "+" if cue.auto_gain_db > 0 else ""
            self.lbl_loudness_info.setText(
                f"📊 {cue.loudness_lufs:.1f} LUFS | Picco: {cue.true_peak_dbfs or 0.0:.1f} dBFS | Auto-Gain: {sign}{cue.auto_gain_db:.1f} dB"
            )
            self.lbl_loudness_info.setStyleSheet(
                "background-color: #0c2017; color: #34d399; border: 1px solid #059669; "
                "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
            )
        else:
            self.lbl_loudness_info.setText("📊 Loudness: Non analizzato")
            self.lbl_loudness_info.setStyleSheet(
                "background-color: #0b111a; color: #94a3b8; border: 1px solid #1e293b; "
                "border-radius: 4px; font-family: monospace; font-size: 10px; padding: 4px 6px;"
            )

        self.chk_normalize_cue.blockSignals(True)
        self.chk_normalize_cue.setChecked(bool(getattr(cue, "normalize_audio", False)))
        self.chk_normalize_cue.blockSignals(False)

        has_orig = bool(getattr(cue, "original_file_path", None))
        self.btn_restore_original.setVisible(has_orig)

    def load_cue(self, cue: Cue | None, row: int = -1) -> None:
        """Load a single cue into the inspector, or disable when *cue* is None."""
        self._multi_mode = False
        self.lbl_multi_banner.setVisible(False)
        self.lbl_layer_conflict.setVisible(False)
        self.lbl_group_layer_conflict.setVisible(False)

        if cue is None:
            self.setTitle("ISPETTORE CUE (Nessuna cue selezionata)")
            self.set_enabled_for_cue(False)
            return

        self._updating = True
        try:
            ref = format_cue_ref(row, cue)
            self.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
            self.set_enabled_for_cue(True, cue.media_type, multi_mode=False)

            if cue.media_type == MediaType.GROUP:
                self.frame_group_membership.setVisible(False)
                self.edit_group_q.setText(cue.q_label)
                self.edit_group_name.setText(cue.name)
                self.edit_group_notes.setText(cue.notes)
                self.spin_group_pre_delay.setValue(getattr(cue, "pre_delay", 0.0))
                self.spin_group_post_delay.setValue(getattr(cue, "post_delay", 0.0))
                self.set_color_silent(getattr(cue, "color", ""))
                self.set_group_mode_checked(getattr(cue, "group_mode", GroupMode.STEP.value))
                if getattr(cue, "collapsed", False):
                    self.btn_group_collapse_toggle.setText("▼ Espandi Gruppo in Scaletta")
                else:
                    self.btn_group_collapse_toggle.setText("▶ Collassa Gruppo in Scaletta")
            else:
                if cue.parent_id is not None:
                    self.frame_group_membership.setVisible(True)
                    self.lbl_group_membership.setText("📁 Questa cue appartiene a una Scena / Gruppo")
                else:
                    self.frame_group_membership.setVisible(False)
                self.edit_cue_q.setText(cue.q_label)
                self.edit_cue_name.setText(cue.name)
                self.edit_cue_notes.setText(cue.notes)
                self.edit_script_page.setText(getattr(cue, "script_page", ""))
                self.edit_script_line.setText(getattr(cue, "script_line", ""))
                self.set_layer_checked(cue.layer)
                self.set_output_target_checked(getattr(cue, "output_target", "A"))
                self.set_color_silent(getattr(cue, "color", ""))
                self.set_follow_mode_silent(cue.follow_mode, enabled=True)
                self.chk_exclusive.setChecked(bool(getattr(cue, "exclusive", False)))
                self.chk_confirm.setChecked(bool(getattr(cue, "confirm_start", False)))
                self.spin_fade_others.blockSignals(True)
                self.spin_fade_others.setValue(float(getattr(cue, "fade_others", 0.0)))
                self.spin_fade_others.blockSignals(False)
                for w, setter in ((self.chk_adlib, lambda: self.chk_adlib.setChecked(bool(getattr(cue, "adlib", False)))),
                                  (self.edit_hotkey, lambda: self.edit_hotkey.setText(getattr(cue, "hotkey", ""))),
                                  (self.combo_hotkey_mode, lambda: self.combo_hotkey_mode.setCurrentIndex(
                                      max(0, self.combo_hotkey_mode.findData(getattr(cue, "hotkey_mode", "trigger")))))):
                    w.blockSignals(True)
                    setter()
                    w.blockSignals(False)
                self._load_start_rel(cue)
                self._load_call_only(cue)
                self._load_audio_output(getattr(cue, "audio_output", "stage"))
                self.mix_panel.load(getattr(cue, "audio_mix", {}), getattr(cue, "audio_output", "stage"))
                self._load_rate(cue)
                self.edit_clock.blockSignals(True)
                self.edit_clock.setText(getattr(cue, "start_clock", ""))
                self.edit_clock.blockSignals(False)
                self._populate_media_fields(cue)
                self.set_also(cue)
                if cue.media_type == MediaType.ACTION:
                    self.action_editor.load(cue.action_spec, cue.cue_id)
        finally:
            self._updating = False

    def load_selection(self, cues: list[Cue], anchor_cue: Cue | None = None,
                       anchor_row: int = -1) -> None:
        """Load 0, 1, or N selected cues with same-type batch editing support."""
        self.lbl_layer_conflict.setVisible(False)
        self.lbl_group_layer_conflict.setVisible(False)
        if not cues:
            self.load_cue(None)
            return
        if len(cues) == 1:
            self.load_cue(cues[0], anchor_row)
            return

        self.frame_group_membership.setVisible(False)

        media_types = {c.media_type for c in cues}
        if len(media_types) > 1:
            self._multi_mode = True
            type_list = ", ".join(sorted(mt.value for mt in media_types))
            self.setTitle(f"ISPETTORE CUE — Selezione Mista ({len(cues)} cue)")
            self.lbl_multi_banner.setText(
                f"⚠ Selezione mista ({type_list}): seleziona solo file dello stesso tipo per modifiche comuni."
            )
            self.lbl_multi_banner.setStyleSheet(
                "background-color: #3a2307; color: #fbbf24; border: 1px solid #d97706; "
                "border-radius: 4px; padding: 5px 7px; font-size: 10px; font-weight: bold;"
            )
            self.lbl_multi_banner.setVisible(True)
            self.set_enabled_for_cue(False)
            return

        mtype = cues[0].media_type
        lead = anchor_cue if (anchor_cue in cues) else cues[0]
        layers = {c.layer for c in cues}
        common_layer = next(iter(layers)) if len(layers) == 1 else None
        targets = {normalize_output_target(getattr(c, "output_target", "A")) for c in cues}
        common_target: str | None = next(iter(targets)) if len(targets) == 1 else None
        colors = {getattr(c, "color", "") for c in cues}
        common_color: str | None = next(iter(colors)) if len(colors) == 1 else None
        modes = {c.follow_mode for c in cues}
        common_mode: str | None = next(iter(modes)) if len(modes) == 1 else None

        self._multi_mode = True
        self._updating = True
        try:
            self.setTitle(f"ISPETTORE CUE — {len(cues)} {mtype.value} (Modifica Multipla)")
            layer_hint = (
                f"Layer comune: L{common_layer}"
                if common_layer is not None
                else "Layer misti (clicca L1/L2/L3 per uniformare)"
            )
            self.lbl_multi_banner.setText(
                f"⚡ MODIFICA MULTIPLA: {len(cues)} file {mtype.value} selezionati • {layer_hint}.\n"
                "Ogni parametro modificato verrà applicato a tutti gli elementi selezionati."
            )
            self.lbl_multi_banner.setStyleSheet(
                "background-color: #0d2b3e; color: #7dd3fc; border: 1px solid #0284c7; "
                "border-radius: 4px; padding: 5px 7px; font-size: 10px; font-weight: bold;"
            )
            self.lbl_multi_banner.setVisible(True)

            self.set_enabled_for_cue(True, mtype, multi_mode=True)
            self.edit_cue_q.setText("(Multiplo)")
            self.edit_cue_name.setText(f"[{len(cues)} file {mtype.value} selezionati]")
            self.edit_cue_notes.setText("")
            self.set_layer_checked(common_layer)
            self.set_output_target_checked(common_target)
            self.set_color_silent(common_color)
            self.set_follow_mode_silent(common_mode, enabled=True)
            self.chk_exclusive.setChecked(all(getattr(c, "exclusive", False) for c in cues))
            self.chk_confirm.setChecked(all(getattr(c, "confirm_start", False) for c in cues))
            self._populate_media_fields(lead)
            self.load_markers(lead)  # the anchor's marks (the ones ✕ deletes and the waveform shows)
            outs = {getattr(c, "audio_output", "stage") for c in cues}
            self._load_audio_output(outs.pop() if len(outs) == 1 else lead.audio_output)
            self.mix_panel.load(getattr(lead, "audio_mix", {}), self.combo_audio_output.currentData() or "stage")
            self.edit_clock.blockSignals(True)
            self.edit_clock.setText(lead.start_clock if all(c.start_clock == lead.start_clock for c in cues) else "")
            self.edit_clock.blockSignals(False)
            if mtype == MediaType.ACTION:
                self.action_editor.load(lead.action_spec, lead.cue_id)
        finally:
            self._updating = False

    def apply_to_cue(self, cue: Cue) -> None:
        """Write all single-cue inspector field values onto *cue*."""
        if cue.media_type == MediaType.GROUP:
            cue.q_label = self.edit_group_q.text().strip()
            new_name = self.edit_group_name.text().strip()
            if new_name:
                cue.name = new_name
            cue.notes = self.edit_group_notes.text().strip()
            cue.pre_delay = self.spin_group_pre_delay.value()
            cue.post_delay = self.spin_group_post_delay.value()
            return

        if cue.media_type == MediaType.ACTION:
            # No media fields: the disabled media controls still hold the
            # values of the previous cue and must not be written here.
            cue.q_label = self.edit_cue_q.text().strip()
            new_name = self.edit_cue_name.text().strip()
            if new_name:
                cue.name = new_name
            cue.notes = self.edit_cue_notes.text().strip()
            cue.pre_delay = self.spin_pre_delay.value()
            cue.post_delay = self.spin_post_delay.value()
            self._apply_start_rel(cue)  # an action can start relative to a cue, at a time, or only by a call
            cue.call_only = self.chk_call_only.isChecked()
            cue.start_clock = self._clock_value(cue)
            self._one_way_to_start(cue)
            if self.action_editor.cue_id() == cue.cue_id:
                new_spec = self.action_editor.spec()
                self._rename_default_action(cue, new_spec["kind"])
                cue.action_spec = new_spec
            return

        cue.q_label = self.edit_cue_q.text().strip()
        new_name = self.edit_cue_name.text().strip()
        if new_name:
            cue.name = new_name
        cue.notes = self.edit_cue_notes.text().strip()
        cue.script_page = self.edit_script_page.text().strip()
        cue.script_line = self.edit_script_line.text().strip()
        cue.exclusive = self.chk_exclusive.isChecked()
        cue.confirm_start = self.chk_confirm.isChecked()
        cue.fade_others = round(self.spin_fade_others.value(), 2)
        cue.adlib = self.chk_adlib.isChecked()
        cue.hotkey = self.edit_hotkey.text().strip()[:1].upper()
        cue.hotkey_mode = self.combo_hotkey_mode.currentData() or "trigger"
        self._apply_start_rel(cue)
        cue.call_only = self.chk_call_only.isChecked()
        cue.start_clock = self._clock_value(cue)
        self._one_way_to_start(cue)
        if cue.media_type in (MediaType.AUDIO, MediaType.VIDEO):
            cue.audio_output = self.combo_audio_output.currentData() or "stage"
            cue.playback_rate = round(self.spin_rate.value() / 100.0, 2)
            cue.keep_pitch = self.chk_keep_pitch.isChecked()
        if cue.media_type == MediaType.AUDIO:
            cue.audio_mix = self.mix_panel.values()  # 3.2 / 3.9

        checked_target = next(
            (t for t, btn in self._output_buttons.items() if btn.isChecked()), "A"
        )
        cue.output_target = normalize_output_target(checked_target)

        cue.position_x = round(self.spin_pos_x.value(), 3)
        cue.position_y = round(self.spin_pos_y.value(), 3)
        cue.rotation = normalize_rotation(self.spin_rotation.value())
        cue.mask_polygon = list(self._mask_polygon)
        cue.scale = round(self.slider_scale.value() / 100.0, 2)
        cue.opacity = round(self.slider_opacity.value() / 100.0, 2)

        crop_l = self._spin_to_norm(self.spin_crop_l, True)
        crop_r = self._spin_to_norm(self.spin_crop_r, True)
        crop_t = self._spin_to_norm(self.spin_crop_t, False)
        crop_b = self._spin_to_norm(self.spin_crop_b, False)
        if crop_l + crop_r > 0.99:
            crop_r = max(0.0, round(0.99 - crop_l, 6))
        if crop_t + crop_b > 0.99:
            crop_b = max(0.0, round(0.99 - crop_t, 6))

        cue.crop = {
            "x": round(crop_l, 6),
            "y": round(crop_t, 6),
            "w": max(0.01, round(1.0 - crop_l - crop_r, 6)),
            "h": max(0.01, round(1.0 - crop_t - crop_b, 6)),
        }

        cue.fade_in = self.spin_fade_in.value()
        cue.fade_out = self.spin_fade_out.value()
        cue.crossfade = self.spin_crossfade.value()
        cue.crossfade_style = self.combo_crossfade_style.currentData() or "dissolve"
        if cue.media_type == MediaType.VIDEO:
            cue.hold_last_frame = self.chk_hold_last_frame.isChecked()
        cue.hold_time = self.spin_hold_time.value()
        cue.pre_delay = self.spin_pre_delay.value()
        cue.post_delay = self.spin_post_delay.value()
        cue.volume = self.slider_volume.value() / 100.0
        cue.normalize_audio = self.chk_normalize_cue.isChecked()

        self._apply_loop_to_cue(cue)

        cue.in_point = self.spin_in.value()
        out_val = self.spin_out.value()
        if out_val > 0 and out_val <= cue.in_point:
            out_val = round(cue.in_point + 0.05, 2)
            self.set_out_silent(out_val)
        cue.out_point = out_val if out_val > 0 else None

        ar_data = self.combo_aspect.currentData()
        cue.aspect_ratio = ar_data if ar_data is not None else None

        surf_data = self.combo_surface.currentData()
        if surf_data:
            cue.surface_id = str(surf_data)

    def _rename_default_action(self, cue: Cue, new_kind: str) -> None:
        """A cue still carrying the default name of its old kind follows the new kind."""
        from engine.action_cues import default_action_name
        from i18n import tr

        old_kind = cue.action_spec.get("kind", "")
        if new_kind == old_kind or cue.name != tr(default_action_name(old_kind)):
            return
        cue.name = tr(default_action_name(new_kind))
        self.edit_cue_name.setText(cue.name)

    def _apply_loop_to_cue(self, cue: Cue) -> None:
        cue.loop = self.chk_loop.isChecked()
        if cue.media_type == MediaType.AUDIO:
            cue.loop_crossfade = round(float(self.spin_loop_xfade.value()), 2)  # 3.4
        if cue.loop:
            idx = self.combo_loop_mode.currentIndex()
            if 0 <= idx < len(_LOOP_PRESET_COUNTS):
                cue.loop_count = _LOOP_PRESET_COUNTS[idx]
            else:
                cue.loop_count = max(1, int(self.spin_loop_count.value()))
        else:
            cue.loop_count = 0

    @staticmethod
    def _update_crop_edge(cue: Cue, edge: str, norm_val: float) -> None:
        c = dict(cue.crop) if isinstance(cue.crop, dict) else {}
        cur_l = float(c.get("x", 0.0))
        cur_t = float(c.get("y", 0.0))
        cur_r = max(0.0, 1.0 - cur_l - float(c.get("w", 1.0)))
        cur_b = max(0.0, 1.0 - cur_t - float(c.get("h", 1.0)))
        if edge == "l":
            cur_l = max(0.0, min(norm_val, 0.99 - cur_r))
        elif edge == "r":
            cur_r = max(0.0, min(norm_val, 0.99 - cur_l))
        elif edge == "t":
            cur_t = max(0.0, min(norm_val, 0.99 - cur_b))
        elif edge == "b":
            cur_b = max(0.0, min(norm_val, 0.99 - cur_t))
        cue.crop = {
            "x": round(cur_l, 6),
            "y": round(cur_t, 6),
            "w": max(0.01, round(1.0 - cur_l - cur_r, 6)),
            "h": max(0.01, round(1.0 - cur_t - cur_b, 6)),
        }

    def apply_batch_field(self, field_key: str, cues: list[Cue]) -> None:
        """Apply ONLY the edited *field_key* across all *cues* without touching other properties."""
        if not cues:
            return
        crop_edge_spins = {
            "crop_l": ("l", self.spin_crop_l, True),
            "crop_r": ("r", self.spin_crop_r, True),
            "crop_t": ("t", self.spin_crop_t, False),
            "crop_b": ("b", self.spin_crop_b, False),
        }

        for cue in cues:
            if field_key == "exclusive":
                cue.exclusive = self.chk_exclusive.isChecked()
            elif field_key == "confirm_start":
                cue.confirm_start = self.chk_confirm.isChecked()
            elif field_key == "fade_others":
                cue.fade_others = round(self.spin_fade_others.value(), 2)
            elif field_key == "adlib":
                cue.adlib = self.chk_adlib.isChecked()
            elif field_key == "hotkey":
                cue.hotkey = self.edit_hotkey.text().strip()[:1].upper()
            elif field_key == "hotkey_mode":
                cue.hotkey_mode = self.combo_hotkey_mode.currentData() or "trigger"
            elif field_key == "start_rel":
                self._apply_start_rel(cue)
                self._one_way_to_start(cue, reload=False)
            elif field_key == "script_page":
                cue.script_page = self.edit_script_page.text().strip()
            elif field_key == "script_line":
                cue.script_line = self.edit_script_line.text().strip()
            elif field_key == "playback_rate":
                cue.playback_rate = round(self.spin_rate.value() / 100.0, 2)
            elif field_key == "keep_pitch":
                cue.keep_pitch = self.chk_keep_pitch.isChecked()
            elif field_key == "audio_output":
                cue.audio_output = self.combo_audio_output.currentData() or "stage"
            elif field_key == "audio_mix":
                if cue.media_type == MediaType.AUDIO:
                    cue.audio_mix = self.mix_panel.values()
            elif field_key == "call_only":
                cue.call_only = self.chk_call_only.isChecked()
            elif field_key == "start_clock":
                cue.start_clock = self._clock_value(cue)
                self._one_way_to_start(cue, reload=False)
            elif field_key == "pos_x":
                cue.position_x = round(self.spin_pos_x.value(), 3)
            elif field_key == "pos_y":
                cue.position_y = round(self.spin_pos_y.value(), 3)
            elif field_key == "position":
                cue.position_x = round(self.spin_pos_x.value(), 3)
                cue.position_y = round(self.spin_pos_y.value(), 3)
            elif field_key == "scale":
                cue.scale = round(self.slider_scale.value() / 100.0, 2)
            elif field_key == "rotation":
                cue.rotation = normalize_rotation(self.spin_rotation.value())
            elif field_key == "mask_polygon":
                cue.mask_polygon = list(self._mask_polygon)
            elif field_key == "opacity":
                cue.opacity = round(self.slider_opacity.value() / 100.0, 2)
            elif field_key in crop_edge_spins:
                edge, spin, horiz = crop_edge_spins[field_key]
                self._update_crop_edge(cue, edge, self._spin_to_norm(spin, horiz))
            elif field_key == "crop_reset":
                cue.crop = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
            elif field_key == "fade_in":
                cue.fade_in = self.spin_fade_in.value()
            elif field_key == "fade_out":
                cue.fade_out = self.spin_fade_out.value()
            elif field_key == "crossfade":
                cue.crossfade = self.spin_crossfade.value()
            elif field_key == "crossfade_style":
                cue.crossfade_style = self.combo_crossfade_style.currentData() or "dissolve"
            elif field_key == "hold_last_frame":
                if cue.media_type == MediaType.VIDEO:
                    cue.hold_last_frame = self.chk_hold_last_frame.isChecked()
            elif field_key == "hold_time":
                cue.hold_time = self.spin_hold_time.value()
            elif field_key == "pre_delay":
                cue.pre_delay = self.spin_pre_delay.value()
            elif field_key == "post_delay":
                cue.post_delay = self.spin_post_delay.value()
            elif field_key == "volume":
                cue.volume = self.slider_volume.value() / 100.0
            elif field_key == "loop":
                self._apply_loop_to_cue(cue)
            elif field_key == "in_point":
                new_in = self.spin_in.value()
                cue.in_point = new_in
                if cue.out_point is not None and cue.out_point <= new_in:
                    cue.out_point = round(new_in + 0.05, 2)
            elif field_key == "out_point":
                out_val = self.spin_out.value()
                if out_val <= 0.0:
                    cue.out_point = None
                elif out_val <= cue.in_point:
                    cue.out_point = round(cue.in_point + 0.05, 2)
                else:
                    cue.out_point = out_val
            elif field_key == "aspect_ratio":
                ar_data = self.combo_aspect.currentData()
                cue.aspect_ratio = ar_data if ar_data is not None else None
            elif field_key == "surface_id":
                s_id = self.combo_surface.currentData() or "default"
                cue.surface_id = str(s_id)
            elif field_key == "group_q":
                cue.q_label = self.edit_group_q.text().strip()
            elif field_key == "group_name":
                new_n = self.edit_group_name.text().strip()
                if new_n:
                    cue.name = new_n
            elif field_key == "group_notes":
                cue.notes = self.edit_group_notes.text().strip()
            elif field_key == "group_pre_delay":
                cue.pre_delay = self.spin_group_pre_delay.value()
            elif field_key == "group_post_delay":
                cue.post_delay = self.spin_group_post_delay.value()
