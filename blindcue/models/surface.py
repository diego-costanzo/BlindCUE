"""Data model for virtual screens, projection surfaces, and video mapping.

Supports:
- RECTANGLE mode: standard normalized (x, y, w, h) sub-screen projection
  (split screens, dual/triple projector desktop span, letterbox, PiP).
- QUAD mode: 4-corner perspective keystone / corner-pinning homography
  (projecting onto angled scenic walls, frames, pillars, or architectural shapes).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SurfaceMode(str, Enum):
    """Mapping projection geometry mode."""
    RECTANGLE = "RECTANGLE"
    QUAD = "QUAD"


class MaskType(str, Enum):
    """Surface clipping and cutout mask type."""
    NONE = "none"
    ELLIPSE = "ellipse"          # Circular / Elliptical cutout
    HOLE = "hole"                # Inner rectangular hole / cutout
    IMAGE = "image"              # Custom PNG mask file


DEFAULT_SURFACE_ID = "default"
DEFAULT_SURFACE_NAME = "Schermo Intero (Default)"

SURFACE_COLORS = [
    "#00f0ff",  # Ciano elettrico
    "#f59e0b",  # Ambra calda
    "#10b981",  # Smeraldo
    "#ec4899",  # Magenta
    "#8b5cf6",  # Viola
    "#06b6d4",  # Turchese
    "#eab308",  # Giallo oro
    "#3b82f6",  # Blu cobalto
]


@dataclass
class SurfaceDefinition:
    """A virtual screen or surface slice for projection mapping.

    All spatial coordinates are normalized in the 0.0 – 1.0 range relative
    to the active OutputWindow canvas (e.g. 1920x1080 for single screen,
    3840x1080 for dual-projector horizontal span).

    In RECTANGLE mode:
        x, y: top-left corner (0.0 – 1.0)
        w, h: width and height (0.01 – 1.0)

    In QUAD mode:
        corners: 4 points [TL, TR, BR, BL] -> [[x, y], [x, y], [x, y], [x, y]]
        Mapped onto stage pixels via QTransform.quadToQuad().
    """

    surface_id: str = DEFAULT_SURFACE_ID
    name: str = DEFAULT_SURFACE_NAME
    mode: str = SurfaceMode.RECTANGLE.value

    # RECTANGLE mode normalized coordinates
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0

    # QUAD mode normalized 4 corners: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]
    corners: list[list[float]] = field(default_factory=lambda: [
        [0.0, 0.0],  # C1: Top-Left
        [1.0, 0.0],  # C2: Top-Right
        [1.0, 1.0],  # C3: Bottom-Right
        [0.0, 1.0],  # C4: Bottom-Left
    ])

    color: str = "#00f0ff"
    blend_left: float = 0.0   # Soft edge blend (0.0 - 0.5) for multi-projector overlap
    blend_right: float = 0.0  # Soft edge blend (0.0 - 0.5) for multi-projector overlap

    # Masking & Cutout properties
    mask_type: str = MaskType.NONE.value        # "none", "ellipse", "hole", "image"
    mask_invert: bool = False                   # Invert mask (e.g. punch hole instead of circle)
    mask_feather: int = 0                       # Edge feather/blur in pixels (0..50 px)
    hole_x: float = 0.25                        # Inner hole X relative to surface (0.0..1.0)
    hole_y: float = 0.25                        # Inner hole Y relative to surface (0.0..1.0)
    hole_w: float = 0.50                        # Inner hole W relative to surface (0.0..1.0)
    hole_h: float = 0.50                        # Inner hole H relative to surface (0.0..1.0)
    mask_image_path: str | None = None          # File path to custom PNG mask
    mask_show_guide: bool = False               # High-visibility optical guide projected on stage

    def __post_init__(self) -> None:
        # Keep the quad and the rectangle consistent: a surface loaded from an
        # old project (rectangle only) must still produce valid corners.
        """Keep rectangle and quad corners consistent for old or hand-edited files."""
        if self.mode not in (SurfaceMode.RECTANGLE.value, SurfaceMode.QUAD.value):
            self.mode = SurfaceMode.RECTANGLE.value
        default_corners = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        if not self.corners or len(self.corners) != 4:
            self.sync_quad_from_rect()
        elif self.mode == SurfaceMode.RECTANGLE.value and self.corners == default_corners:
            if self.x != 0.0 or self.y != 0.0 or self.w != 1.0 or self.h != 1.0:
                self.sync_quad_from_rect()

    def sync_quad_from_rect(self) -> None:
        """Derive the 4 corners from the rectangle bounds."""
        rx = max(0.0, min(1.0, float(self.x)))
        ry = max(0.0, min(1.0, float(self.y)))
        rw = max(0.01, min(1.0 - rx, float(self.w)))
        rh = max(0.01, min(1.0 - ry, float(self.h)))
        self.corners = [
            [round(rx, 6), round(ry, 6)],
            [round(rx + rw, 6), round(ry, 6)],
            [round(rx + rw, 6), round(ry + rh, 6)],
            [round(rx, 6), round(ry + rh, 6)],
        ]

    def sync_rect_from_quad(self) -> None:
        """Derive the enclosing bounding box from the 4 corners."""
        if not self.corners or len(self.corners) != 4:
            return
        xs = [pt[0] for pt in self.corners]
        ys = [pt[1] for pt in self.corners]
        min_x = max(0.0, min(1.0, min(xs)))
        max_x = max(0.0, min(1.0, max(xs)))
        min_y = max(0.0, min(1.0, min(ys)))
        max_y = max(0.0, min(1.0, max(ys)))
        self.x = round(min_x, 6)
        self.y = round(min_y, 6)
        self.w = max(0.01, round(max_x - min_x, 6))
        self.h = max(0.01, round(max_y - min_y, 6))

    def set_corner(self, index: int, x: float, y: float) -> None:
        """Update corner [0..3] ensuring coordinates stay within 0.0 - 1.0."""
        if 0 <= index < 4:
            cx = max(0.0, min(1.0, float(x)))
            cy = max(0.0, min(1.0, float(y)))
            self.corners[index] = [round(cx, 6), round(cy, 6)]
            self.sync_rect_from_quad()

    def nudge_corner(self, index: int, dx: float, dy: float) -> None:
        """Micro-nudge corner index by delta."""
        if 0 <= index < 4:
            cur = self.corners[index]
            self.set_corner(index, cur[0] + dx, cur[1] + dy)

    def nudge_rect(self, dx: float, dy: float) -> None:
        """Micro-nudge rectangle position."""
        nx = max(0.0, min(1.0 - self.w, self.x + dx))
        ny = max(0.0, min(1.0 - self.h, self.y + dy))
        self.x = round(nx, 6)
        self.y = round(ny, 6)
        self.sync_quad_from_rect()

    def to_dict(self) -> dict[str, Any]:
        """Serialize surface definition to dictionary."""
        return {
            "surface_id": self.surface_id,
            "name": self.name,
            "mode": self.mode,
            "x": round(float(self.x), 6),
            "y": round(float(self.y), 6),
            "w": round(float(self.w), 6),
            "h": round(float(self.h), 6),
            "corners": [
                [round(float(pt[0]), 6), round(float(pt[1]), 6)]
                for pt in self.corners
            ],
            "color": self.color,
            "blend_left": round(float(self.blend_left), 4),
            "blend_right": round(float(self.blend_right), 4),
            "mask_type": str(self.mask_type),
            "mask_invert": bool(self.mask_invert),
            "mask_feather": int(self.mask_feather),
            "hole_x": round(float(self.hole_x), 6),
            "hole_y": round(float(self.hole_y), 6),
            "hole_w": round(float(self.hole_w), 6),
            "hole_h": round(float(self.hole_h), 6),
            "mask_image_path": self.mask_image_path,
            "mask_show_guide": bool(self.mask_show_guide),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SurfaceDefinition:
        """Deserialize surface definition from dictionary."""
        raw_corners = data.get("corners")
        if not raw_corners or len(raw_corners) != 4:
            raw_corners = [
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
            ]
        else:
            raw_corners = [
                [float(pt[0]), float(pt[1])]
                for pt in raw_corners
            ]

        mode = data.get("mode", SurfaceMode.RECTANGLE.value)
        if mode not in (SurfaceMode.RECTANGLE.value, SurfaceMode.QUAD.value):
            mode = SurfaceMode.RECTANGLE.value

        return cls(
            surface_id=str(data.get("surface_id", DEFAULT_SURFACE_ID)),
            name=str(data.get("name", DEFAULT_SURFACE_NAME)),
            mode=mode,
            x=max(0.0, min(1.0, float(data.get("x", 0.0)))),
            y=max(0.0, min(1.0, float(data.get("y", 0.0)))),
            w=max(0.01, min(1.0, float(data.get("w", 1.0)))),
            h=max(0.01, min(1.0, float(data.get("h", 1.0)))),
            corners=raw_corners,
            color=str(data.get("color", "#00f0ff")),
            blend_left=max(0.0, min(0.5, float(data.get("blend_left", 0.0)))),
            blend_right=max(0.0, min(0.5, float(data.get("blend_right", 0.0)))),
            mask_type=str(data.get("mask_type", MaskType.NONE.value)),
            mask_invert=bool(data.get("mask_invert", False)),
            mask_feather=int(data.get("mask_feather", 0)),
            hole_x=max(0.0, min(1.0, float(data.get("hole_x", 0.25)))),
            hole_y=max(0.0, min(1.0, float(data.get("hole_y", 0.25)))),
            hole_w=max(0.01, min(1.0, float(data.get("hole_w", 0.50)))),
            hole_h=max(0.01, min(1.0, float(data.get("hole_h", 0.50)))),
            mask_image_path=data.get("mask_image_path"),
            mask_show_guide=bool(data.get("mask_show_guide", False)),
        )

    def clone(self, new_id: str | None = None, new_name: str | None = None) -> SurfaceDefinition:
        """Create a deep clone with optional new ID and name."""
        c = copy.deepcopy(self)
        if new_id:
            c.surface_id = new_id
        if new_name:
            c.name = new_name
        return c


def create_default_surface() -> SurfaceDefinition:
    """Return the default full-screen projection surface."""
    return SurfaceDefinition(
        surface_id=DEFAULT_SURFACE_ID,
        name=DEFAULT_SURFACE_NAME,
        mode=SurfaceMode.RECTANGLE.value,
        x=0.0,
        y=0.0,
        w=1.0,
        h=1.0,
        color="#00f0ff",
    )


# ── Built-in Presets for Theatre & Live Video Mapping ─────────────────────────

PRESET_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "Schermo Intero (100%)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0,
        "desc": "Proiezione a schermo intero standard sul monitor / proiettore selezionato",
    },
    {
        "name": "Doppio Proiettore: Metà Sinistra (0% – 50%)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0,
        "desc": "Occupa il primo proiettore in una configurazione desktop estesa a 2 proiettori",
    },
    {
        "name": "Doppio Proiettore: Metà Destra (50% – 100%)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0,
        "desc": "Occupa il secondo proiettore in una configurazione desktop estesa a 2 proiettori",
    },
    {
        "name": "Doppio Proiettore: Span Panoramico (0% – 100%)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0,
        "desc": "Si estende su entrambi i proiettori affiancati come un unico grande fondale panoramico",
    },
    {
        "name": "Triplo Proiettore: Sinistra (1/3)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.0, "y": 0.0, "w": 0.3333, "h": 1.0,
        "desc": "Occupa il proiettore 1/3 in configurazione a 3 schermi affiancati",
    },
    {
        "name": "Triplo Proiettore: Centro (2/3)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.3333, "y": 0.0, "w": 0.3334, "h": 1.0,
        "desc": "Occupa il proiettore centrale in configurazione a 3 schermi affiancati",
    },
    {
        "name": "Triplo Proiettore: Destra (3/3)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.6667, "y": 0.0, "w": 0.3333, "h": 1.0,
        "desc": "Occupa il proiettore 3/3 in configurazione a 3 schermi affiancati",
    },
    {
        "name": "Picture-in-Picture (PiP Basso DX)",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.68, "y": 0.65, "w": 0.30, "h": 0.30,
        "desc": "Riquadro d'angolo per sovrapporre una seconda immagine o video sopra il fondale",
    },
    {
        "name": "Quadro 4:3 Centrale",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.1875, "y": 0.0, "w": 0.625, "h": 1.0,
        "desc": "Area classica 4:3 centrata su schermo 16:9 con bande laterali pulite",
    },
    {
        "name": "Colonna / Scenografia SX",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.05, "y": 0.1, "w": 0.25, "h": 0.8,
        "desc": "Superficie verticale ideale per banner o colonna scenica sinistra",
    },
    {
        "name": "Colonna / Scenografia DX",
        "mode": SurfaceMode.RECTANGLE.value,
        "x": 0.70, "y": 0.1, "w": 0.25, "h": 0.8,
        "desc": "Superficie verticale ideale per banner o colonna scenica destra",
    },
]
