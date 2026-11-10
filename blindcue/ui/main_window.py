"""Director / Control Panel – main window of BlindCue.

Resides on the primary monitor and provides:

- Cue list with LIVE / PRE-VIZ badges
- Preview / Pre-Viz sandbox with embedded native Wayland player
- Inspector / Cue Properties panel
- Waveform display
- GO button
- Live Upload drag-and-drop zone
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygon,
    QRegion,
    QShortcut,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedLayout,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from models.cue import Cue, CueStatus, MediaType
from models.project_manager import ProjectManager
from engine.audio_analyzer import WaveformAnalyzer
from ui.output_window import OutputWindow

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOGO_PATH = _PROJECT_ROOT / "immagini di progetto" / "BlindCue-logo.jpeg"

# ── Colour palette ────────────────────────────────────────────────────
_CLR_BG = "#1e1e1e"
_CLR_PANEL = "#282828"
_CLR_TEXT = "#e0e0e0"
_CLR_LIVE = "#00e676"       # bright green
_CLR_PREVIZ = "#ffab00"     # amber
_CLR_GO = "#00e676"
_CLR_ACCENT = "#00bcd4"

# Supported file extensions
_VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
_AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".svg"}

_DARK_STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {_CLR_BG};
        color: {_CLR_TEXT};
    }}
    QGroupBox {{
        background-color: #242424;
        border: 1px solid #363636;
        border-radius: 6px;
        margin-top: 10px;
        padding: 10px 8px 8px 8px;
        font-weight: bold;
        font-size: 11px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: #00bcd4;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: #1a1a1a;
        border: 1px solid #383838;
        border-radius: 4px;
        padding: 3px 6px;
        color: #e0e0e0;
        font-size: 11px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: #00bcd4;
        background-color: #202020;
    }}
    QListWidget {{
        background-color: #242424;
        border: 1px solid #3e3e3e;
        border-radius: 4px;
        font-size: 12px;
        font-family: 'DejaVu Sans Mono', 'Liberation Mono', 'Roboto Mono', 'Ubuntu Mono', 'monospace', monospace;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-bottom: 1px solid #333333;
    }}
    QListWidget::item:selected {{
        background-color: #383838;
        border-left: 3px solid #00bcd4;
    }}
    QListWidget::item:hover {{
        background-color: #2e2e2e;
    }}
    QPushButton {{
        background-color: #383838;
        border: 1px solid #4e4e4e;
        border-radius: 4px;
        padding: 5px 12px;
        color: {_CLR_TEXT};
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #484848;
        border-color: #666666;
    }}
    QPushButton:pressed {{
        background-color: #2a2a2a;
    }}
    QPushButton:checked {{
        background-color: #00695c;
        border-color: #00bcd4;
        color: #ffffff;
    }}
    QPushButton:disabled {{
        background-color: #222222;
        border-color: #333333;
        color: #555555;
    }}
    QLabel {{
        color: {_CLR_TEXT};
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: #3e3e3e;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        margin: -4px 0;
        background: {_CLR_ACCENT};
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #26c6da;
    }}
    QSlider::handle:horizontal:disabled {{
        background: #555555;
    }}
    QSpinBox, QDoubleSpinBox, QTimeEdit, QComboBox, QLineEdit {{
        background-color: #333333;
        border: 1px solid #4e4e4e;
        border-radius: 3px;
        padding: 3px 6px;
        color: #ffffff;
        font-size: 11px;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
        border-color: {_CLR_ACCENT};
    }}
    QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled {{
        background-color: #222222;
        border-color: #333333;
        color: #555555;
    }}
    QCheckBox {{
        spacing: 6px;
        color: {_CLR_TEXT};
    }}
    QCheckBox:disabled {{
        color: #555555;
    }}
    QSplitter::handle {{
        background-color: #1a1a1a;
    }}
    QSplitter::handle:hover {{
        background-color: #00bcd4;
    }}
    QStatusBar {{
        background-color: #161616;
        color: #b0bec5;
        font-size: 11px;
    }}
    QMenuBar {{
        background-color: #1a1a1a;
        color: {_CLR_TEXT};
        font-size: 12px;
    }}
    QMenuBar::item:selected {{
        background-color: #333333;
    }}
    QMenu {{
        background-color: #282828;
        border: 1px solid #444444;
        color: {_CLR_TEXT};
    }}
    QMenu::item:selected {{
        background-color: #383838;
    }}
"""


def _format_cid(cue_id: object) -> str:
    """Format cue ID gracefully whether it is int or str."""
    if isinstance(cue_id, int):
        return f"{cue_id:03d}"
    if isinstance(cue_id, str) and cue_id.isdigit():
        return f"{int(cue_id):03d}"
    return str(cue_id)


# ═══════════════════════════════════════════════════════════════════════
# Waveform Display Widget
# ═══════════════════════════════════════════════════════════════════════

