#!/usr/bin/env python3
"""The placement and critical routing history check, run on throwaway git repositories: the critical part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_history  # noqa: E402
from board_history_fixtures import Base, CRITICAL_ROWS, HAND, LOCKED, METHOD, PLACEMENT_ROWS, PLACES, PLAN, REPO, ROUTED, board, candidate, critical, critical_pass, placement, track  # noqa: E402,F401


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

    def test_the_drawing_item_in_the_methods_circuit_catalogue_leaves_the_layout_checklist_unchanged(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C2: The layout checklist the board history check builds is unchanged by the item, shown by the existing test of that isolation passing with the item in the method.
        method = self.read("docs", "board-design-method.md")
        start = method.index("### Drawing (DRAW)")
        end = method.index("\nOut of scope for this section: applying the catalogue to a board", start)
        without = method[:start] + method[end:]
        self.assertNotIn("#### DRAW-1.", without)
        checklist = board_history.catalogue(method)
        self.assertTrue(checklist, "the method's layout catalogue holds items")
        self.assertEqual(checklist, board_history.catalogue(without))
        self.assertFalse([name for name in checklist if name.startswith("DRAW")])
        circuit = method[method.index("## Circuit practice catalogue"):]
        item = circuit[circuit.index("#### DRAW-1."):]
        item = item[:item.index("\n\n", item.index("- **Source:**"))]
        for field in ("**Applies when:** always", "**Asks:**", "**Passes:**", "**Fails, as the schematic shows it:**",
                      "**Kind:** judgement. **Severity:** cosmetic.", "**Source:**", "read 2026-10-18"):
            with self.subTest(field=field):
                self.assertIn(field, item)

    def test_the_review_names_a_sheet_in_the_net_or_part_column_and_in_every_text_on_the_rows_a_record_may_name(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C2: The review's verdict table names the sheet in its Net or part column for the item, and the method's text on that column and on the names a record may carry is amended to allow it.
        method = self.read("docs", "board-design-method.md")
        review = method[method.index("## Schematic review"):method.index("## Planning the layout")]
        for words in ("**Net or part** is one net name, one reference designator or one sheet name",
                      "`DRAW-1` selects every sheet", "every net and every part of the netlist exported from the schematic in that commit, and every sheet of that schematic, has a row",
                      "a sheet the schematic holds, that no row of the next step names fails the round",
                      "every net, part and sheet it selects"):
            with self.subTest(words=words):
                self.assertIn(words, review)
        self.assertNotIn("is one net name or one reference designator, or", review)

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
