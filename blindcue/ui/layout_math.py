"""Shared WYSIWYG frame, edge-anchored crop, and aspect-ratio geometry math."""

from __future__ import annotations

from typing import NamedTuple, Optional

_ASPECT_RATIO_VALUES: dict[str, float] = {
    "16:9": 16.0 / 9.0,
    "16:9 (Widescreen)": 16.0 / 9.0,
    "4:3": 4.0 / 3.0,
    "4:3 (Standard)": 4.0 / 3.0,
    "21:9": 21.0 / 9.0,
    "21:9 (Ultrawide)": 21.0 / 9.0,
    "1:1": 1.0,
    "1:1 (Quadrato)": 1.0,
}


class MediaFrameGeometry(NamedTuple):
    """Exact coordinates of the uncropped frame and its edge-anchored cropped slice."""

    full_x: float
    full_y: float
    full_w: float
    full_h: float
    cut_x: float
    cut_y: float
    vis_x: float
    vis_y: float
    vis_w: float
    vis_h: float


def parse_aspect_ratio(aspect_ratio: Optional[str]) -> Optional[float]:
    """Return numeric width/height ratio for an override string, or None for Native."""
    if not aspect_ratio:
        return None
    val = _ASPECT_RATIO_VALUES.get(aspect_ratio.strip())
    if val is not None:
        return val
    # Fallback parse for custom 'W:H' strings
    if ":" in aspect_ratio:
        try:
            parts = aspect_ratio.split(":", 1)
            w = float(parts[0])
            h = float(parts[1].split()[0])
            if w > 0 and h > 0:
                return w / h
        except ValueError:
            return None
    return None


def compute_media_frame_geometry(
    stage_x: float,
    stage_y: float,
    stage_w: float,
    stage_h: float,
    source_w: float,
    source_h: float,
    scale: float = 1.0,
    pos_x: float = 0.0,
    pos_y: float = 0.0,
    crop: Optional[dict] = None,
    aspect_ratio: Optional[str] = None,
) -> MediaFrameGeometry:
    """Compute centered uncropped frame and stationary edge-anchored crop geometry."""
    sw = max(1.0, float(stage_w))
    sh = max(1.0, float(stage_h))
    stage_ar = sw / sh

    override_ar = parse_aspect_ratio(aspect_ratio)
    if override_ar is not None:
        eff_ar = override_ar
    elif source_w > 0 and source_h > 0:
        eff_ar = float(source_w) / float(source_h)
    else:
        eff_ar = stage_ar

    if eff_ar >= stage_ar:
        base_w = sw
        base_h = sw / eff_ar
    else:
        base_h = sh
        base_w = sh * eff_ar

    target_scale = max(0.1, min(5.0, float(scale)))
    full_w = max(1.0, base_w * target_scale)
    full_h = max(1.0, base_h * target_scale)

    full_x = float(stage_x) + (sw - full_w) / 2.0 + (float(pos_x) * sw)
    full_y = float(stage_y) + (sh - full_h) / 2.0 + (float(pos_y) * sh)

    c = crop or {}
    cx = max(0.0, min(0.99, float(c.get("x", 0.0))))
    cy = max(0.0, min(0.99, float(c.get("y", 0.0))))
    cw = max(0.01, min(1.0 - cx, float(c.get("w", 1.0))))
    ch = max(0.01, min(1.0 - cy, float(c.get("h", 1.0))))

    cut_x = full_w * cx
    cut_y = full_h * cy
    vis_w = max(1.0, full_w * cw)
    vis_h = max(1.0, full_h * ch)

    # Edge-anchored slice stays stationary relative to full frame
    vis_x = full_x + cut_x
    vis_y = full_y + cut_y

    return MediaFrameGeometry(
        full_x=full_x,
        full_y=full_y,
        full_w=full_w,
        full_h=full_h,
        cut_x=cut_x,
        cut_y=cut_y,
        vis_x=vis_x,
        vis_y=vis_y,
        vis_w=vis_w,
        vis_h=vis_h,
    )

