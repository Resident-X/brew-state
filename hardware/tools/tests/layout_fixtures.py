#!/usr/bin/env python3
"""Synthetic repositories and review folders for the layout review caller's, the folder command's and the proof's tests.

Nothing here is a real design or a real specification: the method has a
three-area catalogue with synthetic identifiers, the board is a few files of
placeholder text, and every figure is made up. No KiCad and no model is used.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import review_folder  # noqa: E402

DESIGN = "hardware/synth/board"
METHOD = """# Synthetic board design method

## Layout review

Steps of a review.

## Layout review views

Views of a review.

## Layout practice catalogue

Intro of the catalogue.

### How an item is read

Every item carries fields.

### Floorplan (FLOOR)

#### FLOOR-1. Parts are grouped

- **Applies when:** always.

#### FLOOR-2. Signals stay apart

- **Applies when:** always.

### Grounding (GROUND)

#### GROUND-1. Ground is a plane

- **Applies when:** always.

### Clocks (CLOCK)

#### CLOCK-1. The crystal sits at its pins

- **Applies when:** the schematic has a crystal.

## Ordering

Unrelated: #### NOT-1. Not a layout item
"""
README = "# Synthetic hardware notes\n\nThe views index and the facts.\n"
OWN_NONE = "| none | | | | | | | | | |"
OWN_ROWS = ("| BOARD-1 | always | Asks | Passes | Fails | `classes` | judgement | quality | the plan | How it is met |\n"
            "| BOARD-2 | always | Asks | Passes | Fails | `classes` | judgement | quality | the plan | How it is met |")


def plan(own: str = OWN_NONE) -> str:
    return f"""# Synthetic layout plan

## Floorplan

| Region | Bounds | What it holds | Parts |
|---|---|---|---|
| mains | none | nothing | none |

## Plan

| Item | Applies | How the layout meets it, or why it does not apply |
|---|---|---|
| FLOOR-1 | yes | Regions as drawn. |

### The board's own items

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|
{own}
"""


RECORD = """# Layout review of the synthetic board

## Round 1

- **Board judged**: 1234567.
- **Round kind**: full

### Verdicts

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | fail | classes | Finding 1.1. |

### Findings

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|
| 1.1 | FLOOR-1 | function | classes at (10, 10): a part is outside its region | no | FLOOR-1 | — | met: it is inside |
"""

CHECK_LINES = ["DESIGN | hardware/synth/board/board.kicad_pro | PASS",
               "FIGURE | hardware/synth/board/board.kicad_pro | WORK-2 | 1.3 | project | read"]
VIEW_COMMANDS = ["task hw:views -- --board board.kicad_pcb --project board.kicad_pro --out <views>",
                 "task hw:placement -- --board board.kicad_pcb --project board.kicad_pro --out <placement>"]

BOARD_FILES = {
    "board.kicad_pro": "{}\n", "board.kicad_pcb": "(kicad_pcb committed)\n", "board.kicad_sch": "(kicad_sch)\n",
    "board.kicad_dru": "(version 1)\n", "fp-lib-table": "(fp_lib_table)\n", "board.pretty/part.kicad_mod": "(footprint part)\n",
    "design-rules.md": "# Rules\n", "constraints.md": "# Constraints\n", "separation-basis.yaml": "standard: synthetic\n",
}


def git(repo: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@invalid", *args], capture_output=True,
                          text=True, check=True)
    return done.stdout.strip()


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def make_repo(root: str, own: str = OWN_NONE, record: str = RECORD, extra=None, design: str = DESIGN, method: str = METHOD) -> str:
    """A repository holding the synthetic board, its plan and records, a review record and the designer's own notes; and the
    commit that holds them."""
    repo = os.path.join(root, "repository")
    os.makedirs(repo)
    git(repo, "init", "-q")
    for name, text in {**BOARD_FILES, "layout-plan.md": plan(own), "layout-review.md": record,
                       "designer-notes.md": "Why I placed it so.\n", "session.txt": "the session\n", **(extra or {})}.items():
        write(os.path.join(repo, design, name), text)
    write(os.path.join(repo, "docs", "board-design-method.md"), method)
    write(os.path.join(repo, "hardware", "README.md"), README)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the board")
    return repo


def make_views(root: str) -> dict:
    """A views folder, a placement folder and a check report, as the commands that render and run them leave them."""
    views, placement = os.path.join(root, "views-in"), os.path.join(root, "placement-in")
    write(os.path.join(views, "index.txt"), "layer-F.Cu.png\n")
    write(os.path.join(views, "facts.txt"), "net facts\n")
    write(os.path.join(views, "layer-F.Cu.png"), "png")
    write(os.path.join(placement, "index.txt"), "placement.png\n")
    write(os.path.join(placement, "measures.txt"), "LENGTH 1\n")
    report = os.path.join(root, "report-in.txt")
    write(report, "\n".join(CHECK_LINES) + "\n")
    return {"views": views, "placement": placement, "report": report}


def folder_argv(repo: str, out: str, inputs: dict, number: int = 1, kind: str = "full", commit: str = "HEAD", extra=()) -> list:
    argv = ["--repo", repo, "--commit", commit, "--design", DESIGN, "--out", out, "--views", inputs["views"],
            "--placement", inputs["placement"], "--check-report", inputs["report"], "--number", str(number), "--kind", kind,
            "--documents-repo", repo]
    for command in VIEW_COMMANDS:
        argv += ["--view-command", command]
    for line in CHECK_LINES:
        argv += ["--check-line", line]
    return argv + list(extra)


NARROW = ["--item", "FLOOR-1=the changed region holds its parts", "--item", "CLOCK-1=the crystal moved",
          "--region", "region low voltage, net XTAL1", "--others", "no other item touches a changed region or net"]


def run_folder(argv: list):
    out = io.StringIO()
    status = review_folder.main(argv, out=out)
    return status, out.getvalue()


def write_review_folder(root: str, own: str = OWN_NONE, number: int = 1, kind: str = "full", narrow: bool = False,
                        record: str = RECORD) -> str:
    """A review folder written by the folder command from a synthetic repository; its path."""
    repo = make_repo(root, own, record)
    inputs = make_views(root)
    out = os.path.join(root, "review-folder")
    status, text = run_folder(folder_argv(repo, out, inputs, number, kind, extra=NARROW if narrow else ()))
    assert status == 0, text
    return out


def round_file(folder: str) -> dict:
    with open(os.path.join(folder, review_folder.ROUND_FILE), encoding="utf-8") as handle:
        return json.load(handle)


def set_round(folder: str, **changes) -> dict:
    """The round file with `changes` made to it (a key set to None is removed); what it now holds."""
    content = round_file(folder)
    for key, value in changes.items():
        if value is None:
            content.pop(key, None)
        else:
            content[key] = value
    write(os.path.join(folder, review_folder.ROUND_FILE), json.dumps(content))
    return content
