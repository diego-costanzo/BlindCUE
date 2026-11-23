"""Mode tabs: "○ Preparation" / "◐ Rehearsal" / "● Show", the same in every view.

Entering the show is one click (or F5 / Ctrl+L). Leaving it is never one
stray keystroke: in the show the Preparation and Rehearsal tabs must be held
for 1.5 s (or Show menu → "End the show…", Ctrl+Shift+F5). What plays keeps
playing. Between Preparation and Rehearsal one click is enough (Shift+F5
enters the rehearsal). The sign fills up the more "live" the mode is.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.hold_button import HoldProgressButton

LEAVE_HOLD_MS = 1500

PREPARATION = "preparation"
REHEARSAL = "rehearsal"
SHOW = "show"

_TAB_STYLE = (
    "QPushButton {{ background-color: {bg}; color: {fg}; border: 1px solid {bd}; "
    "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 14px; }} "
    "QPushButton:hover {{ border-color: #38bdf8; }} "
    "QPushButton:focus {{ border: 2px solid #38bdf8; }}"
)
_ACTIVE_PREP = _TAB_STYLE.format(bg="#334155", fg="#ffffff", bd="#94a3b8")
_ACTIVE_REH = _TAB_STYLE.format(bg="#0c4a6e", fg="#bae6fd", bd="#38bdf8")
_ACTIVE_SHOW = _TAB_STYLE.format(bg="#064e3b", fg="#69f0ae", bd="#10b981")
_IDLE = _TAB_STYLE.format(bg="#1c2636", fg="#cbd5e1", bd="#3c4f6b")


def _hold_tab(text: str, tip: str, name: str) -> HoldProgressButton:
    btn = HoldProgressButton(
        text,
        hold_ms=LEAVE_HOLD_MS,
        is_toggle=False,
        color_idle="#1c2636",
        border_idle="#3c4f6b",
        text_color_idle="#cbd5e1",
        fill_color="#38bdf8",
    )
    btn.setFixedHeight(34)
    btn.setMinimumWidth(190)
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    btn.setToolTip(tip)
    btn.setAccessibleName(name)
    return btn


class ModeTabs(QWidget):
    """Three tabs showing (and switching) the mode of the director window."""

    enter_show_requested = Signal()       # "● Show" clicked outside the show
    leave_show_requested = Signal()       # "○ Preparation" held 1.5 s in the show
    rehearsal_requested = Signal()        # "◐ Rehearsal" clicked, or held 1.5 s in the show
    preparation_requested = Signal()      # "○ Preparation" clicked in the rehearsal

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.tab_prep = QPushButton("○ Preparazione")
        self.tab_prep.setFixedHeight(34)
        self.tab_prep.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_prep.clicked.connect(self._on_prep_clicked)
        self.tab_prep_hold = _hold_tab(
            "○ Preparazione  (tieni 1,5 s)",
            "Tieni premuto 1,5 s per tornare alla preparazione (ciò che è in onda continua)."
            " Da tastiera: Ctrl+Maiusc+F5",
            "Torna alla preparazione: tieni premuto 1,5 secondi",
        )
        self.tab_prep_hold.hold_completed.connect(self.leave_show_requested)

        self.tab_reh = QPushButton("◐ Prova")
        self.tab_reh.setFixedHeight(34)
        self.tab_reh.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_reh.setToolTip("Prova: lo spettacolo come in scena, con piccole correzioni [Maiusc+F5]")
        self.tab_reh.clicked.connect(self._on_reh_clicked)
        self.tab_reh_hold = _hold_tab(
            "◐ Prova  (tieni 1,5 s)",
            "Tieni premuto 1,5 s per passare alla prova (ciò che è in onda continua)",
            "Passa alla prova: tieni premuto 1,5 secondi",
        )
        self.tab_reh_hold.hold_completed.connect(self.rehearsal_requested)

        self.tab_show = QPushButton("● Spettacolo")
        self.tab_show.setFixedHeight(34)
        self.tab_show.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tab_show.setToolTip("Entra nello spettacolo [F5]")
        self.tab_show.clicked.connect(self._on_show_clicked)

        for w in (self.tab_prep, self.tab_prep_hold, self.tab_reh, self.tab_reh_hold, self.tab_show):
            lay.addWidget(w)
        self._mode = ""
        self.set_mode(PREPARATION)

    # ── State ─────────────────────────────────────────────────────────
    def mode(self) -> str:
        return self._mode

    def is_live(self) -> bool:
        """True in the show (the rehearsal is not the show)."""
        return self._mode == SHOW

    def set_live(self, live: bool) -> None:
        self.set_mode(SHOW if live else PREPARATION)

    def set_mode(self, mode: str) -> None:
        """Show which mode is on; only the ways out of the show need a hold."""
        if mode == self._mode:
            return
        self._mode = mode
        show = mode == SHOW
        self.tab_prep.setVisible(not show)
        self.tab_prep_hold.setVisible(show)
        self.tab_reh.setVisible(not show)
        self.tab_reh_hold.setVisible(show)
        self.tab_prep.setStyleSheet(_ACTIVE_PREP if mode == PREPARATION else _IDLE)
        self.tab_reh.setStyleSheet(_ACTIVE_REH if mode == REHEARSAL else _IDLE)
        self.tab_show.setStyleSheet(_ACTIVE_SHOW if show else _IDLE)
        self.tab_prep.setText("○ PREPARAZIONE" if mode == PREPARATION else "○ Preparazione")
        self.tab_reh.setText("◐ PROVA" if mode == REHEARSAL else "◐ Prova")
        self.tab_show.setText("● SPETTACOLO" if show else "● Spettacolo")
        self.tab_prep.setAccessibleName(
            "Modalità preparazione (attiva)" if mode == PREPARATION else "Torna alla preparazione")
        self.tab_reh.setAccessibleName("Modalità prova (attiva)" if mode == REHEARSAL else "Passa alla prova")
        self.tab_show.setAccessibleName("Modalità spettacolo (attiva)" if show else "Entra nello spettacolo")

    # ── Clicks ────────────────────────────────────────────────────────
    def _on_show_clicked(self) -> None:
        if self._mode != SHOW:
            self.enter_show_requested.emit()

    def _on_reh_clicked(self) -> None:
        if self._mode == PREPARATION:
            self.rehearsal_requested.emit()

    def _on_prep_clicked(self) -> None:
        if self._mode == REHEARSAL:
            self.preparation_requested.emit()
