# Constraints record of the circuit review proof design

**NOT FOR MANUFACTURE.** This is the constraints record of `circuit-review-proof`, a throwaway design made only to prove the schematic review of `docs/board-design-method.md`. It is synthetic: no machine has these figures. They are stated here so that the steps of the method have a record to read their figures from, as a real board's steps read them from its machine's constraints record. The design is marked `NOT_FOR_MANUFACTURE` `true` and is never ordered. The separation figures are in `separation-basis.yaml`, the derating shares in `derating-policy.yaml`, the pin limits in `pin-limits.yaml`.

| Figure | Value | What it bounds |
|---|---|---|
| Mains supply | 207 V to 250 V rms, 50 Hz; peak at most 353.6 V | The supply at J1, the declared span of every circuit run from `/MAINS_L` |
| Heater load continuous current | 0.3 A rms | The highest continuous current on `/MAINS_L_IN`, `/MAINS_L_FUSE`, `/MAINS_L`, `/MAINS_HEAT_SW` and `/MAINS_N` |
| Declared fault current | 5.0 A rms | The fault current at J1 the mains-side conductors must survive until the fuse F1 clears it: a short on the heater output at J2 or across Q1, limited by the supply wiring |
| Heater trigger delay | at most 18 degrees of the supply cycle after a zero crossing (1 ms at 50 Hz) | How late in a half-cycle the heater triac Q1 begins to conduct, at the lowest mains voltage |
| 5 V supply input | 4.75 V to 5.25 V | The supply entering at J6 pin 1, the declared span of every circuit run from `+5V` |
| 5 V supply continuous current | 0.2 A | The highest continuous current on `/+5V_IN` and `+5V` |
| Logic rail continuous current | 0.1 A | The highest continuous current on `/+3V3_REG` and `+3V3` |
| Status LED current | 0.2 mA to 6 mA | The current in the status LED D1 over the logic rail's span and the temperature range |
| Sensor input settling | within 1/4096 of a step (one count of a 12-bit conversion) in at most 2 ms | The sense input at J5: the time from a step at J5 pin 1 until the voltage at `/SENSE_ADC` is within one count of its final value |
| Sensor source resistance | at most 100 ohm | The resistance J5 pin 1 is driven from |
| Resistor tolerance | 1 % | Every resistor on the board, over life and temperature |
| Ceramic and tantalum capacitor tolerance | 20 % | Every capacitor on the board, over life and temperature, DC bias aside |
| Ambient temperature | 0 °C to 50 °C | The air around the built board, for every circuit on it |
| Board material | withstands 288 °C for 20 s without delamination; maximum temperature in service 105 °C | The laminate, for the fault withstand of copper (Shengyi S1141 data sheet, thermal stress row, for the 288 °C figure; the 105 °C is this record's own synthetic figure, which no data sheet read states) |
| Solder | melts no lower than 217 °C | The joints at the ends of a track |
| Finished outer copper | 1 oz, at least 35 µm thick | Both outer copper layers |
| Mains conductor | track width 0.5 mm on the `Mains` net class | The narrowest copper on `/MAINS_*` nets |
| Mains | present | The board carries mains-referenced nets: `MAINS` is `present`, and the `Mains` net class holds every `/MAINS_*` net |
| Protective device | fuse F1, 500 mA time-lag, 250 VAC | The device ahead of every mains conductor; no other protective device is declared on this board |
| Off-board protective chain | the heater assembly carries its own series thermostat and thermal fuse, outside this board and reached through J2 | A device that acts on the heater's temperature with no part of this board or its controller involved; it bounds the heater whatever state the board's switching parts are in, and protects the heater, not the board's conductors |
| Mains surge | 2 kV open-circuit 1.2/50 µs line-to-neutral combination wave through an effective source impedance of 40 Ω, so 50 A peak on the 8/20 µs short-circuit waveform; overvoltage category 2 | The surge at J1 that `/MAINS_L`, `/MAINS_N` and every part behind them are judged against. A synthetic declaration of this proof design: no standard is cited and no table is reproduced |
| Leakage limits | protective-conductor current at most 1.0 mA with the protective earth connected; touch current at most 0.25 mA with the protective earth open; protection class I; the leakage limit is applied at 250 V and 50 Hz | What the Y capacitors C2 and C3 and every other part from a mains conductor to `/MAINS_PE` are held to. Synthetic figures of this proof design: no standard is cited |
| Static discharge | ±4 kV contact and ±8 kV air discharge to the conductors a person reaches: J3 (the sensor connector, reached by the harness in normal use). J4, J5, J6 and the test points are reached only while the board is open on a bench by a person under static-controlled handling, and J1 and J2 are mains terminals behind the enclosure | Which conductors the clamp of ESD-1 is required on and at what level. Synthetic figures of this proof design: no standard is cited |
| Emission limit | conducted emission at the inlet at most 60 dBµV quasi-peak from 150 kHz to 500 MHz, the filter C1 C2 C3 giving at least 12 dB against the heater's switching spectrum; no emission limit is declared for the controller's I2C and SWD lines, whose edges are judged and left at the controller's own (SWD at most 6.6 ns; SDA and SCL as slow as the pull-ups R11 R12 allow, about 0.4 µs) | What the inlet filter, the snubber R1 C4 and the edge rates of the lines that leave the board are judged against. Synthetic figures of this proof design: no standard is cited |
| Heater load inductance | at most 1 mH (a resistive element and its wiring) | The load of Q1, for the snubber R1 C4 |
| Sensor bus | I2C standard mode, 100 kHz; rise time at most 1000 ns; total bus capacitance at most 100 pF (the sensor, connector J3 and the run of wire together); the sensor's output low level at most 0.4 V at 3 mA; pulled up to `+3V3` only | The speed mode, capacitance and sink limits R11 and R12 are sized against. The figures are this record's own declaration of the mode; no bus specification table is reproduced |
| Debug probe | a target-referenced probe: it drives SWDIO, SWCLK and NRST only while its reference input, J4 pin 1 (`+3V3`), senses the rail, and releases its lines when the reference is absent, as when JP3 is removed | The state of J4's driven lines while U4 is unpowered |
| Sense input range | J5 pin 1 carries 0 V to 3.3 V in service and at most 5.25 V in a fault (the 5 V supply mis-wired to it); the sensor is supplied from this board's `+3V3` only, so it is unpowered whenever the controller is | The voltage `/SENSE_IN` can reach, for the controller pin behind R13 |
| Converter sampling | 500 samples per second on `/SENSE_ADC` (a 2 ms period, firmware-configured); the highest frequency of interest is 10 Hz (a slowly changing sensor) | What the filter R13 C12 is judged against with the converter's datasheet figures |
| Supply rise and inrush | the 5 V supply at J6 rises in at least 1 ms and is limited to 1 A; the `+3V3` rail behind JP3 is connected only with the board unpowered and rises in at least 100 µs; the mains inlet has an installation source impedance of at least 1 Ω and the board may be connected at any phase of the supply | The rise time, source limit and source impedance the inrush of SUPPLY-1 is computed from |
| Layer count | 4 | Copper layers F.Cu, In1.Cu, In2.Cu and B.Cu |
| Board outline | at most 240 mm by 135 mm | The board's size |
| Board manufacturer | JLCPCB | Whose stated limits, `docs/board-manufacturer-jlcpcb.md`, the board-wide minimums are read from, at 4 layers and 1 oz |
