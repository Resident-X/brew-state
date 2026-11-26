"""Retrace the Staircase logo raster into a clean vector, and preview it.

Source: the owner-held raster (435 x 600, shaded, on white/transparent), named by --source or $STAIRCASE_LOGO_RASTER.
Output: staircase-logo.svg, flat-coloured faces with dead-straight edges, and
renders/directions/logo-preview.png (source, vector, and four engraved views drawn from the model's own engraving rule in logo.py).

How the faces were found
------------------------
The artwork is a folded-paper staircase: flat parallelogram faces in about
five flat colours whose edges run in a handful of directions (about -30, +28
and 90 degrees).  A colour segmentation of the raster (k-means in RGB,
background = near white or transparent) separates the faces but leaves their
edges ragged and the paper shading smears neighbours together, so the vertex
table below was read off the raster at pixel resolution along the colour
boundaries and then made exact: shared corners are written once, parallel
edges share one direction, and each face is listed as a full polygon in
back-to-front order.  The visible part of every face is computed (face minus
everything in front of it), so neighbouring faces meet on exactly the same
edge with no gap and no sliver.  The silhouette is the union of the faces.
The table is hand-derived from the pixels; the script reports how well the
silhouette covers the source figure.

Flat fills are the median source colour inside each visible face.
Run:  python trace_logo.py --source PATH.png            (writes the SVG and the preview)
      python trace_logo.py --source PATH.png --svg-only (writes the SVG only)
Needs numpy, shapely, Pillow and PyYAML: the interpreter `task hw:cad` creates holds them.
"""
import argparse
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
PARAMS = HERE / "params.yaml"
SVG_OUT = HERE / "staircase-logo.svg"
PREVIEW_OUT = HERE / "renders" / "directions" / "logo-preview.png"
SOURCE_ENV = "STAIRCASE_LOGO_RASTER"

HEIGHT_UNITS = 100.0
THICK = 9.0  # paper thickness of a stair tread, source pixels


def tread(a, b, e, t=THICK):
    """Stair tread seen from above: front corner a, front-right corner b,
    right tip e, with paper thickness t below the front edges."""
    back = (a[0] + e[0] - b[0], a[1] + e[1] - b[1])
    return [a, back, e, (e[0], e[1] + t), (b[0], b[1] + t), (a[0], a[1] + t)]


STEPS = (("step-4", (218, 388), (276, 419), (336, 386)),
         ("step-3", (228, 371), (292, 398), (336, 373)),
         ("step-2", (238, 357), (294, 384), (336, 360)),
         ("step-1", (247, 341), (295, 370), (336, 344)))

# (name, kind, vertices in source pixels), back to front.
FACES = [
    ("underside-left", "dark", [(100, 227), (162, 262), (181, 309), (199, 337), (175, 324),
                                (165, 302), (159, 284), (153, 280), (100, 249)]),
    ("top-sheet-lower", "light", [(255, 199), (331, 151), (331, 176), (257, 220)]),
    ("top-shadow-band", "dark", [(173, 142), (255, 199), (257, 220), (240, 213), (240, 205),
                                 (174, 164), (160, 172)]),
    ("top-riser", "dark", [(151, 198), (160, 172), (240, 213), (257, 220), (250, 236),
                           (229, 277), (207, 231)]),
    ("top-riser-lip", "light", [(160, 172), (174, 164), (240, 205), (240, 213)]),
    ("top-tread", "light", [(250, 98), (331, 151), (255, 199), (173, 142)]),
    ("middle-tread-wing", "light", [(100, 227), (150, 200), (207, 231), (162, 262)]),
    ("middle-tread-fold", "light", [(162, 262), (207, 231), (229, 277), (181, 309)]),
    ("wedge-shadow", "dark", [(181, 309), (217, 328), (217, 389), (215, 398), (199, 337)]),
    ("block-top", "light", [(181, 309), (229, 278), (245, 269), (281, 290), (217, 328)]),
    ("block-right", "dark", [(217, 328), (281, 290), (289, 318), (247, 341)]),
    ("block-front", "dark", [(217, 328), (247, 341), (247, 362), (230, 372), (217, 389)]),
] + [(n, "light", tread(a, b, e)) for n, a, b, e in STEPS[:3]] + [
    ("stack-side", "light", [(274, 417), (301, 408), (290, 430), (276, 462), (267, 433)]),
] + [(n, "light", tread(a, b, e)) for n, a, b, e in STEPS[3:]] + [
    ("floor-tread", "light", [(165, 433), (216, 399), (267, 433), (215, 464)]),
    ("floor-front-left", "light", [(165, 433), (215, 464), (215, 504), (165, 470)]),
    ("floor-front-right", "light", [(215, 464), (267, 433), (276, 462), (215, 504)]),
    ("navy-tread", "dark", [(104, 396), (159, 364), (216, 399), (165, 433)]),
    ("navy-front", "dark", [(104, 396), (165, 433), (165, 470), (106, 433)]),
]


