# Fabrication notes: Sunbeam EM7000 main controller board

What the board maker is asked to build, as the design records state it at the commit that adds this file, and what is still open before the board is ordered. It carries the production-side statements the graph asks of the main board (laminate, coat) and says plainly where the evidence for them is missing. Nothing here is signed or accepted; the separation basis (`hardware/sunbeam-em7000/separation-basis.yaml`) is itself unsigned at this commit (`accepted_by` and `accepted_on` empty, its 98 accepted exceptions unsigned).

Maker figures are from JLCPCB's published capabilities page (https://jlcpcb.com/capabilities/pcb-capabilities), re-read on 2026-11-05 and held in `manufacturer-limits.yaml` and `docs/board-manufacturer-jlcpcb.md`. Where this file says the maker publishes nothing, that is what the pages read on 2026-11-05 held, not a statement about the maker's practice.

## Board

| Item | Statement | Source |
|---|---|---|
| Outline | 131.0 x 125.0 mm | `manufacturer-limits.yaml` header |
| Thickness | 1.6 mm (offered at six layers; 2.5 mm and over is reserved for 12 layers and more) | `design-rules.md` Stackup row; `manufacturer-limits.yaml` |
| Copper layers | six, in this order from the component side: F.Cu (components, signals); In1.Cu (solid `GND` plane, nothing routed); In2.Cu (`GND` fill, permitted signals, and the `Mains`-class routes inside the `mains` region); In3.Cu (signals); In4.Cu (`GND` fill, slow nets only, never `Fast`, `Sense`, supply or `Mains`); B.Cu (tracks, `GND` pour, test pads) | `design-rules.md` Stackup row |
| Copper weight | 1 oz finished outer copper (the weight a standard multilayer order carries without a surcharge); inner copper 0.5 oz, the maker's default for a multilayer board, taken as is | `board-rules.yaml` `fabrication.outer_copper_oz: 1`; `manufacturer-limits.yaml` |
| Surface finish | ENIG. The maker does not offer HASL at six layers or more; OSP is the other offered finish and is not chosen | `manufacturer-limits.yaml` header; `design-rules.md` Stackup row |
| Controlled impedance | none asked | `manufacturer-limits.yaml` header |
| Panel, tolerance and delivery options | not chosen in any record; set at the quote | none |

## Vias and drills

