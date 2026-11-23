"""Operator note zone of the director window (never shown on the output).

An ACTION cue of kind "note" or "checklist" puts its text here when it fires:
"wait for Anna's entrance", "check the microphones". The zone sits above both
the design page and the LIVE page, does not block GO and never takes the
keyboard focus, so Space keeps meaning GO while a note is on screen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _text_colour_for(background: str) -> str:
    """Black or white text, whichever reads better on *background*."""
    col = QColor(background)
    if not col.isValid():
        return "#ffffff"
    luminance = 0.299 * col.red() + 0.587 * col.green() + 0.114 * col.blue()
    return "#111111" if luminance > 150 else "#ffffff"


class OperatorNoteBanner(QFrame):
    """Coloured strip with a note or a checklist for the operator."""

    dismissed = Signal(int)            # cue_id of the note that was closed
    item_toggled = Signal(int, int, bool)  # cue_id, item index, ticked

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (hidden) note zone."""
        super().__init__(parent)
        self.setObjectName("operatorNote")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setAccessibleName("Nota per la regia")
        self._cue_id: int = -1
        self._is_checklist = False
        self._active = False      # a note is up (shown here or on a card)
        self._docked = False      # in the show a plain note lives on a card of "Now playing"
        self._boxes: list[QCheckBox] = []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 6, 8, 6)
        outer.setSpacing(10)

        body = QVBoxLayout()
        body.setSpacing(3)
        self.lbl_title = QLabel()
        title_font = QFont(self.font())
        title_font.setPointSize(max(8, title_font.pointSize() - 1))
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(self.lbl_title)

        self.lbl_text = QLabel()
        self.lbl_text.setWordWrap(True)
        text_font = QFont(self.font())
        text_font.setPointSize(text_font.pointSize() + 4)
        text_font.setBold(True)
        self.lbl_text.setFont(text_font)
        # Typed by the operator: "<b>" or "&" are shown as written.
        self.lbl_text.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        body.addWidget(self.lbl_text)

        self._items_box = QWidget()
        self._items_layout = QVBoxLayout(self._items_box)
        self._items_layout.setContentsMargins(0, 2, 0, 0)
        self._items_layout.setSpacing(2)
        body.addWidget(self._items_box)
        outer.addLayout(body, stretch=1)

        self.btn_close = QPushButton("✕ Chiudi")
        self.btn_close.setToolTip("Nascondi la nota (non ferma niente)")
        self.btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.dismiss)
        outer.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignTop)

        self.hide()

    # ── State ─────────────────────────────────────────────────────────
    def is_shown(self) -> bool:
        """True while a note is up (also before the window itself is shown, or on a card)."""
        return self._active

    def text(self) -> str:
        """The note's text (for its card in the show)."""
        return self.lbl_text.text()

    def set_docked(self, docked: bool) -> None:
        """In the show a plain note goes to its card instead of this strip (C2a step 8)."""
        self._docked = bool(docked)
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        self.setVisible(self._active and not (self._docked and not self._is_checklist))

    def cue_id(self) -> int:
        """Cue whose note is shown, or -1."""
        return self._cue_id if self.is_shown() else -1

    def is_checklist(self) -> bool:
        """True while a checklist (not a plain note) is shown."""
        return self.is_shown() and self._is_checklist

    def ticked(self) -> tuple[int, int]:
        """(ticked, total) items of the checklist on screen."""
        return sum(1 for b in self._boxes if b.isChecked()), len(self._boxes)

    # ── Show / hide ───────────────────────────────────────────────────
    def show_note(
        self,
        cue_id: int,
        title: str,
        text: str,
        colour: str,
        items: list[str] | None = None,
        ticked: set[int] | None = None,
    ) -> None:
        """Show *text* (and *items* as tick boxes) on a *colour* background."""
        self._cue_id = int(cue_id)
        self._is_checklist = items is not None
        fg = _text_colour_for(colour)
        # Every child transparent: the theme paints plain QWidgets dark, which
        # hid the tick-box labels behind a black strip.
        self.setStyleSheet(
            f"QFrame#operatorNote {{ background-color: {colour}; border-radius: 6px; }}"
            " QFrame#operatorNote QWidget { background: transparent; }"
            f" QFrame#operatorNote QLabel, QFrame#operatorNote QCheckBox {{ color: {fg}; }}"
            " QFrame#operatorNote QCheckBox { font-size: 13px; font-weight: bold; spacing: 8px; }"
            f" QFrame#operatorNote QCheckBox::indicator {{ width: 16px; height: 16px;"
            f" border: 2px solid {fg}; border-radius: 3px; background: transparent; }}"
            f" QFrame#operatorNote QCheckBox::indicator:checked {{ background: {fg}; }}"
            f" QFrame#operatorNote QPushButton {{ color: {fg}; background: transparent;"
            f" border: 1px solid {fg}; border-radius: 4px; padding: 2px 8px; }}"
        )
        self.lbl_title.setText(title)
        self.lbl_text.setText(text)
        self.lbl_text.setVisible(bool(text.strip()))
        for box in self._boxes:
            self._items_layout.removeWidget(box)
            box.deleteLater()
        self._boxes = []
        for idx, line in enumerate(items or []):
            box = QCheckBox(line.replace("&", "&&"))  # "&" is not a shortcut marker here
            # Space must stay GO: a focused tick box would swallow it.
            box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setChecked(bool(ticked and idx in ticked))
            box.toggled.connect(lambda on, i=idx: self.item_toggled.emit(self._cue_id, i, on))
            self._items_layout.addWidget(box)
            self._boxes.append(box)
        self._items_box.setVisible(bool(self._boxes))
        self._active = True
        self._apply_visibility()

    def dismiss(self) -> None:
        """Hide the note (the operator closed it)."""
        if not self.is_shown():
            return
        cue_id = self._cue_id
        self._active = False
        self.hide()
        self.dismissed.emit(cue_id)
