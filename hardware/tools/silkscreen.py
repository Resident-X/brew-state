#!/usr/bin/env python3
"""The silkscreen command: rebuilds a board's whole silkscreen by script, and writes it only if nothing else changed.

    silkscreen.py build --board IN.kicad_pcb --out OUT.kicad_pcb [--table silkscreen.yaml] [--work FOLDER]
                        [--kicad-python PATH] [--resolution MM] [--format text|json]
    silkscreen.py prove --input A.kicad_pcb --output B.kicad_pcb [--format text|json]
    silkscreen.py check --board B.kicad_pcb [--kicad-python PATH] [--work FOLDER] [--format text|json]

`build` reads the board in KiCad's interpreter (KICAD_PYTHON, or `--kicad-python`),
places every part's reference label, the connector, tab, fuse and test-point
names, the pin-1 markings, the warning legends and the fixed texts the board's table
asks for, and edits the board's text. Before it writes, it proves that the board it
would write differs from the input in nothing but silkscreen: a part's Reference
(its position, layer and size), the free graphics and texts on F.SilkS and
B.SilkS, and graphics a footprint draws there. If anything else differs, it refuses,
names what differs, writes nothing and leaves the input as it was. A reference
that finds no free place is not drawn: its Reference goes to the fab layer and the
part is listed as unplaced. The same board and table always give the same bytes.

`prove` runs only that proof between two boards. `check` measures a board's silkscreen
against the fabricator's limits (clearances, keep-ins, height and stroke, angle,
run-together text, ambiguous owner) and exits 1 when any measure is broken.

`build` and `check` need numpy, shapely and Pillow beside KiCad's interpreter, and every
subcommand, `prove` included, needs PyYAML for the table; each stops naming whichever
is missing.

Exit status: 0 when the board is written (`build`), proved silkscreen-only (`prove`) or
clean (`check`); 1 when the command refuses its input, the proof fails or a measure is
broken; 2 when it cannot run, for example because KICAD_PYTHON is unset or a package
is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kicad_scripting  # noqa: E402
import silkscreen_python  # noqa: E402
import silkscreen_patch  # noqa: E402
import silkscreen_table  # noqa: E402
from board_check import CannotRun  # noqa: E402

KICAD_SIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "silkscreen_kicad.py")
DEFAULT_RESOLUTION = 0.025
SOLVER_ITERATIONS = 2500


def read_board(path: str) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot be read ({error})") from error


def make_board(text: str, plan: dict, footprints: dict) -> str:
    """The board the plan makes of `text`: the one step that edits a board, and the one the proof judges."""
    return silkscreen_patch.apply_plan(text, plan, footprints)


def _report(result: str, detail: str, findings: list, **extra) -> dict:
    report = {"result": result, "detail": detail, "findings": findings}
    report.update(extra)
    return report


def _engine():
    """The placement modules, or CannotRun naming the missing package."""
    import silkscreen_engine
    silkscreen_engine.check_packages()
    import silkscreen_check
    import silkscreen_place
    return silkscreen_engine, silkscreen_place, silkscreen_check


def _ink_measurer(python: str):
    def measure(requests, path):
        folder = os.path.dirname(path)
        asked, produced = os.path.join(folder, "ink-request.json"), os.path.join(folder, "ink-new.json")
        with open(asked, "w", encoding="utf-8") as handle:
            json.dump(requests, handle)
        reply = kicad_scripting.run_worker(python, KICAD_SIDE, ["measure", asked, produced])
        if "error" in reply:
            raise CannotRun(f"KiCad could not measure the text ({reply['error']})")
        known = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                known = json.load(handle)
        with open(produced, encoding="utf-8") as handle:
            known.update(json.load(handle))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(known, handle, sort_keys=True)
    return measure


def extract(python: str, board: str, work: str, name: str) -> dict:
    target = os.path.join(work, name)
    reply = kicad_scripting.run_worker(python, KICAD_SIDE, ["extract", os.path.abspath(board), target])
    if "error" in reply:
        raise ValueError(reply["error"])
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def _checks(check_module, data: dict) -> dict:
    found = check_module.check(data)
    return {cls: found[cls] for cls in check_module.CLASSES if cls in found}


def _check_findings(checks: dict) -> list:
    out = []
    for cls, rows in checks.items():
        for row in rows:
            out.append({"finding": "CHECK", "item": f"{cls}: {row['item']}",
                        "detail": f"{row['obstacle']}, {row['distance']} mm, {row['side']} side at ({row['x']}, {row['y']}) {row['note']}".strip()})
    return out


def build(board: str, out_path: str, table_path: Optional[str], work: Optional[str], kicad_python: Optional[str], resolution: float,
          out, as_json: bool) -> int:
    def done(result, detail, findings, status, **extra):
        kicad_scripting.emit(_report(result, detail, findings, **extra), out, as_json)
        return status

    refusals = []
    if os.path.exists(out_path) and os.path.exists(board) and os.path.samefile(out_path, board):
        refusals.append({"finding": "REFUSED", "item": out_path, "detail": "the output is the input board; give another path so the input stays untouched"})
    try:
        text = read_board(board)
    except ValueError as error:
        refusals.append({"finding": "UNREADABLE", "item": board, "detail": str(error)})
        text = ""
    table = None
    try:
        table = silkscreen_table.load(read_board(table_path) if table_path else "")
    except (silkscreen_table.TableError, ValueError) as error:
        refusals.append({"finding": "REFUSED", "item": table_path or "table", "detail": str(error)})
    if resolution <= 0:
        refusals.append({"finding": "REFUSED", "item": "--resolution", "detail": f"{resolution} is not above zero; give the raster step in mm"})
    if refusals:
        return done("REFUSED", "the inputs cannot be used, so nothing was placed or written", refusals, 1, written=None)
    python = kicad_scripting.interpreter(kicad_python)
    _engine_module, place_module, check_module = _engine()
    scratch = None
    if work:
        os.makedirs(work, exist_ok=True)
        folder = work
    else:
        scratch = tempfile.TemporaryDirectory(prefix="silkscreen-")
        folder = scratch.name
    try:
        try:
            data = extract(python, board, folder, "in.json")
        except ValueError as error:
            return done("REFUSED", "KiCad cannot load the board, so nothing was placed or written",
                        [{"finding": "UNREADABLE", "item": board, "detail": str(error)}], 1, written=None)
        placement = place_module.Placement(data, table, place_module.Ink(os.path.join(folder, "ink.json"), _ink_measurer(python)),
                                           res=resolution, solver_iterations=SOLVER_ITERATIONS)
        plan = placement.run()
        with open(os.path.join(folder, "plan.json"), "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=1, sort_keys=True)
        try:
            candidate = make_board(text, plan, data["fps"])
        except (KeyError, ValueError) as error:
            return done("REFUSED", "the board's text could not be edited, so nothing was written",
                        [{"finding": "UNREADABLE", "item": board, "detail": f"{error}"}], 1, written=None)
        differences = silkscreen_patch.difference(text, candidate)
        if differences:
            return done("REFUSED", f"the board to write differs from the input outside silkscreen in {len(differences)} "
                                   f"place{'s' if len(differences) != 1 else ''}, so nothing was written and the input is untouched",
                        [{"finding": "DIFFERS", "item": d, "detail": "changed outside the silkscreen"} for d in differences], 1, written=None)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        temporary = out_path + ".partial"
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(candidate)
        os.replace(temporary, out_path)
        stem_in, stem_out = os.path.splitext(board)[0], os.path.splitext(out_path)[0]
        for extension in (".kicad_pro", ".kicad_dru"):
            if os.path.isfile(stem_in + extension) and os.path.abspath(stem_in) != os.path.abspath(stem_out):
                shutil.copyfile(stem_in + extension, stem_out + extension)
        after = extract(python, out_path, folder, "out.json")
        checks = _checks(check_module, after)
        refs = plan["refs"]
        on_silk = sorted(r for r, v in refs.items() if not v.get("fab") and not v.get("keep"))
        unplaced = placement.report["unplaced"]
        findings = list(placement.notes) + _check_findings(checks)
        detail = (f"wrote {out_path}: only silkscreen differs from the input; {len(on_silk)} of {len(refs)} references on silkscreen, "
                  f"{len(unplaced)} unplaced, {sum(len(v) for v in checks.values())} silkscreen measures broken")
        return done("WRITTEN", detail, findings, 0, written=out_path, sha256=silkscreen_patch.sha(candidate), references=len(refs),
                    references_on_silk=len(on_silk), unplaced=unplaced, fixed=placement.report["fixed"],
                    checks={cls: len(rows) for cls, rows in checks.items()})
    finally:
        if scratch is not None:
            scratch.cleanup()


def prove(first: str, second: str, out, as_json: bool) -> int:
    findings = []
    texts = []
    for path in (first, second):
        try:
            texts.append(read_board(path))
        except ValueError as error:
            findings.append({"finding": "UNREADABLE", "item": path, "detail": str(error)})
    if findings:
        kicad_scripting.emit(_report("REFUSED", "a board cannot be read, so nothing was proved", findings), out, as_json)
        return 1
    try:
        differences = silkscreen_patch.difference(texts[0], texts[1])
    except Exception as error:  # noqa: BLE001 - a malformed board is the reason
        kicad_scripting.emit(_report("REFUSED", "a board is not well-formed, so nothing was proved",
                                     [{"finding": "UNREADABLE", "item": "board text", "detail": str(error)}]), out, as_json)
        return 1
    if differences:
        kicad_scripting.emit(_report("DIFFERS", f"the boards differ outside silkscreen in {len(differences)} place{'s' if len(differences) != 1 else ''}",
                                     [{"finding": "DIFFERS", "item": d, "detail": "changed outside the silkscreen"} for d in differences]), out, as_json)
        return 1
    kicad_scripting.emit(_report("SILKSCREEN ONLY", "nothing outside the silkscreen differs between the boards", [],
                                 input_sha256=silkscreen_patch.sha(texts[0]), output_sha256=silkscreen_patch.sha(texts[1])), out, as_json)
    return 0


def check(board: str, work: Optional[str], kicad_python: Optional[str], out, as_json: bool) -> int:
    if not os.path.isfile(board):
        kicad_scripting.emit(_report("REFUSED", "the board cannot be read, so nothing was measured",
                                     [{"finding": "UNREADABLE", "item": board, "detail": "no such file"}]), out, as_json)
        return 1
    python = kicad_scripting.interpreter(kicad_python)
    _engine_module, _place_module, check_module = _engine()
    scratch = None
    if work:
        os.makedirs(work, exist_ok=True)
        folder = work
    else:
        scratch = tempfile.TemporaryDirectory(prefix="silkscreen-")
        folder = scratch.name
    try:
        try:
            data = extract(python, board, folder, "check.json")
        except ValueError as error:
            kicad_scripting.emit(_report("REFUSED", "KiCad cannot load the board, so nothing was measured",
                                         [{"finding": "UNREADABLE", "item": board, "detail": str(error)}]), out, as_json)
            return 1
        checks = _checks(check_module, data)
        total = sum(len(v) for v in checks.values())
        if total:
            kicad_scripting.emit(_report("VIOLATIONS", f"{total} silkscreen measure{'s' if total != 1 else ''} broken in "
                                                     f"{len(checks)} class{'es' if len(checks) != 1 else ''}", _check_findings(checks),
                                         checks={cls: len(rows) for cls, rows in checks.items()}), out, as_json)
            return 1
        kicad_scripting.emit(_report("CLEAN", f"no silkscreen measure is broken on {len(data['silk'])} silkscreen items", [], checks={}), out, as_json)
        return 0
    finally:
        if scratch is not None:
            scratch.cleanup()


def require_table_packages() -> None:
    """Run again under SILKSCREEN_PYTHON when that holds the table's package; else CannotRun naming the package.

    Every subcommand reads the table's YAML, the proof included, so the stop comes before any of them starts.
    """
    silkscreen_python.rerun_under_silkscreen_python(needed=silkscreen_python.TABLE_PACKAGES)
    missing = silkscreen_python.missing_packages(silkscreen_python.TABLE_PACKAGES)
    if missing:
        raise CannotRun(silkscreen_python.missing_message(missing[0]))


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "prove", "check"):
        p = sub.add_parser(name)
        p.add_argument("--format", choices=("text", "json"), default="text")
        if name == "build":
            p.add_argument("--board", required=True, help="the input layout (.kicad_pcb); never written")
            p.add_argument("--out", required=True, help="where to write the board with the rebuilt silkscreen")
            p.add_argument("--table", default=None, help="the board's silkscreen table (YAML); without it the defaults are used")
            p.add_argument("--work", default=None, help="a folder to keep the extract, ink measures and plan in (default: a temporary one)")
            p.add_argument("--resolution", type=float, default=DEFAULT_RESOLUTION, help="the raster step in mm (default: %(default)s)")
        if name == "prove":
            p.add_argument("--input", required=True, help="the board before")
            p.add_argument("--output", required=True, help="the board after")
        if name == "check":
            p.add_argument("--board", required=True, help="the layout to measure (.kicad_pcb)")
            p.add_argument("--work", default=None, help="a folder to keep the extract in")
        if name != "prove":
            p.add_argument("--kicad-python", default=None,
                           help=f"KiCad's bundled Python (default: the environment variable {kicad_scripting.VARIABLE})")
    args = parser.parse_args(argv)
    as_json = args.format == "json"
    try:
        require_table_packages()
        if args.command == "build":
            return build(args.board, args.out, args.table, args.work, args.kicad_python, args.resolution, out, as_json)
        if args.command == "prove":
            return prove(args.input, args.output, out, as_json)
        return check(args.board, args.work, args.kicad_python, out, as_json)
    except CannotRun as error:
        return kicad_scripting.cannot_run(error, out, as_json)


if __name__ == "__main__":
    sys.exit(main())
