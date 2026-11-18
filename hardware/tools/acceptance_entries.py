#!/usr/bin/env python3
"""The acceptance-entry generator: signed workmanship acceptance entries written from a pre-order check log, for low-voltage neatness lines only.

The pre-order check fails a board for each routing-neatness line it reports
(a pad corner, a pad entry, a detour, a via in a decoupling path and the rest of
the closed set its workmanship acceptance record may excuse). A board whose
owner has judged those lines harmless signs one entry per rule and net in that
record. This tool writes those entries from the log of a check run, so that a
re-run of the check reports the lines as ACCEPTED and not as failures.

It writes an entry only where it can justify one. Every failing neatness line is
first tested against the mains side of the board, and a line on a net of a Mains
net class or at a position inside a mains region (a named rule area of the
layout) is refused, named, and never entered: a mains spacing, creepage or
neatness line is not the generator's to excuse. A line on a low-voltage net is
given the reason the board's own table holds for that net's kind; a net the
table does not place in any kind, a kind with no reason for the rule, and a net
that already has an exhausted signed entry (a signed count is never raised) are
refused by name too. Lines of rules the record does not accept are not touched
and are counted. Entries the log reports stale, which no line uses, are removed.

By default nothing is written while any line is refused, so the owner sees the
whole of what is held back first; --partial writes the entries of the lines that
could be justified. The record's existing text, comments included, is kept as it
is: new entries are appended to it, and a stale entry's lines are cut out.

The reasons table is a YAML file in the board's folder, read by --table:

    accepted_by: who signs, for every entry written (never a placeholder)
    synthetic: true            # only for a design marked not for manufacture
    net_kinds:
      - kind: slow analogue
        nets: ["NTC_*", "/sheet/PT?_BIAS"]   # patterns for a net's whole name or its last path part
        bounded_by: what limits the harm
        reasons:
          workmanship_pad_corner: the engineering reason for that rule on this kind

Exit status: 0 when every failing neatness line was entered or there were none, 1 when any was
refused, 2 when the tool cannot run (an unreadable log, table, board, project or record).
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import os
import re
import sys
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402

CannotRun = board_check.CannotRun

#: The lines a check log carries that name a design and a finding.
LOG_KINDS = ("VIOLATION", "ACCEPTED", "WARNING", "COUNT")
#: The record entries are appended to, and the keys of one entry, as the pre-order check reads them.
RECORD_NAME = board_check.WORKMANSHIP_ACCEPTANCE_NAME
ENTRY_KEYS = board_check.WORKMANSHIP_ENTRY_KEYS
#: The rules a record may accept: a failing line of any other rule is not a neatness line this tool writes for.
ACCEPTED_RULES = board_check.ACCEPTABLE_WORKMANSHIP
#: The default of --mains-class and --mains-region.
MAINS_CLASS_DEFAULT = "Mains*"
MAINS_REGION_DEFAULT = "mains"

NUMBER = r"-?\d+(?:\.\d+)?"
POSITION = re.compile(rf"\(({NUMBER}), ({NUMBER})\)")
NET_PREFIX = re.compile(r"^net (.+?): ")
NET_BRACKET = re.compile(r"\[([^\]]+)\]")
STALE = re.compile(r"accepted_workmanship\[(\d+)\]")


class Line:
    """One line of the log: its kind, the design it names, the rule, the place and the message."""

    def __init__(self, kind: str, design: str, rule: str, where: str, message: str):
        self.kind, self.design, self.rule, self.where, self.message = kind, design, rule, where, message


def read_log(path: str) -> Tuple[List[Line], List[str]]:
    """The finding lines of a check log, and the designs its DESIGN lines name; CannotRun when it is no check log."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as error:
        raise CannotRun(f"the check log {path} cannot be read ({error})") from error
    lines, designs = [], []
    for raw in text.split("\n"):
        fields = [field.strip() for field in raw.split(" | ", 4)]
        if fields[0] == "DESIGN" and len(fields) >= 3:
            designs.append(fields[1])
        elif fields[0] in LOG_KINDS and len(fields) >= 4:
            lines.append(Line(fields[0], fields[1], fields[2], fields[3], fields[4] if len(fields) > 4 else ""))
    if not designs:
        raise CannotRun(f"the check log {path} has no DESIGN line, so it is no log of the pre-order check "
                        "(run python3 hardware/tools/board_check.py and give its output)")
    return lines, designs


