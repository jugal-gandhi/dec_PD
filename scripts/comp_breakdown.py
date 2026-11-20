#!/usr/bin/env python3
"""Component-wise area, critical-path delay and power of the signed-off posit decoder.

Inputs: the cell attribution from comp_attrib.py, the signed-off DEF, cell sizes,
the OpenSTA critical-path reports (pvt sweep) and per-instance power reports.
Rules for the final categories:
  - buffers and delay cells (buf, clkbuf, dly*) are timing-repair buffers, except the
    input/output buffers, which form their own category;
  - cells that feed both regime detection and the shifter are window-reduction gates
    (AND/OR/AOI/OAI types), counted in the AND-OR network, while multiplexers among
    them belong to the in-line shifter;
  - tap and endcap cells are physical cells.
Usage: comp_breakdown.py <attrib.json> <def.gz> <cell_sizes.json> <pvt_dir> <power_dir> <out.json>
"""
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pvt_parse import stages                      # noqa: E402

CATS = ["AND-OR network", "Boundary comparator", "In-line shifter", "Output encoding",
        "Timing-repair buffers", "I/O buffers"]
BUFS = ("buf", "clkbuf", "dlya", "dlyb", "dlyc", "dlyd")
CORNERS = ["ss_125C_4v50", "tt_025C_5v00", "ff_n40C_5v50"]


def category(info):
    base = re.sub(r"_\d+$", "", info["cell"])
    fam = info["comp"].split("|")[0]
    if fam == "I/O buffers":
        return "I/O buffers"
    if base in BUFS or fam == "Timing-repair buffers":
        return "Timing-repair buffers"
    if fam == "Shared":
        return "In-line shifter" if base.startswith("mux") else "AND-OR network"
    return fam


def def_cells(path):
    rows = []
    for ln in gzip.open(path, "rt"):
        m = re.match(r"\s*-\s+(\S+)\s+(gf180\S+)\s", ln)
        if m:
            rows.append((m.group(1).replace("\\", ""), m.group(2)))
    return rows


def power_rows(path):
    out = {}
    for ln in open(path):
        p = ln.split()
        if len(p) == 5:
            try:
                out[p[4].replace("\\", "")] = [float(v) for v in p[:4]]
            except ValueError:
                pass
    return out


