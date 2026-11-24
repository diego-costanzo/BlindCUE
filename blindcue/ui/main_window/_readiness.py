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
import shutil
import struct
import wave
from datetime import datetime
from pathlib import Path

from engine.readiness import (
    AUDIO_OUTS,
    CLOCK,
    DISK,
    LIST,
    VERSION,
    EARCONS,
    INFO,
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
from models.cue import is_placeholder

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
        self._readiness_timer = QTimer(self)
        self._readiness_timer.setInterval(2000)  # the power row changes by itself
        self._readiness_timer.timeout.connect(
            lambda: self._readiness_refresh(rebuild=False) if self._readiness_visible()
            else self._readiness_timer.stop())
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
        earcons = getattr(self, "_earcon_mgr", None)
        headphones = earcons is not None and not earcons.on_audience_speakers()
        # 3.4: a placeholder (sound without a file yet) is listed under "to fix in the list", not as missing
        with_files = [(i, c) for i, c in enumerate(self._cues) if c.media_type.has_file and not is_placeholder(c)]
        missing = tuple(f"{format_cue_ref(i, c)} '{c.name}'" for i, c in with_files
                        if not os.path.isfile(c.file_path or ""))
        path = getattr(self, "_current_project_path", None)
        show = Path(path).stem if path else tr("(non salvato)")
        if self._is_modified:
            show += " · " + tr("modifiche non salvate")
        playing = any(c.status == CueStatus.LIVE for c in self._cues) or bool(self._live_phase_tags)
        from engine.list_check import list_problems

        wrong = tuple(f"{format_cue_ref(i, self._cues[i])} '{self._cues[i].name}': {self._list_problem_text(kind)}"
                      for i, kind in list_problems(self._cues))
        try:
            free_mb = shutil.disk_usage(Path(path).parent if path else Path.home()).free // (1024 * 1024)
        except OSError:
            free_mb = None
        timed = sum(1 for c in self._cues if getattr(c, "start_clock", "") and getattr(c, "enabled", True))
        return Facts(
            list_problems=wrong, version=getattr(self, "_version_name", ""),
            switched_off=sum(1 for c in self._cues if not getattr(c, "enabled", True)),
            disk_free_mb=free_mb, timed=timed, clock=datetime.now().strftime("%H:%M"),
            outputs=self._readiness_outputs(dm),
            screen_name=name, screen_external=external, screen_count=count,
            master_level=self._master_level, master_muted=self._master_muted,
            speakers=speakers, speakers_pinned=pinned, speakers_missing=missing_dev,
            heard=self._readiness_heard, playing=playing,
            missing=missing, media_total=len(with_files),
            power=power_status(), show_name=show,
            earcons_on=bool(earcons is not None and earcons.enabled), headphones=headphones,
        )

    def _readiness_outputs(self, dm) -> tuple[tuple[str, str, bool, int], ...]:
        """3.1: where the hall and the foldback used by this show play now."""
        from engine.audio_routes import LABELS

        if dm is None or not hasattr(dm, "resolve_output"):
            return ()
        rows = []
        audience = {bytes(d.id()) for d in dm.audience_devices()}
        for key in ("hall", "foldback"):
            n = sum(1 for c in self._cues if getattr(c, "audio_output", "stage") == key
                    and c.media_type in (MediaType.AUDIO, MediaType.VIDEO))
            if not n:
                continue
            route = dm.resolve_output(key)
            where = (tr("muto") if route.muted else route.device.description() if route.device is not None
                     else tr("uscita predefinita"))
            own = route.via == key
            if key == "foldback" and own and bytes(dm.route_device(route).id()) in audience:
                own, where = False, where + " – " + tr("lo stesso dispositivo del pubblico")
            rows.append((tr(LABELS[key]), where, own, n))
        return tuple(rows)

    @staticmethod
    def _list_problem_text(kind: str) -> str:
        from engine import list_check as lc

        return {
            lc.REL_MISSING: tr("parte dopo una cue che non c'è più"),
            lc.NO_TARGET: tr("le sue cue bersaglio non ci sono più: non fa nulla"),
            lc.JUMP_NOWHERE: tr("salta o chiama una cue che non c'è"),
            lc.EMPTY_SCENE: tr("scena senza nulla da suonare"),
            lc.NEVER_CALLED: tr("parte solo se chiamata, ma nessuna azione la chiama"),
            lc.PICTURE_TOO_SHORT: tr("immagine sullo schermo meno dei suoi passaggi + 0,5 s"),
            lc.PLACEHOLDER: tr("ancora senza file: al GO non suona"),  # 3.4
        }.get(kind, kind)

    def _readiness_view(self, check: Check) -> RowView:
        v = check.values
        if check.key == LIST:
            shown = "; ".join(v["items"][:3]) + (" …" if len(v["items"]) > 3 else "")
            return RowView(LIST, PROBLEM, tr("Da sistemare nella lista ({}): {}").format(v["count"], shown),
                           [(tr("Mostra nella lista"), "show_list_problem")])
        if check.key == CLOCK:
            return RowView(CLOCK, INFO, tr(
                "Cue a un'ora del giorno: {} – l'orologio del computer segna {}. È giusto?"
            ).format(v["count"], v["time"]))
        if check.key == DISK:
            return RowView(DISK, PROBLEM, tr(
                "Poco spazio libero sul disco dello spettacolo: {} MB – il salvataggio può non riuscire"
            ).format(v["mb"]))
        if check.key == VERSION:
            name = v["name"] or tr("Spettacolo completo")
            return RowView(VERSION, INFO, tr("Versione: {} · {} cue escluse").format(name, v["off"]))
        if check.key == AUDIO_OUTS:
            parts = " · ".join(f"{label} ({n}) → {where}" for label, where, _own, n in v["rows"])
            if check.state == OK:
                return RowView(AUDIO_OUTS, OK, tr("Uscite audio: {}").format(parts))
            return RowView(AUDIO_OUTS, PROBLEM, tr("Uscite audio non impostate o scollegate: {}").format(parts),
                           [(tr("Uscite audio…"), "outputs")])
        if check.key == SCREEN:
            if check.state == OK:
                # "Found" is not "seen": wrong HDMI input, lens cap, focus (GUI review 2026-11-24).
                pattern = (tr("▦ Nascondi la mira") if self._readiness_pattern_on()
                           else tr("▦ Mostra la mira sul proiettore"))
                return RowView(SCREEN, OK, tr("Immagine: {}").format(v["name"]), [(pattern, "pattern")])
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
                           [(tr("Mostra nella lista"), "show_missing"),
                            (tr("🔎 Cerca in una cartella…"), "find_missing")])  # 5.10
        if check.key == POWER:
            if check.state == OK:
                return RowView(POWER, OK, tr("Portatile collegato all'alimentatore"))
            return RowView(POWER, PROBLEM, tr("Portatile a batteria ({} %): collega l'alimentatore").format(
                v["percent"]))
        if check.key == EARCONS:
            if v.get("offer"):
                return RowView(EARCONS, check.state, tr(
                    "Cuffie collegate: i suoni per la regia sono spenti (GO, blocchi, cambio di modalità)"),
                    [(tr("Accendi"), "earcons_on")])
            return RowView(EARCONS, check.state, tr(
                "I suoni per la regia tacciono: le cuffie sono le casse del pubblico"))
        changes = len(self._rehearsal_changes())
        if changes:
            return RowView(SHOW, check.state, tr("Spettacolo: {} · modifiche della prova: {}").format(
                v.get("name", ""), changes), [(tr("Rivedi"), "review_changes")])
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
        target = self._go_target_index()
        if self._live_mode:
            # From the rehearsal: the show goes on where the GO points now.
            cue = self._cues[target] if 0 <= target < len(self._cues) else None
            return [(tr("▶ Inizia: {}").format(f"{format_cue_ref(target, cue)} '{cue.name}'"), target)] \
                if cue is not None else []
        resume_id = getattr(self, "_live_resume_id", None)
        resume_row = next((i for i, c in enumerate(self._cues) if c.cue_id == resume_id), None) \
            if resume_id is not None else None
        choices = live_start_choices(len(self._cues), target, resume_row, self._show_running())
        labels = {START_FROM_TOP: "Dall'inizio: {}", START_RESUME: "Riprendi da: {}",
                  START_SELECTED: "Dalla cue selezionata: {}"}

        def ref(row: int) -> str:
            cue = self._cues[row]
            name = cue.name if len(cue.name) <= 40 else cue.name[:39] + "…"
            return f"{format_cue_ref(row, cue)} '{name}'"

        def first_cue(row: int) -> int:
            # A cue GO skips (an old checklist on top, an effect…) is not where the show starts.
            from engine.show_engine import outside_go_order

            while row < len(self._cues) - 1 and outside_go_order(self._cues[row]):
                row += 1
            return row

        if choices:
            return [("▶ " + tr(labels[kind]).format(ref(first_cue(row) if kind == START_FROM_TOP else row)),
                     first_cue(row) if kind == START_FROM_TOP else row) for kind, row in choices]
        if not self._cues:
            return []
        target = first_cue(target) if target == 0 else target
        return [(tr("▶ Inizia: {}").format(ref(target)), target)]

    def _show_readiness(self, review: bool = False) -> None:
        """Put the page in place of the list (*review*: from the show, without starts)."""
        self._readiness_review = review
        self._readiness_signature = None
        self._readiness_refresh()
        self._central_stack.setCurrentWidget(self._readiness_page)
        # The show page has its own top bar: over this page the editor's bar
        # (mode tabs, Fade All, PANIC) stays in sight.
        self._design_control_bar.setVisible(True)
        if not review:
            self._mode_tabs.set_mode(self._current_mode())
        self._readiness_timer.start()
        default = self._readiness_page.default_button()
        (default or self._readiness_page).setFocus()

    def _readiness_refresh(self, rebuild: bool = True) -> None:
        rows = self._readiness_rows()
        shown = page_rows(rows, full=self._readiness_full_due or self._readiness_review)
        signature = tuple((c.key, c.state, tuple(sorted(c.values.items(), key=str)) if c.values else ())
                          for c in shown) + (self._readiness_tone_asked, self._readiness_review,
                                             self._readiness_pattern_on())
        signature = tuple(str(x) for x in signature)
        if not rebuild and signature == self._readiness_signature:
            return
        self._readiness_signature = signature
        focused = self._readiness_page.focusWidget()
        focus_action = next((a for a, b in self._readiness_page.row_buttons.items() if b is focused), None)
        focus_box = next((k for k, b in self._readiness_page.checkboxes.items() if b is focused), None)
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
        elif focus_box in self._readiness_page.checkboxes:
            self._readiness_page.checkboxes[focus_box].setFocus()
        self._update_readiness_warning(len(bad))

    def _readiness_short(self, key: str) -> str:
        return tr({SCREEN: "proiettore", VOLUME: "volume", SPEAKERS: "audio", MEDIA: "file",
                   POWER: "alimentatore", AUDIO_OUTS: "uscite audio"}.get(key, key))

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
        if self._readiness_pattern_on():
            self._toggle_calibration_guides(False)  # never in front of the audience
        self._readiness_entered_with_problems = bool(problems(self._readiness_rows()))
        if 0 <= row < len(self._cues):
            self._cue_list.setCurrentRow(row)
        logger.info("[READY] Show entered from row %d (problems: %s)", row,
                    self._readiness_entered_with_problems)
        if self._live_mode:
            # From the rehearsal: the same screen, now the show.
            self._rehearsal = False
            self._close_drawer()
            self._central_stack.setCurrentIndex(1)
            self._design_control_bar.setVisible(False)
            self._apply_mode_visuals()
            self._status_label.setText("MODALITÀ LIVE ATTIVA — Interfaccia semplificata per la regia [ESC ×2 = PANIC]")
            self.announce(self._status_label.text(), assertive=True)
            self._live_show_panel.live_table.setFocus()
        else:
            self.set_live_mode(True, checked=True)
        self._update_readiness_warning()

    @Slot()
    def _on_readiness_stay(self) -> None:
        self._readiness_timer.stop()
        self._readiness_review = False
        if self._live_mode:
            # Back to the show's screen (the review from the show, or the rehearsal).
            self._central_stack.setCurrentIndex(1)
            self._design_control_bar.setVisible(False)
            self._apply_mode_visuals()
            self._live_show_panel.live_table.setFocus()
            return
        self._central_stack.setCurrentIndex(0)
        self._apply_mode_visuals()
        self._cue_list.setFocus()

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
        elif action == "outputs":
            self.open_audio_outputs_dialog()
            self._readiness_refresh()
        elif action == "screens":
            self._show_screen_numbers()
        elif action == "pattern":
            self._toggle_calibration_guides(not self._readiness_pattern_on())
            self._readiness_refresh()
        elif action == "show_missing":
            row = next((i for i, c in enumerate(self._cues)
                        if c.media_type.has_file and not os.path.isfile(c.file_path or "")
                        and not is_placeholder(c)), -1)  # 3.4
            if not self._readiness_review:
                self._on_readiness_stay()  # files are replaced in Preparation
            if row >= 0 and not self._live_mode:
                self._cue_list.setCurrentRow(row)
        elif action == "find_missing":
            if not self._readiness_review:
                self._on_readiness_stay()  # files are replaced in Preparation
            self._find_missing_files()
        elif action == "show_list_problem":
            from engine.list_check import list_problems

            found = list_problems(self._cues)
            if not self._readiness_review:
                self._on_readiness_stay()  # the list is fixed in Preparation
            if found and not self._live_mode:
                self._cue_list.setCurrentRow(found[0][0])
        elif action == "earcons_on":
            self._set_earcons_enabled(True)
            if hasattr(self, "_act_earcons"):
                self._act_earcons.setChecked(True)
            self._readiness_refresh()
        elif action == "review_changes":
            self._review_rehearsal_changes()

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

    def _readiness_pattern_on(self) -> bool:
        output = getattr(self, "_output", None)
        return bool(output is not None and output.is_calibration_guides_visible())

    def _show_screen_numbers(self) -> None:
        """A big number and the name on every screen (4.5, the same as Devices → Identify)."""
        from PySide6.QtGui import QGuiApplication

        from ui.identify_screens import show_screen_numbers

        self._screen_number_windows = show_screen_numbers(QGuiApplication.screens())
