"""route_north.py IN.kicad_pcb OUT.kicad_pcb

NORTH block mains routing, Sunbeam EM7000 main board (KiCad 10 pcbnew; run with KiCad's python, -I).
  apply_moves(board): the part MOVES of the block (and the PAD_NETS table, empty), idempotent
  build(board):       adds only north-block copper (tracks, vias, F/B zones); removes earlier north copper of the same items first
Standalone: loads IN, apply_moves, build, rebuilds the In2 NEUTRAL pour (neutral_pour.py, it cuts the antipads of the new
vias), fills every zone, saves twice (must match), re-inserts the 10 board-level property lines, removes .history / *.kicad_prl.
The chain (build_mains.py) calls apply_moves and build.  Board mm, x right, y down.  Everything is in the tables below.
"""
import sys, os, re, math, shutil, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
VIA_DIA, VIA_DRILL = 0.75, 0.3
PUMP = '/Pump drives/'
VCOM = '/Valve drives/VALVE_COM'
HOT = '/HOTVALVE'
COF = '/COFVALVE'
N_NEUTRAL = '/NEUTRAL'
ZCNET = '/Zero-crossing detector/ZC_LED_A'
W_LOAD = 0.6
W_VALVE = 0.3      # PLAN3 F2: valve nets carry at most the 0.4 A of F731
W_SIG = 0.25

# ------------------------------------------------------------------------------------------------ MOVES
# footprint origin positions (x, y, rotation in degrees); applied first, same side, texts follow the part
MOVES = [
    {"ref": "R705", "x": 45.6, "y": 23.8, "rot": 0.0},     # BRIEF J (R4): 0.5 west, frees the ZC_LED_A via site west of U602.1
    {"ref": "R704", "x": 42.05, "y": 26.2, "rot": 90.0},   # BRIEF J (R4): 0.3 west with R705 (courtyards stay apart)
    {"ref": "R715", "x": 38.5, "y": 9.8, "rot": 0.0},
    {"ref": "TP702", "x": 13.3, "y": 36.0, "rot": 180.0},
    {"ref": "TP712", "x": 13.3, "y": 25.4, "rot": 180.0},
]
# pad net swap (PLAN3 F1) NOT applied: with VALVE_COM on the east B column (x 45.46) the accepted PUMP_C_OPTO_MT via has no
# legal site (see NOTES3.md); the table stays empty, apply_moves sets nothing.
PAD_NETS = []
# designator text of the two test points, placed beside them in the strip west of the holder courtyards (centre x, y)
TEXT_AT = {"TP702": (12.2, 34.5), "TP712": (12.2, 23.9)}

# ------------------------------------------------------------------------------------------------ TABLES
TRACKS = []
VIAS = []
ZONES = []
OPTO_V1 = (48.06, 23.05)     # PUMP_C_OPTO_MT via beside R705.2 (BRIEF J)
ZC_V1 = (50.6, 26.17)        # ZC_LED_A via west of U602.1, 0.6/0.3 (BRIEF J R5)
ZC_V2 = (22.3, 58.9)         # ZC_LED_A via below R631.2, 0.6/0.3 (BRIEF J R5)
W_ZC = 0.25


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


