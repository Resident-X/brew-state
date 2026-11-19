"""Writing a board's silkscreen into its text, and proving that nothing else changed.

A board is edited as text, not saved through KiCad, so that every byte outside the
silkscreen stays as the input had it. The silkscreen of a board is its parts'
Reference properties (their position, layer and size), the free graphics and
texts drawn on F.SilkS or B.SilkS, and the footprint graphics drawn there. This
module replaces the first and adds the second, and `difference` reports what
differs between two boards once those items are set aside.

Standard library only: it runs without numpy, shapely and Pillow.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from typing import Dict, List, Optional, Tuple

import sexpr

NAMESPACE = uuid.UUID("5f5e1f4a-0b0d-4c0e-9d57-5c1a5a5a5a05")
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]')
KIND = re.compile(r'\(\s*([^\s()"]+)')
SILK_LAYERS = ("F.SilkS", "B.SilkS")
REFERENCE = re.compile(r'\(property\s+"Reference"\s+"((?:\\.|[^"\\])*)"')
LABEL_LAYERS = {"F.SilkS": "F.label", "F.Fab": "F.label", "B.SilkS": "B.label", "B.Fab": "B.label"}
LABEL_PROPERTIES = (re.compile(r'\(at\s[^)]*\)'), re.compile(r'\(size\s[^)]*\)'), re.compile(r'\(thickness\s[^)]*\)'),
                    re.compile(r'\(hide\s[^)]*\)'))
LAYER = re.compile(r'\(layer\s+"([^"]*)"\)')


class Block:
    """One parenthesised item of the board: where it is in the text, what kind it is, its depth and its footprint's reference."""

    __slots__ = ("start", "end", "depth", "kind", "text", "layer", "parent")

    def __init__(self, start, end, depth, kind, text, layer, parent):
        self.start, self.end, self.depth, self.kind, self.text, self.layer, self.parent = start, end, depth, kind, text, layer, parent


def sha(text) -> str:
    return hashlib.sha256(text if isinstance(text, bytes) else text.encode("utf-8")).hexdigest()


def blocks(text: str) -> List[Block]:
    """Every item directly in the board (depth 1) and every item directly in a footprint (depth 2), in file order."""
    stack: List[int] = []
    found: List[Block] = []
    for match in TOKEN.finditer(text):
        token = match.group()
        if token == "(":
            stack.append(match.start())
        elif token == ")":
            if not stack:
                raise sexpr.SexprError("unbalanced ')'")
            start = stack.pop()
            depth = len(stack)
            if depth not in (1, 2):
                continue
            if depth == 2:
                parent_kind = KIND.match(text, stack[1])
                if parent_kind is None or parent_kind.group(1) != "footprint":
                    continue
            kind_match = KIND.match(text, start)
            block_text = text[start:match.end()]
            layer_match = re.search(r'\(layer\s+"([^"]+)"', block_text)
            found.append(Block(start, match.end(), depth, kind_match.group(1) if kind_match else "", block_text,
                               layer_match.group(1) if layer_match else None, stack[1] if depth == 2 else None))
    if stack:
        raise sexpr.SexprError(f"{len(stack)} unclosed '('")
    found.sort(key=lambda b: b.start)
    return found


def is_reference(block: Block) -> bool:
    return block.depth == 2 and block.kind == "property" and REFERENCE.match(block.text) is not None


def strippable(block: Block) -> bool:
    """True for the items that are silkscreen: a footprint's Reference, a graphic or text on a silkscreen layer."""
    if is_reference(block):
        return True
    if block.depth == 1 and block.kind.startswith("gr_") and block.layer in SILK_LAYERS:
        return True
    if block.depth == 2 and block.kind.startswith("fp_") and block.layer in SILK_LAYERS:
        return True
    return False


def references(text: str) -> Dict[str, Block]:
    """Each footprint's Reference property block by reference text."""
    return {REFERENCE.match(b.text).group(1): b for b in blocks(text) if is_reference(b)}


def label_remainder(block_text: str) -> str:
    """A Reference property with what the silkscreen command legitimately sets put aside.

    Its position, angle, size, stroke and visibility are set aside, and so is which of its own side's
    silkscreen or fab layers it is on. Everything else stays, the layer included when it is any other
    layer or the other side of the board, so a label moved onto copper, the edge or a mask is a difference.
    """
    text = block_text
    for pattern in LABEL_PROPERTIES:
        text = pattern.sub("", text)
    return LAYER.sub(lambda m: '(layer "%s")' % LABEL_LAYERS.get(m.group(1), m.group(1)), text, count=1)


