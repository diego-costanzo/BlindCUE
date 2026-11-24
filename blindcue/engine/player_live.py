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
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaPlayer

from engine.envelope import SectionSequencer, evaluate_cue_level, ramp_value
from models.cue import CueSection

_TAILS: list[_TailFade] = []


class _TailFade(QObject):
    """An outgoing sound handed over by a crossfade: it keeps playing and fades to
    silence (equal-power curve), then stops and goes away.

    *hold_sec* (3.3, playlist "overlap"): it first plays on at its level for that
    long and fades only over the rest of *seconds*.
    """

    def __init__(self, player: QMediaPlayer, audio: QAudioOutput, seconds: float, hold_sec: float = 0.0) -> None:
        super().__init__()
        self._player, self._audio = player, audio
        player.setParent(self)
        audio.setParent(self)
        self._start_volume = audio.volume()
        self._seconds = max(0.05, float(seconds))
        self._hold = max(0.0, min(float(hold_sec), self._seconds - 0.05))
        self._t0 = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        _TAILS.append(self)

    def _tick(self) -> None:
        import math

        elapsed = time.monotonic() - self._t0
        if elapsed >= self._seconds or self._player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.stop()
            return
        if elapsed < self._hold:
            return
        k = (elapsed - self._hold) / max(0.05, self._seconds - self._hold)
        self._audio.setVolume(self._start_volume * math.cos(min(1.0, k) * math.pi / 2))

    def finish_within(self, seconds: float) -> None:
        """Fade All: reach silence within *seconds* (never later than planned)."""
        left = self._seconds - (time.monotonic() - self._t0)
        if left > seconds:
            self._start_volume = self._audio.volume()
            self._t0 = time.monotonic()
            self._seconds = max(0.05, seconds)
            self._hold = 0.0

    def set_paused(self, paused: bool) -> None:
        """Pause All holds the fading sound too; it goes on fading after the resume."""
        try:
            if paused and self._timer.isActive():
                self._timer.stop()
                self._held_at = time.monotonic()
                self._player.pause()
            elif not paused and not self._timer.isActive() and hasattr(self, "_held_at"):
                self._t0 += time.monotonic() - self._held_at
                del self._held_at
                self._player.play()
                self._timer.start()
        except RuntimeError:
            pass

    def stop(self) -> None:
        self._timer.stop()
        try:
            if self._player.playbackState() in (QMediaPlayer.PlaybackState.PlayingState,
                                                QMediaPlayer.PlaybackState.PausedState):
                self._audio.setVolume(0.0)
                self._player.stop()
        except RuntimeError:
            pass
        if self in _TAILS:
            _TAILS.remove(self)
        self.deleteLater()


def _mixer_service() -> Any | None:
    """The own mixer (3.2) when the program already uses it; never created from here."""
    import sys

    module = sys.modules.get("engine.audio_mixer_output")
    return module.MixerService.existing() if module is not None else None


def stop_all_tails() -> None:
    """PANIC / Fade All / Blackout: the sounds still fading after a crossfade stop too."""
    for tail in list(_TAILS):
        tail.stop()
    mixer = _mixer_service()
    if mixer is not None:
        mixer.cut_tails()  # 3.9: reverbs still ringing after their cue stopped


def fade_all_tails(seconds: float) -> None:
    for tail in list(_TAILS):
        tail.finish_within(seconds)
    mixer = _mixer_service()
    if mixer is not None:
        mixer.fade_tails(seconds)


def pause_all_tails(paused: bool) -> None:
    for tail in list(_TAILS):
        tail.set_paused(paused)


def tails_count() -> int:
    return len(_TAILS)

logger = logging.getLogger(__name__)

# A released whole-file loop ends this many ms before the file end: the 20 ms
# position poll must see the end before Qt wraps back to the start.
_RELEASE_MARGIN_MS = 40
# 4.4 "hold the last frame": the video is paused this many ms before its end.
# At EndOfMedia the FFmpeg backend stops and CLEARS the picture, so the frame
# to keep must be taken while the deck is still paused on it.
HOLD_MARGIN_MS = 150

