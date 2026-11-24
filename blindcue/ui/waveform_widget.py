"""Audio/Video/Image interactive timeline with waveform peaks, fade pallini, volume/opacity keyframes, and virtual sections."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygon,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)


class _ZoomStepButton(QPushButton):
    """Square zoom +/- button drawing symmetrical crisp vector strokes instead of font glyphs."""

    def __init__(self, is_plus: bool, parent: QWidget | None = None) -> None:
        """Create a cached +/- zoom button (``is_plus`` selects the glyph)."""
        super().__init__("", parent)
        self._is_plus = is_plus
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the cached +/- glyph instead of relying on OS font symbols."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        color = QColor("#e2e8f0") if self.isEnabled() else QColor("#475569")
        painter.setPen(QPen(color, 1.5))
        cx = self.width() // 2
        cy = self.height() // 2
        painter.drawLine(cx - 4, cy, cx + 4, cy)
        if self._is_plus:
            painter.drawLine(cx, cy - 4, cx, cy + 4)
        painter.end()

from engine.envelope import (
    FADE_CURVE_LABELS,
    MIN_POINT_DB,
    add_or_update_point,
    apply_fade_curve,
    db_to_level,
    evaluate_points_envelope,
    format_level_db,
    level_to_db,
    move_point,
    normalize_points,
    normalize_sections,
    remove_point,
    resize_section_divider,
)
from models.cue import CueSection, MediaType
from ui.section_bar import SECTION_PALETTE, SectionControlBar
from ui.theme import CLR_ACCENT, CLR_LIVE, CLR_PANEL, get_active_theme

_CLR_PLAYHEAD = "#fbbf24"
_CLR_PLAYHEAD_GLOW = "#fef08a"
_CLR_ENV_VOL = "#38bdf8"
_CLR_ENV_OP = "#c084fc"

_ENV_TOP_Y = 24.0
_ENV_BOT_PAD = 12.0


def _format_playhead_time(seconds: float) -> str:
    """Format seconds as MM:SS.cc with centisecond precision."""
    sec = max(0.0, float(seconds))
    mins = int(sec // 60)
    rem = sec - mins * 60
    return f"{mins:02d}:{rem:05.2f}"


class WaveformWidget(QWidget):
    """Interactive timeline canvas for waveform/image opacity, fade handles, keyframes, and sections."""

    in_changed = Signal(float)
    out_changed = Signal(float)
    seek_requested = Signal(float)
    fade_in_changed = Signal(float)
    fade_out_changed = Signal(float)
    fade_curve_changed = Signal(str)
    envelope_points_changed = Signal(str, list)   # mode ("volume"|"opacity"), [[t, v], ...]
    sections_changed = Signal(list)               # list[CueSection]
    view_changed = Signal(float, float, float)    # zoom_factor, view_start_sec, view_span_sec

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the interactive waveform (peaks, envelopes, in/out and sections)."""
        super().__init__(parent)
        self._peaks: np.ndarray | None = None
        self._media_type: MediaType | None = MediaType.AUDIO
        self._envelope_mode: str = "volume"  # "volume" or "opacity"

        self._in_point: float = 0.0
        self._out_point: float = 1.0  # normalized 0-1
        self._in_sec: float = 0.0
        self._out_sec: float | None = None
        self._duration_sec: float = 0.0

        self._zoom: float = 1.0
        self._view_start_sec: float = 0.0
        self._pan_drag_last_x: float | None = None

        self._playhead: float | None = None
        self._playhead_sec: float | None = None
        self._markers: list[tuple[float, str]] = []  # 2.7: (seconds, label)

        self._fade_in_sec: float = 0.0
        self._fade_out_sec: float = 0.0
        self._fade_curve: str = "log"
        self._show_fade_out: bool = True

        self._base_volume: float = 1.0
        self._base_opacity: float = 1.0
        self._volume_points: list[list[float]] = []
        self._opacity_points: list[list[float]] = []
        self._sections: list[CueSection] = []
        self._active_section_idx: int = -1

        self._dragging_kind: str | None = None
        self._dragging_idx: int = -1
        self._hover_kind: str | None = None
        self._hover_idx: int = -1
        self._last_emitted_seek: float = -1.0

        self.setMinimumHeight(88)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background-color: {CLR_PANEL};")

    # ── State Configuration API ───────────────────────────────────────

    def set_peaks(self, peaks: np.ndarray) -> None:
        """Attach the pre-computed min/max peak pairs used by the painter.

        Peaks are produced asynchronously by the audio analyser: the widget
        only stores the array and repaints, so decoding never blocks the UI.
        """
        self._peaks = peaks
        self.update()

    def set_media_context(
        self,
        media_type: MediaType | None,
        envelope_mode: str = "volume",
        show_fade_out: bool = True,
    ) -> None:
        """Tell the widget what kind of media it is drawing.

        Images have no audio peaks, so they always use the opacity envelope;
        audio and video use the volume envelope unless explicitly overridden.
        """
        self._media_type = media_type
        self._envelope_mode = "opacity" if (envelope_mode == "opacity" or media_type == MediaType.IMAGE) else "volume"
        self._show_fade_out = show_fade_out
        self.update()

    def set_envelope_mode(self, mode: str) -> None:
        """Switch between the volume envelope and the opacity envelope."""
        target = "opacity" if mode == "opacity" else "volume"
        if self._envelope_mode != target:
            self._envelope_mode = target
            self.update()

    def set_fades(self, fade_in: float, fade_out: float, fade_curve: str = "log") -> None:
        """Draw the fade-in/fade-out triangles on the waveform.

        The curve is only used to shape the visual ramp: the actual audio
        envelope is applied by the player, the widget just mirrors it.
        """
        self._fade_in_sec = max(0.0, float(fade_in))
        self._fade_out_sec = max(0.0, float(fade_out))
        self._fade_curve = fade_curve if fade_curve in FADE_CURVE_LABELS else "log"
        self.update()

    def set_envelopes(
        self,
        *,
        base_volume: float,
        base_opacity: float,
        volume_points: Sequence[Sequence[float]],
        opacity_points: Sequence[Sequence[float]],
    ) -> None:
        """Replace the automation curves drawn over the waveform.

        Points are ``(position, value)`` pairs normalised 0-1; the widget
        normalises and clones them so later edits of the cue cannot mutate the
        arrays already handed to the painter.
        """
        self._base_volume = max(0.0, min(1.0, float(base_volume)))
        self._base_opacity = max(0.0, min(1.0, float(base_opacity)))
        self._volume_points = normalize_points(volume_points)
        self._opacity_points = normalize_points(opacity_points)
        self.update()

    def set_sections(self, sections: Sequence[CueSection], active_idx: int = -1) -> None:
        """Draw the cue sections (loops/pre-delay zones) behind the waveform.

        Sections are clipped against the effective in/out range, and are
        ignored for images because a still has no timeline.
        """
        eff_end = self._effective_end_sec()
        if eff_end > 0 and self._media_type in (MediaType.VIDEO, MediaType.AUDIO):
            self._sections = normalize_sections(sections, self._in_sec, eff_end)
        else:
            self._sections = []
        self._active_section_idx = active_idx
        self.update()

    def set_active_section_index(self, active_idx: int) -> None:
        """Highlight the section currently being played (``-1`` = none)."""
        if self._active_section_idx != active_idx:
            self._active_section_idx = active_idx
            self.update()

    def set_in_out(self, in_norm: float, out_norm: float) -> None:
        """Set the in/out points as normalised 0-1 fractions of the media."""
        self._in_point = in_norm
        self._out_point = out_norm
        self.update()

    def set_in_out_seconds(self, in_sec: float, out_sec: float | None, duration_sec: float) -> None:
        """Set in/out points in seconds, converting them to normalised values.

        A ``None`` or zero out point means "end of media".
        """
        self._in_sec = max(0.0, in_sec)
        self._out_sec = out_sec
        self._duration_sec = max(0.001, duration_sec) if duration_sec > 0 else 0.0

        if self._duration_sec > 0:
            self._in_point = min(1.0, max(0.0, self._in_sec / self._duration_sec))
            if self._out_sec is not None and self._out_sec > 0:
                self._out_point = min(1.0, max(0.0, self._out_sec / self._duration_sec))
            else:
                self._out_point = 1.0
            if self._playhead is not None and self._playhead_sec is None:
                self._playhead_sec = round(self._playhead * self._duration_sec, 2)
        else:
            self._in_point = 0.0
            self._out_point = 1.0
        self._clamp_view()
        self.view_changed.emit(self._zoom, self._view_start_sec, self._view_span_sec())
        self.update()

    def set_markers(self, items: list[tuple[float, str]]) -> None:
        """2.7: named points of the file, drawn as amber dashed lines."""
        self._markers = list(items)
        self.update()

    def _paint_markers(self, painter: QPainter, w: int, h: int) -> None:
        if not self._markers or self._duration_sec <= 0:
            return
        pen = QPen(QColor("#f59e0b"), 1, Qt.PenStyle.DashLine)
        painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
        for sec, label in self._markers:
            x = self._sec_to_x(sec)
            if x < 0 or x > w:
                continue
            painter.setPen(pen)
            painter.drawLine(int(x), 0, int(x), h)
            painter.setPen(QColor("#fbbf24"))
            painter.drawText(int(x) + 3, h - 4, label)

    def set_playhead(self, norm_pos: float | None) -> None:
        """Move the playhead to a normalised position (``None`` hides it)."""
        if norm_pos is None:
            if self._playhead is not None or self._playhead_sec is not None:
                self._playhead = None
                self._playhead_sec = None
                self.update()
            return
        clamped = min(1.0, max(0.0, float(norm_pos)))
        sec = round(clamped * self._duration_sec, 2) if self._duration_sec > 0 else None
        if self._playhead != clamped or self._playhead_sec != sec:
            self._playhead = clamped
            self._playhead_sec = sec
            self.update()

    def set_playhead_seconds(
        self, sec: float | None, duration_sec: float | None = None
    ) -> None:
        """Move the playhead using absolute seconds, refreshing the duration.

        Passing ``None`` hides the playhead; *duration_sec* is refreshed when
        the media metadata arrives asynchronously after the first paint.
        """
        if duration_sec is not None and duration_sec > 0:
            self._duration_sec = max(0.001, duration_sec)
        if sec is None or self._duration_sec <= 0:
            self.set_playhead(None)
            return
        clamped_sec = min(self._duration_sec, max(0.0, float(sec)))
        norm = min(1.0, max(0.0, clamped_sec / self._duration_sec))
        rounded_sec = round(clamped_sec, 2)
        if self._playhead != norm or self._playhead_sec != rounded_sec:
            self._playhead = norm
            self._playhead_sec = rounded_sec
            self.update()

    def playhead_seconds(self) -> float | None:
        """Playhead position in seconds (``None`` when no media is loaded)."""
        if self._playhead is None or self._duration_sec <= 0:
            return None
        if self._playhead_sec is not None:
            return self._playhead_sec
        return round(self._playhead * self._duration_sec, 2)

    def duration_seconds(self) -> float:
        """Media duration in seconds known by the widget (0 if unknown)."""
        return self._duration_sec

    # ── Zoom & Viewport Helpers ───────────────────────────────────────

    def zoom_factor(self) -> float:
        """Current horizontal zoom factor (1.0 = fit the whole media)."""
        return self._zoom

    def view_start_sec(self) -> float:
        """Left edge of the visible window, in seconds."""
        return self._view_start_sec

    def view_span_sec(self) -> float:
        """Width of the visible window, in seconds."""
        return self._view_span_sec()

    def _view_span_sec(self) -> float:
        if self._duration_sec <= 0:
            return 0.0
        return self._duration_sec / max(1.0, self._zoom)

    def _clamp_view(self) -> None:
        self._zoom = max(1.0, min(32.0, float(self._zoom)))
        if self._duration_sec <= 0 or self._zoom <= 1.001:
            self._zoom = 1.0
            self._view_start_sec = 0.0
            return
        span = self._duration_sec / self._zoom
        max_start = max(0.0, self._duration_sec - span)
        self._view_start_sec = max(0.0, min(max_start, float(self._view_start_sec)))

    def set_zoom(self, factor: float, anchor_sec: float | None = None) -> None:
        """Zoom horizontally [1.0..32.0], keeping *anchor_sec* anchored in place."""
        new_zoom = max(1.0, min(32.0, float(factor)))
        if new_zoom <= 1.02:
            new_zoom = 1.0
        if self._duration_sec <= 0:
            self._zoom = 1.0
            self._view_start_sec = 0.0
            self.view_changed.emit(self._zoom, 0.0, 0.0)
            self.update()
            return

        old_span = self._view_span_sec()
        if anchor_sec is None:
            ph = self.playhead_seconds()
            if ph is not None and self._view_start_sec <= ph <= self._view_start_sec + old_span:
                anchor = ph
            else:
                anchor = self._view_start_sec + old_span * 0.5
        else:
            anchor = max(0.0, min(self._duration_sec, float(anchor_sec)))

        frac = ((anchor - self._view_start_sec) / old_span) if old_span > 0 else 0.5
        frac = max(0.0, min(1.0, frac))

        self._zoom = new_zoom
        new_span = self._duration_sec / self._zoom
        self._view_start_sec = anchor - frac * new_span
        self._clamp_view()
        self.view_changed.emit(self._zoom, self._view_start_sec, self._view_span_sec())
        self.update()

    def set_view_start(self, start_sec: float) -> None:
        """Pan horizontal viewport start time cleanly."""
        self._view_start_sec = start_sec
        self._clamp_view()
        self.view_changed.emit(self._zoom, self._view_start_sec, self._view_span_sec())
        self.update()

    def reset_zoom(self) -> None:
        """Restore 1x zoom."""
        self.set_zoom(1.0)

    # ── Coordinate & Mode Helpers ─────────────────────────────────────

    def _effective_end_sec(self) -> float:
        if self._duration_sec <= 0:
            return 0.0
        if self._out_sec is not None and self._out_sec > self._in_sec:
            return min(self._duration_sec, self._out_sec)
        return self._duration_sec

    def _active_points(self) -> list[list[float]]:
        return self._opacity_points if self._envelope_mode == "opacity" else self._volume_points

    def _set_active_points(self, pts: list[list[float]]) -> None:
        if self._envelope_mode == "opacity":
            self._opacity_points = pts
        else:
            self._volume_points = pts

    def _active_base_level(self) -> float:
        return self._base_opacity if self._envelope_mode == "opacity" else self._base_volume

    def _sec_to_x(self, sec: float) -> float:
        span = self._view_span_sec()
        if span <= 0:
            return 0.0
        return ((sec - self._view_start_sec) / span) * max(1, self.width())

    def _x_to_sec(self, x: float) -> float:
        span = self._view_span_sec()
        if span <= 0:
            return 0.0
        w = max(1, self.width())
        return max(0.0, min(self._duration_sec, self._view_start_sec + (x / w) * span))

    def _level_to_y(self, level: float) -> float:
        bot = max(_ENV_TOP_Y + 12.0, self.height() - _ENV_BOT_PAD)
        lv = max(0.0, min(1.0, float(level)))
        return bot - lv * (bot - _ENV_TOP_Y)

    def _y_to_level(self, y: float) -> float:
        bot = max(_ENV_TOP_Y + 12.0, self.height() - _ENV_BOT_PAD)
        span = max(1.0, bot - _ENV_TOP_Y)
        return max(0.0, min(1.0, (bot - y) / span))

    def _fade_handle_positions(self) -> tuple[QPointF, QPointF]:
        w = max(1, self.width())
        in_x = self._sec_to_x(self._in_sec)
        out_x = self._sec_to_x(self._effective_end_sec())
        fi_px = self._sec_to_x(self._in_sec + self._fade_in_sec)
        fo_px = self._sec_to_x(max(self._in_sec, self._effective_end_sec() - self._fade_out_sec))
        fi_x = fi_px if self._fade_in_sec > 0 else (in_x + 5.0)
        fo_x = fo_px if self._fade_out_sec > 0 else (out_x - 5.0)
        return QPointF(min(max(-20.0, fi_x), w + 20.0), _ENV_TOP_Y + 2.0), QPointF(min(max(-20.0, fo_x), w + 20.0), _ENV_TOP_Y + 2.0)

    # ── Mouse Hit-Testing & Interaction ───────────────────────────────

    def _hit_test_target(self, x: float, y: float) -> str:
        """Compatibility helper returning 'IN', 'OUT', or 'PLAYHEAD' for top-level handle tests."""
        kind, _idx = self._hit_test_detailed(x, y)
        if kind in ("IN", "OUT"):
            return kind
        return "PLAYHEAD"

    def _hit_test_detailed(self, x: float, y: float) -> tuple[str, int]:
        """Priority hit test: Point > Fade Pallini > IN/OUT > Section Dividers > Envelope Line > Playhead."""
        if self._duration_sec <= 0:
            return ("NONE", -1)

        pts = self._active_points()
        for idx, (pt_t, pt_v) in enumerate(pts):
            px = self._sec_to_x(pt_t)
            py = self._level_to_y(pt_v)
            if (x - px) ** 2 + (y - py) ** 2 <= 81:
                return ("POINT", idx)

        fi_pt, fo_pt = self._fade_handle_positions()
        w = max(1, self.width())
        fi_actual_x = self._sec_to_x(self._in_sec + self._fade_in_sec) if self._fade_in_sec > 0 else (self._sec_to_x(self._in_sec) + 5.0)
        fo_actual_x = self._sec_to_x(max(self._in_sec, self._effective_end_sec() - self._fade_out_sec)) if self._fade_out_sec > 0 else (self._sec_to_x(self._effective_end_sec()) - 5.0)
        dist_fi = (x - fi_pt.x()) ** 2 + (y - fi_pt.y()) ** 2
        dist_fo = (x - fo_pt.x()) ** 2 + (y - fo_pt.y()) ** 2
        fi_hit = (-12 <= fi_actual_x <= w + 12) and dist_fi <= 100
        fo_hit = self._show_fade_out and (-12 <= fo_actual_x <= w + 12) and dist_fo <= 100
        if fi_hit and fo_hit:
            return ("FADE_IN", -1) if dist_fi <= dist_fo else ("FADE_OUT", -1)
        if fi_hit:
            return ("FADE_IN", -1)
        if fo_hit:
            return ("FADE_OUT", -1)

        if self._media_type in (MediaType.VIDEO, MediaType.AUDIO):
            h = max(1, self.height())
            in_x = self._sec_to_x(self._in_sec)
            out_x = min(float(w - 1), self._sec_to_x(self._effective_end_sec())) if self._zoom <= 1.001 else self._sec_to_x(self._effective_end_sec())
            in_badge_zone = y <= 18 or y >= h - 18
            tol = 14 if in_badge_zone else 7

            dist_in = abs(x - in_x)
            dist_out = abs(x - out_x)
            near_in = (-15 <= in_x <= w + 15) and dist_in <= tol
            near_out = (-15 <= out_x <= w + 15) and dist_out <= tol
            if near_in and near_out:
                return ("IN", -1) if dist_in <= dist_out else ("OUT", -1)
            if near_in:
                return ("IN", -1)
            if near_out:
                return ("OUT", -1)

            for div_idx in range(len(self._sections) - 1):
                div_sec = self._sections[div_idx].end
                if div_sec is not None:
                    dx = abs(x - self._sec_to_x(div_sec))
                    if dx <= 6 and y >= 18:
                        return ("SECTION_DIV", div_idx)

        sec = self._x_to_sec(x)
        eff_end = self._effective_end_sec()
        if y >= _ENV_TOP_Y - 5 and self._in_sec <= sec <= eff_end:
            env_y = self._level_to_y(
                evaluate_points_envelope(sec, pts, self._active_base_level())
            )
            if abs(y - env_y) <= 8:
                return ("ENVELOPE_LINE", -1)

        return ("PLAYHEAD", -1)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Create/remove envelope points, seek, or open the context menu."""
        if self._duration_sec <= 0:
            return
        pos = event.position()
        kind, idx = self._hit_test_detailed(pos.x(), pos.y())

        if event.button() == Qt.MouseButton.RightButton:
            if kind == "POINT" and idx >= 0:
                updated = remove_point(self._active_points(), idx)
                self._set_active_points(updated)
                self._hover_kind, self._hover_idx = None, -1
                self.envelope_points_changed.emit(self._envelope_mode, updated)
                self.update()
                return
            self._open_context_menu(event.globalPosition().toPoint())
            return

        if event.button() == Qt.MouseButton.MiddleButton and self._zoom > 1.001:
            self._pan_drag_last_x = pos.x()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if kind == "ENVELOPE_LINE":
            sec = max(self._in_sec, min(self._effective_end_sec(), self._x_to_sec(pos.x())))
            val = self._y_to_level(pos.y())
            updated, new_idx = add_or_update_point(self._active_points(), sec, val)
            self._set_active_points(updated)
            self.envelope_points_changed.emit(self._envelope_mode, updated)
            self._dragging_kind, self._dragging_idx = "POINT", new_idx
            self.update()
            return

        self._dragging_kind, self._dragging_idx = kind, idx
        if kind == "PLAYHEAD":
            self._last_emitted_seek = -1.0
            self._apply_drag(pos.x(), pos.y())
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Add or move an envelope point at the cursor position."""
        if event.button() != Qt.MouseButton.LeftButton or self._duration_sec <= 0:
            return
        pos = event.position()
        if pos.y() < _ENV_TOP_Y - 4:
            return
        kind, idx = self._hit_test_detailed(pos.x(), pos.y())
        if kind == "POINT" and idx >= 0 and self._envelope_mode == "volume":
            self._dragging_kind, self._dragging_idx = None, -1
            self.edit_point_db(idx)  # 3.4: type the level of this point in dB
            return
        sec = max(self._in_sec, min(self._effective_end_sec(), self._x_to_sec(pos.x())))
        val = self._y_to_level(pos.y())
        updated, new_idx = add_or_update_point(self._active_points(), sec, val)
        self._set_active_points(updated)
        self.envelope_points_changed.emit(self._envelope_mode, updated)
        self._dragging_kind, self._dragging_idx = "POINT", new_idx
        self.update()

    def edit_point_db(self, idx: int, db: float | None = None) -> bool:
        """3.4: set the level of volume point *idx* in dB (asks for it when *db* is None)."""
        pts = [list(p) for p in self._volume_points]
        if not (0 <= idx < len(pts)):
            return False
        if db is None:
            from PySide6.QtWidgets import QInputDialog

            current = level_to_db(float(pts[idx][1]))
            value, ok = QInputDialog.getDouble(
                self, "Livello del punto", "Livello in dB (0 = pieno, -60 = silenzio):",
                round(max(MIN_POINT_DB, current), 1), MIN_POINT_DB, 0.0, 1)
            if not ok:
                return False
            db = value
        pts[idx][1] = round(db_to_level(float(db)), 4)
        self._volume_points = pts
        self.envelope_points_changed.emit("volume", [list(p) for p in pts])
        self.update()
        return True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Pan the view, drag an envelope element, or update the hover cursor."""
        pos = event.position()
        if self._pan_drag_last_x is not None:
            dx = pos.x() - self._pan_drag_last_x
            self._pan_drag_last_x = pos.x()
            span = self._view_span_sec()
            w = max(1, self.width())
            self.set_view_start(self._view_start_sec - (dx / w) * span)
            return
        if self._dragging_kind:
            self._apply_drag(pos.x(), pos.y())
            return
        if self._duration_sec <= 0:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        kind, idx = self._hit_test_detailed(pos.x(), pos.y())
        if kind != self._hover_kind or idx != self._hover_idx:
            self._hover_kind, self._hover_idx = kind, idx
            self.update()

        ph_s = self.playhead_seconds()
        if kind in ("IN", "OUT", "FADE_IN", "FADE_OUT", "SECTION_DIV"):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        elif kind == "POINT":
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        elif kind == "ENVELOPE_LINE":
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        elif ph_s is not None and abs(pos.x() - self._sec_to_x(ph_s)) <= 6:
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish the active drag and emit the final seek."""
        if self._pan_drag_last_x is not None:
            self._pan_drag_last_x = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return
        if self._dragging_kind == "PLAYHEAD" and self._duration_sec > 0:
            sec = round(self._x_to_sec(event.position().x()), 2)
            if abs(sec - self._last_emitted_seek) >= 0.005:
                self._last_emitted_seek = sec
                self.seek_requested.emit(sec)
        self._dragging_kind = None
        self._dragging_idx = -1
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Zoom centered at cursor timestamp, or pan horizontally with Shift/trackpad X."""
        if self._duration_sec <= 0:
            super().wheelEvent(event)
            return
        delta_x = event.angleDelta().x()
        delta_y = event.angleDelta().y()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if shift or (delta_x != 0 and abs(delta_x) >= abs(delta_y)):
            delta = delta_x if abs(delta_x) > abs(delta_y) else delta_y
            if self._zoom > 1.001 and delta != 0:
                step = self._view_span_sec() * 0.14 * (-1 if delta > 0 else 1)
                self.set_view_start(self._view_start_sec + step)
            event.accept()
            return

        if delta_y == 0:
            return
        factor = 1.28 if delta_y > 0 else (1.0 / 1.28)
        anchor = self._x_to_sec(event.position().x())
        self.set_zoom(self._zoom * factor, anchor_sec=anchor)
        event.accept()

    def leaveEvent(self, _event) -> None:  # noqa: N802
        """Clear hover feedback when the pointer leaves the waveform."""
        self._hover_kind, self._hover_idx = None, -1
        if not self._dragging_kind and self._pan_drag_last_x is None:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def _apply_drag(self, x: float, y: float) -> None:
        if self._duration_sec <= 0:
            return
        sec = self._x_to_sec(x)
        norm = min(1.0, max(0.0, sec / self._duration_sec))
        eff_end = self._effective_end_sec()

        if self._dragging_kind == "PLAYHEAD":
            snapped = round(sec, 2)
            self._playhead = norm
            self._playhead_sec = snapped
            if abs(snapped - self._last_emitted_seek) >= 0.01:
                self._last_emitted_seek = snapped
                self.seek_requested.emit(snapped)
            self.update()
            return

        if self._dragging_kind == "IN":
            max_in = (self._out_sec - 0.05) if (self._out_sec and self._out_sec > 0) else (self._duration_sec - 0.05)
            new_in = round(max(0.0, min(max_in, sec)), 2)
            self._in_sec = new_in
            self._in_point = self._in_sec / self._duration_sec
            self.in_changed.emit(self._in_sec)
            self.update()
            return

        if self._dragging_kind == "OUT":
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
            return

        if self._dragging_kind == "FADE_IN":
            max_fade = max(0.0, eff_end - self._in_sec)
            new_fi = round(max(0.0, min(max_fade, sec - self._in_sec)), 2)
            self._fade_in_sec = 0.0 if new_fi < 0.03 else new_fi
            self.fade_in_changed.emit(self._fade_in_sec)
            self.update()
            return

        if self._dragging_kind == "FADE_OUT":
            max_fade = max(0.0, eff_end - self._in_sec)
            new_fo = round(max(0.0, min(max_fade, eff_end - sec)), 2)
            self._fade_out_sec = 0.0 if new_fo < 0.03 else new_fo
            self.fade_out_changed.emit(self._fade_out_sec)
            self.update()
            return

        if self._dragging_kind == "POINT":
            pts = self._active_points()
            if 0 <= self._dragging_idx < len(pts):
                val = self._y_to_level(y)
                updated = move_point(
                    pts, self._dragging_idx, sec, val, t_min=self._in_sec, t_max=eff_end
                )
                self._set_active_points(updated)
                self.envelope_points_changed.emit(self._envelope_mode, updated)
                self.update()
            return

        if self._dragging_kind == "SECTION_DIV" and 0 <= self._dragging_idx < len(self._sections) - 1:
            updated_secs = resize_section_divider(
                self._sections, self._dragging_idx, sec, self._in_sec, eff_end
            )
            self._sections = updated_secs
            self.sections_changed.emit(updated_secs)
            self.update()

    def _open_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        curve_menu = menu.addMenu("Curva Fade IN / OUT")
        for key, label in FADE_CURVE_LABELS.items():
            act = curve_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self._fade_curve == key)
            act.triggered.connect(lambda _=False, k=key: self.fade_curve_changed.emit(k))

        if self._active_points():
            act_clear = menu.addAction(
                f"Azzera punti {'Opacità' if self._envelope_mode == 'opacity' else 'Volume'}"
            )
            act_clear.triggered.connect(
                lambda: (
                    self._set_active_points([]),
                    self.envelope_points_changed.emit(self._envelope_mode, []),
                    self.update(),
                )
            )
        menu.exec(global_pos)

    # ── Custom Painter ────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Paint peaks, envelopes, in/out markers, sections and the playhead."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        painter.fillRect(0, 0, w, h, QColor(CLR_PANEL))

        is_image = (self._media_type == MediaType.IMAGE)
        if not is_image and (self._peaks is None or len(self._peaks) == 0):
            painter.setPen(QPen(QColor("#888"), 1))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Nessuna forma d'onda caricata",
            )
            painter.end()
            return

        if self._duration_sec <= 0 and is_image:
            painter.end()
            return

        # 1. Section colored background bands (A | B | C ...)
        if len(self._sections) >= 2 and self._duration_sec > 0:
            self._paint_sections_bg(painter, w, h)

        # 2. Waveform bars (Audio/Video) OR Subtle Opacity grid (Images)
        if is_image:
            self._paint_image_opacity_backdrop(painter, w, h)
        else:
            self._paint_waveform_peaks(painter, w, h)

        in_x_raw = self._sec_to_x(self._in_sec)
        out_x_raw = self._sec_to_x(self._effective_end_sec()) if self._duration_sec > 0 else float(w - 1)
        in_x = int(round(in_x_raw))
        out_x = min(w - 1, int(round(out_x_raw))) if (self._zoom <= 1.001 and self._out_sec is None) else int(round(out_x_raw))

        # 3. Trimmed-out dim scrim (Audio/Video)
        if not is_image:
            scrim = QColor(0, 0, 0, 90)
            if in_x > 0:
                painter.fillRect(0, 0, min(w, in_x), h, scrim)
            if out_x < w - 1:
                rx = max(0, out_x + 1)
                painter.fillRect(rx, 0, w - rx, h, scrim)

        # 4. Subtle time ruler ticks when zoomed
        if self._zoom > 1.02 and self._duration_sec > 0:
            self._paint_time_ticks(painter, w, h)

        # 5. Fade IN / Fade OUT curves & draggable pallini
        if self._duration_sec > 0:
            self._paint_fades(painter, w, h)

        # 6. Horizontal Volume/Opacity envelope line + keyframe points
        if self._duration_sec > 0:
            self._paint_envelope(painter, w, h)

        # 7. Section vertical divider lines + letter badges
        if len(self._sections) >= 2 and self._duration_sec > 0:
            self._paint_section_dividers(painter, w, h)

        # 8. IN & OUT vertical markers (Audio/Video)
        if not is_image:
            self._paint_in_out_markers(painter, w, h, in_x, out_x)
            self._paint_markers(painter, w, h)  # 2.7

        # 9. Playhead cursor ("Testina di lettura") — always drawn above markers
        ph_sec = self.playhead_seconds()
        if ph_sec is not None and self._duration_sec > 0:
            px_raw = self._sec_to_x(ph_sec)
            if -6 <= px_raw <= w + 6:
                px = max(1, min(w - 2, int(round(px_raw)))) if self._zoom <= 1.001 else int(round(px_raw))
                painter.setPen(QPen(QColor("#0a0f16"), 4))
                painter.drawLine(px, 0, px, h)
                painter.setPen(QPen(QColor(_CLR_PLAYHEAD), 2))
                painter.drawLine(px, 0, px, h)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(_CLR_PLAYHEAD))
                top_cap = QPolygon([
                    QPoint(px - 6, 0),
                    QPoint(px + 6, 0),
                    QPoint(px + 6, 5),
                    QPoint(px, 11),
                    QPoint(px - 6, 5),
                ])
                painter.drawPolygon(top_cap)
                painter.drawPolygon(
                    QPolygon([QPoint(px, h - 7), QPoint(px - 5, h), QPoint(px + 5, h)])
                )
                painter.setPen(QPen(QColor(_CLR_PLAYHEAD_GLOW), 1))
                painter.drawLine(px, 1, px, 7)
            else:
                # Off-viewport chevron indicator when zoomed elsewhere
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(_CLR_PLAYHEAD))
                if px_raw < -6:
                    painter.drawPolygon(QPolygon([QPoint(2, h // 2), QPoint(9, h // 2 - 5), QPoint(9, h // 2 + 5)]))
                else:
                    painter.drawPolygon(QPolygon([QPoint(w - 2, h // 2), QPoint(w - 9, h // 2 - 5), QPoint(w - 9, h // 2 + 5)]))

        painter.end()

    def _paint_sections_bg(self, painter: QPainter, w: int, h: int) -> None:
        eff_end = self._effective_end_sec()
        is_mono = get_active_theme().is_monochrome
        for i, sec in enumerate(self._sections):
            accent, bg, _ = SECTION_PALETTE[i % len(SECTION_PALETTE)]
            x0 = int(self._sec_to_x(sec.start))
            end_s = sec.end if sec.end is not None else eff_end
            x1 = int(self._sec_to_x(end_s))
            if is_mono:
                if sec.skip:
                    c = QColor(0, 0, 0, 160)
                else:
                    c = QColor(255, 255, 255, 22 if i == self._active_section_idx else (14 if i % 2 == 0 else 6))
                painter.fillRect(x0, 0, max(1, x1 - x0), h, c)
                if i == self._active_section_idx:
                    painter.fillRect(x0, 0, max(1, x1 - x0), 3, QColor("#ffffff"))
            else:
                if sec.skip:
                    c = QColor("#2a161a")
                    c.setAlpha(150)
                else:
                    c = QColor(bg)
                    c.setAlpha(175 if i == self._active_section_idx else 115)
                painter.fillRect(x0, 0, max(1, x1 - x0), h, c)
                if i == self._active_section_idx:
                    painter.fillRect(x0, 0, max(1, x1 - x0), 3, QColor(accent))

    def _paint_section_dividers(self, painter: QPainter, w: int, h: int) -> None:
        eff_end = self._effective_end_sec()
        is_mono = get_active_theme().is_monochrome
        painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
        badge_y = h - 29 if self._zoom > 1.02 else h - 18
        for i, sec in enumerate(self._sections):
            accent, _, _ = SECTION_PALETTE[i % len(SECTION_PALETTE)]
            if is_mono:
                accent = "#ffffff" if i == self._active_section_idx else "#a1a1aa"
            x0 = int(self._sec_to_x(sec.start))
            end_s = sec.end if sec.end is not None else eff_end
            x1 = int(self._sec_to_x(end_s))
            vx0 = max(0, x0)
            vx1 = min(w, x1)
            if vx1 - vx0 >= 26:
                tag = f"{sec.label}" if sec.loops == 1 and not sec.skip else (
                    f"{sec.label} ⏭" if sec.skip else (f"{sec.label} ∞" if sec.loops == 0 else f"{sec.label} ×{sec.loops}")
                )
                painter.setPen(QColor(accent))
                painter.drawText(QRect(vx0 + 4, badge_y, vx1 - vx0 - 8, 14), Qt.AlignmentFlag.AlignCenter, tag)
            if i < len(self._sections) - 1 and sec.end is not None:
                dx = int(self._sec_to_x(sec.end))
                is_hot = (self._hover_kind == "SECTION_DIV" and self._hover_idx == i) or (
                    self._dragging_kind == "SECTION_DIV" and self._dragging_idx == i
                )
                div_clr = "#ffffff" if is_hot else (accent if not is_mono else "#525363")
                pen = QPen(QColor(div_clr), 2 if is_hot else 1.5, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(dx, 18, dx, h)

    def _paint_image_opacity_backdrop(self, painter: QPainter, w: int, h: int) -> None:
        bot = int(max(_ENV_TOP_Y + 12.0, h - _ENV_BOT_PAD))
        mid = int((_ENV_TOP_Y + bot) / 2.0)
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.PenStyle.DotLine))
        for gy in (int(_ENV_TOP_Y), mid, bot):
            painter.drawLine(0, gy, w, gy)
        painter.setFont(QFont("sans-serif", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(6, int(_ENV_TOP_Y) + 11, "100%")
        painter.drawText(6, mid - 2, "50%")
        painter.drawText(6, bot - 2, "0%")

    def _paint_waveform_peaks(self, painter: QPainter, w: int, h: int) -> None:
        assert self._peaks is not None
        n = len(self._peaks)
        dur = self._duration_sec if self._duration_sec > 0 else 1.0
        span = self._view_span_sec() if self._duration_sec > 0 else dur
        start_frac = max(0.0, min(1.0, self._view_start_sec / dur))
        end_frac = max(start_frac, min(1.0, (self._view_start_sec + span) / dur))

        i0 = max(0, int(math.floor(start_frac * n)))
        i1 = min(n, max(i0 + 1, int(math.ceil(end_frac * n))))
        visible_count = max(1, i1 - i0)

        # Render smoothly into pixel columns (either 1 bar per sample or max-pool per pixel)
        mid_y = h / 2.0
        dimmed_for_opacity = (self._envelope_mode == "opacity")
        is_mono = get_active_theme().is_monochrome
        if is_mono:
            active_clr = QColor("#ffffff") if not dimmed_for_opacity else QColor("#71717a")
            inactive_clr = QColor("#27272a")
        else:
            active_clr = QColor("#1f6b4a" if dimmed_for_opacity else CLR_LIVE)
            inactive_clr = QColor("#363b42" if dimmed_for_opacity else "#444444")

        painter.setPen(Qt.PenStyle.NoPen)
        if visible_count <= w:
            bar_w = w / visible_count
            for k in range(visible_count):
                idx = i0 + k
                x = k * bar_w
                bar_h = float(self._peaks[idx]) * mid_y * 0.88
                frac = idx / n
                painter.setBrush(active_clr if self._in_point <= frac <= self._out_point else inactive_clr)
                painter.drawRect(
                    int(x),
                    int(mid_y - bar_h),
                    max(1, int(bar_w) - (1 if bar_w >= 2.0 else 0)),
                    max(1, int(bar_h * 2)),
                )
        else:
            step = visible_count / w
            for px in range(w):
                b0 = i0 + int(px * step)
                b1 = min(i1, max(b0 + 1, i0 + int((px + 1) * step)))
                peak = float(self._peaks[b0:b1].max())
                bar_h = peak * mid_y * 0.88
                frac = ((b0 + b1) * 0.5) / n
                painter.setBrush(active_clr if self._in_point <= frac <= self._out_point else inactive_clr)
                painter.drawRect(px, int(mid_y - bar_h), 1, max(1, int(bar_h * 2)))

    def _paint_time_ticks(self, painter: QPainter, w: int, h: int) -> None:
        span = self._view_span_sec()
        if span <= 0:
            return
        # Choose a human step so ticks land every ~75-110px
        raw_step = span / max(2.0, w / 90.0)
        candidates = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0)
        tick_step = next((c for c in candidates if c >= raw_step), 60.0)
        t_first = math.ceil(self._view_start_sec / tick_step) * tick_step
        t_end = self._view_start_sec + span

        painter.setFont(QFont("monospace", 7))
        t = t_first
        while t <= t_end + 1e-6:
            tx = int(round(self._sec_to_x(t)))
            if 12 <= tx <= w - 38:
                painter.setPen(QPen(QColor("#243244"), 1))
                painter.drawLine(tx, _ENV_TOP_Y, tx, h)
                painter.setPen(QColor("#64748b"))
                lbl = f"{t:.2f}s" if tick_step < 1.0 else _format_playhead_time(t)[:-3]
                painter.drawText(tx + 2, h - 3, lbl)
            t += tick_step

    def _paint_fades(self, painter: QPainter, w: int, h: int) -> None:
        eff_end = self._effective_end_sec()
        in_x = self._sec_to_x(self._in_sec)
        out_x = self._sec_to_x(eff_end)
        bot_y = max(_ENV_TOP_Y + 12.0, h - _ENV_BOT_PAD)

        # Fade IN shaded ramp
        if self._fade_in_sec > 0.02 and eff_end > self._in_sec:
            fi_end_s = min(eff_end, self._in_sec + self._fade_in_sec)
            fi_end_x = self._sec_to_x(fi_end_s)
            path = QPainterPath()
            path.moveTo(in_x, bot_y)
            steps = 20
            pts_env = self._active_points()
            base_lv = self._active_base_level()
            for k in range(steps + 1):
                p = k / steps
                sx = in_x + p * max(1.0, fi_end_x - in_x)
                s_t = self._in_sec + p * (fi_end_s - self._in_sec)
                target_lv = evaluate_points_envelope(s_t, pts_env, base_lv)
                gain = apply_fade_curve(p, self._fade_curve, fade_out=False)
                sy = self._level_to_y(target_lv * gain)
                path.lineTo(sx, sy)
            path.lineTo(fi_end_x, _ENV_TOP_Y)
            path.lineTo(in_x, _ENV_TOP_Y)
            path.closeSubpath()
            painter.fillPath(path, QColor(0, 230, 118, 42))

            curve_line = QPainterPath()
            for k in range(steps + 1):
                p = k / steps
                sx = in_x + p * max(1.0, fi_end_x - in_x)
                s_t = self._in_sec + p * (fi_end_s - self._in_sec)
                target_lv = evaluate_points_envelope(s_t, pts_env, base_lv)
                gain = apply_fade_curve(p, self._fade_curve, fade_out=False)
                sy = self._level_to_y(target_lv * gain)
                if k == 0:
                    curve_line.moveTo(sx, sy)
                else:
                    curve_line.lineTo(sx, sy)
            painter.strokePath(curve_line, QPen(QColor("#4ade80"), 1.8))

        # Fade OUT shaded ramp
        if self._show_fade_out and self._fade_out_sec > 0.02 and eff_end > self._in_sec:
            fo_start_s = max(self._in_sec, eff_end - self._fade_out_sec)
            fo_start_x = self._sec_to_x(fo_start_s)
            path = QPainterPath()
            path.moveTo(fo_start_x, _ENV_TOP_Y)
            steps = 20
            pts_env = self._active_points()
            base_lv = self._active_base_level()
            curve_line = QPainterPath()
            for k in range(steps + 1):
                p = k / steps
                sx = fo_start_x + p * max(1.0, out_x - fo_start_x)
                s_t = fo_start_s + p * (eff_end - fo_start_s)
                target_lv = evaluate_points_envelope(s_t, pts_env, base_lv)
                gain = apply_fade_curve(p, self._fade_curve, fade_out=True)
                sy = self._level_to_y(target_lv * gain)
                if k == 0:
                    path.moveTo(fo_start_x, _ENV_TOP_Y)
                    path.lineTo(sx, sy)
                    curve_line.moveTo(sx, sy)
                else:
                    path.lineTo(sx, sy)
                    curve_line.lineTo(sx, sy)
            path.lineTo(out_x, _ENV_TOP_Y)
            path.closeSubpath()
            painter.fillPath(path, QColor(255, 82, 82, 42))
            painter.strokePath(curve_line, QPen(QColor("#f87171"), 1.8))

        # Draggable Fade Pallini
        fi_pt, fo_pt = self._fade_handle_positions()
        hot_fi = (self._hover_kind == "FADE_IN") or (self._dragging_kind == "FADE_IN")
        painter.setPen(QPen(QColor("#0a0f16"), 1.5))
        painter.setBrush(QColor("#86efac" if hot_fi else "#00e676"))
        painter.drawEllipse(fi_pt, 5.5 if hot_fi else 4.5, 5.5 if hot_fi else 4.5)

        if self._show_fade_out:
            hot_fo = (self._hover_kind == "FADE_OUT") or (self._dragging_kind == "FADE_OUT")
            painter.setPen(QPen(QColor("#0a0f16"), 1.5))
            painter.setBrush(QColor("#fca5a5" if hot_fo else "#ff5252"))
            painter.drawEllipse(fo_pt, 5.5 if hot_fo else 4.5, 5.5 if hot_fo else 4.5)

    def _paint_envelope(self, painter: QPainter, w: int, h: int) -> None:
        pts = self._active_points()
        base_lv = self._active_base_level()
        eff_end = self._effective_end_sec()
        if eff_end <= self._in_sec:
            return

        in_x = self._sec_to_x(self._in_sec)
        out_x = self._sec_to_x(eff_end)
        env_clr = QColor(_CLR_ENV_OP if self._envelope_mode == "opacity" else _CLR_ENV_VOL)

        path = QPainterPath()
        if not pts:
            y_base = self._level_to_y(base_lv)
            path.moveTo(in_x, y_base)
            path.lineTo(out_x, y_base)
        else:
            sorted_pts = sorted(pts, key=lambda p: p[0])
            # Left hold from IN to first keyframe
            y0 = self._level_to_y(sorted_pts[0][1])
            path.moveTo(in_x, y0)
            for pt_t, pt_v in sorted_pts:
                clamped_t = max(self._in_sec, min(eff_end, pt_t))
                path.lineTo(self._sec_to_x(clamped_t), self._level_to_y(pt_v))
            path.lineTo(out_x, self._level_to_y(sorted_pts[-1][1]))

        line_width = 2.4 if self._hover_kind == "ENVELOPE_LINE" else 1.8
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.strokePath(path, QPen(env_clr, line_width))

        # Paint clickable keyframe nodes
        for idx, (pt_t, pt_v) in enumerate(pts):
            px = self._sec_to_x(max(self._in_sec, min(eff_end, pt_t)))
            py = self._level_to_y(pt_v)
            is_hot = (
                (self._hover_kind == "POINT" and self._hover_idx == idx)
                or (self._dragging_kind == "POINT" and self._dragging_idx == idx)
            )
            r = 5.5 if is_hot else 4.2
            painter.setPen(QPen(QColor("#0a0f16"), 1.5))
            painter.setBrush(QColor("#ffffff") if is_hot else env_clr)
            painter.drawEllipse(QPointF(px, py), r, r)
            if is_hot:
                if self._envelope_mode == "opacity":
                    tag = f"{int(round(pt_v * 100))}% @ {pt_t:.2f}s"
                else:  # 3.4: volume points in dB (double-click types a value)
                    tag = f"{format_level_db(pt_v)} @ {pt_t:.2f}s"
                tx = max(4, min(w - 92, int(px) + 8))
                ty = max(14, int(py) - 6)
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
                painter.drawText(tx, ty, tag)

    def _paint_in_out_markers(self, painter: QPainter, w: int, h: int, in_x: int, out_x: int) -> None:
        if -16 <= in_x <= w + 16:
            painter.setPen(QPen(QColor(CLR_LIVE), 2))
            painter.drawLine(in_x, 0, in_x, h)
            painter.setBrush(QColor(CLR_LIVE))
            painter.drawPolygon([QPoint(in_x, 0), QPoint(in_x - 6, 8), QPoint(in_x + 6, 8)])
            painter.drawPolygon([QPoint(in_x, h), QPoint(in_x - 6, h - 8), QPoint(in_x + 6, h - 8)])

            in_txt = f"IN: {self._in_sec:.2f}s" if self._in_sec > 0 else "IN: 0.00s"
            in_pill_w = len(in_txt) * 7 + 8
            in_pill_x = max(0, in_x - in_pill_w - 2) if in_x + in_pill_w + 4 > w else in_x + 2
            painter.fillRect(in_pill_x, 2, in_pill_w, 16, QColor("#003314"))
            painter.setPen(QColor(CLR_LIVE))
            painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
            painter.drawText(in_pill_x + 4, 14, in_txt)

        if -16 <= out_x <= w + 16:
            painter.setPen(QPen(QColor("#ff5252"), 2))
            painter.drawLine(out_x, 0, out_x, h)
            painter.setBrush(QColor("#ff5252"))
            painter.drawPolygon([QPoint(out_x, 0), QPoint(out_x - 6, 8), QPoint(out_x + 6, 8)])
            painter.drawPolygon([QPoint(out_x, h), QPoint(out_x - 6, h - 8), QPoint(out_x + 6, h - 8)])

            out_txt = (
                f"OUT: {self._out_sec:.2f}s"
                if (self._out_sec is not None and self._out_sec > 0)
                else "OUT: Fine"
            )
            out_pill_w = len(out_txt) * 7 + 8
            out_pill_x = max(0, out_x - out_pill_w - 2) if out_x > w - 95 else out_x + 2
            painter.fillRect(out_pill_x, 2, out_pill_w, 16, QColor("#3a0d0d"))
            painter.setPen(QColor("#ff5252"))
            painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
            painter.drawText(out_pill_x + 5, 14, out_txt)


class WaveformPanel(QGroupBox):
    """Unified Timeline panel: Playhead, Snap IN/OUT, Volume/Opacity Envelopes, and Sections A/B/C."""

    def set_markers(self, items: list[tuple[float, str]]) -> None:
        """2.7: the selected cue's markers on the waveform."""
        self.waveform.set_markers(items)

    in_changed = Signal(float)
    out_changed = Signal(float)
    seek_requested = Signal(float)
    snap_in_requested = Signal()
    snap_out_requested = Signal()
    marker_add_requested = Signal()  # 2.7: a marker at the playhead
    reset_in_out_requested = Signal()

    fade_in_changed = Signal(float)
    fade_out_changed = Signal(float)
    fade_curve_changed = Signal(str)
    envelope_mode_changed = Signal(str)
    envelope_points_changed = Signal(str, list)
    reset_envelope_points_requested = Signal(str)
    image_horizon_changed = Signal(float)

    split_section_requested = Signal()
    break_loop_requested = Signal()
    reset_sections_requested = Signal()
    section_jump_requested = Signal(int)
    section_mode_changed = Signal(int, int, bool)
    section_remove_requested = Signal(int)
    sections_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the waveform panel: timecode strip, canvas and zoom controls."""
        super().__init__("Forma d'Onda e Automazioni (Timeline)", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(3)

        # ── Strip 1: Playhead & IN/OUT Snap + Reset ───────────────────
        strip_top = QHBoxLayout()
        strip_top.setContentsMargins(0, 0, 0, 0)
        strip_top.setSpacing(5)

        self.btn_snap_in = QPushButton("↦ IN Testina")
        self.btn_snap_in.setFixedHeight(22)
        self.btn_snap_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_snap_in.setEnabled(False)
        self.btn_snap_in.setToolTip(
            "Imposta il punto IN esattamente sulla testina di lettura (Scorciatoia: I)"
        )
        self.btn_snap_in.setStyleSheet(
            "QPushButton { background-color: #09301d; color: #4ade80; border: 1px solid #00c853; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:hover { background-color: #0e4a2d; color: #ffffff; border-color: #00e676; } "
            "QPushButton:pressed { background-color: #00e676; color: #000000; } "
            "QPushButton:disabled { background-color: #161d26; color: #4b5563; border-color: #24303f; }"
        )

        self.btn_snap_out = QPushButton("OUT Testina ↤")
        self.btn_snap_out.setFixedHeight(22)
        self.btn_snap_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_snap_out.setEnabled(False)
        self.btn_snap_out.setToolTip(
            "Imposta il punto OUT esattamente sulla testina di lettura (Scorciatoia: O)"
        )
        self.btn_snap_out.setStyleSheet(
            "QPushButton { background-color: #361015; color: #fca5a5; border: 1px solid #ef4444; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:hover { background-color: #52171f; color: #ffffff; border-color: #ff5252; } "
            "QPushButton:pressed { background-color: #ff5252; color: #000000; } "
            "QPushButton:disabled { background-color: #161d26; color: #4b5563; border-color: #24303f; }"
        )

        self.lbl_playhead = QLabel("Testina: --:--.--")
        self.lbl_playhead.setFixedHeight(22)
        self.lbl_playhead.setStyleSheet(
            f"background-color: #111824; color: {CLR_ACCENT}; border: 1px solid #243447; "
            "border-radius: 3px; font-family: monospace; font-size: 10px; "
            "font-weight: bold; padding: 0 7px;"
        )

        self.btn_reset_io = QPushButton("⟲ Reset IN/OUT")
        self.btn_reset_io.setFixedHeight(22)
        self.btn_reset_io.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_io.setEnabled(False)
        self.btn_reset_io.setToolTip("Ripristina IN a 0.00s e OUT a Fine file")
        self.btn_reset_io.setStyleSheet(
            "QPushButton { background-color: #16202e; color: #cbd5e1; border: 1px solid #334155; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:hover { background-color: #1f2e42; color: #ffffff; border-color: #38bdf8; } "
            "QPushButton:pressed { background-color: #38bdf8; color: #000000; } "
            "QPushButton:disabled { background-color: #161d26; color: #4b5563; border-color: #24303f; }"
        )

        strip_top.addWidget(self.btn_snap_in)
        strip_top.addWidget(self.btn_snap_out)
        self.btn_marker = QPushButton("◆ Segno")
        self.btn_marker.setFixedHeight(22)
        self.btn_marker.setEnabled(False)
        self.btn_marker.setToolTip("Mette un segno sulla testina (Ctrl+K: anche sulla cue in onda, per esempio "
                                   "battendo a tempo in prova). Una cue può partire «al segno».")
        self.btn_marker.setStyleSheet(
            "QPushButton { background-color: #2b1d05; color: #fbbf24; border: 1px solid #f59e0b; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:disabled { background-color: #161d26; color: #4b5563; border-color: #24303f; }")
        self.btn_marker.clicked.connect(self.marker_add_requested)
        strip_top.addWidget(self.btn_marker)
        strip_top.addWidget(self.lbl_playhead)
        strip_top.addWidget(self.btn_reset_io)
        strip_top.addStretch(1)

        # Envelope mode pills (Volume / Opacity) for Video cues
        self.btn_mode_vol = QPushButton("🔊 Volume")
        self.btn_mode_vol.setCheckable(True)
        self.btn_mode_vol.setChecked(True)
        self.btn_mode_vol.setFixedHeight(22)
        self.btn_mode_vol.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_vol.setToolTip("Modifica la curva Volume sulla forma d'onda")

        self.btn_mode_op = QPushButton("👁 Opacità")
        self.btn_mode_op.setCheckable(True)
        self.btn_mode_op.setFixedHeight(22)
        self.btn_mode_op.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_op.setToolTip("Modifica l'opacità lungo il file video sulla stessa timeline")

        self._style_mode_pills()
        strip_top.addWidget(self.btn_mode_vol)
        strip_top.addWidget(self.btn_mode_op)

        # Horizon selector for infinite-hold Image cues
        self.combo_img_horizon = QComboBox()
        self.combo_img_horizon.setFixedHeight(22)
        self.combo_img_horizon.setToolTip("Finestra temporale visiva per immagini a durata infinita")
        for secs in (5.0, 10.0, 20.0, 30.0, 60.0):
            self.combo_img_horizon.addItem(f"Vista {int(secs)}s", secs)
        self.combo_img_horizon.setCurrentIndex(1)
        self.combo_img_horizon.setVisible(False)
        strip_top.addWidget(self.combo_img_horizon)
        layout.addLayout(strip_top)

        # ── Strip 2: Fade Curve, Keyframe Reset, and Virtual Sections ─
        strip_env = QHBoxLayout()
        strip_env.setContentsMargins(0, 0, 0, 0)
        strip_env.setSpacing(5)

        self.combo_fade_curve = QComboBox()
        self.combo_fade_curve.setFixedHeight(21)
        self.combo_fade_curve.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_fade_curve.setToolTip("Forma della rampa Fade IN / OUT (Logaritmica consigliata per audio)")
        for key, label in FADE_CURVE_LABELS.items():
            self.combo_fade_curve.addItem(f"Fade: {label.split()[0]}", key)
        self.combo_fade_curve.setEnabled(False)

        self.btn_reset_points = QPushButton("⟲ Reset Punti")
        self.btn_reset_points.setFixedHeight(21)
        self.btn_reset_points.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_points.setEnabled(False)
        self.btn_reset_points.setToolTip("Elimina tutti i punti sulla linea Volume/Opacità")
        self.btn_reset_points.setStyleSheet(self.btn_reset_io.styleSheet())

        self.btn_split_section = QPushButton("✂ Dividi")
        self.btn_split_section.setFixedHeight(21)
        self.btn_split_section.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_split_section.setEnabled(False)
        self.btn_split_section.setToolTip("Dividi virtualmente il file alla testina in sezioni A, B, C...")
        self.btn_split_section.setStyleSheet(
            "QPushButton { background-color: #16283b; color: #7dd3fc; border: 1px solid #0284c7; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:hover { background-color: #1d3954; color: #ffffff; border-color: #38bdf8; } "
            "QPushButton:disabled { background-color: #161d26; color: #4b5563; border-color: #24303f; }"
        )

        self.btn_break_loop = QPushButton("⏭ Esci Loop")
        self.btn_break_loop.setFixedHeight(21)
        self.btn_break_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_break_loop.setVisible(False)
        self.btn_break_loop.setToolTip("Salta immediatamente fuori dalla sezione ripetuta verso la successiva")
        self.btn_break_loop.setStyleSheet(
            "QPushButton { background-color: #3d2807; color: #fcd34d; border: 1px solid #f59e0b; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:hover { background-color: #573a0b; color: #ffffff; }"
        )

        self.btn_reset_sections = QPushButton("↺ Reset Sez.")
        self.btn_reset_sections.setFixedHeight(21)
        self.btn_reset_sections.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_sections.setEnabled(False)
        self.btn_reset_sections.setToolTip("Rimuovi tutte le sezioni virtuali e torna al file intero")
        self.btn_reset_sections.setStyleSheet(self.btn_reset_io.styleSheet())

        strip_env.addWidget(self.combo_fade_curve)
        strip_env.addWidget(self.btn_reset_points)
        strip_env.addWidget(self.btn_split_section)
        strip_env.addWidget(self.btn_break_loop)
        strip_env.addWidget(self.btn_reset_sections)
        strip_env.addStretch(1)

        zoom_btn_ss = (
            "QPushButton { background: #141923; border: 1px solid #2b384c; border-radius: 4px; padding: 0px; }"
            "QPushButton:hover:enabled { background: #1e293b; border-color: #38bdf8; }"
            "QPushButton:pressed:enabled { background: #0d121a; }"
            "QPushButton:disabled { background: #10141c; border-color: #1c222e; }"
        )
        self.btn_zoom_out = _ZoomStepButton(is_plus=False)
        self.btn_zoom_out.setToolTip("Zoom indietro forma d'onda (rotella giù)")
        self.btn_zoom_out.setStyleSheet(zoom_btn_ss)

        self.btn_zoom_label = QPushButton("1.0×")
        self.btn_zoom_label.setFixedHeight(22)
        self.btn_zoom_label.setMinimumWidth(42)
        self.btn_zoom_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_label.setToolTip("Zoom forma d'onda — clicca per ripristinare 1.0× (o doppio clic / Ctrl+0)")
        self.btn_zoom_label.setStyleSheet(
            "QPushButton { background: #0f121a; color: #38bdf8; border: 1px solid #2b384c; "
            "border-radius: 4px; font-size: 10px; font-weight: 700; padding: 0px 5px; }"
            "QPushButton:hover:enabled { background: #1e293b; border-color: #38bdf8; }"
            "QPushButton:disabled { color: #3f4756; border-color: #1c222e; }"
        )

        self.btn_zoom_in = _ZoomStepButton(is_plus=True)
        self.btn_zoom_in.setToolTip("Zoom avanti forma d'onda (rotella su)")
        self.btn_zoom_in.setStyleSheet(zoom_btn_ss)

        strip_env.addWidget(self.btn_zoom_out)
        strip_env.addWidget(self.btn_zoom_label)
        strip_env.addWidget(self.btn_zoom_in)
        layout.addLayout(strip_env)

        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform, stretch=1)

        self.zoom_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.zoom_scroll.setFixedHeight(10)
        self.zoom_scroll.setVisible(False)
        self.zoom_scroll.setStyleSheet(
            "QScrollBar:horizontal { background: #0d0f15; height: 10px; border: none; border-radius: 5px; }"
            "QScrollBar::handle:horizontal { background: #334155; min-width: 24px; border-radius: 5px; }"
            "QScrollBar::handle:horizontal:hover { background: #38bdf8; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
        )
        layout.addWidget(self.zoom_scroll, stretch=0)

        self.section_bar = SectionControlBar()
        layout.addWidget(self.section_bar, stretch=0)

        # Forward waveform canvas signals
        self.waveform.in_changed.connect(self.in_changed)
        self.waveform.out_changed.connect(self.out_changed)
        self.waveform.seek_requested.connect(self.seek_requested)
        self.waveform.fade_in_changed.connect(self.fade_in_changed)
        self.waveform.fade_out_changed.connect(self.fade_out_changed)
        self.waveform.fade_curve_changed.connect(self.fade_curve_changed)
        self.waveform.envelope_points_changed.connect(self.envelope_points_changed)
        self.waveform.sections_changed.connect(self.sections_changed)
        self.waveform.view_changed.connect(self._on_waveform_view_changed)
        self.zoom_scroll.valueChanged.connect(self._on_zoom_scroll_changed)
        self.btn_zoom_out.clicked.connect(
            lambda: self.waveform.set_zoom(self.waveform.zoom_factor() / 1.6)
        )
        self.btn_zoom_in.clicked.connect(
            lambda: self.waveform.set_zoom(self.waveform.zoom_factor() * 1.6)
        )
        self.btn_zoom_label.clicked.connect(self.reset_zoom)

        # Top toolbar signals
        self.btn_snap_in.clicked.connect(self.snap_in_requested)
        self.btn_snap_out.clicked.connect(self.snap_out_requested)
        self.btn_reset_io.clicked.connect(self.reset_in_out_requested)
        self.btn_mode_vol.clicked.connect(lambda: self._on_mode_pill_clicked("volume"))
        self.btn_mode_op.clicked.connect(lambda: self._on_mode_pill_clicked("opacity"))
        self.combo_img_horizon.currentIndexChanged.connect(self._on_img_horizon_changed)

        self.combo_fade_curve.currentIndexChanged.connect(self._on_curve_combo_changed)
        self.btn_reset_points.clicked.connect(
            lambda: self.reset_envelope_points_requested.emit(self.waveform._envelope_mode)
        )
        self.btn_split_section.clicked.connect(self.split_section_requested)
        self.btn_break_loop.clicked.connect(self.break_loop_requested)
        self.btn_reset_sections.clicked.connect(self.reset_sections_requested)

        self.section_bar.section_jump_requested.connect(self.section_jump_requested)
        self.section_bar.section_mode_changed.connect(self.section_mode_changed)
        self.section_bar.section_remove_requested.connect(self.section_remove_requested)

    def _style_mode_pills(self) -> None:
        base = (
            "QPushButton { background-color: #141c27; color: #94a3b8; border: 1px solid #2b3b52; "
            "border-radius: 3px; font-size: 10px; font-weight: bold; padding: 1px 7px; } "
            "QPushButton:disabled { background-color: #161d26; color: #475569; border-color: #24303f; }"
        )
        self.btn_mode_vol.setStyleSheet(
            base + "QPushButton:checked { background-color: #0b2d42; color: #38bdf8; border-color: #38bdf8; }"
        )
        self.btn_mode_op.setStyleSheet(
            base + "QPushButton:checked { background-color: #2b1642; color: #c084fc; border-color: #c084fc; }"
        )

    def _on_mode_pill_clicked(self, mode: str) -> None:
        self.btn_mode_vol.setChecked(mode == "volume")
        self.btn_mode_op.setChecked(mode == "opacity")
        self.waveform.set_envelope_mode(mode)
        self.envelope_mode_changed.emit(mode)

    def _on_curve_combo_changed(self, idx: int) -> None:
        key = self.combo_fade_curve.itemData(idx)
        if key:
            self.fade_curve_changed.emit(str(key))

    def _on_img_horizon_changed(self, idx: int) -> None:
        val = self.combo_img_horizon.itemData(idx)
        if val is not None:
            self.image_horizon_changed.emit(float(val))

    def sync_controls_for_cue(
        self,
        *,
        media_type: MediaType | None,
        fade_curve: str = "log",
        has_points: bool = False,
        has_sections: bool = False,
        can_split: bool = False,
        has_repeating_section: bool = False,
        image_horizon_sec: float = 10.0,
        hold_time: float = 0.0,
    ) -> None:
        """Synchronize toolbar mode pills, curve combo, and section action states cleanly."""
        is_audio = (media_type == MediaType.AUDIO)
        is_video = (media_type == MediaType.VIDEO)
        is_image = (media_type == MediaType.IMAGE)

        self.btn_mode_vol.setVisible(not is_image)
        self.btn_mode_op.setVisible(is_video or is_image)
        self.btn_mode_vol.setEnabled(is_audio or is_video)
        self.btn_mode_op.setEnabled(is_video or is_image)
        if is_image:
            self.btn_mode_op.setChecked(True)
            self.btn_mode_vol.setChecked(False)
            self.waveform.set_envelope_mode("opacity")
        elif is_audio:
            self.btn_mode_vol.setChecked(True)
            self.btn_mode_op.setChecked(False)
            self.waveform.set_envelope_mode("volume")

        self.combo_img_horizon.setVisible(is_image and hold_time <= 0.0)
        if is_image and hold_time <= 0.0:
            self.combo_img_horizon.blockSignals(True)
            best = 1
            for i in range(self.combo_img_horizon.count()):
                if abs(float(self.combo_img_horizon.itemData(i)) - image_horizon_sec) < 0.6:
                    best = i
                    break
            self.combo_img_horizon.setCurrentIndex(best)
            self.combo_img_horizon.blockSignals(False)

        self.combo_fade_curve.setEnabled(media_type is not None)
        self.combo_fade_curve.blockSignals(True)
        c_idx = 0
        for i in range(self.combo_fade_curve.count()):
            if self.combo_fade_curve.itemData(i) == fade_curve:
                c_idx = i
                break
        self.combo_fade_curve.setCurrentIndex(c_idx)
        self.combo_fade_curve.blockSignals(False)

        self.btn_reset_points.setEnabled(media_type is not None and has_points)
        self.btn_split_section.setEnabled((is_audio or is_video) and can_split)
        self.btn_reset_sections.setEnabled((is_audio or is_video) and has_sections)
        self.btn_break_loop.setVisible((is_audio or is_video) and has_sections and has_repeating_section)
        self._has_zoomable_cue = media_type is not None
        self._refresh_zoom_controls()

    def reset_zoom(self) -> None:
        """Reset the waveform zoom to 1x and refresh the zoom controls."""
        self.waveform.reset_zoom()

    def _refresh_zoom_controls(self) -> None:
        zoom = self.waveform.zoom_factor()
        dur = self.waveform.duration_seconds()
        can_zoom = getattr(self, "_has_zoomable_cue", False) and dur > 0.0
        self.btn_zoom_label.setText(f"{zoom:.1f}×" if zoom < 10.0 else f"{zoom:.0f}×")
        self.btn_zoom_out.setEnabled(can_zoom and zoom > 1.001)
        self.btn_zoom_label.setEnabled(can_zoom and zoom > 1.001)
        self.btn_zoom_in.setEnabled(can_zoom and zoom < 31.99)

    def _on_waveform_view_changed(self, zoom: float, view_start: float, view_span: float) -> None:
        self._refresh_zoom_controls()
        dur = self.waveform.duration_seconds()
        max_start = max(0.0, dur - view_span)
        zoomed = zoom > 1.001 and max_start > 0.001
        self.zoom_scroll.setVisible(zoomed)
        self.zoom_scroll.blockSignals(True)
        try:
            if zoomed:
                max_val = max(1, int(round(max_start * 100.0)))
                page_step = max(1, int(round(view_span * 100.0)))
                self.zoom_scroll.setRange(0, max_val)
                self.zoom_scroll.setPageStep(page_step)
                self.zoom_scroll.setSingleStep(max(1, page_step // 8))
                self.zoom_scroll.setValue(int(round(view_start * 100.0)))
            else:
                self.zoom_scroll.setRange(0, 0)
                self.zoom_scroll.setValue(0)
        finally:
            self.zoom_scroll.blockSignals(False)
        self.section_bar.set_view_window(view_start, view_span)

    def _on_zoom_scroll_changed(self, value: int) -> None:
        self.waveform.set_view_start(value / 100.0)

    def set_playhead_display(
        self,
        sec: float | None,
        duration_sec: float = 0.0,
        source_tag: str = "PRE-VIZ",
        snap_enabled: bool | None = None,
        reset_enabled: bool | None = None,
    ) -> None:
        """Update the playhead timecode label and the snap/reset controls."""
        has_valid = sec is not None and duration_sec > 0
        if snap_enabled is None:
            snap_enabled = has_valid
        if reset_enabled is None:
            reset_enabled = bool(snap_enabled and has_valid)

        self.btn_snap_in.setEnabled(bool(snap_enabled and has_valid))
        self.btn_snap_out.setEnabled(bool(snap_enabled and has_valid))
        self.btn_marker.setEnabled(bool(snap_enabled and has_valid))
        self.btn_reset_io.setEnabled(bool(reset_enabled))

        if has_valid and sec is not None:
            tc = _format_playhead_time(sec)
            if source_tag.startswith("LIVE"):
                self.lbl_playhead.setText(f"{source_tag}  {tc}")
                self.lbl_playhead.setStyleSheet(
                    "background-color: #0b2619; color: #00e676; border: 1px solid #00c853; "
                    "border-radius: 3px; font-family: monospace; font-size: 10px; "
                    "font-weight: bold; padding: 0 7px;"
                )
            else:
                self.lbl_playhead.setText(f"Testina: {tc}")
                self.lbl_playhead.setStyleSheet(
                    f"background-color: #211a08; color: {_CLR_PLAYHEAD}; border: 1px solid #92670d; "
                    "border-radius: 3px; font-family: monospace; font-size: 10px; "
                    "font-weight: bold; padding: 0 7px;"
                )
        else:
            self.lbl_playhead.setText("Testina: --:--.--")
            self.lbl_playhead.setStyleSheet(
                "background-color: #111824; color: #64748b; border: 1px solid #243447; "
                "border-radius: 3px; font-family: monospace; font-size: 10px; "
                "font-weight: bold; padding: 0 7px;"
            )