# --- The board's own facts ---------------------------------------------------------------------


def wildcard(pattern: str):
    return re.compile("".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern))


class Mains:
    """What makes a net or a position mains: the net classes named, and the rule areas named."""

    def __init__(self, project: dict, layout: list, class_patterns: Sequence[str], regions: Sequence[str], board: str):
        settings = board_check.setting(project, "net_settings")
        settings = settings if isinstance(settings, dict) else {}
        assigned = settings.get("netclass_assignments") or {}
        patterns = settings.get("netclass_patterns") or []
        if not isinstance(assigned, dict) or not isinstance(patterns, list):
            raise CannotRun("the project file's net_settings holds netclass_assignments that is no object or "
                            "netclass_patterns that is no list, so a net's class cannot be told")
        self.assigned = assigned
        self.patterns = []
        for entry in patterns:
            if isinstance(entry, dict) and isinstance(entry.get("pattern"), str) and isinstance(entry.get("netclass"), str):
                self.patterns.append((wildcard(entry["pattern"]), entry["netclass"]))
        self.class_patterns = list(class_patterns)
        variables = project.get("text_variables")
        declared = variables.get("MAINS") if isinstance(variables, dict) else None
        if declared not in ("present", "none"):
            said = "is not set" if declared is None else f"is {json.dumps(declared)}"
            raise CannotRun(f"the project variable MAINS {said}; every board declares it as exactly present or none, so set it "
                            "in the project file before a mains line can be told")
        if declared == "present":
            wanted = [re.compile("".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in each))
                      for each in class_patterns]
            defined = sorted(locked_copper.defined_classes(project, layout))
            if not any(pattern.fullmatch(name) for pattern in wanted for name in defined):
                raise CannotRun(f"the board {board} declares MAINS present and defines no net class matching "
                                f"{', '.join(class_patterns)} (it defines {', '.join(defined) or 'none'}), so a line on a mains net "
                                "cannot be told; name the mains classes with --mains-class, or fix the board")
        self.areas: List[Tuple[str, List[Tuple[float, float]]]] = []
        for zone in sexpr.children(layout, "zone"):
            name = sexpr.child(zone, "name")
            if not sexpr.children(zone, "keepout") or name is None or len(name) < 2 or not any(
                    region.lower() in str(name[1]).lower() for region in regions):
                continue
            for corners in locked_copper.outline(zone, f"the region {name[1]}"):
                points = []
                for corner in corners:
                    for xy in (corner[1:] if corner and corner[0] == "arc" else [corner]):
                        points.append((xy[0] / 1_000_000, xy[1] / 1_000_000))
                self.areas.append((str(name[1]), points))
        found = [name.lower() for name, _ in self.areas]
        missing = [region for region in regions if not any(region.lower() in name for name in found)]
        if declared == "present" and missing:
            held = sorted({str(sexpr.child(zone, "name")[1]) for zone in sexpr.children(layout, "zone")
                           if sexpr.children(zone, "keepout") and sexpr.child(zone, "name") is not None
                           and len(sexpr.child(zone, "name")) > 1})
            raise CannotRun(f"the board {board} declares MAINS present and has no rule area named {', '.join(missing)}, so a line "
                            f"inside a mains region cannot be told; it holds {'the rule areas ' + ', '.join(held) if held else 'no rule area'}"
                            "; name the mains region with --mains-region, or fix the board")

    def classes_of(self, net: str) -> List[str]:
        value = self.assigned.get(net)
        if value is None:
            for pattern, name in self.patterns:
                if pattern.fullmatch(net):
                    value = name
                    break
        if value is None:
            return ["Default"]
        if isinstance(value, list):
            value = ",".join(str(each) for each in value)
        return [part.strip() for part in str(value).split(",") if part.strip()]

    def net_why(self, net: str) -> Optional[str]:
        for name in self.classes_of(net):
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in self.class_patterns):
                return f"net {net} is in the net class {name}, a mains class"
        return None

    def position_why(self, points: Sequence[Tuple[float, float]]) -> Optional[str]:
        """Why a line printing these positions is mains: a point in a mains region, or, when it prints two or more, a
        stretch between consecutive points that touches or crosses one."""
        for x, y in points:
            for name, polygon in self.areas:
                if inside(x, y, polygon):
                    return f"the position ({x:g}, {y:g}) lies in the mains region {name}"
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            for name, polygon in self.areas:
                if crosses(x1, y1, x2, y2, polygon):
                    return f"the stretch from ({x1:g}, {y1:g}) to ({x2:g}, {y2:g}) crosses the mains region {name}"
        return None


