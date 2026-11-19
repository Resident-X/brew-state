"""route_entry.py IN.kicad_pcb OUT.kicad_pcb   (KiCad's Python, -I)

ENTRY block mains copper for the Sunbeam EM7000 main board: LINE1, LINE_IN, LINE_F, LINE (south zone and the
north spine with its taps), NEUTRAL_IN, NEUTRAL (lands, taps, the In2 pour), DISCH_A/B, and the first part of the
SHUNT_SENSE_IN / SHUNT_SENSE_NEUTRAL Kelvin pair. Adds only this block's copper (zones, tracks, vias), refills every zone,
saves. Moves no part, touches no copper of any other net. Re-running on its own output replaces its own copper first.

Board mm, x right, y down. All geometry is in the tables below.

Hand-over to the measure block: the Kelvin pair leaves R105 on F.Cu (a stub along each sense pad's long axis to its dive via) and
runs on In2 to x 15.0, heading east: SHUNT_SENSE_NEUTRAL ends at (15.0, 80.7), SHUNT_SENSE_IN at (15.0, 81.4), both 0.25 wide,
pitch 0.7 (edge gap 0.45 against the signed 0.4). Both nets must stay at y <= 81.45 (SHUNT_SENSE_NEUTRAL <= 80.75) while x is between
14.2 and 18.4, and may not surface on F.Cu within 3.0 mm of the NT601 net-tie polygon (x 12.0..13.0, y 79.75..80.25).

The In2 NEUTRAL pour is neutral_pour.add_neutral_pour (also runnable alone: neutral_pour.py IN OUT).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402

import apply_fp  # noqa: E402
import neutral_pour  # noqa: E402

mm = pcbnew.FromMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu

NETS = {
    "LINE": "/LINE",
    "LINE1": "/LINE1",
    "LINE_IN": "/Mains entry and load feed/LINE_IN",
    "LINE_F": "/Mains entry and load feed/LINE_F",
    "NEUTRAL_IN": "/Mains entry and load feed/NEUTRAL_IN",
    "NEUTRAL": "/NEUTRAL",
    "DISCH_A": "/Mains entry and load feed/DISCH_A",
    "DISCH_B": "/Mains entry and load feed/DISCH_B",
    "SSI": "/SHUNT_SENSE_IN",
    "SSN": "/SHUNT_SENSE_NEUTRAL",
}

VIA_SIZE, VIA_DRILL = 0.75, 0.30
SENSE_W = 0.25
DISCH_W = 0.30
ZONE_MIN_W = 0.20
ZONE_CLEARANCE = 3.0     # a Mains zone may declare 3.0 or more; KiCad's own rules (1.5 between mains nets) decide the fill, the outline holds 2.6


def R(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---------------------------------------------------------------------------------------------------------------- zones
# name: (net, layers, [polygons]); polygons are unioned. Trunk nets are zones only, F and B in parallel through the plated pads.
ZONES = [
    # LINE1: J101 band west of K201 pin column 13 (x 22.7), neck between notch wall (y 102.7, copper from 103.0) and the barrier
    # strip (K201 pad bottoms, y 105.52); 3.0 from LINE (pad bottom 100.48) and from LINE_IN (band bottom 100.4)
    ("LINE1", (F, B), [R(2.96, 103.5, 22.7, 108.7), R(22.7, 103.5, 32.86, 105.5)]),
    # LINE_IN: band over J102 (and TP101), lane to F101.1
    ("LINE_IN", (F, B), [[(14.2, 86.3), (18.4, 86.3), (18.4, 100.4), (2.96, 100.4), (2.96, 96.8), (14.2, 96.8)]]),
    # LINE_F: one 45-degree lane from F101.2 (cut through the pad centre, edges 0.1 outside the tangents of the 3.0 ring) to JP101.1,
    # 2.19 per layer, 4.38 F+B; the B copy also takes TP102
    ("LINE_F", (F,), [[(43.85, 85.85), (45.4, 87.4), (38.2, 94.6), (36.65, 93.05)]]),
    ("LINE_F", (B,), [[(43.85, 85.85), (45.4, 87.4), (38.2, 94.6), (36.65, 93.05)], R(40.0, 92.5, 42.5, 93.5)]),
    # LINE south: JP101.2 -> funnel -> K201 pins 14 (flush with the pad boxes)
    ("LINE", (F,), [[(27.0, 92.4), (30.0, 92.4), (30.0, 95.82), (32.86, 98.68), (32.86, 100.48), (22.7, 100.48),
                       (22.7, 98.68), (27.0, 94.38)]]),
    # NEUTRAL_IN: J103 block (takes TP105, TP107), neck to R105.1
    ("NEUTRAL_IN", (F, B), [[(7.0, 86.6), (11.5, 86.6), (11.5, 94.0), (2.96, 94.0), (2.96, 88.7), (7.0, 88.7)]]),
]

# NEUTRAL land: F (J110 band with NT601.1, stem to R105.4) and B (J110 band with TP106, TP108)
ZONES += [
    ("NEUTRAL", (F,), [R(1.5, 78.2, 8.9, 80.3), R(1.5, 80.3, 6.17, 84.3)]),
    ("NEUTRAL", (B,), [R(1.5, 78.2, 13.3, 81.2), R(12.2, 81.2, 13.3, 82.6)]),
]

# LINE north spine, B.Cu only: cross-bar under the R101..R104 row's north edge with the north spine through the through-hole
# taps, the south riser to K201.14, the west spur to the R101.1/R103.1 via, the east spurs to the R601.1/R630.1 vias
LINE_B = [
    R(16.0, 46.2, 18.0, 73.4),      # north spine: JP303.1 RT301.1 RV101.1 C101.1 stand in it
    R(13.2, 46.7, 16.0, 47.7),      # TP103 (spur exactly the pad box high, 1.0)
    R(9.7, 71.4, 25.0, 73.4),       # cross-bar
    R(23.0, 71.4, 25.0, 99.5),      # south riser (under the fuse body, joins the K201.14 funnel)
    R(18.0, 62.25, 27.05, 63.25),   # SUPPLY: bar to RT301.1 (26.55, 59.95), its top edge 3.35 from the ZC_LED_A via (22.3, 58.9): the zone's 3.0 clearance + the via radius 0.3 leaves the bar uncut
    R(26.05, 59.95, 27.05, 62.25),  # riser into the RT301.1 ring from below (flush on the ring's bottom)
]
LINE_B.append([(27.0, 92.4), (30.0, 92.4), (30.0, 95.82), (32.86, 98.68), (32.86, 100.48), (22.7, 100.48),
               (22.7, 98.68), (27.0, 94.38)])
ZONES += [("LINE", (B,), LINE_B)]

# SMD tap patches on F (zones, 1.0 mm or wider) that join an SMD pad to its via
ZONES += [
    ("LINE", (F,), [R(9.1, 71.9, 11.9, 75.58)]),         # R101.1 + R103.1 (one patch, via at 10.5, 72.5)
    ("LINE", (F,), [R(27.4, 60.3, 28.85, 73.34)]),        # SUPPLY: RT301.1 ring -> R630.1 and R601.1 (right column)
    ("NEUTRAL", (F,), [R(1.57, 73.83, 2.7, 77.5)]),      # R102.2, via 2.135, 76.9
    ("NEUTRAL", (F,), [R(18.3, 73.83, 19.43, 77.5)]),    # R104.2, via 18.865, 76.9
]

# ----------------------------------------------------------------------------------------------------------------- vias
VIAS = [
    ("LINE", 10.5, 72.5),
    ("NEUTRAL", 2.135, 76.9), ("NEUTRAL", 18.865, 76.9),
    ("NEUTRAL", 11.45, 80.0),                      # NT601.1: the net tie's polygon keeps every fill 3.0 away, so a via joins the pad to the B land
    ("SSN", 5.1, 86.22), ("SSI", 11.9, 83.68),     # Kelvin dive vias, each beside its own sense pad
]

# ---------------------------------------------------------------------------------------------------------------- tracks
# (net, layer, width, [points]) ; 0 / 45 / 90 degrees only
IN2 = pcbnew.In2_Cu
TRACKS = [
    ("DISCH_A", F, DISCH_W, [(5.0625, 74.7), (6.7375, 74.7)]),
    ("DISCH_B", F, DISCH_W, [(14.2625, 74.7), (15.9375, 74.7)]),
    # Kelvin pair: stub on F along each sense pad's long axis to its dive via, then In2 under R105 / J110 to the hand-over at
    # x 15.0: SHUNT_SENSE_NEUTRAL y 80.7, SHUNT_SENSE_IN y 81.4 (pitch 0.7, edge gap 0.45), both on In2 heading east
    ("SSN", F, SENSE_W, [(3.725, 86.22), (5.1, 86.22)]),
    ("SSN", IN2, SENSE_W, [(5.1, 86.22), (9.02, 82.3), (12.29, 82.3), (13.89, 80.7), (15.0, 80.7)]),
    ("SSI", F, SENSE_W, [(10.275, 83.68), (11.9, 83.68)]),
    ("SSI", IN2, SENSE_W, [(11.9, 83.68), (14.18, 81.4), (15.0, 81.4)]),
]


def det_uuid(item, *key):
    """A fixed UUID for an item this script adds, from what identifies it, so two runs give the same file."""
    item.SetUuid(pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, "sunbeam-em7000/main-board-v2/entry/" + "/".join(str(k) for k in key)))))


def mk_chain(pts):
    c = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in pts:
        c.Append(mm(x), mm(y))
    c.SetClosed(True)
    return c


def union(polys):
    out = pcbnew.SHAPE_POLY_SET()
    for pts in polys:
        p = pcbnew.SHAPE_POLY_SET()
        p.AddOutline(mk_chain(pts))
        if out.OutlineCount() == 0:
            out = p
        else:
            out.BooleanAdd(p)
    return out


def set_outline(z, poly):
    """Copy `poly` (outlines and holes) into the zone's own outline (SetOutline would take ownership of a Python object)."""
    out = z.Outline()
    out.RemoveAllContours()
    out.Append(poly)


