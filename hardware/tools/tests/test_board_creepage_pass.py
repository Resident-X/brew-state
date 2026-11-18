#!/usr/bin/env python3
"""The creepage pass of the pre-order check and the guard that lets it leave ground pours out, driven with no KiCad involved.

The first pass of the check holds no creepage constraint, since KiCad's creepage
search does not finish on a board with many pours. The creepage pass hands KiCad
only the creepage constraints, over the layout the first pass refilled, less the
ground pours that stand too far from Mains-class copper to matter. What is under
test here is what the check decides for itself: which rules the pass keeps, which
zones it takes out of the layout it hands KiCad and which it keeps in, how it
reads a ground pour's distance from Mains, and what it reports. KiCad itself,
on a design with a creepage shortfall, is in test_board_check_kicad_creepage_once.py.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402
from test_board_layer_separation import FOUR, outline, slot, track, zone  # noqa: E402

DESIGN = board_check.Design("hardware/m/board/board.kicad_pro")
MAINS, GROUND = "/M", "/G"
DESIGN_RULES = (
    "(version 1)\n"
    '(rule "Mains separation"\n'
    "\t(condition \"A.hasNetclass('Mains') && !B.hasNetclass('Mains')\")\n"
    "\t(constraint clearance (min 3mm))\n"
    "\t(constraint creepage (min 10mm)))\n"
    '(rule "Mains track width"\n'
    "\t(condition \"A.hasNetclass('Mains')\")\n"
    "\t(constraint track_width (min 0.2mm)))\n"
)
SIGNED = board_check.appended_rules((3.0, 6.0), "nonce", "/N")
LIMIT = 10.0
#: The top edge of a pour that stands exactly the limit from the 0.25 mm Mains track laid along y 10
EXACT = 10 + 0.125 + LIMIT


def text(*items: str, edge: str = "") -> str:
    return f"(kicad_pcb (version 20260206) (layers {FOUR})\n{outline()}{edge}\n" + "\n".join(items) + "\n)\n"


def tree(*items: str, edge: str = "") -> list:
    return sexpr.parse_one(text(*items, edge=edge))


def pour(top: float, layer: str = "In1.Cu", net: str = GROUND) -> str:
    box = (5, top, 25, top + 3)
    return zone(net, layer, box, box)


MAINS_TRACK = track(MAINS, 10, 10, 20, 10, "F.Cu")
#: A rule that reaches from a net that is not Mains-class, so a pour near that net's copper cannot be judged by the guard
NAMED = '(rule "pair"\n\t(condition "A.NetName == \'/R\' && B.NetName == \'/LV\'")\n\t(constraint creepage (min 10mm)))\n'


class OnlyCreepage(unittest.TestCase):
    def test_every_constraint_but_the_creepage_is_taken_out_and_a_rule_left_with_none_is_dropped_whole(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        out = board_check.only_creepage(DESIGN_RULES)
        self.assertEqual(out, '(version 1)\n(rule "Mains separation"\n'
                              "\t(condition \"A.hasNetclass('Mains') && !B.hasNetclass('Mains')\")\n"
                              "\t(constraint creepage (min 10mm)))\n")

    def test_the_signed_rules_keep_their_names_and_their_creepage_and_lose_the_rest_including_the_marker(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        out = board_check.only_creepage(SIGNED)
        self.assertIn(f'(rule "{board_check.SIGNED_RULE}"', out)
        self.assertIn("(constraint creepage (min 6mm))", out)
        self.assertNotIn("clearance", out)
        self.assertNotIn("assertion", out)

    def test_it_and_without_creepage_split_the_constraints_between_them_with_none_lost_and_none_in_both(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        whole = DESIGN_RULES + SIGNED
        kind = lambda rules: re.findall(r"\(constraint ([a-z_]+)", rules)
        creepage, rest = kind(board_check.only_creepage(whole)), kind(board_check.without_creepage(whole))
        self.assertEqual(sorted(creepage + rest), sorted(kind(whole)))
        self.assertEqual(set(creepage), {"creepage"})
        self.assertNotIn("creepage", rest)

    def test_the_order_of_the_rules_is_kept_since_the_last_matching_rule_decides(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        names = lambda rules: re.findall(r'\(rule "([^"]+)"', rules)
        out = names(board_check.only_creepage(DESIGN_RULES + SIGNED))
        self.assertEqual(out, [name for name in names(DESIGN_RULES + SIGNED) if name in out])
        self.assertEqual(out[0], "Mains separation")

    def test_a_creepage_constraint_in_a_form_the_check_does_not_read_is_kept_so_it_is_judged_here(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        odd = '(version 1)\n(rule "r"\n\t(constraint clearance (min 1mm))\n\t(constraint creepage (foo 4mm)))\n'
        self.assertEqual(board_check.only_creepage(odd), '(version 1)\n(rule "r"\n\t(constraint creepage (foo 4mm)))\n')

    def test_text_that_does_not_balance_is_returned_unchanged_and_a_creepage_inside_a_string_or_comment_is_no_constraint(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        broken = '(rule "r"\n\t(constraint creepage (min 4mm))\n'
        self.assertEqual(board_check.only_creepage(broken), broken)
        quoted = '# (constraint creepage (min 4mm))\n(rule "(constraint creepage (min 4mm))"\n\t(constraint clearance (min 1mm)))\n'
        self.assertEqual(board_check.only_creepage(quoted), "# (constraint creepage (min 4mm))\n")


class TheGuard(unittest.TestCase):
    def guard(self, *items: str, rules: str = DESIGN_RULES + SIGNED, grounds=(GROUND,), edge: str = ""):
        return board_check.ground_pour_guard(tree(MAINS_TRACK, *items, edge=edge), rules, {MAINS}, set(grounds))

    def test_pours_standing_the_limit_or_more_from_the_mains_copper_may_be_left_out_on_every_layer(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        guard = self.guard(pour(30), pour(EXACT, "In2.Cu"), pour(EXACT, "B.Cu"))
        self.assertEqual(guard.limit, LIMIT)
        self.assertEqual(guard.removable, [0, 1, 2])
        self.assertEqual(guard.kept, [])
        self.assertEqual(len(guard.nearest), 3)

    def test_a_pour_inside_the_limit_of_mains_copper_alone_is_judged_here_on_the_layers_it_shares_and_left_out_of_kicads(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        for layer in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
            with self.subTest(layer=layer):
                guard = self.guard(pour(30), pour(EXACT - 0.2, layer))
                self.assertEqual(guard.removable, [0, 1])
                self.assertEqual(guard.kept, [])
                ((label, distance, near),) = guard.judged
                self.assertIn(f"Zone [{GROUND}] on {layer}", label)
                self.assertAlmostEqual(distance, LIMIT - 0.2, places=3)
                self.assertIn("Track [/M] on F.Cu", near)
                # the Mains track is on F.Cu, so only a pour on F.Cu is a pair KiCad compares: the others are the cross-layer rule's
                self.assertEqual(len(guard.findings), 1 if layer == "F.Cu" else 0)
                for finding in guard.findings:
                    self.assertEqual(finding.test, "creepage")
                    self.assertAlmostEqual(finding.measured, LIMIT - 0.2, places=3)
                    self.assertEqual(finding.figure, LIMIT)
                    self.assertIn("Track [/M]", finding.mains.name)
                    self.assertIn(f"Zone [{GROUND}] on F.Cu", finding.other.name)

    def test_a_pour_just_inside_the_limit_on_the_mains_layer_fails_and_one_at_it_does_not(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        self.assertEqual(len(self.guard(pour(EXACT - 0.01, "F.Cu")).findings), 1)
        self.assertEqual(self.guard(pour(EXACT, "F.Cu")).findings, [])

    def test_a_barrier_slot_between_the_pour_and_the_mains_copper_lengthens_the_path_so_the_pour_is_no_shortfall(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        long_slot = slot(2, 14.5, 40, 15.5)
        guard = self.guard(pour(EXACT - 4, "F.Cu"), edge=long_slot)
        self.assertEqual(guard.removable, [0])
        self.assertEqual(len(guard.judged), 1, "it stands inside the limit in a straight line")
        self.assertEqual(guard.findings, [])
        self.assertEqual(len(self.guard(pour(EXACT - 4, "F.Cu")).findings), 1, "the same pour with no slot is a shortfall")

    def test_the_limit_is_the_largest_creepage_figure_of_the_rules_and_the_pour_exactly_at_it_passes(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        rules = '(version 1)\n(rule "a"\n\t(condition "A.hasNetclass(\'Mains\')")\n\t(constraint creepage (min 4mm)))\n'
        self.assertEqual(self.guard(pour(15), rules=rules).limit, 4.0)
        self.assertEqual(self.guard(pour(EXACT), rules=rules + DESIGN_RULES).limit, LIMIT)
        self.assertEqual(self.guard(pour(EXACT)).removable, [0])
        self.assertEqual(self.guard(pour(EXACT)).judged, [], "a pour at the limit is cleared by the distance alone")
        self.assertEqual(len(self.guard(pour(EXACT - 0.05)).judged), 1, "a pour just inside it is judged")

    def test_a_pour_of_a_net_that_is_not_ground_a_keepout_and_a_pour_on_a_net_a_rule_names_are_never_candidates(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        named = DESIGN_RULES + '(rule "pair"\n\t(condition "A.NetName == \'/G\' && B.NetName == \'/M\'")\n\t(constraint creepage (min 10mm)))\n'
        guard = self.guard(pour(30, net="/LV"), zone("", "In1.Cu", (5, 30, 25, 33), None, keepout=True), pour(30), rules=named)
        self.assertEqual(guard.removable, [], "the /G pour is a net a rule reaches from; /LV is not ground; the keepout carries no copper")
        self.assertEqual(guard.nearest, [])
        guard = self.guard(pour(30, net="/LV"), pour(30), grounds=(GROUND, "/LV"))
        self.assertEqual(guard.removable, [0, 1])

    def test_a_pour_standing_near_a_conductor_a_rule_names_is_kept_in_though_it_is_far_from_the_mains_class(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        rules = DESIGN_RULES + '(rule "pair"\n\t(condition "A.NetName == \'/R\' && B.NetName == \'/LV\'")\n\t(constraint creepage (min 8mm)))\n'
        value = board_check.ground_pour_guard(tree(MAINS_TRACK, track("/R", 10, 30, 20, 30, "F.Cu"), pour(33)), rules, {MAINS}, {GROUND})
        self.assertEqual(value.removable, [])
        self.assertEqual(len(value.kept), 1)
        self.assertAlmostEqual(value.kept[0][1], 33 - 30.125, places=3)

    def test_rules_the_guard_cannot_read_leave_every_pour_in_and_say_why(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        cases = {
            "a condition naming no Mains class and no net": '(rule "r"\n\t(condition "A.Type == \'Pad\'")\n\t(constraint creepage (min 5mm)))\n',
            "a rule with no condition": '(rule "r"\n\t(constraint creepage (min 5mm)))\n',
            "a figure in other units": '(rule "r"\n\t(condition "A.hasNetclass(\'Mains\')")\n\t(constraint creepage (min 0.4in)))\n',
            "a form the check does not read": '(rule "r"\n\t(condition "A.hasNetclass(\'Mains\')")\n\t(constraint creepage (foo 4mm)))\n',
            "text that does not balance": '(rule "r"\n\t(constraint creepage (min 5mm))\n',
        }
        for name, rules in cases.items():
            with self.subTest(case=name):
                guard = self.guard(pour(30), rules=DESIGN_RULES + rules)
                self.assertIsNone(guard.limit)
                self.assertEqual(guard.removable, [])
                self.assertTrue(guard.why)

    def test_a_rules_text_with_no_creepage_figure_has_no_limit_and_leaves_every_pour_in(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        guard = self.guard(pour(30), rules="(version 1)\n")
        self.assertIsNone(guard.limit)
        self.assertEqual(guard.removable, [])


class WithoutZones(unittest.TestCase):
    def test_only_the_zones_named_by_position_are_cut_and_every_other_byte_stays(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        zones = [pour(30), pour(20, "In2.Cu"), pour(32, "B.Cu")]
        whole = text(MAINS_TRACK, *zones)
        out = board_check.without_zones(whole, [0, 2], 3)
        parsed = sexpr.parse_one(out)
        self.assertEqual(len(sexpr.children(parsed, "zone")), 1)
        self.assertIn("(layer \"In2.Cu\")", sexpr.dump(sexpr.children(parsed, "zone")[0]))
        self.assertEqual(len(sexpr.children(parsed, "segment")), 1, "the copper that is not a zone stays")
        self.assertIn(zones[1], out)
        for gone in (zones[0], zones[2]):
            self.assertNotIn(gone, out)

    def test_nothing_is_cut_when_no_zone_is_named_and_none_when_the_text_does_not_hold_the_count_of_zones_given(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        whole = text(pour(30), pour(20))
        self.assertEqual(board_check.without_zones(whole, [], 2), whole)
        self.assertIsNone(board_check.without_zones(whole, [0], 3))
        self.assertIsNone(board_check.without_zones("(kicad_pcb (zone", [0], 1))

    def test_a_bracket_or_a_hash_inside_a_quoted_name_does_not_move_a_cut(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        odd = '(zone (net "/G") (net_name "G ) #") (layer "In1.Cu") (polygon (pts (xy 0 0) (xy 1 0) (xy 1 1))))'
        out = board_check.without_zones(text(odd, pour(20)), [0], 2)
        self.assertEqual(len(sexpr.children(sexpr.parse_one(out), "zone")), 1)


class TheCreepagePass(unittest.TestCase):
    """creepage_pass with KiCad's run replaced by one that records the layout and rules it was handed."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.copy = scratch.name
        self.rules_copy = os.path.join(self.copy, "board.kicad_dru")
        self.zones = [pour(30), pour(14, "In2.Cu"), pour(40, "B.Cu")]
        self.original = text(MAINS_TRACK, track("/R", 10, 17, 20, 17, "F.Cu"), *self.zones)
        self.layout = "board.kicad_pcb"
        with open(os.path.join(self.copy, self.layout), "w", encoding="utf-8") as handle:
            handle.write(self.original)
        self.seen = {}

    def run_pass(self, report=None, rules: str = DESIGN_RULES + SIGNED + NAMED, error: str = ""):
        def fake(command, cwd):
            with open(os.path.join(cwd, self.layout), encoding="utf-8") as handle:
                self.seen["layout"] = handle.read()
            with open(self.rules_copy, encoding="utf-8") as handle:
                self.seen["rules"] = handle.read()
            self.seen["command"] = command
            if error:
                return None, error
            marker = {"type": "assertion_failure", "description": f"Assertion failed (rule '{board_check.marker_rule('nonce')}')", "items": []}
            body = report if report is not None else [{"type": "creepage", "description": "Creepage violation (rule 'Mains separation'; actual 3 mm)", "items": []}]
            return {"violations": [marker] + body}, ""
        with mock.patch.object(board_check, "run_report", fake):
            return board_check.creepage_pass("kicad-cli", DESIGN, self.copy, self.layout, self.rules_copy, rules, "nonce", "/N",
                                             sexpr.parse_one(self.original), {MAINS}, {GROUND})

    def test_kicad_is_handed_only_the_creepage_constraints_and_the_layout_less_the_pours_standing_clear(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        found, stopped, guard = self.run_pass()
        self.assertEqual(stopped, [])
        self.assertEqual(guard.removable, [0, 2])
        zones = sexpr.children(sexpr.parse_one(self.seen["layout"]), "zone")
        self.assertEqual(len(zones), 1, "the pour standing inside the limit of the named net's copper is all the layout still holds of the pours")
        self.assertIn("In2.Cu", sexpr.dump(zones[0]))
        self.assertIn("(constraint creepage (min 10mm))", self.seen["rules"])
        self.assertNotIn("clearance", self.seen["rules"])
        self.assertIn(board_check.marker_rule("nonce"), self.seen["rules"])
        self.assertIn("drc", self.seen["command"])
        self.assertNotIn("--refill-zones", self.seen["command"])

    def test_a_pour_judged_by_the_check_is_left_out_of_the_layout_and_its_shortfall_comes_back_with_the_guard(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        self.original = text(MAINS_TRACK, pour(14, "F.Cu"), pour(40, "B.Cu"))
        with open(os.path.join(self.copy, self.layout), "w", encoding="utf-8") as handle:
            handle.write(self.original)
        found, stopped, guard = self.run_pass(rules=DESIGN_RULES + SIGNED)
        self.assertEqual(sexpr.children(sexpr.parse_one(self.seen["layout"]), "zone"), [])
        self.assertEqual(guard.kept, [])
        (finding,) = guard.findings
        self.assertAlmostEqual(finding.measured, 14 - 10.125, places=3)

    def test_the_layout_file_is_put_back_exactly_as_it_was_after_the_run_even_when_the_run_fails(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C6: The creepage pass hands the rule engine only the creepage constraints of the rules the first pass was given, under the same rule names, and the refilled layout less exactly the ground pours the guard cleared
        for error in ("", "KiCad did not finish"):
            with self.subTest(error=error):
                self.run_pass(error=error)
                with open(os.path.join(self.copy, self.layout), encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), self.original)

    def test_the_creepage_findings_come_back_as_reported_and_nothing_else_does(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C1: The signed creepage is computed once per design check, by a pass of its own that holds only the creepage constraints
        other = {"type": "clearance", "description": "Clearance violation (rule 'x'; actual 1 mm)", "items": []}
        creepage = {"type": "creepage", "description": "Creepage violation (rule 'Mains separation'; minimum 10 mm; actual 4.5 mm)",
                    "items": [{"description": "Track [/M] on F.Cu"}, {"description": "Track [/LV] on F.Cu"}]}
        found, stopped, _ = self.run_pass(report=[other, creepage])
        self.assertEqual(found, [creepage])
        self.assertEqual(stopped, [])

    def test_a_pour_inside_the_limit_stays_in_the_layout_and_a_failed_run_names_it_and_its_distance(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        found, stopped, guard = self.run_pass(error="KiCad did not finish within 7200 s")
        self.assertEqual(found, [])
        ((label, distance, _),) = guard.kept
        self.assertIn(f"Zone [{GROUND}] on In2.Cu", label)
        (violation,) = stopped
        self.assertEqual(violation.rule, "design_unreadable")
        self.assertIn("did not finish", violation.message)
        self.assertIn(label, violation.message)
        self.assertIn(f"{distance:.3f} mm", violation.message)
        self.assertIn("slow", violation.message)

    def test_rules_the_guard_cannot_read_leave_every_pour_in_the_layout(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C5: A ground pour is left out of the creepage test only where it stands at least the creepage limit in a straight line from every Mains-class conductor, or is judged by the check itself
        rules = '(version 1)\n(rule "r"\n\t(condition "A.Type == \'Pad\'")\n\t(constraint creepage (min 5mm)))\n'
        self.run_pass(rules=rules)
        self.assertEqual(len(sexpr.children(sexpr.parse_one(self.seen["layout"]), "zone")), 3)

    def test_a_run_that_did_not_load_the_creepage_rules_fails_the_design_and_a_rules_text_with_no_creepage_runs_nothing(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C1: The signed creepage is computed once per design check, by a pass of its own that holds only the creepage constraints
        def silent(command, cwd):
            return {"violations": []}, ""
        with mock.patch.object(board_check, "run_report", silent):
            found, stopped, _ = board_check.creepage_pass("kicad-cli", DESIGN, self.copy, self.layout, self.rules_copy, DESIGN_RULES + SIGNED,
                                                          "nonce", "/N", sexpr.parse_one(self.original), {MAINS}, {GROUND})
        self.assertEqual(found, [])
        self.assertEqual([violation.rule for violation in stopped], ["custom_rules"])
        with mock.patch.object(board_check, "run_report", side_effect=AssertionError("KiCad was run")):
            self.assertEqual(board_check.creepage_pass("kicad-cli", DESIGN, self.copy, self.layout, self.rules_copy, "(version 1)\n",
                                                       "nonce", "/N", sexpr.parse_one(self.original), {MAINS}, {GROUND})[:2], ([], []))


if __name__ == "__main__":
    unittest.main()
