# Decisions and facts log

Written 2026-10-12 at the close of the controller-design discussion session (staircase session `3CD30AB4-5763-4EE0-8610-FD0C090674AA`, project `brew-state`). It is the single record of what has been decided, what is only the owner's statement, and what is a recommendation awaiting a decision. Nothing here is in the graph yet.

Status words used throughout this folder:

- **Chosen** — decided in an earlier discussion session and carried forward; the basis is in the named document.
- **Owner decision** — decided by the owner in the session that closed 2026-10-12.
- **Agreed** — settled in discussion without a separate explicit sign-off.
- **Recommended** — the assistant's recommendation; the owner has not decided.
- **Owner statement** — a fact about the machine given by the owner, not confirmed on the machine or in a document.
- **Parts list** — read from the service manual parts list.
- **Schematic** — read from the service manual circuit diagram.
- **Published, unverified** — from a web source whose text has not been checked at the source.
- **Inferred** / **Unmeasured** — reasoning or an estimate with no measurement behind it.

## Decisions

| # | Decision | Status | Basis and where recorded |
|---|---|---|---|
| D1 | Controller is the WeAct MiniSTM32H743 (STM32H743VIT6) on female headers, for its 16-bit ADCs | Chosen for the H743 and its 16-bit ADCs; the module-on-headers form is reopened 2026-10-12: whether this stays a bought module or becomes a designed circuit is decided by `DEL-HW-PARTITION-AND-FEASIBILITY` in the graph | `README.md`, `control-system-bom.csv`; header footprint read from the WeAct BoardShape V12 drawing |
| D2 | Heaters are two EARU SSR-40DA zero-cross SSRs, low-side driven by one ULN2003A breakout (buy 2, fit 1), SSR control + to 5V, 10k pull-downs at the breakout inputs | Chosen | `heater-drive-and-supply-timing.md`, `passive-and-drive-components.csv` |
| D3 | Pumps are two RBdimmer 4A Standard (Z-C/DIM) modules, one shared Z-C on PA10, DIM on PA9 (coffee) and PD8 (steam), 10k DIM pull-downs, a 1-2 A slow-blow branch fuse | Chosen; module form reopened 2026-10-12: whether this stays a bought module or becomes a designed circuit is decided by `DEL-HW-PARTITION-AND-FEASIBILITY` in the graph | `control-system-bom.csv`, `module-interconnect.csv` |
| D4 | Steam pump drive (phase-angle versus burst) | Open | The OEM steam pump 'thumps', which points to whole-cycle bursts, and one hobbyist report puts it at about 0.3 s on / 0.5 s off (Published, unverified; the OEM timing is menu-adjustable). Pure phase-angle at the steam pump's low flow (about 0.43 g/s, 26 ml/min, from the 1126 W element) against steam backpressure may stall a vibratory pump. The Standard dimmer can do either; a bench step test (weigh output per 60 s at stepped power, then bursts) decides it |
| D5 | Valves: 4-channel mechanical relay module; two RC snubbers (one per valve) | Chosen; mechanical relays stand on the physics below, the relay-module form is reopened 2026-10-12: whether this stays a bought module or becomes a designed circuit is decided by `DEL-HW-PARTITION-AND-FEASIBILITY` in the graph | Mechanical is not a preference: espresso solenoid coils draw about 39-59 mA at 230 V (the coil marking's 9-13.5 VA, `../connector-pinouts.md`) against a BTA16's maximum holding current of 60 mA, so a triac cannot reliably latch on them; the OEM's split (triac for pumps, relay for valves) was the same physics. Contacts also fail open when unpowered, which D6 relies on. `control-system-bom.csv` |
| D6 | The 2-way vent valve is normally open (open to the drain de-energised) and is energised closed whenever the coffee pump is pumping through the block (a 30-40 s shot; also hot water, the pre-shot flush, the dry-fill and the identification runs, since an open vent would take the water), so it vents on power loss, fault, end of brew and whenever the block heats with no flow path | Owner decision | `decisions.md`, `system-design.md` |
| D7 | Supply is one Mean Well IRM-10-5 on a hand-cut single-sided copper-clad carrier, T2A slow-blow fuse (recommended, not required; an internal fuse in the IRM-10-5 is not established), output 100 nF and 47-100 uF | Chosen; the hand-cut carrier is reopened 2026-10-12: whether this stays a bought module or becomes a designed circuit is decided by `DEL-HW-PARTITION-AND-FEASIBILITY` in the graph | `mains-inlet-protection.md` |
| D8 | Mains inlet: Schaffner FN9222-15-06, T10A slow-blow on active, RN3404 MOV; trunk at least 1.5 mm2; one TR5 fuse on the valve branches | Chosen; rating margin decided by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` (15 A filter, trunk above the fuse, valve branches fused) | `mains-inlet-protection.md` |
| D9 | Key temperature sensor is one calibrated PT1000 spike probe in the water at the coffee block outlet, before the 3-way valve (PA4), fitted in a standard tee used as an elbow with the probe in the opposite run port, tip facing upstream | Owner decision (placement); fitting detail agreed | `temperature-sensing-front-end.md` |
| D10 | The block NTCs (coffee, steam) and the wand disc NTC are kept as casing sensors, calibrated in place against the water probe under steady low flow; no MAX31865 | Chosen | `temperature-sensing-front-end.md` |
| D11 | Two flat PT1000 chips are commissioning tools only (temporary puck-inlet probe on PA1, plus a spare) | Chosen | `temperature-sensing-front-end.md` |
| D12 | Pressure sensors are two XDB401 I2C units (1.2 MPa brew, 0.5 MPa steam) on two separate I2C buses, no multiplexer | Chosen | `control-system-bom.csv` |
| D13 | Brew pressure tap is a direct tee on the cold side between the (new) brew OPV and the block, no leg | Agreed | `temperature-sensing-front-end.md` |
| D14 | Steam pressure tap is a normal hairpin-clip tee in the steam line between the steam block and the manual steam knob valve, with a 100-150 mm downhill PTFE drop leg and the sensor at the lowest point; the leg tube is matched to the OEM tube size | Owner decision | `control-system-bom.csv` |
| D15 | Over-pressure valves and dampers are BOM items whether or not the OEM fits them: steam OPV retained (on the steam pump), brew OPV new, brew damper retained, steam damper not fitted | Owner decision | `control-system-bom.csv` |
| D16 | No pulsation damper on the steam line (Opus-agent reasoning review, about 75% confidence, assumed numbers, unmeasured) | Owner decision | `control-system-bom.csv` |
| D17 | Two BL0942 isolated energy-meter modules in series upstream of each SSR | Chosen; no BOM row yet; isolation to be measured; module form reopened 2026-10-12: whether this stays a bought module or becomes a designed circuit is decided by `DEL-HW-PARTITION-AND-FEASIBILITY` in the graph | `heater-drive-and-supply-timing.md` |
| D18 | The OEM panel, gauge and flow-meter harnesses are reused; the controller copies the OEM `Q7` (anode-rail gate) and `Q8` (buzzer) transistor stages, driven open-drain from pins still to be verified 5V-tolerant (PB4, PB5; `open-items.md` section B) | Recommended | `connector-pinouts.md` (sheet 3-3 transcription), `h743-pin-allocation.csv` |
| D19 | Gauge control lines go through a 74HCT541 level-up because the VID66-08 VIH is 3.15 V | Chosen | `h743-pin-allocation.csv` |
| D20 | Mains-presence confirm is replaced by the BL0942 current reading | Recommended; not decided (loses localisation of "did not close" versus "open downstream") | `h743-pin-allocation.csv` |
| D21 | A low-voltage-only PCB (H743 on headers, dividers, ULN2003A breakout, 74HCT541, two transistor stages, connectors; mains modules off-board) as a prototype spin, bare boards hand-soldered | Superseded 2026-10-12 by the graph epic `DEL-CONTROLLER-HARDWARE`: designed boards made and assembled by the manufacturer `DEC-BOARD-MANUFACTURER-JLCPCB` names, through-hole only where needed | `pcb-plan.md` |
| D22 | Cold-side steam pressure tap | Rejected | Cold-side reading adds an unmeasured flow-dependent two-phase block drop and cannot give the in-block pressure the saturation-temperature check needs |
| D23 | A third PT1000 channel on PA6 is reserved permanently for a temperature monitor at the steam output, so the commissioning channel PA1 stays a spare and is not borrowed | Owner decision (channel; the probe, rating and placement at the steam output are not yet specified) | `h743-pin-allocation.csv`, `temperature-sensing-front-end.md` |

## Decisions awaiting the owner

Mirrors `open-items.md` section C.

- **Mains chain rating margin.** Resolved by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`: filter FN9222-15-06 (15 A at 50 C; coupler rating unverified), trunk at least 1.5 mm2 (WB1568), T10A unchanged, one shared TR5 fuse on the valve branches; upstream breaker declared up to 20 A.
- **Heater switching cadence.** Whole-cycle (20 ms) bursts or half-cycle; the files disagree.
- **Steam heater with the knob shut.** The firmware's 137 C ready temperature heats against a closed knob, as the OEM does (F10, as superseded 2026-10-15), and that is the open trapped-pressure case; options are an S8 interlock, a hot-side relief valve, or both.
- **SSR mounting.** Direct to the side wall is proposed, not decided, and conflicts thermally with the IRM-10-5's derating.
- PCB go or no-go (D21); whether the BL0942 current reading replaces the mains-presence confirm (D20); whether to copy the OEM `Q7` and `Q8` stages (D18); the steam pump drive (D4); whether to fit the optional vent-branch test tee.

## Facts about the machine (not yet confirmed on the machine unless stated)

| # | Fact | Source |
|---|---|---|
| F1 | The 3-way valve (JLT 3T0618W) is never closed: de-energised it connects the coffee block outlet to the group (brew path), energised it diverts to the hot water outlet | Owner statement |
| F2 | The 2-way valve (JLT 2T0607W) is on a second coffee block outlet and connects it to the drain; normally open, the OEM energises it closed while pumping | Owner statement, owner inference |
| F3 | The block and group therefore drain downhill to the drip tray whenever the machine is not pumping; each shot may start partly air-filled | Owner inference |
| F4 | The `RELIEF ADAPTER BRASS` on the coffee thermoblock is only an extension tube between the block and the 2-way valve | Owner statement |
| F5 | Steam leaves the steam block through a manual two-way knob valve to the wand; the knob also triggers microswitch S8, the only thing that engages steam mode | Owner statement |
| F6 | The steam pump has a relief valve directly on it, opening at about 4-5 bar and discharging to the drip tray; it is downstream of the pump's own check valve | Owner statement |
| F7 | If no check valve lies between the steam OPV and the block, the OPV caps the block pressure at its setting; otherwise the block pressure is the saturation pressure at the block temperature (about 15.5 bar absolute at the 200 C thermostat trip) | Owner reasoning; to be inspected |
| F8 | The brew pump has a damper and no OPV | Owner statement; a forum post says "no OPV in the 7000" (low confidence) |
| F9 | Both pumps contain check valves; no discrete check valve is visible, so any others would be inside the thermoblocks | Owner statement |
| F10 | The OEM holds the steam block hot (ready) from power-on with the wand knob shut; the block holds no standing water, which enters only when the knob is open. This supersedes the earlier statement that the steam heater is off when no steam is drawn | Owner statement, 2026-10-15 (supersedes the 2026-10-11 statement) |
| F11 | The coffee pump is an Ulka EP5 (15 bar, 48 W; outlet G1/8), the steam pump a JYPC-4 (22 W) | Both wattages read from the nameplates on this machine (inspected, 2026-10-19; `../connector-pinouts.md` § Pumps: running current); outlet thread Published, unverified |
| F12 | Thermostats: coffee block 110 C, steam block 200 C, pump 110 C; steam block thermal fuse 240 C | Parts list; fuse rating Published, unverified (a derived view: `reference-machine.md` § Protection records none seen at the board end and none found by the owner, so no rating is recorded for this machine) |
| F13 | The NTCs are 100 kOhm at 25 C with 10 kOhm 1% dividers on the OEM board; B is not established | Schematic |
| F14 | Panel indicators: 330 Ohm (PWR) and 300 Ohm series resistors; key lines have 1 kOhm in series with each switch to ground and 47 Ohm at the MCU pin, no pull-up drawn | Schematic (disagrees with the earlier reading of the 1 kOhm as pull-ups; check with a meter) |
| F15 | Buzzer stage: 2N5401 PNP, emitter on VCC5, base 1 kOhm to the MCU and 10 kOhm to VCC5, buzzer then 100 Ohm to ground, no diode. Anode-rail gate: 2N5401 PNP, base 2 kOhm to the MCU and 100 kOhm to VCC5. VCC5 is 5 V by derivation | Schematic |
| F16 | The OEM flow meter signal is held to VCC5 by 2 kOhm; its output is probably open-collector or Hall (inferred) | Schematic |

## Options rejected, and why

- MAX31865 RTD boards: the H743's 16-bit ADC with a ratiometric divider and a calibrated PT1000 meets the accuracy need. An Adafruit 3648 (the PT1000 board; 3328 is the PT100 one) stays a fallback only.
- STM32F407 boards, including the MKS Robin Nano: a 12-bit ADC (about 2.2 C resolution on the NTCs), and the Robin Nano takes only 12-24 V in.
- I2C multiplexer: two separate I2C buses instead; the XDB401 address is also programmable in EEPROM.
- DimmerLink dimmer variant and a separate zero-cross detector: the Standard dimmer's Z-C is the phase and period reference.
- Fotek SSR-25DA and Crydom D2425: counterfeit Foteks are endemic, and the Crydom is about AUD 140 each against about AUD 15.
- HLK-10M05, the HLK 3.3 V and 5 V modules, and the IRM-05-5: the Mean Well IRM-10-5 has documented approvals and derating, and the IRM-05-5 is marginal at 60 C against a 0.53 A load.
- The 2-channel mechanical relay module: the 4-channel costs AUD 0.70 more and gives headroom.
- Chips under the NTC clamp, swapping the NTCs for PT1000s, and an external group sensor: no exposed brass for the last; the NTCs stay and are calibrated in place (see `temperature-sensing-front-end.md`).

## Corrections made during the session

- The mounting holes of the H743 are on 35.56 x 61.38 mm centres, not 33.02 x 61.38 mm (33.02 mm is the inner header column spacing).
- The header is 2 columns x 22 rows on each long edge (88 holes) plus a 4-pin SWD header (92 positions); the 2x40 figure does not apply.
- Four 1x22 header pieces need four 1x40 strips, not three.
- The steam OPV is on the cold side at the pump, but if no check valve lies between it and the block it also caps the block; the earlier "does not cap" statement was conditional on that and is now stated conditionally.
- The brew pump has no OPV; the earlier "OPV before the block" meant where the new brew OPV would go.
- The 2-way vent was specified normally closed with no source; it is normally open.
- The snubber quantity was 4; two valves are wired, so it is 2.
- The Adafruit PT1000 board is 3648 (3328 is the PT100 board).
- The sensor divider is 4.7 kOhm (not 1-2 kOhm).
- The brew-line probe rating is 125 C or more (150 C preferred), not 200 C; the steam hot side needs at least 160 C and 8-10 bar if the OPV does cap the block, and the 200 C trip rating until that is confirmed.
- The reviewer's claim that a cold-side brew tap cannot see the vent depressurise was wrong: the check valve opens forward as downstream pressure falls.
