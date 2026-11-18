"""The silkscreen command's placement: from a board's extract and its table to the plan of what to draw.

Order, as the board method has it: the fixed items first (warning legends, fixed
texts), then pin-1 dots, then every part's reference label by solver, then
connector, tab, fuse and test-point names, then pin-1 marks. A label that finds no
free position is not drawn: its Reference moves to the fab layer and the part is
listed as unplaced. Nothing here is random: the same extract and table give the
same plan.

Needs numpy, shapely and Pillow (see silkscreen_engine).
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional

import silkscreen_engine as eng
from silkscreen_engine import (Cands, GAP_TEXT, Item, Ink, Placed, Solver, SideWorld, World, PartGeo, box, find_block, gen_near,
                               gen_ref, mask_sat, min_conflicts, np, polys, rect_sum, rot_rect, triangle_polys, unary_union, view,
                               Point, Polygon)

EXTRA_SMALL = 2.5      # cost of a smaller size than the first the table lists
TAB_FUSE_EXTRA = (8.0, 40.0)   # cost of a tab's or a fuse's label alone, so the label that carries the name is preferred


def board_x(side: str, x: float) -> float:
    return x if side == "F" else -x


def merge_cands(parts):
    """One Cands from [(Cands, variant index, extra cost)], dropping the empty ones."""
    parts = [(C, vi, ex) for C, vi, ex in parts if C is not None]
    if not parts:
        return None
    L = max(C.rect.shape[1] for C, _, _ in parts)
    M = Cands()
    M.cost = np.concatenate([C.cost + ex for C, _vi, ex in parts])
    M.vi = np.concatenate([np.full(len(C.cost), vi) for C, vi, _ex in parts])
    for field in ("A", "gx", "gy", "via", "tier", "side", "nl"):
        M.__dict__[field] = np.concatenate([getattr(C, field) for C, _vi, _ex in parts])
    rects = []
    for C, _vi, _ex in parts:
        r = np.full((len(C.cost), L, 4), np.nan)
        r[:, :C.rect.shape[1], :] = C.rect
        rects.append(r)
    M.rect = np.concatenate(rects)
    M.anchors = [a for C, _vi, _ex in parts for a in C.anchors]
    return M


def subset(C, mask):
    S = Cands()
    for field in ("cost", "vi", "A", "gx", "gy", "via", "tier", "side", "nl", "rect"):
        S.__dict__[field] = getattr(C, field)[mask]
    S.anchors = [a for a, keep in zip(C.anchors, mask) if keep]
    return S


class Placement:
    """One run of the placer over a board's extract."""

    def __init__(self, data: dict, table: dict, ink: Ink, res: float = 0.025, solver_iterations: int = 2500):
        self.table = table
        self.ink = ink
        self.iterations = solver_iterations
        keep = {r for r, o in table["parts"].items() if o.get("reference") == "skip"}
        self.world = World(data, table["clearance"], table["edge_keepin"], table["slot_keepin"], keep)
        self.D = self.world.D
        self.SW = {s: SideWorld(self.world, s, res) for s in "FB"}
        self.PL = {s: Placed() for s in "FB"}
        self.plan: Dict[str, object] = {"refs": {}, "texts": [], "polys": [], "circles": []}
        self.notes: List[dict] = []          # {"finding", "item", "detail"}
        self.report: Dict[str, object] = {"fixed": {}, "moved": []}
        self.geo = PartGeo(self.world)
        self.fixed_count = 0
        self.names: Dict[str, str] = {}      # reference -> the name text its label carries or stands beside
        self.name_kind: Dict[str, str] = {}

    # ------------------------------------------------------------ table helpers
    def thick(self, size: float) -> float:
        return self.table["thickness"][float(size)]

    def note(self, finding: str, item: str, detail: str):
        self.notes.append({"finding": finding, "item": item, "detail": detail})

    def sizes_for(self, ref: str) -> List[float]:
        return list(self.table["parts"].get(ref, {}).get("reference_sizes", self.table["reference_sizes"]))

    # ------------------------------------------------------------ names
    def derive_names(self):
        """The name text each part's label carries: a tab's or a connector's function, a fuse's rating, a test point's net."""
        t, fps = self.table, self.world.fps
        fn, tabs, fuse, tp = t["function_names"], t["tabs"], t["fuses"], t["test_points"]
        known_fuses = dict(fuse["known"])
        for ref, f in fps.items():
            override = t["parts"].get(ref, {}).get("name")
            if override == "skip":
                continue
            if override:
                self.names[ref], self.name_kind[ref] = override, "override"
                continue
            if f["lib"].startswith(tabs["library_prefix"]):
                value = re.sub(tabs["strip_value"], "", f["value"]).replace("_", " ").upper()
                text = tabs["known"].get(ref) or tabs["abbreviations"].get(value, value)
                self.names[ref], self.name_kind[ref] = text, "tab"
                if ref not in tabs["known"]:
                    self.note("NOTE", ref, f"tab {ref} ({f['value']}): name derived from its Value: {text}")
            elif re.match(fuse["pattern"], ref):
                text = self.fuse_text(ref, f)
                if text:
                    self.names[ref], self.name_kind[ref] = text, "fuse"
                    if known_fuses.get(ref) not in (None, text):
                        self.note("NOTE", ref, f"fuse {ref}: rating text {text} differs from the table's {known_fuses[ref]}")
                    if ref not in known_fuses:
                        self.note("NOTE", ref, f"fuse {ref} ({f['value']}): rating text {text} derived from Value and Rating")
                elif ref in known_fuses:
                    self.names[ref], self.name_kind[ref] = known_fuses[ref], "fuse"
            elif re.match(fn["pattern"], ref):
                text = fn["known"].get(ref) or f["value"].replace("_", " ").upper()
                text = fn["abbreviations"].get(text, text)
                if text:
                    self.names[ref], self.name_kind[ref] = text, "function"
            elif re.match(tp["pattern"], ref):
                nets = [p["net"] for p in self.D["pads"] if p["ref"] == ref and p["net"]]
                if nets:
                    self.names[ref], self.name_kind[ref] = nets[0].split("/")[-1], "net"
        for ref in sorted(set(fn["known"]) | set(tabs["known"])):
            if ref not in fps:
                self.note("NOTE", ref, f"{ref} is named in the table and is not on the board: its name text is skipped")
        for ref in sorted(known_fuses):
            if ref not in fps:
                self.note("NOTE", ref, f"fuse {ref} is named in the table and is not on the board: no fuse text for it")

    def fuse_text(self, ref: str, f: dict) -> Optional[str]:
        fuse = self.table["fuses"]
        rating, lib = f["fields"].get("Rating", "").lower(), f["lib"].lower()
        if not (any(w in lib for w in fuse["holder_library_words"]) or any(w in rating for w in fuse["rating_words"])):
            return None
        if any(w in rating for w in fuse["exclude_words"]):
            return None
        m = re.match(r"^([0-9.]+)\s*A", f["value"])
        if not m:
            return None
        amps = float(m.group(1))
        amp_text = ("%dmA" % round(amps * 1000)) if amps < 1 else ("%gA" % amps)
        mv = re.search(r"_(\d{2,3})V$", f["value"]) or re.search(r"(\d{2,3})\s*V\s*AC", f["fields"].get("Rating", ""))
        if not mv:
            return None
        return fuse["format"].format(amps=amp_text, volts=mv.group(1))

    # ------------------------------------------------------------ emitting
    def emit_text(self, side: str, text: str, size: float, A: int, ax: float, ay: float):
        th = self.thick(size)
        self.ink.ensure([(text, size, th)])
        r = rot_rect(self.ink.bb(text, size, th), A)
        rect = (ax + r[0], ay + r[1], ax + r[2], ay + r[3])
        fa = A if side == "F" else (-A) % 360
        self.plan["texts"].append(dict(text=text, side=side, x=board_x(side, ax), y=ay, angle=fa, size=size, thick=th))
        self.fixed_count += 1
        self.PL[side].add("fix:%d" % self.fixed_count, [rect], A, True, thr=0.5 * size + 0.1)
        self.SW[side].add_fixed(box(*rect), GAP_TEXT)
        return rect

    def emit_poly(self, side: str, pts_view, width: float, fill: bool = False):
        self.plan["polys"].append(dict(side=side, pts=[(board_x(side, x), y) for x, y in pts_view], width=width, fill=fill))
        self.SW[side].add_fixed(Polygon(pts_view).buffer(width / 2, 4), 0.3)

    # ------------------------------------------------------------ fixed items
    def region(self, name: str):
        areas = [Polygon(z["outline"][0][0]) for z in self.D["zones"] if z["rule"] and z["name"] == name and z["outline"]]
        return unary_union(areas) if areas else None

    def legend_stage(self):
        for legend in self.table["legends"]:
            lid, side = legend["id"], legend.get("side", "F")
            region = self.region(legend["region"])
            if region is None or region.is_empty:
                self.note("NOTE", lid, f"legend {lid}: the board has no rule area named '{legend['region']}': legend skipped")
                self.report["fixed"][lid] = None
                continue
            sw = self.SW[side]
            lines = [(l["text"], float(l["size"]), self.thick(l["size"])) for l in legend["lines"]]
            self.ink.ensure(lines)
            gap, stack, vt = 0.5, [], 0.0
            bbs = [self.ink.bb(*l) for l in lines]
            width = max(b[2] - b[0] for b in bbs)
            for (text, size, _th), bb in zip(lines, bbs):
                ax = width / 2 - (bb[0] + bb[2]) / 2
                ay = vt - bb[1]
                stack.append((text, size, ax, ay, (ax + bb[0], ay + bb[1], ax + bb[2], ay + bb[3])))
                vt += (bb[3] - bb[1]) + gap
            region_view = view(region.buffer(-1.0), side)
            if region_view.is_empty:
                self.note("NOTE", lid, f"legend {lid}: the rule area '{legend['region']}' is too small to hold it: legend skipped")
                continue
            prefer = legend.get("prefer")
            pref = (board_x(side, prefer[0]), prefer[1]) if prefer else (region_view.centroid.x, region_view.centroid.y)
            found = find_block(sw, [s[4] for s in stack], [], region=region_view, pref=pref, courts=True, step=0.5)
            if not found:
                self.note("NOTE", lid, f"legend {lid}: no free spot inside '{legend['region']}': legend skipped")
                self.report["fixed"][lid] = None
                continue
            _c, gx, gy = found[0]
            for text, size, ax, ay, _rect in stack:
                self.emit_text(side, text, size, 0, gx + ax, gy + ay)
            tb = unary_union([box(gx + s[4][0], gy + s[4][1], gx + s[4][2], gy + s[4][3]) for s in stack]).bounds
            where = {"side": side, "text_at": [round(board_x(side, (tb[0] + tb[2]) / 2), 2), round((tb[1] + tb[3]) / 2, 2)]}
            if legend.get("symbol") == "hazard-triangle":
                side_len = float(legend.get("symbol_size", 8.0))
                k = side_len / 8.0
                tri, bolt = triangle_polys(side_len)
                h = side_len * math.sqrt(3) / 2
                tri_l = [(x, y + h / 6) for x, y in tri]
                bolt_l = [(x * k, y * k + h / 6) for x, y in bolt]
                tc = ((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2)
                spot = find_block(sw, [], [(Polygon(tri_l), 0.3 + 0.15)], region=region_view, pref=tc, courts=True, step=0.25, maxd=40)
                if spot:
                    _c2, tx, ty = spot[0]
                    self.emit_poly(side, [(tx + x, ty + y) for x, y in tri_l], 0.3)
                    self.emit_poly(side, [(tx + x, ty + y) for x, y in bolt_l], 0.1, fill=True)
                    where["symbol_at"] = [round(board_x(side, tx), 2), round(ty, 2)]
                else:
                    self.note("NOTE", lid, f"legend {lid}: no free spot for its triangle: text drawn without it")
            self.report["fixed"][lid] = where

    def fixed_text_stage(self):
        for fixed in self.table["fixed_texts"]:
            fid, side, size, A = fixed["id"], fixed.get("side", "F"), float(fixed["size"]), int(fixed.get("angle", 0))
            th = self.thick(size)
            self.ink.ensure([(fixed["text"], size, th)])
            rr = rot_rect(self.ink.bb(fixed["text"], size, th), A)
            sw = self.SW[side]
            cx, cy = board_x(side, fixed["at"][0]), float(fixed["at"][1])
            ax, ay = cx - (rr[0] + rr[2]) / 2, cy - (rr[1] + rr[3]) / 2
            S = mask_sat(sw, False)
            res = sw.R.res
            px0 = int(math.floor((ax + rr[0] - sw.ox) / res)) - 1
            px1 = int(math.ceil((ax + rr[2] - sw.ox) / res)) + 1
            py0 = int(math.floor((ay + rr[1] - sw.oy) / res)) - 1
            py1 = int(math.ceil((ay + rr[3] - sw.oy) / res)) + 1
            free = 0 <= px0 and 0 <= py0 and px1 < S.shape[1] and py1 < S.shape[0] and rect_sum(S, px0, py0, px1, py1) == 0
            free = free and not any(g.intersects(box(ax + rr[0], ay + rr[1], ax + rr[2], ay + rr[3])) for g in sw.fixed_polys)
            if free:
                self.report["fixed"][fid] = dict(side=side, at=[round(fixed["at"][0], 2), round(fixed["at"][1], 2)], kept_position=True)
                self.emit_text(side, fixed["text"], size, A, ax, ay)
                continue
            found = find_block(sw, [rr], [], pref=(cx, cy), courts=False, step=0.25, maxd=float(fixed.get("max_move", 30.0)))
            if not found:
                self.report["fixed"][fid] = None
                self.note("NOTE", fid, f"fixed text '{fixed['text']}' ({fid}) has no free spot within reach of its place: skipped")
                continue
            dist, gx, gy = found[0]
            at = [round(board_x(side, gx + (rr[0] + rr[2]) / 2), 2), round(gy + (rr[1] + rr[3]) / 2, 2)]
            self.note("MOVED", fid, f"fixed text '{fixed['text']}' moved {dist:.1f} mm from its place in the table, which is taken: now at ({at[0]}, {at[1]})")
            self.report["fixed"][fid] = dict(side=side, at=at, kept_position=False, moved_mm=round(dist, 2))
            self.emit_text(side, fixed["text"], size, A, gx, gy)

    # ------------------------------------------------------------ reference labels
    def pads_view(self, ref: str):
        f = self.world.fps[ref]
        s = f["side"]
        out = []
        for p in self.D["pads"]:
            if p["ref"] == ref and p["side"] == s:
                out.append((p["pad"], view(polys(p["rings"]), s), (board_x(s, p["cx"]), p["cy"])))
        return out

    def preferred_angle(self, ref: str) -> int:
        b = self.geo.bb[ref]
        return 90 if (b[3] - b[1]) > 1.4 * (b[2] - b[0]) else 0

    def build_ref_items(self, side: str) -> List[Item]:
        items = []
        for ref, f in self.world.fps.items():
            if f["side"] != side or self.table["parts"].get(ref, {}).get("reference") == "skip":
                continue
            pref, sizes = self.preferred_angle(ref), self.sizes_for(ref)
            first = sizes[0]
            name = self.names.get(ref)
            variants, parts = [], []
            composite = None
            if name and self.name_kind[ref] in ("tab", "fuse"):
                composite = [(ref, first, self.thick(first)), (name, first, self.thick(first))]
                variants.append(dict(lines=composite))
                angles = (0,) if self.name_kind[ref] == "tab" else (0, 90)
                parts.append((gen_ref(self.SW[side], self.geo, ref, self.ink, composite, angles=angles, pref=pref), 0, 0.0))
            for sz in sizes:
                lines = [(ref, sz, self.thick(sz))]
                variants.append(dict(lines=lines))
                extra = (0.0 if sz == first else EXTRA_SMALL)
                if self.name_kind.get(ref) == "tab":
                    extra += TAB_FUSE_EXTRA[0]
                elif self.name_kind.get(ref) == "fuse":
                    extra += TAB_FUSE_EXTRA[1]
                angles = (0,) if self.name_kind.get(ref) == "tab" else (0, 90)
                parts.append((gen_ref(self.SW[side], self.geo, ref, self.ink, lines, angles=angles, pref=pref), len(variants) - 1, extra))
            it = Item("ref:" + ref, side, owner=ref, target=self.geo.body[ref], variants=variants, pref_angle=pref)
            it.cands, it.composite = merge_cands(parts), composite
            items.append(it)
        return items

    def solve_side(self, items, side):
        sv = Solver(items, self.PL[side])
        order = sorted([it for it in items if it.cands is not None], key=lambda it: len(it.cands.cost))
        fail = [x for x in sv.run(order) if x.cands is not None]
        if fail:
            fail = min_conflicts(sv, fail, iters=self.iterations, seed=1)
        return sv, fail + [it for it in items if it.cands is None]

    # ------------------------------------------------------------ names beside labels
    def names_stage(self, res):
        sizes = self.table["name_sizes"]
        for s in "FB":
            sv, items, fail = res[s]
            new = []
            for it in list(items):
                ref = it.ref
                if it.id not in sv.assign or ref not in self.names:
                    continue
                chosen = it.variants[int(it.cands.vi[sv.assign[it.id]])]["lines"]
                if len(chosen) > 1:
                    continue
                nm = self.names[ref]
                ci = sv.assign[it.id]
                rr = it.cands.rect[ci, 0]
                rc = ((rr[0] + rr[2]) / 2, (rr[1] + rr[3]) / 2)
                parts = [(gen_ref(self.SW[s], self.geo, ref, self.ink, [(nm, sz, self.thick(sz))], pref=it.pref_angle, t2_dist=4.0),
                          k, 0.0 if k == 0 else EXTRA_SMALL) for k, sz in enumerate(sizes)]
                C = merge_cands(parts)
                if C is None:
                    self.report.setdefault("name_skipped", []).append(ref)
                    continue
                cx, cy = (C.rect[:, 0, 0] + C.rect[:, 0, 2]) / 2, (C.rect[:, 0, 1] + C.rect[:, 0, 3]) / 2
                C.cost = C.cost + 0.8 * np.hypot(cx - rc[0], cy - rc[1])
                P, _PA, _PT, _Pthr, Pid = self.PL[s].arrays()
                if len(P):
                    keepm = np.array([str(i) not in ("ref:" + ref, "name:" + ref) for i in Pid])
                    Pq, r0 = P[keepm], C.rect[:, 0, :]
                    if len(Pq):
                        dxx = np.maximum(np.maximum(Pq[:, 0][None, :] - r0[:, 2][:, None], r0[:, 0][:, None] - Pq[:, 2][None, :]), 0)
                        dyy = np.maximum(np.maximum(Pq[:, 1][None, :] - r0[:, 3][:, None], r0[:, 1][:, None] - Pq[:, 3][None, :]), 0)
                        dmin = np.hypot(dxx, dyy).min(axis=1)
                        C.cost = C.cost + 4.0 * (dmin < 1.6)
                        if self.name_kind[ref] == "function":
                            tooclose = dmin < 1.0
                            if (~tooclose).any():
                                C = subset(C, ~tooclose)
                            else:
                                self.report.setdefault("name_skipped", []).append(ref)
                                continue
                n = Item("name:" + ref, s, owner=ref, target=it.target, variants=[dict(lines=[(nm, sz, self.thick(sz))]) for sz in sizes],
                         pref_angle=it.pref_angle)
                n.cands, n.nm = C, nm
                new.append(n)
            for n in new:
                sv.items[n.id] = n
            for n in sorted(new, key=lambda x: len(x.cands.cost)):
                if not sv.try_place(n):
                    sv.eject(n)
            by_ref = {it.ref: it for it in items if it.id.startswith("ref:")}
            for n in new:
                if n.id in sv.assign:
                    continue
                it = by_ref[n.ref]
                vars_, parts = [], []
                for k, sz in enumerate(sizes):
                    lines = [(n.ref, sz, self.thick(sz)), (n.nm, sz, self.thick(sz))]
                    vars_.append(dict(lines=lines))
                    parts.append((gen_ref(self.SW[s], self.geo, n.ref, self.ink, lines, pref=it.pref_angle, t2_dist=3.5), k,
                                  0.0 if k == 0 else EXTRA_SMALL))
                C2 = merge_cands(parts)
                if C2 is None:
                    self.report.setdefault("name_skipped", []).append(n.ref)
                    continue
                old_ci = sv.assign[it.id]
                sv.unplace(it.id)
                it2 = Item(it.id, s, owner=it.owner, target=it.target, variants=vars_, pref_angle=it.pref_angle)
                it2.cands = C2
                sv.items[it.id] = it2
                items[items.index(it)] = it2
                if sv.try_place(it2):
                    self.report.setdefault("composite_retry", []).append(n.ref)
                else:
                    items[items.index(it2)] = it
                    sv.items[it.id] = it
                    sv.place(it, old_ci)
                    self.report.setdefault("name_skipped", []).append(n.ref)
            res[s] = (sv, items + new, fail)
        return res

    # ------------------------------------------------------------ pin-1 dots and marks
    def pin1_kind(self, ref: str) -> Optional[str]:
        override = self.table["parts"].get(ref, {}).get("pin1")
        if override == "none":
            return None
        if override in ("dot", "mark"):
            return override
        if ref in self.table["pin1"]["dot"]:
            return "dot"
        if ref in self.table["pin1"]["mark"]:
            return "mark"
        return None

    def pin1_items(self, want: str):
        out = {s: [] for s in "FB"}
        for ref, f in self.world.fps.items():
            if self.pin1_kind(ref) != want:
                continue
            s = f["side"]
            pv = self.pads_view(ref)
            p1 = [x for x in pv if x[0] == "1"]
            if not p1:
                self.note("NOTE", ref, f"{ref} has no pad 1 on its side: no pin-1 {want} for it")
                continue
            others = [x[1] for x in pv if x[0] != "1"]
            if want == "dot":
                allc = np.array([x[2] for x in pv])
                pc, c1 = allc.mean(axis=0), np.array(p1[0][2])
                d1 = float(np.hypot(*(c1 - pc)))
                item = Item("dot:" + ref, s, kind="dot", owner=ref, target=p1[0][1], variants=[dict(lines=[(None, 0.6, 0.0)])], pref_angle=0)
                item.xfilter = (lambda pcx, pcy, d: (lambda X, Y: np.hypot(X - pcx, Y - pcy) > d - 0.05))(pc[0], pc[1], d1)
                item.spec = dict(lines=[(None, 0.6, 0.0)], distance=1.8, margin=0.2, angles=(0,))
            else:
                item = Item("one:" + ref, s, owner=ref, target=p1[0][1], variants=[dict(lines=[("1", 1.0, self.thick(1.0) if 1.0 in self.table["thickness"] else 0.15)])],
                            pref_angle=0)
                item.xfilter = None
                item.spec = dict(lines=item.variants[0]["lines"], distance=1.6, margin=0.25, angles=(0,))
            item.others = others
            out[s].append(item)
        return out

    def gen_pin1(self, its):
        for s in "FB":
            for it in its[s]:
                spec = it.spec
                lines = spec["lines"]
                for text, size, thick in lines:
                    if text is not None:
                        self.ink.ensure([(text, size, thick)])
                it.cands = gen_near(self.SW[s], self.ink, it.target, it.others, lines, it.owner, distance=spec["distance"],
                                    margin=spec["margin"], angles=spec["angles"], xfilter=it.xfilter)

    def dots_first(self):
        its = self.pin1_items("dot")
        self.gen_pin1(its)
        for s in "FB":
            ok = [m for m in its[s] if m.cands is not None]
            sv = Solver(ok, self.PL[s])
            sv.run(sorted(ok, key=lambda x: len(x.cands.cost)))
            for m in its[s]:
                if m.id in sv.assign:
                    C, ci = m.cands, sv.assign[m.id]
                    al = C.anchors[ci]
                    cx, cy = float(C.gx[ci]) + al[0][0], float(C.gy[ci]) + al[0][1]
                    self.plan["circles"].append(dict(side=s, x=board_x(s, cx), y=cy, r=0.25, width=0.1))
                    self.SW[s].add_fixed(Point(cx, cy).buffer(0.3), 0.15)
                else:
                    self.report.setdefault("marks_skipped", []).append(m.id)

    def marks(self, res):
        its = self.pin1_items("mark")
        self.gen_pin1(its)
        for s in "FB":
            ok = [m for m in its[s] if m.cands is not None]
            sv2 = Solver(ok, self.PL[s])
            sv2.run(sorted(ok, key=lambda x: len(x.cands.cost)))
            sv, items, fail = res[s]
            sv.assign.update(sv2.assign)
            sv.items.update(sv2.items)
            res[s] = (sv, items + ok, fail)
            for m in its[s]:
                if m.id not in sv2.assign:
                    self.report.setdefault("marks_skipped", []).append(m.id)
        return res

    # ------------------------------------------------------------ emitting the solved items
    def emit_all(self, res):
        for s in "FB":
            sv, items, _fail = res[s]
            for it in items:
                if it.id not in sv.assign:
                    continue
                C, ci = it.cands, sv.assign[it.id]
                var = it.variants[int(C.vi[ci])]
                al = C.anchors[ci]
                gx, gy, A = float(C.gx[ci]), float(C.gy[ci]), int(C.A[ci])
                fa = A if s == "F" else (-A) % 360
                if it.kind == "dot":
                    continue
                for k, (text, size, thick) in enumerate(var["lines"]):
                    ax, ay = gx + al[k][0], gy + al[k][1]
                    if it.id.startswith("ref:") and k == 0:
                        self.plan["refs"][it.ref] = dict(layer="F.SilkS" if s == "F" else "B.SilkS", x=board_x(s, ax), y=ay, angle=fa,
                                                         size=size, thick=thick)
                    else:
                        self.plan["texts"].append(dict(text=text, side=s, x=board_x(s, ax), y=ay, angle=fa, size=size, thick=thick))
        for ref in self.world.fps:
            if self.table["parts"].get(ref, {}).get("reference") == "skip":
                self.plan["refs"][ref] = dict(keep=True)
            elif ref not in self.plan["refs"]:
                self.plan["refs"][ref] = dict(fab=True)

    def unplaced_report(self) -> List[dict]:
        rows = []
        fps = self.world.fps
        for ref in sorted(r for r, v in self.plan["refs"].items() if v.get("fab")):
            f = fps[ref]
            near = sorted((math.hypot(f["x"] - g["x"], f["y"] - g["y"]), q) for q, g in fps.items() if q != ref and g["side"] == f["side"])[:3]
            rows.append({"ref": ref, "side": f["side"], "x": round(f["x"], 3), "y": round(f["y"], 3),
                         "nearest": [{"ref": q, "distance": round(d, 2)} for d, q in near]})
        return rows

    # ------------------------------------------------------------ the run
    def run(self) -> dict:
        self.derive_names()
        pre = []
        for ref in self.world.fps:
            for sz in self.sizes_for(ref):
                pre.append((ref, sz, self.thick(sz)))
            if ref in self.names:
                for sz in set(self.table["name_sizes"]) | set(self.sizes_for(ref)):
                    pre.append((self.names[ref], sz, self.thick(sz)))
        for legend in self.table["legends"]:
            pre += [(l["text"], float(l["size"]), self.thick(l["size"])) for l in legend["lines"]]
        pre += [(f["text"], float(f["size"]), self.thick(f["size"])) for f in self.table["fixed_texts"]]
        pre.append(("1", 1.0, self.thick(1.0) if 1.0 in self.table["thickness"] else 0.15))
        self.ink.ensure(pre)
        self.legend_stage()
        self.fixed_text_stage()
        self.dots_first()
        res = {}
        for s in "FB":
            items = self.build_ref_items(s)
            sv, fail = self.solve_side(items, s)
            res[s] = (sv, items, fail)
        res = self.names_stage(res)
        res = self.marks(res)
        self.emit_all(res)
        unplaced = self.unplaced_report()
        for row in unplaced:
            self.note("UNPLACED", row["ref"], f"{row['ref']} on the {row['side']} side at ({row['x']}, {row['y']}) has no free place for its label: "
                      f"its reference moves to the fab layer; nearest parts " + ", ".join(f"{n['ref']} {n['distance']} mm" for n in row["nearest"]))
        for ref in sorted(self.report.get("name_skipped", [])):
            self.note("NOTE", ref, f"the name text of {ref} found no free place and is not drawn")
        for mid in sorted(self.report.get("marks_skipped", [])):
            self.note("NOTE", mid, f"pin-1 marking {mid} found no free place and is not drawn")
        self.report["unplaced"] = unplaced
        return self.plan
