#!/usr/bin/env python3
"""The locked-copper check: a board's rules confirmed, its critical-class copper locked, recorded before the routing round trip and compared after it.

The nets a board depends on are routed by hand and locked before an external
router is let loose on the rest, and nothing about the round trip -- KiCad's
exporter, the router, KiCad's importer -- is trusted to have left them alone.
So every track, arc, via and zone on a net in one of the board's critical net
classes is recorded immediately before export, and the imported board is
compared with that record: each recorded item must still be there, locked and
unchanged, and no critical-class net may carry an item the record does not
hold. Copper on any other net is the router's to place, and is ignored.

Before routing, the rules are confirmed by asking KiCad: its rule check is run
on the board with the board's own custom rules file and a marker rule appended
to it, which fires on the items of one net only if KiCad loaded the whole file,
and each named class's nets are then listed as KiCad places them. The lock command marks
every critical-class track, arc, via and zone locked in the board file, writing
the lock exactly where KiCad writes it and touching nothing else.

Every command but the rules confirmation acts on the board file itself, so each
refuses while KiCad's lock file beside the board shows it open in an editor.
A board must declare MAINS as present or none; on one that declares present,
Mains is a critical class, and every critical class named must hold a net.

The critical nets at comparison are every net the record names as well as every
net the critical classes hold then, and every class the record names must still
be defined, so a change to class membership between the two -- a project file
rewritten by the import, or a different one given -- cannot hide added copper.
A record is of one board, taken with that board's own project file, and is
compared only with that board opened with that project file.

Which nets are in which class is asked of KiCad, through the same class read
the pre-order check uses to learn the Mains class, on boards of one track per
net of the board carrying its project file and its layout's own classes, so the
project file's assignments and patterns and any class the layout file carries
all count as KiCad applies them, however large the board. The layout is read with
the pre-order check's own S-expression reader, in the one form KiCad writes
it; anything else fails by name rather than being taken as no copper. The record
is a working file, refused inside any design's folder so it is never committed
or copied as part of a design.

    locked_copper.py confirm --board B.kicad_pcb --project B.kicad_pro --class NAME [--class NAME ...]
    locked_copper.py lock    --board B.kicad_pcb --project B.kicad_pro --class NAME [--class NAME ...]
    locked_copper.py record  --board B.kicad_pcb --project B.kicad_pro --class NAME [--class NAME ...] --record FILE
    locked_copper.py compare --board B.kicad_pcb --project B.kicad_pro --record FILE

Every finding is one line of a fixed shape, a result line comes last, and the
exit status is the verdict: 0 when the rules are confirmed, the board is locked,
the record is written or the board matches it, 1 when any of those is refused
or fails, 2 when the check cannot run at all, for example because a tool is
missing.
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
from board_geometry import Unreadable, item_net, net_table  # noqa: E402,F401
from board_check import UNWRITABLE, CannotRun, clean  # noqa: E402

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


def editor_lock(board: str) -> str:
    """The lock file KiCad writes beside a board while an editor holds it open, and deletes when it closes it."""
    return os.path.join(os.path.dirname(board), "~" + os.path.basename(board) + ".lck")


def open_in_editor(board: str) -> Optional[Tuple[str, str]]:
    """(lock file, why) when KiCad's lock file shows the board open in an editor, or None."""
    lock = editor_lock(board)
    if not os.path.lexists(lock):
        return None
    return (lock, f"KiCad's lock file shows {board} open in an editor, which would work on a copy this command does "
                  "not see and save it back over the file; close the board in every editor, and if no KiCad process "
                  "is running the lock file is stale, left by a KiCad that did not close the board, so delete it")


def mains_problems(project: dict, path: str, classes: Sequence[str]) -> List[Tuple[str, str]]:
    """Why the board's mains declaration, or the classes named for it, cannot be acted on: (what, why).

    A board declaring mains names Mains among its critical classes, since its
    mains copper is the copper most worth protecting.
    """
    variables = project.get("text_variables")
    mains = variables.get("MAINS") if isinstance(variables, dict) else None
    if mains not in ("present", "none"):
        said = "is not set" if mains is None else f"is {json.dumps(mains)}"
        return [(f"{path} text_variables.MAINS",
                 f"the project variable MAINS {said}; every board declares it as exactly present or none, so set it")]
    if mains == "present" and "Mains" not in classes:
        return [("Mains", "MAINS is present, so Mains is a critical class and its copper is protected with the rest; "
                          "name it with --class Mains")]
    return []


