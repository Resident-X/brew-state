#!/usr/bin/env python3
"""Merge the sheet files in ../sheets into ../schematic-spec.yaml (the one file the drawing agent reads).
usage: python3 spec-tools/build_spec.py      (run from the heater-wall-board folder; needs PyYAML)
The merged file is generated: change the sheet files and run this again, never edit schematic-spec.yaml by hand."""
import yaml, glob, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kilib

ORDER = ["Coffee heater switch", "Steam heater switch", "Low-voltage header", "Return landing"]
sheets = {}
for f in sorted(glob.glob('sheets/*.yaml')):
    d = yaml.safe_load(open(f)); d['source_file'] = os.path.basename(f); sheets[d['sheet']] = d
assert set(sheets) == set(ORDER), set(sheets) ^ set(ORDER)

MAINS_CLASS = """OUT_C OUT_S RET HEAT_C_OPTO_MT HEAT_S_OPTO_MT HEAT_C_GATE_R HEAT_S_GATE_R HEAT_C_TRIAC_G HEAT_S_TRIAC_G""".split()

out_sheets = []
for i, name in enumerate(ORDER, 1):
    s = sheets[name]
    out_sheets.append({
        'order': i, 'sheet': name, 'source_file': s['source_file'], 'function': s.get('function'),
        'parts': s['parts'], 'nets': s['nets'], 'no_connect': s.get('no_connect') or [],
        'custom_symbols': s.get('custom_symbols') or [], 'custom_footprints': s.get('custom_footprints') or [],
        'power_flags': s.get('power_flags') or [], 'drawing_notes': s.get('notes')})

idx = collections.OrderedDict()
for s in out_sheets:
    for n, d in s['nets'].items():
        e = idx.setdefault(n, {'scope': d.get('scope'), 'sheets': []})
        e['sheets'].append(s['sheet'])
net_index = {n: {'scope': e['scope'], 'sheets': e['sheets'], 'class': 'Mains' if n in MAINS_CLASS else 'low-voltage'} for n, e in idx.items()}
for n in MAINS_CLASS: assert n in net_index, n
# a part marked mains must have no pin on a low-voltage net except through a declared barrier part
for s in out_sheets:
    for p in s['parts']:
        if p.get('mains') and not p.get('barrier'):
            for n, d in s['nets'].items():
                if any(x.startswith(p['ref'] + '.') for x in d['pins']):
                    assert net_index[n]['class'] == 'Mains', (p['ref'], n)

parts_total = sum(len(s['parts']) for s in out_sheets)
by_class = collections.Counter(p.get('class') for s in out_sheets for p in s['parts'])
custom_sym = [dict(c, sheet=s['sheet']) for s in out_sheets for c in s['custom_symbols']]
custom_fp = [dict(c, sheet=s['sheet']) for s in out_sheets for c in s['custom_footprints']]

spec = {
 'board': 'Sunbeam EM7000 heater wall board',
 'schema': 'Each sheet is one hierarchical sheet. parts lists every symbol; nets lists every net with every REF.PIN it joins (REF.PIN is the part reference and the symbol pin NUMBER). scope: local = a label on that sheet only; global = a global label carrying the net name across sheets; power = a power symbol / power-flagged net of that name on every sheet it reaches. custom_symbols / custom_footprints list what has no stock KiCad 10 equivalent. A part carrying pinmap and pinmap_source has an accepted physical pin map: pin number, function, and the datasheet page it was read from.',
 'generated_by': 'spec-tools/build_spec.py from sheets/*.yaml; do not edit by hand',
 'drawing': {'tool_notes': [
    "Reference designators are numbered by sheet in the 9xx series (coffee switch T911, U911, R911, R912, RV911, J911; steam switch T921, U921, R921, R922, RV921, J921; header J931; return blade J941). The series is chosen to avoid the main board's references: the shared separation basis keys its pad-pair exceptions by reference designator, and this board's earlier R101 and R102 collided with the main board's discharge-string entries R101 and R102. No reference of this board equals any reference of the main board or of the basis exceptions.",
    'Root sheet: one sheet symbol per entry of sheets, in order, named exactly as the sheet name, with no sheet pins; every connection between sheets is a global label (or a power symbol for scope: power).',
    'Every net carries the designer name given here; no tool-named net may remain. A pin in no_connect gets a no-connect flag.',
    'Symbol fields on every part: Reference, Value (value), Footprint (footprint), LCSC (lcsc), Rating (rating), plus Manufacturer and MPN (maker, mpn). A part with sim_exclude: true is excluded from simulation in its symbol properties.',
    'Flow left to right on each sheet: inputs and supply at the left, outputs at the right; positive supply toward the top, ground toward the bottom. Mains-referenced circuits stand at the left of a sheet and are drawn apart from low-voltage circuits (the barrier part between them); text clear of text and symbols; connector symbols show pin numbers and the net name beside every pin.',
    'Place every part named in a sheet; every numbered part is fitted by the assembler (owner decision of 2026-11-23), and who fits each part is stated in parts-specification.yaml, not here.',
    'Project text variables: MAINS = present. Net class Mains: the nets listed in mains_class_nets.',
    'ERC: a net with only power_in pins needs a PWR_FLAG (the sheet\'s power_flags list names them); no warning may be waived or excluded.']},
 'project_settings': {'MAINS': 'present'},
 'controller': 'none',
 'mains_class_nets': MAINS_CLASS,
 'separation_basis': {'record': '../separation-basis.yaml', 'barrier': 'heater-switch', 'barrier_parts': ['U911', 'U921'], 'insulation': 'reinforced, mains to low voltage', 'not_applicable': 'mains-presence-confirm (the confirms stay off this board, owner decision D2)'},
 'sheets_order': ORDER,
 'totals': {'sheets': len(out_sheets), 'parts': parts_total, 'nets': len(net_index), 'parts_by_catalogue_class': dict(by_class)},
 'header_to_main_board': {
   'ref': 'J931', 'part': 'WB_LV3, 1x3 2.54 mm pin header (XFCN PZ254V-11-03P, C2937625), cable on positions 1 to 3 of the main board J761',
   'pins': [
    {'pin': 1, 'net': '+5V_WB', 'direction': 'power-entering', 'use': 'LED supply to both opto-triac LED anodes, from +5V through the main board isolating link JP761'},
    {'pin': 2, 'net': 'HEAT_C_LED_K', 'direction': 'return sunk by the main board Q761', 'use': 'coffee opto-triac LED cathode'},
    {'pin': 3, 'net': 'HEAT_S_LED_K', 'direction': 'return sunk by the main board Q771', 'use': 'steam opto-triac LED cathode'}],
   'return_landing': {'ref': 'J941', 'net': 'RET', 'note': 'blade; the wire runs to the main board WB_RET blade J110'}},
 'sheets': out_sheets,
 'custom_symbols': custom_sym,
 'custom_footprints': custom_fp,
 'net_index': net_index,
}
class D(yaml.SafeDumper):
    def ignore_aliases(self, data): return True
with open('schematic-spec.yaml', 'w') as f:
    f.write('# Schematic specification of the Sunbeam EM7000 heater wall board: the one file the schematic is drawn from.\n# Generated by spec-tools/build_spec.py from sheets/*.yaml. Do not edit by hand.\n')
    yaml.dump(spec, f, Dumper=D, sort_keys=False, width=220, allow_unicode=True, default_flow_style=False)
print('wrote schematic-spec.yaml', parts_total, 'parts', len(net_index), 'nets', dict(by_class))
