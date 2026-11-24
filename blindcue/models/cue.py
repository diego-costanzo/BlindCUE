"""Data model for show cues (audio, video, image).

Each Cue represents a single media item that can be played, previewed
or composited on the output window across layers 1-3.
"""

from __future__ import annotations

import itertools
import logging
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class MediaType(Enum):
    """Supported media types for cues."""
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    GROUP = "GROUP"
    # A cue without a media file that acts on other cues (stop, fade, level,
    # layer opacity) or shows a note to the operator. It never takes a layer.
    ACTION = "ACTION"

    @property
    def has_file(self) -> bool:
        """True for the types that play a media file (not groups or actions)."""
        return self in (MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE)


class CueStatus(Enum):
    """Lifecycle status of a cue."""
    OFFLINE = "OFFLINE"
    LOADED = "LOADED"
    LIVE = "LIVE"
    PREVIZ = "PREVIZ"


class FollowMode(Enum):
    """Post-cue sequencing link mode for automated/simultaneous show progression."""
    MANUAL = "MANUAL"              # Blocco (Default): esegue la cue e attende GO manuale
    AUTO_FOLLOW = "AUTO_FOLLOW"    # Auto-GO a fine ciclo (dopo Pre-Delay + Durata + Post-Delay)
    SIMULTANEOUS = "SIMULTANEOUS"  # Simultanea: avvia subito la successiva insieme a questa


class GroupMode(Enum):
    """Execution modes for Group cue containers."""
    SIMULTANEOUS = "SIMULTANEOUS"  # Fire All: tutti gli elementi del gruppo partono insieme sul GO
    SEQUENCE = "SEQUENCE"          # Cascata / Auto-follow: un solo GO lancia la catena interna
    STEP = "STEP"                  # Passo-Passo (Capitolo): ogni GO avanza di un elemento nel gruppo
    RANDOM = "RANDOM"              # Random / Variazioni: sceglie a caso un elemento (anti-ripetizione)
    LOOP = "LOOP"                  # Loop continuo: cicla gli elementi interni della scena


def _default_crop() -> dict[str, float]:
    """Return default full-frame crop rectangle."""
    return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


def sanitize_crop(value: object) -> dict[str, float]:
    """Return a valid crop rectangle, falling back to the full frame.

    A damaged project file may contain a crop of the wrong type or with
    non-numeric fields. Downstream the crop is read as a mapping, so an
    unsanitised value makes the cue fail to draw *silently* during the show:
    the safe degradation is to project the whole frame.
    """
    if not isinstance(value, dict):
        return _default_crop()
    out: dict[str, float] = {}
    for key, default in (("x", 0.0), ("y", 0.0), ("w", 1.0), ("h", 1.0)):
        try:
            num = float(value.get(key, default))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return _default_crop()
        if not math.isfinite(num):
            return _default_crop()
        out[key] = min(1.0, max(0.0, num))
    if out["w"] <= 0.0 or out["h"] <= 0.0:
        return _default_crop()
    return out


# A polygon mask is only useful when it actually encloses an area: two points
# are a line, one point is a dot. 64 vertices is far more than any hand-drawn
# cut-out needs and keeps the JSON project file readable.
MASK_MIN_POINTS = 3
MASK_MAX_POINTS = 64
# Edge softness of the mask, expressed as a fraction of the frame's longest
# side (0 = hard cut). Normalised so the feather looks identical on the
# projector, in Pre-Viz and at any output resolution.
MASK_MAX_FEATHER = 0.05


def sanitize_mask_feather(value: object) -> float:
    """Return a mask feather in ``0.0 .. MASK_MAX_FEATHER``.

    Invalid input degrades to a hard edge instead of raising: a damaged project
    must still open and project something.
    """
    try:
        feather = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(feather):
        return 0.0
    return round(min(MASK_MAX_FEATHER, max(0.0, feather)), 4)


def normalize_rotation(value: object) -> float:
    """Return a rotation angle in the supported (-180, 180] degree range.

    The value is wrapped instead of clamped so that "270" (a common phone
    recording) becomes "-90" and keeps working. Invalid or non-finite input
    degrades to 0.0 rather than raising: a damaged project must still open.
    """
    try:
        deg = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(deg):
        return 0.0
    deg = (deg + 180.0) % 360.0 - 180.0
    if deg <= -180.0:
        deg += 360.0
    return round(deg, 2)


def sanitize_mask_polygon(points: object) -> list[list[float]]:
    """Return a clean polygon mask, or an empty list when the input is unusable.

    Points are normalised coordinates (0.0–1.0) of the **visible frame** (the
    cropped area, not the source file), so the mask stays glued to what the
    operator actually sees when the crop changes. Points outside the frame are
    clamped to the border rather than rejected; fewer than 3 valid points mean
    "no mask".
    """
    if not isinstance(points, (list, tuple)):
        return []
    clean: list[list[float]] = []
    for raw in points[:MASK_MAX_POINTS]:
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            return []
        try:
            x = float(raw[0])
            y = float(raw[1])
        except (TypeError, ValueError):
            return []
        if not (math.isfinite(x) and math.isfinite(y)):
            return []
        clean.append([round(min(1.0, max(0.0, x)), 4), round(min(1.0, max(0.0, y)), 4)])
    return clean if len(clean) >= MASK_MIN_POINTS else []


_VALID_FADE_CURVES = ("log", "scurve", "linear")
# 4.4: how a crossfade between two pictures looks (Cue.crossfade_style).
CROSSFADE_STYLES = ("dissolve", "slide")

