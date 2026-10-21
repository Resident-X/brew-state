"""The merge: the replicas of a unit as one answer, the units as one record, and the notes an adjudication may attach.

The merge holds no model and reads no file. Its input is, for each unit (the owner of
one answer; for a packed group, the group), the tables each replica returned, keyed by
the replica's id, and its output does not depend on the order either arrived in.

- A table, column or verdict the declared tables lack is refused, naming the replica.
- For a checklist item the merged verdict is a fail when any replica failed it, a cannot
  judge when none failed and any could not judge, and otherwise the verdict the replicas
  gave (the first of the declared verdicts when they differ). Every row records the
  replicas that raised its verdict and those that gave another.
- Findings the replicas raise for the same item and place are one finding with the
  replicas that raised it; findings that differ are all kept. A place is the caller's
  `place` of a finding row, and a caller with none puts findings at one place when their
  cells other than the number are the same.
- This round's findings are numbered in the checklist's order and the citations of them
  in the rows that cite them rewritten. A citation of an earlier round's finding is left
  as written, told apart by the round it carries against the round the caller names as
  this one, and refused when the review folder's earlier rounds do not hold it.
- Two findings the caller's place puts at one place are reported and neither is dropped.
- An adjudication, a later look at the findings by a further session, attaches notes to
  findings and nothing else. An attempt to change a verdict is recorded as a problem and
  ignored, so the set of failing items is the one the merge gave.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from . import results

FAIL, CANNOT_JUDGE = "fail", "cannot judge"
#: The keys of an adjudication's answer that would change a verdict; they are recorded as problems and ignored.
VERDICT_KEYS = ("verdict", "verdicts", "item_verdicts", "items", "tables")
NOTE_KEYS = ("finding", "note", "false_positive")


class Refused(Exception):
    """The merge is refused, with each cause and what to do about it."""

    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


@dataclass(frozen=True)
class Rules:
    """What the merge needs from a caller beyond the declared tables.

    `checklist` is every item in the order findings are numbered by. `place` is a function of a finding row giving its
    place as text, or None for a finding with no place. `round_label` is this round's label when the caller's citation
    pattern carries a round, and `earlier` the (round label, finding number) pairs the review folder's earlier rounds
    hold. `first` is the number this round's first finding takes. `caller` words a refusal about the caller's own hook.
    """

    checklist: Tuple[str, ...] = ()
    place: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None
    round_label: Optional[str] = None
    earlier: FrozenSet[Tuple[str, int]] = frozenset()
    first: int = 1
    fail: str = FAIL
    cannot_judge: str = CANNOT_JUDGE
    caller: str = "the caller"


def hook(rules: Rules, what: str, call: Callable[..., Any], *args: Any) -> Any:
    """What a caller's function returns; an exception from it is a refusal naming the function, never a traceback."""
    try:
        return call(*args)
    except Refused:
        raise
    except Exception as error:  # the caller's code is not the kit's; its defect is reported, not raised
        raise Refused([f"{rules.caller}'s {what} raised {type(error).__name__}: {error}; fix the caller"])


def natural(name: Any) -> Tuple[Any, ...]:
    """A replica id as an ordering that puts r2 before r10."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"(\d+)", str(name)) if part)


# --- What a replica's tables may hold ----------------------------------------------------------


def current_round(shape: results.AnswerShape, rules: Rules) -> Optional[str]:
    """This round's label when the citation pattern carries a round and the caller names one, otherwise None."""
    findings = shape.findings
    if findings is not None and "round" in findings.citation.groupindex:
        return rules.round_label
    return None


