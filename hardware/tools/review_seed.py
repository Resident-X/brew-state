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
reviewer: the seeded copy's KiCad files at its path from the repository's root,
with the floorplan, plan and rules records that travel with it, and nothing else
of its folder, so never the design's own review record; the method as written;
the hardware readme the method points to for the views' index and per-net
facts; every layout review view rendered from the copy; the placement view and
its measures rendered from the copy, in a folder of their own; and the
pre-order check's report on it. Nothing in the folder names the repository or the seeds,
and nothing in it tells a seeded item or file from an unseeded one but the
defect itself: every item a seed adds takes a fresh random identifier of the
form the design's own items carry, KiCad itself refills and saves the seeded
layout, so every item sits where and as KiCad writes it, the folder holds no
file the committed design lacks, and every file in it carries one time.
The design and the documents are taken as the repository's last commit holds
them.
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
import time
import uuid
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
#: The records of the design's own folder the review step gives a reviewer, by path inside it: the floorplan and plan,
#: the rules table, and the records the rules table reads its figures from.
RECORDS = ("layout-plan.md", "design-rules.md", "constraints.md", "separation-basis.yaml")
#: The endings of KiCad's own files of a design: its project, schematic, layout, rules and library files.
KICAD_FILES = (".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_dru", ".kicad_sym", ".kicad_mod")
VIEWS = "views"
PLACEMENT = "placement"
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
- the placement view, already rendered from the board's files by the placement command, is in placement/; \
placement/index.txt lists its images with their caption fields, and placement/measures.txt gives the \
placement's measures, its connections' lengths, their crossings and every part outside its floorplan regions \
(hardware/README.md, section "The placement view", describes them);
- the pre-order check's report on the board is in check-report.txt.

You cannot run commands, render further views or commit anything. The views in views/ and placement/ are the \
full set the views command and the placement command make; where an item would need a view that is not among them, give it the verdict the method \
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


def identifier() -> str:
    """A fresh random identifier, of the same form as every one KiCad gave the design's own items."""
    return str(uuid.uuid4())


def track(net: str, layer: str, a: Tuple[float, float], b: Tuple[float, float], width: float) -> list:
    return ["segment", ["start", mm(a[0]), mm(a[1])], ["end", mm(b[0]), mm(b[1])], ["width", mm(width)],
            ["layer", Q(layer)], ["net", Q(net)], ["uuid", Q(identifier())]]


def new_via(net: str, at: Tuple[float, float]) -> list:
    return ["via", ["at", mm(at[0]), mm(at[1])], ["size", "0.9"], ["drill", "0.35"], ["layers", Q("F.Cu"), Q("B.Cu")],
            ["net", Q(net)], ["uuid", Q(identifier())]]


def append(tree: list, *items: list) -> None:
    """Items added to the layout; where they fall in the file is settled when KiCad saves it (see settle_layout)."""
    for item in items:
        tree.insert(len(tree) - 1, item)


def snapped(tree: list, at: Tuple[float, float]) -> Tuple[float, float]:
    """`at`, or the centre of the via it falls on as the layout writes it, so a track ends exactly there."""
    for item in sexpr.children(tree, "via"):
        centre = point(sexpr.child(item, "at"))
        if abs(centre[0] - at[0]) < 0.01 and abs(centre[1] - at[1]) < 0.01:
            return centre
    return at


def path(tree: list, net: str, layer: str, width: float, points: List[Tuple[float, float]]) -> None:
    """Tracks joining `points` in turn."""
    points = [snapped(tree, at) for at in points]
    for a, b in zip(points, points[1:]):
        append(tree, track(net, layer, a, b, width))


def zones(tree: list, net: str) -> List[list]:
    """Every zone filled with `net`'s copper; a rule area, which carries no net, is none of them."""
    return [item for item in sexpr.children(tree, "zone")
            if sexpr.child(item, "net") is not None and sexpr.child(item, "net")[1] == net]


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


