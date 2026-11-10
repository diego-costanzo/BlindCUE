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
from typing import Any, ClassVar, Dict, Optional

logger = logging.getLogger(__name__)


class MediaType(Enum):
    """Supported media types for cues."""
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"


class CueStatus(Enum):
    """Lifecycle status of a cue."""
    OFFLINE = "OFFLINE"
    LOADED = "LOADED"
    LIVE = "LIVE"
    PREVIZ = "PREVIZ"


def _default_crop() -> Dict[str, float]:
    """Return default full-frame crop rectangle."""
    return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


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
    """

    # ── Class-level auto-increment counter ────────────────────────────
    _id_counter: ClassVar[itertools.count] = itertools.count(1)

    # ── Required fields ───────────────────────────────────────────────
    name: str
    media_type: MediaType
    file_path: str

    # ── Optional / defaulted fields ───────────────────────────────────
    cue_id: int = field(default_factory=lambda: next(Cue._id_counter))
    layer: int = 1
    volume: float = 1.0
    loop: bool = False
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

        if not os.path.isfile(self.file_path):
            errors.append(f"Media file not found: {self.file_path}")

        if self.layer not in (1, 2, 3):
            errors.append(f"Layer must be 1, 2, or 3 – got {self.layer}")

        if not 0.0 <= self.volume <= 1.0:
            errors.append(f"Volume must be 0.0–1.0 – got {self.volume}")

        if not 0.0 <= self.opacity <= 1.0:
            errors.append(f"Opacity must be 0.0–1.0 – got {self.opacity}")

        if self.hold_time < 0.0:
            errors.append(f"hold_time must be >= 0 – got {self.hold_time}")

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

        if errors:
            logger.warning("Cue %d ('%s') validation errors: %s", self.cue_id, self.name, errors)

        return errors

    # ── Serialization ─────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the cue to a plain dict suitable for JSON storage."""
        return {
            "cue_id": self.cue_id,
            "name": self.name,
            "media_type": self.media_type.value,
            "file_path": self.file_path,
            "layer": self.layer,
            "volume": self.volume,
            "loop": self.loop,
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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Cue:
        """Deserialize a cue from a plain dict.

        The class-level counter is advanced past the loaded ID so that
        future auto-IDs never collide with stored ones.
        """
        cue = cls(
            name=data["name"],
            media_type=MediaType(data["media_type"]),
            file_path=data["file_path"],
            cue_id=data["cue_id"],
            layer=data.get("layer", 1),
            volume=data.get("volume", 1.0),
            loop=data.get("loop", False),
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
            hold_time=data.get("hold_time", 0.0),
        )
        # Safely advance class ID counter O(1) without CPU-bound loops
        current_next = next(cls._id_counter)
        if isinstance(cue.cue_id, int) and cue.cue_id >= current_next:
            cls._id_counter = itertools.count(cue.cue_id + 1)
        return cue

    # ── Helpers ───────────────────────────────────────────────────────
    def __str__(self) -> str:
        return (
            f"Cue #{self.cue_id} '{self.name}' "
            f"[{self.media_type.value}] L{self.layer} "
            f"({self.status.value})"
        )
