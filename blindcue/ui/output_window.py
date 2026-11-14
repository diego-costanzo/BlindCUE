"""Output window – Native Wayland fullscreen borderless on the external monitor.

Implements a layered compositing surface:

- **Layer 0 (Tappo/Failsafe)**: Always visible, shows the event logo
  or solid black.  Guarantees the audience *never* sees the Linux
  desktop, even if any media player encounters an issue.
- **Layers 1-3**: Stacked above Layer 0.  Driven by native QtMultimedia
  video rendering (QVideoWidget) or static image overlays (QGraphicsPixmapItem).

In single-monitor setups, it opens in a friendly floating windowed mode
so the operator can test both the Director Panel and Output Window without
getting locked out.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QScreen,
    QTransform,
)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QGraphicsBlurEffect,
    QGraphicsItem,
    QGraphicsOpacityEffect,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from models.surface import (
    DEFAULT_SURFACE_ID,
    DEFAULT_SURFACE_NAME,
    MaskType,
    SurfaceDefinition,
    SurfaceMode,
    create_default_surface,
)
from ui.layout_math import MediaFrameGeometry, compute_media_frame_geometry, parse_aspect_ratio
from ui.tappo_pattern import is_default_tappo_path, render_default_tappo_pixmap

logger = logging.getLogger(__name__)

# Resolve the default logo path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_LOGO = _PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"


class SurfaceCalibrationOverlayItem(QGraphicsItem):
    """High-visibility projector calibration overlay for live on-stage alignment.

    Draws:
    - 10% crosshatch calibration grid with center target (+)
    - 50% projector seam guide for dual-projector setups
    - Real-time footprints of all defined surfaces (rectangles & 4-corner perspective quads)
    - Corner reticles (C1..C4) with coordinate tags
    - Centroid surface name badges
    - Top calibration status banner
    """

    def __init__(self, output_window: "OutputWindow") -> None:
        super().__init__()
        self._output = output_window
        self._active_surface_id: Optional[str] = None
        self.setZValue(10000)
        self.setVisible(False)

    def set_active_surface_id(self, surface_id: Optional[str]) -> None:
        self._active_surface_id = surface_id
        self.update()

    def boundingRect(self) -> QRectF:
        w = max(1.0, float(self._output.width()))
        h = max(1.0, float(self._output.height()))
        return QRectF(0.0, 0.0, w, h)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1.0, float(self._output.width()))
        h = max(1.0, float(self._output.height()))

        # 1. Subtle projector alignment crosshatch grid (every 10%)
        grid_pen = QPen(QColor(71, 85, 105, 130), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in range(1, 10):
            gx = w * (i / 10.0)
            gy = h * (i / 10.0)
            painter.drawLine(QPointF(gx, 0), QPointF(gx, h))
            painter.drawLine(QPointF(0, gy), QPointF(w, gy))

        # Center optical crosshair (50%, 50%)
        cx, cy = w * 0.5, h * 0.5
        center_pen = QPen(QColor(255, 255, 255, 200), 2, Qt.PenStyle.SolidLine)
        painter.setPen(center_pen)
        painter.drawLine(QPointF(cx - 30, cy), QPointF(cx + 30, cy))
        painter.drawLine(QPointF(cx, cy - 30), QPointF(cx, cy + 30))
        painter.drawEllipse(QPointF(cx, cy), 16, 16)

        # 2. Dual projector / multi-screen seam indicator (if wide aspect ratio >= 2.0)
        if w / h >= 2.0:
            seam_pen = QPen(QColor(244, 63, 94, 220), 2, Qt.PenStyle.DashDotLine)
            painter.setPen(seam_pen)
            painter.drawLine(QPointF(cx, 0), QPointF(cx, h))

            # Seam banner
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
            seam_badge = QRectF(cx - 100, 46, 200, 24)
            painter.drawRoundedRect(seam_badge, 4, 4)
            painter.setPen(QPen(QColor(244, 63, 94), 1))
            painter.drawRoundedRect(seam_badge, 4, 4)
            painter.setPen(QColor(255, 255, 255))
            font_seam = QFont("sans-serif", 9)
            font_seam.setBold(True)
            painter.setFont(font_seam)
            painter.drawText(seam_badge, Qt.AlignmentFlag.AlignCenter, "GIUNZIONE 50% (DUAL)")

        # 3. Draw all defined virtual surfaces
        surfaces = self._output.get_surfaces()
        corner_names = ["C1 · TL", "C2 · TR", "C3 · BR", "C4 · BL"]

        font_label = QFont("sans-serif", 10)
        font_label.setBold(True)
        font_corner = QFont("sans-serif", 9)
        font_corner.setBold(True)

        for s in surfaces:
            is_active = (s.surface_id == self._active_surface_id)
            base_col = QColor(s.color if s.color else "#00f0ff")
            if is_active:
                col = QColor(0, 240, 255) if base_col.name() != "#00f0ff" else QColor(245, 158, 11)
                stroke_pen = QPen(col, 3, Qt.PenStyle.SolidLine)
                fill_brush = QBrush(QColor(col.red(), col.green(), col.blue(), 45))
            else:
                col = base_col
                stroke_pen = QPen(col, 2, Qt.PenStyle.DashLine)
                fill_brush = QBrush(QColor(col.red(), col.green(), col.blue(), 15))

            if s.mode == SurfaceMode.QUAD:
                # 4-corner perspective quad
                p0 = QPointF(w * s.corners[0][0], h * s.corners[0][1])
                p1 = QPointF(w * s.corners[1][0], h * s.corners[1][1])
                p2 = QPointF(w * s.corners[2][0], h * s.corners[2][1])
                p3 = QPointF(w * s.corners[3][0], h * s.corners[3][1])
                poly = QPolygonF([p0, p1, p2, p3])

                painter.setPen(stroke_pen)
                painter.setBrush(fill_brush)
                painter.drawPolygon(poly)

                # Optical center diagonals
                diag_pen = QPen(QColor(col.red(), col.green(), col.blue(), 160), 1, Qt.PenStyle.DotLine)
                painter.setPen(diag_pen)
                painter.drawLine(p0, p2)
                painter.drawLine(p1, p3)

                corners = [p0, p1, p2, p3]
                scx = (p0.x() + p1.x() + p2.x() + p3.x()) / 4.0
                scy = (p0.y() + p1.y() + p2.y() + p3.y()) / 4.0
                sw_px = int(w * s.w)
                sh_px = int(h * s.h)

            else:
                # Rectangle mode
                rx, ry = w * s.x, h * s.y
                rw, rh = w * s.w, h * s.h
                rect = QRectF(rx, ry, rw, rh)

                painter.setPen(stroke_pen)
                painter.setBrush(fill_brush)
                painter.drawRect(rect)

                # Diagonals
                diag_pen = QPen(QColor(col.red(), col.green(), col.blue(), 160), 1, Qt.PenStyle.DotLine)
                painter.setPen(diag_pen)
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.topRight(), rect.bottomLeft())

                corners = [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()]
                scx, scy = rect.center().x(), rect.center().y()
                sw_px, sh_px = int(rw), int(rh)

            # Draw mask overlay guides if mask is active
            if s.mask_type == MaskType.ELLIPSE.value:
                mask_pen = QPen(QColor("#f59e0b" if not is_active else "#ffffff"), 2, Qt.PenStyle.DashDotLine)
                painter.setPen(mask_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if s.mode == SurfaceMode.QUAD:
                    epath = QPainterPath()
                    epath.addEllipse(QRectF(0, 0, 1, 1))
                    src_p = QPolygonF([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1), QPointF(0, 1)])
                    dst_p = QPolygonF([p0, p1, p2, p3])
                    m_xf = QTransform()
                    if QTransform.quadToQuad(src_p, dst_p, m_xf):
                        painter.drawPath(m_xf.map(epath))
                else:
                    painter.drawEllipse(rect)
            elif s.mask_type == MaskType.HOLE.value:
                mask_pen = QPen(QColor("#f43f5e"), 2, Qt.PenStyle.DashDotLine)
                painter.setPen(mask_pen)
                h_brush = QBrush(QColor(244, 63, 94, 50), Qt.BrushStyle.DiagCrossPattern)
                painter.setBrush(h_brush)
                if s.mode == SurfaceMode.QUAD:
                    hpath = QPainterPath()
                    hpath.addRect(QRectF(s.hole_x, s.hole_y, s.hole_w, s.hole_h))
                    src_p = QPolygonF([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1), QPointF(0, 1)])
                    dst_p = QPolygonF([p0, p1, p2, p3])
                    m_xf = QTransform()
                    if QTransform.quadToQuad(src_p, dst_p, m_xf):
                        painter.drawPath(m_xf.map(hpath))
                else:
                    h_rect = QRectF(rx + rw * s.hole_x, ry + rh * s.hole_y, rw * s.hole_w, rh * s.hole_h)
                    painter.drawRect(h_rect)

            # Draw corner reticles
            painter.setFont(font_corner)
            for idx, cpt in enumerate(corners):
                painter.setPen(QPen(col, 2, Qt.PenStyle.SolidLine))
                painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
                painter.drawEllipse(cpt, 12, 12)
                painter.drawLine(QPointF(cpt.x() - 18, cpt.y()), QPointF(cpt.x() + 18, cpt.y()))
                painter.drawLine(QPointF(cpt.x(), cpt.y() - 18), QPointF(cpt.x(), cpt.y() + 18))

                # Corner label
                c_lbl = corner_names[idx]
                offset_x = 16 if idx in (0, 3) else -70
                offset_y = -16 if idx in (0, 1) else 24
                lbl_rect = QRectF(cpt.x() + offset_x, cpt.y() + offset_y, 60, 20)
                painter.setBrush(QBrush(QColor(15, 23, 42, 200)))
                painter.setPen(QPen(col, 1))
                painter.drawRoundedRect(lbl_rect, 3, 3)
                painter.setPen(col)
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, c_lbl)

            # Center optical target
            painter.setPen(QPen(col, 2, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(scx, scy), 10, 10)
            painter.drawLine(QPointF(scx - 16, scy), QPointF(scx + 16, scy))
            painter.drawLine(QPointF(scx, scy - 16), QPointF(scx, scy + 16))

            # Surface Name badge
            mask_tag = ""
            if s.mask_type == MaskType.ELLIPSE.value:
                mask_tag = " · ⭕ Ellisse"
            elif s.mask_type == MaskType.HOLE.value:
                mask_tag = " · 🔲 Buco"
            elif s.mask_type == MaskType.IMAGE.value:
                mask_tag = " · 🖼 PNG"
            badge_text = f"{s.name}{mask_tag} [{sw_px}×{sh_px} px]"
            painter.setFont(font_label)
            bw = max(180, int(painter.fontMetrics().horizontalAdvance(badge_text) + 24))
            bh = 28
            badge_rect = QRectF(scx - bw / 2, scy - bh / 2, bw, bh)
            painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
            painter.setPen(QPen(col, 2 if is_active else 1))
            painter.drawRoundedRect(badge_rect, 5, 5)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # 4. Top calibration status banner
        banner_w = 480
        banner_h = 32
        banner_rect = QRectF((w - banner_w) / 2, 8, banner_w, banner_h)
        painter.setBrush(QBrush(QColor(15, 23, 42, 240)))
        painter.setPen(QPen(QColor(0, 240, 255), 2))
        painter.drawRoundedRect(banner_rect, 6, 6)
        painter.setPen(QColor(255, 255, 255))
        font_banner = QFont("sans-serif", 10)
        font_banner.setBold(True)
        painter.setFont(font_banner)
        painter.drawText(
            banner_rect,
            Qt.AlignmentFlag.AlignCenter,
            "📐 CALIBRAZIONE SUPERFICI LIVE · Premi F7 per Chiudere",
        )


class OutputWindow(QWidget):
    """Native Wayland window for the live output.

    Parameters
    ----------
    fallback_image : str | None
        Path to the image used for Layer 0. Falls back to the bundled
        BlindCue logo, then to solid black.
    parent : QWidget | None
        Optional Qt parent.
    """

    def __init__(self, fallback_image: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet("background-color: #000000;")

        self._force_close_allowed = False
        self._is_external = False
        self._target_screen: Optional[QScreen] = None

        # Graphics scene & view for Layer 0 & Image Compositing
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._view.setStyleSheet("background: black; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        # ── Layer 0: Tappo / Failsafe ─────────────────────────────────
        self._black_rect: Optional[QGraphicsRectItem] = None
        self._logo_item: Optional[QGraphicsPixmapItem] = None
        self._original_logo_pixmap: Optional[QPixmap] = None
        self._layer0_pattern_cache: Optional[tuple[int, int, float, str, QPixmap]] = None
        self._layer0_path = fallback_image or str(_DEFAULT_LOGO)
        self._panic_black: bool = False
        self._build_layer0()

        # ── Virtual Surfaces & Projection Mapping ────────────────────
        self._surfaces: dict[str, SurfaceDefinition] = {
            DEFAULT_SURFACE_ID: create_default_surface()
        }
        self._layer_surfaces: dict[int, str] = {
            1: DEFAULT_SURFACE_ID,
            2: DEFAULT_SURFACE_ID,
            3: DEFAULT_SURFACE_ID,
        }

        # ── Layers 1-3: Independent Video & Image Compositing ─────────
        self._layer_pixmaps: dict[int, QGraphicsPixmapItem] = {}
        self._video_containers: dict[int, QGraphicsPathItem] = {}
        self._image_containers: dict[int, QGraphicsPathItem] = {}
        self._video_items: dict[int, QGraphicsVideoItem] = {}
        self._secondary_video_items: dict[int, QGraphicsVideoItem] = {}
        self._active_video_deck: dict[int, int] = {1: 0, 2: 0, 3: 0}
        self._deck_swap_timers: dict[int, QTimer] = {}
        self._video_layouts: dict[int, dict] = {}
        self._image_layouts: dict[int, dict] = {}

        for layer in (1, 2, 3):
            # Video container (clips child video items)
            container = QGraphicsPathItem()
            container.setPen(Qt.PenStyle.NoPen)
            container.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            container.setZValue(layer * 10)
            self._scene.addItem(container)

            v_item = QGraphicsVideoItem(container)
            v_item.setZValue(2)
            v_item.nativeSizeChanged.connect(
                lambda _sz, l_idx=layer: self._reapply_video_layout(l_idx)
            )
            container.hide()
            self._video_containers[layer] = container
            self._video_items[layer] = v_item

            # Image container (clips child pixmap items for rectangular & quad mapping)
            img_container = QGraphicsPathItem()
            img_container.setPen(Qt.PenStyle.NoPen)
            img_container.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            img_container.setZValue(layer * 10 + 1)
            self._scene.addItem(img_container)
            img_container.hide()
            self._image_containers[layer] = img_container
            self._layer_pixmaps[layer] = QGraphicsPixmapItem(img_container)

        # Backward-compatibility aliases pointing to Layer 1
        self._video_container = self._video_containers[1]
        self._video_item = self._video_items[1]

        # Live Projector Calibration Overlay (F7)
        self._calibration_item = SurfaceCalibrationOverlayItem(self)
        self._scene.addItem(self._calibration_item)

        # Per-layer fade timers (leak-proof & race-proof)
        self._video_fade_timers: dict[int, QTimer] = {}
        self._layer_fade_timers: dict[int, QTimer] = {}

        logger.info("[OUTPUT] Native Wayland Output Window created")

    # ── Layer 0 ───────────────────────────────────────────────────────

    def _build_layer0(self) -> None:
        """Load the failsafe image into the scene (or projector alignment default pattern)."""
        self._black_rect = self._scene.addRect(
            QRectF(0, 0, 1920, 1080),
            brush=QBrush(QColor(0, 0, 0)),
        )
        self._black_rect.setZValue(-100)

        if is_default_tappo_path(self._layer0_path):
            w, h = max(64, self.width()), max(48, self.height())
            pat = render_default_tappo_pixmap(w, h, self._layer0_path)
            self._original_logo_pixmap = None
            self._logo_item = self._scene.addPixmap(pat)
            self._logo_item.setZValue(-50)
            logger.info("[OUTPUT] Layer 0 calibration pattern loaded (%dx%d)", w, h)
        elif os.path.isfile(self._layer0_path):
            try:
                pixmap = QPixmap(self._layer0_path)
                if not pixmap.isNull():
                    self._original_logo_pixmap = pixmap
                    self._logo_item = self._scene.addPixmap(pixmap)
                    self._logo_item.setZValue(-50)
                    logger.info("[OUTPUT] Layer 0 loaded: %s", self._layer0_path)
                else:
                    logger.warning("[OUTPUT] Layer 0 pixmap is null: %s", self._layer0_path)
            except Exception as exc:
                logger.error("[OUTPUT] Layer 0 load failed: %s", exc)
        else:
            logger.warning("[OUTPUT] Layer 0 image not found: %s – using black", self._layer0_path)

    def _fit_layer0(self) -> None:
        """Scale Layer 0 elements to fill the current window size without quality loss."""
        w, h = max(1, self.width()), max(1, self.height())
        if self._black_rect is not None:
            self._black_rect.setRect(QRectF(0, 0, w, h))

        if self._logo_item is not None and is_default_tappo_path(self._layer0_path):
            dpr = max(1.0, float(self.devicePixelRatioF()))
            cache = self._layer0_pattern_cache
            if cache and cache[:4] == (w, h, dpr, self._layer0_path):
                pat = cache[4]
            else:
                pat = render_default_tappo_pixmap(w, h, self._layer0_path, dpr=dpr)
                self._layer0_pattern_cache = (w, h, dpr, self._layer0_path, pat)
            self._logo_item.setPixmap(pat)
            self._logo_item.setPos(0, 0)
        elif self._logo_item is not None and self._original_logo_pixmap is not None:
            scaled = self._original_logo_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._logo_item.setPixmap(scaled)
            self._logo_item.setPos(
                (w - scaled.width()) / 2,
                (h - scaled.height()) / 2,
            )

        self._scene.setSceneRect(0, 0, w, h)
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)

    def set_layer0_image(self, image_path: Optional[str]) -> bool:
        """Set or change the Layer 0 failsafe image dynamically."""
        self._panic_black = False
        target_path = image_path or str(_DEFAULT_LOGO)
        self._layer0_pattern_cache = None

        if is_default_tappo_path(target_path):
            self._layer0_path = str(_DEFAULT_LOGO)
            self._original_logo_pixmap = None
            pat = render_default_tappo_pixmap(max(64, self.width()), max(48, self.height()), self._layer0_path)
            if self._logo_item is None:
                self._logo_item = self._scene.addPixmap(pat)
                self._logo_item.setZValue(-50)
            else:
                self._logo_item.setPixmap(pat)
            self._fit_layer0()
            logger.info("[OUTPUT] Updated Layer 0 (Tappo) to default projector calibration pattern")
            return True

        if not os.path.isfile(target_path):
            logger.warning("[OUTPUT] Target Layer 0 image not found: %s", target_path)
            return False

        pix = QPixmap(target_path)
        if pix.isNull():
            logger.warning("[OUTPUT] Target Layer 0 pixmap could not be loaded: %s", target_path)
            return False

        self._layer0_path = target_path
        self._original_logo_pixmap = pix

        if self._logo_item is None:
            self._logo_item = self._scene.addPixmap(pix)
            self._logo_item.setZValue(-50)
        else:
            self._logo_item.setPixmap(pix)

        self._fit_layer0()
        logger.info("[OUTPUT] Updated Layer 0 (Tappo) image to: %s", target_path)
        return True

    def get_layer0_path(self) -> str:
        """Return the current Layer 0 image file path."""
        return self._layer0_path

    def reset_layer0_default(self) -> None:
        """Reset Layer 0 to the bundled BlindCue official logo."""
        self.set_layer0_image(str(_DEFAULT_LOGO))

    def _update_tappo_visibility(self) -> None:
        """Ensure Layer 0 (Tappo) is visible ONLY when no media is active and not in Panic Black."""
        has_active_media = bool(self._layer_pixmaps) or any(
            c.isVisible() for c in self._video_containers.values()
        )
        if has_active_media:
            self._panic_black = False
        if self._logo_item is not None:
            self._logo_item.setVisible((not has_active_media) and (not self._panic_black))

    @staticmethod
    def _stop_timer_entry(timer_map: dict[int, QTimer], layer: int) -> None:
        old_timer = timer_map.pop(layer, None)
        if old_timer is not None and old_timer.isActive():
            old_timer.stop()

    # ── Layers 1-3 (Images & Overlays) ────────────────────────────────

    def _build_surface_clip_path(self, surf: SurfaceDefinition, w: float, h: float) -> QPainterPath:
        """Construct clipping QPainterPath for rectangular bounds, cutouts, or ellipses."""
        path = QPainterPath()
        if surf.mask_type == MaskType.ELLIPSE.value:
            if surf.mask_invert:
                path.addRect(0.0, 0.0, w, h)
                sub = QPainterPath()
                sub.addEllipse(0.0, 0.0, w, h)
                path = path.subtracted(sub)
            else:
                path.addEllipse(0.0, 0.0, w, h)
        elif surf.mask_type == MaskType.HOLE.value:
            hx = w * surf.hole_x
            hy = h * surf.hole_y
            hw = max(1.0, w * surf.hole_w)
            hh = max(1.0, h * surf.hole_h)
            hole_path = QPainterPath()
            hole_path.addRect(hx, hy, hw, hh)
            if surf.mask_invert:
                path = hole_path
            else:
                path.addRect(0.0, 0.0, w, h)
                path = path.subtracted(hole_path)
        else:
            path.addRect(0.0, 0.0, w, h)
        return path

    def _apply_mask_effect_if_needed(
        self,
        container: QGraphicsPathItem,
        surf: SurfaceDefinition,
        clip_path: QPainterPath,
        w: float,
        h: float,
    ) -> None:
        """Apply custom PNG opacity mask or edge feathering effect."""
        if surf.mask_type == MaskType.IMAGE.value and surf.mask_image_path:
            img_path = Path(surf.mask_image_path)
            if img_path.is_file():
                mask_img = QImage(str(img_path))
                if not mask_img.isNull():
                    scaled = mask_img.scaled(
                        max(1, int(w)),
                        max(1, int(h)),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    if surf.mask_invert:
                        scaled.invertPixels(QImage.InvertMode.InvertRgba)
                    effect = QGraphicsOpacityEffect(container)
                    effect.setOpacityMask(QBrush(scaled))
                    container.setGraphicsEffect(effect)
                    return

        if surf.mask_feather > 0 and w > 2 and h > 2:
            iw, ih = max(1, int(w)), max(1, int(h))
            scene = QGraphicsScene(0, 0, iw, ih)
            item = QGraphicsPathItem(clip_path)
            item.setBrush(QColor(255, 255, 255, 255))
            item.setPen(Qt.PenStyle.NoPen)
            blur = QGraphicsBlurEffect()
            blur.setBlurRadius(min(50.0, float(surf.mask_feather)))
            item.setGraphicsEffect(blur)
            scene.addItem(item)

            feather_img = QImage(iw, ih, QImage.Format_ARGB32_Premultiplied)
            feather_img.fill(0)
            p = QPainter(feather_img)
            scene.render(p)
            p.end()

            effect = QGraphicsOpacityEffect(container)
            effect.setOpacityMask(QBrush(feather_img))
            container.setGraphicsEffect(effect)
            return

        container.setGraphicsEffect(None)

    def _apply_surface_transform(
        self,
        container: QGraphicsPathItem,
        surf: SurfaceDefinition,
        nat_w: float,
        nat_h: float,
        scale: float = 1.0,
        pos_x: float = 0.0,
        pos_y: float = 0.0,
        crop: Optional[dict] = None,
        aspect_ratio: Optional[str] = None,
    ) -> tuple[MediaFrameGeometry, QTransform]:
        """Compute content geometry within surface and apply QTransform to container."""
        win_w = max(1.0, float(self.width()))
        win_h = max(1.0, float(self.height()))

        if surf.mode == SurfaceMode.QUAD:
            p0 = QPointF(win_w * surf.corners[0][0], win_h * surf.corners[0][1])
            p1 = QPointF(win_w * surf.corners[1][0], win_h * surf.corners[1][1])
            p2 = QPointF(win_w * surf.corners[2][0], win_h * surf.corners[2][1])
            p3 = QPointF(win_w * surf.corners[3][0], win_h * surf.corners[3][1])

            st_w = max(1.0, win_w * surf.w)
            st_h = max(1.0, win_h * surf.h)

            geom = compute_media_frame_geometry(
                0.0, 0.0, st_w, st_h, nat_w, nat_h,
                scale=scale, pos_x=pos_x, pos_y=pos_y, crop=crop, aspect_ratio=aspect_ratio,
            )

            src_poly = QPolygonF([
                QPointF(0.0, 0.0),
                QPointF(geom.vis_w, 0.0),
                QPointF(geom.vis_w, geom.vis_h),
                QPointF(0.0, geom.vis_h),
            ])
            dst_poly = QPolygonF([p0, p1, p2, p3])
            xf = QTransform()
            ok = QTransform.quadToQuad(src_poly, dst_poly, xf)
            if not ok:
                xf = QTransform()

            clip_path = self._build_surface_clip_path(surf, geom.vis_w, geom.vis_h)
            container.setPath(clip_path)
            self._apply_mask_effect_if_needed(container, surf, clip_path, geom.vis_w, geom.vis_h)

            container.setTransform(xf)
            container.setPos(0.0, 0.0)
            return geom, xf

        else:
            st_x = win_w * surf.x
            st_y = win_h * surf.y
            st_w = max(1.0, win_w * surf.w)
            st_h = max(1.0, win_h * surf.h)

            geom = compute_media_frame_geometry(
                0.0, 0.0, st_w, st_h, nat_w, nat_h,
                scale=scale, pos_x=pos_x, pos_y=pos_y, crop=crop, aspect_ratio=aspect_ratio,
            )

            clip_path = self._build_surface_clip_path(surf, geom.vis_w, geom.vis_h)
            container.setPath(clip_path)
            self._apply_mask_effect_if_needed(container, surf, clip_path, geom.vis_w, geom.vis_h)

            container.setTransform(QTransform())
            container.setPos(st_x + geom.vis_x, st_y + geom.vis_y)
            return geom, QTransform()

    def clear_pixmap_layer(self, layer: int) -> None:
        """Remove any static image overlay and pending image fade on *layer*."""
        self._stop_timer_entry(self._layer_fade_timers, layer)
        if layer in self._image_containers:
            self._image_containers[layer].hide()
        if layer in self._layer_pixmaps:
            self._layer_pixmaps[layer].setPixmap(QPixmap())
        self._image_layouts.pop(layer, None)
        self._update_tappo_visibility()

    def _apply_pixmap_to_layer(
        self,
        layer: int,
        pix: QPixmap,
        opacity: float = 1.0,
        crop: Optional[dict] = None,
        scale: float = 1.0,
        pos_x: float = 0.0,
        pos_y: float = 0.0,
        aspect_ratio: Optional[str] = None,
        surface_id: Optional[str] = None,
        *,
        reuse_item: bool = False,
    ) -> None:
        """Crop, scale, and composite *pix* onto *layer* mapped to surface."""
        target_layer = layer if layer in self._image_containers else 1
        surf_id = surface_id or self._layer_surfaces.get(target_layer, DEFAULT_SURFACE_ID)
        self._layer_surfaces[target_layer] = surf_id
        surf = self.get_surface(surf_id)

        self._image_layouts[target_layer] = {
            "pixmap": pix,
            "opacity": opacity,
            "crop": crop,
            "scale": scale,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "aspect_ratio": aspect_ratio,
            "surface_id": surf_id,
        }

        img_container = self._image_containers[target_layer]
        geom, _ = self._apply_surface_transform(
            img_container, surf, pix.width(), pix.height(),
            scale=scale, pos_x=pos_x, pos_y=pos_y, crop=crop, aspect_ratio=aspect_ratio,
        )

        eff_pix = pix
        if crop and (crop.get("w", 1.0) < 0.9999 or crop.get("h", 1.0) < 0.9999
                     or crop.get("x", 0.0) > 0.0001 or crop.get("y", 0.0) > 0.0001):
            cw = max(1, int(round(pix.width() * crop.get("w", 1.0))))
            ch = max(1, int(round(pix.height() * crop.get("h", 1.0))))
            cx = max(0, min(pix.width() - 1, int(round(pix.width() * crop.get("x", 0.0)))))
            cy = max(0, min(pix.height() - 1, int(round(pix.height() * crop.get("y", 0.0)))))
            eff_pix = pix.copy(cx, cy, cw, ch)

        scaled = eff_pix.scaled(
            max(1, int(round(geom.vis_w))),
            max(1, int(round(geom.vis_h))),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._stop_timer_entry(self._layer_fade_timers, target_layer)
        if target_layer in self._video_containers and self._video_containers[target_layer].isVisible():
            self._video_containers[target_layer].hide()

        clamped_op = max(0.0, min(1.0, opacity))
        item = self._layer_pixmaps.get(target_layer)
        if item is None:
            item = QGraphicsPixmapItem(img_container)
            self._layer_pixmaps[target_layer] = item

        item.setPixmap(scaled)
        item.setOpacity(clamped_op)
        item.setPos(0.0, 0.0)
        img_container.show()

        self._update_tappo_visibility()

    def show_image(self, layer: int, file_path: str, opacity: float = 1.0,
                   crop: Optional[dict] = None, scale: float = 1.0,
                   pos_x: float = 0.0, pos_y: float = 0.0,
                   aspect_ratio: Optional[str] = None,
                   surface_id: Optional[str] = None) -> None:
        """Display a static image on layer 1, 2, or 3 with transforms and surface mapping."""
        try:
            if not os.path.isfile(file_path):
                logger.warning("[OUTPUT] Image file not found: %s", file_path)
                return

            pix = QPixmap(file_path)
            if pix.isNull():
                return

            self._apply_pixmap_to_layer(
                layer, pix,
                opacity=opacity, crop=crop, scale=scale,
                pos_x=pos_x, pos_y=pos_y, aspect_ratio=aspect_ratio,
                surface_id=surface_id,
                reuse_item=False,
            )
            logger.info("[OUTPUT] Displayed image on Layer %d: %s (surf=%s, pos=%.2f,%.2f, scale=%.2f, op=%.2f, ar=%s)",
                        layer, file_path, surface_id or "default", pos_x, pos_y, scale, opacity, aspect_ratio or "Native")
        except Exception as exc:
            logger.error("[OUTPUT] show_image() failed on layer %d: %s", layer, exc)

    def show_mirrored_frame(self, layer: int, frame_image: QImage, opacity: float = 1.0,
                            crop: Optional[dict] = None, scale: float = 1.0,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            aspect_ratio: Optional[str] = None,
                            surface_id: Optional[str] = None) -> None:
        """Mirror a decoded Pre-Viz QImage video frame onto *layer* without blank video black-screen."""
        try:
            if frame_image is None or frame_image.isNull():
                return
            pix = QPixmap.fromImage(frame_image)
            if pix.isNull():
                return
            self._apply_pixmap_to_layer(
                layer, pix,
                opacity=opacity, crop=crop, scale=scale,
                pos_x=pos_x, pos_y=pos_y, aspect_ratio=aspect_ratio,
                surface_id=surface_id,
                reuse_item=True,
            )
        except Exception as exc:
            logger.error("[OUTPUT] show_mirrored_frame() failed on layer %d: %s", layer, exc)

    def ensure_live_video_visible(self, layer: int, scale: float = 1.0, crop: Optional[dict] = None,
                                  pos_x: float = 0.0, pos_y: float = 0.0,
                                  opacity: float = 1.0, aspect_ratio: Optional[str] = None,
                                  surface_id: Optional[str] = None) -> None:
        """Restore live video visibility on *layer* without disturbing an active loop deck."""
        target_layer = layer if layer in self._video_containers else 1
        self.clear_pixmap_layer(target_layer)
        self.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, layer=target_layer, aspect_ratio=aspect_ratio,
            surface_id=surface_id,
        )
        self._video_containers[target_layer].show()
        self._update_tappo_visibility()

    def clear_layer(self, layer: int) -> None:
        """Remove any visual content (image or video) from *layer*."""
        self.clear_pixmap_layer(layer)
        self.hide_video_widget(layer=layer)
        self._update_tappo_visibility()

    def clear_all_layers(self) -> None:
        """Clear all active media overlays and video items across Layers 1-3."""
        for layer in (1, 2, 3):
            self.clear_pixmap_layer(layer)
            self.hide_video_widget(layer=layer)
        self._update_tappo_visibility()

    # ── Video Widget & Public API ─────────────────────────────────────

    def get_video_widget(self, layer: int = 1) -> QGraphicsVideoItem:
        """Return the native video item for QMediaPlayer.setVideoOutput() on *layer*."""
        return self._video_items.get(layer, self._video_items[1])

    def get_video_item(self, layer: int = 1) -> QGraphicsVideoItem:
        """Return the native primary QGraphicsVideoItem for *layer*."""
        return self._video_items.get(layer, self._video_items[1])

    def _active_video_item(self, layer: int = 1) -> QGraphicsVideoItem:
        target_layer = layer if layer in self._video_containers else 1
        if self._active_video_deck.get(target_layer, 0) == 1 and target_layer in self._secondary_video_items:
            return self._secondary_video_items[target_layer]
        return self._video_items[target_layer]

    def get_secondary_video_item(self, layer: int = 1) -> QGraphicsVideoItem:
        """Lazily allocate and return secondary pre-cue video deck item inside *layer*."""
        target_layer = layer if layer in self._video_containers else 1
        if target_layer not in self._secondary_video_items:
            container = self._video_containers[target_layer]
            v_sec = QGraphicsVideoItem(container)
            v_sec.setZValue(1)
            v_sec.hide()
            v_sec.nativeSizeChanged.connect(
                lambda _sz, l_idx=target_layer: self._reapply_video_layout(l_idx)
            )
            self._secondary_video_items[target_layer] = v_sec
            if target_layer in self._video_layouts:
                self._reapply_video_layout(target_layer)
        return self._secondary_video_items[target_layer]

    def activate_video_deck(self, layer: int, deck_idx: int) -> None:
        """Bring deck 0 or 1 cleanly to front without black flash during section jumps."""
        target_layer = layer if layer in self._video_containers else 1
        deck = 1 if (deck_idx == 1 and target_layer in self._secondary_video_items) else 0
        self._stop_timer_entry(self._deck_swap_timers, target_layer)

        primary = self._video_items[target_layer]
        secondary = self._secondary_video_items.get(target_layer)
        if secondary is None:
            primary.setZValue(2)
            primary.show()
            self._active_video_deck[target_layer] = 0
            return

        new_item = secondary if deck == 1 else primary
        old_item = primary if deck == 1 else secondary
        op = self._video_layouts.get(target_layer, {}).get("opacity", old_item.opacity())
        new_item.setOpacity(max(0.0, min(1.0, op)))
        new_item.setZValue(2)
        old_item.setZValue(1)
        new_item.show()
        self._active_video_deck[target_layer] = deck

        if old_item.isVisible():
            t = QTimer(self)
            t.setSingleShot(True)
            self._deck_swap_timers[target_layer] = t

            def _hide_old(item_ref=old_item, act_deck=deck, l_idx=target_layer) -> None:
                if self._active_video_deck.get(l_idx) == act_deck:
                    item_ref.hide()

            t.timeout.connect(_hide_old)
            t.start(45)

    def set_layer_opacity(self, layer: int, opacity: float) -> None:
        """Set live visual opacity (0.0-1.0) on active image or video item on *layer*."""
        op = max(0.0, min(1.0, float(opacity)))
        if layer in self._image_containers and self._image_containers[layer].isVisible():
            if layer in self._image_layouts:
                self._image_layouts[layer]["opacity"] = op
            item = self._layer_pixmaps.get(layer)
            if item is not None:
                item.setOpacity(op)
        if layer in self._video_containers:
            if layer in self._video_layouts:
                self._video_layouts[layer]["opacity"] = op
            if self._video_containers[layer].isVisible():
                self._active_video_item(layer).setOpacity(op)

    def show_video_widget(self, scale: float = 1.0, crop: Optional[dict] = None,
                          pos_x: float = 0.0, pos_y: float = 0.0,
                          opacity: float = 1.0, layer: int = 1,
                          aspect_ratio: Optional[str] = None,
                          surface_id: Optional[str] = None) -> None:
        """Show the video item for *layer* with scale, crop, pos, opacity, aspect ratio, and surface."""
        target_layer = layer if layer in self._video_containers else 1
        self._stop_timer_entry(self._video_fade_timers, target_layer)
        self._stop_timer_entry(self._deck_swap_timers, target_layer)
        self._active_video_deck[target_layer] = 0
        self._video_items[target_layer].setZValue(2)
        self._video_items[target_layer].show()
        if target_layer in self._secondary_video_items:
            self._secondary_video_items[target_layer].hide()
            self._secondary_video_items[target_layer].setZValue(1)
        self.clear_pixmap_layer(target_layer)
        self.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, layer=target_layer, aspect_ratio=aspect_ratio,
            surface_id=surface_id,
        )
        self._video_containers[target_layer].show()
        self._update_tappo_visibility()

    def update_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            opacity: float = 1.0, layer: int = 1,
                            aspect_ratio: Optional[str] = None,
                            surface_id: Optional[str] = None) -> None:
        """Update geometry, scaling, position, opacity, crop mask, and aspect ratio for *layer* video mapped to surface."""
        try:
            target_layer = layer if layer in self._video_containers else 1
            surf_id = surface_id or self._layer_surfaces.get(target_layer, DEFAULT_SURFACE_ID)
            self._layer_surfaces[target_layer] = surf_id
            surf = self.get_surface(surf_id)

            self._last_scale = scale
            self._last_crop = crop
            self._video_layouts[target_layer] = {
                "scale": scale,
                "crop": crop,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "opacity": opacity,
                "aspect_ratio": aspect_ratio,
                "surface_id": surf_id,
            }
            win_w = max(1, self.width())
            win_h = max(1, self.height())

            container = self._video_containers[target_layer]
            v_item = self._video_items[target_layer]
            v_sec = self._secondary_video_items.get(target_layer)
            nat = v_item.nativeSize()
            if (not nat.isValid() or nat.width() <= 0) and v_sec is not None:
                nat = v_sec.nativeSize()
            nat_w = nat.width() if (nat.isValid() and nat.width() > 0) else float(win_w)
            nat_h = nat.height() if (nat.isValid() and nat.height() > 0) else float(win_h)

            geom, _ = self._apply_surface_transform(
                container, surf, nat_w, nat_h,
                scale=scale, pos_x=pos_x, pos_y=pos_y, crop=crop, aspect_ratio=aspect_ratio,
            )

            ar_mode = (
                Qt.AspectRatioMode.KeepAspectRatio
                if parse_aspect_ratio(aspect_ratio) is None
                else Qt.AspectRatioMode.IgnoreAspectRatio
            )
            op = max(0.0, min(1.0, opacity))
            items_to_update = [v_item] if v_sec is None else [v_item, v_sec]
            for item in items_to_update:
                item.setAspectRatioMode(ar_mode)
                item.setSize(QSizeF(geom.full_w, geom.full_h))
                item.setPos(-geom.cut_x, -geom.cut_y)
                item.setOpacity(op)
        except Exception as exc:
            logger.error("[OUTPUT] update_video_layout (layer %d) failed: %s", layer, exc)

    def _reapply_video_layout(self, layer: int) -> None:
        container = self._video_containers.get(layer)
        if container is not None and container.isVisible() and layer in self._video_layouts:
            cfg = self._video_layouts[layer]
            self.update_video_layout(
                scale=cfg["scale"],
                crop=cfg["crop"],
                pos_x=cfg["pos_x"],
                pos_y=cfg["pos_y"],
                opacity=cfg["opacity"],
                layer=layer,
                aspect_ratio=cfg.get("aspect_ratio"),
                surface_id=cfg.get("surface_id"),
            )

    def _reapply_image_layout(self, layer: int) -> None:
        container = self._image_containers.get(layer)
        if container is not None and container.isVisible() and layer in self._image_layouts:
            cfg = self._image_layouts[layer]
            pix = cfg.get("pixmap")
            if pix is not None and not pix.isNull():
                self._apply_pixmap_to_layer(
                    layer,
                    pix,
                    opacity=cfg.get("opacity", 1.0),
                    crop=cfg.get("crop"),
                    scale=cfg.get("scale", 1.0),
                    pos_x=cfg.get("pos_x", 0.0),
                    pos_y=cfg.get("pos_y", 0.0),
                    aspect_ratio=cfg.get("aspect_ratio"),
                    surface_id=cfg.get("surface_id"),
                    reuse_item=True,
                )

    # ── Virtual Surfaces & Calibration API ────────────────────────────

    def set_surfaces(self, surfaces: list[SurfaceDefinition]) -> None:
        """Update active virtual surfaces list and dynamically re-map all live layers."""
        new_map: dict[str, SurfaceDefinition] = {}
        for s in surfaces:
            new_map[s.surface_id] = s.clone()
        if DEFAULT_SURFACE_ID not in new_map:
            new_map[DEFAULT_SURFACE_ID] = create_default_surface()
        self._surfaces = new_map

        for layer in (1, 2, 3):
            self._reapply_video_layout(layer)
            self._reapply_image_layout(layer)

        if self._calibration_item.isVisible():
            self._calibration_item.update()

    def get_surfaces(self) -> list[SurfaceDefinition]:
        """Return list of all configured surfaces."""
        return list(self._surfaces.values())

    def get_surface(self, surface_id: Optional[str]) -> SurfaceDefinition:
        """Retrieve surface by ID with fallback to default full screen."""
        if not surface_id:
            surface_id = DEFAULT_SURFACE_ID
        return self._surfaces.get(surface_id) or self._surfaces.get(DEFAULT_SURFACE_ID) or create_default_surface()

    def set_calibration_guides_visible(self, visible: bool, active_surface_id: Optional[str] = None) -> None:
        """Show or hide the high-visibility projector calibration overlay."""
        self._calibration_item.set_active_surface_id(active_surface_id)
        self._calibration_item.setVisible(visible)
        self._calibration_item.update()

    def is_calibration_guides_visible(self) -> bool:
        """Return True if on-projector calibration overlay is active."""
        return self._calibration_item.isVisible()

    def toggle_calibration_guides(self) -> bool:
        """Toggle live calibration overlay on the projector output."""
        new_state = not self._calibration_item.isVisible()
        self.set_calibration_guides_visible(new_state)
        return new_state

    def get_output_resolution(self) -> tuple[int, int]:
        """Return the effective resolution (w, h) in pixels of the projector output."""
        if self.width() > 100 and self.height() > 100:
            return self.width(), self.height()
        scr = self.current_target_screen()
        if scr:
            geo = scr.geometry()
            return geo.width(), geo.height()
        return 1920, 1080

    def span_all_screens(self) -> bool:
        """Span output window seamlessly across all connected external monitors/projectors."""
        from PySide6.QtWidgets import QApplication
        screens = QApplication.screens()
        if len(screens) <= 1:
            logger.info("[OUTPUT] Only 1 screen detected; cannot span multi-monitor.")
            return False

        primary = QApplication.primaryScreen()
        external_screens = [s for s in screens if s != primary]
        target_screens = external_screens if external_screens else screens

        combined_geo = target_screens[0].geometry()
        for s in target_screens[1:]:
            combined_geo = combined_geo.united(s.geometry())

        self._is_external = True
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setGeometry(combined_geo)
        self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        self.show()
        self._fit_layer0()
        logger.info("[OUTPUT] Spanned across %d displays: %s", len(target_screens), combined_geo)
        return True

    def hide_video_widget(self, layer: int = 1) -> None:
        """Hide the video item on *layer* and check if Layer 0 should reappear."""
        target_layer = layer if layer in self._video_containers else 1
        self._stop_timer_entry(self._video_fade_timers, target_layer)
        self._stop_timer_entry(self._deck_swap_timers, target_layer)
        self._video_containers[target_layer].hide()
        self._active_video_deck[target_layer] = 0
        self._video_items[target_layer].setOpacity(1.0)
        if target_layer in self._secondary_video_items:
            self._secondary_video_items[target_layer].hide()
            self._secondary_video_items[target_layer].setOpacity(1.0)
        self._update_tappo_visibility()

    def fade_out_video(self, duration_sec: float = 0.2,
                       callback: Optional[Callable[[], None]] = None,
                       layer: int = 1) -> None:
        """Smoothly fade out video on *layer* over duration_sec and hide."""
        target_layer = layer if layer in self._video_containers else 1
        self._stop_timer_entry(self._video_fade_timers, target_layer)

        container = self._video_containers[target_layer]
        v_item = self._active_video_item(target_layer)
        if not container.isVisible() or duration_sec <= 0:
            self.hide_video_widget(layer=target_layer)
            if callback:
                callback()
            return

        start_op = v_item.opacity()
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        decrement = start_op / steps
        cur = 0

        timer = QTimer(self)
        self._video_fade_timers[target_layer] = timer

        def _step():
            nonlocal cur
            cur += 1
            op = max(0.0, start_op - (cur * decrement))
            self._active_video_item(target_layer).setOpacity(op)
            if cur >= steps or op <= 0.01:
                self._stop_timer_entry(self._video_fade_timers, target_layer)
                self.hide_video_widget(layer=target_layer)
                if callback:
                    callback()

        timer.timeout.connect(_step)
        timer.start(interval)

    def fade_out_layer(self, layer: int, duration_sec: float = 0.2,
                       callback: Optional[Callable[[], None]] = None) -> None:
        """Smoothly fade out an image layer over duration_sec and remove it."""
        self._stop_timer_entry(self._layer_fade_timers, layer)

        item = self._layer_pixmaps.get(layer)
        if item is None or duration_sec <= 0:
            self.clear_pixmap_layer(layer)
            if callback:
                callback()
            return

        start_op = item.opacity()
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        decrement = start_op / steps
        cur = 0

        timer = QTimer(self)
        self._layer_fade_timers[layer] = timer

        def _step():
            nonlocal cur
            cur += 1
            op = max(0.0, start_op - (cur * decrement))
            item.setOpacity(op)
            if cur >= steps:
                self._stop_timer_entry(self._layer_fade_timers, layer)
                self.clear_pixmap_layer(layer)
                if callback:
                    callback()

        timer.timeout.connect(_step)
        timer.start(interval)

    def fade_in_video(self, duration_sec: float = 0.5,
                      target_opacity: float = 1.0, layer: int = 1) -> None:
        """Smoothly fade in video on *layer* from 0.0 to target_opacity."""
        target_layer = layer if layer in self._video_containers else 1
        self._stop_timer_entry(self._video_fade_timers, target_layer)

        v_item = self._active_video_item(target_layer)
        target_op = max(0.0, min(1.0, target_opacity))
        if duration_sec <= 0:
            v_item.setOpacity(target_op)
            return

        v_item.setOpacity(0.0)
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        increment = target_op / steps
        cur = 0

        fade_timer = QTimer(self)
        self._video_fade_timers[target_layer] = fade_timer

        def _step():
            nonlocal cur
            cur += 1
            op = min(target_op, cur * increment)
            self._active_video_item(target_layer).setOpacity(op)
            if cur >= steps or op >= target_op - 0.01:
                self._stop_timer_entry(self._video_fade_timers, target_layer)
                self._active_video_item(target_layer).setOpacity(target_op)

        fade_timer.timeout.connect(_step)
        fade_timer.start(interval)

    def fade_in_layer(self, layer: int, duration_sec: float = 0.5, target_opacity: float = 1.0) -> None:
        """Smoothly fade in image layer from 0.0 to target_opacity over duration_sec."""
        self._stop_timer_entry(self._layer_fade_timers, layer)
        item = self._layer_pixmaps.get(layer)
        target_op = max(0.0, min(1.0, target_opacity))
        if item is None or duration_sec <= 0:
            if item is not None:
                item.setOpacity(target_op)
            return

        item.setOpacity(0.0)
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        increment = target_op / steps
        cur = 0

        fade_timer = QTimer(self)
        self._layer_fade_timers[layer] = fade_timer

        def _step():
            nonlocal cur
            cur += 1
            op = min(target_op, cur * increment)
            item.setOpacity(op)
            if cur >= steps or op >= target_op - 0.01:
                self._stop_timer_entry(self._layer_fade_timers, layer)
                item.setOpacity(target_op)

        fade_timer.timeout.connect(_step)
        fade_timer.start(interval)

    def show_fallback(self, fade_duration_sec: float = 0.2,
                      callback: Optional[Callable[[], None]] = None) -> None:
        """Bring Layer 0 (Tappo) to front with optional micro-fade.
        All live media across Layers 1-3 is removed and the logo is displayed."""
        self._panic_black = False
        visible_videos = [l for l, c in self._video_containers.items() if c.isVisible()]
        has_media = bool(visible_videos) or bool(self._layer_pixmaps)
        if not has_media or fade_duration_sec <= 0:
            self.clear_all_layers()
            if self._logo_item is not None:
                self._logo_item.setVisible(True)
            logger.info("[OUTPUT] Fallback (Layer 0 Tappo) restored immediately")
            if callback:
                callback()
            return

        # Faded transition to fallback across all active video & image layers
        def _finish():
            self.clear_all_layers()
            if self._logo_item is not None:
                self._logo_item.setVisible(True)
            logger.info("[OUTPUT] Fallback (Layer 0 Tappo) restored after %.2fs fade", fade_duration_sec)
            if callback:
                callback()

        for l in visible_videos:
            self.fade_out_video(duration_sec=fade_duration_sec, layer=l)
        for l in list(self._layer_pixmaps.keys()):
            self.fade_out_layer(l, duration_sec=fade_duration_sec)
        QTimer.singleShot(int(fade_duration_sec * 1000) + 15, _finish)

    def panic_blackout(self) -> None:
        """0ms hard stop across all visual layers: pure Black if L0 is default grid, else Custom Tappo."""
        for layer in (1, 2, 3):
            self._stop_timer_entry(self._video_fade_timers, layer)
            self._stop_timer_entry(self._layer_fade_timers, layer)
            self._stop_timer_entry(self._deck_swap_timers, layer)
        self.clear_all_layers()
        self._panic_black = is_default_tappo_path(self._layer0_path)
        self._update_tappo_visibility()
        logger.warning(
            "[OUTPUT] PANIC hard blackout executed -> %s",
            "PURE BLACK" if self._panic_black else "Custom Tappo",
        )

    def _bind_to_screen(self, screen: Optional[QScreen]) -> None:
        """Bind both the QWidget and its native QWindow handle to *screen* (Wayland & X11)."""
        if screen is None:
            return
        self.setScreen(screen)
        self.create()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)

    def configure_screen(self, screen: QScreen, is_external: bool = True) -> None:
        """Attach to *screen*. If is_external=True (multi-monitor), goes fullscreen borderless.
        If is_external=False (single monitor test), opens as a clean preview window on screen."""
        self._is_external = is_external
        self._target_screen = screen

        if is_external:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Window
            )
            self._bind_to_screen(screen)
            self.setGeometry(screen.geometry())
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self.showFullScreen()
            logger.info("[OUTPUT] Attached to external screen '%s' (Fullscreen borderless)", screen.name())
        else:
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowCloseButtonHint
                | Qt.WindowType.WindowMinMaxButtonsHint
            )
            self._bind_to_screen(screen)
            self.setWindowTitle("BlindCue – Live Output [Monitor Simulato]")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            geo = screen.availableGeometry()
            w = min(800, int(geo.width() * 0.45))
            h = int(w * 9 / 16)
            self.setGeometry(geo.x() + geo.width() - w - 30, geo.y() + geo.height() - h - 60, w, h)
            self.showNormal()
            logger.info("[OUTPUT] Single monitor preview window (%dx%d)", w, h)

        self._fit_layer0()
        self.hide_video_widget()

    def attach_to_screen(self, screen: QScreen, is_external: bool = True) -> None:
        self.configure_screen(screen, is_external=is_external)

    def current_target_screen(self) -> Optional[QScreen]:
        """Return currently attached QScreen."""
        return self._target_screen

    def set_target_screen(self, screen: QScreen) -> None:
        """Switch output window to *screen* dynamically at runtime."""
        if screen is None or screen == self._target_screen:
            return
        from PySide6.QtWidgets import QApplication
        primary = QApplication.primaryScreen()
        is_external = (screen != primary)
        logger.info("[OUTPUT] Re-binding output to screen '%s' (is_external=%s)", screen.name(), is_external)
        self.configure_screen(screen, is_external=is_external)

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode on the current screen."""
        if self.isFullScreen():
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowCloseButtonHint
                | Qt.WindowType.WindowMinMaxButtonsHint
            )
            self._bind_to_screen(self._target_screen)
            self.setWindowTitle("BlindCue – Live Output [Monitor Simulato]")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.showNormal()
        else:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Window
            )
            self._bind_to_screen(self._target_screen)
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self.showFullScreen()
        self._fit_layer0()

    def force_close(self) -> None:
        self._force_close_allowed = True
        for t in self._video_fade_timers.values():
            t.stop()
        self._video_fade_timers.clear()
        for t in self._layer_fade_timers.values():
            t.stop()
        self._layer_fade_timers.clear()
        self.close()

    # ── Overrides ─────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_layer0()
        for layer in (1, 2, 3):
            self._reapply_video_layout(layer)
            self._reapply_image_layout(layer)
        if self._calibration_item.isVisible():
            self._calibration_item.update()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._force_close_allowed or not self._is_external:
            event.accept()
        else:
            logger.warning("[OUTPUT] Close attempt blocked during show (use force_close)")
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_F7:
            self.toggle_calibration_guides()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if not self._is_external:
                event.accept()
                return
            event.ignore()
            return
        super().keyPressEvent(event)
