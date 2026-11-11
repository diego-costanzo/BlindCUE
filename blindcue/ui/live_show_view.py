"""Dedicated distraction-free LIVE Show Mode view centered on the extended Cue Sequence List."""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.cue import Cue, CueStatus, FollowMode, MediaType
from ui.cue_table import (
    ROLE_CUE_COLOR,
    ROLE_FOLLOW_MODE,
    ROLE_INCOMING_LINK,
    ROLE_PREV_COLOR,
    format_cue_ref,
    paint_cue_row_decorations,
)


class LiveCueRowDelegate(QStyledItemDelegate):
    """Paints left-rail link connectors and cue group colours onto Live Show table rows."""

    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        is_sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        if index.column() == 0:
            txt = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            fg = index.data(Qt.ItemDataRole.ForegroundRole)
            style = opt.widget.style() if opt.widget else QApplication.style()
            opt.text = ""
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)
            painter.save()
            painter.setFont(opt.font)
            painter.setPen(fg.color() if fg is not None else QColor("#e2e8f0"))
            painter.drawText(opt.rect.adjusted(18, 0, -2, 0), Qt.AlignmentFlag.AlignCenter, txt)
            painter.restore()
            return
        super().paint(painter, option, index)
        paint_cue_row_decorations(painter, option.rect, index, is_selected=is_sel)
from ui.live_status_panel import LiveStatusPanel, _fmt_mmss
from ui.theme import CLR_ACCENT, CLR_GO, CLR_LIVE, CLR_PREVIZ

_LINK_ICONS = {
    FollowMode.MANUAL.value: "⏹",
    FollowMode.AUTO_FOLLOW.value: "⤵",
    FollowMode.SIMULTANEOUS.value: "⇉",
}


def format_cue_timing_summary(cue: Cue, known_duration_sec: float = 0.0) -> str:
    """Return a compact, single-line Pre-Delay / Duration / Post-Delay / Link string."""
    parts: list[str] = []
    if cue.pre_delay > 0:
        parts.append(f"Pre +{cue.pre_delay:.1f}s")

    if cue.media_type == MediaType.IMAGE:
        if cue.hold_time <= 0:
            dur_str = "∞"
        elif cue.hold_time < 10.0:
            dur_str = f"{cue.hold_time:.1f}s"
        else:
            dur_str = _fmt_mmss(cue.hold_time)
    else:
        raw_dur = 0.0
        if cue.out_point is not None and cue.out_point > cue.in_point:
            raw_dur = cue.out_point - cue.in_point
        elif known_duration_sec > 0:
            raw_dur = max(0.0, known_duration_sec - cue.in_point)
        dur_str = _fmt_mmss(raw_dur) if raw_dur > 0 else "--:--"
        if cue.loop:
            dur_str = f"{dur_str} 🔁"
    parts.append(dur_str)

    if cue.post_delay > 0:
        parts.append(f"Post +{cue.post_delay:.1f}s")

    link_ico = _LINK_ICONS.get(cue.follow_mode, "⏹")
    return " · ".join(parts) + f"  {link_ico}"