def own_zone(z):
    return z.GetZoneName().startswith("ENTRY ")


def _key(a, b=None):
    return (round(a[0], 3), round(a[1], 3)) if b is None else tuple(sorted(((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)))))


def remove_own(board):
    """Remove what an earlier run of this script added: its zones, its vias and its tracks (matched by net and position)."""
    for z in list(board.Zones()):
        if own_zone(z) or neutral_pour.is_pour(z):
            board.RemoveNative(z)
    via_keys = {(NETS[k], _key((x, y))) for k, x, y in VIAS}
    seg_keys = set()
    for key, layer, w, pts in TRACKS:
        for a, b in zip(pts, pts[1:]):
            seg_keys.add((NETS[key], _key(a, b)))
    for t in list(board.GetTracks()):
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            if (t.GetNetname(), _key((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))) in via_keys:
                board.RemoveNative(t)
        else:
            s_, e_ = t.GetStart(), t.GetEnd()
            k = _key((pcbnew.ToMM(s_.x), pcbnew.ToMM(s_.y)), (pcbnew.ToMM(e_.x), pcbnew.ToMM(e_.y)))
            if (t.GetNetname(), k) in seg_keys:
                board.RemoveNative(t)


def add_zone(board, key, layer, polys, name):
    net = board.FindNet(NETS[key])
    assert net is not None, key
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetZoneName(name)
    z.SetMinThickness(mm(ZONE_MIN_W))
    z.SetLocalClearance(mm(ZONE_CLEARANCE))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(0)
    set_outline(z, union(polys))
    det_uuid(z, "zone", name)
    board.Add(z)
    return z


