"""Take cues over from another show (stage 5, item 5.3) mixin for MainWindow.

File → "Import cues from another show…": pick the show file, tick the cues
to take (a scene brings its cues), see what will not come along (links to
cues left behind, missing files) and add them after the selection - one
Ctrl+Z. They get new numbers inside, so nothing collides with this show.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QDialogButtonBox, QListWidget, QListWidgetItem

from ui.main_window._common import *  # noqa: F403,F401,F405


def warning_text(kind: str, name: str, count: int) -> str:
    if kind == "relative":
        return tr("'{}': partenza relativa a una cue non importata – parte con il GO").format(name)
    if kind == "targets":
        return tr("'{}': {} cue bersaglio non importate").format(name, count)
    return tr("'{}': file non trovato").format(name)


class _ShowImportMixin:
    def _import_from_show(self) -> None:
        from engine.show_engine import insert_position
        from engine.show_import import take_over
        from engine.show_mode import EDIT_LIST

        if not self._change_allowed(EDIT_LIST):
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Importa cue da un altro spettacolo"), "",
                                              "BlindCue (*.blindcue)")
        if not path:
            return
        try:
            other, _index, _settings = ProjectManager().load_project(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Importa cue da un altro spettacolo"), str(exc))
            return
        chosen = self._choose_cues_to_import(other)
        if not chosen:
            return
        new_cues, warnings = take_over(other, chosen)
        for cue in new_cues:
            cue.status = CueStatus.OFFLINE if cue.media_type.has_file and not os.path.isfile(cue.file_path) \
                else CueStatus.LOADED
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        top = self._anchor_row_and_cue()[0] if self._selected_rows() else len(self._cues) - 1
        while 0 <= top < len(self._cues) and self._cues[top].parent_id is not None:
            parent = self._cues[top].parent_id
            top = next((i for i, c in enumerate(self._cues) if c.cue_id == parent), -1)
        at, _parent = insert_position(self._cues, top) if top >= 0 else (len(self._cues), None)
        self._cues[at:at] = new_cues
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(at)
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()
        self._status_label.setText(tr("Importate {} cue da '{}'").format(len(new_cues), Path(path).stem))
        if warnings:
            QMessageBox.information(self, tr("Importa cue da un altro spettacolo"),
                                    "\n".join(warning_text(*w) for w in warnings[:20]))

    def _choose_cues_to_import(self, other: list[Cue]) -> list[int]:
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Importa cue da un altro spettacolo"))
        dlg.resize(480, 520)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("Spunta le cue da importare (una scena porta le sue cue):")))
        listing = QListWidget()
        for i, cue in enumerate(other):
            indent = "    " if cue.parent_id is not None else ""
            item = QListWidgetItem(f"{indent}#{i + 1} {cue.q_label or ''} {cue.name}".replace("  ", " ", 1))
            item.setData(Qt.ItemDataRole.UserRole, cue.cue_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            listing.addItem(item)
        lay.addWidget(listing, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return []
        return [int(listing.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(listing.count())
                if listing.item(i).checkState() == Qt.CheckState.Checked]