def main():
    attrib_p, def_p, sizes_p, pvt_dir, pw_dir, out = sys.argv[1:7]
    att = json.load(open(attrib_p))["attrib"]
    sizes = json.load(open(sizes_p))
    cat_of = {n: category(v) for n, v in att.items()}
    # second view: buffers belong to the component that drives the net they repair;
    # buffers on primary-input nets stay with the I/O buffers
    own_of = {}
    for n, v in att.items():
        c = cat_of[n]
        if c in ("Timing-repair buffers", "I/O buffers") and "owner" in v:
            o = v["owner"]
            oc = "I/O buffers" if o.startswith("port:") else cat_of.get(o, "I/O buffers")
            own_of[n] = oc if oc not in ("Timing-repair buffers",) else "I/O buffers"
        else:
            own_of[n] = c
    res = dict(categories=CATS, area={c: 0.0 for c in CATS + ["Physical cells"]},
               cells={c: 0 for c in CATS + ["Physical cells"]}, delay={}, power={}, stage_area={})
    for name, cell in def_cells(def_p):
        base = re.sub(r"_\d+$", "", cell.split("__")[-1])
        if base.startswith("fill") and base != "filltie":
            continue
        a = sizes[cell][0] * sizes[cell][1]
        c = cat_of.get(name, "Physical cells" if base in ("filltie", "endcap") else None)
        if c is None:
            raise SystemExit(f"unattributed cell {name} {cell}")
        res["area"][c] += a
        res["cells"][c] += 1
        oc = own_of.get(name, c)
        res.setdefault("area_folded", {}).setdefault(oc, 0.0)
        res["area_folded"][oc] += a
        stg = att.get(name, {}).get("comp", "|").split("|")[1]
        if c in ("AND-OR network", "Boundary comparator", "In-line shifter") and stg not in ("", "*", "-"):
            res["stage_area"].setdefault(c, {}).setdefault(stg, 0.0)
            res["stage_area"][c][stg] += a
    for corner in CORNERS:
        pm = stages(os.path.join(pvt_dir, corner, "nom_max_path.rpt"))
        d = {c: 0.0 for c in CATS}
        df = {}
        seq = []
        for s in pm["stages"]:
            inst = s["pin"].rsplit("/", 1)[0].replace("\\", "")
            c = cat_of.get(inst)
            if c is None:
                raise SystemExit(f"path instance {inst} not attributed")
            d[c] += s["delay"]
            oc = own_of.get(inst, c)
            df[oc] = df.get(oc, 0.0) + s["delay"]
            seq.append((c, s["delay"], s["cell"].split("__")[-1], oc))
        res["delay"][corner] = dict(total=sum(d.values()), by_cat=d, by_owner=df, start=pm["start"], end=pm["end"],
                                    seq=seq)
        pf = os.path.join(pw_dir, corner, "power_instances.rpt")
        if os.path.exists(pf):
            rows = power_rows(pf)
            pw = {c: [0.0] * 4 for c in CATS + ["Physical cells"]}
            pwf = {}
            for name, v in rows.items():
                c = cat_of.get(name)
                if c is None:
                    c = "Physical cells"
                pw[c] = [x + y for x, y in zip(pw[c], v)]
                oc = own_of.get(name, c)
                pwf[oc] = [x + y for x, y in zip(pwf.get(oc, [0.0] * 4), v)]
            res["power"][corner] = pw
            res.setdefault("power_folded", {})[corner] = pwf
    json.dump(res, open(out, "w"), indent=1)
    tot_a = sum(res["area"].values())
    print(f"{'Component':24s} {'cells':>5s} {'area um2':>9s} {'area%':>6s}  " +
          "  ".join(f"{c[:2].upper()} dly(ns) %" for c in CORNERS) + ("   TT power mW %" if res["power"] else ""))
    for c in CATS + ["Physical cells"]:
        line = f"{c:24s} {res['cells'][c]:5d} {res['area'][c]:9.1f} {100 * res['area'][c] / tot_a:5.1f}%  "
        for corner in CORNERS:
            dd = res["delay"][corner]
            v = dd["by_cat"].get(c, 0.0)
            line += f"  {v:6.2f} {100 * v / dd['total']:4.0f}%  "
        if "tt_025C_5v00" in res["power"]:
            p = res["power"]["tt_025C_5v00"]
            tp = sum(v[3] for v in p.values())
            line += f"  {p[c][3] * 1e3:6.3f} {100 * p[c][3] / tp:4.1f}%"
        print(line)
    print("totals: area", round(tot_a, 1), "| delay", {k: round(v["total"], 3) for k, v in res["delay"].items()})
    print("\nBuffers folded into the component that drives the repaired net:")
    tp = sum(v[3] for v in res["power_folded"]["tt_025C_5v00"].values()) if res.get("power_folded") else 1
    for c in CATS + ["Physical cells"]:
        if c == "Timing-repair buffers":
            continue
        a_ = res["area_folded"].get(c, 0.0)
        line = f"{c:24s} area {a_:8.1f} ({100 * a_ / tot_a:4.1f}%)"
        for corner in CORNERS:
            v = res["delay"][corner]["by_owner"].get(c, 0.0)
            line += f"  {corner[:2].upper()} {v:5.2f} ns ({100 * v / res['delay'][corner]['total']:3.0f}%)"
        if res.get("power_folded"):
            v = res["power_folded"]["tt_025C_5v00"].get(c, [0] * 4)[3]
            line += f"  TT {v * 1e3:5.3f} mW ({100 * v / tp:4.1f}%)"
        print(line)


if __name__ == "__main__":
    main()
