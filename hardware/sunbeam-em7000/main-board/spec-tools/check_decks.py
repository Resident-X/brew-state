"""Compare the resistor, capacitor and inductor values in circuit-proof/*.cir with the values of the same reference in schematic-spec.yaml.
usage: python3 spec-tools/check_decks.py   (from the main-board folder; needs PyYAML)"""
import yaml, glob, re, sys
spec = yaml.safe_load(open('schematic-spec.yaml'))
val = {p['ref']: str(p['value']) for s in spec['sheets'] for p in s['parts']}
mult = {'t': 1e12, 'g': 1e9, 'meg': 1e6, 'k': 1e3, 'm': 1e-3, 'u': 1e-6, 'n': 1e-9, 'p': 1e-12, 'f': 1e-15}
def num(s):
    s = s.strip().lower().replace('ohm', '').replace('Ω', '').replace('µ', 'u')
    s = re.sub(r'(?<=[0-9.])([a-z]*)f$', r'\1', s) if re.search(r'[0-9.](p|n|u|m)?f$', s) else s
    s = re.sub(r'h$', '', s) if re.search(r'[0-9.](p|n|u|m)h$', s) else s
    m = re.match(r'^([0-9.]+(?:e[-+]?[0-9]+)?)\s*([a-z]*)$', s)
    if not m: return None
    x = float(m.group(1)); u = m.group(2)
    if u == '': return x
    if u == 'r': return x
    if u in mult: return x * mult[u]
    return None
bad = 0; checked = 0
for f in sorted(glob.glob('circuit-proof/*.cir')):
    for ln, line in enumerate(open(f, encoding='utf-8', errors='replace'), 1):
        m = re.match(r'^([RCL]\d{3})\s+\S+\s+\S+\s+(\S+)', line.strip())
        if not m or m.group(1) not in val: continue
        ref, v = m.group(1), m.group(2)
        a, b = num(v), num(val[ref])
        checked += 1
        if a is None or b is None:
            continue
        if abs(a - b) > 1e-6 * max(abs(a), abs(b), 1e-30):
            bad += 1; print(f'{f}:{ln}: {ref} deck {v} spec {val[ref]}')
print('checked', checked, 'lines; mismatches', bad)
