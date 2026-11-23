"""Cues on / off and named versions of the show (stage 2, item 2.3) mixin for MainWindow.

A cue switched off never plays: GO, "together" chains, Auto-GO, groups,
relative starts, jumps and effect keys all pass it by. A *version* of the
show (e.g. "short", "second cast") is a named set of cues that are off;
the versions travel with the show file (settings "versions" / "version").
The full show (every cue on) is always there and has no stored set.
Switching off a cue that something points at (an Auto-GO or "together"
before it, a jump, a call, an action, a relative start) says so first.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QInputDialog

from ui.main_window._common import *  # noqa: F403,F401,F405


class _VersionsMixin:
    def _versions_setup(self) -> None:
        self._versions: dict[str, list[int]] = {}   # version name -> cue_ids that are off
        self._version_name = ""                      # "" = the full show
        self._lbl_version = QLabel("")
        self._lbl_version.setStyleSheet("color: #fbbf24; font-weight: bold; padding: 0 6px;")
        self._lbl_version.setVisible(False)
        self._cue_list.enabled_toggle_requested.connect(self._toggle_selected_enabled)
        # 2.4: rehearse from a cue (both lists)
        self._cue_list.rehearse_from_requested.connect(lambda: self._rehearse_from(self._cue_list.currentRow()))
        self._live_show_panel.rehearse_from_requested.connect(self._rehearse_from)
        self._versions_menu.aboutToShow.connect(self._rebuild_versions_menu)

    # ── the file ──
    def _versions_settings(self) -> dict:
        return {"versions": {k: list(v) for k, v in self._versions.items()}, "version": self._version_name}

    def _versions_load(self, settings: dict | None) -> None:
        raw = (settings or {}).get("versions") if isinstance(settings, dict) else None
        self._versions = {str(k): [int(i) for i in v if isinstance(i, int)]
                          for k, v in (raw or {}).items() if isinstance(v, list)} if isinstance(raw, dict) else {}
        name = str((settings or {}).get("version", "") or "") if isinstance(settings, dict) else ""
        self._version_name = name if name in self._versions else ""
        self._version_status()

    # ── switching ──
    def _rebuild_versions_menu(self) -> None:
        menu = self._versions_menu
        menu.clear()
        group = QActionGroup(menu)
        group.setExclusive(True)
        for name in ["", *sorted(self._versions)]:
            label = tr("Spettacolo completo") if not name else name
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(name == self._version_name)
            act.triggered.connect(lambda _=False, n=name: self._switch_version(n))
            group.addAction(act)
        menu.addSeparator()
        menu.addAction(tr("Salva come nuova versione…"), self._save_version_as)
        if self._version_name:
            menu.addAction(tr("Elimina la versione «{}»").format(self._version_name), self._delete_version)

    def _switch_version(self, name: str) -> None:
        from engine.show_mode import EDIT_LIST

        if not self._change_allowed(EDIT_LIST):
            self._rebuild_versions_menu()
            return
        off = set(self._versions.get(name, [])) if name else set()
        self._begin_change()
        for cue in self._cues:
            cue.enabled = cue.cue_id not in off
        self._version_name = name
        self._end_change(tr("Versione: {}").format(name or tr("Spettacolo completo")))

    def _save_version_as(self) -> None:
        name, ok = QInputDialog.getText(self, tr("Nuova versione dello spettacolo"),
                                        tr("Nome della versione (per esempio «ridotta», «secondo cast»):"))
        name = (name or "").strip()[:40]
        if not ok or not name:
            return
        self._versions[name] = [c.cue_id for c in self._cues if not getattr(c, "enabled", True)]
        self._version_name = name
        self._mark_modified(True)
        self._version_status()

    def _delete_version(self) -> None:
        if not self._version_name:
            return
        self._versions.pop(self._version_name, None)
        self._switch_version("")

    # ── one cue on / off ──
    def _references_to(self, cue: Cue) -> list[str]:
        """What would start *cue*: an Auto-GO / "together" before it, jumps, calls, actions, relative starts."""
        refs = []
        rows = {c.cue_id: i for i, c in enumerate(self._cues)}
        row = rows.get(cue.cue_id, -1)
        if row > 0:
            prev = self._cues[row - 1]
            if prev.follow_mode != FollowMode.MANUAL.value and prev.parent_id == cue.parent_id:
                refs.append(f"#{row} ({'Auto-GO' if prev.follow_mode == FollowMode.AUTO_FOLLOW.value else tr('insieme')})")
        for other in self._cues:
            if other is cue:
                continue
            if other.media_type == MediaType.ACTION and cue.cue_id in (other.action_spec.get("cue_ids") or []):
                refs.append(f"#{rows[other.cue_id] + 1} ({other.name})")
            if getattr(other, "start_rel_cue", None) == cue.cue_id:
                refs.append(f"#{rows[other.cue_id] + 1} (⏱)")
        return refs

    def _toggle_selected_enabled(self) -> None:
        """Context menu: switch the selected cues off (or on again) in this version."""
        from engine.show_mode import EDIT_LIST

        from engine.show_engine import block_end

        rows = self._selected_rows()
        if not rows or not self._change_allowed(EDIT_LIST):
            return
        wanted: list[int] = []
        for r in rows:  # a group: with everything inside it
            for i in range(r, block_end(self._cues, r) + 1):
                if i not in wanted:
                    wanted.append(i)
        cues = [self._cues[r] for r in wanted]
        turn_on = not all(getattr(c, "enabled", True) for c in cues)
        warnings = []
        if not turn_on:
            for cue in cues:
                refs = self._references_to(cue)
                if refs:
                    warnings.append(tr("{} è usata da: {}").format(cue.name, ", ".join(refs)))
        self._begin_change()
        for cue in cues:
            cue.enabled = turn_on
        if self._version_name:
            self._versions[self._version_name] = [c.cue_id for c in self._cues if not getattr(c, "enabled", True)]
        text = (tr("Incluse {} cue") if turn_on else tr("Escluse {} cue")).format(len(cues))
        self._end_change(text + (" — " + tr("Attenzione: ") + "; ".join(warnings) if warnings else ""))

    # ── helpers ──
    def _begin_change(self) -> None:
        if self._undo.is_debounce_active():
            self._commit_undo_point()

    def _end_change(self, message: str) -> None:
        self._refresh_cue_list(keep_selection=True)
        self._commit_undo_point()
        self._mark_modified(True)
        self._version_status()
        self._status_label.setText(message)
        self.announce(message)

    def _version_status(self) -> None:
        off_ids = [c.cue_id for c in self._cues if not getattr(c, "enabled", True)]
        if self._version_name:
            self._versions[self._version_name] = off_ids  # the version is what the list shows (Undo too)
        off = len(off_ids)
        if not self._version_name and not off:
            self._lbl_version.setVisible(False)
            return
        bar = self.statusBar()  # the window sets its own status bar later in its setup
        if self._lbl_version.parent() is not bar:
            bar.addPermanentWidget(self._lbl_version)
        name = self._version_name or tr("Spettacolo completo")
        self._lbl_version.setText(tr("Versione: {} · {} cue escluse").format(name, off))
        self._lbl_version.setVisible(True)