def turn(tree: list, reference: str, angle: float) -> None:
    """A footprint turned to `angle` about its own origin, as KiCad turns one: its pads and texts turned with it."""
    footprint = board_prove.footprint(tree, reference)
    at = sexpr.child(footprint, "at")
    delta = angle - (float(at[3]) if len(at) > 3 else 0.0)
    at[1:] = at[1:3] + ([f"{angle:g}"] if angle else [])
    for node in sexpr.children(footprint, "pad") + sexpr.children(footprint, "property"):
        own = sexpr.child(node, "at")
        if own is not None and len(own) > 2:
            turned = ((float(own[3]) if len(own) > 3 else 0.0) + delta) % 360
            own[1:] = own[1:3] + ([f"{turned:g}"] if turned or sexpr.head(node) == "property" else [])


def drop(tree: list, *ends: Tuple[Tuple[float, float], Tuple[float, float]]) -> None:
    for a, b in ends:
        tree.remove(segment(tree, a, b))


def drop_via(tree: list, *at: Tuple[float, float]) -> None:
    for point_ in at:
        tree.remove(via(tree, point_))


#: The ground network carried on In1.Cu once the planes and pours are gone:
#: each run of 0.5 mm tracks joins the next point in turn, from the supply
#: connector's ground pin to every ground via of the seeded copy.
GROUND_TRACES = [
    [(39.5, 3.5), (39.5, 6), (51, 6), (60.4, 6), (62.5, 6), (66.1, 6), (80, 6), (80, 19)],
    [(39.5, 6), (39.5, 11.7), (38.9, 11.7)],
    [(39.5, 6), (33.85, 6), (33.85, 11.5), (33.85, 16.3), (33.85, 28), (33.85, 38.1), (33.85, 58.9), (46.35, 58.9)],
    [(33.85, 28), (40.3, 28)],
    [(51, 6), (51, 10.6)],
    [(60.4, 6), (60.4, 21.55), (59.8, 21.55)],
    [(62.5, 6), (62.5, 14.9), (62.5, 44.6), (72.55, 44.6)],
    [(66.1, 6), (66.1, 10.1)],
    [(62.5, 44.6), (62.5, 54), (62.962, 54), (62.962, 58.8)],
]


def thin_ground(seed: board_prove.Seed) -> None:
    """Every ground plane and pour taken away, and ground carried instead by 0.5 mm tracks on In1.Cu."""
    def edit(tree: list) -> None:
        for zone in zones(tree, GND):
            tree.remove(zone)
        for points in GROUND_TRACES:
            path(tree, GND, "In1.Cu", 0.5, points)
    seed.layout(edit)


def long_way_decoupling(seed: board_prove.Seed) -> None:
    """The controller's decoupling capacitor C4 moved 4 mm south, on a spur the supply reaches only after U4's supply pin."""
    def edit(tree: list) -> None:
        drop(tree, ((58.55, 17.55), (59.8, 17.55)))
        drop_via(tree, (59.8, 17.55))
        move(tree, "C4", 58.55, 20.775)
        path(tree, "/+3V3", "F.Cu", 0.3, [(58.55, 16), (58.55, 20)])
        path(tree, GND, "F.Cu", 0.5, [(58.55, 21.55), (59.8, 21.55)])
        append(tree, new_via(GND, (59.8, 21.55)))
    seed.layout(edit)


def bare_load_pads(seed: board_prove.Seed) -> None:
    """The copper areas on both sides round the phototriac's load-side pads taken away, leaving bare tracks."""
    def edit(tree: list) -> None:
        for net in ("/MAINS_L", "/MAINS_SW"):
            for zone in zones(tree, net):
                tree.remove(zone)
    seed.layout(edit)


def supply_through_mains(seed: board_prove.Seed) -> None:
    """The +5V trunk to the load connector looped west through the mains region at x 22 mm, beyond the signed distances."""
    def edit(tree: list) -> None:
        drop(tree, ((37, 42.2), (37, 47.6)), ((37, 47.6), (44.9, 55.5)))
        path(tree, "/+5V", "F.Cu", 0.8, [(37, 42.2), (37, 47), (22, 47), (22, 50), (39.4, 50), (44.9, 55.5)])
    seed.layout(edit)


