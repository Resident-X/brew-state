"""The committed separation basis record of the Sunbeam EM7000 machine, read by the board check's own reader."""
from __future__ import annotations

import datetime
import fractions
import math
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import board_check  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
RECORD = os.path.join("hardware", "sunbeam-em7000", board_check.RECORD_NAME)
DESIGN = board_check.Design(os.path.join("hardware", "sunbeam-em7000", "board", "board.kicad_pro"))
TODAY = datetime.date(2026, 10, 23)
#: How many entries the record held before the net-pair and same-part entries were appended after them; the earlier leaves' tests read these.
ORIGINAL_ENTRIES = 25
#: The opto-triacs whose unconnected pin 5 has two same-part pairs each, appended after the set N pairs and held to the full mains figures.
NO_CONNECT_PART_REFS = ("U701", "U711")


def committed():
    import yaml
    with open(os.path.join(ROOT, RECORD), encoding="utf-8") as handle:
        return yaml, board_check.strict_yaml(yaml, handle.read())


def reading(data=None):
    """What read_record finds of the committed record, or of `data` written in its place, in a temporary folder."""
    import tempfile
    import yaml
    with tempfile.TemporaryDirectory() as folder:
        name = os.path.join("hardware", "sunbeam-em7000", board_check.RECORD_NAME)
        os.makedirs(os.path.join(folder, os.path.dirname(name)))
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            if data is None:
                with open(os.path.join(ROOT, RECORD), encoding="utf-8") as source:
                    handle.write(source.read())
            else:
                yaml.safe_dump(data, handle)
        return board_check.read_record(yaml, folder, DESIGN, name, False, TODAY)


def signed_from(data):
    pair = data["mains_to_low_voltage"]
    return board_check.Signed(float(pair["clearance_mm"]), float(pair["creepage_mm"]), data)


def assert_draft(case, data):
    """The record is a draft: no record-level acceptance, and every exception's two acceptance fields empty strings."""
    case.assertNotIn("accepted_by", data)
    case.assertNotIn("accepted_on", data)
    for entry in data["accepted_exceptions"]:
        case.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""), entry.get("between") or entry.get("connector") or entry.get("nets_a"))


