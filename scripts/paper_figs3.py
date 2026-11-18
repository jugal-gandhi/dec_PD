#!/usr/bin/env python3
"""Publication figures for the v3 SoC (IEEE single/double-column widths).

Every figure is written as a vector PDF (fonts embedded, pdfLaTeX-ready) and
a 600 dpi PNG. Inputs are the published flow results:
  --res      results-soc3 snapshot (blockmap.json, metrics.json, macros/*)
  --run      final LibreLane run directory (STA, wirelength reports)
  --v1/--v2  metrics.json of the earlier chips, --v2macro its posit macro
Usage: paper_figs3.py --res R --run RUN --v1 v1.json --v2 v2.json --v2macro m.json --out DIR
"""
import argparse
import collections
import glob
import json
import math
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib import patches, colors as mcolors     # noqa: E402
from matplotlib.ticker import FuncFormatter            # noqa: E402
import numpy as np                                     # noqa: E402

# ---------------------------------------------------------------- style
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8c8b86"
GRID, SURF = "#e4e3df", "#ffffff"
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
       "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SEQ_CMAP = mcolors.LinearSegmentedColormap.from_list("seqblue", SEQ)
COL1, COL2 = 3.5, 7.16                                # IEEE column widths (in)

MACROS = [  # key, label, colour (fixed slot per block, used in every figure)
    ("cpu_core", "CPU core", SLOT[0]),
    ("dsp_mac", "DSP MAC", SLOT[1]),
    ("simd_alu", "SIMD ALU", SLOT[2]),
    ("spimemio", "SPI flash ctrl.", SLOT[3]),
    ("simpleuart", "UART", SLOT[4]),
    ("posit_decoder_32_2", "Posit decoder (this work)", SLOT[5]),
]
MLABEL = {k: l for k, l, _ in MACROS}
MCOL = {k: c for k, _, c in MACROS}
SRAM_COL = SLOT[6]
INSTANCES = {"cpu_core": 1, "dsp_mac": 4, "simd_alu": 1, "spimemio": 1, "simpleuart": 1, "posit_decoder_32_2": 1}
CORNERS = [f"{rc}_{pv}" for pv in ("ss_125C_4v50", "tt_025C_5v00", "ff_n40C_5v50") for rc in ("min", "nom", "max")]


def corner_label(c):
    rc, p, t, v = c.split("_")
    return f"{p.upper()}\n{rc}"


def setup_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "custom", "mathtext.rm": "Liberation Serif",
        "mathtext.it": "Liberation Serif:italic", "mathtext.bf": "Liberation Serif:bold",
        "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7,
        "ytick.labelsize": 7, "legend.fontsize": 7, "axes.edgecolor": INK3, "axes.linewidth": 0.6,
        "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
        "xtick.major.width": 0.5, "ytick.major.width": 0.5, "xtick.major.size": 2.5,
        "ytick.major.size": 2.5, "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.5,
        "legend.frameon": False, "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 600,
        "figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
    })


