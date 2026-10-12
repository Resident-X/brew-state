# System design: replacement control system for the Sunbeam EM7000

The holistic description of the design as it stands on 2026-10-12. It gathers what the other files in this folder say in detail, so a reader can understand the whole before opening any of them. Status words and provenance tags are defined in `decisions.md`; the line-by-line plumbing is in `hydraulic-lines.md`. Nothing here is in the graph yet, and none of it is baselined.

## 1. Purpose

Replace the OEM control board and mains switching of a Sunbeam EM7000 thermoblock espresso machine with a controller that can measure the brew water temperature and the brew and steam pressures, switch the two heaters by burst firing (cadence: open decision), modulate both pumps, and drive the valves, while reusing the machine's own panel, gauge, sensors, valves, pumps and thermostats. The requirements live in the graph (`REQ-BREW-TEMP-001`, `REQ-MEASUREMENT-001`, `REQ-STATE-ESTIMATION-001` and others); these documents hold the hardware design that serves them.

## 2. The machine as found

Two thermoblocks (coffee and steam, each about 1 kW), a Ulka EP5 coffee pump that also feeds hot water, a JYPC-4 steam pump, a three-way solenoid valve (brew or hot water), a two-way solenoid valve that vents the coffee block to the drain, a manual steam knob valve with a microswitch, an operator panel (five keys, eight indicator elements, a buzzer) and a gauge assembly (two stepper gauges and a low-water indicator), a flow meter on the coffee pump's suction line, three NTC thermistors, a tank level switch, and mechanical thermostats and thermal fuses in series with the loads. The OEM control board (two Holtek microcontrollers) is replaced. The full record is `reference-machine.md` (the machine as found) and `connector-pinouts.md` (what each connector carries); both are normative and are not repeated here.

## 3. Architecture

```
mains inlet: Schaffner FN9222-10-06 filter, T10A fuse, RN3404 MOV
   |
   +-- Mean Well IRM-10-5 (on a hand-cut carrier) -> 5 V -> controller board, accessories
   +-- SSR #1 (coffee heater) ---- ULN2003A breakout (low-side) <- controller
   +-- SSR #2 (steam heater)  ---- (same breakout)
   +-- RBdimmer Standard #1 (coffee pump)   DIM <- controller, Z-C -> controller
   +-- RBdimmer Standard #2 (steam pump)    DIM <- controller
   +-- 4-channel mechanical relay module -> 3-way valve, 2-way vent valve (+ 2 spare)
   +-- BL0942 isolated energy meters x2 (upstream of each SSR) -> controller UART
   (the OEM thermostats and thermal fuses stay in series with their loads)

controller board (low voltage only; prototype PCB or perfboard)
   WeAct MiniSTM32H743 on female headers
   5 ADC dividers (3 NTC + 2 PT1000), 4.7 k low-TCR, ratiometric to the ADC reference
   74HCT541 level-up for the 5 gauge lines; two 2N5401 stages (rail gate, buzzer; proposed, D18)
   I2C1 and I2C2 to the two XDB401 pressure sensors
   connectors: gauge (9-way), panel (9-way), flow meter, thermistor plugs, tank level, knob microswitches
```

Mains parts stay off the controller board, wired by harness; only the low-voltage side is on the board (`pcb-plan.md`).

## 4. Channels and pins

The pin map is `h743-pin-allocation.csv` (37 header pins assigned, 18 free, with the alternate functions marked verified or not); the module wiring is `module-interconnect.csv`.

| Channel | Pin(s) | Notes |
|---|---|---|
| Heater SSR gates (coffee, steam) | PB0, PB1 | Via the ULN2003A breakout; burst firing (cadence is an open decision); 10 k pull-downs at the breakout |
| Pump DIM (coffee, steam) | PA9, PD8 | Standard dimmers; 10 k pull-downs at the modules |
| Shared zero-cross capture | PA10 | From the coffee dimmer's Z-C; TIM1_CH3 expected, unverified; output type unmeasured |
| Energy meters (BL0942) | PC7, PA3 (UART RX) | No BOM row yet; isolation to be measured |
| Pressure sensors | PB8/PB9 (I2C1, brew), PB10/PB11 (I2C2, steam) | XDB401 1.2 MPa and 0.5 MPa |
| NTCs | PC0, PC1, PC4 | 100 kOhm NTCs, 4.7 k dividers |
| PT1000 channels | PA4 (outlet water probe), PA1 (commissioning chip) | ADC channel assignment not yet verified |
| Valve relays | PD7 (2-way vent), PD10 (3-way) plus PD14, PD15 spare | 4-channel module, 2 snubbers |
| Gauge lines | PD0, PD1, PD4, PD5, PD6 | Through the 74HCT541 |
| Key lines (5, shared with indicators) | PE4 to PE8 | Internal pull-up; 47 Ohm series; indicator sink current to check |
| Anode-rail gate | PB5 | Open-drain onto a 2N5401 stage; timer AF unverified |
| Buzzer | PB4 | Open-drain onto a 2N5401 stage |
| Water indicator cathode | PA0 | Open-drain |
| Tank level, hot-water knob, steam knob (S6, S7, S8) | PE9, PE15, PC6 | Ground-switched, internal pull-up |
| Flow meter | PA8 | Level handling unsettled (OEM 5 V pull-up) |
| Mains-presence confirm | unassigned | Probably replaced by the BL0942 current reading |

## 5. Sensing

Detailed in `temperature-sensing-front-end.md`. In short:

