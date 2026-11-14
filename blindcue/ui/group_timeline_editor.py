"""Multi-track Studio Timeline Editor for BlindCUE Groups.

Provides a dedicated, non-destructive 3-layer timeline arranger for group cues.
Allows visual alignment of pre-delays, layer routing, in/out trims, and fades
strictly limited to the media cues already present in the group.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.cue import Cue, MediaType
from ui.spinboxes import SmartDoubleSpinBox
from ui.theme import CLR_ACCENT, CLR_GO, CLR_LIVE, CLR_PREVIZ, CLR_TEXT, build_stylesheet, get_active_theme


def _fmt_timecode(sec: float) -> str:
    total_sec = max(0.0, float(sec))
    mins, s = divmod(total_sec, 60.0)
    int_s = int(s)
    ms = int(round((s - int_s) * 100))
    hrs, mins = divmod(int(mins), 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{int_s:02d}.{ms:02d}"
    return f"{mins:02d}:{int_s:02d}.{ms:02d}"


@dataclass
class TimelineClip:
    """Represents a cue placed as a movable clip on the 3-layer timeline."""
    cue: Cue
    cue_id: int
    name: str
    media_type: MediaType
    file_path: str
    layer: int  # 1, 2, or 3
    start_sec: float  # Equivalent to cue.pre_delay
    duration_sec: float  # Visual duration on track
    in_point: float = 0.0
    out_point: Optional[float] = None
    volume: float = 1.0
    opacity: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    native_duration_sec: float = 10.0


# ── Interactive Multi-Layer Timeline Canvas ──────────────────────────

class GroupTimelineCanvas(QWidget):
    """Custom-painted 3-layer interactive timeline canvas with ruler, clips, and playhead."""

    clip_selected = Signal(int)       # cue_id
    clip_moved = Signal(int)          # cue_id
    playhead_moved = Signal(float)    # time_sec

    TRACK_HEIGHT = 58
    RULER_HEIGHT = 28
    HEADER_WIDTH = 130

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(self.RULER_HEIGHT + 3 * self.TRACK_HEIGHT + 20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.clips: list[TimelineClip] = []
        self.selected_cue_id: Optional[int] = None

        self.pixels_per_sec: float = 40.0  # Zoom level (20 to 120 px/s)
        self.playhead_sec: float = 0.0
        self.snap_grid_sec: float = 0.25
        self.snap_enabled: bool = True

        # Mouse interaction states: "NONE", "SCRUB", "MOVE_CLIP", "TRIM_IN", "TRIM_OUT"
        self._interaction_mode: str = "NONE"
        self._active_clip: Optional[TimelineClip] = None
        self._drag_start_pos = QPoint()
        self._clip_original_start: float = 0.0
        self._clip_original_layer: int = 1
        self._clip_original_in: float = 0.0
        self._clip_original_dur: float = 10.0

    # ── Coordinates Conversion Helpers ────────────────────────────────

    def sec_to_x(self, sec: float) -> float:
        return self.HEADER_WIDTH + max(0.0, sec) * self.pixels_per_sec

    def x_to_sec(self, x: float) -> float:
        return max(0.0, (x - self.HEADER_WIDTH) / max(1.0, self.pixels_per_sec))

    def layer_to_y(self, layer: int) -> int:
        # Visual stacking: Layer 3 (top) -> Layer 2 (middle) -> Layer 1 (bottom)
        row_idx = 3 - layer  # 3->0, 2->1, 1->2
        return self.RULER_HEIGHT + row_idx * self.TRACK_HEIGHT

    def y_to_layer(self, y: int) -> int:
        if y < self.RULER_HEIGHT:
            return 3
        rel_y = y - self.RULER_HEIGHT
        row_idx = max(0, min(2, rel_y // self.TRACK_HEIGHT))
        return 3 - row_idx

    def total_composition_duration(self) -> float:
        if not self.clips:
            return 10.0
        return max(10.0, max(c.start_sec + c.duration_sec for c in self.clips) + 4.0)

    # ── Zoom Controls ─────────────────────────────────────────────────

    def zoom_in(self) -> None:
        self.pixels_per_sec = min(150.0, self.pixels_per_sec * 1.25)
        self._update_geometry()

    def zoom_out(self) -> None:
        self.pixels_per_sec = max(15.0, self.pixels_per_sec / 1.25)
        self._update_geometry()

    def zoom_reset(self) -> None:
        self.pixels_per_sec = 40.0
        self._update_geometry()

    def _update_geometry(self) -> None:
        tot_w = int(self.HEADER_WIDTH + self.total_composition_duration() * self.pixels_per_sec + 200)
        self.setMinimumWidth(tot_w)
        self.update()

    def set_playhead(self, sec: float) -> None:
        self.playhead_sec = max(0.0, float(sec))
        self.update()

    def select_clip(self, cue_id: Optional[int]) -> None:
        if self.selected_cue_id != cue_id:
            self.selected_cue_id = cue_id
            self.update()

    # ── Mouse Interaction ─────────────────────────────────────────────

    def _hit_test(self, pt: QPoint) -> tuple[Optional[TimelineClip], str]:
        """Returns (clip, hit_part) where hit_part is 'BODY', 'TRIM_IN', or 'TRIM_OUT'."""
        if pt.x() < self.HEADER_WIDTH:
            return None, "NONE"

        for clip in reversed(self.clips):
            x1 = self.sec_to_x(clip.start_sec)
            x2 = self.sec_to_x(clip.start_sec + clip.duration_sec)
            y1 = self.layer_to_y(clip.layer) + 4
            y2 = y1 + self.TRACK_HEIGHT - 8

            if y1 <= pt.y() <= y2:
                if abs(pt.x() - x1) <= 7:
                    return clip, "TRIM_IN"
                if abs(pt.x() - x2) <= 7:
                    return clip, "TRIM_OUT"
                if x1 < pt.x() < x2:
                    return clip, "BODY"
        return None, "NONE"

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pt = event.position().toPoint()

            # Clicked on ruler: scrub playhead
            if pt.y() <= self.RULER_HEIGHT and pt.x() >= self.HEADER_WIDTH:
                self._interaction_mode = "SCRUB"
                self.playhead_sec = self.x_to_sec(pt.x())
                self.playhead_moved.emit(self.playhead_sec)
                self.update()
                event.accept()
                return

            clip, hit = self._hit_test(pt)
            if clip is not None:
                self._active_clip = clip
                self.selected_cue_id = clip.cue_id
                self.clip_selected.emit(clip.cue_id)
                self._drag_start_pos = pt
                self._clip_original_start = clip.start_sec
                self._clip_original_layer = clip.layer
                self._clip_original_in = clip.in_point
                self._clip_original_dur = clip.duration_sec

                if hit == "TRIM_IN":
                    self._interaction_mode = "TRIM_IN"
                elif hit == "TRIM_OUT":
                    self._interaction_mode = "TRIM_OUT"
                else:
                    self._interaction_mode = "MOVE_CLIP"

                self.update()
                event.accept()
                return

            # Clicked on empty timeline: scrub playhead & deselect
            if pt.x() >= self.HEADER_WIDTH:
                self._interaction_mode = "SCRUB"
                self.playhead_sec = self.x_to_sec(pt.x())
                self.playhead_moved.emit(self.playhead_sec)
                self.selected_cue_id = None
                self.clip_selected.emit(-1)
                self.update()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pt = event.position().toPoint()

        # Update cursor when hovering over trim edges
        if self._interaction_mode == "NONE":
            clip, hit = self._hit_test(pt)
            if hit in ("TRIM_IN", "TRIM_OUT"):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif hit == "BODY":
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif pt.y() <= self.RULER_HEIGHT and pt.x() >= self.HEADER_WIDTH:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()

        # Handle active dragging
        elif self._interaction_mode == "SCRUB":
            self.playhead_sec = self.x_to_sec(pt.x())
            self.playhead_moved.emit(self.playhead_sec)
            self.update()

        elif self._interaction_mode == "MOVE_CLIP" and self._active_clip:
            delta_x = pt.x() - self._drag_start_pos.x()
            delta_sec = delta_x / self.pixels_per_sec
            raw_start = max(0.0, self._clip_original_start + delta_sec)

            if self.snap_enabled and self.snap_grid_sec > 0:
                raw_start = round(raw_start / self.snap_grid_sec) * self.snap_grid_sec

            self._active_clip.start_sec = max(0.0, raw_start)
            new_layer = self.y_to_layer(pt.y())
            self._active_clip.layer = new_layer

            self.clip_moved.emit(self._active_clip.cue_id)
            self._update_geometry()

        elif self._interaction_mode == "TRIM_OUT" and self._active_clip:
            raw_end = self.x_to_sec(pt.x())
            if self.snap_enabled and self.snap_grid_sec > 0:
                raw_end = round(raw_end / self.snap_grid_sec) * self.snap_grid_sec

            new_dur = max(0.5, raw_end - self._active_clip.start_sec)
            # Cap at native media duration if available
            if self._active_clip.native_duration_sec > 0:
                max_dur = self._active_clip.native_duration_sec - self._active_clip.in_point
                new_dur = min(max_dur, new_dur)

            self._active_clip.duration_sec = new_dur
            self._active_clip.out_point = self._active_clip.in_point + new_dur
            self.clip_moved.emit(self._active_clip.cue_id)
            self._update_geometry()

        elif self._interaction_mode == "TRIM_IN" and self._active_clip:
            raw_start = self.x_to_sec(pt.x())
            if self.snap_enabled and self.snap_grid_sec > 0:
                raw_start = round(raw_start / self.snap_grid_sec) * self.snap_grid_sec

            orig_end = self._clip_original_start + self._clip_original_dur
            valid_start = min(orig_end - 0.5, max(0.0, raw_start))
            delta_trim = valid_start - self._clip_original_start

            self._active_clip.start_sec = valid_start
            self._active_clip.in_point = max(0.0, self._clip_original_in + delta_trim)
            self._active_clip.duration_sec = orig_end - valid_start

            self.clip_moved.emit(self._active_clip.cue_id)
            self._update_geometry()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._interaction_mode = "NONE"
            self._active_clip = None
            self.unsetCursor()
            self.update()
        super().mouseReleaseEvent(event)

    # ── Custom Painting ───────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()

        # 1. Background grid
        p.fillRect(0, 0, w, h, QColor("#090d16"))

        # 2. Tracks backgrounds
        for row in range(3):
            layer = 3 - row
            y = self.RULER_HEIGHT + row * self.TRACK_HEIGHT
            bg_clr = QColor("#0e1522" if row % 2 == 0 else "#0b101a")
            p.fillRect(self.HEADER_WIDTH, y, w - self.HEADER_WIDTH, self.TRACK_HEIGHT, bg_clr)
            # Track border divider
            p.setPen(QPen(QColor("#1e293b"), 1))
            p.drawLine(0, y, w, y)

        # 3. Track Headers (Left sidebar)
        p.fillRect(0, 0, self.HEADER_WIDTH, h, QColor("#111827"))
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawLine(self.HEADER_WIDTH, 0, self.HEADER_WIDTH, h)

        # Header Titles
        headers = [
            ("L3 · OVERLAY / FOTO", "#c084fc", "Traccia superiore (Overlay)"),
            ("L2 · VIDEO / AUDIO 2", "#38bdf8", "Traccia intermedia"),
            ("L1 · SFONDO / BASE", "#34d399", "Traccia di fondo (Background)"),
        ]
        hdr_font = QFont("sans-serif", 9, QFont.Weight.Bold)
        p.setFont(hdr_font)

        for row, (title, color_hex, desc) in enumerate(headers):
            y = self.RULER_HEIGHT + row * self.TRACK_HEIGHT
            rect_h = QRect(8, y + 8, self.HEADER_WIDTH - 16, 20)
            p.setPen(QColor(color_hex))
            p.drawText(rect_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
            # Subtitle
            p.setFont(QFont("sans-serif", 8))
            p.setPen(QColor("#64748b"))
            rect_sub = QRect(8, y + 28, self.HEADER_WIDTH - 16, 16)
            p.drawText(rect_sub, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, desc)
            p.setFont(hdr_font)

        # 4. Ruler (Top bar)
        p.fillRect(0, 0, w, self.RULER_HEIGHT, QColor("#0b111c"))
        p.setPen(QPen(QColor("#334155"), 1.2))
        p.drawLine(0, self.RULER_HEIGHT, w, self.RULER_HEIGHT)

        # Time ruler markings
        ruler_font = QFont("monospace", 8)
        p.setFont(ruler_font)
        p.setPen(QColor("#94a3b8"))

        step_sec = 1.0 if self.pixels_per_sec >= 35.0 else 5.0
        tot_sec = self.x_to_sec(w)
        s = 0.0

        while s <= tot_sec:
            x = self.sec_to_x(s)
            p.setPen(QColor("#334155"))
            p.drawLine(int(x), self.RULER_HEIGHT - 6, int(x), self.RULER_HEIGHT)
            # Grid vertical line across tracks
            p.setPen(QPen(QColor(30, 41, 59, 70), 1, Qt.PenStyle.DotLine))
            p.drawLine(int(x), self.RULER_HEIGHT, int(x), h)

            # Major labels
            if s % (step_sec * 2) == 0:
                p.setPen(QColor("#94a3b8"))
                time_str = _fmt_timecode(s)
                p.drawText(int(x + 3), self.RULER_HEIGHT - 8, time_str)
            s += step_sec

        # 5. Paint Clips
        for clip in self.clips:
            is_sel = (clip.cue_id == self.selected_cue_id)
            x1 = self.sec_to_x(clip.start_sec)
            clip_w = max(18.0, clip.duration_sec * self.pixels_per_sec)
            y = self.layer_to_y(clip.layer) + 6
            clip_h = self.TRACK_HEIGHT - 12
            c_rect = QRectF(x1, float(y), clip_w, float(clip_h))

            # Base color theme by media type
            if clip.media_type == MediaType.VIDEO:
                base_c = QColor("#0284c7") if not is_sel else QColor("#38bdf8")
                grad_c = QColor("#0369a1")
                border_c = QColor("#7dd3fc") if is_sel else QColor("#0284c7")
                type_tag = "VID"
            elif clip.media_type == MediaType.IMAGE:
                base_c = QColor("#7c3aed") if not is_sel else QColor("#a855f7")
                grad_c = QColor("#6d28d9")
                border_c = QColor("#d8b4fe") if is_sel else QColor("#7c3aed")
                type_tag = "FOTO"
            else:  # AUDIO
                base_c = QColor("#d97706") if not is_sel else QColor("#fbbf24")
                grad_c = QColor("#b45309")
                border_c = QColor("#fde68a") if is_sel else QColor("#d97706")
                type_tag = "AUD"

            # Rounded clip block
            c_path = QPainterPath()
            c_path.addRoundedRect(c_rect, 4.0, 4.0)

            grad = QLinearGradient(x1, float(y), x1, float(y + clip_h))
            grad.setColorAt(0.0, base_c)
            grad.setColorAt(1.0, grad_c)
            p.fillPath(c_path, grad)

            # Selection stroke
            p.setPen(QPen(border_c, 2.0 if is_sel else 1.0))
            p.drawPath(c_path)

            # Left/Right trim handle notches
            p.setPen(QPen(border_c.lighter(130), 2.0))
            p.drawLine(QPointF(x1 + 3, y + 4), QPointF(x1 + 3, y + clip_h - 4))
            p.drawLine(QPointF(x1 + clip_w - 3, y + 4), QPointF(x1 + clip_w - 3, y + clip_h - 4))

            # Fade In / Fade Out visual sloped indicators
            if clip.fade_in > 0:
                fi_w = min(clip_w * 0.5, clip.fade_in * self.pixels_per_sec)
                p.setPen(QPen(QColor(255, 255, 255, 140), 1.2, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x1, y + clip_h), QPointF(x1 + fi_w, y))

            if clip.fade_out > 0:
                fo_w = min(clip_w * 0.5, clip.fade_out * self.pixels_per_sec)
                p.setPen(QPen(QColor(255, 255, 255, 140), 1.2, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x1 + clip_w - fo_w, y), QPointF(x1 + clip_w, y + clip_h))

            # Clip Title & Duration text
            p.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
            p.setPen(QColor("#ffffff"))
            text_rect = c_rect.adjusted(8, 4, -8, -4)
            dur_str = _fmt_timecode(clip.duration_sec)
            txt = f"[{type_tag}] {clip.name}  ({dur_str})"
            fm = p.fontMetrics()
            elided = fm.elidedText(txt, Qt.TextElideMode.ElideRight, int(text_rect.width()))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        # 6. Playhead cursor (Red broadcast needle)
        px = self.sec_to_x(self.playhead_sec)
        p.setPen(QPen(QColor("#ef4444"), 2.0))
        p.drawLine(QPointF(px, 0.0), QPointF(px, float(h)))

        # Playhead head badge
        head_poly = QPolygonF([
            QPointF(px - 6, 0),
            QPointF(px + 6, 0),
            QPointF(px + 6, self.RULER_HEIGHT - 6),
            QPointF(px, self.RULER_HEIGHT),
            QPointF(px - 6, self.RULER_HEIGHT - 6),
        ])
        p.setBrush(QColor("#ef4444"))
        p.drawPolygon(head_poly)
        p.end()


# ── Main Studio Window / Dialog ───────────────────────────────────────

class GroupTimelineStudioDialog(QDialog):
    """Complete Studio Timeline Arranger Dialog for Group Cues."""

    def __init__(
        self,
        group_cue: Cue,
        child_cues: list[Cue],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"🎬 Studio Timeline Compositore Gruppo — '{group_cue.name}'")
        self.resize(1300, 780)
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(build_stylesheet())

        self._group_cue = group_cue
        self._child_cues = list(child_cues)
        self._is_playing = False
        self._play_start_time = 0.0
        self._play_start_head = 0.0

        # Build clip models strictly from child cues of this group
        self._clips: list[TimelineClip] = []
        for c in self._child_cues:
            # Estimate native duration
            if c.out_point and c.out_point > c.in_point:
                dur = c.out_point - c.in_point
            elif c.media_type == MediaType.IMAGE:
                dur = c.hold_time if c.hold_time > 0 else 10.0
            else:
                dur = max(1.0, (c.out_point or 10.0) - c.in_point)

            self._clips.append(TimelineClip(
                cue=c,
                cue_id=c.cue_id,
                name=c.name,
                media_type=c.media_type,
                file_path=c.file_path,
                layer=c.layer if c.layer in (1, 2, 3) else 1,
                start_sec=max(0.0, float(c.pre_delay)),
                duration_sec=max(0.5, float(dur)),
                in_point=max(0.0, float(c.in_point)),
                out_point=c.out_point,
                volume=c.volume,
                opacity=c.opacity,
                fade_in=c.fade_in,
                fade_out=c.fade_out,
                native_duration_sec=max(dur, (c.out_point or dur)),
            ))

        self._timer_play = QTimer(self)
        self._timer_play.setInterval(33)  # 30 fps preview scrub
        self._timer_play.timeout.connect(self._on_play_tick)

        self._build_ui()
        self._populate_clips_list()

    def _build_ui(self) -> None:
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(12, 10, 12, 10)
        root_lay.setSpacing(10)

        # ── Header Bar ────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("background-color: #0e1626; border: 1px solid #1e293b; border-radius: 6px;")
        hdr_lay = QHBoxLayout(hdr_frame)
        hdr_lay.setContentsMargins(12, 8, 12, 8)
        hdr_lay.setSpacing(10)

        lbl_icon = QLabel("🎬")
        lbl_icon.setFont(QFont("sans-serif", 16))
        hdr_lay.addWidget(lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel(f"STUDIO COMPOSITORE TIMELINE · {self._group_cue.name}")
        lbl_title.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #38bdf8;")
        title_col.addWidget(lbl_title)

        lbl_sub = QLabel("Montaggio multi-traccia non distruttivo (Layer 1, 2, 3) · Modifica solo i file del gruppo")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 10px;")
        title_col.addWidget(lbl_sub)
        hdr_lay.addLayout(title_col, stretch=1)

        self.lbl_tot_dur = QLabel("⏱ Durata Scena: 00:00.00")
        self.lbl_tot_dur.setFont(QFont("monospace", 11, QFont.Weight.Bold))
        self.lbl_tot_dur.setStyleSheet("background-color: #162238; color: #34d399; padding: 4px 10px; border-radius: 4px;")
        hdr_lay.addWidget(self.lbl_tot_dur)

        btn_cancel = QPushButton("↺ Annulla")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setFixedHeight(30)
        btn_cancel.setAccessibleName("Annulla Modifiche Timeline")
        btn_cancel.setAccessibleDescription("Chiude lo studio senza salvare le modifiche apportate alla timeline.")
        btn_cancel.setStyleSheet("""
            QPushButton { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 0 12px; font-weight: bold; }
            QPushButton:hover { background-color: #334155; color: #f8fafc; }
        """)
        btn_cancel.clicked.connect(self.reject)
        hdr_lay.addWidget(btn_cancel)

        btn_save = QPushButton("✓ Salva e Sincronizza nel Gruppo")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setFixedHeight(30)
        btn_save.setAccessibleName("Salva e Sincronizza nel Gruppo")
        btn_save.setAccessibleDescription("Salva ritardi, layer, tagli e dissolvenze all'interno delle cue del gruppo.")
        btn_save.setStyleSheet("""
            QPushButton { background-color: #065f46; color: #34d399; border: 1px solid #10b981; border-radius: 4px; padding: 0 14px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #047857; color: #ffffff; }
        """)
        btn_save.clicked.connect(self._on_save_and_apply)
        hdr_lay.addWidget(btn_save)

        root_lay.addWidget(hdr_frame)

        # ── Upper Section: Files List | Preview Screen | Modifiers ────
        upper_split = QSplitter(Qt.Orientation.Horizontal)
        upper_split.setHandleWidth(6)

        # 1. Left Column: Rigorous Group Elements List
        left_box = QGroupBox(f"📦 ELEMENTI DEL GRUPPO ({len(self._clips)} file)")
        left_lay = QVBoxLayout(left_box)
        left_lay.setContentsMargins(8, 8, 8, 8)
        left_lay.setSpacing(6)

        self.list_items = QListWidget()
        self.list_items.setAccessibleName("Lista File del Gruppo")
        self.list_items.setAccessibleDescription("Elenco dei file assegnati al gruppo. Clicca per selezionare una clip.")
        self.list_items.setStyleSheet("""
            QListWidget { background-color: #0a0f18; border: 1px solid #1e293b; border-radius: 4px; }
            QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #16202e; }
            QListWidget::item:selected { background-color: #1e293b; color: #38bdf8; border-radius: 3px; }
            QListWidget::item:hover { background-color: #131c2a; }
        """)
        self.list_items.currentRowChanged.connect(self._on_list_selection_changed)
        left_lay.addWidget(self.list_items)

        lbl_guide = QLabel("🔒 File vincolati al gruppo per evitare inserimenti accidentali o file estranei.")
        lbl_guide.setWordWrap(True)
        lbl_guide.setStyleSheet("color: #64748b; font-size: 9px;")
        left_lay.addWidget(lbl_guide)

        upper_split.addWidget(left_box)
        upper_split.setStretchFactor(0, 25)

        # 2. Center Column: Multi-layer Preview & Transport controls
        prev_box = QGroupBox("🖥️ ANTEPRIMA MULTI-LAYER & TRASPORTO")
        prev_lay = QVBoxLayout(prev_box)
        prev_lay.setContentsMargins(8, 8, 8, 8)
        prev_lay.setSpacing(6)

        self.preview_screen = QFrame()
        self.preview_screen.setMinimumHeight(140)
        self.preview_screen.setStyleSheet("background-color: #03060a; border: 1px solid #1e293b; border-radius: 4px;")
        scr_lay = QVBoxLayout(self.preview_screen)
        scr_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_preview_info = QLabel("▶ SCHERMO ANTEPRIMA SANDBOX\nComposizione Multi-Layer sincronizzata")
        self.lbl_preview_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_info.setStyleSheet("color: #475569; font-weight: bold; font-size: 12px;")
        scr_lay.addWidget(self.lbl_preview_info)
        prev_lay.addWidget(self.preview_screen, stretch=1)

        # Transport Controls
        tr_row = QHBoxLayout()
        tr_row.setSpacing(6)

        self.btn_rewind = QPushButton("⏮ Inizio")
        self.btn_rewind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rewind.setFixedHeight(28)
        self.btn_rewind.setAccessibleName("Riavvolgi all'Inizio")
        self.btn_rewind.setAccessibleDescription("Porta la testina di riproduzione al secondo zero.")
        self.btn_rewind.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px;")
        self.btn_rewind.clicked.connect(self._on_rewind)
        tr_row.addWidget(self.btn_rewind)

        self.btn_play_pause = QPushButton("▶  Play")
        self.btn_play_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_pause.setFixedHeight(28)
        self.btn_play_pause.setAccessibleName("Play o Pausa Anteprima Gruppo")
        self.btn_play_pause.setAccessibleDescription("Avvia o mette in pausa la riproduzione sincronizzata multi-canale.")
        self.btn_play_pause.setStyleSheet(f"background-color: {CLR_GO}; color: #04130a; border: none; border-radius: 4px; font-weight: bold;")
        self.btn_play_pause.clicked.connect(self._toggle_playback)
        tr_row.addWidget(self.btn_play_pause)

        self.lbl_timecode = QLabel("00:00.00 / 00:00.00")
        self.lbl_timecode.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        self.lbl_timecode.setStyleSheet("color: #38bdf8; background-color: #0d1522; padding: 4px 8px; border-radius: 4px;")
        tr_row.addWidget(self.lbl_timecode)
        tr_row.addStretch()

        prev_lay.addLayout(tr_row)
        upper_split.addWidget(prev_box)
        upper_split.setStretchFactor(1, 45)

        # 3. Right Column: Non-destructive clip modifiers
        mod_box = QGroupBox("🛠️ MODIFICATORI CLIP ATTIVA")
        mod_lay = QVBoxLayout(mod_box)
        mod_lay.setContentsMargins(10, 8, 10, 8)
        mod_lay.setSpacing(6)

        self.lbl_selected_title = QLabel("Nessuna clip selezionata")
        self.lbl_selected_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        mod_lay.addWidget(self.lbl_selected_title)

        # Layer assignment combo
        l_row = QHBoxLayout()
        l_row.addWidget(QLabel("Layer:"), stretch=0)
        self.combo_layer = QComboBox()
        self.combo_layer.addItems(["Layer 1 (Sfondo)", "Layer 2 (Intermedio)", "Layer 3 (Overlay)"])
        self.combo_layer.currentIndexChanged.connect(self._on_layer_combo_changed)
        l_row.addWidget(self.combo_layer, stretch=1)
        mod_lay.addLayout(l_row)

        # Start offset (Pre-delay)
        st_row = QHBoxLayout()
        st_row.addWidget(QLabel("Avvio (s):"), stretch=0)
        self.spin_start = SmartDoubleSpinBox()
        self.spin_start.setDecimals(2)
        self.spin_start.setSingleStep(0.25)
        self.spin_start.setRange(0.0, 3600.0)
        self.spin_start.valueChanged.connect(self._on_spin_start_changed)
        st_row.addWidget(self.spin_start, stretch=1)
        mod_lay.addLayout(st_row)

        # Trim IN / OUT
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Taglio IN:"), stretch=0)
        self.spin_in = SmartDoubleSpinBox()
        self.spin_in.setDecimals(2)
        self.spin_in.setSingleStep(0.25)
        self.spin_in.setRange(0.0, 3600.0)
        self.spin_in.valueChanged.connect(self._on_spin_in_changed)
        in_row.addWidget(self.spin_in, stretch=1)
        mod_lay.addLayout(in_row)

        # Fades In / Out
        f_row = QHBoxLayout()
        f_row.addWidget(QLabel("Fade In:"), stretch=0)
        self.spin_fi = SmartDoubleSpinBox()
        self.spin_fi.setDecimals(1)
        self.spin_fi.setSingleStep(0.5)
        self.spin_fi.setRange(0.0, 60.0)
        self.spin_fi.valueChanged.connect(self._on_spin_fi_changed)
        f_row.addWidget(self.spin_fi, stretch=1)

        f_row.addWidget(QLabel("Fade Out:"), stretch=0)
        self.spin_fo = SmartDoubleSpinBox()
        self.spin_fo.setDecimals(1)
        self.spin_fo.setSingleStep(0.5)
        self.spin_fo.setRange(0.0, 60.0)
        self.spin_fo.valueChanged.connect(self._on_spin_fo_changed)
        f_row.addWidget(self.spin_fo, stretch=1)
        mod_lay.addLayout(f_row)

        # Volume slider
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume:"), stretch=0)
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.valueChanged.connect(self._on_slider_vol_changed)
        vol_row.addWidget(self.slider_vol, stretch=1)
        self.lbl_vol_val = QLabel("100%")
        self.lbl_vol_val.setMinimumWidth(36)
        vol_row.addWidget(self.lbl_vol_val)
        mod_lay.addLayout(vol_row)

        # Opacity slider
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Opacità:"), stretch=0)
        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(0, 100)
        self.slider_op.valueChanged.connect(self._on_slider_op_changed)
        op_row.addWidget(self.slider_op, stretch=1)
        self.lbl_op_val = QLabel("100%")
        self.lbl_op_val.setMinimumWidth(36)
        op_row.addWidget(self.lbl_op_val)
        mod_lay.addLayout(op_row)

        mod_lay.addStretch()
        upper_split.addWidget(mod_box)
        upper_split.setStretchFactor(2, 30)

        root_lay.addWidget(upper_split, stretch=4)

        # ── Lower Section: 3-Layer Timeline Arranger Canvas ───────────
        timeline_frame = QFrame()
        timeline_frame.setStyleSheet("background-color: #0b111a; border: 1px solid #1e293b; border-radius: 6px;")
        tl_lay = QVBoxLayout(timeline_frame)
        tl_lay.setContentsMargins(8, 6, 8, 8)
        tl_lay.setSpacing(6)

        # Timeline Header / Zoom Bar
        tl_tools = QHBoxLayout()
        tl_tools.setSpacing(8)

        lbl_tl_title = QLabel("⏱ TIMELINE DELLE 3 TRACCE (Layer 3 Sopra ➔ Layer 1 Sfondo)")
        lbl_tl_title.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
        lbl_tl_title.setStyleSheet("color: #38bdf8;")
        tl_tools.addWidget(lbl_tl_title)
        tl_tools.addStretch()

        self.chk_snap = QCheckBox("🧲 Snap a griglia (0.25s)")
        self.chk_snap.setChecked(True)
        self.chk_snap.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.chk_snap.toggled.connect(self._on_snap_toggled)
        tl_tools.addWidget(self.chk_snap)

        btn_zm_out = QPushButton("🔍 - Zoom Out")
        btn_zm_out.setFixedHeight(22)
        btn_zm_out.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 3px; padding: 0 8px; font-size: 10px;")
        btn_zm_out.clicked.connect(self._on_zoom_out)
        tl_tools.addWidget(btn_zm_out)

        btn_zm_in = QPushButton("🔍 + Zoom In")
        btn_zm_in.setFixedHeight(22)
        btn_zm_in.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 3px; padding: 0 8px; font-size: 10px;")
        btn_zm_in.clicked.connect(self._on_zoom_in)
        tl_tools.addWidget(btn_zm_in)

        tl_lay.addLayout(tl_tools)

        # Scroll Area holding the Canvas
        self.scroll_tl = QScrollArea()
        self.scroll_tl.setWidgetResizable(True)
        self.scroll_tl.setStyleSheet("QScrollArea { border: 1px solid #16202e; background-color: #070b12; }")

        self.canvas = GroupTimelineCanvas()
        self.canvas.setAccessibleName("Canvas Timeline a 3 Layer")
        self.canvas.setAccessibleDescription("Compositore visivo a 3 layer per allineare temporalmente i file del gruppo.")
        self.canvas.clips = self._clips
        self.canvas.clip_selected.connect(self._on_canvas_clip_selected)
        self.canvas.clip_moved.connect(self._on_canvas_clip_moved)
        self.canvas.playhead_moved.connect(self._on_canvas_playhead_moved)

        self.scroll_tl.setWidget(self.canvas)
        tl_lay.addWidget(self.scroll_tl)

        root_lay.addWidget(timeline_frame, stretch=5)
        self._update_total_duration_ui()

    # ── Population and Synchronization ────────────────────────────────

    def _populate_clips_list(self) -> None:
        self.list_items.blockSignals(True)
        self.list_items.clear()
        for clip in self._clips:
            type_tag = "VID" if clip.media_type == MediaType.VIDEO else ("FOTO" if clip.media_type == MediaType.IMAGE else "AUD")
            txt = f"[{type_tag}] {clip.name}  ➔  L{clip.layer} (+{clip.start_sec:.1f}s)"
            item = QListWidgetItem(txt)
            if clip.media_type == MediaType.VIDEO:
                item.setForeground(QColor("#38bdf8"))
            elif clip.media_type == MediaType.IMAGE:
                item.setForeground(QColor("#c084fc"))
            else:
                item.setForeground(QColor("#fbbf24"))
            self.list_items.addItem(item)
        self.list_items.blockSignals(False)

        if self._clips:
            self.list_items.setCurrentRow(0)
            self._select_clip(self._clips[0].cue_id)

    def _select_clip(self, cue_id: int) -> None:
        clip = next((c for c in self._clips if c.cue_id == cue_id), None)
        self.canvas.select_clip(cue_id)

        if not clip:
            self.lbl_selected_title.setText("Nessuna clip selezionata")
            self.combo_layer.setEnabled(False)
            self.spin_start.setEnabled(False)
            self.spin_in.setEnabled(False)
            self.spin_fi.setEnabled(False)
            self.spin_fo.setEnabled(False)
            self.slider_vol.setEnabled(False)
            self.slider_op.setEnabled(False)
            return

        self.combo_layer.setEnabled(True)
        self.spin_start.setEnabled(True)
        self.spin_in.setEnabled(True)
        self.spin_fi.setEnabled(True)
        self.spin_fo.setEnabled(True)
        self.slider_vol.setEnabled(clip.media_type in (MediaType.VIDEO, MediaType.AUDIO))
        self.slider_op.setEnabled(clip.media_type in (MediaType.VIDEO, MediaType.IMAGE))

        self.lbl_selected_title.setText(f"Clip: {clip.name}")
        self.combo_layer.blockSignals(True)
        self.combo_layer.setCurrentIndex(clip.layer - 1)
        self.combo_layer.blockSignals(False)

        self.spin_start.blockSignals(True)
        self.spin_start.setValue(clip.start_sec)
        self.spin_start.blockSignals(False)

        self.spin_in.blockSignals(True)
        self.spin_in.setValue(clip.in_point)
        self.spin_in.blockSignals(False)

        self.spin_fi.blockSignals(True)
        self.spin_fi.setValue(clip.fade_in)
        self.spin_fi.blockSignals(False)

        self.spin_fo.blockSignals(True)
        self.spin_fo.setValue(clip.fade_out)
        self.spin_fo.blockSignals(False)

        self.slider_vol.blockSignals(True)
        self.slider_vol.setValue(int(round(clip.volume * 100.0)))
        self.lbl_vol_val.setText(f"{int(round(clip.volume * 100.0))}%")
        self.slider_vol.blockSignals(False)

        self.slider_op.blockSignals(True)
        self.slider_op.setValue(int(round(clip.opacity * 100.0)))
        self.lbl_op_val.setText(f"{int(round(clip.opacity * 100.0))}%")
        self.slider_op.blockSignals(False)

    def _update_total_duration_ui(self) -> None:
        tot = self.canvas.total_composition_duration()
        self.lbl_tot_dur.setText(f"⏱ Durata Scena: {_fmt_timecode(tot)}")
        cur = self.canvas.playhead_sec
        self.lbl_timecode.setText(f"{_fmt_timecode(cur)} / {_fmt_timecode(tot)}")

    # ── UI Event Callbacks ────────────────────────────────────────────

    def _on_list_selection_changed(self, row: int) -> None:
        if 0 <= row < len(self._clips):
            self._select_clip(self._clips[row].cue_id)

    def _on_canvas_clip_selected(self, cue_id: int) -> None:
        for idx, clip in enumerate(self._clips):
            if clip.cue_id == cue_id:
                self.list_items.blockSignals(True)
                self.list_items.setCurrentRow(idx)
                self.list_items.blockSignals(False)
                self._select_clip(cue_id)
                return
        self._select_clip(-1)

    def _on_canvas_clip_moved(self, cue_id: int) -> None:
        self._select_clip(cue_id)
        self._populate_clips_list()
        self._update_total_duration_ui()

    def _on_canvas_playhead_moved(self, sec: float) -> None:
        tot = self.canvas.total_composition_duration()
        self.lbl_timecode.setText(f"{_fmt_timecode(sec)} / {_fmt_timecode(tot)}")

    def _on_layer_combo_changed(self, idx: int) -> None:
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.layer = idx + 1
                self.canvas.update()
                self._populate_clips_list()

    def _on_spin_start_changed(self, val: float) -> None:
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.start_sec = max(0.0, float(val))
                self.canvas.update()
                self._populate_clips_list()
                self._update_total_duration_ui()

    def _on_spin_in_changed(self, val: float) -> None:
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.in_point = max(0.0, float(val))
                self.canvas.update()

    def _on_spin_fi_changed(self, val: float) -> None:
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.fade_in = max(0.0, float(val))
                self.canvas.update()

    def _on_spin_fo_changed(self, val: float) -> None:
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.fade_out = max(0.0, float(val))
                self.canvas.update()

    def _on_slider_vol_changed(self, val: int) -> None:
        self.lbl_vol_val.setText(f"{val}%")
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.volume = val / 100.0

    def _on_slider_op_changed(self, val: int) -> None:
        self.lbl_op_val.setText(f"{val}%")
        if self.canvas.selected_cue_id:
            clip = next((c for c in self._clips if c.cue_id == self.canvas.selected_cue_id), None)
            if clip:
                clip.opacity = val / 100.0

    def _on_snap_toggled(self, checked: bool) -> None:
        self.canvas.snap_enabled = checked

    def _on_zoom_in(self) -> None:
        self.canvas.zoom_in()

    def _on_zoom_out(self) -> None:
        self.canvas.zoom_out()

    def _on_rewind(self) -> None:
        self._is_playing = False
        self._timer_play.stop()
        self.btn_play_pause.setText("▶  Play")
        self.canvas.set_playhead(0.0)
        self._update_total_duration_ui()

    def _toggle_playback(self) -> None:
        if self._is_playing:
            self._is_playing = False
            self._timer_play.stop()
            self.btn_play_pause.setText("▶  Play")
        else:
            self._is_playing = True
            self._play_start_time = time.monotonic()
            self._play_start_head = self.canvas.playhead_sec
            self._timer_play.start()
            self.btn_play_pause.setText("⏸  Pausa")

    def _on_play_tick(self) -> None:
        if not self._is_playing:
            return
        now = time.monotonic()
        elapsed = now - self._play_start_time
        new_head = self._play_start_head + elapsed
        tot = self.canvas.total_composition_duration()

        if new_head >= tot:
            new_head = 0.0
            self._play_start_time = time.monotonic()
            self._play_start_head = 0.0

        self.canvas.set_playhead(new_head)
        self._update_total_duration_ui()

    # ── Final Save and Sync ───────────────────────────────────────────

    def _on_save_and_apply(self) -> None:
        """Apply all visual modifications back into the child cues and mark group as composed."""
        self._timer_play.stop()
        for clip in self._clips:
            c = clip.cue
            c.layer = clip.layer
            c.pre_delay = max(0.0, round(clip.start_sec, 2))
            c.in_point = max(0.0, round(clip.in_point, 2))
            if clip.out_point is not None:
                c.out_point = max(c.in_point + 0.1, round(clip.out_point, 2))
            c.volume = max(0.0, min(1.0, clip.volume))
            c.opacity = max(0.0, min(1.0, clip.opacity))
            c.fade_in = max(0.0, round(clip.fade_in, 1))
            c.fade_out = max(0.0, round(clip.fade_out, 1))

        self._group_cue.timeline_composed = True
        self.accept()
