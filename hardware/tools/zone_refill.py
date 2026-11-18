#!/usr/bin/env python3
"""The safe zone refill: every copper zone of a board refilled by KiCad, and nothing else about the board lost to its save.

KiCad's scripting interface refills zones (`ZONE_FILLER`) and saves the board,
but the save rewrites the file as KiCad's own writer sees it, and two of its
changes are damage to a board a design depends on:

  * the board-level `(property "NAME" "value")` lines, which hold the board's own
    declarations, are dropped from the saved file;
  * a zone with no clearance of its own is written with one: `(clearance 0)` when it
    was set to none, KiCad's default otherwise. A reader takes either as declared, and a
    zero is below every spacing a design signs.

This command refills in KiCad's interpreter (named by KICAD_PYTHON, or by
`--kicad-python`), then repairs the saved text: every property line of the board
as given is put back exactly, each zone's `connect_pads` is put back as the board
gave it where it carried a clearance, and a clearance the board did not give,
including KiCad's zero, is never left in the output. The refilled copper is whatever KiCad's fill computes. A board with no
zones is written unchanged, since a refill has nothing to do.

    zone_refill.py --board B.kicad_pcb --output OUT.kicad_pcb [--kicad-python PATH] [--format text|json]

The output may be the board itself. Exit status: 0 refilled, 1 refused or the
board cannot be read, 2 when the refill cannot run, for example because
KICAD_PYTHON is unset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import List, Optional, Tuple

if "--worker" not in sys.argv[1:2]:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --- The worker: runs in KiCad's interpreter, imports nothing but pcbnew -----------------


def worker(board: str, saved: str) -> dict:
    import pcbnew

    try:
        loaded = pcbnew.LoadBoard(board)
    except Exception as error:  # noqa: BLE001 - whatever KiCad raises is the board's reason
        return {"error": f"KiCad cannot load the board ({error})"}
    zones = [zone for zone in loaded.Zones() if not zone.GetIsRuleArea()]
    pcbnew.ZONE_FILLER(loaded).Fill(loaded.Zones())
    pcbnew.SaveBoard(saved, loaded)
    return {"zones": len(zones)}


if __name__ == "__main__" and sys.argv[1:2] == ["--worker"]:
    print(json.dumps(worker(sys.argv[2], sys.argv[3])))
    sys.exit(0)


import kicad_scripting  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402
from board_check import CannotRun  # noqa: E402
from board_geometry import Unreadable  # noqa: E402


# --- Repairing the saved text ----------------------------------------------------------------


def top_forms(text: str):
    """Every top-level form of a layout, each as (form, start, end) offsets in `text`."""
    start, end = text.index("("), text.rindex(")") + 1
    return locked_copper.forms_within(text, start, end)


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        tree = sexpr.parse_one(text)
    except (OSError, UnicodeDecodeError, sexpr.SexprError) as error:
        raise Unreadable(f"the board {path} cannot be read ({error})") from error
    if sexpr.head(tree) != "kicad_pcb":
        raise Unreadable(f"{path} is not a KiCad layout: it begins ({sexpr.head(tree) or '?'} ...), not (kicad_pcb ...)")
    return text


def is_property(form) -> bool:
    return sexpr.head(form) == "property" and len(form) == 3


def zone_label(form, index: int) -> str:
    name = sexpr.child(form, "name")
    uuid = sexpr.child(form, "uuid")
    return str(name[1]) if name and len(name) > 1 and name[1] else (str(uuid[1]) if uuid and len(uuid) > 1 else f"zone {index + 1}")


def zero(value) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def clearance_of(form) -> Optional[list]:
    pads = sexpr.child(form, "connect_pads")
    return sexpr.child(pads, "clearance") if pads is not None else None


def repaired(original: str, saved: str) -> Tuple[str, List[str], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """The saved board's text with the original's property lines and zone clearances back and no zero clearance.

    Returns (text, property names kept, [(zone, clearance text)] kept, [(zone, why)] clearances dropped).
    """
    was, now = top_forms(original), top_forms(saved)
    properties = [(form, start, end) for form, start, end in was if is_property(form)]
    edits: List[Tuple[int, int, str]] = []
    # Property lines: every one the saved file carries goes, every one the original carried comes back, in the
    # original's place -- before the first top-level form that followed them there.
    for form, start, end in now:
        if is_property(form):
            edits.append((gap_start(saved, start), end, ""))
    if properties:
        after = next((form for form, start, _ in was if start > properties[-1][1] and not is_property(form)), None)
        target = next((start for form, start, _ in now if after is not None and sexpr.head(form) == sexpr.head(after)
                       and not is_property(form)), None)
        position = gap_start(saved, target) if target is not None else saved.rstrip().rindex(")")
        block = "".join(original[gap_start(original, start):end] for _, start, end in properties)
        edits.append((position, position, block))
    kept: List[Tuple[str, str]] = []
    dropped: List[Tuple[str, str]] = []
    was_zones = [item for item in was if sexpr.head(item[0]) == "zone"]
    now_zones = [item for item in now if sexpr.head(item[0]) == "zone"]
    by_uuid = {str(sexpr.child(form, "uuid")[1]): (form, start, end) for form, start, end in was_zones
               if sexpr.child(form, "uuid") and len(sexpr.child(form, "uuid")) > 1}
    for index, (form, start, end) in enumerate(now_zones):
        uuid = sexpr.child(form, "uuid")
        match = by_uuid.get(str(uuid[1])) if uuid and len(uuid) > 1 else None
        if match is None and index < len(was_zones) and len(was_zones) == len(now_zones):
            match = was_zones[index]
        label = zone_label(form, index)
        pads = sexpr.child(form, "connect_pads")
        if pads is None:
            continue
        parts = [(part, first, last) for part, first, last in locked_copper.forms_within(saved, start, end)
                 if sexpr.head(part) == "connect_pads"]
        part, first, last = parts[0]
        before = clearance_of(match[0]) if match else None
        if before is not None and len(before) > 1 and not zero(before[1]):
            given = [(p, f, l) for p, f, l in locked_copper.forms_within(original, match[1], match[2])
                     if sexpr.head(p) == "connect_pads"][0]
            edits.append((first, last, original[given[1]:given[2]]))
            kept.append((label, f"{before[1]} mm"))
            continue
        cleared = sexpr.child(pads, "clearance")
        if cleared is None:
            continue
        shown = cleared[1] if len(cleared) > 1 else "?"
        dropped.append((label, "the board gave a zero clearance, which is never written" if before is not None
                        else f"KiCad wrote a clearance of {shown} mm for a zone with none of its own"))
        rest = [p for p in pads[1:] if not (isinstance(p, list) and sexpr.head(p) == "clearance")]
        if rest:
            edits.append((first, last, "(connect_pads " + " ".join(sexpr.dump(p) for p in rest) + ")"))
        else:
            edits.append((gap_start(saved, first), last, ""))
    for first, last, replacement in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        saved = saved[:first] + replacement + saved[last:]
    return saved, [str(form[1]) for form, _, _ in properties], kept, dropped


def gap_start(text: str, start: int) -> int:
    """Where the whitespace before the form at `start` begins, so a form removed takes its own line with it."""
    cursor = start
    while cursor > 0 and text[cursor - 1] in " \t\r\n":
        cursor -= 1
    return cursor


# --- The command ---------------------------------------------------------------------------


def refill(board: str, output: str, kicad_python: Optional[str], out, as_json: bool) -> int:
    findings: List[dict] = []

    def done(result: str, detail: str, status: int) -> int:
        kicad_scripting.emit({"result": result, "detail": detail, "findings": findings, "board": board, "output": output}, out, as_json)
        return status

    editor = locked_copper.open_in_editor(board)
    if editor is not None:
        findings.append({"finding": "OPEN", "item": editor[0], "detail": editor[1]})
        return done("REFUSED", "the board is open in an editor, so nothing was refilled", 1)
    python = kicad_scripting.interpreter(kicad_python)
    try:
        original = read_text(board)
    except Unreadable as error:
        findings.append({"finding": "UNREADABLE", "item": board, "detail": str(error)})
        return done("REFUSED", "the board cannot be read, so nothing was refilled", 1)
    if not any(sexpr.head(form) == "zone" for form, _, _ in top_forms(original)):
        text, zones = original, 0
        kept_properties: List[str] = []
        kept: List[Tuple[str, str]] = []
        dropped: List[Tuple[str, str]] = []
    else:
        with tempfile.TemporaryDirectory(prefix="zone-refill-") as work:
            saved = os.path.join(work, "saved.kicad_pcb")
            reply = kicad_scripting.run_worker(python, os.path.abspath(__file__), [os.path.abspath(board), saved])
            if "error" in reply:
                findings.append({"finding": "UNREADABLE", "item": board, "detail": reply["error"]})
                return done("REFUSED", "KiCad cannot load the board, so nothing was refilled", 1)
            zones = reply["zones"]
            text, kept_properties, kept, dropped = repaired(original, read_text(saved))
    for name in kept_properties:
        findings.append({"finding": "KEPT", "item": f"property {name}", "detail": "the board's property line is as it was"})
    for zone, clearance in kept:
        findings.append({"finding": "KEPT", "item": f"zone {zone}", "detail": f"clearance {clearance} is as it was"})
    for zone, why in dropped:
        findings.append({"finding": "DROPPED", "item": f"zone {zone}", "detail": f"clearance removed: {why}"})
    try:
        scratch = os.path.join(os.path.dirname(os.path.abspath(output)), f".{os.path.basename(output)}.refill")
        with open(scratch, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(scratch, output)
    except OSError as error:
        findings.append({"finding": "UNWRITABLE", "item": output, "detail": f"the board cannot be written there ({error})"})
        return done("REFUSED", "nothing was written", 1)
    return done("REFILLED", f"{zones} zone{'s' if zones != 1 else ''} refilled, {len(kept_properties)} property lines and "
                            f"{len(kept)} zone clearances kept, {len(dropped)} clearances dropped | {output}", 0)


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
    parser.add_argument("--output", required=True, help="where the refilled board is written; may be the board itself")
    parser.add_argument("--kicad-python", default=None,
                        help=f"KiCad's bundled Python (default: the environment variable {kicad_scripting.VARIABLE})")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        return refill(args.board, args.output, args.kicad_python, out, args.format == "json")
    except CannotRun as error:
        return kicad_scripting.cannot_run(error, out, args.format == "json")


if __name__ == "__main__":
    sys.exit(main())
