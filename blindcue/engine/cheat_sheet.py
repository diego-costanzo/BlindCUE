"""The cheat sheet to print (stage 5, item 5.18). No Qt.

One A4 page for the dark room next to the laptop: the keys of the show, the
effects and extra keys of this show and computer, and what to do when
something does not work. The texts come already translated; this module
only lays them out (large type, two columns, black on white).
"""

from __future__ import annotations

from html import escape

Rows = list[tuple[str, str]]


def to_html(title: str, sections: list[tuple[str, Rows]], tips: tuple[str, list[str]], footer: str,
            hint: str = "") -> str:
    """The page: *sections* are (heading, [(keys, what), ...]); *tips* is (heading, [line, ...])."""
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>",
        "@page { size: A4; margin: 12mm; }",
        "body { font-family: 'Segoe UI', Arial, sans-serif; color: #000; background: #fff; margin: 0; }",
        "h1 { font-size: 22pt; margin: 0 0 6pt 0; }",
        "h2 { font-size: 14pt; margin: 10pt 0 4pt 0; border-bottom: 2px solid #000; }",
        "table { border-collapse: collapse; width: 100%; }",
        "td { font-size: 12.5pt; padding: 3pt 4pt; vertical-align: top; border-bottom: 1px solid #bbb; }",
        "td.k { font-weight: bold; white-space: nowrap; width: 34%; }",
        "ul { margin: 2pt 0 0 14pt; padding: 0; } li { font-size: 12pt; margin: 3pt 0; }",
        ".foot { font-size: 9pt; color: #444; margin-top: 10pt; }",
        ".hint { font-size: 10pt; color: #444; } @media print { .hint { display: none; } }",
        "</style></head><body>",
        f"<h1>{escape(title)}</h1>",
    ]
    if hint:
        parts.append(f"<p class='hint'>{escape(hint)}</p>")
    for heading, rows in sections:
        if not rows:
            continue
        parts.append(f"<h2>{escape(heading)}</h2><table>")
        parts += [f"<tr><td class='k'>{escape(keys)}</td><td>{escape(what)}</td></tr>" for keys, what in rows]
        parts.append("</table>")
    heading, lines = tips
    if lines:
        parts.append(f"<h2>{escape(heading)}</h2><ul>")
        parts += [f"<li>{escape(line)}</li>" for line in lines]
        parts.append("</ul>")
    parts.append(f"<p class='foot'>{escape(footer)}</p></body></html>")
    return "\n".join(parts)
