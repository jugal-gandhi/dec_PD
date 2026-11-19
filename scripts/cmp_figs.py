#!/usr/bin/env python3
"""Comparison figures: proposed posit<32,2> decoder against the LDD posit decoder
(JSCooode/LDD_Posit_Decoder) configured to <32,2>. One plot per figure; the LDD design
comes first (left or top) and this work second (right or bottom).

All three designs went through the same GF180MCU flow, SDC and OpenSTA PVT sweep
(15 Liberty corners x 3 RC corners). Power: input activity 0.2 per cycle, 50 MHz.
Usage: cmp_figs.py <config.json> <out_dir>
config.json: {"cell_sizes": path, "designs": [{"key", "label", "pvt", "metrics", "def",
              "masks", "colour_slot", "marker", "ls"}...]}
"""
import gzip
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib import colors as mcolors               # noqa: E402
from matplotlib.lines import Line2D                    # noqa: E402
import numpy as np                                     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paper_figs3 import COL1, COL2, GRID, INK, INK2, INK3, SLOT, save, setup_style  # noqa: E402
from pvt_figs import CAT_COL, category, grid                                      # noqa: E402
from compose_showcase import CLASSIC_GF180, compose_classic                       # noqa: E402
import paint_cells3 as PC                                                           # noqa: E402

PERIOD_NS = 20.0
SEL = [("ss", 125, r"SS, 125$\,^{\circ}$C"), ("tt", 25, r"TT, 25$\,^{\circ}$C"), ("ff", -40, r"FF, $-$40$\,^{\circ}$C")]


def load(cfg):
    sizes = json.load(open(cfg["cell_sizes"]))
    ds = []
    for d in cfg["designs"]:
        d = dict(d)
        d["p"] = json.load(open(d["pvt"]))
        d["m"] = json.load(open(d["metrics"]))
        d["cells"] = PC.read_def(d["def"])
        d["col"] = SLOT[d["colour_slot"]]
        d["sizes"] = sizes
        ds.append(d)
    return ds


def corner(d, name, rc="nom"):
    return d["p"]["corners"][name]["rc"][rc]


def ordered_names(d):
    order = {"ss": 0, "tt": 1, "ff": 2}
    return [n for n, _ in sorted(d["p"]["corners"].items(),
                                 key=lambda x: (order[x[1]["process"]], x[1]["vdd"], x[1]["temp"]))]


def clabel(c):
    return f"{c['process'].upper()} {c['temp']}$\\,^{{\\circ}}$C\n{c['vdd']:.2f} V".replace("-", "$-$")


def logic_cells(d):
    return sum(1 for _, c, _, _, _ in d["cells"] if PC.cls_of(c) in ("comb", "buf", "clk", "seq", "tie"))


def cell_area(d, keep=("comb", "buf", "clk", "seq", "tie", "tap", "endcap", "ant")):
    return sum(d["sizes"][c][0] * d["sizes"][c][1] for _, c, _, _, _ in d["cells"] if PC.cls_of(c) in keep)



def roles(ds):
    base = next(d for d in ds if d["key"] == "this")
    other = next(d for d in ds if d["key"] != "this")
    return base, other


# 1. layouts at one scale
def fig_layouts(ds, out):
    fig, ax = plt.subplots(figsize=(5.2, 3.5))
    x0, gap = 0.0, 36.0
    top = max(json.load(open(os.path.join(d["masks"], "views.json")))["die_um"][3] for d in ds)
    for d in ds:
        meta = json.load(open(os.path.join(d["masks"], "views.json")))
        v = meta["views"]["die"]
        layers = [l for l in v["layers"] if not l.endswith("_fill")]
        arr = compose_classic(os.path.join(d["masks"], "die"), layers, CLASSIC_GF180)
        bx0, by0, bx1, by1 = v["box_um"]
        dw, dh = meta["die_um"][2], meta["die_um"][3]
        ax.imshow(arr, extent=(x0 + bx0, x0 + bx1, by0, by1), interpolation="lanczos", zorder=1)
        ax.add_patch(plt.Rectangle((x0, 0), dw, dh, fill=False, ec=d["col"], lw=1.4, zorder=3))
        ax.annotate("", xy=(x0, dh + 9), xytext=(x0 + dw, dh + 9),
                    arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.6, shrinkA=0, shrinkB=0))
        ax.text(x0 + dw / 2, dh + 13, f"{dw:.1f} $\\times$ {dh:.1f} $\\mu$m", ha="center", va="bottom", fontsize=6.6,
                color=INK2)
        ax.text(x0 + dw / 2, top + 34, d["label"], ha="center", va="bottom", fontsize=8.5, color=d["col"],
                fontweight="bold")
        tt = corner(d, "tt_025C_5v00")
        lines = [f"Cell area {cell_area(d):,.0f} $\\mu$m$^2$", f"{logic_cells(d):,} logic cells",
                 f"TT delay {tt['max_delay']:.2f} ns, {tt['power']['total'] * 1e3:.2f} mW",
                 f"Wirelength {d['m']['route__wirelength'] / 1000:.1f} mm"]
        ax.text(x0 + dw / 2, -12, "\n".join(lines), ha="center", va="top", fontsize=6.6, color=INK, linespacing=1.45)
        x0 += dw + gap
    ax.plot([0, 50], [-92, -92], color=INK, lw=2.2, solid_capstyle="butt")
    ax.text(25, -97, "50 $\\mu$m", ha="center", va="top", fontsize=6.4)
    ax.set_xlim(-8, x0 - gap + 8)
    ax.set_ylim(-110, top + 60)
    ax.set_aspect("equal")
    ax.axis("off")
    save(fig, out, "cmp01_layouts_same_scale")


