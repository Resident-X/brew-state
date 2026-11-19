"""route_supply.py IN.kicad_pcb OUT.kicad_pcb

SUPPLY + MEASURE mains block for the Sunbeam EM7000 main board v2 (placement E4): the small re-placement of the supply parts (MOVES),
then LINE_MOD, ZC_N1, ZC_LED_A, VMEAS_N1/N2/DIV, the continuation of SHUNT_SENSE_NEUTRAL and the AMC measure cluster nets.
Run it AFTER route_entry.py (it routes against the entry copper); the last step of every chain is the NEUTRAL pour rebuild
(neutral_pour.add_neutral_pour), because the pour cuts antipads round every through feature of every block.

Adds only this block's tracks and vias, moves only the parts in MOVES, touches no copper of any net it does not list, refills
every zone, saves. Re-running on its own output replaces its own copper first. Board mm, x right, y down.

ZC_LED_A south part (R631.2 to the north block's In2 hand-over point (25.0, 44.0)) is not drawn by default: the only lane under the
COFVALVE lane runs down the 1.7 mm NEUTRAL neck between the JP303 antipads and would split the In2 pour (ZC_SOUTH_IN2 below, and NOTES3.md).
"""
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402

import neutral_pour  # noqa: E402

mm = pcbnew.FromMM
F, B, IN2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu
LAYERS = {"F": F, "B": B, "In2": IN2}

# ------------------------------------------------------------------------------------------------------------------ MOVES
# (reference, x, y, rotation in degrees): whole footprint, texts with it, same side. Position is the footprint origin
# (JP303 and RT301: pad 1; the 2512 resistors and the test point: the centre).
MOVES = [
    ("JP303", 17.25, 50.00, 0.0),      # pad 1 at (17.25, 50.0): 1.68 below the earlier site, so the COFVALVE lane passes above it
    ("RT301", 26.55, 61.63, 90.0),     # stands north-south: pad 2 (LINE_MOD) at (26.55, 54.13), pad 1 (LINE) at (26.55, 61.63); 1.68 down with JP303
    ("R631", 19.338, 56.18, 0.0),      # window west of RT301: pad 1 (ZC_N1) at 16.376, pad 2 (ZC_LED_A) at (22.3, 56.18); 1.68 down with JP303
    ("R630", 25.27, 65.70, 180.0),     # column x 25.27: pad 1 (LINE) right (28.232), pad 2 (ZC_N1) left (22.308); 1.68 down, 0.2 west
    ("R601", 25.27, 71.66, 180.0),     # pad 1 (LINE) right under R630.1, pad 2 (VMEAS_N1) left; 1.68 down, 0.2 west (keeps 2.6 to the U301.2 ring)
    ("R602", 25.27, 78.20, 0.0),       # pad 1 (VMEAS_N1) left, pad 2 (VMEAS_N2) right
    ("R603", 33.23, 78.20, 0.0),       # east of R602: pad 1 (VMEAS_N2) at 30.268, pad 2 (VMEAS_DIV) at 36.192
    ("TP603", 38.70, 80.00, 180.0),    # VMEAS_DIV test point (back side)
    ("C602", 55.30, 85.80, 90.0),      # measure cluster: 0.3 south, opens the AMC_HGND way out of C608.2
    ("TP606", 41.90, 80.40, 180.0),    # AMC_DCDC_HGND test point (back side): west end of its lane along y 80.4
    ("F602", 52.12, 79.3875, 270.0),    # bead HGND / DCDC_HGND on the FRONT in the pocket between C606 and C603 (pad 1 north at y 78.6 on the DCDC_HGND via row, pad 2 south)
    ("C606", 50.295, 80.33, 180.0),    # 0402 (see FOOTPRINT_SWAPS): pad 1 at (50.775, 80.33), 0.3 south, so the HLDO_IN via fits between C605.1 and C606.1; the courtyard leaves the pocket
    ("TP604", 46.00, 92.90, 180.0),    # AMC_AIN1P test point (back side): south-west site, reached by one B lane from the in-line via on the AIN1P lane
]

