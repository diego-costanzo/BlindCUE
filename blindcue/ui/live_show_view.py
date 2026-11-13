"""Dedicated distraction-free LIVE Show Mode view centered on the extended Cue Sequence List."""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QDateTime, QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
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

from models.cue import Cue, CueStatus, FollowMode, MediaType
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
    ROLE_LOOP,
    ROLE_MEDIA_TYPE,
    ROLE_NOTES_TXT,
    ROLE_PARENT_ID,
    ROLE_PHASE_TXT,
    ROLE_POST_DELAY,
    ROLE_PRE_DELAY,
    ROLE_PREV_COLOR,
    ROLE_SECTION_COUNT,
    ROLE_STATUS_CLR,
    ROLE_STATUS_TXT,
    _GROUP_MODE_PILLS,
    _LINK_RAIL_COLORS,
    format_cue_ref,
    paint_cue_row_decorations,
)
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


class LiveCueTable(QTableWidget):
    """Specialized Live Show table with direct keyboard navigation, context actions, and click signals."""

    go_requested = Signal()
    panic_requested = Signal()
    standby_selected = Signal(int)
    fire_row_requested = Signal(int)
    group_collapse_toggled = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 6, parent)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.go_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.panic_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            curr = self.currentRow()
            if curr >= 0:
                self.standby_selected.emit(curr)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
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
        act_go = menu.addAction("▶ Fai partire subito questa Cue (GO Forzato)")
        act_go.triggered.connect(lambda: self.fire_row_requested.emit(row))

        act_sb = menu.addAction("🎯 Imposta come Prossima Cue (Standby)")
        act_sb.triggered.connect(lambda: self.standby_selected.emit(row))

        it_num = self.item(row, 0)
        if it_num and it_num.data(ROLE_IS_GROUP):
            menu.addSeparator()
            is_col = bool(it_num.data(ROLE_GROUP_COLLAPSED))
            act_toggle = menu.addAction("▼ Espandi Gruppo" if is_col else "▶ Collassa Gruppo")
            act_toggle.triggered.connect(lambda: self.group_collapse_toggled.emit(row))

        menu.exec(event.globalPos())


