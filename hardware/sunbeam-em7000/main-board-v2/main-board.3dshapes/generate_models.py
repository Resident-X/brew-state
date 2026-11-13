#!/usr/bin/env python3
"""Generate the simplified 3D bodies of the main board's custom footprints as STEP files.

usage: generate_models.py [OUTPUT_DIR]      (default: the folder holding this script)

Pure Python, no CAD package needed. Each model is a handful of convex prisms (boxes,
octagonal rods) with a colour, written as an AP214 STEP file in millimetres, origin and
axes the footprint's own (z up from the board surface, pads at their footprint
coordinates). The y written to the file is the footprint's y negated, because KiCad's 3D
viewer draws a model's +Y toward the board's -Y; the part functions below use footprint y. They show where a part's body, height and terminals stand against the
pads; they are not maker drawings. The dimension source of every part is in README.md
next to this script. Running it again rewrites the same bytes.
"""
import math
import os
import sys

# colours (r, g, b)
BLACK = (0.10, 0.10, 0.11)
NAVY = (0.07, 0.11, 0.30)
TIN = (0.78, 0.78, 0.80)
BRASS = (0.80, 0.62, 0.25)
COPPER = (0.72, 0.45, 0.20)
GLASS = (0.72, 0.85, 0.92)
STEEL = (0.62, 0.64, 0.66)
CERAMIC = (0.55, 0.50, 0.45)


# ---------------------------------------------------------------- solids
def box(x0, x1, y0, y1, z0, z1, colour):
    ring = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
    top = [(x, y, z1) for x, y, _ in ring]
    return (ring, top, colour)


def rod(axis, a0, a1, c1, c2, radius, colour, sides=12):
    """Prism of a regular polygon (circumscribed radius) along x, y or z between a0 and a1."""
    pts = []
    for k in range(sides):
        t = 2 * math.pi * (k + 0.5) / sides
        pts.append((radius * math.cos(t), radius * math.sin(t)))
    lo, hi = [], []
    for u, v in pts:
        if axis == "z":
            lo.append((c1 + u, c2 + v, a0)); hi.append((c1 + u, c2 + v, a1))
        elif axis == "x":
            lo.append((a0, c1 + u, c2 + v)); hi.append((a1, c1 + u, c2 + v))
        else:
            lo.append((c1 + u, a0, c2 + v)); hi.append((c1 + u, a1, c2 + v))
    return (lo, hi, colour)


# ---------------------------------------------------------------- STEP writer
class Step:
    def __init__(self):
        self.lines = []

    def add(self, text):
        self.lines.append(text)
        return len(self.lines)

    def ref(self, n):
        return "#%d" % n