def lerp(p, q, f):
    return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)


def sheet_lines():
    """Stacked-sheet edge lines as (face name, p, q), source pixels."""
    out = [("underside-left", (100, 238), (152, 267)),
           ("navy-front", (105, 414), (165, 452))]
    for name, a, b, e in STEPS:
        out += [(name, a, b), (name, b, e)]
    for f in (0.25, 0.5, 0.75):
        out.append(("floor-front-left", lerp((165, 433), (165, 470), f), lerp((215, 464), (215, 504), f)))
        out.append(("floor-front-right", lerp((215, 464), (215, 504), f), lerp((267, 433), (276, 462), f)))
    return out


def largest(geom):
    if geom.geom_type == "Polygon":
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
    return max(parts, key=lambda g: g.area) if parts else Polygon()


def visible_faces():
    polys = [Polygon(v).buffer(0) for _, _, v in FACES]
    out = []
    for i, p in enumerate(polys):
        front = unary_union(polys[i + 1:]) if i + 1 < len(polys) else Polygon()
        out.append(largest(p.difference(front)).simplify(0.01))
    return out


def sample_colour(vis, arr):
    h, w = arr.shape[:2]
    for inset in (3.0, 1.5, 0.0):
        g = largest(vis.buffer(-inset) if inset else vis)
        if g.is_empty:
            continue
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(list(g.exterior.coords), fill=1)
        m = np.array(mask, bool) & (arr[..., 3] > 200)
        if m.sum() >= 12:
            return tuple(int(round(float(np.median(arr[..., c][m])))) for c in range(3))
    raise SystemExit("no source pixels under a face")


def raster_iou(silhouette, arr):
    h, w = arr.shape[:2]
    mine = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mine).polygon(list(silhouette.exterior.coords), fill=1)
    mine = np.array(mine, bool)
    src = (arr[..., 3] > 128) & (arr[..., :3].min(2) < 235)
    return float((mine & src).sum() / (mine | src).sum())


def longest_edge_angle(poly):
    pts = list(poly.exterior.coords)
    best, ang = -1.0, 0.0
    for p, q in zip(pts, pts[1:]):
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d > best:
            best, ang = d, math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
    return (ang + 90.0) % 180.0 - 90.0  # a direction, not a heading: [-90, 90)


