#!/usr/bin/env python3
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

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_fixtures  # noqa: E402
import board_history  # noqa: E402
from board_fixtures import footprint, pad, uuid  # noqa: E402

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


class Passes(Base):
    def test_a_compliant_placement_before_any_track_passes_judged_at_head(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass on a history that keeps the order
        self.repo.placed()
        lines, document = self.assertPasses()
        self.assertIn("before first track", lines[-1])
        self.assertIn("CHECK | first track | PASS | no commit carries a track, arc, via or pour yet", "\n".join(lines))
        self.assertIn("CHECK | parts at HEAD | PASS", "\n".join(lines))
        self.assertFalse(any(check["check"].startswith("pass ") for check in document["checks"]),
                         "no critical routing is judged before the first track")

    def test_a_compliant_history_after_the_router_passes_and_a_hand_route_before_locking_is_not_the_routers(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass on a history that keeps the order
        self.repo.placed()
        judged = self.repo.routed()
        router = self.repo.through_router(judged)
        lines, document = self.assertPasses()
        text = "\n".join(lines)
        first = self.repo.git("rev-parse", "HEAD~3")
        self.assertIn(f"CHECK | first track | PASS | {first[:12]} is the first commit carrying a track", text,
                      "the hand route committed before locking is the first track")
        self.assertIn(f"CHECK | pass 1 before router | PASS | the pass is as it stood before the router's commit "
                      f"{router[:12]}", text, "the router's commit, not the unlocked hand route, is the router's")
        self.assertNotIn("router not yet run", lines[-1])

    def test_a_circuit_item_in_the_method_leaves_the_layout_checklist_unchanged(self):
        # SOL-BOARD-CIRCUIT-PRACTICE-CATALOGUE.C1: Change the board history check so the layout checklist it builds is taken from the layout practice catalogue section alone, with a test showing a circuit item in the method leaves that checklist unchanged.
        circuit = (
            "## Circuit practice catalogue\n\n"
            "#### PINV-1. Every pin stays within its rating\n\n- **Judged on:** `placement`.\n\n"
            "#### BUSP-1. Every bus line has a pull-up\n\n- **Judged on:** the schematic.\n"
        )
        before = board_history.catalogue(METHOD)
        for method in (METHOD + "\n" + circuit, METHOD.replace("## Layout practice catalogue", circuit + "\n## Layout practice catalogue")):
            self.assertEqual(board_history.catalogue(method), before)
            self.assertNotIn("PINV-1", board_history.catalogue(method))
        self.assertEqual(sorted(before), ["FLOOR-1", "GROUND-1", "WORK-1"])
        # A section ending at the next second-level heading, with a circuit item after it, still ends there.
        self.repo.write("docs/board-design-method.md", METHOD + "\n" + circuit)
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        self.assertPasses("--routed")
        self.assertEqual(board_history.catalogue(None), {})
        self.assertEqual(board_history.catalogue("# Board design method\n\n#### PINV-1. A circuit item\n"), {})

    def test_a_compliant_history_after_the_router_passes_with_routed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass on a history that keeps the order
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        lines, _ = self.assertPasses("--routed")
        self.assertNotIn("router not yet run", lines[-1])

    def test_a_pass_recorded_before_the_router_runs_is_judged_at_head_and_says_so(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass on a history that keeps the order
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        lines, _ = self.assertPasses()
        self.assertIn("router not yet run", lines[-1])

    def test_a_second_pass_appended_after_a_placement_change_passes(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: The critical routing section is a series of numbered passes, only ever appended, so that a re-route made to close a placement-caused finding records its own pass
        self.repo.placed()
        judged = self.repo.routed()
        first = self.repo.through_router(judged)
        relocked = track((5, 9), (20, 9), "A", True)
        self.repo.commit(board(copper=[LOCKED]), "b: remove the router's copper the change affects")
        second = self.repo.commit(board(copper=[relocked]), "b: re-route A by hand, locked")
        self.repo.commit(message="b: critical routing pass 2",
                         critical=critical([critical_pass(1, judged), critical_pass(2, second)]))
        router = self.repo.commit(board(copper=[relocked, track((5, 11), (20, 11), "GND", False)]), "b: router again")
        lines, _ = self.assertPasses()
        text = "\n".join(lines)
        self.assertIn(f"CHECK | pass 1 before router | PASS | the pass is as it stood before the router's commit "
                      f"{first[:12]}", text)
        self.assertIn(f"CHECK | pass 2 before router | PASS | the pass is as it stood before the router's commit "
                      f"{router[:12]}", text)

    def test_a_branch_merged_without_fast_forward_passes_checked_on_main(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass on a history that keeps the order, including one merged into another branch without rewriting
        self.repo.git("commit", "-q", "--allow-empty", "-m", "main: root")
        self.repo.git("checkout", "-q", "-b", "board")
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        self.repo.git("checkout", "-q", "main")
        self.repo.write("README.md", "main moved on\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "main: another change")
        self.repo.git("merge", "-q", "--no-ff", "-m", "merge board", "board")
        self.repo.git("branch", "-q", "-D", "board")
        self.assertPasses()


class PlacementFails(Base):
    def test_an_empty_heading_committed_before_the_first_track_and_filled_in_after_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: On placement it fails: a placement section missing, empty or holding fewer than two candidates in the commit before the first commit carrying a track, arc or via, or differing from the section as it now stands
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement heading", placement="## Placement\n")
        self.repo.commit(board(copper=[HAND]), "b: route A")
        self.repo.commit(message="b: placement filled in",
                         placement=placement([candidate(1, one), candidate(2, two)]))
        self.assertFails("holds no `### Candidate` heading", "now differs from the one in the commit before the first "
                         "track", check="placement section")

    def test_a_part_moved_in_the_first_tracks_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a part whose reference, position, angle or side differs between the chosen commit and the first track's commit
        self.repo.placed()
        self.repo.commit(board(r1_angle=180, copper=[HAND]), "b: route A, R1 turned")
        self.assertFails("R1 is at (20, 10) at 0 degrees on F.Cu in the chosen candidate, and at (20, 10) at 180 "
                         "degrees on F.Cu", check="parts at first track")

    def test_a_candidate_off_heads_line_of_history_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a candidate commit missing from the history, not an ancestor of the first track's commit, or holding the same placement as another
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.git("checkout", "-q", "-b", "elsewhere")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2, on a side branch")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="b: placement", placement=placement([candidate(1, one), candidate(2, two)]))
        self.repo.commit(board(copper=[HAND]), "b: route A")
        self.assertFails(f"candidate 2's commit {two} is not in this repository's history from HEAD",
                         check="candidate 2 commit")

    def test_a_candidate_merged_in_only_after_the_first_track_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a candidate commit missing from the history, not an ancestor of the first track's commit, or holding the same placement as another
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.git("checkout", "-q", "-b", "later")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2, on a branch merged after the track")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="b: placement", placement=placement([candidate(1, one), candidate(2, two)]))
        self.repo.commit(board(copper=[HAND]), "b: route A")
        self.repo.git("merge", "-q", "-s", "ours", "-m", "merge the candidate's branch", "later")
        self.assertFails(f"candidate 2's commit {two} does not come before the first track",
                         check="candidate 2 commit")

    def test_two_candidates_holding_the_same_board_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a candidate commit missing from the history, not an ancestor of the first track's commit, or holding the same placement as another
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(message="b: placement candidate 2, the same layout")
        self.repo.commit(message="b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, measures=MEASURES[1])]))
        self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")

    def test_a_recorded_measure_the_candidates_commit_does_not_measure_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: recorded measures that differ from the measures recomputed from the candidate's commit against the floorplan the section is judged against
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        wrong = ["LENGTH | total | 35 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, measures=wrong)]))
        self.assertFails("candidate 2 does not record 'LENGTH | total | 40 mm'",
                         "candidate 2 records 'LENGTH | total | 35 mm'", check="candidate 2 measures")

    def test_a_verdict_table_missing_a_placement_items_row_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a placement item without exactly one verdict
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=PLACEMENT_ROWS[:1])]))
        self.assertFails("candidate 2's verdict table has no row for the placement item WORK-1",
                         check="candidate 2 verdicts")

    def test_a_verdict_outside_the_three_or_a_not_applicable_the_plan_does_not_mark_no_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a placement item without exactly one verdict
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        rows = ["| FLOOR-1 | not applicable | | |", "| WORK-1 | fine | | |"]
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=rows)]))
        self.assertFails("gives FLOOR-1 not applicable, and the plan table does not mark it no",
                         "gives WORK-1 the verdict 'fine'", check="candidate 2 verdicts")

    def test_tracks_first_appearing_on_two_lines_of_history_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a track in the first commit, or the first tracks arriving on two lines of history or by a merge
        self.repo.placed()
        self.repo.git("checkout", "-q", "-b", "other")
        self.repo.commit(board(copper=[track((5, 11), (20, 11), "GND", False)]), "b: GND on one line")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(board(copper=[HAND]), "b: A on another")
        subprocess.run(["git", "merge", "-q", "-m", "merge", "other"], cwd=self.repo.path, capture_output=True)
        self.repo.write("b/b.kicad_pcb", board(copper=[HAND, track((5, 11), (20, 11), "GND", False)]))
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "merge both lines")
        self.assertFails("a track, arc, via or pour first appears on 2 separate lines of history", check="first track")

    def test_a_candidate_measured_against_a_floorplan_widened_in_its_own_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: recorded measures that differ from the measures recomputed from the candidate's commit against the floorplan the section is judged against; a chosen candidate that is not recorded or leaves a part outside its regions
        self.repo.planned()
        self.repo.write("b/layout-plan.md", PLAN.replace("(0, 0)–(40, 40)", "(0, 0)–(60, 40)"))
        one = self.repo.commit(board((50, 10)), "b: placement candidate 1, R1 off the region, the region widened")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        wide = ["LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.repo.commit(board((50, 10)), "b: placement, the region restored",
                         placement=placement([candidate(1, one, measures=wide), candidate(2, two)]))
        failed = self.assertFails("candidate 1 does not record 'OUTSIDE | total | 1'",
                                  "candidate 1 records 'OUTSIDE | total | 0'", check="candidate 1 measures")
        self.assertIn("chosen: the chosen candidate 1 leaves R1 outside its regions", failed)

    def test_tracks_first_appearing_in_a_merge_commit_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a track in the first commit, or the first tracks arriving on two lines of history or by a merge
        self.repo.placed()
        self.repo.git("checkout", "-q", "-b", "other")
        self.repo.write("README.md", "one line\n")
        self.repo.commit(message="other: a change")
        self.repo.git("checkout", "-q", "main")
        merge = self.repo.merge("other", board(copper=[HAND]), "merge, A routed in the merge")
        self.assertFails(f"a track, arc, via or pour first appears in the merge commit {merge[:12]}", check="first track")

    def test_a_track_in_the_root_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a track in the first commit, or the first tracks arriving on two lines of history or by a merge
        self.repo.commit(board(copper=[HAND]), "b: everything at once")
        self.assertFails("the root commit", check="first track")

    def test_one_candidate_a_renders_not_naming_its_commit_and_a_chosen_part_outside_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: On placement it fails: a placement section missing, empty or holding fewer than two candidates in the commit before the first commit carrying a track, arc or via, or differing from the section as it now stands; a chosen candidate that is not recorded or leaves a part outside its regions
        self.repo.planned()
        outside = self.repo.commit(board((50, 10)), "b: placement candidate 1, R1 off the region")
        self.repo.commit(message="b: placement", placement=placement([candidate(
            1, outside, renders="0123456789abcdef", measures=[
                "LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 1",
                "OUTSIDE | R1 | listed in low voltage; its extent covers x 47.5 to 52.5 mm, y 7.5 to 12.5 mm, which "
                "those regions' bounds do not hold"])]))
        failed = self.assertFails("records 1 candidate", check="candidates")
        self.assertTrue(any(line.startswith("candidate 1 commit:") and "does not name its own commit" in line
                            for line in failed), failed)
        self.assertIn("chosen: the chosen candidate 1 leaves R1 outside its regions", failed)

    def test_a_missing_placement_section_fails_rather_than_passing(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: On placement it fails: a placement section missing, empty or holding fewer than two candidates in the commit before the first commit carrying a track, arc or via, or differing from the section as it now stands
        self.repo.planned()
        self.repo.commit(board(PLACES[1]), "b: placed, nothing recorded")
        self.assertFails("holds no `## Placement` section", check="placement section")

    def test_a_placement_item_given_two_verdicts_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a placement item without exactly one verdict
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        rows = PLACEMENT_ROWS + ["| WORK-1 | fail | placement; LENGTH | runs long |"]
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=rows)]))
        self.assertFails("candidate 2's verdict table has 2 rows for WORK-1", check="candidate 2 verdicts")

    def test_a_chosen_candidate_the_section_does_not_record_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a chosen candidate that is not recorded or leaves a part outside its regions
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement, a third candidate chosen",
                         placement=placement([candidate(1, one), candidate(2, two)], chosen=3))
        self.assertFails("the chosen candidate, 3, is not one the section records", check="chosen")
        self.assertFails("the chosen candidate has no commit holding the board to compare the parts with",
                         check="parts at HEAD")

    def test_a_placement_with_no_chosen_field_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a chosen candidate that is not recorded or leaves a part outside its regions
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement, none chosen",
                         placement="## Placement\n\n" + "\n".join([candidate(1, one), candidate(2, two)]))
        self.assertFails("the section names no chosen candidate in a **Chosen** field", check="chosen")
        self.assertFails("no candidate is chosen, so no placement is shown to be the board's", check="parts at HEAD")

    def test_cited_commits_not_in_the_repository_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a candidate commit missing from the history; Every commit it cites must lie on the last commit's line of history, so a branch whose history was rewritten by a squash or rebase fails rather than passes.
        ghost = "0badc0de" * 5
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.commit(board(PLACES[1]), "b: placement, candidate 2 citing a commit the repository lacks",
                         placement=placement([candidate(1, one), candidate(2, ghost, measures=MEASURES[2])]))
        self.repo.routed()
        rows = [f"| WORK-1 | judgement | quality | fail, then pass at {ghost} | net-A | runs long |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1, citing commits the repository lacks",
                         critical=critical([critical_pass(1, ghost, rows)]))
        self.assertFails(f"candidate 2's commit {ghost} is not in this repository", check="candidate 2 commit")
        self.assertFails(f"pass 1's Board judged commit {ghost} is not in this repository", check="pass 1 board judged")
        self.assertFails(f"pass 1 cites {ghost} for WORK-1, which is not in this repository's history from HEAD",
                         check="pass 1 verdicts")