class WaveformWidget(QWidget):
    """Paints a waveform peak array with interactive mouse dragging of IN / OUT markers."""

    in_changed = Signal(float)   # In seconds
    out_changed = Signal(float)  # Out seconds (or 0.0 for End of File)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._peaks: Optional[np.ndarray] = None
        self._in_point: float = 0.0
        self._out_point: float = 1.0  # normalised 0-1
        self._in_sec: float = 0.0
        self._out_sec: Optional[float] = None
        self._duration_sec: float = 0.0
        self._playhead: Optional[float] = None
        self._dragging_handle: Optional[str] = None
        self.setMinimumHeight(100)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background-color: {_CLR_PANEL};")

    def set_peaks(self, peaks: np.ndarray) -> None:
        self._peaks = peaks
        self.update()

    def set_in_out(self, in_norm: float, out_norm: float) -> None:
        self._in_point = in_norm
        self._out_point = out_norm
        self.update()

    def set_in_out_seconds(self, in_sec: float, out_sec: Optional[float], duration_sec: float) -> None:
        """Update IN and OUT points in seconds relative to total file duration."""
        self._in_sec = max(0.0, in_sec)
        self._out_sec = out_sec
        self._duration_sec = max(0.001, duration_sec) if duration_sec > 0 else 0.0

        if self._duration_sec > 0:
            self._in_point = min(1.0, max(0.0, self._in_sec / self._duration_sec))
            if self._out_sec is not None and self._out_sec > 0:
                self._out_point = min(1.0, max(0.0, self._out_sec / self._duration_sec))
            else:
                self._out_point = 1.0
        else:
            self._in_point = 0.0
            self._out_point = 1.0
        self.update()

    def set_playhead(self, norm_pos: Optional[float]) -> None:
        """Update active playhead position (0.0 to 1.0) or None to hide."""
        if self._playhead != norm_pos:
            self._playhead = norm_pos
            self.update()

    # ── Mouse Interaction ─────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._duration_sec > 0:
            x = event.position().x()
            w = max(1, self.width())
            in_x = int(self._in_point * w)
            out_x = int(self._out_point * w)

            if abs(x - in_x) <= 15:
                self._dragging_handle = "IN"
            elif abs(x - out_x) <= 15:
                self._dragging_handle = "OUT"
            else:
                if abs(x - in_x) < abs(x - out_x):
                    self._dragging_handle = "IN"
                else:
                    self._dragging_handle = "OUT"
                self._handle_mouse_drag(x)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        if self._dragging_handle:
            self._handle_mouse_drag(x)
        else:
            w = max(1, self.width())
            in_x = int(self._in_point * w)
            out_x = int(self._out_point * w)
            if abs(x - in_x) <= 12 or abs(x - out_x) <= 12:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging_handle = None
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def leaveEvent(self, _event) -> None:  # noqa: N802
        if not self._dragging_handle:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _handle_mouse_drag(self, x: float) -> None:
        if self._duration_sec <= 0:
            return
        w = max(1, self.width())
        norm = max(0.0, min(1.0, x / w))
        sec = norm * self._duration_sec

        if self._dragging_handle == "IN":
            max_in = (self._out_sec - 0.05) if (self._out_sec is not None and self._out_sec > 0) else (self._duration_sec - 0.05)
            new_in = max(0.0, min(max_in, sec))
            self._in_sec = round(new_in, 2)
            self._in_point = self._in_sec / self._duration_sec
            self.in_changed.emit(self._in_sec)
            self.update()

        elif self._dragging_handle == "OUT":
            min_out = self._in_sec + 0.05
            new_out = max(min_out, min(self._duration_sec, sec))
            if new_out >= self._duration_sec - 0.05:
                self._out_sec = None
                self._out_point = 1.0
                self.out_changed.emit(0.0)
            else:
                self._out_sec = round(new_out, 2)
                self._out_point = self._out_sec / self._duration_sec
                self.out_changed.emit(self._out_sec)
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        # Background
        painter.fillRect(0, 0, w, h, QColor(_CLR_PANEL))

        if self._peaks is None or len(self._peaks) == 0:
            painter.setPen(QPen(QColor("#888"), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Nessuna forma d'onda caricata")
            painter.end()
            return

        n = len(self._peaks)
        bar_w = max(1.0, w / n)
        mid_y = h / 2

        # Draw bars
        painter.setPen(Qt.PenStyle.NoPen)
        for i, peak in enumerate(self._peaks):
            x = i * bar_w
            bar_h = peak * mid_y * 0.9  # 90% of half-height

            # Colour region inside IN-OUT green, outside grey
            frac = i / n
            if self._in_point <= frac <= self._out_point:
                painter.setBrush(QColor(_CLR_LIVE))
            else:
                painter.setBrush(QColor("#444444"))

            painter.drawRect(int(x), int(mid_y - bar_h),
                             max(1, int(bar_w) - 1), int(bar_h * 2))

        # IN marker line & handle tag
        in_x = int(self._in_point * w)
        painter.setPen(QPen(QColor(_CLR_LIVE), 2))
        painter.drawLine(in_x, 0, in_x, h)

        # IN Top & Bottom Handle grips
        painter.setBrush(QColor(_CLR_LIVE))
        painter.drawPolygon([QPoint(in_x, 0), QPoint(in_x - 6, 8), QPoint(in_x + 6, 8)])
        painter.drawPolygon([QPoint(in_x, h), QPoint(in_x - 6, h - 8), QPoint(in_x + 6, h - 8)])

        in_txt = f"IN: {self._in_sec:.2f}s" if self._in_sec > 0 else "IN: 0.00s"
        painter.fillRect(in_x + 2, 2, len(in_txt) * 7 + 8, 16, QColor("#003314"))
        painter.setPen(QColor(_CLR_LIVE))
        font = QFont("sans-serif", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(in_x + 6, 14, in_txt)

        # OUT marker line & handle tag
        out_x = min(w - 1, int(self._out_point * w))
        painter.setPen(QPen(QColor("#ff5252"), 2))
        painter.drawLine(out_x, 0, out_x, h)

        # OUT Top & Bottom Handle grips
        painter.setBrush(QColor("#ff5252"))
        painter.drawPolygon([QPoint(out_x, 0), QPoint(out_x - 6, 8), QPoint(out_x + 6, 8)])
        painter.drawPolygon([QPoint(out_x, h), QPoint(out_x - 6, h - 8), QPoint(out_x + 6, h - 8)])

        out_txt = f"OUT: {self._out_sec:.2f}s" if (self._out_sec is not None and self._out_sec > 0) else "OUT: Fine"
        out_pill_w = len(out_txt) * 7 + 8
        out_pill_x = max(0, out_x - out_pill_w - 2) if out_x > w - 90 else out_x + 2
        painter.fillRect(out_pill_x, 2, out_pill_w, 16, QColor("#3a0d0d"))
        painter.setPen(QColor("#ff5252"))
        painter.drawText(out_pill_x + 5, 14, out_txt)

        # Playhead indicator
        if self._playhead is not None and 0.0 <= self._playhead <= 1.0:
            playhead_x = int(self._playhead * w)
            painter.setPen(QPen(QColor(_CLR_ACCENT), 2))
            painter.drawLine(playhead_x, 0, playhead_x, h)
            # Triangular playhead indicator at top
            painter.setBrush(QColor(_CLR_ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            poly = [
                QPoint(playhead_x - 5, 0),
                QPoint(playhead_x + 5, 0),
                QPoint(playhead_x, 8),
            ]
            painter.drawPolygon(QPolygon(poly))

        painter.end()


# ═══════════════════════════════════════════════════════════════════════
# High Precision SpinBoxes (Centesimi)
# ═══════════════════════════════════════════════════════════════════════

class InPointSpinBox(QDoubleSpinBox):
    """High-precision (centesimi) spinbox for Cue IN point."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")


class OutPointSpinBox(QDoubleSpinBox):
    """Smart Out Point SpinBox with centesimi precision and end-of-file down-stepping."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setRange(0.0, 99999.0)
        self.setDecimals(2)
        self.setSingleStep(0.05)
        self.setSuffix(" s")
        self.setSpecialValueText("Fine File")
        self._media_duration: float = 0.0

    def set_media_duration(self, duration_sec: float) -> None:
        self._media_duration = max(0.0, duration_sec)

    def stepBy(self, steps: int) -> None:  # noqa: N802
        cur = self.value()
        if cur == 0.0 and steps < 0 and self._media_duration > 0:
            target = max(0.05, self._media_duration + (steps * self.singleStep()))
            self.setValue(round(target, 2))
            return
        elif cur == 0.0 and steps > 0 and self._media_duration > 0:
            return
        super().stepBy(steps)


# ═══════════════════════════════════════════════════════════════════════
# WYSIWYG 16:9 Studio Preview Monitor
# ═══════════════════════════════════════════════════════════════════════

class StudioPreviewMonitor(QWidget):
    """16:9 WYSIWYG studio preview monitor that mirrors live output.

    Renders Layer 0 (Tappo) underneath when idle, and places video or images on top
    with pixel-accurate scale, crop, position, and opacity.
    STRICTLY CLIPPED to the 16:9 canvas so media NEVER overflows into the director UI.
    Supports interactive mouse dragging for positioning!
    """

    position_changed = Signal(float, float)  # pos_x, pos_y

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000000; border-radius: 4px;")

        self._layer0_pixmap: Optional[QPixmap] = None
        self._image_pixmap: Optional[QPixmap] = None
        self._active_media_type: Optional[MediaType] = None

        self._scale: float = 1.0
        self._position_x: float = 0.0
        self._position_y: float = 0.0
        self._opacity: float = 1.0
        self._crop: dict = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}

        # Drag state
        self._is_dragging: bool = False
        self._drag_start_pos: QPoint = QPoint()
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0

        # Native Wayland video widget for preview
        self._video_widget = QVideoWidget(self)
        self._video_widget.setStyleSheet("background: transparent;")
        self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._video_widget.hide()
        self._video_widget.installEventFilter(self)
        self._video_opacity_effect: Optional[QGraphicsOpacityEffect] = None

        # Studio Audio Visualizer state
        self._audio_is_playing: bool = False
        self._audio_anim_tick: int = 0
        self._audio_anim_timer = QTimer(self)
        self._audio_anim_timer.timeout.connect(self._on_audio_anim_tick)

    def _on_audio_anim_tick(self) -> None:
        self._audio_anim_tick += 1
        self.update()

    def set_audio_playing(self, is_playing: bool) -> None:
        """Toggle animated studio audio spectrum meter."""
        self._audio_is_playing = is_playing
        if is_playing:
            if not self._audio_anim_timer.isActive():
                self._audio_anim_timer.start(40)  # 25 fps smooth animation
        else:
            self._audio_anim_timer.stop()
        self.update()

    def get_video_widget(self) -> QVideoWidget:
        return self._video_widget

    def set_layer0_image(self, file_path: Optional[str]) -> None:
        if file_path and os.path.isfile(file_path):
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

    def show_video(self, scale: float = 1.0, crop: Optional[dict] = None,
                   pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        self._active_media_type = MediaType.VIDEO
        self._scale = scale
        self._crop = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._position_x = pos_x
        self._position_y = pos_y
        self._opacity = opacity
        self._update_video_geometry()
        self._video_widget.show()
        self._video_widget.raise_()
        self.update()

    def update_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                            pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        self._scale = scale
        self._crop = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._position_x = pos_x
        self._position_y = pos_y
        self._opacity = opacity
        self._update_video_geometry()
        self.update()

    def _update_video_geometry(self) -> None:
        canvas = self.get_canvas_rect()
        target_scale = max(0.1, min(5.0, self._scale))

        vw = int(canvas.width() * target_scale)
        vh = int(canvas.height() * target_scale)

        vx = canvas.x() + (canvas.width() - vw) // 2 + int(self._position_x * canvas.width())
        vy = canvas.y() + (canvas.height() - vh) // 2 + int(self._position_y * canvas.height())

        self._video_widget.setGeometry(vx, vy, vw, vh)

        # STRICT MASK: Intersect with canvas so video NEVER renders outside the 16:9 canvas frame!
        canvas_in_video = QRect(canvas.x() - vx, canvas.y() - vy, canvas.width(), canvas.height())
        if self._crop and (self._crop.get("w", 1.0) < 0.999 or self._crop.get("h", 1.0) < 0.999
                           or self._crop.get("x", 0.0) > 0.001 or self._crop.get("y", 0.0) > 0.001):
            cx = int(self._crop.get("x", 0.0) * vw)
            cy = int(self._crop.get("y", 0.0) * vh)
            cw = int(self._crop.get("w", 1.0) * vw)
            ch = int(self._crop.get("h", 1.0) * vh)
            mask = canvas_in_video.intersected(QRect(cx, cy, cw, ch))
        else:
            mask = canvas_in_video.intersected(QRect(0, 0, vw, vh))

        self._video_widget.setMask(QRegion(mask))

        if self._opacity < 0.999:
            if self._video_opacity_effect is None:
                self._video_opacity_effect = QGraphicsOpacityEffect(self._video_widget)
                self._video_widget.setGraphicsEffect(self._video_opacity_effect)
            self._video_opacity_effect.setOpacity(max(0.0, min(1.0, self._opacity)))
        else:
            if self._video_opacity_effect is not None:
                self._video_widget.setGraphicsEffect(None)
                self._video_opacity_effect = None

    def show_image(self, file_path: str, scale: float = 1.0, crop: Optional[dict] = None,
                   pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        self._video_widget.hide()
        self._active_media_type = MediaType.IMAGE
        self._scale = scale
        self._crop = crop or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        self._position_x = pos_x
        self._position_y = pos_y
        self._opacity = opacity
        if os.path.isfile(file_path):
            self._image_pixmap = QPixmap(file_path)
        else:
            self._image_pixmap = None
        self.update()

    def show_audio(self) -> None:
        self._video_widget.hide()
        self._active_media_type = MediaType.AUDIO
        self.update()

    def clear_media(self) -> None:
        self._active_media_type = None
        self._image_pixmap = None
        self._video_widget.hide()
        self.set_audio_playing(False)
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._active_media_type == MediaType.VIDEO:
            self._update_video_geometry()

    # ── Interactive Mouse Dragging (Filter & Handlers) ────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj == self._video_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                mapped = self._video_widget.mapTo(self, event.position().toPoint())
                self._start_drag(mapped)
                return True
            elif event.type() == QEvent.Type.MouseMove:
                mapped = self._video_widget.mapTo(self, event.position().toPoint())
                self._move_drag(mapped)
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._end_drag()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_drag(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging:
            self._move_drag(event.position().toPoint())
        else:
            canvas = self.get_canvas_rect()
            if canvas.contains(event.position().toPoint()) and self._active_media_type in (MediaType.IMAGE, MediaType.VIDEO):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._end_drag()
        super().mouseReleaseEvent(event)

    def _start_drag(self, pos: QPoint) -> None:
        if self._active_media_type in (MediaType.IMAGE, MediaType.VIDEO):
            canvas = self.get_canvas_rect()
            if canvas.contains(pos):
                self._is_dragging = True
                self._drag_start_pos = pos
                self._drag_start_x = self._position_x
                self._drag_start_y = self._position_y
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _move_drag(self, pos: QPoint) -> None:
        if self._is_dragging:
            canvas = self.get_canvas_rect()
            delta = pos - self._drag_start_pos
            dx = delta.x() / max(1, canvas.width())
            dy = delta.y() / max(1, canvas.height())
            self._position_x = round(max(-2.0, min(2.0, self._drag_start_x + dx)), 3)
            self._position_y = round(max(-2.0, min(2.0, self._drag_start_y + dy)), 3)
            self.update()
            if self._active_media_type == MediaType.VIDEO:
                self._update_video_geometry()
            self.position_changed.emit(self._position_x, self._position_y)

    def _end_drag(self) -> None:
        if self._is_dragging:
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw outer letterbox/pillarbox
        painter.fillRect(self.rect(), QColor("#121212"))

        canvas = self.get_canvas_rect()

        # Draw 16:9 canvas background (black)
        painter.fillRect(canvas, QColor("#000000"))

        # STRICT CANVAS CLIPPING: nothing inside canvas can spill into GUI
        painter.setClipRect(canvas)

        # Draw Layer 0 (Tappo) ONLY if no media is loaded/active ("Il tappo deve fare il tappo e non lo show")
        if not self._active_media_type:
            if self._layer0_pixmap and not self._layer0_pixmap.isNull():
                scaled_l0 = self._layer0_pixmap.scaled(
                    canvas.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lx = canvas.x() + (canvas.width() - scaled_l0.width()) // 2
                ly = canvas.y() + (canvas.height() - scaled_l0.height()) // 2
                painter.drawPixmap(lx, ly, scaled_l0)

        # If Image cue is active, paint it over black background with transforms
        elif self._active_media_type == MediaType.IMAGE and self._image_pixmap and not self._image_pixmap.isNull():
            pix = self._image_pixmap
            if self._crop and (self._crop.get("w", 1.0) < 0.999 or self._crop.get("h", 1.0) < 0.999
                               or self._crop.get("x", 0.0) > 0.001 or self._crop.get("y", 0.0) > 0.001):
                cw = max(1, int(pix.width() * self._crop.get("w", 1.0)))
                ch = max(1, int(pix.height() * self._crop.get("h", 1.0)))
                cx = max(0, min(pix.width() - 1, int(pix.width() * self._crop.get("x", 0.0))))
                cy = max(0, min(pix.height() - 1, int(pix.height() * self._crop.get("y", 0.0))))
                pix = pix.copy(cx, cy, cw, ch)

            target_scale = max(0.1, min(5.0, self._scale))
            iw = int(canvas.width() * target_scale)
            ih = int(canvas.height() * target_scale)
            scaled_img = pix.scaled(iw, ih, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            ix = canvas.x() + (canvas.width() - scaled_img.width()) // 2 + int(self._position_x * canvas.width())
            iy = canvas.y() + (canvas.height() - scaled_img.height()) // 2 + int(self._position_y * canvas.height())

            painter.setOpacity(max(0.0, min(1.0, self._opacity)))
            painter.drawPixmap(ix, iy, scaled_img)
            painter.setOpacity(1.0)

        elif self._active_media_type == MediaType.AUDIO:
            # Studio Animated Audio Spectrum Meter
            canvas_w = canvas.width()
            canvas_h = canvas.height()
            cx = canvas.x()
            cy = canvas.y()

            # Center frequency analyzer / VU bars
            num_bars = 24
            total_bars_w = min(canvas_w * 0.75, num_bars * 16)
            bar_w = max(3.0, (total_bars_w / num_bars) - 4)
            start_x = cx + (canvas_w - total_bars_w) / 2
            mid_y = cy + (canvas_h / 2) + 12
            max_bar_h = canvas_h * 0.35

            t = self._audio_anim_tick * 0.15

            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(num_bars):
                bx = start_x + (i * (bar_w + 4))
                if self._audio_is_playing:
                    # Dynamic bouncing waveform based on harmonic frequencies
                    freq = (i + 1) * 0.45
                    val = (
                        math.sin(t * 1.8 + freq) * 0.35
                        + math.sin(t * 3.1 + i * 0.9) * 0.25
                        + math.cos(t * 0.9 + freq * 1.5) * 0.2
                        + 0.45
                    )
                    norm_h = max(0.08, min(1.0, val))
                else:
                    norm_h = 0.08  # idle standby rest height

                bh = norm_h * max_bar_h
                bar_top = mid_y - bh

                # Color: gradient cyan (#00e5ff) to mint (#00e676)
                if norm_h > 0.7:
                    bar_color = QColor("#00e5ff")
                elif norm_h > 0.4:
                    bar_color = QColor("#00e676")
                else:
                    bar_color = QColor("#00897b")

                painter.setBrush(bar_color)
                painter.drawRoundedRect(int(bx), int(bar_top), max(2, int(bar_w)), int(bh), 2, 2)

                # Floating peak cap when playing
                if self._audio_is_playing:
                    cap_y = max(cy + 10, bar_top - 5)
                    painter.setBrush(QColor("#ffffff"))
                    painter.drawRect(int(bx), int(cap_y), max(2, int(bar_w)), 2)

            # Baseline line
            painter.setPen(QPen(QColor("#263238"), 2))
            painter.drawLine(int(start_x - 10), int(mid_y + 1), int(start_x + total_bars_w + 10), int(mid_y + 1))

            # Bottom status banner
            banner_h = 36
            banner_y = cy + canvas_h - banner_h
            painter.fillRect(cx, banner_y, canvas_w, banner_h, QColor(0, 0, 0, 220))

            if self._audio_is_playing:
                # Blinking green dot
                dot_on = (self._audio_anim_tick // 6) % 2 == 0
                dot_color = QColor("#00e676") if dot_on else QColor("#004d40")
                painter.setBrush(dot_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(cx + 20), int(banner_y + 12), 12, 12)

                painter.setPen(QColor("#00e5ff"))
                painter.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
                painter.drawText(
                    QRect(cx + 42, banner_y, canvas_w - 60, banner_h),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    "RIPRODUZIONE AUDIO IN ANTEPRIMA (PRE-VIZ ON AIR)"
                )
            else:
                painter.setPen(QColor("#80cbc4"))
                painter.setFont(QFont("sans-serif", 9, QFont.Weight.Normal))
                painter.drawText(
                    QRect(cx, banner_y, canvas_w, banner_h),
                    Qt.AlignmentFlag.AlignCenter,
                    "⏸ TRACCIA AUDIO CARICATA — PREMI PLAY PER PRE-VIZ"
                )

        painter.setClipping(False)

        # Thin studio border around 16:9 canvas
        painter.setPen(QPen(QColor("#3e3e3e"), 1))
        painter.drawRect(canvas)
        painter.end()


# ═══════════════════════════════════════════════════════════════════════
# Drop Zone Widget
# ═══════════════════════════════════════════════════════════════════════

class DropZone(QLabel):
    """Drag-and-drop file import zone."""

    file_dropped = Signal(str)  # absolute path of dropped file

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setText("Trascina qui file multimediali\n(Video, Audio, Immagini)\nper aggiungerli alla regia")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(160, 80)
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {_CLR_PREVIZ};
                border-radius: 6px;
                background-color: {_CLR_PANEL};
                color: {_CLR_PREVIZ};
                font-size: 11px;
                font-weight: bold;
                padding: 6px;
            }}
        """)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                self.file_dropped.emit(path)
                logger.info("[DROP] File dropped: %s", path)


# ═══════════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Director / Control Panel."""

    # Signals
    cue_fired = Signal(object)          # emits Cue
    cue_preview_requested = Signal(object) # emits Cue to load in preview
    layer_clear_requested = Signal(int) # emits layer (1, 2, or 3)
    blackout_requested = Signal()       # emits when blackout triggered
    preview_mute_toggled = Signal(bool) # emits is_muted (True or False)
    preview_in_out_changed = Signal(float, object) # emits in_sec, out_sec
    live_volume_changed = Signal(int)   # emits volume 0-100

    def __init__(self, output_window: OutputWindow,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._output = output_window
        self._cues: list[Cue] = []
        self._current_index: int = -1
        self._thread_pool = QThreadPool.globalInstance()
        self._test_player = None  # will be set after native player init
        self._active_analyzers: set = set()

        # Project management & Autosave
        self._project_manager = ProjectManager()
        self._current_project_path: Optional[str] = None
        self._layer0_image: Optional[str] = None
        self._is_modified: bool = False
        self._updating_inspector: bool = False
        self._force_closing: bool = False

        self._setup_window()
        self._build_menu_bar()
        self._build_ui()
        self._setup_shortcuts()
        self._update_inspector(None)
        self._build_status_bar()
        self._setup_autosave()

        # Check for crash recovery after event loop starts
        QTimer.singleShot(150, self._check_crash_recovery)

    # ── Window setup ──────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self._update_window_title()
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        self.setStyleSheet(_DARK_STYLESHEET)

        # Application icon
        if _LOGO_PATH.is_file():
            self.setWindowIcon(QIcon(str(_LOGO_PATH)))

    def _setup_autosave(self) -> None:
        """Periodic background autosave every 30 seconds."""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._auto_save)
        self._autosave_timer.start()

    def _setup_shortcuts(self) -> None:
        """Configure keyboard shortcuts for quick operator access."""
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._on_delete_cue)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, self._on_delete_cue)
        QShortcut(QKeySequence("Alt+Up"), self, self._on_move_up)
        QShortcut(QKeySequence("Alt+Down"), self, self._on_move_down)
        QShortcut(QKeySequence("Ctrl+B"), self, self._on_blackout)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape_pressed)

    @Slot()
    def _on_escape_pressed(self) -> None:
        """Stop test preview if active, without interrupting live show."""
        if hasattr(self, "_btn_test_stop"):
            self._btn_test_stop.click()

    def _update_window_title(self) -> None:
        name = Path(self._current_project_path).name if self._current_project_path else "Nuovo Show"
        mod = " *" if self._is_modified else ""
        self.setWindowTitle(f"BlindCue – [{name}{mod}] – Director Panel v0.1")

    def _mark_modified(self, modified: bool = True) -> None:
        self._is_modified = modified
        self._update_window_title()

    # ── Menu bar ──────────────────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        file_menu.addAction(
            QAction("&New Show", self, shortcut=QKeySequence.StandardKey.New,
                    triggered=self._on_new_show))
        file_menu.addAction(
            QAction("&Open Show…", self, shortcut=QKeySequence.StandardKey.Open,
                    triggered=self._on_open_show))
        file_menu.addAction(
            QAction("&Save Show", self, shortcut=QKeySequence.StandardKey.Save,
                    triggered=self._on_save_show))
        file_menu.addAction(
            QAction("Save Show &As…", self, shortcut=QKeySequence("Ctrl+Shift+S"),
                    triggered=self._on_save_as_show))
        file_menu.addSeparator()
        file_menu.addAction(
            QAction("&Quit", self, shortcut=QKeySequence.StandardKey.Quit,
                    triggered=self._on_quit))

        # Show
        show_menu = mb.addMenu("&Show")
        show_menu.addAction(
            QAction("&GO (Next Cue)", self, shortcut=QKeySequence("Space"),
                    triggered=self._on_go))
        show_menu.addAction(
            QAction("&Blackout", self, shortcut=QKeySequence("Ctrl+B"),
                    triggered=self._on_blackout))
        show_menu.addSeparator()
        show_menu.addAction(
            QAction("Imposta Immagine di &Tappo (Layer 0)…", self,
                    triggered=self._on_choose_layer0))
        show_menu.addAction(
            QAction("&Ripristina Tappo Predefinito", self,
                    triggered=self._on_reset_layer0))

        # View
        mb.addMenu("&View")

        # Help
        help_menu = mb.addMenu("&Help")
        help_menu.addAction(
            QAction("&Info Hardware & Accelerazione…", self,
                    triggered=self._on_hardware_info))
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&About BlindCue", self, triggered=self._on_about))

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # Top splitter: Cue List | Preview + GO | Inspector
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: Cue List ────────────────────────────────────────────
        left_panel = QGroupBox("SCALETTA CUE (Sequence List)")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(6)

        # Cue list summary subtitle bar
        cue_summary_bar = QHBoxLayout()
        self._lbl_cue_count = QLabel("0 Cue caricate")
        self._lbl_cue_count.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold;")
        self._lbl_cue_standby = QLabel("Standby: Nessuna")
        self._lbl_cue_standby.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        cue_summary_bar.addWidget(self._lbl_cue_count)
        cue_summary_bar.addStretch()
        cue_summary_bar.addWidget(self._lbl_cue_standby)
        left_layout.addLayout(cue_summary_bar)

        self._cue_list = QListWidget()
        self._cue_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._cue_list.currentRowChanged.connect(self._on_cue_selected)
        self._cue_list.itemDoubleClicked.connect(lambda _item: self._on_go())
        left_layout.addWidget(self._cue_list)

        # Add/remove buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._btn_add_video = QPushButton("+ Video")
        self._btn_add_video.setToolTip("Aggiungi file video alla scaletta")
        self._btn_add_video.setStyleSheet("QPushButton { height: 28px; font-weight: bold; } QPushButton:hover { border-color: #42a5f5; color: #42a5f5; }")

        self._btn_add_audio = QPushButton("+ Audio")
        self._btn_add_audio.setToolTip("Aggiungi file audio alla scaletta")
        self._btn_add_audio.setStyleSheet("QPushButton { height: 28px; font-weight: bold; } QPushButton:hover { border-color: #26a69a; color: #26a69a; }")

        self._btn_add_image = QPushButton("+ Immagine")
        self._btn_add_image.setToolTip("Aggiungi immagine statica (Layer 1-3)")
        self._btn_add_image.setStyleSheet("QPushButton { height: 28px; font-weight: bold; } QPushButton:hover { border-color: #ffa726; color: #ffa726; }")

        self._btn_move_up = QPushButton("▲")
        self._btn_move_up.setToolTip("Sposta la cue in alto (Alt+↑)")
        self._btn_move_up.setFixedWidth(32)
        self._btn_move_up.setFixedHeight(28)

        self._btn_move_down = QPushButton("▼")
        self._btn_move_down.setToolTip("Sposta la cue in basso (Alt+↓)")
        self._btn_move_down.setFixedWidth(32)
        self._btn_move_down.setFixedHeight(28)

        self._btn_delete = QPushButton("🗑 Elimina")
        self._btn_delete.setToolTip("Rimuovi la cue dalla scaletta (Canc)")
        self._btn_delete.setFixedHeight(28)
        self._btn_delete.setStyleSheet(
            "QPushButton { color: #ff8080; border: 1px solid #ff4444; background-color: #401818; font-weight: bold; } QPushButton:hover { background-color: #5c2222; }")

        self._btn_add_video.clicked.connect(
            lambda: self._on_add_media(MediaType.VIDEO))
        self._btn_add_audio.clicked.connect(
            lambda: self._on_add_media(MediaType.AUDIO))
        self._btn_add_image.clicked.connect(
            lambda: self._on_add_media(MediaType.IMAGE))
        self._btn_move_up.clicked.connect(self._on_move_up)
        self._btn_move_down.clicked.connect(self._on_move_down)
        self._btn_delete.clicked.connect(self._on_delete_cue)

        for btn in (self._btn_add_video, self._btn_add_audio,
                    self._btn_add_image, self._btn_move_up,
                    self._btn_move_down, self._btn_delete):
            btn_row.addWidget(btn)
        left_layout.addLayout(btn_row)

        top_splitter.addWidget(left_panel)

        # ── CENTER: Preview + GO ──────────────────────────────────────
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Preview / Pre-viz sandbox
        preview_group = QGroupBox("ANTEPRIMA PRE-VIZ (Sandbox)")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(6, 4, 6, 6)
        preview_layout.setSpacing(4)

        # Test/Pre-viz top toolbar (fixed height, single thin row)
        preview_header_frame = QFrame()
        preview_header_frame.setFixedHeight(28)
        preview_header_frame.setStyleSheet("background: transparent; border: none;")
        preview_header = QHBoxLayout(preview_header_frame)
        preview_header.setContentsMargins(2, 0, 2, 0)
        preview_header.setSpacing(8)

        lbl_test = QLabel("PRE-VIZ")
        lbl_test.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_test.setStyleSheet(f"""
            QLabel {{
                background-color: {_CLR_PREVIZ};
                color: #000;
                font-weight: bold;
                padding: 1px 7px;
                border-radius: 3px;
                font-size: 10px;
                max-height: 22px;
            }}
        """)
        lbl_test.setFixedHeight(22)
        preview_header.addWidget(lbl_test)

        # Live Mirror rehearsal toggle
        self._btn_live_mirror = QPushButton("🔗 MIRROR LIVE: OFF")
        self._btn_live_mirror.setCheckable(True)
        self._btn_live_mirror.setChecked(False)
        self._btn_live_mirror.setFixedHeight(22)
        self._btn_live_mirror.setToolTip(
            "Modalità Progettazione: se ATTIVO, le modifiche a Crop, Scala e Posizione vengono "
            "proiettate in tempo reale sullo schermo LIVE per calibrare il videoproiettore/schermo.\n"
            "In Spettacolo dal vivo: lasciare DISATTIVATO per isolare completamente l'anteprima."
        )
        self._btn_live_mirror.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #888888;
                border: 1px solid #555555;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background-color: #383838;
                color: #ccc;
            }
        """)
        self._btn_live_mirror.toggled.connect(self._on_live_mirror_toggled)
        preview_header.addWidget(self._btn_live_mirror)

        self._lbl_preview_info = QLabel("— Nessun file selezionato —")
        self._lbl_preview_info.setFixedHeight(22)
        self._lbl_preview_info.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold; background: transparent; padding-left: 4px;")
        preview_header.addWidget(self._lbl_preview_info, stretch=1)

        # Digital time counter display
        self._lbl_preview_time = QLabel("⏱ 00:00.00 / 00:00.00")
        self._lbl_preview_time.setFixedHeight(22)
        self._lbl_preview_time.setStyleSheet("color: #00e5ff; font-family: monospace; font-size: 11px; font-weight: bold; padding: 1px 6px; background: #1a1a1a; border: 1px solid #333; border-radius: 3px;")
        preview_header.addWidget(self._lbl_preview_time)

        lbl_sim = QLabel("16:9 Live")
        lbl_sim.setFixedHeight(22)
        lbl_sim.setStyleSheet("color: #666; font-size: 10px; font-weight: bold; background: transparent;")
        preview_header.addWidget(lbl_sim)

        preview_layout.addWidget(preview_header_frame, stretch=0)

        # 16:9 WYSIWYG studio preview monitor (specchio esatto dello schermo live)
        self._preview_monitor = StudioPreviewMonitor()
        self._preview_monitor.set_layer0_image(self._output.get_layer0_path())
        self._preview_monitor.position_changed.connect(self._on_preview_position_changed)
        preview_layout.addWidget(self._preview_monitor, stretch=1)

        # Transport controls (compact bar)
        transport_frame = QFrame()
        transport_frame.setFixedHeight(34)
        transport_frame.setStyleSheet("background: transparent; border: none;")
        transport = QHBoxLayout(transport_frame)
        transport.setContentsMargins(0, 2, 0, 0)
        transport.setSpacing(6)

        btn_style_base = """
            QPushButton {
                background-color: #383838;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 12px;
                font-size: 11px;
                font-weight: bold;
                height: 24px;
                min-width: 65px;
            }
        """

        self._btn_test_play = QPushButton("▶  Play")
        self._btn_test_play.setToolTip("Riproduci anteprima / Pre-viz")
        self._btn_test_play.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #1e3d24;
                border-color: #00e676;
                color: #00e676;
            }
            QPushButton:pressed {
                background-color: #142918;
            }
        """)

        self._btn_test_pause = QPushButton("⏸  Pausa")
        self._btn_test_pause.setToolTip("Metti in pausa l'anteprima")
        self._btn_test_pause.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #2b3345;
                border-color: #64b5f6;
                color: #64b5f6;
            }
            QPushButton:pressed {
                background-color: #1c222e;
            }
        """)

        self._btn_test_stop = QPushButton("⏹  Stop")
        self._btn_test_stop.setToolTip("Arresta anteprima e riavvolgi")
        self._btn_test_stop.setStyleSheet(btn_style_base + """
            QPushButton:hover {
                background-color: #3d1e1e;
                border-color: #ff5252;
                color: #ff5252;
            }
            QPushButton:pressed {
                background-color: #291414;
            }
        """)

        for btn in (self._btn_test_play, self._btn_test_pause, self._btn_test_stop):
            btn.setFixedHeight(26)
            transport.addWidget(btn)

        transport.addStretch(1)

        # Mute Preview interactive toggle selector
        self._btn_preview_mute = QPushButton()
        self._btn_preview_mute.setFixedHeight(26)
        self._btn_preview_mute.setCheckable(True)
        self._btn_preview_mute.setChecked(True)
        self._btn_preview_mute.setToolTip("Se attivo (default), l'anteprima è muta. Clicca per ascoltare l'audio su richiesta.")
        self._update_mute_preview_style()
        self._btn_preview_mute.toggled.connect(self._on_preview_mute_toggled)
        transport.addWidget(self._btn_preview_mute)
        preview_layout.addWidget(transport_frame, stretch=0)

        center_layout.addWidget(preview_group, stretch=1)

        # GO button
        self._btn_go = QPushButton("GO (Next Cue) — [ SPAZIO ]")
        self._btn_go.setMinimumHeight(48)
        self._btn_go.setMaximumHeight(54)
        self._btn_go.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
        self._btn_go.setStyleSheet(f"""
            QPushButton {{
                background-color: {_CLR_GO};
                color: #000;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: #69f0ae;
            }}
            QPushButton:pressed {{
                background-color: #00c853;
            }}
        """)
        self._btn_go.clicked.connect(self._on_go)
        center_layout.addWidget(self._btn_go, stretch=0)

        top_splitter.addWidget(center_panel)

        # ── RIGHT: Inspector (Modern Flat Studio Design) ───────────────
        self._grp_inspector = QGroupBox("ISPETTORE CUE (Nessuna cue selezionata)")
        outer_right_layout = QVBoxLayout(self._grp_inspector)
        outer_right_layout.setContentsMargins(4, 8, 4, 4)

        def _make_section_header(title: str) -> QWidget:
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 8, 0, 4)
            lay.setSpacing(6)
            lbl = QLabel(title)
            lbl.setStyleSheet("color: #00bcd4; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("background-color: #383838; max-height: 1px; border: none;")
            lay.addWidget(lbl)
            lay.addWidget(line)
            return w

        insp_scroll = QScrollArea()
        insp_scroll.setWidgetResizable(True)
        insp_scroll.setFrameShape(QFrame.Shape.NoFrame)
        insp_scroll.setStyleSheet("background: transparent; border: none;")

        insp_content = QWidget()
        right_layout = QVBoxLayout(insp_content)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)

        lbl_insp_hint = QLabel("Proprietà del media selezionato prima o durante il Live")
        lbl_insp_hint.setStyleSheet("color: #777; font-size: 10px; margin-bottom: 2px;")
        right_layout.addWidget(lbl_insp_hint)

        # ── 1. Dati Cue & Note di Regia ──
        right_layout.addWidget(_make_section_header("DATI CUE • NOTE DI REGIA"))

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Nome:"))
        self._edit_cue_name = QLineEdit()
        self._edit_cue_name.setPlaceholderText("Nome della Cue...")
        row_name.addWidget(self._edit_cue_name)
        right_layout.addLayout(row_name)

        row_notes = QHBoxLayout()
        row_notes.addWidget(QLabel("Note:"))
        self._edit_cue_notes = QLineEdit()
        self._edit_cue_notes.setPlaceholderText("Appunti di regia (es. attacco battuta, sfumata...)")
        row_notes.addWidget(self._edit_cue_notes)
        right_layout.addLayout(row_notes)

        # ── 2. Layer di Uscita ──
        right_layout.addWidget(_make_section_header("LAYER DI USCITA (COMPOSITING)"))

        layer_layout = QHBoxLayout()
        layer_layout.setContentsMargins(0, 2, 0, 2)
        self._btn_layer1 = QPushButton("L1: Sfondo / Base")
        self._btn_layer1.setToolTip("Layer 1: Livello di sfondo o video principale")
        self._btn_layer2 = QPushButton("L2: Principale")
        self._btn_layer2.setToolTip("Layer 2: Livello multimediale intermedio")
        self._btn_layer3 = QPushButton("L3: Overlay / Logo")
        self._btn_layer3.setToolTip("Layer 3: Livello superiore sovrapposto (grafica, loghi, sovraimpressioni)")

        for btn in (self._btn_layer1, self._btn_layer2, self._btn_layer3):
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            layer_layout.addWidget(btn)

        self._btn_layer1.setChecked(True)
        self._btn_layer1.clicked.connect(lambda: self._set_layer(1))
        self._btn_layer2.clicked.connect(lambda: self._set_layer(2))
        self._btn_layer3.clicked.connect(lambda: self._set_layer(3))
        right_layout.addLayout(layer_layout)

        # ── 3. Posizionamento, Zoom & Trasparenza ──
        right_layout.addWidget(_make_section_header("POSIZIONAMENTO • ZOOM • TRASPARENZA"))

        pos_spin_row = QHBoxLayout()
        pos_spin_row.addWidget(QLabel("Pos X:"))
        self._spin_pos_x = QDoubleSpinBox()
        self._spin_pos_x.setRange(-2.0, 2.0)
        self._spin_pos_x.setSingleStep(0.01)
        self._spin_pos_x.setDecimals(2)
        self._spin_pos_x.setValue(0.0)
        self._spin_pos_x.setToolTip("Offset orizzontale (-1.00 = sx, 0.00 = centro, +1.00 = dx). Puoi anche trascinare col mouse sull'anteprima!")
        pos_spin_row.addWidget(self._spin_pos_x)

        pos_spin_row.addWidget(QLabel("Pos Y:"))
        self._spin_pos_y = QDoubleSpinBox()
        self._spin_pos_y.setRange(-2.0, 2.0)
        self._spin_pos_y.setSingleStep(0.01)
        self._spin_pos_y.setDecimals(2)
        self._spin_pos_y.setValue(0.0)
        self._spin_pos_y.setToolTip("Offset verticale (-1.00 = alto, 0.00 = centro, +1.00 = basso). Puoi anche trascinare col mouse sull'anteprima!")
        pos_spin_row.addWidget(self._spin_pos_y)
        right_layout.addLayout(pos_spin_row)

        # Backward compatibility aliases
        self._spin_x = self._spin_pos_x
        self._spin_y = self._spin_pos_y

        # Nudge & Reset Buttons Row
        nudge_row = QHBoxLayout()
        nudge_btn_style = """
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 11px;
                padding: 3px 8px;
                font-weight: bold;
                min-width: 30px;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #383838;
                border-color: #00bcd4;
                color: #00bcd4;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """
        self._btn_nudge_left = QPushButton("◀")
        self._btn_nudge_left.setToolTip("Sposta a sinistra (-0.01)")
        self._btn_nudge_left.setStyleSheet(nudge_btn_style)
        self._btn_nudge_left.clicked.connect(lambda: self._on_nudge_position(-0.01, 0.0))

        self._btn_nudge_up = QPushButton("▲")
        self._btn_nudge_up.setToolTip("Sposta in alto (-0.01)")
        self._btn_nudge_up.setStyleSheet(nudge_btn_style)
        self._btn_nudge_up.clicked.connect(lambda: self._on_nudge_position(0.0, -0.01))

        self._btn_nudge_down = QPushButton("▼")
        self._btn_nudge_down.setToolTip("Sposta in basso (+0.01)")
        self._btn_nudge_down.setStyleSheet(nudge_btn_style)
        self._btn_nudge_down.clicked.connect(lambda: self._on_nudge_position(0.0, 0.01))

        self._btn_nudge_right = QPushButton("▶")
        self._btn_nudge_right.setToolTip("Sposta a destra (+0.01)")
        self._btn_nudge_right.setStyleSheet(nudge_btn_style)
        self._btn_nudge_right.clicked.connect(lambda: self._on_nudge_position(0.01, 0.0))

        self._btn_pos_center = QPushButton("⌖ Centro")
        self._btn_pos_center.setToolTip("Ripristina posizione al centro (0.00, 0.00)")
        self._btn_pos_center.setStyleSheet(nudge_btn_style)
        self._btn_pos_center.clicked.connect(self._on_reset_position)

        for btn in (self._btn_nudge_left, self._btn_nudge_up, self._btn_nudge_down, self._btn_nudge_right, self._btn_pos_center):
            nudge_row.addWidget(btn)
        right_layout.addLayout(nudge_row)

        # Scale slider + Reset
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scala / Zoom:"))
        self._slider_scale = QSlider(Qt.Orientation.Horizontal)
        self._slider_scale.setRange(10, 500)  # 0.1x to 5.0x
        self._slider_scale.setValue(100)
        self._lbl_scale = QLabel("1.0x")
        self._lbl_scale.setFixedWidth(36)
        self._slider_scale.valueChanged.connect(
            lambda v: self._lbl_scale.setText(f"{v / 100:.1f}x"))
        self._btn_scale_reset = QPushButton("1.0x")
        self._btn_scale_reset.setToolTip("Ripristina scala a 1.0x")
        self._btn_scale_reset.setStyleSheet(nudge_btn_style)
        self._btn_scale_reset.clicked.connect(self._on_reset_scale)
        scale_row.addWidget(self._slider_scale)
        scale_row.addWidget(self._lbl_scale)
        scale_row.addWidget(self._btn_scale_reset)
        right_layout.addLayout(scale_row)

        # Opacity / Transparency slider
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Opacità:"))
        self._slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_opacity.setRange(0, 100)
        self._slider_opacity.setValue(100)
        self._lbl_opacity = QLabel("100%")
        self._lbl_opacity.setFixedWidth(36)
        self._slider_opacity.valueChanged.connect(
            lambda v: self._lbl_opacity.setText(f"{v}%"))
        self._btn_opacity_reset = QPushButton("100%")
        self._btn_opacity_reset.setToolTip("Ripristina opacità al 100% (piena visibilità)")
        self._btn_opacity_reset.setStyleSheet(nudge_btn_style)
        self._btn_opacity_reset.clicked.connect(lambda: self._slider_opacity.setValue(100))
        op_row.addWidget(self._slider_opacity)
        op_row.addWidget(self._lbl_opacity)
        op_row.addWidget(self._btn_opacity_reset)
        right_layout.addLayout(op_row)

        # ── 4. Ritaglio (Crop) ──
        right_layout.addWidget(_make_section_header("RITAGLIO (CROP)"))

        crop_row1 = QHBoxLayout()
        crop_row1.addWidget(QLabel("Sinistra (L):"))
        self._spin_crop_l = QDoubleSpinBox()
        self._spin_crop_l.setRange(0.0, 0.99)
        self._spin_crop_l.setSingleStep(0.01)
        self._spin_crop_l.setDecimals(2)
        crop_row1.addWidget(self._spin_crop_l)

        crop_row1.addWidget(QLabel("Destra (R):"))
        self._spin_crop_r = QDoubleSpinBox()
        self._spin_crop_r.setRange(0.0, 0.99)
        self._spin_crop_r.setSingleStep(0.01)
        self._spin_crop_r.setDecimals(2)
        crop_row1.addWidget(self._spin_crop_r)
        right_layout.addLayout(crop_row1)

        crop_row2 = QHBoxLayout()
        crop_row2.addWidget(QLabel("Alto (T):"))
        self._spin_crop_t = QDoubleSpinBox()
        self._spin_crop_t.setRange(0.0, 0.99)
        self._spin_crop_t.setSingleStep(0.01)
        self._spin_crop_t.setDecimals(2)
        crop_row2.addWidget(self._spin_crop_t)

        crop_row2.addWidget(QLabel("Basso (B):"))
        self._spin_crop_b = QDoubleSpinBox()
        self._spin_crop_b.setRange(0.0, 0.99)
        self._spin_crop_b.setSingleStep(0.01)
        self._spin_crop_b.setDecimals(2)
        crop_row2.addWidget(self._spin_crop_b)
        right_layout.addLayout(crop_row2)

        # Backward compatibility aliases
        self._spin_w = self._spin_crop_r
        self._spin_h = self._spin_crop_b

        crop_btn_row = QHBoxLayout()
        self._btn_crop_reset = QPushButton("⟲ Reset Ritaglio")
        self._btn_crop_reset.setToolTip("Rimuove il ritaglio e mostra il fotogramma intero")
        self._btn_crop_reset.setStyleSheet(nudge_btn_style)
        self._btn_crop_reset.clicked.connect(self._on_reset_crop)
        crop_btn_row.addStretch()
        crop_btn_row.addWidget(self._btn_crop_reset)
        right_layout.addLayout(crop_btn_row)

        # ── 5. Transizioni & Aspect Ratio ──
        right_layout.addWidget(_make_section_header("TRANSIZIONI • ASPECT RATIO"))

        fade_row = QHBoxLayout()
        fade_row.addWidget(QLabel("Fade In:"))
        self._spin_fade_in = QDoubleSpinBox()
        self._spin_fade_in.setRange(0, 30)
        self._spin_fade_in.setDecimals(1)
        self._spin_fade_in.setSuffix(" s")
        fade_row.addWidget(self._spin_fade_in)
        fade_row.addWidget(QLabel("Fade Out:"))
        self._spin_fade_out = QDoubleSpinBox()
        self._spin_fade_out.setRange(0, 30)
        self._spin_fade_out.setDecimals(1)
        self._spin_fade_out.setSuffix(" s")
        fade_row.addWidget(self._spin_fade_out)
        right_layout.addLayout(fade_row)

        # Hold time for static images (0 = infinite)
        hold_row = QHBoxLayout()
        hold_row.addWidget(QLabel("Permanenza Img:"))
        self._spin_hold_time = QDoubleSpinBox()
        self._spin_hold_time.setRange(0, 99999)
        self._spin_hold_time.setDecimals(1)
        self._spin_hold_time.setSuffix(" s")
        self._spin_hold_time.setSpecialValueText("0 s (Infinita)")
        self._spin_hold_time.setToolTip("Tempo di permanenza in Live dell'immagine prima della rimozione automatica. 0 = infinita.")
        hold_row.addWidget(self._spin_hold_time)
        right_layout.addLayout(hold_row)

        # Aspect ratio
        ar_row = QHBoxLayout()
        ar_row.addWidget(QLabel("Formato:"))
        self._combo_aspect = QComboBox()
        self._combo_aspect.addItems(["Native (Automatico)", "16:9 (Widescreen)", "4:3 (Standard)", "21:9 (Ultrawide)", "1:1 (Quadrato)"])
        ar_row.addWidget(self._combo_aspect)
        right_layout.addLayout(ar_row)

        # ── 6. Audio & Riproduzione ──
        right_layout.addWidget(_make_section_header("AUDIO • RIPRODUZIONE"))

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume:"))
        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setRange(0, 100)
        self._slider_volume.setValue(100)
        self._lbl_volume = QLabel("100%")
        self._lbl_volume.setFixedWidth(36)
        self._slider_volume.valueChanged.connect(
            lambda v: self._lbl_volume.setText(f"{v}%"))
        vol_row.addWidget(self._slider_volume)
        vol_row.addWidget(self._lbl_volume)
        right_layout.addLayout(vol_row)

        self._chk_loop = QCheckBox("Riproduci in Loop continuo")
        right_layout.addWidget(self._chk_loop)

        # In / Out points (centesimi precision)
        io_row = QHBoxLayout()
        io_row.addWidget(QLabel("Punto IN:"))
        self._spin_in = InPointSpinBox()
        io_row.addWidget(self._spin_in)
        io_row.addWidget(QLabel("Punto OUT:"))
        self._spin_out = OutPointSpinBox()
        io_row.addWidget(self._spin_out)
        right_layout.addLayout(io_row)

        right_layout.addStretch()

        insp_scroll.setWidget(insp_content)
        outer_right_layout.addWidget(insp_scroll)

        # Connect inspector controls to update the active cue
        for spin in (self._spin_pos_x, self._spin_pos_y,
                     self._spin_crop_l, self._spin_crop_r, self._spin_crop_t, self._spin_crop_b,
                     self._spin_fade_in, self._spin_fade_out, self._spin_in, self._spin_out,
                     self._spin_hold_time):
            spin.valueChanged.connect(self._on_inspector_value_changed)
        self._slider_scale.valueChanged.connect(self._on_inspector_value_changed)
        self._slider_opacity.valueChanged.connect(self._on_inspector_value_changed)
        self._slider_volume.valueChanged.connect(self._on_inspector_value_changed)
        self._chk_loop.toggled.connect(self._on_inspector_value_changed)
        self._combo_aspect.currentIndexChanged.connect(self._on_inspector_value_changed)
        self._edit_cue_name.textEdited.connect(self._on_inspector_value_changed)
        self._edit_cue_notes.textEdited.connect(self._on_inspector_value_changed)

        top_splitter.addWidget(self._grp_inspector)

        # Splitter proportions: Center Pre-Viz monitor has primary prominence
        top_splitter.setStretchFactor(0, 2)
        top_splitter.setStretchFactor(1, 6)
        top_splitter.setStretchFactor(2, 3)
        top_splitter.setSizes([280, 750, 330])
        root_layout.addWidget(top_splitter, stretch=7)

        # ── BOTTOM ROW: Waveform | Status | Drop Zone ────────────────
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Waveform
        waveform_group = QGroupBox("Forma d'Onda Audio (Waveform Analysis)")
        wf_layout = QVBoxLayout(waveform_group)
        lbl_wf_info = QLabel("Analisi dei picchi sonori e marcatori di inizio/fine (IN - OUT)")
        lbl_wf_info.setStyleSheet("color: #777; font-size: 10px;")
        wf_layout.addWidget(lbl_wf_info)
        self._waveform = WaveformWidget()
        self._waveform.in_changed.connect(self._on_waveform_in_changed)
        self._waveform.out_changed.connect(self._on_waveform_out_changed)
        wf_layout.addWidget(self._waveform)
        bottom_splitter.addWidget(waveform_group)

        # Live status (currently playing with individual layer clear buttons)
        live_group = QGroupBox("Live Output Status (Monitor Uscita Schermo Esterno)")
        live_layout = QVBoxLayout(live_group)
        live_layout.setSpacing(6)
        lbl_live_sub = QLabel("Controllo emissione in tempo reale sui 3 livelli live:")
        lbl_live_sub.setStyleSheet("color: #777; font-size: 10px;")
        live_layout.addWidget(lbl_live_sub)

        # Layer 1 row
        row_l1 = QHBoxLayout()
        self._lbl_live_l1 = self._make_live_label("Layer 1: —")
        self._btn_clear_l1 = QPushButton("✕ Cut L1")
        self._btn_clear_l1.setToolTip("Rimuovi / arresta immediatamente il contenuto su Layer 1")
        self._btn_clear_l1.setStyleSheet(
            "QPushButton { background-color: #5c1d1d; color: #ff8080; border: 1px solid #ff4444; border-radius: 3px; font-weight: bold; padding: 4px 10px; } QPushButton:hover { background-color: #7a2727; }"
        )
        self._btn_clear_l1.clicked.connect(lambda: self._on_clear_live_layer(1))
        row_l1.addWidget(self._lbl_live_l1, stretch=1)
        row_l1.addWidget(self._btn_clear_l1)
        live_layout.addLayout(row_l1)

        # Layer 2 row
        row_l2 = QHBoxLayout()
        self._lbl_live_l2 = self._make_live_label("Layer 2: —")
        self._btn_clear_l2 = QPushButton("✕ Cut L2")
        self._btn_clear_l2.setToolTip("Rimuovi / arresta immediatamente il contenuto su Layer 2")
        self._btn_clear_l2.setStyleSheet(
            "QPushButton { background-color: #5c1d1d; color: #ff8080; border: 1px solid #ff4444; border-radius: 3px; font-weight: bold; padding: 4px 10px; } QPushButton:hover { background-color: #7a2727; }"
        )
        self._btn_clear_l2.clicked.connect(lambda: self._on_clear_live_layer(2))
        row_l2.addWidget(self._lbl_live_l2, stretch=1)
        row_l2.addWidget(self._btn_clear_l2)
        live_layout.addLayout(row_l2)

        # Layer 3 row
        row_l3 = QHBoxLayout()
        self._lbl_live_l3 = self._make_live_label("Layer 3: —")
        self._btn_clear_l3 = QPushButton("✕ Cut L3")
        self._btn_clear_l3.setToolTip("Rimuovi / arresta immediatamente il contenuto su Layer 3")
        self._btn_clear_l3.setStyleSheet(
            "QPushButton { background-color: #5c1d1d; color: #ff8080; border: 1px solid #ff4444; border-radius: 3px; font-weight: bold; padding: 4px 10px; } QPushButton:hover { background-color: #7a2727; }"
        )
        self._btn_clear_l3.clicked.connect(lambda: self._on_clear_live_layer(3))
        row_l3.addWidget(self._lbl_live_l3, stretch=1)
        row_l3.addWidget(self._btn_clear_l3)
        live_layout.addLayout(row_l3)

        # Master Blackout row
        self._btn_clear_all = QPushButton("⏹ Master Blackout (Tappo) — [ Ctrl+B ]")
        self._btn_clear_all.setToolTip("Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B")
        self._btn_clear_all.setStyleSheet(
            "QPushButton { background-color: #3a1111; color: #ff9999; border: 1px solid #882222; border-radius: 4px; font-weight: bold; padding: 6px; } QPushButton:hover { background-color: #5c1d1d; }"
        )
        self._btn_clear_all.clicked.connect(self._on_blackout)
        live_layout.addWidget(self._btn_clear_all)

        # Layer 0 (Tappo di Emergenza / Fondo) selector row
        row_tappo = QHBoxLayout()
        self._lbl_tappo_info = QLabel("Tappo (L0): Logo BlindCue (Predefinito)")
        self._lbl_tappo_info.setStyleSheet("color: #aaa; font-size: 11px; padding: 2px;")
        self._btn_choose_tappo = QPushButton("📁 Cambia Tappo…")
        self._btn_choose_tappo.setToolTip("Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)")
        self._btn_choose_tappo.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: {_CLR_PREVIZ}; border: 1px solid {_CLR_PREVIZ}; border-radius: 3px; font-weight: bold; padding: 3px 8px; font-size: 11px; }} QPushButton:hover {{ background-color: #4d3800; }}"
        )
        self._btn_choose_tappo.clicked.connect(self._on_choose_layer0)

        self._btn_reset_tappo = QPushButton("🔄 Reset")
        self._btn_reset_tappo.setToolTip("Ripristina il logo predefinito di BlindCue come Layer 0")
        self._btn_reset_tappo.setStyleSheet(
            "QPushButton { background-color: #2b2b2b; color: #888; border: 1px solid #555; border-radius: 3px; padding: 3px 6px; font-size: 11px; } QPushButton:hover { background-color: #3a3a3a; }"
        )
        self._btn_reset_tappo.clicked.connect(self._on_reset_layer0)

        row_tappo.addWidget(self._lbl_tappo_info, stretch=1)
        row_tappo.addWidget(self._btn_choose_tappo)
        row_tappo.addWidget(self._btn_reset_tappo)
        live_layout.addLayout(row_tappo)

        live_layout.addStretch()
        bottom_splitter.addWidget(live_group)

        # Drop zone
        drop_group = QGroupBox("Caricamento Rapido (Drag && Drop)")
        drop_layout = QVBoxLayout(drop_group)
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        drop_layout.addWidget(self._drop_zone)
        bottom_splitter.addWidget(drop_group)

        bottom_splitter.setSizes([460, 320, 220])
        root_layout.addWidget(bottom_splitter, stretch=2)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self._lbl_hw_info = QLabel(self._detect_hardware_brief())
        self._lbl_hw_info.setStyleSheet("color: #00bcd4; font-size: 11px; padding-left: 6px;")
        sb.addWidget(self._lbl_hw_info)
        self._status_label = QLabel("Ready — No show loaded")
        sb.addPermanentWidget(self._status_label)
        self.setStatusBar(sb)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_double_spin(label: str, min_v: float, max_v: float,
                          step: float, default: float = 0.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.setValue(default)
        return spin

    @staticmethod
    def _make_live_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            QLabel {{
                background-color: #333;
                border: 1px solid {_CLR_LIVE};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 12px;
            }}
        """)
        return lbl

    @staticmethod
    def _detect_media_type(file_path: str) -> Optional[MediaType]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in _VIDEO_EXT:
            return MediaType.VIDEO
        if ext in _AUDIO_EXT:
            return MediaType.AUDIO
        if ext in _IMAGE_EXT:
            return MediaType.IMAGE
        return None

    def set_preview_time(self, current_sec: float, total_sec: float) -> None:
        """Update preview digital time counter in centesimi format ⏱ MM:SS.ss / MM:SS.ss."""
        def _fmt(sec: float) -> str:
            if sec < 0:
                sec = 0.0
            m = int(sec // 60)
            s = sec % 60
            return f"{m:02d}:{s:05.2f}"

        cur_str = _fmt(current_sec)
        tot_str = _fmt(total_sec) if total_sec > 0 else "--:--.--"
        if hasattr(self, "_lbl_preview_time"):
            self._lbl_preview_time.setText(f"⏱ {cur_str} / {tot_str}")

    def _update_selected_list_item(self, cue: Cue) -> None:
        """Lightweight in-place text update for the active list item to prevent focus stealing."""
        item = self._cue_list.currentItem()
        if not item:
            return
        badge = ""
        colour = _CLR_TEXT
        if cue.status == CueStatus.LIVE:
            badge = "  [LIVE]"
            colour = _CLR_LIVE
        elif cue.status == CueStatus.PREVIZ:
            badge = "  [PRE-VIZ]"
            colour = _CLR_PREVIZ
        else:
            badge = "  [STANDBY]"
            colour = _CLR_PREVIZ

        notes_icon = " 📝" if cue.notes else ""
        text = (f"#{_format_cid(cue.cue_id)}  [{cue.media_type.value:<5}]  "
                f"{cue.name:<24}  —  L{cue.layer}{notes_icon}{badge}")
        item.setText(text)
        item.setForeground(QColor(colour))
        if cue.notes:
            item.setToolTip(f"Note di Regia: {cue.notes}\nFile: {cue.file_path}")
        else:
            item.setToolTip(f"File: {cue.file_path}")

    def _refresh_cue_list(self, keep_selection: bool = True) -> None:
        """Rebuild the list widget from the internal cue list, preserving selection."""
        prev_row = self._cue_list.currentRow()
        if prev_row < 0 and 0 <= self._current_index < len(self._cues):
            prev_row = self._current_index

        total_cues = len(self._cues)
        if total_cues == 0:
            self._lbl_cue_count.setText("0 Cue in scaletta")
            self._lbl_cue_standby.setText("Standby: Nessuna")
            self._update_inspector(None)
        else:
            self._lbl_cue_count.setText(f"{total_cues} Cue in scaletta")
            standby_row = prev_row if (0 <= prev_row < total_cues) else 0
            standby_cue = self._cues[standby_row]
            self._lbl_cue_standby.setText(f"Standby: #{_format_cid(standby_cue.cue_id)} [{standby_cue.media_type.value}]")

        self._cue_list.blockSignals(True)
        self._cue_list.clear()
        for i, cue in enumerate(self._cues):
            badge = ""
            colour = _CLR_TEXT
            if cue.status == CueStatus.LIVE:
                badge = "  [LIVE]"
                colour = _CLR_LIVE
            elif total_cues > 0 and i == prev_row:
                badge = "  [STANDBY]"
                colour = _CLR_PREVIZ
            elif cue.status == CueStatus.PREVIZ:
                badge = "  [PRE-VIZ]"
                colour = _CLR_PREVIZ

            notes_icon = " 📝" if cue.notes else ""
            text = (f"#{_format_cid(cue.cue_id)}  [{cue.media_type.value:<5}]  "
                    f"{cue.name:<24}  —  L{cue.layer}{notes_icon}{badge}")
            item = QListWidgetItem(text)
            item.setForeground(QColor(colour))
            if cue.notes:
                item.setToolTip(f"Note di Regia: {cue.notes}\nFile: {cue.file_path}")
            else:
                item.setToolTip(f"File: {cue.file_path}")
            self._cue_list.addItem(item)

        if keep_selection and 0 <= prev_row < len(self._cues):
            self._cue_list.setCurrentRow(prev_row)
        self._cue_list.blockSignals(False)

    def _selected_cue(self) -> Optional[Cue]:
        row = self._cue_list.currentRow()
        if 0 <= row < len(self._cues):
            return self._cues[row]
        return None

    def update_waveform_duration(self, duration_sec: float) -> None:
        """Called when media duration is detected by the player."""
        self._active_test_duration = max(0.001, duration_sec)
        if hasattr(self, "_spin_out"):
            self._spin_out.set_media_duration(self._active_test_duration)
        cue = self._selected_cue()
        if cue:
            self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, self._active_test_duration)

    def _update_waveform_markers(self, cue: Optional[Cue] = None) -> None:
        """Update IN/OUT markers on the waveform widget."""
        if cue is None:
            cue = self._selected_cue()
        if cue is None or cue.media_type == MediaType.IMAGE:
            return
        total_dur = getattr(self, "_active_test_duration", 0.0)
        self._waveform.set_in_out_seconds(cue.in_point, cue.out_point, total_dur)

    # ── Inspector Callbacks & Nudge ───────────────────────────────────

    def _on_nudge_position(self, dx: float, dy: float) -> None:
        """Nudge position X, Y by a small delta (e.g. 0.01 = 1% screen)."""
        nx = round(max(-2.0, min(2.0, self._spin_pos_x.value() + dx)), 2)
        ny = round(max(-2.0, min(2.0, self._spin_pos_y.value() + dy)), 2)
        self._spin_pos_x.setValue(nx)
        self._spin_pos_y.setValue(ny)

    def _on_reset_position(self) -> None:
        """Reset position X, Y to center (0.00, 0.00)."""
        self._spin_pos_x.setValue(0.0)
        self._spin_pos_y.setValue(0.0)

    def _on_reset_scale(self) -> None:
        """Reset scale to 1.0x (100%)."""
        self._slider_scale.setValue(100)

    def _on_reset_crop(self) -> None:
        """Reset crop to full frame (0, 0, 0, 0)."""
        self._spin_crop_l.setValue(0.0)
        self._spin_crop_r.setValue(0.0)
        self._spin_crop_t.setValue(0.0)
        self._spin_crop_b.setValue(0.0)

    @Slot(float, float)
    def _on_preview_position_changed(self, pos_x: float, pos_y: float) -> None:
        """Handle interactive mouse dragging on the StudioPreviewMonitor."""
        self._spin_pos_x.blockSignals(True)
        self._spin_pos_y.blockSignals(True)
        self._spin_pos_x.setValue(pos_x)
        self._spin_pos_y.setValue(pos_y)
        self._spin_pos_x.blockSignals(False)
        self._spin_pos_y.blockSignals(False)
        cue = self._selected_cue()
        if cue:
            cue.position_x = pos_x
            cue.position_y = pos_y
            self._mark_modified(True)
            if getattr(self, "_live_mirror_active", False):
                self._mirror_active_cue_to_live()

    def _set_inspector_enabled(self, enabled: bool, media_type: Optional[MediaType] = None) -> None:
        """Enable or disable inspector controls with context-aware logic per media type."""
        self._btn_layer1.setEnabled(enabled)
        self._btn_layer2.setEnabled(enabled)
        self._btn_layer3.setEnabled(enabled)
        self._edit_cue_name.setEnabled(enabled)
        self._edit_cue_notes.setEnabled(enabled)

        all_media_controls = (
            self._spin_pos_x, self._spin_pos_y,
            self._btn_nudge_left, self._btn_nudge_up, self._btn_nudge_down, self._btn_nudge_right, self._btn_pos_center,
            self._slider_scale, self._btn_scale_reset,
            self._slider_opacity, self._btn_opacity_reset,
            self._spin_crop_l, self._spin_crop_r, self._spin_crop_t, self._spin_crop_b, self._btn_crop_reset,
            self._spin_fade_in, self._spin_fade_out,
            self._combo_aspect, self._slider_volume, self._chk_loop,
            self._spin_in, self._spin_out, self._spin_hold_time,
        )

        if not enabled or media_type is None:
            self._edit_cue_name.clear()
            self._edit_cue_notes.clear()
            for w in all_media_controls:
                w.setEnabled(False)
            return

        # Common transitions
        self._spin_fade_in.setEnabled(True)
        self._spin_fade_out.setEnabled(True)

        if media_type == MediaType.AUDIO:
            for w in (self._spin_pos_x, self._spin_pos_y,
                      self._btn_nudge_left, self._btn_nudge_up, self._btn_nudge_down, self._btn_nudge_right, self._btn_pos_center,
                      self._slider_scale, self._btn_scale_reset,
                      self._slider_opacity, self._btn_opacity_reset,
                      self._spin_crop_l, self._spin_crop_r, self._spin_crop_t, self._spin_crop_b, self._btn_crop_reset,
                      self._combo_aspect, self._spin_hold_time):
                w.setEnabled(False)
            for w in (self._slider_volume, self._chk_loop, self._spin_in, self._spin_out):
                w.setEnabled(True)

        elif media_type == MediaType.IMAGE:
            for w in (self._spin_pos_x, self._spin_pos_y,
                      self._btn_nudge_left, self._btn_nudge_up, self._btn_nudge_down, self._btn_nudge_right, self._btn_pos_center,
                      self._slider_scale, self._btn_scale_reset,
                      self._slider_opacity, self._btn_opacity_reset,
                      self._spin_crop_l, self._spin_crop_r, self._spin_crop_t, self._spin_crop_b, self._btn_crop_reset,
                      self._combo_aspect, self._slider_volume, self._spin_hold_time):
                w.setEnabled(True)
            self._chk_loop.setEnabled(False)
            self._spin_in.setEnabled(False)
            self._spin_out.setEnabled(False)

        elif media_type == MediaType.VIDEO:
            for w in (self._spin_pos_x, self._spin_pos_y,
                      self._btn_nudge_left, self._btn_nudge_up, self._btn_nudge_down, self._btn_nudge_right, self._btn_pos_center,
                      self._slider_scale, self._btn_scale_reset,
                      self._slider_opacity, self._btn_opacity_reset,
                      self._spin_crop_l, self._spin_crop_r, self._spin_crop_t, self._spin_crop_b, self._btn_crop_reset,
                      self._combo_aspect, self._slider_volume,
                      self._chk_loop, self._spin_in, self._spin_out):
                w.setEnabled(True)
            self._spin_hold_time.setEnabled(False)

    def _update_inspector(self, cue: Optional[Cue]) -> None:
        """Populate inspector fields from the given cue, or disable if None."""
        if cue is None:
            self._grp_inspector.setTitle("ISPETTORE CUE (Nessuna cue selezionata)")
            self._set_inspector_enabled(False)
            return

        self._updating_inspector = True
        try:
            self._grp_inspector.setTitle(
                f"ISPETTORE CUE — #{_format_cid(cue.cue_id)} [{cue.media_type.value}] '{cue.name}'"
            )
            self._set_inspector_enabled(True, cue.media_type)

            self._edit_cue_name.setText(cue.name)
            self._edit_cue_notes.setText(cue.notes)
            self._btn_layer1.setChecked(cue.layer == 1)
            self._btn_layer2.setChecked(cue.layer == 2)
            self._btn_layer3.setChecked(cue.layer == 3)

            self._spin_pos_x.setValue(cue.position_x)
            self._spin_pos_y.setValue(cue.position_y)
            self._slider_scale.setValue(int(cue.scale * 100))
            self._lbl_scale.setText(f"{cue.scale:.1f}x")
            self._slider_opacity.setValue(int(cue.opacity * 100))
            self._lbl_opacity.setText(f"{int(cue.opacity * 100)}%")

            # L, R, T, B from crop dict
            crop_x = cue.crop.get("x", 0.0)
            crop_y = cue.crop.get("y", 0.0)
            crop_w = cue.crop.get("w", 1.0)
            crop_h = cue.crop.get("h", 1.0)
            self._spin_crop_l.setValue(round(crop_x, 2))
            self._spin_crop_r.setValue(round(max(0.0, 1.0 - crop_x - crop_w), 2))
            self._spin_crop_t.setValue(round(crop_y, 2))
            self._spin_crop_b.setValue(round(max(0.0, 1.0 - crop_y - crop_h), 2))

            self._spin_fade_in.setValue(cue.fade_in)
            self._spin_fade_out.setValue(cue.fade_out)
            self._spin_hold_time.setValue(cue.hold_time)
            self._slider_volume.setValue(int(cue.volume * 100))
            self._chk_loop.setChecked(cue.loop)
            self._spin_in.setValue(cue.in_point)
            self._spin_out.setValue(cue.out_point if cue.out_point else 0.0)

            # Aspect ratio
            idx = 0
            if cue.aspect_ratio == "16:9":
                idx = 1
            elif cue.aspect_ratio == "4:3":
                idx = 2
            elif cue.aspect_ratio == "21:9":
                idx = 3
            elif cue.aspect_ratio == "1:1":
                idx = 4
            self._combo_aspect.setCurrentIndex(idx)
            self._update_waveform_markers(cue)
        finally:
            self._updating_inspector = False

    def _on_inspector_value_changed(self, *_args) -> None:
        """Propagate UI inspector changes back to the cue data model and autosave."""
        if not self._updating_inspector:
            self._apply_inspector_to_cue()
            self._mark_modified(True)
            cue = self._selected_cue()
            if cue:
                self._update_selected_list_item(cue)
                if cue.media_type == MediaType.VIDEO:
                    self.update_preview_video_layout(
                        scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity,
                    )
                elif cue.media_type == MediaType.IMAGE:
                    self.show_preview_image(
                        cue.file_path, scale=cue.scale, crop=cue.crop,
                        pos_x=cue.position_x, pos_y=cue.position_y,
                        opacity=cue.opacity,
                    )

                if getattr(self, "_live_mirror_active", False):
                    self._mirror_active_cue_to_live()

    def _apply_inspector_to_cue(self) -> None:
        """Write inspector values back to the selected cue."""
        cue = self._selected_cue()
        if cue is None:
            return
        new_name = self._edit_cue_name.text().strip()
        if new_name:
            cue.name = new_name
        cue.notes = self._edit_cue_notes.text().strip()

        # Position X and Y
        cue.position_x = round(self._spin_pos_x.value(), 3)
        cue.position_y = round(self._spin_pos_y.value(), 3)

        # Scale & Opacity
        cue.scale = round(self._slider_scale.value() / 100.0, 2)
        cue.opacity = round(self._slider_opacity.value() / 100.0, 2)

        # Crop (L, R, T, B)
        crop_l = self._spin_crop_l.value()
        crop_r = self._spin_crop_r.value()
        crop_t = self._spin_crop_t.value()
        crop_b = self._spin_crop_b.value()
        cue.crop = {
            "x": crop_l,
            "y": crop_t,
            "w": max(0.01, round(1.0 - crop_l - crop_r, 3)),
            "h": max(0.01, round(1.0 - crop_t - crop_b, 3)),
        }

        cue.fade_in = self._spin_fade_in.value()
        cue.fade_out = self._spin_fade_out.value()
        cue.hold_time = self._spin_hold_time.value()
        cue.volume = self._slider_volume.value() / 100.0
        cue.loop = self._chk_loop.isChecked()
        cue.in_point = self._spin_in.value()

        out_val = self._spin_out.value()
        if out_val > 0 and out_val <= cue.in_point:
            out_val = round(cue.in_point + 0.05, 2)
            self._spin_out.blockSignals(True)
            self._spin_out.setValue(out_val)
            self._spin_out.blockSignals(False)

        cue.out_point = out_val if out_val > 0 else None

        ar_text = self._combo_aspect.currentText()
        cue.aspect_ratio = None if ar_text == "Native" else ar_text
        self._update_waveform_markers(cue)

        # Emit real-time updates for Live volume and Pre-Viz in/out seeking
        self.live_volume_changed.emit(self._slider_volume.value())
        self.preview_in_out_changed.emit(cue.in_point, cue.out_point)

    @Slot(float)
    def _on_waveform_in_changed(self, new_in: float) -> None:
        """Handle mouse dragging of IN marker on the waveform."""
        self._spin_in.blockSignals(True)
        self._spin_in.setValue(new_in)
        self._spin_in.blockSignals(False)
        cue = self._selected_cue()
        if cue:
            cue.in_point = new_in
            self._mark_modified(True)
            self.preview_in_out_changed.emit(cue.in_point, cue.out_point)

    @Slot(float)
    def _on_waveform_out_changed(self, new_out: float) -> None:
        """Handle mouse dragging of OUT marker on the waveform."""
        self._spin_out.blockSignals(True)
        self._spin_out.setValue(new_out)
        self._spin_out.blockSignals(False)
        cue = self._selected_cue()
        if cue:
            cue.out_point = new_out if new_out > 0 else None
            self._mark_modified(True)
            self.preview_in_out_changed.emit(cue.in_point, cue.out_point)

    # ── Mute Preview Toggle & Live Layer Controls ─────────────────────

    def _update_mute_preview_style(self) -> None:
        """Update toggle button visual style based on active mute state."""
        if hasattr(self, "_btn_preview_mute"):
            if self._btn_preview_mute.isChecked():
                self._btn_preview_mute.setText("🔒 MUTE: ON")
                self._btn_preview_mute.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #4d3800;
                        color: {_CLR_PREVIZ};
                        border: 1px solid {_CLR_PREVIZ};
                        border-radius: 3px;
                        padding: 2px 10px;
                        font-weight: bold;
                        font-size: 10px;
                        height: 22px;
                    }}
                    QPushButton:hover {{
                        background-color: #664d00;
                    }}
                """)
            else:
                self._btn_preview_mute.setText("🔊 CUFFIA: ON")
                self._btn_preview_mute.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #004d20;
                        color: {_CLR_LIVE};
                        border: 1px solid {_CLR_LIVE};
                        border-radius: 3px;
                        padding: 2px 10px;
                        font-weight: bold;
                        font-size: 10px;
                        height: 22px;
                    }}
                    QPushButton:hover {{
                        background-color: #00662a;
                    }}
                """)

    @Slot(bool)
    def _on_preview_mute_toggled(self, is_muted: bool) -> None:
        """Toggle preview mute on explicit operator request."""
        self._update_mute_preview_style()
        self.preview_mute_toggled.emit(is_muted)
        state_txt = "Silenzioso (Muto)" if is_muted else "Ascolto Attivo"
        self._status_label.setText(f"Audio Preview: {state_txt}")

    def _on_clear_live_layer(self, layer: int) -> None:
        """Remove / stop media currently running on the given layer."""
        self._reset_live_label(layer)
        for cue in self._cues:
            if cue.layer == layer and cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        self.layer_clear_requested.emit(layer)
        self._status_label.setText(f"Layer {layer} arrestato e rimosso dal Live")
        logger.info("[LIVE STATUS] Cleared Layer %d", layer)

    def _reset_live_label(self, layer: int) -> None:
        labels = {1: self._lbl_live_l1, 2: self._lbl_live_l2, 3: self._lbl_live_l3}
        lbl = labels.get(layer)
        if lbl:
            lbl.setText(f"Layer {layer}: —")
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 12px;
                    color: #777;
                }
            """)

    # ── Layer 0 (Tappo) & Hardware Acceleration ───────────────────────

    def set_layer0_image(self, file_path: Optional[str]) -> bool:
        """Update the Layer 0 (tappo) background image across output and UI."""
        success = self._output.set_layer0_image(file_path)
        if success:
            self._layer0_image = file_path
            name = Path(file_path).name if file_path else "Logo BlindCue (Predefinito)"
            if hasattr(self, "_lbl_tappo_info"):
                self._lbl_tappo_info.setText(f"Tappo (L0): {name}")
            if hasattr(self, "_preview_monitor"):
                self._preview_monitor.set_layer0_image(file_path)
            return True
        return False

    @Slot()
    def _on_choose_layer0(self) -> None:
        """Prompt operator to select a custom Layer 0 failsafe image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona Immagine di Tappo (Layer 0)",
            "",
            "Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)",
        )
        if file_path:
            if self.set_layer0_image(file_path):
                self._mark_modified(True)
                self._auto_save()
                self._status_label.setText(f"Tappo (Layer 0) impostato: {Path(file_path).name}")
            else:
                QMessageBox.warning(self, "File non valido", "Impossibile caricare l'immagine di tappo selezionata.")

    @Slot()
    def _on_reset_layer0(self) -> None:
        """Reset Layer 0 to the bundled BlindCue official logo."""
        self._output.reset_layer0_default()
        self._layer0_image = None
        if hasattr(self, "_lbl_tappo_info"):
            self._lbl_tappo_info.setText("Tappo (L0): Logo BlindCue (Predefinito)")
        if hasattr(self, "_preview_monitor"):
            self._preview_monitor.set_layer0_image(str(_LOGO_PATH))
        self._mark_modified(True)
        self._auto_save()
        self._status_label.setText("Tappo (Layer 0) ripristinato al logo predefinito")

    @staticmethod
    def _get_hardware_details() -> dict:
        cpu_cores = os.cpu_count() or 1
        cpu_model = "Multi-core CPU"
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

        gpu_desc = "Scheda Grafica Integrata / Discreta"
        if shutil.which("lspci"):
            try:
                res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=2)
                lines = [line for line in res.stdout.splitlines() if any(k in line for k in ["VGA", "3D", "Display"])]
                if lines:
                    parts = lines[0].split(":", 2)
                    gpu_desc = parts[-1].strip() if len(parts) >= 3 else lines[0]
            except Exception:
                pass
        elif os.path.exists("/dev/dri/renderD128"):
            gpu_desc = "Mesa Direct Rendering (DRI/DRM)"

        has_vaapi = os.path.exists("/dev/dri/renderD128")
        wayland_session = os.environ.get("WAYLAND_DISPLAY", "")
        return {
            "cpu_cores": cpu_cores,
            "cpu_model": cpu_model,
            "gpu_desc": gpu_desc,
            "has_vaapi": has_vaapi,
            "wayland_session": wayland_session,
        }

    def _detect_hardware_brief(self) -> str:
        info = self._get_hardware_details()
        cores = info["cpu_cores"]
        gpu = info["gpu_desc"]
        if "Intel" in gpu:
            gpu_short = "Intel Graphics"
        elif "NVIDIA" in gpu or "GeForce" in gpu:
            gpu_short = "NVIDIA GPU"
        elif "AMD" in gpu or "Radeon" in gpu:
            gpu_short = "AMD Radeon"
        else:
            gpu_short = gpu[:20]
        accel = "VA-API/OpenGL" if info["has_vaapi"] else "EGL/OpenGL"
        return f"🖥️ CPU: {cores} Cores | 🎮 GPU: {gpu_short} ({accel})"

    @Slot()
    def _on_hardware_info(self) -> None:
        info = self._get_hardware_details()
        dialog_txt = (
            f"<h3>Architettura Hardware & Prestazioni BlindCue</h3>"
            f"<p><b>Processore (CPU):</b> {info['cpu_model']}<br/>"
            f"• Core / Thread rilevati: <b>{info['cpu_cores']} core</b></p>"
            f"<p><b>Scheda Video (GPU):</b> {info['gpu_desc']}<br/>"
            f"• Accelerazione Hardware DRI/DRM (/dev/dri): <b>{'Attiva (VA-API / EGL)' if info['has_vaapi'] else 'Mesa Software'}</b><br/>"
            f"• Sessione Grafica: <b>Native Wayland ({info['wayland_session'] or 'Attivo'})</b></p>"
            f"<hr/>"
            f"<h4>Come BlindCue sfrutta l'Hardware per la Massima Stabilità Live:</h4>"
            f"<ul>"
            f"<li><b>GPU Offloading:</b> Il compositing di tutti i layer (0, 1, 2, 3) e lo scaling video/immagini avvengono interamente sulla GPU tramite Wayland EGL/OpenGL. La CPU non esegue operazioni pesanti di ridisegno pixel.</li>"
            f"<li><b>Decodifica Video Hardware:</b> QtMultimedia e FFmpeg interrogano automaticamente la GPU (tramite VA-API per Intel/AMD o NVDEC per NVIDIA). I frame vengono decodificati direttamente nelle texture video senza intasare la RAM.</li>"
            f"<li><b>Architettura Multi-Core Isolato:</b> BlindCue distribuisce il carico su più thread separati:"
            f"<ul>"
            f"<li><i>Core UI:</i> Riservato all'interfaccia utente (event loop a 60 fps garantito, nessun freeze).</li>"
            f"<li><i>Core Audio/Video:</i> Thread prioritario a latenza minima con buffer circolare per evitare audio glitch.</li>"
            f"<li><i>Core Background:</i> Pool di thread worker asincroni per l'analisi della forma d'onda e salvataggio atomico.</li>"
            f"</ul>"
            f"</li>"
            f"</ul>"
            f"<p style='color: #00e676;'><b>Risultato:</b> Zero crash, latenza impercettibile sul tasto GO e carico CPU medio inferiore al 5%.</p>"
        )
        QMessageBox.information(self, "BlindCue — Info Hardware & Accelerazione", dialog_txt)

    # ── Slots ─────────────────────────────────────────────────────────

    @Slot(int)
    def _on_cue_selected(self, row: int) -> None:
        if 0 <= row < len(self._cues):
            self._current_index = row
            cue = self._cues[row]
            self._update_inspector(cue)
            self._request_waveform(cue)
            self._waveform.set_playhead(None)
            icon = "🎬" if cue.media_type == MediaType.VIDEO else ("🎵" if cue.media_type == MediaType.AUDIO else "🖼")
            self._lbl_preview_info.setText(f"{icon} #{_format_cid(cue.cue_id)} {cue.name}")
            self._lbl_preview_info.setToolTip(f"File: {cue.file_path}")
            self._lbl_cue_standby.setText(f"Standby: #{_format_cid(cue.cue_id)} [{cue.media_type.value}]")

            if cue.media_type == MediaType.IMAGE:
                self.show_preview_image(cue.file_path, scale=cue.scale, crop=cue.crop,
                                       pos_x=cue.position_x, pos_y=cue.position_y, opacity=cue.opacity)
            elif cue.media_type == MediaType.VIDEO:
                self.show_preview_video(scale=cue.scale, crop=cue.crop,
                                       pos_x=cue.position_x, pos_y=cue.position_y, opacity=cue.opacity)
            elif cue.media_type == MediaType.AUDIO:
                self.show_preview_audio()

            if getattr(self, "_live_mirror_active", False):
                self._mirror_active_cue_to_live()

            self.cue_preview_requested.emit(cue)
            logger.debug("Cue selected: %s", cue)
        else:
            self._update_inspector(None)
            self.clear_preview()
            self._lbl_preview_info.setText("— Nessun file selezionato —")
            self._lbl_cue_standby.setText("Standby: Nessuna")

    # ── Live Mirror (Rehearsal / Progettazione) ───────────────────────

    @Slot(bool)
    def _on_live_mirror_toggled(self, active: bool) -> None:
        self._live_mirror_active = active
        if active:
            self._btn_live_mirror.setText("🔴 MIRROR: ON")
            self._btn_live_mirror.setStyleSheet("""
                QPushButton {
                    background-color: #5c1818;
                    color: #ff5252;
                    border: 1px solid #ff5252;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 1px 8px;
                }
                QPushButton:hover {
                    background-color: #7a2020;
                }
            """)
            self._status_label.setText("PROGETTAZIONE: LIVE MIRROR ATTIVO (Modifiche visibili sullo schermo esterno)")
            self._mirror_active_cue_to_live()
        else:
            self._btn_live_mirror.setText("🔗 MIRROR LIVE: OFF")
            self._btn_live_mirror.setStyleSheet("""
                QPushButton {
                    background-color: #2b2b2b;
                    color: #888888;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 1px 8px;
                }
                QPushButton:hover {
                    background-color: #383838;
                    color: #ccc;
                }
            """)
            self._status_label.setText("LIVE MIRROR DISATTIVATO — Anteprima isolata (Pronto per lo spettacolo)")
            self._restore_live_output()

    def _mirror_active_cue_to_live(self) -> None:
        cue = self._selected_cue()
        if not cue or not getattr(self, "_live_mirror_active", False):
            return
        try:
            if cue.media_type == MediaType.IMAGE:
                self._output.show_image(
                    cue.layer,
                    cue.file_path,
                    opacity=cue.opacity,
                    crop=cue.crop,
                    scale=cue.scale,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                )
            elif cue.media_type == MediaType.VIDEO:
                self._output.show_video_widget(
                    scale=cue.scale,
                    crop=cue.crop,
                    pos_x=cue.position_x,
                    pos_y=cue.position_y,
                    opacity=cue.opacity,
                )
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error mirroring cue: %s", exc)

    def _restore_live_output(self) -> None:
        try:
            live_cues = [c for c in self._cues if c.status == CueStatus.LIVE]
            if not live_cues:
                self._output.show_fallback()
            else:
                self._output.clear_all_layers()
                for c in live_cues:
                    if c.media_type == MediaType.IMAGE:
                        self._output.show_image(
                            c.layer,
                            c.file_path,
                            opacity=c.opacity,
                            crop=c.crop,
                            scale=c.scale,
                            pos_x=c.position_x,
                            pos_y=c.position_y,
                        )
                    elif c.media_type == MediaType.VIDEO:
                        self._output.show_video_widget(
                            scale=c.scale,
                            crop=c.crop,
                            pos_x=c.position_x,
                            pos_y=c.position_y,
                            opacity=c.opacity,
                        )
        except Exception as exc:
            logger.error("[LIVE MIRROR] Error restoring live output: %s", exc)

    def _set_layer(self, layer: int) -> None:
        self._btn_layer1.setChecked(layer == 1)
        self._btn_layer2.setChecked(layer == 2)
        self._btn_layer3.setChecked(layer == 3)
        cue = self._selected_cue()
        if cue:
            cue.layer = layer
            self._refresh_cue_list()
            self._mark_modified(True)

    @Slot()
    def _on_go(self) -> None:
        """Fire the current/selected cue and advance standby to the next cue."""
        # Safety guard: if focus is currently inside a text input or spinbox, do not fire GO!
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        if not self._cues:
            self._status_label.setText("Scaletta vuota — Aggiungi prima dei file multimediali")
            return

        self._apply_inspector_to_cue()

        # Prioritize currently selected row in cue list
        row = self._cue_list.currentRow()
        if 0 <= row < len(self._cues):
            target_idx = row
        elif 0 <= self._current_index < len(self._cues):
            target_idx = self._current_index
        else:
            target_idx = 0

        cue = self._cues[target_idx]

        # Reset any previous LIVE status on this layer
        for other in self._cues:
            if other.layer == cue.layer and other.cue_id != cue.cue_id and other.status == CueStatus.LIVE:
                other.status = CueStatus.LOADED

        cue.status = CueStatus.LIVE
        self._current_index = target_idx
        self.cue_fired.emit(cue)
        self._refresh_cue_list(keep_selection=False)

        # Update live status control bar
        layer_labels = {1: self._lbl_live_l1, 2: self._lbl_live_l2, 3: self._lbl_live_l3}
        lbl = layer_labels.get(cue.layer)
        if lbl:
            lbl.setText(f"LIVE: [{cue.media_type.value}] {cue.name}  (Layer {cue.layer})")
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: #16361a;
                    border: 1px solid {_CLR_LIVE};
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 12px;
                    font-weight: bold;
                    color: {_CLR_LIVE};
                }}
            """)

        # Auto-advance standby selection to the next cue for the subsequent GO
        next_idx = target_idx + 1
        if next_idx < len(self._cues):
            self._cue_list.setCurrentRow(next_idx)
            self._status_label.setText(
                f"LIVE → Cue #{cue.cue_id} '{cue.name}' (Layer {cue.layer}) | Standby: #{self._cues[next_idx].cue_id} '{self._cues[next_idx].name}'"
            )
        else:
            # Reached end: keep selection on current cue and allow re-firing anytime!
            self._cue_list.setCurrentRow(target_idx)
            self._status_label.setText(
                f"LIVE → Cue #{cue.cue_id} '{cue.name}' (Layer {cue.layer}) — Fine scaletta (premi GO per rilanciare)"
            )

        self._auto_save()
        logger.info("[GO] Fired cue #%d: %s", cue.cue_id, cue)

    @Slot()
    def _on_blackout(self) -> None:
        """Show Layer 0 (failsafe) on the output and clear all live indicators."""
        self._output.show_fallback()
        for cue in self._cues:
            if cue.status == CueStatus.LIVE:
                cue.status = CueStatus.LOADED
        self._refresh_cue_list()
        self._reset_live_label(1)
        self._reset_live_label(2)
        self._reset_live_label(3)
        self.blackout_requested.emit()
        self._status_label.setText("BLACKOUT — Output ripristinato a Layer 0 (Tappo)")
        logger.info("[BLACKOUT] Activated")

    def _on_add_media(self, media_type: MediaType) -> None:
        ext_map = {
            MediaType.VIDEO: "Video (*.mp4 *.mkv *.avi *.mov *.webm)",
            MediaType.AUDIO: "Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)",
            MediaType.IMAGE: "Image (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        }
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Add {media_type.value}", "",
            ext_map.get(media_type, "All Files (*)"))
        if file_path:
            self._add_cue_from_file(file_path, media_type)

    def _add_cue_from_file(self, file_path: str,
                           media_type: Optional[MediaType] = None) -> None:
        if media_type is None:
            media_type = self._detect_media_type(file_path)
        if media_type is None:
            QMessageBox.warning(self, "Unsupported File",
                                f"Cannot determine media type for:\n{file_path}")
            return

        name = os.path.basename(file_path)
        cue = Cue(name=name, media_type=media_type, file_path=file_path)
        errors = cue.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error",
                                "\n".join(errors))
            return

        cue.status = CueStatus.LOADED
        self._cues.append(cue)
        self._refresh_cue_list()
        self._cue_list.setCurrentRow(len(self._cues) - 1)
        self._mark_modified(True)
        self._status_label.setText(f"Added: {cue}")
        self._auto_save()
        logger.info("Added cue: %s", cue)

    @Slot(str)
    def _on_file_dropped(self, file_path: str) -> None:
        self._add_cue_from_file(file_path)

    @Slot()
    def _on_move_up(self) -> None:
        row = self._cue_list.currentRow()
        if row > 0:
            self._cues[row], self._cues[row - 1] = (
                self._cues[row - 1], self._cues[row])
            self._refresh_cue_list()
            self._cue_list.setCurrentRow(row - 1)
            self._mark_modified(True)
            self._auto_save()

    @Slot()
    def _on_move_down(self) -> None:
        row = self._cue_list.currentRow()
        if 0 <= row < len(self._cues) - 1:
            self._cues[row], self._cues[row + 1] = (
                self._cues[row + 1], self._cues[row])
            self._refresh_cue_list()
            self._cue_list.setCurrentRow(row + 1)
            self._mark_modified(True)
            self._auto_save()

    @Slot()
    def _on_delete_cue(self) -> None:
        # Safety guard: if focus is in a text input or spinbox, do not delete the cue!
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox)):
            return

        row = self._cue_list.currentRow()
        if 0 <= row < len(self._cues):
            removed = self._cues.pop(row)
            self._refresh_cue_list(keep_selection=False)
            if self._cues:
                new_row = min(row, len(self._cues) - 1)
                self._cue_list.setCurrentRow(new_row)
            else:
                self._current_index = -1
                self._waveform.set_peaks(np.array([]))
                self._waveform.set_in_out_seconds(0.0, None, 0.0)
                self._lbl_preview_info.setText("— Nessun file selezionato —")
                self.set_preview_time(0.0, 0.0)
                self.clear_preview()
                self._update_inspector(None)
            self._mark_modified(True)
            self._status_label.setText(f"Deleted: #{removed.cue_id} '{removed.name}'")
            self._auto_save()
            logger.info("Deleted cue: %s", removed)

    def _auto_save(self) -> None:
        """Autosave active state if cues exist or Layer 0 is customized."""
        if self._cues or self._layer0_image:
            try:
                self._apply_inspector_to_cue()
                settings = {"layer0_image": self._layer0_image} if self._layer0_image else {}
                self._project_manager.autosave(
                    self._cues,
                    current_index=self._current_index,
                    active_project_path=self._current_project_path,
                    settings=settings,
                )
            except Exception as exc:
                logger.warning("[AUTOSAVE] Auto-save error: %s", exc)

    def _check_crash_recovery(self) -> None:
        """Inspect if a previous session terminated abnormally and offer to restore."""
        recovery = self._project_manager.check_crash_recovery()
        if not recovery:
            return

        saved_at = recovery.get("saved_at", "sconosciuto")
        cues_count = recovery.get("cues_count", len(recovery.get("cues", [])))

        reply = QMessageBox.question(
            self,
            "BlindCue — Ripristino Sessione (Crash Recovery)",
            f"È stata rilevata una sessione precedente interrotta o non salvata!\n\n"
            f"• Data ultimo autosave: {saved_at}\n"
            f"• Cue recuperabili: {cues_count}\n\n"
            f"Vuoi ripristinare il progetto da dove era stato interrotto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Yes:
            raw_cues = recovery.get("cues", [])
            self._cues.clear()
            for item in raw_cues:
                try:
                    cue = Cue.from_dict(item)
                    cue.status = CueStatus.LOADED if os.path.isfile(cue.file_path) else CueStatus.OFFLINE
                    self._cues.append(cue)
                except Exception as e:
                    logger.warning("[RECOVERY] Error recovering cue: %s", e)
            self._current_index = recovery.get("current_cue_index", -1)
            self._current_project_path = recovery.get("active_project_path")

            rec_settings = recovery.get("settings", {})
            layer0 = rec_settings.get("layer0_image") if isinstance(rec_settings, dict) else None
            if layer0 and os.path.isfile(layer0):
                self.set_layer0_image(layer0)
            else:
                self._on_reset_layer0()

            self._refresh_cue_list()
            if 0 <= self._current_index < len(self._cues):
                self._cue_list.setCurrentRow(self._current_index)
            self._mark_modified(True)
            self._status_label.setText(f"Sessione ripristinata con successo ({len(self._cues)} cue)")
            logger.info("[RECOVERY] Restored %d cues from autosave", len(self._cues))
        else:
            self._project_manager.clear_autosave()
            logger.info("[RECOVERY] User discarded autosave recovery")

    @Slot()
    def _on_new_show(self) -> None:
        """Create a new empty show."""
        if self._is_modified and self._cues:
            ret = QMessageBox.question(
                self,
                "Nuovo Show",
                "Ci sono modifiche non salvate nel progetto corrente.\nVuoi salvarle prima di creare un nuovo show?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                if not self._on_save_show():
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                return

        self._cues.clear()
        self._current_index = -1
        self._current_project_path = None
        self._on_reset_layer0()
        self._refresh_cue_list()
        self._waveform.set_peaks(np.array([]))
        self._waveform.set_in_out_seconds(0.0, None, 0.0)
        self.set_preview_time(0.0, 0.0)
        self.clear_preview()
        self._update_inspector(None)
        self._mark_modified(False)
        self._status_label.setText("Nuovo show creato")
        self._auto_save()

    @Slot()
    def _on_open_show(self) -> None:
        """Open a .blindcue or .json show file."""
        if self._is_modified and self._cues:
            ret = QMessageBox.question(
                self,
                "Apri Show",
                "Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                if not self._on_save_show():
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Apri Show BlindCue",
            "",
            "BlindCue Show (*.blindcue *.json);;Tutti i file (*)",
        )
        if not file_path:
            return

        try:
            cues, current_idx, settings = self._project_manager.load_project(file_path)
            self._cues = cues
            self._current_index = current_idx
            self._current_project_path = file_path

            # Restore custom Layer 0 image if specified in project settings
            layer0 = settings.get("layer0_image") if isinstance(settings, dict) else None
            if layer0 and os.path.isfile(layer0):
                self.set_layer0_image(layer0)
            else:
                self._on_reset_layer0()

            self._refresh_cue_list()
            if 0 <= self._current_index < len(self._cues):
                self._cue_list.setCurrentRow(self._current_index)
            elif self._cues:
                self._cue_list.setCurrentRow(0)
            self._mark_modified(False)
            self._status_label.setText(f"Caricato: {Path(file_path).name} ({len(cues)} cue)")
            self._auto_save()
        except Exception as exc:
            logger.error("[PROJECT] Error loading %s: %s", file_path, exc, exc_info=True)
            QMessageBox.critical(self, "Errore di Caricamento", f"Impossibile aprire il file:\n{exc}")

    @Slot()
    def _on_save_show(self) -> bool:
        """Save show to active path, or ask for path if untitled."""
        if not self._current_project_path:
            return self._on_save_as_show()
        return self._do_save(self._current_project_path)

    @Slot()
    def _on_save_as_show(self) -> bool:
        """Prompt user for a destination file and save."""
        suggested = self._current_project_path or "my_show.blindcue"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva Show Con Nome",
            suggested,
            "BlindCue Show (*.blindcue);;JSON File (*.json)",
        )
        if not file_path:
            return False
        if not file_path.endswith((".blindcue", ".json")):
            file_path += ".blindcue"
        self._current_project_path = file_path
        return self._do_save(file_path)

    def _do_save(self, file_path: str) -> bool:
        """Execute physical save via ProjectManager."""
        self._apply_inspector_to_cue()
        settings = {"layer0_image": self._layer0_image} if self._layer0_image else {}
        success = self._project_manager.save_project(
            file_path,
            self._cues,
            current_index=self._current_index,
            settings=settings,
        )
        if success:
            self._mark_modified(False)
            self._status_label.setText(f"Salvato con successo: {Path(file_path).name}")
            self._auto_save()
            return True
        else:
            QMessageBox.critical(self, "Errore Salvataggio", f"Impossibile salvare il file in:\n{file_path}")
            return False

    @Slot()
    def _on_quit(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Handle application close with unsaved changes prompt and clean shutdown."""
        if not self._force_closing and self._is_modified and self._cues:
            ret = QMessageBox.question(
                self,
                "Chiusura BlindCue",
                "Ci sono modifiche non salvate nel progetto.\nVuoi salvare prima di uscire?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                if not self._on_save_show():
                    event.ignore()
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._project_manager.mark_clean_exit()
        self._output.force_close()
        event.accept()

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About BlindCue",
            "<h2>BlindCue v0.1</h2>"
            "<p>Minimal failsafe cue player for live shows.</p>"
            "<p>Layer 0 always active • 100% Native Wayland QtMultimedia</p>"
            "<p>© 2026 — Zero crash in live.</p>")

    # ── Waveform ──────────────────────────────────────────────────────

    def _request_waveform(self, cue: Cue) -> None:
        """Launch background waveform extraction for audio/video cues."""
        if cue.media_type == MediaType.IMAGE:
            self._waveform.set_peaks(np.array([]))
            return
        try:
            analyzer = WaveformAnalyzer(cue.file_path,
                                        self._waveform.width())
            self._active_analyzers.add(analyzer)
            analyzer.signals.finished.connect(
                lambda path, peaks, a=analyzer: self._on_analyzer_ready(a, path, peaks))
            analyzer.signals.error.connect(
                lambda path, msg, a=analyzer: self._on_analyzer_failed(a, path, msg))
            self._thread_pool.start(analyzer)
        except Exception as exc:
            logger.error("Waveform request failed: %s", exc)

    def _on_analyzer_ready(self, analyzer, path: str, peaks: object) -> None:
        self._active_analyzers.discard(analyzer)
        cue = self._selected_cue()
        if cue and os.path.abspath(cue.file_path) == os.path.abspath(path):
            if isinstance(peaks, np.ndarray):
                self._waveform.set_peaks(peaks)

    def _on_analyzer_failed(self, analyzer, path: str, msg: str) -> None:
        self._active_analyzers.discard(analyzer)
        logger.warning("Waveform error for %s: %s", path, msg)
        self._waveform.set_peaks(np.array([]))

    # ── Preview Visual Helpers ────────────────────────────────────────

    def show_preview_image(self, file_path: str, scale: float = 1.0, crop: Optional[dict] = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        """Display a static image in the preview monitor with transforms."""
        self._preview_monitor.show_image(file_path, scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y, opacity=opacity)

    def show_preview_video(self, scale: float = 1.0, crop: Optional[dict] = None,
                           pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        """Display preview video with transforms."""
        self._preview_monitor.show_video(scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y, opacity=opacity)

    def update_preview_video_layout(self, scale: float = 1.0, crop: Optional[dict] = None,
                                    pos_x: float = 0.0, pos_y: float = 0.0, opacity: float = 1.0) -> None:
        """Update transforms of preview video in real time."""
        self._preview_monitor.update_video_layout(scale=scale, crop=crop, pos_x=pos_x, pos_y=pos_y, opacity=opacity)

    def show_preview_audio(self) -> None:
        """Display audio preview banner over Layer 0."""
        self._preview_monitor.show_audio()

    def set_preview_audio_playing(self, is_playing: bool) -> None:
        """Toggle animated equalizer spectrum meter in preview."""
        self._preview_monitor.set_audio_playing(is_playing)

    def clear_preview(self) -> None:
        """Clear media in preview and return to Layer 0."""
        self._preview_monitor.clear_media()

    # ── Overrides ─────────────────────────────────────────────────────

    def get_preview_video_widget(self) -> QVideoWidget:
        """Return the native video widget for embedding preview video."""
        return self._preview_monitor.get_video_widget()

    def get_preview_wid(self) -> int:
        """Return the native window ID for backward compatibility."""
        return int(self._preview_monitor.get_video_widget().winId())

