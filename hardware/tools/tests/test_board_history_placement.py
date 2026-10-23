#!/usr/bin/env python3
"""The placement and critical routing history check, run on throwaway git repositories: the placement part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_history  # noqa: E402
from board_history_fixtures import Base, CRITICAL_ROWS, HAND, LOCKED, MEASURES, METHOD, PLACEMENT_ROWS, PLACES, PLAN, board, candidate, critical, critical_pass, placement, track  # noqa: E402,F401


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
