"""Built-in user manual window (Help → User manual, F1).

Shows ``blindcue/help/manual_<lang>.html`` (with its ``img/<lang>/``
screenshots) in a QTextBrowser, so the manual works offline and travels with
the program. The language follows the UI language; English is the fallback.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget

HELP_DIR = Path(__file__).resolve().parent.parent / "help"
FALLBACK_LANGUAGE = "en"


def manual_file(language: str | None = None) -> Path:
    """Return the manual for *language* (default: the UI language)."""
    if language is None:
        try:
            import i18n
            language = i18n.current_language()
        except Exception:  # pragma: no cover - translation layer missing
            language = "it"
    for code in (language, FALLBACK_LANGUAGE, "it"):
        candidate = HELP_DIR / f"manual_{code}.html"
        if candidate.is_file():
            return candidate
    return HELP_DIR / f"manual_{FALLBACK_LANGUAGE}.html"


class HelpDialog(QDialog):
    """Non-modal manual viewer with in-page links and an "open in browser" button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BlindCue – Manuale utente")
        self.resize(900, 820)
        self._file = manual_file()

        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        self.browser.setSearchPaths([str(HELP_DIR)])
        self.browser.setStyleSheet(
            "QTextBrowser { background-color: #0b1220; color: #e2e8f0; padding: 12px; }"
        )
        self.browser.document().setDefaultStyleSheet("a { color: #7dd3fc; }")
        if self._file.is_file():
            self.browser.setSource(QUrl.fromLocalFile(str(self._file)))
        else:
            self.browser.setHtml(f"<p>Manuale non trovato: {self._file}</p>")

        btn_home = QPushButton("⌂ Indice", self)
        btn_home.clicked.connect(self.browser.home)
        btn_back = QPushButton("← Indietro", self)
        btn_back.clicked.connect(self.browser.backward)
        btn_ext = QPushButton("🌐 Apri nel browser", self)
        btn_ext.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._file)))
        )
        btn_close = QPushButton("Chiudi", self)
        btn_close.clicked.connect(self.close)

        bar = QHBoxLayout()
        bar.addWidget(btn_home)
        bar.addWidget(btn_back)
        bar.addStretch(1)
        bar.addWidget(btn_ext)
        bar.addWidget(btn_close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.browser, 1)
        layout.addLayout(bar)


_dialog: HelpDialog | None = None


def show_help(parent: QWidget | None = None) -> None:
    """Open (or raise) the single manual window."""
    global _dialog
    if _dialog is None:
        _dialog = HelpDialog(parent)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
