# Open items

Ranked by what blocks what. Written 2026-10-12. Status words are defined in `decisions.md`. Nothing here is in the graph.

## A. Machine inspection (one session with calipers, a pitch gauge, a torch and a meter)

These settle most of the hydraulic unknowns and should be done before any plumbing part is ordered.

1. Follow the drain tube from the drip tray: confirm the 3-way (block to group, hot water when energised) and the 2-way (second block outlet to the drain) roles, and whether the OEM 2-way is normally open (decision D6, fact F2).
2. Trace the steam pump outlet: pump, check valve, OPV tee, block inlet. Note where the steam OPV's discharge tube ends and read its setting off the part (fact F6, F7).
3. Open both block inlet fittings and look for a check valve (fact F9).
4. Measure threads and tube sizes: block outlets and inlets, pump outlets, the steam line, and the OEM PTFE or silicone tube OD and ID. The 3-way and 2-way coils' voltage and power are recorded in `../connector-pinouts.md` (230 V AC, 9-13.5 VA marked); read the valves' port threads.
5. Lift an NTC clamp bracket to confirm how the NTC is mounted (an inference from photos so far).
6. Panel and gauge: with a meter on the OEM main-board connector, a pressed key should read about 1 kOhm plus 47 Ohm to ground (fact F14); measure the anode-rail voltage and the indicator element currents; identify the buzzer type (resistance, then a bench supply through a series resistor to find polarity, voltage and current); pin 1 on both harness connectors is now defined (`../connector-pinouts.md`).
7. Flow meter: output type (open-collector, Hall, push-pull) and level into the controller.
8. Observe whether the OEM preheats the steam block with the knob shut. Settled by owner statement, 2026-10-15: it does (fact F10, as superseded); confirm on the machine.
9. Observe how much the idle block drains between shots (fact F3).

## B. Bench tests and datasheet checks

- Scope the dimmer Z-C output: type and pulse width (unpublished).
- Steam pump drive: step test, output per 60 s at stepped phase power against bursts (decision D4).
- BL0942 module isolation measurement, then BOM rows for the meters (decision D17).
- XDB401 I2C variant: output rate, address (EEPROM-programmable, to confirm), thread.
- Supplier rating of the PTFE tube at 160 to 200 C, or use the stainless capillary or 4 mm metal tube.
- DS12110 checks: 5 V tolerance for PB4, PB5, PA8, PD7, PD10, PD14, PD15, PA0 and PE4 to PE8; alternate functions for PA1, PA4 and PA6 (ADC channels), PA10 (TIM1_CH3) and PB5 (TIM3_CH2); H743 pin sink current against the key-line indicator current (the indicator current is pending with the forward voltage, SOL-HW-RETAINED-DEVICE-REMAINING-CHARACTERISTICS-RECORDED).
- Relay module input polarity from its schematic (on an active-low module a 3.3 V high may not turn the optocoupler off); confirm the 4-channel module and the cavity fit.
- 5 V tolerance in DS12110 also for PD7, PD10, PD14, PD15 (relay inputs), PA0 (water indicator cathode) and PE4 to PE8 (key lines pulled toward the 5 V rail through LEDs).
- The solenoid valves' pressure rating (a sibling JLT listing says 1.0 MPa, unverified) against the brew OPV setting.
- The VID66-08 reset level at boot (the allocation has no defined RST level) and whether the gauge step clocks need timer outputs.

## C. Design decisions awaiting the owner

- The supply cord, appliance inlet and inlet filter sit ahead of the inlet fuse, protected only by the building's breaker (up to 20 A). The chosen filter is rated 15 A and its IEC C14 coupler 10 A, both above the machine's own draw (at most 10.5 A at 253 V) and below the breaker. This section is held to fault withstand until the breaker clears rather than to the breaker's rating, the ordinary arrangement for an appliance drawing under 10 A; the owner to confirm that basis (`controller-board-design-constraints.md` § Fault current, `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`).
- PCB go or no-go (`pcb-plan.md`).
- Whether the BL0942 current reading replaces the mains-presence confirm (D20).
- The steam block trapped-pressure case: an S8 interlock on the steam heater, a hot-side relief valve, or both.
- Whether to copy the OEM `Q7` and `Q8` stages as proposed (D18).
- Steam pump drive (D4).
- **Mains chain rating margin.** Resolved by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`: filter FN9222-15-06 (15 A at 50 C), trunk at least 1.5 mm2 (WB1568), T10A unchanged, one shared TR5 fuse on the valve branches. Remaining to confirm: the 15 A filter's coupler rating (IEC C14 is 10 A), its termination type, the TR5 series.
- **Heater switching cadence:** whole-cycle (20 ms) bursts or half-cycle; the files disagree.
- **Steam heater with the knob shut:** the firmware's 125 C ready temperature heats against a closed knob, against F10 and the open trapped-pressure case.
- **SSR mounting:** the side wall is proposed, not decided, and conflicts thermally with the IRM-10-5's derating.
- **A vent state per mode table** (idle, flush, shot, hot water, steam, fault).
- Whether to fit the optional test tee on the vent branch.

## D. Graph work (nothing authored)

Each node must be read with `show` before linking, and existing coverage checked first.

- A decision adding the brew pressure transducer; `REQ-MEASUREMENT-001.C7` has no inbound `addresses` link. The precedent is `DEC-STEAM-PRESSURE-SENSOR-ADDED`.
- A decision adding the outlet water temperature probe (the declared sensing list in `SOL-CHANNEL-ENUMERATION-CORRECTED.C1` is three NTCs). `DEC-DEVICE-RETENTION-BOUNDARY` is unaffected because the NTCs stay.
- A decision on the steam pressure tap position and the hot-side pressure question.
- The vent policy, and the steam damper decision.
- Upstream protection is now declared (`reference-machine.md` § Supply: a circuit breaker of up to 20 A, project assumption) and which device interrupts which fault is decided by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`; the fault-current figures the wiring must be rated for are in `controller-board-design-constraints.md` (`REQ-ELECTRICAL-INSTALL-001.C7`, `OBL-ELECTRICAL-THERMAL-SAFETY-001.C8`). The wiring authority is named there too (`.C9`).
- A commissioning identification deliverable (`REQ-STATE-ESTIMATION-001.C6`).
- `SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET`'s premise "no sensor reports it" is partly dated; the group-side water temperature is still reconstructed.
- The graph has no way to hold a solution waiting for an operator to build it (named in the old working README).
- Settled 2026-10-13, kept for the record: whether a measured supply period is admissible evidence for the supply frequency. No one-off measurement is asked for any more. `REQ-MACHINE-CONFIGURATION-001.C9` has the declaration state the supply's nominal from its governing standard, which `reference-machine.md` § Supply now does (50 Hz), and has anything that depends on the supply's timing read it live while running. The Z-C capture is that live reading; its accuracy is still unpublished, which bears on the crossing offset `DEC-MAINS-PHASED-ACTUATION-BELOW-SEAM` leaves unbounded, not on the declared frequency.
- Whether a surge-suppression criterion should exist at all: nothing in the graph requires transient protection (`OBL-ELECTRICAL-THERMAL-SAFETY-001.C8` is about fault current), so the MOV is fitted on judgement alone. See `mains-inlet-protection.md`.
- Whether the machine has a hard mains switch at all: the five front-panel keys are logic channels, not a mains break. Establish by inspection.
- **Overtaken by `DEC-PROOF-OF-LIFE-INTERLOCK-IN-FIRST-HARDWARE` (2026-10-18): the interlock is built into the first controller hardware, not deferred.** The proof-of-life interlock, deferred: downstream zero-cross sensing can verify that the master relay opened but cannot be the trip path, since `REQ-SAFETY-CHAIN-001` requires the chain to owe nothing to the controller or firmware.
- The accuracy-versus-speed axis for temperature sensing, which nothing in the graph rules on, and recalibration as a maintenance activity, which follows from using a sensor that drifts.

