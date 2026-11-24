"""Exit PIN of the show (stage 1 C2a step 10, optional) mixin for MainWindow.

Set per computer (Show menu, only in Preparation; empty = the 1.5 s hold is
enough). With a PIN, every way out of the show (the held tabs, End the
show…) first asks for it in a small field under the top bar – never a modal
window. The field closes by itself after 10 s without typing. A wrong PIN
just says so (no lock-out); after the second one the way out of a forgotten
PIN is named. The PIN never blocks GO, PANIC, Fade All, Pause, the volume or
Undo GO. It protects against an accident and a curious pupil, not against
someone determined.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QInputDialog, QLineEdit

from ui.hold_button import hold_text
from ui.main_window._common import *  # noqa: F403,F401,F405

PIN_SETTINGS_KEY = "live/exit_pin"


class _PinMixin:
    def _pin_setup(self) -> None:
        self._pin_target = ""
        self._pin_errors = 0
        bar = self._live_show_panel.pin_bar
        bar.pin_entered.connect(self._on_pin_entered)
        bar.cancelled.connect(self._on_pin_cancelled)
        bar.go_requested.connect(self._on_go)

    def _exit_pin(self) -> str:
        return str(QSettings("BlindCue", "BlindCue").value(PIN_SETTINGS_KEY, "") or "")

    def _leave_show_to(self, target: str) -> None:
        """Out of the show to "preparation" or "rehearsal" – through the PIN when one is set."""
        if self._current_mode() == "show" and self._exit_pin():
            self._pin_target = target
            self._pin_errors = 0
            self._live_show_panel.pin_bar.ask(
                tr("PIN per uscire dallo spettacolo:"), tr("Invio – esci"))
            self._status_label.setText(tr("Inserisci il PIN per uscire dallo spettacolo (GO e PANIC funzionano)"))
            self.announce(self._status_label.text(), assertive=True)
            return
        self._do_leave_show(target)

    def _do_leave_show(self, target: str) -> None:
        if target == "rehearsal":
            self._switch_show_to_rehearsal()
        else:
            self.set_live_mode(False)

    def _on_pin_entered(self, text: str) -> None:
        if text == self._exit_pin():
            self._live_show_panel.pin_bar.close_bar()
            target, self._pin_target = self._pin_target, ""
            self._do_leave_show(target)
            return
        self._pin_errors += 1
        if self._pin_errors >= 2:
            msg = tr("Hai dimenticato il PIN? Chiudi il programma (File → Esci): lo spettacolo si riapre "
                     "in Preparazione.")
        else:
            msg = tr("PIN sbagliato.")
        self._live_show_panel.pin_bar.feedback(msg)
        self._status_label.setText(msg)
        self.announce(msg, assertive=True)

    def _on_pin_cancelled(self) -> None:
        self._pin_target = ""

    def _set_exit_pin(self) -> None:
        """Show menu → "Exit PIN of the show…" (this computer, Preparation only)."""
        if self._live_mode:
            self._status_label.setText(tr("Il PIN si cambia in Preparazione"))
            return
        text, ok = QInputDialog.getText(
            self, tr("PIN di uscita dallo spettacolo"),
            tr("4 cifre per uscire dallo spettacolo su questo computer (vuoto = basta tenere premuto {}):")
            .format(hold_text()),
            QLineEdit.EchoMode.Password, self._exit_pin())
        if not ok:
            return
        text = text.strip()
        if text and (len(text) != 4 or not text.isdigit()):
            self._status_label.setText(tr("Il PIN deve avere 4 cifre"))
            return
        QSettings("BlindCue", "BlindCue").setValue(PIN_SETTINGS_KEY, text)
        self._status_label.setText(tr("PIN di uscita impostato") if text else tr("PIN di uscita tolto"))

    # ── Hold time of this computer (accessibility W29) ──
    def _build_hold_menu(self, menu) -> None:
        """Show menu → settings → "Hold time": 0.6-3 s for every hold that leaves the show or jumps ±10 s."""
        from ui.hold_button import HOLD_CHOICES, HOLD_DEFAULT_SEC, seconds_text

        sub = menu.addMenu("✋ Tempo per tenere premuto")
        sub.setToolTipsVisible(True)
        self._hold_group = QActionGroup(self)
        self._hold_group.setExclusive(True)
        for seconds in HOLD_CHOICES:
            text = seconds_text(seconds)
            if seconds == HOLD_DEFAULT_SEC:
                text = tr("{} (predefinito)").format(text)
            act = QAction(text, self, checkable=True)
            act.setData(seconds)
            self._hold_group.addAction(act)
            sub.addAction(act)
        sub.aboutToShow.connect(self._sync_hold_menu)
        self._hold_group.triggered.connect(self._on_hold_time_chosen)
        self._sync_hold_menu()

    def _sync_hold_menu(self) -> None:
        from ui.hold_button import hold_seconds

        now = hold_seconds()
        for act in self._hold_group.actions():
            act.setChecked(abs(float(act.data()) - now) < 0.05)

    def _on_hold_time_chosen(self, act) -> None:
        from ui.hold_button import seconds_text, set_hold_seconds

        if self._live_mode:
            self._sync_hold_menu()
            self._status_label.setText(tr("Il tempo per tenere premuto si cambia in Preparazione"))
            return
        value = set_hold_seconds(float(act.data()))
        for tabs in (self._mode_tabs, self._live_show_panel.mode_tabs):
            tabs.refresh_hold_texts()
        self._status_label.setText(tr("Tenere premuto: {} su questo computer").format(seconds_text(value)))