- **Temperature.** One calibrated PT1000 spike probe in the water at the coffee block outlet before the 3-way valve is the key sensor, read through a 4.7 kOhm low-TCR divider on the H743's 16-bit ADC, ratiometric to the ADC reference, averaged over whole mains cycles synchronised to the zero-cross capture. The block NTCs and the wand disc NTC are kept as casing sensors and calibrated in place against the water probe under steady low flow. Two flat PT1000 chips are commissioning tools only. No MAX31865.
- **Pressure.** Brew: a direct tee on the cold side between the new brew OPV and the block. Steam: a hairpin-clip tee between the steam block and the manual knob valve, with a downhill PTFE drop leg to the sensor.
- **Flow.** The OEM flow meter on the coffee pump's suction line; none on the steam path.
- **Energy.** BL0942 meters report current to the controller, which confirms that a heater command was obeyed and detects a stuck-on SSR.

## 6. Actuation and control concepts

- **Heaters.** Burst firing through zero-cross SSRs; no phase reference is needed for them (`heater-drive-and-supply-timing.md`). **Open decision:** the switching cadence, whole-cycle (20 ms) bursts or half-cycle, is stated both ways across the files; whole-cycle avoids a DC offset, and a zero-cross SSR can switch no finer than a half-cycle.
- **Pumps.** Standard dimmers time the triac from the shared Z-C and fire it with a DIM pulse, so phase-angle and whole-cycle burst are both available. Which drive suits the steam pump's low flow is open (a bench step test decides it). No steam damper; the controller averages pressure over whole mains cycles to remove stroke ripple.
- **Vent.** The 2-way is normally open and energised closed whenever the coffee pump is pumping through the block: the 30-40 s shot, and also hot-water draws, the pre-shot flush and the dry-fill and identification runs, since an open vent would take the water. It therefore vents at end of brew, on power loss or fault, and whenever the block heats with no flow path. A per-mode vent table (idle, flush, shot, hot water, steam, fault) is still to be written.
- **Steam.** The S8 microswitch says steam mode is engaged; a candidate interlock allows the steam heater only while the knob is open. **Open decision:** the firmware's ready temperature (125 C held while nothing is drawn) heats against a closed knob, which contradicts F10 (heater off when no steam is drawn) and is the open trapped-pressure case. The dry-steam limit follows from the heater power and the energy to turn feed water into dry steam, not from an outlet temperature probe.
- **Brew.** The dry-fill and idle-drain behaviour (the block drains downhill when idle) is to be measured; the pre-shot flush, the identification runs and the cold-plug dip are commissioning tests.

## 7. Safety layers

- OEM thermostats (coffee 110 C, steam 200 C, pump 110 C) and thermal fuses stay in series with their loads. [PL]
- Mains inlet: T10A slow-blow fuse, filter, MOV; a 1-2 A branch fuse on each dimmer's live; T2A on the IRM supply recommended, not required (`mains-inlet-protection.md`). **Open decision:** the trunk (1.0 mm2, 10 A), the T10A fuse and the FN9222 (10 A at 50 C) sit at or under the machine's own worst case (9.95 A at 240 V, 10.5 A at 253 V); the valve branches (0.75 mm2 flex) have no branch fuse.
- Valve vent: normally open, fails to the venting state.
- OPVs: steam OPV on the pump (and on the block if no check valve lies between); a new brew OPV.
- Defaults while the controller is in reset: pull-downs hold the SSRs and dimmers off; the valve relays' pulls are intended to hold them de-energised, which depends on the relay module's input polarity and on 5 V tolerance of the driving pins, both still to verify (`passive-and-drive-components.csv`, `open-items.md`).
- **Open:** pressure trapped in the steam block heating against the closed knob valve (needs the inspection of the check-valve order and probably a firmware interlock and possibly a hot-side relief valve); the proof-of-life interlock and master relay are deferred.

## 8. Power

Typical-based 5 V budget is about 0.53 A (worst case with the stepper maximum about 0.66 to 0.86 A) (many items estimated); the IRM-10-5 (10 W, 2 A) derates to about 75% at 60 C and 50% at 70 C; the board's own DC-DC makes the 3.3 V, 1 A max. The enclosure ambient is unmeasured.

## 9. Physical

The control cavity is 130 x 130 x 28 mm (owner statement; an older note says 25 mm of cavity, to be measured); the BOM estimate with everything inside is roughly 80% full, which it calls too tight with a barrier. Proposed, not decided: mount the SSRs direct to the metal side wall in the bottom zone near the pumps (no source says the wall is earthed; each SSR dissipates about 5-6.5 W, which conflicts thermally with the IRM-10-5's derating from 50 C). The H743 sits on four 1x22 female header pieces (2.54 mm pitch; inner columns 33.02 mm apart, outer 38.10 mm, mounting holes 35.56 x 61.38 mm); keep the USB-C end and the NRST/BOOT0/K1/SWD end reachable. Stack height is about 22 mm. Mains-side island gaps on the hand-cut IRM carrier are 4-5 mm or more, then conformal coat with the pins masked.

## 10. Verification and commissioning

A bench bring-up of the low-voltage board on a bench supply comes first, then the mains modules one at a time with the loads unplugged, behind an RCD. The seven commissioning tests are in `temperature-sensing-front-end.md` (calibration, NTC calibration, cold-plug dip, identification runs, noise and ripple capture, dry-fill, mixed-cup check). The machine inspection list is in `open-items.md`.

## 11. Graph position

Nothing from this design is authored. `REQ-MEASUREMENT-001.C7` still has no `addresses` link. The decisions that need authoring are listed in `open-items.md`.
