"""Test funzionali della logica di spettacolo (show engine) – headless.

Coprono il comportamento che va in scena, finora non verificato dai test di
robustezza/infrastruttura:

  1. GO / catena SIMULTANEOUS / standby successivo
  2. Spegnimento del cue precedente sullo stesso layer
  3. Pre-delay: il cue viene emesso ma NON marcato LIVE
  4. Cue di gruppo: SIMULTANEOUS, SEQUENCE, STEP, RANDOM, gruppo vuoto
  5. Gruppo compresso: espansione automatica al GO
  6. Indici fuori range e scaletta vuota non devono mai essere fatali
  7. ShowScheduler: completamento PRE/POST, pausa globale senza drift
  8. SectionSequencer: vamp infinito, loop N, transizioni contigue, skip, EOF
  9. Envelope/fade: valutazione livelli e curve

Nessun media reale viene aperto: si verifica la macchina a stati e il calcolo,
non il pipeline video/audio (già coperto dai test di integrazione).

Esecuzione:
    QT_QPA_PLATFORM=offscreen pytest -q tests/test_show_engine.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine.envelope import (  # noqa: E402
    SectionSequencer,
    apply_fade_curve,
    evaluate_cue_level,
    evaluate_points_envelope,
    normalize_sections,
)
from engine.show_scheduler import ShowScheduler  # noqa: E402
from models.cue import Cue, CueSection, CueStatus, FollowMode, GroupMode, MediaType  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def show_window(qt_app, tmp_path):
    """MainWindow + OutputWindow headless, senza autosave su disco reale."""
    try:
        from ui.main_window import MainWindow
        from ui.output_window import OutputWindow
        output = OutputWindow()
        win = MainWindow(output)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MainWindow non istanziabile in ambiente headless: {exc}")

    # L'autosave asincrono è già coperto altrove: qui isoliamo la macchina a stati.
    win._auto_save = lambda: None
    win._cues.clear()
    win._current_index = 0
    try:
        yield win
    finally:
        win._force_closing = True
        output.force_close()
        win.close()
        win.deleteLater()
        output.deleteLater()
        QCoreApplication.processEvents()


# ── Helper ─────────────────────────────────────────────────────────────

def _cue(
    cue_id: int,
    name: str = "Cue",
    *,
    layer: int = 1,
    media_type: MediaType = MediaType.AUDIO,
    follow: FollowMode = FollowMode.MANUAL,
    pre_delay: float = 0.0,
    parent_id: int | None = None,
    group_mode: GroupMode = GroupMode.STEP,
    collapsed: bool = False,
) -> Cue:
    return Cue.from_dict(
        {
            "cue_id": cue_id,
            "name": name,
            "media_type": media_type.value,
            "file_path": f"/nonexistent/{name}.wav",
            "layer": layer,
            "follow_mode": follow.value,
            "pre_delay": pre_delay,
            "parent_id": parent_id,
            "group_mode": group_mode.value,
            "collapsed": collapsed,
        }
    )


def _load(win, cues: list[Cue]) -> list[int]:
    """Installa la scaletta e cattura gli ID emessi via cue_fired."""
    win._cues.clear()
    win._cues.extend(cues)
    win._refresh_cue_list(keep_selection=False)
    emitted: list[int] = []
    win.cue_fired.connect(lambda cue: emitted.append(cue.cue_id))
    return emitted


# ── 1. GO e catena SIMULTANEOUS ────────────────────────────────────────

def test_manual_go_fires_one_cue_and_advances_standby(show_window):
    win = show_window
    emitted = _load(win, [_cue(1, "A"), _cue(2, "B"), _cue(3, "C")])

    win._fire_cue_chain(0)

    assert emitted == [1], "un cue MANUAL deve emettere un solo cue"
    assert win._cues[0].status == CueStatus.LIVE
    assert win._cues[1].status != CueStatus.LIVE
    # Selezione e indice corrente si spostano sul cue di standby.
    assert win._current_index == 1
    assert win._cue_list.currentRow() == 1


def test_simultaneous_chain_fires_whole_chain_then_stands_by(show_window):
    win = show_window
    emitted = _load(
        win,
        [
            _cue(1, "A", follow=FollowMode.SIMULTANEOUS),
            _cue(2, "B", follow=FollowMode.SIMULTANEOUS),
            _cue(3, "C"),
        ],
    )

    win._fire_cue_chain(0)

    assert emitted == [1, 2, 3] or emitted == [1, 2], (
        f"catena simultanea inattesa: {emitted}"
    )
    assert 1 in emitted and 2 in emitted
    # La catena arriva a fine scaletta: la selezione resta sull'ultimo cue.
    assert win._cue_list.currentRow() == len(win._cues) - 1


def test_simultaneous_chain_at_end_of_show_does_not_overflow(show_window):
    win = show_window
    cues = [_cue(i, f"C{i}", follow=FollowMode.SIMULTANEOUS) for i in range(1, 6)]
    emitted = _load(win, cues)

    win._fire_cue_chain(0)  # non deve sollevare eccezioni

    assert len(emitted) == 5
    assert win._cue_list.currentRow() == len(cues) - 1


def test_firing_new_cue_on_same_layer_demotes_previous_live(show_window):
    win = show_window
    _load(win, [_cue(1, "A", layer=1), _cue(2, "B", layer=1)])

    win._fire_cue_chain(0)
    assert win._cues[0].status == CueStatus.LIVE

    win._fire_cue_chain(1)
    assert win._cues[0].status == CueStatus.LOADED, "il cue precedente deve tornare LOADED"
    assert win._cues[1].status == CueStatus.LIVE


def test_pre_delay_cue_is_emitted_but_not_marked_live(show_window):
    win = show_window
    emitted = _load(win, [_cue(1, "Late", pre_delay=2.0)])

    win._fire_cue_chain(0)

    assert emitted == [1], "il cue con pre-delay deve comunque essere emesso"
    assert win._cues[0].status != CueStatus.LIVE, (
        "un cue in attesa di pre-delay non deve risultare LIVE"
    )


def test_empty_show_go_is_harmless(show_window):
    win = show_window
    win._cues.clear()
    win._on_go()  # non deve sollevare eccezioni
    assert win._cues == []


def test_out_of_range_fire_is_noop(show_window):
    win = show_window
    emitted = _load(win, [_cue(1, "A")])

    win._fire_cue_chain(-1)
    win._fire_cue_chain(99)

    assert emitted == []
    assert win._cues[0].status != CueStatus.LIVE


# ── 4. Cue di gruppo ───────────────────────────────────────────────────

def _group_show(win, mode: GroupMode, n_children: int = 3) -> list[int]:
    group = _cue(1, "GRP", media_type=MediaType.GROUP, group_mode=mode)
    # Figli su layer distinti: è l'uso reale di un gruppo SIMULTANEO
    # (tre proiezioni contemporanee, una per layer).
    children = [
        _cue(10 + i, f"K{i}", layer=min(3, i + 1), parent_id=1) for i in range(n_children)
    ]
    return _load(win, [group, *children])


def test_group_simultaneous_fires_every_child(show_window):
    win = show_window
    emitted = _group_show(win, GroupMode.SIMULTANEOUS)

    win._fire_cue_chain(0)

    assert sorted(emitted) == [10, 11, 12]
    for child in win._cues[1:]:
        assert child.status == CueStatus.LIVE


def test_group_container_keeps_live_badge_while_children_play(show_window):
    """Regressione: il contenitore GROUP non deve essere declassato a LOADED
    dal primo figlio che va in onda sullo stesso layer."""
    win = show_window
    _group_show(win, GroupMode.SIMULTANEOUS)

    win._fire_cue_chain(0)

    assert win._cues[0].status == CueStatus.LIVE, (
        "il cue di gruppo deve restare LIVE mentre i figli sono in onda"
    )


def test_group_sequence_fires_only_first_child(show_window):
    win = show_window
    emitted = _group_show(win, GroupMode.SEQUENCE)

    win._fire_cue_chain(0)

    assert emitted == [10]
    # Lo standby deve passare al secondo figlio del gruppo.
    assert win._cue_list.currentRow() == 2


def test_group_step_fires_only_first_child(show_window):
    win = show_window
    emitted = _group_show(win, GroupMode.STEP)

    win._fire_cue_chain(0)

    assert emitted == [10]


def test_group_random_fires_exactly_one_child_of_the_group(show_window):
    win = show_window
    emitted = _group_show(win, GroupMode.RANDOM, n_children=5)

    win._fire_cue_chain(0)

    assert len(emitted) == 1, "RANDOM deve scegliere un solo figlio"
    assert emitted[0] in {10, 11, 12, 13, 14}


def test_group_without_children_advances_without_crash(show_window):
    win = show_window
    emitted = _load(
        win,
        [
            _cue(1, "EmptyGRP", media_type=MediaType.GROUP, group_mode=GroupMode.STEP),
            _cue(2, "After"),
        ],
    )

    win._fire_cue_chain(0)

    assert emitted == []
    assert win._cue_list.currentRow() == 1, "deve avanzare al cue successivo al gruppo"


def test_firing_child_of_collapsed_group_expands_it(show_window):
    win = show_window
    group = _cue(1, "GRP", media_type=MediaType.GROUP, group_mode=GroupMode.STEP, collapsed=True)
    child = _cue(2, "K1", parent_id=1)
    emitted = _load(win, [group, child])

    win._fire_cue_chain(1)  # GO direttamente sul figlio compresso

    assert emitted == [2]
    assert win._cues[0].collapsed is False, "il gruppo deve espandersi automaticamente"


# ── 7. ShowScheduler: pre/post delay e pausa ──────────────────────────

def test_scheduler_pre_delay_completes_once(qt_app):
    sched = ShowScheduler()
    cue = Cue.from_dict(
        {"cue_id": 1, "name": "X", "media_type": MediaType.AUDIO.value, "file_path": "/x"}
    )
    finished: list[str] = []
    sched.window_finished.connect(lambda w: finished.append(w.phase))

    sched.schedule("PRE", cue, 1, 0.5, generation=7)
    assert sched.has_pending()

    sched.step_for_test(0.2)
    assert finished == [], "non deve terminare prima del tempo"
    assert sched.pending_for_layer(1, "PRE") is not None

    sched.step_for_test(0.4)
    assert finished == ["PRE"], "il pre-delay deve emettere window_finished una sola volta"
    assert not sched.has_pending()


def test_scheduler_global_pause_freezes_timer(qt_app):
    sched = ShowScheduler()
    cue = Cue.from_dict(
        {"cue_id": 1, "name": "X", "media_type": MediaType.AUDIO.value, "file_path": "/x"}
    )
    finished: list[str] = []
    sched.window_finished.connect(lambda w: finished.append(w.phase))

    sched.schedule("PRE", cue, 1, 1.0)
    sched.step_for_test(0.5)

    sched.set_paused(True)
    sched.step_for_test(10.0)  # ignorato mentre è in pausa
    assert finished == [], "in pausa il countdown non deve avanzare"

    sched.set_paused(False)
    sched.step_for_test(0.6)
    assert finished == ["PRE"], "alla ripresa deve ripartire dal tempo residuo"


def test_scheduler_cancel_all_on_panic_drops_every_window(qt_app):
    sched = ShowScheduler()
    cue = Cue.from_dict(
        {"cue_id": 1, "name": "X", "media_type": MediaType.AUDIO.value, "file_path": "/x"}
    )
    sched.schedule("PRE", cue, 1, 5.0)
    sched.schedule("POST", cue, 2, 5.0)
    assert sched.has_pending()

    sched.cancel_all()
    assert not sched.has_pending()


# ── 8. SectionSequencer ───────────────────────────────────────────────

def _seq(*sections: CueSection, end: float = 10.0) -> SectionSequencer:
    seq = SectionSequencer()
    seq.configure(list(sections), 0.0, end)
    return seq


def test_contiguous_sections_advance_without_seek(qt_app):
    seq = _seq(
        CueSection(label="A", start=0.0, end=5.0),
        CueSection(label="B", start=5.0, end=10.0),
    )
    assert seq.active is True

    action, idx, target = seq.advance_at_boundary()
    assert action == "CONTINUE", "sezioni contigue non devono richiedere seek"
    assert idx == 1 and target is None

    action, idx, target = seq.advance_at_boundary()
    assert action == "EOF" and idx is None


def test_infinite_vamp_stays_on_section(qt_app):
    seq = _seq(
        CueSection(label="VAMP", start=0.0, end=4.0, loops=0),
        CueSection(label="END", start=4.0, end=10.0),
    )
    for _ in range(5):
        action, idx, target = seq.advance_at_boundary()
        assert action == "JUMP"
        assert idx == 0, "un vamp infinito non deve abbandonare la sezione"
        assert target == 0.0


def test_loop_count_advances_after_n_iterations(qt_app):
    seq = _seq(
        CueSection(label="L", start=0.0, end=4.0, loops=2),
        CueSection(label="R", start=4.0, end=10.0),
    )
    assert seq.advance_at_boundary()[0] == "JUMP"      # iterazione 2
    action, idx, _ = seq.advance_at_boundary()          # esaurito: avanza
    assert action == "CONTINUE" and idx == 1


def test_skipped_section_is_never_played(qt_app):
    seq = _seq(
        CueSection(label="A", start=0.0, end=3.0),
        CueSection(label="SKIP", start=3.0, end=6.0, skip=True),
        CueSection(label="C", start=6.0, end=10.0),
    )
    action, idx, target = seq.advance_at_boundary()
    assert action == "JUMP" and idx == 2 and target == 6.0, (
        "una sezione saltata deve essere scavalcata con un seek"
    )


def test_jump_to_invalid_section_returns_none(qt_app):
    seq = _seq(CueSection(label="A", start=0.0, end=5.0))
    assert seq.jump_to(-1) is None
    assert seq.jump_to(99) is None


def test_single_section_is_not_active(qt_app):
    seq = _seq(CueSection(label="A", start=0.0, end=10.0))
    assert seq.active is False
    assert seq.peek_next_jump_target() is None


def test_normalize_sections_orders_and_clamps(qt_app):
    secs = normalize_sections(
        [
            CueSection(label="B", start=8.0, end=99.0),
            CueSection(label="A", start=-5.0, end=8.0),
        ],
        0.0,
        10.0,
    )
    assert len(secs) == 2
    assert secs[0].start == 0.0
    # L'ultima sezione resta volutamente "aperta" (end=None): il fondo reale
    # è eff_end, valutato a runtime dal sequencer.
    assert secs[-1].end is None
    assert secs[0].end == secs[1].start


# ── 9. Envelope e fade ────────────────────────────────────────────────

def test_points_envelope_interpolates_and_clamps(qt_app):
    pts = [[0.0, 0.0], [10.0, 1.0]]
    assert evaluate_points_envelope(-1.0, pts, 0.5) == pytest.approx(0.0)
    assert evaluate_points_envelope(5.0, pts, 0.5) == pytest.approx(0.5)
    assert evaluate_points_envelope(99.0, pts, 0.5) == pytest.approx(1.0)
    assert evaluate_points_envelope(5.0, [], 0.42) == pytest.approx(0.42)


def test_fade_curves_are_monotonic_and_bounded(qt_app):
    prev = -1.0
    for step in range(11):
        val = apply_fade_curve(step / 10.0, "log")
        assert 0.0 <= val <= 1.0
        assert val >= prev, "la curva di fade-in deve essere monotona"
        prev = val


def test_cue_level_respects_in_and_out_fade(qt_app):
    kwargs = dict(
        start_sec=0.0,
        end_sec=10.0,
        duration_sec=10.0,
        fade_in=2.0,
        fade_out=2.0,
        fade_curve="linear",
        points=[],
        base_level=1.0,
    )
    assert evaluate_cue_level(0.0, **kwargs) == pytest.approx(0.0)
    assert evaluate_cue_level(5.0, **kwargs) == pytest.approx(1.0)
    assert evaluate_cue_level(10.0, **kwargs) == pytest.approx(0.0)
    assert 0.0 < evaluate_cue_level(1.0, **kwargs) < 1.0
