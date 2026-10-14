#!/usr/bin/env python3
"""Seed known layout defects into a copy of the layout review proof design, and assemble a folder to review it blind.

The pre-order check proves itself by seeding the faults it guards against
(board_prove.py). The layout review cannot be proved the same way, because what
judges a seeded copy is a reviewer following the method's review step, not a
program. So this command does everything up to that judgement and nothing after
it: it copies hardware/proof/review-proof into a temporary git work tree outside
the repository, as board_prove.py copies its own proof design, places one or
more layout defects there for every area of the method's layout practice
catalogue, and requires the pre-order check to pass the seeded copy, since the
review step begins only once the check passes a board. A seed the check catches
is no test of the review, so a copy the check fails is refused.

It then writes a review folder holding only what the review step gives a
reviewer: the seeded copy at its path from the repository's root, with the
floorplan, plan and rules records that travel with it; the method as written;
the hardware readme the method points to for the views' index and per-net
facts; every layout review view rendered from the copy; and the pre-order
check's report on it. Nothing in the folder names the repository or the seeds.
The seed list, each seed's identifier, the catalogue item that covers it, its
layer, its board position and what it is, is written apart from the folder, to
a path the caller names, and is refused inside the review folder or inside a
design's folder.

    review_seed.py --seeds <seed list file> --out <review folder> [--kicad-cli ...] [--resvg ...]
    review_seed.py --print-prompt

--print-prompt prints the fixed prompt a blind review is started with. It
names nothing seeded.

Each step is reported on one line, a RESULT line comes last, and the exit status
is 0 when the folder and the seed list are written, 1 when the command is
refused, and 2 when it cannot run, for example because a tool is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
DESIGN = "hardware/proof/review-proof"
NAME = "review-proof"
#: The critical classes the proof design's routing locked, which its views are rendered for.
CLASSES = ("Mains", "Power", "Supply", "Ground", "Sensing")
#: What the review step gives a reviewer besides the design and its views, by path from the repository's root.
DOCUMENTS = ("docs/board-design-method.md", "hardware/README.md")
VIEWS = "views"
REPORT = "check-report.txt"

PROMPT = """You are reviewing a finished printed circuit board layout. You did not design it, and you have \
no notes from whoever did. Work only from the files in this folder.

Follow the "Layout review" section of docs/board-design-method.md, as written, for the board design in \
hardware/proof/review-proof/ (its project, schematic, layout and rules files, its layout-plan.md and its \
design-rules.md, and every record those name). Its checklist is every item of the "Layout practice catalogue" \
in that document together with the board's own items in layout-plan.md.

What the review step's round 1 would have you produce has been prepared for you:
- the layout review views, already rendered from the board's files by the views command, are in views/; \
views/index.txt lists every image with its caption fields, and views/facts.txt gives every net's track widths, \
via count, zones and classes (hardware/README.md, section "The layout review views", describes them);
- the pre-order check's report on the board is in check-report.txt.

You cannot run commands, render further views or commit anything. The views in views/ are the full set the \
views command makes; where an item would need a view that is not among them, give it the verdict the method \
gives for that case and say which view it needs. Write "the design files in this folder" where the method asks \
for the commit the round judges.

Judge every checklist item on the views its "Judged on" names, open each of those images, and read the board \
coordinates from the captions. Compare the layout with layout-plan.md, then make the free pass over every view.

