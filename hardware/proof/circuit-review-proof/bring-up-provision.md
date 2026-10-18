# Bring-up provisions of the circuit review proof design

**NOT FOR MANUFACTURE.** What `circuit-review-proof`, a throwaway design made only to prove the schematic review of `docs/board-design-method.md`, carries so that its first spin can be diagnosed: a test point on every rail and key signal, an isolating link in every rail, and a means to limit first power at every supply input. Net names are as the schematic's KiCad-format netlist writes them (`kicad-cli sch export netlist`): the nets of the top sheet written by a label carry a leading slash, the nets a power symbol names do not.

The rails, from the netlist: `+5V` and `+3V3` (nets a power symbol names), `/+5V_IN` (the net between the 5 V input connector and the regulator), `/+3V3_REG` (U3's output, a `power_out` pin), and the mains line `/MAINS_L_IN`, `/MAINS_L_FUSE` and `/MAINS_L`. Ground is `GND`. The mains neutral `/MAINS_N` and the protective earth `/MAINS_PE` are return nets and carry no link; `/MAINS_HEAT_SW` is the switched heater output of Q1 and is fed only through it. No net is a producer-only net: every rail net feeds a part other than the one producing it, and U4 has no internal-regulator output or reference brought out for a capacitor.

| Rail, producer-only net, key signal or first power | Net | Test point | Isolating link | What it is for |
|---|---|---|---|---|
| Rail `+5V`, fed by the supply input J6 | `/+5V_IN`, `+5V` | TP2 | JP2 | Source side `/+5V_IN` carries only J6 pin 1 (the supply input, with no series protective part, the constraints record declaring none on this input), TP2 and JP2 pin 1. Load side `+5V` carries JP2 pin 2, U3's input and the input capacitors C5 and C7, and R5 (the heater drive's LED resistor). TP2 measures the supply with every load disconnected; JP2 pin 2 reaches the loads. JP2 is a two-pin header with a shunt, rated 3 A, above the 0.2 A of the constraints record |
| Rail `+3V3`, made by U3 | `/+3V3_REG`, `+3V3` | TP3 | JP3 | Source side `/+3V3_REG` carries only U3's output, its output capacitor C6, TP3 and JP3 pin 1. Load side `+3V3` carries JP3 pin 2, U4's supply pin and its capacitors C8, C9 and C10, U5's supply pin, the pull-ups R8, R11 and R12, and J3 pin 1 and J4 pin 1, through which power leaves the board to the sensor and to the debug probe. JP3 is a two-pin header with a shunt, rated 3 A, above the logic rail's 0.1 A |
| Rail `/MAINS_L`, fed by the supply input J1 | `/MAINS_L_IN`, `/MAINS_L_FUSE`, `/MAINS_L` | TP1 | JP1 | Source side `/MAINS_L_IN` and `/MAINS_L_FUSE` carry only J1 pin 1 (the supply input), the fuse F1 as its series protective part, TP1 on `/MAINS_L_FUSE` and JP1 pin 1. Load side `/MAINS_L` carries JP1 pin 2, the varistor RV1, the X2 capacitors C1 and C4, the Y capacitor C2, and Q1's main terminal 1. JP1 is a wire link in through-hole pads, 1 mm² of copper, rated 300 V open and for the declared fault by the circuit-proof record's row 4. TP1 and JP1 are mains copper in the `Mains` net class |
| Key signal: the heater drive stage's control input | `/HEAT_CMD` | TP7 | — | U4's output PA2 into Q2's gate, held low by R6: with TP7 a multimeter reads whether the controller commands the heater, without probing a pad of Q2 |
| Key signal: the sensing front end's output | `/SENSE_ADC` | TP8 | — | The node after the filter R13 C12, where U4's converter input reads it: with TP8 bring-up reads the filtered sensor voltage |
| Key signal: the safety interlock | `/WD_RESET` | TP9 | — | U5's reset output, which drives Q3's gate in series with Q2: it shows whether the watchdog allows the heater drive |
| Key signal: the controller's reset | `/NRST` | TP4 | — | U4's NRST pin, pulled up by R8 and brought out on J4 pin 4 |
| Key signal: the programming interface, data | `/SWDIO` | TP5 | — | U4's SWDIO, brought out on J4 pin 2 |
| Key signal: the programming interface, clock | `/SWCLK` | TP6 | — | U4's SWCLK, brought out on J4 pin 3 |
| First power: supply input J6 pin 1 | `J6.1` on `/+5V_IN` | — | JP2 | The current-limit means is JP2's position: with its shunt removed, a series resistor or a lamp is fitted in its place and wired to its two pins, between J6 pin 1 (with only TP2 between them) and everything the input feeds (U3, C5, C7, R5). With a 100 ohm resistor the input draws at most 5.25 V / 100 ohm = 52.5 mA into a short on `+5V`, the highest input voltage of the constraints record over the resistance. It needs a multimeter, a soldering iron and a resistor |
| First power: supply input J1 pins 1 and 2 | `J1.1` on `/MAINS_L_IN`, `J1.2` on `/MAINS_N` | — | JP1 | The current-limit means is JP1's position: with its wire link removed, a 60 W mains lamp is fitted in its place and wired to its two through-hole pads, between J1 pin 1 (with only F1 and TP1 between them) and everything the input feeds (RV1, C1, C2, C4, Q1). A 60 W, 230 V lamp has 230² / 60 = 882 ohm, so the input draws at most 250 V / 882 ohm = 0.28 A into a short on the switched side. It needs a multimeter, hand tools and a lamp; the fuse is protection, not the means |

