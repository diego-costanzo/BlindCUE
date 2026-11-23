"""Screen-reader announcements (accessibility review W17, W18) mixin for MainWindow.

One function sends what the status line says to Narrator / NVDA: a GO
politely; a blocked GO, an action not allowed in this mode, the first Esc, a
change of mode, Undo GO and mute assertively. No flooding: one announcement
per 0.5 s at most, a newer one replaces one still waiting, and the 10 Hz
clock never announces anything.
"""

from __future__ import annotations

import time

from ui.main_window._common import *  # noqa: F403,F401,F405

ANNOUNCE_GAP_SECONDS = 0.5


class _AnnounceMixin:
    def announce(self, text: str, assertive: bool = False) -> None:
        """Say *text* through the screen reader (throttled, the newest wins)."""
        text = (text or "").strip()
        if not text:
            return
        pending = getattr(self, "_announce_pending", None)
        if pending is not None and pending[1] and not assertive:
            return  # an urgent message still waits: a polite one does not replace it
        self._announce_pending = (text, assertive)
        wait = ANNOUNCE_GAP_SECONDS - (time.monotonic() - getattr(self, "_announce_last", 0.0))
        if wait <= 0:
            self._announce_now()
        elif not getattr(self, "_announce_timer_armed", False):
            self._announce_timer_armed = True
            QTimer.singleShot(int(wait * 1000) + 1, self._announce_now)

    def _announce_now(self) -> None:
        self._announce_timer_armed = False
        pending = getattr(self, "_announce_pending", None)
        if pending is None:
            return
        self._announce_pending = None
        self._announce_last = time.monotonic()
        text, assertive = pending
        self._announced = getattr(self, "_announced", [])[-19:] + [(text, assertive)]  # for tests
        try:
            from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent

            event = QAccessibleAnnouncementEvent(self, text)
            event.setPoliteness(QAccessible.AnnouncementPoliteness.Assertive if assertive
                                else QAccessible.AnnouncementPoliteness.Polite)
            QAccessible.updateAccessibility(event)
        except Exception as exc:  # noqa: BLE001 - an old Qt or no accessibility: silently nothing
            logger.debug("[A11Y] announcement not sent: %s", exc)
