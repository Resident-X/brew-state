# Temperature sensing front end — working notes

Working draft from the same in-flight selection as the rest of this directory. **Not baselined,
not traced to any criterion, and not evidence for anything.**

Working position: **keep the fitted NTCs, calibrate them, and delete the MAX31865 boards.** One
claim behind that is a hypothesis and not yet measured — see § The open measurement.

**Position update, 2026-10-06 (current — supersedes the working position above and the earlier
same-day note that moved the block sensors to PT1000 chips).**

- **One calibrated PT1000 water probe is the key sensor.** The controlled variable is the water
  (`REQ-BREW-TEMP-001.C2`), so the accuracy goes there: a PT1000 spike probe in the stream at the
  **block outlet, before the 3-way valve**. It sees brew and hot water, has the least transport
  delay, and leaves the downstream loss (valve, tubes, the hot bore) to a model. Calibrate it on the
  real divider-and-ADC chain at the ice and boiling points (pressure-corrected).
- **The block NTCs stay as the casing sensors** (coffee and steam; the wand disc stays an NTC).
  The casing matters for the protection margin against the thermostat trip (110 degC +/-3) and as an
  estimator state; about +/-1 degC is enough. Even a 2 degC casing error moves the arrival
  temperature by only about 0.1-0.4 degC through the bore heat exchange. Calibrate them in place
  against the water probe **under steady low flow after a short flush**, never at rest: stagnant
  water at the probe cools toward ambient and does not equal the casing. The estimator residual
  shows drift. This keeps `DEC-DEVICE-RETENTION-BOUNDARY` untouched.
- **Flat PT1000 chips are commissioning tools only:** a temporary probe at the puck inlet, plus a
  spare. Nothing is fitted under the OEM boot clamp; no drilling into the blocks.
- **No MAX31865** (fallback; the PT1000 board is Adafruit **3648**, **3328 is the PT100 version**).
  The PT1000 channels are read on the H743's 16-bit ADC through the 4.7k low-TCR divider
  (about 0.54 mA, 0.4 mW self-heating; **not 1k**), ratiometric from the same node as the ADC
  reference, with averaging over whole mains cycles synchronised to the Z-C capture and a median
  filter against dimmer spikes.
- **Corrections to the comparison table below:** mechanical risk is low (a screwed clamp and a
  silicone boot on a flat plate, no wetted pocket; inferred from photos, confirm by lifting a
  bracket); speed is not a discriminator; the "10x noise immunity" holds only for series-voltage
  noise; NTC self-heating is not a reason either way.
- **Verify any marketplace "Class A" claim yourself:** about 1090 ohm at room temperature, ice and
  boiling point on the whole chain, heat-cycle and re-check.
- Nothing has been authored in the graph; see § What this owes the graph.

## What the requirement actually is

`reference-machine.md` § Protection: the coffee block's commanded target sits below its 110 °C
thermostat and "the ±3 °C tolerance means the worst-case margin is a few degrees. That margin is
what `REQ-MEASUREMENT-001.C1` is written against, and it is the reason **absolute accuracy matters
more than repeatability** on this channel." `controller-io.md` puts the figure at ±2 °C.

So roughly **±1 °C absolute** is comfortable, and repeatability alone is not enough.

## The axis the documents have not weighed

Those documents draw the distinction as *accuracy vs repeatability*. The live question is
**accuracy vs speed**, and nothing in the graph has ruled on it.

That matters here more than it would on a boiler. A thermoblock is deliberately low-mass and can
move degrees per second, so sensor lag translates directly into phase in the control loop and caps
achievable bandwidth. A sensor that is 0.5 °C more accurate but five seconds slower may well be the
worse instrument for this machine.

This is the *wrong axis* pattern `CLAUDE.md` names — the distinction drawn where the component sits
rather than where the consequence lands. Flagged, not resolved.

## The comparison

| | Fitted NTC | Retrofit PT1000 |
|---|---|---|
| Response speed | **Likely faster** — low mass, OEM-designed pocket. **UNVERIFIED** | A sheathed probe carries more mass and more thermal resistance |
| Accuracy, uncalibrated | Poor — ±2–5 °C, and this unit's beta is recorded as uncharacterised | **Class A ±0.34 °C at 95 °C**, straight from IEC 60751 |
| Accuracy, calibrated | **Excellent** — 3-point Steinhart-Hart reaches ~±0.1 °C | Excellent |
| Long-term stability | **Drifts.** Beta ages with thermal cycling; recalibration becomes a maintenance item | Very stable — platinum drifts <0.05 °C/yr |
| Sensitivity | **~4 %/°C** | 0.385 %/°C |
| Noise immunity | **~10× better**, directly from that sensitivity | 10× worse for the same electrical noise |
| Mechanical risk | **None — already fitted** | Real: new pocket, new seal, a pressurised heated assembly disturbed |
| Front-end cost | Divider + 16-bit ADC | Divider + 16-bit ADC |
| Extra parts | None | 3 probes, fitting, possible plumbing work |

