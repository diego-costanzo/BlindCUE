"""A deck of the live player that plays through the own mixer (3.2 / 3.9).

``LivePlayer`` drives its decks through the QMediaPlayer / QAudioOutput API
(load, play, pause, stop, seek, loops, tempo, volume for its fades, status
and position signals). ``MixerMediaPlayer`` and ``MixerAudioOutput`` speak
the same API on top of a mixer voice, so every path of the program - fades,
Fade All, Pause All, PANIC, Undo GO, crossfade tails, sleep / wake, loops and
sections - works unchanged for a cue that uses pan, more outputs, levels
above 0 dB or effects. Only sound: a video always plays on Qt decks.

Differences to keep in mind:

- ``position()`` is the position being *rendered*, up to one output queue
  (``audio/mixer_buffer_ms``, 200 ms) ahead of what is heard. Fades are
  evaluated there, so they match what is rendered.
- The live player tells the deck where its next stop or jump is
  (``set_fence_ms``: the OUT point, or the end of a section that jumps); the
  voice holds there instead of running on into the queue, so an OUT point is
  exact and a loop jump costs about one GUI tick.
- PANIC drops the queued sound at once (``panic``); a single stop lets the
  queue play out (at most the queue length).

This module also holds the few helpers ``main.py`` calls (``install``,
``spec_for_launch``, ``panic``, ``shutdown``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer

from engine import audio_mix
from engine.audio_mix import MixSpec
from engine.audio_mixer_output import MixerService, mixer_enabled
from engine.audio_mixer_source import find_ffmpeg

logger = logging.getLogger(__name__)

_POLL_MS = 25

PB = QMediaPlayer.PlaybackState
MS = QMediaPlayer.MediaStatus


class MixerAudioOutput(QObject):
    """The QAudioOutput of a mixer deck: its volume is the voice level (the device comes from the routes)."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume = 1.0
        self._muted = False
        self._device: Any = None
        self._player: MixerMediaPlayer | None = None

    def volume(self) -> float:
        return self._volume

    def setVolume(self, volume: float) -> None:
        self._volume = max(0.0, float(volume))
        if self._player is not None:
            self._player._apply_gain()

    def isMuted(self) -> bool:
        return self._muted

    def setMuted(self, muted: bool) -> None:
        self._muted = bool(muted)
        if self._player is not None:
            self._player._apply_gain()

    def device(self) -> Any:
        return self._device

    def setDevice(self, device: Any) -> None:
        self._device = device

    def gain(self) -> float:
        return 0.0 if self._muted else self._volume


def _release(service: MixerService, holder: dict) -> None:
    """The deck is gone (deleteLater): free its voice and its source."""
    voice = holder.pop("voice", None)
    src = holder.pop("source", None)
    try:
        if voice is not None:
            service.core.stop(voice, ring=True)
            service.core.remove_voice(voice)
        service.release_source(src)
    except Exception:
        logger.debug("[MIXER] release failed", exc_info=True)


