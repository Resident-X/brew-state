# Simplified 3D bodies for the main board's own footprints

These STEP files give `main-board.pretty`'s custom footprints a body, so a render shows
where each part stands, how tall it is and which way its terminals face. They are boxes
and rods in the footprint's own frame (z up from the board surface, pads at their
footprint coordinates), not maker drawings. `generate_models.py` writes all of them
(`python3 generate_models.py`, pure Python, no CAD package); change a figure there and
regenerate rather than editing a `.step`. Each footprint refers to its model as
`${KIPRJMOD}/main-board.3dshapes/<footprint name>.step`, which resolves from the board's
project folder. Test points and mounting holes have no body and no model.

Heights are above the board surface. Figures marked "assumed" are not from a maker drawing
in hand and are the generator's own stand-ins; replace them when the part's drawing is read.

| Footprint | Body (x by y by height, mm) and terminals | Source |
|---|---|---|
| `RELAY_HF32FA-G_1H_TYPE1_THT` | 17.6 x 10.1 x 12.7 (0.4 standoff), 4 pins to 3.2 below the board | Hongfa HF32FA-G datasheet, 2026 Rev. 1.00, outline and PCB layout (Type 1), the footprint's fab outline for the body position |
| `Relay_HF115F-Q_1H_Vertical` | 29 x 12.7 x 15.7 (0.3 standoff), body from 2.5 before the coil pins to 26.5; 6.3 mm quick-connect blade 0.8 thick beyond the body end, 13.2 high; pins at the four contact holes | Hongfa HF115F-Q datasheet, 2024 Rev. 1.00, outline (quick-connect vertical) and PCB layout. The footprint's own fab outline puts the 29 mm body 4.3 to 33.3 mm instead; the datasheet's 2.5 mm coil-pin offset and 41 mm overall length fit the placement here |
| `AMC131M02_SOIC-20W_DFM0020A` | 12.8 x 7.5 x 2.65, gull-wing leads 0.4 wide, 10.3 mm across | TI SBASA56 package drawing DFM0020A (SOIC-20W, 1.27 mm pitch) |
| `FUSEHOLDER_5x20_XC_BLX-A` | holder 24 x 9.5, clips 8 wide and 9.5 high, a 5.2 x 20 cartridge between them | Assumed from the 5 x 20 mm cartridge standard and `controller-board-division.md` assumption A6 (24 x 9 mm, at most 15 mm high); the maker's drawing was not read |
| `JP101_WireLink_P10mm` | 1.4 mm square wire, 10.7 long, standing 3.0 above the board on two legs | Assumed from the 10.0 mm pad pitch and 1.7 mm holes |
| `LTV-814S_SMD-4` | 4.6 x 6.5 x 3.5 (0.35 standoff), gull-wing leads reaching 5.15 from the centre | Lite-On LTV-814 series, 4-pin SMD body (4.6 mm along the pin pitch, 6.5 mm wide); height assumed from the DIP-4 outline |
| `MOC3052SVM_SMD-6` | 8.51 x 6.35 x 3.5 (0.4 standoff), gull-wing leads reaching 5.27 from the centre | onsemi MOC3052M family sheet, case 646BY (8.51 mm along the pin pitch, 6.35 mm wide); height assumed from the 6-pin DIP outline |
| `TS1187A_5.1x5.1mm_SMD` | 5.1 x 5.1 x 1.5 with a 2.6 mm button, four 0.6 mm legs reaching 3.4 from the centre | XKB TS-1187A, 5.1 x 5.1 mm; height assumed |
| `Tab_BZXC_BTC-3-PCB634908T` | 6.3 x 0.8 blade 9.9 above the board, 1.6 below | 6.3 mm tab, 9.9 mm blade height as `layout-plan.md` BOARD-15 states it |
| `R_WSK2512_4T` | 6.35 x 3.18 x 0.75, copper end terminations 1.5 wide | Vishay Dale WSK2512 (2512 case, 6.35 x 3.18 mm); thickness assumed. The two sense terminals are not drawn |
| `REED_PADS_P20.00mm` | glass body 14 long, 2.3 across, centred between the pads at 2.0 above the board, 0.6 mm leads | Assumed: a standard 14 mm reed capsule; the element is hand-fitted and its drawing is not in the record |

KiCad draws a model's +Y toward the board's -Y, so the generator negates y when it writes a
file; the part functions use footprint coordinates.
