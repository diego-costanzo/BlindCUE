"""Fade Ramps, Keyframe Envelopes, Image Pre-Viz & Sections mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _EnvelopeMixin:
    @Slot(float)
    def _on_waveform_fade_in_changed(self, new_fi: float) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        val = round(max(0.0, new_fi), 2)
        for cue in sel_cues:
            cue.fade_in = val
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_fades_silent(fade_in=val)
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Fade IN: {val:.2f}s")

    @Slot(float)
    def _on_waveform_fade_out_changed(self, new_fo: float) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        val = round(max(0.0, new_fo), 2)
        for cue in sel_cues:
            cue.fade_out = val
        anchor = self._selected_cue()
        if anchor:
            self._inspector.set_fades_silent(fade_out=val)
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Fade OUT: {val:.2f}s")

    @Slot(str)
    def _on_waveform_fade_curve_changed(self, curve: str) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            cue.fade_curve = curve
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Curva Fade impostata: {curve}")

    @Slot(str)
    def _on_envelope_mode_changed(self, mode: str) -> None:
        cue = self._selected_cue()
        if cue:
            self._sync_timeline_for_cue(cue)

    @Slot(str, list)
    def _on_envelope_points_changed(self, mode: str, points: list) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        copied = [list(p) for p in points]
        for cue in sel_cues:
            if mode == "opacity":
                cue.opacity_points = [list(p) for p in copied]
            else:
                cue.volume_points = [list(p) for p in copied]
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot(str)
    def _on_reset_envelope_points(self, mode: str) -> None:
        sel_cues = self._selected_cues()
        if not sel_cues or len({c.media_type for c in sel_cues}) != 1:
            return
        for cue in sel_cues:
            if mode == "opacity":
                cue.opacity_points = []
            else:
                cue.volume_points = []
        anchor = self._selected_cue()
        if anchor:
            self._sync_timeline_for_cue(anchor)
            self.live_automation_updated.emit(anchor)
            if anchor.media_type == MediaType.IMAGE:
                self._preview_monitor.set_opacity(anchor.opacity)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Punti envelope azzerati")

    @Slot(float)
    def _on_image_horizon_changed(self, horizon_sec: float) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type != MediaType.IMAGE:
            return
        cue.image_timeline_sec = max(1.0, float(horizon_sec))
        self._sync_timeline_for_cue(cue)
        self.set_waveform_playhead_seconds(min(self._img_previz_elapsed, cue.image_timeline_sec), cue.image_timeline_sec, "PRE-VIZ")
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot()
    def _on_split_section(self) -> None:
        cue = self._selected_cue()
        dur = self._active_test_duration
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO) or dur <= 0:
            return
        eff_end = self._effective_timeline_end(cue)
        ph = self._waveform.playhead_seconds()
        if ph is not None and cue.in_point + 0.15 <= ph <= eff_end - 0.15:
            split_t = ph
        else:
            # Smart midpoint split of active region when testina is sitting at an edge
            target_sec = next(
                (s for s in cue.sections if (s.end or eff_end) - s.start >= 0.30),
                None,
            )
            if target_sec is not None:
                s_end = target_sec.end if target_sec.end is not None else eff_end
                split_t = round((target_sec.start + s_end) / 2.0, 2)
            else:
                split_t = round((cue.in_point + eff_end) / 2.0, 2)

        updated = split_sections_at(cue.sections, split_t, cue.in_point, eff_end)
        if len(updated) <= len(cue.sections) and len(cue.sections) >= 2:
            self._status_label.setText("Spazio insufficiente per dividere ancora in questo punto")
            return
        cue.sections = updated
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(f"Creato taglio sezione a {split_t:.2f}s ({len(cue.sections)} sezioni)")

    @Slot(list)
    def _on_sections_resized(self, sections_list: list) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type not in (MediaType.VIDEO, MediaType.AUDIO):
            return
        cue.sections = list(sections_list)
        self._waveform_panel.section_bar.set_sections(
            cue.sections, self._active_test_duration, active_index=self._active_section_idx
        )
        self.live_automation_updated.emit(cue)
        self._schedule_undo_point()
        self._mark_modified(True)

    @Slot(int, int, bool)
    def _on_section_mode_changed(self, idx: int, loops: int, skip: bool) -> None:
        cue = self._selected_cue()
        if cue is None or not (0 <= idx < len(cue.sections)):
            return
        cue.sections[idx].loops = loops
        cue.sections[idx].skip = skip
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        mode_lbl = "Salta" if skip else ("∞ Infinito" if loops == 0 else f"x{loops}")
        self._status_label.setText(f"Sezione {cue.sections[idx].label}: {mode_lbl}")

    @Slot(int)
    def _on_remove_section(self, idx: int) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        eff_end = self._effective_timeline_end(cue)
        cue.sections = merge_section_at(cue.sections, idx, cue.in_point, eff_end)
        if not cue.sections:
            self._active_section_idx = -1
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(
            "Ritorno a file intero (modalità normale)" if not cue.sections else "Sezione unita"
        )

    @Slot()
    def _on_reset_sections(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        cue.sections = []
        self._active_section_idx = -1
        self._sync_timeline_for_cue(cue)
        self.live_automation_updated.emit(cue)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText("Sezioni azzerate: ripristinato il file originale")

    @Slot(int)
    def _on_section_jump_clicked(self, idx: int) -> None:
        cue = self._selected_cue()
        if cue is None or not (0 <= idx < len(cue.sections)):
            return
        self._active_section_idx = idx
        self._waveform.set_active_section_index(idx)
        self._waveform_panel.section_bar.set_active_index(idx)
        self.section_jump_requested.emit(cue, idx, cue.status == CueStatus.LIVE)

    @Slot()
    def _on_break_section_loop(self) -> None:
        cue = self._selected_cue()
        if cue is None or not cue.sections:
            return
        self.section_break_loop_requested.emit(cue, cue.status == CueStatus.LIVE)

    def set_live_section_index(self, cue_id: int, sec_idx: int) -> None:
        """Mirror the scheduler's active section into the waveform editor.

        Only the currently selected cue is updated: sections of other cues are
        irrelevant until the operator opens them.
        """
        cue = self._selected_cue()
        if cue is not None and cue.cue_id == cue_id:
            self._active_section_idx = sec_idx
            self._waveform.set_active_section_index(sec_idx)
            self._waveform_panel.section_bar.set_active_index(sec_idx)
