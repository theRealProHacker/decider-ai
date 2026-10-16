"""Spreadsheets in, rows out: CSV or xlsx bytes to {header: cell text}, and the column guess."""

from __future__ import annotations

import csv
import hashlib
import io
import re

import openpyxl

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class SheetError(ValueError):
    pass


def read(body: bytes, xlsx: bool | None = None) -> list[dict[str, str]]:
    """Rows of a CSV or the first xlsx sheet; the first non-empty row is the header.

    ``xlsx=None`` tells the two apart by the zip signature, for input that comes without a type.
    """
    if xlsx is None:
        xlsx = body[:2] == b"PK"
    if xlsx:
        try:
            sheet = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True).active
            grid = [["" if v is None else str(v) for v in row]
                    for row in sheet.iter_rows(values_only=True)]
        except Exception as exc:
            raise SheetError("not a readable xlsx file") from exc
    else:
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SheetError("CSV must be UTF-8") from exc
        try:  # Excel exports use ";" in many locales
            dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        grid = list(csv.reader(io.StringIO(text), dialect))
    grid = [row for row in grid if any(cell.strip() for cell in row)]
    if not grid:
        return []
    header = [h.strip() for h in grid[0]]
    return [dict(zip(header, (c.strip() for c in row))) for row in grid[1:]]


def external_id(row: dict[str, str], id_column: str | None, text: str) -> str:
    """The row's ID column, or a hash of the text: re-importing the same sheet then updates, not adds."""
    return (id_column and row.get(id_column)) or "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:16]


ID_HEADER = re.compile(r"(^|[^a-z])(id|ticket|nr|no|number|ref|key)([^a-z]|$)", re.I)
LABEL_HEADER = re.compile(r"label|category|class|team|queue|route|routed|type|topic|intent", re.I)


def guess_columns(rows: list[dict[str, str]]) -> dict[str, str | None]:
    """Text = longest cells, label = few repeating values, ID = an ID-like header with unique values."""
    if not rows:
        raise SheetError("the sheet has no data rows")
    columns = list(rows[0])

    def values(c):
        return [r.get(c, "") for r in rows if r.get(c, "")]

    def mean_len(c):
        v = values(c)
        return sum(map(len, v)) / len(v) if v else 0

    def labelish(c):
        v = values(c)
        distinct = len(set(v))
        return len(v) >= len(rows) / 2 and 2 <= distinct <= 50 and distinct <= len(v) / 3

    text = max(columns, key=mean_len)
    candidates = [c for c in columns if c != text and labelish(c)]
    if not candidates:
        raise SheetError(f"no column looks like labels (a few values that repeat); columns: {columns}")
    label = max(candidates, key=lambda c: (bool(LABEL_HEADER.search(c)), -len(set(values(c)))))
    ids = [c for c in columns if c not in (text, label) and ID_HEADER.search(c)
           and len(set(values(c))) == len(rows)]
    return {"text": text, "label": label, "id": ids[0] if ids else None}