# ── Action cues ──────────────────────────────────────────────────────────
# What an ACTION cue does; see ``sanitize_action_spec`` for the full schema.
ACTION_STOP = "stop"          # stop the targets at once
ACTION_FADE = "fade"          # fade the targets out over ``duration``, then stop
ACTION_RELEASE = "release"    # let a looping target finish its current pass
ACTION_LEVEL = "level"        # change the audio level of the targets
ACTION_OPACITY = "opacity"    # change the opacity of the targets' layers
ACTION_NOTE = "note"          # show a note to the operator (never on the output)
ACTION_CHECKLIST = "checklist"  # a note with tick boxes (pre-show checklist)
ACTION_GOTO = "goto"          # 2.2: jump - start the chosen cue, or only make it the next GO
ACTION_CALL = "call"          # 2.2: start the chosen cue without moving the GO pointer
ACTION_SEEK = "seek"          # 2.2: move a playing cue to a position / by N s / N s before its end
ACTION_COUNTDOWN = "countdown"  # 2.5: start a countdown (e.g. the interval); 0 s stops it
ACTION_WAIT = "wait"          # 2.11: wait ``duration`` s, then the next cue starts (a delay you can see)
ACTION_PAUSE = "pause"        # 2.11: pause the targets (sound and video)
ACTION_RESUME = "resume"      # 2.11: resume the paused targets
ACTION_STOPWATCH = "stopwatch"  # 2.11: stopwatch start / stop / reset (sw_mode)
ACTION_KINDS = (
    ACTION_STOP, ACTION_FADE, ACTION_RELEASE, ACTION_LEVEL, ACTION_OPACITY,
    ACTION_NOTE, ACTION_CHECKLIST, ACTION_GOTO, ACTION_CALL, ACTION_SEEK, ACTION_COUNTDOWN,
    ACTION_WAIT, ACTION_PAUSE, ACTION_RESUME, ACTION_STOPWATCH)
STOPWATCH_MODES = ("start", "stop", "reset")
ACTION_TARGET_ALL = "all"      # everything that is playing (or waiting in Pre-Delay)
ACTION_TARGET_LAYER = "layer"  # whatever plays on one layer of one output
ACTION_TARGET_CUES = "cues"    # chosen cues (a group means all its children)
_ACTION_TARGETS = (ACTION_TARGET_ALL, ACTION_TARGET_LAYER, ACTION_TARGET_CUES)
ACTION_MAX_SECONDS = 600.0
ACTION_MAX_CHECKLIST_ITEMS = 30
_DEFAULT_NOTE_COLOR = "#f59e0b"


RELATIVE_WHEN = ("start", "end", "before_end", "marker")
MAX_MARKERS = 200
# Effect keys (1.7): trigger = again from the top, toggle = start / stop, note = plays while the key is
# held, once = again does nothing while it plays (a doorbell pressed twice by accident rings once).
HOTKEY_MODES = ("trigger", "toggle", "note", "once")


def sanitize_markers(value: object) -> list[dict]:
    """2.7: [{"id": int, "name": str, "sec": float}] sorted by time; damaged entries dropped."""
    out: list[dict] = []
    seen: set[int] = set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        mid = _safe_int(item.get("id"), 0, min_val=0)
        if mid <= 0 or mid in seen:
            continue
        seen.add(mid)
        out.append({"id": mid, "name": str(item.get("name", "") or "")[:30],
                    "sec": round(_safe_float(item.get("sec", 0.0), 0.0, min_val=0.0, max_val=86400.0), 3)})
        if len(out) >= MAX_MARKERS:
            break
    return sorted(out, key=lambda m: m["sec"])


def _audio_output(value: object) -> str:
    """3.1: a valid logical output of a cue ("stage" for anything unknown)."""
    from engine.audio_routes import normalize_output

    return normalize_output(value)


def _audio_mix(value: object, audio_output: str, media_type: MediaType) -> dict[str, Any]:
    """3.2 / 3.9: validated mixer settings of a sound (or video) cue, {} when unused."""
    if media_type not in (MediaType.AUDIO, MediaType.VIDEO) or not value:
        return {}
    from engine.audio_mix import sanitize

    return sanitize(value, audio_output)


def _clock_text(value: object) -> str:
    """2.6: a valid "H:MM" / "H:MM:SS" time of day as given, "" for anything else."""
    import re

    text = str(value or "").strip()
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", text)
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59 or int(match.group(3) or 0) > 59:
        return ""
    return text


def action_needs_target(kind: str) -> bool:
    """Notes and checklists act on nobody; a jump or a call names one cue (cue_ids[0])."""
    return kind not in (ACTION_NOTE, ACTION_CHECKLIST, ACTION_GOTO, ACTION_CALL, ACTION_COUNTDOWN,
                        ACTION_WAIT, ACTION_STOPWATCH)


def action_names_one_cue(kind: str) -> bool:
    """Jump and call act on exactly one chosen cue (the first of cue_ids)."""
    return kind in (ACTION_GOTO, ACTION_CALL)


