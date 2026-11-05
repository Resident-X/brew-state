"""The committed derating policy of the Sunbeam EM7000 main board: its owner-signed exceptions, read by the board check's own reader and signature rule."""
from __future__ import annotations

import datetime
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
POLICY = os.path.join("hardware", "sunbeam-em7000", "main-board", board_check.DERATING_NAME)
#: The day the check is told it is: the day the policy was signed.
TODAY = datetime.date(2026, 11, 5)
#: The ten positions whose working voltage the derated-voltage rule finds over their limit at the top of the declared span, in the order the policy lists them.
POSITIONS = ("F101", "F701", "F711", "F731", "K731", "K741", "R102", "R104", "R706", "R716")
OWNER = "David Baker"


def committed():
    yaml = board_check.require_yaml()
    with open(os.path.join(REPO, POLICY), encoding="utf-8") as handle:
        return yaml, board_check.strict_yaml(yaml, handle.read())


class DeratingPolicySigned(unittest.TestCase):
    def test_the_ten_over_limit_positions_each_hold_one_owner_signed_exception_the_reader_accepts(self):
        # SOL-SEPARATION-BASIS-RECORD-STANDS-SIGNED-ON-THE-FINISHED-LAYOUTS-EXCEPTION-SET.C7: The committed main-board derating-policy.yaml holds exactly ten accepted_exceptions entries, for F101, F701, F711, F731, K731, K741, R102, R104, R706 and R716, one each, each holding exactly the keys position, accepted_v, reason, bounded_by, accepted_by and accepted_on, accepted_v a positive number, reason and bounded_by non-empty, accepted_by naming the owner and not a placeholder, accepted_on a valid date no later than the day the check runs, and the check's own signature rule finds each signed; an entry with its acceptance emptied, a placeholder or a future date is found unsigned by the same rule. The policy's classes and shares are unchanged. Out of scope is the derating rule's behaviour on a position.
        yaml, data = committed()
        entries = data["accepted_exceptions"]
        self.assertEqual([e["position"] for e in entries], list(POSITIONS))
        self.assertEqual(len({e["position"] for e in entries}), 10)
        for entry in entries:
            with self.subTest(position=entry["position"]):
                self.assertEqual(sorted(entry), sorted(board_check.DERATING_EXCEPTION_KEYS))
                self.assertIsInstance(entry["accepted_v"], (int, float))
                self.assertGreater(entry["accepted_v"], 0)
                self.assertTrue(entry["reason"].strip() and entry["bounded_by"].strip())
                self.assertIn(OWNER, entry["accepted_by"])
                self.assertIn("owner", entry["accepted_by"])
                self.assertFalse(board_check.is_placeholder(entry["accepted_by"]))
                day = board_check.iso_date(entry["accepted_on"])
                self.assertIsNotNone(day)
                self.assertLessEqual(day, datetime.date.today())
                self.assertIsNone(board_check.entry_unsigned(entry, None, TODAY))
                # the same rule finds the entry unsigned once its acceptance is emptied, a placeholder or dated after the day the check runs
                for field, value in (("accepted_by", ""), ("accepted_by", "tbd"), ("accepted_by", "<owner>"), ("accepted_on", ""),
                                     ("accepted_on", "not a date"), ("accepted_on", "2026-11-06")):
                    self.assertIsNotNone(board_check.entry_unsigned(dict(entry, **{field: value}), None, TODAY), (field, value))
        # the classes and their shares are those the owner adopted: the voltage share of each class the ten positions are held to
        shares = {c["class"]: c["voltage"]["share"] for c in data["classes"]}
        self.assertEqual(shares["capacitor"], 0.6)
        self.assertEqual(shares["resistor"], 1)
        self.assertEqual(shares["semiconductor"], 0.75)

    def test_the_checks_own_reader_accepts_the_policy_and_refuses_a_broken_entry(self):
        # SOL-SEPARATION-BASIS-RECORD-STANDS-SIGNED-ON-THE-FINISHED-LAYOUTS-EXCEPTION-SET.C7: The committed main-board derating-policy.yaml holds exactly ten accepted_exceptions entries, for F101, F701, F711, F731, K731, K741, R102, R104, R706 and R716, one each, each holding exactly the keys position, accepted_v, reason, bounded_by, accepted_by and accepted_on, accepted_v a positive number, reason and bounded_by non-empty, accepted_by naming the owner and not a placeholder, accepted_on a valid date no later than the day the check runs, and the check's own signature rule finds each signed; an entry with its acceptance emptied, a placeholder or a future date is found unsigned by the same rule. The policy's classes and shares are unchanged. Out of scope is the derating rule's behaviour on a position.
        import tempfile
        yaml, data = committed()
        files = board_check.tracked_files("git", REPO)
        repository = board_check.Repository(REPO, files)
        designs, _, _ = board_check.discover(REPO, files)
        main = [design for design in designs if design.directory.replace(os.sep, "/").endswith("sunbeam-em7000/main-board")]
        self.assertEqual(len(main), 1)
        self.assertEqual(board_check.read_derating(yaml, REPO, repository, main[0], False), [])
        # a copy of the policy with an entry's key removed, an accepted_v of zero or a repeated position is refused by the same reader
        with tempfile.TemporaryDirectory() as folder:
            folder_design = os.path.join("hardware", "sunbeam-em7000", "main-board")
            os.makedirs(os.path.join(folder, folder_design))
            for name in os.listdir(os.path.join(REPO, folder_design)):
                if name.endswith(".kicad_pro"):
                    with open(os.path.join(REPO, folder_design, name), encoding="utf-8") as source, \
                            open(os.path.join(folder, folder_design, name), "w", encoding="utf-8") as target:
                        target.write(source.read())
            tracked = [os.path.join(folder_design, name) for name in os.listdir(os.path.join(folder, folder_design))]
            tracked.append(os.path.join(folder_design, board_check.DERATING_NAME))
            copy = board_check.Repository(folder, tracked)
            local = board_check.Design(os.path.join(folder_design, next(n for n in os.listdir(os.path.join(folder, folder_design)) if n.endswith(".kicad_pro"))))
            for label, broken in (
                    ("a key removed", [{k: v for k, v in data["accepted_exceptions"][0].items() if k != "bounded_by"}] + data["accepted_exceptions"][1:]),
                    ("accepted_v zero", [dict(data["accepted_exceptions"][0], accepted_v=0)] + data["accepted_exceptions"][1:]),
                    ("a position repeated", data["accepted_exceptions"] + [dict(data["accepted_exceptions"][1], position="F101")])):
                with open(os.path.join(folder, folder_design, board_check.DERATING_NAME), "w", encoding="utf-8") as handle:
                    yaml.safe_dump(dict(data, accepted_exceptions=broken), handle)
                found = board_check.read_derating(yaml, folder, copy, local, False)
                self.assertTrue(found, label)
                self.assertTrue(all(v.rule == "derating_record" for v in found), (label, [v.line() for v in found]))


if __name__ == "__main__":
    unittest.main()
