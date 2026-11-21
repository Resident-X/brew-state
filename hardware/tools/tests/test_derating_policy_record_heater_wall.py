"""The gate-network resistors of the Sunbeam EM7000 heater wall board: the set the schematic's nets give, each one's rating against its stress, its accepted-exception entry and the pre-order check's reading of it.

The nets come from KiCad's own netlist of the committed schematic, so the tests need
kicad-cli (set KICAD_CLI=/path/to/kicad-cli when it is not on PATH). The records they
read are the board's committed ones; a failing case is a temporary copy of the board's
folder with one entry changed.
"""
from __future__ import annotations

import datetime
import math
import os
import re
import shutil
import sys
import tempfile
import unittest
from typing import Dict, List, Set

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import board_check  # noqa: E402
from board_check import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join("hardware", "sunbeam-em7000", "heater-wall-board")
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
#: The day the check is told it is: after the owner's acceptance of the four entries.
TODAY = datetime.date(2026, 11, 21)
#: The top of the declared supply span, V rms, and the figures of the circuit-proof arithmetic.
SUPPLY_V = 253.0
GATE_OHM_MIN = 198.0  # one 200 ohm resistor at -1 %
CLAMP_V = 775.0  # the wall varistor's clamp at 10 A
FIRING_A = 0.05  # IGT 50 mA at most
FIRING_OHM_MAX = 202.0  # one 200 ohm resistor at +1 %
RATED_W = 0.25
NOMINAL_OHM = 200.0
OWNER = "David Baker"


def netlist_of(schematic: str):
    """KiCad's own netlist of the schematic at `schematic` (repository-relative), parsed."""
    with tempfile.TemporaryDirectory() as scratch:
        text, why = board_check.run_kicad([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
                                           os.path.join(REPO, schematic)], scratch, "netlist.net")
    assert text is not None, f"kicad-cli gave no netlist: {why}"
    return sexpr.parse_one(text)


def gate_network_resistors(nets: Dict[str, List[board_check.PinNode]]) -> Set[str]:
    """Every resistor with a pad on a net between an opto-triac output and a triac gate.

    From each triac's gate pin the walk goes back through two-pin resistors only; when it
    ends on a pin of an opto-triac (a U part), the resistors it crossed are the gate network's.
    """
    by_ref: Dict[str, List[tuple]] = {}
    for net, pins in nets.items():
        for pin in pins:
            by_ref.setdefault(pin.ref, []).append((net, pin))
    found: Set[str] = set()
    for gate_net, pins in nets.items():
        if not any(pin.ref.startswith("T") and pin.names() == ["G"] for pin in pins):
            continue
        crossed: Set[str] = set()
        seen_nets = {gate_net}
        queue = [gate_net]
        reaches_opto = False
        while queue:
            net = queue.pop()
            for pin in nets[net]:
                if pin.ref.startswith("U"):
                    reaches_opto = True
                if pin.ref.startswith("R") and pin.ref not in crossed:
                    crossed.add(pin.ref)
                    for other_net, _ in by_ref[pin.ref]:
                        if other_net not in seen_nets:
                            seen_nets.add(other_net)
                            queue.append(other_net)
        if reaches_opto:
            found |= crossed
    return found


def pin(ref, number, function=""):
    return board_check.PinNode(ref, number, function)


def committed_policy():
    yaml = board_check.require_yaml()
    with open(os.path.join(REPO, BOARD, board_check.DERATING_NAME), encoding="utf-8") as handle:
        return yaml, board_check.strict_yaml(yaml, handle.read())


