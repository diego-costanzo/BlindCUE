"""Bottom Live Output Status panel (Layers 1-3 progress bars, Play/Pause, Cut, Blackout, Layer 0 Tappo)."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from engine.live_state import WARN_BEFORE_END_SEC
from models.cue import Cue, MediaType
from ui.hold_button import HoldProgressButton
from ui.theme import CLR_LIVE, CLR_PREVIZ, get_active_theme


def _fmt_mmss(sec: float) -> str:
    s = max(0, int(round(sec))) if sec < 0.0 else max(0, int(sec))
    mins, rem = divmod(s, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{rem:02d}"
    return f"{mins:02d}:{rem:02d}"


class _LiveLayerBar(QWidget):
    """Progressive status bar showing Left elapsed, Center cue title, Right countdown, and fill.

    Supports interactive live playhead seeking, mouse drag scrubbing, wheel nudging,
    and right-click rehearsal jump actions.
    """

    seek_requested = Signal(int, float)       # (layer_idx, target_sec)
    play_pause_requested = Signal(int)        # (layer_idx)

    def __init__(
        self, layer_idx: int, parent: QWidget | None = None, label: str | None = None
    ) -> None:
        """Create the interactive progress bar for one live layer."""
        super().__init__(parent)
        self._layer_idx = layer_idx
        self._label = label or f"Layer {layer_idx}"
        self._is_live: bool = False
        self._cue_id: int = -1
        self._media_type: MediaType | None = None
        self._title: str = ""
        self._q_label: str = ""
        self._pos_sec: float = 0.0
        self._start_sec: float = 0.0
        self._end_sec: float = 0.0
        self._is_paused: bool = False
        self._is_looping_inf: bool = False
        self._phase: str = ""  # "" (normal), "PRE" (Pre-Delay), "POST" (Post-Delay)

        # Interactive scrub state
        self._locked: bool = False
        self._hover_active: bool = False
        self._hover_x: float = -1.0
        self._hover_sec: float = 0.0
        self._is_dragging: bool = False
        self._drag_sec: float = 0.0
        self._last_drag_seek_time: float = 0.0

        self.setMouseTracking(True)
        self.setMinimumWidth(0)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def _is_seekable(self) -> bool:
        if getattr(self, "_locked", False):
            return False
        return (
            self._is_live
            and self._media_type in (MediaType.AUDIO, MediaType.VIDEO)
            and self._end_sec > self._start_sec
            and self._phase not in ("PRE", "POST")
        )

    def set_locked(self, locked: bool) -> None:
        """Disable interactive scrub on this layer bar while the console is locked."""
        self._locked = bool(locked)
        if self._locked:
            self._is_dragging = False
            self._hover_active = False
            self.unsetCursor()
        self.update()

    def _x_to_sec(self, x: float) -> float:
        w = max(1.0, float(self.width()))
        ratio = max(0.0, min(1.0, float(x) / w))
        span = max(0.01, self._end_sec - self._start_sec)
        return self._start_sec + ratio * span

    def enterEvent(self, event) -> None:  # noqa: N802
        """Show a pointing-hand cursor while the bar accepts seeking."""
        if self._is_seekable():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Clear hover/drag feedback when the pointer leaves the bar."""
        self._hover_active = False
        self._hover_x = -1.0
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Track the hover position and emit throttled seek requests while scrubbing."""
        if not self._is_seekable():
            super().mouseMoveEvent(event)
            return
        x = float(event.position().x())
        target_sec = self._x_to_sec(x)
        self._hover_active = True
        self._hover_x = x
        self._hover_sec = target_sec

        if self._is_dragging:
            self._drag_sec = target_sec
            now = time.monotonic()
            if now - self._last_drag_seek_time >= 0.08:
                self._last_drag_seek_time = now
                self.seek_requested.emit(self._layer_idx, target_sec)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Start a left-click scrub and emit the first seek request."""
        if not self._is_seekable():
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            target_sec = self._x_to_sec(event.position().x())
            self._drag_sec = target_sec
            self._last_drag_seek_time = time.monotonic()
            self.seek_requested.emit(self._layer_idx, target_sec)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Finish a scrub and emit the final seek position."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            target_sec = self._x_to_sec(event.position().x())
            self._pos_sec = target_sec
            self.seek_requested.emit(self._layer_idx, target_sec)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        """Seek ±5 s with the mouse wheel, clamped to the in/out region."""
        if not self._is_seekable():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        step = 5.0 if delta > 0 else -5.0
        new_pos = max(self._start_sec, min(self._end_sec, self._pos_sec + step))
        self.seek_requested.emit(self._layer_idx, new_pos)
        self.update()
        event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Show the per-layer seek / play-pause context menu."""
        if not self._is_seekable():
            super().contextMenuEvent(event)
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #0f172a; color: #e2e8f0; border: 1px solid #334155; padding: 4px; } "
            "QMenu::item { padding: 6px 18px; border-radius: 3px; font-weight: bold; font-size: 11px; } "
            "QMenu::item:selected { background-color: #1e293b; color: #38bdf8; }"
        )
        act_minus10 = menu.addAction("⏪ Salta Indietro di 10s")
        act_minus10.triggered.connect(
            lambda: self.seek_requested.emit(self._layer_idx, max(self._start_sec, self._pos_sec - 10.0))
        )

        act_minus5 = menu.addAction("⏪ Salta Indietro di 5s")
        act_minus5.triggered.connect(
            lambda: self.seek_requested.emit(self._layer_idx, max(self._start_sec, self._pos_sec - 5.0))
        )

        act_plus10 = menu.addAction("⏩ Salta Avanti di 10s")
        act_plus10.triggered.connect(
            lambda: self.seek_requested.emit(self._layer_idx, min(self._end_sec, self._pos_sec + 10.0))
        )

        act_start = menu.addAction("⏮ Riavvia da Inizio Cue (In-Point)")
        act_start.triggered.connect(lambda: self.seek_requested.emit(self._layer_idx, self._start_sec))

        menu.addSeparator()
        if self._is_paused:
            act_pp = menu.addAction("▶ Riprendi Riproduzione")
        else:
            act_pp = menu.addAction("⏸ Metti in Pausa (Prove)")
        act_pp.triggered.connect(lambda: self.play_pause_requested.emit(self._layer_idx))

        menu.exec(event.globalPos())

    def set_live(self, cue: Cue, duration_sec: float = 0.0, preserve_timing: bool = False) -> None:
        """Bind this bar to a cue that is now live on its layer.

        *preserve_timing* keeps the running playhead when the same cue is
        refreshed (e.g. after an inspector edit), so a mid-show tweak never
        restarts the visual countdown from zero.
        """
        same_live = preserve_timing and self._is_live and self._cue_id == cue.cue_id
        self._is_live = True
        self._phase = ""
        self._cue_id = cue.cue_id
        self._media_type = cue.media_type
        self._title = cue.name
        self._q_label = cue.q_label
        if not same_live:
            self._is_paused = False
        if cue.media_type == MediaType.IMAGE:
            self._start_sec = 0.0
            self._end_sec = cue.hold_time if cue.hold_time > 0 else 0.0
            if not same_live:
                self._pos_sec = 0.0
            self._is_looping_inf = (cue.hold_time <= 0)
        else:
            self._start_sec = max(0.0, cue.in_point)
            if cue.out_point is not None and cue.out_point > cue.in_point:
                self._end_sec = cue.out_point
            elif duration_sec > 0:
                self._end_sec = max(self._start_sec, duration_sec)
            elif not same_live:
                self._end_sec = 0.0
            if not same_live:
                self._pos_sec = self._start_sec
            self._is_looping_inf = bool(
                (cue.loop and cue.loop_count <= 0)
                or any(s.loops == 0 and not s.skip for s in cue.sections)
            )
        self.update()

    def set_progress(
        self,
        pos_sec: float,
        start_sec: float | None = None,
        end_sec: float | None = None,
        is_looping_inf: bool | None = None,
    ) -> None:
        """Advance the bar playhead without rebuilding the cue binding.

        Called at ~30 fps by the live view; updates smaller than the paint
        resolution are ignored to avoid useless repaints, and the playhead is
        frozen while the operator is scrubbing the bar.
        """
        if not self._is_live:
            return
        changed = False
        if start_sec is not None and abs(start_sec - self._start_sec) >= 0.01:
            self._start_sec = max(0.0, start_sec)
            changed = True
        if end_sec is not None and end_sec > 0 and abs(end_sec - self._end_sec) >= 0.01:
            self._end_sec = end_sec
            changed = True
        if is_looping_inf is not None and is_looping_inf != self._is_looping_inf:
            self._is_looping_inf = is_looping_inf
            changed = True
        if abs(pos_sec - self._pos_sec) >= 0.05 or changed:
            if not self._is_dragging:
                self._pos_sec = max(0.0, pos_sec)
                self.update()

    def set_phase_progress(self, cue: Cue, phase: str, elapsed_sec: float, total_sec: float) -> None:
        """Show active Pre-Delay or Post-Delay countdown bar cleanly on the layer."""
        self._is_live = True
        self._cue_id = cue.cue_id
        self._media_type = cue.media_type
        self._title = cue.name
        self._q_label = cue.q_label
        self._phase = phase
        self._start_sec = 0.0
        self._end_sec = max(0.01, float(total_sec))
        self._pos_sec = min(self._end_sec, max(0.0, float(elapsed_sec)))
        self._is_looping_inf = False
        self.update()

    def set_paused(self, paused: bool) -> None:
        """Show or clear the PAUSED overlay on this layer bar."""
        if self._is_paused != paused:
            self._is_paused = paused
            self.update()

    def reset(self) -> None:
        """Return the bar to the idle state (no cue, playhead at zero)."""
        self._is_live = False
        self._cue_id = -1
        self._phase = ""
        self._media_type = None
        self._title = ""
        self._q_label = ""
        self._pos_sec = 0.0
        self._start_sec = 0.0
        self._end_sec = 0.0
        self._is_paused = False
        self._is_looping_inf = False
        self._hover_active = False
        self._hover_x = -1.0
        self._is_dragging = False
        self.unsetCursor()
        self.update()

    def text(self) -> str:
        """Backward-compatible text representation."""
        if not self._is_live:
            return f"{self._label}: —"
        mtag = self._media_type.value if self._media_type else "LIVE"
        q_part = f"{self._q_label} • " if self._q_label else ""
        return f"LIVE: [{mtag}] {q_part}{self._title}  ({self._label})"

    def _progress_metrics(self) -> tuple[bool, float, str, str, float | None]:
        """Return (is_timed, progress_0_1, left_elapsed, right_countdown, remaining_sec)."""
        if self._phase in ("PRE", "POST"):
            span = max(0.01, self._end_sec)
            progress = min(1.0, max(0.0, self._pos_sec / span))
            remaining = max(0.0, span - self._pos_sec)
            prefix = "⏳ PRE" if self._phase == "PRE" else "⏱ POST"
            left_str = f"{prefix} {_fmt_mmss(self._pos_sec)}"
            right_str = f"-{_fmt_mmss(remaining)}"
            return True, progress, left_str, right_str, remaining

        is_timed = (self._media_type in (MediaType.AUDIO, MediaType.VIDEO)) or (
            self._media_type == MediaType.IMAGE and self._end_sec > self._start_sec
        )
        progress = 0.0
        cur_pos = self._drag_sec if (self._is_dragging and self._is_seekable()) else self._pos_sec
        elapsed_cue = max(0.0, cur_pos - self._start_sec)
        remaining: float | None = None
        if is_timed and self._end_sec > self._start_sec:
            span = max(0.01, self._end_sec - self._start_sec)
            progress = min(1.0, max(0.0, elapsed_cue / span))
            remaining = max(0.0, self._end_sec - cur_pos)

        left_str = ""
        right_str = ""
        if is_timed:
            left_str = _fmt_mmss(elapsed_cue)
            if self._is_looping_inf:
                right_str = f"-{_fmt_mmss(remaining)} ∞" if remaining is not None else "∞ LOOP"
            elif remaining is not None:
                # The same ends-soon sign as the list and the cards (W36).
                soon = remaining <= WARN_BEFORE_END_SEC
                right_str = f"{'⚠' if soon else ''}-{_fmt_mmss(remaining)}"
            else:
                right_str = "--:--"
        return is_timed, progress, left_str, right_str, remaining

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Paint the layer progress bar, timecodes and drag thumb."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 2 or h <= 2:
            p.end()
            return

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 4.0, 4.0)

        is_mono = get_active_theme().is_monochrome

        if not self._is_live:
            if is_mono:
                p.fillPath(clip_path, QColor("#16171b"))
                p.setPen(QPen(QColor("#2c2d36"), 1))
                p.drawPath(clip_path)
                p.setPen(QColor("#a1a1aa"))
            else:
                p.fillPath(clip_path, QColor("#22262e"))
                p.setPen(QPen(QColor("#4b5563"), 1))
                p.drawPath(clip_path)
                p.setPen(QColor("#94a3b8"))
            p.setFont(QFont("sans-serif", 10))
            p.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{self._label}: —")
            p.end()
            return

        is_timed, progress, left_str, right_str, remaining = self._progress_metrics()

        # Base dark studio bar
        if is_mono:
            base_bg = QColor("#1e1f26") if self._is_paused else QColor("#16171c")
        else:
            if self._is_paused:
                base_bg = QColor("#211a08")
            elif self._phase == "PRE":
                base_bg = QColor("#0d1e2e")
            elif self._phase == "POST":
                base_bg = QColor("#22152e")
            else:
                base_bg = QColor("#0e2215")
        p.fillPath(clip_path, base_bg)

        # Progressive left-to-right animated fill
        p.save()
        p.setClipPath(clip_path)
        if not is_timed:
            # Static image active fill
            if is_mono:
                p.fillRect(rect, QColor(255, 255, 255, 25))
            else:
                p.fillRect(rect, QColor(16, 125, 58, 95))
        elif progress > 0.0:
            fill_w = w * progress
            grad = QLinearGradient(0.0, 0.0, max(1.0, fill_w), 0.0)
            if is_mono:
                grad.setColorAt(0.0, QColor(36, 38, 48, 160))
                grad.setColorAt(1.0, QColor(68, 70, 84, 220))
                edge_clr = QColor("#d4d4d8") if self._is_paused else QColor("#ffffff")
            else:
                if self._is_paused:
                    grad.setColorAt(0.0, QColor(180, 120, 12, 55))
                    grad.setColorAt(1.0, QColor(245, 158, 11, 70))
                    edge_clr = QColor("#fbbf24")
                elif self._phase == "PRE":
                    grad.setColorAt(0.0, QColor(14, 116, 144, 110))
                    grad.setColorAt(1.0, QColor(56, 189, 248, 155))
                    edge_clr = QColor("#7dd3fc")
                elif self._phase == "POST":
                    grad.setColorAt(0.0, QColor(109, 40, 217, 110))
                    grad.setColorAt(1.0, QColor(192, 132, 252, 155))
                    edge_clr = QColor("#d8b4fe")
                else:
                    grad.setColorAt(0.0, QColor(16, 115, 54, 55))
                    grad.setColorAt(1.0, QColor(0, 230, 118, 70))
                    edge_clr = QColor("#69f0ae")
            p.fillRect(QRectF(0.0, 0.0, fill_w, float(h)), grad)
            p.setPen(QPen(edge_clr, 2.0))
            p.drawLine(int(fill_w), 1, int(fill_w), h - 1)
            # Scrubber notches
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(edge_clr)
            p.drawPolygon(QPolygonF([QPointF(fill_w - 3.5, 0), QPointF(fill_w + 3.5, 0), QPointF(fill_w, 4.0)]))
            p.drawPolygon(QPolygonF([QPointF(fill_w - 3.5, h), QPointF(fill_w + 3.5, h), QPointF(fill_w, h - 4.0)]))
        p.restore()

        # Crisp border highlight
        if is_mono:
            border_clr = QColor("#d4d4d8") if self._is_paused else QColor("#ffffff")
            b_width = 1.5 if self._is_paused else 1.8
        else:
            if self._is_paused:
                border_clr = QColor("#f59e0b")
            elif self._phase == "PRE":
                border_clr = QColor("#38bdf8")
            elif self._phase == "POST":
                border_clr = QColor("#c084fc")
            else:
                border_clr = QColor(CLR_LIVE)
            b_width = 1.2
        p.setPen(QPen(border_clr, b_width))
        p.drawRoundedRect(rect, 4.0, 4.0)

        # Text regions: Left elapsed | Center title | Right countdown
        m_pad = 8
        mono = QFont("monospace", 9, QFont.Weight.Bold)
        title_font = QFont("sans-serif", 10, QFont.Weight.Bold)

        fm_mono = QFontMetrics(mono)
        left_w = (fm_mono.horizontalAdvance(left_str) + 8) if left_str else 0
        right_w = (fm_mono.horizontalAdvance(right_str) + 8) if right_str else 0

        if left_str:
            p.setFont(mono)
            if is_mono:
                left_pen = QColor("#f4f4f5")
            else:
                left_pen = QColor("#fde68a" if self._is_paused else "#a7f3d0")
            p.setPen(left_pen)
            p.drawText(
                QRectF(m_pad, 0, left_w, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                left_str,
            )

        if right_str:
            p.setFont(mono)
            # One threshold in the whole program, amber and a sign, never red (W36).
            soon = remaining is not None and not self._is_looping_inf and remaining <= WARN_BEFORE_END_SEC
            if is_mono:
                r_clr = QColor("#ffffff" if soon else "#f4f4f5")
            else:
                if self._is_paused or soon:
                    r_clr = QColor("#fbbf24")
                else:
                    r_clr = QColor("#d1fae5")
            p.setPen(r_clr)
            p.drawText(
                QRectF(w - m_pad - right_w, 0, right_w, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                right_str,
            )

        # Centered cue title elided safely between timers
        mtag = self._media_type.value if self._media_type else "LIVE"
        q_part = f"{self._q_label} • " if self._q_label else ""
        pause_prefix = "⏸ " if self._is_paused else ""
        raw_title = f"{pause_prefix}[{mtag}] {q_part}{self._title}"
        center_left = m_pad + left_w + (4 if left_str else 0)
        center_right = w - m_pad - right_w - (4 if right_str else 0)
        avail_center_w = max(24, int(center_right - center_left))
        fm_title = QFontMetrics(title_font)
        elided_title = fm_title.elidedText(raw_title, Qt.TextElideMode.ElideRight, avail_center_w)

        p.setFont(title_font)
        if is_mono:
            title_clr = QColor("#ffffff")
        else:
            title_clr = QColor("#fef3c7" if self._is_paused else "#ffffff")
        p.setPen(title_clr)
        p.drawText(
            QRectF(center_left, 0, avail_center_w, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
            elided_title,
        )

        # Hover / Drag scrubbing visual indicator & floating time pill
        if is_timed and (self._is_dragging or (self._hover_active and self._is_seekable())):
            span = max(0.01, self._end_sec - self._start_sec)
            active_x = (
                w * max(0.0, min(1.0, (self._drag_sec - self._start_sec) / span))
                if self._is_dragging
                else self._hover_x
            )
            time_sec = self._drag_sec if self._is_dragging else self._hover_sec
            rel_sec = max(0.0, time_sec - self._start_sec)
            time_txt = f"⏱ {_fmt_mmss(rel_sec)}"

            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if is_mono:
                line_clr = QColor("#ffffff") if self._is_dragging else QColor("#d4d4d8")
                bg_clr = QColor("#22232a")
            else:
                line_clr = QColor("#fde047") if self._is_dragging else QColor("#38bdf8")
                bg_clr = QColor("#221b05" if self._is_dragging else "#082f49")
            line_clr.setAlpha(245 if self._is_dragging else 180)
            p.setPen(QPen(line_clr, 1.5, Qt.PenStyle.SolidLine if self._is_dragging else Qt.PenStyle.DashLine))
            p.drawLine(int(active_x), 1, int(active_x), h - 1)

            badge_font = QFont("monospace", 8, QFont.Weight.Bold)
            p.setFont(badge_font)
            fm_b = QFontMetrics(badge_font)
            bw = fm_b.horizontalAdvance(time_txt) + 12
            bh = 17
            bx = max(2.0, min(float(w - bw - 2), active_x - bw / 2.0))
            by = 2.0
            b_rect = QRectF(bx, by, bw, bh)

            p.setPen(QPen(line_clr, 1.0))
            bg_clr.setAlpha(235)
            p.setBrush(bg_clr)
            p.drawRoundedRect(b_rect, 3.5, 3.5)

            p.setPen(line_clr)
            p.drawText(b_rect, Qt.AlignmentFlag.AlignCenter, time_txt)
            p.restore()

        p.end()


class _LayerRoundIconButton(QPushButton):
    """Custom-painted anti-aliased circular button with crisp vector icons (no OS emoji glyph glitch)."""

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        """Create a 26 px circular button showing ``mode`` (PLAY/PAUSE/JUMP_BACK)."""
        super().__init__("", parent)
        self._mode = mode  # "JUMP_BACK", "PAUSE", "PLAY"
        self._hover = False
        self._pressed = False
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_mode(self, mode: str) -> None:
        """Switch the round button glyph between ``"PLAY"`` and ``"PAUSE"``."""
        if self._mode != mode:
            self._mode = mode
            self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        """Repaint with the hover highlight."""
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Clear the hover highlight."""
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Show the pressed state while the button is held."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Restore the normal state on release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Draw the antialiased circle and its vector glyph."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0
        r = (min(w, h) - 2.0) / 2.0

        if self._mode == "JUMP_BACK":
            bg = QColor("#1e3a5f" if self._hover else "#0f2038")
            border = QColor("#60a5fa" if self._hover else "#2563eb")
            fg = QColor("#ffffff" if self._hover else "#93c5fd")
        elif self._mode == "PLAY":
            bg = QColor("#3f2806" if self._hover else "#241604")
            border = QColor("#fbbf24" if self._hover else "#f59e0b")
            fg = QColor("#ffffff" if self._hover else "#fbbf24")
        else:  # PAUSE
            bg = QColor("#14432a" if self._hover else "#0c2818")
            border = QColor("#00e676" if self._hover else "#16a34a")
            fg = QColor("#ffffff" if self._hover else "#86efac")

        if self._pressed:
            bg = bg.lighter(130)

        # Anti-aliased circular disk
        p.setBrush(bg)
        p.setPen(QPen(border, 1.2))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Draw vector icon geometry
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fg)

        if self._mode == "JUMP_BACK":
            # Two crisp left-pointing isosceles triangles, perfectly centered
            poly1 = QPolygonF([QPointF(7.5, cy), QPointF(12.5, cy - 4.5), QPointF(12.5, cy + 4.5)])
            poly2 = QPolygonF([QPointF(13.5, cy), QPointF(18.5, cy - 4.5), QPointF(18.5, cy + 4.5)])
            p.drawPolygon(poly1)
            p.drawPolygon(poly2)

        elif self._mode == "PAUSE":
            # Two vertical rounded pill bars, 10px high, 2.8px wide, centered vertically (y = cy - 5 to cy + 5)
            # Ample 8px margin from top and bottom - never touches or clips the top edge!
            bar_w = 2.8
            bar_h = 10.0
            bar_y = cy - (bar_h / 2.0)
            p.drawRoundedRect(QRectF(cx - 4.6, bar_y, bar_w, bar_h), 1.0, 1.0)
            p.drawRoundedRect(QRectF(cx + 1.8, bar_y, bar_w, bar_h), 1.0, 1.0)

        elif self._mode == "PLAY":
            # Right-pointing triangle, optically centered with a slight right bias (+0.75px)
            play_poly = QPolygonF([
                QPointF(cx - 3.5, cy - 5.0),
                QPointF(cx - 3.5, cy + 5.0),
                QPointF(cx + 5.2, cy),
            ])
            p.drawPolygon(play_poly)

        p.end()


