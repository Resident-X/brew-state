"""chamfer_corners.py IN.kicad_pcb OUT.kicad_pcb [TABLE.json]   (KiCad's Python, -I; the board's .kicad_pro and .kicad_dru beside IN)

Cuts the 90 degree corners of the Mains zones named in chamfer_corners.json at 45 degrees, then refills every zone, checks the Mains
zones still fill and saves. The table holds, for each zone's name, each corner to cut as [x, y, leg]: the corner's position in board
millimetres and the length of the two equal legs the cut takes off its edges. A corner is cut where the table names it and nowhere
else, so an inside corner that cutting would load with copper, or a corner a spacing holds, is left square by leaving it out. A cut only
takes copper away, so no clearance the zone held is lost. A zone or corner the board does not carry stops the run, naming it.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402

import neutral_pour  # noqa: E402

def cut_outline(points, corners, zone_name):
    """The zone's outline points (integer nanometres) with each table corner replaced by its two cut points."""
    left = list(corners)
    result = []
    count = len(points)
    for index, (x, y) in enumerate(points):
        hit = [c for c in left if abs(pcbnew.FromMM(c[0]) - x) <= 1 and abs(pcbnew.FromMM(c[1]) - y) <= 1]
        if not hit:
            result.append((x, y))
            continue
        left.remove(hit[0])
        leg = pcbnew.FromMM(hit[0][2])
        for other in (points[index - 1], points[(index + 1) % count]):
            length = math.hypot(other[0] - x, other[1] - y)
            if length <= leg:
                raise SystemExit("zone '%s': the corner at %s, %s has an edge no longer than its %s mm leg" % (zone_name, pcbnew.ToMM(x), pcbnew.ToMM(y), hit[0][2]))
            result.append((x, y, other, length))
        # the cut point on the edge to the previous vertex first, then the one on the edge to the next vertex
        for k in (-2, -1):
            _, _, other, length = result[k]
            result[k] = (x + int(round((other[0] - x) * leg / length)), y + int(round((other[1] - y) * leg / length)))
    if left:
        raise SystemExit("zone '%s' has no corner at %s" % (zone_name, ", ".join("(%s, %s)" % (c[0], c[1]) for c in left)))
    return result


def main(argv):
    src, out = argv[1], argv[2]
    table_path = argv[3] if len(argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "chamfer_corners.json")
    table = json.load(open(table_path))
    text = open(src, encoding="utf-8", newline="").read()
    board = neutral_pour.load_board(src)
    for name, corners in table.items():
        zones = [z for z in board.Zones() if z.GetZoneName() == name]
        if len(zones) != 1:
            raise SystemExit("the board carries %d zones named '%s', and the chamfer table needs exactly one" % (len(zones), name))
        zone = zones[0]
        outline = zone.Outline()
        if outline.OutlineCount() != 1 or outline.HoleCount(0) != 0:
            raise SystemExit("zone '%s' is not one outline without holes" % name)
        chain = outline.Outline(0)
        points = [(chain.CPoint(i).x, chain.CPoint(i).y) for i in range(chain.PointCount())]
        new_points = cut_outline(points, corners, name)
        outline.RemoveAllContours()
        outline.NewOutline()
        for x, y in new_points:
            outline.Append(x, y)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    neutral_pour.assert_mains_zones_fill(board, out=open(os.devnull, "w"))
    neutral_pour.save_board(board, out, text)


if __name__ == "__main__":
    main(sys.argv)
