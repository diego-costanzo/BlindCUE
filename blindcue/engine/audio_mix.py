"""Mixer settings of a sound cue (stage 3, items 3.2 and 3.9): the rules, without Qt or numpy.

Qt Multimedia plays a file on one device, at most at its recorded level. The
own mixer (``engine.audio_mixer_*``) adds what it cannot do:

- pan (left / right),
- several logical outputs at once ("stage" + "foldback"...), each with its own
  level in dB, -INF meaning "explicitly silent on this output",
- levels above 0 dB (per row of the cue and per output of the computer map),
- effects: a 3-band equaliser and a reverb (every output has a limiter).

A cue keeps these settings in ``Cue.audio_mix``: an empty dict means "nothing
of this", so old shows load and play exactly as before. The first row of the
outputs list is the cue's own ``audio_output`` (3.1); ``level_db`` is its
level, ``sends`` the extra rows.

Only a cue that really uses one of the extras goes through the own mixer
(``uses_mixer``); every other cue stays on Qt Multimedia, which is also the
way back when the mixer is switched off on this computer.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from engine.audio_routes import OUTPUTS, normalize_output

LEVEL_MIN_DB = -60.0     # below this a row is -INF (silent)
LEVEL_MAX_DB = 12.0      # Qt stops at 0 dB; the mixer goes up to +12 dB
EQ_MIN_DB = -12.0
EQ_MAX_DB = 12.0
EQ_BANDS = ("low", "mid", "high")
EQ_FREQS = {"low": 200.0, "mid": 1000.0, "high": 4000.0}   # shelf / peak / shelf (Hz)
ROOMS = ("small", "medium", "large")
ROOM_SECONDS = {"small": 0.8, "medium": 1.5, "large": 2.6}  # reverb time of each room
MAX_SENDS = len(OUTPUTS) - 1   # the extra rows: every other logical output once
SHIFT_MAX_DB = 24.0


def _num(value: object, default: float, lo: float, hi: float) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return max(lo, min(hi, number))


def clamp_level(db: object) -> float | None:
    """A row level: None = -INF (silent), else LEVEL_MIN_DB..LEVEL_MAX_DB rounded to 0.1 dB."""
    if db is None:
        return None
    if isinstance(db, str) and db.strip().lower() in ("-inf", "-infinity", "inf", "mute"):
        return None
    try:
        number = float(db)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number):
        return 0.0
    if number < LEVEL_MIN_DB:
        return None
    return round(min(LEVEL_MAX_DB, number), 1)


def db_to_gain(db: float | None) -> float:
    """Linear gain of a level; None (-INF) is silence."""
    return 0.0 if db is None else 10.0 ** (float(db) / 20.0)


def format_db(db: float | None) -> str:
    """"-INF" / "+3.0 dB" / "0.0 dB" for labels (the unit is international)."""
    if db is None:
        return "-INF"
    return f"{db:+.1f} dB" if db else "0.0 dB"


@dataclass
class Send:
    """An extra output row of a cue: a logical output and its level (None = -INF)."""

    out: str
    db: float | None = 0.0

    def to_dict(self) -> dict:
        return {"out": self.out, "db": self.db}


@dataclass
class MixSettings:
    """What a cue asks of the own mixer; the defaults mean "plain Qt playback"."""

    level_db: float | None = 0.0          # level of the first row (the cue's own audio_output)
    pan: float = 0.0                      # -1 = left, 0 = centre, +1 = right
    sends: list[Send] = field(default_factory=list)
    eq: dict[str, float] = field(default_factory=lambda: {b: 0.0 for b in EQ_BANDS})
    reverb: float = 0.0                   # 0..1: how much reverb is added (0 = off)
    room: str = "medium"

    # ── conversion ─────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, data: object, main_output: str = "stage") -> MixSettings:
        """Validated settings from a stored dict (anything damaged falls back to its default)."""
        if not isinstance(data, Mapping):
            return cls()
        main = normalize_output(main_output)
        level = clamp_level(data.get("level_db", 0.0)) if "level_db" in data else 0.0
        sends: list[Send] = []
        seen = {main}
        raw_sends = data.get("sends")
        for item in raw_sends if isinstance(raw_sends, (list, tuple)) else []:
            if not isinstance(item, Mapping):
                continue
            out = str(item.get("out", "") or "").strip().lower()
            if out not in OUTPUTS or out in seen:
                continue  # one row per output; "mute" is not an output to send to
            seen.add(out)
            sends.append(Send(out, clamp_level(item.get("db", 0.0)) if "db" in item else 0.0))
            if len(sends) >= MAX_SENDS:
                break
        raw_eq = data.get("eq")
        eq = {b: 0.0 for b in EQ_BANDS}
        if isinstance(raw_eq, Mapping):
            for band in EQ_BANDS:
                eq[band] = round(_num(raw_eq.get(band, 0.0), 0.0, EQ_MIN_DB, EQ_MAX_DB), 1)
        elif isinstance(raw_eq, (list, tuple)) and len(raw_eq) == len(EQ_BANDS):
            for band, value in zip(EQ_BANDS, raw_eq):
                eq[band] = round(_num(value, 0.0, EQ_MIN_DB, EQ_MAX_DB), 1)
        room = str(data.get("room", "medium") or "medium")
        return cls(
            level_db=level,
            pan=round(_num(data.get("pan", 0.0), 0.0, -1.0, 1.0), 2),
            sends=sends,
            eq=eq,
            reverb=round(_num(data.get("reverb", 0.0), 0.0, 0.0, 1.0), 2),
            room=room if room in ROOMS else "medium",
        )

    def to_dict(self) -> dict:
        """The dict stored in the show: empty when everything is at its default."""
        if self.is_default():
            return {}
        out: dict = {}
        if self.level_db != 0.0:
            out["level_db"] = self.level_db
        if self.pan:
            out["pan"] = self.pan
        if self.sends:
            out["sends"] = [s.to_dict() for s in self.sends]
        if any(self.eq.get(b, 0.0) for b in EQ_BANDS):
            out["eq"] = {b: float(self.eq.get(b, 0.0)) for b in EQ_BANDS}
        if self.reverb > 0:
            out["reverb"] = self.reverb
            out["room"] = self.room
        return out

    def is_default(self) -> bool:
        return (self.level_db == 0.0 and not self.pan and not self.sends
                and not any(self.eq.get(b, 0.0) for b in EQ_BANDS) and self.reverb <= 0)

    # ── questions ──────────────────────────────────────────────────────
    def has_effects(self) -> bool:
        return any(self.eq.get(b, 0.0) for b in EQ_BANDS) or self.reverb > 0

    def extras(self, main_trim_db: float = 0.0) -> list[str]:
        """What needs the own mixer ([] = Qt can play it): "pan", "outputs", "boost", "eq", "reverb"."""
        found = []
        if abs(self.pan) > 1e-6:
            found.append("pan")
        if any(s.db is not None for s in self.sends):
            found.append("outputs")
        if (self.level_db is not None and self.level_db > 0) or main_trim_db > 0 \
                or any(s.db is not None and s.db > 0 for s in self.sends):
            found.append("boost")
        if any(self.eq.get(b, 0.0) for b in EQ_BANDS):
            found.append("eq")
        if self.reverb > 0:
            found.append("reverb")
        return found

    def qt_gain(self) -> float:
        """The part of the first row's level Qt can play (never above 1.0; -INF = 0)."""
        return min(1.0, db_to_gain(self.level_db))

    def shifted(self, delta_db: float) -> MixSettings:
        """"Change all outputs by X dB": every row that is not -INF moves, within the limits."""
        delta = _num(delta_db, 0.0, -SHIFT_MAX_DB, SHIFT_MAX_DB)

        def move(db: float | None) -> float | None:
            return None if db is None else clamp_level(db + delta)

        return MixSettings(level_db=move(self.level_db), pan=self.pan,
                           sends=[Send(s.out, move(s.db)) for s in self.sends],
                           eq=dict(self.eq), reverb=self.reverb, room=self.room)


