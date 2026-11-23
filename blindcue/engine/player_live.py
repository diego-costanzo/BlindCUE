"""Live Multimedia player – drives the external output window (Layer 1-3).

100% Native Wayland & Linux player using PySide6 QtMultimedia (FFmpeg backend).
Supports perceptual audio/opacity fade ramps, granular keyframe envelopes,
contiguous virtual sections (A/B/C...) with lazy Dual-Deck pre-cue anti-stutter
handoff, and crash-safe recovery in live shows.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaPlayer

from engine.envelope import SectionSequencer, evaluate_cue_level
from models.cue import CueSection

logger = logging.getLogger(__name__)


def _pause_unless_at_end(player: QMediaPlayer) -> None:
    """Pause *player*, except when it has already reached the end of the file.

    At EndOfMedia the deck is already stopped. ``pause()`` there makes the Qt
    FFmpeg backend rewind and rebuild its renderers on a worker thread; a
    ``stop()`` that follows (the EOF handler always calls it) then blocks the
    GIL-holding main thread on that worker while the worker waits for the GIL
    to tear down a PySide-wrapped object: a permanent freeze.
    """
    if player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
        player.pause()


class _PlayerSignals(QObject):
    """Qt signals emitted by the live player."""
    position_changed = Signal(float)   # current playback position (seconds)
    duration_changed = Signal(float)   # total duration (seconds)
    section_changed = Signal(int)      # active section index inside cue
    eof_reached = Signal()             # playback finished / reached end
    error_occurred = Signal(str)       # human-readable error message


class LivePlayer(QObject):
    """Multimedia player for the LIVE output (audio + video on external screen)."""

    def __init__(self, video_widget: Any | None = None,
                 video_output: Any | None = None,
                 parent: QObject | None = None) -> None:
        """Create the live player bound to a video output widget."""
        super().__init__(parent)
        self.signals = _PlayerSignals()
        self._video_output = video_output or video_widget
        self._standby_video_output: Any | None = None
        self._deck_switch_cb: Callable[[int], None] | None = None
        self._opacity_cb: Callable[[float], None] | None = None

        self._fade_timer: QTimer | None = None
        self._start_ms: int = 0
        self._end_ms: int | None = None
        self._duration_sec: float = 0.0
        self._file_path: str = ""
        self._is_looping: bool = False
        self._loop_count: int = 0
        self._current_loop_iteration: int = 0

        # Lazy standby deck for pre-cued anti-stutter jumps (allocated only when needed)
        self._audio_device: QAudioDevice | None = None
        self._standby_player: QMediaPlayer | None = None
        self._standby_audio: QAudioOutput | None = None
        self._standby_target_ms: int | None = None
        self._standby_ready: bool = False
        self._standby_seek_pending: bool = False
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
        self._last_emitted_opacity: float | None = None
        self._sequencer = SectionSequencer()
        self._manual_fade_active: bool = False
        # Section boundary latch: after a jump/continuation we must not react to
        # the stale position report of the section we just left, otherwise the
        # sequencer advances twice and silently eats one loop or one cut.
        self._boundary_armed: bool = True
        self._finished: bool = False

        self._driver_timer = QTimer(self)
        self._driver_timer.setInterval(20)  # 50 Hz precision poll + envelope
        self._driver_timer.timeout.connect(self._on_driver_tick)

        # Load watchdog: the Qt FFmpeg backend can leave a source stuck in
        # LoadingMedia when sources are changed in rapid succession (operator
        # mashing GO, or an AUTO-GO landing on the same deck).  Left alone the
        # deck never plays again on that layer; a hard re-open recovers it.
        self._load_watchdog = QTimer(self)
        self._load_watchdog.setSingleShot(True)
        self._load_watchdog.timeout.connect(self._recover_stalled_load)
        self._watchdog_trials: int = 0
        self._watchdog_armed: bool = False
        self._play_started_pos_ms: int = 0
        self._media_progressed: bool = False

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
        if self._audio_device is not None and not self._audio_device.isNull():
            self._standby_audio.setDevice(self._audio_device)
        self._standby_audio.setVolume(0.0)
        self._standby_player.setAudioOutput(self._standby_audio)
        if self._standby_video_output is not None:
            self._standby_player.setVideoOutput(self._standby_video_output)
        self._standby_player.positionChanged.connect(lambda ms: self._on_deck_pos(1, ms))
        self._standby_player.durationChanged.connect(lambda ms: self._on_deck_dur(1, ms))
        self._standby_player.mediaStatusChanged.connect(lambda st: self._on_deck_status(1, st))
        self._standby_player.errorOccurred.connect(lambda err, msg: self._on_deck_error(1, err, msg))

    def _deck_pair(self, idx: int | None = None) -> tuple[QMediaPlayer, QAudioOutput]:
        target = self._active_deck if idx is None else idx
        if target == 1 and self._standby_player is not None and self._standby_audio is not None:
            return self._standby_player, self._standby_audio
        return self._player, self._audio

    def _idle_deck_idx(self) -> int:
        return 1 if self._active_deck == 0 else 0

    def set_video_output(self, video_output: Any) -> None:
        """Route the active deck's video to *video_output* (QGraphicsVideoItem or widget)."""
        self._video_output = video_output
        self._player.setVideoOutput(video_output)

    def set_video_widget(self, video_widget: Any) -> None:
        """Alias of :meth:`set_video_output` kept for callers using widget semantics."""
        self.set_video_output(video_widget)

    def set_secondary_video_output(self, video_output: Any) -> None:
        """Assign the standby deck's video sink so a pre-cued frame is already decoded."""
        self._standby_video_output = video_output
        if self._standby_player is not None:
            self._standby_player.setVideoOutput(video_output)

    def set_deck_switch_callback(self, callback: Callable[[int], None] | None) -> None:
        """Register a callback invoked with the new deck index (0/1) after a handoff.

        The UI uses it to raise/lower the two video layers without a black frame
        during contiguous-section jumps.
        """
        self._deck_switch_cb = callback

    def set_opacity_callback(self, callback: Callable[[float], None] | None) -> None:
        """Register the callback that applies the video opacity envelope (0.0-1.0)."""
        self._opacity_cb = callback

    def set_audio_device(self, device: QAudioDevice | None) -> None:
        """Assign live output audio device (e.g. Master Sala / PA system)."""
        self._audio_device = device
        if self._audio is not None and device is not None and not device.isNull():
            self._audio.setDevice(device)
        if self._standby_audio is not None and device is not None and not device.isNull():
            self._standby_audio.setDevice(device)
        logger.info("[LIVE] Audio device assigned: %s", device.description() if device and not device.isNull() else "Default")

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
        self._boundary_armed = True
        self._finished = False
        if self._sequencer.active:
            first_start = self._sequencer.active_start_sec()
            # Never overwrite ``_start_ms``: it is the cue IN point and the
            # reference used to normalise the sections on every re-configure.
            if first_start * 1000.0 > self._start_ms + 20:
                p, _ = self._deck_pair()
                p.setPosition(int(round(first_start * 1000)))
            self._pre_cue_next_target()

    def hot_update_automation(
        self,
        *,
        base_volume: float | None = None,
        base_opacity: float | None = None,
        fade_in: float | None = None,
        fade_out: float | None = None,
        fade_curve: str | None = None,
        volume_points: Sequence[Sequence[float]] | None = None,
        opacity_points: Sequence[Sequence[float]] | None = None,
        sections: Sequence[CueSection] | None = None,
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
            self._refresh_live_sections()
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
        """Index of the section currently playing, or ``-1`` when the cue has none."""
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
        target_sec: float | None = None
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
            self._standby_seek_pending = True
            idle_player.setSource(want_url)
            idle_player.pause()
        else:
            self._standby_ready = True
            self._standby_seek_pending = False
            idle_player.pause()
            idle_player.setPosition(target_ms)

    def _execute_jump_ms(self, target_ms: int) -> None:
        """Switch to pre-cued idle deck when parked on target, otherwise fast direct seek."""
        self._boundary_armed = False
        self._finished = False
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
        if self._finished:
            return

        if self._sequencer.active:
            cur_end_sec = self._sequencer.active_end_sec()
            end_ms = int(cur_end_sec * 1000)
            if not self._boundary_armed:
                # A jump/continuation was just issued: ignore stale position
                # reports coming from the section we already left.
                if pos_ms >= end_ms - 18:
                    return
                self._boundary_armed = True
            if cur_end_sec > 0 and pos_ms >= end_ms - 18:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                self._boundary_armed = False
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
        self._finished = True
        self._load_watchdog.stop()
        self._watchdog_armed = False
        self._driver_timer.stop()
        player, _ = self._deck_pair()
        _pause_unless_at_end(player)
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
        if pos_ms != self._play_started_pos_ms:
            self._media_progressed = True
        pos_sec = pos_ms / 1000.0
        self.signals.position_changed.emit(pos_sec)
        self._check_boundaries(pos_ms)

    def _on_deck_dur(self, deck_idx: int, dur_ms: int) -> None:
        if deck_idx != self._active_deck or dur_ms <= 0:
            return
        self._duration_sec = dur_ms / 1000.0
        self._refresh_live_sections()
        self.signals.duration_changed.emit(self._duration_sec)

    def _refresh_live_sections(self) -> None:
        """Re-normalise sections mid-flight and leave a section just marked as skip."""
        if not self._sections_cfg:
            return
        before = self._sequencer.current_index
        self._sequencer.update_live_sections(self._sections_cfg, self._effective_end_sec())
        if self._sequencer.active and self._sequencer.current_index != before:
            self._execute_jump_ms(int(round(self._sequencer.active_start_sec() * 1000)))
            # The operator just marked the playing section as skip: the panel
            # must follow the cue to its new section, exactly as a manual jump.
            self.signals.section_changed.emit(self._sequencer.current_index)
            return
        self._pre_cue_next_target()

    def _on_deck_status(self, deck_idx: int, status: QMediaPlayer.MediaStatus) -> None:
        if deck_idx != self._active_deck:
            if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
                self._standby_ready = True
                if self._standby_seek_pending and self._standby_target_ms is not None:
                    self._standby_seek_pending = False
                    idle_p, _ = self._deck_pair(deck_idx)
                    idle_p.setPosition(self._standby_target_ms)
            return
        if self._finished:
            return

        player, _ = self._deck_pair(deck_idx)
        if status == QMediaPlayer.MediaStatus.BufferedMedia:
            self._media_progressed = True
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            target = (
                int(round(self._sequencer.active_start_sec() * 1000))
                if self._sequencer.active
                else self._start_ms
            )
            if target > 0:
                player.setPosition(target)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # A stale end-of-media report can arrive right after a jump issued at
            # the same edge: honour the latch or the sequencer advances twice.
            if not self._boundary_armed:
                return
            if self._sequencer.active:
                action, next_idx, target_sec = self._sequencer.advance_at_boundary()
                self._boundary_armed = False
                if action == "EOF":
                    self._handle_cue_finished()
                elif target_sec is not None:
                    if next_idx is not None:
                        self.signals.section_changed.emit(next_idx)
                    self._execute_jump_ms(int(round(target_sec * 1000)))
            elif not self._is_looping:
                self._handle_cue_finished()

    def _on_deck_error(self, deck_idx: int, error: QMediaPlayer.Error, msg: str) -> None:
        if deck_idx != self._active_deck:
            logger.warning("[LIVE] Standby deck warning (%s): %s", error, msg)
            self._standby_ready = False
            return
        logger.error("[LIVE] Playback error (%s): %s", error, msg)
        self.signals.error_occurred.emit(msg or str(error))

    # ── Public Playback API ───────────────────────────────────────────

    def _stop_fade_timer(self) -> None:
        """Stop and schedule deletion of any active manual fade timer."""
        old = self._fade_timer
        self._fade_timer = None
        if old is not None:
            if old.isActive():
                old.stop()
            old.deleteLater()

    def load(self, file_path: str, start: float = 0.0,
             end: float | None = None) -> None:
        """Load a media file cleanly on Deck 0, resetting any standby/fade state."""
        try:
            self._manual_fade_active = False
            self._boundary_armed = True
            self._finished = False
            self._driver_timer.stop()
            self._stop_fade_timer()
            if self._standby_player is not None:
                self._standby_player.stop()
                self._standby_target_ms = None
                self._standby_ready = False
                self._standby_seek_pending = False

            # Sections describe the cue being REPLACED, not the incoming media.
            # Left installed, the LoadedMedia handler seeks the fresh file to the
            # previous cue's active section start, so a direct replacement (GO on
            # a layer that is still playing) starts the new cue minutes in.
            # Every caller re-applies the new cue's sections right after load().
            self._sections_cfg.clear()
            self._sequencer.configure([], 0.0, 0.0)

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
            current = self._player.source()
            status = self._player.mediaStatus()
            if current != url or status in (
                QMediaPlayer.MediaStatus.EndOfMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
            ):
                if current == url:
                    # EOF/error: the source is stale, clear it so the backend
                    # really re-opens the file from scratch.
                    self._player.setSource(QUrl())
                self._player.setSource(url)
            else:
                # Same file already loaded (GO repeated on the same cue, or a
                # second cue pointing at the same media): re-issuing setSource
                # churns the FFmpeg demuxer, and a few hundred of them leave
                # the backend permanently stuck in LoadingMedia. Keep the
                # loaded source and just re-seat the playhead below.
                logger.debug("[LIVE] Reusing loaded source for %s", file_path)
                # The backend keeps the decoded metadata when the source is
                # reused, so durationChanged never fires again: publish the
                # known duration, otherwise every listener waiting for the
                # media to be ready (section grid, UI, harnesses) hangs.
                reused_ms = self._player.duration()
                if reused_ms > 0:
                    self._duration_sec = reused_ms / 1000.0
                    self.signals.duration_changed.emit(self._duration_sec)
            # Re-seat the playhead explicitly: when the url is unchanged the
            # backend keeps the previous position and would resume mid-file.
            self._player.setPosition(self._start_ms)

            self._load_watchdog.stop()
            self._watchdog_trials = 0
            self._watchdog_armed = False
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
                # Replay from the top: the sequencer restarts on the first
                # playable section, never on the last one that was played.
                if self._sequencer.active:
                    self._sequencer.restart()
                target = (
                    int(round(self._sequencer.active_start_sec() * 1000))
                    if self._sequencer.active
                    else self._start_ms
                )
                player.setPosition(target)
                pos_ms = target
            elif self._sequencer.active:
                # The deck may sit outside the indexed section (stop/scrub):
                # re-align so skip/loop settings are honoured from the first frame.
                idx = self._sequencer.section_index_for_time(pos_ms / 1000.0)
                if idx is not None and idx != self._sequencer.current_index:
                    target = self._sequencer.jump_to(idx)
                    if target is not None and target * 1000.0 > pos_ms + 20:
                        pos_ms = int(round(target * 1000))
                        player.setPosition(pos_ms)
            self._finished = False
            self._boundary_armed = True
            self._play_started_pos_ms = pos_ms
            self._media_progressed = (
                player.mediaStatus() == QMediaPlayer.MediaStatus.BufferedMedia
            )

            self._apply_envelope_at(pos_ms / 1000.0)
            if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                player.play()
                logger.debug("[LIVE] play()")
            self._arm_load_watchdog()
            self._ensure_driver_timer()
            if self._sequencer.active:
                self.signals.section_changed.emit(self._sequencer.current_index)
        except Exception as exc:
            logger.error("[LIVE] play() failed: %s", exc, exc_info=True)

    def _arm_load_watchdog(self) -> None:
        """Watch the deck after play(): recover if the backend never starts."""
        if self._watchdog_trials >= 3:
            return
        self._watchdog_armed = True
        self._load_watchdog.start(3500)

    def _recover_stalled_load(self) -> None:
        """Hard re-open the active deck when a source stays stuck loading."""
        try:
            if not self._watchdog_armed:
                # A stop()/PANIC landed after the timeout was queued: never
                # resurrect a cue the operator has just silenced.
                return
            self._watchdog_armed = False
            if not self._file_path or self._manual_fade_active:
                return
            player, _ = self._deck_pair()
            st = player.mediaStatus()
            if st == QMediaPlayer.MediaStatus.EndOfMedia:
                # Legitimately finished: never restart a cue that reached its end.
                return
            # In Qt6, playbackState() switches to PlayingState immediately on
            # play(), even while mediaStatus() is wedged in LoadingMedia or
            # StalledMedia. Only consider playback healthy when media actually
            # buffered/progressed.
            stalled_statuses = (
                QMediaPlayer.MediaStatus.LoadingMedia,
                QMediaPlayer.MediaStatus.StalledMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
                QMediaPlayer.MediaStatus.NoMedia,
            )
            if (
                self._media_progressed
                and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and st not in stalled_statuses
            ):
                return
            self._watchdog_trials += 1
            logger.warning(
                "[LIVE] %s non parte (status=%s): riapertura forzata %d/3",
                os.path.basename(self._file_path),
                st.name,
                self._watchdog_trials,
            )
            target = (
                int(round(self._sequencer.active_start_sec() * 1000))
                if self._sequencer.active
                else max(self._start_ms, player.position())
            )
            self._media_progressed = False
            self._play_started_pos_ms = target
            player.stop()
            player.setSource(QUrl())
            player.setSource(QUrl.fromLocalFile(self._file_path))
            player.setPosition(target)
            player.play()
            if self._watchdog_trials >= 3:
                self.signals.error_occurred.emit(
                    f"Impossibile avviare '{os.path.basename(self._file_path)}': "
                    "file danneggiato o codec non supportato"
                )
            else:
                self._arm_load_watchdog()
        except Exception as exc:
            logger.error("[LIVE] watchdog recovery failed: %s", exc, exc_info=True)

    def pause(self) -> None:
        """Pause playback and stop the precision driver, keeping the current position."""
        try:
            self._load_watchdog.stop()
            self._watchdog_armed = False
            self._driver_timer.stop()
            player, _ = self._deck_pair()
            _pause_unless_at_end(player)
            logger.debug("[LIVE] pause()")
        except Exception as exc:
            logger.error("[LIVE] pause() failed: %s", exc, exc_info=True)

    def is_playing(self) -> bool:
        """True while the active deck is actually playing (never raises)."""
        try:
            player, _ = self._deck_pair()
            return player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            logger.debug("[LIVE] is_playing() probe failed", exc_info=True)
            return False

    def is_paused(self) -> bool:
        """True while the active deck is paused (never raises)."""
        try:
            player, _ = self._deck_pair()
            return player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        except Exception:
            logger.debug("[LIVE] is_paused() probe failed", exc_info=True)
            return False

    def duration_seconds(self) -> float:
        """Total duration in seconds, falling back to the live Qt probe if unknown."""
        if self._duration_sec > 0:
            return self._duration_sec
        try:
            player, _ = self._deck_pair()
            dur_ms = player.duration()
            return dur_ms / 1000.0 if dur_ms > 0 else 0.0
        except Exception:
            logger.debug("[LIVE] duration_seconds() probe failed", exc_info=True)
            return 0.0

    def stop(self) -> None:
        """Stop all active/standby decks cleanly."""
        try:
            self._manual_fade_active = False
            self._boundary_armed = True
            self._finished = False
            self._driver_timer.stop()
            self._load_watchdog.stop()
            self._watchdog_trials = 0
            self._watchdog_armed = False
            self._stop_fade_timer()
            self._player.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
                self._standby_target_ms = None
                self._standby_ready = False
                self._standby_seek_pending = False
            self._active_deck = 0
            self._sections_cfg.clear()
            self._sequencer.configure([], 0.0, 0.0)
            logger.debug("[LIVE] stop()")
        except Exception as exc:
            logger.error("[LIVE] stop() failed: %s", exc, exc_info=True)

    def seek(self, position: float) -> None:
        """Jump to *position* seconds, re-aligning the section index and envelope.

        Scrubbing into a skipped section snaps forward to the next playable one,
        so a section mode is honoured in every navigation path.
        """
        try:
            player, _ = self._deck_pair()
            ms = max(0, int(position * 1000))
            if self._sequencer.active:
                idx = self._sequencer.section_index_for_time(position)
                if idx is not None:
                    target = self._sequencer.jump_to(idx)
                    if target is not None and target > position:
                        ms = int(round(target * 1000))
                    self.signals.section_changed.emit(idx)
            self._finished = False
            self._boundary_armed = True
            player.setPosition(ms)
            self._apply_envelope_at(ms / 1000.0)
            self._pre_cue_next_target()
        except Exception as exc:
            logger.error("[LIVE] seek() failed: %s", exc, exc_info=True)

    def set_volume(self, volume: int) -> None:
        """Set live master volume 0-100."""
        try:
            vol_norm = max(0.0, min(1.0, volume / 100.0))
            self._base_volume = vol_norm
            if self._fade_timer is None or not self._fade_timer.isActive():
                self._manual_fade_active = False
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
            # Only allocate the standby video decoder when looping across an
            # explicit OUT point; full-file loops are handled natively by Qt.
            if self._is_video_cue and loop and self._end_ms is not None:
                self._pre_cue_next_target()
        except Exception as exc:
            logger.error("[LIVE] set_loop() failed: %s", exc)

    def set_aspect_ratio(self, aspect: str | None) -> None:
        """No-op on purpose.

        Video geometry (aspect, scale, crop) is owned by ``OutputWindow``: the
        scene applies ``compute_media_frame_geometry`` to the ``QGraphicsVideoItem``
        so that surfaces and calibration stay authoritative.  The method is kept
        so ``main.py`` can configure images and videos through the same call.
        """

    def set_scale(self, scale: float) -> None:
        """No-op: see :meth:`set_aspect_ratio` (geometry lives in ``OutputWindow``)."""

    def set_crop(self, crop: dict | None) -> None:
        """No-op: see :meth:`set_aspect_ratio` (crop is applied by the output scene)."""

    def fade_in(self, target_volume: int, duration_sec: float) -> None:
        """Direct manual fade-in helper (also preserved for standalone callers)."""
        try:
            self._stop_fade_timer()

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

            timer = QTimer(self)
            self._fade_timer = timer

            def _tick() -> None:
                nonlocal current_step
                current_step += 1
                new_vol = min(target_norm, current_step * step_increment)
                self._deck_pair()[1].setVolume(new_vol)
                if current_step >= steps:
                    self._stop_fade_timer()

            timer.timeout.connect(_tick)
            timer.start(step_interval)
        except Exception as exc:
            logger.error("[LIVE] fade_in() failed: %s", exc)
            self.set_volume(target_volume)

    def fade_out(self, duration_sec: float = 0.2, stop_after: bool = False,
                 callback: Callable[[], None] | None = None) -> None:
        """Smooth manual fade-out (e.g. Cut/Blackout) down to 0 and optional stop."""
        try:
            self._stop_fade_timer()

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

            # Progress follows the clock, not the tick count: Windows delivers
            # 33 ms timers late, which stretched a 1 s fade to about 1.4 s.
            started = time.monotonic()

            timer = QTimer(self)
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            self._fade_timer = timer

            def _tick() -> None:
                progress = min(1.0, (time.monotonic() - started) / duration_sec)
                self._deck_pair()[1].setVolume(max(0.0, start_norm * (1.0 - progress)))
                if progress >= 1.0:
                    self._stop_fade_timer()
                    self._deck_pair()[1].setVolume(0.0)
                    if stop_after:
                        self.stop()
                    if callback is not None:
                        callback()

            timer.timeout.connect(_tick)
            timer.start(15)
        except Exception as exc:
            logger.error("[LIVE] fade_out() failed: %s", exc)
            self._deck_pair()[1].setVolume(0.0)
            if stop_after:
                self.stop()
            if callback is not None:
                callback()

    def shutdown(self) -> None:
        """Stop every timer and release the media player (called on exit).

        Safe to call more than once: a failed shutdown must never prevent the
        application from closing after a show.
        """
        try:
            self._load_watchdog.stop()
            self._watchdog_armed = False
            self._driver_timer.stop()
            self._stop_fade_timer()
            self._player.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
            logger.info("[LIVE] Shutdown complete")
        except Exception as exc:
            logger.error("[LIVE] Shutdown error: %s", exc)
