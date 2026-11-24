"""Export and print the cue list (stage 5, item 5.1) mixin for MainWindow.

File → "Export the cue list (CSV)…" writes a spreadsheet (Excel /
LibreOffice), "…(Excel)…" an .xlsx workbook. File → "Print the cue list
for the operator / the prompter…" opens a page in the web browser to print,
"… in PDF…" writes the same page as a PDF without a browser: for the
operator only the cues started by hand, in big letters, with room for notes;
for the prompter the page of the script, the line the cue comes on, Q and
name of every cue.
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
            "follow": tr("Poi"), "pre": tr("Pre-Delay"), "post": tr("Post-Delay"), "page": tr("Pagina"),
            "line": tr("Battuta"), "notes": tr("Note"), "off": tr("Esclusa"), "file": tr("File")}


def follow_names() -> dict[str, str]:
    return {"MANUAL": tr("Manuale (GO)"), "AUTO_FOLLOW": tr("Auto-GO al termine"),
            "SIMULTANEOUS": tr("Insieme alla successiva")}


def _type_names(data: list[dict]) -> list[dict]:
    """The kind of each cue in the UI language (the rows carry the internal name: VIDEO, AUDIO…)."""
    for row in data:
        row["type"] = tr(row["type"])
    return data


class _ExportMixin:
    def _show_title(self) -> str:
        title = getattr(self, "_show_info", {}).get("title", "")
        if title:
            return title  # 5.6: the title from "Show info", not the file name
        path = getattr(self, "_current_project_path", None)
        return Path(path).stem if path else tr("Spettacolo")

    def _export_list_csv(self) -> None:
        from engine.cue_export import rows, to_csv

        start = str(Path(self._current_project_path).with_suffix(".csv")) if getattr(
            self, "_current_project_path", None) else tr("scaletta") + ".csv"
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta la scaletta"), start, "CSV (*.csv)")
        if not path:
            return
        try:
            to_csv(_type_names(rows(self._cues, follow_names())), path, export_headers())
        except OSError as exc:
            QMessageBox.warning(self, tr("Esporta la scaletta"), str(exc))
            return
        self._status_label.setText(tr("Scaletta esportata: {}").format(path))

    def _export_list_xlsx(self) -> None:
        """File → Export and print → "Export the cue list (Excel)…": a real .xlsx, no extra library."""
        from engine.cue_export import rows, to_xlsx

        start = str(Path(self._current_project_path).with_suffix(".xlsx")) if getattr(
            self, "_current_project_path", None) else "scaletta.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta la scaletta"), start, "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            to_xlsx(rows(self._cues, follow_names()), path, export_headers(), sheet=tr("Scaletta"),
                    title=self._show_title())
        except OSError as exc:
            QMessageBox.warning(self, tr("Esporta la scaletta"), str(exc))
            return
        self._status_label.setText(tr("Scaletta esportata: {}").format(path))

    def _export_list_pdf(self, variant: str) -> None:
        """The operator's / the prompter's list as a PDF, made here (no web browser needed)."""
        from engine.cue_export import rows, to_html
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

        word = tr("regia") if variant == "operator" else tr("suggeritore")
        title = self._show_title() + " – " + word
        base = Path(self._current_project_path).with_suffix("") if getattr(
            self, "_current_project_path", None) else Path("scaletta")
        path, _ = QFileDialog.getSaveFileName(self, tr("Scaletta in PDF"), f"{base} – {word}.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        doc = QTextDocument()
        doc.setHtml(to_html(rows(self._cues, follow_names()), title, variant, export_headers()))
        writer = QPdfWriter(path)
        writer.setTitle(title)
        writer.setCreator("BlindCue")
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        # The prompter's list has more columns: landscape; the operator's big letters: portrait.
        writer.setPageOrientation(QPageLayout.Orientation.Landscape if variant == "prompter"
                                  else QPageLayout.Orientation.Portrait)
        before = Path(path).stat().st_mtime if Path(path).is_file() else None
        doc.print_(writer)
        del writer  # closes the file
        # An older PDF open in a viewer stays as it was: say so instead of "saved".
        if not Path(path).is_file() or (before is not None and Path(path).stat().st_mtime == before):
            QMessageBox.warning(self, tr("Scaletta in PDF"), tr("Impossibile scrivere il file:\n{}").format(path))
            return
        self._status_label.setText(tr("Scaletta salvata in PDF: {}").format(path))

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
