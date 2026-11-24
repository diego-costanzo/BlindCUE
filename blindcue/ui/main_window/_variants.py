"""View variants of the Preparation view: Lite / Medium / Full (stage 1 C2b, plan item 1.11).

One mechanism: a variant is a fixed set of visible panels of the editor page
and the proportions of its splitters – the same widgets and data, switched
without a restart. Every start opens in Lite (GUI review 2026-11-24: a calm
first screen for a teacher; whoever needs more switches, for this session
only), never in the show file. The Rehearsal and Show screen is one and the
same in every variant. A rare switch hidden in a variant (Jam, remote, MIRROR
LIVE) shows by itself while it is on.
"""

from __future__ import annotations

from i18n import tr
from PySide6.QtWidgets import QMenu, QPushButton

from ui.main_window._common import *  # noqa: F403,F401,F405

LITE, MEDIUM, FULL = "lite", "medium", "full"
START_VARIANT = LITE
_NAMES = {LITE: "Semplice", MEDIUM: "Esteso", FULL: "Completo"}


class _VariantsMixin:
    def _variants_setup(self) -> None:
        """Menu View → Window layout, the "Layout: … ▾" button; every start in Lite."""
        self._variant = START_VARIANT
        menu = QMenu(tr("▦ Layout della finestra"), self)
        self._variant_menu = menu
        group = QActionGroup(self)
        group.setExclusive(True)
        self._variant_actions: dict[str, QAction] = {}
        labels = {
            LITE: "&Semplice – lista, GO e impostazioni di base",
            MEDIUM: "&Esteso – in più la forma d'onda e tutte le schede",
            FULL: "&Completo – tutto, anche i layer e il caricamento rapido",
        }
        for key in (LITE, MEDIUM, FULL):
            act = QAction(labels[key], self, checkable=True)
            act.triggered.connect(lambda _c=False, k=key: self.apply_view_variant(k))
            group.addAction(act)
            menu.addAction(act)
            self._variant_actions[key] = act
        menu.addSeparator()
        menu.addAction(self._act_lock_layout)
        menu.addAction(QAction(tr("↺ Ripristina layout"), self, triggered=self._restore_variant_layout))
        for act in self.menuBar().actions():
            if act.menu() is not None and act.menu().actions() and self._act_live_mode in act.menu().actions():
                act.menu().insertMenu(act.menu().actions()[2], menu)
                break
        # "Layout: Full ▾" right after the mode tabs of the editor bar.
        self._btn_variant = QPushButton()
        self._btn_variant.setFixedHeight(34)
        self._btn_variant.setMenu(menu)
        self._btn_variant.setToolTip(tr("Quanti pannelli mostra la preparazione (lo spettacolo non cambia)"))
        self._btn_variant.setStyleSheet(
            "QPushButton { background-color: #1c2636; color: #e2e8f0; border: 1px solid #3c4f6b; "
            "border-radius: 5px; font-weight: bold; font-size: 12px; padding: 0px 12px; } "
            "QPushButton:focus { border: 2px solid #38bdf8; }")
        bar_layout = self._design_control_bar.layout()
        bar_layout.insertWidget(bar_layout.indexOf(self._mode_tabs) + 1, self._btn_variant)
        self.apply_view_variant(self._variant, initial=True)

    # ── Switching ─────────────────────────────────────────────────────
    def apply_view_variant(self, variant: str, initial: bool = False) -> None:
        if variant not in _NAMES:
            return
        focused = QApplication.focusWidget()
        if focused is not None and self._inspector.isAncestorOf(focused):
            focused.clearFocus()  # takes what is being typed, like Tab
            if self._undo.is_debounce_active():
                self._commit_undo_point()
        self._variant = variant
        lite, medium = variant == LITE, variant == MEDIUM
        self._variant_actions[variant].setChecked(True)
        name = tr(_NAMES[variant])
        self._btn_variant.setText(tr("Layout: {}").format(name))  # the menu arrow is drawn by Qt
        self._btn_variant.setAccessibleName(tr("Layout della finestra: {}").format(name))
        # Bottom row: nothing in Lite, the waveform alone in Medium, all in Full.
        self._bottom_splitter.setVisible(not lite)
        self._live_status.setVisible(variant == FULL)
        self._drop_group.setVisible(variant == FULL)
        self._cue_list_panel.link_box.setVisible(variant == FULL)
        self._inspector.set_lite(lite)
        # Panels move only in Full; Lite and Medium keep their fixed proportions.
        if variant != FULL:
            self._set_panels_locked(True, announce=False)
        self._act_lock_layout.setEnabled(variant == FULL)
        self._update_variant_status_bar()
        self._apply_top_splitter_ratios()
        if not initial:
            self._cue_list.setFocus()
            if self._live_mode:
                self._status_label.setText(tr("Il layout {} si vede tornando in preparazione").format(name))
            else:
                self._status_label.setText(tr("Layout: {}").format(name))
            self.announce(self._status_label.text())

    def _update_variant_status_bar(self) -> None:
        """Rare switches: hidden in Lite and Medium, but always shown while they are on."""
        # In the Rehearsal and the Show only what is switched on (GUI review 2026-11-24).
        full = self._variant == FULL and not getattr(self, "_live_mode", False)
        self._btn_lock_layout.setVisible(full)
        jam_on = bool(getattr(self, "_jam_mode_active", False))
        remote_on = bool(self._remote_mgr and (self._remote_mgr.is_web_active() or self._remote_mgr.is_osc_active())) \
            if getattr(self, "_remote_mgr", None) else False
        self._btn_jam_mode.setVisible(full or jam_on)
        self._btn_remote_status.setVisible(full or remote_on)
        mirror = getattr(self._preview_panel, "btn_live_mirror", None)
        if mirror is not None:
            mirror.setVisible(self._variant != LITE or bool(getattr(self, "_live_mirror_active", False)))

    def _variant_top_sizes(self, total: int) -> list[int] | None:
        """Lite: middle and inspector first, the list takes the rest (C2b §3.2)."""
        if getattr(self, "_variant", FULL) != LITE:
            return None
        middle = max(420, int(round(total * 0.32)))
        inspector = max(360, int(round(total * 0.25)))
        return [max(300, total - middle - inspector), middle, inspector]

    def _restore_variant_layout(self) -> None:
        """View → Window layout → Restore layout: default sizes, folded inspector, first tab."""
        self._inspector.set_lite(self._variant == LITE)
        self._inspector.tab_widget.setCurrentIndex(0)
        if self._variant == FULL:
            self._set_panels_locked(True, announce=False)
            self._reset_standard_layout()
        else:
            self._apply_top_splitter_ratios()
        self._status_label.setText(tr("Ripristinato il layout {}: larghezze dei pannelli e impostazioni della cue")
                                   .format(tr(_NAMES[self._variant])))
        self.announce(self._status_label.text())

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Enter presses the focused button (Space stays GO, decision 4; W55)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            from PySide6.QtWidgets import QAbstractButton

            focused = QApplication.focusWidget()
            if isinstance(focused, QAbstractButton) and focused.isEnabled() and self.isAncestorOf(focused):
                focused.click()
                event.accept()
                return
        super().keyPressEvent(event)