# 2. delay against supply, one figure per process/temperature
def fig_delay_vdd(ds, out):
    base, other = roles(ds)
    for k, (p, t, lab) in enumerate(SEL):
        fig, ax = plt.subplots(figsize=(COL1, 2.4))
        grid(ax)
        get = lambda d: sorted([c for c in d["p"]["corners"].values() if c["process"] == p and c["temp"] == t],
                               key=lambda c: c["vdd"])
        for d in ds:
            cs = get(d)
            v = [c["vdd"] for c in cs]
            ax.fill_between(v, [c["rc"]["min"]["max_delay"] for c in cs], [c["rc"]["max"]["max_delay"] for c in cs],
                            color=d["col"], alpha=0.15, lw=0)
            ax.plot(v, [c["rc"]["nom"]["max_delay"] for c in cs], color=d["col"], marker=d["marker"], ms=4.2, lw=1.4,
                    mec="white", mew=0.5, label=d["label"], zorder=3)
        for a, b in zip(get(base), get(other)):
            r = 100 * (1 - a["rc"]["nom"]["max_delay"] / b["rc"]["nom"]["max_delay"])
            ax.text(a["vdd"], a["rc"]["nom"]["max_delay"] * 0.78, f"$-${r:.1f}%", ha="center", va="top", fontsize=6.2,
                    color=base["col"], bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
        ax.axhline(PERIOD_NS, color=INK2, lw=0.6, ls=(0, (4, 2)))
        ax.set_yscale("log")
        ax.set_yticks([4, 5, 10, 20, 50, 100])
        ax.set_yticklabels(["", "5", "10", "20", "50", "100"])
        vv = [c["vdd"] for c in get(base)]
        ax.set_xlim(min(vv) - 0.45, max(vv) + 0.45)
        ax.set_ylim(3.8, 130)
        ax.set_xlabel("Supply voltage, $V_{DD}$ (V)")
        ax.set_ylabel("Critical-path delay (ns)")
        ax.legend(loc="upper right", fontsize=6.4)
        ax.set_title(f"{lab}; labels: delay reduction of this work", loc="left", fontsize=6.8, color=INK2)
        save(fig, out, f"cmp02{'abc'[k]}_delay_vs_vdd_{p}_{str(t).replace('-', 'm')}C")


# 3. ratio heat map over all corners
def fig_ratio_heatmap(ds, out):
    a, b = roles(ds)
    names = ordered_names(a)
    rows = [("Critical-path delay", lambda r: r["max_delay"]),
            ("Dynamic power", lambda r: r["power"]["internal"] + r["power"]["switching"]),
            ("Leakage power", lambda r: r["power"]["leakage"]),
            ("Energy per decode", lambda r: r["power"]["total"]),
            ("Energy-delay product", lambda r: r["power"]["total"] * r["max_delay"]),
            ("Area-delay product", lambda r: r["max_delay"])]
    area_r = cell_area(b) / cell_area(a)
    M = []
    for lab, f in rows:
        row = [f(corner(b, n)) / f(corner(a, n)) for n in names]
        if lab == "Area-delay product":
            row = [x * area_r for x in row]
        M.append(row)
    M = np.array(M)
    fig, ax = plt.subplots(figsize=(COL2, 2.5))
    cmap = mcolors.LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f4f3ef", "#eb6834"])
    norm = mcolors.TwoSlopeNorm(vmin=0.9, vcenter=1.0, vmax=2.5)
    im = ax.imshow(M, aspect="auto", cmap=cmap, norm=norm)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=5.4, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r for r, _ in rows], fontsize=6.4)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([clabel(a["p"]["corners"][n]) for n in names], fontsize=5.4)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(names)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(rows)), minor=True)
    ax.grid(which="minor", color="white", lw=0.8)
    ax.tick_params(which="minor", length=0)
    for x in (5.5, 8.5):
        ax.axvline(x, color="white", lw=2.4)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.012, ticks=[0.9, 1, 1.5, 2, 2.5])
    cb.set_label(f"{b['label']} / {a['label']}", fontsize=6.6)
    cb.ax.tick_params(labelsize=5.8)
    cb.outline.set_visible(False)
    ax.set_title("Values above 1 favour this work (nominal RC; 0.2 activity, 50 MHz)", loc="left", fontsize=6.8,
                 color=INK2)
    save(fig, out, "cmp03_ratio_heatmap_all_corners")