def refused(refusals: List[Tuple[str, str]], result: str, out, finding: str = "REFUSED") -> int:
    """Report each refusal and the result line; the exit status for a refusal."""
    for what, detail in refusals:
        print(f"{finding} | {clean(what)} | {clean(detail)}", file=out)
    print(f"RESULT | {result}", file=out)
    return 1


# --- Asking KiCad which nets are critical -------------------------------------------


def members(kicad_cli: str, board: str, project: str, layout: list, classes: Sequence[str]) -> Dict[str, Set[str]]:
    """The nets of the board KiCad places in each of `classes`, with its project file and its layout's own classes."""
    with tempfile.TemporaryDirectory(prefix="locked-copper-") as work:
        found, why = board_check.class_members(kicad_cli, work, project, classes, board_check.layout_nets(layout),
                                               secrets.token_hex(8), board_check.layout_version(layout),
                                               board_check.class_blocks(layout))
    if found is None:
        raise Unreadable(f"KiCad could not say which nets of {board} are in {', '.join(classes)}: {why}")
    return found


def named_classes(board: str, project: str, classes: Sequence[str]) -> Tuple[list, List[Tuple[str, str]]]:
    """The board's layout, and every reason the classes named for it cannot be acted on before KiCad is asked."""
    layout = read_layout(board)
    settings = read_project(project)
    defined = defined_classes(settings, layout)
    refusals = mains_problems(settings, project, classes)
    refusals += [(netclass, f"the design defines no net class of this name (it defines {', '.join(sorted(defined)) or 'none'}); "
                            "name each critical class exactly as the design does")
                 for netclass in classes if netclass not in defined]
    return layout, refusals + class_name_problems(classes)


