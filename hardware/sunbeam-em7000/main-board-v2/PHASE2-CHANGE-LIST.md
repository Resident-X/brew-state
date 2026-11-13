# Phase 2 change list: pin map A on the main board

Written 2026-11-10 for `PLAN.md` phase 2; the pins of seven nets (AMC_CS, AMC_DRDY, WT1_DATA, WT1_CLK, WT2_DATA, WT2_CLK, BUZZER) were moved again during v2 routing and the rows below state those final pins (the pin each had in pin map A is given beside it); the final assignment is `controller-pin-table.md`. Read-only survey of the worktree at its current commit; nothing here has been applied. Pin map A with two changes: AMC_RESET on PC8 (pin 65) and ANODE_GATE stays on PB5 (pin 91). The S-side swap of pins 81 to 88 is not adopted, so the order below is the one pin map A gives. Source of the map: `/Users/david/real5/layoutopinion/pinmap_a.json` and OPINION2 section 2, with the two changes applied (checked against the scratch model `/Users/david/real5/v2go/place2.py`).

## 1. Decisions that fix the shape of the change

1. **Nets keep their names except the three SPI nets, which are renamed `SPI2_SCK`, `SPI2_MISO`, `SPI2_MOSI` to `SPI3_SCK`, `SPI3_MISO`, `SPI3_MOSI`.** Hierarchical labels join sheets by name, so every sheet whose nets keep their names needs no edit. Only `31-controller`, `main-board` (the root), E1 and E3 change in the schematic. The other nine label sheets named in the plan (E4, 700, 710, 720, 730, 740, 750, 52, E2) carry no moved name and need no drawing edit; five of them carry pin names in prose (section 5, spec notes).
2. Keeping the name `SPI2_*` on a SPI3 port would be a standing mislabel in the net class, the signal study, the bring-up list and the firmware's future record, so the rename is taken now while the board holds no footprint.
3. The embedded library symbol in `31-controller.kicad_sch` carries stock alternate-function names (`SPI2_SCK` and so on, lines 483 to 2630). They belong to the stock library, not the design, and are never edited.
4. Every moved pin is a 6.0 V FT class pin (`FT_h`, `FT_f`, `FT_u` or `FT`) with the same limits in `pin-limits.yaml`, so no limit value changes, only the comment above each entry.
5. `controller-input-map.yaml` lists converter inputs only and no ADC pin moves, so it does not change (the plan's mention of a FLOW_IN timer there is wrong: the record holds no timer).
6. `hardware/sunbeam-em7000/controller-part.yaml` lists pin names only, no nets, so it does not change.

## 2. The moved pins (25 nets)

Pin number is the LQFP100 pin. Evidence: DS12110 Rev 11 Table 9 (LQFP100 column) and Table 10, local text copy `/Users/david/real5/schemrev7/ds/stm32h743.txt` (Table 9 rows from line 4070, Table 10 from line 6216), parsed to `/Users/david/real5/layoutopinion/af.json`. A plain GPIO needs no alternate function: every port pin offers GPIO, and every pin below lists EVENTOUT as AF15 in Table 9.

| Net | Old pin | New pin | Function on the new pin | Evidence |
|---|---|---|---|---|
| SPI3_SCK (was SPI2_SCK) | 52 PB13 | 78 PC10 | SPI3_SCK AF6 | Table 9 pin 78 lists SPI3_SCK/I2S3_CK; Table 10 Port C row PC10 (text line 6542), AF6. FT_ha |
| SPI3_MISO (was SPI2_MISO) | 53 PB14 | 79 PC11 | SPI3_MISO AF6 | Table 9 pin 79 lists SPI3_MISO/I2S3_SDI; Table 10 text line 6547. FT_h |
| SPI3_MOSI (was SPI2_MOSI) | 54 PB15 | 80 PC12 | SPI3_MOSI AF6 | Table 9 pin 80 lists SPI3_MOSI/I2S3_SDO; Table 10 text line 6557. FT_h |
| PT1_CS | 51 PB12 | 81 PD0 | GPIO output | Table 9 pin 81: FDCAN1_RX, ..., EVENTOUT; GPIO is free. FT_h |
| PT2_CS | 55 PD8 | 82 PD1 | GPIO output | Table 9 pin 82. FT_h |
| AMC_CS | 56 PD9 | 77 PA15 | GPIO output | Table 9 pin 77 (JTDI AF0 at reset with an internal pull-up; SPI3_NSS AF6 unused). FT. Pin map A gave 83 PD2 |
| WT1_DATA | 65 PC8 | 86 PD5 | GPIO input | Table 9 pin 86. FT_h. Pin map A gave 84 PD3 |
| WT1_CLK | 66 PC9 | 87 PD6 | GPIO output | Table 9 pin 87. FT_h. Pin map A gave 85 PD4 |
| WT2_DATA | 79 PC11 | 83 PD2 | GPIO input | Table 9 pin 83. FT_h. Pin map A gave 86 PD5 |
| WT2_CLK | 80 PC12 | 84 PD3 | GPIO output | Table 9 pin 84. FT_h. Pin map A gave 87 PD6 |
| AMC_DRDY | 57 PD10 | 63 PC6 | GPIO input, EXTI line 6 | Table 9 pin 63. FT_h. Pin map A gave 88 PD7 (EXTI line 7). EXTI line 6 is shared by port pins PA6 (BREW_AN), PB6 (BREW_SCL), PD6 (WT1_CLK) and PE6 (KEY5); none is an interrupt input while the keys are polled |
| AMC_RESET | 58 PD11 | 65 PC8 | GPIO output | Table 9 pin 65 (TRACED1, HRTIM_CHB1, TIM3_CH3, ..., EVENTOUT). FT_h. Not a bootloader pin; powers up a floating input like the pin it leaves. Chosen over PB4 (NJTRST pull-up) |
| BREW_SCL | 46 PB10 | 92 PB6 | I2C4_SCL AF6 | Table 10 Port B row PB6 (text line 6391): I2C4_SCL at AF6. FT_f |
| BREW_SDA | 47 PB11 | 93 PB7 | I2C4_SDA AF6 | Table 10 Port B row PB7 (text line 6394). FT_fa |
| GAUGE_DIR1 | 81 PD0 | 55 PD8 | GPIO output | Table 9 pin 55. FT_h |
| GAUGE_DIR2 | 82 PD1 | 56 PD9 | GPIO output | Table 9 pin 56. FT_h |
| GAUGE_RST | 87 PD6 | 57 PD10 | GPIO output | Table 9 pin 57. FT_h |
| HEAT_C_DRV | 83 PD2 | 58 PD11 | GPIO output | Table 9 pin 58. FT_h |
| HEAT_S_DRV | 84 PD3 | 59 PD12 | GPIO output | Table 9 pin 59 (I2C4_SCL alternate unused). FT_fh |
| VALVE_2W_DRV | 85 PD4 | 60 PD13 | GPIO output | Table 9 pin 60 (I2C4_SDA alternate unused). FT_fh |
| VALVE_3W_DRV | 86 PD5 | 51 PB12 | GPIO output | Table 9 pin 51 (SPI2_NSS alternate unused). FT_u: takes up to 6 V per Table 109 but a 5 000 nA leakage limit above Max(VDDXXX) (Table 147), so the stage must see no 5 V pull-up |
| FLOW_IN | 63 PC6 (TIM8_CH1) | 46 PB10 | TIM2_CH3 AF1, 32-bit timer input capture | Table 10 Port B row PB10 (text line 6427): TIM2_CH3 at AF1. FT_f |
| TANK_LEVEL | 42 PE12 | 97 PE0 | GPIO input | Table 9 pin 97. FT_h |
| LOWWATER_K | 97 PE0 | 42 PE12 | GPIO output (open-drain use) | Table 9 pin 42. FT_h |
| MAINS_PRES_S | 88 PD7 | 47 PB11 | GPIO input | Table 9 pin 47. FT_f |

Stay where they are (not touched): PA8, PA9, PA10, PA11, PA12, PA13, PA14, PB3, PB5 (ANODE_GATE), PC14, PC15, PH0, PH1, every ADC pin, KEY1 to KEY5 (PE2 to PE6), GAUGE_STEP1 and GAUGE_STEP2 (PD14, PD15), POL_OUT (PC7), STM_SCL and STM_SDA (PB8, PB9), KNOB_HOT, KNOB_STEAM, MAINS_PRES_C, BUZZER, USB, supplies.

**No-connect set after the change** (22 pins before and after):
- Newly unconnected: 52 PB13, 53 PB14, 54 PB15, 66 PC9 (and, after the routing moves below the table, 85 PD4, 88 PD7, 98 PE1).
- Newly connected, so their no-connect goes: 78 PC10, 92 PB6, 93 PB7, 59 PD12, 60 PD13.
- PB4 (pin 90) stays unconnected.
- PC9 is MCO2, so the statement "no MCO pin is free" becomes false (section 6, item MCO).

**Expected pin to net map of U401 for the moved and freed pins** (for the forward test; `-` means no connect):

```
46 FLOW_IN
47 MAINS_PRES_S
51 VALVE_3W_DRV
52 -
53 -
54 -
55 GAUGE_DIR1
56 GAUGE_DIR2
57 GAUGE_RST
58 HEAT_C_DRV
59 HEAT_S_DRV
60 VALVE_2W_DRV
63 -
65 AMC_RESET
66 -
78 SPI3_SCK
79 SPI3_MISO
80 SPI3_MOSI
81 PT1_CS
82 PT2_CS
83 AMC_CS
84 WT1_DATA
85 WT1_CLK
86 WT2_DATA
87 WT2_CLK
88 AMC_DRDY
92 BREW_SCL
93 BREW_SDA
97 TANK_LEVEL
42 LOWWATER_K
```

## 3. Schematic edits (main session, Konnect only)

Never by hand or script. In `31-controller.kicad_sch` every moved net is a hierarchical label with no wire, sitting on the pin tip: west pins at x 275.59 with angle 180, east pins at x 321.31 with angle 0, shape `bidirectional`. U401 is at (298.45, 209.55). Because pins swap sides (a net leaving an east pin for a west pin changes angle), a label cannot only be moved: it is deleted at the old pin tip and added at the new one with the side's angle and justification. Check first with `list_schematic_labels` that Konnect handles `hierarchical_label` (not only local labels); if it does not, stop and tell the owner of the plan, since the escape hatch (direct file edit) is the only other route.

Order inside the sheet: delete all 25 labels, delete the 5 no-connect marks, then add the 25 labels and the 5 new no-connect marks, so no pin ever holds two labels.

Pin tip coordinates (x, y), from U401's embedded symbol:

| Pin | Tip | Pin | Tip | Pin | Tip |
|---|---|---|---|---|---|
| 42 | 275.59, 199.39 (W) | 65 | 321.31, 252.73 (E) | 85 | 275.59, 222.25 (W) |
| 46 | 321.31, 214.63 (E) | 66 | 321.31, 255.27 (E) | 86 | 275.59, 224.79 (W) |
| 47 | 321.31, 217.17 (E) | 78 | 321.31, 257.81 (E) | 87 | 275.59, 227.33 (W) |
| 51 | 321.31, 219.71 (E) | 79 | 321.31, 260.35 (E) | 88 | 275.59, 229.87 (W) |
| 52 | 321.31, 222.25 (E) | 80 | 321.31, 262.89 (E) | 92 | 321.31, 204.47 (E) |
| 53 | 321.31, 224.79 (E) | 81 | 275.59, 212.09 (W) | 93 | 321.31, 207.01 (E) |
| 54 | 321.31, 227.33 (E) | 82 | 275.59, 214.63 (W) | 97 | 275.59, 168.91 (W) |
| 55 | 275.59, 232.41 (W) | 83 | 275.59, 217.17 (W) | 59 | 275.59, 242.57 (W) |
| 56 | 275.59, 234.95 (W) | 84 | 275.59, 219.71 (W) | 60 | 275.59, 245.11 (W) |
| 57 | 275.59, 237.49 (W) | 58 | 275.59, 240.03 (W) | 63 | 321.31, 247.65 (E) |

**3.1 Sheet `31-controller.kicad_sch`.**
- Delete these 25 hierarchical labels (name, old pin, uuid prefix): SPI2_SCK 52 (cd291819), SPI2_MISO 53 (a6f3ed7b), SPI2_MOSI 54 (a3a38e32), PT1_CS 51 (472f3c8d), PT2_CS 55 (7437a04e), AMC_CS 56 (54c96e9f), AMC_DRDY 57 (36bb5ca6), AMC_RESET 58 (6283d509), WT1_DATA 65 (c90250c5), WT1_CLK 66 (517ee8eb), WT2_DATA 79 (a964b8ae), WT2_CLK 80 (a45cb515), GAUGE_DIR1 81 (25529317), GAUGE_DIR2 82 (99373f36), HEAT_C_DRV 83 (0420c4e7), HEAT_S_DRV 84 (e1f7fb3e), VALVE_2W_DRV 85 (e9f04b13), VALVE_3W_DRV 86 (5707630c), GAUGE_RST 87 (4edfa888), MAINS_PRES_S 88 (98da928f), BREW_SCL 46 (cffdf6cd), BREW_SDA 47 (dfa7c667), FLOW_IN 63 (8a654ab1), TANK_LEVEL 42 (630cf68e), LOWWATER_K 97 (4517711b).
- Add the 25 labels at the new tips given in section 2 (names there; the three SPI labels with their SPI3 names). West pin: angle 180, east pin: angle 0.
- Delete the 5 no-connect marks at pins 78, 92, 93, 59, 60. Add 5 at pins 52, 53, 54, 63, 66.
- The embedded library symbol is not touched.

**3.2 Rename only, no move** (delete label, add label of the new name at the same point, or Konnect's own rename if it has one; do the rename on every one of these, since a half-renamed net splits in two):
- `main-board.kicad_sch`: 9 local labels at lines 1949, 1959, 1969, 2739, 2749, 2769, 2829, 2839, 2859; 9 sheet pins at lines 3218, 3222, 3226 (the Controller sheet block), 4102, 4106, 4114 (the sheet block that reaches E1), 4230, 4234, 4242 (the sheet block that reaches E3).
- `E1-supply-voltage-and-current-measurement.kicad_sch`: hierarchical labels at lines 2605, 2616, 2638 (SCK, MOSI, MISO) and local label `SPI2_MISO` at 2351. TP610's Value text `TP_SPI2_MISO` (line 5970) becomes `TP_SPI3_MISO`.
- `E3-in-stream-temperature-converters.kicad_sch`: local labels at 2617, 2627, 2637 and hierarchical labels at 2667, 2678, 2700.
- After the three renames a sheet pin of the root and the hierarchical label of its sheet must carry the same name, or the sheet joins to nothing.

**3.3 Sheet text.** `E2-zero-crossing-detector.kicad_sch` line 1096 is a text item naming `MAINS_PRES_S (PD7)`; its new pin is PB11. Edit through Konnect's text tool if it has one; otherwise it is the one item that falls to the direct-edit escape hatch, which the plan's owner confirms first.

**3.4 After the schematic.** `kicad-cli sch erc` clean apart from the known U203/R208/C206 board-absent parity. The board file `main-board.kicad_pcb` holds no footprint, so nothing is updated there until phase 4.

## 4. Net class and project file

- `main-board.kicad_pro` lines 1002, 1006, 1010: the net class patterns `/SPI2_SCK`, `/SPI2_MOSI`, `/SPI2_MISO` become `/SPI3_*`. Not a design sheet, so a text edit is allowed; confirm the three entries are the only SPI patterns first.
- `design-rules.md` line 68 (net class `Fast`, 14 nets): the three names become `SPI3_*`. The count stays 14. Phase 5's `task hw:rules-confirm` is the check that the class is non-empty.

## 5. Records (script agent can do all of these; file:line from the current tree)

All paths are under `hardware/sunbeam-em7000/main-board-v2/` unless a full path is given.

**5.1 Generated, regenerate and do not hand-edit** (`spec-tools/build_spec.py` writes `schematic-spec.yaml` from `sheets/*.yaml`; `spec-tools/build_bring_up.py` writes `bring-up-provision.md` from `bring-up/*.yaml` and `schematic-spec.yaml`).
- `sheets/31-controller.yaml`: net pin lists. Move each moved net's `U401.<pin>` (nets block, lines 895 to 1010 hold BREW_SCL at 898 through WT1_CLK; each net is a `pins:` list with one `U401.n`). `SPI2_SCK`, `SPI2_MISO`, `SPI2_MOSI` at lines 909, 913, 917 become `SPI3_*`. `no_connect:` list (about lines 1055 to 1080): remove `U401.59`, `.60`, `.78`, `.92`, `.93` and add `U401.52`, `.53`, `.54`, `.63`, `.66` with a reason string in the same form (`PB13 unused; DS12110 Table 9 pin, AN4938 7.6: firmware sets unused pins to analog or driven low; no board connection`). Line 1105 (clock note: "PC9 is MCO2 and is a load-cell clock").
- `sheets/E1-supply-voltage-and-current-measurement.yaml`: line 2 (`SPI2 bus`), 50 (TP610 value and function text), 75, 77, 82 (net names).
- `sheets/E3-in-stream-temperature-converters.yaml`: line 2, 529, 534, 539 (net names), 568 (drawing notes).
- Prose pin names in other sheets: `sheets/52-flow-pressure-and-spare-analogue-inputs.yaml:98` (PC6 becomes PB10), `sheets/710-valve-drives.yaml:35` (PD4 becomes PD13, PD5 becomes PB12), `sheets/720-heater-led-drive-and-wall-board-header.yaml:19, 20, 45` (PD7 becomes PB11, PD2 becomes PD11, PD3 becomes PD12), `sheets/740-operator-panel-and-indicators.yaml:58` (PE0 becomes PE12; PB5 stays), `sheets/E2-zero-crossing-detector.yaml:35` (PD7 becomes PB11).
- `spec-tools/build_spec.py`: lines 79, 83 (PD2, PD3, PD7), 86 (SPI2), 87 (PC8, PC9, PC11, PC12 become PD3 to PD6), 96 (SPI2 on PB13 to PB15, selects PB12 and PD8), 97 (I2C2 on PB10/PB11 becomes I2C4 on PB6/PB7), 137 (SPI2), 140 (free-list sentence names PD9, PD10, PD11, which change meaning).
- Then run `python3 spec-tools/build_spec.py`, then `python3 spec-tools/build_bring_up.py`, both from `main-board-v2/`.
- `schematic-spec.yaml` lines that the generator rewrites (verify, never edit): 167, 190, 191, 195, 205, 243, 247, 380 to 545 (the controller pin table), 598, 602, 2966 to 2974, 3002, 3122 to 3134, 3171, 3198, 3722, 3730, 3872 to 3905, 4188, 4189, 5537, 6007, 6534 to 6544, 6573, 7996, 8009, 8108, 8109, 9143, 9145, 9945 to 9959, 10002.
- `bring-up/C.yaml:20, 21` (PB10, PB11 become PB6, PB7); `bring-up/D.yaml:34 to 37` (PD4 to PD13, PD5 to PB12, PD2 to PD11, PD3 to PD12) and `:61` (PD7 to PB11); `bring-up/E.yaml:96, 97` (name and net SPI2_MISO); `bring-up/B.yaml:89` (MCO statement, section 6). `bring-up-provision.md` is regenerated from these (current lines 61, 77, 80, 81, 97, 98, 99, 100, 108, 116, 128, 234).
- `parts-specification.yaml:1256`: `value: TP_SPI2_MISO` becomes `TP_SPI3_MISO`. Also the footprint-side test point naming in `circuit-proof/C_gen_sheets.py` if it spells the name (the sheet-generator test, section 8, shows it).

**5.2 Pin records**
- `controller-pin-table.md`: rows for pins 42, 46, 47, 51 to 60, 63, 65, 66, 78 to 88, 92, 93, 97 (lines 52, 56, 57, 61 to 70, 73, 75, 76, 88 to 98, 102, 103, 107): net, function and AF columns, and the reset/boot note of each (pin 51 keeps its `FT_u` note for VALVE_3W_DRV; PD12 and PD13 lose the "unused (I2C4)" text; pins 52 to 54, 63, 66 become "no connect, unused"). Prose: line 7 (counts: 60 used and 22 unconnected, unchanged); line 116 to 120 (Differences: the `PB12 to PB15` bullet at 119 now describes PB12 only; the "No MCO pin is free" bullet at 120 changes; the PB3 bullet at 117 and unused-pin list at 118 change); the converter-input map is unchanged.
- `pin-allocation.yaml`: `controller_pin:` for each moved net at lines 88, 106, 109, 112, 115, 118, 121, 124, 127, 130, 133, 142, 148, 151, 183, 186, 189, 192, 195, 198, 201, 204, 207, 210, 227 (listed in section 2's order). Channel names `spi2_sck`, `spi2_miso`, `spi2_mosi` (lines 113 to 121) become `spi3_*` with `net: SPI3_*`. Header comment unchanged.
- `pin-limits.yaml`: comments only, the 6 V entry beneath is identical. Comment lines above each pin entry: 485 (pin 42), 509 (46), 515 (47), 539 (51), 545 (52), 551 (53), 557 (54), 563 (55), 569 (56), 575 (57), 581 (58), 587 (59), 593 (60), 611 (63), 623 (65), 629 (66), 701 (78), 707 (79), 713 (80), 719 (81), 725 (82), 731 (83), 737 (84), 743 (85), 749 (86), 755 (87), 761 (88), 785 (92), 791 (93), 815 (97). Each reads `# P (NET), Table 9 class X; ...`: change the net in brackets (and the class where it differs, since moved pins swap `FT_h` and `FT_u`/`FT_f` classes: pin 51 `FT_u`, 59 and 60 `FT_fh`, 92 `FT_f`, 93 `FT_fa`, 46 and 47 `FT_f`, 78 `FT_ha`). Also line 203 (the `mains_present_s_header` domain comment: "controller pin PD7" becomes PB11).
- `controller-input-map.yaml`: no change.
- `hardware/tools/tests/test_main_board_schematic_records.py:15`: `HEADER_CHANNELS` becomes `{"heat_c_drv": "PD11", "heat_s_drv": "PD12", "mains_pres_c": "PE15", "mains_pres_s": "PB11"}`. This test reads `pin-allocation.yaml` and fails until both are changed together.

**5.3 Proofs and verdicts**
- `circuit-proof.md`: lines 58, 232, 303, 306, 329, 345, 370, 397, 399, 405, 411 to 422, 427, 435, 442. Edits: the pin rows of the drive-state table (411 to 414 become PD11, PD12, PD13, PB12; 418 to 420 become PD8, PD9, PD10; 422 becomes PE12); the bootloader pin list at 405 (PB14/PB15 USART1 and PC9 I2C3 no longer carry a signal; PB10/PB11 USART3, PB6 I2C1 and PC10 to PC12 SPI3 now do); the FT_u list at 427 (`PA9, PB12 to PB15` becomes `PA9, PB12`); the owners list at 442; PD7 rows at 329; flow rows at 58, 303 (PC6 becomes PB10); I2C rows at 306; row 370 `E1.8 Shared SPI2 bus`; 232's PC9 clause.
- New rows (each with its own source read, not asserted from memory): (a) SPI3 is a bootloader slave port, so the converters' outputs on PC11 cannot fight the bootloader; each select (now PD0, PD1 and PA15) is held high by its pull-up, and PA15 (SPI3_NSS in the bootloader) carries AMC_CS with its JTDI reset pull-up and R614; (b) PB12 is `FT_u`, so VALVE_3W_DRV sees no 5 V pull-up and the 5 000 nA leakage limit gives at most 50 mV across the stage's 10 kohm pull-down in reset; (c) FLOW_IN sits on PB10, which the bootloader lists as USART3_TX (RM0433 2.6, AN2606 Rev 70 Table 135): the buffer U520's push-pull output meets a pin the bootloader may drive, so the row must read the pin's bootloader drive state and the U520 output; (d) MAINS_PRES_S on PB11 (`FT_f`, USART3_RX in the bootloader), where the reset-state note on the Table 109 row for PD7 ("analog mode at reset, firmware sets a plain floating input") must be re-read for PB11; (e) AMC_RESET on PC8: floating input at reset like PD11, with the AMC's own reset level unchanged; (f) BREW_SCL on PB6 is also the bootloader's I2C1_SCL (open-drain, no pull), with the I2C pull-ups on the net unchanged; (g) AMC_DRDY on PC6: EXTI line 6 has no other interrupt user.
- `circuit-verdicts.md`: lines 192 to 195, 244, 247, 310, 315, 316, 321, 322, 417, 418, 491 to 494, 532, 556, 563, 570 to 572, 615, 616, 632, 649, 666. Same changes as the proof rows they restate, including the verdict for each new row above. `PB4` at 195 is unchanged.
- Scripts: `circuit-proof/E_spi_bus.py:2, 46` (SPI2 wording, `H743 SPI2 master`), `circuit-proof/E_spi_bus.log` (re-run), `circuit-proof/C_front_ends.py:196, 201, 203, 204` and `circuit-proof/C_gen_decks.py:201, 233` (PC6 pad leakage becomes PB10, still `FT_f`: the leakage figure is Table 50 for the FT class, so check it applies to `FT_f`), `circuit-proof/b_supply_protection.py:20, 90` and `b_supply_protection.out:37` (PD7 becomes PB11; re-run to refresh the .out), `circuit-proof/C_gen_sheets.py:168` (PC6 text). No deck's net voltages change.
- `circuit-proof/main-board.cir` does not exist in the tree yet; phase 2 step 4 of the plan creates it from the finished schematic.

**5.4 Layout and other records that restate pins**
- `layout-plan.md`: lines 94 (FLOOR-2: analogue pins unchanged, no edit), 121, 122 (CLOCK-3: "SPI2 on pins 52 to 54" becomes SPI3 on pins 78 to 80), 149, 154, 155 and the SPI2 mentions in the history tables (244 to 702). Phase 3 rewrites the low-voltage rows, so edit these there, not here; the placement-history rows (244 onwards) describe the v1 candidates and stay as they were.
- `signal-study.md`: lines 7, 36, 38, 40, 56, 74, 96, 105, 108, 111, 117, 150, 152, 162, 172, 173 name SPI2; the study is redone whole in phase 9, so only rename the bus now if a record cites it, otherwise leave for the redo.
- `traceability.md:37, 40, 44, 50, 117, 125`; `open-items.md:77, 114, 125, 134, 202`.
- `docs/sunbeam-em7000/component-specification.md`: the allocation table and bus-function rows at lines 178 to 180 (I2C pair and timer rows), 215, 220 to 236, 244, 245, 253, 255, 257, 258, 260, 264, 268, 270, 278 to 293 (SPI2, I2C2, TIM8, the PD, PB and PC allocations, and the "free pins" list at 260). This is the allocation source the pin record cites, so it governs and is corrected first.
- `docs/sunbeam-em7000/controller-board-division.md:1038, 1047, 1048` (channel table cells naming PC8 to PC12, SPI2 on PB13 to PB15, PB12, PD8, I2C2 on PB10/PB11).
- Not changed: `docs/sunbeam-em7000/controller-board-design-constraints.md` (its one hit is PB4, which does not move), `docs/sunbeam-em7000/controller-design/*` (the earlier bought-module design; its pin tables are history and the folder's precedence rule says it loses to the record documents), `docs/sunbeam-em7000/connector-pinouts.md:663` (the original machine's own `PD1`, a different chip), `hardware/proof/review-proof/*` (a synthetic proof design), `schematic-review.md` (a record of rounds 1 to 7; round 8 is appended and no earlier round is edited).

**5.5 Firmware and the pinned analysis records**
- `firmware/src`: no pin-map source. `hw_stm32.c` output table (`GPIO_PIN_6` to `GPIO_PIN_9`, GPIOC) is the STM32F407 verification stand-in's TIM3 outputs, not the board, and `pin-allocation.yaml` binds no `firmware_channel` or `firmware_sensor`. `firmware/tools/check_pin_assignment.py` and `check_sensor_assignment.py` read the record only for channels the firmware names, and none are named. No firmware change.
- `firmware/params`: nothing in it names a pin. The sha256-pinned analysis records (`docs/protection-margin.md`, `docs/parameter-dominance.md`, `docs/parameter-stability.md`, `docs/parameter-identifiability.md`, `docs/casting-peak.md`) pin only `firmware/params/*` files, none of which changes, so no analysis record is regenerated. No path this change touches is in `EMULATION_READS` or `HOST_READS` in `firmware/tools/round_gate.py` (the constraints document is read by emulation, but is not edited), so the round gate's host and emulation tiers do not run for it; its board tier and changed-lines sweep do.

## 6. Statements that become false (found by search, not by pin number)

- MCO. PC9 is now unconnected, so "No MCO pin is free for a clock observation point: MCO1 is PA8 ..., MCO2 is PC9 (a load-cell clock)" is wrong in `controller-pin-table.md:120` (and row 76), `sheets/31-controller.yaml:1105`, `schematic-spec.yaml:3170 to 3171` (regenerated), `bring-up/B.yaml:89`, `bring-up-provision.md:61` (regenerated). Restate: MCO1 is PA8, the steam pump gate; MCO2 (PC9) is unconnected and could carry a clock observation point, which TP406 does not need today.
- "PB3 free list" sentences: `controller-pin-table.md:117`, `build_spec.py:140`, `schematic-spec.yaml:602`, `open-items.md:125` name PD9, PD10, PD11 as placed in the original free-list arithmetic. The list of 20 free 5 V-rated pins now loses a different set; recompute it once from the new map and restate it in all four.
- "PB12 to PB15 are `*_u*` pins" (`controller-pin-table.md:119`): now only PB12 is used.
- `controller-pin-table.md:7` counts stay (60 used, 22 unconnected), so no edit.

## 7. Graph nodes (ids only; the graph is not edited by this work)

Read each with `./engine/staircase show` before any link; bump the version once per node.
- `DEL-HW-MAIN-BOARD-DESIGNED.C27` (version 2, text names "SPI2 port", 4 MHz and 5 ns, and a signal study of the v1 board): change SPI2 to SPI3; re-derive or supersede after the v2 signal study (phase 9).
- `SOL-FW-SPI2-PORT-RUNS-SLOW-EDGES-AND-A-LOW-CLOCK` and its `.C1` (title and text name SPI2): same change; supersede together if C27 is superseded.
- `SOL-HW-MAIN-BOARD-SCHEMATIC-PROVEN.C10` (header channels listed in the pin allocation record, satisfied by `test_main_board_schematic_records.py`): no amendment, the criterion is position-free; the evidence nodes `EV-SOL-HW-MAIN-BOARD-SCHEMATIC-PROVEN-C10-TEST` and `-TEST-2` cite commits and stay as they are, with new evidence if the test is re-run.
- `DEL-HW-MAIN-BOARD-DESIGNED.C4`, `DEL-HW-DESIGN-VERIFICATION.C1`, `SOL-HW-CONNECTIVITY-CHECK.C1`, `SOL-HW-HEATER-WALL-BOARD-PROVEN-AND-LAID-OUT.C4`: criteria about the record and the check, pin-free; no change expected, confirm by `show`.
- `DEL-HW-BRING-UP.C21` (the signal readings the routed board's signal study carries to bring-up; the hits for SPI2 in the signal study feed it): re-point after the study is redone.
- New `DEL-MAINTENANCE` child, as `PLAN.md` lists, tracing to `REQ-BOARD-LAYOUT-PRACTICE-001.C1`: pin map A adopted, with the proof rows and schematic review round 8.

## 8. Order of application

**Main session (Konnect).**
1. `get_project_info`, then `list_schematic_labels` on `31-controller` to confirm the 25 old labels and their coordinates against section 3, and that hierarchical labels are listable.
2. Edit `31-controller` as section 3.1 orders. Run the cheapest forward test (section 9) immediately after this first sheet is saved.
3. Rename the SPI nets in `main-board`, E1, E3 (3.2), then E2 text (3.3).
4. `kicad-cli sch erc` on the root; the netlist test again on the whole design.
5. Round 8 of the schematic review is run by the plan's reviewers.

**Script agent (Haiku for the regeneration runs, Sonnet for the prose records), starting once step 2 is saved:**
1. Edit `sheets/31-controller.yaml`, E1, E3 and the prose sheets (5.1), `spec-tools/build_spec.py`, `bring-up/*.yaml`, `parts-specification.yaml:1256`.
2. `cd hardware/sunbeam-em7000/main-board-v2 && python3 spec-tools/build_spec.py && python3 spec-tools/build_bring_up.py`.
3. `cd hardware/sunbeam-em7000/main-board-v2 && python3 spec-tools/check_spec.py sheets && python3 spec-tools/check_bringup.py && python3 spec-tools/check_decks.py` (each reads the sheets or the spec and prints `ISSUE` lines; run from the folder they are written for).
4. Edit the pin records (5.2), the test constant at `test_main_board_schematic_records.py:15`, the net class entries (4), the proof and verdict rows (5.3, rows written from each source's own text) and the other records (5.4, 6).
5. Re-run the proof scripts named in 5.3 and save their `.log` or `.out` files.
6. `export KICAD_CLI=<path>` first when kicad-cli is off PATH, then `kicad-cli sch export netlist --format spice --output hardware/sunbeam-em7000/main-board-v2/circuit-proof/main-board.cir hardware/sunbeam-em7000/main-board-v2/main-board.kicad_sch` (plan phase 2 step 4; the method, Proving step 4, compares a second export with this one using `cmp`).

**What proves each step.**

| Step | Test | Command |
|---|---|---|
| Sheets and spec agree | spec checks | `cd hardware/sunbeam-em7000/main-board-v2 && python3 spec-tools/check_spec.py sheets` |
| Records agree with the drawing | schematic records tests | `python3 -m pytest hardware/tools/tests/test_main_board_schematic_records.py -q` (from the repo root) |
| Sheet generator and proofs agree | generator tests | `python3 -m pytest hardware/tools/tests/test_circuit_proof_sheet_generator.py hardware/tools/tests/test_derating_policy_record.py -q` |
| Net names in the project file | rules confirm (phase 5) | `task hw:rules-confirm` |
| Whole board check, including `pin_limits` and `pin_allocation` lines | pre-order check in a scratch clone, detached | `task hw:verify` (about 2.5 h; read only the `pin_limits` and `pin_allocation` lines) |
| Board tooling tests | the round gate's board tier | `task hw:test:round` |
| Round gate | the verdict | `task check:round` |
| No firmware path changed | the gate decides which tiers run | `task check:round` (host and emulation tiers are skipped by its own selection) |

## 9. Cheapest forward test (right after the first Konnect edit, seconds)

1. Export the netlist of the sheet after the `31-controller` edit: `kicad-cli sch export netlist --format kicadxml --output <scratch>/n.xml hardware/sunbeam-em7000/main-board-v2/main-board.kicad_sch` (scratch folder outside the worktree).
2. A throwaway scratch script (not committed, `python3 -I`) reads the XML, takes every node of `U401`, and compares `pin to net` with the block in section 2 above. Any missing pin, any extra pin on a net, and any net still named `SPI2_*` is a miss. Run it again after the rename of the other three sheets: `SPI3_SCK`, `SPI3_MISO` and `SPI3_MOSI` must each join `U401`, `U601`, `U620` and `U621` pins (no net holding U401 alone).
3. In the same minute: `kicad-cli sch erc` on the root (one run, a few seconds); an unconnected hierarchical pin or a net with one node is the signature of a half-renamed SPI net or a label left on a stale tip.
4. `python3 -m pytest hardware/tools/tests/test_main_board_schematic_records.py -q`: fails until `pin-allocation.yaml` and the test constant agree, which is the signal the record step was not forgotten.

The first run catches a mis-keyed coordinate, a label left on its old pin, two labels on one pin, a net that lost its connection, and a no-connect left on a connected pin, each of which would otherwise show only in the 2.5 h check.
