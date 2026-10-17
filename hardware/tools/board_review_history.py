#!/usr/bin/env python3
"""The layout review record history check: a board's layout-review.md read against the repository's history.

The method's layout review step has each round of a board's review record stand
as it was first recorded, so that nothing a round found is quietly dropped, and
has the closing round judge the board as it stands. Neither is taken on the
record's word. This command reads every version of the record reachable from
HEAD and judges:

- The round structure. A round must be fully accounted for by the parts the command reads, in the record at HEAD and in
  every earlier version of it. A line, outside a code fence, that mentions a round heading in any way but exactly
  `## Round <n>` (`n` a positive integer, no leading zero), a `## Round <n>` heading given twice in one version, or a code
  fence left open at the end of a version, fails. So does a round holding, outside a code fence, any heading line, a line
  that begins with `#`, an HTML heading or a line of only dashes or equals signs, other than exactly `### Verdicts`,
  `### Findings` or `### Plan and free pass`; a round with no Verdicts part, or with one of those parts twice; a Verdicts or
  Findings part holding anything but one table, or whose table the command cannot read (a Verdicts table headed
  Item, Kind, Severity, Verdict, Rests on and Why; a Findings table with Finding, Raised by, Severity and What and where
  columns, each finding numbered once). A round runs from its heading to the next `## Round <n>` heading, a line
  beginning `## ` in a code fence neither ending it nor counting as a heading. A round with no findings may leave the
  Findings part out or give it only the line `This round raises no finding.`, but not hold one it cannot read. The Plan and free pass part is prose the method does not have
  compared.
- The rounds kept. A `## Round <n>` heading in any earlier version of the
  record that the record at HEAD lacks fails, and so does a record holding no
  round.
- Each round as first recorded. A round's end-of-round commit is the first
  commit, oldest first, whose record holds its heading. In that commit the
  round's opening lines, those up to its first subheading, its Verdicts table,
  and its Findings table's findings, none removed or added, each with the
  number, Raised by, Severity and What and where it was first given, must be
  as the record now gives them. The Closed by column is the one field that
  legitimately changes after a round is recorded, so it is never compared, and
  the other columns of a finding are not compared either.
- Each round's order. The round's end-of-round commit must be an ancestor of,
  and not, every commit after the round's Board judged commit that changes the
  board's design files.
- The closing round, the highest-numbered round at HEAD, which must be judged
  on design files unchanged since its end-of-round commit.
- The round kind. A round states its kind in its opening lines as a line `**Round kind**: full` or
  `**Round kind**: narrow`, a narrow round being one a fresh reviewer limited to the items a fix touches and a full round
  one that judges every item. The closing round must state one: a closing round with no such line, or with any value but
  `full` or `narrow`, is refused, and a closing round that is narrow fails, since only a full round closes a review.
  The kind is exactly the bullet `- **Round kind**: <value>` outside a code fence; any other form, such as one with
  no `- `, with `*` markers, with no colon or inside a code fence, states no kind, and two such lines are refused.
  A closing round that is full must also give a verdict for every item that round 1 (full by the method) and every
  earlier full round judge, or the round completeness check fails, naming the items missing; a narrow round is held
  to no item. Earlier rounds need state no kind, and are compared as first recorded like any other. The command reads a round's
  Verdicts table as a table and does not demand a verdict for every item of the checklist, so a narrow round's table
  holds only the items it judges.

The board's design files are the files KiCad reads for it: everything tracked
in the board's folder, the sheets its schematic reaches and the libraries its
library tables name, less the board folder's own records, its markdown and
YAML files, the review record among them, so a record's own commits and a
finding's closure never count as a design change.

It needs git and Python only. It reads the record and the design files as HEAD
holds them, and refuses a shallow clone, a folder holding no single KiCad
project, and a record or design file that is untracked, absent or differs from
HEAD.

    board_review_history.py --folder <board folder> [--json]

Every check is one line, CHECK | <check> | PASS or FAIL | <detail>, a result
line comes last, and the exit status is the verdict: 0 when every check
passes, 1 when any fails, 2 when the command is refused. With --json the same
verdicts are printed as one JSON document.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402
from board_placement import cells  # noqa: E402
from board_geometry import Unreadable  # noqa: E402
from board_history import History, Report, cited, difference, fields, short, table  # noqa: E402

#: The review record, in the board's own folder.
RECORD = "layout-review.md"
#: The files in the board's folder that are its own records, not files KiCad reads.
RECORD_SUFFIXES = (".md", ".yaml", ".yml")
#: The one form a round's heading takes: a positive integer with no leading zero, and nothing after it.
ROUND = re.compile(r"## Round ([1-9][0-9]*)[ \t]*")
#: Any line that mentions a round's heading in any way, whatever its depth, case, emphasis, spacing or indent, that must
#: be the one form or be refused.
HEADING = re.compile(r"\s*(#+\s*)?[*_`]*\s*round\s*\d", re.IGNORECASE)
#: A line that may open a code fence, and a line that may close one.
FENCE_OPEN = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
FENCE_CLOSE = re.compile(r" {0,3}(`{3,}|~{3,})[ \t]*")
#: The only subheadings a round holds, each in exactly this form.
PART = re.compile(r"### (Verdicts|Findings|Plan and free pass)[ \t]*")
#: Any line that is, or may be read as, a heading of some other kind: one beginning `#`, an HTML heading, or the underline
#: of a heading written over it. In a round, outside a code fence, it must be one of the PART forms.
OTHER_HEADING = re.compile(r"\s*(#|<h[1-6]\b|=+\s*$|-{2,}\s*$)", re.IGNORECASE)
#: The columns of the verdict table, in the order the method gives them.
VERDICT_COLUMNS = ["Item", "Kind", "Severity", "Verdict", "Rests on", "Why"]
#: The columns of a finding that are compared: the Closed by column, and the rest, are not.
COMPARED = ["Raised by", "Severity", "What and where"]
NUMBER = "Finding"
#: The field that gives a round's kind, in its opening lines, and the two kinds it may give.
KIND = re.compile(r"- \*\*Round kind\*\*: (.*\S)")
KINDS = ("full", "narrow")
#: The one line a Findings part holds, in place of its table, when the round raises no finding.
NO_FINDINGS = "This round raises no finding."

#: A line of a record: its number, its text and whether it is a code fence's mark or inside a code fence.
Line = Tuple[int, str, bool]


def record_lines(text: Optional[str]) -> Tuple[List[Line], Optional[int]]:
    """Every line of a record, and the line a code fence was opened at and never closed, if one was. Lines are split on
    newlines alone, so a trailing carriage return is part of the line. Fences follow the CommonMark rule: an opener is
    up to three spaces, then a run of three or more backticks or tildes, and for backticks an info string holding no
    backtick; a fence closes only on a line of up to three spaces, a run of the same character at least as long as the
    opener's, and nothing after it but spaces or tabs. A line indented four spaces or more opens nothing."""
    lines: List[Line] = []
    opener: Optional[Tuple[str, int]] = None
    opened = 0
    for index, line in enumerate((text or "").split("\n"), 1):
        if opener is None:
            mark = FENCE_OPEN.fullmatch(line)
            if mark and not (mark.group(1)[0] == "`" and "`" in mark.group(2)):
                opener, opened = (mark.group(1)[0], len(mark.group(1))), index
                lines.append((index, line, True))
                continue
        else:
            mark = FENCE_CLOSE.fullmatch(line)
            if mark and mark.group(1)[0] == opener[0] and len(mark.group(1)) >= opener[1]:
                opener = None
            lines.append((index, line, True))
            continue
        lines.append((index, line, False))
    return lines, opened if opener is not None else None


