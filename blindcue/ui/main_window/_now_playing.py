"""Now playing (stage 1 C2a step 8) mixin for MainWindow.

Builds the cards of the show's right column from the cue statuses, the live
clocks and the waits, and turns their buttons into the same requests the
layer panel sends (pause, fade out) plus releasing a loop.
"""

from __future__ import annotations

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
        panel.fade_requested.connect(self._on_clear_live_layer)
        panel.release_requested.connect(self.release_loop_requested.emit)
        panel.note_dismissed.connect(lambda _cid: self._note_banner.dismiss())

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
            if t is not None and t.phase == PHASE_PRE:
                state = tr("parte tra {}").format(fmt_clock(t.remaining or 0.0))
            elif paused:
                state = tr("PAUSA")
            elif t is not None and t.phase == PHASE_POST:
                state = tr("attesa {}").format(fmt_clock(t.remaining or 0.0))
            elif t is not None and t.looping_inf:
                state = tr("LOOP ∞")
            if not timed:
                cards.append(CardState(cue.cue_id, STILL, title, layer, state, slot=slot))
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
                                   warn, paused, loop, slot))
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
