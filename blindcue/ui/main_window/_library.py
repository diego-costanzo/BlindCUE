"""Template, sound library and cue library (stage 5, item 5.9) mixin for MainWindow.

- File → "New show: school show": the template of ``engine.show_templates``;
  the cues that wait for a file (music, the school's logo) are OFFLINE until
  "Choose a file…" (right click) attaches one.
- Edit → "Sound library": the sounds of a folder (bells, effects of the
  school) as a menu; a click adds a sound cue after the selection. The
  folder is per computer (QSettings ``library/sounds_dir``) and may be a USB
  stick or a shared drive; at first Documents\\BlindCue\\<Sound library>
  with the program's bell in it.
- Edit → "Cue library": the selected cues (a scene with its cues) saved under
  a name with their media (``library/cues_dir``), inserted into any show
  later like an import from another show - one Ctrl+Z.
"""

from __future__ import annotations

import shutil

from i18n import tr
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog

from ui.main_window._common import *  # noqa: F403,F401,F405

SOUNDS_KEY = "library/sounds_dir"
CUES_KEY = "library/cues_dir"
# The program's own sounds put into a new sound library (the copy is never overwritten).
SEED_SOUNDS = (("bell.mp3", "Campanella"), ("storm.mp3", "Temporale"))


class _LibraryMixin:
    # ── folders ──
    def _library_dir(self, key: str, default_name: str) -> Path:
        from ui import dialog_dirs

        stored = str(QSettings("BlindCue", "BlindCue").value(key, "") or "")
        if stored and Path(stored).is_dir():
            return Path(stored)
        folder = Path(dialog_dirs.show_dir()) / tr(default_name)
        fresh = not folder.exists()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("[LIBRARY] cannot make %s: %s", folder, exc)
            return folder
        QSettings("BlindCue", "BlindCue").setValue(key, str(folder))
        if fresh and key == SOUNDS_KEY:
            self._seed_sound_library(folder)
        return folder

    @staticmethod
    def _seed_sound_library(folder: Path) -> None:
        from ui.theme import ASSETS_DIR

        for source, name in SEED_SOUNDS:
            target = folder / f"{tr(name)}{Path(source).suffix}"
            try:
                if not target.exists() and (ASSETS_DIR / "practice" / source).is_file():
                    shutil.copy2(ASSETS_DIR / "practice" / source, target)
            except OSError as exc:
                logger.warning("[LIBRARY] cannot copy %s: %s", source, exc)

    def _sounds_dir(self) -> Path:
        return self._library_dir(SOUNDS_KEY, "Biblioteca suoni")

    def _cues_dir(self) -> Path:
        return self._library_dir(CUES_KEY, "Biblioteca cue")

    def _choose_library_dir(self, key: str) -> None:
        current = self._sounds_dir() if key == SOUNDS_KEY else self._cues_dir()
        folder = QFileDialog.getExistingDirectory(self, tr("Cartella della biblioteca"), str(current))
        if folder:
            QSettings("BlindCue", "BlindCue").setValue(key, folder)
            self._status_label.setText(tr("Biblioteca: {}").format(folder))

    @staticmethod
    def _open_folder(folder: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ── menus ──
    def _build_library_menus(self, parent_menu) -> None:
        """Edit menu: the two libraries, rebuilt each time they open (the folders may change)."""
        self._sound_menu = parent_menu.addMenu("🔔 Biblioteca suoni")
        self._sound_menu.aboutToShow.connect(self._rebuild_sound_menu)
        self._snippet_menu = parent_menu.addMenu("📚 Biblioteca cue")
        self._snippet_menu.aboutToShow.connect(self._rebuild_snippet_menu)

    def _rebuild_sound_menu(self) -> None:
        from engine.show_templates import library_sounds

        menu = self._sound_menu
        menu.clear()
        folder = self._sounds_dir()
        groups = library_sounds(folder)
        for group, files in groups:
            target = menu if not group else menu.addMenu(f"📁 {group}")
            for path in files:
                act = target.addAction(f"🔔 {path.stem}")
                act.setToolTip(str(path))
                act.triggered.connect(lambda _=False, p=str(path): self._add_library_sound(p))
        if not groups:
            empty = menu.addAction(tr("(vuota: metti i suoni nella cartella)"))
            empty.setEnabled(False)
        menu.addSeparator()
        menu.addAction(tr("📂 Apri la cartella della biblioteca"), lambda: self._open_folder(folder))
        menu.addAction(tr("📁 Usa un'altra cartella (chiavetta, cartella condivisa)…"),
                       lambda: self._choose_library_dir(SOUNDS_KEY))

    def _rebuild_snippet_menu(self) -> None:
        from engine.show_templates import library_snippets

        menu = self._snippet_menu
        menu.clear()
        folder = self._cues_dir()
        save = menu.addAction(tr("💾 Salva le cue selezionate nella biblioteca…"))
        save.triggered.connect(self._save_cues_to_library)
        save.setEnabled(bool(self._selected_rows()))
        menu.addSeparator()
        snippets = library_snippets(folder)
        for path in snippets:
            act = menu.addAction(f"➕ {path.stem}")
            act.setToolTip(tr("Inserisci dopo la selezione: {}").format(path))
            act.triggered.connect(lambda _=False, p=str(path): self._insert_library_snippet(p))
        if not snippets:
            empty = menu.addAction(tr("(vuota: seleziona delle cue e salvale qui)"))
            empty.setEnabled(False)
        menu.addSeparator()
        menu.addAction(tr("📂 Apri la cartella della biblioteca"), lambda: self._open_folder(folder))
        menu.addAction(tr("📁 Usa un'altra cartella (chiavetta, cartella condivisa)…"),
                       lambda: self._choose_library_dir(CUES_KEY))

    # ── actions ──
    def _add_library_sound(self, path: str) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        if not os.path.isfile(path):
            self._status_label.setText(tr("File non trovato: {}").format(path))
            return
        self._add_cue_from_file(path, MediaType.AUDIO)

    def _save_cues_to_library(self) -> None:
        from engine.show_templates import SNIPPET_EXT, safe_file_name, with_scene_cues

        rows = self._selected_rows()
        if not rows:
            self._status_label.setText(tr("Seleziona prima le cue da salvare"))
            return
        self._apply_inspector_to_cue()
        cues = []
        chosen = with_scene_cues(self._cues, rows)
        ids = {c.cue_id for c in chosen}
        for cue in chosen:  # copies: a cue taken out of its scene goes in at the top level
            data = cue.to_dict()
            if data.get("parent_id") not in ids:
                data["parent_id"] = None
            cues.append(Cue.from_dict(data))
        first = cues[0].name if cues else ""
        name, ok = QInputDialog.getText(self, tr("Biblioteca cue"), tr("Nome nella biblioteca:"), text=first)
        if not ok or not name.strip():
            return
        target = self._cues_dir() / f"{safe_file_name(name)}{SNIPPET_EXT}"
        if target.exists() and QMessageBox.question(
                self, tr("Biblioteca cue"), tr("'{}' c'è già nella biblioteca. Sostituirlo?").format(target.stem),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        saved, problems, _copied = ProjectManager().save_project_bundled(target, cues, settings={"snippet": True})
        if not saved:
            QMessageBox.warning(self, tr("Biblioteca cue"), tr("Impossibile scrivere il file:\n{}").format(target))
            return
        text = tr("Salvate {} cue nella biblioteca come '{}'").format(len(cues), target.stem)
        if problems:
            text += " · " + tr("file non copiati: {}").format(len(problems))
        self._status_label.setText(text)

    def _insert_library_snippet(self, path: str) -> None:
        if not self._change_allowed(EDIT_LIST):
            return
        try:
            other, _index, _settings = ProjectManager().load_project(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Biblioteca cue"), str(exc))
            return
        if not other:
            self._status_label.setText(tr("Nessuna cue in questo file."))
            return
        ids = {c.cue_id for c in other}  # a cue whose scene is not in the file counts as a top one
        self._insert_imported(other, [c.cue_id for c in other if c.parent_id not in ids], Path(path).stem)

    def _new_show_from_template(self) -> bool:
        """File → "New show: school show"."""
        from engine.show_templates import library_sounds, school_show
        from engine.text_render import render_text_png

        if not self._on_new_show():
            return False
        sounds = [p for _group, files in library_sounds(self._sounds_dir()) for p in files]
        bell_name = tr("Campanella").casefold()
        bell = next((p for p in sounds if p.stem.casefold() == bell_name), None) or \
            next((p for p in sounds if bell_name in p.stem.casefold() or "bell" in p.stem.casefold()), None)
        try:
            cues = school_show(tr, str(bell) if bell else "", render_text_png)
        except OSError as exc:  # a caption image that cannot be written: the template without captions
            logger.warning("[TEMPLATE] captions left out: %s", exc)
            cues = school_show(tr, str(bell) if bell else "", None)
        self._cues = cues
        self._show_info = {"title": tr("Spettacolo scolastico")}
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(0)
        self._reset_undo_history()
        self._mark_modified(True)
        waiting = sum(1 for c in cues if c.status == CueStatus.OFFLINE)
        self._status_label.setText(tr("Modello pronto: {} cue aspettano il loro file (clic destro → Scegli il "
                                      "file…)").format(waiting))
        self._auto_save()
        return True
