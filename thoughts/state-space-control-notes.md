# State-Space / MPC Control — Design Notes

Sunbeam EM7000 retrofit (dual thermoblock: steam + coffee), custom STM32-class
controller per `parts/controller_bom.csv`. Goal: forward-horizon predictive
control for stable steam pressure and stable brew water temperature.

## Machine architecture

- **Dual independent thermoblocks**, not boilers — no stored water/steam
  reservoir. Each is a metal mass with an embedded cartridge heater and a
  water channel; heating happens in near real time as water flows through.
  Low thermal mass compared to a boiler → more transient-sensitive.
- Steam loop: ~1200W heater (row 3), independent pump (JYPC-4).
- Coffee loop: ~1000W heater (row 4), independent pump (Type EP5). Boost
  target ~105°C, hardware safety thermostat trips 110°C±3°C — thin margin.
- Two separate pump + thermoblock circuits, not plumbed in series today.
- Hardware safety chain is independent of firmware: master contactor +
  watchdog, per-boiler thermal cutout switches, one-shot thermal fuses.

## Cold vs. preheated makeup water (thermoblock case)

Corrected after realizing this is thermoblock, not boiler-reservoir, physics
— flow-through energy balance, not stored-mass depletion.

- Energy per gram of makeup water: cold (20→100°C) ≈ 2592 J/g (sensible +
  latent); preheated (103°C→100°C, already superheated, contributes flash
  energy) ≈ 2244 J/g.
- Sustainable steam flow at 1000W: ~23.2 g/min cold vs ~26.7 g/min preheated
  — **~15% steady-state gain**, much smaller than a boiler-reservoir model
  would suggest, because latent heat dominates the per-gram energy cost
  regardless of inlet temp.
- Bigger effect is likely **transient**, not steady-state: low thermal mass
  means cold water causes a real local temperature dip in the block within
  the water's short residence time → wet/sputtering steam, pressure surge.
  Preheated inlet largely avoids this dip.
- Getting the preheat requires **physically re-plumbing** the two currently-
  independent circuits in series with a diverter valve — real hardware
  complexity for a ~15% steady-state number. Not sure if we will do this as
  it removes the ability to brew and steam at the same time.
- Combined heater draw (1200W + 1000W ≈ 2200W, ~9.2A@240V) may be a tighter
  practical constraint than any of the above if run concurrently on a
  standard 10A/2400W circuit — **verify actual circuit rating**.
- **Recommendation**: don't re-plumb for preheat. Handle concurrent
  brew+steam entirely in the controller — flow-rate feedforward (known
  disturbance) plus duty-cycle arbitration between the two heaters as a
  hard constraint in the MPC/LQR cost function, so combined draw never
  exceeds the real circuit budget.

## Control architecture recommendation (based on quick thoughts, can be updated)

- Two thermoblocks → two loops, likely linear MPC or LQR+integrator
  per loop, coupled only through a shared power-budget constraint.
- States per loop: something like [block/element temp, water-side temp],
  with **flow rate as a measured disturbance** fed forward (already have a
  flow sensor in the BOM) — lets the controller pre-boost heater duty ahead
  of a detected shot/steam draw instead of reacting after temp/pressure
  droop.
- May include a temperature probe on the group head itself as that is the 
  thing we want to have accurate and stable temperature control for.
- Steam side is not directly actuated — pressure is a consequence of temp
  via the saturation relation until the valve opens, which is a large fast
  disturbance. Likely needs gain-scheduled/hybrid dynamics (closed-vessel
  heating vs. venting) rather than one linear model, or start simpler
  (LQR + integrator + feedforward) and reserve full MPC for the coffee
  loop where predictive pre-heating has clearer payoff.
- Burst-fire SSR with a 1Hz window is a natural fit for a ~1Hz control/
  prediction sample rate. State dimension is small (2-4 states, 1-2 inputs
  per loop) — well within reach of even a modest online QP on the target
  MCU, no need for a heavy solver.
- Need a Kalman filter / observer to reconstruct unmeasured states (e.g.
  element temp vs. water temp) from PT1000 + pressure ADC readings.

## Firmware target