def round_headings(text: Optional[str]) -> Tuple[List[int], List[Tuple[int, str]], Optional[int]]:
    """The round numbers a record's `## Round <n>` headings give, in order, every other line outside a code fence that
    mentions a round's heading, as (line number, line), and the line a code fence was opened at and never closed."""
    numbers: List[int] = []
    malformed: List[Tuple[int, str]] = []
    lines, unclosed = record_lines(text)
    for index, line, fenced in lines:
        if fenced:
            continue
        mark = ROUND.fullmatch(line)
        if mark:
            numbers.append(int(mark.group(1)))
        elif HEADING.match(line):
            malformed.append((index, line))
    return numbers, malformed, unclosed


def round_numbers(text: Optional[str]) -> List[int]:
    return round_headings(text)[0]


def round_bodies(text: Optional[str]) -> Dict[int, List[Line]]:
    """The lines of each round, by number, from after its `## Round <n>` heading to the next such heading or the end of
    the record. A line in a code fence neither ends a round nor is a heading. A round given twice brings both."""
    bodies: Dict[int, List[Line]] = {}
    current: Optional[int] = None
    for index, line, fenced in record_lines(text)[0]:
        mark = None if fenced else ROUND.fullmatch(line)
        if mark:
            current = int(mark.group(1))
            bodies.setdefault(current, [])
        elif current is not None:
            bodies[current].append((index, line, fenced))
    return bodies


