"""Data model for show cues (audio, video, image).

Each Cue represents a single media item that can be played, previewed
or composited on the output window across layers 1-3.
"""

from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


class MediaType(Enum):
    """Supported media types for cues."""
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    GROUP = "GROUP"


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


def _default_crop() -> Dict[str, float]:
    """Return default full-frame crop rectangle."""
    return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


_VALID_FADE_CURVES = ("log", "scurve", "linear")
_VALID_FOLLOW_MODES = tuple(m.value for m in FollowMode)
_VALID_GROUP_MODES = tuple(m.value for m in GroupMode)


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


@dataclass
class CueSection:
    """Contiguous virtual section inside an audio or video Cue."""

    label: str
    start: float
    end: Optional[float] = None
    loops: int = 1   # 1 = once (default), >=2 = N repeats, 0 = infinite vamp
    skip: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "start": round(float(self.start), 4),
            "end": round(float(self.end), 4) if self.end is not None else None,
            "loops": int(self.loops),
            "skip": bool(self.skip),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CueSection:
        end_raw = data.get("end")
        return cls(
            label=str(data.get("label", "A")),
            start=max(0.0, float(data.get("start", 0.0))),
            end=max(0.0, float(end_raw)) if end_raw is not None else None,
            loops=max(0, int(data.get("loops", 1))),
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
    out_point: Optional[float] = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    crop: Dict[str, float] = field(default_factory=_default_crop)
    aspect_ratio: Optional[str] = None
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
    color: str = ""  # Optional '#RRGGBB' group/divider colour in Scaletta & Live
    parent_id: Optional[int] = None  # None = root cue; int = belongs to parent Group cue
    group_mode: str = GroupMode.STEP.value  # SIMULTANEOUS, SEQUENCE, STEP, RANDOM, LOOP
    collapsed: bool = False  # UI collapse state for GROUP cues
    fade_curve: str = "log"  # "log" (perceptual), "scurve" (cosine), "linear"
    volume_points: list[list[float]] = field(default_factory=list)   # [[time_sec, level 0..1], ...]
    opacity_points: list[list[float]] = field(default_factory=list)  # [[time_sec, opacity 0..1], ...]
    image_timeline_sec: float = 10.0  # Virtual timeline horizon (s) for infinite-hold images
    sections: list[CueSection] = field(default_factory=list)         # Contiguous virtual playback sections
    normalize_audio: bool = False  # EBU R128 (-16 LUFS) normalization active for this cue
    loudness_lufs: Optional[float] = None  # Measured integrated loudness (LUFS)
    true_peak_dbfs: Optional[float] = None  # Measured true peak (dBFS)
    auto_gain_db: float = 0.0  # Computed gain adjustment in dB to reach target (-16 LUFS)
    original_file_path: Optional[str] = None  # Backup of original path if dynamics-optimized copy is used
    timeline_composed: bool = False  # GROUP cue configured/synced via multi-track studio timeline
    surface_id: str = "default"  # Target virtual screen / mapping surface ID ("default" = full screen)

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
        """
        errors: list[str] = []

        if self.media_type != MediaType.GROUP and not os.path.isfile(self.file_path):
            errors.append(f"Media file not found: {self.file_path}")

        if self.group_mode not in _VALID_GROUP_MODES:
            errors.append(f"group_mode must be one of {_VALID_GROUP_MODES} – got {self.group_mode}")

        if self.layer not in (1, 2, 3):
            errors.append(f"Layer must be 1, 2, or 3 – got {self.layer}")

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

        if self.fade_curve not in _VALID_FADE_CURVES:
            errors.append(f"fade_curve must be one of {_VALID_FADE_CURVES} – got {self.fade_curve}")

        if self.image_timeline_sec <= 0.0:
            errors.append(f"image_timeline_sec must be > 0 – got {self.image_timeline_sec}")

        if errors:
            logger.warning("Cue %d ('%s') validation errors: %s", self.cue_id, self.name, errors)

        return errors

    # ── Serialization ─────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
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
            "color": _sanitize_hex_color(self.color),
            "parent_id": self.parent_id,
            "group_mode": self.group_mode,
            "collapsed": self.collapsed,
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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], project_root: str | Path | None = None) -> Cue:
        """Deserialize a cue from a plain dict.

        The class-level counter is advanced past the loaded ID so that
        future auto-IDs never collide with stored ones.
        """
        cue = cls(
            name=data["name"],
            media_type=MediaType(data["media_type"]),
            file_path=data["file_path"],
            cue_id=data["cue_id"],
            q_label=str(data.get("q_label", "") or ""),
            layer=data.get("layer", 1),
            volume=data.get("volume", 1.0),
            loop=data.get("loop", False),
            loop_count=data.get("loop_count", 0),
            in_point=data.get("in_point", 0.0),
            out_point=data.get("out_point"),
            fade_in=data.get("fade_in", 0.0),
            fade_out=data.get("fade_out", 0.0),
            crop=data.get("crop", _default_crop()),
            aspect_ratio=data.get("aspect_ratio"),
            status=CueStatus(data.get("status", "OFFLINE")),
            position_x=data.get("position_x", 0.0),
            position_y=data.get("position_y", 0.0),
            position_z=data.get("position_z", 0.0),
            scale=data.get("scale", 1.0),
            opacity=data.get("opacity", 1.0),
            notes=data.get("notes", ""),
            hold_time=max(0.0, float(data.get("hold_time", 0.0) or 0.0)),
            pre_delay=max(0.0, float(data.get("pre_delay", 0.0) or 0.0)),
            post_delay=max(0.0, float(data.get("post_delay", 0.0) or 0.0)),
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
            fade_curve=(
                data.get("fade_curve", "log")
                if data.get("fade_curve", "log") in _VALID_FADE_CURVES
                else "log"
            ),
            volume_points=[
                [max(0.0, float(p[0])), max(0.0, min(1.0, float(p[1])))]
                for p in (data.get("volume_points") or [])
                if isinstance(p, (list, tuple)) and len(p) >= 2
            ],
            opacity_points=[
                [max(0.0, float(p[0])), max(0.0, min(1.0, float(p[1])))]
                for p in (data.get("opacity_points") or [])
                if isinstance(p, (list, tuple)) and len(p) >= 2
            ],
            image_timeline_sec=max(1.0, float(data.get("image_timeline_sec", 10.0) or 10.0)),
            sections=[
                CueSection.from_dict(raw)
                for raw in (data.get("sections") or [])
                if isinstance(raw, dict)
            ],
            normalize_audio=bool(data.get("normalize_audio", False)),
            loudness_lufs=float(data["loudness_lufs"]) if data.get("loudness_lufs") is not None else None,
            true_peak_dbfs=float(data["true_peak_dbfs"]) if data.get("true_peak_dbfs") is not None else None,
            auto_gain_db=float(data.get("auto_gain_db", 0.0) or 0.0),
            original_file_path=data.get("original_file_path"),
            timeline_composed=bool(data.get("timeline_composed", False)),
            surface_id=str(data.get("surface_id", "default") or "default"),
        )
        # Safely advance class ID counter O(1) without CPU-bound loops
        current_next = next(cls._id_counter)
        if isinstance(cue.cue_id, int) and cue.cue_id >= current_next:
            cls._id_counter = itertools.count(cue.cue_id + 1)
        if project_root is not None and cue.media_type != MediaType.GROUP:
            cue.resolve_media_path(project_root)
        return cue

    # ── Helpers ───────────────────────────────────────────────────────
    def __str__(self) -> str:
        return (
            f"Cue #{self.cue_id} '{self.name}' "
            f"[{self.media_type.value}] L{self.layer} "
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
        for cid, cname in zip(conflicting_ids, conflicting_names):
            if cid not in existing.conflicting_with_ids:
                existing.conflicting_with_ids.append(cid)
                existing.conflicting_with_names.append(cname)
        if reason not in existing.reason:
            existing.reason += f"\n• {reason}"


def detect_layer_conflicts(cues: Sequence[Cue]) -> dict[int, LayerConflict]:
    """Scan cues and detect simultaneous layer collisions (non-blocking pre-flight check).

    Collisions occur when two or more playable cues (VIDEO, AUDIO, IMAGE) share the
    same layer (1, 2, or 3) and are triggered simultaneously:
      1. Direct children of a Group in SIMULTANEOUS mode.
      2. Chained cues where preceding cues use FollowMode.SIMULTANEOUS.

    Returns a dict mapping cue_id -> LayerConflict for all affected cues (including
    groups that contain collisions).
    """
    conflicts: dict[int, LayerConflict] = {}
    if not cues:
        return conflicts

    # 1. Group simultaneous collisions (GroupMode.SIMULTANEOUS)
    for group in cues:
        if group.media_type != MediaType.GROUP:
            continue
        if getattr(group, "group_mode", GroupMode.STEP.value) != GroupMode.SIMULTANEOUS.value:
            continue

        children = [c for c in cues if c.parent_id == group.cue_id and c.media_type != MediaType.GROUP]
        by_layer: dict[int, list[Cue]] = {}
        for ch in children:
            by_layer.setdefault(ch.layer, []).append(ch)

        for layer, layer_children in by_layer.items():
            if len(layer_children) > 1:
                # Flag each colliding child
                for child in layer_children:
                    others = [c for c in layer_children if c.cue_id != child.cue_id]
                    other_names = ", ".join(f"'{o.name}'" for o in others)
                    reason = (
                        f"Conflitto Layer {layer}: Viene attivato in simultanea con {other_names} "
                        f"nel gruppo '{group.name}' sullo stesso Layer {layer}. "
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
                    f"Conflitto Layer {layer}: {len(layer_children)} elementi ({all_names}) "
                    f"condividono il Layer {layer} in modalità simultanea. Assegna layer differenti (L1, L2, L3)."
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

            playable = [c for c in chain if c.media_type != MediaType.GROUP]
            by_layer: dict[int, list[Cue]] = {}
            for c in playable:
                by_layer.setdefault(c.layer, []).append(c)

            for layer, layer_cues in by_layer.items():
                if len(layer_cues) > 1:
                    for cue in layer_cues:
                        others = [c for c in layer_cues if c.cue_id != cue.cue_id]
                        other_names = ", ".join(f"'{o.name}'" for o in others)
                        reason = (
                            f"Conflitto Layer {layer}: Avvio simultaneo (Follow Simultaneo) "
                            f"con {other_names} sullo stesso Layer {layer}. "
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

