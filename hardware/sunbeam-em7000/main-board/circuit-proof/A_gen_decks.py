# Generates the interlock simulation decks A_*.cir from one place so that the corner lists cannot drift.
# Run from this folder:  python3 -I A_gen_decks.py   then   ./A_run_all.sh
# Variants: "rec"  = the 19-part drive of the division record (R205, R206 opened with alter, 1 T ohm);
#           "fix"  = the drive as drawn on the sheet (R205, R206 100 kohm from each coupling node to ground).
HDR = ".include A_interlock.cir\n.include A_models.inc\n"
SLOW = dict(R="5.6896Meg", Cr="4.9645n", Cc="105.6n")   # slowest decay / highest start (removal time)
FAST = dict(R="5.5104Meg", Cr="4.4547n", Cc="94.8n")    # shortest hold (timeout against refresh)
RAILHI, RAILLO = 5.25, 4.75

def var(v):
    return "alter R205 = 1T\nalter R206 = 1T\n" if v == "rec" else ""

def pwl_edges(t0, period, n, high):
    pts = ["0 0"]
    for k in range(n):
        r = t0 + k*period
        pts += [f"{r:.9f} 0", f"{r+10e-9:.9f} 3.3", f"{r+high:.9f} 3.3", f"{r+high+10e-9:.9f} 0"]
    return pts

def corner(c):
    return f"alter R203 = {c['R']}\nalter R204 = {c['R']}\nalter C203 = {c['Cr']}\nalter C205 = {c['Cr']}\nalter C202 = {c['Cc']}\nalter C204 = {c['Cc']}\n"

def write(name, text):
    open(name, "w").write(text)

CG = "* FET input capacitance at its datasheet maximum, 50 pF (NX3008NBK Table 7), one per gate\nCg201 POL_GATE_A GND 50p\nCg202 POL_GATE_B GND 50p\n"
COIL55 = "* relay coil, a deck-added load (K201 is excluded from simulation): 62 ohm -10 % = 55.8 ohm\nRcoil +5V POL_COIL_LO 55.8\n"
OPT = ".options reltol=1e-5 abstol=1e-15 gmin=1e-15\n"

# last edge then a held level (high or low), slowest corner: gate decay to the lowest datasheet threshold
def removal_gate(final, v, tstop="2500m"):
    t0 = 0.0999001
    pts = ["0 0", "99.9m 0", "99.9001m 3.3"]
    if final == "low":
        pts += ["105m 3.3", "105.001m 0"]
    t = f"Interlock removal, step 1: gate decay after the last rising edge to the lowest FET threshold, slowest corner, output held {final}, variant {v}\n" + HDR
    t += f"Vsup +5V GND {RAILHI}\nVpol POL_OUT GND PWL({' '.join(pts)})\n" + CG + COIL55 + OPT
    t += f".tran 5u {tstop} 0 20u\n.control\n" + var(v) + corner(SLOW) + "run\n"
    t += "meas tran vstartA FIND v(POL_GATE_A) AT=100m\n"
    t += "meas tran tA06 WHEN v(POL_GATE_A)=0.6 FALL=1\nmeas tran tB06 WHEN v(POL_GATE_B)=0.6 FALL=1\n"
    t += f"meas tran tdecA TRIG AT={t0} TARG v(POL_GATE_A) VAL=0.6 FALL=1\nmeas tran tdecB TRIG AT={t0} TARG v(POL_GATE_B) VAL=0.6 FALL=1\n.endc\n.end\n"
    write(f"A_removal_gate_{final}_{v}.cir", t)
for fin in ("high", "low"):
    for v in ("rec", "fix"):
        removal_gate(fin, v, "3000m" if (fin == "high" and v == "rec") else "400m")

# record-style start: gates at the rail top, no diode drop
t = "Interlock removal, step 1, start at the rail top (no diode drop): gate decay to the lowest FET threshold, slowest corner\n" + HDR
t += f"Vsup +5V GND {RAILHI}\nVpol POL_OUT GND 0\n" + CG + COIL55
t += ".ic v(POL_GATE_A)=5.25 v(POL_GATE_B)=5.25 v(POL_NODE_A)=0 v(POL_NODE_B)=0 v(POL_BUF)=0 v(POL_MID)=0 v(POL_COIL_LO)=0\n" + OPT
t += ".tran 2u 300m 0 5u uic\n.control\n" + corner(SLOW) + "run\n"
t += "meas tran tR06 WHEN v(POL_GATE_A)=0.6 FALL=1\nmeas tran tR05 WHEN v(POL_GATE_A)=0.5 FALL=1\n.endc\n.end\n"
write("A_removal_gate_rail.cir", t)

