#!/usr/bin/env python3
"""What the pre-order check measures for itself rather than takes from KiCad's cut report lists, driven on synthetic layouts with no KiCad involved.

KiCad's command-line layout check cuts each list it reports, and which lines it
cuts changes from run to run. The pad pairs of one part on two Mains-class nets,
and the fill of every Mains-class zone, are therefore measured here from the
layout file; these tests feed the judgement a KiCad report that omits, repeats
or words differently the lines for the pairs, and read the zone rules over
zones written the way KiCad writes them.
"""

from __future__ import annotations

import datetime
import math
import os
import re
import sys
import tempfile
import unittest
import unittest.mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import sexpr  # noqa: E402

TODAY = datetime.date(2026, 10, 12)
RECORD = "hardware/m/separation-basis.yaml"
DESIGN = board_check.Design("hardware/m/board/board.kicad_pro")
TERMINAL = board_check.TERMINAL_RULE
MAINS = {"/MAINS_L", "/MAINS_N", "/MAINS_X"}


def entry(between, accepted_mm, constraint="clearance", **changes) -> dict:
    held = {"pair": "mains_to_mains", "constraint": constraint, "between": list(between), "accepted_mm": accepted_mm,
            "reason": "a synthetic ground", "bounded_by": "a synthetic independent element",
            "accepted_by": "maintainer", "accepted_on": "2026-10-01"}
    held.update(changes)
    return held


def signed_record(*entries, reinforced=()):
    """What read_record makes of a mains-present synthetic record accepting `entries`."""
    import yaml
    data = {
        "standard": "synthetic", "supply": "230 V", "working_voltage": "250 V rms", "pollution_degree": 2, "material_group": "IIIb",
        "environment": "indoors", "overvoltage_category": 2, "altitude_m": 2000, "barriers": [], "barrier_types": [],
        "mains_to_low_voltage": {"clearance_mm": 3.0, "creepage_mm": 14.0},
        "mains_to_mains": {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 2.5,
                           "creepage_ahead_of_fuse_mm": 2.5, "entry_fuse": "F1", "held_at_reinforced": [list(p) for p in reinforced]},
        "accepted_exceptions": list(entries), "accepted_by": "maintainer", "accepted_on": "2026-10-05", "synthetic": True}
    with tempfile.TemporaryDirectory() as folder:
        os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
        with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
            handle.write(yaml.safe_dump(data))
        signed, problems = board_check.read_record(yaml, folder, DESIGN, RECORD, True, TODAY)
    assert problems == [], [problem.line() for problem in problems]
    return signed


def pad(number, x, y, net, size=(1.0, 1.0), shape="rect", layers='"F.Cu"', kind="smd", angle=None, more="") -> str:
    turn = f" {angle}" if angle is not None else ""
    return (f'(pad "{number}" {kind} {shape} (at {x} {y}{turn}) (size {size[0]} {size[1]}) (layers {layers}) '
            f'(net "{net}") {more})')


def layout(*parts, zones="") -> list:
    """A layout of footprints, each (reference, [pads]) at the board's origin."""
    text = "(kicad_pcb (layers (0 \"F.Cu\" signal) (31 \"B.Cu\" signal))"
    for reference, pads in parts:
        text += f' (footprint "F" (layer "F.Cu") (at 0 0) (property "Reference" "{reference}") {" ".join(pads)})'
    return sexpr.parse_one(text + zones + ")")


def report_line(reference, first, second, actual, rule=TERMINAL, figure=2.0, nets=("/MAINS_L", "/MAINS_N")) -> dict:
    """A clearance line as KiCad's JSON report writes it for two surface-mount pads of one part."""
    return {"type": "clearance", "severity": "error",
            "description": f"Clearance violation (rule '{rule}' clearance {figure:.4f} mm; actual {actual:.4f} mm)",
            "items": [{"description": f"Pad {first} [{nets[0]}] of {reference} on F.Cu", "pos": {"x": 0, "y": 0}},
                      {"description": f"Pad {second} [{nets[1]}] of {reference} on F.Cu", "pos": {"x": 1, "y": 1}}]}


