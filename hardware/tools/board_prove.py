#!/usr/bin/env python3
"""Break the throwaway proof design on purpose, once per failure condition, and require the check to notice.

Every failure condition the pre-order check enforces gets a fault seeded for it
here. Each fault is introduced into a fresh copy of hardware/proof/gate-proof, or,
for the faults about the keys of the records, of hardware/proof/record-keys-proof,
in a temporary directory outside the repository, made into a git work tree of its
own and committed, so the check finds designs exactly as it does in the
repository, and the shipped check is run on it. A fault counts as caught only when the check exits
non-zero *and* reports a violation of the rule the fault was seeded for, with
the text that names it; a check that failed for some other reason has not shown
it can see this one. The clean copy of each design must pass, or a fault being caught would
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
import copy
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Callable, Dict, List, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
DESIGN = "hardware/proof/gate-proof"
NAME = "gate-proof"
#: The proof design of the record keys, a folder of its own with records of its own, which the faults about those
#: keys are seeded into. A fault names its design by a sixth element; one that names none is seeded into DESIGN.
KEYS_DESIGN = "hardware/proof/record-keys-proof"
KEYS_NAME = "record-keys-proof"
KEYS_TARGET = (KEYS_DESIGN, KEYS_NAME)
#: The circuit-review proof design, whose integrated circuit U4 leaves ten pins on no other pin and no rail, each on a net of its own
#: and none listed in the pin-limit record.
REVIEW_DESIGN = "hardware/proof/circuit-review-proof"
REVIEW_NAME = "circuit-review-proof"
#: The layout review proof design, the only one with a sensing net class and a ground net class, which the faults about the
#: board rules record's sensing and ground returns are seeded into.
SENSING_DESIGN = "hardware/proof/review-proof"
SENSING_NAME = "review-proof"
SENSING_TARGET = (SENSING_DESIGN, SENSING_NAME)
#: The records the proof designs share, found by the nearest-folder rule above their own folders, by path from the
#: repository's root. A seeded copy carries them beside the design so it is held to them as the repository's designs are.
SHARED_RECORDS = ("hardware/proof/manufacturer-limits.yaml",)


class Seed:
    """A copy of a proof design in a temporary git work tree, and the edits a fault makes to it.

    The design is gate-proof unless another is named, by its folder from the
    repository's root and the name its project, schematic and layout share.
    """

    def __init__(self, root: str, design: str = DESIGN, name: str = NAME):
        self.root = root
        self.name = name
        self.design = os.path.join(root, design)
        #: Edits made after the seeded copy is committed, for faults that are
        #: about what the commit does not hold.
        self.after: List[Callable[["Seed"], None]] = []
        #: Variables set in the check's own environment, for faults that are
        #: about what the machine running the check holds.
        self.environment: Dict[str, str] = {}
        #: The kicad-cli the check is run with, known once it is run.
        self.kicad_cli = "kicad-cli"
        #: Every file the design is copied with, by its path inside the design's folder.
        self.files: List[str] = []

    def path(self, suffix: str) -> str:
        return os.path.join(self.design, self.name + suffix) if suffix.startswith(".") else os.path.join(self.design, suffix)

    def read(self, suffix: str) -> str:
        with open(self.path(suffix), encoding="utf-8") as handle:
            return handle.read()

    def replace_shared(self, record: str, old: str, new: str) -> None:
        """Replace text in a record the proof designs share, by its path from the repository's root, in this copy only."""
        path = os.path.join(self.root, record)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if old not in text:
            raise AssertionError(f"the shared record {record} no longer contains {old!r}; the fault cannot be seeded")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace(old, new, 1))

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
        self.write(".kicad_pro", json.dumps(data, indent=2) + "\n")

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


def segment(net: str, x1: float, y1: float, x2: float, y2: float, uuid: str, layer: str = "F.Cu") -> list:
    Q = sexpr.Quoted
    return ["segment", ["start", f"{x1:g}", f"{y1:g}"], ["end", f"{x2:g}", f"{y2:g}"], ["width", "0.25"],
            ["layer", Q(layer)], ["net", Q(net)], ["uuid", Q(uuid)]]


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


def pin_record(old: str, new: str):
    return lambda seed: seed.replace("pin-allocation.yaml", old, new)


def swap_labels(first: Tuple[str, str], second: Tuple[str, str]):
    """Exchange the net names of two labels, each given as (its text, its position), so each net lands where the other was."""
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            found = []
            for item in sexpr.children(tree, "label"):
                at = sexpr.child(item, "at")
                for wanted in (first, second):
                    if item[1] == wanted[0] and " ".join(at[1:3]) == wanted[1]:
                        found.append(item)
            if len(found) != 2:
                raise AssertionError("the proof schematic no longer has the two labels to exchange")
            found[0][1], found[1][1] = found[1][1], found[0][1]
        seed.schematic(edit)
    return seed_it


def drop_net_labels(name: str):
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            labels = [item for item in sexpr.children(tree, "label") if item[1] == name]
            if not labels:
                raise AssertionError(f"the proof schematic has no label {name}")
            for item in labels:
                tree.remove(item)
        seed.schematic(edit)
    return seed_it


def rename_reference(old: str, new: str):
    return lambda seed: seed.schematic(lambda tree: rename_in(tree, old, new))


def rename_in(node, old: str, new: str) -> None:
    if isinstance(node, list):
        for index, item in enumerate(node):
            if item == old and index > 0 and node[index - 1] in ("reference", "Reference"):
                node[index] = new
            else:
                rename_in(item, old, new)


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


def git(seed: Seed, *args: str) -> None:
    subprocess.run(["git", "-C", seed.root, "-c", "user.name=board-prove", "-c", "user.email=board-prove@invalid",
                    *args], check=True, capture_output=True)


def untrack(suffix: str):
    """Leave the file on disk but take it out of the commit."""
    def seed_it(seed: Seed) -> None:
        relative = os.path.relpath(seed.path(suffix), seed.root)
        seed.after.append(lambda seed: (git(seed, "rm", "-q", "--cached", "--", relative),
                                        git(seed, "commit", "-q", "-m", f"untrack {relative}")))
    return seed_it


def drop_field(reference: str, field: str):
    """The symbol field `field` taken off the symbol at `reference`, in the schematic."""
    def edit(tree: list) -> None:
        for symbol in sexpr.children(tree, "symbol"):
            fields = sexpr.children(symbol, "property")
            if any(len(prop) > 2 and prop[1] == "Reference" and prop[2] == reference for prop in fields):
                symbol[:] = [item for item in symbol
                             if not (sexpr.head(item) == "property" and len(item) > 1 and item[1] == field)]
                return
        raise AssertionError(f"the proof schematic has no symbol {reference}")
    return lambda seed: seed.schematic(edit)


def set_field(reference: str, field: str, value: str):
    """The symbol field `field` of the symbol at `reference` given the text `value`, in the schematic."""
    def edit(tree: list) -> None:
        for symbol in sexpr.children(tree, "symbol"):
            for prop in sexpr.children(symbol, "property"):
                if len(prop) > 2 and prop[1] == "Reference" and prop[2] == reference:
                    for target in sexpr.children(symbol, "property"):
                        if len(target) > 2 and target[1] == field:
                            target[2] = sexpr.Quoted(value)
                            return
                    raise AssertionError(f"the proof symbol {reference} has no field {field}")
        raise AssertionError(f"the proof schematic has no symbol {reference}")
    return lambda seed: seed.schematic(edit)


def repeat_symbol(reference: str):
    """A second symbol carrying the reference `reference`, a copy of the first with a fresh identifier."""
    def edit(tree: list) -> None:
        for index, symbol in enumerate(tree):
            if sexpr.head(symbol) == "symbol" and any(
                    len(prop) > 2 and prop[1] == "Reference" and prop[2] == reference
                    for prop in sexpr.children(symbol, "property")):
                twin = copy.deepcopy(symbol)
                sexpr.child(twin, "uuid")[1] = sexpr.Quoted("0b0e5c1a-0000-4000-8000-0000000000e5")
                tree.insert(index + 1, twin)
                return
        raise AssertionError(f"the proof schematic has no symbol {reference}")
    return lambda seed: seed.schematic(edit)


def second_controller(reference: str, number: str):
    """A second controller, a copy of the symbol at `reference` renamed and carrying the catalogue number `number`."""
    def edit(tree: list) -> None:
        for index, symbol in enumerate(tree):
            if sexpr.head(symbol) == "symbol" and any(
                    len(prop) > 2 and prop[1] == "Reference" and prop[2] == reference
                    for prop in sexpr.children(symbol, "property")):
                twin = copy.deepcopy(symbol)
                rename_in(twin, reference, reference + "B")
                sexpr.child(twin, "uuid")[1] = sexpr.Quoted("0b0e5c1a-0000-4000-8000-0000000000e6")
                for prop in sexpr.children(twin, "property"):
                    if len(prop) > 2 and prop[1] == "LCSC":
                        prop[2] = sexpr.Quoted(number)
                tree.insert(index + 1, twin)
                return
        raise AssertionError(f"the proof schematic has no symbol {reference}")
    return lambda seed: seed.schematic(edit)


def parts(old: str, new: str):
    return lambda seed: seed.replace("parts-specification.yaml", old, new)


def extract(old: str, new: str):
    return lambda seed: seed.replace("catalogue-extract.yaml", old, new)


def derating(old: str, new: str):
    return lambda seed: seed.replace("derating-policy.yaml", old, new)


def pin_limits(old: str, new: str):
    return lambda seed: seed.replace("pin-limits.yaml", old, new)


def board_rules(old: str, new: str):
    return lambda seed: seed.replace("board-rules.yaml", old, new)


def limits(old: str, new: str):
    return lambda seed: seed.replace_shared(SHARED_RECORDS[0], old, new)


def resistor_over_its_rating(seed: Seed) -> None:
    """R1, across the mains pair, made a resistor of class resistor rated 100 V in the record and the schematic."""
    parts('    rating: "0.25W"\n    lcsc: "C9000002"\n    class: none',
          '    rating: "100V"\n    lcsc: "C9000002"\n    class: resistor')(seed)
    set_field("R1", "Rating", "100V")(seed)


def uncommitted_record(seed: Seed) -> None:
    seed.after.append(lambda seed: seed.replace("separation-basis.yaml", "accepted_by: david", "accepted_by: someone-else"))


def untracked_sheet(seed: Seed) -> None:
    shutil.copy(seed.path(".kicad_sch"), seed.path("sub.kicad_sch"))
    Q = sexpr.Quoted
    sheet = ["sheet", ["at", "200", "100"], ["size", "20", "10"], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000e1")],
             ["property", Q("Sheetname"), Q("sub"), ["at", "200", "99", "0"]],
             ["property", Q("Sheetfile"), Q("sub.kicad_sch"), ["at", "200", "111", "0"]]]
    seed.schematic(lambda tree: tree.insert(len(tree) - 1, sheet))
    untrack("sub.kicad_sch")(seed)


def forged_rule(seed: Seed) -> None:
    seed.write(".kicad_dru", seed.read(".kicad_dru") + f'(rule "{board_check.RESERVED}: rules loaded"\n'
                                                       "\t(condition \"A.Type == 'Pad'\")\n\t(constraint assertion \"false\"))\n")


def no_mains_but_assigned(seed: Seed) -> None:
    def edit(data: dict) -> None:
        data["text_variables"]["MAINS"] = "none"
        data["net_settings"]["netclass_patterns"][0]["pattern"] = "/NOTHING_*"
        data["net_settings"]["netclass_assignments"] = {"/UNROUTED": "Mains"}
    seed.project(edit)


def no_mains_patterns(data: dict) -> None:
    data["net_settings"]["netclass_patterns"][0]["pattern"] = "/NOTHING_*"


def mains_flag_on_lv_b(seed: Seed) -> None:
    """A schematic net class directive putting /LV_B, R2 pin 2's net, in Mains."""
    Q = sexpr.Quoted
    flag = ["netclass_flag", Q(""), ["length", "2.54"], ["shape", "round"], ["at", "45.72", "78.74", "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", "left", "bottom"]],
            ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000e2")],
            ["property", Q("Netclass"), Q("Mains"), ["at", "46.4", "76.2", "0"],
             ["effects", ["font", ["size", "1.27", "1.27"], "italic"], ["justify", "left"]]]]
    seed.schematic(lambda tree: tree.insert(len(tree) - 1, flag))


def no_mains_but_schematic_class(seed: Seed) -> None:
    seed.project(lambda data: (data["text_variables"].update(MAINS="none"), no_mains_patterns(data)))
    mains_flag_on_lv_b(seed)


def schematic_only_mains(seed: Seed) -> None:
    seed.project(no_mains_patterns)
    mains_flag_on_lv_b(seed)


def project_only_mains(seed: Seed) -> None:
    def edit(data: dict) -> None:
        no_mains_patterns(data)
        data["net_settings"]["netclass_assignments"] = {"/UNROUTED": "Mains"}
    seed.project(edit)


def layout_only_mains(seed: Seed) -> None:
    """A net class block in the layout file itself, as older KiCad versions wrote, putting /LV_A in Mains."""
    Q = sexpr.Quoted
    block = ["net_class", Q("Mains"), Q("written by an older KiCad"), ["clearance", "0.5"], ["add_net", Q("/LV_A")]]
    seed.layout(lambda tree: tree.insert(tree.index(sexpr.child(tree, "paper")) + 1, block))


def project_and_layout_not_schematic(seed: Seed) -> None:
    seed.project(lambda data: data["net_settings"].update(netclass_assignments={"/LV_A": "Mains"}))


def library_uri(new: str):
    return lambda seed: seed.replace("fp-lib-table", "${KIPRJMOD}/proof.pretty", new)


def untracked_library(seed: Seed) -> None:
    for name in os.listdir(seed.path("proof.pretty")):
        untrack(os.path.join("proof.pretty", name))(seed)


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


