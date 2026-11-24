"""Take cues over from another show (stage 5, item 5.3) mixin for MainWindow.

File → "Import cues from another show…": pick the show file, tick the cues
to take (a scene brings its cues), see what will not come along (links to
cues left behind, missing files) and add them after the selection - one
Ctrl+Z. They get new numbers inside, so nothing collides with this show.
File → "Import a show of SCS 11…" reads an ``.scs11`` file
(``engine.scs_import``) the same way, every cue ticked. In both, the window
lists the warnings for the ticked cues BEFORE anything is added.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
)

from ui.main_window._common import *  # noqa: F403,F401,F405

_SCS_SUB_WORDS = {"K": "luci (DMX)", "M": "messaggio di controllo", "R": "avvio di un programma",
                  "T": "posizione di un'altra cue", "U": "time code", "J": "attiva / disattiva cue",
                  "I": "ingresso dal vivo"}


def warning_text(kind: str, name: str, count: int, detail: str = "") -> str:
    if kind == "relative":
        return tr("'{}': partenza relativa a una cue non importata – parte con il GO").format(name)
    if kind == "targets":
        return tr("'{}': {} cue bersaglio non importate").format(name, count)
    if kind == "tie":
        return tr("'{}': legata a una cue non importata (Simult. / Auto-GO) – ora parte con il GO").format(name)
    if kind == "enabled":
        return tr("'{}': era esclusa in quello spettacolo – qui è inclusa").format(name)
    if kind == "key":
        return tr("'{}': il suo tasto è già usato da un effetto di questo spettacolo").format(name)
    if kind == "clock":
        return tr("'{}': parte a un'ora del giorno").format(name)
    if kind == "call":
        return tr("'{}': parte solo da un'azione, che non è stata importata").format(name)
    if kind.startswith("scs_"):
        return scs_warning_text(kind, name, detail)
    return tr("'{}': file non trovato").format(name)


def scs_warning_text(kind: str, name: str, detail: str) -> str:
    """5.3: what of an SCS cue does not come along."""
    if kind == "scs_sub":
        what = tr(_SCS_SUB_WORDS.get(detail, "")) or detail
        return tr("'{}': parte SCS non importata ({})").format(name, what)
    if kind == "scs_start":
        return tr("'{}': partenza SCS «{}» non disponibile – parte con il GO").format(name, detail)
    if kind == "scs_start_ref":
        return tr("'{}': partenza automatica dopo «{}», che non ha un file – parte con il GO").format(name, detail)
    if kind == "scs_key":
        return tr("'{}': il tasto «{}» non è una lettera o una cifra – effetto senza tasto").format(name, detail)
    if kind == "scs_target":
        return tr("'{}': la cue «{}» non c'è – azione senza quel bersaglio").format(name, detail)
    if kind == "scs_loop":
        return tr("'{}': il loop di una parte del file non c'è – si ripete tutto il file").format(name)
    if kind == "scs_pan":
        return tr("'{}': il panorama (sinistra / destra) non viene importato").format(name)
    if kind == "scs_envelope":
        return tr("'{}': i livelli dentro il file non vengono importati").format(name)
    if kind == "scs_devices":
        return tr("'{}': più uscite audio – si usa l'uscita del palco").format(name)
    if kind == "scs_after_sub":
        return tr("'{}': una parte partiva alla fine della precedente – ora partono insieme").format(name)
    if kind == "scs_sfr":
        return tr("'{}': l'azione SCS «{}» non viene importata").format(name, detail)
    if kind == "scs_offset":
        return tr("'{}': partenza oltre 600 s – accorciata a 600 s").format(name)
    if kind == "scs_repeat":
        return tr("'{}': cue SCS con più parti – controllala nella prova").format(name)
    if kind == "scs_group_start":
        return tr("'{}': una scena o una playlist qui non parte da sola (tasto, chiamata o partenza "
                  "automatica) – parte con il GO").format(name)
    return f"'{name}': {kind} {detail}".strip()


class _ShowImportMixin:
    def _import_from_show(self) -> None:
        from engine.show_mode import EDIT_LIST

        from ui import dialog_dirs

        if not self._change_allowed(EDIT_LIST):
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Importa cue da un altro spettacolo"), dialog_dirs.show_dir(),
                                              "BlindCue (*.blindcue)")
        if not path:
            return
        try:
            other, _index, _settings = ProjectManager().load_project(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Importa cue da un altro spettacolo"), str(exc))
            return
        chosen = self._choose_cues_to_import(other)
        if chosen:
            self._insert_imported(other, chosen, Path(path).stem)

    def _import_scs_show(self) -> None:
        """5.3: an SCS 11 show (.scs11): every cue ticked, what does not map listed before OK."""
        from engine.scs_import import read_scs
        from engine.show_mode import EDIT_LIST

        from ui import dialog_dirs

        if not self._change_allowed(EDIT_LIST):
            return
        title = tr("Importa uno spettacolo SCS")
        path, _ = QFileDialog.getOpenFileName(self, title, dialog_dirs.show_dir(), "SCS 11 (*.scs11)")
        if not path:
            return
        try:
            show = read_scs(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        if not show.cues:
            QMessageBox.information(self, title, tr("Nessuna cue in questo file."))
            return
        was_empty = not self._cues
        chosen = self._choose_cues_to_import(show.cues, checked=True, conversion=show.warnings,
                                             title=title)
        if not chosen:
            return
        self._insert_imported(show.cues, chosen, Path(path).stem)
        info = dict(getattr(self, "_show_info", {}))
        if was_empty and show.title and not info.get("title"):
            info["title"] = show.title  # a new show made from SCS keeps its title
            self._show_info = info

    def _insert_imported(self, other: list[Cue], chosen: list[int], source: str) -> None:
        from engine.show_engine import insert_position
        from engine.show_import import take_over

        self._apply_inspector_to_cue()
        new_cues, _warnings = take_over(other, chosen, self._cues)  # the warnings were shown before OK
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
        self._status_label.setText(tr("Importate {} cue da '{}'").format(len(new_cues), source))

    def _choose_cues_to_import(self, other: list[Cue], checked: bool = False,
                               conversion: dict[int, list] | None = None, title: str = "") -> list[int]:
        """Tick the cues; the warnings for what is ticked show below the list, before OK (5.3)."""
        from engine.show_import import chosen_with_children, preview

        dlg = QDialog(self)
        dlg.setWindowTitle(title or tr("Importa cue da un altro spettacolo"))
        dlg.resize(620, 640)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("Spunta le cue da importare (una scena porta le sue cue):")))
        listing = QListWidget()
        listing.setObjectName("import_cues")
        for i, cue in enumerate(other):
            indent = "    " if cue.parent_id is not None else ""
            item = QListWidgetItem(f"{indent}#{i + 1} {cue.q_label or ''} {cue.name}".replace("  ", " ", 1))
            item.setData(Qt.ItemDataRole.UserRole, cue.cue_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if checked and cue.parent_id is None
                               else Qt.CheckState.Unchecked)
            listing.addItem(item)
        row_buttons = QHBoxLayout()
        btn_all = QPushButton(tr("Tutte"))
        btn_none = QPushButton(tr("Nessuna"))
        row_buttons.addWidget(btn_all)
        row_buttons.addWidget(btn_none)
        row_buttons.addStretch(1)
        warn_label = QLabel()
        warn_list = QListWidget()
        warn_list.setObjectName("import_warnings")
        warn_list.setWordWrap(True)
        lower = QWidget()
        lower_lay = QVBoxLayout(lower)
        lower_lay.setContentsMargins(0, 0, 0, 0)
        lower_lay.addWidget(warn_label)
        lower_lay.addWidget(warn_list, 1)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(listing)
        split.addWidget(lower)
        split.setSizes([380, 200])
        lay.addWidget(split, 1)
        lay.addLayout(row_buttons)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        def ticked() -> list[int]:
            return [int(listing.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(listing.count())
                    if listing.item(i).checkState() == Qt.CheckState.Checked]

        def refresh(*_args) -> None:
            ids = ticked()
            coming = chosen_with_children(other, ids)
            lines = []
            for cue_id, items in (conversion or {}).items():
                if cue_id in coming or (cue_id == 0 and coming):
                    lines += [warning_text(*w) for w in items]
            lines += [warning_text(*w) for w in preview(other, ids, self._cues)]
            warn_list.clear()
            for line in lines[:300]:
                warn_list.addItem("⚠ " + line)
            if len(lines) > 300:
                warn_list.addItem(tr("… e altre {}").format(len(lines) - 300))
            warn_label.setText(tr("Da sapere prima di importare ({}):").format(len(lines)) if lines
                               else tr("Niente da segnalare per le cue spuntate."))
            ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
            ok.setEnabled(bool(coming))
            ok.setText(tr("Importa {} cue").format(len(coming)))

        def tick_all(state: Qt.CheckState) -> None:
            listing.blockSignals(True)
            for i in range(listing.count()):
                listing.item(i).setCheckState(state)
            listing.blockSignals(False)
            refresh()

        btn_all.clicked.connect(lambda: tick_all(Qt.CheckState.Checked))
        btn_none.clicked.connect(lambda: tick_all(Qt.CheckState.Unchecked))
        listing.itemChanged.connect(refresh)
        refresh()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return []
        return ticked()