def empty_classes(nets: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
    return [(netclass, "KiCad places no net of the board in this class, so naming it protects nothing; assign the "
                       "board's nets to it as intended, or stop naming it")
            for netclass, held in nets.items() if not held]


def class_lines(classes: Sequence[str], nets: Dict[str, Set[str]], out) -> None:
    for netclass in classes:
        print(f"CLASS | {clean(netclass)} | {len(nets[netclass])} net{'s' if len(nets[netclass]) != 1 else ''}"
              + (f" | {clean(', '.join(sorted(nets[netclass])))}" if nets[netclass] else ""), file=out)


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


# --- Locking -------------------------------------------------------------------------


#: The child KiCad writes an item's (locked yes) immediately before, for each kind.
LOCK_BEFORE = {"track": ("layer",), "arc": ("layer",), "via": ("net",), "zone": ("layer", "layers")}


def forms_within(text: str, start: int, end: int) -> List[Tuple[object, int, int]]:
    """Every form inside the list written at text[start:end], each with its own offsets in `text`."""
    spans: List[Tuple[int, int, int]] = []
    forms = sexpr.parse(text[start + 1:end - 1], spans=spans)
    return [(form, start + 1 + first, start + 1 + last) for form, (first, last, _) in zip(forms, spans)]


def locked_text(text: str, path: str, critical: Set[str]) -> Tuple[str, List[dict], int]:
    """The board's text with every unlocked item on `critical` nets locked: (text, items locked, items already locked).

    Each lock is written where KiCad writes it, with the spacing the item's own
    children are written with, and nothing else in the text is touched.
    """
    start, end = text.index("("), text.rindex(")") + 1
    table = net_table(sexpr.parse_one(text))
    edits: List[Tuple[int, int, str]] = []
    changed, already = [], 0
    for node, first, last in forms_within(text, start, end):
        if sexpr.head(node) not in KIND_OF:
            continue
        try:
            item = read_item(node, table)
        except Unreadable as error:
            raise Unreadable(f"the board {path} cannot be read: {error}") from error
        if item["net"] not in critical:
            continue
        if item["locked"]:
            already += 1
            continue
        parts = forms_within(text, first, last)
        flag = [(at, to) for form, at, to in parts if sexpr.head(form) == "locked"]
        if flag:
            edits.append((flag[0][0], flag[0][1], "(locked yes)"))
        else:
            anchor = next((index for index, (form, _, _) in enumerate(parts)
                           if sexpr.head(form) in LOCK_BEFORE[item["kind"]]), None)
            if anchor is None or anchor == 0:
                raise Unreadable(f"the board {path} cannot be read: {describe(item)} has no "
                                 f"({' or '.join(LOCK_BEFORE[item['kind']])} ...) to write its lock before")
            at = parts[anchor][1]
            spacing = text[parts[anchor - 1][2]:at]
            edits.append((at, at, "(locked yes)" + spacing))
        changed.append(item)
    for at, to, replacement in sorted(edits, reverse=True):
        text = text[:at] + replacement + text[to:]
    return text, changed, already


def lock(board: str, project: str, classes: Sequence[str], kicad_cli: str, out) -> int:
    """Lock every track, arc, via and zone on the board's critical-class nets in the board file; the exit status."""
    refusals = [found for found in [open_in_editor(board)] if found is not None]
    why = own_project(board, project)
    if why is not None:
        refusals.append((project, why))
    if refusals:
        return refused(refusals, "REFUSED | the board was not changed", out)
    layout, refusals = named_classes(board, project, classes)
    if refusals:
        return refused(refusals, "REFUSED | the board was not changed", out)
    nets = members(kicad_cli, board, project, layout, classes)
    refusals = empty_classes(nets)
    if refusals:
        return refused(refusals, "REFUSED | the board was not changed", out)
    critical = set().union(*nets.values())
    try:
        with open(board, encoding="utf-8", newline="") as handle:
            text = handle.read()
        new, changed, already = locked_text(text, board, critical)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise Unreadable(f"the board {board} cannot be read ({error})") from error
    expected = [dict(item, locked=item["locked"] or item["net"] in critical) for item in copper(layout, board)]
    if copper(sexpr.parse_one(new), board) != expected:
        raise Unreadable(f"locking {board} would change more than its critical items' locks, so it was not changed")
    if changed:
        handle, partial = tempfile.mkstemp(prefix=".locked-copper-", dir=os.path.dirname(os.path.abspath(board)))
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
                stream.write(new)
            shutil.copymode(board, partial)
            os.replace(partial, board)
        except BaseException:
            if os.path.exists(partial):
                os.remove(partial)
            raise
    for item in changed:
        print(f"LOCKED | {clean(describe(item))} | locked now", file=out)
    class_lines(classes, nets, out)
    print(f"RESULT | LOCKED | {len(changed)} item{'s' if len(changed) != 1 else ''} locked now and {already} already "
          f"locked, on {len(critical)} critical-class nets | {clean(board)}", file=out)
    return 0


# --- Confirming the rules ------------------------------------------------------------


def confirm(board: str, project: str, classes: Sequence[str], kicad_cli: str, out) -> int:
    """Ask KiCad whether it loads the board's custom rules file and which nets each class holds; the exit status."""
    why = own_project(board, project)
    if why is not None:
        return refused([(project, why)], "FAIL | nothing was confirmed", out)
    layout, refusals = named_classes(board, project, classes)
    if refusals:
        return refused(refusals, "FAIL | nothing was confirmed", out)
    rules = os.path.splitext(board)[0] + ".kicad_dru"
    try:
        with open(rules, encoding="utf-8", errors="replace") as handle:
            existing = handle.read()
    except FileNotFoundError:
        return refused([(rules, "the board has no custom rules file, so there is nothing for KiCad to load; write its "
                                "rules there, beginning with (version 1)")], "FAIL | nothing was confirmed", out, "RULES")
    except OSError as error:
        raise Unreadable(f"the custom rules file {rules} cannot be read ({error})") from error
    nonce = secrets.token_hex(8)
    net = board_check.marker_net(board_check.net_items(layout))
    with tempfile.TemporaryDirectory(prefix="locked-copper-") as work:
        shutil.copy2(board, os.path.join(work, "board.kicad_pcb"))
        shutil.copy2(project, os.path.join(work, "board.kicad_pro"))
        with open(os.path.join(work, "board.kicad_dru"), "w", encoding="utf-8") as handle:
            handle.write(existing + board_check.appended_rules(None, nonce, net))
        report, why = board_check.run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all",
                                              "board.kicad_pcb"], work)
        if report is None:
            raise Unreadable(f"KiCad could not check {board} with its rules: {why}")
        if not board_check.fired(report, board_check.marker_rule(nonce)):
            if board_check.cut_short(report):
                return refused([(rules, f"KiCad's report was cut short at its limit of {board_check.REPORT_LIMIT} "
                                        "assertion failures, the board's own assertion rules failing on that many "
                                        "items, so the marker showing it loaded the rules was dropped from the report; "
                                        "correct the items those rules fail on and confirm again")],
                               "FAIL | KiCad's report was cut short", out, "RULES")
            place, what = board_check.rejected_form(kicad_cli, work, "board.kicad_pcb",
                                                    os.path.join(work, "board.kicad_dru"), existing, nonce)
            return refused([(f"{rules} {place}", "KiCad did not load the board's custom rules file: it drops the whole "
                                                 f"file, without saying so, when any part of it is something it cannot "
                                                 f"parse, so none of its rules is in effect; {what}")],
                           "FAIL | KiCad does not load the board's custom rules", out, "RULES")
    nets = members(kicad_cli, board, project, layout, classes)
    class_lines(classes, nets, out)
    refusals = empty_classes(nets)
    if refusals:
        return refused(refusals, "FAIL | a named class holds no net", out, "EMPTY")
    print(f"RESULT | CONFIRMED | KiCad loads {clean(rules)} and places nets in each of {', '.join(classes)}", file=out)
    return 0


