"""Inspector & Waveform Interaction mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _InspectorMixin:
    def _update_inspector(self, cue: Cue | None) -> None:
        if cue is None:
            self._inspector.load_cue(None)
            self._inspector.set_layer_conflict(None)
            return
        sel_cues = self._selected_cues()
        anchor_row, anchor_cue = self._anchor_row_and_cue()
        if anchor_cue is not None:
            self._update_crop_reference_for_cue(anchor_cue)
        if len(sel_cues) > 1:
            self._inspector.load_selection(sel_cues, anchor_cue=anchor_cue, anchor_row=anchor_row)
        else:
            self._inspector.load_cue(cue, anchor_row)
            if cue.media_type == MediaType.GROUP:
                children = [c for c in self._cues if c.parent_id == cue.cue_id]
                self._inspector.load_group_children(children, cue)
        self._inspector.set_layer_conflict(self._layer_conflicts.get(cue.cue_id))
        if anchor_cue is not None:
            self._update_waveform_markers(anchor_cue)

    @Slot(str)
    def _on_batch_field_edited(self, field_key: str) -> None:
        """Apply a single modified inspector property uniformly across same-type multi-selection."""
        sel_rows = self._selected_rows()
        if len(sel_rows) < 2:
            return
        sel_cues = [self._cues[r] for r in sel_rows]
        if len({c.media_type for c in sel_cues}) != 1:
            return

        self._inspector.apply_batch_field(field_key, sel_cues)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._refresh_rows_in_place(sel_rows)

        anchor_row, anchor = self._anchor_row_and_cue()
        if anchor is not None:
            if field_key in ("in_point", "out_point", "volume", "opacity", "fade_in", "fade_out", "hold_time",
                             "audio_mix"):
                self._sync_timeline_for_cue(anchor)
                self.live_automation_updated.emit(anchor)
            if field_key in ("in_point", "out_point"):
                self.preview_in_out_changed.emit(
                    anchor.in_point, anchor.out_point, field_key == "in_point"
                )
            if field_key == "volume":
                self.live_volume_changed.emit(self._inspector.slider_volume.value())
            if anchor.media_type in (MediaType.VIDEO, MediaType.IMAGE):
                self._render_cue_in_preview(anchor, load_image=(anchor.media_type == MediaType.VIDEO))
            if self._live_mirror_active:
                self._mirror_active_cue_to_live()

    @Slot()
    def _on_inspector_value_changed(self) -> None:
        sel_cues = self._selected_cues()
        if len(sel_cues) != 1:
            return
        self._apply_inspector_to_cue()
        self._schedule_undo_point()
        self._mark_modified(True)
        cue = sel_cues[0]
        self._update_selected_list_item(cue)
        if cue.media_type in (MediaType.VIDEO, MediaType.IMAGE):
            self._render_cue_in_preview(cue, load_image=(cue.media_type == MediaType.VIDEO))
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    def _apply_inspector_to_cue(self) -> None:
        # In the show the inspector is hidden and the document must not change:
        # GO, autosave and save used to write its (stale) values into the
        # selected cue.
        if self._live_mode:
            return
        sel_cues = self._selected_cues()
        if len(sel_cues) != 1:
            return
        cue = sel_cues[0]
        prev_in = cue.in_point
        prev_out = cue.out_point
        self._inspector.apply_to_cue(cue)
        if cue.media_type == MediaType.ACTION:
            # No media: the volume slider must not reach a live player
            # (with Live Mirror on it would re-level layer 1).
            return
        self._sync_timeline_for_cue(cue)
        self.live_volume_changed.emit(self._inspector.slider_volume.value())
        self.live_automation_updated.emit(cue)
        if cue.in_point != prev_in or cue.out_point != prev_out:
            self.preview_in_out_changed.emit(
                cue.in_point, cue.out_point, cue.in_point != prev_in
            )

    @Slot(float, float)
    def _on_preview_position_changed(self, pos_x: float, pos_y: float) -> None:
        self._inspector.set_position_silent(pos_x, pos_y)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            cue.position_x = pos_x
            cue.position_y = pos_y
        self._schedule_undo_point()
        self._mark_modified(True)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    @Slot(float, float, float, float)
    def _on_preview_crop_changed(self, crop_l: float, crop_r: float,
                                 crop_t: float, crop_b: float) -> None:
        self._inspector.set_crop_silent(crop_l, crop_r, crop_t, crop_b)
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        crop_dict = {
            "x": round(crop_l, 6),
            "y": round(crop_t, 6),
            "w": max(0.01, round(1.0 - crop_l - crop_r, 6)),
            "h": max(0.01, round(1.0 - crop_t - crop_b, 6)),
        }
        for cue in sel_cues:
            cue.crop = dict(crop_dict)
        self._schedule_undo_point()
        self._mark_modified(True)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    @Slot()
    def _on_mask_edit_requested(self) -> None:
        """Open the polygon mask editor for the selected IMAGE cue (non-destructive)."""
        cue = self._selected_cue()
        if cue is None or cue.media_type != MediaType.IMAGE:
            return
        dialog = ImageMaskDialog(cue.file_path, cue.crop, cue.mask_polygon, cue.mask_feather, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cue.mask_polygon = dialog.mask_points()
        cue.mask_feather = dialog.mask_feather()
        self._inspector.set_mask_silent(cue.mask_polygon)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._render_cue_in_preview(cue, load_image=False)
        if self._live_mirror_active:
            self._mirror_active_cue_to_live()

    def _commit_waveform_in(
        self, new_in: float, *, clear_conflicting_out: bool = False, seek_preview: bool = True
    ) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        rounded_in = round(max(0.0, new_in), 2)
        for cue in sel_cues:
            cue.in_point = rounded_in
            if cue.out_point is not None and cue.out_point <= rounded_in + 0.04:
                cue.out_point = None if clear_conflicting_out else round(rounded_in + 0.05, 2)
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_in_silent(anchor.in_point)
            self._inspector.set_out_silent(anchor.out_point or 0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point, seek_preview)
        self._schedule_undo_point()
        self._mark_modified(True)

    def _commit_waveform_out(self, new_out: float | None) -> float | None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return None
        for cue in sel_cues:
            if new_out is None or new_out <= 0.0:
                cue.out_point = None
            elif new_out <= cue.in_point + 0.04:
                cue.out_point = round(cue.in_point + 0.05, 2)
            else:
                cue.out_point = round(new_out, 2)
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_out_silent(anchor.out_point or 0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(anchor.in_point, anchor.out_point, False)
        self._schedule_undo_point()
        self._mark_modified(True)
        return anchor.out_point if anchor else None

    @Slot(float)
    def _on_waveform_in_changed(self, new_in: float) -> None:
        self._commit_waveform_in(new_in, clear_conflicting_out=False, seek_preview=True)

    @Slot(float)
    def _on_waveform_out_changed(self, new_out: float) -> None:
        self._commit_waveform_out(None if new_out <= 0.0 else new_out)

    @Slot(float)
    def _on_waveform_seek_requested(self, sec: float) -> None:
        cue = self._selected_cue()
        if cue is None:
            return
        if cue.media_type == MediaType.IMAGE:
            dur = self._effective_timeline_end(cue)
            self._img_previz_elapsed = max(0.0, min(dur, sec))
            self.set_waveform_playhead_seconds(self._img_previz_elapsed, dur, "PRE-VIZ")
            self.set_preview_time(self._img_previz_elapsed, dur)
            op = evaluate_cue_level(
                self._img_previz_elapsed,
                start_sec=0.0,
                end_sec=cue.hold_time if cue.hold_time > 0 else None,
                duration_sec=dur,
                fade_in=cue.fade_in,
                fade_out=cue.fade_out if cue.hold_time > 0 else 0.0,
                fade_curve=cue.fade_curve,
                points=cue.opacity_points,
                base_level=cue.opacity,
                apply_fade_out_at_end=(cue.hold_time > 0),
            )
            self._preview_monitor.set_opacity(op)
            return
        if cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        self._waveform_panel.set_playhead_display(sec, self._active_test_duration, "PRE-VIZ", snap_enabled=True)
        self.set_preview_time(sec, self._active_test_duration)
        self.preview_seek_requested.emit(sec)

    def _on_snap_shortcut(self, is_in: bool) -> None:
        if self._live_mode or self._is_text_input_focused():
            return
        if is_in:
            self._on_snap_in_to_playhead()
        else:
            self._on_snap_out_to_playhead()

    @Slot()
    def _on_snap_in_to_playhead(self) -> None:
        cue = self._selected_cue()
        dur = self._waveform.duration_seconds()
        playhead_sec = self._waveform.playhead_seconds()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0 or playhead_sec is None:
            return
        from engine.in_out import in_at

        target_in = in_at(playhead_sec, dur)  # the same rule as "start here" in the Edit cue window
        self._commit_waveform_in(target_in, clear_conflicting_out=True, seek_preview=False)
        self._status_label.setText(f"Punto IN spostato sulla testina: {target_in:.2f}s")

    @Slot()
    def _on_snap_out_to_playhead(self) -> None:
        cue = self._selected_cue()
        dur = self._waveform.duration_seconds()
        playhead_sec = self._waveform.playhead_seconds()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0 or playhead_sec is None:
            return
        from engine.in_out import OUT_END, OUT_MIN, out_at

        target_out, how = out_at(playhead_sec, cue.in_point, dur)  # the same rule as "end here" (Edit cue)
        if how == OUT_END:
            applied = self._commit_waveform_out(None)
            self._status_label.setText("Punto OUT impostato sulla fine del file (Fine)")
        elif how == OUT_MIN:
            applied = self._commit_waveform_out(target_out)
            self._status_label.setText(
                f"Testina prima di IN: OUT impostato al minimo ({applied:.2f}s)" if applied else "OUT aggiornato"
            )
        else:
            applied = self._commit_waveform_out(target_out)
            self._status_label.setText(
                f"Punto OUT spostato sulla testina: {applied:.2f}s" if applied else "OUT aggiornato"
            )

    @Slot()
    def _on_trim_silence(self) -> None:
        """3.4: IN/OUT of the selected sound / video where its sound really starts and ends."""
        from engine.show_mode import EDIT_CUE
        from engine.silence_trim import THRESHOLD_DB, sound_bounds
        from i18n import tr

        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.AUDIO, MediaType.VIDEO) or len(self._selected_rows()) != 1:
            return
        if not self._change_allowed(EDIT_CUE):
            return
        peaks = self._waveform_cache.get(os.path.abspath(cue.file_path or ""))
        bounds = sound_bounds(peaks if isinstance(peaks, np.ndarray) else None, self._active_test_duration)
        if bounds is None:
            self._status_label.setText(tr("Taglia il silenzio: forma d'onda non ancora pronta o file muto"))
            return
        start, end = bounds
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.in_point, cue.out_point = start, end
        self._inspector.set_in_silent(start)
        self._inspector.set_out_silent(end or 0.0)
        self._update_waveform_markers(cue)
        self.preview_in_out_changed.emit(start, end, True)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(tr("Silenzio tagliato (sotto {} dB): IN {} s, OUT {}").format(
            int(THRESHOLD_DB), f"{start:.2f}", f"{end:.2f} s" if end is not None else tr("Fine File")))

    def _on_reset_in_out(self) -> None:
        """Reset IN to 0.00s and OUT to Fine (None) across selected same-type timed cues."""
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        if sel_cues[0].media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        for cue in sel_cues:
            cue.in_point = 0.0
            cue.out_point = None
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_in_silent(0.0)
            self._inspector.set_out_silent(0.0)
            self._update_waveform_markers(anchor)
            self.preview_in_out_changed.emit(0.0, None, False)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Punti IN e OUT ripristinati: IN = 0.00s, OUT = Fine")