class LiveStatusPanel(QGroupBox):
    """Real-time monitor and Play/Pause, Cut, Blackout controls for Layers 1-3 plus Layer 0."""

    clear_layer_clicked = Signal(int)
    layer_play_pause_clicked = Signal(int)
    layer_seek_requested = Signal(int, float)
    blackout_clicked = Signal()
    choose_layer0_clicked = Signal()
    reset_layer0_clicked = Signal()
    output_screen_changed = Signal(str, str)  # (output "A"/"B", screen name)

    def __init__(self, parent: QWidget | None = None, compact_live_mode: bool = False) -> None:
        """Create the live output monitor (``compact_live_mode`` = embedded in the live view)."""
        super().__init__(
            "Monitor Uscita Layer Live (L3 Sopra → L1 Sfondo)"
            if compact_live_mode
            else "Live Output Status (Monitor Uscita Schermo Esterno)",
            parent,
        )
        self._compact_live_mode = compact_live_mode
        self._locked: bool = compact_live_mode
        self._layer_labels: dict[int, _LiveLayerBar] = {}
        self._play_pause_buttons: dict[int, _LayerRoundIconButton] = {}
        self._jump_back_buttons: dict[int, _LayerRoundIconButton] = {}
        self._clear_buttons: dict[int, QPushButton] = {}
        self._previous_screen: dict[str, str] = {"A": "", "B": ""}
        self._build_ui()
        if self._compact_live_mode:
            self.set_locked(True)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        lbl_sub = QLabel("Controllo emissione in tempo reale sui 3 livelli live:")
        lbl_sub.setStyleSheet("color: #777; font-size: 10px;")
        lbl_sub.setVisible(not self._compact_live_mode)
        layout.addWidget(lbl_sub)

        # Projector picker for outputs A/B. Hidden unless two external displays
        # are connected: with one projector there is nothing to route, with
        # none the output runs on the director screen.
        self._monitor_row = QWidget()
        monitor_layout = QHBoxLayout(self._monitor_row)
        monitor_layout.setContentsMargins(0, 0, 0, 2)
        monitor_layout.setSpacing(6)
        lbl_screen_a = QLabel("Proiettore A:")
        lbl_screen_a.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
        self._combo_screen_a = QComboBox()
        self._combo_screen_a.setToolTip("Schermo fisico su cui viene proiettata l'uscita A.")
        self._combo_screen_a.setAccessibleName("Proiettore uscita A")
        self._combo_screen_a.currentIndexChanged.connect(
            lambda _idx: self._on_screen_combo_changed("A")
        )
        lbl_screen_b = QLabel("Proiettore B:")
        lbl_screen_b.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
        self._combo_screen_b = QComboBox()
        self._combo_screen_b.setToolTip("Schermo fisico su cui viene proiettata l'uscita B.")
        self._combo_screen_b.setAccessibleName("Proiettore uscita B")
        self._combo_screen_b.currentIndexChanged.connect(
            lambda _idx: self._on_screen_combo_changed("B")
        )
        monitor_layout.addWidget(lbl_screen_a)
        monitor_layout.addWidget(self._combo_screen_a, 1)
        monitor_layout.addWidget(lbl_screen_b)
        monitor_layout.addWidget(self._combo_screen_b, 1)
        self._monitor_row.setVisible(False)
        layout.addWidget(self._monitor_row)

        cut_style = (
            "QPushButton { background-color: #2b1111; color: #ff8888; border: 1px solid #772222; "
            "border-radius: 4px; font-weight: bold; font-size: 10px; padding: 0px 8px; } "
            "QPushButton:hover { background-color: #4a1a1a; color: #ffffff; border-color: #ef4444; }"
        )

        # Display Layers top-to-bottom in visual Z-order (Overlay L3 on top -> Sfondo L1 on bottom)
        def _build_layer_row(
            target_layout: QVBoxLayout,
            layer: int,
            display_layer: int,
            *,
            prefix: str = "",
        ) -> None:
            """Build one layer row (status bar + jump back + pause + cut button)."""
            layer_desc = (
                f"Layer {display_layer} · Uscita B" if prefix else f"Layer {display_layer}"
            )
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            bar = _LiveLayerBar(layer, label=layer_desc)
            bar.seek_requested.connect(self.layer_seek_requested.emit)
            bar.play_pause_requested.connect(self.layer_play_pause_clicked.emit)

            btn_back10 = _LayerRoundIconButton("JUMP_BACK")
            btn_back10.setVisible(False)
            btn_back10.setToolTip(f"Salta indietro di 10s su {layer_desc} (utile nelle prove per ripetere la battuta)")
            btn_back10.setAccessibleName(f"Riavvolgi 10 secondi {layer_desc}")
            btn_back10.setAccessibleDescription(f"Sposta indietro di 10 secondi la testina del {layer_desc}.")
            btn_back10.clicked.connect(lambda _=False, idx=layer: self._on_quick_jump_backward(idx, 10.0))

            btn_pp = _LayerRoundIconButton("PAUSE")
            btn_pp.setVisible(False)
            btn_pp.setToolTip(f"Metti in Pausa {layer_desc} (utile durante le prove)")
            btn_pp.setAccessibleName(f"Pausa o Riprendi {layer_desc}")
            btn_pp.clicked.connect(lambda _=False, idx=layer: self.layer_play_pause_clicked.emit(idx))

            if self._compact_live_mode:
                btn = HoldProgressButton(
                    text_idle="Fade Out",
                    hold_ms=600,
                    is_toggle=False,
                    color_idle="#2b1111",
                    border_idle="#772222",
                    text_color_idle="#ff8888",
                    fill_color="#ef4444",
                )
                btn.setFixedHeight(26)
                btn.setMinimumWidth(102)
                btn.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
                btn.setToolTip(
                    f"Dissolvenza in uscita e arresto del contenuto su {layer_desc}.\n"
                    "La durata è quella del Fade Out della cue (minimo 0.2 s).\n"
                    "PROTEZIONE LIVE: tieni premuto 0.6 secondi per confermare, così un clic involontario non taglia nulla."
                )
                btn.setAccessibleName(f"Dissolvenza in uscita {layer_desc}")
                btn.setAccessibleDescription(f"Dissolve in uscita e ferma il contenuto sul {layer_desc} usando il Fade Out della cue. Richiede 0.6 secondi di pressione.")
                btn.hold_completed.connect(lambda idx=layer: self.clear_layer_clicked.emit(idx))
            else:
                btn = QPushButton("Fade Out")
                btn.setFixedHeight(26)
                btn.setToolTip(
                    f"Dissolvenza in uscita e arresto del contenuto su {layer_desc}.\n"
                    "La durata è quella del Fade Out della cue (minimo 0.2 s)."
                )
                btn.setAccessibleName(f"Dissolvenza in uscita {layer_desc}")
                btn.setStyleSheet(cut_style)
                btn.clicked.connect(lambda _=False, idx=layer: self.clear_layer_clicked.emit(idx))

            row.addWidget(bar, stretch=1)
            row.addWidget(btn_back10)
            row.addWidget(btn_pp)
            row.addWidget(btn)
            target_layout.addLayout(row)
            self._layer_labels[layer] = bar
            self._jump_back_buttons[layer] = btn_back10
            self._play_pause_buttons[layer] = btn_pp
            self._clear_buttons[layer] = btn

        # Output A: runtime layers 1-3
        for layer in (3, 2, 1):
            _build_layer_row(layout, layer, layer)

        # Output B: runtime layers 4-6, shown only in "two independent outputs" mode
        self._dual_container = QWidget()
        dual_layout = QVBoxLayout(self._dual_container)
        dual_layout.setContentsMargins(0, 4, 0, 0)
        dual_layout.setSpacing(6)
        lbl_output_b = QLabel("USCITA B — secondo proiettore indipendente")
        lbl_output_b.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        dual_layout.addWidget(lbl_output_b)
        for runtime_layer, display_layer in ((6, 3), (5, 2), (4, 1)):
            _build_layer_row(dual_layout, runtime_layer, display_layer, prefix="B·")
        self._dual_container.setVisible(False)
        layout.addWidget(self._dual_container)

        self.btn_clear_all = QPushButton("⏹ Master Blackout (Tappo) — [ Ctrl+B ]")
        self.btn_clear_all.setToolTip(
            "Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B"
        )
        self.btn_clear_all.setAccessibleName("Master Blackout")
        self.btn_clear_all.setAccessibleDescription("Arresta immediatamente l'output di tutti i layer e torna allo sfondo tappo. Scorciatoia: Ctrl+B.")
        self.btn_clear_all.setStyleSheet(
            "QPushButton { background-color: #3a1111; color: #ff9999; border: 1px solid #882222; "
            "border-radius: 4px; font-weight: bold; padding: 6px; } "
            "QPushButton:hover { background-color: #5c1d1d; }"
        )
        self.btn_clear_all.clicked.connect(self.blackout_clicked)
        self.btn_clear_all.setVisible(not self._compact_live_mode)
        layout.addWidget(self.btn_clear_all)

        row_tappo = QHBoxLayout()
        row_tappo.setContentsMargins(0, 2, 0, 0)
        row_tappo.setSpacing(8)
        self.lbl_tappo_info = QLabel("Tappo (L0): Logo BlindCue (Predefinito)")
        self.lbl_tappo_info.setMinimumWidth(0)
        self.lbl_tappo_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_tappo_info.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 2px;")

        self.btn_choose_tappo = QPushButton("📁 Cambia Tappo…")
        self.btn_choose_tappo.setFixedHeight(24)
        self.btn_choose_tappo.setToolTip(
            "Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)"
        )
        self.btn_choose_tappo.setStyleSheet(
            f"QPushButton {{ background-color: #1e293b; color: {CLR_PREVIZ}; border: 1px solid {CLR_PREVIZ}; "
            f"border-radius: 4px; font-weight: bold; padding: 0px 10px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: #334155; color: #ffffff; }}"
        )
        self.btn_choose_tappo.clicked.connect(self.choose_layer0_clicked)

        self.btn_reset_tappo = QPushButton("🔄 Reset")
        self.btn_reset_tappo.setFixedHeight(24)
        self.btn_reset_tappo.setToolTip("Ripristina il logo predefinito di BlindCue come Layer 0")
        self.btn_reset_tappo.setStyleSheet(
            "QPushButton { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; "
            "border-radius: 4px; padding: 0px 8px; font-size: 11px; font-weight: bold; } "
            "QPushButton:hover { background-color: #334155; color: #f8fafc; border-color: #64748b; }"
        )
        self.btn_reset_tappo.clicked.connect(self.reset_layer0_clicked)

        row_tappo.addWidget(self.lbl_tappo_info, stretch=1)
        row_tappo.addWidget(self.btn_choose_tappo)
        row_tappo.addWidget(self.btn_reset_tappo)
        for w_t in (self.lbl_tappo_info, self.btn_choose_tappo, self.btn_reset_tappo):
            w_t.setVisible(not self._compact_live_mode)
        layout.addLayout(row_tappo)
        layout.addStretch()
        self.refresh_theme_styles()

    def is_locked(self) -> bool:
        """True when the layer controls are protected against accidental use."""
        return self._locked

    def set_locked(self, locked: bool) -> None:
        """Lock or unlock interactive scrub, rehearsal jump, and pause across all layers."""
        self._locked = bool(locked)
        for layer, bar in self._layer_labels.items():
            bar.set_locked(self._locked)
        for layer, btn_back in self._jump_back_buttons.items():
            btn_back.setEnabled(not self._locked)
            btn_back.setToolTip(
                "🔒 Controlli Layer Protetti — Sblocca con il Lucchetto (1,2s)"
                if self._locked
                else f"Salta indietro di 10s su Layer {layer} (prove)"
            )
        for layer, btn_pp in self._play_pause_buttons.items():
            btn_pp.setEnabled(not self._locked)
            btn_pp.setToolTip(
                "🔒 Controlli Layer Protetti — Sblocca con il Lucchetto (1,2s)"
                if self._locked
                else f"Metti in Pausa Layer {layer} (prove)"
            )

    @staticmethod
    def _style_play_pause_btn(btn: _LayerRoundIconButton, *, paused: bool) -> None:
        btn.set_mode("PLAY" if paused else "PAUSE")
        btn.setToolTip(
            "Riprendi riproduzione (Layer attualmente in Pausa)"
            if paused
            else "Metti in Pausa (utile durante le prove)"
        )

    def _on_quick_jump_backward(self, layer: int, delta_sec: float = 10.0) -> None:
        bar = self._layer_labels.get(layer)
        if bar is not None and bar._is_seekable():
            target = max(bar._start_sec, bar._pos_sec - delta_sec)
            self.layer_seek_requested.emit(layer, target)

    def set_layer_live(
        self,
        cue: Cue,
        duration_sec: float = 0.0,
        preserve_timing: bool = False,
        layer_idx: int | None = None,
    ) -> None:
        """Bind *cue* to the bar of its runtime layer (1-6).

        *layer_idx* overrides ``cue.layer`` for dual-output routing, where
        layers 4-6 are the second projector's independent layers.
        """
        idx = cue.layer if layer_idx is None else int(layer_idx)
        bar = self._layer_labels.get(idx)
        if bar is not None:
            bar.set_live(cue, duration_sec=duration_sec, preserve_timing=preserve_timing)
        is_playable = cue.media_type in (MediaType.AUDIO, MediaType.VIDEO)
        btn_pp = self._play_pause_buttons.get(idx)
        if btn_pp is not None:
            btn_pp.setVisible(is_playable)
            if not preserve_timing:
                self._style_play_pause_btn(btn_pp, paused=False)
        btn_back = self._jump_back_buttons.get(idx)
        if btn_back is not None:
            btn_back.setVisible(is_playable)

    def set_layer_progress(
        self,
        layer: int,
        pos_sec: float,
        start_sec: float | None = None,
        end_sec: float | None = None,
        is_looping_inf: bool | None = None,
    ) -> None:
        """Update the playhead of *layer* without touching its cue binding."""
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_progress(
                pos_sec, start_sec=start_sec, end_sec=end_sec, is_looping_inf=is_looping_inf
            )

    def set_layer_phase_progress(self, layer: int, cue: Cue, phase: str, elapsed: float, total: float) -> None:
        """Show a Pre-Delay/Post-Delay countdown instead of media progress.

        During these phases the seek/pause controls are meaningless, so they
        are hidden until the cue returns to normal playback.
        """
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_phase_progress(cue, phase, elapsed, total)
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            btn_pp.setVisible(False)
        btn_back = self._jump_back_buttons.get(layer)
        if btn_back is not None:
            btn_back.setVisible(False)

    def set_layer_paused(self, layer: int, paused: bool) -> None:
        """Show the paused state on *layer*'s bar and flip its play/pause icon."""
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_paused(paused)
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            self._style_play_pause_btn(btn_pp, paused=paused)

    def reset_layer(self, layer: int) -> None:
        """Clear the bar of *layer* and hide its per-layer controls."""
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.reset()
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            btn_pp.setVisible(False)
            self._style_play_pause_btn(btn_pp, paused=False)
        btn_back = self._jump_back_buttons.get(layer)
        if btn_back is not None:
            btn_back.setVisible(False)

    def reset_all_layers(self) -> None:
        """Clear every layer bar (PANIC / stop of the whole show)."""
        for layer in list(self._layer_labels):
            self.reset_layer(layer)

    def set_dual_mode(self, enabled: bool) -> None:
        """Show or hide the second independent output rows (runtime layers 4-6)."""
        self._dual_container.setVisible(bool(enabled))

    def set_output_monitors(
        self,
        screens: list,
        current_a: str = "",
        current_b: str = "",
    ) -> None:
        """Populate the projector pickers for outputs A and B.

        The row stays hidden unless two external displays are connected: with a
        single projector there is nothing to route, and with none the output
        runs on the director screen.
        """
        self._previous_screen = {"A": current_a, "B": current_b}
        show = len(screens) >= 2
        self._monitor_row.setVisible(show)
        if not show:
            return

        for combo, current in (
            (self._combo_screen_a, current_a),
            (self._combo_screen_b, current_b),
        ):
            combo.blockSignals(True)
            combo.clear()
            for screen in screens:
                geo = screen.geometry()
                combo.addItem(
                    f"{screen.name()} — {geo.width()}x{geo.height()}",
                    screen.name(),
                )
            index = combo.findData(current) if current else -1
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _on_screen_combo_changed(self, output: str) -> None:
        """Notify the manager about the projector chosen for *output*.

        Choosing the projector already used by the other output swaps the two
        outputs; the manager reports the final routing back through
        ``screens_changed`` and the combos are refreshed from that state.
        """
        src = self._combo_screen_a if output == "A" else self._combo_screen_b
        name = src.currentData()
        if not name:
            return
        self._previous_screen[output] = str(name)
        self.output_screen_changed.emit(output, str(name))

    def set_layer0_label(self, file_path: str | None) -> None:
        """Show which file backs Layer 0 (the always-on background)."""
        name = Path(file_path).name if file_path else "Logo BlindCue (Predefinito)"
        self.lbl_tappo_info.setText(f"Tappo (L0): {name}")

    def refresh_theme_styles(self) -> None:
        """Update button styles and hold button palettes according to the active theme."""
        active_t = get_active_theme()
        is_mono = active_t.is_monochrome

        for layer, btn in self._clear_buttons.items():
            if isinstance(btn, HoldProgressButton):
                if is_mono:
                    btn.set_palette_colors(
                        color_idle="#1a1b1f",
                        border_idle="#525363",
                        text_color_idle="#ffffff",
                        fill_color="#ffffff",
                    )
                elif active_t.theme_id == "warm_amber_studio":
                    btn.set_palette_colors(
                        color_idle="#2d1508",
                        border_idle="#7c2d12",
                        text_color_idle="#fca5a5",
                        fill_color="#f59e0b",
                    )
                else:
                    btn.set_palette_colors(
                        color_idle="#2b1111",
                        border_idle="#772222",
                        text_color_idle="#ff8888",
                        fill_color="#ef4444",
                    )
            elif isinstance(btn, QPushButton):
                if is_mono:
                    btn.setStyleSheet(
                        "QPushButton { background-color: #22232a; color: #ffffff; border: 1.5px solid #525363; "
                        "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; } "
                        "QPushButton:hover { background-color: #2d2f38; border-color: #ffffff; }"
                    )
                elif active_t.theme_id == "warm_amber_studio":
                    btn.setStyleSheet(
                        "QPushButton { background-color: #2d1508; color: #fca5a5; border: 1px solid #7c2d12; "
                        "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; } "
                        "QPushButton:hover { background-color: #431407; border-color: #f59e0b; color: #ffffff; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background-color: #381414; color: #ff8888; border: 1px solid #772222; "
                        "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; } "
                        "QPushButton:hover { background-color: #551c1c; border-color: #ff4444; color: #ffffff; }"
                    )

        if hasattr(self, "btn_clear_all") and self.btn_clear_all is not None:
            if is_mono:
                self.btn_clear_all.setStyleSheet(
                    "QPushButton { background-color: #1a1b1f; color: #ffffff; border: 1.5px solid #525363; "
                    "border-radius: 4px; font-weight: bold; padding: 6px; } "
                    "QPushButton:hover { background-color: #26272e; border-color: #ffffff; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.btn_clear_all.setStyleSheet(
                    "QPushButton { background-color: #2d1508; color: #fed7aa; border: 1px solid #7c2d12; "
                    "border-radius: 4px; font-weight: bold; padding: 6px; } "
                    "QPushButton:hover { background-color: #431407; border-color: #f59e0b; color: #ffffff; }"
                )
            else:
                self.btn_clear_all.setStyleSheet(
                    "QPushButton { background-color: #3a1111; color: #ff9999; border: 1px solid #882222; "
                    "border-radius: 4px; font-weight: bold; padding: 6px; } "
                    "QPushButton:hover { background-color: #551c1c; border-color: #ff4444; color: #ffffff; }"
                )

        for btn in list(self._jump_back_buttons.values()) + list(self._play_pause_buttons.values()):
            if is_mono:
                btn.setStyleSheet(
                    "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1px solid #3f404d; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; } "
                    "QPushButton:hover { background-color: #2d2f38; border-color: #ffffff; color: #ffffff; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                btn.setStyleSheet(
                    "QPushButton { background-color: #26201b; color: #bfa89b; border: 1px solid #42372f; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; } "
                    "QPushButton:hover { background-color: #362d26; border-color: #f59e0b; color: #ffffff; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color: #1a2230; color: #94a3b8; border: 1px solid #2d3e56; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; } "
                    "QPushButton:hover { background-color: #243144; border-color: #38bdf8; color: #ffffff; }"
                )
        self.update()