class MixerMediaPlayer(QObject):
    """QMediaPlayer look-alike for one mixer voice (sound only)."""

    positionChanged = Signal(int)
    durationChanged = Signal(int)
    mediaStatusChanged = Signal(object)
    playbackStateChanged = Signal(object)
    errorOccurred = Signal(object, str)

    def __init__(self, parent: QObject | None = None, service: MixerService | None = None) -> None:
        super().__init__(parent)
        self._service = service or MixerService.instance()
        self._core = self._service.core
        self._holder: dict = {"voice": self._core.add_voice()}
        self._voice = self._holder["voice"]
        self.destroyed.connect(lambda *_a, s=self._service, h=self._holder: _release(s, h))
        self._url = QUrl()
        self._source = None
        self._status = MS.NoMedia
        self._state = PB.StoppedState
        self._rate = 1.0
        self._pitch = True
        self._loops = 1
        self._audio: MixerAudioOutput | None = None
        self._spec = MixSpec()
        self._duration_ms = 0
        self._last_pos = -1
        self._error = ""
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._poll)

    # ── mixer side ────────────────────────────────────────────────────
    def set_mix(self, spec: MixSpec | None) -> None:
        self._spec = spec or MixSpec()
        self._core.set_spec(self._voice, self._spec)

    def mix(self) -> MixSpec:
        return self._spec

    def take_peak(self) -> float:
        return self._core.take_peak(self._voice)

    def set_fence_ms(self, ms: int | None) -> None:
        """Where the voice must hold (the live player decides what comes after it)."""
        src = self._source
        frame = None if (ms is None or src is None) else src.frame_of(max(0, int(ms)) / 1000.0)
        self._core.set_fence(self._voice, frame)

    def _apply_gain(self) -> None:
        self._voice.gain = self._audio.gain() if self._audio is not None else 1.0

    # ── QMediaPlayer API used by LivePlayer ───────────────────────────
    def setAudioOutput(self, output: MixerAudioOutput | None) -> None:
        if self._audio is not None:
            self._audio._player = None
        self._audio = output
        if output is not None:
            output._player = self
        self._apply_gain()

    def audioOutput(self) -> MixerAudioOutput | None:
        return self._audio

    def setVideoOutput(self, _output: Any) -> None:
        return

    def setAudioBufferOutput(self, _output: Any) -> None:
        return

    def isAvailable(self) -> bool:
        return True

    def source(self) -> QUrl:
        return QUrl(self._url)

    def setSource(self, url: QUrl) -> None:
        old = self._source
        self._url = QUrl(url)
        self._duration_ms = 0
        self._error = ""
        self._source = None
        if self._url.isEmpty():
            self._core.set_source(self._voice, None, 0)
            self._service.release_source(old)
            self._holder["source"] = None
            self._set_state(PB.StoppedState)
            self._set_status(MS.NoMedia)
            return
        self._source = self._service.acquire_source(self._url.toLocalFile(), self._rate, self._pitch)
        self._holder["source"] = self._source
        self._service.release_source(old)
        self._core.set_source(self._voice, self._source, 0)
        self._set_state(PB.StoppedState)
        self._set_status(MS.LoadingMedia)
        self._timer.start()
        QTimer.singleShot(0, self, self._loaded)

    def _loaded(self) -> None:
        if self._source is not None and self._status == MS.LoadingMedia and not self._check_error():
            self._set_status(MS.LoadedMedia)
            self._check_duration()

    def mediaStatus(self) -> QMediaPlayer.MediaStatus:
        return self._status

    def playbackState(self) -> QMediaPlayer.PlaybackState:
        return self._state

    def error(self) -> QMediaPlayer.Error:
        return QMediaPlayer.Error.ResourceError if self._error else QMediaPlayer.Error.NoError

    def errorString(self) -> str:
        return self._error

    def play(self) -> None:
        if self._source is None:
            return
        self._service.ensure_running()
        if self._status == MS.EndOfMedia:
            self._set_status(MS.LoadedMedia)
        self._core.play(self._voice)
        self._set_state(PB.PlayingState)
        self._timer.start()

    def pause(self) -> None:
        if self._source is None:
            return
        self._core.pause(self._voice)
        self._set_state(PB.PausedState)
        self._timer.start()

    def stop(self) -> None:
        if self._source is None:
            return
        self._core.stop(self._voice, ring=True)
        was = self._state
        self._set_state(PB.StoppedState)
        if self._status in (MS.BufferedMedia, MS.EndOfMedia, MS.StalledMedia, MS.BufferingMedia):
            self._set_status(MS.LoadedMedia)
        if was != PB.StoppedState:
            self._last_pos = 0
            self.positionChanged.emit(0)

    def position(self) -> int:
        src = self._source
        if src is None:
            return 0
        return round(src.seconds_of(self._voice.position_frame()) * 1000.0)

    def setPosition(self, ms: int) -> None:
        src = self._source
        if src is None:
            return
        ms = max(0, int(ms))
        self._core.seek(self._voice, src.frame_of(ms / 1000.0))
        if self._status == MS.EndOfMedia:
            self._set_status(MS.LoadedMedia)
        self._last_pos = ms
        self.positionChanged.emit(ms)

    def duration(self) -> int:
        self._check_duration(emit=False)
        return self._duration_ms

    def setLoops(self, loops: Any) -> None:
        value = int(getattr(loops, "value", loops))
        self._loops = value
        self._core.set_loops(self._voice, value)

    def loops(self) -> int:
        return self._loops

    def playbackRate(self) -> float:
        return self._rate

    def setPlaybackRate(self, rate: float) -> None:
        rate = max(0.5, min(2.0, float(rate)))
        if abs(rate - self._rate) > 1e-6:
            self._rate = rate
            self._resource()

    def pitchCompensation(self) -> bool:
        return self._pitch

    def setPitchCompensation(self, keep: bool) -> None:
        if bool(keep) != self._pitch:
            self._pitch = bool(keep)
            if abs(self._rate - 1.0) > 1e-6:
                self._resource()

    def _resource(self) -> None:
        """Tempo changed: the same file decoded at the new tempo, from the same point of the file."""
        old = self._source
        if old is None:
            return
        ms = self.position()
        state = self._state
        self._source = self._service.acquire_source(old.path, self._rate, self._pitch)
        self._holder["source"] = self._source
        self._core.set_source(self._voice, self._source, self._source.frame_of(ms / 1000.0))
        self._service.release_source(old)
        self._duration_ms = 0
        if state == PB.PlayingState:
            self._core.play(self._voice)

    # ── status polling (GUI thread) ───────────────────────────────────
    def _set_state(self, state: QMediaPlayer.PlaybackState) -> None:
        if state != self._state:
            self._state = state
            self.playbackStateChanged.emit(state)

    def _set_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != self._status:
            self._status = status
            self.mediaStatusChanged.emit(status)

    def _check_duration(self, emit: bool = True) -> None:
        src = self._source
        if src is None:
            return
        frames = src.duration_frames()
        if frames:
            ms = round(src.seconds_of(frames) * 1000.0)
            if ms != self._duration_ms:
                self._duration_ms = ms
                if emit:
                    self.durationChanged.emit(ms)

    def _check_error(self) -> bool:
        voice = self._voice
        src = self._source
        msg = voice.error or (src.error if src is not None and not src.available(voice.position_frame()) else "")
        if not msg or self._error:
            return bool(self._error)
        self._error = msg
        self._set_state(PB.StoppedState)
        self._set_status(MS.InvalidMedia)
        self.errorOccurred.emit(QMediaPlayer.Error.ResourceError, msg)
        return True

    def _poll(self) -> None:
        if self._source is None or self._check_error():
            self._timer.stop()
            return
        self._check_duration()
        voice = self._voice
        if self._state == PB.PlayingState:
            if voice.ended:
                pos = round(self._source.seconds_of(voice.frame) * 1000.0)
                self._last_pos = pos
                self.positionChanged.emit(pos)
                self._set_status(MS.EndOfMedia)
                self._set_state(PB.StoppedState)
                return
            if voice.started and self._status in (MS.LoadedMedia, MS.LoadingMedia):
                self._set_status(MS.BufferedMedia)
            pos = self.position()
            if pos != self._last_pos:
                self._last_pos = pos
                self.positionChanged.emit(pos)
        elif self._status != MS.LoadingMedia:
            self._timer.stop()


