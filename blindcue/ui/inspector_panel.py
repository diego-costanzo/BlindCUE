"""Right-column Cue Inspector panel (metadata, compositing layer, transform, %/px crop, fades, audio/loop)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from models.cue import Cue, MediaType
from ui.cue_table import format_cue_ref
from ui.spinboxes import InPointSpinBox, OutPointSpinBox, SmartDoubleSpinBox
from ui.theme import CLR_ACCENT, NUDGE_BTN_STYLE

# Preset index <-> repetition count mapping (0 = infinite loop)
_LOOP_PRESET_COUNTS = (0, 2, 3, 4, 5, 10)
_COUNT_TO_PRESET_IDX = {count: idx for idx, count in enumerate(_LOOP_PRESET_COUNTS)}
_LOOP_CUSTOM_IDX = len(_LOOP_PRESET_COUNTS)

# (UI label, canonical model value)
_ASPECT_OPTIONS: list[tuple[str, Optional[str]]] = [
    ("Native (Automatico)", None),
    ("16:9 (Widescreen)", "16:9"),
    ("4:3 (Standard)", "4:3"),
    ("21:9 (Ultrawide)", "21:9"),
    ("1:1 (Quadrato)", "1:1"),
]

# Layer button visual definitions: (layer_num, label, tooltip, checked_bg, checked_border)
_LAYER_BTN_SPECS = (
    (1, "L1: Sfondo", "Layer 1 (Default): Livello di sfondo o base scena", "#065f46", "#10b981"),
    (2, "L2: Principale", "Layer 2: Livello multimediale intermedio (sopra L1)", "#075985", "#38bdf8"),
    (3, "L3: Overlay", "Layer 3: Livello superiore in primo piano (grafica, loghi, sovraimpressioni)", "#78350f", "#f59e0b"),
)


def _make_layer_btn_style(checked_bg: str, checked_border: str) -> str:
    """Return unmistakable tactile button styling with hover & active color states."""
    return f"""
        QPushButton {{
            background-color: #1c2636;
            color: #cbd5e1;
            border: 1px solid #3c4f6b;
            border-bottom: 2px solid #2b3a50;
            border-radius: 5px;
            padding: 4px 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        QPushButton:hover:!checked {{
            background-color: #26354d;
            border: 1px solid {checked_border};
            border-bottom: 2px solid {checked_border};
            color: #ffffff;
        }}
        QPushButton:pressed {{
            background-color: #131c28;
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


_UNIT_PILL_STYLE = f"""
    QPushButton {{
        background-color: #182230;
        color: #94a3b8;
        border: 1px solid #2b3b52;
        border-radius: 3px;
        padding: 1px 8px;
        font-size: 10px;
        font-weight: bold;
        min-width: 28px;
        height: 20px;
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
    """Scrollable Cue Properties Inspector with fixed width stability, %/px crop, and batch edit."""

    value_changed = Signal()
    batch_field_edited = Signal(str)
    layer_selected = Signal(int)
    in_out_reset_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("ISPETTORE CUE (Nessuna cue selezionata)", parent)
        self._updating: bool = False
        self._multi_mode: bool = False
        self._crop_unit: str = "pct"   # "pct" (%) or "px" (pixels)
        self._crop_ref_w: int = 1920
        self._crop_ref_h: int = 1080
        self._norm_crop: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._layer_buttons: dict[int, QPushButton] = {}

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(340)
        self._build_ui()
        self._connect_signals()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Lock minimum width so long cue titles never stretch or shift the splitter."""
        return QSize(340, 240)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(370, 560)

    def _set_elided_title(self, full_title: str) -> None:
        self.setToolTip(full_title)
        avail = max(240, self.width() - 32)
        elided = QFontMetrics(self.font()).elidedText(
            full_title, Qt.TextElideMode.ElideRight, avail
        )
        super().setTitle(elided)

    def setTitle(self, title: str) -> None:  # noqa: N802
        self._set_elided_title(title)

    @staticmethod
    def _make_section_header(title: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 4)
        lay.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #383838; max-height: 1px; border: none;")
        lay.addWidget(lbl)
        lay.addWidget(line)
        return w

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 8, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 6, 4)
        layout.setSpacing(6)

        lbl_hint = QLabel("Proprietà del media selezionato prima o durante il Live")
        lbl_hint.setStyleSheet("color: #777; font-size: 10px; margin-bottom: 2px;")
        layout.addWidget(lbl_hint)

        self.lbl_multi_banner = QLabel()
        self.lbl_multi_banner.setWordWrap(True)
        self.lbl_multi_banner.setMinimumWidth(0)
        self.lbl_multi_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lbl_multi_banner.setVisible(False)
        layout.addWidget(self.lbl_multi_banner)

        # ── 1. Dati Cue & Note di Regia ──
        layout.addWidget(self._make_section_header("DATI CUE • NOTE DI REGIA"))

        row_q = QHBoxLayout()
        row_q.addWidget(QLabel("Q (Copione):"))
        self.edit_cue_q = QLineEdit()
        self.edit_cue_q.setMinimumWidth(60)
        self.edit_cue_q.setPlaceholderText("Richiamo copione (es. Q-2, Q-9a, Sc.1...)")
        self.edit_cue_q.setToolTip("Numero o sigla Q del copione: segue la cue anche se spostata in scaletta")
        row_q.addWidget(self.edit_cue_q)
        layout.addLayout(row_q)

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Nome:"))
        self.edit_cue_name = QLineEdit()
        self.edit_cue_name.setMinimumWidth(60)
        self.edit_cue_name.setPlaceholderText("Nome della Cue...")
        row_name.addWidget(self.edit_cue_name)
        layout.addLayout(row_name)

        row_notes = QHBoxLayout()
        row_notes.addWidget(QLabel("Note:"))
        self.edit_cue_notes = QLineEdit()
        self.edit_cue_notes.setMinimumWidth(60)
        self.edit_cue_notes.setPlaceholderText("Appunti di regia (es. attacco battuta, sfumata...)")
        row_notes.addWidget(self.edit_cue_notes)
        layout.addLayout(row_notes)

        # ── 2. Layer di Uscita ──
        layout.addWidget(self._make_section_header("LAYER DI USCITA (COMPOSITING)"))

        layer_layout = QHBoxLayout()
        layer_layout.setContentsMargins(0, 2, 0, 2)
        layer_layout.setSpacing(5)
        for layer_idx, label, tooltip, bg, border in _LAYER_BTN_SPECS:
            btn = QPushButton(label)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_make_layer_btn_style(bg, border))
            layer_layout.addWidget(btn)
            self._layer_buttons[layer_idx] = btn

        self.btn_layer1 = self._layer_buttons[1]
        self.btn_layer2 = self._layer_buttons[2]
        self.btn_layer3 = self._layer_buttons[3]
        layout.addLayout(layer_layout)

        # ── 3. Posizionamento, Zoom & Trasparenza ──
        layout.addWidget(self._make_section_header("POSIZIONAMENTO • ZOOM • TRASPARENZA"))

        pos_row = QHBoxLayout()
        pos_row.setSpacing(6)
        pos_row.addWidget(QLabel("Pos X:"))
        self.spin_pos_x = SmartDoubleSpinBox()
        self.spin_pos_x.setRange(-2.0, 2.0)
        self.spin_pos_x.setSingleStep(0.01)
        self.spin_pos_x.setDecimals(2)
        self.spin_pos_x.setToolTip(
            "Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx). Puoi anche trascinare col mouse sull'anteprima!"
        )
        pos_row.addWidget(self.spin_pos_x)

        pos_row.addWidget(QLabel("Pos Y:"))
        self.spin_pos_y = SmartDoubleSpinBox()
        self.spin_pos_y.setRange(-2.0, 2.0)
        self.spin_pos_y.setSingleStep(0.01)
        self.spin_pos_y.setDecimals(2)
        self.spin_pos_y.setToolTip(
            "Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso). Puoi anche trascinare col mouse sull'anteprima!"
        )
        pos_row.addWidget(self.spin_pos_y)
        layout.addLayout(pos_row)

        nudge_row = QHBoxLayout()
        self.btn_nudge_left = self._make_nudge_btn("◀", "Sposta a sinistra (-0.01)")
        self.btn_nudge_up = self._make_nudge_btn("▲", "Sposta in alto (-0.01)")
        self.btn_nudge_down = self._make_nudge_btn("▼", "Sposta in basso (+0.01)")
        self.btn_nudge_right = self._make_nudge_btn("▶", "Sposta a destra (+0.01)")
        self.btn_pos_center = self._make_nudge_btn("⌖ Centro", "Ripristina posizione al centro (0.00, 0.00)")
        for btn in (
            self.btn_nudge_left, self.btn_nudge_up, self.btn_nudge_down,
            self.btn_nudge_right, self.btn_pos_center,
        ):
            nudge_row.addWidget(btn)
        layout.addLayout(nudge_row)

        scale_row = QHBoxLayout()
        lbl_sc_title = QLabel("Scala / Zoom:")
        lbl_sc_title.setFixedWidth(78)
        scale_row.addWidget(lbl_sc_title)
        self.slider_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_scale.setRange(10, 500)
        self.slider_scale.setValue(100)
        self.slider_scale.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_scale = QLabel("1.0x")
        self.lbl_scale.setFixedWidth(36)
        self.lbl_scale.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.btn_scale_reset = self._make_reset_icon_btn("Ripristina scala a 1.0x")
        scale_row.addWidget(self.slider_scale)
        scale_row.addWidget(self.lbl_scale)
        scale_row.addWidget(self.btn_scale_reset)
        layout.addLayout(scale_row)

        op_row = QHBoxLayout()
        lbl_op_title = QLabel("Opacità:")
        lbl_op_title.setFixedWidth(78)
        op_row.addWidget(lbl_op_title)
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_opacity = QLabel("100%")
        self.lbl_opacity.setFixedWidth(36)
        self.lbl_opacity.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.btn_opacity_reset = self._make_reset_icon_btn("Ripristina opacità al 100% (piena visibilità)")
        op_row.addWidget(self.slider_opacity)
        op_row.addWidget(self.lbl_opacity)
        op_row.addWidget(self.btn_opacity_reset)
        layout.addLayout(op_row)

        # ── 4. Ritaglio (Crop % o px) ──
        layout.addWidget(self._make_section_header("RITAGLIO (CROP)"))

        crop_unit_row = QHBoxLayout()
        crop_unit_row.setSpacing(4)
        lbl_unit = QLabel("Unità:")
        lbl_unit.setStyleSheet("color: #94a3b8; font-size: 10px;")
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
        self.lbl_crop_ref.setStyleSheet("color: #64748b; font-size: 10px;")
        self.lbl_crop_ref.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        crop_unit_row.addWidget(lbl_unit)
        crop_unit_row.addWidget(self.btn_crop_pct)
        crop_unit_row.addWidget(self.btn_crop_px)
        crop_unit_row.addStretch()
        crop_unit_row.addWidget(self.lbl_crop_ref)
        layout.addLayout(crop_unit_row)

        crop_row1 = QHBoxLayout()
        crop_row1.setSpacing(6)
        crop_row1.addWidget(QLabel("Sinistra:"))
        self.spin_crop_l = self._make_crop_spin("Ritaglio bordo sinistro")
        crop_row1.addWidget(self.spin_crop_l)
        crop_row1.addWidget(QLabel("Destra:"))
        self.spin_crop_r = self._make_crop_spin("Ritaglio bordo destro")
        crop_row1.addWidget(self.spin_crop_r)
        layout.addLayout(crop_row1)

        crop_row2 = QHBoxLayout()
        crop_row2.setSpacing(6)
        crop_row2.addWidget(QLabel("Alto:"))
        self.spin_crop_t = self._make_crop_spin("Ritaglio bordo superiore")
        crop_row2.addWidget(self.spin_crop_t)
        crop_row2.addWidget(QLabel("Basso:"))
        self.spin_crop_b = self._make_crop_spin("Ritaglio bordo inferiore")
        crop_row2.addWidget(self.spin_crop_b)
        layout.addLayout(crop_row2)

        crop_btn_row = QHBoxLayout()
        self.btn_crop_reset = self._make_nudge_btn(
            "⟲ Reset Ritaglio", "Rimuove il ritaglio e mostra il fotogramma intero"
        )
        crop_btn_row.addStretch()
        crop_btn_row.addWidget(self.btn_crop_reset)
        layout.addLayout(crop_btn_row)

        # ── 5. Transizioni & Aspect Ratio ──
        layout.addWidget(self._make_section_header("TRANSIZIONI • ASPECT RATIO"))

        fade_row = QHBoxLayout()
        fade_row.setSpacing(6)
        fade_row.addWidget(QLabel("Fade In:"))
        self.spin_fade_in = SmartDoubleSpinBox()
        self.spin_fade_in.setRange(0.0, 30.0)
        self.spin_fade_in.setDecimals(1)
        self.spin_fade_in.setSingleStep(0.2)
        self.spin_fade_in.setSuffix(" s")
        fade_row.addWidget(self.spin_fade_in)

        fade_row.addWidget(QLabel("Fade Out:"))
        self.spin_fade_out = SmartDoubleSpinBox()
        self.spin_fade_out.setRange(0.0, 30.0)
        self.spin_fade_out.setDecimals(1)
        self.spin_fade_out.setSingleStep(0.2)
        self.spin_fade_out.setSuffix(" s")
        fade_row.addWidget(self.spin_fade_out)
        layout.addLayout(fade_row)

        hold_row = QHBoxLayout()
        hold_row.addWidget(QLabel("Durata Img:"))
        self.spin_hold_time = SmartDoubleSpinBox()
        self.spin_hold_time.setRange(0.0, 99999.0)
        self.spin_hold_time.setDecimals(1)
        self.spin_hold_time.setSingleStep(0.5)
        self.spin_hold_time.setSuffix(" s")
        self.spin_hold_time.setSpecialValueText("0 s (Infinita)")
        self.spin_hold_time.setToolTip(
            "Tempo di permanenza in Live dell'immagine prima della rimozione automatica. 0 = infinita."
        )
        hold_row.addWidget(self.spin_hold_time)
        layout.addLayout(hold_row)

        delay_row = QHBoxLayout()
        delay_row.setSpacing(6)
        delay_row.addWidget(QLabel("Pre-Delay:"))
        self.spin_pre_delay = SmartDoubleSpinBox()
        self.spin_pre_delay.setRange(0.0, 3600.0)
        self.spin_pre_delay.setDecimals(1)
        self.spin_pre_delay.setSingleStep(0.5)
        self.spin_pre_delay.setSuffix(" s")
        self.spin_pre_delay.setToolTip(
            "Ritardo di avvio dopo il GO prima che il file parta (utile per incastrarlo con altri layer)"
        )
        delay_row.addWidget(self.spin_pre_delay)

        delay_row.addWidget(QLabel("Post-Delay:"))
        self.spin_post_delay = SmartDoubleSpinBox()
        self.spin_post_delay.setRange(0.0, 3600.0)
        self.spin_post_delay.setDecimals(1)
        self.spin_post_delay.setSingleStep(0.5)
        self.spin_post_delay.setSuffix(" s")
        self.spin_post_delay.setToolTip(
            "Attesa dopo la fine del file prima di uscire e avviare l'eventuale Auto-GO successivo"
        )
        delay_row.addWidget(self.spin_post_delay)
        layout.addLayout(delay_row)

        ar_row = QHBoxLayout()
        ar_row.addWidget(QLabel("Formato:"))
        self.combo_aspect = QComboBox()
        self.combo_aspect.setMinimumWidth(80)
        self.combo_aspect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_aspect.setToolTip("Forza le proporzioni del riquadro in Anteprima e Live (es. 16:9, 4:3, 1:1)")
        for label, value in _ASPECT_OPTIONS:
            self.combo_aspect.addItem(label, value)
        ar_row.addWidget(self.combo_aspect, 1)
        layout.addLayout(ar_row)

        # ── 6. Audio & Riproduzione ──
        layout.addWidget(self._make_section_header("AUDIO • RIPRODUZIONE"))

        vol_row = QHBoxLayout()
        lbl_vol_title = QLabel("Volume:")
        lbl_vol_title.setFixedWidth(78)
        vol_row.addWidget(lbl_vol_title)
        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(100)
        self.slider_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_volume = QLabel("100%")
        self.lbl_volume.setFixedWidth(36)
        self.lbl_volume.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.btn_volume_reset = self._make_reset_icon_btn("Ripristina volume al 100%")
        vol_row.addWidget(self.slider_volume)
        vol_row.addWidget(self.lbl_volume)
        vol_row.addWidget(self.btn_volume_reset)
        layout.addLayout(vol_row)

        self.loop_card = QFrame()
        self.loop_card.setObjectName("loopCard")
        self.loop_card.setStyleSheet("""
            QFrame#loopCard {
                background-color: #101722;
                border: 1px solid #1e2c3d;
                border-radius: 6px;
                padding: 6px 8px;
                margin-top: 4px;
                margin-bottom: 4px;
            }
        """)
        loop_card_layout = QVBoxLayout(self.loop_card)
        loop_card_layout.setContentsMargins(8, 6, 8, 6)
        loop_card_layout.setSpacing(6)

        loop_top_row = QHBoxLayout()
        self.chk_loop = QCheckBox("🔁  RIPETI IN LOOP")
        self.chk_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_loop.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                font-size: 11px;
                color: #10b981;
                spacing: 8px;
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
        lbl_mode = QLabel("Modalità:")
        lbl_mode.setStyleSheet("color: #94a3b8; font-size: 11px;")
        loop_options_row.addWidget(lbl_mode)

        self.combo_loop_mode = QComboBox()
        self.combo_loop_mode.setMinimumWidth(60)
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
        self.spin_loop_count.setFixedWidth(82)
        self.spin_loop_count.setVisible(False)
        loop_options_row.addWidget(self.spin_loop_count)

        loop_card_layout.addLayout(loop_options_row)
        layout.addWidget(self.loop_card)

        io_row = QHBoxLayout()
        io_row.setSpacing(6)
        io_row.addWidget(QLabel("IN:"))
        self.spin_in = InPointSpinBox()
        io_row.addWidget(self.spin_in)
        io_row.addWidget(QLabel("OUT:"))
        self.spin_out = OutPointSpinBox()
        io_row.addWidget(self.spin_out)
        self.btn_io_reset = self._make_reset_icon_btn("Ripristina IN a 0.00s e OUT a Fine")
        io_row.addWidget(self.btn_io_reset)
        layout.addLayout(io_row)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

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
        )
        for sig, field_key in field_widgets:
            sig.connect(lambda *_args, key=field_key: self._emit_change(key))

        self.chk_loop.toggled.connect(self._on_loop_chk_toggled)
        self.combo_loop_mode.currentIndexChanged.connect(self._on_loop_mode_changed)

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
        """Emit shared reset signal to restore IN=0.00s and OUT=Fine cleanly."""
        self.in_out_reset_requested.emit()

    def set_layer_checked(self, layer: Optional[int]) -> None:
        """Highlight the button matching *layer*, or uncheck all when *layer* is None."""
        for idx, btn in self._layer_buttons.items():
            btn.setChecked(layer == idx)

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

    def sync_header_and_text(self, row: int, cue: Cue) -> None:
        ref = format_cue_ref(row, cue)
        self._updating = True
        try:
            self.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
            if self.edit_cue_q.text() != cue.q_label:
                self.edit_cue_q.setText(cue.q_label)
            if self.edit_cue_name.text() != cue.name:
                self.edit_cue_name.setText(cue.name)
        finally:
            self._updating = False

    def set_enabled_for_cue(self, enabled: bool, media_type: Optional[MediaType] = None,
                            multi_mode: bool = False) -> None:
        for btn in self._layer_buttons.values():
            btn.setEnabled(enabled)

        identity_enabled = enabled and not multi_mode
        self.edit_cue_q.setEnabled(identity_enabled)
        self.edit_cue_name.setEnabled(identity_enabled)
        self.edit_cue_notes.setEnabled(identity_enabled)

        all_media_controls = (
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
        )

        if not enabled or media_type is None:
            self.set_layer_checked(None)
            self.edit_cue_q.clear()
            self.edit_cue_name.clear()
            self.edit_cue_notes.clear()
            for w in all_media_controls:
                w.setEnabled(False)
            return

        self.spin_fade_in.setEnabled(True)
        self.spin_fade_out.setEnabled(True)
        self.spin_pre_delay.setEnabled(True)
        self.spin_post_delay.setEnabled(True)

        visual_controls = (
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
        )

        is_visual = media_type in (MediaType.VIDEO, MediaType.IMAGE)
        is_timed = media_type in (MediaType.VIDEO, MediaType.AUDIO)

        for w in visual_controls:
            w.setEnabled(is_visual)
        for w in time_controls:
            w.setEnabled(is_timed)

        self.spin_hold_time.setEnabled(media_type == MediaType.IMAGE)
        self.combo_loop_mode.setEnabled(is_timed and self.chk_loop.isChecked())
        self.spin_loop_count.setEnabled(is_timed and self.chk_loop.isChecked())

    def _populate_media_fields(self, cue: Cue) -> None:
        """Populate transform, fade, loop, audio, and timing widgets from *cue*."""
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

    def load_cue(self, cue: Optional[Cue], row: int = -1) -> None:
        """Load a single cue into the inspector, or disable when *cue* is None."""
        self._multi_mode = False
        self.lbl_multi_banner.setVisible(False)

        if cue is None:
            self.setTitle("ISPETTORE CUE (Nessuna cue selezionata)")
            self.set_enabled_for_cue(False)
            return

        self._updating = True
        try:
            ref = format_cue_ref(row, cue)
            self.setTitle(f"ISPETTORE CUE — {ref} [{cue.media_type.value}] '{cue.name}'")
            self.set_enabled_for_cue(True, cue.media_type, multi_mode=False)

            self.edit_cue_q.setText(cue.q_label)
            self.edit_cue_name.setText(cue.name)
            self.edit_cue_notes.setText(cue.notes)
            self.set_layer_checked(cue.layer)
            self._populate_media_fields(cue)
        finally:
            self._updating = False

    def load_selection(self, cues: list[Cue], anchor_cue: Optional[Cue] = None,
                       anchor_row: int = -1) -> None:
        """Load 0, 1, or N selected cues with same-type batch editing support."""
        if not cues:
            self.load_cue(None)
            return
        if len(cues) == 1:
            self.load_cue(cues[0], anchor_row)
            return

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
            self._populate_media_fields(lead)
        finally:
            self._updating = False

    def apply_to_cue(self, cue: Cue) -> None:
        """Write all single-cue inspector field values onto *cue*."""
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

        self._apply_loop_to_cue(cue)

        cue.in_point = self.spin_in.value()
        out_val = self.spin_out.value()
        if out_val > 0 and out_val <= cue.in_point:
            out_val = round(cue.in_point + 0.05, 2)
            self.set_out_silent(out_val)
        cue.out_point = out_val if out_val > 0 else None

        ar_data = self.combo_aspect.currentData()
        cue.aspect_ratio = ar_data if ar_data is not None else None

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