def save(fig, out, name):
    fig.savefig(os.path.join(out, name + ".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(os.path.join(out, name + ".png"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote", name)


def text_on(rgb_hex):
    r, g, b = mcolors.to_rgb(rgb_hex)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return INK if lum > 0.55 else "#ffffff"


# ---------------------------------------------------------------- data
def load(args):
    D = {}
    D["chip"] = json.load(open(os.path.join(args.res, "metrics.json")))
    D["macro"] = {k: json.load(open(os.path.join(args.res, "macros", k, "metrics.json"))) for k, _, _ in MACROS}
    D["bm"] = json.load(open(os.path.join(args.res, "blockmap.json")))
    D["v1"] = json.load(open(args.v1))
    D["v2"] = json.load(open(args.v2))
    D["v2macro"] = json.load(open(args.v2macro))
    D["run"] = args.run
    return D


# ---------------------------------------------------------------- fig 1: area treemap
def squarify(values, x, y, w, h):
    """Squarified treemap (Bruls et al.): returns rectangles in input order."""
    vals = list(values)
    total = sum(vals)
    vals = [v * w * h / total for v in vals]
    rects = []

    def worst(row, side):
        s = sum(row)
        return max(max(side * side * r / (s * s), (s * s) / (side * side * r)) for r in row)

    def layout(row, x, y, w, h):
        s = sum(row)
        out = []
        if w >= h:
            cw = s / h
            yy = y
            for r in row:
                out.append((x, yy, cw, r / cw))
                yy += r / cw
            return out, (x + cw, y, w - cw, h)
        ch = s / w
        xx = x
        for r in row:
            out.append((xx, y, r / ch, ch))
            xx += r / ch
        return out, (x, y + ch, w, h - ch)

    i, row = 0, []
    while i < len(vals):
        side = min(w, h)
        if not row or worst(row + [vals[i]], side) <= worst(row, side):
            row.append(vals[i])
            i += 1
        else:
            out, (x, y, w, h) = layout(row, x, y, w, h)
            rects += out
            row = []
    if row:
        out, _ = layout(row, x, y, w, h)
        rects += out
    return rects


def fig_area(D, out):
    die = D["chip"]["design__die__area"] / 1e6           # mm^2
    core = D["chip"]["design__core__area"] / 1e6
    items = []
    for k, label, col in MACROS:
        m = D["macro"][k]
        a = m["design__die__area"] / 1e6 * INSTANCES[k]
        name = label if INSTANCES[k] == 1 else f"{label} ×{INSTANCES[k]}"
        items.append((name, a, col))
    sram = 8 * 431.86 * 484.88 / 1e6
    items.append(("SRAM 8×512×8", sram, SRAM_COL))
    used = sum(a for _, a, _ in items)
    items.append(("Routing channels and top-level glue", core - used, "#d6d5d0"))
    items.sort(key=lambda t: -t[1])
    fig, ax = plt.subplots(figsize=(COL2, 3.0))
    rects = squarify([a for _, a, _ in items], 0, 0, 1.6, 1.0)
    die_core = die
    small = []
    for (name, a, col), (x, y, w, h) in zip(items, rects):
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=col, edgecolor=SURF, linewidth=1.5))
        tc = text_on(col)
        pct = 100 * a / core
        if w < 0.2 or h < 0.12:
            small.append((name, a, pct, x, y, w, h))
            continue
        ax.text(x + 0.012, y + 0.018, f"{name}\n{a:.3f} mm²  ·  {pct:.1f}%", ha="left", va="top",
                fontsize=7.5 if w * h > 0.06 else 6.2, color=tc, linespacing=1.15)
    # small tiles: short label inside; the posit decoder gets a straight callout
    short = {"SIMD ALU": "SIMD", "SPI flash ctrl.": "SPI", "UART": "UART"}
    for name, a, pct, x, y, w, h in small:
        if "this work" in name:
            ax.annotate(f"{name}\n{a:.3f} mm²  ·  {pct:.1f}% of core", xy=(x + w, y + h / 2),
                        xytext=(x + w + 0.05, y + h / 2), fontsize=6.8, fontweight="bold", color=INK,
                        va="center", ha="left",
                        arrowprops=dict(arrowstyle="-", color=INK, lw=0.7, shrinkA=0, shrinkB=0))
        else:
            col = [c for n_, _, c in items if n_ == name][0]
            ax.text(x + 0.008, y + 0.015, f"{short.get(name, name)}\n{a:.3f}\n{pct:.1f}%", ha="left",
                    va="top", fontsize=5.6, color=text_on(col), linespacing=1.1)
    ax.set_xlim(0, 2.1)
    ax.set_ylim(0, 1.0)
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_title(f"Core area composition in mm² ({core:.2f} mm² core inside a {die:.2f} mm² die)",
                 loc="left", pad=4)
    save(fig, out, "fig01_area_treemap")


