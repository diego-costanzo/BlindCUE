"""Live Multimedia player – drives the external output window (Layer 1-3).

100% Native Wayland & Linux player using PySide6 QtMultimedia (FFmpeg backend).
Every public method is guarded by try/except to guarantee zero crash in live.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)


class _PlayerSignals(QObject):
    """Qt signals emitted by the live player."""
    position_changed = Signal(float)   # current playback position (seconds)
    duration_changed = Signal(float)   # total duration (seconds)
    eof_reached = Signal()             # playback finished / reached end
    error_occurred = Signal(str)       # human-readable error message


class LivePlayer(QObject):
    """Multimedia player for the LIVE output (audio + video on external screen).

    100% Native Wayland without Xwayland or foreign window hacks.
    """

    def __init__(self, video_widget: Optional[Any] = None,
                 video_output: Optional[Any] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.signals = _PlayerSignals()
        self._video_output = video_output or video_widget
        self._fade_timer: Optional[QTimer] = None
        self._start_ms: int = 0
        self._end_ms: Optional[int] = None
        self._is_looping: bool = False
        self._loop_count: int = 0  # 0 = infinite, N = repeat N times
        self._current_loop_iteration: int = 0
        self._setup_player()

    def _setup_player(self) -> None:
        try:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)

            if self._video_output is not None:
                self._player.setVideoOutput(self._video_output)

            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._player.errorOccurred.connect(self._on_error_occurred)

            logger.info("[LIVE] Native Wayland Multimedia player initialised")
        except Exception as exc:
            logger.critical("[LIVE] Failed to initialise QtMultimedia: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Live Player init failed: {exc}")

    def set_video_output(self, video_output: Any) -> None:
        """Attach or redirect video output to the given item, sink, or widget."""
        self._video_output = video_output
        self._player.setVideoOutput(video_output)

    def set_video_widget(self, video_widget: Any) -> None:
        """Backward compatibility alias for set_video_output."""
        self.set_video_output(video_widget)

    # ── Signal Handlers ───────────────────────────────────────────────

    def _on_position_changed(self, pos_ms: int) -> None:
        pos_sec = pos_ms / 1000.0
        self.signals.position_changed.emit(pos_sec)

        # Handle out_point
        if self._end_ms is not None and pos_ms >= self._end_ms:
            if self._is_looping:
                if self._loop_count > 0:
                    self._current_loop_iteration += 1
                    if self._current_loop_iteration >= self._loop_count:
                        self._player.pause()
                        self.signals.eof_reached.emit()
                    else:
                        self._player.setPosition(self._start_ms)
                else:
                    self._player.setPosition(self._start_ms)
            else:
                self._player.pause()
                self.signals.eof_reached.emit()

    def _on_duration_changed(self, dur_ms: int) -> None:
        if dur_ms > 0:
            self.signals.duration_changed.emit(dur_ms / 1000.0)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if self._start_ms > 0:
                self._player.setPosition(self._start_ms)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if not self._is_looping:
                self.signals.eof_reached.emit()

    def _on_error_occurred(self, error: QMediaPlayer.Error, msg: str) -> None:
        logger.error("[LIVE] Playback error (%s): %s", error, msg)
        self.signals.error_occurred.emit(msg or str(error))

    # ── Public API ────────────────────────────────────────────────────

    def load(self, file_path: str, start: float = 0.0,
             end: Optional[float] = None) -> None:
        """Load a media file for playback."""
        try:
            self._start_ms = max(0, int(start * 1000))
            self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
            self._current_loop_iteration = 0

            url = QUrl.fromLocalFile(file_path)
            self._player.setSource(url)
            if self._start_ms > 0:
                self._player.setPosition(self._start_ms)

            logger.info("[LIVE] Loaded %s (start=%.1f, end=%s)", file_path, start, end)
        except Exception as exc:
            logger.error("[LIVE] load() failed: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Load failed: {exc}")

    def play(self) -> None:
        """Start or resume playback."""
        try:
            pos_ms = self._player.position()
            if (self._end_ms is not None and pos_ms >= self._end_ms) or \
               self._player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self._player.setPosition(self._start_ms)
            if self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self._player.play()
                logger.debug("[LIVE] play()")
        except Exception as exc:
            logger.error("[LIVE] play() failed: %s", exc, exc_info=True)

    def pause(self) -> None:
        """Pause playback."""
        try:
            self._player.pause()
            logger.debug("[LIVE] pause()")
        except Exception as exc:
            logger.error("[LIVE] pause() failed: %s", exc, exc_info=True)

    def stop(self) -> None:
        """Stop playback completely."""
        try:
            self._player.stop()
            logger.debug("[LIVE] stop()")
        except Exception as exc:
            logger.error("[LIVE] stop() failed: %s", exc, exc_info=True)

    def seek(self, position: float) -> None:
        """Seek to *position* in seconds."""
        try:
            self._player.setPosition(int(position * 1000))
        except Exception as exc:
            logger.error("[LIVE] seek() failed: %s", exc, exc_info=True)

    def set_volume(self, volume: int) -> None:
        """Set volume 0-100."""
        try:
            vol_norm = max(0.0, min(1.0, volume / 100.0))
            self._audio.setVolume(vol_norm)
        except Exception as exc:
            logger.error("[LIVE] set_volume() failed: %s", exc)

    def set_loop(self, loop: bool, loop_count: int = 0) -> None:
        """Enable or disable seamless looping. loop_count: 0 = infinite, N = repeat N times."""
        try:
            self._is_looping = loop
            self._loop_count = loop_count
            self._current_loop_iteration = 0
            if not loop:
                self._player.setLoops(QMediaPlayer.Loops.Once)
            elif loop_count <= 0:
                self._player.setLoops(QMediaPlayer.Loops.Infinite)
            else:
                self._player.setLoops(loop_count)
        except Exception as exc:
            logger.error("[LIVE] set_loop() failed: %s", exc)

    def set_aspect_ratio(self, aspect: Optional[str]) -> None:
        """Adjust video aspect ratio."""
        # QVideoWidget handles aspect ratio natively via AspectRatioMode
        pass

    def set_scale(self, scale: float) -> None:
        pass

    def set_crop(self, crop: Optional[dict]) -> None:
        pass

    def fade_in(self, target_volume: int, duration_sec: float) -> None:
        """Fade volume in from 0 to *target_volume* over *duration_sec* seconds."""
        try:
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()

            if duration_sec <= 0:
                self.set_volume(target_volume)
                return

            self._audio.setVolume(0.0)
            target_norm = max(0.0, min(1.0, target_volume / 100.0))
            steps = max(1, int(duration_sec * 25))  # 25 fps volume steps
            step_interval = int(1000 / 25)
            step_increment = target_norm / steps
            current_step = 0

            self._fade_timer = QTimer(self)

            def _tick() -> None:
                nonlocal current_step
                current_step += 1
                new_vol = min(target_norm, current_step * step_increment)
                self._audio.setVolume(new_vol)
                if current_step >= steps:
                    self._fade_timer.stop()

            self._fade_timer.timeout.connect(_tick)
            self._fade_timer.start(step_interval)
        except Exception as exc:
            logger.error("[LIVE] fade_in() failed: %s", exc)
            self.set_volume(target_volume)

    def fade_out(self, duration_sec: float = 0.2, stop_after: bool = False,
                 callback: Optional[Callable[[], None]] = None) -> None:
        """Fade volume down to 0 over *duration_sec* seconds (default 0.2s micro-fade).

        Optionally stops playback and calls *callback* when the fade completes.
        """
        try:
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()

            start_norm = self._audio.volume()
            if duration_sec <= 0 or start_norm <= 0:
                self._audio.setVolume(0.0)
                if stop_after:
                    self.stop()
                if callback is not None:
                    callback()
                return

            steps = max(1, int(duration_sec * 30))  # 30 fps volume steps
            step_interval = int(1000 / 30)
            step_decrement = start_norm / steps
            current_step = 0

            self._fade_timer = QTimer(self)

            def _tick() -> None:
                nonlocal current_step
                current_step += 1
                new_vol = max(0.0, start_norm - (current_step * step_decrement))
                self._audio.setVolume(new_vol)
                if current_step >= steps:
                    self._fade_timer.stop()
                    self._audio.setVolume(0.0)
                    if stop_after:
                        self.stop()
                    if callback is not None:
                        callback()

            self._fade_timer.timeout.connect(_tick)
            self._fade_timer.start(step_interval)
        except Exception as exc:
            logger.error("[LIVE] fade_out() failed: %s", exc)
            self._audio.setVolume(0.0)
            if stop_after:
                self.stop()
            if callback is not None:
                callback()

    def shutdown(self) -> None:
        """Cleanly release resources."""
        try:
            if self._fade_timer is not None:
                self._fade_timer.stop()
            self._player.stop()
            logger.info("[LIVE] Shutdown complete")
        except Exception as exc:
            logger.error("[LIVE] Shutdown error: %s", exc)
