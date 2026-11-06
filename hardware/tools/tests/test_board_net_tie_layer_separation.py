#!/usr/bin/env python3
"""How the cross-layer separation rule reads the copper a net-tie footprint draws, driven on synthetic layouts with no KiCad involved."""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import test_board_layer_separation as base  # noqa: E402

MAINS_A, MAINS_B, LOW_A, LOW_B = "/M", "/M2", "/LV", "/LV2"


def tie(first: str, second: str, groups: str = '(net_tie_pad_groups "1, 2")', layer: str = "F.Cu") -> str:
    """A net-tie footprint of two small pads on `first` and `second`, over a netless copper graphic on `layer`, centred at (30, 20)."""
    return ('(footprint "lib:tie" (layer "F.Cu") (at 30 20) (property "Reference" "NT1" (at 0 0 0)) ' + groups
            + f' (fp_poly (pts (xy -1 -0.5) (xy 1 -0.5) (xy 1 0.5) (xy -1 0.5)) (stroke (width 0) (type solid)) (fill yes) (layer "{layer}"))'
            + base.pad("1", "smd", first, 29, 20, (0.5, 0.5), '"F.Cu"') + base.pad("2", "smd", second, 31, 20, (0.5, 0.5), '"F.Cu"') + ")")


def pour(net: str) -> str:
    return base.zone(net, "In1.Cu", (20, 15, 40, 25), (20, 15, 40, 25))


def graphic_findings(result):
    return [finding for finding in result.findings if "Graphic" in (finding.other.name + (finding.mains.name if finding.mains else ""))]


class ANetTiesGraphicIsTheCopperOfTheNetsItJoins(unittest.TestCase):
    def test_the_graphic_of_a_tie_between_mains_class_nets_is_held_against_no_mains_item(self):
        # SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS.C1: On a synthetic layout with a Mains-class line pour on an inner layer and a net-tie footprint of two pads on two Mains-class nets whose netless copper graphic lies on the front layer under it, the cross-layer rule raises no finding between the tie's graphic and any Mains-class item, whatever the distance in plan view, and the same layout with the tie's footprint naming no net-tie groups, so that the graphic is an ordinary netless graphic, raises the finding it raised. Out of scope is the rule's threshold.
        for label, where in (("under the pour", 0), ("beside the pour", 14), ("clear of the pour", 30)):
            with self.subTest(where=label):
                moved = base.board(pour(MAINS_A), tie(MAINS_A, MAINS_B).replace("(at 30 20)", f"(at {30 + where} 20)"))
                self.assertEqual(graphic_findings(base.found(moved, mains=(MAINS_A, MAINS_B))), [])
        ordinary = base.board(pour(MAINS_A), tie(MAINS_A, MAINS_B, groups=""))
        self.assertTrue(graphic_findings(base.found(ordinary, mains=(MAINS_A, MAINS_B))), "an untied graphic is low-voltage copper")

    def test_a_tie_that_joins_only_mains_class_nets_gives_no_finding_whichever_of_its_nets_is_the_pours(self):
        # SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS.C1: a net-tie footprint of two pads on two Mains-class nets whose netless copper graphic lies on the front layer under it, the cross-layer rule raises no finding between the tie's graphic and any Mains-class item
        for under in (MAINS_A, MAINS_B):
            with self.subTest(pour=under):
                self.assertEqual(base.found(base.board(pour(under), tie(MAINS_A, MAINS_B)), mains=(MAINS_A, MAINS_B)).findings, [])


class ATieThatJoinsNoMainsNetIsHeldAsLowVoltage(unittest.TestCase):
    def test_a_tie_between_low_voltage_nets_is_held_to_the_signed_figures_from_mains_on_another_layer(self):
        # SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS.C2: a net-tie footprint whose pads are on two low-voltage nets has its graphic held to the signed clearance and creepage from a Mains-class pour on another layer as a low-voltage item
        result = base.found(base.board(pour(MAINS_A), tie(LOW_A, LOW_B)), mains=(MAINS_A,))
        found = graphic_findings(result)
        self.assertTrue(found)
        self.assertTrue(all(finding.other.net == "" for finding in found))

    def test_a_tie_of_a_mains_class_net_to_one_outside_the_class_is_mains_copper_against_low_voltage_on_other_layers(self):
        # SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS.C2: a tie of one Mains-class net to one outside the class has its graphic held against the low-voltage copper on the other layers as Mains copper, named by its Mains-class net, while the net-tie rule still fails the tie
        low_pour = base.zone(LOW_A, "In1.Cu", (20, 15, 40, 25), (20, 15, 40, 25))
        result = base.found(base.board(low_pour, tie(MAINS_A, LOW_A)), mains=(MAINS_A,))
        found = [finding for finding in result.findings if finding.mains is not None and "Graphic" in finding.mains.name]
        self.assertTrue(found)
        self.assertTrue(all(finding.mains.net == MAINS_A for finding in found))
        layout = base.board(tie(MAINS_A, LOW_A))
        flagged = board_check.net_ties(base.DESIGN, layout, {MAINS_A})
        self.assertEqual([v.rule for v in flagged], ["mains_net_tie"])

    def test_a_group_naming_a_pad_the_footprint_lacks_ties_nothing_and_leaves_the_graphic_low_voltage(self):
        # SOL-PRE-ORDER-CHECK-NET-TIE-COPPER-IS-THE-COPPER-OF-THE-NETS-IT-JOINS.C2: A net tie's graphic that joins no Mains-class net is held as low-voltage copper against mains
        result = base.found(base.board(pour(MAINS_A), tie(LOW_A, LOW_B, groups='(net_tie_pad_groups "7, 8")')), mains=(MAINS_A,))
        self.assertTrue(graphic_findings(result))


if __name__ == "__main__":
    unittest.main()
