#!/usr/bin/env bash
# Component-wise power and critical path at the SS, TT and FF 5 V corners (nominal RC).
# Usage: comp_apd.sh <macro_dir> <out_dir> <top>
set -uo pipefail
M=$1; OUT=$2; TOP=$3
PDK_ROOT=${PDK_ROOT:-$PWD/pdk}
SCL=$PDK_ROOT/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
mkdir -p "$OUT"
TLEF=$(find -L "$SCL" -name "*.tlef" | grep -m1 nom || find -L "$SCL" -name "*.tlef" | head -n 1)
CLEF=$(find -L "$SCL" -name "gf180mcu_fd_sc_mcu7t5v0.lef" | head -n 1)
if command -v sta >/dev/null; then RUN="sta -no_splash -exit"; TLEF=""; CLEF=""; else RUN="openroad -no_init -exit"; fi
for c in ss_125C_4v50 tt_025C_5v00 ff_n40C_5v50; do
  lib=$(find -L "$SCL" -name "gf180mcu_fd_sc_mcu7t5v0__$c.lib*" | head -n 1)
  TOP=$TOP LIB=$lib NL=$M/nl/$TOP.nl.v SPEF=$M/spef/$TOP.nom.spef OUT=$OUT/$c LOAD_PF=0.07291 TLEF=$TLEF CLEF=$CLEF \
    timeout 900 $RUN scripts/comp_apd.tcl > "$OUT/$c.log" 2>&1
  echo "$c: exit $?"
done
