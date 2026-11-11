"""3-column Cue Sequence Table widget and custom cell delegate (#, Q, Nome / Media)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QItemSelectionModel, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QWidget,
)

from models.cue import Cue
from ui.theme import CLR_ACCENT, CLR_TEXT

# Custom item roles for the 3-column Cue Sequence Table (Col 2 stores cue.name in EditRole)
ROLE_MEDIA_TYPE = Qt.ItemDataRole.UserRole + 1
ROLE_LAYER = Qt.ItemDataRole.UserRole + 2
ROLE_HAS_NOTES = Qt.ItemDataRole.UserRole + 3
ROLE_STATUS_TXT = Qt.ItemDataRole.UserRole + 4
ROLE_STATUS_CLR = Qt.ItemDataRole.UserRole + 5


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
    }

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        col = index.column()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else QApplication.style()

        if col == 0:
            super().paint(painter, opt, index)
            if opt.state & QStyle.StateFlag.State_Selected:
                painter.save()
                painter.fillRect(
                    opt.rect.left(), opt.rect.top() + 2, 3, opt.rect.height() - 4,
                    QColor(CLR_ACCENT),
                )
                painter.restore()
            return

        if col == 1:
            raw_q = str(index.data(Qt.ItemDataRole.EditRole) or "").strip()
            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
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
            layer = int(index.data(ROLE_LAYER) or 1)
            has_notes = bool(index.data(ROLE_HAS_NOTES))
            status_txt = str(index.data(ROLE_STATUS_TXT) or "")
            status_clr = str(index.data(ROLE_STATUS_CLR) or CLR_TEXT)

            opt.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = opt.rect.adjusted(5, 3, -5, -3)

            left_x = rect.left()
            if media_type in self._MEDIA_BADGE:
                tag_txt, bg_clr, fg_clr = self._MEDIA_BADGE[media_type]
                pill_w, pill_h = 28, 16
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
                s_bg = QColor("#064e3b") if status_txt == "LIVE" else QColor("#451a03")
                s_fg = QColor(status_clr)
                painter.setPen(QPen(s_fg, 1))
                painter.setBrush(s_bg)
                painter.drawRoundedRect(s_rect, 3, 3)
                painter.setPen(s_fg)
                painter.drawText(s_rect, Qt.AlignmentFlag.AlignCenter, status_txt)
                right_x -= sw + 4

            layer_str = f"L{layer}"
            painter.setFont(tag_font)
            lw, lh = 22, 16
            ly = rect.top() + (rect.height() - lh) // 2
            l_rect = QRect(right_x - lw, ly, lw, lh)
            painter.setPen(QPen(QColor("#283548"), 1))
            painter.setBrush(QColor("#1a2332"))
            painter.drawRoundedRect(l_rect, 3, 3)
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(l_rect, Qt.AlignmentFlag.AlignCenter, layer_str)
            right_x -= lw + 4

            if has_notes:
                nw = 16
                ny = rect.top() + (rect.height() - lh) // 2
                n_rect = QRect(right_x - nw, ny, nw, lh)
                painter.setPen(QColor("#38bdf8"))
                painter.drawText(n_rect, Qt.AlignmentFlag.AlignCenter, "📝")
                right_x -= nw + 4

            avail_w = max(20, right_x - left_x - 4)
            name_rect = QRect(left_x, rect.top(), avail_w, rect.height())
            name_font = QFont(opt.font)
            if status_txt in ("LIVE", "STANDBY"):
                name_font.setBold(True)
            painter.setFont(name_font)
            elided_name = painter.fontMetrics().elidedText(
                name_text, Qt.TextElideMode.ElideRight, avail_w
            )
            painter.setPen(QColor(status_clr))
            painter.drawText(
                name_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided_name,
            )
            painter.restore()
            return

        super().paint(painter, option, index)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index) -> QLineEdit:  # noqa: N802
        editor = QLineEdit(parent)
        editor.setStyleSheet(
            "QLineEdit { background-color: #0f1520; border: 1px solid #38bdf8; "
            "color: #ffffff; padding: 1px 6px; font-weight: bold; border-radius: 3px; }"
        )
        if index.column() == 1:
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            editor.setPlaceholderText("Q-...")
        return editor

    def setEditorData(self, editor: QLineEdit, index) -> None:  # noqa: N802
        val = str(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.setText(val)
        editor.selectAll()

    def setModelData(self, editor: QLineEdit, model, index) -> None:  # noqa: N802
        model.setData(index, editor.text().strip(), Qt.ItemDataRole.EditRole)


class CueSequenceTable(QTableWidget):
    """Three-column cue sequence table (#, Q, Nome / Media) with row-level selection signal."""

    currentRowChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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
        self.setColumnWidth(0, 42)
        self.setColumnWidth(1, 72)

        self.horizontalHeaderItem(0).setToolTip("Numero progressivo di posizione in scaletta (doppio click = GO)")
        self.horizontalHeaderItem(1).setToolTip("Richiamo copione Q (doppio click per modificare)")
        self.horizontalHeaderItem(2).setToolTip(
            "Nome personalizzato scena / file (doppio click per rinominare; Ctrl/Shift+Click per selezione multipla)"
        )

        self.setItemDelegate(CueTableDelegate(self))
        self.currentCellChanged.connect(self._on_current_cell_changed)

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

    def select_rows(self, rows: list[int], anchor_row: Optional[int] = None) -> None:
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

    def keyPressEvent(self, event) -> None:  # noqa: N802
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

