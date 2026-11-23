# Order record, heater wall board

**Status of this file:** the order-time record of this board for `SOL-HW-CONTROLLER-BOARDS-ORDERED`, written ahead of the order. Every row marked **pending** or **OWNER ACT** has not been done: nothing here is a preview, a quote, a manufacturer's answer or a confirmation, and none was made up. The preview, the quote, the laminate answer, the via-finish answer, the order and the payment are the owner's or the manufacturer's-account acts, and the rows name each. Beside this file: `production-files-check.md`, the per-part and per-layer judgement against the preview.

## Production files and the manufacturer's preview (SOL-HW-CONTROLLER-BOARDS-ORDERED.C1)

Both boards ride in one order and one parcel, so each board's preview is judged on its own and the quote and the running total are weighed once for both. The part-by-part table and the layer table of this board are in `production-files-check.md` beside this file; payment waits until every row of both boards' tables matches.

The files are generated from the committed design with the method's ordering step (`kicad-cli pcb export pos`, then `production_files.py fetch-footprints`, `placement` and `parts-list`, each writing a full set and a surface-mount set, then `kicad-cli pcb export gerbers` and `drill`, and `production_files.py render`) and are never edited by hand.

| Item | State |
|---|---|
| Production files exported from the commit | **pending**: export from the commit the layout review closed on; record it in `production-files-check.md` (Board judged) |
| Assembler's footprints fetched (`fetch-footprints`, outside the repository) | **pending**: run on the order date |
| Order-date availability record, `availability-record.yaml` beside this file (written from the assembler's catalogue search service on the order date; both commands refuse to run without it) | **pending**: not written; the order date is not yet set |
| Placement file, both sets, each part in the assembler's footprint frame | **pending**: run `placement --unavailable availability-record.yaml`; a part it refuses is recorded as an override with its reason |
| Parts list, both sets | **pending**: run `parts-list --catalogue catalogue-extract.yaml --unavailable availability-record.yaml`; each row's comment is the one the catalogue extract holds for its number, and a number with no entry or no comment, or held twice, fails it |
| Assembler's preview, each side, and its placement preview | **OWNER ACT, not done**: upload the archive, the placement file and the parts list to the manufacturer's order page and go no further than its preview; save the images with the date |
| Every placed part's row compared with the preview; every layer row | **pending the preview** |
| Rotation direction and origin convention the preview shows | **pending the first real preview**; recorded with that board's check in `production-files-check.md` |
| Quote of the order (both boards) | **OWNER ACT, not done**: the quote shown at upload, with its date; none has been read |
| Declared spend | 250 USD (`docs/sunbeam-em7000/component-specification.md`) |
| Running total before this order | 0 USD bought to date; block-level estimate of the first order 149.68 USD (`docs/sunbeam-em7000/controller-board-cost-estimate.md`) |
| Quote against the running total | **pending the quote**: running total after the order = running total before + the quote; entered in the component specification's running-total table and weighed against 250 USD before payment |

**Why this board's assembler sets hold all fourteen numbered parts.** On 2026-11-23 the owner decided that JLCPCB fits every numbered part of the board, in its Economic assembly mode: the eight through-hole parts (J911, J921, J941, J931, RV911, RV921, T911, T921), which he had first asked for that day to see the quote and check their fitment in the preview, and the six surface-mount parts (U911, U921, R911, R912, R921, R922). The six had been excluded from the position file for hand fitting; the exclusion was taken off them (`assembler-fitting-record.md`) and all fourteen are `fitted_by: assembler` in `parts-specification.yaml`; H1 is a hole, `fitted_by: none`, and the production-files step omits it. The placement step needs the recorded overrides of `placement-overrides.yaml` for U911 and U921 (the assembler's footprint for C899868 has its rows 9.20 mm apart against the board's 9.53 mm). The board carries no fiducials: JLCPCB lists them as not necessary for Economic assembly and adds its own, which the signed exception `board-rules.yaml` `assembler_fiducials` records (`owner-sign-off.md` W-18); a Standard assembly order would need the board changed. This replaces the bare-PCB order of 2026-11-19 and the cost estimate's owner-fit assumption (`docs/sunbeam-em7000/controller-board-cost-estimate.md`: the wall board fabricated only, with no assembly order), under which `parts-list` wrote 0 rows for this board.

## The order-date catalogue read (SOL-HW-CONTROLLER-BOARDS-ORDERED.C3)

Read the manufacturer's public catalogue on the order date for each part below, which the board design accepted below the rating it needs, and record what is found against each before payment. A part found in stock that meets the rating is brought to the schematic leaf as an amendment before the board is ordered. No read has been made: the criterion asks for the order date, and a read made earlier would not state it.

| Position | Catalogue number | Part as drawn | Rating needed | What to look for | Found at the order date (source, read date) |
|---|---|---|---|---|---|
| T911, T921 with U911, U921 | C10065 with C899868 | BTA16-800BWRG triac with MOC3083SVM opto-triac, both 800 V | an 800 V triac and opto-triac pair that is in stock | confirm both numbers are in stock at the order date; no replacement is sought where they are | **pending**: not read |

The limit this board's records state for each figure a part's maker does not publish, read on 2026-11-22 against `bring-up-provision.md` and the accepted exceptions of `derating-policy.yaml`: the four gate resistors R911, R912, R921 and R922 (no pulse rating stated by the sheet) are held in accepted exceptions at 178.9 V, signed by the owner on 2026-11-19; the retained blades and push-on joiners (no maker rating) are held in the bring-up row of the same name, whose limit is a rise of at most 40 K over the surrounding air (the 110 degC cap less the 70 degC air assumed), and the opto-triac neighbour rise is held against the 85 degC ambient limit on the maker's page. Each states its limit and carries it to a bring-up measurement. Confirmed on that date: no figure read there lacks a limit. What stays **pending** is only the order-date catalogue read of the table above, which the criterion dates to the order.

## Via finish (SOL-HW-CONTROLLER-BOARDS-ORDERED.C4)

The board has 2 copper layers. The via sizes it uses, counted on 2026-11-22 from the `(via ...)` items of the committed `heater-wall-board.kicad_pcb` with the repository's s-expression reader (`hardware/tools/sexpr.py`), the copper layers counted from the file's `layers` list (each count is also asserted by `hardware/tools/tests/test_ordering_records.py`):

| Via diameter / hole (mm) | Count |
|---|---|
| 0.70 / 0.30 | 1 |

The wall board is two layers, so the six-layer filling default does not apply, and the quote's default options (`docs/board-manufacturer-jlcpcb.md`, *The quote's default options*) name the smallest via and not the finish of a 0.70 mm via. **The pages read do not state the finish of its one 0.70 / 0.30 mm via**: it needs the manufacturer's written answer before payment.

