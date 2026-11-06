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
'**Nets probed without a test point.** The board carries 84 test points. Twelve nets that earlier drafts gave a test point pad (TP203, TP520, TP521, TP524, TP601, TP672, TP701, TP711, TP822, TP823, TP862, TP863) have none, because the pads were removed to relieve the crowded strips. Where the Test point column of a key-signal row below names a part that is not a test point (a resistor, a connector or an integrated circuit), the row names the pad or pin to probe: ten nets are probed at the pad of a resistor or the pin of a connector that stands on the net (POL_OUT at R207 pad 1, FLOW_IN at R522 pad 2, STM_SCL at R523 pad 2, BREW_SCL at R527 pad 2, PUMP_C_GATE at R701 pad 1, PUMP_S_GATE at R711 pad 1, ANODE_GATE at R821 pad 1, BUZZER at R826 pad 1, KNOB_STEAM at J861 pin 3 and TANK_LEVEL at J862 pin 2), a 0603 pad or a connector pin a probe or a clip reaches without a stand-off. AMC_DRDY (U601 pin 16 or U401 pin 57) and WT2_DATA (U631 pin 12 or U401 pin 79) have only integrated-circuit pins on them and no passive part, so a probe takes the leg of a fine-pitch package (1.27 mm for the SOIC parts, 0.5 mm for the LQFP-100 controller) directly, with a fine-tip probe or a clip made for the package, and cannot be left connected on the bench.','',
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