Return the round 1 review record as your answer, in Markdown, exactly as the method's step lays it out: the \
round's opening lines, the verdict table with one row for every checklist item, and the findings table with one \
row for every finding, each finding's What and where giving the view and the board coordinates that show it. \
Leave Rule, Added as, Planning shortfall and Closed by as the method fills them in later steps; give Rule your \
judgement of whether the finding can be a rule. Return nothing but the record.
"""


class Refused(Exception):
    """The command will not go on, for the reason given."""


# --- Editing the copy's layout ------------------------------------------------------------

Q = sexpr.Quoted
NEAR = 1e-3


def point(node: list) -> Tuple[float, float]:
    return float(node[1]), float(node[2])


def same(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) < NEAR and abs(a[1] - b[1]) < NEAR


def segment(tree: list, a: Tuple[float, float], b: Tuple[float, float]) -> list:
    """The track running from `a` to `b`, either way round."""
    for item in sexpr.children(tree, "segment"):
        ends = point(sexpr.child(item, "start")), point(sexpr.child(item, "end"))
        if (same(ends[0], a) and same(ends[1], b)) or (same(ends[0], b) and same(ends[1], a)):
            return item
    raise AssertionError(f"the proof layout has no track from {a} to {b}; the seed cannot be placed")


def via(tree: list, at: Tuple[float, float]) -> list:
    for item in sexpr.children(tree, "via"):
        if same(point(sexpr.child(item, "at")), at):
            return item
    raise AssertionError(f"the proof layout has no via at {at}; the seed cannot be placed")


def mm(value: float) -> str:
    """A coordinate as the layout writes it, to the nanometre and no further."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def track(net: str, layer: str, a: Tuple[float, float], b: Tuple[float, float], width: float, uuid: str) -> list:
    return ["segment", ["start", mm(a[0]), mm(a[1])], ["end", mm(b[0]), mm(b[1])], ["width", mm(width)],
            ["layer", Q(layer)], ["net", Q(net)], ["uuid", Q(uuid)]]


def new_via(net: str, at: Tuple[float, float], uuid: str) -> list:
    return ["via", ["at", mm(at[0]), mm(at[1])], ["size", "0.9"], ["drill", "0.35"], ["layers", Q("F.Cu"), Q("B.Cu")],
            ["net", Q(net)], ["uuid", Q(uuid)]]


def append(tree: list, *items: list) -> None:
    for item in items:
        tree.insert(len(tree) - 1, item)


def snapped(tree: list, at: Tuple[float, float]) -> Tuple[float, float]:
    """`at`, or the centre of the via it falls on as the layout writes it, so a track ends exactly there."""
    for item in sexpr.children(tree, "via"):
        centre = point(sexpr.child(item, "at"))
        if abs(centre[0] - at[0]) < 0.01 and abs(centre[1] - at[1]) < 0.01:
            return centre
    return at


def path(tree: list, net: str, layer: str, width: float, points: List[Tuple[float, float]], prefix: str) -> None:
    """Tracks joining `points` in turn, each named from `prefix` and its place along the path."""
    points = [snapped(tree, at) for at in points]
    for index, (a, b) in enumerate(zip(points, points[1:]), start=1):
        append(tree, track(net, layer, a, b, width, f"{prefix}{index:04d}"))


def zones(tree: list, net: str) -> List[list]:
    return [item for item in sexpr.children(tree, "zone") if sexpr.child(item, "net")[1] == net]


def move(tree: list, reference: str, x: float, y: float) -> None:
    at = sexpr.child(board_prove.footprint(tree, reference), "at")
    at[1:3] = [mm(x), mm(y)]


def to_front(footprint: list) -> None:
    """A footprint moved from the bottom side to the top, as KiCad flips one: layers swapped, mirrored about the x axis."""
    def flip(node: list, top: bool) -> None:
        for index, child in enumerate(node):
            if not isinstance(child, list) or not child:
                continue
            if child[0] in ("layer", "layers"):
                child[1:] = [Q("F." + str(name)[2:]) if str(name).startswith("B.") else name for name in child[1:]]
            elif child[0] == "justify":
                node[index] = [atom for atom in child if atom != "mirror"]
            elif child[0] in ("at", "start", "end", "center", "mid", "xy") and not top and len(child) > 2:
                child[2] = mm(-float(child[2]))
                if child[0] == "at" and len(child) > 3:
                    child[3] = f"{(180 - float(child[3])) % 360:g}"
            flip(child, False)
        node[:] = [child for child in node if child != ["justify"]]
    flip(footprint, True)


GND = "/GND"


