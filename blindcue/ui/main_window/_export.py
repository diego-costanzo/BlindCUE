"""Export and print the cue list (stage 5, item 5.1) mixin for MainWindow.

File → "Export the cue list (CSV)…" writes a spreadsheet (Excel /
LibreOffice). File → "Print the cue list for the operator / the prompter…"
opens a page in the web browser to print: for the operator only the cues
started by hand, in big letters, with room for notes; for the prompter the
page of the script, the line the cue comes on, Q and name of every cue.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from i18n import tr
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ui.main_window._common import *  # noqa: F403,F401,F405


def export_headers() -> dict[str, str]:
    return {"number": "#", "q": "Q", "name": tr("Nome"), "type": tr("Tipo"), "layer": tr("Layer"),
            "follow": tr("Poi"), "pre": "Pre", "post": "Post", "page": tr("Pagina"), "line": tr("Battuta"),
            "notes": tr("Note"), "off": tr("Esclusa"), "file": tr("File")}


def follow_names() -> dict[str, str]:
    return {"SIMULTANEOUS": tr("⇉ Simult.")}


class _ExportMixin:
    def _show_title(self) -> str:
        path = getattr(self, "_current_project_path", None)
        return Path(path).stem if path else tr("Spettacolo")

    def _export_list_csv(self) -> None:
        from engine.cue_export import rows, to_csv

        start = str(Path(self._current_project_path).with_suffix(".csv")) if getattr(
            self, "_current_project_path", None) else "scaletta.csv"
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta la scaletta"), start, "CSV (*.csv)")
        if not path:
            return
        try:
            to_csv(rows(self._cues, follow_names()), path, export_headers())
        except OSError as exc:
            QMessageBox.warning(self, tr("Esporta la scaletta"), str(exc))
            return
        self._status_label.setText(tr("Scaletta esportata: {}").format(path))

    def _print_list(self, variant: str) -> None:
        from engine.cue_export import rows, to_html

        title = self._show_title() + " – " + (tr("regia") if variant == "operator" else tr("suggeritore"))
        page = to_html(rows(self._cues, follow_names()), title, variant, export_headers(),
                       hint=tr("Stampa con Ctrl+P (orizzontale per molte colonne)."))
        target = Path(tempfile.gettempdir()) / f"blindcue_{variant}.html"
        try:
            target.write_text(page, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        self._status_label.setText(tr("Scaletta aperta nel browser: stampa con Ctrl+P"))
