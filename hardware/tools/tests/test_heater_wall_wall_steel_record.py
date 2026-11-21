"""The wall's material record and the triacs' thermal judgement on it, for the Sunbeam EM7000 heater wall board.

The records are read as committed. Each rule is a function of the record's text, so a failing
case is the same text with one line changed. The arithmetic is checked against an oracle
written here from the stated model, not against the script's own constants.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import tempfile
import unittest
from typing import Dict, List, Tuple

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join(REPO, "hardware", "sunbeam-em7000", "heater-wall-board")
PROOF_DIR = os.path.join(BOARD, "circuit-proof")
SCRIPT = os.path.join(PROOF_DIR, "W_margins.py")
LOG = os.path.join(PROOF_DIR, "W_margins.log")
DIVISION = os.path.join(REPO, "docs", "sunbeam-em7000", "controller-board-division.md")

SECTION_TITLE = "## The wall's material and the triacs' thermal judgement on it"
OWNER_QUOTES = ("It is 2.5mm thick and non magnetic", "I made those scratches fairly easily with a screw driver")

H, L, T = 0.030, 0.080, 0.0025
LEG = 0.139 + 0.027
K_STAINLESS = 15.0


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def board(name: str) -> str:
    return read(os.path.join(BOARD, name))


def r_wall(k: float, h: float) -> float:
    return 1.0 / (h * H * L + 2 * (H + L) * math.sqrt(h * k * T))


def junction(k: float, air: float, h: float, rc: float, load: str) -> float:
    path = r_wall(k, h) + LEG + rc
    if load == "both on":
        return air + 9.09 * path + 9.09 * 0.5325 * (0.50 + 2.1)
    return air + 4.84 * (path + 0.50 + 2.1)


def section(proof: str) -> str:
    start = proof.index(SECTION_TITLE)
    end = proof.index("\n## ", start + 3)
    return proof[start:end]


def cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def quantity_rows(sec: str) -> Dict[str, List[str]]:
    """The first table of the section: quantity name to its cells."""
    rows = {}
    for line in sec.splitlines():
        if line.startswith("| ") and not line.startswith("| Quantity") and not line.startswith("| Air"):
            row = cells(line)
            if len(row) == 3:
                rows[row[0]] = row
    return rows


def case_rows(sec: str) -> List[List[str]]:
    rows = []
    for line in sec.splitlines():
        row = cells(line) if line.startswith("| ") else []
        if len(row) == 10 and row[0].isdigit():
            rows.append(row)
    return rows


def quantity_problems(sec: str, sign_off: str) -> List[str]:
    problems = []
    rows = quantity_rows(sec)
    for name in ("Material", "Magnetic grade", "Thickness at the cut", "Conductivity used", "Coating between plate and wall",
                 "Plate and paste", "Bolted-joint thermal resistance Rc"):
        if name not in rows:
            problems.append("no row for %s" % name)
        elif not rows[name][1] or not rows[name][2]:
            problems.append("%s states no value or no source" % name)
    if problems:
        return problems
    if "aluminium" not in rows["Material"][1].lower() or "non-magnetic" not in rows["Magnetic grade"][1]:
        problems.append("the material and grade are not aluminium, non-magnetic")
    if "2.5 mm" not in rows["Thickness at the cut"][1]:
        problems.append("the thickness is not 2.5 mm")
    cond = rows["Conductivity used"]
    if not cond[1].startswith("110 W/(m.K)") or "lowest plausible" not in cond[1] or "15 W/(m.K)" not in cond[1] or "bounding case" not in cond[1]:
        problems.append("the conductivity row does not state the lowest plausible figure with the stainless bounding case")
    if "mfgrobots.com" not in cond[2] or "read 2026-11-21" not in cond[2] or "110 to 140" not in cond[2]:
        problems.append("the conductivity has no source with its date and range")
    for address in ("https://www.mfgrobots.com/Article/material/metal/40251.html", "https://docs.rs-online.com/2d8e/A700000015689049.pdf"):
        if address not in cond[2]:
            problems.append("the conductivity source %s is not cited by its full address" % address)
    if "under the joint" not in rows["Coating between plate and wall"][1]:
        problems.append("the coating row does not say whether the finish lies under the joint")
    rc = rows["Bolted-joint thermal resistance Rc"]
    for needle in ("0, 1 and 3 K/W", "3 K/W as the stated limit", "No published source", "owner's measurement",
                   "DEL-HW-BRING-UP.C11", "W-5c", "asked once"):
        if needle not in rc[1] + " " + rc[2]:
            problems.append("the joint resistance row lacks '%s'" % needle)
    if not re.search(r"^- W-5c\.", sign_off, re.M):
        problems.append("the owner's existing acceptance W-5c is not in the sign-off record")
    return problems


def script_output(path: str = SCRIPT) -> Tuple[int, str]:
    done = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, cwd=os.path.dirname(path), check=False)
    return done.returncode, done.stdout


def script_cases(out: str) -> Dict[Tuple[float, float, float, float, str], float]:
    """(k, air, h, rc, load) to the junction the script prints for the 2026-11-21 amendment."""
    cases = {}
    k = None
    in_section = False
    for line in out.splitlines():
        if line.startswith("== (e) amendment 2026-11-21"):
            in_section = True
            continue
        if in_section and line.startswith("== "):
            break
        if not in_section:
            continue
        head = re.match(r"\s+-- wall: (aluminium|304 stainless), k (\d+) W", line)
        if head:
            k = float(head.group(2))
            continue
        row = re.match(r"\s+air (\d+) degC, h = +(\d+), Rc = (\d+) K/W, (both heaters on|steam heater alone) *: junction +([\d.]+) degC", line)
        if row and k is not None:
            load = "both on" if row.group(4).startswith("both") else "steam alone"
            cases[(k, float(row.group(1)), float(row.group(2)), float(row.group(3)), load)] = float(row.group(5))
    return cases


def table_problems(sec: str, out: str) -> List[str]:
    """What differs between the record's verdict table, the script's printed cases and the stated model."""
    problems = []
    rows = case_rows(sec)
    printed = script_cases(out)
    if len(rows) != 24:
        problems.append("the table holds %d cases, not 24" % len(rows))
    seen = set()
    for row in rows:
        air, h, rc = float(row[0]), float(row[1]), float(row[2])
        load = row[3]
        seen.add((air, h, rc, load))
        for k, col in ((110.0, 4), (15.0, 7)):
            junction_cell = float(row[col])
            oracle = junction(k, air, h, rc, load)
            if abs(junction_cell - oracle) > 0.006:
                problems.append("k %.0f %s: the table says %.2f, the model gives %.2f" % (k, row[:4], junction_cell, oracle))
            if abs(printed.get((k, air, h, rc, load), -1.0) - junction_cell) > 0.006:
                problems.append("k %.0f %s: the script prints %s, the table says %.2f" % (k, row[:4], printed.get((k, air, h, rc, load)), junction_cell))
            for limit, offset in ((125.0, 1), (100.0, 2)):
                expected = "holds" if junction_cell <= limit else "fails"
                if row[col + offset] != expected:
                    problems.append("k %.0f %s: %.0f degC verdict is %s, the figure says %s" % (k, row[:4], limit, row[col + offset], expected))
    if len(seen) != 24:
        problems.append("the table repeats or misses a case")
    return problems


def provisional_problems(sec: str, out: str) -> List[str]:
    problems = []
    lowered = sec.lower()
    if "provisional on the joint resistance only" not in lowered:
        problems.append("the judgement is not marked provisional on the joint resistance")
    if "w-5c" not in lowered or "DEL-HW-BRING-UP.C11" not in sec:
        problems.append("the shortfall is not recorded against W-5c and its carry")
    over = sorted((a, h, r, t) for (k, a, h, r, ld), t in script_cases(out).items() if k == 110.0 and t > 100.0)
    if not over:
        problems.append("the script finds no aluminium case over the 100 degC share to record")
    for air, h, rc, t in over:
        if "%.2f degC" % t not in sec:
            problems.append("the over-share case air %.0f h %.0f Rc %.0f (%.2f degC) is not stated in the reading" % (air, h, rc, t))
    aluminium = [t for (k, a, h, r, ld), t in script_cases(out).items() if k == 110.0]
    holding = sum(1 for t in aluminium if t <= 100.0)
    stated = "%d of %d hold the 100 degC share" % (holding, len(aluminium))
    if "Reading." in sec and stated not in sec:
        problems.append("the count of cases holding the share is not stated as %s" % stated)
    return problems


def statement_problems(sign_off: str, open_items: str) -> List[str]:
    problems = []
    entry = re.search(r"^- W-17\..*$", sign_off, re.M)
    if not entry:
        return ["owner-sign-off has no W-17 entry"]
    text = entry.group(0)
    if "accepted_by: David Baker (owner), in his words" not in text:
        problems.append("W-17 is not the owner's own words")
    if "accepted_on: 2026-11-21" not in text:
        problems.append("W-17 is not dated 2026-11-21")
    for quote in OWNER_QUOTES:
        if '"%s"' % quote not in text:
            problems.append("W-17 does not quote '%s' as given" % quote)
    for needle in ("scratch test", "No eddy-current (magnet-drag) test was made", "aluminium and not stainless"):
        if needle not in text:
            problems.append("W-17 lacks '%s'" % needle)
    own = sign_off.index("## Owner's own words")
    behalf = sign_off.index("## Signed on behalf")
    carried = sign_off.index("## Carried to named later steps")
    if not (own < sign_off.index("- W-17.") and not (behalf < sign_off.index("- W-17.") < carried)):
        problems.append("W-17 is not in the owner's-own-words section")
    body = sign_off[own:sign_off.index("## For David to sign or confirm")]
    entries = set(re.findall(r"^- (W-\d+[a-d]?)\b", body, re.M))
    count = re.search(r"There are (\d+) entries", sign_off)
    own_count = re.search(r"(\d+) are David Baker's own acceptance", sign_off)
    heading = re.search(r"## Owner's own words \((\d+) entries\)", sign_off)
    if not count or int(count.group(1)) != len(entries):
        problems.append("the header count differs from the %d entries held" % len(entries))
    behalf_heading = re.search(r"## Signed on behalf \((\d+) entries", sign_off)
    if not own_count or not heading or not behalf_heading or own_count.group(1) != heading.group(1) \
            or int(own_count.group(1)) != len(entries) - int(behalf_heading.group(1)):
        problems.append("the owner's-own-words counts disagree with the entries")
    row = next((l for l in open_items.splitlines() if l.startswith("| D11.")), "")
    if "owner-sign-off.md` W-17" not in row or "the cut measures the steel (a magnet and thickness check)" in row:
        problems.append("the D11 row still carries the owner's-measurement mark or does not cite W-17")
    return problems


def marks_problems(proof: str, division: str, open_items: str) -> List[str]:
    problems = []
    for name, text, stale in (
        ("circuit-proof", proof, "the owner finds them out at cutting"),
        ("division record", division, "the owner finds them out when cutting"),
        ("open-items", open_items, "a magnet and thickness check of the steel"),
    ):
        if stale in text:
            problems.append("%s still marks the wall's grade and thickness as the owner's measurement: '%s'" % (name, stale))
    return problems


def earth_bond_problems(sign_off: str, open_items: str) -> List[str]:
    problems = []
    entry = re.search(r"^- W-17\..*$", sign_off, re.M)
    text = entry.group(0) if entry else ""
    for name, blob in (("W-17", text), ("open-items", open_items)):
        for needle in ("screws that fix the plate to the wall", "DEL-HW-BRING-UP.C6", "serrated washer",
                       "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C10"):
            if needle not in blob:
                problems.append("%s lacks '%s'" % (name, needle))
    for name, blob in (("W-17", text), ("open-items", open_items)):
        if "drill the plate's fixing holes" not in blob or "not stated as done" not in blob and "not done" not in blob:
            problems.append("%s does not state the drilling as intent that is not done" % name)
    return problems


def outer_face_figures(k: float, air: float, h: float) -> str:
    """The outer-face temperature at the patch, both triacs on, from the stated model, to one decimal."""
    return "%.1f" % (air + 9.09 * r_wall(k, h))


def outer_face_problems(constraints: str, open_items: str, log: str) -> List[str]:
    """The outer-face statements: the recorded wall's own figures beside the stainless bounding case, and no steel assertion."""
    problems = []
    row = next((l for l in constraints.splitlines() if l.startswith("| Outer-face temperature of the")), "")
    para = next((l for l in open_items.splitlines() if l.startswith("**Outer-face temperature of the")), "")
    for name, blob in (("constraints row", row), ("open-items paragraph", para)):
        if not blob:
            problems.append("no %s" % name)
            continue
        if "steel sheet" in blob or "steel wall" in blob:
            problems.append("%s calls the wall steel" % name)
        if "aluminium" not in blob or "bounding case" not in blob or "W-17" not in blob:
            problems.append("%s does not state the aluminium wall with the stainless bounding case and the owner's statement" % name)
        for k in (110.0, K_STAINLESS):
            for air in (25.0, 40.0):
                for h in (10, 5):
                    figure = outer_face_figures(k, air, h)
                    if figure not in blob and "%.0f degC" % float(figure) not in blob:
                        problems.append("%s lacks the %.1f degC figure (k %.0f, air %.0f, h %d)" % (name, float(figure), k, air, h))
    for k in (110.0, K_STAINLESS):
        for air in (25.0, 40.0):
            for h in (10, 5):
                if "%s degC at h = %d" % (outer_face_figures(k, air, h), h) not in log:
                    problems.append("the log does not derive the %s degC figure (k %.0f, air %.0f, h %d)" % (outer_face_figures(k, air, h), k, air, h))
    return problems


