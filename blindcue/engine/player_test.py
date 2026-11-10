"""Test / Pre-Viz Multimedia player – ALWAYS muted by default, never heard by audience.

100% Native Wayland & Linux player using PySide6 QtMultimedia (FFmpeg backend).
Enforces silent preview by default; audio monitoring can be enabled explicitly by operator.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)


class _TestSignals(QObject):
    """Qt signals emitted by the test/preview player."""
    position_changed = Signal(float)
    duration_changed = Signal(float)
    eof_reached = Signal()
    error_occurred = Signal(str)


class TestPlayer(QObject):
    """Multimedia player for PRE-VIZ / TEST preview (silent by default).

    100% Native Wayland without Xwayland or foreign window hacks.
    """

    def __init__(self, video_widget: Optional[Any] = None,
                 video_output: Optional[Any] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.signals = _TestSignals()
        self._video_output = video_output or video_widget
        self._is_muted: bool = True
        self._preview_volume: float = 0.8
        self._start_ms: int = 0
        self._end_ms: Optional[int] = None
        self._is_looping: bool = False
        self._loop_count: int = 0
        self._current_loop_iteration: int = 0
        self._fade_timer: Optional[QTimer] = None
        self._setup_player()

    def _setup_player(self) -> None:
        try:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)

            if self._video_output is not None:
                self._player.setVideoOutput(self._video_output)

            # Default: strict silence for preview safety
            self._enforce_mute()

            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._player.errorOccurred.connect(self._on_error_occurred)

            logger.info("[TEST] Native Wayland Test player initialised (MUTED)")
        except Exception as exc:
            logger.critical("[TEST] Failed to initialise QtMultimedia: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Test Player init failed: {exc}")

    def set_video_output(self, video_output: Any) -> None:
        """Attach or redirect preview video output to the given sink or widget."""
        self._video_output = video_output
        self._player.setVideoOutput(video_output)

    def set_video_widget(self, video_widget: Any) -> None:
        """Backward compatibility alias for set_video_output."""
        self.set_video_output(video_widget)

    def set_mute(self, is_muted: bool) -> None:
        """Toggle preview mute on or off on explicit operator request."""
        self._is_muted = is_muted
        self._enforce_mute()
        logger.info("[TEST] Preview mute set to: %s", is_muted)

    def is_muted(self) -> bool:
        return self._is_muted

    def _enforce_mute(self) -> None:
        try:
            if self._is_muted:
                self._audio.setMuted(True)
                self._audio.setVolume(0.0)
            else:
                self._audio.setMuted(False)
                self._audio.setVolume(self._preview_volume)
        except Exception:
            pass

    # ── Signal Handlers ───────────────────────────────────────────────

    def _on_position_changed(self, pos_ms: int) -> None:
        pos_sec = pos_ms / 1000.0
        self.signals.position_changed.emit(pos_sec)

        # Handle out_point: pause and rewind to start so it is immediately re-playable!
        if self._end_ms is not None and pos_ms >= self._end_ms:
            if self._is_looping:
                if self._loop_count > 0:
                    self._current_loop_iteration += 1
                    if self._current_loop_iteration >= self._loop_count:
                        self._player.pause()
                        self._player.setPosition(self._start_ms)
                        self.signals.eof_reached.emit()
                    else:
                        self._player.setPosition(self._start_ms)
                else:
                    self._player.setPosition(self._start_ms)
            else:
                self._player.pause()
                self._player.setPosition(self._start_ms)
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
        logger.error("[TEST] Preview error (%s): %s", error, msg)
        self.signals.error_occurred.emit(msg or str(error))

    # ── Public API ────────────────────────────────────────────────────

    def load(self, file_path: str, start: float = 0.0,
             end: Optional[float] = None, pause: bool = False) -> None:
        """Load a media file for preview."""
        self._enforce_mute()
        try:
            self._start_ms = max(0, int(start * 1000))
            self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
            self._current_loop_iteration = 0

            url = QUrl.fromLocalFile(file_path)
            self._player.setSource(url)
            if self._start_ms > 0:
                self._player.setPosition(self._start_ms)

            if pause:
                self._player.pause()

            logger.info("[TEST] Loaded %s (start=%.1f, end=%s, pause=%s)",
                        file_path, start, end, pause)
        except Exception as exc:
            logger.error("[TEST] load() failed: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Test load failed: {exc}")
        finally:
            self._enforce_mute()

    def play(self) -> None:
        self._enforce_mute()
        try:
            pos_ms = self._player.position()
            if (self._end_ms is not None and pos_ms >= self._end_ms) or \
               self._player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self._player.setPosition(self._start_ms)
            self._player.play()
            logger.debug("[TEST] play()")
        except Exception as exc:
            logger.error("[TEST] play() failed: %s", exc, exc_info=True)

    def pause(self) -> None:
        self._enforce_mute()
        try:
            self._player.pause()
            logger.debug("[TEST] pause()")
        except Exception as exc:
            logger.error("[TEST] pause() failed: %s", exc, exc_info=True)

    def stop(self) -> None:
        self._enforce_mute()
        try:
            self._player.stop()
            logger.debug("[TEST] stop()")
        except Exception as exc:
            logger.error("[TEST] stop() failed: %s", exc, exc_info=True)

    def seek(self, position: float) -> None:
        self._enforce_mute()
        try:
            self._player.setPosition(int(position * 1000))
        except Exception as exc:
            logger.error("[TEST] seek() failed: %s", exc, exc_info=True)

    def set_loop(self, loop: bool, loop_count: int = 0) -> None:
        self._enforce_mute()
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
            logger.error("[TEST] set_loop() failed: %s", exc)

    def set_aspect_ratio(self, aspect: Optional[str]) -> None:
        self._aspect = aspect

    def set_scale(self, scale: float) -> None:
        self._scale = scale

    def set_crop(self, crop: Optional[dict]) -> None:
        self._crop = crop

    def is_paused(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_idle(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState

    def set_in_out(self, start: float, end: Optional[float] = None,
                   seek_to_start: bool = True) -> None:
        """Update IN/OUT points dynamically and immediately seek to IN point without requiring stop and play."""
        self._start_ms = max(0, int(start * 1000))
        self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
        if seek_to_start or not self.is_playing():
            self._player.setPosition(self._start_ms)

    def shutdown(self) -> None:
        try:
            self._player.stop()
            logger.info("[TEST] Shutdown complete")
        except Exception as exc:
            logger.error("[TEST] Shutdown error: %s", exc)