# ---------------------------------------------------------------- fig 2: sub-block cells
def fig_subblocks(D, out):
    counts = collections.defaultdict(int)
    for g, lab, n in D["bm"]["counts"]:
        if g in INSTANCES and lab != "Clock tree":
            counts[(g, lab)] += n / INSTANCES[g]
    rows = []
    for k, label, col in MACROS:
        sub = sorted([(lab, n) for (g, lab), n in counts.items() if g == k], key=lambda t: -t[1])
        rows.append((k, label, col, sub))
    nbars = sum(len(r[3]) for r in rows)
    fig, ax = plt.subplots(figsize=(COL1, 0.13 * nbars + 0.9))
    y = 0
    yt, yl = [], []
    for k, label, col, sub in rows:
        ax.text(-0.02, y - 0.1, label, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=7.5, fontweight="bold", color=INK)
        y += 0.9
        for lab, n in sub:
            ax.barh(y, n, height=0.72, color=col, edgecolor=SURF, linewidth=0.4)
            ax.text(n * 1.08, y, f"{n:,.0f}", va="center", ha="left", fontsize=6, color=INK2)
            yt.append(y)
            yl.append(lab)
            y += 1
        y += 0.6
    ax.set_yticks(yt)
    ax.set_yticklabels(yl, fontsize=6.3)
    ax.set_ylim(y - 0.4, -0.8)
    ax.set_xscale("log")
    ax.set_xlim(3, 2e4)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Standard cells per block instance (log scale)")
    ax.xaxis.grid(True, which="major")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.spines["left"].set_visible(False)
    ax.set_title("Functional sub-blocks inside each hard macro", loc="left")
    save(fig, out, "fig02_subblock_cells")


# ---------------------------------------------------------------- fig 3: timing heatmap
def corner_ws(m, kind):
    return [m.get(f"timing__{kind}__ws__corner:{c}") for c in CORNERS]


def fig_timing(D, out):
    rows = [("Chip top level\n(16.7 MHz)", D["chip"])] + \
           [(MLABEL[k].replace(" (this work)", "\n(this work)") +
             ("\n(comb., 20 ns)" if k == "posit_decoder_32_2" else "\n(25 MHz)"), D["macro"][k]) for k, _, _ in MACROS]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.9), gridspec_kw={"wspace": 0.08})
    for ax, kind, title in zip(axes, ("setup", "hold"), ("Setup worst slack (ns)", "Hold worst slack (ns)")):
        M = np.array([[v if v is not None else np.nan for v in corner_ws(m, kind)] for _, m in rows])
        vmax = np.nanmax(M)
        im = ax.imshow(M, cmap=SEQ_CMAP, vmin=0, vmax=vmax, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                c = SEQ_CMAP(v / vmax)
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=5.8,
                        color=text_on(mcolors.to_hex(c)))
        for xx in (2.5, 5.5):
            ax.axvline(xx, color=SURF, linewidth=2)
        ax.set_xticks(range(len(CORNERS)))
        ax.set_xticklabels([corner_label(c) for c in CORNERS], fontsize=6)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r for r, _ in rows] if kind == "setup" else [], fontsize=6.3)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(title, loc="left")
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=6, length=2)
    fig.text(0.5, -0.04, "Process corner (SS 125 °C 4.5 V · TT 25 °C 5.0 V · FF −40 °C 5.5 V) and RC extraction corner",
             ha="center", fontsize=7, color=INK2)
    save(fig, out, "fig03_timing_heatmap")


# ---------------------------------------------------------------- fig 4: path slack distribution
def path_slacks(rpt):
    txt = open(rpt).read()
    out = []
    for blk in txt.split("Startpoint: ")[1:]:
        sp = blk.split()[0]
        ep = re.search(r"Endpoint: (\S+)", blk).group(1)
        sl = re.search(r"(-?[\d.]+)\s+slack \((MET|VIOLATED)\)", blk)
        if sl:
            out.append((sp, ep, float(sl.group(1))))
    return out


def endpoint_class(ep):
    for key, lab in (("u_cpu", "CPU core"), ("u_ram", "SRAM"), ("u_scratch", "SRAM"), ("u_spi", "SPI / UART"),
                     ("u_uart", "SPI / UART"), ("u_dsp", "DSP / SIMD"), ("u_simd", "DSP / SIMD"),
                     ("u_posit", "Posit decoder"), ("PAD", "I/O pad")):
        if key in ep:
            return lab
    return "Top-level registers"


