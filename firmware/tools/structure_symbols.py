"""What it means to name a plant structure, and which names belong to which.

The plant-model seam holds only while nothing reaches around it, so two checks
need to agree on what "a structure's own symbol" is: the encapsulation check,
which fails the build when a model consumer names one, and the exclusivity
check, which requires a linked artefact to carry one structure's symbols and no
other's. This module is the one place that answers it, so the two cannot drift.

The answer is read out of the structures themselves rather than written down as
a list of names. A hand-maintained list goes stale the moment a structure gains
a coefficient, and a check that has gone stale is a check that passes while the
property it names is broken.

Two kinds of name are distinguished, because they leak differently:

  * A *member* is a field of a structure's state or parameter record. It leaks
    only through a member access -- `record.brew_heater_power_w` -- so it is
    reported there and nowhere else. A consumer is entitled to a local variable
    that happens to share a field's name.
  * A *declaration* is a function, type, macro or enumerator the structure's
    header declares at the top level. Naming one at all is reaching into the
    structure, so it is reported wherever it appears.

Names the seam's own headers already carry are not a structure's to own, so
they are excluded from both sets. That errs towards silence: a name shared with
the neutral vocabulary is not reported even from a structure's record. The
alternative errs towards reporting a consumer's own local variable as a
violation, which would make the check something to be worked around.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from vendor_symbols import Violation, strip_comments_and_strings

#: The file a structure directory is recognised by. A directory under the plant
#: root that supplies this header is a structure; one that does not -- the
#: shared parameter loader, for instance -- is not.
STRUCTURE_HEADER = "plant_structure.h"

#: The headers that carry the seam's own vocabulary. Everything they name is
#: neutral: it belongs to the interface rather than to any structure.
#:
#: The actuation vocabulary is among them because it belongs to the machine and
#: is named by every structure that states which of its channels it answers. Its
#: names would otherwise be read as that structure's own, and the seam headers
#: carrying the same set would be reported for reaching into a structure.
NEUTRAL_HEADERS = ("plant_model.h", "plant_types.h", "machine_actuation.h")

_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
#: The declared name of one field: the identifier a member declaration ends on.
_FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[[^\]]*\])?\s*;")
_MEMBER_ACCESS = re.compile(r"(?:\.|->)\s*([A-Za-z_][A-Za-z0-9_]*)\b")
_DEFINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_TYPEDEF_TAIL = re.compile(r"\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*;")
_CALLABLE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')
_INCLUDE_DIRECTIVE = re.compile(r"^\s*#\s*include\b")

#: Words that appear in a declaration without being declared by it.
_KEYWORDS = frozenset(
    """
    auto break case char const continue default do double else enum extern float for goto if
    inline int long register restrict return short signed sizeof static struct switch typedef
    union unsigned void volatile while _Bool _Complex _Imaginary _Alignas _Alignof _Atomic
    _Generic _Noreturn _Static_assert _Thread_local bool true false offsetof size_t
    int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t NULL
    """.split()
)


@dataclass(frozen=True)
class Structure:
    """One plant structure, and the names it owns."""

    name: str
    directory: str
    header: str
    #: Fields of its state and parameter records, reported only on access.
    members: frozenset[str]
    #: Functions, types, macros and enumerators its header declares.
    declarations: frozenset[str]


def neutral_names(include_dir: str, exclude: tuple[str, ...] = ()) -> frozenset[str]:
    """Every identifier the seam's own headers carry.

    Read from the headers rather than listed here, for the same reason the
    structures' names are: a vocabulary that has to be kept in step by hand
    will not be.

    `exclude` drops a header from the neutral set, which is what lets that
    header itself be inspected. A header cannot make a name neutral by naming
    it -- judging the seam header against a vocabulary read out of the seam
    header would clear it of anything it did.
    """
    names: set[str] = set()
    for header in NEUTRAL_HEADERS:
        if header in exclude:
            continue
        path = os.path.join(include_dir, header)
        if not os.path.isfile(path):
            raise SystemExit(f"structure_symbols: no seam header at {path}")
        with open(path, "r", encoding="utf-8") as handle:
            cleaned = strip_comments_and_strings(handle.read())
        names.update(_IDENTIFIER.findall(cleaned))
    return frozenset(names)


def _record_regions(cleaned: str) -> list[tuple[int, int]]:
    """The spans of every struct and union body, as [begin, end) offsets.

    Enum bodies are deliberately not included: an enumerator is used bare
    rather than through a member access, so it belongs with the declarations.
    """
    regions: list[tuple[int, int]] = []
    for match in re.finditer(r"\b(struct|union)\b[^;{]*\{", cleaned):
        begin = match.end()
        depth = 1
        index = begin
        while index < len(cleaned) and depth > 0:
            if cleaned[index] == "{":
                depth += 1
            elif cleaned[index] == "}":
                depth -= 1
            index += 1
        if depth == 0:
            regions.append((begin, index - 1))
    return regions


def _enum_regions(cleaned: str) -> list[tuple[int, int]]:
    """The spans of every enum body, whose enumerators are top-level names."""
    regions: list[tuple[int, int]] = []
    for match in re.finditer(r"\benum\b[^;{]*\{", cleaned):
        begin = match.end()
        end = cleaned.find("}", begin)
        if end != -1:
            regions.append((begin, end))
    return regions


def _blank_define_replacements(cleaned: str) -> str:
    """Blank what a `#define` expands to, keeping the name it declares.

    A macro's replacement text is made of names the header uses, not names it
    declares -- `#define X SET_OF(Y)` declares X, and says that SET_OF and Y are
    somebody else's. Read whole, it would make every name a structure's macro
    reaches for look like the structure's own, and the header those names really
    come from would then be reported for naming them.

    Blanked rather than removed so that every offset into the source still
    points where it did: the record and enum spans are found on this same text.
    """
    kept: list[str] = []
    continuing = False
    # Split after each newline rather than on it, so the line endings are
    # carried through untouched and every offset lands where it did. Rebuilding
    # from splitlines() would drop a byte per line on a carriage-return tree and
    # move every span this text is later searched against.
    for line in re.split(r"(?<=\n)", cleaned):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        directive = re.match(r"^(\s*#\s*define\s+[A-Za-z_][A-Za-z0-9_]*)", body)
        if continuing:
            kept.append(" " * len(body) + ending)
        elif directive is not None:
            head = directive.group(1)
            kept.append(head + " " * (len(body) - len(head)) + ending)
        else:
            kept.append(line)
        # Only a directive's own line continues onto the next one for this
        # purpose. A stray trailing backslash elsewhere is not a replacement
        # spilling over, and reading it as one would blank a declaration.
        continuing = (continuing or directive is not None) and body.endswith("\\")
    return "".join(kept)


def owned_names(header_source: str, neutral: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Split a structure header's own names into declarations and members."""
    cleaned = strip_comments_and_strings(header_source)

    record_spans = _record_regions(cleaned)
    inside_record = set()
    for begin, end in record_spans:
        inside_record.update(range(begin, end))

    declarations: set[str] = set(_DEFINE.findall(cleaned))
    declarations.update(_TYPEDEF_TAIL.findall(cleaned))
    for begin, end in _enum_regions(cleaned):
        declarations.update(_IDENTIFIER.findall(cleaned[begin:end]))
    for match in _CALLABLE.finditer(_blank_define_replacements(cleaned)):
        if match.start(1) not in inside_record:
            declarations.add(match.group(1))

    members: set[str] = set()
    for begin, end in record_spans:
        for match in _IDENTIFIER.finditer(cleaned, begin, end):
            members.add(match.group(0))

    declarations -= _KEYWORDS | neutral
    members -= _KEYWORDS | neutral | declarations
    return frozenset(declarations), frozenset(members)


