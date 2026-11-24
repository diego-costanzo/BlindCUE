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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.hold_button import HoldProgressButton
from ui.rehearsal_drawer import RehearsalDrawer

TIMED = "timed"    # audio / video / picture with a hold time: full card
STILL = "still"    # picture, caption without an end: one line
NOTE = "note"      # operator note: one line with OK
SCENE = "scene"    # a scene with something on air: one line with "Fade the scene"
_FULL_HEIGHT = 94  # a full card: room for the 26 px remaining time (was 84 with 18 px)

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
    trim: float = 1.0          # operator's level correction (1.0 = the cue's own level)
    seekable: bool = False     # audio/video: -10 s / +10 s
    waiting: bool = False      # still in its Pre-Delay: the card can only cancel the start


class _TrimSlider(QSlider):
    """Level correction 0-100 %: the wheel works only after a click on it, Home/End
    do nothing (never silence or full by accident, W46), Ctrl+click = the cue's level."""

    reset_requested = Signal()

    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.setRange(0, 100)
        self.setSingleStep(1)
        self.setPageStep(10)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Home, Qt.Key.Key_End):
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Space):
            event.ignore()  # arrows move the next cue, Space is GO
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.reset_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)


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
        self.btn_edit = self._button("✎", "Correggi questa cue (prova)")
        self.btn_edit.setMinimumSize(26, 22)
        self.btn_edit.clicked.connect(lambda: panel.edit_requested.emit(self.cue_id))
        self.btn_edit.setVisible(False)
        line1.addWidget(self.btn_edit)
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
        # Compact card (#15): with three or more cues on air the later cards keep one
        # "Fade" in the title line and drop the row of buttons.
        self.btn_fade_small = self._button("Sfuma", "Sfuma e ferma questa cue (non sposta il GO)")
        self.btn_fade_small.clicked.connect(self._on_fade_clicked)
        self.btn_fade_small.setVisible(False)
        line1.addWidget(self.btn_fade_small)
        outer.addLayout(line1)
        self._compact = False
        self._rehearsal_on = False

        self.btn_fade = self._button("Sfuma", "Sfuma e ferma questa cue (non sposta il GO)")
        self.btn_fade.clicked.connect(self._on_fade_clicked)
        self._panel_ref = panel
        self._waiting = False
        if kind == TIMED:
            self.setFixedHeight(_FULL_HEIGHT)
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
            self.controls_row = QWidget()
            line3 = QHBoxLayout(self.controls_row)
            line3.setContentsMargins(0, 0, 0, 0)
            line3.setSpacing(6)
            self.btn_pause = self._button("❚❚", "Pausa / riprendi questa cue")
            self.btn_pause.clicked.connect(lambda: panel.pause_requested.emit(self.slot))
            line3.addWidget(self.btn_pause)
            line3.addWidget(self.btn_fade)
            self.btn_release = self._button("Rilascia loop", "Il loop finisce dopo questo giro")
            self.btn_release.clicked.connect(lambda: panel.release_requested.emit(self.slot))
            line3.addWidget(self.btn_release)
            # Jumps are held for half a second: a stray click never moves the music.
            self.btn_back = self._hold_button("−10 s", "Indietro di 10 s (tieni premuto)")
            self.btn_back.hold_completed.connect(lambda: panel.seek_requested.emit(self.slot, -10.0))
            self.btn_back.released_early.connect(panel.hold_longer)
            line3.addWidget(self.btn_back)
            self.btn_fwd = self._hold_button("+10 s", "Avanti di 10 s (tieni premuto)")
            self.btn_fwd.hold_completed.connect(lambda: panel.seek_requested.emit(self.slot, 10.0))
            self.btn_fwd.released_early.connect(panel.hold_longer)
            line3.addWidget(self.btn_fwd)
            self.slider = _TrimSlider()
            self.slider.setToolTip("Livello di questa cue (Ctrl+clic = livello della cue)")
            self.slider.setAccessibleName("Livello di questa cue")
            self.slider.setMinimumWidth(56)
            self.slider.valueChanged.connect(self._on_slider)
            self.slider.reset_requested.connect(lambda: self.slider.setValue(100))
            line3.addWidget(self.slider, stretch=1)
            self.lbl_trim = QLabel("100 %")
            self.lbl_trim.setMinimumWidth(38)
            self.lbl_trim.setStyleSheet("QLabel { color: #cbd5e1; font-size: 11px; }")
            line3.addWidget(self.lbl_trim)
            outer.addWidget(self.controls_row)
            # Rehearsal only: stop at once, jump near the end, keep the level.
            self.rehearsal_row = QWidget()
            line4 = QHBoxLayout(self.rehearsal_row)
            line4.setContentsMargins(0, 0, 0, 0)
            line4.setSpacing(6)
            self.btn_stop = self._button("⏹", "Ferma subito questa cue")
            self.btn_stop.clicked.connect(lambda: panel.stop_requested.emit(self.slot))
            line4.addWidget(self.btn_stop)
            self.btn_to_end = self._button("⇥ −5 s", "Salta a 5 s dalla fine (per provare il finale)")
            self.btn_to_end.clicked.connect(lambda: panel.to_end_requested.emit(self.slot))
            line4.addWidget(self.btn_to_end)
            self.btn_save_level = self._button("Salva livello", "Il livello corretto diventa quello della cue")
            self.btn_save_level.clicked.connect(lambda: panel.save_level_requested.emit(self.cue_id))
            line4.addWidget(self.btn_save_level)
            line4.addStretch(1)
            outer.addWidget(self.rehearsal_row)
            self.rehearsal_row.setVisible(False)
            self._panel = panel
        else:
            self.setFixedHeight(34)
            outer.setContentsMargins(8, 2, 8, 2)
            if kind == SCENE:
                self.btn_fade.setText("Sfuma la scena")
                self.btn_fade.setToolTip("Sfuma e ferma tutto ciò che la scena suona o mostra; il GO va dopo la scena")
                self.btn_fade.clicked.disconnect()
                self.btn_fade.clicked.connect(lambda: panel.scene_fade_requested.emit(self.cue_id))
            if kind == NOTE:
                self.btn_fade.setText("OK")
                self.btn_fade.setToolTip("Nascondi la nota (non ferma niente)")
                self.btn_fade.clicked.disconnect()
                self.btn_fade.clicked.connect(lambda: panel.note_dismissed.emit(self.cue_id))
            line1.addWidget(self.btn_fade)
        self._last: CardState | None = None
        self._setting = False

    def _on_slider(self, value: int) -> None:
        self.lbl_trim.setText(f"{value} %")
        if not self._setting:
            self._panel.trim_requested.emit(self.slot, value / 100.0)

    @staticmethod
    def _hold_button(text: str, tip: str) -> HoldProgressButton:
        btn = HoldProgressButton(text_idle=text, hold_ms=1500, is_toggle=False, fill_color="#38bdf8")
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.setFixedSize(52, 26)
        btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return btn

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

    def _on_fade_clicked(self) -> None:
        if self._waiting:
            self._panel_ref.cancel_start_requested.emit(self.slot)
        else:
            self._panel_ref.fade_requested.emit(self.slot)

    def set_rehearsal(self, on: bool) -> None:
        """Rehearsal tools on the card; jumps need a long hold only in the show."""
        self.btn_edit.setVisible(on)
        self._rehearsal_on = on
        if on and self._compact:
            self.set_compact(False)  # the rehearsal keeps all the tools
        if self.kind == TIMED:
            self.rehearsal_row.setVisible(on)
            self._apply_height()
            for btn in (self.btn_back, self.btn_fwd):
                btn.set_hold_ms(200 if on else 1500)
        self._last = None  # redraw with the new tools

    def set_compact(self, on: bool) -> None:
        """#15: title line with "Fade" and the progress line only (never in the rehearsal)."""
        on = bool(on) and self.kind == TIMED and not self._rehearsal_on
        if on == self._compact:
            return
        self._compact = on
        self.controls_row.setVisible(not on)
        self.btn_fade_small.setVisible(on)
        self._apply_height()

    def _apply_height(self) -> None:
        base = 58 if self._compact else _FULL_HEIGHT
        self.setFixedHeight(base + (28 if self._rehearsal_on else 0))
        self._last = None  # the time font follows the compact state: paint it again

    def _remaining_px(self) -> int:
        """26 px on a full card, read at a glance in the dark (GUI review 2026-11-24); 18 px compact."""
        return 18 if self._compact else 26

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
        if self.kind not in (NOTE, SCENE) and st.waiting != self._waiting:
            # A cue still waiting only offers to cancel its start; the other
            # buttons would act on the cue that plays on the same layer (H3).
            self._waiting = st.waiting
            for btn in (self.btn_fade, self.btn_fade_small):
                btn.setText("Annulla partenza" if st.waiting else "Sfuma")
                btn.setToolTip("La cue non partirà" if st.waiting else
                               "Sfuma e ferma questa cue (non sposta il GO)")
        if self.kind != TIMED:
            self.setAccessibleName(" ".join(x for x in (st.title, st.layer, st.state) if x))
            return
        self.lbl_elapsed.setText(st.elapsed)
        # The ends-soon warning is a sign as well as a colour (W35, W36).
        colour = "#fbbf24" if st.warn else "#f8fafc"
        self.lbl_remaining.setText(("⚠ " if st.warn else "") + st.remaining)
        self.lbl_remaining.setStyleSheet(
            f"QLabel {{ color: {colour}; font-size: {self._remaining_px()}px; font-weight: bold; }}")
        self.bar.setVisible(st.fraction >= 0)
        if st.fraction >= 0:
            self.bar.setValue(int(st.fraction * 1000))
        self.btn_pause.setText("▶" if st.paused else "❚❚")
        self.btn_pause.setVisible(not st.waiting)
        self.slider.setVisible(not st.waiting)
        self.lbl_trim.setVisible(not st.waiting)
        self.btn_release.setVisible(st.loop and not st.waiting)
        self.btn_back.setVisible(st.seekable)
        self.btn_fwd.setVisible(st.seekable)
        self.btn_to_end.setVisible(st.seekable)
        self.btn_save_level.setVisible(st.trim < 0.995)
        if not self.slider.isSliderDown() and not self.slider.hasFocus():
            self._setting = True
            self.slider.setValue(round(st.trim * 100))
            self._setting = False
        self.setAccessibleName(" ".join(x for x in (st.title, st.layer, st.state, st.remaining) if x))