def second_condition(seed: Seed) -> None:
    """The Mains rule in its form, then a second condition, which KiCad keeps in place of the first."""
    seed.replace(".kicad_dru", f'(condition "{CONDITION}")', f'(condition "{CONDITION}")\n\t(condition "A.Type == \'Via\'")')


def rule(name: str, condition: str, body: str = "(constraint clearance (min 1mm))"):
    return lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + f'(rule "{name}"\n\t(condition "{condition}")\n\t{body})\n')


def mains_constraint(text: str):
    return mains_rule("\n\t(constraint creepage (min 4mm))", "\n\t(constraint creepage (min 4mm))\n\t" + text)


def project_text(old: str, new: str):
    return lambda seed: seed.replace(".kicad_pro", old, new)


def table_entry(old: str, new: str):
    return lambda seed: seed.replace("fp-lib-table", old, new)


def empty_table(kind: str):
    return lambda seed: seed.write(f"{kind}-lib-table", f"({kind}_lib_table\n\t(version 7)\n)\n")


def machine_table_library(seed: Seed) -> None:
    """The footprint library named only by the KiCad tables of whoever runs the check, not by the design's own.

    The design's table drops the library and a copy of it outside the
    repository is named from the global table of a KiCad configuration the
    check is run under, as a library set up once on one machine would be. KiCad
    run as that user finds every footprint; a reader without that setup would not.
    """
    outside = os.path.join(os.path.dirname(seed.root), "machine-libraries")
    home = os.path.join(os.path.dirname(seed.root), "machine-kicad")
    shutil.copytree(seed.path("proof.pretty"), os.path.join(outside, "proof.pretty"))
    empty_table("fp")(seed)
    seed.environment["KICAD_CONFIG_HOME"] = home
    seed.after.append(lambda seed: machine_configuration(seed.kicad_cli, home, os.path.join(outside, "proof.pretty")))


def machine_configuration(kicad_cli: str, home: str, library: str) -> None:
    """A KiCad configuration in `home` whose own footprint table names `library` as 'proof'."""
    os.makedirs(home, exist_ok=True)
    subprocess.run([kicad_cli, "version"], env={**os.environ, "KICAD_CONFIG_HOME": home}, capture_output=True, check=True)
    folder = next(os.path.join(home, name) for name in os.listdir(home) if os.path.isdir(os.path.join(home, name)))
    with open(os.path.join(folder, "fp-lib-table"), "w", encoding="utf-8") as handle:
        handle.write(f'(fp_lib_table\n\t(version 7)\n\t(lib (name "proof")(type "KiCad")(uri "{library}")(options "")(descr ""))\n)\n')


def twice_named_sheet(seed: Seed) -> None:
    shutil.copy(seed.path(".kicad_sch"), seed.path("sub.kicad_sch"))
    Q = sexpr.Quoted
    sheet = ["sheet", ["at", "200", "100"], ["size", "20", "10"], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000e3")],
             ["property", Q("Sheetname"), Q("sub"), ["at", "200", "99", "0"]],
             ["property", Q("Sheetfile"), Q("sub.kicad_sch"), ["at", "200", "111", "0"]],
             ["property", Q("Sheetfile"), Q("gate-proof.kicad_sch"), ["at", "200", "113", "0"]]]
    seed.schematic(lambda tree: tree.insert(len(tree) - 1, sheet))


def subsheet(seed: Seed, name: str, uuid: str, edit: Optional[Callable[[list], None]] = None) -> None:
    """A copy of the schematic placed below it as a sheet called `name`, with `edit` made to the copy."""
    shutil.copy(seed.path(".kicad_sch"), seed.path("sub.kicad_sch"))
    Q = sexpr.Quoted
    sheet = ["sheet", ["at", "200", "100"], ["size", "20", "10"], ["uuid", Q(uuid)],
             ["property", Q("Sheetname"), Q(name), ["at", "200", "99", "0"]],
             ["property", Q("Sheetfile"), Q("sub.kicad_sch"), ["at", "200", "111", "0"]]]
    seed.schematic(lambda tree: tree.insert(len(tree) - 1, sheet))
    if edit is not None:
        # KiCad lists a symbol under the sheet its instance names, so the copy's parts are moved down to the sheet
        # for the nets they join to be read there.
        root_path = "/" + sexpr.child(sexpr.parse_one(seed.read(".kicad_sch")), "uuid")[1]
        text = seed.read("sub.kicad_sch").replace(f'(path "{root_path}"', f'(path "{root_path}/{uuid}"')
        tree = sexpr.parse_one(text)
        edit(tree)
        seed.write("sub.kicad_sch", sexpr.dump(tree) + "\n")


def sheet_named(name: str):
    return lambda seed: subsheet(seed, name, "0b0e5c1a-0000-4000-8000-0000000000e5")


def generated_net_on_subsheet(seed: Seed) -> None:
    """A sub-sheet with no labels, R1 pin 1 wired to R2 pin 1 and nothing else: that net is KiCad's to name, and
    R1 pin 2, flagged no-connect, and every other pin are nothing's, which KiCad names `unconnected-` and carries no net."""
    Q = sexpr.Quoted

    def wire(uuid: str, start: Tuple[str, str], end: Tuple[str, str]) -> list:
        return ["wire", ["pts", ["xy", *start], ["xy", *end]], ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Q(uuid)]]

    def edit(tree: list) -> None:
        for item in sexpr.children(tree, "label"):
            tree.remove(item)
        for number, (start, end) in enumerate([(("63.5", "48.26"), ("70", "48.26")), (("70", "48.26"), ("70", "73.66")),
                                               (("70", "73.66"), ("63.5", "73.66"))]):
            tree.insert(len(tree) - 1, wire(f"0b0e5c1a-0000-4000-8000-0000000000f{number + 3}", start, end))
        tree.insert(len(tree) - 1, ["no_connect", ["at", "63.5", "55.88"], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000f2")]])
    subsheet(seed, "sub", "0b0e5c1a-0000-4000-8000-0000000000e6", edit)


def net_tie(group: str, extra_pad: bool):
    """R1, whose pads carry /MAINS_L and /MAINS_N, made a net tie over `group`; with a third pad on /LV_A if asked."""
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            item = footprint(tree, "R1")
            if extra_pad:
                third = copy.deepcopy(pad(tree, "R1", "2"))
                third[1] = sexpr.Quoted("3")
                sexpr.child(third, "at")[1:3] = ["10.16", "8"]
                third[third.index(sexpr.child(third, "net"))] = ["net", sexpr.Quoted("/LV_A")]
                sexpr.child(third, "uuid")[1] = sexpr.Quoted("0b0e5c1a-0000-4000-8000-0000000000e4")
                item.insert(item.index(pad(tree, "R1", "2")) + 1, third)
            item.insert(item.index(sexpr.child(item, "at")) + 1, ["net_tie_pad_groups", sexpr.Quoted(group)])
        seed.layout(edit)
    return seed_it


def unfilled_pour_by_mains(seed: Seed) -> None:
    """A low-voltage pour around R1's mains pad 2, saved unfilled: filled, it keeps the signed clearance but not the creepage."""
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000a9")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "20", "5"], ["xy", "34", "5"], ["xy", "34", "15"], ["xy", "20", "15"]]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))


def track_at(tree: list, a: Tuple[float, float], b: Tuple[float, float]) -> list:
    """The proof layout's track from `a` to `b`, either way round."""
    for item in sexpr.children(tree, "segment"):
        ends = [tuple(float(value) for value in sexpr.child(item, key)[1:3]) for key in ("start", "end")]
        if sorted(ends) == sorted([a, b]):
            return item
    raise AssertionError(f"the proof layout has no track from {a} to {b}; the fault cannot be seeded")


#: Where the proof layout's /LV_A track runs, from J2's pad 1 to R2's pad 1, and
#: /LV_B's 45-degree run into R2's pad 2.
LV_A_ENDS = ((40.0, 10.0), (45.0, 10.0))
LV_B_RUN = ((40.0, 12.54), (52.62, 12.54))
LV_B_BEND = ((52.62, 12.54), (55.16, 10.0))


def reroute(net: str, removed, points, widths: Optional[Tuple[float, ...]] = None):
    """The tracks running between each pair of `removed` ends replaced by tracks through `points` in turn, each
    0.25 mm wide or as `widths` gives."""
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            for ends in removed:
                tree.remove(track_at(tree, *ends))
            for index, (a, b) in enumerate(zip(points, points[1:])):
                item = segment(net, *a, *b, f"0b0e5c1a-0000-4000-8000-0000000001{index:02d}")
                if widths:
                    sexpr.child(item, "width")[1] = f"{widths[index]:g}"
                tree.insert(len(tree) - 1, item)
        seed.layout(edit)
    return seed_it


def stub(seed: Seed) -> None:
    """A /LV_A track leaving R2's pad 1 and ending 1.5 mm away in free space, which KiCad reports unaided."""
    seed.layout(lambda tree: tree.insert(len(tree) - 1, segment("/LV_A", 45, 10, 45, 8.5, "0b0e5c1a-0000-4000-8000-000000000201")))


def unneeded_via(seed: Seed) -> None:
    """A via on /LV_A where its track runs on, on the one layer, joining nothing to anything."""
    Q = sexpr.Quoted
    def edit(tree: list) -> None:
        tree.remove(track_at(tree, *LV_A_ENDS))
        for index, (a, b) in enumerate((((40, 10), (42, 10)), ((42, 10), (45, 10)))):
            tree.insert(len(tree) - 1, segment("/LV_A", *a, *b, f"0b0e5c1a-0000-4000-8000-00000000030{index}"))
        tree.insert(len(tree) - 1, ["via", ["at", "42", "10"], ["size", "0.9"], ["drill", "0.4"],
                                    ["layers", Q("F.Cu"), Q("B.Cu")], ["net", Q("/LV_A")],
                                    ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000302")]])
    seed.layout(edit)


def long_pad(seed: Seed) -> None:
    """R2's pad 1, which /LV_A enters from the side, made an oval 3.6 mm tall and 1.6 mm wide."""
    def edit(tree: list) -> None:
        item = pad(tree, "R2", "1")
        item[3] = "oval"
        sexpr.child(item, "size")[1:3] = ["1.6", "3.6"]
    seed.layout(edit)


def token_zone(seed: Seed) -> None:
    """A 2 mm square /LV_A pour over R2's pad 1, which once took a net with any zone out of the route-length rule."""
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000501")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "44", "9"], ["xy", "46", "9"], ["xy", "46", "11"], ["xy", "44", "11"]]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))


def pour_short_of_pad(seed: Seed) -> None:
    """/LV_A looping the long way round and ending 2.5 mm short of R2's pad 1, inside a pour of its net over the pad,
    which once left the pad out of the route-length rule's tree and the net unmeasured."""
    reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (40, 6), (41, 5), (44, 5), (45, 6), (45, 7.5)])(seed)
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000502")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "44", "7"], ["xy", "46", "7"], ["xy", "46", "11"], ["xy", "44", "11"]]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))


def small_part(reference: str, x: float, y: float, uuid: str, *pads) -> list:
    """A footprint `reference` at (x, y) holding pads given as (number, technology, layers, net, x, y, size)."""
    Q = sexpr.Quoted
    body = [["layer", Q("F.Cu")], ["uuid", Q(uuid)], ["at", f"{x:g}", f"{y:g}"],
            ["property", Q("Reference"), Q(reference), ["at", "0", "-2", "0"], ["layer", Q("F.SilkS")]]]
    for index, (number, technology, layers, net, dx, dy, size) in enumerate(pads):
        item = ["pad", Q(number), technology, "circle" if technology == "thru_hole" else "rect", ["at", f"{dx:g}", f"{dy:g}"],
                ["size", f"{size:g}", f"{size:g}"]]
        if technology == "thru_hole":
            item.append(["drill", "0.8"])
        item += [["layers", *[Q(layer) for layer in layers]], ["net", Q(net)], ["uuid", Q(f"{uuid[:-2]}{index + 1:02d}")]]
        body.append(item)
    return ["footprint", Q("proof:Seeded_Part"), *body]


def track_under_bridging_part(seed: Seed) -> None:
    """A part with a pad on Mains-class /MAINS_L and one on /LV_A, 6 mm apart, and a /LV_B track running between them."""
    thru = ("thru_hole", ["*.Cu", "*.Mask"])
    part = small_part("X1", 30, 4, "0b0e5c1a-0000-4000-8000-000000000800", ("1", *thru, "/MAINS_L", 0, 0, 1.6),
                      ("2", *thru, "/LV_A", 6, 0, 1.6))
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, part),
                              tree.insert(len(tree) - 1, segment("/LV_B", 32, 4, 34, 4, "0b0e5c1a-0000-4000-8000-000000000801"))))


def via_under_paste(seed: Seed) -> None:
    """A surface-mount pad of /LV_A, paste layer and all, with a 0.3 mm /LV_A via drilled through its middle."""
    Q = sexpr.Quoted
    part = small_part("X2", 30, 4, "0b0e5c1a-0000-4000-8000-000000000900",
                      ("1", "smd", ["F.Cu", "F.Paste", "F.Mask"], "/LV_A", 0, 0, 1.5))
    hole = ["via", ["at", "30", "4"], ["size", "0.6"], ["drill", "0.3"], ["layers", Q("F.Cu"), Q("B.Cu")],
            ["net", Q("/LV_A")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000901")]]
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, part), tree.insert(len(tree) - 1, hole)))


def track_beside_pour(seed: Seed) -> None:
    """A /LV_A pour 8 mm by 5 mm and, 0.08 mm off its upper edge and parallel to it, a /LV_A track: the fill stops short of
    the track by less than the 0.15 mm minimum clearance the project states, where KiCad compares no copper of one net."""
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000a00")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"], ["island_removal_mode", "1"]],
            ["polygon", ["pts", ["xy", "30", "2"], ["xy", "38", "2"], ["xy", "38", "7"], ["xy", "30", "7"]]]]
    seed.project(lambda data: data["board"]["design_settings"]["rules"].update(min_clearance=0.15))
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, zone),
                              tree.insert(len(tree) - 1, segment("/LV_A", 30, 7.205, 38, 7.205, "0b0e5c1a-0000-4000-8000-000000000a01"))))


