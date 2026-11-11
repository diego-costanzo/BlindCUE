"""Bottom Live Output Status panel (Layers 1-3 progress bars, Play/Pause, Cut, Blackout, Layer 0 Tappo)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from models.cue import Cue, MediaType
from ui.theme import CLR_LIVE, CLR_PREVIZ


def _fmt_mmss(sec: float) -> str:
    s = max(0, int(round(sec))) if sec < 0.0 else max(0, int(sec))
    mins, rem = divmod(s, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{rem:02d}"
    return f"{mins:02d}:{rem:02d}"


class _LiveLayerBar(QWidget):
    """Progressive status bar showing Left elapsed, Center cue title, Right countdown, and fill."""

    def __init__(self, layer_idx: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layer_idx = layer_idx
        self._is_live: bool = False
        self._cue_id: int = -1
        self._media_type: Optional[MediaType] = None
        self._title: str = ""
        self._q_label: str = ""
        self._pos_sec: float = 0.0
        self._start_sec: float = 0.0
        self._end_sec: float = 0.0
        self._is_paused: bool = False
        self._is_looping_inf: bool = False
        self._phase: str = ""  # "" (normal), "PRE" (Pre-Delay), "POST" (Post-Delay)
        self.setMinimumWidth(0)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_live(self, cue: Cue, duration_sec: float = 0.0, preserve_timing: bool = False) -> None:
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
        start_sec: Optional[float] = None,
        end_sec: Optional[float] = None,
        is_looping_inf: Optional[bool] = None,
    ) -> None:
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
        if self._is_paused != paused:
            self._is_paused = paused
            self.update()

    def reset(self) -> None:
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
        self.update()

    def text(self) -> str:
        """Backward-compatible text representation."""
        if not self._is_live:
            return f"Layer {self._layer_idx}: —"
        mtag = self._media_type.value if self._media_type else "LIVE"
        q_part = f"{self._q_label} • " if self._q_label else ""
        return f"LIVE: [{mtag}] {q_part}{self._title}  (Layer {self._layer_idx})"

    def _progress_metrics(self) -> tuple[bool, float, str, str, Optional[float]]:
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
        elapsed_cue = max(0.0, self._pos_sec - self._start_sec)
        remaining: Optional[float] = None
        if is_timed and self._end_sec > self._start_sec:
            span = max(0.01, self._end_sec - self._start_sec)
            progress = min(1.0, max(0.0, elapsed_cue / span))
            remaining = max(0.0, self._end_sec - self._pos_sec)

        left_str = ""
        right_str = ""
        if is_timed:
            left_str = _fmt_mmss(elapsed_cue)
            if self._is_looping_inf:
                right_str = f"-{_fmt_mmss(remaining)} ∞" if remaining is not None else "∞ LOOP"
            elif remaining is not None:
                right_str = f"-{_fmt_mmss(remaining)}"
            else:
                right_str = "--:--"
        return is_timed, progress, left_str, right_str, remaining

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 2 or h <= 2:
            p.end()
            return

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 4.0, 4.0)

        if not self._is_live:
            p.fillPath(clip_path, QColor("#22262e"))
            p.setPen(QPen(QColor("#4b5563"), 1))
            p.drawPath(clip_path)
            p.setPen(QColor("#7b8494"))
            p.setFont(QFont("sans-serif", 10))
            p.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"Layer {self._layer_idx}: —")
            p.end()
            return

        is_timed, progress, left_str, right_str, remaining = self._progress_metrics()

        # Base dark studio bar
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
            p.fillRect(rect, QColor(16, 125, 58, 95))
        elif progress > 0.0:
            fill_w = w * progress
            grad = QLinearGradient(0.0, 0.0, max(1.0, fill_w), 0.0)
            if self._is_paused:
                grad.setColorAt(0.0, QColor(180, 120, 12, 95))
                grad.setColorAt(1.0, QColor(245, 158, 11, 145))
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
                grad.setColorAt(0.0, QColor(16, 115, 54, 105))
                grad.setColorAt(1.0, QColor(0, 230, 118, 150))
                edge_clr = QColor("#69f0ae")
            p.fillRect(QRectF(0.0, 0.0, fill_w, float(h)), grad)
            p.setPen(QPen(edge_clr, 1.5))
            p.drawLine(int(fill_w), 2, int(fill_w), h - 2)
        p.restore()

        # Crisp border highlight
        if self._is_paused:
            border_clr = QColor("#f59e0b")
        elif self._phase == "PRE":
            border_clr = QColor("#38bdf8")
        elif self._phase == "POST":
            border_clr = QColor("#c084fc")
        else:
            border_clr = QColor(CLR_LIVE)
        p.setPen(QPen(border_clr, 1.2))
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
            p.setPen(QColor("#fde68a" if self._is_paused else "#a7f3d0"))
            p.drawText(
                QRectF(m_pad, 0, left_w, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                left_str,
            )

        if right_str:
            p.setFont(mono)
            if self._is_paused:
                r_clr = QColor("#fbbf24")
            elif remaining is not None and not self._is_looping_inf and remaining <= 5.0:
                r_clr = QColor("#ff8080")
            elif remaining is not None and not self._is_looping_inf and remaining <= 12.0:
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
        p.setPen(QColor("#fef3c7" if self._is_paused else "#ffffff"))
        p.drawText(
            QRectF(center_left, 0, avail_center_w, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
            elided_title,
        )
        p.end()


class LiveStatusPanel(QGroupBox):
    """Real-time monitor and Play/Pause, Cut, Blackout controls for Layers 1-3 plus Layer 0."""

    clear_layer_clicked = Signal(int)
    layer_play_pause_clicked = Signal(int)
    blackout_clicked = Signal()
    choose_layer0_clicked = Signal()
    reset_layer0_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None, compact_live_mode: bool = False) -> None:
        super().__init__(
            "Monitor Uscita Layer Live (L3 Sopra → L1 Sfondo)"
            if compact_live_mode
            else "Live Output Status (Monitor Uscita Schermo Esterno)",
            parent,
        )
        self._compact_live_mode = compact_live_mode
        self._layer_labels: dict[int, _LiveLayerBar] = {}
        self._play_pause_buttons: dict[int, QPushButton] = {}
        self._clear_buttons: dict[int, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        lbl_sub = QLabel("Controllo emissione in tempo reale sui 3 livelli live:")
        lbl_sub.setStyleSheet("color: #777; font-size: 10px;")
        lbl_sub.setVisible(not self._compact_live_mode)
        layout.addWidget(lbl_sub)

        cut_style = (
            "QPushButton { background-color: #5c1d1d; color: #ff8080; border: 1px solid #ff4444; "
            "border-radius: 3px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background-color: #7a2727; }"
        )

        # Display Layers top-to-bottom in visual Z-order (Overlay L3 on top -> Sfondo L1 on bottom)
        for layer in (3, 2, 1):
            row = QHBoxLayout()
            row.setSpacing(5)
            bar = _LiveLayerBar(layer)

            btn_pp = QPushButton("⏸")
            btn_pp.setFixedSize(24, 24)
            btn_pp.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_pp.setVisible(False)
            btn_pp.setToolTip(f"Pausa / Riprendi Layer {layer} (utile durante le prove)")
            self._style_play_pause_btn(btn_pp, paused=False)
            btn_pp.clicked.connect(lambda _=False, idx=layer: self.layer_play_pause_clicked.emit(idx))

            btn = QPushButton(f"✕ Cut L{layer}")
            btn.setToolTip(f"Rimuovi / arresta immediatamente il contenuto su Layer {layer}")
            btn.setStyleSheet(cut_style)
            btn.clicked.connect(lambda _=False, idx=layer: self.clear_layer_clicked.emit(idx))

            row.addWidget(bar, stretch=1)
            row.addWidget(btn_pp)
            row.addWidget(btn)
            layout.addLayout(row)
            self._layer_labels[layer] = bar
            self._play_pause_buttons[layer] = btn_pp
            self._clear_buttons[layer] = btn

        self.btn_clear_all = QPushButton("⏹ Master Blackout (Tappo) — [ Ctrl+B ]")
        self.btn_clear_all.setToolTip(
            "Arresta tutto l'output e mostra Layer 0 (Tappo) — Scorciatoia di sicurezza: Ctrl+B"
        )
        self.btn_clear_all.setStyleSheet(
            "QPushButton { background-color: #3a1111; color: #ff9999; border: 1px solid #882222; "
            "border-radius: 4px; font-weight: bold; padding: 6px; } "
            "QPushButton:hover { background-color: #5c1d1d; }"
        )
        self.btn_clear_all.clicked.connect(self.blackout_clicked)
        self.btn_clear_all.setVisible(not self._compact_live_mode)
        layout.addWidget(self.btn_clear_all)

        row_tappo = QHBoxLayout()
        self.lbl_tappo_info = QLabel("Tappo (L0): Logo BlindCue (Predefinito)")
        self.lbl_tappo_info.setMinimumWidth(0)
        self.lbl_tappo_info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_tappo_info.setStyleSheet("color: #aaa; font-size: 11px; padding: 2px;")

        self.btn_choose_tappo = QPushButton("📁 Cambia Tappo…")
        self.btn_choose_tappo.setToolTip(
            "Seleziona un'immagine personalizzata per il Layer 0 (locandina festival, logo evento, nero)"
        )
        self.btn_choose_tappo.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: {CLR_PREVIZ}; border: 1px solid {CLR_PREVIZ}; "
            f"border-radius: 3px; font-weight: bold; padding: 3px 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ background-color: #4d3800; }}"
        )
        self.btn_choose_tappo.clicked.connect(self.choose_layer0_clicked)

        self.btn_reset_tappo = QPushButton("🔄 Reset")
        self.btn_reset_tappo.setToolTip("Ripristina il logo predefinito di BlindCue come Layer 0")
        self.btn_reset_tappo.setStyleSheet(
            "QPushButton { background-color: #2b2b2b; color: #888; border: 1px solid #555; "
            "border-radius: 3px; padding: 3px 6px; font-size: 11px; } "
            "QPushButton:hover { background-color: #3a3a3a; }"
        )
        self.btn_reset_tappo.clicked.connect(self.reset_layer0_clicked)

        row_tappo.addWidget(self.lbl_tappo_info, stretch=1)
        row_tappo.addWidget(self.btn_choose_tappo)
        row_tappo.addWidget(self.btn_reset_tappo)
        for w_t in (self.lbl_tappo_info, self.btn_choose_tappo, self.btn_reset_tappo):
            w_t.setVisible(not self._compact_live_mode)
        layout.addLayout(row_tappo)
        layout.addStretch()

    @staticmethod
    def _style_play_pause_btn(btn: QPushButton, *, paused: bool) -> None:
        if paused:
            btn.setText("▶")
            btn.setStyleSheet(
                "QPushButton { background-color: #3b2806; color: #fbbf24; border: 1px solid #f59e0b; "
                "border-radius: 12px; font-size: 10px; font-weight: bold; padding: 0; } "
                "QPushButton:hover { background-color: #543a0a; color: #ffffff; }"
            )
        else:
            btn.setText("⏸")
            btn.setStyleSheet(
                "QPushButton { background-color: #12291c; color: #86efac; border: 1px solid #16a34a; "
                "border-radius: 12px; font-size: 10px; font-weight: bold; padding: 0; } "
                "QPushButton:hover { background-color: #1a3d29; color: #ffffff; border-color: #00e676; }"
            )

    def set_layer_live(self, cue: Cue, duration_sec: float = 0.0, preserve_timing: bool = False) -> None:
        bar = self._layer_labels.get(cue.layer)
        if bar is not None:
            bar.set_live(cue, duration_sec=duration_sec, preserve_timing=preserve_timing)
        btn_pp = self._play_pause_buttons.get(cue.layer)
        if btn_pp is not None:
            is_playable = cue.media_type in (MediaType.AUDIO, MediaType.VIDEO)
            btn_pp.setVisible(is_playable)
            if not preserve_timing:
                self._style_play_pause_btn(btn_pp, paused=False)

    def set_layer_progress(
        self,
        layer: int,
        pos_sec: float,
        start_sec: Optional[float] = None,
        end_sec: Optional[float] = None,
        is_looping_inf: Optional[bool] = None,
    ) -> None:
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_progress(
                pos_sec, start_sec=start_sec, end_sec=end_sec, is_looping_inf=is_looping_inf
            )

    def set_layer_phase_progress(self, layer: int, cue: Cue, phase: str, elapsed: float, total: float) -> None:
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_phase_progress(cue, phase, elapsed, total)
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            btn_pp.setVisible(False)

    def set_layer_paused(self, layer: int, paused: bool) -> None:
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.set_paused(paused)
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            self._style_play_pause_btn(btn_pp, paused=paused)

    def reset_layer(self, layer: int) -> None:
        bar = self._layer_labels.get(layer)
        if bar is not None:
            bar.reset()
        btn_pp = self._play_pause_buttons.get(layer)
        if btn_pp is not None:
            btn_pp.setVisible(False)
            self._style_play_pause_btn(btn_pp, paused=False)

    def reset_all_layers(self) -> None:
        # Display Layers top-to-bottom in visual Z-order (Overlay L3 on top -> Sfondo L1 on bottom)
        for layer in (3, 2, 1):
            self.reset_layer(layer)

    def set_layer0_label(self, file_path: Optional[str]) -> None:
        name = Path(file_path).name if file_path else "Logo BlindCue (Predefinito)"
        self.lbl_tappo_info.setText(f"Tappo (L0): {name}")
