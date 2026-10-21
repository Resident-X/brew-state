"""Reading a session's answer: the tolerant parse, the classed problems, the cell escaping and the choice among attempts.

An answer is read from the structured output when the command line returned one,
and otherwise as the one object holding a `tables` key found in the text, whatever
prose, fence or trailing remark surrounds it. What is wrong with it is classed:

- cosmetic: a cell holding a vertical bar or a line break, a column name that
  differs only in case or surrounding space, a number given as text. The kit
  repairs it and records the repair; a round is never refused for it.
- local: a citation of a finding the unit did not raise, a checklist item with no
  verdict or with two, a verdict outside the declared set. The scheduler repairs
  it with a turn in the unit's own session.
- fatal: no object, or a violation of the declared tables that cannot be mapped.
  The scheduler runs the unit again from the same parent.

Every attempt of a unit is kept, and the one that stands is chosen by `standing`.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

COSMETIC, LOCAL, FATAL = "cosmetic", "local", "fatal"
STRUCTURED, EXTRACTED, NONE = "structured", "extracted", "none"
NUMBER_TEXT = re.compile(r"\s*-?\d+(?:\.\d+)?\s*")


@dataclass(frozen=True)
class Problem:
    cls: str
    where: str
    what: str

    def line(self) -> str:
        return f"{self.where}: {self.what}"


@dataclass(frozen=True)
class TableShape:
    """One declared table: its columns in order, its key column, and for a table of verdicts the verdict column and the
    verdicts it may hold. `numeric` names the columns whose cells are numbers."""

    name: str
    columns: Tuple[str, ...]
    key: Optional[str] = None
    verdict_column: Optional[str] = None
    verdicts: Tuple[str, ...] = ()
    numeric: Tuple[str, ...] = ()


@dataclass(frozen=True)
class FindingShape:
    """Where a unit's findings are: the table that holds them and its number column, and the cells that cite them.
    `citation` is a pattern with a `number` group, and optionally a `round` group."""

    table: str
    number: str
    citations: Tuple[Tuple[str, str], ...]
    citation: "re.Pattern"


@dataclass(frozen=True)
class AnswerShape:
    tables: Tuple[TableShape, ...]
    findings: Optional[FindingShape] = None

    def table(self, name: str) -> Optional[TableShape]:
        return next((table for table in self.tables if table.name == name), None)


@dataclass
class Parsed:
    obj: Optional[Dict[str, Any]]
    source: str
    note: str = ""


def objects_in(text: str) -> List[Dict[str, Any]]:
    """Every top-level JSON object in `text`, in order, whatever surrounds them; an object is skipped over, not looked into."""
    decoder, found = json.JSONDecoder(), []
    position = text.find("{")
    while position != -1:
        try:
            value, end = decoder.raw_decode(text, position)
        except (ValueError, RecursionError):
            position = text.find("{", position + 1)
            continue
        if isinstance(value, dict):
            found.append(value)
            position = text.find("{", end)
        else:
            position = text.find("{", position + 1)
    return found


def read_answer(structured: Any, text: str) -> Parsed:
    """The object an answer holds: the structured output when it holds a `tables` mapping, else the object in the text
    that does. Of several in the text the last stands, and the note says so; with none the answer holds none."""
    if isinstance(structured, dict) and isinstance(structured.get("tables"), dict):
        return Parsed(structured, STRUCTURED)
    holders = [found for found in objects_in(text or "") if isinstance(found.get("tables"), dict)]
    if not holders:
        return Parsed(None, NONE)
    note = f"the answer held {len(holders)} objects with a tables key; the last was read" if len(holders) > 1 else ""
    return Parsed(holders[-1], EXTRACTED, note)


def cell_ok(value: Any) -> bool:
    """Whether a table cell is text or a finite number, the only cells a record holds."""
    if isinstance(value, str):
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def folded(name: Any) -> str:
    return " ".join(str(name).split()).casefold()


def repair_cosmetic(tables: Dict[str, Any], shape: AnswerShape) -> Tuple[Dict[str, Any], List[Problem], List[Problem]]:
    """The tables with every cosmetic problem repaired, the repairs made, and the problems that cannot be repaired.

    A table or column named in other case or with other spacing than declared is read as the declared one, and a number
    given as text becomes a number. A cell holding a vertical bar or a line break is left as written and listed: it is
    escaped when the record is rendered, and the raw text is kept. What cannot be mapped to the declared tables is
    returned as fatal problems, the table left out.
    """
    repaired: Dict[str, Any] = {}
    repairs: List[Problem] = []
    fatal: List[Problem] = []
    declared = {folded(table.name): table for table in shape.tables}
    for given, rows in tables.items():
        table = declared.get(folded(given))
        if table is None:
            fatal.append(Problem(FATAL, f"table {given!r}", f"no such table is declared; the tables are "
                                                          f"{[t.name for t in shape.tables]}"))
            continue
        if given != table.name:
            repairs.append(Problem(COSMETIC, f"table {given!r}", f"read as the declared table {table.name!r}"))
        if table.name in repaired:
            fatal.append(Problem(FATAL, f"table {table.name!r}", "the answer gives the table twice"))
            continue
        if not isinstance(rows, list):
            fatal.append(Problem(FATAL, f"table {table.name!r}", "is not a list of rows"))
            continue
        columns = {folded(column): column for column in table.columns}
        made, broken = [], False
        for number, row in enumerate(rows, 1):
            where = f"table {table.name!r} row {number}"
            if not isinstance(row, dict):
                fatal.append(Problem(FATAL, where, "is not a mapping of column to cell"))
                broken = True
                continue
            mapped: Dict[str, Any] = {}
            for name, value in row.items():
                column = columns.get(folded(name))
                if column is None:
                    fatal.append(Problem(FATAL, where, f"has a column {name!r} the table does not have; its columns are "
                                                       f"{list(table.columns)}"))
                    broken = True
                    continue
                if column in mapped:
                    fatal.append(Problem(FATAL, where, f"gives the column {column!r} twice"))
                    broken = True
                    continue
                if name != column:
                    repairs.append(Problem(COSMETIC, where, f"column {name!r} read as {column!r}"))
                mapped[column] = value
            lacking = [column for column in table.columns if column not in mapped]
            if lacking and not broken:
                fatal.append(Problem(FATAL, where, f"lacks the column {lacking}"))
                broken = True
            for column, value in list(mapped.items()):
                if not cell_ok(value):
                    fatal.append(Problem(FATAL, where, f"has {column!r} as {value!r:.80}, not text or a finite number"))
                    broken = True
                    continue
                if column in table.numeric:
                    if isinstance(value, str):
                        if not NUMBER_TEXT.fullmatch(value):
                            fatal.append(Problem(FATAL, where, f"has {column!r} as {value!r:.80}, which is not a number"))
                            broken = True
                            continue
                        mapped[column] = float(value) if "." in value else int(value)
                        repairs.append(Problem(COSMETIC, where, f"{column!r} gave the number {value.strip()} as text"))
                elif isinstance(value, str) and ("|" in value or "\n" in value or "\r" in value):
                    repairs.append(Problem(COSMETIC, where, f"{column!r} holds a vertical bar or a line break; it is "
                                                            "escaped when the record is rendered"))
            made.append({column: mapped[column] for column in table.columns if column in mapped})
        if not broken:
            repaired[table.name] = made
    return repaired, repairs, fatal


def local_problems(tables: Dict[str, Any], shape: AnswerShape, unit: str, items: Optional[Sequence[str]],
                   round_label: Optional[str] = None) -> List[Problem]:
    """What is wrong with repaired tables that the unit can put right in a turn of its own session."""
    found: List[Problem] = []
    for table in shape.tables:
        if table.verdict_column is None or table.key is None:
            continue
        rows = tables.get(table.name, [])
        counts: Dict[str, int] = {}
        for number, row in enumerate(rows, 1):
            verdict = row[table.verdict_column]
            if not isinstance(verdict, str) or verdict not in table.verdicts:
                found.append(Problem(LOCAL, f"unit {unit} table {table.name!r} row {number}",
                                     f"has the verdict {verdict!r}, outside {list(table.verdicts)}"))
            counts[row[table.key]] = counts.get(row[table.key], 0) + 1
        for item, count in counts.items():
            if count > 1:
                found.append(Problem(LOCAL, f"unit {unit} table {table.name!r}", f"gives item {item!r} {count} verdicts"))
        if items is not None:
            for number, row in enumerate(rows, 1):
                if row[table.key] not in items:
                    found.append(Problem(LOCAL, f"unit {unit} table {table.name!r} row {number}",
                                         f"gives a verdict for item {row[table.key]!r} in the {table.key!r} cell, which is "
                                         f"not one of the unit's items; name exactly one of {list(items)} in that cell"))
        for item in items or []:
            if item not in counts:
                found.append(Problem(LOCAL, f"unit {unit} table {table.name!r}", f"gives no verdict for item {item!r}"))
    findings = shape.findings
    if findings is not None:
        found_table = shape.table(findings.table)
        if items is not None and found_table is not None and found_table.key not in (None, findings.number):
            for number, row in enumerate(tables.get(findings.table, []), 1):
                if row[found_table.key] not in items:
                    found.append(Problem(LOCAL, f"unit {unit} table {findings.table!r} row {number}",
                                         f"raises a finding on {row[found_table.key]!r} in the {found_table.key!r} cell, "
                                         f"which is not one of the unit's items; name exactly one of {list(items)} in that "
                                         "cell and raise a separate finding for each item"))
        raised: List[int] = []
        for row in tables.get(findings.table, []):
            number = row[findings.number]
            if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                found.append(Problem(LOCAL, f"unit {unit} table {findings.table!r}",
                                     f"numbers a finding {number!r}; findings are numbered with whole numbers from 1"))
            elif number in raised:
                found.append(Problem(LOCAL, f"unit {unit} table {findings.table!r}", f"numbers two findings {number}"))
            else:
                raised.append(number)
        for table_name, column in findings.citations:
            for number, row in enumerate(tables.get(table_name, []), 1):
                for match in findings.citation.finditer(str(row[column])):
                    if "round" in findings.citation.groupindex and round_label is not None \
                            and match.group("round") != round_label:
                        continue
                    if int(match.group("number")) not in raised:
                        found.append(Problem(LOCAL, f"unit {unit} table {table_name!r} row {number}",
                                             f"cites a finding {match.group('number')} the unit did not raise"))
    return found


@dataclass
class Assessment:
    """One attempt's answer, read and classed. `raw` is the answer as the session gave it, kept whatever is repaired;
    `tables` the repaired tables, None for an answer that holds none or cannot be mapped."""

    source: str
    raw: str
    tables: Optional[Dict[str, Any]]
    repairs: List[Problem] = field(default_factory=list)
    problems: List[Problem] = field(default_factory=list)
    items_covered: int = 0
    note: str = ""

    @property
    def fatal(self) -> List[Problem]:
        return [problem for problem in self.problems if problem.cls == FATAL]

    @property
    def local(self) -> List[Problem]:
        return [problem for problem in self.problems if problem.cls == LOCAL]

    def as_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "raw": self.raw, "tables": self.tables, "note": self.note,
                "items_covered": self.items_covered,
                "repairs": [problem.line() for problem in self.repairs],
                "problems": [{"class": problem.cls, "where": problem.where, "what": problem.what}
                             for problem in self.problems]}


def assess(structured: Any, text: str, shape: AnswerShape, unit: str, items: Optional[Sequence[str]] = None,
           round_label: Optional[str] = None) -> Assessment:
    """The answer a session gave, read, repaired of what is cosmetic and classed. The raw text is kept as given; for a
    structured answer it is the structured output as JSON."""
    raw = json.dumps(structured, ensure_ascii=False) if isinstance(structured, dict) else (text or "")
    parsed = read_answer(structured, text)
    if parsed.obj is None:
        return Assessment(NONE, raw, None, problems=[Problem(FATAL, f"unit {unit}", "the answer holds no object with a "
                                                                                   "tables mapping")])
    tables, repairs, fatal = repair_cosmetic(copy.deepcopy(parsed.obj["tables"]), shape)
    if fatal:
        return Assessment(parsed.source, raw, None, repairs, [Problem(FATAL, f"unit {unit} {p.where}", p.what) for p in fatal],
                          note=parsed.note)
    problems = local_problems(tables, shape, unit, items, round_label)
    covered = 0
    for table in shape.tables:
        if table.verdict_column and table.key:
            covered += len({row[table.key] for row in tables.get(table.name, []) if row[table.key] in (items or [row[table.key]])})
    return Assessment(parsed.source, raw, tables, repairs, problems, covered, parsed.note)


# --- Attempts ----------------------------------------------------------------------------------


def standing(attempts: Sequence[Assessment]) -> int:
    """The index of the attempt that stands: the first with no problems, else the one with no fatal problem and the fewest
    local problems, else the most items covered, else the first. A later attempt never replaces a better one."""
    if not attempts:
        raise ValueError("a unit with no attempt has none that stands")
    for index, attempt in enumerate(attempts):
        if not attempt.problems:
            return index
    return min(range(len(attempts)), key=lambda index: (bool(attempts[index].fatal), len(attempts[index].local),
                                                        -attempts[index].items_covered, index))


class UnitRecord:
    """Every attempt of one unit, in order, and the attempt that stands."""

    def __init__(self, unit: str):
        self.unit = unit
        self.attempts: List[Assessment] = []

    def add(self, attempt: Assessment) -> int:
        self.attempts.append(attempt)
        return self.standing_index

    @property
    def standing_index(self) -> int:
        return standing(self.attempts)

    @property
    def standing(self) -> Assessment:
        return self.attempts[self.standing_index]

    def as_dict(self) -> Dict[str, Any]:
        return {"unit": self.unit, "standing": self.standing_index if self.attempts else None,
                "attempts": [attempt.as_dict() for attempt in self.attempts]}


# --- Cells in a record -------------------------------------------------------------------------

ENTITY = re.compile(r"&(amp|#[0-9]+);")


def needs_entity(char: str, at_edge: bool) -> bool:
    return (char in "&|" or (char.isspace() and char != " ") or (char == " " and at_edge)
            or ord(char) < 32 or 127 <= ord(char) < 160 or char in "  ")


def escape_cell(value: Any) -> str:
    """A cell as a record's table can hold it and read it back: `&`, the vertical bar, every line break, tab, control
    and non-space whitespace character, and a space at either end, are written as a character reference, so the cell
    splits only where the table does and loses nothing to the reader's trimming. A markdown reader shows it as written."""
    text = value if isinstance(value, str) else str(value)
    last = len(text) - 1
    out = []
    for index, char in enumerate(text):
        if char == "&":
            out.append("&amp;")
        elif needs_entity(char, index in (0, last)):
            out.append(f"&#{ord(char)};")
        else:
            out.append(char)
    return "".join(out)


def unescape_cell(text: str) -> str:
    """The cell as its writer gave it, from what `escape_cell` wrote."""
    return ENTITY.sub(lambda match: "&" if match.group(1) == "amp" else chr(int(match.group(1)[1:])), text)


def table_lines(columns: Sequence[str], rows: Sequence[Dict[str, Any]]) -> List[str]:
    """A markdown table: the header, the separator and a line for each row, every cell escaped."""
    lines = ["| " + " | ".join(escape_cell(column) for column in columns) + " |", "|" + "---|" * len(columns)]
    return lines + ["| " + " | ".join(escape_cell(row[column]) for column in columns) + " |" for row in rows]
