"""The cue list on paper and in a spreadsheet (stage 5, item 5.1). No Qt.

``rows`` turns the show into plain rows (number, Q, name, type, layer, what
follows, delays, script page, the line it comes on, notes, file).
``to_csv`` writes them for Excel / LibreOffice (UTF-8 with BOM, ";" as the
Polish Excel expects). ``to_xlsx`` writes a real Excel workbook without any
extra library (the few XML parts of a minimal .xlsx, zipped). ``to_html``
makes a page to print in two versions: for the operator (only the cues
started by hand, big letters, room for notes) and for the prompter (page,
line, Q and name of every cue); the same page goes into a PDF (Qt prints it
in the window module).
"""

from __future__ import annotations

import csv
import html
import re
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from models.cue import Cue, FollowMode, MediaType

from engine.show_engine import go_stops

COLUMNS = ("number", "q", "name", "type", "layer", "follow", "pre", "post", "page", "line", "notes", "off",
           "file")
_FOLLOW = {FollowMode.MANUAL.value: "GO", FollowMode.AUTO_FOLLOW.value: "Auto-GO",
           FollowMode.SIMULTANEOUS.value: "⇉ Simult."}
# A spreadsheet reads a cell starting with one of these as a formula ("-Yes?" -> #NAME?).
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def rows(cues: Iterable[Cue], follow_names: dict[str, str] | None = None) -> list[dict]:
    """One row per cue; ``_by_hand`` marks the cues the operator starts with GO (``go_stops``)."""
    cue_list = list(cues)
    names = {**_FOLLOW, **(follow_names or {})}
    by_hand = set(go_stops(cue_list))
    out = []
    for i, cue in enumerate(cue_list):
        out.append({
            "number": i + 1,
            "q": cue.q_label or "",
            "name": cue.name or "",
            "_depth": 1 if cue.parent_id is not None else 0,
            "type": cue.media_type.value,
            "layer": "" if cue.media_type in (MediaType.GROUP, MediaType.ACTION) else cue.layer,
            "follow": names.get(cue.follow_mode, cue.follow_mode),
            "pre": round(float(cue.pre_delay), 2) if cue.pre_delay else "",
            "post": round(float(cue.post_delay), 2) if cue.post_delay else "",
            "off": "" if getattr(cue, "enabled", True) else "✕",
            "page": getattr(cue, "script_page", "") or "",
            "line": getattr(cue, "script_line", "") or "",
            "notes": cue.notes or "",
            "file": Path(cue.file_path).name if cue.file_path else "",
            "_by_hand": i in by_hand,
        })
    return out


def _cell(value: object) -> str:
    """A spreadsheet cell: a decimal comma (Polish Excel reads "1.5" as the 1st of May) and
    text that would start a formula kept as text."""
    if isinstance(value, float):
        return f"{value:g}".replace(".", ",")
    text = str(value)
    if text.startswith(_FORMULA_START):
        return "'" + text
    return text


def to_csv(data: list[dict], path: str | Path, headers: dict[str, str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        out = csv.writer(fh, delimiter=";")
        out.writerow([_cell(headers.get(c, c)) for c in COLUMNS])
        for row in data:
            out.writerow([_cell(("  " * row["_depth"] + row["name"]) if c == "name" else row[c])
                          for c in COLUMNS])


# ── XLSX: the smallest workbook Excel and LibreOffice open without a repair question ──
_XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")  # not allowed in XML 1.0
_XLSX_WIDTHS = {"number": 5, "q": 8, "name": 36, "type": 9, "layer": 6, "follow": 11, "pre": 6, "post": 6,
                "page": 7, "line": 36, "notes": 36, "off": 8, "file": 28}
_CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Override PartName="/xl/workbook.xml" '
       'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
       '<Override PartName="/xl/worksheets/sheet1.xml" '
       'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
       '<Override PartName="/xl/styles.xml" '
       'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
       '<Override PartName="/docProps/core.xml" '
       'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
       '</Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" '
         'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
         'Target="xl/workbook.xml"/>'
         '<Relationship Id="rId2" '
         'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
         'Target="docProps/core.xml"/>'
         '</Relationships>')
_WB_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            '</Relationships>')
# Style 0 = normal, 1 = bold (the header row), 2 = grey and struck through (a cue that is off).
_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
           '<font><b/><sz val="11"/><name val="Calibri"/></font>'
           '<font><strike/><sz val="11"/><color rgb="FF808080"/><name val="Calibri"/></font></fonts>'
           '<fills count="2"><fill><patternFill patternType="none"/></fill>'
           '<fill><patternFill patternType="gray125"/></fill></fills>'
           '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
           '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
           '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
           '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
           '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
           '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
           '</styleSheet>')


