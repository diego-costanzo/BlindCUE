"""Readiness check before the show (stage 1 C2a step 7) mixin for MainWindow.

Entering the show (F5, Ctrl+L, the tab) first shows the "Before the show"
page in place of the list – a full check the first time in a session, after
the screens or the speakers changed and after another show was opened; later
only the rows that are not right, and no page at all when everything is.
The page ends with the start buttons of the start question (one decision).
Setting ``live/readiness_check`` (this computer) turns it off.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from engine.readiness import (
    CHECKLIST,
    DEFAULT_CHECKLIST,
    DEFAULT_CHECKLIST_NAME,
    MEDIA,
    OK,
    POWER,
    PROBLEM,
    SCREEN,
    SHOW,
    SKIPPED,
    SPEAKERS,
    VOLUME,
    Check,
    Facts,
    checks,
    page_rows,
    power_status,
    problems,
)
from i18n import tr

from ui.main_window._common import *  # noqa: F403,F401,F405
from ui.readiness_page import ReadinessPage, RowView

READINESS_SETTINGS_KEY = "live/readiness_check"


def _write_test_tone(path: Path) -> None:
    """1 s soft two-note chime at -20 dBFS (never played by itself)."""
    rate, amp = 44100, 0.1
    frames = bytearray()
    for i in range(rate):
        t = i / rate
        freq = 523.25 if t < 0.5 else 659.25
        local = t if t < 0.5 else t - 0.5
        env = min(1.0, local / 0.03, (0.5 - local) / 0.08)  # no clicks
        sample = int(32767 * amp * max(0.0, env) * math.sin(2 * math.pi * freq * t))
        frames += struct.pack("<hh", sample, sample)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))


class _ReadinessMixin:
    # ── Setup ─────────────────────────────────────────────────────────
    def _readiness_setup(self) -> None:
        """The page in the central stack (called once the stack exists)."""
        self._readiness_full_due = True     # first entry of the session
        self._readiness_heard: bool | None = None
        self._readiness_tone_asked = False
        self._readiness_review = False
        self._readiness_signature: tuple | None = None
        self._readiness_page = ReadinessPage()
        self._central_stack.addWidget(self._readiness_page)
        self._readiness_page.action_requested.connect(self._on_readiness_action)
        self._readiness_page.start_chosen.connect(self._on_readiness_start)
        self._readiness_page.stay_requested.connect(self._on_readiness_stay)
        self._readiness_page.checklist_toggled.connect(self._on_readiness_tick)
        self._readiness_timer = QTimer(self)
        self._readiness_timer.setInterval(2000)  # the power row changes by itself
        self._readiness_timer.timeout.connect(lambda: self._readiness_refresh(rebuild=False))
        self._tone_player = None
        self._tone_output = None

    def _readiness_enabled(self) -> bool:
        value = QSettings("BlindCue", "BlindCue").value(READINESS_SETTINGS_KEY, True)
        return str(value).lower() not in ("false", "0", "no")

    def _readiness_devices_changed(self) -> None:
        """Screens or speakers changed: the next entry checks everything again."""
        self._readiness_full_due = True
        self._readiness_heard = None
        self._readiness_tone_asked = False
        if self._readiness_visible():
            self._readiness_refresh()

    def _readiness_visible(self) -> bool:
        return self._central_stack.currentWidget() is self._readiness_page

    # ── Facts and words ───────────────────────────────────────────────
    def _readiness_screen(self) -> tuple[str | None, bool, int]:
        from PySide6.QtGui import QGuiApplication

        screens = QGuiApplication.screens()
        dm = getattr(self, "_device_mgr", None)
        target = dm.get_target_screen() if dm is not None else None
        if target is None:
            return None, False, len(screens)
        label = " ".join(x for x in (target.manufacturer(), target.model()) if x).strip(" -") or target.name()
        index = screens.index(target) + 1 if target in screens else 0
        name = tr("{} (schermo {})").format(label, index) if index else label
        return name, target != QGuiApplication.primaryScreen(), len(screens)

    def _readiness_checklist_cue(self) -> Cue | None:
        return next((c for c in self._cues if c.media_type == MediaType.ACTION
                     and c.action_spec.get("kind") == "checklist"), None)

    def _readiness_facts(self) -> Facts:
        from PySide6.QtMultimedia import QMediaDevices

        name, external, count = self._readiness_screen()
        dm = getattr(self, "_device_mgr", None)
        if dm is not None and dm.get_master_audio_device() is not None:
            speakers = dm.get_master_audio_device().description()
            pinned = dm.is_audio_remembered("master")
            missing_dev = dm.missing_audio_name("master")
        else:
            speakers, pinned, missing_dev = QMediaDevices.defaultAudioOutput().description(), False, None
        with_files = [(i, c) for i, c in enumerate(self._cues) if c.media_type.has_file]
        missing = tuple(f"{format_cue_ref(i, c)} '{c.name}'" for i, c in with_files
                        if not os.path.isfile(c.file_path or ""))
        checklist = None
        cue = self._readiness_checklist_cue()
        if cue is not None:
            items = cue.action_spec.get("items", [])
            ticks = getattr(self, "_checklist_ticks", {}).get(cue.cue_id, set())
            checklist = (len([i for i in ticks if i < len(items)]), len(items))
        path = getattr(self, "_current_project_path", None)
        show = Path(path).stem if path else tr("(non salvato)")
        if self._is_modified:
            show += " · " + tr("modifiche non salvate")
        playing = any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags)
        return Facts(
            screen_name=name, screen_external=external, screen_count=count,
            master_level=self._master_level, master_muted=self._master_muted,
            speakers=speakers, speakers_pinned=pinned, speakers_missing=missing_dev,
            heard=self._readiness_heard, playing=playing,
            missing=missing, media_total=len(with_files),
            power=power_status(), checklist=checklist, show_name=show,
        )

    def _readiness_view(self, check: Check) -> RowView:
        v = check.values
        if check.key == SCREEN:
            if check.state == OK:
                return RowView(SCREEN, OK, tr("Immagine: {}").format(v["name"]))
            text = (tr("L'immagine va sullo schermo del portatile: proiettore non trovato. "
                       "Se gli schermi sono duplicati, premi Win+P → Estendi.")
                    if v.get("single") else
                    tr("L'immagine va sullo schermo del portatile, anche se c'è un altro schermo."))
            return RowView(SCREEN, PROBLEM, text, [(tr("Mostra i numeri degli schermi"), "screens"),
                                                   (tr("Scegli lo schermo…"), "devices")])
        if check.key == VOLUME:
            if check.state == OK:
                return RowView(VOLUME, OK, tr("Volume generale 100 %, senza silenziamento"))
            text = (tr("Volume generale {} % · SILENZIATO") if v["muted"] else tr("Volume generale {} %")
                    ).format(v["percent"])
            return RowView(VOLUME, PROBLEM, text, [(tr("Riporta a 100 %"), "volume")])
        if check.key == SPEAKERS:
            name = tr("{} (scelte qui)").format(v["name"]) if v.get("pinned") else v.get("name", "")
            if check.state == OK:
                return RowView(SPEAKERS, OK, tr("Audio: {} – si sente in sala").format(name))
            if v.get("missing"):
                return RowView(SPEAKERS, PROBLEM, tr(
                    "Le casse scelte '{}' non sono collegate: suona l'uscita predefinita di Windows."
                ).format(v["missing"]), [(tr("Scegli le casse…"), "devices")])
            if v.get("not_heard"):
                return RowView(SPEAKERS, PROBLEM, tr("Audio: {} – il tono non si sente in sala").format(name),
                               [(tr("Scegli le casse…"), "devices"), (tr("▶ Tono di prova"), "tone")])
            answer = [(tr("Sì, si sente"), "heard_yes"), (tr("Non si sente"), "heard_no")]
            if v.get("playing"):
                return RowView(SPEAKERS, SKIPPED, tr(
                    "Audio: {} – il tono non è disponibile, qualcosa suona. Si sente in sala?"
                ).format(name), answer)
            if self._readiness_tone_asked:
                return RowView(SPEAKERS, SKIPPED, tr("Audio: {} – si sente in sala?").format(name),
                               answer + [(tr("▶ Tono di prova"), "tone")])
            return RowView(SPEAKERS, SKIPPED, tr("Audio: {} – suona il tono di prova e ascolta in sala").format(name),
                           [(tr("▶ Tono di prova"), "tone")])
        if check.key == MEDIA:
            if check.state == OK:
                return RowView(MEDIA, OK, tr("Tutti i file al loro posto ({})").format(v["count"]))
            shown = ", ".join(v["cues"][:4]) + (" …" if len(v["cues"]) > 4 else "")
            return RowView(MEDIA, PROBLEM, tr("File mancanti ({}): {}").format(v["count"], shown),
                           [(tr("Mostra nella lista"), "show_missing")])
        if check.key == POWER:
            if check.state == OK:
                return RowView(POWER, OK, tr("Portatile collegato all'alimentatore"))
            return RowView(POWER, PROBLEM, tr("Portatile a batteria ({} %): collega l'alimentatore").format(
                v["percent"]))
        if check.key == CHECKLIST:
            if v.get("none"):
                return RowView(CHECKLIST, check.state, tr("Lo spettacolo non ha una checklist"),
                               [(tr("Aggiungi la checklist predefinita"), "add_checklist")])
            cue = self._readiness_checklist_cue()
            return RowView(
                CHECKLIST, check.state, tr("Checklist: {} di {} spuntate").format(v["done"], v["total"]),
                items=list(cue.action_spec.get("items", [])) if cue else [],
                ticked=set(getattr(self, "_checklist_ticks", {}).get(cue.cue_id, set())) if cue else set(),
                cue_id=cue.cue_id if cue else -1,
            )
        return RowView(SHOW, check.state, tr("Spettacolo: {}").format(v.get("name", "")))

    # ── Page ──────────────────────────────────────────────────────────
    def _readiness_rows(self) -> list[Check]:
        return checks(self._readiness_facts())

    def _readiness_wanted(self) -> bool:
        """Show the page before entering? Never when it is turned off on this computer."""
        if not self._readiness_enabled():
            return False
        return self._readiness_full_due or bool(problems(self._readiness_rows()))

    def _readiness_starts(self) -> list[tuple[str, int]]:
        """The start question of C1 as buttons; one start when there is nothing to ask."""
        resume_id = getattr(self, "_live_resume_id", None)
        resume_row = next((i for i, c in enumerate(self._cues) if c.cue_id == resume_id), None) \
            if resume_id is not None else None
        target = self._go_target_index()
        choices = live_start_choices(len(self._cues), target, resume_row, self._show_running())
        labels = {START_FROM_TOP: "Dall'inizio: {}", START_RESUME: "Riprendi da: {}",
                  START_SELECTED: "Dalla cue selezionata: {}"}

        def ref(row: int) -> str:
            cue = self._cues[row]
            name = cue.name if len(cue.name) <= 40 else cue.name[:39] + "…"
            return f"{format_cue_ref(row, cue)} '{name}'"

        if choices:
            return [("▶ " + tr(labels[kind]).format(ref(row)), row) for kind, row in choices]
        if not self._cues:
            return []
        return [(tr("▶ Inizia: {}").format(ref(target)), target)]

    def _show_readiness(self, review: bool = False) -> None:
        """Put the page in place of the list (*review*: from the show, without starts)."""
        self._readiness_review = review
        self._readiness_signature = None
        self._readiness_refresh()
        self._central_stack.setCurrentWidget(self._readiness_page)
        if not review:
            self._mode_tabs.set_live(False)
        self._readiness_timer.start()
        default = self._readiness_page.default_button()
        (default or self._readiness_page).setFocus()

    def _readiness_refresh(self, rebuild: bool = True) -> None:
        rows = self._readiness_rows()
        shown = page_rows(rows, full=self._readiness_full_due or self._readiness_review)
        signature = tuple((c.key, c.state, tuple(sorted(c.values.items(), key=str)) if c.values else ())
                          for c in shown) + (self._readiness_tone_asked, self._readiness_review)
        signature = tuple(str(x) for x in signature)
        if not rebuild and signature == self._readiness_signature:
            return
        self._readiness_signature = signature
        focused = self._readiness_page.focusWidget()
        focus_action = next((a for a, b in self._readiness_page.row_buttons.items() if b is focused), None)
        bad = problems(rows)
        if bad:
            names = ", ".join(self._readiness_short(c.key) for c in bad)
            summary = tr("Problemi: {}. Puoi iniziare lo stesso.").format(names)
        elif any(c.state == SKIPPED for c in rows):
            names = ", ".join(self._readiness_short(c.key) for c in rows if c.state == SKIPPED)
            summary = tr("Pronto. Non verificato: {}.").format(names)
        else:
            summary = tr("Tutto pronto.")
        starts = [] if self._readiness_review else self._readiness_starts()
        stay = tr("Torna allo spettacolo") if self._readiness_review else tr("Resta in Preparazione")
        self._readiness_page.show_rows([self._readiness_view(c) for c in shown], summary, starts, stay,
                                       all_ok=not bad)
        if focus_action in self._readiness_page.row_buttons:
            self._readiness_page.row_buttons[focus_action].setFocus()
        self._update_readiness_warning(len(bad))

    def _readiness_short(self, key: str) -> str:
        return tr({SCREEN: "proiettore", VOLUME: "volume", SPEAKERS: "audio", MEDIA: "file",
                   POWER: "alimentatore", CHECKLIST: "checklist"}.get(key, key))

    def _update_readiness_warning(self, count: int | None = None) -> None:
        """"⚠ N" in the show while entered with problems (gone once they are fixed)."""
        panel = getattr(self, "_live_show_panel", None)
        if panel is None:
            return
        if not self._live_mode or not getattr(self, "_readiness_entered_with_problems", False):
            panel.set_readiness_warning(0)
            return
        if count is None:
            count = len(problems(self._readiness_rows()))
        panel.set_readiness_warning(count, tr("Controllo prima dello spettacolo: problemi: {}").format(count))

    # ── Answers ───────────────────────────────────────────────────────
    @Slot(int)
    def _on_readiness_start(self, row: int) -> None:
        """A start button: into the show from *row*, without asking again."""
        self._readiness_timer.stop()
        self._readiness_full_due = False
        self._readiness_entered_with_problems = bool(problems(self._readiness_rows()))
        if 0 <= row < len(self._cues):
            self._cue_list.setCurrentRow(row)
        logger.info("[READY] Show entered from row %d (problems: %s)", row,
                    self._readiness_entered_with_problems)
        self.set_live_mode(True, checked=True)
        self._update_readiness_warning()

    @Slot()
    def _on_readiness_stay(self) -> None:
        self._readiness_timer.stop()
        if self._readiness_review:
            self._readiness_review = False
            self._central_stack.setCurrentIndex(1 if self._live_mode else 0)
            if self._live_mode:
                self._live_show_panel.live_table.setFocus()
            return
        self._central_stack.setCurrentIndex(0)
        self._cue_list.setFocus()

    @Slot(int, int, bool)
    def _on_readiness_tick(self, cue_id: int, index: int, ticked: bool) -> None:
        self._on_note_item_toggled(cue_id, index, ticked)  # same ticks as the note zone
        self._readiness_refresh(rebuild=False)

    @Slot(str)
    def _on_readiness_action(self, action: str) -> None:
        if action == "recheck":
            self._readiness_refresh()
        elif action == "volume":
            self._set_master(level=1.0, muted=False)
            self._readiness_refresh()
        elif action == "tone":
            self._play_test_tone()
        elif action in ("heard_yes", "heard_no"):
            self._readiness_heard = action == "heard_yes"
            self._readiness_tone_asked = False
            self._readiness_refresh()
        elif action == "devices":
            self.open_device_settings_dialog()
            self._readiness_refresh()
        elif action == "screens":
            self._show_screen_numbers()
        elif action == "show_missing":
            row = next((i for i, c in enumerate(self._cues)
                        if c.media_type.has_file and not os.path.isfile(c.file_path or "")), -1)
            if not self._readiness_review:
                self._on_readiness_stay()  # files are replaced in Preparation
            if row >= 0 and not self._live_mode:
                self._cue_list.setCurrentRow(row)
        elif action == "add_checklist":
            self._add_default_checklist()
            self._readiness_refresh()

    def _play_test_tone(self) -> None:
        """1 s chime through the show's speakers and master volume; never while something plays."""
        if self._readiness_facts().playing:
            self._readiness_refresh()
            return
        from PySide6.QtCore import QStandardPaths, QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "test_tone.wav"
        if not path.is_file():
            _write_test_tone(path)
        if self._tone_player is None:
            self._tone_output = QAudioOutput(self)
            self._tone_player = QMediaPlayer(self)
            self._tone_player.setAudioOutput(self._tone_output)
        dm = getattr(self, "_device_mgr", None)
        if dm is not None and dm.get_master_audio_device() is not None:
            self._tone_output.setDevice(dm.get_master_audio_device())
        self._tone_output.setVolume(0.0 if self._master_muted else self._master_level)
        self._tone_player.setSource(QUrl.fromLocalFile(str(path)))
        self._tone_player.play()
        self._readiness_tone_asked = True
        logger.info("[READY] Test tone played")
        self._readiness_refresh()

    def _show_screen_numbers(self) -> None:
        """A big number and the name on every screen for 3 s."""
        from PySide6.QtGui import QGuiApplication

        windows = []
        for i, screen in enumerate(QGuiApplication.screens(), start=1):
            label = QLabel(f"{i}\n{screen.manufacturer()} {screen.model()}".strip())
            label.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                                 | Qt.WindowType.Tool)
            label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("QLabel { background-color: #0f172a; color: #fbbf24; font-size: 72px; "
                                "font-weight: bold; border: 4px solid #fbbf24; }")
            geo = screen.geometry()
            label.setGeometry(geo.x() + geo.width() // 2 - 200, geo.y() + geo.height() // 2 - 150, 400, 300)
            label.show()
            windows.append(label)
        self._screen_number_windows = windows
        QTimer.singleShot(3000, lambda: [w.close() for w in windows])

    # ── Default checklist ─────────────────────────────────────────────
    def _default_checklist_cue(self) -> Cue:
        return Cue(
            name=tr(DEFAULT_CHECKLIST_NAME),
            media_type=MediaType.ACTION,
            file_path="",
            action_spec={"kind": "checklist", "target": "all", "items": [tr(i) for i in DEFAULT_CHECKLIST]},
        )

    def _add_default_checklist(self) -> None:
        """Sterowanie → "Add the default checklist": at the top of the list (Preparation only)."""
        if not self._change_allowed(EDIT_LIST):
            return
        cue = self._default_checklist_cue()
        cue.status = CueStatus.LOADED
        self._cues.insert(0, cue)
        self._refresh_cue_list(keep_selection=False)
        self._cue_list.setCurrentRow(0)
        self._commit_undo_point()
        self._mark_modified(True)
        self._status_label.setText(tr("Checklist predefinita aggiunta in cima alla scaletta"))
