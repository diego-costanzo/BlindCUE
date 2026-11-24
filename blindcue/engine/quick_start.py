"""A quick start of a show (stage 5, item 5.9). No Qt.

``media_in_folder`` lists a folder's media in the order people number them
(1, 2, 10 – not 1, 10, 2). ``read_skeleton`` reads a cue list prepared in a
spreadsheet (CSV with ";" or ","; the columns of the program's own export,
in Italian, English or Polish), so a teacher can write the list in Excel
first and attach the files later.
"""

from __future__ import annotations

import csv
import io
import os
import re
from collections.abc import Callable
from pathlib import Path


def natural_key(name: str) -> list:
    """"Scena 2" before "Scena 10"; letters without case."""
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]


def media_in_folder(folder: str | Path, is_media: Callable[[str], bool]) -> list[str]:
    """The media files of *folder* (not its subfolders) in natural order; hidden files left out."""
    base = Path(folder)
    if not base.is_dir():
        return []
    names = [p.name for p in base.iterdir() if p.is_file() and not p.name.startswith((".", "~$"))]
    return [str(base / n) for n in sorted(names, key=natural_key) if is_media(str(base / n))]


# Column names of a skeleton: the keys of the program's export and its headers in it / en / pl.
ALIASES = {
    "q": ("q", "cue"),
    "name": ("name", "nome", "nazwa", "tytuł", "titolo", "title"),
    "type": ("type", "tipo", "typ"),
    "file": ("file", "plik", "path", "percorso", "ścieżka"),
    "page": ("page", "pagina", "strona"),
    "line": ("line", "battuta", "kwestia", "cue line"),
    "notes": ("notes", "note", "notatki", "uwagi"),
}


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def read_skeleton(path: str | Path) -> list[dict[str, str]]:
    """Rows of a CSV cue list as dicts with the keys of ALIASES ("" when the column is missing).

    The first line must name the columns; rows without a name and a file are skipped.
    Raises OSError when the file cannot be read and ValueError when no column is known.
    """
    text = _decode(Path(path).read_bytes())
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, [])
    columns: dict[str, int] = {}
    for i, title in enumerate(header):
        key = title.strip().lstrip("'").casefold().rstrip(":")
        for field, names in ALIASES.items():
            if key in names and field not in columns:
                columns[field] = i
    if "name" not in columns and "file" not in columns:
        raise ValueError("no 'name' or 'file' column")
    rows = []
    for cells in reader:
        row = {field: (cells[i].strip().lstrip("'") if i < len(cells) else "") for field, i in columns.items()}
        for field in ALIASES:
            row.setdefault(field, "")
        if row["name"] or row["file"]:
            rows.append(row)
    return rows


def resolve_file(file: str, csv_path: str | Path) -> str:
    """A file named in the skeleton: absolute as it is, relative to the CSV's folder otherwise."""
    if not file:
        return ""
    if os.path.isabs(file):
        return file
    return str((Path(csv_path).parent / file).resolve())
