"""Show menu → AI assistant: connect an AI client and allow it to change the show (stage 1M, M3)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from i18n import tr
from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from version import APP_VERSION


def _documents() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or Path.home())


class AssistantDialog(QDialog):
    """What the assistant is, how to add it to Claude Desktop, and the switch that lets it in."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._win = window
        self.setWindowTitle(tr("Assistente AI (MCP)"))
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        intro = QLabel(tr(
            "Un assistente AI (per esempio Claude Desktop) può preparare lo spettacolo per te: crea la "
            "scaletta da una cartella di file, aggiunge didascalie, scene e note per l'operatore. "
            "Trova i file su tutti i dischi di questo computer (anche su una chiavetta USB; le cartelle si "
            "possono limitare in Claude), non suona niente, non cancella i media e non cambia mai uno "
            "spettacolo in corso. Ai fornitori di AI arrivano i nomi delle cue, le note e i nomi dei file, "
            "non il contenuto dei file."))
        intro.setWordWrap(True)
        root.addWidget(intro)

        step1 = QLabel(tr("1. Aggiungi l'assistente a Claude Desktop (una volta per computer):"))
        step1.setWordWrap(True)
        root.addWidget(step1)
        row = QHBoxLayout()
        self.btn_claude = QPushButton(tr("Aggiungi a Claude Desktop…"))
        self.btn_claude.setToolTip(tr("Crea il file dell'estensione e lo apre: Claude Desktop chiede quali "
                                      "cartelle l'assistente può usare."))
        self.btn_claude.clicked.connect(self._add_to_claude)
        row.addWidget(self.btn_claude)
        self.btn_copy = QPushButton(tr("Copia le impostazioni per altri programmi"))
        self.btn_copy.setToolTip(tr("Impostazioni «mcpServers» (JSON) per Claude Code, Cursor e altri client MCP."))
        self.btn_copy.clicked.connect(self._copy_config)
        row.addWidget(self.btn_copy)
        row.addStretch(1)
        root.addLayout(row)

        step2 = QLabel(tr("2. Se vuoi che l'assistente modifichi lo spettacolo aperto qui (si vede subito, "
                          "Ctrl+Z annulla), permettilo:"))
        step2.setWordWrap(True)
        root.addWidget(step2)
        self.chk_allow = QCheckBox(tr("L'assistente AI può modificare lo spettacolo (solo nella preparazione)"))
        self.chk_allow.setChecked(window._act_assistant.isChecked())
        self.chk_allow.toggled.connect(window._act_assistant.setChecked)
        root.addWidget(self.chk_allow)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #93c5fd;")
        root.addWidget(self.lbl_status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.btn_changes = QPushButton(tr("Modifiche dall'assistente…"))
        self.btn_changes.clicked.connect(window._show_assistant_changes)
        buttons.addButton(self.btn_changes, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _add_to_claude(self) -> None:
        from mcp_server.bundle import BUNDLE_NAME, build_mcpb

        target = _documents() / "BlindCue" / f"{BUNDLE_NAME}.mcpb"
        icon = Path(__file__).resolve().parent.parent / "assets" / "blindcue-256.png"
        try:
            build_mcpb(target, APP_VERSION.split("-")[0], icon.read_bytes() if icon.is_file() else None)
        except OSError as exc:
            self.lbl_status.setText(tr("Impossibile creare il file: {}").format(exc))
            return
        if sys.platform == "win32":
            # Claude Desktop for Windows has no file type for .mcpb: opening the file only made Windows ask
            # which program to use (2026-11-24). The install starts in Claude: show the file, bring Claude up
            # and say where to click.
            subprocess.Popen(["explorer", "/select,", os.path.normpath(str(target))])  # noqa: S603,S607
            QDesktopServices.openUrl(QUrl("claude://"))
            self.lbl_status.setText(tr(
                "Creato {}. In Claude Desktop: Impostazioni → Estensioni (o «App desktop» → Estensioni → Gestisci) "
                "→ Impostazioni avanzate → «Installa estensione…» e scegli questo file, poi indica le cartelle. "
                "Se non funziona: «Copia le impostazioni per altri programmi» e in Claude Desktop Impostazioni → "
                "Sviluppatore → Modifica configurazione.").format(target))
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        self.lbl_status.setText(
            tr("Creato {}. Se Claude Desktop non si è aperto, trascina questo file nella sua finestra "
               "(Impostazioni → Estensioni).").format(target) if not opened else
            tr("Creato {} e aperto: conferma l'installazione in Claude Desktop e scegli le cartelle.").format(target))

    def _copy_config(self) -> None:
        from mcp_server.bundle import client_config

        QApplication.clipboard().setText(client_config([]))   # every drive, also USB (2026-11-24)
        self.lbl_status.setText(tr("Impostazioni copiate: l'assistente può usare tutti i dischi di questo "
                                   "computer (anche una chiavetta USB). Incollale nella configurazione del "
                                   "client MCP."))
