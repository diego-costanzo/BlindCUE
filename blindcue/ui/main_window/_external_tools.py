"""The cue's file in other programs (stage 5, item 5.15) mixin for MainWindow.

Row menu → "🛠 The file": show it in its folder, open it with the default
program or with one of the favourite programs of this computer. Files handed
over are watched: when the program comes back to the front and a file has
changed, its waveform, length and cached picture are read again.
"""

from __future__ import annotations

import subprocess
import sys

from i18n import tr
from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices

from ui.main_window._common import *  # noqa: F403,F401,F405

TOOLS_KEY = "tools/programs"


class _ExternalToolsMixin:
    def _external_tools_setup(self) -> None:
        self._watched_files: dict[str, float] = {}
        self._cue_list.menu_extender = self._extend_file_menu
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(
                lambda state: self._check_watched_files() if state == Qt.ApplicationState.ApplicationActive else None)

    def _tool_programs(self) -> list[dict[str, str]]:
        from engine.external_tools import parse_programs

        return parse_programs(QSettings("BlindCue", "BlindCue").value(TOOLS_KEY, ""))

    def _extend_file_menu(self, menu, rows: list[int]) -> None:
        if len(rows) != 1 or not (0 <= rows[0] < len(self._cues)):
            return
        path = self._cues[rows[0]].file_path or ""
        if not path or not os.path.isfile(path):
            return
        sub = menu.addMenu(tr("🛠 Il file"))
        sub.addAction(tr("📂 Mostra nella cartella"), lambda: self._show_in_folder(path))
        sub.addAction(tr("✎ Apri con il programma predefinito"), lambda: self._open_external(path, None))
        for prog in self._tool_programs():
            sub.addAction(tr("✎ Apri con {}").format(prog["name"]), lambda p=prog: self._open_external(path, p))
        sub.addSeparator()
        sub.addAction(tr("➕ Aggiungi un programma…"), self._add_tool_program)
        if not self._cues[rows[0]].text_spec:  # 5.10: a caption's picture is the program's own
            sub.addAction(tr("✏ Rinomina il file…"), lambda r=rows[0]: self._rename_media_file(r))

    def _show_in_folder(self, path: str) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])  # noqa: S603,S607 - fixed program
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _open_external(self, path: str, program: dict[str, str] | None) -> None:
        try:
            self._watched_files[path] = os.path.getmtime(path)
        except OSError:
            pass
        if program is None:
            ok = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            who = tr("il programma predefinito")
        else:
            ok = QProcess.startDetached(program["path"], [path])
            ok = ok[0] if isinstance(ok, tuple) else bool(ok)
            who = program["name"]
        if ok:
            self._status_label.setText(tr("'{}' aperto con {}: quando torni qui le modifiche si vedono subito").format(
                os.path.basename(path), who))
        else:
            self._status_label.setText(tr("Impossibile aprire '{}' con {}").format(os.path.basename(path), who))

    def _add_tool_program(self) -> None:
        from engine.external_tools import add_program, to_setting

        start = os.environ.get("ProgramFiles", "") if sys.platform == "win32" else "/usr/bin"
        path, _ = QFileDialog.getOpenFileName(self, tr("Scegli un programma"), start,
                                              tr("Programmi") + " (*.exe);;" + tr("Tutti i file") + " (*)")
        if not path:
            return
        programs = add_program(self._tool_programs(), path)
        QSettings("BlindCue", "BlindCue").setValue(TOOLS_KEY, to_setting(programs))
        self._status_label.setText(tr("Programma aggiunto: {}").format(programs[0]["name"]))

    def _check_watched_files(self) -> list[str]:
        """Files edited in another program: read their waveform, length and picture again."""
        from engine.external_tools import changed_files

        changed = changed_files(getattr(self, "_watched_files", {}))
        for path in changed:
            self._waveform_cache.pop(os.path.abspath(path), None)
            self._known_file_durations.pop(path, None)
            for out in (self._output, getattr(self, "_output_b", None)):
                if out is not None:
                    out._image_pixmap_cache.clear()
            for cue in self._cues:
                if cue.file_path == path and cue.media_type in (MediaType.AUDIO, MediaType.VIDEO):
                    self._request_waveform(cue)
            self._status_label.setText(tr("'{}' è cambiato: forma d'onda e durata aggiornate").format(
                os.path.basename(path)))
        if changed:
            self._last_selection_sig = None
            self._sync_selection_state()
        return changed
