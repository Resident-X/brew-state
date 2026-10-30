"""Throwaway board designs for the board tooling's tests, written from text in a temporary folder outside the repository.

A design is a layout and its project file in a folder of its own, with a
working folder beside it for whatever a command writes. The layout is built from
footprints and pads written here, on a layer table carrying every layer a board
needs, and the project file is the gate proof design's own with its classes,
mains declaration and design rules set as a test asks.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(TESTS)))
PROOF_PROJECT = os.path.join(REPO, "hardware", "proof", "gate-proof", "gate-proof.kicad_pro")

#: The throwaway board's minimum track width and minimum clearance, and so its views' resolution.
MINIMUM_MM = 0.1

_SCRATCH = []


def require_tools(kicad_cli: str, resvg: str = "") -> None:
    """Stop a module of tests that needs KiCad, and the rasteriser when one is named, if either is missing.

    The module stops with the tool's own account of what is missing and where to get
    it, and a line written as every board command writes it, `CANNOT RUN | ...`, so
    whoever reads the run, a build round's gate included, can tell a missing tool
    from a failing test.
    """
    import board_check
    import board_views

    try:
        board_check.require_kicad(kicad_cli)
        if resvg:
            board_views.require_resvg(resvg)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr, flush=True)
        raise


def require_gerbonara(python: str) -> None:
    """Stop a module of tests that draws exported layers if `python` does not import gerbonara at the exact version.

    The module stops as `require_tools` stops it, with the account of what is
    missing and how to install it, and a `CANNOT RUN | ...` line naming gerbonara.
    """
    import board_check
    import production_seed

    try:
        production_seed.check_gerbonara(python)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr, flush=True)
        raise


def cleanup():
    """Remove every throwaway design's folder."""
    while _SCRATCH:
        _SCRATCH.pop().cleanup()


_UUID = [0]


def uuid() -> str:
    _UUID[0] += 1
    return f'"00000000-0000-4000-8000-{_UUID[0]:012d}"'


def pad(number, x, y, net, pintype, angle=0):
    """A surface-mount pad at (x, y) of its footprint, turned to `angle` on the board, as KiCad writes it."""
    at = f"{x} {y} {angle}" if angle else f"{x} {y}"
    return (f'(pad "{number}" smd roundrect (at {at}) (size 1 0.6) (layers "F.Cu" "F.Mask" "F.Paste") '
            f'(roundrect_rratio 0.25) (net "{net}") (pintype "{pintype}") (uuid {uuid()}))')


def model(path, height=1, hidden=False):
    return (f'(model "{path}"{" (hide yes)" if hidden else ""} (offset (xyz 0 0 0)) (scale (xyz 1 1 {height})) '
            '(rotate (xyz 0 0 0)))')


def footprint(reference, x, y, pads, models=(), attributes="", angle=0, courtyard=(-2.5, -2.5, 2.5, 2.5)):
    """A part at (x, y) turned to `angle`, with its reference on the front silkscreen, a fabrication outline 4 mm
    square and, unless `courtyard` is None, a courtyard of those corners."""
    at = f"{x} {y} {angle}" if angle else f"{x} {y}"
    yard = (f'(fp_rect (start {courtyard[0]} {courtyard[1]}) (end {courtyard[2]} {courtyard[3]}) '
            f'(stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") (uuid {uuid()})) ') if courtyard else ""
    return (f'(footprint "proof:Part" (layer "F.Cu") (uuid {uuid()}) (at {at}) {attributes}'
            f'(property "Reference" "{reference}" (at 0 -3 {angle}) (layer "F.SilkS") (uuid {uuid()}) '
            '(effects (font (size 1 1) (thickness 0.15)))) ' + yard +
            f'(fp_rect (start -2 -2) (end 2 2) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab") '
            f'(uuid {uuid()})) ' + " ".join(list(pads) + list(models)) + ")")


