# Design rules of the heater wall board

Every design rule and net class the heater wall board uses, with its figure, where it is set in KiCad, where the figure comes from, and what stands behind it. The board is two layers at 1 oz finished outer copper, as `manufacturer-limits.yaml` states. The rows below are the two board-wide minimums set before placement, because the placement view takes its resolution from them; the other rows are written at the rules step, before any track is routed.

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|
| Minimum clearance | 0.1 mm | Board Setup, Constraints (`min_clearance`) | MFG-1; JLCPCB capabilities page, https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-11-05, as `manufacturer-limits.yaml` records it, *Tracks and spacing*, "Minimum track width and spacing": 0.10 mm for 1- and 2-layer boards at 1 oz | not confirmed by step 3; enforced by the layout rule check in the pre-order check |
| Minimum track width | 0.1 mm | Board Setup, Constraints (`min_track_width`) | MFG-1; JLCPCB capabilities page, https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-11-05, as `manufacturer-limits.yaml` records it, *Tracks and spacing*, "Minimum track width and spacing": 0.10 mm for 1- and 2-layer boards at 1 oz | not confirmed by step 3; enforced by the layout rule check in the pre-order check |