# --- Reading a round -------------------------------------------------------------------------


class Round:
    """What a round holds that is compared: its opening lines, its verdict table and its findings. Everything in the
    round it cannot read, as a fault, since a part of a round it does not read is a part it does not guard."""

    def __init__(self, body: List[Line]):
        self.faults: List[str] = []
        parts: Dict[str, List[Line]] = {"": []}
        seen: Counter = Counter()
        name = ""
        for index, line, fenced in body:
            if not fenced:
                mark = PART.fullmatch(line)
                if mark:
                    name = mark.group(1)
                    seen[name] += 1
                    if seen[name] > 1:
                        self.faults.append(f"line {index} gives its '### {name}' part a second time")
                    parts.setdefault(name, [])
                    continue
                if OTHER_HEADING.match(line) and not HEADING.match(line):
                    self.faults.append(f"line {index} reads '{line.strip()}', a heading the command cannot read; a round "
                                       f"holds only the subheadings '### Verdicts', '### Findings' and "
                                       f"'### Plan and free pass'")
            parts[name].append((index, line, fenced))
        self.opening = [line.strip() for _, line, _ in parts[""] if line.strip()]
        #: The value of each line, outside a code fence, that is exactly the bullet `- **Round kind**: <value>`.
        self.kinds = [mark.group(1) for _, line, fenced in parts[""] if not fenced
                      for mark in [KIND.fullmatch(line.strip())] if mark]
        if "Verdicts" not in parts:
            self.faults.append("it has no '### Verdicts' part")
        self.verdicts = self.read(parts.get("Verdicts"), "its Verdicts table")
        self.findings = self.read(parts.get("Findings"), "its Findings table", NO_FINDINGS)
        if self.verdicts[0] and self.verdicts[0] != VERDICT_COLUMNS:
            self.faults.append(f"its Verdicts table is headed '{' | '.join(self.verdicts[0])}' where the method gives "
                               f"'{' | '.join(VERDICT_COLUMNS)}'")
        self.numbers: List[str] = []
        self.compared: Dict[str, Dict[str, str]] = {}
        header, rows = self.findings
        columns = [column for column in [NUMBER] + COMPARED if header and column not in header]
        self.faults += [f"its Findings table has no {column} column" for column in columns]
        if len(set(header)) != len(header):
            self.faults.append("its Findings table has a column named twice")
        elif not columns:
            for row in rows:
                named = dict(zip(header, row))
                if named[NUMBER] in self.compared:
                    self.faults.append(f"its Findings table gives finding {named[NUMBER]} more than once")
                    continue
                self.numbers.append(named[NUMBER])
                self.compared[named[NUMBER]] = {column: named[column] for column in COMPARED}

    def read(self, lines: Optional[List[Line]], what: str,
             instead: Optional[str] = None) -> Tuple[List[str], List[List[str]]]:
        """The header and rows of the one table a part holds, or none when the part holds only the line `instead`. A
        part holding anything else, a second table, text or a code fence among them, or a table with no readable
        header, is a fault, and a part the round lacks reads as empty."""
        if lines is None:
            return [], []
        entries = [(index, line.strip(), fenced) for index, line, fenced in lines]
        start = next((place for place, (_, line, fenced) in enumerate(entries)
                      if not fenced and line.startswith("|")), None)
        if start is None and instead is not None and [(line, fenced) for _, line, fenced in entries if line] == [
                (instead, False)]:
            return [], []
        if start is None:
            self.faults.append(f"{what}: it holds no table")
            return [], []
        end = start
        while end < len(entries) and not entries[end][2] and entries[end][1].startswith("|"):
            end += 1
        self.faults += [f"{what}: line {index} reads '{line}', which is not part of its one table"
                        for index, line, _ in entries[:start] + entries[end:] if line]
        header = cells(entries[start][1])
        _, rows, faults = table([line for _, line, _ in entries[start:end]], header)
        self.faults += [f"{what}: {fault}" for fault in faults]
        return header, rows


