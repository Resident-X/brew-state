* Device models for the interlock decks. Every parameter is a datasheet LIMIT or a fit to datasheet limits,
* never a typical figure; the source of each is in circuit-proof.md and circuit-verdicts.md.
* 74AHCT1G17 (Nexperia, Rev. 4, 15 September 2023, Table 8 and Table 7): Schmitt input, VT+ at most 2.0 V,
* VT- at least 0.5 V (VCC 4.5-5.5 V, -40..85 C). Output: VOH >= 3.8 V at -8 mA (VCC 4.5 V, -40..85 C), i.e. a
* drop of at most 0.7 V at 8 mA, taken as a resistance of 87.5 ohm (the drop of a driver is convex in its
* current through the origin, so 87.5 ohm bounds the drop at any current below 8 mA); VOL <= 0.44 V at 8 mA, 55 ohm.
.model SWH SW(vt=1.25 vh=0.75 ron=87.5 roff=1e9)
.model SWL SW(vt=-1.25 vh=0.75 ron=55 roff=1e9)
.subckt AHCT1G17 a y vcc gnd
S1 vcc y a gnd SWH
S2 y gnd gnd a SWL
.ends
* Schottky, onsemi BAT54HT1G (Rev. 3, Oct 2005): VF max 0.32 V at 1 mA, 0.40 V at 10 mA, 0.80 V at 100 mA, 25 C.
.model DSCH D(IS=4.2e-9 N=1 RS=2.3 CJO=0 BV=30)
* Silicon diode, Nexperia BAS116 (SOT23 sheet, Table 7): VF max 0.9 V at 1 mA, 1.0 at 10 mA, 1.1 at 50 mA,
* 1.25 at 150 mA, 25 C; fitted so that it equals the limit at 1 mA and stays under it at the others.
.model DSI D(IS=7.0e-19 N=1 RS=1.4 CJO=0 BV=75)
* Zener, Nexperia BZX84-C12 (Rev. 7, 1 Jan 2023, Table 8): VZ 11.4..12.7 V at 5 mA, 25 C. BV is the low end.
.model DZ12 D(IS=1e-14 N=1 RS=0 BV=11.4 IBV=5m)
* N-FET, Nexperia NX3008NBK (5 November 2022, Table 7): VGSth 0.6..1.1 V at 250 uA; RDSon <= 2.8 ohm at
* VGS=1.8 V, ID=10 mA, 25 C. Level 1 model; KP is set per deck from that limit; VTO is set per deck.
.model NM NMOS(LEVEL=1 VTO=1.1 KP=0.5 LAMBDA=0 GAMMA=0 PHI=0.6 CBD=0 CBS=0 IS=0)
* the clamp diodes carry their own model name so that a deck can move them alone
.model DCL D(IS=7.0e-19 N=1 RS=1.4 CJO=0 BV=75)