def drive_through_sensing(seed: board_prove.Seed) -> None:
    """The phototriac drive line LED_DRV rerouted on B.Cu down x 57 mm through the analog sensing region."""
    def edit(tree: list) -> None:
        drop(tree, ((59.1, 13), (48, 13)), ((48, 13), (37, 24)))
        path(tree, "/LED_DRV", "B.Cu", 0.25, [(59.1, 13), (57, 13), (57, 36), (51, 36), (39, 24), (37, 24)])
    seed.layout(edit)


def sense_off_the_load_track(seed: board_prove.Seed) -> None:
    """The amplifier's sense track taken off the load-current track beside J4, 6 mm short of R1's pad, not from the pad."""
    def edit(tree: list) -> None:
        drop(tree, ((57.0375, 51), (57.0375, 48.7)))
        path(tree, "/LOAD_RTN", "F.Cu", 0.8, [(53.8, 55.5), (53.8, 49.7), (54.8, 48.7), (57.0375, 48.7)])
    seed.layout(edit)


def load_capacitor_away(seed: board_prove.Seed) -> None:
    """The crystal's XTAL1 load capacitor C5 moved from beside its partner at U4 to beyond the crystal, off its pad 1."""
    def edit(tree: list) -> None:
        drop(tree, ((66.1, 16.05), (66.1, 17.4)))
        drop_via(tree, (66.1, 17.4))
        turn(tree, "C5", 0)
        move(tree, "C5", 74.675, 19)
        path(tree, "/XTAL1", "F.Cu", 0.25, [(69.7, 15.6), (72.0, 15.6), (73.9, 17.5), (73.9, 19)])
        path(tree, GND, "F.Cu", 0.5, [(75.45, 19), (80, 19)])
        append(tree, new_via(GND, (80, 19)))
    seed.layout(edit)


def suppressor_away(seed: board_prove.Seed) -> None:
    """The supply input's suppressor D1 moved 19 mm from its connector, onto the +5V trunk at y 28 mm."""
    def edit(tree: list) -> None:
        drop(tree, ((39.1, 9.2), (40.3, 9.2)))
        drop_via(tree, (40.3, 9.2))
        move(tree, "D1", 38.05, 28)
        path(tree, GND, "F.Cu", 0.5, [(39.1, 28), (40.3, 28)])
        append(tree, new_via(GND, (40.3, 28)))
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
    """The amplifier's supply bead FB1 moved 11 mm east of its capacitor, 15 mm from U3's supply pin."""
    def edit(tree: list) -> None:
        drop(tree, ((74.588, 40.276), (74.588, 43.05)), ((69.138, 43.05), (73.012, 43.05)))
        move(tree, "FB1", 84.8, 43.05)
        path(tree, "/+3V3", "F.Cu", 0.3, [(74.588, 40.276), (85.588, 40.276), (85.588, 43.05)])
        path(tree, "/+3V3A", "F.Cu", 0.3, [(69.138, 43.05), (84.012, 43.05)])
    seed.layout(edit)


def parts_apart(seed: board_prove.Seed) -> None:
    """The LED resistor R4 moved 15 mm south of U1's pin it serves, its connection running down to it."""
    def edit(tree: list) -> None:
        drop(tree, ((31.81, 21.46), (33.675, 21.46)), ((35.325, 21.46), (35.325, 23)))
        drop_via(tree, (35.325, 23))
        turn(tree, "R4", -90)
        move(tree, "R4", 33.85, 36)
        path(tree, "/LED_K", "F.Cu", 0.25, [(31.81, 21.46), (32.85, 21.46), (33.85, 22.46), (33.85, 35.175)])
        path(tree, GND, "F.Cu", 0.5, [(33.85, 36.825), (33.85, 38.1)])
        append(tree, new_via(GND, (33.85, 38.1)))
    seed.layout(edit)