def fig_slack_dist(D, out):
    sta = sorted(glob.glob(os.path.join(D["run"], "*-openroad-stapostpnr")))[-1]
    series = [("nom_ss_125C_4v50", "SS, 125 °C, 4.5 V", SLOT[1]),
              ("nom_tt_025C_5v00", "TT, 25 °C, 5.0 V", SLOT[0]),
              ("nom_ff_n40C_5v50", "FF, −40 °C, 5.5 V", SLOT[2])]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.2), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.3})
    ax = axes[0]
    bins = np.linspace(0, 60, 61)
    for c, lab, col in series:
        s = [p[2] for p in path_slacks(os.path.join(sta, c, "max.rpt"))]
        ax.hist(s, bins=bins, histtype="step", linewidth=1.4, color=col, label=f"{lab}  (WNS {min(s):.2f} ns)")
    ax.set_xlabel("Setup slack (ns), 60 ns clock period")
    ax.set_ylabel("Timing paths")
    ax.legend(loc="upper left", handlelength=1.4)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_title(f"Setup slack of the {len(s)} worst paths at each process corner", loc="left")
    # right: worst path per endpoint class, SS corner
    ax = axes[1]
    s = path_slacks(os.path.join(sta, "nom_ss_125C_4v50", "max.rpt"))
    best = collections.defaultdict(lambda: 1e9)
    nper = collections.Counter()
    for sp, ep, v in s:
        k = endpoint_class(ep)
        best[k] = min(best[k], v)
        nper[k] += 1
    ks = sorted(best, key=lambda k: best[k])
    ax.barh(range(len(ks)), [best[k] for k in ks], height=0.62, color=SLOT[1], edgecolor=SURF)
    for i, k in enumerate(ks):
        ax.text(best[k] + 0.6, i, f"{best[k]:.2f} ns  ({nper[k]} paths)", va="center", fontsize=6, color=INK2)
    ax.set_yticks(range(len(ks)))
    ax.set_yticklabels(ks, fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlim(0, max(best.values()) * 1.75)
    ax.set_xlabel("Worst setup slack at SS corner (ns)")
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_title("By capturing endpoint", loc="left")
    save(fig, out, "fig04_slack_distribution")


# ---------------------------------------------------------------- fig 5: wirelength
def fig_wirelength(D, out):
    f = glob.glob(os.path.join(D["run"], "*-odb-reportwirelength", "wire_lengths.csv"))[0]
    L, names = [], []
    for line in open(f).read().splitlines()[1:]:
        n, v = line.rsplit(",", 1)
        um = float(v[:-2]) * 1000 if v.endswith("mm") else float(v[:-2])
        L.append(um)
        names.append(n.replace("\\", ""))
    L = np.array(L)
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.2), gridspec_kw={"wspace": 0.28})
    ax = axes[0]
    bins = np.logspace(np.log10(max(1, L.min())), np.log10(L.max()), 40)
    ax.hist(L, bins=bins, color=SLOT[0], edgecolor=SURF, linewidth=0.4)
    ax.set_xscale("log")
    ax.set_xlabel("Routed net length (µm, log scale)")
    ax.set_ylabel("Top-level nets")
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    med = np.median(L)
    ax.axvline(med, color=INK2, linewidth=0.8, linestyle=(0, (3, 2)))
    ax.text(med * 1.1, ax.get_ylim()[1] * 0.92, f"median {med:.0f} µm", fontsize=6.3, color=INK2)
    ax.set_title(f"Length distribution of {len(L):,} top-level nets", loc="left")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax = axes[1]
    srt = np.sort(L)[::-1]
    cum = np.cumsum(srt) / srt.sum() * 100
    frac = np.arange(1, len(srt) + 1) / len(srt) * 100
    ax.plot(frac, cum, color=SLOT[0], linewidth=1.6)
    ax.plot([0, 100], [0, 100], color=INK3, linewidth=0.7, linestyle=(0, (3, 2)))
    for q in (5, 20):
        k = int(len(srt) * q / 100)
        ax.scatter(q, cum[k - 1], s=18, color=SLOT[0], edgecolor=SURF, linewidth=1, zorder=3)
        ax.text(q + 2.5, cum[k - 1] - 6, f"longest {q}% of nets\ncarry {cum[k - 1]:.0f}% of the wire",
                fontsize=6.2, color=INK, va="top")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Nets, longest first (% of nets)")
    ax.set_ylabel("Cumulative routed length (%)")
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.set_title(f"Concentration of top-level wiring ({L.sum() / 1000:.0f} mm total)", loc="left")
    save(fig, out, "fig05_wirelength")


