"""The PIN field under the show's top bar (stage 1 C2a step 10): never a modal window."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

PIN_IDLE_MS = 10_000  # the field goes away after 10 s without typing


class PinBar(QFrame):
    """"PIN to leave the show: [____]  Enter – leave · [Cancel]"."""

    pin_entered = Signal(str)
    cancelled = Signal()
    go_requested = Signal()   # Space while typing the PIN is still GO

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pinBar")
        self.setStyleSheet(
            "QFrame#pinBar { background-color: #0c1a2b; border: 1px solid #38bdf8; border-radius: 6px; } "
            "QFrame#pinBar QLabel { background: transparent; color: #e2e8f0; font-size: 13px; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        self.lbl_prompt = QLabel()
        lay.addWidget(self.lbl_prompt)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setMaxLength(4)
        self.edit.setFixedWidth(90)
        self.edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,4}"), self.edit))
        self.edit.setAccessibleName("PIN")
        self.edit.installEventFilter(self)
        self.edit.returnPressed.connect(lambda: self.pin_entered.emit(self.edit.text()))
        self.edit.textEdited.connect(lambda _t: self._idle.start())
        lay.addWidget(self.edit)
        self.lbl_hint = QLabel()
        self.lbl_hint.setStyleSheet("QLabel { color: #94a3b8; }")
        lay.addWidget(self.lbl_hint, stretch=1)
        self.btn_cancel = QPushButton("Annulla")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._cancel)
        lay.addWidget(self.btn_cancel)
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(PIN_IDLE_MS)
        self._idle.timeout.connect(self._cancel)
        self.hide()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        from PySide6.QtCore import QEvent

        if obj is self.edit and event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) \
                and event.key() == Qt.Key.Key_Space:
            if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                from ui.live_show_view import LiveCueTable

                if LiveCueTable.space_starts_go:  # 5.7: the program's Space = GO may be off on this computer
                    self.go_requested.emit()
            event.accept()
            return True
        return super().eventFilter(obj, event)

    def ask(self, prompt: str, hint: str) -> None:
        self.lbl_prompt.setText(prompt)
        self.lbl_hint.setText(hint)
        self.edit.clear()
        self.show()
        self.edit.setFocus()
        self._idle.start()

    def feedback(self, text: str) -> None:
        self.lbl_hint.setText(text)
        self.edit.clear()
        self.edit.setFocus()
        self._idle.start()

    def close_bar(self) -> None:
        self._idle.stop()
        self.edit.clear()
        self.hide()

    def _cancel(self) -> None:
        self.close_bar()
        self.cancelled.emit()
