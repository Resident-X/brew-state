"""The silkscreen command's placement engine: the geometry of a board, raster masks, candidate positions and the solver.

Everything is done in a side's own view frame: the back side is mirrored in x (x
becomes -x), so each side reads as an unmirrored front view. A label is a
rectangle of stroke-font ink; a position is free when no pad opening, drilled hole,
foreign silkscreen, board-edge keep-in, courtyard or earlier label touches it.
Free positions are found on a raster by summed-area tables, ranked by how plainly
the label belongs to its part, and a solver assigns one position to each label,
ejecting and re-placing neighbours when a label has nowhere free.

This module needs numpy, shapely and Pillow, which the rest of the board tooling
does not; importing it without one stops naming the package (CannotRun).
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from board_check import CannotRun

PACKAGES = (("numpy", "numpy"), ("shapely", "shapely"), ("PIL", "Pillow"))


def check_packages() -> None:
    """Run again under SILKSCREEN_PYTHON when that holds the packages; else raise CannotRun naming the first missing one."""
    import importlib

    import silkscreen_python
    silkscreen_python.rerun_under_silkscreen_python()

    for module, package in PACKAGES:
        try:
            importlib.import_module(module)
        except ImportError as error:
            raise CannotRun(f"the Python package {package} is not installed, and the silkscreen command needs numpy, "
                            f"shapely and Pillow (hardware/README.md names them beside KiCad); "
                            f"{silkscreen_python.where_to_find()}") from error


check_packages()

import numpy as np  # noqa: E402
import shapely  # noqa: E402
from PIL import Image, ImageChops, ImageDraw  # noqa: E402
from shapely import affinity  # noqa: E402
from shapely.geometry import Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

GAP_TEXT = 0.16        # least distance between texts of different owners
RUN_GAP = 1.05         # least end-to-end gap between two texts on one line
T1_GAP = 0.6           # a label is "directly against" its part within this distance
T2_DIST = 2.5          # a label may stand this far from its part when it is strictly the nearest
T2_MARGIN = 0.1        # and then by at least this much nearer to its own part than to any other
TOLC = 0.5             # centring tolerance of a label against its own part


# ---------------------------------------------------------------- geometry of the board
def polys(rings):
    """One geometry from a list of [outer, hole...] rings."""
    out = []
    for ring in rings:
        try:
            polygon = Polygon(ring[0], ring[1:]).buffer(0)
        except Exception:  # noqa: BLE001 - a degenerate ring holds no ink
            continue
        if not polygon.is_empty:
            out.append(polygon)
    return unary_union(out) if out else Polygon()


def view(geometry, side: str):
    """`geometry` as seen from `side`: unchanged on the front, mirrored in x on the back."""
    return geometry if side == "F" else affinity.scale(geometry, xfact=-1, yfact=1, origin=(0, 0))


def slots_of(board_outer, outline):
    """Cutouts inside the board and narrow notches running out through its edge, as one geometry."""
    inner = board_outer.difference(outline)
    closed = board_outer.buffer(1.5, 16).buffer(-1.5, 16)
    notch = closed.difference(board_outer).buffer(-0.2, 8).buffer(0.2, 8)
    notch = notch.buffer(0.01).intersection(closed.difference(board_outer))
    notch = unary_union([g for g in (notch.geoms if hasattr(notch, "geoms") else [notch]) if g.area > 1.0])
    return unary_union([inner, notch])


class World:
    """The board's obstacles and parts per side, from the extract's dump."""

    def __init__(self, data: dict, clearance: float, edge_keepin: float, slot_keepin: float, keep_refs=frozenset()):
        self.D = data
        self.keep_refs = frozenset(keep_refs)
        self.clearance = clearance
        outline = polys(data["outline"])
        board_outer = unary_union([Polygon(r[0]).buffer(0) for r in data["outline"]]) if data["outline"] else Polygon()
        self.slots = slots_of(board_outer, outline) if not board_outer.is_empty else Polygon()
        self.board = board_outer
        edge = polys(data["edge"])
        self.edge_all = unary_union([edge, outline.boundary.buffer(0.005)]) if not outline.is_empty else edge
        self.outline = outline
        self.fps = {ref: data["fps"][ref] for ref in sorted(data["fps"])}
        bounds = board_outer.bounds if not board_outer.is_empty else (0.0, 0.0, 1.0, 1.0)
        self.bounds = bounds
        self.edge_keepin, self.slot_keepin = edge_keepin, slot_keepin
        self.W = {side: self.build_side(side) for side in "FB"}

    def build_side(self, s: str) -> dict:
        data, clr = self.D, self.clearance
        o = {}
        keepin = self.board.difference(self.edge_all.buffer(self.edge_keepin)).difference(self.slots.buffer(self.slot_keepin))
        o["allowed"] = view(keepin, s)
        hard = []
        for p in data["pads"]:
            if p["side"] == s:
                hard.append(view(polys(p["rings"]), s).buffer(clr, 8))
        for h in data["holes"]:
            hard.append(view(polys(h["rings"]), s).buffer(clr, 8))
        for v in data["vias"]:
            hard.append(Point(-v["x"] if s == "B" else v["x"], v["y"]).buffer(v["drill"] / 2 + clr, 8))
        o["hard"] = hard
        o["via"] = [Point(-v["x"] if s == "B" else v["x"], v["y"]).buffer(v["dia"] / 2 + 0.15, 8) for v in data["vias"]]
        silk = []
        for item in data["silk"]:
            if item["side"] != s or item["owner"] == "free":
                continue
            if item["kind"] == "field:Reference" and item["owner"] not in self.keep_refs:
                continue
            silk.append((item["owner"], view(polys(item["rings"]), s).buffer(clr, 8)))
        o["silk"] = silk
        court, body = {}, {}
        for ref, f in self.fps.items():
            if f["side"] != s:
                continue
            c = view(polys(f["court"]), s)
            ph = view(polys(f["padhull"]), s)
            court[ref] = c if not c.is_empty else ph.buffer(0.2)
            b = unary_union([c, ph])
            body[ref] = b if not b.is_empty else Point(-f["x"] if s == "B" else f["x"], f["y"]).buffer(0.5)
        o["court"], o["body"] = court, body
        o["padhull"] = {ref: view(polys(f["padhull"]), s) for ref, f in self.fps.items() if f["side"] == s}
        return o


# ---------------------------------------------------------------- stroke-font ink
class Ink:
    """Measured stroke-font ink of strings, cached in a JSON file; `measure` is called with the strings missing from it."""

    def __init__(self, path: str, measure: Callable[[List[list], str], None]):
        self.path = path
        self.measure = measure
        self.d = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                self.d = json.load(handle)

    @staticmethod
    def key(text, size, thick) -> str:
        return "%s|%s|%s" % (text, float(size), float(thick))

    def ensure(self, strings) -> None:
        need = sorted({(t, float(s), float(th)) for t, s, th in strings if self.key(t, s, th) not in self.d})
        if need:
            self.measure([list(n) for n in need], self.path)
            with open(self.path, encoding="utf-8") as handle:
                self.d = json.load(handle)

    def bb(self, text, size, thick):
        if self.key(text, size, thick) not in self.d:
            self.ensure([(text, size, thick)])
        return self.d[self.key(text, size, thick)]["bb"]


def rot_rect(bb, angle):
    """A reading-frame rectangle (u0, v0, u1, v1) in the view frame for reading angle 0 or 90."""
    u0, v0, u1, v1 = bb
    return (u0, v0, u1, v1) if angle == 0 else (v0, -u1, v1, -u0)


def rot_pt(du, dv, angle):
    return (du, dv) if angle == 0 else (dv, -du)


# ---------------------------------------------------------------- raster masks
class Raster:
    def __init__(self, ox: float, oy: float, width_mm: float, height_mm: float, res: float):
        self.ox, self.oy, self.res = ox, oy, res
        self.W = int(width_mm / res) + 2
        self.H = int(height_mm / res) + 2

    def px(self, x, y):
        return (x - self.ox) / self.res, (y - self.oy) / self.res

    def new(self):
        return Image.new("L", (self.W, self.H), 0)

    def draw(self, img, geom, val=1):
        draw = ImageDraw.Draw(img)
        for g in (list(geom.geoms) if hasattr(geom, "geoms") else [geom]):
            if g.is_empty:
                continue
            if g.geom_type in ("MultiPolygon", "GeometryCollection"):
                self.draw(img, g, val)
                continue
            if g.geom_type != "Polygon":
                continue
            if not len(g.interiors):
                draw.polygon([self.px(x, y) for x, y in g.exterior.coords], fill=val, outline=val)
                continue
            x0, y0, x1, y1 = g.bounds
            ix0 = max(int((x0 - self.ox) / self.res) - 2, 0)
            iy0 = max(int((y0 - self.oy) / self.res) - 2, 0)
            ix1 = min(int((x1 - self.ox) / self.res) + 3, self.W)
            iy1 = min(int((y1 - self.oy) / self.res) + 3, self.H)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            sub = Image.new("L", (ix1 - ix0, iy1 - iy0), 0)
            sd = ImageDraw.Draw(sub)

            def f(x, y):
                return ((x - self.ox) / self.res - ix0, (y - self.oy) / self.res - iy0)

            sd.polygon([f(x, y) for x, y in g.exterior.coords], fill=val, outline=val)
            for hole in g.interiors:
                sd.polygon([f(x, y) for x, y in hole.coords], fill=0, outline=0)
                sd.line([f(x, y) for x, y in hole.coords], fill=val, width=1)
            current = img.crop((ix0, iy0, ix1, iy1))
            img.paste(ImageChops.lighter(current, sub), (ix0, iy0))


class SideWorld:
    """Per side: view-frame obstacle masks and part data."""

    def __init__(self, world: World, side: str, res: float):
        self.world, self.side = world, side
        self.o = world.W[side]
        bx0, by0, bx1, by1 = world.bounds
        vx0, vx1 = (bx0, bx1) if side == "F" else (-bx1, -bx0)
        self.ox, self.oy = vx0 - 2.0, by0 - 2.0
        width, height = (vx1 - vx0) + 4.0, (by1 - by0) + 4.0
        self.xmin, self.xmax = self.ox + 1.0, self.ox + width - 1.0
        self.ymin, self.ymax = self.oy + 1.0, self.oy + height - 1.0
        self.R = Raster(self.ox, self.oy, width, height, res)
        self.fixed_polys = []
        self.build_static()

    def build_static(self):
        o, R = self.o, self.R
        img = R.new()
        outside = box(self.ox - 1, self.oy - 1, self.ox + R.W * R.res + 1, self.oy + R.H * R.res + 1).difference(o["allowed"])
        R.draw(img, outside)
        for g in o["hard"]:
            R.draw(img, g)
        for _owner, g in o["silk"]:
            R.draw(img, g)
        self.hard = np.array(img, dtype=np.uint8)
        count = np.zeros((R.H, R.W), dtype=np.uint8)
        for _ref, c in o["court"].items():
            im = R.new()
            R.draw(im, c)
            count += np.array(im, dtype=np.uint8)
        self.court_cnt = count
        im = R.new()
        for g in o["via"]:
            R.draw(im, g)
        self.via = np.array(im, dtype=np.uint8)

    def add_fixed(self, geom, buf: float):
        """Mark new silkscreen `geom` (view frame) and `buf` of clearance round it as taken."""
        g = geom.buffer(buf, 8)
        self.fixed_polys.append(g)
        im = self.R.new()
        self.R.draw(im, g)
        self.hard = np.maximum(self.hard, np.array(im, dtype=np.uint8))


def sat(a):
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.int32)
    s[1:, 1:] = a.astype(np.int32).cumsum(0).cumsum(1)
    return s


def rect_sum(S, x0, y0, x1, y1):
    return S[y1, x1] - S[y0, x1] - S[y1, x0] + S[y0, x0]


def mask_sat(sw: SideWorld, courts: bool = True):
    m = sw.hard.astype(np.int16)
    if courts:
        m = m + (sw.court_cnt > 0)
    return sat((m > 0).astype(np.uint8))


class Cands:
    """The candidate positions of one item, as arrays."""


class Item:
    def __init__(self, iid, side, kind="text", owner=None, target=None, variants=None, pref_angle=0):
        self.id, self.side, self.kind, self.owner = iid, side, kind, owner
        self.target, self.variants, self.pref_angle = target, variants or [], pref_angle
        self.cands = None
        self.ref = owner


# ---------------------------------------------------------------- part geometry
class PartGeo:
    """Each part's pads-and-outline geometry, hull, bounds and body on its own side, with a tree of them per side."""

    def __init__(self, world: World):
        self.G, self.hull, self.bb, self.body = {}, {}, {}, {}
        for s in "FB":
            o = world.W[s]
            silk_by: Dict[str, list] = {}
            for item in world.D["silk"]:
                if item["side"] != s or item["kind"] == "field:Reference" or item["owner"] == "free":
                    continue
                if item["kind"].startswith("fpgfx"):
                    silk_by.setdefault(item["owner"], []).append(view(polys(item["rings"]), s))
            for ref, f in world.fps.items():
                if f["side"] != s:
                    continue
                ph = o["padhull"][ref]
                parts = ([ph] if not ph.is_empty else []) + silk_by.get(ref, [])
                g = unary_union(parts) if parts else o["body"][ref]
                self.G[ref], self.hull[ref], self.bb[ref], self.body[ref] = g, g.convex_hull, g.bounds, o["body"][ref]
        self.refs_arr, self.Gs, self.bodies, self.bbs, self.trees = {}, {}, {}, {}, {}
        for s in "FB":
            refs = [r for r, f in world.fps.items() if f["side"] == s]
            self.refs_arr[s] = np.array(refs, dtype=object)
            self.Gs[s] = np.array([self.G[r] for r in refs], dtype=object)
            self.bodies[s] = np.array([self.body[r] for r in refs], dtype=object)
            self.bbs[s] = np.array([self.bb[r] for r in refs], float).reshape(-1, 4)
            self.trees[s] = STRtree([unary_union([self.Gs[s][i], self.bodies[s][i]]) for i in range(len(refs))])


