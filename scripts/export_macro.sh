#!/usr/bin/env bash
# Copy the hardened posit macro views into ip/posit_macro/ with fixed names.
set -euo pipefail
SRC=${1:-build/posit_macro}
DST=ip/posit_macro
N=posit_decoder_32_2
mkdir -p $DST/gds $DST/lef $DST/lib $DST/nl $DST/spef
cp "$SRC/gds/$N.gds" $DST/gds/
cp "$SRC/lef/$N.lef" $DST/lef/
cp "$SRC/nl/$N.nl.v" $DST/nl/
for c in tt_025C_5v00 ss_125C_4v50 ff_n40C_5v50; do
  f=$(find "$SRC/lib" -name "*nom_${c}*.lib" | head -n 1)
  [ -n "$f" ] && cp "$f" "$DST/lib/$N.$c.lib"
done
if ! ls $DST/lib/*.lib >/dev/null 2>&1; then
  echo "export_macro: no Liberty views found under $SRC/lib" >&2; exit 1
fi
for c in tt_025C_5v00 ss_125C_4v50 ff_n40C_5v50; do
  [ -f "$DST/lib/$N.$c.lib" ] || cp "$(ls $DST/lib/*.lib | head -n 1)" "$DST/lib/$N.$c.lib"
done
for r in nom min max; do
  f=$(find "$SRC/spef" -path "*${r}*" -name "*.spef" | head -n 1)
  [ -n "$f" ] && cp "$f" "$DST/spef/$N.$r.spef"
done
find $DST -type f | sort