def thin_ground(seed: board_prove.Seed) -> None:
    """Every ground plane and pour taken away, and ground carried instead by 0.4 mm tracks on In1.Cu."""
    def edit(tree: list) -> None:
        for zone in zones(tree, GND):
            tree.remove(zone)
        # Joined in turn: the supply connector's ground pin and the ground vias of every part, as one tree of tracks.
        branches = [
            [(39.5, 3.5), (40.3, 4.3), (40.3, 9.2), (38.9, 10.6), (38.9, 11.7), (38.9, 17.4), (38.9, 22.6), (40.85, 22.6),
             (42.4, 22.6), (42.4, 30)],
            [(38.9, 22.6), (35.325, 22.6), (35.325, 23)],
            [(38.9, 17.4), (50, 17.4), (67.4, 17.4), (71.35, 17.4), (74.5, 17.4), (74.5, 20.7)],
            [(71.35, 17.4), (71.35, 14.65), (71.35, 13.35), (72.65, 13.35), (72.65, 14.65)],
            [(72.65, 13.35), (72.65, 7.5), (86.5, 7.5), (86.5, 9.75), (86.5, 26), (86.5, 41.7), (86.5, 52.6),
             (65.5, 52.6), (65.5, 55.5), (66.5, 55.5), (69.5, 55.5)],
            [(86.5, 41.7), (72.7, 41.7)],
            [(65.5, 52.6), (65.5, 44.9), (64.6, 44.9), (64.6, 44)],
        ]
        for number, points in enumerate(branches, start=1):
            path(tree, GND, "In1.Cu", 0.4, points, f"5eed0001-0000-4000-8000-0{number:03d}0000")
    seed.layout(edit)


def long_way_decoupling(seed: board_prove.Seed) -> None:
    """The controller's decoupling capacitor C4 moved across the controller, reached from the supply pin the long way round."""
    def edit(tree: list) -> None:
        for a, b in (((66.7, 15.825), (68.5, 15.825)), ((68.5, 15.825), (69.8, 15)), ((68.5, 17.375), (67.4, 18.6))):
            tree.remove(segment(tree, a, b))
        tree.remove(via(tree, (67.4, 18.6)))
        move(tree, "C4", 74.5, 18.5)
        reference = [prop for prop in sexpr.children(board_prove.footprint(tree, "C4"), "property") if prop[1] == "Reference"][0]
        sexpr.child(reference, "at")[1:4] = ["0", "-1.6", "90"]
        path(tree, "/+3V3", "F.Cu", 0.3, [(66.7, 15.825), (69.2, 15.825), (69.8, 15.225), (69.8, 15)],
             "5eed0002-0000-4000-8000-00000000")
        path(tree, "/+3V3", "F.Cu", 0.3, [(70.075, 15), (70.075, 17.3), (74.5, 17.3), (74.5, 17.725)],
             "5eed0002-0000-4000-8000-00000001")
        append(tree, track(GND, "F.Cu", (74.5, 19.275), (74.5, 20.7), 0.4, "5eed0002-0000-4000-8000-000000001001"),
               new_via(GND, (74.5, 20.7), "5eed0002-0000-4000-8000-000000001002"))
    seed.layout(edit)


def bare_load_pads(seed: board_prove.Seed) -> None:
    """The copper areas on both sides round the phototriac's load-side pads taken away, leaving bare tracks."""
    def edit(tree: list) -> None:
        for net in ("/MAINS_L", "/MAINS_SW"):
            for zone in zones(tree, net):
                tree.remove(zone)
    seed.layout(edit)


def supply_through_mains(seed: board_prove.Seed) -> None:
    """The +5V supply trunk to the load connector looped through the mains region, beyond the signed distances."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (37, 3.5), (37, 55.5)))
        path(tree, "/+5V", "F.Cu", 0.8, [(37, 3.5), (37, 39.5), (22, 39.5), (22, 50), (37, 50), (37, 55.5)],
             "5eed0004-0000-4000-8000-00000000")
    seed.layout(edit)


def drive_through_sensing(seed: board_prove.Seed) -> None:
    """The phototriac drive line LED_DRV rerouted on B.Cu through the analog sensing region."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (64, 13), (64, 26)))
        tree.remove(segment(tree, (64, 26), (33.8, 26)))
        path(tree, "/LED_DRV", "B.Cu", 0.25, [(64, 13), (64, 40), (46, 40), (46, 26), (33.8, 26)],
             "5eed0005-0000-4000-8000-00000000")
    seed.layout(edit)