## Why NTC wins on the arguments available

1. **Zero mechanical risk.** Replacing a sensor in a pressurised, heated thermoblock is real work
   with a real failure mode. `DEC-DEVICE-RETENTION-BOUNDARY` already leans toward retaining fitted
   devices.
2. **Ten times the noise immunity.** `REQ-ELECTRICAL-INSTALL-001.C8` requires precision sensing to
   hold its accuracy *while the kilowatt loads switch*. At 4 %/°C against 0.385 %/°C, electrical
   noise has to be an order of magnitude larger to move an NTC reading by the same amount. In this
   machine that is not a small consideration.
3. **Probably faster**, which matters for a low-mass block — though see below.
4. **Calibration closes the accuracy gap**, and the gap is the NTC's only real weakness.
5. **It costs nothing.**

The honest cost of choosing NTC is **drift**: the calibration decays as the part ages, so
recalibration has to be a named maintenance activity rather than a one-off at build time.

## Calibration

**Three points, fitted to Steinhart-Hart**, not two points fitted to a beta model. An NTC is
strongly non-linear; a two-parameter (R25, β) fit leaves real residual error away from the
calibration points, while the three-coefficient Steinhart-Hart form holds to ~0.01 °C across a wide
span.

**Bracket the operating region.** If the interesting range is 90–105 °C, calibrate there rather
than at 0 °C and 100 °C out of habit.

**Calibrate the sensor with its final cable, as an assembly**, in a stirred bath — not in situ.
Thermoblock gradients and lag are exactly what the estimator exists to handle, so calibrating in
place fits a correction to a temperature that is not actually known.

## Front-end electrical notes

**Measure ratiometrically.** Feed the divider from the same reference the ADC uses (VREF+/VDDA) so
supply variation cancels in the ratio. Free — it is only a wiring choice — and it removes reference
accuracy from the error budget entirely.

**Specify divider resistors by temperature coefficient, not initial tolerance.** Calibration solves
for the gain term, so initial tolerance is absorbed. What calibration cannot absorb is drift, so buy
**low TCR (≈25 ppm/°C) metal film** and do not pay for 0.1 % initial accuracy. This supersedes an
earlier note in these documents recommending 0.1 % parts.

**Self-heating is negligible.** The NTCs are 100 kΩ at 25 °C (schematic RT1–RT3, with 10 kΩ 1% dividers on the OEM board); at 95 °C that is of the order of 5–8 kΩ if B is about 3950 (B is not established). With the 4.7 k divider at 3.3 V that is about 0.3 mA and 0.5 mW in the sensor, an estimate.

**16-bit buys resolution, not accuracy.** Resolution was never the binding constraint — the 12-bit
divider already gave ~0.035 °C/count. The error stack is dominated by sensor tolerance and beta
uncertainty, and no ADC upgrade touches either. This is worth stating plainly because the board was
changed *for* the 16-bit ADCs, and it would be easy to assume they solved this.

## Consequence: the MAX31865 boards are not needed

The three MAX31865 breakouts exist in `control-system-bom.csv` as the front end for a **PT1000
migration**. On the position above there is no migration, so they go — and even if PT1000 were
adopted, the arithmetic says a plain ratiometric divider on a 16-bit ADC would serve:

- PT1000 spans 1000 Ω at 0 °C to ~1370 Ω at 95 °C
- With a 1 k reference resistor at 3.3 V: 1.650 V → 1.908 V, i.e. **258 mV over 95 °C ≈ 2.7 mV/°C**
- 16 bits over 3.3 V is 50 µV/LSB → **54 counts/°C**; derated to a realistic ~14 ENOB, still
  ~13 counts/°C, about **0.075 °C**

So the MAX31865 is unnecessary on **either** branch. Deleting it saves AUD 54, 714 mm², six pins
and the entire SPI2 bus.

**Lead resistance would not have blocked PT1000 either.** Two-point calibration solves for gain and
offset together: the delta between two known temperatures gives the gain (lead resistance cancels),
and either absolute point then gives the lead offset. Copper's +0.393 %/°C means a 0.2 Ω lead
swinging 50 °C moves ~0.04 Ω — about 0.01 °C at PT1000 sensitivity. This is exactly why PT1000
tolerates 2-wire where PT100 does not.