class LiveCueRowDelegate(QStyledItemDelegate):
    """High-contrast, distraction-free delegate for Live Show table with custom pills, tree branches, and timing."""

    _MEDIA_BADGE = {
        "VIDEO": ("VID", QColor("#0284c7"), QColor("#e0f2fe")),
        "AUDIO": ("AUD", QColor("#0d9488"), QColor("#ccfbf1")),
        "IMAGE": ("IMG", QColor("#d97706"), QColor("#fef3c7")),
        "GROUP": ("GRP", QColor("#6d28d9"), QColor("#ede9fe")),
    }

    _URGENT_NOTES_KEYWORDS = (
        "ATTENZIONE", "PERICOLO", "BUIO TOTALE", "STOP IMMEDIATO", "EMERGENZA", "AVVISO", "ALLARME"
    )

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
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

        # ── Col 0: # & Group Chevron & Link Rail ──────────────────────────────
        if col == 0:
            raw_num = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen_clr = QColor("#4ade80") if is_live else (QColor("#fcd34d") if is_standby else QColor("#94a3b8"))

            if is_group:
                arrow_sym = "▶" if is_collapsed else "▼"
                painter.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
                painter.setPen(QColor("#38bdf8"))
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

                painter.setPen(QPen(QColor("#0284c7"), 1))
                painter.setBrush(QColor("#082f49"))
                painter.drawRoundedRect(pill_rect, 4, 4)
                painter.setPen(QColor("#38bdf8"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, raw_q)
            else:
                painter.setFont(opt.font)
                painter.setPen(QColor("#334155"))
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
                painter.setPen(QColor("#64748b"))
                painter.drawText(
                    QRect(left_x, rect.top(), 24, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    branch_sym,
                )
                left_x += 20

            # Media badge pill
            if media_type in self._MEDIA_BADGE:
                tag_txt, bg_clr, fg_clr = self._MEDIA_BADGE[media_type]
                pill_w, pill_h = (34, 18) if is_group else (30, 18)
                pill_y = rect.top() + (rect.height() - pill_h) // 2
                pill_rect = QRect(left_x, pill_y, pill_w, pill_h)
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
                if group_mode in _GROUP_MODE_PILLS:
                    gm_txt, gm_bg, gm_fg = _GROUP_MODE_PILLS[group_mode]
                    painter.setFont(tag_font)
                    fm_gm = painter.fontMetrics()
                    gm_w = fm_gm.horizontalAdvance(gm_txt) + 12
                    gm_rect = QRect(right_x - gm_w, rect.top() + (rect.height() - 18) // 2, gm_w, 18)
                    painter.setPen(QPen(gm_fg, 1))
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
                    painter.setPen(QPen(QColor("#334155"), 1))
                    painter.setBrush(QColor("#0f172a"))
                    painter.drawRoundedRect(cc_rect, 3, 3)
                    painter.setPen(QColor("#94a3b8"))
                    painter.drawText(cc_rect, Qt.AlignmentFlag.AlignCenter, cc_txt)
                    right_x -= cc_w + 6
            else:
                if is_loop:
                    loop_txt = "🔁 LOOP"
                    painter.setFont(tag_font)
                    fm_lp = painter.fontMetrics()
                    lp_w = fm_lp.horizontalAdvance(loop_txt) + 10
                    lp_rect = QRect(right_x - lp_w, rect.top() + (rect.height() - 18) // 2, lp_w, 18)
                    painter.setPen(QPen(QColor("#d97706"), 1))
                    painter.setBrush(QColor("#451a03"))
                    painter.drawRoundedRect(lp_rect, 3, 3)
                    painter.setPen(QColor("#fbbf24"))
                    painter.drawText(lp_rect, Qt.AlignmentFlag.AlignCenter, loop_txt)
                    right_x -= lp_w + 6

                if sec_count > 0:
                    sec_txt = f"[{sec_count} sez.]"
                    painter.setFont(tag_font)
                    fm_sec = painter.fontMetrics()
                    sec_w = fm_sec.horizontalAdvance(sec_txt) + 8
                    sec_rect = QRect(right_x - sec_w, rect.top() + (rect.height() - 18) // 2, sec_w, 18)
                    painter.setPen(QPen(QColor("#334155"), 1))
                    painter.setBrush(QColor("#1e293b"))
                    painter.drawRoundedRect(sec_rect, 3, 3)
                    painter.setPen(QColor("#94a3b8"))
                    painter.drawText(sec_rect, Qt.AlignmentFlag.AlignCenter, sec_txt)
                    right_x -= sec_w + 6

            avail_w = max(24, right_x - left_x - 4)
            name_rect = QRect(left_x, rect.top(), avail_w, rect.height())
            name_font = QFont(opt.font)
            name_font.setPointSize(11)
            if is_live or is_standby or is_group or is_waiting:
                name_font.setBold(True)
            painter.setFont(name_font)

            if is_group:
                disp_name = name_text[2:].strip() if name_text.startswith("📁") else name_text
                name_clr = QColor("#c084fc")
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
                name_clr = QColor("#f8fafc")

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
                is_urgent = any(k in notes_text.upper() for k in self._URGENT_NOTES_KEYWORDS)

                if is_urgent:
                    painter.setPen(QPen(QColor("#d97706"), 1))
                    painter.setBrush(QColor(69, 26, 3, 160))
                    painter.drawRoundedRect(rect, 4, 4)

                painter.setFont(QFont(opt.font.family(), 9))
                painter.setPen(QColor("#f59e0b" if is_urgent else "#38bdf8"))
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
                painter.setPen(QColor("#334155"))
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
                painter.setPen(QPen(QColor("#d97706"), 1))
                painter.setBrush(QColor("#332006"))
                painter.drawRoundedRect(p_rect, 3, 3)
                painter.setPen(QColor("#fbbf24"))
                painter.drawText(p_rect, Qt.AlignmentFlag.AlignCenter, pre_txt)

            # Anchored duration slot (stable horizontal column across all rows)
            dur_x = rect.left() + 58
            dur_w = 54
            dur_rect = QRect(dur_x, rect.top(), dur_w, rect.height())
            dur_font = QFont("monospace", 10, QFont.Weight.Bold)
            painter.setFont(dur_font)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(dur_rect, Qt.AlignmentFlag.AlignCenter, dur_str)

            # Middle-right slot: Post-Delay pill (if configured)
            if post_delay > 0:
                post_txt = f"Post +{post_delay:.1f}s"
                painter.setFont(tag_font)
                post_w = min(60, painter.fontMetrics().horizontalAdvance(post_txt) + 8)
                post_x = dur_x + dur_w + 6
                post_rect = QRect(post_x, rect.top() + (rect.height() - 18) // 2, post_w, 18)
                painter.setPen(QPen(QColor("#7c3aed"), 1))
                painter.setBrush(QColor("#2e1065"))
                painter.drawRoundedRect(post_rect, 3, 3)
                painter.setPen(QColor("#c084fc"))
                painter.drawText(post_rect, Qt.AlignmentFlag.AlignCenter, post_txt)

            painter.restore()
            return

        # ── Col 5: Layer · Stato LIVE ─────────────────────────────────────────
        if col == 5:
            layer = int(index.data(ROLE_LAYER) or 1)
            phase_txt = str(index.data(ROLE_PHASE_TXT) or "")

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(6, 3, -6, -3)

            conflict_reason = str(index.data(ROLE_LAYER_CONFLICT) or "")
            if is_group:
                layer_txt = "⚠️ GRP" if conflict_reason else "GRP"
            else:
                layer_txt = f"⚠️ L{layer}" if conflict_reason else f"L{layer}"
            layer_font = QFont(opt.font)
            layer_font.setPointSize(8)
            layer_font.setBold(True)
            painter.setFont(layer_font)

            fm_lt = painter.fontMetrics()
            lw = fm_lt.horizontalAdvance(layer_txt) + 8
            lh = 18
            ly = rect.top() + (rect.height() - lh) // 2
            l_rect = QRect(rect.left(), ly, lw, lh)

            if conflict_reason:
                painter.setPen(QPen(QColor("#d97706"), 1))
                painter.setBrush(QColor("#451a03"))
                painter.drawRoundedRect(l_rect, 3, 3)
                painter.setPen(QColor("#fbbf24"))
            elif is_group:
                painter.setPen(QPen(QColor("#7c3aed"), 1))
                painter.setBrush(QColor("#2e1065"))
                painter.drawRoundedRect(l_rect, 3, 3)
                painter.setPen(QColor("#c084fc"))
            else:
                painter.setPen(QPen(QColor("#334155"), 1))
                painter.setBrush(QColor("#1e293b"))
                painter.drawRoundedRect(l_rect, 3, 3)
                painter.setPen(QColor("#94a3b8"))
            painter.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, layer_txt)

            tag_font = QFont(opt.font)
            tag_font.setPointSize(8.5)
            tag_font.setBold(True)
            painter.setFont(tag_font)

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
                st_fg = QColor("#64748b")

            fm_st = painter.fontMetrics()
            sw = max(72, fm_st.horizontalAdvance(st_label) + 12)
            sh = 20
            sx = rect.right() - sw
            sy = rect.top() + (rect.height() - sh) // 2
            s_rect = QRect(sx, sy, sw, sh)

            painter.setPen(QPen(st_border, 1.5 if (is_live or is_standby) else 1.0))
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
    cue_row_clicked = Signal(int)
    cue_row_double_clicked = Signal(int)
    group_collapse_toggled = Signal(int)
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

        self.lbl_show_badge = QLabel("● MODALITÀ LIVE (SHOW MODE)")
        self.lbl_show_badge.setFixedHeight(30)
        self.lbl_show_badge.setStyleSheet(
            "QLabel { background-color: #064e3b; color: #69f0ae; border: 1px solid #10b981; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 12px; }"
        )
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

        # Far away from bottom GO trigger: Crimson PANIC Stop button
        self.btn_panic = QPushButton("🚨  PANIC  —  STOP TOTALE   [ ESC ]")
        self.btn_panic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_panic.setFixedHeight(34)
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
        self.live_table.setColumnWidth(0, 60)
        self.live_table.setColumnWidth(1, 76)
        self.live_table.setColumnWidth(3, 260)
        self.live_table.setColumnWidth(4, 280)
        self.live_table.setColumnWidth(5, 160)
        self.live_table.setItemDelegate(LiveCueRowDelegate(self.live_table))

        self.live_table.cellClicked.connect(self._on_table_clicked)
        self.live_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.live_table.go_requested.connect(self.go_requested)
        self.live_table.panic_requested.connect(self.panic_requested)
        self.live_table.standby_selected.connect(self.cue_row_clicked)
        self.live_table.fire_row_requested.connect(self.cue_row_double_clicked)
        self.live_table.group_collapse_toggled.connect(self.group_collapse_toggled)
        root.addWidget(self.live_table, stretch=1)

        # Standby Hero Bar + optional Break Section Loop shortcut
        standby_bar = QFrame()
        standby_bar.setFixedHeight(40)
        standby_bar.setStyleSheet(
            "QFrame { background-color: #0b111a; border: 1px solid #1e2d42; border-radius: 6px; }"
        )
        sb_layout = QHBoxLayout(standby_bar)
        sb_layout.setContentsMargins(12, 2, 12, 2)
        sb_layout.setSpacing(10)

        self.lbl_standby_pill = QLabel("▶ STANDBY")
        self.lbl_standby_pill.setFixedHeight(26)
        self.lbl_standby_pill.setStyleSheet(
            "QLabel { background-color: #451a03; color: #fbbf24; border: 1px solid #d97706; "
            "border-radius: 4px; font-weight: bold; font-size: 11px; padding: 0px 8px; }"
        )
        sb_layout.addWidget(self.lbl_standby_pill)

        self.lbl_standby_banner = QLabel("Nessuna cue pronta in scaletta")
        self.lbl_standby_banner.setMinimumWidth(0)
        self.lbl_standby_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_standby_banner.setStyleSheet(
            "QLabel { color: #f8fafc; font-size: 13px; font-weight: bold; border: none; background: transparent; }"
        )
        sb_layout.addWidget(self.lbl_standby_banner, stretch=1)

        self.btn_break_loop = QPushButton("⏭ Esci da Loop Sezione")
        self.btn_break_loop.setVisible(False)
        self.btn_break_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_break_loop.setFixedHeight(26)
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

    def _on_table_clicked(self, row: int, col: int) -> None:
        if not self._updating_table and row >= 0:
            if col == 0:
                it = self.live_table.item(row, col)
                if it and it.data(ROLE_IS_GROUP):
                    self.group_collapse_toggled.emit(row)
                    return
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
        layer_conflicts: Optional[dict[int, Any]] = None,
    ) -> None:
        """Refresh the extended Live Scaletta table, standby banner, and GO target label."""
        self._updating_table = True
        try:
            self.live_table.setRowCount(len(cues))
            phases = phase_tags or {}
            conflicts = layer_conflicts or {}

            for r, cue in enumerate(cues):
                is_live = (cue.status == CueStatus.LIVE)
                is_standby = (r == standby_row and not is_live)
                phase_txt = phases.get(cue.cue_id, "")
                is_waiting = bool(phase_txt)
                is_group = (cue.media_type == MediaType.GROUP)

                # Duration string calculation
                dur_hint = known_durations.get(cue.file_path, 0.0)
                if is_group:
                    children = [c for c in cues if c.parent_id == cue.cue_id]
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
                    siblings = [c for c in cues if c.parent_id == cue.parent_id]
                    if siblings and siblings[-1].cue_id == cue.cue_id:
                        is_last_child = True

                cue_color = getattr(cue, "color", "") or ""
                prev_color = (getattr(cues[r - 1], "color", "") or "") if r > 0 else ""
                incoming_link = cues[r - 1].follow_mode if r > 0 else ""

                it_num = QTableWidgetItem(f"{r + 1}")
                it_q = QTableWidgetItem((cue.q_label or "").strip() or "—")
                it_name = QTableWidgetItem(cue.name)
                it_notes = QTableWidgetItem(cue.notes or "")
                it_timing = QTableWidgetItem(dur_str)
                it_state = QTableWidgetItem(
                    "LIVE" if is_live else ("STANDBY" if is_standby else ("ATTESA" if is_waiting else "PRONTO"))
                )

                conflict = conflicts.get(cue.cue_id)
                conflict_txt = conflict.reason if hasattr(conflict, "reason") else str(conflict or "")

                items = (it_num, it_q, it_name, it_notes, it_timing, it_state)
                for c_idx, it in enumerate(items):
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
                    it.setData(ROLE_MEDIA_TYPE, cue.media_type.value)
                    it.setData(ROLE_LAYER, cue.layer)
                    it.setData(ROLE_LAYER_CONFLICT, conflict_txt)
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
                    it.setData(
                        ROLE_STATUS_TXT,
                        "LIVE" if is_live else ("STANDBY" if is_standby else ("ATTESA" if is_waiting else "PRONTO")),
                    )
                    it.setData(
                        ROLE_STATUS_CLR,
                        "#4ade80" if is_live else ("#fcd34d" if is_standby else ("#7dd3fc" if is_waiting else "#94a3b8")),
                    )
                    if conflict_txt:
                        it.setToolTip(f"⚠️ {conflict_txt}")
                    self.live_table.setItem(r, c_idx, it)

                # Set row visibility based on parent collapsed state
                if cue.parent_id is not None:
                    parent = next((c for c in cues if c.cue_id == cue.parent_id), None)
                    self.live_table.setRowHidden(r, bool(parent and parent.collapsed))
                else:
                    self.live_table.setRowHidden(r, False)

            if 0 <= standby_row < len(cues):
                self.live_table.selectRow(standby_row)
                sb_cue = cues[standby_row]
                ref = format_cue_ref(standby_row, sb_cue)

                q_badge = f"[{sb_cue.q_label.strip()}] " if (sb_cue.q_label and sb_cue.q_label.strip()) else ""
                layer_badge = f"[L{sb_cue.layer}]" if sb_cue.media_type != MediaType.GROUP else "[SCENA]"
                type_map = {
                    MediaType.VIDEO: "VID",
                    MediaType.AUDIO: "AUD",
                    MediaType.IMAGE: "IMG",
                    MediaType.GROUP: "GRP",
                }
                type_tag = type_map.get(sb_cue.media_type, sb_cue.media_type.value[:3])

                extra_tags: list[str] = []
                if sb_cue.pre_delay > 0:
                    extra_tags.append(f"⏳ Pre +{sb_cue.pre_delay:.1f}s")
                if sb_cue.follow_mode == FollowMode.AUTO_FOLLOW.value:
                    extra_tags.append("⤵ Auto-GO al termine")
                elif sb_cue.follow_mode == FollowMode.SIMULTANEOUS.value:
                    extra_tags.append("⇉ + Cue successiva simultanea")
                if sb_cue.loop:
                    extra_tags.append("🔁 Loop")

                extras_str = ("   │   " + " · ".join(extra_tags)) if extra_tags else ""
                notes_str = f"   │   📝 Note: {sb_cue.notes}" if sb_cue.notes else ""

                self.lbl_standby_banner.setText(
                    f"PROSSIMA IN STANDBY:  #{standby_row + 1} {q_badge}'{sb_cue.name}'  {layer_badge} [{type_tag}]{extras_str}{notes_str}"
                )
                self.btn_go.setText(f"▶   GO:  {ref} '{sb_cue.name}'   [ SPAZIO ]")
            else:
                self.live_table.clearSelection()
                self.lbl_standby_banner.setText("Nessuna cue pronta in scaletta")
                self.btn_go.setText("▶   GO  —  PROSSIMA CUE   [ SPAZIO ]")

            self.btn_break_loop.setVisible(show_break_loop)
        finally:
            self._updating_table = False
