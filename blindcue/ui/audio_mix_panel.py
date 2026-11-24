"""Mixer settings of a sound cue (3.2 / 3.9): pan, more outputs with their levels, EQ, reverb.

Used by the inspector and by the "Edit cue" window. Folded by default (a
plain cue needs none of it); it opens by itself on a cue that uses it. The
first row is the cue's own output (chosen in the "Output" field above it);
"+ Add output" adds Hall / Foldback rows, each with its own level, -INF
being an explicit "silent here". Values above 0 dB, pan and effects are
played by the own mixer; a note says so, and says when the mixer is off on
this computer (then the cue plays as before, without them).
"""

from __future__ import annotations

from engine import audio_mix
from engine.audio_mix import EQ_BANDS, LEVEL_MAX_DB, LEVEL_MIN_DB, MixSettings, Send
from engine.audio_routes import LABELS, OUTPUTS
from i18n import tr
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_INF_VALUE = LEVEL_MIN_DB - 0.5   # the spin box minimum shows "-INF"
ROOM_LABELS = {"small": "Stanza piccola", "medium": "Sala media", "large": "Sala grande"}
BAND_LABELS = {"low": "Bassi", "mid": "Medi", "high": "Acuti"}


class DbSpinBox(QDoubleSpinBox):
    """A level in dB, -60..+12, whose lowest step is -INF (silent)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(_INF_VALUE, LEVEL_MAX_DB)
        self.setDecimals(1)
        self.setSingleStep(1.0)
        self.setSuffix(" dB")
        self.setSpecialValueText("-INF")
        self.setKeyboardTracking(False)
        self.setMinimumWidth(84)

    def db(self) -> float | None:
        value = self.value()
        return None if value <= _INF_VALUE + 0.01 else round(value, 1)

    def set_db(self, db: float | None) -> None:
        self.setValue(_INF_VALUE if db is None else float(db))


class AudioMixPanel(QWidget):
    """Pan, output rows, EQ and reverb of one sound cue; ``changed`` on every edit."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main = "stage"
        self._loading = False
        self._preview_hint = False
        self._rows: list[tuple[QWidget, QComboBox, DbSpinBox]] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(4)

        self.btn_toggle = QToolButton()
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.btn_toggle.setText("Mixer: panorama, più uscite, effetti")
        self.btn_toggle.setToolTip("Panorama sinistra / destra, la stessa cue su più uscite con il proprio "
                                   "livello, livelli sopra 0 dB, equalizzatore e riverbero.")
        self.btn_toggle.setAccessibleName("Mostra le impostazioni del mixer")
        self.btn_toggle.toggled.connect(self._on_toggle)
        lay.addWidget(self.btn_toggle)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(14, 0, 0, 0)
        body.setSpacing(4)
        lay.addWidget(self.body)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        grid.addWidget(QLabel("Livello uscita:"), 0, 0)
        self.spin_level = DbSpinBox()
        self.spin_level.setToolTip("Livello della cue sulla sua uscita (quella scelta sopra); -INF = in silenzio. "
                                   "Sopra 0 dB suona attraverso il mixer interno.")
        self.spin_level.setAccessibleName("Livello della cue sulla sua uscita in decibel")
        self.spin_level.valueChanged.connect(self._emit)
        grid.addWidget(self.spin_level, 0, 1)
        grid.addWidget(QLabel("Panorama:"), 1, 0)
        pan_row = QHBoxLayout()
        self.sl_pan = QSlider(Qt.Orientation.Horizontal)
        self.sl_pan.setRange(-100, 100)
        self.sl_pan.setSingleStep(5)
        self.sl_pan.setPageStep(25)
        self.sl_pan.setToolTip("Da dove arriva il suono: sinistra, centro, destra.")
        self.sl_pan.setAccessibleName("Panorama: sinistra meno cento, centro zero, destra più cento")
        self.sl_pan.valueChanged.connect(self._on_pan)
        pan_row.addWidget(self.sl_pan, 1)
        self.lbl_pan = QLabel(tr("C"))
        self.lbl_pan.setMinimumWidth(42)
        pan_row.addWidget(self.lbl_pan)
        self.btn_pan_reset = QPushButton("C")
        self.btn_pan_reset.setFixedWidth(28)
        self.btn_pan_reset.setToolTip("Al centro")
        self.btn_pan_reset.setAccessibleName("Panorama al centro")
        self.btn_pan_reset.clicked.connect(lambda: self.sl_pan.setValue(0))
        pan_row.addWidget(self.btn_pan_reset)
        grid.addLayout(pan_row, 1, 1)
        body.addLayout(grid)

        self.lbl_more = QLabel("Altre uscite:")
        body.addWidget(self.lbl_more)
        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(2)
        body.addLayout(self.rows_box)
        add_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Aggiungi uscita")
        self.btn_add.setToolTip("La cue suona anche su un'altra uscita (es. Spie per gli attori), "
                                "con il suo livello.")
        self.btn_add.clicked.connect(self._on_add)
        add_row.addWidget(self.btn_add)
        add_row.addStretch(1)
        body.addLayout(add_row)

        shift_row = QHBoxLayout()
        shift_row.addWidget(QLabel("Cambia tutte le uscite di"))
        self.spin_shift = QDoubleSpinBox()
        self.spin_shift.setRange(-audio_mix.SHIFT_MAX_DB, audio_mix.SHIFT_MAX_DB)
        self.spin_shift.setDecimals(1)
        self.spin_shift.setSingleStep(1.0)
        self.spin_shift.setSuffix(" dB")
        self.spin_shift.setValue(-3.0)
        self.spin_shift.setAccessibleName("Di quanti decibel cambiare tutte le uscite")
        shift_row.addWidget(self.spin_shift)
        self.btn_shift = QPushButton("Applica")
        self.btn_shift.setToolTip("Sposta il livello di ogni uscita (non quelle a -INF).")
        self.btn_shift.setAccessibleName("Cambia tutte le uscite")
        self.btn_shift.clicked.connect(self._on_shift)
        shift_row.addWidget(self.btn_shift)
        shift_row.addStretch(1)
        body.addLayout(shift_row)

        eq_row = QHBoxLayout()
        eq_row.addWidget(QLabel("Equalizzatore:"))
        self.spin_eq: dict[str, QDoubleSpinBox] = {}
        for band in EQ_BANDS:
            eq_row.addWidget(QLabel(BAND_LABELS[band]))
            spin = QDoubleSpinBox()
            spin.setRange(audio_mix.EQ_MIN_DB, audio_mix.EQ_MAX_DB)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setSuffix(" dB")
            spin.setKeyboardTracking(False)
            spin.setToolTip(f"{tr(BAND_LABELS[band])}: {int(audio_mix.EQ_FREQS[band])} Hz")
            spin.setAccessibleName(tr("Equalizzatore {} in decibel").format(tr(BAND_LABELS[band])))
            spin.valueChanged.connect(self._emit)
            self.spin_eq[band] = spin
            eq_row.addWidget(spin)
        eq_row.addStretch(1)
        body.addLayout(eq_row)

        rev_row = QHBoxLayout()
        rev_row.addWidget(QLabel("Riverbero:"))
        self.spin_reverb = QSpinBox()
        self.spin_reverb.setRange(0, 100)
        self.spin_reverb.setSingleStep(5)
        self.spin_reverb.setSuffix(" %")
        self.spin_reverb.setSpecialValueText("spento")
        self.spin_reverb.setKeyboardTracking(False)
        self.spin_reverb.setToolTip("Quanto riverbero aggiungere (0 = nessuno).")
        self.spin_reverb.setAccessibleName("Riverbero in percento")
        self.spin_reverb.valueChanged.connect(self._emit)
        rev_row.addWidget(self.spin_reverb)
        self.combo_room = QComboBox()
        for key in audio_mix.ROOMS:
            self.combo_room.addItem(ROOM_LABELS[key], key)
        self.combo_room.setCurrentIndex(1)
        self.combo_room.setAccessibleName("Grandezza della stanza del riverbero")
        self.combo_room.currentIndexChanged.connect(self._emit)
        rev_row.addWidget(self.combo_room)
        rev_row.addStretch(1)
        body.addLayout(rev_row)

        self.lbl_note = QLabel("")
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("QLabel { color: #94a3b8; font-size: 11px; }")
        body.addWidget(self.lbl_note)
        self.body.setVisible(False)

    # ── loading / reading ─────────────────────────────────────────────
    def load(self, mix: dict | None, main_output: str = "stage") -> None:
        """Show the settings of a cue (no ``changed`` while loading)."""
        self._loading = True
        try:
            self._main = main_output if main_output in (*OUTPUTS, "mute") else "stage"
            settings = MixSettings.from_dict(mix or {}, self._main)
            self.spin_level.set_db(settings.level_db)
            self.sl_pan.setValue(round(settings.pan * 100))
            self._on_pan(self.sl_pan.value(), emit=False)
            for band in EQ_BANDS:
                self.spin_eq[band].setValue(float(settings.eq.get(band, 0.0)))
            self.spin_reverb.setValue(round(settings.reverb * 100))
            self.combo_room.setCurrentIndex(max(0, self.combo_room.findData(settings.room)))
            self._clear_rows()
            for send in settings.sends:
                self._add_row(send.out, send.db)
            used = not settings.is_default()
            self.btn_toggle.setChecked(used or self.btn_toggle.isChecked())
            self._refresh()
        finally:
            self._loading = False

    def settings(self) -> MixSettings:
        sends = [Send(combo.currentData(), spin.db()) for _w, combo, spin in self._rows if combo.currentData()]
        return MixSettings.from_dict(MixSettings(
            level_db=self.spin_level.db(),
            pan=self.sl_pan.value() / 100.0,
            sends=sends,
            eq={band: self.spin_eq[band].value() for band in EQ_BANDS},
            reverb=self.spin_reverb.value() / 100.0,
            room=self.combo_room.currentData() or "medium",
        ).to_dict(), self._main)

    def values(self) -> dict:
        """What goes into ``Cue.audio_mix`` ({} = nothing of the mixer)."""
        return self.settings().to_dict()

    def set_preview_hint(self, on: bool) -> None:
        """Say that the private preview of this window plays without the mixer."""
        self._preview_hint = bool(on)
        self._refresh()

    def set_main_output(self, key: str) -> None:
        """The cue's own output changed: a row on that output goes (one row per output)."""
        self._main = key
        for widget, combo, _spin in list(self._rows):
            if combo.currentData() == key:
                self._remove_row(widget)
        self._refresh()

    # ── rows ──────────────────────────────────────────────────────────
    def _free_outputs(self) -> list[str]:
        taken = {self._main} | {combo.currentData() for _w, combo, _s in self._rows}
        return [k for k in OUTPUTS if k not in taken]

    def _add_row(self, out: str, db: float | None = 0.0) -> None:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        for key in OUTPUTS:
            combo.addItem(LABELS[key], key)
        combo.setCurrentIndex(max(0, combo.findData(out)))
        combo.setAccessibleName("Altra uscita della cue")
        spin = DbSpinBox()
        spin.set_db(db)
        spin.setAccessibleName("Livello su questa uscita in decibel")
        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.setToolTip("Togli questa uscita")
        remove.setAccessibleName("Togli questa uscita")
        lay.addWidget(combo, 1)
        lay.addWidget(spin)
        lay.addWidget(remove)
        self.rows_box.addWidget(row)
        self._rows.append((row, combo, spin))
        combo.currentIndexChanged.connect(lambda _i, c=combo: self._on_row_output(c))
        spin.valueChanged.connect(self._emit)
        remove.clicked.connect(lambda _c=False, w=row: (self._remove_row(w), self._refresh(), self._emit()))

    def _remove_row(self, widget: QWidget) -> None:
        self._rows = [r for r in self._rows if r[0] is not widget]
        widget.setParent(None)
        widget.deleteLater()

    def _clear_rows(self) -> None:
        for widget, _c, _s in list(self._rows):
            self._remove_row(widget)

    def _on_add(self) -> None:
        free = self._free_outputs()
        if not free:
            return
        self._add_row(free[0], 0.0)
        self._refresh()
        self._emit()

    def _on_row_output(self, combo: QComboBox) -> None:
        # One row per output: a row moved onto an output already used goes back to a free one.
        key = combo.currentData()
        others = [c.currentData() for _w, c, _s in self._rows if c is not combo]
        if key == self._main or key in others:
            free = self._free_outputs()
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(free[0])) if free else 0)
            combo.blockSignals(False)
        self._refresh()
        self._emit()

    # ── other edits ───────────────────────────────────────────────────
    def _on_toggle(self, on: bool) -> None:
        self.body.setVisible(on)
        self.btn_toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    def _on_pan(self, value: int, emit: bool = True) -> None:
        if value == 0:
            text = tr("C")
        else:
            text = (tr("L {}") if value < 0 else tr("R {}")).format(abs(value))
        self.lbl_pan.setText(text)
        if emit:
            self._emit()

    def _on_shift(self) -> None:
        moved = self.settings().shifted(self.spin_shift.value())
        self._loading = True
        try:
            self.spin_level.set_db(moved.level_db)
            for (_w, _c, spin), send in zip(self._rows, moved.sends):
                spin.set_db(send.db)
        finally:
            self._loading = False
        self._emit()

    def _emit(self, *_args) -> None:
        if self._loading:
            return
        self._refresh()
        self.changed.emit()

    def _refresh(self) -> None:
        self.btn_add.setEnabled(bool(self._free_outputs()))
        self.lbl_more.setVisible(bool(self._rows))
        self.spin_level.setEnabled(self._main != "mute")
        from engine.audio_mixer_output import mixer_enabled

        extras = self.settings().extras()
        if not extras:
            note = tr("Nessuna impostazione del mixer: la cue suona come sempre.")
        elif not mixer_enabled():
            note = tr("⚠ Mixer spento su questo computer (Show → Dispositivi → Uscite audio): la cue suona "
                      "senza queste impostazioni.")
        else:
            note = tr("Questa cue suona attraverso il mixer interno.")
        if extras and self._preview_hint:
            note += " " + tr("L'ascolto di prova (▶) suona senza il mixer.")
        self.lbl_note.setText(note)
