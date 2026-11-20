#!/usr/bin/env python3
"""Build the heater wall board's own separation-basis.yaml (PROPOSED, UNSIGNED) from the shared record's figures.
usage: build_basis.py <shared separation-basis.yaml> <out.yaml> [--sign]   (--sign writes a THROWAWAY signature for a structure test only)"""
import sys, yaml, textwrap
src, out = sys.argv[1:3]
sign = "--sign" in sys.argv
d = yaml.safe_load(open(src))
PH = "PROPOSED, UNSIGNED: to be entered by the main session from the owner's recorded words"
BY = "THROWAWAY test signature, never delivered" if sign else PH
ON = "2026-11-19" if sign else PH

def block(text, w=118):
    return "\n".join(textwrap.fill(p, w, initial_indent="# ", subsequent_indent="# ") if p else "#" for p in text.split("\n"))

HEADER = """The separation basis record of the Sunbeam EM7000 heater wall board: the figures for the distance between mains-referenced and low-voltage conductors, and between conductors at different potentials of the mains supply, that this board design is held to, read by the pre-order board check. It is the board's own record, found before the machine's (hardware/sunbeam-em7000/separation-basis.yaml) because the check reads the separation-basis.yaml nearest at or above the design: the machine's record names the main board's pad pairs, nets and entry fuse, and every one of its 42 exception entries, its entry fuse F101 and its held_at_reinforced nets fail this board, which has none of them. The figures below are the machine's, copied unchanged.

PROPOSED, UNSIGNED. This record has not been accepted by the owner. accepted_by and accepted_on, here and on every entry, are placeholders for the main session to enter from the owner's recorded words; an unsigned entry fails the check, which is the intended state until then. The owner's acceptances W-2, W-4 and W-9 (hardware/sunbeam-em7000/heater-wall-board/owner-sign-off.md) were given on 2026-11-18 and 2026-11-19 for the THROUGH-HOLE figures (the onsemi MOC3083M, DIP-6, opto-triac pin gap 0.94 mm). The package has since changed to the surface-mount onsemi MOC3083SR2M (LCSC C111561, the owner's option A, 2026-11-19). W-9 1b (the tight gaps between two mains-side points) stands with the opto-triac pin gap now 1.04 mm; W-9 1a (the opto-triac's roughly 7 mm external creepage and clearance under the 10.0 mm declared for mains to low voltage, resting on the part's own 4170 V rms isolation rating) is OWED a re-confirmation on the surface-mount figures, and the parts order must not proceed before it is given (owner-sign-off.md, W-9 and the keeper's note).

What this record holds that the machine's does not. (1) Barrier heater-switch, formed by the opto-triacs U911 and U921 and the board spacing around them: the part's own external creepage and clearance of at least 7 mm (onsemi MOC3083M/D Rev. 2, p.2 and p.4; VISO 4170 Vrms for one minute) under the declared 10.0 mm creepage, owner-accepted as an exception for the through-hole part (W-2) and owed a re-confirmation for the surface-mount part; the board path lengthened by a 1.5 mm slot cut under each part (layout-plan.md MAINS-4, BOARD-3, layout-hedges.md hedge 5); the 10.0 mm figure itself unchanged. (2) Barrier mains-to-earthed-plate, the triac's insulated tab and the mains copper toward the earthed spreader plate at the basic creepage of 2.6 mm: the case's tray carries an insulating barrier between the bare plate face and the mains copper, the board's top edge set back 1.0 mm from the plate plane (owner-sign-off.md W-10, which replaces the 6.0 mm lift of W-9 1c); the barrier awaits the case step, and the plate's earth bond is measured at bring-up (DEL-HW-BRING-UP.C6). The check cannot see the plate or the tray, so this record states the barrier and no entry excuses it. (3) The accepted pad pairs of this board, below.

The mains_to_mains entry fuse. This board carries no net ahead of the entry fuse (MAINS_ENTRY is none): the entry fuse F101 is on the main board. The check requires entry_fuse to name a reference of this layout whatever MAINS_ENTRY says (hardware/tools/board_check.py, mains_pairs, the test that entry_fuse is among the layout's references). No honest value passes: F101 is the machine's fuse and is truthfully named here; the check reports it as no reference on this layout. That is a gap in the check, reported to the main session, and no reference of this board is named in its place. held_at_reinforced is empty: this board has no relay contact whose bridge would defeat a safety function, and none of /LINE, /LINE1, /LINE_IN.

The accepted pad pairs. Each is a pair of pads of one part whose gap the part's own land pattern or the owner-accepted oval triac pads leave under the 2.0 mm terminal clearance and the 2.6 mm creepage. Each pair has two entries, one of clearance and one of creepage, as the check reports each. accepted_mm is set 0.01 mm under the gap measured on the committed board (HEAD b5f2547d: 1.04 mm for the triac pins T911 and T921 1-2 and 2-3 and for the opto-triac pads U911 and U921 4-5 and 5-6; 1.80 mm for the 1206 pads of R911, R912, R921 and R922), because the check fails an entry whose accepted distance is above what the layout leaves. The reasons and bounds are those of owner-sign-off.md W-2, W-4, W-6, W-7 and W-9 and of open-items.md, quoted or paraphrased there and cited here, not new ones. The varistor leads of RV911 and RV921 (5.0 mm apart) and every other pair are not entered, because the check reports no shortfall for them."""