# value text of a moved part that would otherwise lie on a pad
TEXT_AT = {"JP303": (17.25, 52.68)}

# silk: texts moved off pads (free board text by its content, footprint reference by part)
FREE_TEXT_AT = {"LINK_MOD": (16.70, 53.48)}
REF_TEXT_AT = {"F731": (27.80, 44.00), "F602": (52.90, 74.50)}
REF_TEXT_ANGLE = {"F602": 0.0}

N = {
    "LINE_MOD": "/Logic supply/LINE_MOD",
    "ZC_N1": "/Zero-crossing detector/ZC_N1",
    "ZC_LED_A": "/Zero-crossing detector/ZC_LED_A",
    "N1": "/Supply voltage and current measurement/VMEAS_N1",
    "N2": "/Supply voltage and current measurement/VMEAS_N2",
    "DIV": "/Supply voltage and current measurement/VMEAS_DIV",
    "SSN": "/SHUNT_SENSE_NEUTRAL",
    "SSI": "/SHUNT_SENSE_IN",
    "AIN0P": "/Supply voltage and current measurement/AMC_AIN0P",
    "AIN0N": "/Supply voltage and current measurement/AMC_AIN0N",
    "AIN1P": "/Supply voltage and current measurement/AMC_AIN1P",
    "AIN1N": "/Supply voltage and current measurement/AMC_AIN1N",
    "HGND": "/Supply voltage and current measurement/AMC_HGND",
    "DCDC_HGND": "/Supply voltage and current measurement/AMC_DCDC_HGND",
    "HLDO_OUT": "/Supply voltage and current measurement/AMC_HLDO_OUT",
    "HLDO_IN": "/Supply voltage and current measurement/AMC_HLDO_IN",
}

VIA_SIZE, VIA_DRILL = 0.75, 0.30

# ZC_LED_A south part (R631.2 to the hand-over point (25.0, 44.0) on In2). Drawn only when ZC_SOUTH_IN2 is True: the lane has to go
# down the 1.7 mm neck between the JP303 antipads, the only link between the north and south pieces of the In2 NEUTRAL pour, and the
# pour keeps 3.0 mm round the lane, so drawing it splits the pour (NOTES3.md has the figures). False keeps the pour whole.
ZC_SOUTH_IN2 = False

ZC_VIA = (25.0, 44.0)    # In2 hand-over from the north block

# net, layer, width, [points]  (0 / 45 / 90 degrees only)
TRACKS = [
    # LINE_MOD 0.6: JP303.2 -> 45 degrees -> straight down RT301.2's axis (north pass 3's leg); RT301.2 -> 45 degrees down-right (135 degrees
    # from the leg), east, 45 degrees up into U301.1 on its centre
    ("LINE_MOD", "F", 0.6, [(27.25, 50.0), (26.55, 50.7), (26.55, 54.13)]),
    ("LINE_MOD", "F", 0.6, [(26.55, 54.13), (27.5, 55.08), (29.87, 55.08), (33.0, 51.95)]),
    # ZC_N1: R631.1 down its axis, 45 degrees, down R630.2's axis
    ("ZC_N1", "F", 0.3, [(16.376, 56.18), (16.376, 57.18), (22.308, 63.112), (22.308, 65.70)]),
    # VMEAS chain
    ("N1", "F", 0.3, [(22.308, 71.66), (22.308, 78.20)]),
    ("N2", "F", 0.3, [(28.233, 78.20), (30.268, 78.20)]),
    ("DIV", "F", 0.3, [(36.192, 78.20), (38.7, 78.20)]),
    ("DIV", "F", 0.3, [(38.7, 78.20), (41.1, 80.6), (44.175, 80.6)]),
]

VIAS = []

