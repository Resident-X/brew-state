"""The placement and critical routing history check, run on throwaway git repositories.

Each repository is built in a temporary folder outside this one, holding a
short copy of the design method's catalogue, a board written from text with
the shared board fixtures, and its layout plan. Its history is committed step
by step as the method's placement and routing steps commit it, compliant or
with one known defect, and the command is held to the verdict that history
should get. The measures each candidate records are worked out by hand from
the pad centres, so a candidate is held to a placement known in advance. Only
git and Python are needed.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import footprint  # noqa: E402
from board_fixtures import pad  # noqa: E402
from board_fixtures import uuid  # noqa: E402
import board_fixtures  # noqa: E402
import board_history  # noqa: E402


REPO = board_fixtures.REPO


METHOD = """# Board design method

## Layout practice catalogue

#### FLOOR-1. Parts are grouped by function into their floorplan regions

- **Judged on:** `assembly-top`, `placement`.

#### WORK-1. Connected parts sit together

- **Judged on:** `placement`.

#### GROUND-1. Ground is a plane

- **Judged on:** `layer-F.Cu`.
"""


PLAN = """# Layout plan

## Floorplan

| Region | Bounds | What it holds | Parts |
|---|---|---|---|
| mains | none: the board carries no mains | nothing | none |
| low voltage | (0, 0)–(40, 40) | the connector and its resistor | J1, R1 |
| analog sensing | none: the schematic carries no sensing front end | nothing | none |
| digital | none: the schematic carries no controller | nothing | none |

## Plan

| Item | Applies | How the layout meets it, or why it does not apply |
|---|---|---|
| FLOOR-1 | yes | J1 and R1 in low voltage. |
| WORK-1 | yes | R1 beside J1. |
| GROUND-1 | no | No ground plane: the schematic carries one return, GND, between two parts. |

