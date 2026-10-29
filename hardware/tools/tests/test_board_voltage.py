#!/usr/bin/env python3
"""The pre-order check's derated-voltage rule and pin-limit rule, driven on synthetic designs with no KiCad involved.

What is under test is everything the two rules decide for themselves: how a
net's highest and lowest voltage are worked out from the pin-limit record, what
each rule fails and what it leaves alone, and what each failure names. The
nets are given as KiCad's netlist would give them; the schematic holds the
parts, with their catalogue numbers, values and ratings. Each of these can be
wrong while the check still reports a pass, which is the failure worth a test.
The check run against KiCad and the seeded-fault proof are in
the test_board_check_kicad_*.py files.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import datetime
import json
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
PEAK = 250 * 2 ** 0.5


def symbol(reference, value, lcsc, rating=None) -> str:
    fields = [("Reference", reference), ("Value", value), ("Footprint", ""), ("LCSC", lcsc)]
    fields += [("Rating", rating)] if rating is not None else []
    body = "".join(f'\t\t(property "{name}" "{text}")\n' for name, text in fields)
    return (f'\t(symbol\n\t\t(lib_id "Device:X")\n\t\t(unit 1)\n\t\t(on_board yes)\n{body}'
            f'\t\t(instances (project "board" (path "/root" (reference "{reference}") (unit 1))))\n\t)\n')


def pins(*nodes):
    """Pin nodes written (reference, pin number, pin name)."""
    return [board_check.PinNode(ref, pin, function) for ref, pin, function in nodes]


def domain(name, rail, volts):
    return {"name": name, "rail": rail, "highest_voltage_v": volts}


def limit_part(lcsc, *pin_entries):
    return {"lcsc": lcsc, "source": {"document": "none", "revision": "A", "section": "ratings", "read_on": "2026-10-14"},
            "pins": [{"pin": pin, "domain": dom, "absolute_max_v": high, "absolute_min_v": low,
                      "tolerates_driven_unpowered": tolerates} for pin, dom, high, low, tolerates in pin_entries]}


DOMAINS = [domain("five", "+5V", 5.25), domain("logic", "+3V3", 3.48), domain("ground", "GND", 0),
           domain("mains_line", "MAINS_L", PEAK), domain("mains_neutral", "MAINS_N", PEAK)]
POLICY = {"source": "none", "classes": [
    {"class": cls, "voltage": {"share": share, "source": "none"}, "power": {"share": 1, "source": "none"},
     "temperature": {"share": 1, "source": "none"}} for cls, share in (("capacitor", 0.8), ("mains part", 1), ("connector", 0.5))],
    "synthetic": True}


class World(unittest.TestCase):
    """A synthetic repository tracking every file in it, holding one design under hw/machine/board/."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        self.yaml = board_check.require_yaml()
        self.design = board_check.Design("hw/machine/board/board.kicad_pro")
        self.write(self.design.project, "{}")
        self.write(self.design.layout, "")

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def record(self, name, data):
        self.write(f"hw/machine/{name}", self.yaml.safe_dump(data, sort_keys=False))

    def remove(self, name):
        os.remove(os.path.join(self.root, "hw/machine", name))

    def build(self, parts, nets, domains=DOMAINS, limits=(), policy=POLICY, mains="present", mains_nets=("/MAINS_L", "/MAINS_N")):
        """Place `parts`, written (reference, value, lcsc, rating, class), on `nets`, and hold them to the records."""
        sheet = "(kicad_sch (version 20250114) (lib_symbols)\n" + "".join(symbol(r, v, n, rating) for r, v, n, rating, _ in parts) + ")\n"
        self.write(self.design.schematic, sheet)
        positions = []
        for ref, value, lcsc, rating, klass in parts:
            entry = {"reference": ref, "value": value, "lcsc": lcsc}
            if rating is not None:
                entry["rating"] = rating
            if klass is not None:
                entry["class"] = klass
            positions.append(entry)
        self.record("parts-specification.yaml", {"positions": positions, "synthetic": True})
        if domains is DOMAINS:
            nets = {**{"/" + d["rail"]: [] for d in DOMAINS}, **nets}
        for name, held in (("derating-policy.yaml", policy), ("pin-limits.yaml", limits)):
            if held is None and os.path.exists(os.path.join(self.root, "hw/machine", name)):
                self.remove(name)
        if policy is not None:
            self.record("derating-policy.yaml", policy)
        if limits is not None:
            self.record("pin-limits.yaml", {"domains": list(domains), "parts": list(limits) or [limit_part("C-NONE", ("1", "five", 9, 0, True))],
                                            "synthetic": True})
        self.nets = nets
        self.mains = mains
        self.mains_nets = set(mains_nets)

    def run_rules(self, mains=None, signed=True):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)
        basis = board_check.Signed(3.0, 4.0, {"working_voltage": "250 V rms"}) if signed else None
        return board_check.voltage_rules(self.design, self.yaml, self.root, repository, True, mains or self.mains, basis,
                                         self.nets, self.mains_nets)

    def read(self, reader):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)
        return reader(self.yaml, self.root, repository, self.design, True)

    def lines(self, **more):
        return [v.line() for v in self.run_rules(**more)]

    def found(self, rule, **more):
        return [v for v in self.run_rules(**more) if v.rule == rule]


def cap_on_rails(extra_nets=None):
    nets = {"/+5V": pins(("C1", "1", ""), ("U1", "1", "VDD_1")), "/GND": pins(("C1", "2", ""), ("U1", "2", "GND_2")),
            "/MAINS_L": pins(("J1", "1", "")), "/MAINS_N": pins(("J1", "2", ""))}
    nets.update(extra_nets or {})
    return nets


CAP = ("C1", "100nF", "C100", "16V", "capacitor")
IC = ("U1", "CHIP", "C200", None, "none")
IC_LIMITS = limit_part("C200", ("1", "five", 6, -0.3, False), ("2", "ground", 6, -0.3, False))


