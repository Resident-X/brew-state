#!/usr/bin/env python3
"""Break the throwaway proof design on purpose, once per failure condition, and require the check to notice.

Every failure condition the pre-order check enforces gets a fault seeded for it
here. Each fault is introduced into a fresh copy of hardware/proof/gate-proof in
a temporary directory outside the repository, made into a git work tree of its
own and committed, so the check finds designs exactly as it does in the
repository, and the shipped check is run on it. A fault counts as caught only when the check exits
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
import copy
import io
import json
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


def drop_rule(name: str):
    def seed_it(seed: Seed) -> None:
        text = seed.read(".kicad_dru")
        start = text.index(f'(rule "{name}"')
        end = text.index("\n(rule", start + 1) + 1 if "\n(rule" in text[start + 1:] else len(text)
        seed.write(".kicad_dru", text[:start] + text[end:])
    return seed_it


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
    ("a track off the board's edges and the 45 degrees to them", "workmanship: each track's direction is measured against the board's edges", "workmanship_direction", "3.43 degrees off",
     reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (45, 10.3)])),
    ("a track entering a long pad from its side", "workmanship: the way a track enters a long pad is measured against the pad's axis", "workmanship_pad_entry", "enters it 90.00 degrees off its long axis", long_pad),
    ("a track running across a long pad from side to side", "workmanship: the way a track crosses a long pad is measured against the pad's axis", "workmanship_pad_entry", "runs across it 90.00 degrees off its long axis",
     lambda seed: (long_pad(seed), reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (46.5, 10)])(seed))),
    ("a route narrowed partway along", "workmanship: a track narrower than its class is measured against its figure", "workmanship_width", "0.15 mm wide, narrower than its net class's 0.25 mm",
     reroute("/LV_A", (LV_A_ENDS,), [(40, 10), (42.5, 10), (45, 10)], (0.25, 0.15))),
    ("a rules file without the corner rule", "workmanship: the rules file holds every workmanship rule", "workmanship_rule", "WORK-4 (corner) has no rule", drop_rule("Corners")),
    ("a jog rule narrowed to some tracks", "workmanship: the rules file's workmanship rules hold on every track", "workmanship_rule", "WORK-5 (jog) is not in force on every track",
     mains_rule('(rule "Jogs"', '(rule "Jogs"\n\t(condition "A.hasNetclass(\'Mains\')")')),
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
]


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
