"""The board's silkscreen table: the choices the silkscreen command leaves to the board.

A board's folder holds a small YAML file, `silkscreen.yaml`, read by the command's
`--table` argument. It carries what is a decision about one board and not a rule of
the placer: the text heights and strokes, the warning legends and fixed texts, how
connector, tab and fuse names are made, and the per-part overrides. Every key is
optional; an empty table gives the defaults below. The file is checked whole before
anything is placed, and a mistake in it is refused naming the key.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

import yaml


class TableError(ValueError):
    """The table is not a table the command can use."""


DEFAULTS: Dict[str, Any] = {
    "clearance": 0.16,
    "edge_keepin": 0.5,
    "slot_keepin": 1.0,
    "thickness": {1.0: 0.15, 0.8: 0.15, 1.5: 0.2, 2.0: 0.3},
    "reference_sizes": [1.0, 0.8],
    "name_sizes": [1.0, 0.8],
    "function_names": {"pattern": r"^(J|JP)\d+$", "known": {}, "abbreviations": {}},
    "tabs": {"library_prefix": "Tab_", "strip_value": r"^TAB\d+_", "known": {}, "abbreviations": {}},
    "fuses": {"pattern": r"^F\d+$", "holder_library_words": ["fuseholder", "fuse_holder"], "rating_words": ["slow-blow"],
              "exclude_words": ["ptc"], "format": "T{amps} {volts}V", "known": {}},
    "test_points": {"pattern": r"^TP\d+$"},
    "pin1": {"dot": [], "mark": []},
    "parts": {},
    "legends": [],
    "fixed_texts": [],
}

PART_KEYS = {"reference", "reference_sizes", "name", "pin1"}
LEGEND_KEYS = {"id", "side", "region", "lines", "symbol", "symbol_size", "prefer"}
FIXED_KEYS = {"id", "text", "side", "size", "angle", "at", "max_move"}


def _merge(base: dict, over: dict, path: str) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if key not in base:
            raise TableError(f"{path}{key}: not a key of the silkscreen table")
        if isinstance(base[key], dict) and isinstance(value, dict) and key not in ("parts", "thickness", "known", "abbreviations"):
            out[key] = _merge(base[key], value, f"{path}{key}.")
        else:
            out[key] = value
    return out


def _number(value, where: str, low: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < low:
        raise TableError(f"{where}: must be a number of at least {low}, not {value!r}")
    return float(value)


def _regex(value, where: str) -> str:
    try:
        re.compile(value)
    except (re.error, TypeError) as error:
        raise TableError(f"{where}: not a regular expression ({error})") from error
    return value


def _sizes(value, where: str) -> List[float]:
    if not isinstance(value, list) or not value:
        raise TableError(f"{where}: must be a list of text heights in mm, largest first")
    return [_number(v, where, 0.1) for v in value]


def load(text: str) -> Dict[str, Any]:
    """The table in `text` (YAML) completed with the defaults, or TableError naming what is wrong."""
    try:
        given = yaml.safe_load(text) if text.strip() else {}
    except yaml.YAMLError as error:
        raise TableError(f"the table is not YAML ({error})") from error
    if given is None:
        given = {}
    if not isinstance(given, dict):
        raise TableError("the table must be a mapping of keys to values")
    table = _merge(DEFAULTS, given, "")
    for key in ("clearance", "edge_keepin", "slot_keepin"):
        table[key] = _number(table[key], key)
    if not isinstance(table["thickness"], dict) or not table["thickness"]:
        raise TableError("thickness: must map each text height in mm to its stroke in mm")
    table["thickness"] = {float(h): _number(t, f"thickness.{h}", 0.05) for h, t in table["thickness"].items()}
    table["reference_sizes"] = _sizes(table["reference_sizes"], "reference_sizes")
    table["name_sizes"] = _sizes(table["name_sizes"], "name_sizes")
    for height in table["reference_sizes"] + table["name_sizes"]:
        if height not in table["thickness"]:
            raise TableError(f"thickness: no stroke for the text height {height} that reference_sizes or name_sizes names")
    for section, keys in (("function_names", ("pattern",)), ("tabs", ("strip_value",)), ("fuses", ("pattern",)),
                          ("test_points", ("pattern",))):
        for key in keys:
            table[section][key] = _regex(table[section][key], f"{section}.{key}")
    for section in ("function_names", "tabs"):
        for key in ("known", "abbreviations"):
            if not isinstance(table[section][key], dict):
                raise TableError(f"{section}.{key}: must map a reference or a word to its text")
    if not isinstance(table["fuses"]["known"], dict):
        raise TableError("fuses.known: must map a fuse reference to its rating text")
    if "{amps}" not in table["fuses"]["format"] and "{volts}" not in table["fuses"]["format"]:
        raise TableError("fuses.format: must hold {amps} or {volts}")
    for key in ("holder_library_words", "rating_words", "exclude_words"):
        if not isinstance(table["fuses"][key], list):
            raise TableError(f"fuses.{key}: must be a list of words")
    for kind in ("dot", "mark"):
        if not isinstance(table["pin1"].get(kind), list):
            raise TableError(f"pin1.{kind}: must be a list of references")
    if set(table["pin1"]) - {"dot", "mark"}:
        raise TableError("pin1: holds only the keys dot and mark")
    if not isinstance(table["parts"], dict):
        raise TableError("parts: must map a reference to its overrides")
    for ref, override in table["parts"].items():
        if not isinstance(override, dict) or set(override) - PART_KEYS:
            raise TableError(f"parts.{ref}: holds only the keys {sorted(PART_KEYS)}")
        if override.get("reference") not in (None, "skip"):
            raise TableError(f"parts.{ref}.reference: only 'skip' is a reference override")
        if "reference_sizes" in override:
            sizes = _sizes(override["reference_sizes"], f"parts.{ref}.reference_sizes")
            for height in sizes:
                if height not in table["thickness"]:
                    raise TableError(f"thickness: no stroke for the text height {height} that parts.{ref} names")
            override["reference_sizes"] = sizes
        if override.get("pin1") not in (None, "dot", "mark", "none"):
            raise TableError(f"parts.{ref}.pin1: must be dot, mark or none")
        name = override.get("name")
        if name is not None and (not isinstance(name, str) or not name):
            raise TableError(f"parts.{ref}.name: must be the text to write, or 'skip'")
    seen = set()
    for kind, allowed, items in (("legends", LEGEND_KEYS, table["legends"]), ("fixed_texts", FIXED_KEYS, table["fixed_texts"])):
        if not isinstance(items, list):
            raise TableError(f"{kind}: must be a list")
        for n, item in enumerate(items):
            where = f"{kind}[{n}]"
            if not isinstance(item, dict) or set(item) - allowed:
                raise TableError(f"{where}: holds only the keys {sorted(allowed)}")
            if not isinstance(item.get("id"), str) or not item["id"]:
                raise TableError(f"{where}.id: every entry needs an id of its own")
            if item["id"] in seen:
                raise TableError(f"{where}.id: '{item['id']}' is used twice")
            seen.add(item["id"])
            if item.get("side", "F") not in ("F", "B"):
                raise TableError(f"{where}.side: must be F or B")
    for n, legend in enumerate(table["legends"]):
        where = f"legends[{n}]"
        if not isinstance(legend.get("region"), str) or not legend["region"]:
            raise TableError(f"{where}.region: must name the board's rule area the legend stands in")
        lines = legend.get("lines")
        if not isinstance(lines, list) or not lines:
            raise TableError(f"{where}.lines: must list the legend's lines, each with text and size")
        for line in lines:
            if not isinstance(line, dict) or not isinstance(line.get("text"), str) or not line["text"]:
                raise TableError(f"{where}.lines: each line needs its text")
            _number(line.get("size"), f"{where}.lines.size", 0.1)
            if float(line["size"]) not in table["thickness"]:
                raise TableError(f"thickness: no stroke for the text height {line['size']} that {where} names")
        if legend.get("symbol", "none") not in ("none", "hazard-triangle"):
            raise TableError(f"{where}.symbol: must be none or hazard-triangle")
        if "symbol_size" in legend:
            _number(legend["symbol_size"], f"{where}.symbol_size", 1.0)
        prefer = legend.get("prefer")
        if prefer is not None and not (isinstance(prefer, list) and len(prefer) == 2):
            raise TableError(f"{where}.prefer: must be [x, y] in mm")
    for n, fixed in enumerate(table["fixed_texts"]):
        where = f"fixed_texts[{n}]"
        if not isinstance(fixed.get("text"), str) or not fixed["text"]:
            raise TableError(f"{where}.text: must be the text to write")
        _number(fixed.get("size"), f"{where}.size", 0.1)
        if float(fixed["size"]) not in table["thickness"]:
            raise TableError(f"thickness: no stroke for the text height {fixed['size']} that {where} names")
        if fixed.get("angle", 0) not in (0, 90):
            raise TableError(f"{where}.angle: must be 0 or 90")
        at = fixed.get("at")
        if not (isinstance(at, list) and len(at) == 2):
            raise TableError(f"{where}.at: must be [x, y], the centre of the text in the board's frame, in mm")
        if "max_move" in fixed:
            _number(fixed["max_move"], f"{where}.max_move")
    return table