def barrier_part(seed: Seed, second: Tuple[str, str, float, float]) -> None:
    """A part with a pad on Mains-class /MAINS_L at its origin and a second pad given as (net, technology, x, y) off it,
    where a net of "" leaves the pad with none."""
    thru = ["*.Cu", "*.Mask"]
    net, _, dx, dy = second
    part = small_part("X1", 30, 4, "0b0e5c1a-0000-4000-8000-000000000b00", ("1", "thru_hole", thru, "/MAINS_L", 0, 0, 1.6),
                      ("2", "thru_hole", thru, net or "/LV_A", dx, dy, 1.6))
    if not net:
        for item in sexpr.children(part, "pad")[1:]:
            item.remove(sexpr.child(item, "net"))
    seed.layout(lambda tree: tree.insert(len(tree) - 1, part))


def crystal_part(seed: Seed) -> None:
    """R2 renamed, in the layout, to a footprint of a crystal's name: a board with a crystal."""
    seed.layout(lambda tree: footprint(tree, "R2").__setitem__(1, sexpr.Quoted("proof:Crystal_Seeded")))


def keep_clear_exempting_all(seed: Seed) -> None:
    """The crystal keep-clear written for R2 with an exemption for every other footprint of the board."""
    others = [board_check.board_geometry.reference(item)
              for item in sexpr.children(sexpr.parse_one(seed.read(".kicad_pcb")), "footprint")]
    crystal_part(seed)
    exempt = "".join(f" && B.Reference != '{name}'" for name in others if name != "R2")
    rule("Crystal keep-clear", f"A.Reference == 'R2'{exempt}", "(constraint courtyard_clearance (min 25mm))")(seed)


def ground_class(seed: Seed) -> None:
    """A Ground net class holding /LV_B, whose pads then want thermal reliefs."""
    def edit(data: dict) -> None:
        classes = data["net_settings"]["classes"]
        classes.append({**copy.deepcopy(classes[0]), "name": "Ground"})
        data["net_settings"]["netclass_patterns"].append({"netclass": "Ground", "pattern": "/LV_B"})
    seed.project(edit)


def reliefs_exempting_a_plain_pad(seed: Seed) -> None:
    """The ground pad reliefs written with an exemption for R2's pad 2, an ordinary pad on /LV_B."""
    ground_class(seed)
    rule("Ground pad reliefs", "A.Type == 'Pad' && A.hasNetclass('Ground') && !(A.Reference == 'R2' && A.Pad_Number == '2')",
         "(constraint zone_connection thermal_reliefs)")(seed)


def bowed(net: str, start: Tuple[float, float], heading: float, length: float, half_sweep: float, uuid: str) -> list:
    """An arc from `start` along a chord `length` long at `heading` degrees, turning `half_sweep` degrees either side of it."""
    Q = sexpr.Quoted
    chord, turn = math.radians(heading), math.radians(half_sweep)
    end = (start[0] + length * math.cos(chord), start[1] + length * math.sin(chord))
    rise = length / 2 * math.tan(turn / 2)
    mid = ((start[0] + end[0]) / 2 - rise * math.sin(chord), (start[1] + end[1]) / 2 + rise * math.cos(chord))
    return ["arc", ["start", f"{start[0]:.6f}", f"{start[1]:.6f}"], ["mid", f"{mid[0]:.6f}", f"{mid[1]:.6f}"],
            ["end", f"{end[0]:.6f}", f"{end[1]:.6f}"], ["width", "0.25"], ["layer", Q("F.Cu")], ["net", Q(net)], ["uuid", Q(uuid)]]


def flat_arcs(seed: Seed) -> None:
    """/LV_A drawn as two flat arcs meeting at 160 degrees, each bowed 2 degrees either side of a chord 10 degrees off the
    board's edges, which the direction rule once passed by leaving every arc to the corner rule."""
    def edit(tree: list) -> None:
        tree.remove(track_at(tree, *LV_A_ENDS))
        middle = (40 + 2.5, 10 + 2.5 * math.tan(math.radians(10)))
        tree.insert(len(tree) - 1, bowed("/LV_A", (40, 10), 10, math.dist((40, 10), middle), 2, "0b0e5c1a-0000-4000-8000-000000000601"))
        tree.insert(len(tree) - 1, bowed("/LV_A", middle, -10, math.dist(middle, (45, 10)), 2, "0b0e5c1a-0000-4000-8000-000000000602"))
    seed.layout(edit)