# ── helpers for main.py ──────────────────────────────────────────────────

_noticed: set[int] = set()
HEAD_SECONDS = 12.0   # decoded ahead for every mixer cue of the show (~2.3 MB each)


class _Prefetcher(QObject):
    """Decodes the first seconds of every mixer cue of the show before its GO.

    Starting FFmpeg costs ~50 ms on an idle Dell but took about a second
    while the computer was busy (measured 2026-11-24): with the start of the
    cue already decoded, a GO plays at once and the rest of the file is
    decoded meanwhile. It also keeps the output devices open while the show
    has mixer cues (opening a sleeping HDMI device took about a second).
    """

    def __init__(self, service: MixerService, cues: Callable[[], list], trim: Callable[[str], float] | None) -> None:
        super().__init__(service)
        self._service, self._cues, self._trim = service, cues, trim
        self._held: dict[tuple, Any] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(2500)
        self._timer.timeout.connect(self.scan)
        self._timer.start()

    def scan(self) -> None:
        try:
            self._scan()
        except Exception:
            logger.debug("[MIXER] prefetch scan failed", exc_info=True)

    def _scan(self) -> None:
        import os

        wanted: dict[tuple, Any] = {}
        if mixer_enabled() and find_ffmpeg() is not None:
            for cue in list(self._cues() or []):
                if not audio_mix.cue_extras(cue, self._trim) or not getattr(cue, "file_path", ""):
                    continue
                path = os.path.abspath(cue.file_path)
                key = (path, round(float(cue.in_point or 0.0), 3), round(float(getattr(cue, "playback_rate", 1.0)), 3),
                       bool(getattr(cue, "keep_pitch", True)))
                wanted[key] = cue
        for key in [k for k in self._held if k not in wanted]:
            self._service.release_source(self._held.pop(key))
        started = 0
        for key, _cue in wanted.items():
            if key in self._held or started >= 2:   # two FFmpeg starts per round at most
                continue
            path, start, rate, pitch = key
            if not os.path.isfile(path):
                continue
            src = self._service.acquire_source(path, rate, pitch)
            src.prefetch(src.frame_of(start), HEAD_SECONDS)
            self._held[key] = src
            started += 1
        if wanted:
            self._service.warm()


