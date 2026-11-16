"""Waveform & Preview Layout Helpers mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _WaveformMixin:
    def set_waveform_playhead_seconds(
        self,
        sec: float | None,
        duration_sec: float = 0.0,
        source_tag: str = "PRE-VIZ",
    ) -> None:
        """Update waveform cursor position (testina) and header readout/buttons safely."""
        prev_dur = self._active_test_duration
        if duration_sec > 0:
            self._active_test_duration = max(0.001, duration_sec)
        dur = self._active_test_duration if duration_sec <= 0 else duration_sec
        cue = self._selected_cue()
        is_image = cue is not None and cue.media_type == MediaType.IMAGE
        timed_cue = cue is not None and cue.media_type in (MediaType.VIDEO, MediaType.AUDIO)
        sel_cues = self._selected_cues()
        uniform_timed = timed_cue and bool(sel_cues) and len({c.media_type for c in sel_cues}) == 1
        if sec is None or dur <= 0 or (not timed_cue and not is_image):
            self._waveform.set_playhead(None)
            self._waveform_panel.set_playhead_display(
                None, 0.0, source_tag, snap_enabled=False, reset_enabled=uniform_timed
            )
            return
        if prev_dur <= 0 and dur > 0 and cue is not None:
            self._inspector.spin_out.set_media_duration(dur)
            self._sync_timeline_for_cue(cue)
        self._waveform.set_playhead_seconds(sec, dur)
        self._waveform_panel.set_playhead_display(
            sec,
            dur,
            source_tag,
            snap_enabled=timed_cue,
            reset_enabled=uniform_timed,
        )

    def update_waveform_duration(self, duration_sec: float) -> None:
        """Store the real media duration and refresh waveform + OUT spinbox limits."""
        self._active_test_duration = max(0.001, duration_sec)
        self._inspector.spin_out.set_media_duration(self._active_test_duration)
        cue = self._selected_cue()
        if cue:
            self._sync_timeline_for_cue(cue)
            if cue.media_type in (MediaType.VIDEO, MediaType.AUDIO):
                cur_ph = self._waveform.playhead_seconds()
                target_sec = min(self._active_test_duration, max(0.0, cue.in_point)) if cur_ph is None else cur_ph
                self.set_waveform_playhead_seconds(target_sec, self._active_test_duration, "PRE-VIZ")

    def _update_waveform_markers(self, cue: Cue | None = None) -> None:
        if cue is None:
            cue = self._selected_cue()
        if cue is None:
            return
        self._sync_timeline_for_cue(cue)

    def _effective_timeline_end(self, cue: Cue) -> float:
        if cue.media_type == MediaType.IMAGE:
            return cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec
        dur = self._active_test_duration
        if dur <= 0:
            return 0.0
        if cue.out_point is not None and cue.out_point > cue.in_point:
            return min(dur, cue.out_point)
        return dur

    def _sync_timeline_for_cue(self, cue: Cue | None) -> None:
        """Keep waveform/opacity canvas, fade pallini, section bands, and controls synced."""
        if cue is None:
            return
        is_image = (cue.media_type == MediaType.IMAGE)
        dur = (cue.hold_time if cue.hold_time > 0 else cue.image_timeline_sec) if is_image else self._active_test_duration
        if is_image:
            self._active_test_duration = dur

        mode = "opacity" if is_image else self._waveform._envelope_mode
        show_fo = (not is_image) or (cue.hold_time > 0)
        self._waveform.set_media_context(cue.media_type, mode, show_fade_out=show_fo)
        if is_image:
            self._waveform.set_in_out_seconds(0.0, None, dur)
        else:
            self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, dur)

        self._waveform.set_fades(cue.fade_in, cue.fade_out, cue.fade_curve)
        self._waveform.set_envelopes(
            base_volume=cue.volume,
            base_opacity=cue.opacity,
            volume_points=cue.volume_points,
            opacity_points=cue.opacity_points,
        )

        eff_end = self._effective_timeline_end(cue)
        if not is_image and dur > 0 and cue.sections:
            cue.sections = normalize_sections(cue.sections, cue.in_point, eff_end)
        else:
            cue.sections = [] if is_image else cue.sections

        active_idx = self._active_section_idx if len(cue.sections) >= 2 else -1
        self._waveform.set_sections(cue.sections, active_idx=active_idx)
        self._waveform_panel.section_bar.set_sections(cue.sections, dur, active_index=active_idx)

        active_pts = cue.opacity_points if mode == "opacity" else cue.volume_points
        can_split = (not is_image) and dur > 0 and (eff_end - cue.in_point) >= 0.35
        has_repeating = any(s.loops == 0 or s.loops > 1 for s in cue.sections if not s.skip)
        self._waveform_panel.sync_controls_for_cue(
            media_type=cue.media_type,
            fade_curve=cue.fade_curve,
            has_points=bool(active_pts),
            has_sections=len(cue.sections) >= 2,
            can_split=can_split,
            has_repeating_section=has_repeating,
            image_horizon_sec=cue.image_timeline_sec,
            hold_time=cue.hold_time,
        )

    def _update_crop_reference_for_cue(self, cue: Cue) -> None:
        """Supply exact pixel dimensions (cached header/frame size) to Inspector Crop %/px."""
        cached = self._media_res_cache.get(cue.file_path)
        if cached is not None:
            self._inspector.set_crop_reference_size(cached[0], cached[1])
            return
        if cue.media_type == MediaType.IMAGE and os.path.isfile(cue.file_path):
            sz = QImageReader(cue.file_path).size()
            if sz.isValid() and sz.width() > 0 and sz.height() > 0:
                res = (sz.width(), sz.height())
                self._media_res_cache[cue.file_path] = res
                self._inspector.set_crop_reference_size(res[0], res[1])
                return
        self._inspector.set_crop_reference_size(1920, 1080)

    @Slot(int, int)
    def _on_video_resolution_detected(self, width: int, height: int) -> None:
        cue = self._selected_cue()
        if cue and cue.media_type == MediaType.VIDEO and width > 0 and height > 0:
            self._media_res_cache[cue.file_path] = (width, height)
            self._inspector.set_crop_reference_size(width, height)

    def _render_cue_in_preview(self, cue: Cue, load_image: bool = True) -> None:
        if cue.media_type == MediaType.VIDEO:
            if load_image:
                self.update_preview_video_layout(
                    scale=cue.scale, crop=cue.crop,
                    pos_x=cue.position_x, pos_y=cue.position_y,
                    opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                    rotation=cue.rotation,
                )
            else:
                self.show_preview_video(
                    scale=cue.scale, crop=cue.crop,
                    pos_x=cue.position_x, pos_y=cue.position_y,
                    opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                    rotation=cue.rotation,
                )
        elif cue.media_type == MediaType.IMAGE:
            self.show_preview_image(
                cue.file_path, scale=cue.scale, crop=cue.crop,
                pos_x=cue.position_x, pos_y=cue.position_y,
                opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
                rotation=cue.rotation, mask_polygon=cue.mask_polygon,
                mask_feather=cue.mask_feather,
            )
        elif cue.media_type == MediaType.AUDIO:
            self.show_preview_audio()
