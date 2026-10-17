# Constraints record of the method proof design

**NOT FOR MANUFACTURE.** This is the constraints record of `method-proof`, a throwaway design made only to prove `docs/board-design-method.md` from its first step to the pre-order check. It is synthetic: no machine has these figures. They are stated here so that the steps of the method have a record to read their figures from, as a real board's steps read them from its machine's constraints record. The design is marked `NOT_FOR_MANUFACTURE` `true` and is never ordered.

| Figure | Value | What it bounds |
|---|---|---|
| Supply input voltage | 4.75 V to 5.25 V | The 5 V supply entering at J1 pin 1, which is the declared supply span of every circuit run from it |
| Supply input continuous current | 0.5 A | The highest continuous current on `+5V_IN`, `+5V` and the ground that returns it, at J1 |
| Logic rail continuous current | 0.1 A | The highest continuous current on `+3V3_REG` and `+3V3`, from the 3.3 V regulator U1 |
| Status LED current | 1 mA to 5 mA | The current in the status LED D1, over the supply span and over 0 °C to 50 °C ambient |
| Ambient temperature | 0 °C to 50 °C | The air around the built board, for every circuit on it |
| Mains | none | The board carries no mains-referenced net |
| Protective device | none declared | No fuse or breaker on the board, and none declared ahead of it, so the record declares no fault current and no let-through energy |
| Layer count | 4 | Copper layers F.Cu, In1.Cu, In2.Cu and B.Cu |
| Copper weight | 1 oz | Finished copper on every copper layer |
| Board outline | at most 40 mm by 30 mm | The board's size |
| Board manufacturer | JLCPCB | Whose stated limits, `docs/board-manufacturer-jlcpcb.md`, the board-wide minimums are read from, at 4 layers and 1 oz |
