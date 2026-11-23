"""3-column Cue Sequence Table widget and custom cell delegate (#, Q, Nome / Media)."""

from __future__ import annotations

import os

from PySide6.QtCore import QItemSelectionModel, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLineEdit,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QWidget,
)

from models.cue import Cue
from ui.theme import CLR_ACCENT, CLR_TEXT, CUE_COLOR_PALETTE, get_active_theme

# Custom item roles for Cue Tables (Col 2 stores cue.name in EditRole)
ROLE_MEDIA_TYPE = Qt.ItemDataRole.UserRole + 1
ROLE_LAYER = Qt.ItemDataRole.UserRole + 2
ROLE_HAS_NOTES = Qt.ItemDataRole.UserRole + 3
ROLE_STATUS_TXT = Qt.ItemDataRole.UserRole + 4
ROLE_STATUS_CLR = Qt.ItemDataRole.UserRole + 5
ROLE_FOLLOW_MODE = Qt.ItemDataRole.UserRole + 6
ROLE_TIMING_BADGE = Qt.ItemDataRole.UserRole + 7
ROLE_CUE_COLOR = Qt.ItemDataRole.UserRole + 8
ROLE_PREV_COLOR = Qt.ItemDataRole.UserRole + 9
ROLE_INCOMING_LINK = Qt.ItemDataRole.UserRole + 10
ROLE_PARENT_ID = Qt.ItemDataRole.UserRole + 11
ROLE_IS_GROUP = Qt.ItemDataRole.UserRole + 12
ROLE_GROUP_MODE = Qt.ItemDataRole.UserRole + 13
ROLE_GROUP_COLLAPSED = Qt.ItemDataRole.UserRole + 14
ROLE_CHILD_COUNT = Qt.ItemDataRole.UserRole + 15
ROLE_IS_LAST_CHILD = Qt.ItemDataRole.UserRole + 16
ROLE_SECTION_COUNT = Qt.ItemDataRole.UserRole + 17
ROLE_LOOP = Qt.ItemDataRole.UserRole + 18
ROLE_PRE_DELAY = Qt.ItemDataRole.UserRole + 19
ROLE_POST_DELAY = Qt.ItemDataRole.UserRole + 20
ROLE_DURATION_TXT = Qt.ItemDataRole.UserRole + 21
ROLE_NOTES_TXT = Qt.ItemDataRole.UserRole + 22
ROLE_IS_LIVE = Qt.ItemDataRole.UserRole + 23
ROLE_IS_STANDBY = Qt.ItemDataRole.UserRole + 24
ROLE_PHASE_TXT = Qt.ItemDataRole.UserRole + 25
ROLE_LAYER_CONFLICT = Qt.ItemDataRole.UserRole + 26
ROLE_TIMELINE_COMPOSED = Qt.ItemDataRole.UserRole + 27
ROLE_OUTPUT_TARGET = Qt.ItemDataRole.UserRole + 28
# Live timing, redrawn by the 10 Hz clock (engine/live_state.py) without a rebuild.
ROLE_LIVE_TIME = Qt.ItemDataRole.UserRole + 29       # short text ("-0:45"), "" when idle
ROLE_LIVE_FRACTION = Qt.ItemDataRole.UserRole + 30   # 0..1 played, -1 when unknown/idle
ROLE_LIVE_WARN = Qt.ItemDataRole.UserRole + 31       # ends in a few seconds, next GO is manual
ROLE_PLAYED = Qt.ItemDataRole.UserRole + 32          # started in this run of the show (✓, dimmed)


def paint_live_progress(painter: QPainter, rect: QRect, fraction: float, warn: bool) -> None:
    """Thin played-part bar along the bottom of a cue cell."""
    if fraction < 0:
        return
    bar = QRect(rect.left() + 2, rect.bottom() - 3, max(0, rect.width() - 4), 3)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 40))
    painter.drawRect(bar)
    painter.setBrush(QColor("#fbbf24" if warn else "#4ade80"))
    painter.drawRect(QRect(bar.left(), bar.top(), int(bar.width() * min(1.0, fraction)), bar.height()))
    painter.restore()

# Broadcast Default Media Badges (Obsidian Slate / Deep Indigo)
_MEDIA_BADGE_BROADCAST = {
    "VIDEO": ("VID", QColor("#0284c7"), QColor("#e0f2fe"), None),
    "AUDIO": ("AUD", QColor("#0d9488"), QColor("#ccfbf1"), None),
    "IMAGE": ("IMG", QColor("#d97706"), QColor("#fef3c7"), None),
    "GROUP": ("GRP", QColor("#6d28d9"), QColor("#ede9fe"), None),
    "ACTION": ("ACT", QColor("#be123c"), QColor("#ffe4e6"), None),
}