LAYER_TABLE = ['(0 "F.Cu" signal)', '(2 "B.Cu" signal)', '(13 "F.Paste" user)', '(15 "B.Paste" user)',
               '(5 "F.SilkS" user "F.Silkscreen")', '(7 "B.SilkS" user "B.Silkscreen")', '(1 "F.Mask" user)',
               '(3 "B.Mask" user)', '(17 "Dwgs.User" user "User.Drawings")', '(19 "Cmts.User" user "User.Comments")',
               '(25 "Edge.Cuts" user)', '(31 "F.CrtYd" user "F.Courtyard")', '(29 "B.CrtYd" user "B.Courtyard")',
               '(35 "F.Fab" user)', '(33 "B.Fab" user)']

OUTLINE = '(gr_rect (start 0 0) (end 60 40) (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-0000000000e0"))'


def layout(items, layers=None, outline=OUTLINE) -> str:
    """A layout file holding `items` within `outline`, on `layers` or the full layer table."""
    table = "\n".join(f"\t\t{entry}" for entry in (LAYER_TABLE if layers is None else layers))
    body = "".join(f"\t{item}\n" for item in ([outline] if outline else []) + list(items))
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            f'\t(general (thickness 1.6))\n\t(paper "A4")\n\t(layers\n{table}\n\t)\n' + body + ")\n")


def project(classes=("Power", "Ground"), assignments=None, mains="none", rules="default", patterns=()) -> str:
    """A project file defining `classes` beside Default, declaring MAINS as `mains`, with design rules `rules`, and
    assigning nets to classes by name and by `patterns` as well."""
    with open(PROOF_PROJECT, encoding="utf-8") as handle:
        data = json.load(handle)
    settings = data["net_settings"]
    default, template = settings["classes"][0], settings["classes"][1]
    settings["classes"] = [default] + [dict(copy.deepcopy(template), name=name, priority=index)
                                       for index, name in enumerate(classes)]
    settings["netclass_assignments"] = {"+3V3": "Power", "GND": "Ground"} if assignments is None else assignments
    settings["netclass_patterns"] = [{"netclass": netclass, "pattern": pattern} for netclass, pattern in patterns]
    data["text_variables"] = {"MAINS": mains, **({"MAINS_ENTRY": "none"} if mains == "present" else {})}
    data["board"]["design_settings"]["rules"] = (
        {"min_track_width": MINIMUM_MM, "min_clearance": MINIMUM_MM} if rules == "default" else rules)
    return json.dumps(data, indent=1)


class Design:
    """A throwaway board and its project in their own folder, with a working folder `out` outside it."""

    def __init__(self, board_text: str, project_text: str, prefix: str = "board-test-", out: str = "views"):
        scratch = tempfile.TemporaryDirectory(prefix=prefix)
        _SCRATCH.append(scratch)
        self.root = scratch.name
        self.folder = os.path.join(self.root, "design")
        os.makedirs(self.folder)
        self.board = os.path.join(self.folder, "proof.kicad_pcb")
        self.project = os.path.join(self.folder, "proof.kicad_pro")
        self.out = os.path.join(self.root, out)
        self.write("proof.kicad_pcb", board_text)
        self.write("proof.kicad_pro", project_text)

    def write(self, name: str, text: str) -> str:
        """A file of the design, by its path inside the design's folder, written with `text`; its full path."""
        path = os.path.join(self.folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path


def hex_rgb(colour: str):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def partly(found, colour: str, background: str) -> bool:
    """Whether a pixel is the colour over the background, at least half covered: a thin line's antialiased pixels
    carry the colour in proportion to how much of them it covers."""
    target, under = hex_rgb(colour), hex_rgb(background)
    spread = [t - b for t, b in zip(target, under)]
    cover = max((f - b) / s for f, b, s in zip(found, under, spread) if abs(s) > 60)
    return cover >= 0.5 and all(abs(f - (b + cover * s)) <= 16 for f, b, s in zip(found, under, spread))
