#!/usr/bin/env python3
"""Insert the heater wall board's silk legend and conformal-coat keep-out marks into its .kicad_pcb as new top-level
S-expression text. Nothing already in the file is touched: the output is the input with lines added before the final ')'.

usage: add_legend.py IN.kicad_pcb OUT.kicad_pcb [items.json]
"""
import json, sys, uuid

NS = uuid.UUID("5d1c0f7e-3a52-4b0a-9a6e-77c0b4a3e001")
items = []          # dicts describing every inserted item (also written to items.json)
out = []


def n(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def uid(key):
    return str(uuid.uuid5(NS, key))


def text(name, layer, s, x, y, size, thick, rot=0, just="center"):
    out.append(
        '\t(gr_text "%s"\n\t\t(at %s %s %s)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %s %s)\n\t\t\t\t(thickness %s)\n\t\t\t)\n%s\t\t)\n\t)\n'
        % (s, n(x), n(y), n(rot), layer, uid(name), n(size), n(size), n(thick), ("\t\t\t(justify %s)\n" % just) if just in ("left", "right") else ""))
    items.append(dict(kind="gr_text", name=name, layer=layer, text=s, x=x, y=y, size=size, thickness=thick, rot=rot, justify=just))


def poly(name, layer, pts, width, fill):
    out.append(
        '\t(gr_poly\n\t\t(pts\n\t\t\t%s\n\t\t)\n\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill %s)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)\n'
        % (" ".join("(xy %s %s)" % (n(a), n(b)) for a, b in pts), n(width), "yes" if fill else "no", layer, uid(name)))
    items.append(dict(kind="gr_poly", name=name, layer=layer, pts=pts, stroke=width, fill=fill))


def rect(name, layer, x0, y0, x1, y1, width, dash):
    out.append(
        '\t(gr_rect\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width %s)\n\t\t\t(type %s)\n\t\t)\n\t\t(fill no)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)\n'
        % (n(x0), n(y0), n(x1), n(y1), n(width), "dash" if dash else "solid", layer, uid(name)))
    items.append(dict(kind="gr_rect", name=name, layer=layer, x0=x0, y0=y0, x1=x1, y1=y1, stroke=width, dash=dash))


def dot(name, x, y):
    out.append(
        '\t(gr_circle\n\t\t(center %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill yes)\n\t\t(layer "F.SilkS")\n\t\t(uuid "%s")\n\t)\n'
        % (n(x), n(y), n(x + 0.25), n(y), uid(name)))
    items.append(dict(kind="gr_circle", name=name, layer="F.SilkS", x=x, y=y, radius=0.25, stroke=0.1, fill=True))


S = "F.SilkS"
# (a) blade names and captions
for nm, big, cap, x in (("RET", "RET", "RETURN", 24.5), ("OUT_S", "OUT_S", "STEAM", 32.6), ("OUT_C", "OUT_C", "COFFEE", 44.0)):
    text("blade_" + nm, S, big, x, 80.3, 1.5, 0.2)
    text("blade_cap_" + nm, S, cap, x, 82.3, 1.0, 0.15)
# (b) triac function names
text("triac_steam", S, "STEAM", 41.2, 25.6, 1.0, 0.15)
text("triac_coffee", S, "COFFEE", 48.6, 25.6, 1.0, 0.15)
# (c) J931 pin names, vertical, bottom-aligned (left-justified, rotated 90: the text starts at the anchor and runs upward)
text("j931_pin3", S, "3 HEAT_S_LED_K", 47.4, 64.5, 1.0, 0.15, 90, "left")
text("j931_pin2", S, "2 HEAT_C_LED_K", 48.9, 64.5, 1.0, 0.15, 90, "left")
text("j931_pin1", S, "1 +5V_WB", 50.4, 64.5, 1.0, 0.15, 90, "left")
# (d) board name block
BX = 64.3
text("blk_brew", S, "BREW STATE", BX, 80.3, 1.5, 0.2, 0, "right")
text("blk_sunbeam", S, "SUNBEAM EM7000", BX, 82.3, 1.0, 0.15, 0, "right")
text("blk_heater", S, "HEATER WALL BOARD", BX, 83.9, 1.0, 0.15, 0, "right")
text("blk_version", S, "v1  2026-11", BX, 86.0, 1.5, 0.2, 0, "right")
# (e) mains warning: the main board's front triangle and bolt, translated so the triangle's centre is at (33.5, 56.5)
TRI = [(13.475, 5.425), (16.475, 10.6212), (10.475, 10.6212)]
BOLT = [(13.8875, 7.7641), (12.7625, 9.4141), (13.4375, 9.4141), (13.025, 10.6891), (14.1875, 8.9641), (13.5125, 8.9641)]
dx, dy = 33.5 - 13.475, 56.5 - (5.425 + 10.6212) / 2
poly("warn_triangle", S, [(x + dx, y + dy) for x, y in TRI], 0.25, False)
poly("warn_bolt", S, [(x + dx, y + dy) for x, y in BOLT], 0.1, True)
text("warn_danger", S, "DANGER", 33.5, 61.6, 1.5, 0.2)
text("warn_mains", S, "MAINS VOLTAGE", 33.5, 63.9, 1.5, 0.2)
text("warn_rating", S, "230 V~ 50 Hz", 33.5, 66.0, 1.0, 0.15)
# (f) pin 1 marks outside the body of the two optocouplers (the footprint's own dot lies inside the body outline)
dot("u911_pin1_dot", 56.7, 54.95)
dot("u921_pin1_dot", 64.45, 61.45)

# Job 2: conformal-coat keep-outs on F.Fab, dashed, 0.15. Extents are the F.Fab outlines' boxes, stroke included.
F = "F.Fab"
blade = {"J911": (43.55, 86.06, 44.45, 94.03), "J921": (32.15, 86.06, 33.05, 94.03), "J941": (24.05, 86.06, 24.95, 94.03)}
for r, (a, b, c, d) in blade.items():
    rect("coat_" + r, F, a - 0.6, b - 0.6, c + 0.6, d + 0.6, 0.15, True)
a, b, c, d = 56.78, 56.88, 64.50, 59.52
rect("coat_J931", F, a - 0.3, b - 0.3, c + 0.3, d + 0.3, 0.15, True)
rect("coat_T911_tab", F, 51.95, 19.45, 62.45, 20.25, 0.15, True)
rect("coat_T921_tab", F, 27.35, 19.45, 37.85, 20.25, 0.15, True)
text("coat_note1", F, "DASHED BOXES: NO COAT", 33.5, 73.4, 1.0, 0.15)
text("coat_note2", F, "SEE FABRICATION-NOTES.MD", 33.5, 75.0, 1.0, 0.15)

if __name__ == "__main__":
    src = open(sys.argv[1], encoding="utf-8").read()
    assert src.endswith("\n)\n"), "unexpected end of board file"
    for it in items:
        pass
    new = src[:-2] + "".join(out) + ")\n"
    open(sys.argv[2], "w", encoding="utf-8").write(new)
    if len(sys.argv) > 3:
        json.dump(items, open(sys.argv[3], "w"), indent=1)
    print("inserted", len(items), "items")
