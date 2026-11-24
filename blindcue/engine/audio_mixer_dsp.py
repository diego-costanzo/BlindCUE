"""Signal processing of the own mixer (3.2 / 3.9): pan, 3-band EQ, reverb, limiter.

Everything works on blocks of ``BLOCK`` stereo frames (float32, shape
``(n, 2)``) at ``RATE``: a per-sample IIR loop in Python is far too slow, so

- the equaliser is the exact response of three RBJ biquads (low shelf, peak,
  high shelf) turned into a 1024-tap FIR and run by FFT overlap-save;
- the reverb is a uniformly partitioned FFT convolution with a synthetic
  room response (decorrelated noise with a faster decay of the highs);
- the limiter computes one gain per 32-frame step with a one-step look-ahead
  and interpolates between steps, so a peak never passes the threshold.

numpy only (no scipy). Pure functions and small state objects: testable
without Qt and without a sound card.
"""

from __future__ import annotations

import math

import numpy as np

RATE = 48000
BLOCK = 1024          # frames per mixer block (21.3 ms at 48 kHz)
_EQ_TAPS = 1024       # FIR length of the equaliser (<= BLOCK for overlap-save)
_EQ_DESIGN_N = 8192   # frequency grid for the EQ design


def db_gain(db: float) -> float:
    return 10.0 ** (float(db) / 20.0)


# ── Pan ──────────────────────────────────────────────────────────────────

def pan_gains(pan: float) -> tuple[float, float]:
    """Balance of a stereo signal: (left, right) gains for pan -1..+1.

    Unity in the centre (a cue with pan 0 plays exactly as with Qt); towards
    one side the other side falls on a constant-power curve and the near
    side stays at unity (hard left = the left channel alone).
    """
    p = max(-1.0, min(1.0, float(pan)))
    theta = (p + 1.0) * math.pi / 4.0
    return min(1.0, math.sqrt(2.0) * math.cos(theta)), min(1.0, math.sqrt(2.0) * math.sin(theta))


# ── Equaliser ────────────────────────────────────────────────────────────

def _biquad(kind: str, freq: float, gain_db: float, rate: int, q: float = 0.7071) -> tuple:
    """RBJ cookbook coefficients (b0, b1, b2, a0, a1, a2)."""
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / rate
    cw, sw = math.cos(w0), math.sin(w0)
    if kind == "peak":
        alpha = sw / (2.0 * q)
        return 1 + alpha * a, -2 * cw, 1 - alpha * a, 1 + alpha / a, -2 * cw, 1 - alpha / a
    alpha = sw / 2.0 * math.sqrt(2.0)  # shelf slope S = 1
    sa = 2.0 * math.sqrt(a) * alpha
    if kind == "lowshelf":
        return (a * ((a + 1) - (a - 1) * cw + sa), 2 * a * ((a - 1) - (a + 1) * cw),
                a * ((a + 1) - (a - 1) * cw - sa), (a + 1) + (a - 1) * cw + sa,
                -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - sa)
    return (a * ((a + 1) + (a - 1) * cw + sa), -2 * a * ((a - 1) + (a + 1) * cw),
            a * ((a + 1) + (a - 1) * cw - sa), (a + 1) - (a - 1) * cw + sa,
            2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - sa)


def eq_response(gains_db: tuple[float, float, float], freqs_hz: np.ndarray, rate: int = RATE,
                band_freqs: tuple[float, float, float] = (200.0, 1000.0, 4000.0)) -> np.ndarray:
    """Complex response of the 3-band EQ at *freqs_hz* (for tests and the FIR design)."""
    z1 = np.exp(-2j * np.pi * np.asarray(freqs_hz, dtype=np.float64) / rate)
    z2 = z1 * z1
    h = np.ones_like(z1)
    for kind, freq, gain in zip(("lowshelf", "peak", "highshelf"), band_freqs, gains_db):
        if abs(gain) < 1e-6:
            continue
        b0, b1, b2, a0, a1, a2 = _biquad(kind, freq, float(gain), rate, q=0.9 if kind == "peak" else 0.7071)
        h = h * (b0 + b1 * z1 + b2 * z2) / (a0 + a1 * z1 + a2 * z2)
    return h


def _eq_kernel(gains_db: tuple[float, float, float], block: int, rate: int) -> np.ndarray:
    """Spectrum (size block+1) of the FIR version of the EQ, ready for overlap-save with 2*block."""
    freqs = np.arange(_EQ_DESIGN_N // 2 + 1) * rate / _EQ_DESIGN_N
    ir = np.fft.irfft(eq_response(gains_db, freqs, rate), _EQ_DESIGN_N)[:_EQ_TAPS]
    fade = _EQ_TAPS // 4
    ir[-fade:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, fade)))   # gentle end of the truncated tail
    return np.fft.rfft(ir, 2 * block).astype(np.complex64)


