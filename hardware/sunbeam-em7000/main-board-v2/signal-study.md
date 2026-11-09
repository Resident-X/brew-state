# Signal study of the routed main board (commit c25f3af6)

Read-only study of the board file as committed at c25f3af6 (`hardware/sunbeam-em7000/main-board/main-board.kicad_pcb` and `main-board.kicad_pro`). The scripts and working output behind it are not committed (see Provenance). The study edited nothing in the repository.

## Provenance

Produced on 2026-11-05 from board commit c25f3af6. Every figure below is the output of a model of the board file, run with ngspice 47 (transmission-line transients and the supply-impedance sweep) and a set of scripts written for this study: a net extraction (a pure-Python reader of the board's KiCad file that builds each net's routed tree, layers, vias, plane coverage and neighbouring copper), a two-dimensional finite-difference solver for the mutual capacitance of two traces over a plane, and closed-form scripts for crosstalk, crystal loading, shunt pickup and path delays. Those scripts and their output files are not committed to the repository, so the study cannot be re-run from the repository alone: the method sections state each model, and the assumptions are stated where they are made, so it can be rebuilt. No physical measurement was made: no board of this design exists yet, and nothing here was measured on a bench. The figures stand until the bring-up measurements in section 6 are made, and a design change to the board file after c25f3af6 is not covered. The firmware settings it asks for (SPI2 pin speed Low or Medium, so edges are 5 ns or slower, and a clock of 4 MHz or lower) are carried by DEL-HW-MAIN-BOARD-DESIGNED.C27, and the readings it asks of bring-up (section 6) by DEL-HW-BRING-UP.C21.

## Bottom line (plain words)

- **No net has to change copper before ordering** on the evidence of this study. Nothing fails; three things are *marginal* and each is closed by a firmware setting or a bring-up reading, not by moving copper (section 7).
- The three marginal items: (1) the SPI clock and data lines to the two MAX31865 chips (U620, U621) have no series resistor and ring by 0.5 to 1.4 V if the controller's pins are set to the fastest edge; (2) the MAX31865 read-back (MISO) has about 8 ns left of a 100 ns half period at 5 MHz in the worst datasheet corner; (3) the 32.768 kHz crystal start-up margin is thin on paper (inherited from the pre-layout proof, not made worse by routing).
- Crosstalk into the thermistor, current and converter inputs is 10^2 to 10^4 times below one converter step. The reason is physical: every sense input has a large filter capacitor at the pin (47 nF, 100 nF), and a 0.2 mm trace 0.3 to 0.8 mm from another over a plane at 0.1 mm couples only about 0.002 pF per mm.
- What I could not do: the stackup heights, the controller's pin capacitance and output edge speed, the MAX31865 pin overshoot rating and the HX711 noise are not in the repo. Each is stated as an assumption and swept, never guessed silently.

## Method and tools

