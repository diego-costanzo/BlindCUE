"""Files of the show found again or chosen anew (stage 5, item 5.10) mixin for MainWindow.

- File → "Find missing files…": point at a folder (a USB stick, the
  show's folder on another computer) and every missing file found there by
  its name is used again – all at once, one Ctrl+Z.
- Right click on a cue → "Choose the file…": another file for this cue (or
  the first one for a cue from an imported list); its settings stay.
"""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405


class _RelinkMixin:
    def _relink_setup(self) -> None:
        self._cue_list.file_choose_requested.connect(self._choose_file_for_cue)

    def _missing_file_cues(self) -> list[Cue]:
        return [c for c in self._cues if c.media_type.has_file and not getattr(c, "text_spec", None)
                and c.file_path and not os.path.isfile(c.file_path)]

    def _find_missing_files(self) -> None:
        from engine.relink import find_in_folder

        if not self._change_allowed(EDIT_LIST):
            return
        missing = self._missing_file_cues()
        if not missing:
            empty = sum(1 for c in self._cues if c.media_type.has_file and not getattr(c, "text_spec", None)
                        and not c.file_path)
            self._status_label.setText(
                tr("Cue senza file: {} – clic destro → Scegli il file…").format(empty) if empty
                else tr("Tutti i file sono al loro posto"))
            return
        from ui import dialog_dirs

        folder = QFileDialog.getExistingDirectory(self, tr("Cerca i file mancanti in una cartella"),
                                                  dialog_dirs.media_dir())
        if not folder:
            return
        found, twice = find_in_folder({c.file_path for c in missing}, folder)
        if not found:
            QMessageBox.information(self, tr("Cerca i file mancanti in una cartella"),
                                    tr("Nessuno dei {} file mancanti è in questa cartella.").format(len(missing)))
            return
        self._apply_inspector_to_cue()
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        fixed = 0
        for cue in missing:
            new = found.get(cue.file_path)
            if new:
                cue.file_path = new
                if cue.status == CueStatus.OFFLINE:
                    cue.status = CueStatus.LOADED
                fixed += 1
        self._after_file_change()
        text = tr("File ritrovati: {} di {}").format(fixed, len(missing))
        if twice:
            text += "\n" + tr("Nomi trovati più volte (usato il primo): {}").format(", ".join(sorted(twice)[:5]))
        QMessageBox.information(self, tr("Cerca i file mancanti in una cartella"), text)

    def _choose_file_for_cue(self) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        cue = self._selected_cue()
        if cue is None or not cue.media_type.has_file or getattr(cue, "text_spec", None):
            self._status_label.setText(tr("Scegli una cue video, audio o immagine"))
            return
        from ui import dialog_dirs

        start = os.path.dirname(cue.file_path) if cue.file_path and os.path.isdir(os.path.dirname(cue.file_path)) \
            else dialog_dirs.media_dir(cue.media_type.value)
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Scegli il file per '{}'").format(cue.name), start,
            "Media (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.ogg *.aac *.m4a "
            "*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        kind = self._detect_media_type(path)
        if kind is None:
            self._status_label.setText(tr("Formato non supportato: {}").format(os.path.basename(path)))
            return
        self._apply_inspector_to_cue()
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.file_path = path
        cue.media_type = kind
        if not cue.name:
            cue.name = Path(path).stem
        if cue.status == CueStatus.OFFLINE:
            cue.status = CueStatus.LOADED
        self._after_file_change()
        self._status_label.setText(tr("'{}' suona ora: {}").format(cue.name, os.path.basename(path)))

    def _after_file_change(self) -> None:
        self._commit_undo_point()
        self._mark_modified(True)
        self._refresh_cue_list(keep_selection=True)
        self._last_selection_sig = None
        self._sync_selection_state()  # the inspector shows the new file (not the old one written back)
        self._auto_save()
