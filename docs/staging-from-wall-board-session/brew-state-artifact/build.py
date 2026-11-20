"""Build the new Brew State page from the saved live version (v62) plus the wall-board parts."""
import base64, sys

SRC, PARTS, MASKS, DST = sys.argv[1:5]
lines = open(SRC, encoding="utf-8").read().split("\n")
L = lambda a, b: lines[a - 1:b]          # 1-based inclusive
part = lambda n: open(f"{PARTS}/{n}", encoding="utf-8").read().rstrip("\n").split("\n")
b64 = lambda n: base64.b64encode(open(f"{MASKS}/{n}", "rb").read()).decode()

assert lines[0].startswith("<!doctype html>") and lines[1] == "<title>Brew State</title>"
assert lines[955] == "</body></html>"
assert lines[303] == "</section>" and lines[304].startswith('<section class="wide" aria-labelledby="h-layers">')
assert lines[393].startswith('<section class="col" aria-labelledby="h-wall">') and lines[640] == "</section>"
assert lines[662] == "<script>" and lines[953] == "</script>"

css = L(2, 176)
css = [l for l in css if not l.startswith(".checks")]
css = "\n".join(css)
reps = [
    (".viewer { position: relative; aspect-ratio: 2400 / 2302; width: 100%;",
     ".viewer { position: relative; aspect-ratio: var(--ar, 2400 / 2302); width: 100%; max-width: var(--vw, 100%); margin-inline: auto;"),
    (".stage { position: relative; width: calc(var(--z, 1) * 100%); aspect-ratio: 2400 / 2302; }",
     ".stage { position: relative; width: calc(var(--z, 1) * 100%); aspect-ratio: var(--ar, 2400 / 2302); }"),
    (".tile .thumb { position: relative; display: block; aspect-ratio: 2400 / 2302;",
     ".tile .thumb { position: relative; display: block; aspect-ratio: var(--ar, 2400 / 2302);"),
    (".tiles { display: grid; grid-template-columns: repeat(10, minmax(0, 1fr));",
     ".tiles { display: grid; grid-template-columns: repeat(var(--tc, 10), minmax(0, 1fr));"),
    ("@media (max-width: 720px) { .tiles { grid-template-columns: repeat(5, minmax(0, 1fr)); } }",
     "@media (max-width: 720px) { .tiles { grid-template-columns: repeat(var(--tc-m, 5), minmax(0, 1fr)); } }"),
    (".ctl .sep { flex-basis: 100%; height: 0; }",
     ".ctl .sep { flex-basis: 100%; height: 0; }\n.ctl.lead { margin: 0 0 12px; }"),
]
for a, b in reps:
    assert css.count(a) == 1, a
    css = css.replace(a, b)

wall_css = [
    f'.WT {{ background-image: url("data:image/webp;base64,{b64("render_top.webp")}"); }}',
    f'.WB {{ background-image: url("data:image/webp;base64,{b64("render_bottom.webp")}"); }}',
    f'.W1 {{ --m: url("data:image/webp;base64,{b64("F.Cu.webp")}"); --c: var(--l1); }}',
    f'.W2 {{ --m: url("data:image/webp;base64,{b64("B.Cu.webp")}"); --c: var(--l6); }}',
    f'.WE {{ --m: url("data:image/webp;base64,{b64("Edge.Cuts.webp")}"); }}',
    f'.WS {{ --m: url("data:image/webp;base64,{b64("F.SilkS.webp")}"); }}',
    f'.WBS {{ --m: url("data:image/webp;base64,{b64("B.SilkS.webp")}"); }}',
]

import re as _re
head = L(225, 237)
_h = [i for i, l in enumerate(head) if l.startswith('  <img src="data:image/webp;base64,')]
assert len(_h) == 1
head[_h[0]], _n = _re.subn(r'data:image/webp;base64,[A-Za-z0-9+/=]+',
                           "data:image/webp;base64," + base64.b64encode(open(f"{PARTS}/hero.webp", "rb").read()).decode(), head[_h[0]])
assert _n == 1
intro = L(238, 241)
old = "The heater wall board is new: it carries the two heater switches out to the steel wall, where their heat has somewhere to go. "
assert old in intro[1]
intro[1] = intro[1].replace(old, "The heater wall board switches the two heaters from the machine's steel wall. ")

pair = L(243, 259)
old = "<td>Routed; checks under way</td>"
assert old in pair[12]
pair[12] = pair[12].replace(old, "<td>Routed; round gate passed; order files judged; not ordered</td>")

out = (
    [css]
    + L(205, 224) + wall_css + head
    + intro + [""] + pair + [""] + L(261, 279) + [""] + part("wall_section.html")
    + L(280, 304) + part("layers_section.html")
    + L(383, 392) + L(642, 662)
    + part("scripts.html") + [""]
)
open(DST, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("wrote", DST, sum(len(x.encode()) + 1 for x in out))