TRACKS += [
    ('/COFFPUMP', 'F', W_LOAD, [(4.46, 39.3), (12.2, 39.3), (16.8, 34.7), (16.8, 31.1)]),
    ('/STEAMPUMP', 'F', W_LOAD, [(4.46, 29.7), (12.1, 29.7), (16.8, 25.0), (16.8, 20.5)]),
]
TRACKS += [
    (PUMP + 'PUMP_C_GATE_R', 'F', W_SIG, [(42.3, 24.3), (43.7, 24.3)]),
    (PUMP + 'PUMP_S_GATE_R', 'F', W_SIG, [(36.6, 13.6), (36.6, 10.4)]),
    (PUMP + 'PUMP_S_MT2', 'F', W_LOAD, [(40.5, 14.7), (41.6, 14.7)]),
    (PUMP + 'PUMP_C_TRIAC_G', 'F', W_SIG, [(50.54, 29.72), (50.54, 31.5), (53.5, 34.46), (54.9, 34.46)]),
    (PUMP + 'PUMP_S_TRIAC_G', 'F', W_SIG, [(50.54, 14.92), (50.54, 16.99), (54.05, 20.5), (54.9, 20.5)]),
]
TRACKS += [
    # BRIEF J: the via moves to the north-east corner of R705.2 (between the T711 tab and U602.2), the B lane passes west and south of
    # the ZC_LED_A via ZC_V1 and returns along y 29.3 to the U701.6 via
    (PUMP + 'PUMP_C_OPTO_MT', 'F', W_SIG, [OPTO_V1, (47.5, OPTO_V1[1])]),
    (PUMP + 'PUMP_C_OPTO_MT', 'B', W_SIG, [OPTO_V1, (47.45, OPTO_V1[1] + 0.61), (47.45, 27.6), (49.15, 29.3), (53.55, 29.3), (55.0, 27.85)]),
    (PUMP + 'PUMP_S_OPTO_MT', 'F', W_SIG, [(40.4, 9.4), (40.4, 7.1), (39.2, 5.9), (38.0, 5.9)]),
    (PUMP + 'PUMP_S_OPTO_MT', 'In2', W_SIG, [(38.0, 5.9), (38.0, 9.0), (44.4, 15.4), (52.8, 15.4), (55.0, 13.2)]),
    (PUMP + 'PUMP_S_OPTO_MT', 'F', W_SIG, [(55.0, 13.2), (55.0, 14.2)]),
]
VIAS += [(PUMP + 'PUMP_C_OPTO_MT', OPTO_V1[0], OPTO_V1[1]), (PUMP + 'PUMP_C_OPTO_MT', 55.0, 27.85),
         (PUMP + 'PUMP_S_OPTO_MT', 38.0, 5.9), (PUMP + 'PUMP_S_OPTO_MT', 55.0, 13.2)]
# --- TP702 / TP712 (B test points on the pump MT2 nets), west of the holder courtyards (their west edge is x 14.86; the pad edge keeps 1.06):
#     one B lane each to the B pour, between the F701.1 / F711.1 / F731.2 rings (2.6 creepage); the steam lane bends once to meet the lower pour
TRACKS += [
    (PUMP + 'PUMP_C_MT2', 'B', W_LOAD, [(13.3, 36.0), (25.5, 36.0)]),
    (PUMP + 'PUMP_S_MT2', 'B', W_LOAD, [(13.3, 25.4), (23.4, 25.4), (26.1, 22.7)]),
]
# --- VALVE_COM (pass 2, accepted form): K731.14 -> F731.1 on F; north run K731.14 -> K741.14 on B (x 42.6, jog 41.3)
TRACKS += [
    (VCOM, 'F', W_LOAD, [(45.46, 38.9), (43.16, 41.2), (38.8, 41.2)]),
    (VCOM, 'B', W_LOAD, [(45.46, 38.9), (42.6, 36.04), (42.6, 14.4), (41.3, 13.1), (41.3, 7.91), (45.46, 3.75)]),
]
# --- COFVALVE (PLAN3 COFVALVE (a), F2 width 0.3): J106 tab pair joined, one 45-degree leg, then ONE straight F lane y 45.6
#     between the F731 rings (bottom 42.8) and the JP303 rings (top 48.5 with JP303 pad 1 at y 50.0), ending on the K731.13 pad
TRACKS += [
    (COF, 'F', W_VALVE, [(4.46, 49.9), (9.54, 49.9), (13.84, 45.6), (44.46, 45.6)]),
]
# --- HOTVALVE (BRIEF J, R1): 0.3 mm (F2, one width), the J109 tab pair on F, then ONE In3 line from the J109.1 ring to the K741.13
#     ring (both through pads, no via): south of F711.1 (H3 10 mm zone and the F711.1 ring), the band y 25.2, one diagonal up west of
#     the pour's thick part, the lane y 15.24 above the steam MT2 via grid, one diagonal into K741.13 crossing the
#     PUMP_S_OPTO_MT In2 diagonal at a right angle
TRACKS += [
    (HOT, 'F', W_VALVE, [(4.46, 21.0), (9.54, 21.0)]),
    (HOT, 'In3', W_VALVE, [(9.54, 21.0), (13.74, 25.2), (18.0, 25.2), (27.96, 15.24), (40.32, 15.24), (45.46, 10.1)]),
]
# --- ZC_LED_A (BRIEF J, R1/R5/R8): U602.1 west stub on F, via ZC_V1, ONE In3 line west through the band under the NEUTRAL neck,
#     one diagonal to x 22.3, straight south between the JP303 rings to via ZC_V2 below R631.2, F stub up R631.2's long axis
TRACKS += [
    (ZCNET, 'F', W_ZC, [ZC_V1, (51.3, ZC_V1[1])]),
    (ZCNET, 'In3', W_ZC, [ZC_V1, (30.0, ZC_V1[1]), (22.3, ZC_V1[1] + 7.7), ZC_V2]),
    (ZCNET, 'F', W_ZC, [ZC_V2, (22.3, 56.18)]),
]
SMALL_VIAS = [(ZCNET, ZC_V1[0], ZC_V1[1]), (ZCNET, ZC_V2[0], ZC_V2[1])]
VIAS += SMALL_VIAS
# --- NEUTRAL taps (F rectangles joined to the In2 pour by vias)
ZONES += [
    (N_NEUTRAL, 'F', rect(50.1, 34.7, 51.25, 37.5), 'north T701.1 NEUTRAL tap'),
    (N_NEUTRAL, 'F', rect(51.05, 19.9, 52.05, 22.45), 'north T711.1 U602.2 NEUTRAL tap'),
]
VIAS += [(N_NEUTRAL, 50.55, 35.4), (N_NEUTRAL, 50.55, 36.25), (N_NEUTRAL, 50.55, 37.1),
         (N_NEUTRAL, 51.2, 20.5), (N_NEUTRAL, 51.2, 21.35)]
