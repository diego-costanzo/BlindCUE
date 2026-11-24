"""File → "Settings of this computer": save to a file / load from a file (stage 5, item 5.13)."""

from __future__ import annotations

import socket
from datetime import datetime

from i18n import tr
from ui.main_window._common import *  # noqa: F403,F401,F405


class _SettingsTransferMixin:
    def _build_settings_transfer_menu(self, file_menu) -> None:
        menu = file_menu.addMenu("💻 Impostazioni di questo computer")
        menu.addAction(QAction("💾 Salva in un file…", self, triggered=self._export_computer_settings))
        menu.addAction(QAction("📂 Carica da un file…", self, triggered=self._import_computer_settings))

    @staticmethod
    def _settings_now() -> dict:
        from engine.settings_transfer import transferable

        settings = QSettings("BlindCue", "BlindCue")
        return {key: settings.value(key) for key in settings.allKeys() if transferable(key)}

    def _export_computer_settings(self) -> None:
        from engine.settings_transfer import to_json
        from ui import dialog_dirs

        host = socket.gethostname() or "PC"
        suggested = os.path.join(dialog_dirs.show_dir(), f"{tr('Impostazioni')} {host}.json")
        path, _ = QFileDialog.getSaveFileName(self, tr("Salva le impostazioni di questo computer"), suggested,
                                              "JSON (*.json)")
        if not path:
            return
        values = self._settings_now()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(to_json(values, host, datetime.now().isoformat(timespec="seconds")))
        except OSError as exc:
            QMessageBox.warning(self, tr("Impostazioni di questo computer"), str(exc))
            return
        self._status_label.setText(tr("Impostazioni salvate ({} valori): {}").format(len(values), path))

    def _import_computer_settings(self) -> None:
        from engine.settings_transfer import GROUP_LABELS, changes, from_json
        from engine.show_mode import PREPARATION
        from ui import dialog_dirs

        if self._current_mode() != PREPARATION:
            self._status_label.setText(tr("Le impostazioni si caricano nella preparazione, non durante lo spettacolo"))
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Carica le impostazioni di un altro computer"),
                                              dialog_dirs.show_dir(), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                incoming = from_json(fh.read())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Impostazioni di questo computer"),
                                tr("Impossibile caricare il file: {}").format(tr(str(exc))))
            return
        diff = changes(self._settings_now(), incoming)
        if not diff:
            QMessageBox.information(self, tr("Impostazioni di questo computer"),
                                    tr("Il file ha le stesse impostazioni di questo computer."))
            return
        lines = "\n".join(f"• {tr(GROUP_LABELS[g])} ({len(keys)})" for g, keys in diff.items())
        answer = QMessageBox.question(
            self, tr("Impostazioni di questo computer"),
            tr("Cambiare queste impostazioni di questo computer?\n\n{}\n\nAlcune valgono dopo il riavvio del "
               "programma.").format(lines))
        if answer != QMessageBox.StandardButton.Yes:
            return
        settings = QSettings("BlindCue", "BlindCue")
        count = 0
        for keys in diff.values():
            for key in keys:
                settings.setValue(key, incoming[key])
                count += 1
        settings.sync()
        self._status_label.setText(tr("Caricate {} impostazioni: riavvia il programma perché valgano tutte").format(count))
