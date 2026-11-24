"""The "Edit cue" window from the cue list (teacher-workflow evaluation, 2026-11-24).

A double-click on a row (not on the GO column), Enter on the list, the
"✏ Edit…" button under it or the row menu open ``EditCueDialog`` on that
cue in every view; OK writes the changed fields as one undo step.
"""

from __future__ import annotations

from i18n import tr
from ui.main_window._common import *  # noqa: F403,F401,F405


class _EditCueMixin:
    """Opens the edit window and saves what it changed."""

    def _edit_cue_setup(self) -> None:
        self._cue_list.edit_requested.connect(lambda: self._open_cue_editor())
        self._cue_list_panel.edit_cue_requested.connect(lambda: self._open_cue_editor())

    def _open_cue_editor(self, row: int | None = None) -> bool:
        """Open the window on *row* (default: the selected cue); True when something was saved."""
        from engine.show_mode import EDIT_CUE
        from ui.edit_cue_dialog import EditCueDialog

        if row is None:
            row = self._cue_list.currentRow()
        if not (0 <= row < len(self._cues)):
            self._status_label.setText(tr("Scegli prima una cue nella lista"))
            return False
        if not self._change_allowed(EDIT_CUE):
            return False
        cue = self._cues[row]
        test_player = getattr(self, "_test_player", None)
        if test_player is not None and test_player.is_playing():
            test_player.pause()   # one sound at a time: the window has its own preview
        path = os.path.abspath(cue.file_path) if cue.file_path else ""
        if cue.media_type in (MediaType.AUDIO, MediaType.VIDEO) and path and os.path.isfile(path):
            self._request_waveform(cue)
        device_mgr = getattr(self, "_device_mgr", None)
        dlg = EditCueDialog(
            cue,
            peaks_provider=lambda: self._waveform_cache.get(path) if path else None,
            audio_device=getattr(device_mgr, "_monitor_device", None) if device_mgr is not None else None,
            edit_text=self._ask_text_spec,
            parent=self,
        )
        if self._q_locked() and (cue.q_label or "").strip() and hasattr(dlg, "ed_q"):
            dlg.ed_q.setReadOnly(True)  # 5.2: the script is approved, its labels stay
            dlg.ed_q.setToolTip(tr("Q bloccata: il copione è approvato (menu Modifica)"))
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        changes = dlg.changes() if accepted else {}
        dlg.deleteLater()
        if "q_label" in changes and self._q_label_blocked(cue, changes["q_label"]):
            changes.pop("q_label")
        if not changes:
            return False
        self._apply_cue_changes(cue, changes)
        return True

    def _on_add_scene_interactive(self) -> None:
        """"+ Scene" and Ctrl+G: make the scene, then its name and how it plays in the edit window (#12)."""
        before = {c.cue_id for c in self._cues}
        self._on_add_group()
        row = next((i for i, c in enumerate(self._cues)
                    if c.cue_id not in before and c.media_type == MediaType.GROUP), None)
        if row is not None:
            self._open_cue_editor(row)

    def _ask_text_spec(self, spec: dict) -> dict | None:
        from ui.text_cue_dialog import TextCueDialog

        dlg = TextCueDialog(spec, self)
        return dlg.spec() if dlg.exec() == QDialog.DialogCode.Accepted else None

    def _apply_cue_changes(self, cue: Cue, changes: dict) -> None:
        """Write the window's fields into *cue*: one undo step, list and inspector refreshed."""
        from engine.text_render import render_text_png, text_cue_name

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        spec = changes.pop("text_spec", None)
        if spec is not None:
            try:
                cue.file_path = render_text_png(spec)
            except OSError as exc:
                QMessageBox.warning(self, tr("Cue di testo"), str(exc))
            else:
                if "name" not in changes and cue.name == text_cue_name(cue.text_spec):
                    cue.name = text_cue_name(spec)
                cue.text_spec = spec
        for field_name, value in changes.items():
            setattr(cue, field_name, value)
        self._commit_undo_point()
        self._mark_modified(True)
        self._refresh_cue_list(keep_selection=True)
        self._last_selection_sig = None
        self._sync_selection_state()  # the inspector shows the new values (never writes the old ones back)
        if hasattr(self, "_sync_live_view"):
            self._sync_live_view()
        self._status_label.setText(tr("'{}' modificata").format(cue.name))
        self._auto_save()
