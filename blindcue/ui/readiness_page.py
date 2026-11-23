"""The "Before the show" page (stage 1 C2a step 7).

Shown in place of the cue list, never as a modal window: PANIC, Fade All and
the rest of the window keep working. Each row says YES / NO / NOT CHECKED in
a word and an icon (never only a colour) and offers its fix; the page ends
with the start buttons of the start question, so entering the show is one
decision. Enter (and Space, which is GO elsewhere) presses the default
button: a start when everything is right, otherwise "Check again" – starting
anyway needs Tab + Enter on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.readiness import INFO, OK, PROBLEM, SKIPPED
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_WORDS = {OK: "✓ SÌ", PROBLEM: "✗ NO", SKIPPED: "– NON VERIFICATO", INFO: "ℹ"}
_COLOURS = {OK: "#69f0ae", PROBLEM: "#fbbf24", SKIPPED: "#94a3b8", INFO: "#93c5fd"}


@dataclass
class RowView:
    """One row as the page shows it (texts already in the operator's language)."""

    key: str
    state: str
    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)  # (label, action)
    items: list[str] = field(default_factory=list)                 # checklist items
    ticked: set[int] = field(default_factory=set)
    cue_id: int = -1                                                # checklist cue


class ReadinessPage(QWidget):
    """Rows of the readiness check and the way into the show."""

    action_requested = Signal(str)               # fix / check button of a row
    start_chosen = Signal(int)                   # row the show starts from
    stay_requested = Signal()                    # stay in Preparation / back to the show
    checklist_toggled = Signal(int, int, bool)   # cue_id, item, ticked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("readinessPage")
        self.setAccessibleName("Prima dello spettacolo")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        self.lbl_title = QLabel("Prima dello spettacolo")
        self.lbl_title.setStyleSheet("QLabel { color: #f8fafc; font-size: 20px; font-weight: bold; }")
        root.addWidget(self.lbl_title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_box = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_box)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        self._scroll.setWidget(self._rows_box)
        root.addWidget(self._scroll, stretch=1)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet("QLabel { color: #f8fafc; font-size: 15px; font-weight: bold; }")
        root.addWidget(self.lbl_summary)

        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(10)
        root.addLayout(self._buttons)

        self.rows: list[RowView] = []
        self.start_buttons: list[QPushButton] = []
        self.btn_recheck: QPushButton | None = None
        self.btn_stay: QPushButton | None = None
        self.row_buttons: dict[str, QPushButton] = {}
        self._default: QPushButton | None = None

    # ── Content ───────────────────────────────────────────────────────
    def show_rows(
        self,
        rows: list[RowView],
        summary: str,
        starts: list[tuple[str, int]],
        stay_label: str,
        all_ok: bool,
    ) -> None:
        """Rebuild the page: *rows*, the *summary* line and the start buttons."""
        self.rows = rows
        self.row_buttons = {}
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for row in rows:
            self._rows_layout.addWidget(self._row_widget(row))
        self._rows_layout.addStretch(1)

        self.lbl_summary.setText(summary)
        self.setAccessibleDescription(summary)

        while self._buttons.count():
            item = self._buttons.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.start_buttons = []
        for label, start_row in starts:
            btn = self._button(label, primary=not self.start_buttons)
            btn.clicked.connect(lambda _=False, r=start_row: self.start_chosen.emit(r))
            self.start_buttons.append(btn)
            self._buttons.addWidget(btn)
        self.btn_recheck = self._button("↻ Ricontrolla")
        self.btn_recheck.clicked.connect(lambda: self.action_requested.emit("recheck"))
        self._buttons.addWidget(self.btn_recheck)
        self._buttons.addStretch(1)
        self.btn_stay = self._button(stay_label)
        self.btn_stay.clicked.connect(self.stay_requested)
        self._buttons.addWidget(self.btn_stay)
        if all_ok and self.start_buttons:
            self._default = self.start_buttons[0]
        elif self.start_buttons:
            self._default = self.btn_recheck
        else:
            self._default = self.btn_stay

    def _button(self, label: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setMinimumHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            btn.setStyleSheet(
                "QPushButton { background-color: #047857; color: #ffffff; border: 1px solid #10b981; "
                "border-radius: 6px; font-weight: bold; font-size: 14px; padding: 4px 16px; } "
                "QPushButton:focus { border: 2px solid #ffffff; }")
        else:
            btn.setStyleSheet(
                "QPushButton { background-color: #1e293b; color: #f8fafc; border: 1px solid #475569; "
                "border-radius: 6px; font-size: 13px; padding: 4px 14px; } "
                "QPushButton:focus { border: 2px solid #ffffff; }")
        return btn

    def _row_widget(self, row: RowView) -> QWidget:
        frame = QFrame()
        colour = _COLOURS.get(row.state, "#94a3b8")
        frame.setStyleSheet(
            f"QFrame#readinessRow {{ background-color: #0f172a; border: 1px solid #1e293b; "
            f"border-left: 4px solid {colour}; border-radius: 6px; }}")
        frame.setObjectName("readinessRow")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)
        line = QHBoxLayout()
        word = QLabel(_WORDS.get(row.state, ""))
        word.setMinimumWidth(150)
        word.setStyleSheet(f"QLabel {{ color: {colour}; font-weight: bold; font-size: 14px; }}")
        line.addWidget(word)
        text = QLabel(row.text)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.PlainText)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text.setStyleSheet("QLabel { color: #e2e8f0; font-size: 14px; }")
        line.addWidget(text, stretch=1)
        for label, action in row.buttons:
            btn = self._button(label)
            btn.clicked.connect(lambda _=False, a=action: self.action_requested.emit(a))
            line.addWidget(btn)
            self.row_buttons[action] = btn
        outer.addLayout(line)
        frame.setAccessibleName(f"{word.text()} {row.text}")
        for i, item in enumerate(row.items):
            box = QCheckBox(item)  # takes the focus: the checklist works from the keyboard (W48)
            box.setChecked(i in row.ticked)
            box.setStyleSheet("QCheckBox { color: #e2e8f0; font-size: 14px; padding-left: 160px; }")
            box.toggled.connect(lambda on, c=row.cue_id, k=i: self.checklist_toggled.emit(c, k, on))
            outer.addWidget(box)
        return frame

    # ── Keyboard ──────────────────────────────────────────────────────
    def default_button(self) -> QPushButton | None:
        return self._default

    def activate_default(self) -> None:
        """Enter / Space: the focused button, else the default one."""
        focused = self.focusWidget()
        if isinstance(focused, QPushButton) and self.isAncestorOf(focused):
            focused.click()
        elif isinstance(focused, QCheckBox) and self.isAncestorOf(focused):
            focused.toggle()
        elif self._default is not None:
            self._default.click()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_default()
            event.accept()
            return
        super().keyPressEvent(event)
