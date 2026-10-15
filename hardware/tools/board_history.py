#!/usr/bin/env python3
"""The placement and critical routing history check: a board's layout plan read against the repository's history.

The placement section and the critical routing section of a board's
layout-plan.md each say they were written before something happened to the
board: the placement before its first track, each pass of the critical routing
before the router ran. Neither is taken on its word. This command finds those
moments in the history of the board file itself, reading every version of it
reachable from HEAD, and judges each section as it stood in the commit before:

- The first track, a commit whose board carries a straight track, an arc, a
  via or a copper pour while no commit before it does. A pour is a zone on a
  copper layer that is not a rule area, an unfilled outline included; a rule
  area, a zone carrying a keepout, carries no net and is no copper, and a zone
  on a layer that is no copper is no pour. Copper in the root
  commit, first appearing on two separate lines of history, and first
  appearing in a merge commit, fail. While no commit carries any, the
  placement section is judged as it stands at HEAD.
- The first placement, the first commit whose board holds a footprint, found
  from the history alone and never from the placement section, and the plan
  in the commit before it. A footprint in the root commit, footprints first
  appearing on two separate lines of history or in a merge commit, a first
  placement that does not come before the commit the placement section is
  judged in, and no readable floorplan in the commit before it, fail.
- The plan, the floorplan in the commit the placement section is judged in,
  held to the floorplan in the commit before the first placement: the same
  regions, the same bounds for each and the same parts in each, the only
  difference allowed being a reference appended to a region's parts, with no
  bound changed and no reference removed or moved between regions, which the
  floorplan lists in each commit just before its footprint first appears on
  the board, that commit coming after the commit before the first placement.
  The floorplan is read as the commit before the first copper holds it, so a
  part appended after that copper is not compared.
- The placement section, in the commit before the first track, holding at
  least two candidates and as it is now. Each candidate's commit is in the
  history, comes before the first track, holds the board, places its parts
  differently from every other candidate, by reference, position, angle and
  side and not by the bytes of the board file, and is named by its Renders;
  its recorded totals and parts outside are the measures recomputed from that
  commit's board, against the floorplan of the commit the section is judged in
  with the references the plan appended removed where the candidate's board
  does not hold them, with the placement view's own arithmetic
  (board_placement.py); its verdict table has one row for every placement
  item, each verdict pass, fail or not applicable, a not applicable only for
  an item the plan marks no; and the chosen candidate has no part outside and
  every footprint where the first track's commit holds it.
- The critical routing section's passes, numbered from 1 and only ever
  appended. Each pass's Board judged commit is on HEAD's line of history, the
  first holding critical copper and all of it locked, a later one following
  the previous pass's router commit with no unlocked copper added or changed
  between, a merge bringing it from another line among them. A pass's router
  commit is the first after its Board judged commit that adds or changes an
  unlocked track, arc or via, since the router's copper is never locked and
  every critical item is; that copper first appearing on two lines of
  history, or in a merge commit, fails. The pass is judged as it stood in the
  commit before the router's, and only the last pass may have none, when it
  is judged at HEAD; with --routed the router has run, and a last pass with
  none fails too. Every checklist item of the commit the pass is judged in
  appears in it exactly once, as a verdict row or in its list of items
  bearing on no critical net, and every fail has a later verdict with a
  commit putting it right before the router ran.

A commit a record cites that a squash, rebase or force-push left out of the
history is reported as not in it, so the check fails closed on a rewritten
branch. It needs git and Python only. It reads the board and its layout plan as
HEAD holds them, and refuses a board or plan that differs from HEAD, a shallow
clone, and a board it cannot read.

    board_history.py --board B.kicad_pcb [--routed] [--json]

Every check is one line, CHECK | <check> | PASS or FAIL | <detail>, a result
line comes last, and the exit status is the verdict: 0 when every check
passes, 1 when any fails, 2 when the command is refused. With --json the same
verdicts are printed as one JSON document. With --routed, a board on which
the router has not been shown to run, with no critical routing section or a
last pass with no router commit, fails rather than passing as router not yet
run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import board_placement  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402
from board_geometry import Unreadable  # noqa: E402

#: The design method, from the repository's root, whose catalogue gives the checklist.
METHOD = "docs/board-design-method.md"
#: The kinds of copper a pass holds locked and whose unlocked appearance is the router's commit; a zone is not one.
#: The first-copper search also counts a pour (carries_copper), which this set must not, or an unlocked non-critical
#: pour would be read as the router's commit.
TRACKS = ("track", "arc", "via")

PLACEMENT = "Placement"
CRITICAL = "Critical routing"
CANDIDATE = re.compile(r"### Candidate (\d+)")
PASS = re.compile(r"### Pass (\d+)")
COMMIT = re.compile(r"\b[0-9a-f]{7,40}\b")
CATALOGUE_ITEM = re.compile(r"^#### ([A-Z]+-\d+)\. ", re.M)
JUDGED_ON = re.compile(r"^- \*\*Judged on:\*\* (.*)$", re.M)
#: An item a pass lists as bearing on no critical net, with its reason: - `ITEM`: why.
LISTED = re.compile(r"^[-*]\s+`?([A-Z]+-\d+)`?:\s*\S")
#: The measures lines a candidate records: the totals and every part outside.
MEASURED = ("LENGTH | ", "CROSSINGS | ", "OUTSIDE | ")
#: One verdict of a verdict cell, and the commit it was reached at.
STEP = re.compile(r"(pass|fail|not applicable|cannot judge)(?: at ([0-9a-f]{7,40}))?")

PLACEMENT_TABLE = ["Item", "Verdict", "Rests on", "Why"]
CRITICAL_TABLE = ["Item", "Kind", "Severity", "Verdict", "Rests on", "Why"]


def field(name: str):
    return re.compile(r"^(?:[-*]\s+)?\*\*" + re.escape(name) + r"\*\*:?\s*(.*)$")


# --- The repository's history ---------------------------------------------------------


class History:
    """The commits reachable from HEAD, and the files they hold, read through git."""

    def __init__(self, git: str, root: str, work: str):
        self.git, self.root, self.work = git, root, work
        self.layouts: Dict[str, list] = {}
        listed = self.run("rev-list", "--topo-order", "--reverse", "--parents", "HEAD").split("\n")
        self.order = [line.split()[0] for line in listed if line]
        self.parents = {line.split()[0]: line.split()[1:] for line in listed if line}

    def run(self, *args: str, stdin: Optional[str] = None) -> str:
        result = subprocess.run([self.git, "-C", self.root, *args], input=stdin, capture_output=True, text=True)
        if result.returncode != 0:
            raise CannotRun(f"git {' '.join(args[:3])} failed in {self.root}: {result.stderr.strip()}")
        return result.stdout

    def resolve(self, name: str) -> Optional[str]:
        result = subprocess.run([self.git, "-C", self.root, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"],
                                capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def is_ancestor(self, older: str, newer: str) -> bool:
        return subprocess.run([self.git, "-C", self.root, "merge-base", "--is-ancestor", older, newer],
                              capture_output=True).returncode == 0

    def ancestry(self, older: str, newer: str) -> List[str]:
        """The commits after `older` and up to `newer` that descend from `older`, oldest first."""
        return [line for line in self.run("rev-list", "--topo-order", "--reverse", "--ancestry-path",
                                          f"{older}..{newer}").split() if line]

    def blobs(self, commits: Sequence[str], path: str) -> Dict[str, Optional[str]]:
        """The object each commit holds at `path`, or None where it holds none."""
        out = self.run("cat-file", "--batch-check=%(objectname) %(objecttype)",
                       stdin="".join(f"{commit}:{path}\n" for commit in commits)).splitlines()
        return {commit: (line.split()[0] if line.endswith(" blob") else None) for commit, line in zip(commits, out)}

    def text(self, commit: str, path: str) -> Optional[str]:
        result = subprocess.run([self.git, "-C", self.root, "cat-file", "blob", f"{commit}:{path}"], capture_output=True)
        if result.returncode != 0:
            return None
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as error:
            raise Unreadable(f"{path} at {commit} is not UTF-8 text ({error})") from error

    def file(self, commit: str, path: str) -> Optional[str]:
        """A file as `commit` holds it, written into the work folder; its path there, or None when it holds none."""
        text = self.text(commit, path)
        if text is None:
            return None
        local = os.path.join(self.work, commit, path)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, "w", encoding="utf-8") as handle:
            handle.write(text)
        return local

    def layout(self, commit: str, path: str) -> list:
        """The board as `commit` holds it; Unreadable when it holds none or it cannot be read."""
        blob = self.blobs([commit], path)[commit]
        if blob is None:
            raise Unreadable(f"{commit} holds no {path}")
        if blob not in self.layouts:
            self.layouts[blob] = locked_copper.read_layout(self.file(commit, path))
        return self.layouts[blob]

    def copper(self, commit: str, path: str) -> List[dict]:
        return locked_copper.copper(self.layout(commit, path), f"{path} at {commit}")


def tracks(items: List[dict]) -> List[dict]:
    return [item for item in items if item["kind"] in TRACKS]


def on_copper(node: list) -> bool:
    """Whether the zone is drawn on a copper layer, one whose name ends in `.Cu`, as `(layer ...)` or `(layers ...)`."""
    names = []
    for key in ("layer", "layers"):
        found = sexpr.child(node, key)
        names += [str(name) for name in found[1:]] if found else []
    return any(name.endswith(".Cu") for name in names)


def pours(layout: list) -> List[list]:
    """The zones the board carries at its top level that are copper: every zone on a copper layer but a rule area, a
    zone carrying a keepout, which carries no net. A zone on a layer that is no copper, silkscreen or mask for one, is
    no pour. An unfilled outline is a pour too, since the outline is what a designer draws."""
    return [node for node in layout[1:] if sexpr.head(node) == "zone" and sexpr.child(node, "keepout") is None
            and on_copper(node)]


def references(layout: list) -> set:
    """The reference of every footprint on the board."""
    return {board_geometry.reference(node).strip() for node in sexpr.children(layout, "footprint")}


def unlocked(items: List[dict]) -> Counter:
    """The unlocked tracks, arcs and vias, each by all it is read by, counted."""
    return Counter(json.dumps(item, sort_keys=True) for item in tracks(items) if not item["locked"])


def short(commit: str) -> str:
    return commit[:12]


# --- Reading the layout plan and the method --------------------------------------------------


def section(text: Optional[str], heading: str) -> Optional[List[str]]:
    """The non-blank lines of the `## heading` section, its heading among them, up to the next `## ` heading; a heading
    given twice brings both sections' lines, each heading among them."""
    if text is None:
        return None
    found, inside = None, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.rstrip() == f"## {heading}"
            if inside and found is None:
                found = []
        if inside and line.strip():
            found.append(line.rstrip())
    return found