# 3.4: a crossfaded whole-file loop treats the file as ending this many ms early, so the pass that
# fades out is paused before EndOfMedia (pause() at EndOfMedia freezes, see _pause_unless_at_end).
_LOOP_XFADE_END_MARGIN_MS = 120


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


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a or "")) == os.path.normcase(os.path.abspath(b or ""))


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
        # 3.4: loop with a crossfade (sound only): the next pass starts on the second deck this many
        # seconds before the end of the pass; the old pass fades out over them (_xf, _xf_in).
        self._loop_xfade_sec: float = 0.0
        self._xf: dict | None = None
        self._xf_in: float = 1.0

        # Lazy standby deck for pre-cued anti-stutter jumps (allocated only when needed)
        self._audio_device: QAudioDevice | None = None
        self._standby_player: QMediaPlayer | None = None
        self._standby_audio: QAudioOutput | None = None
        self._standby_target_ms: int | None = None
        self._standby_ready: bool = False
        self._standby_seek_pending: bool = False
        self._active_deck: int = 0  # 0 = primary, 1 = standby deck
        # 3.3: (player, audio, start ms, path) of the next playlist track opened in advance
        self._preload: tuple[QMediaPlayer, QAudioOutput, int, str] | None = None

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
        # Level change from an ACTION cue: multiplies the cue's own envelope
        # (fades, volume points) and is reset when a new cue is loaded.
        self._level_trim: float = 1.0
        self._level_timer: QTimer | None = None
        self._level_ramp_clock: list = [0.0, None]  # [ramp start, paused at] - see ramp_level
        self._master_gain: float = 1.0  # master volume of the show (set_master_gain) x output trim
        self._show_gain: float = 1.0    # master volume of the show alone
        self._output_gain: float = 1.0  # 3.1: trim of the logical output (0 = muted)
        # Section boundary latch: after a jump/continuation we must not react to
        # the stale position report of the section we just left, otherwise the
        # sequencer advances twice and silently eats one loop or one cut.
        self._boundary_armed: bool = True
        self._finished: bool = False
        # 4.4: the video ends HOLD_MARGIN_MS before its end, paused on a frame
        # that is still shown (see set_hold_last_frame).
        self._hold_last_frame: bool = False

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

        # 3.2 / 3.9: the decks are Qt Multimedia ("qt", the default) or own-mixer decks ("mixer")
        # for a sound cue with pan / more outputs / boost / effects (engine.player_mixer).
        self._backend: str = "qt"
        self._want_mix: Any | None = None   # set by use_mixer() for the next load() only
        self._mix_spec: Any | None = None   # the mixer spec of the loaded cue

        self._setup_player()

    def _make_deck(self) -> tuple[Any, Any]:
        """A new (player, audio output) pair of the current backend."""
        if self._backend == "mixer":
            from engine.player_mixer import MixerAudioOutput, MixerMediaPlayer

            player, audio = MixerMediaPlayer(self), MixerAudioOutput(self)
            player.setAudioOutput(audio)
            player.set_mix(self._mix_spec)
            return player, audio
        player, audio = QMediaPlayer(self), QAudioOutput(self)
        if self._audio_device is not None and not self._audio_device.isNull():
            audio.setDevice(self._audio_device)
        player.setAudioOutput(audio)
        return player, audio

    def _setup_player(self) -> None:
        try:
            self._player, self._audio = self._make_deck()

            if self._video_output is not None:
                self._player.setVideoOutput(self._video_output)

            self._wire_main_player()

            logger.info("[LIVE] Native Wayland Multimedia player initialised (%s)", self._backend)
        except Exception as exc:
            logger.critical("[LIVE] Failed to initialise QtMultimedia: %s", exc, exc_info=True)
            self.signals.error_occurred.emit(f"Live Player init failed: {exc}")

    def _wire_main_player(self) -> None:
        """Deck 0 reports to this player (a fresh deck, or one opened in advance). Only the current
        deck 0 speaks: a deck replaced by the other backend (3.2) or handed over (3.3) is silent."""
        p = self._player
        p.positionChanged.connect(lambda ms, p=p: self._on_deck_pos(0, ms) if p is self._player else None)
        p.durationChanged.connect(lambda ms, p=p: self._on_deck_dur(0, ms) if p is self._player else None)
        p.mediaStatusChanged.connect(lambda st, p=p: self._on_deck_status(0, st) if p is self._player else None)
        p.errorOccurred.connect(
            lambda err, msg, p=p: self._on_deck_error(0, err, msg) if p is self._player else None)

    @staticmethod
    def _unwire(player: QMediaPlayer) -> None:
        for sig in (player.positionChanged, player.durationChanged, player.mediaStatusChanged,
                    player.errorOccurred):
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass

    def _retap_main(self) -> None:
        """The VU meter listens to the current deck 0 (after it was replaced)."""
        taps = getattr(self, "_level_taps", None)
        if not taps:
            return
        try:
            taps[0].audioBufferReceived.disconnect()
        except (RuntimeError, TypeError):
            pass
        from PySide6.QtMultimedia import QAudioBufferOutput

        tap = QAudioBufferOutput(self)
        self._player.setAudioBufferOutput(tap)
        tap.audioBufferReceived.connect(self._on_level_buffer, Qt.ConnectionType.QueuedConnection)
        taps[0] = tap

    # ── 3.3: gapless playlists - the next track opened before it is needed ──
    def preload_next(self, file_path: str, start: float = 0.0) -> bool:
        """Open *file_path* on a spare player, paused at *start* and silent.

        The next ``load()`` of the same file takes that player over, so the
        track starts without the delay of opening the file (as close to
        gapless as Qt Multimedia allows). Sound only: no picture is bound.
        """
        try:
            if not file_path or not os.path.isfile(file_path):
                return False
            start_ms = max(0, int(start * 1000))
            pre = getattr(self, "_preload", None)
            if pre is not None and _same_path(pre[3], file_path):
                if pre[2] != start_ms:
                    self._preload = (pre[0], pre[1], start_ms, pre[3])
                    pre[0].setPosition(start_ms)
                return True
            self.discard_preload()
            player = QMediaPlayer(self)
            audio = QAudioOutput(self)
            if self._audio_device is not None and not self._audio_device.isNull():
                audio.setDevice(self._audio_device)
            audio.setVolume(0.0)
            player.setAudioOutput(audio)
            self._preload = (player, audio, start_ms, file_path)

            def _ready(status, p=player) -> None:
                pre_now = getattr(self, "_preload", None)
                if pre_now is None or pre_now[0] is not p:
                    return
                if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia) \
                        and pre_now[2] > 0 and abs(p.position() - pre_now[2]) > 40:
                    p.setPosition(pre_now[2])

            player.mediaStatusChanged.connect(_ready)
            player.setSource(QUrl.fromLocalFile(file_path))
            player.pause()  # decodes the first buffers; never at EndOfMedia (it never played)
            logger.info("[LIVE] next track opened in advance: %s", os.path.basename(file_path))
            return True
        except Exception as exc:  # a preload is only a help: never an error for the show
            logger.warning("[LIVE] preload failed: %s", exc)
            self.discard_preload()
            return False

    def preloaded_path(self) -> str:
        pre = getattr(self, "_preload", None)
        return pre[3] if pre is not None else ""

    def discard_preload(self) -> None:
        pre = getattr(self, "_preload", None)
        self._preload = None
        if pre is None:
            return
        player, audio = pre[0], pre[1]
        try:
            try:
                player.mediaStatusChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            player.stop()  # it never played: not at EndOfMedia
            player.deleteLater()
            audio.deleteLater()
        except RuntimeError:
            pass

    def _adopt_preload(self, file_path: str, resume_at: float | None) -> bool:
        """``load()`` of the file opened in advance: that player becomes deck 0."""
        pre = getattr(self, "_preload", None)
        if pre is None:
            return False
        player, audio, _start_ms, path = pre
        ready = player.mediaStatus() in (QMediaPlayer.MediaStatus.LoadedMedia,
                                         QMediaPlayer.MediaStatus.BufferedMedia)
        if not _same_path(path, file_path) or resume_at is not None or not ready:
            self.discard_preload()
            return False
        self._preload = None
        try:
            player.mediaStatusChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        old_p, old_a = self._player, self._audio
        self._unwire(old_p)
        old_p.stop()  # never pause(): it may sit at EndOfMedia (see _pause_unless_at_end)
        old_p.setVideoOutput(None)
        old_p.deleteLater()
        old_a.deleteLater()
        self._player, self._audio = player, audio
        if self._video_output is not None:
            player.setVideoOutput(self._video_output)
        self._wire_main_player()
        self._retap_main()
        logger.info("[LIVE] the track opened in advance takes over: %s", os.path.basename(file_path))
        return True

    def _ensure_standby_deck(self) -> None:
        if self._standby_player is not None:
            return
        self._standby_player, self._standby_audio = self._make_deck()
        self._standby_audio.setVolume(0.0)
        if self._standby_video_output is not None:
            self._standby_player.setVideoOutput(self._standby_video_output)
        s = self._standby_player
        s.positionChanged.connect(lambda ms, s=s: self._on_deck_pos(1, ms) if s is self._standby_player else None)
        s.durationChanged.connect(lambda ms, s=s: self._on_deck_dur(1, ms) if s is self._standby_player else None)
        s.mediaStatusChanged.connect(
            lambda st, s=s: self._on_deck_status(1, st) if s is self._standby_player else None)
        s.errorOccurred.connect(
            lambda err, msg, s=s: self._on_deck_error(1, err, msg) if s is self._standby_player else None)
        rate = getattr(self, "_rate", 1.0)
        if abs(rate - 1.0) > 1e-6:  # 3.7: the second deck (loops, sections) plays at the cue's tempo too
            self._standby_player.setPlaybackRate(rate)
            if hasattr(self._standby_player, "setPitchCompensation"):
                self._standby_player.setPitchCompensation(getattr(self, "_keep_pitch", True))

    # ── Level meter (stage 1 C3, 1.14) ──────────────────────────────────
    def enable_level_tap(self) -> None:
        """Report the peak level of what plays (for the VU meter next to the master volume).

        The buffers come from the decoder thread; the slot runs queued on the
        main thread and only takes a peak, so playback never waits for Python.
        """
        from PySide6.QtMultimedia import QAudioBufferOutput

        self._peak = 0.0
        self._level_taps = []
        self._ensure_standby_deck()
        for player in (self._player, self._standby_player):
            if player is None:
                continue
            tap = QAudioBufferOutput(self)
            player.setAudioBufferOutput(tap)
            tap.audioBufferReceived.connect(self._on_level_buffer, Qt.ConnectionType.QueuedConnection)
            self._level_taps.append(tap)

    def _on_level_buffer(self, buffer) -> None:
        try:
            fmt = buffer.format()
            raw = bytes(buffer.constData())
            if not raw:
                return
            sample = fmt.sampleFormat()
            from PySide6.QtMultimedia import QAudioFormat
            import numpy as np

            if sample == QAudioFormat.SampleFormat.Float:
                peak = float(np.max(np.abs(np.frombuffer(raw, dtype=np.float32))))
            elif sample == QAudioFormat.SampleFormat.Int16:
                peak = float(np.max(np.abs(np.frombuffer(raw, dtype=np.int16)))) / 32768.0
            elif sample == QAudioFormat.SampleFormat.Int32:
                peak = float(np.max(np.abs(np.frombuffer(raw, dtype=np.int32)))) / 2147483648.0
            else:
                return
            sender = self.sender()
            audio = self._audio if (self._level_taps and sender is self._level_taps[0]) else self._standby_audio
            volume = audio.volume() if audio is not None else 1.0
            self._peak = max(self._peak, min(1.0, peak * volume))
        except Exception:  # noqa: BLE001 - a meter must never disturb playback
            return

    def take_peak(self) -> float:
        """Peak level since the last call (0..1), then start again."""
        peak = getattr(self, "_peak", 0.0)
        self._peak = 0.0
        if self._backend == "mixer":  # 3.2: mixer decks measure what they send to the outputs
            for player in (self._player, self._standby_player):
                if player is not None and hasattr(player, "take_peak"):
                    peak = max(peak, player.take_peak())
        return peak

    # ── Own mixer (3.2 / 3.9) ───────────────────────────────────────────
    def use_mixer(self, spec: Any | None) -> None:
        """The next load() plays through the own mixer with *spec* (None: Qt Multimedia).

        One-shot: a load() without it always goes back to Qt Multimedia, so a
        cue never inherits the mixer of the cue before it.
        """
        self._want_mix = spec

    def uses_mixer(self) -> bool:
        return self._backend == "mixer"

    def update_mixer(self, spec: Any | None) -> None:
        """Pan / outputs / effects changed while the cue plays (from the next mixer block)."""
        if self._backend != "mixer" or spec is None:
            return
        self._mix_spec = spec
        for player in (self._player, self._standby_player):
            if player is not None and hasattr(player, "set_mix"):
                player.set_mix(spec)

    def _swap_backend(self) -> None:
        """Called by load(): put decks of the wanted backend in place (the old ones are stopped and freed)."""
        want, self._want_mix = self._want_mix, None
        backend = "mixer" if want is not None else "qt"
        self._mix_spec = want
        if backend != self._backend:
            for player, audio in ((self._player, self._audio), (self._standby_player, self._standby_audio)):
                if player is None:
                    continue
                for sig in (player.positionChanged, player.durationChanged, player.mediaStatusChanged,
                            player.errorOccurred):
                    try:
                        sig.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                try:
                    player.stop()
                    player.setVideoOutput(None)
                except RuntimeError:
                    logger.debug("[LIVE] old deck already gone", exc_info=True)
                player.deleteLater()
                if audio is not None:
                    audio.deleteLater()
            self._backend = backend
            self._standby_player = self._standby_audio = None
            self._standby_target_ms = None
            self._standby_ready = False
            self._standby_seek_pending = False
            self._setup_player()
            if getattr(self, "_level_taps", None) is not None:
                self._retap()
            logger.info("[LIVE] decks now play through %s", "the own mixer" if backend == "mixer" else "Qt Multimedia")
        elif backend == "mixer":
            for player in (self._player, self._standby_player):
                if player is not None and hasattr(player, "set_mix"):
                    player.set_mix(want)
        self._recompute_master()

    def _retap(self) -> None:
        """The VU meter taps again after Qt decks came back (mixer decks report their own peaks)."""
        for tap in self._level_taps:
            try:
                tap.audioBufferReceived.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._level_taps = []
        if self._backend != "qt":
            return
        from PySide6.QtMultimedia import QAudioBufferOutput

        self._ensure_standby_deck()
        for player in (self._player, self._standby_player):
            tap = QAudioBufferOutput(self)
            player.setAudioBufferOutput(tap)
            tap.audioBufferReceived.connect(self._on_level_buffer, Qt.ConnectionType.QueuedConnection)
            self._level_taps.append(tap)

    def _recompute_master(self) -> None:
        # A mixer deck gets each output's trim (or mute) in the mixer, per output row.
        self._master_gain = self._show_gain * (1.0 if self._backend == "mixer" else self._output_gain)

    def _update_fence(self) -> None:
        """Mixer decks render ahead: tell the active one where the next stop or jump is."""
        if self._backend != "mixer":
            return
        player, _ = self._deck_pair()
        setter = getattr(player, "set_fence_ms", None)
        if setter is None:
            return
        fence = None
        if not self._finished:
            if self._sequencer.active:
                if self._sequencer._compute_transition()[0] != "CONTINUE":
                    fence = int(round(self._sequencer.active_end_sec() * 1000))
            elif self._end_ms is not None:
                fence = self._end_ms
        setter(fence)

    def hand_over_tail(self, seconds: float, hold_sec: float = 0.0) -> bool:
        """Crossfade of sound (evaluation 2026-11-24): what plays now keeps playing on its own
        and fades to silence over *seconds*; this player gets a fresh deck for the next cue.

        Before, a new cue on the same layer cut the old sound at once. Only the
        main deck is handed over (a cue playing on the loop / section deck is cut
        as before). *hold_sec*: it plays on at its level that long before the
        fade (3.3, playlist "overlap"). Returns False when nothing was handed over.
        """
        try:
            if self._active_deck != 0 or seconds <= 0:
                return False
            player, audio = self._player, self._audio
            if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                return False
            self._unwire(player)
            # The picture belongs to the next cue; the output dissolves its own snapshot.
            player.setVideoOutput(None)
            self._driver_timer.stop()
            self._stop_fade_timer()
            _TailFade(player, audio, seconds, hold_sec)
            self._setup_player()
            self._retap_main()
            logger.info("[LIVE] crossfade: the outgoing sound fades over %.1fs on its own", seconds)
            return True
        except Exception as exc:  # noqa: BLE001 - a crossfade must never break the next cue
            logger.error("[LIVE] hand_over_tail failed: %s", exc, exc_info=True)
            return False

    def extend_fade_in(self, seconds: float) -> None:
        """A crossfade: the new cue rises at least over the time the old one falls."""
        self._fade_in_sec = max(self._fade_in_sec, float(seconds))

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

    def set_rate(self, rate: float, keep_pitch: bool = True) -> None:
        """3.7: tempo of the cue (0.5-2.0) on every deck; the pitch stays when the backend can keep it."""
        rate = max(0.5, min(2.0, float(rate)))
        for player in (getattr(self, "_player", None), getattr(self, "_standby_player", None)):
            if player is None:
                continue
            if abs(player.playbackRate() - rate) > 1e-6:
                player.setPlaybackRate(rate)
            if hasattr(player, "setPitchCompensation"):
                try:
                    player.setPitchCompensation(bool(keep_pitch))
                except (RuntimeError, TypeError):
                    pass
        self._rate = rate
        self._keep_pitch = bool(keep_pitch)

    def set_audio_device(self, device: QAudioDevice | None) -> None:
        """Assign live output audio device (e.g. Master Sala / PA system)."""
        same = (device is not None and self._audio_device is not None and not device.isNull()
                and bytes(device.id()) == bytes(self._audio_device.id()))
        if same:
            return  # 3.1 routes on every start / map change: nothing to do
        self._audio_device = device
        if self._audio is not None and device is not None and not device.isNull():
            self._audio.setDevice(device)
        if self._standby_audio is not None and device is not None and not device.isNull():
            self._standby_audio.setDevice(device)
        pre = getattr(self, "_preload", None)
        if pre is not None and device is not None and not device.isNull():
            pre[1].setDevice(device)  # 3.3: the track opened in advance plays there too
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
            or self._hold_last_frame
        )

    # ── Hold the last frame (stage 4.4) ───────────────────────────────

    def set_hold_last_frame(self, on: bool) -> None:
        """At its end the cue pauses HOLD_MARGIN_MS early instead of running into EndOfMedia.

        The frame it pauses on stays in the video output, so the caller can
        take it (``current_frame_image``) and keep it on the layer. Call after
        ``load()`` (which resets it), like ``set_loop()``.
        """
        self._hold_last_frame = bool(on)
        self._ensure_driver_timer()

    def holds_last_frame(self) -> bool:
        return self._hold_last_frame

    def _hold_end_ms(self) -> int | None:
        """Where the cue ends (OUT point or file end, ms), None while the length is unknown."""
        if self._end_ms is not None and self._end_ms > self._start_ms:
            return self._end_ms
        if self._duration_sec > 0:
            return int(self._duration_sec * 1000)
        return None

    def _on_last_pass(self) -> bool:
        """True when this pass is the last one (no loop, or the last of N loops)."""
        if not self._is_looping:
            return True
        return self._loop_count > 0 and self._current_loop_iteration >= self._loop_count - 1

    def current_frame_image(self) -> QImage | None:
        """The frame the active deck shows now (None: no picture, e.g. after EndOfMedia)."""
        try:
            player, _ = self._deck_pair()
            sink = player.videoSink()
            if sink is None:
                return None
            frame = sink.videoFrame()
            if not frame.isValid():
                return None
            image = frame.toImage()
            return None if image.isNull() else image
        except Exception:  # noqa: BLE001 - no frame: the caller clears the layer as before
            logger.debug("[LIVE] current_frame_image() failed", exc_info=True)
            return None

    def _ensure_driver_timer(self) -> None:
        self._update_fence()
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
        elif (self._is_video_cue or self._loop_xfade_sec > 0) and self._is_looping and self._file_path:
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
        if idle_player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            # Never pause() a deck at EndOfMedia (see _pause_unless_at_end): open the file again.
            idle_player.stop()
            idle_player.setSource(QUrl())
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
            self._update_fence()
            return

        # Direct seek fallback (seamless fallback if user clicked arbitrary section fast)
        active_p.setPosition(target_ms)
        self._apply_envelope_at(target_ms / 1000.0)
        self._pre_cue_next_target()
        self._update_fence()

    def _compute_audio_gain(self, pos_sec: float) -> float:
        looping_inf = self._is_looping and self._loop_count <= 0
        has_inf_section = any(s.loops == 0 and not s.skip for s in self._sections_cfg)
        allow_fo = self._apply_fade_out_at_end and (not looping_inf) and (not has_inf_section)
        if self._is_looping and self._loop_xfade_sec > 0:
            allow_fo = allow_fo and self._xf_last_pass()  # 3.4: the Fade Out ends the last pass only
        allow_fi = self._apply_fade_in and (self._current_loop_iteration == 0)
        level = evaluate_cue_level(
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
        return max(0.0, min(1.0, level * self._level_trim * self._master_gain * self._xf_in))

    def set_master_gain(self, gain: float) -> None:
        """Master volume of the whole show (0..1, MUTE = 0): multiplies everything.

        The gain stack is envelope (cue fades, points) × level change from an
        action cue × this master; it is never stored in a cue.
        """
        self._show_gain = max(0.0, min(1.0, float(gain)))
        self._recompute_master()
        if self.is_playing() and not self._manual_fade_active:
            self._apply_current_level()

    def set_output_gain(self, gain: float) -> None:
        """3.1: trim of the logical output this player plays on (0 = the output is muted)."""
        self._output_gain = max(0.0, min(1.0, float(gain)))
        self._recompute_master()
        if self._backend == "mixer":
            pass  # 3.2: the mixer applies each output's trim / mute per output row
        elif self._output_gain <= 0.0:
            for audio in (self._audio, self._standby_audio):
                if audio is not None:
                    audio.setVolume(0.0)  # also under a running fade-out: its tail stays silent
        elif self.is_playing() and not self._manual_fade_active:
            self._apply_current_level()

    def _apply_envelope_at(self, pos_sec: float) -> None:
        if self._manual_fade_active:
            return
        _, audio = self._deck_pair()
        vol = self._compute_audio_gain(pos_sec)
        audio.setVolume(vol)

        if self._is_video_cue and self._opacity_cb is not None:
            looping_inf = self._is_looping and self._loop_count <= 0
            has_inf_section = any(s.loops == 0 and not s.skip for s in self._sections_cfg)
            # 4.4: a held last frame stays visible - its Fade Out is for the sound only.
            allow_fo = (self._apply_fade_out_at_end and (not looping_inf) and (not has_inf_section)
                        and not self._hold_last_frame)
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

        if self._hold_last_frame and self._on_last_pass():
            hold_end = self._hold_end_ms()
            if hold_end is not None and pos_ms >= hold_end - HOLD_MARGIN_MS:
                self._handle_cue_finished()  # paused on a frame that is still shown (4.4)
                return
        if self._is_looping and self._loop_xfade_sec > 0:
            self._loop_xfade_boundary(pos_ms)  # 3.4
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

    # ── 3.4: loop with a crossfade ────────────────────────────────────
    def _xf_last_pass(self) -> bool:
        """The pass playing now is the last one of a counted loop (or the loop was released)."""
        if not self._is_looping:
            return True
        return self._loop_count > 0 and self._current_loop_iteration >= self._loop_count - 1

    def _loop_end_ms(self) -> int | None:
        """Where a pass ends: the OUT point, else a little before the file end (never at EndOfMedia)."""
        if self._end_ms is not None and self._end_ms > self._start_ms:
            return self._end_ms
        if self._duration_sec <= 0:
            return None
        return max(self._start_ms + 1, int(self._duration_sec * 1000) - _LOOP_XFADE_END_MARGIN_MS)

    def _loop_xfade_boundary(self, pos_ms: int) -> None:
        end_ms = self._loop_end_ms()
        if end_ms is None:
            return  # length not known yet
        if self._xf_last_pass():
            if pos_ms >= end_ms - 18:
                self._handle_cue_finished()
            return
        if self._xf is not None:
            return  # this pass already handed over
        rate = max(0.5, float(getattr(self, "_rate", 1.0)))
        xf_ms = min(self._loop_xfade_sec * 1000.0 * rate, (end_ms - self._start_ms) / 2.0)
        if pos_ms < end_ms - xf_ms:
            return
        ready = (self._standby_player is not None and self._standby_ready and self._standby_target_ms is not None
                 and abs(self._standby_target_ms - self._start_ms) <= 60)
        if not ready:
            if pos_ms >= end_ms - 18:  # no second deck ready: a plain jump at the end, as before
                self._current_loop_iteration += 1
                self._execute_jump_ms(self._start_ms)
                self._boundary_armed = True
            return
        idle_idx = self._idle_deck_idx()
        old_p, old_a = self._deck_pair(self._active_deck)
        new_p, new_a = self._deck_pair(idle_idx)
        seconds = max(0.05, (end_ms - pos_ms) / 1000.0 / rate)
        self._xf = {"player": old_p, "audio": old_a, "t0": time.monotonic(), "sec": seconds,
                    "from": old_a.volume(), "held": None}
        self._current_loop_iteration += 1
        self._xf_in = 0.0
        new_a.setVolume(0.0)
        new_p.play()
        self._active_deck = idle_idx
        self._standby_target_ms = None
        self._apply_envelope_at(self._start_ms / 1000.0)
        logger.info("[LIVE] loop crossfade %.2fs (pass %d)", seconds, self._current_loop_iteration + 1)

    def _advance_loop_xfade(self) -> None:
        import math

        xf = self._xf
        if xf is None or xf["held"] is not None:
            return
        k = (time.monotonic() - xf["t0"]) / xf["sec"]
        if k >= 1.0:
            self._xf = None
            self._xf_in = 1.0
            xf["audio"].setVolume(0.0)
            _pause_unless_at_end(xf["player"])
            self._pre_cue_next_target()  # the old deck waits at the loop start for the next pass
            return
        out_level = 0.0 if self._output_gain <= 0.0 else xf["from"] * math.cos(k * math.pi / 2)
        xf["audio"].setVolume(out_level)
        self._xf_in = math.sin(k * math.pi / 2)

    def _hold_loop_xfade(self, held: bool) -> None:
        """Pause / play hold the pass that is fading out too."""
        xf = self._xf
        if xf is None:
            return
        if held and xf["held"] is None:
            xf["held"] = time.monotonic()
            _pause_unless_at_end(xf["player"])
        elif not held and xf["held"] is not None:
            xf["t0"] += time.monotonic() - xf["held"]
            xf["held"] = None
            xf["player"].play()

    def _drop_loop_xfade(self) -> None:
        self._xf = None
        self._xf_in = 1.0

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
        self._advance_loop_xfade()  # 3.4
        pos_ms = player.position()
        self._apply_envelope_at(pos_ms / 1000.0)
        self._update_fence()
        self._check_boundaries(pos_ms)

    def _on_deck_pos(self, deck_idx: int, pos_ms: int) -> None:
        if deck_idx != self._active_deck:
            return
        player, _ = self._deck_pair(deck_idx)
        if player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            return
        resume = getattr(self, "_resume_ms", None)
        if resume is not None:
            # Undo GO resumes a cut sound: hold on to the point until playback
            # really got there (a backend may report from 0 first, or reload).
            if pos_ms >= resume + 250:
                self._resume_ms = None  # playing on past it: done
            elif pos_ms < resume - 300 and self._resume_tries < 3:
                self._resume_tries += 1
                player.setPosition(resume)
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
            # A fresh deck (after a crossfade hand-over) reports "not playing" for a
            # moment after play(): the first driver tick stopped the envelope for good
            # and a fade-in stayed silent. Start it again once the media plays.
            self._ensure_driver_timer()
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            resume = getattr(self, "_resume_ms", None)
            target = (
                int(round(self._sequencer.active_start_sec() * 1000))
                if self._sequencer.active
                else (resume if resume is not None else self._start_ms)
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
            elif self._loop_xfade_sec > 0:
                # 3.4: a crossfaded loop is played pass by pass (no Qt loop): the end of the file
                # without a crossfade (length unknown, no second deck) ends the last pass or starts
                # the next one from the IN point.
                if self._xf_last_pass():
                    self._handle_cue_finished()
                else:
                    self._current_loop_iteration += 1
                    self.play()

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
             end: float | None = None, resume_at: float | None = None) -> None:
        """Load a media file cleanly on Deck 0, resetting any standby/fade state.

        *resume_at*: begin there instead of at *start* (Undo GO resuming a cut
        sound); *start* stays the cue's IN point for loops and the envelope.
        """
        try:
            self._manual_fade_active = False
            self._boundary_armed = True
            self._finished = False
            self._hold_last_frame = False  # 4.4: each cue says it again (set_hold_last_frame)
            self._driver_timer.stop()
            self._stop_fade_timer()
            self._reset_level_trim()
            self._drop_loop_xfade()
            self._loop_xfade_sec = 0.0  # set again by set_loop() for the new cue
            self._swap_backend()  # 3.2: own mixer for this cue, or Qt Multimedia (the default)
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
            self._resume_ms = max(0, int(resume_at * 1000)) if resume_at is not None else None
            self._resume_tries = 0
            self._end_ms = int(end * 1000) if (end is not None and end > 0) else None
            self._duration_sec = 0.0
            self._current_loop_iteration = 0
            self._last_emitted_opacity = None

            url = QUrl.fromLocalFile(file_path)
            if self._adopt_preload(file_path, resume_at):
                # 3.3: opened in advance (the next playlist track): already loaded, so no
                # durationChanged will come - publish the length now.
                ready_ms = self._player.duration()
                if ready_ms > 0:
                    self._duration_sec = ready_ms / 1000.0
                    self.signals.duration_changed.emit(self._duration_sec)
                if abs(self._player.position() - self._start_ms) > 40:
                    self._player.setPosition(self._start_ms)
                self._load_watchdog.stop()
                self._watchdog_trials = 0
                self._watchdog_armed = False
                logger.info("[LIVE] Loaded %s (start=%.1f, end=%s, opened in advance)", file_path, start, end)
                return
            self._player.stop()
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
            self._player.setPosition(self._resume_ms if self._resume_ms is not None else self._start_ms)

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

            clock = self._level_ramp_clock
            if clock[1] is not None:  # a level ramp held by pause() goes on from where it was
                clock[0] += time.monotonic() - clock[1]
                clock[1] = None
            self._apply_envelope_at(pos_ms / 1000.0)
            self._update_fence()  # before play(): a mixer deck starts rendering at once
            if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                player.play()
                logger.debug("[LIVE] play()")
            self._hold_loop_xfade(False)  # 3.4
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
                else max(getattr(self, "_resume_ms", None) or self._start_ms, player.position())
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
            if self._level_timer is not None and self._level_ramp_clock[1] is None:
                self._level_ramp_clock[1] = time.monotonic()  # hold a running level ramp
            player, _ = self._deck_pair()
            _pause_unless_at_end(player)
            self._hold_loop_xfade(True)  # 3.4: the pass fading out holds too
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
            self._hold_last_frame = False
            self._driver_timer.stop()
            self._load_watchdog.stop()
            self._watchdog_trials = 0
            self._watchdog_armed = False
            self._stop_fade_timer()
            self._reset_level_trim()
            self._drop_loop_xfade()
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
            self._update_fence()
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
                audio.setVolume(max(0.0, min(1.0, vol_norm * self._level_trim * self._master_gain)))
            else:
                player, _ = self._deck_pair()
                self._apply_envelope_at(player.position() / 1000.0)
        except Exception as exc:
            logger.error("[LIVE] set_volume() failed: %s", exc)

    def set_loop(self, loop: bool, loop_count: int = 0, crossfade: float = 0.0) -> None:
        """Enable or disable seamless looping. When sections exist, section sequencer governs.

        3.4: *crossfade* > 0 (sound only): each pass runs into the next over that many
        seconds on the second deck, and the loop is played pass by pass instead of by Qt.
        """
        try:
            self._is_looping = loop
            self._loop_count = loop_count
            self._current_loop_iteration = 0
            self._drop_loop_xfade()
            self._loop_xfade_sec = (max(0.0, float(crossfade))
                                    if loop and not self._is_video_cue and not self._sequencer.active else 0.0)
            if self._sequencer.active:
                self._player.setLoops(QMediaPlayer.Loops.Once)
                return
            if not loop:
                self._player.setLoops(QMediaPlayer.Loops.Once)
            elif self._loop_xfade_sec > 0:
                self._player.setLoops(QMediaPlayer.Loops.Once)
                self._pre_cue_next_target()  # the next pass waits on the second deck
                self._ensure_driver_timer()
                return
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
                muted = self._output_gain <= 0.0 and self._backend != "mixer"
                level = 0.0 if muted else max(0.0, start_norm * (1.0 - progress))
                self._deck_pair()[1].setVolume(level)
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

    # ── Action cues: level change and loop release ────────────────────

    def level_trim(self) -> float:
        """Current level multiplier set by level-change actions (1.0 = cue's own level)."""
        return self._level_trim

    def _reset_level_trim(self) -> None:
        old = self._level_timer
        self._level_timer = None
        if old is not None:
            old.stop()
            old.deleteLater()
        self._level_trim = 1.0

    def _apply_current_level(self) -> None:
        """Push the envelope × trim to the active deck right now.

        ``_apply_envelope_at`` does nothing while a stop fade owns the volume.
        """
        player, _ = self._deck_pair()
        self._apply_envelope_at(player.position() / 1000.0)

    def ramp_level(self, target_trim: float, duration_sec: float, curve: str = "linear") -> None:
        """Move the level multiplier to *target_trim* over *duration_sec* (0 = at once).

        Progress follows the clock, like ``fade_out``. A later ramp replaces a
        running one from wherever it got to.
        """
        target = max(0.0, float(target_trim))
        old = self._level_timer
        self._level_timer = None
        if old is not None:
            old.stop()
            old.deleteLater()
        start = self._level_trim
        if duration_sec <= 0 or abs(target - start) < 1e-4:
            self._level_trim = target
            self._apply_current_level()
            return
        # [start time, paused at]: pause() holds the ramp, play() moves its
        # start by the time spent paused, so Pause All freezes it too.
        clock = self._level_ramp_clock = [time.monotonic(), None]
        timer = QTimer(self)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._level_timer = timer

        def _tick() -> None:
            if self._level_timer is not timer or clock[1] is not None:
                return
            progress = min(1.0, (time.monotonic() - clock[0]) / duration_sec)
            self._level_trim = ramp_value(start, target, progress, curve)
            self._apply_current_level()
            if progress >= 1.0:
                self._level_timer = None
                timer.stop()
                timer.deleteLater()

        timer.timeout.connect(_tick)
        timer.start(15)

    def release_loop(self) -> bool:
        """Let a looping cue finish its current pass, then end (or go on) normally.

        Section loops/vamps move on to the next section at the end of the pass;
        a looping cue plays to its OUT point once more and then reports EOF,
        so Post-Delay and Auto-GO run as after any natural end.
        Returns False when nothing was looping.
        """
        if self._sequencer.active:
            if not self._sequencer.release_current_loop():
                return False
            self._pre_cue_next_target()
            return True
        if not self._is_looping:
            return False
        player, _ = self._deck_pair()
        end_ms = self._end_ms
        if end_ms is None:
            # A whole-file loop is run by Qt itself, and the FFmpeg backend
            # ignores a loop count changed mid-play (measured: it kept
            # looping). Give the boundary check an OUT point just before the
            # file end, so this pass ends there and reports EOF.
            dur_ms = int(self._duration_sec * 1000) or int(player.duration())
            if dur_ms <= 0:
                return False  # length still unknown: cannot tell where this pass ends
            end_ms = max(self._start_ms + 1, dur_ms - _RELEASE_MARGIN_MS)
        self._is_looping = False
        self._player.setLoops(QMediaPlayer.Loops.Once)
        self._end_ms = end_ms
        # The cue's Fade Out now applies at the end of this pass: never let it
        # start in the past (the level would jump down at once).
        remaining = max(0.0, (end_ms - player.position()) / 1000.0)
        self._fade_out_sec = min(self._fade_out_sec, remaining)
        self._ensure_driver_timer()
        return True

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
            self._reset_level_trim()
            self.discard_preload()
            self._player.stop()
            if self._standby_player is not None:
                self._standby_player.stop()
            logger.info("[LIVE] Shutdown complete")
        except Exception as exc:
            logger.error("[LIVE] Shutdown error: %s", exc)
