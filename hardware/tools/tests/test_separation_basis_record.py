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


class SeparationBasisRecord(unittest.TestCase):
    def test_only_the_unsigned_acceptance_is_left_to_find(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: A separation basis record, not marked synthetic, sits in the machine's hardware folder in the form the separation-basis decision sets. A test reads the committed record through the board check's own reader and finds the only problems, if any, to be the unsigned acceptance until the owner signs, and none once signed.
        yaml, data = committed()
        self.assertIsNot(data.get("synthetic"), True)
        _, problems = reading()
        # The machine's mains_to_mains figures are the record's own leaf to sign; this reads the record as it stands.
        problems = [p for p in problems if "mains_to_mains" not in p.location]
        left = [p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))]
        self.assertEqual(left, [], [p.line() for p in left])
        if "accepted_by" not in data and "accepted_on" not in data:
            self.assertEqual(len(problems), 2)
            self.assertTrue(all("unsigned" in p.message for p in problems))
        else:
            self.assertEqual(problems, [])

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
            self.assertTrue(board_check.row_applies(row["inputs"], data, 253.0, strongest), row["inputs"])
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
        # each mutation leaves the rows as drafted and changes the input they are read at; the keys are the figures left with no applicable row
        mutations = [("altitude_m", 3000, ["clearance_mm"]),
                     ("material_group", "IIIa", ["creepage_mm"]),
                     ("pollution_degree", 2, ["clearance_mm", "creepage_mm"]),
                     ("overvoltage_category", 3, ["clearance_mm"]),
                     ("working_voltage", "400 V rms", ["clearance_mm", "creepage_mm"])]
        for key, value, figures in mutations:
            found = board_check.separation_floor(DESIGN, RECORD, signed_from(dict(data, **{key: value})))
            self.assertEqual(sorted(p.location.rsplit(".", 1)[1] for p in found), sorted(figures), key)
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


if __name__ == "__main__":
    unittest.main()