# ---------------------------------------------------------------- fig 6: density map
def fig_density(D, out):
    bm = D["bm"]
    x0, y0, x1, y1 = bm["die"]
    b = 20.0
    nx, ny = int(math.ceil((x1 - x0) / b)), int(math.ceil((y1 - y0) / b))
    A = np.zeros((ny, nx))
    for rx0, ry0, rx1, ry1, g, lab in bm["rects"]:
        # spread each cell's area over the bins it covers (cells are much smaller than a bin)
        cx, cy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
        i, j = int((cx - x0) / b), int((cy - y0) / b)
        if 0 <= i < nx and 0 <= j < ny:
            A[j, i] += (rx1 - rx0) * (ry1 - ry0)
    A = A / (b * b) * 100
    A = np.ma.masked_where(A <= 0, A)
    fig, ax = plt.subplots(figsize=(COL1, COL1 * 0.95))
    cm = SEQ_CMAP.copy()
    cm.set_bad("#f3f2ef")
    im = ax.imshow(A, origin="lower", extent=(x0 / 1000, x1 / 1000, y0 / 1000, y1 / 1000), cmap=cm,
                   vmin=0, vmax=np.percentile(A.compressed(), 99), interpolation="nearest")
    for inst, cell, mx0, my0, mx1, my1 in bm["macros"]:
        if "dieart" in cell:
            continue
        col = SRAM_COL if "sram" in cell else MCOL.get(cell, INK2)
        ax.add_patch(patches.Rectangle((mx0 / 1000, my0 / 1000), (mx1 - mx0) / 1000, (my1 - my0) / 1000,
                                       fill="sram" in cell, facecolor=mcolors.to_rgba(SRAM_COL, 0.18) if "sram" in cell else "none",
                                       edgecolor=col, linewidth=0.9))
        if "sram" not in cell:
            lab = MLABEL.get(cell, cell).replace(" (this work)", "")
            if cell == "dsp_mac":
                lab = "DSP" + inst[-1]
            if cell == "posit_decoder_32_2":
                lab = "Posit"
            below = cell == "dsp_mac" and inst[-1] in "23"
            ax.text((mx0 + mx1) / 2000, (my0 / 1000 - 0.025) if below else (my1 / 1000 + 0.025), lab,
                    ha="center", va="top" if below else "bottom", fontsize=5.3,
                    color=INK, fontweight="bold" if cell == "posit_decoder_32_2" else "normal")
    ax.text(0.68, 2.0, "SRAM", rotation=90, ha="center", va="center", fontsize=5.5, color=SRAM_COL)
    ax.text(2.93, 2.0, "SRAM", rotation=90, ha="center", va="center", fontsize=5.5, color=SRAM_COL)
    ax.set_xlim(x0 / 1000, x1 / 1000)
    ax.set_ylim(y0 / 1000, y1 / 1000)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_aspect("equal")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Standard-cell area density (%)", fontsize=7)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=6, length=2)
    ax.set_title("Placement density, 20 µm bins", loc="left")
    save(fig, out, "fig06_density_map")


# ---------------------------------------------------------------- fig 7: cell classes
CLASS_GROUPS = [
    ("Sequential", ["sequential_cell"]),
    ("Combinational logic", ["multi_input_combinational_cell"]),
    ("Buffers and inverters", ["buffer", "inverter"]),
    ("Timing-repair buffers", ["timing_repair_buffer"]),
    ("Clock tree", ["clock_buffer", "clock_inverter"]),
]


def fig_classes(D, out):
    rows = [(MLABEL[k], D["macro"][k]) for k, _, _ in MACROS]
    fig, ax = plt.subplots(figsize=(COL1, 2.3))
    for i, (lab, m) in enumerate(rows):
        vals = [sum(m.get(f"design__instance__area__class:{c}", 0) for c in cs) for _, cs in CLASS_GROUPS]
        tot = sum(vals)
        left = 0
        for j, v in enumerate(vals):
            w = 100 * v / tot
            ax.barh(i, w, left=left, height=0.62, color=SLOT[j], edgecolor=SURF, linewidth=0.8,
                    label=CLASS_GROUPS[j][0] if i == 0 else None)
            if w >= 9:
                ax.text(left + w / 2, i, f"{w:.0f}", ha="center", va="center", fontsize=5.8, color=text_on(SLOT[j]))
            left += w
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of logic-cell area (%)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(-0.02, 1.0), handlelength=1.0, columnspacing=0.8,
              fontsize=6.2)
    ax.set_title("Cell-area mix per hard macro", loc="left", pad=26)
    save(fig, out, "fig07_cell_class_mix")


