#!/usr/bin/env bash
# Copy hardened macro views into ip/v3/macros/<name>/ with fixed names.
# Usage: export_macro3.sh <name> [views_dir]
set -euo pipefail
N=$1
SRC=${2:-build/macros/$N}
DST=ip/v3/macros/$N
mkdir -p "$DST"/{gds,lef,lib,nl,spef,def}
cp "$SRC/gds/$N.gds" "$DST/gds/"
cp "$SRC/lef/$N.lef" "$DST/lef/"
cp "$SRC/nl/$N.nl.v" "$DST/nl/"
cp "$SRC/def/$N.def" "$DST/def/" 2>/dev/null || true
cp "$SRC/metrics.json" "$DST/metrics.json" 2>/dev/null || true
for c in tt_025C_5v00 ss_125C_4v50 ff_n40C_5v50; do
  f=$(find "$SRC/lib" -name "*nom_${c}*.lib" | head -n 1)
  [ -n "$f" ] && cp "$f" "$DST/lib/$N.$c.lib"
done
ls "$DST"/lib/*.lib >/dev/null 2>&1 || { echo "no Liberty views for $N" >&2; exit 1; }
for c in tt_025C_5v00 ss_125C_4v50 ff_n40C_5v50; do
  [ -f "$DST/lib/$N.$c.lib" ] || cp "$(ls "$DST"/lib/*.lib | head -n 1)" "$DST/lib/$N.$c.lib"
done
for r in nom min max; do
  f=$(find "$SRC/spef" -path "*${r}*" -name "*.spef" | head -n 1)
  [ -n "$f" ] && cp "$f" "$DST/spef/$N.$r.spef"
done
grep -m1 "SIZE" "$DST/lef/$N.lef"
