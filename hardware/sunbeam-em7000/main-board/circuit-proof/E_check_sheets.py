#!/usr/bin/env python3
"""Checks the four sheet fragments of this work package against themselves and against the proof decks.
  1. every pin of every part is in exactly one net or in no_connect (rule 9)
  2. no net or no_connect names a pin the part does not have; every ref is unique across the four sheets
  3. every resistor / capacitor line of a proof deck that carries a sheet reference has the sheet's value
Run from the board folder:  python3 circuit-proof/E_check_sheets.py     (needs PyYAML; the inputs are this folder's own files)
"""
import glob, os, re, sys
import yaml

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
sheets = sorted(glob.glob(os.path.join(root, "sheets", "E?-*.yaml")))
if len(sheets) != 4:
    sys.exit(f"expected four E sheets, found {len(sheets)}")

STOCK_PINS = {
    "Device:R": 2, "Device:C": 2, "Device:FerriteBead_Small": 2, "Connector:TestPoint": 1,
    "Oscillator:ASE-xxxMHz": 4, "Connector_Generic:Conn_01x02": 2, "Connector_Generic:Conn_01x03": 3,
    "Connector_Generic:Conn_01x04": 4, "Connector_Generic:Conn_01x05": 5,
    "Sensor_Temperature:MAX31865xTP": 21, "Analog_ADC:HX711": 16,
}
SI = {"k": 1e3, "K": 1e3, "Meg": 1e6, "M": 1e6, "n": 1e-9, "u": 1e-6, "p": 1e-12}

def val(s):
    m = re.fullmatch(r"([0-9.]+)\s*([a-zA-Z]*)", s)
    return float(m.group(1)) * SI.get(m.group(2), 1.0) if m else None

errors = []
refs = {}
spec_values = {}
for path in sheets:
    d = yaml.safe_load(open(path))
    custom = {c["name"]: len(c["pins"]) for c in d.get("custom_symbols", [])}
    pins_of = {}
    for p in d["parts"]:
        r = p["ref"]
        if r in refs:
            errors.append(f"{r} appears in {refs[r]} and {os.path.basename(path)}")
        refs[r] = os.path.basename(path)
        n = custom.get(p["lib_id"]) or STOCK_PINS.get(p["lib_id"])
        if n is None:
            errors.append(f"{r}: unknown pin count for {p['lib_id']}")
            continue
        pins_of[r] = {str(i) for i in range(1, n + 1)}
        spec_values[r] = p["value"]
    seen = {}
    for net, spec in d["nets"].items():
        for pin in spec["pins"]:
            if pin in seen:
                errors.append(f"{os.path.basename(path)}: {pin} in {seen[pin]} and {net}")
            seen[pin] = net
    for nc in d.get("no_connect", []):
        pin = nc["pin"]
        if pin in seen:
            errors.append(f"{os.path.basename(path)}: {pin} in {seen[pin]} and no_connect")
        seen[pin] = "no_connect"
    for r, pins in pins_of.items():
        for i in pins:
            if f"{r}.{i}" not in seen:
                errors.append(f"{os.path.basename(path)}: {r}.{i} unconnected and not in no_connect")
    for pin in seen:
        r, i = pin.split(".")
        if r not in pins_of or i not in pins_of[r]:
            errors.append(f"{os.path.basename(path)}: {pin} names a pin that does not exist")
    print(f"{os.path.basename(path)}: {len(d['parts'])} parts, {len(d['nets'])} nets, {len(d.get('no_connect', []))} no-connect")

# decks
for deck in sorted(glob.glob(os.path.join(here, "E_*.cir"))):
    for line in open(deck):
        m = re.match(r"^([RC]\d{3})\s+\S+\s+\S+\s+(\S+)\s*$", line.strip())
        if not m:
            continue
        r, v = m.groups()
        if r not in spec_values:
            errors.append(f"{os.path.basename(deck)}: {r} is not a part of the E sheets")
        elif val(v) is None or abs(val(v) - val(spec_values[r])) > 1e-9 * max(1, abs(val(spec_values[r]))):
            errors.append(f"{os.path.basename(deck)}: {r} = {v} but the sheet has {spec_values[r]}")
print("parts checked:", len(refs))
if errors:
    print("\n".join("ERROR " + e for e in errors))
    sys.exit(1)
print("all sheets consistent; deck values match the sheets")