def sanitize_action_spec(value: object) -> dict[str, Any]:
    """Return a complete, valid action description; damaged input degrades safely.

    Schema (every key is always present after sanitising)::

        kind      stop | fade | release | level | opacity | note | checklist |
                  goto | call | seek | countdown | wait | pause | resume | stopwatch
        target    all | layer | cues
        layer     1-3 (target "layer")
        output    "A" | "B" (target "layer")
        cue_ids   [int, ...] (target "cues")
        duration  seconds of the fade / level / opacity change (0 = at once)
        mode      "absolute" | "relative" (level)
        level     0.0-1.0: absolute volume (level) or opacity (opacity)
        db        -60..+20: relative level change in dB
        curve     log | scurve | linear
        text      note text
        note_color '#RRGGBB' background of the note
        items     checklist lines

    A missing kind, or an unknown one from a newer version, becomes a note:
    a damaged cue then does nothing on stage (it never turns into "fade out
    everything") instead of failing to load.
    """
    raw = value if isinstance(value, dict) else {}
    kind = str(raw.get("kind", ACTION_NOTE) or ACTION_NOTE)
    if kind not in ACTION_KINDS:
        kind = ACTION_NOTE
    target = str(raw.get("target", ACTION_TARGET_ALL) or ACTION_TARGET_ALL)
    if target not in _ACTION_TARGETS:
        target = ACTION_TARGET_ALL
    cue_ids: list[int] = []
    raw_ids = raw.get("cue_ids")
    if isinstance(raw_ids, (list, tuple)):
        for item in raw_ids:
            cid = _safe_int(item, -1)
            if cid > 0 and cid not in cue_ids:
                cue_ids.append(cid)
    items: list[str] = []
    raw_items = raw.get("items")
    if isinstance(raw_items, (list, tuple)):
        for item in raw_items[:ACTION_MAX_CHECKLIST_ITEMS]:
            line = str(item or "").strip()
            if line:
                items.append(line)
    mode = str(raw.get("mode", "absolute") or "absolute")
    curve = str(raw.get("curve", "linear") or "linear")
    seek_mode = str(raw.get("seek_mode", "relative") or "relative")
    sw_mode = str(raw.get("sw_mode", "start") or "start")
    return {
        "kind": kind,
        "target": target,
        "layer": _safe_int(raw.get("layer", 1), 1, min_val=1, max_val=3),
        "output": normalize_output_target(raw.get("output", "A")),
        "cue_ids": cue_ids,
        "duration": round(_safe_float(raw.get("duration", 3.0), 3.0,
                                      min_val=0.0, max_val=ACTION_MAX_SECONDS), 3),
        "mode": mode if mode in ("absolute", "relative") else "absolute",
        "level": round(_safe_float(raw.get("level", 0.5), 0.5, min_val=0.0, max_val=1.0), 4),
        "db": round(_safe_float(raw.get("db", -6.0), -6.0, min_val=-60.0, max_val=20.0), 2),
        "curve": curve if curve in _VALID_FADE_CURVES else "linear",
        "text": str(raw.get("text", "") or ""),
        "note_color": _sanitize_hex_color(raw.get("note_color", _DEFAULT_NOTE_COLOR))
        or _DEFAULT_NOTE_COLOR,
        "items": items,
        "goto_play": bool(raw.get("goto_play", True)),
        "goto_max": _safe_int(raw.get("goto_max", 0), 0, min_val=0, max_val=999),
        "seek_mode": seek_mode if seek_mode in ("absolute", "relative", "before_end") else "relative",
        "seek_sec": round(_safe_float(raw.get("seek_sec", 10.0), 10.0, min_val=-86400.0, max_val=86400.0), 3),
        "countdown_sec": round(_safe_float(raw.get("countdown_sec", 900.0), 900.0, min_val=0.0, max_val=14400.0), 1),
        "sw_mode": sw_mode if sw_mode in STOPWATCH_MODES else "start",
        # 3.3: pause / resume with sleep_sec > 0 = put the music to sleep / wake it (0 = at once)
        "sleep_sec": round(_safe_float(raw.get("sleep_sec", 0.0), 0.0, min_val=0.0, max_val=ACTION_MAX_SECONDS), 3),
    }


_VALID_FOLLOW_MODES = tuple(m.value for m in FollowMode)
_VALID_GROUP_MODES = tuple(m.value for m in GroupMode)
_VALID_OUTPUT_TARGETS = ("A", "B")


def normalize_output_target(value: object) -> str:
    """Return ``A`` or ``B``; unknown/empty values fall back to ``A``."""
    text = str(value or "").strip().upper()
    return text if text in _VALID_OUTPUT_TARGETS else "A"


def layer_label(layer: int, output_target: str = "A") -> str:
    """Human-readable layer label, e.g. ``Layer 1`` or ``Layer 1 · Uscita B``."""
    if normalize_output_target(output_target) == "B":
        return f"Layer {layer} · Uscita B"
    return f"Layer {layer}"


def runtime_layer(layer: int, output_target: str = "A") -> int:
    """Map a cue layer (1-3) to its live runtime slot.

    Output A uses runtime layers 1-3, output B uses 4-6 (``layer + 3``).
    """
    if normalize_output_target(output_target) == "B":
        return int(layer) + 3
    return int(layer)


def resolve_output_target(value: object, dual_active: bool) -> str:
    """Return the output that will actually show the cue.

    With dual independent outputs inactive there is only one projector, so a
    cue assigned to output B is projected on output A instead of vanishing
    into a hidden window.
    """
    target = normalize_output_target(value)
    return target if dual_active else "A"


def _sanitize_hex_color(value: object) -> str:
    """Validate optional '#RRGGBB' hex group colour; return '' when empty or malformed."""
    txt = str(value or "").strip()
    if len(txt) == 7 and txt.startswith("#"):
        try:
            int(txt[1:], 16)
            return txt.lower()
        except ValueError:
            return ""
    return ""


def _safe_float(
    value: object,
    default: float,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
) -> float:
    """Parse a finite float with optional clamping, falling back to *default* on NaN/Inf/type errors."""
    if value is None or isinstance(value, bool):
        return default
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    if min_val is not None:
        num = max(min_val, num)
    if max_val is not None:
        num = min(max_val, num)
    return num


