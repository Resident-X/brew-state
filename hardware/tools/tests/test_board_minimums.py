#!/usr/bin/env python3
"""The pre-order check's manufacturer limits record and board-minimums rule, driven on synthetic designs with no KiCad involved.

What is under test is everything the rule decides for itself: how the manufacturer
limits record is found, read and refused, which process a layout falls in, and
which of the board's minimums (the board setup's, each net class's, each custom
rule's) are looser than the limit of that process. Each of these can be wrong
while the check still reports a pass, which is the failure worth a test. The
check run against KiCad, the tracked designs and the seeded-fault proof are in
the test_board_check_kicad_*.py files.
"""

from __future__ import annotations

import copy
import datetime
import os
import re
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
DESIGN = board_check.Design("hw/machine/board/board.kicad_pro")
RECORD = "hw/machine/manufacturer-limits.yaml"
TODAY = datetime.date(2026, 10, 12)

CITATION = {"section": "Tracks and spacing", "limit": "Minimum track width and spacing",
            "condition": "1- and 2-layer boards, 1 oz finished copper"}


def figure(mm, **edits) -> dict:
    return {"mm": mm, "citation": dict(CITATION, **edits)}


TWO_LAYERS = {"copper_layers": 2, "outer_copper_oz": 1,
              "limits": {"min_track_width": figure(0.1), "min_clearance": figure(0.1),
                         "min_through_hole_diameter": figure(0.2)}}
FOUR_LAYERS = {"copper_layers": 4, "outer_copper_oz": 1,
               "limits": {"min_track_width": figure(0.09), "min_clearance": figure(0.09)}}
COMPLETE = {"read_on": datetime.date(2026, 10, 1), "source": "none -- a synthetic reading", "max_age_days": 30,
            "processes": [TWO_LAYERS, FOUR_LAYERS], "synthetic": True}


def changed(**edits) -> dict:
    """The complete record with the top-level keys given replaced, a key set to Ellipsis removed."""
    record = copy.deepcopy(COMPLETE)
    for key, value in edits.items():
        if value is Ellipsis:
            del record[key]
        else:
            record[key] = value
    return record


def with_process(index: int = 0, **edits) -> dict:
    """The complete record with the keys of one process replaced, a key set to Ellipsis removed."""
    record = copy.deepcopy(COMPLETE)
    for key, value in edits.items():
        if value is Ellipsis:
            del record["processes"][index][key]
        else:
            record["processes"][index][key] = value
    return record


def with_limits(limits) -> dict:
    return with_process(limits=limits)