def add_track(board, key, layer, width, a, b):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    t.SetNet(board.FindNet(NETS[key]))
    det_uuid(t, "track", key, layer, a, b)
    board.Add(t)


def add_via(board, key, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(VIA_SIZE))
    v.SetDrill(mm(VIA_DRILL))
    v.SetLayerPair(F, B)
    v.SetNet(board.FindNet(NETS[key]))
    det_uuid(v, "via", key, x, y)
    board.Add(v)


def build(board, pour=True):
    remove_own(board)
    apply_fp.sync_footprint(board)
    for i, (key, layers, polys) in enumerate(ZONES):
        for layer in layers:
            add_zone(board, key, layer, polys, "ENTRY %s %s %d" % (key, "F" if layer == F else "B", i))
    for key, x, y in VIAS:
        add_via(board, key, x, y)
    for key, layer, w, pts in TRACKS:
        for a, b in zip(pts, pts[1:]):
            add_track(board, key, layer, w, a, b)
    if pour:
        neutral_pour.add_neutral_pour(board)


def main(argv):
    src, out = argv[1], argv[2]
    text = open(src, encoding="utf-8", newline="").read()
    board = neutral_pour.load_board(src)
    build(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    neutral_pour.save_board(board, out, text)


if __name__ == "__main__":
    main(sys.argv)
