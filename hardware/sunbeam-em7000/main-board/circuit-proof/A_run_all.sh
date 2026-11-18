#!/bin/bash
# Regenerates and runs every interlock deck; each log is A_<deck>.log; prints exit status and measurement lines.
# At most four ngspice runs at a time, under nice. An "Error: measure ... out of interval" line means the level was never reached.
cd "$(dirname "$0")"
python3 -I A_gen_decks.py >/dev/null
decks=$(ls A_*.cir | grep -v '^A_interlock.cir$')
echo "$decks" | xargs -P 4 -I{} sh -c 'f={}; d=${f%.cir}; nice ngspice -b $f -o $d.log >/dev/null 2>&1; echo $? > $d.exit'
for f in $decks; do
  d=${f%.cir}
  echo "== $d exit=$(cat $d.exit)"; rm -f $d.exit
  grep -i -E '^(vstart|ta0|tb0|tdec|tr0|tcoil|i0|vpeak|tabove|gmin|ipeak|vlo|vcoil|icoil|vpickup|vgmax|vbufmax|vlate|vpre|tdelay)[a-z0-9_]* *=' $d.log
  grep -E '^Error' $d.log
done