def layout_centered(ink: Ink, lines, gap: float = 0.25):
    """Lines [(text, size, thick)] as reading-frame rectangles centred on u=0 stacked down from v=0, and their anchors."""
    rects, anchors, vt = [], [], 0.0
    for text, size, thick in lines:
        x0, y0, x1, y1 = ink.bb(text, size, thick)
        wd, h = x1 - x0, y1 - y0
        rects.append((-wd / 2, vt, wd / 2, vt + h))
        anchors.append((-wd / 2 - x0, vt - y0))
        vt += h + gap
    return rects, anchors


def _thin(out, key_cell: float, maxn: int):
    """The best `maxn` records over (variant, angle, cell) of the per-angle candidate dictionaries `out`."""
    recs = []
    for k, c in enumerate(out):
        cx = np.floor(c["ox"] / key_cell).astype(int)
        cy = np.floor(c["oy"] / key_cell).astype(int)
        for i in range(len(c["cost"])):
            recs.append((float(c["cost"][i]), k, i, c["A"], int(cx[i]), int(cy[i])))
    recs.sort(key=lambda r: (r[0], r[1], r[2]))
    seen, sel = set(), []
    for r in recs:
        key = (r[3], r[4], r[5])
        if key in seen:
            continue
        seen.add(key)
        sel.append(r)
        if len(sel) >= maxn:
            break
    return sel


