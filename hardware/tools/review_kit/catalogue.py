"""The catalogue of a review: its artefacts admitted against the review folder and measured.

Before any session starts, every artefact any unit needs is checked: it lies
inside the review folder (a link out of it does not count), it matches none of
the deny patterns, and it is not a result of another unit of this round. A
refusal names the artefact and the rule. An admitted artefact is measured: a
text by its recorded token count when the declaration gives one and otherwise by
its length in characters, which is an upper bound; an image by the model's patch
formula; and each by the hash of its content.

Files are read through an injected reader, so a test can stand a folder of its own in.
"""

from __future__ import annotations

import fnmatch
import hashlib
import math
import os
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import decl

#: The side of the square patch the model reads an image in, and the allowance on the patch count.
PATCH_PIXELS = 28
PATCH_ALLOWANCE = 1.04
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_START = b"\xff\xd8"
OUTSIDE, DENIED, RESULT, UNREADABLE, NOT_TEXT, NOT_IMAGE = (
    "inside the review folder", "deny list", "no result of another unit", "readable file", "text", "image")


class DiskReader:
    """The files of a folder on disk."""

    def realpath(self, path: str) -> str:
        return os.path.realpath(path)

    def isfile(self, path: str) -> bool:
        return os.path.isfile(path)

    def read(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            return handle.read()


@dataclass(frozen=True)
class Refusal:
    """An artefact the review may not use, the rule that refuses it, and what to do."""

    artefact: str
    rule: str
    detail: str

    def line(self) -> str:
        return f"artefact {self.artefact}: refused by the rule {self.rule!r}: {self.detail}"


class Refused(Exception):
    def __init__(self, refusals: Sequence[Refusal]):
        self.refusals = list(refusals)
        super().__init__("\n".join(refusal.line() for refusal in refusals))


@dataclass(frozen=True)
class Measured:
    """An admitted artefact: where it was read from, how large the model reads it as, and the hash of its content."""

    name: str
    kind: str
    source: str
    sha256: str
    tokens: int
    #: Whether `tokens` is an upper bound (a text measured by its length) and not a recorded count or the patch formula.
    bound: bool
    data: bytes = field(repr=False, compare=False, default=b"")
    media_type: Optional[str] = None
    size: Optional[Tuple[int, int]] = None

    def as_dict(self) -> Dict[str, object]:
        return {"name": self.name, "kind": self.kind, "source": self.source, "sha256": self.sha256, "tokens": self.tokens,
                "bound": self.bound, "media_type": self.media_type, "size": list(self.size) if self.size else None}


@dataclass(frozen=True)
class Catalogue:
    """The admitted, measured artefacts any unit needs, in the fixed order the shared context holds them."""

    artefacts: Tuple[Measured, ...]

    def get(self, name: str) -> Measured:
        for artefact in self.artefacts:
            if artefact.name == name:
                return artefact
        raise KeyError(name)

    @property
    def tokens(self) -> int:
        return sum(artefact.tokens for artefact in self.artefacts)

    def as_dict(self) -> Dict[str, object]:
        return {"artefacts": [artefact.as_dict() for artefact in self.artefacts], "tokens": self.tokens}


def image_tokens(width: int, height: int) -> int:
    """What the model reads an image of this size as: its 28-pixel patches, with the allowance measured on the live runs."""
    patches = math.ceil(width / PATCH_PIXELS) * math.ceil(height / PATCH_PIXELS)
    return math.ceil(patches * PATCH_ALLOWANCE)


def image_size(data: bytes) -> Optional[Tuple[str, int, int]]:
    """The media type, width and height of a PNG or JPEG, read from its header; None for any other bytes."""
    if data.startswith(PNG_SIGNATURE) and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return ("image/png", width, height) if width and height else None
    if data.startswith(JPEG_START):
        position = 2
        while position + 9 <= len(data):
            if data[position] != 0xFF:
                return None
            marker = data[position + 1]
            if marker == 0xFF:
                position += 1
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[position + 5:position + 9])
                return ("image/jpeg", width, height) if width and height else None
            if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
                position += 2
                continue
            position += 2 + struct.unpack(">H", data[position + 2:position + 4])[0]
    return None


def inside(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([path, folder]) == folder
    except ValueError:
        return False


def denied_by(relative: str, patterns: Sequence[str]) -> Optional[str]:
    """The first deny pattern the path matches, tried on the whole relative path and on its last component."""
    base = relative.rsplit("/", 1)[-1]
    for pattern in patterns:
        if fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(base, pattern):
            return pattern
    return None


def admit(declaration: decl.Declaration, folder: str, reader=None, results_folder: Optional[str] = None) -> Catalogue:
    """The measured catalogue of every artefact any unit needs, or a Refused naming each artefact and rule.

    `results_folder` is where this round's results are kept; an artefact lying in it is a result of another unit.
    Nothing is sent anywhere before this passes.
    """
    reader = reader or DiskReader()
    root = reader.realpath(folder)
    kept = reader.realpath(results_folder) if results_folder else None
    refusals: List[Refusal] = []
    found: List[Measured] = []
    for name in declaration.needed:
        artefact = declaration.artefacts[name]
        path = reader.realpath(os.path.join(root, artefact.source))
        relative = os.path.relpath(path, root).replace(os.sep, "/")
        if kept is not None and inside(path, kept):
            refusals.append(Refusal(name, RESULT, f"{artefact.source!r} lies in the results folder, so it holds a result of "
                                                  "another unit of this round; name a file of the review folder"))
            continue
        if not inside(path, root):
            refusals.append(Refusal(name, OUTSIDE, f"{artefact.source!r} resolves outside the review folder; name a file "
                                                   "inside it, not a path that leaves it or a link out of it"))
            continue
        pattern = denied_by(relative, declaration.deny)
        if pattern is not None:
            refusals.append(Refusal(name, DENIED, f"{relative!r} matches the deny pattern {pattern!r}; no session may read it"))
            continue
        if not reader.isfile(path):
            hint = f"; run its producer {artefact.producer!r} first" if artefact.producer else ""
            refusals.append(Refusal(name, UNREADABLE, f"{relative!r} is not a file of the review folder{hint}"))
            continue
        measured, refusal = measure(artefact, relative, reader.read(path))
        if refusal is not None:
            refusals.append(refusal)
        else:
            found.append(measured)
    if refusals:
        raise Refused(refusals)
    return Catalogue(tuple(found))


def measure(artefact: decl.Artefact, relative: str, data: bytes) -> Tuple[Optional[Measured], Optional[Refusal]]:
    digest = hashlib.sha256(data).hexdigest()
    if artefact.kind == "image":
        header = image_size(data)
        if header is None:
            return None, Refusal(artefact.name, NOT_IMAGE, f"{relative!r} is not a PNG or JPEG image")
        media, width, height = header
        return Measured(artefact.name, "image", relative, digest, image_tokens(width, height), False, data, media,
                        (width, height)), None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, Refusal(artefact.name, NOT_TEXT, f"{relative!r} is not UTF-8 text; declare it as an image if it is one")
    recorded = artefact.tokens
    return Measured(artefact.name, artefact.kind, relative, digest, recorded if recorded is not None else len(text),
                    recorded is None, data), None
