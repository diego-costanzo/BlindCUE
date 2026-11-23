"""Now playing (stage 1 C2a step 8) mixin for MainWindow.

Builds the cards of the show's right column from the cue statuses, the live
clocks and the waits, and turns their buttons into the same requests the
layer panel sends (pause, fade out) plus releasing a loop.
"""

from __future__ import annotations

import time

from engine.live_state import PHASE_POST, PHASE_PRE, fmt_clock
from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.now_playing import NOTE, STILL, TIMED, CardState

_ICONS = {MediaType.AUDIO: "♪", MediaType.VIDEO: "▶", MediaType.IMAGE: "▣"}


class _NowPlayingMixin:
    def _now_playing_setup(self) -> None:
        """Wire the cards (called once the show page exists)."""
        panel = self._live_show_panel.now_playing
        panel.pause_requested.connect(self.layer_play_pause_requested.emit)
        panel.fade_requested.connect(self._on_card_fade)
        panel.cancel_start_requested.connect(self._on_card_cancel_start)
        panel.release_requested.connect(self.release_loop_requested.emit)
        panel.note_dismissed.connect(lambda _cid: self._note_banner.dismiss())
        panel.seek_requested.connect(self._on_card_seek)
        panel.hold_longer.connect(lambda: self._status_label.setText(
            tr("Tieni premuto per saltare di 10 s (1,5 s nello spettacolo)")))
        panel.trim_requested.connect(self._on_card_trim)
        self._live_show_panel.hold_auto_go_requested.connect(self._on_hold_auto_go)
        # Output preview: up to 5 frames a second, only while the show page is up.
        shown = str(QSettings("BlindCue", "BlindCue").value("live/output_preview", True)).lower()             not in ("false", "0")
        panel.btn_preview.setChecked(shown)
        panel.preview_toggled.connect(self._on_preview_toggled)
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(200)
        self._preview_timer.timeout.connect(self._refresh_output_preview)
        self._preview_cost: list[float] = []

    def _on_preview_toggled(self, shown: bool) -> None:
        QSettings("BlindCue", "BlindCue").setValue("live/output_preview", bool(shown))
        self._update_preview_timer()

    def _update_preview_timer(self) -> None:
        run = self._live_mode and self._live_show_panel.now_playing.preview_shown()
        if run and not self._preview_timer.isActive():
            name = self._readiness_screen()[0]
            self._live_show_panel.now_playing.set_preview_title(
                tr("ANTEPRIMA USCITA") + (f" · {name}" if name else ""))
            self._preview_timer.start()
            self._refresh_output_preview()
        elif not run:
            self._preview_timer.stop()

    def _refresh_output_preview(self) -> None:
        if not self._live_mode or not self.isVisible():
            return
        from PySide6.QtGui import QPixmap

        started = time.perf_counter()
        image = self._output.preview_image(240, 135)
        self._live_show_panel.now_playing.set_preview(QPixmap.fromImage(image))
        cost = time.perf_counter() - started
        self._preview_cost = (self._preview_cost + [cost])[-50:]
        if len(self._preview_cost) == 50 and not getattr(self, "_preview_cost_logged", False):
            self._preview_cost_logged = True
            logger.info("[PREVIEW] output preview: %.1f ms a frame (avg of 50, 5 fps)",
                        1000 * sum(self._preview_cost) / 50)

    def _on_card_fade(self, slot: int) -> None:
        self._status_label.setText(tr("Sfuma: solo la cue di questa scheda"))
        self.card_fade_requested.emit(slot)

    def _on_card_cancel_start(self, slot: int) -> None:
        self._status_label.setText(tr("Partenza annullata: la cue non parte"))
        self.layer_cancel_start_requested.emit(slot)

    def _on_card_seek(self, slot: int, delta: float) -> None:
        pos = self._live_clocks.layer_position(slot)
        if pos is not None:
            self.layer_seek_requested.emit(slot, max(0.0, pos + delta))

    def _on_card_trim(self, slot: int, trim: float) -> None:
        self._trims[slot] = max(0.0, min(1.0, float(trim)))
        self._ramps.pop(slot, None)  # the operator's hand replaces a running ramp
        self.layer_trim_requested.emit(slot, self._trims[slot])

    def note_level_ramp(self, slot: int, trim: float, seconds: float, by: Cue) -> None:
        """main.py: a level action ramps *slot* to *trim* (shown on that card while it runs)."""
        before = self._trims.get(slot, 1.0)
        self._trims[slot] = max(0.0, float(trim))
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == by.cue_id), -1)
        arrow = "↘" if trim < before else "↗"
        self._ramps[slot] = (
            tr("{} a {} % ({} s) da {}").format(arrow, round(trim * 100), f"{seconds:.1f}",
                                               format_cue_ref(row, by) if row >= 0 else by.name),
            time.monotonic() + max(0.3, float(seconds)),
        )
        self._run_live_clock()

    def _on_hold_auto_go(self, cue_id: int) -> None:
        """NEXT bar "Hold": the Auto-GO after *cue_id* waits for a GO (an actor is late)."""
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)
        ref = format_cue_ref(row, self._cues[row]) if row >= 0 else "?"
        if cue_id in self._held_auto_go:
            self._held_auto_go.discard(cue_id)
            self._status_label.setText(tr("Auto-GO dopo {} di nuovo attivo").format(ref))
        else:
            self._held_auto_go.add(cue_id)
            self._status_label.setText(tr("Auto-GO dopo {} fermato: la prossima aspetta il GO").format(ref))
        self._live_show_panel.set_auto_go_held(self._held_auto_go)
        self.announce(self._status_label.text(), assertive=True)

    def _now_playing_cards(self) -> list[CardState]:
        cards: list[CardState] = []
        paused_all = getattr(self, "_is_global_paused", False)
        for row, cue in enumerate(self._cues):
            if cue.media_type in (MediaType.GROUP, MediaType.ACTION):
                continue
            tag = str(self._live_phase_tags.get(cue.cue_id, ""))
            waiting = tag.startswith("PRE")
            if cue.status != CueStatus.LIVE and not waiting:
                continue
            slot = self._runtime_slot(cue)
            t = self._live_clocks.cue_time(cue.cue_id)
            title = f"{_ICONS.get(cue.media_type, '•')} {format_cue_ref(row, cue)} '{cue.name}'"
            layer = f"B·L{cue.layer}" if slot > 3 else f"L{cue.layer}"
            timed = cue.media_type in (MediaType.AUDIO, MediaType.VIDEO) or (
                cue.media_type == MediaType.IMAGE and cue.hold_time > 0)
            loop = bool(cue.loop) or any(s.loops == 0 and not s.skip for s in cue.sections)
            paused = paused_all or slot in self._paused_slots
            state = ""
            ramp = self._ramps.get(slot)
            if ramp is not None and ramp[1] <= time.monotonic():
                self._ramps.pop(slot, None)
                ramp = None
            if t is not None and t.phase == PHASE_PRE:
                state = tr("parte tra {}").format(fmt_clock(t.remaining or 0.0))
            elif paused:
                state = tr("PAUSA")
            elif t is not None and t.phase == PHASE_POST:
                state = tr("attesa {}").format(fmt_clock(t.remaining or 0.0))
            elif ramp is not None:
                state = ramp[0]
            elif t is not None and t.looping_inf:
                state = tr("LOOP ∞")
            if not timed:
                cards.append(CardState(cue.cue_id, STILL, title, layer, state, slot=slot, waiting=waiting))
                continue
            elapsed = remaining = ""
            fraction, warn = -1.0, False
            if t is not None and not t.phase:
                elapsed = fmt_clock(t.elapsed)
                if t.remaining is not None:
                    remaining = "-" + fmt_clock(t.remaining)
                elif t.looping_inf:
                    remaining = "∞"
                fraction = t.fraction
                warn = ends_soon(t) and not self._hands_over_by_itself(cue)
            cards.append(CardState(cue.cue_id, TIMED, title, layer, state, elapsed, remaining, fraction,
                                   warn, paused, loop, slot, self._trims.get(slot, 1.0),
                                   cue.media_type in (MediaType.AUDIO, MediaType.VIDEO) and not waiting,
                                   waiting=waiting))
        banner = getattr(self, "_note_banner", None)
        if self._live_mode and banner is not None and banner.is_shown() and not banner.is_checklist():
            cue_id = banner.cue_id()
            row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue_id), -1)
            ref = format_cue_ref(row, self._cues[row]) if row >= 0 else ""
            cards.append(CardState(cue_id, NOTE, f"📝 {ref} {banner.text()}".strip()))
        return cards

    def _refresh_now_playing(self) -> None:
        panel = getattr(self, "_live_show_panel", None)
        if panel is not None and hasattr(panel, "now_playing"):
            panel.now_playing.set_cards(self._now_playing_cards())
            paused_all = getattr(self, "_is_global_paused", False)
            panel.set_paused_cues({c.cue_id for c in self._cues if c.status == CueStatus.LIVE and (
                paused_all or self._runtime_slot(c) in self._paused_slots)})