- Bare STM32 HAL via PlatformIO (per BOM row 2), **not** the Arduino
  framework — needed for direct control of interrupt priority (zero-cross
  EXTI timing for burst-fire accuracy, watchdog heartbeat/contactor hold
  logic, shared SPI bus timing across two MAX31865 channels).
- No OS required; likely an interrupt-driven scheduler (zero-cross ISR,
  flow pulse counting, watchdog heartbeat all in real ISRs) over a simple
  superloop. FreeRTOS is an option later if task separation becomes messy,
  not needed up front.

## Simulation / verification pipeline (free tools)

Layered so that low-cost, fast-iterating design work happens before
anything touches the embedded target, and the final layer runs the *actual
compiled firmware binary*, not a re-implementation of it.

1. **Control/plant design** — Python. `python-control` for LQR/observer
   baseline, `do-mpc` (CasADi + IPOPT/qpOASES) for MPC formulation and
   tuning. Plant model: plain ODE (`scipy.integrate.solve_ivp` or fixed-
   step Euler) — full Modelica/FMI-level fidelity isn't needed for a
   lumped-parameter system this size.
2. **Native C validation** — port/generate the control algorithm as C
   (hand-port, or use **OSQP's embedded code-generation mode**, or
   `acados` for auto-generated real-time NLP code), compile it both for
   the STM32 target and natively (e.g. PlatformIO `pio test` native env)
   linked against the same plant model, to catch numeric drift between the
   Python design and the embedded port before ever touching hardware.
3. **Full-firmware, peripheral-accurate emulation — Renode** (Antmicro,
   free/OSS). Runs the literal compiled `.elf` against real STM32
   peripheral register maps (SVD-based), not a re-implementation. Write
   the plant model as a **`PythonPeripheral`** — Renode has a built-in
   Python scripting bridge, so the *same* Python plant module from step 1
   can be reused here rather than re-written in C#. This is the layer that
   validates ISR latency, zero-cross-referenced burst-fire timing, SPI bus
   sharing, watchdog timing — things a pure Python co-sim can't catch.
   `Wokwi` is a useful lighter-weight companion for wiring/UART/display
   sanity checks.
4. **Optional bench HIL** — real board + real SSRs into dummy resistive
   loads, sensors stand-in driven by the same plant model over serial/DAC,
   before ever connecting real thermoblocks/mains.

Rationale for not skipping straight to step 3: Renode verifies code that
already exists, it doesn't help choose the control law. Sweeping MPC
weights/horizon is much faster as a direct Python function call than a
compile-flash-emulate cycle, and keeping design bugs (bad control law) and
port bugs (bad C implementation) separated makes both easier to debug.

## Expected sim-to-real accuracy

- Realistic first-pass grey-box fit: steady-state gain within a few
  percent; dynamic response shape (time constants) within roughly
  **10-20%** on the first identification pass.
- Split parameters by measurability:
  - **Low error, directly measurable**: coil resistance under load (→
    actual power via P=V²/R, more trustworthy than nameplate wattage),
    block mass (→ thermal capacitance via known c_p), PT1000/flow sensor
    calibration.
  - **Higher error, must be fit from step-response data**: heat transfer
    coefficients (cartridge→block, block→water, block→ambient) — not
    measurable directly; block→water coefficient is flow-dependent, so a
    single-flow-rate step test only characterizes a local regime; the
    phase-change nonlinearity near 100°C is invisible unless a test
    actually produces steam; sensor placement lag is only captured by the
    real step response, not a datasheet.
- Best-practice fitting method: physics-informed **grey-box** fit — use
  measured R/mass/sensor specs as priors/bounds, refine heat-transfer
  coefficients via least-squares (`scipy.optimize`) against real step/PRBS
  data, validate against a held-out test not used in the fit.
- Reframe: the goal isn't matching simulated and real traces exactly —
  it's designing the controller with enough robustness margin (integral
  action, constraint tightening proportional to known model uncertainty)
  that ~10-20% model error doesn't threaten stability or safety, just
  possibly the tightness of setpoint tracking.

## Bench auto-ID harness (PC-driven)