def sense_off_the_load_track(seed: board_prove.Seed) -> None:
    """The amplifier's sense track taken off the load-current track 8 mm short of the shunt, not from the shunt's pad."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (58.038, 52), (58.038, 46.4)))
        path(tree, "/LOAD_RTN", "F.Cu", 0.4, [(50, 52), (50, 46.4), (58.038, 46.4)], "5eed0006-0000-4000-8000-00000000")
    seed.layout(edit)


def load_capacitor_away(seed: board_prove.Seed) -> None:
    """The crystal's XTAL1 load capacitor C5 moved away from the crystal and its partner, reached by a long track."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (76.8, 18.25), (83.625, 18.25)))
        tree.remove(segment(tree, (85.175, 18.25), (86.5, 18.25)))
        tree.remove(via(tree, (86.5, 18.25)))
        move(tree, "C5", 84.4, 26)
        path(tree, "/XTAL1", "F.Cu", 0.25, [(76.8, 18.25), (81.5, 18.25), (81.5, 26), (83.625, 26)],
             "5eed0007-0000-4000-8000-00000000")
        append(tree, track(GND, "F.Cu", (85.175, 26), (86.5, 26), 0.4, "5eed0007-0000-4000-8000-000000000001"),
               new_via(GND, (86.5, 26), "5eed0007-0000-4000-8000-000000000002"))
    seed.layout(edit)


def suppressor_away(seed: board_prove.Seed) -> None:
    """The supply input's suppressor D1 moved 26 mm from its connector, onto a stub off the supply trunk."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (39.1, 9.2), (40.3, 9.2)))
        tree.remove(via(tree, (40.3, 9.2)))
        move(tree, "D1", 40.05, 30)
        append(tree, track("/+5V", "F.Cu", (37, 30), (39, 30), 0.8, "5eed0008-0000-4000-8000-000000000001"),
               track(GND, "F.Cu", (41.1, 30), (42.4, 30), 0.4, "5eed0008-0000-4000-8000-000000000002"),
               new_via(GND, (42.4, 30), "5eed0008-0000-4000-8000-000000000003"))
    seed.layout(edit)


def test_point_on_top(seed: board_prove.Seed) -> None:
    """Test point TP5 moved to the top side, so the test points sit on both sides."""
    seed.layout(lambda tree: to_front(board_prove.footprint(tree, "TP5")))


EDGE_ROW = "| Copper to board edge | 0.3 mm |"


def edge_minimum_below_source(seed: board_prove.Seed) -> None:
    """The board-wide copper-to-edge minimum set to 0.2 mm, below the 0.3 mm its row's source recommends."""
    seed.project(lambda data: data["board"]["design_settings"]["rules"].update(min_copper_edge_clearance=0.2))
    seed.replace("design-rules.md", EDGE_ROW, "| Copper to board edge | 0.2 mm |")


def bead_at_the_source(seed: board_prove.Seed) -> None:
    """The amplifier's supply bead FB1 moved to the far end of the supply, by the regulator's trunk, away from the amplifier."""
    def edit(tree: list) -> None:
        tree.remove(segment(tree, (66, 15.1), (66, 37)))
        tree.remove(segment(tree, (69.14, 37), (69.14, 37.712)))
        sexpr.child(segment(tree, (66, 37), (69.14, 37)), "net")[1] = Q("/+3V3A")
        move(tree, "FB1", 66, 18)
        append(tree, track("/+3V3", "F.Cu", (66, 15.1), (66, 17.212), 0.4, "5eed0011-0000-4000-8000-000000000001"),
               track("/+3V3A", "F.Cu", (66, 18.788), (66, 37), 0.4, "5eed0011-0000-4000-8000-000000000002"),
               track("/+3V3A", "F.Cu", (69.14, 37), (69.14, 39.288), 0.3, "5eed0011-0000-4000-8000-000000000003"))
    seed.layout(edit)