def table_problems(shape: results.AnswerShape, rules: Rules, who: str, tables: Any) -> List[str]:
    """Why a replica's tables are not what the declaration allows: a table, column or verdict it lacks, a finding
    outside the checklist, and a citation of a finding that was not raised or that the earlier rounds do not hold."""
    if not isinstance(tables, dict):
        return [f"{who} gave tables that are not a mapping of table name to rows"]
    found: List[str] = []
    for name, rows in tables.items():
        table = shape.table(name)
        if table is None:
            found.append(f"{who} returned a table {name!r} the declaration does not have; the tables are "
                         f"{[t.name for t in shape.tables]}")
            continue
        if not isinstance(rows, list):
            found.append(f"{who}'s table {name!r} is not a list of rows")
            continue
        columns = list(table.columns)
        for number, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                found.append(f"{who}'s table {name!r} row {number} is not a mapping of column to cell")
                continue
            extra, absent = sorted(set(row) - set(columns)), [c for c in columns if c not in row]
            if extra:
                found.append(f"{who}'s table {name!r} row {number} has a column {extra} the declared table does not have; "
                             f"its columns are {columns}")
            if absent:
                found.append(f"{who}'s table {name!r} row {number} lacks the column {absent}")
            odd = [c for c in columns if c in row and not results.cell_ok(row[c])]
            if odd:
                found.append(f"{who}'s table {name!r} row {number} has " + ", ".join(
                    f"{c!r} as {row[c]!r:.80}" for c in odd) + ", not text or a finite number")
            verdict = table.verdict_column
            if verdict and verdict in row and (not isinstance(row[verdict], str) or row[verdict] not in table.verdicts):
                found.append(f"{who}'s table {name!r} row {number} has the verdict {row[verdict]!r}, outside "
                             f"{list(table.verdicts)}")
    if shape.findings is not None and not found:
        found += finding_problems(shape, rules, who, tables)
    return found


def finding_problems(shape: results.AnswerShape, rules: Rules, who: str, tables: Dict[str, Any]) -> List[str]:
    findings = shape.findings
    table = shape.table(findings.table)
    found: List[str] = []
    numbers: List[int] = []
    for row in tables.get(findings.table, []):
        number = row[findings.number]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            found.append(f"{who} numbered a finding {number!r}; a reviewer numbers its findings with whole numbers from 1")
        elif number in numbers:
            found.append(f"{who} numbered two findings {number}")
        else:
            numbers.append(number)
        if table.key and rules.checklist and row[table.key] not in rules.checklist:
            found.append(f"{who} raised a finding on {row[table.key]!r}, which is no item of the checklist")
    current = current_round(shape, rules)
    for name, column in findings.citations:
        for row in tables.get(name, []):
            for match in findings.citation.finditer(str(row[column])):
                if current is None or match.group("round") == current:
                    if int(match.group("number")) not in numbers:
                        found.append(f"{who}'s {name!r} row cites a finding {match.group('number')} the unit did not raise")
                elif (match.group("round"), int(match.group("number"))) not in rules.earlier:
                    found.append(f"{who}'s {name!r} {column!r} cell {str(row[column])!r} cites {match.group(0)!r}, a finding of "
                                 f"round {match.group('round')} that the review folder's earlier rounds do not hold (this round "
                                 f"is {current}); cite only findings the earlier rounds raised")
    return found


# --- Citations ---------------------------------------------------------------------------------


def rewrite(pattern: "re.Pattern", text: str, current: Optional[str], renamed: Callable[[int], int]) -> str:
    """The text with the number of every citation of this round's findings swapped for `renamed` of it; a citation of
    another round's finding is left as written."""
    def one(match: "re.Match") -> str:
        if current is not None and match.group("round") != current:
            return match.group(0)
        whole, (start, end) = match.group(0), match.span("number")
        return whole[:start - match.start()] + str(renamed(int(match.group("number")))) + whole[end - match.start():]
    return pattern.sub(one, text)


# --- The replicas of one unit ------------------------------------------------------------------


def merged_verdict(table: results.TableShape, rules: Rules, given: Sequence[str]) -> str:
    present = set(given)
    if rules.fail in present:
        return rules.fail
    if rules.cannot_judge in present:
        return rules.cannot_judge
    return min(present, key=lambda verdict: table.verdicts.index(verdict))


def place_of(shape: results.AnswerShape, rules: Rules, row: Dict[str, Any]) -> Tuple[Any, ...]:
    """What puts two findings at one place: the item and the caller's place, or without a place their other cells."""
    findings = shape.findings
    table = shape.table(findings.table)
    item = row[table.key] if table.key else None
    place = hook(rules, "place function", rules.place, row) if rules.place is not None else None
    if place is not None:
        if not isinstance(place, str):
            raise Refused([f"{rules.caller}'s place function returned {place!r:.100}, which is not a place as text or None; "
                           "fix the caller"])
        return (item, place)
    return (item, tuple(row[c] for c in table.columns if c != findings.number))


@dataclass
class Merged:
    """One unit's replicas merged: the tables (each row with the replicas that raised it), and the finding each
    (replica, number) became."""

    tables: Dict[str, Dict[str, Any]]
    local: Dict[Tuple[str, int], int]