# --- Recording and comparing -------------------------------------------------------------


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
    refusals = [found for found in [open_in_editor(board)] if found is not None]
    folder = design_folder(out_path, board)
    if folder is not None:
        refusals.append((out_path, "the record is a working file and is never kept in a design's folder, where it could be "
                                   f"committed and copied as part of the design; {folder} holds a design's project file, "
                                   "so write the record outside it"))
    why = own_project(board, project)
    if why is not None:
        refusals.append((project, why))
    if refusals:
        return refused(refusals, "REFUSED | no record was written", out)
    layout, refusals = named_classes(board, project, classes)
    if refusals:
        return refused(refusals, "REFUSED | no record was written", out)
    items = copper(layout, board)
    nets = members(kicad_cli, board, project, layout, classes)
    refusals = empty_classes(nets)
    if refusals:
        return refused(refusals, "REFUSED | no record was written", out)
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
        return refused([(out_path, f"the record cannot be written there ({error})")], "REFUSED | no record was written", out)
    class_lines(classes, nets, out)
    print(f"RESULT | RECORDED | {len(kept)} locked items on {len(critical)} critical-class nets | {clean(out_path)}", file=out)
    return 0


def compare(board: str, project: str, record_path: str, kicad_cli: str, out) -> int:
    """Compare the board's critical-class copper with the record; the exit status."""
    found = open_in_editor(board)
    if found is not None:
        return refused([found], "FAIL | the board is open in an editor, so nothing is taken as a pass", out, "OPEN")
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
        return refused(mismatches, f"FAIL | the board, project file and record given are not one board's, so nothing "
                                   f"in {', '.join(classes)} is taken as a pass", out, "MISMATCH")
    layout = read_layout(board)
    settings = read_project(project)
    defined = defined_classes(settings, layout)
    findings = [("MAINS", what, why) for what, why in mains_problems(settings, project, classes)]
    findings += [("UNDEFINED", netclass, "the record names this critical class and the design no longer defines it, so its "
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


#: What each command's result line says when its input cannot be read.
UNREAD_RESULT = {"confirm": "FAIL", "lock": "REFUSED", "record": "REFUSED", "compare": "FAIL"}


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    commands = parser.add_subparsers(dest="command", required=True)
    confirming = commands.add_parser("confirm", help="confirm KiCad loads the board's rules and list each class's nets")
    locking = commands.add_parser("lock", help="lock every critical-class item in the board file, with the board closed")
    taking = commands.add_parser("record", help="record the critical-class copper before export")
    checking = commands.add_parser("compare", help="compare the imported board with the record")
    for sub in (confirming, locking, taking):
        sub.add_argument("--class", dest="classes", action="append", required=True, metavar="NAME",
                         help="a critical net class, as the design names it; give each one")
    for sub in (confirming, locking, taking, checking):
        sub.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
        sub.add_argument("--project", required=True, help="the layout's project file (.kicad_pro)")
    for sub in (taking, checking):
        sub.add_argument("--record", required=True, help="the record: written by record, read by compare")
    args = parser.parse_args(argv)
    try:
        board_check.require_python()
        version = board_check.require_kicad(args.kicad_cli)
        with tempfile.TemporaryDirectory(prefix="locked-copper-kicad-") as home:
            board_check.KICAD_ENVIRONMENT = board_check.isolate_kicad(args.kicad_cli, version, home)
            try:
                if args.command == "confirm":
                    return confirm(args.board, args.project, args.classes, args.kicad_cli, out)
                if args.command == "lock":
                    return lock(args.board, args.project, args.classes, args.kicad_cli, out)
                if args.command == "record":
                    return record(args.board, args.project, args.classes, args.record, args.kicad_cli, out)
                return compare(args.board, args.project, args.record, args.kicad_cli, out)
            finally:
                board_check.KICAD_ENVIRONMENT = None
    except Unreadable as error:
        print(f"UNREADABLE | {clean(str(error))}", file=out)
        print(f"RESULT | {UNREAD_RESULT[args.command]} | the input cannot be read, so nothing is taken as a pass", file=out)
        return 1
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
