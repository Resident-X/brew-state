"""The committed separation basis record of the Sunbeam EM7000 machine, read by the board check's own reader."""
from __future__ import annotations

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import board_check  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
RECORD = os.path.join("hardware", "sunbeam-em7000", board_check.RECORD_NAME)
DESIGN = board_check.Design(os.path.join("hardware", "sunbeam-em7000", "board", "board.kicad_pro"))
TODAY = datetime.date(2026, 10, 23)


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
        case.assertEqual((entry["accepted_by"], entry["accepted_on"]), ("", ""), entry.get("between") or entry["connector"])


class SeparationBasisRecord(unittest.TestCase):
    def test_only_the_unsigned_acceptance_is_left_to_find(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: A separation basis record, not marked synthetic, sits in the machine's hardware folder in the form the separation-basis decision sets. A test reads the committed record through the board check's own reader and finds the only problems, if any, to be the unsigned acceptance until the owner signs, and none once signed.
        yaml, data = committed()
        self.assertIsNot(data.get("synthetic"), True)
        _, problems = reading()
        left = [p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))]
        self.assertEqual(left, [], [p.line() for p in left])
        # the draft state is pinned: the owner-acts leaf SOL-SEPARATION-BASIS-RECORD-MAINS-TO-MAINS-ACCEPTED-BY-OWNER changes this assertion when the owner accepts
        assert_draft(self, data)
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("unsigned" in p.message for p in problems))

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
        self.assertEqual(len(mains), 6)
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
        self.assertEqual(data["pollution_degree"], 3)
        for row in data["table_rows"]:
            self.assertTrue(all(row["citation"][k].strip() for k in board_check.CITATION_KEYS))
        strongest = max((entry["insulation"] for entry in data["barrier_types"]), key=board_check.STRENGTH.get)
        for row in data["table_rows"]:
            # a row of basic insulation is the floor of the mains-to-mains figures, so it is read at its own insulation
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
                     ("pollution_degree", 2, low_clearance + low_creepage + mains_clearance + mains_creepage),
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
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C1: The committed record holds mains_to_mains with clearance_mm 1.5, terminal_clearance_mm 2.0, creepage_mm 4.1, creepage_ahead_of_fuse_mm 4.1, entry_fuse F101 and held_at_reinforced, and the check's own reader reads it with no problem other than the unsigned acceptance until the owner signs. The mains_to_low_voltage figures are out of scope and read 3.0 mm and 10.0 mm as before.
        _, data = committed()
        assert_draft(self, data)
        held = data["mains_to_mains"]
        self.assertEqual({key: held[key] for key in ("clearance_mm", "terminal_clearance_mm", "creepage_mm", "creepage_ahead_of_fuse_mm")},
                         {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 4.1, "creepage_ahead_of_fuse_mm": 4.1})
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
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C1: The committed record holds mains_to_mains with clearance_mm 1.5, terminal_clearance_mm 2.0, creepage_mm 4.1, creepage_ahead_of_fuse_mm 4.1, entry_fuse F101 and held_at_reinforced, and the check's own reader reads it with no problem other than the unsigned acceptance until the owner signs. The mains_to_low_voltage figures are out of scope and read 3.0 mm and 10.0 mm as before.
        _, data = committed()
        held = data["mains_to_mains"]
        for key, value in (("entry_fuse", ""), ("clearance_mm", 0), ("creepage_mm", "4.1")):
            _, problems = reading(dict(data, mains_to_mains=dict(held, **{key: value})))
            self.assertTrue(any(f"mains_to_mains.{key}" in p.location for p in problems), key)
        _, problems = reading(dict(data, mains_to_mains=dict(held, terminal_clearance_mm=1.0)))
        self.assertTrue(any("terminal_clearance_mm" in p.location for p in problems))

    def test_every_figure_rests_on_a_cited_row_and_a_figure_below_its_floor_fails(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C2: The record's table_rows hold a row for each figure: the clearance row (2.5 kV), a terminal row carrying location terminal, and a derived creepage row at 253 V whose figure is the interpolation of the 250 V and 320 V rows, 4.04 mm, signed rounded up to 4.1 mm, a deliberate 0.1 mm design margin over the standard's own rounded result of 4.0 mm, its citation naming both rows, the arithmetic and the clause that allows the interpolation (IEC 60664-1:2007 clause 5.2.4, per the 2007 edition, rows as read from reproductions), and stating the margin. The floor the check holds is the project's round-up, 4.1 mm, not the standard's rounding, 4.0 mm. The derived row restates the inputs it was read at, material group included, as signed. Each row has its citation (document, edition and the table and row), its inputs and its figure. The check's floor rule, run on the record's own figures taken as signed, finds no figure below its floor, and a creepage figure of 4.0 mm would fail it. Rows for the mains_to_low_voltage figures are out of scope and stay as signed.
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
        self.assertEqual(clearance["inputs"].get("working_voltage_v"), 300)
        self.assertIn("2.5 kV", clearance["citation"]["locator"])
        self.assertEqual(terminal["inputs"]["location"], "terminal")
        self.assertEqual(terminal["figure"]["clearance_mm"], 2.0)
        self.assertEqual(derived["inputs"]["working_voltage_v"], 253)
        self.assertEqual(derived["inputs"]["material_group"], data["material_group"])
        self.assertEqual(derived["figure"]["creepage_mm"], 4.1)
        cited = " ".join(derived["citation"].values())
        for phrase in ("250 V", "320 V", "4.0 + (5.0 - 4.0) x (253 - 250) / (320 - 250)", "4.04 mm", "clause 5.2.4", "0.1 mm"):
            self.assertIn(phrase, cited)
        # the floor rule finds nothing below its floor on the record's own figures, and each figure is held to its row
        signed = signed_from(data)
        self.assertEqual(board_check.separation_floor(DESIGN, RECORD, signed), [])
        for key, low in (("creepage_mm", 4.0), ("creepage_ahead_of_fuse_mm", 4.0), ("clearance_mm", 1.4), ("terminal_clearance_mm", 1.9)):
            held = dict(data["mains_to_mains"], **{key: low})
            if key == "clearance_mm":
                held["terminal_clearance_mm"] = 2.0
            found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=held)))
            self.assertEqual([p.location.split(" ", 1)[1] for p in found], [f"mains_to_mains.{key}"], key)
            self.assertIn("below the", found[0].message)
        # the figures at their floor pass
        at_floor = dict(data["mains_to_mains"], creepage_mm=4.1, creepage_ahead_of_fuse_mm=4.1, clearance_mm=1.5, terminal_clearance_mm=2.0)
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
        entries = [e for e in data["accepted_exceptions"] if e["pair"] == "mains_to_mains"]
        found = {(tuple(e["between"]), e["accepted_mm"]) for e in entries}
        expected = {(("T701.2", "T701.1"), 1.08), (("T701.2", "T701.3"), 1.08), (("T711.2", "T711.1"), 1.08), (("T711.2", "T711.3"), 1.08),
                    (("R105.1", "R105.4"), 1.65)}
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
        # the triac shortfall is the gap between two lead pads, and the reason says the tab is not excused
        for entry in entries:
            if entry["between"][0] in ("T701.2", "T711.2"):
                self.assertIn("lead-pad to lead-pad", entry["reason"])
                self.assertIn("does not excuse the triac's tab", entry["reason"])
                self.assertNotIn("tab lead", entry["reason"])
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
        lower = dict(held, creepage_mm=3.0)
        _, problems = reading(dict(data, mains_to_mains=lower))
        self.assertTrue(any("downstream_basis" in p.message for p in problems))
        stated = dict(lower, downstream_basis="a prospective fault current and the entry fuse clearing a tracking fault at it")
        _, problems = reading(dict(data, mains_to_mains=stated))
        self.assertFalse(any("downstream_basis" in p.message for p in problems))
        # with a stated basis the floor is the functional row, which this record does not carry, so the lower figure still fails by name
        found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, mains_to_mains=stated)))
        self.assertEqual([p.location.split(" ", 1)[1] for p in found], ["mains_to_mains.creepage_mm"])
        self.assertIn("functional", found[0].message)


