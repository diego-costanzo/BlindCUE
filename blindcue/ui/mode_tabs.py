"""Mode tabs: "○ Preparation" / "● Show", the same in the editor and in LIVE.

Entering the show is one click (or F5 / Ctrl+L). Leaving it is never one
stray keystroke: in the show the Preparation tab must be held for 1.5 s
(or Show menu → "End the show…", Ctrl+Shift+F5). What plays keeps playing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.hold_button import HoldProgressButton

LEAVE_HOLD_MS = 1500

_TAB_STYLE = (
    "QPushButton {{ background-color: {bg}; color: {fg}; border: 1px solid {bd}; "
    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; }} "
    "QPushButton:hover {{ border-color: #38bdf8; }} "
    "QPushButton:focus {{ border: 2px solid #38bdf8; }}"
)
_ACTIVE_PREP = _TAB_STYLE.format(bg="#334155", fg="#ffffff", bd="#94a3b8")
_ACTIVE_SHOW = _TAB_STYLE.format(bg="#064e3b", fg="#69f0ae", bd="#10b981")
_IDLE = _TAB_STYLE.format(bg="#1c2636", fg="#cbd5e1", bd="#3c4f6b")


class ModeTabs(QWidget):
    """Two tabs showing (and switching) the mode of the director window."""

    enter_show_requested = Signal()
    leave_show_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.tab_prep = QPushButton("○ Preparazione")
        self.tab_prep.setFixedHeight(34)
        self.tab_prep.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_prep.setAccessibleName("Modalità preparazione (attiva)")

        self.tab_prep_hold = HoldProgressButton(
            "○ Preparazione  (tieni 1,5 s)",
            hold_ms=LEAVE_HOLD_MS,
            is_toggle=False,
            color_idle="#1c2636",
            border_idle="#3c4f6b",
            text_color_idle="#cbd5e1",
            fill_color="#38bdf8",
        )
        self.tab_prep_hold.setFixedHeight(34)
        self.tab_prep_hold.setMinimumWidth(210)
        self.tab_prep_hold.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_prep_hold.setToolTip(
            "Tieni premuto 1,5 s per tornare alla preparazione (ciò che è in onda continua)."
            " Da tastiera: Ctrl+Maiusc+F5"
        )
        self.tab_prep_hold.setAccessibleName("Torna alla preparazione: tieni premuto 1,5 secondi")
        self.tab_prep_hold.hold_completed.connect(self.leave_show_requested)

        self.tab_show = QPushButton("● Spettacolo")
        self.tab_show.setFixedHeight(34)
        self.tab_show.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_show.setToolTip("Entra nello spettacolo [F5]")
        self.tab_show.clicked.connect(self._on_show_clicked)

        lay.addWidget(self.tab_prep)
        lay.addWidget(self.tab_prep_hold)
        lay.addWidget(self.tab_show)
        self._live = True  # force the first set_live to apply
        self.set_live(False)

    def is_live(self) -> bool:
        return self._live

    def set_live(self, live: bool) -> None:
        """Show which mode is on; only the way out of the show needs a hold."""
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        self.tab_prep.setVisible(not live)
        self.tab_prep_hold.setVisible(live)
        self.tab_prep.setStyleSheet(_ACTIVE_PREP if not live else _IDLE)
        self.tab_show.setStyleSheet(_ACTIVE_SHOW if live else _IDLE)
        self.tab_show.setText("● SPETTACOLO" if live else "● Spettacolo")
        self.tab_prep.setText("○ PREPARAZIONE" if not live else "○ Preparazione")
        self.tab_show.setAccessibleName("Modalità spettacolo (attiva)" if live else "Entra nello spettacolo")

    def _on_show_clicked(self) -> None:
        if not self._live:
            self.enter_show_requested.emit()
