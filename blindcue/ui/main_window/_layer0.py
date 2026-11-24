"""Layer 0 (Tappo) mixin for MainWindow.

Layer 0 is what the projector shows when no cue is live. Since the teacher
evaluation (2026-11-24) it is one of four kinds, saved with the show
(``layer0_kind``): plain black (the default), a picture or logo, a video
playing in a loop without sound (e.g. curtains), or the test pattern for
setting up the projector - the pattern shows only in Preparation; in the
rehearsal and the show the placeholder is black then. It is mirrored on both
outputs and on the preview monitor.
"""

from __future__ import annotations

from i18n import tr
from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.main_window._common import (  # noqa: F401
    _AutosaveWorker,
    _DEFAULT_TOP_RATIOS,
    _MEDIA_ICONS,
    _demote_live_on_layer,
)

L0_BLACK, L0_IMAGE, L0_VIDEO, L0_PATTERN = "black", "image", "video", "pattern"
L0_KINDS = (L0_BLACK, L0_IMAGE, L0_VIDEO, L0_PATTERN)


class _Layer0Mixin:
    def _apply_layer0(self, kind: str, path: str | None = None) -> bool:
        """Put the placeholder on both outputs and the preview; False (nothing changed) when the file cannot be used."""
        from engine.show_mode import PREPARATION
        from ui.output_window import LAYER0_BLACK

        kind = kind if kind in L0_KINDS else L0_BLACK
        shown = kind
        if kind == L0_PATTERN and self._current_mode() != PREPARATION:
            shown = L0_BLACK  # the test pattern is for setting up, never in front of the audience
        outputs = [self._output] + ([self._output_b] if getattr(self, "_output_b", None) is not None else [])
        for i, out in enumerate(outputs):
            if shown == L0_IMAGE:
                ok = out.set_layer0_image(path)
            elif shown == L0_VIDEO:
                ok = out.set_layer0_video(path or "")
            elif shown == L0_PATTERN:
                ok = out.set_layer0_image(None)
            else:
                ok = out.set_layer0_image(LAYER0_BLACK)
            if i == 0 and not ok:
                return False
        self._layer0_kind = kind
        self._layer0_image = path if kind == L0_IMAGE else None
        self._layer0_video = path if kind == L0_VIDEO else None
        self._layer0_shown = shown
        self._preview_monitor.set_layer0_image(
            path if shown == L0_IMAGE else (None if shown == L0_PATTERN else LAYER0_BLACK))
        self._live_status.set_layer0_label(path, kind)
        for k, act in getattr(self, "_l0_actions", {}).items():
            act.setChecked(k == kind)
        return True

    def set_layer0_image(self, file_path: str | None) -> bool:
        """A picture as the placeholder (None or the built-in logo: the test pattern)."""
        from ui.tappo_pattern import is_default_tappo_path

        if is_default_tappo_path(file_path):
            return self._apply_layer0(L0_PATTERN)
        return self._apply_layer0(L0_IMAGE, file_path)

    def _layer0_settings(self) -> dict[str, Any]:
        """What the show saves about its placeholder."""
        kind = getattr(self, "_layer0_kind", L0_BLACK)
        out: dict[str, Any] = {"layer0_kind": kind}
        if kind == L0_IMAGE and self._layer0_image:
            out["layer0_image"] = self._layer0_image
        if kind == L0_VIDEO and getattr(self, "_layer0_video", None):
            out["layer0_video"] = self._layer0_video
        return out

    def _restore_layer0(self, settings: Any) -> None:
        """The placeholder of an opened show; a missing file falls back to black (never an error)."""
        settings = settings if isinstance(settings, dict) else {}
        image, video = settings.get("layer0_image"), settings.get("layer0_video")
        kind = settings.get("layer0_kind") or (L0_IMAGE if image else L0_BLACK)
        path = image if kind == L0_IMAGE else video if kind == L0_VIDEO else None
        if kind in (L0_IMAGE, L0_VIDEO) and not (path and os.path.isfile(path)):
            kind, path = L0_BLACK, None
        if not self._apply_layer0(kind, path):
            self._apply_layer0(L0_BLACK)

    def _layer0_follow_mode(self) -> None:
        """Into the rehearsal or the show the test pattern turns black; back in Preparation it comes back."""
        if getattr(self, "_layer0_kind", L0_BLACK) == L0_PATTERN:
            from engine.show_mode import PREPARATION

            wanted = L0_PATTERN if self._current_mode() == PREPARATION else L0_BLACK
            if wanted != getattr(self, "_layer0_shown", None):
                self._apply_layer0(L0_PATTERN)

    def _build_layer0_menu(self, parent_menu) -> Any:
        """Show → "Placeholder (when nothing plays)": four kinds, one checked."""
        menu = parent_menu.addMenu("Tappo (quando non va niente)")
        group = QActionGroup(self)
        group.setExclusive(True)
        self._l0_actions = {}
        for kind, label, slot in (
            (L0_BLACK, "⬛ Nero", lambda: self._choose_layer0_kind(L0_BLACK)),
            (L0_IMAGE, "🖼 Immagine o logo…", self._on_choose_layer0),
            (L0_VIDEO, "🎞 Video in loop (senza suono)…", self._on_choose_layer0_video),
            (L0_PATTERN, "▦ Schema di prova (solo in preparazione)", lambda: self._choose_layer0_kind(L0_PATTERN)),
        ):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(slot)
            group.addAction(act)
            menu.addAction(act)
            self._l0_actions[kind] = act
        self._l0_actions[getattr(self, "_layer0_kind", L0_BLACK)].setChecked(True)
        self._l0_menu = menu
        return menu

    def _choose_layer0_kind(self, kind: str, path: str | None = None) -> None:
        if self._apply_layer0(kind, path):
            self._mark_modified(True)
            self._auto_save()
            names = {L0_BLACK: tr("Tappo: nero"), L0_PATTERN: tr("Tappo: schema di prova (solo in preparazione)")}
            self._status_label.setText(names.get(kind) or tr("Tappo: {}").format(Path(path or "").name))
        else:
            for k, act in getattr(self, "_l0_actions", {}).items():
                act.setChecked(k == getattr(self, "_layer0_kind", L0_BLACK))
            QMessageBox.warning(self, tr("File non valido"), tr("Impossibile usare questo file come tappo."))

    @Slot()
    def _on_choose_layer0(self) -> None:
        """A picture or a logo as the placeholder."""
        from ui import dialog_dirs

        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("Immagine del tappo"), dialog_dirs.media_dir("IMAGE"),
            "Immagini (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;Tutti i file (*)",
        )
        if file_path:
            dialog_dirs.remember_media_dir(file_path)
            self._choose_layer0_kind(L0_IMAGE, file_path)
        else:
            self._recheck_layer0_actions()

    @Slot()
    def _on_choose_layer0_video(self) -> None:
        """A video playing in a loop without sound as the placeholder."""
        from ui import dialog_dirs

        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("Video del tappo"), dialog_dirs.media_dir("VIDEO"),
            self._MEDIA_FILTERS[MediaType.VIDEO] + ";;" + tr("Tutti i file") + " (*)",
        )
        if file_path:
            dialog_dirs.remember_media_dir(file_path)
            self._choose_layer0_kind(L0_VIDEO, file_path)
        else:
            self._recheck_layer0_actions()

    def _recheck_layer0_actions(self) -> None:
        """A cancelled file dialog leaves the menu showing what is really on."""
        for k, act in getattr(self, "_l0_actions", {}).items():
            act.setChecked(k == getattr(self, "_layer0_kind", L0_BLACK))

    def _on_layer0_button(self) -> None:
        """The "Change placeholder" button under the output preview opens the same four choices."""
        menu = getattr(self, "_l0_menu", None)
        btn = self._live_status.btn_choose_tappo
        if menu is not None:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    @Slot()
    def _on_reset_layer0(self) -> None:
        """Back to the default placeholder: black."""
        self._choose_layer0_kind(L0_BLACK)
