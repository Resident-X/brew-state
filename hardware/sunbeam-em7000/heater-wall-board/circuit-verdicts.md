# Circuit verdicts: Sunbeam EM7000 heater wall board

This is the skeleton of the record in the form of the main board's `circuit-verdicts.md`: every part, every net and every sheet of `schematic-spec.yaml` is listed once, with the catalogue items of `docs/board-design-method.md` that bear on it (items PINV, PARTS, CAPD, BUSL, STRAP, RCFL, SUPPLY, POLAR, CABLE, FAULT, INDEP, BARRIER, SURGE, ESD, TOUCH, EMSRC, DERATE, DRAW). **No verdict is written here: every row reads "not yet reviewed"**, and the review rounds fill the verdict column (PASS, N/A or FINDING; a FINDING is closed by a change to the sheets, by a recorded reason, or is held by the owner and listed in `open-items.md`). The arithmetic the rounds judge against is in `circuit-proof.md`; the facts about the bring-up path are in `bring-up-provision.md`.

The board has 5 sheets (the four drawn sheets and the root sheet), 14 parts and 16 nets as the netlist writes them (the 12 named nets of `schematic-spec.yaml` and the 4 `unconnected-` nets of the two opto-triacs' pins 3 and 5, written by the netlist as `unconnected-(U911-NC-Pad3)` and the like; amended 2026-11-18, the record had `-Pad3`). Its references are the 9xx series, chosen so that none equals a reference of the main board or of the separation basis's exceptions (`schematic-spec.yaml`, drawing notes). It places no controller, no ground net and no test point.

| Group | PASS rows | FINDING rows | N/A rows | Not yet reviewed |
|---|---|---|---|---|
| Parts | 0 | 0 | 0 | 14 |
| Nets | 0 | 0 | 0 | 16 |
| Sheets and the board | 0 | 0 | 0 | 10 |
| Total | 0 | 0 | 0 | 40 |

## Board-level items

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| Whole board | DERATE-1, DERATE-2 | not yet reviewed | `derating-policy.yaml`, `circuit-proof.md` (grading every part against the enclosure air) |
| Whole board | DRAW-1 | not yet reviewed | the drawn sheets against the convention of `schematic-spec.yaml` `drawing` |
| Root sheet | DRAW-1 | not yet reviewed | the root sheet: one sheet symbol per drawn sheet, a title naming the board |
| Whole board | BARRIER-1 | not yet reviewed | the heater-switch barrier (`separation-basis.yaml`): the opto-triacs U911 and U921 and the board spacing; the gate-resistor pairs the basis does not list (`open-items.md`) |
| Whole board | FAULT-1, CABLE-1, INDEP-1 | not yet reviewed | `circuit-proof.md` rows (b2) and (c); the cable-loose checks of `bring-up-provision.md` |
| Whole board | SURGE-1 | not yet reviewed | `circuit-proof.md` row (d) and owner decision D7 |

## Sheet 1. Coffee heater switch

### Parts

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| T911 (BTA16-800BWRG, C10065) | PINV-1, PARTS-1, DERATE-2, POLAR-1, BARRIER-1 | not yet reviewed | |
| U911 (MOC3083M, C23552) | PINV-1, PINV-2, PARTS-1, STRAP-1, SUPPLY-2, POLAR-1, INDEP-1, FAULT-1, BARRIER-1, DERATE-2 | not yet reviewed | |
| R911 (200 ohm 1206) | PINV-1, DERATE-2, FAULT-1, SURGE-1 | not yet reviewed | |
| R912 (200 ohm 1206) | PINV-1, DERATE-2, FAULT-1, SURGE-1 | not yet reviewed | |
| RV911 (07D471K) | PINV-1, SURGE-1, DERATE-2, TOUCH-1 | not yet reviewed | |
| J911 (blade TAB_OUT_C) | PINV-1, CABLE-1, DERATE-2 | not yet reviewed | |

### Nets

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| OUT_C (Mains) | PINV-1, SURGE-1, TOUCH-1 | not yet reviewed | |
| HEAT_C_OPTO_MT (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_C_GATE_R (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_C_TRIAC_G (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_C_LED_K (low voltage) | PINV-1, CABLE-1, FAULT-1, BARRIER-1 | not yet reviewed | |
| unconnected-(U911-NC-Pad3) (no-connect net of U911 pin 3) | PINV-1 | not yet reviewed | |
| unconnected-(U911-NC-Pad5) (no-connect net of U911 pin 5) | PINV-1 | not yet reviewed | |

### Sheet

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| Coffee heater switch | DRAW-1 | not yet reviewed | |

## Sheet 2. Steam heater switch

### Parts

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| T921 (BTA16-800BWRG, C10065) | PINV-1, PARTS-1, DERATE-2, POLAR-1, BARRIER-1 | not yet reviewed | |
| U921 (MOC3083M, C23552) | PINV-1, PINV-2, PARTS-1, STRAP-1, SUPPLY-2, POLAR-1, INDEP-1, FAULT-1, BARRIER-1, DERATE-2 | not yet reviewed | |
| R921 (200 ohm 1206) | PINV-1, DERATE-2, FAULT-1, SURGE-1 | not yet reviewed | |
| R922 (200 ohm 1206) | PINV-1, DERATE-2, FAULT-1, SURGE-1 | not yet reviewed | |
| RV921 (07D471K) | PINV-1, SURGE-1, DERATE-2, TOUCH-1 | not yet reviewed | |
| J921 (blade TAB_OUT_S) | PINV-1, CABLE-1, DERATE-2 | not yet reviewed | |

### Nets

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| OUT_S (Mains) | PINV-1, SURGE-1, TOUCH-1 | not yet reviewed | |
| HEAT_S_OPTO_MT (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_S_GATE_R (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_S_TRIAC_G (Mains) | PINV-1, FAULT-1 | not yet reviewed | |
| HEAT_S_LED_K (low voltage) | PINV-1, CABLE-1, FAULT-1, BARRIER-1 | not yet reviewed | |
| unconnected-(U921-NC-Pad3) (no-connect net of U921 pin 3) | PINV-1 | not yet reviewed | |
| unconnected-(U921-NC-Pad5) (no-connect net of U921 pin 5) | PINV-1 | not yet reviewed | |

### Sheet

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| Steam heater switch | DRAW-1 | not yet reviewed | |

## Sheet 3. Low-voltage header

### Parts

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| J931 (WB_LV3, XFCN PZ254V-11-03P, C2937625) | PINV-1, CABLE-1, POLAR-1, SUPPLY-1, ESD-1, DERATE-2 | not yet reviewed | |

### Nets

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| +5V_WB (low voltage, power entering) | PINV-1, SUPPLY-1, SUPPLY-2, CABLE-1 | not yet reviewed | |

### Sheet

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| Low-voltage header | DRAW-1 | not yet reviewed | |

## Sheet 4. Return landing

### Parts

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| J941 (blade TAB_RET) | PINV-1, CABLE-1, DERATE-2 | not yet reviewed | |

### Nets

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| RET (Mains, shared by sheets 1, 2 and 4) | PINV-1, SURGE-1, TOUCH-1, CABLE-1 | not yet reviewed | |

### Sheet

| item | catalogue items | verdict | evidence or closing action |
|---|---|---|---|
| Return landing | DRAW-1 | not yet reviewed | |
