# Photographs of the machine as found

Photographs of the reference machine, taken by its owner during the as-found inspection (October 2026). The owner releases each into the public domain, on the same terms as the rest of this repository. Each is reduced to about 1600 px on its long side and re-encoded as JPEG; the originals are the owner's.

Two of them are derived, not as taken: `original-board-component-side-aligned.jpg` is the original board's component side, squared up, and `original-board-solder-side-aligned.jpg` is its solder side, mirrored left to right and perspective-warped so that every board point sits at the same pixel as in the component-side image (1602 px wide, 12 px per mm, origin at the lower left, JPEG quality 70). The two were registered on the four mounting holes and 42 matched pads. The four holes agree to within 0.12 mm; the pads have a median disagreement of 0.25 mm and a maximum of 0.73 mm, over 46 scored points. The fit rests on pads visible on both sides: areas of bare board and the board's flex are not constrained, so a position read off the pair away from a pad carries more than the pad figures.

Each photograph supports the entries of the record that cite it by file name.

| File | Shows | Supports |
|---|---|---|
| `lid-underside.jpg` | The inside of the control-cavity lid with a 150 mm steel ruler: the rib grid, the two screw bosses and the raised portion over the DC wiring | `reference-machine.md` § Controller enclosure as found |
| `mains-bundle-entry.jpg` | The mains bundle entering the cavity along the left edge of the original board, including the green-and-yellow conductor | `reference-machine.md`, `connector-pinouts.md` § Mains terminals |
| `mains-terminals-with-ruler.jpg` | The nine mains tabs and their silkscreen labels, `F1`, and the opto-isolators `U4` and `U6`, beside a millimetre ruler | `connector-pinouts.md` § Mains terminals |
| `low-voltage-bundle-entry.jpg` | The low-voltage bundle entering at the top right | `reference-machine.md` § Where each harness enters the cavity |
| `gauge-connector-sp2.jpg` | The 9-way gauge connector `SP2` and its neighbour `CON2` | `connector-pinouts.md` § Gauge harness |
| `ntc-two-pin-headers.jpg` | The two-pin headers the temperature sensing elements plug into, close up | `connector-pinouts.md` § Temperature sensing harness (item `B12.map`) |
| `two-way-valve-coil-marking.jpg` | The marking on the two-way valve's coil | `connector-pinouts.md` § Valve coils |
| `three-way-valve-coil-marking.jpg` | The marking and tabs of the three-way valve's coil | `connector-pinouts.md` § Valve coils |
| `original-board-component-side-aligned.jpg` | The original board's component side, squared: the nine mains tabs with their silkscreen, relays `K1` to `K4`, the triacs `Q2` and `Q5` with their opto-couplers `U5` and `U7`, the transformer, `F1` and the connector headers | `connector-pinouts.md` § Mains terminals, § The source of each live feed |
| `original-board-solder-side-aligned.jpg` | The same board's solder side, mirrored and warped onto the component-side image so that a point has the same pixel in both: the copper from the mains tabs, including the thick runs from `NEUTRAL`, `COFHEATER` and `STMHEATER` and the one copper area under `LINE` and `LINE1` | `connector-pinouts.md` § Mains terminals, § The source of each live feed |
