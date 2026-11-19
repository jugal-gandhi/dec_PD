#!/usr/bin/env bash
# Functional check of a comparison design against cmp_golden.py (Icarus Verilog).
# Usage: cmp_sim.sh <design>    (after cmp_prepare.sh)
set -euo pipefail
D=$1
ES=${D##*_}
W=build/ext/${D}_sim
mkdir -p "$W"
NV=$(python3 scripts/cmp_golden.py "$ES" "$W")
iverilog -g2012 -DTOP="$D" -DES="$ES" -DNV="$NV" -DVIN="\"$W/vin.hex\"" -DVEXP="\"$W/vexp.hex\"" \
  -o "$W/sim" verif/cmp/tb_cmp.v build/ext/$D/*.v
vvp -n "$W/sim" | tee "$W/sim.log"
grep -q "errors=0" "$W/sim.log"
