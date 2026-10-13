#!/usr/bin/env python3
"""The locked-copper check: a board's critical-class copper, recorded before the routing round trip and compared after it.

The nets a board depends on are routed by hand and locked before an external
router is let loose on the rest, and nothing about the round trip -- KiCad's
exporter, the router, KiCad's importer -- is trusted to have left them alone.
So every track, arc, via and zone on a net in one of the board's critical net
classes is recorded immediately before export, and the imported board is
compared with that record: each recorded item must still be there, locked and
unchanged, and no critical-class net may carry an item the record does not
hold. Copper on any other net is the router's to place, and is ignored.

The critical nets at comparison are every net the record names as well as every
net the critical classes hold then, and every class the record names must still
be defined, so a change to class membership between the two -- a project file
rewritten by the import, or a different one given -- cannot hide added copper.
A record is of one board, taken with that board's own project file, and is
compared only with that board opened with that project file.

Which nets are in which class is asked of KiCad, through the same probe the
pre-order check uses to learn the Mains class, run on the board itself with its
project file, so the project file's assignments and patterns and any class the
layout file carries all count as KiCad applies them. The layout is read with
the pre-order check's own S-expression reader, in the one form KiCad writes
it; anything else fails by name rather than being taken as no copper. The record
is a working file, refused inside any design's folder so it is never committed
or copied as part of a design.

    locked_copper.py record  --board B.kicad_pcb --project B.kicad_pro --class NAME [--class NAME ...] --record FILE
    locked_copper.py compare --board B.kicad_pcb --project B.kicad_pro --record FILE

Every finding is one line of a fixed shape, a result line comes last, and the
exit status is the verdict: 0 when the record is written or the board matches
it, 1 when recording is refused or the board does not match, 2 when the check
cannot run at all, for example because a tool is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import sexpr  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402

#: What a record says it is, so a file of any other kind is not read as one.
FORMAT = "locked-copper record 1"

#: Each kind of item recorded, the layout keyword it is written under, and the
#: properties it is recorded by, in the order a report names them.
KINDS = {
    "track": ("segment", ("net", "layer", "start", "end", "width")),
    "arc": ("arc", ("net", "layer", "start", "mid", "end", "width")),
    "via": ("via", ("net", "at", "diameter", "drill", "layers")),
    "zone": ("zone", ("net", "layers", "outline")),
}
KIND_OF = {keyword: kind for kind, (keyword, _) in KINDS.items()}

#: Characters that cannot be written into the probe's condition or rule name.
UNWRITABLE = set("'\"\\")


class Unreadable(Exception):
    """A board, project file or record that cannot be read in the form KiCad or this check writes it."""


# --- Reading the layout ---------------------------------------------------------


def nanometres(value, what: str) -> int:
    """A length KiCad writes in millimetres, as the whole nanometres it holds internally."""
    try:
        return round(float(value) * 1_000_000)
    except (TypeError, ValueError) as error:
        raise Unreadable(f"{what} is '{value}', not a length in millimetres") from error


def point(node, what: str) -> List[int]:
    if not isinstance(node, list) or len(node) != 3:
        raise Unreadable(f"{what} is {sexpr.dump(node) if node is not None else 'missing'}, not one x and y")
    return [nanometres(node[1], what), nanometres(node[2], what)]


def one(node: list, keyword: str, what: str) -> list:
    """The single child list `keyword` of `node`, which KiCad writes exactly once."""
    found = sexpr.children(node, keyword)
    if len(found) != 1:
        raise Unreadable(f"{what} has {len(found) or 'no'} ({keyword} ...) where KiCad writes one")
    return found[0]


def locked(node: list, what: str) -> bool:
    flags = sexpr.children(node, "locked")
    if not flags:
        return False
    if len(flags) == 1 and len(flags[0]) == 2 and flags[0][1] in ("yes", "no"):
        return flags[0][1] == "yes"
    raise Unreadable(f"{what} marks its lock as {' '.join(sexpr.dump(flag) for flag in flags)}, "
                     "where KiCad writes (locked yes) or nothing")


def layer_names(node: list, what: str) -> List[str]:
    """The copper layers an item is on, from its (layer ...) or (layers ...), in a fixed order."""
    given = sexpr.children(node, "layer") + sexpr.children(node, "layers")
    if len(given) != 1 or len(given[0]) < 2 or any(isinstance(name, list) for name in given[0][1:]):
        raise Unreadable(f"{what} does not name its layers in one (layer ...) or (layers ...)")
    return sorted(str(name) for name in given[0][1:])


def outline(zone: list, what: str) -> List[list]:
    """A zone's outline as KiCad writes it: each (polygon (pts ...)), its corners and arcs in order.

    The fill is not part of the outline, since KiCad recomputes it on every
    refill; only what the designer drew is recorded.
    """
    polygons = sexpr.children(zone, "polygon")
    if not polygons:
        raise Unreadable(f"{what} has no (polygon ...) outline")
    shape = []
    for polygon in polygons:
        pts = one(polygon, "pts", what)
        corners = []
        for node in pts[1:]:
            if sexpr.head(node) == "xy":
                corners.append(point(node, f"{what} outline corner"))
            elif sexpr.head(node) == "arc":
                corners.append(["arc"] + [point(one(node, key, what), f"{what} outline arc {key}")
                                          for key in ("start", "mid", "end")])
            else:
                raise Unreadable(f"{what} outline holds {sexpr.dump(node)}, where KiCad writes (xy ...) or (arc ...)")
        shape.append(corners)
    return shape


def net_table(layout: list) -> Dict[str, str]:
    """The numbered net table an older layout file carries at its top level, number -> name; empty in KiCad 10's form."""
    return {str(node[1]): str(node[2]) for node in sexpr.children(layout, "net") if len(node) == 3}


