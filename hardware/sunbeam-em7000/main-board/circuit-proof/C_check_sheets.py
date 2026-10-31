#!/usr/bin/env python3
"""Checks the three sheet fragments of blocks 500-599: every pin of every part is in exactly one net or in
no_connect, no pin is named twice, every net has a designer name, references stay inside 500-599 and are unique.
Pin counts per symbol are the stock symbols' (KiCad 10 libraries)."""
import importlib.util, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("G", os.path.join(HERE, "C_gen_sheets.py"))
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
PINS = {"Device:R": 2, "Device:C": 2, "Device:D_TVS": 2, "Diode:BAT54S": 3, "Device:Polyfuse": 2, "Connector_Generic:Conn_01x02": 2,
        "Connector_Generic:Conn_01x03": 3, "Connector_Generic:Conn_01x04": 4, "Connector:TestPoint": 1, "74xGxx:74LVC1G17": 5}
bad = 0
seen_refs = set()
for S in (G.S1, G.S2, G.S3):
    used = {}
    for n, (scope, pins) in S.nets.items():
        if n.startswith("Net-") or n.startswith("unconnected"):
            print("tool-style name", n); bad += 1
        for p in pins:
            if p in used:
                print("pin in two nets", p, used[p], n); bad += 1
            used[p] = n
    for pin, why in S.nc:
        if pin in used:
            print("no-connect pin also in a net", pin); bad += 1
        used[pin] = "NC"
    for p in S.parts:
        ref = p["ref"]
        num = int(''.join(ch for ch in ref if ch.isdigit()))
        if not 500 <= num <= 599:
            print("reference outside 500-599", ref); bad += 1
        if ref in seen_refs:
            print("duplicate reference", ref); bad += 1
        seen_refs.add(ref)
        for i in range(1, PINS[p["lib_id"]] + 1):
            if "%s.%d" % (ref, i) not in used:
                print("pin without net", ref, i); bad += 1
    refs = {p["ref"] for p in S.parts}
    for pin in used:
        if pin.split(".")[0] not in refs:
            print("net names an unknown part", pin); bad += 1
    print("%-45s parts %3d nets %3d" % (S.name, len(S.parts), len(S.nets)))
print("problems:", bad)
sys.exit(1 if bad else 0)
