"""The connector list and discharge-level record of the Sunbeam EM7000 heater wall board.

The records are read as committed; each rule is a function of the record's text so a
failing case is the same text with one line changed.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from typing import List, Set

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_check import sexpr, walk  # noqa: E402
from test_derating_policy_record_heater_wall import Board  # noqa: E402
REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join(REPO, "hardware", "sunbeam-em7000", "heater-wall-board")
PRINTED_CASE = "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON"


def read(name: str) -> str:
    with open(os.path.join(BOARD, name), encoding="utf-8") as handle:
        return handle.read()


def parts_references() -> Set[str]:
    """Every reference the parts record places."""
    return {p["reference"] for p in yaml.safe_load(read("parts-specification.yaml"))["positions"]}


def schematic_references() -> Set[str]:
    """Every component reference of KiCad's own netlist of the committed schematic, pinless parts included."""
    return {str(sexpr.child(comp, "ref")[1]) for comp in walk(Board.load().parsed, "comp")}


def placement_problems(schematic: Set[str], parts: Set[str]) -> List[str]:
    """Where the schematic and the parts record disagree on which connectors and mounting parts the board places."""
    problems = []
    for prefix, name in (("J", "connector"), ("H", "non-connector")):
        in_schematic = {r for r in schematic if r.startswith(prefix)}
        in_parts = {r for r in parts if r.startswith(prefix)}
        for ref in sorted(in_schematic - in_parts):
            problems.append("%s %s is in the schematic and not in the parts record" % (name, ref))
        for ref in sorted(in_parts - in_schematic):
            problems.append("%s %s is in the parts record and not in the schematic" % (name, ref))
    return problems


def placed_connectors() -> Set[str]:
    """The connectors the board places: every J reference of the schematic's netlist."""
    return {r for r in schematic_references() if r.startswith("J")}


def non_connectors() -> Set[str]:
    return {r for r in schematic_references() if r.startswith("H")}


def connector_section(proof: str) -> str:
    start = proof.index("### ESD at the connectors")
    end = proof.index("\n## ", start)
    return proof[start:end]