def build(source):
    arr = np.array(Image.open(source).convert("RGBA"))
    vis = visible_faces()
    union = unary_union([Polygon(v).buffer(0) for _, _, v in FACES])
    # close hairline notches where two faces only touch at a corner
    sil = largest(union.buffer(0.7, join_style="mitre").buffer(-0.7, join_style="mitre")).simplify(0.01)
    colours = [sample_colour(v, arr) for v in vis]
    minx, miny, maxx, maxy = sil.bounds
    k = HEIGHT_UNITS / (maxy - miny)

    def tf(geom):
        return affine_transform(geom, [k, 0, 0, k, -minx * k, -miny * k])

    def rounded(poly):
        return Polygon([(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords[:-1]])

    faces = []
    for (name, kind, _), v, c in zip(FACES, vis, colours):
        if v.is_empty or v.area < 4.0:
            raise SystemExit("face %s has no visible area" % name)
        faces.append(dict(name=name, kind=kind, poly=rounded(tf(v)), rgb=c))
    by_name = {n: i for i, (n, _, _) in enumerate(FACES)}
    lines = []
    for name, p, q in sheet_lines():
        seg = LineString([p, q]).intersection(vis[by_name[name]].buffer(0.05))
        for s in ([seg] if seg.geom_type == "LineString" else list(getattr(seg, "geoms", []))):
            if s.geom_type == "LineString" and not s.is_empty and s.length * k >= 1.0:
                (a, b) = tf(LineString([s.coords[0], s.coords[-1]])).coords
                lines.append((round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2)))
    return dict(W=(maxx - minx) * k, sil=rounded(tf(sil)), faces=faces, lines=lines,
                iou=raster_iou(sil, arr), arr=arr)


def hexrgb(c):
    return "#%02x%02x%02x" % c


def pts(poly):
    return " ".join("%g,%g" % xy for xy in poly.exterior.coords[:-1])


def write_svg(m):
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g 100">' % round(m["W"], 2),
         "  <title>Staircase logo, traced</title>",
         "  <desc>Traced from the Staircase logo, copyright David Baker, used with permission. "
         "Flat faces with straight edges; y down, height 100 units. Groups: silhouette, light faces, "
         "dark faces (each with data-hatch-angle, the direction of its longest edge in degrees), "
         "sheets (stacked-sheet edge lines).</desc>",
         '  <g id="silhouette">',
         '    <polygon points="%s" fill="#c9d3d6"/>' % pts(m["sil"]),
         "  </g>", '  <g id="light">']
    for f in m["faces"]:
        if f["kind"] == "light":
            o.append('    <polygon points="%s" fill="%s"/>' % (pts(f["poly"]), hexrgb(f["rgb"])))
    o += ["  </g>", '  <g id="dark">']
    for f in m["faces"]:
        if f["kind"] == "dark":
            o.append('    <polygon points="%s" fill="%s" data-hatch-angle="%.1f"/>'
                     % (pts(f["poly"]), hexrgb(f["rgb"]), longest_edge_angle(f["poly"])))
    o += ["  </g>", '  <g id="sheets" stroke="#33454d" stroke-width="0.4" fill="none">']
    for a, b, c, d in m["lines"]:
        o.append('    <line x1="%g" y1="%g" x2="%g" y2="%g"/>' % (a, b, c, d))
    o += ["  </g>", "</svg>"]
    SVG_OUT.write_text("\n".join(o) + "\n")


# ----------------------------------------------------------------- preview

SS = 2  # supersample factor
PX_PER_MM = 16.0
LID_MM, TRAY_MM = 28.0, 48.0        # the placed heights the preview shows (the lid's least, the tray top's)
BONE, GRAPHITE = "#e6e1d6", "#2f3237"


def font(size):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def logo_figures():
    """params.yaml read for the `logo` block only, as the callable the engraving rule takes."""
    import yaml
    data = yaml.safe_load(PARAMS.read_text())

    def P(key):
        node = data
        for part in key.split("."):
            node = node[part]
        return node["value"]
    return P