- Firmware: raw test-mode command layer over serial (reuse the existing
  USB-serial on the SKR/Octopus-class board), separate from the normal
  control loop — direct actuator override (heater duty, pump duty, valve),
  named test routines (step/PRBS/chirp), telemetry stream timestamped by
  the firmware's own hardware timer (not PC arrival time, to avoid
  USB/serial jitter corrupting time-constant estimates).
- Safety: hardware watchdog/contactor/thermostat chain stays fully active
  in test mode — no bypass. Firmware-side ceiling (max duration/duty,
  auto-cutoff on lost PC heartbeat) as a second layer independent of the
  hardware chain. Firmware's own loop keeps servicing the watchdog during
  test routines.
- PC side: `pyserial` + Python, log to CSV/dataframe, script test
  sequences, feed straight into the same `scipy.optimize` grey-box fit
  used for the plant model.
- Worth building as a **permanent** low-level interface, not a throwaway
  test build — useful later for live sim-vs-real comparison and field
  diagnostics.

## Self-calibration without a PC

- Storage isn't the real blocker: buffering a test run needs only RAM
  (tens of KB, trivial on an STM32F4/F7), and what needs to *persist*
  across power cycles is just the fitted parameter values (dozens of
  bytes) — internal flash (reserved sector / EEPROM emulation) is enough,
  no SD card or external chip required.
- The actual hard part is the **fitting step** — embedding a nonlinear
  least-squares solver (Levenberg-Marquardt-style) in C instead of calling
  `scipy.optimize`, and doing it with **no human in the loop** to catch a
  bad convergence or wrong model order — needs its own sanity checks
  (bounded parameters, residual-error threshold, fallback to last-known-
  good calibration).
- Split by purpose:
  - **Initial commissioning**: keep PC-driven — this is where model
    *structure* gets validated, not just parameter values.
  - **Ongoing drift correction**: good fit for standalone on-device
    operation — narrower problem (small corrections to already-validated
    structure), not a full from-scratch system-ID.

## Drift detection & correction with a running state-space model

- **Detection is essentially free**: a Kalman filter/observer already
  computes an innovation residual (predicted vs. actual sensor output)
  every cycle. Run a CUSUM or threshold test on that residual sequence for
  drift detection — no extra sensing or model evaluation needed.
- **Correction is easy on-device *if* the firmware doesn't hardcode fixed
  numeric A/B matrices.** Two options, not mutually exclusive:
  - Keep A(θ), B(θ) as functions of a small physical parameter vector θ
    (heat transfer coefficients, thermal resistances), and use **CasADi's
    code generation** to export a C function (`computeAB(theta, x_op, &A,
    &B)`) that's compiled into firmware. Correction becomes: update θ,
    call the generated function — no offline tool, no PC, no reflash.
  - Fold θ into the Kalman filter's own state vector as slowly-varying
    states (near-zero process noise) — the same filter already running
    for state estimation jointly estimates the drifting parameters
    continuously, using the same residual signal as detection.
  - This costs little extra at design time since CasADi is already
    deriving the model symbolically for the MPC formulation.
- **When you actually need to rerun the offline generation tool**: only
  for structural changes — adding/removing a state, changing how a
  nonlinearity enters the equations, re-deriving around a fundamentally
  different operating regime. Routine parametric drift (5-20% from
  original calibration) is exactly what the on-device path is for. If the
  detection residual stays anomalously large even after online correction
  converges, that's a signal the issue is structural, not just parametric
  — that's when to go back to the PC/offline tool.

## Open items / not yet decided

- Exact steam thermocoil operating pressure/temp target (assumed ~120°C
  saturation for earlier back-of-envelope calcs — needs confirming).
- Actual circuit rating the machine will be wired into (10A vs 15A/20A) —
  affects how tight the combined-heater power budget really is.
- Model order/structure for each thermoblock loop (2-state assumed;
  whether that's sufficient won't be known until real step-response data
  is in hand).
- Choice of embedded QP/NLP solver (OSQP codegen vs. acados vs. hand-
  rolled) — not yet settled, depends on how the MPC formulation lands in
  the Python design phase.