## The open measurement

**The speed claim is a hypothesis.** "The fitted NTC is faster than a sheathed PT1000 would be" is
plausible from mass and mounting, and it is doing real work in the argument above — but nothing has
measured it.

A step-response test on the bench settles it: drive the block from cold and record the sensor
against a fast reference. If the fitted NTC turns out to be slow — because the OEM pocket, not the
bead, dominates — then the speed argument evaporates and the decision rests on noise immunity and
mechanical risk alone. Those two are probably still enough, but the reasoning would change.

Related and already recorded as unestablished: `controller-io.md` notes the steam wand disc's
"relation to the quantity it stands for is itself unestablished" — a separate problem from the two
block sensors, and not addressed here.

## Water probe, group hardware and commissioning (revised 2026-10-06)

**What the hardware turned out to be.** The brass group outlet is built into the centre of the
thermoblock, and the brew water reaches it through a tube that runs down the block's open central
bore, ending in a brass nut that is very hot to touch. So the group metal is thermally tied to the
block: the casing temperature is, to a good approximation, the group metal temperature, and no
separate group sensor is needed (there is also no exposed brass to mount one on). The tube and nut in
the bore exchange heat with the casing: rough numbers, a metal tube there picks up about 15% of the gap
between its water temperature and the casing's at shot flow (1.2 ml/s) and about half at pre-infusion
flow (0.3 ml/s); a PTFE tube picks up much less. The portafilter and basket, which leave the machine
and cool in air, are the one state nothing observes.

**Expected loss from the block outlet to the group** (rough, unmeasured): a few degC through the valve
and tube at shot flow, partly offset by that bore reheating, with a larger and more uncertain figure
at low flow. The brew branch after the valve is partly copper (it warms by conduction) and about
15 cm of PTFE (about 1.9 ml of water). Thin insulation on a small tube helps little (critical-radius
effect), so shorten and reduce the bore rather than relying on foam. The honest answer is to
measure it.

**Probe fitting.** The probe goes in a standard tee used as an elbow, straight at the block outlet: the
outlet feeds one run port, the branch carries on to the 3-way valve, and the probe sits in the opposite
run port pointing back into the oncoming flow, tip upstream, sheath along the flow axis (about 20 mm
of a 30 mm probe immersed). A tee used this way mixes the stream, gives the probe a long immersion
and keeps its tip out of the sheath's wake, and its only dead volume is the gap behind the branch. A Y
with an upstream-facing angled probe port is the second choice; a plain T with the probe across the
flow gives the sheath a few millimetres of immersion, a stagnant ring and a large stem-conduction
error. This replaces the earlier "tee a few cm clear of the casing": that was caution about heat
conducting from the casing, and the fitting is insulated from the casing instead. It is general
instrumentation practice, not checked on this block, and the outlet port's thread is unmeasured. A
stream heated in a laminar channel is cooler at its core than its mixed average, so the reading is
compared with a mixed temperature in test 7.

**Commissioning tests that settle it** (each uses the temporary puck-inlet probe, in a dummy puck or
the basket path, read during steady flow after a flush unless stated):
1. Ice-point and boiling-point calibration of the water probe on the real chain.
2. NTC calibration against the water probe under steady low flow.
3. Cold-plug dip: after several minutes idle, start a shot and log the first five seconds at the
   puck inlet. A short flush or a plug-flow state is added only if a meaningful dip is measured.
4. Identification runs: cold start, second shot, and a shot after a hot-water draw, at several flows,
   to fit the downstream loss, the soak of the valve and tube, and the bore heat exchange
   (`REQ-STATE-ESTIMATION-001.C6`). A permanent second water probe is added only if the model's
   residuals demand it.
5. A noise check with the loads switching, and the pump pressure-ripple capture.
6. Dry-fill: with an empty or blind basket and a fixed pump drive, log the suction-side flow meter and
   the brew pressure tap from the pump start. The flow integrated to the first pressure rise is the
   empty volume ahead of the restriction (block, tubes, group); repeat after a long idle and straight
   after a shot to see how much the idle drain empties the block and how repeatable the fill is.
   Then fit the empty-basket resistance as a baseline, so the extra resistance when a puck is fitted
   can be read as the puck's. One pressure sensor sees only the total series resistance. Needs the
   flow meter's pulses per litre calibrated, the sensor's low-pressure noise floor and the I2C sample
   rate measured; none is known yet.
