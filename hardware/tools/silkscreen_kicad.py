#!/usr/bin/env python3
"""The silkscreen command's side that runs in KiCad's own interpreter.

Two workers, each run as `python -I silkscreen_kicad.py --worker NAME ARGS...` in
the interpreter that can `import pcbnew` (named by KICAD_PYTHON). They only read:

    extract BOARD OUT.json     every silkscreen ink item as KiCad's own stroke outline, each pad's
                               solder-mask opening, each drilled hole, each via, the board outline and
                               edge strokes, each footprint's courtyard and pad hull, and each zone's
                               outline, as millimetres in the board's own frame
    measure REQUESTS.json OUT.json
                               the stroke-font ink of each (text, size, thickness) asked for, centred on
                               the origin at reading angle 0, as outlines and a bounding box

The last line a worker prints is one JSON object. Nothing here is written to a board.
"""

from __future__ import annotations

import json
import sys


def _rings(polyset, to_mm):
    out = []
    for i in range(polyset.OutlineCount()):
        outline = polyset.Outline(i)
        ring = [[(to_mm(outline.GetPoint(k).x), to_mm(outline.GetPoint(k).y)) for k in range(outline.PointCount())]]
        for h in range(polyset.HoleCount(i)):
            hole = polyset.Hole(i, h)
            ring.append([(to_mm(hole.GetPoint(k).x), to_mm(hole.GetPoint(k).y)) for k in range(hole.PointCount())])
        out.append(ring)
    return out