def item_net(node: list, table: Dict[str, str], what: str) -> str:
    nets = sexpr.children(node, "net")
    if len(nets) > 1:
        raise Unreadable(f"{what} names its net {len(nets)} times")
    if not nets:
        return ""
    if len(nets[0]) != 2 or isinstance(nets[0][1], list):
        raise Unreadable(f"{what} names its net as {sexpr.dump(nets[0])}, where KiCad writes (net \"name\")")
    raw = str(nets[0][1])
    return table.get(raw, raw) if table and not isinstance(nets[0][1], sexpr.Quoted) else raw


def read_item(node: list, table: Dict[str, str]) -> dict:
    """One track, arc, via or zone, by the properties it is recorded by."""
    kind = KIND_OF[sexpr.head(node)]
    uuid = sexpr.child(node, "uuid")
    uuid = str(uuid[1]) if uuid is not None and len(uuid) > 1 else ""
    what = f"a {kind}" + (f" ({uuid})" if uuid else "")
    item = {"kind": kind, "net": item_net(node, table, what), "uuid": uuid}
    if kind in ("track", "arc"):
        layer = one(node, "layer", what)
        if len(layer) != 2 or isinstance(layer[1], list):
            raise Unreadable(f"{what} names its layer as {sexpr.dump(layer)}, where KiCad writes one (layer \"name\")")
        item["layer"] = str(layer[1])
        for key in ("start", "mid", "end") if kind == "arc" else ("start", "end"):
            item[key] = point(one(node, key, what), f"{what} {key}")
        width = one(node, "width", what)
        item["width"] = nanometres(width[1] if len(width) == 2 else None, f"{what} width")
    elif kind == "via":
        item["at"] = point(one(node, "at", what), f"{what} position")
        size = one(node, "size", what)
        diameter: list = [nanometres(size[1] if len(size) == 2 else None, f"{what} diameter")]
        padstack = sexpr.child(node, "padstack")
        if padstack is not None:
            for layer in sexpr.children(padstack, "layer"):
                inner = sexpr.child(layer, "size")
                if len(layer) > 1 and inner is not None:
                    diameter.append([str(layer[1]), nanometres(inner[1] if len(inner) == 2 else None,
                                                               f"{what} diameter on {layer[1]}")])
        item["diameter"] = diameter
        drill = one(node, "drill", what)
        item["drill"] = nanometres(drill[1] if len(drill) > 1 else None, f"{what} drill")
        item["layers"] = layer_names(node, what)
    else:
        item["layers"] = layer_names(node, what)
        item["outline"] = outline(node, what)
    item["locked"] = locked(node, what)
    return item


