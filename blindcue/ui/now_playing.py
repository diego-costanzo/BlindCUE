"""Now playing (stage 1 C2a step 8, plan item 1.3): the right column of the show.

One card per cue on air, in fixed places (a new cue takes the first free
place, a finished one frees its place): what it is, on which layer, its state
only when it is an exception (PAUSED, FADING, LOOP, starts in 0:03), the time
played and – the one big number – the time left, with a sign when it ends
soon (never colour alone), and its own controls: pause, fade out, release the
loop. Pictures, captions and operator notes take one line. Fed by the main
window at 10 Hz; widgets are reused, never rebuilt on each tick.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

TIMED = "timed"    # audio / video / picture with a hold time: full card
STILL = "still"    # picture, caption without an end: one line
NOTE = "note"      # operator note: one line with OK

_BTN = ("QPushButton { background-color: #1e293b; color: #f8fafc; border: 1px solid #475569; "
        "border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0px 8px; } "
        "QPushButton:hover { background-color: #334155; } "
        "QPushButton:focus { border: 2px solid #ffffff; }")


@dataclass
class CardState:
    """What one card shows (texts already in the operator's language)."""

    cue_id: int
    kind: str
    title: str                 # "♪ #3 'Birds'"
    layer: str = ""            # "L2", "B·L1"
    state: str = ""            # exception only: "PAUSED", "starts in 0:03", "LOOP ∞"
    elapsed: str = ""
    remaining: str = ""        # "-01:48", "∞"
    fraction: float = -1.0     # 0..1, -1 = nothing to measure
    warn: bool = False         # ends soon and the next GO waits for it
    paused: bool = False
    loop: bool = False
    slot: int = 0              # runtime layer for the controls


class _Card(QFrame):
    def __init__(self, panel: NowPlayingPanel, kind: str) -> None:
        super().__init__()
        self.kind = kind
        self.cue_id = -1
        self.slot = 0
        self.setObjectName("nowCard")
        self.setStyleSheet("QFrame#nowCard { background-color: #0f172a; border: 1px solid #1e293b; "
                           "border-radius: 6px; } QFrame#nowCard QLabel { background: transparent; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(2)
        line1 = QHBoxLayout()
        line1.setSpacing(6)
        self.lbl_title = QLabel()
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_title.setStyleSheet("QLabel { color: #f8fafc; font-weight: bold; font-size: 13px; }")
        line1.addWidget(self.lbl_title, stretch=1)
        self.lbl_state = QLabel()
        self.lbl_state.setStyleSheet("QLabel { color: #fbbf24; font-weight: bold; font-size: 11px; }")
        line1.addWidget(self.lbl_state)
        self.lbl_layer = QLabel()
        self.lbl_layer.setStyleSheet("QLabel { color: #94a3b8; font-size: 11px; font-weight: bold; }")
        line1.addWidget(self.lbl_layer)
        outer.addLayout(line1)

        self.btn_fade = self._button("Sfuma", "Sfuma e ferma questa cue (non sposta il GO)")
        self.btn_fade.clicked.connect(lambda: panel.fade_requested.emit(self.slot))
        if kind == TIMED:
            self.setFixedHeight(84)
            line2 = QHBoxLayout()
            self.lbl_elapsed = QLabel()
            self.lbl_elapsed.setStyleSheet("QLabel { color: #94a3b8; font-size: 12px; }")
            line2.addWidget(self.lbl_elapsed)
            self.bar = QProgressBar()
            self.bar.setRange(0, 1000)
            self.bar.setTextVisible(False)
            self.bar.setFixedHeight(8)
            line2.addWidget(self.bar, stretch=1)
            self.lbl_remaining = QLabel()
            self.lbl_remaining.setMinimumWidth(80)
            self.lbl_remaining.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line2.addWidget(self.lbl_remaining)
            outer.addLayout(line2)
            line3 = QHBoxLayout()
            line3.setSpacing(6)
            self.btn_pause = self._button("⏸", "Pausa / riprendi questa cue")
            self.btn_pause.clicked.connect(lambda: panel.pause_requested.emit(self.slot))
            line3.addWidget(self.btn_pause)
            line3.addWidget(self.btn_fade)
            self.btn_release = self._button("Rilascia loop", "Il loop finisce dopo questo giro")
            self.btn_release.clicked.connect(lambda: panel.release_requested.emit(self.slot))
            line3.addWidget(self.btn_release)
            line3.addStretch(1)
            outer.addLayout(line3)
        else:
            self.setFixedHeight(34)
            outer.setContentsMargins(8, 2, 8, 2)
            if kind == NOTE:
                self.btn_fade.setText("OK")
                self.btn_fade.setToolTip("Nascondi la nota (non ferma niente)")
                self.btn_fade.clicked.disconnect()
                self.btn_fade.clicked.connect(lambda: panel.note_dismissed.emit(self.cue_id))
            line1.addWidget(self.btn_fade)
        self._last: CardState | None = None

    @staticmethod
    def _button(text: str, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.setMinimumSize(32, 26)  # W45: >= 24 px, bigger in a dark booth
        btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # a click never steals Space from GO
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(_BTN)
        return btn

    def show_state(self, st: CardState) -> None:
        if st == self._last:
            return
        self._last = st
        self.cue_id, self.slot = st.cue_id, st.slot
        self.lbl_title.setText(st.title)
        self.lbl_title.setToolTip(st.title)
        self.lbl_layer.setText(st.layer)
        self.lbl_state.setText(st.state)
        self.lbl_state.setVisible(bool(st.state))
        if self.kind != TIMED:
            self.setAccessibleName(" ".join(x for x in (st.title, st.layer, st.state) if x))
            return
        self.lbl_elapsed.setText(st.elapsed)
        # The ends-soon warning is a sign as well as a colour (W35, W36).
        colour = "#fbbf24" if st.warn else "#f8fafc"
        self.lbl_remaining.setText(("⚠ " if st.warn else "") + st.remaining)
        self.lbl_remaining.setStyleSheet(f"QLabel {{ color: {colour}; font-size: 18px; font-weight: bold; }}")
        self.bar.setVisible(st.fraction >= 0)
        if st.fraction >= 0:
            self.bar.setValue(int(st.fraction * 1000))
        self.btn_pause.setText("▶" if st.paused else "⏸")
        self.btn_release.setVisible(st.loop)
        self.setAccessibleName(" ".join(x for x in (st.title, st.layer, st.state, st.remaining) if x))


class NowPlayingPanel(QFrame):
    """The right column of the show: every cue on air with its own controls."""

    pause_requested = Signal(int)     # runtime layer
    fade_requested = Signal(int)      # runtime layer
    release_requested = Signal(int)   # runtime layer
    note_dismissed = Signal(int)      # cue_id of the note

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(360)
        self.setObjectName("nowPlaying")
        self.setAccessibleName("Ora in onda")
        self.setStyleSheet("QFrame#nowPlaying { background-color: #0b0f16; border: 1px solid #1e293b; "
                           "border-radius: 6px; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)
        self.lbl_header = QLabel("ORA IN ONDA")
        self.lbl_header.setFixedHeight(20)
        self.lbl_header.setStyleSheet("QLabel { color: #94a3b8; font-weight: bold; font-size: 11px; }")
        root.addWidget(self.lbl_header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        box = QWidget()
        self._cards_layout = QVBoxLayout(box)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self.lbl_empty = QLabel("Niente in onda.")
        self.lbl_empty.setStyleSheet("QLabel { color: #64748b; font-size: 13px; padding: 8px; }")
        self._cards_layout.addWidget(self.lbl_empty)
        self._cards_layout.addStretch(1)
        scroll.setWidget(box)
        root.addWidget(scroll, stretch=1)
        self._cards: dict[int, _Card] = {}   # cue_id -> card (fixed places)

    def cards(self) -> dict[int, _Card]:
        return dict(self._cards)

    def set_cards(self, states: list[CardState]) -> None:
        """Show *states*; a known cue keeps its card and its place."""
        wanted = {s.cue_id: s for s in states}
        for cue_id in [c for c in self._cards if c not in wanted or self._cards[c].kind != wanted[c].kind]:
            card = self._cards.pop(cue_id)
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        for st in states:
            card = self._cards.get(st.cue_id)
            if card is None:
                card = _Card(self, st.kind)
                self._cards[st.cue_id] = card
                # New cards go after the ones already there (before the stretch).
                self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            card.show_state(st)
        self.lbl_empty.setVisible(not self._cards)
