#!/bin/bash
# Regenerates and runs every interlock deck; each log is A_<deck>.log; prints exit status and measurement lines.
cd "$(dirname "$0")"
python3 -I A_gen_decks.py >/dev/null
for f in A_*.cir; do
  [ "$f" = "A_interlock.cir" ] && continue
  d=${f%.cir}
  ngspice -b $f -o $d.log >/dev/null 2>&1; echo "== $d exit=$?"
  grep -i -E '^(vstart|ta0|tb0|tdec|tr0|tcoil|i0|vpeak|tabove|gmin|ipeak|vlo|vcoil|icoil|vpickup)[a-z0-9_]* *=' $d.log
  grep -E '^Error' $d.log
done
