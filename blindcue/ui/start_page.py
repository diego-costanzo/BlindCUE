"""The start page with the first steps (stage 5, item 5.16).

Shown when the program starts without a show: start a show (new, from a
folder of files, the practice show, open one, a recent one) and the first
steps of a teacher who sees the program for the first time (sound, projector,
files, GO). "Show at start" turns it off.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

SETTINGS_KEY = "ui/start_page"
_BIG = ("QPushButton { font-size: 15px; font-weight: bold; padding: 10px 14px; text-align: left; "
        "min-height: 30px; }")


class StartPage(QWidget):
    """"What do you want to do?" – the first thing a teacher sees."""

    new_requested = Signal()
    folder_requested = Signal()
    practice_requested = Signal()
    open_requested = Signal()
    recent_chosen = Signal(str)
    sound_requested = Signal()
    screens_requested = Signal()
    projector_requested = Signal()
    add_files_requested = Signal()
    manual_requested = Signal()
    list_requested = Signal()                 # "Go to the cue list" (nothing else)
    show_at_start_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("startPage")
        self.setAccessibleName("Pagina iniziale")
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 24)
        root.setSpacing(18)
        title = QLabel("BlindCue")
        title.setStyleSheet("QLabel { font-size: 30px; font-weight: bold; }")
        root.addWidget(title)
        subtitle = QLabel("Che cosa vuoi fare?")
        subtitle.setStyleSheet("QLabel { font-size: 17px; color: #94a3b8; }")
        root.addWidget(subtitle)

        columns = QHBoxLayout()
        columns.setSpacing(36)
        root.addLayout(columns, stretch=1)

        start = QVBoxLayout()
        start.setSpacing(10)
        for text, signal in (("＋ Nuovo spettacolo", self.new_requested),
                             ("📁 Nuovo spettacolo da una cartella di file…", self.folder_requested),
                             ("🎓 Spettacolo di prova (per imparare)", self.practice_requested),
                             ("📂 Apri uno spettacolo…", self.open_requested)):
            btn = QPushButton(text)
            btn.setStyleSheet(_BIG)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(signal)
            start.addWidget(btn)
        self.lbl_recent = QLabel("Aperti di recente")
        self.lbl_recent.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #94a3b8; margin-top: 10px; }")
        start.addWidget(self.lbl_recent)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(4)
        start.addLayout(self.recent_box)
        start.addStretch(1)
        columns.addLayout(start, stretch=1)

        steps_frame = QFrame()
        steps_frame.setObjectName("startSteps")
        steps_frame.setStyleSheet("QFrame#startSteps { border: 1px solid #334155; border-radius: 8px; }")
        steps = QGridLayout(steps_frame)
        steps.setContentsMargins(18, 14, 18, 14)
        steps.setHorizontalSpacing(12)
        steps.setVerticalSpacing(12)
        head = QLabel("Primi passi")
        head.setStyleSheet("QLabel { font-size: 17px; font-weight: bold; }")
        steps.addWidget(head, 0, 0, 1, 3)
        rows = (
            ("1", "Suono: scegli gli altoparlanti e prova se si sentono.",
             [("🔊 Altoparlanti e uscite…", self.sound_requested)]),
            ("2", "Proiettore: collegalo e controlla quale schermo è quale.",
             [("🔢 Mostra i numeri degli schermi", self.screens_requested),
              ("🖥 Scegli il proiettore…", self.projector_requested)]),
            ("3", "File: aggiungi video, suoni e immagini (o trascinali sulla lista).",
             [("＋ Aggiungi file…", self.add_files_requested)]),
            ("4", "GO: entra nella Prova (Maiusc+F5) e premi la barra spaziatrice. Esc due volte = PANIC.", []),
        )
        for r, (number, text, buttons) in enumerate(rows, start=1):
            num = QLabel(number)
            num.setStyleSheet("QLabel { font-size: 22px; font-weight: bold; color: #38bdf8; }")
            num.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            steps.addWidget(num, r, 0)
            label = QLabel(text)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            label.setStyleSheet("QLabel { font-size: 14px; }")
            steps.addWidget(label, r, 1)
            box = QVBoxLayout()
            for btn_text, signal in buttons:
                btn = QPushButton(btn_text)
                btn.clicked.connect(signal)
                box.addWidget(btn)
            steps.addLayout(box, r, 2)
        manual = QPushButton("📖 Manuale (F1)")
        manual.clicked.connect(self.manual_requested)
        steps.addWidget(manual, len(rows) + 1, 1, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        steps.setColumnStretch(1, 1)
        steps.setRowStretch(len(rows) + 2, 1)
        columns.addWidget(steps_frame, stretch=1)

        foot = QHBoxLayout()
        self.chk_show = QCheckBox("Mostra questa pagina all'avvio")
        self.chk_show.toggled.connect(self.show_at_start_toggled)
        foot.addWidget(self.chk_show)
        foot.addStretch(1)
        self.btn_list = QPushButton("Vai alla scaletta →")
        self.btn_list.clicked.connect(self.list_requested)
        foot.addWidget(self.btn_list)
        root.addLayout(foot)

    def set_recent(self, paths: list[str]) -> None:
        """Up to six recent shows that still exist, as buttons."""
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        shown = [p for p in paths if os.path.isfile(p)][:6]
        for path in shown:
            btn = QPushButton("🎭 " + os.path.splitext(os.path.basename(path))[0])
            btn.setToolTip(path)
            btn.setStyleSheet("QPushButton { text-align: left; padding: 6px 10px; }")
            btn.clicked.connect(lambda _=False, p=path: self.recent_chosen.emit(p))
            self.recent_box.addWidget(btn)
        self.lbl_recent.setVisible(bool(shown))
