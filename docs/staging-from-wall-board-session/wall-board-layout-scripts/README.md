# Wall board layout scripts (staged)

What this is: the scripts that made the heater wall board's later layout changes, each a text edit of the board file (everything not named is kept as it was), plus KiCad-python helpers that measure the result. The `CHANGES-*.txt` files are each pass's before and after of the geometry it moved.

What it needs: Python 3; KiCad's bundled Python for every script that imports `pcbnew` or refills zones (`analyse.py`, `measure.py`, `silk_copper.py`, and the `--fill` step of `edit_pass2.py`, `edit_final.py`, `edit_r7.py`). Those three edit scripts hold a `KPY` constant at the top naming that interpreter at KiCad's standard macOS location: change it for another install. `build_basis.py` needs PyYAML. `verify_one.py` needs a checkout of the repository (`--root`) and `kicad-cli` (`--kicad-cli` or the `KICAD_CLI` environment variable). The board's `.kicad_pro` and `.kicad_dru` must sit beside the input board with the same stem for the edit scripts. The scripts were last run against the boards at the commits below and were not re-run when staged.

Proposed permanent home: edit scripts that are specific to one board's geometry (`edit_pass2.py`, `edit_final.py`, `edit_r7.py`, `edit_silk.py`, `add_legend.py`, `build_basis.py`) beside the wall board, as build scripts of that board; generic measures and filters (`silk_copper.py`, `analyse.py`, `measure.py`, `widen_silk.py`, `widen_lib.py`, `verify_one.py`) in `hardware/tools/`, each with a test on a synthetic board.

| Script | Does | Produced commit |
| --- | --- | --- |
| `edit_pass2.py` (+ `CHANGES-pass2.txt`) | Rewrites the four output-copper zone outlines, moves the mains warning silk block, refills those zones in KiCad and transplants only their fill | 48d2bbdd (critical routing pass 2) |
| `add_legend.py` | Inserts the front silk legend, logo, maker line and coat keep-out marks as new top-level text | d7fe8e5e (logo and maker line), 3d6b5b12 (legend and coat keep-outs on the assembly layer) |
| `edit_silk.py` | Moves named silk items by uuid and inserts two new texts, each edit asserting a single match | 7588acbd (front silk repositioned, back-side placeholder), 60c665fc (round 3 silk) |
| `widen_silk.py`, `widen_lib.py` | Widen every silk stroke under 0.15 mm to 0.15 mm in the board and in the board's footprint library | 8ee00b84 |
| `edit_final.py` (+ `CHANGES-final.txt`) | Critical routing pass 3: fills the wedge in the front output zone, straightens the U921 pin 4 track, centres the +5V_WB via | 361c0406 |
| `edit_r7.py` (+ `CHANGES-r7.txt`) | Critical routing pass 4: straightens the output band edge, moves the blade legends and the RV921 reference off copper edges | 56660c80 |
| `silk_copper.py` | Census of silk against the copper of its own face | used for the silk census of the production-files check, no board change |
| `analyse.py` | Geometry census of zones (angles, islands, necks, edge distance) and silk boxes | used for the geometry check of passes 3 and 4, no board change |
| `measure.py` | Nearest-obstacle gap of every new front silk item | used for the silk rounds 2 and 3, no board change |
| `build_basis.py` | Builds the wall board's proposed separation-basis record from the shared record's figures | the wall board's separation basis (proposed, unsigned form; its `--sign` option writes a throwaway signature for structure tests only and must never be used on a delivered record) |
| `verify_one.py` | Runs the pre-order check on one design of a clone | no board change |

Overlaps with the scripted-layout-tools leaf (SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD, finished): that leaf tracks `hardware/tools/silkscreen.py` (with its table), `chain_runner.py`, `kicad_scripting.py`, `locked_copper.py` and `footprint_audit.py`. These scripts overlap it in three places. Silk placement here is by hand-written uuid edits where the leaf's silkscreen command places by engine: after reconciliation `edit_silk.py` and `add_legend.py` should be expressed as that command's table or dropped. `silk_copper.py` and `measure.py` overlap the silkscreen legality measures. The zone-outline edit plus transplanted refill of `edit_pass2.py`, `edit_final.py` and `edit_r7.py` overlaps the leaf's safe refill and fill difference, and each is a candidate chain step. Whoever resolves this folder reads the leaf's tools first and keeps only what they do not do.
