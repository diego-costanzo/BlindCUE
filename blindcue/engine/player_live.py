"""Live Multimedia player – drives the external output window (Layer 1-3).

100% Native Wayland & Linux player using PySide6 QtMultimedia (FFmpeg backend).
Supports perceptual audio/opacity fade ramps, granular keyframe envelopes,
contiguous virtual sections (A/B/C...) with lazy Dual-Deck pre-cue anti-stutter
handoff, and crash-safe recovery in live shows.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from engine.envelope import SectionSequencer, evaluate_cue_level
from models.cue import CueSection

logger = logging.getLogger(__name__)


class _PlayerSignals(QObject):
    """Qt signals emitted by the live player."""
    position_changed = Signal(float)   # current playback position (seconds)
    duration_changed = Signal(float)   # total duration (seconds)
    section_changed = Signal(int)      # active section index inside cue
    eof_reached = Signal()             # playback finished / reached end
    error_occurred = Signal(str)       # human-readable error message


class LivePlayer(QObject):
    """Multimedia player for the LIVE output (audio + video on external screen)."""

    def __init__(self, video_widget: Optional[Any] = None,
                 video_output: Optional[Any] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.signals = _PlayerSignals()
        self._video_output = video_output or video_widget
        self._standby_video_output: Optional[Any] = None
        self._deck_switch_cb: Optional[Callable[[int], None]] = None
        self._opacity_cb: Optional[Callable[[float], None]] = None

        self._fade_timer: Optional[QTimer] = None
        self._start_ms: int = 0
        self._end_ms: Optional[int] = None
        self._duration_sec: float = 0.0
        self._file_path: str = ""
        self._is_looping: bool = False
        self._loop_count: int = 0
        self._current_loop_iteration: int = 0

        # Lazy standby deck for pre-cued anti-stutter jumps (allocated only when needed)
        self._standby_player: Optional[QMediaPlayer] = None
        self._standby_audio: Optional[QAudioOutput] = None
        self._standby_target_ms: Optional[int] = None
        self._standby_ready: bool = False
        self._active_deck: int = 0  # 0 = primary, 1 = standby deck

        # Automation & sections state
        self._base_volume: float = 1.0
        self._base_opacity: float = 1.0
        self._fade_in_sec: float = 0.0
        self._fade_out_sec: float = 0.0
        self._fade_curve: str = "log"
        self._volume_points: list[list[float]] = []
        self._opacity_points: list[list[float]] = []
        self._sections_cfg: list[CueSection] = []
        self._is_video_cue: bool = False
        self._apply_fade_in: bool = True
        self._apply_fade_out_at_end: bool = True
        self._last_emitted_opacity: Optional[float] = None
        self._sequencer = SectionSequencer()
        self._manual_fade_active: bool = False

        self._driver_timer = QTimer(self)
        self._driver_timer.setInterval(20)  # 50 Hz precision poll + envelope
        self._driver_timer.timeout.connect(self._on_driver_tick)

        self._setup_player()

    def _setup_player(self) -> None:
        try:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)

            if self._video_output is not None:
                self._player.setVideoOutput(self._video_output)

            self._player.positionChanged.connect(lambda ms: self._on_deck_pos(0, ms))
            self._player.durationChanged.connect(lambda ms: self._on_deck_dur(0, ms))
            self._player.mediaStatusChanged.connect(lambda st: self._on_deck_status(0, st))
            self._player.errorOccurred.connect(lambda err, msg: self._on_deck_error(0, err, msg))

            logger.info("[LIVE] Native Wayland Multimedia player initialised")
        except Exception as exc:
            logger.critical("[LIVE] Failed to initialise QtMultimedia: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Live Player init failed: {exc}")

    def _ensure_standby_deck(self) -> None:
        if self._standby_player is not None:
            return
        self._standby_player = QMediaPlayer(self)
        self._standby_audio = QAudioOutput(self)
        self._standby_audio.setVolume(0.0)
        self._standby_player.setAudioOutput(self._standby_audio)
        if self._standby_video_output is not None:
            self._standby_player.setVideoOutput(self._standby_video_output)
        self._standby_player.positionChanged.connect(lambda ms: self._on_deck_pos(1, ms))
        self._standby_player.durationChanged.connect(lambda ms: self._on_deck_dur(1, ms))
        self._standby_player.mediaStatusChanged.connect(lambda st: self._on_deck_status(1, st))
        self._standby_player.errorOccurred.connect(lambda err, msg: self._on_deck_error(1, err, msg))

    def _deck_pair(self, idx: Optional[int] = None) -> tuple[QMediaPlayer, QAudioOutput]:
        target = self._active_deck if idx is None else idx
        if target == 1 and self._standby_player is not None and self._standby_audio is not None:
            return self._standby_player, self._standby_audio
        return self._player, self._audio

    def _idle_deck_idx(self) -> int:
        return 1 if self._active_deck == 0 else 0

    def set_video_output(self, video_output: Any) -> None:
        self._video_output = video_output
        self._player.setVideoOutput(video_output)

    def set_video_widget(self, video_widget: Any) -> None:
        self.set_video_output(video_widget)

    def set_secondary_video_output(self, video_output: Any) -> None:
        self._standby_video_output = video_output
        if self._standby_player is not None:
            self._standby_player.setVideoOutput(video_output)

    def set_deck_switch_callback(self, callback: Optional[Callable[[int], None]]) -> None:
        self._deck_switch_cb = callback

    def set_opacity_callback(self, callback: Optional[Callable[[float], None]]) -> None:
        self._opacity_cb = callback

    # ── Automation & Section Configuration ────────────────────────────

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
        apply_fade_in: bool = True,
        apply_fade_out_at_end: bool = True,
    ) -> None:
        """Configure cue automation curve, fades, and contiguous virtual sections."""
        self._base_volume = max(0.0, min(1.0, float(base_volume)))
        self._base_opacity = max(0.0, min(1.0, float(base_opacity)))
        self._fade_in_sec = max(0.0, float(fade_in))
        self._fade_out_sec = max(0.0, float(fade_out))
        self._fade_curve = fade_curve if fade_curve in ("log", "scurve", "linear") else "log"
        self._volume_points = [list(p) for p in volume_points]
        self._opacity_points = [list(p) for p in opacity_points]
        self._sections_cfg = [CueSection(**s.to_dict()) for s in sections]
        self._is_video_cue = is_video
        self._apply_fade_in = apply_fade_in
        self._apply_fade_out_at_end = apply_fade_out_at_end
        self._last_emitted_opacity = None

        start_s = self._start_ms / 1000.0
        eff_end = self._effective_end_sec()
        self._sequencer.configure(self._sections_cfg, start_s, eff_end)
        if self._sequencer.active:
            first_start = self._sequencer.active_start_sec()
            self._start_ms = max(0, int(first_start * 1000))
            if self._sequencer.current_index > 0:
                p, _ = self._deck_pair()
                p.setPosition(self._start_ms)
            self._pre_cue_next_target()

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
        """Update envelope points or section loops on the fly without interrupting playback."""
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
            self._pre_cue_next_target()
        self._ensure_driver_timer()

    def jump_to_section(self, section_index: int) -> bool:
        """Jump live playback immediately to *section_index*."""
        if not self._sequencer.active:
            return False
        target_sec = self._sequencer.jump_to(section_index)
        if target_sec is None:
            return False
        self._execute_jump_ms(int(round(target_sec * 1000)))
        self.signals.section_changed.emit(self._sequencer.current_index)
        return True

    def break_section_loop(self) -> bool:
        """Exit infinite/repeated section cleanly onto the next playable section."""
        if not self._sequencer.active:
            return False
        action, _idx, target_sec = self._sequencer.break_loop_to_next()
        if action == "EOF" or target_sec is None:
            self._handle_cue_finished()
            return True
        self._execute_jump_ms(int(round(target_sec * 1000)))
        self.signals.section_changed.emit(self._sequencer.current_index)
        return True

    def active_section_index(self) -> int:
        return self._sequencer.current_index if self._sequencer.active else -1

    # ── Internal Helpers ──────────────────────────────────────────────

    def _effective_end_sec(self) -> float:
        if self._end_ms is not None and self._end_ms > self._start_ms:
            return self._end_ms / 1000.0
        if self._duration_sec > 0:
            return self._duration_sec
        return max(self._start_ms / 1000.0 + 0.1, 600.0)

    def _needs_precision_driver(self) -> bool:
        return bool(
            self._sequencer.active
            or self._fade_in_sec > 0
            or self._fade_out_sec > 0
            or self._volume_points
            or (self._is_video_cue and self._opacity_points)
            or self._end_ms is not None
            or self._is_looping
        )

    def _ensure_driver_timer(self) -> None:
        player, _ = self._deck_pair()
        if (
            self._needs_precision_driver()
            and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        ):
            if not self._driver_timer.isActive():
                self._driver_timer.start()
        elif not self._needs_precision_driver():
            self._driver_timer.stop()

    def _pre_cue_next_target(self) -> None:
        """Pre-load and pause the idle deck at the next jump target for near-zero stutter."""
        target_sec: Optional[float] = None
        if self._sequencer.active:
            target_sec = self._sequencer.peek_next_jump_target()
        elif self._is_video_cue and self._is_looping and self._file_path:
            target_sec = self._start_ms / 1000.0

        if target_sec is None or not self._file_path or not os.path.isfile(self._file_path):
            return

        target_ms = max(0, int(round(target_sec * 1000)))
        self._ensure_standby_deck()
        idle_idx = self._idle_deck_idx()
        idle_player, idle_audio = self._deck_pair(idle_idx)
        idle_audio.setVolume(0.0)
        self._standby_target_ms = target_ms

        want_url = QUrl.fromLocalFile(self._file_path)
        if idle_player.source() != want_url:
            self._standby_ready = False
            idle_player.setSource(want_url)
            idle_player.pause()
        else:
            self._standby_ready = True
            idle_player.pause()
            idle_player.setPosition(target_ms)

    def _execute_jump_ms(self, target_ms: int) -> None:
        """Switch to pre-cued idle deck when parked on target, otherwise fast direct seek."""
        active_p, active_a = self._deck_pair(self._active_deck)
        idle_idx = self._idle_deck_idx()
        idle_p, idle_a = self._deck_pair(idle_idx)

        can_swap = (
            self._standby_player is not None
            and self._standby_ready
            and self._standby_target_ms is not None
            and abs(self._standby_target_ms - target_ms) <= 60
        )
        if can_swap:
            # Evaluate volume/opacity right at destination timestamp
            cur_vol = self._compute_audio_gain(target_ms / 1000.0)
            idle_a.setVolume(cur_vol)
            if self._is_video_cue and self._deck_switch_cb is not None:
                self._deck_switch_cb(idle_idx)
            idle_p.play()
            active_a.setVolume(0.0)
            active_p.pause()
            self._active_deck = idle_idx
            self._standby_target_ms = None
            self._apply_envelope_at(target_ms / 1000.0)
            self._pre_cue_next_target()
            return

        # Direct seek fallback (seamless fallback if user clicked arbitrary section fast)
        active_p.setPosition(target_ms)
        self._apply_envelope_at(target_ms / 1000.0)
        self._pre_cue_next_target()

    def _compute_audio_gain(self, pos_sec: float) -> float:
        looping_inf = self._is_looping and self._loop_count <= 0
        has_inf_section = any(s.loops == 0 and not s.skip for s in self._sections_cfg)
        allow_fo = self._apply_fade_out_at_end and (not looping_inf) and (not has_inf_section)
        allow_fi = self._apply_fade_in and (self._current_loop_iteration == 0)
        return evaluate_cue_level(
            pos_sec,
            start_sec=self._start_ms / 1000.0 if not self._sequencer.active else self._sequencer.cue_in,
            end_sec=self._end_ms / 1000.0 if self._end_ms else None,
            duration_sec=self._duration_sec,
            fade_in=self._fade_in_sec if allow_fi else 0.0,
            fade_out=self._fade_out_sec if allow_fo else 0.0,
            fade_curve=self._fade_curve,
            points=self._volume_points,
            base_level=self._base_volume,
            apply_fade_out_at_end=allow_fo,
        )

    def _apply_envelope_at(self, pos_sec: float) -> None:
        if self._manual_fade_active:
            return
        _, audio = self._deck_pair()
        vol = self._compute_audio_gain(pos_sec)
        audio.setVolume(vol)

        if self._is_video_cue and self._opacity_cb is not None:
            looping_inf = self._is_looping and self._loop_count <= 0
            has_inf_section = any(s.loops == 0 and not s.skip for s in self._sections_cfg)
            allow_fo = self._apply_fade_out_at_end and (not looping_inf) and (not has_inf_section)
            allow_fi = self._apply_fade_in and (self._current_loop_iteration == 0)
            op = evaluate_cue_level(
                pos_sec,
                start_sec=self._start_ms / 1000.0 if not self._sequencer.active else self._sequencer.cue_in,
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
        player, _ = self._deck_pair()
        if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return

        if self._sequencer.active:
            cur_end_sec = self._sequencer.active_end_sec()
            if cur_end_sec > 0 and pos_ms >= int(cur_end_sec * 1000) - 18:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                if action == "EOF":
                    self._handle_cue_finished()
                    return
                if next_idx is not None:
                    self.signals.section_changed.emit(next_idx)
                if action == "CONTINUE":
                    self._pre_cue_next_target()
                    return
                if action == "JUMP" and target_sec is not None:
                    self._execute_jump_ms(int(round(target_sec * 1000)))
                    return
            return

        if self._end_ms is not None and pos_ms >= self._end_ms - 18:
            if self._is_looping:
                if self._loop_count > 0:
                    self._current_loop_iteration += 1
                    if self._current_loop_iteration >= self._loop_count:
                        self._handle_cue_finished()
                        return
                self._execute_jump_ms(self._start_ms)
            else:
                self._handle_cue_finished()

    def _handle_cue_finished(self) -> None:
        self._driver_timer.stop()
        player, _ = self._deck_pair()
        player.pause()
        self.signals.eof_reached.emit()

    # ── Signal Handlers ───────────────────────────────────────────────

    def _on_driver_tick(self) -> None:
        player, _ = self._deck_pair()
        if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._driver_timer.stop()
            return
        pos_ms = player.position()
        self._apply_envelope_at(pos_ms / 1000.0)
        self._check_boundaries(pos_ms)

    def _on_deck_pos(self, deck_idx: int, pos_ms: int) -> None:
        if deck_idx != self._active_deck:
            return
        player, _ = self._deck_pair(deck_idx)
        if player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return
        pos_sec = pos_ms / 1000.0
        self.signals.position_changed.emit(pos_sec)
        self._check_boundaries(pos_ms)

    def _on_deck_dur(self, deck_idx: int, dur_ms: int) -> None:
        if deck_idx != self._active_deck or dur_ms <= 0:
            return
        self._duration_sec = dur_ms / 1000.0
        if self._sections_cfg:
            self._sequencer.update_live_sections(self._sections_cfg, self._effective_end_sec())
            self._pre_cue_next_target()
        self.signals.duration_changed.emit(self._duration_sec)

    def _on_deck_status(self, deck_idx: int, status: QMediaPlayer.MediaStatus) -> None:
        if deck_idx != self._active_deck:
            if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
                self._standby_ready = True
                if self._standby_target_ms is not None and self._standby_player is not None:
                    self._standby_player.setPosition(self._standby_target_ms)
            return

        player, _ = self._deck_pair(deck_idx)
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            target = (
                int(round(self._sequencer.active_start_sec() * 1000))
                if self._sequencer.active
                else self._start_ms
            )
            if target > 0:
                player.setPosition(target)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._sequencer.active:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                if action == "EOF":
                    self._driver_timer.stop()
                    self.signals.eof_reached.emit()
                elif target_sec is not None:
                    if next_idx is not None:
                        self.signals.section_changed.emit(next_idx)
                    self._execute_jump_ms(int(round(target_sec * 1000)))
            elif not self._is_looping:
                self._driver_timer.stop()
                self.signals.eof_reached.emit()

    def _on_deck_error(self, deck_idx: int, error: QMediaPlayer.Error, msg: str) -> None:
        if deck_idx != self._active_deck:
            logger.warning("[LIVE] Standby deck warning (%s): %s", error, msg)
            self._standby_ready = False
            return
        logger.error("[LIVE] Playback error (%s): %s", error, msg)
        self.signals.error_occurred.emit(msg or str(error))

    # ── Public Playback API ───────────────────────────────────────────

    def load(self, file_path: str, start: float = 0.0,
             end: Optional[float] = None) -> None:
        """Load a media file cleanly on Deck 0, resetting any standby/fade state."""
        try:
            self._manual_fade_active = False
            self._driver_timer.stop()
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
                self._standby_target_ms = None
                self._standby_ready = False

            self._active_deck = 0
            if self._deck_switch_cb is not None and self._is_video_cue:
                self._deck_switch_cb(0)

            self._file_path = file_path
            self._start_ms = max(0, int(start * 1000))
            self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
            self._duration_sec = 0.0
            self._current_loop_iteration = 0
            self._last_emitted_opacity = None

            self._player.stop()
            url = QUrl.fromLocalFile(file_path)
            if self._player.source() == url:
                # Resetting source forces Qt FFmpeg backend to clear cached EOF state and re-emit durationChanged
                self._player.setSource(QUrl())
            self._player.setSource(url)
            if self._start_ms > 0:
                self._player.setPosition(self._start_ms)

            logger.info("[LIVE] Loaded %s (start=%.1f, end=%s)", file_path, start, end)
        except Exception as exc:
            logger.error("[LIVE] load() failed: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Load failed: {exc}")

    def play(self) -> None:
        """Start or resume playback cleanly with immediate initial envelope gain."""
        try:
            player, _ = self._deck_pair()
            pos_ms = player.position()
            if (self._end_ms is not None and pos_ms >= self._end_ms) or \
               player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                target = (
                    int(round(self._sequencer.active_start_sec() * 1000))
                    if self._sequencer.active
                    else self._start_ms
                )
                player.setPosition(target)
                pos_ms = target

            self._apply_envelope_at(pos_ms / 1000.0)
            if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                player.play()
                logger.debug("[LIVE] play()")
            self._ensure_driver_timer()
            if self._sequencer.active:
                self.signals.section_changed.emit(self._sequencer.current_index)
        except Exception as exc:
            logger.error("[LIVE] play() failed: %s", exc, exc_info=True)

    def pause(self) -> None:
        try:
            self._driver_timer.stop()
            player, _ = self._deck_pair()
            player.pause()
            logger.debug("[LIVE] pause()")
        except Exception as exc:
            logger.error("[LIVE] pause() failed: %s", exc, exc_info=True)

    def is_playing(self) -> bool:
        try:
            player, _ = self._deck_pair()
            return player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            return False

    def is_paused(self) -> bool:
        try:
            player, _ = self._deck_pair()
            return player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        except Exception:
            return False

    def duration_seconds(self) -> float:
        if self._duration_sec > 0:
            return self._duration_sec
        try:
            player, _ = self._deck_pair()
            dur_ms = player.duration()
            return dur_ms / 1000.0 if dur_ms > 0 else 0.0
        except Exception:
            return 0.0

    def stop(self) -> None:
        """Stop all active/standby decks cleanly."""
        try:
            self._manual_fade_active = False
            self._driver_timer.stop()
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()
            self._player.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
                self._standby_target_ms = None
                self._standby_ready = False
            self._active_deck = 0
            self._sections_cfg.clear()
            self._sequencer.configure([], 0.0, 0.0)
            logger.debug("[LIVE] stop()")
        except Exception as exc:
            logger.error("[LIVE] stop() failed: %s", exc, exc_info=True)

    def seek(self, position: float) -> None:
        try:
            player, _ = self._deck_pair()
            ms = max(0, int(position * 1000))
            player.setPosition(ms)
            self._apply_envelope_at(position)
        except Exception as exc:
            logger.error("[LIVE] seek() failed: %s", exc, exc_info=True)

    def set_volume(self, volume: int) -> None:
        """Set live master volume 0-100."""
        try:
            vol_norm = max(0.0, min(1.0, volume / 100.0))
            self._base_volume = vol_norm
            _, audio = self._deck_pair()
            if not self._volume_points and not self._manual_fade_active:
                audio.setVolume(vol_norm)
            else:
                player, _ = self._deck_pair()
                self._apply_envelope_at(player.position() / 1000.0)
        except Exception as exc:
            logger.error("[LIVE] set_volume() failed: %s", exc)

    def set_loop(self, loop: bool, loop_count: int = 0) -> None:
        """Enable or disable seamless looping. When sections exist, section sequencer governs."""
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
            if self._is_video_cue and loop:
                self._pre_cue_next_target()
        except Exception as exc:
            logger.error("[LIVE] set_loop() failed: %s", exc)

    def set_aspect_ratio(self, aspect: Optional[str]) -> None:
        pass

    def set_scale(self, scale: float) -> None:
        pass

    def set_crop(self, crop: Optional[dict]) -> None:
        pass

    def fade_in(self, target_volume: int, duration_sec: float) -> None:
        """Direct manual fade-in helper (also preserved for standalone callers)."""
        try:
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()

            if duration_sec <= 0:
                self.set_volume(target_volume)
                return

            _, audio = self._deck_pair()
            audio.setVolume(0.0)
            target_norm = max(0.0, min(1.0, target_volume / 100.0))
            steps = max(1, int(duration_sec * 25))
            step_interval = int(1000 / 25)
            step_increment = target_norm / steps
            current_step = 0

            self._fade_timer = QTimer(self)

            def _tick() -> None:
                nonlocal current_step
                current_step += 1
                new_vol = min(target_norm, current_step * step_increment)
                self._deck_pair()[1].setVolume(new_vol)
                if current_step >= steps:
                    self._fade_timer.stop()

            self._fade_timer.timeout.connect(_tick)
            self._fade_timer.start(step_interval)
        except Exception as exc:
            logger.error("[LIVE] fade_in() failed: %s", exc)
            self.set_volume(target_volume)

    def fade_out(self, duration_sec: float = 0.2, stop_after: bool = False,
                 callback: Optional[Callable[[], None]] = None) -> None:
        """Smooth manual fade-out (e.g. Cut/Blackout) down to 0 and optional stop."""
        try:
            if self._fade_timer is not None and self._fade_timer.isActive():
                self._fade_timer.stop()

            self._manual_fade_active = True
            _, audio = self._deck_pair()
            start_norm = audio.volume()
            if duration_sec <= 0 or start_norm <= 0:
                audio.setVolume(0.0)
                if stop_after:
                    self.stop()
                if callback is not None:
                    callback()
                return

            steps = max(1, int(duration_sec * 30))
            step_interval = int(1000 / 30)
            step_decrement = start_norm / steps
            current_step = 0

            self._fade_timer = QTimer(self)

            def _tick() -> None:
                nonlocal current_step
                current_step += 1
                new_vol = max(0.0, start_norm - (current_step * step_decrement))
                self._deck_pair()[1].setVolume(new_vol)
                if current_step >= steps:
                    self._fade_timer.stop()
                    self._deck_pair()[1].setVolume(0.0)
                    if stop_after:
                        self.stop()
                    if callback is not None:
                        callback()

            self._fade_timer.timeout.connect(_tick)
            self._fade_timer.start(step_interval)
        except Exception as exc:
            logger.error("[LIVE] fade_out() failed: %s", exc)
            self._deck_pair()[1].setVolume(0.0)
            if stop_after:
                self.stop()
            if callback is not None:
                callback()

    def shutdown(self) -> None:
        try:
            self._driver_timer.stop()
            if self._fade_timer is not None:
                self._fade_timer.stop()
            self._player.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
            logger.info("[LIVE] Shutdown complete")
        except Exception as exc:
            logger.error("[LIVE] Shutdown error: %s", exc)
