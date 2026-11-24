"""Renumber the Q labels (stage 5, item 5.2) mixin for MainWindow: Edit → "Renumber the Q…"."""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _RenumberMixin:
    def _renumber_q(self) -> None:
        from engine import renumber
        from engine.show_mode import EDIT_LIST
        from ui.renumber_dialog import RenumberDialog

        if not self._change_allowed(EDIT_LIST):
            return
        self._apply_inspector_to_cue()  # what is typed in the inspector first, so it is not lost
        chosen = self._selected_rows() if len(self._selected_rows()) > 1 else []
        dlg = RenumberDialog(self._cues, chosen, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        changed = renumber.apply(self._cues, dlg.changes())
        if changed:
            self._commit_undo_point()
            self._mark_modified(True)
            self._refresh_cue_list(keep_selection=True)
            # The inspector shows the new Q: otherwise the next save writes the old one back.
            self._last_selection_sig = None
            self._sync_selection_state()
        self._status_label.setText(tr("Q rinumerate: {}").format(changed))