class SeparationBasisRecord(unittest.TestCase):
    def test_only_the_unsigned_acceptance_is_left_to_find(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C9: The committed record holds no accepted_by and no accepted_on at its top level, no entry of its accepted_exceptions holds a signed acceptance, and the check's own reader finds the unsigned acceptance as the only problem with the record. The test never writes an acceptance into the record. Out of scope is the owner's acceptance, which is its own leaf.
        yaml, data = committed()
        self.assertIsNot(data.get("synthetic"), True)
        _, problems = reading()
        left = [p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))]
        self.assertEqual(left, [], [p.line() for p in left])
        # the draft state is pinned: the owner-acts leaf SOL-SEPARATION-BASIS-RECORD-MAINS-TO-MAINS-ACCEPTED-BY-OWNER changes this assertion when the owner accepts
        assert_draft(self, data)
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("unsigned" in p.message for p in problems))
        self.assertTrue(all(entry["accepted_by"] == "" and entry["accepted_on"] == "" for entry in data["accepted_exceptions"]))

    def test_every_barrier_has_exactly_one_type_and_the_floor_holds_on_its_own_figures(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry, giving its insulation type, basic or reinforced, whether its low-voltage side is bonded to protective earth, the low-voltage parts a person can touch beyond it (such as a service port, the operator's controls or the enclosure), and the part or spacing that forms it; The mains-to-low-voltage clearance and creepage are at or above the floor those rows give. It also runs the check's floor rule on the record's own figures taken as signed and finds no violation.
        _, data = committed()
        names = data["barriers"]
        self.assertEqual(sorted(entry["barrier"] for entry in data["barrier_types"]), sorted(names))
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed_from(data)), [])

    def test_a_figure_below_its_floor_is_caught_by_the_same_rule(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: The mains-to-low-voltage clearance and creepage are at or above the floor those rows give.
        _, data = committed()
        for key in ("clearance_mm", "creepage_mm"):
            low = dict(data, mains_to_low_voltage=dict(data["mains_to_low_voltage"], **{key: 0.5}))
            found = board_check.separation_floor(DESIGN, RECORD, signed_from(low))
            self.assertEqual(len(found), 1, key)
            self.assertIn(f"mains_to_low_voltage.{key}", found[0].location)

    def test_only_the_earth_referenced_sensor_barrier_is_basic_and_every_mains_barrier_is_reinforced(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry, giving its insulation type, basic or reinforced, whether its low-voltage side is bonded to protective earth, the low-voltage parts a person can touch beyond it (such as a service port, the operator's controls or the enclosure), and the part or spacing that forms it;
        _, data = committed()
        types = {entry["barrier"]: entry["insulation"] for entry in data["barrier_types"]}
        sensor = "pressure-sensor-water-path"
        self.assertEqual(types[sensor], "basic")
        mains = [name for name in types if name != sensor]
        self.assertEqual(len(mains), 8)
        self.assertEqual({types[name] for name in mains}, {"reinforced"}, types)
        entry = next(e for e in data["barrier_types"] if e["barrier"] == sensor)
        self.assertIn("referenced to earth through the earthed", entry["formed_by"])
        # the floor is still read at reinforced because mains barriers remain
        strongest = max(types.values(), key=board_check.STRENGTH.get)
        self.assertEqual(strongest, "reinforced")

    def test_the_record_states_the_inputs_the_figures_are_read_at(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: It states: the named standard, or a cited, freely available derivation of its tables; the declared supply, and the working voltage at the top of its span; the pollution degree, taken as 3 unless the boards are protected against moisture, and saying which; the material group, with its reason; the environment, with water, steam and repeated heating; the overvoltage category and the altitude; the barriers; only the table rows its own inputs select, never a whole table, each with its citation.
        _, data = committed()
        for key in ("standard", "supply", "working_voltage", "pollution_degree", "material_group", "environment",
                    "overvoltage_category", "altitude_m", "table_rows"):
            self.assertTrue(data.get(key), key)
        self.assertEqual(board_check.basis_voltage(data["working_voltage"]), 253.0)
        self.assertEqual(data["pollution_degree"], 2)
        for row in data["table_rows"]:
            self.assertTrue(all(row["citation"][k].strip() for k in board_check.CITATION_KEYS))
        strongest = max((entry["insulation"] for entry in data["barrier_types"]), key=board_check.STRENGTH.get)
        for row in data["table_rows"]:
            # a row of basic insulation is the floor of the mains-to-mains figures, so it is read at its own insulation; a functional band row sits below the supply voltage by design and is read by the net-pair band, not the floor
            if row["inputs"].get("insulation") != "functional":
                self.assertTrue(board_check.row_applies(row["inputs"], data, 253.0, row["inputs"].get("insulation", strongest)), row["inputs"])
            for key in ("overvoltage_category", "pollution_degree", "material_group", "altitude_m"):
                if key in row["inputs"]:
                    self.assertEqual(row["inputs"][key], data[key], key)

    def test_a_barrier_without_an_entry_is_refused(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry, giving its insulation type, basic or reinforced, whether its low-voltage side is bonded to protective earth, the low-voltage parts a person can touch beyond it (such as a service port, the operator's controls or the enclosure), and the part or spacing that forms it;
        _, data = committed()
        short = dict(data, barrier_types=data["barrier_types"][1:])
        _, problems = reading(short)
        self.assertTrue(any("holds no entry" in p.message for p in problems))

    def test_an_input_no_table_row_is_read_at_leaves_the_figure_without_a_floor(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: The mains-to-low-voltage clearance and creepage are at or above the floor those rows give.
        _, data = committed()
        low_clearance = ["mains_to_low_voltage.clearance_mm"]
        low_creepage = ["mains_to_low_voltage.creepage_mm"]
        mains_clearance = ["mains_to_mains.clearance_mm", "mains_to_mains.terminal_clearance_mm"]
        mains_creepage = ["mains_to_mains.creepage_mm", "mains_to_mains.creepage_ahead_of_fuse_mm"]
        # each mutation leaves the rows as drafted and changes the input they are read at; the keys are the figures left with no applicable row
        mutations = [("altitude_m", 3000, low_clearance + mains_clearance),
                     ("material_group", "IIIb", low_creepage + mains_creepage),
                     ("pollution_degree", 3, low_clearance + low_creepage + mains_clearance + mains_creepage),
                     ("overvoltage_category", 3, low_clearance + mains_clearance),
                     ("working_voltage", "400 V rms", low_clearance + low_creepage + mains_clearance + mains_creepage)]
        for key, value, figures in mutations:
            found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, **{key: value})))
            self.assertEqual(sorted(p.location.split(" ", 1)[1] for p in found), sorted(figures), key)
            self.assertTrue(all("no table row" in p.message for p in found), key)

    def test_an_input_the_floor_needs_and_the_record_lacks_is_refused(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: It states: the named standard, or a cited, freely available derivation of its tables; the declared supply, and the working voltage at the top of its span; the pollution degree, taken as 3 unless the boards are protected against moisture, and saying which; the material group, with its reason; the environment, with water, steam and repeated heating; the overvoltage category and the altitude; the barriers; only the table rows its own inputs select, never a whole table, each with its citation.
        _, data = committed()
        for key in ("overvoltage_category", "altitude_m"):
            found = board_check.separation_floor(DESIGN, RECORD, signed_from({k: v for k, v in data.items() if k != key}))
            self.assertEqual([p.location for p in found], [f"{RECORD} {key}"], key)
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, working_voltage="about 253 V")))
        self.assertEqual([p.location for p in found], [f"{RECORD} working_voltage"])

    def test_a_duplicate_or_incomplete_barrier_entry_is_refused(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry, giving its insulation type, basic or reinforced, whether its low-voltage side is bonded to protective earth, the low-voltage parts a person can touch beyond it (such as a service port, the operator's controls or the enclosure), and the part or spacing that forms it;
        _, data = committed()
        entries = data["barrier_types"]
        _, problems = reading(dict(data, barrier_types=entries + [dict(entries[0])]))
        self.assertTrue(any("already describes" in p.message for p in problems))
        for key in ("touchable", "formed_by", "insulation", "earth_bonded"):
            incomplete = [{k: v for k, v in entries[0].items() if k != key}] + entries[1:]
            _, problems = reading(dict(data, barrier_types=incomplete))
            self.assertTrue(any(key in p.message for p in problems), key)


class MainsToMainsRecord(unittest.TestCase):
    """The committed record's mains_to_mains figures, table rows and accepted exceptions, read through the check's own reader."""

    def test_the_mains_to_mains_mapping_holds_the_four_figures_and_the_entry_fuse(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C4: The committed record's mains_to_mains holds creepage_mm 2.6 and creepage_ahead_of_fuse_mm 2.6, clearance_mm 1.5, terminal_clearance_mm 2.0, entry_fuse F101 and the same held_at_reinforced pairs as before, and its mains_to_low_voltage holds clearance_mm 3.0 and creepage_mm 10.0. The check's own reader reads it with no problem other than the unsigned acceptance. Out of scope is any figure not named here.
        _, data = committed()
        assert_draft(self, data)
        held = data["mains_to_mains"]
        self.assertEqual({key: held[key] for key in ("clearance_mm", "terminal_clearance_mm", "creepage_mm", "creepage_ahead_of_fuse_mm")},
                         {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 2.6, "creepage_ahead_of_fuse_mm": 2.6})
        self.assertEqual(held["entry_fuse"], "F101")
        self.assertIn("held_at_reinforced", held)
        self.assertEqual((data["mains_to_low_voltage"]["clearance_mm"], data["mains_to_low_voltage"]["creepage_mm"]), (3.0, 10.0))
        self.assertEqual(board_check.read_mains_to_mains(DESIGN, RECORD, data), [])
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        for key in held:
            if key == "downstream_basis":
                continue
            without = dict(data, mains_to_mains={k: v for k, v in held.items() if k != key})
            _, problems = reading(without)
            self.assertTrue(any(f"mains_to_mains.{key}" in p.location or key in p.message for p in problems), key)

    def test_the_entry_fuse_must_be_a_reference_the_record_names_and_the_figures_stay_in_order(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C4: The committed record's mains_to_mains holds creepage_mm 2.6 and creepage_ahead_of_fuse_mm 2.6, clearance_mm 1.5, terminal_clearance_mm 2.0, entry_fuse F101 and the same held_at_reinforced pairs as before, and its mains_to_low_voltage holds clearance_mm 3.0 and creepage_mm 10.0. The check's own reader reads it with no problem other than the unsigned acceptance. Out of scope is any figure not named here.
        _, data = committed()
        held = data["mains_to_mains"]
        for key, value in (("entry_fuse", ""), ("clearance_mm", 0), ("creepage_mm", "2.6")):
            _, problems = reading(dict(data, mains_to_mains=dict(held, **{key: value})))
            self.assertTrue(any(f"mains_to_mains.{key}" in p.location for p in problems), key)
        _, problems = reading(dict(data, mains_to_mains=dict(held, terminal_clearance_mm=1.0)))
        self.assertTrue(any("terminal_clearance_mm" in p.location for p in problems))

    def test_every_figure_rests_on_a_cited_row_and_a_figure_below_its_floor_fails(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C5: The record's derived basic creepage row has working_voltage_v 253, pollution_degree 2 and material_group IIIa, figure creepage_mm 2.6, and a citation that names the 250 V row (2.5 mm) and the 320 V row (3.2 mm) of the pollution degree 2 material group III column of IEC 60664-1 Table F.4, the arithmetic giving 2.53 mm, the clause that allows the interpolation (IEC 60664-1:2007 clause 5.2.4), the 0.1 mm margin over the standard's own rounded 2.5 mm, and that the rows are read from reproductions and not from the standard. The citation keeps the fallback of the 320 V row, 3.2 mm, should the household-appliance standard refuse interpolation. Out of scope is the standard's own text.
        _, data = committed()
        rows = data["table_rows"]
        by = {}
        for row in rows:
            inputs = row["inputs"]
            by[(inputs.get("insulation"), inputs.get("location", "conductor"), tuple(sorted(row["figure"])))] = row
            self.assertTrue(all(row["citation"][key].strip() for key in board_check.CITATION_KEYS), row["inputs"])
        clearance = by[("basic", "conductor", ("clearance_mm",))]
        terminal = by[("basic", "terminal", ("clearance_mm",))]
        derived = by[("basic", "conductor", ("creepage_mm",))]
        self.assertEqual(sum(1 for row in rows if row["inputs"].get("insulation") == "basic" and "creepage_mm" in row["figure"]), 1)
        self.assertEqual(clearance["inputs"].get("working_voltage_v"), 300)
        self.assertIn("2.5 kV", clearance["citation"]["locator"])
        self.assertEqual(terminal["inputs"]["location"], "terminal")
        self.assertEqual(terminal["figure"]["clearance_mm"], 2.0)
        self.assertEqual(derived["inputs"]["working_voltage_v"], 253)
        self.assertEqual(derived["inputs"]["material_group"], data["material_group"])
        self.assertEqual(derived["figure"]["creepage_mm"], 2.6)
        self.assertEqual((derived["inputs"]["pollution_degree"], derived["inputs"]["material_group"]), (2, "IIIa"))
        cited = " ".join(derived["citation"].values())
        for phrase in ("250 V", "320 V", "2.5 mm", "3.2 mm", "2.5 + (3.2 - 2.5) x (253 - 250) / (320 - 250)", "2.53 mm", "clause 5.2.4", "0.1 mm",
                       "pollution degree 2", "reproductions", "not the standard"):
            self.assertIn(phrase, cited)
        # the floor rule finds nothing below its floor on the record's own figures, and each figure is held to its row
        signed = signed_from(data)
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed), [])
        for key, low in (("creepage_mm", 2.5), ("creepage_ahead_of_fuse_mm", 2.5), ("clearance_mm", 1.4), ("terminal_clearance_mm", 1.9)):
            held = dict(data["mains_to_mains"], **{key: low})
            if key == "clearance_mm":
                held["terminal_clearance_mm"] = 2.0
            found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=held)))
            self.assertEqual([p.location.split(" ", 1)[1] for p in found], [f"mains_to_mains.{key}"], key)
            self.assertIn("below the", found[0].message)
        # the figures at their floor pass
        at_floor = dict(data["mains_to_mains"], creepage_mm=2.6, creepage_ahead_of_fuse_mm=2.6, clearance_mm=1.5, terminal_clearance_mm=2.0)
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=at_floor))), [])
        # a row removed leaves its figure with no floor, which fails by name
        for position, row in enumerate(rows):
            if row in (clearance, terminal, derived):
                short = dict(data, table_rows=rows[:position] + rows[position + 1:])
                found = board_check.separation_floor(DESIGN, RECORD, signed_from(short))
                self.assertTrue(found and all("no table row" in p.message for p in found), position)

    def test_each_mains_to_mains_shortfall_the_owner_accepted_has_an_unsigned_entry(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C3: accepted_exceptions holds a mains_to_mains clearance entry with accepted_mm 1.08 for T701 and T711, one with 1.65 for R105 and one with 1.8 for each 1206 series resistor, every entry naming the one pair of pads or nets it excuses in between, with a reason and a bounding element, and its accepted_by and accepted_on left empty for the owner's acceptance. Each accepted_mm is below the signed figure it relaxes, a part's other pairs have no entry, and a part the owner did not accept has none. The mains-to-low-voltage entries are the next criterion's and out of scope here. The values are drafted from the schematic and the division record; confirming them against the main-board layout is the layout leaf's and out of scope here.
        _, data = committed()
        assert_draft(self, data)
        held = data["mains_to_mains"]
        entries = [e for e in data["accepted_exceptions"][:ORIGINAL_ENTRIES] if e["pair"] == "mains_to_mains" and e["constraint"] == "clearance"]
        found = {(tuple(e["between"]), e["accepted_mm"]) for e in entries}
        expected = {(("R105.1", "R105.4"), 1.65)}
        expected |= {((f"{ref}.1", f"{ref}.2"), 1.8) for ref in ("R101", "R102", "R103", "R104", "R704", "R705", "R714", "R715")}
        self.assertEqual(found, expected)
        self.assertEqual(len(entries), len(found))
        for entry in entries:
            self.assertEqual(entry["constraint"], "clearance")
            # below the figure it relaxes: the terminal clearance, which is what a pair of pads of one part is held to
            self.assertLess(entry["accepted_mm"], held["terminal_clearance_mm"])
            self.assertTrue(entry["reason"].strip() and entry["bounded_by"].strip())
            self.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""))
            self.assertEqual(len(entry["between"]), 2)
        # the triacs' two-lead land has no middle-lead pad, so no clearance entry names a triac pad
        self.assertFalse(any(pad.startswith(("T701.", "T711.")) for e in entries for pad in e["between"]))
        # a part's other pairs have no entry, and a part the owner did not accept has none
        pairs = {frozenset(e["between"]) for e in data["accepted_exceptions"] if "between" in e}
        self.assertNotIn(frozenset(("T701.1", "T701.3")), pairs)
        parts = {pad.split(".")[0] for e in entries for pad in e["between"]}
        self.assertTrue(parts.isdisjoint({"K201", "K731", "K741", "U602", "F101", "RV101"}), parts)
        # the reader finds the entries well formed, and no problem but the unsigned record
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        # an entry missing a key, or naming one pad, is refused by the same reader
        first = data["accepted_exceptions"][0]
        for key in ("between", "accepted_mm", "reason", "bounded_by"):
            broken = [{k: v for k, v in first.items() if k != key}] + data["accepted_exceptions"][1:]
            _, problems = reading(dict(data, accepted_exceptions=broken))
            self.assertTrue(any(key in p.message for p in problems), key)
        _, problems = reading(dict(data, accepted_exceptions=[dict(first, between=["T701.2"])] + data["accepted_exceptions"][1:]))
        self.assertTrue(any("between" in p.location for p in problems))

    def test_each_bought_part_creepage_shortfall_the_owner_accepted_has_an_unsigned_entry(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C4: accepted_exceptions holds a mains_to_low_voltage creepage entry with accepted_mm 8.0 for U601 and one with 7.0 for each of U701 and U711, each naming the one pair of pads it excuses in between, with its reason and bounding element and its accepted_by and accepted_on left empty for the owner's acceptance, and the reasons are those of the owner's recorded acceptance. K201, K731, K741 and U602 are out of scope here; their own leaf judges them. The values are drafted from the schematic and the division record; confirming them against the main-board layout is the layout leaf's and out of scope here.
        _, data = committed()
        assert_draft(self, data)
        entries = [e for e in data["accepted_exceptions"] if e["pair"] == "mains_to_low_voltage"]
        self.assertEqual({(tuple(e["between"]), e["accepted_mm"]) for e in entries},
                         {(("U601.10", "U601.11"), 8.0), (("U701.1", "U701.6"), 7.0), (("U711.1", "U711.6"), 7.0),
                          (("U602.1", "U602.4"), 7.6), (("U602.2", "U602.3"), 7.6), (("U602.1", "U602.3"), 7.6), (("U602.2", "U602.4"), 7.6)})
        self.assertEqual(len(entries), 7)
        for entry in entries:
            self.assertEqual(entry["constraint"], "creepage")
            self.assertLess(entry["accepted_mm"], data["mains_to_low_voltage"]["creepage_mm"])
            self.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""))
            self.assertTrue(entry["bounded_by"].strip())
            # the owner's recorded reasons, as the decision of 2026-10-29 states them
            for reason in ("sealed and inside the machine", "slots between pad rows", "conformal coat", "touchable"):
                self.assertIn(reason, entry["reason"])
        # K201, K731 and K741 have no entry: their short figure is inside the part and no pad pair shows it
        parts = {pad.split(".")[0] for e in entries for pad in e["between"]}
        self.assertEqual(parts, {"U601", "U701", "U711", "U602"})
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        # a creepage entry at or above the signed figure relaxes nothing, and the reader keeps the pair kind in its vocabulary
        _, problems = reading(dict(data, accepted_exceptions=[dict(entries[0], pair="mains_to_ground")]))
        self.assertTrue(any("pair" in p.location for p in problems))

    def test_the_pair_across_the_open_interlock_contact_is_held_at_the_reinforced_figures(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C8: held_at_reinforced in the committed record lists the net pair LINE and LINE1 and the net pair LINE_IN and LINE1, held to 3.0 mm clearance and 10.0 mm creepage, with no credit taken for the relay's own contact gap. The check's reader reads the pair. Other pairs of mains nets are out of scope and take the mains-to-mains figures.
        _, data = committed()
        pairs = data["mains_to_mains"]["held_at_reinforced"]
        self.assertEqual(sorted(sorted(pair) for pair in pairs),
                         sorted([sorted(["/LINE", "/LINE1"]), sorted(["/Mains entry and load feed/LINE_IN", "/LINE1"])]))
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        self.assertEqual(signed_from(data).mains_to_mains["held_at_reinforced"], pairs)
        # the rules the check appends hold each pair at the mains-to-low-voltage figures, 3.0 mm and 10.0 mm, whatever the mains-to-mains ones are
        rules = board_check.mains_to_mains_rules(signed_from(data))
        for first, second in pairs:
            self.assertIn(f"A.NetName == '{first}' && B.NetName == '{second}'", rules)
        reinforced = rules[rules.index(board_check.REINFORCED_RULE):]
        self.assertEqual(reinforced.count("(min 3mm)"), 2)
        self.assertEqual(reinforced.count("(min 10mm)"), 2)
        # a pair that is not two net names is refused by the reader
        for bad in (["/LINE"], ["/LINE", ""], "LINE LINE1"):
            _, problems = reading(dict(data, mains_to_mains=dict(data["mains_to_mains"], held_at_reinforced=[bad])))
            self.assertTrue(any("held_at_reinforced" in p.location for p in problems), bad)

    def test_a_downstream_creepage_below_the_basic_figure_needs_a_stated_basis(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C9: Before any creepage_mm below creepage_ahead_of_fuse_mm is signed, the record holds downstream_basis stating the prospective fault current at the downstream conductors, the entry fuse's clearing time for a tracking fault between them at that current, and the argument that this satisfies the standard's allowance; until then both creepage figures are the basic 4.1 mm. Figures for the pairs ahead of the fuse are out of scope here.
        _, data = committed()
        held = data["mains_to_mains"]
        self.assertNotIn("downstream_basis", held)
        self.assertEqual(held["creepage_mm"], held["creepage_ahead_of_fuse_mm"])
        lower = dict(held, creepage_mm=2.0)
        _, problems = reading(dict(data, mains_to_mains=lower))
        self.assertTrue(any("downstream_basis" in p.message for p in problems))
        stated = dict(lower, downstream_basis="a prospective fault current and the entry fuse clearing a tracking fault at it")
        _, problems = reading(dict(data, mains_to_mains=stated))
        self.assertFalse(any("downstream_basis" in p.message for p in problems))
        # with a stated basis the floor is the functional row at or above the working voltage, the 320 V band row (3.2 mm), so the lower figure still fails by name
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=stated)))
        self.assertEqual([p.location.split(" ", 1)[1] for p in found], ["mains_to_mains.creepage_mm"])
        self.assertIn("3.2 mm floor", found[0].message)


