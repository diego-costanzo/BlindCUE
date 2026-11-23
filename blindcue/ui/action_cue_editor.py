"""Inspector page for ACTION cues (stop, fade, release loop, level, opacity, notes).

The editor works on a plain ``action_spec`` dict (see
``models.cue.sanitize_action_spec``): ``load()`` fills the controls without
emitting, ``spec()`` reads them back, ``changed`` fires on every user edit.
"""

from __future__ import annotations

from collections.abc import Callable

from engine.action_cues import describe_action
from engine.envelope import FADE_CURVE_LABELS
from models.cue import (
    ACTION_CHECKLIST,
    ACTION_FADE,
    ACTION_LEVEL,
    ACTION_NOTE,
    ACTION_OPACITY,
    ACTION_RELEASE,
    ACTION_STOP,
    ACTION_TARGET_ALL,
    ACTION_TARGET_CUES,
    ACTION_TARGET_LAYER,
    Cue,
    MediaType,
    action_needs_target,
    sanitize_action_spec,
)
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.cue_table import format_cue_ref
from ui.spinboxes import SmartDoubleSpinBox

_KIND_LABELS = (
    (ACTION_FADE, "🔉 Dissolvi e ferma"),
    (ACTION_STOP, "⏹ Ferma subito"),
    (ACTION_RELEASE, "🔁 Rilascia loop"),
    (ACTION_LEVEL, "🎚 Cambio livello"),
    (ACTION_OPACITY, "🌓 Opacità layer"),
    (ACTION_NOTE, "📝 Nota per la regia"),
    (ACTION_CHECKLIST, "☑ Checklist prima dello spettacolo"),
)
_KIND_HELP = {
    ACTION_FADE: "Abbassa audio e immagine delle cue scelte nel tempo indicato, poi le ferma. "
                 "Il loro Post-Delay e Auto-GO non partono.",
    ACTION_STOP: "Ferma subito le cue scelte, anche quelle in attesa del Pre-Delay.",
    ACTION_RELEASE: "La cue in loop finisce il giro in corso e poi prosegue: passa alla sezione "
                    "successiva o termina normalmente (con Post-Delay e Auto-GO).",
    ACTION_LEVEL: "Cambia il volume di ciò che suona, senza fermarlo. Assoluto: come se il "
                  "Volume della cue fosse quello indicato. Relativo: più o meno dB rispetto ad ora.",
    ACTION_OPACITY: "Rende più o meno trasparente tutto il layer (immagini e video). "
                    "La cue successiva sullo stesso layer riparte piena.",
    ACTION_NOTE: "Mostra il testo in cima alla finestra di regia (non sul proiettore). "
                 "Non blocca il GO; sparisce al GO successivo o con ✕.",
    ACTION_CHECKLIST: "Lista da spuntare prima dello spettacolo: compare con il GO e anche "
                      "entrando in LIVE finché non è tutta spuntata. Le spunte non vengono salvate.",
}
_TARGET_LABELS = (
    (ACTION_TARGET_ALL, "Tutto ciò che è in onda"),
    (ACTION_TARGET_LAYER, "Un layer"),
    (ACTION_TARGET_CUES, "Cue scelte"),
)
_NOTE_COLOURS = (
    ("#f59e0b", "Ambra"),
    ("#ef4444", "Rosso — attenzione"),
    ("#10b981", "Verde"),
    ("#3b82f6", "Blu"),
    ("#a855f7", "Viola"),
    ("#e5e7eb", "Grigio chiaro"),
)


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; background: transparent;")
    return lbl