#: (identifier, the catalogue item that covers it, layer, board position in mm, what it is, the edit)
SEEDS: List[Tuple[str, str, str, Tuple[float, float], str, Callable[[board_prove.Seed], None]]] = [
    ("S1", "GROUND-1", "F.Cu, In1.Cu, In2.Cu, B.Cu", (61, 30),
     "ground drawn as thin traces: the four ground planes and pours removed and ground carried by 0.4 mm tracks on In1.Cu",
     thin_ground),
    ("S2", "DECOUPLE-1", "F.Cu", (74.5, 18.5),
     "a decoupling capacitor routed the long way round to its pin: C4 moved across U4, the supply reaching U4's VCC pin "
     "before it", long_way_decoupling),
    ("S3", "POWER-5", "F.Cu, B.Cu", (24.19, 21.46),
     "a high-current pad without the copper it needs: the copper areas round U1's load-side pads removed on both sides",
     bare_load_pads),
    ("S4", "MAINS-2", "F.Cu", (22, 45),
     "low-voltage copper inside the mains region: the +5V trunk looped through the mains region at x 22 mm", supply_through_mains),
    ("S5", "FLOOR-2", "B.Cu", (64, 34),
     "a digital track through the analog sensing region: LED_DRV rerouted down x 64 mm and along y 40 mm", drive_through_sensing),
    ("S6", "SENSE-1", "F.Cu", (50, 49),
     "a sense connection off the load-current track: the amplifier's LOAD_RTN sense track tapped 8 mm short of R1's pad",
     sense_off_the_load_track),
    ("S7", "CLOCK-1", "F.Cu", (84.4, 26),
     "a load capacitor away from the crystal: C5 moved 7.75 mm from Y1's pad and from C6", load_capacitor_away),
    ("S8", "CONN-1", "F.Cu", (40.05, 30),
     "a suppressor away from its connector: D1 moved 26 mm from J2 onto a stub off the +5V trunk", suppressor_away),
    ("S9", "TEST-2", "F.Cu", (66.5, 55.5),
     "test points on both sides: TP5 moved to the top side", test_point_on_top),
    ("S10", "MFG-1", "design-rules.md, Board Setup", (0, 0),
     "a board-wide minimum below its source: copper-to-edge set to 0.2 mm where the row's source recommends more than "
     "0.3 mm", edge_minimum_below_source),
    ("S11", "EMI-4", "F.Cu", (66, 18),
     "a supply ferrite bead at the far end of the supply: FB1 moved from U3 to the +3V3 trunk by U4, 20 mm from U3",
     bead_at_the_source),
]


# --- The command -------------------------------------------------------------------------------


def inside(path: str, folder: str) -> bool:
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return os.path.commonpath([path, folder]) == folder


def design_folder(path: str) -> Optional[str]:
    """The folder holding a KiCad project file that `path` sits in, at any depth, or None."""
    folder = os.path.dirname(os.path.realpath(path))
    while True:
        try:
            if any(name.endswith(".kicad_pro") for name in os.listdir(folder)):
                return folder
        except OSError:
            pass
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def refusals(seeds: str, out: str, repo: str = REPO) -> List[str]:
    """Why the seed list or the review folder cannot be written where they are asked to go."""
    found = []
    if inside(out, repo):
        found.append(f"the review folder {out} is inside the repository; a reviewer working there could read the "
                     "proof design as committed and the seeding command, so put it outside")
    if os.path.isfile(out):
        found.append(f"the review folder {out} is a file")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"the review folder {out} already holds files; give a new or empty folder")
    if inside(seeds, out):
        found.append(f"the seed list {seeds} is inside the review folder, where the reviewer would read it")
    holder = design_folder(seeds)
    if holder is not None:
        found.append(f"the seed list {seeds} is inside the design folder {holder}; write it outside every design's folder")
    if os.path.isdir(seeds):
        found.append(f"the seed list {seeds} is a folder")
    return found