def differences(then: Round, now: Round) -> List[str]:
    """Every way `now` differs from `then` in what is compared, each naming the thing that differs."""
    found = []
    if then.opening != now.opening:
        found.append(f"its opening lines differ, first at '{difference(then.opening, now.opening)}'")
    if then.verdicts != now.verdicts:
        old, new = then.verdicts, now.verdicts
        old_rows, new_rows = {row[0]: row for row in old[1]}, {row[0]: row for row in new[1]}
        rows = [f"its verdict table no longer has the row for {item}" for item in old_rows if item not in new_rows]
        rows += [f"its verdict table gained the row for {item}" for item in new_rows if item not in old_rows]
        rows += [f"its verdict table row for {item} differs, now '{' | '.join(new_rows[item])}'"
                 for item in old_rows if item in new_rows and old_rows[item] != new_rows[item]]
        if old[0] != new[0]:
            rows.append(f"its verdict table header now reads '{' | '.join(new[0])}'")
        found += rows or ["its verdict table rows are in a different order"]
    found += [f"finding {number} was removed" for number in sorted((Counter(then.numbers) - Counter(now.numbers)))]
    found += [f"finding {number} was added" for number in sorted((Counter(now.numbers) - Counter(then.numbers)))]
    for number, was in then.compared.items():
        for column, value in was.items():
            if number in now.compared and now.compared[number][column] != value:
                found.append(f"finding {number}'s {column} now reads '{now.compared[number][column]}'")
    if then.numbers != now.numbers and sorted(then.numbers) == sorted(now.numbers):
        found.append("its findings are in a different order")
    return found


# --- The history -----------------------------------------------------------------------------


def changed_paths(history: History) -> Dict[str, Set[str]]:
    """The paths each commit changes against a parent, a merge's against each; a root commit's are those it adds."""
    listing = history.run("-c", "core.quotepath=off", "log", "-m", "--format=%x01%H", "--name-only", "HEAD")
    changed: Dict[str, Set[str]] = {}
    for block in listing.split("\x01")[1:]:
        lines = block.split("\n")
        changed.setdefault(lines[0].strip(), set()).update(line for line in lines[1:] if line.strip())
    return changed


