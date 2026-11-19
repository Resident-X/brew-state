"""route_lv.py IN.kicad_pcb OUT.kicad_pcb   (KiCad's Python, -I; the board's .kicad_pro and .kicad_dru beside IN)

Low-voltage reconnect after the mains re-lay, Sunbeam EM7000 main board.  Adds only low-voltage copper (tracks, vias); deterministic uuids;
refills every zone, checks the mains zones still fill, saves through neutral_pour.save_board.  Board mm, x right, y down.
Layer keys: F, B, In3.  TRACKS rows: (net, layer, width, [points]); VIAS rows: (net, x, y).
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import neutral_pour as NP

TAG = 'sunbeam-em7000/main-board-v2/s5-lv/'
PUMP, VALVE, INTL = '/Pump drives/', '/Valve drives/', '/Interlock/'
W_SIG, W_5V = 0.2, 0.45
VIA_DIA, VIA_DRILL = 0.6, 0.3
LAYER = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu, 'In3': pcbnew.In3_Cu}
mm = lambda v: int(round(v * 1e6))

TRACKS = []
VIAS = []

# ---- PUMP_S_LED_A: U711.1 east to a 45 degree jog and north to R713.2
TRACKS += [(PUMP + 'PUMP_S_LED_A', 'F', W_SIG, [(64.26, 19.892), (65.6, 19.892), (67.13, 18.362), (67.13, 15.257)])]

# ---- +5V: D206.3 leaves its pad along the axis to a via, B.Cu to the end of the B.Cu track at the (68.8, 102.7) via
VIAS += [('+5V', 67.6, 107.569)]
TRACKS += [('+5V', 'F', W_5V, [(66.4, 107.569), (67.6, 107.569)]),
           ('+5V', 'B', W_5V, [(67.6, 107.569), (68.4, 106.769), (68.4, 103.1), (68.8, 102.7)])]

# ---- PUMP_C_LED_K: U701.2 to Q701.3 (enters its vertical pad from the north)
TRACKS += [(PUMP + 'PUMP_C_LED_K', 'F', W_SIG, [(64.26, 31.446), (66.4, 31.446), (67.0, 32.046), (67.0, 34.562)])]

# ---- PUMP_C_GATE_G: Q701.1 to R702.1 by a B.Cu hop under the PUMP_C_LED_A lane, then R702.1 to R701.2
VIAS += [(PUMP + 'PUMP_C_GATE_G', 66.05, 37.7), (PUMP + 'PUMP_C_GATE_G', 70.6, 36.7)]
TRACKS += [(PUMP + 'PUMP_C_GATE_G', 'F', W_SIG, [(66.05, 36.438), (66.05, 37.7)]),
           (PUMP + 'PUMP_C_GATE_G', 'B', W_SIG, [(66.05, 37.7), (66.45, 37.3), (70.0, 37.3), (70.6, 36.7)]),
           (PUMP + 'PUMP_C_GATE_G', 'F', W_SIG, [(69.5, 36.7), (75.4, 36.7), (76.49, 37.79), (81.602, 37.79)])]

# ---- PUMP_C_LED_A: U701.1 east, a B.Cu hop under the U701 pad column's east lane, then round Q701.3 / Q701.2 on their east side, south to R703.2
VIAS += [(PUMP + 'PUMP_C_LED_A', 66.1, 33.986), (PUMP + 'PUMP_C_LED_A', 68.6, 33.986)]
TRACKS += [(PUMP + 'PUMP_C_LED_A', 'F', W_SIG, [(64.26, 33.986), (66.1, 33.986)]),
           (PUMP + 'PUMP_C_LED_A', 'B', W_SIG, [(66.1, 33.986), (68.6, 33.986)]),
           (PUMP + 'PUMP_C_LED_A', 'F', W_SIG, [(68.6, 33.986), (68.6, 38.0), (67.6, 39.0), (67.6, 44.1),
                                                (67.1, 44.6), (65.2, 44.6), (64.337, 45.463), (64.337, 46.1)])]

# ---- PUMP_S_LED_K: U711.2 down the east side of the U711/U701 pad column, hop to B.Cu, back to F beside Q711 and into Q711.3 from the west
VIAS += [(PUMP + 'PUMP_S_LED_K', 65.9, 17.352), (PUMP + 'PUMP_S_LED_K', 62.3, 38.2)]
TRACKS += [(PUMP + 'PUMP_S_LED_K', 'F', W_SIG, [(64.26, 17.352), (65.9, 17.352)]),
           (PUMP + 'PUMP_S_LED_K', 'B', W_SIG, [(65.9, 17.352), (65.4, 17.852), (65.4, 35.1), (62.3, 38.2)]),
           (PUMP + 'PUMP_S_LED_K', 'F', W_SIG, [(62.3, 38.2), (62.3, 42.4), (62.9, 43.0), (65.338, 43.0)])]

# ---- VALVE_3W_G: Q741.1 (leaves its vertical pad along the axis) over a B.Cu lane to R742.1; R742.1 over In3 to R741.2
VIAS += [(VALVE + 'VALVE_3W_G', 64.302, 24.1), (VALVE + 'VALVE_3W_G', 61.45, 35.6), (VALVE + 'VALVE_3W_G', 65.0, 36.675), (VALVE + 'VALVE_3W_G', 69.8, 39.599)]
TRACKS += [(VALVE + 'VALVE_3W_G', 'F', W_SIG, [(67.052, 22.456), (67.052, 23.6), (66.552, 24.1), (64.302, 24.1)]),
           (VALVE + 'VALVE_3W_G', 'B', W_SIG, [(64.302, 24.1), (64.302, 34.4), (63.102, 35.6), (61.45, 35.6)]),
           (VALVE + 'VALVE_3W_G', 'F', W_SIG, [(61.45, 35.6), (62.525, 36.675)]),
           (VALVE + 'VALVE_3W_G', 'F', W_SIG, [(62.525, 36.675), (65.0, 36.675)]),
           (VALVE + 'VALVE_3W_G', 'In3', W_SIG, [(65.0, 36.675), (66.876, 36.675), (69.8, 39.599)]),
           (VALVE + 'VALVE_3W_G', 'F', W_SIG, [(69.8, 39.599), (77.715, 39.599)])]

# ---- ZC_IN: U602.4 east to C630.1 (via the TP630 B.Cu test point on a short stub)
VIAS += [('/ZC_IN', 63.15, 24.368)]
TRACKS += [('/ZC_IN', 'F', W_SIG, [(60.7, 23.128), (61.91, 23.128), (63.15, 24.368), (64.45, 25.668), (65.707, 26.925), (66.35, 26.925)]),
           ('/ZC_IN', 'B', W_SIG, [(63.15, 24.368), (63.15, 25.4)])]

# ---- POL_COIL_LO: Z201.3 stub down to the Z202.3 west track
VIAS += [(INTL + 'POL_COIL_LO', 62.895, 101.4)]
TRACKS += [(INTL + 'POL_COIL_LO', 'F', W_SIG, [(62.895, 100.605), (62.895, 101.4)]),
           (INTL + 'POL_COIL_LO', 'B', W_SIG, [(62.895, 101.4), (61.2, 103.095), (61.2, 103.777)])]

# ---- K201 coil: both lanes on B.Cu under the relay, west of the interlock block (the pads leave south of the barrier strip).
#      The +5V lane ends at a via beside U203.5 (F.Cu stub to the pad); from that via an In3 lane carries it to the +5V column's via.
VIAS += [('+5V', 61.018, 113.2)]
TRACKS += [(INTL + 'POL_COIL_LO', 'B', W_SIG, [(31.56, 124.78), (32.537, 124.78), (47.0, 110.317), (59.846, 110.317)]),
           ('+5V', 'B', W_5V, [(24.0, 124.78), (25.62, 126.4), (49.318, 126.4), (61.018, 114.7), (61.018, 113.2)]),
           ('+5V', 'F', W_5V, [(61.018, 113.2), (61.018, 112.094)]),
           ('+5V', 'In3', W_5V, [(61.018, 113.2), (63.818, 110.4), (70.439, 110.4)])]


# ---- GND: the F.Cu pour fragment that the lanes above close off (it holds R712.2, Q701.2, R742.2 and Q711.2) is tied to the GND planes by a via beside Q711.2
VIAS += [('GND', 62.0, 43.95)]
TRACKS += [('GND', 'F', W_5V, [(63.462, 43.95), (62.0, 43.95)])]


def _kiid(*key):
    return pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, TAG + '/'.join(str(k) for k in key))))


def _near(a, b):
    return abs(a - b) < 5e-4


def _same_point(p, q):
    return _near(p[0], q[0]) and _near(p[1], q[1])


def remove_own(board):
    """Take up the tracks and vias the tables draw (matched by net, layer, width and position), so a re-run replaces them."""
    layer_key = {v: k for k, v in LAYER.items()}
    for t in list(board.GetTracks()):
        if isinstance(t, pcbnew.PCB_VIA):
            p = (t.GetPosition().x / 1e6, t.GetPosition().y / 1e6)
            if any(net == t.GetNetname() and _same_point(p, (x, y)) for net, x, y in VIAS):
                board.RemoveNative(t)
            continue
        if t.GetLayer() not in layer_key:
            continue
        a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        for net, layer, width, pts in TRACKS:
            if net != t.GetNetname() or layer != layer_key[t.GetLayer()] or not _near(width, t.GetWidth() / 1e6):
                continue
            if any((_same_point(a, p) and _same_point(b, q)) or (_same_point(a, q) and _same_point(b, p)) for p, q in zip(pts, pts[1:])):
                board.RemoveNative(t)
                break


def build(board):
    remove_own(board)
    V = lambda x, y: pcbnew.VECTOR2I(mm(x), mm(y))
    new = []
    for i, (net, layer, width, pts) in enumerate(TRACKS):
        ni = board.FindNet(net)
        assert ni is not None, net
        for j, (a, b) in enumerate(zip(pts, pts[1:])):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(mm(width)); t.SetLayer(LAYER[layer]); t.SetNet(ni)
            t.SetUuid(_kiid('track', i, j, net, layer, a, b)); board.Add(t); new.append(t)
    for i, (net, x, y) in enumerate(VIAS):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y)); v.SetWidth(mm(VIA_DIA)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(board.FindNet(net))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetUuid(_kiid('via', i, net, x, y)); board.Add(v); new.append(v)
    return new


def main(argv):
    src, out = argv[1], argv[2]
    text = open(src, encoding='utf-8', newline='').read()
    board = NP.load_board(src)
    build(board)
    NP.unset_tap_clearances(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    NP.assert_mains_zones_fill(board, out=open(os.devnull, 'w'))
    board.BuildConnectivity()
    print('unconnected after fill:', board.GetConnectivity().GetUnconnectedCount(False))
    NP.save_board(board, out, text)


if __name__ == '__main__':
    main(sys.argv)