# Stepped Carbon/Graphite Monocromo Badges (WCAG AAA · Zero Chromatic Clutter)
_MEDIA_BADGE_CARBON_MONO = {
    "VIDEO": ("VID", QColor("#2d2f38"), QColor("#f4f4f5"), QColor("#525363")),
    "AUDIO": ("AUD", QColor("#22232a"), QColor("#d4d4d8"), QColor("#3f404d")),
    "IMAGE": ("IMG", QColor("#373844"), QColor("#ffffff"), QColor("#6b6d7c")),
    "GROUP": ("GRP", QColor("#18191f"), QColor("#e4e4e7"), QColor("#484956")),
    "ACTION": ("ACT", QColor("#26272e"), QColor("#ffffff"), QColor("#a1a1aa")),
}

# Backward compatibility alias
_MEDIA_BADGE = _MEDIA_BADGE_BROADCAST


def get_media_badge(media_type: str, is_mono: bool = False):
    """Return the (label, colour, background) badge for a media type.

    *is_mono* selects the high-contrast Carbon palette used by the live view.
    """
    badges = _MEDIA_BADGE_CARBON_MONO if is_mono else _MEDIA_BADGE_BROADCAST
    return badges.get(media_type)


_GROUP_MODE_PILLS_BROADCAST = {
    "SIMULTANEOUS": ("⇉ SIMULT", QColor("#065f46"), QColor("#34d399"), None),
    "SEQUENCE": ("⤵ CASCATA", QColor("#0c4a6e"), QColor("#38bdf8"), None),
    "STEP": ("⏹ PASSO", QColor("#312e81"), QColor("#a5b4fc"), None),
    "RANDOM": ("🎲 RND", QColor("#701a75"), QColor("#f472b6"), None),
    "LOOP": ("🔁 LOOP", QColor("#78350f"), QColor("#fbbf24"), None),
}

_GROUP_MODE_PILLS_CARBON_MONO = {
    "SIMULTANEOUS": ("⇉ SIMULT", QColor("#272832"), QColor("#f4f4f5"), QColor("#525363")),
    "SEQUENCE": ("⤵ CASCATA", QColor("#22232a"), QColor("#e4e4e7"), QColor("#484956")),
    "STEP": ("⏹ PASSO", QColor("#1e1f26"), QColor("#d4d4d8"), QColor("#3f404d")),
    "RANDOM": ("🎲 RND", QColor("#292a34"), QColor("#f4f4f5"), QColor("#585969")),
    "LOOP": ("🔁 LOOP", QColor("#2c2d37"), QColor("#ffffff"), QColor("#5c5e6f")),
}

# Backward compatibility alias
_GROUP_MODE_PILLS = _GROUP_MODE_PILLS_BROADCAST


def get_group_mode_pill(group_mode: str, is_mono: bool = False):
    """Return the (label, background, foreground, border) pill for a group mode."""
    pills = _GROUP_MODE_PILLS_CARBON_MONO if is_mono else _GROUP_MODE_PILLS_BROADCAST
    return pills.get(group_mode)


def get_link_rail_color(mode: str, is_mono: bool = False) -> QColor | None:
    """Colour of the rail linking a group cue to its children (``None`` = default)."""
    if is_mono:
        if mode == "AUTO_FOLLOW":
            return QColor("#ffffff")
        if mode == "SIMULTANEOUS":
            return QColor("#a1a1aa")
        return None
    if mode == "AUTO_FOLLOW":
        return QColor("#38bdf8")
    if mode == "SIMULTANEOUS":
        return QColor("#f59e0b")
    return None


_LINK_RAIL_COLORS = {
    "SIMULTANEOUS": QColor("#f59e0b"),
    "AUTO_FOLLOW": QColor("#38bdf8"),
}


