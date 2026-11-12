"""Test / Pre-Viz Multimedia player – ALWAYS muted by default, never heard by audience.

100% Native Wayland & Linux player using PySide6 QtMultimedia (FFmpeg backend).
Supports full Pre-Viz auditioning of perceptual fades, volume/opacity keyframe
envelopes, and virtual sections A/B/C while strictly honoring the preview mute switch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaPlayer

from engine.envelope import SectionSequencer, evaluate_cue_level
from models.cue import CueSection

logger = logging.getLogger(__name__)


class _TestSignals(QObject):
    """Qt signals emitted by the test/preview player."""
    position_changed = Signal(float)
    duration_changed = Signal(float)
    section_changed = Signal(int)
    eof_reached = Signal()
    error_occurred = Signal(str)


class TestPlayer(QObject):
    """Multimedia player for PRE-VIZ / TEST preview (silent by default)."""

    def __init__(self, video_widget: Optional[Any] = None,
                 video_output: Optional[Any] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.signals = _TestSignals()
        self._video_output = video_output or video_widget
        self._opacity_cb: Optional[Callable[[float], None]] = None
        self._audio_device: Optional[QAudioDevice] = None

        self._is_muted: bool = True
        self._preview_volume: float = 0.8
        self._start_ms: int = 0
        self._end_ms: Optional[int] = None
        self._duration_sec: float = 0.0
        self._is_looping: bool = False
        self._loop_count: int = 0
        self._current_loop_iteration: int = 0

        # Preview envelope & section state (mirrors live automation accurately)
        self._base_volume: float = 1.0
        self._base_opacity: float = 1.0
        self._fade_in_sec: float = 0.0
        self._fade_out_sec: float = 0.0
        self._fade_curve: str = "log"
        self._volume_points: list[list[float]] = []
        self._opacity_points: list[list[float]] = []
        self._sections_cfg: list[CueSection] = []
        self._is_video_cue: bool = False
        self._last_emitted_opacity: Optional[float] = None
        self._sequencer = SectionSequencer()

        self._driver_timer = QTimer(self)
        self._driver_timer.setInterval(20)
        self._driver_timer.timeout.connect(self._on_driver_tick)

        self._setup_player()

    def _setup_player(self) -> None:
        try:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            if self._audio_device is not None and not self._audio_device.isNull():
                self._audio.setDevice(self._audio_device)
            self._player.setAudioOutput(self._audio)

            if self._video_output is not None:
                self._player.setVideoOutput(self._video_output)

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
        self._video_output = video_output
        self._player.setVideoOutput(video_output)

    def set_video_widget(self, video_widget: Any) -> None:
        self.set_video_output(video_widget)

    def set_opacity_callback(self, callback: Optional[Callable[[float], None]]) -> None:
        self._opacity_cb = callback

    def set_audio_device(self, device: Optional[QAudioDevice]) -> None:
        """Assign preview / pre-viz audio device (e.g. Headphones / PFL monitor)."""
        self._audio_device = device
        if self._audio is not None and device is not None and not device.isNull():
            self._audio.setDevice(device)
        logger.info("[TEST] Preview audio device assigned: %s", device.description() if device and not device.isNull() else "Default")

    def set_mute(self, is_muted: bool) -> None:
        self._is_muted = is_muted
        if is_muted:
            self._enforce_mute()
        else:
            self._apply_envelope_at(self._player.position() / 1000.0)
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
                self._audio.setVolume(self._preview_volume * self._base_volume)
        except Exception:
            pass

    # ── Automation & Sections ─────────────────────────────────────────

    def configure_automation(
        self,
        *,
        base_volume: float = 1.0,
        base_opacity: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
        fade_curve: str = "log",
        volume_points: Sequence[Sequence[float]] = (),
        opacity_points: Sequence[Sequence[float]] = (),
        sections: Sequence[CueSection] = (),
        is_video: bool = False,
    ) -> None:
        self._base_volume = max(0.0, min(1.0, float(base_volume)))
        self._base_opacity = max(0.0, min(1.0, float(base_opacity)))
        self._fade_in_sec = max(0.0, float(fade_in))
        self._fade_out_sec = max(0.0, float(fade_out))
        self._fade_curve = fade_curve if fade_curve in ("log", "scurve", "linear") else "log"
        self._volume_points = [list(p) for p in volume_points]
        self._opacity_points = [list(p) for p in opacity_points]
        self._sections_cfg = [CueSection(**s.to_dict()) for s in sections]
        self._is_video_cue = is_video
        self._last_emitted_opacity = None
        self._sequencer.configure(self._sections_cfg, self._start_ms / 1000.0, self._effective_end_sec())
        self._apply_envelope_at(self._player.position() / 1000.0)
        self._ensure_driver_timer()

    def hot_update_automation(
        self,
        *,
        base_volume: Optional[float] = None,
        base_opacity: Optional[float] = None,
        fade_in: Optional[float] = None,
        fade_out: Optional[float] = None,
        fade_curve: Optional[str] = None,
        volume_points: Optional[Sequence[Sequence[float]]] = None,
        opacity_points: Optional[Sequence[Sequence[float]]] = None,
        sections: Optional[Sequence[CueSection]] = None,
    ) -> None:
        if base_volume is not None:
            self._base_volume = max(0.0, min(1.0, float(base_volume)))
        if base_opacity is not None:
            self._base_opacity = max(0.0, min(1.0, float(base_opacity)))
        if fade_in is not None:
            self._fade_in_sec = max(0.0, float(fade_in))
        if fade_out is not None:
            self._fade_out_sec = max(0.0, float(fade_out))
        if fade_curve is not None:
            self._fade_curve = fade_curve if fade_curve in ("log", "scurve", "linear") else "log"
        if volume_points is not None:
            self._volume_points = [list(p) for p in volume_points]
        if opacity_points is not None:
            self._opacity_points = [list(p) for p in opacity_points]
        if sections is not None:
            self._sections_cfg = [CueSection(**s.to_dict()) for s in sections]
            self._sequencer.update_live_sections(self._sections_cfg, self._effective_end_sec())
        self._apply_envelope_at(self._player.position() / 1000.0)
        self._ensure_driver_timer()

    def jump_to_section(self, section_index: int) -> Optional[float]:
        if not self._sequencer.active:
            return None
        target_sec = self._sequencer.jump_to(section_index)
        if target_sec is None:
            return None
        self.seek(target_sec)
        self.signals.section_changed.emit(self._sequencer.current_index)
        return target_sec

    def break_section_loop(self) -> Optional[float]:
        if not self._sequencer.active:
            return None
        action, _idx, target_sec = self._sequencer.break_loop_to_next()
        if action == "EOF" or target_sec is None:
            self._handle_eof()
            return None
        self.seek(target_sec)
        self.signals.section_changed.emit(self._sequencer.current_index)
        return target_sec

    def _effective_end_sec(self) -> float:
        if self._end_ms is not None and self._end_ms > self._start_ms:
            return self._end_ms / 1000.0
        if self._duration_sec > 0:
            return self._duration_sec
        return max(self._start_ms / 1000.0 + 0.1, 600.0)

    def _needs_driver(self) -> bool:
        return bool(
            self._sequencer.active
            or self._fade_in_sec > 0
            or self._fade_out_sec > 0
            or self._volume_points
            or (self._is_video_cue and self._opacity_points)
            or self._end_ms is not None
        )

    def _ensure_driver_timer(self) -> None:
        if self._needs_driver() and self.is_playing():
            if not self._driver_timer.isActive():
                self._driver_timer.start()
        elif not self.is_playing() or not self._needs_driver():
            self._driver_timer.stop()

    def _apply_envelope_at(self, pos_sec: float) -> None:
        looping_inf = self._is_looping and self._loop_count <= 0
        has_inf_sec = any(s.loops == 0 and not s.skip for s in self._sections_cfg)
        allow_fo = (not looping_inf) and (not has_inf_sec)
        allow_fi = (self._current_loop_iteration == 0)

        if self._is_muted:
            self._audio.setMuted(True)
            self._audio.setVolume(0.0)
        else:
            gain = evaluate_cue_level(
                pos_sec,
                start_sec=self._start_ms / 1000.0,
                end_sec=self._end_ms / 1000.0 if self._end_ms else None,
                duration_sec=self._duration_sec,
                fade_in=self._fade_in_sec if allow_fi else 0.0,
                fade_out=self._fade_out_sec if allow_fo else 0.0,
                fade_curve=self._fade_curve,
                points=self._volume_points,
                base_level=self._base_volume,
                apply_fade_out_at_end=allow_fo,
            )
            self._audio.setMuted(False)
            self._audio.setVolume(self._preview_volume * gain)

        if self._is_video_cue and self._opacity_cb is not None and not self.is_idle():
            # When actively paused before playback, keep exact opacity or preview envelope
            op = evaluate_cue_level(
                pos_sec,
                start_sec=self._start_ms / 1000.0,
                end_sec=self._end_ms / 1000.0 if self._end_ms else None,
                duration_sec=self._duration_sec,
                fade_in=self._fade_in_sec if allow_fi else 0.0,
                fade_out=self._fade_out_sec if allow_fo else 0.0,
                fade_curve=self._fade_curve,
                points=self._opacity_points,
                base_level=self._base_opacity,
                apply_fade_out_at_end=allow_fo,
            )
            if self._last_emitted_opacity is None or abs(op - self._last_emitted_opacity) >= 0.004:
                self._last_emitted_opacity = op
                self._opacity_cb(op)

    def _check_boundaries(self, pos_ms: int) -> None:
        if not self.is_playing():
            return

        if self._sequencer.active:
            cur_end = self._sequencer.active_end_sec()
            if cur_end > 0 and pos_ms >= int(cur_end * 1000) - 18:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                if action == "EOF":
                    self._handle_eof()
                    return
                if next_idx is not None:
                    self.signals.section_changed.emit(next_idx)
                if action == "JUMP" and target_sec is not None:
                    self._player.setPosition(int(round(target_sec * 1000)))
            return

        if self._end_ms is not None and pos_ms >= self._end_ms - 18:
            if self._is_looping:
                if self._loop_count > 0:
                    self._current_loop_iteration += 1
                    if self._current_loop_iteration >= self._loop_count:
                        self._handle_eof()
                        return
                self._player.setPosition(self._start_ms)
            else:
                self._handle_eof()

    def _handle_eof(self) -> None:
        self._driver_timer.stop()
        self._player.pause()
        target = (
            int(round(self._sequencer.active_start_sec() * 1000))
            if self._sequencer.active
            else self._start_ms
        )
        self._player.setPosition(target)
        self.signals.eof_reached.emit()

    # ── Signal Handlers ───────────────────────────────────────────────

    def _on_driver_tick(self) -> None:
        if not self.is_playing():
            self._driver_timer.stop()
            return
        pos_ms = self._player.position()
        self._apply_envelope_at(pos_ms / 1000.0)
        self._check_boundaries(pos_ms)

    def _on_position_changed(self, pos_ms: int) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return
        pos_sec = pos_ms / 1000.0
        self.signals.position_changed.emit(pos_sec)
        self._check_boundaries(pos_ms)

    def _on_duration_changed(self, dur_ms: int) -> None:
        if dur_ms > 0:
            self._duration_sec = dur_ms / 1000.0
            if self._sections_cfg:
                self._sequencer.update_live_sections(self._sections_cfg, self._effective_end_sec())
            self.signals.duration_changed.emit(self._duration_sec)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if self._start_ms > 0:
                self._player.setPosition(self._start_ms)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._sequencer.active:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                if action == "EOF":
                    self._driver_timer.stop()
                    self.signals.eof_reached.emit()
                elif target_sec is not None:
                    if next_idx is not None:
                        self.signals.section_changed.emit(next_idx)
                    self._player.setPosition(int(round(target_sec * 1000)))
                    self._player.play()
            elif not self._is_looping:
                self._driver_timer.stop()
                self.signals.eof_reached.emit()

    def _on_error_occurred(self, error: QMediaPlayer.Error, msg: str) -> None:
        logger.error("[TEST] Preview error (%s): %s", error, msg)
        self.signals.error_occurred.emit(msg or str(error))

    # ── Public API ────────────────────────────────────────────────────

    def load(self, file_path: str, start: float = 0.0,
             end: Optional[float] = None, pause: bool = False) -> None:
        """Load a media file for preview."""
        self._enforce_mute()
        self._driver_timer.stop()
        try:
            self._start_ms = max(0, int(start * 1000))
            self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
            self._duration_sec = 0.0
            self._current_loop_iteration = 0
            self._last_emitted_opacity = None

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
                pos_ms = self._start_ms
            self._apply_envelope_at(pos_ms / 1000.0)
            self._player.play()
            self._ensure_driver_timer()
            if self._sequencer.active:
                self.signals.section_changed.emit(self._sequencer.current_index)
            logger.debug("[TEST] play()")
        except Exception as exc:
            logger.error("[TEST] play() failed: %s", exc, exc_info=True)

    def pause(self) -> None:
        self._driver_timer.stop()
        self._enforce_mute()
        try:
            self._player.pause()
            logger.debug("[TEST] pause()")
        except Exception as exc:
            logger.error("[TEST] pause() failed: %s", exc, exc_info=True)

    def stop(self) -> None:
        self._driver_timer.stop()
        self._enforce_mute()
        try:
            self._player.stop()
            logger.debug("[TEST] stop()")
        except Exception as exc:
            logger.error("[TEST] stop() failed: %s", exc, exc_info=True)

    def seek(self, position: float) -> None:
        self._enforce_mute()
        try:
            pos_ms = max(0, int(position * 1000))
            if (
                self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
                and self._player.source().isValid()
            ):
                self._player.pause()
            self._player.setPosition(pos_ms)
            self._apply_envelope_at(position)
        except Exception as exc:
            logger.error("[TEST] seek() failed: %s", exc, exc_info=True)

    def set_loop(self, loop: bool, loop_count: int = 0) -> None:
        self._enforce_mute()
        try:
            self._is_looping = loop
            self._loop_count = loop_count
            self._current_loop_iteration = 0
            if self._sequencer.active:
                self._player.setLoops(QMediaPlayer.Loops.Once)
                return
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
        """Update IN/OUT points dynamically; seek to start only when requested."""
        self._start_ms = max(0, int(start * 1000))
        self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
        if self._sections_cfg:
            self._sequencer.configure(self._sections_cfg, start, self._effective_end_sec())
        if seek_to_start:
            self._player.setPosition(self._start_ms)

    def shutdown(self) -> None:
        try:
            self._driver_timer.stop()
            self._player.stop()
            logger.info("[TEST] Shutdown complete")
        except Exception as exc:
            logger.error("[TEST] Shutdown error: %s", exc)
