#!/usr/bin/env python3
"""Report which parts of a board's 3D export stand inside one another or closer than a gap.

usage: board_collisions_3d.py BOARD.glb [--flags FLAGS.json] [--gap 0.3] [--thickness 1.6]

Reads the GLB `kicad-cli pcb export glb` writes (one top-level node per footprint, named by its
reference) and, for every part, takes its geometry on each side of the board (above the front surface,
below the back one; what lies inside the board's thickness, the part's own pins and holes, is not a body).
Each part's side is reduced to a convex plan outline (hull of its vertices) and a height range. Two parts on the
same side collide when their outlines come within `--gap` mm of each other (or overlap) and their height
ranges do too. The hull of an L-shaped or comb-shaped part (a pin header, a clip pair) is larger than the part,
so a pair listed is where to look, not a proof. `--flags` names a JSON object of reference -> kind for the
hand-fitted parts (relays, fuse holders, tabs, the reed, the module), whose pairs are marked.

Needs numpy and trimesh; render_board_3d.py runs it with the virtual environment it keeps in the 3D cache.
Prints one line per pair, the worst first, and a closing count; the exit status is 0 whatever it finds.
"""

from __future__ import annotations

import argparse
import json
import math
import sys


MIN_BODY = 0.3  # a side of a part thinner than this (mm) is a pin end, not a body


def hull(points):
    """Convex hull of 2D points (monotone chain), counter-clockwise, without repeated points."""
    pts = sorted(set((round(x, 4), round(y, 4)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def plan_gap(a, b):
    """Signed separation of two convex polygons by the separating-axis test: positive is the clear distance
    along the best axis (a lower bound of the true distance), negative is the least translation that frees them."""
    best = -math.inf
    for poly in (a, b):
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            nx, ny = y2 - y1, x1 - x2
            length = math.hypot(nx, ny)
            if length == 0:
                continue
            nx, ny = nx / length, ny / length
            pa = [x * nx + y * ny for x, y in a]
            pb = [x * nx + y * ny for x, y in b]
            best = max(best, min(pb) - max(pa), min(pa) - max(pb))
    return best


def part_sides(path, thickness):
    """reference -> side ('top' or 'bottom') -> list of (x, y, height) vertices in mm, height measured from the
    board's front surface for the top and from its back surface (as a positive depth) for the bottom."""
    import trimesh

    scene = trimesh.load(path, force="scene")
    parents = scene.graph.transforms.parents
    result = {}
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        chain = [node]
        while parents.get(chain[-1]) is not None:
            chain.append(parents[chain[-1]])
        # the chain ends at the world frame and the file's scene node; the footprint's node is just below them
        top = chain[-3] if len(chain) >= 3 else node
        mesh = scene.geometry[geometry]
        verts = trimesh.transformations.transform_points(mesh.vertices, transform) * 1000.0
        sides = result.setdefault(top, {"top": [], "bottom": []})
        for x, h, y in verts:  # glTF is y up; the board's y runs along glTF z
            if h > thickness + 0.05:
                sides["top"].append((x, y, h - thickness))
            elif h < -0.05:
                sides["bottom"].append((x, y, -h))
    return result


def find_collisions(parts, gap):
    """Pairs of (reference, reference, side, plan gap, height gap) that are closer than `gap` in both."""
    boxes = []
    for ref, sides in parts.items():
        for side, verts in sides.items():
            if len(verts) < 3 or ref.startswith("=>"):  # the board's own graphics are not a part
                continue
            poly = hull([(x, y) for x, y, _ in verts])
            if len(poly) < 3:
                continue
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            hs = [h for _, _, h in verts]
            if max(hs) - min(hs) < MIN_BODY:  # the tip of a pin through the board, not a body
                continue
            boxes.append((ref, side, poly, (min(xs), min(ys), max(xs), max(ys)), (min(hs), max(hs))))
    found = []
    for i in range(len(boxes)):
        ra, sa, pa, ba, ha = boxes[i]
        for j in range(i + 1, len(boxes)):
            rb, sb, pb, bb, hb = boxes[j]
            if sa != sb or ra == rb:
                continue
            if ba[0] > bb[2] + gap or bb[0] > ba[2] + gap or ba[1] > bb[3] + gap or bb[1] > ba[3] + gap:
                continue
            height_gap = max(ha[0], hb[0]) - min(ha[1], hb[1])
            if height_gap >= gap:
                continue
            separation = plan_gap(pa, pb)
            if separation >= gap:
                continue
            found.append((ra, rb, sa, separation, height_gap, ha, hb))
    found.sort(key=lambda f: (f[3], f[4]))
    return found


def report(found, flags):
    lines = []
    for ra, rb, side, separation, height_gap, ha, hb in found:
        state = f"overlap {-separation:.2f} mm" if separation < 0 else f"{separation:.2f} mm apart"
        vertical = f"overlap {-height_gap:.2f} mm" if height_gap < 0 else f"{height_gap:.2f} mm apart"
        marks = [f"{r} {flags[r]}" for r in (ra, rb) if r in flags]
        lines.append(f"COLLISION {ra} / {rb} on {side}: plan {state}, height {vertical}; "
                     f"{ra} {ha[0]:.1f}..{ha[1]:.1f} mm, {rb} {hb[0]:.1f}..{hb[1]:.1f} mm"
                     + (f"; HAND-FITTED {', '.join(marks)}" if marks else ""))
    inside = sum(1 for f in found if f[3] < 0)
    hand = sum(1 for f in found if f[0] in flags or f[1] in flags)
    lines.append(f"{len(found)} pairs closer than the gap, {inside} with outlines overlapping in plan, "
                 f"{hand} involving a hand-fitted part")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("glb")
    parser.add_argument("--flags", default="")
    parser.add_argument("--gap", type=float, default=0.3)
    parser.add_argument("--thickness", type=float, default=1.6)
    args = parser.parse_args(argv)
    flags = json.load(open(args.flags)) if args.flags else {}
    for line in report(find_collisions(part_sides(args.glb, args.thickness), args.gap), flags):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
