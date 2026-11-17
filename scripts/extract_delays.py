#!/usr/bin/env python3
"""Print the worst data-arrival time per corner from the last post-PnR STA step.

Usage: extract_delays.py <run_dir>
"""
import glob
import json
import os
import re
import sys

run = sys.argv[1]
steps = sorted(glob.glob(os.path.join(run, "*-openroad-stapostpnr")))
if not steps:
    sys.exit("no stapostpnr step found")
out = {}
for corner_dir in sorted(glob.glob(os.path.join(steps[-1], "*", ""))):
    rpt = os.path.join(corner_dir, "max.rpt")
    if not os.path.exists(rpt):
        continue
    txt = open(rpt).read()
    m = re.search(r"Startpoint:\s*(\S+).*?Endpoint:\s*(\S+).*?([\d.]+)\s+data arrival time", txt, re.S)
    if m:
        out[os.path.basename(os.path.dirname(corner_dir))] = {
            "start": m.group(1), "end": m.group(2), "arrival_ns": float(m.group(3))}
print(json.dumps(out, indent=2))
