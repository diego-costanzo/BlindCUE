"""Order in the show's files (stage 5, item 5.10) mixin for MainWindow.

- File → Export and print → "ZIP package with the media…": the show and its
  media in one ZIP; big playlists may stay out (a question when there are).
- File → Backups and missing files → "Set aside unused files…": files in the
  show's media folder that nothing uses (nor a backup copy) go into its
  ``_unused`` subfolder after a list - never deleted.
- Row menu → The file → "Rename the file…": renamed on disk, every cue that
  uses it and the undo steps follow.
The logic is in ``engine.show_package``.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QInputDialog

from ui.main_window._common import *  # noqa: F403,F401,F405


def _mb(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


class _ShowFilesMixin:
    # ── ZIP package ──
    def _export_zip_package(self) -> None:
        from engine.show_package import (
            BIG_PLAYLIST_BYTES,
            big_playlist_files,
            playlists,
            write_zip,
        )

        from ui import dialog_dirs

        title = tr("Pacchetto ZIP")
        if not self._cues:
            self._status_label.setText(tr("Scaletta vuota: niente da mettere nel pacchetto"))
            return
        self._apply_inspector_to_cue()
        path = getattr(self, "_current_project_path", None)
        stem = Path(path).stem if path else tr("Spettacolo")
        start = str(Path(path).with_suffix(".zip")) if path else str(Path(dialog_dirs.show_dir()) / f"{stem}.zip")
        target, _ = QFileDialog.getSaveFileName(self, title, start, "ZIP (*.zip)")
        if not target:
            return
        if not target.lower().endswith(".zip"):
            target += ".zip"
        exclude: set[str] = set()
        big = [(g, total) for g, total, _files in playlists(self._cues) if total > BIG_PLAYLIST_BYTES]
        if big:
            lines = "\n".join(f"• {g.name}: {_mb(total)}" for g, total in big[:10])
            answer = QMessageBox.question(
                self, title,
                tr("Playlist grandi:\n{}\n\nLasciarle fuori dal pacchetto? Il pacchetto resta piccolo; sull'altro "
                   "computer quelle cue cercano i file dove sono qui (copiali a parte).").format(lines),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Yes:
                exclude = big_playlist_files(self._cues)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = write_zip(target, stem, self._cues, self._document_settings(),
                               current_index=self._current_index, exclude=exclude)
        except Exception as exc:  # noqa: BLE001 - a failed package never takes the program down
            logger.warning("[ZIP] %s: %s", target, exc, exc_info=True)
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, title, tr("Impossibile scrivere il file:\n{}").format(f"{target}\n{exc}"))
            return
        QApplication.restoreOverrideCursor()
        text = tr("Pacchetto ZIP scritto: {} file, {}").format(result.files, _mb(result.size))
        self._status_label.setText(text)
        notes = []
        if result.excluded:
            notes.append(tr("Lasciati fuori (playlist grandi): {}").format(len(result.excluded)))
        if result.missing:
            notes.append(tr("File mancanti, non nel pacchetto:") + "\n" + "\n".join(result.missing[:15]))
        if notes:
            QMessageBox.information(self, title, text + "\n\n" + "\n\n".join(notes))

    # ── unused files ──
    def _tidy_media_folder(self) -> None:
        from engine.show_package import (
            references,
            references_in_show_file,
            set_aside,
            unused_media,
        )
        from models.project_manager import backups_of

        title = tr("File non usati")
        path = getattr(self, "_current_project_path", None)
        media_dir = ProjectManager.media_dir_for(path) if path else None
        if media_dir is None or not media_dir.is_dir():
            QMessageBox.information(self, title, tr(
                "Questo spettacolo non ha una cartella dei media: c'è solo quando è salvato come spettacolo "
                "portatile (i file copiati accanto)."))
            return
        self._apply_inspector_to_cue()
        used = references(self._cues, self._document_settings())
        for show in [Path(path), *backups_of(path)]:
            used |= references_in_show_file(show, Path(path).parent)  # a backup copy must still find its files
        unused = unused_media(media_dir, used)
        if not unused:
            self._status_label.setText(tr("Nessun file non usato in {}").format(media_dir.name))
            QMessageBox.information(self, title, tr("Tutti i file della cartella dei media sono usati."))
            return
        size = sum(p.stat().st_size for p in unused if p.exists())
        names = "\n".join(f"• {p.relative_to(media_dir)}" for p in unused[:20])
        more = "\n" + tr("… e altre {}").format(len(unused) - 20) if len(unused) > 20 else ""
        answer = QMessageBox.question(
            self, title,
            tr("{} file ({}) della cartella dei media non sono usati da nessuna cue né dalle copie di "
               "sicurezza:\n{}\n\nMetterli da parte nella sottocartella «_unused»? Non vengono cancellati."
               ).format(len(unused), _mb(size), names + more),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            moved = set_aside(media_dir, unused)
        except OSError as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        self._status_label.setText(tr("Messi da parte {} file in {}").format(len(moved), f"{media_dir.name}/_unused"))

    # ── renaming a media file ──
    def _rename_media_file(self, row: int) -> None:
        from engine.show_package import rename_in_cues, rename_in_dicts, rename_target

        title = tr("Rinomina il file")
        if not self._change_allowed(EDIT_LIST) or not 0 <= row < len(self._cues):
            return
        cue = self._cues[row]
        old = cue.file_path or ""
        if cue.text_spec or not old or not os.path.isfile(old):
            self._status_label.setText(tr("Questa cue non ha un file da rinominare"))
            return
        users = [c for c in self._cues if c.file_path and os.path.normcase(os.path.abspath(c.file_path))
                 == os.path.normcase(os.path.abspath(old))]
        if any(c.status == CueStatus.LIVE for c in users):
            self._status_label.setText(tr("Il file è in onda: fermalo prima di rinominarlo"))
            return
        name, ok = QInputDialog.getText(
            self, title, tr("Nuovo nome per «{}» (le {} cue che lo usano seguono; altri spettacoli che lo usano "
                            "non lo troveranno più):").format(Path(old).name, len(users)), text=Path(old).stem)
        if not ok or not name.strip():
            return
        new = rename_target(old, name)
        if os.path.normcase(str(new)) == os.path.normcase(old):
            return
        if new.exists():
            QMessageBox.warning(self, title, tr("C'è già un file con questo nome:\n{}").format(new))
            return
        was_modified = self._is_modified
        test_player = getattr(self, "_test_player", None)
        if test_player is not None and hasattr(test_player, "stop"):
            test_player.stop()  # the preview may hold the file open
        try:
            os.rename(old, new)
        except OSError as exc:
            QMessageBox.warning(self, title, tr("Impossibile rinominare il file: è aperto in un altro programma o "
                                                "nell'anteprima (seleziona prima un'altra cue).\n{}").format(exc))
            return
        self._apply_inspector_to_cue()
        count = rename_in_cues(self._cues, old, str(new))
        for snapshot in (*self._undo._undo_stack, *self._undo._redo_stack, self._undo._committed_state):
            if isinstance(snapshot, dict):
                rename_in_dicts(snapshot.get("cues", []), old, str(new))   # Ctrl+Z never brings the old name back
        for attr in ("_layer0_image", "_layer0_video"):
            value = getattr(self, attr, None)
            if value and os.path.normcase(os.path.abspath(value)) == os.path.normcase(os.path.abspath(old)):
                setattr(self, attr, str(new))
        for cache in (getattr(self, "_waveform_cache", {}), getattr(self, "_known_file_durations", {})):
            if old in cache:
                cache[str(new)] = cache.pop(old)
        self._refresh_cue_list(keep_selection=True)
        self._last_selection_sig = None
        self._sync_selection_state()
        self._mark_modified(True)
        path = getattr(self, "_current_project_path", None)
        if path and not was_modified:
            self._do_save(path)  # the saved show names the new file at once (it had no other changes)
        else:
            self._auto_save()
        self._status_label.setText(tr("File rinominato in «{}»: {} riferimenti aggiornati").format(new.name, count))
