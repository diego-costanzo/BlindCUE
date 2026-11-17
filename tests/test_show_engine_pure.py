"""Unit test per la macchina a stati pura dello show (nessuna Qt).

``engine.show_engine`` non importa PySide6, quindi questi test girano senza
QApplication e senza ambiente grafico: verificano direttamente le transizioni
di stato che alimentano GO, catene simultanee, gruppi, blackout e auto-follow.

Esecuzione:
    pytest -q tests/test_show_engine_pure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "blindcue"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from engine.show_engine import (
    ShowEngine,
    chain_indices,
    demote_live_on_layer,
)
from models.cue import Cue, CueStatus, FollowMode, GroupMode, MediaType


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
        }
    )


# ── demote_live_on_layer ──────────────────────────────────────────────

def test_demote_skips_group_containers():
    media = _cue(1, "A", layer=1)
    group = _cue(2, "GRP", layer=1, media_type=MediaType.GROUP)
    other = _cue(3, "B", layer=1)
    media.status = CueStatus.LIVE
    group.status = CueStatus.LIVE
    other.status = CueStatus.LIVE

    demote_live_on_layer([media, group, other], layer=1, keep_cue_id=1)

    assert media.status == CueStatus.LIVE, "il cue da tenere resta LIVE"
    assert group.status == CueStatus.LIVE, "il contenitore GROUP non va declassato"
    assert other.status == CueStatus.LOADED


# ── chain_indices ─────────────────────────────────────────────────────

def test_chain_manual_stops_at_one():
    cues = [_cue(1, "A"), _cue(2, "B")]
    assert chain_indices(cues, 0) == [0]


def test_chain_simultaneous_extends_until_manual():
    cues = [
        _cue(1, "A", follow=FollowMode.SIMULTANEOUS),
        _cue(2, "B", follow=FollowMode.SIMULTANEOUS),
        _cue(3, "C"),
    ]
    assert chain_indices(cues, 0) == [0, 1, 2]


def test_chain_out_of_range_is_empty():
    assert chain_indices([_cue(1)], 5) == []
    assert chain_indices([], 0) == []


# ── children_of / next_standby_index ──────────────────────────────────

def test_children_of_filters_by_parent():
    group = _cue(1, "GRP", media_type=MediaType.GROUP)
    a = _cue(2, "A", parent_id=1)
    b = _cue(3, "B", parent_id=1)
    c = _cue(4, "C")
    assert ShowEngine.children_of([group, a, b, c], 1) == [a, b]


def test_next_standby_index_mid_show_and_end():
    cues = [_cue(i, f"C{i}") for i in range(1, 4)]
    assert ShowEngine.next_standby_index(cues, 0) == 1
    assert ShowEngine.next_standby_index(cues, 2) == 2  # fine scaletta: resta sull'ultimo


# ── promote_to_live ───────────────────────────────────────────────────

def test_promote_demotes_previous_live_on_same_layer():
    a = _cue(1, "A", layer=1)
    b = _cue(2, "B", layer=1)
    a.status = CueStatus.LIVE

    ShowEngine.promote_to_live([a, b], b)

    assert a.status == CueStatus.LOADED
    assert b.status == CueStatus.LIVE


def test_promote_does_not_touch_other_layers():
    a = _cue(1, "A", layer=1)
    b = _cue(2, "B", layer=2)
    a.status = CueStatus.LIVE

    ShowEngine.promote_to_live([a, b], b)

    assert a.status == CueStatus.LIVE
    assert b.status == CueStatus.LIVE


# ── demote_all_live / clear_layer ─────────────────────────────────────

def test_demote_all_live_only_touches_live():
    a = _cue(1, "A")
    b = _cue(2, "B")
    c = _cue(3, "C")
    a.status = CueStatus.LIVE
    c.status = CueStatus.LIVE

    ShowEngine.demote_all_live([a, b, c])

    assert a.status == CueStatus.LOADED
    assert b.status == CueStatus.OFFLINE, "i cue mai LIVE restano invariati"
    assert c.status == CueStatus.LOADED


def test_clear_layer_only_demotes_that_layer():
    a = _cue(1, "A", layer=1)
    b = _cue(2, "B", layer=2)
    a.status = CueStatus.LIVE
    b.status = CueStatus.LIVE

    ShowEngine.clear_layer([a, b], layer=1)

    assert a.status == CueStatus.LOADED
    assert b.status == CueStatus.LIVE


# ── auto_follow_target ────────────────────────────────────────────────

def test_auto_follow_returns_next_or_negative():
    cues = [_cue(i, f"C{i}") for i in range(1, 4)]
    assert ShowEngine.auto_follow_target(cues, cues[0]) == 1
    assert ShowEngine.auto_follow_target(cues, cues[2]) == -1
    assert ShowEngine.auto_follow_target(cues, _cue(99, "Ghost")) == -1


def test_group_mode_of_resolves_container():
    group = _cue(10, "SEQ", media_type=MediaType.GROUP,
                 group_mode=GroupMode.SEQUENCE)
    kid = _cue(11, "k1", parent_id=10)
    plain = _cue(12, "plain")
    cues = [group, kid, plain]

    assert ShowEngine.group_mode_of(cues, kid) == GroupMode.SEQUENCE.value
    assert ShowEngine.group_mode_of(cues, plain) == ""


def test_sequence_group_cascades_to_next_child():
    group = _cue(10, "SEQ", media_type=MediaType.GROUP,
                 group_mode=GroupMode.SEQUENCE)
    kids = [_cue(11, "k1", parent_id=10), _cue(12, "k2", parent_id=10),
            _cue(13, "k3", parent_id=10)]
    cues = [group, *kids]

    assert ShowEngine.auto_follow_target(cues, kids[0]) == 2
    assert ShowEngine.auto_follow_target(cues, kids[1]) == 3
    assert ShowEngine.auto_follow_target(cues, kids[2]) == -1


def test_loop_group_wraps_back_to_first_child():
    group = _cue(10, "LOOP", media_type=MediaType.GROUP,
                 group_mode=GroupMode.LOOP)
    kids = [_cue(11, "k1", parent_id=10), _cue(12, "k2", parent_id=10)]
    cues = [group, *kids]

    assert ShowEngine.auto_follow_target(cues, kids[0]) == 2
    assert ShowEngine.auto_follow_target(cues, kids[1]) == 1