# ZC_LED_A south part, drawn when ZC_SOUTH_IN2: In2 lane from the hand-over point under the COFVALVE lane, down the neck beside JP303,
# one via at the south end of the neck, F leg down R631.2's axis
ZC_SOUTH_TRACKS = [
    ("ZC_LED_A", "In2", 0.25, [ZC_VIA, (25.0, 45.9), (22.3, 48.6), (22.3, 53.55)]),
    ("ZC_LED_A", "F", 0.25, [(22.3, 53.55), (22.3, 56.18)]),
]
ZC_SOUTH_VIAS = [("ZC_LED_A", 22.3, 53.55)]


# measure cluster (hand drawn lanes)
CLUSTER_TRACKS = [
    ('AIN0N', 'F', 0.25, [(51.645, 88.85), (57.0, 88.85)]),
    ('AIN0P', 'F', 0.25, [(51.645, 87.3), (53.3, 87.3)]),
    ('AIN0P', 'F', 0.25, [(53.3, 87.3), (53.8, 87.8), (57.0, 87.8)]),
    ('AIN1N', 'F', 0.25, [(51.645, 84.45), (55.3, 84.45)]),
    ('AIN1N', 'F', 0.25, [(55.3, 84.95), (57.0, 84.95)]),
    ('AIN1P', 'F', 0.25, [(51.645, 85.675), (54.2, 85.675), (55.15, 86.625)]),
    ('AIN1P', 'F', 0.25, [(55.5, 86.4), (57.0, 86.4)]),
    # AMC_AIN1P test point: in-line via on the lane, B lane west under the pad column, south down x 50.2, one 45-degree run to TP604
    ('AIN1P', 'B', 0.25, [(52.45, 85.675), (50.7, 85.675), (50.2, 86.175), (50.2, 88.7), (46.0, 92.9)]),
    ('HGND', 'F', 0.25, [(55.5, 82.565), (57.0, 82.565)]),
    ('HGND', 'F', 0.25, [(55.5, 82.875), (54.575, 83.8), (52.8, 83.8), (51.55, 82.55)]),
    # HGND at C605.2 / C606.2 / C607.2: column down C605.2's axis, 45 degrees into C606.2, down its axis, 45 degrees into C607.2; the via (48.3, 79.375) joins the column
    ('HGND', 'F', 0.25, [(49.025, 78.6), (49.025, 79.54), (49.815, 80.33)]),
    ('HGND', 'F', 0.25, [(49.815, 80.33), (49.815, 81.2), (50.515, 81.9)]),
    ('HLDO_OUT', 'F', 0.25, [(53.9, 81.6), (55.5, 81.6)]),
    ('HLDO_OUT', 'F', 0.25, [(55.5, 81.3), (57.0, 81.3)]),
    ('DCDC_HGND', 'F', 0.25, [(53.85, 78.475), (55.5, 78.475)]),
    ('DCDC_HGND', 'F', 0.25, [(55.5, 78.6), (57.0, 78.6)]),
    # AMC_DCDC_HGND: via beside C603.2 on the y 78.6 row, F bridge west into bead F602.1, B lane west along y 80.4 to TP606
    ('DCDC_HGND', 'F', 0.25, [(52.12, 78.6), (53.0, 78.6), (53.85, 78.6)]),
    ('DCDC_HGND', 'B', 0.25, [(53.0, 78.6), (52.0, 78.6)]),
    ('DCDC_HGND', 'B', 0.25, [(52.0, 78.6), (50.4, 78.6), (48.6, 80.4), (41.9, 80.4)]),
    # bead F602.2 (HGND, pad 2): straight down past the in-line HGND via (52.12, 81.1), one 45-degree run into C607.2
    ('HGND', 'F', 0.25, [(52.12, 80.175), (52.12, 81.5), (51.3, 82.32)]),
    # AMC_HLDO_IN to U601 pin 3 on B: C606.1 up its axis to an in-line via between C605.1 and C606.1, B east along y 79.55 under bead F602, 45 degrees down, via at the pin stub
    ('HLDO_IN', 'F', 0.3, [(50.775, 80.33), (50.775, 78.45)]),
    ('HLDO_IN', 'B', 0.3, [(50.775, 79.55), (55.3, 79.55), (55.775, 80.025), (56.405, 80.025)]),
    # HGND tie R604.2 / NT601 lane to the island: In2 east along y 79.375 from the existing via, via V_C, F stub into the C605/C606 lane
    ('HGND', 'In2', 0.25, [(45.825, 79.375), (48.3, 79.375)]),
    ('HGND', 'F', 0.25, [(48.3, 79.375), (49.025, 79.375)]),
    # Kelvin pair: SSN north lane ends in a via on its own lane, F lane down and into R608.1; SSI diagonal on In2 to a via in the row
    ('SSN', 'In2', 0.25, [(15.0, 80.7), (47.2, 80.7), (47.9, 81.4)]),
    ('SSN', 'F', 0.25, [(47.9, 81.4), (47.9, 83.3), (48.9, 84.3), (49.995, 84.3)]),
    ('SSI', 'In2', 0.25, [(15.0, 81.4), (45.5, 81.4), (48.8, 84.7), (48.8, 85.8)]),
    ('SSI', 'F', 0.25, [(48.8, 85.8), (49.995, 85.8)]),
    ('DIV', 'In2', 0.3, [(38.7, 78.2), (48.7, 78.2), (49.8, 79.3), (49.8, 86.3), (48.8, 87.3)]),
    ('DIV', 'B', 0.3, [(38.7, 78.2), (38.7, 80.0)]),
    ('DIV', 'F', 0.3, [(48.8, 87.3), (49.995, 87.3)]),
    ('HGND', 'F', 0.25, [(48.8, 88.8), (49.995, 88.8)]),
    ('HGND', 'In2', 0.25, [(48.8, 88.8), (51.55, 86.05), (51.55, 81.67), (52.12, 81.1)]),
    ('HLDO_OUT', 'F', 0.25, [(53.9, 80.9), (53.9, 81.4)]),
    ('HLDO_OUT', 'B', 0.25, [(53.9, 80.9), (53.9, 88.6), (52.9, 89.6), (51.9, 89.6), (48.7, 92.8)]),
    # HGND link NT601.2 -> R604.2 on In2 (third lane of the corridor, y 80.0)
    ('HGND', 'F', 0.25, [(14.2, 79.4), (13.6, 80.0), (13.0, 80.0)]),
    ('HGND', 'In2', 0.25, [(14.2, 79.4), (14.8, 80.0), (45.2, 80.0), (45.825, 79.375)]),
    ('HGND', 'F', 0.25, [(45.825, 79.375), (45.825, 80.6)]),
]