def subsections(lines: List[str], pattern) -> Tuple[List[str], List[Tuple[int, List[str]]], List[str]]:
    """The lines before the first `### ` heading, each subsection `pattern` heads as (number, lines), and every other
    `### ` heading."""
    before, found, other = [], [], []
    for line in lines[1:]:
        if line.startswith("### "):
            match = pattern.fullmatch(line.strip())
            if match:
                found.append((int(match.group(1)), [line]))
                continue
            other.append(line)
        (found[-1][1] if found else before).append(line)
    return before, found, other


def table(lines: List[str], header: List[str]) -> Tuple[Optional[int], List[List[str]], List[str]]:
    """The table `header` heads in `lines`: the index of its header line, its rows, and every way it cannot be read."""
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and board_placement.cells(line) == header:
            separator = board_placement.cells(lines[index + 1]) if index + 1 < len(lines) else []
            if len(separator) != len(header) or not all(re.fullmatch(r":?-+:?", cell) for cell in separator):
                return index, [], ["its verdict table has no separator row of dashes under its header"]
            rows, faults = [], []
            for row in lines[index + 2:]:
                if not row.strip().startswith("|"):
                    break
                cells = board_placement.cells(row)
                if len(cells) != len(header):
                    faults.append(f"its verdict table row '{clean(row)}' has {len(cells)} cells where its header has "
                                  f"{len(header)}")
                else:
                    rows.append(cells)
            return index, rows, faults
    return None, [], [f"it holds no verdict table headed | {' | '.join(header)} |"]