class ActionCueEditor(QWidget):
    """Controls for one action cue."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the (empty) editor."""
        super().__init__(parent)
        self._loading = False
        self._cue_id = -1
        self._catalog: Callable[[], list[Cue]] = list
        self._note_colour = "#f59e0b"
        self._colour_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 7, 6, 7)
        lay.setSpacing(7)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)

        self.combo_kind = QComboBox()
        for kind, label in _KIND_LABELS:
            self.combo_kind.addItem(label, kind)
        self.combo_kind.setAccessibleName("Tipo di azione")
        form.addRow(_label("Azione:"), self.combo_kind)

        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setStyleSheet("color: #7c8fa6; font-size: 10px; background: transparent;")
        form.addRow(self.lbl_help)

        self.combo_target = QComboBox()
        for target, label in _TARGET_LABELS:
            self.combo_target.addItem(label, target)
        self.combo_target.setAccessibleName("Su cosa agisce")
        self.lbl_target = _label("Su cosa:")
        form.addRow(self.lbl_target, self.combo_target)

        self.row_layer = QWidget()
        layer_lay = QHBoxLayout(self.row_layer)
        layer_lay.setContentsMargins(0, 0, 0, 0)
        layer_lay.setSpacing(4)
        self.combo_layer = QComboBox()
        for n in (1, 2, 3):
            self.combo_layer.addItem(f"Layer {n}", n)
        self.combo_output = QComboBox()
        self.combo_output.addItem("Uscita A", "A")
        self.combo_output.addItem("Uscita B", "B")
        self.combo_output.setToolTip("Conta solo con due proiettori indipendenti")
        layer_lay.addWidget(self.combo_layer, 1)
        layer_lay.addWidget(self.combo_output, 1)
        self.lbl_layer = _label("Layer:")
        form.addRow(self.lbl_layer, self.row_layer)

        self.list_cues = QListWidget()
        self.list_cues.setMinimumHeight(90)
        # Space ticks the focused target and Delete does nothing here: without
        # this they reach the window shortcuts (GO, delete the whole cue).
        self.list_cues.installEventFilter(self)
        self.list_cues.setAccessibleName("Cue su cui agisce l'azione")
        self.list_cues.setToolTip("Spunta le cue su cui agisce l'azione (un gruppo = tutte le sue cue)")
        self.lbl_cues = _label("Cue:")
        form.addRow(self.lbl_cues, self.list_cues)

        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Assoluto (%)", "absolute")
        self.combo_mode.addItem("Relativo (dB)", "relative")
        self.lbl_mode = _label("Modo:")
        form.addRow(self.lbl_mode, self.combo_mode)

        self.spin_level = SmartDoubleSpinBox()
        self.spin_level.setRange(0.0, 100.0)
        self.spin_level.setDecimals(0)
        self.spin_level.setSingleStep(5.0)
        self.spin_level.setSuffix(" %")
        self.lbl_level = _label("Livello:")
        form.addRow(self.lbl_level, self.spin_level)

        self.spin_db = SmartDoubleSpinBox()
        self.spin_db.setRange(-60.0, 20.0)
        self.spin_db.setDecimals(1)
        self.spin_db.setSingleStep(1.0)
        self.spin_db.setSuffix(" dB")
        self.lbl_db = _label("Variazione:")
        form.addRow(self.lbl_db, self.spin_db)

        self.spin_duration = SmartDoubleSpinBox()
        self.spin_duration.setRange(0.0, 600.0)
        self.spin_duration.setDecimals(1)
        self.spin_duration.setSingleStep(0.5)
        self.spin_duration.setSuffix(" s")
        self.spin_duration.setToolTip("0 = subito")
        self.lbl_duration = _label("Durata:")
        form.addRow(self.lbl_duration, self.spin_duration)

        self.combo_curve = QComboBox()
        for key in ("linear", "log", "scurve"):
            self.combo_curve.addItem(FADE_CURVE_LABELS[key], key)
        self.lbl_curve = _label("Curva:")
        form.addRow(self.lbl_curve, self.combo_curve)

        self.edit_text = QPlainTextEdit()
        self.edit_text.setPlaceholderText("Es. Aspetta l'ingresso di Anna, poi GO")
        self.edit_text.setMaximumHeight(80)
        self.edit_text.setAccessibleName("Testo della nota")
        self.lbl_text = _label("Testo:")
        form.addRow(self.lbl_text, self.edit_text)

        self.edit_items = QPlainTextEdit()
        self.edit_items.setPlaceholderText("Una voce per riga")
        self.edit_items.setMaximumHeight(110)
        self.edit_items.setAccessibleName("Voci della checklist, una per riga")
        self.lbl_items = _label("Voci:")
        form.addRow(self.lbl_items, self.edit_items)

        self.row_colour = QWidget()
        colour_lay = QHBoxLayout(self.row_colour)
        colour_lay.setContentsMargins(0, 0, 0, 0)
        colour_lay.setSpacing(4)
        for hex_val, tip in _NOTE_COLOURS:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(24, 20)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {hex_val}; border: 1px solid #334155; border-radius: 3px; }}"
                " QPushButton:checked { border: 2px solid #ffffff; }"
            )
            btn.clicked.connect(lambda _=False, hv=hex_val: self._on_colour(hv))
            colour_lay.addWidget(btn)
            self._colour_buttons[hex_val] = btn
        colour_lay.addStretch()
        self.lbl_colour = _label("Colore:")
        form.addRow(self.lbl_colour, self.row_colour)

        lay.addLayout(form)

        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setMinimumWidth(0)
        self.lbl_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lbl_summary.setStyleSheet(
            "background-color: #0c1f33; color: #7dd3fc; border: 1px solid #1e3a5f; "
            "border-radius: 5px; font-size: 11px; padding: 6px 10px;"
        )
        lay.addWidget(self.lbl_summary)
        lay.addStretch()

        for combo in (self.combo_kind, self.combo_target, self.combo_layer, self.combo_output,
                      self.combo_mode, self.combo_curve):
            combo.currentIndexChanged.connect(self._on_edit)
        for spin in (self.spin_level, self.spin_db, self.spin_duration):
            spin.valueChanged.connect(self._on_edit)
        self.edit_text.textChanged.connect(self._on_edit)
        self.edit_items.textChanged.connect(self._on_edit)
        self.list_cues.itemChanged.connect(self._on_edit)

    # ── Public API ────────────────────────────────────────────────────
    def cue_id(self) -> int:
        """The cue whose action is loaded (-1 = none)."""
        return self._cue_id

    def set_catalog_provider(self, provider: Callable[[], list[Cue]]) -> None:
        """Function returning the show's cue list (targets to choose from)."""
        self._catalog = provider

    def load(self, spec: dict, cue_id: int = -1) -> None:
        """Show *spec* (of the cue *cue_id*) without emitting ``changed``."""
        spec = sanitize_action_spec(spec)
        self._loading = True
        try:
            self._cue_id = int(cue_id)
            self._select(self.combo_kind, spec["kind"])
            self._select(self.combo_target, spec["target"])
            self._select(self.combo_layer, spec["layer"])
            self._select(self.combo_output, spec["output"])
            self._select(self.combo_mode, spec["mode"])
            self._select(self.combo_curve, spec["curve"])
            self.spin_level.setValue(round(float(spec["level"]) * 100.0))
            self.spin_db.setValue(float(spec["db"]))
            self.spin_duration.setValue(float(spec["duration"]))
            if self.edit_text.toPlainText() != spec["text"]:
                self.edit_text.setPlainText(spec["text"])
            items_txt = "\n".join(spec["items"])
            if self.edit_items.toPlainText() != items_txt:
                self.edit_items.setPlainText(items_txt)
            self._note_colour = spec["note_color"]
            self._fill_cue_list(set(spec["cue_ids"]))
            self._refresh_visibility()
        finally:
            self._loading = False

    def spec(self) -> dict:
        """The action described by the controls."""
        cue_ids = [
            int(self.list_cues.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.list_cues.count())
            if self.list_cues.item(i).checkState() == Qt.CheckState.Checked
        ]
        return sanitize_action_spec({
            "kind": self.combo_kind.currentData(),
            "target": self.combo_target.currentData(),
            "layer": self.combo_layer.currentData(),
            "output": self.combo_output.currentData(),
            "cue_ids": cue_ids,
            "duration": self.spin_duration.value(),
            "mode": self.combo_mode.currentData(),
            "level": self.spin_level.value() / 100.0,
            "db": self.spin_db.value(),
            "curve": self.combo_curve.currentData(),
            "text": self.edit_text.toPlainText(),
            "note_color": self._note_colour,
            "items": self.edit_items.toPlainText().splitlines(),
        })

    # ── Internals ─────────────────────────────────────────────────────
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Keep Space/Delete inside the target list (see ``_build_ui``)."""
        if obj is self.list_cues and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            key = event.key()
            if key in (Qt.Key.Key_Space, Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                event.accept()
                if event.type() == QEvent.Type.KeyPress and key == Qt.Key.Key_Space:
                    item = self.list_cues.currentItem()
                    if item is not None:
                        item.setCheckState(
                            Qt.CheckState.Unchecked
                            if item.checkState() == Qt.CheckState.Checked
                            else Qt.CheckState.Checked
                        )
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _select(combo: QComboBox, value: object) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _fill_cue_list(self, chosen: set[int]) -> None:
        self.list_cues.clear()
        cues = list(self._catalog() or [])
        known = {c.cue_id for c in cues}
        for row, cue in enumerate(cues):
            if cue.media_type == MediaType.ACTION or cue.cue_id == self._cue_id:
                continue
            item = QListWidgetItem(f"{format_cue_ref(row, cue)}  {cue.name}  [{cue.media_type.value}]")
            item.setData(Qt.ItemDataRole.UserRole, cue.cue_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if cue.cue_id in chosen else Qt.CheckState.Unchecked)
            self.list_cues.addItem(item)
        for cid in sorted(chosen - known):
            # A target deleted from the show stays listed so the loss is visible.
            item = QListWidgetItem("? cue eliminata dalla scaletta")
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_cues.addItem(item)

    def _refresh_visibility(self) -> None:
        kind = self.combo_kind.currentData()
        target = self.combo_target.currentData()
        mode = self.combo_mode.currentData()
        has_target = action_needs_target(kind)
        timed = kind in (ACTION_FADE, ACTION_LEVEL, ACTION_OPACITY)
        rows = (
            (self.lbl_target, self.combo_target, has_target),
            (self.lbl_layer, self.row_layer, has_target and target == ACTION_TARGET_LAYER),
            (self.lbl_cues, self.list_cues, has_target and target == ACTION_TARGET_CUES),
            (self.lbl_mode, self.combo_mode, kind == ACTION_LEVEL),
            (self.lbl_level, self.spin_level,
             (kind == ACTION_LEVEL and mode == "absolute") or kind == ACTION_OPACITY),
            (self.lbl_db, self.spin_db, kind == ACTION_LEVEL and mode == "relative"),
            (self.lbl_duration, self.spin_duration, timed),
            (self.lbl_curve, self.combo_curve, kind in (ACTION_LEVEL, ACTION_OPACITY)),
            (self.lbl_text, self.edit_text, not has_target),
            (self.lbl_items, self.edit_items, kind == ACTION_CHECKLIST),
            (self.lbl_colour, self.row_colour, not has_target),
        )
        for label, widget, visible in rows:
            label.setVisible(visible)
            widget.setVisible(visible)
        self.lbl_level.setText("Opacità:" if kind == ACTION_OPACITY else "Livello:")
        self.lbl_help.setText(_KIND_HELP.get(kind, ""))
        for hex_val, btn in self._colour_buttons.items():
            btn.setChecked(hex_val == self._note_colour)
        self.lbl_summary.setText("⚡ " + describe_action(self.spec(), self._catalog() or []))

    def _on_colour(self, hex_val: str) -> None:
        self._note_colour = hex_val
        self._on_edit()

    def _on_edit(self, *_args: object) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._refresh_visibility()
        finally:
            self._loading = False
        self.changed.emit()
