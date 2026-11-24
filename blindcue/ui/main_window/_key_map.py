"""Extra keys and a presenter remote (stage 5, items 5.7 and 5.8) mixin for MainWindow.

Show → "Keys and presenter remote…" adds keys of this computer to GO, the
previous / next cue, Pause All, Fade All and Undo GO (``engine.key_map``).
They work in the rehearsal and the show only, never while typing, in a menu
or on the "Before the show" page, and an effect of the show that has the
same key wins. Stored per computer (QSettings ``keys/map``).
"""

from __future__ import annotations

from engine import key_map as km
from i18n import tr
from PySide6.QtCore import QEvent, QObject, QSettings

from ui.main_window._common import *  # noqa: F403,F401,F405


def key_name(event) -> str:
    """The plain name of the key of *event* ("PgDown", "B", "."), "" for a modifier alone."""
    key = event.key()
    if key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_unknown, 0):
        return ""
    return QKeySequence(Qt.Key(key)).toString()


class _KeyMapFilter(QObject):
    """Application-wide: the extra keys, only in the rehearsal/show and only when nothing else wants them."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._win = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            return False
        w = self._win
        if not w._live_mode or not w._key_lookup or not w.isActiveWindow():
            return False
        if event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            return False  # Ctrl/Alt/Shift combinations belong to the menus
        name = key_name(event)
        func = w._key_lookup.get(name)
        if func is None or name.upper() in getattr(w, "_hotkey_map", {}):
            return False  # not ours, or an effect of this show has the key
        if QApplication.activePopupWidget() is not None or QApplication.activeModalWidget() is not None:
            return False
        if w._is_text_input_focused() or w._readiness_visible():
            return False
        if kind == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if not event.isAutoRepeat():
            w._run_key_function(func)
        return True


class _KeyMapMixin:
    def _keymap_setup(self) -> None:
        settings = QSettings("BlindCue", "BlindCue")
        self._key_map: dict[str, list[str]] = km.from_text(str(settings.value("keys/map", "") or ""))
        self._space_go = bool(settings.value(km.SPACE_GO_SETTING, True, type=bool))  # 5.7
        self._key_lookup: dict[str, str] = {}
        self._key_filter = _KeyMapFilter(self)
        self._key_filter_installed = False
        self._keymap_apply()

    def _keymap_apply(self) -> None:
        from ui.live_show_view import LiveCueTable

        # 5.7: the program's Space = GO, on or off for this computer (the menu, the show's list, the PIN bar).
        LiveCueTable.space_starts_go = self._space_go
        act = getattr(self, "_act_go", None)
        if act is not None:
            act.setShortcut(QKeySequence("Space") if self._space_go else QKeySequence())
        self._key_lookup = km.lookup(self._key_map)
        app = QApplication.instance()
        if self._key_lookup and not self._key_filter_installed:
            app.installEventFilter(self._key_filter)
            self._key_filter_installed = True
        elif not self._key_lookup and self._key_filter_installed:
            app.removeEventFilter(self._key_filter)
            self._key_filter_installed = False

    def _keymap_store(self, key_map: dict[str, list[str]], space_go: bool | None = None) -> None:
        self._key_map = km.clean(key_map)
        settings = QSettings("BlindCue", "BlindCue")
        settings.setValue("keys/map", km.to_text(self._key_map))
        if space_go is not None:
            self._space_go = bool(space_go)
            settings.setValue(km.SPACE_GO_SETTING, self._space_go)
        self._keymap_apply()

    def _run_key_function(self, func: str) -> None:
        logger.info("[KEYS] %s", func)
        if func == km.GO:
            if self._gate_waiting() >= 0:
                self._confirm_gate()  # like the GO of the phone: the OK of a cue waiting for it (1.9)
            else:
                self._on_go()
        elif func == km.PREV_CUE:
            self._on_remote_prev_cue()
        elif func == km.NEXT_CUE:
            self._on_remote_next_cue()
        elif func == km.PAUSE:
            self.pause_all_toggled.emit()
        elif func == km.FADE_ALL:
            self._on_fade_all()
        elif func == km.UNDO_GO:
            self._on_undo_go()

    def _open_key_map(self) -> None:
        from ui.key_map_dialog import KeyMapDialog

        effects = list(getattr(self, "_hotkey_map", {}).keys()) or [
            (c.hotkey or "").upper() for c in self._cues if getattr(c, "adlib", False) and c.hotkey]
        dlg = KeyMapDialog(self._key_map, effects, self, space_go=self._space_go)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._keymap_store(dlg.key_map(), dlg.space_go())
            self._status_label.setText(tr("Tasti aggiuntivi salvati per questo computer") if self._space_go
                                       else tr("Tasti salvati per questo computer: lo Spazio non dà più il GO"))