def paint_cue_row_decorations(
    painter: QPainter,
    rect: QRect,
    index,
    *,
    is_selected: bool = False,
) -> None:
    """Paint group colour wash, top chapter divider, and left link-chain rail shared by Project & LIVE tables."""
    col = index.column()
    cue_color = str(index.data(ROLE_CUE_COLOR) or "")
    prev_color = str(index.data(ROLE_PREV_COLOR) or "")
    is_live = bool(index.data(ROLE_IS_LIVE))
    is_standby = bool(index.data(ROLE_IS_STANDBY))
    is_mono = get_active_theme().is_monochrome

    painter.save()
    if is_mono:
        # High-legibility monochrome decoration:
        # Subtle neutral graphite lift for color-tagged cues, without chromatic noise
        if cue_color:
            painter.fillRect(rect, QColor(255, 255, 255, 10 if is_selected else 16))
            if col == 0 and not is_live and not is_standby:
                painter.fillRect(rect.left(), rect.top() + 1, 4, rect.height() - 2, QColor("#525363"))

        if is_live:
            # Pure luminous white lift for LIVE in monochrome
            painter.fillRect(rect, QColor(255, 255, 255, 38))
            if col == 0:
                painter.fillRect(rect.left(), rect.top() + 1, 5, rect.height() - 2, QColor("#ffffff"))
        elif is_standby:
            # Crisp neutral silver lift for STANDBY
            painter.fillRect(rect, QColor(255, 255, 255, 20))
            if col == 0:
                painter.fillRect(rect.left(), rect.top() + 1, 5, rect.height() - 2, QColor("#d4d4d8"))

        if index.row() > 0 and cue_color != prev_color and (cue_color or prev_color):
            painter.setPen(QPen(QColor("#525363"), 1.5))
            painter.drawLine(rect.left(), rect.top() + 1, rect.right(), rect.top() + 1)
    else:
        if cue_color:
            wash = QColor(cue_color)
            if wash.isValid():
                wash.setAlpha(20 if is_selected else 30)
                painter.fillRect(rect, wash)
                if col == 0 and not is_live and not is_standby:
                    ribbon = QColor(cue_color)
                    painter.fillRect(rect.left(), rect.top() + 1, 4, rect.height() - 2, ribbon)

        if is_live:
            live_wash = QColor("#092919")
            live_wash.setAlpha(150)
            painter.fillRect(rect, live_wash)
            if col == 0:
                painter.fillRect(rect.left(), rect.top() + 1, 5, rect.height() - 2, QColor("#10b981"))
        elif is_standby:
            sb_wash = QColor("#261a08")
            sb_wash.setAlpha(160)
            painter.fillRect(rect, sb_wash)
            if col == 0:
                painter.fillRect(rect.left(), rect.top() + 1, 5, rect.height() - 2, QColor("#f59e0b"))

        if index.row() > 0 and cue_color != prev_color and (cue_color or prev_color):
            div_clr = QColor(cue_color or prev_color)
            if div_clr.isValid():
                div_clr.setAlpha(155)
                painter.setPen(QPen(div_clr, 1.5))
                painter.drawLine(rect.left(), rect.top() + 1, rect.right(), rect.top() + 1)

    if col == 0:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        incoming = str(index.data(ROLE_INCOMING_LINK) or "")
        outgoing = str(index.data(ROLE_FOLLOW_MODE) or "")
        rail_x = float(rect.left() + 11)
        mid_y = float(rect.center().y())

        in_clr = get_link_rail_color(incoming, is_mono)
        if in_clr is not None:
            painter.setPen(QPen(in_clr, 2.0))
            painter.drawLine(QPointF(rail_x, float(rect.top())), QPointF(rail_x, mid_y))
            painter.drawLine(QPointF(rail_x, mid_y), QPointF(rail_x + 6.0, mid_y))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(in_clr)
            arrow = QPolygonF([
                QPointF(rail_x + 8.5, mid_y),
                QPointF(rail_x + 4.5, mid_y - 3.2),
                QPointF(rail_x + 4.5, mid_y + 3.2),
            ])
            painter.drawPolygon(arrow)

        out_clr = get_link_rail_color(outgoing, is_mono)
        if out_clr is not None:
            painter.setPen(QPen(out_clr, 2.0))
            painter.drawLine(QPointF(rail_x, mid_y), QPointF(rail_x, float(rect.bottom()) + 0.5))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(out_clr)
            painter.drawEllipse(QPointF(rail_x, mid_y), 3.0, 3.0)

    painter.restore()


def format_cid(cue_id: object) -> str:
    """Format cue ID gracefully whether it is int or str."""
    if isinstance(cue_id, int):
        return f"{cue_id:03d}"
    if isinstance(cue_id, str) and cue_id.isdigit():
        return f"{int(cue_id):03d}"
    return str(cue_id)


def format_cue_ref(row_index: int, cue: Cue) -> str:
    """Return progressive '#row' plus script Q callout (if assigned)."""
    pos_str = f"#{row_index + 1}" if row_index >= 0 else f"#{format_cid(cue.cue_id)}"
    q_txt = (cue.q_label or "").strip()
    return f"{pos_str} {q_txt}" if q_txt else pos_str


