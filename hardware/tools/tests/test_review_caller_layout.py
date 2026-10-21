#!/usr/bin/env python3
"""The layout review as a caller of the review fan-out command, over synthetic review folders.

The caller is loaded and run as shipped: its units, prompts, tool grant and merge are exercised through the
fan-out command's own functions, and through the command itself against the stub that plays the agent command line.
The method, the plan, the board and every verdict are synthetic. No model and no KiCad is used.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_history  # noqa: E402
import board_review_history  # noqa: E402
import layout_fixtures as fx  # noqa: E402
import review_caller_layout  # noqa: E402
import review_folder  # noqa: E402
import review_fan_out  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
STUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_fan_out_stub.py")
ITEMS = {"area-FLOOR": ["FLOOR-1", "FLOOR-2"], "area-GROUND": ["GROUND-1"], "area-CLOCK": ["CLOCK-1"]}


def verdict(item, outcome="pass", why="Judged on the views.", rests="layer-F.Cu"):
    return {"Item": item, "Kind": "judgement", "Severity": "function", "Verdict": outcome, "Rests on": rests, "Why": why}


def finding(number, item, what="layer-F.Cu at (10, 10): a part is off its place", raised=None):
    return {"Finding": number, "Item": item, "Raised by": raised or item, "Severity": "function", "What and where": what,
            "Rule": "no", "Added as": "", "Planning shortfall": "—", "Closed by": ""}


def note(text):
    return {"Note": text}


def results(items=ITEMS, plan_notes=("Compared every region with the plan; the free pass found nothing else.",), **extra):
    """A synthetic result for every unit of a full round with no board items: every item passes."""
    found = {unit: {"Verdicts": [verdict(item) for item in ids]} for unit, ids in items.items()}
    found["plan-and-free-pass"] = {"Plan and free pass": [note(text) for text in plan_notes]}
    for unit, tables in extra.items():
        found[unit.replace("_", "-")] = tables
    return found


def caller_for(folder):
    caller = review_fan_out.load_caller("layout", TOOLS)
    review_fan_out.Run(caller, folder, "unused", "unused", 2, None, 0).resolve_checklist()
    return caller


def merged(folder, given, order=None):
    caller = caller_for(folder)
    return review_fan_out.merge(caller, folder, order or list(given), given)


class Folder(unittest.TestCase):
    """A review folder the folder command wrote from a synthetic repository, in a temporary folder."""

    own = fx.OWN_NONE
    narrow = False
    number = 1

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="layout-caller-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.folder = fx.write_review_folder(self.root, own=self.own, number=self.number, narrow=self.narrow,
                                             kind="narrow" if self.narrow else "full")

    def refused(self, call, *words):
        with self.assertRaises(review_fan_out.Refused) as caught:
            call()
        text = "; ".join(caught.exception.causes)
        for word in words:
            self.assertIn(word, text)
        return text


class TheUnits(Folder):
    def test_a_full_round_has_a_unit_for_each_catalogue_area_and_one_for_the_plan_and_the_free_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.assertEqual(review_fan_out.unit_names(caller, self.folder),
                         ["area-FLOOR", "area-GROUND", "area-CLOCK", "plan-and-free-pass"])

    def test_the_checklist_is_the_catalogue_in_the_methods_order_and_no_other_section(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        self.assertEqual(review_caller_layout.checklist(self.folder),
                         ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", review_caller_layout.PLAN_ENTRY])
        self.assertEqual(review_caller_layout.unit_items(self.folder)["area-FLOOR"], ["FLOOR-1", "FLOOR-2"])

    def test_the_real_method_gives_a_unit_for_each_of_its_catalogue_areas(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        with open(os.path.join(REPO, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            method = handle.read()
        os.remove(os.path.join(self.folder, "docs", "board-design-method.md"))
        fx.write(os.path.join(self.folder, "docs", "board-design-method.md"), method)
        found = review_caller_layout.areas(self.folder)
        self.assertEqual([item for _, _, ids in found for item in ids], list(board_history.catalogue(method)))
        self.assertGreater(len(found), 1)
        self.assertTrue(all(ids for _, _, ids in found), "an area heading of the real method holds no item")

    def test_a_method_with_no_catalogue_areas_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        caller = review_fan_out.load_caller("layout", TOOLS)
        method = os.path.join(self.folder, "docs", "board-design-method.md")
        with open(method, encoding="utf-8") as handle:
            text = handle.read()
        fx.write(method, re.sub(r"^### (Floorplan|Grounding|Clocks) \(\w+\)$", r"### \1", text, flags=re.M))
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "no catalogue area heading")
        fx.write(method, text.replace("## Layout practice catalogue", "## Something else"))
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "no `## Layout practice catalogue` section")
        os.remove(method)
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "no readable method")

    def test_a_plan_whose_table_of_own_items_cannot_be_read_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        caller = review_fan_out.load_caller("layout", TOOLS)
        plan = os.path.join(self.folder, fx.DESIGN, "layout-plan.md")
        good = fx.plan(fx.OWN_ROWS)
        for name, text, word in (
                ("no table", good.split("### The board's own items")[0], "holds no table of the board's own items"),
                ("no divider", good.replace("|---|---|---|---|---|---|---|---|---|---|\n", ""), "has no divider row"),
                ("a short row", fx.plan("| BOARD-1 | always |"), "has 2 cells where the header has 10"),
                ("a foreign item", fx.plan(fx.OWN_ROWS.replace("BOARD-2", "FLOOR-9")), "not BOARD-<n> or `none`"),
                ("an item twice", fx.plan(fx.OWN_ROWS.replace("BOARD-2", "BOARD-1")), "an item is given twice")):
            fx.write(plan, text)
            self.refused(lambda: review_fan_out.unit_names(caller, self.folder), word)
        os.remove(plan)
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "no readable plan")

    def test_a_folder_that_holds_no_one_design_or_no_round_file_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        caller = review_fan_out.load_caller("layout", TOOLS)
        fx.write(os.path.join(self.folder, "second", "other.kicad_pro"), "{}")
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "holds 2 KiCad project files")
        shutil.rmtree(os.path.join(self.folder, "second"))
        os.remove(os.path.join(self.folder, review_folder.ROUND_FILE))
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "round file", "cannot be read")


class TheBoardsOwnItems(Folder):
    own = fx.OWN_ROWS

    def test_a_plan_with_own_items_adds_a_unit_for_them_before_the_plan_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.assertEqual(review_fan_out.unit_names(caller, self.folder),
                         ["area-FLOOR", "area-GROUND", "area-CLOCK", "board-items", "plan-and-free-pass"])
        self.assertEqual(review_caller_layout.checklist(self.folder)[-3:], ["BOARD-1", "BOARD-2", review_caller_layout.PLAN_ENTRY])

    def test_the_merge_gives_the_board_items_one_verdict_each_after_the_catalogues(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results(**{"board_items": {"Verdicts": [verdict("BOARD-1")]}})
        self.assertIn("item BOARD-2 has no verdict row", "; ".join(self.refused(lambda: merged(self.folder, given)).split(";")))
        given["board-items"]["Verdicts"].append(verdict("BOARD-2"))
        order = [row["Item"] for row in merged(self.folder, given)["tables"]["Verdicts"]["rows"]]
        self.assertEqual(order, ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", "BOARD-1", "BOARD-2"])


class TheNarrowRound(Folder):
    narrow = True

    def test_the_units_are_the_areas_the_listed_items_fall_in_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two areas, the caller has a unit for each of the two areas and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one area is judged in the setup session. Out of scope: how the designer chooses the listed items.
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.assertEqual(review_fan_out.unit_names(caller, self.folder), ["area-FLOOR", "area-CLOCK"])

    def test_each_units_prompt_names_only_its_listed_items(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two areas, the caller has a unit for each of the two areas and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one area is judged in the setup session. Out of scope: how the designer chooses the listed items.
        floor = review_caller_layout.unit_prompt("area-FLOOR", self.folder)
        clock = review_caller_layout.unit_prompt("area-CLOCK", self.folder)
        self.assertIn("FLOOR-1: the changed region holds its parts", floor)
        self.assertIn("This round is narrow", floor)
        for unlisted in ("FLOOR-2", "GROUND-1", "CLOCK-1"):
            self.assertNotIn(unlisted, floor)
        self.assertIn("CLOCK-1: the crystal moved", clock)
        for unlisted in ("FLOOR-1", "FLOOR-2", "GROUND-1"):
            self.assertNotIn(unlisted, clock)

    def test_the_merge_accepts_a_verdict_only_for_a_listed_item(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two areas, the caller has a unit for each of the two areas and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one area is judged in the setup session. Out of scope: how the designer chooses the listed items.
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1")]}, "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}}
        self.assertEqual([row["Item"] for row in merged(self.folder, given)["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "CLOCK-1"])
        given["area-FLOOR"]["Verdicts"].append(verdict("FLOOR-2"))
        self.refused(lambda: merged(self.folder, given), "a verdict row for FLOOR-2, which this round does not judge",
                     "an item the narrow round lists")
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1")]
        given["area-CLOCK"]["Verdicts"] = []
        self.refused(lambda: merged(self.folder, given), "item CLOCK-1 has no verdict row")

    def test_a_listed_item_that_is_no_item_of_the_checklist_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two areas, the caller has a unit for each of the two areas and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one area is judged in the setup session. Out of scope: how the designer chooses the listed items.
        fx.set_round(self.folder, items=[{"item": "FLOOR-1", "reason": "r"}, {"item": "NOPE-9", "reason": "r"}])
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.refused(lambda: review_fan_out.unit_names(caller, self.folder), "lists NOPE-9", "no item of the catalogue")

    def test_a_narrow_round_in_one_area_is_one_unit_judged_in_the_setup_session(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two areas, the caller has a unit for each of the two areas and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one area is judged in the setup session. Out of scope: how the designer chooses the listed items.
        fx.set_round(self.folder, items=[{"item": "FLOOR-1", "reason": "r"}, {"item": "FLOOR-2", "reason": "r2"}])
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.assertEqual(review_fan_out.unit_names(caller, self.folder), ["area-FLOOR"])
        run = Command(self)
        run.scenario_for(self.folder)
        status, text, _ = run.go("--json")
        report = json.loads(text)
        self.assertEqual(status, 0, text)
        self.assertEqual([unit["mode"] for unit in report["units"]], ["setup session"])
        self.assertEqual(run.forks(), [], "a one-unit round is not forked")
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "FLOOR-2"])

    def test_a_narrow_round_names_its_changed_regions_items_and_why_the_others_are_not_judged_in_the_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1")]}, "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}}
        text = review_caller_layout.RENDER(self.folder, merged(self.folder, given)["tables"])["round-1.md"]
        opening = text.split("### Verdicts")[0].splitlines()
        marks = [next(index for index, line in enumerate(opening) if line.startswith(f"- **{name}**"))
                 for name in ("Board judged", "Views", "Pre-order check", "Round kind", "Changed regions", "Items judged", "Items not judged")]
        self.assertEqual(marks, sorted(marks))
        self.assertIn("- **Round kind**: narrow", opening)
        self.assertIn("- **Changed regions**: region low voltage, net XTAL1", opening)
        self.assertIn("  - FLOOR-1: the changed region holds its parts", opening)
        self.assertIn("  - CLOCK-1: the crystal moved", opening)
        self.assertIn("- **Items not judged**: no other item touches a changed region or net", opening)
        rows = text.split("### Verdicts")[1].split("### Plan and free pass")[0]
        self.assertNotIn("FLOOR-2", rows)
        self.assertIn("no comparison with the plan or free pass beyond them was made", text)

    def test_a_cannot_judge_in_a_narrow_round_fails_the_merge_as_in_a_full_one(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1", "cannot judge", "needs crop-U9: the views show no crop of U9")]},
                 "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}}
        self.refused(lambda: merged(self.folder, given), "item FLOOR-1 is still cannot judge", "asks for crop-U9",
                     "unit area-FLOOR", "--rerun")


class TheMerge(Folder):
    def test_a_full_round_merges_one_verdict_for_every_item_in_the_checklist_order(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        out = merged(self.folder, dict(reversed(list(results().items()))), order=list(results()))
        self.assertEqual([row["Item"] for row in out["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"])

    def test_an_item_with_no_verdict_row_and_an_item_with_two_fail_the_merge_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1")]
        given["area-GROUND"]["Verdicts"] = [verdict("GROUND-1"), verdict("GROUND-1", "pass", "Judged again.")]
        text = self.refused(lambda: merged(self.folder, given), "item FLOOR-2 has no verdict row", "item GROUND-1 has 2 verdict rows")
        self.assertIn("judge it in unit area-FLOOR and run that unit again with --rerun", text)

    def test_a_verdict_for_an_item_of_no_checklist_and_a_second_units_row_for_an_item_fail_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-CLOCK"]["Verdicts"].append(verdict("MISC-7"))
        given["area-FLOOR"]["Verdicts"].append(verdict("CLOCK-1"))
        text = self.refused(lambda: merged(self.folder, given), "a verdict row for MISC-7", "item CLOCK-1 has 2 verdict rows")
        self.assertIn("an item of the checklist", text)

    def test_a_round_whose_fields_are_missing_or_malformed_fails_the_merge_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        for changes, word in (({"number": None}, "the round's number is None"), ({"number": 0}, "the round's number is 0"),
                              ({"number": "1"}, "the round's number is '1'"), ({"kind": None}, "the round's kind is None"),
                              ({"kind": "Full"}, "the round's kind is 'Full'"), ({"commit": None}, "the commit judged is None"),
                              ({"commit": "not a sha"}, "the commit judged is 'not a sha'"),
                              ({"views": None}, "the views are None"), ({"views": []}, "the views are []"),
                              ({"views": ["a\nb"]}, "the views are ['a\\nb']"),
                              ({"check": None}, "the pre-order check's lines are None"),
                              ({"check": ["VIOLATION | x | a | b | c"]}, "no DESIGN line"),
                              ({"check": ["RESULT | PASS"]}, "the pre-order check's lines are ['RESULT | PASS']")):
            with self.subTest(changes=changes):
                folder = os.path.join(self.root, "broken")
                shutil.rmtree(folder, ignore_errors=True)
                shutil.copytree(self.folder, folder)
                fx.set_round(folder, **changes)
                self.refused(lambda: merged(folder, results()), word, "missing or malformed")

    def test_a_narrow_round_missing_its_reasons_regions_or_why_others_line_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        fx.set_round(self.folder, kind="narrow", items=[{"item": "FLOOR-1", "reason": "r"}], regions=["a region"], others="why")
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1")]}}
        self.assertEqual(len(merged(self.folder, given)["tables"]["Verdicts"]["rows"]), 1)
        for changes, word in (({"items": [{"item": "FLOOR-1", "reason": ""}]}, "a narrow round's listed items are"),
                              ({"regions": None}, "a narrow round's changed regions are None"),
                              ({"others": None}, "line saying why every other item is not judged is None")):
            with self.subTest(changes=changes):
                folder = os.path.join(self.root, "broken")
                shutil.rmtree(folder, ignore_errors=True)
                shutil.copytree(self.folder, folder)
                fx.set_round(folder, **changes)
                self.refused(lambda: merged(folder, given), word)

    def test_findings_are_numbered_item_units_first_in_the_checklist_order_then_the_plan_unit_in_its_own(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.2."), verdict("FLOOR-2", "fail", "Finding 1.1.")],
                               "Findings": [finding(1, "FLOOR-2", "layer-F.Cu at (1, 1): second item's finding"),
                                            finding(2, "FLOOR-1", "layer-F.Cu at (2, 2): first item's finding")]}
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "layer-F.Cu at (3, 3): clock's finding")]
        given["plan-and-free-pass"]["Findings"] = [
            finding(1, review_caller_layout.PLAN_ENTRY, "layer-B.Cu at (4, 4): the free pass saw this first", "free pass"),
            finding(2, review_caller_layout.PLAN_ENTRY, "layer-B.Cu at (5, 5): then this", "plan, row FLOOR-1")]
        rows = merged(self.folder, given)["tables"]["Findings"]["rows"]
        self.assertEqual([(row["Finding"], row["Item"]) for row in rows],
                         [(1, "FLOOR-1"), (2, "FLOOR-2"), (3, "CLOCK-1"), (4, review_caller_layout.PLAN_ENTRY),
                          (5, review_caller_layout.PLAN_ENTRY)])
        self.assertEqual([row["What and where"].split(": ")[1] for row in rows[3:]], ["the free pass saw this first", "then this"])
        by_item = {row["Item"]: row["Why"] for row in merged(self.folder, given)["tables"]["Verdicts"]["rows"]}
        self.assertEqual((by_item["FLOOR-1"], by_item["FLOOR-2"]), ("Finding 1.1.", "Finding 1.2."), "the citations follow the renumbering")

    def test_two_findings_citing_one_view_and_place_are_reported_and_both_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "On crop-U4 at (74.675, 19.0) the capacitor is far from its pin")]
        given["plan-and-free-pass"]["Findings"] = [
            finding(1, review_caller_layout.PLAN_ENTRY, "crop-U4 shows a capacitor at (74.675, 19) stranded", "free pass"),
            finding(2, review_caller_layout.PLAN_ENTRY, "crop-U4 shows a capacitor at (60, 19) apart from its pin", "free pass")]
        out = merged(self.folder, given)
        self.assertEqual(len(out["tables"]["Findings"]["rows"]), 3, "neither finding is dropped")
        self.assertEqual(out["same_place"], [{"key": "crop-U4 (74.675, 19)", "findings": [1, 2], "units": ["area-CLOCK", "plan-and-free-pass"]}])

    def test_findings_that_name_no_view_or_no_place_are_not_taken_to_concern_one_place(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        for first, second in (("whole board, no view named", "whole board, no view named"),
                              ("crop-U4 at (1, 1)", "layer-F.Cu at (1, 1)"), ("crop-U4 at (1, 1)", "crop-U4 at (1, 2)"),
                              ("crop-U4 only", "crop-U4 only")):
            given = results()
            given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", first)]
            given["plan-and-free-pass"]["Findings"] = [finding(1, review_caller_layout.PLAN_ENTRY, second, "free pass")]
            self.assertEqual(merged(self.folder, given)["same_place"], [], (first, second))

    def test_a_rule_kind_verdict_is_not_judged_by_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-GROUND"]["Verdicts"] = [{**verdict("GROUND-1"), "Kind": "rule", "Rests on": "nothing the method names", "Why": "pass"}]
        rows = merged(self.folder, given)["tables"]["Verdicts"]["rows"]
        self.assertEqual([row["Rests on"] for row in rows if row["Item"] == "GROUND-1"], ["nothing the method names"])

    def test_a_cannot_judge_fails_the_round_naming_the_item_and_the_view_its_why_asks_for(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y1: the views show no crop of the crystal")]
        text = self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is still cannot judge", "asks for crop-Y1",
                            "render that view", "--add-view", "unit area-CLOCK", "--rerun")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "the views do not show it")]
        self.assertIn("'the views do not show it'", self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is still cannot judge"))

    def test_a_recorded_cannot_judge_for_an_item_outside_the_round_fails_the_merge_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        view = os.path.join(self.root, "crop-Y1.svg")
        fx.write(view, "<svg/>")
        status, text = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "kicad-cli pcb export svg crop",
                                      "--cannot-judge-item", "CLOCK-9", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(status, 0, text)
        text = self.refused(lambda: merged(self.folder, results()), "CLOCK-9", "not an item this round judges", "exact name")
        self.assertNotIn("still cannot judge", text)

    def test_a_resolved_cannot_judge_for_an_item_with_its_row_still_merges_and_renders(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        view = os.path.join(self.root, "crop-Y1.svg")
        fx.write(view, "<svg/>")
        status, text = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "kicad-cli pcb export svg crop",
                                      "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(status, 0, text)
        out = merged(self.folder, results())
        rendered = review_caller_layout.RENDER(self.folder, out["tables"])["round-1.md"]
        self.assertIn("| cannot judge; added-views/crop-Y1.svg; pass |", rendered)

    def test_a_resolved_cannot_judge_is_one_row_recording_the_cannot_judge_then_the_view_then_the_verdict(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        view = os.path.join(self.root, "crop-Y1.svg")
        fx.write(view, "<svg/>")
        status, text = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "kicad-cli pcb export svg crop",
                                      "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(status, 0, text)
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "Finding 1.1.", "crop-Y1 at (5, 5)")]
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1")]
        out = merged(self.folder, given)
        rendered = review_caller_layout.RENDER(self.folder, out["tables"])["round-1.md"]
        row = next(line for line in rendered.splitlines() if line.startswith("| CLOCK-1 "))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[3], "cannot judge; added-views/crop-Y1.svg; fail")
        self.assertEqual(cells[5], "Cannot judge: needs crop-Y1: no crop of the crystal. Finding 1.1.")
        self.assertEqual(cells[4], "crop-Y1 at (5, 5)", "the row rests on what the re-run's reviewer cites")
        again = results()
        again["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y2: still not enough")]
        self.refused(lambda: merged(self.folder, again), "item CLOCK-1 is still cannot judge", "asks for crop-Y2")

    def test_a_full_round_whose_plan_unit_wrote_no_note_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        self.refused(lambda: merged(self.folder, results(plan_notes=())), "unit plan-and-free-pass gave no note")
        given = results(plan_notes=("  ",))
        self.refused(lambda: merged(self.folder, given), "the Plan and free pass table's row 1 is empty")

    def test_a_vertical_bar_or_line_break_in_a_verdicts_or_findings_cell_is_written_sanitised_and_kept_raw_in_the_table_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1.", rests="layer-F.Cu | layer-B.Cu"), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1", what="classes at (10, 10):\r\nwrong\n\nplace|b")]}
        given["area-GROUND"]["Verdicts"][0]["Why"] = "two\nlines and a||b"
        out = merged(self.folder, given)
        raw = {row["Item"]: row for row in out["tables"]["Verdicts"]["rows"]}
        self.assertEqual(raw["FLOOR-1"]["Rests on"], "layer-F.Cu | layer-B.Cu", "the table-form record keeps the raw cell")
        self.assertEqual(raw["GROUND-1"]["Why"], "two\nlines and a||b")
        self.assertEqual(out["tables"]["Findings"]["rows"][0]["What and where"], "classes at (10, 10):\r\nwrong\n\nplace|b")
        text = review_caller_layout.RENDER(self.folder, out["tables"])["round-1.md"]
        self.assertNotIn("\r", text)
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        self.assertEqual(parsed.faults, [])
        floor = next(row for row in parsed.verdicts[1] if row[0] == "FLOOR-1")
        self.assertIn("layer-F.Cu / layer-B.Cu", floor)
        ground = next(row for row in parsed.verdicts[1] if row[0] == "GROUND-1")
        self.assertIn("two lines and a / b", ground)
        self.assertEqual({len(row) for row in parsed.verdicts[1]}, {len(parsed.verdicts[0])})
        self.assertEqual(parsed.findings[1][0][3], "classes at (10, 10): wrong place / b")
        self.assertEqual(len(parsed.findings[1][0]), len(parsed.findings[0]))
        self.assertEqual(parsed.numbers, ["1.1"])

    def test_a_citation_of_an_earlier_rounds_finding_is_left_and_one_the_record_lacks_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        root = tempfile.mkdtemp(prefix="layout-caller-test-")
        self.addCleanup(shutil.rmtree, root, True)
        folder = fx.write_review_folder(root, number=2)
        self.assertEqual(review_caller_layout.earlier_findings(folder), [("1", 1)])
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1 closed by a reason, which no longer applies; "
                                                                        "Finding 2.1 is raised."), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1")]}
        out = merged(folder, given)
        self.assertEqual(out["tables"]["Verdicts"]["rows"][0]["Why"],
                         "Finding 1.1 closed by a reason, which no longer applies; Finding 2.1 is raised.")
        given["area-FLOOR"]["Verdicts"][0]["Why"] = "Finding 1.7."
        self.refused(lambda: merged(folder, given), "cites 'Finding 1.7', a finding of round 1 that the review folder's earlier rounds do not hold")
        given["area-FLOOR"]["Verdicts"][0]["Why"] = "the clearance is 1.3 mm and 0.25 mm wide"
        merged(folder, given)


class TheRenderedRound(Folder):
    HAND_WRITTEN = f"""## Round 1

