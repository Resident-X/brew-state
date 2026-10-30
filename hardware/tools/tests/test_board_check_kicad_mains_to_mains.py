#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the spacing between conductors at different mains potentials.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI  # noqa: E402

#: Where the rules the check appends are named in KiCad's own report.
M2M, TERMINAL, AHEAD, REINFORCED = (f"rule '{name}" for name in (
    board_check.MAINS_TO_MAINS_RULE, board_check.TERMINAL_RULE, board_check.AHEAD_OF_FUSE_RULE, board_check.REINFORCED_RULE))


def seeded(name: str):
    """The edit of the seeded fault of that name, so a test seeds exactly what the proof does."""
    return next(fault[4] for fault in board_prove.FAULTS if fault[0].startswith(name))


class MainsToMainsRunDirectly(Copy):
    def spacing(self, lines, rule):
        """The violations KiCad reports under one of the check's appended rules, as (type, items, message)."""
        return [(v[2], v[3], v[4]) for v in self.violations(lines) if rule in v[4]]

    def looser_design_rule(self):
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru")
                        + "(rule \"looser\"\n\t(condition \"A.hasNetclass('Mains') && B.hasNetclass('Mains')\")\n"
                          "\t(constraint clearance (min 0.1mm))\n\t(constraint creepage (min 0.1mm)))\n")

    def test_two_mains_items_closer_than_the_signed_clearance_fail_naming_both_nets_whatever_the_designs_rules_say(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        for looser in (False, True):
            with self.subTest(looser=looser):
                self.setUp()
                seeded("a Mains track nearer a Mains track of another net than the signed clearance")(self.seed)
                if looser:
                    self.looser_design_rule()
                status, lines = self.check()
                self.assertEqual(status, 1)
                found = [f for f in self.spacing(lines, M2M) if f[0] == "clearance"]
                self.assertEqual(len(found), 1, lines)
                for net in ("/MAINS_L", "/MAINS_N"):
                    self.assertIn(net, found[0][1])
                self.assertIn("actual 0.5500 mm", found[0][2])

    def test_two_mains_items_closer_than_the_signed_creepage_fail_naming_both_nets_whatever_the_designs_rules_say(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        for looser in (False, True):
            with self.subTest(looser=looser):
                self.setUp()
                seeded("a Mains track nearer a Mains track of another net than the signed creepage")(self.seed)
                if looser:
                    self.looser_design_rule()
                status, lines = self.check()
                self.assertEqual(status, 1)
                found = self.spacing(lines, M2M)
                self.assertEqual([f[0] for f in found], ["creepage"], lines)
                for net in ("/MAINS_L", "/MAINS_N"):
                    self.assertIn(net, found[0][1])
                self.assertIn("actual 0.4500 mm", found[0][2])

    def test_items_of_one_net_and_pairs_at_or_beyond_the_figures_are_never_reported(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        # a /MAINS_N track 0.1 mm from the /MAINS_N track that runs along the board, and /MAINS_N 0.65 mm from /MAINS_L, beyond the 0.6 mm figures
        board_prove.without_entry(self.seed)
        board_prove.mains_beside_mains(0.65)(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment(
            "/MAINS_N", 14, 12.54 + 0.25 + 0.1 + 0.125, 18, 12.54 + 0.25 + 0.1 + 0.125, "0b0e5c1a-0000-4000-8000-000000000d02")))
        status, lines = self.check()
        self.assertEqual([v for v in self.violations(lines) if v[2] in ("clearance", "creepage")], [], lines)
        self.assertEqual([line for line in lines if board_check.RESERVED in line and line.startswith("VIOLATION")], [])

    def test_a_pair_with_a_mains_entry_item_between_the_downstream_and_the_ahead_of_the_fuse_creepage_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment(
            "/MAINS_N", board_prove.NEAR_MAINS_X[0], 10.25 + 0.7 + 0.125, board_prove.NEAR_MAINS_X[1], 10.25 + 0.7 + 0.125,
            board_prove.NEAR_MAINS_UUID)))
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = self.spacing(lines, AHEAD)
        self.assertEqual([f[0] for f in found], ["creepage"], lines)
        for net in ("/MAINS_L", "/MAINS_N"):
            self.assertIn(net, found[0][1])
        self.assertIn("creepage 0.8000 mm; actual 0.7000 mm", found[0][2])
        # beyond the signed downstream creepage and clearance, so the downstream figure does not fail it
        self.assertEqual(self.spacing(lines, M2M), [])

    def test_the_same_distance_between_two_nets_outside_mains_entry_passes(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        board_prove.without_entry(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment(
            "/MAINS_N", board_prove.NEAR_MAINS_X[0], 10.25 + 0.7 + 0.125, board_prove.NEAR_MAINS_X[1], 10.25 + 0.7 + 0.125,
            board_prove.NEAR_MAINS_UUID)))
        status, lines = self.check()
        self.assertEqual([line for line in lines if board_check.RESERVED in line and line.startswith("VIOLATION")], [], lines)
        self.assertEqual([v for v in self.violations(lines) if v[2] in ("clearance", "creepage")], [], lines)

    def test_pads_of_one_part_and_of_neighbouring_parts_closer_than_the_terminal_clearance_fail_and_conductors_between_it_and_the_clearance_pass(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        thru = ["*.Cu", "*.Mask"]
        # R1 pad 2 is a 1.6 mm round pad on /MAINS_N at (25.16, 10): X1's pad on /MAINS_L stands 0.9 mm from its edge
        neighbour = board_prove.small_part("X1", 25.16 + 0.8 + 0.9 + 0.8, 10, "0b0e5c1a-0000-4000-8000-000000000e00",
                                           ("1", "thru_hole", thru, "/MAINS_L", 0, 0, 1.6))
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, neighbour))
        board_prove.mains_beside_mains(0.9)(self.seed)
        # a terminal clearance of 1.0 mm, above the 0.84 mm between the pads of J1, the 0.9 mm between R1 and X1 and the 0.9 mm
        # between the tracks, which sit between the 0.6 mm clearance and it
        board_prove.records(("  terminal_clearance_mm: 0.8\n", "  terminal_clearance_mm: 1.0\n"),
                            ("figure:\n      clearance_mm: 0.8", "figure:\n      clearance_mm: 1.0"))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = self.spacing(lines, TERMINAL)
        pairs = sorted(tuple(sorted(re.findall(r"pad \d+ \[[^\]]+\] of \w+", f[1]))) for f in found)
        self.assertIn(("pad 1 [/MAINS_L] of J1", "pad 2 [/MAINS_N] of J1"), pairs)
        self.assertIn(("pad 1 [/MAINS_L] of X1", "pad 2 [/MAINS_N] of R1"), pairs)
        self.assertTrue(all(f[0] == "clearance" for f in found))
        # the tracks, 0.9 mm apart, are conductors, held to the 0.6 mm clearance and passing it
        self.assertFalse([f for f in found if "Track" in f[1]], found)
        self.assertEqual([f for f in self.spacing(lines, M2M) if "Track" in f[1]], [], lines)

    def test_the_terminal_pairs_of_the_clean_design_pass_at_the_signed_terminal_clearance(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual([line for line in lines if board_check.RESERVED in line and line.startswith("VIOLATION")], [])

    def test_a_pair_listed_in_held_at_reinforced_fails_at_the_mains_to_low_voltage_figures_in_either_order(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C8: On a seeded layout with two Mains-class nets listed in held_at_reinforced, a clearance between them below the signed mains_to_low_voltage clearance, and a surface path below its creepage, each fail with the layout rule check's violation naming both nets, though both distances exceed the mains_to_mains figures. A pair naming a net outside the Mains class fails mains_declaration. A pair is held to the larger of each mains_to_low_voltage figure and the matching mains_to_mains figure, so a record whose mains_to_low_voltage is below its mains_to_mains never holds a listed pair looser than an unlisted one. Pairs not listed are out of scope and keep the mains-to-mains figures.
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "separation-basis.yaml"), encoding="utf-8") as handle:
            record = yaml.safe_load(handle)
        held, lv = record["mains_to_mains"], record["mains_to_low_voltage"]
        for first, second in (("/MAINS_L", "/MAINS_N"), ("/MAINS_N", "/MAINS_L")):
            with self.subTest(pair=(first, second)):
                self.setUp()
                board_prove.records(("  held_at_reinforced: []", f'  held_at_reinforced:\n    - ["{first}", "{second}"]'))(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                found = self.spacing(lines, REINFORCED)
                self.assertEqual({f[0] for f in found}, {"clearance", "creepage"}, lines)
                # every reported distance stands beyond the mains-to-mains figure of its kind and inside the mains-to-low-voltage one
                for kind, signed, beyond in (("clearance", lv["clearance_mm"], max(held["clearance_mm"], held["terminal_clearance_mm"])),
                                             ("creepage", lv["creepage_mm"], max(held["creepage_mm"], held["creepage_ahead_of_fuse_mm"]))):
                    reported = [f for f in found if f[0] == kind]
                    self.assertTrue(reported, lines)
                    for f in reported:
                        for net in ("/MAINS_L", "/MAINS_N"):
                            self.assertIn(net, f[1])
                        self.assertIn(f"{kind} {signed:.4f} mm", f[2])
                        actual = float(re.search(r"actual ([0-9.]+) mm", f[2]).group(1))
                        self.assertTrue(beyond < actual < signed, f)
                self.assertEqual(self.spacing(lines, M2M) + self.spacing(lines, TERMINAL) + self.spacing(lines, AHEAD), [])

    def test_a_pair_not_listed_keeps_the_mains_to_mains_figures(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C8: On a seeded layout with two Mains-class nets listed in held_at_reinforced, a clearance between them below the signed mains_to_low_voltage clearance, and a surface path below its creepage, each fail with the layout rule check's violation naming both nets, though both distances exceed the mains_to_mains figures. A pair naming a net outside the Mains class fails mains_declaration. A pair is held to the larger of each mains_to_low_voltage figure and the matching mains_to_mains figure, so a record whose mains_to_low_voltage is below its mains_to_mains never holds a listed pair looser than an unlisted one. Pairs not listed are out of scope and keep the mains-to-mains figures.
        # /MAINS_X is a third Mains-class net, far from the rest; only /MAINS_L and /MAINS_X are held at reinforced, so /MAINS_L and
        # /MAINS_N, 0.84 mm apart, stay held to the mains-to-mains figures and pass them
        board_prove.records(("  held_at_reinforced: []", '  held_at_reinforced:\n    - ["/MAINS_L", "/MAINS_X"]'))(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment(
            "/MAINS_X", 30, 20, 34, 20, "0b0e5c1a-0000-4000-8000-000000000d03")))
        status, lines = self.check()
        self.assertEqual(self.spacing(lines, REINFORCED), [], lines)
        self.assertEqual(self.spacing(lines, M2M) + self.spacing(lines, TERMINAL) + self.spacing(lines, AHEAD), [], lines)

    def test_a_pair_naming_a_net_outside_the_mains_class_fails_mains_declaration_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C8: On a seeded layout with two Mains-class nets listed in held_at_reinforced, a clearance between them below the signed mains_to_low_voltage clearance, and a surface path below its creepage, each fail with the layout rule check's violation naming both nets, though both distances exceed the mains_to_mains figures. A pair naming a net outside the Mains class fails mains_declaration. A pair is held to the larger of each mains_to_low_voltage figure and the matching mains_to_mains figure, so a record whose mains_to_low_voltage is below its mains_to_mains never holds a listed pair looser than an unlisted one. Pairs not listed are out of scope and keep the mains-to-mains figures.
        board_prove.records(("  held_at_reinforced: []", '  held_at_reinforced:\n    - ["/MAINS_L", "/LV_A"]'))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = [v for v in self.violations(lines) if v[2] == "mains_declaration"]
        self.assertEqual(len(found), 1, lines)
        self.assertIn("held_at_reinforced[0]", found[0][3])
        self.assertIn("/LV_A", found[0][4])


class TheMainsEntryDeclaration(Copy):
    def declaration(self, edit):
        self.seed.project(edit)
        status, lines = self.check()
        self.assertEqual(status, 1)
        return [v for v in self.violations(lines) if v[2] == "mains_declaration"]

    def test_a_mains_entry_variable_that_is_unset_or_neither_present_nor_none_fails_naming_the_variable(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY. A fixture, a design that declares NOT_FOR_MANUFACTURE true and is held by a record marked synthetic, is likewise out of scope and passes with MAINS_ENTRY unset when its record carries no mains_to_mains mapping, and a value it sets is read as above; a fixture whose record carries the mapping, an orderable design, and a design marked not for manufacture but held by a record not marked synthetic, each need it.
        for value, said in ((None, "is not set"), ("maybe", "is 'maybe'"), ("", "is ''"), ("Present", "is 'Present'")):
            with self.subTest(value=value):
                self.setUp()
                found = self.declaration(lambda data: data["text_variables"].pop("MAINS_ENTRY") if value is None
                                         else data["text_variables"].__setitem__("MAINS_ENTRY", value))
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0][3].endswith("text_variables.MAINS_ENTRY"), found)
                self.assertIn(f"MAINS_ENTRY {said}", found[0][4])

    def test_present_with_no_net_in_the_mains_entry_class_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY. A fixture, a design that declares NOT_FOR_MANUFACTURE true and is held by a record marked synthetic, is likewise out of scope and passes with MAINS_ENTRY unset when its record carries no mains_to_mains mapping, and a value it sets is read as above; a fixture whose record carries the mapping, an orderable design, and a design marked not for manufacture but held by a record not marked synthetic, each need it.
        def edit(data):
            data["net_settings"]["netclass_patterns"] = [p for p in data["net_settings"]["netclass_patterns"]
                                                         if p["netclass"] != "Mains_Entry"]
        found = self.declaration(edit)
        self.assertEqual(len(found), 1, found)
        self.assertIn("MAINS_ENTRY is present but no net on the layout is in the Mains_Entry net class", found[0][4])

    def test_a_mains_entry_net_outside_the_mains_class_fails_naming_the_net(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY. A fixture, a design that declares NOT_FOR_MANUFACTURE true and is held by a record marked synthetic, is likewise out of scope and passes with MAINS_ENTRY unset when its record carries no mains_to_mains mapping, and a value it sets is read as above; a fixture whose record carries the mapping, an orderable design, and a design marked not for manufacture but held by a record not marked synthetic, each need it.
        found = self.declaration(lambda data: data["net_settings"]["netclass_patterns"].append(
            {"netclass": "Mains_Entry", "pattern": "/LV_A"}))
        self.assertEqual(len(found), 1, found)
        self.assertIn("net /LV_A", found[0][3])
        self.assertIn("net /LV_A is in the Mains_Entry net class but not in the Mains class", found[0][4])

    def test_none_with_a_net_in_the_mains_entry_class_fails_naming_the_variable_and_the_net(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY. A fixture, a design that declares NOT_FOR_MANUFACTURE true and is held by a record marked synthetic, is likewise out of scope and passes with MAINS_ENTRY unset when its record carries no mains_to_mains mapping, and a value it sets is read as above; a fixture whose record carries the mapping, an orderable design, and a design marked not for manufacture but held by a record not marked synthetic, each need it.
        found = self.declaration(lambda data: data["text_variables"].__setitem__("MAINS_ENTRY", "none"))
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0][3].endswith("text_variables.MAINS_ENTRY"), found)
        self.assertIn("MAINS_ENTRY is none but the layout puts /MAINS_L in the Mains_Entry net class", found[0][4])

    def test_a_valid_declaration_with_a_net_in_the_class_passes(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY. A fixture, a design that declares NOT_FOR_MANUFACTURE true and is held by a record marked synthetic, is likewise out of scope and passes with MAINS_ENTRY unset when its record carries no mains_to_mains mapping, and a value it sets is read as above; a fixture whose record carries the mapping, an orderable design, and a design marked not for manufacture but held by a record not marked synthetic, each need it.
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual([v for v in self.violations(lines) if v[2] == "mains_declaration"], [])


class EveryTrackedDesignPassesTheMainsToMainsRules(unittest.TestCase):
    """Every design the repository tracks passes the check with the rules extended, the mains-present ones with synthetic figures."""

    PRESENT = {"gate-proof": "present", "record-keys-proof": "present"}
    #: Fixtures that declare mains present: not for manufacture, held by a synthetic record, carrying neither the mapping nor MAINS_ENTRY.
    FIXTURES = ("circuit-review-proof", "review-proof")
    DESIGNS = tuple(sorted(set(PRESENT) | set(FIXTURES))) + ("method-proof",)

    def test_every_tracked_design_passes_and_the_mains_present_ones_state_the_new_keys(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones passing as fixtures without the mains_to_mains mapping and MAINS_ENTRY, bar those kept to exercise the rules, which carry synthetic figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        tracked = set(subprocess.run(["git", "ls-files", "*.kicad_pro"], cwd=board_prove.REPO, capture_output=True,
                                     text=True, check=True).stdout.split())
        self.assertEqual(tracked, {f"hardware/proof/{name}/{name}.kicad_pro" for name in self.DESIGNS})
        for name in self.DESIGNS:
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, f"hardware/proof/{name}", name)
                with open(seed.path(".kicad_pro"), encoding="utf-8") as handle:
                    variables = json.load(handle)["text_variables"]
                with open(seed.path("separation-basis.yaml"), encoding="utf-8") as handle:
                    record = yaml.safe_load(handle)
                if name in self.PRESENT:
                    self.assertEqual(variables["MAINS"], "present")
                    self.assertEqual(variables["MAINS_ENTRY"], self.PRESENT[name])
                    self.assertTrue(record["synthetic"])
                    self.assertEqual(sorted(record["mains_to_mains"]), sorted(
                        ["clearance_mm", "terminal_clearance_mm", "creepage_mm", "creepage_ahead_of_fuse_mm", "entry_fuse",
                         "held_at_reinforced"] + (["downstream_basis"] if "downstream_basis" in record["mains_to_mains"] else [])))
                elif name in self.FIXTURES:
                    # a fixture, not for manufacture and held by a synthetic record, is out of scope of the mapping and of MAINS_ENTRY
                    self.assertEqual(variables["MAINS"], "present")
                    self.assertEqual(variables["NOT_FOR_MANUFACTURE"], "true")
                    self.assertTrue(record["synthetic"])
                    self.assertNotIn("mains_to_mains", record)
                    self.assertNotIn("MAINS_ENTRY", variables)
                else:
                    # a design that declares MAINS none is exempt from the mapping and from MAINS_ENTRY
                    self.assertEqual(variables["MAINS"], "none")
                    self.assertNotIn("mains_to_mains", record)
                    self.assertNotIn("MAINS_ENTRY", variables)
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertEqual(status, 0, lines)
                self.assertEqual([line for line in lines if line.startswith("VIOLATION")], [])


if __name__ == "__main__":
    unittest.main()