def catalogue(text: Optional[str]) -> Dict[str, str]:
    """Each catalogue item of the method, by identifier, with its Judged on line."""
    if text is None:
        return {}
    marks = list(CATALOGUE_ITEM.finditer(text))
    found = {}
    for index, mark in enumerate(marks):
        body = text[mark.end():marks[index + 1].start() if index + 1 < len(marks) else len(text)]
        judged = JUDGED_ON.search(body)
        found[mark.group(1)] = judged.group(1) if judged else ""
    return found


def plan_rows(text: Optional[str], header: Sequence[str]) -> List[Dict[str, str]]:
    """The rows of the layout plan's table whose header begins with `header`, each by column name."""
    lines = (text or "").splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and board_placement.cells(line)[:len(header)] == list(header):
            names = board_placement.cells(line)
            rows = []
            for row in lines[index + 2:]:
                if not row.strip().startswith("|"):
                    break
                rows.append(dict(zip(names, board_placement.cells(row))))
            return rows
    return []


def own_items(text: Optional[str]) -> Dict[str, str]:
    """The board's own items, by identifier, with their Judged on cell; none for the table's one `none` row."""
    return {row["Item"]: row.get("Judged on", "") for row in plan_rows(text, ["Item", "Applies when"])
            if row.get("Item") and row["Item"].lower() != "none"}


def fields(lines: List[str], names: Sequence[str]) -> Dict[str, Tuple[int, str]]:
    """Each named field's first line in `lines`: (its index, its value)."""
    found = {}
    for name in names:
        pattern = field(name)
        for index, line in enumerate(lines):
            match = pattern.match(line.strip())
            if match:
                found[name] = (index, match.group(1).strip())
                break
    return found


def cited(value: str) -> Optional[str]:
    match = COMMIT.search(value.replace("`", ""))
    return match.group(0) if match else None


def steps(cell: str) -> Optional[List[Tuple[str, Optional[str]]]]:
    """A verdict cell's verdicts in order, each with the commit it was reached at, or None when it cannot be read."""
    found = []
    for part in re.split(r",\s*then\s+", cell.replace("`", "").strip().lower()):
        match = STEP.fullmatch(part.strip())
        if not match:
            return None
        found.append((match.group(1), match.group(2)))
    return found


# --- The checks --------------------------------------------------------------------------


class Report:
    """Every check's verdict, in the order judged."""

    def __init__(self):
        self.checks: List[dict] = []
        self.notes: List[str] = []

    def add(self, name: str, faults: List[str], passed: str) -> bool:
        for fault in faults:
            self.checks.append({"check": name, "verdict": "FAIL", "detail": fault})
        if not faults:
            self.checks.append({"check": name, "verdict": "PASS", "detail": passed})
        return not faults

    def failed(self) -> int:
        return sum(1 for check in self.checks if check["verdict"] == "FAIL")


def first_holding(history: History, commits: List[str], holds) -> List[str]:
    """The commits of `commits`, oldest first, for which `holds` is true while it is for none of their parents among
    them: where it first appears on each line of history."""
    ever: Dict[str, bool] = {}
    firsts = []
    for commit in commits:
        here = holds(commit)
        before = any(ever.get(parent, False) for parent in history.parents[commit])
        ever[commit] = here or before
        if here and not before:
            firsts.append(commit)
    return firsts


def first_track(history: History, board: str, report: Report) -> Tuple[bool, Optional[str]]:
    """Whether any commit's board carries copper, a track, arc, via or pour, and the first commit to carry it when it
    can be told."""
    blobs = history.blobs(history.order, board)
    carries: Dict[str, bool] = {}
    faults = []

    def holds(commit: str) -> bool:
        blob = blobs[commit]
        if blob is not None and blob not in carries:
            try:
                layout = history.layout(commit, board)
                carries[blob] = bool(tracks(locked_copper.copper(layout, f"{board} at {commit}")) or pours(layout))
            except Unreadable as error:
                faults.append(f"the board at {short(commit)} cannot be read, so whether it carries copper cannot be "
                              f"told: {error}")
                carries[blob] = False
        return blob is not None and carries[blob]

    firsts = first_holding(history, history.order, holds)
    for commit in firsts:
        if not history.parents[commit]:
            faults.append(f"the root commit {short(commit)} carries a track, arc, via or pour, so nothing was "
                          "committed before the first track")
        elif len(history.parents[commit]) > 1:
            faults.append(f"a track, arc, via or pour first appears in the merge commit {short(commit)}, which none of "
                          f"its {len(history.parents[commit])} parents carries, so there is no one commit before the "
                          "first track")
    if len(firsts) > 1:
        faults.append(f"a track, arc, via or pour first appears on {len(firsts)} separate lines of history, at "
                      f"{', '.join(short(commit) for commit in firsts)}, so there is no one first track before which "
                      "the placement was recorded")
    if not firsts:
        report.add("first track", faults, "no commit carries a track, arc, via or pour yet, so the placement section is "
                                          "judged as it stands at HEAD")
        return False, None
    if report.add("first track", faults, f"{short(firsts[0])} is the first commit carrying a track, arc, via or pour, "
                                         "and the placement section is judged as it stood in the commit before it"):
        return True, firsts[0]
    return True, None


