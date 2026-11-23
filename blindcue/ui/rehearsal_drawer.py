"""The rehearsal drawer (stage 1 C2a step 9): small fixes of one cue during a run.

Opened only by an explicit "✎" next to a named cue (Last line, Next bar, a
card of Now playing, the row menu), so there is one cursor: a click on a row
still only sets the next cue. Every change is saved at once and can be undone
(Ctrl+Z); the list "changes from the rehearsal" keeps what was before. The
drawer takes the place of the output preview; Esc never closes it (Esc is
PANIC) – "×" does.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

FIELDS = ("name", "notes", "volume", "fade_in", "fade_out", "in_point", "out_point", "follow_mode")
FOLLOW_CHOICES = (("MANUAL", "Manuale (GO)"), ("AUTO_FOLLOW", "Auto-GO al termine"),
                  ("SIMULTANEOUS", "Insieme alla successiva"))


def _spin(maximum: float, special: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.0, maximum)
    spin.setDecimals(1)
    spin.setSingleStep(0.1)
    spin.setSuffix(" s")
    spin.setKeyboardTracking(False)  # one change when typing is done, not per digit
    if special:
        spin.setSpecialValueText(special)
    spin.setMaximumWidth(100)
    return spin


class RehearsalDrawer(QFrame):
    """A few fields of one cue, changed while the rehearsal runs."""

    field_changed = Signal(str, object)   # field name, new value
    closed = Signal()
    done_editing = Signal()               # Enter in a field: the keyboard goes back to the list
    review_requested = Signal()
    more_requested = Signal()             # "More settings → Preparation"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rehearsalDrawer")
        self.setAccessibleName("Correzioni della prova")
        self.setStyleSheet(
            "QFrame#rehearsalDrawer { background-color: #0c1a2b; border: 1px solid #38bdf8; border-radius: 6px; } "
            "QFrame#rehearsalDrawer QLabel { background: transparent; color: #e2e8f0; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)
        # Never wider than the column (it scrolls there when the column is short).
        self.setMaximumWidth(340)
        head = QHBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_title.setStyleSheet("QLabel { color: #bae6fd; font-weight: bold; font-size: 13px; }")
        head.addWidget(self.lbl_title, stretch=1)
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 26)
        self.btn_close.setToolTip("Chiudi le correzioni (le modifiche restano)")
        self.btn_close.setAccessibleName("Chiudi le correzioni")
        self.btn_close.clicked.connect(self.closed)
        head.addWidget(self.btn_close)
        root.addLayout(head)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        self.ed_name = QLineEdit()
        self.ed_name.editingFinished.connect(lambda: self._emit("name", self.ed_name.text().strip()))
        form.addRow(QLabel("Nome"), self.ed_name)
        self.ed_notes = QLineEdit()
        self.ed_notes.editingFinished.connect(lambda: self._emit("notes", self.ed_notes.text()))
        form.addRow(QLabel("Note"), self.ed_notes)
        level = QHBoxLayout()
        self.sl_volume = QSlider(Qt.Orientation.Horizontal)
        self.sl_volume.setRange(0, 100)
        self.sl_volume.setAccessibleName("Livello della cue")
        self.sl_volume.valueChanged.connect(lambda v: self.lbl_volume.setText(f"{v} %"))
        self.sl_volume.sliderReleased.connect(lambda: self._emit("volume", self.sl_volume.value() / 100.0))
        self.sl_volume.valueChanged.connect(
            lambda v: None if self.sl_volume.isSliderDown() else self._emit("volume", v / 100.0))
        level.addWidget(self.sl_volume, stretch=1)
        self.lbl_volume = QLabel("100 %")
        self.lbl_volume.setFixedWidth(42)
        level.addWidget(self.lbl_volume)
        form.addRow(QLabel("Livello"), level)
        fades = QHBoxLayout()
        self.sp_fade_in = _spin(60.0)
        self.sp_fade_in.valueChanged.connect(lambda v: self._emit("fade_in", float(v)))
        self.sp_fade_out = _spin(60.0)
        self.sp_fade_out.valueChanged.connect(lambda v: self._emit("fade_out", float(v)))
        fades.addWidget(self.sp_fade_in)
        fades.addWidget(QLabel("↘"))
        fades.addWidget(self.sp_fade_out)
        self.sp_fade_in.setToolTip("Entra (dissolvenza in entrata)")
        self.sp_fade_out.setToolTip("Sfuma (dissolvenza in uscita)")
        form.addRow(QLabel("↗ / ↘"), fades)
        points = QHBoxLayout()
        self.sp_in = _spin(36000.0)
        self.sp_in.valueChanged.connect(lambda v: self._emit("in_point", float(v)))
        self.sp_out = _spin(36000.0, "fine")
        self.sp_out.valueChanged.connect(lambda v: self._emit("out_point", float(v) if v > 0 else None))
        points.addWidget(self.sp_in)
        points.addWidget(QLabel("→"))
        points.addWidget(self.sp_out)
        self.sp_in.setToolTip("Inizio (dove parte il file)")
        self.sp_out.setToolTip("Fine (dove si ferma; «fine» = fine del file)")
        form.addRow(QLabel("Da / a"), points)
        self.cb_follow = QComboBox()
        for value, label in FOLLOW_CHOICES:
            self.cb_follow.addItem(label, value)
        self.cb_follow.currentIndexChanged.connect(
            lambda _i: self._emit("follow_mode", self.cb_follow.currentData()))
        form.addRow(QLabel("Poi"), self.cb_follow)
        root.addLayout(form)

        foot = QHBoxLayout()
        self.lbl_changes = QLabel("")
        foot.addWidget(self.lbl_changes, stretch=1)
        self.btn_review = QPushButton("Rivedi")
        self.btn_review.clicked.connect(self.review_requested)
        foot.addWidget(self.btn_review)
        root.addLayout(foot)
        self.btn_more = QPushButton("Altre impostazioni → Preparazione")
        self.btn_more.clicked.connect(self.more_requested)
        root.addWidget(self.btn_more)
        self.setMinimumHeight(372)
        for w in (self.ed_name, self.ed_notes, self.sp_fade_in, self.sp_fade_out, self.sp_in, self.sp_out):
            w.installEventFilter(self)
        self._loading = False
        self.hide()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        from PySide6.QtCore import QEvent, QTimer

        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # After the field takes the value: Space must be GO again, not a space in the name.
            QTimer.singleShot(0, self.done_editing.emit)
        return super().eventFilter(obj, event)

    def _emit(self, field: str, value: object) -> None:
        if not self._loading:
            self.field_changed.emit(field, value)

    def edit(self, title: str, values: dict, playing: bool) -> None:
        """Show *values* of the cue (without reporting them as changes)."""
        self._loading = True
        try:
            self.lbl_title.setText(title)
            self.ed_name.setText(str(values.get("name", "")))
            self.ed_notes.setText(str(values.get("notes", "")))
            self.sl_volume.setValue(round(float(values.get("volume", 1.0)) * 100))
            self.sp_fade_in.setValue(float(values.get("fade_in", 0.0)))
            self.sp_fade_out.setValue(float(values.get("fade_out", 0.0)))
            self.sp_in.setValue(float(values.get("in_point", 0.0)))
            out = values.get("out_point")
            self.sp_out.setValue(float(out) if out else 0.0)
            idx = self.cb_follow.findData(values.get("follow_mode", "MANUAL"))
            self.cb_follow.setCurrentIndex(max(0, idx))
            # What follows and when it starts change only while the cue does not play.
            self.cb_follow.setEnabled(not playing)
            self.cb_follow.setToolTip("" if not playing else "Si cambia quando la cue non suona")
        finally:
            self._loading = False
        self.show()

    def set_changes(self, text: str, count: int) -> None:
        self.lbl_changes.setText(text)
        self.btn_review.setEnabled(count > 0)
