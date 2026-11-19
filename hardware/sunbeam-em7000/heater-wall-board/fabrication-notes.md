# Fabrication notes: Sunbeam EM7000 heater wall board

What the board maker is asked to build, as the design records state it, and what is still open before the board is ordered. It carries the production-side statements the graph asks of this board (laminate, criterion C11; conformal coat, criterion C10 of `SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT`) and says plainly where the evidence for them is missing. It follows the main board's `fabrication-notes.md`, whose research it cites and does not repeat. Nothing here is signed or accepted by this file; the separation basis (`hardware/sunbeam-em7000/separation-basis.yaml`) is the owner's, and it names these notes as carrying the coat and the laminate preference for this board.

Maker figures are from JLCPCB's published capabilities page as `docs/board-manufacturer-jlcpcb.md` and `manufacturer-limits.yaml` hold them (read 2026-10-13 and 2026-11-05); the page was not read again for this file.

## Board

| Item | Statement | Source |
|---|---|---|
| Outline | a plain 45 x 76 mm rectangle with one 3.2 mm mounting hole (H1; the layout chose one, the printed case retaining the board with a ledge and fingers or lid ribs) and no ears, as narrow as the parts allow, its size set at layout and to stay inside the maker's 102 x 102 mm lowest price band (**amended 2026-11-19**: the earlier form's 57.0 x 42.5 mm body of 2422.5 mm2, 2662.5 mm2 with two mounting ears of a bracket, is not carried); the layout leaf draws the outline and the later case-design step the case and the plate | `docs/sunbeam-em7000/controller-board-division.md`, The heater wall board; leaf text |
| Copper layers | two: F.Cu and B.Cu | `manufacturer-limits.yaml` |
| Copper weight | 1 oz finished outer copper, the maker's introductory-price default | `board-rules.yaml` `fabrication.outer_copper_oz: 1`; `manufacturer-limits.yaml` |
| Thickness, surface finish, panel, tolerance and delivery options | not chosen in any record of this board; set at the quote | none |
| Parts | **amended 2026-11-19 (owner decision, option A): a bare-PCB order, every part fitted by hand by the owner, no assembly service.** Hand-fitted: T911, T921, J911, J921, J941 (through-hole), the two surface-mount opto-triacs U911 and U921 (onsemi MOC3083SR2M, C111561, gull-wing SMDIP-6 on `heater-wall-board:SMDIP-6_W9.53mm_MOC3083SR2M`, pads 2.00 x 1.50 mm, hand-soldered within the sheet's 260 degC limit; the earlier text named them through-hole DIP-6 parts), and the four 1206 gate resistors R911, R912, R921 and R922 (8 joints); eleven references carry `hand: true` in `schematic-spec.yaml`'s `hand_fitted_refs`; the two varistors and the header J931 are also fitted by hand, so all fifteen parts are. No fiducials, by design: nothing is placed by a machine, so nothing needs one. The position file lists nothing; the two varistors and the header J931 are the only other parts | `schematic-spec.yaml` totals |
| Controlled impedance | none asked | `manufacturer-limits.yaml` |

## Laminate and comparative tracking index

The requirement (C11): the notes prefer laminate families with a published comparative tracking index (CTI) of at least 175 (material group IIIa or better), as margin at pollution degree 2 and not as a precondition.

The separation basis credits pollution degree 2 on the material group III column, which covers groups IIIa and IIIb alike, so a laminate under 175 changes none of the basis's figures (`separation-basis.yaml`, condition 3). This board's laminate preference is therefore margin. It is the same preference as the main board's, and rests on the same research, which this file does not repeat: the main board's `fabrication-notes.md`, "Laminate and comparative tracking index" (read 2026-11-05) names the laminate makers' own datasheets and what the maker's pages say.

- **Preferred families, with a published CTI class and range of at least 175 (material group IIIa or better):** Shengyi S1000-2M / S1000-2MB (class PLC 3, specification "175~250", typical "200 V") and Shengyi S1000-2 / S1000-2B (PLC 3, "175 V to 249 V"), as the main board's notes record them from the laminate maker's sheets. A published figure of exactly 175 V sits on the group boundary with no margin; the notes say so.
- **The order note:** "laminate: Shengyi S1000-2M or S1000-2, comparative tracking index class PLC 3 (175 V or more) per IEC 60112; report any substitution before production". It is advice to the maker and not a requirement the maker is shown to honour: the maker's pages read on 2026-11-05 give a pool of laminate makers (Nan Ya, KB, Shengyi and others) and no way to fix one for an order.
- **What remains unverified, and is a pre-order action for the owner:** the identity and CTI of the laminate the maker will ship for this two-layer order, until the maker answers the written request the main board's notes set out (the laminate maker and product with its datasheet; whether it can be fixed to one of the two families; a certificate of the shipped lot). A two-layer order may use a different laminate from the six-layer one; the request is made for this order as for that one.

Status: criterion C11 is **met on paper**; the shipped laminate is **not verified**.

## Conformal coat

The requirement (C10): the notes name the coat that supports the basis's pollution degree 2 credit (which rests on the enclosure), with its type and the maker's current datasheet, state that it is applied after bring-up once the machine is deemed functional from a hardware perspective, and say where it is applied.

The coat is a supporting measure and earns no part of the pollution degree 2 credit, which stands on the enclosure (`separation-basis.yaml`, conditions 1 and 2). No coating test is planned and none is claimed.

### Coat chosen

The same coat as the main board, so that one can serves both boards: a one-part acrylic conformal coating in an aerosol can, sprayed at home with no equipment beyond a ventilated space, cured at room temperature, removable by a common solvent or by soldering through it.

- **Product: MG Chemicals 419D Acrylic Conformal Coating, aerosol, part number 419D-340G** (410 mL, 340 g net). **Fallback, equivalent type: Techspray Turbo-Coat Acrylic Conformal Coating, aerosol, product 2108-12S.**
- **The maker's current datasheet:** "419D Aerosol, Acrylic Conformal Coating", technical data sheet, 3 pages, dated 31 July 2025, Ver. 4.0, `https://mgchemicals.com/downloads/tds/tds-419d-a.pdf`, as the main board's notes cite it (fetched 2026-11-17 there; not fetched again here). The figures relied on (dielectric strength, service temperature -65 to 125 degC against the 70 degC air assumed and the 45 degC working figure at the wall, cure times, film thickness 25 to 75 um, rework by solder-through) are tabled there. The sheet states no creepage or clearance credit and no pollution degree, so none is taken; the cured film's chemical resistance is printed "Poor", so the enclosure and not the coat protects against solvent spills.
- **Flammability and supply:** the main board's notes carry the safety-data-sheet figures and the supply note; the owner reads the SDS packed with the can.

### Where and when it is applied

After bring-up, once the machine is deemed functional from a hardware perspective (owner, 2026-11-06). Until then the board is uncoated: the first connection of this board's mains side and the bring-up bench tests run on the uncoated board, in a clean room, and the coat is no part of the bound on any fault between mains pads until it is applied. The owner applies it at home.

It is applied to **both faces of the board**, covering the gaps between this board's mains pads: the pads of the nets `OUT_C`, `OUT_S`, `RET`, `HEAT_C_OPTO_MT`, `HEAT_S_OPTO_MT`, `HEAT_C_GATE_R`, `HEAT_S_GATE_R`, `HEAT_C_TRIAC_G` and `HEAT_S_TRIAC_G` (the Mains class) on the parts T911, T921, U911, U921, R911, R912, R921, R922, RV911, RV921, J911, J921 and J941, and in practice the whole board face except the keep-outs. The mains region is not yet drawn: the layout plan fixes it, and this paragraph is corrected to the drawn region when the layout is.

**Keep-outs for contacts, by reference designator** (proposed; confirmed against the drawn pads at layout):
- J911, J921 and J941: the blade contact surfaces and the push-on mating area (coat on a blade defeats the push-on contact).
- J931: the header's pins and the cable connector's mating area.
- T911 and T921: the insulated tab faces and the spreader plate's contact area under the compound and the M3 screw (the heat path and the bolted joint stay bare); the leads and pads are coated.
- U911 and U921: no keep-out; the surface-mount package is soldered to the pads and coated over (**amended 2026-11-19**; the earlier line allowed for sockets, which a surface-mount part does not take).

### Home application steps

As the main board's notes give them (clean with 99.9 % isopropyl alcohol, mask the keep-outs, spray 20 to 25 cm away at 45 degrees in thin coats rotating the board 90 degrees with 3 minutes between coats, 25 to 75 um, cure 24 hours at room temperature before power, inspect under a low-angle light for bare gaps between mains pads). Differences for this board: finish every bring-up repair and fit every hand-fitted part first (a later part is soldered through the film); the plate and triac mounting are done and the heat compound applied before coating, with the tab faces masked; the board's area, a plain rectangle set at layout inside the 102 x 102 mm band (the earlier form's 2422.5 mm2 a face was under 70 cm2), is to be kept under 70 cm2 for both faces together at layout, which the one can the main board uses covers many times over.

Status: criterion C10 is **met on paper**; no coating test is planned and none is claimed.