class CriticalRoutingFails(Base):
    def test_a_board_judged_commit_on_a_side_branch_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: for each pass it fails: a board judged commit that is not an ancestor of the last commit
        self.repo.placed()
        self.repo.commit(board(copper=[HAND]), "b: route A by hand")
        self.repo.git("checkout", "-q", "-b", "elsewhere")
        aside = self.repo.commit(board(copper=[LOCKED]), "b: lock A, on a side branch")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="b: critical routing", critical=critical([critical_pass(1, aside)]))
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router")
        self.assertFails(f"pass 1's Board judged commit {aside} is not in this repository's history from HEAD",
                         check="pass 1 board judged")

    def test_a_first_pass_edited_after_the_second_was_appended_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass that differs from how it stood in the commit before its router commit
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.through_router(judged)
        relocked = track((5, 9), (20, 9), "A", True)
        self.repo.commit(board(copper=[LOCKED]), "b: remove the router's copper")
        second = self.repo.commit(board(copper=[relocked]), "b: re-route A, locked")
        self.repo.commit(message="b: pass 2", critical=critical([critical_pass(1, judged), critical_pass(2, second)]))
        self.repo.commit(board(copper=[relocked, track((5, 11), (20, 11), "GND", False)]), "b: router again")
        edited = ["| WORK-1 | judgement | quality | pass | net-A, whole board, looked at again | |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1 edited",
                         critical=critical([critical_pass(1, judged, edited), critical_pass(2, second)]))
        self.assertFails("pass 1 now differs from the pass in the commit before the router's",
                         check="pass 1 before router")

    def test_a_router_commit_between_the_first_router_and_the_second_passs_board_judged_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: for a later pass, a board judged commit that does not follow the previous pass's router commit, or unlocked copper added or changed between that router commit and it, the router's copper the re-route does not affect being left in place
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.through_router(judged)
        stray = self.repo.commit(board(copper=[LOCKED, track((5, 11), (20, 11.5), "GND", False)]), "b: router ran again")
        second = self.repo.commit(board(copper=[track((5, 9), (20, 9), "A", True)]), "b: re-route A, locked")
        self.repo.commit(message="b: pass 2", critical=critical([critical_pass(1, judged), critical_pass(2, second)]))
        self.assertFails(f"{stray[:12]}, between pass 1's router commit and pass 2's Board judged commit, adds or "
                         "changes 1 unlocked tracks", check="pass 2 board judged")

    def test_a_fail_with_no_commit_putting_it_right_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: an item bearing on the critical nets without exactly one verdict, or a failing verdict not put right before the router ran
        self.repo.placed()
        judged = self.repo.routed()
        rows = ["| WORK-1 | judgement | quality | fail | net-A | runs long |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, rows)]))
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router")
        self.assertFails("pass 1's fail for WORK-1 has no later verdict with the commit that put it right",
                         check="pass 1 verdicts")

    def test_a_fail_put_right_before_the_router_passes_and_one_put_right_after_it_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: an item bearing on the critical nets without exactly one verdict, or a failing verdict not put right before the router ran
        self.repo.placed()
        judged = self.repo.routed()
        fixed = self.repo.commit(board(copper=[track((5, 9), (20, 9.0), "A", True)]), "b: re-route A, locked")
        rows = [f"| WORK-1 | judgement | quality | fail, then pass at {fixed} | net-A | runs long |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, rows)]))
        router = self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router")
        self.assertPasses()
        late = [f"| WORK-1 | judgement | quality | fail, then pass at {router} | net-A | runs long |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1 rewritten", critical=critical([critical_pass(1, judged, late)]))
        self.assertFails(f"cites {router} for WORK-1, which does not come before the router's commit",
                         check="pass 1 verdicts")

    def test_a_checklist_item_neither_judged_nor_listed_or_given_twice_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: an item bearing on the critical nets without exactly one verdict, or a failing verdict not put right before the router ran
        self.repo.placed()
        judged = self.repo.routed()
        rows = ["| WORK-1 | judgement | quality | pass | net-A | |", "| FLOOR-1 | judgement | function | pass | | |"]
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, rows)]))
        self.assertFails("pass 1 neither judges GROUND-1 nor lists it", "pass 1 gives FLOOR-1 2 times",
                         check="pass 1 verdicts")

    def test_a_board_judged_commit_holding_unlocked_copper_or_none_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: for the first pass, a board judged commit that holds no track or holds an unlocked one
        self.repo.placed()
        placed = self.repo.git("rev-parse", "HEAD")
        unlocked = self.repo.commit(board(copper=[HAND]), "b: route A by hand, not locked")
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, unlocked)]))
        self.assertFails("holds 1 unlocked tracks, arcs or vias", check="pass 1 board judged")
        self.repo.commit(message="b: pass 1 judged on the placement", critical=critical([critical_pass(1, placed)]))
        self.assertFails(f"pass 1's Board judged commit {placed[:12]} holds no track, arc or via",
                         check="pass 1 board judged")

    def test_a_later_pass_judged_before_the_previous_passs_router_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: for a later pass, a board judged commit that does not follow the previous pass's router commit
        self.repo.placed()
        judged = self.repo.routed()
        router = self.repo.through_router(judged)
        self.repo.commit(message="b: pass 2, judged on the board before the router",
                         critical=critical([critical_pass(1, judged), critical_pass(2, judged)]))
        self.assertFails(f"pass 2's Board judged commit {judged[:12]} does not follow pass 1's router commit "
                         f"{router[:12]}", check="pass 2 board judged")

    def test_locked_router_copper_in_the_board_judged_commit_fails_with_routed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: when it is told the router has run, a last pass with no router commit
        self.repo.placed()
        self.repo.commit(board(copper=[HAND]), "b: route A by hand")
        judged = self.repo.commit(board(copper=[LOCKED, track((5, 11), (20, 11), "GND", True)]),
                                  "b: lock A, the router's GND copper committed locked with it")
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        lines, _ = self.assertPasses()
        self.assertIn("router not yet run", lines[-1], "locked copper on any net reads as critical routing")
        self.assertFails("--routed says the router has run", "the router's copper is not committed, or is locked",
                         check="pass 1 before router", args=("--routed",))

    def test_tracks_with_no_critical_routing_section_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: Add a second command among the repository's hardware tasks that, from a board's folder, reads its layout plan and the repository's history and judges the order the placement and critical routing sections require, so the cross-checks C2 and C3 ask of the method are made by running it.
        self.repo.placed()
        self.repo.routed()
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router, nothing recorded")
        self.assertFails("holds no `## Critical routing` section", check="critical routing section")

    def test_locked_router_copper_reads_as_router_not_yet_run_and_fails_with_routed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: when it is told the router has run, a last pass with no router commit
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        self.repo.commit(board(copper=[LOCKED, track((5, 11), (20, 11), "GND", True)]), "b: router, its copper locked")
        lines, _ = self.assertPasses()
        self.assertIn("router not yet run", lines[-1], "without --routed, locked router copper is not the router's")
        self.assertFails("--routed says the router has run", "the router's copper is not committed, or is locked",
                         check="pass 1 before router", args=("--routed",))

    def test_no_tracks_and_no_critical_routing_section_fail_with_routed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: when it is told the router has run, a last pass with no router commit
        self.repo.placed()
        self.assertPasses()
        self.assertFails("--routed says the router has run, and no commit carries a track",
                         check="critical routing section", args=("--routed",))

    def test_a_router_commit_that_is_a_merge_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass that differs from how it stood in the commit before its router commit
        self.repo.placed()
        self.repo.commit(board(copper=[HAND]), "b: route A by hand")
        self.repo.git("checkout", "-q", "-b", "router")
        self.repo.commit(board(copper=[HAND, ROUTED]), "b: router, before any pass is recorded")
        self.repo.git("checkout", "-q", "main")
        judged = self.repo.commit(board(copper=[LOCKED]), "b: lock A")
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        merge = self.repo.merge("router", board(copper=[LOCKED, ROUTED]), "merge the router's copper")
        self.assertFails(f"in the merge commit {merge[:12]}, joining 2 lines of history", check="pass 1 before router")

    def test_router_copper_on_two_lines_after_the_board_judged_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: a pass that differs from how it stood in the commit before its router commit
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.git("checkout", "-q", "-b", "router")
        early = self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router, before the pass is recorded")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        late = self.repo.commit(board(copper=[LOCKED, track((5, 11), (20, 11.5), "GND", False)]), "b: router")
        self.repo.merge("router", board(copper=[LOCKED, ROUTED]), "merge both routers")
        self.assertFails("the router's copper first appears on 2 separate lines of history", early[:12], late[:12],
                         check="pass 1 before router")

    def test_unlocked_copper_merged_in_from_another_line_between_the_passes_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: for a later pass, a board judged commit that does not follow the previous pass's router commit, or unlocked copper added or changed between that router commit and it, the router's copper the re-route does not affect being left in place
        self.repo.placed()
        self.repo.commit(board(copper=[HAND]), "b: route A by hand")
        stray = track((5, 11), (20, 11.5), "GND", False)
        self.repo.git("checkout", "-q", "-b", "elsewhere")
        self.repo.commit(board(copper=[HAND, stray]), "b: the router run on another line")
        self.repo.git("checkout", "-q", "main")
        judged = self.repo.commit(board(copper=[LOCKED]), "b: lock A")
        self.repo.through_router(judged)
        merge = self.repo.merge("elsewhere", board(copper=[LOCKED, ROUTED, stray]), "merge the other line's copper")
        relocked = track((5, 9), (20, 9), "A", True)
        self.repo.commit(board(copper=[LOCKED]), "b: remove the router's copper")
        second = self.repo.commit(board(copper=[relocked]), "b: re-route A, locked")
        self.repo.commit(message="b: pass 2", critical=critical([critical_pass(1, judged), critical_pass(2, second)]))
        self.repo.commit(board(copper=[relocked, track((5, 11), (20, 11), "GND", False)]), "b: router again")
        self.assertFails(f"{merge[:12]}, between pass 1's router commit and pass 2's Board judged commit, adds or "
                         "changes 1 unlocked tracks", check="pass 2 board judged")

    def test_a_checklist_item_dropped_in_the_board_judged_commit_and_restored_before_the_router_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: an item bearing on the critical nets without exactly one verdict, or a failing verdict not put right before the router ran
        self.repo.placed()
        self.repo.commit(board(copper=[HAND]), "b: route A by hand")
        self.repo.write("docs/board-design-method.md", METHOD[:METHOD.index("#### GROUND-1")])
        judged = self.repo.commit(board(copper=[LOCKED]), "b: lock A, GROUND-1 dropped from the method")
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, CRITICAL_ROWS[:1])]))
        self.repo.write("docs/board-design-method.md", METHOD)
        self.repo.commit(message="docs: GROUND-1 restored")
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router")
        self.assertFails("pass 1 neither judges GROUND-1 nor lists it", check="pass 1 verdicts")

    def test_a_squash_merged_copy_of_a_compliant_branch_fails_closed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: Every commit it cites must lie on the last commit's line of history, so a branch whose history was rewritten by a squash or rebase fails rather than passes.
        self.repo.git("commit", "-q", "--allow-empty", "-m", "main: root")
        self.repo.git("checkout", "-q", "-b", "board")
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        self.repo.git("checkout", "-q", "main")
        self.repo.git("merge", "-q", "--squash", "board")
        self.repo.git("commit", "-q", "-m", "board, squashed")
        self.repo.git("branch", "-q", "-D", "board")
        self.assertFails("holds no `## Placement` section", check="placement section")
        self.assertFails("is not in this repository's history from HEAD", check="pass 1 board judged")