ZONES += [
    # one polygon: the F rectangle with the R704.1 MT2 patch (x 41.3..42.9, y 28.0..29.3) as its north-east arm, so no two zones overlap
    (PUMP + 'PUMP_C_MT2', 'F', [(24.2, 29.1), (41.3, 29.1), (41.3, 28.0), (42.9, 28.0), (42.9, 29.3), (41.5, 29.3), (41.5, 36.9), (24.2, 36.9)],
     'north PUMP_C_MT2 F'),
    (PUMP + 'PUMP_C_MT2', 'B', rect(24.3, 28.8, 39.6, 36.9), 'north PUMP_C_MT2 B'),
    (PUMP + 'PUMP_S_MT2', 'F', rect(33.3, 17.7, 41.5, 21.5), 'north PUMP_S_MT2 F'),
    (PUMP + 'PUMP_S_MT2', 'B', rect(24.3, 15.9, 39.6, 23.0), 'north PUMP_S_MT2 B'),
]
# --- BRIEF L: the pump snubbers are not fitted (R706, C701, R716, C711 and the copper of PUMP_C_SNUB / PUMP_S_SNUB are gone);
#     a bidirectional TVS clamp D701 / D711 (SMCJ400CA, SMC package) sits across each triac, MT2 to NEUTRAL, on the front in the
#     strip the capacitors freed.  Pad 1 is MT2, pad 2 is NEUTRAL as the schematic has it (part turned 180: symmetric, the pads stay where they were).  Ref, x, y, rotation, MT2 net.
DELETE_REFS = ("R706", "C701", "R716", "C711")
TVS_LIB = 'Diode_SMD'
TVS_NAME = 'D_SMC'
TVS_FIELDS = {"Value": "SMCJ400CA", "LCSC": "C151285", "MPN": "SMCJ400CA", "Manufacturer": "Littelfuse",
              "Rating": "400 V stand-off bidirectional TVS, 1500 W at 10/1000 us; VBR 447 to 494 V at 1 mA, VC 648 V at 2.3 A, IR 1 uA at VR; DO-214AB (SMC); Littelfuse SMCJ series datasheet revised 11/20/15", "Description": "Bidirectional transient-voltage-suppression diode"}