CLUSTER_VIAS = [
    ('DCDC_HGND', 53.0, 78.6), ('HGND', 48.3, 79.375), ('SSN', 47.9, 81.4), ('SSI', 48.8, 85.8),  ('DIV', 38.7, 78.2), ('DIV', 48.8, 87.3), ('HLDO_OUT', 53.9, 80.9), ('HGND', 48.8, 88.8), ('AIN1P', 52.45, 85.675), ('HGND', 52.12, 81.1), ('HLDO_IN', 56.405, 80.025), ('HLDO_IN', 50.775, 79.55), ('HGND', 14.2, 79.4), ('HGND', 45.825, 79.375),
]

# stale copper this block replaces: the baseline VMEAS_N2 link between the old R602 / R603 positions
STALE = [
    ("N2", "F", (32.25, 78.0), (31.0, 78.0)),
    # the start board's AMC_HLDO_IN lane east of C606.1 along y 79.62 (the pocket belongs to bead F602 now); the lane to U601 pin 3 runs on B
    ("HLDO_IN", "F", (50.775, 80.03), (50.775, 78.45)),
    ("HLDO_IN", "F", (51.18, 80.03), (50.775, 80.03)),
    ("HLDO_IN", "F", (51.59, 79.62), (51.18, 80.03)),
    ("HLDO_IN", "F", (55.99, 79.62), (51.59, 79.62)),
    ("HLDO_IN", "F", (56.4, 80.03), (55.99, 79.62)),
]