def two_pads(gap, **changes) -> list:
    """A part whose two 1 mm square pads, on two Mains nets, stand `gap` mm apart edge to edge."""
    return layout(("R1", [pad(1, 0, 0, "/MAINS_L", **changes), pad(2, 1.0 + gap, 0, "/MAINS_N", **changes)]))


def measured(tree, signed=None, mains=MAINS):
    return board_check.same_part_pad_pairs(DESIGN, tree, set(mains), signed or signed_record())


class SamePartPairsAreMeasured(unittest.TestCase):
    def test_a_pair_under_the_pad_to_pad_figure_is_found_with_no_line_from_kicad(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        found, problems = measured(two_pads(1.8))
        self.assertEqual(problems, [])
        (one,) = found
        self.assertEqual(one["type"], "clearance")
        self.assertEqual(one["description"], f"Clearance violation (rule '{TERMINAL}' clearance 2.0000 mm; actual 1.8000 mm)")
        self.assertEqual([item["description"] for item in one["items"]],
                         ["Pad 1 [/MAINS_L] of R1 on F.Cu", "Pad 2 [/MAINS_N] of R1 on F.Cu"])
        # with KiCad's list silent on the pair it is an ordinary clearance violation of the check's own finding
        merged = board_check.with_measured_pad_pairs([], found)
        self.assertEqual(board_check.judge_exceptions(DESIGN, RECORD, signed_record(), merged, two_pads(1.8), TODAY).violations, [])
        self.assertEqual([board_check.kicad_violation(DESIGN, line, "x").rule for line in merged], ["clearance"])

    def test_a_pair_at_or_over_the_figure_is_not_found(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        for gap in (2.0, 2.0000004, 2.5, 40.0):
            with self.subTest(gap=gap):
                self.assertEqual(measured(two_pads(gap)), ([], []))

    def test_the_pads_true_shape_is_measured_not_its_box(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        diagonal = lambda shape, ratio: layout(("R1", [pad(1, 0, 0, "/MAINS_L", shape=shape, more=f"(roundrect_rratio {ratio})"),
                                                       pad(2, 2.0, 2.0, "/MAINS_N", shape=shape, more=f"(roundrect_rratio {ratio})")]))
        # two circles of 1 mm diameter 2.83 mm apart centre to centre stand 1.83 mm apart; two squares, 1.41 mm
        for shape, ratio, actual in (("circle", 0.25, "1.8284"), ("roundrect", 0.5, "1.8284"), ("rect", 0.25, "1.4142")):
            with self.subTest(shape=shape):
                (found,), _ = measured(diagonal(shape, ratio))
                self.assertIn(f"actual {actual} mm", found["description"])
        # an oval is a stadium: two 2 x 1 ovals end to end, 1.9 mm apart
        ovals = layout(("R1", [pad(1, 0, 0, "/MAINS_L", size=(2.0, 1.0), shape="oval"),
                               pad(2, 3.9, 0, "/MAINS_N", size=(2.0, 1.0), shape="oval")]))
        (found,), _ = measured(ovals)
        self.assertIn("actual 1.9000 mm", found["description"])

    def test_a_turned_pad_is_measured_as_it_lies_on_the_board(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        # the 2 x 0.5 pad turned a quarter lies 0.5 wide along x: its near edge is 2.25 from the centre of the 1 mm square beside it
        turned = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 2.5, 0, "/MAINS_N", size=(2.0, 0.5), angle=90)]))
        (found,), _ = measured(turned)
        self.assertIn("actual 1.7500 mm", found["description"])
        straight = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 2.5, 0, "/MAINS_N", size=(2.0, 0.5))]))
        (found,), _ = measured(straight)
        self.assertIn("actual 1.0000 mm", found["description"])

    def test_only_pads_sharing_a_copper_layer_are_paired(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        opposite = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 1.8 + 1.0, 0, "/MAINS_N", layers='"B.Cu"')]))
        self.assertEqual(measured(opposite), ([], []))
        # a through-hole pad has copper on every layer, so it shares the back with a back pad
        through = layout(("R1", [pad(1, 0, 0, "/MAINS_L", kind="thru_hole", shape="circle", layers='"*.Cu"'),
                                 pad(2, 2.3, 0, "/MAINS_N", layers='"B.Cu"')]))
        (found,), _ = measured(through)
        self.assertEqual(found["items"][0]["description"], "PTH pad 1 [/MAINS_L] of R1")
        self.assertEqual(found["items"][1]["description"], "Pad 2 [/MAINS_N] of R1 on B.Cu")

    def test_pads_of_one_net_of_a_low_voltage_net_or_of_two_parts_are_not_paired(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        same_net = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 1.8 + 1.0, 0, "/MAINS_L")]))
        low = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 1.8 + 1.0, 0, "/LV")]))
        apart_parts = layout(("R1", [pad(1, 0, 0, "/MAINS_L")]), ("R2", [pad(2, 1.8 + 1.0, 0, "/MAINS_N")]))
        for name, tree in (("one net", same_net), ("low voltage", low), ("two parts", apart_parts)):
            with self.subTest(name):
                self.assertEqual(measured(tree), ([], []))

    def test_a_pad_whose_copper_is_not_sized_fails_naming_it_where_it_has_a_mains_neighbour(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        for more, shape in (("", "custom"), ("(chamfer top_left)(chamfer_ratio 0.2)", "rect"), ("(primitives)", "rect")):
            with self.subTest(shape=shape, more=more):
                tree = layout(("R1", [pad(1, 0, 0, "/MAINS_L", shape=shape, more=more), pad(2, 5, 0, "/MAINS_N")]))
                found, problems = measured(tree)
                self.assertEqual(found, [])
                (problem,) = problems
                self.assertEqual(problem.rule, board_check.PAD_PAIR_RULE)
                self.assertIn("Pad 1 [/MAINS_L] of R1", problem.location)
                self.assertIn("cannot be measured", problem.message)
        # alone in its part, or beside only its own net, it has nothing to be measured against
        alone = layout(("R1", [pad(1, 0, 0, "/MAINS_L", shape="custom"), pad(2, 5, 0, "/MAINS_L"), pad(3, 9, 0, "/LV")]))
        self.assertEqual(measured(alone), ([], []))

    def test_a_pair_on_nets_held_at_reinforced_is_held_to_the_larger_figure_and_no_exception_excuses_it(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        signed = signed_record(entry(("R1.1", "R1.2"), 2.0 - 0.5), reinforced=[("/MAINS_X", "/MAINS_L")])
        tree = layout(("R1", [pad(1, 0, 0, "/MAINS_L"), pad(2, 3.5, 0, "/MAINS_X")]))
        (found,), _ = measured(tree, signed)
        self.assertEqual(found["description"],
                         f"Clearance violation (rule '{board_check.REINFORCED_RULE} 1' clearance 3.0000 mm; actual 2.5000 mm)")
        judged = board_check.judge_exceptions(DESIGN, RECORD, signed, [found], tree, TODAY)
        self.assertEqual(judged.accepted, [])
        self.assertEqual(judged.consumed, set())
        self.assertTrue(any("reports no shortfall" in v.message for v in judged.violations))


class SamePartPairsAreJudgedOnTheCheckOwnMeasurement(unittest.TestCase):
    def judge(self, gap, accepted, kicad=()):
        tree = two_pads(gap)
        signed = signed_record(entry(("R1.1", "R1.2"), accepted))
        found, _ = measured(tree, signed)
        merged = board_check.with_measured_pad_pairs(list(kicad), found)
        return board_check.judge_exceptions(DESIGN, RECORD, signed, merged, tree, TODAY), merged

    def test_an_entry_covering_the_pair_accepts_it_whether_or_not_kicad_lists_it(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C2: A signed same-part clearance entry is judged against the check's own measurement of its pad pair, and the verdict does not change with what the rule engine lists
        for name, kicad in (("kicad silent", []), ("kicad lists it", [report_line("R1", 2, 1, 1.8)]),
                            ("kicad lists it the other way round", [report_line("R1", 1, 2, 1.8)])):
            with self.subTest(name):
                judged, merged = self.judge(1.8, 1.8, kicad)
                self.assertEqual(judged.violations, [])
                (line,) = judged.accepted
                self.assertIn("mains_to_mains clearance between R1.1 and R1.2", line)
                self.assertIn("measures 1.8 mm, accepted down to 1.8 mm against the signed 2 mm", line)
                # the pair is one finding: the entry has taken it and nothing of it is left to be an ordinary violation
                self.assertEqual([found for found in merged if id(found) not in judged.consumed], [])

    def test_a_pair_both_found_and_listed_is_reported_once(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C1: A same-part mains pad pair nearer than the signed pad-to-pad clearance is found by the check's own measurement, whether or not the rule engine's list names it
        found, _ = measured(two_pads(1.8))
        listed = [report_line("R1", 2, 1, 1.7999), report_line("R1", 1, 2, 1.8)]
        # a second part's pair KiCad lists and the check does not measure as short is kept as KiCad words it
        other = report_line("R9", 1, 2, 0.5)
        merged = board_check.with_measured_pad_pairs(listed + [other], found)
        self.assertEqual(sorted(line["items"][0]["description"] for line in merged),
                         ["Pad 1 [/MAINS_L] of R1 on F.Cu", "Pad 1 [/MAINS_L] of R9 on F.Cu"])
        unjudged = [board_check.kicad_violation(DESIGN, line, "x") for line in merged]
        self.assertEqual(len([v for v in unjudged if "R1" in v.location]), 1)
        self.assertEqual(len([v for v in unjudged if "R9" in v.location]), 1)

    def test_an_entry_asking_more_than_the_measured_gap_fails_naming_the_entry_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C2: A signed same-part clearance entry is judged against the check's own measurement of its pad pair, and the verdict does not change with what the rule engine lists
        for name, kicad in (("kicad silent", []), ("kicad lists it", [report_line("R1", 1, 2, 1.8)])):
            with self.subTest(name):
                judged, _ = self.judge(1.8, 1.9, kicad)
                self.assertEqual(judged.accepted, [])
                (found,) = judged.violations
                self.assertEqual(found.rule, "spacing_exception")
                self.assertTrue(found.location.endswith("accepted_exceptions[0]"), found.location)
                for words in ("down to 1.9 mm", "leaves 1.8 mm"):
                    self.assertIn(words, found.message)

    def test_an_entry_for_a_pair_the_layout_has_since_moved_apart_covers_no_shortfall(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C2: A signed same-part clearance entry is judged against the check's own measurement of its pad pair, and the verdict does not change with what the rule engine lists
        judged, _ = self.judge(2.2, 1.8)
        self.assertEqual(judged.accepted, [])
        (found,) = judged.violations
        self.assertIn("reports no shortfall", found.message)

    def test_an_entry_no_less_than_the_figure_relaxes_nothing(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C2: A signed same-part clearance entry is judged against the check's own measurement of its pad pair, and the verdict does not change with what the rule engine lists
        judged, _ = self.judge(1.8, 2.0)
        (found,) = judged.violations
        self.assertIn("relaxes nothing", found.message)

    def test_twelve_entries_are_each_accepted_whatever_subset_of_their_lines_kicad_lists(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C2: A signed same-part clearance entry is judged against the check's own measurement of its pad pair, and the verdict does not change with what the rule engine lists
        # four resistors with two pads each and two three-pad parts whose middle pad stands 0.76 from either end pad
        parts = [(f"R{n}", [pad(1, 0, 0, "/MAINS_L"), pad(2, 2.8, 0, "/MAINS_N")]) for n in (101, 102, 103, 104)]
        parts += [(f"U{n}", [pad(4, 0, 0, "/MAINS_L", size=(0.5, 1.0)), pad(5, 1.26, 0, "/MAINS_X", size=(0.5, 1.0)),
                             pad(6, 2.52, 0, "/MAINS_N", size=(0.5, 1.0))]) for n in (701, 711)]
        tree = layout(*parts)
        entries = ([entry((f"R{n}.1", f"R{n}.2"), 1.8) for n in (101, 102, 103, 104)]
                   + [entry((f"U{n}.5", f"U{n}.{end}"), 0.76) for n in (701, 711) for end in (4, 6)])
        signed = signed_record(*entries)
        found, problems = measured(tree, signed)
        self.assertEqual((len(found), problems), (8, []))
        every = [report_line(f"R{n}", 1, 2, 1.8) for n in (101, 102, 103, 104)] + [
            report_line(f"U{n}", 5, end, 0.76, nets=("/MAINS_X", "/MAINS_L" if end == 4 else "/MAINS_N")) for n in (701, 711) for end in (4, 6)]
        verdicts = []
        for dropped in [()] + [(index,) for index in range(len(every))] + [tuple(range(len(every)))]:
            listed = [line for index, line in enumerate(every) if index not in dropped]
            judged = board_check.judge_exceptions(DESIGN, RECORD, signed, board_check.with_measured_pad_pairs(listed, found), tree, TODAY)
            self.assertEqual(judged.violations, [], dropped)
            verdicts.append(sorted(judged.accepted))
        self.assertEqual(len(verdicts[0]), 8)
        self.assertTrue(all(verdict == verdicts[0] for verdict in verdicts), "the accepted lines changed with what KiCad listed")


class AZoneClearanceOfZeroIsNone(unittest.TestCase):
    def overrides(self, written: str):
        tree = sexpr.parse_one(f'(kicad_pcb (zone (net "/MAINS_N") (connect_pads {written}) (min_thickness 0.2)))')
        return board_check.overrides(DESIGN, tree, 3.0, {"/MAINS_N"})

    def test_zero_and_no_clearance_are_no_local_clearance(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C3: A zone clearance written as 0 is read as no local clearance
        for written in ("yes (clearance 0)", "yes (clearance 0.0)", "yes", "(clearance 0)", "yes (clearance 3)", "yes (clearance 3.5)"):
            with self.subTest(written=written):
                self.assertEqual(self.overrides(written), [])

    def test_a_real_clearance_below_the_signed_figure_still_fails(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C3: A zone clearance written as 0 is read as no local clearance
        for written in ("yes (clearance 0.5)", "yes (clearance 0.01)", "yes (clearance 2.9)"):
            with self.subTest(written=written):
                (found,) = self.overrides(written)
                self.assertEqual(found.rule, "local_clearance_override")
                self.assertIn("below the signed 3 mm", found.message)

    def test_a_zone_off_the_mains_class_is_not_read(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C3: A zone clearance written as 0 is read as no local clearance
        tree = sexpr.parse_one('(kicad_pcb (zone (net "/LV") (connect_pads yes (clearance 0.5))))')
        self.assertEqual(board_check.overrides(DESIGN, tree, 3.0, {"/MAINS_N"}), [])


def square(side_x, side_y, x=0.0, y=0.0) -> str:
    return f"(xy {x} {y}) (xy {x + side_x} {y}) (xy {x + side_x} {y + side_y}) (xy {x} {y + side_y})"


def zone(net="/MAINS_N", layers='(layer "F.Cu")', name="pour", outline=None, fills=(), extra="") -> str:
    """A zone as KiCad writes it: its outline and, per layer, the polygons it filled."""
    outline = outline if outline is not None else f"(polygon (pts {square(10, 10)}))"
    text = f'(zone (net "{net}") {layers} (name "{name}") {extra} {outline}' if name else f'(zone (net "{net}") {layers} {extra} {outline}'
    for layer, points in fills:
        text += f' (filled_polygon (layer "{layer}") (pts {points}))'
    return text + ")"


def fill_check(*zones: str, mains=("/MAINS_N",)):
    tree = sexpr.parse_one('(kicad_pcb (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) ' + " ".join(zones) + ")")
    return board_check.mains_zone_fill(DESIGN, tree, set(mains))


class AMainsZoneMustFill(unittest.TestCase):
    def test_a_zone_filled_to_its_outline_passes(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        self.assertEqual(fill_check(zone(fills=[("F.Cu", square(10, 10))])), [])
        self.assertEqual(fill_check(zone(fills=[("F.Cu", square(9.75, 10))])), [])
        self.assertEqual(fill_check(zone(fills=[("F.Cu", square(9.6, 10))])), [])
        self.assertEqual(fill_check(zone(fills=[("F.Cu", square(9.0, 10))])), [])

    def test_a_fill_of_89_percent_fails_naming_the_zone_the_layer_and_the_fraction(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        (found,) = fill_check(zone(name="neutral tap", fills=[("F.Cu", square(8.9, 10))]))
        self.assertEqual(found.rule, "mains_zone_fill")
        self.assertIn("zone neutral tap [/MAINS_N] on F.Cu", found.location)
        self.assertIn("fills 0.890 of its 100.00 mm2 outline on F.Cu", found.message)

    def test_an_empty_fill_fails_and_a_zone_without_a_name_is_named_by_its_net(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        (found,) = fill_check(zone(name=None))
        self.assertTrue(found.location.endswith("zone [/MAINS_N] on F.Cu"), found.location)
        self.assertIn("fills 0.000 of its", found.message)
        # a fill on another layer is no fill on this one
        (found,) = fill_check(zone(fills=[("B.Cu", square(10, 10))]))
        self.assertIn("on F.Cu", found.location)

    def test_a_rule_area_and_a_zone_off_the_mains_class_are_not_judged(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        rule_area = zone(extra="(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed))")
        no_net = '(zone (layer "F.Cu") (name "keepout") (keepout (tracks not_allowed)) (polygon (pts ' + square(5, 5) + ')))'
        low_voltage = zone(net="/LV")
        self.assertEqual(fill_check(rule_area, no_net, low_voltage), [])

    def test_two_layers_are_judged_one_by_one(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        both = '(layers "F.Cu" "B.Cu")'
        (found,) = fill_check(zone(layers=both, fills=[("F.Cu", square(10, 10)), ("B.Cu", square(5, 10))]))
        self.assertIn("on B.Cu", found.location)
        self.assertIn("0.500", found.message)
        self.assertEqual(fill_check(zone(layers=both, fills=[("F.Cu", square(10, 10)), ("B.Cu", square(10, 10))])), [])
        found = fill_check(zone(layers=both, fills=[("F.Cu", square(10, 10))]))
        self.assertEqual([v.location.rsplit(" ", 1)[-1] for v in found], ["B.Cu"])

    def test_several_filled_polygons_of_a_layer_add_and_a_hole_bridged_into_one_is_taken_off(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        halves = [("F.Cu", square(5, 10)), ("F.Cu", square(5, 10, x=5))]
        self.assertEqual(fill_check(zone(fills=halves)), [])
        # the square with a 4 x 4 hole, joined to the outside by a bridge of no width, is 84 mm2 of 100
        ring = "(xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10) (xy 0 0) (xy 3 3) (xy 3 7) (xy 7 7) (xy 7 3) (xy 3 3)"
        (found,) = fill_check(zone(fills=[("F.Cu", ring)]))
        self.assertIn("fills 0.840", found.message)

    def test_an_outline_with_an_arc_is_measured_and_one_inside_another_is_a_hole(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        half_disc = "(polygon (pts (xy -5 0) (arc (start -5 0) (mid 0 5) (end 5 0))))"
        area = math.pi * 25 / 2
        points = " ".join(f"(xy {5 * math.cos(math.radians(a)):.6f} {5 * math.sin(math.radians(a)):.6f})" for a in range(0, 181))
        self.assertEqual(fill_check(zone(outline=half_disc, fills=[("F.Cu", points)])), [])
        halved = " ".join(f"(xy {x:.6f} {y:.6f})" for x, y in [(-5, 0), (-2.5, 0), (-2.5, 4.3), (-5, 4.3)])
        (found,) = fill_check(zone(outline=half_disc, fills=[("F.Cu", halved)]))
        stated = float(re.search(r"of its ([0-9.]+) mm2 outline", found.message).group(1))
        self.assertAlmostEqual(stated, area, delta=0.1)
        nested = f"(polygon (pts {square(10, 10)})) (polygon (pts {square(2, 2, 4, 4)}))"
        self.assertEqual(fill_check(zone(outline=nested, fills=[("F.Cu", "(xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10) (xy 0 0) (xy 4 4) (xy 4 6) (xy 6 6) (xy 6 4) (xy 4 4)")])), [])

    def test_an_outline_or_fill_that_cannot_be_read_fails_naming_the_zone_rather_than_being_skipped(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C4: A Mains-class zone whose fill covers less than 90 % of its outline on a layer fails the design, naming the zone, the layer and the fraction
        broken = "(polygon (pts (xy -5 0) (arc (start -5 0) (end 5 0))))"
        with self.assertRaises(board_geometry.Unreadable) as raised:
            fill_check(zone(name="neutral tap", outline=broken))
        self.assertIn("neutral tap", str(raised.exception))
        with self.assertRaises(board_geometry.Unreadable) as raised:
            fill_check(zone(name="neutral tap", fills=[("F.Cu", "(xy 0 0) (arc (start 0 0) (mid 1 1) (end 2 0)) (xy 3 3)")]))
        self.assertIn("neutral tap", str(raised.exception))
        with self.assertRaises(board_geometry.Unreadable):
            fill_check(zone(outline=""))


NONCE = "abc123"


def lines_of(kind, count, rule="x"):
    return [{"type": kind, "description": f"{kind} violation (rule '{rule}')", "items": [{"description": f"Track #{n}"}]} for n in range(count)]


class ACutListIsNotAVerdict(unittest.TestCase):
    def test_a_clearance_list_of_the_cap_or_more_fails_naming_the_pass_and_the_count(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C5: A rule engine list cut at its cap on a pass that carries a Mains rule fails the design
        for count in (board_check.CLEARANCE_REPORT_LIMIT, board_check.CLEARANCE_REPORT_LIMIT + 7):
            with self.subTest(count=count):
                (found,) = board_check.cut_lists(DESIGN, {"violations": lines_of("clearance", count)}, "first run")
                self.assertEqual(found.rule, "report_cut_short")
                self.assertIn(f"list of clearance lines in the first run holds {count}", found.message)
                self.assertIn("a cut list is not a verdict", found.message)

    def test_a_list_one_under_the_cap_passes_and_other_kinds_do_not_count_toward_it(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C5: A rule engine list cut at its cap on a pass that carries a Mains rule fails the design
        report = {"violations": lines_of("clearance", board_check.CLEARANCE_REPORT_LIMIT - 1) + lines_of("silk_overlap", 600)
                  + lines_of("creepage", board_check.REPORT_LIMIT - 1)}
        self.assertEqual(board_check.cut_lists(DESIGN, report, "creepage pass"), [])
        self.assertEqual(board_check.cut_lists(DESIGN, {}, "creepage pass"), [])

    def test_a_creepage_or_hole_list_at_the_other_limit_fails_and_each_cut_list_is_named_once(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C5: A rule engine list cut at its cap on a pass that carries a Mains rule fails the design
        report = {"violations": lines_of("creepage", board_check.REPORT_LIMIT) + lines_of("hole_clearance", board_check.REPORT_LIMIT)
                  + lines_of("clearance", 3)}
        found = board_check.cut_lists(DESIGN, report, "mounting-hole pass")
        self.assertEqual(sorted(v.message.split(" lines")[0].rsplit(" ", 1)[-1] for v in found), ["creepage", "hole_clearance"])


class ThePadPairRunIsReadOnceAndLeavesTheRestToTheFirst(unittest.TestCase):
    def run_pass(self, report, rules="(version 1)\n"):
        with tempfile.TemporaryDirectory() as scratch:
            path = os.path.join(scratch, "m.kicad_dru")
            with unittest.mock.patch.object(board_check, "run_report", return_value=(report, "")) as called:
                found = board_check.pad_pair_pass("kicad-cli", DESIGN, scratch, "m.kicad_pcb", path, rules, signed_record(), NONCE, None)
            with open(path, encoding="utf-8") as handle:
                written = handle.read()
            return found, written, called.call_args[0][0]

    def marker(self):
        return {"type": "assertion_failure", "description": f"Rule violation (rule '{board_check.marker_rule(NONCE)}')", "items": []}

    def test_only_the_lines_of_the_checks_terminal_and_reinforced_rules_are_taken_and_nothing_is_refilled(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C6: The mains clearance findings of the first pass are gathered in runs that each stay under the rule engine's cap, and each finding is reported once
        terminal = report_line("R1", 1, 2, 1.0)
        reinforced = report_line("R2", 1, 2, 1.0, rule=f"{board_check.REINFORCED_RULE} 1")
        other = report_line("R3", 1, 2, 0.1, rule="the design's own")
        (lines, problems), written, command = self.run_pass({"violations": [self.marker(), terminal, other, reinforced]})
        self.assertEqual(problems, [])
        self.assertEqual(lines, [terminal, reinforced])
        self.assertNotIn("--refill-zones", command)
        self.assertNotIn("--save-board", command)
        self.assertIn(board_check.OTHER_PAIRS_SILENCED_RULE, written)
        self.assertNotIn(board_check.PAD_PAIRS_SILENCED_RULE, written)
        self.assertNotIn("creepage", written.replace(board_check.RESERVED, ""))
        self.assertTrue(written.index(board_check.marker_rule(NONCE)) < written.index(board_check.OTHER_PAIRS_SILENCED_RULE))
        self.assertTrue(written.rstrip().endswith("(constraint clearance (min 0mm)))"))

    def test_a_run_that_did_not_load_its_rules_or_could_not_run_or_was_cut_fails_the_design(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C6: The mains clearance findings of the first pass are gathered in runs that each stay under the rule engine's cap, and each finding is reported once
        (lines, problems), _, _ = self.run_pass({"violations": [report_line("R1", 1, 2, 1.0)]})
        self.assertEqual((lines, [v.rule for v in problems]), ([], ["custom_rules"]))
        with tempfile.TemporaryDirectory() as scratch, unittest.mock.patch.object(board_check, "run_report", return_value=(None, "no report")):
            lines, problems = board_check.pad_pair_pass("kicad-cli", DESIGN, scratch, "m.kicad_pcb", os.path.join(scratch, "m.kicad_dru"),
                                                        "(version 1)\n", signed_record(), NONCE, None)
        self.assertEqual((lines, [v.rule for v in problems]), ([], ["design_unreadable"]))
        (lines, problems), _, _ = self.run_pass({"violations": [self.marker()] + lines_of("clearance", board_check.CLEARANCE_REPORT_LIMIT)})
        self.assertEqual([v.rule for v in problems], ["report_cut_short"])
        self.assertIn("pad-pair run", problems[0].message)

    def test_the_two_silencing_rules_split_the_pairs_between_the_runs_and_come_last(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C6: The mains clearance findings of the first pass are gathered in runs that each stay under the rule engine's cap, and each finding is reported once
        pads = board_check.pad_pairs_silenced()
        rest = board_check.other_pairs_silenced()
        self.assertIn(board_check.TERMINAL_CONDITION, pads)
        self.assertIn("A.Type != 'Pad' || B.Type != 'Pad'", rest)
        for text in (pads, rest):
            self.assertIn("(constraint clearance (min 0mm))", text)
            self.assertEqual(text.count("(rule "), 1)

    def test_a_line_both_runs_list_is_one_finding(self):
        # SOL-PRE-ORDER-CHECK-MEASURES-SAME-PART-MAINS-PAD-PAIRS-AND-MAINS-ZONE-FILL-ITSELF.C6: The mains clearance findings of the first pass are gathered in runs that each stay under the rule engine's cap, and each finding is reported once
        one, two, three = report_line("R1", 1, 2, 1.0), report_line("R2", 1, 2, 0.9), report_line("R3", 1, 2, 0.8)
        self.assertEqual(board_check.joined_once([one, two], [two, three, three, dict(one)]), [one, two, three])
        self.assertEqual(board_check.joined_once([], []), [])


if __name__ == "__main__":
    unittest.main()
