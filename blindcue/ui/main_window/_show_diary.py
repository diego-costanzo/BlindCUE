"""The show diary, "why changed?" and saved versions (stage 5, item 5.6) mixin for MainWindow.

- Show → "Show diary…": a window (it does not block the show) with what has
  happened so far in this show, with the time - every GO, automatic start,
  PANIC, Fade All, pause... from the run log (2.5 / 5.19) - and a line where
  the operator writes a note ("mic 2 crackled"); the notes go into the run
  log, so the report after the show (5.19) lists them too.
- File → "Why is the show marked as changed?": every difference between the
  show as it was saved (or opened) and the show now (``engine.show_diff``).
- File → "Restore a saved version…" (5.11): the saved file, each backup
  copy, a session set aside after a crash - with the differences from the
  show now - put back as one Ctrl+Z.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from i18n import tr
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QSplitter,
)

from ui.main_window._common import *  # noqa: F403,F401,F405

_SETTING_WORDS = {"versions": "versioni dello spettacolo", "version": "versione scelta",
                  "info": "informazioni sullo spettacolo", "layer0_kind": "Layer 0", "layer0_image": "Layer 0",
                  "layer0_video": "Layer 0", "surfaces": "superfici di proiezione"}


def diff_text(change) -> str:
    """One difference (``engine.show_diff``) in words."""
    from ui.main_window._history import change_text

    if change.kind == "setting":
        word = tr(_SETTING_WORDS.get(change.field, change.field))
        return tr("Impostazioni dello spettacolo: {}").format(word)
    return change_text(change)


def _event_words() -> dict[str, str]:
    from engine import run_report as rr

    return {rr.GO: tr("GO"), rr.AUTO: tr("automatico"), rr.PANIC: tr("PANIC"), rr.FADE_ALL: tr("Sfuma tutto"),
            rr.PAUSE: tr("Pausa tutto"), rr.RESUME: tr("Riprendi"), rr.BLACKOUT: tr("Blackout"),
            rr.UNDO_GO: tr("Annulla l'ultimo GO"), rr.EFFECT: tr("Effetto"), rr.FADE_SCENE: tr("Sfuma la scena"),
            rr.END: tr("Fine dello spettacolo"), rr.NOTE: tr("📝 Annotazione")}


class _DiaryWindow(QDialog):
    """Non-modal: the show goes on while it is open (Esc twice is still PANIC)."""

    def __init__(self, window) -> None:
        super().__init__(window)
        from ui.main_window._cue_table import _EmergencyKeysInDialog

        self._win = window
        self._shown = -1
        self.setWindowTitle(tr("Diario dello spettacolo"))
        self.setModal(False)
        self.resize(560, 480)
        lay = QVBoxLayout(self)
        self.lbl_state = QLabel()
        self.lbl_state.setWordWrap(True)
        lay.addWidget(self.lbl_state)
        self.listing = QListWidget()
        self.listing.setObjectName("diary_entries")
        lay.addWidget(self.listing, 1)
        row = QHBoxLayout()
        self.edit_note = QLineEdit()
        self.edit_note.setPlaceholderText(tr("Annotazione (per esempio: il microfono 2 gracchia)"))
        self.edit_note.setMaxLength(300)
        self.edit_note.returnPressed.connect(self._add)
        self.btn_add = QPushButton(tr("📝 Annota"))
        self.btn_add.clicked.connect(self._add)
        row.addWidget(self.edit_note, 1)
        row.addWidget(self.btn_add)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        lay.addWidget(buttons)
        keys = _EmergencyKeysInDialog(window, self)
        self.installEventFilter(keys)
        self.edit_note.installEventFilter(keys)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _add(self) -> None:
        text = self.edit_note.text().strip()
        if text and self._win.diary_note(text):
            self.edit_note.clear()
            # The keyboard back to the show: Space / the remote must give GO again at once.
            self._win.activateWindow()
            self._win.raise_()
        self.refresh()

    def refresh(self) -> None:
        from engine.run_report import mmss
        from engine.show_mode import SHOW

        win = self._win
        in_show = win._current_mode() == SHOW
        self.edit_note.setEnabled(in_show)
        self.btn_add.setEnabled(in_show)
        log = list(getattr(win, "_run_log", []))
        started = getattr(win, "_run_started", None)
        if in_show:
            self.lbl_state.setText(tr("Spettacolo in corso: ogni GO, PANIC, pausa… si scrive qui con l'ora. "
                                      "Le annotazioni vanno anche nel rapporto dopo lo spettacolo."))
        else:
            self.lbl_state.setText(tr("Il diario scrive solo durante lo spettacolo (non nella prova e nella "
                                      "preparazione). Il rapporto dell'ultimo spettacolo: File → Esporta e stampa."))
        if len(log) == self._shown:
            return
        rows = {c.cue_id: i for i, c in enumerate(win._cues)}
        words = _event_words()
        self.listing.clear()
        for secs, cue_id, name, _hand, event in log:
            clock = (started + timedelta(seconds=secs)).strftime("%H:%M:%S") if started else ""
            number = f"#{rows[cue_id] + 1} " if cue_id in rows else ""
            self.listing.addItem(f"{mmss(secs)}  {clock}  {words.get(event, event)}  {number}{name}".rstrip())
        if not log:
            self.listing.addItem(tr("Ancora niente in questo spettacolo"))
        self.listing.scrollToBottom()
        self._shown = len(log)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()  # closed (also by Esc / Shift+Esc): nothing to refresh
        super().hideEvent(event)


class _ShowDiaryMixin:
    # ── the diary ──
    def _open_show_diary(self) -> None:
        dlg = getattr(self, "_diary_window", None)
        if dlg is None:
            dlg = self._diary_window = _DiaryWindow(self)
        dlg._timer.start()
        dlg.refresh()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def diary_note(self, text: str) -> bool:
        """A note of the operator, with the time, in the run log (only in the show)."""
        from engine import run_report as rr
        from engine.show_mode import SHOW

        if self._current_mode() != SHOW or not text.strip():
            return False
        self._run_event(rr.NOTE, text.strip()[:300])
        self._status_label.setText(tr("Annotazione scritta nel diario"))
        return True

    # ── why changed ──
    def _document_settings(self) -> dict:
        """What the show file keeps besides the cues (the computer's own output setting left out)."""
        settings = dict(self._layer0_settings()) if hasattr(self, "_layer0_settings") else {}
        settings["surfaces"] = [s.to_dict() for s in getattr(self, "_surfaces", [])]
        settings.update(self._versions_settings() if hasattr(self, "_versions") else {})
        settings.update(self._show_info_settings())
        return settings

    def _remember_saved_state(self) -> None:
        try:
            self._saved_state = ([c.to_dict() for c in self._cues], self._document_settings())
        except Exception as exc:  # noqa: BLE001 - never in the way of a save
            logger.warning("[WHY CHANGED] cannot remember the saved state: %s", exc)
            self._saved_state = None

    def _changes_since_save(self) -> list:
        from engine.show_diff import differences

        self._apply_inspector_to_cue()
        saved = getattr(self, "_saved_state", None)
        if saved is None:  # never saved nor opened since the program started: an empty show
            saved = ([], self._document_settings())
        return differences(saved[0], [c.to_dict() for c in self._cues], saved[1], self._document_settings())

    def _why_modified(self) -> None:
        changes = self._changes_since_save()
        title = tr("Perché lo spettacolo risulta modificato?")
        if not self._is_modified and not changes:
            QMessageBox.information(self, title, tr("Lo spettacolo non ha modifiche da salvare."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(600, 440)
        lay = QVBoxLayout(dlg)
        saved = getattr(self, "_current_project_path", None)
        intro = tr("Differenze dall'ultimo salvataggio ({}):").format(len(changes)) if saved else \
            tr("Lo spettacolo non è mai stato salvato. Differenze da quando è stato creato ({}):").format(len(changes))
        lay.addWidget(QLabel(intro))
        listing = QListWidget()
        listing.setObjectName("why_changed")
        for change in changes[:500]:
            listing.addItem(diff_text(change))
        if len(changes) > 500:
            listing.addItem(tr("… e altre {}").format(len(changes) - 500))
        if not changes:
            listing.addItem(tr("Nessuna differenza nella lista: era cambiato qualcosa ed è tornato com'era. "
                               "Salva per togliere l'asterisco."))
        lay.addWidget(listing, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_save = buttons.addButton(tr("💾 Salva ora"), QDialogButtonBox.ButtonRole.AcceptRole)
        btn_save.setEnabled(self._current_mode() == "preparation")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._on_save_show()

    # ── saved versions (5.11) ──
    def _saved_versions(self) -> list[tuple[str, str, Path]]:
        """(kind, label, file): "file" = the show as saved, "backup", "aside" = a session set aside."""
        from models.project_manager import backups_of

        path = getattr(self, "_current_project_path", None)
        out: list[tuple[str, str, Path]] = []
        if path and Path(path).is_file():
            stamp = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            out.append(("file", tr("Ultimo salvataggio ({})").format(stamp), Path(path)))
        if path:
            stem = Path(path).stem
            for copy in backups_of(path):
                when = copy.stem[len(stem) + 1:] if copy.stem.startswith(stem + " ") else copy.stem
                out.append(("backup", tr("Copia di sicurezza del {}").format(when), copy))
        aside = self._project_manager.autosave_file.with_name("autosave.discarded.json")
        if aside.is_file():
            try:
                data = json.loads(aside.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            data = data if isinstance(data, dict) else {}
            other = data.get("active_project_path")
            same = (not path and not other) or (path and other and os.path.normcase(os.path.abspath(other))
                                                == os.path.normcase(os.path.abspath(path)))
            if same and isinstance(data.get("cues"), list):
                out.append(("aside", tr("Sessione messa da parte ({})").format(
                    str(data.get("saved_at", ""))[:19].replace("T", " ")), aside))
        return out

    def _load_saved_version(self, kind: str, file: Path) -> tuple[list[Cue], dict]:
        if kind == "aside":
            data = json.loads(file.read_text(encoding="utf-8"))
            cues = []
            for item in data.get("cues", []):
                try:
                    cue = Cue.from_dict(item)
                except Exception as exc:  # noqa: BLE001 - one damaged cue never stops the rest
                    logger.warning("[VERSIONS] skipped a cue: %s", exc)
                    continue
                cue.status = CueStatus.LOADED if not cue.media_type.has_file or os.path.isfile(cue.file_path) \
                    else CueStatus.OFFLINE
                cues.append(cue)
            settings = data.get("settings", {})
            return cues, settings if isinstance(settings, dict) else {}
        cues, _index, settings = ProjectManager().load_project(file, as_path=getattr(self, "_current_project_path", None)
                                                               or file)
        return cues, settings

    def _choose_saved_version(self, versions: list[tuple[str, str, Path]]) -> int | None:
        """The window: the versions on the left, what each would change on the right."""
        from engine.show_diff import differences

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Ripristina una versione salvata"))
        dlg.resize(780, 480)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("Scegli una versione: a destra che cosa cambierebbe nella scaletta di adesso. "
                                "Il ripristino si annulla con Ctrl+Z.")))
        split = QSplitter(Qt.Orientation.Horizontal)
        listing = QListWidget()
        listing.setObjectName("saved_versions")
        for _kind, label, _file in versions:
            listing.addItem(label)
        details = QListWidget()
        details.setObjectName("version_changes")
        details.setWordWrap(True)
        split.addWidget(listing)
        split.addWidget(details)
        split.setSizes([280, 500])
        lay.addWidget(split, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btn = buttons.addButton(tr("🕘 Ripristina questa versione"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        now = [c.to_dict() for c in self._cues]
        # Only what a restore puts back is compared (versions and the show info, not Layer 0 / surfaces).
        restored_keys = ("versions", "version", "info")
        now_settings = {k: v for k, v in self._document_settings().items() if k in restored_keys}

        def show(row: int) -> None:
            details.clear()
            btn.setEnabled(0 <= row < len(versions))
            if not 0 <= row < len(versions):
                return
            kind, _label, file = versions[row]
            try:
                cues, settings = self._load_saved_version(kind, file)
            except (OSError, ValueError) as exc:
                details.addItem(str(exc))
                btn.setEnabled(False)
                return
            changes = differences(now, [c.to_dict() for c in cues], now_settings,
                                  {k: v for k, v in settings.items() if k in restored_keys})
            details.addItem(tr("{} cue in questa versione").format(len(cues)))
            if not changes:
                details.addItem(tr("Uguale alla scaletta di adesso"))
            for change in changes[:200]:
                details.addItem("• " + diff_text(change))
            if len(changes) > 200:
                details.addItem(tr("… e altre {}").format(len(changes) - 200))

        listing.currentRowChanged.connect(show)
        listing.itemDoubleClicked.connect(lambda _item: dlg.accept())
        listing.setCurrentRow(0)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        row = listing.currentRow()
        return row if 0 <= row < len(versions) else None

    def _restore_saved_version(self) -> None:
        """File → "Restore a saved version…": one Ctrl+Z takes it back."""
        if not self._change_allowed(EDIT_LIST):
            return
        title = tr("Ripristina una versione salvata")
        versions = self._saved_versions()
        if not versions:
            QMessageBox.information(self, title, tr(
                "Ancora nessuna versione salvata: il programma tiene il file salvato e una copia a ogni "
                "salvataggio."))
            return
        row = self._choose_saved_version(versions)
        if row is None:
            return
        kind, label, file = versions[row]
        try:
            cues, settings = self._load_saved_version(kind, file)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        self._apply_inspector_to_cue()
        if self._undo.is_debounce_active():
            self._commit_undo_point()
        live_ids = {c.cue_id for c in self._cues if c.status == CueStatus.LIVE}
        for cue in cues:
            if cue.cue_id in live_ids:
                cue.status = CueStatus.LIVE  # what plays (a preview) keeps playing, as after Ctrl+Z
        self._cues = cues
        self._versions_load(settings)
        self._show_info_load(settings)
        self._refresh_cue_list(keep_selection=False)
        self._commit_undo_point()
        self._mark_modified(True)
        self._last_selection_sig = None
        self._sync_selection_state()
        self._auto_save()
        self._status_label.setText(tr("Ripristinata: {} (Ctrl+Z torna indietro)").format(label))
