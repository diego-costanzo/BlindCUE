"""Persistence & Crash Recovery mixin for MainWindow."""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)
from models.output_config import OutputConfig


class _PersistenceMixin:
    # Last opened/saved projects, most recent first. Kept in QSettings (not in
    # the project file) so the list survives across sessions and machines.
    _RECENT_PROJECTS_KEY = "file/recent_projects"
    _RECENT_PROJECTS_LIMIT = 5

    def _output_settings(self) -> dict[str, str]:
        """Return the persistable output routing block, if hardware is wired."""
        if self._device_mgr is None:
            return {}
        return {"mode": self._device_mgr.get_output_mode()}

    def _apply_output_settings(self, settings: object) -> None:
        """Restore the output routing stored in a project or autosave payload."""
        if self._device_mgr is None or not isinstance(settings, dict):
            return
        raw = settings.get("output")
        if not raw:
            return
        mode = OutputConfig.from_dict(raw).mode
        if not self._device_mgr.set_output_mode(mode):
            logger.warning(
                "[PROJECT] Modalità uscita '%s' non applicabile con gli schermi attuali", mode
            )

    def _auto_save(self) -> None:
        if not (self._cues or self._layer0_image):
            return
        if self._autosave_in_progress:
            # A previous background write is still running: remember to re-run
            # once it finishes so the latest state is never lost.
            self._autosave_retry_pending = True
            return
        try:
            self._apply_inspector_to_cue()
            settings: dict[str, Any] = {"layer0_image": self._layer0_image} if self._layer0_image else {}
            settings["surfaces"] = [s.to_dict() for s in self._surfaces]
            output = self._output_settings()
            if output:
                settings["output"] = output
            # After a crash during the show the restore question offers to go back into it.
            settings["live_mode"] = bool(self._live_mode)
            payload = self._project_manager.build_autosave_payload(
                self._cues,
                current_index=self._current_index,
                active_project_path=self._current_project_path,
                settings=settings,
            )
        except Exception as exc:
            logger.warning("[AUTOSAVE] Auto-save payload error: %s", exc, exc_info=True)
            return

        self._autosave_in_progress = True
        worker = _AutosaveWorker(self._project_manager, payload)
        worker.signals.finished.connect(self._on_autosave_finished)
        self._autosave_worker = worker  # keep alive until finished is delivered
        self._autosave_pool.start(worker)

    def _on_autosave_finished(self) -> None:
        """Clear the in-flight flag and flush any autosave that was deferred."""
        self._autosave_worker = None
        self._autosave_in_progress = False
        if self._autosave_retry_pending:
            self._autosave_retry_pending = False
            self._auto_save()

    def _check_crash_recovery(self) -> None:
        if self._cues:
            return
        recovery = self._project_manager.check_crash_recovery()
        if not recovery:
            return

        saved_at = recovery.get("saved_at", "sconosciuto")
        cue_dicts = recovery.get("cues", [])
        cues_count = recovery.get("cues_count", len(cue_dicts))
        last = recovery.get("current_cue_index", -1)
        rec_settings_peek = recovery.get("settings", {})
        was_live = bool(rec_settings_peek.get("live_mode")) if isinstance(rec_settings_peek, dict) else False

        def ref(i: int) -> str:
            name = str(cue_dicts[i].get("name", "")) if 0 <= i < len(cue_dicts) else ""
            return f"#{i + 1} '{name}'"

        nxt = last + 1 if 0 <= last < len(cue_dicts) - 1 else (0 if last < 0 else last)
        text = (
            f"È stata rilevata una sessione precedente interrotta o non salvata!\n\n"
            f"• Data ultimo autosave: {saved_at}\n"
            f"• Cue recuperabili: {cues_count}\n\n"
            f"Vuoi ripristinare il progetto da dove era stato interrotto?"
        )
        if was_live:
            text += "\nLo spettacolo era in corso: si torna nello spettacolo."
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "BlindCue — Ripristino Sessione (Crash Recovery)",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        # The safe default (Enter and a reflex Esc): restore and go on with the
        # next cue. "Again" replays the last one, which suits background music
        # but not a bell. "No" sets the show aside, never deletes it.
        box.button(QMessageBox.StandardButton.Yes).setText(f"Riprendi: prossima {ref(nxt)}")
        btn_again = btn_top = None
        if 0 <= last < len(cue_dicts) and last != nxt:
            btn_again = box.addButton(f"Ripeti l'ultima: {ref(last)}", QMessageBox.ButtonRole.AcceptRole)
        if nxt != 0 and cue_dicts:
            btn_top = box.addButton("Dall'inizio", QMessageBox.ButtonRole.AcceptRole)
        box.button(QMessageBox.StandardButton.No).setText("Apri senza ripristinare")
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setEscapeButton(QMessageBox.StandardButton.Yes)
        box.exec()
        clicked = box.clickedButton()
        reply = box.standardButton(clicked)
        start_row = nxt
        if clicked is not None and clicked is btn_again:
            reply, start_row = QMessageBox.StandardButton.Yes, last
        elif clicked is not None and clicked is btn_top:
            reply, start_row = QMessageBox.StandardButton.Yes, 0

        if reply == QMessageBox.StandardButton.Yes:
            self._cues.clear()
            for item in recovery.get("cues", []):
                try:
                    cue = Cue.from_dict(item)
                    if not cue.media_type.has_file:
                        cue.status = CueStatus.LOADED
                    else:
                        cue.status = CueStatus.LOADED if os.path.isfile(cue.file_path) else CueStatus.OFFLINE
                    self._cues.append(cue)
                except Exception as exc:
                    logger.warning("[RECOVERY] Error recovering cue: %s", exc)
            self._current_index = recovery.get("current_cue_index", -1)
            self._live_resume_id = None
            self._played_ids.clear()
            self._released_groups.clear()  # cue ids repeat between shows
            self._checklist_ticks = {}
            self._current_project_path = recovery.get("active_project_path")
            self._project_bundled = bool(self._current_project_path) and \
                self._project_manager.uses_media_archive(self._current_project_path, self._cues)

            rec_settings = recovery.get("settings", {})
            lay0 = rec_settings.get("layer0_image") if isinstance(rec_settings, dict) else None
            if lay0 and os.path.isfile(lay0):
                self.set_layer0_image(lay0)
            else:
                self._on_reset_layer0()
            surfaces_raw = rec_settings.get("surfaces") if isinstance(rec_settings, dict) else None
            if surfaces_raw:
                try:
                    self._surfaces = [SurfaceDefinition.from_dict(d) for d in surfaces_raw]
                except Exception as exc:
                    logger.warning("[RECOVERY] Error restoring surfaces: %s", exc)
                    self._surfaces = [create_default_surface()]
            else:
                self._surfaces = [create_default_surface()]
            self._output.set_surfaces(self._surfaces)
            if getattr(self, "_output_b", None) is not None:
                self._output_b.set_surfaces(self._surfaces)
            self._inspector.set_available_surfaces(self._surfaces)
            self._apply_output_settings(rec_settings)

            self._refresh_cue_list(keep_selection=False)
            if 0 <= start_row < len(self._cues):
                self._cue_list.setCurrentRow(start_row)  # the GO starts where the operator chose
            elif self._cues:
                self._cue_list.setCurrentRow(0)
            self._reset_undo_history()
            self._mark_modified(True)
            self._status_label.setText(f"Sessione ripristinata con successo ({len(self._cues)} cue)")
            logger.info("[RECOVERY] Restored %d cues from autosave, GO on row %d", len(self._cues), start_row)
            if was_live and self._cues:
                # Back into the show at the chosen cue (no second start question).
                self._live_resume_id = self._cues[self._go_target_index()].cue_id
                self.set_live_mode(True)
        else:
            kept = self._project_manager.discard_autosave()
            if kept is not None:
                self._status_label.setText(f"Sessione precedente messa da parte: {kept}")
            logger.info("[RECOVERY] User discarded autosave recovery (kept as %s)", kept)

    def _confirm_save_if_modified(self, title: str, message: str) -> bool:
        """Prompt user to save dirty state; returns True to continue action or False to abort."""
        if not (self._is_modified and self._cues):
            return True
        ret = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if ret == QMessageBox.StandardButton.Save:
            return self._on_save_show()
        return ret != QMessageBox.StandardButton.Cancel

    @Slot()
    def _on_new_show(self) -> None:
        if not self._confirm_save_if_modified(
            "Nuovo Show",
            "Ci sono modifiche non salvate nel progetto corrente.\nVuoi salvarle prima di creare un nuovo show?",
        ):
            return

        if any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags):
            self._on_panic()

        self._cues.clear()
        self._current_index = -1
        self._live_resume_id = None
        self._played_ids.clear()
        self._released_groups.clear()  # cue ids repeat between shows
        self._checklist_ticks = {}
        self._current_project_path = None
        self._project_bundled = False
        self._surfaces = [create_default_surface()]
        self._output.set_surfaces(self._surfaces)
        if getattr(self, "_output_b", None) is not None:
            self._output_b.set_surfaces(self._surfaces)
        self._inspector.set_available_surfaces(self._surfaces)
        self._on_reset_layer0()
        self._refresh_cue_list()
        self._reset_idle_preview_ui()
        self._update_inspector(None)
        self._reset_undo_history()
        self._mark_modified(False)
        self._status_label.setText("Nuovo show creato")
        self._auto_save()

    @Slot()
    def _on_open_show(self) -> None:
        if not self._confirm_save_if_modified(
            "Apri Show",
            "Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?",
        ):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Apri Show BlindCue",
            "",
            "BlindCue Show (*.blindcue *.json);;Tutti i file (*)",
        )
        if not file_path:
            return
        self._open_project_file(file_path)

    # ── Recent projects ───────────────────────────────────────────────

    @staticmethod
    def _settings() -> QSettings:
        """Return the application QSettings store (overridable in tests)."""
        return QSettings("BlindCue", "BlindCue")

    def _recent_projects(self) -> list[str]:
        """Return the recent-project paths, most recent first (never raises)."""
        try:
            raw = self._settings().value(
                self._RECENT_PROJECTS_KEY, [], type=list
            )
        except Exception as exc:  # a broken settings backend must not block the UI
            logger.warning("[PROJECT] Cannot read recent projects: %s", exc)
            return []
        paths = [str(p) for p in (raw or []) if isinstance(p, str) and p.strip()]
        return paths[: self._RECENT_PROJECTS_LIMIT]

    @staticmethod
    def _recent_key(file_path: str) -> str:
        """Normalise a path the way it is stored in the recent list."""
        return str(Path(file_path).expanduser())

    def _remember_recent_project(self, file_path: str) -> None:
        """Move *file_path* to the top of the recent list and persist it."""
        try:
            path = self._recent_key(file_path)
        except Exception:
            return
        if not path:
            return
        recent = [p for p in self._recent_projects() if p != path]
        recent.insert(0, path)
        recent = recent[: self._RECENT_PROJECTS_LIMIT]
        try:
            self._settings().setValue(self._RECENT_PROJECTS_KEY, recent)
        except Exception as exc:
            logger.warning("[PROJECT] Cannot store recent projects: %s", exc)

    def _forget_recent_project(self, file_path: str) -> None:
        """Drop one entry (used when the file disappeared from disk)."""
        try:
            gone = {str(file_path), self._recent_key(file_path)}
        except Exception:
            gone = {str(file_path)}
        recent = [p for p in self._recent_projects() if p not in gone]
        try:
            self._settings().setValue(self._RECENT_PROJECTS_KEY, recent)
        except Exception as exc:
            logger.warning("[PROJECT] Cannot update recent projects: %s", exc)

    def _clear_recent_projects(self) -> None:
        """Empty the recent list."""
        try:
            self._settings().remove(self._RECENT_PROJECTS_KEY)
        except Exception as exc:
            logger.warning("[PROJECT] Cannot clear recent projects: %s", exc)

    def _open_recent_project(self, file_path: str) -> None:
        """Open a project chosen from the recent list, guarding a missing file."""
        if not os.path.isfile(file_path):
            self._forget_recent_project(file_path)
            QMessageBox.warning(
                self,
                "Progetto non trovato",
                f"Il file non esiste più e verrà rimosso dall'elenco recenti:\n{file_path}",
            )
            return
        if not self._confirm_save_if_modified(
            "Apri Show",
            "Ci sono modifiche non salvate.\nVuoi salvare prima di aprire un altro show?",
        ):
            return
        self._open_project_file(file_path)

    def _open_project_file(self, file_path: str) -> None:
        """Load *file_path* into the window, restoring every project setting."""
        try:
            cues, current_idx, settings = self._project_manager.load_project(file_path)
            if any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags):
                self._on_panic()
            self._cues = cues
            self._current_index = current_idx
            self._live_resume_id = None
            self._played_ids.clear()
            self._released_groups.clear()  # cue ids repeat between shows
            self._checklist_ticks = {}
            self._current_project_path = file_path
            # A show saved as a portable bundle must stay one on the next Ctrl+S.
            self._project_bundled = self._project_manager.uses_media_archive(file_path, cues)

            layer0 = settings.get("layer0_image") if isinstance(settings, dict) else None
            if layer0 and os.path.isfile(layer0):
                self.set_layer0_image(layer0)
            else:
                self._on_reset_layer0()

            surfaces_raw = settings.get("surfaces") if isinstance(settings, dict) else None
            if surfaces_raw:
                self._surfaces = [SurfaceDefinition.from_dict(d) for d in surfaces_raw]
            else:
                self._surfaces = [create_default_surface()]
            self._output.set_surfaces(self._surfaces)
            if getattr(self, "_output_b", None) is not None:
                self._output_b.set_surfaces(self._surfaces)
            self._inspector.set_available_surfaces(self._surfaces)
            self._apply_output_settings(settings)

            self._refresh_cue_list(keep_selection=False)
            if 0 <= self._current_index < len(self._cues):
                self._cue_list.setCurrentRow(self._current_index)
            elif self._cues:
                self._cue_list.setCurrentRow(0)
            self._reset_undo_history()
            self._mark_modified(False)
            self._remember_recent_project(file_path)
            self._status_label.setText(f"Caricato: {Path(file_path).name} ({len(cues)} cue)")
            missing = [
                c.name for c in cues
                if c.media_type != MediaType.GROUP
                and c.file_path
                and not os.path.isfile(c.file_path)
            ]
            if missing:
                shown = "\n".join(f"• {name}" for name in missing[:10])
                more = f"\n… e altre {len(missing) - 10} cue" if len(missing) > 10 else ""
                QMessageBox.warning(
                    self,
                    "File media mancanti",
                    f"{len(missing)} cue puntano a file che non esistono più "
                    "(verranno mostrate come OFFLINE):\n\n"
                    f"{shown}{more}\n\n"
                    "Ricollega i file dalla Cue Inspector prima dello spettacolo.",
                )
            self._auto_save()
        except Exception as exc:
            logger.error("[PROJECT] Error loading %s: %s", file_path, exc, exc_info=True)
            QMessageBox.critical(self, "Errore di Caricamento", f"Impossibile aprire il file:\n{exc}")

    @Slot()
    def _on_save_show(self) -> bool:
        if not self._current_project_path:
            return self._on_save_as_show()
        return self._do_save(self._current_project_path)

    @Slot()
    def _on_save_as_show(self) -> bool:
        suggested = self._current_project_path or "my_show.blindcue"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva Show Con Nome",
            suggested,
            "BlindCue Show (*.blindcue);;JSON File (*.json)",
        )
        if not file_path:
            return False
        if not file_path.endswith((".blindcue", ".json")):
            file_path += ".blindcue"
        self._project_bundled = self._ask_bundle_media()
        self._current_project_path = file_path
        return self._do_save(file_path)

    def _ask_bundle_media(self) -> bool:
        """Ask whether the media files should be copied beside the project."""
        answer = QMessageBox.question(
            self,
            "Salvataggio show",
            "Vuoi copiare i file audio/video dentro la cartella dello show?\n\n"
            "Sì: archivio portatile, lo show si apre anche su un altro PC.\n"
            "No: salva solo i collegamenti ai file originali (nessuna copia).\n\n"
            "In entrambi i casi i file originali non vengono mai modificati.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _do_save(self, file_path: str) -> bool:
        self._apply_inspector_to_cue()
        settings = {"layer0_image": self._layer0_image} if self._layer0_image else {}
        settings["surfaces"] = [s.to_dict() for s in self._surfaces]
        output = self._output_settings()
        if output:
            settings["output"] = output
        problems: list[str] = []
        copied = 0
        if getattr(self, "_project_bundled", False):
            success, problems, copied = self._project_manager.save_project_bundled(
                file_path,
                self._cues,
                current_index=self._current_index,
                settings=settings,
                surfaces=self._surfaces,
            )
        else:
            success = self._project_manager.save_project(
                file_path,
                self._cues,
                current_index=self._current_index,
                settings=settings,
                surfaces=self._surfaces,
            )
        if success:
            self._mark_modified(False)
            self._remember_recent_project(file_path)
            if copied:
                self._status_label.setText(
                    f"Salvato {Path(file_path).name} con {copied} file media copiati"
                )
            else:
                self._status_label.setText(f"Salvato con successo: {Path(file_path).name}")
            if problems:
                shown = "\n".join(problems[:10])
                more = f"\n… e altri {len(problems) - 10}" if len(problems) > 10 else ""
                QMessageBox.warning(
                    self,
                    "File media non copiati",
                    "Lo show è stato salvato, ma questi file non sono stati "
                    "copiati (restano collegati al percorso originale):\n\n"
                    f"{shown}{more}",
                )
            self._auto_save()
            return True
        QMessageBox.critical(self, "Errore Salvataggio", f"Impossibile salvare il file in:\n{file_path}")
        return False

    @Slot()
    def _on_quit(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Ask to save unsaved changes before the main window closes.

        During a show (LIVE, or something plays or waits) Alt+F4 or a stray
        click on × asks first, with "stay" as the safe default.
        """
        if not self._force_closing and (self._live_mode or self._show_running()):
            box = QMessageBox(
                QMessageBox.Icon.Warning,
                "Chiusura BlindCue",
                "Lo spettacolo è in corso.\nChiudere il programma ferma tutto ciò che è in onda.",
                QMessageBox.StandardButton.NoButton,
                self,
            )
            stay = box.addButton("Resta nel programma", QMessageBox.ButtonRole.RejectRole)
            box.addButton("Chiudi il programma", QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(stay)
            box.setEscapeButton(stay)
            box.exec()
            if box.clickedButton() is stay:
                event.ignore()
                return
        if not self._force_closing and self._is_modified and self._cues:
            ret = QMessageBox.question(
                self,
                "Chiusura BlindCue",
                "Ci sono modifiche non salvate nel progetto.\nVuoi salvare prima di uscire?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                if not self._on_save_show():
                    event.ignore()
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        # Stop the periodic autosave and wait for any in-flight background write
        # to finish, so a late worker cannot overwrite the clean-exit marker and
        # trigger a spurious crash-recovery prompt on the next launch.
        self._autosave_timer.stop()
        if self._autosave_pool is not None:
            self._autosave_pool.waitForDone(5000)
        self._project_manager.mark_clean_exit()
        self._output.force_close()
        if getattr(self, "_output_b", None) is not None:
            self._output_b.force_close()
        event.accept()