- **Stale slice files are cited by the graph.** 22 spec files cite `docs/sunbeam-em7000/controller-io.md`, 6 cite `component-specification.md`, 2 cite `controller-io-bom.csv` and 1 cites `control-board-electrical-requirements.csv` (evidence nodes such as `EVD-SOL-CHANNEL-MEASUREMENT-FIGURES.C1-INSPECTION`, solutions such as `SOL-CONTROLLER-CHANNEL-ENUMERATION`, and `DEC-U8-BOARD-RETENTION-UNVERIFIED`); `reference-machine.md` is cited by 24 and `connector-pinouts.md` by 5. Those nodes verified the old content. Deleting or rewriting the old files would orphan or invalidate that evidence. The graph work has to decide, node by node, whether to supersede the cited nodes against the refreshed files in this folder, repoint them, or leave the old files as the historical record. Read each node with `show` first.

## E. Housekeeping and unresolved items from the refresh

- The mainboard's own height (an estimate; the cavity is 34.5 mm deep, with 23.4 mm usable above the original board within about 2 mm of a wall and at least 28 mm where its tallest part stood: `../reference-machine.md` § Controller enclosure as found, which supersedes the 25 mm note) and the dimmer module's height (footprint 50 x 16 mm).
- The 10 A chain margin is resolved by `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE` (15 A filter, trunk above the fuse); the 15 A filter's coupler rating is unverified and its termination type is not recorded.
- Whether the IRM-10-5 has an internal fuse (the old text and the BOM disagreed).
- Nothing specifies ferrules for the screw terminals, the FN9222's termination type, the earth conductor and chassis stud, or the temperature ratings of PVC wire and flex near the hot blocks.
- The EARU SSR-40DA's zero-cross type, isolation rating, package and fail-short behaviour are unconfirmed; the dimmer's Z-C is believed full-wave but unmeasured; the BL0942 ZX delay and module isolation are unknown.
- Heater switching cadence is stated as half-cycle burst-fire in the BOM and as whole-cycle granularity in the pin allocation; reconcile against `heater-drive-and-supply-timing.md`.
- PC6 is both the S8 switch input and the optional USART6 TX; it only matters if the BL0942 meters need a transmit line.
- Whether the gauge step clocks need timer outputs (the allocation assigns plain GPIO).
- Whether the OEM valves are kept or the BOM's valve rows are replacements; the owner's statement on the three-way valve (a planned replacement, nothing bought) is recorded in `../controller-board-design-constraints.md` § Purchases ahead of verification, and the question stands for the other valve; the BOM is in AUD against a declared 250 USD figure, so no total is given.
- Whether the graph has changed since the old text on `DEC-PREHARDWARE-TARGET-FAMILY`, the zero-cross enumeration row and `SOL-CHANNEL-ENUMERATION-CORRECTED.C4`.

- Harness connector families are not identified (pitch, ways and first pin of every retained connector are recorded in `../connector-pinouts.md`); panel and gauge parts are not specified.
- The rail-gate and buzzer stage parts are in the BOM; the relay module's snubber count is 2.
- All prices are estimates; no catalogue numbers have been checked against stock.
- The old `controller-selection-working/` folder has been removed (git history, commit `07913f4`). The four stale slice files in `docs/sunbeam-em7000/` (`controller-io.md`, `component-specification.md`, `controller-io-bom.csv`, `control-board-electrical-requirements.csv`) are superseded in content by this folder but are cited by path from graph nodes, so they stay until the graph is dealt with (section D).
