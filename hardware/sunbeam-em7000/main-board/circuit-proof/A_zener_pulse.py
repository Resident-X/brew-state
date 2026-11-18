#!/usr/bin/env python3
"""Pulse load of the interlock coil clamp Z201 / Z202 (BZX84-C12) by power and energy, for any K201 coil inductance.

Run:  python3 -I A_zener_pulse.py > A_zener_pulse.out   (exit 0 when the M34 limit of 3.4 H, the inductance bring-up must read the coil under, holds against the extrapolated pulse-power line; exit 1 when it does not. The 3.47 H bound and the pulse at the 4.73 H bound of M28 are printed as information)

Circuit (sheet 102, interlock): the K201 coil runs from +5V (A1) to POL_COIL_LO (A2), switched low by Q202. Two clamp branches in parallel,
each a BZX84-C12 (cathode on POL_COIL_LO) in series with a BAS116 to +5V. When the switch opens the coil current circulates through a branch
and decays against the zener voltage; no supply energy enters the loop, so the zener takes at most the coil's stored energy.
No sharing between the two branches is counted: one zener is taken to carry the whole current.

Sources:
  Nexperia BZX84 series Rev. 7 (1 January 2023): BZX84-C12 VZ 11.40 to 12.70 V at IZ 5 mA, rdif 25 ohm maximum at 5 mA (Table 8);
    PZSM 40 W, tp 100 us square, Tj 25 degC before the surge (Table 5); Fig. 1, non-repetitive peak reverse power against pulse duration,
    maximum values, read off the plot: curve (2), Tj 150 degC before the surge, about 30 W at 0.1 ms falling as tp^-0.5 to about 3 W at
    10 ms, where the plot ends (curve (1), 25 degC, about 4 W at 10 ms).
  Hongfa HF115F-I 2020 Rev. 1.00: coil 62 ohm +/-10 %, so 55.8 ohm at its lowest; rail 5.25 V.
  circuit-proof.md interlock removal-time row: the flyback lasts 6.159 ms per henry (clamp at 11.4 V, to the 7.3 mA drop-out current).

Method, conservative at each step:
  peak power: the zener at its highest voltage, 12.70 V plus rdif 25 ohm x (I0 - 5 mA), times the whole coil current I0;
  pulse: a square pulse of that peak power lasting the whole flyback, 6.159 ms/H x L (the real pulse decays, so this over-states it);
  curve beyond 10 ms: extrapolated at constant energy (power falling as 1/tp from the 3 W x 10 ms = 30 mJ end point), steeper than the
    plotted tp^-0.5 slope, so it under-states what the part takes; the plot's own slope continued is shown beside it for comparison;
  energy: the coil's stored energy 0.5 x L x I0^2, an upper bound on what the zener absorbs, against the same 30 mJ.
"""
import math
import sys

R_COIL = 62 * 0.9
I0 = 5.25 / R_COIL
VZ = 12.70 + 25 * (I0 - 5e-3)
P_PEAK = VZ * I0
T_PER_H = 6.159e-3
L_M28 = 4.73
L_M34 = 3.4
P_10MS, E_10MS = 3.0, 3.0 * 10e-3


def curve(tp):
    """Fig. 1 curve (2) read off the plot; beyond 10 ms at constant energy (conservative)."""
    return 3.0 * math.sqrt(10e-3 / tp) if tp <= 10e-3 else E_10MS / tp


def curve_slope(tp):
    return 3.0 * math.sqrt(10e-3 / tp)


print("coil current I0 = 5.25 V / %.1f ohm = %.2f mA; zener voltage at I0 at most 12.70 + 25 x %.4f = %.2f V; peak power %.3f W (one zener, no sharing)"
      % (R_COIL, I0 * 1e3, I0 - 5e-3, VZ, P_PEAK))
print("stored energy 0.5 x L x I0^2 = %.2f mJ per henry" % (0.5 * I0 ** 2 * 1e3))
# Inductance at which the square peak-power pulse meets the extrapolated curve: P_PEAK = E_10MS / (T_PER_H x L)
L_POWER = E_10MS / (P_PEAK * T_PER_H)
L_ENERGY = E_10MS / (0.5 * I0 ** 2)
L_SLOPE = (3.0 / P_PEAK) ** 2 * 10e-3 / T_PER_H
print("limit by peak power held for the whole pulse, constant-energy extrapolation: L at most 30 mJ / (%.3f W x 6.159 ms/H) = %.2f H" % (P_PEAK, L_POWER))
print("limit by energy (stored energy against 30 mJ): L at most %.2f H" % L_ENERGY)
print("for comparison, the plotted tp^-0.5 slope continued gives L at most %.2f H (not used)" % L_SLOPE)
for L in (1.0, 1.6, 3.0, L_POWER, L_M28):
    tp = T_PER_H * L
    print("L %.2f H: pulse %.1f ms, peak %.3f W against the curve's %.3f W (ratio %.2f); energy %.1f mJ against %.0f mJ"
          % (L, tp * 1e3, P_PEAK, curve(tp), P_PEAK / curve(tp), 0.5 * L * I0 ** 2 * 1e3, E_10MS * 1e3))
ok = P_PEAK <= curve(T_PER_H * L_M34)
print("information: the M28 bound %.2f H is %s the conservative extrapolation (ratio %.2f); the bound holds for every coil inductance up to %.2f H without knowing it, and no source bounds the coil's inductance, so the bring-up reading (M34) must confirm it is under %.1f H"
      % (L_M28, "inside" if P_PEAK <= curve(T_PER_H * L_M28) else "outside", P_PEAK / curve(T_PER_H * L_M28), L_POWER, L_M34))
print("%s  M34 limit %.1f H: clamp pulse %.1f ms, peak %.3f W against the extrapolated line's %.3f W (ratio %.2f)"
      % ("PASS" if ok else "FAIL", L_M34, T_PER_H * L_M34 * 1e3, P_PEAK, curve(T_PER_H * L_M34), P_PEAK / curve(T_PER_H * L_M34)))
sys.exit(0 if ok else 1)