### The board's own items

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|
| none | | | | | | | | | |
"""


def board(r1=(20, 10), r1_angle=0, copper=(), r2=None):
    """J1 at (5, 10) and R1 at `r1`, each with a pad on net A above its centre and on GND below it, `r2` when given at
    that position with each pad on a net of its own, which joins nothing, and `copper`."""
    parts = [footprint("J1", 5, 10, [pad(1, 0, -1, "A", "passive"), pad(2, 0, 1, "GND", "passive")]),
             footprint("R1", r1[0], r1[1], [pad(1, 0, -1, "A", "passive", r1_angle),
                                            pad(2, 0, 1, "GND", "passive", r1_angle)], angle=r1_angle)]
    if r2 is not None:
        parts.append(footprint("R2", r2[0], r2[1], [pad(1, 0, -1, "X", "passive"), pad(2, 0, 1, "Y", "passive")]))
    return board_fixtures.layout(parts + list(copper))


def track(start, end, net, locked):
    """A straight track in the form KiCad writes it."""
    return (f'(segment (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) (width 0.25) (layer "F.Cu")'
            + (" (locked yes)" if locked else "") + f' (net "{net}") (uuid {uuid()}))')


def pour(rule_area=False):
    """A zone over the lower left of the board with no fill, as a designer draws it before KiCad fills it: a pour on
    net GND, or a rule area, which carries a keepout and no net."""
    outline = "(polygon (pts (xy 1 1) (xy 30 1) (xy 30 30) (xy 1 30)))"
    if rule_area:
        return (f'(zone (layers "F.Cu") (uuid {uuid()}) (hatch edge 0.5) (keepout (tracks not_allowed) '
                f'(vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) {outline})')
    return (f'(zone (net "GND") (layer "F.Cu") (uuid {uuid()}) (hatch edge 0.5) (connect_pads (clearance 0.5)) '
            f'(min_thickness 0.25) {outline})')


#: Critical routing by hand: net A from J1's pad to R1's, before and after locking.
HAND = track((5, 9), (20, 9), "A", False)


LOCKED = track((5, 9), (20, 9), "A", True)


#: The router's copper: GND, never locked.
ROUTED = track((5, 11), (20, 11), "GND", False)


#: Each candidate's measures, worked out by hand. Candidate 1 puts R1 at (20, 10): A runs (5, 9) to (20, 9) and GND
#: (5, 11) to (20, 11), 15 mm each and apart. Candidate 2 puts it at (25, 10): 20 mm each.
MEASURES = {1: ["LENGTH | total | 30 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"],
            2: ["LENGTH | total | 40 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]}


PLACES = {1: (20, 10), 2: (25, 10)}


PLACEMENT_ROWS = ["| FLOOR-1 | pass | placement, whole board | |", "| WORK-1 | pass | placement; LENGTH | |"]


def candidate(number, commit, measures=None, rows=None, renders=None):
    lines = [f"### Candidate {number}", "", f"- **Commit**: `{commit}`",
             "- **Renders**:", "", "  ```",
             f"  git worktree add --detach /tmp/w/b-candidate-{number} {renders or commit}",
             "  ```", "", "- **Measures**:", "", "  ```"]
    lines += [f"  {line}" for line in (MEASURES[number] if measures is None else measures)]
    lines += ["  ```", "", "| Item | Verdict | Rests on | Why |", "|---|---|---|---|"]
    lines += PLACEMENT_ROWS if rows is None else rows
    return "\n".join(lines) + "\n"


def placement(candidates, chosen=1):
    return "## Placement\n\n" + "\n".join(candidates) + f"\n**Chosen**: {chosen}, its connections the shorter.\n"


CRITICAL_ROWS = ["| WORK-1 | judgement | quality | pass | net-A, whole board | |",
                 "| GROUND-1 | judgement | function | not applicable | | the plan marks it no |"]


def critical_pass(number, judged, rows=None):
    lines = [f"### Pass {number}", "", f"- **Board judged**: `{judged}`",
             "- **Views**: `task hw:views -- --board b.kicad_pcb --project b.kicad_pro --class Power --out /tmp/v`; "
             "the placement view was not rendered", "",
             "| Item | Kind | Severity | Verdict | Rests on | Why |", "|---|---|---|---|---|---|"]
    lines += CRITICAL_ROWS if rows is None else rows
    lines += ["", "Bearing on no critical net:", "", "- `FLOOR-1`: decided by where the parts sit, not by copper"]
    return "\n".join(lines) + "\n"


def critical(passes):
    return "## Critical routing\n\n" + "\n".join(passes)


class Repo:
    """A throwaway repository holding the method's catalogue, a board in `b/` and its layout plan."""

    def __init__(self, test):
        self.test = test
        self.root = tempfile.mkdtemp(prefix="board-history-test-")
        test.addCleanup(shutil.rmtree, self.root, True)
        self.path = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.path, "b"))
        os.makedirs(os.path.join(self.path, "docs"))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write("docs/board-design-method.md", METHOD)
        self.sections = {}
        self.base = PLAN

    @property
    def board(self):
        return os.path.join(self.path, "b", "b.kicad_pcb")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.path, capture_output=True, text=True,
                              check=True).stdout.strip()

    def write(self, name, text):
        with open(os.path.join(self.path, name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def plan(self, **sections):
        """Write the layout plan with these sections, by name, below the plan, keeping those not given."""
        self.sections.update(sections)
        self.write("b/layout-plan.md", self.base + "".join(f"\n{text}" for text in self.sections.values() if text))

    def commit(self, board_text=None, message="step", **sections):
        if board_text is not None:
            self.write("b/b.kicad_pcb", board_text)
        if sections or not os.path.exists(os.path.join(self.path, "b", "layout-plan.md")):
            self.plan(**sections)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run(self, *extra, board=None):
        """The command's exit status, its report's lines and its JSON document."""
        args = ["--board", board or self.board, *extra]
        stream = io.StringIO()
        status = board_history.main(args, out=stream)
        document = io.StringIO()
        self.test.assertEqual(board_history.main(args + ["--json"], out=document), status,
                              "the JSON run exits with the text run's status")
        return status, stream.getvalue().splitlines(), json.loads(document.getvalue())

    # --- The method's steps, as a compliant board's history commits them --------------------------

    def replan(self, base):
        """Rewrite the layout plan on `base`, keeping its sections, for the next commit to hold."""
        self.base = base
        self.plan()

    def planned(self):
        """The floorplan and plan committed alone, before any part is placed; the commit."""
        return self.commit(message="b: floorplan and plan")

    def placed(self, chosen=1):
        """The plan committed alone, then two candidates, then the placement section with the chosen layout: the
        candidates' commits."""
        self.planned()
        one = self.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.commit(board(PLACES[2]), "b: placement candidate 2")
        self.commit(board(PLACES[chosen]), "b: placement chosen",
                    placement=placement([candidate(1, one), candidate(2, two)], chosen))
        return one, two

    def routed(self):
        """The critical net routed by hand and committed unlocked, then locked; the Board judged commit."""
        self.commit(board(copper=[HAND]), "b: route A by hand")
        return self.commit(board(copper=[LOCKED]), "b: lock A")

    def merge(self, branch, board_text, message):
        """`branch` merged into the checked-out one as a merge commit holding `board_text`; the merge's commit."""
        self.git("merge", "-q", "--no-ff", "--no-commit", "-s", "ours", branch)
        return self.commit(board_text, message)

    def through_router(self, judged):
        """Pass 1 recorded and committed, then the router's commit; the router's commit."""
        self.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        return self.commit(board(copper=[LOCKED, ROUTED]), "b: router")


def short_of(commit):
    return commit[:12]


def checks(document, verdict="FAIL"):
    return [f"{check['check']}: {check['detail']}" for check in document["checks"] if check["verdict"] == verdict]


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)

    def assertPasses(self, *extra, board=None):
        status, lines, document = self.repo.run(*extra, board=board)
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(document["result"], "PASS")
        self.assertTrue(lines[-1].startswith("RESULT | PASS |"), lines[-1])
        return lines, document

    def assertFails(self, *words, check=None, args=()):
        status, lines, document = self.repo.run(*args)
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertEqual(document["result"], "FAIL")
        self.assertTrue(lines[-1].startswith("RESULT | FAIL |"), lines[-1])
        failed = checks(document)
        printed = [line for line in lines if line.startswith("CHECK | ") and line.split(" | ")[2] == "FAIL"]
        for word in words:
            self.assertTrue(any(word in line and (check is None or line.startswith(check + ":")) for line in failed),
                            f"no failed check{' ' + check if check else ''} says '{word}':\n" + "\n".join(failed))
            self.assertTrue(any(board_history.clean(word) in line
                                and (check is None or line.startswith(f"CHECK | {check} | FAIL | ")) for line in printed),
                            f"no printed failed check{' ' + check if check else ''} says '{word}':\n" + "\n".join(lines))
        return failed


if __name__ == "__main__":
    unittest.main()
