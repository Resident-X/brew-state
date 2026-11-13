#!/usr/bin/env python3
"""Generate the simplified 3D bodies of the main board's custom footprints as coloured VRML files.

usage: render_fallback_models.py [--out OUTPUT_DIR]      (default: the current folder)

The stand-in bodies fetch_3d_models.py gives a footprint no vendor model fits, for pictures only: the
output belongs in the git-ignored 3D cache, never in the repository.

Pure Python, no CAD package needed. Each model is a set of small convex solids (chamfered and rounded
bodies, rods, flat blades, bent leads) with a muted material, written as VRML 2.0 (`.wrl`), which
`kicad-cli` draws with the material's colour, a low specular and a low shininess so nothing glares. The
origin and axes are the footprint's own (z up from the board surface, pads at their footprint
coordinates). The y written to the file is the footprint's y negated, because KiCad's 3D viewer draws a
model's +Y toward the board's -Y; the part functions below use footprint y. VRML length units in KiCad are
0.1 inch, so every coordinate is written divided by 2.54. The overall dimensions come from the makers'
drawings; the chamfers, radii, label panels, caps and leads are the visible detail an observer expects and
are not maker dimensions. The reed capsule sits on the back of the board (its footprint is on the front
layer): its body is modelled under the board and its leads rise through the holes to solder cones on the front. Running it again rewrites the same bytes.
"""
import math
import os

BOARD_THICKNESS = 1.6

# material name -> (diffuse rgb, specular rgb, shininess, transparency); muted, slightly warm, low gloss
MATERIALS = {
    "body": ((0.15, 0.145, 0.14), (0.08, 0.08, 0.08), 0.15, 0.0),
    "label": ((0.27, 0.265, 0.25), (0.05, 0.05, 0.05), 0.1, 0.0),
    "dot": ((0.30, 0.29, 0.28), (0.05, 0.05, 0.05), 0.1, 0.0),
    "tin": ((0.58, 0.57, 0.55), (0.25, 0.25, 0.24), 0.3, 0.0),
    "brass": ((0.60, 0.49, 0.28), (0.22, 0.20, 0.14), 0.25, 0.0),
    "tab": ((0.62, 0.57, 0.45), (0.22, 0.21, 0.18), 0.3, 0.0),
    "coating": ((0.12, 0.12, 0.12), (0.05, 0.05, 0.05), 0.1, 0.0),
    "glass": ((0.60, 0.64, 0.63), (0.20, 0.20, 0.20), 0.3, 0.35),
    "element": ((0.35, 0.33, 0.30), (0.1, 0.1, 0.1), 0.2, 0.0),
    "steel": ((0.50, 0.50, 0.49), (0.18, 0.18, 0.18), 0.25, 0.0),
    "base": ((0.17, 0.165, 0.155), (0.07, 0.07, 0.07), 0.12, 0.0),
    "hole": ((0.10, 0.10, 0.10), (0.0, 0.0, 0.0), 0.0, 0.0),
}


# ---------------------------------------------------------------- solids
# A solid is (points, faces, material): points are (x, y, z) in footprint millimetres, faces are lists of
# point indices; every solid is convex, which is how a face's outward side is told.
def loft(rings, material, caps=True):
    """Solid through equal-sized rings of points (each ring one cross-section), quads between neighbours."""
    n = len(rings[0])
    points = [p for ring in rings for p in ring]
    faces = []
    for r in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append([r * n + i, r * n + j, (r + 1) * n + j, (r + 1) * n + i])
    if caps:
        faces.append(list(range(n)))
        faces.append([(len(rings) - 1) * n + i for i in range(n)])
    return (points, faces, material)


def rrect(x0, x1, y0, y1, radius, segments=3):
    """Corner points of a rectangle with rounded corners, counter-clockwise."""
    radius = max(min(radius, (x1 - x0) / 2, (y1 - y0) / 2), 0.0)
    if radius <= 0.0:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    pts = []
    for cx, cy, a0 in ((x1 - radius, y0 + radius, -90), (x1 - radius, y1 - radius, 0),
                       (x0 + radius, y1 - radius, 90), (x0 + radius, y0 + radius, 180)):
        for k in range(segments + 1):
            a = math.radians(a0 + 90.0 * k / segments)
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return pts