def first_placement(history: History, board: str, at: str, report: Report) -> Optional[str]:
    """The commit before the first commit whose board holds a footprint, the commit the plan is judged in, found from
    the history alone; None, with the reasons reported, when there is no one such commit."""
    blobs = history.blobs(history.order, board)
    held: Dict[str, bool] = {}

    def holds(commit: str) -> bool:
        blob = blobs[commit]
        if blob is not None and blob not in held:
            try:
                held[blob] = bool(sexpr.children(history.layout(commit, board), "footprint"))
            except Unreadable:
                held[blob] = False  # first track has already reported a board version that cannot be read
        return blob is not None and held[blob]

    firsts = first_holding(history, history.order, holds)
    faults = []
    for commit in firsts:
        if not history.parents[commit]:
            faults.append(f"the root commit {short(commit)} already holds a footprint, so no plan was committed before "
                          "the first placement")
        elif len(history.parents[commit]) > 1:
            faults.append(f"a footprint first appears in the merge commit {short(commit)}, which none of its "
                          f"{len(history.parents[commit])} parents holds, so there is no one commit before the first "
                          "placement to judge the plan in")
    if len(firsts) > 1:
        faults.append(f"a footprint first appears on {len(firsts)} separate lines of history, at "
                      f"{', '.join(short(commit) for commit in firsts)}, so there is no one first placement before "
                      "which the plan was committed")
    if not firsts:
        faults.append("no commit's board holds a footprint, so there is no placement for the plan to have come before")
    anchor = history.parents[firsts[0]][0] if len(firsts) == 1 and len(history.parents[firsts[0]]) == 1 else None
    if anchor is not None and not history.is_ancestor(anchor, at):
        faults.append(f"the commit before the first placement, {short(anchor)}, is not an ancestor of {short(at)}, the "
                      "commit the placement section is judged in, so the plan was not committed before it")
    if report.add("first placement", faults, f"{short(firsts[0]) if firsts else '?'} is the first commit whose board "
                                             "holds a footprint, and the plan is judged as it stood in the commit "
                                             "before it" + (f", {short(anchor)}" if anchor else "")):
        return anchor
    return None


def read_plan(history: History, commit: str, plan: str) -> List[dict]:
    """The floorplan of the layout plan as `commit` holds it; Unreadable when it holds none or it cannot be read."""
    local = history.file(commit, plan)
    if local is None:
        raise Unreadable(f"{plan} is not in the commit {short(commit)}")
    return board_placement.floorplan(local)


def bounds_key(region: dict):
    return None if region["bounds"] is None else sorted(tuple(rectangle) for rectangle in region["bounds"])


def plan_changes(then: List[dict], now: List[dict]) -> Tuple[List[str], Dict[str, List[str]]]:
    """How the floorplan `now` differs from `then` other than by references appended to a region's parts: every such
    difference, and the references it appends, each with the regions it is appended to."""
    faults, appended = [], {}
    names_then, names_now = [region["name"] for region in then], [region["name"] for region in now]
    if sorted(names_then) != sorted(names_now):
        faults.append(f"the floorplan's region rows are {', '.join(names_now) or 'none'} where the plan before "
                      f"placement has {', '.join(names_then) or 'none'}")
    before = {region["name"]: region for region in then}
    listed = {part for region in then for part in region["parts"]}
    for region in now:
        was = before.get(region["name"])
        if was is None:
            continue
        if bounds_key(was) != bounds_key(region):
            faults.append(f"the region '{region['name']}' has the bounds {board_placement.bounds_text(region)} where "
                          f"the plan before placement gives {board_placement.bounds_text(was)}")
        faults += [f"{part} is listed in the region '{region['name']}' in the plan before placement and not now"
                   for part in was["parts"] if part not in region["parts"]]
        for part in region["parts"]:
            if part in was["parts"]:
                continue
            if part in listed:
                holders = [other["name"] for other in then if part in other["parts"]]
                faults.append(f"{part} is listed in the region '{region['name']}', where the plan before placement "
                              f"lists it only in {', '.join(repr(name) for name in holders)}: a reference is not moved "
                              "between regions")
            else:
                appended.setdefault(part, []).append(region["name"])
    return faults, appended


def first_commits(history: History, path: str, holds_in) -> List[str]:
    """Where `holds_in`, true of the file `path` as a commit holds it, first becomes true on each line of history."""
    blobs = history.blobs(history.order, path)
    seen: Dict[str, bool] = {}

    def holds(commit: str) -> bool:
        blob = blobs[commit]
        if blob is not None and blob not in seen:
            try:
                seen[blob] = holds_in(commit)
            except Unreadable:
                seen[blob] = False  # a version that cannot be read lists and holds nothing
        return blob is not None and seen[blob]

    return first_holding(history, history.order, holds)


def amended_in(history: History, plan: str, anchor: str, commit: str, part: str) -> bool:
    """Whether `commit` descends from `anchor` and the floorplan it holds lists `part` in a region."""
    if not history.is_ancestor(anchor, commit):
        return False
    try:
        return any(part in region["parts"] for region in read_plan(history, commit, plan))
    except Unreadable:
        return False


def judge_plan(history: History, board: str, plan: str, anchor: Optional[str], at: str, where: str,
               regions: Optional[List[dict]], unread: Optional[Unreadable], report: Report) -> Dict[str, List[str]]:
    """The floorplan in the commit the placement section is judged in, held to the one in the commit before the first
    placement; the references it appends to a region's parts, each with its regions. Without the commit before the
    first placement there is nothing to hold it to and no reference is taken as appended."""
    if anchor is None:
        return {}
    faults, appended = [], {}
    try:
        then = read_plan(history, anchor, plan)
    except Unreadable as error:
        then = None
        faults.append(f"{plan} in the commit before the first placement ({short(anchor)}) holds no readable floorplan, "
                      f"so the plan was not committed before placement: {error}")
    if regions is None:
        faults.append(f"the floorplan in {where} cannot be read, so it cannot be held to the plan before placement: "
                      f"{unread}")
    if then is not None and regions is not None:
        faults, appended = plan_changes(then, regions)
        for part in sorted(appended):
            holders = first_commits(history, board, lambda commit, part=part: part in references(
                history.layout(commit, board)))
            for holder in holders:
                parents = history.parents[holder]
                unlisted = [parent for parent in parents if not amended_in(history, plan, anchor, parent, part)]
                if unlisted or not parents:
                    faults.append(f"{part} is appended to the parts of {', '.join(repr(n) for n in appended[part])} "
                                  f"and its footprint first appears on the board at {short(holder)}, but the plan "
                                  f"does not list it, after the commit before the first placement ({short(anchor)}), "
                                  f"in {', '.join(short(parent) for parent in unlisted) or 'a commit before it'}: the "
                                  "amendment is committed after that commit and before the part is placed, and the "
                                  "plan keeps it until then")
    report.add("plan before placement", faults,
               f"the floorplan in {where} is the one in the commit before the first placement ({short(anchor)})"
               + (f", with {', '.join(sorted(appended))} appended to its parts, each committed before its footprint "
                  "first appears on the board" if appended else ""))
    return appended


