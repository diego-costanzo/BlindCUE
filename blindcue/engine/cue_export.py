"""The cue list on paper and in a spreadsheet (stage 5, item 5.1). No Qt.

``rows`` turns the show into plain rows (number, Q, name, type, layer, what
follows, delays, script page, the line it comes on, notes, file).
``to_csv`` writes them for Excel / LibreOffice (UTF-8 with BOM, ";" as the
Polish Excel expects). ``to_html`` makes a page to print in two versions:
for the operator (only the cues started by hand, big letters, room for
notes) and for the prompter (page, line, Q and name of every cue).
"""

from __future__ import annotations

import csv
import html
from collections.abc import Iterable
from pathlib import Path

from engine.show_engine import outside_go_order
from models.cue import Cue, FollowMode, MediaType

COLUMNS = ("number", "q", "name", "type", "layer", "follow", "pre", "post", "page", "line", "notes", "file")
_FOLLOW = {FollowMode.MANUAL.value: "GO", FollowMode.AUTO_FOLLOW.value: "Auto-GO",
           FollowMode.SIMULTANEOUS.value: "+"}


def rows(cues: Iterable[Cue]) -> list[dict]:
    cue_list = list(cues)
    out = []
    for i, cue in enumerate(cue_list):
        depth = 1 if cue.parent_id is not None else 0
        out.append({
            "number": i + 1,
            "q": cue.q_label or "",
            "name": ("  " * depth) + (cue.name or ""),
            "type": cue.media_type.value,
            "layer": "" if cue.media_type in (MediaType.GROUP, MediaType.ACTION) else cue.layer,
            "follow": _FOLLOW.get(cue.follow_mode, cue.follow_mode),
            "pre": round(float(cue.pre_delay), 2) if cue.pre_delay else "",
            "post": round(float(cue.post_delay), 2) if cue.post_delay else "",
            "page": getattr(cue, "script_page", "") or "",
            "line": getattr(cue, "script_line", "") or "",
            "notes": cue.notes or "",
            "file": Path(cue.file_path).name if cue.file_path else "",
            "_by_hand": _started_by_hand(cue_list, i),
        })
    return out


def _started_by_hand(cues: list[Cue], i: int) -> bool:
    """True when GO starts this cue (not the cue before it, a scene, a time or another cue)."""
    cue = cues[i]
    if outside_go_order(cue) or not getattr(cue, "enabled", True):
        return False
    if cue.parent_id is not None:
        return False  # a scene starts its own cues
    prev = next((cues[j] for j in range(i - 1, -1, -1) if cues[j].parent_id is None
                 and not outside_go_order(cues[j])), None)
    return prev is None or prev.follow_mode == FollowMode.MANUAL.value


def to_csv(data: list[dict], path: str | Path, headers: dict[str, str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        out = csv.writer(fh, delimiter=";")
        out.writerow([headers.get(c, c) for c in COLUMNS])
        for row in data:
            out.writerow([row[c] for c in COLUMNS])


_CSS = """body{font-family:Segoe UI,Arial,sans-serif;margin:12mm}h1{font-size:18pt;margin:0 0 4mm}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #888;padding:2mm;vertical-align:top;text-align:left}
th{background:#eee}tr{page-break-inside:avoid}.op td{font-size:15pt}.op .notes{height:14mm;width:35%}
.small{color:#555;font-size:9pt}@media print{.noprint{display:none}}"""


def to_html(data: list[dict], title: str, variant: str, headers: dict[str, str], hint: str = "") -> str:
    """A page to print. *variant*: "operator" (cues started by hand, room for notes) or "prompter"."""
    esc = html.escape
    if variant == "operator":
        cols = ("number", "q", "name", "page", "line")
        body_rows = [r for r in data if r["_by_hand"]]
        extra = '<th class="notes">' + esc(headers.get("notes", "notes")) + "</th>"
    else:
        cols = ("page", "line", "number", "q", "name", "follow")
        body_rows = data
        extra = ""
    head = "".join(f"<th>{esc(headers.get(c, c))}</th>" for c in cols) + extra
    lines = []
    for r in body_rows:
        cells = "".join(f"<td>{esc(str(r[c]))}</td>" for c in cols)
        if variant == "operator":
            cells += f'<td class="notes">{esc(r["notes"])}</td>'
        lines.append(f"<tr>{cells}</tr>")
    cls = "op" if variant == "operator" else "pr"
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>"
            f"<style>{_CSS}</style></head><body><h1>{esc(title)}</h1>"
            f"<p class='small noprint'>{esc(hint)}</p>"
            f"<table class='{cls}'><thead><tr>{head}</tr></thead><tbody>{''.join(lines)}</tbody></table>"
            f"</body></html>")