def _col_name(index: int) -> str:
    """0 -> "A", 25 -> "Z", 26 -> "AA"."""
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def _xml_text(value: object) -> str:
    return html.escape(_XML_BAD.sub("", str(value)), quote=False)


def _xlsx_cell(ref: str, value: object, style: int) -> str:
    s = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        value = "✕" if value else ""
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{s}><v>{value:g}</v></c>' if isinstance(value, float) else \
            f'<c r="{ref}"{s}><v>{value}</v></c>'
    text = str(value)
    if not text:
        return f'<c r="{ref}"{s}/>' if style else ""
    # An inline string is never read as a formula: "=1+1" stays text (no quote needed).
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{_xml_text(text)}</t></is></c>'


def to_xlsx(data: list[dict], path: str | Path, headers: dict[str, str], sheet: str = "Cue",
            title: str = "") -> None:
    """Write *data* as an Excel workbook: a bold, frozen header row, one row per cue."""
    widths = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{_XLSX_WIDTHS.get(c, 12)}" customWidth="1"/>'
                     for i, c in enumerate(COLUMNS))
    lines = ["<row r=\"1\">" + "".join(_xlsx_cell(f"{_col_name(i)}1", headers.get(c, c), 1)
                                       for i, c in enumerate(COLUMNS)) + "</row>"]
    for n, row in enumerate(data, start=2):
        style = 2 if row.get("off") else 0
        cells = []
        for i, c in enumerate(COLUMNS):
            value = ("    " * row["_depth"] + row["name"]) if c == "name" else row[c]
            cells.append(_xlsx_cell(f"{_col_name(i)}{n}", value, style))
        lines.append(f'<row r="{n}">' + "".join(cells) + "</row>")
    last = f"{_col_name(len(COLUMNS) - 1)}{len(data) + 1}"
    sheet_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 f'<dimension ref="A1:{last}"/>'
                 '<sheetViews><sheetView workbookViewId="0">'
                 '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                 '</sheetView></sheetViews>'
                 f'<sheetFormatPr defaultRowHeight="15"/><cols>{widths}</cols>'
                 f'<sheetData>{"".join(lines)}</sheetData>'
                 '</worksheet>')
    # Excel refuses a sheet name with []:*?/\ or longer than 31 characters.
    name = _XML_BAD.sub("", re.sub(r"[\[\]:*?/\\]", " ", sheet)).strip()[:31] or "Cue"
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets><sheet name="{html.escape(name)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{_xml_text(title)}</dc:title>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
            "</cp:coreProperties>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CT)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("docProps/core.xml", core)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        zf.writestr("xl/styles.xml", _STYLES)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


_CSS = """body{font-family:Segoe UI,Arial,sans-serif;margin:12mm}h1{font-size:18pt;margin:0 0 4mm}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #888;padding:2mm;vertical-align:top;text-align:left}
th{background:#eee}tr{page-break-inside:avoid}.op td{font-size:15pt}.op .notes{height:14mm;width:35%}
.small{color:#555;font-size:9pt}.in{padding-left:8mm}.off{color:#888;text-decoration:line-through}
@media print{.noprint{display:none}}"""


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
        cells = "".join(
            f'<td class="in">{esc(str(r[c]))}</td>' if c == "name" and r["_depth"] else f"<td>{esc(str(r[c]))}</td>"
            for c in cols)
        if variant == "operator":
            cells += f'<td class="notes">{esc(r["notes"])}</td>'
        lines.append(f'<tr class="off">{cells}</tr>' if r["off"] else f"<tr>{cells}</tr>")
    cls = "op" if variant == "operator" else "pr"
    hint_html = f"<p class='small noprint'>{esc(hint)}</p>" if hint else ""
    # The table attributes are for Qt's PDF printer (it knows little CSS); a browser lets the CSS win.
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>"
            f"<style>{_CSS}</style></head><body><h1>{esc(title)}</h1>{hint_html}"
            f"<table class='{cls}' border='1' cellspacing='0' cellpadding='5' width='100%'>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(lines)}</tbody></table>"
            f"</body></html>")
