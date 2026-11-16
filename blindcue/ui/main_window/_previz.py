"""Image Pre-Viz Opacity Timeline Player mixin for MainWindow.

Static images have no media clock, so this mixin drives a 30 fps QTimer that
advances a virtual playhead and applies the cue opacity envelope. It lets the
operator rehearse a fade without touching the live output.
"""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _PrevizMixin:
    def start_image_preview_playback(self, cue: Cue) -> None:
        """Start (or resume) the invisible-clock rehearsal of an image cue."""
        if cue.media_type != MediaType.IMAGE:
            return
        dur = self._effective_timeline_end(cue)
        if self._img_previz_elapsed >= dur - 0.02:
            self._img_previz_elapsed = 0.0
        self.show_preview_image(
            cue.file_path, scale=cue.scale, crop=cue.crop,
            pos_x=cue.position_x, pos_y=cue.position_y,
            opacity=cue.opacity, aspect_ratio=cue.aspect_ratio,
            rotation=cue.rotation, mask_polygon=cue.mask_polygon,
            mask_feather=cue.mask_feather,
        )
        self._on_img_previz_tick(advance=False)
        self._img_previz_timer.start()

    def pause_image_preview_playback(self) -> None:
        """Freeze the virtual playhead; resume keeps the current position."""
        self._img_previz_timer.stop()

    def stop_image_preview_playback(self) -> None:
        """Reset the rehearsal playhead to zero and restore the cue opacity."""
        self._img_previz_timer.stop()
        self._img_previz_elapsed = 0.0
        cue = self._selected_cue()
        if cue is not None and cue.media_type == MediaType.IMAGE:
            dur = self._effective_timeline_end(cue)
            self.set_waveform_playhead_seconds(0.0, dur, "PRE-VIZ")
            self.set_preview_time(0.0, dur)
            self._preview_monitor.set_opacity(cue.opacity)

    def _on_img_previz_tick(self, advance: bool = True) -> None:
        cue = self._selected_cue()
        if cue is None or cue.media_type != MediaType.IMAGE:
            self._img_previz_timer.stop()
            return
        dur = self._effective_timeline_end(cue)
        if advance:
            self._img_previz_elapsed += 0.033
        if self._img_previz_elapsed >= dur:
            self._img_previz_elapsed = dur
            self._img_previz_timer.stop()
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
        self.set_waveform_playhead_seconds(self._img_previz_elapsed, dur, "PRE-VIZ")
        self.set_preview_time(self._img_previz_elapsed, dur)