def needless_layer_change(seed: board_prove.Seed) -> None:
    """XTAL1 dropped to B.Cu and straight back up, through two vias, on its run from U4 to the crystal."""
    def edit(tree: list) -> None:
        drop(tree, ((67.1, 14.5), (68.2, 15.6)))
        path(tree, "/XTAL1", "B.Cu", 0.25, [(67.1, 14.5), (68.2, 15.6)])
        append(tree, new_via("/XTAL1", (67.1, 14.5)), new_via("/XTAL1", (68.2, 15.6)))
    seed.layout(edit)


def figure(row: str, old: str, new: str, variable: Optional[str] = None, value: Optional[str] = None,
           rules: Optional[Tuple[str, str]] = None):
    """A rule's figure loosened below its source: in the rules table's row, and where the board sets it."""
    def seed_it(seed: board_prove.Seed) -> None:
        text = seed.read("design-rules.md")
        line = next(item for item in text.splitlines() if item.startswith(f"| {row} |"))
        seed.replace("design-rules.md", line, line.replace(old, new))
        if variable is not None:
            seed.project(lambda data: data["text_variables"].update({variable: value}))
        if rules is not None:
            seed.replace(".kicad_dru", *rules)
    return seed_it


def route_the_long_way(seed: board_prove.Seed) -> None:
    """The detour ratio raised to 2, and the +3V3 trunk to U4 taken north round a loop from x 54.5 to 56.5 mm."""
    figure("Route length", "| 1.3 |", "| 2 |", "WORK_DETOUR_RATIO", "2")(seed)
    seed.replace("design-rules.md", "WORK_DETOUR_RATIO | 1.3 times", "WORK_DETOUR_RATIO | 2 times")
    def edit(tree: list) -> None:
        drop(tree, ((54.5, 14), (56.5, 16)))
        path(tree, "/+3V3", "F.Cu", 0.3, [(54.5, 14), (54.5, 4), (56.5, 4), (56.5, 16)])
    seed.layout(edit)


def square_corners(seed: board_prove.Seed) -> None:
    """The corner rule's minimum lowered to 90 degrees, and U3's feedback brought into pin 4 round a square corner."""
    figure("Corners", "| 135 |", "| 90 |", rules=("(constraint track_angle (min 135))", "(constraint track_angle (min 90))"))(seed)
    def edit(tree: list) -> None:
        drop(tree, ((69.138, 44.95), (70.15, 44.95)), ((70.15, 44.95), (71.575, 46.375)))
        path(tree, "/AMP_FB", "F.Cu", 0.25, [(69.138, 44.95), (69.138, 46.375), (71.575, 46.375)])
    seed.layout(edit)


def jogs(seed: board_prove.Seed) -> None:
    """The shortest straight run lowered to 0.3 mm, and a 0.4 mm offset jogged into the feedback track from R2 to R3."""
    figure("Jogs", "| 1 mm |", "| 0.3 mm |", rules=("(constraint track_segment_length (min 1mm))",
                                                   "(constraint track_segment_length (min 0.3mm))"))(seed)
    def edit(tree: list) -> None:
        drop(tree, ((71.575, 46.375), (71.575, 47.9)))
        path(tree, "/AMP_FB", "F.Cu", 0.25, [(71.575, 46.375), (71.975, 46.775), (71.975, 47.5), (71.575, 47.9)])
    seed.layout(edit)


def narrowed(seed: board_prove.Seed) -> None:
    """The neck figure raised to 8 mm, and the +3V3 trunk narrowed to 0.2 mm for its last 4 mm into U4."""
    figure("Necks", "| 1 mm |", "| 8 mm |", "WORK_NECK_MM", "8")(seed)
    seed.replace("design-rules.md", "WORK_NECK_MM | 1 mm off", "WORK_NECK_MM | 8 mm off")
    def edit(tree: list) -> None:
        for a, b in (((56.5, 16), (58.55, 16)), ((58.55, 16), (59.55, 15))):
            sexpr.child(segment(tree, a, b), "width")[1] = "0.2"
    seed.layout(edit)