def parts_placed(layout: list) -> Dict[str, Tuple[str, str]]:
    """Each footprint's reference, with its position, angle and side as text."""
    found = {}
    for name, node in board_placement.footprints(layout).items():
        x, y, angle = board_geometry.placement(node, f"the footprint {name}")
        side = sexpr.child(node, "layer")
        found[name] = (f"({x:g}, {y:g}) at {angle:g} degrees", str(side[1]) if side and len(side) > 1 else "?")
    return found


def judge_placement(history: History, board: str, plan: str, first: Optional[str], report: Report) -> None:
    at = history.parents[first][0] if first else history.order[-1]
    where = f"the commit before the first track ({short(at)})" if first else f"HEAD ({short(at)})"
    try:
        regions, unread = read_plan(history, at, plan), None
    except Unreadable as error:
        regions, unread = None, error
    appended = judge_plan(history, board, plan, first_placement(history, board, at, report), at, where, regions, unread,
                          report)
    then = section(history.text(at, plan), PLACEMENT)
    now = section(history.text(history.order[-1], plan), PLACEMENT)
    faults = []
    if then is None:
        faults.append(f"{plan} in {where} holds no `## {PLACEMENT}` section, so the placement was not recorded "
                      + ("before the first track" if first else "yet"))
    else:
        _, candidates, other = subsections(then, CANDIDATE)
        if not candidates:
            faults.append(f"the `## {PLACEMENT}` section in {where} holds no `### Candidate` heading")
        if then != now:
            faults.append(f"the `## {PLACEMENT}` section now differs from the one in {where}"
                          + (f", first at '{clean(difference(then, now))}'" if now else ", which is now gone")
                          + "; the section is not changed after the first track")
        faults += [f"the section holds the heading '{clean(line)}', which is no `### Candidate <n>`" for line in other]
        if then.count(f"## {PLACEMENT}") > 1:
            faults.append(f"{plan} in {where} gives the heading `## {PLACEMENT}` {then.count(f'## {PLACEMENT}')} times")
    report.add("placement section", faults, f"the section in {where} holds its candidates and is the section now")
    if then is None:
        return
    _, candidates, _ = subsections(then, CANDIDATE)
    method = history.text(at, METHOD)
    plan_text = history.text(at, plan)
    listed = catalogue(method)
    own = own_items(plan_text)
    items = {item for item, judged in list(listed.items()) + list(own.items()) if "`placement`" in judged}
    report.add("placement items", [] if items else [
        f"{METHOD} and {plan} in {where} name no item whose Judged on names `placement`"
        + ("" if method is not None else f"; {where} holds no {METHOD}") + ", so the verdicts have nothing to be judged "
        "against"], f"{len(items)} placement items, from {METHOD} and {plan} in {where}")
    applies = {row.get("Item"): row.get("Applies", "").strip().lower() for row in plan_rows(plan_text, ["Item", "Applies"])}

    numbers = [number for number, _ in candidates]
    faults = [f"the section records {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}, where a placement "
              "is chosen from at least two"] if len(candidates) < 2 else []
    faults += [f"candidate {number} is recorded {count} times" for number, count in Counter(numbers).items() if count > 1]
    report.add("candidates", faults, f"{len(candidates)} candidates")

    blobs, outside, placements = {}, {}, {}
    for number, lines in candidates:
        name = f"candidate {number}"
        given = fields(lines, ["Commit", "Renders", "Measures"])
        commit = resolved = None
        faults = []
        if "Commit" not in given or cited(given["Commit"][1]) is None:
            faults.append(f"{name} names no commit in a **Commit** field")
        else:
            commit = cited(given["Commit"][1])
            resolved = history.resolve(commit)
            if resolved is None:
                faults.append(f"{name}'s commit {commit} is not in this repository: a squash, rebase or force-push "
                              "leaves the commits a record cites out of its history")
            elif not history.is_ancestor(resolved, history.order[-1]):
                faults.append(f"{name}'s commit {commit} is not in this repository's history from HEAD: a squash, "
                              "rebase or force-push left it off the branch's line of history")
            elif first and (resolved == first or not history.is_ancestor(resolved, first)):
                faults.append(f"{name}'s commit {commit} does not come before the first track, {short(first)}: "
                              + ("it is the first track's commit" if resolved == first else "it is not an ancestor of it"))
            elif history.blobs([resolved], board)[resolved] is None:
                faults.append(f"{name}'s commit {commit} does not hold the board {board}")
            else:
                blobs[number] = history.blobs([resolved], board)[resolved]
        if "Renders" not in given:
            faults.append(f"{name} has no **Renders** field giving the commands that render it from its commit")
        elif commit is not None:
            end = given["Measures"][0] if "Measures" in given and given["Measures"][0] > given["Renders"][0] else len(lines)
            if commit not in "\n".join(lines[given["Renders"][0]:end]):
                faults.append(f"{name}'s **Renders** does not name its own commit, {commit}, so its view was not "
                              "rendered from it")
        report.add(f"{name} commit", faults, f"{commit} comes before the first track, holds the board and is named by "
                                             "its Renders" if first else f"{commit} is on HEAD's line of history, holds "
                                             "the board and is named by its Renders")

        faults = []
        recorded = []
        if "Measures" not in given:
            faults.append(f"{name} has no **Measures** field")
        else:
            header, _, _ = table(lines, PLACEMENT_TABLE)
            end = header if header is not None and header > given["Measures"][0] else len(lines)
            for line in lines[given["Measures"][0]:end]:
                text = line.strip().strip("`").strip()
                text = re.sub(r"^(?:[-*]\s+)?\*\*Measures\*\*:?\s*", "", text).strip("`").strip()
                if text.startswith(MEASURED):
                    recorded.append(board_placement.clean_line(text))
        if number in blobs:
            try:
                if regions is None:
                    raise Unreadable(f"the floorplan of {plan} in {where} cannot be read: {unread}")
                layout = history.layout(resolved, board)
                held = references(layout)
                measured = board_placement.measured_placement(board, plan, layout, [
                    dict(region, parts=[part for part in region["parts"] if part in held or part not in appended])
                    for region in regions])
                placements[number] = parts_placed(layout)
                outside[number] = measured["outside"]
                expected = [line for line in board_placement.measure_lines(measured) if line.startswith(MEASURED)]
                missing = sorted((Counter(expected) - Counter(recorded)).elements())
                extra = sorted((Counter(recorded) - Counter(expected)).elements())
                faults += [f"{name} does not record '{line}', which its commit measures against the floorplan in "
                           f"{where}" for line in missing]
                faults += [f"{name} records '{line}', which its commit does not measure against the floorplan in "
                           f"{where}" for line in extra]
            except Unreadable as error:
                faults.append(f"{name} cannot be measured from its commit: {error}")
        elif "Measures" in given:
            faults.append(f"{name}'s measures cannot be recomputed without a commit holding the board")
        report.add(f"{name} measures", faults, f"its totals and parts outside are those its commit measures against "
                                               f"the floorplan in {where}")

        _, rows, faults = table(lines, PLACEMENT_TABLE)
        faults = [f"{name}: {fault}" for fault in faults]
        counted = Counter(row[0].strip("`") for row in rows)
        faults += [f"{name}'s verdict table has no row for the placement item {item}" for item in sorted(items - set(counted))]
        faults += [f"{name}'s verdict table has {count} rows for {item}" for item, count in sorted(counted.items())
                   if count > 1 and item in items]
        faults += [f"{name}'s verdict table names {item}, which is no placement item" for item in sorted(set(counted) - items)]
        for row in rows:
            verdict = row[1].replace("`", "").strip().lower()
            if verdict not in ("pass", "fail", "not applicable"):
                faults.append(f"{name} gives {row[0]} the verdict '{row[1]}', not pass, fail or not applicable")
            elif verdict == "not applicable" and applies.get(row[0].strip("`")) != "no":
                faults.append(f"{name} gives {row[0]} not applicable, and the plan table does not mark it no")
        report.add(f"{name} verdicts", faults, f"one verdict for each of the {len(items)} placement items")

    seen: Dict[tuple, int] = {}
    faults = []
    for number, placed in placements.items():
        key = tuple(sorted(placed.items()))
        if key in seen:
            faults.append(f"candidates {seen[key]} and {number} place every part alike, by reference, position, angle "
                          "and side, so they are one placement")
        seen.setdefault(key, number)
    report.add("distinct candidates", faults, "no two candidates place their parts alike")

    chosen_field = fields(then, ["Chosen"]).get("Chosen")
    chosen = re.match(r"`?(?:candidate\s+)?(\d+)", chosen_field[1], re.I) if chosen_field else None
    faults, chosen_commit = [], None
    if chosen is None:
        faults.append("the section names no chosen candidate in a **Chosen** field")
    elif int(chosen.group(1)) not in numbers:
        faults.append(f"the chosen candidate, {chosen.group(1)}, is not one the section records")
    else:
        number = int(chosen.group(1))
        if number not in outside:
            faults.append(f"the chosen candidate {number} could not be measured, so it is not shown to leave no part "
                          "outside its regions")
        else:
            faults += [f"the chosen candidate {number} leaves {part['reference']} outside its regions"
                       for part in outside[number]]
        lines = dict(candidates)[number]
        commit = cited(fields(lines, ["Commit"]).get("Commit", (0, ""))[1])
        chosen_commit = history.resolve(commit) if commit and number in blobs else None
    report.add("chosen", faults, f"candidate {chosen.group(1) if chosen else '?'} is recorded and leaves no part outside")

    faults = []
    against = first or history.order[-1]
    if chosen_commit is not None:
        try:
            was, now_placed = parts_placed(history.layout(chosen_commit, board)), parts_placed(history.layout(against, board))
            for name in sorted(set(was) | set(now_placed), key=board_placement.board_views.natural):
                if name not in now_placed:
                    faults.append(f"{name} is on the board in the chosen candidate and not at {short(against)}")
                elif name not in was:
                    faults.append(f"{name} is on the board at {short(against)} and not in the chosen candidate")
                elif was[name] != now_placed[name]:
                    faults.append(f"{name} is at {' on '.join(was[name])} in the chosen candidate, and at "
                                  f"{' on '.join(now_placed[name])} at {short(against)}")
        except Unreadable as error:
            faults.append(f"the parts cannot be compared: {error}")
    elif chosen is not None:
        faults.append("the chosen candidate has no commit holding the board to compare the parts with")
    else:
        faults.append("no candidate is chosen, so no placement is shown to be the board's")
    report.add("parts at first track" if first else "parts at HEAD", faults,
               f"every footprint at {short(against)} is where the chosen candidate put it")


