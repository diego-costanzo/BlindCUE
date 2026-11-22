"""16:9 WYSIWYG Pre-Viz monitor with strict canvas clipping, interactive position drag, and 8 crop handles."""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QVideoFrame, QVideoSink
from PySide6.QtWidgets import QSizePolicy, QWidget

from models.cue import MediaType
from ui.layout_math import (
    compute_media_frame_geometry,
    feathered_mask_image,
    polygon_path_from_normalized,
)
from ui.tappo_pattern import is_default_tappo_path, render_default_tappo_pixmap
from ui.theme import DEFAULT_LOGO_PATH


class StudioPreviewMonitor(QWidget):
    """16:9 WYSIWYG studio preview monitor that mirrors live output.

    Renders Layer 0 (Tappo) underneath when idle, and places video or images on top
    with pixel-accurate scale, crop, position, and opacity.
    STRICTLY CLIPPED to the 16:9 canvas so media NEVER overflows into the director UI.
    Provides interactive mouse dragging for position AND 8 crop handles for direct cropping!
    """

    position_changed = Signal(float, float)  # pos_x, pos_y
    crop_changed = Signal(float, float, float, float)  # crop_l, crop_r, crop_t, crop_b
    video_resolution_detected = Signal(int, int)  # natural width, height
    video_frame_changed = Signal(QImage)  # emits freshly decoded Pre-Viz video frame

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the pre-viz monitor with crop and position handles."""
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000000; border-radius: 4px;")
        self.setMouseTracking(True)

        self._layer0_pixmap: QPixmap | None = None
        self._layer0_path: str = str(DEFAULT_LOGO_PATH)
        self._layer0_is_default: bool = True
        self._layer0_pattern_cache: tuple[int, int, float, QPixmap] | None = None
        self._image_pixmap: QPixmap | None = None
        self._image_qimage: QImage | None = None
        self._video_frame_image: QImage | None = None
        self._active_media_type: MediaType | None = None

        self._scale: float = 1.0
        self._position_x: float = 0.0
        self._position_y: float = 0.0
        self._opacity: float = 1.0
        self._aspect_ratio: str | None = None
        self._crop: dict = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._rotation: float = 0.0
        self._mask_polygon: list[list[float]] = []
        # Soft edge of the mask, normalised to the frame (0 = hard cut).
        self._mask_feather: float = 0.0
        self._last_video_res: tuple[int, int] = (0, 0)

        # Drag state (position & 8 crop handles)
        self._drag_mode: str | None = None
        self._drag_start_pt: QPoint = QPoint()
        self._drag_start_pos_x: float = 0.0
        self._drag_start_pos_y: float = 0.0
        self._drag_start_crop_l: float = 0.0
        self._drag_start_crop_r: float = 0.0
        self._drag_start_crop_t: float = 0.0
        self._drag_start_crop_b: float = 0.0

        # Cached rendered geometries for hit-testing
        self._rendered_media_rect: QRectF | None = None
        self._full_media_rect: QRectF | None = None

        # Native Wayland video sink for zero-leak, zero-overflow preview
        self._video_sink = QVideoSink(self)
        self._video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

        # Studio Audio state (calm, zero blinking)
        self._audio_is_playing: bool = False

    @Slot(QVideoFrame)
    def _on_video_frame_changed(self, frame: QVideoFrame) -> None:
        """Receive hardware frame from QtMultimedia and update canvas smoothly."""
        if frame.isValid():
            img = frame.toImage()
            self._video_frame_image = img
            res = (img.width(), img.height())
            if res[0] > 0 and res[1] > 0 and res != self._last_video_res:
                self._last_video_res = res
                self.video_resolution_detected.emit(res[0], res[1])
            self.video_frame_changed.emit(img)
            self.update()

    def current_video_frame(self) -> QImage | None:
        """Return the last decoded video frame (``None`` before playback)."""
        return self._video_frame_image

    def clear_video_frame(self) -> None:
        """Forget the stored frame (called when a cue is unloaded)."""
        self._video_frame_image = None

    def get_video_sink(self) -> QVideoSink:
        """Sink where QMediaPlayer pushes decoded frames for this monitor."""
        return self._video_sink

    def get_video_widget(self) -> QVideoSink:
        """Backward compatibility alias for QMediaPlayer.setVideoOutput()."""
        return self._video_sink

    def set_audio_playing(self, is_playing: bool) -> None:
        """Toggle calm studio audio indicator."""
        self._audio_is_playing = is_playing
        self.update()

    def set_layer0_image(self, file_path: str | None) -> None:
        """Set the Layer 0 background shown behind every previewed cue."""
        self._layer0_pattern_cache = None
        self._layer0_is_default = is_default_tappo_path(file_path)
        if self._layer0_is_default:
            self._layer0_path = str(file_path or DEFAULT_LOGO_PATH)
            self._layer0_pixmap = None
        elif file_path and os.path.isfile(file_path):
            self._layer0_path = file_path
            self._layer0_pixmap = QPixmap(file_path)
        else:
            self._layer0_pixmap = None
        self.update()

    def get_canvas_rect(self) -> QRect:
        """Calculate the 16:9 inner canvas rectangle inside the monitor widget."""
        w, h = max(1, self.width()), max(1, self.height())
        target_ar = 16.0 / 9.0
        curr_ar = w / h

        if curr_ar > target_ar:
            ch = h
            cw = int(h * target_ar)
            cx = (w - cw) // 2
            cy = 0
        else:
            cw = w
            ch = int(w / target_ar)
            cx = 0
            cy = (h - ch) // 2

        return QRect(cx, cy, cw, ch)

    def show_video(self, scale: float = 1.0, crop: dict | None = None,
                   pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                   aspect_ratio: str | None = None, rotation: float = 0.0) -> None:
        """Switch the monitor to video mode and apply the cue geometry."""
        self._active_media_type = MediaType.VIDEO
        self._last_video_res = (0, 0)
        self._mask_polygon = []  # masks are an image-only transform
        self._mask_feather = 0.0
        self.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, aspect_ratio=aspect_ratio, rotation=rotation,
        )

    def update_video_layout(self, scale: float = 1.0, crop: dict | None = None,
                            pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                            aspect_ratio: str | None = None, rotation: float = 0.0) -> None:
        """Update geometry/opacity/rotation without changing the active media type."""
        self._scale = scale
        self._crop = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._position_x = pos_x
        self._position_y = pos_y
        self._opacity = opacity
        self._aspect_ratio = aspect_ratio
        self._rotation = rotation
        self.update()

    def set_opacity(self, opacity: float) -> None:
        """Update rendered preview opacity without resetting media/position."""
        clamped = max(0.0, min(1.0, float(opacity)))
        if abs(self._opacity - clamped) >= 0.002:
            self._opacity = clamped
            self.update()

    def show_image(self, file_path: str, scale: float = 1.0, crop: dict | None = None,
                   pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0,
                   aspect_ratio: str | None = None, rotation: float = 0.0,
                   mask_polygon: list[list[float]] | None = None,
                   mask_feather: float = 0.0) -> None:
        """Switch the monitor to image mode and load *file_path*."""
        self._active_media_type = MediaType.IMAGE
        self._scale = scale
        self._crop = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._position_x = pos_x
        self._position_y = pos_y
        self._opacity = opacity
        self._aspect_ratio = aspect_ratio
        self._rotation = rotation
        self._mask_polygon = list(mask_polygon or [])
        self._mask_feather = float(mask_feather or 0.0)
        if os.path.isfile(file_path):
            self._image_pixmap = QPixmap(file_path)
            self._image_qimage = self._image_pixmap.toImage() if not self._image_pixmap.isNull() else None
        else:
            self._image_pixmap = None
            self._image_qimage = None
        self.update()

    def show_audio(self) -> None:
        """Switch the monitor to audio mode (waveform-only placeholder)."""
        self._active_media_type = MediaType.AUDIO
        self.update()

    def clear_media(self) -> None:
        """Reset the monitor to an empty state (no image, frame or audio)."""
        self._active_media_type = None
        self._image_pixmap = None
        self._image_qimage = None
        self._video_frame_image = None
        self._rendered_media_rect = None
        self._full_media_rect = None
        self._audio_is_playing = False
        self._rotation = 0.0
        self._mask_polygon = []
        self._mask_feather = 0.0
        self.update()

    def _hit_test(self, pt: QPoint) -> str | None:
        """Determine if pt is over one of the 8 crop handles or inside the media."""
        if not self._rendered_media_rect or self._rendered_media_rect.isEmpty():
            return None

        r = self._rendered_media_rect
        margin = 9.0

        handles = {
            "top_left": r.topLeft(),
            "top_right": r.topRight(),
            "bottom_left": r.bottomLeft(),
            "bottom_right": r.bottomRight(),
            "top": QPointF(r.center().x(), r.top()),
            "bottom": QPointF(r.center().x(), r.bottom()),
            "left": QPointF(r.left(), r.center().y()),
            "right": QPointF(r.right(), r.center().y()),
        }

        for name in ("top_left", "top_right", "bottom_left", "bottom_right", "top", "bottom", "left", "right"):
            hp = handles[name]
            if abs(pt.x() - hp.x()) <= margin and abs(pt.y() - hp.y()) <= margin:
                return name

        if r.contains(QPointF(pt)):
            return "position"

        return None

    @staticmethod
    def _cursor_for_mode(mode: str | None) -> Qt.CursorShape:
        if mode in ("top_left", "bottom_right"):
            return Qt.CursorShape.SizeFDiagCursor
        if mode in ("top_right", "bottom_left"):
            return Qt.CursorShape.SizeBDiagCursor
        if mode in ("top", "bottom"):
            return Qt.CursorShape.SizeVerCursor
        if mode in ("left", "right"):
            return Qt.CursorShape.SizeHorCursor
        if mode == "position":
            return Qt.CursorShape.OpenHandCursor
        return Qt.CursorShape.ArrowCursor

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a position or crop drag when a handle or the media is clicked."""
        if event.button() == Qt.MouseButton.LeftButton and self._active_media_type in (MediaType.IMAGE, MediaType.VIDEO):
            pt = event.position().toPoint()
            mode = self._hit_test(pt)
            if mode is not None:
                self._drag_mode = mode
                self._drag_start_pt = pt
                self._drag_start_pos_x = self._position_x
                self._drag_start_pos_y = self._position_y

                crop_l = self._crop.get("x", 0.0)
                crop_t = self._crop.get("y", 0.0)
                crop_w = self._crop.get("w", 1.0)
                crop_h = self._crop.get("h", 1.0)
                self._drag_start_crop_l = crop_l
                self._drag_start_crop_t = crop_t
                self._drag_start_crop_r = max(0.0, 1.0 - crop_l - crop_w)
                self._drag_start_crop_b = max(0.0, 1.0 - crop_t - crop_h)

                if mode == "position":
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                else:
                    self.setCursor(self._cursor_for_mode(mode))
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Apply the active position/crop drag or update the hover cursor."""
        pt = event.position().toPoint()

        if self._drag_mode is not None:
            if self._drag_mode == "position":
                canvas = self.get_canvas_rect()
                delta = pt - self._drag_start_pt
                dx = delta.x() / max(1, canvas.width())
                dy = delta.y() / max(1, canvas.height())
                self._position_x = round(max(-2.0, min(2.0, self._drag_start_pos_x + dx)), 3)
                self._position_y = round(max(-2.0, min(2.0, self._drag_start_pos_y + dy)), 3)
                self.position_changed.emit(self._position_x, self._position_y)
                self.update()

            elif self._drag_mode in ("top_left", "top", "top_right", "right", "bottom_right", "bottom", "bottom_left", "left"):
                if self._full_media_rect and not self._full_media_rect.isEmpty():
                    full_w = max(10.0, self._full_media_rect.width())
                    full_h = max(10.0, self._full_media_rect.height())
                else:
                    full_w = max(10.0, float(self.get_canvas_rect().width()))
                    full_h = max(10.0, float(self.get_canvas_rect().height()))

                delta = pt - self._drag_start_pt
                dx = delta.x() / full_w
                dy = delta.y() / full_h

                cur_l = self._drag_start_crop_l
                cur_r = self._drag_start_crop_r
                cur_t = self._drag_start_crop_t
                cur_b = self._drag_start_crop_b

                if "left" in self._drag_mode:
                    cur_l = max(0.0, min(0.95 - self._drag_start_crop_r, self._drag_start_crop_l + dx))
                if "right" in self._drag_mode:
                    cur_r = max(0.0, min(0.95 - self._drag_start_crop_l, self._drag_start_crop_r - dx))
                if "top" in self._drag_mode:
                    cur_t = max(0.0, min(0.95 - self._drag_start_crop_b, self._drag_start_crop_t + dy))
                if "bottom" in self._drag_mode:
                    cur_b = max(0.0, min(0.95 - self._drag_start_crop_t, self._drag_start_crop_b - dy))

                self._crop = {
                    "x": round(cur_l, 4),
                    "y": round(cur_t, 4),
                    "w": round(max(0.01, 1.0 - cur_l - cur_r), 4),
                    "h": round(max(0.01, 1.0 - cur_t - cur_b), 4),
                }
                self.crop_changed.emit(round(cur_l, 4), round(cur_r, 4), round(cur_t, 4), round(cur_b, 4))
                self.update()
        else:
            mode = self._hit_test(pt)
            self.setCursor(self._cursor_for_mode(mode))

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End the drag and restore the hover cursor."""
        if self._drag_mode is not None:
            self._drag_mode = None
            pt = event.position().toPoint()
            self.setCursor(self._cursor_for_mode(self._hit_test(pt)))
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Paint the 16:9 canvas, the media frame and the crop/position handles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor("#121212"))
        canvas = self.get_canvas_rect()
        painter.fillRect(canvas, QColor("#000000"))

        # Strict 16:9 canvas clip so zoomed/shifted media never overflows UI chrome
        painter.setClipRect(canvas)

        if not self._active_media_type:
            self._rendered_media_rect = None
            self._full_media_rect = None
            if self._layer0_is_default:
                dpr = max(1.0, float(self.devicePixelRatioF()))
                cw, ch = max(1, canvas.width()), max(1, canvas.height())
                cache = self._layer0_pattern_cache
                if cache and cache[:3] == (cw, ch, dpr):
                    pat = cache[3]
                else:
                    pat = render_default_tappo_pixmap(cw, ch, self._layer0_path, dpr=dpr)
                    self._layer0_pattern_cache = (cw, ch, dpr, pat)
                painter.drawPixmap(canvas.x(), canvas.y(), pat)
            elif self._layer0_pixmap and not self._layer0_pixmap.isNull():
                scaled_l0 = self._layer0_pixmap.scaled(
                    canvas.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lx = canvas.x() + (canvas.width() - scaled_l0.width()) // 2
                ly = canvas.y() + (canvas.height() - scaled_l0.height()) // 2
                painter.drawPixmap(lx, ly, scaled_l0)

        elif self._active_media_type in (MediaType.IMAGE, MediaType.VIDEO):
            source_img: QImage | None = None

            if self._active_media_type == MediaType.IMAGE and self._image_qimage and not self._image_qimage.isNull():
                source_img = self._image_qimage
            elif self._active_media_type == MediaType.IMAGE and self._image_pixmap and not self._image_pixmap.isNull():
                self._image_qimage = self._image_pixmap.toImage()
                source_img = self._image_qimage
            elif self._active_media_type == MediaType.VIDEO and self._video_frame_image and not self._video_frame_image.isNull():
                source_img = self._video_frame_image

            if source_img and not source_img.isNull():
                orig_w, orig_h = source_img.width(), source_img.height()
                geom = compute_media_frame_geometry(
                    canvas.x(), canvas.y(), canvas.width(), canvas.height(),
                    orig_w, orig_h,
                    scale=self._scale,
                    pos_x=self._position_x,
                    pos_y=self._position_y,
                    crop=self._crop,
                    aspect_ratio=self._aspect_ratio,
                )

                crop_x = max(0.0, min(0.99, self._crop.get("x", 0.0)))
                crop_y = max(0.0, min(0.99, self._crop.get("y", 0.0)))
                crop_w = max(0.01, min(1.0 - crop_x, self._crop.get("w", 1.0)))
                crop_h = max(0.01, min(1.0 - crop_y, self._crop.get("h", 1.0)))

                cx = int(orig_w * crop_x)
                cy = int(orig_h * crop_y)
                cw = max(1, int(orig_w * crop_w))
                ch = max(1, int(orig_h * crop_h))
                cropped_slice = source_img.copy(cx, cy, cw, ch)

                rendered_w = max(1, int(round(geom.vis_w)))
                rendered_h = max(1, int(round(geom.vis_h)))
                scaled_slice = cropped_slice.scaled(
                    rendered_w, rendered_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                ix = int(round(geom.vis_x))
                iy = int(round(geom.vis_y))
                self._full_media_rect = QRectF(geom.full_x, geom.full_y, geom.full_w, geom.full_h)
                self._rendered_media_rect = QRectF(geom.vis_x, geom.vis_y, geom.vis_w, geom.vis_h)

                # Rotation and polygon mask are preview-only transforms: they
                # change what is drawn, never the source file. The dashed frame
                # and handles below stay unrotated so they remain easy to grab.
                painter.save()
                if abs(self._rotation) > 0.01:
                    center = QPointF(ix + rendered_w / 2.0, iy + rendered_h / 2.0)
                    painter.translate(center)
                    painter.rotate(self._rotation)
                    painter.translate(-center)
                if self._active_media_type == MediaType.IMAGE and len(self._mask_polygon) >= 3:
                    feather_px = self._mask_feather * float(max(rendered_w, rendered_h))
                    soft = (
                        feathered_mask_image(
                            self._mask_polygon, rendered_w, rendered_h, feather_px
                        )
                        if feather_px >= 1.0
                        else None
                    )
                    if soft is not None and not soft.isNull():
                        # Apply the same soft alpha mask the projector uses, so
                        # Pre-Viz and the real output match pixel for pixel.
                        masked_slice = QImage(
                            rendered_w, rendered_h, QImage.Format.Format_ARGB32_Premultiplied
                        )
                        masked_slice.fill(Qt.GlobalColor.transparent)
                        slice_painter = QPainter(masked_slice)
                        try:
                            slice_painter.drawImage(0, 0, scaled_slice)
                            slice_painter.setCompositionMode(
                                QPainter.CompositionMode.CompositionMode_DestinationIn
                            )
                            slice_painter.drawImage(
                                QRectF(0.0, 0.0, float(rendered_w), float(rendered_h)), soft
                            )
                        finally:
                            slice_painter.end()
                        scaled_slice = masked_slice
                    else:
                        painter.setClipPath(
                            polygon_path_from_normalized(
                                self._mask_polygon,
                                float(ix), float(iy), float(rendered_w), float(rendered_h),
                            )
                        )
                painter.setOpacity(max(0.0, min(1.0, self._opacity)))
                painter.drawImage(ix, iy, scaled_slice)
                painter.restore()
                painter.setOpacity(1.0)

                r = self._rendered_media_rect
                painter.setPen(QPen(QColor("#00e5ff"), 1.5, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(r)

                hs = 8.0
                half = hs / 2.0
                handle_points = [
                    r.topLeft(),
                    QPointF(r.center().x(), r.top()),
                    r.topRight(),
                    QPointF(r.right(), r.center().y()),
                    r.bottomRight(),
                    QPointF(r.center().x(), r.bottom()),
                    r.bottomLeft(),
                    QPointF(r.left(), r.center().y()),
                ]
                painter.setPen(QPen(QColor("#102027"), 1.5))
                painter.setBrush(QBrush(QColor("#ffffff")))
                for pt in handle_points:
                    painter.drawRect(QRectF(pt.x() - half, pt.y() - half, hs, hs))

            elif self._active_media_type == MediaType.VIDEO:
                self._rendered_media_rect = None
                self._full_media_rect = None
                painter.setPen(QColor("#80cbc4"))
                painter.setFont(QFont("sans-serif", 10, QFont.Weight.Normal))
                painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "🎬 VIDEO CARICATO IN PRE-VIZ — PREMI PLAY")

        elif self._active_media_type == MediaType.AUDIO:
            self._rendered_media_rect = None
            self._full_media_rect = None

            canvas_w, canvas_h = canvas.width(), canvas.height()
            cx, cy = canvas.x(), canvas.y()
            card_w = min(canvas_w * 0.85, 480)
            card_h = min(canvas_h * 0.58, 140)
            card_x = cx + (canvas_w - card_w) / 2
            card_y = cy + (canvas_h - card_h) / 2
            card_rect = QRectF(card_x, card_y, card_w, card_h)

            painter.setPen(QPen(QColor("#263238"), 1.5))
            painter.setBrush(QBrush(QColor(16, 24, 32, 235)))
            painter.drawRoundedRect(card_rect, 8, 8)

            painter.setFont(QFont("sans-serif", 12, QFont.Weight.Bold))
            painter.setPen(QColor("#00e5ff"))
            title_text = "🎵 RIPRODUZIONE AUDIO IN ANTEPRIMA (PRE-VIZ)" if self._audio_is_playing else "⏸ TRACCIA AUDIO IN STANDBY"
            painter.drawText(
                QRectF(card_x + 20, card_y + 16, card_w - 40, 26),
                Qt.AlignmentFlag.AlignCenter,
                title_text,
            )

            painter.setFont(QFont("sans-serif", 9, QFont.Weight.Normal))
            painter.setPen(QColor("#90a4ae"))
            subtitle = "Pre-ascolto attivo in cuffia • Monitor sala mutato" if self._audio_is_playing else "Premi ▶ Play sotto l'anteprima per pre-ascoltare in cuffia"
            painter.drawText(
                QRectF(card_x + 20, card_y + 44, card_w - 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                subtitle,
            )

            bar_y = card_y + 78
            meter_w = card_w - 90
            meter_h = 7
            meter_x = card_x + 45

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#1e272c"))
            painter.drawRoundedRect(QRectF(meter_x, bar_y, meter_w, meter_h), 3, 3)
            painter.drawRoundedRect(QRectF(meter_x, bar_y + 13, meter_w, meter_h), 3, 3)

            if self._audio_is_playing:
                painter.setBrush(QColor("#00e676"))
                painter.drawRoundedRect(QRectF(meter_x, bar_y, meter_w * 0.68, meter_h), 3, 3)
                painter.drawRoundedRect(QRectF(meter_x, bar_y + 13, meter_w * 0.63, meter_h), 3, 3)

                painter.setPen(QColor("#78909c"))
                painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
                painter.drawText(QRectF(meter_x - 22, bar_y - 2, 18, meter_h + 4), Qt.AlignmentFlag.AlignRight, "L")
                painter.drawText(QRectF(meter_x - 22, bar_y + 11, 18, meter_h + 4), Qt.AlignmentFlag.AlignRight, "R")

        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#3e3e3e"), 1))
        painter.drawRect(canvas)
        painter.end()