def read_layout(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as handle:
            tree = sexpr.parse_one(handle.read())
    except (OSError, UnicodeDecodeError, sexpr.SexprError) as error:
        raise Unreadable(f"the board {path} cannot be read ({error})") from error
    if sexpr.head(tree) != "kicad_pcb":
        raise Unreadable(f"{path} is not a KiCad layout: it begins ({sexpr.head(tree) or '?'} ...), not (kicad_pcb ...)")
    return tree


def copper(layout: list, path: str) -> List[dict]:
    """Every track, arc, via and zone the layout carries at its top level, each read in full."""
    table = net_table(layout)
    found = []
    for node in layout:
        if sexpr.head(node) in KIND_OF:
            try:
                found.append(read_item(node, table))
            except Unreadable as error:
                raise Unreadable(f"the board {path} cannot be read: {error}") from error
    return found


def defined_classes(project: dict, layout: list) -> Set[str]:
    """The net classes a design defines: those in its project file and those its layout file carries."""
    classes = board_check.setting(project, "net_settings", "classes")
    named = {str(entry.get("name")) for entry in classes if isinstance(entry, dict)} if isinstance(classes, list) else set()
    return named | {str(block[1]) for block in sexpr.children(layout, "net_class") if len(block) > 1}


def class_name_problems(classes: Sequence[str]) -> List[Tuple[str, str]]:
    """Every way a list of critical classes cannot be put to KiCad as given: (class, why)."""
    problems = [(netclass, "a class name holding a quote or backslash cannot be put to KiCad in a rule; rename the class")
                for netclass in classes if UNWRITABLE & set(netclass)]
    if len(set(classes)) != len(classes):
        problems.append((", ".join(classes), "a critical class is named more than once; name each once"))
    return problems


def own_project(board: str, project: str) -> Optional[str]:
    """Why `project` is not the project file KiCad opens `board` with, or None when it is."""
    beside = os.path.splitext(board)[0] + ".kicad_pro"
    if os.path.realpath(project) == os.path.realpath(beside):
        return None
    return (f"KiCad opens {board} with the project file {beside} beside it, not {project}, so class membership "
            "read with the one given would not be the board's own; give the board's own project file")


def read_project(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            project = json.load(handle, object_pairs_hook=board_check.unique_keys)
    except board_check.DuplicateKey as error:
        raise Unreadable(f"the project file {path} gives the key '{error}' more than once in one object") from error
    except (OSError, ValueError) as error:
        raise Unreadable(f"the project file {path} cannot be read ({error})") from error
    if not isinstance(project, dict):
        raise Unreadable(f"the project file {path} is not a JSON object")
    return project


# --- Asking KiCad which nets are critical -------------------------------------------


def members(kicad_cli: str, board: str, project: str, layout: list, classes: Sequence[str]) -> Dict[str, Set[str]]:
    """The nets KiCad places in each of `classes` on the board itself, opened with its project file."""
    with tempfile.TemporaryDirectory(prefix="locked-copper-") as work:
        shutil.copy2(board, os.path.join(work, "board.kicad_pcb"))
        shutil.copy2(project, os.path.join(work, "board.kicad_pro"))
        found, why = board_check.class_members(kicad_cli, work, "board", classes, board_check.layout_nets(layout),
                                               secrets.token_hex(8))
    if found is None:
        raise Unreadable(f"KiCad could not say which nets of {board} are in {', '.join(classes)}: {why}")
    return found


# --- Describing items ---------------------------------------------------------------


def mm(value: int) -> str:
    return board_check.coordinate(value / 1_000_000)


def where(xy: List[int]) -> str:
    return f"({mm(xy[0])}, {mm(xy[1])})"


def shown(key: str, value) -> str:
    """One recorded property, as a report names it."""
    if key in ("start", "mid", "end", "at"):
        return f"{where(value)} mm"
    if key in ("width", "drill"):
        return f"{mm(value)} mm"
    if key == "diameter":
        return f"{mm(value[0])} mm" + "".join(f", {layer} {mm(size)} mm" for layer, size in value[1:])
    if key == "layers":
        return " ".join(value)
    if key == "outline":
        rings = []
        for ring in value:
            corners = [where(c) if c[0] != "arc" else "arc " + " ".join(where(p) for p in c[1:]) for c in ring]
            rings.append(" ".join(corners))
        return "; ".join(rings) + " mm"
    return str(value)


def describe(item: dict) -> str:
    kind, net = item["kind"], item["net"]
    if kind == "track":
        text = f"track [{net}] on {item['layer']} from {shown('start', item['start'])} to {shown('end', item['end'])}, width {shown('width', item['width'])}"
    elif kind == "arc":
        text = (f"arc [{net}] on {item['layer']} from {shown('start', item['start'])} through {shown('mid', item['mid'])} "
                f"to {shown('end', item['end'])}, width {shown('width', item['width'])}")
    elif kind == "via":
        text = (f"via [{net}] at {shown('at', item['at'])} on {shown('layers', item['layers'])}, diameter "
                f"{shown('diameter', item['diameter'])}, drill {shown('drill', item['drill'])}")
    else:
        first = item["outline"][0][0] if item["outline"] and item["outline"][0] else None
        corner = f" with its first corner at {where(first if first[0] != 'arc' else first[1])} mm" if first else ""
        text = f"zone [{net}] on {shown('layers', item['layers'])}{corner}"
    return text + (f" (uuid {item['uuid']})" if item.get("uuid") else "")


# --- Comparing --------------------------------------------------------------------


def key(item: dict) -> str:
    """Everything an item is recorded by except whether it is locked, as one comparable value."""
    return json.dumps([item["kind"]] + [item[name] for name in KINDS[item["kind"]][1]])


def differences(was: dict, now: dict) -> List[str]:
    return [f"{name} {shown(name, was[name])} -> {shown(name, now[name])}"
            for name in KINDS[was["kind"]][1] if was[name] != now[name]]


def compare_items(recorded: List[dict], current: List[dict]) -> List[Tuple[str, str, str]]:
    """Every way the board's critical-class copper departs from the record: (finding, item, detail).

    Items are matched by every recorded property, as a count, so an added item
    identical to a recorded one is still an addition. Where several identical
    items are present, a locked one is matched first, so the one left over is
    the addition and an unlocked copy cannot stand in for the locked original.
    Each recorded item left unmatched is paired, where it can be, with a left-over
    item of the same kind -- the same item by uuid first, on whichever critical
    net it now is, then the one on the same net differing in fewest properties --
    and reported as changed; whatever is still unpaired is missing or added.
    """
    findings = []
    waiting: Dict[str, List[dict]] = {}
    for item in sorted(current, key=lambda item: not item["locked"]):
        waiting.setdefault(key(item), []).append(item)
    unmatched = []
    for item in recorded:
        pool = waiting.get(key(item))
        if pool:
            now = pool.pop(0)
            if not now["locked"]:
                findings.append(("UNLOCKED", describe(item),
                                 "was locked when recorded and is not locked now; lock it, and if it was moved, route "
                                 "it again deliberately and record afresh"))
        else:
            unmatched.append(item)
    left = [item for pool in waiting.values() for item in pool]
    for item in unmatched:
        twin = next((now for now in left if item["uuid"] and now["kind"] == item["kind"]
                     and now["uuid"] == item["uuid"]), None)
        same = [now for now in left if now["kind"] == item["kind"] and now["net"] == item["net"]]
        if twin is None and same:
            twin = min(same, key=lambda now: len(differences(item, now)))
        if twin is None:
            findings.append(("MISSING", describe(item), "is in the record but not on the board"))
            continue
        left.remove(twin)
        changed = differences(item, twin)
        if not twin["locked"]:
            changed.append("locked yes -> no")
        findings.append(("CHANGED", describe(item), "; ".join(changed)))
    for item in left:
        findings.append(("ADDED", describe(item), "is on a critical-class net but not in the record, so it was placed "
                         "after recording -- by the router or the importer, or by hand without a fresh record"))
    return findings


# --- The record ---------------------------------------------------------------------


#: Everything a record holds, as recording writes it and comparing reads it.
RECORD_KEYS = ("format", "board", "classes", "nets", "items")


def write_record(path: str, board: str, classes: Sequence[str], nets: Dict[str, Set[str]], items: List[dict]) -> None:
    """Write the record whole or not at all, so a failed write never leaves a partial record to compare against."""
    document = {
        "format": FORMAT,
        "board": os.path.realpath(board),
        "classes": list(classes),
        "nets": {netclass: sorted(nets[netclass]) for netclass in classes},
        "items": items,
    }
    handle, partial = tempfile.mkstemp(prefix=".locked-copper-", dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=1)
            stream.write("\n")
        os.replace(partial, path)
    except BaseException:
        if os.path.exists(partial):
            os.remove(partial)
        raise


def _length(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _point(value) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(_length(part) for part in value)


def _corner(value) -> bool:
    return _point(value) or (isinstance(value, list) and len(value) == 4 and value[0] == "arc"
                             and all(_point(part) for part in value[1:]))


def _names(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(name, str) for name in value)


#: The form each recorded property takes in a record, as recording writes it.
FORMS = {
    "net": lambda value: isinstance(value, str) and bool(value),
    "uuid": lambda value: isinstance(value, str),
    "locked": lambda value: isinstance(value, bool),
    "layer": lambda value: isinstance(value, str) and bool(value),
    "layers": _names,
    "start": _point, "mid": _point, "end": _point, "at": _point,
    "width": _length, "drill": _length,
    "diameter": lambda value: isinstance(value, list) and bool(value) and _length(value[0]) and all(
        isinstance(part, list) and len(part) == 2 and isinstance(part[0], str) and _length(part[1]) for part in value[1:]),
    "outline": lambda value: isinstance(value, list) and bool(value) and all(
        isinstance(ring, list) and ring and all(_corner(corner) for corner in ring) for ring in value),
}


def read_record(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle, object_pairs_hook=board_check.unique_keys)
    except board_check.DuplicateKey as error:
        raise Unreadable(f"the record {path} gives the key '{error}' more than once in one object") from error
    except (OSError, ValueError) as error:
        raise Unreadable(f"the record {path} cannot be read ({error})") from error
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise Unreadable(f"{path} is not a locked-copper record (it does not say it is a {FORMAT})")
    if set(document) != set(RECORD_KEYS):
        raise Unreadable(f"the record {path} holds {', '.join(sorted(map(str, document)))}, where recording writes "
                         f"exactly {', '.join(sorted(RECORD_KEYS))}")
    board, classes, nets, items = (document[name] for name in ("board", "classes", "nets", "items"))
    if not isinstance(board, str) or not os.path.isabs(board):
        raise Unreadable(f"the record {path} does not name the board it was taken of by its full path")
    if not isinstance(classes, list) or not classes or not all(isinstance(name, str) and name for name in classes):
        raise Unreadable(f"the record {path} names no critical classes")
    problems = class_name_problems(classes)
    if problems:
        raise Unreadable(f"the record {path} names its classes in a form recording refuses "
                         f"({'; '.join(f'{name}: {why}' for name, why in problems)})")
    if not isinstance(nets, dict) or set(nets) != set(classes) or not all(
            isinstance(names, list) and all(isinstance(name, str) and name for name in names) for names in nets.values()):
        raise Unreadable(f"the record {path} does not give the nets of each of its classes, {', '.join(classes)}, "
                         "and of no other")
    if not isinstance(items, list):
        raise Unreadable(f"the record {path} holds no list of items")
    critical = set().union(*nets.values())
    for index, item in enumerate(items):
        kind = item.get("kind") if isinstance(item, dict) else None
        wanted = ("kind", "net", "uuid", "locked") + (KINDS[kind][1] if kind in KINDS else ())
        if kind not in KINDS or set(item) != set(wanted) or not all(FORMS[name](item[name]) for name in wanted[1:]):
            raise Unreadable(f"the record {path} item {index + 1} is not a track, arc, via or zone in the form recording writes")
        if item["net"] not in critical:
            raise Unreadable(f"the record {path} item {index + 1} is on the net {item['net']}, which none of its classes holds")
        if not item["locked"]:
            raise Unreadable(f"the record {path} item {index + 1} is not locked, where recording takes only locked items")
    return document


# --- The two commands -------------------------------------------------------------------


def inside(path: str, folder: str) -> bool:
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return os.path.commonpath([path, folder]) == folder


def design_folder(path: str, board: str) -> Optional[str]:
    """The design's folder `path` would sit in, at any depth, or None.

    That is the board's own folder, or any folder above `path` holding a
    project file, whichever design it belongs to.
    """
    own = os.path.dirname(os.path.realpath(board))
    if inside(path, own):
        return own
    folder = os.path.dirname(os.path.realpath(path))
    while True:
        try:
            if any(name.endswith(".kicad_pro") for name in os.listdir(folder)):
                return folder
        except OSError:
            pass
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def record(board: str, project: str, classes: Sequence[str], out_path: str, kicad_cli: str, out) -> int:
    """Record every track, arc, via and zone on the board's critical-class nets; the exit status."""
    refusals: List[Tuple[str, str]] = []
    folder = design_folder(out_path, board)
    if folder is not None:
        refusals.append((out_path, "the record is a working file and is never kept in a design's folder, where it could be "
                                   f"committed and copied as part of the design; {folder} holds a design's project file, "
                                   "so write the record outside it"))
    why = own_project(board, project)
    if why is not None:
        refusals.append((project, why))
    if refusals:
        for what, detail in refusals:
            print(f"REFUSED | {clean(what)} | {clean(detail)}", file=out)
        print("RESULT | REFUSED | no record was written", file=out)
        return 1
    layout = read_layout(board)
    defined = defined_classes(read_project(project), layout)
    refusals = [(netclass, f"the design defines no net class of this name (it defines {', '.join(sorted(defined)) or 'none'}); "
                           "name each critical class exactly as the design does")
                for netclass in classes if netclass not in defined]
    refusals += class_name_problems(classes)
    if refusals:
        for what, detail in refusals:
            print(f"REFUSED | {clean(what)} | {clean(detail)}", file=out)
        print("RESULT | REFUSED | no record was written", file=out)
        return 1
    items = copper(layout, board)
    nets = members(kicad_cli, board, project, layout, classes)
    critical = set().union(*nets.values())
    kept = [item for item in items if item["net"] in critical]
    loose = [item for item in kept if not item["locked"]]
    for item in loose:
        print(f"UNLOCKED | {clean(describe(item))} | every item on a critical-class net is locked before export; "
              "lock it and record again", file=out)
    if loose:
        print(f"RESULT | REFUSED | {len(loose)} of {len(kept)} critical-class items are not locked, so no record was written",
              file=out)
        return 1
    try:
        write_record(out_path, board, classes, nets, kept)
    except OSError as error:
        print(f"REFUSED | {clean(out_path)} | the record cannot be written there ({clean(str(error))})", file=out)
        print("RESULT | REFUSED | no record was written", file=out)
        return 1
    for netclass in classes:
        print(f"CLASS | {clean(netclass)} | {len(nets[netclass])} net{'s' if len(nets[netclass]) != 1 else ''}"
              + (f" | {clean(', '.join(sorted(nets[netclass])))}" if nets[netclass] else ""), file=out)
    print(f"RESULT | RECORDED | {len(kept)} locked items on {len(critical)} critical-class nets | {clean(out_path)}", file=out)
    return 0


def compare(board: str, project: str, record_path: str, kicad_cli: str, out) -> int:
    """Compare the board's critical-class copper with the record; the exit status."""
    document = read_record(record_path)
    mismatches = []
    if document["board"] != os.path.realpath(board):
        mismatches.append((record_path, f"the record was taken of {document['board']}, not of {os.path.realpath(board)}; "
                                        "a board is compared only with its own record, so record this board afresh"))
    why = own_project(board, project)
    if why is not None:
        mismatches.append((project, why))
    classes = document["classes"]
    if mismatches:
        for what, detail in mismatches:
            print(f"MISMATCH | {clean(what)} | {clean(detail)}", file=out)
        print(f"RESULT | FAIL | the board, project file and record given are not one board's, so nothing in "
              f"{', '.join(classes)} is taken as a pass", file=out)
        return 1
    layout = read_layout(board)
    defined = defined_classes(read_project(project), layout)
    findings = [("UNDEFINED", netclass, "the record names this critical class and the design no longer defines it, so its "
                                        "nets' copper is no longer protected; restore the class, or record afresh")
                for netclass in classes if netclass not in defined]
    nets = members(kicad_cli, board, project, layout, classes)
    critical = set().union(*nets.values(), *document["nets"].values())
    current = [item for item in copper(layout, board) if item["net"] in critical]
    findings += compare_items(document["items"], current)
    for finding, item, detail in findings:
        print(f"{finding} | {clean(item)} | {clean(detail)}", file=out)
    if findings:
        print(f"RESULT | FAIL | {len(findings)} difference{'s' if len(findings) != 1 else ''} from the record of "
              f"{len(document['items'])} items in {', '.join(classes)}", file=out)
        return 1
    print(f"RESULT | PASS | all {len(document['items'])} recorded items present, locked and unchanged, and none added, "
          f"in {', '.join(classes)}", file=out)
    return 0


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    commands = parser.add_subparsers(dest="command", required=True)
    taking = commands.add_parser("record", help="record the critical-class copper before export")
    taking.add_argument("--class", dest="classes", action="append", required=True, metavar="NAME",
                        help="a critical net class, as the design names it; give each one")
    checking = commands.add_parser("compare", help="compare the imported board with the record")
    for sub in (taking, checking):
        sub.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
        sub.add_argument("--project", required=True, help="the layout's project file (.kicad_pro)")
        sub.add_argument("--record", required=True, help="the record: written by record, read by compare")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        version = board_check.require_kicad(args.kicad_cli)
        with tempfile.TemporaryDirectory(prefix="locked-copper-kicad-") as home:
            board_check.KICAD_ENVIRONMENT = board_check.isolate_kicad(args.kicad_cli, version, home)
            try:
                if args.command == "record":
                    return record(args.board, args.project, args.classes, args.record, args.kicad_cli, out)
                return compare(args.board, args.project, args.record, args.kicad_cli, out)
            finally:
                board_check.KICAD_ENVIRONMENT = None
    except Unreadable as error:
        print(f"UNREADABLE | {clean(str(error))}", file=out)
        print(f"RESULT | {'REFUSED' if args.command == 'record' else 'FAIL'} | the input cannot be read, "
              "so nothing is taken as a pass", file=out)
        return 1
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
