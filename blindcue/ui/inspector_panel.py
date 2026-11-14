"""Right-column Tabbed Cue Inspector panel (Cue & Timing tabs, Visual transform/crop, Audio/Loop/Fades)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
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

from models.cue import Cue, FollowMode, GroupMode, MediaType, _sanitize_hex_color
from ui.cue_table import format_cue_ref
from ui.spinboxes import InPointSpinBox, OutPointSpinBox, SmartDoubleSpinBox
from ui.theme import CLR_ACCENT, CUE_COLOR_PALETTE, NUDGE_BTN_STYLE, get_active_theme

# Preset index <-> repetition count mapping (0 = infinite loop)
_LOOP_PRESET_COUNTS = (0, 2, 3, 4, 5, 10)
_COUNT_TO_PRESET_IDX = {count: idx for idx, count in enumerate(_LOOP_PRESET_COUNTS)}
_LOOP_CUSTOM_IDX = len(_LOOP_PRESET_COUNTS)

_ASPECT_OPTIONS: list[tuple[str, Optional[str]]] = [
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
    batch_field_edited = Signal(str)
    layer_selected = Signal(int)
    in_out_reset_requested = Signal()
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("ISPETTORE CUE (Nessuna cue selezionata)", parent)
        self._updating: bool = False
        self._multi_mode: bool = False
        self._crop_unit: str = "pct"   # "pct" (%) or "px" (pixels)
        self._crop_ref_w: int = 1920
        self._crop_ref_h: int = 1080
        self._norm_crop: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._layer_buttons: dict[int, QPushButton] = {}
        self._color_buttons: dict[str, QPushButton] = {}
        self._follow_buttons: dict[str, QPushButton] = {}
        self._group_color_buttons: dict[str, QPushButton] = {}
        self._group_mode_buttons: dict[str, QPushButton] = {}

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(360)
        self._build_ui()
        self._connect_signals()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(360, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(400, 560)

    def _set_elided_title(self, full_title: str) -> None:
        self.setToolTip(full_title)
        avail = max(260, self.width() - 32)
        elided = QFontMetrics(self.font()).elidedText(
            full_title, Qt.TextElideMode.ElideRight, avail
        )
        super().setTitle(elided)

    def setTitle(self, title: str) -> None:  # noqa: N802
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

        self._build_tab_cue_and_timing()
        self._build_tab_visual()
        self._build_tab_audio_and_cuts()
        self._build_tab_group()
        self.tab_widget.setTabVisible(3, False)

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

        self.lbl_layer_conflict = QLabel()
        self.lbl_layer_conflict.setWordWrap(True)
        self.lbl_layer_conflict.setStyleSheet(
            "background-color: #3b1d07; color: #fde047; border: 1px solid #d97706; "
            "border-radius: 4px; font-size: 10px; font-weight: bold; padding: 4px 6px;"
        )
        self.lbl_layer_conflict.setVisible(False)
        l2.addWidget(self.lbl_layer_conflict)

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

        timing_grid.addWidget(self._make_field_label("Pre-Delay:"), 0, 0)
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

        timing_grid.addWidget(self._make_field_label("Post-Delay:"), 0, 2)
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

        timing_grid.addWidget(self._make_field_label("Durata Img:"), 1, 0)
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
        l3.addLayout(io_row)
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
        self.slider_volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v}%"))
        self.btn_volume_reset.clicked.connect(lambda: self.slider_volume.setValue(100))
        self.btn_io_reset.clicked.connect(self.reset_in_out)

        field_widgets = (
            (self.spin_pos_x.valueChanged, "pos_x"),
            (self.spin_pos_y.valueChanged, "pos_y"),
            (self.spin_crop_l.valueChanged, "crop_l"),
            (self.spin_crop_r.valueChanged, "crop_r"),
            (self.spin_crop_t.valueChanged, "crop_t"),
            (self.spin_crop_b.valueChanged, "crop_b"),
            (self.spin_fade_in.valueChanged, "fade_in"),
            (self.spin_fade_out.valueChanged, "fade_out"),
            (self.spin_in.valueChanged, "in_point"),
            (self.spin_out.valueChanged, "out_point"),
            (self.spin_hold_time.valueChanged, "hold_time"),
            (self.spin_pre_delay.valueChanged, "pre_delay"),
            (self.spin_post_delay.valueChanged, "post_delay"),
            (self.slider_scale.valueChanged, "scale"),
            (self.slider_opacity.valueChanged, "opacity"),
            (self.slider_volume.valueChanged, "volume"),
            (self.spin_loop_count.valueChanged, "loop"),
            (self.combo_aspect.currentIndexChanged, "aspect_ratio"),
            (self.edit_cue_q.textEdited, "q_label"),
            (self.edit_cue_name.textEdited, "name"),
            (self.edit_cue_notes.textEdited, "notes"),
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
        for mk, btn in self._group_mode_buttons.items():
            btn.setChecked(mk == mode_key)
        for mk, label, desc, _, _ in _GROUP_MODE_SPECS:
            if mk == mode_key:
                self.lbl_group_mode_desc.setText(f"💡 {desc}")
                break

    def _on_remove_selected_child_clicked(self) -> None:
        item = self.list_group_children.currentItem()
        if item is not None:
            child_id = item.data(Qt.ItemDataRole.UserRole)
            if child_id is not None:
                self.remove_child_requested.emit(int(child_id))

    def load_group_children(self, children: list[Cue], group_cue: Optional[Cue] = None) -> None:
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

    def _on_layer_clicked(self, layer: int) -> None:
        self.set_layer_checked(layer)
        self.layer_selected.emit(layer)

    def _emit_change(self, field_key: str) -> None:
        if field_key in ("crop_l", "crop_r", "crop_t", "crop_b"):
            self._refresh_cached_norm_from_spins()
        if not self._updating:
            self.batch_field_edited.emit(field_key)
            self.value_changed.emit()

    def _on_loop_chk_toggled(self, checked: bool) -> None:
        self.combo_loop_mode.setEnabled(checked)
        self.spin_loop_count.setEnabled(checked)
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
        nx = round(max(-2.0, min(2.0, self.spin_pos_x.value() + dx)), 2)
        ny = round(max(-2.0, min(2.0, self.spin_pos_y.value() + dy)), 2)
        self.set_position_silent(nx, ny)
        self._emit_change("position")

    def reset_position(self) -> None:
        self.set_position_silent(0.0, 0.0)
        self._emit_change("position")

    def reset_scale(self) -> None:
        self.slider_scale.setValue(100)

    def reset_crop(self) -> None:
        self.set_crop_silent(0.0, 0.0, 0.0, 0.0)
        self._emit_change("crop_reset")

    def reset_in_out(self) -> None:
        self.in_out_reset_requested.emit()

    def set_layer_checked(self, layer: Optional[int]) -> None:
        for idx, btn in self._layer_buttons.items():
            btn.setChecked(layer == idx)

    def set_layer_conflict(self, conflict: Optional[Any] = None) -> None:
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

    def set_color_silent(self, color_hex: Optional[str]) -> None:
        clean = _sanitize_hex_color(color_hex) if color_hex is not None else "__MIXED__"
        for hv, btn in self._color_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(color_hex is not None and hv == clean)
            btn.blockSignals(False)
        for hv, btn in self._group_color_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(color_hex is not None and hv == clean)
            btn.blockSignals(False)

    def set_follow_mode_silent(self, mode: Optional[str], *, enabled: bool = True) -> None:
        for m, btn in self._follow_buttons.items():
            btn.blockSignals(True)
            btn.setEnabled(enabled)
            btn.setChecked(enabled and (m == mode))
            btn.blockSignals(False)

    def set_position_silent(self, pos_x: float, pos_y: float) -> None:
        for w, val in ((self.spin_pos_x, pos_x), (self.spin_pos_y, pos_y)):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)

    def set_crop_silent(self, crop_l: float, crop_r: float, crop_t: float, crop_b: float) -> None:
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
        self.spin_in.blockSignals(True)
        self.spin_in.setValue(new_in)
        self.spin_in.blockSignals(False)

    def set_out_silent(self, new_out: float) -> None:
        self.spin_out.blockSignals(True)
        self.spin_out.setValue(new_out)
        self.spin_out.blockSignals(False)

    def set_fades_silent(self, fade_in: Optional[float] = None, fade_out: Optional[float] = None) -> None:
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

    def set_enabled_for_cue(self, enabled: bool, media_type: Optional[MediaType] = None,
                            multi_mode: bool = False) -> None:
        is_group = (media_type == MediaType.GROUP)

        # Tab visibility: when GROUP, show tab 3 (Gruppo), hide tabs 0, 1, 2
        # when NOT GROUP, show tabs 0, 1, 2, hide tab 3
        if is_group:
            self.tab_widget.setTabVisible(0, False)
            self.tab_widget.setTabVisible(1, False)
            self.tab_widget.setTabVisible(2, False)
            self.tab_widget.setTabVisible(3, True)
            self.tab_widget.setCurrentIndex(3)
        else:
            self.tab_widget.setTabVisible(0, True)
            self.tab_widget.setTabVisible(1, True)
            self.tab_widget.setTabVisible(2, True)
            self.tab_widget.setTabVisible(3, False)
            if self.tab_widget.currentIndex() == 3:
                self.tab_widget.setCurrentIndex(0)

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
            self.btn_crop_reset, self.spin_fade_in, self.spin_fade_out,
            self.combo_aspect, self.slider_volume, self.btn_volume_reset,
            self.loop_card, self.chk_loop, self.combo_loop_mode, self.spin_loop_count,
            self.spin_in, self.spin_out, self.btn_io_reset, self.spin_hold_time,
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
            for w in all_media_controls:
                w.setEnabled(False)
            return

        if is_group:
            for w in all_media_controls:
                w.setEnabled(False)
            return

        self.spin_fade_in.setEnabled(True)
        self.spin_fade_out.setEnabled(True)
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
        )
        time_controls = (
            self.slider_volume, self.btn_volume_reset,
            self.loop_card, self.chk_loop, self.spin_in, self.spin_out, self.btn_io_reset,
            self.card_loudness, self.btn_scan_loudness, self.chk_normalize_cue, self.btn_optimize_dynamics,
        )

        is_visual = media_type in (MediaType.VIDEO, MediaType.IMAGE)
        is_timed = media_type in (MediaType.VIDEO, MediaType.AUDIO)

        for w in visual_controls:
            w.setEnabled(is_visual)
        for w in time_controls:
            w.setEnabled(is_timed)
        self.card_loudness.setVisible(is_timed)

        self.spin_hold_time.setEnabled(media_type == MediaType.IMAGE)
        self.combo_loop_mode.setEnabled(is_timed and self.chk_loop.isChecked())
        self.spin_loop_count.setEnabled(is_timed and self.chk_loop.isChecked())

        if media_type == MediaType.IMAGE:
            self.lbl_hold_hint.setText("0 s = Infinita in Live")
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
        self.spin_hold_time.setValue(cue.hold_time)
        self.spin_pre_delay.setValue(getattr(cue, "pre_delay", 0.0))
        self.spin_post_delay.setValue(getattr(cue, "post_delay", 0.0))
        self.slider_volume.setValue(int(cue.volume * 100))

        self.chk_loop.setChecked(cue.loop)
        self.combo_loop_mode.setEnabled(cue.loop)
        self.spin_loop_count.setEnabled(cue.loop)

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

    def load_cue(self, cue: Optional[Cue], row: int = -1) -> None:
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
                self.set_layer_checked(cue.layer)
                self.set_color_silent(getattr(cue, "color", ""))
                self.set_follow_mode_silent(cue.follow_mode, enabled=True)
                self._populate_media_fields(cue)
        finally:
            self._updating = False

    def load_selection(self, cues: list[Cue], anchor_cue: Optional[Cue] = None,
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
        colors = {getattr(c, "color", "") for c in cues}
        common_color: Optional[str] = next(iter(colors)) if len(colors) == 1 else None
        modes = {c.follow_mode for c in cues}
        common_mode: Optional[str] = next(iter(modes)) if len(modes) == 1 else None

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
            self.set_color_silent(common_color)
            self.set_follow_mode_silent(common_mode, enabled=True)
            self._populate_media_fields(lead)
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

        cue.q_label = self.edit_cue_q.text().strip()
        new_name = self.edit_cue_name.text().strip()
        if new_name:
            cue.name = new_name
        cue.notes = self.edit_cue_notes.text().strip()

        cue.position_x = round(self.spin_pos_x.value(), 3)
        cue.position_y = round(self.spin_pos_y.value(), 3)
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

    def _apply_loop_to_cue(self, cue: Cue) -> None:
        cue.loop = self.chk_loop.isChecked()
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
            if field_key == "pos_x":
                cue.position_x = round(self.spin_pos_x.value(), 3)
            elif field_key == "pos_y":
                cue.position_y = round(self.spin_pos_y.value(), 3)
            elif field_key == "position":
                cue.position_x = round(self.spin_pos_x.value(), 3)
                cue.position_y = round(self.spin_pos_y.value(), 3)
            elif field_key == "scale":
                cue.scale = round(self.slider_scale.value() / 100.0, 2)
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
