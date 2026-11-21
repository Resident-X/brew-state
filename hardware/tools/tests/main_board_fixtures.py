"""The committed main board read for its do-not-populate marks, shared by the tests that hold the board to them.

The set of unfitted parts is read from the committed schematic's own `(dnp yes)` symbols and never listed here, so
a test that uses it follows the board when a part is fitted or left off, and two tests cannot disagree about it.
"""

from __future__ import annotations

import os
import shutil
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD_FOLDER = "hardware/sunbeam-em7000/main-board"
PROJECT = f"{BOARD_FOLDER}/main-board.kicad_pro"
BOARD = os.path.join(REPO, *BOARD_FOLDER.split("/"))


def design():
    return board_check.Design(PROJECT)


def repository(root, tracked=None):
    """The files of the board's folder as the check reads them: those git tracks, or `tracked` when a scratch copy is given."""
    if tracked is None:
        tracked = [path for path in board_check.tracked_files("git", root) if path.startswith(BOARD_FOLDER + "/")]
    return board_check.Repository(root, tracked)


def unfitted(root=REPO):
    """Every reference the board's schematic marks do-not-populate on the symbol, read from the sheets as committed."""
    marks = board_check.schematic_marks(root, design(), repository(root))
    return {reference for reference, units in marks.items() if any(unit.attribute for unit in units)}


def scratch_board(scratch):
    """A copy of the board's folder under `scratch`, laid out at the same repository path, and its tracked file list."""
    target = os.path.join(scratch, *BOARD_FOLDER.split("/"))
    shutil.copytree(BOARD, target, ignore=shutil.ignore_patterns("__pycache__"))
    tracked = [f"{BOARD_FOLDER}/{os.path.relpath(os.path.join(folder, name), target).replace(os.sep, '/')}"
               for folder, _, names in os.walk(target) for name in names]
    return tracked


def flip_symbol(scratch, reference):
    """Flip the do-not-populate attribute of the one symbol of `reference` in the scratch copy's sheets."""
    folder = os.path.join(scratch, *BOARD_FOLDER.split("/"))
    marker = f'(property "Reference" "{reference}"'
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".kicad_sch"):
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if marker not in text:
            continue
        assert text.count(marker) == 1, f"{reference} is placed more than once in {name}"
        at = text.index(marker)
        start = text.rindex("\n\t(symbol\n", 0, at)
        following = text.find("\n\t(", at)
        end = following if following != -1 else len(text)
        block = text[start:end]
        flag = "(dnp yes)" if "(dnp yes)" in block else "(dnp no)"
        assert block.count(flag) == 1, reference
        other = "(dnp no)" if flag == "(dnp yes)" else "(dnp yes)"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text[:start] + block.replace(flag, other) + text[end:])
        return name
    raise AssertionError(f"{reference} is on no sheet of the board")
