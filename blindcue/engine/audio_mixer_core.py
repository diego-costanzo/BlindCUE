"""The own mixer (3.2 / 3.9): voices -> pan, EQ, reverb -> logical outputs -> devices.

No Qt here: the output thread (``audio_mixer_output``) asks ``MixerCore.render``
for blocks and hands each device its share; tests call ``render`` directly.

A *voice* is one deck of a live player: a decoded source (``PcmSource``), a
read position, play / pause / stop, a level (the player's envelope, set
through ``Voice.gain`` at any time), pan, effects, and the logical outputs it
sends to with their levels. Changes of level, pan and sends glide over one
block (21 ms), starts, stops, pauses and seeks get a 1.3 ms ramp: no clicks.
A voice with reverb that stops leaves its reverb ringing out (a *tail*);
PANIC / Blackout cut the tails, Fade All fades them.

Routing: a logical output ("stage", "hall", "foldback") maps to a device bus
with a gain (the computer's trim, may be above 0 dB here) or is muted; the
map comes from the program (``set_routes``) and can change while playing.
Every bus ends in a limiter, so +12 dB rows and summed outputs never clip.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from engine.audio_mix import ROOM_SECONDS, MixSpec
from engine.audio_mixer_dsp import BLOCK, Equalizer, Limiter, Reverb, pan_gains
from engine.audio_mixer_source import PcmSource

DECLICK = 64                 # frames of the start / stop / seek ramps (1.3 ms)
LOOP_PREFETCH = 2 * 48000    # a looping voice asks for its start this many frames before the end


@dataclass(frozen=True)
class Route:
    """Where a logical output plays now: a bus (device key), its gain, or muted."""

    bus: str
    gain: float = 1.0
    muted: bool = False


class Voice:
    """One sound in the mixer (all changes go through ``MixerCore``; ``gain`` may be set directly)."""

    def __init__(self, vid: int) -> None:
        self.vid = vid
        self.source: PcmSource | None = None
        self.frame = 0
        self.state = "stopped"          # stopped / playing / paused
        self.loops_left = 0             # extra passes (-1 = forever), Qt's setLoops semantics
        self.gain = 1.0                 # wanted level (the live player's envelope x trims)
        self._g = 0.0                   # level applied at the end of the last block
        self.spec = MixSpec()
        self._pan = pan_gains(0.0)
        self._eq = Equalizer()
        self._reverb: Reverb | None = None
        self._reverb_amount = 0.0
        self._room_seconds = ROOM_SECONDS["medium"]
        self._bus_gain: dict[str, float] = {}   # applied gain per bus at the end of the last block
        self._fade_in = 0               # frames of the start ramp still to do
        self._fresh = False             # just started: output levels jump to their values
        self.fence: int | None = None   # hold here (the live player decides what comes next)
        self.held = False               # it is holding at the fence
        # A change of a playing voice, done after a 1.3 ms ramp in the next block:
        # (kind "pause" | "stop" | "seek", frame to stand on afterwards or None = where it is / 0, ring)
        self._pending: tuple | None = None
        # Read by the program (written only here, under the core lock):
        self.ended = False              # it played to the end of the file
        self.waiting = False            # the decoder had nothing yet for the last block
        self.started = False            # real sound went out since the last start / seek
        self.error = ""
        self.peak = 0.0                 # peak sent to the outputs since the program took it

    def position_frame(self) -> int:
        """Where it plays (a change not rendered yet counts as done, like Qt reports it at once)."""
        pending = self._pending
        if pending is not None:
            kind, frame = pending[0], pending[1]
            if frame is not None:
                return int(frame)
            if kind == "stop":
                return 0
        return self.frame


class _Tail:
    """The reverb of a stopped voice ringing out on its own."""

    def __init__(self, reverb: Reverb, amount: float, bus_gain: dict[str, float]) -> None:
        self.reverb = reverb
        self.amount = amount
        self.bus_gain = dict(bus_gain)
        self.level = 1.0
        self.fade_step = 0.0   # per frame, > 0 while fading out


class MixerCore:
    """Voices, routing and buses; ``render`` is called by the output thread."""

    def __init__(self, block: int = BLOCK) -> None:
        self.block = block
        self.lock = threading.RLock()
        self._voices: dict[int, Voice] = {}
        self._tails: list[_Tail] = []
        self._next = 1
        self._routes: dict[str, Route] = {"stage": Route("default")}
        self._limiters: dict[str, Limiter] = {}
        self._idle_blocks: dict[str, int] = {}
        self.starved = 0  # blocks in which a playing voice had to wait for its decoder

    # ── voices (program side) ─────────────────────────────────────────
    def add_voice(self) -> Voice:
        with self.lock:
            voice = Voice(self._next)
            self._next += 1
            self._voices[voice.vid] = voice
            return voice

    def remove_voice(self, voice: Voice) -> None:
        with self.lock:
            self._voices.pop(voice.vid, None)

    def voices(self) -> list[Voice]:
        with self.lock:
            return list(self._voices.values())

    def set_source(self, voice: Voice, source: PcmSource | None, frame: int = 0) -> None:
        """A new file (or tempo) for *voice*: stopped there, at *frame*."""
        with self.lock:
            voice.source = source
            voice.frame = max(0, int(frame))
            voice.state = "stopped"
            voice._pending = None
            voice.ended = False
            voice.held = False
            voice.error = ""
            voice.started = False
            # No decoding yet: the live player seeks to the cue's IN point next (seek() starts it there).

    def play(self, voice: Voice) -> None:
        with self.lock:
            if voice.state == "playing":
                pending = voice._pending
                if pending is not None and pending[0] == "pause":
                    # Paused and played again before it was heard: it plays on (from the new place, if any).
                    voice._pending = None if pending[1] is None else ("seek", pending[1], False)
                elif pending is not None and pending[0] == "stop":
                    voice._pending = ("seek", 0 if pending[1] is None else pending[1], False)  # Qt: from the top
                return
            if voice.ended:
                voice.frame = 0   # like Qt: play() after the end starts from the top
                voice.ended = False
            voice.state = "playing"
            voice._fade_in = DECLICK
            voice._g = max(0.0, float(voice.gain))  # the level at the start is the wanted one (no glide)
            voice._fresh = True                     # ... and so are the output levels
            voice.started = False
            if voice.source is not None:
                voice.source.ensure(voice.frame, whole=True)  # a prefetched head plays, the rest follows

    def pause(self, voice: Voice) -> None:
        with self.lock:
            if voice.state == "playing":
                pending = voice._pending
                if pending is not None and pending[0] == "stop":
                    return  # already stopping
                # A seek waiting to be rendered: paused at its target (Qt: setPosition then pause).
                voice._pending = ("pause", pending[1] if pending is not None else None, False)
            elif voice.state == "stopped" and not voice.ended:
                voice.state = "paused"   # Qt: pause() on a stopped deck parks it there

    def stop(self, voice: Voice, ring: bool = True) -> None:
        """Stop (with a 1.3 ms ramp); with *ring* its reverb rings out on its own."""
        with self.lock:
            if voice.state == "playing":
                voice._pending = ("stop", None, ring)
            else:
                voice._pending = None
                voice.state = "stopped"
                voice.frame = 0
                voice.held = False
                if ring:
                    self._start_tail(voice)

    def seek(self, voice: Voice, frame: int) -> None:
        with self.lock:
            frame = max(0, int(frame))
            voice.ended = False
            pending = voice._pending
            if voice.source is not None:
                going_on = voice.state == "playing" and (pending is None or pending[0] == "seek")
                voice.source.ensure(frame, whole=going_on)
            if voice.state == "playing":
                if pending is not None and pending[0] in ("pause", "stop"):
                    # Paused / stopped and then moved before the ramp was rendered: it stays
                    # paused / stopped, on the new place (the standby deck of LivePlayer does this).
                    voice._pending = (pending[0], frame, pending[2])
                else:
                    voice._pending = ("seek", frame, False)
            else:
                voice._pending = None
                voice.frame = frame
                voice.held = False

    def set_fence(self, voice: Voice, frame: int | None) -> None:
        """Hold *voice* at *frame* (an OUT point, a section that jumps); None lifts it."""
        with self.lock:
            voice.fence = None if frame is None else max(0, int(frame))
            if voice.held and (voice.fence is None or voice.fence > voice.frame):
                voice.held = False
                voice._fade_in = DECLICK

    def set_loops(self, voice: Voice, loops: int) -> None:
        """Qt's QMediaPlayer.setLoops: -1 forever, n >= 1 plays n times in all."""
        with self.lock:
            voice.loops_left = -1 if loops < 0 else max(0, int(loops) - 1)

    def set_spec(self, voice: Voice, spec: MixSpec) -> None:
        """Pan, effects and outputs of *voice* (applied from the next block, gliding)."""
        amount = max(0.0, min(1.0, float(spec.reverb)))
        seconds = ROOM_SECONDS.get(spec.room, ROOM_SECONDS["medium"])
        fresh = None
        if amount > 0 and (voice._reverb is None or abs(voice._reverb.seconds - seconds) > 1e-3):
            fresh = Reverb(seconds, self.block)  # built outside the lock: the audio thread never waits for it
        with self.lock:
            voice.spec = spec
            voice._pan = pan_gains(spec.pan)
            voice._eq.set_gains(spec.eq)
            voice._room_seconds = seconds
            if fresh is not None:
                voice._reverb = fresh
            voice._reverb_amount = amount

    # ── routing and tails ─────────────────────────────────────────────
    def set_routes(self, routes: dict[str, Route]) -> None:
        """The map of logical outputs now (replaces the old one; gains glide)."""
        self._routes = dict(routes)

    def routes(self) -> dict[str, Route]:
        return dict(self._routes)

    def _start_tail(self, voice: Voice) -> None:
        if voice._reverb is not None and voice._reverb.ringing() and voice._bus_gain and voice._reverb_amount > 0:
            self._tails.append(_Tail(voice._reverb, voice._reverb_amount, voice._bus_gain))
            # The next start gets a fresh room (the room partitions are cached: this is cheap).
            voice._reverb = Reverb(voice._room_seconds, self.block)

    def cut_tails(self) -> None:
        """PANIC / Blackout: the ringing reverbs go silent at once (1.3 ms ramp)."""
        with self.lock:
            for tail in self._tails:
                tail.fade_step = max(tail.fade_step, 1.0 / DECLICK)

    def fade_tails(self, seconds: float) -> None:
        with self.lock:
            step = 1.0 / max(DECLICK, float(seconds) * 48000)
            for tail in self._tails:
                tail.fade_step = max(tail.fade_step, step)

    def tails_count(self) -> int:
        return len(self._tails)

    def ready(self, voice: Voice) -> bool:
        """Its next frames are decoded (or it has nothing more to wait for)."""
        src = voice.source
        if src is None or src.error:
            return True
        return src.available(voice.position_frame())

    def flushing(self) -> bool:
        """Some bus still has its limiter's last step to give out."""
        return bool(self._limiters)

    def take_peak(self, voice: Voice) -> float:
        peak, voice.peak = voice.peak, 0.0
        return peak

    # ── rendering (output thread) ─────────────────────────────────────
    def render(self, n: int | None = None) -> dict[str, np.ndarray]:
        """The next *n* frames (a multiple of 32) of every bus that is in use."""
        n = n or self.block
        with self.lock:
            buses: dict[str, np.ndarray] = {}
            for voice in list(self._voices.values()):
                if voice.state == "playing":
                    self._render_voice(voice, n, buses)
            for tail in list(self._tails):
                self._render_tail(tail, n, buses)
            out: dict[str, np.ndarray] = {}
            for bus in set(buses) | set(self._limiters):
                mix = buses.get(bus)
                limiter = self._limiters.get(bus)
                if limiter is None:
                    limiter = self._limiters[bus] = Limiter()
                if mix is None:
                    self._idle_blocks[bus] = self._idle_blocks.get(bus, 0) + 1
                    if self._idle_blocks[bus] > 4:   # flushed: the bus can go
                        self._limiters.pop(bus, None)
                        self._idle_blocks.pop(bus, None)
                        continue
                    mix = np.zeros((n, 2), dtype=np.float32)
                else:
                    self._idle_blocks[bus] = 0
                out[bus] = limiter.process(mix)
            return out

    def _pull(self, voice: Voice, n: int) -> tuple[np.ndarray, int]:
        """Up to *n* frames of the source from voice.frame (loops and the end handled)."""
        pcm = np.zeros((n, 2), dtype=np.int16)
        src = voice.source
        if src is None:
            voice.state = "stopped"
            voice.error = "no source"
            return pcm, 0
        filled = 0
        guard = 0
        voice.waiting = False
        fence = voice.fence
        limit = n
        if fence is not None and voice.frame <= fence:
            limit = min(n, fence - voice.frame)
            if limit <= 0:
                voice.held = True
                return pcm, 0
        while filled < limit and guard < 8:
            guard += 1
            got, state = src.read(voice.frame, pcm[filled:limit])
            filled += got
            voice.frame += got
            if state == "ok":
                break
            if state == "end":
                if voice.loops_left != 0 and (src.total_frames or 0) > 0:
                    if voice.loops_left > 0:
                        voice.loops_left -= 1
                    voice.frame = 0
                    continue
                voice.ended = True
                voice.state = "stopped"
                break
            if state == "error":
                voice.error = src.error or "decoding failed"
                voice.state = "stopped"
                break
            voice.waiting = True   # "wait": the decoder is behind (or just starting)
            if voice.started:
                self.starved += 1  # it had played already: an audible gap
            break
        if fence is not None and limit < n and voice.frame >= fence and not voice.ended:
            voice.held = True
        total = src.total_frames or src.duration_frames()
        if voice.loops_left != 0 and total and total - voice.frame < LOOP_PREFETCH:
            src.ensure(0)  # the loop start is decoded before the end comes
        return pcm, filled

    def _read(self, voice: Voice, m: int) -> np.ndarray:
        """*m* frames of *voice* as float, with its level and its start ramp."""
        was_held = voice.held
        pcm, got = self._pull(voice, m)
        x = pcm.astype(np.float32) * (1.0 / 32768.0)
        if got:
            voice.started = True
        # Level: glide from the last block's level to the wanted one.
        target = max(0.0, float(voice.gain))
        if abs(target - voice._g) > 1e-6:
            x *= np.linspace(voice._g, target, m, dtype=np.float32)[:, None]
        elif target != 1.0:
            x *= target
        voice._g = target
        if voice._fade_in > 0 and got:
            k = min(voice._fade_in, got)
            x[:k] *= np.linspace(0.0, 1.0, k, endpoint=False, dtype=np.float32)[:, None]
            voice._fade_in -= k
        if got and ((voice.ended and got < m) or (voice.held and not was_held)):
            k = min(DECLICK, got)  # the file ends / it reached its fence: no click there
            x[got - k:got] *= np.linspace(1.0, 0.0, k, dtype=np.float32)[:, None]
        return x

    def _render_voice(self, voice: Voice, n: int, buses: dict[str, np.ndarray]) -> None:
        pending, voice._pending = voice._pending, None
        if pending is None:
            x = self._read(voice, n)
        else:
            # Pause, stop or seek: a 1.3 ms ramp down where it is, then the change.
            k = min(DECLICK, n)
            x = np.zeros((n, 2), dtype=np.float32)
            x[:k] = self._read(voice, k) * np.linspace(1.0, 0.0, k, dtype=np.float32)[:, None]
            kind, target, _ring = pending
            if target is not None:
                voice.frame = int(target)
                voice.held = False
                voice.ended = False
            if kind == "pause":
                voice.state = "paused"
            elif kind == "stop":
                voice.state = "stopped"
                voice.held = False
                if target is None:
                    voice.frame = 0
            elif kind == "seek":
                voice._fade_in = DECLICK
                if voice.state == "playing":
                    x[k:] = self._read(voice, n - k)  # the new place starts in the same block
        x = voice._eq.process(x)
        gl, gr = voice._pan
        if gl != 1.0 or gr != 1.0:
            x = x * np.array([gl, gr], dtype=np.float32)
        if voice._reverb is not None and (voice._reverb_amount > 0 or voice._reverb.ringing()):
            x = x + voice._reverb.process(x) * voice._reverb_amount
        self._send(voice, x, buses, n)
        if pending is not None and pending[0] == "stop" and pending[2]:
            self._start_tail(voice)
        if voice.state == "stopped" and voice.ended:
            self._start_tail(voice)

    def _bus_targets(self, sends: tuple[tuple[str, float], ...]) -> dict[str, float]:
        targets: dict[str, float] = {}
        for key, gain in sends:
            route = self._routes.get(key)
            if route is None or route.muted:
                continue
            targets[route.bus] = targets.get(route.bus, 0.0) + float(gain) * float(route.gain)
        return targets

    def _send(self, voice: Voice, x: np.ndarray, buses: dict[str, np.ndarray], n: int) -> None:
        targets = self._bus_targets(voice.spec.sends)
        peak_in = float(np.max(np.abs(x))) if len(x) else 0.0
        top = 0.0
        fresh, voice._fresh = voice._fresh, False
        if fresh:
            voice._bus_gain = {}
        for bus in set(targets) | set(voice._bus_gain):
            end = targets.get(bus, 0.0)
            start = end if fresh else voice._bus_gain.get(bus, 0.0)
            if start <= 0.0 and end <= 0.0:
                voice._bus_gain.pop(bus, None)
                continue
            acc = buses.get(bus)
            if acc is None:
                acc = buses[bus] = np.zeros((n, 2), dtype=np.float32)
            if abs(end - start) > 1e-6:
                acc += x * np.linspace(start, end, n, dtype=np.float32)[:, None]
            else:
                acc += x * end
            top = max(top, start, end)
            if end > 0.0:
                voice._bus_gain[bus] = end
            else:
                voice._bus_gain.pop(bus, None)
        voice.peak = max(voice.peak, min(1.0, peak_in * top))

    def _render_tail(self, tail: _Tail, n: int, buses: dict[str, np.ndarray]) -> None:
        wet = tail.reverb.process(np.zeros((n, 2), dtype=np.float32)) * tail.amount
        if tail.fade_step > 0:
            levels = tail.level - tail.fade_step * np.arange(1, n + 1, dtype=np.float32)
            levels = np.maximum(levels, 0.0)
            wet *= levels[:, None]
            tail.level = float(levels[-1])
        for bus, gain in tail.bus_gain.items():
            acc = buses.get(bus)
            if acc is None:
                acc = buses[bus] = np.zeros((n, 2), dtype=np.float32)
            acc += wet * gain
        if tail.level <= 0.0 or not tail.reverb.ringing():
            self._tails.remove(tail)
