# Brew State artifact generators (staged)

What this is: the scripts that built the Brew State web page's wall-board parts and its image and 3D data, the page itself, and the verified 3D placement corrections found while doing so (`placements.yaml`, hand-written).

| File | Does |
| --- | --- |
| `pack.py` | Repacks a `hardware/tools/glb_simplify.py` GLB into a compact deflated model the page decodes in the browser, losslessly (positions, triangles, colours unchanged). Main board model 2.12 MB, wall board 0.20 MB. |
| `build.py` | Builds the new page from the saved live version plus the wall-board part files and the layer masks |
| `build_page.py` | Replaces the page's embedded WebP images (renders, layer masks, silk, hero) with new ones |
| `conv.py` | Converts a board SVG into the page's themed inline form (class names for colours) |
| `layer_views_c.py` | Flat per-layer pictures of one board, using `hardware/tools/board_views.py`; needs KiCad, `resvg` and macOS `sips`. Environment: `BOARD_TOOLS` (the checkout's `hardware/tools`), `KICAD_CLI`, `WORK_DIR` (an existing scratch folder), optional `WIDTH_PX` |
| `masks.py` | Turns layer pictures into the page's colour masks |
| `hero.py` | Crops the 3200 x 2200 transparent render to its alpha box plus 30 px, resizes to 1600 wide and writes WebP |
| `placements.yaml` | The verified 3D placement corrections, and the hero render settings |
| `brew-state.html` | The page itself, 2.3 MB (under the 3 MB staging limit). It is the only master of the published artifact page: nothing else regenerates it from nothing. Whoever resolves this folder either keeps it as a tracked source (with the Artifact tool's publish as the way it reaches the reader) or rebuilds it from the scripts above and the tracked board files |

What it needs: Python 3 with Pillow and NumPy; KiCad 9 with `kicad-cli`; `resvg`; the tracked boards under `hardware/sunbeam-em7000/`; the 3D models fetched by `hardware/tools/fetch_3d_models.py`. The scripts take their paths as arguments. They were not re-run when staged.

Proposed permanent home: the generators in `hardware/tools/` (or a machine-record tooling folder) with a test on a synthetic board; `placements.yaml` merged into the model-fitting tool's table so the corrections stop living in the artifact pipeline; the page under the machine-record folder if kept as a source.

Known limitation recorded elsewhere: the corrections were applied only in the artifact pipeline. `hardware/tools/fetch_3d_models.py` still picks the 180 degree turn on symmetric parts; the maintenance item SOL-BOARD-MODEL-FITTING-PLACES-A-POLARISED-PART-ON-THE-SIDE-ITS-FOOTPRINT-MARKS covers it.
