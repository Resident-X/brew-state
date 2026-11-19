"""build_mains.py IN.kicad_pcb OUT.kicad_pcb   (KiCad's Python, -I; the board's .kicad_pro and .kicad_dru beside IN)

The whole mains routing chain of the Sunbeam EM7000 main board in one deterministic pcbnew run:
  1. every MOVES table (supply parts, C602 and the other measure-cluster parts, north parts from moves_north.json, then the north
     placement step: the unfitted pump snubber parts R706 C701 R716 C711 deleted, the TVS clamps D701 D711 added)
  2. entry copper (route_entry.py, without the pour)
  3. north copper (route_north.py: its MOVES and PAD_NETS again, then its copper)
  4. supply and measure copper (route_supply.py)
  5. the In2 NEUTRAL pour, rebuilt last (it cuts antipads round every through feature of every block)
  5b. unset the local clearance of the Mains zones a 3.0 clearance trims (neutral_pour.UNSET_CLEARANCE_ZONES)
  5c. cut back the outline of the Mains zones that reached into foreign copper's spacing (neutral_pour.RESHAPE_ZONES)
  6. fill every zone, assert every Mains-class zone fills at least 0.97 of its outline (prints the table), save, restore the ten
     board-level property lines

KICAD_FOOTPRINTS names KiCad's stock footprint libraries; it is read only when a part has to be taken from them.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402

import neutral_pour  # noqa: E402
import route_entry  # noqa: E402
import route_north  # noqa: E402
import route_supply  # noqa: E402


def apply_north_moves(board):
    for m in json.load(open(os.path.join(HERE, "moves_north.json"))):
        fp = board.FindFootprintByReference(m["ref"])
        assert fp is not None, m["ref"]
        fp.SetOrientationDegrees(m["rot"])
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(m["x"]), pcbnew.FromMM(m["y"])))


def main(argv):
    src, out = argv[1], argv[2]
    text = open(src, encoding="utf-8", newline="").read()
    board = neutral_pour.load_board(src)
    route_supply.apply_moves(board)
    apply_north_moves(board)
    route_north.apply_moves(board)   # placement step: the snubber parts out, the two TVS clamps in (before any copper)
    route_entry.build(board, pour=False)
    route_north.apply_moves(board)
    route_north.build(board)
    route_supply.build(board)
    neutral_pour.add_neutral_pour(board)
    neutral_pour.unset_tap_clearances(board)
    neutral_pour.reshape_outlines(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    neutral_pour.assert_mains_zones_fill(board)
    neutral_pour.save_board(board, out, text)


if __name__ == "__main__":
    main(sys.argv)
