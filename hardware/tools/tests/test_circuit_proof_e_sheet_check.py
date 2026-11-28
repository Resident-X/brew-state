"""The main board's measurement and high-side sheet check (circuit-proof/E_check_sheets.py), run in scratch copies of the committed proof folder and sheets: it passes the committed sheets, and it still fails a pin the net-tie symbol lacks and a symbol it does not know."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_circuit_proof_sheet_generator import read, scratch_copy  # noqa: E402

SCRIPT = "E_check_sheets.py"


def run(root, script):
    """The script, run on its scratch copy. Not under -I: the script imports PyYAML, which an isolated interpreter does not see where the package is installed for the user only; the folder it runs from is the scratch copy."""
    return subprocess.run([sys.executable, os.path.join(root, "circuit-proof", script)], cwd=root, capture_output=True, text=True, timeout=120)


def e1_path(root):
    (path,) = glob.glob(os.path.join(root, "sheets", "E1-*.yaml"))
    return path


def edit_e1(root, old, new):
    """Replace one exact text in the scratch copy's E1 sheet; the text must be there once."""
    path = e1_path(root)
    text = read(path)
    assert text.count(old) == 1, old
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(old, new))


class ESheetCheckTest(unittest.TestCase):
    def setUp(self):
        self.root = scratch_copy()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_committed_sheets_pass_with_the_net_tie_known(self):
        # SOL-CIRCUIT-PROOF-SHEET-CHECK-KNOWS-THE-NET-TIE-SYMBOL.C1: Run on the committed main board's sheet records for the measurement and high-side sheets, the proof script exits 0 and counts the net tie NT601 as a two-pin part whose pins 1 and 2 exist; run on a sheet record that names a pin the net-tie symbol does not have (a third pin), or a part whose symbol the script does not know, it exits non-zero and names that part. A test runs the script on the committed sheets and on one altered copy of each kind. Out of scope: any change to a sheet record, the schematic or the board, and the other proof scripts.
        result = run(self.root, SCRIPT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("NT601", result.stdout + result.stderr)
        self.assertIn("all sheets consistent", result.stdout)

    def test_a_third_net_tie_pin_is_refused_and_named(self):
        # SOL-CIRCUIT-PROOF-SHEET-CHECK-KNOWS-THE-NET-TIE-SYMBOL.C1: Run on the committed main board's sheet records for the measurement and high-side sheets, the proof script exits 0 and counts the net tie NT601 as a two-pin part whose pins 1 and 2 exist; run on a sheet record that names a pin the net-tie symbol does not have (a third pin), or a part whose symbol the script does not know, it exits non-zero and names that part. A test runs the script on the committed sheets and on one altered copy of each kind. Out of scope: any change to a sheet record, the schematic or the board, and the other proof scripts.
        edit_e1(self.root, "pins: [NT601.1]", "pins: [NT601.1, NT601.3]")
        result = run(self.root, SCRIPT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NT601.3 names a pin that does not exist", result.stdout + result.stderr)
        self.assertNotIn("NT601.1 names", result.stdout + result.stderr)
        self.assertNotIn("NT601.2 names", result.stdout + result.stderr)

    def test_a_part_with_an_unknown_symbol_is_refused_and_named(self):
        # SOL-CIRCUIT-PROOF-SHEET-CHECK-KNOWS-THE-NET-TIE-SYMBOL.C1: Run on the committed main board's sheet records for the measurement and high-side sheets, the proof script exits 0 and counts the net tie NT601 as a two-pin part whose pins 1 and 2 exist; run on a sheet record that names a pin the net-tie symbol does not have (a third pin), or a part whose symbol the script does not know, it exits non-zero and names that part. A test runs the script on the committed sheets and on one altered copy of each kind. Out of scope: any change to a sheet record, the schematic or the board, and the other proof scripts.
        edit_e1(self.root, "{ref: R601, lib_id: Device:R,", "{ref: R601, lib_id: Device:NoSuchSymbol,")
        result = run(self.root, SCRIPT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R601: unknown pin count for Device:NoSuchSymbol", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
