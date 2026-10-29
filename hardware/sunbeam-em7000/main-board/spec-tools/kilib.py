import re, os, glob, functools
S=os.environ.get('KICAD_SHARE','/Applications/KiCad/KiCad.app/Contents/SharedSupport')  # KiCad's SharedSupport folder; set KICAD_SHARE elsewhere
def _parse(text):
    tok=re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+',text)
    pos=0
    def rd():
        nonlocal pos
        t=tok[pos]; pos+=1
        if t=='(':
            l=[]
            while tok[pos]!=')': l.append(rd())
            pos+=1
            return l
        return t[1:-1] if t.startswith('"') else t
    return rd()
@functools.lru_cache(None)
def _libtext(lib):
    p=f'{S}/symbols/{lib}.kicad_sym'
    return open(p,encoding='utf-8').read() if os.path.exists(p) else None
def sym_node(lib,name):
    t=_libtext(lib)
    if t is None: return None
    m=re.search(r'\n\t\(symbol "%s"'%re.escape(name),t)
    if not m: return None
    i=m.start()+1; depth=0; j=i
    while True:
        c=t[j]
        if c=='"':
            j+=1
            while t[j]!='"':
                if t[j]=='\\': j+=1
                j+=1
        elif c=='(': depth+=1
        elif c==')':
            depth-=1
            if depth==0: break
        j+=1
    return _parse(t[i:j+1])
def _walk(n,out):
    if isinstance(n,list):
        if n and n[0]=='pin' and len(n)>2:
            d={'type':n[1]}
            for x in n:
                if isinstance(x,list) and x and x[0]=='name': d['name']=x[1]
                if isinstance(x,list) and x and x[0]=='number': d['number']=x[1]
            out.append(d)
        for x in n: _walk(x,out)
def sym_pins(lib_id):
    lib,name=lib_id.split(':',1)
    n=sym_node(lib,name)
    if n is None: return None
    ext=[x for x in n if isinstance(x,list) and x and x[0]=='extends']
    if ext:
        n=sym_node(lib,ext[0][1])
    pins=[]; _walk(n,pins)
    return pins
def fp_pads(lib_id):
    lib,name=lib_id.split(':',1)
    p=f'{S}/footprints/{lib}.pretty/{name}.kicad_mod'
    if not os.path.exists(p): return None
    return sorted(set(re.findall(r'\(pad "([^"]*)"',open(p).read())))