TVS = [("D701", 25.4, 12.07, 180.0, PUMP + 'PUMP_C_MT2'), ("D711", 29.6, 5.36, 180.0, PUMP + 'PUMP_S_MT2')]
# the F711 designator stood inside the freed C701 courtyard; it now sits west of D701, above the MAINS VOLTAGE legend
REF_TEXT_AT = {"F711": (14.5, 13.2)}
TRACKS += [
    # coffee: pad 2 (28.8, 12.4) straight south over the fuse area to the coffee F pour (its top edge y 29.1), no bend
    (PUMP + 'PUMP_C_MT2', 'F', W_LOAD, [(28.8, 12.07), (28.8, 29.6)]),
    # steam: pad 2 (33.0, 5.4) straight south, one 45-degree turn into the steam F pour's north-west corner (33.3, 17.7)
    (PUMP + 'PUMP_S_MT2', 'F', W_LOAD, [(33.0, 5.36), (33.0, 16.9), (33.9, 17.8)]),
]
# NEUTRAL taps of the two clamps: an F rectangle flush on pad 1 carrying two vias into the In2 pour
ZONES += [
    (N_NEUTRAL, 'F', rect(22.8, 10.6, 24.5, 13.1), 'north D701 NEUTRAL tap'),
    (N_NEUTRAL, 'F', rect(27.2, 4.0, 28.7, 6.8), 'north D711 NEUTRAL tap'),
]
VIAS += [(N_NEUTRAL, 24.0, 11.2), (N_NEUTRAL, 24.0, 12.6), (N_NEUTRAL, 28.1, 4.7), (N_NEUTRAL, 28.1, 6.1)]
HEAT_X = (33.8, 35.0, 36.2, 37.4)
VIAS += [(PUMP + 'PUMP_C_MT2', x, y) for x in HEAT_X for y in (30.0, 31.2, 32.4, 33.6, 34.8, 36.0)]
VIAS += [(PUMP + 'PUMP_S_MT2', x, y) for x in HEAT_X for y in (18.4, 19.6, 20.8)]

# ------------------------------------------------------------------------------------------------ MACHINERY
_TAG = 'sunbeam-em7000/main-board-v2/north3/'


def _uuid(item, *key):
    import pcbnew
    item.SetUuid(pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, _TAG + '/'.join(str(k) for k in key)))))


def _kiid(*key):
    import pcbnew
    return pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, _TAG + '/'.join(str(k) for k in key))))


def _swap_parts(board):
    """delete the unfitted snubber parts, add the two TVS clamps (idempotent)"""
    import pcbnew
    mm = pcbnew.FromMM
    for ref in DELETE_REFS:
        f = board.FindFootprintByReference(ref)
        if f is not None:
            board.RemoveNative(f)
    for ref, x, y, rot, mt2 in TVS:
        if board.FindFootprintByReference(ref) is not None:
            continue
        import neutral_pour
        stock = neutral_pour.stock_footprints()
        fp = pcbnew.FootprintLoad(os.path.join(stock, TVS_LIB + '.pretty'), TVS_NAME)
        if fp is None:
            raise SystemExit('footprint not found: ' + TVS_NAME)
        fp.SetFPID(pcbnew.LIB_ID(TVS_LIB, TVS_NAME))
        board.Add(fp)                      # on the board first, then position and fields
        fp.SetReference(ref)
        fp.SetValue(TVS_FIELDS["Value"])
        for fname in ("LCSC", "MPN", "Manufacturer", "Rating", "Description"):
            fp.SetField(fname, TVS_FIELDS[fname])
            fp.GetField(fname).SetVisible(False)
            fp.GetField(fname).SetLayer(pcbnew.F_Fab)
        fp.Value().SetVisible(False)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        for pad in fp.Pads():
            pad.SetNet(board.FindNet(N_NEUTRAL if pad.GetNumber() == '2' else mt2))
        fp.SetUuid(_kiid('footprint', ref))
        for i, item in enumerate(list(fp.GetFields()) + list(fp.Pads()) + list(fp.GraphicalItems())):
            item.SetUuid(_kiid('footprint-item', ref, i))


