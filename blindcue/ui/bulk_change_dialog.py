"""The "Change the selected cues" window (stage 5, item 5.2).

Relative steps for several cues at once (±dB, ±seconds); the list below
shows every change before OK. The logic is in ``engine.bulk_change``.
"""

from __future__ import annotations

from engine import bulk_change as bc
from i18n import tr
from models.cue import Cue, MediaType
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

_FIELD_WORDS = {"volume": "Volume", "fade_in": "Fade In", "fade_out": "Fade Out", "pre_delay": "Pre-Delay",
                "post_delay": "Post-Delay"}


def step_text(cues: list[Cue], step: bc.Step) -> str:
    cue = cues[step.row]
    who = f"#{step.row + 1} {cue.q_label + ' ' if cue.q_label else ''}'{cue.name}'"
    if step.field == "volume":
        return f"{who}: {tr('Volume')} {round(step.old * 100)} % → {round(step.new * 100)} %"
    return f"{who}: {tr(_FIELD_WORDS[step.field])} {step.old:g} → {step.new:g} s"


class BulkChangeDialog(QDialog):
    def __init__(self, cues: list[Cue], rows: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cues = cues
        self._rows = sorted(rows)
        self.setWindowTitle(tr("Cambia le cue selezionate"))
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        intro = QLabel(tr("{} cue selezionate. Ogni cue cambia del passo indicato e tiene la sua differenza "
                          "dalle altre (0 = invariato).").format(len(self._rows)))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.spin_db = self._spin(-bc.MAX_DB, bc.MAX_DB, 1.0, " dB")
        self.spin_db.setToolTip(tr("Più forte (+) o più piano (−); il volume resta tra 0 e 100 %"))
        form.addRow(QLabel(tr("Volume ±")), self.spin_db)
        self.spins = {}
        for field in bc.DELTA_FIELDS:
            spin = self._spin(-bc.MAX_SECONDS, bc.MAX_SECONDS, 0.5, " s")
            self.spins[field] = spin
            form.addRow(QLabel(tr(_FIELD_WORDS[field]) + " ±"), spin)
        lay.addLayout(form)
        has_scene = any(cues[r].media_type == MediaType.GROUP for r in self._rows if 0 <= r < len(cues))
        self.chk_scenes = QCheckBox(tr("Anche le cue dentro le scene selezionate"))
        self.chk_scenes.setChecked(True)
        self.chk_scenes.setVisible(has_scene)
        self.chk_scenes.toggled.connect(self._refresh)
        lay.addWidget(self.chk_scenes)
        lay.addWidget(QLabel(tr("Che cosa cambierà:")))
        self.preview = QListWidget()
        lay.addWidget(self.preview, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self._refresh()

    def _spin(self, low: float, high: float, step: float, suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setDecimals(1)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(self._refresh)
        return spin

    def deltas(self) -> dict[str, float]:
        out = {bc.VOLUME_DB: self.spin_db.value()}
        out.update({field: spin.value() for field, spin in self.spins.items()})
        return out

    def rows(self) -> list[int]:
        """The selected rows, plus the cues of the selected scenes when the box (shown only then) is ticked."""
        if not self.chk_scenes.isHidden() and self.chk_scenes.isChecked():
            return bc.with_scene_cues(self._cues, self._rows)
        return list(self._rows)

    def steps(self) -> list[bc.Step]:
        return bc.plan(self._cues, self.rows(), self.deltas())

    def _refresh(self, *_args) -> None:
        steps = self.steps()
        self.preview.clear()
        for step in steps[:300]:
            self.preview.addItem(step_text(self._cues, step))
        if len(steps) > 300:
            self.preview.addItem(tr("… e altre {}").format(len(steps) - 300))
        if not steps:
            self.preview.addItem(tr("Niente da cambiare: scegli un passo diverso da 0"))
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(bool(steps))
        ok.setText(tr("Applica a {} cue").format(len({s.row for s in steps})))
