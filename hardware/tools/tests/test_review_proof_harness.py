"""The guards and hooks the review proof commands share, held once: the key a baseline is read under, the file shapes the kit
cannot use, the lock across a single run and its write, and the rows a seed may be matched against."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import review_proof_harness as harness  # noqa: E402
from review_kit import proof  # noqa: E402

KEY = proof.BaselineKey("a" * 8, "design", "model", proof.SINGLE, "p" * 8)
OTHER = proof.BaselineKey("b" * 8, "design", "model", proof.SINGLE, "p" * 8)


def run(run_id="one"):
    return proof.RunOutcome(run_id, proof.SINGLE, "tool", "seeded", ("S1",), (), {}, {"S1": ("single",)}, {"S1": ("single",)},
                            (proof.SessionRecord("single", 1.0, 1.0, 1, 1, 1),), 1.0, 1.0, ("first_call_read",))


class Held(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="review-proof-harness-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.path = os.path.join(self.root, "baselines.json")

    def write(self, content):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(content, handle)

    def group(self, key, runs):
        return {"key": key.as_dict(), "runs": [each.as_dict() for each in runs]}


# SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2 and SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: run again for a key whose
# baseline is recorded the proof command refuses to run the single form; the guard is the harness's, held once.
class TheGuard(Held):
    def test_a_key_is_recorded_absent_or_refused(self):
        self.assertIsNone(harness.recorded_under(self.path, KEY))
        self.write({"version": proof.BASELINES_VERSION, "baselines": [self.group(KEY, [run()])]})
        self.assertEqual([each.id for each in harness.recorded_under(self.path, KEY)], ["one"])
        self.assertIsNone(harness.recorded_under(self.path, OTHER), "a key the file does not hold is free")

    def test_a_key_held_with_no_runs_is_refused_naming_the_key_and_file_and_another_key_is_free(self):
        self.write({"version": proof.BASELINES_VERSION, "baselines": [self.group(KEY, [])]})
        with self.assertRaises(harness.Refused) as caught:
            harness.recorded_under(self.path, KEY)
        text = str(caught.exception)
        self.assertIn(self.path, text)
        self.assertIn(str(KEY), text)
        self.assertIn("no runs", text)
        self.assertIsNone(harness.recorded_under(self.path, OTHER))

    def test_every_shape_the_kit_cannot_use_is_refused(self):
        key = KEY.as_dict()
        for name, content in (("version", {"version": 0, "baselines": [self.group(KEY, [run()])]}),
                              ("no baselines", {"version": proof.BASELINES_VERSION, "baselines": []}),
                              ("not a list", {"version": proof.BASELINES_VERSION, "baselines": {}}),
                              ("no runs", {"version": proof.BASELINES_VERSION, "baselines": [{"key": key}]}),
                              ("run missing fields", {"version": proof.BASELINES_VERSION,
                                                      "baselines": [{"key": key, "runs": [{"id": "one"}]}]}),
                              ("not an object", [])):
            with self.subTest(name=name):
                self.write(content)
                with self.assertRaises(harness.Refused):
                    harness.recorded_under(self.path, KEY)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{")
        with self.assertRaises(harness.Refused):
            harness.recorded_under(self.path, KEY)


class TheLock(Held):
    def test_a_lock_held_is_refused_naming_it_and_released_when_the_block_ends(self):
        with harness.baseline_lock(self.path):
            with self.assertRaises(harness.Refused) as caught:
                with harness.baseline_lock(self.path):
                    self.fail("the second lock was taken")
            self.assertIn(self.path + ".lock", str(caught.exception))
        with harness.baseline_lock(self.path):
            pass

    def test_the_lock_is_released_when_the_block_raises(self):
        with self.assertRaises(RuntimeError):
            with harness.baseline_lock(self.path):
                raise RuntimeError("stop")
        with open(self.path + ".lock", "a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_a_baseline_written_for_one_key_keeps_the_one_already_in_the_file(self):
        self.assertIsNone(harness.recorded_under(self.path, OTHER))
        self.write({"version": proof.BASELINES_VERSION, "source": "x", "seeds": [], "baselines": [self.group(KEY, [run("kept")])]})
        harness.write_baseline(self.path, "y", [], OTHER, run("added"))
        loaded = proof.load_baselines(self.path)
        self.assertEqual([each.id for each in loaded.recorded(KEY)], ["kept"])
        self.assertEqual([each.id for each in loaded.recorded(OTHER)], ["added"])


class TheSeedRows(unittest.TestCase):
    def lane(self, tables):
        return types.SimpleNamespace(group="G1", replica=1, units=("u",), failure=None,
                                     unit_record=types.SimpleNamespace(standing=types.SimpleNamespace(tables=tables)))

    def test_rows_are_added_after_a_lane_s_findings_without_changing_the_lanes_given(self):
        lane = self.lane({"Findings": [{"Item": "A"}], "Verdicts": [{"Item": "B"}]})
        (wide,) = harness.widened([lane], "Findings", lambda tables: [{"Item": row["Item"]} for row in tables["Verdicts"]])
        self.assertEqual(wide.unit_record.standing.tables["Findings"], [{"Item": "A"}, {"Item": "B"}])
        self.assertEqual(lane.unit_record.standing.tables["Findings"], [{"Item": "A"}], "the lane given is as it was")
        self.assertEqual((wide.group, wide.replica, wide.units), ("G1", 1, ("u",)))

    def test_a_lane_with_no_tables_gets_only_the_rows_given(self):
        (wide,) = harness.widened([self.lane(None)], "Findings", lambda tables: [{"Item": "Z"}])
        self.assertEqual(wide.unit_record.standing.tables["Findings"], [{"Item": "Z"}])


if __name__ == "__main__":
    unittest.main()