class CueTableDelegate(QStyledItemDelegate):
    """Custom delegate for the 3-column cue table (#, Q, Nome / Media).

    - Col 0 (#): Progressive position number; draws a crisp left selection bar.
    - Col 1 (Q): Script callout; paints muted '—' when empty while leaving EditRole blank.
    - Col 2 (Nome / Media): Stores raw editable cue.name cleanly in EditRole/text,
      while painting media type badge, elided cue name, layer pill, and LIVE/STANDBY badge.
    """

    _MEDIA_BADGE = {
        "VIDEO": ("VID", QColor("#0284c7"), QColor("#e0f2fe")),
        "AUDIO": ("AUD", QColor("#0d9488"), QColor("#ccfbf1")),
        "IMAGE": ("IMG", QColor("#d97706"), QColor("#fef3c7")),
        "GROUP": ("GRP", QColor("#6d28d9"), QColor("#ede9fe")),
    }

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        """Attach the custom background brush computed in :meth:`paint`."""
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        """Draw one cue row: coloured status band, live badge and inline editor."""
        col = index.column()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else QApplication.style()
        is_mono = get_active_theme().is_monochrome

        if col == 0:
            raw_num = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            fg_brush = index.data(Qt.ItemDataRole.ForegroundRole)
            is_group = bool(index.data(ROLE_IS_GROUP))
            is_collapsed = bool(index.data(ROLE_GROUP_COLLAPSED))
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            is_sel = bool(opt.state & QStyle.StateFlag.State_Selected)
            paint_cue_row_decorations(painter, opt.rect, index, is_selected=is_sel)
            painter.save()
            if is_sel and not str(index.data(ROLE_CUE_COLOR) or ""):
                painter.fillRect(
                    opt.rect.left(), opt.rect.top() + 2, 3, opt.rect.height() - 4,
                    QColor(CLR_ACCENT),
                )
            painter.setFont(opt.font)
            pen_clr = fg_brush.color() if fg_brush is not None else QColor("#94a3b8")

            if is_group:
                arrow_sym = "▶" if is_collapsed else "▼"
                painter.setPen(QColor("#ffffff" if is_mono else "#38bdf8"))
                painter.drawText(
                    opt.rect.adjusted(4, 0, -28, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    arrow_sym,
                )
                painter.setPen(pen_clr)
                painter.drawText(
                    opt.rect.adjusted(16, 0, -2, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    raw_num,
                )
            else:
                painter.setPen(pen_clr)
                painter.drawText(
                    opt.rect.adjusted(18, 0, -2, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    raw_num,
                )
            painter.restore()
            return

        if col == 1:
            raw_q = str(index.data(Qt.ItemDataRole.EditRole) or "").strip()
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(
                painter, opt.rect, index, is_selected=bool(opt.state & QStyle.StateFlag.State_Selected)
            )
            painter.save()
            font = QFont(opt.font)
            if raw_q:
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor(CLR_ACCENT))
                painter.drawText(
                    opt.rect.adjusted(3, 0, -3, 0),
                    Qt.AlignmentFlag.AlignCenter, raw_q,
                )
            else:
                painter.setFont(font)
                painter.setPen(QColor("#475569"))
                painter.drawText(
                    opt.rect.adjusted(3, 0, -3, 0),
                    Qt.AlignmentFlag.AlignCenter, "—",
                )
            painter.restore()
            return

        if col == 2:
            name_text = str(index.data(Qt.ItemDataRole.EditRole) or "")
            media_type = str(index.data(ROLE_MEDIA_TYPE) or "")
            is_group = bool(index.data(ROLE_IS_GROUP))
            parent_id = index.data(ROLE_PARENT_ID)
            child_count = int(index.data(ROLE_CHILD_COUNT) or 0)
            group_mode = str(index.data(ROLE_GROUP_MODE) or "STEP")
            is_last_child = bool(index.data(ROLE_IS_LAST_CHILD))
            layer = int(index.data(ROLE_LAYER) or 1)
            has_notes = bool(index.data(ROLE_HAS_NOTES))
            status_txt = str(index.data(ROLE_STATUS_TXT) or "")
            status_clr = str(index.data(ROLE_STATUS_CLR) or CLR_TEXT)
            follow_mode = str(index.data(ROLE_FOLLOW_MODE) or "MANUAL")
            timing_badge = str(index.data(ROLE_TIMING_BADGE) or "")
            is_mono = get_active_theme().is_monochrome

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
            paint_cue_row_decorations(
                painter, opt.rect, index, is_selected=bool(opt.state & QStyle.StateFlag.State_Selected)
            )

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(5, 3, -5, -3)

            left_x = rect.left()

            # Indent child cue and draw tree connector branch
            if parent_id is not None:
                branch_sym = "└── " if is_last_child else "├── "
                painter.setFont(QFont("monospace", 9))
                painter.setPen(QColor("#64748b"))
                painter.drawText(
                    QRect(left_x, rect.top(), 22, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    branch_sym,
                )
                left_x += 18

            badge_info = get_media_badge(media_type, is_mono)
            if badge_info:
                tag_txt, bg_clr, fg_clr, border_clr = badge_info
                pill_w, pill_h = (32, 16) if is_group else (28, 16)
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
                left_x += pill_w + 6

            right_x = rect.right()
            tag_font = QFont(opt.font)
            tag_font.setPointSize(8)
            tag_font.setBold(True)

            if status_txt:
                painter.setFont(tag_font)
                fm_tag = painter.fontMetrics()
                sw = fm_tag.horizontalAdvance(status_txt) + 10
                sh = 16
                sy = rect.top() + (rect.height() - sh) // 2
                s_rect = QRect(right_x - sw, sy, sw, sh)
                if is_mono:
                    if status_txt == "LIVE":
                        s_bg = QColor("#2c2d36")
                        s_border = QColor("#ffffff")
                        s_fg = QColor("#ffffff")
                    else:
                        s_bg = QColor("#22232a")
                        s_border = QColor("#d4d4d8")
                        s_fg = QColor("#f4f4f5")
                else:
                    s_bg = QColor("#064e3b") if status_txt == "LIVE" else QColor("#451a03")
                    s_border = QColor(status_clr)
                    s_fg = QColor(status_clr)
                painter.setPen(QPen(s_border, 1.5 if is_mono and status_txt == "LIVE" else 1.0))
                painter.setBrush(s_bg)
                painter.drawRoundedRect(s_rect, 3, 3)
                painter.setPen(s_fg)
                painter.drawText(s_rect, Qt.AlignmentFlag.AlignCenter, status_txt)
                right_x -= sw + 4

            conflict_reason = str(index.data(ROLE_LAYER_CONFLICT) or "")
            out_target = str(index.data(ROLE_OUTPUT_TARGET) or "A").upper()
            layer_prefix = "B·" if out_target == "B" else ""

            if is_group:
                # Group mode pill on the right
                gm_info = get_group_mode_pill(group_mode, is_mono)
                if gm_info:
                    gm_txt, gm_bg, gm_fg, gm_border_spec = gm_info
                    gm_border = gm_border_spec or gm_fg
                    if conflict_reason:
                        gm_txt = f"⚠️ {gm_txt}"
                        gm_bg = QColor("#2c2d36") if is_mono else QColor("#451a03")
                        gm_fg = QColor("#f4f4f5") if is_mono else QColor("#fbbf24")
                        gm_border = QColor("#a1a1aa") if is_mono else QColor("#d97706")
                    painter.setFont(tag_font)
                    fm_gm = painter.fontMetrics()
                    gm_w = fm_gm.horizontalAdvance(gm_txt) + 10
                    gm_rect = QRect(right_x - gm_w, rect.top() + (rect.height() - 16) // 2, gm_w, 16)
                    painter.setPen(QPen(gm_border, 1))
                    painter.setBrush(gm_bg)
                    painter.drawRoundedRect(gm_rect, 3, 3)
                    painter.setPen(gm_fg)
                    painter.drawText(gm_rect, Qt.AlignmentFlag.AlignCenter, gm_txt)
                    right_x -= gm_w + 4

                if bool(index.data(ROLE_TIMELINE_COMPOSED)):
                    tc_txt = "🎬 MULTI-TRACK"
                    painter.setFont(tag_font)
                    fm_tc = painter.fontMetrics()
                    tc_w = fm_tc.horizontalAdvance(tc_txt) + 10
                    tc_rect = QRect(right_x - tc_w, rect.top() + (rect.height() - 16) // 2, tc_w, 16)
                    tc_border = QColor("#525363") if is_mono else QColor("#6366f1")
                    tc_bg = QColor("#22232a") if is_mono else QColor("#1e1b4b")
                    tc_fg = QColor("#f4f4f5") if is_mono else QColor("#a5b4fc")
                    painter.setPen(QPen(tc_border, 1))
                    painter.setBrush(tc_bg)
                    painter.drawRoundedRect(tc_rect, 3, 3)
                    painter.setPen(tc_fg)
                    painter.drawText(tc_rect, Qt.AlignmentFlag.AlignCenter, tc_txt)
                    right_x -= tc_w + 4

                if child_count > 0:
                    cc_txt = f"{child_count} Cue"
                    painter.setFont(tag_font)
                    fm_cc = painter.fontMetrics()
                    cc_w = fm_cc.horizontalAdvance(cc_txt) + 10
                    cc_rect = QRect(right_x - cc_w, rect.top() + (rect.height() - 16) // 2, cc_w, 16)
                    painter.setPen(QPen(QColor("#3f404d") if is_mono else QColor("#334155"), 1))
                    painter.setBrush(QColor("#18191f") if is_mono else QColor("#0f172a"))
                    painter.drawRoundedRect(cc_rect, 3, 3)
                    painter.setPen(QColor("#a1a1aa") if is_mono else QColor("#94a3b8"))
                    painter.drawText(cc_rect, Qt.AlignmentFlag.AlignCenter, cc_txt)
                    right_x -= cc_w + 4
            else:
                lh = 16
                if media_type == "ACTION":
                    pass  # an action cue has no layer of its own
                elif conflict_reason:
                    layer_str = f"⚠️ {layer_prefix}L{layer}"
                    painter.setFont(tag_font)
                    lw = painter.fontMetrics().horizontalAdvance(layer_str) + 8
                    lh = 16
                    ly = rect.top() + (rect.height() - lh) // 2
                    l_rect = QRect(right_x - lw, ly, lw, lh)
                    l_border = QColor("#a1a1aa") if is_mono else QColor("#d97706")
                    l_bg = QColor("#2c2d36") if is_mono else QColor("#451a03")
                    l_fg = QColor("#f4f4f5") if is_mono else QColor("#fbbf24")
                    painter.setPen(QPen(l_border, 1))
                    painter.setBrush(l_bg)
                    painter.drawRoundedRect(l_rect, 3, 3)
                    painter.setPen(l_fg)
                    painter.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, layer_str)
                    right_x -= lw + 4
                else:
                    layer_str = f"{layer_prefix}L{layer}"
                    painter.setFont(tag_font)
                    lw = painter.fontMetrics().horizontalAdvance(layer_str) + 8
                    lh = 16
                    ly = rect.top() + (rect.height() - lh) // 2
                    l_rect = QRect(right_x - lw, ly, lw, lh)
                    l_border = QColor("#3f404d") if is_mono else QColor("#283548")
                    l_bg = QColor("#22232a") if is_mono else QColor("#1a2332")
                    l_fg = QColor("#d4d4d8") if is_mono else QColor("#94a3b8")
                    painter.setPen(QPen(l_border, 1))
                    painter.setBrush(l_bg)
                    painter.drawRoundedRect(l_rect, 3, 3)
                    painter.setPen(l_fg)
                    painter.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, layer_str)
                    right_x -= lw + 4

                if follow_mode == "AUTO_FOLLOW":
                    fw = 46
                    fy = rect.top() + (rect.height() - lh) // 2
                    f_rect = QRect(right_x - fw, fy, fw, lh)
                    f_border = QColor("#ffffff" if is_mono else "#38bdf8")
                    f_bg = QColor("#1e1f26") if is_mono else QColor("#0c2638")
                    f_fg = QColor("#ffffff") if is_mono else QColor("#7dd3fc")
                    painter.setPen(QPen(f_border, 1))
                    painter.setBrush(f_bg)
                    painter.drawRoundedRect(f_rect, 3, 3)
                    painter.setPen(f_fg)
                    painter.drawText(f_rect, Qt.AlignmentFlag.AlignCenter, "⤵ AUTO")
                    right_x -= fw + 4
                elif follow_mode == "SIMULTANEOUS":
                    fw = 42
                    fy = rect.top() + (rect.height() - lh) // 2
                    f_rect = QRect(right_x - fw, fy, fw, lh)
                    f_border = QColor("#525363") if is_mono else QColor("#f59e0b")
                    f_bg = QColor("#22232a") if is_mono else QColor("#332006")
                    f_fg = QColor("#e4e4e7") if is_mono else QColor("#fcd34d")
                    painter.setPen(QPen(f_border, 1))
                    painter.setBrush(f_bg)
                    painter.drawRoundedRect(f_rect, 3, 3)
                    painter.setPen(f_fg)
                    painter.drawText(f_rect, Qt.AlignmentFlag.AlignCenter, "⇉ SIM")
                    right_x -= fw + 4

            min_name_end = left_x + 52
            if timing_badge and right_x - 18 >= min_name_end:
                tw = 16
                ty = rect.top() + (rect.height() - 16) // 2
                t_rect = QRect(right_x - tw, ty, tw, 16)
                painter.setPen(QColor("#d4d4d8" if is_mono else "#a78bfa"))
                painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, timing_badge)
                right_x -= tw + 2

            if has_notes and right_x - 18 >= min_name_end:
                nw = 16
                ny = rect.top() + (rect.height() - 16) // 2
                n_rect = QRect(right_x - nw, ny, nw, 16)
                painter.setPen(QColor("#ffffff" if is_mono else "#38bdf8"))
                painter.drawText(n_rect, Qt.AlignmentFlag.AlignCenter, "📝")
                right_x -= nw + 4

            avail_w = max(24, right_x - left_x - 4)
            name_rect = QRect(left_x, rect.top(), avail_w, rect.height())
            name_font = QFont(opt.font)
            if status_txt in ("LIVE", "STANDBY") or is_group:
                name_font.setBold(True)
            painter.setFont(name_font)
            disp_name = ("📁 " + name_text) if (is_group and not name_text.startswith("📁")) else name_text
            elided_name = painter.fontMetrics().elidedText(
                disp_name, Qt.TextElideMode.ElideRight, avail_w
            )
            if is_mono:
                name_clr = QColor("#ffffff") if (status_txt == "LIVE" or is_group) else (
                    QColor("#f4f4f5") if status_txt == "STANDBY" else QColor("#e4e4e7")
                )
            else:
                name_clr = QColor("#c084fc") if is_group else QColor(status_clr)
            painter.setPen(name_clr)
            painter.drawText(
                name_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided_name,
            )
            painter.restore()
            fraction = index.data(ROLE_LIVE_FRACTION)
            if fraction is not None:
                paint_live_progress(painter, opt.rect, float(fraction), bool(index.data(ROLE_LIVE_WARN)))
            return

        super().paint(painter, option, index)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index) -> QLineEdit:  # noqa: N802
        """Create the inline editor for the Q and Name columns only."""
        editor = QLineEdit(parent)
        active_t = get_active_theme()
        editor.setStyleSheet(
            f"QLineEdit {{ background-color: {active_t.input_bg}; border: 1px solid {active_t.accent}; "
            f"color: {active_t.text}; padding: 1px 6px; font-weight: bold; border-radius: 3px; }}"
        )
        if index.column() == 1:
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            editor.setPlaceholderText("Q-...")
        return editor

    def setEditorData(self, editor: QLineEdit, index) -> None:  # noqa: N802
        """Seed the inline editor with the current cell text."""
        val = str(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.setText(val)
        editor.selectAll()

    def setModelData(self, editor: QLineEdit, model, index) -> None:  # noqa: N802
        """Commit the edited text back to the cue table model."""
        model.setData(index, editor.text().strip(), Qt.ItemDataRole.EditRole)


class CueSequenceTable(QTableWidget):
    """Three-column cue sequence table (#, Q, Nome / Media) with row-level selection signal."""

    currentRowChanged = Signal(int)
    color_selected = Signal(str)
    group_collapse_toggled = Signal(int)
    group_requested = Signal()
    ungroup_requested = Signal()
    extract_child_requested = Signal()
    open_timeline_requested = Signal()
    edit_text_requested = Signal()
    # Media files dropped on the list: (paths, row they were dropped on, -1 = below the last row)
    files_dropped = Signal(list, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the cue sequence table with its three columns and selection rules."""
        super().__init__(0, 3, parent)
        self._last_emitted_row: int = -1

        self.setHorizontalHeaderLabels(["#", "Q", "Nome / Media"])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        hdr = self.horizontalHeader()
        hdr.setHighlightSections(False)
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 50)
        self.setColumnWidth(1, 52)

        self.horizontalHeaderItem(0).setToolTip("Numero progressivo di posizione in scaletta (doppio click = GO)")
        self.horizontalHeaderItem(1).setToolTip("Richiamo copione Q (doppio click per modificare)")
        self.horizontalHeaderItem(2).setToolTip(
            "Nome personalizzato scena / file (doppio click per rinominare; Ctrl/Shift+Click per selezione multipla)"
        )

        self.setItemDelegate(CueTableDelegate(self))
        self.currentCellChanged.connect(self._on_current_cell_changed)
        # Files from the file manager can be dropped straight on the list
        # (the rows themselves are not dragged: order changes use Up/Down).
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDropIndicatorShown(True)

    @staticmethod
    def _dropped_files(event) -> list[str]:
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_files(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._dropped_files(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = self._dropped_files(event)
        if not paths:
            event.ignore()
            return
        row = self.rowAt(event.position().toPoint().y())
        event.acceptProposedAction()
        self.files_dropped.emit(paths, row)

    def _on_current_cell_changed(self, curr_row: int, _curr_col: int,
                                 prev_row: int, _prev_col: int) -> None:
        if curr_row != prev_row or curr_row != self._last_emitted_row:
            self._last_emitted_row = curr_row
            self.currentRowChanged.emit(curr_row)

    def selected_rows(self) -> list[int]:
        """Return sorted unique row indices currently selected."""
        sm = self.selectionModel()
        if sm is None:
            row = self.currentRow()
            return [row] if row >= 0 else []
        return sorted({idx.row() for idx in sm.selectedRows() if 0 <= idx.row() < self.rowCount()})

    def select_rows(self, rows: list[int], anchor_row: int | None = None) -> None:
        """Select *rows* programmatically cleanly while preserving an anchor row."""
        valid = [r for r in rows if 0 <= r < self.rowCount()]
        if not valid:
            self._last_emitted_row = -1
            self.clearSelection()
            self.setCurrentCell(-1, -1)
            return
        anchor = anchor_row if (anchor_row is not None and anchor_row in valid) else valid[0]
        if self.signalsBlocked():
            self._last_emitted_row = anchor
        sm = self.selectionModel()
        if sm is not None:
            sm.setCurrentIndex(
                self.model().index(anchor, 1),
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
            for r in valid:
                if r != anchor:
                    sm.select(
                        self.model().index(r, 0),
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                    )
        else:
            self.setCurrentCell(anchor, 1)

    def setCurrentRow(self, row: int) -> None:  # noqa: N802
        """Select strictly the given row atomically (compatible with QListWidget API)."""
        if 0 <= row < self.rowCount():
            if self.signalsBlocked():
                self._last_emitted_row = row
            sm = self.selectionModel()
            if sm is not None:
                sm.setCurrentIndex(
                    self.model().index(row, 1),
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
            else:
                self.clearSelection()
                self.setCurrentCell(row, 1)
                self.selectRow(row)
        else:
            self._last_emitted_row = -1
            self.clearSelection()
            self.setCurrentCell(-1, -1)

    def clear(self) -> None:
        """Clear all rows while preserving the 3 column headers."""
        self._last_emitted_row = -1
        self.setRowCount(0)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Collapse/expand group cues and start the anchor selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())
            if idx.isValid() and idx.column() == 0:
                is_grp = bool(idx.data(ROLE_IS_GROUP))
                if is_grp:
                    self.group_collapse_toggled.emit(idx.row())
                    event.accept()
                    return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Right-click menu for the selected cue(s): edit, duplicate, delete."""
        rows = self.selected_rows()
        if not rows:
            idx = self.indexAt(event.pos())
            if idx.isValid():
                self.setCurrentRow(idx.row())
                rows = [idx.row()]
        if not rows:
            return

        menu = QMenu(self)

        # Group actions
        if len(rows) > 0:
            curr_item = self.item(rows[0], 2)
            is_grp = bool(curr_item and curr_item.data(ROLE_IS_GROUP))
            parent_id = curr_item.data(ROLE_PARENT_ID) if curr_item else None

            if not is_grp and len(rows) == 1:
                act_text = menu.addAction("✏ Modifica testo…")
                act_text.triggered.connect(self.edit_text_requested)
            if not is_grp:
                act_grp = menu.addAction("📁 Raggruppa in Scena (Ctrl+G)")
                act_grp.triggered.connect(self.group_requested)

            if is_grp:
                act_timeline = menu.addAction("🎬 Apri Studio Timeline Gruppo…")
                act_timeline.triggered.connect(self.open_timeline_requested)
                act_toggle = menu.addAction("▶ / ▼ Espandi o Collassa Gruppo")
                act_toggle.triggered.connect(lambda: self.group_collapse_toggled.emit(rows[0]))
                act_ungrp = menu.addAction("🔓 Sciogli Gruppo (Ctrl+Shift+G)")
                act_ungrp.triggered.connect(self.ungroup_requested)
            elif parent_id is not None:
                act_extract = menu.addAction("⏏ Estrai dal Gruppo (Ctrl+Shift+G)")
                act_extract.triggered.connect(self.extract_child_requested)

            menu.addSeparator()

        color_menu = menu.addMenu("🎨 Colore Scena / Gruppo")
        for hex_val, label in CUE_COLOR_PALETTE:
            pm = QPixmap(14, 14)
            pm.fill(QColor(hex_val) if hex_val else QColor("#283548"))
            act = color_menu.addAction(QIcon(pm), label)
            act.triggered.connect(lambda _=False, clr=hex_val: self.color_selected.emit(clr))
        menu.exec(event.globalPos())

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Keyboard navigation: arrows move the anchor, Enter starts editing."""
        if event.key() == Qt.Key.Key_F2 and self.currentRow() >= 0 and self.currentColumn() == 0:
            item_q = self.item(self.currentRow(), 1)
            if item_q is not None:
                self.setCurrentCell(self.currentRow(), 1)
                self.editItem(item_q)
                return
        if event.key() == Qt.Key.Key_Space and self.state() != QAbstractItemView.State.EditingState:
            event.ignore()
            return
        super().keyPressEvent(event)