def inside(x: float, y: float, polygon: Sequence[Tuple[float, float]]) -> bool:
    """Whether (x, y) is in the polygon, a point on its edge included."""
    result = False
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if (abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9
                and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9):
            return True
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            result = not result
    return result


def orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> int:
    value = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)


def on_stretch(ax: float, ay: float, bx: float, by: float, x: float, y: float) -> bool:
    return min(ax, bx) - 1e-9 <= x <= max(ax, bx) + 1e-9 and min(ay, by) - 1e-9 <= y <= max(ay, by) + 1e-9


def stretches_meet(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float], d: Tuple[float, float]) -> bool:
    """Whether the stretch a-b and the stretch c-d share a point, touching included."""
    o1, o2 = orientation(*a, *b, *c), orientation(*a, *b, *d)
    o3, o4 = orientation(*c, *d, *a), orientation(*c, *d, *b)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and on_stretch(*a, *b, *c)) or (o2 == 0 and on_stretch(*a, *b, *d))
            or (o3 == 0 and on_stretch(*c, *d, *a)) or (o4 == 0 and on_stretch(*c, *d, *b)))


def crosses(x1: float, y1: float, x2: float, y2: float, polygon: Sequence[Tuple[float, float]]) -> bool:
    """Whether the stretch from (x1, y1) to (x2, y2) has a point in the polygon: an end inside it, or the stretch meeting an edge."""
    if inside(x1, y1, polygon) or inside(x2, y2, polygon):
        return True
    return any(stretches_meet((x1, y1), (x2, y2), polygon[i], polygon[(i + 1) % len(polygon)]) for i in range(len(polygon)))


# --- The reasons table -------------------------------------------------------------------------


class Table:
    """The board's reasons by net kind."""

    def __init__(self, path: str, accepted_on: datetime.date):
        yaml = board_check.require_yaml()
        try:
            with open(path, encoding="utf-8") as handle:
                data = board_check.strict_yaml(yaml, handle.read())
        except OSError as error:
            raise CannotRun(f"the reasons table {path} cannot be read ({error})") from error
        except (yaml.YAMLError, board_check.RecordForm) as error:
            raise CannotRun(f"the reasons table {path} is not readable YAML in the one form read ({error})") from error
        if not isinstance(data, dict) or set(data) - {"accepted_by", "synthetic", "net_kinds"} or "net_kinds" not in data:
            raise CannotRun(f"the reasons table {path} is a mapping of accepted_by, net_kinds and optionally synthetic, and nothing else")
        self.accepted_by = data.get("accepted_by")
        unsigned = board_check.entry_unsigned({"accepted_by": self.accepted_by, "accepted_on": accepted_on}, None,
                                              datetime.date.today())
        if unsigned is not None:
            raise CannotRun(f"the reasons table {path} cannot sign an entry: {unsigned}")
        self.accepted_by = self.accepted_by.strip()
        self.accepted_on = accepted_on
        self.synthetic = data.get("synthetic", False)
        if not isinstance(self.synthetic, bool):
            raise CannotRun(f"the reasons table {path} gives synthetic as {self.synthetic!r}, where it is true or false")
        kinds = data["net_kinds"]
        if not isinstance(kinds, list):
            raise CannotRun(f"the reasons table {path} gives net_kinds that is no list")
        self.kinds: List[dict] = []
        names = set()
        for index, kind in enumerate(kinds):
            where = f"net_kinds[{index}]"
            if not isinstance(kind, dict) or set(kind) != {"kind", "nets", "bounded_by", "reasons"}:
                raise CannotRun(f"the reasons table {path} {where} is not a mapping of exactly kind, nets, bounded_by and reasons")
            for key in ("kind", "bounded_by"):
                if not isinstance(kind[key], str) or not kind[key].strip():
                    raise CannotRun(f"the reasons table {path} {where}.{key} is empty or not text")
            if kind["kind"].strip() in names:
                raise CannotRun(f"the reasons table {path} names the kind {kind['kind'].strip()} twice")
            names.add(kind["kind"].strip())
            nets = kind["nets"]
            if (not isinstance(nets, list) or not nets
                    or any(not isinstance(net, str) or not net.strip() for net in nets)):
                raise CannotRun(f"the reasons table {path} {where}.nets is not a list of net name patterns")
            reasons = kind["reasons"]
            if not isinstance(reasons, dict) or not reasons:
                raise CannotRun(f"the reasons table {path} {where}.reasons is not a mapping of a rule to its reason")
            for rule, reason in reasons.items():
                if rule not in ACCEPTED_RULES:
                    raise CannotRun(f"the reasons table {path} {where}.reasons names the rule {rule}, which the workmanship "
                                    f"acceptance record does not accept; the rules it accepts are {', '.join(ACCEPTED_RULES)}")
                if not isinstance(reason, str) or not reason.strip():
                    raise CannotRun(f"the reasons table {path} {where}.reasons.{rule} is empty or not text")
            self.kinds.append({"kind": kind["kind"].strip(), "nets": [net.strip() for net in nets],
                               "bounded_by": kind["bounded_by"].strip(),
                               "reasons": {rule: reason.strip() for rule, reason in reasons.items()}})

    def kinds_of(self, net: str) -> List[dict]:
        last = net.rsplit("/", 1)[-1]
        return [kind for kind in self.kinds
                if any(fnmatch.fnmatchcase(net, pattern) or fnmatch.fnmatchcase(last, pattern) for pattern in kind["nets"])]


