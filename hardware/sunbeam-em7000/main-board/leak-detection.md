# Can the mains current channel see leakage through an output that is commanded off?

An analysis of the main board, not a measurement. Every figure below comes from datasheet arithmetic and the board's own records; no board has been built, powered or measured. A figure marked "derived here" is worked out in this record and is not stated in another record.

The question: if a pump triac, a valve relay or a heater switch conducts when it is commanded off, can the firmware see it through the mains current channel (the 1 mohm shunt R105 read by channel 1 of the AMC131M02, U601)? The answer feeds the startup confirmation that `REQ-ACTUATION-CONFIRMATION-001.C6` requires, which commands each output and confirms that an output commanded off draws nothing, from the independent observation `REQ-ACTUATION-CONFIRMATION-001.C1` asks for (the shunt measures the actual current whatever the command path believes) and covering the off direction `REQ-ACTUATION-CONFIRMATION-001.C3` asks for.

## Result

| Leak through an output commanded off | Shunt signal (rms) | Seen with every output commanded off | Seen with a heater on |
|---|---|---|---|
| 10 mA | 10 uV | Statistically yes, marginal in practice: only if the idle baseline repeats to within a few mA | No |
| 50 mA | 50 uV | Yes | No |
| 190 mA (a valve coil at inrush) | 190 uV | Yes | No |
| 460 mA (a pump) | 460 uV | Yes | Marginal: only a leak above about 0.3 to 0.5 A can be separated |

What this means:

- With every output commanded off, a leak of 50 mA and above is seen. 10 mA is marginal.
- With a heater on (4.8 to 5.4 A), the heater's own current is about 100 times the leak. The current gain error alone is 1.6 % of 5 A, which is 80 mA (0.43 % of 5.4 A is 23 mA at best), before the heater's resistance tolerance and the supply voltage are counted. Only a leak above roughly 0.3 to 0.5 A can be separated, so the early heating stage, where a leak is about 10 to 100 mA, is caught only at 50 mA and above with all outputs off.
- The shunt sees the sum of all current returning through the neutral, so the check says that something commanded off conducts a given current. It cannot name the pump, valve or heater unless the outputs are toggled one at a time with the others off and the readings compared.
- It does not see earth leakage: current that leaves by the protective earth does not return through R105.
- It cannot see an output that fails to turn on. That is the on-direction check, which compares the expected current from the plant model with the reading, within the calibrated gain bound of `DEL-HW-BRING-UP.C22` (1.6 % for current).

## Where the load currents return

R105 is a 1 mohm Kelvin shunt. Its pin 1 is the plug-side neutral tab (`NEUTRAL_IN`), pin 4 is the board neutral pour (`NEUTRAL`), and pins 2 and 3 are the sense pair, which reach U601 channel 1 through R607 and R608. Everything on the `NEUTRAL` net returns through R105:

- The pump triacs T701 and T711 have MT1 on `NEUTRAL`.
- The valve relays K731 and K741 return through `VALVE_COM`, F731 and `NEUTRAL`.
- The heater wall board's return lands on the `NEUTRAL` pour (sheet 101 puts that landing above the shunt), so heater on and off is also seen.
- The logic supply module U301 (IRM-20), the zero-crossing optocoupler U602, the X2 capacitor C101 across line and neutral, the varistor RV101, the discharge strings R101 to R104 and the voltage divider return are all downstream of R105 and flow in the shunt.
- Not through R105: current that leaves by protective earth, and any wire a harness joins to the plug neutral outside the board. The netlist shows none on the board; the plug-side neutral tab carries only R105 and test points.
- The pump snubbers (R706 with C701, R716 with C711) are not fitted. Fitted, each would add 100 nF x 253 V x 2 pi x 50 Hz = 7.9 mA to the off-state baseline of its pump. Not fitted, they add nothing. A triac's own off-state leakage (BTA204S, 0.1 mA typical and 0.5 mA at most at 600 V and 125 degC) is below anything resolved here and harmless.

## What the channel can resolve

The shunt gives 1 mV per amp, so 1 uV of signal is 1 mA.

- **Gain.** The converter's gain is a register, so it is a firmware choice. Every board record assumes gain 32: full scale plus or minus 37.5 mV is 37.5 A peak (26.5 A rms), and 15 A rms (21.2 A peak) uses 57 % of it. Gain 64 would clip at the 15 A overload the records require the channel to read, so 32 is the highest gain that meets that.
- **Quantisation.** 24 bits over 75 mV is 4.5 nV, or 4.5 uA of shunt current. Noise, not quantisation, sets the resolution.
- **Noise.** The converter's datasheet gives, for channel 0 at gain 32 with the inputs shorted, 1.75 uV rms at 4 kSPS (typical), improving by the square root of 2 in global-chop mode. It states no figure for channel 1, no maximum, and nothing for noise picked up in the circuit. The sample rate and chop mode are firmware choices; the board's 8 MHz crystal at the default settings gives about 3.9 kSPS, taken here as 4 kSPS.
- **Front end.** R607 and R608 are now 470 ohm. With C602 (4.7 nF across the pair) the corner is 36.0 kHz, far above 50 or 60 Hz, so the filter does not limit resolution.
- **Offset.** 100 uV typical (330 uV at most) without chopping is 100 mA (330 mA); with global chop, 6 uV typical (100 uV at most). It matters only if the DC component of the reading is kept. With the mean over whole mains cycles removed, offset drops out. After the calibration of `DEL-HW-BRING-UP.C22`, only drift remains: for 30 degC from the calibration temperature, at most 15 mA without chopping and 9 mA with it.
- **Windowing.** The converter's clock is not locked to the mains, so a window must end on a voltage zero crossing (channel 0 samples the voltage at the same moment; the zero-crossing detector of sheet E2 also gives an edge at every crossing). A partial cycle adds an error comparable to the leak.

