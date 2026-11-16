"""Polygon mask editor for still images.

BlindCue never rewrites media files. This dialog only produces a list of
normalised points that the output window and the Pre-Viz monitor use as a
clip path, so an image can be cut to an irregular shape (a silhouette, a
logo with holes, a torn-paper edge) without leaving the application.

Coordinates are normalised to the **visible frame** (the image after the
current crop), because that is exactly what the operator sees in the
Pre-Viz monitor. Rotation is applied afterwards, so the polygon is always
drawn on an upright image.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from models.cue import (
    MASK_MAX_FEATHER,
    MASK_MAX_POINTS,
    MASK_MIN_POINTS,
    sanitize_mask_polygon,
)
from ui.layout_math import feathered_mask_image, polygon_path_from_normalized

# Hit radius for grabbing an existing vertex, in widget pixels.
_HANDLE_RADIUS = 9.0
# 8× is enough to place a vertex on a single pixel of a 4K still without
# making the image unreadable; beyond that the operator just loses orientation.
_MAX_ZOOM = 8.0


def _cropped_pixmap(pixmap: QPixmap, crop: dict | None) -> QPixmap:
    """Return *pixmap* restricted to the cue crop rectangle (visible frame)."""
    if pixmap.isNull():
        return pixmap
    c = crop or {}
    cx = max(0.0, min(0.99, float(c.get("x", 0.0))))
    cy = max(0.0, min(0.99, float(c.get("y", 0.0))))
    cw = max(0.01, min(1.0 - cx, float(c.get("w", 1.0))))
    ch = max(0.01, min(1.0 - cy, float(c.get("h", 1.0))))
    if cx <= 0.0001 and cy <= 0.0001 and cw >= 0.9999 and ch >= 0.9999:
        return pixmap
    px = round(pixmap.width() * cx)
    py = round(pixmap.height() * cy)
    pw = max(1, round(pixmap.width() * cw))
    ph = max(1, round(pixmap.height() * ch))
    return pixmap.copy(px, py, min(pw, pixmap.width() - px), min(ph, pixmap.height() - py))


class _MaskCanvas(QWidget):
    """Draw the mask: click to add a point, drag to move, right-click to delete.

    The polygon is intentionally made of **straight segments**: the clip path is
    produced by :func:`polygon_path_from_normalized`, shared with the projector
    output and the Pre-Viz monitor. Bezier handles would need extra data in the
    cue model and the same curve math in two painters, which is not worth the
    live risk for a tool meant to be fast and predictable.
    """

    changed = Signal()

    def __init__(
        self,
        pixmap: QPixmap,
        points: list[list[float]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the canvas for *pixmap* with an optional existing polygon."""
        super().__init__(parent)
        self._pixmap = pixmap
        self._points: list[list[float]] = [list(p) for p in (points or [])]
        self._drag_index: int | None = None
        self._hover_index: int | None = None
        # Cursor position in widget space: drives the rubber-band preview so the
        # shape being drawn is visible before the next click.
        self._cursor: QPointF | None = None
        # View transform (never touches the stored points).
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._pan_anchor: tuple[QPointF, QPointF] | None = None
        # Soft edge, normalised to the frame's longest side (0 = hard cut).
        self._feather = 0.0
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── Geometry helpers ──────────────────────────────────────────────
    def _base_image_rect(self) -> QRectF:
        """Return the letterboxed rectangle where the image would be at 1:1."""
        if self._pixmap.isNull():
            return QRectF()
        area_w = max(1.0, float(self.width()))
        area_h = max(1.0, float(self.height()))
        src_ar = self._pixmap.width() / max(1, self._pixmap.height())
        if area_w / area_h >= src_ar:
            h = area_h
            w = h * src_ar
        else:
            w = area_w
            h = w / src_ar
        return QRectF((area_w - w) / 2.0, (area_h - h) / 2.0, w, h)

    def _image_rect(self) -> QRectF:
        """Return the painted rectangle after zoom and pan.

        Zoom/pan are a pure *view* transform: the stored points stay normalised,
        so zooming never alters the selection the operator is drawing.
        """
        base = self._base_image_rect()
        if base.isEmpty():
            return base
        w = base.width() * self._zoom
        h = base.height() * self._zoom
        cx = base.center().x() + self._pan.x()
        cy = base.center().y() + self._pan.y()
        return QRectF(cx - w / 2.0, cy - h / 2.0, w, h)

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        """Zoom in/out keeping *anchor* (widget coords) fixed under the cursor."""
        new_zoom = min(_MAX_ZOOM, max(1.0, float(zoom)))
        base = self._base_image_rect()
        if base.isEmpty():
            self._zoom = new_zoom
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        old = self._image_rect()
        # Normalised position under the anchor before the zoom change.
        nx = (anchor.x() - old.x()) / max(1.0, old.width())
        ny = (anchor.y() - old.y()) / max(1.0, old.height())
        self._zoom = new_zoom
        w = base.width() * new_zoom
        h = base.height() * new_zoom
        cx = anchor.x() + w / 2.0 - nx * w
        cy = anchor.y() + h / 2.0 - ny * h
        self._pan = QPointF(cx - base.center().x(), cy - base.center().y())
        self._clamp_pan()
        self.update()

    def zoom_reset(self) -> None:
        """Return to the full image (zoom 1:1, no pan)."""
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def zoom_percent(self) -> int:
        """Current zoom as a percentage, for the dialog label."""
        return int(round(self._zoom * 100.0))

    def _clamp_pan(self) -> None:
        """Keep the zoomed image covering the widget instead of drifting away."""
        base = self._base_image_rect()
        if base.isEmpty():
            self._pan = QPointF(0.0, 0.0)
            return
        max_x = max(0.0, (base.width() * self._zoom - base.width()) / 2.0)
        max_y = max(0.0, (base.height() * self._zoom - base.height()) / 2.0)
        self._pan = QPointF(
            min(max_x, max(-max_x, self._pan.x())),
            min(max_y, max(-max_y, self._pan.y())),
        )

    def _normalize(self, pos: QPointF) -> list[float]:
        """Convert a widget position into normalised (0..1) image coordinates."""
        rect = self._image_rect()
        if rect.isEmpty():
            return [0.0, 0.0]
        x = (pos.x() - rect.x()) / rect.width()
        y = (pos.y() - rect.y()) / rect.height()
        return [round(min(1.0, max(0.0, x)), 4), round(min(1.0, max(0.0, y)), 4)]

    def _denormalize(self, point: list[float]) -> QPointF:
        """Convert a normalised point back into widget coordinates."""
        rect = self._image_rect()
        return QPointF(
            rect.x() + float(point[0]) * rect.width(),
            rect.y() + float(point[1]) * rect.height(),
        )

    def _hit_index(self, pos: QPointF) -> int | None:
        """Return the index of the vertex under *pos*, if any."""
        for idx, point in enumerate(self._points):
            center = self._denormalize(point)
            if math.hypot(center.x() - pos.x(), center.y() - pos.y()) <= _HANDLE_RADIUS:
                return idx
        return None

    # ── Public API ────────────────────────────────────────────────────
    def points(self) -> list[list[float]]:
        """Return the current polygon as sanitised normalised points."""
        return sanitize_mask_polygon(self._points)

    def set_feather(self, feather: float) -> None:
        """Set the soft edge used by the dim overlay so the preview is truthful."""
        self._feather = min(MASK_MAX_FEATHER, max(0.0, float(feather)))
        self.update()

    def clear(self) -> None:
        """Remove every vertex."""
        self._points = []
        self._drag_index = None
        self._hover_index = None
        self.changed.emit()
        self.update()

    # ── Mouse interaction ─────────────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Add, grab, delete a vertex, or start panning with the middle button."""
        pos = event.position()
        if event.button() == Qt.MouseButton.MiddleButton:
            # Pan without touching the selection: the view transform is separate
            # from the normalised points, so nothing can be lost while panning.
            self._pan_anchor = (pos, QPointF(self._pan))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        hit = self._hit_index(pos)
        if event.button() == Qt.MouseButton.RightButton:
            # A mask needs three vertices: never let a stray right-click wipe the
            # whole selection. To start over the operator uses "Svuota".
            if hit is not None and len(self._points) > MASK_MIN_POINTS:
                self._points.pop(hit)
                self._hover_index = None
                self.changed.emit()
                self.update()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if hit is not None:
            self._drag_index = hit
            return
        if len(self._points) >= MASK_MAX_POINTS:
            return
        self._points.append(self._normalize(pos))
        self._drag_index = len(self._points) - 1
        self.changed.emit()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Drag the grabbed vertex, pan the view, or track the cursor for preview."""
        pos = event.position()
        self._cursor = pos
        if self._pan_anchor is not None:
            start, start_pan = self._pan_anchor
            self._pan = QPointF(
                start_pan.x() + (pos.x() - start.x()),
                start_pan.y() + (pos.y() - start.y()),
            )
            self._clamp_pan()
        elif self._drag_index is not None and self._drag_index < len(self._points):
            self._points[self._drag_index] = self._normalize(pos)
        else:
            hit = self._hit_index(pos)
            if hit != self._hover_index:
                self._hover_index = hit
            self.setCursor(
                Qt.CursorShape.OpenHandCursor if hit is not None else Qt.CursorShape.CrossCursor
            )
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Drop the grabbed vertex or finish panning."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_index = None
            self.changed.emit()
            self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Zoom in/out around the cursor with the mouse wheel."""
        delta = event.angleDelta().y()
        if not delta:
            return
        step = 1.15 if delta > 0 else (1.0 / 1.15)
        self.set_zoom(self._zoom * step, event.position())
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Keep the panned image inside the widget after a resize."""
        super().resizeEvent(event)
        self._clamp_pan()

    def leaveEvent(self, _event) -> None:  # noqa: N802
        """Clear hover/rubber-band state when the pointer leaves the canvas."""
        self._cursor = None
        self._hover_index = None
        if self._pan_anchor is None:
            self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    # ── Painting ──────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:  # noqa: N802
        """Paint the image, dim what falls outside the polygon, then the handles."""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), QColor("#0b1118"))

            rect = self._image_rect()
            if rect.isEmpty():
                painter.setPen(QColor("#f87171"))
                painter.drawText(
                    self.rect(), Qt.AlignmentFlag.AlignCenter, "Immagine non disponibile"
                )
                return

            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))

            closed_path = polygon_path_from_normalized(
                self._points, rect.x(), rect.y(), rect.width(), rect.height()
            )
            if len(self._points) >= 3:
                # Dim what will be cut away so the result is obvious. With a soft
                # edge the dim boundary follows the same blurred alpha mask used
                # by the projector, so the preview is truthful (WYSIWYG).
                feather_px = self._feather * max(rect.width(), rect.height())
                mask = (
                    feathered_mask_image(self._points, int(rect.width()), int(rect.height()), feather_px)
                    if feather_px >= 1.0
                    else None
                )
                if mask is not None and not mask.isNull():
                    # Dim only what the mask cuts away. The compositing must
                    # happen on a scratch image: a DestinationOut drawn straight
                    # on the widget erases the picture under the selection.
                    overlay = QImage(
                        mask.size(), QImage.Format.Format_ARGB32_Premultiplied
                    )
                    overlay.fill(QColor(0, 0, 0, 150))
                    dim = QPainter(overlay)
                    try:
                        dim.setCompositionMode(
                            QPainter.CompositionMode.CompositionMode_DestinationOut
                        )
                        dim.drawImage(0, 0, mask)
                    finally:
                        dim.end()
                    painter.drawImage(rect, overlay)
                    # Tint only the ramp band, i.e. where the fade actually
                    # happens: the inside of the mask keeps showing the real
                    # image so the operator judges the cut on the picture.
                    band = QPen(QColor(0, 229, 255, 80), max(2.0, feather_px))
                    band.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(band)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(closed_path)
                else:
                    outside = QPainterPath()
                    outside.addRect(rect)
                    outside = outside.subtracted(closed_path)
                    painter.fillPath(outside, QColor(0, 0, 0, 150))
                # No fill inside the polygon: a flat tint would hide the image
                # exactly where the operator needs to look.
                painter.setPen(QPen(QColor("#00e5ff"), 2.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(closed_path)
            elif len(self._points) == 2:
                # Open polyline: the shape is not a polygon yet, so no dimming.
                painter.setPen(QPen(QColor("#00e5ff"), 2.0))
                painter.drawLine(
                    self._denormalize(self._points[0]), self._denormalize(self._points[1])
                )

            self._paint_rubber_band(painter)
            self._paint_handles(painter)
            self._paint_zoom_badge(painter)
        finally:
            # An open QPainter on a widget paint event crashes the whole process:
            # always close it, even when an early branch returns.
            painter.end()

    def _paint_rubber_band(self, painter: QPainter) -> None:
        """Preview the next segment(s) with a dashed line following the cursor."""
        if self._cursor is None or self._drag_index is not None or not self._points:
            return
        last = self._denormalize(self._points[-1])
        pen = QPen(QColor(0, 229, 255, 160), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(last, self._cursor)
        if len(self._points) >= 2:
            # Closing hint: shows where the polygon will be sealed.
            painter.setPen(QPen(QColor(0, 229, 255, 90), 1.0, Qt.PenStyle.DotLine))
            painter.drawLine(self._cursor, self._denormalize(self._points[0]))

    def _paint_zoom_badge(self, painter: QPainter) -> None:
        """Show the zoom level so the operator always knows the current scale."""
        if self._zoom <= 1.001:
            return
        text = f"zoom {self.zoom_percent()}%  ·  rotellina = zoom · centrale = sposta · Ctrl+0 = 100%"
        painter.setPen(QColor("#e2e8f0"))
        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 16
        height = metrics.height() + 8
        painter.setBrush(QColor(11, 17, 24, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(8.0, 8.0, float(width), float(height)), 4.0, 4.0)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(
            QRectF(16.0, 8.0, float(width), float(height)),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )

    def _paint_handles(self, painter: QPainter) -> None:
        """Draw every vertex; the first one is amber, the hovered one is ringed."""
        for idx, point in enumerate(self._points):
            center = self._denormalize(point)
            hovered = idx == self._hover_index
            painter.setPen(QPen(QColor("#0b1118"), 1.5))
            painter.setBrush(QColor("#fbbf24") if idx == 0 else QColor("#ffffff"))
            radius = 6.5 if hovered else 5.0
            painter.drawEllipse(center, radius, radius)
            if hovered:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#00e5ff"), 1.2))
                painter.drawEllipse(center, radius + 3.0, radius + 3.0)


class ImageMaskDialog(QDialog):
    """Modal editor returning a polygon mask for one image cue."""

    def __init__(
        self,
        image_path: str,
        crop: dict | None = None,
        points: list[list[float]] | None = None,
        feather: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        """Load *image_path*, show the existing *points* and let the operator edit them."""
        super().__init__(parent)
        self.setWindowTitle("Maschera poligonale immagine")
        self.setModal(True)
        self.resize(860, 560)

        source = QImage(image_path)
        pixmap = QPixmap.fromImage(source) if not source.isNull() else QPixmap()
        self._canvas = _MaskCanvas(_cropped_pixmap(pixmap, crop), points, self)
        self._canvas.set_feather(feather)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Clic per aggiungere un punto · trascina un punto per spostarlo · clic destro per eliminarlo (minimo 3 punti).\n"
            "Rotellina del mouse = zoom sul cursore · trascina con il tasto centrale per spostarti · Ctrl+0 = 100%.\n"
            "La linea tratteggiata segue il cursore e mostra il lato successivo: il poligono si chiude da solo.\n"
            "Il file originale non viene mai modificato: la maschera viene salvata nel progetto."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(hint)
        layout.addWidget(self._canvas, 1)

        row = QHBoxLayout()
        self._lbl_count = QLabel("0 punti")
        self._lbl_count.setStyleSheet("color: #64748b; font-family: monospace; font-size: 11px;")
        btn_clear = QPushButton("Svuota")
        btn_clear.clicked.connect(self._canvas.clear)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedWidth(30)
        btn_zoom_out.setToolTip("Riduci zoom (Ctrl+−)")
        btn_zoom_out.clicked.connect(lambda: self._canvas.set_zoom(self._canvas._zoom / 1.25))
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(30)
        btn_zoom_in.setToolTip("Aumenta zoom (Ctrl++)")
        btn_zoom_in.clicked.connect(lambda: self._canvas.set_zoom(self._canvas._zoom * 1.25))
        btn_zoom_reset = QPushButton("100%")
        btn_zoom_reset.setToolTip("Torna all'immagine intera (Ctrl+0)")
        btn_zoom_reset.clicked.connect(self._canvas.zoom_reset)

        row.addWidget(self._lbl_count)
        row.addStretch()
        row.addWidget(btn_zoom_out)
        row.addWidget(btn_zoom_in)
        row.addWidget(btn_zoom_reset)
        row.addSpacing(16)
        row.addWidget(btn_clear)
        layout.addLayout(row)

        # ── Soft edge (feather) ───────────────────────────────────────
        feather_row = QHBoxLayout()
        lbl_feather = QLabel("Bordo sfumato")
        lbl_feather.setToolTip(
            "Ammorbidisce il contorno della maschera: 0 = taglio netto.\n"
            "La sfumatura è proporzionata al frame, quindi identica sul proiettore e in Pre-Viz."
        )
        self._slider_feather = QSlider(Qt.Orientation.Horizontal)
        self._slider_feather.setRange(0, 100)
        self._slider_feather.setValue(self._feather_to_slider(feather))
        self._slider_feather.setToolTip(lbl_feather.toolTip())
        self._lbl_feather = QLabel("")
        self._lbl_feather.setMinimumWidth(120)
        self._lbl_feather.setStyleSheet("color: #64748b; font-family: monospace; font-size: 11px;")
        self._slider_feather.valueChanged.connect(self._on_feather_changed)
        feather_row.addWidget(lbl_feather)
        feather_row.addWidget(self._slider_feather, 1)
        feather_row.addWidget(self._lbl_feather)
        layout.addLayout(feather_row)
        self._refresh_feather_label()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Applica")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annulla")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons

        # Zoom shortcuts work wherever the focus is inside the dialog, so the
        # operator never has to click the canvas first (and never loses a
        # half-drawn polygon by clicking outside it).
        QShortcut(QKeySequence.StandardKey.ZoomIn, self, lambda: self._nudge_zoom(1.25))
        QShortcut(QKeySequence("Ctrl+="), self, lambda: self._nudge_zoom(1.25))
        QShortcut(QKeySequence.StandardKey.ZoomOut, self, lambda: self._nudge_zoom(1.0 / 1.25))
        QShortcut(QKeySequence("Ctrl+0"), self, self._canvas.zoom_reset)

        self._canvas.changed.connect(self._refresh_count)
        self._refresh_count()

    def _nudge_zoom(self, factor: float) -> None:
        """Zoom around the canvas centre (keyboard / buttons)."""
        self._canvas.set_zoom(self._canvas._zoom * factor)

    @staticmethod
    def _feather_to_slider(feather: float) -> int:
        """Map a normalised feather to the 0–100 slider."""
        return int(round(max(0.0, min(MASK_MAX_FEATHER, float(feather))) / MASK_MAX_FEATHER * 100.0))

    def _slider_to_feather(self) -> float:
        """Current slider position as a normalised feather."""
        return MASK_MAX_FEATHER * (self._slider_feather.value() / 100.0)

    def _on_feather_changed(self, _value: int) -> None:
        """Keep the canvas preview and the numeric readout in sync."""
        self._canvas.set_feather(self._slider_to_feather())
        self._refresh_feather_label()

    def _refresh_feather_label(self) -> None:
        """Show the feather in pixels at 1920 px, which is what the eye expects."""
        px = self._slider_to_feather() * 1920.0
        self._lbl_feather.setText(f"{px:.0f} px @1920" if px >= 0.5 else "netto")

    def _refresh_count(self) -> None:
        """Keep the vertex counter in sync and enable OK only for a real polygon."""
        count = len(self._canvas.points())
        self._lbl_count.setText(f"{count} punti" if count else "Nessun punto")
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(count >= 3)

    def mask_points(self) -> list[list[float]]:
        """Return the edited polygon (empty list = no mask)."""
        return self._canvas.points()

    def mask_feather(self) -> float:
        """Return the edited soft-edge width (normalised, 0.0 = hard cut)."""
        return self._slider_to_feather()
