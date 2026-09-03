# Controller selection — working documents

Working drafts from an in-flight controller and mains-parts selection. **Not baselined, not
traced to any criterion, and not evidence for anything.** They are committed so the reasoning
survives the branch, because the graph currently has no way to hold a solution in a
pre-flight state waiting on an operator to physically build it.

Read them as a snapshot of a decision in progress, not as a record of one taken.

## Status of each file

| File | Status |
|---|---|
| `control-system-bom.csv` | **Current.** Parts, dimensions, rails, current, cost, and where each item physically lives. |
| `part-numbers.csv` | **Current.** Orderable part numbers, search terms, and the specific variant trap for each. |
| `module-interconnect.csv` | **Mostly current**, but every row naming "Robin Nano" predates the board change below. Signal assignments hold; the board name does not. |
| `robin-nano-v3.1-pin-allocation.csv` | **Stale in its board column.** See below. |

## The board changed mid-way

The pin allocation was built against an **MKS Robin Nano V3.1**, and its `Header/Source`
column is entirely that board's features — onboard thermistor ports with 4.7k pull-ups,
stepper driver slots, a repurposed SD-card SPI bus, EXP1/EXP2 headers, a WiFi module header.

The selection has since moved to a bare **VCC-GND STM32F407VET6 Mini**, for two reasons that
turned out to be independent of each other: the Robin Nano's only power input is 12–24V into
an onboard buck, and the project has no such rail; and almost none of a printer board is used
once the AC switching and analog front ends are off-boarded.

**The MCU is unchanged** — STM32F407VET6 either way — so the *pin* assignments and their
timer/ADC/EXTI reasoning transfer directly. What does not transfer is the board-level column:
a bare board exposes the LQFP100 pins on plain headers, so there are no thermistor dividers
fitted (three 4.7k resistors are owed), no stepper slots to borrow GPIO from, and no
SD/EXP/WiFi headers to repurpose. **This file needs re-basing onto the bare board before use.**

## What is settled

- Controller: VCC-GND STM32F407VET6 Mini. Staying on F407 costs zero porting — 97.5% of
  firmware source and 100% of tests sit behind a CI-enforced hardware seam.
- Heaters: 2× Fotek SSR-25DA, heatsinked. Semiconductors are required because half-cycle
  burst-fire is; the OEM's mechanical relays could not be commanded per half-cycle.
- Pumps + zero-cross: one RobotDyn 2-channel dimmer. MOC3021 confirmed random-phase.
- Valves: 4-channel mechanical relay module. Mechanical is not a preference — espresso
  solenoid coils draw 17–61 mA against a BTA16 holding current of 60 mA max, so a triac
  cannot reliably latch on them. The OEM's split (triac for pumps, relay for valves) was the
  same physics.
- Pressure: 2× XDB401, 3.3V supply / I2C output, G1/4.
- Supply: one 5V isolated mains module. The board's own LDO makes 3.3V.

## What is open

- The mainboard's own height, and the MAX31865 height with terminals fitted. Both are
  estimates; 25 mm of cavity makes them worth measuring.
- The dimmer module's height — not published anywhere found.
- Whether the I2C multiplexer is needed at all. It exists only because both XDB401 units
  ship on a fixed 0x7F; a supplier-programmed address makes it unnecessary.
- Valve count and placement. A hot-water diverter and a drip-tray vent are both plausible
  additions, and placement is thermal as much as functional — the diverter belongs near the
  thermoblock outlet so the brew path stays short, with the long leg going to the tap.
- The over-pressure relief valve. Its setpoint and the steam sensor's full scale are a
  coordinated pair, not two independent choices.
- The proof-of-life interlock, deferred. Downstream zero-cross sensing can verify the master
  relay opened, but cannot be the trip path: `REQ-SAFETY-CHAIN-001` requires the chain to owe
  nothing to the controller or firmware.