class Equalizer:
    """3-band EQ of one stereo voice; changing the gains crossfades over one block."""

    def __init__(self, block: int = BLOCK, rate: int = RATE) -> None:
        self.block, self.rate = block, rate
        self._gains: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._kernel: np.ndarray | None = None
        self._old_kernel: np.ndarray | None = None
        self._prev = np.zeros((block, 2), dtype=np.float32)

    def set_gains(self, gains_db: tuple[float, float, float]) -> None:
        gains = tuple(round(float(g), 2) for g in gains_db)
        if gains == self._gains:
            return
        self._old_kernel = self._kernel if self._kernel is not None else _FLAT
        self._gains = gains  # type: ignore[assignment]
        self._kernel = None if self.is_flat() else _eq_kernel(gains, self.block, self.rate)  # type: ignore[arg-type]

    def is_flat(self) -> bool:
        return not any(abs(g) > 1e-6 for g in self._gains)

    def busy(self) -> bool:
        """True while the EQ changes the signal (or fades out of a change)."""
        return self._kernel is not None or self._old_kernel is not None

    def _run(self, spectrum: np.ndarray, kernel: np.ndarray | None) -> np.ndarray:
        if kernel is None or kernel is _FLAT:
            return self._last_input
        return np.fft.irfft(spectrum * kernel[:, None], 2 * self.block, axis=0)[self.block:].astype(np.float32)

    def process(self, x: np.ndarray) -> np.ndarray:
        """Filter one block (the input is kept for the next one even when the EQ is flat)."""
        self._last_input = x
        if not self.busy():
            self._prev = x.copy()
            return x
        frame = np.concatenate((self._prev, x), axis=0)
        self._prev = x.copy()
        spectrum = np.fft.rfft(frame, axis=0)
        y = self._run(spectrum, self._kernel)
        if self._old_kernel is not None:
            old = self._run(spectrum, self._old_kernel)
            ramp = np.linspace(0.0, 1.0, len(x), dtype=np.float32)[:, None]
            y = old * (1.0 - ramp) + y * ramp
            self._old_kernel = None
        return y


_FLAT = np.zeros(1, dtype=np.complex64)  # marker: "no filtering" in a crossfade


# ── Reverb ───────────────────────────────────────────────────────────────

_ROOM_CACHE: dict[tuple[float, int, int], np.ndarray] = {}