def install(device_mgr: Any, cues: Callable[[], list] | None = None) -> None:
    """The mixer follows the computer's map of logical outputs and prefetches the show's mixer cues."""
    service = MixerService.instance()
    if hasattr(device_mgr, "register_mixer"):
        device_mgr.register_mixer(service)
    if cues is not None:
        service._prefetcher = _Prefetcher(service, cues, getattr(device_mgr, "output_trim_db", None))
    if mixer_enabled():
        QTimer.singleShot(2000, MixerService.warm_up)  # room responses ready before the first reverb


def spec_for_launch(cue: Any, device_mgr: Any = None, notify: Callable[[str], None] | None = None) -> MixSpec | None:
    """The mixer spec a sound cue starts with, or None (Qt Multimedia plays it as before).

    When the cue asks for the mixer but it is off here (or FFmpeg is missing),
    the cue plays without the extras and *notify* says so once per cue.
    """
    trim = getattr(device_mgr, "output_trim_db", None)
    extras = audio_mix.cue_extras(cue, trim)
    if not extras:
        return None
    if not mixer_enabled() or find_ffmpeg() is None:
        cue_id = int(getattr(cue, "cue_id", 0) or 0)
        if notify is not None and cue_id not in _noticed:
            _noticed.add(cue_id)
            notify("mixer_off" if not mixer_enabled() else "no_ffmpeg")
        logger.warning("[MIXER] '%s' asks for %s but the mixer is %s: plays without them",
                       getattr(cue, "name", "?"), audio_mix.describe(extras),
                       "off" if not mixer_enabled() else "without FFmpeg")
        return None
    logger.info("[MIXER] '%s' plays through the mixer (%s)", getattr(cue, "name", "?"), audio_mix.describe(extras))
    return audio_mix.spec_for(cue)


def spec_of(cue: Any) -> MixSpec:
    """The mixer spec of a cue as it is now (a cue already on the mixer follows its edits live)."""
    return audio_mix.spec_for(cue)


def qt_level(cue: Any) -> float:
    """The level of a cue's own output row that Qt Multimedia can play (0..1; -INF = 0)."""
    return audio_mix.settings_of(cue).qt_gain()


def panic() -> None:
    """PANIC: the sound already queued for the devices goes too (not only the voices)."""
    service = MixerService.existing()
    if service is not None:
        service.panic()


def shutdown() -> None:
    service = MixerService.existing()
    if service is not None:
        service.shutdown()
