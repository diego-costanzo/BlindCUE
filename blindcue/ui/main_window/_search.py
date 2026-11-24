"""Find a cue (stage 2, item 2.8) mixin for MainWindow.

Ctrl+F in Preparation opens a search field above the cue list: typing
filters the list live (name, Q, notes, file path, case-insensitive), Enter
selects the first match, Esc closes it and shows the whole list again. In
the Rehearsal and the Show, Ctrl+F only asks what to find and moves the GO
pointer to the next match - nothing is filtered or edited there.
"""

from __future__ import annotations

from pathlib import Path

from i18n import tr
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QInputDialog, QLineEdit

from ui.main_window._common import *  # noqa: F403,F401,F405


def cue_matches(cue: Cue, text: str) -> bool:
    """True when *text* is in the cue's name, Q, notes or file path (case-insensitive)."""
    needle = (text or "").strip().casefold()
    if not needle:
        return True
    hay = " ".join((cue.name or "", cue.q_label or "", cue.notes or "", cue.file_path or "",
                    Path(cue.file_path or "").name))
    return needle in hay.casefold()


class _SearchKeys(QObject):
    """Esc in the search field closes it (it never counts towards a PANIC there)."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._win = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and event.key() == Qt.Key.Key_Escape:
            event.accept()
            if event.type() == QEvent.Type.KeyPress:
                self._win._search_close()
            return True
        return False


class _SearchMixin:
    def _search_setup(self) -> None:
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("Cerca: nome, Q, note, file…  (Invio: primo risultato, Esc: chiudi)"))
        self._search_edit.setAccessibleName(tr("Cerca nella scaletta"))
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setVisible(False)
        self._search_edit.textChanged.connect(self._search_apply)
        self._search_edit.returnPressed.connect(self._search_first)
        self._search_edit.installEventFilter(_SearchKeys(self))
        self._cue_list_panel.layout().insertWidget(0, self._search_edit)
        QShortcut(QKeySequence("Ctrl+F"), self, self._search_open)

    def _search_open(self) -> None:
        from engine.show_mode import PREPARATION

        if self._current_mode() != PREPARATION:
            text = self._search_ask()
            if text and text.strip():
                self._search_jump(text)
            return
        self._search_edit.setVisible(True)
        self._search_edit.setFocus()
        self._search_edit.selectAll()
        self._search_apply(self._search_edit.text())

    def _search_ask(self) -> str | None:
        """Rehearsal / Show: what to find. Esc and Shift+Esc keep their emergency meaning here."""
        from ui.main_window._cue_table import _EmergencyKeysInDialog

        dlg = QInputDialog(self)
        dlg.setWindowTitle(tr("Cerca una cue"))
        dlg.setInputMode(QInputDialog.InputMode.TextInput)
        dlg.setLabelText(tr("Nome, Q, note o file:"))
        keys = _EmergencyKeysInDialog(self, dlg)
        dlg.installEventFilter(keys)
        for child in dlg.findChildren(QWidget):
            child.installEventFilter(keys)
        return dlg.textValue() if dlg.exec() == QDialog.DialogCode.Accepted else None

    def _search_apply(self, text: str) -> None:
        if self._search_edit.isHidden():  # closed (isVisible is False too while the window is hidden)
            return
        shown = 0
        hidden_selected = False
        selected = set(self._selected_rows())
        for row, cue in enumerate(self._cues):
            hit = cue_matches(cue, text)
            self._cue_list.setRowHidden(row, not hit)
            shown += hit
            hidden_selected |= (not hit and row in selected)
        if hidden_selected:  # Delete / Alt+arrows never act on cues the filter hides
            keep = [r for r in sorted(selected) if not self._cue_list.isRowHidden(r)]
            if keep:
                self._cue_list.select_rows(keep, anchor_row=keep[0])
            else:
                self._cue_list.clearSelection()
        self._status_label.setText(tr("Trovate {} cue su {}").format(shown, len(self._cues)) if text.strip() else "")

    def _search_first(self) -> None:
        text = self._search_edit.text()
        row = next((i for i, c in enumerate(self._cues) if cue_matches(c, text)), -1)
        if row >= 0:
            self._cue_list.setCurrentRow(row)
            self._cue_list.setFocus()

    def _search_close(self) -> None:
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)
        self._search_edit.setVisible(False)
        self._refresh_cue_list(keep_selection=True)  # the whole list again (groups folded as before)
        self._cue_list.setFocus()

    def _search_jump(self, text: str) -> None:
        """Rehearsal / Show: the GO pointer goes to the next match (nothing is filtered)."""
        start = self._go_target_index()
        order = list(range(start + 1, len(self._cues))) + list(range(0, start + 1))
        row = next((i for i in order if not ShowEngine.outside_go_order(self._cues[i])
                    and cue_matches(self._cues[i], text)), -1)  # GO never lands on a timed/relative cue
        if row < 0:
            self._status_label.setText(tr("Nessuna cue trovata: '{}'").format(text))
            return
        self._cue_list.setCurrentRow(row)
        self._sync_live_view()
        self._status_label.setText(tr("Prossimo GO: {}").format(f"{format_cue_ref(row, self._cues[row])} "
                                                               f"'{self._cues[row].name}'"))