def shadowed_members(header_source: str, neutral: frozenset[str]) -> frozenset[str]:
    """Record fields the seam's own vocabulary already carries a name for.

    Such a field is owned by nobody. It is dropped from the structure's members
    to keep a consumer's local variable of the same name from being reported,
    and the cost is that reaching that one field goes undetected in every
    consumer at once. That is a narrowing nothing would otherwise announce, so
    it is refused here: a structure names its fields, and naming one after the
    interface's own vocabulary is the structure's to fix.
    """
    cleaned = strip_comments_and_strings(header_source)
    fields: set[str] = set()
    for begin, end in _record_regions(cleaned):
        for match in _FIELD.finditer(cleaned, begin, end):
            fields.add(match.group(1))
    return frozenset(field for field in fields if field in neutral and field not in _KEYWORDS)


def supplied_types(header_source: str) -> frozenset[str]:
    """The type names a structure supplies for the seam's signatures to use.

    These are the one sanctioned crossing: the seam declares its operations in
    terms of a state type and a parameter type, and whichever structure the
    build compiles is what defines them. Everything else a structure header
    declares is the structure's own business.
    """
    return frozenset(_TYPEDEF_TAIL.findall(strip_comments_and_strings(header_source)))


def discover(
    plant_root: str, include_dir: str, exclude_headers: tuple[str, ...] = ()
) -> list[Structure]:
    """Every structure under the plant root, with the names each one owns.

    `exclude_headers` is passed through to the neutral vocabulary, so a caller
    inspecting one of the seam's own headers can have that header's contents
    left out of what counts as neutral.
    """
    if not os.path.isdir(plant_root):
        raise SystemExit(f"structure_symbols: no plant root at {plant_root}")

    neutral = neutral_names(include_dir, exclude_headers)
    structures: list[Structure] = []
    for entry in sorted(os.listdir(plant_root)):
        directory = os.path.join(plant_root, entry)
        header = os.path.join(directory, STRUCTURE_HEADER)
        if not os.path.isdir(directory) or not os.path.isfile(header):
            continue
        with open(header, "r", encoding="utf-8") as handle:
            declarations, members = owned_names(handle.read(), neutral)
        structures.append(Structure(entry, directory, header, members, declarations))
    return structures