def seed_list(seeds) -> dict:
    return {"design": DESIGN, "seeds": [{"id": ident, "item": item, "layer": layer, "position": {"x": x, "y": y},
                                         "description": description}
                                        for ident, item, layer, (x, y), description, _ in seeds]}


def assemble(seed: board_prove.Seed, out: str, report: List[str], kicad_cli: str, resvg: str) -> Tuple[bool, str]:
    """The review folder written from the seeded copy; whether the views were rendered, and their report."""
    shutil.copytree(seed.design, os.path.join(out, DESIGN), ignore=shutil.ignore_patterns(".git"))
    for document in DOCUMENTS:
        os.makedirs(os.path.dirname(os.path.join(out, document)), exist_ok=True)
        shutil.copy2(os.path.join(REPO, document), os.path.join(out, document))
    with open(os.path.join(out, REPORT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report) + "\n")
    command = [sys.executable, os.path.join(TOOLS, "board_views.py"), "--kicad-cli", kicad_cli, "--resvg", resvg,
               "--board", f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro"]
    for name in CLASSES:
        command += ["--class", name]
    command += ["--out", os.path.join(out, VIEWS)]
    result = subprocess.run(command, cwd=os.path.join(out, DESIGN), capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seeds", help="where to write the seed list, outside the review folder and every design's folder")
    parser.add_argument("--out", help="the review folder to write, new or empty, outside the repository")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg program the views are drawn with (default: resvg on the search path)")
    parser.add_argument("--print-prompt", action="store_true", help="print the fixed prompt a blind review is started with, and stop")
    args = parser.parse_args(argv)
    if args.print_prompt:
        print(PROMPT, end="")
        return 0
    if not args.seeds or not args.out:
        parser.error("--seeds and --out are both required")
    seeds, out = os.path.abspath(args.seeds), os.path.abspath(args.out)
    found = refusals(seeds, out)
    if found:
        for why in found:
            print(f"REFUSED | {board_check.clean(why)}")
        print("RESULT | REFUSED | nothing was written")
        return 1
    try:
        board_check.require_python()
        board_check.require_yaml()
        board_check.require_kicad(args.kicad_cli)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="review-seed-") as scratch:
        seed = board_prove.prepare(scratch, DESIGN, NAME)
        for _, _, _, _, _, edit in SEEDS:
            edit(seed)
        status, lines, stderr = board_prove.check(seed, args.kicad_cli)
        if status == 2:
            print(f"CANNOT RUN | the pre-order check could not run on the seeded copy: {board_check.clean(stderr)}",
                  file=sys.stderr)
            return 2
        report = [line.replace(os.path.realpath(seed.root), ".").replace(seed.root, ".") for line in lines]
        if status != 0:
            print("REFUSED | the pre-order check fails the seeded copy, and a review begins only once it passes a "
                  "board, so a seed the check catches is no test of the review")
            for line in report[1:]:
                print(f"CHECK | {line}")
            print("RESULT | REFUSED | nothing was written")
            return 1
        print(f"CHECK | {report[-1]}")
        os.makedirs(out, exist_ok=True)
        rendered, said = assemble(seed, out, report, args.kicad_cli, args.resvg)
        if not rendered:
            shutil.rmtree(out, ignore_errors=True)
            print(f"CANNOT RUN | the views could not be rendered from the seeded copy: {board_check.clean(said)}",
                  file=sys.stderr)
            return 2
    with open(seeds, "w", encoding="utf-8") as handle:
        json.dump(seed_list(SEEDS), handle, indent=2)
        handle.write("\n")
    print(f"VIEWS | {said.splitlines()[-1] if said else 'rendered'}")
    print(f"SEEDS | {len(SEEDS)} seeds | {seeds}")
    print(f"RESULT | WRITTEN | {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