def apply_moves(board):
    import pcbnew
    mm = pcbnew.FromMM
    _swap_parts(board)
    for m in MOVES:
        f = board.FindFootprintByReference(m['ref'])
        if f is None:
            raise SystemExit('footprint not found: ' + m['ref'])
        f.SetOrientationDegrees(m['rot'])
        f.SetPosition(pcbnew.VECTOR2I(mm(m['x']), mm(m['y'])))
        if m['ref'] in TEXT_AT:
            tx, ty = TEXT_AT[m['ref']]
            f.Reference().SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
    for ref, (tx, ty) in REF_TEXT_AT.items():
        board.FindFootprintByReference(ref).Reference().SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
    t0 = board.FindFootprintByReference("TP702")
    t1 = board.FindFootprintByReference("TP712")
    if t0 is not None and t1 is not None:
        t1.Reference().SetTextAngle(t0.Reference().GetTextAngle())
    for ref, num, netname in PAD_NETS:
        f = board.FindFootprintByReference(ref)
        n = board.FindNet(netname)
        if f is None or n is None:
            raise SystemExit('pad swap: not found ' + ref + ' ' + netname)
        hit = [p for p in f.Pads() if p.GetNumber() == num]
        if len(hit) != 1:
            raise SystemExit('pad swap: pad %s.%s' % (ref, num))
        hit[0].SetNet(n)


def own_uuids():
    """the deterministic uuids of every track, via and zone this script draws"""
    keys = []
    for (nname, layer, width, pts) in TRACKS:
        for a, b in zip(pts, pts[1:]):
            keys.append(('track', nname, layer, a, b))
    for (nname, x, y) in VIAS:
        keys.append(('via', nname, x, y))
    for (nname, layer, poly, zname) in ZONES:
        keys.append(('zone', zname))
    return {str(uuid.uuid5(uuid.NAMESPACE_URL, _TAG + '/'.join(str(x) for x in k))) for k in keys}


def remove_own(board):
    """remove copper this script added earlier (by its deterministic uuid), so a re-run is idempotent"""
    own = own_uuids()
    mine = []
    for t in list(board.GetTracks()) + list(board.Zones()):
        if str(t.m_Uuid.AsString()) in own:
            mine.append(t)
    for t in mine:
        board.RemoveNative(t)


def build(board):
    import pcbnew
    mm = pcbnew.FromMM
    F, B, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu
    LAYER = {'F': F, 'B': B, 'In2': I2, 'In3': pcbnew.In3_Cu}
    def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))
    def net(name):
        n = board.FindNet(name)
        if n is None:
            raise SystemExit('net not found: ' + name)
        return n
    remove_own(board)
    for (nname, layer, width, pts) in TRACKS:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(mm(width)); t.SetLayer(LAYER[layer]); t.SetNet(net(nname))
            _uuid(t, 'track', nname, layer, a, b)
            board.Add(t)
    for (nname, x, y) in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        small = (nname, x, y) in SMALL_VIAS
        v.SetWidth(mm(0.6 if small else VIA_DIA)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net(nname))
        v.SetLayerPair(F, B)
        _uuid(v, 'via', nname, x, y)
        board.Add(v)
    for (nname, layer, poly, zname) in ZONES:
        if len(poly) < 3:
            raise SystemExit('zone with fewer than 3 points: ' + zname)
        z = pcbnew.ZONE(board)
        z.SetLayer(LAYER[layer]); z.SetNet(net(nname)); z.SetZoneName(zname)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetMinThickness(mm(0.2))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetLocalClearance(mm(3.0))
        ol = z.Outline(); ol.RemoveAllContours(); ol.NewOutline()
        for (x, y) in poly:
            ol.Append(mm(x), mm(y))
        _uuid(z, 'zone', zname)
        board.Add(z)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    src, dst = args
    sys.path.insert(0, HERE)
    import pcbnew
    import neutral_pour
    text_before = open(src, encoding='utf-8', newline='').read()
    board = neutral_pour.load_board(src)
    apply_moves(board)
    build(board)
    neutral_pour.add_neutral_pour(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    neutral_pour.save_board(board, dst, text_before)
    d = os.path.dirname(os.path.abspath(dst))
    shutil.rmtree(os.path.join(d, '.history'), ignore_errors=True)
    for f in os.listdir(d):
        if f.endswith('.kicad_prl'):
            os.remove(os.path.join(d, f))
    print('written', dst, 'track runs', len(TRACKS), 'vias', len(VIAS), 'zones', len(ZONES))


if __name__ == '__main__':
    main(sys.argv[1:])