class Tree(unittest.TestCase):
    """A synthetic repository holding one design under hw/machine/board/ and the records it is held to."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        self.yaml = board_check.require_yaml()

    def write(self, path: str, text: str) -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def repository(self, tracked=True):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names] if tracked else []
        return board_check.Repository(self.root, files)

    def load(self, record, path: str = RECORD, manufacturable: bool = False, tracked: bool = True,
             today: datetime.date = TODAY):
        """The limits and violations the reader gives for `record`, a mapping or the text of the file, written at `path`."""
        if record is not None:
            self.write(path, record if isinstance(record, str) else self.yaml.safe_dump(record, sort_keys=False))
        return board_check.load_manufacturer_limits(self.yaml, self.root, self.repository(tracked), DESIGN, today,
                                                    not manufacturable)

    def problems(self, record, **more):
        return self.load(record, **more)[1]

    def assertFails(self, record, where: str, words: str, **more):
        problems = self.problems(record, **more)
        self.assertTrue([v for v in problems if v.location.endswith(where) and words in v.message],
                        [(v.location, v.message) for v in problems])
        self.assertEqual({v.rule for v in problems}, {"manufacturer_limits_record"})
        return problems


class TheManufacturerLimitsRecordIsRead(Tree):
    def test_a_complete_synthetic_record_is_accepted_for_a_design_not_for_manufacture_and_its_processes_returned(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A manufacturer limits record states the date read, its source, a max_age_days and per process the limits each with the citation of the published entry it was read from
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C3: This leaf extends the check's record reader to accept the manufacturer limits record
        limits, problems = self.load(COMPLETE)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(limits.processes), [(2, 1.0), (4, 1.0)])
        self.assertEqual(limits.processes[(2, 1.0)]["min_track_width"], (0.1, CITATION))
        self.assertEqual(set(limits.processes[(4, 1.0)]), {"min_track_width", "min_clearance"})
        self.assertEqual(limits.record, RECORD)

    def test_a_design_whose_folders_hold_no_record_fails_naming_where_one_belongs(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a design with no usable record
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        limits, problems = self.load(None)
        self.assertIsNone(limits)
        self.assertEqual([(v.design, v.rule, v.location) for v in problems],
                         [("hw/machine/board/board.kicad_pro", "manufacturer_limits_record",
                           "hw/machine/board/manufacturer-limits.yaml")])
        self.assertIn("no manufacturer-limits.yaml in the design's folder or any folder above it", problems[0].message)

    def test_the_record_in_the_nearest_folder_at_or_above_the_design_is_the_one_read(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A manufacturer limits record, found by the nearest-folder rule
        self.write(RECORD, self.yaml.safe_dump(COMPLETE, sort_keys=False))
        near = with_limits({"min_track_width": figure(0.5)})
        limits, problems = self.load(near, path="hw/machine/board/manufacturer-limits.yaml")
        self.assertEqual(problems, [])
        self.assertEqual(limits.processes[(2, 1.0)], {"min_track_width": (0.5, CITATION)})
        self.assertEqual(limits.record, "hw/machine/board/manufacturer-limits.yaml")
        self.write("hw/manufacturer-limits.yaml", "not: a record\n")
        self.assertEqual(self.load(None)[0].record, "hw/machine/board/manufacturer-limits.yaml")

    def test_a_record_the_repository_does_not_track_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a design with no usable record
        problems = self.problems(COMPLETE, tracked=False)
        self.assertEqual([v.rule for v in problems], ["manufacturer_limits_record"])
        self.assertIn("not tracked", problems[0].message)

    def test_a_synthetic_record_applied_to_an_orderable_board_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a synthetic record applied to an orderable board
        problems = self.assertFails(COMPLETE, "manufacturer-limits.yaml synthetic", "marked synthetic", manufacturable=True)
        self.assertIn("a proof record cannot let it pass", problems[0].message)
        self.assertEqual(self.problems(changed(synthetic=False), manufacturable=True), [])
        self.assertEqual(self.problems(changed(synthetic=...), manufacturable=True), [])
        self.assertFails(changed(synthetic="yes"), "manufacturer-limits.yaml synthetic", "where it is true on a manufacturer limits record")

    def test_a_record_read_longer_ago_than_its_max_age_days_fails_and_one_at_the_limit_passes(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a record older than its own max_age_days, as the catalogue extract is
        self.assertEqual(self.problems(COMPLETE, today=datetime.date(2026, 10, 31)), [], "30 days old, the limit")
        limits, problems = self.load(COMPLETE, today=datetime.date(2026, 11, 1))
        self.assertEqual(len(problems), 1, problems)
        self.assertEqual((problems[0].rule, problems[0].location), ("manufacturer_limits_record", f"{RECORD} read_on"))
        self.assertIn("read on 2026-10-01, 31 days before today (2026-11-01), past the 30 days it allows itself", problems[0].message)
        self.assertIsNotNone(limits, "a stale record is still read, so the minimums are judged beside the failure")

    def test_a_record_dated_later_than_today_fails_so_it_cannot_stay_fresh_for_ever(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a record older than its own max_age_days, as the catalogue extract is
        problems = self.problems(changed(read_on=datetime.date(2026, 10, 13)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("is dated 2026-10-13, later than today (2026-10-12)", problems[0].message)

    def test_a_record_missing_a_key_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A manufacturer limits record states the date read, its source, a max_age_days and per process the limits
        for key in ("read_on", "source", "max_age_days", "processes"):
            with self.subTest(missing=key):
                self.assertFails(changed(**{key: ...}), f"manufacturer-limits.yaml {key}", f"lacks {key}")

    def test_a_date_an_age_or_a_source_that_is_not_usable_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: states the date read, its source, a max_age_days
        for bad in ("01/10/2026", "2026-02-30", "soon", 20261001, None):
            with self.subTest(read_on=bad):
                self.assertFails(changed(read_on=bad), "read_on", "is not a valid calendar date written as YYYY-MM-DD")
        for bad in (0, -3, 1.5, "30", True, None):
            with self.subTest(max_age_days=bad):
                self.assertFails(changed(max_age_days=bad), "max_age_days", "where it is a whole number of days above zero")
        for bad in ("", "  ", 4, None):
            with self.subTest(source=bad):
                self.assertFails(changed(source=bad), "manufacturer-limits.yaml source", "non-empty string")

    def test_processes_must_be_a_non_empty_list_of_mappings_each_with_all_three_keys(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: per process the limits
        self.assertFails(changed(processes=[]), "processes", "lists no processes")
        self.assertFails(changed(processes="two layers"), "processes", "is not a list of processes")
        self.assertFails(changed(processes=["two layers"]), "processes[0]", "not a mapping of the keys")
        for key in ("copper_layers", "outer_copper_oz", "limits"):
            with self.subTest(missing=key):
                self.assertFails(with_process(**{key: ...}), f"processes[0].{key}", f"lacks {key}")

    def test_the_copper_layers_and_weight_of_a_process_must_be_usable_numbers(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A process is keyed by its copper layers and outer copper weight
        for layers in (0, -2, 2.5, "2", True, None):
            with self.subTest(copper_layers=layers):
                self.assertFails(with_process(copper_layers=layers), "processes[0].copper_layers", "where it is a whole number from 1 to 64")
        for weight in (0, -1, "1", "1 oz", True, None, float("nan")):
            with self.subTest(outer_copper_oz=weight):
                self.assertFails(with_process(outer_copper_oz=weight), "processes[0].outer_copper_oz", "not a positive number of ounces")

    def test_a_process_stated_twice_fails_but_the_same_layers_at_another_weight_does_not(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A process is keyed by its copper_layers and outer_copper_oz together
        twin = changed(processes=[TWO_LAYERS, dict(TWO_LAYERS, outer_copper_oz=1.0)])
        self.assertFails(twin, "processes", "lists the process '2 copper layers at 1 oz' more than once")
        heavier = changed(processes=[TWO_LAYERS, dict(TWO_LAYERS, outer_copper_oz=2)])
        limits, problems = self.load(heavier)
        self.assertEqual(problems, [])
        self.assertEqual(sorted(limits.processes), [(2, 1.0), (2, 2.0)])

    def test_the_limits_of_a_process_must_be_a_non_empty_mapping_of_named_minimums(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: per process the limits (minimum track width, clearance, drill ... and every other board-setup or rule key it bounds)
        self.assertFails(with_limits({}), "processes[0].limits", "lists no limit")
        self.assertFails(with_limits(["min_track_width"]), "processes[0].limits", "is not a mapping from the name of a board-setup minimum")
        for name in ("track_width", "MIN_TRACK_WIDTH", "min track width", "max_error", 3):
            with self.subTest(name=name):
                self.assertFails(with_limits({name: figure(0.1)}), f"processes[0].limits.{name}", "not the name of a board-setup minimum as KiCad names it")

    def test_each_limit_needs_a_positive_figure_in_millimetres_and_a_citation_naming_its_entry(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: each with the citation of the published entry it was read from
        for key in ("mm", "citation"):
            gone = {k: v for k, v in figure(0.1).items() if k != key}
            self.assertFails(with_limits({"min_track_width": gone}), f"limits.min_track_width.{key}", f"lacks {key}")
        for mm in (0, -0.1, "0.1", "0.1mm", True, None, float("inf")):
            with self.subTest(mm=mm):
                self.assertFails(with_limits({"min_track_width": figure(mm)}), "limits.min_track_width.mm", "not a positive number of millimetres")
        for part in ("section", "limit", "condition"):
            gone = dict(figure(0.1)["citation"])
            del gone[part]
            self.assertFails(with_limits({"min_track_width": {"mm": 0.1, "citation": gone}}),
                             f"limits.min_track_width.citation.{part}", f"lacks {part}")
            for blank in ("", "  ", 3, None):
                with self.subTest(part=part, blank=blank):
                    self.assertFails(with_limits({"min_track_width": figure(0.1, **{part: blank})}),
                                     f"limits.min_track_width.citation.{part}", "non-empty string")
        self.assertFails(with_limits({"min_track_width": {"mm": 0.1, "citation": "Tracks and spacing"}}),
                         "limits.min_track_width.citation", "not a mapping of the keys section, limit, condition")

    def test_a_key_the_decisions_do_not_define_fails_at_every_depth_naming_it(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C3: the reader still fails a key the decisions do not define
        cases = [
            (dict(COMPLETE, max_age=30), "manufacturer-limits.yaml max_age", "holds the key 'max_age'"),
            (with_process(outer_copper_ounces=1), "processes[0].outer_copper_ounces", "holds the key 'outer_copper_ounces'"),
            (with_limits({"min_track_width": {"mm": 0.1, "citation": CITATION, "source": "x"}}), "limits.min_track_width.source", "holds the key 'source'"),
            (with_limits({"min_track_width": figure(0.1, page="3")}), "min_track_width.citation.page", "holds the key 'page'"),
        ]
        for record, where, words in cases:
            with self.subTest(where=where):
                self.assertFails(record, where, words)

    def test_a_key_given_twice_or_a_merge_key_fails_because_the_shared_reader_refuses_both(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C3: The rules extend the existing pre-order check and its record reader
        self.assertIn("more than once", self.problems("read_on: 2026-10-01\nread_on: 2026-10-02\n")[0].message)
        self.assertIn("merge key", self.problems("base: &b {x: 1}\nsource: a\n<<: *b\n")[0].message)
        problems = self.problems("- not a mapping\n")
        self.assertEqual([v.rule for v in problems], ["manufacturer_limits_record"])
        self.assertIn("not a mapping", problems[0].message)

    def test_a_record_not_in_its_form_returns_no_limits_so_no_minimum_is_judged_against_it(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a design with no usable record
        self.assertIsNone(self.load(with_limits({"min_track_width": figure(-1)}))[0])


# --- The rule ---------------------------------------------------------------------------------------------

FOUR_COPPER = board_fixtures.LAYER_TABLE + ['(4 "In1.Cu" signal)', '(6 "In2.Cu" signal)']


def tree_of(layers=None) -> list:
    return sexpr.parse_one(board_fixtures.layout([], layers=layers))


def limits_of(**processes) -> board_check.Limits:
    """Limits for the processes given as name=(copper layers, weight, {limit: mm}), each limit cited as CITATION."""
    return board_check.Limits({(layers, float(weight)): {name: (mm, dict(CITATION)) for name, mm in held.items()}
                               for layers, weight, held in processes.values()}, RECORD)


STANDARD = {"two": (2, 1, {"min_track_width": 0.1, "min_clearance": 0.1, "min_through_hole_diameter": 0.2})}


def project_of(rules=None, classes=()) -> dict:
    return {"board": {"design_settings": {"rules": {"min_track_width": 0.1, "min_clearance": 0.1, "min_through_hole_diameter": 0.2}
                                          if rules is None else rules}},
            "net_settings": {"classes": list(classes)}}


def rules_of(text: str) -> list:
    return board_check.rule_forms("(version 1)\n" + text)


def minimums(project=None, rules=None, limits=None, tree=None, weight=1):
    return board_check.board_minimums(DESIGN, project if project is not None else project_of(), rules,
                                      tree if tree is not None else tree_of(), limits or limits_of(**STANDARD), weight)


class TheBoardIsHeldToTheLimitsOfItsProcess(unittest.TestCase):
    def test_a_board_at_or_above_every_limit_passes_and_a_figure_exactly_at_a_limit_is_not_looser(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose board-setup minimums ... is looser than its process's limit
        self.assertEqual(minimums(), [])
        self.assertEqual(minimums(project_of({"min_track_width": 0.1 + 1e-12, "min_clearance": 0.3, "min_through_hole_diameter": 0.2})), [])
        self.assertEqual(minimums(project_of({"min_track_width": 0.1 - 1e-12, "min_clearance": 0.1, "min_through_hole_diameter": 0.2})), [],
                         "float rounding below a limit is not looser")

    def test_a_board_setup_minimum_looser_than_its_limit_fails_naming_the_key_the_figure_and_the_limit_cited(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose board-setup minimums is looser than its process's limit
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C4: Every failure names the rule, the design, and the offending item (record key or figure)
        found = minimums(project_of({"min_track_width": 0.05, "min_clearance": 0.1, "min_through_hole_diameter": 0.2}))
        self.assertEqual(len(found), 1, found)
        self.assertEqual((found[0].design, found[0].rule),
                         ("hw/machine/board/board.kicad_pro", "board_minimums"))
        self.assertEqual(found[0].location, "hw/machine/board/board.kicad_pro board.design_settings.rules.min_track_width")
        for words in ("min_track_width is 0.05 mm", "looser than the manufacturer's", f"{RECORD} limits min_track_width, 0.1 mm for 2 copper layers at 1 oz",
                      "Tracks and spacing: Minimum track width and spacing, 1- and 2-layer boards, 1 oz finished copper"):
            self.assertIn(words, found[0].message)
        self.assertTrue(found[0].line().startswith("VIOLATION | hw/machine/board/board.kicad_pro | board_minimums | "))

    def test_every_limit_the_record_states_is_held_so_each_looser_minimum_is_found(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: every other board-setup or rule key it bounds
        found = minimums(project_of({"min_track_width": 0.01, "min_clearance": 0.01, "min_through_hole_diameter": 0.01}))
        self.assertEqual(sorted(v.location.rsplit(".", 1)[1] for v in found), ["min_clearance", "min_through_hole_diameter", "min_track_width"])

    def test_a_minimum_the_record_does_not_bound_is_not_judged_however_small_it_is(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: Out of scope: any minimum the record does not state
        rules = {"min_track_width": 0.1, "min_clearance": 0.1, "min_through_hole_diameter": 0.2, "min_hole_to_hole": 0.0,
                 "min_via_diameter": 0.0, "min_silk_clearance": 0, "max_error": 0.005, "min_connection": 0}
        self.assertEqual(minimums(project_of(rules)), [])

    def test_a_minimum_the_record_bounds_and_the_project_file_does_not_state_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board-setup minimum the record bounds that the project file does not state
        found = minimums(project_of({"min_track_width": 0.1, "min_clearance": 0.1}))
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].location, "hw/machine/board/board.kicad_pro board.design_settings.rules.min_through_hole_diameter")
        self.assertIn("states no min_through_hole_diameter", found[0].message)
        self.assertIn("KiCad would apply its own default, which no record reviews", found[0].message)
        self.assertEqual(len(minimums(project_of({}))), 3)
        self.assertEqual(len(minimums({"board": {}, "net_settings": {"classes": []}})), 3)
        self.assertEqual(len(minimums({})), 3)

    def test_a_board_setup_minimum_that_is_not_a_number_fails_since_it_cannot_be_held_to_the_limit(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose board-setup minimums is looser than its process's limit
        for bad in ("0.2", True, [0.2], {"mm": 0.2}, float("nan")):
            with self.subTest(value=bad):
                found = minimums(project_of({"min_track_width": bad, "min_clearance": 0.1, "min_through_hole_diameter": 0.2}))
                self.assertEqual(len(found), 1, found)
                self.assertIn("is not a number of millimetres", found[0].message)

    def test_each_net_classs_clearance_and_track_width_is_held_to_the_matching_limit(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose each net class's clearance and track width is looser than its process's limit
        classes = [{"name": "Default", "clearance": 0.2, "track_width": 0.25},
                   {"name": "Fine", "clearance": 0.08, "track_width": 0.2},
                   {"name": "Thin", "clearance": 0.3, "track_width": 0.05}]
        found = minimums(project_of(classes=classes))
        self.assertEqual(sorted(v.location for v in found), [
            "hw/machine/board/board.kicad_pro net_settings.classes 'Fine' clearance",
            "hw/machine/board/board.kicad_pro net_settings.classes 'Thin' track_width"])
        fine = next(v for v in found if "'Fine'" in v.location)
        self.assertIn("the net class Fine has a clearance of 0.08 mm, looser than the manufacturer's", fine.message)
        self.assertIn("limits min_clearance, 0.1 mm", fine.message)
        self.assertEqual(minimums(project_of(classes=[{"name": "At", "clearance": 0.1, "track_width": 0.1}])), [])

    def test_a_net_class_that_states_no_figure_or_one_no_limit_bounds_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: Out of scope: any minimum the record does not state
        classes = [{"name": "Quiet"}, {"name": "Via", "via_diameter": 0.01, "via_drill": 0.0, "diff_pair_gap": 0.0}, "not a class"]
        self.assertEqual(minimums(project_of(classes=classes)), [])
        only_tracks = limits_of(two=(2, 1, {"min_track_width": 0.1, "min_clearance": 0.1}))
        self.assertEqual(minimums(project_of({"min_track_width": 0.1, "min_clearance": 0.1}, classes=[{"name": "C", "clearance": 0.2}]),
                                  limits=only_tracks), [])
        unbounded = limits_of(two=(2, 1, {"min_track_width": 0.1}))
        self.assertEqual(minimums(project_of({"min_track_width": 0.1}, classes=[{"name": "C", "clearance": 0.0, "track_width": 0.2}]),
                                  limits=unbounded), [], "no min_clearance limit, so no clearance is judged")

    def test_a_net_class_figure_that_is_not_a_number_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: each net class's clearance and track width
        for bad in ("0.2", True, None):
            with self.subTest(value=bad):
                found = minimums(project_of(classes=[{"name": "Odd", "clearance": bad}]))
                self.assertEqual(len(found), 1, found)
                self.assertIn("the net class Odd gives its clearance as", found[0].message)

    CONSTRAINTS = {"clearance": "min_clearance", "track_width": "min_track_width", "hole_size": "min_through_hole_diameter",
                   "hole_to_hole": "min_hole_to_hole", "annular_width": "min_via_annular_width", "via_diameter": "min_via_diameter",
                   "hole_clearance": "min_hole_clearance", "edge_clearance": "min_copper_edge_clearance"}

    def everything_limits(self):
        return limits_of(two=(2, 1, {name: 0.2 for name in self.CONSTRAINTS.values()}))

    def everything_project(self):
        return project_of({name: 0.2 for name in self.CONSTRAINTS.values()})

    def test_a_custom_rules_minimum_is_held_to_the_limit_of_the_board_setup_key_its_constraint_maps_to(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose any minimum a custom rule sets is looser than its process's limit
        for constraint, key in self.CONSTRAINTS.items():
            with self.subTest(constraint=constraint):
                loose = rules_of(f'(rule "loose"\n\t(condition "A.hasNetclass(\'Fine\')")\n\t(constraint {constraint} (min 0.1mm)))\n')
                found = minimums(self.everything_project(), loose, self.everything_limits())
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0].location, f"{DESIGN.rules} rule 'loose' at line 2")
                self.assertIn(f"sets a {constraint} minimum of 0.1 mm, looser than the manufacturer's", found[0].message)
                self.assertIn(f"limits {key}, 0.2 mm", found[0].message)
                tight = rules_of(f'(rule "tight"\n\t(constraint {constraint} (min 0.2mm)))\n')
                self.assertEqual(minimums(self.everything_project(), tight, self.everything_limits()), [])

    def test_a_constraint_kind_the_map_does_not_hold_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: any other constraint, such as track_angle, creepage or courtyard_clearance, is not judged
        text = ('(rule "angles"\n\t(constraint track_angle (min 1)))\n'
                '(rule "creep"\n\t(constraint creepage (min 0.001mm)))\n'
                '(rule "yard"\n\t(constraint courtyard_clearance (min 0mm)))\n'
                '(rule "jog"\n\t(constraint track_segment_length (min 0.001mm)))\n'
                '(rule "thermal"\n\t(constraint zone_connection thermal_reliefs))\n'
                '(rule "keepout"\n\t(constraint disallow footprint))\n')
        self.assertEqual(minimums(self.everything_project(), rules_of(text), self.everything_limits()), [])

    def test_a_constraint_whose_limit_the_record_does_not_state_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: Out of scope: any minimum the record does not state
        loose = rules_of('(rule "loose"\n\t(constraint hole_to_hole (min 0mm)))\n')
        self.assertEqual(minimums(rules=loose), [])

    def test_a_rule_figure_is_converted_to_millimetres_from_the_unit_it_is_written_in(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: a rule's figure is converted to millimetres from its own unit
        # the limit is 0.2 mm: 8 mil is 0.2032 mm, 7 mil is 0.1778 mm
        cases = [("0.2mm", False), ("0.2", False), ("0.05", True), ("8mil", False), ("7mil", True), ("3mil", True),
                 ("0.008in", False), ("0.007in", True), ("0.1mm", True), ("0", True), ("100mil", False)]
        for written, looser in cases:
            with self.subTest(written=written):
                found = minimums(self.everything_project(), rules_of(f'(rule "r"\n\t(constraint track_width (min {written})))\n'),
                                 self.everything_limits())
                self.assertEqual(bool(found), looser, found)
        found = minimums(self.everything_project(), rules_of('(rule "r"\n\t(constraint track_width (min 3mil)))\n'), self.everything_limits())
        self.assertIn("sets a track_width minimum of 0.0762 mm", found[0].message)

    def test_a_minimum_written_in_a_form_that_cannot_be_read_as_a_length_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a minimum it cannot show to be no looser than the limit
        for written in ('"0.2mm"', "0.2cm", "wide", "(expr 1)", "-0.1mm", "1e-3mm", "0.2mm 0.01mm", ""):
            with self.subTest(written=written):
                found = minimums(self.everything_project(), rules_of(f'(rule "r"\n\t(constraint track_width (min {written})))\n'),
                                 self.everything_limits())
                self.assertEqual(len(found), 1, found)
                self.assertIn("cannot be shown to be no looser than the limit", found[0].message)

    def test_only_a_minimum_is_held_so_a_maximum_or_an_optimum_alone_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: looser means smaller
        text = '(rule "ceiling"\n\t(constraint hole_size (max 0.05mm) (opt 0.01mm)))\n'
        self.assertEqual(minimums(self.everything_project(), rules_of(text), self.everything_limits()), [])
        both = '(rule "both"\n\t(constraint hole_size (min 0.1mm) (max 6mm)))\n'
        self.assertEqual(len(minimums(self.everything_project(), rules_of(both), self.everything_limits())), 1)

    def test_every_loose_rule_is_reported_each_at_its_own_line_and_a_design_with_no_rules_file_is_not_failed(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C4: Every failure names the rule, the design, and the offending item
        text = ('(rule "first"\n\t(constraint clearance (min 0.1mm)))\n(rule "ok"\n\t(constraint clearance (min 0.3mm)))\n'
                '(rule "second"\n\t(constraint edge_clearance (min 0.1mm)))\n')
        found = minimums(self.everything_project(), rules_of(text), self.everything_limits())
        self.assertEqual([v.location for v in found], [f"{DESIGN.rules} rule 'first' at line 2",
                                                        f"{DESIGN.rules} rule 'second' at line 6"])
        self.assertEqual(minimums(rules=None), [])
        self.assertEqual(minimums(rules=[]), [])

    def test_a_process_the_record_does_not_list_fails_naming_the_layers_the_weight_and_what_it_lists(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose process the record does not list
        found = minimums(tree=tree_of(FOUR_COPPER))
        self.assertEqual(len(found), 1, found)
        self.assertEqual((found[0].rule, found[0].location), ("board_minimums", RECORD))
        self.assertIn("the board has 4 copper layers and its board rules record declares a finished outer copper weight of 1 oz", found[0].message)
        self.assertIn("it lists 2 copper layers at 1 oz", found[0].message)
        found = minimums(weight=2)
        self.assertEqual(len(found), 1, found)
        self.assertIn("finished outer copper weight of 2 oz, a process", found[0].message)

    def test_the_process_is_the_layers_stack_and_the_declared_weight_together(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The design's process is its copper layer count, derived from its own layer stack, and its finished outer copper weight, declared in the board rules record's fabrication mapping
        both = limits_of(two=(2, 1, {"min_track_width": 0.1}), four=(4, 1, {"min_track_width": 0.09}), heavy=(2, 2, {"min_track_width": 0.16}))
        project = project_of({"min_track_width": 0.1})
        self.assertEqual(minimums(project, limits=both, tree=tree_of(), weight=1), [])
        self.assertEqual(minimums(project, limits=both, tree=tree_of(FOUR_COPPER), weight=1), [], "four layers: 0.1 mm is no looser than 0.09 mm")
        found = minimums(project, limits=both, tree=tree_of(), weight=2)
        self.assertEqual(len(found), 1, found)
        self.assertIn("limits min_track_width, 0.16 mm for 2 copper layers at 2 oz", found[0].message)
        self.assertEqual(minimums(project, limits=both, tree=tree_of(), weight=1.0), [], "an integer weight and a float one are one weight")

    def test_a_layout_naming_no_copper_layers_is_read_as_the_two_outer_ones(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The design's process is its copper layer count, derived from its own layer stack
        self.assertEqual(minimums(tree=tree_of(['(25 "Edge.Cuts" user)'])), [])


# --- The record cannot drift from its source ----------------------------------------------------------

PROSE = """\
# Board manufacturer: a synthetic page

