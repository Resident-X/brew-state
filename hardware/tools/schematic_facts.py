#!/usr/bin/env python3
"""The nets, parts and sheets of a schematic, read without KiCad: from the netlist KiCad exports and from the schematic files.

The schematic review gives a verdict for every net, every part and every sheet of a schematic. The nets and the parts come
from the netlist the round's first step exports, and the sheets from the schematic's own files: the root sheet is named by the
design, the project file's name, and a sheet below it by its Sheetname property, a sheet below that one by the names leading
to it, joined by `/`. A part is a placed symbol's reference, by the references its instances give for the project, a power
symbol or flag (a reference that begins with `#`) not being a part. The netlist also names its sheets, and the parts and the
sheets it holds are what the folder command holds against the committed schematic's.

Every function raises `FactsProblem`, naming the file and what is wrong, for a file that cannot be read.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Dict, FrozenSet, List, NamedTuple, Optional, Sequence, Set, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import sexpr  # noqa: E402

#: The netlist, in the root of a review folder.
NETLIST_FILE = "review.net"
PROJECT_SUFFIX = ".kicad_pro"
SCHEMATIC_SUFFIX = ".kicad_sch"


class FactsProblem(ValueError):
    """A netlist or schematic that cannot be read for its nets, parts and sheets."""


class Names(NamedTuple):
    """What a netlist or a schematic names: its nets, parts and sheets."""

    nets: FrozenSet[str]
    parts: FrozenSet[str]
    sheets: FrozenSet[str]


def text_of(node: Optional[list]) -> Optional[str]:
    return str(node[1]) if node is not None and len(node) > 1 and not isinstance(node[1], list) else None


def sheet_of_netlist(name: str, design: str) -> str:
    """The name the schematic gives a sheet the netlist names `/` (the root, which the design names) or `/Power/Reg/`."""
    inner = name.strip("/")
    return design if not inner else inner


def netlist_names(text: str, design: str, where: str = "the netlist") -> Names:
    """The nets, parts and sheets a netlist holds. A net with no name, as a netlist never writes, is left out. Raises
    FactsProblem for a text that is not a netlist, or one that holds no component and no net."""
    try:
        root = sexpr.parse_one(text)
    except (sexpr.SexprError, IndexError, ValueError, RecursionError) as error:
        raise FactsProblem(f"{where} cannot be read as KiCad's netlist ({error})")
    if sexpr.head(root) != "export":
        raise FactsProblem(f"{where} is not a KiCad netlist: it does not begin `(export`")
    parts: Set[str] = set()
    for group in sexpr.children(root, "components"):
        for comp in sexpr.children(group, "comp"):
            ref = text_of(sexpr.child(comp, "ref"))
            if ref:
                parts.add(ref)
    nets: Set[str] = set()
    for group in sexpr.children(root, "nets"):
        for net in sexpr.children(group, "net"):
            name = text_of(sexpr.child(net, "name"))
            if name:
                nets.add(name)
    sheets: Set[str] = set()
    for group in sexpr.children(root, "design"):
        for sheet in sexpr.children(group, "sheet"):
            name = text_of(sexpr.child(sheet, "name"))
            if name is not None:
                sheets.add(sheet_of_netlist(name, design))
    if not parts and not nets:
        raise FactsProblem(f"{where} holds no component and no net")
    return Names(frozenset(nets), frozenset(parts), frozenset(sheets))


def references(symbol: list, project: str) -> List[str]:
    """The references one placed symbol has: those its instances give for `project`, or for any project when none is given for
    it, else its Reference property."""
    found: Dict[str, List[str]] = {}
    for instances in sexpr.children(symbol, "instances"):
        for entry in sexpr.children(instances, "project"):
            name = str(entry[1]) if len(entry) > 1 else ""
            for path in sexpr.children(entry, "path"):
                ref = text_of(sexpr.child(path, "reference"))
                if ref:
                    found.setdefault(name, []).append(ref)
    chosen = found.get(project) or [ref for refs in found.values() for ref in refs]
    if chosen:
        return chosen
    prop = next((p for p in sexpr.children(symbol, "property") if len(p) > 2 and p[1] == "Reference"), None)
    return [str(prop[2])] if prop else []


def sheet_file_of(sheet: list) -> Optional[str]:
    named = [p for p in sexpr.children(sheet, "property") if len(p) > 1 and p[1] == "Sheetfile"]
    if len(named) != 1 or len(named[0]) < 3 or isinstance(named[0][2], list):
        return None
    return str(named[0][2])


def schematic_names(read: Callable[[str], Optional[str]], design: str) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """The parts and the sheets of the schematic whose root file is `<design>.kicad_sch`, `read` giving the text of a schematic
    file by its path from the design's folder (None for a file that is not there). A sheet placed twice is two sheets, one under
    each name it is placed under. Raises FactsProblem for a root file or a sheet file that cannot be read."""
    parts: Set[str] = set()
    sheets: List[str] = []

    def walk(path: str, chain: Tuple[str, ...], ancestry: Tuple[str, ...]) -> None:
        text = read(path)
        if text is None:
            raise FactsProblem(f"the schematic file {path} is not among the files given")
        try:
            tree = sexpr.parse_one(text)
        except (sexpr.SexprError, IndexError, ValueError, RecursionError) as error:
            raise FactsProblem(f"the schematic file {path} cannot be read ({error})")
        sheets.append("/".join(chain) if chain else design)
        for symbol in sexpr.children(tree, "symbol"):
            for ref in references(symbol, design):
                if not ref.startswith("#"):
                    parts.add(ref)
        if path in ancestry:
            return
        for sheet in sexpr.children(tree, "sheet"):
            target = sheet_file_of(sheet)
            title = next((str(p[2]) for p in sexpr.children(sheet, "property") if len(p) > 2 and p[1] == "Sheetname"), "")
            if target is None or not title:
                raise FactsProblem(f"a sheet of {path} names no one file or has no name, so the schematic's sheets cannot be told")
            if "/" in title or "\\" in title:
                raise FactsProblem(f"the sheet {title!r} of {path} has a slash in its name, which cannot be told from a sheet "
                                   "below a sheet; rename the sheet")
            walk(os.path.normpath(os.path.join(os.path.dirname(path), target)).replace(os.sep, "/"), chain + (title,),
                 ancestry + (path,))

    walk(design + SCHEMATIC_SUFFIX, (), ())
    return frozenset(parts), frozenset(sheets)


def design_name(files: Sequence[str]) -> str:
    """The design's name from the file names of its folder: the stem of its one project file."""
    found = [name[:-len(PROJECT_SUFFIX)] for name in files if "/" not in name and name.endswith(PROJECT_SUFFIX)]
    if len(found) != 1:
        raise FactsProblem(f"the design folder holds {len(found)} project files; it must hold the one")
    return found[0]


def folder_schematic(folder: str, design: str) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """The parts and sheets of the schematic in a design's folder on disk."""
    def read(path: str) -> Optional[str]:
        target = os.path.join(folder, path)
        if not os.path.isfile(target):
            return None
        try:
            with open(target, encoding="utf-8") as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError) as error:
            raise FactsProblem(f"the schematic file {path} cannot be read ({error})")
    return schematic_names(read, design)


def folder_names(folder: str) -> Set[str]:
    """Every net, part and sheet a review folder names, from its netlist and its schematic files; empty when the folder cannot
    be read for them, so that a caller that asks cannot tell and does not refuse."""
    import review_folder
    try:
        design = review_folder.design_in(folder)
        project = design_name(os.listdir(os.path.join(folder, design)))
        with open(os.path.join(folder, NETLIST_FILE), encoding="utf-8") as handle:
            named = netlist_names(handle.read(), project)
        parts, sheets = folder_schematic(os.path.join(folder, design), project)
    except (OSError, UnicodeDecodeError, FactsProblem, review_folder.ReviewFolderProblem):
        return set()
    return set(named.nets) | set(named.parts) | set(named.sheets) | set(parts) | set(sheets)