def odd_angle(seed: board_prove.Seed) -> None:
    """The direction tolerance raised to 15 degrees, and the load connector's filter capacitor's ground via moved so its track runs 13 degrees off."""
    figure("Track directions", "| 0.1 degree |", "| 15 degrees |", "WORK_ANGLE_TOLERANCE_DEG", "15")(seed)
    seed.replace("design-rules.md", "WORK_ANGLE_TOLERANCE_DEG | 0.1 degrees", "WORK_ANGLE_TOLERANCE_DEG | 15 degrees")
    def edit(tree: list) -> None:
        drop(tree, ((46, 57.4), (46, 58.9)))
        drop_via(tree, (46, 58.9))
        path(tree, GND, "F.Cu", 0.5, [(46, 57.4), (46.35, 58.9)])
        append(tree, new_via(GND, (46.35, 58.9)))
    seed.layout(edit)


def side_entry(seed: board_prove.Seed) -> None:
    """The pad-entry ratio raised to 10, so no pad on the board counts as long, with U3's pin 4 entered from its side."""
    figure("Pad entries", "| 2 |", "| 10 |", "WORK_PAD_ENTRY_RATIO", "10")(seed)
    seed.replace("design-rules.md", "WORK_PAD_ENTRY_RATIO | 2 times", "WORK_PAD_ENTRY_RATIO | 10 times")


def row_taken_out(row: str):
    """A rules table row taken out: for an item KiCad's own check reports unaided, the row that names the check."""
    def seed_it(seed: board_prove.Seed) -> None:
        line = next(item for item in seed.read("design-rules.md").splitlines() if item.startswith(f"| {row} |"))
        seed.replace("design-rules.md", line + "\n", "")
    return seed_it


