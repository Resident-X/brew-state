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

#: The line the generated file records its origin on, so what it was made from
#: is answerable from the artefact rather than from the build that made it.
SOURCE_MARKER = "description-source:"

#: The symbol the generated array is defined as. The checked-in declaration
#: names the same symbol; nothing else may.
SYMBOL = "reference_description"

#: Where the build puts what it renders, under the environment's build
#: directory, and what it calls it. Here rather than in the script that writes
#: it, because the check that reads it needs the same answer and a second
#: statement of where a file is, is how the two come to look at different ones.
GENERATED_DIRECTORY = "generated"
GENERATED_NAME = "reference_description_bytes.h"

#: How many bytes go on one line. Narrow enough to read, wide enough that a
#: description of a few kilobytes does not become a file of a few thousand
#: lines.
_BYTES_PER_LINE = 12

_SOURCE_LINE = re.compile(r"^\s*\*?\s*" + SOURCE_MARKER + r"\s*(\S+)\s*$", re.MULTILINE)
_BYTE = re.compile(r"\(char\)0x([0-9a-f]{2})u")


class MalformedEmbedding(Exception):
    """The generated file is not something this module wrote."""


def render(source: str, data: bytes) -> str:
    """The C definition carrying `data`, recording `source` as where it came from.

    Refuses an empty description. There is no C for it that every compiler
    accepts -- an empty initialiser is an extension -- and a description with
    nothing in it is not a smaller description of the machine anyway.
    """
    if not data:
        raise MalformedEmbedding(f"{source} is empty, so there is no description to carry")

    lines = [
        "/*",
        " * Generated. Do not edit, and do not check in.",
        " *",
        " * It is derived from the description named below every time the build runs. A copy",
        " * of it kept in the source tree would be a second description of the same machine,",
        " * answering differently the moment either was corrected.",
        " *",
        f" * {SOURCE_MARKER} {source}",
        " */",
        "",
        f"const char {SYMBOL}[] = {{",
    ]
    for offset in range(0, len(data), _BYTES_PER_LINE):
        chunk = data[offset : offset + _BYTES_PER_LINE]
        lines.append("    " + " ".join(f"(char)0x{byte:02x}u," for byte in chunk))
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def decode(text: str) -> tuple[str, bytes]:
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

    opening = text.find(f"const char {SYMBOL}[] = {{")
    if opening < 0:
        raise MalformedEmbedding(f"no definition of {SYMBOL}, so it carries no description")
    closing = text.find("};", opening)
    if closing < 0:
        raise MalformedEmbedding(f"the definition of {SYMBOL} is not terminated")

    body = text[opening:closing]
    if text.find(f"const char {SYMBOL}[] = {{", closing) >= 0:
        raise MalformedEmbedding(
            f"{SYMBOL} is defined more than once, so which description it carries is not settled"
        )

    stray = re.sub(_BYTE.pattern, "", body[body.index("{") + 1 :]).replace(",", "")
    if stray.split():
        raise MalformedEmbedding(
            f"the definition of {SYMBOL} carries something other than bytes: {stray.split()[0]}"
        )

    return named.group(1), bytes(int(pair, 16) for pair in _BYTE.findall(body))