| Via | Count in the placed board | Annular width | Use |
|---|---|---|---|
| 0.6 mm pad, 0.2 mm drill | 338 | 0.20 mm (the maker's recommended figure) | signal vias |
| 0.5 mm pad, 0.2 mm drill | 222 | (0.5 - 0.2) / 2 = 0.15 mm (the maker's absolute minimum, below its 0.20 mm recommendation) | non-critical slow nets |
| 0.75 mm pad, 0.3 mm drill (the count includes 15 of 0.7 mm pad, 0.3 mm drill) | 541 | 0.225 mm | ground, supply and mains vias |

Counts are those of `design-rules.md`, "Via sizes in the layout", read from the board file. Every drill (0.2 or 0.3 mm) is over the maker's 0.15 mm minimum drill, and every via pad is at least 0.10 mm over its hole. The board setup's minimum annular width is 0.15 mm for the 0.5 / 0.2 mm via; the deviation from the recommended 0.20 mm is unsigned, for the owner (`design-rules.md`, Minimum annular width; `layout-plan.md` MFG-1). No via of under 0.45 mm pad diameter with a 0.2 mm drill is placed, so the maker's extra charge for that size does not arise.

## Laminate and comparative tracking index (graph criterion C16)

The requirement: the notes specify a laminate whose published comparative tracking index (CTI) is at least 175 (material group IIIa or better), the figure the basis's material group rests on, and cite the laminate maker's current document for it. A laminate below 175, or one with no such document cited, is reported and the owner re-declares the basis before the board is ordered.

What is known, read 2026-11-05:

- The maker's capabilities page (https://jlcpcb.com/capabilities/pcb-capabilities, fetched with curl and again through a page reader) states the material as "FR-4 Grade A laminates from suppliers including Nan Ya, KB, Shengyi and etc." and, for HDI builds only, "Nan Ya NP-175F TG170 / Shengyi S1000-2M TG170". It names no laminate for a standard six-layer order and states no CTI, no tracking-index class and no laminate datasheet.
- The maker's help-centre pages for materials and material datasheets (https://jlcpcb.com/help/article/PCB-Material-Datasheet and neighbours) are script-rendered: fetched with curl they return only the site's generic page shell, with no laminate or CTI content. No CTI figure was readable from any page of the maker.
- The quote's default option read on 2026-10-13 (`docs/board-manufacturer-jlcpcb.md`) is "FR-4, TG 135-140", still without a laminate maker or product.

Status: **criterion C16 is not met.** No laminate is chosen, no laminate maker's document is cited, and no CTI figure has been read, so none is written here. What is missing: the laminate the maker will use for this order (the quote or the maker's support can name it, and it may differ by order), and that laminate maker's current datasheet stating its CTI. Until both are cited and the figure is 175 or more, the owner must treat the pollution degree 2 / material group IIIa reading as unsupported on the laminate condition (basis condition 3) and re-declare the basis if the figure is lower or cannot be found. The criterion's own text puts choosing the laminate's supplier out of scope.

## Conformal coat (graph criterion C17)

The requirement: the notes name the coat that supports the basis's pollution degree 2 credit (which rests on the enclosure), with its type and the maker's current datasheet, and state that it is applied before the board is energised in the machine and covers the gaps between the board's mains pads, except keep-outs for contacts listed by reference designator.

Status: **criterion C17 is not met.** What the records say, in full:

- The coat is planned, applied after the boards work (`docs/sunbeam-em7000/reference-machine.md`), as a supporting measure that does not itself earn the pollution degree 2 credit; the credit stands on the enclosure (`separation-basis.yaml` conditions 1 and 2).
- No coat type is chosen and no coat datasheet is cited anywhere in the repository. No keep-out list exists. No coating test is planned and none is claimed (`layout-plan.md` ENV-1 row).
- Stated here as the requirement the owner is to confirm: the coat is applied before the board is first energised in the machine, covers the gaps between the board's mains pads, and leaves uncovered only contacts whose reference designators are listed in this file. The list is empty at this commit because no keep-out has been decided; which parts need a keep-out (for example any contact a plug or probe must reach bare) is the owner's decision, each listed here by designator once decided.
- Applying the coat and choosing its supplier are out of scope of the criterion. The bring-up humidity step (DEL-HW-BRING-UP) is the only check planned after it.

## Mask, silkscreen and assembly

No record chooses a solder mask colour or a silkscreen colour. The maker's quote defaults read on 2026-10-13 are green mask and white silkscreen; a colour other than green, red, yellow, blue or purple has a wider minimum mask bridge (black and white, 0.13 mm against 0.10 mm), so any change to a colour is a decision for the quote. The board's designators are on F.SilkS (and B.SilkS for the test pads). Assembly options (side, count, which parts) are in `parts-specification.yaml` and the cost estimate, not here.

## Unresolved before ordering

Both are unresolved in the records and must be checked at the quote, not assumed:

1. **Finish of vias over 0.55 mm at six layers.** The maker fills and plates over vias of 0.15 to 0.55 mm diameter by default at six layers and above; the page says nothing about a via over 0.55 mm. The board has 338 vias of 0.6 mm and 541 of 0.7 and 0.75 mm, all over that range; the 222 of 0.5 mm are inside the filled range.
2. **The six-layer engineering and board fee and the ENIG charge at 131 x 125 mm.** Only the quote reads them; the cost estimate carries an estimate, not a quote.

## Unsigned deviations carried by this board

Every one of these is a recorded draft for the owner, not an acceptance, and none changes a signed figure (there is none: the basis is unsigned). They are held, with their measurements, in the open rows of `layout-plan.md` ("Open after the fix rounds") and in `layout-review.md`; this file points to them and does not restate them.

- The 0.15 mm annular width of the 0.5 / 0.2 mm via (above).
- The mains-to-mains spacing shortfalls, the 98 draft spacing exceptions of the basis, and the detour ratios of routed critical nets (`layout-plan.md` open rows, including the standing mains items row).
- The plated-hole pairs at 1.25 mm, the pour gaps under 0.09 mm, the back-side assembled parts without a fiducial, and the other open rows of that section.
- The three `footprint_symbol_mismatch` parity entries for R522, R572 and R576 (do-not-populate set on the board footprints, not on the schematic symbols; `open-items.md`, flow meter output type).
