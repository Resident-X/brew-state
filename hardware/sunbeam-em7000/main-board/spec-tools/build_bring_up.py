"""Writes bring-up-provision.md from bring-up/*.yaml and schematic-spec.yaml (run from the main-board folder; needs PyYAML)."""
import yaml,glob,sys,collections
sys.path.insert(0,'spec-tools'); import kilib
spec=yaml.safe_load(open('schematic-spec.yaml'))
P={p['ref']:p for s in spec['sheets'] for p in s['parts']}
net_of={}
for s in spec['sheets']:
    for n,d in s['nets'].items():
        for pin in d['pins']: net_of[pin]=n
    for nc in s['no_connect']: net_of[nc['pin']]='no-connect'
def L(x): return x if isinstance(x,list) else [x]
def cell(s): return str(s).replace('|','/').replace('\n',' ').strip()
B=[yaml.safe_load(open(f)) for f in sorted(glob.glob('bring-up/*.yaml'))]
rows=[];pins={}
for d in B:
    for r in d.get('rails') or []:
        nets=', '.join(L(r['source_sides']))+', '+', '.join(L(r['load_side']))
        rows.append(('Rail '+cell(r['name']),nets,', '.join(L(r['test_points'])),', '.join(L(r['links'])),r['what']))
for d in B:
    for r in d.get('producer_only') or []:
        what=f"Producer-only net: made by {r.get('producer')}; capacitors {', '.join(r.get('caps') or []) or 'none'}"+(f"; bead {r['bead']}" if r.get('bead') else '')+(f"; part the datasheet requires: {r['part_required_by_datasheet']}" if r.get('part_required_by_datasheet') else '')+('. '+r['what'] if r.get('what') else '')
        rows.append(('Producer-only '+r['net'],r['net'],r['test_point'],'—',what))
for d in B:
    for r in d.get('key_signals') or []:
        rows.append(('Key signal: '+cell(r['name']),r['net'],cell(r['test_point']),'—',r['block']))
for d in B:
    for r in d.get('first_power') or []:
        pin=r['input'].split(' ')[0]
        rows.append(('First power: '+cell(r['input']),cell(r['input']),'—',r.get('link') or '—',f"Means: {r['means']} Limited current: {r['limited_current']}"))
    if d.get('first_power_note'): pass
out=['# Bring-up provision: Sunbeam EM7000 main controller board','',
'Test points, isolating links, first-power current limiting and the pin classification of every connector, terminal, header and tab of the main board, kept to the method in `docs/board-design-method.md` ("Designing for bring-up and a second spin"). It is committed before any footprint is placed, and every row is cross-checked against the schematic specification (`schematic-spec.yaml`, generated into the KiCad schematic) and its exported netlist in the commit before placement.','',
'Part references are those of `schematic-spec.yaml`. A test point is a one-pin pad part (`Connector:TestPoint`, `main-board:TestPoint_Pad_D1.0mm_Tight`) whose pin is on the net it tests. An isolating link is a two-pin part: a 0 ohm resistor, or a 2-pin 2.54 mm header with a shunt jumper, or two plated holes that take a wire link, a lamp or a resistor. Mains-referenced links (JP101) are in the `Mains` net class with the rest of the mains copper.','',
'Where the method requires a rating for a link on a path that carries a protective device\'s fault current, the link\'s conductor row is in `circuit-proof.md`; a link whose rating or conductor row is not met there is listed in `open-items.md` and the row below stays open until the source it names is amended.','',
'## Provisions','',
'| Rail, producer-only net, key signal or first power | Net | Test point | Isolating link | What it is for |','|---|---|---|---|---|']
for r in rows: out.append('| '+' | '.join(cell(x) for x in r)+' |')
# pins
for d in B:
    for key in ('supply_inputs','connector_pins'):
        for p in d.get(key) or []:
            pins.setdefault(p['pin'],p)
conn=[r for r in P if r.startswith('J') and not r.startswith('JP')]
missing=[]
allpins=[]
for r in sorted(conn,key=lambda x:int(x[1:])):
    lid=P[r]['lib_id']
    if lid in [c['name'] for c in spec['custom_symbols']]:
        nums=[c['pins'] for c in spec['custom_symbols'] if c['name']==lid][0]; nums=[x['number'] for x in nums]
    else: nums=[p['number'] for p in kilib.sym_pins(lid)]
    for n in sorted(set(nums),key=lambda x:(len(x),x)):
        allpins.append(f'{r}.{n}')
for pin in allpins:
    if pin not in pins: missing.append(pin)
extra=[p for p in pins if p not in allpins]
out+=['','## Pins of every connector, terminal, header and tab','','| Pin | Net | Class | Why |','|---|---|---|---|']
def key(p):
    import re; r,_,n=p.partition('.'); m=re.match(r'([A-Z]+)(\d+)',r); return (m.group(1),int(m.group(2)),len(n),n)
for pin in sorted(pins,key=key):
    p=pins[pin]; nm=net_of.get(pin,'?')
    if nm!=p['net'] and nm!='no-connect': print('NET MISMATCH',pin,nm,p['net'])
    out.append(f"| {pin} | {cell(p['net'])} | {cell(p['class'])} | {cell(p['why'])} |")
open('bring-up-provision.md','w').write('\n'.join(out)+'\n')
print('rows',len(rows),'pins',len(pins),'missing',missing[:40],len(missing),'extra',extra)