def extract(board_path: str, out_path: str) -> dict:
    import pcbnew
    from pcbnew import ToMM, FromMM

    try:
        board = pcbnew.LoadBoard(board_path)
    except Exception as error:  # noqa: BLE001 - whatever KiCad raises is the board's reason
        return {"error": f"KiCad cannot load the board ({error})"}
    err = FromMM(0.002)
    outside = pcbnew.ERROR_OUTSIDE
    silk_layers = {pcbnew.F_SilkS: "F", pcbnew.B_SilkS: "B"}
    copper = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
    mask = {"F": pcbnew.F_Mask, "B": pcbnew.B_Mask}
    data = {"silk": [], "pads": [], "holes": [], "vias": [], "edge": [], "outline": [], "fps": {}, "zones": []}

    def polyset():
        return pcbnew.SHAPE_POLY_SET()

    outline = polyset()
    board.GetBoardPolygonOutlines(outline, True)
    data["outline"] = _rings(outline, ToMM)

    def text_item(text, owner, kind, side):
        ps = polyset()
        text.TransformTextToPolySet(ps, 0, err, outside)
        rings = _rings(ps, ToMM)
        if not rings:
            return
        position = text.GetPosition()
        data["silk"].append({
            "side": side, "owner": owner, "kind": kind, "text": text.GetShownText(True), "is_text": True,
            "size": ToMM(text.GetTextSize().x), "sizey": ToMM(text.GetTextSize().y),
            "thick": ToMM(text.GetTextThickness()), "ang": text.GetTextAngleDegrees(),
            "mirror": bool(text.IsMirrored()), "px": ToMM(position.x), "py": ToMM(position.y), "rings": rings})

    def shape_item(shape, owner, kind, side):
        ps = polyset()
        shape.TransformShapeToPolygon(ps, shape.GetLayer(), 0, err, outside)
        rings = _rings(ps, ToMM)
        if rings:
            data["silk"].append({"side": side, "owner": owner, "kind": kind, "text": "", "is_text": False,
                                 "width": ToMM(shape.GetWidth()), "rings": rings})

    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        side = "B" if footprint.GetLayer() == pcbnew.B_Cu else "F"
        position = footprint.GetPosition()
        record = {"side": side, "x": ToMM(position.x), "y": ToMM(position.y), "rot": footprint.GetOrientationDegrees(),
                  "lib": str(footprint.GetFPID().GetLibItemName()), "value": footprint.GetValue(),
                  "fields": {field.GetName(): field.GetText() for field in footprint.GetFields()},
                  "court": [], "padhull": []}
        try:
            record["court"] = _rings(footprint.GetCourtyard(pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd), ToMM)
        except Exception:  # noqa: BLE001 - a footprint without a courtyard has none
            pass
        data["fps"][ref] = record
        for field in footprint.GetFields():
            if field.IsVisible() and field.GetLayer() in silk_layers:
                text_item(field, ref, "field:" + field.GetName(), silk_layers[field.GetLayer()])
        for graphic in footprint.GraphicalItems():
            layer = graphic.GetLayer()
            if layer == pcbnew.Edge_Cuts:
                ps = polyset()
                graphic.TransformShapeToPolygon(ps, layer, 0, err, outside)
                data["edge"] += _rings(ps, ToMM)
            if layer not in silk_layers:
                continue
            if graphic.GetClass() == "PCB_TEXT":
                if graphic.IsVisible():
                    text_item(graphic, ref, "fptext", silk_layers[layer])
            else:
                shape_item(graphic, ref, "fpgfx:" + graphic.GetShapeStr(), silk_layers[layer])
        for pad in footprint.Pads():
            for s in "FB":
                if pad.IsOnLayer(copper[s]) and s == side:
                    ps = polyset()
                    pad.TransformShapeToPolygon(ps, copper[s], 0, err, outside)
                    record["padhull"] += _rings(ps, ToMM)
                if pad.IsOnLayer(mask[s]):
                    expansion = pad.GetSolderMaskExpansion(mask[s])
                    ps = polyset()
                    pad.TransformShapeToPolygon(ps, copper[s] if pad.IsOnLayer(copper[s]) else mask[s], expansion, err, outside)
                    data["pads"].append({
                        "side": s, "ref": ref, "pad": pad.GetNumber(), "net": pad.GetNetname(), "exp": ToMM(expansion),
                        "cx": ToMM(pad.GetPosition().x), "cy": ToMM(pad.GetPosition().y),
                        "w": ToMM(pad.GetSize(pcbnew.F_Cu).x), "h": ToMM(pad.GetSize(pcbnew.F_Cu).y),
                        "th": bool(pad.HasHole()), "rings": _rings(ps, ToMM)})
            if pad.HasHole():
                ps = polyset()
                pad.TransformHoleToPolygon(ps, 0, err, outside)
                data["holes"].append({"ref": ref, "pad": pad.GetNumber(), "net": pad.GetNetname(),
                                      "plated": pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH, "rings": _rings(ps, ToMM)})

    for drawing in board.GetDrawings():
        layer = drawing.GetLayer()
        if layer == pcbnew.Edge_Cuts:
            ps = polyset()
            drawing.TransformShapeToPolygon(ps, layer, 0, err, outside)
            data["edge"] += _rings(ps, ToMM)
        if layer in silk_layers:
            side, cls = silk_layers[layer], drawing.GetClass()
            if cls == "PCB_TEXT":
                text_item(drawing, "free", "freetext", side)
            elif cls == "PCB_TEXTBOX":
                text_item(drawing, "free", "freetextbox", side)
            else:
                shape_item(drawing, "free", "freegfx:" + (drawing.GetShapeStr() if hasattr(drawing, "GetShapeStr") else cls), side)

    for track in board.GetTracks():
        if track.GetClass() != "PCB_VIA":
            continue
        position = track.GetPosition()
        data["vias"].append({"x": ToMM(position.x), "y": ToMM(position.y), "dia": ToMM(track.GetWidth(pcbnew.F_Cu)),
                             "drill": ToMM(track.GetDrillValue()), "net": track.GetNetname(),
                             "exp": ToMM(track.GetSolderMaskExpansion()),
                             "tent_F": bool(track.IsTented(pcbnew.F_Mask)), "tent_B": bool(track.IsTented(pcbnew.B_Mask))})

    for zone in board.Zones():
        data["zones"].append({"name": zone.GetZoneName(), "rule": bool(zone.GetIsRuleArea()), "net": zone.GetNetname(),
                              "layers": [board.GetLayerName(layer) for layer in zone.GetLayerSet().Seq()],
                              "outline": _rings(zone.Outline(), ToMM)})
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return {"silk": len(data["silk"]), "pads": len(data["pads"]), "footprints": len(data["fps"])}


def measure(requests_path: str, out_path: str) -> dict:
    import pcbnew
    from pcbnew import ToMM, FromMM

    with open(requests_path, encoding="utf-8") as handle:
        requests = json.load(handle)
    board = pcbnew.BOARD()
    ink = {}
    for text, size, thick in requests:
        key = "%s|%s|%s" % (text, size, thick)
        if key in ink:
            continue
        item = pcbnew.PCB_TEXT(board)
        item.SetText(text)
        item.SetLayer(pcbnew.F_SilkS)
        item.SetTextSize(pcbnew.VECTOR2I(FromMM(size), FromMM(size)))
        item.SetTextThickness(FromMM(thick))
        item.SetPosition(pcbnew.VECTOR2I(0, 0))
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        ps = pcbnew.SHAPE_POLY_SET()
        item.TransformTextToPolySet(ps, 0, FromMM(0.002), pcbnew.ERROR_OUTSIDE)
        rings, xs, ys = _rings(ps, ToMM), [], []
        for ring in rings:
            for x, y in ring[0]:
                xs.append(x)
                ys.append(y)
        ink[key] = {"rings": rings, "bb": [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 0, 0]}
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(ink, handle)
    return {"measured": len(ink)}


if __name__ == "__main__" and sys.argv[1:2] == ["--worker"]:
    _name = sys.argv[2]
    print(json.dumps({"extract": extract, "measure": measure}[_name](sys.argv[3], sys.argv[4])))
