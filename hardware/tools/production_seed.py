#!/usr/bin/env python3
"""Seed known defects into a board's production files, and assemble a folder to check them blind.

The method's ordering step has a follower compare a board's production files with
the assembler's preview and look at every rendered fabrication layer before the
board is paid for. What judges seeded files is a session following that step, not
a program, so this command does everything up to the judgement and nothing after
it. It exports the committed layout review proof design's production files,
hardware/proof/review-proof, with the commands the step names, and seeds them:

- the placement file, converted from KiCad's position export as the step converts
  it, gets a part rotated, a polarised part reversed, an integrated circuit's
  first pin turned and a part moved;
- the parts list gets a position's catalogue number replaced by another part's;
- the fabrication layers are exported from an edited copy of the board, in which
  a layer is missing content, shifted and mirrored.

A seed that does not land, whose file or row is the same after it as before, is
refused, as is a copy the exports cannot be made from.

It writes a production-files folder holding only what the step gives a follower:
the seeded placement file, parts list, Gerber and drill files, the image of every
fabrication layer and of the drill file drawn from those files, the unseeded
design's own rendered views and placement view, which stand in for the assembler's
preview (the preview needs an account and an upload, which a read-only session
cannot make), the design's parts specification record, the method as written, the
hardware readme and the manufacturer's record. Nothing in it names the repository
or a seed, and every file in it carries one time. The design and the documents are
taken as the repository's last commit holds them, and nothing under the design's
own folder changes. The seed list, each seed's identifier, the area it covers, the
part or layer and what it is, is written apart from the folder, to a path the
caller names, and is refused inside the folder or inside a design's folder.

    production_seed.py --seeds <seed list file> --out <production-files folder> [--kicad-cli ...] [--resvg ...] [--gerbonara-python ...]
    production_seed.py --print-prompt

--print-prompt prints the fixed prompt a blind follow is started with. It names
nothing seeded.

Each step is reported on one line, a RESULT line comes last, and the exit status
is 0 when the folder and the seed list are written, 1 when the command is
refused, and 2 when it cannot run, for example because a tool is missing.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import board_views  # noqa: E402
import production_files  # noqa: E402
import review_seed  # noqa: E402
import sexpr  # noqa: E402

REPO = review_seed.REPO
DESIGN = review_seed.DESIGN
NAME = review_seed.NAME
CLASSES = review_seed.CLASSES
#: What the ordering step gives a follower besides the design's exports and views, by path from the repository's root.
DOCUMENTS = ("docs/board-design-method.md", "docs/board-manufacturer-jlcpcb.md", "hardware/README.md")
#: The design's record of each position's catalogue part, which the step compares the parts list with, by path in the design's folder.
RECORD = "parts-specification.yaml"
PRODUCTION = "production"
GERBERS = "gerbers"
LAYERS = "layers"
PLACEMENT_FILE = "placement.csv"
PARTS_FILE = "parts-list.csv"
VIEWS = review_seed.VIEWS
PLACEMENT = review_seed.PLACEMENT

#: The commands the ordering step names, as arguments of kicad-cli, with <name> where the board or a folder goes. The
#: method states each one, and the tests hold the two together.
COPPER = "F.Cu,In1.Cu,In2.Cu,B.Cu"
POSITIONS_COMMAND = ["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-dnp",
                     "--output", "<positions>", "<board>"]
PARTS_COMMAND = ["sch", "export", "bom", "--fields", "Reference,Value,Footprint,LCSC",
                 "--labels", "Designator,Comment,Footprint,LCSC", "--group-by", "LCSC", "--exclude-dnp",
                 "--output", "<parts list>", "<schematic>"]
GERBERS_COMMAND = ["pcb", "export", "gerbers", "--layers", f"{COPPER},F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts",
                   "--output", "<folder>/", "<board>"]
DRILL_COMMAND = ["pcb", "export", "drill", "--output", "<folder>/", "<board>"]

PROMPT = """You are about to order a printed circuit board and its assembly, and must check its production files first. \
You did not design the board, and you have no notes from whoever did. Work only from the files in this folder.