def engraved(height_mm, surface, ink, P):
    """The engraving at a placed height drawn from the model's own groove geometry: the surface colour with the grooves in the ink colour, at true line weights."""
    import logo
    e = logo.engrave(P, height_mm)
    s = PX_PER_MM * SS
    pad = 4.0
    w, h = e.width, e.height
    img = Image.new("RGB", (int((w + 2 * pad) * s), int((h + 2 * pad) * s)), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=int(2 * s), fill=surface)

    def px(x, y):          # the engraving's frame has y up; the image's y runs down
        return ((x + pad) * s, (h - y + pad) * s)

    geoms = list(e.geometry.geoms) if hasattr(e.geometry, "geoms") else [e.geometry]
    for poly in geoms:
        if poly.is_empty:
            continue
        d.polygon([px(x, y) for x, y in poly.exterior.coords], fill=ink)
        for ring in poly.interiors:
            d.polygon([px(x, y) for x, y in ring.coords], fill=surface)
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def flat_vector(m, height_mm):
    s = PX_PER_MM * height_mm / HEIGHT_UNITS * SS
    img = Image.new("RGB", (int(m["W"] * s), int(HEIGHT_UNITS * s)), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(x * s, y * s) for x, y in m["sil"].exterior.coords], fill=(201, 211, 214))
    for kind in ("light", "dark"):
        for f in m["faces"]:
            if f["kind"] == kind:
                d.polygon([(x * s, y * s) for x, y in f["poly"].exterior.coords], fill=f["rgb"])
    for a, b, c, e in m["lines"]:
        d.line([a * s, b * s, c * s, e * s], fill=(51, 69, 77), width=max(1, int(0.4 * s / 2)))
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def preview(m):
    P = logo_figures()
    ph = int(TRAY_MM * PX_PER_MM)
    rgba = Image.fromarray(m["arr"], "RGBA")
    bg = Image.new("RGBA", rgba.size, "white")
    bg.alpha_composite(rgba)
    src = bg.convert("RGB")
    box = src.convert("L").point(lambda v: 255 if v < 250 else 0).getbbox()
    src = src.crop(box)
    src = src.resize((int(src.width * ph / src.height), ph), Image.LANCZOS)
    panels = [("1  source raster", src),
              ("2  vector, flat colours", flat_vector(m, TRAY_MM)),
              ("3  engraved, single, %g mm (lid)" % LID_MM, engraved(LID_MM, BONE, "#9b968b", P)),
              ("4  engraved, single, %g mm (tray top)" % TRAY_MM, engraved(TRAY_MM, BONE, "#9b968b", P)),
              ("5  two colour, %g mm (lid): graphite on bone" % LID_MM, engraved(LID_MM, BONE, GRAPHITE, P)),
              ("6  two colour, %g mm (tray top): bone on graphite" % TRAY_MM, engraved(TRAY_MM, GRAPHITE, BONE, P))]
    gap, top = 24, 56
    W = sum(p.width for _, p in panels) + gap * (len(panels) + 1)
    H = max(p.height for _, p in panels) + top + gap
    canvas = Image.new("RGB", (W, H), "white")
    cd = ImageDraw.Draw(canvas)
    x = gap
    for label, p in panels:
        cd.text((x, 16), label, fill=(0, 0, 0), font=font(18))
        canvas.paste(p, (x, top))
        x += p.width + gap
    PREVIEW_OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(PREVIEW_OUT)


def main():
    parser = argparse.ArgumentParser(description="Retrace the Staircase logo raster into staircase-logo.svg and write the preview of its engraving.")
    parser.add_argument("--source", default=os.environ.get(SOURCE_ENV), help="the owner-held logo raster (a PNG, shaded, on white or transparent); defaults to $" + SOURCE_ENV)
    parser.add_argument("--svg-only", action="store_true", help="write the SVG only")
    args = parser.parse_args()
    if not args.source or not Path(args.source).is_file():
        raise SystemExit("the logo raster is not held in this repository: pass --source PATH or set " + SOURCE_ENV)
    m = build(args.source)
    write_svg(m)
    print("silhouette IoU against source: %.3f" % m["iou"])
    print("light faces %d, dark faces %d, sheet lines %d" % (
        sum(f["kind"] == "light" for f in m["faces"]),
        sum(f["kind"] == "dark" for f in m["faces"]), len(m["lines"])))
    if not args.svg_only:
        preview(m)


if __name__ == "__main__":
    main()
