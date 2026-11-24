"""Extra keys for the show and a presenter remote (stage 5, items 5.7 and 5.8). No Qt.

The program's own keys stay (Space = GO, Esc twice = PANIC, ...). The map
adds keys of this computer to a few safe functions, so a presenter remote
(which types Page Down / Page Up / B like a keyboard) or an odd keyboard can
run the show. PANIC is not offered: one button of a remote pressed by
mistake must never stop everything. Keys are plain names as Qt writes them
("PgDown", "B", "."); no Ctrl / Alt / Shift.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

GO = "go"
PREV_CUE = "prev_cue"
NEXT_CUE = "next_cue"
PAUSE = "pause_toggle"
FADE_ALL = "fade_all"
UNDO_GO = "undo_go"
FUNCTIONS = (GO, PREV_CUE, NEXT_CUE, PAUSE, FADE_ALL, UNDO_GO)

# Italian source strings (translated in the window).
LABELS = {
    GO: "GO",
    PREV_CUE: "Cue precedente (solo selezione)",
    NEXT_CUE: "Cue successiva (solo selezione)",
    PAUSE: "Pausa tutto / riprendi",
    FADE_ALL: "Sfuma tutto",
    UNDO_GO: "Annulla l'ultimo GO",
}

# Most presenter remotes type Page Down / Page Up for the arrows and B or "." for "black screen".
PRESENTER = {GO: ["PgDown"], PREV_CUE: ["PgUp"], PAUSE: ["B", "."]}

# Keys the program already uses on their own (without Ctrl / Alt).
RESERVED = {
    "Space": "GO", "Esc": "PANIC (2×)", "Return": "OK", "Enter": "OK", "Del": "Elimina", "Backspace": "Elimina",
    "Up": "Selezione", "Down": "Selezione", "F5": "Spettacolo", "I": "Punto IN", "O": "Punto OUT",
    "Tab": "Focus",
}

# The order the remote wizard asks for buttons in.
WIZARD = (GO, PREV_CUE, PAUSE)


def clean(raw: object) -> dict[str, list[str]]:
    """A map read from the settings: known functions, text keys, each key once per function."""
    out: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return out
    for func in FUNCTIONS:
        keys = raw.get(func, [])
        if isinstance(keys, list):
            seen: list[str] = []
            for key in keys:
                if isinstance(key, str) and key.strip() and key.strip() not in seen:
                    seen.append(key.strip())
            if seen:
                out[func] = seen
    return out


def to_text(key_map: dict[str, list[str]]) -> str:
    return json.dumps(clean(key_map), ensure_ascii=False, sort_keys=True)


def from_text(text: str) -> dict[str, list[str]]:
    try:
        return clean(json.loads(text or "{}"))
    except (ValueError, TypeError):
        return {}


def lookup(key_map: dict[str, list[str]]) -> dict[str, str]:
    """key -> function (the first function that has it, in the order of FUNCTIONS)."""
    out: dict[str, str] = {}
    for func in FUNCTIONS:
        for key in key_map.get(func, []):
            out.setdefault(key, func)
    return out


def conflicts(key_map: dict[str, list[str]], effect_keys: Iterable[str] = ()) -> list[tuple[str, str, str]]:
    """(key, kind, detail) for keys that will not do what the map says.

    kind: "reserved" (the program uses it: detail = what for), "twice" (two functions:
    detail = the second one), "effect" (an effect of this show uses it: the effect wins).
    """
    effects = {k.upper() for k in effect_keys if k}
    out: list[tuple[str, str, str]] = []
    owner: dict[str, str] = {}
    for func in FUNCTIONS:
        for key in key_map.get(func, []):
            if key in RESERVED:
                out.append((key, "reserved", RESERVED[key]))
            if key in owner:
                out.append((key, "twice", func))
            else:
                owner[key] = func
            if key.upper() in effects:
                out.append((key, "effect", func))
    return out
