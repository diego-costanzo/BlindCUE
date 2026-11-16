"""Group Cues & Scene Containers mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _GroupsMixin:
    @Slot()
    def _on_add_group(self) -> None:
        """Create a new Group cue, wrapping any selected cues or inserting an empty group."""
        if self._live_mode:
            return
        sel_rows = self._selected_rows()
        sel_cues = [self._cues[r] for r in sel_rows if self._cues[r].media_type != MediaType.GROUP]

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        group_color = sel_cues[0].color if (sel_cues and sel_cues[0].color) else "#6366f1"
        group_cue = Cue(
            name="Nuova Scena / Gruppo",
            file_path="",
            media_type=MediaType.GROUP,
            group_mode=GroupMode.STEP.value,
            color=group_color,
            layer=1,
            collapsed=False,
            status=CueStatus.LOADED,
        )

        if sel_cues:
            insert_pos = min(sel_rows)
            # Remove sel_cues from self._cues
            remaining_cues = [c for c in self._cues if c not in sel_cues]
            # Set parent_id on all sel_cues
            for c in sel_cues:
                c.parent_id = group_cue.cue_id
            # Reconstruct list with group_cue and its children placed contiguously
            new_cues = remaining_cues[:insert_pos] + [group_cue] + sel_cues + remaining_cues[insert_pos:]
            self._cues = new_cues
            target_row = insert_pos
        else:
            curr = self._cue_list.currentRow()
            target_row = curr + 1 if 0 <= curr < len(self._cues) else len(self._cues)
            self._cues.insert(target_row, group_cue)

        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Creato Gruppo Scena: '{group_cue.name}'")
        self._auto_save()
        logger.info("[GROUP] Created group #%d '%s'", group_cue.cue_id, group_cue.name)

    @Slot()
    def _ungroup_selected(self) -> None:
        """Dissolve the selected group (or parent of selected child), returning cues to root."""
        if self._live_mode:
            return
        anchor_row, cue = self._anchor_row_and_cue()
        if cue is None:
            return

        target_group: Cue | None = None
        if cue.media_type == MediaType.GROUP:
            target_group = cue
        elif cue.parent_id is not None:
            target_group = next((c for c in self._cues if c.cue_id == cue.parent_id), None)

        if target_group is None:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        # Detach children
        for c in self._cues:
            if c.parent_id == target_group.cue_id:
                c.parent_id = None

        # Remove group cue
        if target_group in self._cues:
            idx = self._cues.index(target_group)
            self._cues.remove(target_group)
            target_row = min(idx, len(self._cues) - 1)
        else:
            target_row = max(0, len(self._cues) - 1)

        self._refresh_cue_list(keep_selection=False)
        if 0 <= target_row < len(self._cues):
            self._cue_list.setCurrentRow(target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Sciolto Gruppo: '{target_group.name}'")
        self._auto_save()
        logger.info("[GROUP] Ungrouped group #%d", target_group.cue_id)

    @Slot(int)
    def _toggle_group_collapsed(self, row: int) -> None:
        """Toggle collapse/expand for the group at *row*."""
        if not (0 <= row < len(self._cues)):
            return
        cue = self._cues[row]
        if cue.media_type != MediaType.GROUP:
            return

        cue.collapsed = not cue.collapsed

        # Apply visibility to both tables
        for r, c in enumerate(self._cues):
            if c.parent_id == cue.cue_id:
                self._cue_list.setRowHidden(r, cue.collapsed)
                if hasattr(self, "_live_show_panel") and self._live_show_panel is not None:
                    self._live_show_panel.live_table.setRowHidden(r, cue.collapsed)

        # Update table row data
        it_num = self._cue_list.item(row, 0)
        if it_num:
            it_num.setData(ROLE_GROUP_COLLAPSED, cue.collapsed)
        it_name = self._cue_list.item(row, 2)
        if it_name:
            it_name.setData(ROLE_GROUP_COLLAPSED, cue.collapsed)
        self._cue_list.viewport().update()

        # Update button text in inspector if group is active
        if self._selected_cue() is cue:
            if cue.collapsed:
                self._inspector.btn_group_collapse_toggle.setText("▼ Espandi Gruppo in Scaletta")
            else:
                self._inspector.btn_group_collapse_toggle.setText("▶ Collassa Gruppo in Scaletta")

        self._sync_live_view()

    @Slot()
    def _toggle_group_collapse_from_inspector(self) -> None:
        anchor_row, cue = self._anchor_row_and_cue()
        if cue and cue.media_type == MediaType.GROUP:
            self._toggle_group_collapsed(anchor_row)

    @Slot(int)
    def _on_remove_child_from_group(self, child_cue_id: int) -> None:
        """Remove a child cue from its parent group and place it outside."""
        child = next((c for c in self._cues if c.cue_id == child_cue_id), None)
        if child is None or child.parent_id is None:
            return
        parent_group = next((c for c in self._cues if c.cue_id == child.parent_id), None)
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        child.parent_id = None
        if parent_group is not None:
            siblings = [c for c in self._cues if c.parent_id == parent_group.cue_id and c != child]
            self._cues.remove(child)
            if siblings:
                last_sibling_idx = self._cues.index(siblings[-1])
                self._cues.insert(last_sibling_idx + 1, child)
            else:
                p_idx = self._cues.index(parent_group)
                self._cues.insert(p_idx + 1, child)
        target_row = self._cues.index(child)
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._commit_undo_point()
        self._mark_modified(True)
        anchor_row, group_cue = self._anchor_row_and_cue()
        if group_cue and group_cue.media_type == MediaType.GROUP:
            children = [c for c in self._cues if c.parent_id == group_cue.cue_id]
            self._inspector.load_group_children(children, group_cue)
        self._status_label.setText(f"Estratta cue '{child.name}' dal gruppo (spostata all'esterno)")

    @Slot()
    def _extract_selected_from_group(self) -> None:
        """Extract the selected cue(s) from their parent group."""
        sel_cues = [c for c in self._selected_cues() if c.parent_id is not None]
        if not sel_cues:
            anchor_row, cue = self._anchor_row_and_cue()
            if cue and cue.parent_id is not None:
                sel_cues = [cue]
        if not sel_cues:
            return
        for c in sel_cues:
            self._on_remove_child_from_group(c.cue_id)

    @Slot()
    def _on_ctrl_shift_g(self) -> None:
        """Ungroup if group is selected, or extract if child cue is selected."""
        anchor_row, cue = self._anchor_row_and_cue()
        if cue is None:
            return
        if cue.media_type == MediaType.GROUP:
            self._ungroup_selected()
        elif cue.parent_id is not None:
            self._extract_selected_from_group()

    @Slot(str)
    def _set_group_mode(self, mode: str) -> None:
        """Update group execution mode across selected group cue(s)."""
        sel_cues = [c for c in self._selected_cues() if c.media_type == MediaType.GROUP]
        if not sel_cues:
            anchor_row, cue = self._anchor_row_and_cue()
            if cue and cue.media_type == MediaType.GROUP:
                sel_cues = [cue]
        if not sel_cues:
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()

        for c in sel_cues:
            c.group_mode = mode

        self._refresh_rows_in_place(list(range(len(self._cues))))
        anchor_row, cue = self._anchor_row_and_cue()
        if cue:
            self._inspector.set_layer_conflict(self._layer_conflicts.get(cue.cue_id))
        self._commit_undo_point()
        self._mark_modified(True)
        self._sync_live_view()
        self._status_label.setText(f"Modalità Gruppo impostata a: {mode}")

    @Slot()
    def _on_open_group_timeline(self) -> None:
        """Open the dedicated 3-layer Studio Timeline Arranger Dialog for the selected group."""
        if self._live_mode:
            return
        anchor_row, cue = self._anchor_row_and_cue()
        if not cue:
            return
        group_cue = (
            cue if cue.media_type == MediaType.GROUP
            else next((c for c in self._cues if c.cue_id == cue.parent_id), None)
        )
        if not group_cue or group_cue.media_type != MediaType.GROUP:
            return

        child_cues = [c for c in self._cues if c.parent_id == group_cue.cue_id]
        if not child_cues:
            QMessageBox.information(
                self,
                "Studio Timeline Gruppo",
                f"Il gruppo '{group_cue.name}' non contiene ancora file multimediali.\n\n"
                "Aggiungi prima delle tracce audio, video o immagini al gruppo nella scaletta principale\n"
                "per poterle allineare e sincronizzare sulla timeline a 3 layer.",
            )
            return

        dialog = GroupTimelineStudioDialog(group_cue, child_cues, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._commit_undo_point()
            self._mark_modified(True)
            self._refresh_cue_list(keep_selection=True)
            self._update_inspector(group_cue)
            self._status_label.setText(
                f"Studio Timeline: Gruppo '{group_cue.name}' sincronizzato con successo ({len(child_cues)} file allineati sui layer)"
            )