def sanitize(value: object, main_output: str = "stage") -> dict:
    """``Cue.audio_mix`` as stored: validated, and {} when it asks for nothing."""
    return MixSettings.from_dict(value, main_output).to_dict()


def settings_of(cue: object) -> MixSettings:
    return MixSettings.from_dict(getattr(cue, "audio_mix", None) or {}, getattr(cue, "audio_output", "stage"))


def cue_extras(cue: object, out_trim_db: Callable[[str], float] | None = None) -> list[str]:
    """The extras a SOUND cue uses ([] for any other cue, or when Qt plays it as it is)."""
    media = getattr(getattr(cue, "media_type", None), "value", getattr(cue, "media_type", ""))
    if str(media) != "AUDIO":
        return []
    main = normalize_output(getattr(cue, "audio_output", "stage"))
    trim = out_trim_db(main) if (out_trim_db is not None and main != "mute") else 0.0
    return settings_of(cue).extras(trim)


@dataclass(frozen=True)
class MixSpec:
    """What a mixer voice plays with: pan, effects and (logical output, linear gain) rows."""

    pan: float = 0.0
    sends: tuple[tuple[str, float], ...] = (("stage", 1.0),)
    eq: tuple[float, float, float] = (0.0, 0.0, 0.0)
    reverb: float = 0.0
    room: str = "medium"


def spec_for(cue: object) -> MixSpec:
    """The mixer spec of a cue: its own output first (unless "mute"), then the extra rows."""
    mix = settings_of(cue)
    rows: list[tuple[str, float]] = []
    main = normalize_output(getattr(cue, "audio_output", "stage"))
    if main != "mute" and mix.level_db is not None:
        rows.append((main, db_to_gain(mix.level_db)))
    for send in mix.sends:
        if send.db is not None:
            rows.append((send.out, db_to_gain(send.db)))
    return MixSpec(pan=mix.pan, sends=tuple(rows), eq=tuple(float(mix.eq.get(b, 0.0)) for b in EQ_BANDS),
                   reverb=mix.reverb, room=mix.room)


def describe(extras: Iterable[str]) -> str:
    """Short English list for logs."""
    return ", ".join(extras) or "-"