## Key signals the schematic does not carry

- **Clock**: U4 runs from its internal oscillator, so the schematic carries no clock net.

## Connector, terminal and header pins

| Pin | Net | Class | Why |
|---|---|---|---|
| J1.1 | `/MAINS_L_IN` | supply input | The mains live enters the board here and feeds, through F1 and JP1, the heater triac Q1, the varistor and the capacitors |
| J1.2 | `/MAINS_N` | supply input | The mains neutral enters here; it is the return of the same supply and feeds the heater return and the capacitors C1, C3 and the varistor |
| J1.3 | `/MAINS_PE` | ground or return | The protective earth, joined to the Y capacitors C2 and C3 |
| J2.1 | `/MAINS_HEAT_SW` | power-leaving | The heater's live feed, switched by Q1; the board supplies the heater and nothing off the board can power it |
| J2.2 | `/MAINS_N` | ground or return | The heater's return to the mains neutral |
| J3.1 | `+3V3` | power-leaving | The board's 3.3 V to the sensor on J3; the schematic gives no path by which a source is meant to power the board through it |
| J3.2 | `/SDA_J` | signal | The sensor bus data line, through the series resistor R9 and clamp D2 |
| J3.3 | `/SCL_J` | signal | The sensor bus clock line, through the series resistor R10 and clamp D2 |
| J3.4 | `GND` | ground or return | The return of the sensor connector |
| J4.1 | `+3V3` | power-leaving | The board's 3.3 V as the debug probe's voltage reference; the schematic gives no path by which a probe is meant to power the board through it |
| J4.2 | `/SWDIO` | signal | U4's debug data |
| J4.3 | `/SWCLK` | signal | U4's debug clock |
| J4.4 | `/NRST` | signal | U4's reset |
| J4.5 | `GND` | ground or return | The return of the debug header |
| J5.1 | `/SENSE_IN` | signal | The sensor input to the filter R13 C12; it feeds no power |
| J5.2 | `GND` | ground or return | The return of the sensor input |
| J6.1 | `/+5V_IN` | supply input | The 5 V supply enters the board here and feeds, through JP2, the regulator U3, its input capacitors and R5 |
| J6.2 | `GND` | ground or return | The return of the 5 V supply |
| JP1.1 | `/MAINS_L_FUSE` | signal | The source-side pin of the mains isolating link; power reaches it only through J1 and F1 |
| JP1.2 | `/MAINS_L` | signal | The load-side pin of the mains isolating link |
| JP2.1 | `/+5V_IN` | signal | The source-side pin of the 5 V isolating link; power reaches it only through J6 |
| JP2.2 | `+5V` | signal | The load-side pin of the 5 V isolating link |
| JP3.1 | `/+3V3_REG` | signal | The source-side pin of the 3.3 V isolating link; power reaches it only from U3 |
| JP3.2 | `+3V3` | signal | The load-side pin of the 3.3 V isolating link |
