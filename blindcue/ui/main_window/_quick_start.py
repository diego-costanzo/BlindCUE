"""A quick start of a show (stage 5, item 5.9) mixin for MainWindow.

- File → "New show from a folder…": the folder's media in name order
  (1, 2, 10), as separate cues or as one scene (sounds: one playlist).
- File → "Import a cue list (CSV)…": a list written in a spreadsheet
  (Q, name, type, file, page, line, notes) becomes cues after the
  selection; a row without a file is a cue that waits for its file.
- Pinned shows stay at the top of "Open recent" and never drop out of it.
"""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405

_PINNED_KEY = "recent/pinned"


class _QuickStartMixin:
    # ── New show from a folder ──
    def _new_show_from_folder(self) -> None:
        from engine.quick_start import media_in_folder

        if not self._change_allowed(EDIT_LIST):
            return
        from ui import dialog_dirs

        folder = QFileDialog.getExistingDirectory(self, tr("Nuovo spettacolo da una cartella"),
                                                  dialog_dirs.media_dir())
        if not folder:
            return
        dialog_dirs.remember_media_dir(folder)
        files = media_in_folder(folder, lambda p: self._detect_media_type(p) is not None)
        if not files:
            QMessageBox.information(self, tr("Nuovo spettacolo da una cartella"),
                                    tr("Nella cartella non ci sono video, suoni o immagini."))
            return
        sounds_only = all(self._detect_media_type(f) == MediaType.AUDIO for f in files)
        together = self._ask_folder_layout(len(files), sounds_only)
        if together is None or not self._on_new_show():
            return
        self._cue_list.setCurrentRow(len(self._cues) - 1)
        self._undo_batch = True
        try:
            added = self._add_files_collect(files)
        finally:
            self._undo_batch = False
        if together and len(added) >= 2:
            name = Path(folder).name
            if sounds_only:
                self._make_playlist(added, name)
            else:
                self._make_scene(added, name)
        self._commit_undo_point()
        self._auto_save()
        self._status_label.setText(tr("Nuovo spettacolo: {} file da '{}'").format(len(added), Path(folder).name))

    def _ask_folder_layout(self, count: int, sounds_only: bool) -> bool | None:
        """True = one scene (playlist for sounds), False = separate cues, None = cancelled."""
        box = QMessageBox(QMessageBox.Icon.Question, tr("Nuovo spettacolo da una cartella"),
                          tr("{} file in ordine di nome. Come aggiungerli?").format(count), parent=self)
        separate = box.addButton(tr("Cue separate"), QMessageBox.ButtonRole.AcceptRole)
        one = box.addButton(tr("Una playlist") if sounds_only else tr("Una scena (un GO per elemento)"),
                            QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(separate)
        box.exec()
        clicked = box.clickedButton()
        if clicked is separate:
            return False
        if clicked is one:
            return True
        return None

    def _make_scene(self, cues: list[Cue], name: str) -> Cue:
        """Wrap the new (contiguous, top level) *cues* in a step-by-step scene."""
        first = next(i for i, c in enumerate(self._cues) if c is cues[0])
        group = Cue(name=name, file_path="", media_type=MediaType.GROUP, group_mode=GroupMode.STEP.value,
                    color="#6366f1", layer=1, collapsed=False, status=CueStatus.LOADED)
        for cue in cues:
            cue.parent_id = group.cue_id
        self._cues.insert(first, group)
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(first)
        self._mark_modified(True)
        return group

    # ── A cue list from a spreadsheet ──
    def _import_skeleton(self) -> None:
        from engine.quick_start import read_skeleton, resolve_file
        from engine.show_engine import insert_position

        if not self._change_allowed(EDIT_LIST):
            return
        from ui import dialog_dirs

        path, _ = QFileDialog.getOpenFileName(self, tr("Importa una scaletta (CSV)"), dialog_dirs.show_dir(),
                                              "CSV (*.csv *.txt)")
        if not path:
            return
        try:
            rows = read_skeleton(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Importa una scaletta (CSV)"),
                                tr("Il file non è una scaletta: serve una prima riga con i nomi delle "
                                   "colonne (almeno Nome o File).") + f"\n\n{exc}")
            return
        if not rows:
            self._status_label.setText(tr("Nessuna riga da importare"))
            return
        new_cues = []
        waiting = 0
        for row in rows:
            file = resolve_file(row["file"], path)
            kind = self._detect_media_type(file) if file else None
            if kind is None:
                kind = next((t for t in (MediaType.VIDEO, MediaType.AUDIO, MediaType.IMAGE)
                             if row["type"].upper() == t.value), MediaType.AUDIO)
            cue = Cue(name=row["name"] or Path(file).stem, file_path=file, media_type=kind,
                      layer=2 if kind == MediaType.AUDIO else 1)
            cue.q_label = row["q"]
            cue.notes = row["notes"]
            cue.script_page = row["page"]
            cue.script_line = row["line"]
            cue.status = CueStatus.LOADED if file and os.path.isfile(file) else CueStatus.OFFLINE
            waiting += cue.status == CueStatus.OFFLINE
            new_cues.append(cue)
        self._apply_inspector_to_cue()
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
        text = tr("Importate {} righe da '{}'").format(len(new_cues), Path(path).name)
        if waiting:
            text += " · " + tr("senza file (da collegare): {}").format(waiting)
        self._status_label.setText(text)

    # ── Pinned shows in "Open recent" ──
    def _pinned_projects(self) -> list[str]:
        try:
            raw = self._settings().value(_PINNED_KEY, [], type=list)
        except Exception:  # a broken settings backend must not block the menu
            return []
        return [str(p) for p in (raw or []) if isinstance(p, str) and p.strip()]

    def _set_pinned(self, path: str, pinned: bool) -> None:
        key = self._recent_key(path)
        items = [p for p in self._pinned_projects() if p != key]
        if pinned:
            items.append(key)
        self._settings().setValue(_PINNED_KEY, items)

    def _toggle_pin_current(self) -> None:
        path = getattr(self, "_current_project_path", None)
        if not path:
            self._status_label.setText(tr("Salva prima lo spettacolo, poi fissalo"))
            return
        pinned = self._recent_key(path) in self._pinned_projects()
        self._set_pinned(path, not pinned)
        self._status_label.setText(tr("Spettacolo fissato in 'Apri recenti'") if not pinned
                                   else tr("Spettacolo non più fissato"))