def f(v):
    s = "%.6f" % v
    s = s.rstrip("0")
    return s + "0" if s.endswith(".") else s


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def unit(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def faces_of(lo, hi):
    n = len(lo)
    pts = lo + hi
    centre = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
    raw = [list(range(n)), [n + i for i in range(n)]]
    for i in range(n):
        j = (i + 1) % n
        raw.append([i, j, n + j, n + i])
    out = []
    for idx in raw:
        nrm = [0.0, 0.0, 0.0]
        for k in range(len(idx)):
            c = cross(pts[idx[k]], pts[idx[(k + 1) % len(idx)]])
            nrm = [nrm[m] + c[m] for m in range(3)]
        mid = tuple(sum(pts[i][m] for i in idx) / len(idx) for m in range(3))
        if dot(nrm, sub(mid, centre)) < 0:
            idx = idx[::-1]
            nrm = [-v for v in nrm]
        out.append((idx, unit(tuple(nrm))))
    return pts, out


def write_step(path, name, solids):
    st = Step()
    A = st.add
    app = A("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    A("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#%d)" % app)
    pdc = A("PRODUCT_DEFINITION_CONTEXT('part definition',#%d,'design')" % app)
    pc = A("PRODUCT_CONTEXT('',#%d,'mechanical')" % app)
    prod = A("PRODUCT('%s','%s','',(#%d))" % (name, name, pc))
    pdf = A("PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('','',#%d,.NOT_KNOWN.)" % prod)
    pd = A("PRODUCT_DEFINITION('design','',#%d,#%d)" % (pdf, pdc))
    pds = A("PRODUCT_DEFINITION_SHAPE('','',#%d)" % pd)
    lu = A("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    au = A("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    su = A("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = A("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05),#%d,'distance_accuracy_value','confusion accuracy')" % lu)
    ctx = A("( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#%d)) "
            "GLOBAL_UNIT_ASSIGNED_CONTEXT((#%d,#%d,#%d)) REPRESENTATION_CONTEXT('ctx','3D') )" % (unc, lu, au, su))
    o = A("CARTESIAN_POINT('',(0.,0.,0.))")
    dz = A("DIRECTION('',(0.,0.,1.))")
    dx = A("DIRECTION('',(1.,0.,0.))")
    ax = A("AXIS2_PLACEMENT_3D('',#%d,#%d,#%d)" % (o, dz, dx))
    breps, styled = [], []
    dirs = {}

    def direction(v):
        key = tuple(round(c, 9) for c in v)
        if key not in dirs:
            dirs[key] = A("DIRECTION('',(%s,%s,%s))" % tuple(f(c) for c in v))
        return dirs[key]

    for lo, hi, colour in solids:
        # KiCad's 3D viewer draws a model's +Y toward the board's -Y (footprint y runs down the page)
        lo = [(x, -y, z) for x, y, z in lo]
        hi = [(x, -y, z) for x, y, z in hi]
        pts, faces = faces_of(lo, hi)
        pt_ids = [A("CARTESIAN_POINT('',(%s,%s,%s))" % tuple(f(c) for c in p)) for p in pts]
        vx = [A("VERTEX_POINT('',#%d)" % i) for i in pt_ids]
        edges = {}

        def edge(a, b):
            key = (min(a, b), max(a, b))
            if key not in edges:
                p, q = key
                d = sub(pts[q], pts[p])
                length = math.sqrt(dot(d, d))
                vec = A("VECTOR('',#%d,%s)" % (direction(unit(d)), f(length)))
                line = A("LINE('',#%d,#%d)" % (pt_ids[p], vec))
                edges[key] = A("EDGE_CURVE('',#%d,#%d,#%d,.T.)" % (vx[p], vx[q], line))
            return edges[key], (a, b) == key

        face_ids = []
        for idx, nrm in faces:
            oes = []
            for k in range(len(idx)):
                e, fwd = edge(idx[k], idx[(k + 1) % len(idx)])
                oes.append(A("ORIENTED_EDGE('',*,*,#%d,%s)" % (e, ".T." if fwd else ".F.")))
            loop = A("EDGE_LOOP('',(%s))" % ",".join("#%d" % i for i in oes))
            bound = A("FACE_OUTER_BOUND('',#%d,.T.)" % loop)
            first = sub(pts[idx[1]], pts[idx[0]])
            ref = unit(first)
            axis = A("AXIS2_PLACEMENT_3D('',#%d,#%d,#%d)" % (pt_ids[idx[0]], direction(nrm), direction(ref)))
            plane = A("PLANE('',#%d)" % axis)
            face_ids.append(A("ADVANCED_FACE('',(#%d),#%d,.T.)" % (bound, plane)))
        shell = A("CLOSED_SHELL('',(%s))" % ",".join("#%d" % i for i in face_ids))
        solid = A("MANIFOLD_SOLID_BREP('',#%d)" % shell)
        breps.append(solid)
        rgb = A("COLOUR_RGB('',%s,%s,%s)" % tuple(f(c) for c in colour))
        fac = A("FILL_AREA_STYLE_COLOUR('',#%d)" % rgb)
        fas = A("FILL_AREA_STYLE('',(#%d))" % fac)
        sfa = A("SURFACE_STYLE_FILL_AREA(#%d)" % fas)
        sss = A("SURFACE_SIDE_STYLE('',(#%d))" % sfa)
        ssu = A("SURFACE_STYLE_USAGE(.BOTH.,#%d)" % sss)
        psa = A("PRESENTATION_STYLE_ASSIGNMENT((#%d))" % ssu)
        styled.append(A("STYLED_ITEM('',(#%d),#%d)" % (psa, solid)))
    rep = A("ADVANCED_BREP_SHAPE_REPRESENTATION('',(#%d,%s),#%d)" % (ax, ",".join("#%d" % i for i in breps), ctx))
    A("SHAPE_DEFINITION_REPRESENTATION(#%d,#%d)" % (pds, rep))
    A("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(%s),#%d)" % (",".join("#%d" % i for i in styled), ctx))
    body = "\n".join("#%d = %s;" % (i + 1, t) for i, t in enumerate(st.lines))
    text = ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('%s simplified body'),'2;1');\n"
            "FILE_NAME('%s.step','2026-11-13T00:00:00',(''),(''),'generate_models.py','','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n%s\nENDSEC;\nEND-ISO-10303-21;\n"
            % (name, name, body))
    with open(path, "w", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- the parts
def relay_hf32fa_g():
    s = [box(-1.08, 16.52, -1.25, 8.85, 0.4, 12.7, NAVY)]
    for x, y in ((0, 0), (0, 7.6)):
        s.append(box(x - 0.25, x + 0.25, y - 0.25, y + 0.25, -3.2, 0.4, TIN))
    for x, y in ((15.24, 0.625), (15.24, 6.975)):
        s.append(box(x - 0.15, x + 0.15, y - 0.4, y + 0.4, -3.2, 0.4, TIN))
    return s


def relay_hf115f_q():
    # body 29 long from 2.5 before the coil pins; quick-connect blade 6.3 long beyond the contact end
    cy = 3.78
    s = [box(-2.5, 26.5, cy - 6.35, cy + 6.35, 0.3, 15.7, BLACK)]
    for y in (0, 7.56):
        s.append(box(-0.4, 0.4, y - 0.25, y + 0.25, -3.3, 0.3, TIN))
    s.append(box(26.5, 32.8, cy - 0.4, cy + 0.4, 0.3, 13.2, BRASS))
    for x in (32.5, 37.5):
        for y in (0, 7.56):
            s.append(box(x - 0.4, x + 0.4, y - 0.4, y + 0.4, -3.3, 0.3, TIN))
    return s


def amc131m02():
    s = [box(-3.75, 3.75, -6.4, 6.4, 0.1, 2.65, BLACK)]
    for k in range(10):
        y = -5.715 + 1.27 * k
        for sx in (-1, 1):
            xa, xb = sorted((sx * 3.75, sx * 5.15))
            s.append(box(xa, xb, y - 0.2, y + 0.2, 0.0, 0.25, TIN))
            xa, xb = sorted((sx * 3.75, sx * 3.95))
            s.append(box(xa, xb, y - 0.2, y + 0.2, 0.0, 1.5, TIN))
    return s


def fuseholder_5x20():
    s = [box(-12.0, 12.0, -4.75, 4.75, 0.0, 1.5, BLACK)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * 9.0, sx * 12.0))
        s.append(box(xa, xb, -4.0, 4.0, 1.5, 9.5, BRASS))
        s.append(box(sx * 11 - 0.6, sx * 11 + 0.6, -0.3, 0.3, -1.6, 0.0, TIN))
    s.append(rod("x", -10.0, 10.0, 0.0, 6.2, 2.6, GLASS, sides=16))
    return s


def jp101_wire_link():
    s = []
    for x in (0, 10):
        s.append(box(x - 0.7, x + 0.7, -0.7, 0.7, -1.6, 3.0, COPPER))
    s.append(box(-0.7, 10.7, -0.7, 0.7, 2.3, 3.0, COPPER))
    return s


def ltv_814s():
    s = [box(-2.3, 2.3, -3.25, 3.25, 0.35, 3.85, BLACK)]
    for x in (-1.27, 1.27):
        for sy in (-1, 1):
            ya, yb = sorted((sy * 3.25, sy * 5.15))
            s.append(box(x - 0.25, x + 0.25, ya, yb, 0.0, 0.25, TIN))
            ya, yb = sorted((sy * 3.25, sy * 3.5))
            s.append(box(x - 0.25, x + 0.25, ya, yb, 0.0, 1.0, TIN))
    return s


def moc3052svm():
    s = [box(-4.255, 4.255, -3.175, 3.175, 0.4, 3.9, BLACK)]
    for x in (-2.54, 0.0, 2.54):
        for sy in (-1, 1):
            ya, yb = sorted((sy * 3.175, sy * 5.27))
            s.append(box(x - 0.25, x + 0.25, ya, yb, 0.0, 0.25, TIN))
            ya, yb = sorted((sy * 3.175, sy * 3.425))
            s.append(box(x - 0.25, x + 0.25, ya, yb, 0.0, 1.0, TIN))
    return s


def ts1187a():
    s = [box(-2.55, 2.55, -2.55, 2.55, 0.1, 1.3, STEEL),
         rod("z", 1.3, 1.5, 0.0, 0.0, 1.3, BLACK, sides=16)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb = sorted((sx * 2.55, sx * 3.4))
            s.append(box(xa, xb, sy * 1.875 - 0.3, sy * 1.875 + 0.3, 0.0, 0.2, TIN))
    return s


def tab_bzxc():
    return [box(-3.15, 3.15, -0.4, 0.4, -1.6, 9.9, TIN)]


def r_wsk2512():
    s = [box(-1.675, 1.675, -1.59, 1.59, 0.0, 0.75, CERAMIC)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * 1.675, sx * 3.175))
        s.append(box(xa, xb, -1.59, 1.59, 0.0, 0.75, COPPER))
    return s


def reed_pads():
    s = [rod("y", 3.0, 17.0, 0.0, 2.0, 1.15, GLASS)]
    for y in (0, 20):
        s.append(box(-0.3, 0.3, y - 0.3, y + 0.3, -1.6, 2.3, TIN))
    s.append(box(-0.3, 0.3, 0.0, 3.0, 1.7, 2.3, TIN))
    s.append(box(-0.3, 0.3, 17.0, 20.0, 1.7, 2.3, TIN))
    return s


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
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out, exist_ok=True)
    for name, build in PARTS.items():
        write_step(os.path.join(out, name + ".step"), name, build())
        print(name + ".step")


if __name__ == "__main__":
    main()