def _build_cands(out, sel, n_lines: int, pad_composite: bool):
    C = Cands()
    n = len(sel)
    C.cost = np.array([r[0] for r in sel])
    C.vi = np.zeros(n, int)
    C.A = np.array([r[3] for r in sel])
    C.gx = np.array([out[r[1]]["ox"][r[2]] for r in sel])
    C.gy = np.array([out[r[1]]["oy"][r[2]] for r in sel])
    C.via = np.array([out[r[1]]["via"][r[2]] for r in sel])
    C.tier = np.array([out[r[1]]["tier"][r[2]] for r in sel])
    C.side = np.array([out[r[1]]["side"][r[2]] for r in sel])
    C.nl = np.full(n, n_lines)
    C.rect = np.full((n, n_lines, 4), np.nan)
    C.anchors = []
    for j, r in enumerate(sel):
        c = out[r[1]]
        for l in range(n_lines):
            rr = c["rl"][l]
            C.rect[j, l] = (c["ox"][r[2]] + rr[0], c["oy"][r[2]] + rr[1], c["ox"][r[2]] + rr[2], c["oy"][r[2]] + rr[3])
        C.anchors.append(c["al"])
    if pad_composite and n_lines > 1:
        C.rect[:, :, 0] -= 0.45
        C.rect[:, :, 1] -= 0.45
        C.rect[:, :, 2] += 0.45
        C.rect[:, :, 3] += 0.45
    return C


