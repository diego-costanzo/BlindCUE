"""Dedicated distraction-free LIVE Show Mode view centered on the extended Cue Sequence List."""

from __future__ import annotations

import re
import time
from typing import Any

from PySide6.QtCore import QDateTime, QRect, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
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

from engine.action_cues import action_duration
from models.cue import Cue, CueStatus, FollowMode, MediaType, normalize_output_target
from ui.cue_table import (
    ROLE_CHILD_COUNT,
    ROLE_CUE_COLOR,
    ROLE_DURATION_TXT,
    ROLE_FOLLOW_MODE,
    ROLE_GROUP_COLLAPSED,
    ROLE_GROUP_MODE,
    ROLE_HAS_NOTES,
    ROLE_INCOMING_LINK,
    ROLE_IS_GROUP,
    ROLE_IS_LAST_CHILD,
    ROLE_IS_LIVE,
    ROLE_IS_STANDBY,
    ROLE_LAYER,
    ROLE_LAYER_CONFLICT,
    ROLE_LIVE_FRACTION,
    ROLE_LIVE_TIME,
    ROLE_LIVE_WARN,
    ROLE_LOOP,
    ROLE_MEDIA_TYPE,
    ROLE_NOTES_TXT,
    ROLE_OUTPUT_TARGET,
    ROLE_PARENT_ID,
    ROLE_PHASE_TXT,
    ROLE_PAUSED,
    ROLE_PLAYED,
    ROLE_POST_DELAY,
    ROLE_PRE_DELAY,
    ROLE_PREV_COLOR,
    ROLE_SECTION_COUNT,
    ROLE_STATUS_CLR,
    ROLE_STATUS_TXT,
    ROLE_TIMELINE_COMPOSED,
    format_cue_ref,
    get_group_mode_pill,
    get_media_badge,
    paint_cue_row_decorations,
    paint_live_progress,
)
from ui.hold_button import ElidedButton, HoldProgressButton
from ui.master_volume import MasterVolume
from ui.mode_tabs import ModeTabs
from ui.now_playing import NowPlayingPanel
from ui.pin_bar import PinBar
from ui.live_status_panel import LiveStatusPanel, _fmt_mmss
from ui.theme import CLR_GO, get_active_theme

from i18n import tr

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

    if cue.media_type == MediaType.GROUP:
        mode_tag = {
            "SIMULTANEOUS": "Simultaneo",
            "SEQUENCE": "Sequenziale",
            "STEP": "Passo-Passo",
            "RANDOM": "Random",
            "LOOP": "Loop Scena",
        }.get(getattr(cue, "group_mode", "STEP"), getattr(cue, "group_mode", "STEP"))
        parts.append(f"📁 {mode_tag}")
    elif cue.media_type == MediaType.IMAGE:
        if cue.hold_time <= 0:
            dur_str = "∞"
        elif cue.hold_time < 10.0:
            dur_str = f"{cue.hold_time:.1f}s"
        else:
            dur_str = _fmt_mmss(cue.hold_time)
        parts.append(dur_str)
    elif cue.media_type == MediaType.ACTION:
        act_d = action_duration(cue.action_spec)
        parts.append(f"⚡ {act_d:.1f}s" if act_d > 0 else "⚡")
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


DOUBLE_CLICK_FIRES_KEY = "live/double_click_fires"


def live_double_click_fires() -> bool:
    """True when a double-click on the live list should start the cue at once."""
    value = QSettings("BlindCue", "BlindCue").value(DOUBLE_CLICK_FIRES_KEY, False)
    return str(value).lower() in ("1", "true", "yes")


