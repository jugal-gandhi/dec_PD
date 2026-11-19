#!/usr/bin/env bash
# Run pvt_sweep.tcl for every Liberty corner of the 7-track 5 V library.
# Usage: pvt_sweep.sh <macro_dir> <out_dir> [top]
set -uo pipefail
M=$1
OUT=$2
TOP=${3:-posit_decoder_32_2}
PDK_ROOT=${PDK_ROOT:-$PWD/pdk}
SCL=$PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
mkdir -p "$OUT"
find -L "$SCL" -name "gf180mcu_fd_sc_mcu7t5v0__*.lib*" | sort > "$OUT/liberty_list.txt"
find -L "$SCL" -maxdepth 2 > "$OUT/scl_tree.txt"
# sign-off output load from the PDK's flow configuration (pF); 72 fF if not found
CFG=$(grep -rhs "OUTPUT_CAP_LOAD" "$PDK_ROOT/gf180mcuD/libs.tech/librelane" | head -n 1)
FF=$(echo "$CFG" | grep -oE '[0-9]+(\.[0-9]+)?' | tail -n 1)
LOAD_PF=$(python3 -c "print(${FF:-72}/1000)")
echo "{\"output_cap_cfg\": \"${CFG//\"/\'}\", \"load_pf\": $LOAD_PF}" > "$OUT/setup.json"
TLEF=$(find -L "$SCL" -name "*.tlef" | grep -m1 nom || find -L "$SCL" -name "*.tlef" | head -n 1)
CLEF=$(find -L "$SCL" -name "gf180mcu_fd_sc_mcu7t5v0.lef" | head -n 1)
if command -v sta >/dev/null; then RUN="sta -no_splash -exit"; TLEF=""; CLEF=""; else RUN="openroad -no_init -exit"; fi
echo "runner: $RUN | tlef: $TLEF | lef: $CLEF"
declare -A seen
for lib in $(cat "$OUT/liberty_list.txt"); do
  c=$(basename "$lib" | sed -E 's/gf180mcu_fd_sc_mcu7t5v0__//; s/\.lib(\.gz)?$//')
  [ -n "${seen[$c]:-}" ] && continue
  seen[$c]=1
  ps=0; [ "$c" = "tt_025C_5v00" ] && ps=1
  TLEF=$TLEF CLEF=$CLEF TOP=$TOP LIB=$lib NL=$M/nl/$TOP.nl.v SPEF_DIR=$M/spef OUT=$OUT/$c \
    LOAD_PF=$LOAD_PF POWER_SWEEP=$ps timeout 1800 $RUN scripts/pvt_sweep.tcl > "$OUT/$c.log" 2>&1
  echo "$c: exit $? $(grep -c . "$OUT/$c.log") log lines"
done
