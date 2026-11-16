"""Vector projector alignment pattern and BlindCue logo renderer for Layer 0 (Tappo)."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from ui.theme import CLR_LIVE, CLR_PREVIZ, DEFAULT_LOGO_PATH


def is_default_tappo_path(file_path: str | Path | None) -> bool:
    """Return True when *file_path* refers to the built-in BlindCue Layer 0 Tappo."""
    if not file_path:
        return True
    try:
        return Path(file_path).resolve() == Path(DEFAULT_LOGO_PATH).resolve()
    except Exception:
        return str(file_path) == str(DEFAULT_LOGO_PATH)


def render_default_tappo_pixmap(
    width: int,
    height: int,
    logo_path: str | Path = DEFAULT_LOGO_PATH,
    *,
    dpr: float = 1.0,
) -> QPixmap:
    """Render crisp projector alignment guides + BlindCue logo sized to exact pixel dimensions."""
    lw = max(64, int(width))
    lh = max(48, int(height))
    scale = max(1.0, float(dpr))
    pw = max(64, int(round(lw * scale)))
    ph = max(48, int(round(lh * scale)))

    pix = QPixmap(pw, ph)
    pix.setDevicePixelRatio(scale)
    pix.fill(QColor("#090c10"))

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    w = float(lw)
    h = float(lh)
    cx = w * 0.5
    cy = h * 0.5
    min_dim = min(w, h)

    # 1. Subtle projector level & squareness grid (low light spill on stage)
    cols, rows = 16, 9
    p.setPen(QPen(QColor("#141c26"), 1.0))
    for i in range(1, cols):
        gx = (w * i) / cols
        p.drawLine(QPointF(gx, 0.0), QPointF(gx, h))
    for j in range(1, rows):
        gy = (h * j) / rows
        p.drawLine(QPointF(0.0, gy), QPointF(w, gy))

    # Faint corner-to-corner diagonals for rapid trapezoidal keystone check
    p.setPen(QPen(QColor(30, 41, 59, 130), 1.0))
    p.drawLine(QPointF(0.0, 0.0), QPointF(w, h))
    p.drawLine(QPointF(w, 0.0), QPointF(0.0, h))

    # 2. Inner 90% Action-Safe dashed guide rectangle + 5% tick marks
    inset_x = w * 0.05
    inset_y = h * 0.05
    safe_rect = QRectF(inset_x, inset_y, w - 2.0 * inset_x, h - 2.0 * inset_y)
    safe_pen = QPen(QColor("#334155"), 1.0, Qt.PenStyle.DashLine)
    p.setPen(safe_pen)
    p.drawRect(safe_rect)

    # Perimeter 10% calibration edge ticks along all 4 outer sides
    tick_len = max(5.0, min(14.0, min_dim * 0.018))
    p.setPen(QPen(QColor("#38bdf8"), 1.2))
    for k in range(1, 10):
        tx = (w * k) / 10.0
        ty = (h * k) / 10.0
        p.drawLine(QPointF(tx, 0.0), QPointF(tx, tick_len))
        p.drawLine(QPointF(tx, h - tick_len), QPointF(tx, h))
        p.drawLine(QPointF(0.0, ty), QPointF(tick_len, ty))
        p.drawLine(QPointF(w - tick_len, ty), QPointF(w, ty))

    # 3. Exact outer perimeter 0px frame (shows exact projector image borders & clipping)
    p.setPen(QPen(QColor("#38bdf8"), 2.0))
    p.drawRect(QRectF(1.0, 1.0, w - 2.0, h - 2.0))

    # 4. Corner L-Brackets + corner vertices arrows (Amber #f59e0b / Emerald #00e676)
    arm = max(16.0, min(72.0, min_dim * 0.09))
    tri = max(6.0, min(18.0, min_dim * 0.022))

    corners = (
        (0.0, 0.0, 1.0, 1.0, CLR_PREVIZ),
        (w, 0.0, -1.0, 1.0, CLR_LIVE),
        (0.0, h, 1.0, -1.0, CLR_LIVE),
        (w, h, -1.0, -1.0, CLR_PREVIZ),
    )
    for ox, oy, sx, sy, clr_hex in corners:
        c = QColor(clr_hex)
        p.setPen(QPen(c, max(2.0, min_dim * 0.004)))
        # Crisp corner L edges hugged against exact border
        ex = ox + sx * arm
        ey = oy + sy * arm
        bx = ox + sx * 1.5
        by = oy + sy * 1.5
        p.drawLine(QPointF(bx, by), QPointF(ex, by))
        p.drawLine(QPointF(bx, by), QPointF(bx, ey))
        # Filled corner pointer triangle right at vertex
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawPolygon(QPolygonF([
            QPointF(ox, oy),
            QPointF(ox + sx * tri, oy),
            QPointF(ox, oy + sy * tri),
        ]))

    # 5. Center Geometry Circle & Crosshair (oval = aspect distortion or keystone skew)
    r_outer = min_dim * 0.36
    r_inner = min_dim * 0.255

    # Horizontal & vertical full center axes
    p.setPen(QPen(QColor("#1e3a4c"), 1.0))
    p.drawLine(QPointF(cx, 0.0), QPointF(cx, h))
    p.drawLine(QPointF(0.0, cy), QPointF(w, cy))

    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(45, 212, 191, 140), max(1.2, min_dim * 0.0022)))
    p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
    p.setPen(QPen(QColor(100, 116, 139, 130), 1.0, Qt.PenStyle.DashLine))
    p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)

    # Cardinal crosshair ticks on the outer calibration ring
    p.setPen(QPen(QColor("#2dd4bf"), max(1.4, min_dim * 0.0025)))
    c_tick = max(6.0, min_dim * 0.02)
    p.drawLine(QPointF(cx, cy - r_outer - c_tick), QPointF(cx, cy - r_outer + c_tick))
    p.drawLine(QPointF(cx, cy + r_outer - c_tick), QPointF(cx, cy + r_outer + c_tick))
    p.drawLine(QPointF(cx - r_outer - c_tick, cy), QPointF(cx - r_outer + c_tick, cy))
    p.drawLine(QPointF(cx + r_outer - c_tick, cy), QPointF(cx + r_outer + c_tick, cy))

    # 6. Seamless BlindCue Base Logo centered inside inner calibration ring
    logo_pix = QPixmap(str(logo_path))
    if not logo_pix.isNull():
        medallion_d = r_inner * 1.62
        mr = QRectF(cx - medallion_d * 0.5, cy - medallion_d * 0.5, medallion_d, medallion_d)

        # Dark backdrop disc matched to logo charcoal so circular emblem sits cleanly inside
        grad = QRadialGradient(QPointF(cx, cy), medallion_d * 0.5)
        grad.setColorAt(0.0, QColor("#1f2328"))
        grad.setColorAt(0.88, QColor("#1c2024"))
        grad.setColorAt(1.0, QColor("#12161c"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(mr)

        p.save()
        clip = QPainterPath()
        clip.addEllipse(mr.adjusted(3.0, 3.0, -3.0, -3.0))
        p.setClipPath(clip)
        # Keep square image <= medallion_d / sqrt(2) (~0.68) so corners never touch circle rim
        target_box = int(max(16, round(medallion_d * 0.68)))
        scaled_logo = logo_pix.scaled(
            int(round(target_box * scale)),
            int(round(target_box * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled_logo.setDevicePixelRatio(scale)
        log_w = scaled_logo.width() / scale
        log_h = scaled_logo.height() / scale
        p.drawPixmap(QPointF(cx - log_w * 0.5, cy - log_h * 0.5), scaled_logo)
        p.restore()

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 230, 118, 95), 1.4))
        p.drawEllipse(mr.adjusted(1.5, 1.5, -1.5, -1.5))

    # 7. Edge Orientation Labels (verify projector upright / mirror / overshoot)
    if min_dim >= 150.0:
        font_sz = max(7, min(14, int(round(min_dim * 0.019))))
        tag_font = QFont("monospace", font_sz, QFont.Weight.Bold)
        p.setFont(tag_font)
        fm = QFontMetrics(tag_font)
        edge_pad = max(6.0, min_dim * 0.015)

        def _draw_tag(rect: QRectF, text: str, fg: str = "#cbd5e1") -> None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(9, 12, 16, 210))
            p.drawRoundedRect(rect, 3.0, 3.0)
            p.setPen(QColor(fg))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        tag_h = max(16.0, font_sz * 1.9)
        top_txt = "▲ ALTO / TOP ▲"
        top_w = float(fm.horizontalAdvance(top_txt) + 14)
        bot_txt = "▼ BASSO ▼"
        bot_w = float(fm.horizontalAdvance(bot_txt) + 14)
        _draw_tag(QRectF(cx - top_w * 0.5, edge_pad, top_w, tag_h), top_txt, "#38bdf8")
        _draw_tag(QRectF(cx - bot_w * 0.5, h - edge_pad - tag_h, bot_w, tag_h), bot_txt, "#94a3b8")

        sx_txt, dx_txt = "◀ SX", "DX ▶"
        sx_w = float(fm.horizontalAdvance(sx_txt) + 10)
        dx_w = float(fm.horizontalAdvance(dx_txt) + 10)
        _draw_tag(QRectF(edge_pad, cy - tag_h * 0.5, sx_w, tag_h), sx_txt, "#94a3b8")
        _draw_tag(QRectF(w - edge_pad - dx_w, cy - tag_h * 0.5, dx_w, tag_h), dx_txt, "#94a3b8")

        if w >= 280.0:
            g = math.gcd(lw, lh)
            ar_txt = f"{lw // g}:{lh // g}" if g > 0 and (lw // g) <= 32 else f"{w / h:.2f}:1"
            res_txt = f"L0 TAPPO • {lw}×{lh} ({ar_txt})"
            res_w = float(fm.horizontalAdvance(res_txt) + 14)
            info_rect = QRectF(
                safe_rect.right() - res_w - 6.0,
                safe_rect.bottom() - tag_h - 6.0,
                res_w,
                tag_h,
            )
            _draw_tag(info_rect, res_txt, "#94a3b8")

    p.end()
    return pix

