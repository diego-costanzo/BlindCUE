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
import time
from collections import OrderedDict
from pathlib import Path
from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QCoreApplication, QPointF, QRectF, QSizeF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
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

from engine.envelope import ramp_value
from models.surface import (
    DEFAULT_SURFACE_ID,
    MaskType,
    SurfaceDefinition,
    SurfaceMode,
    create_default_surface,
)
from ui.layout_math import (
    MediaFrameGeometry,
    compute_media_frame_geometry,
    feathered_mask_image,
    parse_aspect_ratio,
    polygon_path_from_normalized,
)
from ui.tappo_pattern import is_default_tappo_path, render_default_tappo_pixmap
from ui.theme import DEFAULT_LOGO_PATH

logger = logging.getLogger(__name__)

# Logo di fallback (Layer 0): asset di runtime dentro il pacchetto, così esiste
# anche dopo l'installazione in una cartella diversa dal repository.
_DEFAULT_LOGO = DEFAULT_LOGO_PATH


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

    def __init__(self, output_window: OutputWindow) -> None:
        """Overlay drawing the calibration guides of the edited surface."""
        super().__init__()
        self._output = output_window
        self._active_surface_id: str | None = None
        self.setZValue(10000)
        self.setVisible(False)

    def set_active_surface_id(self, surface_id: str | None) -> None:
        """Choose which surface the calibration overlay highlights."""
        self._active_surface_id = surface_id
        self.update()

    def boundingRect(self) -> QRectF:
        """Area covered by the calibration overlay (the whole output scene)."""
        cw, ch = self._output._canvas_size()
        w, h = float(cw), float(ch)
        return QRectF(0.0, 0.0, w, h)

    def _draw_guide_badge(self, painter: QPainter, cx: float, cy: float, text: str, col: QColor) -> None:
        font_b = QFont("sans-serif", 9, QFont.Weight.Bold)
        painter.setFont(font_b)
        bw = painter.fontMetrics().horizontalAdvance(text) + 18
        bh = 22
        badge_rect = QRectF(cx - bw / 2, cy - bh / 2, bw, bh)
        painter.setBrush(QBrush(QColor(15, 23, 42, 240)))
        painter.setPen(QPen(col, 1.5))
        painter.drawRoundedRect(badge_rect, 4, 4)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Draw the surface outlines and corner calibration guides."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cw, ch = self._output._canvas_size()
        w, h = float(cw), float(ch)

        is_full_calib = self._output.is_calibration_guides_visible()
        surfaces = self._output.get_surfaces()
        has_mask_guide = any(s.mask_show_guide for s in surfaces)

        if not is_full_calib and not has_mask_guide:
            return

        if is_full_calib:
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

        # 3. Draw surfaces and masks
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
                p0 = QPointF(w * s.corners[0][0], h * s.corners[0][1])
                p1 = QPointF(w * s.corners[1][0], h * s.corners[1][1])
                p2 = QPointF(w * s.corners[2][0], h * s.corners[2][1])
                p3 = QPointF(w * s.corners[3][0], h * s.corners[3][1])
                poly = QPolygonF([p0, p1, p2, p3])

                if is_full_calib:
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
                rx, ry = w * s.x, h * s.y
                rw, rh = w * s.w, h * s.h
                rect = QRectF(rx, ry, rw, rh)

                if is_full_calib:
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
                is_hole = s.mask_invert
                col_mask = QColor("#f43f5e" if is_hole else "#00f0ff")
                mask_pen = QPen(col_mask, 3, Qt.PenStyle.SolidLine)
                painter.setPen(mask_pen)
                painter.setBrush(QBrush(QColor(col_mask.red(), col_mask.green(), col_mask.blue(), 40 if is_hole else 20), Qt.BrushStyle.DiagCrossPattern if is_hole else Qt.BrushStyle.SolidPattern))

                epath = QPainterPath()
                epath.addEllipse(QRectF(0, 0, 1, 1))
                if s.mode == SurfaceMode.QUAD:
                    src_p = QPolygonF([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1), QPointF(0, 1)])
                    dst_p = QPolygonF([p0, p1, p2, p3])
                    m_xf = QTransform()
                    if QTransform.quadToQuad(src_p, dst_p, m_xf):
                        painter.drawPath(m_xf.map(epath))
                else:
                    painter.drawEllipse(rect)

                dim_txt = f"{'⭕ BUCO ELLITTICO' if is_hole else '⭕ SAGOMA ELLISSE'}: {int(sw_px)}×{int(sh_px)} px"
                if s.mask_feather > 0:
                    dim_txt += f" (Feather {s.mask_feather}px)"
                self._draw_guide_badge(painter, scx, scy - 30, dim_txt, col_mask)

            elif s.mask_type == MaskType.HOLE.value:
                is_hole = not s.mask_invert
                col_mask = QColor("#f43f5e" if is_hole else "#00f0ff")
                mask_pen = QPen(col_mask, 3, Qt.PenStyle.SolidLine)
                painter.setPen(mask_pen)
                painter.setBrush(QBrush(QColor(col_mask.red(), col_mask.green(), col_mask.blue(), 50 if is_hole else 20), Qt.BrushStyle.DiagCrossPattern if is_hole else Qt.BrushStyle.SolidPattern))

                hpath = QPainterPath()
                hpath.addRect(QRectF(s.hole_x, s.hole_y, s.hole_w, s.hole_h))
                if s.mode == SurfaceMode.QUAD:
                    src_p = QPolygonF([QPointF(0, 0), QPointF(1, 0), QPointF(1, 1), QPointF(0, 1)])
                    dst_p = QPolygonF([p0, p1, p2, p3])
                    m_xf = QTransform()
                    if QTransform.quadToQuad(src_p, dst_p, m_xf):
                        painter.drawPath(m_xf.map(hpath))
                    hc_x = (p0.x() + p1.x() + p2.x() + p3.x()) / 4.0
                    hc_y = (p0.y() + p1.y() + p2.y() + p3.y()) / 4.0
                else:
                    h_rect = QRectF(rx + rw * s.hole_x, ry + rh * s.hole_y, rw * s.hole_w, rh * s.hole_h)
                    painter.drawRect(h_rect)
                    hc_x = h_rect.center().x()
                    hc_y = h_rect.center().y()

                dim_txt = f"{'🔲 BUCO / FORATURA' if is_hole else '🔲 SAGOMA INTERNA'}: {int(sw_px * s.hole_w)}×{int(sh_px * s.hole_h)} px"
                if s.mask_feather > 0:
                    dim_txt += f" (Feather {s.mask_feather}px)"
                self._draw_guide_badge(painter, hc_x, hc_y - 20, dim_txt, col_mask)

            if is_full_calib:
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

        if is_full_calib:
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

    def __init__(self, fallback_image: str | None = None,
                 parent: QWidget | None = None) -> None:
        """Create a frameless black output window ready to be attached to a screen."""
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet("background-color: #000000;")

        self._force_close_allowed = False
        self._is_external = False
        self._target_screen: QScreen | None = None
        self._span_screens: list[QScreen] = []

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
        self._black_rect: QGraphicsRectItem | None = None
        self._logo_item: QGraphicsPixmapItem | None = None
        self._original_logo_pixmap: QPixmap | None = None
        self._layer0_pattern_cache: tuple[int, int, float, str, QPixmap] | None = None
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
        # Managed Layer 0 fallback transition timer (cancelled if new media starts)
        self._fallback_timer: QTimer | None = None
        self._fallback_gen: int = 0
        # Bounded LRU caches for expensive surface masks and decoded static images
        self._surface_mask_cache: OrderedDict[tuple, QImage] = OrderedDict()
        self._image_pixmap_cache: OrderedDict[tuple, QPixmap] = OrderedDict()

        # Crossfade: frozen snapshot of a layer dissolving over new content
        self._xfade_ghosts: dict[int, QGraphicsPixmapItem] = {}
        self._xfade_timers: dict[int, QTimer] = {}
        # Layer opacity set by an action cue: the containers of a layer dim
        # whatever plays on it, on top of the cue's own opacity/fades.
        self._master_fade_timers: dict[int, QTimer] = {}

        # Crossfade: frozen snapshot of a layer dissolving over new content
        self._xfade_ghosts: dict[int, QGraphicsPixmapItem] = {}
        self._xfade_timers: dict[int, QTimer] = {}

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
            cw, ch = self._canvas_size()
            w, h = max(64, cw), max(48, ch)
            pat = render_default_tappo_pixmap(w, h, self._layer0_path)
            self._original_logo_pixmap = None
            self._logo_item = self._scene.addPixmap(pat)
            self._logo_item.setZValue(-50)
            logger.info("[OUTPUT] Layer 0 calibration pattern loaded (%dx%d)", w, h)
        elif Path(self._layer0_path).is_file():
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

    def _canvas_size(self) -> tuple[int, int]:
        """Size (px) of the picture area every layer is laid out in.

        A projector uses the whole window. The single-monitor preview window
        keeps a 16:9 picture letterboxed in whatever shape the window gets:
        Windows Snap can squeeze it into a tall strip, and stretching the
        layout to that shape showed something the projector never shows.
        """
        w, h = max(1, self.width()), max(1, self.height())
        if self._is_external:
            return w, h
        if w * 9 > h * 16:
            return max(1, round(h * 16 / 9)), h
        return w, max(1, round(w * 9 / 16))

    def _fit_layer0(self) -> None:
        """Scale Layer 0 elements to fill the picture area without quality loss."""
        w, h = self._canvas_size()
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
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_layer0_image(self, image_path: str | None) -> bool:
        """Set or change the Layer 0 failsafe image dynamically."""
        self._panic_black = False
        target_path = image_path or str(_DEFAULT_LOGO)
        self._layer0_pattern_cache = None

        if is_default_tappo_path(target_path):
            self._layer0_path = str(_DEFAULT_LOGO)
            self._original_logo_pixmap = None
            cw, ch = self._canvas_size()
            pat = render_default_tappo_pixmap(max(64, cw), max(48, ch), self._layer0_path)
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

    def _has_active_media(self) -> bool:
        """Return True only if Layers 1-3 really show a video or a non-empty image.

        The per-layer dicts are created once at init, so their truthiness says
        nothing about content: a cleared layer keeps its (empty) pixmap item.
        """
        if any(c.isVisible() for c in self._video_containers.values()):
            return True
        for layer, item in self._layer_pixmaps.items():
            if item.pixmap().isNull():
                continue
            container = self._image_containers.get(layer)
            if container is not None and container.isVisible():
                return True
        return False

    def _update_tappo_visibility(self) -> None:
        """Ensure Layer 0 (Tappo) is visible ONLY when no media is active and not in Panic Black."""
        has_active_media = self._has_active_media()
        if has_active_media:
            self._panic_black = False
        if self._logo_item is not None:
            self._logo_item.setVisible((not has_active_media) and (not self._panic_black))

    @staticmethod
    def _stop_timer_entry(timer_map: dict[int, QTimer], layer: int) -> None:
        old_timer = timer_map.pop(layer, None)
        if old_timer is not None:
            if old_timer.isActive():
                old_timer.stop()
            old_timer.deleteLater()

    def _cancel_fallback_timer(self) -> None:
        """Cancel any pending Layer 0 fallback transition so new media is never wiped."""
        self._fallback_gen += 1
        timer = self._fallback_timer
        self._fallback_timer = None
        if timer is not None:
            if timer.isActive():
                timer.stop()
            timer.deleteLater()

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
        """Apply custom PNG opacity mask or edge feathering effect (with bounded LRU cache)."""
        iw, ih = max(1, int(w)), max(1, int(h))

        if surf.mask_type == MaskType.IMAGE.value and surf.mask_image_path:
            img_path = Path(surf.mask_image_path)
            if img_path.is_file():
                try:
                    mtime_ns = img_path.stat().st_mtime_ns
                except OSError:
                    mtime_ns = 0
                cache_key = ("image", str(img_path), mtime_ns, bool(surf.mask_invert), iw, ih)
                scaled = self._surface_mask_cache.get(cache_key)
                if scaled is not None:
                    self._surface_mask_cache.move_to_end(cache_key)
                else:
                    mask_img = QImage(str(img_path))
                    if not mask_img.isNull():
                        scaled = mask_img.scaled(
                            iw,
                            ih,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        if surf.mask_invert:
                            scaled.invertPixels(QImage.InvertMode.InvertRgba)
                        self._surface_mask_cache[cache_key] = scaled
                        while len(self._surface_mask_cache) > 8:
                            self._surface_mask_cache.popitem(last=False)
                if scaled is not None and not scaled.isNull():
                    effect = QGraphicsOpacityEffect(container)
                    effect.setOpacityMask(QBrush(scaled))
                    container.setGraphicsEffect(effect)
                    return

        if surf.mask_feather > 0 and w > 2 and h > 2:
            hole_key = (
                round(float(surf.hole_x), 4),
                round(float(surf.hole_y), 4),
                round(float(surf.hole_w), 4),
                round(float(surf.hole_h), 4),
            )
            cache_key = (
                "feather",
                surf.mask_type,
                bool(surf.mask_invert),
                round(float(surf.mask_feather), 2),
                hole_key,
                iw,
                ih,
            )
            feather_img = self._surface_mask_cache.get(cache_key)
            if feather_img is not None:
                self._surface_mask_cache.move_to_end(cache_key)
            else:
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

                self._surface_mask_cache[cache_key] = feather_img
                while len(self._surface_mask_cache) > 8:
                    self._surface_mask_cache.popitem(last=False)

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
        crop: dict | None = None,
        aspect_ratio: str | None = None,
    ) -> tuple[MediaFrameGeometry, QTransform]:
        """Compute content geometry within surface and apply QTransform to container."""
        cw, ch = self._canvas_size()
        win_w, win_h = float(cw), float(ch)

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
        self._reset_master_if_empty(layer)
        self._update_tappo_visibility()

    def _reset_master_if_empty(self, layer: int) -> None:
        """A layer left empty forgets the opacity an action cue gave it.

        Otherwise whatever shows up there next without a GO (Live Mirror in
        design mode) would appear dimmed.
        """
        vc = self._video_containers.get(layer)
        ic = self._image_containers.get(layer)
        if vc is not None and ic is not None and not vc.isVisible() and not ic.isVisible():
            self.reset_layer_master_opacity(layer)

    def _apply_pixmap_to_layer(
        self,
        layer: int,
        pix: QPixmap,
        opacity: float = 1.0,
        crop: dict | None = None,
        scale: float = 1.0,
        pos_x: float = 0.0,
        pos_y: float = 0.0,
        aspect_ratio: str | None = None,
        surface_id: str | None = None,
        *,
        rotation: float = 0.0,
        mask_polygon: list[list[float]] | None = None,
        mask_feather: float = 0.0,
        reuse_item: bool = False,
    ) -> None:
        """Crop, scale, mask, rotate and composite *pix* onto *layer* mapped to surface."""
        self._cancel_fallback_timer()
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
            "rotation": rotation,
            "mask_polygon": mask_polygon,
            "mask_feather": mask_feather,
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

        # Polygon masks are baked into the already-scaled pixmap: the cost is
        # bounded by the output resolution (not the source) and happens only
        # when the operator edits the image, never per video frame.
        if mask_polygon and len(mask_polygon) >= 3:
            feather_px = float(mask_feather or 0.0) * float(max(scaled.width(), scaled.height()))
            soft = (
                feathered_mask_image(
                    mask_polygon, scaled.width(), scaled.height(), feather_px
                )
                if feather_px >= 1.0
                else None
            )
            masked = QPixmap(scaled.size())
            masked.fill(Qt.GlobalColor.transparent)
            mask_painter = QPainter(masked)
            try:
                mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                if soft is not None and not soft.isNull():
                    mask_painter.drawPixmap(0, 0, scaled)
                    # DestinationIn keeps the image where the soft mask is
                    # opaque and fades it out along the blurred ramp.
                    mask_painter.setCompositionMode(
                        QPainter.CompositionMode.CompositionMode_DestinationIn
                    )
                    mask_painter.drawImage(
                        QRectF(0.0, 0.0, float(scaled.width()), float(scaled.height())), soft
                    )
                else:
                    mask_painter.setClipPath(
                        polygon_path_from_normalized(
                            mask_polygon, 0.0, 0.0, float(scaled.width()), float(scaled.height())
                        )
                    )
                    mask_painter.drawPixmap(0, 0, scaled)
            finally:
                mask_painter.end()
            scaled = masked

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
        # Rotate around the centre of the visible slice so the image spins in
        # place instead of orbiting the corner; 1/10 degree is below the eye.
        item.setTransformOriginPoint(QPointF(scaled.width() / 2.0, scaled.height() / 2.0))
        item.setRotation(float(rotation))
        img_container.show()

        self._update_tappo_visibility()

    def show_image(self, layer: int, file_path: str, opacity: float = 1.0,
                   crop: dict | None = None, scale: float = 1.0,
                   pos_x: float = 0.0, pos_y: float = 0.0,
                   aspect_ratio: str | None = None,
                   surface_id: str | None = None,
                   rotation: float = 0.0,
                   mask_polygon: list[list[float]] | None = None,
                   mask_feather: float = 0.0) -> None:
        """Display a static image on layer 1, 2, or 3 with transforms and surface mapping.

        *rotation* is applied around the centre of the visible slice and
        *mask_polygon* (normalised to the visible frame) cuts the image to an
        arbitrary shape, with *mask_feather* softening its edge (0 = hard cut).
        All of them are non-destructive: the source file is untouched.
        """
        try:
            if not os.path.isfile(file_path):
                logger.warning("[OUTPUT] Image file not found: %s", file_path)
                return

            try:
                st = os.stat(file_path)
                pix_key = (file_path, st.st_mtime_ns, st.st_size)
            except OSError:
                pix_key = (file_path, 0, 0)

            pix = self._image_pixmap_cache.get(pix_key)
            if pix is not None and not pix.isNull():
                self._image_pixmap_cache.move_to_end(pix_key)
            else:
                pix = QPixmap(file_path)
                if pix.isNull():
                    return
                self._image_pixmap_cache[pix_key] = pix
                while len(self._image_pixmap_cache) > 16:
                    self._image_pixmap_cache.popitem(last=False)

            self._apply_pixmap_to_layer(
                layer, pix,
                opacity=opacity, crop=crop, scale=scale,
                pos_x=pos_x, pos_y=pos_y, aspect_ratio=aspect_ratio,
                surface_id=surface_id,
                rotation=rotation, mask_polygon=mask_polygon,
                mask_feather=mask_feather,
                reuse_item=False,
            )
            logger.info("[OUTPUT] Displayed image on Layer %d: %s (surf=%s, pos=%.2f,%.2f, scale=%.2f, op=%.2f, ar=%s, rot=%.1f, mask=%d)",
                        layer, file_path, surface_id or "default", pos_x, pos_y, scale, opacity,
                        aspect_ratio or "Native", rotation, len(mask_polygon or []))
        except Exception as exc:
            logger.error("[OUTPUT] show_image() failed on layer %d: %s", layer, exc)

    def show_mirrored_frame(self, layer: int, frame_image: QImage, opacity: float = 1.0,
                            crop: dict | None = None, scale: float = 1.0,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            aspect_ratio: str | None = None,
                            surface_id: str | None = None,
                            rotation: float = 0.0) -> None:
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
                rotation=rotation,
                reuse_item=True,
            )
        except Exception as exc:
            logger.error("[OUTPUT] show_mirrored_frame() failed on layer %d: %s", layer, exc)

    def ensure_live_video_visible(self, layer: int, scale: float = 1.0, crop: dict | None = None,
                                  pos_x: float = 0.0, pos_y: float = 0.0,
                                  opacity: float = 1.0, aspect_ratio: str | None = None,
                                  surface_id: str | None = None,
                                  rotation: float = 0.0) -> None:
        """Restore live video visibility on *layer* without disturbing an active loop deck."""
        self._cancel_fallback_timer()
        target_layer = layer if layer in self._video_containers else 1
        self.clear_pixmap_layer(target_layer)
        self.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, layer=target_layer, aspect_ratio=aspect_ratio,
            surface_id=surface_id, rotation=rotation,
        )
        self._video_containers[target_layer].show()
        self._update_tappo_visibility()

    # ── Crossfade ─────────────────────────────────────────────────────
    def begin_crossfade(self, layer: int, duration_sec: float) -> None:
        """Freeze what *layer* shows now and dissolve it over whatever comes next.

        Call right before new content is placed on *layer*: the snapshot sits
        just above the layer (below higher layers) and fades from opaque to
        transparent over *duration_sec*, so the new picture appears through it.
        Works for image→image, video→image, image→video and video→video.
        """
        target = layer if layer in self._video_containers else 1
        self._end_crossfade(target)
        if duration_sec <= 0:
            return
        vc = self._video_containers[target]
        ic = self._image_containers[target]
        if not (vc.isVisible() or ic.isVisible()):
            return
        rect = self._scene.sceneRect()
        w, h = int(rect.width()), int(rect.height())
        if w <= 0 or h <= 0:
            return

        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        hidden = []
        for item in self._scene.items():
            if item.parentItem() is None and item not in (vc, ic) and item.isVisible():
                item.setVisible(False)
                hidden.append(item)
        painter = QPainter(img)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            self._scene.render(painter, QRectF(0.0, 0.0, float(w), float(h)), rect)
        finally:
            painter.end()
            for item in hidden:
                item.setVisible(True)

        ghost = self._scene.addPixmap(QPixmap.fromImage(img))
        ghost.setPos(rect.topLeft())
        ghost.setZValue(target * 10 + 5)
        self._xfade_ghosts[target] = ghost

        steps = max(1, int(duration_sec * 30))
        cur = 0
        timer = QTimer(self)
        self._xfade_timers[target] = timer

        def _step() -> None:
            nonlocal cur
            cur += 1
            ghost.setOpacity(max(0.0, 1.0 - cur / steps))
            if cur >= steps:
                self._end_crossfade(target)

        timer.timeout.connect(_step)
        timer.start(int(1000 / 30))
        logger.info("[OUTPUT] Crossfade on Layer %d over %.2fs", target, duration_sec)

    def _end_crossfade(self, layer: int) -> None:
        """Stop and remove the crossfade snapshot on *layer* (if any)."""
        self._stop_timer_entry(self._xfade_timers, layer)
        ghost = self._xfade_ghosts.pop(layer, None)
        if ghost is not None:
            self._scene.removeItem(ghost)

    def clear_layer(self, layer: int) -> None:
        """Remove any visual content (image or video) from *layer*."""
        self._end_crossfade(layer)
        self.reset_layer_master_opacity(layer)
        self.clear_pixmap_layer(layer)
        self.hide_video_widget(layer=layer)
        self._update_tappo_visibility()

    def clear_all_layers(self) -> None:
        """Clear all active media overlays and video items across Layers 1-3."""
        self._cancel_fallback_timer()
        for layer in (1, 2, 3):
            self._end_crossfade(layer)
            self.reset_layer_master_opacity(layer)
            self.clear_pixmap_layer(layer)
            self.hide_video_widget(layer=layer)
        self._update_tappo_visibility()

    # ── Layer opacity (action cues) ───────────────────────────────────

    def layer_master_opacity(self, layer: int) -> float:
        """Opacity an action cue gave to the whole of *layer* (1.0 = untouched)."""
        container = self._video_containers.get(layer)
        return container.opacity() if container is not None else 1.0

    def _set_layer_master(self, layer: int, opacity: float) -> None:
        op = max(0.0, min(1.0, float(opacity)))
        for containers in (self._video_containers, self._image_containers):
            item = containers.get(layer)
            if item is not None:
                item.setOpacity(op)

    def reset_layer_master_opacity(self, layer: int) -> None:
        """Back to full layer opacity (a new cue on the layer starts undimmed)."""
        self._stop_timer_entry(self._master_fade_timers, layer)
        self._set_layer_master(layer, 1.0)

    def fade_layer_master(self, layer: int, target: float, duration_sec: float,
                          curve: str = "linear") -> None:
        """Dim or restore everything on *layer* to *target* over *duration_sec*.

        Independent of the cue's own opacity and fades (it multiplies them),
        and follows the clock like the audio fades.
        """
        if layer not in self._video_containers:
            return
        self._stop_timer_entry(self._master_fade_timers, layer)
        start = self.layer_master_opacity(layer)
        end = max(0.0, min(1.0, float(target)))
        if duration_sec <= 0 or abs(end - start) < 1e-3:
            self._set_layer_master(layer, end)
            return
        started = time.monotonic()
        timer = QTimer(self)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._master_fade_timers[layer] = timer

        def _step() -> None:
            progress = min(1.0, (time.monotonic() - started) / duration_sec)
            self._set_layer_master(layer, ramp_value(start, end, progress, curve))
            if progress >= 1.0:
                self._stop_timer_entry(self._master_fade_timers, layer)

        timer.timeout.connect(_step)
        timer.start(15)

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

    def show_video_widget(self, scale: float = 1.0, crop: dict | None = None,
                          pos_x: float = 0.0, pos_y: float = 0.0,
                          opacity: float = 1.0, layer: int = 1,
                          aspect_ratio: str | None = None,
                          surface_id: str | None = None,
                          rotation: float = 0.0) -> None:
        """Show the video item for *layer* with scale, crop, pos, opacity, aspect ratio, surface and rotation."""
        self._cancel_fallback_timer()
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
            surface_id=surface_id, rotation=rotation,
        )
        self._video_containers[target_layer].show()
        self._update_tappo_visibility()

    def update_video_layout(self, scale: float = 1.0, crop: dict | None = None,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            opacity: float = 1.0, layer: int = 1,
                            aspect_ratio: str | None = None,
                            surface_id: str | None = None,
                            rotation: float = 0.0) -> None:
        """Update geometry, scaling, position, opacity, crop mask, aspect ratio and rotation for *layer* video."""
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
                "rotation": rotation,
            }
            win_w, win_h = self._canvas_size()

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
            # Origin = centre of the *visible* slice (crop-aware), in item
            # coordinates: the item is positioned at (-cut_x, -cut_y), so the
            # visible rectangle starts at (cut_x, cut_y) inside the item.
            origin = QPointF(geom.cut_x + geom.vis_w / 2.0, geom.cut_y + geom.vis_h / 2.0)
            for item in items_to_update:
                item.setAspectRatioMode(ar_mode)
                item.setSize(QSizeF(geom.full_w, geom.full_h))
                item.setPos(-geom.cut_x, -geom.cut_y)
                item.setTransformOriginPoint(origin)
                item.setRotation(float(rotation))
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
                rotation=cfg.get("rotation", 0.0),
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
                    rotation=cfg.get("rotation", 0.0),
                    mask_polygon=cfg.get("mask_polygon"),
                    mask_feather=cfg.get("mask_feather", 0.0),
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

    def get_surface(self, surface_id: str | None) -> SurfaceDefinition:
        """Retrieve surface by ID with fallback to default full screen."""
        if not surface_id:
            surface_id = DEFAULT_SURFACE_ID
        return self._surfaces.get(surface_id) or self._surfaces.get(DEFAULT_SURFACE_ID) or create_default_surface()

    def set_calibration_guides_visible(self, visible: bool, active_surface_id: str | None = None) -> None:
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

    def span_all_screens(self) -> bool:
        """Span the output across every non-primary display."""
        return self.enter_span_mode()

    def enter_span_mode(self, screens: list[QScreen] | None = None) -> bool:
        """Map the output window as a single canvas over *screens*.

        Used when two (or more) projectors must form one uniform surface. The
        window is positioned on the union of the display geometries, so the
        desktop span shows a single continuous image.

        Returns ``False`` when no screen is available, leaving the window in
        its current state so the caller can fall back to single-screen output.
        """
        from PySide6.QtWidgets import QApplication

        if screens is None:
            app = QApplication.instance()
            primary = app.primaryScreen() if app is not None else None
            screens = [s for s in (app.screens() if app is not None else []) if s != primary]

        targets = [s for s in screens if s is not None]
        if not targets:
            logger.warning("[OUTPUT] Span richiesto ma nessuno schermo esterno disponibile")
            return False

        combined_geo = targets[0].geometry()
        for s in targets[1:]:
            combined_geo = combined_geo.united(s.geometry())

        self._span_screens = list(targets)
        self._target_screen = targets[0]
        self._is_external = True
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        # Leave fullscreen before setting an explicit geometry: while a window is
        # fullscreen the compositor ignores setGeometry().
        if self.isFullScreen():
            self.showNormal()
        self.setGeometry(combined_geo)
        self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        self.show()
        self._fit_layer0()
        logger.info(
            "[OUTPUT] Superficie unica su %d display: %s",
            len(targets), combined_geo,
        )
        return True

    def is_spanning(self) -> bool:
        """Return True when the output currently spans multiple displays."""
        return bool(self._span_screens)

    def spanned_screens(self) -> list[QScreen]:
        """Return the screens covered by the current span (empty if none)."""
        return list(self._span_screens)

    def get_output_resolution(self) -> tuple[int, int]:
        """Return the effective resolution (w, h) in pixels of the projector output."""
        if self.width() > 100 and self.height() > 100:
            return self._canvas_size()
        if self._span_screens:
            geo = self._span_screens[0].geometry()
            for s in self._span_screens[1:]:
                geo = geo.united(s.geometry())
            return geo.width(), geo.height()
        scr = self.current_target_screen()
        if scr:
            geo = scr.geometry()
            return geo.width(), geo.height()
        return 1920, 1080

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
        self._reset_master_if_empty(target_layer)
        self._update_tappo_visibility()

    def fade_out_video(self, duration_sec: float = 0.2,
                       callback: Callable[[], None] | None = None,
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
                       callback: Callable[[], None] | None = None) -> None:
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
                      callback: Callable[[], None] | None = None) -> None:
        """Bring Layer 0 (Tappo) to front with optional micro-fade.
        All live media across Layers 1-3 is removed and the logo is displayed."""
        self._cancel_fallback_timer()
        self._panic_black = False
        visible_videos = [l for l, c in self._video_containers.items() if c.isVisible()]
        has_media = bool(visible_videos) or self._has_active_media()
        if not has_media or fade_duration_sec <= 0:
            self.clear_all_layers()
            if self._logo_item is not None:
                self._logo_item.setVisible(True)
            logger.info("[OUTPUT] Fallback (Layer 0 Tappo) restored immediately")
            if callback:
                callback()
            return

        # Faded transition to fallback across all active video & image layers.
        # Guarded by generation counter + managed QTimer so any cue fired within
        # fade_duration_sec cancels this callback cleanly instead of getting wiped.
        expected_gen = self._fallback_gen
        timer = QTimer(self)
        timer.setSingleShot(True)
        self._fallback_timer = timer

        def _finish():
            if self._fallback_timer is timer:
                self._fallback_timer = None
            timer.deleteLater()
            if self._fallback_gen != expected_gen:
                return
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
        timer.timeout.connect(_finish)
        timer.start(int(fade_duration_sec * 1000) + 15)

    def panic_blackout(self) -> None:
        """0ms hard stop across all visual layers: pure Black if L0 is default grid, else Custom Tappo."""
        self._cancel_fallback_timer()
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

    def _bind_to_screen(self, screen: QScreen | None) -> None:
        """Bind both the QWidget and its native QWindow handle to *screen* (Wayland & X11)."""
        if screen is None:
            return
        self.setScreen(screen)
        self.create()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)

    def _show_fullscreen_on(self, screen: QScreen) -> None:
        """Make the window full screen on *screen* itself.

        Windows puts a window full screen on the monitor it currently sits on.
        setWindowFlags() re-creates the native window where the old one was, so
        when a projector was plugged in while the single-monitor preview was
        open, showFullScreen() covered the director window on the laptop
        (2026-11-21). Show the window on the target monitor first, then switch
        it to full screen there.

        processEvents() can run a monitor change: if the screen went away
        meanwhile (HDMI flapping) or the window was re-targeted by that change,
        the newer configuration wins and this one stops here.
        """
        geo = screen.geometry()
        self.setGeometry(geo)
        self.show()
        QCoreApplication.processEvents()
        if self._target_screen is not screen or not shiboken6.isValid(screen) \
                or screen not in QGuiApplication.screens():
            logger.info("[OUTPUT] Screen changed while going full screen - keeping the newer setup")
            return
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.setGeometry(geo)
        self.showFullScreen()

    def configure_screen(self, screen: QScreen, is_external: bool = True) -> None:
        """Attach to *screen*. If is_external=True (multi-monitor), goes fullscreen borderless.
        If is_external=False (single monitor test), opens as a clean preview window on screen."""
        self._is_external = is_external
        self._target_screen = screen
        self._span_screens = []

        if is_external:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Window
            )
            self._bind_to_screen(screen)
            self.setWindowTitle("BlindCue – Live Output")
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self._show_fullscreen_on(screen)
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
        for layer in (1, 2, 3):
            self._reapply_video_layout(layer)
            self._reapply_image_layout(layer)
        self._update_tappo_visibility()

    def attach_to_screen(self, screen: QScreen, is_external: bool = True) -> None:
        """Move the output window onto *screen* and match its geometry.

        External screens go fullscreen; the primary (director) screen falls
        back to a window so the operator can still see the UI underneath.
        """
        self.configure_screen(screen, is_external=is_external)

    def current_target_screen(self) -> QScreen | None:
        """Return currently attached QScreen."""
        return self._target_screen

    def ensure_on_target_screen(self) -> None:
        """Put the window back on its screen if Windows moved it.

        After a display change Windows 11 restores window positions on its own,
        a moment after the program placed its windows: coming back from
        "Second screen only" it moved the output onto the laptop, full screen
        over the director (2026-11-22). Called once things have settled.
        """
        target = self._target_screen
        if target is None or self._span_screens or not self.isVisible():
            return
        if not shiboken6.isValid(target) or target not in QGuiApplication.screens():
            return
        if target.geometry().contains(self.frameGeometry().center()):
            return
        logger.info("[OUTPUT] Window moved off '%s' by the system - placing it again", target.name())
        self.configure_screen(target, is_external=self._is_external)

    def set_target_screen(self, screen: QScreen) -> None:
        """Switch output window to *screen* dynamically at runtime.

        The same screen still needs a new setup when it became the primary one
        (Windows "Second screen only", or the laptop lid closed): the output
        must then turn into the preview window, or it covers the director.
        """
        if screen is None:
            return
        from PySide6.QtWidgets import QApplication
        primary = QApplication.primaryScreen()
        is_external = (screen != primary)
        if screen == self._target_screen and is_external == self._is_external:
            return
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
            if self._target_screen is not None:
                self._show_fullscreen_on(self._target_screen)
            else:
                self.showFullScreen()
        self._fit_layer0()

    def force_close(self) -> None:
        """Close the output reliably during shutdown, bypassing hide logic."""
        self._force_close_allowed = True
        self._cancel_fallback_timer()
        for timer_map in (self._video_fade_timers, self._layer_fade_timers, self._deck_swap_timers,
                          self._master_fade_timers):
            for t in list(timer_map.values()):
                if t.isActive():
                    t.stop()
                t.deleteLater()
            timer_map.clear()
        self._surface_mask_cache.clear()
        self._image_pixmap_cache.clear()
        self.close()

    # ── Overrides ─────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Refit the 16:9 scene and Layer 0 background after a size change."""
        super().resizeEvent(event)
        self._fit_layer0()
        for layer in (1, 2, 3):
            self._reapply_video_layout(layer)
            self._reapply_image_layout(layer)
        if self._calibration_item.isVisible():
            self._calibration_item.update()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Ignore accidental close requests unless shutdown is in progress."""
        if self._force_close_allowed or not self._is_external:
            event.accept()
        else:
            logger.warning("[OUTPUT] Close attempt blocked during show (use force_close)")
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """F7 toggles the calibration guides; F11 toggles full screen; Escape leaves
        full screen on a floating preview (never closes the external output)."""
        if event.key() == Qt.Key.Key_F7:
            self.toggle_calibration_guides()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F11:
            # Full screen on demand for the single-monitor preview (rehearsals).
            # The external projector output is always full screen already.
            if not self._is_external:
                self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if not self._is_external:
                if self.isFullScreen():
                    self.toggle_fullscreen()
                event.accept()
                return
            event.ignore()
            return
        super().keyPressEvent(event)