WIDE = PLAN.replace("(0, 0)–(40, 40)", "(0, 0)–(60, 40)")
#: The plan with R2 appended to low voltage's parts, and with the analog region given bounds and no parts.
WITH_R2 = PLAN.replace("J1, R1 |", "J1, R1, R2 |")
SENSING = "| analog sensing | none: the schematic carries no sensing front end | nothing | none |"
BOUNDED = PLAN.replace(SENSING, "| analog sensing | (40, 0)–(60, 40) | nothing | none |")


class PlanAndCopperFails(Base):
    """The orderings a final review found the command passing."""

    def candidates_two(self, first_board, second_board):
        one = self.repo.commit(first_board, "b: placement candidate 1")
        two = self.repo.commit(second_board, "b: placement candidate 2")
        return one, two

    def record(self, one, two, board_text, chosen=1, measures=None, message="b: placement"):
        measures = measures or {}
        return self.repo.commit(board_text, message, placement=placement(
            [candidate(1, one, measures=measures.get(1)), candidate(2, two, measures=measures.get(2))], chosen))

    def assertOnly(self, failed, *names):
        self.assertEqual(sorted({line.split(":")[0] for line in failed}), sorted(names), "\n".join(failed))

    # --- Candidates are told apart by their placements ---------------------------------------------

    def test_two_candidates_differing_only_in_the_files_text_fail_as_one_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Change the history command so that it fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side rather than by the board file's bytes
        label = '(gr_text "rev B" (at 30 30) (layer "F.SilkS") (uuid ' + uuid() + ') (effects (font (size 1 1))))'
        variants = {"a label": board(PLACES[1], copper=[label]),
                    "the paper size": board(PLACES[1]).replace('(paper "A4")', '(paper "A3")')}
        for name, second in variants.items():
            with self.subTest(differing_in=name):
                self.repo = Repo(self)
                self.assertNotEqual(board(PLACES[1]), second, "the two files differ in their bytes")
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), second)
                self.record(one, two, board(PLACES[1]), measures={2: MEASURES[1]})
                failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
                self.assertOnly(failed, "distinct candidates")

    def test_candidates_differing_in_a_parts_angle_or_in_which_parts_they_hold_are_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[1], r1_angle=180))
        # R1 turned half way round puts its pads at (20, 11) on A and (20, 9) on GND: each net 15.1327 mm, and the two
        # connections cross.
        turned = ["LENGTH | total | 30.2655 mm", "CROSSINGS | total | 1", "OUTSIDE | total | 0"]
        self.record(one, two, board(PLACES[1]), measures={2: turned})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS | no two candidates place their parts alike", "\n".join(lines))

    def test_candidates_holding_different_sets_of_parts_are_distinct_though_one_part_sits_alike(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended to the floorplan")
        two = self.repo.commit(board(PLACES[1], r2=(30, 25)), "b: placement candidate 2, R2 added")
        self.record(one, two, board(PLACES[1], r2=(30, 25)), chosen=2, measures={2: MEASURES[1]})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS", "\n".join(lines))

    def test_candidates_differing_only_by_the_side_their_parts_sit_on_are_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: judged by each part's reference, position, angle and side rather than by the board file's bytes
        self.repo.planned()
        front = board(PLACES[1])
        back = front.replace('(footprint "proof:Part" (layer "F.Cu")', '(footprint "proof:Part" (layer "B.Cu")')
        self.assertNotEqual(front, back)
        one, two = self.candidates_two(front, back)
        self.record(one, two, front, measures={2: MEASURES[1]})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS | no two candidates place their parts alike",
                      "\n".join(lines))

    def test_one_turn_written_two_ways_fails_as_one_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        plain = board(PLACES[1])
        r1 = "(at 20 10)"
        self.assertEqual(plain.count(r1), 1)
        for name, first, second, measures in (("0 and 360", "0", "360", MEASURES[1]),
                                              ("0 and -0", "0", "-0", MEASURES[1]),
                                              ("-90 and 270", "-90", "270", None)):
            with self.subTest(turns=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = plain.replace(r1, f"(at 20 10 {first})" if first != "0" else r1)
                two = plain.replace(r1, f"(at 20 10 {second})")
                self.assertNotEqual(one, two, "the two files differ in their bytes")
                if measures is None:
                    # R1 turned to 270 puts its pads at (21, 10) on A and (19, 10) on GND: 16.0312 mm and 14.0357 mm.
                    measures = ["LENGTH | total | 30.0669 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
                first_commit, second_commit = self.candidates_two(one, two)
                self.record(first_commit, second_commit, one, measures={1: measures, 2: measures})
                failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
                self.assertOnly(failed, "distinct candidates")

    def test_a_negative_zero_in_a_position_reads_as_zero(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        with tempfile.TemporaryDirectory() as directory:
            placed = {}
            for name, at in (("zero", "0 0 0"), ("negative", "-0 -0.0 -0")):
                path = os.path.join(directory, name + ".kicad_pcb")
                with open(path, "w") as handle:
                    handle.write(board_fixtures.layout([footprint("R1", 0, 0, [pad(1, 0, -1, "A", "passive")]).replace(
                        "(at 0 0)", f"(at {at})", 1)]))
                placed[name] = board_history.parts_placed(board_history.locked_copper.read_layout(path))
        self.assertEqual(placed["zero"], placed["negative"])
        self.assertEqual(placed["zero"]["R1"][0], "(0, 0) at 0 degrees")

    def test_turns_a_full_circle_apart_or_a_tiny_step_under_one_stay_whole(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: judged by each part's reference, position, angle and side rather than by the board file's bytes
        self.assertEqual({board_history.turn_text(angle) for angle in (0, 360, -360, 720, -0.0)}, {"0"})
        self.assertEqual(board_history.turn_text(-1e-20), "0")
        self.assertEqual({board_history.turn_text(angle) for angle in (-90, 270, 630)}, {"270"})
        self.assertEqual(board_history.turn_text(180), "180")
        self.assertNotEqual(board_history.turn_text(180), board_history.turn_text(360))
        self.assertEqual(board_history.turn_text(-0.5), "359.5")

    def test_positions_equal_to_six_significant_digits_fail_as_one_placement_and_a_sixth_digit_apart_stay_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a position or angle read to six significant digits
        plain = board(PLACES[1])
        self.repo.planned()
        nudged = plain.replace("(at 20 10)", "(at 20.0000001 10.00000001)")
        self.assertNotEqual(plain, nudged, "the two files differ in their bytes")
        one, two = self.candidates_two(plain, nudged)
        self.record(one, two, plain, measures={2: MEASURES[1]})
        failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
        self.assertOnly(failed, "distinct candidates")
        with tempfile.TemporaryDirectory() as directory:
            placed = {}
            for name, x in (("whole", "20"), ("seventh digit", "20.00001"), ("sixth digit", "20.0001")):
                path = os.path.join(directory, name.replace(" ", "_") + ".kicad_pcb")
                with open(path, "w") as handle:
                    handle.write(board_fixtures.layout([footprint("R1", 0, 0, [pad(1, 0, -1, "A", "passive")]).replace(
                        "(at 0 0)", f"(at {x} 5)", 1)]))
                placed[name] = board_history.parts_placed(board_history.locked_copper.read_layout(path))
        self.assertEqual(placed["whole"], placed["seventh digit"])
        self.assertNotEqual(placed["whole"], placed["sixth digit"])

    def test_a_half_turn_stays_distinct_from_a_full_turn(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        self.repo.planned()
        plain = board(PLACES[1])
        full = plain.replace("(at 20 10)", "(at 20 10 360)")
        half = plain.replace("(at 20 10)", "(at 20 10 180)")
        one, two = self.candidates_two(full, half)
        turned = ["LENGTH | total | 30.2655 mm", "CROSSINGS | total | 1", "OUTSIDE | total | 0"]
        self.record(one, two, full, measures={1: MEASURES[1], 2: turned})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS", "\n".join(lines))

    # --- A pour is the first copper ------------------------------------------------------------------

    def test_a_pour_drawn_before_the_placement_section_is_recorded_is_the_first_track(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        poured = self.repo.commit(board(PLACES[1], copper=[pour()]), "b: a ground pour, drawn by hand")
        self.record(one, two, board(PLACES[1], copper=[pour()]), message="b: placement recorded after the pour")
        self.repo.commit(board(copper=[pour(), HAND]), "b: route A")
        self.assertFails("holds no `## Placement` section", check="placement section")
        _, lines, _ = self.repo.run()
        self.assertIn(f"CHECK | first track | PASS | {short_of(poured)} is the first commit carrying a track, arc, via "
                      "or pour", "\n".join(lines))

    def test_the_same_history_with_the_section_recorded_before_the_pour_keeps_the_order_and_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.placed()
        poured = self.repo.commit(board(copper=[pour()]), "b: a ground pour, drawn by hand")
        judged = self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        lines, _ = self.assertPasses()
        self.assertIn(f"CHECK | first track | PASS | {short_of(poured)} is the first commit carrying a track, arc, via "
                      "or pour", "\n".join(lines))

    def test_a_rule_area_is_no_copper_and_a_history_drawing_one_before_the_section_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a zone that is a rule area being no copper
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        self.repo.commit(board(PLACES[1], copper=[pour(rule_area=True)]), "b: a keepout over the connector")
        self.record(one, two, board(PLACES[1], copper=[pour(rule_area=True)]))
        self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1",
                         critical=critical([critical_pass(1, self.repo.git("rev-parse", "HEAD"))]))
        lines, _ = self.assertPasses()
        first = self.repo.git("rev-parse", "HEAD~2")
        self.assertIn(f"CHECK | first track | PASS | {first[:12]} is the first commit carrying a track", "\n".join(lines),
                      "the hand route, not the rule area, is the first copper")

    def test_a_zone_on_a_layer_that_is_no_copper_is_no_pour_and_one_on_the_back_copper_is(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via, a pour being a zone on a copper layer
        def zone_on(layers):
            return pour().replace('(layer "F.Cu")', layers)
        for name, drawn, copper in (("silkscreen", zone_on('(layer "F.SilkS")'), False),
                                    ("mask", zone_on('(layers "F.Mask" "B.Mask")'), False),
                                    ("back copper", zone_on('(layer "B.Cu")'), True),
                                    ("both coppers", zone_on('(layers "F&B.Cu")'), True)):
            with self.subTest(zone=name):
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.commit(board(PLACES[1], copper=[drawn]), f"b: a zone on the {name}")
                self.record(one, two, board(PLACES[1], copper=[drawn]))
                if copper:
                    self.assertFails("holds no `## Placement` section", check="placement section")
                else:
                    lines, _ = self.assertPasses()
                    self.assertIn("CHECK | first track | PASS | no commit carries a track, arc, via or pour yet",
                                  "\n".join(lines))

    def test_an_unlocked_pour_between_the_board_judged_commit_and_the_router_is_not_the_routers_commit(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.commit(board(copper=[LOCKED, pour()]), "b: an unlocked ground pour, after the critical routing")
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        router = self.repo.commit(board(copper=[LOCKED, pour(), ROUTED]), "b: router")
        lines, _ = self.assertPasses("--routed")
        self.assertIn(f"CHECK | pass 1 before router | PASS | the pass is as it stood before the router's commit "
                      f"{router[:12]}", "\n".join(lines))

    # --- The plan is held to the plan committed before placement --------------------------------------

    def test_a_region_widened_in_the_commit_that_records_the_section_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint
        self.repo.planned()
        one, two = self.candidates_two(board((50, 10)), board(PLACES[2]))
        self.repo.replan(WIDE)
        wide = ["LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.record(one, two, board((50, 10)), measures={1: wide})
        failed = self.assertFails("the region 'low voltage' has the bounds (0, 0)–(60, 40) where the plan before "
                                  "placement gives (0, 0)–(40, 40)", check="plan before placement")
        self.assertOnly(failed, "plan before placement")

    def test_a_region_widened_after_an_unrecorded_placement_and_before_the_first_candidate_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint, the commit the method judges the plan in
        self.repo.planned()
        self.repo.commit(board(PLACES[2]), "b: a placement no section records")
        self.repo.replan(WIDE)
        one, two = self.candidates_two(board((50, 10)), board(PLACES[2]))
        wide = ["LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.record(one, two, board((50, 10)), measures={1: wide})
        self.assertFails("the region 'low voltage' has the bounds (0, 0)–(60, 40)", check="plan before placement")

    def test_a_part_removed_moved_or_a_region_added_in_the_plan_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint
        changes = {
            "a part removed": (PLAN, PLAN.replace("J1, R1 |", "J1 |"),
                               "R1 is listed in the region 'low voltage' in the plan before placement and not now"),
            "a part moved to another region": (BOUNDED, BOUNDED.replace(
                "| nothing | none |\n| digital", "| nothing | R1 |\n| digital"),
                "R1 is listed in the region 'analog sensing', where the plan before placement lists it only in "
                "'low voltage': a reference is not moved between regions"),
            "a bound moved": (BOUNDED, BOUNDED.replace("(40, 0)–(60, 40)", "(35, 0)–(60, 40)"),
                              "the region 'analog sensing' has the bounds (35, 0)–(60, 40) where the plan before "
                              "placement gives (40, 0)–(60, 40)"),
            "a region row added": (PLAN, PLAN.replace("\n\n## Plan", "\n| extra | none | nothing | none |\n\n## Plan"),
                                   "the floorplan's set of region names is"),
        }
        for name, (then, now, words) in changes.items():
            with self.subTest(change=name):
                self.assertNotEqual(then, now, "the change was made to the plan")
                self.repo = Repo(self)
                self.repo.replan(then)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                self.assertFails(words, check="plan before placement")

    def test_a_repeated_region_name_stops_the_plan_check_rather_than_comparing_a_plan_with_its_own_copy(self):
        # SOL-BOARD-FLOORPLAN-REGION-NAMES-DISTINCT.C1: Change the floorplan reader so it stops, naming the region, when two rows of the floorplan carry the same region name, so the history command's plan compare never judges a plan against an identical copy of itself as changed and never hides a change to one row behind another. Tests in throwaway repositories show a plan with a repeated region name stops rather than fails as changed, in the history command and in the placement command, and that a plan with distinct names is read as before.
        twice = PLAN.replace("\n\n## Plan", "\n| digital | none | nothing | none |\n\n## Plan")
        hidden = PLAN.replace("\n\n## Plan", "\n| low voltage | (0, 0)–(60, 40) | a second row | R1 |\n\n## Plan")
        cases = {
            "an identical plan before and after": (twice, twice),
            "the repeat only in the plan judged": (PLAN, twice),
            "the repeat only in the plan before placement": (twice, PLAN),
            "a changed second row behind the first": (PLAN, hidden),
        }
        for name, (then, now) in cases.items():
            with self.subTest(case=name):
                self.repo = Repo(self)
                self.repo.replan(then)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                failed = self.assertFails("repeats the name of an earlier region row", check="plan before placement")
                text = "\n".join(failed)
                self.assertNotIn("set of region names", text)
                self.assertNotIn("has the bounds", text)
                self.assertNotIn("agrees with", text)

    def test_region_names_differing_only_in_case_or_spacing_are_distinct_regions_and_pass(self):
        # SOL-BOARD-FLOORPLAN-REGION-NAMES-DISTINCT.C1: Change the floorplan reader so it stops, naming the region, when two rows of the floorplan carry the same region name, so the history command's plan compare never judges a plan against an identical copy of itself as changed and never hides a change to one row behind another. Tests in throwaway repositories show a plan with a repeated region name stops rather than fails as changed, in the history command and in the placement command, and that a plan with distinct names is read as before.
        variants = PLAN.replace("\n\n## Plan", "\n| Digital | none | nothing | none |\n| digital 2 | none | nothing | none |"
                                "\n\n## Plan")
        self.repo.replan(variants)
        self.repo.placed()
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | plan before placement | PASS |", "\n".join(lines))

    def test_a_part_appended_to_a_region_before_its_footprint_first_appears_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended to low voltage")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        lines, _ = self.assertPasses()
        text = "\n".join(lines)
        self.assertIn("CHECK | plan before placement | PASS | the floorplan in HEAD", text)
        self.assertIn("with R2 appended to its parts, each committed before its footprint first appears on the board",
                      text)
        self.assertIn("CHECK | candidate 1 measures | PASS", text, "candidate 1 is measured without R2, which it lacks")

    def test_a_part_appended_in_the_commit_that_places_it_or_after_it_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name in ("in the same commit", "after"):
            with self.subTest(appended=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
                placed = board(PLACES[2], r2=(30, 25))
                if name == "in the same commit":
                    self.repo.replan(WITH_R2)
                    two = self.repo.commit(placed, "b: candidate 2, with R2 and the amendment in one commit")
                else:
                    two = self.repo.commit(placed, "b: candidate 2, with R2 placed before it is planned")
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="b: R2 appended to low voltage, too late")
                self.record(one, two, placed, chosen=2)
                self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the "
                                 "board at", "but the plan does not list it, after the commit before the first placement",
                                 check="plan before placement")

    def test_a_part_listed_once_dropped_before_placement_and_listed_again_after_it_is_placed_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed with the floorplan")
        self.repo.replan(PLAN)
        self.repo.planned()
        placed = board(PLACES[1], r2=(30, 25))
        one = self.repo.commit(placed, "b: candidate 1 places R2, which the plan dropped")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed again, after it was placed")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: candidate 2")
        self.record(one, two, placed, measures={2: MEASURES[2]})
        failed = self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the "
                                  "board at", "but the plan does not list it, after the commit before the first "
                                  "placement", check="plan before placement")
        self.assertOnly(failed, "plan before placement")

    def test_a_part_placed_in_the_first_placement_commit_and_listed_only_afterwards_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        placed = board(PLACES[1], r2=(30, 25))
        one = self.repo.commit(placed, "b: the first placement holds R2, which the plan does not list")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed after the first placement")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: candidate 2")
        self.record(one, two, placed, measures={2: MEASURES[2]})
        self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the board at "
                         f"{short_of(one)}", check="plan before placement")

    def test_a_part_listed_dropped_and_listed_again_all_before_it_is_placed_passes_as_the_plan_holds_it_when_placed(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended")
        self.repo.replan(PLAN)
        self.repo.commit(message="b: R2 dropped again")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended again")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        self.assertPasses()

    def test_a_part_first_placed_in_a_merge_commit_fails_unless_every_parent_lists_it(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name, main_lists, side_lists in (("every parent lists it", True, True),
                                             ("only the side branch lists it", False, True),
                                             ("only the main line lists it", True, False)):
            with self.subTest(merge_of=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
                self.repo.git("checkout", "-q", "-b", "side")
                if side_lists:
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="side: R2 listed")
                else:
                    self.repo.write("README.md", "one line\n")
                    self.repo.commit(message="side: a change that leaves R2 unlisted")
                side = self.repo.git("rev-parse", "HEAD")
                self.repo.git("checkout", "-q", "main")
                if main_lists:
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="main: R2 listed")
                else:
                    self.repo.write("README.md", "one line\n")
                    self.repo.commit(message="main: a change that leaves R2 unlisted")
                main = self.repo.git("rev-parse", "HEAD")
                two = self.repo.merge("side", board(PLACES[2], r2=(30, 25)), "b: candidate 2, with R2, in a merge")
                self.repo.replan(WITH_R2)
                self.repo.commit(message="b: R2 listed in the plan the section is judged in")
                self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
                if main_lists and side_lists:
                    self.assertPasses()
                else:
                    unlisted = side if main_lists else main
                    failed = self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first "
                                              f"appears on the board at {short_of(two)}",
                                              f"in {short_of(unlisted)}: the amendment", check="plan before placement")
                    self.assertOnly(failed, "plan before placement")

    def test_a_plan_text_the_compare_does_not_cover_may_change_and_the_report_says_what_it_covers(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a region's description, a reason given for no bounds and the order of rows not being compared
        reordered = PLAN.replace("| mains | none: the board carries no mains | nothing | none |\n", "").replace(
            "| digital |", "| mains | none: the board carries no mains | nothing | none |\n| digital |")
        changes = {"a What it holds cell rewritten": PLAN.replace("the connector and its resistor", "something else"),
                   "a reason given for none reworded": PLAN.replace("none: the board carries no mains", "none: no mains"),
                   "the rows reordered": reordered}
        for name, now in changes.items():
            with self.subTest(change=name):
                self.assertNotEqual(PLAN, now, "the change was made to the plan")
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                lines, _ = self.assertPasses()
                self.assertIn(f"in {board_history.PLAN_COMPARED}", "\n".join(lines))

    def test_the_pass_says_none_placed_yet_for_an_appended_part_no_footprint_has_reached(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: each listed in the plan of every parent of the commit where its footprint first appears
        both = PLAN.replace("J1, R1 |", "J1, R1, R2, R3 |")
        for name, plan, placed, words in (
                ("none placed", WITH_R2, None,
                 "with R2 appended to its parts, none placed yet"),
                ("one of two placed", both, (30, 25),
                 "with R2, R3 appended to its parts, R2 committed before its footprint first appears on the board "
                 "and R3 not placed yet")):
            with self.subTest(appended=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without the appended parts")
                self.repo.replan(plan)
                self.repo.commit(message="b: parts appended to low voltage")
                two = self.repo.commit(board(PLACES[2], r2=placed), "b: placement candidate 2")
                self.record(one, two, board(PLACES[2], r2=placed), chosen=2)
                lines, _ = self.assertPasses()
                text = "\n".join(line for line in lines if line.startswith("CHECK | plan before placement"))
                self.assertIn(words, text)
                self.assertNotIn("each committed before its footprint", text)

    def test_a_part_appended_and_placed_after_the_first_copper_passes_with_the_section_left_as_it_is(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        one, two = self.repo.placed()
        self.repo.through_router(self.repo.routed())
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 added to the plan after the router")
        self.repo.commit(board(copper=[LOCKED, ROUTED], r2=(30, 25)), "b: R2 placed after the router")
        lines, _ = self.assertPasses("--routed")
        self.assertNotIn("appended", "\n".join(line for line in lines if line.startswith("CHECK | plan before placement")))
        self.repo.commit(message="b: the placement section recorded again after the first copper",
                         placement=placement([candidate(1, one), candidate(2, two)], 2))
        self.assertFails("section now differs from the one in", check="placement section")

    def test_a_part_appended_before_the_first_copper_is_held_to_the_plan_when_it_is_placed_after_it(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name, kept in (("the plan regenerated without it", False), ("the plan keeping it", True)):
            with self.subTest(plan=name):
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(WITH_R2)
                self.repo.commit(message="b: R2 appended before the first copper, not placed")
                self.record(one, two, board(PLACES[1]))
                self.repo.commit(board(PLACES[1], copper=[HAND]), "b: the first route")
                judged = self.repo.commit(board(PLACES[1], copper=[LOCKED]), "b: lock the route")
                self.repo.through_router(judged)
                self.repo.replan(WITH_R2 if kept else PLAN)
                self.repo.commit(message="b: the plan regenerated")
                self.repo.commit(board(PLACES[1], copper=[LOCKED, ROUTED], r2=(30, 25)),
                                 "b: R2 placed after the first copper")
                if kept:
                    self.assertPasses("--routed")
                else:
                    failed = self.assertFails("R2 is appended to the parts of 'low voltage'", "but the plan does not "
                                              "list it, after the commit before the first placement",
                                              check="plan before placement", args=("--routed",))
                    self.assertOnly(failed, "plan before placement")

    def test_a_part_dropped_from_the_plan_when_it_is_placed_fails_though_listed_earlier_after_the_first_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended")
        self.repo.replan(PLAN)
        self.repo.commit(message="b: R2 dropped")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2 the plan does not hold")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed again, after it was placed")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        self.assertFails("but the plan does not list it, after the commit before the first placement",
                         check="plan before placement")

    def test_a_part_appended_and_placed_after_the_chosen_candidate_still_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        self.repo.replan(WITH_R2)
        self.record(one, two, board(PLACES[1]))
        self.repo.commit(board(copper=[HAND], r2=(30, 25)), "b: R2 placed with the first route")
        self.assertFails("R2 is on the board at", "and not in the chosen candidate", check="parts at first track")

    # --- The commit the plan is judged in comes from the history alone -------------------------------

    def test_a_plan_committed_with_the_first_placement_or_after_it_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        def root():
            self.repo.commit(board(PLACES[1]), "b: plan and first placement together")
            return "the root commit", "first placement"

        def no_plan():
            self.repo.write("README.md", "a repository\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "a root commit")
            self.repo.commit(board(PLACES[1]), "b: plan and first placement together")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        def plan_later():
            self.repo.write("README.md", "a repository\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "a root commit")
            self.repo.write("b/b.kicad_pcb", board(PLACES[1]))
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: placed, no plan yet")
            self.repo.commit(message="b: the plan, after the placement")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        def no_floorplan():
            self.repo.write("README.md", "a repository\n")
            self.repo.write("b/layout-plan.md", "# Layout plan\n\nnothing yet\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: a plan with no floorplan")
            self.repo.write("b/b.kicad_pcb", board(PLACES[1]))
            self.repo.plan()
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: the floorplan, with the first placement")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        for build in (root, no_plan, plan_later, no_floorplan):
            with self.subTest(case=build.__name__):
                self.repo = Repo(self)
                words, check = build()
                self.assertFails(words, check=check)

    def test_footprints_first_appearing_in_a_merge_or_on_two_lines_of_history_fail(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "other")
        self.repo.write("README.md", "one line\n")
        self.repo.commit(message="other: a change")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="main: a change")
        merge = self.repo.merge("other", board(PLACES[1]), "merge, the parts placed in the merge")
        self.assertFails(f"a footprint first appears in the merge commit {merge[:12]}", check="first placement")

        self.repo = Repo(self)
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "other")
        side = self.repo.commit(board(PLACES[1]), "other: parts placed on one line")
        self.repo.git("checkout", "-q", "main")
        here = self.repo.commit(board(PLACES[2]), "main: parts placed on another")
        self.repo.git("merge", "-q", "-s", "ours", "-m", "merge both lines", "other")
        self.assertFails("a footprint first appears on 2 separate lines of history, at", short_of(side),
                         short_of(here), check="first placement")

    def test_a_first_placement_that_does_not_come_before_the_sections_commit_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint, the commit the method judges the plan in
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "side")
        self.repo.write("README.md", "side\n")
        before = self.repo.commit(message="side: the commit before the first placement")
        self.repo.commit(board(PLACES[1]), "side: the first placement")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(board_fixtures.layout([HAND]), "main: copper and no footprint")
        self.repo.git("merge", "-q", "-s", "ours", "-m", "merge the side line", "side")
        self.assertFails(f"the commit before the first placement, {before[:12]}, is not an ancestor of",
                         check="first placement")

    def test_a_board_that_never_holds_a_footprint_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        self.repo.planned()
        self.repo.commit(board_fixtures.layout([]), "b: an empty board")
        self.assertFails("no commit's board holds a footprint", check="first placement")

    def test_a_plan_committed_alone_before_the_first_placement_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.placed()
        planned = self.repo.git("rev-parse", "HEAD~3")
        lines, _ = self.assertPasses()
        text = "\n".join(lines)
        self.assertIn("CHECK | first placement | PASS", text)
        self.assertIn(f"in the commit before it, {planned[:12]}", text,
                      "the plan is judged in the commit before the first placement")
        self.assertIn("CHECK | plan before placement | PASS | the floorplan in HEAD", text)



class Refusals(Base):
    def assertRefused(self, *words, board=None):
        status, lines, document = self.repo.run(board=board)
        self.assertEqual(status, 2, "\n".join(lines))
        self.assertEqual(document["result"], "REFUSED")
        self.assertEqual(document["checks"], [], "a refused history is not judged at all")
        self.assertTrue(lines[-1].startswith("RESULT | REFUSED |"), lines[-1])
        for word in words:
            self.assertTrue(any(word in line for line in lines if line.startswith("REFUSED |")), "\n".join(lines))
            self.assertTrue(any(word in refusal["what"] or word in refusal["why"] for refusal in document["refusals"]),
                            document["refusals"])
        return document

    def test_a_shallow_clone_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It refuses, without judging, a folder outside a git work tree, a shallow clone, a board or plan that is untracked or differs from the last commit, and a board that cannot be read.
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        shallow = os.path.join(self.repo.root, "shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.repo.path}", shallow], check=True,
                       capture_output=True)
        self.assertRefused("the repository is a shallow clone, which lacks the commits the records cite",
                           board=os.path.join(shallow, "b", "b.kicad_pcb"))

    def test_a_board_or_plan_differing_from_head_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It refuses, without judging, a folder outside a git work tree, a shallow clone, a board or plan that is untracked or differs from the last commit, and a board that cannot be read.
        self.repo.placed()
        self.repo.write("b/b.kicad_pcb", board((22, 10)))
        self.assertRefused("has changes that are not committed")
        self.repo.git("checkout", "--", "b/b.kicad_pcb")
        self.repo.write("b/layout-plan.md", PLAN)
        self.assertRefused("b/layout-plan.md")

    def test_a_board_outside_a_git_work_tree_or_unreadable_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It refuses, without judging, a folder outside a git work tree, a shallow clone, a board or plan that is untracked or differs from the last commit, and a board that cannot be read.
        loose = os.path.join(self.repo.root, "loose")
        os.makedirs(loose)
        with open(os.path.join(loose, "b.kicad_pcb"), "w", encoding="utf-8") as handle:
            handle.write(board())
        self.assertRefused("not inside a git work tree", board=os.path.join(loose, "b.kicad_pcb"))
        self.repo.commit("(not_a_board)\n", "b: not a board")
        self.assertRefused("is not a KiCad layout")

    def test_an_untracked_board_or_plan_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It refuses, without judging, a folder outside a git work tree, a shallow clone, a board or plan that is untracked or differs from the last commit, and a board that cannot be read.
        self.repo.placed()
        for name in ("b/b.kicad_pcb", "b/layout-plan.md"):
            with self.subTest(untracked=name):
                self.repo.git("rm", "-q", "--cached", name)
                self.repo.git("commit", "-q", "-m", f"stop tracking {name}")
                document = self.assertRefused("is not tracked in the repository")
                self.assertEqual([refusal["what"] for refusal in document["refusals"]], [name])
                self.repo.git("add", name)
                self.repo.git("commit", "-q", "-m", f"track {name} again")


class Output(Base):
    def test_the_text_and_json_outputs_give_the_same_verdicts(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It writes its verdicts as text and as JSON and exits differently for a pass, a failure and a refusal; the hardware tools' guide describes it as it describes the other hardware commands.
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=PLACEMENT_ROWS[:1])]))
        status, lines, document = self.repo.run()
        self.assertEqual(status, 1)
        from_text = [line.split(" | ", 3)[1:] for line in lines if line.startswith("CHECK | ")]
        from_json = [[check["check"], check["verdict"], board_history.clean(check["detail"])]
                     for check in document["checks"]]
        self.assertEqual(from_text, from_json)
        self.assertIn(["candidate 2 verdicts", "FAIL", "candidate 2's verdict table has no row for the placement item "
                       "WORK-1"], from_json)
        self.assertEqual(lines[-1], f"RESULT | {document['result']} | {document['detail']}")
        self.assertEqual(len(lines), len(from_text) + 1, "every line but the result is a check")

    def test_the_task_runs_the_command_from_the_repositorys_taskfile(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: Add a second command among the repository's hardware tasks that, from a board's folder, reads its layout plan and the repository's history and judges the order the placement and critical routing sections require, so the cross-checks C2 and C3 ask of the method are made by running it.
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.through_router(judged)
        result = subprocess.run(["task", "hw:history", "--", "--board", self.repo.board], cwd=REPO,
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT | PASS |", result.stdout)
        self.repo.commit(message="b: pass 1 edited after the router", critical=critical([critical_pass(
            1, judged, CRITICAL_ROWS[:1] + ["| GROUND-1 | judgement | function | pass | | |"])]))
        result = subprocess.run(["task", "hw:history", "--", "--board", self.repo.board], cwd=REPO,
                                capture_output=True, text=True, timeout=300)
        self.assertNotEqual(result.returncode, 0, "a failing history fails the task")
        self.assertIn("CHECK | pass 1 before router | FAIL |", result.stdout)



class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    def test_the_guide_and_the_task_describe_the_command(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C6: It writes its verdicts as text and as JSON and exits differently for a pass, a failure and a refusal; the hardware tools' guide describes it as it describes the other hardware commands.
        readme = self.read("hardware", "README.md")
        section = readme[readme.index("## The placement and critical routing history"):]
        section = section[:section.index("\n## ")]
        for words in ("task hw:history -- --board <board>.kicad_pcb", "git and Python only", "first track",
                      "two separate lines of history", "### Candidate <n>", "### Pass <n>", "router commit",
                      "`CHECK | <check> | PASS | <detail>`", "`RESULT | REFUSED`", "`before first track`",
                      "`router not yet run`", "`--json`", "never squashed, rebased or force-pushed", "shallow clone",
                      "differs from the checked-out commit", "0 when every check passes, 1 when any fails, and 2 when "
                      "the command is refused", "`--routed`", "rather than reading as `router not yet run`",
                      "against the floorplan in the commit the section is judged in", "in a merge commit"):
            with self.subTest(words=words):
                self.assertIn(words, section)

    def test_the_guide_and_the_task_state_each_hardened_behaviour(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: The hardware tools' guide, the task's description and the command's own description state each changed behaviour, so none of them contradicts the command on what counts as first copper, what makes candidates distinct, or what the plan is compared with.
        readme = self.read("hardware", "README.md")
        section = readme[readme.index("## The placement and critical routing history"):]
        section = section[:section.index("\n## ")]
        for words in ("a straight track, an arc, a via or a copper pour", "a rule area, a zone carrying a keepout, carries "
                      "no net and is no copper", "an unfilled outline included", "the first commit whose board holds a "
                      "footprint", "from the history alone and never from the placement section",
                      "a commit before the first placement that holds no readable floorplan",
                      "held to the floorplan in the commit before the first placement",
                      "a reference appended to a region's parts, with no bound changed and no reference removed or moved "
                      "between regions", "so a reference listed once, dropped, placed and listed again fails, as does one "
                      "listed in the commit that places it or after", "not by the board file's bytes",
                      "when no commit carries copper yet, a track, an arc, a via or a pour",
                      "the floorplan is read as the commit before the first copper holds it, so a reference appended "
                      "only after that copper is not compared, while one appended before it and placed after it is "
                      "still held to the plan in the commit before the one that places it",
                      "a zone on a copper layer, one whose name ends in `.Cu`",
                      "a zone on a layer that is no copper, silkscreen or mask for one, is no pour",
                      "two files differing only in a text label or an identifier are one placement",
                      "with the references the plan appended removed where that commit's board does not hold them"):
            with self.subTest(words=words):
                self.assertIn(words, section)
        self.assertNotIn("a straight track, an arc or a via", section)
        self.assertNotIn("compares nothing", " ".join(readme.split()))
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:history:"):]
        task = task[:task.index("\n\n")]
        for words in ("a track, an arc, a via or a copper pour on a copper layer, a rule area being none",
                      "by reference, position, angle and side and not by the file's bytes",
                      "the first commit whose board holds a footprint",
                      "the only difference allowed is a reference appended to a region's parts, committed before its "
                      "footprint first appears and kept in the plan until then", "a commit before the first placement with no readable floorplan"):
            with self.subTest(task=words):
                self.assertIn(words, task)
        doc = " ".join(board_history.__doc__.split())
        for words in ("a copper pour", "a rule area, a zone", "carrying a keepout", "The first placement, the first "
                      "commit whose board holds a footprint", "never from the placement section", "The plan, the "
                      "floorplan in the commit the placement section is judged in", "the only difference allowed being "
                      "a reference appended to a region's parts", "so a part appended only after that copper is not "
                      "compared, while one appended before it and placed after it is still held to the plan in each "
                      "commit just before its footprint first appears", "by reference, position, angle and side and not "
                      "by the bytes of the board file"):
            with self.subTest(docstring=words):
                self.assertIn(words, doc)
        self.assertIn("`task hw:history`", readme[:readme.index("## The locked-copper check")])
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:history:"):]
        task = task[:task.index("\n\n")]
        for words in ("board_history.py", "layout-plan.md", "git and Python", "--routed"):
            self.assertIn(words, task)
        self.assertLess(taskfile.index("  hw:placement:"), taskfile.index("  hw:history:"))
        test = taskfile[taskfile.index("  hw:test:"):]
        self.assertIn("the placement and critical routing history check", test.splitlines()[1],
                      "hw:test's description names the tools it tests")

    def test_every_site_describing_the_plan_compare_carries_the_one_sentence_and_none_a_falsehood(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: The hardware tools' guide, the task's description and the command's own description state each changed behaviour, so none of them contradicts the command on what counts as first copper, what makes candidates distinct, or what the plan is compared with.
        canonical = ("the set of region names, each region's bounds and each region's parts; no other text in the "
                     "table is compared")
        self.assertEqual(board_history.PLAN_COMPARED, canonical)

        def flat(text):
            return " ".join(text.split())

        readme = self.read("hardware", "README.md")
        readme = readme[readme.index("## The placement and critical routing history"):]
        readme = readme[:readme.index("\n## ")]
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:history:"):]
        task = task[:task.index("\n\n")]
        # Each site, split into the units that each state a whole sentence's worth of what the command does: a line of
        # the guides, a bullet of the docstring, the one description of the task. A unit that says the floorplan is
        # held to another, or differs from it, is describing the compare and carries the sentence.
        sites = {"guide": (readme.splitlines(), 1), "task": ([task], 1),
                 "method": (self.read("docs", "board-design-method.md").splitlines(), 3),
                 "docstring": (re.split(r"\n- ", board_history.__doc__), 1)}
        describing = ("holds the floorplan", "held to the floorplan", "held to the plan", "differs from the one in",
                      "agrees with the one in", "compared with", "compares", "the floorplan in")

        def describes(unit):
            if any(words in unit for words in describing[:5]):
                return True
            # The wider phrases name no plan themselves: a unit using one describes the plan compare when it speaks of
            # the plan, and not when it speaks of what a candidate is measured against.
            return (any(words in unit for words in describing[5:]) and "measure" not in unit
                    and re.search(r"\bplan\b|floorplan", unit) is not None)

        false = ("region row", "must be the same", "the same regions", "the same bounds", "the same parts",
                 "compares nothing further", "in the table is the same")
        for name, (units, expected) in sites.items():
            units = [flat(unit) for unit in units]
            described = [unit for unit in units if describes(unit)]
            with self.subTest(site=name):
                self.assertEqual(len([unit for unit in units if canonical in unit]), expected,
                                 f"the {name} states the compare in the one sentence, {expected} time(s)")
                for unit in described:
                    self.assertIn(canonical, unit, f"a unit of the {name} describes the compare without the sentence")
                    for words in false:
                        self.assertNotIn(words, unit)
        source = flat(self.read("hardware", "tools", "board_history.py"))
        for words in false:
            with self.subTest(source=words):
                self.assertNotIn(words, source)

    def test_nothing_the_command_prints_or_the_guides_say_calls_the_first_copper_a_track_only(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: none of them contradicts the command on what counts as first copper
        readme = self.read("hardware", "README.md")
        readme = readme[readme.index("## The placement and critical routing history"):]
        readme = readme[:readme.index("\n## ")]
        method = self.read("docs", "board-design-method.md")
        source = self.read("hardware", "tools", "board_history.py")
        for name, text in (("README", readme), ("method", method), ("source", source)):
            flat = " ".join(text.split())
            for stale in ("when no commit carries a track yet", "the board carries tracks", "no commit carries a track and",
                          "no commit carries a track yet", "commit carrying a track, an arc or a via",
                          "carries a straight track, an arc or a via"):
                with self.subTest(file=name, stale=stale):
                    self.assertNotIn(stale, flat)

if __name__ == "__main__":
    unittest.main()