# ---------------------------------------------------------------- fig 8: macro power / area
def fig_power(D, out):
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.25), gridspec_kw={"wspace": 0.45, "width_ratios": [1.15, 1]})
    ax = axes[0]
    keys = [k for k, _, _ in MACROS]
    for i, k in enumerate(keys):
        m = D["macro"][k]
        tot = m["power__total"] * 1e3
        sw = m["power__switching__total"] / m["power__total"] * 100
        ax.plot([0.5, tot], [i, i], color=GRID, linewidth=1.2, zorder=1)
        ax.scatter(tot, i, s=30, color=MCOL[k], edgecolor=SURF, linewidth=1.1, zorder=3)
        ax.text(tot * 1.25, i, f"{tot:.2f} mW  ({sw:.0f}% switching)", va="center", fontsize=6, color=INK2)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([MLABEL[k] for k in keys], fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(1, 2000)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Power per instance (mW, log), TT corner, vectorless estimate")
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_title("Estimated power per hard macro", loc="left")
    # right: area vs cells, labelled points
    ax = axes[1]
    offs = {"cpu_core": (-6, -10, "right"), "dsp_mac": (7, 2, "left"), "simd_alu": (-7, 6, "right"),
            "spimemio": (8, 3, "left"), "simpleuart": (-7, -8, "right"), "posit_decoder_32_2": (8, -2, "left")}
    for k in keys:
        m = D["macro"][k]
        a = m["design__die__area"] / 1e6
        n = m["design__instance__count__stdcell"]
        u = m["design__instance__utilization"] * 100
        ax.scatter(a, n, s=40, color=MCOL[k], edgecolor=SURF, linewidth=1.2, zorder=3)
        dx, dy, ha = offs[k]
        ax.annotate(f"{MLABEL[k].replace(' (this work)', '*')} ({u:.0f}% util.)", (a, n), xytext=(dx, dy),
                    textcoords="offset points", fontsize=5.8, color=INK, ha=ha, va="center",
                    fontweight="bold" if "posit" in k else "normal")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.02, 2.0)
    ax.set_ylim(400, 50000)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Macro area (mm², log)")
    ax.set_ylabel("Standard cells (log)")
    ax.grid(True, which="major")
    ax.set_axisbelow(True)
    ax.set_title("Area and cell count (* this work)", loc="left")
    save(fig, out, "fig08_macro_power_area")


# ---------------------------------------------------------------- fig 9: evolution
def logic_cells(m):
    keys = ["sequential_cell", "multi_input_combinational_cell", "buffer", "inverter", "timing_repair_buffer",
            "clock_buffer", "clock_inverter"]
    return sum(m.get(f"design__instance__count__class:{k}", 0) for k in keys)


def fig_evolution(D, out):
    v3_logic = logic_cells(D["chip"]) + sum(logic_cells(D["macro"][k]) * INSTANCES[k] for k in INSTANCES)
    v2_logic = logic_cells(D["v2"]) + logic_cells(D["v2macro"])
    v1_logic = logic_cells(D["v1"])
    data = {
        "Die area (mm²)": [D["v1"]["design__die__area"] / 1e6, D["v2"]["design__die__area"] / 1e6,
                           D["chip"]["design__die__area"] / 1e6],
        "Logic cells (thousands)": [v1_logic / 1e3, v2_logic / 1e3, v3_logic / 1e3],
        "Hard macros": [0, 5, 17],
        "Signal pads": [70, 28, 28],
    }
    labels = ["v1", "v2", "v3"]
    fig, axes = plt.subplots(1, 4, figsize=(COL2, 1.65), gridspec_kw={"wspace": 0.5})
    for ax, (title, vals) in zip(axes, data.items()):
        ax.bar(range(3), vals, width=0.62, color=[SLOT[0]] * 3, edgecolor=SURF)
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.03, f"{v:.1f}" if v < 100 and v != int(v) else f"{v:.0f}",
                    ha="center", va="bottom", fontsize=6.3, color=INK2)
        ax.set_xticks(range(3))
        ax.set_xticklabels(labels, fontsize=5.8)
        ax.set_ylim(0, max(vals) * 1.22)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=7.3)
    fig.suptitle("From a pad-limited decoder chip to a design-limited SoC", x=0.08, ha="left", y=1.12, fontsize=8.5)
    fig.text(0.08, -0.12, "v1: decoder alone with direct pads · v2: RISC-V SoC with posit macro and 2 KB SRAM · "
             "v3: multi-block SoC (CPU, 4 DSP, SIMD, SPI, UART, posit, 4 KB SRAM)", fontsize=6.3, color=INK2)
    save(fig, out, "fig09_design_evolution")