def gen_ref(sw: SideWorld, geo: PartGeo, ref: str, ink: Ink, lines, angles=(0, 90), pref=0, t2_dist: float = T2_DIST,
            extra: float = 0.0, maxn: int = 500, step: float = 0.05):
    """Candidate positions of a label block (`lines`, the first being the designator) for part `ref`, or None.

    Tier 1: directly against the part, centred on it, parallel to it, with no
    other part a label would stand against as plainly. Tier 2: within `t2_dist`
    and strictly nearest to this part. Each position carries a cost: nearer and
    better centred is cheaper, a turned label costs a little, a ring of a via a lot.
    """
    side, R, o = sw.side, sw.R, sw.o
    G, hull = geo.G[ref], geo.hull[ref]
    bx0, by0, bx1, by1 = geo.bb[ref]
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    own_court = o["court"].get(ref)
    ink.ensure(list(lines))
    rects_r, anchors_r = layout_centered(ink, lines)
    out = []
    shapely.prepare(hull)
    for A in angles:
        rl = [rot_rect(r, A) for r in rects_r]
        al = [rot_pt(a[0], a[1], A) for a in anchors_r]
        hx0, hy0 = min(r[0] for r in rl), min(r[1] for r in rl)
        hx1, hy1 = max(r[2] for r in rl), max(r[3] for r in rl)
        W, H = hx1 - hx0, hy1 - hy0
        lim = t2_dist + 0.1
        xs = np.arange(bx0 - W - lim, bx1 + lim, step)
        ys = np.arange(by0 - H - lim, by1 + lim, step)
        GX, GY = np.meshgrid(xs, ys)
        GX, GY = GX.ravel(), GY.ravel()
        OX, OY = GX - hx0, GY - hy0
        dx = np.maximum(np.maximum(bx0 - (GX + W), GX - bx1), 0)
        dy = np.maximum(np.maximum(by0 - (GY + H), GY - by1), 0)
        keep = np.hypot(dx, dy) <= lim
        keep &= (GX >= sw.xmin) & (GX + W <= sw.xmax) & (GY >= sw.ymin) & (GY + H <= sw.ymax)
        idx = np.nonzero(keep)[0]
        if not len(idx):
            continue
        res = R.res
        wx0 = max(int(math.floor((GX[idx].min() - sw.ox) / res)) - 3, 0)
        wx1 = min(int(math.ceil((GX[idx].max() + W - sw.ox) / res)) + 3, R.W)
        wy0 = max(int(math.floor((GY[idx].min() - sw.oy) / res)) - 3, 0)
        wy1 = min(int(math.ceil((GY[idx].max() + H - sw.oy) / res)) + 3, R.H)
        hm = sw.hard[wy0:wy1, wx0:wx1].astype(np.int16)
        cc = sw.court_cnt[wy0:wy1, wx0:wx1].astype(np.int16)
        if own_court is not None and not own_court.is_empty:
            im = R.new()
            R.draw(im, own_court)
            cc = cc - np.array(im, dtype=np.uint8)[wy0:wy1, wx0:wx1].astype(np.int16)
        S = sat(((hm > 0) | (cc > 0)).astype(np.uint8))
        SV = sat(sw.via[wy0:wy1, wx0:wx1])
        ok = np.ones(len(idx), bool)
        viahit = np.zeros(len(idx), np.int8)
        for (rx0, ry0, rx1, ry1) in rl:
            X0, Y0, X1, Y1 = OX[idx] + rx0, OY[idx] + ry0, OX[idx] + rx1, OY[idx] + ry1
            px0 = np.floor((X0 - sw.ox) / res).astype(int) - wx0
            px1 = np.ceil((X1 - sw.ox) / res).astype(int) - wx0
            py0 = np.floor((Y0 - sw.oy) / res).astype(int) - wy0
            py1 = np.ceil((Y1 - sw.oy) / res).astype(int) - wy0
            ok &= (px0 >= 0) & (py0 >= 0) & (px1 <= S.shape[1] - 1) & (py1 <= S.shape[0] - 1)
            a, b = np.clip(px0, 0, S.shape[1] - 1), np.clip(px1, 0, S.shape[1] - 1)
            c_, d = np.clip(py0, 0, S.shape[0] - 1), np.clip(py1, 0, S.shape[0] - 1)
            ok &= rect_sum(S, a, c_, b, d) == 0
            viahit += (rect_sum(SV, a, c_, b, d) > 0).astype(np.int8)
        idx, viahit = idx[ok], viahit[ok]
        if not len(idx):
            continue
        X0, Y0 = GX[idx], GY[idx]
        X1, Y1 = X0 + W, Y0 + H
        blocks = shapely.box(X0, Y0, X1, Y1)
        under = shapely.intersects(hull, blocks) & (shapely.area(shapely.intersection(hull, blocks)) > 1e-6)
        sel = ~under
        idx, viahit, X0, Y0, X1, Y1, blocks = idx[sel], viahit[sel], X0[sel], Y0[sel], X1[sel], Y1[sel], blocks[sel]
        if not len(idx):
            continue
        g_own = shapely.distance(blocks, G)
        b_own = shapely.distance(blocks, geo.body[ref])
        qd = np.maximum(0.65, g_own + T2_MARGIN + 0.05)
        pi, ti = geo.trees[side].query(blocks, predicate="dwithin", distance=qd)
        refs_arr = geo.refs_arr[side]
        not_self = refs_arr[ti] != ref
        pi, ti = pi[not_self], ti[not_self]
        n = len(idx)
        g_q = shapely.distance(blocks[pi], geo.Gs[side][ti])
        b_q = shapely.distance(blocks[pi], geo.bodies[side][ti])
        t2margin = np.full(n, 9.0)
        np.minimum.at(t2margin, pi, g_q - g_own[pi])
        t2bm = np.full(n, 9.0)
        np.minimum.at(t2bm, pi, b_q - b_own[pi])
        t2ok = (g_own <= t2_dist) & (t2margin >= T2_MARGIN) & (t2bm >= 0.0)
        cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
        tw, th_ = X1 - X0, Y1 - Y0
        own_x, own_y = bx1 - bx0, by1 - by0
        tol_x = np.maximum(TOLC, 0.5 * (own_x - tw))
        tol_y = np.maximum(TOLC, 0.5 * (own_y - th_))
        top = (Y1 <= by0 + 0.02) & (np.abs(cx - bcx) <= tol_x)
        bot = (Y0 >= by1 - 0.02) & (np.abs(cx - bcx) <= tol_x)
        lef = (X1 <= bx0 + 0.02) & (np.abs(cy - bcy) <= tol_y)
        rig = (X0 >= bx1 - 0.02) & (np.abs(cy - bcy) <= tol_y)
        cent_ok = ((top | bot) & (A == 0)) | ((lef | rig) & (A != 0))
        off = np.where(top | bot, np.abs(cx - bcx), np.abs(cy - bcy))
        hw_, hh_ = (bx1 - bx0) / 2 + 0.5, (by1 - by0) / 2 + 0.5
        dxn, dyn = (cx - bcx) / hw_, (cy - bcy) / hh_
        sidecode = np.where(np.abs(dyn) >= np.abs(dxn), np.where(dyn < 0, 0, 1), np.where(dxn < 0, 2, 3))
        t1 = cent_ok & (g_own <= T1_GAP)
        comp = np.zeros(n, bool)
        if len(pi):
            qb = geo.bbs[side][ti]
            qx0, qy0, qx1, qy1 = qb[:, 0], qb[:, 1], qb[:, 2], qb[:, 3]
            qcx, qcy = (qx0 + qx1) / 2, (qy0 + qy1) / 2
            tlx, tly = np.maximum(0.4, 0.25 * (qx1 - qx0)), np.maximum(0.4, 0.25 * (qy1 - qy0))
            cxi, cyi = cx[pi], cy[pi]
            qtop = (Y1[pi] <= qy0 + 0.02) & (np.abs(cxi - qcx) <= tlx)
            qbot = (Y0[pi] >= qy1 - 0.02) & (np.abs(cxi - qcx) <= tlx)
            qlef = (X1[pi] <= qx0 + 0.02) & (np.abs(cyi - qcy) <= tly)
            qrig = (X0[pi] >= qx1 - 0.02) & (np.abs(cyi - qcy) <= tly)
            qc = (qtop | qbot | qlef | qrig) & (g_q <= T1_GAP) & (g_q <= g_own[pi] + 1e-6)
            np.logical_or.at(comp, pi[qc], True)
        t1 &= ~comp
        tier = np.where(t1, 1, np.where(t2ok, 2, 0))
        good = tier > 0
        if not good.any():
            continue
        gi = np.nonzero(good)[0]
        cost = np.where(tier[gi] == 1, g_own[gi] + off[gi] * 0.8, 4.0 + g_own[gi]) + extra
        cost = cost + np.where(A != pref, 0.3, 0.0) * np.where(tier[gi] == 2, 1.0, 0.5)
        cost = cost + 3.0 * viahit[gi]
        out.append(dict(A=A, ox=OX[idx][gi], oy=OY[idx][gi], cost=cost, tier=tier[gi], via=viahit[gi], side=sidecode[gi], rl=rl, al=al))
    if not out:
        return None
    sel = _thin(out, 0.2, maxn)
    return _build_cands(out, sel, len(lines), True)