- **Board judged**: 1234567.
- **Views**: `task hw:views -- ...`.
- **Pre-order check**: the board's `DESIGN` line.

```
DESIGN | x | PASS
```

- **Round kind**: full

### Verdicts

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | fail | classes | Finding 1.1. |

### Plan and free pass

The plan was compared.

### Findings

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|
| 1.1 | FLOOR-1 | function | classes at (10, 10): wrong | no | FLOOR-1 | — | |
"""

    def shape(self, text):
        bodies = board_review_history.round_bodies(text)
        parsed = board_review_history.Round(bodies[1])
        headings = [line for _, line, _ in bodies[1] if line.startswith("###")]
        return {"faults": parsed.faults, "kinds": parsed.kinds, "verdict header": parsed.verdicts[0],
                "verdict cells": {len(row) for row in parsed.verdicts[1]}, "findings header": parsed.findings[0],
                "finding numbers": [bool(re.fullmatch(r"1\.\d+", number)) for number in parsed.numbers],
                "compared": {tuple(sorted(row)) for row in parsed.compared.values()}, "headings": headings,
                "opening starts": parsed.opening[0].split(":")[0]}

    def test_the_merged_round_is_read_by_the_history_commands_reader_as_a_hand_written_round_is(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1."), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1")]}
        text = review_caller_layout.RENDER(self.folder, merged(self.folder, given)["tables"])["round-1.md"]
        mine, theirs = self.shape(text), self.shape(self.HAND_WRITTEN)
        self.assertEqual(mine["faults"], [], mine["faults"])
        self.assertEqual(theirs["faults"], [])
        self.assertEqual(mine["kinds"], ["full"])
        for key in ("kinds", "verdict header", "findings header", "compared", "headings", "opening starts"):
            self.assertEqual(mine[key], theirs[key], key)
        self.assertEqual(mine["verdict cells"], theirs["verdict cells"])
        self.assertEqual(mine["finding numbers"], [True])
        lines = text.splitlines()
        order = [lines.index(mark) for mark in ("## Round 1", "### Verdicts", "### Plan and free pass", "### Findings")]
        self.assertEqual(order, sorted(order))
        self.assertLess(next(index for index, line in enumerate(lines) if line.startswith("- **Round kind**")), order[1])

    def test_a_round_that_raises_no_finding_has_the_line_saying_so_and_is_read_as_one(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        text = review_caller_layout.RENDER(self.folder, merged(self.folder, results())["tables"])["round-1.md"]
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        self.assertEqual(parsed.faults, [])
        self.assertEqual(parsed.findings, ([], []))
        self.assertTrue(text.rstrip().endswith("### Findings\n\nThis round raises no finding."))

    def test_a_record_holding_the_merged_round_below_an_earlier_one_is_read_round_by_round(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        root = tempfile.mkdtemp(prefix="layout-caller-test-")
        self.addCleanup(shutil.rmtree, root, True)
        folder = fx.write_review_folder(root, number=2)
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1", "fail", "Finding 1.1."), verdict("FLOOR-2")]
        given["area-FLOOR"]["Findings"] = [finding(1, "FLOOR-1")]
        text = review_caller_layout.RENDER(folder, merged(folder, given)["tables"])["round-2.md"]
        with open(os.path.join(folder, fx.DESIGN, "layout-review.md"), encoding="utf-8") as handle:
            record = handle.read() + "\n" + text
        numbers, malformed, unclosed = board_review_history.round_headings(record)
        self.assertEqual((numbers, malformed, unclosed), ([1, 2], [], None))
        bodies = board_review_history.round_bodies(record)
        self.assertEqual(board_review_history.Round(bodies[2]).faults, [])
        self.assertEqual(board_review_history.Round(bodies[2]).numbers, ["2.1"])
        self.assertEqual(board_review_history.Round(bodies[2]).kinds, ["full"])

    def test_the_rendered_record_is_one_plain_file_named_for_its_round(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        files = review_caller_layout.RENDER(self.folder, merged(self.folder, results())["tables"])
        self.assertEqual(list(files), ["round-1.md"])
        self.assertTrue(review_fan_out.rendered_name_ok("round-1.md"))
        self.assertEqual(review_caller_layout.RENDER.__name__, "RENDER")


# --- The command, against the stub ---------------------------------------------------------------


class Command:
    """The fan-out command run on a review folder with the layout caller, the stub playing the agent command line."""

    def __init__(self, case: Folder):
        self.case, self.root = case, case.root
        self.out = os.path.join(self.root, "out")
        self.log = os.path.join(self.root, "log")
        shutil.rmtree(self.log, ignore_errors=True)
        os.makedirs(self.log)
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        fx.write(self.program, f'#!/bin/sh\nexec "{sys.executable}" "{STUB}" "$@"\n')
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {review_fan_out.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path,
                                               "STUB_LOG": self.log})
        patcher.start()
        case.addCleanup(patcher.stop)

    def scenario_for(self, folder, **changes):
        """A scenario in which every unit returns a passing verdict for each of its items, and the plan unit a note."""
        units = review_caller_layout.unit_items(folder)
        tables = {unit: ({"Verdicts": [verdict(item) for item in items]} if items else
                         {"Verdicts": [], "Plan and free pass": [note("Compared the plan.")], "Findings": []})
                  for unit, items in units.items()}
        scenario = {"setup": {"reads": ["docs/board-design-method.md"]}, "tables": tables}
        scenario.update(changes)
        fx.write(self.scenario_path, json.dumps(scenario))
        return scenario

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        status = review_fan_out.main(["--caller", "layout", "--callers", TOOLS, "--review", self.case.folder, "--out", self.out,
                                      "--rate-limit-wait", "0"] + list(extra), out=out, err=err)
        return status, out.getvalue(), err.getvalue()

    def calls(self):
        found = []
        for name in sorted(os.listdir(self.log)):
            if name.endswith(".json"):
                with open(os.path.join(self.log, name), encoding="utf-8") as handle:
                    found.append(json.load(handle))
        return sorted(found, key=lambda call: call["began"])

    def forks(self):
        return [call for call in self.calls() if call["forked"]]


class TheSetupDocuments(Folder):
    def texts(self):
        return dict(review_fan_out.document_texts(self.folder, review_caller_layout.SETUP_DOCUMENTS(self.folder)))

    def test_the_setup_holds_the_review_sections_and_the_catalogue_introduction_then_the_records_in_order(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        design = "hardware/synth/board"
        fx.write(os.path.join(self.folder, design, "zeta.yaml"), "a: 1\n")
        fx.write(os.path.join(self.folder, design, "alpha.md"), "alpha\n")
        fx.write(os.path.join(self.folder, design, "notes.txt"), "not listed\n")
        listed = review_caller_layout.SETUP_DOCUMENTS(self.folder)
        self.assertEqual([entry if isinstance(entry, str) else entry[0].split(" (")[0] for entry in listed[:3]],
                         ["docs/board-design-method.md"] * 3)
        self.assertEqual(listed[3:], [
            "round.json", "check-report.txt", "views/index.txt", "views/facts.txt", "placement/index.txt",
            "placement/measures.txt", f"{design}/layout-plan.md", f"{design}/design-rules.md",
            f"{design}/alpha.md", f"{design}/constraints.md", f"{design}/separation-basis.yaml", f"{design}/zeta.yaml"])
        self.assertNotIn("hardware/README.md", listed)
        for entry in listed[3:]:
            self.assertFalse(entry.endswith((".kicad_pcb", ".kicad_sch", ".kicad_pro", ".png", ".svg")), entry)
        joined = "\n".join(self.texts().values())
        for wanted in ("Steps of a review.", "Views of a review.", "Intro of the catalogue.", "Every item carries fields."):
            self.assertIn(wanted, joined)

    def test_the_setup_holds_no_area_section_and_no_other_method_section(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        extracts = "\n".join(text for entry, text in self.texts().items() if entry.startswith("docs/board-design-method.md"))
        self.assertIn("Intro of the catalogue.", extracts)
        for absent in ("### Floorplan (FLOOR)", "FLOOR-1", "Parts are grouped", "GROUND-1", "CLOCK-1", "crystal sits",
                       "## Ordering", "NOT-1", "Synthetic hardware notes"):
            self.assertNotIn(absent, extracts)
        self.assertNotIn("Synthetic hardware notes", "\n".join(self.texts().values()))

    def test_the_setup_is_byte_identical_for_every_unit_of_every_round_kind(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        first = review_caller_layout.SETUP_DOCUMENTS(self.folder)
        run = Command(self)
        run.scenario_for(self.folder, setup={"reads": []})
        status, text, _ = run.go("--json")
        self.assertEqual(status, 0, text)
        setups = [call for call in run.calls() if call["unit"] is None and not call["forked"] and "-p" in call["args"]]
        self.assertEqual(len(setups), 1, "one setup session, which every fork starts from")
        self.assertEqual(review_caller_layout.SETUP_DOCUMENTS(self.folder), first)
        self.assertNotIn("### Floorplan (FLOOR)", setups[0]["stdin"])
        fx.set_round(self.folder, kind="narrow", items=[{"item": "CLOCK-1", "reason": "moved"}], regions=["r"], others="rest")
        self.assertEqual(review_caller_layout.SETUP_DOCUMENTS(self.folder), first, "a narrow round's setup is the same")

    def test_an_area_unit_prompt_holds_its_own_area_block_and_no_other_area(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        floor = review_caller_layout.unit_prompt("area-FLOOR", self.folder)
        ground = review_caller_layout.unit_prompt("area-GROUND", self.folder)
        clock = review_caller_layout.unit_prompt("area-CLOCK", self.folder)
        self.assertIn("### Floorplan (FLOOR)", floor)
        self.assertIn("#### FLOOR-2. Signals stay apart", floor)
        self.assertIn("other areas of the catalogue are not given", floor)
        for text, own, others in ((floor, "FLOOR", ("GROUND-1", "CLOCK-1", "Grounding", "Clocks")),
                                  (ground, "GROUND", ("FLOOR-1", "FLOOR-2", "CLOCK-1", "Floorplan", "Clocks")),
                                  (clock, "CLOCK", ("FLOOR-1", "GROUND-1", "Floorplan", "Grounding"))):
            self.assertIn(f"({own})", text)
            for other in others:
                self.assertNotIn(other, text.split("Your unit:")[1].split("Return exactly one JSON")[0], other)
        self.assertIn("the schematic has a crystal", clock)
        self.assertNotIn("Unrelated", clock, "the last area's block ends at the next method section")
        self.assertNotIn("Ordering", clock)

    def test_the_board_items_and_plan_units_carry_no_area_block(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        root = tempfile.mkdtemp(prefix="layout-caller-own-")
        self.addCleanup(shutil.rmtree, root, True)
        folder = fx.write_review_folder(root, own=fx.OWN_ROWS)
        for unit in ("board-items", "plan-and-free-pass"):
            text = review_caller_layout.unit_prompt(unit, folder)
            for absent in ("### Floorplan", "FLOOR-1", "GROUND-1", "CLOCK-1", "other areas of the catalogue"):
                self.assertNotIn(absent, text.replace("FLOOR-1, FLOOR-2", ""))

    def test_a_method_lacking_a_section_the_setup_needs_is_refused_naming_it_with_no_session_started(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = os.path.join(self.folder, "docs", "board-design-method.md")
        with open(method, encoding="utf-8") as handle:
            text = handle.read()
        cases = {"## Layout review views": text.replace("## Layout review views", "## Renamed views"),
                 "## Layout review": text.replace("## Layout review\n", "## Renamed review\n"),
                 "introduction": text.replace("Intro of the catalogue.\n\n### How an item is read\n\nEvery item carries fields.\n\n", "")}
        for name, changed in cases.items():
            with self.subTest(section=name):
                fx.write(method, changed)
                self.assertNotEqual(changed, text)
                shutil.rmtree(os.path.join(self.root, "out"), ignore_errors=True)
                run = Command(self)
                run.scenario_for(self.folder)
                status, output, _ = run.go("--json")
                self.assertEqual(status, 1, output)
                self.assertIn("REFUSED", output)
                self.assertIn(name if name != "introduction" else "introduction", output)
                self.assertEqual(run.calls(), [], "no session was started")

    def test_a_narrow_rounds_area_prompt_names_only_the_listed_items_and_holds_its_area_block(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        fx.set_round(self.folder, kind="narrow", items=[{"item": "FLOOR-2", "reason": "moved"}], regions=["r"], others="rest")
        text = review_caller_layout.unit_prompt("area-FLOOR", self.folder)
        self.assertIn("- FLOOR-2: moved", text)
        self.assertNotIn("FLOOR-1", text)
        self.assertIn("### Floorplan (FLOOR)", text)
        self.assertIn("#### FLOOR-2. Signals stay apart", text)

    def test_the_real_methods_shared_setup_is_far_smaller_than_the_whole_method(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        with open(os.path.join(REPO, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            method = handle.read()
        fx.write(os.path.join(self.folder, "docs", "board-design-method.md"), method)
        extracts = [entry for entry in review_caller_layout.SETUP_DOCUMENTS(self.folder) if not isinstance(entry, str)]
        self.assertEqual(len(extracts), 3)
        size = sum(len(text) for _, text in extracts)
        self.assertLess(size, 0.35 * len(method))
        self.assertNotIn("(FLOOR)", "".join(text for _, text in extracts))

    def test_the_setup_prompt_asks_for_no_judgement_and_no_image_and_the_layout_run_sends_the_documents_on_standard_input(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.assertIn("do not open any view image, the design's schematic or its layout", review_caller_layout.SETUP_PROMPT)
        self.assertIn("Judge nothing", review_caller_layout.SETUP_PROMPT)
        run = Command(self)
        run.scenario_for(self.folder, setup={"reads": []})
        status, text, _ = run.go("--json")
        self.assertEqual(status, 0, text)
        setup = [call for call in run.calls() if call["unit"] is None and not call["forked"] and "-p" in call["args"]][0]
        self.assertTrue(setup["args"][1].startswith("--"), "no prompt argument")
        for entry in review_caller_layout.SETUP_DOCUMENTS(self.folder):
            self.assertIn(f"=== {entry if isinstance(entry, str) else entry[0]} ===", setup["stdin"])
        self.assertNotIn(".kicad_", "".join(line for line in setup["stdin"].splitlines() if line.startswith("=== ")))
        self.assertNotIn(".png", "".join(line for line in setup["stdin"].splitlines() if line.startswith("=== ")))
        with open(os.path.join(self.folder, "hardware/synth/board/layout-plan.md"), encoding="utf-8") as handle:
            self.assertIn(handle.read().rstrip(), setup["stdin"])


class TheToolGrant(Folder):
    def test_the_caller_is_a_valid_caller_that_grants_the_read_tools_and_the_one_retrieval_tool(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the driver's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        caller = review_fan_out.load_caller("layout", TOOLS)
        self.assertEqual(tuple(caller.TOOLS), review_fan_out.READ_TOOLS + review_fan_out.RETRIEVAL_TOOLS)
        self.assertEqual(review_fan_out.caller_problems(caller, "layout"), [])

    def test_every_reviewer_is_started_with_the_four_tools_and_the_setup_session_with_the_read_tools_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the driver's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        run = Command(self)
        run.scenario_for(self.folder)
        status, text, _ = run.go("--json")
        self.assertEqual(status, 0, text)
        forks = run.forks()
        self.assertEqual(len(forks), 4)
        for call in forks:
            self.assertEqual(call["args"][call["args"].index("--tools") + 1], "Read,Glob,Grep,WebFetch")
            self.assertEqual(call["args"][call["args"].index("--allowedTools") + 1], "Read,Glob,Grep,WebFetch")
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.folder))
        setup = [call for call in run.calls() if not call["forked"] and call["unit"] is None and "-p" in call["args"]]
        self.assertEqual(len(setup), 1)
        self.assertEqual(setup[0]["args"][setup[0]["args"].index("--tools") + 1], "Read,Glob,Grep")

    def test_a_session_that_reports_a_different_tool_set_an_mcp_server_or_another_directory_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the driver's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        for unit, key, value, word in (("area-GROUND", "tools", ["Read", "Bash"], "started with tools ['Bash', 'Read']"),
                                       ("area-CLOCK", "tools", ["Read", "Glob", "Grep"], "started with tools ['Glob', 'Grep', 'Read']"),
                                       ("area-FLOOR", "mcp_servers", [{"name": "konnect"}], "started with MCP servers"),
                                       ("plan-and-free-pass", "cwd", "/somewhere/else", "started in '/somewhere/else'")):
            with self.subTest(unit=unit, key=key):
                shutil.rmtree(os.path.join(self.root, "out"), ignore_errors=True)
                run = Command(self)
                run.scenario_for(self.folder, units={unit: [{"start_set": {key: value}}]})
                status, text, _ = run.go("--json")
                report = json.loads(text)
                self.assertEqual(status, 1, text)
                failed = [entry for entry in report["units"] if entry["status"] == "failed"]
                self.assertEqual([entry["unit"] for entry in failed], [unit])
                self.assertIn(f"the reviewer of unit {unit} {word.split(' ')[0]} {word.split(' ', 1)[1]}", failed[0]["detail"])


class TheCommandEndToEnd(Folder):
    def test_the_command_writes_the_round_as_text_and_as_json(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        run = Command(self)
        run.scenario_for(self.folder)
        status, text, _ = run.go()
        self.assertEqual(status, 0, text)
        self.assertIn("RENDERED | round-1.md", text.splitlines())
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))
        with open(os.path.join(self.out_of(run), "round-1.md"), encoding="utf-8") as handle:
            rendered = handle.read()
        self.assertEqual(board_review_history.Round(board_review_history.round_bodies(rendered)[1]).faults, [])
        shutil.rmtree(run.out)
        status, as_json, _ = run.go("--json")
        report = json.loads(as_json)
        self.assertEqual((status, report["result"], report["rendered"]), (0, "WRITTEN", ["round-1.md"]))
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"])

    @staticmethod
    def out_of(run):
        return run.out

    def test_a_merge_that_fails_names_the_item_and_keeps_the_units_results(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        run = Command(self)
        scenario = run.scenario_for(self.folder)
        scenario["tables"]["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1")]
        fx.write(run.scenario_path, json.dumps(scenario))
        status, text, _ = run.go()
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | item FLOOR-2 has no verdict row", text)
        self.assertTrue(os.path.isfile(os.path.join(run.out, "units", "area-FLOOR.json")))
        self.assertFalse(os.path.exists(os.path.join(run.out, "round-1.md")))

    def test_a_cannot_judge_is_resolved_by_adding_the_view_and_running_that_unit_again(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the add-view mode recorded and the re-run's verdict, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        run = Command(self)
        scenario = run.scenario_for(self.folder)
        scenario["tables"]["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y1: no crop of the crystal")]
        fx.write(run.scenario_path, json.dumps(scenario))
        status, text, _ = run.go()
        self.assertEqual(status, 1)
        self.assertIn("item CLOCK-1 is still cannot judge", text)
        view = os.path.join(self.root, "crop-Y1.svg")
        fx.write(view, "<svg/>")
        added, said = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "render crop-Y1",
                                     "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(added, 0, said)
        scenario["tables"]["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "pass", "On the added crop the capacitor sits at its pin.")]
        fx.write(run.scenario_path, json.dumps(scenario))
        status, text, _ = run.go("--rerun", "area-CLOCK")
        self.assertEqual(status, 0, text)
        with open(os.path.join(run.out, "round-1.md"), encoding="utf-8") as handle:
            rendered = handle.read()
        self.assertIn("| CLOCK-1 | judgement | function | cannot judge; added-views/crop-Y1.svg; pass |", rendered)
        self.assertIn("render crop-Y1 (added view: added-views/crop-Y1.svg)", rendered)
        reruns = [call for call in run.calls() if call["unit"] == "area-CLOCK"]
        self.assertEqual(len(reruns), 2, "only that unit was judged again")
        self.assertEqual([call["unit"] for call in run.calls() if call["forked"]].count("area-FLOOR"), 1)


class ThePrompts(Folder):
    def test_a_units_prompt_names_the_unit_the_round_the_output_form_and_what_the_folder_holds(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        text = review_caller_layout.unit_prompt("area-GROUND", self.folder)
        for words in ("UNIT=area-GROUND", "round.json", "hardware/synth/board/", "GROUND-1", "This round is full", "fetch a published document", "`finding 1.<n>`", "PLAN-AND-FREE-PASS", "no cell holds a line break",
                      "write it from the row's text and the layout alone"):
            self.assertIn(words, text)
        for other in ("FLOOR-1", "CLOCK-1"):
            self.assertNotIn(other, text)
        plan = review_caller_layout.unit_prompt("plan-and-free-pass", self.folder)
        self.assertIn("You judge no item", plan)
        self.assertIn("Return an empty Verdicts table", plan)

    def test_a_prompt_for_a_unit_the_round_has_not_is_refused_and_a_later_round_names_its_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's units are one per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass; each unit's prompt holds the section of the catalogue for its own area and the setup session's documents hold no area section, the same for every unit; a folder whose method has no catalogue areas or lacks a section the setup needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        with self.assertRaises(review_caller_layout.ReviewFolderProblem):
            review_caller_layout.unit_prompt("area-NOPE", self.folder)
        root = tempfile.mkdtemp(prefix="layout-caller-test-")
        self.addCleanup(shutil.rmtree, root, True)
        later = fx.write_review_folder(root, number=2)
        text = review_caller_layout.unit_prompt("area-FLOOR", later)
        self.assertIn("This is round 2", text)
        self.assertIn("hardware/synth/board/layout-review.md", text)
        self.assertNotIn("This is round", review_caller_layout.unit_prompt("area-FLOOR", self.folder))

    def test_the_single_reviewers_prompt_asks_for_the_whole_round_as_the_method_lays_it_out(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        text = review_caller_layout.single_prompt(self.folder)
        for words in ("## Round 1", "### Verdicts", "### Plan and free pass", "### Findings", "every item of the checklist",
                      "Return nothing but the record", "round.json"):
            self.assertIn(words, text)
        self.assertNotIn("UNIT=", text)


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def layout_review(self):
        method = self.read("docs", "board-design-method.md")
        return self.flat(method[method.index("\n## Layout review\n"):].split("\n## Ordering")[0])

    def test_the_layout_review_step_says_a_round_may_be_judged_by_unit_and_what_the_merge_checks(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        section = self.layout_review()
        for words in ("A round may be judged by unit instead of by one reviewer", "changes none of them",
                      "one reviewer for each area of the catalogue, one for the board's own items and one for the comparison with the plan and the free pass",
                      "merges what they return, with no model, into one round of the one record",
                      "come from whoever starts the round", "since the merge has no model to write them",
                      "in which an item the round judges has no verdict row or has two", "in which a verdict row is for an item the round does not judge",
                      "or in which a `cannot judge` is left, and it names the item",
                      "numbers this round's findings in the checklist's order with the comparison and the free pass last",
                      "leaves a citation of an earlier round's finding as written",
                      "reports two findings that cite the same view and board place for the designer to resolve, dropping neither",
                      "The unit that raised a finding writes its Planning shortfall entry from the plan row",
                      "the designer names the item or step to amend, amends it and adds the commit",
                      "add it to the review folder with the folder command's add-view mode", "and run that unit again",
                      "the merged row records the `cannot judge`, the view and the verdict reached, in that order",
                      "appended below the record's earlier rounds, which stay as they are",
                      "whoever started the round commits it at the end of the round", "before any change to the board",
                      "Judging a round with one reviewer, a person or an agent session that does not use the command, stays valid"):
            self.assertIn(words, section, f"the layout review section says {words!r}")

    def test_the_sentence_that_a_proof_is_repeated_names_the_form_that_changed(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        section = self.layout_review()
        sentence = section[section.index("Repeat the proof after changing"):].split("`hardware/README.md` describes")[0]
        for words in ("in the form that changed", "repeats the single-reviewer proof above", "repeats the fanned-out proof",
                      "task hw:review-proof -- --work <folder>", "with the same four tools in both",
                      "to report every seed the single reviewer reports in no more time and at no more cost",
                      "A change to the catalogue or the views repeats both",
                      "The recorded proof of one form stands for that form alone"):
            self.assertIn(words, sentence)
        self.assertNotIn("Repeat the proof after changing the catalogue, the views or this step.", section)

    def test_the_hardware_notes_describe_the_layout_caller_and_the_folder_command_and_what_each_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The layout review by unit"):].split("\n## ")[0])
        for words in ("review_folder.py", "review_caller_layout.py", "layout_review_proof.py", "review_agent_tap.py",
                      "It needs git and Python, no KiCad and no model", "needs the agent command line on the search path and logged in",
                      "and no KiCad", "the commit that holds the board", "round.json", "`--round-fields number,kind,commit,views,check`",
                      "The set of fields is a parameter", "--item ITEM=reason", "--add-view", "added-views/", "`--rerun`",
                      "`area-<code>`", "`board-items`", "`plan-and-free-pass`", "`Read`, `Glob`, `Grep` and `WebFetch`",
                      "the setup session keeps the read tools alone", "exactly one verdict row",
                      "round-<n>.md", "committed by whoever started the round", "`BOUND`",
                      "`--keep-work-tree`", "money", "on demand and in neither the build round nor the nightly",
                      "the most reviewers that ran together", "calls refused for a rate limit"):
            self.assertIn(words, section, f"the hardware notes' section says {words!r}")
        listed = self.flat(notes[notes.index("- `task hw:test` runs"):].splitlines()[0])
        for words in ("review fan-out command", "layout review's caller", "review folder command", "layout review proof command"):
            self.assertIn(words, listed)
        commands = notes[notes.index("## The commands"):notes.index("## The schematic sheets")]
        for words in ("task hw:review-folder", "task hw:review-proof"):
            self.assertIn(words, commands)
        self.assertIn("the layout review's caller for it, the command that writes a committed board's review folder", notes.splitlines()[5])
        self.assertIn("--keep-work-tree <folder>", self.flat(notes[notes.index("## The proof designs"):]))

    def test_the_task_runner_names_the_new_commands_and_their_tests(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        taskfile = self.read("Taskfile.yml")
        folder = self.flat(taskfile[taskfile.index("  hw:review-folder:"):].splitlines()[1])
        proof = self.flat(taskfile[taskfile.index("  hw:review-proof:"):].splitlines()[1])
        for words in ("review_folder.py", "on demand", "neither the build round nor the nightly", "Needs git and Python 3.9 or newer, no KiCad and no model",
                      "--add-view", "the set of round fields being a parameter"):
            self.assertIn(words, folder)
        for words in ("layout_review_proof.py", "review_agent_tap.py", "on demand", "neither the build round nor the nightly", "spends the agent command line's usage",
                      "agent command line on the search path and logged in", "the most reviewers that ran together", "the layout caller's bound"):
            self.assertIn(words, proof)
        for text in (taskfile[taskfile.index("  hw:test:\n"):].splitlines()[1], taskfile[taskfile.index("  hw:test:round:"):].splitlines()[1]):
            for words in ("review fan-out command", "layout review", "review folder command", "layout review proof command"):
                self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