BAR = [
 {"barrier": "heater-switch", "insulation": "reinforced", "earth_bonded": False,
  "touchable": ["USB connector", "operator controls", "enclosure"],
  "formed_by": "the opto-triacs U911 and U921 between the heater drive and the triac gate, and the board spacing around them. Bought parts U911 and U921, onsemi MOC3083SR2M (LCSC C111561, the surface-mount form of the part in the onsemi MOC3081M / MOC3082M / MOC3083M sheet, MOC3083M/D Rev. 2, September 2022): external creepage and clearance at least 7 mm, VISO 4170 Vrms for one minute, VIORM 850 Vpk, VIOTM 6000 Vpk, CTI 175, pollution degree 2. 7 mm falls below the declared 10.0 mm creepage and the 3.0 mm clearance is met; the creepage is an owner-accepted exception (owner-sign-off.md W-2 for the through-hole part, W-9 1a owed a re-confirmation for the surface-mount part). The board path under each part is lengthened by a 1.5 mm slot (layout-plan.md MAINS-4, BOARD-3), which does not lengthen the path over the moulding; the opto-triac pads on the mains side stand apart from the low-voltage pads by the land pattern, with no copper between the pad rows (layout-plan.md MAINS-5)."},
 {"barrier": "mains-to-earthed-plate", "insulation": "basic", "earth_bonded": True,
  "touchable": ["earthed spreader plate", "the machine's steel wall it is screwed to"],
  "formed_by": "the insulated tab of the triacs T911 and T921 (ST BTA16-800BWRG, tab rated 2500 Vrms, UL 1557 file E81734, ST DS2114 Rev 11 p.1) to the earthed plate, and the board's mains copper toward the plate held to the basic creepage of 2.6 mm by an insulating barrier in the case's fixed tray (owner-sign-off.md W-10), the board's top edge set back 1.0 mm from the plate plane. The plate is bonded to protective earth through the machine's steel wall and mains-inlet earth, which the owner holds as a fact and bring-up measures (DEL-HW-BRING-UP.C6). The barrier is realised by the case step and is not seen by the pre-order check."},
]

def ent(pair, constraint, a, b, measured, accepted, reason, bound):
    return {"pair": "mains_to_mains", "constraint": constraint, "between": [a, b], "accepted_mm": accepted,
            "reason": reason, "bounded_by": bound, "accepted_by": BY, "accepted_on": ON}

BOUND_W4 = ("Each pad pair is functional insulation inside one switched branch: a tracking short across it fails 'heater on' or 'gate network shorted', both bounded by the interlock relay K201 (which acts when the controller stops refreshing it or the 5 V rail collapses) and the firmware's stuck-on current threshold with every heater commanded off, which must trip at 2.0 A or less (REQ-ACTUATION-CONFIRMATION-001.C10, a requirement no node delivers yet), and by the element's own thermostats and cutoffs; none is a shock path (owner-sign-off.md W-4, W-6, W-9 1b, and the failure-mode table of circuit-proof.md). The conformal coat comes after bring-up and is no part of the bound until it is applied.")
ex = []
R_REASON = "{r} (200 ohm, R_1206_3216Metric, UNI-ROYAL C18002) is one of the two series gate resistors of its heater's gate network ({pair}), between the opto-triac's output and the triac gate. Its two pads stand 1.80 mm apart edge to edge, which is the 1206 package's own pad gap and not a layout choice; the gap meets the 1.5 mm clearance and falls short of the 2.0 mm pad-to-pad terminal clearance and the 2.6 mm creepage. The same footprint and circuit as the main board's R704, R705, R714 and R715, whose 1.8 mm entries the machine's record carries (open-items.md, 'A barrier the basis does not list'); accepted by the owner on 2026-11-18 as one of the 1206 gate-resistor pad pairs (owner-sign-off.md W-4, W-9 1b). The part is not changed, and the entry excuses only this pair of pads. Measured on the committed board: 1.80 mm; accepted down to 1.79 mm."
T_REASON = "{t} (ST BTA16-800BWRG, insulated TO-220AB) pins {a} and {b} on the board-library oval-pad footprint: the pads are 1.5 mm across the row by 2.5 mm, drill 1.1 mm, at the 2.54 mm lead pitch, so the gap between adjacent pads is 1.04 mm, at least the 1.0 mm that layout-hedges.md hedge 4 sets (round 1.9 mm pads would leave 0.74 mm); it falls short of the 2.0 mm terminal clearance and the 2.6 mm creepage. Accepted by the owner on 2026-11-18 as one of the TO-220 pin pairs of T911 and T921 (owner-sign-off.md W-4, W-9 1b). The part is not changed, and the entry excuses only this pair of pads. Measured on the committed board: 1.04 mm; accepted down to 1.03 mm."
U_REASON = "{u} (onsemi MOC3083SR2M, surface-mount, six-pin) pin 5, which the maker gives no connection and the board leaves unconnected, is the output side's substrate; its net is named in the Mains class so that the check holds it to the mains figures. It stands 1.04 mm edge to edge from pin {o} (on {net}) on the land pattern the part is drawn with; the gap falls short of the 2.0 mm terminal clearance and the 2.6 mm creepage. The same class of entry as the machine's record carries for the main board's opto-triacs U701 and U711 (U701.5 with U701.4 and U701.6). Accepted by the owner on 2026-11-19 as the opto-triac pin pair (owner-sign-off.md W-9 1b) on the through-hole gap of 0.94 mm; W-9 records that 1b stands with the pin gap now 1.04 mm. The entry excuses only this pair of pads. Measured on the committed board: 1.04 mm; accepted down to 1.03 mm."
pairs = []
for r, n in (("R911", "R911 and R912, the coffee side"), ("R912", "R911 and R912, the coffee side"), ("R921", "R921 and R922, the steam side"), ("R922", "R921 and R922, the steam side")):
    pairs.append((f"{r}.1", f"{r}.2", 1.79, R_REASON.format(r=r, pair=n)))