def room_response(seconds: float, rate: int = RATE, seed: int = 7) -> np.ndarray:
    """Synthetic stereo room response (shape (n, 2), unit energy per channel).

    Decorrelated noise; the lows decay over *seconds* (to -60 dB), the highs
    twice as fast, after a 12 ms pre-delay and a few early reflections. Cut
    at 80 % of the time (about -48 dB) with a short fade.
    """
    rng = np.random.default_rng(seed)
    n = int(max(0.2, seconds) * 0.8 * rate)
    t = np.arange(n) / rate
    out = np.zeros((n, 2), dtype=np.float64)
    pre = int(0.012 * rate)
    for ch in range(2):
        noise_spec = np.fft.rfft(rng.standard_normal(n))
        freqs = np.fft.rfftfreq(n, 1.0 / rate)
        low_mask = 1.0 / (1.0 + (freqs / 3000.0) ** 4)
        low = np.fft.irfft(noise_spec * low_mask, n)
        high = np.fft.irfft(noise_spec * (1.0 - low_mask), n)
        late = low * np.exp(-6.91 * t / seconds) + high * np.exp(-13.8 * t / seconds)
        late[:pre] = 0.0
        late[pre:pre + int(0.01 * rate)] *= np.linspace(0.0, 1.0, int(0.01 * rate))  # soft onset
        for delay_ms, gain in ((7.0 + 3 * ch, 0.5), (17.0 - 2 * ch, 0.35), (23.0 + 4 * ch, 0.25)):
            late[int(delay_ms * rate / 1000)] += gain * (-1 if ch else 1)
        fade = min(n // 10, int(0.1 * rate))
        late[-fade:] *= np.linspace(1.0, 0.0, fade)
        out[:, ch] = late / max(1e-9, float(np.sqrt(np.sum(late * late))))
    return out.astype(np.float32)


def _room_partitions(seconds: float, block: int, rate: int) -> np.ndarray:
    """Partition spectra (2, P, block+1) of a room response, cached per (time, block, rate)."""
    key = (round(seconds, 3), block, rate)
    cached = _ROOM_CACHE.get(key)
    if cached is None:
        ir = room_response(seconds, rate)
        parts = -(-len(ir) // block)
        padded = np.zeros((parts * block, 2), dtype=np.float32)
        padded[: len(ir)] = ir
        segs = padded.reshape(parts, block, 2)
        cached = np.fft.rfft(segs, 2 * block, axis=1).transpose(2, 0, 1).astype(np.complex64)
        _ROOM_CACHE[key] = cached
    return cached


class Reverb:
    """Mono-in / stereo-out convolution reverb of one voice (returns the wet signal only)."""

    def __init__(self, seconds: float, block: int = BLOCK, rate: int = RATE) -> None:
        self.block = block
        self.seconds = float(seconds)
        self._h = _room_partitions(self.seconds, block, rate)
        parts = self._h.shape[1]
        self._fdl = np.zeros((parts, block + 1), dtype=np.complex64)
        self._idx = 0
        self._prev = np.zeros(block, dtype=np.float32)
        self._quiet_blocks = parts + 2   # how long the tail still rings after silence came in

    @property
    def partitions(self) -> int:
        return self._h.shape[1]

    def ringing(self) -> bool:
        """True while some input is still in the room (the tail is not over)."""
        return self._quiet_blocks <= self.partitions + 1

    def process(self, x: np.ndarray) -> np.ndarray:
        mono = (x[:, 0] + x[:, 1]) * 0.5
        if float(np.max(np.abs(mono))) > 1e-7:
            self._quiet_blocks = 0
        else:
            self._quiet_blocks += 1
        frame = np.concatenate((self._prev, mono))
        self._prev = mono.astype(np.float32, copy=True)
        parts = self.partitions
        self._idx = (self._idx + 1) % parts
        self._fdl[self._idx] = np.fft.rfft(frame).astype(np.complex64)
        # fdl[idx] is the newest input (partition 0), fdl[idx-1] the one before (partition 1)...
        newest = self._fdl[self._idx::-1]               # partitions 0..idx
        older = self._fdl[:self._idx:-1]                # partitions idx+1..P-1
        out = np.empty((len(x), 2), dtype=np.float32)
        for ch in range(2):
            h = self._h[ch]
            acc = np.einsum("pk,pk->k", newest, h[: self._idx + 1])
            if len(older):
                acc = acc + np.einsum("pk,pk->k", older, h[self._idx + 1:])
            out[:, ch] = np.fft.irfft(acc, 2 * self.block)[self.block:]
        return out


# ── Limiter ──────────────────────────────────────────────────────────────

class Limiter:
    """Peak limiter of one output: never above *threshold*, recovers at *recovery_db_s*.

    Works in steps of *step* frames with a one-step look-ahead (the output is
    delayed by one step = 0.7 ms). A hard clip at 1.0 stays as the last guard.
    """

    def __init__(self, threshold_db: float = -1.0, recovery_db_s: float = 40.0, step: int = 32,
                 rate: int = RATE) -> None:
        self.threshold = db_gain(threshold_db)
        self.step = step
        self._up = db_gain(recovery_db_s * step / rate)
        self._carry = np.zeros((step, 2), dtype=np.float32)
        self._carry_peak = 0.0
        self._g = 1.0
        self.reduction = 1.0  # lowest gain of the last block (for a meter / tests)

    def _target(self, peak: np.ndarray) -> np.ndarray:
        return np.minimum(1.0, self.threshold / np.maximum(peak, 1e-12))

    def process(self, x: np.ndarray) -> np.ndarray:
        n = len(x)
        if n % self.step:
            raise ValueError("block length must be a multiple of the limiter step")
        m = n // self.step
        peaks = np.max(np.abs(x).reshape(m, self.step, 2), axis=(1, 2))
        delayed = np.concatenate((self._carry, x[:-self.step]), axis=0) if m > 1 else self._carry.copy()
        # Peaks of the delayed steps: the carried step, then the steps of x but the last.
        t = self._target(np.concatenate(([self._carry_peak], peaks[:-1])))
        t_next = float(self._target(np.array([peaks[-1]]))[0])
        self._carry = x[-self.step:].copy()
        self._carry_peak = float(peaks[-1])
        # Gain points at the step boundaries: each <= the targets of both steps it touches.
        points = np.empty(m + 1)
        points[0] = min(self._g, t[0])
        bound = np.minimum(t, np.concatenate((t[1:], [t_next])))
        g = points[0]
        if self._g <= 1.0 and float(np.min(bound)) >= 1.0 and g >= 1.0:
            points[:] = 1.0  # nothing to do in this block (the usual case)
        else:
            for j in range(1, m + 1):
                g = min(float(bound[j - 1]), g * self._up, 1.0)
                points[j] = g
        self._g = float(points[-1])
        self.reduction = float(np.min(points))
        if self.reduction >= 1.0:
            out = delayed
        else:
            ramp = np.linspace(0.0, 1.0, self.step, endpoint=False)
            gains = (points[:-1, None] + (points[1:] - points[:-1])[:, None] * ramp[None, :]).reshape(-1)
            out = delayed * gains[:, None].astype(np.float32)
        return np.clip(out, -1.0, 1.0)