def blank(columns: Sequence[str]) -> Dict[str, Any]:
    return {"columns": list(columns), "rows": [], "raised_by": [], "dissent": [], "notes": []}


def merge_replicas(shape: results.AnswerShape, rules: Rules, unit: str, replicas: Mapping[str, Dict[str, Any]]) -> Merged:
    """The replicas of one unit as one set of tables. Replicas are taken in the order of their ids, never the order they
    arrived in. Finding numbers in the result are the unit's own, from 1, in the order the findings were first raised."""
    ids = sorted(replicas, key=natural)
    out = {table.name: blank(table.columns) for table in shape.tables}
    local: Dict[Tuple[str, int], int] = {}
    current = current_round(shape, rules)
    findings = shape.findings
    if findings is not None:
        raised: List[Dict[str, Any]] = []
        for rid in ids:
            for row in replicas[rid].get(findings.table, []):
                identity = place_of(shape, rules, row)
                joined = next((entry for entry in raised if entry["identity"] == identity and rid not in entry["by"]), None)
                if joined is None:
                    joined = {"identity": identity, "row": dict(row), "by": []}
                    raised.append(joined)
                joined["by"].append(rid)
                local[(rid, row[findings.number])] = len(raised)
        for number, entry in enumerate(raised, 1):
            for name, column in findings.citations:
                if name == findings.table:
                    entry["row"][column] = rewrite(findings.citation, str(entry["row"][column]), current,
                                                   lambda cited, rid=entry["by"][0]: local[(rid, cited)])
            entry["row"][findings.number] = number
        merged = out[findings.table]
        merged["rows"] = [entry["row"] for entry in raised]
        merged["raised_by"] = [list(entry["by"]) for entry in raised]
        merged["dissent"] = [[] for _ in raised]
        merged["notes"] = [[] for _ in raised]
    rows: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for table in shape.tables:
        if findings is not None and table.name == findings.table:
            continue
        rows[table.name] = [(rid, copy.deepcopy(row)) for rid in ids for row in replicas[rid].get(table.name, [])]
    if findings is not None:
        for name, column in findings.citations:
            if name == findings.table:
                continue
            for rid, row in rows.get(name, []):
                row[column] = rewrite(findings.citation, str(row[column]), current,
                                      lambda number, rid=rid: local[(rid, number)])
    for table in shape.tables:
        if findings is not None and table.name == findings.table:
            continue
        target = out[table.name]
        if table.verdict_column and table.key:
            by_item: Dict[Any, List[Tuple[str, Dict[str, Any]]]] = {}
            for rid, row in rows[table.name]:
                by_item.setdefault(row[table.key], []).append((rid, row))
            for item, given in by_item.items():
                verdict = merged_verdict(table, rules, [row[table.verdict_column] for _, row in given])
                chosen = next(row for _, row in given if row[table.verdict_column] == verdict)
                target["rows"].append(chosen)
                target["raised_by"].append([rid for rid, row in given if row[table.verdict_column] == verdict])
                target["dissent"].append([[rid, row[table.verdict_column]] for rid, row in given
                                          if row[table.verdict_column] != verdict])
                target["notes"].append([])
        else:
            for rid, row in rows[table.name]:
                at = next((i for i, kept in enumerate(target["rows"]) if kept == row), None)
                if at is None:
                    target["rows"].append(row)
                    target["raised_by"].append([rid])
                    target["dissent"].append([])
                    target["notes"].append([])
                elif rid not in target["raised_by"][at]:
                    target["raised_by"][at].append(rid)
    return Merged(out, local)


# --- The units ---------------------------------------------------------------------------------