for t in ("T911", "T921"):
    for a, b in (("1", "2"), ("2", "3")):
        pairs.append((f"{t}.{a}", f"{t}.{b}", 1.03, T_REASON.format(t=t, a=a, b=b)))
NETS = {("U911", "4"): "HEAT_C_OPTO_MT", ("U911", "6"): "OUT_C", ("U921", "4"): "HEAT_S_OPTO_MT", ("U921", "6"): "OUT_S"}
for u in ("U911", "U921"):
    for o in ("4", "6"):
        pairs.append((f"{u}.5", f"{u}.{o}", 1.03, U_REASON.format(u=u, o=o, net=NETS[(u, o)])))
for a, b, acc, why in pairs:
    for c in ("creepage", "clearance"):
        ex.append(ent("mains_to_mains", c, a, b, None, acc, why, BOUND_W4))

rec = {"standard": d["standard"], "supply": d["supply"], "working_voltage": d["working_voltage"],
       "pollution_degree": d["pollution_degree"], "material_group": d["material_group"], "environment": d["environment"],
       "overvoltage_category": d["overvoltage_category"], "altitude_m": d["altitude_m"],
       "barriers": [b["barrier"] for b in BAR], "barrier_types": BAR,
       "mains_to_low_voltage": d["mains_to_low_voltage"],
       "mains_to_mains": {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 2.6, "creepage_ahead_of_fuse_mm": 2.6,
                          "entry_fuse": "F101", "held_at_reinforced": []},
       "table_rows": d["table_rows"]}
def dump(o): return yaml.safe_dump(o, width=118, sort_keys=False, allow_unicode=True)
text = block(HEADER) + "\n"
for k in ("standard", "supply", "working_voltage", "pollution_degree", "material_group", "environment", "overvoltage_category", "altitude_m", "barriers"):
    text += dump({k: rec[k]})
text += "# Barrier types: the heater switch is reinforced, mains to low voltage, with its low-voltage side not bonded to protective earth (the logic supply is a Class II module whose output is not referenced to earth), as the machine's record declares; the mains-to-earthed-plate barrier is basic, to the earthed plate.\n"
text += dump({"barrier_types": rec["barrier_types"]})
text += dump({"mains_to_low_voltage": rec["mains_to_low_voltage"]})
text += "# The entry fuse F101 is the machine's, on the main board; this board has none (MAINS_ENTRY is none). See the header: the check names it as no reference on this layout.\n"
text += dump({"mains_to_mains": rec["mains_to_mains"]})
text += "# The table rows are the machine's, copied unchanged: the floors the signed figures are read against.\n"
text += dump({"table_rows": rec["table_rows"]})
text += "# Signature of the record. " + ("THROWAWAY test signature for a structure test, never delivered.\n" if sign else "PROPOSED, UNSIGNED.\n")
text += dump({"accepted_by": BY, "accepted_on": ON})
text += "\n" + block("The accepted pad pairs, one entry for each constraint of each pair (24 entries). See the header for where each reason and bound comes from.") + "\n"
text += dump({"accepted_exceptions": ex})
open(out, "w").write(text)