# 4. energy against delay, all corners
def fig_energy_delay(ds, out):
    base, other = roles(ds)
    fig, ax = plt.subplots(figsize=(COL1, 2.75))
    grid(ax)
    names = ordered_names(base)
    for n in names:
        p0, p1 = corner(other, n), corner(base, n)
        ax.annotate("", xy=(p1["max_delay"], p1["power"]["total"] * PERIOD_NS * 1e3),
                    xytext=(p0["max_delay"], p0["power"]["total"] * PERIOD_NS * 1e3),
                    arrowprops=dict(arrowstyle="-|>", color=INK3, lw=0.5, mutation_scale=5, shrinkA=2.5, shrinkB=2.5),
                    zorder=1)
    for d in ds:
        ax.scatter([corner(d, n)["max_delay"] for n in names],
                   [corner(d, n)["power"]["total"] * PERIOD_NS * 1e3 for n in names], s=22, marker=d["marker"],
                   color=d["col"], edgecolor="white", lw=0.5, zorder=3, label=d["label"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([5, 10, 20, 50, 100])
    ax.set_xticklabels(["5", "10", "20", "50", "100"])
    ax.set_yticks([5, 10, 20, 50, 100, 200])
    ax.set_yticklabels(["5", "10", "20", "50", "100", "200"])
    ax.set_xlabel("Critical-path delay (ns)")
    ax.set_ylabel("Energy per decode (pJ)")
    ax.legend(loc="upper right", fontsize=6.2)
    ax.set_title("15 PVT corners; arrows: LDD to this work, same corner", loc="left", fontsize=6.6, color=INK2)
    save(fig, out, "cmp04_energy_vs_delay")


# 5. normalised metrics at TT 5 V
def fig_normalised(ds, out):
    base, other = roles(ds)

    def vals(d):
        tt, ss = corner(d, "tt_025C_5v00"), corner(d, "ss_125C_4v50")
        return [("Standard-cell area", cell_area(d)), ("Logic cells", logic_cells(d)),
                ("Core area", d["m"]["design__core__area"]), ("Routed wirelength", d["m"]["route__wirelength"]),
                ("Vias", d["m"]["route__vias"]), ("Critical-path delay, TT", tt["max_delay"]),
                ("Critical-path delay, SS", ss["max_delay"]),
                ("Dynamic power, TT", tt["power"]["internal"] + tt["power"]["switching"]),
                ("Leakage power, TT", tt["power"]["leakage"]), ("Energy per decode, TT", tt["power"]["total"]),
                ("Energy-delay product, TT", tt["power"]["total"] * tt["max_delay"]),
                ("Area-delay product, TT", cell_area(d) * tt["max_delay"])]
    bv = vals(base)
    labs = [k for k, _ in bv]
    r = np.array([v / b for (_, v), (_, b) in zip(vals(other), bv)])
    fig, ax = plt.subplots(figsize=(COL1, 3.1))
    grid(ax, "x")
    y = np.arange(len(labs))
    ax.hlines(y, 1, r, color=other["col"], lw=1.6)
    ax.scatter(r, y, s=24, marker=other["marker"], color=other["col"], edgecolor="white", lw=0.5, zorder=3,
               label=other["label"])
    for yi, ri in zip(y, r):
        ax.text(ri * 1.04, yi, f"{ri:.2f}$\\times$", va="center", ha="left", fontsize=5.8, color=other["col"])
    ax.axvline(1, color=base["col"], lw=1.4, label=base["label"] + " = 1")
    ax.set_xscale("log")
    ax.set_xlim(0.9, 3.6)
    ax.set_xticks([1, 1.5, 2, 3])
    ax.set_xticklabels(["1", "1.5", "2", "3"])
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=6.3)
    ax.invert_yaxis()
    ax.set_xlabel("Normalised to this work (log scale)")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.47), fontsize=6.0)
    save(fig, out, "cmp05_normalised_metrics")


