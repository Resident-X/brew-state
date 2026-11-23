# Assembler fitting of every part, heater wall board

**What this records.** The owner's decision of 2026-11-23 that JLCPCB fits all fourteen numbered parts of the heater wall board, in its Economic assembly mode, and the change it took: the six surface-mount parts U911, U921 (onsemi MOC3083SVM, C899868, SMDIP-6) and R911, R912, R921, R922 (UNI-ROYAL 1206W4F2000T5E, C18002) came out of hand fitting and into the position file. The eight through-hole parts J911, J921, J931, J941, RV911, RV921, T911 and T921 had been given to the assembler earlier the same day. H1 is a hole, not a part, and stays excluded. It replaces the bare-PCB order of 2026-11-19 (option A), under which the owner fitted every part by hand.

## What changed in the design

- **Board and library: attributes only.** `heater-wall-board.kicad_pcb`: the six footprints U911, U921, R911, R912, R921 and R922 lost `exclude_from_pos_files` (`(attr smd exclude_from_pos_files)` became `(attr smd)`); the six attribute lines are the whole diff of the board file. `heater-wall-board.pretty/SMDIP-6_W9.53mm_MOC3083SR2M.kicad_mod`: the library footprint lost the same attribute, and its description's "hand-fitted" became "fitted by the assembler". H1 keeps `(attr exclude_from_pos_files)`.
- **How the edits were made.** The library footprint was changed with Konnect's `set_footprint_metadata` tool. Konnect has no tool that sets a placed footprint's attributes alone: `update_footprints_from_library` would also have refreshed the six footprints' pads, graphics and models (its dry run listed those domains for all six, and U911 and U921 carry Mains-class pads), so it was not applied, and the six attribute lines of the board file were edited as text with the board closed in KiCad.
- **No copper, mask, drill, silkscreen or outline changed, and no fiducial was added.** The varistor footprints are unchanged.
- **Records.** `parts-specification.yaml` marks all fourteen numbered parts `fitted_by: assembler` and H1 `fitted_by: none`. `placement-overrides.yaml` holds the two recorded placement overrides for U911 and U921 (below). The `hand: true` flags came out of `sheets/*.yaml` and the `hand_fitted_refs` total out of `spec-tools/build_spec.py`, and `schematic-spec.yaml` was regenerated from them. The board's other records (fabrication notes, layout plan, layout hedges, open items, design rules, circuit proof, constraints figures, production-files check, ordering record, owner sign-off) carry dated amendment notes of 2026-11-23.

## The fiducial rule: a signed exception, not added fiducials

The project's pre-order rule `side_fiducials` (`MFG-10` of `docs/board-design-method.md`) asks for three fiducials on each side that carries assembled surface-mount parts. With the six parts in the position file, the front carries six and no fiducial. The board is not changed to add any; the owner's signed statement in `board-rules.yaml`, `assembler_fiducials`, takes the rule's line, and the pre-order check reports it as an `ACCEPTED` line with the reason, the source and the signature.

The ground is the manufacturer's own published words, read on 2026-11-23:

- JLCPCB, *PCB Assembly Capabilities*, https://jlcpcb.com/capabilities/pcb-assembly-capabilities: row *Fiducials*, Economic PCBA "Not necessary", Standard PCBA "Necessary"; row *Edge Rails*, Economic "Not necessary", Standard "Necessary"; row *Assembly Types*, Economic PCBA "Single sided placement (SMT/Thru-hole)".
- JLCPCB, *PCB Assembly FAQs*, item 12, https://jlcpcb.com/help/article/pcb-assembly-faqs: "Do I need to add fiducial marks myself? No, you don't have to. We'll add fiducial marks for SMT assembly."
- JLCPCB's guide *How to add edge rails/fiducials for PCB assembly order*, https://jlcpcb.com/help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order: "Edge rails and fiducials are required for standard PCB assembly at JLCPCB." It names no requirement for Economic assembly. None of the pages read offers an order option or a fee for fiducials.

`docs/board-manufacturer-jlcpcb.md` carried the capabilities row since 2026-10-13 and now quotes the FAQ item too.

**Signature.** `accepted_by`: Claude, on behalf of David Baker (owner), under his standing instruction of 2026-11-07; `accepted_on`: 2026-11-23 (`owner-sign-off.md` W-18, item 10 of the end-of-work list).

**Bound.** The exception holds for an Economic assembly order only. A Standard assembly order, whose table lists fiducials as necessary, needs the board changed. Adding fiducials was not taken: a fiducial is low-voltage copper and needs the board's 10 mm from Mains copper, which the 45 mm board does not have for three (`layout-plan.md` D2), and placing them would reopen the locked mains copper.

