"""Qt-free policy: what each mode of the director window allows.

In the show the document (the cue list and every cue) must not change, by a
stray key, a click or a remote: the operator runs it, nothing else. The
window asks ``allows`` at every point that would change the document and,
when the answer is no, says why (``BLOCKED_MESSAGES``) instead of ignoring
the key in silence.
"""

from __future__ import annotations

PREPARATION = "preparation"
REHEARSAL = "rehearsal"
SHOW = "show"

# Kinds of change
EDIT_LIST = "edit_list"        # add, delete, move, group, drop files, rename in the list
EDIT_CUE = "edit_cue"          # any field of a cue (inspector, remote level)
UNDO = "undo"                  # undo / redo of document changes
RUN = "run"                    # GO, stop, pause, fade, PANIC, volume: always

_ALLOWED: dict[str, frozenset[str]] = {
    PREPARATION: frozenset({EDIT_LIST, EDIT_CUE, UNDO, RUN}),
    # The rehearsal drawer (step 9) will allow a few cue fields: EDIT_CUE there
    # goes through its own narrower check.
    REHEARSAL: frozenset({EDIT_CUE, UNDO, RUN}),
    SHOW: frozenset({RUN}),
}

BLOCKED_MESSAGES: dict[str, str] = {
    EDIT_LIST: "Nello spettacolo la scaletta non cambia: per modificarla torna alla preparazione "
               "(tieni premuto «○ Preparazione»)",
    EDIT_CUE: "Nello spettacolo le cue non cambiano: per modificarle torna alla preparazione",
    UNDO: "Annulla non serve nello spettacolo: lo spettacolo non è stato cambiato",
}


def allows(mode: str, change: str) -> bool:
    """True when *change* is allowed in *mode* (an unknown mode allows only RUN)."""
    return change in _ALLOWED.get(mode, frozenset({RUN}))
