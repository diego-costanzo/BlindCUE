"""Stage 3, item 3.3: how a playlist plays - a card in the inspector's scene tab.

Shown only for a playlist (a scene made with "One playlist" or from an .m3u):
the transition between tracks and its seconds, random order with no repeat
among the last N tracks, start again after the last track, "the next GO goes
on with the next track", and "same loudness for every track". The card never
writes into the cue itself: ``changed`` hands the values to the main window,
which makes them one undo step.
"""

from __future__ import annotations

from engine.playlist_flow import (
    CROSSFADE,
    GAP,
    MAX_SHUFFLE_GAP,
    MAX_TRANSITION_SEC,
    NONE,
    OVERLAP,
)
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.spinboxes import SmartDoubleSpinBox

TRANSITION_CHOICES = (
    (NONE, "Nessuna (senza pause)"),
    (CROSSFADE, "Dissolvenza incrociata"),
    (OVERLAP, "Sovrapposizione"),
    (GAP, "Pausa tra i brani"),
)
_TRANSITION_TIPS = {
    NONE: "Il brano successivo parte appena finisce quello in corso: il programma lo apre qualche secondo "
          "prima, così la pausa è la più corta possibile.",
    CROSSFADE: "Il brano successivo entra N secondi prima della fine di quello in corso, che sfuma nello "
               "stesso tempo.",
    OVERLAP: "Il brano successivo entra N secondi prima della fine; quello in corso suona fino alla sua fine.",
    GAP: "Tra un brano e l'altro N secondi di silenzio.",
}


class PlaylistSettingsBox(QFrame):
    """The playlist settings of one scene; ``changed(dict)`` with the field values."""

    changed = Signal(dict)
    normalize_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("playlistCard")
        self.setStyleSheet("QFrame#playlistCard { background-color: #101723; border: 1px solid #223044; "
                           "border-radius: 6px; }")
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(6)
        title = QLabel("🎵 PLAYLIST")
        title.setStyleSheet("QLabel { font-weight: bold; font-size: 11px; color: #38bdf8; background: transparent; }")
        lay.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.addWidget(QLabel("Tra i brani:"), 0, 0)
        self.combo_transition = QComboBox()
        self.combo_transition.setAccessibleName("Passaggio tra i brani")
        for key, label in TRANSITION_CHOICES:
            self.combo_transition.addItem(label, key)
        grid.addWidget(self.combo_transition, 0, 1)
        self.spin_seconds = SmartDoubleSpinBox()
        self.spin_seconds.setRange(0.0, MAX_TRANSITION_SEC)
        self.spin_seconds.setDecimals(1)
        self.spin_seconds.setSingleStep(0.5)
        self.spin_seconds.setSuffix(" s")
        self.spin_seconds.setAccessibleName("Secondi del passaggio tra i brani")
        self.spin_seconds.setMinimumWidth(68)
        grid.addWidget(self.spin_seconds, 0, 2)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        shuffle_row = QHBoxLayout()
        self.chk_shuffle = QCheckBox("Ordine casuale")
        self.chk_shuffle.setToolTip("Ogni giro in un ordine diverso.")
        shuffle_row.addWidget(self.chk_shuffle)
        self.lbl_gap = QLabel("senza ripetere gli ultimi")
        shuffle_row.addWidget(self.lbl_gap)
        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(0, MAX_SHUFFLE_GAP)
        self.spin_gap.setAccessibleName("Nessuna ripetizione tra gli ultimi brani")
        self.spin_gap.setToolTip("Un brano non torna tra gli ultimi N brani suonati (per quanto lo permette "
                                 "la lunghezza della playlist).")
        shuffle_row.addWidget(self.spin_gap)
        shuffle_row.addStretch(1)
        lay.addLayout(shuffle_row)

        self.chk_loop = QCheckBox("Dopo l'ultimo brano ricomincia (a ciclo)")
        self.chk_loop.setToolTip("La musica dell'intervallo suona finché non la fermi o la addormenti.")
        lay.addWidget(self.chk_loop)
        self.chk_remember = QCheckBox("Il GO successivo continua dal brano seguente")
        self.chk_remember.setToolTip("Dopo uno stop o una pausa la playlist non riparte dal primo brano: "
                                     "continua con quello dopo l'ultimo suonato.")
        lay.addWidget(self.chk_remember)

        self.btn_normalize = QPushButton("🎚 Stesso volume percepito per tutti i brani (LUFS)")
        self.btn_normalize.setToolTip("Misura ogni brano e lo abbassa quanto serve, così tutti suonano forte "
                                      "uguale (il programma non può suonare più forte del file).")
        self.btn_normalize.clicked.connect(self.normalize_requested.emit)
        lay.addWidget(self.btn_normalize)

        self.combo_transition.currentIndexChanged.connect(self._on_edit)
        self.spin_seconds.valueChanged.connect(self._on_edit)
        self.spin_gap.valueChanged.connect(self._on_edit)
        for chk in (self.chk_shuffle, self.chk_loop, self.chk_remember):
            chk.toggled.connect(self._on_edit)
        self._refresh()

    def load(self, cue) -> None:
        """Show the settings of the playlist *cue* (no ``changed``)."""
        self._loading = True
        try:
            idx = self.combo_transition.findData(getattr(cue, "playlist_transition", NONE))
            self.combo_transition.setCurrentIndex(max(0, idx))
            self.spin_seconds.setValue(float(getattr(cue, "playlist_transition_sec", 3.0)))
            self.chk_shuffle.setChecked(bool(getattr(cue, "playlist_shuffle", False)))
            self.spin_gap.setValue(int(getattr(cue, "playlist_shuffle_gap", 3)))
            self.chk_loop.setChecked(bool(getattr(cue, "playlist_loop", False)))
            self.chk_remember.setChecked(bool(getattr(cue, "playlist_remember", False)))
            self._refresh()
        finally:
            self._loading = False

    def values(self) -> dict:
        return {
            "playlist_transition": self.combo_transition.currentData() or NONE,
            "playlist_transition_sec": round(float(self.spin_seconds.value()), 2),
            "playlist_shuffle": self.chk_shuffle.isChecked(),
            "playlist_shuffle_gap": int(self.spin_gap.value()),
            "playlist_loop": self.chk_loop.isChecked(),
            "playlist_remember": self.chk_remember.isChecked(),
        }

    def _refresh(self) -> None:
        kind = self.combo_transition.currentData() or NONE
        self.spin_seconds.setEnabled(kind != NONE)
        self.combo_transition.setToolTip(_TRANSITION_TIPS.get(kind, ""))
        self.spin_gap.setEnabled(self.chk_shuffle.isChecked())
        self.lbl_gap.setEnabled(self.chk_shuffle.isChecked())

    def _on_edit(self, *_args) -> None:
        self._refresh()
        if not self._loading:
            self.changed.emit(self.values())
