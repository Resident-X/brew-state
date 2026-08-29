#!/usr/bin/env python3
"""The form a parameter description takes when it travels inside an artefact.

A target has no filesystem, so the description it is built against cannot be
opened at start-up the way the host tier opens one. It travels compiled in
instead, as an array of bytes the same loader is then pointed at.

Rendering that array and reading it back live here together, in one module,
because they are two halves of one format. Written apart they drift: the check
that compares what an artefact carries against what the tier verified would be
reading a shape the generator had stopped emitting, and would go on passing
while reading nothing. The generator writes through `render`, the check reads
through `decode`, and neither has an opinion of its own about the form.

The array is a brace initialiser rather than a string literal deliberately.
C11 guarantees an implementation supports string literals of only 4095
characters after concatenation, and line splicing folds a backslash-continued
literal back into one logical line before that limit is applied -- so a
description of any size is a portability question the moment it is written as
text. An initialiser list carries no such limit.

Each byte carries its cast because plain `char` is signed on some targets and
unsigned on others. A byte above 127 written bare is a narrowing conversion
there and not here, which is a build that fails on somebody else's machine for
a reason the file gives no sign of.
"""

from __future__ import annotations

import re
from typing import NamedTuple

#: The line the generated file records its origin on, so what it was made from
#: is answerable from the artefact rather than from the build that made it.
SOURCE_MARKER = "description-source:"

#: Where the build puts what it renders, under the environment's build
#: directory. Here rather than in the script that writes it, because the check
#: that reads it needs the same answer and a second statement of where a file
#: is, is how the two come to look at different ones.
GENERATED_DIRECTORY = "generated"


class Embedding(NamedTuple):
    """One file an artefact carries compiled in.

    An artefact carries more than one: the description of the machine, the
    declaration of what a reading off that machine may plausibly be, the band
    a delivery off it is held to, and the gains the pump trim corrects a rate
    gap with. They are the same mechanism repeated rather than four mechanisms,
    so the parts that differ between them -- the symbol defined and the file
    rendered to -- are named here and everything else is shared. A second copy
    of the renderer for a second file is how the formats would come to differ,
    and each copy after the first is a place the drift can start from without
    anything reporting it.
    """

    #: The symbol the generated array is defined as. The checked-in declaration
    #: names the same symbol; nothing else may.
    symbol: str
    #: What the rendered file is called, under GENERATED_DIRECTORY.
    generated_name: str
    #: What the file is, in words, for a message a reader has to act on.
    description: str


#: The parameter description: what the machine is.
DESCRIPTION = Embedding(
    symbol="reference_description",
    generated_name="reference_description_bytes.h",
    description="parameter description",
)

#: The limits declaration: what a reading off it may plausibly be, and how long
#: the estimator may go without one.
LIMITS = Embedding(
    symbol="reference_limits",
    generated_name="reference_limits_bytes.h",
    description="limits declaration",
)

#: The tolerance declaration: how far from the temperature it was asked for a
#: delivery off the machine may sit. It travels with the other two and is unlike
#: them: they say what this machine is and what its sensors could report, and
#: this says what the drink demands whatever machine it was made on.
TOLERANCE = Embedding(
    symbol="reference_tolerance",
    generated_name="reference_tolerance_bytes.h",
    description="tolerance declaration",
)

#: The pump trim declaration: the gains DEC-CORRECTION-KEEPS-THE-ACCOUNT's
#: closed-loop trim leans on a rate gap with. It travels with the other three
#: for the same want of a filesystem on the target, and it is unlike all three
#: of them in what it is a statement about: the description and the limits say
#: what this machine is and what its sensors could report, and the tolerance
#: says what the drink demands whatever machine it was made on -- this says how
#: hard the design corrects a rate gap, which is a control-tuning policy on
#: exactly the footing the steam side's own declaration already is, and not a
#: fact about this machine or this drink at all. It is carried anyway, because
#: control_init refuses to come up without it and there is nowhere on the
#: target to read it from.
PUMP_TRIM = Embedding(
    symbol="reference_pump_trim",
    generated_name="reference_pump_trim_bytes.h",
    description="pump trim declaration",
)

#: All of them, in the order a build renders them.
EMBEDDINGS = (DESCRIPTION, LIMITS, TOLERANCE, PUMP_TRIM)

#: How many bytes go on one line. Narrow enough to read, wide enough that a
#: description of a few kilobytes does not become a file of a few thousand
#: lines.
_BYTES_PER_LINE = 12

_SOURCE_LINE = re.compile(r"^\s*\*?\s*" + SOURCE_MARKER + r"\s*(\S+)\s*$", re.MULTILINE)
_BYTE = re.compile(r"\(char\)0x([0-9a-f]{2})u")


class MalformedEmbedding(Exception):
    """The generated file is not something this module wrote."""


def render(source: str, data: bytes, embedding: Embedding = DESCRIPTION) -> str:
    """The C definition carrying `data`, recording `source` as where it came from.

    Refuses an empty file. There is no C for it that every compiler accepts --
    an empty initialiser is an extension -- and a description with nothing in it
    is not a smaller description of the machine anyway.
    """
    if not data:
        raise MalformedEmbedding(f"{source} is empty, so there is nothing to carry")

    lines = [
        "/*",
        " * Generated. Do not edit, and do not check in.",
        " *",
        " * It is derived from the file named below every time the build runs. A copy of it",
        " * kept in the source tree would be a second statement about the same machine,",
        " * answering differently the moment either was corrected.",
        " *",
        f" * {SOURCE_MARKER} {source}",
        " */",
        "",
        f"const char {embedding.symbol}[] = {{",
    ]
    for offset in range(0, len(data), _BYTES_PER_LINE):
        chunk = data[offset : offset + _BYTES_PER_LINE]
        lines.append("    " + " ".join(f"(char)0x{byte:02x}u," for byte in chunk))
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def decode(text: str, embedding: Embedding = DESCRIPTION) -> tuple[str, bytes]:
    """The source a generated file records, and the bytes it carries.

    Refuses rather than returning what it managed to find. A file whose marker
    is missing, or which defines no array, is not a smaller embedding; it is a
    file this module did not write, and reading bytes out of it would be the
    check answering about something other than what the build compiles.
    """
    named = _SOURCE_LINE.search(text)
    if named is None:
        raise MalformedEmbedding(
            f"no '{SOURCE_MARKER}' line, so what it was generated from is not recorded"
        )

    opening = text.find(f"const char {embedding.symbol}[] = {{")
    if opening < 0:
        raise MalformedEmbedding(
            f"no definition of {embedding.symbol}, so it carries no {embedding.description}"
        )
    closing = text.find("};", opening)
    if closing < 0:
        raise MalformedEmbedding(f"the definition of {embedding.symbol} is not terminated")

    body = text[opening:closing]
    if text.find(f"const char {embedding.symbol}[] = {{", closing) >= 0:
        raise MalformedEmbedding(
            f"{embedding.symbol} is defined more than once, so which "
            f"{embedding.description} it carries is not settled"
        )

    stray = re.sub(_BYTE.pattern, "", body[body.index("{") + 1 :]).replace(",", "")
    if stray.split():
        raise MalformedEmbedding(
            f"the definition of {embedding.symbol} carries something other than "
            f"bytes: {stray.split()[0]}"
        )

    return named.group(1), bytes(int(pair, 16) for pair in _BYTE.findall(body))
