"""Stage 3, item 3.4: a cue without a file yet (mixin for MainWindow).

The teacher writes the script before the sound effects are recorded: a
"sound to record" cue holds the place (its Q, name, notes, page, follow
mode). It stays in the GO order, so the operator's GOs keep their count in
the rehearsal, but its GO plays nothing: the status line says so and what
follows by itself still follows. The list marks it "NO FILE", the GO button
says it, the readiness page lists it; "Choose the file…" on the cue makes
it an ordinary cue.
"""

from __future__ import annotations

from i18n import tr
from models.cue import is_placeholder

from ui.main_window._common import *  # noqa: F403,F401,F405


class _PlaceholderMixin:
    def _placeholder_setup(self) -> None:
        menu = self._cue_list_panel.btn_add_action.menu()
        if menu is not None:
            menu.addSeparator()
            act = menu.addAction("🕳 Suono da registrare (senza file)")
            act.setToolTip("Un posto nella scaletta per un effetto che non c'è ancora: al GO non suona. "
                           "Il file si sceglie dopo, dal menu della cue.")
            act.triggered.connect(self._on_add_placeholder)

    def _on_add_placeholder(self) -> None:
        """A sound cue without its file (3.4), after the selected cue."""
        cue = Cue(name=tr("Effetto da registrare"), media_type=MediaType.AUDIO, file_path="")
        cue.layer = 2  # where its sound will play, as every new sound
        self._append_new_cue(cue)
        if any(c is cue for c in self._cues):
            self._status_label.setText(tr("Suono da registrare aggiunto: scegli il file quando c'è "
                                          "(menu della cue → Scegli il file…)"))

    def _placeholder_go(self, cue: Cue, note: bool = False) -> bool:
        """GO reached a cue without its file: nothing plays, what follows by itself goes on. False: not one."""
        if not is_placeholder(cue):
            return False
        if note:
            self._note_fired(cue)
        row = next((i for i, c in enumerate(self._cues) if c is cue), -1)
        ref = format_cue_ref(row, cue) if row >= 0 else ""
        text = tr("{} '{}': ancora senza file – non suona").format(ref, cue.name)
        logger.info("[GO] '%s' has no file yet: nothing plays", cue.name)

        def tell() -> None:
            self._status_label.setText(text)
            self.announce(text)

        QTimer.singleShot(0, tell)  # after the "LIVE →" line of this GO
        if self._hands_over_by_itself(cue) and not self._only_placeholders_loop(cue):
            QTimer.singleShot(100, lambda cid=cue.cue_id: self._placeholder_follow(cid))
        return True

    def _only_placeholders_loop(self, cue: Cue) -> bool:
        """A "Loop Scena" of placeholders only would start itself again for ever."""
        parent = ShowEngine.group_parent(self._cues, cue)
        if parent is None or getattr(parent, "group_mode", "") != GroupMode.LOOP.value:
            return False
        return all(is_placeholder(k) for k in ShowEngine.children_of(self._cues, parent.cue_id))

    def _placeholder_follow(self, cue_id: int) -> None:
        cue = next((c for c in self._cues if c.cue_id == cue_id), None)
        if cue is not None:
            self.trigger_auto_follow_from(cue)