def difference(old: List[str], new: List[str]) -> str:
    """The first line of `new` that `old` does not hold in its place, or the first line one holds beyond the other."""
    for was, now in zip(old, new):
        if was != now:
            return now
    longer = new if len(new) > len(old) else old
    return longer[min(len(old), len(new))] if len(old) != len(new) else ""


def judge_critical(history: History, board: str, plan: str, tracked: bool, routed: bool, report: Report) -> None:
    head = history.order[-1]
    lines = section(history.text(head, plan), CRITICAL)
    if lines is None:
        if tracked:
            report.add("critical routing section", [
                f"the board carries copper, a track, arc, via or pour, and {plan} holds no `## {CRITICAL}` section; "
                "the critical routing is judged and recorded before the router runs"], "")
        elif routed:
            report.add("critical routing section", [
                f"--routed says the router has run, and no commit carries a track, arc, via or pour and {plan} holds no "
                f"`## {CRITICAL}` section"], "")
        return
    before, passes, other = subsections(lines, PASS)
    faults = [f"the section holds '{clean(line)}' before its first `### Pass` heading" for line in before]
    faults += [f"the section holds the heading '{clean(line)}', which is no `### Pass <n>`" for line in other]
    if lines.count(f"## {CRITICAL}") > 1:
        faults.append(f"{plan} gives the heading `## {CRITICAL}` {lines.count(f'## {CRITICAL}')} times")
    numbers = [number for number, _ in passes]
    if not passes:
        faults.append("the section holds no `### Pass <n>` heading")
    elif numbers != list(range(1, len(numbers) + 1)):
        faults.append(f"the passes are numbered {', '.join(str(n) for n in numbers)}, not from 1 in order; a pass is "
                      "only ever appended, never removed or renumbered")
    report.add("critical routing section", faults, f"{len(passes)} pass{'es' if len(passes) != 1 else ''}, numbered "
                                                   "from 1")
    router: Optional[str] = None
    for index, (number, text) in enumerate(passes):
        name = f"pass {number}"
        last = index == len(passes) - 1
        given = fields(text, ["Board judged", "Views"])
        faults, judged = [], None
        if "Board judged" not in given or cited(given["Board judged"][1]) is None:
            faults.append(f"{name} names no commit in a **Board judged** field")
        else:
            commit = cited(given["Board judged"][1])
            judged = history.resolve(commit)
            if judged is None:
                faults.append(f"{name}'s Board judged commit {commit} is not in this repository: a squash, rebase or "
                              "force-push leaves the commits a record cites out of its history")
            elif not history.is_ancestor(judged, head):
                faults.append(f"{name}'s Board judged commit {commit} is not in this repository's history from HEAD: "
                              "it is on another branch, or a squash, rebase or force-push left it off this one")
                judged = None
        if "Views" not in given:
            faults.append(f"{name} has no **Views** field giving the commands that rendered its views")
        if judged is not None and index == 0:
            try:
                held = tracks(history.copper(judged, board))
                if not held:
                    faults.append(f"{name}'s Board judged commit {short(judged)} holds no track, arc or via")
                loose = [item for item in held if not item["locked"]]
                if loose:
                    faults.append(f"{name}'s Board judged commit {short(judged)} holds {len(loose)} unlocked tracks, "
                                  "arcs or vias, so its critical routing was not locked or the router had run")
            except Unreadable as error:
                faults.append(f"{name}'s Board judged commit cannot be read: {error}")
        if judged is not None and index > 0:
            if router is None:
                faults.append(f"{name} follows a pass whose router commit is not found")
            elif judged == router or not history.is_ancestor(router, judged):
                faults.append(f"{name}'s Board judged commit {short(judged)} does not follow pass {number - 1}'s router "
                              f"commit {short(router)}")
            else:
                try:
                    between = history.ancestry(router, judged)
                    line = set(between) | {router}
                    for commit in between:
                        added = unlocked(history.copper(commit, board)) - sum(
                            (unlocked(history.copper(parent, board)) for parent in history.parents[commit]
                             if parent in line), Counter())
                        if added:
                            faults.append(f"{short(commit)}, between pass {number - 1}'s router commit and {name}'s "
                                          f"Board judged commit, adds or changes {sum(added.values())} unlocked "
                                          "tracks, arcs or vias: the router ran again before the pass was judged")
                except Unreadable as error:
                    faults.append(f"the board between the passes cannot be read: {error}")
        report.add(f"{name} board judged", faults, f"{short(judged) if judged else '?'} is on HEAD's line of history "
                                                   + ("and holds critical copper, all of it locked" if index == 0 else
                                                      "and follows the previous pass's router commit with no unlocked "
                                                      "copper added between"))
        router = None
        faults, routers = [], []
        if judged is not None:
            try:
                base = unlocked(history.copper(judged, board))
                routers = first_holding(history, history.ancestry(judged, head),
                                        lambda commit: bool(unlocked(history.copper(commit, board)) - base))
            except Unreadable as error:
                faults.append(f"the board after {name}'s Board judged commit cannot be read: {error}")
        if len(routers) > 1:
            faults.append(f"the router's copper first appears on {len(routers)} separate lines of history after "
                          f"{name}'s Board judged commit, at {', '.join(short(commit) for commit in routers)}, so there "
                          "is no one router commit before which the pass was recorded")
        elif routers:
            router = routers[0]
            if len(history.parents[router]) > 1:
                faults.append(f"the router's copper first appears after {name}'s Board judged commit in the merge "
                              f"commit {short(router)}, joining {len(history.parents[router])} lines of history, so "
                              "there is no one commit before the router's to judge the pass in")
        stood = history.parents[router][0] if router is not None and not faults else head
        if not routers and not faults and judged is not None:
            if last and not routed:
                report.notes.append("router not yet run")
                report.add(f"{name} before router", [], "router not yet run: no commit after the Board judged commit "
                                                        "adds unlocked copper, so the pass is judged as it stands at HEAD")
            elif last:
                report.add(f"{name} before router", [f"--routed says the router has run, and no commit after {name}'s "
                                                     "Board judged commit adds unlocked copper: the router's copper is "
                                                     "not committed, or is locked"], "")
            else:
                report.add(f"{name} before router", [f"{name} has no router commit after its Board judged commit, and "
                                                     "only the last pass may have none"], "")
        elif router is not None and not faults:
            then = dict(subsections(section(history.text(stood, plan), CRITICAL) or [""], PASS)[1])
            if number not in then:
                faults.append(f"{name} is not in {plan} in the commit before the router's, {short(router)}^, so it "
                              "was not recorded before the router ran")
            elif then[number] != text:
                faults.append(f"{name} now differs from the pass in the commit before the router's, "
                              f"{short(router)}^, first at '{clean(difference(then[number], text))}'")
            report.add(f"{name} before router", faults, f"the pass is as it stood before the router's commit "
                                                        f"{short(router)}")
        else:
            report.add(f"{name} before router", faults or [f"{name}'s router commit cannot be found without its Board "
                                                           "judged commit"], "")
        judge_verdicts(history, plan, name, text, judged, router, stood, report)


