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


def board(r1=(20, 10), r1_angle=0, copper=()):
    """J1 at (5, 10) and R1 at `r1`, each with a pad on net A above its centre and on GND below it, and `copper`."""
    parts = [footprint("J1", 5, 10, [pad(1, 0, -1, "A", "passive"), pad(2, 0, 1, "GND", "passive")]),
             footprint("R1", r1[0], r1[1], [pad(1, 0, -1, "A", "passive", r1_angle),
                                            pad(2, 0, 1, "GND", "passive", r1_angle)], angle=r1_angle)]
    return board_fixtures.layout(parts + list(copper))


def track(start, end, net, locked):
    """A straight track in the form KiCad writes it."""
    return (f'(segment (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) (width 0.25) (layer "F.Cu")'
            + (" (locked yes)" if locked else "") + f' (net "{net}") (uuid {uuid()}))')


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
        self.write("b/layout-plan.md", PLAN + "".join(f"\n{text}" for text in self.sections.values() if text))

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

    def placed(self, chosen=1):
        """Two candidates committed, then the placement section with the chosen layout: the candidates' commits."""
        one = self.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.commit(board(PLACES[2]), "b: placement candidate 2")
        self.commit(board(PLACES[chosen]), "b: placement chosen",
                    placement=placement([candidate(1, one), candidate(2, two)], chosen))
        return one, two

    def routed(self):
        """The critical net routed by hand and committed unlocked, then locked; the Board judged commit."""
        self.commit(board(copper=[HAND]), "b: route A by hand")
        return self.commit(board(copper=[LOCKED]), "b: lock A")

    def through_router(self, judged):
        """Pass 1 recorded and committed, then the router's commit; the router's commit."""
        self.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        return self.commit(board(copper=[LOCKED, ROUTED]), "b: router")


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

    def assertFails(self, *words, check=None):
        status, lines, document = self.repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertEqual(document["result"], "FAIL")
        failed = checks(document)
        for word in words:
            self.assertTrue(any(word in line and (check is None or line.startswith(check + ":")) for line in failed),
                            f"no failed check{' ' + check if check else ''} says '{word}':\n" + "\n".join(failed))
        return failed