# --- The record --------------------------------------------------------------------------------


def entry_blocks(lines: List[str]) -> List[Tuple[int, int, int]]:
    """Each entry of the record's text as (first line including its own comment lines, the `- rule:` line, end), in file order."""
    blocks = []
    for index, line in enumerate(lines):
        if not line.startswith("  - rule:"):
            continue
        start = index
        while start > 0 and lines[start - 1].startswith("  # ") and not lines[start - 1].startswith("  # ----"):
            start -= 1
        end = index + 1
        while end < len(lines) and lines[end].startswith("    "):
            end += 1
        blocks.append((start, index, end))
    return blocks


def read_record(path: str) -> Tuple[Optional[List[str]], List[dict]]:
    """The record's text lines and its entries; (None, []) when there is no record yet."""
    if not os.path.exists(path):
        return None, []
    yaml = board_check.require_yaml()
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        data = board_check.strict_yaml(yaml, text)
    except OSError as error:
        raise CannotRun(f"the record {path} cannot be read ({error})") from error
    except (yaml.YAMLError, board_check.RecordForm) as error:
        raise CannotRun(f"the record {path} is not readable YAML in the one form read ({error})") from error
    entries = data.get("accepted_workmanship") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(entries, list):
        raise CannotRun(f"the record {path} is not a mapping holding an accepted_workmanship list")
    lines = text.split("\n")
    if len(entry_blocks(lines)) != len(entries) or any(
            not isinstance(entry, dict) or set(entry) != set(ENTRY_KEYS) for entry in entries):
        raise CannotRun(f"the record {path} is not written as the block list of entries with the keys "
                        f"{', '.join(ENTRY_KEYS)} that this tool edits; correct it by hand first")
    return lines, entries


def quoted(text: str) -> str:
    return json.dumps(" ".join(text.split()), ensure_ascii=False)


def entry_text(entry: dict, example: str) -> str:
    return (f"  # {entry['rule']} at {entry['scope']}: {entry['count']} line(s) on the board. e.g. {' '.join(example.split())}\n"
            f"  - rule: {entry['rule']}\n    scope: {quoted(entry['scope'])}\n    count: {entry['count']}\n"
            f"    reason: {quoted(entry['reason'])}\n    bounded_by: {quoted(entry['bounded_by'])}\n"
            f"    accepted_by: {quoted(entry['accepted_by'])}\n    accepted_on: \"{entry['accepted_on']}\"\n")


# --- The generator ----------------------------------------------------------------------------


def line_nets(line: Line) -> List[str]:
    found = NET_PREFIX.match(line.where)
    nets = [found.group(1)] if found else NET_BRACKET.findall(line.where)
    return sorted(set(nets))