class LiveCueTable(QTableWidget):
    """Specialized Live Show table with direct keyboard navigation, context actions, and click signals."""

    go_requested = Signal()
    force_go_requested = Signal()
    panic_requested = Signal()
    standby_selected = Signal(int)
    fire_row_requested = Signal(int)
    group_collapse_toggled = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the high-contrast live rundown table."""
        super().__init__(0, 6, parent)
        self.setAccessibleName("Scaletta Regia LIVE Show")
        self.setAccessibleDescription("Elenco scaletta ad alto contrasto per il live. Frecce Su e Giù per standby, Spazio per il GO, Esc due volte per il Panic.")

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Keyboard shortcuts on the live list (GO, arrows). ESC propagates to MainWindow double-ESC guard."""
        key = event.key()
        if key == Qt.Key.Key_Space:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.force_go_requested.emit()
            else:
                self.go_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            curr = self.currentRow()
            if curr >= 0:
                self.standby_selected.emit(curr)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Right-click menu on a live cue (go, stop, jump, edit notes)."""
        row = self.rowAt(event.pos().y())
        if row < 0 or row >= self.rowCount():
            return
        self.selectRow(row)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #0f172a; color: #e2e8f0; border: 1px solid #334155; padding: 4px; } "
            "QMenu::item { padding: 6px 18px; border-radius: 3px; font-weight: bold; font-size: 11px; } "
            "QMenu::item:selected { background-color: #1e293b; color: #38bdf8; }"
        )
        # The harmless choice comes first: a stray tap on a touchpad must not
        # start a cue, so "start now" sits last, after a separator.
        act_sb = menu.addAction("🎯 Imposta come Prossima Cue (Standby)")
        act_sb.triggered.connect(lambda: self.standby_selected.emit(row))

        it_num = self.item(row, 0)
        if it_num and it_num.data(ROLE_IS_GROUP):
            is_col = bool(it_num.data(ROLE_GROUP_COLLAPSED))
            act_toggle = menu.addAction("▼ Espandi Gruppo" if is_col else "▶ Collassa Gruppo")
            act_toggle.triggered.connect(lambda: self.group_collapse_toggled.emit(row))

        menu.addSeparator()
        act_go = menu.addAction("▶ Fai partire subito questa Cue (GO Forzato)")
        act_go.triggered.connect(lambda: self.fire_row_requested.emit(row))

        menu.exec(event.globalPos())


class LiveCueRowDelegate(QStyledItemDelegate):
    """High-contrast, distraction-free delegate for Live Show table with custom pills, tree branches, and timing."""

    _MEDIA_BADGE = {
        "VIDEO": ("VID", QColor("#0369a1"), QColor("#ffffff")),
        "AUDIO": ("AUD", QColor("#0f766e"), QColor("#f0fdfa")),
        "IMAGE": ("IMG", QColor("#b45309"), QColor("#ffffff")),
        "GROUP": ("GRP", QColor("#6d28d9"), QColor("#ede9fe")),
    }

    _URGENT_NOTES_KEYWORDS = (
        "ATTENZIONE", "PERICOLO", "BUIO TOTALE", "STOP IMMEDIATO", "EMERGENZA", "AVVISO", "ALLARME"
    )
    # Whole words (a stem may take an ending), in Italian, Polish and English,
    # so that "stop" does not light up "stopniowo" and "wait" not "awaiting".
    _URGENT_NOTES_RE = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in _URGENT_NOTES_KEYWORDS)
        + r"|UWAGA|(?:PO)?CZEKAJ\w*|STOP|CIEMNO(?:Ś\w*)?|NIEBEZPIECZ\w*|ALARM|AWARI\w*|PILN[EI]E?"
        + r"|WARNING|DANGER|WAIT|BLACKOUT|EMERGENCY|ALERT|URGENT|CAUTION)\b"
    )

    @classmethod
    def is_urgent_note(cls, text: str) -> bool:
        """A director's note to highlight in the LIVE list (danger, wait, blackout...)."""
        return bool(text) and cls._URGENT_NOTES_RE.search(text.upper()) is not None

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        """Attach the live-state colour computed by :meth:`paint`."""
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        """Draw a cue in the live view with LIVE/STANDBY colouring."""
        col = index.column()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else QApplication.style()

        is_sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_live = bool(index.data(ROLE_IS_LIVE))
        is_standby = bool(index.data(ROLE_IS_STANDBY))
        is_group = bool(index.data(ROLE_IS_GROUP))
        is_collapsed = bool(index.data(ROLE_GROUP_COLLAPSED))
        phase_txt = str(index.data(ROLE_PHASE_TXT) or "")
        is_waiting = bool(phase_txt)
        is_mono = get_active_theme().is_monochrome
        # Started earlier in this run of the show: ✓ and a dimmer name (still readable).
        is_played = bool(index.data(ROLE_PLAYED)) and not (is_live or is_standby or is_waiting)

        # ── Col 0: # & Group Chevron & Link Rail ──────────────────────────────
        if col == 0:
            raw_num = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            if is_played:
                raw_num = f"✓{raw_num}"
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if is_mono:
                pen_clr = QColor("#ffffff") if is_live else (QColor("#d4d4d8") if is_standby else QColor("#888891"))
            else:
                pen_clr = QColor("#4ade80") if is_live else (QColor("#fcd34d") if is_standby else QColor("#94a3b8"))

            if is_group:
                arrow_sym = "▶" if is_collapsed else "▼"
                painter.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
                painter.setPen(QColor("#ffffff" if is_mono else "#38bdf8"))
                painter.drawText(
                    opt.rect.adjusted(6, 0, -28, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    arrow_sym,
                )
                painter.setFont(QFont("monospace", 10, QFont.Weight.Bold))
                painter.setPen(pen_clr)
                painter.drawText(
                    opt.rect.adjusted(20, 0, -2, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    raw_num,
                )
            else:
                painter.setFont(
                    QFont("monospace", 10, QFont.Weight.Bold if (is_live or is_standby) else QFont.Weight.Normal)
                )
                painter.setPen(pen_clr)
                painter.drawText(
                    opt.rect.adjusted(20, 0, -2, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    raw_num,
                )
            painter.restore()
            return

        # ── Col 1: Q Script Callout ───────────────────────────────────────────
        if col == 1:
            raw_q = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
            if raw_q == "—":
                raw_q = ""
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect

            if raw_q:
                font = QFont(opt.font)
                font.setPointSize(9)
                font.setBold(True)
                painter.setFont(font)
                fm = painter.fontMetrics()
                pw = max(34, fm.horizontalAdvance(raw_q) + 12)
                ph = 20
                px = rect.left() + (rect.width() - pw) // 2
                py = rect.top() + (rect.height() - ph) // 2
                pill_rect = QRect(px, py, pw, ph)

                q_border = QColor("#525363") if is_mono else QColor("#0284c7")
                q_bg = QColor("#22232a") if is_mono else QColor("#082f49")
                q_fg = QColor("#ffffff") if is_mono else QColor("#38bdf8")
                painter.setPen(QPen(q_border, 1))
                painter.setBrush(q_bg)
                painter.drawRoundedRect(pill_rect, 4, 4)
                painter.setPen(q_fg)
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, raw_q)
            else:
                painter.setFont(opt.font)
                painter.setPen(QColor("#3f404d") if is_mono else QColor("#334155"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
            painter.restore()
            return

        # ── Col 2: Media / Titolo Cue ─────────────────────────────────────────
        if col == 2:
            name_text = str(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole) or "")
            media_type = str(index.data(ROLE_MEDIA_TYPE) or "")
            parent_id = index.data(ROLE_PARENT_ID)
            child_count = int(index.data(ROLE_CHILD_COUNT) or 0)
            group_mode = str(index.data(ROLE_GROUP_MODE) or "STEP")
            is_last_child = bool(index.data(ROLE_IS_LAST_CHILD))
            sec_count = int(index.data(ROLE_SECTION_COUNT) or 0)
            is_loop = bool(index.data(ROLE_LOOP))

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(6, 3, -6, -3)
            left_x = rect.left()

            # Indent child cue with branch connector
            if parent_id is not None:
                branch_sym = "└── " if is_last_child else "├── "
                painter.setFont(QFont("monospace", 10))
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(
                    QRect(left_x, rect.top(), 24, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    branch_sym,
                )
                left_x += 20

            # Media badge pill
            badge_info = get_media_badge(media_type, is_mono)
            if badge_info:
                tag_txt, bg_clr, fg_clr, border_clr = badge_info
                pill_w, pill_h = (34, 18) if is_group else (30, 18)
                pill_y = rect.top() + (rect.height() - pill_h) // 2
                pill_rect = QRect(left_x, pill_y, pill_w, pill_h)
                if border_clr is not None:
                    painter.setPen(QPen(border_clr, 1))
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(bg_clr)
                painter.drawRoundedRect(pill_rect, 3, 3)

                badge_font = QFont(opt.font)
                badge_font.setPointSize(8)
                badge_font.setBold(True)
                painter.setFont(badge_font)
                painter.setPen(fg_clr)
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, tag_txt)
                left_x += pill_w + 8

            right_x = rect.right()
            tag_font = QFont(opt.font)
            tag_font.setPointSize(8)
            tag_font.setBold(True)

            # Right badges
            if is_group:
                gm_info = get_group_mode_pill(group_mode, is_mono)
                if gm_info:
                    gm_txt, gm_bg, gm_fg, gm_border_spec = gm_info
                    gm_border = gm_border_spec or gm_fg
                    painter.setFont(tag_font)
                    fm_gm = painter.fontMetrics()
                    gm_w = fm_gm.horizontalAdvance(gm_txt) + 12
                    gm_rect = QRect(right_x - gm_w, rect.top() + (rect.height() - 18) // 2, gm_w, 18)
                    painter.setPen(QPen(gm_border, 1))
                    painter.setBrush(gm_bg)
                    painter.drawRoundedRect(gm_rect, 3, 3)
                    painter.setPen(gm_fg)
                    painter.drawText(gm_rect, Qt.AlignmentFlag.AlignCenter, gm_txt)
                    right_x -= gm_w + 6

                if child_count > 0:
                    cc_txt = f"{child_count} Cue"
                    painter.setFont(tag_font)
                    fm_cc = painter.fontMetrics()
                    cc_w = fm_cc.horizontalAdvance(cc_txt) + 10
                    cc_rect = QRect(right_x - cc_w, rect.top() + (rect.height() - 18) // 2, cc_w, 18)
                    painter.setPen(QPen(QColor("#3f404d") if is_mono else QColor("#334155"), 1))
                    painter.setBrush(QColor("#18191f") if is_mono else QColor("#0f172a"))
                    painter.drawRoundedRect(cc_rect, 3, 3)
                    painter.setPen(QColor("#a1a1aa") if is_mono else QColor("#94a3b8"))
                    painter.drawText(cc_rect, Qt.AlignmentFlag.AlignCenter, cc_txt)
                    right_x -= cc_w + 6
            else:
                if is_loop:
                    loop_txt = "🔁 LOOP"
                    painter.setFont(tag_font)
                    fm_lp = painter.fontMetrics()
                    lp_w = fm_lp.horizontalAdvance(loop_txt) + 10
                    lp_rect = QRect(right_x - lp_w, rect.top() + (rect.height() - 18) // 2, lp_w, 18)
                    lp_border = QColor("#525363") if is_mono else QColor("#d97706")
                    lp_bg = QColor("#22232a") if is_mono else QColor("#451a03")
                    lp_fg = QColor("#f4f4f5") if is_mono else QColor("#fbbf24")
                    painter.setPen(QPen(lp_border, 1))
                    painter.setBrush(lp_bg)
                    painter.drawRoundedRect(lp_rect, 3, 3)
                    painter.setPen(lp_fg)
                    painter.drawText(lp_rect, Qt.AlignmentFlag.AlignCenter, loop_txt)
                    right_x -= lp_w + 6

                if sec_count > 0:
                    sec_txt = f"[{sec_count} sez.]"
                    painter.setFont(tag_font)
                    fm_sec = painter.fontMetrics()
                    sec_w = fm_sec.horizontalAdvance(sec_txt) + 8
                    sec_rect = QRect(right_x - sec_w, rect.top() + (rect.height() - 18) // 2, sec_w, 18)
                    painter.setPen(QPen(QColor("#3f404d") if is_mono else QColor("#334155"), 1))
                    painter.setBrush(QColor("#1e1f26") if is_mono else QColor("#1e293b"))
                    painter.drawRoundedRect(sec_rect, 3, 3)
                    painter.setPen(QColor("#a1a1aa") if is_mono else QColor("#94a3b8"))
                    painter.drawText(sec_rect, Qt.AlignmentFlag.AlignCenter, sec_txt)
                    right_x -= sec_w + 6

            avail_w = max(24, right_x - left_x - 4)
            name_rect = QRect(left_x, rect.top(), avail_w, rect.height())
            name_font = QFont(opt.font)
            name_font.setPointSize(11)
            if is_live or is_standby or is_group or is_waiting:
                name_font.setBold(True)
            painter.setFont(name_font)

            if is_mono:
                if is_live:
                    disp_name = name_text
                    name_clr = QColor("#ffffff")
                elif is_standby:
                    disp_name = name_text
                    name_clr = QColor("#d4d4d8")
                elif is_waiting:
                    disp_name = name_text
                    name_clr = QColor("#d4d4d8")
                elif is_group:
                    disp_name = name_text[2:].strip() if name_text.startswith("📁") else name_text
                    name_clr = QColor("#a1a1aa" if is_played else "#f4f4f5")
                else:
                    disp_name = name_text
                    name_clr = QColor("#8e8e96" if is_played else "#a1a1aa")
            else:
                if is_group:
                    disp_name = name_text[2:].strip() if name_text.startswith("📁") else name_text
                    name_clr = QColor("#a78bca" if is_played else "#c084fc")
                elif is_live:
                    disp_name = name_text
                    name_clr = QColor("#4ade80")
                elif is_standby:
                    disp_name = name_text
                    name_clr = QColor("#fef08a")
                elif is_waiting:
                    disp_name = name_text
                    name_clr = QColor("#7dd3fc")
                else:
                    disp_name = name_text
                    name_clr = QColor("#94a3b8" if is_played else "#f8fafc")

            elided_name = painter.fontMetrics().elidedText(disp_name, Qt.TextElideMode.ElideRight, avail_w)
            painter.setPen(name_clr)
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_name)
            painter.restore()
            return

        # ── Col 3: Note di Regia ──────────────────────────────────────────────
        if col == 3:
            notes_text = str(index.data(ROLE_NOTES_TXT) or "").strip()
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(6, 3, -6, -3)

            if notes_text:
                is_urgent = self.is_urgent_note(notes_text)

                if is_urgent:
                    u_border = QColor("#a1a1aa") if is_mono else QColor("#d97706")
                    u_bg = QColor(40, 41, 51, 180) if is_mono else QColor(69, 26, 3, 160)
                    painter.setPen(QPen(u_border, 1))
                    painter.setBrush(u_bg)
                    painter.drawRoundedRect(rect, 4, 4)

                painter.setFont(QFont(opt.font.family(), 9))
                if is_mono:
                    ico_clr = QColor("#ffffff" if is_urgent else "#d4d4d8")
                else:
                    ico_clr = QColor("#f59e0b" if is_urgent else "#38bdf8")
                painter.setPen(ico_clr)
                painter.drawText(
                    QRect(rect.left() + 4, rect.top(), 20, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    "📝",
                )

                note_font = QFont(opt.font)
                note_font.setPointSize(9)
                if is_urgent:
                    note_font.setBold(True)
                painter.setFont(note_font)
                if is_mono:
                    note_clr = QColor("#ffffff" if is_urgent else "#a1a1aa")
                else:
                    note_clr = QColor("#fef3c7" if is_urgent else "#cbd5e1")
                painter.setPen(note_clr)
                avail_w = max(20, rect.width() - 28)
                elided = painter.fontMetrics().elidedText(notes_text, Qt.TextElideMode.ElideRight, avail_w)
                painter.drawText(
                    QRect(rect.left() + 26, rect.top(), avail_w, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    elided,
                )
            else:
                painter.setFont(opt.font)
                painter.setPen(QColor("#3f404d") if is_mono else QColor("#334155"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")

            painter.restore()
            return

        # ── Col 4: Tempi · Sequenza ───────────────────────────────────────────
        if col == 4:
            pre_delay = float(index.data(ROLE_PRE_DELAY) or 0.0)
            post_delay = float(index.data(ROLE_POST_DELAY) or 0.0)
            dur_str = str(index.data(ROLE_DURATION_TXT) or "--:--")
            follow_mode = str(index.data(ROLE_FOLLOW_MODE) or "MANUAL")

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(6, 3, -6, -3)

            tag_font = QFont(opt.font)
            tag_font.setPointSize(8)
            tag_font.setBold(True)
            painter.setFont(tag_font)

            if is_mono:
                if follow_mode == "AUTO_FOLLOW":
                    fm_txt, fm_bg, fm_border, fm_fg = "⤵ AUTO-GO", QColor("#1e1f26"), QColor("#d4d4d8"), QColor("#ffffff")
                    fm_w = 68
                elif follow_mode == "SIMULTANEOUS":
                    fm_txt, fm_bg, fm_border, fm_fg = "⇉ SIMULT", QColor("#22232a"), QColor("#525363"), QColor("#e4e4e7")
                    fm_w = 66
                else:
                    fm_txt, fm_bg, fm_border, fm_fg = "⏹ MANUALE", QColor("#18191f"), QColor("#33343d"), QColor("#888891")
                    fm_w = 70
            else:
                if follow_mode == "AUTO_FOLLOW":
                    fm_txt, fm_bg, fm_border, fm_fg = "⤵ AUTO-GO", QColor("#0c2638"), QColor("#38bdf8"), QColor("#7dd3fc")
                    fm_w = 68
                elif follow_mode == "SIMULTANEOUS":
                    fm_txt, fm_bg, fm_border, fm_fg = "⇉ SIMULT", QColor("#332006"), QColor("#f59e0b"), QColor("#fcd34d")
                    fm_w = 66
                else:
                    fm_txt, fm_bg, fm_border, fm_fg = "⏹ MANUALE", QColor("#131a26"), QColor("#243144"), QColor("#94a3b8")
                    fm_w = 70

            right_x = rect.right()
            # Only the exceptions get a pill (AUTO-GO, Simultaneous): a manual
            # cue is the normal case, and a pill on every row was just noise.
            if follow_mode in ("AUTO_FOLLOW", "SIMULTANEOUS"):
                fm_rect = QRect(right_x - fm_w, rect.top() + (rect.height() - 18) // 2, fm_w, 18)
                painter.setPen(QPen(fm_border, 1))
                painter.setBrush(fm_bg)
                painter.drawRoundedRect(fm_rect, 3, 3)
                painter.setPen(fm_fg)
                painter.drawText(fm_rect, Qt.AlignmentFlag.AlignCenter, fm_txt)

            # Left slot: Pre-Delay pill (if configured)
            if pre_delay > 0:
                pre_txt = f"Pre +{pre_delay:.1f}s"
                painter.setFont(tag_font)
                pw = min(56, painter.fontMetrics().horizontalAdvance(pre_txt) + 8)
                p_rect = QRect(rect.left(), rect.top() + (rect.height() - 18) // 2, pw, 18)
                p_border = QColor("#484956") if is_mono else QColor("#d97706")
                p_bg = QColor("#22232a") if is_mono else QColor("#332006")
                p_fg = QColor("#d4d4d8") if is_mono else QColor("#fbbf24")
                painter.setPen(QPen(p_border, 1))
                painter.setBrush(p_bg)
                painter.drawRoundedRect(p_rect, 3, 3)
                painter.setPen(p_fg)
                painter.drawText(p_rect, Qt.AlignmentFlag.AlignCenter, pre_txt)

            # Anchored duration slot (stable horizontal column across all rows)
            dur_x = rect.left() + 58
            dur_w = 54
            dur_rect = QRect(dur_x, rect.top(), dur_w, rect.height())
            dur_font = QFont("monospace", 10, QFont.Weight.Bold)
            painter.setFont(dur_font)
            # On air the slot shows what is left (redrawn by the 10 Hz clock).
            live_txt = str(index.data(ROLE_LIVE_TIME) or "")
            live_warn = bool(index.data(ROLE_LIVE_WARN))
            if live_txt:
                if live_warn:
                    painter.setPen(QColor("#ffffff") if is_mono else QColor("#fbbf24"))
                else:
                    painter.setPen(QColor("#ffffff") if is_mono else QColor("#4ade80"))
                # "-00:45∞" / "⏳-00:03" are a little wider than a length; the
                # ends-soon warning is a sign as well as a colour (W36).
                shown = f"⚠{live_txt}" if live_warn else live_txt
                painter.drawText(dur_rect.adjusted(-8, 0, 8, 0), Qt.AlignmentFlag.AlignCenter, shown)
            else:
                painter.setPen(QColor("#f4f4f5") if is_mono else QColor("#e2e8f0"))
                painter.drawText(dur_rect, Qt.AlignmentFlag.AlignCenter, dur_str)

            # Middle-right slot: Post-Delay pill (if configured)
            if post_delay > 0:
                post_txt = f"Post +{post_delay:.1f}s"
                painter.setFont(tag_font)
                post_w = min(60, painter.fontMetrics().horizontalAdvance(post_txt) + 8)
                post_x = dur_x + dur_w + 6
                post_rect = QRect(post_x, rect.top() + (rect.height() - 18) // 2, post_w, 18)
                post_border = QColor("#484956") if is_mono else QColor("#7c3aed")
                post_bg = QColor("#22232a") if is_mono else QColor("#2e1065")
                post_fg = QColor("#d4d4d8") if is_mono else QColor("#c084fc")
                painter.setPen(QPen(post_border, 1))
                painter.setBrush(post_bg)
                painter.drawRoundedRect(post_rect, 3, 3)
                painter.setPen(post_fg)
                painter.drawText(post_rect, Qt.AlignmentFlag.AlignCenter, post_txt)

            painter.restore()
            if live_txt:
                frac = index.data(ROLE_LIVE_FRACTION)
                paint_live_progress(painter, opt.rect, -1.0 if frac is None else float(frac), live_warn)
            return

        # ── Col 5: Layer · Stato LIVE ─────────────────────────────────────────
        if col == 5:
            layer = int(index.data(ROLE_LAYER) or 1)
            out_target = normalize_output_target(index.data(ROLE_OUTPUT_TARGET))
            layer_prefix = "B·" if out_target == "B" else ""
            phase_txt = str(index.data(ROLE_PHASE_TXT) or "")

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(6, 3, -6, -3)

            is_action = str(index.data(ROLE_MEDIA_TYPE) or "") == "ACTION"
            if is_group:
                layer_txt = "GRP"
            elif is_action:
                layer_txt = "ACT"  # an action cue has no layer of its own
            else:
                layer_txt = f"{layer_prefix}L{layer}"
            layer_font = QFont(opt.font)
            layer_font.setPointSize(8)
            layer_font.setBold(True)
            painter.setFont(layer_font)

            lw = 32 if is_group else (38 if layer_prefix else 26)
            lh = 18
            ly = rect.top() + (rect.height() - lh) // 2
            l_rect = QRect(rect.left(), ly, lw, lh)

            if is_mono:
                l_border = QColor("#484956") if is_group else QColor("#3f404d")
                l_bg = QColor("#1e1f26") if is_group else QColor("#22232a")
                l_fg = QColor("#f4f4f5") if is_group else QColor("#d4d4d8")
            else:
                if is_group:
                    l_border, l_bg, l_fg = QColor("#7c3aed"), QColor("#2e1065"), QColor("#c084fc")
                else:
                    l_border, l_bg, l_fg = QColor("#334155"), QColor("#1e293b"), QColor("#94a3b8")
            painter.setPen(QPen(l_border, 1))
            painter.setBrush(l_bg)
            painter.drawRoundedRect(l_rect, 3, 3)
            painter.setPen(l_fg)
            painter.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, layer_txt)

            tag_font = QFont(opt.font)
            tag_font.setPointSize(8.5)
            tag_font.setBold(True)
            painter.setFont(tag_font)

            if is_mono:
                if is_live:
                    st_label = "● LIVE"
                    st_bg = QColor("#2c2d36")
                    st_border = QColor("#ffffff")
                    st_fg = QColor("#ffffff")
                elif phase_txt:
                    st_label = f"⏳ {phase_txt}"
                    st_bg = QColor("#1e1f26")
                    st_border = QColor("#71717a")
                    st_fg = QColor("#a1a1aa")
                elif is_standby:
                    st_label = "▶ STANDBY"
                    st_bg = QColor("#22232a")
                    st_border = QColor("#a1a1aa")
                    st_fg = QColor("#e4e4e7")
                else:
                    st_label = "PRONTO"
                    st_bg = QColor("#16171b")
                    st_border = QColor("#27272a")
                    st_fg = QColor("#a1a1aa")
            else:
                if is_live:
                    st_label = "● LIVE"
                    st_bg = QColor("#064e3b")
                    st_border = QColor("#10b981")
                    st_fg = QColor("#4ade80")
                elif phase_txt:
                    st_label = f"⏳ {phase_txt}"
                    st_bg = QColor("#082f49")
                    st_border = QColor("#0284c7")
                    st_fg = QColor("#7dd3fc")
                elif is_standby:
                    st_label = "▶ STANDBY"
                    st_bg = QColor("#451a03")
                    st_border = QColor("#d97706")
                    st_fg = QColor("#fbbf24")
                else:
                    st_label = "PRONTO"
                    st_bg = QColor("#101722")
                    st_border = QColor("#1e293b")
                    st_fg = QColor("#94a3b8")

            if is_live and bool(index.data(ROLE_PAUSED)):
                # Paused is a state of its own, in a word and a sign (W35).
                st_label = "⏸ PAUSA"
                if is_mono:
                    st_bg, st_border, st_fg = QColor("#ffffff"), QColor("#ffffff"), QColor("#111111")
                else:
                    st_bg, st_border, st_fg = QColor("#451a03"), QColor("#f59e0b"), QColor("#fbbf24")

            fm_st = painter.fontMetrics()
            sw = max(72, fm_st.horizontalAdvance(st_label) + 12)
            sh = 20
            sx = rect.right() - sw
            sy = rect.top() + (rect.height() - sh) // 2
            s_rect = QRect(sx, sy, sw, sh)

            b_width = 2.0 if (is_mono and is_live) else (1.5 if (is_live or is_standby) else 1.0)
            if st_label != "PRONTO":  # ready is the normal case: no pill (the empty cell says it)
                painter.setPen(QPen(st_border, b_width))
                painter.setBrush(st_bg)
                painter.drawRoundedRect(s_rect, 4, 4)
                painter.setPen(st_fg)
                painter.drawText(s_rect, Qt.AlignmentFlag.AlignCenter, st_label)

            painter.restore()
            return


class LiveShowPanel(QWidget):
    """Full-width live operation console with extended cue table, GO, Global Pause, and PANIC."""

    exit_live_mode_requested = Signal()
    go_requested = Signal()
    force_go_requested = Signal()
    cue_row_clicked = Signal(int)
    cue_row_double_clicked = Signal(int)
    group_collapse_toggled = Signal(int)
    pause_all_toggled = Signal()
    panic_requested = Signal()
    fade_all_requested = Signal()
    break_loop_requested = Signal()
    double_click_armed = Signal(int)
    force_row_requested = Signal(int)
    undo_go_requested = Signal()
    readiness_review_requested = Signal()
    hold_auto_go_requested = Signal(int)   # cue_id whose Auto-GO should wait for a GO
    edit_cue_requested = Signal(int)       # rehearsal "✎": cue_id to fix in the drawer
    gate_ok_requested = Signal()           # the OK of a cue waiting for confirmation (1.9)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the live show panel with its drift-free show stopwatch."""
        super().__init__(parent)
        self._is_paused_all: bool = False
        self._updating_table: bool = False
        self._cue_id_to_row: dict[int, int] = {}
        # cue_id -> (short time text, played fraction, ends-soon warning); see set_live_times
        self._live_times: dict[int, tuple[str, float, bool]] = {}

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
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(8)

        left_box = QWidget()
        left_box.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

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
        # Replaced by the mode tabs: leaving the show is a 1.5 s hold, never one click.
        self.btn_back_project.setVisible(False)
        self.mode_tabs = ModeTabs()
        self.mode_tabs.set_live(True)
        self.mode_tabs.leave_show_requested.connect(self.exit_live_mode_requested)
        left_layout.addWidget(self.mode_tabs)

        # Entered the show with problems from the readiness check: "⚠ 2",
        # a click shows the same page again.
        self.btn_ready_warn = QPushButton("")
        self.btn_ready_warn.setFixedHeight(30)
        self.btn_ready_warn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Space stays GO
        self.btn_ready_warn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ready_warn.setStyleSheet(
            "QPushButton { background-color: #451a03; color: #fbbf24; border: 1px solid #d97706; "
            "border-radius: 4px; font-weight: bold; font-size: 13px; padding: 0px 10px; }"
        )
        self.btn_ready_warn.clicked.connect(self.readiness_review_requested)
        self.btn_ready_warn.setVisible(False)
        left_layout.addWidget(self.btn_ready_warn)

        self.lbl_show_badge = QLabel("● MODALITÀ LIVE (SHOW MODE)")
        self.lbl_show_badge.setFixedHeight(30)
        self.lbl_show_badge.setStyleSheet(
            "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
        )
        self.lbl_show_badge.setVisible(False)  # the tabs show the mode; the badge only shows a pause
        left_layout.addWidget(self.lbl_show_badge)
        left_layout.addStretch(1)

        # Dead-center real-time wall clock
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
        right_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        right_layout.addStretch(1)

        # Show duration stopwatch
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

        # Softer sibling of PANIC: every layer fades out together.
        self.btn_fade_all = QPushButton("🔉 DISSOLVI [⇧ESC]")
        self.btn_fade_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fade_all.setFixedHeight(34)
        self.btn_fade_all.setToolTip(
            "Dissolvenza totale: audio, video e immagini su tutti i layer sfumano insieme, "
            "poi si fermano. Il prossimo GO riparte dalla cue avviata a mano che è stata fermata."
        )
        self.btn_fade_all.setStyleSheet(
            "QPushButton { background-color: #78350f; color: #ffffff; border: 2px solid #f59e0b; "
            "border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0px 8px; } "
            "QPushButton:hover { background-color: #b45309; border-color: #fcd34d; } "
            "QPushButton:pressed { background-color: #92400e; }"
        )
        self.btn_fade_all.clicked.connect(self.fade_all_requested)
        # Master volume of the show, the same control as in the editor's top row.
        self.master_volume = MasterVolume()
        right_layout.addWidget(self.master_volume)
        right_layout.addWidget(self.btn_fade_all)

        # Far away from bottom GO trigger: Crimson PANIC Stop button
        # Same words and place as in the Preparation bar (it fits 1280 px too).
        self.btn_panic = QPushButton("🚨 PANIC [ESC ×2]")
        self.btn_panic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_panic.setFixedHeight(34)
        self.btn_panic.setMinimumWidth(160)
        self.btn_panic.setToolTip(
            "EMERGENZA (0ms): Taglia immediatamente Audio, Video e Immagini su tutti i layer. "
            "Mostra Nero assoluto se il Tappo è quello di calibrazione (o Tappo personalizzato se impostato).\n"
            "Da tastiera: premi ESC due volte entro 0,6s (protezione anti-tocco accidentale)."
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
        root.addWidget(self.top_bar)
        self.pin_bar = PinBar()  # the exit PIN, when one is set (C2a step 10)
        root.addWidget(self.pin_bar)

        # Shown when the keyboard is not on the director window (Space/Esc lost).
        self.lbl_focus_warning = QLabel(
            "⚠  TASTIERA NON SUL PANNELLO REGIA — SPAZIO ed ESC non arrivano a BlindCue. "
            "Clicca qui per riprenderla."
        )
        self.lbl_focus_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_focus_warning.setWordWrap(True)
        self.lbl_focus_warning.setStyleSheet(
            "QLabel { background-color: #b91c1c; color: #ffffff; font-weight: bold; "
            "font-size: 15px; padding: 8px; border-radius: 4px; }"
        )
        self.lbl_focus_warning.setVisible(False)
        root.addWidget(self.lbl_focus_warning)

        # ── 2. Center Hero Area: Extended 6-Column Live Scaletta ──────────────
        self.live_table = LiveCueTable()
        self.live_table.setHorizontalHeaderLabels([
            "#", "Q", "Media / Cue", "Note di Regia", "Tempi · Sequenza", "Layer / Stato"
        ])
        self.live_table.verticalHeader().setVisible(False)
        self.live_table.verticalHeader().setDefaultSectionSize(38)
        self.live_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.live_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.live_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.live_table.setShowGrid(False)
        self.live_table.setWordWrap(False)
        self.live_table.setStyleSheet(
            "QTableWidget { background-color: #0b0f16; border: 1px solid #1e293b; border-radius: 6px; "
            "font-size: 13px; gridline-color: #161f2c; } "
            "QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #131b26; } "
            "QHeaderView::section { background-color: #131a26; color: #94a3b8; font-weight: bold; "
            "font-size: 11px; padding: 6px; border: none; border-bottom: 1px solid #243144; }"
        )
        hdr = self.live_table.horizontalHeader()
        hdr.setHighlightSections(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        # Narrower than before: "Now playing" takes 360 px on the right and
        # the cue name needs the room (C2a step 8; Q only when a cue has one).
        self.live_table.setColumnWidth(0, 52)
        self.live_table.setColumnWidth(1, 76)
        self.live_table.setColumnWidth(3, 200)
        self.live_table.setColumnWidth(4, 204)
        self.live_table.setColumnWidth(5, 136)
        self.live_table.setItemDelegate(LiveCueRowDelegate(self.live_table))

        self.live_table.cellClicked.connect(self._on_table_clicked)
        self.live_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.live_table.go_requested.connect(self.go_requested)
        self.live_table.force_go_requested.connect(self.force_go_requested)
        self.live_table.panic_requested.connect(self.panic_requested)
        self.live_table.standby_selected.connect(self.cue_row_clicked)
        self.live_table.fire_row_requested.connect(self.force_row_requested)
        self.live_table.group_collapse_toggled.connect(self.group_collapse_toggled)
        # The list and, on its right, what is on air now (stage 1 C2a step 8).
        middle = QHBoxLayout()
        middle.setSpacing(8)
        middle.addWidget(self.live_table, stretch=1)
        self.now_playing = NowPlayingPanel()
        middle.addWidget(self.now_playing)
        root.addLayout(middle, stretch=1)

        # "Last started" line above "Next": what the last GO started, and when.
        self.last_bar = QFrame()
        self.last_bar.setFixedHeight(32)
        lb_layout = QHBoxLayout(self.last_bar)
        lb_layout.setContentsMargins(12, 2, 12, 2)
        lb_layout.setSpacing(10)
        self.lbl_last_pill = QLabel("✓ ULTIMA")
        self.lbl_last_pill.setFixedHeight(24)
        self.lbl_last_pill.setStyleSheet(
            "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 10px; }"
        )
        lb_layout.addWidget(self.lbl_last_pill)
        self.lbl_last_banner = QLabel("")
        self.lbl_last_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_last_banner.setTextFormat(Qt.TextFormat.PlainText)  # names are typed by people
        lb_layout.addWidget(self.lbl_last_banner, stretch=1)
        self.btn_edit_last = self._edit_button()
        self.btn_edit_last.clicked.connect(lambda: self._emit_edit(self._last_cue_id))
        lb_layout.addWidget(self.btn_edit_last)
        self._last_cue_id = -1
        self.last_bar_layout = lb_layout
        # Undo the last GO (1.18): a fixed 180 px place at the right end, empty
        # when there is nothing to undo (not greyed out). No keyboard focus:
        # Space must stay GO; the keyboard way is the Show menu.
        self._undo_slot = QWidget()
        self._undo_slot.setFixedWidth(180)
        us_layout = QHBoxLayout(self._undo_slot)
        us_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_undo_go = QPushButton("")
        self.btn_undo_go.setFixedHeight(24)
        self.btn_undo_go.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_undo_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo_go.setStyleSheet(
            "QPushButton { background-color: #1e293b; color: #f8fafc; border: 1px solid #94a3b8; "
            "border-radius: 4px; font-weight: bold; font-size: 12px; padding: 0px 8px; } "
            "QPushButton:hover { background-color: #334155; border-color: #f8fafc; }"
        )
        self.btn_undo_go.clicked.connect(self.undo_go_requested)
        self.btn_undo_go.setVisible(False)
        us_layout.addWidget(self.btn_undo_go)
        lb_layout.addWidget(self._undo_slot)
        self.last_bar.setVisible(False)  # until the first GO
        self._last_text = ""
        self._last_note = ""
        self._paused_ids: set[int] = set()
        # Helper cues (started by the cue before: Auto-GO, "together") fold
        # under the head of their chain; a click on its number opens it (1.13).
        self._open_chains: set[int] = set()
        self._chain_head: dict[int, int] = {}     # row -> row of its chain head
        self._centred_row = -1
        self._last_at = 0.0
        self._last_by_hand = False
        self._last_hot: bool | None = None
        self._set_last_hot(False)
        root.addWidget(self.last_bar)

        # Standby Hero Bar + optional Break Section Loop shortcut.
        # Always two lines (the second one is the cue's note, kept even when
        # empty so the layout never jumps).
        self.standby_bar = QFrame()
        self.standby_bar.setFixedHeight(52)
        sb_layout = QHBoxLayout(self.standby_bar)
        sb_layout.setContentsMargins(12, 2, 12, 2)
        sb_layout.setSpacing(10)

        self.lbl_standby_pill = QLabel("▶ STANDBY")
        self.lbl_standby_pill.setFixedHeight(26)
        sb_layout.addWidget(self.lbl_standby_pill)

        sb_lines = QVBoxLayout()
        sb_lines.setContentsMargins(0, 0, 0, 0)
        sb_lines.setSpacing(0)
        self.lbl_standby_banner = QLabel("Nessuna cue pronta in scaletta")
        self.lbl_standby_banner.setMinimumWidth(0)
        self.lbl_standby_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby_banner.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_standby_banner.setStyleSheet(
            "QLabel { color: #f8fafc; font-size: 13px; font-weight: bold; border: none; background: transparent; }"
        )
        sb_lines.addWidget(self.lbl_standby_banner)
        self.lbl_standby_note = QLabel("")
        self.lbl_standby_note.setMinimumWidth(0)
        self.lbl_standby_note.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby_note.setTextFormat(Qt.TextFormat.PlainText)
        self._set_standby_note("")
        sb_lines.addWidget(self.lbl_standby_note)
        sb_layout.addLayout(sb_lines, stretch=1)
        self.btn_gate_ok = QPushButton("✋ OK")
        self.btn_gate_ok.setFixedHeight(28)
        self.btn_gate_ok.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Space stays GO
        self.btn_gate_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gate_ok.setToolTip("Conferma: la cue parte adesso (anche Invio sulla lista)")
        self.btn_gate_ok.setStyleSheet(
            "QPushButton { background-color: #fbbf24; color: #1c1203; border: 2px solid #f59e0b; "
            "border-radius: 4px; font-weight: bold; font-size: 14px; padding: 0px 14px; }")
        self.btn_gate_ok.clicked.connect(self.gate_ok_requested)
        self.btn_gate_ok.setVisible(False)
        sb_layout.addWidget(self.btn_gate_ok)
        self._gate_id = -1
        self.btn_edit_next = self._edit_button()
        self.btn_edit_next.clicked.connect(lambda: self._emit_edit(self._standby_cue_id))
        sb_layout.addWidget(self.btn_edit_next)
        self._standby_cue_id = -1
        self._rehearsal = False
        # "Hold": the coming Auto-GO waits for a GO (an actor is late); Pause
        # All would stop the music as well.
        self.btn_hold_auto = QPushButton("Trattieni")
        self.btn_hold_auto.setFixedHeight(26)
        self.btn_hold_auto.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Space stays GO
        self.btn_hold_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hold_auto.setToolTip("L'Auto-GO aspetta il GO: la prossima cue non parte da sola")
        self.btn_hold_auto.setStyleSheet(
            "QPushButton { background-color: #0c2638; color: #7dd3fc; border: 1px solid #38bdf8; "
            "border-radius: 4px; font-weight: bold; font-size: 12px; padding: 0px 10px; }"
        )
        self.btn_hold_auto.clicked.connect(self._on_hold_auto_clicked)
        self.btn_hold_auto.setVisible(False)
        sb_layout.addWidget(self.btn_hold_auto)
        self._held_ids: set[int] = set()
        self._standby_base = ""          # line 1 without "how it starts"
        self._standby_waits_on: tuple[int, str] | None = None  # (cue_id, "#3") of an Auto-GO

        self.btn_break_loop = QPushButton("⏭ Esci da Loop Sezione")
        self.btn_break_loop.setVisible(False)
        self.btn_break_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_break_loop.setFixedHeight(26)
        self.btn_break_loop.clicked.connect(self.break_loop_requested)
        sb_layout.addWidget(self.btn_break_loop)
        root.addWidget(self.standby_bar)

        # ── 3. Bottom Transport & Live Output Dock ───────────────────────────
        dock = QHBoxLayout()
        dock.setSpacing(10)

        self.live_status = LiveStatusPanel(compact_live_mode=True)
        self.live_status.setMinimumHeight(140)
        dock.addWidget(self.live_status, stretch=52)

        # Safety Lock Button: Protects Layer controls against accidental touches in crowded control booths
        self.btn_layer_lock = HoldProgressButton(
            text_idle="🔒\nBLOCCO\nLAYER\n(Tieni 1,2s)",
            text_active="🔓\nLAYER\nATTIVI\n(Click = 🔒)",
            hold_ms=1200,
            deactivate_hold_ms=0,  # 1 immediate click to re-lock
            is_toggle=True,
            initial_state=False,   # Starts LOCKED by default
            fill_orientation="vertical",
            color_idle="#2d0a0a",
            border_idle="#b91c1c",
            text_color_idle="#fca5a5",
            color_active="#064e3b",
            border_active="#10b981",
            text_color_active="#6ee7b7",
            fill_color="#ef4444",
        )
        self.btn_layer_lock.setFixedWidth(78)
        self.btn_layer_lock.setMinimumHeight(140)
        self.btn_layer_lock.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))
        self.btn_layer_lock.setToolTip(
            "🔒 CONTROLLI LAYER BLOCCATI (Protezione di Sicurezza Regia)\n"
            "Di default le barre e i controlli dei layer sono protetti per evitare spostamenti o tagli accidentali.\n"
            "Per sbloccare scrub, riavvolgimento e pausa dei singoli layer: tieni premuto per 1,2 secondi.\n"
            "Quando sbloccato, un singolo click istantaneo riattiva subito il blocco."
        )
        self.btn_layer_lock.setAccessibleName("Blocco di Sicurezza Layer")
        self.btn_layer_lock.setAccessibleDescription("Protezione controlli layer Live. Tieni premuto 1,2 secondi per sbloccare, tocca per ribloccare.")
        self.btn_layer_lock.toggled_state.connect(lambda active: self.live_status.set_locked(not active))
        dock.addWidget(self.btn_layer_lock, stretch=0)

        # In the show the cards of "Now playing" carry the layer controls:
        # the layer panel and its lock stay in Preparation only (C2a step 8).
        self.live_status.setVisible(False)
        self.btn_layer_lock.setVisible(False)

        self.transport_frame = QFrame()
        # Pause next to GO, not above it: one row less under the list.
        tr_layout = QHBoxLayout(self.transport_frame)
        tr_layout.setContentsMargins(10, 6, 10, 6)
        tr_layout.setSpacing(8)

        self.btn_pause_all = QPushButton("⏸  PAUSA TUTTO")
        self.btn_pause_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_all.setFixedHeight(64)
        self.btn_pause_all.setFixedWidth(220)
        self.btn_pause_all.setToolTip(
            "Congela tutti i layer LIVE (Audio, Video, Pre-Delay, Post-Delay e Immagini temporizzate) "
            "per ripartire poi dallo stesso istante"
        )
        self.btn_pause_all.setAccessibleName("Pausa o Riprendi Tutto")
        self.btn_pause_all.setAccessibleDescription("Congela o riprende tutti i layer multimediali attivi.")
        self.btn_pause_all.clicked.connect(self.pause_all_toggled)
        self._apply_pause_btn_style(paused=False)
        tr_layout.addWidget(self.btn_pause_all)

        self.btn_go = ElidedButton("▶   GO  —  PROSSIMA CUE")
        self._go_warn = False
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setMinimumHeight(64)
        self.btn_go.setFont(QFont("sans-serif", 17, QFont.Weight.Bold))
        self.btn_go.setAccessibleName("GO - Avvia Cue in Standby")
        self.btn_go.setAccessibleDescription("Manda in esecuzione la cue pronta in standby. Tasto di scelta rapida: Spazio.")
        self.btn_go.clicked.connect(self.go_requested)
        tr_layout.addWidget(self.btn_go, stretch=1)

        dock.addWidget(self.transport_frame, stretch=48)
        root.addLayout(dock)
        self.refresh_theme_styles()

    def stopwatch_elapsed_sec(self) -> float:
        """Return total elapsed seconds recorded by the Show Duration Stopwatch."""
        if self._sw_running:
            return self._sw_accum_sec + max(0.0, time.monotonic() - self._sw_started_mono)
        return self._sw_accum_sec

    def set_go_label(self, text: str, warn: bool) -> None:
        """GO says what it will do; anything but a plain start turns it amber (never red)."""
        self.btn_go.set_full_text(text)
        if warn != self._go_warn:
            self._go_warn = warn
            self._apply_go_style()

    def _apply_go_style(self) -> None:
        active_t = get_active_theme()
        base = "border-radius: 6px; font-size: 17px; font-weight: bold; padding: 6px 12px;"
        if active_t.is_monochrome:
            border = "dashed" if self._go_warn else "solid"
            self.btn_go.setStyleSheet(
                f"QPushButton {{ background-color: #26272e; color: #ffffff; border: 2px {border} #ffffff; {base} }} "
                "QPushButton:hover { background-color: #33343d; border-color: #ffffff; color: #ffffff; } "
                "QPushButton:pressed { background-color: #18191f; }"
            )
        elif self._go_warn:
            # Amber in every colour theme; the amber theme's GO is amber already,
            # so its warning is the dark variant.
            dark = active_t.theme_id == "warm_amber_studio"
            bg, fg, bd = ("#3d2a06", "#fcd34d", "#f59e0b") if dark else ("#f59e0b", "#1c1203", "#fbbf24")
            self.btn_go.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: {fg}; border: 2px solid {bd}; {base} }} "
                "QPushButton:hover { border-color: #fde68a; } "
                "QPushButton:pressed { background-color: #d97706; }"
            )
        elif active_t.theme_id == "warm_amber_studio":
            self.btn_go.setStyleSheet(
                f"QPushButton {{ background-color: #f59e0b; color: #151210; border: 1px solid #fbbf24; {base} }} "
                "QPushButton:hover { background-color: #fbbf24; } "
                "QPushButton:pressed { background-color: #d97706; }"
            )
        else:
            self.btn_go.setStyleSheet(
                f"QPushButton {{ background-color: {CLR_GO}; color: #04130a; border: none; {base} }} "
                "QPushButton:hover { background-color: #69f0ae; } "
                "QPushButton:pressed { background-color: #00c853; }"
            )

    def set_focus_warning(self, visible: bool) -> None:
        """Show or hide the 'keyboard is elsewhere' banner."""
        self.lbl_focus_warning.setVisible(bool(visible))

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
            is_mono = get_active_theme().is_monochrome
            if is_mono:
                if state == "running":
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #2c2d36; color: #ffffff; border: 1.5px solid #ffffff; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #383946; border-color: #d4d4d8; color: #ffffff; }"
                    )
                elif state == "paused":
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1.5px solid #a1a1aa; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #2d2f38; border-color: #ffffff; color: #ffffff; }"
                    )
                else:
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #16171b; color: #a1a1aa; border: 1px solid #27272a; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #22232a; border-color: #3f404d; color: #a1a1aa; }"
                    )
            else:
                if state == "running":
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #0b2920; color: #6ee7b7; border: 1px solid #10b981; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #113b2e; border-color: #34d399; color: #ffffff; }"
                    )
                elif state == "paused":
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #2b2109; color: #fcd34d; border: 1px solid #d97706; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #3d2f0e; border-color: #fbbf24; color: #ffffff; }"
                    )
                else:
                    self.btn_stopwatch.setStyleSheet(
                        "QPushButton { background-color: #151e2c; color: #94a3b8; border: 1px solid #334155; "
                        "border-radius: 5px; font-family: monospace; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                        "QPushButton:hover { background-color: #1e293b; border-color: #38bdf8; color: #f8fafc; }"
                    )
            if state == "running":
                self.btn_stopwatch.setToolTip(
                    "Cronometro Spettacolo in corso (avvio auto al 1° GO o manuale) — Clicca per PAUSA (non ferma i media)"
                )
            elif state == "paused":
                self.btn_stopwatch.setToolTip(
                    "Cronometro Spettacolo in PAUSA — Clicca per RIPRENDERE o usa ↺ per azzerare e riarmare"
                )
            else:
                self.btn_stopwatch.setToolTip(
                    "Durata Spettacolo (Cronometro): parte in automatico al 1° GO oppure clicca qui ora per avviare nelle filate/prove"
                )

    def _update_clock(self) -> None:
        now_txt = QDateTime.currentDateTime().toString("HH:mm:ss")
        if now_txt != self._last_clock_text:
            self._last_clock_text = now_txt
            self.lbl_clock.setText(now_txt)
            self._refresh_last_banner()
        self._refresh_stopwatch_ui()

    # Seconds the "Last" line stays lit after a GO given by hand: the same
    # window in which that GO can be undone (stage 1.18).
    LAST_HOT_SECONDS = 15.0

    @staticmethod
    def _edit_button() -> QPushButton:
        btn = QPushButton("✎")
        btn.setFixedSize(30, 24)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Space stays GO
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Correggi questa cue (prova)")
        btn.setAccessibleName("Correggi questa cue")
        btn.setStyleSheet(
            "QPushButton { background-color: #0c4a6e; color: #bae6fd; border: 1px solid #38bdf8; "
            "border-radius: 4px; font-weight: bold; font-size: 13px; }")
        btn.setVisible(False)
        return btn

    def _emit_edit(self, cue_id: int) -> None:
        if cue_id >= 0:
            self.edit_cue_requested.emit(cue_id)

    def set_rehearsal(self, on: bool) -> None:
        """The rehearsal adds "✎" next to the named cues (Last, Next, the cards)."""
        self._rehearsal = bool(on)
        self.btn_edit_last.setVisible(on and self._last_cue_id >= 0)
        self.btn_edit_next.setVisible(on and self._standby_cue_id >= 0)
        self.now_playing.set_rehearsal(on)

    def set_last_started(self, text: str, note: str = "", by_hand: bool = True, cue_id: int = -1) -> None:
        """The last GO started *text* (e.g. "#3 'Birds' + 2 together").

        Shown with how long ago and the cue's *note*; lit for
        :attr:`LAST_HOT_SECONDS` when the operator gave the GO (*by_hand*).
        """
        self._last_text = text
        self._last_note = note
        self._last_cue_id = cue_id
        self.btn_edit_last.setVisible(self._rehearsal and cue_id >= 0)
        self._last_at = time.monotonic()
        self._last_by_hand = by_hand
        self.last_bar.setVisible(bool(text))
        self._refresh_last_banner()

    def set_readiness_warning(self, count: int, tooltip: str = "") -> None:
        """"⚠ N" while N problems of the readiness check are left (0 hides it)."""
        self.btn_ready_warn.setVisible(count > 0)
        self.btn_ready_warn.setText(f"⚠ {count}")
        self.btn_ready_warn.setToolTip(tooltip)
        self.btn_ready_warn.setAccessibleName(tooltip or f"⚠ {count}")

    def set_undo_go(self, label: str, tooltip: str = "", accessible: str = "") -> None:
        """Show "↶ Undo GO #5 · 12" (empty *label*: nothing to undo, the place stays empty)."""
        self.btn_undo_go.setVisible(bool(label))
        if label:
            self.btn_undo_go.setText(label)
            self.btn_undo_go.setToolTip(tooltip)
            self.btn_undo_go.setAccessibleName(accessible or label)
            self.btn_undo_go.setAccessibleDescription(tooltip)

    def last_started_age(self) -> float:
        """Seconds since the last start shown on the "Last" line."""
        return max(0.0, time.monotonic() - self._last_at)

    def _refresh_last_banner(self) -> None:
        if not self._last_text:
            return
        ago = int(self.last_started_age())
        when = tr("· {} fa").format(f"{ago // 60}:{ago % 60:02d}")
        note = f"   │   📝 {self._last_note}" if self._last_note else ""
        self.lbl_last_banner.setText(f"{self._last_text}  {when}{note}")
        self._set_last_hot(self._last_by_hand and ago < self.LAST_HOT_SECONDS)

    def _set_last_hot(self, hot: bool) -> None:
        """Lit (green) right after a GO, quiet (grey) afterwards."""
        if hot == self._last_hot:
            return
        self._last_hot = hot
        if hot:
            self.last_bar.setStyleSheet(
                "QFrame { background-color: #052e1f; border: 1px solid #10b981; border-radius: 6px; }")
            self.lbl_last_pill.setStyleSheet(
                "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 10px; }")
            colour = "#ecfdf5"
        else:
            self.last_bar.setStyleSheet(
                "QFrame { background-color: #0b111a; border: 1px solid #1e2d42; border-radius: 6px; }")
            self.lbl_last_pill.setStyleSheet(
                "QLabel { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 10px; }")
            colour = "#cbd5e1"
        self.lbl_last_banner.setStyleSheet(
            f"QLabel {{ color: {colour}; font-size: 13px; font-weight: bold; border: none; background: transparent; }}")

    def _set_standby_note(self, note: str) -> None:
        """Second line of "Next": the cue's note, amber, red when it is urgent."""
        urgent = LiveCueRowDelegate.is_urgent_note(note) if note else False
        colour = "#fca5a5" if urgent else "#fcd34d"
        weight = "bold" if urgent else "normal"
        self.lbl_standby_note.setStyleSheet(
            f"QLabel {{ color: {colour}; font-size: 15px; font-weight: {weight}; "
            "border: none; background: transparent; }")
        self.lbl_standby_note.setText(f"📝 {note}" if note else "")

    def _refresh_standby_how(self) -> None:
        """Line 1 of "Next" plus how that cue will start (by hand, or by itself in m:ss)."""
        if not self._standby_base:
            return
        how = tr("· manuale (GO)")
        waits = self._standby_waits_on
        if self._gate_id >= 0 and self._gate_id == self._standby_cue_id:
            how = tr("· ✋ aspetta l'OK")
        elif waits is not None and waits[0] in self._held_ids:
            how = tr("· aspetta il GO (Auto-GO fermato)")
        elif waits is not None:
            cue_id, ref = waits
            live = self._live_times.get(cue_id)
            left = live[0][1:] if live and live[0].startswith("-") else ""
            how = tr("· parte da sola tra {}").format(left) if left else tr("· parte da sola dopo {}").format(ref)
        self.lbl_standby_banner.setText(f"{self._standby_base}  {how}")
        self.btn_hold_auto.setVisible(waits is not None)
        if waits is not None:
            self.btn_hold_auto.setText(tr("Riprendi Auto-GO") if waits[0] in self._held_ids else tr("Trattieni"))

    def set_gate(self, cue_id: int, ref: str) -> None:
        """A cue waits at the start gate (cue_id < 0: nothing waits)."""
        self._gate_id = cue_id
        self.btn_gate_ok.setVisible(cue_id >= 0)
        self._refresh_standby_how()

    def _on_hold_auto_clicked(self) -> None:
        if self._standby_waits_on is not None:
            self.hold_auto_go_requested.emit(self._standby_waits_on[0])

    def set_auto_go_held(self, ids: set[int]) -> None:
        """Cues whose Auto-GO waits for a GO this time (said on the NEXT bar)."""
        self._held_ids = set(ids)
        self._refresh_standby_how()

    def _on_table_clicked(self, row: int, col: int) -> None:
        if not self._updating_table and row >= 0:
            if col == 0:
                it = self.live_table.item(row, col)
                if it and it.data(ROLE_IS_GROUP):
                    self.group_collapse_toggled.emit(row)
                    return
                if row in self._chain_head.values():
                    self.toggle_chain(row)
            self.cue_row_clicked.emit(row)

    def toggle_chain(self, head_row: int) -> None:
        """Open / fold the helper cues under the chain head at *head_row*."""
        name_item = self.live_table.item(head_row, 2)
        id_row = next((cid for cid, r in self._cue_id_to_row.items() if r == head_row), None)
        if id_row is None:
            return
        opening = id_row not in self._open_chains
        if opening:
            self._open_chains.add(id_row)
        else:
            self._open_chains.discard(id_row)
        helpers = [r for r, h in self._chain_head.items() if h == head_row]
        for r in helpers:
            self.live_table.setRowHidden(r, not opening)
        if name_item is not None:
            base = name_item.text().split("   ⤵+")[0]
            name_item.setText(base if opening else f"{base}   ⤵+{len(helpers)}")

    def _on_table_double_clicked(self, row: int, _col: int) -> None:
        """Double-click only arms the cue as next, unless the operator opted in.

        A slip of the mouse must not start a cue during a show; GO, the
        right-click "GO Forzato" and ``live/double_click_fires`` still can.
        """
        if row < 0 or self._updating_table:
            return
        if live_double_click_fires():
            self.cue_row_double_clicked.emit(row)
        else:
            self.cue_row_clicked.emit(row)
            self.double_click_armed.emit(row)

    def _apply_pause_btn_style(self, *, paused: bool) -> None:
        is_mono = get_active_theme().is_monochrome
        self.lbl_show_badge.setVisible(paused)  # the mode is on the tabs; the badge says "paused"
        if paused:
            self.btn_pause_all.setText("▶  RIPRENDI TUTTO  [IN PAUSA]")
            if is_mono:
                self.btn_pause_all.setStyleSheet(
                    "QPushButton { background-color: #f4f4f5; color: #111215; border: 2px solid #ffffff; "
                    "border-radius: 5px; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                    "QPushButton:hover { background-color: #ffffff; }"
                )
                self.lbl_show_badge.setText("⏸ SHOW IN PAUSA")
                self.lbl_show_badge.setStyleSheet(
                    "QLabel { background-color: #22232a; color: #d4d4d8; border: 1.5px solid #a1a1aa; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
                )
            else:
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
            if is_mono:
                self.btn_pause_all.setStyleSheet(
                    "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1.5px solid #525363; "
                    "border-radius: 5px; font-weight: bold; font-size: 13px; padding: 0px 10px; } "
                    "QPushButton:hover { background-color: #2d2f38; border-color: #a1a1aa; color: #ffffff; }"
                )
                self.lbl_show_badge.setText("● MODALITÀ LIVE (SHOW MODE)")
                self.lbl_show_badge.setStyleSheet(
                    "QLabel { background-color: #2c2d36; color: #ffffff; border: 1.5px solid #ffffff; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
                )
            else:
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

    def refresh_theme_styles(self) -> None:
        """Apply theme styling to Live Show controls (top bar, table, dock, GO button, panic, layer bars)."""
        active_t = get_active_theme()
        is_mono = active_t.is_monochrome

        # 1. Top Show Bar & its controls
        if hasattr(self, "top_bar") and self.top_bar is not None:
            if is_mono:
                self.top_bar.setStyleSheet(
                    "QFrame { background-color: #16171b; border: 1.5px solid #3f404d; border-radius: 6px; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.top_bar.setStyleSheet(
                    "QFrame { background-color: #191512; border: 1px solid #3d322a; border-radius: 6px; }"
                )
            else:
                self.top_bar.setStyleSheet(
                    "QFrame { background-color: #101620; border: 1px solid #1e293b; border-radius: 6px; }"
                )

        if hasattr(self, "btn_back_project") and self.btn_back_project is not None:
            if is_mono:
                self.btn_back_project.setStyleSheet(
                    "QPushButton { background-color: #26272e; color: #f4f4f6; border: 1.5px solid #3f404d; "
                    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; } "
                    "QPushButton:hover { background-color: #33343d; border-color: #ffffff; color: #ffffff; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.btn_back_project.setStyleSheet(
                    "QPushButton { background-color: #26201b; color: #fef3c7; border: 1px solid #42372f; "
                    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; } "
                    "QPushButton:hover { background-color: #362d26; border-color: #f59e0b; color: #ffffff; }"
                )
            else:
                self.btn_back_project.setStyleSheet(
                    "QPushButton { background-color: #1c2636; color: #e2e8f0; border: 1px solid #3c4f6b; "
                    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; } "
                    "QPushButton:hover { background-color: #27364d; border-color: #38bdf8; color: #ffffff; }"
                )

        if hasattr(self, "btn_stopwatch_reset") and self.btn_stopwatch_reset is not None:
            if is_mono:
                self.btn_stopwatch_reset.setStyleSheet(
                    "QPushButton { background-color: #26272e; color: #d4d4d8; border: 1.5px solid #3f404d; "
                    "border-radius: 5px; font-weight: bold; font-size: 15px; } "
                    "QPushButton:hover { background-color: #33343d; color: #ffffff; border-color: #ffffff; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.btn_stopwatch_reset.setStyleSheet(
                    "QPushButton { background-color: #26201b; color: #bfa89b; border: 1px solid #42372f; "
                    "border-radius: 5px; font-weight: bold; font-size: 15px; } "
                    "QPushButton:hover { background-color: #362d26; color: #ffffff; border-color: #f59e0b; }"
                )
            else:
                self.btn_stopwatch_reset.setStyleSheet(
                    "QPushButton { background-color: #16202e; color: #94a3b8; border: 1px solid #334155; "
                    "border-radius: 5px; font-weight: bold; font-size: 15px; } "
                    "QPushButton:hover { background-color: #253347; color: #f8fafc; border-color: #64748b; }"
                )

        if hasattr(self, "btn_panic") and self.btn_panic is not None:
            if is_mono:
                self.btn_panic.setStyleSheet(
                    "QPushButton { background-color: #1a1b1f; color: #ffffff; border: 2px solid #ffffff; "
                    "border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0px 14px; } "
                    "QPushButton:hover { background-color: #26272e; border-color: #f4f4f5; } "
                    "QPushButton:pressed { background-color: #3f3f46; }"
                )
            else:
                self.btn_panic.setStyleSheet(
                    "QPushButton { background-color: #7f1d1d; color: #ffffff; border: 2px solid #ef4444; "
                    "border-radius: 6px; font-weight: bold; font-size: 13px; padding: 0px 14px; } "
                    "QPushButton:hover { background-color: #dc2626; border-color: #fca5a5; } "
                    "QPushButton:pressed { background-color: #991b1b; }"
                )

        # 2. Live Scaletta Table
        if hasattr(self, "live_table") and self.live_table is not None:
            if is_mono:
                self.live_table.setStyleSheet(
                    "QTableWidget { background-color: #111215; border: 1.5px solid #3f404d; border-radius: 6px; "
                    "font-size: 13px; gridline-color: #27272a; } "
                    "QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #27272a; } "
                    "QHeaderView::section { background-color: #16171b; color: #ffffff; font-weight: bold; "
                    "font-size: 11px; padding: 6px; border: none; border-bottom: 1.5px solid #3f404d; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.live_table.setStyleSheet(
                    "QTableWidget { background-color: #151210; border: 1px solid #3d322a; border-radius: 6px; "
                    "font-size: 13px; gridline-color: #2a221c; } "
                    "QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #2a221c; } "
                    "QHeaderView::section { background-color: #191512; color: #f59e0b; font-weight: bold; "
                    "font-size: 11px; padding: 6px; border: none; border-bottom: 1px solid #3d322a; }"
                )
            else:
                self.live_table.setStyleSheet(
                    "QTableWidget { background-color: #0b0f16; border: 1px solid #1e293b; border-radius: 6px; "
                    "font-size: 13px; gridline-color: #161f2c; } "
                    "QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #131b26; } "
                    "QHeaderView::section { background-color: #131a26; color: #94a3b8; font-weight: bold; "
                    "font-size: 11px; padding: 6px; border: none; border-bottom: 1px solid #243144; }"
                )

        # 3. Standby Bar
        if hasattr(self, "standby_bar") and self.standby_bar is not None:
            if is_mono:
                self.standby_bar.setStyleSheet(
                    "QFrame { background-color: #1a1b1f; border: 1.5px solid #3f404d; border-radius: 6px; }"
                )
                self.lbl_standby_pill.setStyleSheet(
                    "QLabel { background-color: #22232a; color: #ffffff; border: 1.5px solid #ffffff; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.standby_bar.setStyleSheet(
                    "QFrame { background-color: #1e1916; border: 1px solid #3d322a; border-radius: 6px; }"
                )
                self.lbl_standby_pill.setStyleSheet(
                    "QLabel { background-color: #3d2612; color: #fbbf24; border: 1px solid #d97706; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; }"
                )
            else:
                self.standby_bar.setStyleSheet(
                    "QFrame { background-color: #0b111a; border: 1px solid #1e2d42; border-radius: 6px; }"
                )
                self.lbl_standby_pill.setStyleSheet(
                    "QLabel { background-color: #451a03; color: #fbbf24; border: 1px solid #d97706; "
                    "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; }"
                )

        # 4. Layer Safety Lock Button
        if hasattr(self, "btn_layer_lock") and self.btn_layer_lock is not None:
            if is_mono:
                self.btn_layer_lock.set_palette_colors(
                    color_idle="#1a1b1f",
                    border_idle="#ffffff",
                    text_color_idle="#ffffff",
                    color_active="#26272e",
                    border_active="#d4d4d8",
                    text_color_active="#ffffff",
                    fill_color="#ffffff",
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.btn_layer_lock.set_palette_colors(
                    color_idle="#2d1508",
                    border_idle="#b45309",
                    text_color_idle="#fed7aa",
                    color_active="#1b2a1a",
                    border_active="#10b981",
                    text_color_active="#a7f3d0",
                    fill_color="#f59e0b",
                )
            else:
                self.btn_layer_lock.set_palette_colors(
                    color_idle="#2d0a0a",
                    border_idle="#b91c1c",
                    text_color_idle="#fca5a5",
                    color_active="#064e3b",
                    border_active="#10b981",
                    text_color_active="#6ee7b7",
                    fill_color="#ef4444",
                )

        # 5. Bottom Transport Frame
        if hasattr(self, "transport_frame") and self.transport_frame is not None:
            if is_mono:
                self.transport_frame.setStyleSheet(
                    "QFrame { background-color: #16171b; border: 1.5px solid #3f404d; border-radius: 6px; }"
                )
            elif active_t.theme_id == "warm_amber_studio":
                self.transport_frame.setStyleSheet(
                    "QFrame { background-color: #191512; border: 1px solid #3d322a; border-radius: 6px; }"
                )
            else:
                self.transport_frame.setStyleSheet(
                    "QFrame { background-color: #0e141e; border: 1px solid #1e293b; border-radius: 6px; }"
                )

        # 6. GO and Loop Buttons
        self._apply_go_style()
        if is_mono:
            self.btn_break_loop.setStyleSheet(
                "QPushButton { background-color: #22232a; color: #d4d4d8; border: 1.5px solid #525363; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 4px 8px; } "
                "QPushButton:hover { background-color: #2d2f38; border-color: #a1a1aa; color: #ffffff; }"
            )
        elif active_t.theme_id == "warm_amber_studio":
            self.btn_break_loop.setStyleSheet(
                "QPushButton { background-color: #2b2420; color: #fef3c7; border: 1px solid #f59e0b; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 4px 8px; } "
                "QPushButton:hover { background-color: #3d322a; }"
            )
        else:
            self.btn_break_loop.setStyleSheet(
                "QPushButton { background-color: #78350f; color: #fef3c7; border: 1px solid #f59e0b; "
                "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 4px 8px; } "
                "QPushButton:hover { background-color: #b45309; }"
            )
        self._apply_pause_btn_style(paused=getattr(self, "_is_paused_all", False))
        self._last_sw_state = ""
        self._refresh_stopwatch_ui()
        if hasattr(self, "live_status") and hasattr(self.live_status, "refresh_theme_styles"):
            self.live_status.refresh_theme_styles()

    def set_global_paused(self, paused: bool) -> None:
        """Show the global pause/panic banner over the live view."""
        self._is_paused_all = paused
        self._apply_pause_btn_style(paused=paused)

    def update_phase_badge(self, cue_id: int, phase_txt: str) -> bool:
        """Fast-path O(1) update of a single row's phase countdown badge (10 Hz scheduler ticks)."""
        row = self._cue_id_to_row.get(cue_id)
        if row is None or not (0 <= row < self.live_table.rowCount()):
            return False
        is_waiting = bool(phase_txt)
        for c_idx in range(6):
            it = self.live_table.item(row, c_idx)
            if it is None:
                return False
            is_live = bool(it.data(ROLE_IS_LIVE))
            is_standby = bool(it.data(ROLE_IS_STANDBY))
            status_txt = "LIVE" if is_live else ("STANDBY" if is_standby else ("ATTESA" if is_waiting else "PRONTO"))
            status_clr = "#4ade80" if is_live else ("#fcd34d" if is_standby else ("#7dd3fc" if is_waiting else "#94a3b8"))
            it.setData(ROLE_PHASE_TXT, phase_txt)
            it.setData(ROLE_STATUS_TXT, status_txt)
            it.setData(ROLE_STATUS_CLR, status_clr)
            if c_idx == 5:
                it.setText(status_txt)
        return True

    @staticmethod
    def _apply_live_time(item: QTableWidgetItem, value: tuple[str, float, bool] | None) -> None:
        text, fraction, warn = value if value is not None else ("", -1.0, False)
        item.setData(ROLE_LIVE_TIME, text)
        item.setData(ROLE_LIVE_FRACTION, fraction)
        item.setData(ROLE_LIVE_WARN, warn)
        # What is only painted, in words for screen readers (W21); the text
        # changes once a second at most (mm:ss).
        if text:
            spoken = tr("tempo: {}").format(text)
            if warn:
                spoken += ", " + tr("finisce – il prossimo GO è tuo")
            item.setData(Qt.ItemDataRole.AccessibleTextRole, spoken)
        else:
            item.setData(Qt.ItemDataRole.AccessibleTextRole, None)

    def set_paused_cues(self, ids: set[int]) -> None:
        """Cues on air that a pause holds: "⏸ PAUSED" instead of "● LIVE" (W35)."""
        ids = set(ids)
        if ids == self._paused_ids:
            return
        changed = ids ^ self._paused_ids
        self._paused_ids = ids
        for cue_id in changed:
            row = self._cue_id_to_row.get(cue_id)
            item = self.live_table.item(row, 5) if row is not None else None
            if item is not None:
                item.setData(ROLE_PAUSED, cue_id in ids)
                item.setData(Qt.ItemDataRole.AccessibleTextRole,
                             tr("in pausa") if cue_id in ids else tr("in onda"))

    def set_live_times(self, times: dict[int, tuple[str, float, bool]]) -> None:
        """Redraw only the time cells of the cues on air (called by the 10 Hz clock).

        *times* maps cue_id to (short text, played fraction, ends-soon warning);
        rows missing from it go back to showing their length.
        """
        changed = set(self._live_times) | set(times)
        self._live_times = dict(times)
        for cue_id in changed:
            row = self._cue_id_to_row.get(cue_id)
            item = self.live_table.item(row, 4) if row is not None else None
            if item is not None:
                self._apply_live_time(item, times.get(cue_id))
        if self._standby_waits_on is not None:
            self._refresh_standby_how()  # "starts by itself in 0:03" counts down

    def sync_cues(
        self,
        cues: list[Cue],
        standby_row: int,
        known_durations: dict[str, float],
        phase_tags: dict[int, str] | None = None,
        show_break_loop: bool = False,
        layer_conflicts: dict[int, Any] | None = None,
        played: set[int] | None = None,
    ) -> None:
        """Refresh the extended Live Scaletta table, standby banner, and GO target label.

        *played* holds the cue_ids started in this run of the show (✓, dimmed).

        Reuses existing QTableWidgetItem cells in place to avoid churning 6*N Qt heap
        objects on every GO or phase update.
        """
        self._updating_table = True
        try:
            self.live_table.setRowCount(len(cues))
            phases = phase_tags or {}
            conflicts = layer_conflicts or {}
            played_ids = played or set()

            # Pre-index hierarchy once in O(N) instead of O(N^2) scans per row
            cue_by_id: dict[int, Cue] = {c.cue_id: c for c in cues}
            children_by_parent: dict[int, list[Cue]] = {}
            self._cue_id_to_row.clear()
            for idx, c in enumerate(cues):
                self._cue_id_to_row[c.cue_id] = idx
                if c.parent_id is not None:
                    children_by_parent.setdefault(c.parent_id, []).append(c)
            self._chain_head = {}
            helpers_of: dict[int, int] = {}
            for idx in range(1, len(cues)):
                prev = cues[idx - 1]
                if (prev.follow_mode in (FollowMode.AUTO_FOLLOW.value, FollowMode.SIMULTANEOUS.value)
                        and prev.parent_id == cues[idx].parent_id
                        and cues[idx].media_type != MediaType.GROUP):
                    head = self._chain_head.get(idx - 1, idx - 1)
                    self._chain_head[idx] = head
                    helpers_of[head] = helpers_of.get(head, 0) + 1

            for r, cue in enumerate(cues):
                is_live = (cue.status == CueStatus.LIVE)
                is_standby = (r == standby_row and not is_live)
                phase_txt = phases.get(cue.cue_id, "")
                is_waiting = bool(phase_txt)
                is_group = (cue.media_type == MediaType.GROUP)
                conflict = conflicts.get(cue.cue_id)
                conflict_txt = getattr(conflict, "reason", "") if conflict is not None else ""

                # Duration string calculation
                dur_hint = known_durations.get(cue.file_path, 0.0)
                if is_group:
                    children = children_by_parent.get(cue.cue_id, [])
                    child_count = len(children)
                    tot_d = 0.0
                    for ch in children:
                        ch_hint = known_durations.get(ch.file_path, 0.0)
                        if ch.out_point is not None and ch.out_point > ch.in_point:
                            tot_d += (ch.out_point - ch.in_point)
                        elif ch_hint > 0:
                            tot_d += max(0.0, ch_hint - ch.in_point)
                        elif ch.media_type == MediaType.IMAGE:
                            tot_d += ch.hold_time if ch.hold_time > 0 else 5.0
                    dur_str = f"~{_fmt_mmss(tot_d)}" if tot_d > 0 else "[Scena]"
                elif cue.media_type == MediaType.IMAGE:
                    child_count = 0
                    if cue.hold_time <= 0:
                        dur_str = "∞"
                    elif cue.hold_time < 10.0:
                        dur_str = f"{cue.hold_time:.1f}s"
                    else:
                        dur_str = _fmt_mmss(cue.hold_time)
                elif cue.media_type == MediaType.ACTION:
                    child_count = 0
                    act_d = action_duration(cue.action_spec)
                    dur_str = f"⚡ {act_d:.1f}s" if act_d > 0 else "⚡"
                else:
                    child_count = 0
                    raw_dur = 0.0
                    if cue.out_point is not None and cue.out_point > cue.in_point:
                        raw_dur = cue.out_point - cue.in_point
                    elif dur_hint > 0:
                        raw_dur = max(0.0, dur_hint - cue.in_point)
                    dur_str = _fmt_mmss(raw_dur) if raw_dur > 0 else "--:--"

                is_last_child = False
                if cue.parent_id is not None:
                    siblings = children_by_parent.get(cue.parent_id, [])
                    if siblings and siblings[-1].cue_id == cue.cue_id:
                        is_last_child = True

                cue_color = getattr(cue, "color", "") or ""
                prev_color = (getattr(cues[r - 1], "color", "") or "") if r > 0 else ""
                incoming_link = cues[r - 1].follow_mode if r > 0 else ""
                status_txt = "LIVE" if is_live else ("STANDBY" if is_standby else ("ATTESA" if is_waiting else "PRONTO"))
                status_clr = "#4ade80" if is_live else ("#fcd34d" if is_standby else ("#7dd3fc" if is_waiting else "#94a3b8"))

                folded = helpers_of.get(r, 0) if cue.cue_id not in self._open_chains else 0
                col_texts = (
                    f"{r + 1}",
                    (cue.q_label or "").strip() or "—",
                    f"{cue.name}   ⤵+{folded}" if folded else cue.name,
                    cue.notes or "",
                    dur_str,
                    status_txt,
                )

                for c_idx, cell_text in enumerate(col_texts):
                    it = self.live_table.item(r, c_idx)
                    if it is None:
                        it = QTableWidgetItem(cell_text)
                        self.live_table.setItem(r, c_idx, it)
                    elif it.text() != cell_text:
                        it.setText(cell_text)

                    it.setData(ROLE_CUE_COLOR, cue_color)
                    it.setData(ROLE_PREV_COLOR, prev_color)
                    it.setData(ROLE_FOLLOW_MODE, cue.follow_mode)
                    it.setData(ROLE_INCOMING_LINK, incoming_link)
                    it.setData(ROLE_IS_GROUP, is_group)
                    it.setData(ROLE_PARENT_ID, cue.parent_id)
                    it.setData(ROLE_IS_LAST_CHILD, is_last_child)
                    it.setData(ROLE_CHILD_COUNT, child_count)
                    it.setData(ROLE_GROUP_MODE, getattr(cue, "group_mode", "STEP"))
                    it.setData(ROLE_GROUP_COLLAPSED, getattr(cue, "collapsed", False))
                    it.setData(ROLE_TIMELINE_COMPOSED, bool(getattr(cue, "timeline_composed", False)))
                    it.setData(ROLE_MEDIA_TYPE, cue.media_type.value)
                    it.setData(ROLE_LAYER, cue.layer)
                    it.setData(ROLE_OUTPUT_TARGET, getattr(cue, "output_target", "A"))
                    it.setData(ROLE_HAS_NOTES, bool(cue.notes))
                    it.setData(ROLE_NOTES_TXT, cue.notes or "")
                    it.setData(ROLE_IS_LIVE, is_live)
                    it.setData(ROLE_IS_STANDBY, is_standby)
                    it.setData(ROLE_SECTION_COUNT, len(cue.sections))
                    it.setData(ROLE_LOOP, cue.loop)
                    it.setData(ROLE_PRE_DELAY, cue.pre_delay)
                    it.setData(ROLE_POST_DELAY, cue.post_delay)
                    it.setData(ROLE_DURATION_TXT, dur_str)
                    it.setData(ROLE_PHASE_TXT, phase_txt)
                    it.setData(ROLE_LAYER_CONFLICT, conflict_txt)
                    it.setData(ROLE_STATUS_TXT, status_txt)
                    it.setData(ROLE_STATUS_CLR, status_clr)
                    it.setData(ROLE_PLAYED, cue.cue_id in played_ids)
                    if c_idx == 0:
                        played_word = (", " + tr("✓ suonata")) if cue.cue_id in played_ids else ""
                        it.setData(Qt.ItemDataRole.AccessibleTextRole, f"{r + 1}{played_word}")
                    elif c_idx == 5:
                        paused = is_live and cue.cue_id in self._paused_ids
                        it.setData(ROLE_PAUSED, paused)
                        word = (tr("in pausa") if paused else tr("in onda")) if is_live else (
                            tr("prossima") if is_standby else (tr("in attesa") if is_waiting else tr("pronta")))
                        it.setData(Qt.ItemDataRole.AccessibleTextRole, word)
                    if c_idx == 4:
                        self._apply_live_time(it, self._live_times.get(cue.cue_id))
                    if conflict_txt:
                        it.setToolTip(f"⚠ {conflict_txt}")
                    elif it.toolTip():
                        it.setToolTip("")

                # Set row visibility based on parent collapsed state
                hidden = False
                if cue.parent_id is not None:
                    parent = cue_by_id.get(cue.parent_id)
                    hidden = bool(parent and parent.collapsed)
                head = self._chain_head.get(r)
                if (head is not None and cues[head].cue_id not in self._open_chains
                        and r != standby_row):
                    hidden = True  # a helper cue, folded under its chain head (1.13)
                self.live_table.setRowHidden(r, hidden)

            self.live_table.setColumnHidden(1, not any((c.q_label or "").strip() for c in cues))
            if 0 <= standby_row < len(cues):
                self.live_table.selectRow(standby_row)
                if standby_row != self._centred_row:
                    # The next cue sits in the middle of the list (1.13); only when
                    # it moves, so scrolling by hand is not fought on every refresh.
                    self._centred_row = standby_row
                    centre = self.live_table.item(standby_row, 2)
                    if centre is not None:
                        self.live_table.scrollToItem(centre, QAbstractItemView.ScrollHint.PositionAtCenter)
                sb_cue = cues[standby_row]
                self._standby_cue_id = sb_cue.cue_id
                self.btn_edit_next.setVisible(self._rehearsal)
                ref = format_cue_ref(standby_row, sb_cue)

                q_badge = f"[{sb_cue.q_label.strip()}] " if (sb_cue.q_label and sb_cue.q_label.strip()) else ""
                if sb_cue.media_type == MediaType.GROUP:
                    layer_badge = "[SCENA]"
                elif sb_cue.media_type == MediaType.ACTION:
                    layer_badge = ""  # no layer; the [ACT] type tag follows
                else:
                    sb_prefix = "B·" if normalize_output_target(getattr(sb_cue, "output_target", "A")) == "B" else ""
                    layer_badge = f"[{sb_prefix}L{sb_cue.layer}]"
                type_map = {
                    MediaType.VIDEO: "VID",
                    MediaType.AUDIO: "AUD",
                    MediaType.IMAGE: "IMG",
                    MediaType.GROUP: "GRP",
                    MediaType.ACTION: "ACT",
                }
                type_tag = type_map.get(sb_cue.media_type, sb_cue.media_type.value[:3])

                extra_tags: list[str] = []
                if sb_cue.pre_delay > 0:
                    extra_tags.append(f"⏳ Pre +{sb_cue.pre_delay:.1f}s")
                # Each piece is translated on its own: glued into one string
                # they no longer matched the dictionary (Italian on a Polish screen).
                if sb_cue.follow_mode == FollowMode.AUTO_FOLLOW.value:
                    extra_tags.append(tr("⤵ Auto-GO al termine"))
                elif sb_cue.follow_mode == FollowMode.SIMULTANEOUS.value:
                    extra_tags.append(tr("⇉ + Cue successiva simultanea"))
                if sb_cue.loop:
                    extra_tags.append(tr("🔁 Loop"))

                extras_str = ("   │   " + " · ".join(extra_tags)) if extra_tags else ""

                # The pill on the left already says what this line is; the
                # note gets a line of its own.
                self._standby_base = (
                    f"#{standby_row + 1} {q_badge}'{sb_cue.name}'  {layer_badge} [{type_tag}]{extras_str}"
                )
                prev = cues[standby_row - 1] if standby_row > 0 else None
                self._standby_waits_on = None
                if (prev is not None and prev.follow_mode == FollowMode.AUTO_FOLLOW.value
                        and prev.status == CueStatus.LIVE):
                    self._standby_waits_on = (prev.cue_id, format_cue_ref(standby_row - 1, prev))
                self._refresh_standby_how()
                self._set_standby_note(sb_cue.notes or "")
                # The GO text (with its state) comes from the main window: set_go_label.
                self.btn_go.setToolTip(
                    f"Esegui cue in Standby: {ref} '{sb_cue.name}'\n"
                    "Scorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]"
                )
            else:
                self.live_table.clearSelection()
                self._standby_base = ""
                self._standby_waits_on = None
                self._standby_cue_id = -1
                self.btn_edit_next.setVisible(False)
                self.btn_hold_auto.setVisible(False)
                self.lbl_standby_banner.setText("Nessuna cue pronta in scaletta")
                self._set_standby_note("")
                self.btn_go.setToolTip(
                    "Esegui prossima cue\n"
                    "Scorciatoia principale da tastiera: [ BARRA SPAZIATRICE ]"
                )

            self.btn_break_loop.setVisible(show_break_loop)
        finally:
            self._updating_table = False

    def closeEvent(self, event) -> None:  # noqa: N802
        """Stop the show clock timer cleanly when the live panel closes."""
        if hasattr(self, "_clock_timer") and self._clock_timer.isActive():
            self._clock_timer.stop()
        super().closeEvent(event)
