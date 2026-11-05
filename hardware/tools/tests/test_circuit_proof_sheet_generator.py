"""The main board's circuit-proof sheet generator, run in scratch copies of the committed proof folder: it writes the committed sheets, its own check reports a difference when one appears, and its parts table names only parts the committed sheets carry."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board")
PROOF = os.path.join(BOARD, "circuit-proof")
SHEETS = os.path.join(BOARD, "sheets")
#: The sheet files the generator writes, in the sheets folder.
WRITTEN = ("50-thermistor-inputs.yaml", "52-flow-pressure-and-spare-analogue-inputs.yaml", "57-current-sensing-inputs.yaml")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def scratch_copy():
    """A scratch copy of the proof folder and the sheets folder, laid out as the generator expects (the sheets beside the proof folder)."""
    root = tempfile.mkdtemp(prefix="proof-gen-")
    shutil.copytree(PROOF, os.path.join(root, "circuit-proof"), ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SHEETS, os.path.join(root, "sheets"), ignore=shutil.ignore_patterns("__pycache__"))
    return root


def run(root, script):
    return subprocess.run([sys.executable, "-I", os.path.join(root, "circuit-proof", script)], capture_output=True, text=True, timeout=120)


def committed_references():
    """Every reference designator on a committed schematic sheet of the board."""
    refs = set()
    for name in os.listdir(BOARD):
        if name.endswith(".kicad_sch"):
            refs.update(re.findall(r'\(property "Reference" "([A-Z]+[0-9]+)"', read(os.path.join(BOARD, name))))
    return refs


def table_references(root):
    """Every reference designator in the generator's parts table, taken from its own sheets."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", os.path.join(root, "circuit-proof", "C_gen_sheets.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return {part["ref"] for sheet, _ in gen.WRITTEN for part in sheet.parts}


def dnp_flags(text):
    """The do-not-populate flag of each part of a sheet file, by reference."""
    flags = {}
    for block in re.split(r"(?m)^  - ref: ", text.split("\nnets:", 1)[0])[1:]:
        flags[block.split("\n", 1)[0]] = re.search(r"(?m)^    dnp: (true|false)$", block).group(1) == "true"
    return flags


def test_point_names(path):
    return set(re.findall(r"\bTP[0-9]+\b", read(path)))


