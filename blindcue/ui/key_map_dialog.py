"""Keys and presenter remote (stage 5, items 5.7 and 5.8): extra keys for a few safe functions.

A row per function with its extra keys; "Add a key…" waits for a key or a
button of the remote; "Remote wizard…" asks for the buttons one by one
(GO, previous cue, pause); "Presenter remote" fills the usual keys of such
remotes; "Defaults" removes every extra key. Keys the program uses, keys of
two functions and keys of the show's effects are pointed out below.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engine import key_map as km

SKIP = 2  # KeyCaptureDialog result: go on without a key


def _key_name(event) -> str:
    from ui.main_window._key_map import key_name

    return key_name(event)


class KeyCaptureDialog(QDialog):
    """Waits for one key (no Ctrl / Alt / Shift): ``captured`` after ``Accepted``."""

    def __init__(self, prompt: str, parent: QWidget | None = None, can_skip: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Premi un tasto"))
        self.captured = ""
        lay = QVBoxLayout(self)
        label = QLabel(prompt)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 15px;")
        lay.addWidget(label)
        row = QHBoxLayout()
        if can_skip:
            skip = QPushButton(tr("Salta"))
            skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # every key goes to the capture, not to a button
            skip.clicked.connect(lambda: self.done(SKIP))
            row.addWidget(skip)
        cancel = QPushButton(tr("Interrompi"))
        cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            return  # combinations are for the menus
        name = _key_name(event)
        if name:
            self.captured = name
            self.accept()


class KeyMapDialog(QDialog):
    def __init__(self, key_map: dict[str, list[str]], effect_keys: list[str],
                 parent: QWidget | None = None, space_go: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Tasti e telecomando di presentazione"))
        self.setMinimumSize(620, 460)
        self._map = {f: list(keys) for f, keys in km.clean(key_map).items()}
        self._effects = effect_keys
        lay = QVBoxLayout(self)
        intro = QLabel(tr(
            "Tasti in più per questo computer, attivi nella prova e nello spettacolo. I tasti del programma "
            "restano (Spazio = GO, Esc due volte = PANIC). Un telecomando di presentazione funziona come una "
            "tastiera: premi i suoi pulsanti qui sotto."))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTableWidget(len(km.FUNCTIONS), 4)
        self.table.setHorizontalHeaderLabels([tr("Funzione"), tr("Tasti"), "", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        for row, func in enumerate(km.FUNCTIONS):
            self.table.setItem(row, 0, QTableWidgetItem(tr(km.LABELS[func])))
            add = QPushButton(tr("Aggiungi un tasto…"))
            add.clicked.connect(lambda _=False, f=func: self._capture_for(f))
            clear = QPushButton(tr("Togli"))
            clear.clicked.connect(lambda _=False, f=func: self._clear(f))
            self.table.setCellWidget(row, 2, add)
            self.table.setCellWidget(row, 3, clear)
        lay.addWidget(self.table, 1)
        tools = QHBoxLayout()
        wizard = QPushButton(tr("🎯 Procedura guidata del telecomando…"))
        wizard.clicked.connect(self._wizard)
        presenter = QPushButton(tr("Telecomando di presentazione (tasti tipici)"))
        presenter.clicked.connect(lambda: self._set_map(km.PRESENTER))
        defaults = QPushButton(tr("Predefiniti (nessun tasto in più)"))
        defaults.clicked.connect(lambda: self._set_map({}))
        for b in (wizard, presenter, defaults):
            tools.addWidget(b)
        lay.addLayout(tools)
        # 5.7: the only key of the program that may be switched off here (Esc, Enter, arrows, F5 stay).
        self.chk_space = QCheckBox(tr("Spazio = GO (tasto del programma)"))
        self.chk_space.setChecked(space_go)
        self.chk_space.setToolTip(tr("Togli la spunta se il GO deve venire solo dal telecomando o da un tasto "
                                     "scelto qui (per esempio uno Spazio premuto per sbaglio). Ctrl+Spazio e "
                                     "il pulsante GO restano."))
        self.chk_space.toggled.connect(lambda _on: self._show())
        lay.addWidget(self.chk_space)
        self.lbl_conflicts = QLabel()
        self.lbl_conflicts.setWordWrap(True)
        self.lbl_conflicts.setStyleSheet("color: #fbbf24;")
        lay.addWidget(self.lbl_conflicts)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._show()

    def key_map(self) -> dict[str, list[str]]:
        return km.clean(self._map)

    def space_go(self) -> bool:
        return self.chk_space.isChecked()

    def _set_map(self, key_map: dict[str, list[str]]) -> None:
        self._map = {f: list(keys) for f, keys in key_map.items()}
        self._show()

    def _add_key(self, func: str, key: str) -> None:
        keys = self._map.setdefault(func, [])
        if key not in keys:
            keys.append(key)
        self._show()

    def _clear(self, func: str) -> None:
        self._map.pop(func, None)
        self._show()

    def _capture_for(self, func: str) -> None:
        dlg = KeyCaptureDialog(tr("Premi il tasto o il pulsante del telecomando per: {}").format(
            tr(km.LABELS[func])), self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured:
            self._add_key(func, dlg.captured)

    def _wizard(self) -> None:
        """5.7: the remote's buttons one by one (GO, previous cue, pause)."""
        for func in km.WIZARD:
            dlg = KeyCaptureDialog(tr("Premi sul telecomando il pulsante per: {}").format(tr(km.LABELS[func])),
                                   self, can_skip=True)
            result = dlg.exec()
            if result == QDialog.DialogCode.Rejected:
                return
            if result == QDialog.DialogCode.Accepted and dlg.captured:
                self._add_key(func, dlg.captured)

    def _show(self) -> None:
        for row, func in enumerate(km.FUNCTIONS):
            self.table.setItem(row, 1, QTableWidgetItem(", ".join(self._map.get(func, [])) or "—"))
        self.table.resizeColumnsToContents()
        lines = []
        space_go = self.chk_space.isChecked() if hasattr(self, "chk_space") else True
        if not km.go_reachable(self._map, space_go):
            lines.append(tr("⚠ Senza Spazio e senza un tasto per il GO, il GO si dà solo con il pulsante GO "
                            "o con Ctrl+Spazio"))
        for key, kind, detail in km.conflicts(self._map, self._effects, space_go):
            if kind == "reserved":
                lines.append(tr("⚠ {}: il programma lo usa già ({})").format(key, tr(detail)))
            elif kind == "twice":
                lines.append(tr("⚠ {}: assegnato a due funzioni – vale la prima").format(key))
            else:
                lines.append(tr("⚠ {}: è il tasto di un effetto di questo spettacolo – vale l'effetto").format(key))
        self.lbl_conflicts.setText("\n".join(lines))