def gen_near(sw: SideWorld, ink: Ink, target, others, lines, owner_court: Optional[str], distance: float = 1.6, margin: float = 0.25,
             angles=(0,), step: float = 0.1, xfilter=None, maxn: int = 300):
    """Candidate positions of a small mark (`lines`: one (text, size, thick) or a dot as (None, size)) that plainly belongs to `target`.

    A position is kept when the mark is within `distance` of `target` and nearer to it
    than to any of `others` by at least `margin`.
    """
    R, o = sw.R, sw.o
    tx0, ty0, tx1, ty1 = target.bounds
    own_court = o["court"].get(owner_court) if owner_court else None
    otree = STRtree(others) if others else None
    out = []
    rects_r, anchors_r = [], []
    vt = 0.0
    for line in lines:
        text, size, thick = line
        if text is None:
            rects_r.append((0.0, vt, size, vt + size))
            anchors_r.append((size / 2, vt + size / 2))
            vt += size
            continue
        x0, y0, x1, y1 = ink.bb(text, size, thick)
        rects_r.append((0.0, vt, x1 - x0, vt + y1 - y0))
        anchors_r.append((-x0, vt - y0))
        vt += y1 - y0
    for A in angles:
        rl = [rot_rect(r, A) for r in rects_r]
        al = [rot_pt(a[0], a[1], A) for a in anchors_r]
        hx0, hy0 = min(r[0] for r in rl), min(r[1] for r in rl)
        hx1, hy1 = max(r[2] for r in rl), max(r[3] for r in rl)
        gx0, gx1 = max(tx0 - hx1 - distance, sw.xmin - hx0), min(tx1 - hx0 + distance, sw.xmax - hx1)
        gy0, gy1 = max(ty0 - hy1 - distance, sw.ymin - hy0), min(ty1 - hy0 + distance, sw.ymax - hy1)
        if gx1 <= gx0 or gy1 <= gy0:
            continue
        GX, GY = np.meshgrid(np.arange(gx0, gx1, step), np.arange(gy0, gy1, step))
        GX, GY = GX.ravel(), GY.ravel()
        res = R.res
        wx0 = max(int(math.floor((gx0 + hx0 - sw.ox) / res)) - 2, 0)
        wx1 = min(int(math.ceil((gx1 + hx1 - sw.ox) / res)) + 2, R.W)
        wy0 = max(int(math.floor((gy0 + hy0 - sw.oy) / res)) - 2, 0)
        wy1 = min(int(math.ceil((gy1 + hy1 - sw.oy) / res)) + 2, R.H)
        hm = sw.hard[wy0:wy1, wx0:wx1].astype(np.int16)
        cc = sw.court_cnt[wy0:wy1, wx0:wx1].astype(np.int16)
        if own_court is not None and not own_court.is_empty:
            im = R.new()
            R.draw(im, own_court)
            cc = cc - np.array(im, dtype=np.uint8)[wy0:wy1, wx0:wx1].astype(np.int16)
        S = sat(((hm > 0) | (cc > 0)).astype(np.uint8))
        SV = sat(sw.via[wy0:wy1, wx0:wx1])
        keep = np.ones(len(GX), bool)
        viahit = np.zeros(len(GX), np.int8)
        rects_abs = []
        for (rx0, ry0, rx1, ry1) in rl:
            X0, Y0, X1, Y1 = GX + rx0, GY + ry0, GX + rx1, GY + ry1
            rects_abs.append((X0, Y0, X1, Y1))
            px0 = np.floor((X0 - sw.ox) / res).astype(int) - wx0 - 1
            px1 = np.ceil((X1 - sw.ox) / res).astype(int) - wx0 + 1
            py0 = np.floor((Y0 - sw.oy) / res).astype(int) - wy0 - 1
            py1 = np.ceil((Y1 - sw.oy) / res).astype(int) - wy0 + 1
            keep &= (px0 >= 0) & (py0 >= 0) & (px1 <= S.shape[1] - 1) & (py1 <= S.shape[0] - 1)
            a, b = np.clip(px0, 0, S.shape[1] - 1), np.clip(px1, 0, S.shape[1] - 1)
            c_, d = np.clip(py0, 0, S.shape[0] - 1), np.clip(py1, 0, S.shape[0] - 1)
            keep &= rect_sum(S, a, c_, b, d) == 0
            viahit += (rect_sum(SV, a, c_, b, d) > 0).astype(np.int8)
        if xfilter is not None:
            r0 = rl[0]
            keep &= xfilter(GX + (r0[0] + r0[2]) / 2, GY + (r0[1] + r0[3]) / 2)
        idx = np.nonzero(keep)[0]
        if not len(idx):
            continue
        boxes = [shapely.box(X0[idx], Y0[idx], X1[idx], Y1[idx]) for (X0, Y0, X1, Y1) in rects_abs]
        dts = [shapely.distance(b, target) for b in boxes]
        sel = dts[0] <= distance
        idx = idx[sel]
        if not len(idx):
            continue
        boxes = [b[sel] for b in boxes]
        dts = [d[sel] for d in dts]
        marg = np.full(len(idx), 9.0)
        if otree is not None:
            qb = shapely.buffer(boxes[0], dts[0] + margin + 1e-6)
            pi, ti = otree.query(qb, predicate="intersects")
            if len(pi):
                og = np.array(others, dtype=object)[ti]
                np.minimum.at(marg, pi, shapely.distance(boxes[0][pi], og) - dts[0][pi])
        sel = marg >= margin
        idx = idx[sel]
        if not len(idx):
            continue
        dts = [d[sel] for d in dts]
        cost = dts[0] + 1.2 * viahit[idx]
        out.append(dict(A=A, ox=GX[idx], oy=GY[idx], cost=cost, tier=np.full(len(idx), 1), via=viahit[idx], side=np.zeros(len(idx), int),
                        rl=rl, al=al, rects=np.stack([np.stack([X0[idx], Y0[idx], X1[idx], Y1[idx]], 1) for (X0, Y0, X1, Y1) in rects_abs], 1)))
    if not out:
        return None
    sel = _thin(out, 0.25, maxn)
    C = Cands()
    n, L = len(sel), len(lines)
    C.cost = np.array([r[0] for r in sel])
    C.vi = np.zeros(n, int)
    C.A = np.array([r[3] for r in sel])
    C.gx = np.array([out[r[1]]["ox"][r[2]] for r in sel])
    C.gy = np.array([out[r[1]]["oy"][r[2]] for r in sel])
    C.via = np.array([out[r[1]]["via"][r[2]] for r in sel])
    C.tier = np.ones(n, int)
    C.side = np.zeros(n, int)
    C.nl = np.full(n, L)
    C.rect = np.array([out[r[1]]["rects"][r[2]] for r in sel], float).reshape(n, L, 4)
    C.anchors = [out[r[1]]["al"] for r in sel]
    return C


