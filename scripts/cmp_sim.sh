#!/usr/bin/env bash
# Functional check of a comparison design against cmp_golden.py (Icarus Verilog).
# Usage: cmp_sim.sh <design>    (after cmp_prepare.sh)
set -euo pipefail
D=$1
W=build/ext/${D}_sim
mkdir -p "$W"
if [ "$D" = "posit_decoder_32_2_hier" ]; then
  # formal equivalence with the signed-off RTL (combinational miter, SAT)
  yosys -q -p "read_verilog src/posit_decoder_32_2.v build/ext/$D/$D.v; prep; flatten; \
    miter -equiv -flatten -make_assert posit_decoder_32_2 $D miter; hierarchy -top miter; \
    sat -verify -prove-asserts -show-ports miter" > "$W/equiv.log" 2>&1
  rc=$?
  tail -n 5 "$W/equiv.log"
  if [ $rc -eq 0 ]; then echo "RESULT equivalence PASS errors=0"; else echo "RESULT equivalence FAIL"; exit 1; fi
  exit 0
fi
if [ "$D" = "percival_32_2" ]; then
  NV=$(python3 scripts/cmp_golden.py percival "$W")
  iverilog -g2012 -DNV="$NV" -DVIN="\"$W/vin.hex\"" -DVEXP="\"$W/vexp.hex\"" \
    -o "$W/sim" verif/cmp/tb_percival.v build/ext/$D/*.v
else
  ES=${D##*_}
  MODE=$ES; case "$D" in lod_*) MODE=lod$ES ;; esac
  NV=$(python3 scripts/cmp_golden.py "$MODE" "$W")
  iverilog -g2012 -DTOP="$D" -DES="$ES" -DNV="$NV" -DVIN="\"$W/vin.hex\"" -DVEXP="\"$W/vexp.hex\"" \
    -o "$W/sim" verif/cmp/tb_cmp.v build/ext/$D/*.v
fi
vvp -n "$W/sim" | tee "$W/sim.log"
grep -q "errors=0" "$W/sim.log"