def section_of_circuit_proof() -> str:
    """The text of the circuit proof's gate-network section."""
    with open(os.path.join(REPO, BOARD, "circuit-proof.md"), encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("## The gate-network resistors")
    return text[start:text.index("\n## ", start + 3)]


def stresses() -> Dict[str, float]:
    """The stress figures of the circuit-proof arithmetic, computed here from its inputs."""
    peak = SUPPLY_V * math.sqrt(2)
    pair = 2 * GATE_OHM_MIN
    surge_a = peak / pair
    clamp_a = CLAMP_V / pair
    rcwv = math.sqrt(RATED_W * NOMINAL_OHM)
    return {
        "peak_v": peak, "surge_a": surge_a, "surge_v": surge_a * GATE_OHM_MIN, "surge_w": surge_a ** 2 * GATE_OHM_MIN,
        "surge_w_nominal": (peak / 2) ** 2 / NOMINAL_OHM, "clamp_a": clamp_a, "clamp_v": clamp_a * GATE_OHM_MIN,
        "clamp_w": clamp_a ** 2 * GATE_OHM_MIN, "clamp_w_nominal": (CLAMP_V / 2) ** 2 / NOMINAL_OHM,
        "firing_v": FIRING_A * FIRING_OHM_MAX, "firing_w": FIRING_A ** 2 * FIRING_OHM_MAX,
        "rcwv": rcwv, "overload_v": 2.5 * rcwv,
    }


class Board:
    """The committed board: its design, its netlist and a repository view, read once."""

    nets = None
    design = None

    @classmethod
    def load(cls):
        if cls.nets is None:
            files = board_check.tracked_files("git", REPO)
            designs, _, _ = board_check.discover(REPO, files)
            cls.design = next(d for d in designs if d.directory.replace(os.sep, "/").endswith("sunbeam-em7000/heater-wall-board"))
            cls.parsed = netlist_of(cls.design.schematic)
            cls.nets = board_check.schematic_pin_nodes(cls.parsed)
            cls.mains = board_check.schematic_mains(board_check.schematic_nets(cls.parsed))
        return cls

    @classmethod
    def run(cls, root, design, nets=None):
        """The derated-voltage rule on `design` under `root`: its violations and its ACCEPTED lines."""
        files = [os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/") for d, _, names in os.walk(root) for n in names
                 if ".git" not in d.split(os.sep)]
        repository = board_check.Repository(root, files)
        signed = board_check.Signed(3.0, 10.0, {"working_voltage": "253 V rms"})
        accepted: List[str] = []
        found = board_check.voltage_rules(design, board_check.require_yaml(), root, repository, False, "present", signed,
                                          nets or cls.nets, cls.mains, TODAY, accepted)
        return found, accepted


class GateNetworkSet(unittest.TestCase):
    def test_the_schematics_nets_give_exactly_the_four_resistors_and_the_records_state_them_closed(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C1: The board's records state which resistors are mains gate-network resistors, defined as every resistor with a pad on a net between an opto-triac output and a triac gate, derived from the schematic's references and the parts record, and state that list as the complete set; a resistor in a gate network on any sheet that is missing from the list fails the criterion. Out of scope: resistors outside a gate network and any change to the circuit.
        board = Board.load()
        derived = gate_network_resistors(board.nets)
        self.assertEqual(derived, {"R911", "R912", "R921", "R922"})
        # the board places no other resistor, so a resistor outside a gate network cannot be hiding beside them
        every_resistor = {p.ref for pins in board.nets.values() for p in pins if re.fullmatch(r"R\d+", p.ref)}
        self.assertEqual(every_resistor, derived)
        # the circuit proof states the set, as closed, and the policy holds one entry for each member and no other
        section = section_of_circuit_proof()
        statement = re.search(r"\*\*Closed set: ([^*]+)\.\*\*", section)
        self.assertIsNotNone(statement)
        self.assertEqual(set(re.findall(r"R\d+", statement.group(1))), derived)
        _, policy = committed_policy()
        self.assertEqual(sorted(e["position"] for e in policy["accepted_exceptions"]), sorted(derived))

    def test_the_walk_finds_a_resistor_added_to_a_gate_network_and_leaves_one_outside_it(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C1: The board's records state which resistors are mains gate-network resistors, defined as every resistor with a pad on a net between an opto-triac output and a triac gate, derived from the schematic's references and the parts record, and state that list as the complete set; a resistor in a gate network on any sheet that is missing from the list fails the criterion. Out of scope: resistors outside a gate network and any change to the circuit.
        gate = [pin("U1", "4"), pin("R1", "1")]
        nets = {
            "OPTO": gate,
            "MID": [pin("R1", "2"), pin("R2", "1")],
            "GATE": [pin("R2", "2"), pin("T1", "3", "G_3")],
            "LED": [pin("U1", "1"), pin("R9", "1")],  # a series resistor on the opto-triac's input side
            "GND": [pin("R9", "2"), pin("R7", "1"), pin("T1", "1", "A1_1")],
            "ELSEWHERE": [pin("R7", "2"), pin("C1", "1")],
        }
        self.assertEqual(gate_network_resistors(nets), {"R1", "R2"})
        # a third resistor in the chain, however it is wired, is in the set the statement must list
        nets["GATE"] = [pin("R2", "2"), pin("R3", "1")]
        nets["EXTRA"] = [pin("R3", "2"), pin("T1", "3", "G_3")]
        self.assertEqual(gate_network_resistors(nets), {"R1", "R2", "R3"})
        # a gate no resistor chain joins to an opto-triac has no gate network
        self.assertEqual(gate_network_resistors({"GATE": [pin("T1", "3", "G_3"), pin("R5", "1")], "N": [pin("R5", "2"), pin("C1", "1")]}), set())


class RatingsAgainstStress(unittest.TestCase):
    def test_each_resistors_stress_is_recomputed_from_its_inputs_and_matches_every_figure_the_records_state(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C2: For each resistor of the closed set, the records give in one table the maker-sourced rated working voltage and pulse rating beside the stress the board puts on it at the top of the declared supply span, with the arithmetic, and either the ratings cover the stress or the resistor has an accepted exception entry instead; every stress, power and current figure the records state for these resistors is recomputed and agrees with that arithmetic. Out of scope: changing a part to a pulse-rated class, which is the owner's hedge in the open items.
        figures = stresses()
        self.assertAlmostEqual(figures["peak_v"], 357.8, places=1)
        self.assertAlmostEqual(figures["rcwv"], 7.07, places=2)
        self.assertAlmostEqual(figures["overload_v"], 17.7, places=1)
        section = section_of_circuit_proof()
        stated = {"false trigger": ("178.9 V", "162 W", "0.904 A"), "clamp": ("387.5 V", "758 W", "1.957 A"),
                  "firing": ("10.1 V", "0.505 W", "0.04 ms")}
        self.assertEqual(round(figures["surge_v"], 1), 178.9)
        self.assertEqual(round(figures["surge_w"]), 162)
        self.assertEqual(round(figures["surge_a"], 3), 0.904)
        self.assertEqual(round(figures["surge_w_nominal"]), 160)
        self.assertEqual(round(figures["clamp_v"], 1), 387.5)
        self.assertEqual(round(figures["clamp_w"]), 758)
        self.assertEqual(round(figures["clamp_a"], 3), 1.957)
        self.assertEqual(round(figures["clamp_w_nominal"]), 751)
        self.assertEqual(round(figures["firing_v"], 1), 10.1)
        self.assertEqual(round(figures["firing_w"], 3), 0.505)
        for words in sum(stated.values(), ()) + ("160 W", "751 W", "7.07 V / 17.7 V", "none stated"):
            self.assertIn(words, section, words)
        # one row per resistor of the closed set, each with the maker's rated voltage and the absent pulse rating
        for ref in ("R911", "R912", "R921", "R922"):
            row = next((line for line in section.splitlines() if line.startswith(f"| {ref} |")), None)
            self.assertIsNotNone(row, ref)
            for words in ("7.07 V / 17.7 V", "none stated", "no", "accepted_v 178.9 V"):
                self.assertIn(words, row, (ref, words))
        # the ratings do not cover the stresses, which is why each resistor has an entry instead
        for stress in (figures["firing_v"], figures["surge_v"], figures["clamp_v"]):
            self.assertGreater(stress, figures["rcwv"])
        # the parts record carries the same rating, and the policy's resistor class holds the maker's voltage as the limit
        yaml = board_check.require_yaml()
        with open(os.path.join(REPO, BOARD, "parts-specification.yaml"), encoding="utf-8") as handle:
            parts = board_check.strict_yaml(yaml, handle.read())["positions"]
        by_ref = {p["reference"]: p for p in parts if "reference" in p}
        for ref in ("R911", "R912", "R921", "R922"):
            self.assertEqual(by_ref[ref]["value"], "200")
            self.assertIn("RCWV 7.07V", by_ref[ref]["rating"])
            self.assertEqual(by_ref[ref]["class"], "resistor")
        # the open items' prose qualifies the two powers by the resistance they are taken at, so none reads against its own inputs
        with open(os.path.join(REPO, BOARD, "open-items.md"), encoding="utf-8") as handle:
            prose = handle.read()
        self.assertIn("178.9 V and 162 W per resistor (the pair at its minimum, 2 x 198 ohm = 396 ohm, 0.904 A; 160 W at the nominal 200 ohm each)", prose)
        self.assertIn("387.5 V and 758 W (1.957 A at 396 ohm; 751 W at the nominal 200 ohm)", prose)
        self.assertNotIn("162 W per resistor until", prose)


class ExceptionEntries(unittest.TestCase):
    def test_each_entry_states_the_stress_the_missing_rating_the_owners_acceptance_and_the_bounding_element(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C3: Every accepted_exceptions entry of a gate-network resistor states the stress and the accepted working voltage, the rating the maker leaves out or falls short on, the owner's acceptance with its date and the element that bounds the residual, and the check reads the entry through its existing reader. Out of scope: a pulse field or pulse rule in the check.
        yaml, policy = committed_policy()
        figures = stresses()
        entries = policy["accepted_exceptions"]
        self.assertEqual([e["position"] for e in entries], ["R911", "R912", "R921", "R922"])
        for entry in entries:
            with self.subTest(position=entry["position"]):
                self.assertEqual(sorted(entry), sorted(board_check.DERATING_EXCEPTION_KEYS))
                # the stress and the accepted working voltage
                self.assertEqual(entry["accepted_v"], round(figures["surge_v"], 1))
                self.assertGreaterEqual(entry["accepted_v"], figures["surge_v"] - 0.05)
                self.assertIn("178.9 V", entry["reason"])
                # the rating the maker leaves out or falls short on
                for words in ("7.07 V", "17.7 V", "no pulse rating", "UNI-ROYAL V.3 p.5"):
                    self.assertIn(words, entry["reason"])
                # the owner's acceptance with its date, in his words
                self.assertIn(OWNER, entry["accepted_by"])
                self.assertIn("owner", entry["accepted_by"])
                self.assertFalse(board_check.is_placeholder(entry["accepted_by"]))
                self.assertEqual(board_check.iso_date(entry["accepted_on"]), datetime.date(2026, 11, 19))
                self.assertIsNone(board_check.entry_unsigned(entry, None, TODAY))
                self.assertIn("Accept 1 2 and 3", entry["reason"])
                self.assertIn("2026-11-19", entry["reason"])
                # the element that bounds the residual
                for words in ("opto-triac", "K201", "thermostat", "firmware"):
                    self.assertIn(words, entry["bounded_by"])
                # the entry is no more than its own text: an emptied or placeholder acceptance is found unsigned
                for field, value in (("accepted_by", ""), ("accepted_by", "tbd"), ("accepted_on", ""), ("accepted_on", "2026-11-22")):
                    self.assertIsNotNone(board_check.entry_unsigned(dict(entry, **{field: value}), None, TODAY), (field, value))

    def test_the_checks_own_reader_accepts_the_committed_policy_and_refuses_a_broken_entry(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C3: Every accepted_exceptions entry of a gate-network resistor states the stress and the accepted working voltage, the rating the maker leaves out or falls short on, the owner's acceptance with its date and the element that bounds the residual, and the check reads the entry through its existing reader. Out of scope: a pulse field or pulse rule in the check.
        yaml, policy = committed_policy()
        board = Board.load()
        files = board_check.tracked_files("git", REPO)
        repository = board_check.Repository(REPO, files)
        self.assertEqual(board_check.read_derating(yaml, REPO, repository, board.design, False), [])
        with tempfile.TemporaryDirectory() as folder:
            design = copy_board(folder)
            copy_files = [os.path.relpath(os.path.join(d, n), folder) for d, _, names in os.walk(folder) for n in names]
            copy = board_check.Repository(folder, copy_files)
            first = policy["accepted_exceptions"]
            for label, broken in (("a key removed", [{k: v for k, v in first[0].items() if k != "bounded_by"}] + first[1:]),
                                  ("accepted_v zero", [dict(first[0], accepted_v=0)] + first[1:]),
                                  ("a position repeated", first + [dict(first[1], position="R911")])):
                write_policy(yaml, folder, dict(policy, accepted_exceptions=broken))
                found = board_check.read_derating(yaml, folder, copy, design, False)
                self.assertTrue(found, label)
                self.assertTrue(all(v.rule == "derating_record" for v in found), (label, [v.line() for v in found]))


def copy_board(folder: str):
    """A temporary copy of the board's folder under `folder`; its design, found as the check finds one."""
    shutil.copytree(os.path.join(REPO, BOARD), os.path.join(folder, BOARD), ignore=shutil.ignore_patterns("*.pretty", "circuit-proof", "spec-tools"))
    files = [os.path.relpath(os.path.join(d, n), folder).replace(os.sep, "/") for d, _, names in os.walk(folder) for n in names]
    designs, _, _ = board_check.discover(folder, files)
    return next(d for d in designs if d.directory.replace(os.sep, "/").endswith("heater-wall-board"))


def write_policy(yaml, folder: str, policy: dict) -> None:
    with open(os.path.join(folder, BOARD, board_check.DERATING_NAME), "w", encoding="utf-8") as handle:
        yaml.safe_dump(policy, handle)


class PreOrderCheck(unittest.TestCase):
    def test_the_derated_voltage_rule_passes_every_gate_resistor_on_the_committed_records_and_fails_on_an_entry_below_the_stress(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C4: The pre-order check run on the heater wall board passes its derated-voltage rule for every gate-network resistor with the records as committed, and an entry whose accepted working voltage is below the position's stress fails it in a temporary copy of the board's records, so that the pass is shown to depend on the entry. Out of scope: any change to the check's rules and any pulse rule.
        yaml, policy = committed_policy()
        board = Board.load()
        found, accepted = Board.run(REPO, board.design)
        self.assertEqual([v.line() for v in found], [])
        taken = {ref: line for ref in ("R911", "R912", "R921", "R922") for line in accepted if f"the position {ref} sees" in line}
        self.assertEqual(sorted(taken), ["R911", "R912", "R921", "R922"])
        working = {ref: float(re.search(r"working voltage of ([\d.]+) V", line).group(1)) for ref, line in taken.items()}
        self.assertEqual(working["R911"], 178.9)
        self.assertEqual(working["R921"], 178.9)
        self.assertAlmostEqual(working["R912"], 177.576, places=3)
        self.assertAlmostEqual(working["R922"], 177.576, places=3)
        for line in taken.values():
            self.assertIn("above its limit of 7.07 V", line)
            self.assertIn("David Baker (owner)", line)
        # the same records with one entry's accepted_v below that position's stress fail the rule, one position at a time
        entries = policy["accepted_exceptions"]
        for index, entry in enumerate(entries):
            ref = entry["position"]
            below = round(working[ref] - 0.1, 3)
            with self.subTest(position=ref, accepted_v=below):
                with tempfile.TemporaryDirectory() as folder:
                    design = copy_board(folder)
                    changed = [dict(e, accepted_v=below) if e["position"] == ref else e for e in entries]
                    write_policy(yaml, folder, dict(policy, accepted_exceptions=changed))
                    failing, _ = Board.run(folder, design)
                    mine = [v for v in failing if v.rule == "derated_voltage"]
                    self.assertEqual(len(mine), 1, [v.line() for v in failing])
                    self.assertIn(f"{design.schematic} {ref}", mine[0].location)
                    self.assertIn(f"accepted_exceptions[{index}] accepts only {below:g} V, below the working voltage", mine[0].message)

    def test_the_pass_depends_on_the_entry_for_each_resistor(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C4: The pre-order check run on the heater wall board passes its derated-voltage rule for every gate-network resistor with the records as committed, and an entry whose accepted working voltage is below the position's stress fails it in a temporary copy of the board's records, so that the pass is shown to depend on the entry. Out of scope: any change to the check's rules and any pulse rule.
        yaml, policy = committed_policy()
        entries = policy["accepted_exceptions"]
        for ref in ("R911", "R912", "R921", "R922"):
            with self.subTest(position=ref):
                with tempfile.TemporaryDirectory() as folder:
                    design = copy_board(folder)
                    kept = [e for e in entries if e["position"] != ref]
                    write_policy(yaml, folder, dict(policy, accepted_exceptions=kept))
                    failing, accepted = Board.run(folder, design)
                    mine = [v for v in failing if v.rule == "derated_voltage"]
                    self.assertEqual(len(mine), 1, [v.line() for v in failing])
                    self.assertIn(f"{design.schematic} {ref}", mine[0].location)
                    self.assertIn("above 7.07 V", mine[0].message)
                    self.assertEqual(len(accepted), 3)

    def test_an_entry_unsigned_or_for_no_gate_resistor_does_not_pass_the_board(self):
        # SOL-HW-HEATER-WALL-BOARD-GATE-NETWORK-RESISTOR-PULSE-AND-WORKING-VOLTAGE-RATINGS-COVERED.C4: The pre-order check run on the heater wall board passes its derated-voltage rule for every gate-network resistor with the records as committed, and an entry whose accepted working voltage is below the position's stress fails it in a temporary copy of the board's records, so that the pass is shown to depend on the entry. Out of scope: any change to the check's rules and any pulse rule.
        yaml, policy = committed_policy()
        entries = policy["accepted_exceptions"]
        for label, changed, rule in (
                ("unsigned", [dict(entries[0], accepted_by="tbd")] + entries[1:], "derated_voltage"),
                ("dated after the check's day", [dict(entries[0], accepted_on="2026-11-22")] + entries[1:], "derated_voltage"),
                ("a stale entry", entries + [dict(entries[0], position="R999")], "derating_exception")):
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as folder:
                    design = copy_board(folder)
                    write_policy(yaml, folder, dict(policy, accepted_exceptions=changed))
                    failing, _ = Board.run(folder, design)
                    self.assertTrue([v for v in failing if v.rule == rule], [v.line() for v in failing])


if __name__ == "__main__":
    unittest.main()