DIVISION = os.path.join("docs", "sunbeam-em7000", "controller-board-division.md")


def record_text():
    with open(os.path.join(ROOT, RECORD), encoding="utf-8") as handle:
        return handle.read()


class MainsToMainsReadings(unittest.TestCase):
    """What the committed record and the division record say about the readings behind the mains-to-mains figures."""

    def test_the_division_record_restates_the_signed_figures_and_holds_no_old_bound(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C6: The board division record no longer holds the 3.0 mm and 5.0 mm upper bound for mains copper of different nets, or says the basis gives no mains-to-mains figure, anywhere it appears. The restatements to correct are its separation row, assumption A3, the option row on the second division (about line 267), the paragraph on mains against mains (about 357), the rule list (about 378), finding 3 (about 1095), the verification table's creepage row (about 1193) and its row 6 on the wall edge and the bracket (about 1194), the 5.0 mm wall-edge distance in the opening table (about 32), and the verification script's docstring, its guards and its expected-output strings and seeded faults (from about 2919), each stating the signed figures, the interpolated row selection and the accepted exceptions. A search of the division record, the layout plans and the design constraints for the old bound and for 'basic creepage' finds no other, and any found is aligned. The basic mains-to-earth pair (D15 and the bracket paragraph) keeps its separate decision but states 4.1 mm from the same row selection. A layout plan that does not exist yet is out of scope.
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
        for phrase in ("250 V row (4.0 mm) and 320 V row (5.0 mm)", "253 V", "rounded up", stated["terminal"],
                       "T701 and T711 at 1.08 mm", "R105 at 1.65 mm", "1206 series resistors at 1.8 mm"):
            self.assertIn(phrase, a3, phrase)
        # the mains-to-earth pair states the same row selection
        d15 = text[text.index("**D15."):]
        d15 = d15[:d15.index("\n")]
        self.assertIn("4.1 mm", d15)
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
                       "SOL-HW-MAIN-BOARD-PROVEN-AND-LAID-OUT", "no laminate is chosen yet", "only up to a working voltage of 50 V",
                       "equal for IIIa and IIIb", "was not read"):
            self.assertIn(phrase, " ".join(comments.split()), phrase)
        # every row that states a group states IIIa, the derived creepage row included, and the 10.0 mm figure is unchanged
        groups = {row["inputs"]["material_group"] for row in data["table_rows"] if "material_group" in row["inputs"]}
        self.assertEqual(groups, {"IIIa"})
        derived = next(row for row in data["table_rows"] if row["inputs"].get("working_voltage_v") == 253)
        self.assertEqual(derived["inputs"]["material_group"], "IIIa")
        self.assertEqual(data["mains_to_low_voltage"]["creepage_mm"], 10.0)
        # no laminate maker's document is cited
        self.assertNotIn("laminate maker", " ".join(row["citation"]["document"] for row in data["table_rows"]))

    def test_the_readings_for_the_owner_to_check_are_marked_and_the_interpolation_permission_is_stated_from_the_2007_text(self):
        # SOL-SEPARATION-BASIS-SIGNS-MAINS-TO-MAINS-SPACING-AND-EXCEPTIONS.C10: The record marks the 0.5 mm terminal allowance (Table 16 footnote of the household-appliance standard) as a reading from reproductions, with its source and its clause where the source gives one, unverified against the standard's own text, and the owner's acceptance includes checking it. The permission to interpolate creepage between voltage rows is verified against IEC 60664-1:2007 clause 5.2.4 (clause 5.2.3 carries the same wording for functional insulation): where the working voltage of 4.3.2.2.2 is used for dimensioning, interpolation for intermediate voltages is allowed, linear interpolation shall be used, and values are rounded to the same number of digits as the table values. That reading is of the 2007 edition text only; the 2020 edition and AMD1:2025 were not read. By that rounding rule the standard's own result at 253 V is 4.0 mm, so the signed 4.1 mm is a deliberate design margin of 0.1 mm over it and the record says so. Whether the household-appliance standard (IEC 60335-1) permits interpolation of its own creepage table is not verified, nothing having been found either way: the record carries that caveat and the fallback figure, the 320 V row, 5.0 mm, that applies if interpolation is refused, and the owner's signed acceptance of the record includes confirming the 60335-1 position, or the owner's or a test house's confirmation is recorded in the record, before certification. A clause the sources do not give is stated as not found, not guessed. The same owner check covers the material-group column of the 250 V and 320 V rows used: they are drafter readings of IEC 60664-1 Table F.4 from reproductions (pollution degree 3, group III: 250 V = 4.0 mm, 320 V = 5.0 mm). The comment in hardware/sunbeam-em7000/separation-basis.yaml near line 28, which says the 320 V row is used and no interpolation is made, is corrected to say that interpolation is permitted and that the larger 10.0 mm mains-to-low-voltage figure is kept deliberately. Reading the standard's own text beyond these points is out of scope.
        _, data = committed()
        terminal = next(row for row in data["table_rows"] if row["inputs"].get("location") == "terminal")
        marked = " ".join(terminal["citation"].values())
        for phrase in ("0.5 mm", "Table 16", "certification reports", "drafter's reading", "unverified", "not found"):
            self.assertIn(phrase, marked, phrase)
        derived = next(row for row in data["table_rows"] if row["inputs"].get("working_voltage_v") == 253)
        cited = " ".join(derived["citation"].values())
        for phrase in ("clause 5.2.4", "clause 5.2.3 for functional insulation", "2007 edition", "2020 edition and AMD1:2025 not read",
                       "drafter's reading", "IEC 60335-1", "not verified", "fallback is the 320 V row, 5.0 mm", "4.0 mm", "design margin of 0.1 mm"):
            self.assertIn(phrase, cited, phrase)
        text = " ".join(" ".join(line[1:].strip() for line in record_text().splitlines() if line.startswith("#")).split())
        for phrase in ("pollution degree 3, material group III: 250 V = 4.0 mm, 320 V = 5.0 mm", "linear interpolation for intermediate voltages",
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
        entries = [e for e in data["accepted_exceptions"] if e.get("between", [""])[0].startswith("U602.")]
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


if __name__ == "__main__":
    unittest.main()
