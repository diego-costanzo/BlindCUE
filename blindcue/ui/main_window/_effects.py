"""Effects on demand (stage 1 phase D, plan items 1.7 and 1.10) mixin for MainWindow.

A cue marked "effect on demand" stays out of the GO order: its key (a letter
or a digit) or its tile in "Now playing" starts it on a free player, without
moving the GO pointer or stopping what plays. Modes: start (again = from the
top), start/stop, and "plays while the key is held". Several cues on one key
start one after the other (steps, from the first again when the show is
entered). "Repeat the last effect" (Ctrl+R or its tile) plays it once more.
Keys work only in the rehearsal and the show, never while typing.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtCore import QEvent, QObject

from ui.main_window._common import *  # noqa: F403,F401,F405


def _event_key(event) -> str:
    """The letter or digit of a key event by its key code (any keyboard layout, any Shift)."""
    code = int(event.key())
    if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A:
        return chr(code)
    return ""


class _HotkeyFilter(QObject):
    """Application-wide: letters and digits of the effects, only in the rehearsal/show."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._win = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        w = self._win
        if kind == QEvent.Type.ApplicationDeactivate or (
                kind == QEvent.Type.WindowDeactivate and obj is w):
            w._release_all_notes()
            return False
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.ShortcutOverride):
            return False
        key = _event_key(event)
        if not key:
            return False
        if kind == QEvent.Type.KeyRelease and key in w._held_notes:
            # A held effect always stops when its key is let go, whatever else changed.
            if not event.isAutoRepeat():
                w._on_hotkey_release(key)
            return True
        if not w._live_mode or key not in w._hotkey_map or not w.isActiveWindow():
            return False
        if event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            return False  # Ctrl/Alt/Shift combinations belong to the menus
        if QApplication.activePopupWidget() is not None:
            return False  # a menu or a list is open: the letter is for it
        if w._is_text_input_focused() or w._readiness_visible():
            return False
        if kind == QEvent.Type.ShortcutOverride:
            event.accept()  # the key is ours, not a shortcut's (I / O of the editor)
            return True
        if not event.isAutoRepeat():
            if kind == QEvent.Type.KeyPress:
                w._on_hotkey_press(key)
            else:
                w._on_hotkey_release(key)
        return True  # never also a search by letter in the list


