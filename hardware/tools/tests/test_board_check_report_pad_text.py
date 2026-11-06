#!/usr/bin/env python3
"""How the pre-order check reads a pad out of KiCad's own report, driven on synthetic report text with no KiCad involved."""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import sexpr  # noqa: E402
import test_board_spacing_exceptions as base  # noqa: E402

#: Two parts whose pads are all surface-mount, each pad on a net of its own.
SURFACE = sexpr.parse_one(
    '(kicad_pcb'
    ' (footprint "T" (property "Reference" "T1") (pad "1" smd rect (net "/MAINS_L")) (pad "2" smd rect (net "/MAINS_N"))'
    ' (pad "3" smd rect (net "/MAINS_N")))'
    ' (footprint "U" (property "Reference" "U1") (pad "1" smd rect (net "/MAINS_L")) (pad "2" smd rect (net "/MAINS_N"))))')

#: How KiCad 10 words each surface-mount pad of the layout above, with the copper layer after the part.
KICAD_10 = {"T1.1": "Pad 1 [/MAINS_L] of T1 on F.Cu", "T1.2": "Pad 2 [/MAINS_N] of T1 on F.Cu", "T1.3": "Pad 3 [/MAINS_N] of T1 on F.Cu",
            "U1.1": "Pad 1 [/MAINS_L] of U1 on B.Cu", "U1.2": "Pad 2 [/MAINS_N] of U1 on B.Cu"}


def reported(figure: float, actual: float, first: str, second: str, words: dict = None) -> dict:
    """One creepage violation as KiCad's JSON report writes it, between two of the pads above, each described as `words` has it."""
    words = words or KICAD_10
    return {"type": "creepage", "severity": "error",
            "description": f"Creepage violation (rule '{base.TERMINAL}' creepage {figure:.4f} mm; actual {actual:.4f} mm)",
            "items": [{"description": words[first], "pos": {"x": 1, "y": 2}}, {"description": words[second], "pos": {"x": 3, "y": 4}}]}


def judge(violations, *entries):
    signed, problems = base.read(base.basis(*entries))
    assert problems == [], [problem.line() for problem in problems]
    return board_check.judge_exceptions(base.DESIGN, base.RECORD, signed, violations, SURFACE, base.TODAY)


def entry(first: str, second: str, accepted: float = 1.8, **changes) -> dict:
    return base.entry(pair="mains_to_mains", constraint="creepage", between=[first, second], accepted_mm=accepted, **changes)


def read(text: str):
    found = board_check.REPORTED_PAD.search(text)
    return found and (found.group(2), found.group(1))