class NowPlayingPanel(QFrame):
    """The right column of the show: every cue on air with its own controls."""

    pause_requested = Signal(int)     # runtime layer
    fade_requested = Signal(int)      # runtime layer
    release_requested = Signal(int)   # runtime layer
    note_dismissed = Signal(int)      # cue_id of the note
    seek_requested = Signal(int, float)   # runtime layer, seconds (-10 / +10)
    trim_requested = Signal(int, float)   # runtime layer, level correction 0..1
    preview_toggled = Signal(bool)        # the output preview opened / folded
    edit_requested = Signal(int)          # cue_id: open the rehearsal drawer on it
    stop_requested = Signal(int)          # runtime layer: stop at once (rehearsal)
    to_end_requested = Signal(int)        # runtime layer: jump to 5 s before the end
    save_level_requested = Signal(int)    # cue_id: the corrected level becomes the cue's
    cancel_start_requested = Signal(int)  # runtime layer: the waiting cue never starts
    scene_fade_requested = Signal(int)    # cue_id of the scene: fade all it plays (evaluation 2026-11-24)
    effect_requested = Signal(int)        # cue_id of an effect tile
    repeat_effect_requested = Signal()    # "repeat the last effect" (1.10)
    hold_longer = Signal()                # a jump button let go too early

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
        # The rehearsal drawer takes the place of the preview while it is open.
        self.drawer = RehearsalDrawer()
        # It scrolls inside the column, so the cards below keep their buttons (QA C2a).
        self._drawer_scroll = QScrollArea()
        self._drawer_scroll.setWidgetResizable(True)
        self._drawer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._drawer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._drawer_scroll.setMaximumHeight(280)
        self._drawer_scroll.setWidget(self.drawer)
        self._drawer_scroll.setVisible(False)
        root.addWidget(self._drawer_scroll)
        self._rehearsal = False
        # What the audience sees, small, on top; folds to its header ("▾").
        self.btn_preview = QPushButton("▾ ANTEPRIMA USCITA")
        self.btn_preview.setCheckable(True)
        self.btn_preview.setChecked(True)
        self.btn_preview.setFixedHeight(22)
        self.btn_preview.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_preview.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none; font-weight: bold; "
            "font-size: 11px; text-align: left; } QPushButton:focus { color: #ffffff; }")
        self.btn_preview.toggled.connect(self._on_preview_toggled)
        root.addWidget(self.btn_preview)
        self.lbl_preview = QLabel()
        self.lbl_preview.setFixedSize(240, 135)
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("QLabel { background-color: #000000; border: 1px solid #334155; }")
        self.lbl_preview.setAccessibleName("Anteprima dell'uscita")
        root.addWidget(self.lbl_preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        # Effects on demand: one tile each, never in the GO order (1.7, 1.10).
        self.effects_box = QWidget()
        self._effects_layout = QGridLayout(self.effects_box)
        self._effects_layout.setContentsMargins(0, 0, 0, 0)
        self._effects_layout.setSpacing(4)
        self.effects_box.setVisible(False)
        root.addWidget(self.effects_box)
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
        self.lbl_empty.setStyleSheet("QLabel { color: #94a3b8; font-size: 13px; padding: 8px; }")
        self._cards_layout.addWidget(self.lbl_empty)
        self._cards_layout.addStretch(1)
        scroll.setWidget(box)
        root.addWidget(scroll, stretch=1)
        self._cards: dict[int, _Card] = {}   # cue_id -> card (fixed places)

    def _on_preview_toggled(self, shown: bool) -> None:
        self.btn_preview.setText(("▾ " if shown else "▸ ") + self._preview_title)
        self.lbl_preview.setVisible(shown)
        self.preview_toggled.emit(shown)

    _preview_title = "ANTEPRIMA USCITA"

    def set_preview_title(self, title: str) -> None:
        """Header of the preview, e.g. with the screen it goes to."""
        self._preview_title = title
        self.btn_preview.setText(("▾ " if self.btn_preview.isChecked() else "▸ ") + title)

    def set_preview(self, pixmap) -> None:
        self.lbl_preview.setPixmap(pixmap)

    def preview_shown(self) -> bool:
        return self.btn_preview.isChecked()

    def show_drawer(self, shown: bool) -> None:
        self.drawer.setVisible(shown)
        self._drawer_scroll.setVisible(shown)
        self.btn_preview.setVisible(not shown)
        self.lbl_preview.setVisible(not shown and self.btn_preview.isChecked())

    def set_rehearsal(self, on: bool) -> None:
        self._rehearsal = bool(on)
        for card in self._cards.values():
            card.set_rehearsal(self._rehearsal)
        if not on:
            self.show_drawer(False)

    def set_effects(self, items: list[tuple[int, str]]) -> None:
        """Tiles for the effects on demand (cue_id, "B · #5 Bell"), plus "repeat the last"."""
        while self._effects_layout.count():
            item = self._effects_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.effect_tiles: dict[int, QPushButton] = {}
        for i, (cue_id, label) in enumerate(items):
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Space stays GO
            btn.setStyleSheet(
                "QPushButton { background-color: #2e1065; color: #e9d5ff; border: 1px solid #7c3aed; "
                "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 6px; text-align: left; }")
            btn.setToolTip(label)
            btn.clicked.connect(lambda _=False, c=cue_id: self.effect_requested.emit(c))
            self._effects_layout.addWidget(btn, i // 2, i % 2)
            self.effect_tiles[cue_id] = btn
        if items:
            again = QPushButton("↻ Ripeti l'ultimo effetto  [Ctrl+R]")
            again.setFixedHeight(26)
            again.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            again.setStyleSheet(_BTN)
            again.clicked.connect(self.repeat_effect_requested)
            self._effects_layout.addWidget(again, (len(items) + 1) // 2, 0, 1, 2)
        self.effects_box.setVisible(bool(items))

    def cards(self) -> dict[int, _Card]:
        return dict(self._cards)

    def _cards_in_order(self) -> list[_Card]:
        """The cards as they stand in the column, top first."""
        out = []
        for i in range(self._cards_layout.count()):
            widget = self._cards_layout.itemAt(i).widget()
            if isinstance(widget, _Card):
                out.append(widget)
        return out

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
                card.set_rehearsal(self._rehearsal)
                self._cards[st.cue_id] = card
                # New cards go after the ones already there (before the stretch).
                self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            card.show_state(st)
        # #15: with three or more sounds / videos on air the later cards get compact (no scrolling).
        timed = [c for c in self._cards_in_order() if c.kind == TIMED]
        for i, card in enumerate(timed):
            card.set_compact(len(timed) >= 3 and i > 0)
        self.lbl_empty.setVisible(not self._cards)


class NowPlayingStrip(NowPlayingPanel):
    """Preparation: the same cards, compact, above the GO; hidden while nothing plays.

    The GO in Preparation plays to the room, and the button under the preview stops only the preview:
    without this strip the Lite layout had no way to fade one sound (GUI review 2026-11-24).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self.setAccessibleName("Ora in onda – si sente in sala")
        for widget in (self.btn_preview, self.lbl_preview, self.effects_box, self.lbl_empty):
            widget.setVisible(False)
        self.lbl_header.setText("ORA IN ONDA – si sente in sala")
        self.setVisible(False)

    def set_preview(self, pixmap) -> None:  # no output preview here
        return

    def set_cards(self, states: list[CardState]) -> None:
        super().set_cards([s for s in states if s.kind != NOTE])
        for card in self._cards.values():
            card.set_compact(True)
        self.lbl_empty.setVisible(False)
        shown = self._cards_in_order()[:3]   # more than three scroll inside
        self.setFixedHeight(sum(c.height() + 4 for c in shown) + 40 if shown else 0)
        self.setVisible(bool(shown))
