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

from PySide6.QtCore import Qt, QRect, QRectF, QSizeF, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QKeyEvent,
    QPixmap,
    QRegion,
    QScreen,
)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem, QVideoWidget
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsOpacityEffect,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Resolve the default logo path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_LOGO = _PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"


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
        self._layer0_path = fallback_image or str(_DEFAULT_LOGO)
        self._build_layer0()

        # ── Layers 1-3: Graphics overlays & media ─────────────────────
        self._layer_pixmaps: dict[int, QGraphicsPixmapItem] = {}

        # Native Wayland video item in scene with clipping container
        self._video_container = QGraphicsRectItem()
        self._video_container.setPen(Qt.PenStyle.NoPen)
        self._video_container.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        self._video_container.setZValue(15)  # sits above layer overlays
        self._scene.addItem(self._video_container)

        self._video_item = QGraphicsVideoItem(self._video_container)
        self._video_container.hide()

        # Fade timers management (leak-proof & race-proof)
        self._video_fade_timer: Optional[QTimer] = None
        self._layer_fade_timers: dict[int, QTimer] = {}

        logger.info("[OUTPUT] Native Wayland Output Window created")

    # ── Layer 0 ───────────────────────────────────────────────────────

    def _build_layer0(self) -> None:
        """Load the failsafe image into the scene (or create solid black)."""
        self._black_rect = self._scene.addRect(
            QRectF(0, 0, 1920, 1080),
            brush=QBrush(QColor(0, 0, 0)),
        )
        self._black_rect.setZValue(-100)

        if os.path.isfile(self._layer0_path):
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

        if self._logo_item is not None and self._original_logo_pixmap is not None:
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
        target_path = image_path or str(_DEFAULT_LOGO)
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
        """Ensure Layer 0 (Tappo) is ONLY visible when NO cues are active.
        When any image or video is on air, background is pure solid black."""
        has_active_media = bool(self._layer_pixmaps) or self._video_container.isVisible()
        if self._logo_item is not None:
            self._logo_item.setVisible(not has_active_media)

    # ── Layers 1-3 (Images & Overlays) ────────────────────────────────

    def show_image(self, layer: int, file_path: str, opacity: float = 1.0,
                   crop: Optional[dict] = None, scale: float = 1.0,
                   pos_x: float = 0.0, pos_y: float = 0.0) -> None:
        """Display a static image on layer 1, 2, or 3 with transforms."""
        try:
            if not os.path.isfile(file_path):
                logger.warning("[OUTPUT] Image file not found: %s", file_path)
                return

            pix = QPixmap(file_path)
            if pix.isNull():
                return

            if crop and (crop.get("w", 1.0) < 0.999 or crop.get("h", 1.0) < 0.999
                         or crop.get("x", 0.0) > 0.001 or crop.get("y", 0.0) > 0.001):
                cw = max(1, int(pix.width() * crop.get("w", 1.0)))
                ch = max(1, int(pix.height() * crop.get("h", 1.0)))
                cx = max(0, min(pix.width() - 1, int(pix.width() * crop.get("x", 0.0))))
                cy = max(0, min(pix.height() - 1, int(pix.height() * crop.get("y", 0.0))))
                pix = pix.copy(cx, cy, cw, ch)

            w, h = max(1, self.width()), max(1, self.height())
            target_scale = max(0.1, min(5.0, scale))
            scaled = pix.scaled(
                int(w * target_scale), int(h * target_scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.clear_layer(layer)

            item = self._scene.addPixmap(scaled)
            item.setOpacity(max(0.0, min(1.0, opacity)))
            item.setZValue(layer * 10)

            offset_x = (w - scaled.width()) / 2 + (pos_x * w)
            offset_y = (h - scaled.height()) / 2 + (pos_y * h)
            item.setPos(offset_x, offset_y)

            self._layer_pixmaps[layer] = item
            self._update_tappo_visibility()
            logger.info("[OUTPUT] Displayed image on Layer %d: %s (pos=%.2f,%.2f, scale=%.2f, op=%.2f)",
                        layer, file_path, pos_x, pos_y, scale, opacity)
        except Exception as exc:
            logger.error("[OUTPUT] show_image() failed on layer %d: %s", layer, exc)

    def clear_layer(self, layer: int) -> None:
        """Remove content from a specific layer."""
        item = self._layer_pixmaps.pop(layer, None)
        if item is not None:
            try:
                self._scene.removeItem(item)
            except Exception:
                pass
        self._update_tappo_visibility()

    def clear_all_layers(self) -> None:
        """Clear all active media overlays (Layers 1-3)."""
        for layer in list(self._layer_pixmaps.keys()):
            self.clear_layer(layer)
        self._update_tappo_visibility()

    # ── Video Widget & Public API ─────────────────────────────────────

    def get_video_widget(self) -> QGraphicsVideoItem:
        """Return the native video item for QMediaPlayer.setVideoOutput()."""
        return self._video_item

    def get_video_item(self) -> QGraphicsVideoItem:
        """Return the native QGraphicsVideoItem."""
        return self._video_item

    def show_video_widget(self, scale: float = 1.0, crop: Optional[dict] = None,
                          pos_x: float = 0.0, pos_y: float = 0.0,
                          opacity: float = 1.0) -> None:
        """Show the video playback item above Layer 0 with scale, crop, pos & opacity."""
        self.update_video_layout(scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y, opacity=opacity)
        self._video_container.show()
        self._update_tappo_visibility()

    def update_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            opacity: float = 1.0) -> None:
        """Update geometry, scaling, position, opacity, and crop mask for the live video item.
        Strictly clips to output window boundaries and crop rectangle using QGraphicsItem clipping."""
        try:
            self._last_scale = scale
            self._last_crop = crop
            win_w = max(1, self.width())
            win_h = max(1, self.height())
            target_scale = max(0.1, min(5.0, scale))

            full_w = int(win_w * target_scale)
            full_h = int(win_h * target_scale)

            crop_dict = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
            cx_pct = max(0.0, min(1.0, crop_dict.get("x", 0.0)))
            cy_pct = max(0.0, min(1.0, crop_dict.get("y", 0.0)))
            cw_pct = max(0.01, min(1.0 - cx_pct, crop_dict.get("w", 1.0)))
            ch_pct = max(0.01, min(1.0 - cy_pct, crop_dict.get("h", 1.0)))

            cut_x = int(full_w * cx_pct)
            cut_y = int(full_h * cy_pct)
            box_w = int(full_w * cw_pct)
            box_h = int(full_h * ch_pct)

            # Center position on the output screen + normalized position offset
            center_x = (win_w - box_w) / 2.0 + (pos_x * win_w)
            center_y = (win_h - box_h) / 2.0 + (pos_y * win_h)

            self._video_container.setRect(0, 0, box_w, box_h)
            self._video_container.setPos(center_x, center_y)

            self._video_item.setSize(QSizeF(full_w, full_h))
            self._video_item.setPos(-cut_x, -cut_y)
            self._video_item.setOpacity(max(0.0, min(1.0, opacity)))
        except Exception as exc:
            logger.error("[OUTPUT] update_video_layout failed: %s", exc)

    def hide_video_widget(self) -> None:
        """Hide the video playback item and check if Layer 0 should reappear."""
        self._video_container.hide()
        self._update_tappo_visibility()

    def fade_out_video(self, duration_sec: float = 0.2,
                       callback: Optional[Callable[[], None]] = None) -> None:
        """Smoothly fade out video over duration_sec (default 0.2s micro-fade) and hide."""
        if self._video_fade_timer is not None and self._video_fade_timer.isActive():
            self._video_fade_timer.stop()
            self._video_fade_timer = None

        if not self._video_container.isVisible() or duration_sec <= 0:
            self.hide_video_widget()
            if callback:
                callback()
            return

        start_op = self._video_item.opacity()
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        decrement = start_op / steps
        cur = 0

        self._video_fade_timer = QTimer(self)

        def _step():
            nonlocal cur
            cur += 1
            op = max(0.0, start_op - (cur * decrement))
            self._video_item.setOpacity(op)
            if cur >= steps or op <= 0.01:
                if self._video_fade_timer is not None:
                    self._video_fade_timer.stop()
                    self._video_fade_timer = None
                self.hide_video_widget()
                self._video_item.setOpacity(1.0)
                if callback:
                    callback()

        self._video_fade_timer.timeout.connect(_step)
        self._video_fade_timer.start(interval)

    def fade_out_layer(self, layer: int, duration_sec: float = 0.2,
                       callback: Optional[Callable[[], None]] = None) -> None:
        """Smoothly fade out an image layer over duration_sec and remove it."""
        old_timer = self._layer_fade_timers.pop(layer, None)
        if old_timer is not None and old_timer.isActive():
            old_timer.stop()

        item = self._layer_pixmaps.get(layer)
        if item is None or duration_sec <= 0:
            self.clear_layer(layer)
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
                timer.stop()
                self._layer_fade_timers.pop(layer, None)
                self.clear_layer(layer)
                if callback:
                    callback()

        timer.timeout.connect(_step)
        timer.start(interval)

    def fade_in_video(self, duration_sec: float = 0.5, target_opacity: float = 1.0) -> None:
        """Smoothly fade in video from 0.0 to target_opacity over duration_sec."""
        if duration_sec <= 0:
            self._video_item.setOpacity(max(0.0, min(1.0, target_opacity)))
            return

        self._video_item.setOpacity(0.0)
        target_op = max(0.0, min(1.0, target_opacity))
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        increment = target_op / steps
        cur = 0

        fade_timer = QTimer(self)

        def _step():
            nonlocal cur
            cur += 1
            op = min(target_op, cur * increment)
            self._video_item.setOpacity(op)
            if cur >= steps or op >= target_op - 0.01:
                fade_timer.stop()
                self._video_item.setOpacity(target_op)

        fade_timer.timeout.connect(_step)
        fade_timer.start(interval)

    def fade_in_layer(self, layer: int, duration_sec: float = 0.5, target_opacity: float = 1.0) -> None:
        """Smoothly fade in image layer from 0.0 to target_opacity over duration_sec."""
        item = self._layer_pixmaps.get(layer)
        if item is None or duration_sec <= 0:
            if item is not None:
                item.setOpacity(max(0.0, min(1.0, target_opacity)))
            return

        target_op = max(0.0, min(1.0, target_opacity))
        item.setOpacity(0.0)
        steps = max(1, int(duration_sec * 30))
        interval = int(1000 / 30)
        increment = target_op / steps
        cur = 0

        fade_timer = QTimer(self)

        def _step():
            nonlocal cur
            cur += 1
            op = min(target_op, cur * increment)
            item.setOpacity(op)
            if cur >= steps or op >= target_op - 0.01:
                fade_timer.stop()
                item.setOpacity(target_op)

        fade_timer.timeout.connect(_step)
        fade_timer.start(interval)

    def show_fallback(self, fade_duration_sec: float = 0.2,
                      callback: Optional[Callable[[], None]] = None) -> None:
        """Bring Layer 0 (Tappo) to front with optional micro-fade.
        All live media is removed and the logo is displayed."""
        has_media = self._video_container.isVisible() or bool(self._layer_pixmaps)
        if not has_media or fade_duration_sec <= 0:
            self._video_container.hide()
            self.clear_all_layers()
            if self._logo_item is not None:
                self._logo_item.setVisible(True)
            logger.info("[OUTPUT] Fallback (Layer 0 Tappo) restored immediately")
            if callback:
                callback()
            return

        # Faded transition to fallback
        def _finish():
            self._video_container.hide()
            self.clear_all_layers()
            if self._logo_item is not None:
                self._logo_item.setVisible(True)
            logger.info("[OUTPUT] Fallback (Layer 0 Tappo) restored after %.2fs fade", fade_duration_sec)
            if callback:
                callback()

        if self._video_container.isVisible():
            self.fade_out_video(duration_sec=fade_duration_sec, callback=_finish)
        else:
            for l in list(self._layer_pixmaps.keys()):
                self.fade_out_layer(l, duration_sec=fade_duration_sec)
            _finish()
            QTimer.singleShot(int(fade_duration_sec * 1000) + 10, _finish)

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
            self.setWindowTitle("BlindCue – Live Output [Monitor Simulato]")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            geo = screen.geometry()
            w = min(800, int(geo.width() * 0.45))
            h = int(w * 9 / 16)
            self.setGeometry(geo.x() + geo.width() - w - 30, geo.y() + geo.height() - h - 60, w, h)
            self.showNormal()
            logger.info("[OUTPUT] Single monitor preview window (%dx%d)", w, h)

        self._fit_layer0()
        self.hide_video_widget()

    def attach_to_screen(self, screen: QScreen, is_external: bool = True) -> None:
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
            self.setWindowTitle("BlindCue – Live Output [Monitor Simulato]")
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.showNormal()
        else:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Window
            )
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self.showFullScreen()
        self._fit_layer0()

    def force_close(self) -> None:
        self._force_close_allowed = True
        if self._video_fade_timer is not None:
            self._video_fade_timer.stop()
            self._video_fade_timer = None
        for t in self._layer_fade_timers.values():
            t.stop()
        self._layer_fade_timers.clear()
        self.close()

    # ── Overrides ─────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_layer0()
        if hasattr(self, "_video_widget"):
            self._video_widget.setGeometry(0, 0, self.width(), self.height())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._force_close_allowed or not self._is_external:
            event.accept()
        else:
            logger.warning("[OUTPUT] Close attempt blocked during show (use force_close)")
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if not self._is_external:
                event.accept()
                return
            event.ignore()
            return
        super().keyPressEvent(event)