def det_uuid(item, *key):
    item.SetUuid(pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL, "sunbeam-em7000/main-board-v2/supply/" + "/".join(str(k) for k in key)))))


def _key(a, b=None):
    return (round(a[0], 3), round(a[1], 3)) if b is None else tuple(sorted(((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)))))


BACK_SIDE = ()

# part, library, footprint, fields that follow the footprint (1n 50V X7R 10% in 0402: LCSC C1523, FH 0402B102K500NT)
FOOTPRINT_SWAPS = [
    ("C606", "Capacitor_SMD", "C_0402_1005Metric", {"Rating": "X7R 50V 10% 0402", "MPN": "0402B102K500NT", "Manufacturer": "FH", "LCSC": "C1523"}),
]


def swap_footprints(board):
    """Replace a board footprint by another library footprint, keeping net, path (schematic link), fields, text layers. Idempotent."""
    for ref, lib, name, fields in FOOTPRINT_SWAPS:
        old = board.FindFootprintByReference(ref)
        assert old is not None, ref
        if str(old.GetFPID().GetLibItemName()) == name:
            continue
        new = pcbnew.FootprintLoad(os.path.join(neutral_pour.stock_footprints(), lib + ".pretty"), name)
        assert new is not None, (lib, name)
        new.SetFPID(pcbnew.LIB_ID(lib, name))
        new.SetReference(ref)
        new.SetValue(old.GetValue())
        for f in old.GetFields():
            fname = f.GetName()
            if fname in ("Reference", "Value"):
                continue
            new.SetField(fname, fields.get(fname, f.GetText()))
            nf = new.GetField(fname)
            nf.SetVisible(f.IsVisible())
            nf.SetLayer(f.GetLayer())
        new.SetPath(old.GetPath())
        for p in new.Pads():
            p.SetNet(old.FindPadByNumber(p.GetNumber()).GetNet())
        det_uuid(new, "footprint", ref)
        for i, item in enumerate(list(new.GetFields()) + list(new.Pads()) + list(new.GraphicalItems())):
            det_uuid(item, "footprint-item", ref, i)
        for tn in ("Reference", "Value"):
            ot, nt = getattr(old, tn)(), getattr(new, tn)()
            nt.SetLayer(ot.GetLayer())
            nt.SetVisible(ot.IsVisible())
            nt.SetTextSize(ot.GetTextSize())
            nt.SetTextThickness(ot.GetTextThickness())
        board.RemoveNative(old)
        board.Add(new)


def apply_moves(board):
    swap_footprints(board)
    for ref, x, y, rot in MOVES:
        fp = board.FindFootprintByReference(ref)
        assert fp is not None, ref
        if ref in BACK_SIDE and fp.GetLayer() == F:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        if ref in [sw[0] for sw in FOOTPRINT_SWAPS]:
            fp.Reference().SetPosition(fp.GetPosition())
            fp.Value().SetPosition(pcbnew.VECTOR2I(mm(x), mm(y + 1.43)))
        if ref in TEXT_AT:
            tx, ty = TEXT_AT[ref]
            fp.Value().SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
    for ref, (tx, ty) in REF_TEXT_AT.items():
        board.FindFootprintByReference(ref).Reference().SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
    for ref, ang in REF_TEXT_ANGLE.items():
        board.FindFootprintByReference(ref).Reference().SetTextAngleDegrees(ang)
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() in FREE_TEXT_AT:
            tx, ty = FREE_TEXT_AT[d.GetText()]
            d.SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))


STALE_RULE_AREAS = ("PUMP_S_OPTO_MT via pour pull-back_1",)