DIVISION = os.path.join("docs", "sunbeam-em7000", "controller-board-division.md")


def record_text():
    with open(os.path.join(ROOT, RECORD), encoding="utf-8") as handle:
        return handle.read()


class MainsToMainsReadings(unittest.TestCase):
    """What the committed record and the division record say about the readings behind the mains-to-mains figures."""

    def test_the_division_record_restates_the_signed_figures_and_holds_no_old_bound(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C10: The division record states the new figures at each place it stated the replaced ones, the places being its separation row, assumption A3, the option row on the second division, the paragraph on mains against mains, the rule list, finding 3, D15 and the bracket paragraph, the verification table's creepage row, the verification script's basis constants, expected-output strings and seeded faults, and the sentences reporting pairs under the basic creepage. A search of the record for 4.1 mm as a creepage figure and for pollution degree 3 finds none left unexplained, and the verification script passes on the record as edited. Out of scope is a distance the record chose larger than the figure for its own reason, such as the 5.0 mm wall-edge distance.
        with open(os.path.join(ROOT, DIVISION), encoding="utf-8") as handle:
            text = handle.read()
        _, data = committed()
        held = data["mains_to_mains"]
        # the old bound, and the statement that the basis gives no mains-to-mains figure, are gone wherever they appeared
        for old in ("keeps 3.0 mm in a straight line and 5.0 mm by surface path", "keeps 3.0 mm in a straight line and the basic creepage, 5.0 mm",
                    "3.0 mm straight and 5.0 mm by path", "3.0 mm or more apart and 5.0 mm or more by path",
                    "The file gives no mains-to-mains distance", "The basis states no mains-to-mains distance",
                    "Mains-to-mains spacing is not in the basis", "is held apart by 3.0 mm and 5.0 mm of path",
                    "the basis's basic creepage row, 5.0 mm", "the basis's own creepage row for basic insulation at 320 V"):
            self.assertNotIn(old, text, old)
        # the restatements state the signed figures, the interpolated row selection and the accepted exceptions
        stated = {"clearance": f"{held['clearance_mm']:.1f} mm", "creepage": f"{held['creepage_mm']:.1f} mm",
                  "terminal": f"{held['terminal_clearance_mm']:.1f} mm"}
        for heading in ("| Separation basis |", "| A3 |", "**Mains against mains (A3).**", "3. **Mains-to-mains spacing is signed in the basis"):
            start = text.index(heading)
            row = text[start:text.index("\n", start)]
            self.assertIn(stated["clearance"], row, heading)
            self.assertIn(stated["creepage"], row, heading)
            self.assertIn("exception", row, heading)
        a3 = text[text.index("| A3 |"):]
        a3 = a3[:a3.index("\n")]
        for phrase in ("250 V row (2.5 mm) and 320 V row (3.2 mm)", "pollution degree 2", "253 V", "rounded up", stated["terminal"],
                       "T701 and T711 at 2.0 mm of creepage between the tab and each lead pad", "R105 at 1.65 mm", "1206 series resistors at 1.8 mm"):
            self.assertIn(phrase, a3, phrase)
        # the mains-to-earth pair states the same row selection
        d15 = text[text.index("**D15."):]
        d15 = d15[:d15.index("\n")]
        self.assertIn(stated["creepage"], d15)
        self.assertEqual(stated["creepage"], "2.6 mm")
        self.assertIn("same row selection", d15)
        # the script reads the signed mains-to-mains figures from the record and checks the data against them
        script = text[text.index("```python"):]
        for name in ("m_clearance", "m_terminal", "m_creepage", "'mains_to_mains'"):
            self.assertIn(name, script, name)
        data_block = text[text.index("```floorplan-data"):]
        for fragment in (f'"m_clearance": {held["clearance_mm"]}', f'"m_terminal": {held["terminal_clearance_mm"]}',
                         f'"m_creepage": {held["creepage_mm"]}'):
            self.assertIn(fragment, data_block, fragment)

    def test_the_record_signs_group_iiia_on_a_fabrication_notes_requirement_and_cites_no_laminate(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C7: A footnote of the household-appliance standard's creepage tables, as reproduced in two certification reports, allows the lowest material group (IIIb) at pollution degree 3 only up to a working voltage of 50 V. The record signs material_group IIIa. The stated ground is a requirement on the main board's fabrication notes, carried by the main-board layout leaf (SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT): a laminate whose published comparative tracking index is at least 175. No laminate is chosen yet, so the record states that ground as a requirement on the fabrication notes and cites no laminate maker's document. The creepage rows at 253 V are equal for groups IIIa and IIIb (5.0 mm at the 320 V row), so no figure changes. The mains_to_low_voltage 10.0 mm figure rests on the same basis and is unchanged. A reading of the standard's own text, which the reports only reproduce, is out of scope and is noted as unread. The derived row's material_group input is stated as IIIa.
        _, data = committed()
        self.assertEqual(data["material_group"], "IIIa")
        comments = " ".join(line[1:].strip() for line in record_text().splitlines() if line.startswith("#"))
        for phrase in ("requirement on the main board's fabrication notes", "comparative tracking index", "at least 175",
                       "SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT", "no laminate is chosen yet",
                       "equal for IIIa and IIIb", "was not read"):
            self.assertIn(phrase, " ".join(comments.split()), phrase)
        # every row that states a group states IIIa, the derived creepage row included, and the 10.0 mm figure is unchanged
        groups = {row["inputs"]["material_group"] for row in data["table_rows"] if "material_group" in row["inputs"]}
        self.assertEqual(groups, {"IIIa"})
        derived = next(row for row in data["table_rows"] if row["inputs"].get("working_voltage_v") == 253)
        self.assertEqual(derived["inputs"]["material_group"], "IIIa")
        self.assertEqual(data["mains_to_low_voltage"]["creepage_mm"], 10.0)
        self.assertNotIn("only up to a working voltage of 50 V", " ".join(record_text().split()))
        # no laminate maker's document is cited
        self.assertNotIn("laminate maker", " ".join(row["citation"]["document"] for row in data["table_rows"]))

    def test_the_readings_for_the_owner_to_check_are_marked_and_the_interpolation_permission_is_stated_from_the_2007_text(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C5: The record's derived basic creepage row has working_voltage_v 253, pollution_degree 2 and material_group IIIa, figure creepage_mm 2.6, and a citation that names the 250 V row (2.5 mm) and the 320 V row (3.2 mm) of the pollution degree 2 material group III column of IEC 60664-1 Table F.4, the arithmetic giving 2.53 mm, the clause that allows the interpolation (IEC 60664-1:2007 clause 5.2.4), the 0.1 mm margin over the standard's own rounded 2.5 mm, and that the rows are read from reproductions and not from the standard. The citation keeps the fallback of the 320 V row, 3.2 mm, should the household-appliance standard refuse interpolation. Out of scope is the standard's own text.
        _, data = committed()
        terminal = next(row for row in data["table_rows"] if row["inputs"].get("location") == "terminal")
        marked = " ".join(terminal["citation"].values())
        for phrase in ("0.5 mm", "Table 16", "certification reports", "drafter's reading", "unverified", "not found"):
            self.assertIn(phrase, marked, phrase)
        derived = next(row for row in data["table_rows"] if row["inputs"].get("working_voltage_v") == 253)
        cited = " ".join(derived["citation"].values())
        for phrase in ("clause 5.2.4", "clause 5.2.3 for functional insulation", "2007 edition", "2020 edition and AMD1:2025 not read",
                       "drafter's reading", "IEC 60335-1", "not verified", "fallback is the 320 V row, 3.2 mm", "2.5 mm", "design margin of 0.1 mm"):
            self.assertIn(phrase, cited, phrase)
        text = " ".join(" ".join(line[1:].strip() for line in record_text().splitlines() if line.startswith("#")).split())
        for phrase in ("pollution degree 2, material group III: 250 V = 2.5 mm, 320 V = 3.2 mm", "fallback is the 320 V row, 3.2 mm",
                       "linear interpolation for intermediate voltages",
                       "rounds the result to the same number of digits as the table values", "owner, or a test house, confirms",
                       "creepage keeps the larger 10.0 mm figure"):
            self.assertIn(phrase, text, phrase)
        # the old comment that said the 320 V row is used and no interpolation is made is gone
        self.assertNotIn("no interpolation is made", text)
        self.assertNotIn("the next row up, 320 V, is the one used", text)


class BoughtPartsJudged(unittest.TestCase):
    """The four bought parts judged against the signed figures: the drafted U602 entries and the division record's judgement."""

    def division(self):
        with open(os.path.join(ROOT, DIVISION), encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("### The four parts judged against the signed figures")
        return text[start:text.index("\n## ", start)]

    def rows(self):
        found = {}
        for line in self.division().splitlines():
            if line.startswith("| ") and not line.startswith(("| Part", "|---")):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                found[(cells[0], cells[1])] = cells
        return found

    def test_each_part_and_quantity_has_a_row_with_the_signed_figure_and_absent_where_the_makers_state_nothing(self):
        # SOL-BOUGHT-PART-CREEPAGE-OF-K201-K731-K741-AND-U602-JUDGED.C2: For each of K201, K731, K741 and U602, the committed record and division record show exactly one of three states: the part's published creepage and clearance meet 10.0 mm and 3.0 mm; or the part's board pad gaps are what the check measures and the pad pairs that fall short each carry an accepted_exceptions entry in the check's form, with accepted_mm no greater than the measured gap, a stated ground and a bounding element, left unsigned; or the part is replaced by one in the first or second state. A figure inside the part that the board's pad gaps do not measure (the relays' published creepage over 8 mm, their clearance and U602's creepage and clearance where the maker publishes none) is recorded in the division record against the signed figure and counts as absent where unpublished: it is carried by the owner's recorded acceptance of bought-part creepage and put to the owner as an open decision to accept, change the part or find a published figure, and is never excused by an entry the check cannot judge. The owner's signature of the record is out of scope here and belongs to the acceptance leaf.
        rows = self.rows()
        self.assertEqual(sorted(rows), sorted([("K201", "Creepage"), ("K201", "Clearance"), ("K731 and K741", "Creepage"),
                                               ("K731 and K741", "Clearance"), ("U602", "Creepage"), ("U602", "Clearance")]))
        for (part, quantity), cells in rows.items():
            self.assertEqual(len(cells), 7, cells)
            self.assertIn("10.0 mm" if quantity == "Creepage" else "3.0 mm", cells[3], cells)
            self.assertTrue(cells[4] and cells[5], cells)
        # a figure the makers' table calls absent stays absent, and none is turned into an estimate
        for key in (("K201", "Clearance"), ("K731 and K741", "Clearance"), ("U602", "Creepage"), ("U602", "Clearance")):
            self.assertTrue(rows[key][2].startswith("absent"), rows[key])
            self.assertIn("absent", rows[key][4], rows[key])
        for key in (("K201", "Creepage"), ("K731 and K741", "Creepage")):
            self.assertIn("over 8 mm", rows[key][2])
            self.assertIn("not shown to meet", rows[key][4])
            self.assertIn("8.0 mm at least, short by up to 2.0 mm (20 %)", rows[key][4])
        # U602's board gap, read from the entries, is what the row's arithmetic states
        _, data = committed()
        accepted = {e["accepted_mm"] for e in data["accepted_exceptions"] if e["pair"] == "mains_to_low_voltage" and e.get("between", [""])[0].startswith("U602.")}
        self.assertEqual(len(accepted), 1, accepted)
        (accepted_mm,) = accepted
        arithmetic = rows[("U602", "Creepage")][4]
        facing = round(9.0 - 1.3, 2)
        shortfall = round(data["mains_to_low_voltage"]["creepage_mm"] - facing, 1)
        self.assertEqual((facing, shortfall), (7.7, 2.3))
        self.assertLess(accepted_mm, facing)
        self.assertIn(f"{facing} mm for the facing pairs", arithmetic)
        self.assertIn("7.77 mm for the diagonals", arithmetic)
        self.assertIn(f"short of 10.0 mm by {shortfall} mm ({round(100 * shortfall / 10.0)} %)", arithmetic)
        self.assertIn(f"{accepted_mm} mm each", rows[("U602", "Creepage")][6])

    def test_the_relays_and_the_unpublished_figures_are_left_to_the_owner_and_nothing_is_signed(self):
        # SOL-BOUGHT-PART-CREEPAGE-OF-K201-K731-K741-AND-U602-JUDGED.C2: For each of K201, K731, K741 and U602, the committed record and division record show exactly one of three states: the part's published creepage and clearance meet 10.0 mm and 3.0 mm; or the part's board pad gaps are what the check measures and the pad pairs that fall short each carry an accepted_exceptions entry in the check's form, with accepted_mm no greater than the measured gap, a stated ground and a bounding element, left unsigned; or the part is replaced by one in the first or second state. A figure inside the part that the board's pad gaps do not measure (the relays' published creepage over 8 mm, their clearance and U602's creepage and clearance where the maker publishes none) is recorded in the division record against the signed figure and counts as absent where unpublished: it is carried by the owner's recorded acceptance of bought-part creepage and put to the owner as an open decision to accept, change the part or find a published figure, and is never excused by an entry the check cannot judge. The owner's signature of the record is out of scope here and belongs to the acceptance leaf.
        text = self.division()
        for phrase in ("accept the figure as published, change the part, or find a published figure",
                       "accept this distance, change the part, or find a published figure", "*Recommendation:* accept K201, K731 and K741",
                       "VDE 0700 and 0631", "Open layout item (not an exception)", "5.06 mm apart", "no exception for it"):
            self.assertIn(phrase, " ".join(text.split()), phrase)
        _, data = committed()
        assert_draft(self, data)
        parts = {pad.split(".")[0] for e in data["accepted_exceptions"] for pad in e.get("between", [])}
        self.assertTrue(parts.isdisjoint({"K201", "K731", "K741"}), parts)

    def test_the_four_u602_pad_pairs_are_unsigned_creepage_entries_stating_the_gap_is_the_boards(self):
        # SOL-BOUGHT-PART-CREEPAGE-OF-K201-K731-K741-AND-U602-JUDGED.C2: For each of K201, K731, K741 and U602, the committed record and division record show exactly one of three states: the part's published creepage and clearance meet 10.0 mm and 3.0 mm; or the part's board pad gaps are what the check measures and the pad pairs that fall short each carry an accepted_exceptions entry in the check's form, with accepted_mm no greater than the measured gap, a stated ground and a bounding element, left unsigned; or the part is replaced by one in the first or second state. A figure inside the part that the board's pad gaps do not measure (the relays' published creepage over 8 mm, their clearance and U602's creepage and clearance where the maker publishes none) is recorded in the division record against the signed figure and counts as absent where unpublished: it is carried by the owner's recorded acceptance of bought-part creepage and put to the owner as an open decision to accept, change the part or find a published figure, and is never excused by an entry the check cannot judge. The owner's signature of the record is out of scope here and belongs to the acceptance leaf.
        _, data = committed()
        entries = [e for e in data["accepted_exceptions"] if e["pair"] == "mains_to_low_voltage" and e.get("between", [""])[0].startswith("U602.")]
        self.assertEqual(sorted(tuple(e["between"]) for e in entries),
                         sorted([("U602.1", "U602.4"), ("U602.2", "U602.3"), ("U602.1", "U602.3"), ("U602.2", "U602.4")]))
        for entry in entries:
            self.assertEqual((entry["pair"], entry["constraint"]), ("mains_to_low_voltage", "creepage"))
            self.assertLess(entry["accepted_mm"], data["mains_to_low_voltage"]["creepage_mm"])
            self.assertLess(entry["accepted_mm"], 7.7)
            self.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""))
            self.assertIn("not a published creepage", entry["reason"])
            self.assertIn("Unpublished: owner to decide: accept this distance, change the part, or find a published figure", entry["reason"])
            self.assertTrue(entry["bounded_by"].strip())
        # no clearance entry: the board's gap is over the signed clearance, so one would cover no shortfall
        self.assertEqual([e for e in entries if e["constraint"] != "creepage"], [])
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])