def strip(text: str) -> Tuple[str, List[Tuple[str, Optional[str]]]]:
    """The board with its silkscreen set aside: (remainder, [(kind, layer)] of what was taken out).

    A Reference is not removed whole: what the command does not set stays (its text, its layer unless
    that is a silkscreen or fab layer of its side, its other properties), so a part renamed or a
    label moved onto another layer counts as a change.
    """
    parts, last, removed = [], 0, []
    for block in blocks(text):
        if not strippable(block):
            continue
        if is_reference(block):
            parts.append(text[last:block.start])
            parts.append(label_remainder(block.text))
        else:
            begin = block.start
            while begin > last and text[begin - 1] in "\t ":
                begin -= 1
            if begin > last and text[begin - 1] == "\n":
                begin -= 1
            parts.append(text[last:begin])
        last = block.end
        removed.append((block.kind, block.layer))
    parts.append(text[last:])
    return "".join(parts), removed


def describe(node) -> str:
    """A short name for a top-level item of the board, to say what differs."""
    head = sexpr.head(node)
    text = sexpr.dump(node)
    if head == "footprint":
        ref = next((c[2] for c in sexpr.children(node, "property") if len(c) > 2 and c[1] == "Reference"), "?")
        return f"footprint {ref}"
    if head == "zone":
        name = sexpr.child(node, "name")
        return f"zone {name[1] if name and len(name) > 1 else '(unnamed)'}"
    if head in ("segment", "arc"):
        start, end, net = sexpr.child(node, "start"), sexpr.child(node, "end"), sexpr.child(node, "net")
        return f"{head} on net {net[-1] if net else '?'} from ({start[1]}, {start[2]}) to ({end[1]}, {end[2]})" if start and end else head
    if head == "via":
        at = sexpr.child(node, "at")
        return f"via at ({at[1]}, {at[2]})" if at else "via"
    uid = sexpr.child(node, "uuid")
    return f"{head} {uid[1]}" if uid and len(uid) > 1 else (head or text[:40])


def _key(node):
    head = sexpr.head(node)
    if head == "footprint":
        return ("footprint", describe(node))
    uid = sexpr.child(node, "uuid")
    if uid and len(uid) > 1:
        return (head, str(uid[1]))
    return (head, sha(sexpr.dump(node)) if head in ("gr_line", "gr_arc", "gr_rect", "gr_circle", "gr_poly") else "")


def difference(before: str, after: str) -> List[str]:
    """What differs between two boards outside their silkscreen, one phrase each; empty when only silkscreen does."""
    a, _ra = strip(before)
    b, _rb = strip(after)
    if a == b:
        return []
    try:
        left, right = sexpr.parse_one(a), sexpr.parse_one(b)
    except sexpr.SexprError as error:
        return [f"a board is not well-formed text ({error})"]
    def index(root):
        table: Dict[tuple, list] = {}
        for node in root[1:]:
            if isinstance(node, list):
                table.setdefault(_key(node), []).append(node)
        return table
    ia, ib = index(left), index(right)
    out: List[str] = []
    for key in sorted(set(ia) | set(ib)):
        one, two = ia.get(key, []), ib.get(key, [])
        if len(one) != len(two):
            for node in (one if len(one) > len(two) else two)[min(len(one), len(two)):]:
                out.append(f"{describe(node)} is {'only in the input' if len(one) > len(two) else 'only in the output'}")
            continue
        for x, y in zip(one, two):
            if sexpr.dump(x) != sexpr.dump(y):
                out.append(f"{describe(x)} differs")
    if not out:
        out.append("the text outside the silkscreen differs (order or spacing of items)")
    return out


# ---------------------------------------------------------------- writing the plan
def num(v: float) -> str:
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def uid(*parts) -> str:
    return str(uuid.uuid5(NAMESPACE, "|".join(str(p) for p in parts)))


def _effects(size, thick, mirror) -> str:
    text = "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %s %s)\n\t\t\t\t(thickness %s)\n\t\t\t)\n" % (num(size), num(size), num(thick))
    if mirror:
        text += "\t\t\t(justify mirror)\n"
    return text + "\t\t)\n"


