"""Help → "Cheat sheet to print" (stage 5, item 5.18) mixin for MainWindow."""

from __future__ import annotations

import tempfile
from datetime import date

from i18n import tr
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ui.main_window._common import *  # noqa: F403,F401,F405


class _CheatSheetMixin:
    def _cheat_sheet_html(self) -> str:
        from engine import key_map as km
        from engine.cheat_sheet import to_html
        from version import APP_NAME, APP_VERSION

        show = [
            (tr("Spazio"), tr("GO – la cue successiva")),
            (tr("Esc due volte (entro 0,6 s)"), tr("PANIC – ferma subito tutto")),
            (tr("Maiusc+Esc"), tr("Sfuma tutto (dolcemente)")),
            (tr("Ctrl+P"), tr("Pausa tutto / riprendi")),
            (tr("Ctrl+B"), tr("Blackout: il tappo sul proiettore")),
            (tr("↑ ↓"), tr("Scegli la prossima cue")),
            (tr("Ctrl+Spazio"), tr("GO forzato (anche se una cue esclusiva sta suonando)")),
            (tr("F5"), tr("Entra nello spettacolo")),
            (tr("Maiusc+F5"), tr("Prova")),
            (tr("Tieni premuto «Preparazione» 1,5 s"), tr("Esci dallo spettacolo")),
        ]
        effects = [(c.hotkey.upper(), c.name) for c in self._cues
                   if getattr(c, "hotkey", "") and getattr(c, "adlib", False)]
        extra = [(" / ".join(keys), tr(km.LABELS.get(func, func)))
                 for func, keys in getattr(self, "_key_map", {}).items() if keys]
        tips = [
            tr("Non si sente niente: guarda il volume in alto (e «Silenzia»), poi l'amplificatore e i cavi; "
               "nella pagina «Prima dello spettacolo» c'è il tono di prova."),
            tr("Sul proiettore non c'è niente o c'è il desktop: Win+P → «Estendi», poi Dispositivi → scegli il "
               "proiettore."),
            tr("Lo Spazio non fa niente: clicca nella finestra del programma (la striscia rossa dice che la "
               "tastiera è altrove)."),
            tr("Suona qualcosa che non deve: «Sfuma» sulla sua scheda, Maiusc+Esc per tutto, Esc due volte "
               "solo in emergenza."),
            tr("Il programma si è chiuso: riaprilo e scegli «Riprendi: la successiva»."),
        ]
        title = f"{APP_NAME} – {tr('promemoria')}"
        name = self._show_title() if hasattr(self, "_show_title") else ""
        footer = " · ".join(x for x in (name, date.today().isoformat(), f"{APP_NAME} {APP_VERSION}") if x)
        return to_html(title, [(tr("Durante lo spettacolo"), show),
                               (tr("Effetti di questo spettacolo"), effects),
                               (tr("Tasti aggiuntivi di questo computer"), extra)],
                       (tr("Se qualcosa non va"), tips), footer,
                       hint=tr("Stampa con Ctrl+P e tienila accanto al portatile."))

    def _open_cheat_sheet(self) -> None:
        target = Path(tempfile.gettempdir()) / "blindcue_cheat_sheet.html"
        try:
            target.write_text(self._cheat_sheet_html(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, tr("Promemoria da stampare"), str(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        self._status_label.setText(tr("Promemoria aperto nel browser: stampalo con Ctrl+P"))