def judge_verdicts(history: History, plan: str, name: str, text: List[str], judged: Optional[str],
                   router: Optional[str], stood: str, report: Report) -> None:
    head = history.order[-1]
    _, rows, faults = table(text, CRITICAL_TABLE)
    faults = [f"{name}: {fault}" for fault in faults]
    checklist = set(catalogue(history.text(stood, METHOD))) | set(own_items(history.text(stood, plan)))
    if not checklist:
        faults.append(f"{METHOD} and {plan} at {short(stood)} name no checklist item, so the pass has nothing to be "
                      "judged against")
    counted = Counter(row[0].strip("`") for row in rows)
    counted.update(match.group(1) for match in (LISTED.match(line.strip()) for line in text) if match)
    faults += [f"{name} neither judges {item} nor lists it as bearing on no critical net"
               for item in sorted(checklist - set(counted))]
    faults += [f"{name} gives {item} {count} times, in its table and its list together" for item, count in
               sorted(counted.items()) if count > 1 and item in checklist]
    faults += [f"{name} names {item}, which is no checklist item" for item in sorted(set(counted) - checklist)]
    for row in rows:
        found = steps(row[3])
        if found is None:
            faults.append(f"{name} gives {row[0]} the verdict '{row[3]}', not pass, fail, not applicable or cannot "
                          "judge, each later verdict written ', then <verdict> at <commit>'")
            continue
        for position, (verdict, _) in enumerate(found):
            after = found[position + 1] if position + 1 < len(found) else None
            if verdict == "fail" and (after is None or after[1] is None):
                faults.append(f"{name}'s fail for {row[0]} has no later verdict with the commit that put it right")
            elif verdict == "cannot judge" and after is None:
                faults.append(f"{name}'s cannot judge for {row[0]} has no later verdict")
        for verdict, commit in found[1:]:
            if commit is None:
                continue
            resolved = history.resolve(commit)
            if resolved is None or not history.is_ancestor(resolved, head):
                faults.append(f"{name} cites {commit} for {row[0]}, which is not in this repository's history from HEAD")
            elif judged is not None and (resolved == judged or not history.is_ancestor(judged, resolved)):
                faults.append(f"{name} cites {commit} for {row[0]}, which does not come after its Board judged commit")
            elif router is not None and (resolved == router or not history.is_ancestor(resolved, router)):
                faults.append(f"{name} cites {commit} for {row[0]}, which does not come before the router's commit "
                              f"{short(router)}")
    report.add(f"{name} verdicts", faults, f"every one of the {len(checklist)} checklist items at {short(stood)} judged "
                                           "or listed once, every fail put right before the router")