class SheetGenerator(unittest.TestCase):
    def setUp(self):
        self.root = scratch_copy()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_the_generator_writes_each_committed_sheet_it_writes_unchanged_and_the_proofs_check_agrees(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C1: Running the generator on a clean checkout writes, for each sheet it writes, a file that is identical to the committed sheet, and the proof's own sheet check reports no difference. Out of scope is any edit to a committed sheet to make it match the generator.
        # start from sheets that differ from the committed ones, so a generator that wrote nothing would be found
        for name in WRITTEN:
            os.remove(os.path.join(self.root, "sheets", name))
        done = run(self.root, "C_gen_sheets.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("wrote 3 sheet fragments", done.stdout)
        for name in WRITTEN:
            with self.subTest(sheet=name):
                self.assertEqual(read(os.path.join(self.root, "sheets", name)), read(os.path.join(SHEETS, name)))
        checked = run(self.root, "C_check_sheets.py")
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("problems: 0", checked.stdout)
        for name in WRITTEN:
            self.assertIn(f"{name}", checked.stdout)
            self.assertIn("identical to the committed sheet", checked.stdout)
        # the fit of the flow-meter input is the committed one: the buffer and its capacitor fitted, the link position and the two burden positions not
        flow, current = dnp_flags(read(os.path.join(self.root, "sheets", WRITTEN[1]))), dnp_flags(read(os.path.join(self.root, "sheets", WRITTEN[2])))
        self.assertEqual((flow["R522"], flow["U520"], flow["C521"]), (True, False, False))
        self.assertEqual((current["R572"], current["R576"]), (True, True))

    def test_the_check_reports_a_committed_sheet_that_the_generator_would_not_write(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C1: Running the generator on a clean checkout writes, for each sheet it writes, a file that is identical to the committed sheet, and the proof's own sheet check reports no difference. Out of scope is any edit to a committed sheet to make it match the generator.
        target = os.path.join(self.root, "sheets", WRITTEN[1])
        text = read(target)
        # the old fit: the link position fitted, the buffer not
        self.assertIn("    dnp: true\n", text)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text.replace("    dnp: true\n", "    dnp: false\n", 1))
        checked = run(self.root, "C_check_sheets.py")
        self.assertEqual(checked.returncode, 1, checked.stdout)
        self.assertIn(f"generator output differs from the committed sheet {WRITTEN[1]}", checked.stdout)
        self.assertIn("problems: 1", checked.stdout)
        # the check wrote nothing over the committed sheet
        self.assertEqual(read(target), text.replace("    dnp: true\n", "    dnp: false\n", 1))

    def test_the_parts_table_names_only_parts_on_the_committed_sheets_and_no_test_point_the_board_has_lost(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C2: Every reference designator in the generator's parts table appears on a committed sheet of the board, and no test point removed from the board is named in the generator's source or in the decks and records that read its table. A reference designator that is on a committed sheet and absent from the table is listed with its reason. Out of scope is any change to a committed sheet.
        on_board = committed_references()
        self.assertTrue(on_board, "no reference read from the committed sheets")
        table = table_references(self.root)
        self.assertEqual(sorted(table - on_board), [])
        # the sheets the generator writes carry no part the table lacks, so no reference is left to list with a reason
        written = set()
        for name in WRITTEN:
            written.update(re.findall(r"^  - ref: (\S+)$", read(os.path.join(SHEETS, name)), re.M))
        self.assertEqual(sorted(written - table), [])
        self.assertEqual(sorted(table - written), [])
        # no test point the board no longer carries is named by the source, a deck or the record
        named = test_point_names(os.path.join(PROOF, "C_gen_sheets.py")) | test_point_names(os.path.join(PROOF, "C_gen_decks.py"))
        named |= test_point_names(os.path.join(BOARD, "circuit-proof.md"))
        for name in os.listdir(PROOF):
            if name.endswith(".cir"):
                named |= test_point_names(os.path.join(PROOF, name))
        self.assertEqual(sorted(named - on_board), [])
        # the same comparison finds a reference the board does not carry (a synthetic table entry, a removed test point)
        self.assertEqual(sorted((table | {"TP999"}) - on_board), ["TP999"])


class ProofDecks(unittest.TestCase):
    """The proof's decks model the fit the committed sheets carry."""

    def deck(self, name):
        return read(os.path.join(PROOF, name))

    def test_no_deck_carries_a_part_the_committed_sheets_mark_do_not_populate(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C3: No deck of the proof that reads the generator's parts table carries a part the committed sheets mark do-not-populate, and the decks of the flow-meter input carry the fitted buffer and its supply capacitor, with the buffer's input leakage at the datasheet maximum, and the committed log of each holds every measurement the deck asks for. Out of scope is any change to a committed sheet.
        unfitted = set()
        for name in WRITTEN:
            unfitted.update(ref for ref, flag in dnp_flags(read(os.path.join(SHEETS, name))).items() if flag)
        self.assertEqual(sorted(unfitted), ["R522", "R572", "R576"])
        decks = [n for n in os.listdir(PROOF) if re.match(r"C_.*\.cir$", n)]
        self.assertGreaterEqual(len(decks), 20)
        for name in decks:
            elements = {line.split()[0] for line in self.deck(name).splitlines() if line.strip() and line[0] not in "*.+"}
            with self.subTest(deck=name):
                self.assertEqual(sorted(elements & unfitted), [])

    def test_the_flow_decks_carry_the_fitted_buffer_and_its_capacitor_and_not_the_unfitted_link(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C3: No deck of the proof that reads the generator's parts table carries a part the committed sheets mark do-not-populate, and the decks of the flow-meter input carry the fitted buffer and its supply capacitor, with the buffer's input leakage at the datasheet maximum, and the committed log of each holds every measurement the deck asks for. Out of scope is any change to a committed sheet.
        for name in ("C_flow_od.cir", "C_flow_pp.cir"):
            text = self.deck(name)
            elements = {line.split()[0] for line in text.splitlines() if line.strip() and line[0] not in "*.+"}
            with self.subTest(deck=name):
                self.assertNotIn("R522", elements)
                self.assertIn("C521", elements)
                self.assertIn("SSIM_U520H", elements)
                self.assertIn("SSIM_U520L", elements)
                self.assertIn("ISIM_U520IN", elements)
                self.assertIn("as built (U520 fitted, link R522 not fitted)", text.splitlines()[0])
                # the buffer's input leakage is the SN74LVC1G17 maximum, 5 uA, and the open-drain deck draws it out of the node
                self.assertRegex(text, r"(?m)^ISIM_U520IN FLOW_F 0 -?5u$")
        self.assertRegex(self.deck("C_flow_od.cir"), r"(?m)^ISIM_U520IN FLOW_F 0 5u$")
        self.assertRegex(self.deck("C_flow_pp.cir"), r"(?m)^ISIM_U520IN FLOW_F 0 -5u$")

    def test_each_flow_deck_log_holds_every_measurement_the_deck_asks_for(self):
        # SOL-HW-MAIN-BOARD-SHEET-GENERATOR-REPRODUCES-COMMITTED-SHEETS.C3: No deck of the proof that reads the generator's parts table carries a part the committed sheets mark do-not-populate, and the decks of the flow-meter input carry the fitted buffer and its supply capacitor, with the buffer's input leakage at the datasheet maximum, and the committed log of each holds every measurement the deck asks for. Out of scope is any change to a committed sheet.
        for name in ("C_flow_od", "C_flow_pp"):
            deck, log = self.deck(name + ".cir"), self.deck(name + ".log")
            asked = re.findall(r"(?m)^\s*meas tran (\w+) ", deck)
            self.assertTrue(asked)
            for measurement in asked:
                with self.subTest(deck=name, measurement=measurement):
                    self.assertRegex(log, r"(?mi)^%s\s*=\s*[-+0-9.eE]+" % re.escape(measurement))
        # the filter node at the buffer's input stays under the buffer's 5.5 V recommended input limit, and the pin sees the buffer's output
        log = self.deck("C_flow_pp.log")
        high = float(re.search(r"(?m)^vhigh_pp_5p25\s*=\s*([-+0-9.eE]+)", log).group(1))
        pin = float(re.search(r"(?m)^vpin_hi_pp_5p25\s*=\s*([-+0-9.eE]+)", log).group(1))
        self.assertLess(high, 5.5)
        self.assertGreater(high, 5.25)
        self.assertLess(pin, 3.7)


if __name__ == "__main__":
    unittest.main()