#: (identifier, the catalogue item that covers it, layer, board position in mm, what it is, the edit)
SEEDS: List[Tuple[str, str, str, Tuple[float, float], str, Callable[[board_prove.Seed], None]]] = [
    ("S1", "GROUND-1", "F.Cu, In1.Cu, In2.Cu, B.Cu", (61, 30),
     "ground drawn as thin traces: the four ground planes and pours removed and ground carried by 0.5 mm tracks on In1.Cu",
     thin_ground),
    ("S2", "DECOUPLE-1", "F.Cu", (58.55, 20.775),
     "a decoupling capacitor routed the long way round to its pin: C4 moved 4 mm south of U4's supply pin, the supply "
     "reaching the pin before it", long_way_decoupling),
    ("S3", "POWER-5", "F.Cu, B.Cu", (24.19, 21.46),
     "a high-current pad without the copper it needs: the copper areas round U1's load-side pads removed on both sides",
     bare_load_pads),
    ("S4", "MAINS-2", "F.Cu", (22, 48.5),
     "low-voltage copper inside the mains region: the +5V trunk looped through the mains region at x 22 mm", supply_through_mains),
    ("S5", "FLOOR-2", "B.Cu", (57, 32),
     "a digital track through the analog sensing region: LED_DRV rerouted down x 57 mm and along y 36 mm", drive_through_sensing),
    ("S6", "SENSE-1", "F.Cu", (53.8, 52),
     "a sense connection off the load-current track: the amplifier's LOAD_RTN sense track tapped off the load track "
     "beside J4, 6 mm short of R1's pad", sense_off_the_load_track),
    ("S7", "CLOCK-1", "F.Cu", (74.675, 19),
     "a load capacitor away from its oscillator pin and its partner: C5 moved from beside C6 at U4 to beyond the crystal, "
     "11 mm from C6", load_capacitor_away),
    ("S8", "CONN-1", "F.Cu", (38.05, 28),
     "a suppressor away from its connector: D1 moved 24 mm from J2, onto the +5V trunk at y 28 mm", suppressor_away),
    ("S9", "TEST-2", "F.Cu", (62.962, 56.4),
     "test points on both sides: TP5 moved to the top side", test_point_on_top),
    ("S10", "MFG-1", "design-rules.md, Board Setup", (0, 0),
     "a board-wide minimum below its source: copper-to-edge set to 0.2 mm where the row's source recommends more than "
     "0.3 mm", edge_minimum_below_source),
    ("S11", "EMI-4", "F.Cu", (84.8, 43.05),
     "a supply ferrite bead at the far end of the supply: FB1 moved from beside U3 to 11 mm east of its capacitor, "
     "15 mm from U3's supply pin",
     bead_at_the_source),
    ("S12", "WORK-1", "F.Cu", (33.85, 36),
     "a part set apart from the part it serves: R4 moved 15 mm south of U1's pin 2, its connection running down to it",
     parts_apart),
    ("S13", "WORK-3", "F.Cu, B.Cu", (67.65, 15.05),
     "a needless change of layer: XTAL1 dropped to B.Cu and straight back up through two vias on its run to the crystal",
     needless_layer_change),
    ("S14", "WORK-2", "design-rules.md, project text variables, F.Cu", (55.5, 4),
     "a route-length figure looser than its item's and a supply route the long way round: WORK_DETOUR_RATIO 2 where the "
     "item gives 1.3, and the +3V3 trunk to U4 taken north round a loop from x 54.5 to 56.5 mm", route_the_long_way),
    ("S15", "WORK-4", "design-rules.md, rules file, F.Cu", (69.138, 46.375),
     "a corner figure looser than its item's and a square corner: the Corners rule at 90 where the item gives 135, and "
     "U3's feedback turning square into pin 4", square_corners),
    ("S16", "WORK-5", "design-rules.md, rules file, F.Cu", (71.975, 47.1),
     "a jog figure looser than its item's and a jog: the Jogs rule at 0.3 mm where the item gives 1 mm, and a 0.4 mm "
     "offset in the feedback track from R2 to R3", jogs),
    ("S17", "WORK-8", "design-rules.md, project text variables, F.Cu", (57.5, 16),
     "a neck figure looser than its item's and a narrowed route: WORK_NECK_MM 8 where the item gives 1, and the +3V3 "
     "trunk narrowed to 0.2 mm for its last 4 mm into U4", narrowed),
    ("S18", "WORK-9", "design-rules.md, project text variables, F.Cu", (46.2, 58.1),
     "a direction tolerance looser than its item's and a track at an odd angle: WORK_ANGLE_TOLERANCE_DEG 15 where the "
     "item gives 0.1, and C8's ground track to its via running 13 degrees off the board's edges", odd_angle),
    ("S19", "WORK-10", "design-rules.md, project text variables, F.Cu", (69.138, 45.7),
     "a pad-entry ratio looser than its item's and a track entering a long pad from its side: WORK_PAD_ENTRY_RATIO 10 "
     "where the item gives 2, so U3's pin 4, entered from its side by S15's corner, passes", side_entry),
    ("S20", "WORK-6", "design-rules.md", (0, 0),
     "the rules table's row for KiCad's unconnected-track-end check taken out", row_taken_out("Stubs")),
    ("S21", "WORK-7", "design-rules.md", (0, 0),
     "the rules table's row for KiCad's unconnected-via check taken out", row_taken_out("Unconnected vias")),
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


def settle_layout(seed: board_prove.Seed, kicad_cli: str) -> None:
    """The seeded layout refilled and saved by KiCad itself, as it saves any board.

    The seeds are written by this command, not by KiCad, so left as written they
    would differ from every other item in where they sit in the file and how it
    lays them out. KiCad's save writes every item in its own order and form, and
    refilling the copper areas first leaves no fill drawn round where a part or
    track used to be. Saving the committed design this way changes nothing in it,
    so after it the only difference from the committed layout is the seeds
    themselves. KiCad's own leftovers, such as the project's local settings file,
    are taken away, so the copy holds the committed design's files and no others.
    """
    report = os.path.join(os.path.dirname(seed.root), "settle-layout.rpt")
    result = subprocess.run([kicad_cli, "pcb", "drc", "--refill-zones", "--save-board", "--output", report,
                             seed.path(".kicad_pcb")], capture_output=True, text=True)
    if result.returncode != 0:
        raise board_check.CannotRun(f"KiCad could not refill and save the seeded layout: "
                                    f"{(result.stdout + result.stderr).strip()}")
    leftovers(seed.design, seed.files, remove=True)


def leftovers(folder: str, files: List[str], remove: bool = False) -> List[str]:
    """Every file under `folder` that is not one of `files`, by its path inside `folder`; taken away when `remove` is set."""
    found = sorted(os.path.relpath(os.path.join(directory, name), folder)
                   for directory, _, names in os.walk(folder) for name in names
                   if os.path.relpath(os.path.join(directory, name), folder) not in files)
    for name in found if remove else []:
        os.remove(os.path.join(folder, name))
    return found


def given(name: str) -> bool:
    """Whether the review step gives a reviewer the design's file `name`, by its path inside the design's folder.

    It gives KiCad's files of the design, its library tables among them, and the
    records named in RECORDS, and nothing else the folder holds: the design's own
    review record tells what a review of the unseeded board found, and a file the
    step does not name is one it does not give.
    """
    base = os.path.basename(name)
    return name in RECORDS or base.endswith(KICAD_FILES) or base in board_check.LIBRARY_TABLES


def documents() -> Dict[str, bytes]:
    """What the review step gives a reviewer besides the design, as the repository's last commit holds it."""
    found = {}
    for document in DOCUMENTS:
        held = board_prove.committed(document)
        if held is None:
            with open(os.path.join(REPO, document), "rb") as handle:
                held = {document: handle.read()}
        found[document] = held[document]
    return found


def assemble(seed: board_prove.Seed, out: str, report: List[str], kicad_cli: str, resvg: str) -> Tuple[bool, str]:
    """The review folder written from the seeded copy; whether the views and the placement view were rendered, and
    their reports.

    Only the committed design's files the review step gives a reviewer are copied,
    by content alone, and once the folder is complete every file and folder in it
    is given the same time, so no file in it is told from another by when it was
    written.
    """
    files = [name for name in seed.files if given(name)]
    for name in files:
        target = os.path.join(out, DESIGN, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(os.path.join(seed.design, name), target)
    for document, content in documents().items():
        os.makedirs(os.path.dirname(os.path.join(out, document)), exist_ok=True)
        with open(os.path.join(out, document), "wb") as handle:
            handle.write(content)
    with open(os.path.join(out, REPORT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report) + "\n")
    command = [sys.executable, os.path.join(TOOLS, "board_views.py"), "--kicad-cli", kicad_cli, "--resvg", resvg,
               "--board", f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro"]
    for name in CLASSES:
        command += ["--class", name]
    command += ["--out", os.path.join(out, VIEWS)]
    result = subprocess.run(command, cwd=os.path.join(out, DESIGN), capture_output=True, text=True)
    said = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_placement.py"), "--kicad-cli", kicad_cli,
                                 "--resvg", resvg, "--board", f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro",
                                 "--out", os.path.join(out, PLACEMENT)],
                                cwd=os.path.join(out, DESIGN), capture_output=True, text=True)
        said = (said + "\n" + (result.stdout + result.stderr).strip()).strip()
    leftovers(os.path.join(out, DESIGN), files, remove=True)
    stamp = time.time()
    for directory, _, names in os.walk(out, topdown=False):
        for name in names:
            os.utime(os.path.join(directory, name), (stamp, stamp))
        os.utime(directory, (stamp, stamp))
    return result.returncode == 0, said


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
        try:
            settle_layout(seed, args.kicad_cli)
        except board_check.CannotRun as error:
            print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
            return 2
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
            print(f"CANNOT RUN | the views or the placement view could not be rendered from the seeded copy: "
                  f"{board_check.clean(said)}", file=sys.stderr)
            return 2
    with open(seeds, "w", encoding="utf-8") as handle:
        json.dump(seed_list(SEEDS), handle, indent=2)
        handle.write("\n")
    for kind, line in zip(("VIEWS", "PLACEMENT"), [line for line in said.splitlines() if line.startswith("RESULT | ")]):
        print(f"{kind} | {line}")
    print(f"SEEDS | {len(SEEDS)} seeds | {seeds}")
    print(f"RESULT | WRITTEN | {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