Noise-only resolution, assuming white noise (derived here: one estimate from N samples has an error of 1.75 mA divided by the square root of N; the change between two estimates taken the same way is the square root of 2 larger):

| Window | Samples at 4 kSPS | 3 sigma of one estimate | 3 sigma of a change against a baseline taken the same way |
|---|---|---|---|
| 20 ms | 80 | 0.59 mA | 0.83 mA |
| 200 ms | 800 | 0.19 mA | 0.26 mA |
| 1 s | 4000 | 0.083 mA | 0.12 mA |

A 10 mA leak is 12 times the 20 ms figure and 38 times the 200 ms figure; 50 mA is 60 and 190 times. These are noise-only limits. The real limit is how well the idle baseline repeats.

## The idle baseline

No record holds an idle current figure. The estimate below is derived here and is to be replaced by the bring-up reading.

| Source, all outputs off | Estimate |
|---|---|
| IRM-20 supply module (about 0.3 to 0.5 A of 5 V load: controller, interlock coil, indicators; 78 % efficient; the rms current of a capacitor-input front end about twice its real component) | 20 to 40 mA |
| C101, 0.1 uF across line and neutral, 253 V at 50 Hz (7.2 mA at 230 V; 9.5 mA at 60 Hz and 230 V) | 7.9 mA, in quadrature with the voltage |
| Zero-crossing detector, about 143 kohm | 1.8 mA |
| Voltage divider, 253 V over 0.9 Mohm | 0.28 mA |
| Discharge strings R101 to R104, 1 Mohm | 0.25 mA |
| Total | roughly 30 to 55 mA, mostly the module |

The baseline moves with line voltage (C101's current is proportional to it, the module's is not) and with activity on the 5 V rail, so a fixed absolute threshold is wrong; a leak is a change from the baseline. How well the baseline repeats is not in any record; a few mA to ten mA is a guess. That is why 10 mA is marginal and 50 mA is clear.

The in-phase (resistive) component of the fundamental, measured against channel 0's voltage, leaves out C101 (90 degrees away) and much of the module's distortion, and is steadier than total rms. The pump's and valve's current waveforms are not in the records; a pump that draws half-wave current has a DC component that mean removal rejects, in which case the total with DC kept (after the offset calibration, about 3 to 15 mA of drift) is the quantity to read.

## Recommended check

The outputs-off quiescence check, for the firmware slice that delivers `REQ-ACTUATION-CONFIRMATION-001.C6`:

1. **Condition.** Every pump, valve and heater commanded off, the interlock and logic supply as in normal running, held for at least 500 ms after the last switching so the 5 V rail and the module are steady, with no relay or triac transition inside the window.
2. **Window.** Whole mains cycles ending on a channel-0 voltage zero crossing, 200 ms (10 cycles at 50 Hz, 12 at 60 Hz). Its 3 sigma change is 0.26 mA, which leaves the margin for the baseline. A 1 s window is available if the baseline proves noisy; 20 ms (0.83 mA) is enough for 50 mA and above.
3. **Quantity.** The fundamental's amplitude and in-phase component, and the total rms with the DC kept, recorded together.
4. **Baseline.** Learned by the machine in the same all-off condition at power-up before any output is commanded, as the median of several windows, and refreshed whenever all outputs have been off. Each new window is compared with it.
5. **Threshold.** The baseline plus the larger of 5 mA and 6 times the baseline's own measured spread. Until bring-up measures the spread, 10 mA over the baseline.
6. **Time.** 200 ms plus the 500 ms settle.

Other stages:

- **Pump on, other outputs off.** The pump's expected current is large, and its model error (supply, load, gain at 1.6 %) is about 7 mA at 460 mA plus the current's own ripple. A leak of about 50 mA and above through another output is therefore detectable, which confirms the other outputs are off while one runs.
- **Heater on.** A weak check, useful for the heaters' own on and off state only.

## What the figures rest on

- The idle baseline of 30 to 55 mA is an estimate. Bring-up measures it and its spread (a criterion of `DEL-HW-BRING-UP` added with this record), and the threshold is set from them.
- The converter's noise is typical, for channel 0 with shorted inputs at 25 degC. Channel 1 and in-circuit noise are not stated or measured. The Kelvin pair's pickup, bounded in `signal-study.md` at 8.4 uV rms at 11 A, is proportional to the current and in quadrature with it, so it is not a noise floor.
- The sample rate, chop mode, gain and clock are firmware and part choices that no record fixes beyond gain 32.
- The pump's and valve's current figures (460 mA, 190 mA) are the owner's; their waveforms are not recorded.
- The sources are the board's sheets and records (`error-budget.md`, `signal-study.md`, `circuit-proof.md`, `traceability.md`), the AMC131M02 datasheet (SBASA56, Table 7-1, section 6.8 and Table 8-1), the IRM-20 datasheet and the BTA204S datasheet.
