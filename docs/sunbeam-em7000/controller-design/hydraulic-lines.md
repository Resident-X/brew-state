# Hydraulic lines, tank to outlet

Every device in order on each line of the replacement design, with where it comes from. It is built from `reference-machine.md`, the service manual parts list and schematic, the owner's statements of 2026-10-11/12 and the replacement design (`decisions.md`). Where the files do not establish an item or its position it says **UNESTABLISHED**; it does not fill the gap from typical coffee-machine practice.

Provenance tags: **[PL]** service manual parts list, position not stated; **[SCH]** read from the service manual circuit diagram; **[OWN]** owner statement, not confirmed on the machine; **[INF]** inferred; **[ADD]** added by the replacement design; **[WEB]** published, unverified. "Retained" means the base-machine part stays; "new" means the base machine lacks it.

## Brew line (group head)

1. Water tank, 3 L. [PL] Retained.
2. Tank level sensor, magnet/reed, schematic `S6` / `WAT`, read as a controller input (PE9). [SCH][OWN] Wiring route not bench-verified. Retained.
3. Flow meter on the suction line, about 5-7 cm ahead of the coffee pump, below the tank's water level. [OWN] Three-pin `CZ1`, signal held to VCC5 by 2 kOhm, output type probably open-collector or Hall [SCH][INF]; make, pulses per litre unknown. Retained; controller input PA8. No flow meter on the steam path.
4. Coffee pump, Ulka EP5, 15 bar, 48 W, outlet G1/8 [WEB]; it serves brew and hot water. [PL][OWN] Contains an internal check valve. [OWN] Driven by a Standard dimmer. Retained.
5. Noise damper assembly on the coffee pump (the parts list's name for the damper). [PL][OWN] The brew pump has a damper. Retained.
6. **Brew OPV, discharging to the drip tray.** [ADD] The base machine has no OPV on the brew pump [OWN]. Position (our choice): between the pump and damper and the block, cold side. Setting TBD: above the highest profile pressure, below the pump maximum, the solenoid valves' rating (a sibling JLT listing says 1.0 MPa [WEB], unverified) and the XDB401 1.2 MPa overload. New.
7. **Brew pressure tap**: a direct tee, no leg, with an XDB401 1.2 MPa. [ADD] Between the OPV and the block. New.
8. Coffee thermoblock, about 1 kW, thermistor `EM70025` (NTC), thermostat 110 C, thermal-fuse bracket. [PL] Inlet and outlet at opposite ends [WEB, low confidence]. A check valve in the block inlet is **UNESTABLISHED** (none in the parts list or exploded views; to be inspected). The NTC stays as the casing sensor. Retained.
9. **Outlet water probe**: a standard tee used as an elbow at the block outlet; block outlet in one run port, branch on to the 3-way valve, PT1000 spike probe in the opposite run port facing upstream; fitting insulated from the casing. [ADD] Thread unmeasured. New.
10. Three-way solenoid valve, JLT `3T0618W`: de-energised connects the block outlet to the group (brew), energised diverts to the hot water outlet; never closed. [PL][OWN] Coil voltage, power and port thread not established (sibling JLT listing: G1/8 [WEB]). Retained; relay-driven.
11. Brew branch: about 15 cm of PTFE, partly copper, then a tube down the block's open central bore ending in a very hot brass nut, which is the group head outlet. [OWN, from photos] The tube and nut exchange heat with the casing. The OEM tube sizes are unmeasured.
12. Group head, portafilter, basket and puck. [OWN] Nothing is measured downstream of the block. Retained.

**Vent branch.** A second coffee block outlet runs through a brass extension tube (the parts list's `RELIEF ADAPTER BRASS`, part `EM70042`, as read from the manual by a web search) to the two-way solenoid valve `2T0607W` and on to the drain and drip tray. [PL][OWN] The valve is normally open (open to the drain de-energised) and the OEM energises it closed while pumping, so the block and group drain downhill when the machine is not pumping. [OWN][INF] The replacement keeps it closed whenever the coffee pump is pumping through the block (the 30-40 s shot; also hot water; the pre-shot flush; dry-fill and identification runs) (decision D6). While closed the branch is a dead end at block-outlet pressure; a tee on it is the cheap test of the block's pressure drop. [ADD, optional]

## Hot water

Items 1-10 as for the brew line, then the hot water outlet arm. [PL][OWN] The 3-way is near the hot water arm. No hot-water device between the 3-way and the arm is established.

## Steam line

1. Water tank, as above. **How the steam pump draws from the tank, and whether it shares the flow-meter suction line, is UNESTABLISHED.**
2. Steam pump, JYPC-4, 22 W, 230 V. [PL] The fitted variant and its pressure rating are not confirmed (a generic listing says 7 bar, another snippet 5.5 bar, a 110 V listing 1.5 bar [WEB]). Contains an internal check valve. [OWN] Driven by a Standard dimmer. The OEM pulses it in software (menu-adjustable timing). [WEB] Retained.
3. **Steam OPV**, directly on the pump outlet, downstream of the pump's own check valve, opening at about 4-5 bar, discharging to the drip tray. [OWN] Read the setting off the part. Retained. If no check valve lies between it and the block it also caps the block pressure; to be inspected.
4. No pulsation damper (decision D16). [OWN]
5. Steam thermoblock, element about 1 kW (schematic 1000 W; 47.0 Ohm measured, about 1.1 kW at 230 V), soleplate thermistor `EM70020`, thermostat 200 C, thermal fuse 240 C [PL][WEB]. A check valve in the block inlet is UNESTABLISHED. The heater is off when no steam is drawn. [OWN] Retained.
6. **Steam pressure tap**: a normal hairpin-clip tee in the steam line between the steam block and the manual knob valve, a 100-150 mm PTFE drop leg running downhill (matched to the OEM tube size), XDB401 0.5 MPa at the lowest point. [ADD] The leg fills with condensate and seals the steam off the sensor. Upstream of the knob valve, so a closed knob blocks milk suck-back. Hot-side ratings: at least 160 C and 8-10 bar if the OPV caps the block, otherwise the 200 C trip rating (about 15.5 bar absolute). New.
7. Manual steam knob valve (two-way, `STEAM REGULATOR` `EM70019`, as read from the manual by a web search) with microswitch `S8`, which is the only thing that engages steam mode. [PL][OWN] Retained.
8. Steam arm and wand, NTC disc `EM70024` on the wand's exterior, nozzle usually submerged in milk. [PL][OWN] The disc's behaviour is a hypothesis. Retained.

## What this chain still lacks

- The steam pump's suction route (item 1 of the steam line).
- Whether either thermoblock has an inlet check valve, and the order pump, check valve, OPV tee, block inlet on the steam line.
- Where each OPV discharge tube ends; hot water or steam may reach the tray from the steam OPV if it caps the block.
- The hot-water outlet device and the pump thermostat's location.
- The 3-way and 2-way valves' coil voltage and power, port threads, and whether the OEM 2-way is normally open as inferred.
- Thread sizes at the block outlets and inlets, the pump outlets and the steam line, and the OEM tube sizes.
- The flow meter's K-factor and the tank level switch's trip point.
- The solenoid valves' pressure rating (a sibling JLT listing says 1.0 MPa, unverified), which limits how high the brew OPV can be set against a 15 bar pump.
