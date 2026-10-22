#!/usr/bin/env python3
"""Synthetic repositories, netlists, sheet drawings and review folders for the schematic review caller's, the folder command's and
the proof's tests.

Nothing here is a real design or a real specification: the method has a three-area catalogue with synthetic identifiers, the
schematic is a few symbols in KiCad's text form, the netlist is the few lines KiCad would write for them, and every figure is made
up. No KiCad and no model is used.
"""

from __future__ import annotations

import io
import json
import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as lfx  # noqa: E402
import review_folder  # noqa: E402
import schematic_review_folder  # noqa: E402

DESIGN = "hardware/synth/board"
NAME = "board"
METHOD = """# Synthetic board design method

## Schematic review

Steps of a schematic review.

## Layout review

Unrelated: a layout review section.

## Schematic drawing convention

How a sheet is drawn.

## Circuit practice catalogue

Intro of the circuit catalogue.

### How a circuit item is read

Every item carries fields.

### Pin voltages (PINV)

#### PINV-1. Every pin stays within its rating

- **Applies when:** always; it selects every net, and each pin on the net is judged.

#### PINV-2. A pin driven while unpowered

- **Applies when:** a net reaches a pin from a part with a supply of its own.

### Boot and strap (STRAP)

#### STRAP-1. A strap pin is not left floating

- **Applies when:** a part has a strap pin.

### Derating (DERATE)

#### DERATE-1. Every part is derated

- **Applies when:** always; it selects every part.

#### DERATE-2. Every sheet is legible

- **Applies when:** always; it selects every sheet.

## Ordering

Unrelated: #### NOT-1. Not a circuit item
"""
README = "# Synthetic hardware notes\n\nThe sheets and the netlist.\n"
#: The sheets of the synthetic schematic: the root, named for the design, and one below it.
SHEETS = [NAME, "Power"]
PARTS = ["C1", "R1", "R2", "U1"]
NETS = ["/IN", "/MID", "/PWR", "GND"]
ITEMS = ["PINV-1", "PINV-2", "STRAP-1", "DERATE-1", "DERATE-2"]

ROOT_SCH = """(kicad_sch (version 20250114) (generator "synthetic")
 (uuid "00000000-0000-0000-0000-000000000001")
 (symbol (lib_id "Device:R") (at 10 10 0) (unit 1)
  (property "Reference" "R1") (property "Value" "10k")
  (instances (project "board" (path "/00000000-0000-0000-0000-000000000001" (reference "R1") (unit 1)))))
 (symbol (lib_id "Device:C") (at 20 10 0) (unit 1)
  (property "Reference" "C1") (property "Value" "100n")
  (instances (project "board" (path "/00000000-0000-0000-0000-000000000001" (reference "C1") (unit 1)))))
 (symbol (lib_id "power:GND") (at 30 10 0) (unit 1)
  (property "Reference" "#PWR01") (property "Value" "GND")
  (instances (project "board" (path "/00000000-0000-0000-0000-000000000001" (reference "#PWR01") (unit 1)))))
 (sheet (at 50 50) (size 20 20)
  (property "Sheetname" "Power") (property "Sheetfile" "power.kicad_sch"))
)
"""
POWER_SCH = """(kicad_sch (version 20250114) (generator "synthetic")
 (uuid "00000000-0000-0000-0000-000000000002")
 (symbol (lib_id "Device:R") (at 10 10 0) (unit 1)
  (property "Reference" "R2") (property "Value" "1k")
  (instances (project "board" (path "/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-0000000000a2" (reference "R2") (unit 1)))))
 (symbol (lib_id "Device:U") (at 20 10 0) (unit 1)
  (property "Reference" "U1") (property "Value" "chip")
  (instances (project "board" (path "/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-0000000000a2" (reference "U1") (unit 1)))))
)
"""
NETLIST = """(export (version "E")
  (design (source "board.kicad_sch") (tool "synthetic")
    (sheet (number "1") (name "/") (tstamps "/"))
    (sheet (number "2") (name "/Power/") (tstamps "/a2/")))
  (components
    (comp (ref "C1") (value "100n"))
    (comp (ref "R1") (value "10k"))
    (comp (ref "R2") (value "1k"))
    (comp (ref "U1") (value "chip")))
  (nets
    (net (code "1") (name "/IN") (node (ref "R1") (pin "1")))
    (net (code "2") (name "/MID") (node (ref "R1") (pin "2")) (node (ref "U1") (pin "1")))
    (net (code "3") (name "/PWR") (node (ref "R2") (pin "1")) (node (ref "U1") (pin "2")))
    (net (code "4") (name "GND") (node (ref "C1") (pin "2")) (node (ref "R2") (pin "2")))))
"""
NETLIST_COMMAND = "kicad-cli sch export netlist --output <work folder>/review.net board.kicad_sch"
RECORD = """# Schematic review of the synthetic board

## Round 1

- **Schematic judged**: 1234567.

### Verdicts

| Item | Net or part | Verdict | Rests on | Why |
|---|---|---|---|---|
| PINV-1 | /IN | fail | sheet board, net /IN | Finding 1.1. |

### Findings

| Finding | Raised by | Severity | What and where | Closed by |
|---|---|---|---|---|
| 1.1 | PINV-1 | function | sheet board, net /IN: a pin above its rating | met: it is inside |
"""
SEPARATION = "standard: synthetic\naccepted_by: a person\naccepted_on: 2026-10-18\n"
RECORDS = {"constraints.md": "# Constraints\n", "circuit-proof.md": "# Circuit proof\n", "separation-basis.yaml": SEPARATION}
CHECK_REPORT = "DESIGN | hardware/synth/board/board.kicad_pro | PASS\nRESULT | PASS\n"

