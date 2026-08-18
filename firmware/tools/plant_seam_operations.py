#!/usr/bin/env python3
"""The operations the plant seam declares, read out of the seam header.

Two things need this list and neither may keep its own. The build step that
stops the linker discarding the model from an artefact nothing has yet been
written to drive needs to name them; the check that the artefact carries the
model needs to look for them. A seam that gained an operation while one of
those lists stayed as it was would leave that operation retained and unchecked,
or checked and discarded, and both read as passing.

So the header is the list. What is read out of it is checked rather than
trusted: the seam header's own check establishes that no structure name, vendor
symbol or function definition reaches it, but not that every file-scope
declaration in it is an operation. A typedef of a function pointer written at
column zero looks exactly like one to a reader this simple, and the name it
would yield is a C keyword. So a name that could not be a function's is refused
here rather than passed on to a linker, which would ask for a symbol called
`void` and say so in a way that names none of this.
"""

from __future__ import annotations

import os
import re

#: The header declaring the seam.
SEAM_HEADER = "plant_model.h"

#: A function declaration at file scope: a return type, a name, an open bracket.
_OPERATION = re.compile(r"^[A-Za-z_][A-Za-z0-9_ *]*?\b([a-z_][a-z0-9_]*)\s*\(", re.MULTILINE)

#: Comments, stripped before matching so a name written in prose is not read as
#: a declaration. Replaced by a newline rather than a space, so a declaration
#: sitting on the line a block comment ends on still begins a line.
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)

#: A declaration this cannot be reading, whatever it looks like. A keyword is
#: what a function-pointer typedef at column zero yields, and it is the one
#: shape that reads as an operation without being one.
_NOT_A_NAME = frozenset(
    {
        "void", "char", "short", "int", "long", "float", "double", "signed",
        "unsigned", "const", "volatile", "struct", "union", "enum", "typedef",
        "static", "extern", "inline", "register", "return", "sizeof", "if",
        "for", "while", "switch", "do", "else", "goto", "break", "continue",
    }
)


class NoSeamOperations(Exception):
    """The seam header is absent, or declares nothing this can retain or look for."""


def operations(include_dir: str) -> list[str]:
    """Every operation the seam declares, in name order.

    Refuses rather than returning an empty list. An empty answer would retain
    nothing and look for nothing, and both of those pass.
    """
    path = os.path.join(include_dir, SEAM_HEADER)
    if not os.path.isfile(path):
        raise NoSeamOperations(f"no plant seam header at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        source = _COMMENT.sub("\n", handle.read())

    matched = set(_OPERATION.findall(source))
    refused = sorted(name for name in matched if name in _NOT_A_NAME)
    if refused:
        raise NoSeamOperations(
            f"{path}: '{refused[0]}' is not a name a function could have, so what looks like "
            "a declaration here is something else -- a function-pointer typedef, most likely"
        )

    found = sorted(matched)
    if not found:
        raise NoSeamOperations(f"{path} declares no operations, so there is nothing to carry")
    return found
