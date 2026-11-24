"""Title, author and notes of the show, with its numbers (stage 5, item 5.6) mixin for MainWindow.

File → "Show info…": the title (used on the printed lists instead of the
file name), the author and free notes are saved in the show; below them the
numbers of the show (cues of each kind, how many GOs, effects, cues switched
off, missing files). Read only in the Show mode.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit

from ui.main_window._common import *  # noqa: F403,F401,F405

INFO_KEYS = ("title", "author", "notes")


def stats_text(stats: dict[str, int]) -> str:
    return tr(
        "Cue: {} · GO: {} · video {} · audio {} · immagini {} · testi {} · scene {} · azioni {} · "
        "effetti {} · escluse {} · file mancanti {}"
    ).format(stats["cues"], stats["go"], stats["video"], stats["audio"], stats["pictures"], stats["texts"],
             stats["scenes"], stats["actions"], stats["effects"], stats["off"], stats["missing"])


class _ShowInfoMixin:
    def _show_info_settings(self) -> dict:
        info = {k: v for k, v in getattr(self, "_show_info", {}).items() if k in INFO_KEYS and v}
        return {"info": info} if info else {}

    def _show_info_load(self, settings: dict | None) -> None:
        raw = (settings or {}).get("info", {})
        self._show_info = {k: str(raw.get(k, "")) for k in INFO_KEYS} if isinstance(raw, dict) else {}

    def _open_show_info(self) -> None:
        from engine.show_mode import SHOW
        from engine.show_stats import show_stats

        info = getattr(self, "_show_info", {})
        read_only = self._current_mode() == SHOW
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Informazioni sullo spettacolo"))
        dlg.resize(520, 420)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        edit_title = QLineEdit(info.get("title", ""))
        edit_title.setPlaceholderText(self._show_title())
        edit_author = QLineEdit(info.get("author", ""))
        edit_notes = QPlainTextEdit(info.get("notes", ""))
        for w in (edit_title, edit_author, edit_notes):
            w.setReadOnly(read_only)
        form.addRow(QLabel(tr("Titolo:")), edit_title)
        form.addRow(QLabel(tr("Autore / regia:")), edit_author)
        form.addRow(QLabel(tr("Note:")), edit_notes)
        lay.addLayout(form, 1)
        numbers = QLabel(stats_text(show_stats(self._cues)))
        numbers.setWordWrap(True)
        numbers.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(numbers)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close if read_only else
                                   QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted or read_only:
            return
        new = {"title": edit_title.text().strip(), "author": edit_author.text().strip(),
               "notes": edit_notes.toPlainText().strip()}
        if new != {k: info.get(k, "") for k in INFO_KEYS}:
            self._show_info = new
            self._mark_modified(True)
            self._status_label.setText(tr("Informazioni sullo spettacolo salvate con lo spettacolo"))