FUNC = [("NAND / NOR", ("nand", "nor")), ("AND / OR", ("and", "or")), ("AOI / OAI", ("aoi", "oai")),
        ("XOR / XNOR", ("xor", "xnor")), ("Multiplexer", ("mux",)), ("Inverter", ("inv", "clkinv")),
        ("Buffer", ("buf", "clkbuf")), ("Delay cell", ("dly",)), ("Tap / endcap / tie", ("filltie", "endcap", "tie"))]
FCOL = [SLOT[0], "#7fb1ea", SLOT[6], SLOT[4], SLOT[2], "#9b9a95", SLOT[3], SLOT[7], "#d4d3cf"]


def func_of(cell):
    b = re.sub(r"_\d+$", "", cell.split("__")[-1])
    if b.startswith("fill") and b != "filltie":
        return None
    if b in ("filltie", "endcap", "tiel", "tieh", "antenna"):
        return "Tap / endcap / tie"
    if b.startswith(("nand", "nor")):
        return "NAND / NOR"
    if b.startswith(("xor", "xnor")):
        return "XOR / XNOR"
    if b.startswith(("aoi", "oai")):
        return "AOI / OAI"
    if b.startswith("mux"):
        return "Multiplexer"
    if b in ("inv", "clkinv"):
        return "Inverter"
    if b in ("buf", "clkbuf"):
        return "Buffer"
    if b.startswith("dly"):
        return "Delay cell"
    if b.startswith(("and", "or")):
        return "AND / OR"
    raise ValueError(f"unclassified cell {cell}")



def func_totals(d):
    area, cnt = {}, {}
    for _, c, _, _, _ in d["cells"]:
        f = func_of(c)
        if f:
            area[f] = area.get(f, 0.0) + d["sizes"][c][0] * d["sizes"][c][1]
            cnt[f] = cnt.get(f, 0) + 1
    return area, cnt


# 6. area and count by cell function (two figures)
def fig_cell_mix(ds, out):
    tot = [func_totals(d) for d in ds]
    for which, xl, name, unit, thr in ((0, "Placed cell area by function ($\\mu$m$^2$)", "cmp06a_cell_area_by_function",
                                        " $\\mu$m$^2$", 2200),
                                       (1, "Placed cell count by function", "cmp06b_cell_count_by_function", "", 90)):
        fig, ax = plt.subplots(figsize=(COL1, 1.9))
        y = np.arange(len(ds))
        left = np.zeros(len(ds))
        for (fname, _), col in zip(FUNC, FCOL):
            v = np.array([t[which].get(fname, 0) for t in tot], dtype=float)
            ax.barh(y, v, left=left, color=col, height=0.6, edgecolor="white", lw=0.5, label=fname)
            for yi in range(len(ds)):
                if v[yi] > thr:
                    txt = f"{v[yi] / 1000:.1f}k" if which == 0 else f"{v[yi]:.0f}"
                    ax.text(left[yi] + v[yi] / 2, yi, txt, ha="center", va="center", fontsize=5.0,
                            color=INK if col in ("#d4d3cf", "#7fb1ea") else "white")
            left += v
        for yi in range(len(ds)):
            ax.text(left[yi] + left.max() * 0.015, yi, f"{left[yi]:,.0f}{unit}", va="center", fontsize=6.0, color=INK)
        ax.set_yticks(y)
        ax.set_yticklabels([d["label"] for d in ds], fontsize=6.6)
        ax.invert_yaxis()
        ax.set_xlabel(xl)
        ax.set_xlim(0, left.max() * 1.25)
        grid(ax, "x")
        ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, fontsize=5.6, handlelength=1.0,
                  columnspacing=0.7)
        save(fig, out, name)


