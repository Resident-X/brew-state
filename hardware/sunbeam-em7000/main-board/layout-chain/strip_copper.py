"""strip_copper.py IN.kicad_pcb OUT.kicad_pcb   (KiCad's Python, -I; the board's .kicad_pro and .kicad_dru beside IN)

The placed board: the board with every track, via and zone the chain draws taken up -- the entry, north and supply blocks' mains
copper, the In2 NEUTRAL pour and the low-voltage reconnect -- and everything else left as it is (the parts, the hand-routed copper,
the ground pours, the silkscreen). The chain's other steps then draw that copper from the placed board. Each block names its own
copper in its own tables, so this takes up exactly what the block would draw and nothing else.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neutral_pour  # noqa: E402
import route_entry  # noqa: E402
import route_lv  # noqa: E402
import route_north  # noqa: E402
import route_supply  # noqa: E402


def main(argv):
    src, out = argv[1], argv[2]
    text = open(src, encoding="utf-8", newline="").read()
    board = neutral_pour.load_board(src)
    route_entry.remove_own(board)
    route_north.remove_own(board)
    route_supply.remove_own(board)
    route_lv.remove_own(board)
    neutral_pour.save_board(board, out, text)


if __name__ == "__main__":
    main(sys.argv)