# coil decay through the clamp, L = 1 H, gates forced to zero at 1 ms
def coil(name, title, mods, tstop='7.2m', extra=''):
    t = title + "\n" + HDR
    t += f"Vsup +5V GND {RAILHI}\n"
    t += "* the gates are forced: 5.25 V until 1 ms, then 0 V (gate decay is step 1; the FET turn-off allowance is added in the row)\n"
    t += "Vga POL_GATE_A GND PWL(0 5.25 1m 5.25 1.001m 0)\nVgb POL_GATE_B GND PWL(0 5.25 1m 5.25 1.001m 0)\n"
    t += "* relay coil, deck-added: 62 ohm -10 % = 55.8 ohm in series with L = 1 H (the inductance is open in the records; the time scales with L)\n"
    t += extra + "Vsense +5V KA 0\nRcoil KA KB 55.8\nLcoil KB POL_COIL_LO 1 IC=0.094086\n* the stack's midpoint is floating while both FETs are off; its leakage is modelled as 100 Mohm (a convergence aid, deck-added)\nRmid POL_MID GND 100Meg\n"
    t += f".options reltol=1e-4 abstol=1e-10 gmin=1e-12 itl4=200 method=gear\n.tran 5u {tstop} 0 20u\n.control\n" + mods + "run\n"
    t += "meas tran i0 FIND i(Vsense) AT=0.9m\nmeas tran tcoil_per_H TRIG AT=1.001m TARG i(Vsense) VAL=7.3m FALL=1\n.endc\n.end\n"
    write(name, t)
coil("A_removal_coil.cir", "Interlock removal, step 3: coil decay through the clamp per henry; zener at 11.4 V, clamp diode drop taken as about 0 (no sheet bounds it below)",
     "altermod DCL is=1e-14 n=0.05 rs=0\n")
coil("A_removal_coil_real.cir", "Interlock removal, step 3: as above with the clamp diode at the BAS116 limit fit", "")
coil("A_removal_coil_zshort.cir", "Interlock fault: both zeners shorted, the diodes alone clamp (BAS116 limit fit); coil decay per henry", "", tstop="29m", extra="* fault: both zeners shorted, a deck-added 10 mohm across each\nRzs1 POL_CLAMP_1 POL_COIL_LO 0.01\nRzs2 POL_CLAMP_2 POL_COIL_LO 0.01\n")

# hold: timeout against the 12 ms refresh, every end that shortens it
def hold(case, ileak, desc, v):
    pts = pwl_edges(10e-3, 12e-3, 10, 6e-3)
    last = 10e-3 + 9*12e-3
    t = f"Interlock timeout against the 12 ms refresh, shortest corner, leakage case {case}, variant {v}: {desc}\n" + HDR
    t += f"Vsup +5V GND {RAILLO}\nVpol POL_OUT GND PWL({' '.join(pts)})\n"
    t += "* output low after the last edge (a held-high output is run in the removal decks)\nRcoil +5V POL_COIL_LO 81.8\n"
    t += "* gate leakage (pump-diode reverse current plus FET gate leakage) as a current from the gate to ground, faded out under 0.2 V\n"
    t += f".param IL={ileak}\nBl201 POL_GATE_A GND I='IL*(v(POL_GATE_A)>0.2 ? 1 : v(POL_GATE_A)/0.2)'\nBl202 POL_GATE_B GND I='IL*(v(POL_GATE_B)>0.2 ? 1 : v(POL_GATE_B)/0.2)'\n" + OPT
    t += ".tran 2u 400m 0 5u\n.control\n" + var(v) + corner(FAST) + "run\n"
    t += f"meas tran vpeakA MAX v(POL_GATE_A) FROM={last-1e-6:.9f} TO={last+0.1e-3:.9f}\n"
    t += f"meas tran gminA MIN v(POL_GATE_A) FROM={last-6e-3:.9f} TO={last-1e-6:.9f}\n"
    t += f"meas tran tabove_after_edge TRIG AT={last:.9f} TARG v(POL_GATE_A) VAL=1.8 FALL=1 TD={last+0.1e-3:.9f}\n.endc\n.end\n"
    write(f"A_hold_{case}_{v}.cir", t)
