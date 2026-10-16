# Bring-up provisions of the method proof design

**NOT FOR MANUFACTURE.** What `method-proof`, a throwaway design made only to prove `docs/board-design-method.md`, carries so that its first spin can be diagnosed: a test point on every rail and key signal, an isolating link in every rail, and a means to limit first power. Net names are as the schematic's KiCad-format netlist writes them (`kicad-cli sch export netlist`): the nets of the top sheet written by a label carry a leading slash, the nets a power symbol names do not.

The rails, from the netlist: `+5V` and `+3V3` (nets a power symbol names), `/+5V_IN` (the net between the input connector and the regulator, which the supply input feeds before the board's first regulator) and `/+3V3_REG` (U1's output, a `power_out` pin). Ground is `GND`. No net is a producer-only net: every rail net feeds a part other than the one producing it, and U2 has no internal-regulator output or reference brought out for a capacitor.

| Rail, producer-only net, key signal or first power | Net | Test point | Isolating link | What it is for |
|---|---|---|---|---|
| Rail `+5V`, fed by the supply input J1 | `/+5V_IN`, `+5V` | TP1 | JP1 | Source side `/+5V_IN` carries only J1 pin 1 (the supply input, with no series protective part, the constraints record declaring none), TP1 and JP1 pin 1. Load side `+5V` carries JP1 pin 2, U1's input VI and its input capacitor C1, R1 (the status LED's resistor) and J2 pin 1, through which power leaves the board to an off-board load. TP1 measures the supply with every load disconnected; JP1 pin 2 reaches the loads. JP1 is a two-pin header with a shunt, rated 4.3 A per pin (Samtec SNT, *Specifications*), above the 0.5 A continuous current of the constraints record |
| Rail `+3V3`, made by U1 | `/+3V3_REG`, `+3V3` | TP2 | JP2 | Source side `/+3V3_REG` carries only U1's output VO, its output capacitor C2, TP2 and JP2 pin 1. Load side `+3V3` carries JP2 pin 2, U2's supply pin VDD and its capacitor C3, U2's NRST pin (tied to the rail), TP3 and J2 pin 2, through which power leaves the board to an off-board load. JP2 is a two-pin header with a shunt, rated 4.3 A per pin, above the logic rail's 0.1 A |
| Key signal: the status LED drive stage's control input | `/LED_K` | TP4 | — | The node where D1's cathode meets U2's PA0, which sinks the LED current: with TP4 a multimeter reads whether PA0 pulls low and an oscilloscope reads it switching, so bring-up can tell whether the LED stage works without probing a pad of D1 |
| Key signal: the controller's reset | `+3V3` | TP3 | — | U2's NRST pin, which the TI datasheet's table of unused pins says to take to VCC ("NRST ... Pull high to VCC or the device cannot start"); it is joined to the 3.3 V rail directly, so TP3 on that rail shows the reset input held high |
| First power: supply input J1 pin 1 | `J1.1` on `/+5V_IN` | — | JP1 | The current-limit means is JP1's position: with its shunt removed, a series resistor or a lamp is fitted in its place and wired to its two pins, between J1 pin 1 (with only TP1 between them) and everything the input feeds (U1, C1, R1, J2 pin 1). With a 100 ohm resistor the input draws at most 5.25 V / 100 ohm = 52.5 mA into a short on `+5V`, the highest input voltage of the constraints record over the resistance. It needs a multimeter, a soldering iron and a resistor |

## Key signals the schematic does not carry

- **Clock**: U2 runs from its internal oscillator, so the schematic carries no clock net.
- **Programming interface**: the brief gives the board no programming header. U2's SWDIO (PA19) and SWCLK (PA20) pins are left unconnected under no-connect flags, so there is no programming interface net to give a test point.

## Connector, terminal and header pins

| Pin | Net | Class | Why |
|---|---|---|---|
| J1.1 | `/+5V_IN` | supply input | The 5 V supply enters the board here and feeds, through JP1, U1's input, C1, R1 and J2 pin 1 |
| J1.2 | `GND` | ground or return | The return of the 5 V supply |
| J2.1 | `+5V` | power-leaving | The board's 5 V output to an off-board load, fed from the `+5V` load side; the schematic gives no path by which a source is meant to power the board through it |
| J2.2 | `+3V3` | power-leaving | The board's 3.3 V output to an off-board load, fed from the `+3V3` load side; the schematic gives no path by which a source is meant to power the board through it |
| J2.3 | `GND` | ground or return | The return of the outputs |
| J3.1 | `/PA1_HDR` | signal | U2's PA1 brought out to the header; it feeds no power |
| JP1.1 | `/+5V_IN` | signal | The source-side pin of the 5 V isolating link; power reaches it only through J1 |
| JP1.2 | `+5V` | signal | The load-side pin of the 5 V isolating link |
| JP2.1 | `/+3V3_REG` | signal | The source-side pin of the 3.3 V isolating link; power reaches it only from U1 |
| JP2.2 | `+3V3` | signal | The load-side pin of the 3.3 V isolating link |