# ---------------------------------------------------------------- fig 10: posit decoder delay
def fig_posit(D, out):
    m = D["macro"]["posit_decoder_32_2"]
    budget, unc = 20.0, 0.25
    groups = [("SS", "125 °C, 4.5 V", "ss_125C_4v50"), ("TT", "25 °C, 5.0 V", "tt_025C_5v00"),
              ("FF", "−40 °C, 5.5 V", "ff_n40C_5v50")]
    rcs = [("min", SLOT[2]), ("nom", SLOT[0]), ("max", SLOT[1])]
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.0), gridspec_kw={"width_ratios": [1.35, 1], "wspace": 0.35})
    ax = axes[0]
    for gi, (g, cond, key) in enumerate(groups):
        for ri, (rc, col) in enumerate(rcs):
            d = budget - unc - m[f"timing__setup__ws__corner:{rc}_{key}"]
            y = gi * 4 + ri
            ax.plot([0, d], [y, y], color=GRID, linewidth=1.2, zorder=1)
            ax.scatter(d, y, s=26, color=col, edgecolor=SURF, linewidth=1, zorder=3,
                       label=f"{rc} RC" if gi == 0 else None)
            ax.text(d + 0.35, y, f"{d:.2f} ns", va="center", fontsize=6, color=INK2)
    ax.set_yticks([gi * 4 + 1 for gi in range(3)])
    ax.set_yticklabels([f"{g}\n{c}" for g, c, _ in groups], fontsize=6.5)
    ax.invert_yaxis()
    ax.axvline(budget - unc, color=INK2, linewidth=0.8, linestyle=(0, (3, 2)))
    ax.text(budget - unc + 0.3, 10.9, "20 ns constraint", ha="left", va="bottom", fontsize=6, color=INK2)
    ax.set_xlim(0, 23)
    ax.set_xlabel("Worst input-to-output delay (ns), post-route STA, 5% derate")
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), handlelength=0.8, fontsize=6.3, ncol=3,
              columnspacing=0.8, borderaxespad=0.2)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_ylim(11.3, -0.8)
    ax.set_title(r"Posit$\langle 32,2 \rangle$ decoder macro: critical-path delay", loc="left", pad=14)
    ax = axes[1]
    counts = collections.defaultdict(int)
    for g, lab, n in D["bm"]["counts"]:
        if g == "posit_decoder_32_2" and lab != "Clock tree":
            counts[lab] += n
    ks = sorted(counts, key=lambda k: -counts[k])
    tot = sum(counts.values())
    left = 0
    for j, k in enumerate(ks):
        w = 100 * counts[k] / tot
        ax.barh(0, w, left=left, height=0.5, color=SLOT[j], edgecolor=SURF, linewidth=1)
        ax.text(left + w / 2, 0.42 if j % 2 == 0 else -0.42, f"{k}\n{counts[k]} cells ({w:.0f}%)", ha="center",
                va="bottom" if j % 2 == 0 else "top", fontsize=5.8, color=INK)
        left += w
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.3, 1.3)
    ax.axis("off")
    ax.text(0, 1.3, f"Logic cells by function: {tot} cells, {m['design__die__area'] / 1e6:.3f} mm²,\n"
            f"{m['power__total'] * 1e3:.2f} mW (vectorless, TT)", fontsize=7.5, va="bottom")
    save(fig, out, "fig10_posit_decoder")


def main():
    ap = argparse.ArgumentParser()
    for a in ("res", "run", "v1", "v2", "v2macro", "out"):
        ap.add_argument("--" + a, required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    setup_style()
    D = load(args)
    for f in (fig_area, fig_subblocks, fig_timing, fig_slack_dist, fig_wirelength, fig_density, fig_classes,
              fig_power, fig_evolution, fig_posit):
        f(D, args.out)


if __name__ == "__main__":
    main()