# ---------------------------------------------------------------- free-space search
def find_block(sw: SideWorld, rects, shapes, region=None, pref=None, courts=True, step=0.5, topn=400, maxd=None):
    """Positions where a block of rectangles `rects` and (polygon, clearance) `shapes` is free, nearest `pref` first.

    Returns [(distance, x, y)] of the block's origin, at most twelve.
    """
    R = sw.R
    S = mask_sat(sw, courts)
    allr = list(rects) + [p.bounds for p, _c in shapes]
    allc = [0.0] * len(rects) + [c for _p, c in shapes]
    hx0 = min(r[0] - c for r, c in zip(allr, allc))
    hy0 = min(r[1] - c for r, c in zip(allr, allc))
    hx1 = max(r[2] + c for r, c in zip(allr, allc))
    hy1 = max(r[3] + c for r, c in zip(allr, allc))
    bx0, by0, bx1, by1 = region.bounds if region is not None else (sw.xmin, sw.ymin, sw.xmax, sw.ymax)
    xs, ys = np.arange(bx0 - hx0, bx1 - hx1, step), np.arange(by0 - hy0, by1 - hy1, step)
    if not len(xs) or not len(ys):
        return []
    GX, GY = np.meshgrid(xs, ys)
    GX, GY = GX.ravel(), GY.ravel()
    keep = np.ones(len(GX), bool)
    res = R.res
    for (r0, r1, r2, r3), c in zip(allr, allc):
        X0, Y0, X1, Y1 = GX + r0 - c, GY + r1 - c, GX + r2 + c, GY + r3 + c
        px0 = np.floor((X0 - sw.ox) / res).astype(int) - 1
        px1 = np.ceil((X1 - sw.ox) / res).astype(int) + 1
        py0 = np.floor((Y0 - sw.oy) / res).astype(int) - 1
        py1 = np.ceil((Y1 - sw.oy) / res).astype(int) + 1
        keep &= (px0 >= 0) & (py0 >= 0) & (px1 < S.shape[1]) & (py1 < S.shape[0])
        a, b = np.clip(px0, 0, S.shape[1] - 1), np.clip(px1, 0, S.shape[1] - 1)
        c_, d = np.clip(py0, 0, S.shape[0] - 1), np.clip(py1, 0, S.shape[0] - 1)
        keep &= rect_sum(S, a, c_, b, d) == 0
    idx = np.nonzero(keep)[0]
    if region is not None and len(idx):
        hb = shapely.box(GX[idx] + hx0, GY[idx] + hy0, GX[idx] + hx1, GY[idx] + hy1)
        shapely.prepare(region)
        idx = idx[shapely.contains(region, hb)]
    if not len(idx):
        return []
    cx, cy = GX[idx] + (hx0 + hx1) / 2, GY[idx] + (hy0 + hy1) / 2
    cost = np.hypot(cx - pref[0], cy - pref[1]) if pref is not None else np.zeros(len(idx))
    if maxd is not None:
        m = cost <= maxd
        idx, cost = idx[m], cost[m]
    order = np.argsort(cost, kind="stable")[:topn]
    geoms = list(sw.o["hard"]) + [g for _, g in sw.o["silk"]] + list(sw.o["court"].values())
    tree = STRtree(geoms) if geoms else None
    found = []
    for k in order:
        i = idx[k]
        ok = True
        for p, c in shapes:
            q = affinity.translate(p, GX[i], GY[i]).buffer(c, 8)
            if tree is not None:
                for j in tree.query(q, predicate="intersects"):
                    if geoms[j].intersects(q) and not (not courts and j >= len(sw.o["hard"]) + len(sw.o["silk"])):
                        ok = False
                        break
            if ok and any(g.intersects(q) for g in sw.fixed_polys):
                ok = False
            if not ok:
                break
        if ok:
            found.append((float(cost[k]), float(GX[i]), float(GY[i])))
            if len(found) >= 12:
                break
    return found