def plan(lines: Sequence[Line], design: str, mains: Mains, table: Table, existing: Sequence[dict]) -> dict:
    """What to write: entries, refusals, entries to remove and the count of failing lines of other rules."""
    groups: "OrderedDict[Tuple[str, str], List[Line]]" = OrderedDict()
    refused, not_covered, removed = [], 0, []
    unplaced = 0
    stale = set()
    for line in lines:
        if line.kind != "VIOLATION" or line.design != design:
            continue
        if line.rule == "workmanship_acceptance":
            found = STALE.search(line.where)
            if found and "is used by no line" in line.message:
                stale.add(int(found.group(1)))
            continue
        if line.rule not in ACCEPTED_RULES:
            not_covered += 1
            continue
        nets = line_nets(line)
        points = [(float(x), float(y)) for x, y in POSITION.findall(line.where)]
        unplaced += 0 if points else 1
        why = [reason for reason in [mains.net_why(net) for net in nets] + [mains.position_why(points)] if reason]
        if why:
            refused.append({"rule": line.rule, "scope": ", ".join(nets), "location": line.where,
                            "why": "; ".join(why) + "; a mains line is never entered"})
        elif len(nets) != 1:
            refused.append({"rule": line.rule, "scope": ", ".join(nets), "location": line.where,
                            "why": ("the line names no net" if not nets else f"the line names {len(nets)} nets")
                            + ", so no net kind of the table gives it a reason"})
        else:
            groups.setdefault((line.rule, nets[0]), []).append(line)
    entries = []
    taken = {(entry["rule"].strip(), entry["scope"].strip()) for index, entry in enumerate(existing) if index not in stale}
    for (rule, net), group in groups.items():
        kinds = table.kinds_of(net)
        why = None
        if not kinds:
            why = f"the net {net} is in no net kind of the reasons table"
        elif len(kinds) > 1:
            why = f"the net {net} is in more than one net kind of the reasons table ({', '.join(k['kind'] for k in kinds)})"
        elif rule not in kinds[0]["reasons"]:
            why = f"the net kind {kinds[0]['kind']} of the reasons table has no reason for the rule {rule}"
        elif (rule, net) in taken:
            why = (f"a signed entry for {rule} at {net} already exists and is exhausted; a signed count is never raised, "
                   "so the owner decides these lines")
        if why:
            refused.extend({"rule": rule, "scope": net, "location": line.where, "why": why} for line in group)
            continue
        kind = kinds[0]
        entries.append({"rule": rule, "scope": net, "count": len(group), "reason": kind["reasons"][rule],
                        "bounded_by": kind["bounded_by"], "accepted_by": table.accepted_by,
                        "accepted_on": table.accepted_on.isoformat(), "kind": kind["kind"],
                        "example": group[0].message})
    for index in sorted(stale):
        if index < len(existing):
            removed.append({"index": index, "rule": existing[index]["rule"].strip(), "scope": existing[index]["scope"].strip()})
    return {"entries": entries, "refused": refused, "removed": removed, "not_covered": not_covered, "no_position": unplaced}


def write_record(path: str, text_lines: Optional[List[str]], plan_: dict, synthetic: bool) -> None:
    """The record with the stale entries cut out and the new entries appended; a missing record is made."""
    if text_lines is None:
        text_lines = ["accepted_workmanship: []"] + (["synthetic: true"] if synthetic else []) + [""]
    for item in sorted(plan_["removed"], key=lambda removed: -removed["index"]):
        start, _, end = entry_blocks(text_lines)[item["index"]]
        del text_lines[start:end]
    text = "\n".join(text_lines)
    if not text.endswith("\n"):
        text += "\n"
    new = "".join(entry_text(entry, entry["example"]) for entry in plan_["entries"])
    if new:
        text = insert_entries(text, new)
    elif not entry_blocks(text.split("\n")):
        text = re.sub(r"^accepted_workmanship:[ \t]*$", "accepted_workmanship: []", text, flags=re.M)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def insert_entries(text: str, new: str) -> str:
    """`new` placed after the last entry of the record's list, or just under its key when the list is empty."""
    lines = text.split("\n")
    blocks = entry_blocks(lines)
    if blocks:
        position = blocks[-1][2]
    else:
        position = next(index for index, line in enumerate(lines) if line.startswith("accepted_workmanship:")) + 1
        if lines[position - 1].strip() != "accepted_workmanship:":
            lines[position - 1] = "accepted_workmanship:"
    lines[position:position] = new.rstrip("\n").split("\n")
    return "\n".join(lines)


def design_of(lines: Sequence[Line], designs: Sequence[str], given: Optional[str]) -> str:
    if given is not None:
        if given not in designs:
            raise CannotRun(f"the log names no design {given}; it names {', '.join(designs)}")
        return given
    if len(set(designs)) != 1:
        raise CannotRun(f"the log names several designs ({', '.join(sorted(set(designs)))}); name the board's with --design")
    return designs[0]


