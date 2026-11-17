#!/usr/bin/env bash
# Gather flow outputs into results/<name>/ for publication on a results branch.
# Usage: collect_results.sh <gf180|sky130> <flow_outcome> [equiv_outcome]
set -uo pipefail
NAME=$1
FLOW_OUTCOME=$2
EQUIV_OUTCOME=${3:-skipped}

case "$NAME" in
  gf180)  RUNS=librelane/runs;        FINAL=final;        TOP=chip_top ;;
  sky130) RUNS=librelane/sky130/runs; FINAL=final_sky130; TOP=posit_decoder_32_2 ;;
  soc)    RUNS=librelane/soc/runs;    FINAL=final_soc;    TOP=soc_chip_top ;;
  *) echo "unknown target $NAME"; exit 1 ;;
esac

R=results/$NAME
mkdir -p "$R"

RUN=$(ls -1d "$RUNS"/*/ 2>/dev/null | tail -n 1)
cat > "$R/status.json" <<EOF
{
  "target": "$NAME",
  "commit": "${GITHUB_SHA:-local}",
  "run_id": "${GITHUB_RUN_ID:-local}",
  "flow_outcome": "$FLOW_OUTCOME",
  "equiv_outcome": "$EQUIV_OUTCOME",
  "run_dir": "${RUN:-none}",
  "date_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Console logs from the workflow steps
cp -f flow_console_"$NAME".log "$R/" 2>/dev/null || true
cp -f equiv_console.log "$R/" 2>/dev/null || true
if [ "$NAME" = soc ]; then
  cp -f firmware_build.log soc_sim_console.log flow_console_macro.log "$R/" 2>/dev/null || true
  cp -f verif/soc/out/sim.log "$R/soc_sim.log" 2>/dev/null || true
  cp -f firmware/firmware.hex "$R/" 2>/dev/null || true
  MRUN=$(ls -1d librelane/posit_macro/runs/*/ 2>/dev/null | tail -n 1)
  if [ -n "$MRUN" ]; then
    mkdir -p "$R/macro"
    find "$MRUN" -maxdepth 2 -name 'metrics.json' -exec cp -f {} "$R/macro/metrics.json" \; 2>/dev/null
    cp -f "$MRUN"/flow.log "$MRUN"/error.log "$R/macro/" 2>/dev/null || true
    find "$MRUN" -type f \( -name '*.rpt' -o -name '*.log' -o -name '*.json' \) -size -10M -print0 \
      | tar czf "$R/macro/run_reports.tar.gz" --null -T - 2>/dev/null || true
  fi
  [ -f build/posit_macro/metrics.json ] && cp -f build/posit_macro/metrics.json "$R/macro/metrics.json"
fi
if [ -d verif/out ]; then
  mkdir -p "$R/equiv"
  cp -f verif/out/*.txt verif/out/*.log verif/out/*.v "$R/equiv/" 2>/dev/null || true
fi

if [ -n "${RUN:-}" ]; then
  cp -f "$RUN"/flow.log "$RUN"/error.log "$RUN"/warning.log "$R/" 2>/dev/null || true
  find "$RUN" -maxdepth 2 -name 'metrics.json' -exec cp -f {} "$R/metrics.json" \; 2>/dev/null
  find "$RUN" -maxdepth 2 -name 'metrics.csv' -exec cp -f {} "$R/metrics.csv" \; 2>/dev/null
  # All small text reports and logs, one tarball
  find "$RUN" -type f \( -name '*.rpt' -o -name '*.log' -o -name '*.json' -o -name '*.csv' \
       -o -name '*.txt' -o -name '*.lyrdb' -o -name '*.drc' -o -name '*.tcl' -o -name '*.sdc' \) \
       -size -25M -print0 | tar czf "$R/run_reports.tar.gz" --null -T - 2>/dev/null || true
fi

[ -f "$FINAL/metrics.json" ] && cp -f "$FINAL/metrics.json" "$R/metrics.json"
[ -f "$FINAL/metrics.csv" ] && cp -f "$FINAL/metrics.csv" "$R/metrics.csv"

GDS=$(ls "$FINAL"/gds/"$TOP".gds 2>/dev/null | head -n 1)
if [ -z "$GDS" ] && [ -n "${RUN:-}" ]; then
  # Flow stopped at a sign-off checker: take the newest GDS of the run
  GDS=$(ls -1 "$RUN"/*-klayout-filler/"$TOP".gds "$RUN"/*-klayout-streamout/"$TOP".gds 2>/dev/null | sort | tail -n 1)
fi
if [ -n "$GDS" ]; then
  gzip -9 -c "$GDS" > "$R/$TOP.gds.gz"
fi
NL=$(ls "$FINAL"/nl/"$TOP".nl.v 2>/dev/null | head -n 1)
[ -n "$NL" ] && gzip -9 -c "$NL" > "$R/$TOP.nl.v.gz"
mkdir -p "$R/flow_render"
cp -f "$FINAL"/render/*.png "$R/flow_render/" 2>/dev/null || true

# Keep every file under GitHub's 100 MB limit
find "$R" -type f -size +95M | while read -r f; do
  split -b 90m -d "$f" "$f.part"
  rm -f "$f"
done

du -sh "$R"
find "$R" -maxdepth 2 -type f | sort | head -n 200