def judge_record(history: History, folder: str, record: str, design: set, report: Report) -> None:
    head = history.order[-1]
    prefix = folder + "/" if folder else ""

    def is_design(path: str) -> bool:
        return path in design or (path.startswith(prefix) and not path.endswith(RECORD_SUFFIXES))

    blobs = history.blobs(history.order, record)
    parsed: Dict[str, Tuple[List[int], List[Tuple[int, str]], Optional[int], Dict[int, Round]]] = {}
    first: Dict[int, str] = {}
    unjudgeable: List[str] = []
    name = folder or "."
    for commit in history.order:
        blob = blobs[commit]
        if blob is None:
            continue
        if blob not in parsed:
            text = history.text(commit, record)
            rounds = {number: Round(body) for number, body in round_bodies(text).items()}
            parsed[blob] = (*round_headings(text), rounds)
            numbers, malformed, unclosed, _ = parsed[blob]
            version = "the record at HEAD" if blob == blobs[head] else f"the version of the record at {short(commit)}"
            unjudgeable += [f"{name}: line {line} of {version} reads '{text}', which mentions a round heading that "
                            f"is not exactly '## Round <n>', so is a round the command cannot judge"
                            for line, text in malformed]
            if unclosed is not None:
                unjudgeable.append(f"{name}: a code fence opened at line {unclosed} of {version} is never closed, so "
                                   f"the rounds after it are unguarded")
            unjudgeable += [f"{name}: {version} holds round {number} more than once"
                            for number in sorted(n for n, count in Counter(numbers).items() if count > 1)]
            unjudgeable += [f"{name}: round {number} of {version}: {fault}"
                            for number, one in sorted(rounds.items()) for fault in one.faults]
        for number in parsed[blob][0]:
            first.setdefault(number, commit)
    now_text = history.text(head, record)
    present = sorted(set(round_numbers(now_text)))
    faults = [f"{name}: round {number} was recorded at {short(commit)} and the record at HEAD lacks it"
              for number, commit in sorted(first.items()) if number not in present]
    if not present:
        faults.append(f"{name}: the record at HEAD holds no round, a '## Round <n>' heading")
    report.add("rounds kept", faults, f"every one of the {len(present)} rounds recorded in any version is in the record")
    report.add("round structure", unjudgeable,
               "every round heading in every version of the record is '## Round <n>', none is given twice, no "
               "code fence is left open, and every round is only the parts the command reads, each as it reads them")
    if not present:
        return
    changed = changed_paths(history)
    for number in present:
        end = first[number]
        then, now = parsed[blobs[end]][3][number], parsed[blobs[head]][3][number]
        faults = [f"{name}: round {number} differs from its end-of-round commit {short(end)}: {fault}"
                  for fault in differences(then, now)]
        report.add(f"round {number} as first recorded", faults,
                   f"the round's opening lines, verdict table and findings are as {short(end)} first recorded them")
        judged = cited(fields(then.opening, ["Board judged"]).get("Board judged", (0, ""))[1])
        resolved = history.resolve(judged) if judged else None
        if resolved is None or not history.is_ancestor(resolved, head):
            report.add(f"round {number} order", [
                f"{name}: round {number}'s Board judged commit "
                f"{judged or '(none given)'} is not in this repository's history from HEAD"], "")
            continue
        faults = []
        for commit in history.ancestry(resolved, head):
            files = sorted(path for path in changed.get(commit, ()) if is_design(path))
            if files and (commit == end or not history.is_ancestor(end, commit)):
                faults.append(f"{name}: round {number}'s end-of-round commit {short(end)} does not come before "
                              f"{short(commit)}, which changes {', '.join(files)} after the round's Board judged "
                              f"commit {short(resolved)}")
        report.add(f"round {number} order", faults,
                   f"the end-of-round commit {short(end)} comes before every design change after "
                   f"{short(resolved)}")
    closing = present[-1]
    end = first[closing]
    diff = history.run("-c", "core.quotepath=off", "diff", "--name-only", end, head).split("\n")
    files = sorted(path for path in diff if path.strip() and is_design(path))
    report.add("closing round", [f"{name}: the board's design files changed after closing round {closing}'s commit "
                                 f"{short(end)}: {', '.join(files)}"] if files else [],
               f"no design file has changed since closing round {closing}'s commit {short(end)}")
    rounds = parsed[blobs[head]][3]
    kinds = rounds[closing].kinds
    stated = kinds[0] if len(kinds) == 1 else ""
    if len(kinds) > 1:
        raise CannotRun(f"{name}: closing round {closing} of the record at HEAD states its round kind "
                        f"{len(kinds)} times, where its opening lines must hold one line")
    if stated not in KINDS:
        raise CannotRun(f"{name}: closing round {closing} of the record at HEAD " + (
            f"gives its round kind as '{stated}'" if stated else "states no round kind") +
            ", where its opening lines must hold the bullet '- **Round kind**: full' or "
            "'- **Round kind**: narrow'")
    report.add("round kind", [f"{name}: closing round {closing} is narrow, and a narrow round never closes the review; "
                              f"only a full round, which judges every item, does"] if stated == "narrow" else [],
               f"closing round {closing} is a full round")
    required: Dict[str, int] = {}
    for number in sorted(rounds):
        if number < closing and (number == 1 or rounds[number].kinds == ["full"]):
            for row in rounds[number].verdicts[1]:
                required.setdefault(row[0], number)
    held = {row[0] for row in rounds[closing].verdicts[1]}
    missing = [f"{item} (round {number})" for item, number in required.items() if item not in held]
    faults = []
    if stated == "full" and missing:
        faults = [f"{name}: closing round {closing} is full but gives no verdict for {len(missing)} item(s) that "
                  f"round 1 or an earlier full round judges, first {', '.join(missing[:5])}"]
    report.add("round completeness", faults,
               f"closing round {closing} gives a verdict for every item round 1 and each earlier full round judge"
               if stated == "full" else f"closing round {closing} is narrow, so is held to no item")


