#!/usr/bin/env python3
"""The heater wall board's own three-dimensional model, exported from its KiCad file and kept beside the case.

    python board_model.py                     regenerate board-model/heater-wall-board.step and its sidecar
    python board_model.py --kicad-cli PATH    name kicad-cli when it is not on PATH (or set KICAD_CLI)

The model is what `kicad-cli pcb export step` writes for the layout file with the origin left at KiCad's own (so X is the layout's x,
Y is its y negated, and the component face, F.Cu, looks toward +Z): the board body with its outline, both slots and every drilled hole, and
the pads as thin solids. The footprints carry no component models. fit.py places the exported case against it by a translation alone.

The STEP file is a cache of that export, committed so that the fit check needs no KiCad. Its sidecar, board-model/heater-wall-board.json,
holds the sha256 of the layout file the model came from, the command and the kicad-cli version; `stale()` says in words when the layout
file has changed since, and the fit check and its tests fail on it, naming `task hw:case:board-model`. Only the layout file's hash is
pinned: the STEP file itself carries a time stamp and is not byte-stable between runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD_DIR = os.path.dirname(HERE)
PCB = os.path.join(BOARD_DIR, "heater-wall-board.kicad_pcb")
MODEL_DIR = os.path.join(HERE, "board-model")
STEP = os.path.join(MODEL_DIR, "heater-wall-board.step")
SIDECAR = os.path.join(MODEL_DIR, "heater-wall-board.json")
TASK = "task hw:case:board-model"


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def export_command(kicad_cli: str = "kicad-cli") -> List[str]:
    """The export, as it is run from the board's own folder (the paths are relative to it)."""
    return [kicad_cli, "pcb", "export", "step", "--user-origin", "0x0mm", "--include-pads", "-f", "-o",
            os.path.relpath(STEP, BOARD_DIR), os.path.relpath(PCB, BOARD_DIR)]


def stale(pcb: str = PCB, sidecar: str = SIDECAR, step: str = STEP) -> Optional[str]:
    """None when the cached model is the export of the layout file as it is now, else what is wrong, naming the task that regenerates it."""
    if not os.path.exists(step) or not os.path.exists(sidecar):
        return f"the board's three-dimensional model {os.path.relpath(step, HERE)} or its sidecar is missing: run `{TASK}`"
    with open(sidecar, encoding="utf-8") as handle:
        recorded = json.load(handle)
    now = sha256_of(pcb)
    if recorded.get("kicad_pcb_sha256") != now:
        return (f"the board's three-dimensional model was exported from a layout file with sha256 {str(recorded.get('kicad_pcb_sha256'))[:12]}, "
                f"the layout file is now {now[:12]}: run `{TASK}`")
    return None


def regenerate(kicad_cli: str) -> Dict[str, Any]:
    os.makedirs(MODEL_DIR, exist_ok=True)
    command = export_command(kicad_cli)
    result = subprocess.run(command, cwd=BOARD_DIR, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(STEP):
        raise SystemExit(f"kicad-cli failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}\n"
                         "set KICAD_CLI=/path/to/kicad-cli (or pass --kicad-cli) when kicad-cli is not on PATH")
    version = subprocess.run([kicad_cli, "version"], capture_output=True, text=True).stdout.strip()
    record = {"kicad_pcb": os.path.relpath(PCB, BOARD_DIR), "kicad_pcb_sha256": sha256_of(PCB), "board_model": os.path.relpath(STEP, BOARD_DIR),
              "command": [os.path.basename(command[0])] + command[1:], "working_folder": "the board's own folder", "kicad_cli_version": version}
    with open(SIDECAR, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1)
        handle.write("\n")
    return record


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export the board's three-dimensional model from its KiCad file into the case's cache.")
    parser.add_argument("--kicad-cli", default=os.environ.get("KICAD_CLI", "kicad-cli"), help="kicad-cli, 10.0 or newer (default: $KICAD_CLI, else kicad-cli on PATH)")
    args = parser.parse_args(argv)
    record = regenerate(args.kicad_cli)
    print(f"{os.path.relpath(STEP, HERE)}: kicad-cli {record['kicad_cli_version']}, layout sha256 {record['kicad_pcb_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