BOARD_FILES = {"board.kicad_pro": "{}\n", "board.kicad_sch": ROOT_SCH, "power.kicad_sch": POWER_SCH,
               "board.kicad_sym": "(kicad_symbol_lib)\n", "sym-lib-table": "(sym_lib_table)\n", "fp-lib-table": "(fp_lib_table)\n",
               "board.kicad_pcb": "(kicad_pcb)\n", "board.kicad_dru": "(version 1)\n", **RECORDS}


def make_repo(root: str, record: str = RECORD, extra=None, design: str = DESIGN, method: str = METHOD,
              files=None) -> str:
    """A repository holding the synthetic schematic, its records, a review record and the designer's own notes; the commit that
    holds them is its only one."""
    repo = os.path.join(root, "repository")
    os.makedirs(repo)
    lfx.git(repo, "init", "-q")
    for name, text in {**(BOARD_FILES if files is None else files), "schematic-review.md": record,
                       "designer-notes.md": "Why I drew it so.\n", "session.txt": "the session\n", **(extra or {})}.items():
        if text is not None:
            lfx.write(os.path.join(repo, design, name), text)
    lfx.write(os.path.join(repo, "docs", "board-design-method.md"), method)
    lfx.write(os.path.join(repo, "hardware", "README.md"), README)
    lfx.git(repo, "add", "-A")
    lfx.git(repo, "commit", "-q", "-m", "the schematic")
    return repo


def make_inputs(root: str, netlist: str = NETLIST) -> dict:
    """A netlist, a folder of sheet drawings and a check report, as the commands that export, draw and run them leave them."""
    net, sheets, report = os.path.join(root, "export", "review.net"), os.path.join(root, "sheets-in"), os.path.join(root, "report-in.txt")
    lfx.write(net, netlist)
    for sheet in SHEETS:
        lfx.write(os.path.join(sheets, schematic_review_folder.drawing_name(NAME, sheet)), f"<svg><!-- {sheet} --></svg>\n")
    lfx.write(report, CHECK_REPORT)
    return {"netlist": net, "sheets": sheets, "report": report}


def folder_argv(repo: str, out: str, inputs: dict, number: int = 1, commit: str = "HEAD", records=tuple(RECORDS), extra=()) -> list:
    argv = ["--repo", repo, "--commit", commit, "--design", DESIGN, "--out", out, "--netlist", inputs["netlist"],
            "--netlist-command", NETLIST_COMMAND, "--sheets", inputs["sheets"], "--check-report", inputs["report"],
            "--number", str(number), "--documents-repo", repo]
    for record in records:
        argv += ["--record", record]
    return argv + list(extra)


def run_folder(argv: list):
    out = io.StringIO()
    status = schematic_review_folder.main(argv, out=out)
    return status, out.getvalue()


def write_review_folder(root: str, number: int = 1, record: str = RECORD, netlist: str = NETLIST, method: str = METHOD) -> str:
    """A review folder written by the folder command from a synthetic repository; its path."""
    repo = make_repo(root, record, method=method)
    inputs = make_inputs(root, netlist)
    out = os.path.join(root, "review-folder")
    status, text = run_folder(folder_argv(repo, out, inputs, number))
    assert status == 0, text
    return out


def add_view_argv(folder: str, view: str, item: str = "STRAP-1", why: str = "needs the sheet Power: its drawing is blurred",
                  target: str = None, command: str = "task hw:sheets -- --out <sheets>") -> list:
    argv = ["--add-view", folder, "--view", view, "--view-command", command, "--cannot-judge-item", item, "--cannot-judge-why", why]
    return argv + (["--cannot-judge-target", target] if target is not None else [])


def add_document_argv(folder: str, document: str, source: str = "datasheet table 3, strap levels", item: str = "STRAP-1",
                      why: str = "needs the datasheet of U1: the strap levels are not in the folder", target: str = None) -> list:
    argv = ["--add-document", folder, "--document", document, "--source", source, "--cannot-judge-item", item,
            "--cannot-judge-why", why]
    return argv + (["--cannot-judge-target", target] if target is not None else [])


round_file = lfx.round_file
set_round = lfx.set_round
write = lfx.write
