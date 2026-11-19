#!/usr/bin/env python3
"""Comparison figures: proposed posit<32,2> decoder against the LDD posit decoder
(JSCooode/LDD_Posit_Decoder) configured to <32,2>, and the published LDD <32,3>.

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


# 1. layouts at one scale
def fig_layouts(ds, out):
    fig, ax = plt.subplots(figsize=(COL2, 3.6))
    x0, gap = 0.0, 32.0
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
        ax.text(x0 + dw / 2, dh + 13, f"{dw:.1f} $\\times$ {dh:.1f} $\\mu$m", ha="center", va="bottom", fontsize=6.4,
                color=INK2)
        ax.text(x0 + dw / 2, top + 34, d["label"], ha="center", va="bottom", fontsize=8, color=d["col"],
                fontweight="bold")
        tt = corner(d, "tt_025C_5v00")
        lines = [f"Cell area {cell_area(d):,.0f} $\\mu$m$^2$  |  {logic_cells(d):,} logic cells",
                 f"TT delay {tt['max_delay']:.2f} ns  |  {tt['power']['total'] * 1e3:.2f} mW",
                 f"Wirelength {d['m']['route__wirelength'] / 1000:.1f} mm"]
        ax.text(x0 + dw / 2, -12, "\n".join(lines), ha="center", va="top", fontsize=6.2, color=INK, linespacing=1.5)
        x0 += dw + gap
    ax.plot([0, 50], [-78, -78], color=INK, lw=2.2, solid_capstyle="butt")
    ax.text(25, -83, "50 $\\mu$m", ha="center", va="top", fontsize=6.4)
    ax.set_xlim(-8, x0 - gap + 8)
    ax.set_ylim(-95, top + 58)
    ax.set_aspect("equal")
    ax.axis("off")
    save(fig, out, "cmp01_layouts_same_scale")


# 2. delay against supply, one panel per process/temperature
def fig_delay_panels(ds, out):
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 2.35), sharey=True, gridspec_kw=dict(wspace=0.08))
    for ax, (p, t, lab) in zip(axs, SEL):
        grid(ax)
        for d in ds:
            cs = sorted([c for c in d["p"]["corners"].values() if c["process"] == p and c["temp"] == t],
                        key=lambda c: c["vdd"])
            v = [c["vdd"] for c in cs]
            ax.fill_between(v, [c["rc"]["min"]["max_delay"] for c in cs], [c["rc"]["max"]["max_delay"] for c in cs],
                            color=d["col"], alpha=0.15, lw=0)
            ax.plot(v, [c["rc"]["nom"]["max_delay"] for c in cs], color=d["col"], ls=d["ls"], marker=d["marker"],
                    ms=3.8, lw=1.3, mec="white", mew=0.5, label=d["label"], zorder=3)
        base = sorted([c for c in ds[0]["p"]["corners"].values() if c["process"] == p and c["temp"] == t],
                      key=lambda c: c["vdd"])
        oth = sorted([c for c in ds[1]["p"]["corners"].values() if c["process"] == p and c["temp"] == t],
                     key=lambda c: c["vdd"])
        for a, b in zip(base, oth):
            r = 100 * (b["rc"]["nom"]["max_delay"] / a["rc"]["nom"]["max_delay"] - 1)
            ax.text(a["vdd"], a["rc"]["nom"]["max_delay"] * 0.76, f"{r:+.1f}%", ha="center", va="top", fontsize=5.6,
                    color=ds[1]["col"], bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
        ax.axhline(PERIOD_NS, color=INK2, lw=0.6, ls=(0, (4, 2)))
        ax.set_yscale("log")
        ax.set_yticks([5, 10, 20, 50, 100])
        ax.set_yticklabels(["5", "10", "20", "50", "100"])
        ax.set_title(lab, fontsize=7.4, loc="left")
        ax.set_xlabel("$V_{DD}$ (V)")
        vv = [c["vdd"] for c in base]
        ax.set_xlim(min(vv) - 0.45, max(vv) + 0.45)
    axs[0].set_ylabel("Critical-path delay (ns)")
    axs[0].legend(loc="upper right", fontsize=5.9, handlelength=2.0)
    fig.text(0.125, -0.06, f"Labels: delay change of {ds[1]['label']} against {ds[0]['label']}; "
             "bands: min-to-max RC; dashed: 20 ns budget", fontsize=6.2, color=INK2)
    save(fig, out, "cmp02_delay_vs_vdd_panels")


# 3. ratio heat map over all corners
def fig_ratio_heatmap(ds, out):
    a, b = ds[0], ds[1]
    names = ordered_names(a)
    rows = [("Critical-path delay", lambda r: r["max_delay"]),
            ("Dynamic power", lambda r: r["power"]["internal"] + r["power"]["switching"]),
            ("Leakage power", lambda r: r["power"]["leakage"]),
            ("Energy per decode", lambda r: r["power"]["total"]),
            ("Energy-delay product", lambda r: r["power"]["total"] * r["max_delay"]),
            ("Area-delay product", lambda r: r["max_delay"])]
    area_r = cell_area(b) / cell_area(a)
    M = []
    for i, (lab, f) in enumerate(rows):
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
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=5.4,
                    color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r for r, _ in rows], fontsize=6.4)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([clabel(a["p"]["corners"][n]) for n in names], fontsize=5.4)
    for s in ax.spines.values():
        s.set_visible(False)
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
    ax.set_title("Values above 1 favour the proposed decoder (nominal RC; 0.2 activity, 50 MHz)", loc="left",
                 fontsize=6.8, color=INK2)
    save(fig, out, "cmp03_ratio_heatmap_all_corners")


# 4. energy against delay, all corners
def fig_energy_delay(ds, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.75))
    grid(ax)
    names = ordered_names(ds[0])
    for n in names:
        p0 = corner(ds[0], n)
        p1 = corner(ds[1], n)
        ax.annotate("", xy=(p1["max_delay"], p1["power"]["total"] * PERIOD_NS * 1e3),
                    xytext=(p0["max_delay"], p0["power"]["total"] * PERIOD_NS * 1e3),
                    arrowprops=dict(arrowstyle="-|>", color=INK3, lw=0.5, mutation_scale=5, shrinkA=2.5, shrinkB=2.5),
                    zorder=1)
    for d in ds:
        x = [corner(d, n)["max_delay"] for n in names]
        y = [corner(d, n)["power"]["total"] * PERIOD_NS * 1e3 for n in names]
        ax.scatter(x, y, s=20, marker=d["marker"], color=d["col"], edgecolor="white", lw=0.5, zorder=3,
                   label=d["label"], alpha=1 if d["ls"] == "-" else 0.75)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([5, 10, 20, 50, 100])
    ax.set_xticklabels(["5", "10", "20", "50", "100"])
    ax.set_yticks([5, 10, 20, 50, 100, 200])
    ax.set_yticklabels(["5", "10", "20", "50", "100", "200"])
    ax.set_xlabel("Critical-path delay (ns)")
    ax.set_ylabel("Energy per decode (pJ)")
    ax.legend(loc="upper right", fontsize=6.0)
    ax.set_title("15 PVT corners; arrows join the same corner", loc="left", fontsize=6.6, color=INK2)
    save(fig, out, "cmp04_energy_vs_delay")


# 5. normalised metrics at TT 5 V
def fig_normalised(ds, out):
    a = ds[0]

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
    base = vals(a)
    labs = [k for k, _ in base]
    fig, ax = plt.subplots(figsize=(COL1, 3.4))
    grid(ax, "x")
    y = np.arange(len(labs))
    off = {1: -0.17, 2: 0.17}
    for k, d in enumerate(ds[1:], 1):
        r = np.array([v / b for (_, v), (_, b) in zip(vals(d), base)])
        ax.hlines(y + off[k], 1, r, color=d["col"], lw=1.4, alpha=0.8 if d["ls"] == "-" else 0.5)
        ax.scatter(r, y + off[k], s=20, marker=d["marker"], color=d["col"], edgecolor="white", lw=0.5, zorder=3,
                   label=d["label"])
        for yi, ri in zip(y, r):
            ax.text(ri * 1.05 if ri >= 1 else ri / 1.05, yi + off[k], f"{ri:.2f}$\\times$", va="center",
                    ha="left" if ri >= 1 else "right", fontsize=5.3, color=d["col"])
    ax.axvline(1, color=a["col"], lw=1.2)
    ax.text(1.02, -0.68, a["label"] + " = 1", color=a["col"], fontsize=6.0, ha="left", va="center")
    ax.set_xscale("log")
    ax.set_xlim(0.8, 4.4)
    ax.set_xticks([0.8, 1, 1.5, 2, 3, 4])
    ax.set_xticklabels(["0.8", "1", "1.5", "2", "3", "4"])
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=6.3)
    ax.invert_yaxis()
    ax.set_ylim(len(labs) - 0.4, -0.9)
    ax.set_xlabel("Normalised to the proposed decoder (log scale)")
    ax.legend(loc="lower right", fontsize=6.0)
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


# 6. area by cell function
def fig_cell_mix(ds, out):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL2, 1.95), gridspec_kw=dict(width_ratios=[1.6, 1], wspace=0.06),
                                 sharey=True)
    y = np.arange(len(ds))
    left = np.zeros(len(ds))
    lc = np.zeros(len(ds))
    for (fname, _), col in zip(FUNC, FCOL):
        area = np.array([sum(d["sizes"][c][0] * d["sizes"][c][1] for _, c, _, _, _ in d["cells"] if func_of(c) == fname)
                         for d in ds])
        cnt = np.array([sum(1 for _, c, _, _, _ in d["cells"] if func_of(c) == fname) for d in ds])
        a1.barh(y, area, left=left, color=col, height=0.6, edgecolor="white", lw=0.5, label=fname)
        a2.barh(y, cnt, left=lc, color=col, height=0.6, edgecolor="white", lw=0.5)
        for yi in range(len(ds)):
            if area[yi] > 2200:
                a1.text(left[yi] + area[yi] / 2, yi, f"{area[yi] / 1000:.1f}k", ha="center", va="center",
                        fontsize=5.2, color="white" if col not in ("#d4d3cf", "#7fb1ea") else INK)
        left += area
        lc += cnt
    for yi in range(len(ds)):
        a1.text(left[yi] + 300, yi, f"{left[yi]:,.0f} $\\mu$m$^2$", va="center", fontsize=6.0, color=INK)
        a2.text(lc[yi] + 25, yi, f"{lc[yi]:,.0f}", va="center", fontsize=6.0, color=INK)
    a1.set_yticks(y)
    a1.set_yticklabels([d["label"] for d in ds], fontsize=6.6)
    a1.invert_yaxis()
    a1.set_xlabel("Placed cell area by function ($\\mu$m$^2$)")
    a2.set_xlabel("Placed cell count")
    a1.set_xlim(0, left.max() * 1.2)
    a2.set_xlim(0, lc.max() * 1.22)
    grid(a1, "x")
    grid(a2, "x")
    a1.legend(loc="lower center", bbox_to_anchor=(0.8, 1.0), ncol=5, fontsize=5.8, handlelength=1.1,
              columnspacing=0.8)
    save(fig, out, "cmp06_cell_function_mix")


# 7. critical-path anatomy at TT
def fig_critical(ds, out):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL2, 2.5), gridspec_kw=dict(width_ratios=[1.2, 1], wspace=0.34))
    grid(a1)
    shares = []
    for d in ds:
        pm = d["p"]["corners"]["tt_025C_5v00"]["path_max"]
        st = pm["stages"]
        arr = [0] + [s["arrival"] for s in st]
        a1.step(range(len(arr)), arr, where="post", color=d["col"], lw=1.3, ls=d["ls"],
                label=f"{d['label']}: {pm['start']} $\\rightarrow$ {pm['end']}")
        sh = {}
        for i, s in enumerate(st):
            c = category(s["cell"], s["pin"], i == 0, i == len(st) - 1)
            sh[c] = sh.get(c, 0.0) + s["delay"]
            if c == "Delay cell (dlyb)":
                a1.plot([i + 1, i + 1], [arr[i], arr[i + 1]], color=d["col"], lw=4.0, alpha=0.3, solid_capstyle="butt")
        shares.append(sh)
    a1.set_xlabel("Stage on the critical path")
    a1.set_ylabel("Arrival time (ns)")
    a1.xaxis.set_major_locator(plt.MultipleLocator(2))
    a1.legend(loc="upper left", fontsize=5.6)
    a1.set_title(r"TT, 25$\,^{\circ}$C, 5.00 V; shaded: delay-cell stages", loc="left", fontsize=6.6, color=INK2)
    y = np.arange(len(ds))
    left = np.zeros(len(ds))
    for c in CAT_COL:
        v = np.array([sh.get(c, 0.0) for sh in shares])
        a2.barh(y, v, left=left, color=CAT_COL[c], height=0.58, edgecolor="white", lw=0.5, label=c.replace(" (dlyb)", ""))
        for yi in range(len(ds)):
            tot = sum(shares[yi].values())
            if v[yi] / tot > 0.1:
                a2.text(left[yi] + v[yi] / 2, yi, f"{100 * v[yi] / tot:.0f}%", ha="center", va="center", fontsize=5.6,
                        color="white")
        left += v
    a2.set_yticks(y)
    a2.set_yticklabels([d["label"] for d in ds], fontsize=6.2)
    a2.invert_yaxis()
    a2.set_xlabel("Critical-path delay by cell type (ns)")
    a2.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=3, fontsize=5.6, handlelength=1.1,
              columnspacing=0.7)
    grid(a2, "x")
    save(fig, out, "cmp07_critical_path_anatomy")


# 8. per-output arrival distributions
def fig_output_dist(ds, out):
    fig, axs = plt.subplots(1, 2, figsize=(COL2, 2.35), gridspec_kw=dict(wspace=0.18))
    rng = np.random.default_rng(7)
    for ax, (n, lab) in zip(axs, [("tt_025C_5v00", r"TT, 25$\,^{\circ}$C, 5.00 V"),
                                  ("ss_125C_4v50", r"SS, 125$\,^{\circ}$C, 4.50 V")]):
        grid(ax, "y")
        for k, d in enumerate(ds):
            r = corner(d, n)
            v = np.array(list(r["out_max"].values()))
            vm = np.array(list(r["out_min"].values()))
            parts = ax.violinplot([v], positions=[k], widths=0.7, showextrema=False)
            for b in parts["bodies"]:
                b.set_facecolor(d["col"])
                b.set_alpha(0.22)
                b.set_edgecolor(d["col"])
            ax.scatter(k + rng.uniform(-0.16, 0.16, len(v)), v, s=6, color=d["col"], lw=0, alpha=0.9, zorder=3)
            ax.scatter(k + rng.uniform(-0.16, 0.16, len(vm)), vm, s=6, facecolor="white", edgecolor=d["col"], lw=0.5,
                       zorder=3)
            ax.hlines(np.median(v), k - 0.28, k + 0.28, color=INK, lw=0.8, zorder=4)
            ax.text(k, v.max() * 1.03, f"max {v.max():.2f}", ha="center", va="bottom", fontsize=5.6, color=d["col"])
        ax.set_xticks(range(len(ds)))
        ax.set_xticklabels([d["label"] for d in ds], fontsize=6.2)
        ax.set_title(lab, loc="left", fontsize=7)
        ax.set_ylim(0, max(corner(d, n)["max_delay"] for d in ds) * 1.14)
    axs[0].set_ylabel("Output arrival time (ns)")
    h = [Line2D([], [], marker="o", ls="", color=INK2, ms=3, label="Longest path to each output"),
         Line2D([], [], marker="o", ls="", mfc="white", mec=INK2, ms=3, label="Shortest path to each output"),
         Line2D([], [], color=INK, lw=0.8, label="Median of longest paths")]
    fig.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, fontsize=6.0)
    save(fig, out, "cmp08_output_arrival_distribution")


def main():
    cfg = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    setup_style()
    ds = load(cfg)
    for f in (fig_layouts, fig_delay_panels, fig_ratio_heatmap, fig_energy_delay, fig_normalised, fig_cell_mix,
              fig_critical, fig_output_dist):
        f(ds, out)
        print("ok", f.__name__)


if __name__ == "__main__":
    main()
