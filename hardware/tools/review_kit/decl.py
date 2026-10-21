"""The declaration of a review: the file a caller supplies and the kit loads, validates and turns into the result schema.

A declaration is a JSON file (the board tools take no YAML dependency for it)
holding the review's artefacts, units, prompt templates, result tables, deny
list and budget. Nothing is read from the review folder here; this module
checks the declaration against itself, so a slip is reported as a unit that
needs a view which is not an artefact, and costs nothing. Every problem names
the file, and the unit or table, and the artefact, slot or column that is wrong.

    {
      "artefacts": {"<name>": {"kind": "text|image|extract", "source": "<path in the review folder>",
                               "producer": "<command that writes an extract>", "tokens": <recorded count>}},
      "templates": {"<name>": "text with {slot} slots"},
      "units": {"<id>": {"items": [...], "template": "<name>", "needs": [...], "couples_with": [...],
                         "expected_output_tokens": N, "stakes": "low|normal|high", "values": {"<slot>": "..."}}},
      "schema": {"tables": [{"name", "columns", "key", "verdict_column", "verdicts", "numeric"}],
                 "findings": {"table", "number", "citations": [[table, column]], "citation": "<pattern>"}},
      "deny": ["<glob>"],
      "budget": {"wall_s", "usd", "context_tokens", "tree_saving_usd"}
    }

The tables yield the `results.AnswerShape` the results module checks an answer
against and, through `result_schema`, the JSON schema the sessions are given, so
one change to a table changes both.
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import results

KINDS = ("text", "image", "extract")
STAKES = ("low", "normal", "high")
#: The slots the kit fills in every template; a declared value may not take one of these names.
BUILT_IN_SLOTS = ("unit", "items", "schema")
SLOT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TOP_KEYS = ("artefacts", "templates", "units", "schema", "deny", "budget")
ARTEFACT_KEYS = ("kind", "source", "producer", "tokens")
UNIT_KEYS = ("items", "template", "needs", "couples_with", "expected_output_tokens", "stakes", "values")
TABLE_KEYS = ("name", "columns", "key", "verdict_column", "verdicts", "numeric")
FINDING_KEYS = ("table", "number", "citations", "citation")
BUDGET_KEYS = ("wall_s", "usd", "context_tokens", "tree_saving_usd")


@dataclass(frozen=True)
class Problem:
    """One thing wrong with a declaration: the unit or table it is about (or None), the artefact, slot or column, and what is wrong."""

    where: Optional[str]
    thing: Optional[str]
    what: str


class DeclarationError(Exception):
    """A declaration that cannot be loaded; every problem is named with the file, and `lines` holds one line each."""

    def __init__(self, file: str, problems: Sequence[Problem]):
        self.file, self.problems = file, list(problems)
        self.lines = [f"{file}: {problem.where + ': ' if problem.where else ''}{problem.what}" for problem in self.problems]
        super().__init__("\n".join(self.lines))


@dataclass(frozen=True)
class Artefact:
    name: str
    kind: str
    source: str
    producer: Optional[str] = None
    tokens: Optional[int] = None


@dataclass(frozen=True)
class Unit:
    id: str
    items: Tuple[str, ...]
    template: str
    needs: Tuple[str, ...]
    couples_with: Tuple[str, ...]
    expected_output_tokens: int
    stakes: str
    values: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Budget:
    """The review's time target in seconds, its cost ceiling in USD, its context budget in tokens, and the saving in USD
    below which a tree of shared contexts is not worth building."""

    wall_s: Optional[float] = None
    usd: Optional[float] = None
    context_tokens: Optional[int] = None
    tree_saving_usd: float = 0.5


@dataclass(frozen=True)
class Declaration:
    file: str
    artefacts: Mapping[str, Artefact]
    units: Mapping[str, Unit]
    templates: Mapping[str, str]
    shape: results.AnswerShape
    deny: Tuple[str, ...] = ()
    budget: Budget = field(default_factory=Budget)

    @property
    def needed(self) -> List[str]:
        """Every artefact any unit needs, in the fixed order the shared context holds them: by name."""
        return sorted({name for unit in self.units.values() for name in unit.needs})

    def json_schema(self) -> str:
        return schema_text(self.shape)


# --- Reading ----------------------------------------------------------------------------------


class Duplicate(ValueError):
    pass


def no_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            raise Duplicate(key)
        found[key] = value
    return found


def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def load(path: str, reader: Callable[[str], str] = read_file) -> Declaration:
    """The declaration in the file, or a DeclarationError naming the file and every problem."""
    try:
        text = reader(path)
    except (OSError, UnicodeDecodeError) as error:
        raise DeclarationError(path, [Problem(None, None, f"cannot be read ({error})")])
    return parse(text, path)


def parse(text: str, file: str) -> Declaration:
    try:
        raw = json.loads(text, object_pairs_hook=no_duplicates)
    except Duplicate as error:
        raise DeclarationError(file, [Problem(None, str(error), f"gives the key {str(error)!r} twice in one object")])
    except (ValueError, RecursionError) as error:
        raise DeclarationError(file, [Problem(None, None, f"is not valid JSON ({error})")])
    return build(raw, file)


def slots_of(template: str) -> Tuple[List[str], Optional[str]]:
    """The named slots a template holds and, when its braces are malformed or a slot is not a plain name, why not."""
    found: List[str] = []
    try:
        for _, name, spec, conversion in string.Formatter().parse(template):
            if name is None:
                continue
            if not SLOT_NAME.fullmatch(name) or spec or conversion:
                return found, f"holds the slot {{{name}}}, which is not a plain name"
            found.append(name)
    except ValueError as error:
        return found, f"has braces that cannot be read ({error})"
    return found, None


def text_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def build(raw: Any, file: str) -> Declaration:
    problems: List[Problem] = []

    def bad(where: Optional[str], thing: Optional[str], what: str) -> None:
        problems.append(Problem(where, thing, what))

    if not isinstance(raw, dict):
        raise DeclarationError(file, [Problem(None, None, "is not a JSON object")])
    for key in raw:
        if key not in TOP_KEYS:
            bad(None, key, f"has a key {key!r} the declaration does not take; the keys are {list(TOP_KEYS)}")
    artefacts = read_artefacts(raw.get("artefacts"), bad)
    templates = raw.get("templates", {})
    if not isinstance(templates, dict) or not all(isinstance(v, str) for v in templates.values()):
        bad(None, "templates", "`templates` is not a mapping of name to template text")
        templates = {}
    units = read_units(raw.get("units"), artefacts, templates, bad)
    shape = read_schema(raw.get("schema"), bad)
    deny = raw.get("deny", [])
    if not text_list(deny):
        bad(None, "deny", "`deny` is not a list of patterns")
        deny = []
    budget = read_budget(raw.get("budget", {}), bad)
    if problems:
        raise DeclarationError(file, problems)
    return Declaration(file, artefacts, units, dict(templates), shape, tuple(deny), budget)


def read_artefacts(raw: Any, bad) -> Dict[str, Artefact]:
    found: Dict[str, Artefact] = {}
    if not isinstance(raw, dict) or not raw:
        bad(None, "artefacts", "`artefacts` is missing or is not a mapping of name to artefact")
        return found
    for name, entry in raw.items():
        where = f"artefact {name}"
        if not isinstance(entry, dict):
            bad(where, name, f"artefact {name!r} is not a mapping")
            continue
        for key in entry:
            if key not in ARTEFACT_KEYS:
                bad(where, name, f"artefact {name!r} has a key {key!r} it does not take; the keys are {list(ARTEFACT_KEYS)}")
        kind, source = entry.get("kind"), entry.get("source")
        ok = True
        if kind not in KINDS:
            bad(where, name, f"artefact {name!r} has kind {kind!r}, not one of {list(KINDS)}")
            ok = False
        if not isinstance(source, str) or not source.strip():
            bad(where, name, f"artefact {name!r} has no source path")
            ok = False
        producer = entry.get("producer")
        if kind == "extract" and not (isinstance(producer, str) and producer.strip()):
            bad(where, name, f"artefact {name!r} is an extract and names no producer command")
            ok = False
        if kind in ("text", "image") and producer is not None:
            bad(where, name, f"artefact {name!r} is a {kind} and cannot have a producer; only an extract is produced")
            ok = False
        tokens = entry.get("tokens")
        if tokens is not None and (not whole(tokens) or tokens < 0):
            bad(where, name, f"artefact {name!r} gives tokens as {tokens!r}, not a whole number of zero or more")
            ok = False
        if tokens is not None and kind == "image":
            bad(where, name, f"artefact {name!r} is an image, which is measured by the patch formula and takes no recorded tokens")
            ok = False
        if ok:
            found[name] = Artefact(name, kind, source, producer, tokens)
    return found


def read_units(raw: Any, artefacts: Mapping[str, Artefact], templates: Mapping[str, str], bad) -> Dict[str, Unit]:
    found: Dict[str, Unit] = {}
    if not isinstance(raw, dict) or not raw:
        bad(None, "units", "`units` is missing or is not a mapping of id to unit")
        return found
    for uid, entry in raw.items():
        where = f"unit {uid}"
        if not isinstance(entry, dict):
            bad(where, None, f"unit {uid!r} is not a mapping")
            continue
        for key in entry:
            if key not in UNIT_KEYS:
                bad(where, key, f"unit {uid} has a key {key!r} it does not take; the keys are {list(UNIT_KEYS)}")
        items = entry.get("items")
        if not text_list(items) or not items:
            bad(where, "items", f"unit {uid} has no list of items, or an item that is not text")
            items = []
        elif len(set(items)) != len(items):
            bad(where, "items", f"unit {uid} lists an item twice")
        needs = entry.get("needs", [])
        if not text_list(needs):
            bad(where, "needs", f"unit {uid}'s `needs` is not a list of artefact names")
            needs = []
        for name in needs:
            if name not in artefacts:
                bad(where, name, f"unit {uid} needs the artefact {name!r}, which the declaration does not list")
        coupled = entry.get("couples_with", [])
        if not text_list(coupled):
            bad(where, "couples_with", f"unit {uid}'s `couples_with` is not a list of unit ids")
            coupled = []
        for other in coupled:
            if other not in raw:
                bad(where, other, f"unit {uid} is coupled with {other!r}, which is not a unit of the declaration")
            elif other == uid:
                bad(where, other, f"unit {uid} is coupled with itself")
        output = entry.get("expected_output_tokens")
        if not whole(output) or output < 1:
            bad(where, "expected_output_tokens", f"unit {uid} gives expected_output_tokens as {output!r}, not a whole number above zero")
            output = 1
        stakes = entry.get("stakes", "normal")
        if stakes not in STAKES:
            bad(where, "stakes", f"unit {uid} gives stakes as {stakes!r}, not one of {list(STAKES)}")
        values = entry.get("values", {})
        if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
            bad(where, "values", f"unit {uid}'s `values` is not a mapping of slot to text")
            values = {}
        template_name = entry.get("template")
        if template_name not in templates:
            bad(where, str(template_name), f"unit {uid} names the template {template_name!r}, which the declaration does not hold")
        else:
            slots, why = slots_of(templates[template_name])
            if why:
                bad(where, template_name, f"unit {uid}'s template {template_name!r} {why}")
            else:
                filled = set(BUILT_IN_SLOTS) | set(values)
                for slot in sorted(set(slots) - filled):
                    bad(where, slot, f"unit {uid} does not fill the slot {{{slot}}} of its template {template_name!r}")
                for slot in sorted(set(values) - set(slots)):
                    bad(where, slot, f"unit {uid} fills the value {slot!r}, which its template {template_name!r} has no slot for")
        for slot in values:
            if slot in BUILT_IN_SLOTS:
                bad(where, slot, f"unit {uid} fills {slot!r}, which the kit fills itself")
        found[uid] = Unit(uid, tuple(items), str(template_name), tuple(needs), tuple(coupled), output, stakes,
                          tuple(sorted(values.items())) if isinstance(values, dict) else ())
    return found


def read_schema(raw: Any, bad) -> results.AnswerShape:
    tables: List[results.TableShape] = []
    if not isinstance(raw, dict) or not isinstance(raw.get("tables"), list) or not raw["tables"]:
        bad(None, "schema", "`schema` is missing or holds no `tables` list")
        return results.AnswerShape(())
    for key in raw:
        if key not in ("tables", "findings"):
            bad(None, key, f"`schema` has a key {key!r} it does not take; the keys are ['tables', 'findings']")
    names: List[str] = []
    for index, entry in enumerate(raw["tables"], 1):
        label = entry.get("name") if isinstance(entry, dict) else None
        where = f"table {label}" if isinstance(label, str) else f"table {index}"
        if not isinstance(entry, dict):
            bad(where, None, f"{where} is not a mapping")
            continue
        for key in entry:
            if key not in TABLE_KEYS:
                bad(where, key, f"{where} has a key {key!r} it does not take; the keys are {list(TABLE_KEYS)}")
        if not isinstance(label, str) or not label.strip():
            bad(where, "name", f"{where} has no name")
            continue
        if label in names:
            bad(where, label, f"{where} is declared twice")
        names.append(label)
        columns = entry.get("columns")
        if not text_list(columns) or not columns or len(set(columns)) != len(columns):
            bad(where, "columns", f"{where} has no list of distinct column names")
            continue
        key = entry.get("key")
        if key is not None and key not in columns:
            bad(where, str(key), f"{where}'s key {key!r} is not one of its columns {columns}")
        verdict_column = entry.get("verdict_column")
        if verdict_column is not None and verdict_column not in columns:
            bad(where, str(verdict_column), f"{where}'s verdict column {verdict_column!r} is not one of its columns {columns}")
        verdicts = entry.get("verdicts", [])
        if not text_list(verdicts):
            bad(where, "verdicts", f"{where}'s verdicts are not a list of text")
            verdicts = []
        if verdict_column is not None and not verdicts:
            bad(where, "verdicts", f"{where}'s verdict set is empty; a table of verdicts needs at least one verdict")
        if verdicts and verdict_column is None:
            bad(where, "verdicts", f"{where} has verdicts and no verdict column to hold them")
        if len(set(verdicts)) != len(verdicts):
            bad(where, "verdicts", f"{where}'s verdict set holds a verdict twice")
        if verdict_column is not None and key is None:
            bad(where, "key", f"{where} has verdicts and no key column to say what each is a verdict on")
        numeric = entry.get("numeric", [])
        if not text_list(numeric) or any(name not in columns for name in numeric):
            bad(where, "numeric", f"{where}'s numeric columns are not a list of its columns")
            numeric = []
        tables.append(results.TableShape(label, tuple(columns), key, verdict_column, tuple(verdicts), tuple(numeric)))
    findings = read_findings(raw.get("findings"), tables, bad)
    return results.AnswerShape(tuple(tables), findings)


def read_findings(raw: Any, tables: Sequence[results.TableShape], bad) -> Optional[results.FindingShape]:
    if raw is None:
        return None
    where = "findings"
    if not isinstance(raw, dict):
        bad(where, None, "`findings` is not a mapping")
        return None
    for key in raw:
        if key not in FINDING_KEYS:
            bad(where, key, f"`findings` has a key {key!r} it does not take; the keys are {list(FINDING_KEYS)}")
    by_name = {table.name: table for table in tables}
    table = by_name.get(raw.get("table"))
    if table is None:
        bad(where, str(raw.get("table")), f"`findings` names the table {raw.get('table')!r}, which is not declared")
        return None
    if raw.get("number") not in table.columns:
        bad(where, str(raw.get("number")), f"`findings` names the number column {raw.get('number')!r}, which table {table.name} lacks")
    cites = raw.get("citations", [])
    pairs: List[Tuple[str, str]] = []
    for pair in cites if isinstance(cites, list) else [None]:
        if not (isinstance(pair, list) and len(pair) == 2 and pair[0] in by_name and pair[1] in by_name[pair[0]].columns):
            bad(where, str(pair), f"`findings` cites {pair!r}, which is not a [table, column] of the schema")
        else:
            pairs.append((pair[0], pair[1]))
    try:
        pattern = re.compile(str(raw.get("citation")))
    except re.error as error:
        bad(where, "citation", f"`findings` citation pattern does not compile ({error})")
        return None
    if "number" not in pattern.groupindex:
        bad(where, "citation", "`findings` citation pattern has no `number` group")
        return None
    return results.FindingShape(table.name, str(raw.get("number")), tuple(pairs), pattern)


def read_budget(raw: Any, bad) -> Budget:
    if not isinstance(raw, dict):
        bad(None, "budget", "`budget` is not a mapping")
        return Budget()
    values: Dict[str, Any] = {}
    for key, value in raw.items():
        if key not in BUDGET_KEYS:
            bad(None, key, f"`budget` has a key {key!r} it does not take; the keys are {list(BUDGET_KEYS)}")
        elif not positive(value) or (key == "context_tokens" and not whole(value)):
            bad(None, key, f"`budget` gives {key} as {value!r}, not a number above zero")
        else:
            values[key] = value
    return Budget(**values)


# --- The derived schema ------------------------------------------------------------------------


def column_schema(table: results.TableShape, column: str) -> Dict[str, Any]:
    if column in table.numeric:
        return {"type": "number"}
    if column == table.verdict_column:
        return {"type": "string", "enum": list(table.verdicts)}
    return {"type": "string"}


def result_schema(shape: results.AnswerShape) -> Dict[str, Any]:
    """The JSON schema a session is given, derived from the same tables the results module checks an answer against."""
    tables = {}
    for table in shape.tables:
        row = {"type": "object", "properties": {column: column_schema(table, column) for column in table.columns},
               "required": list(table.columns), "additionalProperties": False}
        tables[table.name] = {"type": "array", "items": row}
    return {"type": "object",
            "properties": {"tables": {"type": "object", "properties": tables,
                                      "required": [table.name for table in shape.tables], "additionalProperties": False}},
            "required": ["tables"], "additionalProperties": False}


def schema_text(shape: results.AnswerShape) -> str:
    """The schema as the one JSON text the command line is given, the same for the same tables."""
    return json.dumps(result_schema(shape), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def describe(shape: results.AnswerShape) -> str:
    """The tables in plain terms, for a unit's prompt."""
    lines = ["Answer with one JSON object holding a `tables` object, with these tables:"]
    for table in shape.tables:
        line = f"- `{table.name}`: a list of rows, each with the columns {', '.join(f'`{c}`' for c in table.columns)}"
        if table.key:
            line += f"; `{table.key}` names what the row is about"
        if table.verdict_column:
            line += f"; `{table.verdict_column}` is one of {', '.join(repr(v) for v in table.verdicts)}"
        if table.numeric:
            line += f"; {', '.join(f'`{c}`' for c in table.numeric)} must be a number"
        lines.append(line + ".")
    return "\n".join(lines)