def merge(shape: results.AnswerShape, rules: Rules, order: Sequence[str], units: Mapping[str, Mapping[str, Dict[str, Any]]],
          checks: Optional[Callable[[Dict[str, Any]], Sequence[str]]] = None) -> Dict[str, Any]:
    """The units' replicas as one record. Units are taken in `order`, replicas in the order of their ids; the dictionaries'
    own order is never read, so the record is the same for every order they arrive in.

    The result is `{"tables": {name: {"columns", "rows", "raised_by", "dissent", "notes"}}, "same_place": [...]}`, the
    lists beside the rows holding, for each row, the replicas that raised its verdict, those that gave another, and the
    notes an adjudication attached.
    """
    problems: List[str] = []
    for unit in order:
        if unit not in units:
            problems.append(f"unit {unit} has no result to merge; run it, or leave it out of the order")
    for unit in units:
        if unit not in order:
            problems.append(f"unit {unit} has a result and is no unit of the merge's order {list(order)}")
    for unit in order:
        if unit in units and not units[unit]:
            problems.append(f"unit {unit} has no replica result to merge")
    if problems:
        raise Refused(problems)
    for unit in order:
        for rid in sorted(units[unit], key=natural):
            problems += table_problems(shape, rules, f"unit {unit} replica {rid}", units[unit][rid])
    if problems:
        raise Refused(problems)
    parts = {unit: merge_replicas(shape, rules, unit, units[unit]) for unit in order}
    out = {table.name: blank(table.columns) for table in shape.tables}
    findings = shape.findings
    same_place: List[Dict[str, Any]] = []
    renamed: Dict[Tuple[str, int], int] = {}
    if findings is not None:
        table = shape.table(findings.table)
        checklist = list(rules.checklist)
        entries = []
        for position, unit in enumerate(order):
            held = parts[unit].tables[findings.table]
            for index, row in enumerate(held["rows"]):
                item = row[table.key] if table.key else None
                entries.append((checklist.index(item) if item in checklist else 0, position, index, unit, row, held["raised_by"][index]))
        entries.sort(key=lambda entry: entry[:3])
        target = out[findings.table]
        for offset, (_, _, index, unit, row, by) in enumerate(entries):
            renamed[(unit, index + 1)] = rules.first + offset
            target["rows"].append(row)
            target["raised_by"].append(by)
            target["dissent"].append([])
            target["notes"].append([])
        current = current_round(shape, rules)
        for (_, _, _, unit, row, _) in entries:
            for name, column in findings.citations:
                if name == findings.table:
                    row[column] = rewrite(findings.citation, str(row[column]), current,
                                          lambda number, unit=unit: renamed[(unit, number)])
            row[findings.number] = renamed[(unit, row[findings.number])]
        groups: Dict[str, List[Tuple[int, str]]] = {}
        for _, _, _, unit, row, _ in entries:
            if rules.place is None:
                continue
            place = hook(rules, "place function", rules.place, row)
            if place is not None:
                groups.setdefault(place, []).append((row[findings.number], unit))
        same_place = sorted(({"key": key, "findings": sorted(number for number, _ in members),
                              "units": sorted({unit for _, unit in members}, key=order.index)}
                             for key, members in groups.items() if len(members) > 1),
                            key=lambda place: place["findings"][0])
    for table in shape.tables:
        if findings is not None and table.name == findings.table:
            continue
        for unit in order:
            held = parts[unit].tables[table.name]
            for key in ("rows", "raised_by", "dissent", "notes"):
                out[table.name][key] += held[key]
    if findings is not None:
        current = current_round(shape, rules)
        for table in shape.tables:
            if table.name == findings.table:
                continue
            for unit in order:
                for row in parts[unit].tables[table.name]["rows"]:
                    for name, column in findings.citations:
                        if name == table.name:
                            row[column] = rewrite(findings.citation, str(row[column]), current,
                                                  lambda number, unit=unit: renamed[(unit, number)])
    record = {"tables": out, "same_place": same_place}
    if checks is not None:
        refused = hook(rules, "checks function", checks, plain_tables(record))
        if not isinstance(refused, (list, tuple)) or not all(isinstance(line, str) and line.strip() for line in refused):
            raise Refused([f"{rules.caller}'s checks function returned {refused!r:.200}, which is not a list of problems as "
                           "text; fix the caller"])
        if refused:
            raise Refused(list(refused))
    return record