Follow the "Ordering" section of docs/board-design-method.md, as written, for the board design in \
hardware/proof/review-proof/. The files it names have been exported and prepared for you:
- the placement file, converted as the step converts it, is production/placement.csv, and the parts list is \
production/parts-list.csv; the board's record of each position's catalogue part is \
hardware/proof/review-proof/parts-specification.yaml;
- the exported Gerber and drill files are in production/gerbers/, and the image of every fabrication layer and of \
the drill file, drawn from those files by the step's render command, is in production/layers/, whose index.txt lists \
every image and the frame all of them share;
- you cannot upload files to the assembler, so its preview is replaced by the board's own rendered placement and \
three-dimensional views, which show every part at its intended position, rotation and polarity: placement/ and the \
assembly and three-dimensional images in views/. The design's other rendered views, one for each of its layers, are in \
views/ as well; views/index.txt lists every image with its caption fields (hardware/README.md, section "The layout \
review views", describes them, and section "The placement view" the placement view);
- the assembler's own record of what it accepts, including its placement file and the correction it makes to a \
rotation, is docs/board-manufacturer-jlcpcb.md.

You cannot run commands, render further views or commit anything. Where the step would have you upload files or run a \
command, take what is prepared here in its place, and where a judgement would need something that is not here, give it \
the verdict the step gives for that case and say what it needs. Write "the files in this folder" where the step asks \
for the commit the check judges.

Judge every placed part and every fabrication layer, the drill file and the outline, open every image you rely on, and \
read board coordinates from the captions and the index.

Return the production-files check record as your answer, in Markdown, exactly as the method's step lays it out: its \
opening lines, the table with one row for every placed part, the verdict for every fabrication layer, the drill file \
and the outline, and a finding for everything that differs. Return nothing but the record.
"""


class Refused(Exception):
    """The command will not go on, for the reason given."""


class Fault(NamedTuple):
    """One seeded defect: its identifier, the area it covers, the part or layer, what it is and how it is made.

    A placement or parts seed edits the rows of the file it names, by designator, and lands when its
    row differs afterwards. A layer seed edits a copy of the board that the layers are exported from,
    and lands when the exported files it names, by the ending of their names, differ from the unseeded
    export's.
    """
    ident: str
    area: str
    target: str
    description: str
    kind: str
    edit: Callable
    files: Tuple[str, ...] = ()
    designator: str = ""


# --- The seeds --------------------------------------------------------------------------------


def turned(designator: str, degrees: float) -> Callable[[Dict[str, List[str]]], None]:
    def edit(rows: Dict[str, List[str]]) -> None:
        row = rows[designator]
        row[4] = production_files.figure((float(row[4]) + degrees) % 360)
    return edit


def moved(designator: str, dx: float, dy: float) -> Callable[[Dict[str, List[str]]], None]:
    def edit(rows: Dict[str, List[str]]) -> None:
        row = rows[designator]
        row[1], row[2] = production_files.figure(float(row[1]) + dx), production_files.figure(float(row[2]) + dy)
    return edit


def number_of(designator: str, other: str) -> Callable[[Dict[str, Dict[str, str]]], None]:
    """`designator`'s catalogue number replaced by `other`'s."""
    def edit(rows: Dict[str, Dict[str, str]]) -> None:
        rows[designator]["LCSC"] = rows[other]["LCSC"]
    return edit


def footprint_of(tree: list, reference: str) -> list:
    return board_prove.footprint(tree, reference)


def mask_openings_missing(reference: str) -> Callable[[list], None]:
    """The solder mask openings of every pad of `reference` taken away, so the mask covers its pads."""
    def edit(tree: list) -> None:
        for pad in sexpr.children(footprint_of(tree, reference), "pad"):
            layers = sexpr.child(pad, "layers")
            layers[:] = [name for name in layers if name not in ("*.Mask", "F.Mask", "B.Mask")]
    return edit


def hole_moved(reference: str, dx: float, dy: float) -> Callable[[list], None]:
    """The footprint `reference` moved by (dx, dy) mm, a mounting hole with it."""
    def edit(tree: list) -> None:
        at = sexpr.child(footprint_of(tree, reference), "at")
        at[1:3] = [review_seed.mm(float(at[1]) + dx), review_seed.mm(float(at[2]) + dy)]
    return edit


def legend_mirrored(tree: list) -> None:
    """Every text on the front silkscreen, each footprint's reference and value included, drawn mirrored."""
    def flag(node: list) -> None:
        layer = sexpr.child(node, "layer")
        effects = sexpr.child(node, "effects")
        if layer is None or effects is None or layer[1] != "F.SilkS":
            return
        justify = sexpr.child(effects, "justify")
        if justify is None:
            effects.append(["justify", "mirror"])
        elif "mirror" not in justify:
            justify.append("mirror")
    for node in sexpr.children(tree, "gr_text"):
        flag(node)
    for footprint in sexpr.children(tree, "footprint"):
        for node in sexpr.children(footprint, "property") + sexpr.children(footprint, "fp_text"):
            flag(node)


