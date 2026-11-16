"""Preview Visual Pass-Throughs mixin for MainWindow.

The director panel shows the same composited result as the projectors. These
methods forward the selected cue's geometry (scale/crop/position/opacity) to
``PreviewMonitor`` so the preview is never a rough approximation of the output.
"""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _PreviewMixin:
    def show_preview_image(self, file_path: str, scale: float = 1.0, crop: dict | None = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                           aspect_ratio: str | None = None, rotation: float = 0.0,
                           mask_polygon: list[list[float]] | None = None,
                           mask_feather: float = 0.0) -> None:
        """Show a still image in the preview with the cue's exact geometry."""
        self._preview_monitor.show_image(
            file_path, scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio,
            rotation=rotation, mask_polygon=mask_polygon,
            mask_feather=mask_feather,
        )

    def show_preview_video(self, scale: float = 1.0, crop: dict | None = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                           aspect_ratio: str | None = None, rotation: float = 0.0) -> None:
        """Switch the preview surface to video mode with the given geometry."""
        self._preview_monitor.show_video(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio, rotation=rotation,
        )

    def update_preview_video_layout(self, scale: float = 1.0, crop: dict | None = None,
                                    pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                                    aspect_ratio: str | None = None,
                                    rotation: float = 0.0) -> None:
        """Re-layout the live preview video without restarting playback."""
        self._preview_monitor.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio, rotation=rotation,
        )

    def show_preview_audio(self) -> None:
        """Show the audio placeholder (waveform/icon) in the preview surface."""
        self._preview_monitor.show_audio()

    def set_preview_audio_playing(self, is_playing: bool) -> None:
        """Toggle the preview play/pause indicator for audio cues."""
        self._preview_monitor.set_audio_playing(is_playing)

    def clear_preview(self) -> None:
        """Clear the preview surface back to the layer-0 tappo."""
        self._preview_monitor.clear_media()

    def get_preview_video_sink(self) -> QVideoSink:
        """Return the sink the test player renders into."""
        return self._preview_monitor.get_video_sink()

    def get_preview_video_widget(self) -> Any:
        """Alias of :meth:`get_preview_video_sink` for player constructors."""
        return self._preview_monitor.get_video_sink()
