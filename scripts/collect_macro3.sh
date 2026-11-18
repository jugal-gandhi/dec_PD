#!/usr/bin/env bash
# Gather one v3 macro run into results/m3_<name>/ for publication.
# Usage: collect_macro3.sh <name> <outcome>
set -uo pipefail
N=$1
OUTCOME=$2
R=results/m3_$N
mkdir -p "$R"
RUN=$(ls -1d librelane/v3/macros/"$N"/runs/*/ 2>/dev/null | tail -n 1)
cat > "$R/status.json" <<EOF
{"macro": "$N", "outcome": "$OUTCOME", "commit": "${GITHUB_SHA:-local}", "run_id": "${GITHUB_RUN_ID:-local}"}
EOF
cp -f flow_console_"$N".log "$R/" 2>/dev/null || true
if [ -n "${RUN:-}" ]; then
  cp -f "$RUN"/flow.log "$RUN"/error.log "$RUN"/warning.log "$R/" 2>/dev/null || true
  find "$RUN" -maxdepth 2 -name 'metrics.json' -exec cp -f {} "$R/metrics.json" \; 2>/dev/null
  find "$RUN" -type f \( -name '*.rpt' -o -name '*.log' -o -name '*.json' -o -name '*.tcl' \) \
       -size -20M -print0 | tar czf "$R/run_reports.tar.gz" --null -T - 2>/dev/null || true
fi
[ -f "ip/v3/macros/$N/metrics.json" ] && cp -f "ip/v3/macros/$N/metrics.json" "$R/metrics.json"
cp -f ip/v3/macros/"$N"/lef/*.lef "$R/" 2>/dev/null || true
GDS=ip/v3/macros/$N/gds/$N.gds
[ -f "$GDS" ] && gzip -9 -c "$GDS" > "$R/$N.gds.gz"
du -sh "$R"
