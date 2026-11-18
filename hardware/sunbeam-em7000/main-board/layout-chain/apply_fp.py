"""apply_fp.py: make the board's F101 pads equal to the project library footprint (no board-only pad edit).

sync_footprint(board, ref="F101", libname="main-board"): reads the pad sizes (and shape, drill, position) of the
footprint file main-board.pretty/Fuse_SETfuse_SCT520PT_Axial_P28.0mm.kicad_mod in the board folder (the folder above this one) and sets them on the board footprint.
Run standalone:  apply_fp.py IN.kicad_pcb OUT.kicad_pcb   (KiCad python, -I)
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
FP_NAME = "Fuse_SETfuse_SCT520PT_Axial_P28.0mm"


def sync_footprint(board, ref="F101", libdir=os.path.join(os.path.dirname(HERE), "main-board.pretty"), name=FP_NAME):
    lib = pcbnew.FootprintLoad(libdir, name)
    assert lib is not None, (libdir, name)
    fp = board.FindFootprintByReference(ref)
    assert fp is not None, ref
    for lp in lib.Pads():
        bp = fp.FindPadByNumber(lp.GetNumber())
        assert bp is not None, lp.GetNumber()
        bp.SetSize(lp.GetSize())
        bp.SetDrillSize(lp.GetDrillSize())


def main(argv):
    src, out = argv[1], argv[2]
    sys.path.insert(0, HERE)
    import neutral_pour
    board = neutral_pour.load_board(src)
    sync_footprint(board)
    board.Save(out)


if __name__ == "__main__":
    main(sys.argv)
