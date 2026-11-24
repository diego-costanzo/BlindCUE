"""Warnings that must not get lost: a persistent bar above both pages (GUI review 2026-11-24).

Speakers unplugged, everything muted, an overloaded projector used to land on the 11 px status bar,
where the next GO wrote over them. The bar stays until the cause is gone; "✕" hides the warnings shown
now (a new or changed warning brings it back).
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class AlarmBar(QFrame):
    changed = Signal(str)  # the text shown now ("" = hidden), for screen readers and the earcon

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("alarmBar")
        self.setStyleSheet(
            "QFrame#alarmBar { background-color: #451a03; border: 2px solid #f59e0b; border-radius: 4px; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 6, 4)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        self.lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl.setStyleSheet("QLabel { color: #fde68a; font-size: 16px; font-weight: bold; }")
        lay.addWidget(self.lbl, stretch=1)
        self.btn_hide = QPushButton("✕")
        self.btn_hide.setFixedSize(30, 26)
        self.btn_hide.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # Space stays GO
        self.btn_hide.setToolTip("Nascondi questi avvisi (tornano se cambiano)")
        self.btn_hide.setAccessibleName("Nascondi gli avvisi")
        self.btn_hide.setStyleSheet(
            "QPushButton { background-color: #78350f; color: #fde68a; border: 1px solid #f59e0b; "
            "border-radius: 4px; font-weight: bold; }")
        self.btn_hide.clicked.connect(self._hide_current)
        lay.addWidget(self.btn_hide)
        self._alarms: dict[str, str] = {}
        self._hidden: set[tuple[str, str]] = set()
        self.setVisible(False)

    def set_alarm(self, key: str, text: str | None) -> None:
        """*key* warns with *text*; an empty text clears it."""
        text = (text or "").strip()
        if text:
            if self._alarms.get(key) == text:
                return
            self._alarms[key] = text
        elif self._alarms.pop(key, None) is None:
            return
        self._hidden = {pair for pair in self._hidden if self._alarms.get(pair[0]) == pair[1]}
        self._refresh()

    def alarms(self) -> dict[str, str]:
        return dict(self._alarms)

    def shown_text(self) -> str:
        return self.lbl.text() if self.isVisible() else ""

    def _hide_current(self) -> None:
        self._hidden |= set(self._alarms.items())
        self._refresh()

    def _refresh(self) -> None:
        texts = [text for key, text in self._alarms.items() if (key, text) not in self._hidden]
        shown = ("⚠ " + "  ·  ".join(texts)) if texts else ""
        before = self.lbl.text() if not self.isHidden() else ""
        self.lbl.setText(shown)
        self.setAccessibleName(shown or tr("Nessun avviso"))
        self.setVisible(bool(shown))
        if shown != before:
            self.changed.emit(shown)