def gr_text(t, k) -> str:
    layer = "B.SilkS" if t["side"] == "B" else "F.SilkS"
    return '\t(gr_text "%s"\n\t\t(at %s %s %s)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n%s\t)\n' % (
        t["text"].replace("\\", "\\\\").replace('"', '\\"'), num(t["x"]), num(t["y"]), num(t["angle"]), layer,
        uid("text", k, t["text"], t["x"], t["y"]), _effects(t["size"], t["thick"], t["side"] == "B"))


def gr_poly(p, k) -> str:
    layer = "B.SilkS" if p["side"] == "B" else "F.SilkS"
    pts = " ".join("(xy %s %s)" % (num(x), num(y)) for x, y in p["pts"])
    return ('\t(gr_poly\n\t\t(pts\n\t\t\t%s\n\t\t)\n\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill %s)\n\t\t(layer "%s")\n'
            '\t\t(uuid "%s")\n\t)\n') % (pts, num(p["width"]), "yes" if p.get("fill") else "no", layer, uid("poly", k, pts[:60]))


def gr_circle(c, k) -> str:
    layer = "B.SilkS" if c["side"] == "B" else "F.SilkS"
    return ('\t(gr_circle\n\t\t(center %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n'
            '\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)\n') % (num(c["x"]), num(c["y"]), num(c["x"] + c["r"]), num(c["y"]), num(c["width"]),
                                                          layer, uid("circle", k, c["x"], c["y"]))


def reference_block(block_text: str, ref: str, plan_entry: dict, footprint: dict) -> str:
    """A Reference property's text with its position, layer, size and stroke set to `plan_entry`, or moved to the fab layer."""
    if plan_entry.get("fab"):
        layer = "B.Fab" if footprint["side"] == "B" else "F.Fab"
        return re.sub(r'\(layer\s+"[FB]\.SilkS"', '(layer "%s"' % layer, block_text, count=1)
    theta = math.radians(footprint["rot"])
    dx, dy = plan_entry["x"] - footprint["x"], plan_entry["y"] - footprint["y"]
    c, s = math.cos(-theta), math.sin(-theta)
    fx, fy = dx * c + dy * s, -dx * s + dy * c
    text = re.sub(r'\(at [^)]*\)', '(at %s %s %s)' % (num(fx), num(fy), num(plan_entry["angle"])), block_text, count=1)
    text = re.sub(r'\(layer\s+"[^"]*"', '(layer "%s"' % plan_entry["layer"], text, count=1)
    text = re.sub(r'\(size [\d.]+ [\d.]+\)', '(size %s %s)' % (num(plan_entry["size"]), num(plan_entry["size"])), text, count=1)
    if re.search(r'\(thickness [\d.]+\)', text):
        text = re.sub(r'\(thickness [\d.]+\)', '(thickness %s)' % num(plan_entry["thick"]), text, count=1)
    return text


def apply_plan(text: str, plan: dict, footprints: dict) -> str:
    """The board `text` with its silkscreen replaced by `plan`.

    Each Reference named in the plan's `refs` is rewritten (a reference the plan
    leaves out, or marks `keep`, is left as it is); every free graphic on a
    silkscreen layer is removed and the plan's texts, polygons, circles and lines
    are added at the end of the board.
    """
    out, last = [], 0
    for block in blocks(text):
        if not strippable(block):
            continue
        if is_reference(block):
            ref = REFERENCE.match(block.text).group(1)
            entry = plan["refs"].get(ref)
            if entry is None or entry.get("keep"):
                continue
            out.append(text[last:block.start])
            out.append(reference_block(block.text, ref, entry, footprints[ref]))
            last = block.end
        elif block.depth == 1:
            begin = block.start
            while begin > last and text[begin - 1] in "\t ":
                begin -= 1
            if begin > last and text[begin - 1] == "\n":
                begin -= 1
            out.append(text[last:begin])
            last = block.end
    out.append(text[last:])
    body = "".join(out)
    new = "".join([gr_text(x, i) for i, x in enumerate(plan.get("texts", []))] + [gr_poly(x, i) for i, x in enumerate(plan.get("polys", []))] +
                  [gr_circle(x, i) for i, x in enumerate(plan.get("circles", []))])
    if not new:
        return body
    end = body.rstrip().rfind(")")
    head = body[:end]
    if not head.endswith("\n"):
        head += "\n"
    return head + new + body[end:]