def table_rows(section: str) -> List[List[str]]:
    rows = []
    for line in section.splitlines():
        if line.startswith("| J") or line.startswith("| H"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def list_problems(section: str, placed: Set[str], holes: Set[str]) -> List[str]:
    """What is wrong with the connector list of a circuit-proof section."""
    problems = []
    rows = table_rows(section)
    listed = {r[0] for r in rows if r[0].startswith("J")}
    for missing in sorted(placed - listed):
        problems.append("connector %s is placed and not listed" % missing)
    for extra in sorted(listed - placed):
        problems.append("%s is listed and not placed" % extra)
    for row in rows:
        if row[0] in placed and row[2] != "reachable":
            problems.append("%s is not classed reachable" % row[0])
        if row[0] in placed and "reachable" not in row[3]:
            problems.append("%s states no in-service state" % row[0])
        if row[0] in placed and "reachable" not in row[4]:
            problems.append("%s states no normal-use state" % row[0])
    excluded = {r[0] for r in rows if r[0].startswith("H") and "excluded" in r[2]}
    for hole in sorted(holes - excluded):
        problems.append("non-connector %s is not named as excluded" % hole)
    if "complete" not in section.split("\n", 3)[2].lower():
        problems.append("the list is not stated complete")
    if PRINTED_CASE not in section:
        problems.append("the printed-case design is not named as the work that can relax the class")
    return problems


def level_problems(section: str, sign_off: str, items: str, placed: Set[str]) -> List[str]:
    """What is wrong with the level, source, clamp and acceptance records."""
    problems = []
    if "No level is declared" not in section:
        problems.append("the proof does not state that no level is declared")
    if "IEC 61000-4-2 level 4" not in section or "not a level a household-appliance product standard sets" not in section:
        problems.append("the named level is not stated as an owner declaration")
    for row in table_rows(section):
        if row[0] in placed and (row[5] != "none declared" or "absence accepted" not in row[6] or not row[7].startswith("none")):
            problems.append("%s row does not declare level, source and clamp as absent" % row[0])
    entry = re.search(r"^- W-5b\..*$", sign_off, re.M)
    if not entry:
        problems.append("owner-sign-off has no W-5b entry")
    else:
        for ref in sorted(placed):
            if ref not in entry.group(0):
                problems.append("W-5b does not name %s" % ref)
        if not re.search(r"accepted_on: 2026-11-21", entry.group(0)):
            problems.append("W-5b is not dated for the amendment")
        if "accepted_by:" not in entry.group(0):
            problems.append("W-5b carries no accepted_by")
    item = re.search(r"^- \*\*ESD level at J931 and the blades.*$", items, re.M)
    if not item:
        problems.append("open-items has no ESD item")
    elif "no level is declared" not in item.group(0).lower() or "W-5b" not in item.group(0):
        problems.append("the open item does not state the absence and its acceptance")
    return problems


def verdict_problems(verdicts: str, placed: Set[str]) -> List[str]:
    problems = []
    for ref in sorted(placed):
        rows = [l for l in verdicts.splitlines() if l.startswith("| %s " % ref)]
        if len(rows) != 1:
            problems.append("%s has %d verdict rows" % (ref, len(rows)))
        elif "ESD-1 only:" not in rows[0] or "not yet reviewed" in rows[0]:
            problems.append("%s has no ESD-1 verdict" % ref)
    return problems


def sign_off_counts_problems(sign_off: str) -> List[str]:
    """The entry counts of the header agree with the entries the sections hold."""
    problems = []
    body = sign_off[sign_off.index("## Owner's own words"):sign_off.index("## For David to sign or confirm")]
    entries = set(re.findall(r"^- (W-\d+[a-d]?)\b", body, re.M))
    count = re.search(r"There are (\d+) entries", sign_off)
    if not count or int(count.group(1)) != len(entries):
        problems.append("the header count %s differs from %d entries" % (count and count.group(1), len(entries)))
    behalf = re.search(r"## Signed on behalf \((\d+) entries", sign_off)
    section = re.search(r"## Signed on behalf.*?(?=\n## )", sign_off, re.S)
    held = len(re.findall(r"^- W-\d+[a-d]?\b", section.group(0), re.M)) if section else -1
    if not behalf or int(behalf.group(1)) != held:
        problems.append("the signed-on-behalf count %s differs from the %d entries held" % (behalf and behalf.group(1), held))
    return problems


class ConnectorDischargeRecord(unittest.TestCase):
    def setUp(self):
        self.proof = read("circuit-proof.md")
        self.section = connector_section(self.proof)
        self.placed = placed_connectors()
        self.holes = non_connectors()

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C1: The board's records list every connector the board places, derived from its schematic and parts record, name any non-connector part (such as a mounting hole) that the list leaves out, and state the list as complete; each is classed for use in service with the case off and for normal use with the machine assembled, and is classed reachable if either state lets a person touch it. A connector whose reachability depends on the printed case is classed reachable, and its record names the printed-case design as the work that can relax the class. Out of scope: the case design itself and any physical discharge measurement.
    def test_connector_list_is_closed_over_the_parts_record(self):
        self.assertEqual(placement_problems(schematic_references(), parts_references()), [])
        self.assertEqual(self.placed, {"J911", "J921", "J931", "J941"})
        self.assertEqual(self.holes, {"H1"})
        self.assertEqual(list_problems(self.section, self.placed, self.holes), [])

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C1: The board's records list every connector the board places, derived from its schematic and parts record, name any non-connector part (such as a mounting hole) that the list leaves out, and state the list as complete; each is classed for use in service with the case off and for normal use with the machine assembled, and is classed reachable if either state lets a person touch it. A connector whose reachability depends on the printed case is classed reachable, and its record names the printed-case design as the work that can relax the class. Out of scope: the case design itself and any physical discharge measurement.
    def test_list_fails_when_a_connector_is_dropped_or_declassed(self):
        dropped = "\n".join(l for l in self.section.splitlines() if not l.startswith("| J931"))
        self.assertIn("connector J931 is placed and not listed", list_problems(dropped, self.placed, self.holes))
        declassed = self.section.replace("| J911 | TAB_OUT_C, TE 63849-1 blade (C86469), coffee element lead, mains | reachable |",
                                         "| J911 | TAB_OUT_C, TE 63849-1 blade (C86469), coffee element lead, mains | not reachable |")
        self.assertIn("J911 is not classed reachable", list_problems(declassed, self.placed, self.holes))
        extra = self.section + "\n| J999 | x | reachable | reachable | reachable | none declared | s | c | W |"
        self.assertIn("J999 is listed and not placed", list_problems(extra, self.placed, self.holes))
        silent = self.section.replace("| reachable (fitting the push-on) | not reachable inside the closed machine; depends on the unbuilt case |", "| | |", 1)
        self.assertIn("J911 states no in-service state", list_problems(silent, self.placed, self.holes))
        no_hole = "\n".join(l for l in self.section.splitlines() if not l.startswith("| H1"))
        self.assertIn("non-connector H1 is not named as excluded", list_problems(no_hole, self.placed, self.holes))
        no_case = self.section.replace(PRINTED_CASE, "the case")
        self.assertTrue(any("printed-case" in p for p in list_problems(no_case, self.placed, self.holes)))

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C1: The board's records list every connector the board places, derived from its schematic and parts record, name any non-connector part (such as a mounting hole) that the list leaves out, and state the list as complete; each is classed for use in service with the case off and for normal use with the machine assembled, and is classed reachable if either state lets a person touch it. A connector whose reachability depends on the printed case is classed reachable, and its record names the printed-case design as the work that can relax the class. Out of scope: the case design itself and any physical discharge measurement.
    def test_list_follows_a_connector_added_to_the_parts_record(self):
        self.assertIn("connector J951 is placed and not listed",
                      list_problems(self.section, self.placed | {"J951"}, self.holes))

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C1: The board's records list every connector the board places, derived from its schematic and parts record, name any non-connector part (such as a mounting hole) that the list leaves out, and state the list as complete; each is classed for use in service with the case off and for normal use with the machine assembled, and is classed reachable if either state lets a person touch it. A connector whose reachability depends on the printed case is classed reachable, and its record names the printed-case design as the work that can relax the class. Out of scope: the case design itself and any physical discharge measurement.
    def test_a_connector_in_only_one_of_the_schematic_and_the_parts_record_is_found(self):
        schematic, parts = schematic_references(), parts_references()
        self.assertIn("connector J951 is in the schematic and not in the parts record",
                      placement_problems(schematic | {"J951"}, parts))
        self.assertIn("connector J941 is in the parts record and not in the schematic",
                      placement_problems(schematic - {"J941"}, parts))
        self.assertIn("non-connector H2 is in the schematic and not in the parts record",
                      placement_problems(schematic | {"H2"}, parts))
        self.assertIn("connector J952 is in the parts record and not in the schematic",
                      placement_problems(schematic, parts | {"J952"}))

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C2: Each reachable connector has in the board's records the discharge level it is held to with the governing standard or cited free derivation it is taken from, and any clamp it carries with its part; or the record states that no level is declared and carries the owner's dated acceptance. Does not cover non-reachable connectors, and the main board's connectors are excluded.
    def test_levels_absence_and_owner_acceptance_are_recorded(self):
        problems = level_problems(self.section, read("owner-sign-off.md"), read("open-items.md"), self.placed)
        self.assertEqual(problems, [])
        self.assertEqual(verdict_problems(read("circuit-verdicts.md"), self.placed), [])
        self.assertEqual(sign_off_counts_problems(read("owner-sign-off.md")), [])

    # SOL-HW-HEATER-WALL-BOARD-REACHABLE-CONNECTOR-DISCHARGE-LEVELS-DECLARED.C2: Each reachable connector has in the board's records the discharge level it is held to with the governing standard or cited free derivation it is taken from, and any clamp it carries with its part; or the record states that no level is declared and carries the owner's dated acceptance. Does not cover non-reachable connectors, and the main board's connectors are excluded.
    def test_acceptance_fails_when_the_entry_loses_a_connector_date_or_level_statement(self):
        sign_off = read("owner-sign-off.md")
        items = read("open-items.md")
        stale = sign_off.replace("accepted_on: 2026-11-21 (amended; first signed 2026-11-18)", "accepted_on: 2026-11-18")
        self.assertIn("W-5b is not dated for the amendment", level_problems(self.section, stale, items, self.placed))
        entry = re.search(r"^- W-5b\..*$", sign_off, re.M).group(0)
        short = sign_off.replace(entry, entry.replace("J941", "J94"))
        self.assertIn("W-5b does not name J941", level_problems(self.section, short, items, self.placed))
        unowned = self.section.replace("an owner declaration and not a level a household-appliance product standard sets", "a level")
        self.assertTrue(any("owner declaration" in p for p in level_problems(unowned, sign_off, items, self.placed)))
        claimed = self.section.replace("| J931 | WB_LV3", "| J931 | WB_LV3").replace("| none declared | none; absence accepted | none; a clamp on the header", "| IEC 61000-4-2 level 4 | cited | none; a clamp on the header")
        self.assertIn("J931 row does not declare level, source and clamp as absent", level_problems(claimed, sign_off, items, self.placed))
        verdicts = read("circuit-verdicts.md").replace("| J941 (blade TAB_RET) | PINV-1, CABLE-1, ESD-1, DERATE-2 | ESD-1 only:", "| J941 (blade TAB_RET) | PINV-1, CABLE-1, DERATE-2 | not yet reviewed |")
        self.assertIn("J941 has no ESD-1 verdict", verdict_problems(verdicts, self.placed))
        count = int(re.search(r"There are (\d+) entries", sign_off).group(1))
        wrong = sign_off.replace(f"There are {count} entries", f"There are {count - 1} entries")
        self.assertNotEqual(wrong, sign_off)
        self.assertTrue(sign_off_counts_problems(wrong))
        held = int(re.search(r"## Signed on behalf \((\d+) entries", sign_off).group(1))
        wrong_behalf = sign_off.replace(f"## Signed on behalf ({held} entries", f"## Signed on behalf ({held + 1} entries")
        self.assertNotEqual(wrong_behalf, sign_off)
        self.assertTrue(sign_off_counts_problems(wrong_behalf))


if __name__ == "__main__":
    unittest.main()
