"""Visual Surface Mapping Studio Dialog & Interactive Projection Canvas.

Provides theatre technicians and live operators with:
- Visual management of virtual screens / surfaces (Full screen, Slices, PiP, Dual Projector Spanning).
- Direct mouse dragging of bounding boxes and 4-corner perspective handles (keystone / corner-pinning).
- Real-time on-projector alignment guides and test pattern toggle (F7).
- Micro-nudge directional controls for precision calibration onto physical objects/architectures.
- Dual unit support: native Pixels (px) and normalized Percentages (%).
"""

from __future__ import annotations

import logging
import math
from typing import Any, List, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.surface import (
    DEFAULT_SURFACE_ID,
    DEFAULT_SURFACE_NAME,
    PRESET_DEFINITIONS,
    SURFACE_COLORS,
    SurfaceDefinition,
    SurfaceMode,
    create_default_surface,
)
from ui.output_window import OutputWindow
from ui.spinboxes import SmartDoubleSpinBox
from ui.theme import get_active_theme

logger = logging.getLogger(__name__)


# ── Interactive Stage Preview Canvas ──────────────────────────────────────────

class SurfaceCanvasWidget(QWidget):
    """Interactive visual representation of the stage projector canvas.

    Allows operators to drag entire surfaces or individual corner pins in real-time
    with live coordinate HUD overlays, hover highlights, and precision snapping.
    """

    surface_modified = Signal(SurfaceDefinition)
    active_corner_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._surfaces: list[SurfaceDefinition] = []
        self._active_surface_id: str = DEFAULT_SURFACE_ID
        self._active_corner: int = 0  # 0: TL, 1: TR, 2: BR, 3: BL

        # Hover & visual feedback state
        self._hovered_corner: Optional[int] = None
        self._hovered_surface: bool = False
        self._output_res: tuple[int, int] = (1920, 1080)
        self._unit_mode: str = "px"  # "px" or "percent"
        self._last_mouse_pos = QPointF()

        # Interaction drag state
        self._drag_mode: Optional[str] = None  # None, "corner_0".."corner_3", "move_surface"
        self._drag_start_mouse = QPointF()
        self._drag_start_surface: Optional[SurfaceDefinition] = None
        self._aspect_ratio: float = 16.0 / 9.0

        # Snapping thresholds
        self._snap_grid = True
        self._snap_threshold = 0.015

    def set_canvas_aspect_ratio(self, ratio: float) -> None:
        if ratio > 0.1:
            self._aspect_ratio = ratio
            self.update()

    def set_output_resolution(self, w: int, h: int) -> None:
        self._output_res = (max(1, w), max(1, h))
        self.set_canvas_aspect_ratio(self._output_res[0] / self._output_res[1])
        self.update()

    def set_unit_mode(self, mode: str) -> None:
        self._unit_mode = mode
        self.update()

    def set_surfaces(self, surfaces: list[SurfaceDefinition], active_id: str) -> None:
        self._surfaces = surfaces
        self._active_surface_id = active_id
        self.update()

    def set_active_surface_id(self, active_id: str) -> None:
        self._active_surface_id = active_id
        self.update()

    def set_active_corner(self, corner_idx: int) -> None:
        if 0 <= corner_idx < 4:
            self._active_corner = corner_idx
            self.update()

    def get_active_surface(self) -> Optional[SurfaceDefinition]:
        for s in self._surfaces:
            if s.surface_id == self._active_surface_id:
                return s
        return self._surfaces[0] if self._surfaces else None

    # ── Geometry Math ─────────────────────────────────────────────────

    def _get_canvas_rect(self) -> QRectF:
        """Return the letterboxed/pillarboxed stage rectangle inside this widget."""
        w = max(1.0, float(self.width() - 24))
        h = max(1.0, float(self.height() - 24))
        target_ar = self._aspect_ratio

        if (w / h) >= target_ar:
            ch = h
            cw = ch * target_ar
        else:
            cw = w
            ch = cw / target_ar

        cx = 12.0 + (w - cw) / 2.0
        cy = 12.0 + (h - ch) / 2.0
        return QRectF(cx, cy, cw, ch)

    def _norm_to_canvas(self, nx: float, ny: float) -> QPointF:
        crect = self._get_canvas_rect()
        return QPointF(crect.x() + nx * crect.width(), crect.y() + ny * crect.height())

    def _canvas_to_norm(self, pt: QPointF) -> tuple[float, float]:
        crect = self._get_canvas_rect()
        nx = (pt.x() - crect.x()) / max(1.0, crect.width())
        ny = (pt.y() - crect.y()) / max(1.0, crect.height())
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    def _snap_norm(self, val: float) -> float:
        """Snap value to 0.0, 0.25, 0.3333, 0.5, 0.6667, 0.75, 1.0 if close."""
        if not self._snap_grid:
            return val
        snap_targets = [0.0, 0.25, 1.0 / 3.0, 0.5, 2.0 / 3.0, 0.75, 1.0]
        for t in snap_targets:
            if abs(val - t) <= self._snap_threshold:
                return t
        return val

    # ── Mouse Interaction ─────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        mpos = event.position()
        self._last_mouse_pos = mpos
        active_surf = self.get_active_surface()
        if not active_surf:
            return

        # Check corner handles first with generous hit radius (18 px)
        handle_radius = 18.0
        for i in range(4):
            cpt = self._norm_to_canvas(active_surf.corners[i][0], active_surf.corners[i][1])
            dist = math.hypot(mpos.x() - cpt.x(), mpos.y() - cpt.y())
            if dist <= handle_radius:
                self._drag_mode = f"corner_{i}"
                self._active_corner = i
                self._drag_start_mouse = mpos
                self._drag_start_surface = active_surf.clone()
                self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
                self.active_corner_changed.emit(i)
                self.update()
                return

        # Check inside active surface body for whole move
        poly = QPolygonF([
            self._norm_to_canvas(pt[0], pt[1]) for pt in active_surf.corners
        ])
        if poly.containsPoint(mpos, Qt.FillRule.OddEvenFill):
            self._drag_mode = "move_surface"
            self._drag_start_mouse = mpos
            self._drag_start_surface = active_surf.clone()
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            self.update()
            return

        # Check if clicking on another surface
        for s in self._surfaces:
            if s.surface_id == self._active_surface_id:
                continue
            s_poly = QPolygonF([
                self._norm_to_canvas(pt[0], pt[1]) for pt in s.corners
            ])
            if s_poly.containsPoint(mpos, Qt.FillRule.OddEvenFill):
                self._active_surface_id = s.surface_id
                self.surface_modified.emit(s)
                self.update()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        mpos = event.position()
        self._last_mouse_pos = mpos
        active_surf = self.get_active_surface()

        if self._drag_mode and self._drag_start_surface and active_surf:
            crect = self._get_canvas_rect()
            dx_norm = (mpos.x() - self._drag_start_mouse.x()) / max(1.0, crect.width())
            dy_norm = (mpos.y() - self._drag_start_mouse.y()) / max(1.0, crect.height())

            if self._drag_mode.startswith("corner_"):
                c_idx = int(self._drag_mode.split("_")[1])
                start_c = self._drag_start_surface.corners[c_idx]
                new_x = self._snap_norm(max(0.0, min(1.0, start_c[0] + dx_norm)))
                new_y = self._snap_norm(max(0.0, min(1.0, start_c[1] + dy_norm)))

                if active_surf.mode == SurfaceMode.QUAD.value:
                    active_surf.set_corner(c_idx, new_x, new_y)
                else:
                    # In RECTANGLE mode, moving a corner resizes the bounding box
                    cur_rect_x = self._drag_start_surface.x
                    cur_rect_y = self._drag_start_surface.y
                    cur_rect_w = self._drag_start_surface.w
                    cur_rect_h = self._drag_start_surface.h

                    if c_idx == 0:  # TL
                        r = cur_rect_x + cur_rect_w
                        b = cur_rect_y + cur_rect_h
                        active_surf.x = min(r - 0.02, new_x)
                        active_surf.y = min(b - 0.02, new_y)
                        active_surf.w = r - active_surf.x
                        active_surf.h = b - active_surf.y
                    elif c_idx == 1:  # TR
                        b = cur_rect_y + cur_rect_h
                        active_surf.y = min(b - 0.02, new_y)
                        active_surf.w = max(0.02, new_x - active_surf.x)
                        active_surf.h = b - active_surf.y
                    elif c_idx == 2:  # BR
                        active_surf.w = max(0.02, new_x - active_surf.x)
                        active_surf.h = max(0.02, new_y - active_surf.y)
                    elif c_idx == 3:  # BL
                        r = cur_rect_x + cur_rect_w
                        active_surf.x = min(r - 0.02, new_x)
                        active_surf.w = r - active_surf.x
                        active_surf.h = max(0.02, new_y - active_surf.y)

                    active_surf.sync_quad_from_rect()

                self.surface_modified.emit(active_surf)
                self.update()
                return

            elif self._drag_mode == "move_surface":
                # Translate entire surface
                if active_surf.mode == SurfaceMode.RECTANGLE.value:
                    start_x = self._drag_start_surface.x
                    start_y = self._drag_start_surface.y
                    new_x = self._snap_norm(max(0.0, min(1.0 - active_surf.w, start_x + dx_norm)))
                    new_y = self._snap_norm(max(0.0, min(1.0 - active_surf.h, start_y + dy_norm)))
                    active_surf.x = round(new_x, 6)
                    active_surf.y = round(new_y, 6)
                    active_surf.sync_quad_from_rect()
                else:
                    # Translate all 4 corners keeping relative shape
                    for i in range(4):
                        sc = self._drag_start_surface.corners[i]
                        nx = max(0.0, min(1.0, sc[0] + dx_norm))
                        ny = max(0.0, min(1.0, sc[1] + dy_norm))
                        active_surf.corners[i] = [round(nx, 6), round(ny, 6)]
                    active_surf.sync_rect_from_quad()

                self.surface_modified.emit(active_surf)
                self.update()
                return

        # Hover detection when not dragging
        prev_hover_c = self._hovered_corner
        prev_hover_s = self._hovered_surface
        self._hovered_corner = None
        self._hovered_surface = False

        if active_surf:
            handle_radius = 18.0
            for i in range(4):
                cpt = self._norm_to_canvas(active_surf.corners[i][0], active_surf.corners[i][1])
                if math.hypot(mpos.x() - cpt.x(), mpos.y() - cpt.y()) <= handle_radius:
                    self._hovered_corner = i
                    self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    if self._hovered_corner != prev_hover_c:
                        self.update()
                    return

            poly = QPolygonF([
                self._norm_to_canvas(pt[0], pt[1]) for pt in active_surf.corners
            ])
            if poly.containsPoint(mpos, Qt.FillRule.OddEvenFill):
                self._hovered_surface = True
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                if not prev_hover_s:
                    self.update()
                return

        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        if prev_hover_c is not None or prev_hover_s:
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode:
            self._drag_mode = None
            self._drag_start_surface = None
            active_surf = self.get_active_surface()
            if active_surf:
                self.surface_modified.emit(active_surf)
            self.update()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        active_surf = self.get_active_surface()
        if not active_surf:
            super().keyPressEvent(event)
            return

        # Number keys 1..4 switch corner directly
        if event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4):
            idx = event.key() - Qt.Key.Key_1
            self._active_corner = idx
            self.active_corner_changed.emit(idx)
            self.update()
            event.accept()
            return

        w, h = self._output_res
        if self._unit_mode == "px":
            step_px = 10.0 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1.0
            dx = step_px / max(1.0, float(w))
            dy = step_px / max(1.0, float(h))
        else:
            step_pct = 0.01 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 0.002
            dx = step_pct
            dy = step_pct

        step_x, step_y = 0.0, 0.0
        if event.key() == Qt.Key.Key_Left:
            step_x = -dx
        elif event.key() == Qt.Key.Key_Right:
            step_x = dx
        elif event.key() == Qt.Key.Key_Up:
            step_y = -dy
        elif event.key() == Qt.Key.Key_Down:
            step_y = dy
        else:
            super().keyPressEvent(event)
            return

        if active_surf.mode == SurfaceMode.QUAD.value:
            active_surf.nudge_corner(self._active_corner, step_x, step_y)
        else:
            active_surf.nudge_rect(step_x, step_y)

        self.surface_modified.emit(active_surf)
        self.update()
        event.accept()

    # ── Paint Engine ──────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        theme = get_active_theme()
        is_mono = theme.is_monochrome

        # Outer widget background
        painter.fillRect(self.rect(), QColor("#090d16" if not is_mono else "#111114"))

        crect = self._get_canvas_rect()

        # Stage projector canvas background
        painter.fillRect(crect, QColor("#111827" if not is_mono else "#18181c"))
        painter.setPen(QPen(QColor("#334155" if not is_mono else "#383840"), 1))
        painter.drawRect(crect)

        # Draw 10% grid lines
        grid_pen = QPen(QColor(71, 85, 105, 80 if not is_mono else 60), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in range(1, 10):
            gx = crect.x() + crect.width() * (i / 10.0)
            gy = crect.y() + crect.height() * (i / 10.0)
            painter.drawLine(QPointF(gx, crect.y()), QPointF(gx, crect.bottom()))
            painter.drawLine(QPointF(crect.x(), gy), QPointF(crect.right(), gy))

        # Center optical crosshair on stage
        cx, cy = crect.center().x(), crect.center().y()
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.SolidLine))
        painter.drawLine(QPointF(cx - 15, cy), QPointF(cx + 15, cy))
        painter.drawLine(QPointF(cx, cy - 15), QPointF(cx, cy + 15))

        # Draw dual-projector 50% seam line if aspect ratio >= 2.0
        if self._aspect_ratio >= 2.0:
            painter.setPen(QPen(QColor("#f43f5e"), 1, Qt.PenStyle.DashDotLine))
            painter.drawLine(QPointF(cx, crect.y()), QPointF(cx, crect.bottom()))
            painter.setPen(QColor("#f43f5e"))
            font_seam = QFont("sans-serif", 8)
            painter.setFont(font_seam)
            painter.drawText(int(cx + 4), int(crect.y() + 14), "SEAM 50%")

        # Draw all surfaces
        corner_names = ["TL", "TR", "BR", "BL"]
        font_badge = QFont("sans-serif", 9)
        font_badge.setBold(True)
        font_corner = QFont("sans-serif", 8)
        font_corner.setBold(True)

        for s in self._surfaces:
            is_active = (s.surface_id == self._active_surface_id)
            base_col = QColor(s.color if s.color else "#00f0ff")
            if is_mono:
                col = QColor("#ffffff" if is_active else "#94a3b8")
            else:
                col = QColor("#00f0ff") if is_active else base_col

            poly_pts = [self._norm_to_canvas(pt[0], pt[1]) for pt in s.corners]
            poly = QPolygonF(poly_pts)

            # Fill surface
            fill_alpha = 60 if is_active else 20
            painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), fill_alpha)))
            painter.setPen(QPen(col, 2 if is_active else 1, Qt.PenStyle.SolidLine if is_active else Qt.PenStyle.DashLine))
            painter.drawPolygon(poly)

            # Optical diagonals
            diag_pen = QPen(QColor(col.red(), col.green(), col.blue(), 140 if is_active else 70), 1, Qt.PenStyle.DotLine)
            painter.setPen(diag_pen)
            painter.drawLine(poly_pts[0], poly_pts[2])
            painter.drawLine(poly_pts[1], poly_pts[3])

            # Surface centroid badge
            scx = sum(p.x() for p in poly_pts) / 4.0
            scy = sum(p.y() for p in poly_pts) / 4.0
            badge_text = s.name
            painter.setFont(font_badge)
            bw = painter.fontMetrics().horizontalAdvance(badge_text) + 14
            bh = 20
            badge_rect = QRectF(scx - bw / 2, scy - bh / 2, bw, bh)
            painter.setBrush(QBrush(QColor(15, 23, 42, 230 if not is_mono else 240)))
            painter.setPen(QPen(col, 1))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            # Draw corner handles for active surface
            if is_active:
                painter.setFont(font_corner)
                for idx, pt in enumerate(poly_pts):
                    is_selected_corner = (idx == self._active_corner)
                    is_hovered = (idx == self._hovered_corner)
                    is_dragging_this = (self._drag_mode == f"corner_{idx}")

                    h_rad = 10 if (is_selected_corner or is_hovered or is_dragging_this) else 8
                    handle_col = QColor("#f59e0b" if not is_mono else "#ffffff") if is_selected_corner else col

                    # Glowing dashed ring on hover or active dragging
                    if is_hovered or is_dragging_this:
                        ring_pen = QPen(QColor("#38bdf8" if not is_mono else "#ffffff"), 2, Qt.PenStyle.DashLine)
                        painter.setPen(ring_pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawEllipse(pt, h_rad + 6, h_rad + 6)

                    painter.setBrush(QBrush(handle_col))
                    painter.setPen(QPen(QColor("#000000"), 2))
                    painter.drawEllipse(pt, h_rad, h_rad)

                    # Label
                    c_lbl = f"C{idx+1} {corner_names[idx]}"
                    ox = 12 if idx in (0, 3) else -42
                    oy = -12 if idx in (0, 1) else 18
                    painter.setPen(QColor("#000000"))
                    painter.drawText(int(pt.x() + ox + 1), int(pt.y() + oy + 1), c_lbl)
                    painter.setPen(handle_col)
                    painter.drawText(int(pt.x() + ox), int(pt.y() + oy), c_lbl)

        # Draw live floating HUD tooltip when dragging
        active_surf = self.get_active_surface()
        if self._drag_mode and active_surf:
            mpt = self._last_mouse_pos
            painter.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
            if self._drag_mode.startswith("corner_"):
                c_idx = int(self._drag_mode.split("_")[1])
                c_norm = active_surf.corners[c_idx]
                px_x = int(round(c_norm[0] * self._output_res[0]))
                px_y = int(round(c_norm[1] * self._output_res[1]))
                pct_x = c_norm[0] * 100.0
                pct_y = c_norm[1] * 100.0
                hud_text = f"C{c_idx+1} ({corner_names[c_idx]}): {px_x} px, {px_y} px  ({pct_x:.1f}%, {pct_y:.1f}%)"
            else:
                px_x = int(round(active_surf.x * self._output_res[0]))
                px_y = int(round(active_surf.y * self._output_res[1]))
                px_w = int(round(active_surf.w * self._output_res[0]))
                px_h = int(round(active_surf.h * self._output_res[1]))
                hud_text = f"Pos: {px_x}, {px_y} px · Dim: {px_w} × {px_h} px"

            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(hud_text) + 20
            th = 26
            hx = min(float(self.width() - tw - 12), max(12.0, float(mpt.x() + 15)))
            hy = min(float(self.height() - th - 12), max(12.0, float(mpt.y() - 36)))
            hud_rect = QRectF(hx, hy, float(tw), float(th))

            painter.setBrush(QBrush(QColor(15, 23, 42, 240)))
            painter.setPen(QPen(QColor("#38bdf8" if not is_mono else "#ffffff"), 1.5))
            painter.drawRoundedRect(hud_rect, 5, 5)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(hud_rect, Qt.AlignmentFlag.AlignCenter, hud_text)


# ── Visual Surface Mapping Studio Dialog ──────────────────────────────────────

class SurfaceMappingDialog(QDialog):
    """Full-featured Studio Dialog for Managing Virtual Screens & Projection Mapping."""

    surfaces_changed = Signal(list)  # emits list[SurfaceDefinition]

    def __init__(
        self,
        output_window: OutputWindow,
        surfaces: Optional[List[SurfaceDefinition]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._output = output_window
        self._surfaces: list[SurfaceDefinition] = [
            s.clone() for s in (surfaces or self._output.get_surfaces())
        ]
        if not self._surfaces:
            self._surfaces = [create_default_surface()]

        self._active_id: str = self._surfaces[0].surface_id
        self._active_corner: int = 0
        self._unit_mode: str = "px"  # "px" or "percent"

        w_out, h_out = self._output.get_output_resolution() if hasattr(self._output, "get_output_resolution") else (1920, 1080)
        self._output_res = (w_out, h_out)
        self._updating_ui: bool = False

        self.setWindowTitle("BlindCue – Studio Superfici di Proiezione & Video Mapping")
        self.setMinimumSize(1040, 700)
        self.resize(1140, 740)

        self._build_ui()
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

        # Canvas signals
        self.canvas.set_output_resolution(w_out, h_out)
        self.canvas.set_unit_mode(self._unit_mode)
        self.canvas.surface_modified.connect(self._on_canvas_surface_modified)
        self.canvas.active_corner_changed.connect(self._on_canvas_corner_selected)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_title = QLabel("📐")
        icon_title.setStyleSheet("font-size: 26px; background: transparent;")
        header.addWidget(icon_title)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("Studio Superfici di Proiezione & Video Mapping")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #ffffff;")
        lbl_sub = QLabel("Crea schermi virtuali, keystone a 4 angoli per elementi scenografici e proiezioni su monitor affiancati")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)

        header.addStretch()

        # Live Projector Guides Toggle (F7)
        self.btn_live_guides = QPushButton("👁 Mostra Guide sul Proiettore Live (F7)")
        self.btn_live_guides.setCheckable(True)
        self.btn_live_guides.setChecked(self._output.is_calibration_guides_visible())
        self.btn_live_guides.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_guides.setFixedHeight(36)
        self.btn_live_guides.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:checked {
                background: #0284c7;
                color: #ffffff;
                border: 2px solid #38bdf8;
            }
            QPushButton:hover {
                background: #0369a1;
                color: #ffffff;
            }
        """)
        self.btn_live_guides.clicked.connect(self._toggle_live_guides)
        header.addWidget(self.btn_live_guides)

        main_layout.addLayout(header)

        # ── Body Splitter ─────────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(14)

        # Left Column: Configuration Controls (width ~370px)
        left_panel = QFrame()
        left_panel.setFixedWidth(370)
        left_panel.setStyleSheet("background: #0f172a; border: 1px solid #334155; border-radius: 8px;")
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(12, 12, 12, 12)
        left_lay.setSpacing(10)

        # Group 1: Surfaces List
        lbl_surfs = QLabel("SUPERFICI DEFINITE")
        lbl_surfs.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; letter-spacing: 1px;")
        left_lay.addWidget(lbl_surfs)

        self.list_surfaces = QListWidget()
        self.list_surfaces.setFixedHeight(115)
        self.list_surfaces.setStyleSheet("""
            QListWidget {
                background: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #f8fafc;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #0284c7;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        self.list_surfaces.currentRowChanged.connect(self._on_surface_selected)
        left_lay.addWidget(self.list_surfaces)

        # Surface action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_add = QPushButton("＋ Nuova")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_surface)

        self.btn_dup = QPushButton("⎘ Duplica")
        self.btn_dup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dup.clicked.connect(self._duplicate_surface)

        self.btn_del = QPushButton("✕ Elimina")
        self.btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del.clicked.connect(self._delete_surface)

        for b in (self.btn_add, self.btn_dup, self.btn_del):
            b.setStyleSheet("""
                QPushButton {
                    background: #334155;
                    color: #ffffff;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #475569;
                }
            """)
            btn_row.addWidget(b)
        left_lay.addLayout(btn_row)

        # Surface Name edit
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(QLabel("Nome:"))
        self.edit_name = QLineEdit()
        self.edit_name.setStyleSheet("background: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 4px;")
        self.edit_name.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self.edit_name)
        left_lay.addLayout(name_row)

        # Group 2: Mode & Presets
        lbl_geom = QLabel("GEOMETRIA & PRESET")
        lbl_geom.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; letter-spacing: 1px; margin-top: 4px;")
        left_lay.addWidget(lbl_geom)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_mode_rect = QPushButton("⬛ Rettangolare")
        self.btn_mode_rect.setCheckable(True)
        self.btn_mode_rect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_rect.clicked.connect(lambda: self._set_surface_mode(SurfaceMode.RECTANGLE.value))

        self.btn_mode_quad = QPushButton("⬡ Prospettiva (4 Angoli)")
        self.btn_mode_quad.setCheckable(True)
        self.btn_mode_quad.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_quad.clicked.connect(lambda: self._set_surface_mode(SurfaceMode.QUAD.value))

        mode_style = """
            QPushButton {
                background: #1e293b;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:checked {
                background: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
            }
        """
        self.btn_mode_rect.setStyleSheet(mode_style)
        self.btn_mode_quad.setStyleSheet(mode_style)
        mode_row.addWidget(self.btn_mode_rect)
        mode_row.addWidget(self.btn_mode_quad)
        left_lay.addLayout(mode_row)

        # Presets dropdown
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        preset_row.addWidget(QLabel("Preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.setStyleSheet("background: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 4px;")
        self.combo_preset.addItem("— Seleziona Preset Rapido —", None)
        for p in PRESET_DEFINITIONS:
            self.combo_preset.addItem(p["name"], p)
        self.combo_preset.currentIndexChanged.connect(self._apply_preset)
        preset_row.addWidget(self.combo_preset)
        left_lay.addLayout(preset_row)

        # Group 3: Fine Adjustment & Unit Switch (Pixel vs Percentage)
        fine_header = QHBoxLayout()
        lbl_fine = QLabel("REGOLAZIONE FINE & UNITA'")
        lbl_fine.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; letter-spacing: 1px; margin-top: 4px;")
        fine_header.addWidget(lbl_fine)
        fine_header.addStretch()

        self.lbl_res_badge = QLabel(f"🖥 {self._output_res[0]}×{self._output_res[1]} px")
        self.lbl_res_badge.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold; padding: 2px 6px; background: #1e293b; border: 1px solid #334155; border-radius: 4px;")
        fine_header.addWidget(self.lbl_res_badge)
        left_lay.addLayout(fine_header)

        # Unit Selector Toggle: Pixel vs Percentage
        unit_row = QHBoxLayout()
        unit_row.setSpacing(6)
        self.btn_unit_px = QPushButton("📐 Pixel (px)")
        self.btn_unit_px.setCheckable(True)
        self.btn_unit_px.setChecked(True)
        self.btn_unit_px.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unit_px.clicked.connect(lambda: self._set_unit_mode("px"))

        self.btn_unit_pct = QPushButton("％ Percentuale (%)")
        self.btn_unit_pct.setCheckable(True)
        self.btn_unit_pct.setChecked(False)
        self.btn_unit_pct.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unit_pct.clicked.connect(lambda: self._set_unit_mode("percent"))

        unit_btn_style = """
            QPushButton {
                background: #1e293b;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
            QPushButton:checked {
                background: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
            }
        """
        self.btn_unit_px.setStyleSheet(unit_btn_style)
        self.btn_unit_pct.setStyleSheet(unit_btn_style)
        unit_row.addWidget(self.btn_unit_px)
        unit_row.addWidget(self.btn_unit_pct)
        left_lay.addLayout(unit_row)

        # Directional D-Pad for micro-nudge
        dpad_box = QHBoxLayout()
        dpad_box.setSpacing(6)
        self.btn_nudge_l = QPushButton("◀")
        self.btn_nudge_u = QPushButton("▲")
        self.btn_nudge_d = QPushButton("▼")
        self.btn_nudge_r = QPushButton("▶")

        for b, (dx, dy) in (
            (self.btn_nudge_l, (-1, 0)),
            (self.btn_nudge_u, (0, -1)),
            (self.btn_nudge_d, (0, 1)),
            (self.btn_nudge_r, (1, 0)),
        ):
            b.setFixedSize(36, 30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("background: #334155; color: #ffffff; border: 1px solid #475569; border-radius: 4px; font-weight: bold;")
            b.clicked.connect(lambda _=False, x=dx, y=dy: self._nudge_active(x, y))

        dpad_box.addStretch()
        dpad_box.addWidget(self.btn_nudge_l)
        dpad_box.addWidget(self.btn_nudge_u)
        dpad_box.addWidget(self.btn_nudge_d)
        dpad_box.addWidget(self.btn_nudge_r)
        dpad_box.addStretch()
        left_lay.addLayout(dpad_box)

        # Coordinates grid (updates dynamically based on mode)
        self.coord_stack = QFrame()
        self.coord_lay = QGridLayout(self.coord_stack)
        self.coord_lay.setContentsMargins(0, 0, 0, 0)
        self.coord_lay.setSpacing(6)

        # RECT widgets
        self.spin_rx = SmartDoubleSpinBox()
        self.spin_ry = SmartDoubleSpinBox()
        self.spin_rw = SmartDoubleSpinBox()
        self.spin_rh = SmartDoubleSpinBox()
        for s in (self.spin_rx, self.spin_ry, self.spin_rw, self.spin_rh):
            s.setStyleSheet("background: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px;")
            s.valueChanged.connect(self._on_rect_spins_changed)

        # QUAD widgets
        self.combo_corner = QComboBox()
        self.combo_corner.setStyleSheet("background: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px;")
        for i, lbl in enumerate(["C1 · Alto SX (TL)", "C2 · Alto DX (TR)", "C3 · Basso DX (BR)", "C4 · Basso SX (BL)"]):
            self.combo_corner.addItem(lbl, i)
        self.combo_corner.currentIndexChanged.connect(self._on_corner_combo_changed)

        self.spin_cx = SmartDoubleSpinBox()
        self.spin_cy = SmartDoubleSpinBox()
        for s in (self.spin_cx, self.spin_cy):
            s.setStyleSheet("background: #1e293b; color: #ffffff; border: 1px solid #475569; border-radius: 4px;")
            s.valueChanged.connect(self._on_quad_spins_changed)

        self._configure_spinboxes_for_unit()
        left_lay.addWidget(self.coord_stack)

        # Group 4: Multi-Monitor Spanning Helper
        left_lay.addStretch()
        span_frame = QFrame()
        span_frame.setStyleSheet("background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 6px;")
        span_lay = QVBoxLayout(span_frame)
        span_lay.setContentsMargins(6, 6, 6, 6)
        span_lay.setSpacing(4)

        lbl_span_title = QLabel("🖥 MULTI-PROIETTORE & SPAN")
        lbl_span_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #38bdf8;")
        span_lay.addWidget(lbl_span_title)

        lbl_span_desc = QLabel("Per 2 o 3 proiettori affiancati, estendi il desktop nel sistema operativo e usa lo Span:")
        lbl_span_desc.setWordWrap(True)
        lbl_span_desc.setStyleSheet("font-size: 10px; color: #94a3b8;")
        span_lay.addWidget(lbl_span_desc)

        self.btn_span = QPushButton("Estendi su Tutti i Monitor Esterni (Span)")
        self.btn_span.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_span.setStyleSheet("background: #0284c7; color: #ffffff; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_span.clicked.connect(self._span_displays)
        span_lay.addWidget(self.btn_span)

        left_lay.addWidget(span_frame)
        body.addWidget(left_panel)

        # Right Column: Visual Stage Canvas
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        self.canvas = SurfaceCanvasWidget()
        right_panel.addWidget(self.canvas)

        hint_lbl = QLabel("💡 Mouse: trascina i vertici C1..C4 o il riquadro direttamente sul canvas. Con i pulsanti o le frecce usi il micro-nudge. Passa tra Pixel e Percentuale in qualsiasi momento.")
        hint_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic;")
        right_panel.addWidget(hint_lbl)

        body.addLayout(right_panel, stretch=1)
        main_layout.addLayout(body, stretch=1)

        # ── Dialog Footer ─────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(10)

        lbl_footer_info = QLabel("Le modifiche sono applicate in tempo reale al motore di riproduzione.")
        lbl_footer_info.setStyleSheet("font-size: 11px; color: #64748b;")
        footer.addWidget(lbl_footer_info)

        footer.addStretch()

        self.btn_close = QPushButton("Salva & Chiudi")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setFixedHeight(34)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #0369a1;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)

    # ── Unit Mode Conversion Helpers ──────────────────────────────────

    def _to_display_x(self, norm_x: float) -> float:
        if self._unit_mode == "px":
            return float(round(norm_x * self._output_res[0]))
        return round(norm_x * 100.0, 1)

    def _to_display_y(self, norm_y: float) -> float:
        if self._unit_mode == "px":
            return float(round(norm_y * self._output_res[1]))
        return round(norm_y * 100.0, 1)

    def _from_display_x(self, val: float) -> float:
        if self._unit_mode == "px":
            return max(0.0, min(1.0, val / max(1.0, float(self._output_res[0]))))
        return max(0.0, min(1.0, val / 100.0))

    def _from_display_y(self, val: float) -> float:
        if self._unit_mode == "px":
            return max(0.0, min(1.0, val / max(1.0, float(self._output_res[1]))))
        return max(0.0, min(1.0, val / 100.0))

    def _set_unit_mode(self, mode: str) -> None:
        if self._unit_mode == mode:
            return
        self._unit_mode = mode
        self.btn_unit_px.setChecked(mode == "px")
        self.btn_unit_pct.setChecked(mode == "percent")
        self.canvas.set_unit_mode(mode)
        self._configure_spinboxes_for_unit()
        self._load_active_surface_to_controls()

    def _configure_spinboxes_for_unit(self) -> None:
        self._updating_ui = True
        w, h = self._output_res
        if self._unit_mode == "px":
            self.spin_rx.setRange(0, w)
            self.spin_rx.setDecimals(0)
            self.spin_rx.setSuffix(" px")
            self.spin_rx.setSingleStep(1)

            self.spin_ry.setRange(0, h)
            self.spin_ry.setDecimals(0)
            self.spin_ry.setSuffix(" px")
            self.spin_ry.setSingleStep(1)

            self.spin_rw.setRange(1, w)
            self.spin_rw.setDecimals(0)
            self.spin_rw.setSuffix(" px")
            self.spin_rw.setSingleStep(1)

            self.spin_rh.setRange(1, h)
            self.spin_rh.setDecimals(0)
            self.spin_rh.setSuffix(" px")
            self.spin_rh.setSingleStep(1)

            self.spin_cx.setRange(0, w)
            self.spin_cx.setDecimals(0)
            self.spin_cx.setSuffix(" px")
            self.spin_cx.setSingleStep(1)

            self.spin_cy.setRange(0, h)
            self.spin_cy.setDecimals(0)
            self.spin_cy.setSuffix(" px")
            self.spin_cy.setSingleStep(1)
        else:
            for s in (self.spin_rx, self.spin_ry, self.spin_rw, self.spin_rh, self.spin_cx, self.spin_cy):
                s.setRange(0.0, 100.0)
                s.setDecimals(1)
                s.setSuffix(" %")
                s.setSingleStep(0.5)
        self._updating_ui = False

    # ── Internal State Helpers ────────────────────────────────────────

    def _get_active_surface(self) -> SurfaceDefinition:
        for s in self._surfaces:
            if s.surface_id == self._active_id:
                return s
        return self._surfaces[0]

    def _refresh_surface_list(self) -> None:
        self.list_surfaces.blockSignals(True)
        self.list_surfaces.clear()
        for idx, s in enumerate(self._surfaces):
            icon_str = "⬛" if s.mode == SurfaceMode.RECTANGLE.value else "⬡"
            item = QListWidgetItem(f"{icon_str}  {s.name}")
            item.setData(Qt.ItemDataRole.UserRole, s.surface_id)
            self.list_surfaces.addItem(item)
            if s.surface_id == self._active_id:
                self.list_surfaces.setCurrentItem(item)
        self.list_surfaces.blockSignals(False)

        # Disable delete for default surface
        self.btn_del.setEnabled(self._active_id != DEFAULT_SURFACE_ID)

    def _sync_controls_from_surface(self, s: SurfaceDefinition) -> None:
        """Update spinboxes from surface without touching layout or resetting canvas."""
        self._updating_ui = True
        if s.mode == SurfaceMode.RECTANGLE.value:
            self.spin_rx.setValue(self._to_display_x(s.x))
            self.spin_ry.setValue(self._to_display_y(s.y))
            self.spin_rw.setValue(self._to_display_x(s.w))
            self.spin_rh.setValue(self._to_display_y(s.h))
        else:
            c_pt = s.corners[self._active_corner]
            self.spin_cx.setValue(self._to_display_x(c_pt[0]))
            self.spin_cy.setValue(self._to_display_y(c_pt[1]))
        self._updating_ui = False

    def _load_active_surface_to_controls(self) -> None:
        self._updating_ui = True
        s = self._get_active_surface()

        self.edit_name.setText(s.name)
        is_rect = (s.mode == SurfaceMode.RECTANGLE.value)
        self.btn_mode_rect.setChecked(is_rect)
        self.btn_mode_quad.setChecked(not is_rect)

        # Clear coord layout
        while self.coord_lay.count():
            item = self.coord_lay.takeAt(0)
            if w := item.widget():
                w.setParent(None)

        if is_rect:
            self.coord_lay.addWidget(QLabel("Pos X:"), 0, 0)
            self.spin_rx.setValue(self._to_display_x(s.x))
            self.coord_lay.addWidget(self.spin_rx, 0, 1)

            self.coord_lay.addWidget(QLabel("Pos Y:"), 0, 2)
            self.spin_ry.setValue(self._to_display_y(s.y))
            self.coord_lay.addWidget(self.spin_ry, 0, 3)

            self.coord_lay.addWidget(QLabel("Larghezza:"), 1, 0)
            self.spin_rw.setValue(self._to_display_x(s.w))
            self.coord_lay.addWidget(self.spin_rw, 1, 1)

            self.coord_lay.addWidget(QLabel("Altezza:"), 1, 2)
            self.spin_rh.setValue(self._to_display_y(s.h))
            self.coord_lay.addWidget(self.spin_rh, 1, 3)
        else:
            self.coord_lay.addWidget(QLabel("Angolo Attivo:"), 0, 0)
            self.combo_corner.setCurrentIndex(self._active_corner)
            self.coord_lay.addWidget(self.combo_corner, 0, 1, 1, 3)

            c_pt = s.corners[self._active_corner]
            self.coord_lay.addWidget(QLabel("Corner X:"), 1, 0)
            self.spin_cx.setValue(self._to_display_x(c_pt[0]))
            self.coord_lay.addWidget(self.spin_cx, 1, 1)

            self.coord_lay.addWidget(QLabel("Corner Y:"), 1, 2)
            self.spin_cy.setValue(self._to_display_y(c_pt[1]))
            self.coord_lay.addWidget(self.spin_cy, 1, 3)

        self.canvas.set_surfaces(self._surfaces, self._active_id)
        self.canvas.set_active_corner(self._active_corner)
        self._sync_to_output()
        self._updating_ui = False

    def _sync_to_output(self) -> None:
        """Propagate current surface state live to the live OutputWindow."""
        self._output.set_surfaces(self._surfaces)
        if self._output.is_calibration_guides_visible():
            self._output.set_calibration_guides_visible(True, active_surface_id=self._active_id)
        self.surfaces_changed.emit(self._surfaces)

    # ── Slots ─────────────────────────────────────────────────────────

    @Slot(int)
    def _on_surface_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._surfaces):
            return
        self._active_id = self._surfaces[row].surface_id
        self.btn_del.setEnabled(self._active_id != DEFAULT_SURFACE_ID)
        self._load_active_surface_to_controls()

    @Slot(str)
    def _on_name_changed(self, text: str) -> None:
        if self._updating_ui:
            return
        s = self._get_active_surface()
        s.name = text.strip() or "Superficie"
        self._refresh_surface_list()
        self.canvas.update()
        self._sync_to_output()

    def _set_surface_mode(self, mode: str) -> None:
        s = self._get_active_surface()
        if s.mode == mode:
            return
        s.mode = mode
        if mode == SurfaceMode.QUAD.value:
            s.sync_quad_from_rect()
        else:
            s.sync_rect_from_quad()
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

    @Slot(int)
    def _apply_preset(self, index: int) -> None:
        preset = self.combo_preset.currentData()
        if not preset or self._updating_ui:
            return
        s = self._get_active_surface()
        s.mode = preset.get("mode", SurfaceMode.RECTANGLE.value)
        s.x = preset.get("x", 0.0)
        s.y = preset.get("y", 0.0)
        s.w = preset.get("w", 1.0)
        s.h = preset.get("h", 1.0)
        s.sync_quad_from_rect()
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

    @Slot()
    def _on_rect_spins_changed(self) -> None:
        if self._updating_ui:
            return
        s = self._get_active_surface()
        s.x = self._from_display_x(self.spin_rx.value())
        s.y = self._from_display_y(self.spin_ry.value())
        s.w = self._from_display_x(self.spin_rw.value())
        s.h = self._from_display_y(self.spin_rh.value())
        s.sync_quad_from_rect()
        self.canvas.update()
        self._sync_to_output()

    @Slot(int)
    def _on_corner_combo_changed(self, index: int) -> None:
        self._active_corner = index
        self.canvas.set_active_corner(index)
        s = self._get_active_surface()
        c_pt = s.corners[index]
        self._updating_ui = True
        self.spin_cx.setValue(self._to_display_x(c_pt[0]))
        self.spin_cy.setValue(self._to_display_y(c_pt[1]))
        self._updating_ui = False

    @Slot()
    def _on_quad_spins_changed(self) -> None:
        if self._updating_ui:
            return
        s = self._get_active_surface()
        nx = self._from_display_x(self.spin_cx.value())
        ny = self._from_display_y(self.spin_cy.value())
        s.set_corner(self._active_corner, nx, ny)
        self.canvas.update()
        self._sync_to_output()

    def _nudge_active(self, dx_step: int, dy_step: int) -> None:
        """Nudge active element by discrete steps (1px or 0.2%)."""
        s = self._get_active_surface()
        w, h = self._output_res
        if self._unit_mode == "px":
            dx_norm = dx_step / max(1.0, float(w))
            dy_norm = dy_step / max(1.0, float(h))
        else:
            dx_norm = dx_step * 0.002
            dy_norm = dy_step * 0.002

        if s.mode == SurfaceMode.QUAD.value:
            s.nudge_corner(self._active_corner, dx_norm, dy_norm)
        else:
            s.nudge_rect(dx_norm, dy_norm)
        self._sync_controls_from_surface(s)
        self.canvas.update()
        self._sync_to_output()

    @Slot(SurfaceDefinition)
    def _on_canvas_surface_modified(self, modified_surface: SurfaceDefinition) -> None:
        self._sync_controls_from_surface(modified_surface)
        self._sync_to_output()

    @Slot(int)
    def _on_canvas_corner_selected(self, corner_idx: int) -> None:
        self._active_corner = corner_idx
        s = self._get_active_surface()
        if s.mode == SurfaceMode.QUAD.value:
            self._updating_ui = True
            self.combo_corner.setCurrentIndex(corner_idx)
            c_pt = s.corners[corner_idx]
            self.spin_cx.setValue(self._to_display_x(c_pt[0]))
            self.spin_cy.setValue(self._to_display_y(c_pt[1]))
            self._updating_ui = False

    @Slot()
    def _add_surface(self) -> None:
        new_idx = len(self._surfaces) + 1
        col = SURFACE_COLORS[(new_idx - 1) % len(SURFACE_COLORS)]
        new_surf = SurfaceDefinition(
            surface_id=f"surface_{new_idx}",
            name=f"Superficie {new_idx}",
            mode=SurfaceMode.RECTANGLE.value,
            x=0.1, y=0.1, w=0.5, h=0.5,
            color=col,
        )
        self._surfaces.append(new_surf)
        self._active_id = new_surf.surface_id
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

    @Slot()
    def _duplicate_surface(self) -> None:
        src = self._get_active_surface()
        dup = src.clone()
        dup.surface_id = f"{src.surface_id}_copy_{len(self._surfaces)}"
        dup.name = f"{src.name} (Copia)"
        dup.x = min(0.9, dup.x + 0.05)
        dup.y = min(0.9, dup.y + 0.05)
        dup.sync_quad_from_rect()
        self._surfaces.append(dup)
        self._active_id = dup.surface_id
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

    @Slot()
    def _delete_surface(self) -> None:
        if self._active_id == DEFAULT_SURFACE_ID or len(self._surfaces) <= 1:
            return
        self._surfaces = [s for s in self._surfaces if s.surface_id != self._active_id]
        self._active_id = self._surfaces[0].surface_id
        self._refresh_surface_list()
        self._load_active_surface_to_controls()

    @Slot()
    def _toggle_live_guides(self) -> None:
        is_on = self.btn_live_guides.isChecked()
        self._output.set_calibration_guides_visible(is_on, active_surface_id=self._active_id)

    @Slot()
    def _span_displays(self) -> None:
        success = self._output.span_all_screens()
        if success:
            w, h = self._output.get_output_resolution()
            self._output_res = (w, h)
            self.lbl_res_badge.setText(f"🖥 {w}×{h} px (Span)")
            self.canvas.set_output_resolution(w, h)
            self._configure_spinboxes_for_unit()
            self._load_active_surface_to_controls()
            QMessageBox.information(
                self,
                "Multi-Monitor Esteso",
                f"La finestra di uscita è stata estesa su tutti i monitor ({w}×{h} px).\n"
                "I preset 'Doppio Proiettore' mapperanno automaticamente ciascuna metà dello schermo!",
            )
        else:
            QMessageBox.information(
                self,
                "Monitor Singolo Rilevato",
                "È presente un solo schermo collegato. Per usare lo spanning multi-proiettore, collega un secondo monitor/proiettore alle uscite HDMI o DisplayPort.",
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_F7:
            self.btn_live_guides.setChecked(not self.btn_live_guides.isChecked())
            self._toggle_live_guides()
            event.accept()
            return
        super().keyPressEvent(event)