SEEDS: List[Fault] = [
    Fault("S1", "placement file: rotation", "U3", "U3, the small-outline amplifier, turned 90 degrees in the placement file "
          "from the 0 its footprint is placed at on the board", "placement", turned("U3", 90), designator="U3"),
    Fault("S2", "placement file: polarity", "D1", "D1, the polarised suppressor diode, reversed in the placement file, "
          "turned 180 degrees from the board's placement", "placement", turned("D1", 180), designator="D1"),
    Fault("S3", "placement file: first-pin orientation", "U4", "U4, the controller in a leadless package with a pin-one "
          "marker, turned a quarter turn in the placement file from the board's placement", "placement", turned("U4", 90),
          designator="U4"),
    Fault("S4", "placement file: position", "R4", "R4, a resistor, moved 4 mm along X in the placement file from where "
          "the board places it", "placement", moved("R4", 4, 0), designator="R4"),
    Fault("S5", "parts list: catalogue part", "R2", "R2's catalogue number in the parts list replaced by R3's, a different "
          "part, the parts specification record mapping R2 to its own", "parts", number_of("R2", "R3"), designator="R2"),
    Fault("S6", "fabrication layer: missing content", "F.Mask, B.Mask", "the solder mask on both sides without its openings "
          "over the mains terminal block J1's through-hole pads, so the mask covers them", "layer",
          mask_openings_missing("J1"), ("F_Mask.gts", "B_Mask.gbs")),
    Fault("S7", "fabrication layer: shifted content", "drill, F.Mask, B.Mask", "the mounting hole H1 moved 4 mm along X and Y "
          "in the board the layers are exported from, so its drilled hole and its mask openings on both sides stand 4 mm "
          "from the design's", "layer", hole_moved("H1", 4, 4), (".drl", "F_Mask.gts", "B_Mask.gbs")),
    Fault("S8", "fabrication layer: mirrored content", "F.SilkS", "every text on the front legend, the reference "
          "designators, exported mirrored", "layer", legend_mirrored, ("F_Silkscreen.gto",)),
]


# --- Exporting ----------------------------------------------------------------------------------


