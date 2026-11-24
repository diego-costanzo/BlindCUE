"""Q labels locked and relative changes for several cues (stage 5, item 5.2) mixin for MainWindow.

- Edit → "Lock the Q labels (script approved)": a label that is there can
  no longer be changed (inspector, the list, the "Edit cue" window,
  renumbering, the AI assistant); an empty label may still be filled in.
  Saved with the show (in the show info block).
- Edit → "Change the selected cues…": ±dB, ±seconds of fades and delays,
  each cue keeps its own value and moves by the same step; a preview first,
  then one Ctrl+Z.
"""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405

LOCK_KEY = "q_locked"


class _BulkChangeMixin:
    # ── Q labels locked ──
    def _q_locked(self) -> bool:
        return bool(getattr(self, "_show_info", {}).get(LOCK_KEY))

    def _set_q_locked(self, locked: bool) -> None:
        info = dict(getattr(self, "_show_info", {}))
        if bool(info.get(LOCK_KEY)) == bool(locked):
            return
        info[LOCK_KEY] = "1" if locked else ""
        self._show_info = info
        self._mark_modified(True)
        act = getattr(self, "_act_q_lock", None)
        if act is not None and act.isChecked() != bool(locked):
            act.blockSignals(True)
            act.setChecked(bool(locked))
            act.blockSignals(False)
        self._apply_q_lock_to_inspector()
        self._status_label.setText(tr("Q bloccate: il copione è approvato") if locked else tr("Q sbloccate"))

    def _sync_q_lock_action(self) -> None:
        """The menu tick follows the show (a show was opened, restored, made new)."""
        act = getattr(self, "_act_q_lock", None)
        if act is not None and act.isChecked() != self._q_locked():
            act.blockSignals(True)
            act.setChecked(self._q_locked())
            act.blockSignals(False)

    def _q_label_blocked(self, cue: Cue | None, new_label: str) -> bool:
        """True (and says why) when *new_label* would replace a locked label of *cue*."""
        from engine.bulk_change import locked_change

        if cue is None or not locked_change(cue.q_label, new_label, self._q_locked()):
            return False
        self._status_label.setText(tr("Le Q sono bloccate (copione approvato): sbloccale nel menu Modifica"))
        self.announce(self._status_label.text(), assertive=True)
        return True

    def _apply_q_lock_to_inspector(self) -> None:
        """Read-only Q fields in the inspector while the shown cue has a locked label."""
        self._sync_q_lock_action()
        insp = getattr(self, "_inspector", None)
        if insp is None:
            return
        sel = self._selected_cues() if hasattr(self, "_cue_list") else []
        locked = self._q_locked() and any((c.q_label or "").strip() for c in sel)
        tips = getattr(self, "_q_field_tips", None)  # the fields' own tooltips, put back on unlock
        if tips is None:
            tips = self._q_field_tips = {}
        for name in ("edit_cue_q", "edit_group_q"):
            field = getattr(insp, name, None)
            if field is None:
                continue
            tips.setdefault(name, field.toolTip())
            if field.isReadOnly() != locked:
                field.setReadOnly(locked)
                field.setToolTip(tr("Q bloccata: il copione è approvato (menu Modifica)") if locked else tips[name])

    # ── Relative changes ──
    def _open_bulk_change(self) -> None:
        from engine import bulk_change as bc
        from engine.show_mode import EDIT_LIST

        from ui.bulk_change_dialog import BulkChangeDialog

        if not self._change_allowed(EDIT_LIST):
            return
        rows = self._selected_rows()
        if not rows:
            self._status_label.setText(tr("Seleziona prima le cue da cambiare"))
            return
        self._apply_inspector_to_cue()  # what is typed in the inspector first, so it is not lost
        dlg = BulkChangeDialog(self._cues, rows, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        steps = dlg.steps()
        if not steps:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        changed = bc.apply(self._cues, steps)
        self._commit_undo_point()  # one Ctrl+Z
        self._mark_modified(True)
        self._refresh_cue_list(keep_selection=True)
        # The inspector shows the new values: otherwise the next save writes the old ones back.
        self._last_selection_sig = None
        self._sync_selection_state()
        for cue in {self._cues[s.row].cue_id: self._cues[s.row] for s in steps}.values():
            if cue.status == CueStatus.LIVE:
                self.live_automation_updated.emit(cue)
        self._auto_save()
        self._status_label.setText(tr("Cambiate {} cue (Ctrl+Z annulla)").format(changed))