# 7. critical-path anatomy at TT (two figures)
def fig_critical(ds, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.5))
    grid(ax)
    shares = []
    for d in ds:
        pm = d["p"]["corners"]["tt_025C_5v00"]["path_max"]
        st = pm["stages"]
        arr = [0] + [s["arrival"] for s in st]
        ax.step(range(len(arr)), arr, where="post", color=d["col"], lw=1.4,
                label=f"{d['label']}: {pm['start']} $\\rightarrow$ {pm['end']}")
        sh = {}
        for i, s in enumerate(st):
            c = category(s["cell"], s["pin"], i == 0, i == len(st) - 1)
            sh[c] = sh.get(c, 0.0) + s["delay"]
            if c == "Delay cell (dlyb)":
                ax.plot([i + 1, i + 1], [arr[i], arr[i + 1]], color=d["col"], lw=4.0, alpha=0.3, solid_capstyle="butt")
        shares.append(sh)
    ax.set_xlabel("Stage on the critical path")
    ax.set_ylabel("Arrival time (ns)")
    ax.xaxis.set_major_locator(plt.MultipleLocator(2))
    ax.legend(loc="upper left", fontsize=5.8)
    ax.set_title(r"TT, 25$\,^{\circ}$C, 5.00 V; shaded: delay-cell stages", loc="left", fontsize=6.6, color=INK2)
    save(fig, out, "cmp07a_critical_path_arrival")

    fig, ax = plt.subplots(figsize=(COL1, 1.8))
    y = np.arange(len(ds))
    left = np.zeros(len(ds))
    for c in CAT_COL:
        v = np.array([sh.get(c, 0.0) for sh in shares])
        ax.barh(y, v, left=left, color=CAT_COL[c], height=0.58, edgecolor="white", lw=0.5,
                label=c.replace(" (dlyb)", ""))
        for yi in range(len(ds)):
            t = sum(shares[yi].values())
            if v[yi] / t > 0.1:
                ax.text(left[yi] + v[yi] / 2, yi, f"{100 * v[yi] / t:.0f}%", ha="center", va="center", fontsize=5.8,
                        color="white")
        left += v
    for yi in range(len(ds)):
        ax.text(left[yi] + 0.15, yi, f"{left[yi]:.2f} ns", va="center", fontsize=6.0, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([d["label"] for d in ds], fontsize=6.6)
    ax.invert_yaxis()
    ax.set_xlim(0, left.max() * 1.18)
    ax.set_xlabel(r"Critical-path delay by cell type (ns), TT, 25$\,^{\circ}$C, 5.00 V")
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, fontsize=5.6, handlelength=1.0,
              columnspacing=0.7)
    grid(ax, "x")
    save(fig, out, "cmp07b_critical_path_by_cell_type")


# 8. per-output arrival distributions (one figure per corner)
def fig_output_dist(ds, out):
    rng = np.random.default_rng(7)
    for k, (n, lab) in enumerate([("tt_025C_5v00", r"TT, 25$\,^{\circ}$C, 5.00 V"),
                                  ("ss_125C_4v50", r"SS, 125$\,^{\circ}$C, 4.50 V")]):
        fig, ax = plt.subplots(figsize=(COL1, 2.6))
        grid(ax, "y")
        for i, d in enumerate(ds):
            r = corner(d, n)
            v = np.array(list(r["out_max"].values()))
            vm = np.array(list(r["out_min"].values()))
            parts = ax.violinplot([v], positions=[i], widths=0.7, showextrema=False)
            for b in parts["bodies"]:
                b.set_facecolor(d["col"])
                b.set_alpha(0.22)
                b.set_edgecolor(d["col"])
            ax.scatter(i + rng.uniform(-0.16, 0.16, len(v)), v, s=7, color=d["col"], lw=0, alpha=0.9, zorder=3)
            ax.scatter(i + rng.uniform(-0.16, 0.16, len(vm)), vm, s=7, facecolor="white", edgecolor=d["col"], lw=0.5,
                       zorder=3)
            ax.hlines(np.median(v), i - 0.28, i + 0.28, color=INK, lw=0.8, zorder=4)
            ax.text(i, v.max() * 1.03, f"max {v.max():.2f} ns", ha="center", va="bottom", fontsize=6.0, color=d["col"])
        ax.set_xticks(range(len(ds)))
        ax.set_xticklabels([d["label"] for d in ds], fontsize=6.8)
        ax.set_xlim(-0.6, len(ds) - 0.4)
        ax.set_ylim(0, max(corner(d, n)["max_delay"] for d in ds) * 1.14)
        ax.set_ylabel("Output arrival time (ns)")
        ax.set_title(lab, loc="left", fontsize=7)
        h = [Line2D([], [], marker="o", ls="", color=INK2, ms=3, label="Longest path"),
             Line2D([], [], marker="o", ls="", mfc="white", mec=INK2, ms=3, label="Shortest path"),
             Line2D([], [], color=INK, lw=0.8, label="Median, longest")]
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=6.0)
        save(fig, out, f"cmp08{'ab'[k]}_output_arrival_{n.split('_')[0]}")


def main():
    cfg = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    setup_style()
    ds = load(cfg)
    for f in (fig_layouts, fig_delay_vdd, fig_ratio_heatmap, fig_energy_delay, fig_normalised, fig_cell_mix,
              fig_critical, fig_output_dist):
        f(ds, out)
        print("ok", f.__name__)


if __name__ == "__main__":
    main()
