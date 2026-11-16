"""Cue List Manipulation mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _CueManipMixin:
    def _on_add_media(self, media_type: MediaType) -> None:
        ext_map = {
            MediaType.VIDEO: "Video (*.mp4 *.mkv *.avi *.mov *.webm)",
            MediaType.AUDIO: "Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)",
            MediaType.IMAGE: "Image (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        }
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Add {media_type.value}", "", ext_map.get(media_type, "All Files (*)")
        )
        if file_path:
            self._add_cue_from_file(file_path, media_type)

    def _add_cue_from_file(self, file_path: str, media_type: MediaType | None = None) -> None:
        if media_type is None:
            media_type = self._detect_media_type(file_path)
        if media_type is None:
            QMessageBox.warning(self, "Unsupported File", f"Cannot determine media type for:\n{file_path}")
            return

        cue = Cue(name=os.path.basename(file_path), media_type=media_type, file_path=file_path)
        errors = cue.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.status = CueStatus.LOADED
        self._cues.append(cue)
        self._refresh_cue_list()
        self._cue_list.setCurrentRow(len(self._cues) - 1)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Added: {cue}")
        self._auto_save()
        logger.info("Added cue: %s", cue)

    @Slot(str)
    def _on_file_dropped(self, file_path: str) -> None:
        self._add_cue_from_file(file_path)

    def _move_selected_cue(self, delta: int) -> None:
        sel_rows = self._selected_rows()
        if len(sel_rows) != 1:
            return
        row = sel_rows[0]
        target_row = row + delta
        if not (0 <= row < len(self._cues) and 0 <= target_row < len(self._cues)):
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()

        moving_cue = self._cues[row]
        target_cue = self._cues[target_row]

        # Extract if moving past group boundaries
        if delta < 0 and moving_cue.parent_id == target_cue.cue_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sopra la scena)")
        elif delta > 0 and moving_cue.parent_id is not None and target_cue.parent_id != moving_cue.parent_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sotto la scena)")

        self._cues[row], self._cues[target_row] = self._cues[target_row], self._cues[row]
        self._current_index = target_row
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._sync_inspector_header_and_text(target_row, self._cues[target_row])
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    @Slot()
    def _on_move_up(self) -> None:
        if self._live_mode:
            return
        self._move_selected_cue(-1)

    @Slot()
    def _on_move_down(self) -> None:
        if self._live_mode:
            return
        self._move_selected_cue(1)

    @Slot()
    def _on_delete_cue(self) -> None:
        if self._live_mode:
            return
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        anchor_row, _ = self._anchor_row_and_cue()
        self._undo.update_current_index(anchor_row)

        removed = [self._cues.pop(r) for r in sorted(sel_rows, reverse=True)]
        for rem in removed:
            if rem.media_type == MediaType.GROUP:
                for c in self._cues:
                    if c.parent_id == rem.cue_id:
                        c.parent_id = None
        first_row = sel_rows[0]
        self._refresh_cue_list(keep_selection=False)
        if self._cues:
            self._cue_list.setCurrentRow(min(first_row, len(self._cues) - 1))
        else:
            self._current_index = -1
            self._reset_idle_preview_ui()
            self._update_inspector(None)
        self._commit_undo_point()
        self._mark_modified(True)
        if len(removed) == 1:
            rem = removed[0]
            self._status_label.setText(
                f"Deleted: {format_cue_ref(first_row, rem)} '{rem.name}' (Ctrl+Z per ripristinare)"
            )
        else:
            self._status_label.setText(
                f"Eliminate {len(removed)} cue selezionate (Ctrl+Z per ripristinare)"
            )
        self._auto_save()
        logger.info("Deleted %d cue(s)", len(removed))