## Fabrication limits

### Tracks and spacing

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum track width and spacing | 0.10 mm / 0.10 mm (4 / 4 mil) | 1- and 2-layer boards, 1 oz finished copper | published | https://example.invalid/a | 2026-10-13 |
| Minimum track width and spacing | 0.09 mm / 0.09 mm (3.5 / 3.5 mil) | Multilayer boards, 1 oz | published | https://example.invalid/a | 2026-10-13 |

### Drills, vias and annular rings

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum via hole / via diameter | 0.15 mm / 0.25 mm | 2-layer and multilayer boards | published | https://example.invalid/b | 2026-10-13 |

## Assembly limits

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum track width and spacing | 9.99 mm | 1- and 2-layer boards, 1 oz finished copper | published | https://example.invalid/c | 2026-10-13 |
"""


def prose_entries(text: str) -> list:
    """Every table row of the dated prose manufacturer record as (section, limit, condition, value cell), the section being the
    nearest heading above its table; a table is one whose header row names Limit, Value and Condition columns."""
    entries, section, columns = [], "", None
    for line in text.splitlines():
        heading = re.match(r"#{2,4}\s+(.*\S)\s*$", line)
        if heading:
            section, columns = heading.group(1), None
            continue
        if not line.startswith("|"):
            columns = None if line.strip() == "" else columns
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if columns is None:
            columns = {name: cells.index(name) for name in ("Limit", "Value", "Condition") if name in cells}
            columns = columns if len(columns) == 3 else None
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        entries.append((section, cells[columns["Limit"]], cells[columns["Condition"]], cells[columns["Value"]]))
    return entries


def drift(record: dict, prose: str) -> list:
    """What differs between each limit of a manufacturer limits record and the entry of the prose record it cites.

    A limit is held to the table row under the section it names whose limit and condition cells equal the citation's, and its
    figure must be among the millimetre figures of that row's value cell. A citation that names no such row is a difference.
    """
    entries = prose_entries(prose)
    found = []
    for process in record["processes"]:
        for name, held in process["limits"].items():
            cite = held["citation"]
            row = [e for e in entries if e[0] == cite["section"] and e[1] == cite["limit"] and e[2] == cite["condition"]]
            if not row:
                found.append(f"{name}: no entry in section '{cite['section']}' has the limit '{cite['limit']}' under the condition "
                             f"'{cite['condition']}'")
                continue
            shown = [float(n) for n in re.findall(r"[0-9]+(?:\.[0-9]+)?", re.sub(r"\([^)]*\)", "", row[0][3]))]
            if "mm" not in row[0][3] or held["mm"] not in shown:
                found.append(f"{name}: the record states {held['mm']:g} mm and the entry's value is '{row[0][3]}'")
    return found


def mirrored(**edits) -> dict:
    record = {"read_on": "2026-10-13", "source": "docs/a-synthetic-page.md", "max_age_days": 30, "processes": [
        {"copper_layers": 2, "outer_copper_oz": 1, "limits": {
            "min_track_width": figure(0.1),
            "min_via_diameter": {"mm": 0.25, "citation": {"section": "Drills, vias and annular rings", "limit": "Minimum via hole / via diameter",
                                                           "condition": "2-layer and multilayer boards"}}}}]}
    record.update(edits)
    return record


class TheRecordCannotDriftFromTheDatedProseItCites(unittest.TestCase):
    def test_a_record_whose_every_figure_matches_the_entry_it_cites_has_no_difference(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A test holds each recorded figure of a record not marked synthetic to the matching entry of the dated prose manufacturer record it cites
        self.assertEqual(drift(mirrored(), PROSE), [])

    def test_a_figure_that_differs_from_its_entry_is_a_difference_naming_the_limit_and_both_figures(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: so the record cannot drift from its source
        record = mirrored()
        record["processes"][0]["limits"]["min_track_width"]["mm"] = 0.12
        found = drift(record, PROSE)
        self.assertEqual(len(found), 1, found)
        self.assertIn("min_track_width: the record states 0.12 mm and the entry's value is '0.10 mm / 0.10 mm (4 / 4 mil)'", found[0])

    def test_a_citation_that_names_no_entry_by_section_limit_and_condition_is_a_difference(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: each citation naming the entry's section, limit and condition
        for part, wrong in (("section", "Assembly limits"), ("limit", "Minimum spacing"), ("condition", "Multilayer boards, 2 oz")):
            with self.subTest(part=part):
                record = mirrored()
                record["processes"][0]["limits"]["min_track_width"]["citation"][part] = wrong
                found = drift(record, PROSE)
                self.assertEqual(len(found), 1, found)
                if part == "section":
                    self.assertIn("the entry's value is '9.99 mm'", found[0], "the other section's row has the limit and condition")
                else:
                    self.assertIn("no entry in section", found[0])

    def test_the_section_is_part_of_the_entry_so_the_same_limit_and_condition_in_another_section_is_another_entry(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: several entries share one source, so the citation names the section
        record = mirrored()
        record["processes"][0]["limits"]["min_track_width"]["citation"]["section"] = "Assembly limits"
        found = drift(record, PROSE)
        self.assertEqual(len(found), 1, found)
        self.assertIn("the record states 0.1 mm and the entry's value is '9.99 mm'", found[0])

    def test_the_prose_record_of_the_repository_is_read_into_entries_the_test_can_hold_a_record_to(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A test holds each recorded figure ... to the matching entry of the dated prose manufacturer record
        with open(os.path.join(REPO, "docs", "board-manufacturer-jlcpcb.md"), encoding="utf-8") as handle:
            entries = prose_entries(handle.read())
        sections = {entry[0] for entry in entries}
        self.assertIn("Tracks and spacing", sections)
        self.assertIn("Drills, vias and annular rings", sections)
        self.assertGreater(len(entries), 20)
        self.assertTrue(all(entry[1] and entry[2] and entry[3] for entry in entries))

    def test_every_tracked_record_not_marked_synthetic_is_held_to_the_prose_record_its_source_names(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: A test holds each recorded figure of a record not marked synthetic to the matching entry of the dated prose manufacturer record it cites, so the record cannot drift from its source
        yaml = board_check.require_yaml()
        tracked = board_check.tracked_files("git", REPO)
        records = [path for path in tracked if os.path.basename(path) == board_check.MANUFACTURER_LIMITS_NAME]
        self.assertTrue(records, "the repository tracks a manufacturer limits record")
        for path in records:
            with open(os.path.join(REPO, path), encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            if data.get("synthetic") is True:
                continue
            with self.subTest(record=path):
                named = re.findall(r"docs/[A-Za-z0-9_.-]+\.md", str(data.get("source")))
                self.assertTrue(named and os.path.isfile(os.path.join(REPO, named[0])),
                                f"the source of {path} names no dated prose record in docs/ to hold its figures to")
                with open(os.path.join(REPO, named[0]), encoding="utf-8") as handle:
                    self.assertEqual(drift(data, handle.read()), [])

    def test_a_synthetic_record_is_exempt_because_it_exists_only_to_prove_the_rule(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: a synthetic record, which exists only to prove the rule against a throwaway design, is exempt
        record = mirrored()
        record["processes"][0]["limits"]["min_track_width"]["mm"] = 0.12
        self.assertNotEqual(drift(record, PROSE), [])
        self.assertTrue(COMPLETE["synthetic"] is True)


class WhatTheRoundReads(Tree):
    def test_a_designs_reads_include_its_manufacturer_limits_record_wherever_it_sits(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C6: A change to a design's board files or to any record these rules read re-runs the board tier of the build round
        self.write("hw/machine/board/board.kicad_pro", "{}")
        self.write("hw/machine/board/board.kicad_pcb", "")
        self.write("hw/machine/board/board.kicad_sch", "")
        self.write(RECORD, "synthetic: true\n")
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn(RECORD, reads)


class TheHardwareNotesCarryAnEntryForEachRule(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            self.text = handle.read()
        table = self.text[self.text.index("| Rule | Meaning |"):]
        table = table[:table.index("\n\n")]
        self.rows = {line.split("|")[1].strip().strip("`"): line.split("|")[2] for line in table.splitlines()[2:]}

    def test_each_rule_has_a_row_naming_what_fails_it_what_exempts_a_design_and_the_name_it_is_reported_under(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C7: The hardware notes' table of the pre-order check's rules carries one entry for each of the board-minimums rule and the lifecycle rule, naming what fails it, what exempts a design, and the name its failure is reported under
        for name, words in (("board_minimums", ("not one the manufacturer limits record lists", "smaller than the limit of its process",
                                                 "not stated by the project file", "are exempt")),
                            ("parts_lifecycle", ("holds no `lifecycle` mapping", "`end of life`, `obsolete` or `not recommended for new designs`",
                                                 "`no source publishes one`", "are exempt")),
                            ("manufacturer_limits_record", ("missing", "synthetic on an orderable board", "`max_age_days`"))):
            with self.subTest(rule=name):
                self.assertIn(name, self.rows)
                for phrase in words:
                    self.assertIn(phrase, self.rows[name])
        self.assertIn("declares no `fabrication.outer_copper_oz`", self.rows["board_rules_record"])

    def test_the_notes_state_the_form_of_the_limits_record_and_of_the_fabrication_mapping_and_that_the_declared_weight_is_the_one_ordered(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C7: the notes state the form of the manufacturer limits record and of the board rules record's fabrication mapping, and that the copper weight declared there is the weight the order must select
        section = self.text[self.text.index("## The board-minimums and lifecycle rules"):]
        section = section[:section.index("\n## ")]
        for phrase in ("`read_on`", "`source`", "`max_age_days`", "`processes`", "`copper_layers`", "`outer_copper_oz`", "`limits`",
                       "`mm`", "`citation`", "`section`, `limit` and `condition`",
                       "**The fabrication mapping**", "`outer_copper_oz`, the finished outer copper weight in ounces",
                       "may not state `none`",
                       "**The copper weight declared there is the weight the order must select**"):
            self.assertIn(phrase, section)
        form = self.text[self.text.index("## The one form each file is read in"):]
        self.assertIn("Manufacturer limits record (`manufacturer-limits.yaml`)", form)
        self.assertIn("`fabrication` a mapping of exactly `outer_copper_oz`", form)

    def test_the_reads_listing_and_the_gate_description_name_the_manufacturer_limits_record(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C6: The board-reads listing's description names every record a design is held to, including the manufacturer limits record this leaf adds
        self.assertEqual(self.text.count("board rules and manufacturer limits records it is held to"), 2)


if __name__ == "__main__":
    unittest.main()
