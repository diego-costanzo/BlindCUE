"""Render text cues (on-screen captions) to transparent 1920×1080 PNG images.

A text cue is an ordinary IMAGE cue whose picture is generated from its
``Cue.text_spec``; layers, fades, crossfade, position and surfaces therefore
work exactly as for photos. Images are cached by content hash, so the same
settings always map to the same file and can be re-created on any computer.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QStandardPaths, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

WIDTH, HEIGHT = 1920, 1080

DEFAULT_SPEC: dict[str, Any] = {
    "text": "",
    "size": 90,            # font size in pixels at 1920×1080
    "color": "#ffffff",
    "bold": True,
    "position": "bottom",  # "top" | "center" | "bottom"
    "box": True,           # semi-transparent dark band behind the text
    "shadow": True,
    "font": "Segoe UI",
}

_VALIGN = {
    "top": Qt.AlignmentFlag.AlignTop,
    "center": Qt.AlignmentFlag.AlignVCenter,
    "bottom": Qt.AlignmentFlag.AlignBottom,
}


def normalize_spec(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete, sanitised copy of *spec*."""
    out = dict(DEFAULT_SPEC)
    out.update({k: v for k, v in (spec or {}).items() if k in DEFAULT_SPEC})
    out["text"] = str(out["text"])
    out["size"] = max(12, min(400, int(out["size"])))
    out["color"] = out["color"] if QColor(str(out["color"])).isValid() else "#ffffff"
    out["position"] = out["position"] if out["position"] in _VALIGN else "bottom"
    out["bold"] = bool(out["bold"])
    out["box"] = bool(out["box"])
    out["shadow"] = bool(out["shadow"])
    out["font"] = str(out["font"] or "Segoe UI")
    return out


def render_text_image(spec: dict[str, Any] | None) -> QImage:
    """Draw the caption described by *spec* on a transparent 1920×1080 image."""
    s = normalize_spec(spec)
    img = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    if not s["text"].strip():
        return img

    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont(s["font"])
        font.setPixelSize(s["size"])
        font.setBold(s["bold"])
        p.setFont(font)

        margin = 90
        area = QRect(margin, margin, WIDTH - 2 * margin, HEIGHT - 2 * margin)
        flags = int(Qt.AlignmentFlag.AlignHCenter | _VALIGN[s["position"]] | Qt.TextFlag.TextWordWrap)
        text = s["text"]
        bounds = p.boundingRect(area, flags, text)

        if s["box"]:
            pad_x, pad_y = int(s["size"] * 0.45), int(s["size"] * 0.25)
            band = bounds.adjusted(-pad_x, -pad_y, pad_x, pad_y)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            radius = max(8.0, s["size"] * 0.18)
            p.drawRoundedRect(band, radius, radius)

        if s["shadow"]:
            off = max(2, s["size"] // 22)
            p.setPen(QColor(0, 0, 0, 210))
            p.drawText(area.translated(off, off), flags, text)

        p.setPen(QColor(s["color"]))
        p.drawText(area, flags, text)
    finally:
        p.end()
    return img


def _cache_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    root = Path(base) if base else Path(tempfile.gettempdir()) / "BlindCue"
    folder = root / "text_cues"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def render_text_png(spec: dict[str, Any] | None) -> str:
    """Render *spec* to a cached PNG and return its path (re-used if it exists)."""
    s = normalize_spec(spec)
    digest = hashlib.sha1(json.dumps(s, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    path = _cache_dir() / f"caption_{digest}.png"
    if not path.is_file():
        if not render_text_image(s).save(str(path), "PNG"):
            raise OSError(f"Cannot write text cue image: {path}")
    return str(path)


def text_cue_name(spec: dict[str, Any] | None) -> str:
    """Short cue-list name for a text cue: its first line, shortened."""
    first = normalize_spec(spec)["text"].strip().splitlines()
    line = first[0].strip() if first else ""
    if len(line) > 40:
        line = line[:39].rstrip() + "…"
    return f"📝 {line}" if line else "📝"