class _EffectsMixin:
    def _effects_setup(self) -> None:
        self._hotkey_map: dict[str, list[int]] = {}   # key -> cue_ids in list order
        self._step_pos: dict[str, int] = {}
        self._held_notes: dict[str, int] = {}         # key -> cue_id playing while held
        self._last_effect_id = -1
        self._effects_on = False
        self._effects_sig: tuple = ()
        self._hotkey_filter = _HotkeyFilter(self)
        self._hotkeys_installed = False
        panel = self._live_show_panel.now_playing
        panel.effect_requested.connect(self._fire_effect_id)
        panel.repeat_effect_requested.connect(self._repeat_last_effect)
        QShortcut(QKeySequence("Ctrl+R"), self, self._repeat_last_effect)

    def _effects_activate(self, on: bool) -> None:
        """Entering the rehearsal/show: keys and tiles from the show; leaving: none."""
        self._effects_on = on
        self._step_pos = {}
        self._effects_sig = ()
        if not on:
            self._release_all_notes()
        self._effects_sync()

    def _effects_sync(self) -> None:
        """Keys and tiles from the cues now (also after a fix in the rehearsal)."""
        effects = []
        for row, cue in enumerate(self._cues):
            if getattr(cue, "adlib", False) and getattr(cue, "enabled", True):
                key = (getattr(cue, "hotkey", "") or "").upper()
                effects.append((cue.cue_id, key, f"{key + ' · ' if key else ''}{format_cue_ref(row, cue)} {cue.name}"))
        sig = (self._effects_on, tuple(effects))
        if sig == self._effects_sig:
            return
        self._effects_sig = sig
        self._hotkey_map = {}
        if self._effects_on:
            for cue_id, key, _label in effects:
                if key:
                    self._hotkey_map.setdefault(key, []).append(cue_id)
        # The filter sees every event of the program: only while a key can do something.
        want = bool(self._hotkey_map)
        app = QApplication.instance()
        if want and not self._hotkeys_installed:
            app.installEventFilter(self._hotkey_filter)
            self._hotkeys_installed = True
        elif not want and self._hotkeys_installed:
            app.removeEventFilter(self._hotkey_filter)
            self._hotkeys_installed = False
        tiles = [(cue_id, label) for cue_id, _key, label in effects] if self._effects_on else []
        self._live_show_panel.now_playing.set_effects(tiles)

    # ── Starting and stopping ─────────────────────────────────────────
    def _effect_running(self, cue: Cue) -> bool:
        return cue.status == CueStatus.LIVE or cue.cue_id in self._live_phase_tags

    def _fire_effect_id(self, cue_id: int, remember: bool = True) -> None:
        idx = next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)
        if idx < 0:
            return
        cue = self._cues[idx]
        mode = getattr(cue, "hotkey_mode", "trigger")
        if mode == "toggle" and self._effect_running(cue):
            self._stop_effect(cue)
            return
        if mode == "once" and self._effect_running(cue):
            # Pressed again while it plays (or waits in its Pre-Delay): nothing, it is not restarted.
            self._status_label.setText(tr("Effetto già in corso: '{}' (non riparte)").format(cue.name))
            return
        self._run_event("EFFECT", cue.name, cue.cue_id)  # 5.19
        if remember:
            self._last_effect_id = cue.cue_id
        self._fire_cue_chain(idx, auto=True, keep_pointer=True)
        go = self._go_target_index()
        if 0 <= go < len(self._cues):
            self._status_label.setText(tr("Effetto: {} '{}' (il GO resta su {})").format(
                format_cue_ref(idx, cue), cue.name, format_cue_ref(go, self._cues[go])))

    def _stop_effect(self, cue: Cue) -> None:
        if cue.status == CueStatus.LIVE:
            self.card_fade_requested.emit(self._runtime_slot(cue))
        elif cue.cue_id in self._live_phase_tags:
            # Still in its Pre-Delay: only its start is cancelled (what plays there goes on).
            self.layer_cancel_start_requested.emit(self._runtime_slot(cue))

    def _repeat_last_effect(self) -> None:
        """Ctrl+R / its tile: the last effect once more (1.10)."""
        if not self._live_mode:
            return
        if self._last_effect_id < 0:
            self._status_label.setText(tr("Nessun effetto da ripetere"))
            return
        self._fire_effect_id(self._last_effect_id)

    def _on_hotkey_press(self, key: str) -> None:
        ids = self._hotkey_map.get(key, [])
        if not ids:
            return
        if len(ids) > 1:
            # Steps: one key, several cues, one after the other.
            pos = self._step_pos.get(key, 0) % len(ids)
            self._step_pos[key] = pos + 1
            self._fire_effect_id(ids[pos])
            return
        cue = next((c for c in self._cues if c.cue_id == ids[0]), None)
        if cue is None:
            return
        note = getattr(cue, "hotkey_mode", "trigger") == "note"
        # A held note is not "the last effect": Ctrl+R would play it to its end.
        self._fire_effect_id(cue.cue_id, remember=not note)
        if note:
            self._held_notes[key] = cue.cue_id

    def _on_hotkey_release(self, key: str) -> None:
        cue_id = self._held_notes.pop(key, None)
        if cue_id is not None:
            cue = next((c for c in self._cues if c.cue_id == cue_id), None)
            if cue is not None:
                self._stop_effect(cue)

    def _release_all_notes(self) -> None:
        """Keys let go behind our back (the window lost focus): a held note stops."""
        for key in list(self._held_notes):
            self._on_hotkey_release(key)