# --- Running it ------------------------------------------------------------------------------


def join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def refusals(git: str, folder: str) -> Tuple[Optional[str], str, set, List[Tuple[str, str]]]:
    """The top of the work tree, the folder from it, the design files, and every reason the record cannot be judged."""
    if not os.path.isdir(folder):
        return None, "", set(), [(folder, "there is no board folder here to judge")]
    try:
        board_check.require_python()
        root = os.path.realpath(board_check.require_git(git, os.path.abspath(folder)))
    except CannotRun as error:
        return None, "", set(), [("git", str(error))]
    shallow = subprocess.run([git, "-C", root, "rev-parse", "--is-shallow-repository"], capture_output=True, text=True)
    if shallow.stdout.strip() == "true":
        return root, "", set(), [(root, "the repository is a shallow clone, which lacks the commits the record's "
                                        "rounds were first recorded in; fetch its whole history "
                                        "(git fetch --unshallow)")]
    if shallow.stdout.strip() != "false":
        return root, "", set(), [(root, "git could not say whether the repository is a shallow clone (git 2.15 or "
                                        "newer can)")]
    if subprocess.run([git, "-C", root, "rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True).returncode:
        return root, "", set(), [(root, "the repository has no commit")]
    folder_rel = os.path.relpath(os.path.realpath(folder), root)
    folder_rel = "" if folder_rel == "." else folder_rel.replace(os.sep, "/")
    tracked = board_check.tracked_files(git, root)
    projects = sorted(path for path in tracked if os.path.dirname(path) == folder_rel and path.endswith(".kicad_pro"))
    if len(projects) != 1:
        return root, folder_rel, set(), [(folder_rel or ".", "the folder tracks " + (
            "no KiCad project" if not projects else f"{len(projects)} KiCad projects") +
            ", and the record is judged against the design of the one project beside it")]
    repository = board_check.Repository(root, tracked, git)
    design = board_check.Design(projects[0])
    files, _ = board_check.design_files(design, repository)
    prefix = folder_rel + "/" if folder_rel else ""
    files = {path for path in files if not (path.startswith(prefix) and path.endswith(RECORD_SUFFIXES))}
    record = join(folder_rel, RECORD)
    core = [record, design.project, design.schematic, design.layout]
    rules = [design.rules] if repository.on_disk(design.rules) else []
    found = []
    for path in dict.fromkeys(core + sorted(files) + rules):
        why = repository.uncommitted(path)
        if why is not None:
            found.append((path, f"{why}; the record is judged as HEAD holds it and its design files, so commit them"))
    return root, folder_rel, files | {design.project, design.schematic, design.layout, design.rules}, found


def judge(git: str, folder: str) -> Tuple[str, Report, List[Tuple[str, str]]]:
    """The board's folder from the repository's root, the verdicts, and every refusal."""
    root, rel, design, refused = refusals(git, folder)
    if refused:
        return rel or folder, Report(), refused
    report = Report()
    try:
        record = join(rel, RECORD)
        judge_record(History(git, root, ""), rel, record, design, report)
    except CannotRun as error:
        return rel, Report(), [(root, str(error))]
    except Unreadable as error:
        report.add("history", [str(error)], "")
    return rel or ".", report, []


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--git", default="git", help="git (default: git on the search path)")
    parser.add_argument("--folder", required=True,
                        help="the board's folder, holding its KiCad project and its layout-review.md")
    parser.add_argument("--json", action="store_true", help="print the verdicts as one JSON document")
    args = parser.parse_args(argv)
    board, report, refused = judge(args.git, args.folder)
    if refused:
        result, status, detail = "REFUSED", 2, "the record was not judged"
    elif report.failed():
        result, status = "FAIL", 1
        detail = f"{report.failed()} of {len(report.checks)} checks failed"
    else:
        result, status = "PASS", 0
        detail = f"all {len(report.checks)} checks passed"
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
