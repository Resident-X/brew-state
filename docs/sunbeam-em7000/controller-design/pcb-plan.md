# PCB plan

Written 2026-10-12. This is a recommendation, not a decision (D21 in `decisions.md`), and it is the starting input for the discussion of what the graph should hold for an AI-assisted PCB manufacture method.

## Position

A low-voltage-only prototype PCB, hand-soldered through-hole, rather than building the whole controller on perfboard. The board carries: the H743 module on four 1x22 female header pieces, the five sensor dividers (4.7 kOhm low-TCR, 100 nF), the ULN2003A breakout, the 74HCT541 (DIP-20 in a socket), the two 2N5401 stages with their resistors, the key-line series resistors, the connectors, and the pull-ups and pull-downs. The mains parts stay off-board and are wired by harness: the SSRs, the dimmers, the relay module, the IRM-10-5 on its carrier, the BL0942 modules and the inlet chain.

## Why

- About 37 assigned pins, about 40 passives and at least 8 connectors; hand-wiring is a few hundred joints.
- The 16-bit ADC front end targets 0.05 to 0.2 C noise (estimate) and wants controlled grounding and short traces next to dimmer and SSR switching.
- The machine vibrates and cycles in heat.
- This repository is open source and meant to be rebuilt elsewhere; Gerbers and a schematic can be rebuilt, hand-wired perfboard cannot.

## Why not placed assembly on the first spin

The BOM is through-hole with no assembler part numbers or footprints, the harness connector types are unidentified, and the design will probably change once. Use bare boards and hand-solder; move to surface-mount parts and a placed assembly for repeat builds. Prices and assembler libraries have not been looked up.

## Footprints: what is known

| Part | Status |
|---|---|
| H743 headers | Known: 2 columns x 22 rows per long edge at 2.54 mm; columns 2.54 mm apart; inner columns 33.02 mm, outer 38.10 mm apart; first row 6.77 mm from each end; mounting holes 3.1 mm on 35.56 x 61.38 mm centres; a separate 4-pin SWD header; board 40.64 x 66.88 mm (WeAct BoardShape V12 drawing) |
| 74HCT541, DIP-20 socket | Standard (2.54 mm pitch, 7.62 mm row spacing) |
| 2N5401 | TO-92, standard |
| Resistors, capacitors | Axial or radial through-hole, standard |
| ULN2003A breakout | Unknown (dimensions and header pitch not measured; AliExpress board) |
| Harness connectors (panel, gauge, flow meter, thermistors, sensors) | Unknown (types unidentified, pin 1 untraced) |
| RBdimmer modules | 50 x 16 mm with terminals; off-board |
| Relay module | 73 x 54 mm (4-channel); off-board |
| IRM-10-5 | Off-grid pins (38.5 mm between columns, 10.75 mm AC L to AC N, 8 mm between outputs); off-board |

## Before layout (cheap checks that change the schematic)

The seven datasheet and bench checks in `open-items.md` section B that bear on pins, and the panel meter checks in section A item 6.

## What a Staircase solution for this would need

(Reasoned from the project's own tasks and skills; the engine's ability to run a non-firmware verification command is unconfirmed.)

- A verification gate beside the firmware gate: run `kicad-cli` ERC and DRC, check that the exported netlist matches `h743-pin-allocation.csv` and the firmware's hardware-seam channel list, and check the exported BOM against `control-system-bom.csv`, as tests carrying the project's trace comments.
- Requirements stating outcomes, not mechanism; "KiCad" belongs in the solution, not in a requirement.
- CI that provides KiCad in a pinned container, SHA-checked like the rest of CI.
- A decision on the repository layout (a hardware directory) and whether Gerbers are committed.
- A home for physical build and bring-up evidence: the graph cannot hold a solution awaiting an operator's build (a gap named in the old working README); bench bring-up would be demonstration evidence.
- Reading `DEL-COMPONENT-SPECIFICATION.C6` (regenerate the specification and purchase list from the graph), which the old `component-specification.md` and `controller-io.md` name as a later criterion and which has not been read in this session.

## Order

Measure the H743 header and the ULN2003A breakout, identify the harness connectors, close the pin checks, then author the solution and its gate, then lay out and order a prototype spin. Mains-side work is a separate step with a safety review.
