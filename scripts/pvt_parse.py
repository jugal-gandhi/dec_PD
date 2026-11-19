#!/usr/bin/env python3
"""Parse the OpenSTA PVT-sweep reports into one JSON file.
Usage: pvt_parse.py <results_dir> <out.json>"""
import glob
import json
import os
import re
import sys

END_RE = re.compile(r"^(\S+) \((?:output)\)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)")
STAGE_RE = re.compile(r"^\s*(?:(\d+)\s+)?(?:([\d.]+)\s+)?([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([v^])\s+(\S+)\s+\((\S+)\)")


def ends(path):
    """endpoint -> arrival (ns)"""
    out = {}
    for ln in open(path):
        m = END_RE.match(ln.strip())
        if m:
            out[m.group(1)] = float(m.group(3))
    return out


def power(path):
    for ln in open(path):
        if ln.startswith("Total"):
            v = [float(x) for x in ln.split()[1:5]]
            return dict(internal=v[0], switching=v[1], leakage=v[2], total=v[3])
    return None


def stages(path):
    """cell output stages of the reported path: (pin, cell, stage delay, arrival, slew, cap, fanout)"""
    rows, prev = [], 0.0
    for ln in open(path):
        if "data arrival time" in ln:
            break
        m = STAGE_RE.match(ln)
        if not m:
            continue
        fan, cap, slew, dly, t, _, pin, cell = m.groups()
        t = float(t)
        if fan is not None and "/" in pin:            # cell output pin carries the fanout column
            rows.append(dict(pin=pin, cell=cell, delay=t - prev, arrival=t, slew=float(slew),
                             cap=float(cap) if cap else None, fanout=int(fan)))
        prev = t if "/" in pin or pin.endswith("(out)") else prev
    m = re.search(r"Startpoint: (\S+)", open(path).read())
    e = re.search(r"Endpoint: (\S+)", open(path).read())
    return dict(start=m.group(1) if m else "", end=e.group(1) if e else "", stages=rows)


def main():
    res, out = sys.argv[1], sys.argv[2]
    data = dict(setup=json.load(open(os.path.join(res, "setup.json"))), corners={}, power_grid={})
    for d in sorted(glob.glob(os.path.join(res, "*_*C_*v*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        proc, temp, volt = re.match(r"(\w\w)_(n?\d+)C_(\d)v(\d+)", name).groups()[0], None, None
        m = re.match(r"(\w\w)_(n?)(\d+)C_(\d)v(\d+)", name)
        proc, temp, volt = m.group(1), (-1 if m.group(2) else 1) * int(m.group(3)), float(f"{m.group(4)}.{m.group(5)}")
        c = dict(process=proc, temp=temp, vdd=volt, rc={})
        for rc in ("min", "nom", "max"):
            mx, mn = ends(f"{d}/{rc}_max_end.rpt"), ends(f"{d}/{rc}_min_end.rpt")
            c["rc"][rc] = dict(max_delay=max(mx.values()), min_delay=min(mn.values()), out_max=mx, out_min=mn,
                               power=power(f"{d}/{rc}_power.rpt"))
        c["path_max"] = stages(f"{d}/nom_max_path.rpt")
        c["load"] = {float(re.search(r"load_([\d.]+)\.rpt", f).group(1)): max(ends(f).values())
                     for f in glob.glob(f"{d}/load_*.rpt")}
        c["slew"] = {float(re.search(r"slew_([\d.]+)\.rpt", f).group(1)): max(ends(f).values())
                     for f in glob.glob(f"{d}/slew_*.rpt")}
        data["corners"][name] = c
        for f in glob.glob(f"{d}/pw_*.rpt"):
            p, a = re.search(r"pw_([\d.]+)_([\d.]+)\.rpt", f).groups()
            data["power_grid"][f"{p}|{a}"] = power(f)
    json.dump(data, open(out, "w"), indent=1, sort_keys=True)
    for n, c in data["corners"].items():
        r = c["rc"]["nom"]
        print(f"{n:14s} max {r['max_delay']:7.3f} min {r['min_delay']:6.3f} P {r['power']['total']*1e3:7.3f} mW "
              f"leak {r['power']['leakage']*1e9:9.2f} nW  stages {len(c['path_max']['stages'])} "
              f"{c['path_max']['start']}->{c['path_max']['end']}")


if __name__ == "__main__":
    main()