**The check's mechanism.** The pre-order check had no way to accept `side_fiducials` for a board (the workmanship acceptance record refuses the rule by name). The check now reads the optional `assembler_fiducials` mapping of a board rules record (`reason`, `source`, `accepted_by`, `accepted_on`, all required): a signed statement takes every `side_fiducials` line and reports each as accepted; an unsigned one (a blank or placeholder signer, an undated or future date) excuses nothing and each line still fails with the reason said; a signed statement on a board that lacks no fiducial fails as stale. The tests are in `hardware/tools/tests/test_board_marks.py` (`TheOwnersAssemblerFiducialsStatement`, which keeps the rule failing a board without the statement) and `hardware/tools/tests/test_board_rules.py` (`TheAssemblerFiducialsStatementIsRead`); `hardware/README.md` and the method's `MFG-10` describe it.

## Placement of the opto-triacs

The assembler's footprint for C899868 (fetched from the assembler's component service on 2026-11-23, kept outside the repository) has its two rows of pads 9.20 mm apart, centre to centre; the board's land, drawn to the MOC3083SVM sheet's 9.53 mm row pitch, has them 9.53 mm apart. The placement step matches pads by number and refuses a part whose pads land more than 0.1 mm off. The best fit by pad number puts every pad of the assembler's footprint 0.165 mm inward of the board's pad centre, across the rows (along the pad's 2.00 mm length), and none off along a row, so the two parts are placed through recorded overrides, each with its reason, in `placement-overrides.yaml`:

| Part | Row (x, y, rotation) | Residual | Pin 1 |
|---|---|---|---|
| U911 | 60.64, -50.19, 0 | 0.165 mm on every pad | the assembler's pad 1 on the board's pad 1 at board (58.10, 54.96) mm |
| U921 | 60.64, -66.21, 180 | 0.165 mm on every pad | the assembler's pad 1 on the board's pad 1 at board (63.18, 61.45) mm |

The residual is (9.53 - 9.20) / 2 = 0.165 mm. These rows are the ones the owner's test quote of 2026-11-23 used, and pin 1 agreed with JLCPCB's preview of it. The four resistors and the eight through-hole parts fit the assembler's footprints by themselves within 0.1 mm and take no override; the tool refuses an override for a part that fits.

## Checks of the change

- **Mains copper unchanged.** `python3 hardware/tools/locked_copper.py --kicad-cli "$KICAD_CLI" mains-compare --before-board <HEAD before the change>/heater-wall-board.kicad_pcb --before-project ... --board heater-wall-board.kicad_pcb --project heater-wall-board.kicad_pro --distance 7.0`: `RESULT | PASS | all 52 Mains-class items identical on both boards and no low-voltage copper nearer than 7 mm`. The 7.0 mm is the opto-triacs' accepted creepage exception (`owner-sign-off.md` W-14); the nearest low-voltage copper stands 7.53 mm from Mains copper, across U921's own rows, as before.
- **Layout rule check identical.** `kicad-cli pcb drc --format json --severity-all --schematic-parity --units mm`, on a copy of the board as committed before the change and on the changed board: 12 violations (all `clearance`, error), 0 unconnected items, 0 schematic parity issues on each, and the two lists identical item for item. The 12 are the board's standing clearance lines that the pre-order check judges against the board's own separation basis.
- **Pre-order check.** The heater wall board passes `task hw:verify`, with the `side_fiducials` line reported as `ACCEPTED` under `board-rules.yaml` `assembler_fiducials`; the result is recorded below.
- **Production files.** Generated from the committed design: placement full set 14 rows, surface-mount set 6 rows; parts list 6 catalogue numbers; H1 omitted as not a part to be fitted.

## Results of the gates

Recorded at the end of the change, below.

## What the owner acts on

- Order Economic assembly, not Standard (the board rests on JLCPCB adding its own fiducials).
- The order remark asking the assembler to seat T911 and T921 with the tab hole 17.25 mm above the board face (`ordering-record.md`; `open-items.md`, *Triac seating when the assembler fits the triacs*). The fitting order of `fabrication-notes.md` assumed the owner soldered the triacs after bolting their tabs to the plate; with the assembler fitting them, the seated height is the assembler's, and a triac whose tab does not meet the plate at 17.25 mm without force is refitted before the plate is bolted on.
- The opto-triacs are reflowed at JLCPCB's Economic peak of 255 +- 5 degC against the sheet's 260 degC soldering limit (`open-items.md`).