for v in ("fix",):
    hold("L0", "0", "no leakage", v)
    hold("L1", "50n", "50 nA, the pump-diode figure of the record", v)
    hold("L2", "1.08u", "datasheet limits: BAS116 80 nA (75 V, 150 C) + NX3008NBK IGSS 1 uA (8 V, 25 C)", v)
    hold("L3", "180n", "datasheet limits with a gate-leakage limit of 100 nA + the diode's 80 nA", v)
hold("L0", "0", "no leakage", "rec")

# coil pick-up, gates at 1.8 V
def pickup(name, title, vg, rail, rcoil, kp, pick):
    t = title + "\n" + HDR + f"Vsup +5V GND {rail}\nVga POL_GATE_A GND {vg}\nVgb POL_GATE_B GND {vg}\nRcoil +5V POL_COIL_LO {rcoil}\n.tran 1u 20u\n.control\n"
    t += f"altermod NM vto=1.1 kp={kp}\nrun\nmeas tran vlo FIND v(POL_COIL_LO) AT=19u\nlet vcoil = {rail} - vlo\nlet icoil = vcoil/{rcoil}\nlet vpickup_limit = {pick}\nprint vcoil icoil vpickup_limit\n.endc\n.end\n"
    write(name, t)
pickup("A_pickup_25C.cir", "Coil pick-up at 25 C: both gates 1.8 V, rail 4.75 V, coil at 68.2 ohm", 1.8, RAILLO, 68.2, 0.5102, 3.5)
pickup("A_pickup_70C.cir", "Coil pick-up at 70 C air: both gates 1.8 V, rail 4.75 V, coil 68.2 x 1.2 = 81.84 ohm, FET resistance x 1.28", 1.8, RAILLO, 81.84, 0.3986, 4.2)

# rest states
def rest(state, v):
    pts = pwl_edges(10e-3, 10e-3, 8, 5e-3)
    last = 10e-3 + 7*10e-3
    t = f"Interlock rest state: controller output {state} after the last edge, variant {v}; gate decay to the lowest FET threshold, slowest corner\n" + HDR
    t += f"Vsup +5V GND {RAILHI}\n" + COIL55 + CG
    if state == "high":
        t += f"Vpol POL_OUT GND PWL({' '.join(pts[:-2])} {last+5e-3:.9f} 3.3)\n"
    elif state == "low":
        t += f"Vpol POL_OUT GND PWL({' '.join(pts)} 3 0)\n"
    else:
        t += f"Vsrc SRC GND PWL({' '.join(pts)} 3 0)\nSzz SRC POL_OUT CTL GND SWZ\nVctl CTL GND PWL(0 1 {last+0.5e-3:.9f} 1 {last+0.5e-3+1e-9:.9f} 0)\n.model SWZ SW(vt=0.5 vh=0.1 ron=1 roff=1e12)\n"
    t += OPT + ".tran 5u 3000m 0 20u\n.control\n" + var(v) + corner(SLOW) + "run\n"
    t += f"meas tran vstartA FIND v(POL_GATE_A) AT={last+1e-3:.9f}\nmeas tran tA06 WHEN v(POL_GATE_A)=0.6 FALL=1\nmeas tran tB06 WHEN v(POL_GATE_B)=0.6 FALL=1\n"
    t += f"meas tran tdecA TRIG AT={last:.9f} TARG v(POL_GATE_A) VAL=0.6 FALL=1\nmeas tran tdecB TRIG AT={last:.9f} TARG v(POL_GATE_B) VAL=0.6 FALL=1\n.endc\n.end\n"
    write(f"A_rest_{state}_{v}.cir", t)
for s in ("high", "low", "float"):
    for v in ("rec", "fix"):
        rest(s, v)

# buffer output peak current at an edge (informative for the output's absolute maximum): fresh start, rail top, Cc at its largest
t = "Interlock: peak supply current of U201 at the first rising edge, Cc at its largest\n" + HDR
t += f"Vsup +5V GND {RAILHI}\nVpol POL_OUT GND PWL(0 0 1m 0 1.00001m 3.3 6m 3.3)\n" + COIL55 + OPT
t += ".tran 0.05u 3m\n.control\n" + corner(SLOW) + "run\nmeas tran ipeak MIN i(Vsup) FROM=0.99m TO=1.2m\n.endc\n.end\n"
write("A_buffer_peak.cir", t)
print("decks written")