def remove_stale_rule_areas(board):
    """The start board carries a pull-back rule area for a PUMP_S_OPTO_MT via that no longer exists; delete it (idempotent)."""
    for z in list(board.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName() in STALE_RULE_AREAS:
            board.RemoveNative(z)


def remove_own(board):
    seg_keys = set()
    for key, layer, w, pts in TRACKS + CLUSTER_TRACKS + ZC_SOUTH_TRACKS:
        for a, b in zip(pts, pts[1:]):
            seg_keys.add((N[key], layer, _key(a, b)))
    for key, layer, a, b in STALE:
        seg_keys.add((N[key], layer, _key(a, b)))
    via_keys = {(N[k], _key((x, y))) for k, x, y in VIAS + CLUSTER_VIAS + ZC_SOUTH_VIAS}
    for t in list(board.GetTracks()):
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            if (t.GetNetname(), _key((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))) in via_keys:
                board.RemoveNative(t)
        else:
            s_, e_ = t.GetStart(), t.GetEnd()
            lname = {F: "F", B: "B", IN2: "In2"}.get(t.GetLayer(), "?")
            k = _key((pcbnew.ToMM(s_.x), pcbnew.ToMM(s_.y)), (pcbnew.ToMM(e_.x), pcbnew.ToMM(e_.y)))
            if (t.GetNetname(), lname, k) in seg_keys:
                board.RemoveNative(t)


def add_track(board, key, layer, width, a, b):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    t.SetWidth(mm(width))
    t.SetLayer(LAYERS[layer])
    t.SetNet(board.FindNet(N[key]))
    det_uuid(t, "track", key, layer, a, b)
    board.Add(t)


def add_via(board, key, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(VIA_SIZE))
    v.SetDrill(mm(VIA_DRILL))
    v.SetLayerPair(F, B)
    v.SetNet(board.FindNet(N[key]))
    det_uuid(v, "via", key, x, y)
    board.Add(v)


def build(board):
    """Apply MOVES, replace this block's copper. Does not fill and does not touch the NEUTRAL pour."""
    remove_own(board)
    remove_stale_rule_areas(board)
    apply_moves(board)
    for key, layer, w, pts in TRACKS + CLUSTER_TRACKS + (ZC_SOUTH_TRACKS if ZC_SOUTH_IN2 else []):
        for a, b in zip(pts, pts[1:]):
            add_track(board, key, layer, w, a, b)
    for key, x, y in VIAS + CLUSTER_VIAS + (ZC_SOUTH_VIAS if ZC_SOUTH_IN2 else []):
        add_via(board, key, x, y)


def save_board(board, out, props_from_text):
    """SaveBoard twice (must be identical), re-insert the ten board-level property lines, write OUT."""
    import filecmp
    import tempfile
    tmp = tempfile.mkdtemp(prefix="supply_save_")
    a, b = os.path.join(tmp, "a.kicad_pcb"), os.path.join(tmp, "b.kicad_pcb")
    pcbnew.SaveBoard(a, board)
    pcbnew.SaveBoard(b, board)
    assert filecmp.cmp(a, b, shallow=False), "two saves differ"
    props = re.findall(r'\n\t\(property "[A-Z_0-9]+" "[^"\n]*"\)', props_from_text[:props_from_text.index("\n\t(footprint ")])
    assert len(props) == 10, len(props)
    txt = open(a, encoding="utf-8", newline="").read()
    first = txt.index("\n\t(footprint ")
    head = re.sub(r'\n\t\(property "[A-Z_0-9]+" "[^"\n]*"\)', "", txt[:first])
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(head + "".join(props) + txt[first:])
    for p in (a, b):
        os.remove(p)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


def main(argv):
    src, out = argv[1], argv[2]
    text = open(src, encoding="utf-8", newline="").read()
    board = neutral_pour.load_board(src)
    build(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    save_board(board, out, text)


if __name__ == "__main__":
    main(sys.argv)