# --- Running it -----------------------------------------------------------------------------


def refusals(git: str, board: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    """The top of the work tree, and every reason the history cannot be judged."""
    try:
        board_check.require_python()
        root = os.path.realpath(board_check.require_git(git, os.path.dirname(os.path.abspath(board))))
    except CannotRun as error:
        return None, [("git", str(error))]
    shallow = subprocess.run([git, "-C", root, "rev-parse", "--is-shallow-repository"], capture_output=True, text=True)
    if shallow.stdout.strip() == "true":
        return root, [(root, "the repository is a shallow clone, which lacks the commits the records cite and the first "
                             "track's; fetch its whole history (git fetch --unshallow)")]
    if shallow.stdout.strip() != "false":
        return root, [(root, "git could not say whether the repository is a shallow clone (git 2.15 or newer can)")]
    if subprocess.run([git, "-C", root, "rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True).returncode:
        return root, [(root, "the repository has no commit")]
    rel = os.path.relpath(os.path.realpath(board), root)
    repository = board_check.Repository(root, board_check.tracked_files(git, root), git)
    found = []
    for path in (rel, os.path.join(os.path.dirname(rel), board_placement.PLAN)):
        why = repository.uncommitted(path)
        if why is not None:
            found.append((path, f"{why}; the history is judged as HEAD holds the board and its plan, so commit them"))
    if not found:
        try:
            locked_copper.read_layout(board)
        except Unreadable as error:
            found.append((rel, str(error)))
    return root, found


def judge(git: str, board: str, routed: bool = False) -> Tuple[str, Report, List[Tuple[str, str]]]:
    """The board's path from the repository's root, the verdicts, and every refusal."""
    if not os.path.isfile(board):
        return board, Report(), [(board, "there is no board file here to judge")]
    root, refused = refusals(git, board)
    report = Report()
    if refused:
        return board, report, refused
    rel = os.path.relpath(os.path.realpath(board), root)
    plan = os.path.join(os.path.dirname(rel), board_placement.PLAN)
    with tempfile.TemporaryDirectory(prefix="board-history-") as work:
        try:
            history = History(git, root, work)
            tracked, first = first_track(history, rel, report)
            if tracked and first is None:
                return rel, report, []
            if not tracked:
                report.notes.append("before first track")
            judge_placement(history, rel, plan, first, report)
            judge_critical(history, rel, plan, tracked, routed, report)
        except CannotRun as error:
            return rel, Report(), [(root, str(error))]
        except Unreadable as error:
            report.add("history", [str(error)], "")
    return rel, report, []


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--git", default="git", help="git (default: git on the search path)")
    parser.add_argument("--board", required=True, help="the layout file (.kicad_pcb), with its layout-plan.md beside it")
    parser.add_argument("--routed", action="store_true",
                        help="the router has run: a last pass with no router commit, or no critical routing section, "
                             "fails")
    parser.add_argument("--json", action="store_true", help="print the verdicts as one JSON document")
    args = parser.parse_args(argv)
    board, report, refused = judge(args.git, args.board, args.routed)
    if refused:
        result, status, detail = "REFUSED", 2, "the history was not judged"
    elif report.failed():
        result, status = "FAIL", 1
        detail = f"{report.failed()} of {len(report.checks)} checks failed"
    else:
        result, status = "PASS", 0
        detail = f"all {len(report.checks)} checks passed"
    detail = "; ".join([detail] + report.notes)
    if args.json:
        json.dump({"board": board, "result": result, "detail": detail, "checks": report.checks,
                   "refusals": [{"what": what, "why": why} for what, why in refused]}, out, indent=1)
        out.write("\n")
        return status
    for what, why in refused:
        print(f"REFUSED | {clean(what)} | {clean(why)}", file=out)
    for check in report.checks:
        print(f"CHECK | {clean(check['check'])} | {check['verdict']} | {clean(check['detail'])}", file=out)
    print(f"RESULT | {result} | {clean(detail)}", file=out)
    return status


if __name__ == "__main__":
    sys.exit(main())
