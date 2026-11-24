"""Renumber the Q labels with a preview (stage 5, item 5.2)."""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine import renumber


class RenumberDialog(QDialog):
    def __init__(self, cues, chosen: list[int], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cues = cues
        self.chosen = chosen
        self.setWindowTitle("Rinumera le Q")
        self.setMinimumSize(520, 420)
        lay = QVBoxLayout(self)
        scope = (tr("Le cue selezionate lanciate con GO ({})").format(len(renumber.numbered_rows(cues, chosen)))
                 if chosen else tr("Tutte le cue lanciate con GO ({})").format(len(renumber.numbered_rows(cues))))
        lay.addWidget(QLabel(scope))
        form = QFormLayout()
        self.edit_prefix = QLineEdit("Q")
        self.edit_prefix.setMaxLength(6)
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 9999)
        self.spin_start.setValue(1)
        self.spin_step = QSpinBox()
        self.spin_step.setRange(1, 100)
        self.spin_step.setValue(1)
        self.spin_step.setToolTip("Passo 10 lascia spazio per le cue aggiunte dopo (Q10, Q15, Q20)")
        form.addRow(QLabel("Prefisso:"), self.edit_prefix)
        form.addRow(QLabel("Primo numero:"), self.spin_start)
        form.addRow(QLabel("Passo:"), self.spin_step)
        lay.addLayout(form)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Cue"), tr("Prima"), tr("Dopo")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        for w in (self.spin_start, self.spin_step):
            w.valueChanged.connect(self._preview)
        self.edit_prefix.textChanged.connect(self._preview)
        self._preview()

    def changes(self) -> list[tuple[int, str, str]]:
        return renumber.plan(self.cues, self.chosen, self.spin_start.value(), self.spin_step.value(),
                             self.edit_prefix.text().strip())

    def _preview(self) -> None:
        rows = self.changes()
        self.table.setRowCount(len(rows))
        for i, (row, old, new) in enumerate(rows):
            for col, text in enumerate((f"#{row + 1} {self.cues[row].name}", old or "—", new)):
                item = QTableWidgetItem(text)
                self.table.setItem(i, col, item)
        self.table.resizeColumnsToContents()