class WallSteelRecord(unittest.TestCase):
    def setUp(self):
        self.proof = board("circuit-proof.md")
        self.sec = section(self.proof)
        self.sign_off = board("owner-sign-off.md")
        self.open_items = board("open-items.md")
        self.division = read(DIVISION)
        self.code, self.out = script_output()

    # SOL-HW-HEATER-WALL-BOARD-WALL-STEEL-RECORDED-AND-TRIAC-THERMAL-JUDGEMENT-HOLDS-ON-IT.C1: The heater wall board's records state the wall's material, its grade (magnetic or not) and its thickness at the owner's cut, the conductivity of that material at the lowest plausible value for its kind with the source, whether a coating lies between the spreader plate and the wall at the joint, and the thermal resistance of the bolted joint, each with its source; a quantity only the owner can measure on the machine is marked as the owner's measurement, states its bounding figure and names the measurement that closes it, and that mark is reconciled with the owner's recorded acceptance that carries the grade and thickness to the cut-time checks, so that the owner is asked once. Out of scope: measuring the wall on the owner's behalf and the cut's size, which the cut-confirmation work already covers.
    def test_the_outer_face_temperature_is_stated_for_the_recorded_wall_beside_the_stainless_bound(self):
        constraints = board("constraints-figures.md")
        self.assertEqual(outer_face_problems(constraints, self.open_items, self.out), [])
        stale = constraints.replace("The outer face is the same wall sheet the spreader plate is bolted to", "The outer face is the same steel sheet")
        self.assertNotEqual(stale, constraints)
        self.assertIn("calls the wall steel", " ".join(outer_face_problems(stale, self.open_items, self.out)))
        no_alu = self.open_items.replace("48.4 degC", "xx").replace("48 degC", "xx")
        self.assertTrue(outer_face_problems(constraints, no_alu, self.out))

    # SOL-HW-HEATER-WALL-BOARD-WALL-STEEL-RECORDED-AND-TRIAC-THERMAL-JUDGEMENT-HOLDS-ON-IT.C1: The heater wall board's records state the wall's material, its grade (magnetic or not) and its thickness at the owner's cut, the conductivity of that material at the lowest plausible value for its kind with the source, whether a coating lies between the spreader plate and the wall at the joint, and the thermal resistance of the bolted joint, each with its source; a quantity only the owner can measure on the machine is marked as the owner's measurement, states its bounding figure and names the measurement that closes it, and that mark is reconciled with the owner's recorded acceptance that carries the grade and thickness to the cut-time checks, so that the owner is asked once. Out of scope: measuring the wall on the owner's behalf and the cut's size, which the cut-confirmation work already covers.
    def test_every_wall_quantity_is_recorded_with_its_source(self):
        self.assertEqual(quantity_problems(self.sec, self.sign_off), [])

    def test_a_missing_source_or_joint_limit_is_found(self):
        broken = self.sec.replace("mfgrobots.com", "a supplier")
        self.assertTrue(any("source" in p for p in quantity_problems(broken, self.sign_off)))
        no_limit = self.sec.replace("3 K/W as the stated limit", "no stated limit")
        self.assertTrue(any("3 K/W as the stated limit" in p for p in quantity_problems(no_limit, self.sign_off)))
        no_mark = self.sec.replace("owner's measurement", "measurement")
        self.assertTrue(any("owner's measurement" in p for p in quantity_problems(no_mark, self.sign_off)))
        no_row = "\n".join(l for l in self.sec.splitlines() if not l.startswith("| Plate and paste"))
        self.assertIn("no row for Plate and paste", quantity_problems(no_row, self.sign_off))

    def test_the_conductivity_bound_in_the_script_is_the_recorded_one(self):
        recorded = quantity_rows(self.sec)["Conductivity used"][1]
        in_script = re.search(r"^K_ALU_LOW = ([\d.]+)", read(SCRIPT), re.M)
        self.assertIsNotNone(in_script)
        self.assertTrue(recorded.startswith("%d W/(m.K)" % float(in_script.group(1))))
        self.assertLessEqual(float(in_script.group(1)), 110.0, "the bound is above the lower end of the cited range")

    def test_the_owner_is_asked_once_for_the_joint_resistance(self):
        items = self.open_items[self.open_items.index("## The wall at the cut"):]
        items = items[:items.index("\n## ", 3)]
        self.assertIn("W-5c", items)
        self.assertIn("so he is asked once", items)
        self.assertIn("DEL-HW-BRING-UP.C11", items)
        entry = re.search(r"^- W-17\..*$", self.sign_off, re.M).group(0)
        self.assertIn("so he is asked once", entry)

    # SOL-HW-HEATER-WALL-BOARD-WALL-STEEL-RECORDED-AND-TRIAC-THERMAL-JUDGEMENT-HOLDS-ON-IT.C2: The triacs' thermal judgement of the wall assembly is re-stated on the material, thickness and joint resistance the records hold, with the arithmetic shown at the two external-air temperatures the live basis holds (25 and 40 degC), for both heaters on and for the steam heater alone, at each joint-resistance value the record carries, against the maker's 125 degC junction ceiling and the 100 degC policy share, with a pass or fail stated for each case. The wall-path figures at the stainless conductivity stay in the record as the stated bounding case beside the recorded material's. Each quantity still marked as the owner's measurement is taken at its stated bounding figure and the judgement is marked provisional until the owner's statement is on record, when it is re-stated on it. Where a case does not hold, the shortfall is recorded against the owner's existing acceptance of it, or the bracket's leg or the cut is changed and the owner's acceptance of the change is recorded. Does not cover re-selection of the triacs or any change to board copper.
    def test_the_script_runs_clean_and_its_log_is_current(self):
        self.assertEqual(self.code, 0, "W_margins.py reports a failed check")
        self.assertEqual(self.out, read(LOG), "W_margins.log is stale: regenerate it with python3 -I W_margins.py > W_margins.log")

    def test_the_verdict_table_agrees_with_the_script_and_the_model(self):
        self.assertEqual(table_problems(self.sec, self.out), [])

    def test_a_wrong_figure_or_verdict_in_the_table_is_found(self):
        row = next(l for l in self.sec.splitlines() if l.startswith("| 40 | 10 | 3 | both on |"))
        figure = cells(row)[4]
        wrong_figure = self.sec.replace(row, row.replace(figure, "%.2f" % (float(figure) - 10.0), 1))
        self.assertNotEqual(wrong_figure, self.sec)
        self.assertTrue(table_problems(wrong_figure, self.out))
        wrong_verdict = self.sec.replace(row, row.replace("fails", "holds", 1))
        self.assertTrue(any("verdict" in p for p in table_problems(wrong_verdict, self.out)))
        dropped = self.sec.replace(row + "\n", "")
        self.assertTrue(any("not 24" in p for p in table_problems(dropped, self.out)))

    def test_every_case_is_stated_at_both_air_temperatures_for_both_loads(self):
        keys = {(r[0], r[1], r[2], r[3]) for r in case_rows(self.sec)}
        expected = {(str(a), str(h), str(rc), load) for a in (25, 40) for h in (10, 5) for rc in (0, 1, 3) for load in ("both on", "steam alone")}
        self.assertEqual(keys, expected)

    def test_the_stainless_bounding_case_stays_beside_the_recorded_wall(self):
        rows = {tuple(r[:4]): r for r in case_rows(self.sec)}
        for key in (("25", "10", "0", "both on"), ("40", "5", "3", "both on")):
            expected = "%.2f" % junction(K_STAINLESS, float(key[0]), float(key[1]), float(key[2]), key[3])
            self.assertEqual(rows[key][7], expected)
        self.assertIn("96.4 degC", read(LOG), "the 2026-11-19 stainless lines of the log are gone")
        self.assertIn("123.8 °C", self.division, "the 2026-11-19 stainless table is gone from the division record")
        self.assertIn("2026-11-21 amendment: the wall is aluminium", self.division)

    def test_the_judgement_is_marked_provisional_and_the_shortfall_is_recorded(self):
        self.assertEqual(provisional_problems(self.sec, self.out), [])
        self.assertTrue(provisional_problems(self.sec.replace("provisional on the joint resistance only", "final"), self.out))
        over = max(t for (k, a, h, r, ld), t in script_cases(self.out).items() if k == 110.0 and t > 100.0)
        dropped = self.sec.replace("%.2f degC" % over, "%d degC" % over)
        self.assertNotEqual(dropped, self.sec)
        self.assertTrue(provisional_problems(dropped, self.out))
        count = re.search(r"(\d+) of (\d+) hold the 100 degC share", self.sec)
        self.assertIsNotNone(count)
        miscounted = self.sec.replace(count.group(0), "%d of %s hold the 100 degC share" % (int(count.group(1)) + 1, count.group(2)))
        self.assertNotEqual(miscounted, self.sec)
        self.assertTrue(any("count of cases" in p for p in provisional_problems(miscounted, self.out)))

    def test_the_script_check_fails_when_the_wall_does_not_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            mutated = os.path.join(tmp, "W_margins.py")
            source = read(SCRIPT)
            bound = re.search(r"^K_ALU_LOW = [\d.]+(?= )", source, re.M)
            self.assertIsNotNone(bound)
            weakened = source.replace(bound.group(0), "K_ALU_LOW = %s" % K_STAINLESS, 1)
            self.assertNotEqual(weakened, source)
            with open(mutated, "w", encoding="utf-8") as handle:
                handle.write(weakened)
            code, out = script_output(mutated)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  aluminium wall holds the maker's 125 degC in every case", out)

    # SOL-HW-HEATER-WALL-BOARD-WALL-STEEL-RECORDED-AND-TRIAC-THERMAL-JUDGEMENT-HOLDS-ON-IT.C3: The owner's dated statement of the wall's material, grade (magnetic or not) and thickness at the cut is on the board's records, quoted as given with the test it rests on, and replaces every owner's-measurement mark that those quantities carried. The criterion closes only on that statement. Out of scope: making the measurement on the owner's behalf.
    def test_the_owner_statement_is_dated_quoted_with_its_test_and_counted(self):
        self.assertEqual(statement_problems(self.sign_off, self.open_items), [])

    def test_a_statement_without_its_test_or_date_is_found(self):
        self.assertTrue(statement_problems(self.sign_off.replace("accepted_on: 2026-11-21. **The test", "accepted_on: 2026-11-20. **The test"), self.open_items))
        self.assertTrue(statement_problems(self.sign_off.replace("No eddy-current (magnet-drag) test was made", "A test was made"), self.open_items))
        count = int(re.search(r"There are (\d+) entries", self.sign_off).group(1))
        wrong_count = self.sign_off.replace("There are %d entries" % count, "There are %d entries" % (count - 1))
        self.assertNotEqual(wrong_count, self.sign_off)
        self.assertTrue(statement_problems(wrong_count, self.open_items))
        self.assertTrue(statement_problems(self.sign_off.replace("I made those scratches fairly easily with a screw driver", "paraphrase"), self.open_items))

    def test_no_owner_measurement_mark_remains_on_the_grade_and_thickness(self):
        self.assertEqual(marks_problems(self.proof, self.division, self.open_items), [])
        self.assertTrue(marks_problems(self.proof + "the owner finds them out at cutting", self.division, self.open_items))

    def test_the_plate_earth_bond_fact_and_the_drilling_intent_are_recorded(self):
        self.assertEqual(earth_bond_problems(self.sign_off, self.open_items), [])
        self.assertTrue(earth_bond_problems(self.sign_off.replace("serrated washer", "washer"), self.open_items))


if __name__ == "__main__":
    unittest.main()