class SameConnectorRecord(unittest.TestCase):
    """The committed record's same_connector_pins entries, one for each 2.0 mm-pitch harness header, read through the check's own reader."""

    HEADERS = ("J630", "J635", "J791", "J821", "J861")

    def entries(self, data):
        return [e for e in data["accepted_exceptions"] if e["pair"] == board_check.SAME_CONNECTOR_PAIR]

    def test_each_of_the_five_headers_has_one_drafted_entry_with_its_acceptance_empty(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C6: The committed record holds one same_connector_pins entry for each of J630, J635, J791, J821 and J861 with pitch_mm 2.0, an accepted_mm drafted from the schematic and the division record, the reason that the header carries slow signals only and no fast signal crosses its strip, a bounding element, and the entry's own accepted_by and accepted_on empty. The five entries are read through the check's own reader from the committed record in whatever acceptance state the record as a whole is in, and each is accepted as a form; the test asserts nothing about whether the record as a whole reads signed or unsigned.
        _, data = committed()
        entries = self.entries(data)
        self.assertEqual([e["connector"] for e in entries], list(self.HEADERS))
        for entry in entries:
            with self.subTest(connector=entry["connector"]):
                self.assertEqual(sorted(entry), sorted(board_check.SAME_CONNECTOR_KEYS))
                self.assertEqual((entry["constraint"], entry["pitch_mm"]), ("hole_to_hole", 2.0))
                # the pitch less the 0.75 mm drill of the JST PH footprint, and below the plated-hole figure the layout practice derives
                self.assertEqual(entry["accepted_mm"], 1.25)
                self.assertIn("slow signals only", entry["reason"])
                self.assertIn("no fast signal crosses its strip", entry["reason"])
                self.assertIn("the owner makes, which the tool does not check", entry["reason"])
                self.assertIn(entry["connector"], entry["reason"])
                self.assertTrue(entry["bounded_by"].strip())
                self.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""))

    def test_the_checks_own_reader_accepts_each_entry_as_a_form_and_refuses_a_broken_one(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-SAME-CONNECTOR-PLATED-HOLE-SPACING-EXCEPTIONS.C6: The committed record holds one same_connector_pins entry for each of J630, J635, J791, J821 and J861 with pitch_mm 2.0, an accepted_mm drafted from the schematic and the division record, the reason that the header carries slow signals only and no fast signal crosses its strip, a bounding element, and the entry's own accepted_by and accepted_on empty. The five entries are read through the check's own reader from the committed record in whatever acceptance state the record as a whole is in, and each is accepted as a form; the test asserts nothing about whether the record as a whole reads signed or unsigned.
        _, data = committed()
        _, problems = reading()
        self.assertEqual([p.line() for p in problems if "accepted_exceptions" in p.location], [])
        first = next(i for i, e in enumerate(data["accepted_exceptions"]) if e["pair"] == board_check.SAME_CONNECTOR_PAIR)
        for key in board_check.SAME_CONNECTOR_KEYS:
            broken = [dict(e) for e in data["accepted_exceptions"]]
            del broken[first][key]
            _, found = reading(dict(data, accepted_exceptions=broken))
            self.assertTrue(any(p.location.endswith(f"accepted_exceptions[{first}].{key}") and f"lacks {key}" in p.message
                                for p in found), key)
        twice = [dict(e) for e in data["accepted_exceptions"]]
        twice[first + 1]["connector"] = twice[first]["connector"]
        _, found = reading(dict(data, accepted_exceptions=twice))
        self.assertTrue(any(p.location.endswith(f"accepted_exceptions[{first + 1}].connector") for p in found))
        held = [dict(e) for e in data["accepted_exceptions"]]
        held[first]["between"] = ["J630.1", "J630.2"]
        _, found = reading(dict(data, accepted_exceptions=held))
        self.assertTrue(any(p.location.endswith(f"accepted_exceptions[{first}].between") for p in found))


def band_figure(rows, voltage, key):
    """The band rule as the record's citation states it, in exact arithmetic: the figure at `voltage` read from the functional band `rows`."""
    points = sorted((fractions.Fraction(str(row["inputs"]["working_voltage_v"])), fractions.Fraction(str(row["figure"][key]))) for row in rows)
    voltage = fractions.Fraction(str(voltage))
    if voltage <= points[0][0]:
        return float(points[0][1])
    if voltage > points[-1][0]:
        return None
    for (low_v, low), (high_v, high) in zip(points, points[1:]):
        if low_v <= voltage <= high_v:
            exact = low + (high - low) * (voltage - low_v) / (high_v - low_v)
            return math.ceil(exact * 10) / 10
    raise AssertionError(voltage)


def band_rows(data):
    return [row for row in data["table_rows"] if row["inputs"].get("insulation") == "functional"]


def comment_text():
    """The record's whole comment text, whitespace-normalised."""
    return " ".join(" ".join(line[1:].strip() for line in record_text().splitlines() if line.startswith("#")).split())


class PollutionDegreeTwoRecord(unittest.TestCase):
    """The record at pollution degree 2 on a coated board: its inputs, conditions, band rows and restated documents."""

    def test_the_record_reads_pollution_degree_2_and_credits_no_pollution_degree_1(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C1: The committed separation-basis.yaml holds pollution_degree 2, and no table_rows entry and no other value in the record reads pollution degree 1. The test reads the record through the check's own reader. Out of scope is the check refusing a pollution degree below 3 that states no protection, which the record's own wording and the owner's acceptance carry.
        _, data = committed()
        self.assertEqual(data["pollution_degree"], 2)
        found = []

        def walk(node, path):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "pollution_degree":
                        found.append((path, value))
                    walk(value, path + [key])
            elif isinstance(node, list):
                for position, value in enumerate(node):
                    walk(value, path + [position])

        walk(data, [])
        self.assertTrue(found)
        self.assertEqual({value for _, value in found}, {2}, found)
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        # the same record with a row read at pollution degree 1 is a different record: the walk would find it
        rows = [dict(row, inputs=dict(row["inputs"], pollution_degree=1)) if position == 1 else row for position, row in enumerate(data["table_rows"])]
        found.clear()
        walk(dict(data, table_rows=rows), [])
        self.assertIn(1, {value for _, value in found})

    def test_the_environment_says_the_boards_are_protected_against_moisture_by_the_enclosure(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C2: The environment text of the committed record contains the words "protected against moisture: enclosure", names the conformal coat as a supporting measure, and no longer contains "uncoated" or "not protected against moisture". The test reads the committed record. Out of scope is whether a coat is applied, which the layout leaves and the bring-up task carry.
        _, data = committed()
        environment = data["environment"]
        self.assertIn("protected against moisture: enclosure", environment)
        self.assertIn("conformal coat as a supporting measure", environment)
        self.assertNotIn("moisture: coated", environment)
        self.assertNotIn("uncoated", environment)
        self.assertNotIn("not protected against moisture", environment)

    def test_the_header_holds_the_six_conditions_in_order_the_sources_the_readings_and_the_carrying_nodes(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C3: The header comment of the committed record holds a numbered block of six conditions, each naming its subject, in this order and with these figures: the coat before the boards are energised in the machine, with the coat type and datasheet named in the fabrication notes and the gaps between mains pads covered except documented contact keep-outs; the protection stated as coated and credited at pollution degree 2 only, never 1; a laminate comparative tracking index of at least 175; slots in creepage paths at least 1.0 mm wide, 1.5 mm if a pollution degree 3 credit must survive; the bring-up humidity reading confirming no condensation while energised, with the fall back to pollution degree 3 and 4.1 mm as a fresh basis; and the whole record re-signed by the owner. The header no longer says that coating the boards later would be a fresh basis. Out of scope is any condition beyond those six. The header also names the open reproductions the figures rest on (the EMA table, TI SLUP421 and SLUAAR5, IECEx document 1422 and the IECEE decision sheet) and says they are reproductions and not the standard's text, lists the readings the owner or a test house is to confirm, and names by node id the layout leaves and the bring-up task that carry the coat, the laminate and the humidity requirements.
        text = comment_text()
        start = text.index("The credit of pollution degree 2 on a board its enclosure protects rests on six conditions")
        block = text[start:text.index("The tables are those of IEC 60664-1")]
        items = re.split(r"\s(?=[1-6]\. [A-Z][a-z]+:)", block)[1:]
        self.assertEqual([item[3:item.index(":")] for item in items], ["Enclosure", "Degree", "Laminate", "Slots", "Humidity", "Signature"])
        enclosure, degree, laminate, slots, humidity, signature = items
        for phrase in ("the credit stands on the enclosure", "supporting measure that does not itself earn the credit",
                       "before they are energised in the machine", "coat type and cite its datasheet", "covers the gaps between mains pads",
                       "except the keep-outs documented for contacts"):
            self.assertIn(phrase, enclosure)
        for phrase in ("protected against moisture, by the enclosure, with the coat a supporting measure", "credits pollution degree 2 only", "Pollution degree 1 is never credited"):
            self.assertIn(phrase, degree)
        for phrase in ("comparative tracking index", "at least 175"):
            self.assertIn(phrase, laminate)
        for phrase in ("at least 1.0 mm wide", "1.5 mm if a pollution degree 3 credit must survive"):
            self.assertIn(phrase, slots)
        for phrase in ("humidity reading", "no condensation on the boards while energised", "pollution degree 3 and 4.1 mm", "fresh basis"):
            self.assertIn(phrase, humidity)
        for phrase in ("whole record is re-signed by the owner",):
            self.assertIn(phrase, signature)
        # the nodes that carry the coat, the laminate and the humidity requirements are named by id
        for node in ("SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT", "SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT", "DEL-HW-BRING-UP"):
            self.assertIn(node, block, node)
        # and so are the criteria within them
        for criterion in ("SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT.C16", "SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT.C17",
                          "SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT.C10", "DEL-HW-BRING-UP.C16", "DEL-HW-BRING-UP.C17"):
            node, number = criterion.split(".")
            self.assertRegex(block, re.escape(node) + r"\W+(?:\w+\W+){0,3}?" + number + r"\b", criterion)
        self.assertNotIn("Coating them later would be a fresh basis", text)
        self.assertNotIn("boards not protected against moisture", text)
        # the open reproductions the figures rest on, and that they are not the standard's text
        for phrase in ("EMA Design Automation", "SLUP421", "SLUAAR5", "IECEx document 1422", "IECEE decision sheet", "note 1 of Table F.4",
                       "reproductions and not the standard's text", "pollution degree 2, material group III: 250 V = 2.5 mm, 320 V = 3.2 mm"):
            self.assertIn(phrase, text, phrase)
        # the readings the owner or a test house is to check name the coat conditions and the band rows
        readings = text[text.index("Readings the drafter made"):text.index("The credit of pollution degree 2")]
        for phrase in ("The conditions below", "functional band rows", "the fallback is the 320 V row, 3.2 mm"):
            self.assertIn(phrase, readings, phrase)

    def test_the_mains_to_low_voltage_rows_are_read_at_pollution_degree_2_and_the_floor_holds(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C6: The record's rows for the mains-to-low-voltage clearance and creepage are read at pollution degree 2 (clearance 3.0 mm from Table F.2 at 4.0 kV, creepage 6.4 mm, the 3.2 mm of the 320 V row doubled for reinforced insulation), the check's floor rule run on the record's own figures taken as signed finds no violation, and a creepage_mm of 2.5 or a pollution degree 3 on those rows fails it. The record says the margin of the signed 10.0 mm over 6.4 mm is deliberate. Out of scope is changing the signed 3.0 mm and 10.0 mm.
        _, data = committed()
        rows = data["table_rows"]
        clearance = next(r for r in rows if r["inputs"].get("insulation") == "reinforced" and "clearance_mm" in r["figure"])
        creepage = next(r for r in rows if r["inputs"].get("insulation") == "reinforced" and "creepage_mm" in r["figure"])
        self.assertEqual((clearance["inputs"]["pollution_degree"], clearance["figure"]["clearance_mm"]), (2, 3.0))
        self.assertIn("Table F.2: 4.0 kV, pollution degree 2, 3.0 mm", clearance["citation"]["locator"])
        self.assertEqual((creepage["inputs"]["pollution_degree"], creepage["figure"]["creepage_mm"]), (2, 6.4))
        self.assertIn("3.2 mm basic, doubled to 6.4 mm", creepage["citation"]["locator"])
        self.assertEqual((data["mains_to_low_voltage"]["clearance_mm"], data["mains_to_low_voltage"]["creepage_mm"]), (3.0, 10.0))
        self.assertIn("3.6 mm over", comment_text())
        self.assertIn("3.6 mm over it, deliberately", creepage["citation"]["locator"])
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed_from(data)), [])
        low = dict(data, mains_to_low_voltage=dict(data["mains_to_low_voltage"], creepage_mm=2.5))
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(low))
        self.assertEqual(len(found), 1)
        self.assertIn("mains_to_low_voltage.creepage_mm", found[0].location)
        self.assertIn("below the", found[0].message)
        # a record read at pollution degree 3 leaves every figure without an applicable row
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, pollution_degree=3)))
        self.assertEqual(sorted(p.location.split(" ", 1)[1] for p in found if "mains_to_low_voltage" in p.location),
                         ["mains_to_low_voltage.clearance_mm", "mains_to_low_voltage.creepage_mm"])
        self.assertTrue(all("no table row" in p.message for p in found))

    def test_the_record_carries_the_eight_functional_band_rows_and_the_floor_reads_the_same_with_them(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C7: The record's table_rows hold exactly eight rows of insulation functional, location conductor, pollution degree 2 and material group IIIa, at working_voltage_v 10, 25, 50, 125, 160, 200, 250 and 320 with creepage_mm 0.40, 0.50, 1.20, 1.5, 1.6, 2.0, 2.5 and 3.2 and clearance_mm 0.2, 0.2, 0.2, 1.5, 1.5, 1.5, 1.5 and 1.5, the rows from 10 V to 50 V cited as readings from open reproductions with the IEC text unread, each citing Table F.4 and its reproduction, with exactly the keys inputs {working_voltage_v, insulation functional, location conductor, pollution_degree 2, material_group IIIa} and figure {creepage_mm, clearance_mm} and no downstream_basis in the mapping, and the check's own reader reads them with no problem. The mains_to_mains floor rule, run with them present, reads the same floors as without them. Out of scope is any row at another pollution degree or material group.
        _, data = committed()
        rows = band_rows(data)
        self.assertEqual(len(rows), 8)
        self.assertEqual([(r["inputs"]["working_voltage_v"], r["figure"]["creepage_mm"], r["figure"]["clearance_mm"]) for r in rows],
                         [(10, 0.40, 0.2), (25, 0.50, 0.2), (50, 1.20, 0.2), (125, 1.5, 1.5), (160, 1.6, 1.5), (200, 2.0, 1.5), (250, 2.5, 1.5), (320, 3.2, 1.5)])
        for row in rows:
            self.assertEqual(set(row["inputs"]), {"working_voltage_v", "insulation", "location", "pollution_degree", "material_group"})
            self.assertEqual((row["inputs"]["insulation"], row["inputs"]["location"], row["inputs"]["pollution_degree"], row["inputs"]["material_group"]),
                             ("functional", "conductor", 2, "IIIa"))
            self.assertEqual(set(row["figure"]), {"creepage_mm", "clearance_mm"})
            cited = " ".join(row["citation"].values())
            self.assertIn("Table F.4", cited)
            self.assertIn("reproduction", cited)
        for row in rows[:3]:
            cited = " ".join(row["citation"].values())
            self.assertIn("open reproductions", cited)
            self.assertIn("IEC text unread", cited)
        self.assertNotIn("downstream_basis", data["mains_to_mains"])
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])
        without = dict(data, table_rows=[r for r in data["table_rows"] if r not in rows])
        self.assertEqual(len(without["table_rows"]), 5)
        signed = signed_from(data)
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed), [])
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed_from(without)), [])
        # the equality is not vacuous: a figure under the floor fails the same way with the rows present and without them
        for key, low in (("creepage_mm", 2.5), ("clearance_mm", 1.4)):
            lowered = dict(data["mains_to_mains"], **{key: low})
            with_rows = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=lowered)))
            no_rows = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(without, mains_to_mains=lowered)))
            self.assertEqual([(p.location, p.message) for p in with_rows], [(p.location, p.message) for p in no_rows], key)
            self.assertEqual(len(with_rows), 1, key)
        # a stated downstream basis would pull the functional 320 V row into the creepage floor, which is why the record holds none
        stated = dict(data["mains_to_mains"], downstream_basis="a prospective fault current and the entry fuse clearing a tracking fault at it")
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=stated)))
        self.assertTrue(found)

    def test_the_enclosure_credit_the_unread_standards_and_the_single_fault_basis_are_stated(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C3: The header states the enclosure as the credit, that the figures are single-sourced reproductions and that IEC 60335-1, IEC 60335-2-15, IEC 60664-1 and IEC 60664-3 are unread, an owner-accepted residual risk dated 2026-10-31 quoting the owner, and that a reduced pair rests on normal operation plus a recorded single-fault analysis whose table the check does not read.
        text = comment_text()
        required = ("the credit stands on the enclosure", "single-sourced reproductions", "IEC 60335-2-15 (appliances for heating liquids",
                    "IEC 60664-3 is unread", "accepted by the owner on 2026-10-31",
                    "I'm not buying the standards, this is a hobby project, we probably won't insulation test with equipment",
                    "single-fault analysis recorded for that listing", "The fault table is a comment of this record: the check does not read it")
        for phrase in required:
            self.assertIn(phrase, text, phrase)
        # a header that drops any one sentence is caught, and none asks for a purchase or an independent read as a step
        for phrase in required:
            self.assertNotIn(phrase, text.replace(phrase, ""), phrase)
        for step in ("buy the standard", "purchase the standard", "independent read before", "before the boards are ordered, read the standard"):
            self.assertNotIn(step, text)

    def test_the_band_rule_is_stated_and_gives_the_listed_figures_on_the_committed_rows(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C8: The citation of the band rows states the band rule in these terms: between two adjacent rows the figure is the linear interpolation rounded up to 0.1 mm, below 10 V the 10 V row is read, above the 320 V row there is no band figure, and a pair at the supply voltage keeps 2.6 mm. The test evaluates the stated rule on creepage at 10 V (0.4 mm), 30 V (0.7 mm), 84.5 V (1.4 mm), 126.5 V (1.6 mm), 168.5 V (1.7 mm), 178.7 V (1.8 mm) and 253 V (2.6 mm), and on clearance at 10 V (0.2 mm), 50 V (0.2 mm) and 125 V (1.5 mm), from the committed rows and finds those figures. Out of scope is the check's use of the rows.
        _, data = committed()
        rows = band_rows(data)
        for row in rows:
            locator = " ".join(row["citation"]["locator"].split())
            for term in ("between two adjacent rows the figure is the linear interpolation rounded up to 0.1 mm", "below 10 V the 10 V row is read",
                         "above the 320 V row there is no band figure", "a pair at the supply voltage in normal operation keeps 2.6 mm",
                         "a pair reaching it only on a single fault being reduced only with that listing's single-fault table"):
                self.assertIn(term, locator, term)
        for voltage, creepage in ((10, 0.4), (30, 0.7), (84.5, 1.4), (126.5, 1.6), (168.5, 1.7), (178.7, 1.8), (253, 2.6)):
            self.assertEqual(band_figure(rows, voltage, "creepage_mm"), creepage, voltage)
        for voltage, clearance in ((10, 0.2), (50, 0.2), (125, 1.5)):
            self.assertEqual(band_figure(rows, voltage, "clearance_mm"), clearance, voltage)
        self.assertEqual(band_figure(rows, 5, "creepage_mm"), 0.4)
        self.assertIsNone(band_figure(rows, 321, "creepage_mm"))
        # the pair at the supply voltage reads the signed mains-to-mains figure
        self.assertEqual(band_figure(rows, 253, "creepage_mm"), data["mains_to_mains"]["creepage_mm"])
        # a changed row changes a figure the rule gives
        shifted = [dict(r, figure=dict(r["figure"], creepage_mm=r["figure"]["creepage_mm"] + 0.3)) if r["inputs"]["working_voltage_v"] == 50 else r for r in rows]
        self.assertNotEqual(band_figure(shifted, 84.5, "creepage_mm"), 1.4)

    def test_the_division_record_states_no_old_figure_unexplained_and_its_script_passes(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C10: The division record states the new figures at each place it stated the replaced ones, the places being its separation row, assumption A3, the option row on the second division, the paragraph on mains against mains, the rule list, finding 3, D15 and the bracket paragraph, the verification table's creepage row, the verification script's basis constants, expected-output strings and seeded faults, and the sentences reporting pairs under the basic creepage. A search of the record for 4.1 mm as a creepage figure and for pollution degree 3 finds none left unexplained, and the verification script passes on the record as edited. Out of scope is a distance the record chose larger than the figure for its own reason, such as the 5.0 mm wall-edge distance.
        with open(os.path.join(ROOT, DIVISION), encoding="utf-8") as handle:
            text = handle.read()
        # every place that states the replaced creepage or pollution degree 3 says why (the fall back, or the figure replaced)
        for pattern in (r"(?<![\d.])4\.1 mm", r"pollution degree 3"):
            for match in re.finditer(pattern, text):
                around = " ".join(text[max(0, match.start() - 200):match.end() + 200].split())
                self.assertTrue("fall back" in around or "replaced" in around, around)
        # a distance the record chose larger than the figure for its own reason stays as drawn
        self.assertIn("least 5.0 mm of 2.6", text)
        # the script compares the record with the data and with its expected output, and ends with the verdict
        script = re.search(r"^```python\n(.*?)^```", text, re.S | re.M).group(1)
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "checks.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(script)
            for board in ("main", "wall"):
                done = subprocess.run([sys.executable, "-I", path, os.path.join(ROOT, DIVISION), board], capture_output=True, text=True, cwd=ROOT, timeout=900)
                self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
                self.assertEqual(done.stdout.strip().splitlines()[-1], f"all {board} board checks pass")

    def test_the_division_separation_row_quotes_the_records_own_creepage_rows(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C10: The division record states the new figures at each place it stated the replaced ones, the places being its separation row, assumption A3, the option row on the second division, the paragraph on mains against mains, the rule list, finding 3, D15 and the bracket paragraph, the verification table's creepage row, the verification script's basis constants, expected-output strings and seeded faults, and the sentences reporting pairs under the basic creepage.
        _, data = committed()
        rows = {r["inputs"]["working_voltage_v"]: r["figure"]["creepage_mm"] for r in data["table_rows"]
                if r["inputs"].get("insulation") == "functional" and r["inputs"].get("working_voltage_v") in (250, 320)}
        self.assertEqual(sorted(rows), [250, 320])
        with open(os.path.join(ROOT, DIVISION), encoding="utf-8") as handle:
            row = next(line for line in handle.read().splitlines() if line.startswith("| Separation basis"))
        self.assertIn(f"{rows[250]} mm at 250 V and {rows[320]} mm at 320 V", row)
        self.assertIn(f"{data['mains_to_mains']['creepage_mm']} mm", row)
        for old in ("(4.0 mm)", "(5.0 mm)", "250 V row (", "320 V row ("):
            self.assertNotIn(old, row)

    def test_the_constraints_record_the_readme_and_the_method_restate_pollution_degree_2(self):
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C11: The constraints record's pollution degree row reads 2 with the boards protected against moisture by a coat and cites the decision's conditions, its separation and material-group rows restate the figures of the committed record, and a search of the record for pollution degree 3 and 4.1 mm finds none left unexplained. Out of scope is any row about another quantity.
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C12: hardware/README.md states, in its adopter steps, that pollution degree 3 is taken unless the boards are protected against moisture and that a coat credits pollution degree 2 only on the stated conditions, and describes the functional band rows of table_rows beside the record keys it lists. Out of scope is the net_pairs exception form, which the pre-order check leaf documents.
        # SOL-SEPARATION-BASIS-TAKES-POLLUTION-DEGREE-2-ON-A-COATED-BOARD.C13: Item MAINS-4 of docs/board-design-method.md states that the width it requires of a slot or groove is the pollution degree 2 figure, 1.0 mm, that it is held wider than 1 mm, and that a pollution degree 3 basis needs 1.5 mm. Out of scope is any other item.
        with open(os.path.join(ROOT, "docs", "sunbeam-em7000", "controller-board-design-constraints.md"), encoding="utf-8") as handle:
            constraints = handle.read()
        row = next(line for line in constraints.splitlines() if line.startswith("| Pollution degree the enclosure warrants"))
        for phrase in ("| 2, boards protected against moisture by the enclosure", "supporting measure", "never 1", "IEC 60335-2-15", "inferred"):
            self.assertIn(phrase, row)
        material = next(line for line in constraints.splitlines() if line.startswith("| Laminate's tracking resistance"))
        self.assertNotIn("pollution degree 3", material)
        self.assertNotIn("5.0 mm", material)
        self.assertIn("2.5 mm at 250 V and 3.2 mm at 320 V", material)
        separation = {line.split("|")[1].strip(): line for line in constraints.splitlines() if line.startswith(("| Mains-to-low-voltage separation", "| Mains-to-mains separation"))}
        self.assertEqual(sorted(separation), ["Mains-to-low-voltage separation", "Mains-to-mains separation"])
        self.assertIn("6.4 mm", separation["Mains-to-low-voltage separation"])
        self.assertIn("2.6 mm creepage", separation["Mains-to-mains separation"])
        for line in constraints.splitlines():
            for match in re.finditer(r"pollution degree 3|(?<![\d.])4\.1 mm", line):
                self.assertTrue("fall" in line or "survive" in line, line[:120])
        with open(os.path.join(ROOT, "hardware", "README.md"), encoding="utf-8") as handle:
            readme = " ".join(handle.read().split())
        for phrase in ("Pollution degree is 3 unless your boards are protected against moisture", "The credit stands on the enclosure",
                       "supporting measure and is not itself the credit", "credits pollution degree 2 only, never 1", "IEC 60335-2-15",
                       "the fault table is a comment of the record",
                       "slots at least 1.0 mm wide", "functional **band rows**", "below the lowest row that row is read"):
            self.assertIn(phrase, readme, phrase)
        with open(os.path.join(ROOT, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            method = handle.read()
        item = method[method.index("#### MAINS-4."):]
        item = " ".join(item[:item.index("\n#### ")].split())
        for phrase in ("wider than 1 mm", "pollution degree 2 groove width", "1.0 mm is the pollution degree 2 groove width", "a record at pollution degree 3 needs 1.5 mm"):
            self.assertIn(phrase, item, phrase)
        for field in ("**Applies when:**", "**Asks:**", "**Passes:**", "**Fails, as the views show it:**", "**Judged on:**"):
            self.assertIn(field, item, field)


S, P, Z, M = ("/Supply voltage and current measurement/", "/Pump drives/", "/Zero-crossing detector/", "/Mains entry and load feed/")
#: The fifteen neutral-referenced nets, as the main board's netlist writes them: the thirteen on the converter and the shunt, the net of U601's unconnected pin 6 and the converter's high-side ground.
SET_N = ["/NEUTRAL", M + "NEUTRAL_IN", "/SHUNT_SENSE_IN", "/SHUNT_SENSE_NEUTRAL", S + "AMC_AIN0P", S + "AMC_AIN0N", S + "AMC_AIN1P",
         S + "AMC_AIN1N", S + "AMC_DCDC_OUT", S + "AMC_DCDC_HGND", S + "AMC_HGND", S + "AMC_HLDO_IN", S + "AMC_HLDO_OUT", S + "VMEAS_DIV",
         "unconnected-(U601-GPO-Pad6)"]
#: The triac gate nets and the zero-cross LED anode, which pair only with /NEUTRAL.
GATE_AND_LED = [P + "PUMP_C_TRIAC_G", P + "PUMP_S_TRIAC_G", Z + "ZC_LED_A"]
#: The eleven net-pair entries: constraint, nets_a, nets_b (None where omitted), working voltage, accepted distance.
NET_PAIRS = [
    ("creepage", SET_N, None, 10, 0.4),
    ("clearance", SET_N, None, 10, 0.2),
    ("creepage", [M + "DISCH_A", M + "DISCH_B"], ["/LINE", "/NEUTRAL"], 126.5, 1.6),
    ("creepage", [M + "DISCH_A"], [M + "DISCH_B"], 10, 0.4),
    ("creepage", [Z + "ZC_N1"], ["/LINE", "/NEUTRAL", Z + "ZC_LED_A"], 126.5, 1.6),
    ("creepage", [S + "VMEAS_N1"], ["/LINE", S + "VMEAS_N2"], 84.5, 1.4),
    ("creepage", [S + "VMEAS_N2"], [S + "VMEAS_DIV", "/NEUTRAL", S + "AMC_HGND", M + "NEUTRAL_IN"], 94.5, 1.4),
    ("creepage", [S + "VMEAS_N1"], [S + "VMEAS_DIV", "/NEUTRAL", S + "AMC_HGND", M + "NEUTRAL_IN"], 178.8, 1.8),
    ("creepage", ["/LINE"], [S + "VMEAS_N2"], 168.6, 1.7),
    ("creepage", GATE_AND_LED, ["/NEUTRAL"], 10, 0.4),
    ("clearance", GATE_AND_LED, ["/NEUTRAL"], 10, 0.2),
]
#: Each same-part pad pair under 1.5 mm in the committed main-board layout, and its edge-to-edge gap rounded down to 0.01 mm.
SAME_PART = [
    ("C601", "1", "2", 0.90), ("C602", "1", "2", 0.90), ("C603", "1", "2", 0.65), ("C604", "1", "2", 0.65), ("C605", "1", "2", 0.65),
    ("C606", "1", "2", 0.65), ("C608", "1", "2", 0.65), ("F601", "1", "2", 0.70), ("F602", "1", "2", 0.70),
    ("R105", "1", "2", 0.44), ("R105", "1", "3", 0.44), ("R105", "4", "2", 0.44), ("R105", "4", "3", 0.44), ("R105", "2", "3", 1.19),
    ("R604", "1", "2", 0.85), ("R605", "1", "2", 0.85), ("R606", "1", "2", 0.85), ("R607", "1", "2", 0.85), ("R608", "1", "2", 0.85),
    ("U601", "1", "2", 0.67), ("U601", "2", "3", 0.67), ("U601", "3", "4", 0.67), ("U601", "4", "5", 0.67), ("U601", "7", "8", 0.67),
    ("U601", "8", "9", 0.67), ("U601", "9", "10", 0.67), ("U602", "1", "2", 1.04),
]


def decimal(value):
    return fractions.Fraction(str(value))


def held_across(entry, held_pairs):
    """The held pairs an entry lists on opposite sides, as the check refuses them."""
    first = list(entry["nets_a"])
    second = list(entry.get("nets_b") or first)
    return [(one, other) for one, other in held_pairs if (one in first and other in second) or (other in first and one in second)]


SET_N_CAVEAT = (
    "while the circuit is intact", "R604 open", "VMEAS_DIV floats toward the divider",
    "R604 open", "VMEAS_DIV floats toward the divider", "loss of NEUTRAL", "0.281 mA", "no AMC_* net",
    "within about 1.2 V of NEUTRAL", "entries 10 and 11",
)
#: A row of the single-fault table: entry number, fault, volts, current in amperes, limiting element, arithmetic.
FAULT_ROW = re.compile(r"^\s*#\s+(\d+) \| fault: (.+?) \| volts: ([\d.]+) V \| current_a: ([\d.]+(?:e-?\d+)?) A \| limit: (.+?) \| arithmetic: (.+)$")


class NetPairAndSamePartDrafts(unittest.TestCase):
    """The net-pair and same-part entries drafted after the earlier entries of the committed record, unsigned."""

    def net_pairs(self, data):
        return [e for e in data["accepted_exceptions"] if "nets_a" in e]

    def same_part(self, data):
        return [e for e in data["accepted_exceptions"][ORIGINAL_ENTRIES:] if "between" in e and e["between"][0].split(".")[0] not in NO_CONNECT_PART_REFS]

    def test_the_eleven_net_pair_entries_hold_the_lists_working_voltages_and_distances_the_leaf_sets(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C1: The record holds the eleven net-pair entries with the lists, working voltages and accepted distances this leaf sets
        _, data = committed()
        entries = self.net_pairs(data)
        found = [(e["constraint"], e["nets_a"], e.get("nets_b"), e["working_voltage_v"], e["accepted_mm"]) for e in entries]
        self.assertEqual(found, NET_PAIRS)
        self.assertEqual(len(entries), 11)
        self.assertEqual(len({(c, tuple(a), tuple(b or ()), v, k) for c, a, b, v, k in found}), 11)
        for entry in entries:
            self.assertEqual(entry["pair"], "mains_to_mains")
        _, problems = reading()
        self.assertEqual(sorted(p.location.rsplit(" ", 1)[-1] for p in problems), ["accepted_by", "accepted_on"])
        # the reader reads an entry whose list is emptied or whose voltage is dropped as broken
        first = data["accepted_exceptions"].index(entries[2])
        for key in ("nets_a", "working_voltage_v"):
            broken = list(data["accepted_exceptions"])
            broken[first] = {k: v for k, v in entries[2].items() if k != key}
            _, problems = reading(dict(data, accepted_exceptions=broken))
            self.assertTrue(any(p.location.endswith(f"accepted_exceptions[{first}].{'between' if key == 'nets_a' else key}") for p in problems), key)

    def test_every_listed_net_is_written_as_the_netlist_writes_it_and_none_repeats(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C2: Every net a net-pair entry lists is a Mains-class net of the main board. Inspected against the main board's project file and netlist on the branch that carries it: each of the nets below matches a Mains-class pattern of its net_settings and is a net of the netlist, and this test holds only the naming form and the distinctness of the lists.
        _, data = committed()
        known = set(SET_N) | set(GATE_AND_LED) | {M + "DISCH_A", M + "DISCH_B", "/LINE", Z + "ZC_N1", S + "VMEAS_N1", S + "VMEAS_N2"}
        for entry in self.net_pairs(data):
            for key in ("nets_a", "nets_b"):
                names = entry.get(key, [])
                self.assertEqual(len(names), len(set(names)), names)
                for name in names:
                    self.assertIsInstance(name, str)
                    self.assertTrue((name.startswith("/") or name.startswith("unconnected-(U")) and name == name.strip(), name)
                    self.assertIn(name, known)
        for name in known:
            self.assertEqual(name.count("/"), 0 if not name.startswith("/") else 1 if not name[1:].count("/") else 2, name)

    def test_each_accepted_distance_is_the_band_figure_for_its_working_voltage(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C3: Each creepage entry's accepted distance is the band figure for its working voltage
        _, data = committed()
        for entry in self.net_pairs(data):
            with self.subTest(nets=entry["nets_a"][:1], volts=entry["working_voltage_v"], constraint=entry["constraint"]):
                figure = board_check.band_figure(data, f"{entry['constraint']}_mm", entry["working_voltage_v"])
                self.assertEqual(decimal(entry["accepted_mm"]), figure)
                self.assertIsNone(board_check.net_pair_entry_problem(entry, data))
                lowered = dict(entry, accepted_mm=float(decimal(entry["accepted_mm"]) - fractions.Fraction(1, 10)))
                self.assertIsNotNone(board_check.net_pair_entry_problem(lowered, data), "a distance 0.1 mm below the band figure is refused")
                raised = dict(entry, working_voltage_v=entry["working_voltage_v"] + 1)
                if entry["constraint"] == "creepage" and entry["working_voltage_v"] >= 50:
                    # the same distance at a voltage one step up can fall under the next band figure; the helper judges it on the rows, not on the entry's own word
                    self.assertEqual(board_check.net_pair_entry_problem(raised, data) is None,
                                     decimal(entry["accepted_mm"]) >= board_check.band_figure(data, "creepage_mm", raised["working_voltage_v"]))
        ten = [e for e in self.net_pairs(data) if e["working_voltage_v"] == 10]
        self.assertEqual({(e["constraint"], e["accepted_mm"], tuple(e["nets_a"])) for e in ten if e["nets_a"] in (SET_N, GATE_AND_LED)},
                         {("creepage", 0.4, tuple(SET_N)), ("clearance", 0.2, tuple(SET_N)),
                          ("creepage", 0.4, tuple(GATE_AND_LED)), ("clearance", 0.2, tuple(GATE_AND_LED))})

    def test_no_entry_reduces_a_pair_that_can_reach_the_supply_voltage_or_a_held_pair(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C4: No net-pair entry reduces the figure of a pair that can reach the supply voltage or of a held pair
        _, data = committed()
        held = data["mains_to_mains"]["held_at_reinforced"]
        entries = self.net_pairs(data)
        for entry in entries:
            self.assertLess(entry["working_voltage_v"], 250, entry["nets_a"])
            self.assertLess(entry["working_voltage_v"], board_check.basis_voltage(data["working_voltage"]))
            self.assertEqual(held_across(entry, held), [], entry["nets_a"])
            listed = set(entry["nets_a"]) | set(entry.get("nets_b", []))
            for name in listed:
                leaf = name.rsplit("/", 1)[-1]
                for excluded in ("LINE_MOD", "LINE_IN", "LINE_F", "LINE1", "SNUB", "GATE_R", "MT2", "OPTO_MT"):
                    self.assertNotIn(excluded, leaf, name)
        # the check for a held pair can fail: the same entries with the held pair listed on opposite sides are caught
        crossed = dict(entries[2], nets_a=["/LINE"], nets_b=["/LINE1"])
        self.assertEqual(held_across(crossed, held), [("/LINE", "/LINE1")])
        crossed = dict(entries[2], nets_a=["/Mains entry and load feed/LINE_IN"], nets_b=["/LINE1"])
        self.assertEqual(len(held_across(crossed, held)), 1)
        # a triac gate net or the zero-cross LED anode is paired with /NEUTRAL alone, never listed in set N, and a gate
        # network net is in no entry; the one other entry listing the LED anode is the zero-cross midpoint's own
        def placed_right(entry):
            names = set(entry["nets_a"]) | set(entry.get("nets_b", []))
            if {P + "PUMP_C_GATE_R", P + "PUMP_S_GATE_R"} & names:
                return False
            if not names & set(GATE_AND_LED):
                return True
            if entry["nets_a"] == [Z + "ZC_N1"]:
                return True
            return entry["nets_a"] == GATE_AND_LED and entry.get("nets_b") == ["/NEUTRAL"]
        for entry in entries:
            self.assertTrue(placed_right(entry), entry["nets_a"])
        # the check can fail: a gate net in set N, against a measurement net, beside a second net, or a gate network net listed
        for bad in (dict(entries[0], nets_a=SET_N + [P + "PUMP_C_TRIAC_G"]), dict(entries[9], nets_b=[S + "AMC_AIN0P"]),
                    dict(entries[9], nets_b=["/NEUTRAL", Z + "ZC_LED_A"]), dict(entries[9], nets_a=GATE_AND_LED[:2]),
                    dict(entries[2], nets_a=[P + "PUMP_C_GATE_R"])):
            self.assertFalse(placed_right(bad), bad["nets_a"])

    def test_each_net_pair_reason_states_the_derivation_of_its_working_voltage(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C5: Each net-pair entry's reason states the derivation of its working voltage
        _, data = committed()
        entries = self.net_pairs(data)
        needles = {
            0: ("10 V", "0.000832639467", "2.7 V", "3.2 V", "fifteen"), 1: ("10 V", "0.2 mm", "fifteen"),
            2: ("253 / 2 = 126.5 V", "R101", "R104", "intact"), 3: ("126.5 V", "0.5 %", "10 V", "intact"),
            4: ("253 / 2 = 126.5 V", "R630", "R631", "intact"),
            5: ("0.666944", "0.333888", "253 x", "84.3 V is the value", "84.5 V written", "intact"),
            6: ("0.333888", "84.5 + 10 = 94.5", "intact"), 7: ("0.666944", "168.7 + 10 = 178.7", "178.8", "intact"),
            8: ("0.333888", "253 x (1 - 0.333888) = 168.5", "168.6", "intact"),
            9: ("1.2 V above NEUTRAL", "10 V band row (creepage 0.4 mm)", "PUMP_C_GATE_R", "microamps", "120.8 kohm", "2.09 mA", "rows 10"),
            10: ("1.2 V above NEUTRAL", "10 V band row (clearance 0.2 mm)", "PUMP_S_GATE_R", "microamps", "120.8 kohm", "2.09 mA", "rows 11"),
        }
        for position, entry in enumerate(entries):
            with self.subTest(position=position):
                for needle in needles[position]:
                    self.assertIn(needle, entry["reason"])
                self.assertIn("drafter's figure for the owner to accept or correct", entry["reason"])
                if 2 <= position <= 8:
                    self.assertIn(f"judged in row {position + 1} of the single-fault table", entry["reason"])
                self.assertTrue(entry["bounded_by"].strip())
                self.assertRegex(entry["bounded_by"], r"F101|branch fuses|energy")
                self.assertNotIn("the part itself", entry["bounded_by"])

    def test_the_set_n_reasons_state_the_reduction_holds_while_the_circuit_is_intact_and_name_the_fault_states(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C5: Each net-pair entry's reason states the derivation of its working voltage
        _, data = committed()
        entries = self.net_pairs(data)[:2]
        self.assertEqual([e["constraint"] for e in entries], ["creepage", "clearance"])
        for entry in entries:
            with self.subTest(constraint=entry["constraint"]):
                for needle in SET_N_CAVEAT:
                    self.assertIn(needle, entry["reason"])

    def test_each_same_part_pad_pair_under_1_5_mm_has_one_creepage_and_one_clearance_entry(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C6: The record holds a creepage entry and a clearance entry for each same-part pad pair under 1.5 mm
        _, data = committed()
        entries = self.same_part(data)
        self.assertEqual(len(entries), 2 * len(SAME_PART))
        self.assertEqual(len(SAME_PART), 27)
        for ref, one, other, gap in SAME_PART:
            with self.subTest(pair=f"{ref}.{one}-{other}"):
                found = [e for e in entries if e["between"] == [f"{ref}.{one}", f"{ref}.{other}"]]
                self.assertEqual(sorted(e["constraint"] for e in found), ["clearance", "creepage"])
                for entry in found:
                    self.assertEqual(entry["pair"], "mains_to_mains")
                    self.assertEqual(decimal(entry["accepted_mm"]), decimal(gap))
                    self.assertLess(entry["accepted_mm"], 1.5)
                    self.assertLess(entry["accepted_mm"], data["mains_to_mains"]["creepage_mm" if entry["constraint"] == "creepage" else "clearance_mm"])
        # a pair of one of these parts standing 1.5 mm or more apart, or a part whose pins clear the figure, has no entry
        pairs = {frozenset(e["between"]) for e in entries}
        for left, right in (("C607.1", "C607.2"), ("R105.1", "R105.4"), ("U601.1", "U601.3"), ("U601.8", "U601.10"), ("T701.1", "T701.3")):
            self.assertNotIn(frozenset((left, right)), pairs)
        self.assertEqual({e["between"][0].split(".")[0] for e in entries}.isdisjoint({"T701", "T711", "U701", "U711", "K201", "K731", "K741"}), True)
        _, problems = reading()
        self.assertEqual([p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))], [])

    def test_each_same_part_entry_states_its_ground_and_bounding_element(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C7: Each same-part entry states its ground and bounding element
        _, data = committed()
        for entry in self.same_part(data):
            with self.subTest(between=entry["between"], constraint=entry["constraint"]):
                for phrase in ("pitch of", "forces the gap", "set N", "under 10 V rms", "The part is not changed"):
                    self.assertIn(phrase, entry["reason"])
                self.assertIn(entry["between"][0].split(".")[0], entry["reason"])
                for phrase in ("neutral-referenced circuit can supply", "F101", "branch fuses"):
                    self.assertIn(phrase, entry["bounded_by"])
        # the two entries of one pair share their ground, so the texts cannot drift apart
        entries = self.same_part(data)
        for one, two in zip(entries[0::2], entries[1::2]):
            self.assertEqual((one["between"], one["reason"], one["bounded_by"]), (two["between"], two["reason"], two["bounded_by"]))

    def test_every_drafted_entry_is_unsigned_the_record_stays_unsigned_and_the_earlier_entries_are_unchanged(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C8: Every drafted entry is unsigned, the record stays unsigned and the existing entries are unchanged
        _, data = committed()
        assert_draft(self, data)
        entries = data["accepted_exceptions"]
        self.assertEqual(len(entries), ORIGINAL_ENTRIES + 11 + 54 + 8)
        self.assertEqual([e["between"][0].split(".")[0] for e in entries[-8:]], ["U701", "U701", "U701", "U701", "U711", "U711", "U711", "U711"])
        for entry in entries[ORIGINAL_ENTRIES:]:
            self.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""))
        _, problems = reading()
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("unsigned" in p.message for p in problems))
        earlier = [(e["pair"], e["constraint"], tuple(e.get("between") or ()), e.get("connector"), e["accepted_mm"]) for e in entries[:ORIGINAL_ENTRIES]]
        expected = ([("mains_to_mains", "creepage", pads, None, 2.0) for pads in (
            ("T701.2", "T701.1"), ("T701.2", "T701.3"), ("T711.2", "T711.1"), ("T711.2", "T711.3"))]
                    + [("mains_to_mains", "clearance", ("R105.1", "R105.4"), None, 1.65)]
                    + [("mains_to_mains", "clearance", (f"{ref}.1", f"{ref}.2"), None, 1.8)
                       for ref in ("R101", "R102", "R103", "R104", "R704", "R705", "R714", "R715")]
                    + [("mains_to_low_voltage", "creepage", pads, None, mm) for pads, mm in (
                        (("U601.10", "U601.11"), 8.0), (("U701.1", "U701.6"), 7.0), (("U711.1", "U711.6"), 7.0), (("U602.1", "U602.4"), 7.6),
                        (("U602.2", "U602.3"), 7.6), (("U602.1", "U602.3"), 7.6), (("U602.2", "U602.4"), 7.6))]
                    + [("same_connector_pins", "hole_to_hole", (), connector, 1.25) for connector in ("J630", "J635", "J791", "J821", "J861")])
        self.assertEqual(earlier, expected)
        # a signed copy is read as signed by the same reader, so the unsigned assertions above can fail
        signed = dict(data, accepted_by="someone", accepted_on="2026-10-01")
        _, problems = reading(signed)
        self.assertEqual([p for p in problems if p.location.endswith(("accepted_by", "accepted_on"))], [])


    def test_the_single_fault_table_has_a_bounded_row_for_each_net_pair_entry(self):
        # SOL-MAIN-BOARD-NET-PAIR-EXCEPTIONS-DRAFTED.C9: The record holds a single-fault table with a bounded row for each fault of each net-pair entry
        lines = [line for line in record_text().splitlines() if re.match(r"^\s*#\s+\d+ \| fault:", line)]
        rows = [FAULT_ROW.match(line) for line in lines]
        self.assertTrue(all(rows), "every table line has the five items in order")
        self.assertEqual(sorted({int(row.group(1)) for row in rows}), list(range(1, 12)))
        for row in rows:
            number, fault, volts, current, limit, arithmetic = row.groups()
            with self.subTest(number=number, fault=fault):
                self.assertGreater(float(volts), 0)
                self.assertLessEqual(float(volts), 253)
                self.assertGreater(float(current), 0)
                self.assertLess(float(current), 0.01)
                for part in (fault, limit, arithmetic):
                    self.assertTrue(part.strip())
                self.assertRegex(arithmetic, r"\d")
        by_number = {}
        for row in rows:
            by_number.setdefault(int(row.group(1)), []).append(row)
        # the current of each row is recomputed from the schematic's part values
        for number, ohms in ((1, 900000), (2, 900000), (3, 1000000), (4, 1000000), (5, 60400), (6, 600750), (7, 600750), (8, 600750), (9, 600750),
                             (10, 120800), (11, 120800)):
            self.assertAlmostEqual(float(by_number[number][0].group(4)), 253 / ohms, delta=0.006 * 253 / ohms, msg=number)
        for number in (10, 11):
            faults = " ".join(r.group(2) for r in by_number[number])
            self.assertIn("gate junction open while the opto-triac is off", faults)
            self.assertIn("U602 LED open", faults)
        for number in range(3, 10):
            self.assertIn("shorted", by_number[number][0].group(2))
        # the check can fail: a missing number, a row lacking an item, and a number beyond eleven are all found
        without_seven = [line for line in lines if not re.match(r"^\s*#\s+7 \|", line)]
        self.assertNotEqual(sorted({int(FAULT_ROW.match(line).group(1)) for line in without_seven}), list(range(1, 12)))
        self.assertIsNone(FAULT_ROW.match(lines[0].replace(" | limit:", " | lim:")))
        self.assertIsNone(FAULT_ROW.match(lines[0].replace(" | current_a:", " | amps:")))
        self.assertEqual(int(FAULT_ROW.match(lines[0].replace("#   1 |", "#   12 |")).group(1)), 12)



if __name__ == "__main__":
    unittest.main()
