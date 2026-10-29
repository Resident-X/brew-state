import yaml,glob,collections
sheets=[yaml.safe_load(open(f)) for f in sorted(glob.glob('sheets/*.yaml'))]
part={};pin2nets=collections.defaultdict(set); net2pins=collections.defaultdict(set)
for s in sheets:
    for p in s['parts']: part[p['ref']]=p
    for n,d in s['nets'].items():
        for pin in d['pins']:
            r=pin.split('.')[0]; pin2nets[r].add(n); net2pins[n].add(pin)
def L(x): return x if isinstance(x,list) else [x]
bad=0
def err(m):
    global bad; bad+=1; print('ISSUE',m)
GND={'GND'}
tps=set(r for r in part if r.startswith('TP'))
used=set()
for f in sorted(glob.glob('bring-up/*.yaml')):
    d=yaml.safe_load(open(f))
    for r in d.get('rails',[]) or []:
        src=L(r['source_sides']); ld=L(r['load_side']); allr=set(src)|set(ld)
        for tp in L(r['test_points']):
            used.add(tp)
            if tp not in part: err(f'{f} {r["name"]}: {tp} not a part'); continue
            ns=pin2nets[tp]-GND
            if not ns<=allr: err(f'{f} {r["name"]}: {tp} on {ns} not in rail nets {allr}')
        for k in L(r['links']):
            if k not in part: err(f'{f} {r["name"]}: link {k} not a part'); continue
            ns=pin2nets[k]
            if len(net2pins and [p for p in net2pins if False])>0: pass
            if not (ns&set(src) and ns&set(ld)) : err(f'{f} {r["name"]}: link {k} nets {ns} vs src {src} load {ld}')
            if part[k]['lib_id'].startswith('Device:R') and str(part[k]['value']) not in ('0','0R','0 ohm'): err(f'{f} {r["name"]}: link {k} resistor value {part[k]["value"]} (a resistor link must be 0, unless it is the first-power substitute position)')
    for r in d.get('producer_only',[]) or []:
        used.add(r.get('test_point'))
        if r.get('test_point') not in part: err(f'{f} prod {r["net"]}: tp missing')
    for k in d.get('key_signals',[]) or []:
        tp=k.get('test_point'); 
        for t in L(tp) if tp else []:
            used.add(t)
            if t not in part: err(f'{f} key {k.get("name")}: {t} not a part')
print('test points in sheets not referenced by any bring-up row:',sorted(tps-used))
# every connector pin in sheets covered?
conn=[r for r in part if r[0] in 'JP' and not r.startswith('JP') and not r.startswith('PJ')]
cp=set()
for f in glob.glob('bring-up/*.yaml'):
    d=yaml.safe_load(open(f))
    for p in d.get('connector_pins',[]) or []: cp.add(str(p['pin']).split('.')[0])
print('J parts without pin rows:',sorted(set(r for r in part if r.startswith('J') and not r.startswith('JP'))-cp))
print('issues',bad)