class Passes(Base):
    def test_a_compliant_placement_before_any_track_passes_judged_at_head(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.placed()
        lines, document = self.assertPasses()
        self.assertIn("before first track", lines[-1])
        self.assertIn("CHECK | first track | PASS | no commit carries a track, arc or via yet", "\n".join(lines))
        self.assertIn("CHECK | parts at HEAD | PASS", "\n".join(lines))
        self.assertFalse(any(check["check"].startswith("pass ") for check in document["checks"]),
                         "no critical routing is judged before the first track")

    def test_a_compliant_history_after_the_router_passes_and_a_hand_route_before_locking_is_not_the_routers(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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

    def test_a_pass_recorded_before_the_router_runs_is_judged_at_head_and_says_so(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        lines, _ = self.assertPasses()
        self.assertIn("router not yet run", lines[-1])

    def test_a_second_pass_appended_after_a_placement_change_passes(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C4: A finding against a workmanship item caused by where parts sit is closed by changing the placement, re-routing what it affects and repeating the placement measures, and its record names the change and the measures before and after.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement heading", placement="## Placement\n")
        self.repo.commit(board(copper=[HAND]), "b: route A")
        self.repo.commit(message="b: placement filled in",
                         placement=placement([candidate(1, one), candidate(2, two)]))
        self.assertFails("holds no `### Candidate` heading", "now differs from the one in the commit before the first "
                         "track", check="placement section")

    def test_a_part_moved_in_the_first_tracks_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.placed()
        self.repo.commit(board(r1_angle=180, copper=[HAND]), "b: route A, R1 turned")
        self.assertFails("R1 is at (20, 10) at 0 degrees on F.Cu in the chosen candidate, and at (20, 10) at 180 "
                         "degrees on F.Cu", check="parts at first track")

    def test_a_candidate_off_heads_line_of_history_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.git("checkout", "-q", "-b", "elsewhere")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2, on a side branch")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="b: placement", placement=placement([candidate(1, one), candidate(2, two)]))
        self.repo.commit(board(copper=[HAND]), "b: route A")
        self.assertFails(f"candidate 2's commit {two} is not in this repository's history from HEAD",
                         check="candidate 2 commit")

    def test_a_candidate_merged_in_only_after_the_first_track_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(message="b: placement candidate 2, the same layout")
        self.repo.commit(message="b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, measures=MEASURES[1])]))
        self.assertFails("candidates 1 and 2 hold the same board", check="distinct candidates")

    def test_a_recorded_measure_the_candidates_commit_does_not_measure_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        wrong = ["LENGTH | total | 35 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, measures=wrong)]))
        self.assertFails("candidate 2 does not record 'LENGTH | total | 40 mm'",
                         "candidate 2 records 'LENGTH | total | 35 mm'", check="candidate 2 measures")

    def test_a_verdict_table_missing_a_placement_items_row_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=PLACEMENT_ROWS[:1])]))
        self.assertFails("candidate 2's verdict table has no row for the placement item WORK-1",
                         check="candidate 2 verdicts")

    def test_a_verdict_outside_the_three_or_a_not_applicable_the_plan_does_not_mark_no_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        two = self.repo.commit(board(PLACES[2]), "b: placement candidate 2")
        rows = ["| FLOOR-1 | not applicable | | |", "| WORK-1 | fine | | |"]
        self.repo.commit(board(PLACES[1]), "b: placement",
                         placement=placement([candidate(1, one), candidate(2, two, rows=rows)]))
        self.assertFails("gives FLOOR-1 not applicable, and the plan table does not mark it no",
                         "gives WORK-1 the verdict 'fine'", check="candidate 2 verdicts")

    def test_tracks_first_appearing_on_two_lines_of_history_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.placed()
        self.repo.git("checkout", "-q", "-b", "other")
        self.repo.commit(board(copper=[track((5, 11), (20, 11), "GND", False)]), "b: GND on one line")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(board(copper=[HAND]), "b: A on another")
        subprocess.run(["git", "merge", "-q", "-m", "merge", "other"], cwd=self.repo.path, capture_output=True)
        self.repo.write("b/b.kicad_pcb", board(copper=[HAND, track((5, 11), (20, 11), "GND", False)]))
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "merge both lines")
        self.assertFails("tracks first appear on 2 separate lines of history", check="first track")

    def test_a_track_in_the_root_commit_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.commit(board(copper=[HAND]), "b: everything at once")
        self.assertFails("the root commit", check="first track")

    def test_one_candidate_a_renders_not_naming_its_commit_and_a_chosen_part_outside_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.commit(board(PLACES[1]), "b: placed, nothing recorded")
        self.assertFails("holds no `## Placement` section", check="placement section")


class CriticalRoutingFails(Base):
    def test_a_board_judged_commit_on_a_side_branch_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C4: A finding against a workmanship item caused by where parts sit is closed by changing the placement, re-routing what it affects and repeating the placement measures, and its record names the change and the measures before and after.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C4: A finding against a workmanship item caused by where parts sit is closed by changing the placement, re-routing what it affects and repeating the placement measures, and its record names the change and the measures before and after.
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.through_router(judged)
        stray = self.repo.commit(board(copper=[LOCKED, track((5, 11), (20, 11.5), "GND", False)]), "b: router ran again")
        second = self.repo.commit(board(copper=[track((5, 9), (20, 9), "A", True)]), "b: re-route A, locked")
        self.repo.commit(message="b: pass 2", critical=critical([critical_pass(1, judged), critical_pass(2, second)]))
        self.assertFails(f"{stray[:12]}, between pass 1's router commit and pass 2's Board judged commit, adds or "
                         "changes 1 unlocked tracks", check="pass 2 board judged")

    def test_a_fail_with_no_commit_putting_it_right_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        self.repo.placed()
        judged = self.repo.routed()
        rows = ["| WORK-1 | judgement | quality | fail | net-A | runs long |", CRITICAL_ROWS[1]]
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, rows)]))
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router")
        self.assertFails("pass 1's fail for WORK-1 has no later verdict with the commit that put it right",
                         check="pass 1 verdicts")

    def test_a_fail_put_right_before_the_router_passes_and_one_put_right_after_it_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        self.repo.placed()
        judged = self.repo.routed()
        rows = ["| WORK-1 | judgement | quality | pass | net-A | |", "| FLOOR-1 | judgement | function | pass | | |"]
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, judged, rows)]))
        self.assertFails("pass 1 neither judges GROUND-1 nor lists it", "pass 1 gives FLOOR-1 2 times",
                         check="pass 1 verdicts")

    def test_a_board_judged_commit_holding_unlocked_copper_or_none_fails(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        self.repo.placed()
        unlocked = self.repo.commit(board(copper=[HAND]), "b: route A by hand, not locked")
        self.repo.commit(message="b: pass 1", critical=critical([critical_pass(1, unlocked)]))
        self.assertFails("holds 1 unlocked tracks, arcs or vias", check="pass 1 board judged")

    def test_tracks_with_no_critical_routing_section_fail(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        self.repo.placed()
        self.repo.routed()
        self.repo.commit(board(copper=[LOCKED, ROUTED]), "b: router, nothing recorded")
        self.assertFails("holds no `## Critical routing` section", check="critical routing section")

    def test_a_squash_merged_copy_of_a_compliant_branch_fails_closed(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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


class Refusals(Base):
    def assertRefused(self, *words, board=None):
        status, lines, document = self.repo.run(board=board)
        self.assertEqual(status, 2, "\n".join(lines))
        self.assertEqual(document["result"], "REFUSED")
        self.assertEqual(document["checks"], [], "a refused history is not judged at all")
        self.assertTrue(lines[-1].startswith("RESULT | REFUSED |"), lines[-1])
        for word in words:
            self.assertTrue(any(word in line for line in lines if line.startswith("REFUSED |")), "\n".join(lines))

    def test_a_shallow_clone_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.placed()
        self.repo.through_router(self.repo.routed())
        shallow = os.path.join(self.repo.root, "shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.repo.path}", shallow], check=True,
                       capture_output=True)
        self.assertRefused("the repository is a shallow clone, which lacks the commits the records cite",
                           board=os.path.join(shallow, "b", "b.kicad_pcb"))

    def test_a_board_or_plan_differing_from_head_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        self.repo.placed()
        self.repo.write("b/b.kicad_pcb", board((22, 10)))
        self.assertRefused("has changes that are not committed")
        self.repo.git("checkout", "--", "b/b.kicad_pcb")
        self.repo.write("b/layout-plan.md", PLAN)
        self.assertRefused("b/layout-plan.md")

    def test_a_board_outside_a_git_work_tree_or_unreadable_is_refused(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
        loose = os.path.join(self.repo.root, "loose")
        os.makedirs(loose)
        with open(os.path.join(loose, "b.kicad_pcb"), "w", encoding="utf-8") as handle:
            handle.write(board())
        self.assertRefused("not inside a git work tree", board=os.path.join(loose, "b.kicad_pcb"))
        self.repo.commit("(not_a_board)\n", "b: not a board")
        self.assertRefused("is not a KiCad layout")


class Output(Base):
    def test_the_text_and_json_outputs_give_the_same_verdicts(self):
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C2: The placement is recorded in the layout plan, and its cross-check confirms from the history that the placement section and every candidate's commit came before the first commit carrying a track.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
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
        # SOL-BOARD-LAYOUT-PLACEMENT-CHECKPOINTS.C3: The critical routing section is committed before the router runs, with a cross-check that the history shows that section before the first commit carrying the router's tracks.
        readme = self.read("hardware", "README.md")
        section = readme[readme.index("## The placement and critical routing history"):]
        section = section[:section.index("\n## ")]
        for words in ("task hw:history -- --board <board>.kicad_pcb", "git and Python only", "first track",
                      "two separate lines of history", "### Candidate <n>", "### Pass <n>", "router commit",
                      "`CHECK | <check> | PASS | <detail>`", "`RESULT | REFUSED`", "`before first track`",
                      "`router not yet run`", "`--json`", "never squashed, rebased or force-pushed", "shallow clone",
                      "differs from the checked-out commit", "0 when every check passes, 1 when any fails, and 2 when "
                      "the command is refused"):
            with self.subTest(words=words):
                self.assertIn(words, section)
        self.assertIn("`task hw:history`", readme[:readme.index("## The locked-copper check")])
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:history:"):]
        task = task[:task.index("\n\n")]
        for words in ("board_history.py", "layout-plan.md", "git and Python"):
            self.assertIn(words, task)
        self.assertLess(taskfile.index("  hw:placement:"), taskfile.index("  hw:history:"))
        test = taskfile[taskfile.index("  hw:test:"):]
        self.assertIn("the placement and critical routing history check", test.splitlines()[1],
                      "hw:test's description names the tools it tests")

if __name__ == "__main__":
    unittest.main()
