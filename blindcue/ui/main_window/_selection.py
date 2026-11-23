"""Selection & Live Mirror mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _SelectionMixin:
    def _output_for_cue(self, cue: Cue):
        """Return the OutputWindow that renders *cue* (output A or B)."""
        target = resolve_output_target(
            getattr(cue, "output_target", "A"), self._dual_output_active
        )
        if target == "B" and self._output_b is not None:
            return self._output_b
        return self._output

    @Slot(int)
    def _on_cue_selected(self, _row: int) -> None:
        self._sync_selection_state()

    @Slot()
    def _on_cue_selection_changed(self) -> None:
        self._sync_selection_state()

    def _sync_selection_state(self) -> None:
        """Update Inspector, Standby badges, Pre-Viz, and Waveform for 0, 1, or N selected cues."""
        if self._updating_cue_list:
            return
        if not self._undo.restoring and self._undo.is_debounce_active():
            self._commit_undo_point()

        sel_rows = self._selected_rows()
        anchor_row, cue = self._anchor_row_and_cue()
        sig = (tuple(sel_rows), anchor_row, cue.cue_id if cue else None)
        if sig == self._last_selection_sig:
            return
        prev_anchor_id = self._last_selection_sig[2] if self._last_selection_sig else None
        self._last_selection_sig = sig

        if cue is not None and 0 <= anchor_row < len(self._cues):
            self._current_index = anchor_row
            self._undo.update_current_index(anchor_row)
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))

            sel_cues = [self._cues[r] for r in sel_rows]
            self._update_crop_reference_for_cue(cue)
            self._inspector.load_selection(sel_cues, anchor_cue=cue, anchor_row=anchor_row)
            if cue.media_type == MediaType.GROUP:
                children = [c for c in self._cues if c.parent_id == cue.cue_id]
                self._inspector.load_group_children(children, cue)

            if cue.cue_id != prev_anchor_id:
                self._img_previz_timer.stop()
                self._img_previz_elapsed = 0.0
                self._active_section_idx = -1
                self._waveform_panel.reset_zoom()
                self._request_waveform(cue)
                if cue.media_type == MediaType.IMAGE:
                    dur_img = cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
                    self._active_test_duration = dur_img
                    self._sync_timeline_for_cue(cue)
                    self.set_waveform_playhead_seconds(0.0, dur_img, "PRE-VIZ")
                else:
                    self._active_test_duration = 0.0
                    self.set_waveform_playhead_seconds(None, 0.0)
                if cue.media_type == MediaType.VIDEO:
                    self._preview_monitor.clear_video_frame()
                self._render_cue_in_preview(cue, load_image=False)
                self.cue_preview_requested.emit(cue)

            self._sync_timeline_for_cue(cue)
            self._update_cue_readouts(anchor_row, cue)
            if len(sel_cues) > 1:
                mtypes = {c.media_type for c in sel_cues}
                if len(mtypes) == 1:
                    self._lbl_cue_standby.setText(
                        f"Selezione: {len(sel_cues)} {cue.media_type.value}"
                    )
                else:
                    self._lbl_cue_standby.setText(f"Selezione mista: {len(sel_cues)} cue")

            if self._live_mirror_active:
                self._mirror_active_cue_to_live()

            modes = {c.follow_mode for c in sel_cues}
            self._cue_list_panel.set_follow_mode_checked(
                next(iter(modes)) if len(modes) == 1 else None, enabled=True
            )
            self._sync_live_view()

            logger.debug("Cue selected (count=%d): %s", len(sel_cues), cue)
        else:
            self._inspector.load_cue(None)
            self._cue_list_panel.set_follow_mode_checked(FollowMode.MANUAL.value, enabled=False)
            self._reset_idle_preview_ui()
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._sync_live_view()

    @Slot(object)
    def _on_preview_video_frame_for_mirror(self, _frame) -> None:
        if not self._live_mirror_active:
            return
        cue = self._selected_cue()
        if cue is not None and cue.media_type == MediaType.VIDEO and cue.status != CueStatus.LIVE:
            self._push_cue_to_output(cue)

    def _push_cue_to_output(self, cue: Cue) -> None:
        """Render an IMAGE or VIDEO cue onto its assigned output layer (mirror-safe)."""
        out = self._output_for_cue(cue)
        surf_id = getattr(cue, "surface_id", "default") or "default"
        if cue.media_type == MediaType.IMAGE:
            out.show_image(
                cue.layer,
                cue.file_path,
                opacity=cue.opacity,
                crop=cue.crop,
                scale=cue.scale,
                pos_x=cue.position_x,
                pos_y=cue.position_y,
                aspect_ratio=cue.aspect_ratio,
                surface_id=surf_id,
                rotation=cue.rotation,
                mask_polygon=cue.mask_polygon,
                mask_feather=cue.mask_feather,
            )
        elif cue.media_type == MediaType.VIDEO:
            if cue.status == CueStatus.LIVE:
                out.ensure_live_video_visible(
                    layer=cue.layer,
                    scale=cue.scale,
                    crop=cue.crop,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    opacity=cue.opacity,
                    aspect_ratio=cue.aspect_ratio,
                    surface_id=surf_id,
                    rotation=cue.rotation,
                )
            else:
                frame_img = self._preview_monitor.current_video_frame()
                if frame_img is not None and not frame_img.isNull():
                    # Keep standby/Pre-Viz preview opacity synced when playing fades
                    op = (
                        self._preview_monitor._opacity
                        if self._preview_monitor._active_media_type == MediaType.VIDEO
                        else cue.opacity
                    )
                    out.show_mirrored_frame(
                        cue.layer,
                        frame_img,
                        opacity=op,
                        crop=cue.crop,
                        scale=cue.scale,
                        pos_x=cue.position_x,
                        pos_y=cue.position_y,
                        aspect_ratio=cue.aspect_ratio,
                        surface_id=surf_id,
                        rotation=cue.rotation,
                    )
                else:
                    # Wait for decoded Pre-Viz frame rather than flashing black video surface
                    has_live_on_layer = any(
                        c.status == CueStatus.LIVE
                        and self._same_runtime_layer(c, cue)
                        and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                        for c in self._cues
                    )
                    if not has_live_on_layer:
                        out.clear_layer(cue.layer)
        elif cue.media_type == MediaType.AUDIO:
            has_live_visual = any(
                c.status == CueStatus.LIVE
                and self._same_runtime_layer(c, cue)
                and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                for c in self._cues
            )
            if not has_live_visual:
                out.clear_layer(cue.layer)

    def _runtime_slot(self, cue: Cue) -> int:
        """Runtime layer 1-6 actually used by *cue* under the current output mode."""
        return runtime_layer(
            cue.layer,
            resolve_output_target(getattr(cue, "output_target", "A"), self._dual_output_active),
        )

    def _same_runtime_layer(self, first: Cue, second: Cue) -> bool:
        """True when both cues play on the same physical output layer (A/B aware)."""
        return self._runtime_slot(first) == self._runtime_slot(second)

    @Slot(bool)
    def _on_live_mirror_toggled(self, active: bool) -> None:
        self._live_mirror_active = active
        if hasattr(self, "_variant"):
            self._update_variant_status_bar()
        self._preview_panel.set_live_mirror_style(active)
        if active:
            self._status_label.setText(
                "PROGETTAZIONE: LIVE MIRROR ATTIVO (Modifiche visibili sullo schermo esterno)"
            )
            self._mirror_active_cue_to_live()
        else:
            self._status_label.setText(
                "LIVE MIRROR DISATTIVATO — Anteprima isolata (Pronto per lo spettacolo)"
            )
            self._restore_live_output()

    def _mirror_active_cue_to_live(self) -> None:
        cue = self._selected_cue()
        if not cue or not self._live_mirror_active:
            return
        try:
            out = self._output_for_cue(cue)
            target = resolve_output_target(cue.output_target, self._dual_output_active)
            prev = self._last_mirrored_layer
            if prev is not None and prev[:2] != (out, cue.layer):
                prev_out, prev_layer, prev_target = prev
                key = runtime_layer(prev_layer, prev_target)
                live_on_prev = next(
                    (
                        c for c in self._cues
                        if c.status == CueStatus.LIVE
                        and self._runtime_slot(c) == key
                    ),
                    None,
                )
                if live_on_prev is None:
                    prev_out.clear_layer(prev_layer)
                else:
                    self._push_cue_to_output(live_on_prev)

            self._last_mirrored_layer = (out, cue.layer, target)
            self._push_cue_to_output(cue)
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error mirroring cue: %s", exc)

    def _restore_live_output(self) -> None:
        try:
            prev = self._last_mirrored_layer
            self._last_mirrored_layer = None
            live_cues = [c for c in self._cues if c.status == CueStatus.LIVE]
            if not live_cues:
                self._output.show_fallback()
                if self._output_b is not None:
                    self._output_b.show_fallback()
            elif prev is not None:
                prev_out, prev_layer, prev_target = prev
                key = runtime_layer(prev_layer, prev_target)
                live_on_prev = next(
                    (
                        c for c in live_cues
                        if self._runtime_slot(c) == key
                        and c.media_type in (MediaType.IMAGE, MediaType.VIDEO)
                    ),
                    None,
                )
                if live_on_prev is None:
                    prev_out.clear_layer(prev_layer)
                else:
                    self._push_cue_to_output(live_on_prev)
            else:
                self._output.clear_all_layers()
                if self._output_b is not None:
                    self._output_b.clear_all_layers()
                for c in live_cues:
                    self._push_cue_to_output(c)
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error restoring live output: %s", exc)

    @Slot(int)
    def _set_layer(self, layer: int) -> None:
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        sel_cues = [self._cues[r] for r in sel_rows]
        if len({c.media_type for c in sel_cues}) != 1:
            return

        self._inspector.set_layer_checked(layer)
        changed = any(cue.layer != layer for cue in sel_cues)
        if changed:
            if self._undo.is_debounce_active():
                self._commit_undo_point()
            for cue in sel_cues:
                cue.layer = layer
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            if len(sel_cues) > 1:
                anchor_row, anchor = self._anchor_row_and_cue()
                self._inspector.load_selection(sel_cues, anchor_cue=anchor, anchor_row=anchor_row)
            else:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(sel_cues[0].cue_id))
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()
            self._sync_live_view()

    @Slot(str)
    def _set_output_target(self, target: str) -> None:
        """Assign the selected cues to output A or B (dual independent routing)."""
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        resolved = normalize_output_target(target)
        sel_cues = [self._cues[r] for r in sel_rows]
        self._inspector.set_output_target_checked(resolved)
        if not any(cue.output_target != resolved for cue in sel_cues):
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        for cue in sel_cues:
            cue.output_target = resolved
        self._refresh_rows_in_place(list(range(len(self._cues))))
        anchor_row, anchor = self._anchor_row_and_cue()
        if anchor:
            self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()
        self._sync_live_view()

    @Slot(str)
    def _set_follow_mode(self, mode: str) -> None:
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        sel_cues = [self._cues[r] for r in sel_rows]
        changed = any(cue.follow_mode != mode for cue in sel_cues)
        self._cue_list_panel.set_follow_mode_checked(mode, enabled=True)
        self._inspector.set_follow_mode_silent(mode, enabled=True)
        if changed:
            for cue in sel_cues:
                cue.follow_mode = mode
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            self._sync_live_view()
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()

    @Slot(str)
    def _set_cue_color(self, color_hex: str) -> None:
        """Assign or clear visual scene group colour across selected cue(s)."""
        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        clean = _sanitize_hex_color(color_hex)
        sel_cues = [self._cues[r] for r in sel_rows]
        changed = any(getattr(cue, "color", "") != clean for cue in sel_cues)
        self._inspector.set_color_silent(clean)
        if changed:
            for cue in sel_cues:
                cue.color = clean
            self._refresh_rows_in_place(list(range(len(self._cues))))
            anchor_row, anchor = self._anchor_row_and_cue()
            if anchor:
                self._inspector.set_layer_conflict(self._layer_conflicts.get(anchor.cue_id))
            self._sync_live_view()
            self._commit_undo_point()
            self._mark_modified(True)
            self._auto_save()
