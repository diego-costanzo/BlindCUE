"""Shared WYSIWYG frame, edge-anchored crop, and aspect-ratio geometry math."""

from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath

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


def parse_aspect_ratio(aspect_ratio: str | None) -> float | None:
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
    crop: dict | None = None,
    aspect_ratio: str | None = None,
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


def polygon_path_from_normalized(
    points: list[list[float]],
    x: float,
    y: float,
    w: float,
    h: float,
) -> QPainterPath:
    """Build a closed clip path from normalised (0..1) polygon points.

    Used by both the Pre-Viz monitor and the projector output so an image mask
    is guaranteed to look identical in preview and in the venue. Invalid or
    too-short input yields an empty path, which callers treat as "no mask".
    """
    path = QPainterPath()
    if not points or len(points) < 3 or w <= 0 or h <= 0:
        return path
    path.moveTo(x + float(points[0][0]) * w, y + float(points[0][1]) * h)
    for px, py in points[1:]:
        path.lineTo(x + float(px) * w, y + float(py) * h)
    path.closeSubpath()
    return path


# The mask never needs output resolution. A hard edge keeps 1024 px so the cut
# stays crisp even on a 4K projector; a feathered edge is a smooth gradient and
# 512 px is already more than enough (the blur leaves no detail to preserve and
# the painter stretches it for free). Masks are only rebuilt when the operator
# edits the polygon or the feather, never per video frame.
_MASK_CACHE_LONG_SIDE_HARD = 1024
_MASK_CACHE_LONG_SIDE_SOFT = 512


def _box_blur_axis(values: np.ndarray, radius: int, axis: int) -> np.ndarray:
    """One box-blur pass along *axis*, in O(n) thanks to a prefix sum."""
    if radius < 1:
        return values
    pad = [(0, 0), (0, 0)]
    pad[axis] = (radius, radius)
    padded = np.pad(values, pad, mode="edge")
    cumulative = np.cumsum(padded, axis=axis, dtype=np.float32)
    zeros_shape = list(cumulative.shape)
    zeros_shape[axis] = 1
    cumulative = np.concatenate(
        [np.zeros(zeros_shape, dtype=np.float32), cumulative], axis=axis
    )
    window = 2 * radius + 1
    high = [slice(None), slice(None)]
    low = [slice(None), slice(None)]
    high[axis] = slice(window, None)
    low[axis] = slice(0, -window)
    return (cumulative[tuple(high)] - cumulative[tuple(low)]) / float(window)


def _blur_alpha(mask: QImage, feather_px: int) -> QImage:
    """Give *mask* a smooth alpha ramp ~*feather_px* wide.

    Three box passes approximate a Gaussian. The previous implementation
    downsampled by the feather width and upsampled again with bilinear
    filtering: that aliases badly on diagonal edges and produced visible
    stair-steps, which is worse than no feather at all. A real blur has no
    high frequencies left, so the painter can stretch it to 1080p/4K without
    replicating the steps.
    """
    width, height = mask.width(), mask.height()
    words = np.frombuffer(mask.constBits(), dtype=np.uint32, count=width * height)
    # 0xAARRGGBB: reading the word avoids any endianness assumption.
    alpha = ((words >> 24) & 0xFF).reshape(height, width).astype(np.float32)

    # 3 box passes of half-width r behave like a Gaussian with sigma ≈ r + 0.5,
    # and the visible ramp (10-90%) is ~3.3 sigma: r ≈ feather/3.5 makes the
    # blur as wide as the feather the operator asked for.
    radius = max(1, int(round(feather_px / 3.5)))
    for _ in range(3):
        alpha = _box_blur_axis(alpha, radius, 0)
        alpha = _box_blur_axis(alpha, radius, 1)

    levels = np.clip(alpha + 0.5, 0.0, 255.0).astype(np.uint32)
    # White premultiplied pixel: RGB == A, i.e. a white veil that
    # DestinationIn / DestinationOut read as "keep this much of the image".
    soft = (levels << 24) | (levels << 16) | (levels << 8) | levels
    blurred = QImage(
        soft.tobytes(), width, height, width * 4, QImage.Format.Format_ARGB32_Premultiplied
    )
    # copy(): the QImage must own its pixels, not point at the numpy buffer.
    return blurred.copy()


@lru_cache(maxsize=6)
def _soft_mask_cached(
    points_key: tuple[tuple[float, float], ...],
    width: int,
    height: int,
    feather_px: int,
) -> QImage:
    """Build (and cache) a white soft-edged alpha mask. Internal helper."""
    mask = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(Qt.GlobalColor.transparent)
    painter = QPainter(mask)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawPath(
            polygon_path_from_normalized(
                [list(p) for p in points_key], 0.0, 0.0, float(width), float(height)
            )
        )
    finally:
        painter.end()

    return _blur_alpha(mask, feather_px) if feather_px >= 1 else mask


def feathered_mask_image(
    points: list[list[float]],
    width: int,
    height: int,
    feather_px: float = 0.0,
) -> QImage:
    """Return a white alpha mask for *points* with an optionally soft edge.

    The mask is meant to be composited with ``CompositionMode_DestinationIn``
    (or used as an alpha channel) so a masked image fades into transparency
    instead of showing a jagged cut. ``feather_px`` is the ramp width in pixels
    of the target surface; the result is cached because the geometry only
    changes when the operator edits the mask, never per video frame. The
    returned image may be smaller than ``width`` × ``height``: draw it scaled
    into the target rectangle.

    An empty image is returned for unusable input, which callers treat as
    "no mask" (the same contract as :func:`polygon_path_from_normalized`).
    """
    if not points or len(points) < 3:
        return QImage()
    width = int(max(1, width))
    height = int(max(1, height))
    soft_edge = float(feather_px) >= 1.0
    long_side = max(width, height)
    # Ramp width in "hard" (1024 px) space: it decides whether we can afford the
    # cheaper 512 px grid without turning a thin feather into a wide blur.
    feather_hi = float(feather_px) * min(1.0, _MASK_CACHE_LONG_SIDE_HARD / long_side)
    long_side_limit = (
        _MASK_CACHE_LONG_SIDE_SOFT
        if soft_edge and feather_hi >= 8.0
        else _MASK_CACHE_LONG_SIDE_HARD
    )
    scale = min(1.0, long_side_limit / long_side)
    mask_w = max(1, int(round(width * scale)))
    mask_h = max(1, int(round(height * scale)))
    key = tuple((round(float(p[0]), 4), round(float(p[1]), 4)) for p in points)
    # Cap the ramp so a huge value on a small surface cannot eat the shape.
    feather = int(max(0, min(round(float(feather_px) * scale), max(mask_w, mask_h) // 3)))
    return _soft_mask_cached(key, mask_w, mask_h, feather)