def _safe_int(
    value: object,
    default: int,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """Parse an integer safely with optional clamping, falling back to *default*."""
    if value is None or isinstance(value, bool):
        return default
    try:
        num = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if min_val is not None:
        num = max(min_val, num)
    if max_val is not None:
        num = min(max_val, num)
    return num


def _safe_opt_float(
    value: object,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
) -> float | None:
    """Parse an optional finite float; returns None if input is None or non-finite."""
    if value is None or isinstance(value, bool):
        return None
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    if min_val is not None:
        num = max(min_val, num)
    if max_val is not None:
        num = min(max_val, num)
    return num


@dataclass
class CueSection:
    """Contiguous virtual section inside an audio or video Cue."""

    label: str
    start: float
    end: float | None = None
    loops: int = 1   # 1 = once (default), >=2 = N repeats, 0 = infinite vamp
    skip: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise the section (times rounded to 0.1 ms to keep projects small)."""
        return {
            "label": self.label,
            "start": round(float(self.start), 4),
            "end": round(float(self.end), 4) if self.end is not None else None,
            "loops": int(self.loops),
            "skip": bool(self.skip),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CueSection:
        """Rebuild a section, clamping corrupt or non-finite times instead of failing the show."""
        start_val = _safe_float(data.get("start", 0.0), 0.0, min_val=0.0)
        end_val = _safe_opt_float(data.get("end"), min_val=0.0)
        if end_val is not None and end_val <= start_val:
            end_val = None
        return cls(
            label=str(data.get("label", "A")),
            start=start_val,
            end=end_val,
            loops=_safe_int(data.get("loops", 1), 1, min_val=0),
            skip=bool(data.get("skip", False)),
        )


@dataclass
class Cue:
    """Represents a single playable cue in the show.

    Attributes:
        cue_id:      Auto-incremented unique identifier.
        name:        Human-readable cue label.
        media_type:  VIDEO, AUDIO, or IMAGE.
        file_path:   Absolute path to the media file.
        layer:       Output layer (1, 2, or 3).
        volume:      Playback volume, 0.0 – 1.0.
        loop:        Whether to loop playback.
        in_point:    Start position in seconds.
        out_point:   End position in seconds (None = end of file).
        fade_in:     Fade-in duration in seconds.
        fade_out:    Fade-out duration in seconds.
        crop:        Crop rectangle as percentages {x, y, w, h} in 0.0 – 1.0.
        rotation:    Clockwise rotation in degrees, (-180, 180]; 0 = upright.
        mask_polygon: Optional polygon mask for images, as normalised [[x, y], ...]
                     points of the visible frame; empty list = no mask.
        aspect_ratio: Override aspect ratio string (e.g. "16:9") or None.
        status:      Current lifecycle status.
        position_x:  Horizontal position offset.
        position_y:  Vertical position offset.
        position_z:  Depth / z-order offset.
        scale:       Scale factor (1.0 = native size).
        q_label:     Modifiable script callout (e.g. "Q-2", "Q-9a", free text).
    """

    # ── Class-level auto-increment counter ────────────────────────────
    _id_counter: ClassVar[itertools.count] = itertools.count(1)

    # ── Required fields ───────────────────────────────────────────────
    name: str
    media_type: MediaType
    file_path: str

    # ── Optional / defaulted fields ───────────────────────────────────
    cue_id: int = field(default_factory=lambda: next(Cue._id_counter))
    q_label: str = ""  # Script cue / copione callout (e.g., "Q-2", "Q-9a")
    layer: int = 1
    volume: float = 1.0
    loop: bool = False
    loop_count: int = 0  # 0 = infinite loop; N >= 1 = repeat N times
    in_point: float = 0.0
    out_point: float | None = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    crop: dict[str, float] = field(default_factory=_default_crop)
    rotation: float = 0.0  # Degrees clockwise; applied to images and videos
    mask_polygon: list[list[float]] = field(default_factory=list)  # Images only
    mask_feather: float = 0.0  # Images only; soft mask edge (0 = hard cut)
    aspect_ratio: str | None = None
    status: CueStatus = CueStatus.OFFLINE
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    scale: float = 1.0
    opacity: float = 1.0
    notes: str = ""
    hold_time: float = 0.0
    pre_delay: float = 0.0
    post_delay: float = 0.0
    follow_mode: str = FollowMode.MANUAL.value
    exclusive: bool = False  # while LIVE, a manual GO is refused (Ctrl+GO forces it)
    confirm_start: bool = False  # starts only after an OK (keyboard, phone): the director's sign
    fade_others: float = 0.0     # on start, what else plays (sound) fades out over this many s (1.16)
    adlib: bool = False          # an effect on demand: outside the GO order, started by its key or tile (1.7)
    hotkey: str = ""             # one letter or digit (several cues on one key = steps)
    hotkey_mode: str = "trigger"  # see HOTKEY_MODES
    call_only: bool = False      # 2.2: started only by a "call" action, never by GO
    enabled: bool = True         # 2.3: off in this version of the show - never plays
    start_clock: str = ""        # 2.6: starts by itself at this time of day ("19:55" / "19:55:30")
    audio_output: str = "stage"  # 3.1: logical output stage / hall / foldback, or "mute" (engine.audio_routes)
    playback_rate: float = 1.0  # 3.7: tempo, 0.5-2.0 (1.0 = as recorded)
    keep_pitch: bool = True     # 3.7: a faster / slower tempo keeps the pitch (when the backend can)
    # 3.2 / 3.9: own mixer - pan, more outputs, levels above 0 dB, EQ, reverb (engine.audio_mix).
    # Empty = none of it: the cue plays through Qt Multimedia exactly as before.
    audio_mix: dict[str, Any] = field(default_factory=dict)
    script_page: str = ""       # 5.1: page of the script the cue is on
    script_line: str = ""       # 5.1: the line (words) it comes on
    # 2.1: starts by itself relative to another cue (by cue_id): N s after its
    # start, after its end, or N s before its end. Outside the GO order.
    start_rel_cue: int | None = None
    start_rel_when: str = "start"  # start | end | before_end
    start_rel_offset: float = 0.0
    start_rel_marker: int | None = None  # 2.7: with start_rel_when "marker": the marker id in the reference
    markers: list[dict] = field(default_factory=list)  # 2.7: named points in the file (sec), see sanitize_markers
    color: str = ""  # Optional '#RRGGBB' group/divider colour in Scaletta & Live
    parent_id: int | None = None  # None = root cue; int = belongs to parent Group cue
    group_mode: str = GroupMode.STEP.value  # SIMULTANEOUS, SEQUENCE, STEP, RANDOM, LOOP
    collapsed: bool = False  # UI collapse state for GROUP cues
    playlist: bool = False   # 3.3: a GROUP made as a playlist: stops after its last track, GO goes on after it
    fade_curve: str = "log"  # "log" (perceptual), "scurve" (cosine), "linear"
    volume_points: list[list[float]] = field(default_factory=list)   # [[time_sec, level 0..1], ...]
    opacity_points: list[list[float]] = field(default_factory=list)  # [[time_sec, opacity 0..1], ...]
    image_timeline_sec: float = 10.0  # Virtual timeline horizon (s) for infinite-hold images
    sections: list[CueSection] = field(default_factory=list)         # Contiguous virtual playback sections
    normalize_audio: bool = False  # EBU R128 (-16 LUFS) normalization active for this cue
    loudness_lufs: float | None = None  # Measured integrated loudness (LUFS)
    true_peak_dbfs: float | None = None  # Measured true peak (dBFS)
    auto_gain_db: float = 0.0  # Computed gain adjustment in dB to reach target (-16 LUFS)
    original_file_path: str | None = None  # Backup of original path if dynamics-optimized copy is used
    timeline_composed: bool = False  # GROUP cue configured/synced via multi-track studio timeline
    surface_id: str = "default"  # Target virtual screen / mapping surface ID ("default" = full screen)
    output_target: str = "A"  # Physical projector output: "A" (default) or "B" (second independent output)
    # Text cue: settings of an on-screen caption rendered to a transparent PNG
    # (file_path). Empty dict = ordinary media cue.
    text_spec: dict[str, Any] = field(default_factory=dict)
    # Crossfade: seconds over which the previous picture on the same layer
    # dissolves into this cue. 0 = hard cut / normal Fade In behaviour.
    crossfade: float = 0.0
    # 4.4 (MultiPlay): how the crossfade looks - "dissolve" (the old picture fades) or
    # "slide" (the new picture slides in from the right and pushes the old one out).
    crossfade_style: str = "dissolve"
    # 4.4: a video stays on its last frame at its end (until another cue takes the
    # layer, or the operator fades it) instead of leaving the layer empty.
    hold_last_frame: bool = False
    # Action cue (media_type ACTION): what it does, see sanitize_action_spec().
    # Empty dict = ordinary media cue.
    action_spec: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise routing target, crop, rotation and mask once, at construction."""
        # Every consumer downstream (routing, conflict detection, live badges,
        # output window) can then trust these values without re-validating.
        self.output_target = normalize_output_target(self.output_target)
        self.crop = sanitize_crop(self.crop)
        self.rotation = normalize_rotation(self.rotation)
        self.mask_polygon = sanitize_mask_polygon(self.mask_polygon)
        self.mask_feather = sanitize_mask_feather(self.mask_feather)
        if self.media_type == MediaType.ACTION:
            self.action_spec = sanitize_action_spec(self.action_spec)
            self.file_path = ""
        else:
            self.action_spec = {}
        self.audio_mix = _audio_mix(self.audio_mix, self.audio_output, self.media_type)

    # ── Path Resolution & Security ────────────────────────────────────
    def resolve_media_path(self, project_root: str | Path) -> str:
        """Resolve and validate relative media file_path against project_root.

        Raises:
            ValueError: If the resolved path escapes project_root (Path Traversal prevention).
        """
        root = Path(project_root).resolve()
        p = Path(self.file_path)
        if not p.is_absolute():
            resolved = (root / p).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(
                    f"Path traversal detected: '{self.file_path}' resolves outside project root '{root}'"
                )
            self.file_path = str(resolved)

        if self.original_file_path:
            orig_p = Path(self.original_file_path)
            if not orig_p.is_absolute():
                resolved_orig = (root / orig_p).resolve()
                if not resolved_orig.is_relative_to(root):
                    raise ValueError(
                        f"Path traversal detected: '{self.original_file_path}' resolves outside project root '{root}'"
                    )
                self.original_file_path = str(resolved_orig)

        return self.file_path

    # ── Validation ────────────────────────────────────────────────────
    def validate(self) -> list[str]:
        """Validate cue data and return a list of error strings (empty = valid).

        Checks performed:
        - file_path exists on disk
        - layer is 1, 2, or 3
        - volume in 0.0 – 1.0
        - in_point >= 0 and out_point (if set) > in_point
        - fade values >= 0
        - crop values in 0.0 – 1.0
        - scale > 0
        - rotation in (-180, 180] and a polygon mask has at least 3 points
        """
        errors: list[str] = []

        if self.media_type.has_file and not os.path.isfile(self.file_path):
            errors.append(f"Media file not found: {self.file_path}")

        if self.group_mode not in _VALID_GROUP_MODES:
            errors.append(f"group_mode must be one of {_VALID_GROUP_MODES} – got {self.group_mode}")

        if self.layer not in (1, 2, 3):
            errors.append(f"Layer must be 1, 2, or 3 – got {self.layer}")

        if self.output_target not in _VALID_OUTPUT_TARGETS:
            errors.append(
                f"output_target must be one of {_VALID_OUTPUT_TARGETS} – got {self.output_target}"
            )

        if not 0.0 <= self.volume <= 1.0:
            errors.append(f"Volume must be 0.0–1.0 – got {self.volume}")

        if not 0.0 <= self.opacity <= 1.0:
            errors.append(f"Opacity must be 0.0–1.0 – got {self.opacity}")

        if self.hold_time < 0.0:
            errors.append(f"hold_time must be >= 0 – got {self.hold_time}")
        if self.pre_delay < 0.0:
            errors.append(f"pre_delay must be >= 0 – got {self.pre_delay}")
        if self.post_delay < 0.0:
            errors.append(f"post_delay must be >= 0 – got {self.post_delay}")
        if self.follow_mode not in _VALID_FOLLOW_MODES:
            errors.append(f"follow_mode must be one of {_VALID_FOLLOW_MODES} – got {self.follow_mode}")

        if self.in_point < 0.0:
            errors.append(f"in_point must be >= 0 – got {self.in_point}")

        if self.out_point is not None and self.out_point <= self.in_point:
            errors.append(
                f"out_point ({self.out_point}) must be > in_point ({self.in_point})"
            )

        if self.fade_in < 0.0:
            errors.append(f"fade_in must be >= 0 – got {self.fade_in}")
        if self.fade_out < 0.0:
            errors.append(f"fade_out must be >= 0 – got {self.fade_out}")

        for key in ("x", "y", "w", "h"):
            val = self.crop.get(key, 0.0)
            if not 0.0 <= val <= 1.0:
                errors.append(f"crop['{key}'] must be 0.0–1.0 – got {val}")

        if self.scale <= 0.0:
            errors.append(f"scale must be > 0 – got {self.scale}")

        if not -180.0 < self.rotation <= 180.0:
            errors.append(f"rotation must be in (-180, 180] – got {self.rotation}")

        if self.mask_polygon and len(self.mask_polygon) < MASK_MIN_POINTS:
            errors.append(
                f"mask_polygon needs at least {MASK_MIN_POINTS} points – got {len(self.mask_polygon)}"
            )

        if self.fade_curve not in _VALID_FADE_CURVES:
            errors.append(f"fade_curve must be one of {_VALID_FADE_CURVES} – got {self.fade_curve}")

        if self.image_timeline_sec <= 0.0:
            errors.append(f"image_timeline_sec must be > 0 – got {self.image_timeline_sec}")

        if errors:
            logger.warning("Cue %d ('%s') validation errors: %s", self.cue_id, self.name, errors)

        return errors

    # ── Serialization ─────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        """Serialize the cue to a plain dict suitable for JSON storage."""
        return {
            "cue_id": self.cue_id,
            "q_label": self.q_label,
            "name": self.name,
            "media_type": self.media_type.value,
            "file_path": self.file_path,
            "layer": self.layer,
            "volume": self.volume,
            "loop": self.loop,
            "loop_count": self.loop_count,
            "in_point": self.in_point,
            "out_point": self.out_point,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "crop": dict(self.crop),
            "rotation": self.rotation,
            "mask_polygon": [list(pt) for pt in self.mask_polygon],
            "mask_feather": self.mask_feather,
            "aspect_ratio": self.aspect_ratio,
            "status": self.status.value,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "position_z": self.position_z,
            "scale": self.scale,
            "opacity": self.opacity,
            "notes": self.notes,
            "hold_time": self.hold_time,
            "pre_delay": round(float(self.pre_delay), 3),
            "post_delay": round(float(self.post_delay), 3),
            "follow_mode": self.follow_mode,
            "exclusive": self.exclusive,
            "confirm_start": self.confirm_start,
            "fade_others": self.fade_others,
            "adlib": self.adlib,
            "hotkey": self.hotkey,
            "hotkey_mode": self.hotkey_mode,
            "call_only": self.call_only,
            "enabled": self.enabled,
            "start_clock": self.start_clock,
            "audio_output": self.audio_output,
            "playback_rate": self.playback_rate,
            "keep_pitch": self.keep_pitch,
            "audio_mix": _audio_mix(self.audio_mix, self.audio_output, self.media_type),
            "script_page": self.script_page,
            "script_line": self.script_line,
            "start_rel_cue": self.start_rel_cue,
            "start_rel_when": self.start_rel_when,
            "start_rel_offset": self.start_rel_offset,
            "start_rel_marker": self.start_rel_marker,
            "markers": [dict(m) for m in self.markers],
            "color": _sanitize_hex_color(self.color),
            "parent_id": self.parent_id,
            "group_mode": self.group_mode,
            "collapsed": self.collapsed,
            "playlist": self.playlist,
            "fade_curve": self.fade_curve,
            "volume_points": [[round(float(t), 4), round(float(v), 4)] for t, v in self.volume_points],
            "opacity_points": [[round(float(t), 4), round(float(v), 4)] for t, v in self.opacity_points],
            "image_timeline_sec": self.image_timeline_sec,
            "sections": [sec.to_dict() for sec in self.sections],
            "normalize_audio": self.normalize_audio,
            "loudness_lufs": self.loudness_lufs,
            "true_peak_dbfs": self.true_peak_dbfs,
            "auto_gain_db": round(float(self.auto_gain_db), 2),
            "original_file_path": self.original_file_path,
            "timeline_composed": self.timeline_composed,
            "surface_id": self.surface_id,
            "output_target": self.output_target,
            "text_spec": dict(self.text_spec),
            "crossfade": round(float(self.crossfade), 3),
            "crossfade_style": self.crossfade_style if self.crossfade_style in CROSSFADE_STYLES else "dissolve",
            "hold_last_frame": bool(self.hold_last_frame),
            # Fresh lists: undo snapshots must not share them with the live cue.
            "action_spec": (
                sanitize_action_spec(self.action_spec)
                if self.media_type == MediaType.ACTION else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_root: str | Path | None = None) -> Cue:
        """Deserialize a cue from a plain dict.

        The class-level counter is advanced past the loaded ID so that
        future auto-IDs never collide with stored ones.
        """
        in_pt = _safe_float(data.get("in_point", 0.0), 0.0, min_val=0.0)
        out_pt = _safe_opt_float(data.get("out_point"), min_val=0.0)
        if out_pt is not None and out_pt <= in_pt:
            out_pt = None

        def _clean_env_points(raw_pts: object) -> list[list[float]]:
            cleaned: list[list[float]] = []
            if not isinstance(raw_pts, (list, tuple)):
                return cleaned
            for p in raw_pts:
                if not isinstance(p, (list, tuple)) or len(p) < 2:
                    continue
                t_val = _safe_opt_float(p[0], min_val=0.0)
                v_val = _safe_opt_float(p[1], min_val=0.0, max_val=1.0)
                if t_val is not None and v_val is not None:
                    cleaned.append([t_val, v_val])
            return cleaned

        cue = cls(
            name=str(data["name"]),
            media_type=MediaType(data["media_type"]),
            file_path=str(data["file_path"]),
            cue_id=_safe_int(data["cue_id"], next(cls._id_counter), min_val=1),
            q_label=str(data.get("q_label", "") or ""),
            layer=_safe_int(data.get("layer", 1), 1, min_val=1, max_val=3),
            volume=_safe_float(data.get("volume", 1.0), 1.0, min_val=0.0, max_val=1.0),
            loop=bool(data.get("loop", False)),
            loop_count=_safe_int(data.get("loop_count", 0), 0, min_val=0),
            in_point=in_pt,
            out_point=out_pt,
            fade_in=_safe_float(data.get("fade_in", 0.0), 0.0, min_val=0.0),
            fade_out=_safe_float(data.get("fade_out", 0.0), 0.0, min_val=0.0),
            crop=data.get("crop", _default_crop()),
            rotation=normalize_rotation(data.get("rotation", 0.0)),
            mask_polygon=sanitize_mask_polygon(data.get("mask_polygon")),
            mask_feather=sanitize_mask_feather(data.get("mask_feather", 0.0)),
            aspect_ratio=data.get("aspect_ratio"),
            status=CueStatus(data.get("status", "OFFLINE")),
            position_x=_safe_float(data.get("position_x", 0.0), 0.0, min_val=-5.0, max_val=5.0),
            position_y=_safe_float(data.get("position_y", 0.0), 0.0, min_val=-5.0, max_val=5.0),
            position_z=_safe_float(data.get("position_z", 0.0), 0.0, min_val=-100.0, max_val=100.0),
            scale=_safe_float(data.get("scale", 1.0), 1.0, min_val=0.05, max_val=10.0),
            opacity=_safe_float(data.get("opacity", 1.0), 1.0, min_val=0.0, max_val=1.0),
            notes=str(data.get("notes", "") or ""),
            hold_time=_safe_float(data.get("hold_time", 0.0), 0.0, min_val=0.0),
            pre_delay=_safe_float(data.get("pre_delay", 0.0), 0.0, min_val=0.0),
            post_delay=_safe_float(data.get("post_delay", 0.0), 0.0, min_val=0.0),
            exclusive=bool(data.get("exclusive", False)),
            confirm_start=bool(data.get("confirm_start", False)),
            fade_others=max(0.0, float(data.get("fade_others", 0.0) or 0.0)),
            adlib=bool(data.get("adlib", False)),
            hotkey=str(data.get("hotkey", "") or "")[:1].upper(),
            hotkey_mode=str(data.get("hotkey_mode", "trigger") or "trigger")
            if str(data.get("hotkey_mode", "trigger")) in HOTKEY_MODES else "trigger",
            call_only=bool(data.get("call_only", False)),
            enabled=bool(data.get("enabled", True)),
            start_clock=_clock_text(data.get("start_clock", "")),
            audio_output=_audio_output(data.get("audio_output", "stage")),
            playback_rate=_safe_float(data.get("playback_rate", 1.0), 1.0, min_val=0.5, max_val=2.0),
            keep_pitch=bool(data.get("keep_pitch", True)),
            audio_mix=dict(data["audio_mix"]) if isinstance(data.get("audio_mix"), dict) else {},
            script_page=str(data.get("script_page", "") or "")[:20],
            script_line=str(data.get("script_line", "") or "")[:300],
            start_rel_cue=_safe_int(data.get("start_rel_cue"), 0, min_val=0) or None
            if data.get("start_rel_cue") not in (None, "", 0) else None,
            start_rel_when=str(data.get("start_rel_when", "start"))
            if str(data.get("start_rel_when", "start")) in RELATIVE_WHEN else "start",
            start_rel_offset=min(600.0, max(0.0, float(data.get("start_rel_offset", 0.0) or 0.0))),
            start_rel_marker=_safe_int(data.get("start_rel_marker"), 0, min_val=0) or None,
            markers=sanitize_markers(data.get("markers")),
            follow_mode=(
                data.get("follow_mode", FollowMode.MANUAL.value)
                if data.get("follow_mode", FollowMode.MANUAL.value) in _VALID_FOLLOW_MODES
                else FollowMode.MANUAL.value
            ),
            color=_sanitize_hex_color(data.get("color", "")),
            parent_id=data.get("parent_id"),
            group_mode=(
                data.get("group_mode", GroupMode.STEP.value)
                if data.get("group_mode", GroupMode.STEP.value) in _VALID_GROUP_MODES
                else GroupMode.STEP.value
            ),
            collapsed=bool(data.get("collapsed", False)),
            playlist=bool(data.get("playlist", False)),
            fade_curve=(
                data.get("fade_curve", "log")
                if data.get("fade_curve", "log") in _VALID_FADE_CURVES
                else "log"
            ),
            volume_points=_clean_env_points(data.get("volume_points")),
            opacity_points=_clean_env_points(data.get("opacity_points")),
            image_timeline_sec=_safe_float(data.get("image_timeline_sec", 10.0), 10.0, min_val=1.0),
            sections=[
                CueSection.from_dict(raw)
                for raw in (data.get("sections") or [])
                if isinstance(raw, dict)
            ],
            normalize_audio=bool(data.get("normalize_audio", False)),
            loudness_lufs=_safe_opt_float(data.get("loudness_lufs")),
            true_peak_dbfs=_safe_opt_float(data.get("true_peak_dbfs")),
            auto_gain_db=_safe_float(data.get("auto_gain_db", 0.0), 0.0, min_val=-40.0, max_val=40.0),
            original_file_path=data.get("original_file_path"),
            timeline_composed=bool(data.get("timeline_composed", False)),
            surface_id=str(data.get("surface_id", "default") or "default"),
            output_target=normalize_output_target(data.get("output_target", "A")),
            text_spec=dict(data.get("text_spec") or {}),
            crossfade=max(0.0, float(data.get("crossfade", 0.0) or 0.0)),
            crossfade_style=(str(data.get("crossfade_style") or "dissolve")
                             if str(data.get("crossfade_style") or "dissolve") in CROSSFADE_STYLES else "dissolve"),
            hold_last_frame=bool(data.get("hold_last_frame", False)),
            action_spec=(
                dict(data["action_spec"]) if isinstance(data.get("action_spec"), dict) else {}
            ),
        )
        # Safely advance class ID counter O(1) without CPU-bound loops
        current_next = next(cls._id_counter)
        if isinstance(cue.cue_id, int) and cue.cue_id >= current_next:
            cls._id_counter = itertools.count(cue.cue_id + 1)
        if project_root is not None and cue.media_type.has_file:
            cue.resolve_media_path(project_root)
        if cue.text_spec and not Path(cue.file_path).is_file():
            # Text cues are re-creatable from their settings (e.g. a show
            # opened on another computer without the cached caption image).
            try:
                from engine.text_render import render_text_png
                cue.file_path = render_text_png(cue.text_spec)
            except Exception as exc:  # pragma: no cover - needs Qt GUI
                logger.warning("Could not re-render text cue %s: %s", cue.cue_id, exc)
        return cue

    # ── Helpers ───────────────────────────────────────────────────────
    def __str__(self) -> str:
        """Compact one-line description used in logs and status messages."""
        layer = "" if self.media_type == MediaType.ACTION else f" L{self.layer}"
        return (
            f"Cue #{self.cue_id} '{self.name}' "
            f"[{self.media_type.value}]{layer} "
            f"({self.status.value})"
        )


@dataclass
class LayerConflict:
    """Represents a simultaneous layer collision between two or more cues."""

    cue_id: int
    conflicting_with_ids: list[int]
    conflicting_with_names: list[str]
    layer: int
    reason: str


def _record_conflict(
    conflicts: dict[int, LayerConflict],
    cue_id: int,
    conflicting_ids: list[int],
    conflicting_names: list[str],
    layer: int,
    reason: str,
) -> None:
    if cue_id not in conflicts:
        conflicts[cue_id] = LayerConflict(
            cue_id=cue_id,
            conflicting_with_ids=list(conflicting_ids),
            conflicting_with_names=list(conflicting_names),
            layer=layer,
            reason=reason,
        )
    else:
        existing = conflicts[cue_id]
        for cid, cname in zip(conflicting_ids, conflicting_names, strict=True):
            if cid not in existing.conflicting_with_ids:
                existing.conflicting_with_ids.append(cid)
                existing.conflicting_with_names.append(cname)
        if reason not in existing.reason:
            existing.reason += f"\n• {reason}"


def detect_layer_conflicts(
    cues: Sequence[Cue], dual_active: bool = True
) -> dict[int, LayerConflict]:
    """Scan cues and detect simultaneous layer collisions (non-blocking pre-flight check).

    Collisions occur when two or more playable cues (VIDEO, AUDIO, IMAGE) share the
    same layer (1, 2, or 3) and are triggered simultaneously:
      1. Direct children of a Group in SIMULTANEOUS mode.
      2. Chained cues where preceding cues use FollowMode.SIMULTANEOUS.

    ``dual_active`` mirrors the current output mode: when the two independent
    outputs are off, every cue ends up on output A, so ``A·L2`` and ``B·L2``
    do collide and must be reported.

    Returns a dict mapping cue_id -> LayerConflict for all affected cues (including
    groups that contain collisions).
    """
    conflicts: dict[int, LayerConflict] = {}
    if not cues:
        return conflicts

    def target_of(cue: Cue) -> str:
        """Resolve the physical output (A/B) a cue will actually use."""
        return resolve_output_target(cue.output_target, dual_active)

    # 1. Group simultaneous collisions (GroupMode.SIMULTANEOUS)
    for group in cues:
        if group.media_type != MediaType.GROUP:
            continue
        if getattr(group, "group_mode", GroupMode.STEP.value) != GroupMode.SIMULTANEOUS.value:
            continue

        children = [c for c in cues if c.parent_id == group.cue_id and c.media_type.has_file]
        by_layer: dict[tuple[str, int], list[Cue]] = {}
        for ch in children:
            by_layer.setdefault((target_of(ch), ch.layer), []).append(ch)

        for (target, layer), layer_children in by_layer.items():
            if len(layer_children) > 1:
                layer_txt = layer_label(layer, target)
                # Flag each colliding child
                for child in layer_children:
                    others = [c for c in layer_children if c.cue_id != child.cue_id]
                    other_names = ", ".join(f"'{o.name}'" for o in others)
                    reason = (
                        f"Conflitto {layer_txt}: Viene attivato in simultanea con {other_names} "
                        f"nel gruppo '{group.name}' sullo stesso {layer_txt}. "
                        f"Assegna un layer differente (L1, L2, L3)."
                    )
                    _record_conflict(
                        conflicts,
                        child.cue_id,
                        [o.cue_id for o in others],
                        [o.name for o in others],
                        layer,
                        reason,
                    )
                # Flag the group container itself
                all_names = ", ".join(f"'{c.name}'" for c in layer_children)
                grp_reason = (
                    f"Conflitto {layer_txt}: {len(layer_children)} elementi ({all_names}) "
                    f"condividono il {layer_txt} in modalità simultanea. Assegna layer differenti (L1, L2, L3)."
                )
                _record_conflict(
                    conflicts,
                    group.cue_id,
                    [c.cue_id for c in layer_children],
                    [c.name for c in layer_children],
                    layer,
                    grp_reason,
                )

    # 2. Sequential SIMULTANEOUS follow-mode chains
    i = 0
    n = len(cues)
    while i < n:
        if cues[i].follow_mode == FollowMode.SIMULTANEOUS.value:
            chain: list[Cue] = [cues[i]]
            j = i
            while j < n and cues[j].follow_mode == FollowMode.SIMULTANEOUS.value:
                j += 1
                if j < n:
                    chain.append(cues[j])
                    if cues[j].media_type == MediaType.GROUP:
                        break

            playable = [c for c in chain if c.media_type.has_file]
            by_layer: dict[tuple[str, int], list[Cue]] = {}
            for c in playable:
                by_layer.setdefault((target_of(c), c.layer), []).append(c)

            for (target, layer), layer_cues in by_layer.items():
                if len(layer_cues) > 1:
                    layer_txt = layer_label(layer, target)
                    for cue in layer_cues:
                        others = [c for c in layer_cues if c.cue_id != cue.cue_id]
                        other_names = ", ".join(f"'{o.name}'" for o in others)
                        reason = (
                            f"Conflitto {layer_txt}: Avvio simultaneo (Follow Simultaneo) "
                            f"con {other_names} sullo stesso {layer_txt}. "
                            f"Assegna un layer differente (L1, L2, L3)."
                        )
                        _record_conflict(
                            conflicts,
                            cue.cue_id,
                            [o.cue_id for o in others],
                            [o.name for o in others],
                            layer,
                            reason,
                        )
            i = j
        else:
            i += 1

    return conflicts

