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

### What the board maker says about its laminate (read 2026-11-05)

- Capabilities page (https://jlcpcb.com/capabilities/pcb-capabilities): material "FR-4 Grade A laminates from suppliers including Nan Ya, KB, Shengyi and etc."; for HDI builds only, "Nan Ya NP-175F TG170 / Shengyi S1000-2M TG170". No laminate is named for a standard six-layer order and no CTI is stated.
- Materials page (https://jlcpcb.com/resources/pcb-material): names Rogers and Nan Ya as suppliers, offers a choice of standard multi-layer stackups and of TG value, and says nothing about choosing a laminate brand or about CTI. Its FAQ on custom material requirements answers, as far as the page reader returned it, that the customer should contact customer support.
- Certifications help page (https://jlcpcb.com/help/article/Certifications): no laminate datasheet link, no supplier name and no CTI statement in the text returned. A web-search summary said the page lists Nan Ya NP-140F and NP-155F, Shengyi S1000-2M and KB-6164 datasheets; the page reader could not confirm that, so it is not relied on.
- Help-centre pages for material datasheets (https://jlcpcb.com/help/article/PCB-Material-Datasheet) are script-rendered; fetched with curl they return only the page shell.
- The quote's default option read on 2026-10-13 (`docs/board-manufacturer-jlcpcb.md`) is "FR-4, TG 135-140", with no laminate maker or product.
- A customer question on the maker's forum (https://jlc3dp.com/help/answers/detail/961-What-material-group-according-to-UL-would-the-FR-4,-Nan-Ya-NP-140F,-PCB-boards-have) asks for the material group of "FR-4, Nan Ya NP-140F" and carries no answer.

### Laminate makers' own datasheets (read 2026-11-05)

Each figure is as printed, from the page shown, at the 1.6 mm specimen thickness the sheet states. The files were fetched with curl and read with pdftotext (and, for S1000-2, as a rendered image, since its text is outlines). These are copies hosted by distributors, not the makers' own sites; the revision is the one on the copy. The makers' sites could not be reached for current revisions, so "current document" in the requirement is not shown to be satisfied by any of these.

| Family | Document, revision as printed | Copy read | CTI as printed |
|---|---|---|---|
| Shengyi S1000-2M / S1000-2MB | "S1000-2M data sheet (20120321)" (file title), 3 pages | https://a-contract.ru/fileadmin/datasheets/base-material/S1000-2M.pdf; same text in the 2013-05 copy at https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/1023/S1000_2D00_2M-data-sheet.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "PLC3(175~250)", Typical Value "PLC3(200V)". The sheet says its data are typical values and not specification values. |
| Shengyi S1000-2 / S1000-2B | no revision printed; page "-31-" of a catalogue; file created 2009 | https://a-contract.ru/fileadmin/datasheets/base-material/S1000-2.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "PLC 3(175V--249V)", Typical "PLC 3". Remark 3: typical values are for reference. |
| Shengyi S1141 | no revision printed; file created 2003 | https://a-contract.ru/fileadmin/datasheets/base-material/S1141.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "-", Typical Value "175". No specification limit is printed, so 175 is a typical value with no guarantee. |
| Kingboard KB-6165F (lead-free series sheet) | "KB-616XF (Lead Free Series)", Version 2.0 / 2.1 (file dated 2012-04) | https://www.intectiv.si/wp-content/uploads/2023/08/Technical-data-sheet-KB-6165F-min.pdf | Purchasing Information table, page 3: column "CTI Value", "175V", beside the yellow base colour and the thickness and sheet-size rows. No test method is printed with it, and it is not in the General Properties table. |
| Kingboard KB-6165 | "KB-6165 Technical Information", Version 1.0 | https://a-contract.ru/fileadmin/datasheets/base-material/KB-6165.pdf | No CTI, tracking or IEC 60112 entry anywhere in the text. Not found. |
| Kingboard KB-6160 / KB-6164 | combined sheet KB-6160_6165_H140_150 (https://www.rezonit.ru/upload/spetsifikatsii/KB-6160_6165_H140_150.pdf) | the downloaded file was damaged (no readable cross-reference table) | Not read. A search summary said it gives "greater than 175 V"; that is not relied on. |
| Nan Ya NP-140TL (NP-140B on the same file) | Nan Ya data sheet, no revision date printed in the text | https://www.epectec.com/downloads/NAN-YA-NP140TL-Data-Sheet.pdf and https://www.mclpcb.com/wp-content/uploads/2021/05/NP-140TL.pdf | No CTI, tracking or IEC 60112 entry in either copy. Not found. NP-140F and NP-155F (the grades the maker's forum mentions) were not found in any datasheet that could be read. |

Reading of the figures against 175 V:

- Published at 175 V or above, as a range or typical value: S1000-2M (class PLC3, range 175 to 250, typical 200), S1000-2 (PLC 3, range 175 to 249), KB-6165F (175 V, no method printed), S1141 (175 V typical, no specification limit).
- Not published in the documents read: KB-6165, Nan Ya NP-140 family (NP-140TL sheet), KB-6160 and KB-6164 (sheet not readable).
- A published figure of exactly 175 V sits on the group boundary, with no margin: material group IIIa is CTI 175 to 399 (`separation-basis.yaml`). Only the S1000-2M and S1000-2 sheets print a class and a range that states 175 as the lower limit of PLC3.

### What the order can and cannot require

The maker's pages read give the customer a choice of stackup and TG value and nothing that selects the laminate maker or product. They name the families above as a pool ("Nan Ya, KB, Shengyi and etc."), not as an order option, and say custom material requirements go through customer support. Nothing read shows that a laminate brand can be written into the order form or a notes field and be honoured, or that the shipped brand is reported to the customer.

So: the order cannot be shown to require any laminate. The CTI of the laminate actually shipped is unverified, and could be any family in the pool, including ones whose published CTI was not found above.

Before ordering, the owner asks the maker's customer support, in writing, for: (1) the laminate maker and product that will be used for this six-layer 1.6 mm order, with that maker's datasheet; (2) confirmation that it can be fixed to one of the families above at order time, and the order-form field or note that does it (the order note to carry is: "laminate: Shengyi S1000-2M or S1000-2, CTI 175 V or more per IEC 60112; report any substitution before production"); (3) a material or conformance certificate for the shipped lot stating the CTI to IEC 60112, or the laminate maker's report. If the maker cannot fix the laminate or supply the certificate, the owner re-declares the basis (basis condition 3) before ordering.

### Status

Criterion C16 is **not met.** What is met: the notes cite laminate makers' published datasheets with a CTI of at least 175 for four families (S1000-2M, S1000-2, S1141, KB-6165F) and say which families publish none in the documents read. What is not met: the notes do not specify one laminate that the order can actually require (nothing read lets the customer require it); the copies cited are distributor-hosted, not confirmed as the makers' current revisions; and no certificate for the shipped lot exists. The criterion's own text puts choosing the laminate's supplier out of scope.

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