def plain_tables(record: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The merged tables as a caller's checks and rendering see them: each table's columns and rows, with the replicas
    that raised each row beside them."""
    return {name: {"columns": list(table["columns"]), "rows": [dict(row) for row in table["rows"]],
                   "raised_by": [list(by) for by in table["raised_by"]]} for name, table in record["tables"].items()}


def table_markdown(table: Mapping[str, Any], raised_by: bool = True, column: str = "Raised by") -> List[str]:
    """A merged table as markdown lines, every cell escaped as the record history reader reads it back, and the replicas
    that raised each row in a last column."""
    columns = list(table["columns"])
    if not raised_by:
        return results.table_lines(columns, table["rows"])
    rows = [dict(row, **{column: ", ".join(by)}) for row, by in zip(table["rows"], table["raised_by"])]
    return results.table_lines(columns + [column], rows)


def failing_items(shape: results.AnswerShape, rules: Rules, record: Mapping[str, Any]) -> List[Tuple[str, Any]]:
    """The (table, item) pairs a merged record fails, in the order the record holds them."""
    found = []
    for table in shape.tables:
        if table.verdict_column and table.key:
            for row in record["tables"][table.name]["rows"]:
                if row[table.verdict_column] == rules.fail:
                    found.append((table.name, row[table.key]))
    return found


# --- Adjudication ------------------------------------------------------------------------------


@dataclass
class Adjudication:
    """What an adjudicating session returned: the session that wrote it, the notes it may attach, and the problems found in
    what it returned."""

    session: str
    notes: List[Dict[str, Any]] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)


def read_adjudication(session: str, answer: Any) -> Adjudication:
    """An adjudicator's answer, `{"notes": [{"finding": n, "note": text, "false_positive": true|false}]}`, read for the notes
    it may attach. Any verdict it tries to give, and anything else it holds, is recorded as a problem and ignored."""
    found = Adjudication(session)
    if not isinstance(answer, dict):
        found.problems.append(f"adjudication {session} gave {answer!r:.100}, which is not a mapping with a `notes` list; ignored")
        return found
    for key in answer:
        if key == "notes":
            continue
        if key in VERDICT_KEYS or "verdict" in str(key).casefold():
            found.problems.append(f"adjudication {session} tries to change a verdict through {key!r}; an adjudication attaches "
                                  "notes only, so it is ignored")
        else:
            found.problems.append(f"adjudication {session} holds {key!r}, which is not part of an adjudication; ignored")
    notes = answer.get("notes", [])
    if not isinstance(notes, list):
        found.problems.append(f"adjudication {session}'s `notes` is not a list; ignored")
        return found
    for number, note in enumerate(notes, 1):
        where = f"adjudication {session} note {number}"
        if not isinstance(note, dict):
            found.problems.append(f"{where} is not a mapping; ignored")
            continue
        changes = [key for key in note if "verdict" in str(key).casefold()]
        if changes:
            found.problems.append(f"{where} tries to change a verdict through {changes[0]!r}; an adjudication attaches notes "
                                  "only, so the whole note is ignored")
            continue
        extra = [key for key in note if key not in NOTE_KEYS]
        if extra:
            found.problems.append(f"{where} holds {extra[0]!r}, which a note does not; the note is ignored")
            continue
        finding, text, false_positive = note.get("finding"), note.get("note"), note.get("false_positive", False)
        if isinstance(finding, bool) or not isinstance(finding, int) or finding < 1:
            found.problems.append(f"{where} names the finding {finding!r}, not a finding number; ignored")
        elif not isinstance(text, str) or not text.strip():
            found.problems.append(f"{where} gives no note text; ignored")
        elif not isinstance(false_positive, bool):
            found.problems.append(f"{where} gives false_positive as {false_positive!r}, not true or false; ignored")
        else:
            found.notes.append({"finding": finding, "note": text, "false_positive": false_positive})
    return found


def adjudicate(shape: results.AnswerShape, record: Mapping[str, Any], adjudications: Sequence[Adjudication]) -> Dict[str, Any]:
    """The merged record with the adjudications' notes attached to the findings they name, each with the session that wrote
    it, and the problems found recorded beside the tables. No verdict row is touched."""
    out = copy.deepcopy(dict(record))
    problems: List[str] = []
    findings = shape.findings
    for adjudication in sorted(adjudications, key=lambda a: natural(a.session)):
        problems += adjudication.problems
        if findings is None:
            if adjudication.notes:
                problems.append(f"adjudication {adjudication.session} names findings and the review has no findings table; ignored")
            continue
        table = out["tables"][findings.table]
        numbers = [row[findings.number] for row in table["rows"]]
        for note in adjudication.notes:
            if note["finding"] not in numbers:
                problems.append(f"adjudication {adjudication.session} names the finding {note['finding']}, which the merged "
                                f"record does not hold; ignored")
                continue
            table["notes"][numbers.index(note["finding"])].append(
                {"note": note["note"], "false_positive": note["false_positive"], "session": adjudication.session})
    out["adjudication"] = {"sessions": [a.session for a in sorted(adjudications, key=lambda a: natural(a.session))],
                           "problems": problems}
    return out
