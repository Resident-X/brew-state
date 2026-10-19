# Constraints record of the layout review proof design

This is the constraints record of `review-proof`, a throwaway design made only to prove the layout review step of `docs/board-design-method.md`. It is synthetic: no machine has these figures, and they are stated here so the design's rules table has a record to read its role figures from, as a real board's rules table reads them from its machine's constraints record. The design is marked not for manufacture and is never ordered.

| Figure | Value | What it bounds |
|---|---|---|
| Load supply continuous current | 1.0 A | The highest continuous current on `+5V` and `LOAD_RTN`, the supply from J2 to the load at J4 and its return through the shunt R1, and so on the ground the return reaches |
| Switched mains load continuous current | 0.5 A | The highest continuous current on `MAINS_L` and `MAINS_SW`, through J1 and U1's load side |
| Logic rail continuous current | 0.1 A | The highest continuous current on `+3V3` and `+3V3A`, from U2 to U4 and, through FB1, to U3 |
| Layer count | 4 | Copper layers F.Cu, In1.Cu, In2.Cu and B.Cu |
| Copper weight | 2 oz | Every copper layer, finished |
| Board manufacturer | JLCPCB | Whose stated limits the board-wide minimums are read from, at 4 layers and 2 oz |
| Leadless package clearance | 10 mm | The least distance, courtyard to courtyard, a leadless package keeps from a connector, a mounting hole and a board edge. A figure chosen for this synthetic design, which has no machine behind it |
