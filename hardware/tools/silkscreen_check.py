"""The silkscreen legality measures: what a fabricator's silkscreen check holds a board's ink to.

Measured on the ink KiCad itself draws (true stroke outlines) from the extract of a
board, per side. The texts and the free graphics are held to the measures; a part's own
library outline is an obstacle for them and is not held to them, since it is the library's.
A text or graphic must stay clear of pad solder-mask openings, drilled
holes and the copper ring of an open via; keep away from the board edge and from
slots; stay on the board; keep clear of other parts' silkscreen; a text must not
run into another on its line, must be at least 0.8 mm high with a stroke of at least
0.12 mm, must read at 0 or 90 degrees, and a reference label must stand nearer its
own part than any other. Each finding names the silk item, what it breaks and
where.

Needs numpy, shapely and Pillow (see silkscreen_engine).
"""

from __future__ import annotations

from typing import Dict, List

import silkscreen_engine as eng
from silkscreen_engine import Point, Polygon, STRtree, polys, slots_of, unary_union

CLEARANCE = 0.15
EDGE_KEEPIN = 0.3
SLOT_KEEPIN = 1.0
MIN_HEIGHT = 0.8
MIN_STROKE = 0.12

CLASSES = ("pad_mask", "drill_hole", "via_ring", "edge_keepin", "slot", "over_edge", "silk_vs_silk", "run_together",
           "ambiguous_owner", "size_stroke", "angle")


def reading_angle(item: dict) -> float:
    a = item["ang"] % 360
    if item["side"] == "B":
        a = (-a) % 360
    return round(a, 3) % 360