def triangle_polys(side_len: float = 8.0):
    """A warning triangle and a lightning bolt in it, centred on the origin, apex towards -y."""
    h = side_len * math.sqrt(3) / 2
    tri = [(0, -2 * h / 3), (side_len / 2, h / 3), (-side_len / 2, h / 3)]
    bolt = [(0.55, -1.95), (-0.95, 0.25), (-0.05, 0.25), (-0.6, 1.95), (0.95, -0.35), (0.05, -0.35)]
    return tri, [(x, y + 0.45) for x, y in bolt]   # the bolt is drawn for an 8 mm triangle and scaled with it


# ---------------------------------------------------------------- the solver
class Placed:
    """The placed text rectangles of one side."""

    def __init__(self):
        self.rows = []

    def arrays(self):
        if not self.rows:
            return np.zeros((0, 4)), np.zeros(0), np.zeros(0, bool), np.zeros(0), np.zeros(0, dtype=object)
        return (np.array([r[:4] for r in self.rows], float), np.array([r[4] for r in self.rows]),
                np.array([r[5] for r in self.rows]), np.array([r[6] for r in self.rows]),
                np.array([r[7] for r in self.rows], dtype=object))

    def add(self, iid, rects, A, istext, thr=0.6):
        for r in rects:
            self.rows.append((r[0], r[1], r[2], r[3], A, istext, thr, iid))

    def remove(self, iid):
        self.rows = [r for r in self.rows if r[7] != iid]


def dx_raw(p0, p1, c0, c1):
    return np.maximum(p0[None, :] - c1, c0 - p1[None, :])


def conflicts(C, istext, P, PA, PT, Pthr, thr=1.0):
    """A boolean matrix (candidates x placed rows) of conflicts between each candidate and the rows already placed."""
    n, m = len(C.cost), len(P)
    if m == 0:
        return np.zeros((n, 0), bool)
    res = np.zeros((n, m), bool)
    for l in range(C.rect.shape[1]):
        c = C.rect[:, l, :]
        valid = ~np.isnan(c[:, 0])
        c0, c1, c2, c3 = c[:, 0][:, None], c[:, 2][:, None], c[:, 1][:, None], c[:, 3][:, None]
        dx = np.maximum(np.maximum(P[:, 0][None, :] - c1, c0 - P[:, 2][None, :]), 0)
        dy = np.maximum(np.maximum(P[:, 1][None, :] - c3, c2 - P[:, 3][None, :]), 0)
        cf = np.hypot(dx, dy) < GAP_TEXT
        if istext:
            same = (PA[None, :] == C.A[:, None]) & PT[None, :]
            vcx, vcy = (c0 + c1) / 2, (c2 + c3) / 2
            pcx, pcy = ((P[:, 0] + P[:, 2]) / 2)[None, :], ((P[:, 1] + P[:, 3]) / 2)[None, :]
            is0 = (C.A == 0)[:, None]
            vdiff = np.where(is0, np.abs(vcy - pcy), np.abs(vcx - pcx))
            gu = np.where(is0, dx_raw(P[:, 0], P[:, 2], c0, c1), dx_raw(P[:, 1], P[:, 3], c2, c3))
            tt = np.maximum(Pthr[None, :], thr)
            cf = cf | (same & (vdiff < tt) & (gu < RUN_GAP))
        res |= cf & valid[:, None]
    return res


