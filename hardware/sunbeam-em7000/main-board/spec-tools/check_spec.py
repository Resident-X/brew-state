#!/usr/bin/env python3
"""Check the sheets against KiCad's stock libraries and for pin and net consistency.
usage: python3 spec-tools/check_spec.py <folder of sheet yaml files | schematic-spec.yaml>
needs PyYAML; KICAD_SHARE names KiCad's SharedSupport folder if not the macOS default."""
import sys, os, glob, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, kilib
def load(path):
    if os.path.isdir(path):
        sheets=[]
        for f in sorted(glob.glob(path+'/*.yaml')):
            d=yaml.safe_load(open(f)); d['_file']=os.path.basename(f); sheets.append(d)
        return sheets
    d=yaml.safe_load(open(path)); return d['sheets']
sheets=load(sys.argv[1])
err=[];warn=[]
refs={}; allnets=collections.defaultdict(list)
custom_sym={}; custom_fp={}
for s in sheets:
    for c in s.get('custom_symbols',[]) or []: custom_sym[c['name']]=c
    for c in s.get('custom_footprints',[]) or []: custom_fp[c['name']]=c
for s in sheets:
    sn=s['sheet']; pinsof={}; 
    for p in s.get('parts',[]):
        r=p['ref']
        if r in refs: err.append(f'{sn}: duplicate ref {r} (also {refs[r]})')
        refs[r]=sn
        lid=p['lib_id']
        if lid in custom_sym:
            pins=[x['number'] for x in custom_sym[lid]['pins']]
        else:
            pp=kilib.sym_pins(lid)
            if pp is None: err.append(f'{sn}: {r} lib_id {lid} not in stock libraries and not a custom symbol'); pins=None
            else: pins=[x['number'] for x in pp]
        pinsof[r]=pins
        fp=p.get('footprint')
        if not fp: err.append(f'{sn}: {r} has no footprint')
        elif fp in custom_fp: pass
        else:
            pads=kilib.fp_pads(fp)
            if pads is None: err.append(f'{sn}: {r} footprint {fp} not found and not custom')
            elif pins is not None:
                missing=[x for x in pins if x not in pads and x!='']
                if missing and not all(m in ('~','') for m in missing): warn.append(f'{sn}: {r} {lid} pins {sorted(set(missing))} have no pad in {fp}')
        for k in ('value','lcsc','class','function'):
            if k not in p: warn.append(f'{sn}: {r} missing {k}')
    covered=collections.defaultdict(list)
    for n,d in (s.get('nets') or {}).items():
        if re.match(r'^(Net-|unconnected-)',n): err.append(f'{sn}: tool-style net name {n}')
        for pin in d.get('pins',[]):
            r,_,pn=str(pin).partition('.')
            if r not in pinsof: err.append(f'{sn}: net {n} pin {pin}: ref not in this sheet'); continue
            if pinsof[r] is not None and pn not in pinsof[r]: err.append(f'{sn}: net {n} pin {pin}: pin number not in symbol')
            covered[(r,pn)].append(n)
        allnets[n].append((sn,d.get('scope')))
    for nc in s.get('no_connect',[]) or []:
        r,_,pn=str(nc['pin']).partition('.'); covered[(r,pn)].append('NC')
    for (r,pn),ns in covered.items():
        if len(ns)>1: err.append(f'{sn}: {r}.{pn} on several nets {ns}')
    for r,pins in pinsof.items():
        if pins is None: continue
        for pn in set(pins):
            if (r,pn) not in covered: err.append(f'{sn}: {r}.{pn} not on any net or no_connect')
    for n,d in (s.get('nets') or {}).items():
        if len(d.get('pins',[]))<2 and d.get('scope')=='local': warn.append(f'{sn}: local net {n} has one pin')
# net scope sanity
for n,occ in allnets.items():
    scopes={sc for _,sc in occ}
    if len(occ)>1 and 'local' in scopes: err.append(f'net {n} is local in one sheet but appears in {len(occ)} sheets: {occ}')
print('sheets',len(sheets),'parts',len(refs),'nets',len(allnets))
for w in warn: print('WARN',w)
for e in err: print('ERR',e)
print('errors',len(err),'warnings',len(warn))
sys.exit(1 if err else 0)