| Via diameter / hole | Finish the manufacturer states | Source | Read on |
|---|---|---|---|
| each size above | **pending**: a page of the manufacturer's capabilities, or its support's written answer, stating the finish | | |

A diameter whose finish is not stated is reported here and the order is not paid for until it is.

## Laminate (SOL-HW-CONTROLLER-BOARDS-ORDERED.C5)

The separation basis reads the material group III column at pollution degree 2, which covers groups IIIa and IIIb alike, so a comparative tracking index certificate is not a precondition to payment. The basis is the signed record `hardware/sunbeam-em7000/separation-basis.yaml` and is not restated here.

**Written request to the manufacturer's support (OWNER ACT: send, then record the date):**

> Please state the laminate maker and product (the core and prepreg family and the TG grade) that will be used for the order the owner names when sending this request and, if you hold one, a certificate or test report of that laminate's comparative tracking index to IEC 60112. We do not need the certificate to proceed.

**Laminate note carried on the order (OWNER ACT: paste into the order's remarks, record the date):** the laminate line of this board's `fabrication-notes.md`.

| Item | Date | State |
|---|---|---|
| Request sent | | **pending, owner** |
| Laminate note on the order | | **pending, owner** |
| Manufacturer's answer, or the absence of one | | **pending**; record the text with its source and date |

An answer naming a laminate whose published comparative tracking index is below 100, which falls in no material group, is reported here and the order is not paid for until the owner re-declares the basis; so is a pollution degree 3 fallback taken without an index of 175 or more recorded.

## Pin functions (SOL-HW-CONTROLLER-BOARDS-ORDERED.C9)

The board places no controller; the two channels crossing its three-way header J931 are the far channels heat_c_drv and heat_s_drv, each read at the controller pin the main board's record gives it. Each channel is read at the pin the board gives it in the pin allocation record, against the function the main board's controller pin table lists for that pin (`main-board/controller-pin-table.md`, DS12110 Rev 11 Table 9, LQFP100 column). The reading was made on the commit that holds this file; every channel below carries its function, so none stops the order. Whether the firmware's own tables spell the same pin is the firmware-side check's, after the order. The crystal pins (HSE and LSE) and the serial-wire output are not firmware channels and are not listed.

| Channel | Pin | Function the pin table lists | Function the channel needs | Carries it |
|---|---|---|---|---|
| heat_c_drv | PD11 | GPIO output | plain output | yes |
| heat_s_drv | PD12 | GPIO output (I2C4_SCL, LPTIM1_IN1 not used) | plain output | yes |

## The placed order (SOL-HW-CONTROLLER-BOARDS-ORDERED.C8)

Filled in after the owner reports the order placed; placing the order and paying are the owner's acts and receipt is the received-boards leaf's.

| Item | Record |
|---|---|
| Manufacturer's order confirmation (number and date) | **pending, owner** |
| Set of production files uploaded (full or surface-mount, with the placement file's and parts list's names) | **pending, owner** |
| Fitting choice taken (who fits the parts) | **Taken by the owner on 2026-11-23: the assembler fits all fourteen numbered parts, Economic assembly mode; recorded in `parts-specification.yaml`.** Upload the full set (`parts-list-full.csv` and `placement-full.csv`, 14 rows each in placement, 6 catalogue numbers in the parts list); the surface-mount-only set holds the six surface-mount parts and is not the choice. Choose Economic, not Standard, assembly: the board carries no fiducials and rests on JLCPCB adding its own for Economic (`board-rules.yaml` `assembler_fiducials`). |
| Order remark for the triacs | **none** (settled 2026-11-24): the assembler seats T911 and T921 as its line does; the owner drills the plate's tab holes after delivery, at the height the delivered triacs stand (owner, 2026-11-24), in a short vertical slot or a hole about 1 mm oversize so that the bolted tab puts no load on the soldered leads; see `open-items.md`, *Triac seating when the assembler fits the triacs*. The tab-hole height measured on the delivered board: **pending** |
| Cost of the assembly the owner chose | **pending the quote.** The cost estimate's basis (`docs/sunbeam-em7000/controller-board-cost-estimate.md`, the heater wall board) had no assembly at the manufacturer; the owner's choice of 2026-11-23 adds that board's own assembly charges (setup, stencil, Extended feeder loading, through-hole soldering) that the estimate does not price, read from the quote. **Pending, owner** |
| Cost paid | **pending, owner** |
| Running total after this order (entered in the component specification) | **pending** |
