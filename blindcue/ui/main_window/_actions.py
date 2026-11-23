"""Action cues (stop, fade, level, layer opacity, operator notes) mixin for MainWindow.

The players and output windows are driven from ``main.py``; this mixin keeps
the director window in step: new action cues, cue statuses after a stop, the
operator note zone and the status line.
"""

from __future__ import annotations

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    ShowEngine,
)

from engine.action_cues import default_action_name, default_action_spec, describe_action
from models.cue import ACTION_CHECKLIST, action_needs_target


class _ActionsMixin:
    # ── Creating action cues ──────────────────────────────────────────
    @Slot(str)
    def _on_add_action_cue(self, kind: str) -> None:
        """Append a new action cue of *kind* and open its settings."""
        from i18n import tr

        spec = default_action_spec(kind)
        # Stored text is show data: write it in the operator's language.
        spec["items"] = [tr(item) for item in spec["items"]]
        cue = Cue(
            name=tr(default_action_name(kind)),
            media_type=MediaType.ACTION,
            file_path="",
            action_spec=spec,
        )
        self._append_new_cue(cue)
        if hasattr(self, "_inspector"):
            self._inspector.show_action_tab()

    # ── Effects on the cue list ───────────────────────────────────────
    def mark_layer_stopped(self, layer: int) -> None:
        """Mark what plays on runtime *layer* (1-6) as stopped, without touching the players."""
        self._reset_live_label(layer)
        runtime = int(layer)
        if runtime > 3:
            ShowEngine.clear_layer(
                self._cues, runtime - 3, output_target="B",
                dual_active=self._dual_output_active,
            )
        else:
            ShowEngine.clear_layer(
                self._cues, runtime, output_target="A",
                dual_active=self._dual_output_active,
            )
        self._refresh_cue_list()

    def action_cue_done(self, cue: Cue, layers: list[int]) -> None:
        """Report on the status line what an action cue just did."""
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue.cue_id), -1)
        ref = format_cue_ref(row, cue)
        kind = cue.action_spec.get("kind", "")
        if action_needs_target(kind) and not layers:
            self._status_label.setText(
                f"Azione {ref} '{cue.name}': nessun bersaglio in onda, niente da fare"
            )
        else:
            self._status_label.setText(
                f"AZIONE → {ref} '{cue.name}': {describe_action(cue.action_spec, self._cues)}"
            )
        self._sync_live_view()

    # ── Operator note zone ────────────────────────────────────────────
    def show_operator_note(self, cue: Cue) -> None:
        """Show the note or checklist of *cue* in the director window."""
        spec = cue.action_spec
        row = next((i for i, c in enumerate(self._cues) if c.cue_id == cue.cue_id), -1)
        title = f"📝 {format_cue_ref(row, cue)}  {cue.name}"
        items = list(spec.get("items", [])) if spec.get("kind") == ACTION_CHECKLIST else None
        banner = self._note_banner
        if items is None and banner.is_checklist() and banner.cue_id() != cue.cue_id:
            # One strip: a note covers an open checklist, which comes back after it.
            self._suspended_checklist_id = banner.cue_id()
        elif items is not None:
            self._suspended_checklist_id = None
        ticks = getattr(self, "_checklist_ticks", {}).get(cue.cue_id, set())
        self._note_banner.show_note(
            cue.cue_id, title, str(spec.get("text", "")), str(spec.get("note_color", "#f59e0b")),
            items=items, ticked=ticks,
        )
        self._refresh_now_playing()  # in the show a plain note is a card

    @Slot(int, int, bool)
    def _on_note_item_toggled(self, cue_id: int, index: int, ticked: bool) -> None:
        """Remember checklist ticks for this run of the program (not saved in the show)."""
        if not hasattr(self, "_checklist_ticks"):
            self._checklist_ticks = {}
        marks = self._checklist_ticks.setdefault(cue_id, set())
        if ticked:
            marks.add(index)
        else:
            marks.discard(index)
        done, total = self._note_banner.ticked()
        self._status_label.setText(f"Checklist: {done} di {total} spuntate")

    @Slot(int)
    def _on_note_dismissed(self, cue_id: int) -> None:
        """A note went away: bring back the checklist it covered, if any."""
        self._refresh_now_playing()
        suspended = getattr(self, "_suspended_checklist_id", None)
        self._suspended_checklist_id = None
        if suspended is None or suspended == cue_id:
            return
        cue = next((c for c in self._cues if c.cue_id == suspended), None)
        if cue is not None and cue.media_type == MediaType.ACTION:
            self.show_operator_note(cue)

    def _dismiss_note_on_go(self) -> None:
        """A manual GO moves on: a plain note goes away, a checklist stays until closed."""
        banner = getattr(self, "_note_banner", None)
        if banner is not None and banner.is_shown() and not banner.is_checklist():
            banner.dismiss()

    def _show_pending_checklist(self) -> None:
        """Entering LIVE shows the first checklist that still has unticked items."""
        banner = getattr(self, "_note_banner", None)
        if banner is None or banner.is_shown():
            return
        ticks = getattr(self, "_checklist_ticks", {})
        for cue in self._cues:
            if cue.media_type != MediaType.ACTION or cue.action_spec.get("kind") != ACTION_CHECKLIST:
                continue
            items = cue.action_spec.get("items", [])
            if items and len(ticks.get(cue.cue_id, set())) < len(items):
                self.show_operator_note(cue)
                return
