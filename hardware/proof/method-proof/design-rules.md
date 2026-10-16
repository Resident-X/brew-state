# Design rules of the method proof design

**NOT FOR MANUFACTURE.** Every design rule and net class `method-proof` uses, with its figure, where it is set in KiCad, where the figure comes from, and what stands behind it. The board is four layers at 1 oz finished copper, made by JLCPCB, as its constraints record `constraints.md` states. The manufacturer's limits are read from `docs/board-manufacturer-jlcpcb.md`, which records JLCPCB's rigid PCB capabilities page, https://jlcpcb.com/capabilities/pcb-capabilities, read on 2026-10-13, and its PCB Assembly FAQ (Part 2), https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, read on 2026-10-13. Each row quotes the figure as that record gives it.

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|
| Minimum clearance | 0.09 mm | Board Setup, Constraints (`min_clearance`) | MFG-1; JLCPCB capabilities page, *Traces*, "Min. track width and spacing (1 oz)": 0.09 mm / 0.09 mm (3.5 / 3.5 mil) for multilayer boards at 1 oz, read 2026-10-13 | not confirmed by step 3; enforced by the layout rule check in the pre-order check |
| Minimum track width | 0.09 mm | Board Setup, Constraints (`min_track_width`) | MFG-1; JLCPCB capabilities page, *Traces*, "Min. track width and spacing (1 oz)": 0.09 mm / 0.09 mm (3.5 / 3.5 mil) for multilayer boards at 1 oz, read 2026-10-13 | not confirmed by step 3; enforced by the layout rule check in the pre-order check |