def run(args, out) -> int:
    log, designs = read_log(args.log)
    design = design_of(log, designs, args.design)
    when = datetime.date.today()
    if args.accepted_on:
        try:
            when = datetime.date.fromisoformat(args.accepted_on)
        except ValueError as error:
            raise CannotRun(f"--accepted-on {args.accepted_on} is not a date written YYYY-MM-DD") from error
    table = Table(args.table, when)
    project = locked_copper.read_project(args.project)
    layout = locked_copper.read_layout(args.board)
    regions = args.mains_regions or [MAINS_REGION_DEFAULT]
    mains = Mains(project, layout, args.mains_classes or [MAINS_CLASS_DEFAULT], regions, args.board)
    record = args.record or os.path.join(os.path.dirname(os.path.abspath(args.board)), RECORD_NAME)
    text_lines, existing = read_record(record)
    result = plan(log, design, mains, table, existing)
    held = bool(result["refused"])
    write = not args.dry_run and (not held or args.partial) and (result["entries"] or result["removed"])
    if write:
        write_record(record, text_lines, result, table.synthetic)
    state = "FAIL" if held else "PASS"
    summary = (f"{len(result['entries'])} entries {'would be ' if args.dry_run else ''}written for "
               f"{sum(e['count'] for e in result['entries'])} lines, {len(result['refused'])} lines refused, "
               f"{len(result['removed'])} stale entries removed, {result['not_covered']} failing lines of other rules not covered")
    if result["no_position"]:
        print(f"NOTE | {result['no_position']} failing line{'s' if result['no_position'] != 1 else ''} gave no position, so "
              "whether they lie in a mains region could not be told and they were judged by net only", file=sys.stderr)
    if args.format == "json":
        print(json.dumps({"result": state, "design": design, "record": record, "written": bool(write),
                          "entries": [{key: entry[key] for key in ("rule", "scope", "count", "kind", "reason")}
                                      for entry in result["entries"]],
                          "refused": result["refused"], "removed": result["removed"],
                          "not_covered": result["not_covered"], "no_position": result["no_position"], "detail": summary}, indent=2), file=out)
    else:
        for entry in result["entries"]:
            print(f"ENTRY | {entry['rule']} | {entry['scope']} | {entry['count']} | {entry['kind']}", file=out)
        for item in result["refused"]:
            print(f"REFUSED | {item['rule']} | {board_check.clean(item['location'])} | {board_check.clean(item['why'])}", file=out)
        for item in result["removed"]:
            print(f"REMOVED | {item['rule']} | {item['scope']} | stale entry {item['index']}", file=out)
        print(f"RESULT | {state} | {summary}", file=out)
    return 1 if held else 0


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", required=True, help="the output of the pre-order check (board_check.py) on the board as it stands")
    parser.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
    parser.add_argument("--project", required=True, help="the layout's project file (.kicad_pro)")
    parser.add_argument("--table", required=True, help="the board's reasons table, a YAML file in its folder")
    parser.add_argument("--record", help=f"the workmanship acceptance record to extend (default: {RECORD_NAME} beside the board)")
    parser.add_argument("--design", help="the design's project path as the log prints it, when the log names several")
    parser.add_argument("--mains-class", dest="mains_classes", action="append", metavar="PATTERN",
                        help=f"a net class, or a pattern of class names, that is mains; give each (default: {MAINS_CLASS_DEFAULT})")
    parser.add_argument("--mains-region", dest="mains_regions", action="append", metavar="NAME",
                        help=f"text a rule area's name contains, in any case, for it to be a mains region: every rule area whose name contains it is one; give each (default: {MAINS_REGION_DEFAULT}, "
                             "and a rule area must match each when the project declares MAINS present)")
    parser.add_argument("--accepted-on", metavar="DATE", help="the date each entry is signed, YYYY-MM-DD (default: today)")
    parser.add_argument("--partial", action="store_true", help="write the entries that can be justified even when other lines are refused")
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        return run(args, out)
    except locked_copper.Unreadable as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        if args.format == "json":
            print(json.dumps({"result": "CANNOT RUN", "detail": board_check.clean(str(error))}, indent=2), file=out)
        return 2
    except CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        if args.format == "json":
            print(json.dumps({"result": "CANNOT RUN", "detail": board_check.clean(str(error))}, indent=2), file=out)
        return 2


if __name__ == "__main__":
    sys.exit(main())
