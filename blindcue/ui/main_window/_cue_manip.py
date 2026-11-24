"""Cue List Manipulation mixin for MainWindow."""

from __future__ import annotations

from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)


class _CueManipMixin:
    _MEDIA_FILTERS = {
        MediaType.VIDEO: "Video (*.mp4 *.mkv *.avi *.mov *.webm)",
        MediaType.AUDIO: "Audio (*.mp3 *.wav *.flac *.ogg *.aac *.m4a)",
        MediaType.IMAGE: "Image (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
    }

    def _on_add_media(self, media_type: MediaType | None) -> None:
        """One kind of media (the menu), or None: "Add files…" - several files of any kind at once."""
        from ui import dialog_dirs

        if media_type is None:
            self._on_add_files()
            return
        titles = {MediaType.VIDEO: tr("Aggiungi video"), MediaType.AUDIO: tr("Aggiungi audio"),
                  MediaType.IMAGE: tr("Aggiungi immagine")}
        file_path, _ = QFileDialog.getOpenFileName(
            self, titles.get(media_type, tr("Aggiungi file")), dialog_dirs.media_dir(media_type.value),
            self._MEDIA_FILTERS.get(media_type, "*.*"))
        if file_path:
            dialog_dirs.remember_media_dir(file_path)
            self._add_cue_from_file(file_path, media_type)

    def _on_add_files(self) -> None:
        """"Add files…": videos, sounds and pictures at once, in name order, after the selection -
        with the same questions as a drop (one playlist / one scene)."""
        from engine.quick_start import natural_key
        from ui import dialog_dirs

        if not self._change_allowed(EDIT_LIST):
            return
        every = " ".join(part.split("(")[1].rstrip(")") for part in self._MEDIA_FILTERS.values())
        filters = ";;".join([f"{tr('Video, suoni e immagini')} ({every})", *self._MEDIA_FILTERS.values()])
        files, _ = QFileDialog.getOpenFileNames(self, tr("Aggiungi file"), dialog_dirs.media_dir(), filters)
        if not files:
            return
        dialog_dirs.remember_media_dir(files[0])
        files.sort(key=lambda f: natural_key(os.path.basename(f)))
        self._on_files_dropped_on_list(files, self._cue_list.currentRow())

    def _add_cue_from_file(self, file_path: str, media_type: MediaType | None = None) -> None:
        if media_type is None:
            media_type = self._detect_media_type(file_path)
        if media_type is None:
            QMessageBox.warning(self, "Unsupported File", f"Cannot determine media type for:\n{file_path}")
            return

        # The name a teacher reads: "Highway To Hell", not "Highway To Hell.mp3" (evaluation 2026-11-24).
        cue = Cue(name=Path(file_path).stem or os.path.basename(file_path), media_type=media_type,
                  file_path=file_path)
        if media_type == MediaType.AUDIO:
            # One player per layer: music on L1 would be cut by the next photo
            # or video (also L1) started with it in "Simultanea" mode.
            cue.layer = 2
        self._append_new_cue(cue)

    def _append_new_cue(self, cue: Cue) -> None:
        """Validate *cue*, insert it after the selected one, select it and record undo.

        See ``insert_position``: a cue tied to the next one (Simultaneous,
        Auto-GO, a group) gets the new cue after the end of its chain or group.
        """
        if not self._change_allowed(EDIT_LIST):
            return
        errors = cue.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return

        if self._undo.is_debounce_active():
            self._commit_undo_point()
        cue.status = CueStatus.LOADED
        sel_row = self._anchor_row_and_cue()[0] if self._selected_rows() else -1
        pos, parent_id = insert_position(self._cues, sel_row)
        cue.parent_id = parent_id
        self._cues.insert(pos, cue)
        self._refresh_cue_list()
        self._cue_list.setCurrentRow(pos)
        if not getattr(self, "_undo_batch", False):
            self._commit_undo_point()
        self._mark_modified(True)
        if 0 <= sel_row and pos != sel_row + 1:
            self._status_label.setText(
                f"Aggiunta dopo '{self._cues[pos - 1].name}', alla fine della catena "
                "Simultanea / Auto-GO o del gruppo"
            )
        else:
            self._status_label.setText(f"Added: {cue}")
        self._auto_save()
        logger.info("Added cue at row %d: %s", pos, cue)

    # ── Text cues (captions) ──────────────────────────────────────────
    def _on_add_text_cue(self) -> None:
        """Create a caption cue on Layer 3 with soft fades."""
        from engine.text_render import render_text_png, text_cue_name
        from ui.text_cue_dialog import TextCueDialog

        dlg = TextCueDialog(None, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        spec = dlg.spec()
        try:
            path = render_text_png(spec)
        except OSError as exc:
            QMessageBox.warning(self, "Cue di testo", str(exc))
            return
        cue = Cue(name=text_cue_name(spec), media_type=MediaType.IMAGE, file_path=path)
        cue.text_spec = spec
        cue.layer = 3
        cue.fade_in = 0.5
        cue.fade_out = 0.5
        self._append_new_cue(cue)

    def _on_edit_text_cue(self) -> None:
        """Re-open the caption editor for the selected text cue."""
        from engine.text_render import render_text_png, text_cue_name
        from ui.text_cue_dialog import TextCueDialog

        cue = self._selected_cue()
        if cue is None or not cue.text_spec:
            QMessageBox.information(
                self, "Cue di testo",
                "Il cue selezionato non è un cue di testo. Aggiungine uno con il pulsante \"+ Testo\".",
            )
            return
        dlg = TextCueDialog(cue.text_spec, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        spec = dlg.spec()
        try:
            path = render_text_png(spec)
        except OSError as exc:
            QMessageBox.warning(self, "Cue di testo", str(exc))
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        if cue.name == text_cue_name(cue.text_spec):
            cue.name = text_cue_name(spec)
        cue.text_spec = spec
        cue.file_path = path
        self._refresh_cue_list()
        self._on_cue_selected(self._cue_list.currentRow())
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    @Slot(str)
    def _on_file_dropped(self, file_path: str) -> None:
        self._add_cue_from_file(file_path)

    @Slot(list)
    def _on_files_dropped_on_zone(self, paths: list) -> None:
        """The quick-add zone: like a drop on the list, after the selected cue (3.3)."""
        self._on_files_dropped_on_list([str(p) for p in paths], self._cue_list.currentRow())

    def _on_files_dropped_on_list(self, paths: list[str], row: int) -> None:
        """Files dropped on the cue list go after the row they were dropped on.

        Below the last row they go to the end. Each new cue becomes the
        selected one, so several files keep the order they were dropped in.
        """
        if not self._change_allowed(EDIT_LIST):
            return
        from engine.playlist_import import PLAYLIST_EXT

        lists = [p for p in paths if Path(p).suffix.lower() in PLAYLIST_EXT]
        media = [p for p in paths if self._detect_media_type(p) is not None]
        skipped = [os.path.basename(p) for p in paths if p not in media and p not in lists]
        sounds = [p for p in media if self._detect_media_type(p) == MediaType.AUDIO]
        # 3.3: several sounds and nothing else -> offered as one playlist row once they are in
        # (not inside a scene: a playlist is a row of the show of its own).
        in_scene = 0 <= row < len(self._cues) and self._cues[row].parent_id is not None
        offer = len(sounds) >= 2 and len(sounds) == len(media) and not lists and not skipped and not in_scene
        # 5.12: several files that are not only sounds -> offered as one step-by-step scene
        offer_scene = len(media) >= 2 and len(sounds) != len(media) and not lists and not skipped and not in_scene
        if 0 <= row < len(self._cues):
            self._cue_list.setCurrentRow(row)
        else:
            self._cue_list.clearSelection()
            self._cue_list.setCurrentCell(-1, -1)
        # One drop = one undo step, however many files it brings.
        self._undo_batch = True
        try:
            added = self._add_files_collect(media)
            for playlist in lists:
                self._import_playlist_file(playlist)
        finally:
            self._undo_batch = False
        if media or lists:
            self._commit_undo_point()
            self._auto_save()  # the playlist row too, not only the files
        if skipped:
            self._status_label.setText(f"File non supportati, ignorati: {', '.join(skipped)}")
        if offer and len(added) >= 2:
            self._offer_playlist(added)
        elif offer_scene and len(added) >= 2:
            self._offer_scene(added)

    def _offer_scene(self, added: list[Cue]) -> None:
        """5.12: the files just dropped (already in the list) may become one scene (its own undo step)."""
        ids = [c.cue_id for c in added]

        def answer(make: bool) -> None:
            self._playlist_question = None
            if not make:
                return
            rows = [i for i, c in enumerate(self._cues) if c.cue_id in ids]
            still = (len(rows) == len(ids) and rows == list(range(rows[0], rows[0] + len(rows)))
                     and all(self._cues[r].parent_id is None for r in rows))
            if not still or not self._change_allowed(EDIT_LIST):
                return  # the list changed meanwhile: they stay separate cues
            if self._undo.is_debounce_active():
                self._commit_undo_point()
            self._make_scene([self._cues[r] for r in rows], tr("Scena ({} elementi)").format(len(rows)))
            self._commit_undo_point()
            self._auto_save()

        self._ask_scene(len(added), answer)

    def _ask_scene(self, count: int, answer) -> None:
        """Ask without blocking (the drop is over): *answer(True)* for one scene."""
        old = getattr(self, "_playlist_question", None)
        if old is not None:
            old.close()
        box = QMessageBox(QMessageBox.Icon.Question, tr("Scena"),
                          tr("{} file: farne una scena (un GO per elemento)?").format(count), parent=self)
        one = box.addButton(tr("Una scena"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cue separate"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(one)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.buttonClicked.connect(lambda button: answer(button is one))
        self._playlist_question = box
        box.open()

    # ── 3.3: playlists ──
    def _ask_playlist(self, count: int, answer) -> None:
        """Ask without blocking (the drop is over, the show goes on): *answer(True)* for one playlist."""
        old = getattr(self, "_playlist_question", None)
        if old is not None:
            old.close()
        box = QMessageBox(QMessageBox.Icon.Question, tr("Playlist"),
                          tr("{} file audio: farne una playlist (una riga che li suona uno dopo l'altro)?").format(count),
                          parent=self)
        one = box.addButton(tr("Una playlist"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Cue separate"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(one)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.buttonClicked.connect(lambda button: answer(button is one))
        self._playlist_question = box
        box.open()

    def _offer_playlist(self, added: list[Cue]) -> None:
        """The sounds just dropped (already in the list) may become one playlist row (its own undo step)."""
        ids = [c.cue_id for c in added]

        def answer(make: bool) -> None:
            self._playlist_question = None
            if not make:
                return
            rows = [i for i, c in enumerate(self._cues) if c.cue_id in ids]
            still = (len(rows) == len(ids) and rows == list(range(rows[0], rows[0] + len(rows)))
                     and all(self._cues[r].parent_id is None for r in rows))
            if not still or not self._change_allowed(EDIT_LIST):
                return  # the list changed meanwhile: they stay separate cues
            if self._undo.is_debounce_active():
                self._commit_undo_point()
            self._make_playlist([self._cues[r] for r in rows], tr("Playlist ({} brani)").format(len(rows)))
            self._commit_undo_point()
            self._auto_save()

        self._ask_playlist(len(added), answer)

    def _add_files_collect(self, files: list[str]) -> list[Cue]:
        """Add *files* after the selection (in order) and return the new cues."""
        before = {c.cue_id for c in self._cues}
        for path in files:
            self._add_cue_from_file(path)
        return [c for c in self._cues if c.cue_id not in before]

    def _make_playlist(self, cues: list[Cue], name: str) -> Cue | None:
        """Wrap the new (contiguous) *cues* in a playlist group: one row that plays them one after another,
        stops after the last one and leaves GO on the next cue of the show. Never inside a scene."""
        if cues[0].parent_id is not None:
            self._status_label.setText(tr("Una playlist non può stare dentro una scena: aggiunte cue separate"))
            return None
        first = next(i for i, c in enumerate(self._cues) if c is cues[0])
        group = Cue(name=name, file_path="", media_type=MediaType.GROUP, group_mode=GroupMode.SEQUENCE.value,
                    color="#0ea5e9", layer=2, collapsed=True, status=CueStatus.LOADED)
        group.playlist = True
        group.playlist_remember = True  # 3.3: interval music goes on with new songs at the next GO
        for cue in cues:
            cue.parent_id = group.cue_id
        self._cues.insert(first, group)
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(first)
        self._mark_modified(True)
        logger.info("[PLAYLIST] '%s' with %d tracks", name, len(cues))
        return group

    def _import_playlist_file(self, path: str) -> Cue | None:
        """An .m3u / .m3u8: its files become one playlist row (missing files and streams are listed)."""
        from engine.playlist_import import read_m3u

        try:
            files, skipped = read_m3u(path)
        except OSError as exc:
            self._status_label.setText(tr("Playlist non leggibile: {}").format(exc))
            return None
        playable = [f for f in files if self._detect_media_type(f) is not None]
        skipped = skipped + [f for f in files if f not in playable]  # e.g. a nested .m3u, a .txt
        files = playable
        group = None
        if files:
            group = self._make_playlist(self._add_files_collect(files), Path(path).stem)
        text = tr("Playlist '{}': {} brani").format(Path(path).stem, len(files))
        if skipped:
            text += " · " + tr("non trovati o in streaming: {}").format(len(skipped))
        self._status_label.setText(text)
        return group

    def _on_import_playlist(self) -> None:
        """File menu: import an .m3u / .m3u8 playlist."""
        if not self._change_allowed(EDIT_LIST):
            return
        from ui import dialog_dirs

        path, _ = QFileDialog.getOpenFileName(self, tr("Importa playlist"), dialog_dirs.media_dir("AUDIO"),
                                              "Playlist (*.m3u *.m3u8)")
        if not path:
            return
        self._undo_batch = True
        try:
            self._import_playlist_file(path)
        finally:
            self._undo_batch = False
        self._commit_undo_point()
        self._auto_save()

    def _move_selected_cue(self, delta: int) -> None:
        sel_rows = self._selected_rows()
        if len(sel_rows) != 1:
            return
        row = sel_rows[0]
        target_row = row + delta
        if not (0 <= row < len(self._cues) and 0 <= target_row < len(self._cues)):
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()

        moving_cue = self._cues[row]
        target_cue = self._cues[target_row]

        # Extract if moving past group boundaries
        if delta < 0 and moving_cue.parent_id == target_cue.cue_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sopra la scena)")
        elif delta > 0 and moving_cue.parent_id is not None and target_cue.parent_id != moving_cue.parent_id:
            moving_cue.parent_id = None
            self._status_label.setText(f"Estratta cue '{moving_cue.name}' dal gruppo (spostata sotto la scena)")

        self._cues[row], self._cues[target_row] = self._cues[target_row], self._cues[row]
        self._current_index = target_row
        self._refresh_cue_list(keep_selection=False, select_row=target_row)
        self._sync_inspector_header_and_text(target_row, self._cues[target_row])
        self._commit_undo_point()
        self._mark_modified(True)
        self._auto_save()

    @Slot()
    def _on_move_up(self) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        self._move_selected_cue(-1)

    @Slot()
    def _on_move_down(self) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        self._move_selected_cue(1)

    @Slot()
    def _on_delete_cue(self) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        focus_w = QApplication.focusWidget()
        if isinstance(focus_w, (QLineEdit, QAbstractSpinBox, QComboBox, QPlainTextEdit)):
            return

        sel_rows = self._selected_rows()
        if not sel_rows:
            return
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        anchor_row, _ = self._anchor_row_and_cue()
        self._undo.update_current_index(anchor_row)

        removed = [self._cues.pop(r) for r in sorted(sel_rows, reverse=True)]
        cleared_slots: set[int] = set()
        for rem in removed:
            had_phase = rem.cue_id in self._live_phase_tags
            if had_phase:
                self._live_phase_tags.pop(rem.cue_id, None)
            if rem.media_type == MediaType.ACTION:
                # No layer of its own: only its pending Pre-Delay / Auto-GO wait goes.
                self.action_cancel_requested.emit(rem.cue_id)
            elif rem.media_type != MediaType.GROUP and (rem.status == CueStatus.LIVE or had_phase):
                slot = self._runtime_slot(rem)
                if slot not in cleared_slots:
                    cleared_slots.add(slot)
                    self._reset_live_label(slot)
                    self.layer_clear_requested.emit(slot)
            if rem.media_type == MediaType.GROUP:
                for c in self._cues:
                    if c.parent_id == rem.cue_id:
                        c.parent_id = None
        first_row = sel_rows[0]
        self._refresh_cue_list(keep_selection=False)
        if self._cues:
            self._cue_list.setCurrentRow(min(first_row, len(self._cues) - 1))
        else:
            self._current_index = -1
            self._reset_idle_preview_ui()
            self._update_inspector(None)
        self._commit_undo_point()
        self._mark_modified(True)
        if len(removed) == 1:
            rem = removed[0]
            self._status_label.setText(
                f"Deleted: {format_cue_ref(first_row, rem)} '{rem.name}' (Ctrl+Z per ripristinare)"
            )
        else:
            self._status_label.setText(
                f"Eliminate {len(removed)} cue selezionate (Ctrl+Z per ripristinare)"
            )
        self._auto_save()
        logger.info("Deleted %d cue(s)", len(removed))