def body(x0, x1, y0, y1, z0, z1, material, chamfer=0.0, radius=0.0):
    """A box with its top edges chamfered and its plan corners rounded."""
    plan = rrect(x0, x1, y0, y1, radius)
    c = min(chamfer, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01, (z1 - z0) / 2 - 0.01) if chamfer else 0.0
    if c <= 0:
        return loft([[(x, y, z0) for x, y in plan], [(x, y, z1) for x, y in plan]], material)
    inner = rrect(x0 + c, x1 - c, y0 + c, y1 - c, max(radius - c, 0.05) if radius > 0 else 0.0)
    return loft([[(x, y, z0) for x, y in plan], [(x, y, z1 - c) for x, y in plan],
                 [(x, y, z1) for x, y in inner]], material)


def _at(axis, a, c1, c2, u, v):
    """Point at `a` along `axis`, offset (u, v) across it from the line through (c1, c2)."""
    if axis == "x":
        return (a, c1 + u, c2 + v)
    if axis == "y":
        return (c1 + u, a, c2 + v)
    return (c1 + u, c2 + v, a)


def rod(axis, a0, a1, c1, c2, radius, material, sides=16, chamfer=0.0):
    """Round rod along x, y or z between a0 and a1 about the line through (c1, c2), with chamfered ends."""
    circle = [(math.cos(2 * math.pi * k / sides), math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    stations = [(a0, radius - chamfer), (a0 + chamfer, radius), (a1 - chamfer, radius), (a1, radius - chamfer)] \
        if chamfer > 0 else [(a0, radius), (a1, radius)]
    return loft([[_at(axis, a, c1, c2, r * u, r * v) for u, v in circle] for a, r in stations], material)


def flat(axis, a0, a1, c1, c2, width, thick, material, narrow=0.0, ends=0.0, tip=1.0):
    """Flat blade along `axis`: `width` across the first cross axis, `thick` across the second. The last `tip`
    of its length narrows by `narrow` on each side of the width and `ends` on each side of the thickness."""
    stations = [(a0, width, thick)]
    if narrow or ends:
        stations.append((a1 - tip, width, thick))
    stations.append((a1, width - 2 * narrow, thick - 2 * ends))
    return loft([[_at(axis, a, c1, c2, u * w / 2, v * t / 2) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                 for a, w, t in stations], material)


def ball(centre, radius, material, sides=10):
    cx, cy, cz = centre
    rings = []
    for lat in (-60, -20, 20, 60):
        z = cz + radius * math.sin(math.radians(lat))
        r = radius * math.cos(math.radians(lat))
        rings.append([(cx + r * math.cos(2 * math.pi * k / sides), cy + r * math.sin(2 * math.pi * k / sides), z)
                      for k in range(sides)])
    return loft(rings, material)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(sum(c * c for c in a))
    return tuple(c / n for c in a)


def tube(path, radius, material, sides=12):
    """Round wire through the 3D points of `path`, a rod per leg and a ball at each bend."""
    solids = []
    for p, q in zip(path, path[1:]):
        d = _unit([q[i] - p[i] for i in range(3)])
        ref = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
        u = _unit(_cross(d, ref))
        v = _cross(d, u)
        solids.append(loft([[tuple(end[i] + radius * (math.cos(2 * math.pi * k / sides) * u[i]
                                                      + math.sin(2 * math.pi * k / sides) * v[i]) for i in range(3))
                             for k in range(sides)] for end in (p, q)], material))
    for p in path[1:-1]:
        solids.append(ball(p, radius * 1.02, material))
    return solids


def gull(along, lat, sign, edge, out, width, thick, ztop, material="tin"):
    """Gull-wing lead leaving a body edge at `edge` (distance from the centre, along x or y) toward `sign`,
    flat on the board out to `out`, at lateral position `lat`."""
    drop = ztop * 0.45
    path = [(-0.2, ztop - thick / 2), (0.25, ztop - thick / 2), (0.25 + drop, thick / 2), (abs(out) - abs(edge), thick / 2)]
    solids = []
    for (u0, z0), (u1, z1) in zip(path, path[1:]):
        rings = []
        for u, z in ((u0, z0), (u1, z1)):
            s = sign * (abs(edge) + u)
            section = ((-width / 2, -thick / 2), (width / 2, -thick / 2), (width / 2, thick / 2), (-width / 2, thick / 2))
            if along == "x":
                rings.append([(s, lat + d, z + dz) for d, dz in section])
            else:
                rings.append([(lat + d, s, z + dz) for d, dz in section])
        solids.append(loft(rings, material))
    return solids


def pin1_dot(x, y, z, radius=0.35):
    return rod("z", z, z + 0.06, x, y, radius, "dot", sides=12)


# ---------------------------------------------------------------- VRML writer
def _outward(points, faces):
    """Faces of a convex solid wound so each normal points away from the solid's centre."""
    centre = [sum(p[i] for p in points) / len(points) for i in range(3)]
    out = []
    for face in faces:
        n = [0.0, 0.0, 0.0]
        for k in range(len(face)):
            c = _cross(points[face[k]], points[face[(k + 1) % len(face)]])
            n = [n[m] + c[m] for m in range(3)]
        mid = [sum(points[i][m] for i in face) / len(face) for m in range(3)]
        if sum(n[m] * (mid[m] - centre[m]) for m in range(3)) < 0:
            face = face[::-1]
        out.append(face)
    return out


def f(v):
    s = ("%.5f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def write_wrl(path, name, solids):
    """Write `solids` as one VRML 2.0 shape per material, y negated and lengths in 0.1 inch."""
    by_material = {}
    for points, faces, material in solids:
        flipped = [(x, -y, z) for x, y, z in points]
        by_material.setdefault(material, []).append((flipped, _outward(flipped, faces)))
    out = ["#VRML V2.0 utf8", "# %s: simplified body for pictures, generated by render_fallback_models.py" % name]
    for material in sorted(by_material):
        diffuse, specular, shininess, transparency = MATERIALS[material]
        coords, index = [], []
        for pts, faces in by_material[material]:
            base = len(coords)
            coords.extend(pts)
            for face in faces:
                index.append(",".join(str(base + i) for i in face) + ",-1")
        out.append("Shape {\n appearance Appearance { material Material {\n"
                   "  diffuseColor %s\n  specularColor %s\n  ambientIntensity 0.25\n  shininess %s\n  transparency %s\n } }\n"
                   " geometry IndexedFaceSet {\n  creaseAngle 0.5\n  solid FALSE\n  coord Coordinate { point [\n%s\n  ] }\n"
                   "  coordIndex [\n%s\n  ]\n }\n}"
                   % (" ".join(f(c) for c in diffuse), " ".join(f(c) for c in specular), f(shininess), f(transparency),
                      ",\n".join("   %s %s %s" % (f(x / 2.54), f(y / 2.54), f(z / 2.54)) for x, y, z in coords),
                      ",\n".join("   " + line for line in index)))
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- the parts
def _relay_body(x0, x1, y0, y1, z0, z1, label_margin):
    """Relay can: chamfered, rounded body with a raised lighter label panel on the top."""
    return [body(x0, x1, y0, y1, z0, z1, "body", chamfer=0.7, radius=0.8),
            body(x0 + label_margin, x1 - label_margin, y0 + label_margin, y1 - label_margin, z1 - 0.05, z1 + 0.12,
                 "label", chamfer=0.05)]


def relay_hf32fa_g():
    # body 16 x 10 x 12.3 above 0.4 standoffs; coil pins round, contact pins flat
    s = _relay_body(-1.08, 16.52, -1.25, 8.85, 0.4, 12.7, 1.6)
    for x, y in ((-0.7, -0.9), (-0.7, 8.5), (16.1, -0.9), (16.1, 8.5)):
        s.append(body(x - 0.5, x + 0.5, y - 0.5, y + 0.5, 0.0, 0.45, "base"))
    for x, y in ((0, 0), (0, 7.6)):
        s.append(rod("z", -3.2, 0.45, x, y, 0.3, "tin", sides=10, chamfer=0.12))
    for x, y in ((15.24, 0.625), (15.24, 6.975)):
        s.append(flat("z", -3.2, 0.45, x, y, 0.3, 0.8, "tin", ends=0.1, tip=0.6))
    return s


def relay_hf115f_q():
    # body 29 long from 2.5 before the coil pins; quick-connect blade 6.3 long beyond the contact end
    cy = 3.78
    s = _relay_body(-2.5, 26.5, cy - 6.35, cy + 6.35, 0.3, 15.7, 2.2)
    for x, y in ((-2.0, cy - 5.85), (-2.0, cy + 5.85), (26.0, cy - 5.85), (26.0, cy + 5.85)):
        s.append(body(x - 0.5, x + 0.5, y - 0.5, y + 0.5, 0.0, 0.35, "base"))
    for y in (0, 7.56):
        s.append(rod("z", -3.3, 0.35, 0.0, y, 0.3, "tin", sides=10, chamfer=0.12))
    s.append(flat("x", 26.4, 32.8, cy, 6.75, 0.8, 12.9, "brass", ends=1.2, tip=1.4))
    for x in (32.5, 37.5):
        for y in (0, 7.56):
            s.append(flat("z", -3.3, 0.35, x, y, 0.8, 0.8, "tin", ends=0.2, tip=0.6))
    return s


def amc131m02():
    # SOIC-20W: body 7.5 x 12.8 x 2.65, ten gull-wing leads each side at 1.27 pitch
    s = [body(-3.75, 3.75, -6.4, 6.4, 0.1, 2.65, "body", chamfer=0.3), pin1_dot(-2.5, -5.2, 2.65)]
    for k in range(10):
        y = -5.715 + 1.27 * k
        for sx in (-1, 1):
            s.extend(gull("x", y, sx, 3.75, 5.15, 0.4, 0.25, 1.4))
    return s


def _dip_smd(half_x, half_y, height, z0, xs, out, dot):
    s = [body(-half_x, half_x, -half_y, half_y, z0, height, "body", chamfer=0.3), pin1_dot(dot[0], dot[1], height, 0.3)]
    for x in xs:
        for sy in (-1, 1):
            s.extend(gull("y", x, sy, half_y, out, 0.5, 0.25, 1.5))
    return s


def ltv_814s():
    return _dip_smd(2.3, 3.25, 3.85, 0.35, (-1.27, 1.27), 5.15, (-1.27, -2.2))


def moc3052svm():
    return _dip_smd(4.255, 3.175, 3.9, 0.4, (-2.54, 0.0, 2.54), 5.27, (-3.0, -2.2))


def ts1187a():
    # tactile switch: pressed-steel cover over a dark housing, round actuator, four bent feet
    s = [body(-2.55, 2.55, -2.55, 2.55, 0.1, 1.2, "base", chamfer=0.15),
         body(-2.45, 2.45, -2.45, 2.45, 1.2, 1.35, "steel", chamfer=0.1),
         rod("z", 1.35, 1.8, 0.0, 0.0, 1.3, "body", sides=20, chamfer=0.2)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.extend(gull("x", sy * 1.875, sx, 2.55, 3.4, 0.6, 0.2, 0.9))
    return s


def tab_bzxc():
    # flat blade 6.3 wide, 0.8 thick, with a chamfered tip, a punched hole, a barb each side and a base shoulder
    s = [flat("z", -1.6, 9.9, 0.0, 0.0, 6.3, 0.8, "tab", narrow=1.1, tip=1.2),
         body(-3.15, 3.15, -0.5, 0.5, 0.0, 1.0, "tab", chamfer=0.15),
         rod("y", -0.43, 0.43, 0.0, 7.4, 0.9, "hole", sides=14)]
    for sx in (-1, 1):
        s.append(flat("z", 4.4, 5.6, sx * 3.15, 0.0, 0.6, 0.8, "tab"))
    return s


def r_wsk2512():
    # metal-strip shunt: dark coated centre, tin end caps
    s = [body(-1.8, 1.8, -1.59, 1.59, 0.0, 0.85, "coating", chamfer=0.12)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * 1.55, sx * 3.175))
        s.append(body(xa, xb, -1.59, 1.59, 0.0, 0.7, "tin", chamfer=0.12))
    return s


def reed_pads():
    # the capsule sits under the board and its leads go up through the plated holes to the front, where each
    # lead end stands proud of a small solder cone
    z = -BOARD_THICKNESS - 2.2
    s = [rod("y", 3.0, 17.0, 0.0, z, 1.15, "glass", sides=18, chamfer=0.45),
         flat("y", 3.3, 10.4, 0.0, z, 0.7, 0.2, "element"),
         flat("y", 9.6, 16.7, 0.0, z, 0.7, 0.2, "element")]
    for y, sign in ((0, 1), (20, -1)):
        s.extend(tube([(0, y, 1.3), (0, y, z), (0, y + sign * 3.4, z)], 0.3, "tin"))
        circle = [(math.cos(2 * math.pi * k / 14), math.sin(2 * math.pi * k / 14)) for k in range(14)]
        s.append(loft([[(u * r, y + v * r, h) for u, v in circle] for r, h in ((1.0, 0.0), (0.75, 0.2), (0.35, 0.8))], "tin"))
    return s


def fuseholder_5x20():
    # black base, two open-topped brass clips cradling a 5 x 20 glass cartridge with metal end caps
    s = [body(-12.0, 12.0, -4.75, 4.75, 0.0, 1.5, "base", chamfer=0.4, radius=0.8)]
    cz, cy = 6.2, 0.0
    for sx in (-1, 1):
        xa, xb = sorted((sx * 8.2, sx * 11.0))
        n = 10
        for k in range(n):  # the C of the clip, open at the top (angles in the y-z plane from +y toward +z)
            a0 = math.radians(160 + 240.0 * k / n)
            a1 = math.radians(160 + 240.0 * (k + 1) / n)
            s.append(loft([[(x, cy + r * math.cos(a), cz + r * math.sin(a)) for a, r in
                            ((a0, 2.65), (a0, 3.2), (a1, 3.2), (a1, 2.65))] for x in (xa, xb)], "brass"))
        wa, wb = sorted((sx * 10.6, sx * 11.2))
        s.append(body(wa, wb, -3.2, 3.2, 1.5, 7.6, "brass", chamfer=0.2))
        xa2, xb2 = sorted((sx * 8.2, sx * 11.2))
        s.append(body(xa2, xb2, -1.2, 1.2, 1.5, 3.5, "brass"))
        s.append(flat("z", -1.6, 1.6, sx * 10.0, 0.0, 1.2, 0.6, "tin", ends=0.1, tip=0.6))
    s.append(rod("x", -7.0, 7.0, cy, cz, 2.5, "glass", sides=20))
    s.append(rod("x", -7.0, 7.0, cy, cz, 0.12, "element", sides=6))
    for sx in (-1, 1):
        xa, xb = sorted((sx * 7.0, sx * 10.0))
        s.append(rod("x", xa, xb, cy, cz, 2.55, "tin", sides=20, chamfer=0.25))
    return s


def jp101_wire_link():
    # 1.5 mm2 wire bent into a slightly arched link, 10 mm between its legs
    path = [(0, 0, -1.6), (0, 0, 2.4), (1.5, 0, 3.1), (5, 0, 3.4), (8.5, 0, 3.1), (10, 0, 2.4), (10, 0, -1.6)]
    return tube(path, 0.7, "tin", sides=14)


PARTS = {
    "RELAY_HF32FA-G_1H_TYPE1_THT": relay_hf32fa_g,
    "Relay_HF115F-Q_1H_Vertical": relay_hf115f_q,
    "AMC131M02_SOIC-20W_DFM0020A": amc131m02,
    "FUSEHOLDER_5x20_XC_BLX-A": fuseholder_5x20,
    "JP101_WireLink_P10mm": jp101_wire_link,
    "LTV-814S_SMD-4": ltv_814s,
    "MOC3052SVM_SMD-6": moc3052svm,
    "TS1187A_5.1x5.1mm_SMD": ts1187a,
    "Tab_BZXC_BTC-3-PCB634908T": tab_bzxc,
    "R_WSK2512_4T": r_wsk2512,
    "REED_PADS_P20.00mm": reed_pads,
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".", help="folder to write the VRML files into")
    out = parser.parse_args().out
    os.makedirs(out, exist_ok=True)
    for name, build in PARTS.items():
        write_wrl(os.path.join(out, name + ".wrl"), name, build())
        print(name + ".wrl")


if __name__ == "__main__":
    main()
