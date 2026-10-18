#!/usr/bin/env python3
"""Render every sheet of every board design the repository tracks, as a vector image for each sheet.

A board design is found as the pre-order check finds it: a KiCad project file
git tracks, with the schematic and layout beside it, wherever it sits. Each
design's tracked files are copied into a scratch replica of the repository,
and KiCad's own command-line tool writes one SVG file for each sheet of the
schematic from the copy, so the drawing is of the design as the repository
holds it and nothing left lying beside it, and nothing is ever written into the
repository. KiCad alone draws the sheets; no second tool is needed.

The images are written into a new or empty folder outside every design's
folder, in a subfolder for each design that follows the design's place in the
repository, and they are working files, never committed, so a render cannot
drift from the schematic it shows. A file is named for the design and, for a
sheet below the root, the sheet's name.

Every line is printed in a fixed shape,

    SHEET | <design> | <file written>
    DESIGN | <design> | PASS or FAIL
    RESULT | PASS or FAIL | <summary>

and the exit status is 0 when every sheet of every design was written, 1 when a
design could not be rendered or the command was refused, and 2 when it cannot
run at all, such as for a missing or too-old KiCad.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import locked_copper  # noqa: E402

#: How long KiCad may take to draw one design, in seconds.
RENDER_TIMEOUT_S = 600


def refusals(top: str, designs: Sequence[board_check.Design], out: str) -> List[str]:
    """Why sheets are not to be written into `out`: a folder inside a design's folder, a file, or one already holding files."""
    found = []
    for design in designs:
        folder = locked_copper.design_folder(out, os.path.join(top, design.schematic))
        if folder is not None:
            found.append(f"{out}: the renders are working files and are never kept in a design's folder, where they "
                         f"could be committed and copied as part of the design; {folder} holds a design's project "
                         "file, so write them outside it")
            break
    if os.path.lexists(out) and not os.path.isdir(out):
        found.append(f"{out}: the output folder is a file; name a new folder, or an empty one")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"{out}: the output folder already holds files, which would be mistaken for these renders; "
                     "name a new folder, or an empty one")
    return found


def render_design(top: str, repository: board_check.Repository, design: board_check.Design, out: str,
                  kicad_cli: str, environment: dict) -> List[str]:
    """Write one SVG for each sheet of `design` into `out`; the files written, or raise ValueError saying why not."""
    files, unreachable = board_check.design_files(design, repository)
    if unreachable:
        raise ValueError("; ".join(f"{v.location}: {v.message}" for v in unreachable))
    with tempfile.TemporaryDirectory(prefix="schematic-sheets-") as scratch:
        replica = os.path.join(scratch, "repository")
        for path in files:
            if os.path.isfile(os.path.join(top, path)):
                target = os.path.join(replica, path)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(top, path), target)
        drawn = os.path.join(scratch, "drawn")
        os.makedirs(drawn)
        schematic = os.path.join(replica, design.schematic)
        if not os.path.isfile(schematic):
            raise ValueError(f"{design.schematic} is not among the tracked files, so there is no schematic to draw")
        try:
            result = subprocess.run([kicad_cli, "sch", "export", "svg", "--output", drawn, schematic],
                                    cwd=os.path.dirname(schematic), capture_output=True, text=True,
                                    timeout=RENDER_TIMEOUT_S, env=environment)
        except subprocess.TimeoutExpired:
            raise ValueError(f"KiCad did not finish drawing it within {RENDER_TIMEOUT_S} s") from None
        written = sorted(name for name in os.listdir(drawn) if name.endswith(".svg"))
        if result.returncode != 0 or not written:
            said = " ".join((result.stdout + " " + result.stderr).split())
            raise ValueError(f"KiCad could not draw its schematic (exit {result.returncode}: {said[:300]})")
        os.makedirs(out, exist_ok=True)
        for name in written:
            shutil.copy2(os.path.join(drawn, name), os.path.join(out, name))
        return [os.path.join(out, name) for name in written]


def sheets(root: str, out_dir: str, kicad_cli: str, git: str = "git", out=sys.stdout) -> int:
    """Render every sheet of every tracked design into `out_dir`; the exit status."""
    board_check.require_python()
    top = board_check.require_git(git, root)
    version = board_check.require_kicad(kicad_cli)
    files = board_check.tracked_files(git, top)
    repository = board_check.Repository(top, files, git)
    designs, orphans, problems = board_check.discover(top, files)
    if not designs and not orphans:
        print("REFUSED | no board design was found: no project file (.kicad_pro) is tracked anywhere in the "
              "repository, and a command that finds nothing to draw fails rather than reporting success", file=out)
        return 1
    why = refusals(top, designs, os.path.abspath(out_dir))
    if why:
        for line in why:
            print(f"REFUSED | {board_check.clean(line)}", file=out)
        print("RESULT | FAIL | no sheet was written", file=out)
        return 1
    print(f"Drawing board designs under {top} with KiCad {version}", file=out)

    failed = 0
    with tempfile.TemporaryDirectory(prefix="schematic-sheets-kicad-") as home:
        environment = board_check.isolate_kicad(kicad_cli, version, home)
        for design in designs:
            name = board_check.clean(design.project)
            try:
                if problems[design.project]:
                    raise ValueError("; ".join(f"{v.location}: {v.message}" for v in problems[design.project]))
                folder = os.path.join(os.path.abspath(out_dir), design.directory)
                written = render_design(top, repository, design, folder, kicad_cli, environment)
            except (ValueError, OSError) as error:
                failed += 1
                print(f"DESIGN | {name} | FAIL | {board_check.clean(str(error))}", file=out)
                continue
            for path in written:
                print(f"SHEET | {name} | {board_check.clean(path)}", file=out)
            print(f"DESIGN | {name} | PASS | {len(written)} sheet{'s' if len(written) != 1 else ''}", file=out)
    for orphan in orphans:
        failed += 1
        print(f"DESIGN | {board_check.clean(orphan.design)} | FAIL | {board_check.clean(orphan.message)}", file=out)
    total = len(designs) + len(orphans)
    if failed:
        print(f"RESULT | FAIL | {failed} of {total} designs could not be drawn", file=out)
        return 1
    print(f"RESULT | PASS | every sheet of all {total} designs was written to {os.path.abspath(out_dir)}", file=out)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".", help="any folder inside the repository to draw (default: here)")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--git", default="git", help="git (default: git on the search path)")
    parser.add_argument("--out", required=True, help="a new or empty folder outside every design's folder")
    args = parser.parse_args(argv)
    try:
        return sheets(args.root, args.out, args.kicad_cli, args.git)
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