class Solver:
    """Assigns one candidate to each item: greedily by fewest options, then by ejecting and re-placing neighbours."""

    def __init__(self, items, placed_fixed: Placed):
        self.items = {it.id: it for it in items}
        self.pl = placed_fixed
        self.assign = {}
        self.fail = []

    def conf_matrix(self, it):
        C = it.cands
        P, PA, PT, Pthr, Pid = self.pl.arrays()
        if len(P):
            r = C.rect
            x0, x1 = np.nanmin(r[:, :, 0]) - 2.5, np.nanmax(r[:, :, 2]) + 2.5
            y0, y1 = np.nanmin(r[:, :, 1]) - 2.5, np.nanmax(r[:, :, 3]) + 2.5
            sel = (P[:, 2] > x0) & (P[:, 0] < x1) & (P[:, 3] > y0) & (P[:, 1] < y1)
            P, PA, PT, Pthr, Pid = P[sel], PA[sel], PT[sel], Pthr[sel], Pid[sel]
        return conflicts(C, it.kind == "text", P, PA, PT, Pthr), Pid

    def place(self, it, ci):
        C = it.cands
        self.pl.add(it.id, [C.rect[ci, l] for l in range(int(C.nl[ci]))], int(C.A[ci]), it.kind == "text")
        self.assign[it.id] = ci

    def unplace(self, iid):
        self.pl.remove(iid)
        self.assign.pop(iid, None)

    def try_place(self, it):
        if it.cands is None:
            return False
        M, _pid = self.conf_matrix(it)
        ok = ~M.any(axis=1) if M.shape[1] else np.ones(len(it.cands.cost), bool)
        if not ok.any():
            return False
        self.place(it, int(np.argmin(np.where(ok, it.cands.cost, np.inf))))
        return True

    def run(self, order, repair_rounds: int = 4):
        self.fail = []
        for it in order:
            if not self.try_place(it):
                self.fail.append(it)
        for _round in range(repair_rounds):
            if not self.fail:
                break
            still = [it for it in self.fail if not self.eject(it)]
            if len(still) == len(self.fail):
                self.fail = still
                break
            self.fail = still
        return self.fail

    def eject(self, it, maxv: int = 3):
        if it.cands is None:
            return False
        M, Pid = self.conf_matrix(it)
        C = it.cands
        if M.shape[1] == 0:
            return self.try_place(it)
        fixed_ids = {r[7] for r in self.pl.rows if r[7] not in self.assign}
        cands = []
        for ci in np.argsort(C.cost, kind="stable")[:200]:
            victims = set(Pid[M[ci]])
            if victims & fixed_ids or len(victims) > maxv:
                continue
            cands.append((C.cost[ci] + 2.0 * len(victims), int(ci), victims))
        cands.sort(key=lambda t: (t[0], t[1]))
        for _cost, ci, victims in cands[:25]:
            saved = {x: self.assign[x] for x in sorted(victims)}
            for x in saved:
                self.unplace(x)
            self.place(it, ci)
            good, moved = True, []
            for x in saved:
                if not self.try_place(self.items[x]):
                    good = False
                    break
                moved.append(x)
            if good:
                return True
            for x in moved:
                self.unplace(x)
            self.unplace(it.id)
            for x, cj in saved.items():
                self.place(self.items[x], cj)
        return False


def min_conflicts(sv: Solver, fail, iters: int = 400, seed: int = 1):
    """A randomised ejection search from a fixed seed; the best state found is kept and the items still failing returned."""
    rnd = random.Random(seed)
    fail = list(fail)
    best_fail, best_state = list(fail), dict(sv.assign)
    tabu = {}
    for it_no in range(iters):
        if not fail:
            break
        f = rnd.choice(fail)
        if f.cands is None:
            fail.remove(f)
            continue
        M, Pid = sv.conf_matrix(f)
        C = f.cands
        fixed_ids = {r[7] for r in sv.pl.rows if r[7] not in sv.assign}
        opts = []
        for ci in np.argsort(C.cost, kind="stable")[:120]:
            victims = set(Pid[M[ci]]) if M.shape[1] else set()
            if victims & fixed_ids:
                continue
            pen = sum(1.5 for x in victims if tabu.get((f.id, x), 0) > it_no)
            opts.append((len(victims) * 2.0 + C.cost[ci] * 0.3 + pen + rnd.random() * 1.5, int(ci), victims))
        if not opts:
            continue
        opts.sort(key=lambda t: (t[0], t[1]))
        _s, ci, victims = opts[0]
        order = sorted(victims)
        for x in order:
            sv.unplace(x)
            tabu[(x, f.id)] = it_no + 15
        sv.place(f, ci)
        fail.remove(f)
        for x in order:
            if not sv.try_place(sv.items[x]):
                fail.append(sv.items[x])
        if len(fail) < len(best_fail):
            best_fail, best_state = list(fail), dict(sv.assign)
    for x in list(sv.assign):
        sv.unplace(x)
    for x, ci in best_state.items():
        sv.place(sv.items[x], ci)
    return best_fail