def rectangle_outline(seed: Seed) -> None:
    """The board's outline redrawn as one rectangle, with a 3 mm square cut out of it turned to the off-angle /LV_A track,
    which the direction rule once took for the board's edges, reading the rectangle as a side 1 mm long."""
    Q = sexpr.Quoted
    turn = math.atan2(0.3, 5)
    corners = [(33 + 1.5 * (x * math.cos(turn) - y * math.sin(turn)), 16 + 1.5 * (x * math.sin(turn) + y * math.cos(turn)))
               for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    def edit(tree: list) -> None:
        for item in [node for node in tree if sexpr.head(node) == "gr_line"
                     and str((sexpr.child(node, "layer") or [None, None])[1]) == "Edge.Cuts"]:
            tree.remove(item)
        stroke = ["stroke", ["width", "0.1"], ["type", "default"]]
        tree.insert(len(tree) - 1, ["gr_rect", ["start", "0", "0"], ["end", "60", "20"], stroke, ["fill", "no"],
                                    ["layer", Q("Edge.Cuts")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000701")]])
        tree.insert(len(tree) - 1, ["gr_poly", ["pts", *[["xy", f"{x:.6f}", f"{y:.6f}"] for x, y in corners]], stroke,
                                    ["fill", "no"], ["layer", Q("Edge.Cuts")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000702")]])
    seed.layout(edit)
    reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (45, 10.3)])(seed)


def custom_pad(seed: Seed) -> None:
    """R2's pad 1, which /LV_A runs into, made a custom-shaped pad whose copper the check does not size."""
    def edit(tree: list) -> None:
        item = pad(tree, "R2", "1")
        item[3] = "custom"
        item.append(["options", ["clearance", "outline"], ["anchor", "circle"]])
        item.append(["primitives", ["gr_poly", ["pts", ["xy", "0", "-0.8"], ["xy", "1.2", "0"], ["xy", "0", "0.8"]],
                                    ["width", "0"], ["fill", "yes"]]])
    seed.layout(edit)


def via_in_decoupling_path(seed: Seed) -> None:
    """U1's two pads typed as power inputs, a capacitor C9 across them 6 mm below U1, and a /LV_A via between C9's /LV_A pad
    and U1's /LV_A pin."""
    Q = sexpr.Quoted
    thru = ("thru_hole", ["*.Cu", "*.Mask"])
    part = small_part("C9", 43, 16, "0b0e5c1a-0000-4000-8000-000000000d00", ("1", *thru, "/LV_A", 0, 0, 1.2),
                      ("2", *thru, "/LV_B", 2, 0, 1.2))
    hole = ["via", ["at", "43", "13"], ["size", "0.6"], ["drill", "0.3"], ["layers", Q("F.Cu"), Q("B.Cu")],
            ["net", Q("/LV_A")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000d01")]]

    def edit(tree: list) -> None:
        for number in ("1", "2"):
            pad(tree, "U1", number).append(["pintype", Q("power_in")])
        tree.insert(len(tree) - 1, part)
        tree.insert(len(tree) - 1, hole)
    seed.layout(edit)


def reference_removed(seed: Seed) -> None:
    """R1's reference text taken out of the footprint."""
    def edit(tree: list) -> None:
        part = footprint(tree, "R1")
        part.remove(next(item for item in sexpr.children(part, "property") if item[1] == "Reference"))
    seed.layout(edit)


def reference_on_fab(seed: Seed) -> None:
    """R1's reference text moved to the fabrication layer."""
    def edit(tree: list) -> None:
        text = next(item for item in sexpr.children(footprint(tree, "R1"), "property") if item[1] == "Reference")
        sexpr.child(text, "layer")[1] = sexpr.Quoted("F.Fab")
    seed.layout(edit)


def reference_in_courtyard(seed: Seed) -> None:
    """R1's reference text moved to the middle of R1, inside its own courtyard."""
    def edit(tree: list) -> None:
        text = next(item for item in sexpr.children(footprint(tree, "R1"), "property") if item[1] == "Reference")
        at = sexpr.child(text, "at")
        at[1:3] = ["0", "0"]
    seed.layout(edit)


def test_point_in_courtyard(seed: Seed) -> None:
    """A 1 mm test point TP9 placed at (20, 10) mm, on R1's body between its pads, inside R1's courtyard."""
    Q = sexpr.Quoted
    uuid = "0b0e5c1a-0000-4000-8000-000000000d00"
    point = ["footprint", Q("proof:Seeded_Test_Point"), ["layer", Q("F.Cu")], ["uuid", Q(uuid)], ["at", "20", "10"],
             ["property", Q("Reference"), Q("TP9"), ["at", "0", "-1.5", "0"], ["layer", Q("F.SilkS")]],
             ["pad", Q("1"), "smd", "circle", ["at", "0", "0"], ["size", "1", "1"], ["layers", Q("F.Cu"), Q("F.Mask")],
              ["uuid", Q(f"{uuid[:-2]}01")]]]
    seed.layout(lambda tree: tree.insert(len(tree) - 1, point))


def surface_mounted_r2(tree: list, bare: bool = True) -> list:
    """R2 turned into a surface-mount part on the front: its pads smd on the front copper, its attribute smd and, when
    `bare`, nothing drawn on its silkscreen but its reference text. Returns R2's footprint."""
    Q = sexpr.Quoted
    part = footprint(tree, "R2")
    for node in sexpr.children(part, "attr"):
        part.remove(node)
    part.insert(2, ["attr", "smd"])
    for node in sexpr.children(part, "pad"):
        node[2] = "smd"
        for drill in sexpr.children(node, "drill"):
            node.remove(drill)
        sexpr.child(node, "layers")[1:] = [Q("F.Cu"), Q("F.Mask")]
    if bare:
        for node in list(part):
            if isinstance(node, list) and node and str(node[0]).startswith("fp_") and str(node[0]) != "fp_text":
                layer = sexpr.child(node, "layer")
                if layer is not None and str(layer[1]) == "F.SilkS":
                    part.remove(node)
    return part


def through_hole_unmarked(seed: Seed) -> None:
    """R2 left a plated through-hole part, its drills and plating as the design has them, with nothing drawn on its front
    silkscreen and its schematic symbol a polarised capacitor's: the only thing that makes R2 polarised."""
    def edit(tree: list) -> None:
        part = footprint(tree, "R2")
        for node in list(part):
            if isinstance(node, list) and node and str(node[0]).startswith("fp_") and str(node[0]) != "fp_text":
                layer = sexpr.child(node, "layer")
                if layer is not None and str(layer[1]) == "F.SilkS":
                    part.remove(node)
    seed.layout(edit)
    polarised_symbol_r2(seed)


def polarised_symbol_r2(seed: Seed) -> None:
    """R2's schematic symbol made a polarised capacitor's, a copy of the resistor symbol named C_Polarized: the only thing
    that makes R2 polarised."""
    Q = sexpr.Quoted

    def edit(tree: list) -> None:
        library = sexpr.child(tree, "lib_symbols")
        source = next(item for item in sexpr.children(library, "symbol") if item[1] == "proof:R")
        copied = copy.deepcopy(source)
        copied[1] = Q("proof:C_Polarized")
        for unit in sexpr.children(copied, "symbol"):
            unit[1] = Q("C_Polarized" + str(unit[1])[1:])
        library.append(copied)
        for symbol in sexpr.children(tree, "symbol"):
            if any(len(p) > 2 and p[1] == "Reference" and p[2] == "R2" for p in sexpr.children(symbol, "property")):
                sexpr.child(symbol, "lib_id")[1] = Q("proof:C_Polarized")
                return
        raise AssertionError("the proof schematic has no symbol R2")
    seed.schematic(edit)


def fiducials_short(seed: Seed) -> None:
    """R2 a surface-mount part on the front, and two fiducials on the front, one short of the three the side needs."""
    Q = sexpr.Quoted

    def edit(tree: list) -> None:
        surface_mounted_r2(tree)
        for index in range(2):
            uuid = f"0b0e5c1a-0000-4000-8000-0000000{index}0e00"
            tree.insert(len(tree) - 1, ["footprint", Q("proof:Fiducial"), ["layer", Q("F.Cu")], ["uuid", Q(uuid)],
                                        ["at", f"{5 + 5 * index}", "30"], ["attr", "smd", "exclude_from_bom"],
                                        ["property", Q("Reference"), Q(f"FID{index + 1}"), ["at", "0", "-1.5", "0"], ["layer", Q("F.SilkS")]],
                                        ["pad", Q(""), "smd", "circle", ["at", "0", "0"], ["size", "1", "1"],
                                         ["property", "pad_prop_fiducial_glob"], ["layers", Q("F.Cu"), Q("F.Mask")],
                                         ["uuid", Q(f"{uuid[:-2]}01")]]])
    seed.layout(edit)


def three_nets_unmarked(seed: Seed) -> None:
    """R2 a surface-mount part on the front with a third pad on a third net and no mark of its first pin."""
    Q = sexpr.Quoted

    def edit(tree: list) -> None:
        part = surface_mounted_r2(tree)
        third = ["pad", Q("3"), "smd", "circle", ["at", "5.08", "3"], ["size", "1.6", "1.6"], ["layers", Q("F.Cu"), Q("F.Mask")],
                 ["net", Q("/MAINS_L")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000e03")]]
        part.insert(len(part) - 1, third)
    seed.layout(edit)


def capacitor_unmarked(seed: Seed) -> None:
    """R2 a surface-mount part of two pads and no mark, polarised only by its schematic symbol, a polarised capacitor's."""
    seed.layout(surface_mounted_r2)
    polarised_symbol_r2(seed)


def mark_on_back(seed: Seed) -> None:
    """The polarised R2 of two pads with a bar beside pad 1 drawn on B.SilkS, where a front part's mark does not belong, and
    only a line midway between its pads on F.SilkS."""
    Q = sexpr.Quoted

    def edit(tree: list) -> None:
        part = surface_mounted_r2(tree)
        part.insert(len(part) - 1, ["fp_line", ["start", "-1.5", "-1.5"], ["end", "-1.5", "1.5"], ["stroke", ["width", "0.12"], ["type", "solid"]],
                                    ["layer", Q("B.SilkS")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000e04")]])
        part.insert(len(part) - 1, ["fp_line", ["start", "5.08", "-1.5"], ["end", "5.08", "1.5"], ["stroke", ["width", "0.12"], ["type", "solid"]],
                                    ["layer", Q("F.SilkS")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000e06")]])
    seed.layout(edit)
    polarised_symbol_r2(seed)


def symmetric_outline(seed: Seed) -> None:
    """The polarised R2 of two pads outlined by four lines, whose end beside pad 1 stands nearer it than pad 2 but whose drawing is
    the same turned half way about the pads."""
    Q = sexpr.Quoted

    def edit(tree: list) -> None:
        part = surface_mounted_r2(tree)
        for index, (x1, y1, x2, y2) in enumerate(((-1.5, -1.5, 11.66, -1.5), (-1.5, 1.5, 11.66, 1.5), (-1.5, -1.5, -1.5, 1.5), (11.66, -1.5, 11.66, 1.5))):
            part.insert(len(part) - 1, ["fp_line", ["start", f"{x1:g}", f"{y1:g}"], ["end", f"{x2:g}", f"{y2:g}"],
                                        ["stroke", ["width", "0.12"], ["type", "solid"]], ["layer", Q("F.SilkS")],
                                        ["uuid", Q(f"0b0e5c1a-0000-4000-8000-0000000{index}0e05")]])
    seed.layout(edit)
    polarised_symbol_r2(seed)


def drop_rule(name: str):
    def seed_it(seed: Seed) -> None:
        text = seed.read(".kicad_dru")
        start = text.index(f'(rule "{name}"')
        end = text.index("\n(rule", start + 1) + 1 if "\n(rule" in text[start + 1:] else len(text)
        seed.write(".kicad_dru", text[:start] + text[end:])
    return seed_it


def seeded_hole(reference: str, x: float, y: float, uuid: str, plated_net: Optional[str] = None, courtyard: float = 0,
                pad: float = 3.2, surface_pad: bool = False, excluded: bool = False) -> list:
    """A 3.2 mm hole footprint `reference` at (x, y): a non-plated hole whose pad is `pad` mm across, or a plated pad on
    `plated_net` when one is named, with a square courtyard `courtyard` mm to a side when that is given and a surface-mount
    pad beside the hole, which makes the footprint a part and not a mounting hole, when `surface_pad` is, and KiCad's
    exclude_from_bom attribute when `excluded` is."""
    Q = sexpr.Quoted
    layers = ["layers", Q("*.Cu"), Q("*.Mask")]
    if plated_net is None:
        hole = ["pad", Q(""), "np_thru_hole", "circle", ["at", "0", "0"], ["size", f"{pad:g}", f"{pad:g}"], ["drill", "3.2"], layers,
                ["uuid", Q(f"{uuid[:-2]}01")]]
    else:
        hole = ["pad", Q("1"), "thru_hole", "circle", ["at", "0", "0"], ["size", "4", "4"], ["drill", "3.2"], layers,
                ["net", Q(plated_net)], ["uuid", Q(f"{uuid[:-2]}01")]]
    body = [hole]
    if surface_pad:
        body.append(["pad", Q("2"), "smd", "rect", ["at", "0", "6"], ["size", "1", "1"],
                     ["layers", Q("F.Cu"), Q("F.Mask")], ["uuid", Q(f"{uuid[:-2]}03")]])
    if courtyard:
        half = f"{courtyard / 2:g}"
        body.append(["fp_rect", ["start", f"-{half}", f"-{half}"], ["end", half, half], ["stroke", ["width", "0.05"], ["type", "solid"]],
                     ["fill", "none"], ["layer", Q("F.CrtYd")], ["uuid", Q(f"{uuid[:-2]}02")]])
    if excluded:
        body.append(["attr", "exclude_from_pos_files", "exclude_from_bom"])
    return ["footprint", Q("proof:Seeded_Hole"), ["layer", Q("F.Cu")], ["uuid", Q(uuid)], ["at", f"{x:g}", f"{y:g}"],
            ["property", Q("Reference"), Q(reference), ["at", "0", "-3", "0"], ["layer", Q("F.SilkS")]], *body]


#: R1 pad 2, on /MAINS_N, is a 1.6 mm round pad at (25.16, 10), its edge at 25.96. A non-plated 3.2 mm hole whose edge is
#: 2.5 mm from it, and a plated hole whose 4 mm pad stands 3.5 mm from it (clear of the signed 3 mm clearance, so only
#: its hole, 0.4 mm inside the pad, is nearer than the 4 mm that is the larger of the signed clearance and creepage).
HOLE_X = 25.96 + 2.5 + 1.6
PLATED_X = 25.96 + 3.5 + 2.0

#: A hole 7.4 mm from R1's pad, so only its 10 mm courtyard, whose left edge stands at x = 30, is inside the signed distance
#: of Mains copper that is not a pad: a track 2.9 mm off that edge, or a pour's fill 2 mm off it.
FIXING_X = 35
FIXING_UUID = "0b0e5c1a-0000-4000-8000-000000000c00"


def fixing_near_mains_track(seed: Seed) -> None:
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, seeded_hole("H9", FIXING_X, 10, FIXING_UUID, courtyard=10)),
                              tree.insert(len(tree) - 1, segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))


def fixing_near_mains_pour(seed: Seed) -> None:
    """The same fixing with, in place of the track, a /MAINS_N pour on the back copper whose fill ends 2 mm off its courtyard."""
    Q = sexpr.Quoted
    zone = ["zone", ["net", Q("/MAINS_N")], ["layer", Q("B.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000c20")],
            ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", "24", "4"], ["xy", "28", "4"], ["xy", "28", "16"], ["xy", "24", "16"]]]]
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, seeded_hole("H9", FIXING_X, 10, FIXING_UUID, courtyard=10)),
                              tree.insert(len(tree) - 1, zone)))


#: A hole whose own edge is 4.2 mm from R1's pad, clear of the 4 mm, drilled through a 6 mm pad whose edge is 2.8 mm from it.
OVERSIZE_X = 25.96 + 4.2 + 1.6


def hole_with_oversize_pad(seed: Seed) -> None:
    """A part with a 6 mm non-plated pad round a 3.2 mm hole, and a surface-mount pad, so it is held by KiCad's rule alone."""
    seed.layout(lambda tree: tree.insert(len(tree) - 1, seeded_hole(
        "H9", OVERSIZE_X, 10, FIXING_UUID, pad=6, surface_pad=True)))


def hole_near_mains(plated_net: Optional[str] = None):
    def seed_it(seed: Seed) -> None:
        seed.layout(lambda tree: tree.insert(len(tree) - 1, seeded_hole(
            "H9", HOLE_X if plated_net is None else PLATED_X, 10, FIXING_UUID, plated_net)))
    return seed_it


#: J2 pad 1, on Power-class /+5V, is a 1.7 mm by 2 mm pad at (37, 3.5), the Power copper nearest a free corner of the board. A
#: Sensing-class /AMP_OUT track 0.3 mm from its edge keeps the Sensing net class's own 0.2 mm clearance and stands inside the
#: 0.5 mm the board rules record declares.
SENSED_X = 37 - 0.85 - 0.3 - 0.125
SENSED_UUID = "0b0e5c1a-0000-4000-8000-000000001001"


def sensing_item_near_power(seed: Seed) -> None:
    seed.layout(lambda tree: tree.insert(len(tree) - 1, segment("/AMP_OUT", SENSED_X, 2.5, SENSED_X, 4.5, SENSED_UUID)))


def declared_above_mains(seed: Seed) -> None:
    """The record declares 40 mm, above the signed 3 mm and above the 34 mm the nearest Sensing copper stands from Mains copper."""
    seed.replace("board-rules.yaml", "clearance_mm: 0.5", "clearance_mm: 40")


def override_on(target: Callable[[list], list]):
    def seed_it(seed: Seed) -> None:
        def edit(tree: list) -> None:
            item = target(tree)
            item.insert(len(item) - 1, ["clearance", "0.1"])
        seed.layout(edit)
    return seed_it


CONNECTOR_UUID = "0b0e5c1a-0000-4000-8000-000000001100"


def connector(*nets: str, record: Optional[Callable[["Seed"], None]] = None):
    """A connector J9 with a pin for each net given, in a free corner of the board, and an edit to the record if one is given."""
    thru = ("thru_hole", ["*.Cu", "*.Mask"])

    def seed_it(seed: Seed) -> None:
        pads = [(str(index + 1), *thru, net, 2.54 * index, 0, 1.6) for index, net in enumerate(nets)]
        seed.layout(lambda tree: tree.insert(len(tree) - 1, small_part("J9", 12, 50, CONNECTOR_UUID, *pads)))
        if record is not None:
            record(seed)
    return seed_it


#: The record's non-signal classes and its signal classes, as the committed record writes them.
NON_SIGNAL = "  non_signal_classes:\n    - Mains\n    - Power\n    - Supply\n  signal_classes:\n"
SOURCE = "source: none -- synthetic figure chosen to exercise the check, not read from a guideline\n"


def supply_a_signal(seed: Seed) -> None:
    """Supply is a signal class held to one signal pin per return, and Sensing to three."""
    seed.replace("board-rules.yaml", NON_SIGNAL, "  non_signal_classes:\n    - Mains\n    - Power\n  signal_classes:\n"
                 "    - class: Supply\n      signal_pins_per_return: 1\n      " + SOURCE)
    seed.replace("board-rules.yaml", "signal_pins_per_return: 1\n      " + SOURCE + "synthetic",
                 "signal_pins_per_return: 3\n      " + SOURCE + "synthetic")


SIGNED = f"rule '{board_check.SIGNED_RULE}' clearance"
CONDITION = board_check.MAINS_CONDITION

#: (fault, the check it proves, the rule the check must report, text that line must carry, the edit), and, for a
#: fault seeded into a design other than DESIGN, that design's folder and name as a sixth element and, as a seventh,
#: text no violation line of the run may carry, for a fault seeded beside something the check must leave alone.
FAULTS: List[tuple] = [
    # Discovery
    ("an empty tree", "discovery: finding nothing fails", "design_discovery", "no board design was found", empty_tree),
    ("a layout that cannot be opened", "discovery: an unreadable design fails by name", "design_unreadable", "layout cannot be checked", truncate(".kicad_pcb")),
    ("a schematic that cannot be opened", "discovery: an unreadable design fails by name", "design_unreadable", "schematic", truncate(".kicad_sch")),
    ("a project file that cannot be read", "discovery: an unreadable design fails by name", "design_unreadable", "project file cannot be read", lambda seed: seed.write(".kicad_pro", "{ not json")),
    ("a project missing its schematic", "discovery: a project needs both its schematic and layout", "design_discovery", "no schematic beside it", remove(".kicad_sch")),
    ("a project missing its layout", "discovery: a project needs both its schematic and layout", "design_discovery", "no layout beside it", remove(".kicad_pcb")),
    ("a layout committed without its project", "discovery: no board file escapes the check", "design_discovery", "a layout is tracked without", stray(".kicad_pcb")),
    ("a schematic committed without its project", "discovery: no board file escapes the check", "design_discovery", "a schematic is tracked without", stray(".kicad_sch")),
    ("a sheet left out of the commit of the schematic naming it", "discovery: no half-committed board escapes the check", "design_discovery", "names the sheet hardware/proof/gate-proof/sub.kicad_sch, which is not tracked", untracked_sheet),
    ("a library the design's table names that git does not track", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "library 'proof' is at ${KIPRJMOD}/proof.pretty, which is hardware/proof/gate-proof/proof.pretty in the repository, and git tracks nothing there", untracked_library),
    ("a library table git does not track", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "library table is not tracked in the repository", untrack("fp-lib-table")),
    ("a library named outside the repository", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "it lies outside the repository", library_uri("${KIPRJMOD}/../../../../proof.pretty")),
    ("a library named by an absolute path", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "named by an absolute path", library_uri("/opt/kicad-libs/proof.pretty")),
    ("a library reached through one machine's own path variable", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "reached through ${PROOF_LIBS}", library_uri("${PROOF_LIBS}/proof.pretty")),
    ("a library table entry holding a clause KiCad does not write", "discovery: a library table is read only in the form KiCad writes", "design_library", "a (priority ...) clause, which is not one KiCad writes", table_entry('(descr "Footprints', '(priority 1)(descr "Footprints')),
    ("a library table giving one nickname twice", "discovery: a library table is read only in the form KiCad writes", "design_library", "the nickname 'proof', which an earlier entry already takes", table_entry("\n)", '\n\t(lib (name "proof")(type "KiCad")(uri "${KIPRJMOD}/other.pretty")(options "")(descr ""))\n)')),
    ("a library of a format other than KiCad's own", "discovery: a library table is read only in the form KiCad writes", "design_library", "the type 'Legacy'", table_entry('(type "KiCad")', '(type "Legacy")')),
    ("a library table headed for the other kind of library", "discovery: a library table is read only in the form KiCad writes", "design_library", "headed (sym_lib_table ...), not (fp_lib_table ...)", table_entry("(fp_lib_table", "(sym_lib_table")),
    ("a footprint library no table the design carries names", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "does not include the footprint library 'proof'", empty_table("fp")),
    ("a symbol library no table the design carries names", "discovery: a design is checked with what it reaches, or fails naming what it cannot", "design_library", "does not include the symbol library 'proof'", empty_table("sym")),
    ("a footprint library named only by the KiCad tables of the machine running the check", "discovery: the check needs nothing from the machine it runs on", "design_library", "does not include the footprint library 'proof'", machine_table_library),
    ("a sheet naming its file twice", "discovery: no half-committed board escapes the check", "design_discovery", "has 2 Sheetfile properties", twice_named_sheet),
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
    ("a rules file KiCad declines to load", "rule checks: the design's rules are read as written, and the rule KiCad rejects is named", "custom_rules", "gate-proof.kicad_dru rule 'typo' at line 18",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + "(rule \"typo\"\n\t(condition \"A.Type == 'Pad'\")\n\t(constraint clearence (min 1mm)))\n")),
    ("a rules file that is not well-formed", "rule checks: the design's rules are read as written, and why no one rule can be named is said", "custom_rules", "gate-proof.kicad_dru at its end | KiCad did not load the design's custom rules",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + "(rule \"open\"\n\t(condition \"A.Type == 'Pad'\")\n")),
    ("a rules file without its version header", "rule checks: the design's rules are read as written, and what KiCad rejects is named", "custom_rules", "does not begin with a (version 1) header",
     mains_rule("(version 1)\n", "")),
    ("an untracked custom rules file", "rule checks: the design's rules are read as the repository holds them", "custom_rules", "custom rules file is not tracked", untrack(".kicad_dru")),
    ("a design rule taking a name reserved for the check's own rules", "rule checks: nothing the design writes passes for the check's own rules", "custom_rules", "reserved for the rules the check adds", forged_rule),
    ("a rule holding two conditions, of which KiCad keeps one", "rule checks: the design's rules are read only in a form KiCad reads the same way", "custom_rules", "rule 'Mains separation' | the rule holds 2 (condition ...) clauses", second_condition),
    ("two rules sharing one name", "rule checks: the design's rules are read only in a form KiCad reads the same way", "custom_rules", "2 rules are named 'Mains separation'", rule("Mains separation", "A.Type == 'Via'")),
    ("a project file giving one key twice", "rule checks: the project file is read only in the form KiCad writes", "project_file", "gives the key 'MAINS' more than once", project_text('"MAINS": "present"', '"MAINS": "none", "MAINS": "present"')),
    ("a project file whose exclusions are not a list", "rule checks: the project file is read only in the form KiCad writes", "project_file", "drc_exclusions is", lambda seed: seed.project(lambda data: data["board"]["design_settings"].update(drc_exclusions={"clearance": "tolerated"}))),
    ("a project file whose net class assignments are not an object", "rule checks: the project file is read only in the form KiCad writes", "project_file", "netclass_assignments is", lambda seed: seed.project(lambda data: data["net_settings"].update(netclass_assignments=["/LV_A"]))),
    ("a project text variable that is not a string", "rule checks: the project file is read only in the form KiCad writes", "project_file", "text variable MAINS is true", lambda seed: seed.project(lambda data: data["text_variables"].update(MAINS=True))),
    ("a stale fill hiding a creepage violation beside a mains pad", "rule checks: zones are refilled before they are judged", "creepage", f"rule '{board_check.SIGNED_RULE}' creepage", unfilled_pour_by_mains),
    # Workmanship
    ("a right-angled corner", "workmanship: KiCad measures each corner against the rules file's corner rule", "track_angle", "workmanship item WORK-4",
     reroute("/LV_B", (LV_B_RUN, LV_B_BEND), [(40, 12.54), (55.16, 12.54), (55.16, 10)])),
    ("a corner a few degrees off 45", "workmanship: KiCad measures each corner against the rules file's corner rule", "track_angle", "actual 132.6",
     reroute("/LV_B", (LV_B_RUN, LV_B_BEND), [(40, 12.54), (52.82, 12.54), (55.16, 10)])),
    ("a short jog", "workmanship: KiCad measures each straight run against the rules file's jog rule", "track_segment_length", "workmanship item WORK-5",
     reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (42, 10), (42.3, 10.3), (45, 10.3)])),
    ("an unneeded via", "workmanship: KiCad reports a via a route does not need, unaided", "via_dangling", "workmanship item WORK-7", unneeded_via),
    ("a route turning at 45 degrees through a pad", "workmanship: two tracks meeting at a pad are measured against the corner rule's figure", "workmanship_pad_corner",
     "/LV_A turns through pad 1 of R2 on F.Cu, and two tracks leave it 45.00 degrees apart, where the corner rule's track_angle allows no less than 135 degrees",
     lambda seed: seed.layout(lambda tree: [tree.insert(len(tree) - 1, segment("/LV_A", *a, *b, f"0b0e5c1a-0000-4000-8000-00000000040{index}"))
                                            for index, (a, b) in enumerate((((40, 10), (41, 9)), ((41, 9), (44, 9)), ((44, 9), (45, 10))))])),
    ("a branch leaving a pad at 45 degrees", "workmanship: tracks branching at a pad are measured against their figure", "workmanship_pad_corner",
     "/LV_A branches at pad 1 of R2 on F.Cu, 3 of its tracks leaving it, and two tracks leave it 45.00 degrees apart, where WORK_PAD_ANGLE_DEG allows no less than 90 degrees",
     lambda seed: seed.layout(lambda tree: [tree.insert(len(tree) - 1, segment("/LV_A", *a, *b, f"0b0e5c1a-0000-4000-8000-00000000041{index}"))
                                            for index, (a, b) in enumerate((((40, 10), (41, 9)), ((41, 9), (44, 9)), ((44, 9), (45, 10)),
                                                                            ((40, 10), (41, 11)), ((41, 11), (44, 11)), ((44, 11), (45, 10))))])),
    ("a short stub", "workmanship: KiCad reports a track ending free, unaided", "track_dangling", "workmanship item WORK-6", stub),
    ("a route wandering the long way round", "workmanship: a net's track length is measured against the tree joining its pads", "workmanship_detour", "where WORK_DETOUR_RATIO allows 1.3 times",
     reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (40, 6), (41, 5), (44, 5), (45, 6), (45, 10)])),
    ("a route wandering the long way round to a pad its net's pour covers", "workmanship: a zone never exempts a net's tracks from the route-length rule",
     "workmanship_detour", "where WORK_DETOUR_RATIO allows 1.3 times",
     lambda seed: (reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (40, 6), (41, 5), (44, 5), (45, 6), (45, 10)])(seed), token_zone(seed))),
    ("a route wandering the long way round to end in its net's pour short of its pad", "workmanship: a net's track length is measured against the tree joining all its pads",
     "workmanship_detour", "/LV_A's tracks are 11.33 mm long, 2.27 times the 5.00 mm", pour_short_of_pad),
    ("a track off the board's edges and the 45 degrees to them", "workmanship: each track's direction is measured against the board's edges", "workmanship_direction", "3.43 degrees off",
     reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (45, 10.3)])),
    ("flat arcs drawn at an odd angle", "workmanship: an arc's direction is measured at its ends against the board's edges", "workmanship_direction",
     "the arc runs 12.00 degrees off the nearest of those directions at its end at", flat_arcs),
    ("a track off a rectangle outline's sides beside a cutout turned to it", "workmanship: the board's edges are read at their true shape",
     "workmanship_direction", "track [/LV_A] on F.Cu from (40, 10) to (45, 10.3) mm", rectangle_outline),
    ("a track entering a long pad from its side", "workmanship: the way a track enters a long pad is measured against the pad's axis", "workmanship_pad_entry", "enters it 90.00 degrees off its long axis", long_pad),
    ("a track ending just short of a long pad's side", "workmanship: a track meets a pad where its end's copper reaches the pad's, as KiCad joins them",
     "workmanship_pad_entry", "enters it 90.00 degrees off its long axis",
     lambda seed: (long_pad(seed), reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (44.1, 10)])(seed))),
    ("a track running across a long pad from side to side", "workmanship: the way a track crosses a long pad is measured against the pad's axis", "workmanship_pad_entry", "runs across it 90.00 degrees off its long axis",
     lambda seed: (long_pad(seed), reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (46.5, 10)])(seed))),
    ("a pad whose copper the check cannot size", "workmanship: a pad a track of its net meets is sized from the board file or named",
     "workmanship_pad_copper", "cannot be measured at pad 1 of R2: its shape is custom", custom_pad),
    ("a route narrowed partway along", "workmanship: a track narrower than its class is measured against its figure", "workmanship_width", "0.15 mm wide, narrower than its net class's 0.25 mm",
     reroute("/LV_B", (LV_B_RUN,), [(40, 12.54), (46, 12.54), (52.62, 12.54)], (0.25, 0.15))),
    ("a rules file without the corner rule", "workmanship: the rules file holds every workmanship rule", "workmanship_rule", "WORK-4 (corner) has no rule", drop_rule("Corners")),
    ("a jog rule narrowed to some tracks", "workmanship: the rules file's workmanship rules hold on every track", "workmanship_rule", "WORK-5 (jog) is not in force on every track",
     mains_rule('(rule "Jogs"', '(rule "Jogs"\n\t(condition "A.hasNetclass(\'Mains\')")')),
    ("a later corner rule looser on some tracks", "workmanship: no rule in the rules file loosens a workmanship rule's figure", "workmanship_rule",
     "WORK-4 (corner) is loosened: rule 'Mains corners' at line",
     lambda seed: seed.write(".kicad_dru", seed.read(".kicad_dru") + '(rule "Mains corners"\n\t(condition "A.hasNetclass(\'Mains\')")\n'
                             "\t(constraint track_angle (min 90)))\n")),
    ("a corner rule written with a unit KiCad does not take", "workmanship: a rules file KiCad drops for a unit is named", "custom_rules", "rule 'Corners'",
     mains_rule("(min 135)", "(min 135deg)")),
    ("a measured rule with no figure", "workmanship: each measured rule's figure is set", "workmanship_figure", "WORK-2 (route length) has no figure",
     variables(lambda v: v.pop("WORK_DETOUR_RATIO"))),
    ("a measured rule's figure written with a unit", "workmanship: each measured rule's figure is a plain number", "workmanship_figure", "WORK_NECK_MM is '1mm'",
     variables(lambda v: v.update(WORK_NECK_MM="1mm"))),
    ("a measured rule's figure out of its range", "workmanship: each measured rule's figure is within its range", "workmanship_figure", "WORK_DETOUR_RATIO is '0.5'",
     variables(lambda v: v.update(WORK_DETOUR_RATIO="0.5"))),
    ("a project file whose net classes are not a list", "rule checks: the project file is read only in the form KiCad writes", "project_file", "net_settings.classes is",
     lambda seed: seed.project(lambda data: data["net_settings"].update(classes={"Default": {}}))),
    ("a net class whose track width is not a number", "workmanship: each net class's width is read", "project_file", "the net class Default gives no track width",
     lambda seed: seed.project(lambda data: data["net_settings"]["classes"][0].update(track_width="wide"))),
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
    ("a Mains rule whose class name is spelt with a space", "separation: the Mains rule is read only in its exact form", "separation_rule", "narrowed by its condition or not in the required form", mains_rule("A.hasNetclass('Mains') &&", "A.hasNetclass('Ma ins') &&")),
    ("a Mains rule holding a constraint the check does not read", "separation: the Mains rule is read only in its exact form", "separation_rule", "holds a (constraint hole_clearance ...) constraint", mains_constraint("(constraint hole_clearance (min 1mm))")),
    ("a Mains rule stating its clearance twice", "separation: the Mains rule is read only in its exact form", "separation_rule", "holds 2 clearance constraints", mains_constraint("(constraint clearance (min 0.1mm))")),
    ("a Mains rule figure written in other units", "separation: the Mains rule is read only in its exact form", "separation_rule", "where the check reads only (constraint clearance (min <number>mm))", mains_rule("(min 3mm)", "(min 118.2mil)")),
    ("a Mains rule figure with a further limit", "separation: the Mains rule is read only in its exact form", "separation_rule", "where the check reads only (constraint creepage (min <number>mm))", mains_rule("(min 4mm)", "(min 4mm) (opt 5mm)")),
    ("a net tie joining a Mains-class net to a low-voltage net", "separation: nothing exempts mains copper from the separation check", "mains_net_tie", "net tie R1 joins Mains-class /MAINS_N to /LV_A", net_tie("2, 3", True)),
    ("a net tie naming a pad its footprint does not have", "separation: nothing exempts mains copper from the separation check", "mains_net_tie", "names pad 9, which the footprint does not have", net_tie("1, 9", False)),
    ("a mains-carrying design with no Mains rule", "separation: a mains-carrying design declares its basis", "separation_rule", "no custom rule has the condition", lambda seed: seed.write(".kicad_dru", "(version 1)\n")),
    ("a mains-carrying design with no rules file", "separation: a mains-carrying design declares its basis", "separation_rule", "no custom rules file", remove(".kicad_dru")),
    ("a design silent on whether it carries mains", "separation: MAINS is declared", "mains_declaration", "MAINS is not set", variables(lambda v: v.pop("MAINS"))),
    ("a design declaring an invalid MAINS value", "separation: MAINS is declared", "mains_declaration", "MAINS is 'yes'", variables(lambda v: v.update(MAINS="yes"))),
    ("a design declaring no mains while carrying a Mains-class net", "separation: MAINS agrees with the Mains class", "mains_declaration", "MAINS is none but", variables(lambda v: v.update(MAINS="none"))),
    ("a design declaring no mains while the project file assigns a net with no copper to Mains", "separation: MAINS agrees with the Mains class wherever it is declared", "mains_class", "net /UNROUTED is in the Mains net class in the project file's net settings but not on the layout or in the schematic", no_mains_but_assigned),
    ("a design declaring no mains while its schematic puts a net in Mains", "separation: MAINS agrees with the Mains class wherever it is declared", "mains_class", "net /LV_B is in the Mains net class in the schematic but not on the layout or in the project file's net settings; the layout's", no_mains_but_schematic_class),
    ("a design declaring mains with no net in the Mains class", "separation: MAINS agrees with the Mains class", "mains_declaration", "no net on the layout is in the Mains net class",
     lambda seed: seed.project(no_mains_patterns)),
    ("a design declaring mains whose schematic alone puts a net in Mains", "separation: the layout, schematic and project file name the same Mains nets", "mains_class", "net /LV_B is in the Mains net class in the schematic but not on the layout or in the project file's net settings", schematic_only_mains),
    ("a design declaring mains whose project file alone puts a net in Mains", "separation: the layout, schematic and project file name the same Mains nets", "mains_class", "net /UNROUTED is in the Mains net class in the project file's net settings but not on the layout or in the schematic", project_only_mains),
    ("a design declaring mains whose layout alone puts a net in Mains", "separation: the layout, schematic and project file name the same Mains nets", "mains_class", "net /LV_A is in the Mains net class on the layout but not in the schematic or in the project file's net settings", layout_only_mains),
    ("a design whose schematic puts one net more in Mains than its layout and project file", "separation: the layout, schematic and project file name the same Mains nets", "mains_class", "net /LV_B is in the Mains net class in the schematic but not on the layout or in the project file's net settings", mains_flag_on_lv_b),
    ("a design whose project file and layout put one net more in Mains than its schematic", "separation: the layout, schematic and project file name the same Mains nets", "mains_class", "net /LV_A is in the Mains net class on the layout and in the project file's net settings but not in the schematic", project_and_layout_not_schematic),
    ("a missing basis record", "separation: the basis record exists", "separation_basis", "no separation-basis.yaml", remove("separation-basis.yaml")),
    ("a basis record that is not tracked", "separation: the basis record is the committed one", "separation_basis", "record is not tracked in the repository", untrack("separation-basis.yaml")),
    ("a basis record with uncommitted changes", "separation: the basis record is the committed one", "separation_basis", "record has changes that are not committed", uncommitted_record),
    ("a basis record holding a key it does not have", "separation: the basis record is read only in its one form", "separation_basis", "holds the key 'acceptd_by'", record("accepted_by: david\n", "accepted_by: david\nacceptd_by: someone-else\n")),
    ("a basis record giving one key twice", "separation: the basis record is read only in its one form", "separation_basis", "gives the key 'clearance_mm' more than once", record("  clearance_mm: 3.0\n", "  clearance_mm: 1.0\n  clearance_mm: 3.0\n")),
    ("a basis record using a merge key", "separation: the basis record is read only in its one form", "separation_basis", "merge key", record("mains_to_low_voltage:\n", "defaults: &figures\n  clearance_mm: 3.0\n  creepage_mm: 4.0\nmains_to_low_voltage:\n  <<: *figures\n")),
    ("a basis record whose figure pair holds a key it does not have", "separation: the basis record is read only in its one form", "separation_basis", "mains_to_low_voltage holds 'clearance_mm_rms'", record("  creepage_mm: 4.0\n", "  creepage_mm: 4.0\n  clearance_mm_rms: 1.0\n")),
    ("a basis record whose synthetic mark is not true or false", "separation: the basis record is read only in its one form", "separation_basis", "synthetic is 'yes'", record("synthetic: true", "synthetic: 'yes'")),
    ("a basis record that cannot be parsed", "separation: the basis record is readable", "separation_basis", "cannot be parsed", record("mains_to_low_voltage:\n", "mains_to_low_voltage: [unclosed\n")),
    ("a basis record lacking a figure", "separation: the basis record states both figures", "separation_basis", "lacks mains_to_low_voltage.creepage_mm", record("  creepage_mm: 4.0\n", "")),
    ("a basis record with a figure that is not a positive number", "separation: the basis record states both figures", "separation_basis", "not a positive number", record("clearance_mm: 3.0", "clearance_mm: 0")),
    ("a basis record with no acceptor", "separation: the basis record is signed", "separation_basis", "accepted_by is missing", record("accepted_by: david\n", "")),
    ("a basis record whose acceptor is a placeholder", "separation: the basis record is signed", "separation_basis", "is a placeholder", record("accepted_by: david", "accepted_by: TBD")),
    ("a basis record with no acceptance date", "separation: the basis record is signed", "separation_basis", "accepted_on, the date", record("accepted_on: 2026-10-12\n", "")),
    ("a basis record with an invalid acceptance date", "separation: the basis record is signed", "separation_basis", "not a valid calendar date", record("accepted_on: 2026-10-12", "accepted_on: '12/10/2026'")),
    ("a basis record accepted on a future date", "separation: the basis record is signed", "separation_basis", "later than today", record("accepted_on: 2026-10-12", "accepted_on: 2999-01-01")),
    ("a synthetic basis record applied to a design not marked not for manufacture", "separation: a synthetic record cannot pass an orderable board", "separation_basis", "marked synthetic", variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    # Names
    ("a net KiCad named on a sub-sheet, beside pins nothing joins", "names: a net the tool generated fails, and a pin nothing joins is exempt", "tool_named_net", "Net-(", generated_net_on_subsheet, (DESIGN, NAME), "unconnected-("),
    ("a sheet with a blank name", "names: a sheet with no name of its own fails", "unnamed_sheet", "its name is blank", sheet_named("")),
    ("a sheet with the tool's default name", "names: a sheet with no name of its own fails", "unnamed_sheet", "is 'Untitled Sheet'", sheet_named("Untitled Sheet")),
    ("a second sheet with the tool's default name, numbered", "names: a sheet with no name of its own fails", "unnamed_sheet", "is 'Untitled Sheet 1'", sheet_named("Untitled Sheet 1")),
    # Separation floor
    ("a signed clearance below the floor the table rows give", "separation floor: a signed clearance below its floor fails", "separation_floor",
     "the signed clearance_mm is 3 mm, below the 3.5 mm floor", record("      clearance_mm: 3.0", "      clearance_mm: 3.5")),
    ("a signed creepage below the floor the table rows give", "separation floor: a signed creepage below its floor fails", "separation_floor",
     "the signed creepage_mm is 4 mm, below the 4.5 mm floor", record("      creepage_mm: 4.0", "      creepage_mm: 4.5")),
    ("a mains-present basis with no applicable table row", "separation floor: no applicable row for a figure fails", "separation_floor",
     "no table row of the record gives a clearance_mm that applies", record("working_voltage: 250 V rms", "working_voltage: 300 V rms")),
    ("a mains-present basis lacking a required key", "separation floor: a basis lacking a required key fails by key", "separation_floor",
     "the record lacks altitude_m", record("altitude_m: 2000\nbarriers", "barriers")),
    # Mounting holes
    ("a mounting hole inside the signed distance of a Mains net", "mounting holes: a hole inside the larger of the signed clearance and creepage of Mains fails", "mounting_hole",
     "a non-plated hole or its pad stands", hole_near_mains()),
    ("a plated hole on a non-Mains net inside the signed distance of a Mains net", "mounting holes: a plated hole on a non-Mains net inside that distance fails", "mounting_hole",
     "a plated hole on a net outside Mains stands", hole_near_mains("/LV_A")),
    ("a Mains track inside the signed distance of a fixing's courtyard", "mounting holes: a fixing's extent inside that distance of Mains copper fails", "mounting_hole",
     "of the mounting hole H9 stands", fixing_near_mains_track),
    ("a Mains pour inside the signed distance of a fixing's courtyard", "mounting holes: a fixing's extent inside that distance of Mains copper fails", "mounting_hole",
     "of Mains-class net /MAINS_N on B.Cu", fixing_near_mains_pour),
    ("a part's oversize non-plated pad inside the signed distance of a Mains net with its hole clear", "mounting holes: a non-plated pad larger than its hole is held at its pad edge", "mounting_hole",
     "a non-plated hole or its pad stands", hole_with_oversize_pad),
    # Connectivity
    ("a channel's net moved to the other controller pin", "connectivity: a net must reach the controller pin its channel names", "connectivity", "net /LV_A reaches controller pin PA1, where the record names controller pin PA0", swap_labels(("LV_A", "96.52 76.2"), ("LV_B", "96.52 78.74"))),
    ("a channel's net moved to the other pin of its connector", "connectivity: a net must reach the connector pin its channel names", "connectivity", "net /LV_A reaches connector pin J2 pin 2, where the record names connector pin J2 pin 1", swap_labels(("LV_A", "45.72 76.2"), ("LV_B", "45.72 78.74"))),
    ("a channel on the wrong connector", "connectivity: a net must reach the connector its channel names", "connectivity", "net /LV_A reaches connector pin J3 pin 1, where the record names connector pin J2 pin 1", rename_reference("J2", "J3")),
    ("a listed channel removed from the design", "connectivity: a channel the record lists must be in the design", "connectivity", "the record lists net LV_B, which the design does not have", drop_net_labels("LV_B")),
    ("a channel on pins the record omits", "connectivity: a net on a pin the record omits fails", "connectivity", "which the record does not list", pin_record("  - channel: lv_b\n    net: LV_B\n    controller_pin: PA1\n    connector: J2\n    connector_pin: 2\n", "")),
    ("a pin allocation record that does not exist", "pin allocation: a design with no record fails", "pin_allocation", "there is no pin-allocation.yaml", remove("pin-allocation.yaml")),
    ("a pin allocation record that cannot be parsed", "pin allocation: the record is readable", "pin_allocation", "cannot be parsed", pin_record("channels:\n", "channels: [unclosed\n")),
    ("a pin allocation record giving a key twice", "pin allocation: the record is read only in its one form", "pin_allocation", "gives the key 'net' more than once", pin_record("    net: LV_A\n", "    net: LV_A\n    net: LV_B\n")),
    ("a pin allocation record lacking the channels", "pin allocation: a record without channels fails", "pin_allocation", "the record lacks channels", pin_record("channels:\n", "chanels:\n")),
    ("a pin allocation record listing no channel", "pin allocation: an empty record cannot pass a design", "pin_allocation", "lists no channel", lambda seed: seed.write("pin-allocation.yaml", "synthetic: true\nchannels: []\n")),
    ("a pin allocation entry lacking its controller pin", "pin allocation: a record missing a required key fails", "pin_allocation", "the entry lacks controller_pin", pin_record("    controller_pin: PA0\n", "")),
    ("a pin allocation entry naming a connector without its pin", "pin allocation: a record missing a required key fails", "pin_allocation", "gives only one of connector and connector_pin", pin_record("    connector_pin: 1\n", "")),
    ("a synthetic pin allocation record applied to a design not marked not for manufacture", "pin allocation: a synthetic record cannot pass an orderable board", "pin_allocation", "marked synthetic", variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    # Controller part
    ("a controller whose catalogue number differs from the controller part record", "controller part: a controller other than the selected part fails", "controller_part", "the controller U1 has the catalogue number C9000005, where the controller part record names C9000099",
     lambda seed: seed.replace("controller-part.yaml", 'lcsc: "C9000005"', 'lcsc: "C9000099"')),
    ("a controller with no LCSC field", "controller part: a controller whose catalogue number is absent fails", "controller_part", "the controller U1 has no LCSC field", drop_field("U1", "LCSC")),
    ("a pin allocation entry naming a pin the controller part record omits", "controller part: a channel on a pin the selected part does not have fails", "controller_part", "channel lv_b names controller pin PA1, which the selected SYNTHETIC-CTRL does not have",
     lambda seed: seed.replace("controller-part.yaml", "  - PA1\n", "")),
    ("a controller part record that does not exist", "controller part: a design placing a controller with no record fails", "controller_record", "there is no controller-part.yaml", remove("controller-part.yaml")),
    ("a controller part record that cannot be parsed", "controller part: the record is readable", "controller_record", "cannot be parsed", lambda seed: seed.replace("controller-part.yaml", "pins:\n", "pins: [unclosed\n")),
    ("a controller part record lacking its catalogue number", "controller part: a record missing a required key fails", "controller_record", "lacks lcsc", lambda seed: seed.replace("controller-part.yaml", 'lcsc: "C9000005"\n', "")),
    ("a controller part record holding a key no decision names", "controller part: the record is read only in its one form", "controller_record", "holds the key 'package'", lambda seed: seed.replace("controller-part.yaml", "synthetic: true\n", "synthetic: true\npackage: LQFP144\n")),
    ("a controller part record listing a pin twice", "controller part: a pin is listed once", "controller_record", "lists the pin 'PA0' more than once", lambda seed: seed.replace("controller-part.yaml", "  - PA1\n", "  - PA1\n  - PA0\n")),
    ("a synthetic controller part record applied to a design not marked not for manufacture", "controller part: a synthetic record cannot pass an orderable board", "controller_record", "marked synthetic", variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    ("a controller part record not marked synthetic in the design's own folder", "controller part: a record nearer the design than the machine's cannot stand in for it", "controller_record", "is not marked synthetic and is not in the machine's own folder",
     lambda seed: seed.replace("controller-part.yaml", "synthetic: true\n", "synthetic: false\n")),
    ("a second controller whose catalogue number differs from the controller part record", "controller part: every controller is held to the record", "controller_part", "the controller U1B has the catalogue number C9000077, where the controller part record names C9000005",
     second_controller("U1", "C9000077")),
    # Parts
    ("a part whose value differs from the specification record", "parts: a stated property that differs fails", "parts_part", "R1 value differs: the record states '100k' and the design has '1M'",
     lambda seed: seed.replace(".kicad_sch", '(property "Value" "100k"', '(property "Value" "1M"')),
    ("a part whose package differs from the specification record", "parts: a stated property that differs fails", "parts_part", "J2 package differs",
     parts('    package: "PinHeader_1x02_P2.54mm_Vertical"\n    lcsc: "C9000003"', '    package: "PinHeader_1x03_P2.54mm_Vertical"\n    lcsc: "C9000003"')),
    ("a part whose rating differs from the specification record", "parts: a stated property that differs fails", "parts_part", "R2 rating differs: the record states '1W' and the design has '0.25W'",
     parts('    rating: "0.25W"\n    lcsc: "C9000004"', '    rating: "1W"\n    lcsc: "C9000004"')),
    ("a part whose LCSC number differs from the specification record", "parts: a catalogue number that differs fails", "parts_part", "J1 lcsc differs: the record states 'C9000099' and the design has 'C9000001'",
     parts('lcsc: "C9000001"', 'lcsc: "C9000099"')),
    ("a part with no LCSC field", "parts: a part with no catalogue number fails", "parts_part", "R1 lcsc differs: the record states 'C9000002' and the design has '(absent)'", drop_field("R1", "LCSC")),
    ("a part with no Rating field where the record states one", "parts: a part with no stated rating fails a record that states one", "parts_part", "R1 rating differs: the record states '0.25W' and the design has '(absent)'",
     drop_field("R1", "Rating")),
    ("a placed position the specification record omits", "parts: a position the record does not list fails", "parts_part", "the design places the position J2 and the parts specification record does not list it",
     parts('  - reference: J2\n    value: "LV_IN"\n    package: "PinHeader_1x02_P2.54mm_Vertical"\n    lcsc: "C9000003"\n', "")),
    ("a part whose number is absent from the extract", "parts: a part the extract does not list fails", "parts_catalogue", "R2 lcsc | the position R2 has the catalogue number C9000004, which the catalogue extract does not list",
     extract("  - lcsc: C9000004\n    library_class: basic\n    stock: 1003\n    unit_price: 0.01\n", "")),
    ("a part the extract shows out of stock", "parts: a part with no stock fails", "parts_catalogue", "the position J1 has the catalogue number C9000001, which the catalogue extract shows with no stock",
     extract("    stock: 1000", "    stock: 0")),
    ("an extract past its age limit", "parts: a stale extract fails", "parts_catalogue", "past the 36500 days it allows itself",
     extract("read_on: 2026-10-14", "read_on: 1900-01-01")),
    ("an extract dated later than the day of the check", "parts: a future-dated extract fails", "parts_catalogue", "later than today",
     extract("read_on: 2026-10-14", "read_on: 2999-01-01")),
    ("an extract entry whose stock is not a whole number", "parts: a malformed stock fails", "parts_catalogue", "which is not a whole number of zero or more",
     extract("    stock: 1001", "    stock: -4")),
    ("two symbols carrying one reference", "parts: a reference carried twice fails", "parts_part", "more than one symbol carries the reference R2", repeat_symbol("R2")),
    ("two extract entries carrying one catalogue number", "parts: a catalogue number listed twice fails", "parts_catalogue", "C9000002, which another entry also carries",
     extract("synthetic: true", "  - lcsc: C9000002\n    library_class: basic\n    stock: 5\n    unit_price: 0.01\nsynthetic: true")),
    ("a design with no specification record", "parts: no record to be held to fails", "parts_record", "there is no parts-specification.yaml", remove("parts-specification.yaml")),
    ("a design with no catalogue extract", "parts: no extract to be held to fails", "parts_record", "there is no catalogue-extract.yaml", remove("catalogue-extract.yaml")),
    ("a specification record that cannot be parsed", "parts: an unparseable record fails", "parts_record", "cannot be parsed", parts("positions:\n", "positions: [unclosed\n")),
    ("a specification record lacking a catalogue number", "parts: a record missing a required key fails", "parts_record", "positions[0] lacks lcsc", parts('    lcsc: "C9000001"\n', "")),
    ("a specification record listing nothing", "parts: an empty record fails", "parts_record", "lists no positions",
     lambda seed: seed.write("parts-specification.yaml", "positions: []\nsynthetic: true\n")),
    ("a catalogue extract lacking its age limit", "parts: an extract missing a required key fails", "parts_record", "lacks max_age_days", extract("max_age_days: 36500\n", "")),
    ("a catalogue extract listing nothing", "parts: an empty extract fails", "parts_record", "lists no entries",
     lambda seed: seed.write("catalogue-extract.yaml", "read_on: 2026-10-14\nmax_age_days: 36500\nentries: []\nsynthetic: true\n")),
    ("a synthetic specification record applied to a design not marked not for manufacture", "parts: a synthetic record cannot pass an orderable board", "parts_record", "the parts specification record is marked synthetic",
     variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    ("a synthetic catalogue extract applied to a design not marked not for manufacture", "parts: a synthetic extract cannot pass an orderable board", "parts_record", "the catalogue extract is marked synthetic",
     variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    # Barrier, paste and pours
    ("a barrier rule with no figure", "separation: the barrier rule's figure is set", "workmanship_figure", "MAINS-5 (barrier copper) has no figure",
     variables(lambda v: v.pop("BARRIER_COPPER_MM2"))),
    ("a paste rule with a figure written with a unit", "manufacture: the paste rule's figure is a plain number", "workmanship_figure",
     "PASTE_OVER_VIA_MM2 is '0.1mm2'", variables(lambda v: v.update(PASTE_OVER_VIA_MM2="0.1mm2"))),
    ("a track under a part that joins mains to low voltage", "separation: no copper lies between the pads of a part that bridges the mains barrier", "mains_barrier",
     "X1 joins Mains-class /MAINS_L (pad 1) to /LV_A (pad 2), and a track of net /LV_B on F.Cu lies under it", track_under_bridging_part),
    ("a via drilled through the paste of a pad", "manufacture: solder paste is not printed over a via's hole", "paste_via",
     "solder paste is printed over the hole of the 0.3 mm via at (30, 4) mm", via_under_paste),
    ("a pour stopping short of a track of its own net", "manufacture: a pour leaves no narrow gap to copper of its own net", "pour_gap",
     "stops 0.080 mm short of track from (30, 7.205) to (38, 7.205) mm", track_beside_pour),
    ("a part whose Mains-class and other pads overlap on both axes", "separation: a part with no strip between its pad rows fails by name", "mains_barrier",
     "the boxes of its two groups of pads overlap along both axes, so no strip lies between them", lambda seed: barrier_part(seed, ("/LV_A", "", 0.5, 0.5))),
    ("a part whose only pads off the Mains class have no net", "separation: a part whose bridging cannot be known fails by name", "mains_barrier",
     "its only pads off the Mains class, pad 2, have no net, so whether it bridges the barrier is not known", lambda seed: barrier_part(seed, ("", "", 6, 0))),
    ("a crystal on a board whose rules file has no keep-clear", "clock: a board with a crystal holds the keep-clear rule", "crystal_keepclear",
     "R2 is a crystal, and the rules file holds no rule keeping the parts unrelated", crystal_part),
    ("a crystal keep-clear that exempts every other part", "clock: the keep-clear exempts no more than the parts related to the oscillator", "crystal_keepclear",
     "exempts every other part of the layout from the keep-clear of R2", keep_clear_exempting_all),
    ("a ground class on a board whose rules file has no relief rule", "manufacture: a board with ground pads holds the thermal relief rule", "ground_relief",
     "the rules file holds no rule giving them thermal reliefs", ground_class),
    ("a relief rule exempting a pad that is not an exposed pad", "manufacture: the relief rule exempts only an exposed pad", "ground_relief",
     "exempts R2 pad 2 from the reliefs of net class Ground, but it is not an exposed pad", reliefs_exempting_a_plain_pad),
    ("an integrated circuit with netted pads and no pad typed as a power pin on a design not marked not for manufacture", "layout: an orderable board's integrated circuit has its supply pads typed", "decoupling_pintype",
     "has netted pads and none typed power input or power output", variables(lambda v: v.pop("NOT_FOR_MANUFACTURE"))),
    ("a via between a decoupling capacitor's supply pad and the pin it decouples", "layout: no via sits in a decoupling capacitor's path", "decoupling_via",
     "via at (43, 13) mm of net /LV_A lies in the box from (42.15, 9.15) to (43.85, 16.6) mm about pad 1 of C9 of /LV_A and pad 1 of U1", via_in_decoupling_path),
    ("a reference designator on the fabrication layer", "manufacture: every part's reference is on a silkscreen layer", "reference_off_silkscreen",
     "the reference of R1 is on F.Fab, not F.SilkS", reference_on_fab),
    ("a part with no reference text", "manufacture: every part carries a reference on a silkscreen layer", "reference_off_silkscreen",
     "has no reference text", reference_removed),
    ("a reference designator inside a part's courtyard", "manufacture: every designator stands outside every courtyard, beside its own part", "designator_astray",
     "the text of R1 stands inside the courtyard of R1", reference_in_courtyard),
    ("a test point seeded inside a part's courtyard", "test access: a test pad nearer than its figure to a part's courtyard fails", "test_point_courtyard",
     "the pad of test point TP9 is 0 mm from the F.CrtYd courtyard of R1, where TEST_COURTYARD_MM requires 1 mm", test_point_in_courtyard),
    ("a side with surface-mount parts and two fiducials", "assembly: each side with assembled surface-mount parts carries three fiducials", "side_fiducials",
     "the front side has 1 surface-mount parts and 2 fiducials", fiducials_short),
    ("a polarised part with no mark at its first pin", "assembly: a polarised part marks its first pin on the silkscreen", "polarity_mark",
     "R2 is not marked at pad 1, it draws nothing on F.SilkS", three_nets_unmarked),
    ("a polarised capacitor named only by its symbol with no mark", "assembly: a part a polarised capacitor's symbol names is marked at its first pin", "polarity_mark",
     "R2 is not marked at pad 1, it draws nothing on F.SilkS", capacitor_unmarked),
    ("a plated through-hole polarised part with no mark", "assembly: a plated through-hole part is judged by the mark rule as a surface-mount part is", "polarity_mark",
     "R2 is not marked at pad 1, it draws nothing on F.SilkS", through_hole_unmarked),
    ("a polarity mark on the wrong side of the part", "assembly: the mark is on the silkscreen of the part's own side", "polarity_mark",
     "R2 is not marked at pad 1, it has no graphic on F.SilkS nearer pad 1", mark_on_back),
    ("a symmetric outline on a symmetric pad pattern", "assembly: a drawing the pads' symmetry leaves unchanged marks nothing", "polarity_mark",
     "the silkscreen of R2 looks the same when its pads are turned or reflected onto themselves so that pad 1 moves", symmetric_outline),
    # The keys of the records
    ("a separation basis key misspelt", "record keys: a key the separation basis decision does not define is refused by name", "separation_basis",
     "holds the key 'overvoltage_categry'", record("overvoltage_category: 2", "overvoltage_categry: 2"), KEYS_TARGET),
    ("a barrier entry key misspelt", "record keys: a key inside a separation basis entry that the decision does not define is refused by name", "separation_basis",
     "barrier_types[0] holds the key 'formd_by'", record("    formed_by: the slot", "    formd_by: the slot"), KEYS_TARGET),
    ("a derating policy key misspelt", "record keys: a key the design records decision does not define is refused by name in the derating policy", "derating_record",
     "holds the key 'shre'", derating("share: 0.8", "shre: 0.8"), KEYS_TARGET),
    ("a pin-limit key misspelt", "record keys: a key the design records decision does not define is refused by name in the pin limits", "pin_limits_record",
     "holds the key 'absolute_mx_v'", pin_limits("absolute_max_v: 3.6", "absolute_mx_v: 3.6"), KEYS_TARGET),
    ("a catalogue lifecycle key misspelt", "record keys: a key the design records decision does not define is refused by name in a catalogue entry's lifecycle", "parts_record",
     "holds the key 'stauts'", extract("status: active", "stauts: active"), KEYS_TARGET),
    # The derated-voltage and pin-limit rules
    ("a resistor across the mains pair rated below the policy's share of the mains peak", "derated voltage: a part whose working voltage exceeds the policy's voltage share of its rating fails", "derated_voltage",
     "the position R1 sees a working voltage of 353.553 V", resistor_over_its_rating, KEYS_TARGET),
    ("a position with no class", "derated voltage: every position of the parts specification record carries a class", "derated_voltage",
     "the position J1 has no class", parts('    lcsc: "C9000001"\n    class: none', '    lcsc: "C9000001"'), KEYS_TARGET),
    ("a position naming a class the policy lacks", "derated voltage: a position's class is one the derating policy lists, or none", "derated_voltage",
     "the position J1 names the class 'ghost', which the derating policy does not list", parts('    lcsc: "C9000001"\n    class: none', '    lcsc: "C9000001"\n    class: ghost'), KEYS_TARGET),
    ("a rated position naming the class none", "derated voltage: a position whose record or Rating field states a figure in V, VDC or VAC cannot name the class none", "derated_voltage",
     "the position R1 names the class none and the parts specification record gives '50V 0.25W'", parts('    rating: "0.25W"\n    lcsc: "C9000002"', '    rating: "50V 0.25W"\n    lcsc: "C9000002"'), KEYS_TARGET),
    ("a listed pin the part does not have", "pin limits: a pin the record lists that the placed part's symbol does not have fails", "pin_limit",
     "the pin-limit record lists pin 9 of catalogue number C9000005, which the part U1 does not have", pin_limits("      - pin: 2\n        domain: sense", "      - pin: 9\n        domain: sense"), KEYS_TARGET),
    ("a pin whose net can exceed its absolute maximum", "pin limits: a pin whose net can reach more than its absolute_max_v fails", "pin_limit",
     "U1 pin 1 is on net /LV_A, which can reach 3.3 V, above the pin's absolute_max_v 3", pin_limits("absolute_max_v: 3.6", "absolute_max_v: 3.0"), KEYS_TARGET),
    ("a pin whose net can fall below its absolute minimum", "pin limits: a pin whose net can fall below its absolute_min_v fails", "pin_limit",
     "U1 pin 1 is on net /LV_A, which can fall to 0 V, below the pin's absolute_min_v 0.5", pin_limits("absolute_min_v: -0.3", "absolute_min_v: 0.5"), KEYS_TARGET),
    ("a pin driven from another domain that does not tolerate it", "pin limits: a pin on a net driven from another domain while its own is unpowered fails where it does not tolerate it", "pin_limit",
     "U1 pin 2 of domain logic is on net /LV_B, driven from the domain sense", pin_limits(
         "      - pin: 2\n        domain: sense\n        absolute_max_v: 5.5\n        absolute_min_v: -0.3\n        tolerates_driven_unpowered: true",
         "      - pin: 2\n        domain: logic\n        absolute_max_v: 5.5\n        absolute_min_v: -0.3\n        tolerates_driven_unpowered: false"), KEYS_TARGET),
    ("an integrated circuit the pin-limit record omits", "pin limits: every integrated circuit and semiconductor has an entry in the pin-limit record", "pin_limit",
     "the pin-limit record omits the integrated circuit U1", pin_limits("- lcsc: C9000005", "- lcsc: C9000099"), KEYS_TARGET),
    ("a connected pin of a listed integrated circuit left out of its entry", "pin coverage: a connected pin of a listed semiconductor or integrated circuit that its entry omits fails, naming the part and the pin", "pin_limit",
     "the pin-limit record entry for the integrated circuit U1, catalogue number C9000005, omits U1 pin 1, which is connected on net /LV_A",
     pin_limits('      - pin: PA0\n        domain: logic\n        absolute_max_v: 3.6\n        absolute_min_v: -0.3\n        tolerates_driven_unpowered: false\n', ""),
     KEYS_TARGET, "U1 pin 2"),
    ("a connected pin of a listed integrated circuit left out beside pins on no net", "pin coverage: a connected pin of a listed part that its entry omits fails while the part's pins on no other pin and no rail, which the entry never lists, are not failed", "pin_limit",
     "the pin-limit record entry for the integrated circuit U4, catalogue number C9200032, omits U4 pin 13, which is connected on net /WDI",
     pin_limits('      - pin: "PA17"\n        domain: logic\n        absolute_max_v: 4.1\n        absolute_min_v: -0.3\n        tolerates_driven_unpowered: false\n', ""),
     (REVIEW_DESIGN, REVIEW_NAME), "U4 pin 5"),
    # The sensing-clearance and ground-return rules
    ("a sensing item closer to Power copper than the declared clearance", "sensing clearance: a sensing item closer to a noisy item outside Mains than the declared clearance fails", "sensing_clearance",
     "of the noisy class Power, inside the 0.5 mm that hardware/proof/review-proof/board-rules.yaml declares", sensing_item_near_power, SENSING_TARGET),
    ("a declared sensing clearance above the signed one that Mains copper stands inside", "sensing clearance: a sensing item closer to a Mains item than the declared clearance fails where the declared clearance is above the signed one", "sensing_clearance",
     "of the noisy class Mains, inside the 40 mm that hardware/proof/review-proof/board-rules.yaml declares", declared_above_mains, SENSING_TARGET),
    ("a pad clearance override below the declared sensing clearance", "sensing clearance: a pad on a sensing class net with a local clearance override below the declared clearance fails", "sensing_override",
     "pad 1 of U3 is on the sensing or noisy class net /AMP_OUT and sets a local clearance override of 0.1 mm", override_on(lambda tree: pad(tree, "U3", "1")), SENSING_TARGET),
    ("a footprint clearance override below the declared sensing clearance", "sensing clearance: a footprint with a pad on a noisy class net and a local clearance override below the declared clearance fails", "sensing_override",
     "footprint J4 has a pad on a sensing or noisy class net and sets a local clearance override of 0.1 mm", override_on(lambda tree: footprint(tree, "J4")), SENSING_TARGET),
    ("a board rules record silent on sensing", "sensing clearance: a board rules record that does not state sensing, even as none, fails", "board_rules_record",
     "the record lacks sensing, which every board rules record states", board_rules("sensing:\n  classes:\n    - Sensing\n  noisy_classes:\n    - Mains\n    - Power\n  clearance_mm: 0.5\n  " + SOURCE, ""), SENSING_TARGET),
    ("a board rules record with a misspelt sensing key", "sensing clearance: a key the records decisions do not define is refused by name in the board rules record", "board_rules_record",
     "holds the key 'clearence_mm'", board_rules("  clearance_mm: 0.5", "  clearence_mm: 0.5"), SENSING_TARGET),
    ("a sensing declaration without its source", "sensing clearance: a clearance stated without its source fails", "board_rules_record",
     "sensing lacks source", board_rules("  source: none -- synthetic figure chosen to exercise the check, not read from a guideline\nground_returns:", "ground_returns:"), SENSING_TARGET),
    ("a design with no board rules record for sensing or ground returns", "board rules: a design whose folders hold no board rules record fails", "board_rules_record",
     "there is no board-rules.yaml in the design's folder or any folder above it", remove("board-rules.yaml"), SENSING_TARGET),
    ("a noisy sensing class the project does not define", "sensing clearance: a declared class that is no net class of the project fails", "sensing_clearance",
     "the class 'Switching' is no net class of the design's project file", board_rules("    - Power\n  clearance_mm", "    - Power\n    - Switching\n  clearance_mm"), SENSING_TARGET),
    ("a ground-return mapping with a misspelt key", "ground returns: a key the records decisions do not define is refused by name in the ground-return mapping", "board_rules_record",
     "holds the key 'signal_pins_per_retun'", board_rules("signal_pins_per_return: 2", "signal_pins_per_retun: 2"), SENSING_TARGET),
    ("a ground-return signal class with a ratio that is not a whole number", "ground returns: a signal_pins_per_return that is not a positive whole number fails", "board_rules_record",
     "signal_pins_per_return is 1.5, where it is a positive whole number", board_rules("signal_pins_per_return: 2", "signal_pins_per_return: 1.5"), SENSING_TARGET),
    ("a ground-return connector whose signal pins exceed the declared signal pins per return", "ground returns: a connector whose signal pins exceed the signal class's signal_pins_per_return times its ground-return pins fails", "ground_return",
     "connector J9 has 2 signal pins (1 [/AMP_OUT], 2 [/AMP_FB]) and 1 ground-return pins (3 [/GND])", connector("/AMP_OUT", "/AMP_FB", "/GND"), SENSING_TARGET),
    ("a ground-return connector with signal pins and no ground-return pin", "ground returns: a connector with signal pins and no ground-return pin fails", "ground_return",
     "connector J9 has 1 signal pins (1 [/AMP_OUT]) and 0 ground-return pins (none)", connector("/AMP_OUT", "/+5V"), SENSING_TARGET),
    ("a ground-return connector pin on a class declared neither ground nor signal", "ground returns: a connector pin on a class declared none of ground, signal or non-signal fails", "ground_return",
     "pin 2 of connector J9 is on net /+3V3, in the net class Supply, which hardware/proof/review-proof/board-rules.yaml ground_returns declares as none of ground, signal or non-signal",
     connector("/AMP_OUT", "/+3V3", "/GND", record=board_rules(NON_SIGNAL, "  non_signal_classes:\n    - Mains\n    - Power\n  signal_classes:\n")), SENSING_TARGET),
    ("a ground-return connector of two signal classes over the smaller signal pins per return", "ground returns: a connector carrying several signal classes is held to the smallest signal_pins_per_return among them", "ground_return",
     "connector J9 has 2 signal pins (1 [/AMP_OUT], 2 [/+3V3]) and 1 ground-return pins (3 [/GND]); hardware/proof/review-proof/board-rules.yaml ground_returns lets one return serve 1 signal pins at most",
     connector("/AMP_OUT", "/+3V3", "/GND", record=supply_a_signal), SENSING_TARGET),
    # The board-minimums and lifecycle rules
    ("a board-setup track width looser than the manufacturer's limit for its process", "board minimums: a board whose minimum track width is looser than the manufacturer limits record's figure for its process fails", "board_minimums",
     "the board setup's min_track_width is 0.05 mm, looser than the manufacturer's hardware/proof/manufacturer-limits.yaml limits min_track_width, 0.1 mm for 2 copper layers at 1 oz",
     lambda seed: seed.project(lambda data: data["board"]["design_settings"]["rules"].update(min_track_width=0.05))),
    ("a design whose copper layers and outer copper weight the manufacturer limits record does not list", "board minimums: a board whose process the record does not list fails", "board_minimums",
     "its board rules record declares a finished outer copper weight of 2 oz, a process hardware/proof/manufacturer-limits.yaml does not list",
     board_rules("outer_copper_oz: 1", "outer_copper_oz: 2")),
    ("a board rules record declaring no outer copper weight", "board minimums: a design whose board rules record declares no finished outer copper weight fails", "board_rules_record",
     "fabrication lacks outer_copper_oz", board_rules("  outer_copper_oz: 1\n", "")),
    ("a manufacturer limits record read longer ago than its own max_age_days", "board minimums: a record older than its own max_age_days fails", "manufacturer_limits_record",
     "past the 30 days it allows itself",
     lambda seed: (limits("max_age_days: 36500", "max_age_days: 30")(seed), limits("read_on: 2026-10-20", "read_on: 2026-01-01")(seed))),
    ("a part whose catalogue lifecycle status is end of life", "lifecycle: a part whose status is end of life, obsolete or not recommended for new designs fails", "parts_lifecycle",
     "the position R1, catalogue number C9000002, has the lifecycle status 'end of life'",
     extract("    stock: 1001\n    unit_price: 0.01\n    lifecycle:\n      status: active", "    stock: 1001\n    unit_price: 0.01\n    lifecycle:\n      status: end of life")),
    ("a part whose catalogue entry lacks its lifecycle mapping", "lifecycle: the mapping is required on the entry of every part the design places", "parts_lifecycle",
     "the position R1, catalogue number C9000002, has no lifecycle in the catalogue extract",
     extract("    stock: 1001\n    unit_price: 0.01\n    lifecycle:\n      status: active\n      source: none -- synthetic lifecycle reading\n      read_on: 2026-10-14\n", "    stock: 1001\n    unit_price: 0.01\n")),
]


def target_of(fault) -> Tuple[str, str]:
    """The design a fault is seeded into, as its folder from the repository's root and its name."""
    return fault[5] if len(fault) > 5 else (DESIGN, NAME)


def committed(path: str) -> Optional[Dict[str, bytes]]:
    """Every file git holds at HEAD at or under `path`, by its path from the repository's root, or None when git cannot say."""
    archive = subprocess.run(["git", "-C", REPO, "archive", "--format=tar", "HEAD", "--", path], capture_output=True)
    if archive.returncode != 0:
        return None
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                files[member.name] = tar.extractfile(member).read()
    return files or None


def prepare(scratch: str, design: str = DESIGN, name: str = NAME) -> Seed:
    """A fresh copy of the design at `design`, from the repository's root, in its own git work tree under `scratch`.

    The files are copied as the repository's last commit holds them, so the copy
    is the committed design and not whatever else lies beside it or is edited in
    the working tree; only where git cannot say, outside a git checkout, is the
    folder copied as it stands.
    """
    root = os.path.join(scratch, "repository")
    held = committed(design)
    if held is None:
        shutil.copytree(os.path.join(REPO, design), os.path.join(root, design))
        held = {os.path.relpath(os.path.join(directory, file), root): b""
                for directory, _, files in os.walk(os.path.join(root, design)) for file in files}
    else:
        for path, content in held.items():
            target = os.path.join(root, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(content)
    for record in SHARED_RECORDS:
        shared = committed(record)
        target = os.path.join(root, record)
        if shared is not None:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(shared[record])
        elif os.path.isfile(os.path.join(REPO, record)):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(REPO, record), target)
    subprocess.run(["git", "init", "-q", root], check=True)
    seed = Seed(root, design, name)
    seed.files = sorted(os.path.relpath(path, design) for path in held)
    return seed


def check(seed: Seed, kicad_cli: str) -> Tuple[int, List[str], str]:
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "--allow-empty", "-m", "seeded copy")
    seed.kicad_cli = kicad_cli
    for edit in seed.after:
        edit(seed)
    seed.after = []
    result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_check.py"), "--root", seed.root,
                             "--kicad-cli", kicad_cli], capture_output=True, text=True,
                            env={**os.environ, **seed.environment})
    return result.returncode, result.stdout.splitlines(), result.stderr.strip()


def prove(fault, kicad_cli: str) -> Tuple[bool, str]:
    name, _, rule, text, edit = fault[:5]
    with tempfile.TemporaryDirectory(prefix="board-prove-") as scratch:
        seed = prepare(scratch, *target_of(fault))
        edit(seed)
        status, lines, stderr = check(seed, kicad_cli)
    if status == 2:
        return False, f"the check could not run: {stderr}"
    spared = fault[6] if len(fault) > 6 else None
    for line in lines:
        if spared is not None and line.startswith("VIOLATION") and spared in line:
            return False, f"a violation names what the check must leave alone ({spared!r}): {line}"
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

    faults = [fault for fault in FAULTS if not args.only or any(word in fault[0] for word in args.only)]
    clean_ok = True
    for design, name in dict.fromkeys([(DESIGN, NAME)] + [target_of(fault) for fault in faults]):
        with tempfile.TemporaryDirectory(prefix="board-prove-") as scratch:
            seed = prepare(scratch, design, name)
            status, lines, stderr = check(seed, args.kicad_cli)
        clean_ok = clean_ok and status == 0
        print(f"{'CLEAN' if status == 0 else 'DIRTY'} | {'the throwaway design' if design == DESIGN else design} as committed | must pass | "
              + (" / ".join(lines[1:]) if lines else stderr))

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        outcomes = list(pool.map(lambda fault: prove(fault, args.kicad_cli), faults))
    missed = 0
    for (name, proves, *_), (caught, evidence) in zip(faults, outcomes):
        missed += 0 if caught else 1
        print(f"{'CAUGHT' if caught else 'MISSED'} | {name} | {proves} | {evidence}")
    print(f"RESULT | {'PASS' if clean_ok and not missed else 'FAIL'} | {len(faults) - missed} of {len(faults)} faults caught"
          + ("" if clean_ok else "; the clean design did not pass"))
    return 0 if clean_ok and not missed else 1


if __name__ == "__main__":
    sys.exit(main())
