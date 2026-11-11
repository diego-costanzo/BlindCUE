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

from PySide6.QtCore import Qt, QRectF, QSizeF, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QPixmap,
    QScreen,
)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from ui.layout_math import compute_media_frame_geometry, parse_aspect_ratio
from ui.tappo_pattern import is_default_tappo_path, render_default_tappo_pixmap

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
        self._layer0_pattern_cache: Optional[tuple[int, int, float, str, QPixmap]] = None
        self._layer0_path = fallback_image or str(_DEFAULT_LOGO)
        self._panic_black: bool = False
        self._build_layer0()

        # ── Layers 1-3: Independent Video & Image Compositing ─────────
        self._layer_pixmaps: dict[int, QGraphicsPixmapItem] = {}
        self._video_containers: dict[int, QGraphicsRectItem] = {}
        self._video_items: dict[int, QGraphicsVideoItem] = {}
        self._secondary_video_items: dict[int, QGraphicsVideoItem] = {}
        self._active_video_deck: dict[int, int] = {1: 0, 2: 0, 3: 0}
        self._deck_swap_timers: dict[int, QTimer] = {}
        self._video_layouts: dict[int, dict] = {}

        for layer in (1, 2, 3):
            container = QGraphicsRectItem()
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

        # Backward-compatibility aliases pointing to Layer 1
        self._video_container = self._video_containers[1]
        self._video_item = self._video_items[1]

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

    def clear_pixmap_layer(self, layer: int) -> None:
        """Remove any static image overlay and pending image fade on *layer*."""
        self._stop_timer_entry(self._layer_fade_timers, layer)
        item = self._layer_pixmaps.pop(layer, None)
        if item is not None:
            try:
                self._scene.removeItem(item)
            except Exception:
                pass
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
        *,
        reuse_item: bool = False,
    ) -> None:
        """Crop, scale, and composite *pix* onto *layer* without duplicating layout math."""
        w, h = max(1, self.width()), max(1, self.height())
        geom = compute_media_frame_geometry(
            0.0, 0.0, w, h,
            pix.width(), pix.height(),
            scale=scale,
            pos_x=pos_x,
            pos_y=pos_y,
            crop=crop,
            aspect_ratio=aspect_ratio,
        )

        if crop and (crop.get("w", 1.0) < 0.9999 or crop.get("h", 1.0) < 0.9999
                     or crop.get("x", 0.0) > 0.0001 or crop.get("y", 0.0) > 0.0001):
            cw = max(1, int(round(pix.width() * crop.get("w", 1.0))))
            ch = max(1, int(round(pix.height() * crop.get("h", 1.0))))
            cx = max(0, min(pix.width() - 1, int(round(pix.width() * crop.get("x", 0.0)))))
            cy = max(0, min(pix.height() - 1, int(round(pix.height() * crop.get("y", 0.0)))))
            pix = pix.copy(cx, cy, cw, ch)

        scaled = pix.scaled(
            max(1, int(round(geom.vis_w))),
            max(1, int(round(geom.vis_h))),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._stop_timer_entry(self._layer_fade_timers, layer)
        if layer in self._video_containers and self._video_containers[layer].isVisible():
            self._video_containers[layer].hide()

        clamped_op = max(0.0, min(1.0, opacity))
        existing = self._layer_pixmaps.get(layer) if reuse_item else None
        if existing is not None:
            existing.setPixmap(scaled)
            existing.setOpacity(clamped_op)
            existing.setZValue(layer * 10)
            existing.setPos(geom.vis_x, geom.vis_y)
            existing.show()
        else:
            self.clear_pixmap_layer(layer)
            item = self._scene.addPixmap(scaled)
            item.setOpacity(clamped_op)
            item.setZValue(layer * 10)
            item.setPos(geom.vis_x, geom.vis_y)
            self._layer_pixmaps[layer] = item

        self._update_tappo_visibility()

    def show_image(self, layer: int, file_path: str, opacity: float = 1.0,
                   crop: Optional[dict] = None, scale: float = 1.0,
                   pos_x: float = 0.0, pos_y: float = 0.0,
                   aspect_ratio: Optional[str] = None) -> None:
        """Display a static image on layer 1, 2, or 3 with transforms."""
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
                reuse_item=False,
            )
            logger.info("[OUTPUT] Displayed image on Layer %d: %s (pos=%.2f,%.2f, scale=%.2f, op=%.2f, ar=%s)",
                        layer, file_path, pos_x, pos_y, scale, opacity, aspect_ratio or "Native")
        except Exception as exc:
            logger.error("[OUTPUT] show_image() failed on layer %d: %s", layer, exc)

    def show_mirrored_frame(self, layer: int, frame_image: QImage, opacity: float = 1.0,
                            crop: Optional[dict] = None, scale: float = 1.0,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            aspect_ratio: Optional[str] = None) -> None:
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
                reuse_item=True,
            )
        except Exception as exc:
            logger.error("[OUTPUT] show_mirrored_frame() failed on layer %d: %s", layer, exc)

    def ensure_live_video_visible(self, layer: int, scale: float = 1.0, crop: Optional[dict] = None,
                                  pos_x: float = 0.0, pos_y: float = 0.0,
                                  opacity: float = 1.0, aspect_ratio: Optional[str] = None) -> None:
        """Restore live video visibility on *layer* without disturbing an active loop deck."""
        target_layer = layer if layer in self._video_containers else 1
        self.clear_pixmap_layer(target_layer)
        self.update_video_layout(
            scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y,
            opacity=opacity, layer=target_layer, aspect_ratio=aspect_ratio,
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
        img_item = self._layer_pixmaps.get(layer)
        if img_item is not None:
            img_item.setOpacity(op)
        if layer in self._video_containers:
            if layer in self._video_layouts:
                self._video_layouts[layer]["opacity"] = op
            if self._video_containers[layer].isVisible():
                self._active_video_item(layer).setOpacity(op)

    def show_video_widget(self, scale: float = 1.0, crop: Optional[dict] = None,
                          pos_x: float = 0.0, pos_y: float = 0.0,
                          opacity: float = 1.0, layer: int = 1,
                          aspect_ratio: Optional[str] = None) -> None:
        """Show the video item for *layer* with scale, crop, pos, opacity, and aspect ratio."""
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
        )
        self._video_containers[target_layer].show()
        self._update_tappo_visibility()

    def update_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                            pos_x: float = 0.0, pos_y: float = 0.0,
                            opacity: float = 1.0, layer: int = 1,
                            aspect_ratio: Optional[str] = None) -> None:
        """Update geometry, scaling, position, opacity, crop mask, and aspect ratio for *layer* video."""
        try:
            target_layer = layer if layer in self._video_containers else 1
            self._last_scale = scale
            self._last_crop = crop
            self._video_layouts[target_layer] = {
                "scale": scale,
                "crop": crop,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "opacity": opacity,
                "aspect_ratio": aspect_ratio,
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

            geom = compute_media_frame_geometry(
                0.0, 0.0, win_w, win_h,
                nat_w, nat_h,
                scale=scale,
                pos_x=pos_x,
                pos_y=pos_y,
                crop=crop,
                aspect_ratio=aspect_ratio,
            )

            container.setRect(0, 0, geom.vis_w, geom.vis_h)
            container.setPos(geom.vis_x, geom.vis_y)

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
            )

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