class LiveShowPanel(QWidget):
    """Full-width live operation console with extended cue table, GO, Global Pause, and PANIC."""

    exit_live_mode_requested = Signal()
    go_requested = Signal()
    cue_row_clicked = Signal(int)
    cue_row_double_clicked = Signal(int)
    pause_all_toggled = Signal()
    panic_requested = Signal()
    break_loop_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_paused_all: bool = False
        self._updating_table: bool = False

        # Show duration stopwatch (monotonic drift-free tracking for shows & rehearsals)
        self._sw_armed: bool = True
        self._sw_running: bool = False
        self._sw_accum_sec: float = 0.0
        self._sw_started_mono: float = 0.0
        self._last_clock_text: str = ""
        self._last_sw_text: str = ""
        self._last_sw_state: str = ""

        self._build_ui()

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(250)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(8)

        # ── 1. Top Show Bar (Left controls | Dead-Center Clock | Right Show Stopwatch + PANIC) ──
        top_bar = QFrame()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet(
            "QFrame { background-color: #101620; border: 1px solid #1e293b; border-radius: 6px; }"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(8)

        left_box = QWidget()
        left_box.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.btn_back_project = QPushButton("← 🛠 Torna a Progetto  [F5]")
        self.btn_back_project.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_project.setFixedHeight(34)
        self.btn_back_project.setToolTip("Torna alla vista Progetto per modificare file, crop, fade o tempi (senza interrompere il Live)")
        self.btn_back_project.setStyleSheet(
            "QPushButton { background-color: #1c2636; color: #e2e8f0; border: 1px solid #3c4f6b; "
            "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; } "
            "QPushButton:hover { background-color: #27364d; border-color: #38bdf8; color: #ffffff; }"
        )
        self.btn_back_project.clicked.connect(self.exit_live_mode_requested)
        left_layout.addWidget(self.btn_back_project)

        self.lbl_show_badge = QLabel("● MODALITÀ LIVE (SHOW MODE)")
        self.lbl_show_badge.setFixedHeight(28)
        self.lbl_show_badge.setStyleSheet(
            "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
        )
        left_layout.addWidget(self.lbl_show_badge)
        left_layout.addStretch(1)

        # Dead-center real-time wall clock (balanced left/right stretch=1 containers)
        self.lbl_clock = QLabel("00:00:00")
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_clock.setStyleSheet(
            "QLabel { color: #e2e8f0; font-family: monospace; font-size: 20px; "
            "font-weight: bold; border: none; background: transparent; padding: 0px 10px; }"
        )

        right_box = QWidget()
        right_box.setStyleSheet("background: transparent;")
        right_layout = QHBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addStretch(1)

        # Show duration stopwatch (auto-starts on 1st GO or clickable anytime for rehearsals)
        self.btn_stopwatch = QPushButton("⏱  00:00:00")
        self.btn_stopwatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stopwatch.setFixedHeight(34)
        self.btn_stopwatch.setMinimumWidth(132)
        self.btn_stopwatch.clicked.connect(self.toggle_stopwatch)
        right_layout.addWidget(self.btn_stopwatch)

        self.btn_stopwatch_reset = QPushButton("↺")
        self.btn_stopwatch_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stopwatch_reset.setFixedSize(34, 34)
        self.btn_stopwatch_reset.setToolTip(
            "Azzera Cronometro Spettacolo e riarma l'avvio automatico al prossimo 1° GO"
        )
        self.btn_stopwatch_reset.setStyleSheet(
            "QPushButton { background-color: #16202e; color: #94a3b8; border: 1px solid #334155; "
            "border-radius: 5px; font-weight: bold; font-size: 15px; } "
            "QPushButton:hover { background-color: #253347; color: #f8fafc; border-color: #64748b; }"
        )
        self.btn_stopwatch_reset.clicked.connect(self.reset_stopwatch)
        right_layout.addWidget(self.btn_stopwatch_reset)
        right_layout.addSpacing(8)

        # Far away from bottom GO trigger: Crimson PANIC Stop button
        self.btn_panic = QPushButton("🚨  PANIC  —  STOP TOTALE   [ ESC ]")
        self.btn_panic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_panic.setFixedHeight(36)
        self.btn_panic.setMinimumWidth(252)
        self.btn_panic.setToolTip(
            "EMERGENZA (0ms): Taglia immediatamente Audio, Video e Immagini su tutti i layer. "
            "Mostra Nero assoluto se il Tappo è quello di calibrazione (o Tappo personalizzato se impostato)."
        )
        self.btn_panic.setStyleSheet(
            "QPushButton { background-color: #7f1d1d; color: #ffffff; border: 2px solid #ef4444; "
            "border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0px 14px; } "
            "QPushButton:hover { background-color: #dc2626; border-color: #fca5a5; } "
            "QPushButton:pressed { background-color: #991b1b; }"
        )
        self.btn_panic.clicked.connect(self.panic_requested)
        right_layout.addWidget(self.btn_panic)

        top_layout.addWidget(left_box, stretch=1)
        top_layout.addWidget(self.lbl_clock, stretch=0)
        top_layout.addWidget(right_box, stretch=1)
        root.addWidget(top_bar)

        # ── 2. Center Hero Area: Extended 6-Column Live Scaletta ──────────────
        self.live_table = QTableWidget(0, 6)
        self.live_table.setHorizontalHeaderLabels([
            "#", "Q", "Media / Cue", "Note di Regia", "Tempi · Sequenza", "Layer / Stato"
        ])
        self.live_table.verticalHeader().setVisible(False)
        self.live_table.verticalHeader().setDefaultSectionSize(34)
        self.live_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.live_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.live_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.live_table.setShowGrid(False)
        self.live_table.setWordWrap(False)
        self.live_table.setStyleSheet(
            "QTableWidget { background-color: #0b0f16; border: 1px solid #1e293b; border-radius: 6px; "
            "font-size: 13px; gridline-color: #161f2c; } "
            "QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid #131b26; } "
            "QHeaderView::section { background-color: #131a26; color: #94a3b8; font-weight: bold; "
            "font-size: 11px; padding: 6px; border: none; border-bottom: 1px solid #243144; }"
        )
        hdr = self.live_table.horizontalHeader()
        hdr.setHighlightSections(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.live_table.setColumnWidth(0, 56)
        self.live_table.setColumnWidth(1, 80)
        self.live_table.setColumnWidth(4, 290)
        self.live_table.setColumnWidth(5, 145)
        self.live_table.setItemDelegate(LiveCueRowDelegate(self.live_table))

        self.live_table.cellClicked.connect(self._on_table_clicked)
        self.live_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        root.addWidget(self.live_table, stretch=1)

        # Standby Info Banner + optional Break Section Loop shortcut
        standby_bar = QFrame()
        standby_bar.setFixedHeight(34)
        standby_bar.setStyleSheet(
            "QFrame { background-color: #111824; border: 1px solid #243044; border-radius: 5px; }"
        )
        sb_layout = QHBoxLayout(standby_bar)
        sb_layout.setContentsMargins(10, 2, 10, 2)
        sb_layout.setSpacing(10)

        self.lbl_standby_banner = QLabel("STANDBY: Nessuna cue pronta")
        self.lbl_standby_banner.setMinimumWidth(0)
        self.lbl_standby_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby_banner.setStyleSheet(
            f"QLabel {{ color: {CLR_PREVIZ}; font-size: 12px; font-weight: bold; border: none; }}"
        )
        sb_layout.addWidget(self.lbl_standby_banner, stretch=1)

        self.btn_break_loop = QPushButton("⏭ Esci da Loop Sezione")
        self.btn_break_loop.setVisible(False)
        self.btn_break_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_break_loop.setFixedHeight(24)
        self.btn_break_loop.setStyleSheet(
            "QPushButton { background-color: #78350f; color: #fef3c7; border: 1px solid #f59e0b; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 10px; } "
            "QPushButton:hover { background-color: #b45309; }"
        )
        self.btn_break_loop.clicked.connect(self.break_loop_requested)
        sb_layout.addWidget(self.btn_break_loop)
        root.addWidget(standby_bar)

        # ── 3. Bottom Transport & Live Output Dock ───────────────────────────
        dock = QHBoxLayout()
        dock.setSpacing(10)

        self.live_status = LiveStatusPanel(compact_live_mode=True)
        self.live_status.setMinimumHeight(140)
        dock.addWidget(self.live_status, stretch=54)

        transport_frame = QFrame()
        transport_frame.setStyleSheet(
            "QFrame { background-color: #0e141e; border: 1px solid #1e293b; border-radius: 6px; }"
        )
        tr_layout = QVBoxLayout(transport_frame)
        tr_layout.setContentsMargins(10, 8, 10, 8)
        tr_layout.setSpacing(8)

        self.btn_pause_all = QPushButton("⏸  PAUSA TUTTO")
        self.btn_pause_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_all.setFixedHeight(44)
        self.btn_pause_all.setToolTip(
            "Congela tutti i layer LIVE (Audio, Video, Pre-Delay, Post-Delay e Immagini temporizzate) "
            "per ripartire poi dallo stesso istante"
        )
        self.btn_pause_all.clicked.connect(self.pause_all_toggled)
        self._apply_pause_btn_style(paused=False)
        tr_layout.addWidget(self.btn_pause_all)

        self.btn_go = QPushButton("▶   GO  —  PROSSIMA CUE   [ SPAZIO ]")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setMinimumHeight(64)
        self.btn_go.setFont(QFont("sans-serif", 17, QFont.Weight.Bold))
        self.btn_go.setStyleSheet(
            f"QPushButton {{ background-color: {CLR_GO}; color: #04130a; border: none; "
            f"border-radius: 6px; font-size: 17px; font-weight: bold; padding: 6px 12px; }} "
            f"QPushButton:hover {{ background-color: #69f0ae; }} "
            f"QPushButton:pressed {{ background-color: #00c853; }}"
        )
        self.btn_go.clicked.connect(self.go_requested)
        tr_layout.addWidget(self.btn_go, stretch=1)

        dock.addWidget(transport_frame, stretch=46)
        root.addLayout(dock)

    def stopwatch_elapsed_sec(self) -> float:
        """Return total elapsed seconds recorded by the Show Duration Stopwatch."""
        if self._sw_running:
            return self._sw_accum_sec + max(0.0, time.monotonic() - self._sw_started_mono)
        return self._sw_accum_sec

    def notify_first_go(self) -> None:
        """Auto-start the show duration stopwatch on the very first GO if still armed."""
        if self._sw_armed and not self._sw_running:
            self._sw_armed = False
            self._sw_running = True
            self._sw_started_mono = time.monotonic()
            self._refresh_stopwatch_ui()

    def toggle_stopwatch(self) -> None:
        """Start, pause, or resume the Show Duration Stopwatch (manual/rehearsal control)."""
        now = time.monotonic()
        if self._sw_running:
            self._sw_accum_sec += max(0.0, now - self._sw_started_mono)
            self._sw_running = False
            self._sw_armed = False
        else:
            self._sw_armed = False
            self._sw_running = True
            self._sw_started_mono = now
        self._refresh_stopwatch_ui()

    def reset_stopwatch(self) -> None:
        """Reset the Show Duration Stopwatch to 00:00:00 and re-arm it for the next 1st GO."""
        self._sw_running = False
        self._sw_accum_sec = 0.0
        self._sw_started_mono = 0.0
        self._sw_armed = True
        self._refresh_stopwatch_ui()

    def _refresh_stopwatch_ui(self) -> None:
        """Update Show Duration Stopwatch pill text, styling, and contextual tooltip cleanly."""
        total = int(self.stopwatch_elapsed_sec())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        clock_str = f"{h:02d}:{m:02d}:{s:02d}"

        if self._sw_running:
            text = f"⏱  {clock_str}"
            state = "running"
        elif not self._sw_armed:
            text = f"⏸  {clock_str}"
            state = "paused"
        else:
            text = f"⏱  {clock_str}"
            state = "armed"

        if text != self._last_sw_text:
            self.btn_stopwatch.setText(text)
            self._last_sw_text = text

        if state != self._last_sw_state:
            self._last_sw_state = state
            if state == "running":
                self.btn_stopwatch.setStyleSheet(
                    "QPushButton { background-color: #0b2920; color: #6ee7b7; border: 1px solid #10b981; "
                    "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                    "QPushButton:hover { background-color: #113b2e; border-color: #34d399; color: #ffffff; }"
                )
                self.btn_stopwatch.setToolTip(
                    "Cronometro Spettacolo in corso (avvio auto al 1° GO o manuale) — Clicca per PAUSA (non ferma i media)"
                )
            elif state == "paused":
                self.btn_stopwatch.setStyleSheet(
                    "QPushButton { background-color: #2b2109; color: #fcd34d; border: 1px solid #d97706; "
                    "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                    "QPushButton:hover { background-color: #3d2f0e; border-color: #fbbf24; color: #ffffff; }"
                )
                self.btn_stopwatch.setToolTip(
                    "Cronometro Spettacolo in PAUSA — Clicca per RIPRENDERE o usa ↺ per azzerare e riarmare"
                )
            else:
                self.btn_stopwatch.setStyleSheet(
                    "QPushButton { background-color: #151e2c; color: #94a3b8; border: 1px solid #334155; "
                    "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                    "QPushButton:hover { background-color: #1e293b; border-color: #38bdf8; color: #f8fafc; }"
                )
                self.btn_stopwatch.setToolTip(
                    "Durata Spettacolo (Cronometro): parte in automatico al 1° GO oppure clicca qui ora per avviare nelle filate/prove"
                )

    def _update_clock(self) -> None:
        now_txt = QDateTime.currentDateTime().toString("HH:mm:ss")
        if now_txt != self._last_clock_text:
            self._last_clock_text = now_txt
            self.lbl_clock.setText(now_txt)
        self._refresh_stopwatch_ui()

    def _on_table_clicked(self, row: int, _col: int) -> None:
        if not self._updating_table and row >= 0:
            self.cue_row_clicked.emit(row)

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        if row >= 0:
            self.cue_row_double_clicked.emit(row)

    def _apply_pause_btn_style(self, *, paused: bool) -> None:
        if paused:
            self.btn_pause_all.setText("▶  RIPRENDI TUTTO  [IN PAUSA]")
            self.btn_pause_all.setStyleSheet(
                "QPushButton { background-color: #f59e0b; color: #000000; border: 2px solid #fef3c7; "
                "border-radius: 5px; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                "QPushButton:hover { background-color: #fbbf24; }"
            )
            self.lbl_show_badge.setText("⏸ SHOW IN PAUSA")
            self.lbl_show_badge.setStyleSheet(
                "QLabel { background-color: #78350f; color: #fde68a; border: 1px solid #f59e0b; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
            )
        else:
            self.btn_pause_all.setText("⏸  PAUSA TUTTO")
            self.btn_pause_all.setStyleSheet(
                "QPushButton { background-color: #3f2806; color: #fbbf24; border: 1px solid #d97706; "
                "border-radius: 5px; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                "QPushButton:hover { background-color: #5c3b09; color: #ffffff; }"
            )
            self.lbl_show_badge.setText("● MODALITÀ LIVE (SHOW MODE)")
            self.lbl_show_badge.setStyleSheet(
                "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
            )

    def set_global_paused(self, paused: bool) -> None:
        self._is_paused_all = paused
        self._apply_pause_btn_style(paused=paused)

    def sync_cues(
        self,
        cues: list[Cue],
        standby_row: int,
        known_durations: dict[str, float],
        phase_tags: Optional[dict[int, str]] = None,
        show_break_loop: bool = False,
    ) -> None:
        """Refresh the extended Live Scaletta table, standby banner, and GO target label."""
        self._updating_table = True
        try:
            self.live_table.setRowCount(len(cues))
            phases = phase_tags or {}
            bold_font = QFont("sans-serif", 12, QFont.Weight.Bold)
            mono_font = QFont("monospace", 10)

            for r, cue in enumerate(cues):
                is_live = (cue.status == CueStatus.LIVE)
                is_standby = (r == standby_row and not is_live)
                phase_txt = phases.get(cue.cue_id, "")
                is_waiting = bool(phase_txt)

                if is_live:
                    row_bg = QColor("#092919")
                    fg_main = QColor(CLR_LIVE)
                elif is_waiting:
                    row_bg = QColor("#0e2136")
                    fg_main = QColor("#7dd3fc")
                elif is_standby:
                    row_bg = QColor("#261a08")
                    fg_main = QColor(CLR_PREVIZ)
                else:
                    row_bg = QColor("#0d121a" if r % 2 == 0 else "#101620")
                    fg_main = QColor("#e2e8f0")

                # Col 0: #
                it_num = QTableWidgetItem(f"{r + 1}")
                it_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Col 1: Q
                q_str = (cue.q_label or "").strip() or "—"
                it_q = QTableWidgetItem(q_str)
                it_q.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if q_str != "—":
                    it_q.setForeground(QColor(CLR_ACCENT))
                    it_q.setFont(bold_font)
                # Col 2: Media badge text + name
                short_type = {"VIDEO": "VID", "AUDIO": "AUD", "IMAGE": "IMG"}.get(cue.media_type.value, "CUE")
                sec_tag = f"  [{len(cue.sections)} sez.]" if cue.sections else ""
                it_name = QTableWidgetItem(f"[{short_type}]  {cue.name}{sec_tag}")
                if is_live or is_standby or is_waiting:
                    it_name.setFont(bold_font)
                # Col 3: Regia notes directly readable!
                it_notes = QTableWidgetItem(cue.notes or "—")
                # Col 4: Timing & Link summary
                dur_hint = known_durations.get(cue.file_path, 0.0)
                it_timing = QTableWidgetItem(format_cue_timing_summary(cue, dur_hint))
                it_timing.setFont(mono_font)
                it_timing.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Col 5: Layer + Status / Phase
                if phase_txt:
                    st_str = f"L{cue.layer} • {phase_txt}"
                elif is_live:
                    st_str = f"L{cue.layer} • LIVE"
                elif is_standby:
                    st_str = f"L{cue.layer} • STANDBY"
                else:
                    st_str = f"L{cue.layer}"
                it_state = QTableWidgetItem(st_str)
                it_state.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_state.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))

                items = (it_num, it_q, it_name, it_notes, it_timing, it_state)
                cue_color = getattr(cue, "color", "") or ""
                prev_color = (getattr(cues[r - 1], "color", "") or "") if r > 0 else ""
                incoming_link = cues[r - 1].follow_mode if r > 0 else ""
                for c_idx, it in enumerate(items):
                    it.setBackground(row_bg)
                    it.setData(ROLE_CUE_COLOR, cue_color)
                    it.setData(ROLE_PREV_COLOR, prev_color)
                    it.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
                    it.setData(ROLE_INCOMING_LINK, incoming_link)
                    if c_idx == 1 and q_str != "—":
                        pass
                    elif c_idx == 3:
                        it.setForeground(QColor("#cbd5e1" if cue.notes else "#475569"))
                    elif c_idx == 4:
                        it.setForeground(QColor("#93c5fd" if cue.follow_mode != FollowMode.MANUAL.value else "#94a3b8"))
                    else:
                        it.setForeground(fg_main)
                    self.live_table.setItem(r, c_idx, it)

            if 0 <= standby_row < len(cues):
                self.live_table.selectRow(standby_row)
                sb_cue = cues[standby_row]
                ref = format_cue_ref(standby_row, sb_cue)
                notes_part = f"   │   Note: {sb_cue.notes}" if sb_cue.notes else ""
                pre_part = f"   │   Pre +{sb_cue.pre_delay:.1f}s" if sb_cue.pre_delay > 0 else ""
                self.lbl_standby_banner.setText(
                    f"PROSSIMA (STANDBY):  {ref}  '{sb_cue.name}'  [L{sb_cue.layer}]{pre_part}{notes_part}"
                )
                self.btn_go.setText(f"▶   GO:  {ref} '{sb_cue.name}'   [ SPAZIO ]")
            else:
                self.live_table.clearSelection()
                self.lbl_standby_banner.setText("STANDBY: Nessuna cue pronta in scaletta")
                self.btn_go.setText("▶   GO  —  PROSSIMA CUE   [ SPAZIO ]")

            self.btn_break_loop.setVisible(show_break_loop)
        finally:
            self._updating_table = False
