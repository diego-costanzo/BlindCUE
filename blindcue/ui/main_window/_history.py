"""Undo with names and backups put back (stage 5, item 5.11) mixin for MainWindow.

- Edit → "History of changes…": every step Ctrl+Z can take back, newest
  first, in words ("Q7 'Bell': Fade In 2 → 0"); "Undo back to here" takes
  back that step and all after it.
- File → "Restore a backup…": the cue list of one of the copies the
  program keeps at every save (5.6), as one step Ctrl+Z can take back.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QDialogButtonBox, QListWidget

from ui.main_window._common import *  # noqa: F403,F401,F405


def change_text(change) -> str:
    """One undo step in words."""
    from engine.undo_names import FIELD_LABELS

    who = f"{change.q} '{change.name}'".strip() if change.q else f"'{change.name}'"
    field = tr(FIELD_LABELS.get(change.field, change.field)) if change.field else ""
    if change.kind == "added":
        return tr("Aggiunte {} cue ({}…)").format(change.count, who) if change.count > 1 else \
            tr("Aggiunta {}").format(who)
    if change.kind == "removed":
        return tr("Eliminate {} cue ({}…)").format(change.count, who) if change.count > 1 else \
            tr("Eliminata {}").format(who)
    if change.kind == "replaced":
        return tr("Cue sostituite ({}…)").format(who)
    if change.kind == "moved":
        return tr("Ordine cambiato ({}…)").format(who)
    if change.kind == "field":
        return f"{who}: {field} {change.old} → {change.new}"
    if change.kind == "fields":
        return tr("{}: {} campi ({})").format(who, change.count, change.field)
    if change.kind == "many":
        return tr("{} cue cambiate: {}").format(change.count, field) if field else \
            tr("{} cue cambiate").format(change.count)
    return tr("Nessuna differenza nella lista")


class _HistoryMixin:
    def _undo_steps_text(self) -> list[str]:
        """Newest first."""
        from engine.undo_names import describe

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        return [change_text(describe(before["cues"], after["cues"]))
                for before, after in reversed(self._undo.steps())]

    def _open_history(self) -> None:
        if not self._change_allowed(UNDO):
            return
        if self._current_mode() == "rehearsal":
            self._status_label.setText(tr("Nella prova Ctrl+Z annulla l'ultima correzione; ripeti in preparazione"))
            return
        texts = self._undo_steps_text()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Storia delle modifiche"))
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("Le modifiche che Ctrl+Z può annullare, la più recente in alto:")))
        listing = QListWidget()
        for i, text in enumerate(texts, start=1):
            listing.addItem(f"{i}. {text}")
        if not texts:
            listing.addItem(tr("Nessuna modifica da annullare"))
            listing.setEnabled(False)
        listing.setCurrentRow(0)
        lay.addWidget(listing, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        back = buttons.addButton(tr("↶ Annulla fino a qui (compresa)"), QDialogButtonBox.ButtonRole.AcceptRole)
        back.setEnabled(bool(texts))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        listing.itemDoubleClicked.connect(lambda _item: dlg.accept())
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted or not texts:
            return
        self._undo_steps(listing.currentRow() + 1)

    def _undo_steps(self, count: int) -> None:
        for _ in range(max(0, count)):
            if not self._undo.can_undo:
                break
            self._on_undo()
        self._status_label.setText(tr("Annullate {} modifiche (Ctrl+Y le ripete)").format(count))

    # ── A backup put back ──
    def _restore_backup(self) -> None:
        """The saved file, a backup copy or a session set aside - in the window of 5.6 (``_show_diary``)."""
        self._restore_saved_version()
