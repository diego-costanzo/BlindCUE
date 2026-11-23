"""Undo / Redo Integration mixin for MainWindow."""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _UndoRedoMixin:
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Route Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y to Cue Undo/Redo unless mid-typing in QLineEdit."""
        if event.type() == QEvent.Type.KeyPress and hasattr(obj, "window") and obj.window() is self:
            if isinstance(obj, QLineEdit):
                is_inline = (
                    hasattr(self, "_cue_list")
                    and self._cue_list.state() == QAbstractItemView.State.EditingState
                )
                mid_typing = is_inline or self._undo.is_debounce_active()
                if event.matches(QKeySequence.StandardKey.Undo):
                    if mid_typing and obj.isUndoAvailable():
                        return False
                    self._on_undo()
                    return True
                if (
                    event.matches(QKeySequence.StandardKey.Redo)
                    or (event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier)
                ):
                    if mid_typing and obj.isRedoAvailable():
                        return False
                    self._on_redo()
                    return True
        return super().eventFilter(obj, event)

    def _current_row_or_index(self) -> int:
        return self._cue_list.currentRow() if hasattr(self, "_cue_list") else self._current_index

    def _on_undo_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        if hasattr(self, "_act_undo"):
            self._act_undo.setEnabled(can_undo)
        if hasattr(self, "_act_redo"):
            self._act_redo.setEnabled(can_redo)

    def _schedule_undo_point(self) -> None:
        self._undo.schedule_commit()

    @Slot()
    def _commit_undo_point(self) -> None:
        self._undo.commit(self._cues, self._current_row_or_index())

    def _reset_undo_history(self) -> None:
        self._undo.reset(self._cues, self._current_row_or_index())

    def _restore_snapshot(self, snapshot: dict) -> None:
        """Restore cues and settings from a snapshot without interrupting LIVE playback."""
        self._undo.restoring = True
        try:
            self._undo.stop_debounce()

            live_ids = {c.cue_id for c in self._cues if c.status == CueStatus.LIVE}
            prev_row = self._cue_list.currentRow()
            prev_cue_id = self._cues[prev_row].cue_id if 0 <= prev_row < len(self._cues) else None
            prev_file = self._cues[prev_row].file_path if 0 <= prev_row < len(self._cues) else None

            restored: list[Cue] = []
            for raw in snapshot.get("cues", []):
                cue = Cue.from_dict(raw)
                if cue.cue_id in live_ids:
                    cue.status = CueStatus.LIVE
                elif raw.get("status") == CueStatus.OFFLINE.value:
                    cue.status = CueStatus.OFFLINE
                else:
                    cue.status = CueStatus.LOADED
                restored.append(cue)

            self._cues = restored
            target_row = int(snapshot.get("current_index", -1))
            if restored and not (0 <= target_row < len(restored)):
                target_row = min(max(0, prev_row), len(restored) - 1)
            elif not restored:
                target_row = -1

            self._current_index = target_row
            self._last_selection_sig = None
            self._refresh_cue_list(keep_selection=False, select_row=target_row)

            if 0 <= target_row < len(self._cues):
                cue = self._cues[target_row]
                same_cue = (cue.cue_id == prev_cue_id and cue.file_path == prev_file)
                self._update_inspector(cue)
                self._update_cue_readouts(target_row, cue)

                if same_cue:
                    self._render_cue_in_preview(cue, load_image=True)
                    self._sync_timeline_for_cue(cue)
                    self.live_automation_updated.emit(cue)
                    if self._live_mirror_active:
                        self._mirror_active_cue_to_live()
                else:
                    self._on_cue_selected(target_row)
            else:
                self._reset_idle_preview_ui()
                self._update_inspector(None)

            for c in self._cues:
                if c.status == CueStatus.LIVE:
                    self._update_live_layer_label(c)

            self._undo.set_committed_state(self._cues, self._current_row_or_index())
            self._mark_modified(True)
            self._auto_save()
        finally:
            self._undo.restoring = False
            self._on_undo_history_changed(self._undo.can_undo, self._undo.can_redo)

    @Slot()
    def _on_undo(self) -> None:
        if not self._change_allowed(UNDO):
            return
        if self._current_mode() == "rehearsal":
            self._undo_last_rehearsal_change()  # never a whole snapshot in the rehearsal (M6)
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        prev = self._undo.pop_undo(self._cues, self._current_row_or_index())
        if prev is None:
            self._status_label.setText("Nessuna operazione da annullare")
            return
        self._restore_snapshot(prev)
        self._status_label.setText(
            f"↶ Annulla (Ctrl+Z) — Stato precedente ripristinato ({len(self._undo._undo_stack)} nel registro)"
        )

    @Slot()
    def _on_redo(self) -> None:
        if not self._change_allowed(UNDO):
            return
        if self._current_mode() == "rehearsal":
            self._status_label.setText(tr("Nella prova Ctrl+Z annulla l'ultima correzione; ripeti in preparazione"))
            return
        nxt = self._undo.pop_redo(self._cues, self._current_row_or_index())
        if nxt is None:
            self._status_label.setText("Nessuna operazione da ripetere")
            return
        self._restore_snapshot(nxt)
        self._status_label.setText(
            f"↷ Ripeti — Modifica ripristinata ({len(self._undo._redo_stack)} ripetibili)"
        )

    def _update_window_title(self) -> None:
        name = Path(self._current_project_path).name if self._current_project_path else "Nuovo Show"
        mod = " *" if self._is_modified else ""
        from version import APP_VERSION
        self.setWindowTitle(f"BlindCue – [{name}{mod}] – Director Panel v{APP_VERSION}")

    def _mark_modified(self, modified: bool = True) -> None:
        self._is_modified = modified
        self._update_window_title()