class AReportedPadIsReadInEveryWordingKiCadAndTheCheckWrite(unittest.TestCase):
    def test_a_surface_mount_pad_in_kicad_10_wording_is_a_pad_of_its_part_and_name(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C1: On a synthetic report item, "Pad 2 [/Net A] of T1 on F.Cu @ (42.34, 31.4) mm", "Pad 2 [/Net A] of T1 on B.Cu", "SMD pad 2 [/Net A] of T1", "PTH pad 2 [/Net A] of T1", "PTH pad A1 [+5V] of K1 @ (60.7, 11.35) mm" and a pad of no net, "Pad 1 [<no net>] of T1 on F.Cu" and "Pad [<no net>] of T1 on F.Cu", each read as a pad of the named reference designator and, where it has one, pad name; a net written with brackets or the word "of" inside it is read through to the pad's own reference; and a text that names a track, a via or a zone, and a part with no pad, is read as no pad. Out of scope is which pairs a record's entries name.
        for text, wanted in (
                ("Pad 2 [/Pump drives/PUMP_C_MT2] of T701 on F.Cu @ (42.34, 31.4) mm", ("T701", "2")),
                ("Pad 2 [/Net A] of T1 on B.Cu", ("T1", "2")),
                ("Pad 2 [/Net A] of T1 on In2.Cu", ("T1", "2")),
                ("SMD pad 2 [/Net A] of T1", ("T1", "2")),
                ("PTH pad 2 [/Net A] of T1", ("T1", "2")),
                ("pth pad 2 [/Net A] of T1 @ (1, 2) mm", ("T1", "2")),
                ("PTH pad A1 [+5V] of K1 @ (60.7, 11.35) mm", ("K1", "A1")),
                ("Pad 1 [<no net>] of T1 on F.Cu", ("T1", "1")),
                ("Pad 4 [unconnected-(U711-NC-Pad5)] of U711 on F.Cu @ (53.49, 20.34) mm", ("U711", "4")),
                ("SMD pad 1 [/AC] of R9 [x] of X1", ("X1", "1")),
                ("Pad [<no net>] of T1 on F.Cu", ("T1", None)),
        ):
            with self.subTest(text=text):
                self.assertEqual(read(text), wanted)

    def test_an_item_that_names_no_pad_is_read_as_no_pad(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C1: a text that names a track, a via or a zone, and a part with no pad, is read as no pad
        for text in ("Track [/Net A] on F.Cu, length 2.5 mm @ (1, 2) mm", "Via [/Net A] on F.Cu - B.Cu @ (1, 2) mm",
                     "Zone 'pour' [/Net A] on In2.Cu, priority 1 @ (1, 2) mm", "NPTH pad of H9 @ (1, 2) mm", "Graphic on F.Cu of NT601",
                     "Footprint T1 on F.Cu", "Pad 2 [/Net A] of", ""):
            with self.subTest(text=text):
                self.assertIsNone(read(text))

    def test_the_position_the_check_reads_from_a_surface_mount_item_is_the_pads_reference_and_place(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C1: each read as a pad of the named reference designator
        found = board_check.Shortfall(reported(2.6, 1.8, "T1.1", "T1.2"), "mains_to_mains", 2.6,
                                      reported(2.6, 1.8, "T1.1", "T1.2")["items"])
        self.assertEqual(found.pads(), [("T1", 1.0, 2.0), ("T1", 3.0, 4.0)])
        self.assertTrue(found.is_item("T1.1", True, KICAD_10["T1.1"]))
        self.assertFalse(found.is_item("T1.2", True, KICAD_10["T1.1"]))


class ASignedExceptionForSurfaceMountPadsIsMatchedAndJudged(unittest.TestCase):
    def test_a_shortfall_at_or_above_the_accepted_distance_is_accepted_on_its_entry(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C2: On a synthetic layout rule check report whose two items are surface-mount pads worded as KiCad 10 words them, with the position the check reads from the item, a signed pad-pair exception between those two pads accepts the shortfall when the measured distance is no less than the accepted one
        for first, second in (("T1.1", "T1.2"), ("T1.2", "T1.1")):
            with self.subTest(order=(first, second)):
                judged = judge([reported(2.6, 1.8, "T1.1", "T1.2")], entry(first, second, 1.8))
                self.assertEqual(judged.violations, [])
                self.assertEqual(len(judged.accepted), 1)
                self.assertIn("measures 1.8 mm", judged.accepted[0])

    def test_a_shortfall_below_the_accepted_distance_fails_naming_the_entry(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C2: and fails naming the entry when it is less
        judged = judge([reported(2.6, 1.7, "T1.1", "T1.2")], entry("T1.1", "T1.2", 1.8))
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertEqual(found.rule, "spacing_exception")
        self.assertIn("accepted_exceptions[0]", found.message)
        self.assertIn("leaves 1.7 mm", found.message)

    def test_an_entry_for_another_pair_of_the_same_part_excuses_nothing_and_is_reported_unused(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C2: an entry for a different pair of the same part's pads does not excuse it, and an entry no reported shortfall uses still fails as unused
        shortfall = reported(2.6, 1.8, "T1.1", "T1.2")
        judged = judge([shortfall], entry("T1.1", "T1.3", 1.8))
        self.assertEqual((judged.accepted, judged.consumed), ([], set()))
        self.assertEqual([found.rule for found in judged.violations], ["spacing_exception"])
        self.assertIn("reports no shortfall", judged.violations[0].message)

    def test_the_through_hole_wording_is_matched_as_it_was(self):
        # SOL-PRE-ORDER-CHECK-READS-A-SURFACE-MOUNT-PAD-IN-KICADS-REPORT.C2: The same holds for the through-hole wording, whose matches do not change.
        through = {name: text.replace("Pad ", "PTH pad ").replace(" on F.Cu", "").replace(" on B.Cu", "") for name, text in KICAD_10.items()}
        judged = judge([reported(2.6, 1.8, "T1.1", "T1.2", through)], entry("T1.1", "T1.2", 1.8))
        self.assertEqual((judged.violations, len(judged.accepted)), ([], 1))


if __name__ == "__main__":
    unittest.main()
