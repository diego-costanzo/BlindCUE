"""The report after a show (stage 5, item 5.19). No Qt.

From the run log of one show (every GO by hand or automatic, PANIC, Fade
All, pauses, blackout, Undo GO, effects, a faded scene, the end) it makes a
page to read after the show: when it started and ended, how long it took,
the counts, the timeline, and which cues that need a GO never played. The
texts come already translated; this module only counts and lays them out.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from html import escape

GO, AUTO, PANIC, FADE_ALL, PAUSE, RESUME, BLACKOUT, UNDO_GO, EFFECT, FADE_SCENE, END = (
    "GO", "AUTO", "PANIC", "FADE_ALL", "PAUSE", "RESUME", "BLACKOUT", "UNDO_GO", "EFFECT", "FADE_SCENE", "END")
NOTE = "NOTE"  # 5.6: a line the operator wrote in the show diary ("mic 2 crackled")
CUE_EVENTS = (GO, AUTO)


def mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60:02d}:{rest % 60:02d}"


def counts(events: Iterable[str]) -> Counter:
    return Counter(events)


def unplayed(go_rows: Iterable[int], played_ids: set[int], cue_ids: list[int]) -> list[int]:
    """Rows that need a GO (*go_rows*) whose cue never started in this run."""
    return [r for r in go_rows if 0 <= r < len(cue_ids) and cue_ids[r] not in played_ids]


def to_html(title: str, started: datetime, log: list[tuple[float, str, str, str]],
            labels: dict[str, str], summary_labels: dict[str, str], missed: list[str],
            headings: tuple[str, str, str], footer: str) -> str:
    """*log*: (seconds from the start, event, "#n" or "", name / detail).

    *labels*: event -> words for the timeline; *summary_labels*: "start", "end", "length" and events to count;
    *headings*: (summary, timeline, cues that never played).
    """
    length = log[-1][0] if log else 0.0
    ended = started + timedelta(seconds=length)
    tally = counts(event for _s, event, _n, _d in log)
    rows = [(summary_labels["start"], started.strftime("%H:%M:%S")),
            (summary_labels["end"], ended.strftime("%H:%M:%S")),
            (summary_labels["length"], mmss(length))]
    rows += [(summary_labels[e], str(tally[e]))
             for e in (GO, AUTO, EFFECT, PAUSE, FADE_ALL, PANIC, BLACKOUT, UNDO_GO, NOTE)
             if tally[e] and e in summary_labels]
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>body { font-family: 'Segoe UI', Arial, sans-serif; margin: 18px; color: #000; background: #fff; }"
        " h1 { font-size: 20pt; margin: 0 0 4pt 0; } h2 { font-size: 13pt; border-bottom: 2px solid #000;"
        " margin: 14pt 0 4pt 0; } table { border-collapse: collapse; } td, th { font-size: 11pt;"
        " padding: 2pt 8pt; border-bottom: 1px solid #bbb; text-align: left; vertical-align: top; }"
        " tr.alarm td { font-weight: bold; color: #b00000; } tr.note td { font-style: italic; color: #1d4ed8; }"
        " .foot { font-size: 9pt; color: #444; }</style>",
        "</head><body>",
        f"<h1>{escape(title)}</h1>",
        f"<h2>{escape(headings[0])}</h2><table>",
    ]
    parts += [f"<tr><td>{escape(k)}</td><td><b>{escape(v)}</b></td></tr>" for k, v in rows]
    parts.append(f"</table><h2>{escape(headings[1])}</h2><table>")
    for secs, event, number, detail in log:
        clock = (started + timedelta(seconds=secs)).strftime("%H:%M:%S")
        alarm = " class='alarm'" if event in (PANIC, BLACKOUT) else (" class='note'" if event == NOTE else "")
        parts.append(f"<tr{alarm}><td>{mmss(secs)}</td><td>{clock}</td><td>{escape(labels.get(event, event))}</td>"
                     f"<td>{escape(number)}</td><td>{escape(detail)}</td></tr>")
    parts.append("</table>")
    if missed:
        parts.append(f"<h2>{escape(headings[2])}</h2><ul>")
        parts += [f"<li>{escape(m)}</li>" for m in missed]
        parts.append("</ul>")
    parts.append(f"<p class='foot'>{escape(footer)}</p></body></html>")
    return "\n".join(parts)