def kicad(kicad_cli: str, arguments: List[str], cwd: str, what: str) -> None:
    result = subprocess.run([kicad_cli] + arguments, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise board_check.CannotRun(f"kicad-cli could not export {what}: {board_check.clean((result.stdout + result.stderr).strip())}")


def command(template: List[str], **given: str) -> List[str]:
    """`template` with each <name> in it replaced by what `given` holds under that name (spaces in a name written as _)."""
    values = {f"<{name.replace('_', ' ')}>": value for name, value in given.items()}
    return [values.get(argument, argument.replace("<folder>", given.get("folder", ""))) for argument in template]


def export_fabrication(seed: board_prove.Seed, kicad_cli: str, folder: str) -> None:
    os.makedirs(folder, exist_ok=True)
    board = seed.path(".kicad_pcb")
    kicad(kicad_cli, command(GERBERS_COMMAND, folder=folder, board=board), seed.design, "the Gerber layers")
    kicad(kicad_cli, command(DRILL_COMMAND, folder=folder, board=board), seed.design, "the drill file")


def export_parts(seed: board_prove.Seed, kicad_cli: str, folder: str) -> Tuple[List[List[str]], List[Dict[str, str]]]:
    """The converted placement file's rows and the parts list's rows, as the step's commands write them."""
    os.makedirs(folder, exist_ok=True)
    positions, parts = os.path.join(folder, "positions.csv"), os.path.join(folder, "parts.csv")
    kicad(kicad_cli, command(POSITIONS_COMMAND, positions=positions, board=seed.path(".kicad_pcb")), seed.design,
          "the placement file")
    kicad(kicad_cli, command(PARTS_COMMAND, parts_list=parts, schematic=seed.path(".kicad_sch")), seed.design,
          "the parts list")
    try:
        rows = production_files.placement_rows(production_files.read_positions(positions))
    except production_files.Refused as error:
        raise board_check.CannotRun(f"the position export of the design cannot be converted: {error}") from None
    with open(parts, encoding="utf-8", newline="") as handle:
        listed = list(csv.DictReader(handle))
    if not listed:
        raise board_check.CannotRun("the design's parts list is empty")
    return rows, listed


def stable(path: str) -> bytes:
    """A file's bytes without the lines that record when it was written (a Gerber file's creation date and creator comment, a drill file's header), which differ between two exports of one board."""
    with open(path, "rb") as handle:
        lines = handle.read().splitlines()
    return b"\n".join(line for line in lines if b"CreationDate" not in line
                     and not line.startswith((b"; DRILL file ", b"G04 Created by KiCad")))


def fabrication_files(folder: str) -> Dict[str, bytes]:
    return {name: stable(os.path.join(folder, name)) for name in sorted(os.listdir(folder))}


def differing(clean: Dict[str, bytes], seeded: Dict[str, bytes], endings: Tuple[str, ...]) -> List[str]:
    return [name for name in clean if name.endswith(endings) and seeded.get(name) != clean[name]]


def render_csv(header: List[str], rows: List[List[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


# --- The command --------------------------------------------------------------------------------


def refusals(seeds: str, out: str, repo: str = REPO) -> List[str]:
    """Why the seed list or the production-files folder cannot be written where they are asked to go."""
    found = []
    if review_seed.inside(out, repo):
        found.append(f"the production-files folder {out} is inside the repository; a follower working there could read "
                     "the proof design as committed and the seeding command, so put it outside")
    if os.path.isfile(out):
        found.append(f"the production-files folder {out} is a file")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"the production-files folder {out} already holds files; give a new or empty folder")
    if review_seed.inside(seeds, out):
        found.append(f"the seed list {seeds} is inside the production-files folder, where the follower would read it")
    holder = review_seed.design_folder(seeds)
    if holder is not None:
        found.append(f"the seed list {seeds} is inside the design folder {holder}; write it outside every design's folder")
    if os.path.isdir(seeds):
        found.append(f"the seed list {seeds} is a folder")
    return found


def seed_list(seeds: List[Fault]) -> dict:
    return {"design": DESIGN, "seeds": [{"id": seed.ident, "area": seed.area, "target": seed.target,
                                         "description": seed.description} for seed in seeds]}


def check_gerbonara(python: str) -> None:
    """Stop unless `python` imports gerbonara at the exact version the drawings are made with."""
    try:
        result = subprocess.run([python, "-c", "import gerbonara; print(gerbonara.__version__)"], capture_output=True,
                                text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise board_check.CannotRun(f"the Python '{python}' for gerbonara could not be run ({error}). {production_files.INSTALL}") from None
    found = result.stdout.strip()
    if result.returncode != 0:
        raise board_check.CannotRun(f"gerbonara could not be imported by '{python}'. {production_files.INSTALL}")
    if found != production_files.GERBONARA:
        raise board_check.CannotRun(f"gerbonara {found} is installed for '{python}', not the version "
                                    f"{production_files.GERBONARA} the drawings are made with. {production_files.INSTALL}")


def landed(seeds: List[Fault], placement, parts, kicad_cli: str, scratch: str, clean_files: Dict[str, bytes]):
    """The seeded rows of both files, and the layer exports; refuses a seed that changed nothing."""
    edited_placement = {row[0]: list(row) for row in placement}
    edited_parts = {row["Designator"]: dict(row) for row in parts}
    for seed in seeds:
        if seed.kind == "placement":
            rows, key = edited_placement, seed.designator
        elif seed.kind == "parts":
            rows, key = edited_parts, seed.designator
        else:
            continue
        if key not in rows:
            raise Refused(f"seed {seed.ident} names {key}, which the exported files do not hold")
        before = json.dumps(rows[key])
        seed.edit(rows)
        if json.dumps(rows[key]) == before:
            raise Refused(f"seed {seed.ident} ({seed.description}) did not land: {key}'s row is unchanged")
    for seed in seeds:
        if seed.kind != "layer":
            continue
        alone = board_prove.prepare(os.path.join(scratch, f"alone-{seed.ident}"), DESIGN, NAME)
        alone.layout(seed.edit)
        export_fabrication(alone, kicad_cli, os.path.join(scratch, f"alone-{seed.ident}-files"))
        changed = differing(clean_files, fabrication_files(os.path.join(scratch, f"alone-{seed.ident}-files")), seed.files)
        if len(changed) != len(seed.files) or not changed:
            raise Refused(f"seed {seed.ident} ({seed.description}) did not land: the exported file ending "
                          f"{', '.join(seed.files)} is the same as the unseeded design's")
    return edited_placement, edited_parts


def documents() -> Dict[str, bytes]:
    """What the ordering step gives a follower besides the design, as the repository's last commit holds it."""
    found = {}
    for document in DOCUMENTS:
        held = board_prove.committed(document)
        if held is None:
            with open(os.path.join(REPO, document), "rb") as handle:
                held = {document: handle.read()}
        found[document] = held[document]
    return found


def render_views(clean: board_prove.Seed, out: str, kicad_cli: str, resvg: str) -> Tuple[bool, str]:
    """The unseeded design's views and placement view, rendered from its copy into the folder, with the copy's own path taken out."""
    command_line = [sys.executable, os.path.join(TOOLS, "board_views.py"), "--kicad-cli", kicad_cli, "--resvg", resvg,
                    "--board", f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro"]
    for name in CLASSES:
        command_line += ["--class", name]
    result = subprocess.run(command_line + ["--out", os.path.join(out, VIEWS)], cwd=clean.design, capture_output=True, text=True)
    said = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_placement.py"), "--kicad-cli", kicad_cli,
                                 "--resvg", resvg, "--board", f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro",
                                 "--out", os.path.join(out, PLACEMENT)], cwd=clean.design, capture_output=True, text=True)
        said = (said + "\n" + (result.stdout + result.stderr).strip()).strip()
    for folder in (VIEWS, PLACEMENT):
        base = os.path.join(out, folder)
        for name in os.listdir(base) if os.path.isdir(base) else []:
            if name.endswith((".txt", ".json")):
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                for root in (os.path.realpath(clean.root), clean.root):
                    text = text.replace(root + os.sep, "")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
    return result.returncode == 0, said


def assemble(clean: board_prove.Seed, out: str, placement: Dict[str, List[str]], order: List[str], parts: List[Dict[str, str]],
             fields: List[str], fabrication: str, kicad_cli: str, resvg: str, gerbonara_python: str) -> Tuple[bool, str]:
    """The production-files folder written; whether the views and the layer images were rendered, and their reports."""
    production = os.path.join(out, PRODUCTION)
    os.makedirs(production)
    with open(os.path.join(production, PLACEMENT_FILE), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_csv(production_files.PLACEMENT_COLUMNS, [placement[key] for key in order]))
    with open(os.path.join(production, PARTS_FILE), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_csv(fields, [[row[field] for field in fields] for row in parts]))
    shutil.copytree(fabrication, os.path.join(production, GERBERS))
    record = os.path.join(out, DESIGN, RECORD)
    os.makedirs(os.path.dirname(record), exist_ok=True)
    shutil.copyfile(clean.path(RECORD), record)
    for document, content in documents().items():
        os.makedirs(os.path.dirname(os.path.join(out, document)), exist_ok=True)
        with open(os.path.join(out, document), "wb") as handle:
            handle.write(content)
    drawn = subprocess.run([gerbonara_python, os.path.join(TOOLS, "production_files.py"), "render", "--gerbers",
                            os.path.join(production, GERBERS), "--out", os.path.join(production, LAYERS), "--resvg", resvg],
                           capture_output=True, text=True)
    said = (drawn.stdout + drawn.stderr).strip()
    if drawn.returncode != 0:
        return False, said
    rendered, views = render_views(clean, out, kicad_cli, resvg)
    stamp = time.time()
    for directory, _, names in os.walk(out, topdown=False):
        for name in names:
            os.utime(os.path.join(directory, name), (stamp, stamp))
        os.utime(directory, (stamp, stamp))
    return rendered, (said + "\n" + views).strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seeds", help="where to write the seed list, outside the production-files folder and every design's folder")
    parser.add_argument("--out", help="the production-files folder to write, new or empty, outside the repository")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg program the images are drawn with (default: resvg on the search path)")
    parser.add_argument("--gerbonara-python", default="python3",
                        help=f"the Python that imports gerbonara {production_files.GERBONARA}, which draws the layers (default: python3 on the search path)")
    parser.add_argument("--print-prompt", action="store_true", help="print the fixed prompt a blind follow is started with, and stop")
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
        board_views.require_resvg(args.resvg)
        check_gerbonara(args.gerbonara_python)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="production-seed-") as scratch:
        try:
            clean = board_prove.prepare(os.path.join(scratch, "clean"), DESIGN, NAME)
            placement, parts = export_parts(clean, args.kicad_cli, os.path.join(scratch, "clean-parts"))
            export_fabrication(clean, args.kicad_cli, os.path.join(scratch, "clean-files"))
            clean_files = fabrication_files(os.path.join(scratch, "clean-files"))
            order = [row[0] for row in placement]
            edited_placement, edited_parts = landed(SEEDS, placement, parts, args.kicad_cli, scratch, clean_files)
            edited = board_prove.prepare(os.path.join(scratch, "edited"), DESIGN, NAME)
            for seed in SEEDS:
                if seed.kind == "layer":
                    edited.layout(seed.edit)
            export_fabrication(edited, args.kicad_cli, os.path.join(scratch, "edited-files"))
        except Refused as error:
            print(f"REFUSED | {board_check.clean(str(error))}")
            print("RESULT | REFUSED | nothing was written")
            return 1
        except board_check.CannotRun as error:
            print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
            return 2
        for seed in SEEDS:
            print(f"SEED | {seed.ident} | landed | {seed.target}")
        os.makedirs(out, exist_ok=True)
        fields = list(parts[0].keys())
        rendered, said = assemble(clean, out, edited_placement, order, list(edited_parts.values()), fields,
                                  os.path.join(scratch, "edited-files"), args.kicad_cli, args.resvg, args.gerbonara_python)
        if not rendered:
            shutil.rmtree(out, ignore_errors=True)
            print(f"CANNOT RUN | the layer images, the views or the placement view could not be rendered: "
                  f"{board_check.clean(said)}", file=sys.stderr)
            return 2
    with open(seeds, "w", encoding="utf-8") as handle:
        json.dump(seed_list(SEEDS), handle, indent=2)
        handle.write("\n")
    results = [line for line in said.splitlines() if line.startswith("RESULT | ")]
    for kind, line in zip(("LAYERS", "VIEWS", "PLACEMENT"), results):
        print(f"{kind} | {line}")
    print(f"SEEDS | {len(SEEDS)} seeds | {seeds}")
    print(f"RESULT | WRITTEN | {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