def exclusive_declarations(structures: list[Structure]) -> dict[str, frozenset[str]]:
    """Per structure, the declarations no other structure also makes.

    Shared names -- the operations every structure implements, the include
    guard they all use -- cannot tell two artefacts apart, so only what is
    unique to a structure can witness its presence or absence in one.
    """
    exclusive: dict[str, frozenset[str]] = {}
    for structure in structures:
        others: set[str] = set()
        for other in structures:
            if other.name != structure.name:
                others |= other.declarations
        exclusive[structure.name] = frozenset(structure.declarations - others)
    return exclusive


def find_violations(path: str, source: str, structures: list[Structure]) -> list[Violation]:
    """Report every way one source reaches a structure instead of the seam."""
    if not structures:
        raise SystemExit("structure_symbols: no structures to check against")

    cleaned = strip_comments_and_strings(source)
    original_lines = source.splitlines()
    directories = {structure.name for structure in structures}

    declaration_owner = {
        name: structure.name for structure in structures for name in structure.declarations
    }
    member_owner = {name: structure.name for structure in structures for name in structure.members}

    violations: list[Violation] = []
    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        if _INCLUDE_DIRECTIVE.match(line):
            original = original_lines[lineno - 1] if lineno <= len(original_lines) else ""
            match = _INCLUDE.match(original)
            if match is None:
                violations.append(
                    Violation(path, lineno, original.strip(), "include the check cannot resolve")
                )
                continue
            included = match.group(1)
            parts = included.replace("\\", "/").split("/")
            if parts[-1] == STRUCTURE_HEADER:
                violations.append(
                    Violation(path, lineno, included, "structure header include")
                )
            elif any(part in directories for part in parts[:-1]):
                violations.append(
                    Violation(path, lineno, included, "structure directory include")
                )
            continue

        accessed = set()
        for match in _MEMBER_ACCESS.finditer(line):
            accessed.add(match.group(1))
            owner = member_owner.get(match.group(1))
            if owner is not None:
                violations.append(
                    Violation(path, lineno, match.group(1), f"field of the {owner} structure")
                )

        for match in _IDENTIFIER.finditer(line):
            name = match.group(0)
            if name in accessed:
                continue
            owner = declaration_owner.get(name)
            if owner is not None:
                violations.append(
                    Violation(path, lineno, name, f"symbol of the {owner} structure")
                )

    return _deduplicate(violations)


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    """Collapse repeats of the same symbol at the same place, keeping order."""
    seen: set[tuple[str, int, str]] = set()
    unique: list[Violation] = []
    for violation in violations:
        key = (violation.path, violation.line, violation.symbol)
        if key in seen:
            continue
        seen.add(key)
        unique.append(violation)
    return unique