def check(data: dict) -> Dict[str, List[dict]]:
    """{class: [finding]} for the board dumped in `data`; a class with no finding is absent."""
    findings: Dict[str, List[dict]] = {}
    silk = []     # every silkscreen item; a part's own library outline is an obstacle for the rest and is not itself held to these measures
    for i, item in enumerate(data["silk"]):
        geom = polys(item["rings"])
        if geom.is_empty:
            continue
        label = ("%s %s \"%s\"" % (item["owner"], item["kind"], item["text"])).strip() if item["is_text"] else "%s %s" % (item["owner"], item["kind"])
        silk.append(dict(item, id=i, geom=geom, label=label))
    outline = polys(data["outline"])
    outer = unary_union([Polygon(r[0]).buffer(0) for r in data["outline"]]) if data["outline"] else Polygon()
    slots = slots_of(outer, outline) if not outer.is_empty else Polygon()
    edge = polys(data["edge"])
    edge_all = unary_union([edge, outline.boundary.buffer(0.005)]) if not outline.is_empty else edge

    def add(cls, s, obstacle, dist, x, y, note=""):
        findings.setdefault(cls, []).append({"class": cls, "side": s["side"], "item": s["label"], "obstacle": obstacle,
                                             "distance": round(dist, 4), "x": round(x, 3), "y": round(y, 3), "note": note})

    def subjects():
        return [s for s in silk if s["is_text"] or s["owner"] == "free"]

    def pair(cls, side, obstacles, keep=CLEARANCE):
        if not obstacles:
            return
        tree = STRtree([o[0] for o in obstacles])
        for s in subjects():
            if side != "*" and s["side"] != side:
                continue
            for j in tree.query(s["geom"], predicate="dwithin", distance=keep):
                g, label, owner = obstacles[j]
                d = s["geom"].distance(g)
                if d >= keep:
                    continue
                c = (s["geom"].intersection(g).centroid if d == 0 else s["geom"].centroid)
                add(cls, s, label, d, c.x, c.y, "own part" if owner == s["owner"] else "")

    for side in "FB":
        pair("pad_mask", side, [(polys(p["rings"]), "%s.%s" % (p["ref"], p["pad"]), p["ref"]) for p in data["pads"] if p["side"] == side])
    holes = [(polys(h["rings"]), "%s.%s %s" % (h["ref"], h["pad"], "PTH" if h["plated"] else "NPTH"), h["ref"]) for h in data["holes"]]
    holes += [(Point(v["x"], v["y"]).buffer(v["drill"] / 2, 16), "via hole (%.3f, %.3f)" % (v["x"], v["y"]), "via") for v in data["vias"]]
    for side in "FB":
        pair("drill_hole", side, holes)
    for side in "FB":
        pair("via_ring", side, [(Point(v["x"], v["y"]).buffer(v["dia"] / 2 + v["exp"], 16), "open via ring (%.3f, %.3f)" % (v["x"], v["y"]), "via")
                                for v in data["vias"] if not v["tent_" + side]])
    if not edge_all.is_empty:
        pair("edge_keepin", "*", [(edge_all, "Edge.Cuts", None)], keep=EDGE_KEEPIN)
    if not slots.is_empty:
        pair("slot", "*", [(slots, "slot or cutout", None)], keep=SLOT_KEEPIN)
    if not outer.is_empty:
        for s in subjects():
            out = s["geom"].difference(outer)
            if out.area > 1e-6:
                add("over_edge", s, "outside the board outline", 0.0, out.centroid.x, out.centroid.y)
    if silk:
        tree = STRtree([s["geom"] for s in silk])
        seen = set()
        for s in subjects():
            for j in tree.query(s["geom"], predicate="dwithin", distance=CLEARANCE):
                t = silk[j]
                if t["id"] == s["id"] or t["side"] != s["side"]:
                    continue
                if t["owner"] == s["owner"] and t["owner"] != "free":
                    continue
                if t["owner"] == "free" and s["owner"] == "free" and not (s["is_text"] or t["is_text"]):
                    continue
                key = tuple(sorted((s["id"], t["id"])))
                if key in seen:
                    continue
                seen.add(key)
                d = s["geom"].distance(t["geom"])
                if d < CLEARANCE:
                    c = s["geom"].intersection(t["geom"]).centroid if d == 0 else s["geom"].centroid
                    add("silk_vs_silk", s, t["label"], d, c.x, c.y)
    texts = [s for s in silk if s["is_text"]]
    for s in texts:
        c = s["geom"].centroid
        if min(s["size"], s["sizey"]) < MIN_HEIGHT - 1e-9 or s["thick"] < MIN_STROKE - 1e-9:
            add("size_stroke", s, "height %.2f stroke %.3f" % (s["sizey"], s["thick"]), 0, c.x, c.y)
        angle = reading_angle(s)
        if angle not in (0.0, 90.0):
            add("angle", s, "reading angle %.1f" % angle, 0, c.x, c.y, "upside-down" if angle == 180 else "top-to-bottom" if angle == 270 else "oblique")
    for side in "FB":
        ts = [s for s in texts if s["side"] == side]
        for k, s in enumerate(ts):
            ra = reading_angle(s)
            horizontal = ra in (0.0, 180.0)
            b1 = s["geom"].bounds
            for t in ts[k + 1:]:
                if reading_angle(t) != ra:
                    continue
                b2 = t["geom"].bounds
                if horizontal:
                    u1, u2, v1, v2 = (b1[0], b1[2]), (b2[0], b2[2]), (b1[1] + b1[3]) / 2, (b2[1] + b2[3]) / 2
                else:
                    u1, u2, v1, v2 = (b1[1], b1[3]), (b2[1], b2[3]), (b1[0] + b1[2]) / 2, (b2[0] + b2[2]) / 2
                if abs(v1 - v2) >= 0.5 * max(s["sizey"], t["sizey"]):
                    continue
                gap = max(u2[0] - u1[1], u1[0] - u2[1])
                if gap < min(s["size"], t["size"]):
                    c = s["geom"].centroid
                    add("run_together", s, t["label"], gap, c.x, c.y)
    bodies = {}
    for ref, f in data["fps"].items():
        g = unary_union([polys(f["court"]), polys(f["padhull"])])
        if not g.is_empty:
            bodies[ref] = g
    refs = sorted(bodies)
    if refs:
        tree = STRtree([bodies[r] for r in refs])
        for s in silk:
            if s["kind"] != "field:Reference" or s["owner"] not in bodies:
                continue
            d_own = s["geom"].distance(bodies[s["owner"]])
            best = None
            for j in tree.query(s["geom"], predicate="dwithin", distance=d_own + 0.5):
                other = refs[j]
                if other == s["owner"] or data["fps"][other]["side"] != s["side"]:
                    continue
                d = s["geom"].distance(bodies[other])
                if best is None or d < best[1]:
                    best = (other, d)
            if best and best[1] < d_own - 1e-6:
                c = s["geom"].centroid
                add("ambiguous_owner", s, "nearer to %s (%.2f mm) than to its own part (%.2f mm)" % (best[0], best[1], d_own), best[1], c.x, c.y)
    return findings
