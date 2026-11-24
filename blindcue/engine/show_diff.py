"""Everything that differs between two states of a show (stage 5, item 5.6). No Qt.

"Why is the show marked as changed?" compares the show as it was saved (or
opened) with the show now; "Restore a saved version" compares a backup with
the show now. Unlike ``undo_names.describe`` (one step, one sentence) this
lists every difference: cues added and removed, the order, each changed
field of each cue, and the show's own settings (versions, info, Layer 0...).
"""

from __future__ import annotations

from engine.undo_names import Change, _short

_IGNORED = {"status"}
# Settings that are the computer's, not the show's (they are saved, but change without an edit).
_IGNORED_SETTINGS = {"output", "live_mode"}


def differences(before: list[dict], after: list[dict], before_settings: dict | None = None,
                after_settings: dict | None = None) -> list[Change]:
    """Every difference from *before* to *after* (cue dicts as ``Cue.to_dict`` makes them), in list order.

    Kinds: "added", "removed", "moved" (the order of the cues both have changed), "field" (one field of
    one cue: ``field`` = the key, ``old`` / ``new`` short texts), "setting" (``field`` = the settings key).
    """
    old = {d.get("cue_id"): d for d in before}
    new = {d.get("cue_id"): d for d in after}
    out: list[Change] = []
    for d in after:
        if d.get("cue_id") not in old:
            out.append(Change("added", d.get("name", ""), d.get("q_label", ""), 1))
    for d in before:
        if d.get("cue_id") not in new:
            out.append(Change("removed", d.get("name", ""), d.get("q_label", ""), 1))
    kept_before = [d.get("cue_id") for d in before if d.get("cue_id") in new]
    kept_after = [d.get("cue_id") for d in after if d.get("cue_id") in old]
    if kept_before != kept_after:
        moved = next((new[a] for a, b in zip(kept_after, kept_before) if a != b), {})
        out.append(Change("moved", moved.get("name", ""), moved.get("q_label", "")))
    for d in after:
        was = old.get(d.get("cue_id"))
        if was is None:
            continue
        for key in sorted(k for k in set(d) | set(was) if k not in _IGNORED and d.get(k) != was.get(k)):
            out.append(Change("field", d.get("name", ""), d.get("q_label", ""), 1, key,
                              _short(was.get(key)), _short(d.get(key))))
    a, b = before_settings or {}, after_settings or {}
    for key in sorted(k for k in set(a) | set(b) if k not in _IGNORED_SETTINGS and a.get(k) != b.get(k)):
        out.append(Change("setting", "", "", 1, key, _short(a.get(key)), _short(b.get(key))))
    return out
