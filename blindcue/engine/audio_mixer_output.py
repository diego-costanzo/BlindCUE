"""The own mixer on real devices (3.2): an audio thread with one QAudioSink per device.

``MixerService`` (one per program, GUI thread) owns the ``MixerCore``, the
decoded sources and the routing of the logical outputs; a ``QThread`` runs
``_OutputWorker``, which renders blocks and pushes them into one QAudioSink
per device (push mode, 48 kHz float stereo).

Why a thread of its own: the GUI thread can be busy for a while (opening a
window, a big picture). Two things were measured (2026-11-24, details in
docs/claude/noc/mikser.md):

- GIL convoy: numpy releases the GIL inside each array operation and gets it
  back only after Python's switch interval (5 ms) when the GUI thread runs
  Python - dozens of times per block: rendering fell to 0.2-0.5x real time.
  While the mixer runs the interval is 0.5 ms (3.6-5.7x real time then).
- A single long C++ call holds the GIL for its whole length (110-170 ms for
  a big picture scaled, under load); only the sound already queued in the
  sink covers it. That queue (``lead``, QSettings ``audio/mixer_buffer_ms``,
  default 200 ms) is also how late a second sound joins one already playing;
  a sound starting on silent outputs starts in ~50 ms when its start was
  prefetched (``PcmSource.prefetch``), else after the FFmpeg start.

The worker never queues silence for a voice that waits for its decoder (the
sound would then come a whole queue later); it only tops the sinks up by one
block meanwhile. Every block goes to every device: devices drift apart by a
few ppm, so each device has a small queue capped at the lead.

Nothing here touches the GUI; the program talks to the service only.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtMultimedia import (
    QAudioDevice,
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
    QtAudio,
)

from engine.audio_mixer_core import MixerCore, Route
from engine.audio_mixer_dsp import BLOCK, RATE, Reverb
from engine.audio_mixer_source import PcmSource, find_ffmpeg, source_key

logger = logging.getLogger(__name__)

SETTING_ENABLED = "audio/mixer_enabled"
SETTING_LEAD = "audio/mixer_buffer_ms"
LEAD_CHOICES = (100, 200, 300, 500)
# A single long C++ call in the GUI thread (a big picture loaded / scaled: 110-170 ms measured on the
# Dell under load) holds the GIL; only the queued sound covers it. 200 ms covers that with a margin
# and is how late a second mixer sound joins one already playing (the first one starts in ~60 ms).
DEFAULT_LEAD_MS = 200
SWITCH_INTERVAL = 0.0005   # s: Python thread switch interval while the mixer runs (see ensure_running)
# s without sound before a device is let go: opening one can take a second (a sleeping HDMI
# audio device, measured), so a show with mixer cues keeps its devices open (``warm``).
_SINK_IDLE_CLOSE = 120.0
_SOURCE_IDLE_FREE = 45.0     # s an unused decoded file stays in memory (a GO again starts at once)
_SOURCES_MAX_BYTES = 400 * 1024 * 1024

RouteProvider = Callable[[str], tuple]   # key -> (QAudioDevice | None, gain, muted)


def mixer_enabled() -> bool:
    """The own mixer is on on this computer (default: on; off = every cue through Qt)."""
    return QSettings("BlindCue", "BlindCue").value(SETTING_ENABLED, True, type=bool)


def lead_ms() -> int:
    value = QSettings("BlindCue", "BlindCue").value(SETTING_LEAD, DEFAULT_LEAD_MS, type=int)
    return max(40, min(1000, int(value or DEFAULT_LEAD_MS)))


def device_key(device: QAudioDevice | None) -> str:
    if device is None or device.isNull():
        return "default"
    return bytes(device.id()).hex() or "default"


class _Sink:
    """One device: its QAudioSink, its writer and the frames waiting for it."""

    def __init__(self, device: QAudioDevice, lead_frames: int) -> None:
        self.device = device
        self.lead_frames = lead_frames
        self.fifo: list[np.ndarray] = []
        self.fifo_frames = 0
        self.last_sound = time.monotonic()
        self.drained = 0
        self.int16 = False
        fmt = QAudioFormat()
        fmt.setSampleRate(RATE)
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        if not device.isNull() and not device.isFormatSupported(fmt):
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self.int16 = True
        self.frame_bytes = 4 if self.int16 else 8
        self.sink = QAudioSink(device, fmt)
        self.sink.setBufferSize(lead_frames * self.frame_bytes)
        self.io = self.sink.start()
        self.failed = self.io is None or self.sink.error() != QtAudio.Error.NoError

    def free_frames(self) -> int:
        return max(0, self.sink.bytesFree() // self.frame_bytes)

    def queued_frames(self) -> int:
        return max(0, self.sink.bufferSize() // self.frame_bytes - self.free_frames())

    def push(self, block: np.ndarray) -> None:
        self.fifo.append(block)
        self.fifo_frames += len(block)
        excess = self.fifo_frames - self.lead_frames
        while excess > 0 and self.fifo:  # this device runs slower than the others: drop the oldest
            head = self.fifo[0]
            if len(head) <= excess:
                self.fifo.pop(0)
                self.fifo_frames -= len(head)
                excess -= len(head)
            else:
                self.fifo[0] = head[excess:]
                self.fifo_frames -= excess
                excess = 0

    def write(self) -> None:
        free = self.free_frames()
        while free > 0 and self.fifo:
            head = self.fifo[0]
            take = min(free, len(head))
            part = head[:take]
            data = (np.clip(part, -1.0, 1.0) * 32767).astype(np.int16) if self.int16 else part.astype(np.float32)
            written = self.io.write(data.tobytes())
            if written is None or written <= 0:
                break
            frames = int(written) // self.frame_bytes
            if frames < len(head):
                self.fifo[0] = head[frames:]
            else:
                self.fifo.pop(0)
            self.fifo_frames -= frames
            free -= frames
            if frames < take:
                break

    def close(self) -> None:
        try:
            self.sink.stop()
        except RuntimeError:
            logger.debug("[MIXER] sink already gone", exc_info=True)
        self.sink.deleteLater()


class _OutputWorker(QObject):
    """Lives in the mixer thread: renders the core and feeds the devices."""

    stats = Signal(int, int)  # starved blocks, drained sinks (for the log / a status line)

    def __init__(self, core: MixerCore, lead_frames: int) -> None:
        super().__init__()
        self.core = core
        self.lead_frames = lead_frames
        self.devices: dict[str, QAudioDevice] = {}   # bus -> device, replaced by the service
        self._sinks: dict[str, _Sink] = {}
        self._timer: QTimer | None = None
        self.drained = 0
        self.failed_buses: set[str] = set()

    @Slot()
    def begin(self) -> None:
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(5)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @Slot()
    def finish(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        for sink in self._sinks.values():
            sink.close()
        self._sinks.clear()

    def _sink_for(self, bus: str) -> _Sink | None:
        sink = self._sinks.get(bus)
        if sink is not None or bus in self.failed_buses:
            return sink
        device = self.devices.get(bus) or QMediaDevices.defaultAudioOutput()
        try:
            sink = _Sink(device, self.lead_frames)
        except Exception:
            logger.error("[MIXER] cannot open %s", device.description(), exc_info=True)
            sink = None
        if sink is None or sink.failed:
            logger.error("[MIXER] output device '%s' does not accept the mixer's sound",
                         device.description() if not device.isNull() else "default")
            self.failed_buses.add(bus)
            return None
        logger.info("[MIXER] output opened on '%s'%s", device.description(), " (16 bit)" if sink.int16 else "")
        self._sinks[bus] = sink
        return sink

    def _target(self) -> int:
        """How many frames each device should have queued now.

        Full lead while everything plays. A voice that waits for its first
        frames must not get silence queued before it: then only a short queue
        for what already sounds, and none at all when nothing sounds yet.
        """
        voices = [v for v in self.core.voices() if v.state == "playing"]
        # Waiting for its decoder, or holding at an OUT point / a jump the live player decides on.
        waiting = [v for v in voices if v.held or (not v.started and not self.core.ready(v))]
        if not waiting:
            return self.lead_frames
        if any(v.started and not v.held for v in voices) or self.core.tails_count() > 0:
            return 2 * BLOCK
        return 0

    def touch(self, buses: list[str]) -> None:
        """Open these devices now (or keep them open): the first sound then starts at once."""
        now = time.monotonic()
        for bus in buses:
            sink = self._sink_for(bus)
            if sink is not None:
                sink.last_sound = now

    @Slot()
    def drop_all(self) -> None:
        """PANIC: what is queued for the devices goes at once (the devices are reopened on the next sound)."""
        for sink in self._sinks.values():
            sink.close()
        self._sinks.clear()

    @Slot()
    def _tick(self) -> None:
        now = time.monotonic()
        last = getattr(self, "_last_tick", None)
        if last is not None and self._sinks:
            self.max_gap = max(getattr(self, "max_gap", 0.0), now - last)  # how long the thread could not run
        self._last_tick = now
        try:
            self._feed()
        except Exception:
            logger.error("[MIXER] audio thread error", exc_info=True)

    def _feed(self) -> None:
        now = time.monotonic()
        for sink in self._sinks.values():
            sink.write()
        active = any(v.state == "playing" for v in self.core.voices()) or self.core.tails_count() > 0
        rounds = 0
        while (active or self.core.flushing()) and rounds < 24:
            target = self._target() if active else BLOCK
            if self._sinks:
                need = max(target - (s.queued_frames() + s.fifo_frames) for s in self._sinks.values())
            else:
                need = target
            if need <= 0:
                break
            rounds += 1
            out = self.core.render(BLOCK)
            for bus, block in out.items():
                sink = self._sink_for(bus)
                if sink is None:
                    continue
                sink.push(block)
                sink.last_sound = now
                sink.write()
            active = any(v.state == "playing" for v in self.core.voices()) or self.core.tails_count() > 0
        for bus, sink in list(self._sinks.items()):
            if active and sink.queued_frames() == 0 and sink.fifo_frames == 0 and now - sink.last_sound < 1.0:
                sink.drained += 1
                self.drained += 1
            sink.write()
            state = sink.sink.state()
            if state == QtAudio.State.StoppedState and sink.sink.error() != QtAudio.Error.NoError:
                logger.warning("[MIXER] device of bus %s stopped (%s): reopening", bus, sink.sink.error())
                sink.close()
                del self._sinks[bus]
            elif now - sink.last_sound > _SINK_IDLE_CLOSE:
                sink.close()
                del self._sinks[bus]
                logger.info("[MIXER] output on bus %s closed (idle)", bus)


class MixerService(QObject):
    """The own mixer of the program (created on first use; GUI thread)."""

    _instance: MixerService | None = None

    def __init__(self, parent: QObject | None = None, *, start_output: bool = True) -> None:
        super().__init__(parent)
        self.core = MixerCore()
        self._sources: dict[tuple, PcmSource] = {}
        self._provider: RouteProvider | None = None
        self._thread: QThread | None = None
        self._worker: _OutputWorker | None = None
        self._start_output = start_output
        self.decoder = None  # None: FFmpeg; tests put a fake decoder factory here
        self._gc = QTimer(self)
        self._gc.setInterval(5000)
        self._gc.timeout.connect(self._collect)
        self._gc.start()
        self.refresh_routes()

    @classmethod
    def instance(cls) -> MixerService:
        if cls._instance is None:
            cls._instance = MixerService()
        return cls._instance

    @classmethod
    def existing(cls) -> MixerService | None:
        return cls._instance

    @staticmethod
    def available() -> bool:
        """The mixer can play here: switched on and FFmpeg found."""
        return mixer_enabled() and find_ffmpeg() is not None

    # ── output thread ─────────────────────────────────────────────────
    def ensure_running(self) -> None:
        if self._thread is not None or not self._start_output:
            return
        # GIL convoy (measured 2026-11-24): numpy lets go of the GIL inside every array operation, and
        # with Python's 5 ms switch interval the audio thread then waits up to 5 ms to get it back,
        # dozens of times per block, whenever the GUI thread runs Python: rendering fell to 0.2-0.5x
        # real time and the devices ran dry. At 0.5 ms it renders 3.6-5.7x real time under the same load.
        # Only while the mixer runs; restored by shutdown().
        self._old_switch = sys.getswitchinterval()
        sys.setswitchinterval(min(self._old_switch, SWITCH_INTERVAL))
        lead = int(lead_ms() * RATE / 1000)
        self._thread = QThread()
        self._thread.setObjectName("blindcue-mixer")
        self._worker = _OutputWorker(self.core, lead)
        self._worker.devices = self._devices
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.begin)
        self._thread.start(QThread.Priority.TimeCriticalPriority)
        logger.info("[MIXER] audio thread started (queue %d ms)", lead_ms())

    def warm(self) -> None:
        """The show has mixer cues: open the devices of the outputs before the first GO."""
        if not self._start_output:
            return
        self.ensure_running()
        worker = self._worker
        buses = sorted({r.bus for r in self.core.routes().values() if not r.muted})
        if worker is not None and buses:
            QTimer.singleShot(0, worker, lambda w=worker, b=buses: w.touch(b))

    def shutdown(self) -> None:
        """Stop the audio thread and every decoder (program exit)."""
        thread, worker = self._thread, self._worker
        self._thread = self._worker = None
        if thread is not None and worker is not None:
            QTimer.singleShot(0, worker, worker.finish)
            thread.quit()
            if not thread.wait(3000):
                logger.warning("[MIXER] audio thread did not stop in time")
        for src in list(self._sources.values()):
            src.close()
        self._sources.clear()
        self._gc.stop()
        old = getattr(self, "_old_switch", None)
        if old is not None:
            sys.setswitchinterval(old)
            self._old_switch = None
        if MixerService._instance is self:
            MixerService._instance = None

    def stats(self) -> dict:
        worker = self._worker
        return {"starved": self.core.starved, "drained": worker.drained if worker else 0,
                "sources": len(self._sources), "bytes": sum(s.nbytes() for s in self._sources.values()),
                "sinks": len(worker._sinks) if worker else 0,
                "max_gap_ms": round(getattr(worker, "max_gap", 0.0) * 1000, 1) if worker else 0.0}

    # ── routing ───────────────────────────────────────────────────────
    def set_route_provider(self, provider: RouteProvider | None) -> None:
        self._provider = provider
        self.refresh_routes()

    def refresh_routes(self) -> None:
        """Ask the program where each logical output plays now (map changed, device came or went)."""
        routes: dict[str, Route] = {}
        devices: dict[str, QAudioDevice] = {}
        for key in ("stage", "hall", "foldback"):
            device, gain, muted = (None, 1.0, key == "foldback")
            if self._provider is not None:
                try:
                    device, gain, muted = self._provider(key)
                except Exception:
                    logger.error("[MIXER] route of %s failed", key, exc_info=True)
            if device is None:
                device = QMediaDevices.defaultAudioOutput()
            bus = device_key(device)
            devices[bus] = device
            routes[key] = Route(bus, float(gain), bool(muted))
        self._devices = devices
        if self._worker is not None:
            self._worker.devices = devices
            self._worker.failed_buses.clear()
        self.core.set_routes(routes)

    # ── sources ───────────────────────────────────────────────────────
    def acquire_source(self, path: str, tempo: float = 1.0, keep_pitch: bool = True) -> PcmSource:
        key = source_key(path, tempo, keep_pitch)
        src = self._sources.get(key)
        if src is None:
            src = self._sources[key] = PcmSource(path, tempo, keep_pitch, decoder=self.decoder)
        src.users += 1
        src.last_used = time.monotonic()
        return src

    def release_source(self, src: PcmSource | None) -> None:
        if src is not None:
            src.users = max(0, src.users - 1)
            src.last_used = time.monotonic()

    def _collect(self) -> None:
        """Free decoded files nobody plays (after a while), and keep the memory under the cap."""
        now = time.monotonic()
        idle = [s for s in self._sources.values() if s.users <= 0]
        total = sum(s.nbytes() for s in self._sources.values())
        for src in sorted(idle, key=lambda s: s.last_used):
            if now - src.last_used > _SOURCE_IDLE_FREE or total > _SOURCES_MAX_BYTES:
                total -= src.nbytes()
                src.close()
                self._sources.pop(src.key, None)
        standing: dict[int, list[int]] = {}
        for voice in self.core.voices():
            if voice.source is not None and voice.state != "stopped":
                standing.setdefault(id(voice.source), []).append(voice.position_frame())
        for src in self._sources.values():
            src.prune(standing.get(id(src), ()))

    # ── tails (PANIC / Blackout / Fade All) ───────────────────────────
    def panic(self) -> None:
        """PANIC: every voice and tail silent, and the sound queued for the devices dropped."""
        self.core.cut_tails()
        for voice in self.core.voices():
            self.core.stop(voice, ring=False)
        worker = self._worker
        if worker is not None:
            QTimer.singleShot(0, worker, worker.drop_all)

    def cut_tails(self) -> None:
        self.core.cut_tails()

    def fade_tails(self, seconds: float) -> None:
        self.core.fade_tails(seconds)

    @staticmethod
    def warm_up() -> None:
        """Build the room responses once (a first reverb then costs nothing at GO)."""
        from engine.audio_mix import ROOM_SECONDS

        for seconds in ROOM_SECONDS.values():
            Reverb(seconds)
