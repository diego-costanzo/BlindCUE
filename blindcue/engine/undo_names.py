"""What one undo step changed, in words (stage 5, item 5.11). No Qt.

``describe`` compares two snapshots of the cue list (``Cue.to_dict`` rows)
and says what happened between them: cues added or removed, the list
reordered, or which field of which cue went from what to what. The UI turns
the result into a sentence ("Q7 'Bell': Fade In 2 → 0").
"""

from __future__ import annotations

from dataclasses import dataclass

# Italian source labels of the fields people change most (others show their key).
FIELD_LABELS = {
    "name": "nome", "q_label": "Q", "fade_in": "Fade In", "fade_out": "Fade Out", "volume": "volume",
    "pre_delay": "Pre-Delay", "post_delay": "Post-Delay", "in_point": "IN", "out_point": "OUT",
    "layer": "layer", "follow_mode": "poi", "file_path": "file", "notes": "note", "enabled": "inclusa",
    "parent_id": "scena", "group_mode": "modo della scena", "color": "colore", "crossfade": "dissolvenza",
    "playback_rate": "tempo", "script_page": "pagina", "script_line": "battuta", "hotkey": "tasto",
    "adlib": "effetto", "start_clock": "ora", "action_spec": "azione", "text_spec": "testo",
    "markers": "marcatori", "audio_output": "uscita audio",
}
_IGNORED = {"status"}


@dataclass(frozen=True)
class Change:
    kind: str           # "added", "removed", "replaced", "moved", "field", "fields", "many", "none"
    name: str = ""      # the cue (the first one when several)
    q: str = ""
    count: int = 0      # cues added / removed / changed, or fields changed
    field: str = ""     # FIELD_LABELS key or raw key
    old: str = ""
    new: str = ""


def _short(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return "…"
    text = str(value)
    return text if len(text) <= 28 else text[:27] + "…"


def describe(before: list[dict], after: list[dict]) -> Change:
    old = {d.get("cue_id"): d for d in before}
    new = {d.get("cue_id"): d for d in after}
    added = [d for i, d in new.items() if i not in old]
    removed = [d for i, d in old.items() if i not in new]
    if added or removed:
        first = (added or removed)[0]
        kind = "replaced" if added and removed else "added" if added else "removed"
        return Change(kind, first.get("name", ""), first.get("q_label", ""), len(added) or len(removed))
    changed: list[tuple[dict, list[str]]] = []
    for cue_id, row in new.items():
        keys = sorted(k for k in set(row) | set(old[cue_id]) if k not in _IGNORED
                      and row.get(k) != old[cue_id].get(k))
        if keys:
            changed.append((row, keys))
    if not changed:
        if [d.get("cue_id") for d in before] != [d.get("cue_id") for d in after]:
            moved = next((a for a, b in zip(after, before) if a.get("cue_id") != b.get("cue_id")), after[0])
            return Change("moved", moved.get("name", ""), moved.get("q_label", ""))
        return Change("none")
    row, keys = changed[0]
    if len(changed) == 1 and len(keys) == 1:
        key = keys[0]
        return Change("field", row.get("name", ""), row.get("q_label", ""), 1, key,
                      _short(old[row.get("cue_id")].get(key)), _short(row.get(key)))
    if len(changed) == 1:
        return Change("fields", row.get("name", ""), row.get("q_label", ""), len(keys), ", ".join(keys[:3]))
    fields = {k for _row, ks in changed for k in ks}
    return Change("many", row.get("name", ""), row.get("q_label", ""), len(changed),
                  next(iter(fields)) if len(fields) == 1 else "")
