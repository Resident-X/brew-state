"""Streamlines of a potential flow along a plan region round obstacles, deterministic and parametric.

The stream function psi is harmonic in the region. On the region's edge it takes the value 0 on the left, 1 on the
right and the linear blend across the inlet and the outlet, so the edge itself is a streamline; a wall named zero_walls,
a block set against the left edge, carries 0 too. Each island is an obstacle on which psi is one constant, chosen so that
the flow circulates round none of them. The lines are the contours of psi at evenly spaced levels, traced with marching
squares on a regular grid, joined into polylines and smoothed.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from shapely.geometry import Polygon as ShPolygon

Point2 = Tuple[float, float]


class Field:
    """psi on a grid over a region with islands cut out of it."""

    def __init__(self, region: ShPolygon, islands: Sequence[ShPolygon], h: float = 0.4, zero_walls: Sequence[ShPolygon] = ()):
        self.h = h
        self.zero_walls = list(zero_walls)
        minx, miny, maxx, maxy = region.bounds
        self.x0, self.y0 = math.floor(minx / h) * h - h, math.floor(miny / h) * h - h
        self.nx = int(math.ceil((maxx - self.x0) / h)) + 2
        self.ny = int(math.ceil((maxy - self.y0) / h)) + 2
        xs = self.x0 + h * np.arange(self.nx)
        ys = self.y0 + h * np.arange(self.ny)
        self.X, self.Y = np.meshgrid(xs, ys)
        inside = shapely.contains_xy(region, self.X, self.Y)
        isl = [shapely.contains_xy(i, self.X, self.Y) & inside for i in islands]
        self.inside, self.islands = inside, isl
        pad = np.pad(inside, 1, constant_values=False)
        all_nb = pad[1:-1, :-2] & pad[1:-1, 2:] & pad[:-2, 1:-1] & pad[2:, 1:-1]
        self.boundary = inside & ~all_nb & ~np.logical_or.reduce(isl) if isl else inside & ~all_nb
        island_any = np.logical_or.reduce(isl) if isl else np.zeros_like(inside)
        self.unknown = inside & ~self.boundary & ~island_any
        self.psi_boundary = self._edge_values(region)
        self.psi = self._solve()

    def _edge_values(self, region: ShPolygon) -> np.ndarray:
        """psi on the edge: 0 at the region's left extent of the row, 1 at its right extent, linear between; 0 on a zero wall."""
        vals = np.zeros_like(self.X)
        for j in range(self.ny):
            row = self.inside[j]
            if not row.any():
                continue
            xs = self.X[j][row]
            lo, hi = xs.min(), xs.max()
            vals[j] = np.clip((self.X[j] - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
        for wall in self.zero_walls:
            near = shapely.dwithin(wall.exterior, shapely.points(self.X, self.Y), 1.5 * self.h) if hasattr(shapely, "dwithin") else None
            vals[near] = 0.0
        return vals

    def _solve(self) -> np.ndarray:
        unk = self.unknown
        index = -np.ones(unk.shape, dtype=int)
        index[unk] = np.arange(int(unk.sum()))
        n = int(unk.sum())
        rows, cols, vals = [], [], []
        rhs_cols = 1 + len(self.islands)
        rhs = np.zeros((n, rhs_cols))
        known = [self.psi_boundary * self.boundary] + [m.astype(float) for m in self.islands]
        for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            jj, ii = np.nonzero(unk)
            nj, ni = jj + dj, ii + di
            nb_unk = unk[nj, ni]
            rows.append(index[jj, ii])
            cols.append(np.where(nb_unk, index[nj, ni], 0))
            vals.append(np.where(nb_unk, 1.0, 0.0))
            for k, kn in enumerate(known):
                is_known = (self.boundary if k == 0 else self.islands[k - 1])[nj, ni]
                rhs[index[jj, ii], k] += np.where(is_known, kn[nj, ni], 0.0)
        rows.append(np.arange(n))
        cols.append(np.arange(n))
        vals.append(np.full(n, -4.0))
        A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsc()
        # the base solution carries the edge, each basis solution carries one island at 1 and the rest at 0
        sol = [spsolve(A, -rhs[:, k]) for k in range(rhs_cols)]
        fields = []
        for k in range(rhs_cols):
            f = np.zeros_like(self.X)
            f[unk] = sol[k]
            if k == 0:
                f += self.psi_boundary * self.boundary
            else:
                f += self.islands[k - 1].astype(float)
            fields.append(f)
        consts = self._circulation_free(fields)
        psi = fields[0].copy()
        for k, c in enumerate(consts):
            psi += c * (fields[k + 1])
        # the islands carry their constants
        for k, c in enumerate(consts):
            psi[self.islands[k]] = c
        self.constants = consts
        psi[~self.inside] = np.nan
        return psi

    def _circulation_free(self, fields: List[np.ndarray]) -> List[float]:
        k = len(self.islands)
        if k == 0:
            return []
        # circulation about island i: the sum over its edge cells of (psi at the fluid neighbour - the island's constant)
        A = np.zeros((k, k))
        b = np.zeros(k)
        fluid = self.unknown
        for i, mask in enumerate(self.islands):
            pad = np.pad(mask, 1, constant_values=False)
            for dj, di in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                shifted = np.roll(np.roll(mask, -dj, axis=0), -di, axis=1)
                pair = mask & fluid_shift(fluid, dj, di)
                jj, ii = np.nonzero(pair)
                nj, ni = jj + dj, ii + di
                b[i] -= fields[0][nj, ni].sum()
                for m in range(k):
                    A[i, m] += fields[m + 1][nj, ni].sum()
                A[i, i] -= len(jj)
        return list(np.linalg.solve(A, b))

    # -- contours --------------------------------------------------------------------------------------------------------
    def contour(self, level: float) -> List[List[Point2]]:
        """The polylines of psi = level, each a list of (x, y); marching squares, segments joined end to end."""
        psi = np.where(np.isnan(self.psi), 2.0, self.psi)
        valid = ~np.isnan(self.psi)
        segs: List[Tuple[Point2, Point2]] = []
        a, b, c, d = psi[:-1, :-1], psi[:-1, 1:], psi[1:, 1:], psi[1:, :-1]
        ok = valid[:-1, :-1] & valid[:-1, 1:] & valid[1:, 1:] & valid[1:, :-1]
        h = self.h
        for j, i in zip(*np.nonzero(ok)):
            v = (a[j, i], b[j, i], c[j, i], d[j, i])
            corners = ((self.X[j, i], self.Y[j, i]), (self.X[j, i + 1], self.Y[j, i + 1]), (self.X[j + 1, i + 1], self.Y[j + 1, i + 1]), (self.X[j + 1, i], self.Y[j + 1, i]))
            pts = []
            for e in range(4):
                p, q = v[e], v[(e + 1) % 4]
                if (p - level) * (q - level) < 0:
                    t = (level - p) / (q - p)
                    x = corners[e][0] + t * (corners[(e + 1) % 4][0] - corners[e][0])
                    y = corners[e][1] + t * (corners[(e + 1) % 4][1] - corners[e][1])
                    pts.append((x, y))
            if len(pts) == 2:
                segs.append((pts[0], pts[1]))
            elif len(pts) == 4:
                segs.append((pts[0], pts[1]))
                segs.append((pts[2], pts[3]))
        return join_segments(segs, 1e-6)


def fluid_shift(fluid: np.ndarray, dj: int, di: int) -> np.ndarray:
    out = np.zeros_like(fluid)
    h, w = fluid.shape
    src = fluid[max(dj, 0): h + min(dj, 0), max(di, 0): w + min(di, 0)]
    out[max(-dj, 0): h - max(dj, 0), max(-di, 0): w - max(di, 0)] = src
    return out


def join_segments(segs: List[Tuple[Point2, Point2]], tol: float) -> List[List[Point2]]:
    """Segments with shared end points joined into polylines."""
    key = lambda p: (round(p[0] / 1e-5), round(p[1] / 1e-5))  # noqa: E731
    ends: Dict[Tuple[int, int], List[int]] = {}
    for n, (p, q) in enumerate(segs):
        ends.setdefault(key(p), []).append(n)
        ends.setdefault(key(q), []).append(n)
    used = [False] * len(segs)
    lines: List[List[Point2]] = []
    for n in range(len(segs)):
        if used[n]:
            continue
        used[n] = True
        line = [segs[n][0], segs[n][1]]
        for direction in (0, 1):
            while True:
                tip = line[-1] if direction == 0 else line[0]
                nxt = [m for m in ends.get(key(tip), []) if not used[m]]
                if not nxt:
                    break
                m = nxt[0]
                used[m] = True
                p, q = segs[m]
                other = q if key(p) == key(tip) else p
                if direction == 0:
                    line.append(other)
                else:
                    line.insert(0, other)
        lines.append(line)
    return lines


def smooth(line: Sequence[Point2], passes: int = 3) -> List[Point2]:
    """Chaikin corner cutting that keeps the end points."""
    pts = [tuple(p) for p in line]
    for _ in range(passes):
        out = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        out.append(pts[-1])
        pts = out
    return pts


def resample(line: Sequence[Point2], step: float) -> List[Point2]:
    p = np.asarray(line, dtype=float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    count = max(int(round(s[-1] / step)), 1)
    grid = np.linspace(0.0, s[-1], count + 1)
    return [(float(np.interp(g, s, p[:, 0])), float(np.interp(g, s, p[:, 1]))) for g in grid]
