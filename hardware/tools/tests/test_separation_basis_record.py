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
        left = [p for p in problems if not p.location.endswith(("accepted_by", "accepted_on"))]
        self.assertEqual(left, [], [p.line() for p in left])
        if "accepted_by" not in data and "accepted_on" not in data:
            self.assertEqual(len(problems), 2)
            self.assertTrue(all("unsigned" in p.message for p in problems))
        else:
            self.assertEqual(problems, [])

    def test_every_barrier_has_exactly_one_type_and_the_floor_holds_on_its_own_figures(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry, giving its insulation type, ... The mains-to-low-voltage clearance and creepage are at or above the floor those rows give. It also runs the check's floor rule on the record's own figures taken as signed and finds no violation.
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

    def test_the_record_states_the_inputs_the_figures_are_read_at(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: It states the named standard, the declared supply and the working voltage at the top of its span, the pollution degree, the material group, the environment, the overvoltage category and the altitude, only the table rows its own inputs select, each with its citation.
        _, data = committed()
        for key in ("standard", "supply", "working_voltage", "pollution_degree", "material_group", "environment",
                    "overvoltage_category", "altitude_m", "table_rows"):
            self.assertTrue(data.get(key), key)
        self.assertEqual(board_check.basis_voltage(data["working_voltage"]), 253.0)
        self.assertEqual(data["pollution_degree"], 3)
        for row in data["table_rows"]:
            self.assertTrue(all(row["citation"][k].strip() for k in board_check.CITATION_KEYS))
        self.assertLessEqual(len(data["table_rows"]), 4)

    def test_a_barrier_without_an_entry_is_refused(self):
        # SOL-HW-SEPARATION-BASIS-SIGNED.C1: Every barrier named has exactly one barrier_types entry.
        _, data = committed()
        short = dict(data, barrier_types=data["barrier_types"][1:])
        _, problems = reading(short)
        self.assertTrue(any("holds no entry" in p.message for p in problems))


if __name__ == "__main__":
    unittest.main()