| Tool | Used for |
|---|---|
| `net_extract.py` (pure Python, reuses the repo's `sexpr.py`) | per-net extraction, reduced electrical tree, plane coverage, aggressors. Output `nets.json`, `nets.md` |
| ngspice 47 (`tl_sim.py`, `pdn.py`) | lossless transmission-line transients; supply impedance AC sweep |
| `fd/cap2d.c` (2-D finite-difference solver, C) | mutual capacitance of two 0.2 mm traces over a plane; calibrates the crosstalk figures |
| `sense.py`, `crystals.py`, `shunt_pickup.py`, `skew.py` | closed-form crosstalk, crystal load, shunt pickup (Neumann), path delays |

Not used: kicad-cli (not on PATH), numpy/scipy (not installed), any field solver beyond the 2-D one above.
The extraction took about 2 minutes on the board file. If the maker's stackup becomes known, the stackup constants of the extraction and of the transmission-line script are changed and the study re-run.

**Stackup caveat.** The board file has no stackup block and the repo gives none ("controlled impedance: none asked", `manufacturer-limits.yaml`). I assumed: 1.6 mm, 35 um outer and 15.2 um inner copper, FR-4 er 4.3, outer prepreg (F.Cu to In1.Cu, In4.Cu to B.Cu) 0.10 mm, inner dielectrics 0.42 mm. Everything outer-layer was also run at 0.07 and 0.20 mm. A 0.2 mm track then has Z0 of 37, 45 or 66 ohm and 6.1 ps/mm delay (In3.Cu stripline 56 to 62 ohm, 6.9 ps/mm). The order form should state or the maker confirm the real heights.

## 1. Net extraction (what the board actually has)

The working output `nets.md` (not committed) has one line for every Fast and Sense net plus the extras (96 nets): length per layer, vias, widths, route/straight ratio, functional length and stub length, plane coverage, top aggressors within 2 mm with coupled length and minimum gap. `nets.json` (not committed) also holds each net's reduced electrical tree and the list of no-plane runs. Every track is 0.2 mm wide except supply tracks (0.45 mm).

| Net | Length mm | Layers (mm) | Vias | Plane under (adjacent layer) | Longest run with no plane | Path delay |
|---|---|---|---|---|---|---|
| SPI2_SCK | 149.4 | F 39.7, B 109.7 | 9 | 88 % | 3.2 | U401 to U620 0.75 ns (123.9 mm), U621 0.65 ns, R610 11.3 mm |
| AMC_SCLK (after R610) | 138.1 | F 17.4, B 88.7, In3 32.0 | 6 | 80 % | 4.9 | U401 to U601.18 0.93 ns (149.2 mm) |
| SPI2_MOSI | 184.8 | F 103.5, B 81.3 | 10 | 90 % | 3.4 | to U620 0.88 ns (144.4 mm), U621 0.76 ns |
| AMC_DIN (after R611) | 117.2 | F 70.2, B 47.0 | 6 | 74 % | 6.0 | U401 to U601.20 0.79 ns (130.8 mm) |
| SPI2_MISO | 196.3 | F 119.3, B 66.5, In3 10.5 | 16 | 81 % | 5.8 | U620 1.03 ns (168.5 mm), U621 0.90 ns, R613 0.74 ns |
| AMC_DOUT_PIN | 4.1 | F | 0 | n/a (3.6 mm uncovered) | 1.4 | R613 to U601 3.0 mm |
| AMC_CLKIN / CLK_OUT | 10.2 / 3.5 | F, B | 2 / 0 | 70 % / 100 % | 1.1 | R609 to U601 6.2 mm; stub to TP602 4.0 mm |
| USB_DP / USB_DM | 41.8 / 38.1 | F 10.6 / 13.1, B 31.2 / 25.0 | 3 / 2 | 86 % / 79 % | 1.1 / 3.4 | DP 29.8 mm, DM 36.9 mm to J402: 7.1 mm (43 ps) apart; DP stub 10.9 mm to TP411 |
| HSE_IN / HSE_OUT | 8.8 / 7.0 | F (HSE_IN 1.1 mm B) | 1 / 0 | 86 % / 100 % | 0 | Y401 3.2 / 3.6 mm from the pins |
| LSE_IN / LSE_OUT | 8.6 / 7.1 | F | 0 | 100 % | 0 | Y402 5.8 / 3.9 mm from the pins |

Reading the table: "plane under" is any GND copper on the adjacent layer(s), sampled every 0.2 mm; it counts the In4.Cu fill cuts and the mains pull-back (the last 6 mm of AMC_DIN and 4 to 5 mm of AMC_SCLK sit there). The repo's own measure (critical-routing triage, board `final18`) counted 130.7 mm of Fast track with no plane over runs of 1 mm or more; mine counts about 85 mm on c25f3af6 (later copper, and I count either adjacent layer). Every Fast signal via has a ground via within 2.2 mm (worst 2.18 mm, AMC_DIN). Route/straight ratios of 1.4 to 1.7 on the SPI nets are the recorded WORK-2 deviation (nets pulled round the mains barrier).

## 2. Fast digital: transmission-line runs

**Model.** Each net's routed tree (every run, layer, via) becomes lossless T-lines (DC resistance 2.5 mohm/mm, 0.34 ohm over the longest net, so loss is negligible), 0.8 nH plus 0.4 pF per via, joined through the 33 ohm parts R609 to R613 (`parts-specification.yaml`). Driver: a ramp behind Rout (15 or 50 ohm) with edge time 1, 2.5, 5, 10 ns. Receivers: 8 pF each plus the controller's 5 pF pin; no clamp (worst) and with clamp diodes. Run at 0.10 and 0.20 mm heights. The results were written to one working file for each of the two heights and reported by a small script; neither is committed.

**Figures from the repo, and what is unknown.**
- Clock 5 MHz, mode 1: the MAX31865 limit (`circuit-proof/E_spi_bus.py`, MAX31865 sheet via circuit-proof E1.8). AMC131M02 allows 25 MHz (SBASA56 via the same script); the shared bus is held to 5 MHz by the MAX31865.
- Receiver thresholds: AMC SCLK/DIN VIH 0.8 DVDD, VIL 0.2 DVDD (SBASA56 6.8); MAX31865 and controller VIH 0.7, VIL 0.3 (MAX31865 sheet, DS12110 Table 60).
- Controller output impedance: only an upper bound, 50 ohm (VOL 0.4 V at 8 mA, VOH VDD-0.4 V at 8 mA, DS12110 Table 61). **Lower bound and edge rate are not in the repo**; the firmware does not configure SPI2 yet (the only GPIO speed set, `hw_stm32.c` line 174, is LOW for the PWM pins). So edge time 1 to 10 ns and Rout 15 to 50 ohm are swept.
- Y601 clock: edges 2 ns max, VOH 90 % of Vdd (SiT8008B Rev 1.08 via E1.9).
- MAX31865 pin overshoot rating: **not in the repo** (only VDD/DVDD 4 V absolute maximum, `parts-specification.yaml`).

**Which nets need a line model (rise-time rule, line is long if delay > edge/6).** At 2.5 ns edges the limit is 69 mm of track: SCK, MOSI, MISO trunks and AMC_SCLK/DIN (0.65 to 1.03 ns) are long; at 10 ns edges (300 mm limit) all are short. USB (0.25 ns, edges 4 to 20 ns, USB 2.0 full speed, from the spec, not the repo), HSE/LSE (0.05 ns), AMC_CLKIN (0.04 ns) are electrically short: lumped behaviour, no line model needed.

**Results (controller drives; height 0.10 mm unless said).**

| Receiver | Edge 1 ns / 15 ohm | 2.5 ns / 15 ohm | 5 ns / 15 ohm | 2.5 ns / 50 ohm | Ring through threshold |
|---|---|---|---|---|---|
| U620/U621 SCK and MOSI pins (no series R) | over +0.8 to +1.1 V | +0.5 to +0.8 V | +0.1 to +0.3 V | +0.01 V | none; 1 corner (0.20 mm, 1 ns, U621 MOSI) crosses twice |
| U601 SCLK/DIN pins (after 33 ohm) | +0.34 | +0.26 | +0.06 | 0.00 | none |

At 0.20 mm height the first row reaches +1.4 V (1 ns) and +1.2 V (2.5 ns). Receiver clamp diodes hold it to about +0.7 V. Undershoot mirrors overshoot. Delay driver to receiver 1.0 to 4 ns, so the sampling edge is clean in every case (no false clock) and the 33 ohm parts at R610/R611 are effective on the AMC branch.
Verdict: **marginal, firmware-closed.** With edge time of 5 ns or more (GPIO speed Low or Medium) overshoot is 0.3 V or less, with no copper change. At the fastest setting the MAX31865 inputs would see 4.1 to 4.7 V against an unknown pin rating.

**Return path (MISO).** Drivers: AMC DOUT through R613 (Rout up to 660 ohm, the 1 mA VOH limit), MAX31865 SDO (up to 250 ohm, 1.6 mA VOH limit, MAX31865 sheet). Result at the controller pin (0.7 VDD): AMC path adds 5.7 ns (100 ohm), 11 ns (330), 20 ns (660); MAX31865 adds 2 ns (50 ohm) to 7.5 ns (250). No ringing. Budget at 5 MHz, half period 100 ns:
- AMC: tp(SCDO) 20 ns + 20 ns (worst) + 2 ns setup = 42 ns, margin 58 ns. Pass.
- MAX31865: tCDD 80 ns (measured with 50 pF) + 7.5 ns line and load + 2.2 ns SCK arrival + 2 ns controller setup = 91.7 ns, **margin about 8 ns**. The MISO net carries about 22 pF of track and 6 pF of vias (196 mm at 0.114 pF/mm; 16 vias at 0.4 pF) plus three pins, so it is probably above the 50 pF the MAX31865 was measured at (circuit-proof E1.8 asks for 50 pF or less; the pin capacitances are not in the repo, so I cannot prove either side). Running SPI2 at 4 MHz gives about 33 ns. Verdict: **marginal**, closed by firmware clock and a bring-up read.

**Skew.** SCLK to DIN at the AMC 0.14 ns (18 mm); SCK to MOSI at the MAX31865 0.13 ns; SCK to MISO round trip 1.8 ns (U620). The plan's skew figure (WORK-2 row: worst about 47 mm, 0.3 ns, SCK to MISO) is consistent. Against a 100 ns half period it is 0.1 to 2 percent. **No skew problem.** (Mode 1 launches on one edge and samples on the other, so skew is not the budget; the line delay and driver impedance above are.)

**Other fast nets.** AMC_CLKIN 8 MHz from Y601 through R609 (33 ohm) over 6.2 mm plus a 4 mm stub to TP602: lumped, the 2 ns edge and 49 ns half-period margin (7.2 ns, E1.9) are untouched. USB: 38 to 42 mm, skew 43 ps against an 83 ns bit, no line effects; DP's 10.9 mm TP411 stub adds under 2 pF (full-speed budget is far larger). Both OK.

## 3. Crystals

Figures: Y401 YSX530GA, CL 20 pF, ESR 80 ohm max, C0 7 pF max (`parts-specification.yaml`, circuit-proof B row); C414 = C415 = 20 pF C0G. Y402 FC-135, CL 12.5 pF, R1 70 kohm max, C0 1 pF typical only, drive level 0.5 uW; C416 = C417 = 4.7 pF. MCU: Gm_crit max 1.5 mA/V for HSE (DS12110 Table 131), LSE 0.5/0.75/1.7/2.7 uA/V by drive setting (Table 132). Pre-layout assumed 10 pF stray per node from AN4938 section 4.1.2 ("a rough estimate of pin and board").

**Measured board stray per node (track + pad over In1 + via), `crystals.py`:**

| Node | Track mm | Board stray at 0.10 mm | Range 0.07 to 0.20 mm |
|---|---|---|---|
| HSE_IN (incl. 1 via and 3 mm TP406 stub) | 8.8 | 4.8 pF | 2.9 to 6.5 |
| HSE_OUT | 7.0 | 3.6 pF | 2.0 to 5.1 |
| LSE_IN | 8.6 | 2.3 pF | 1.4 to 3.2 |
| LSE_OUT | 7.1 | 2.1 pF | 1.2 to 2.9 |

The pin capacitance of the controller is **not in the repo** (the AN's 10 pF includes it). The board part is therefore well under the 10 pF allowance and the layout does not exceed it unless the pin itself is above 5 pF (HSE) or 7.8 pF (LSE).
- **HSE:** CL = 10 + Cs. At Cs 6 to 14 pF the start-up margin (1.5 mA/V over gm_crit) is 3.5x to 1.9x (2.54x at the AN's 10 pF; limit 4 ESR (2 pi f)^2 (C0+CL)^2). Pulling: with CL low by 1 to 4 pF the frequency error is a few tens of ppm at a typical 10 fF motional capacitance (**typical, not in repo**), irrelevant for USB (2500 ppm) and UART. **OK, margin 2x or more, confidence high.**
- **LSE:** CL = 2.35 + Cs. Margin against LSEDRV 11 (2.7 uA/V): 1.28x at Cs 10 pF and C0 1 pF, 1.77x at Cs 8, 0.97x at Cs 12. The repo already marks this row FAILS (C0 maximum not stated; circuit-proof B) and says leave Y402 unfitted is the alternative; LSE has no requirement (RTC not required). Layout effect: the board adds 2.1 to 2.3 pF per node, so it moves the margin only if pin capacitance is high. **Marginal on paper (inherited), not layout-driven; confidence medium.** Closed at bring-up by start-up time and frequency of LSE with LSEDRV = 11.
- **Aggressors and keep-clear facts.** HSE_IN/HSE_OUT run 1.1 mm side by side at 0.3 mm; LSE_IN/LSE_OUT 2.95 mm at 0.25 mm. The coupling between them is across the crystal: about 0.009 pF (FD solve, 3 pF/m at 0.25 mm), against C0 of 1 pF and 7 pF: negligible. Other nets cross under the bank on B.Cu (SPI2_MOSI 11.9 mm, SPI2_SCK 11.5, +5V_GAUGE 11.0, +3V3 10.4, TANK_LEVEL 10.0, NRST 8.4, and slow nets on In2 to In4) but In1.Cu is solid between, five layers separate them from the crystal copper, and the nearest same-net-free track to an HSE/LSE node on F.Cu is 0.3 mm (NRST, HSE_OUT). At 0.3 mm and 0.1 mm height the crystal node sees 0.002 pF/mm: under 0.01 pF per aggressor, and an 8 MHz oscillation is not disturbed by a 5 MHz signal 1.25 mm away on another layer. Seven unrelated parts (R795 5.1 mm, R713, R302, R794, U791 6.8 mm, JP302, D821) stand inside 10 mm (the accepted CLOCK-3 deviation): none is a fast aggressor except U791's gauge outputs; effect not quantifiable without the gauge edge timing (outputs 8 to 15 ns, SCLS306E via circuit-proof F2). Verdict: **OK, confidence medium.**

## 4. Sense chains

**Method.** The charge a neighbour's edge can inject is Cm x dV (Cm from the FD solve; log-log interpolation on edge gap: 0.0038 pF/mm at 0.2 mm, 0.0022 at 0.3, 0.0009 at 0.5, 0.0004 at 0.8, 0.00012 at 1.5, height 0.10 mm; about double at 0.20 mm; 0.009 to 0.013 pF/mm with **no plane**). A filter capacitor C at the pin absorbs it: step = Cm dV / (C + Cm), which is an upper bound whatever the source resistance upstream. All aggressors within 2 mm on the same layer are summed as if they stepped together (worst case). Swings: logic 3.3 V; 5 V stages (HCT541 8 to 15 ns, FET gates 140 to 280 ns, circuit-proof F2) 5 V; +5V rail 0.2 Vpp (IRM-20 via circuit-proof); +3V3 0.1 V (assumed). Inductive pickup is the same order (Lm/L about Cm/C for traces over a plane) and was not added separately except for the shunt.

| Victim (filter cap) | Worst-case sum (h 0.1 / 0.2 mm) | One step of the converter | Biggest neighbour |
|---|---|---|---|
| NTC_COF (C501 47 nF) | 1.9 / 4.1 uV | 50.4 uV (16-bit of 3.3 V) | KEY5 16.6 mm at 0.43 mm |
| NTC_STM, NTC_WAND (47 nF) | 0.02 / 0.04 uV | 50.4 uV | SPI2_SCK 3.1 mm at 1.75 mm |
| STMP_AN, BREW_AN, SPARE_AN2, CURR1_AN, CURR2_AN (47 nF) | 0.06 / 0.10 uV or less | 50.4 uV | GAUGE_STEP2_B 0.6 mm at 0.7 mm |
| VREF+ (C410 + C411) | under 0.001 uV | 50.4 uV | none within 2 mm |
| PT1/PT2_RTDIN (C640/C645 10 nF) | 0.2 / 0.4 to 1.9 / 3.7 uV | about 62.6 uV (15-bit, 2.05 V reference, E3.1 figures) | SPI2_MOSI 1.85 mm at 0.45 mm |
| WT1_SN_RAW (C670 100 nF) | 0.5 / 1.0 uV | HX711 +-20 mV full scale, 24-bit step 2.4 nV | LOWWATER_CATHODE 10.85 mm at 0.55 mm |
| WT2_SP_RAW (C675 100 nF) | 2.9 / 6.3 uV | same | PT2_CS 24.2 mm at 0.20 mm (B.Cu) |
| WT2_SN_RAW | 0.25 / 0.52 uV | same | SPI2_SCK 4.25 mm at 0.45 mm |
| AMC_AIN1P (C602 4.7 nF, no plane) | 0.03 uV | AMC gain 32, +-37.5 mV, step 4.5 nV | AMC DC-DC node 0.42 mm at 1.56 mm (swing assumed 0.1 V) |

- **Thermistor and pressure channels (the ones with a requirement):** thermoblock temperature +-2 degC and steam-path pressure +-0.775 bar (`controller-board-design-constraints.md`, Sensing accuracy). Worst case is 4.1 uV, 0.08 of a 16-bit step. With a 3.3 V divider and any ordinary thermistor near its working point the signal moves at least about 15 mV per kelvin (**assumed**: beta 3000 to 4000, divider matched to the thermistor; the thermistor values are not in the repo), so 2 degC is 30 mV or more, 7000 times the crosstalk. **OK, margin x10^3 or more, confidence medium** (swing assumptions; the dominant uncertainties are the ADC charge-sharing kick already in circuit-proof, 195 to 296 uV, and clamp leakage, not crosstalk).
- **Filter corners with the measured strays:** track capacitance at the filter node moves the corner by 0.002 to 0.08 percent (NTC_COF 85 mm = 9.7 pF on 47 nF is 0.02 percent; PT RTD 70 mm = 8 pF on 10 nF is 0.08 percent; AMC_AIN1P 30 mm = 3.4 pF on 4.7 nF is 0.07 percent). The 240 Hz, 344 Hz, 10.1 kHz, 8.0 kHz, 51 kHz corners of circuit-proof F1 stand.
- **HX711 channels (WT1/WT2).** There is **no weight requirement** (the load cell is "anticipated, not fitted", `controller-io.md`; circuit-proof E4.1 FAILS for lack of any figure). Step sizes above are a few microvolts on a 40 mV span: 70 to 160 ppm of full scale for the one bad pair, WT2_SP_RAW beside PT2_CS (24 mm at 0.2 mm), and PT2_CS toggles once per conversion command. The HX711's effective noise and its response to 5 MHz bursts are not in the repo, so the ratio to the 2.4 nV step is not a meaningful limit (**unknown**). The pair is also routed 0.21 mm apart for 18.8 mm (WT1) so common-mode pickup is mostly rejected. The recorded 12 to 14 mm stub of WT1_INA_P (14.8 mm to TP671, 1.7 pF) is under 0.01 percent of C670; the 12.6 mm of WT1 pair in the reed keep-out has no plane (BOARD-8, accepted). **OK for any requirement that exists; marginal only if a future weight accuracy is tighter than about 100 ppm of full scale.**
- **SENSE-4 as built.** 54 sense nets total 67 mm of track within 0.8 mm of Noisy, Fast, Supply5V or Mains copper on the same layer (counting +3V3 neighbours too: 15 mm at 0.3 to 0.5 and 63 mm at 0.5 to 0.8) and 160 mm more between 0.8 and 2 mm. Biggest single runs: PT1_FORCEP 14.3 mm beside GAUGE_DIR1_B at 0.8 mm; WT1_SN_RAW 10.9 mm beside LOWWATER_CATHODE at 0.55 mm; WT2_SN_RAW 7.2 mm beside SPI2_SCK / +3V3. The step each can inject is the table above (microvolts); the repo's 70 mV for 2 ns "1 percent crosstalk" at 1 mm was a ratio estimate, the FD ratio Cm to self-capacitance is 0.2 to 3 percent over 0.2 to 0.8 mm gaps. **OK.**
- **Current-sense (AMC131M02, ch1 gain 32, shunt R105 1 mohm, 21.2 mV peak at 15 A).** The Kelvin pair (SHUNT_SENSE_IN 53.6 mm, SHUNT_SENSE_NEUTRAL 58.4 mm, 2.2 mm apart on average, no plane by the mains pull-back) picks up the load current's field. Neumann sum over all MainsTrunk copper with the whole 11 A in every trunk segment (an overestimate): upper bound 2.4 nH, i.e. 8.4 uV rms at 11 A, 0.076 percent of the signal, in quadrature with the current, phase error at most 0.044 degree. Against channel 1's own +-1 % gain error (SBASA56 via circuit-proof E1.5) and the absence of any declared accuracy (E1.5 FAILS for lack of a figure), **OK, confidence medium**. Capacitive pickup into AMC_AIN1P is 0.03 uV (1.6 ppm of full scale). Bring-up: compare the reading with a known resistive load while pumps and heaters switch (DEL-HW-BRING-UP.C5 does this).

## 5. Power

Model: the routed +3V3, +3V3_REG and +5V track networks (R 2.5 mohm/mm, L 0.28 nH/mm over the plane), decoupling capacitors as C (derated 0.8 for 100 nF X7R, 0.6 for X5R 1 to 10 uF, 0.5 for 22 uF; **assumed**), ESR 10 to 50 mohm (**assumed**), ESL 0.5 nH plus mount 0.5 nH (**assumed**, typical 0603; not in the repo) plus the real ground-leg length to the nearest GND via. Pessimistic case ESL 0.8, mount 1.0, derate 0.6. The 3V3 regulator is an AC short behind C304/C305 (not valid below about 100 kHz). 1 A injected at each pin.

Target impedance: 5 percent of 3.3 V (0.165 V) over the transient. The transient current is **not in the repo**; circuit-proof budgets 240 mA at 200 MHz, so I take half as a step (0.12 A, target 1.4 ohm) and, to bound it, 0.5 A (0.33 ohm).

| Pin | Capacitor and distance | 1 MHz | 10 MHz | 100 MHz | First above 1.4 ohm (base / pessimistic) |
|---|---|---|---|---|---|
| U401.11 | C401 100 nF, path 10.3 mm | 0.08 | 0.24 | 2.75 | 53 / 50 MHz |
| U401.27, .50, .75, .100 | C402, C403, C404, C405 1.4 to 3.5 mm, C407 4.7 uF at .50 | 0.05 to 0.17 | 0.11 to 0.23 | 0.76 to 1.04 | 141 to 188 / 100 to 150 MHz |
| U601.13 (AMC DVDD) | C609 1 nF, C610 1 uF, ~2 mm | 0.21 | 0.13 | 0.4 to 13 (anti-resonance of the two caps near 100 MHz) | 71 / 60 MHz |
| U620.20 | C641/C642 100 nF | 0.17 | 0.05 | 0.86 | 168 / 133 MHz |
| U630.16, U631.16 (HX711 DVDD) | C673, C678 100 nF | 0.15 | 0.15 to 0.24 | 0.9 to 1.0 | 150 to 158 / 112 to 126 MHz |
| U630.1, U631.1 (HX711 AVDD, +5V) | C671, C676 10 uF | 0.015 | 0.085 | 0.85 | 168 / 126 MHz |

Numbers in ohms. All pins stay under the 1.4 ohm target to 50 MHz or more and under 0.33 ohm to 14 MHz or more except U601's 1 nF (see below). Reading the DECOUPLE items that failed in round 2 (round 2 of `layout-review.md`, findings 2.16 to 2.20):
- **C401 10.3 mm from U401.11 (2.16/2.17):** the only distance that shows in the numbers: pin 11 is about three times worse than the other VDD pins above 50 MHz (2.75 ohm at 100 MHz). The core is also decoupled on chip and in the package (not modelled). A real but minor item; the same two vias in its path (2.20: +3V3 vias at (95.35, 34.25), (95.35, 33.45)) add about 1 nH. **Marginal, confidence low-medium.** Closed by a scope reading of +3V3 at the C401 pad (no test point sits on +3V3 itself; TP302 is +3V3_REG at the regulator) with firmware running flat out (alarm if over 50 mV peak to peak).
- **C405, C609, C676 with one ground via (2.17):** adds about 0.3 nH; not visible. **OK.**
- **C406 9.3 mm (VBAT):** VBAT carries microamps. **OK.**
- **C605/C606 6.9 to 7.2 mm from U601 pin 3 (HLDO input), C301/C302 8.1 to 9.5 mm from the logic-supply module pins (2.16/2.18):** the converter's internal regulator figures and the IRM-20's switching frequency are **not in the repo**, so the effect cannot be computed; at the module's likely sub-MHz switching a 2.6 nH leg is irrelevant, and `circuit-proof` already budgets 200 mVpp of module noise. Not assessed; bring-up TP605 (DCDC_OUT) and TP608 (HLDO_OUT), TP206 (+5V), ripple against the AMC sheet.
- **C409 5.4 mm from VDDA, FB301 5.3 mm (2.65):** FB301 (600 ohm at 100 MHz, 0.5 ohm DC, 350 mA) with C408/C409 filters above about 1 MHz; bead impedance below 100 MHz is not in the repo, so the attenuation is not computed. Bring-up: ripple at TP403 (+3V3A) against TP302 (+3V3_REG).
- **C612 via (2.20):** adds about 1 nH to an internal flying capacitor of the converter; unimportant at its 4 MHz.
Snubber distance (2.19, DECOUPLE-5) is a mains switching item, out of scope of this study.

## 6. Result table

Confidence = how well the method plus the assumptions bound the truth. "TP" = a test point on the board (84 exist; 82 on B.Cu).

| Net or signal | Requirement | Result | Confidence | Bring-up measurement that closes it |
|---|---|---|---|---|
| SPI2_SCK, SPI2_MOSI to U620/U621 | clean edge, no false clock, pin stays in rating | **marginal**: ring 0.5 to 1.4 V at fastest GPIO edge, 0.3 V or less at 5 ns edges; no threshold re-crossing | medium (driver Rout and edge unknown) | scope at R610.1 / R611.1 pads (no TP on SCK/MOSI) with the GPIO speed set; 5 MHz burst |
| AMC_SCLK, AMC_DIN (after 33 ohm) | AMC VIH 0.8 DVDD clean | OK, over 0.34 V at worst, margin 2x or more | medium | same scope at U601 pins (via R610/R611 pads) |
| SPI2_MISO, AMC DOUT | tp + setup inside half period | AMC OK (58 ns margin); **MAX31865 marginal**, about 8 ns at 5 MHz worst corner (33 ns at 4 MHz) | medium | TP610 (MISO) with SCK; read RTD at 5 and 4 MHz |
| SCLK/MOSI skew at AMC and MAX31865 | no figure; plan 0.3 ns | OK, 0.13 to 0.14 ns | high | none |
| AMC_CLKIN 8 MHz | clock range, duty, level (E1.9) | OK, lumped, edges unchanged | high | TP602 |
| USB_DP / USB_DM | full-speed eye | OK, 38 to 42 mm, skew 43 ps | medium | TP411/TP412 eye, or enumeration |
| HSE (Y401) | start with margin, CL 20 pF | OK, margin 1.9x to 3.5x over Cs 6 to 14 pF | high | TP406 (HSE_IN); start-up and frequency |
| LSE (Y402) | start-up on LSEDRV 11 | marginal on paper (1.0x to 1.8x), inherited, not layout-driven | medium | no TP: probe at C416/C417 pads; time to start, LSE on MCO |
| NTC_COF / NTC_STM / NTC_WAND | +-2 degC thermoblock | OK, margin 10^3 or more | medium | TP501, TP502, TP503 with pumps/heaters switching |
| STMP_AN, BREW_AN, SPARE_AN2, CURR1/2_AN | +-0.775 bar steam pressure | OK, margin 10^2 or more | medium | TP527, TP529, TP531, TP570, TP571 |
| VREF+ | quiet reference | OK | medium | TP402 |
| PT1/PT2_RTDIN | none declared (E3.1) | OK, 0.06 of a code worst case | medium | TP621, TP623 |
| WT1/WT2 (HX711) | none (anticipated) | OK for any existing requirement; WT2_SP_RAW 2.9 to 6.3 uV from PT2_CS | low (HX711 noise unknown) | TP671, TP673, TP670; read with SPI2 and PT2_CS active |
| AMC_AIN1 / shunt Kelvin pair | none declared (E1.5) | OK, pickup under 0.08 percent, quadrature | medium | TP604; known load, switching loads on |
| +3V3 at U401 | within 5 percent, transient | pins OK to 100 MHz+; pin 11 weakest (C401) | low-medium (ESL, di/dt assumed) | C401 pad (or TP302 for the regulator end) scope with firmware running |
| AMC DVDD, HLDO, DCDC | converter supply | OK at DVDD; internal nodes not assessed | low | TP605, TP608, TP206 |
| HX711 AVDD / DVDD | 2.6 to 5.5 V, low noise | OK impedance 0.015 ohm at 1 MHz; supply rejection unknown | low | +5V and +3V3 at U630 pins |

## 7. What could force a copper or placement change before ordering

Nothing here is a must. Smallest changes, in order of how likely they are to be wanted:

1. **SPI2_SCK and SPI2_MOSI branches to U620/U621** (the shared trunk of about 70 mm and the 20 to 50 mm legs beyond it, junction a few mm from U401 pins 52 and 54): only if a scope shows over 0.3 V ringing with the GPIO set to its slowest edge. Change: put 33 ohm in the branch (needs a footprint; none drawn) or reduce the edge in firmware first. Today: firmware only.
2. **SPI2 clock rate**: set SPI2 at 4 MHz or lower in firmware (limit stays the MAX31865's 5 MHz); no copper.
3. **PT2_CS beside WT2_SP_RAW** (24.2 mm B.Cu at 0.20 mm): only if the weight channel becomes a requirement tighter than about 100 ppm of full scale. Change: re-route PT2_CS to at least 0.8 mm from WT2_SP_RAW.
4. **C401 at 10.3 mm**: only if the +3V3 scope reading is over 50 mV peak to peak. Change: one more 100 nF directly at U401.11 on B.Cu.
5. **Y402 and C416/C417**: if LSE is wanted and fails to start, leave unfitted (the repo's own alternative) or change C416/C417 downward; no copper.
Everything else is fine or accepted with the bring-up check named in section 6.

## 8. What this study cannot show

- It assumes ideal ground planes below the tracks except where I measured them absent; it does not model the plane cuts, slot edges and via fences as 3-D structures (return-path discontinuity radiation, EMI), so it says nothing about emissions or susceptibility to ESD.
- Stackup heights, MCU pin capacitance and output slew, MAX31865 pin rating, HX711 noise and PSRR, IRM-20 switching frequency, ferrite impedance below 100 MHz, capacitor ESL and DC-bias loss are not in the repo; each was assumed and swept as stated, or reported "unknown".
- Crosstalk is closed form plus a 2-D solver (two traces over a plane, no solder mask, no 3-D end effects); good to about a factor of 2, far smaller than the margins quoted, but it does not replace a scope reading.
- The power model's regulator is ideal below 100 kHz; load-step behaviour of the LT1963A, brown-out and start-up are in circuit-proof, not here.
- Mains-side nets (AMC inputs) have no plane by design; mains-frequency capacitive pickup from Mains-class copper was checked only within 2 mm (none found other than the converter's own pair and ground).
- No physical measurement: every number is a model of the file at c25f3af6.
