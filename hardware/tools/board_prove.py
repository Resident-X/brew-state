#!/usr/bin/env python3
"""Break the throwaway proof design on purpose, once per failure condition, and require the check to notice.

Every failure condition the pre-order check enforces gets a fault seeded for it
here. Each fault is introduced into a fresh copy of hardware/proof/gate-proof in
a temporary directory outside the repository, made into a git work tree of its
own so the check finds designs exactly as it does in the repository, and the
shipped check is run on it. A fault counts as caught only when the check exits
non-zero *and* reports a violation of the rule the fault was seeded for, with
the text that names it; a check that failed for some other reason has not shown
it can see this one. The clean copy must pass, or a fault being caught would
show nothing.

The committed tree is never touched, unlike the firmware mutation tool, which
edits its sources in place and restores them: the proof design has to stay clean
for the every-design check to stay green.

Each result is printed on one line,

    CAUGHT | <fault> | <check it proves> | <the violation line the check printed>

or MISSED in place of CAUGHT, and the exit status is 0 only when the clean copy
passes and every fault is caught.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, List, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402

PROOF = os.path.join(os.path.dirname(TOOLS), "proof", "gate-proof")
DESIGN = "hardware/proof/gate-proof"
NAME = "gate-proof"


class Seed:
    """A copy of the proof design in a temporary git work tree, and the edits a fault makes to it."""

    def __init__(self, root: str):
        self.root = root
        self.design = os.path.join(root, DESIGN)

    def path(self, suffix: str) -> str:
        return os.path.join(self.design, NAME + suffix) if suffix.startswith(".") else os.path.join(self.design, suffix)

    def read(self, suffix: str) -> str:
        with open(self.path(suffix), encoding="utf-8") as handle:
            return handle.read()

    def write(self, suffix: str, text: str) -> None:
        with open(self.path(suffix), "w", encoding="utf-8") as handle:
            handle.write(text)

    def replace(self, suffix: str, old: str, new: str) -> None:
        text = self.read(suffix)
        if old not in text:
            raise AssertionError(f"the proof design's {suffix} no longer contains {old!r}; the fault cannot be seeded")
        self.write(suffix, text.replace(old, new, 1))

    def project(self, edit: Callable[[dict], None]) -> None:
        data = json.loads(self.read(".kicad_pro"))
        edit(data)
        self.write(".kicad_pro", json.dumps(data, indent=2))

    def layout(self, edit: Callable[[list], None]) -> None:
        tree = sexpr.parse_one(self.read(".kicad_pcb"))
        edit(tree)
        self.write(".kicad_pcb", sexpr.dump(tree) + "\n")

    def schematic(self, edit: Callable[[list], None]) -> None:
        tree = sexpr.parse_one(self.read(".kicad_sch"))
        edit(tree)
        self.write(".kicad_sch", sexpr.dump(tree) + "\n")


def footprint(tree: list, reference: str) -> list:
    for item in sexpr.children(tree, "footprint"):
        for prop in sexpr.children(item, "property"):
            if len(prop) > 2 and prop[1] == "Reference" and prop[2] == reference:
                return item
    raise AssertionError(f"the proof layout has no footprint {reference}")


def pad(tree: list, reference: str, number: str) -> list:
    for item in sexpr.children(footprint(tree, reference), "pad"):
        if item[1] == number:
            return item
    raise AssertionError(f"the proof layout has no pad {number} on {reference}")


def segment(net: str, x1: float, y1: float, x2: float, y2: float, uuid: str) -> list:
    Q = sexpr.Quoted
    return ["segment", ["start", f"{x1:g}", f"{y1:g}"], ["end", f"{x2:g}", f"{y2:g}"], ["width", "0.25"],
            ["layer", Q("F.Cu")], ["net", Q(net)], ["uuid", Q(uuid)]]


#: R1 pad 2, on /MAINS_N, is a 1.6 mm round pad at (25.16, 10). This low-voltage
#: track runs 2.0 mm from its edge: clear of every net-class figure, inside the
#: signed 3 mm clearance and 4 mm creepage. It is what each override fault would
#: let pass if the override won.
ENCROACH_X = 25.16 + 0.8 + 2.0 + 0.125
ENCROACH_UUID = "0b0e5c1a-0000-4000-8000-000000000001"


def encroach(seed: Seed) -> None:
    seed.layout(lambda tree: tree.insert(len(tree) - 1, segment("/LV_A", ENCROACH_X, 9, ENCROACH_X, 11, ENCROACH_UUID)))


#: R2 pad 2, on /LV_B, is a 1.6 mm round pad at (55.16, 10). A /LV_A track 0.1 mm
#: from its edge breaks the Default net class's 0.2 mm clearance.
CROWD_X = 55.16 + 0.8 + 0.1 + 0.125
CROWD_UUID = "0b0e5c1a-0000-4000-8000-000000000002"


def crowd(seed: Seed) -> None:
    seed.layout(lambda tree: tree.insert(len(tree) - 1, segment("/LV_A", CROWD_X, 9, CROWD_X, 11, CROWD_UUID)))


def later_rule(condition: str):
    def seed_it(seed: Seed) -> None:
        text = seed.read(".kicad_dru")
        seed.write(".kicad_dru", text + f'(rule "undercut"\n\t(condition "{condition}")\n'
                                        "\t(constraint clearance (min 0.1mm))\n\t(constraint creepage (min 0.1mm)))\n")
        encroach(seed)
    return seed_it


def record(old: str, new: str):
    return lambda seed: seed.replace("separation-basis.yaml", old, new)


def variables(edit: Callable[[dict], None]):
    return lambda seed: seed.project(lambda data: edit(data["text_variables"]))


def remove(*suffixes: str):
    def seed_it(seed: Seed) -> None:
        for suffix in suffixes:
            os.remove(seed.path(suffix))
    return seed_it


def stray(suffix: str):
    def seed_it(seed: Seed) -> None:
        target = os.path.join(seed.root, "hardware", "stray")
        os.makedirs(target, exist_ok=True)
        shutil.copy(seed.path(suffix), os.path.join(target, "stray" + suffix))
    return seed_it


def drop_label(seed: Seed) -> None:
    def edit(tree: list) -> None:
        for item in sexpr.children(tree, "label"):
            at = sexpr.child(item, "at")
            if item[1] == "LV_B" and at[1:3] == ["63.5", "81.28"]:
                tree.remove(item)
                return
        raise AssertionError("the proof schematic has no LV_B label on R2 pin 2")
    seed.schematic(edit)


def excluded(seed: Seed) -> None:
    crowd(seed)
    key = f"clearance|{round(CROWD_X * 1e6)}|9000000|{CROWD_UUID}|00000000-0000-0000-0000-000000000000"
    seed.project(lambda data: data["board"]["design_settings"]["drc_exclusions"].append([key, "tolerated"]))


def severity(setting: str, key: str, value: Optional[str]):
    def edit(data: dict) -> None:
        table = data["erc"]["rule_severities"] if setting == "erc" else data["board"]["design_settings"]["rule_severities"]
        if value is None:
            del table[key]
        else:
            table[key] = value
    return lambda seed: seed.project(edit)


def mains_rule(old: str, new: str):
    return lambda seed: seed.replace(".kicad_dru", old, new)


def local_override(target: Callable[[list], list]):
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            item = target(tree)
            item.insert(len(item) - 1, ["clearance", "0.1"])
        seed.layout(edit)
        encroach(seed)
    return seed_it


def mains_zone(seed: Seed) -> None:
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/MAINS_L")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000003")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "2", "15"], ["xy", "20", "15"], ["xy", "20", "19"], ["xy", "2", "19"]]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))


def netclass_below(seed: Seed) -> None:
    def edit(data: dict) -> None:
        for netclass in data["net_settings"]["classes"]:
            if netclass["name"] == "Mains":
                netclass["clearance"] = 0.1
    seed.project(edit)
    encroach(seed)


def parity(seed: Seed) -> None:
    def edit(tree: list) -> None:
        for prop in sexpr.children(footprint(tree, "R2"), "property"):
            if prop[1] == "Value":
                prop[2] = sexpr.Quoted("22k")
    seed.layout(edit)


def truncate(suffix: str):
    return lambda seed: seed.write(suffix, seed.read(suffix)[: len(seed.read(suffix)) // 2])


def empty_tree(seed: Seed) -> None:
    shutil.rmtree(os.path.join(seed.root, "hardware"))


SIGNED = f"rule '{board_check.SIGNED_RULE}' clearance"
CONDITION = board_check.MAINS_CONDITION

#: (fault, the check it proves, the rule the check must report, text that line must carry, the edit)
FAULTS: List[Tuple[str, str, str, str, Callable[[Seed], None]]] = [
    # Discovery
    ("an empty tree", "discovery: finding nothing fails", "design_discovery", "no board design was found", empty_tree),
    ("a layout that cannot be opened", "discovery: an unreadable design fails by name", "design_unreadable", "layout cannot be checked", truncate(".kicad_pcb")),
    ("a schematic that cannot be opened", "discovery: an unreadable design fails by name", "design_unreadable", "schematic", truncate(".kicad_sch")),
    ("a project file that cannot be read", "discovery: an unreadable design fails by name", "design_unreadable", "project file cannot be read", lambda seed: seed.write(".kicad_pro", "{ not json")),
    ("a project missing its schematic", "discovery: a project needs both its schematic and layout", "design_discovery", "no schematic beside it", remove(".kicad_sch")),
    ("a project missing its layout", "discovery: a project needs both its schematic and layout", "design_discovery", "no layout beside it", remove(".kicad_pcb")),
    ("a layout committed without its project", "discovery: no board file escapes the check", "design_discovery", "a layout is tracked without", stray(".kicad_pcb")),
    ("a schematic committed without its project", "discovery: no board file escapes the check", "design_discovery", "a schematic is tracked without", stray(".kicad_sch")),
    # Rule checks
    ("an electrical rule violation", "rule checks: KiCad's ERC", "pin_not_connected", "Pin not connected", drop_label),
    ("a layout clearance violation", "rule checks: KiCad's DRC", "clearance", "netclass 'Default'", crowd),
    ("layout-schematic disagreement", "rule checks: schematic parity", "footprint_symbol_mismatch", "R2", parity),
    ("a violation marked as excluded", "rule checks: an exclusion is a failure", "clearance", "excluded in its project file", excluded),
    ("a custom rule marking its violations excluded", "rule checks: an exclusion is a failure", "ignored_check", "severity to exclusion",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + "(rule \"tolerate\"\n\t(condition \"A.Type == 'Track'\")\n\t(severity exclusion))\n")),
    ("a layout rule set to ignore", "rule checks: an ignored check is a failure", "ignored_check", "rule_severities.clearance", severity("drc", "clearance", "ignore")),
    ("an electrical rule set to ignore", "rule checks: an ignored check is a failure", "ignored_check", "erc.rule_severities.pin_not_connected", severity("erc", "pin_not_connected", "ignore")),
    ("a rule left at KiCad's own default of ignore", "rule checks: an ignored check is a failure, default or not", "ignored_check", "missing_courtyard", severity("drc", "missing_courtyard", None)),
    ("a custom rule set to ignore", "rule checks: an ignored check is a failure", "ignored_check", "severity to ignore",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + "(rule \"hush\"\n\t(condition \"A.Type == 'Track'\")\n\t(severity ignore))\n")),
    ("a rules file KiCad declines to load", "rule checks: the design's rules are read as written", "custom_rules", "KiCad did not load",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + "(rule \"typo\"\n\t(condition \"A.Type == 'Pad'\")\n\t(constraint clearence (min 1mm)))\n")),
    # Separation
    ("a declared clearance below the signed figure", "separation: a declared figure is compared with the record", "separation_rule", "clearance of 2 mm, below the signed 3 mm", mains_rule("(constraint clearance (min 3mm))", "(constraint clearance (min 2mm))")),
    ("a declared creepage below the signed figure", "separation: a declared figure is compared with the record", "separation_rule", "creepage of 3.5 mm, below the signed 4 mm", mains_rule("(constraint creepage (min 4mm))", "(constraint creepage (min 3.5mm))")),
    ("a later rule naming the Mains class that undercuts the signed figure", "separation: the signed rule prevails over later rules", "clearance", SIGNED, later_rule("A.hasNetclass('Mains')")),
    ("a later rule matching mains items without naming the Mains class", "separation: the signed rule prevails over later rules", "clearance", SIGNED, later_rule("A.Type == 'Pad' || A.Type == 'Track'")),
    ("a local clearance override on a mains pad", "separation: no override outranks the signed figure", "local_clearance_override", "pad 2 of R1", local_override(lambda tree: pad(tree, "R1", "2"))),
    ("a local clearance override on a mains footprint", "separation: no override outranks the signed figure", "local_clearance_override", "footprint R1", local_override(lambda tree: footprint(tree, "R1"))),
    ("a local clearance override on a low-voltage pad", "separation: no override outranks the signed figure", "local_clearance_override", "pad 1 of R2", local_override(lambda tree: pad(tree, "R2", "1"))),
    ("a clearance below the signed figure on a mains zone", "separation: no override outranks the signed figure", "local_clearance_override", "zone on Mains-class net /MAINS_L", mains_zone),
    ("a net class setting below the signed figure", "separation: the signed rule prevails over net class settings", "clearance", SIGNED, netclass_below),
    ("a Mains rule narrowed by layer", "separation: the Mains rule holds everywhere", "separation_rule", "narrowed by layer", mains_rule("(condition", "(layer outer)\n\t(condition")),
    ("a Mains rule narrowed by area", "separation: the Mains rule holds everywhere", "separation_rule", "narrowed by its condition", mains_rule(CONDITION, CONDITION + " && A.intersectsArea('mains')")),
    ("a Mains rule holding only clearance", "separation: the Mains rule holds both distances", "separation_rule", "no creepage constraint", mains_rule("\n\t(constraint creepage (min 4mm))", "")),
    ("a Mains rule holding only creepage", "separation: the Mains rule holds both distances", "separation_rule", "no clearance constraint", mains_rule("\n\t(constraint clearance (min 3mm))", "")),
    ("a mains-carrying design with no Mains rule", "separation: a mains-carrying design declares its basis", "separation_rule", "no custom rule has the condition", lambda seed: seed.write(".kicad_dru", "(version 1)\n")),
    ("a mains-carrying design with no rules file", "separation: a mains-carrying design declares its basis", "separation_rule", "no custom rules file", remove(".kicad_dru")),
    ("a design silent on whether it carries mains", "separation: MAINS is declared", "mains_declaration", "MAINS is not set", variables(lambda v: v.pop("MAINS"))),
    ("a design declaring an invalid MAINS value", "separation: MAINS is declared", "mains_declaration", "MAINS is 'yes'", variables(lambda v: v.update(MAINS="yes"))),
    ("a design declaring no mains while carrying a Mains-class net", "separation: MAINS agrees with the Mains class", "mains_declaration", "MAINS is none but", variables(lambda v: v.update(MAINS="none"))),
    ("a design declaring mains with no net in the Mains class", "separation: MAINS agrees with the Mains class", "mains_declaration", "no copper on the layout is in the Mains",
     lambda seed: seed.project(lambda data: data["net_settings"]["netclass_patterns"][0].update(pattern="/NOTHING_*"))),
    ("a missing basis record", "separation: the basis record exists", "separation_basis", "no separation-basis.yaml", remove("separation-basis.yaml")),
    ("a basis record that cannot be parsed", "separation: the basis record is readable", "separation_basis", "cannot be parsed", record("mains_to_low_voltage:\n", "mains_to_low_voltage: [unclosed\n")),
    ("a basis record lacking a figure", "separation: the basis record states both figures", "separation_basis", "lacks mains_to_low_voltage.creepage_mm", record("  creepage_mm: 4.0\n", "")),
    ("a basis record with a figure that is not a positive number", "separation: the basis record states both figures", "separation_basis", "not a positive number", record("clearance_mm: 3.0", "clearance_mm: 0")),
    ("a basis record with no acceptor", "separation: the basis record is signed", "separation_basis", "accepted_by is missing", record("accepted_by: david\n", "")),
    ("a basis record whose acceptor is a placeholder", "separation: the basis record is signed", "separation_basis", "is a placeholder", record("accepted_by: david", "accepted_by: TBD")),
    ("a basis record with no acceptance date", "separation: the basis record is signed", "separation_basis", "accepted_on, the date", record("accepted_on: 2026-10-12\n", "")),
    ("a basis record with an invalid acceptance date", "separation: the basis record is signed", "separation_basis", "not a valid calendar date", record("accepted_on: 2026-10-12", "accepted_on: '12/10/2026'")),
    ("a basis record accepted on a future date", "separation: the basis record is signed", "separation_basis", "later than today", record("accepted_on: 2026-10-12", "accepted_on: 2999-01-01")),
    ("a synthetic basis record applied to a design not marked not for manufacture", "separation: a synthetic record cannot pass an orderable board", "separation_basis", "marked synthetic", variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
]


def prepare(scratch: str) -> Seed:
    root = os.path.join(scratch, "repository")
    shutil.copytree(PROOF, os.path.join(root, DESIGN))
    subprocess.run(["git", "init", "-q", root], check=True)
    return Seed(root)


def check(seed: Seed, kicad_cli: str) -> Tuple[int, List[str], str]:
    subprocess.run(["git", "-C", seed.root, "add", "-A"], check=True)
    result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_check.py"), "--root", seed.root,
                             "--kicad-cli", kicad_cli], capture_output=True, text=True)
    return result.returncode, result.stdout.splitlines(), result.stderr.strip()


def prove(fault, kicad_cli: str) -> Tuple[bool, str]:
    name, _, rule, text, edit = fault
    with tempfile.TemporaryDirectory(prefix="board-prove-") as scratch:
        seed = prepare(scratch)
        edit(seed)
        status, lines, stderr = check(seed, kicad_cli)
    if status == 2:
        return False, f"the check could not run: {stderr}"
    for line in lines:
        fields = [field.strip() for field in line.split("|")]
        if fields[0] == "VIOLATION" and len(fields) == 5 and fields[2] == rule and text in line:
            return status == 1, line if status == 1 else f"exit status {status} despite: {line}"
    return False, f"exit status {status}; no {rule} violation carrying {text!r} among: " + " / ".join(lines[1:])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    parser.add_argument("only", nargs="*", help="prove only the faults whose name contains one of these")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        board_check.require_yaml()
        board_check.require_kicad(args.kicad_cli)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="board-prove-") as scratch:
        seed = prepare(scratch)
        status, lines, stderr = check(seed, args.kicad_cli)
    clean_ok = status == 0
    print(f"{'CLEAN' if clean_ok else 'DIRTY'} | the throwaway design as committed | must pass | "
          + (" / ".join(lines[1:]) if lines else stderr))

    faults = [fault for fault in FAULTS if not args.only or any(word in fault[0] for word in args.only)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        outcomes = list(pool.map(lambda fault: prove(fault, args.kicad_cli), faults))
    missed = 0
    for (name, proves, _, _, _), (caught, evidence) in zip(faults, outcomes):
        missed += 0 if caught else 1
        print(f"{'CAUGHT' if caught else 'MISSED'} | {name} | {proves} | {evidence}")
    print(f"RESULT | {'PASS' if clean_ok and not missed else 'FAIL'} | {len(faults) - missed} of {len(faults)} faults caught"
          + ("" if clean_ok else "; the clean design did not pass"))
    return 0 if clean_ok and not missed else 1


if __name__ == "__main__":
    sys.exit(main())