7. Mixed-cup check: at a steady low flow, collect a shot into a lidded insulated cup and compare its
   mixed temperature, with the cup's own heat capacity allowed for, against the probe reading; repeat at
   two flows. A consistent offset is calibrated out; one that varies with flow says the probe is reading
   the core and the fitting needs a stronger mixing feature upstream of it.

**Pre-shot conditioning.** A short hot-water flush conditions the probe, its stub and the common
chamber of the 3-way valve and can run with the portafilter attached; run it at a low flow through the
pump dimmer so the water is at temperature (about 1 kW cannot heat a fully open flow). It does not
condition the brew branch, the bore or the portafilter; a group flush needs an empty portafilter locked
in. The controller defers a target it cannot yet reach (`REQ-BREW-TEMP-001.C3`) and acts on the thermal
state it is actually in (`.C5`).

**Pressure taps.** The brew tap goes on the cold side, **between the OPV and the block**, as a direct
tee with no capillary: the block, valve and tube drop is only hundredths of a bar at espresso flow,
the pump's peaks (what opens the OPV) are visible there, and the OPV setting can be checked in place
against a blocked outlet. A brew tap after the block would also work with the same drop leg (the water is
already liquid at about 95 degC) and would read the pressure the puck sees, but the gain is only the
block, valve and tube drop (estimated, unmeasured), it adds thermal mass and dead volume to the path whose
temperature is controlled, and it loses the OPV-node check; the second block outlet, which runs to the
vent and is a dead end while the vent is closed in a shot, is the cheap place to test it. The vent
is opened by the controller at the end of the brew, so a tap there would read the depressurisation too. The steam tap goes on the steam side as a normal hairpin-clip-style tee in the line
**between the steam block and the manual steam knob valve**, with a plain drop leg of PTFE (matched to the OEM tube size
and wall) about 100-150 mm long running downhill to the sensor, so the leg fills with condensate and air
rises back into the line. It sits upstream of the valve so a closed valve stops milk suck-back reaching
it, and away from the block so the water seal does not boil off. It is not on the cold side, because
the cold-side reading is the steam-path pressure plus a flow-dependent two-phase drop through the block
that has not been measured, and the saturation temperature and the fault reading need the pressure in
the block. Rough, unmeasured estimates: heat penetrates the stagnant column only mm to about 1 cm in
minutes; check with the spare chip on the tube next to the sensor (aim under about 60 degC). PTFE is
accepted only if its rating at the hot-side maximum is confirmed. The steam OPV is directly on the pump, downstream of the pump's own check valve (owner statement), so if no check valve lies between it and the block (to be inspected) it opens when the block pressure rises and caps it at its 4-5 bar setting; otherwise the pressure after the block is the saturation pressure at the block temperature. If it does cap the block, saturated steam at 4-5 bar gauge is about 152-159 degC, so the hot-side parts need at least 160 degC and 8-10 bar. The OEM steam line is already PTFE, and its tube size and joint method are to be matched; if the rating cannot be confirmed a stainless capillary (about 3 mm OD x 1.5 mm ID, 300 mm) or 4 mm metal tube is the fallback. Until the real maximum block temperature is established, the steam parts keep the conservative rating of saturated steam at the 200 degC trip. The XDB401's datasheet
(owner-supplied) gives -40 to 105 degC operating and -20 to 80 degC compensated, +/-1% FS, response
time 4 ms; a brew tap after the block would sit at about 95 degC outside the compensated range with the
110 degC thermostat trip above the sensor's limit, so it would need a leg or capillary too. The I2C chip is
probably the NSA2302 (single-shot conversions, output rate set by OSR, address programmable in
EEPROM); the achievable sample rate for ripple capture is to be bench-measured. Machine-side thread
sizes are not yet measured.

**Graph.** `DEC-PLUMBING-LEFT-AS-BUILT` rules on re-routing brew water through the steam side, and
`CLAUDE.md` records that it does not forbid inserting a fitting; the pressure sensing
`REQ-MEASUREMENT-001.C7`/`.C8` already requires fitted taps.

## What this owes the graph

Nothing has been authored.

- The **accuracy-vs-speed axis** is not ruled on anywhere. If NTC is retained *because* it is
  faster, that is a decision with a rationale, and it should exist as one.
- **Recalibration as a maintenance activity** follows directly from choosing a drifting sensor. No
  criterion currently requires it, and a calibration that silently decays is worse than one that
  was never claimed.
- The **MAX31865 deletion** removes a part that `control-system-bom.csv` reserved pins and space
  for. That is a working-document change, not a graph change — but if any node cites the RTD
  migration path, it moves too.