class PartKindIsReadFromTheDesignator(unittest.TestCase):
    def test_each_prefix_gives_its_kind_and_the_class_plays_no_part(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A part's kind is read from its reference designator: U is an integrated circuit, D or Q a semiconductor, FB, L, F or R with the value zero a part that joins nets, and any other designator a passive or mechanical part.
        kinds = {("U1", None): board_check.INTEGRATED_CIRCUIT, ("U12", "x"): board_check.INTEGRATED_CIRCUIT,
                 ("D1", None): board_check.SEMICONDUCTOR, ("Q3", None): board_check.SEMICONDUCTOR,
                 ("FB1", None): board_check.JOINS_NETS, ("L2", "10uH"): board_check.JOINS_NETS, ("F1", None): board_check.JOINS_NETS,
                 ("R1", "0"): board_check.JOINS_NETS, ("R1", "0R"): board_check.JOINS_NETS, ("R1", " 0.0 "): board_check.JOINS_NETS,
                 ("R1", "0 ohm"): board_check.JOINS_NETS, ("R1", "10k"): board_check.PASSIVE, ("R1", "0.05"): board_check.PASSIVE,
                 ("R1", "100"): board_check.PASSIVE, ("R1", None): board_check.PASSIVE, ("C1", "0"): board_check.PASSIVE,
                 ("J1", None): board_check.PASSIVE, ("TP1", None): board_check.PASSIVE,
                 ("LED1", None): board_check.SEMICONDUCTOR, ("FID1", None): board_check.PASSIVE, ("FL1", None): board_check.PASSIVE,
                 ("LCD1", None): board_check.PASSIVE, ("LS1", None): board_check.PASSIVE, ("DS1", None): board_check.PASSIVE,
                 ("R0", "10k"): board_check.PASSIVE, ("R0", "0"): board_check.JOINS_NETS, ("Q10", None): board_check.SEMICONDUCTOR,
                 ("F1", "T1A"): board_check.JOINS_NETS, ("1", None): board_check.PASSIVE, ("RV1", "0"): board_check.PASSIVE}
        for (ref, value), kind in kinds.items():
            with self.subTest(ref=ref, value=value):
                self.assertEqual(board_check.part_kind(ref, value), kind)

    def test_a_figure_with_unit_v_vdc_or_vac_is_the_rating_and_an_ac_figure_is_taken_at_its_peak(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The voltage rating is the figure written with unit V, VDC or VAC; an AC figure is taken at its peak.
        peaks = {"16V": 16, "5.5 V": 5.5, "50VDC": 50, "250VAC": PEAK, "3A 250V": 250, "320V 8A": 320, "500mA 250VAC": PEAK,
                 "275Vrms": None, "630Vdc": 630, "250 Vac": PEAK, "275VAC": 275 * 2 ** 0.5, "5.5 v": 5.5, "50vdc": 50, "3A 250v": 250, "3A": None, "1W": None, "": None, "0V": None, "V": None, "x16V": None, None: None}
        for text, peak in peaks.items():
            with self.subTest(text=text):
                got = board_check.rating_peak(text)
                if peak is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(got, peak)


class TheDeratedVoltageRule(World):
    def test_a_part_within_the_voltage_share_of_its_rating_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The rule fails a part whose working voltage exceeds the policy's voltage share times its rating.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        self.assertEqual(self.lines(), [])

    def test_a_part_above_the_share_fails_naming_the_part_the_nets_and_the_limit(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The rule fails a part whose working voltage exceeds the policy's voltage share times its rating.
        self.build([("C1", "100nF", "C100", "6V", "capacitor"), IC], cap_on_rails(), limits=[IC_LIMITS])
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].design, self.design.project)
        self.assertEqual(found[0].location, f"{self.design.schematic} C1")
        for words in ("C1", "5.25 V", "/+5V", "/GND", "4.8 V", "0.8"):
            self.assertIn(words, found[0].message)

    def test_the_share_boundary_passes_at_the_limit_and_fails_just_above_it(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The rule fails a part whose working voltage exceeds the policy's voltage share times its rating.
        policy = {**POLICY, "classes": [{**POLICY["classes"][0], "voltage": {"share": 0.5, "source": "none"}}]}
        self.build([("C1", "x", "C100", "10.5V", "capacitor"), IC], cap_on_rails(), limits=[IC_LIMITS], policy=policy)
        self.assertEqual(self.found("derated_voltage"), [])
        self.build([("C1", "x", "C100", "10.4V", "capacitor"), IC], cap_on_rails(), limits=[IC_LIMITS], policy=policy)
        self.assertEqual(len(self.found("derated_voltage")), 1)

    def test_an_ac_rating_is_judged_at_its_peak(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: An AC figure is taken at its peak.
        nets = cap_on_rails({"/MAINS_L": pins(("C1", "1", "")), "/MAINS_N": pins(("C1", "2", ""))})
        nets.pop("/+5V"), nets.pop("/GND")
        self.build([("C1", "x", "C100", "250VAC", "mains part")], nets, limits=())
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        self.build([("C1", "x", "C100", "250VDC", "mains part")], nets, limits=())
        self.assertEqual(len(self.found("derated_voltage")), 1)
        self.build([("C1", "x", "C100", "240VAC", "mains part")], nets, limits=())
        self.assertEqual(len(self.found("derated_voltage")), 1)

    def test_a_pair_of_mains_nets_counts_as_the_domain_voltage_not_as_zero(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A pair whose two nets both take their highest voltage from the mains domain counts as that domain's highest_voltage_v.
        nets = {"/MAINS_L": pins(("C1", "1", "")), "/MAINS_N": pins(("C1", "2", ""))}
        self.build([("C1", "x", "C100", "100V", "mains part")], nets, limits=())
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("353.553 V", found[0].message)

    def test_the_working_voltage_is_the_largest_difference_over_every_pair_of_the_parts_nets(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The working voltage of a part is the largest, over every pair of nets it connects, of the difference between their highest voltages.
        nets = {"/+5V": pins(("C1", "1", "")), "/+3V3": pins(("C1", "2", "")), "/GND": pins(("C1", "3", ""))}
        self.build([("C1", "x", "C100", "6V", "capacitor")], nets, limits=(), mains="none", mains_nets=())
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("5.25 V", found[0].message)
        self.build([("C1", "x", "C100", "6.6V", "capacitor")], nets, limits=(), mains="none", mains_nets=())
        self.assertEqual(self.found("derated_voltage"), [])
        # between two rails the difference is taken, not the larger of the two
        nets = {"/+5V": pins(("C1", "1", "")), "/+3V3": pins(("C1", "2", ""))}
        self.build([("C1", "x", "C100", "2.3V", "capacitor")], nets, limits=(), mains="none", mains_nets=())
        self.assertEqual(self.found("derated_voltage"), [], "5.25 - 3.48 = 1.77, within 0.8 of 2.3")
        self.build([("C1", "x", "C100", "2.1V", "capacitor")], nets, limits=(), mains="none", mains_nets=())
        self.assertEqual(len(self.found("derated_voltage")), 1)

    def test_a_net_reached_only_through_resistors_and_capacitors_cannot_be_worked_out_and_fails_the_covered_part(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A covered part with a net whose voltage cannot be worked out, being reached only through resistors or capacitors with no rail or listed pin, fails until that net is declared as the rail of a power domain.
        nets = {"/+5V": pins(("R1", "1", "")), "/MID": pins(("R1", "2", ""), ("C1", "1", ""), ("R2", "1", "")), "/GND": pins(("C1", "2", ""))}
        parts = [CAP, ("R1", "10k", "C300", None, "none"), ("R2", "10k", "C300", None, "none")]
        self.build(parts, nets, limits=(), mains="none", mains_nets=())
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].location, f"{self.design.schematic} C1 /MID")
        self.assertIn("declare it as the rail of a power domain", found[0].message)
        # a part of class none on the same net is not failed for it
        self.build([("C1", "x", "C100", None, "none")] + parts[1:], nets, limits=(), mains="none", mains_nets=())
        self.assertEqual(self.found("derated_voltage"), [])
        # declaring the net as a rail clears it
        self.build(parts, nets, domains=DOMAINS + [domain("mid", "MID", 2.5)], limits=(), mains="none", mains_nets=())
        self.assertEqual(self.found("derated_voltage"), [])

    def test_a_joining_part_carries_a_nets_voltage_and_a_resistor_does_not(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: each worked out as for pin limits, through a ferrite bead, inductor, fuse or zero-ohm link.
        for ref, value, joins in (("FB1", "600R", True), ("L1", "10uH", True), ("F1", "1A", True), ("R9", "0", True),
                                  ("R9", "0R", True), ("R9", "1k", False), ("C9", "10uF", False)):
            with self.subTest(ref=ref, value=value):
                nets = {"/+5V": pins((ref, "1", "")), "/MID": pins((ref, "2", ""), ("C1", "1", "")), "/GND": pins(("C1", "2", ""))}
                self.build([CAP, (ref, value, "C300", None, "none")], nets, limits=(), mains="none", mains_nets=())
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 0 if joins else 1, self.lines())

    def test_a_chain_of_joining_parts_carries_the_voltage_the_whole_way(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: The highest voltage a net can reach is that of any net joined to it, directly or in a chain.
        nets = {"/+5V": pins(("FB1", "1", "")), "/A": pins(("FB1", "2", ""), ("L1", "1", "")), "/B": pins(("L1", "2", ""), ("C1", "1", "")),
                "/GND": pins(("C1", "2", ""))}
        self.build([("C1", "x", "C100", "6V", "capacitor"), ("FB1", "x", "C3", None, "none"), ("L1", "x", "C4", None, "none")], nets,
                   limits=(), mains="none", mains_nets=())
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("5.25 V", found[0].message)

    def test_a_position_without_a_class_fails_and_none_and_a_listed_class_pass(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: Every position of the parts specification record carries class, naming a class of the derating policy exactly, or the value none; a position without it fails.
        self.build([("C1", "x", "C100", "16V", None), IC], cap_on_rails(), limits=[IC_LIMITS])
        found = self.found("derated_voltage")
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} C1"])
        self.assertIn("has no class", found[0].message)
        self.build([("C1", "x", "C100", None, "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
        self.assertEqual(self.found("derated_voltage"), [])

    def test_a_rated_part_cannot_name_none_whether_the_record_or_the_design_states_the_rating(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: none is for a part no class covers whose rating, in the record and in the design's Rating field, states no figure in V, VDC or VAC; a part with such a figure that names none fails.
        for rating in ("16V", "250VAC", "50VDC", "3A 250V"):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertEqual([v.location for v in found], [f"{self.design.schematic} C1 rating"] * 2)
                self.assertIn("names the class none", found[0].message)
                self.assertIn("the parts specification record", found[0].message)
                self.assertIn("the design's Rating field", found[1].message)
                self.assertIn(repr(rating), found[0].message)
                self.assertEqual(found[0].design, self.design.project)
                self.assertTrue(found[0].line().startswith(f"VIOLATION | {self.design.project} | derated_voltage | "))
        # the rating in the design's Rating field alone is enough, with the record silent
        self.build([("C1", "x", "C100", "16V", "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
        self.record("parts-specification.yaml", {"positions": [{"reference": "C1", "value": "x", "lcsc": "C100", "class": "none"},
                                                               {"reference": "U1", "value": "CHIP", "lcsc": "C200", "class": "none"}],
                                                 "synthetic": True})
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("the design's Rating field", found[0].message)

    def test_an_unrated_part_or_one_rated_in_other_units_may_name_none(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: none is accepted for a part whose rating states no figure in V, VDC or VAC.
        for rating in (None, "3A", "0.25W", "500mA", "1A", "50mA", ""):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
                self.assertEqual(self.found("derated_voltage"), [])

    def test_a_class_none_part_cannot_hide_a_voltage_shaped_rating_the_rule_cannot_read(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: none is for a part whose rating states no figure in V, VDC or VAC and no number followed by any other voltage unit.
        for rating in ("275Vrms", "275VRMS", "1,000V", "1kV", "1.5kV", "250VAC", "100mV", "0,5V"):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 2)
                self.assertIn("names the class none", found[0].message)
                self.assertTrue(found[0].location.endswith("C1 rating"))

    def test_a_position_naming_a_class_the_policy_lacks_fails_and_a_near_miss_of_the_name_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A position naming a class the derating policy lacks fails.
        for named in ("ghost", "Capacitor", "capacitor ", "Capacitors"):
            with self.subTest(named=named):
                self.build([("C1", "x", "C100", "16V", named), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1)
                self.assertIn(f"'{named}'", found[0].message)

    def test_a_design_with_no_derating_policy_fails_a_named_class_and_accepts_none(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C5: A missing record or declaration the rule needs fails; a design with no covered part is not failed for that; an explicit none is accepted.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS], policy=None)
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("the design has no derating policy", found[0].message)
        self.build([("C1", "x", "C100", None, "none"), IC], cap_on_rails(), limits=[IC_LIMITS], policy=None)
        self.assertEqual(self.found("derated_voltage"), [])

    def test_a_covered_part_without_a_voltage_rating_in_either_place_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: Every position whose part falls in a covered class carries a rating written as a figure with unit V, VDC or VAC in both that record and the design's Rating field, and one without it fails.
        for rating in (None, "0.25W", "275Vrms", "3A"):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "capacitor"), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertTrue(found)
                self.assertIn("no figure in V, VDC or VAC", found[0].message)
                self.assertTrue(found[0].location.endswith("C1 rating"))

    def test_a_rating_in_the_record_but_not_the_design_fails_naming_the_design_field(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: ... a rating written as a figure with unit V, VDC or VAC in both that record and the design's Rating field.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        sheet = open(os.path.join(self.root, self.design.schematic), encoding="utf-8").read()
        self.write(self.design.schematic, sheet.replace('(property "Rating" "16V")', '(property "Rating" "16W")'))
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("the design's Rating field", found[0].message)

    def test_mains_present_needs_a_pin_limit_record_with_a_mains_domain_at_least_the_basis_peak(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A mains domain in the pin-limit record is required when mains is declared present and is at least that peak.
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), limits=[IC_LIMITS])
        self.assertEqual(self.found("derated_voltage"), [])
        low = [d for d in DOMAINS if not d["name"].startswith("mains")] + [domain("mains_line", "MAINS_L", 353.5)]
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), domains=low, limits=[IC_LIMITS])
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("the mains domain mains_line", found[0].message)
        self.assertIn("353.553", found[0].message)
        none = [d for d in DOMAINS if not d["name"].startswith("mains")]
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), domains=none, limits=[IC_LIMITS])
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("no domain of the pin-limit record has a rail on a net of the Mains class", found[0].message)
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), limits=None)
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("holds no pin-limit record", found[0].message)

    def test_a_domain_whose_rail_is_not_in_the_mains_class_is_no_mains_domain(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The mains domain is the power domain whose rail is on a net of the Mains net class.
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), limits=[IC_LIMITS], mains_nets=("/MAINS_L",))
        self.assertEqual(self.found("derated_voltage"), [])
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), limits=[IC_LIMITS], mains_nets=("/OTHER",),
                   domains=[d for d in DOMAINS if not d["name"].startswith("mains")] + [domain("mains_line", "MAINS_L", 400)])
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("no domain of the pin-limit record has a rail on a net of the Mains class", found[0].message)

    def test_a_design_declaring_no_mains_needs_no_mains_domain(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C5: A missing record or declaration the rule needs fails; a design with no covered part is not failed for that.
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), limits=None, mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_an_unsigned_basis_leaves_the_peak_comparison_to_the_separation_rules(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A mains domain in the pin-limit record is required when mains is declared present.
        low = [d for d in DOMAINS if not d["name"].startswith("mains")] + [domain("mains_line", "MAINS_L", 1)]
        self.build([("C1", "x", "C100", None, "none")], cap_on_rails(), domains=low, limits=[IC_LIMITS])
        self.assertEqual(self.found("derated_voltage", signed=False), [])

    def test_a_rule_does_not_judge_a_record_whose_form_has_already_failed(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The reader still fails a key the decisions do not define; the rules read only what it accepts.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        self.record("pin-limits.yaml", {"domains": DOMAINS, "parts": [IC_LIMITS], "synthetic": True, "extra": 1})
        self.assertEqual(self.lines(), [])


class ThePinLimitRule(World):
    def test_a_pin_on_a_net_at_its_maximum_passes_and_above_it_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails a pin whose net can exceed its absolute_max_v.
        nets = {"/+5V": pins(("U1", "1", "VDD_1"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 5.25, -0.3, False))], mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 5.2, -0.3, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].design, self.design.project)
        self.assertEqual(found[0].location, f"{self.design.schematic} U1 pin 1")
        for words in ("net /+5V", "5.25 V", "absolute_max_v 5.2"):
            self.assertIn(words, found[0].message)

    def test_a_pin_on_a_net_that_can_fall_below_its_minimum_fails_and_a_pin_at_zero_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails a pin whose net can fall below its absolute_min_v.
        nets = {"/+5V": pins(("U1", "1", "VDD_1"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 6, 0.1, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("can fall to 0 V, below the pin's absolute_min_v 0.1", found[0].message)

    def test_a_mains_net_swings_to_minus_its_highest_voltage_and_only_that_tests_the_minimum(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The lowest voltage a net can reach is used only to test absolute_min_v: minus the domain's highest_voltage_v where it is the rail of the mains domain.
        nets = {"/MAINS_L": pins(("U1", "1", "A"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "mains_line", 400, -400, True))])
        self.assertEqual(self.found("pin_limit"), [])
        self.build([IC], nets, limits=[limit_part("C200", ("1", "mains_line", 400, -300, True))])
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("-353.553 V, below the pin's absolute_min_v -300", found[0].message)
        # a mains net is not judged against a floor of zero for the highest: a non-mains net is never below zero
        self.build([IC], {"/+5V": pins(("U1", "1", "VDD_1"))}, limits=[limit_part("C200", ("1", "five", 6, -0.3, False))])
        self.assertEqual(self.found("pin_limit"), [])

    def test_the_lowest_of_a_net_is_the_smallest_over_its_sources_including_a_listed_mains_pin(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The lowest voltage is the smallest of 0 V for a rail of another domain, minus the mains domain's highest, the lowest of every listed pin's domain on it, and that of any net joined to it.
        nets = {"/+5V": pins(("U1", "1", "VDD_1"), ("U2", "1", "A"))}
        parts = [IC, ("U2", "OPTO", "C201", None, "none")]
        limits = [limit_part("C200", ("1", "five", 6, -0.3, False)), limit_part("C201", ("1", "mains_line", 400, -400, True))]
        self.build(parts, nets, limits=limits)
        found = [v for v in self.found("pin_limit") if "can fall" in v.message]
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} U1 pin 1"])
        self.assertIn("-353.553 V", found[0].message)

    def test_a_pin_on_a_net_joined_to_a_higher_rail_through_a_fuse_or_link_fails_but_not_through_a_resistor(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A resistor or capacitor never carries one net's voltage onto another, so a divider or a decoupling capacitor never lifts a net.
        for ref, value, fails in (("F1", "1A", True), ("FB1", "x", True), ("L1", "x", True), ("R9", "0", True), ("R9", "4.7k", False),
                                  ("C9", "1u", False)):
            with self.subTest(ref=ref, value=value):
                nets = {"/+5V": pins((ref, "1", "")), "/LOGIC": pins((ref, "2", ""), ("U1", "1", "VDD_1"))}
                limits = [limit_part("C200", ("1", "logic", 3.6, -0.3, False))]
                self.build([IC, (ref, value, "C300", None, "none")], nets, limits=limits, mains="none", mains_nets=())
                lifted = [v for v in self.found("pin_limit") if "can reach" in v.message]
                self.assertEqual(len(lifted), 1 if fails else 0, self.lines())

    def test_a_net_reached_only_through_resistors_with_no_listed_pin_takes_no_limit_from_the_rule(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A net reached only through resistors or capacitors and carrying no listed pin takes no limit from this rule.
        nets = {"/+5V": pins(("R1", "1", "")), "/MID": pins(("R1", "2", ""), ("R2", "1", "")),
                "/AUX": pins(("U1", "1", "A"))}
        self.build([IC, ("R1", "1k", "C300", None, "none"), ("R2", "1k", "C301", None, "none")], nets,
                   limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_a_pin_driven_from_another_domain_fails_unless_it_tolerates_it(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails a pin whose net is driven from another domain while its own is unpowered where tolerates_driven_unpowered is false.
        nets = {"/+3V3": pins(("U1", "1", "A"))}
        for tolerates, count in ((False, 1), (True, 0)):
            with self.subTest(tolerates=tolerates):
                self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 6, -0.3, tolerates))], mains="none", mains_nets=())
                found = self.found("pin_limit")
                self.assertEqual([v.location for v in found], [f"{self.design.schematic} U1 pin 1"] if count else [])
                if count:
                    self.assertIn("of domain five is on net /+3V3, driven from the domain logic", found[0].message)

    def test_a_ground_net_does_not_count_as_driving_from_another_domain(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: driven from another domain.
        nets = {"/GND": pins(("U1", "1", "GND_1"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "logic", 6, -0.3, False))], mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_a_connector_pin_declared_in_the_connectors_entry_gives_its_net_the_domain_voltage(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A connector pin driven from outside the board is declared in the connector's entry.
        nets = {"/IN": pins(("J1", "1", ""), ("U1", "1", "A"))}
        parts = [IC, ("J1", "IN", "C500", None, "none")]
        limits = [limit_part("C200", ("1", "logic", 3.6, -0.3, False)), limit_part("C500", ("1", "five", 30, -30, True))]
        self.build(parts, nets, limits=limits, mains="none", mains_nets=())
        found = [v for v in self.found("pin_limit") if "can reach" in v.message]
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} U1 pin 1"])
        self.assertIn("5.25 V", found[0].message)

    def test_a_pin_is_found_by_its_number_or_its_name(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The pin-limit record holds per part by LCSC number its pins.
        nets = {"/+5V": pins(("U1", "7", "VDD/PA3_7"))}
        for pin in ("7", "VDD", "PA3"):
            with self.subTest(pin=pin):
                self.build([IC], nets, limits=[limit_part("C200", (pin, "five", 5, 0, False))], mains="none", mains_nets=())
                self.assertEqual(len(self.found("pin_limit")), 1)

    def test_a_listed_pin_the_part_does_not_have_fails_naming_the_part_the_pin_and_the_catalogue_number(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A listed pin the placed part's symbol does not have fails.
        nets = {"/+5V": pins(("U1", "7", "VDD/PA3_7"))}
        self.build([IC], nets, limits=[limit_part("C200", ("7", "five", 6, 0, False), ("9", "five", 6, 0, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} U1"])
        for words in ("pin 9", "C200", "U1", "does not have"):
            self.assertIn(words, found[0].message)
        self.assertEqual(found[0].design, self.design.project)

    def test_one_bad_pin_among_good_ones_fails_and_a_real_unconnected_pin_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A listed pin the placed part's symbol does not have fails; a pin the part has but nothing connects is a pin it has.
        nets = {"/+5V": pins(("U1", "1", "VDD_1")), "unconnected-(U1-NC-Pad3)": pins(("U1", "3", "NC_3"))}
        good = [("1", "five", 6, 0, False), ("3", "five", 6, 0, False)]
        self.build([IC], nets, limits=[limit_part("C200", *good)], mains="none", mains_nets=())
        self.assertEqual(self.found("pin_limit"), [])
        self.build([IC], nets, limits=[limit_part("C200", *good, ("4", "five", 6, 0, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("pin 4", found[0].message)

    def test_every_integrated_circuit_and_semiconductor_the_record_omits_fails_and_a_passive_does_not(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails every semiconductor or integrated-circuit part the record omits; a passive or mechanical part needs no entry.
        parts = [IC, ("D1", "LED", "C210", None, "none"), ("Q1", "FET", "C211", None, "none"), ("R1", "1k", "C212", None, "none"),
                 ("C1", "1u", "C213", None, "none"), ("J1", "H", "C214", None, "none"), ("TP1", "T", "C215", None, "none"),
                 ("FID1", "F", "C216", None, "none")]
        self.build(parts, {"/+5V": pins(("U1", "1", "A"))}, limits=[limit_part("C200", ("1", "five", 6, 0, False))],
                   mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} D1", f"{self.design.schematic} Q1"])
        self.assertIn("omits the semiconductor D1, catalogue number C210", found[0].message)

    def test_an_integrated_circuit_with_no_catalogue_number_fails_by_name(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails every integrated-circuit part the record omits.
        self.build([("U1", "CHIP", "", None, "none")], {"/+5V": pins(("U1", "1", "A"))}, limits=[limit_part("C200", ("1", "five", 6, 0, False))],
                   mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("has no LCSC number", found[0].message)

    def test_a_design_with_no_pin_limit_record_fails_each_integrated_circuit_and_a_design_with_none_to_inspect_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C5: A missing record or declaration the rule needs fails; a design with no semiconductor, integrated-circuit or covered part is not failed for that.
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, limits=None, mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual(len(found), 1)
        self.assertIn("holds no pin-limit record", found[0].message)
        self.build([("R1", "1k", "C300", None, "none"), ("C1", "1u", "C301", None, "none")], {"/+5V": pins(("R1", "1", ""))},
                   limits=None, mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_two_pins_of_one_part_on_one_failing_net_are_each_named(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C4: A failure of any rule is reported with the rule's name, the design, and the offending item.
        nets = {"/+5V": pins(("U1", "1", "A"), ("U1", "2", "B"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 3, 0, False), ("2", "five", 3, 0, False))], mains="none", mains_nets=())
        self.assertEqual([v.location for v in self.found("pin_limit")],
                         [f"{self.design.schematic} U1 pin 1", f"{self.design.schematic} U1 pin 2"])


class ThePinCoverageRule(World):
    """Every connected pin of a listed semiconductor or integrated circuit has its own entry."""

    def omissions(self):
        return [v for v in self.found("pin_limit") if "omits" in v.message and "entry" in v.message]

    def test_a_connected_pin_the_entry_omits_fails_naming_the_rule_the_design_the_part_the_pin_and_the_catalogue_number(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: For each semiconductor or integrated-circuit part the pin-limit record lists, every connected pin of the placed part carries an entry in the part's record entry, and a connected pin the entry leaves out fails, naming the part and the pin.
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C3: A coverage failure is reported with the rule's name, the design, the part reference, the pin number and the part's catalogue number, in terms a builder can act on, in the same report as the existing checks.
        nets = {"/+5V": pins(("U1", "1", "VDD_1")), "/GND": pins(("U1", "2", "GND_2"), ("C1", "2", ""))}
        self.build([IC, ("C1", "1u", "C300", None, "none")], nets, limits=[limit_part("C200", ("1", "five", 6, 0, False))],
                   mains="none", mains_nets=())
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"^VIOLATION \| hw/machine/board/board.kicad_pro \| pin_limit \| \S+ U1 pin 2 \| ")
        self.assertEqual(len(lines[0].split(" | ")), 5)
        for words in ("U1", "pin 2", "C200", "net /GND", "integrated circuit"):
            self.assertIn(words, lines[0])

    def test_a_connected_pin_is_one_on_a_net_with_another_pin_of_the_same_or_any_other_part_or_on_a_rail(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: A pin is connected when its net holds another pin, of the same part or of any other part, or is the rail of a declared domain.
        listed = [limit_part("C200", ("1", "five", 6, 0, False))]
        cases = {
            "the rail of a declared domain, alone": {"/+5V": pins(("U1", "1", "A")), "/+3V3": pins(("U1", "2", "B"))},
            "another pin of the same part": {"/+5V": pins(("U1", "1", "A")), "/X": pins(("U1", "2", "B"), ("U1", "3", "C"))},
            "a pin of another part": {"/+5V": pins(("U1", "1", "A")), "/X": pins(("U1", "2", "B"), ("R1", "1", ""))},
        }
        for name, nets in cases.items():
            with self.subTest(name):
                self.build([IC, ("R1", "1k", "C300", None, "none")], nets, limits=listed, mains="none", mains_nets=())
                self.assertEqual({v.location for v in self.omissions()},
                                 {f"{self.design.schematic} U1 pin {pin}" for pin in ("2", "3") if any(n.pin == pin for p in nets.values() for n in p)})
                self.assertTrue(self.omissions())

    def test_a_pin_on_no_other_pin_and_no_rail_needs_no_entry(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: a pin on no other pin and no rail needs no entry.
        nets = {"/+5V": pins(("U1", "1", "A")), "unconnected-(U1-NC-Pad3)": pins(("U1", "3", "NC_3")),
                "/FLOAT": pins(("U1", "4", "D"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_a_pin_is_covered_by_an_entry_that_names_it_by_number_or_name_and_by_no_other_entry(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: A pin is covered only by an entry that names it, by its number or its name, and no entry stands for the pins it leaves unlisted.
        nets = {"/+5V": pins(("U1", "7", "VDD/PA3_7")), "/GND": pins(("U1", "8", "VSS_8"), ("R1", "1", ""))}
        parts = [IC, ("R1", "1k", "C300", None, "none")]
        for first, second in (("7", "8"), ("VDD", "VSS"), ("PA3", "8")):
            with self.subTest(first=first, second=second):
                self.build(parts, nets, limits=[limit_part("C200", (first, "five", 6, 0, False), (second, "ground", 6, 0, False))],
                           mains="none", mains_nets=())
                self.assertEqual(self.lines(), [])
        self.build(parts, nets, limits=[limit_part("C200", ("7", "five", 6, 0, False), ("9", "ground", 6, 0, False))],
                   mains="none", mains_nets=())
        self.assertEqual([v.location for v in self.omissions()], [f"{self.design.schematic} U1 pin 8"])
        self.build(parts, nets, limits=[limit_part("C200", ("VDD", "five", 6, 0, False))], mains="none", mains_nets=())
        self.assertEqual([v.location for v in self.omissions()], [f"{self.design.schematic} U1 pin 8"])

    def test_a_connected_pin_limited_only_by_a_current_still_takes_an_entry(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: A connected pin limited only by current takes an entry too, as the pin-limit decision states.
        nets = {"/+5V": pins(("D1", "1", "A"), ("R1", "1", "")), "/GND": pins(("D1", "2", "K"), ("R1", "2", ""))}
        parts = [("D1", "LED", "C210", None, "none"), ("R1", "1k", "C300", None, "none")]
        self.build(parts, nets, limits=[limit_part("C210", ("2", "ground", 5, -5, True))], mains="none", mains_nets=())
        self.assertEqual([v.location for v in self.omissions()], [f"{self.design.schematic} D1 pin 1"])
        self.build(parts, nets, limits=[limit_part("C210", ("1", "five", 5.25, -5, True), ("2", "ground", 5, -5, True))],
                   mains="none", mains_nets=())
        self.assertEqual(self.lines(), [])

    def test_a_semiconductor_is_held_to_it_and_a_passive_or_mechanical_part_is_not(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: Out of scope: passives and mechanical parts.
        nets = {"/+5V": pins(("Q1", "1", "G"), ("R1", "1", ""), ("J1", "1", ""), ("C1", "1", "")), "/GND": pins(("R1", "2", ""), ("C1", "2", ""))}
        parts = [("Q1", "FET", "C211", None, "none"), ("R1", "1k", "C300", None, "none"), ("J1", "H", "C214", None, "none"),
                 ("C1", "1u", "C213", None, "none")]
        self.build(parts, nets, limits=[limit_part("C211", ("2", "five", 6, 0, False)), limit_part("C300", ("2", "ground", 6, 0, False))],
                   mains="none", mains_nets=())
        self.assertEqual([v.location for v in self.omissions()], [f"{self.design.schematic} Q1 pin 1"])
        self.assertIn("semiconductor Q1", self.omissions()[0].message)

    def test_a_part_the_record_omits_altogether_is_reported_once_and_not_for_each_pin(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C1: A part the record omits altogether is reported once by the existing omission failure and not again for each pin.
        nets = {"/+5V": pins(("U1", "1", "A"), ("U1", "2", "B"), ("U1", "3", "C"))}
        self.build([IC], nets, limits=[limit_part("C999", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} U1"])
        self.assertIn("omits the integrated circuit U1", found[0].message)

    def test_a_record_whose_form_has_already_failed_is_not_judged_for_coverage(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C2: The coverage check is added to the pin-limit rule of the existing pre-order check, reading only the design's files and the records the design is held to, with no new record key.
        nets = {"/+5V": pins(("U1", "1", "A"), ("U1", "2", "B"))}
        self.build([IC], nets, limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        self.record("pin-limits.yaml", {"domains": DOMAINS, "parts": [limit_part("C200", ("1", "five", 6, 0, False))],
                                        "synthetic": True, "extra": 1})
        self.assertEqual(self.found("pin_limit"), [])

    def test_the_coverage_failure_reaches_the_design_checks_report_beside_the_existing_rules(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C2: The coverage check is added to the pin-limit rule of the existing pre-order check, run by the same one task-runner command.
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C3: ... in the same report as the existing checks.
        self.write(self.design.project, json.dumps({"text_variables": {"MAINS": "none", "NOT_FOR_MANUFACTURE": "true"}}))
        self.write(self.design.layout, "(kicad_pcb (version 20250114))\n")
        netlist = """(export (version "E")
  (components (comp (ref "U1") (libsource (lib "Device") (part "X"))) (comp (ref "C1") (libsource (lib "Device") (part "X"))))
  (nets
    (net (code 1) (name "/+5V") (node (ref "U1") (pin "1") (pinfunction "VDD_1")) (node (ref "C1") (pin "1")))
    (net (code 2) (name "/GND") (node (ref "U1") (pin "2") (pinfunction "GND_2")) (node (ref "C1") (pin "2")))))
"""
        self.build([IC, ("C1", "x", "C100", "6V", "capacitor")],
                   {"/+5V": pins(("U1", "1", "VDD_1"), ("C1", "1", "")), "/GND": pins(("U1", "2", "GND_2"), ("C1", "2", ""))},
                   limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/") for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)

        def kicad_report(command, cwd):
            return ({"sheets": []}, "") if "erc" in command else (None, "stood in")

        with mock.patch.object(board_check, "run_report", kicad_report), \
                mock.patch.object(board_check, "run_kicad", lambda command, cwd, output="report.json": (netlist, "")):
            found = board_check.check_design(self.design, repository, "kicad-cli", self.yaml, datetime.date(2026, 10, 20), [])
        self.assertIn(("pin_limit", f"{self.design.schematic} U1 pin 2"), {(v.rule, v.location) for v in found})


class EveryFailureNamesTheRuleTheDesignAndTheItem(World):
    def test_the_report_line_of_each_rule_carries_its_name_the_design_and_the_item(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item (net, pin, part reference, record key or figure) in terms a builder can act on, in the same report as the existing checks.
        self.build([("C1", "x", "C100", "1V", "capacitor"), IC, ("C2", "x", "C101", "16V", None)],
                   cap_on_rails(), limits=[limit_part("C200", ("1", "five", 3, 0, False))])
        lines = self.lines()
        self.assertTrue(any(re.match(r"VIOLATION \| hw/machine/board/board.kicad_pro \| derated_voltage \| \S+ C1 \| ", line) for line in lines), lines)
        self.assertTrue(any(re.match(r"VIOLATION \| hw/machine/board/board.kicad_pro \| derated_voltage \| \S+ C2 \| ", line) for line in lines), lines)
        self.assertTrue(any(re.match(r"VIOLATION \| hw/machine/board/board.kicad_pro \| pin_limit \| \S+ U1 pin 1 \| ", line) for line in lines), lines)
        for line in lines:
            self.assertEqual(len(line.split(" | ")), 5, line)


class TheReaderTakesTheClassKey(World):
    def specification(self, **entry):
        base = {"reference": "R1", "value": "1k", "lcsc": "C1"}
        self.record("parts-specification.yaml", {"positions": [{**base, **entry}], "synthetic": True})
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        return board_check.read_specification(self.yaml, self.root, board_check.Repository(self.root, files), self.design, True)

    def test_a_position_may_carry_class_and_the_reader_hands_it_on(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: This leaf extends the check's record reader to accept the class key on every position of the parts specification record, with none allowed.
        for value in ("none", "capacitor"):
            stated, problems = self.specification(**{"class": value})
            self.assertEqual(problems, [])
            self.assertEqual(stated["R1"]["class"], value)

    def test_a_blank_or_non_text_class_and_a_misspelt_key_still_fail(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: ... and the reader still fails a key the decisions do not define.
        for entry, words in (({"class": ""}, "class is ''"), ({"class": 3}, "class is 3"), ({"clas": "none"}, "holds the key 'clas'"),
                             ({"classes": "none"}, "holds the key 'classes'")):
            with self.subTest(entry=entry):
                stated, problems = self.specification(**entry)
                self.assertIsNone(stated)
                self.assertTrue(any(words in v.message for v in problems), [v.message for v in problems])

    def test_a_position_without_class_is_read_and_left_to_the_rule(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: a position without it fails, under the derated-voltage rule.
        stated, problems = self.specification()
        self.assertEqual(problems, [])
        self.assertNotIn("class", stated["R1"])

    def test_the_loaders_hand_back_the_mapping_only_when_the_form_is_right(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules read only the records the reader accepts.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)
        data, problems = board_check.load_pin_limits(self.yaml, self.root, repository, self.design, True)
        self.assertEqual(problems, [])
        self.assertEqual(data["domains"][0]["name"], "five")
        data, problems = board_check.load_derating(self.yaml, self.root, repository, self.design, True)
        self.assertEqual((problems, data["classes"][0]["class"]), ([], "capacitor"))
        self.record("derating-policy.yaml", {**POLICY, "shre": 1})
        data, problems = board_check.load_derating(self.yaml, self.root, repository, self.design, True)
        self.assertIsNone(data)
        self.assertTrue(problems)
        self.remove("pin-limits.yaml")
        repository = board_check.Repository(self.root, [f for f in files if not f.endswith("pin-limits.yaml")])
        self.assertEqual(board_check.load_pin_limits(self.yaml, self.root, repository, self.design, True), (None, []))


class TheRatingUnitAndDesignatorLettersAreReadIgnoringCase(World):
    def test_a_class_none_part_cannot_hide_a_rating_by_the_case_of_its_unit(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: none is for a part no class covers whose rating states no figure in V, VDC or VAC; a part with such a figure that names none fails.
        for rating in ("630Vdc", "250 Vac", "275VAC", "16v", "50vDC"):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "none"), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertEqual([v.location for v in found], [f"{self.design.schematic} C1 rating"] * 2)
                self.assertIn("names the class none", found[0].message)

    def test_a_covered_part_is_judged_the_same_whatever_the_case_of_its_unit(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C1: A part whose net can exceed its derated voltage rating fails.
        for rating in ("6V", "6v"):
            with self.subTest(rating=rating):
                self.build([("C1", "x", "C100", rating, "capacitor"), IC], cap_on_rails(), limits=[IC_LIMITS])
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1, self.lines())
                self.assertIn("5.25 V", found[0].message)

    def test_a_lowercase_designator_is_read_as_its_kind(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A part's kind is read from its reference designator: U is an integrated circuit, D or Q a semiconductor, FB, L, F or R with the value zero a part that joins nets, and any other designator a passive or mechanical part.
        kinds = {"u1": board_check.INTEGRATED_CIRCUIT, "q1": board_check.SEMICONDUCTOR, "d1": board_check.SEMICONDUCTOR,
                 "led1": board_check.SEMICONDUCTOR, "Led1": board_check.SEMICONDUCTOR, "fb1": board_check.JOINS_NETS,
                 "f1": board_check.JOINS_NETS, "l1": board_check.JOINS_NETS, "fid1": board_check.PASSIVE, "ds1": board_check.PASSIVE}
        for ref, kind in kinds.items():
            with self.subTest(ref=ref):
                self.assertEqual(board_check.part_kind(ref, None), kind)
        self.assertEqual(board_check.part_kind("r1", "0"), board_check.JOINS_NETS)

    def test_a_lowercase_integrated_circuit_needs_a_pin_limit_entry(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: The rule fails every semiconductor or integrated-circuit part the record omits.
        self.build([("u1", "CHIP", "C200", None, "none")], {"/+5V": pins(("u1", "1", "A"))},
                   limits=[limit_part("C999", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        found = self.found("pin_limit")
        self.assertEqual([v.location for v in found], [f"{self.design.schematic} u1"])

    def test_a_lowercase_ferrite_bead_joins_nets(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: a pin on a net joined to a higher rail through a ferrite bead fails.
        nets = {"/+5V": pins(("fb1", "1", "")), "/LOGIC": pins(("fb1", "2", ""), ("U1", "1", "VDD_1"))}
        self.build([IC, ("fb1", "x", "C300", None, "none")], nets, limits=[limit_part("C200", ("1", "logic", 3.6, -0.3, False))],
                   mains="none", mains_nets=())
        lifted = [v for v in self.found("pin_limit") if "can reach" in v.message]
        self.assertEqual(len(lifted), 1, self.lines())


class ADuplicateEntryIsRefusedRatherThanLettingTheLaterReplaceTheEarlier(World):
    def test_a_strict_part_entry_followed_by_a_lax_one_for_the_same_catalogue_number_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules read only the records the reader accepts.
        strict = limit_part("C200", ("1", "five", 3, 0, False))
        lax = limit_part("C200", ("1", "five", 30, -30, False))
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, limits=[strict, lax], mains="none", mains_nets=())
        problems = self.read(board_check.read_pin_limits)
        self.assertEqual(len(problems), 1)
        self.assertIn("'C200'", problems[0].message)
        self.assertIn("more than once", problems[0].message)
        self.assertEqual(problems[0].design, self.design.project)
        self.assertIsNone(self.read(board_check.load_pin_limits)[0])

    def test_a_catalogue_number_listed_once_each_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules read only the records the reader accepts.
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))},
                   limits=[limit_part("C200", ("1", "five", 3, 0, False)), limit_part("C201", ("1", "five", 3, 0, False))],
                   mains="none", mains_nets=())
        self.assertEqual(self.read(board_check.read_pin_limits), [])

    def test_a_duplicate_domain_or_class_name_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules read only the records the reader accepts.
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, domains=DOMAINS + [domain("five", "+12V", 50)],
                   limits=[limit_part("C200", ("1", "five", 3, 0, False))], mains="none", mains_nets=())
        problems = self.read(board_check.read_pin_limits)
        self.assertEqual(len(problems), 1)
        self.assertIn("the domain 'five'", problems[0].message)
        twice = {**POLICY, "classes": POLICY["classes"] + [dict(POLICY["classes"][0])]}
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, policy=twice, limits=[limit_part("C200", ("1", "five", 3, 0, False))])
        problems = self.read(board_check.read_derating)
        self.assertEqual(len(problems), 1)
        self.assertIn("the class 'capacitor'", problems[0].message)


    def test_two_domains_naming_one_rail_fail_whatever_the_slash_and_either_order(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules read only the records the reader accepts.
        for second in ("/+5V", "+5V", " +5V"):
            with self.subTest(second=second):
                self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, domains=[domain("five", "+5V", 50), domain("logic", second, 3.3)],
                           limits=[limit_part("C200", ("1", "five", 3, 0, False))], mains="none", mains_nets=())
                problems = self.read(board_check.read_pin_limits)
                self.assertEqual(len(problems), 1)
                self.assertIn("the rail '+5V'", problems[0].message)
                self.assertIn("more than once", problems[0].message)
                self.assertIsNone(self.read(board_check.load_pin_limits)[0])

    def test_a_domain_whose_rail_matches_no_net_of_the_design_fails_naming_the_domain_and_rail(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: a domain whose rail is no net of the design fails.
        for rail in ("+5v", "+5V ", "/sub/+5V", "+12V"):
            with self.subTest(rail=rail):
                self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, domains=[domain("five", rail, 5.25)],
                           limits=[limit_part("C200", ("1", "five", 3, 0, False))], mains="none", mains_nets=())
                found = [v for v in self.found("pin_limit") if "no net of the design" in v.message]
                self.assertEqual(len(found), 1, self.lines())
                self.assertIn("domain five", found[0].message)
                self.assertIn(f"rail {rail}", found[0].message)
                self.assertTrue(found[0].location.endswith("domains five"))
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, domains=[domain("five", "+5V", 5.25)],
                   limits=[limit_part("C200", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        self.assertEqual(self.found("pin_limit"), [])


class AReferenceDesignatorIsReadWithoutItsSurroundingSpace(World):
    def test_a_padded_designator_is_read_as_its_kind(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: A part's kind is read from its reference designator.
        for ref, kind in ((" U1", board_check.INTEGRATED_CIRCUIT), ("U1 ", board_check.INTEGRATED_CIRCUIT),
                          ("\tq1", board_check.SEMICONDUCTOR), (" FB1", board_check.JOINS_NETS), (" J1", board_check.PASSIVE)):
            with self.subTest(ref=ref):
                self.assertEqual(board_check.part_kind(ref, None), kind)

    def test_a_padded_integrated_circuit_needs_a_pin_limit_entry(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C2: An integrated circuit with no entry in the pin-limit record fails.
        self.build([(" U1", "CHIP", "C200", None, "none")], {"/+5V": pins((" U1", "1", "A"))},
                   limits=[limit_part("C999", ("1", "five", 6, 0, False))], mains="none", mains_nets=())
        found = [v for v in self.found("pin_limit") if "omits" in v.message]
        self.assertEqual(len(found), 1, self.lines())


RIDING_NETS = ("/MAINS_L", "/MAINS_N", "/TAP", "/HIGH", "/LOW")
FIVE = {"/+5V": []}
FIVE_DOMAIN = domain("five", "+5V", 5.25)
BASE = [FIVE_DOMAIN, domain("mains_line", "MAINS_L", PEAK), domain("mains_neutral", "MAINS_N", PEAK)]


def riding(name, rail, host, base=PEAK, fraction=None, offset_v=None):
    """A domain riding on `host` whose own figure is the one its host's `base` figure derives."""
    entry = {"name": name, "rail": rail, "highest_voltage_v": base * fraction if fraction is not None else base + offset_v,
             "rides_on": host}
    entry.update({"fraction": fraction} if fraction is not None else {"offset_v": offset_v})
    return entry


def across(first, second, rating, ref="C1"):
    """A part with a single pin on each of the two nets, in the order given."""
    return {first: pins((ref, "1", "")), second: pins((ref, "2", ""))}, [(ref, "x", "C100", rating, "mains part")]


class ARidingDomainIsJudgedByTheDifferenceOfItsVoltageAndItsHosts(World):
    def divider(self, domains, nets, rating, mains_nets=RIDING_NETS):
        nets, parts = nets
        self.build(parts, {**FIVE, **nets}, domains=domains, limits=(), mains_nets=mains_nets)

    def test_a_part_across_a_fraction_tap_and_its_reference_passes_within_the_share_and_fails_above_it_naming_the_difference(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: On a synthetic design with a mains domain and a domain riding on it by fraction, a part across the derived net and its reference passes when the difference is within the policy's share of its rating, and fails when it exceeds it, naming the part and the difference.
        domains = BASE + [riding("tap", "TAP", "mains_neutral", fraction=0.5)]
        # the difference is half the mains peak, 176.78 V, far below the 353.55 V the whole domain would charge
        self.divider(domains, across("/TAP", "/MAINS_N", "180V"), "180V")
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        self.divider(domains, across("/TAP", "/MAINS_N", "170V"), "170V")
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("C1", found[0].message)
        self.assertIn("176.777 V", found[0].message)
        self.assertEqual(found[0].location, f"{self.design.schematic} C1")

    def test_a_part_across_an_offset_net_passes_or_fails_by_the_offset_whether_it_sits_above_or_below_its_host(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: The same holds for offset_v, above or below the host.
        for rail, offset in (("HIGH", 3.2), ("LOW", -3.2)):
            with self.subTest(rail=rail):
                domains = BASE + [riding(rail.lower(), rail, "mains_neutral", offset_v=offset)]
                self.divider(domains, across("/" + rail, "/MAINS_N", "3.5V"), "3.5V")
                self.assertEqual(self.found("derated_voltage"), [], self.lines())
                self.divider(domains, across("/" + rail, "/MAINS_N", "3.1V"), "3.1V")
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1)
                self.assertIn("3.2 V", found[0].message)

    def test_the_result_is_the_same_whichever_net_the_part_names_first(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: The result is the same whichever of the two nets the part names first, and a mains domain on either net counts.
        domains = BASE + [riding("tap", "TAP", "mains_neutral", fraction=0.5)]
        for first, second in (("/TAP", "/MAINS_N"), ("/MAINS_N", "/TAP")):
            with self.subTest(first=first):
                self.divider(domains, across(first, second, "170V"), "170V")
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1)
                self.assertIn("176.777 V", found[0].message)
        # two unrelated mains domains of different figures: the larger counts from either side
        domains = [FIVE_DOMAIN, domain("small", "MAINS_L", PEAK), domain("large", "MAINS_N", PEAK * 1.1)]
        for first, second in (("/MAINS_L", "/MAINS_N"), ("/MAINS_N", "/MAINS_L")):
            with self.subTest(first=first, unrelated=True):
                self.divider(domains, across(first, second, "100V"), "100V", mains_nets=("/MAINS_L", "/MAINS_N"))
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1, self.lines())
                self.assertIn("388.909 V", found[0].message)

    def test_a_mains_domain_on_the_second_net_alone_still_counts_when_the_first_is_a_riding_net_of_another_host(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: a mains domain on either net counts, not only on the first.
        domains = [FIVE_DOMAIN, domain("mains_line", "MAINS_L", PEAK * 1.1), domain("mains_neutral", "MAINS_N", PEAK),
                   riding("tap", "TAP", "mains_line", base=PEAK * 1.1, fraction=0.5)]
        for first, second in (("/TAP", "/MAINS_N"), ("/MAINS_N", "/TAP")):
            with self.subTest(first=first):
                self.divider(domains, across(first, second, "100V"), "100V", mains_nets=("/MAINS_L", "/MAINS_N", "/TAP"))
                found = self.found("derated_voltage")
                self.assertEqual(len(found), 1, self.lines())
                self.assertIn("353.553 V", found[0].message)

    def test_two_nets_riding_one_host_count_the_difference_and_unrelated_nets_count_the_larger_domain_figure(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: A part across two nets of one host with no stated relation still counts the host's full highest_voltage_v.
        both = BASE + [riding("tap", "TAP", "mains_neutral", fraction=0.5), riding("high", "HIGH", "mains_neutral", fraction=0.25)]
        self.divider(both, across("/TAP", "/HIGH", "88V"), "88V")
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("88.3883 V", found[0].message)
        self.divider(both, across("/TAP", "/HIGH", "89V"), "89V")
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        apart = BASE + [riding("tap", "TAP", "mains_line", fraction=0.5), riding("high", "HIGH", "mains_neutral", fraction=0.25)]
        self.divider(apart, across("/TAP", "/HIGH", "170V"), "170V")
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("176.777 V", found[0].message)
        self.divider(apart, across("/TAP", "/HIGH", "180V"), "180V")
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        self.divider(both, across("/MAINS_L", "/MAINS_N", "300V"), "300V")
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("353.553 V", found[0].message)

    def test_a_chain_of_hosts_is_worked_through_to_its_root(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: a chain of hosts is worked out through to its root.
        domains = BASE + [riding("tap", "TAP", "mains_neutral", fraction=0.5), riding("high", "HIGH", "tap", base=PEAK * 0.5, offset_v=3.2)]
        self.divider(domains, across("/HIGH", "/TAP", "3.1V"), "3.1V")
        self.assertEqual(len(self.found("derated_voltage")), 1)
        self.divider(domains, across("/HIGH", "/TAP", "3.5V"), "3.5V")
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        self.divider(domains, across("/HIGH", "/MAINS_N", "170V"), "170V")
        found = self.found("derated_voltage")
        self.assertEqual(len(found), 1)
        self.assertIn("173.577 V", found[0].message)

    def test_a_riding_domain_lowest_voltage_follows_its_host_and_its_highest_tests_the_absolute_maximum(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: The riding net's highest voltage is the host's highest with the fraction applied or offset_v added, and its lowest is worked out from the host's lowest the same way.
        domains = BASE + [riding("high", "HIGH", "mains_neutral", offset_v=3.2), riding("tap", "TAP", "mains_neutral", fraction=0.5)]
        volts = None

        def volts_of(domains):
            self.divider(domains, across("/HIGH", "/TAP", "1000V"), "1000V")
            listed = {}
            nets = self.nets
            return board_check.NetVoltages(
                nets, {d["name"]: (d["rail"], d["highest_voltage_v"]) for d in domains}, set(self.mains_nets), set(), listed,
                {d["name"]: (d["rides_on"], d.get("fraction"), d.get("offset_v")) for d in domains if "rides_on" in d})

        volts = volts_of(domains)
        self.assertAlmostEqual(volts.highest("/HIGH"), PEAK + 3.2)
        self.assertAlmostEqual(volts.lowest("/HIGH"), -PEAK + 3.2)
        self.assertAlmostEqual(volts.lowest("/TAP"), -PEAK / 2)

    def test_a_mains_domain_riding_a_host_passes_the_floor_when_the_host_meets_it_and_fails_when_it_does_not(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C1: A mains domain with rides_on passes the mains floor when its host meets it directly or through its own hosts and fails when that host does not, while a mains domain with no rides_on below the floor still fails.
        part = [("C1", "x", "C100", None, "none")]
        tap = riding("tap", "TAP", "mains_neutral", fraction=0.5)
        self.build(part, {**FIVE, "/TAP": []}, domains=BASE + [tap], limits=(), mains_nets=RIDING_NETS)
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        # through a host that itself rides: the chain's root meets the floor
        deep = riding("deep", "HIGH", "tap", base=PEAK * 0.5, offset_v=1)
        self.build(part, {**FIVE, "/TAP": [], "/HIGH": []}, domains=BASE + [tap, deep], limits=(), mains_nets=RIDING_NETS)
        self.assertEqual(self.found("derated_voltage"), [], self.lines())
        # the root of the chain is below the floor
        weak = [FIVE_DOMAIN, domain("mains_line", "MAINS_L", PEAK), domain("mains_neutral", "MAINS_N", 100)]
        weak_tap = riding("tap", "TAP", "mains_neutral", base=100, fraction=0.5)
        self.build(part, {**FIVE, "/TAP": []}, domains=weak + [weak_tap], limits=(), mains_nets=RIDING_NETS)
        found = [v for v in self.found("derated_voltage") if v.location.endswith("domains tap")]
        self.assertEqual(len(found), 1, self.lines())
        self.assertIn("the mains domain tap rides on mains_neutral", found[0].message)
        self.assertIn("mains_neutral stating highest_voltage_v 100", found[0].message)
        # and through a host that rides
        weak_deep = riding("deep", "HIGH", "tap", base=50, offset_v=1)
        self.build(part, {**FIVE, "/TAP": [], "/HIGH": []}, domains=weak + [weak_tap, weak_deep], limits=(), mains_nets=RIDING_NETS)
        self.assertEqual(len([v for v in self.found("derated_voltage") if v.location.endswith("domains deep")]), 1)
        # a mains domain with no rides_on below the floor still fails, and it is named
        self.build(part, {**FIVE, "/TAP": []}, domains=weak + [riding("tap", "TAP", "mains_line", fraction=0.5)], limits=(), mains_nets=RIDING_NETS)
        found = self.found("derated_voltage")
        self.assertEqual([v.location.rsplit(" ", 1)[-1] for v in found], ["mains_neutral"], self.lines())

    def test_records_without_the_riding_keys_are_judged_as_before(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: Records without the new keys read as before.
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        self.assertEqual(self.lines(), [])
        self.assertEqual(self.read(board_check.read_pin_limits), [])


class AMalformedRidingDeclarationFailsThePinLimitRecord(World):
    def problems(self, *domains):
        self.build([IC], {"/+5V": pins(("U1", "1", "A"))}, domains=BASE + list(domains),
                   limits=[limit_part("C200", ("1", "five", 3, 0, False))], mains="none", mains_nets=())
        return self.read(board_check.read_pin_limits)

    def only(self, problems, *words):
        self.assertEqual(len(problems), 1, [p.message for p in problems])
        for word in words:
            self.assertIn(word, problems[0].message)
        return problems[0]

    def test_a_well_formed_fraction_or_offset_declaration_is_accepted(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: Records without the new keys read as before.
        self.assertEqual(self.problems(riding("tap", "TAP", "mains_neutral", fraction=0.5),
                                       riding("high", "HIGH", "tap", base=PEAK * 0.5, offset_v=3.2),
                                       riding("full", "FULL", "mains_line", fraction=1)), [])

    def test_a_rides_on_naming_no_listed_domain_or_its_own_domain_fails_naming_the_domain_and_key(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: a rides_on that names no listed domain, names its own domain, or forms a cycle.
        missing = self.only(self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), "rides_on": "ghost"}),
                            "the domain tap", "rides_on", "ghost")
        self.assertTrue(missing.location.endswith("rides_on"))
        self.only(self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), "rides_on": "tap"}),
                  "the domain tap", "rides_on naming itself")
        self.only(self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), "rides_on": 7}), "rides_on", "7")

    def test_a_cycle_of_hosts_fails_naming_each_domain_in_it(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: a rides_on that forms a cycle.
        first = {**riding("a", "A", "b", base=100, fraction=0.5), "highest_voltage_v": 50}
        second = {**riding("b", "B", "a", base=50, fraction=0.5), "highest_voltage_v": 25}
        problems = self.problems(first, second)
        named = sorted(re.search(r"the domain (\w+) has rides_on that leads back", p.message).group(1) for p in problems
                       if "leads back" in p.message)
        self.assertEqual(named, ["a", "b"])
        # a domain that only leads into a cycle is not itself reported as being in it
        third = riding("c", "C", "a", base=50, fraction=0.5)
        problems = [p for p in self.problems(first, second, third) if "leads back" in p.message]
        self.assertEqual(len(problems), 2)

    def test_a_fraction_or_offset_without_rides_on_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: a fraction or offset_v without rides_on.
        for key, value in (("fraction", 0.5), ("offset_v", 1.0)):
            with self.subTest(key=key):
                self.only(self.problems({**domain("tap", "TAP", 5), key: value}), "the domain tap", f"states {key} without rides_on")

    def test_rides_on_with_both_keys_or_neither_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: fraction and offset_v together.
        both = {**riding("tap", "TAP", "mains_neutral", fraction=0.5), "offset_v": 1.0}
        self.only(self.problems(both), "the domain tap", "both fraction and offset_v")
        neither = {**domain("tap", "TAP", 5), "rides_on": "mains_neutral"}
        self.only(self.problems(neither), "the domain tap", "neither fraction nor offset_v")

    def test_a_fraction_of_zero_above_one_or_not_a_number_fails_and_one_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: a fraction of zero or above 1.
        for fraction in (0, 1.01, -0.5, "half", True):
            with self.subTest(fraction=fraction):
                entry = {**riding("tap", "TAP", "mains_neutral", fraction=0.5), "fraction": fraction}
                found = [p for p in self.problems(entry) if "fraction" in p.message and "above zero and at most one" in p.message]
                self.assertEqual(len(found), 1)
                self.assertIn("the domain tap", found[0].message)
        self.assertEqual(self.problems(riding("tap", "TAP", "mains_neutral", fraction=1)), [])

    def test_an_offset_of_zero_or_not_a_number_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: an offset_v of zero.
        for offset in (0, 0.0, "3", False):
            with self.subTest(offset=offset):
                entry = {**riding("tap", "TAP", "mains_neutral", offset_v=1), "offset_v": offset}
                found = [p for p in self.problems(entry) if "offset_v" in p.message and "other than zero" in p.message]
                self.assertEqual(len(found), 1)
                self.assertIn("the domain tap", found[0].message)

    def test_an_offset_leaving_the_derived_figure_not_above_zero_fails_and_one_just_above_passes(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: an offset_v that leaves the derived figure not above 0.
        low = {**domain("low", "LOW", 5), "rides_on": "small", "offset_v": -5}
        found = self.only(self.problems(domain("small", "SMALL", 5), low), "the domain low", "offset_v", "above 0")
        self.assertTrue(found.location.endswith("offset_v"))
        below = {**low, "offset_v": -6}
        self.only(self.problems(domain("small", "SMALL", 5), below), "the domain low", "-1")
        self.assertEqual(self.problems(domain("small", "SMALL", 5), {**low, "offset_v": -4.9, "highest_voltage_v": 0.1}), [])

    def test_a_highest_voltage_that_differs_from_the_derived_figure_fails_through_a_chain_too(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: a domain's highest_voltage_v that differs from the figure derived.
        wrong = {**riding("tap", "TAP", "mains_neutral", fraction=0.5), "highest_voltage_v": 200}
        found = self.only(self.problems(wrong), "the domain tap", "highest_voltage_v 200", "176.777")
        self.assertTrue(found.location.endswith("highest_voltage_v"))
        # a chain is worked out from the root, so a host that rides is held to the same figure its child derives from
        chain = riding("high", "HIGH", "tap", base=PEAK * 0.5, offset_v=3.2)
        self.assertEqual(self.problems(riding("tap", "TAP", "mains_neutral", fraction=0.5), chain), [])
        self.only(self.problems(riding("tap", "TAP", "mains_neutral", fraction=0.5), {**chain, "highest_voltage_v": 180}),
                  "the domain high", "highest_voltage_v 180")
        # float noise inside the check's slack is not a difference
        self.assertEqual(self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), "highest_voltage_v": PEAK * 0.5 * (1 + 1e-12)}), [])

    def test_any_other_unknown_key_on_a_domain_still_fails(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: any other unknown key.
        for key in ("rides", "offset", "fractions", "ride_on"):
            with self.subTest(key=key):
                self.only(self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), key: 1}), f"the key '{key}'")

    def test_the_rules_do_not_judge_a_record_whose_riding_keys_failed(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C2: Each of these fails the pin-limit record.
        self.problems({**riding("tap", "TAP", "mains_neutral", fraction=0.5), "rides_on": "tap"})
        self.assertEqual(self.lines(), [])
        self.assertIsNone(self.read(board_check.load_pin_limits)[0])


class TheHardwareNotesCarryAnEntryForEachRule(unittest.TestCase):
    def rows(self):
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        table = text[text.index("| Rule | Meaning |"):]
        table = table[:table.index("\n\n")]
        return {line.split("|")[1].strip().strip("`"): line.split("|")[2] for line in table.splitlines()[2:]}

    def test_each_rule_has_a_row_naming_what_fails_it_what_exempts_a_design_and_the_name_it_is_reported_under(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C7: The hardware notes' table of the pre-order check's rules carries one entry for each of the derated-voltage rule and the pin-limit rule, naming what fails it, what exempts a design, and the name its failure is reported under.
        rows = self.rows()
        with open(os.path.join(TOOLS, "board_check.py"), encoding="utf-8") as handle:
            code = handle.read()
        reported = set(re.findall(r'fail\("(derated_voltage|pin_limit)"', code))
        self.assertEqual(reported, {"derated_voltage", "pin_limit"})
        for name in reported:
            self.assertIn(name, rows)
            self.assertRegex(rows[name], r"(?i)exempt")
        self.assertIn("class", rows["derated_voltage"])
        self.assertIn("voltage share", rows["derated_voltage"])
        self.assertIn("mains domain", rows["derated_voltage"])
        self.assertIn("absolute_max_v", rows["pin_limit"])
        self.assertIn("absolute_min_v", rows["pin_limit"])
        self.assertIn("not in the pin-limit record", rows["pin_limit"])
        self.assertIn("tolerates_driven_unpowered", rows["pin_limit"])

    def test_the_notes_state_the_riding_keys_the_pairing_rule_and_the_floor_for_a_riding_domain(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-ACROSS-DERIVED-NETS.C3: The hardware notes state the keys, and every tracked design passes in the build round and nightly.
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        record = next(line for line in text.splitlines() if line.startswith("| Pin-limit record (`pin-limits.yaml`)"))
        for words in ("`rides_on`", "`fraction`", "`offset_v`", "a positive offset puts the riding net above its host", "forms a cycle",
                      "naming the domain and the key", "differs from the derived figure"):
            self.assertIn(words, record)
        bullet = next(line for line in text.splitlines() if line.startswith("- **Derated voltage** (`derated_voltage`)"))
        for words in ("unless one net rides on the other's domain or both ride on one host", "two nets of one host with no stated relation",
                      "a mains domain with `rides_on` is held instead to its derivation from its host"):
            self.assertIn(words, bullet)
        self.assertIn("a riding mains domain on a host below the mains floor", text)

    def test_the_pin_limit_entry_and_bullet_state_the_coverage_failure_its_exemption_and_its_name_and_no_longer_exempt_a_current_limited_pin(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C6: The hardware notes' table of the pre-order check's rules extends the pin-limit rule's entry, and replaces its sentence that exempts a pin whose limit is a current, with what the coverage failure names, which pin it exempts and the name it is reported under.
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        row = self.rows()["pin_limit"]
        for words in ("connected pin", "missing from its entry", "part, the pin number and the catalogue number", "on no other pin and no rail is exempt"):
            self.assertIn(words, row)
        bullet = next(line for line in text.splitlines() if line.startswith("- **Pin limits** (`pin_limit`)"))
        for words in ("connected pin the entry omits fails, naming the part, the pin and the part's catalogue number",
                      "a pin on no other pin and no rail needs no entry", "takes an entry like any other"):
            self.assertIn(words, bullet)
        self.assertNotIn("is not listed", bullet)

    def test_the_parts_specification_form_and_the_hw_reads_listing_name_the_new_records_and_key(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C6: The board-reads listing's description names the derating policy and pin-limit records.
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            readme = handle.read()
        self.assertIn("`rating`, `lcsc` and `class`", readme)
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        start = lines.index("  hw:reads:")
        description = next(line for line in lines[start:] if line.strip().startswith("desc:"))
        self.assertIn("derating policy, pin-limit, board rules and manufacturer limits records", description)


class EveryTrackedDesignCarriesTheRecordsTheRulesRead(World):
    def test_the_designs_reads_list_the_derating_policy_and_pin_limit_records_wherever_they_sit(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C6: A change to a design's board files or to any record these rules read re-runs the board tier of the build round.
        import subprocess
        self.build([CAP, IC], cap_on_rails(), limits=[IC_LIMITS])
        self.write(self.design.schematic, "(kicad_sch (version 20250114))\n")
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hw/machine/derating-policy.yaml", reads)
        self.assertIn("hw/machine/pin-limits.yaml", reads)

    def test_every_tracked_proof_design_carries_a_class_on_each_position_and_a_pin_limit_entry_for_each_chip(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C6: Every design git tracks passes the derated-voltage rule and the pin-limit rule, carrying the records they read, synthetic where the design is not for manufacture.
        files = board_check.tracked_files("git", REPO)
        repository = board_check.Repository(REPO, files)
        designs, _, _ = board_check.discover(REPO, files)
        self.assertGreaterEqual(len(designs), 5)
        for design in designs:
            with self.subTest(design=design.project):
                stated, problems = board_check.read_specification(self.yaml, REPO, repository, design, True)
                self.assertEqual(problems, [])
                self.assertEqual([ref for ref, entry in stated.items() if "class" not in entry], [])
                limits, problems = board_check.load_pin_limits(self.yaml, REPO, repository, design, True)
                self.assertEqual(problems, [])
                held = {str(part["lcsc"]) for part in limits["parts"]}
                placed, _, _ = board_check.placed_positions(REPO, design, repository)
                chips = {ref: info["lcsc"] for ref, info in placed.items()
                         if board_check.part_kind(ref, info["value"]) in (board_check.INTEGRATED_CIRCUIT, board_check.SEMICONDUCTOR)}
                self.assertEqual({ref for ref, lcsc in chips.items() if lcsc not in held}, set())


class TheRulesAreCalledFromTheDesignCheck(World):
    """check_design run on a synthetic design with KiCad's reports stood in for, so no KiCad is needed."""

    NETLIST = """(export (version "E")
  (components (comp (ref "U1") (libsource (lib "Device") (part "X"))) (comp (ref "C1") (libsource (lib "Device") (part "X"))))
  (nets
    (net (code 1) (name "/+5V") (node (ref "U1") (pin "1") (pinfunction "VDD_1")) (node (ref "C1") (pin "1")))
    (net (code 2) (name "/GND") (node (ref "C1") (pin "2")))))
"""

    def test_a_violation_of_either_rule_reaches_the_design_checks_report(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C3: The rules extend the existing pre-order check and its record reader.
        self.write(self.design.project, json.dumps({"text_variables": {"MAINS": "none", "NOT_FOR_MANUFACTURE": "true"}}))
        self.write(self.design.layout, "(kicad_pcb (version 20250114))\n")
        self.build([IC, ("C1", "x", "C100", "6V", "capacitor")], {"/+5V": pins(("U1", "1", "VDD_1"), ("C1", "1", "")), "/GND": pins(("C1", "2", ""))},
                   limits=[limit_part("C200", ("1", "five", 3, 0, False))], mains="none", mains_nets=())
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/") for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)

        def kicad_report(command, cwd):
            return ({"sheets": []}, "") if "erc" in command else (None, "stood in")

        with mock.patch.object(board_check, "run_report", kicad_report), \
                mock.patch.object(board_check, "run_kicad", lambda command, cwd, output="report.json": (self.NETLIST, "")):
            found = board_check.check_design(self.design, repository, "kicad-cli", self.yaml, datetime.date(2026, 10, 20), [])
        rules = {(v.rule, v.location) for v in found if v.rule in ("pin_limit", "derated_voltage")}
        self.assertIn(("pin_limit", f"{self.design.schematic} U1 pin 1"), rules)
        self.assertIn(("derated_voltage", f"{self.design.schematic} C1"), rules)


if __name__ == "__main__":
    unittest.main()
