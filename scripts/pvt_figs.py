#!/usr/bin/env python3
"""PVT figures of the posit<32,2> decoder from the OpenSTA sweep (pvt_parse.py output).

All values come from the signed-off post-route netlist with its extracted RC
(min/nom/max SPEF) and the 15 Liberty corners of gf180mcu_fd_sc_mcu7t5v0.
Power is vectorless: input activity 0.2 per cycle at 50 MHz unless stated.
Usage: pvt_figs.py pvt.json out_dir
"""
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
from paper_figs3 import (COL1, COL2, GRID, INK, INK2, INK3, SEQ_CMAP, SLOT, save,  # noqa: E402
                         setup_style)

PT = [  # (process, temperature, label, colour, marker, linestyle)
    ("ss", 125, r"SS, 125$\,^{\circ}$C", SLOT[7], "v", "-"),
    ("ss", -40, r"SS, $-$40$\,^{\circ}$C", SLOT[1], "v", "--"),
    ("tt", 25, r"TT, 25$\,^{\circ}$C", SLOT[0], "o", "-"),
    ("ff", -40, r"FF, $-$40$\,^{\circ}$C", SLOT[2], "^", "--"),
    ("ff", 125, r"FF, 125$\,^{\circ}$C", SLOT[6], "^", "-"),
]
PERIOD_NS = 20.0
TITLE = r"Posit$\langle 32,2\rangle$ decoder"


def grid(ax, axis="both"):
    ax.grid(True, axis=axis, color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)


def corners_of(d, p, t):
    cs = [(n, c) for n, c in d["corners"].items() if c["process"] == p and c["temp"] == t]
    return sorted(cs, key=lambda x: x[1]["vdd"])


def short(n, c):
    return f"{c['process'].upper()} {c['temp']}$\\,^{{\\circ}}$C {c['vdd']:.2f} V".replace("-", "$-$")


def ordered(d):
    order = {"ss": 0, "tt": 1, "ff": 2}
    return sorted(d["corners"].items(), key=lambda x: (order[x[1]["process"]], x[1]["vdd"], x[1]["temp"]))


# 1. critical-path delay against supply voltage
def fig_delay_vdd(d, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.55))
    grid(ax)
    for p, t, lab, col, mk, ls in PT:
        cs = corners_of(d, p, t)
        v = [c["vdd"] for _, c in cs]
        nom = [c["rc"]["nom"]["max_delay"] for _, c in cs]
        lo = [c["rc"]["min"]["max_delay"] for _, c in cs]
        hi = [c["rc"]["max"]["max_delay"] for _, c in cs]
        ax.fill_between(v, lo, hi, color=col, alpha=0.18, lw=0)
        ax.plot(v, nom, ls=ls, color=col, lw=1.4, marker=mk, ms=4.2, mec="white", mew=0.6, label=lab, zorder=3)
    ax.axhline(PERIOD_NS, color=INK2, lw=0.7, ls=(0, (4, 2)))
    ax.text(5.55, PERIOD_NS * 1.07, "20 ns sign-off budget", ha="right", va="bottom", fontsize=6.3, color=INK2)
    ax.set_yscale("log")
    ax.set_yticks([5, 10, 20, 50, 100])
    ax.set_yticklabels(["5", "10", "20", "50", "100"])
    ax.set_xlabel("Supply voltage, $V_{DD}$ (V)")
    ax.set_ylabel("Critical-path delay (ns)")
    ax.set_xlim(1.45, 5.7)
    ax.legend(ncol=2, loc="upper right", handlelength=2.2, columnspacing=1.0)
    tt = d["corners"]["tt_025C_5v00"]["rc"]["nom"]["max_delay"]
    ax.annotate(f"TT 5.00 V: {tt:.2f} ns ({1e3 / tt:.0f} MHz)", xy=(5.0, tt), xytext=(3.45, 5.25), fontsize=6.3,
                color=SLOT[0], arrowprops=dict(arrowstyle="-", color=SLOT[0], lw=0.6))
    ax.set_title("Bands: min-to-max extracted RC", loc="left", fontsize=6.8, color=INK2)
    save(fig, out, "pvt01_delay_vs_vdd")


# 2. leakage against supply voltage
def fig_leakage(d, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.4))
    grid(ax)
    for p, t, lab, col, mk, ls in PT:
        cs = corners_of(d, p, t)
        ax.plot([c["vdd"] for _, c in cs], [c["rc"]["nom"]["power"]["leakage"] * 1e9 for _, c in cs], ls=ls,
                color=col, lw=1.4, marker=mk, ms=4.2, mec="white", mew=0.6, label=lab, zorder=3)
    ax.set_yscale("log")
    ax.set_xlabel("Supply voltage, $V_{DD}$ (V)")
    ax.set_ylabel("Leakage power (nW)")
    ax.set_xlim(1.45, 5.7)
    hot = d["corners"]["ff_125C_5v50"]["rc"]["nom"]["power"]["leakage"]
    cold = d["corners"]["ff_n40C_5v50"]["rc"]["nom"]["power"]["leakage"]
    ax.annotate("", xy=(5.62, hot * 1e9), xytext=(5.62, cold * 1e9),
                arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.7))
    ax.text(5.52, np.sqrt(hot * cold) * 1e9, f"{hot / cold:.0f}$\\times$\n$-$40 to\n125$\\,^{{\\circ}}$C", ha="right",
            va="center", fontsize=6.2, color=INK2)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0.0, 1.0), handlelength=2.2, columnspacing=0.9,
              fontsize=6.3)
    save(fig, out, "pvt02_leakage_vs_vdd")


# 3. power breakdown at every corner
def fig_power_breakdown(d, out):
    items = ordered(d)
    x = np.arange(len(items))
    internal = np.array([c["rc"]["nom"]["power"]["internal"] for _, c in items]) * 1e3
    switching = np.array([c["rc"]["nom"]["power"]["switching"] for _, c in items]) * 1e3
    leak = np.array([c["rc"]["nom"]["power"]["leakage"] for _, c in items]) * 1e9
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(COL2, 3.3), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1],
                                                                                           hspace=0.08))
    grid(a1, "y")
    grid(a2, "y")
    a1.bar(x, internal, 0.62, color=SLOT[0], label="Internal", zorder=3, edgecolor="white", lw=0.4)
    a1.bar(x, switching, 0.62, bottom=internal, color=SLOT[3], label="Switching", zorder=3, edgecolor="white", lw=0.4)
    for xi, tot in zip(x, internal + switching):
        a1.text(xi, tot + 0.08, f"{tot:.2f}", ha="center", va="bottom", fontsize=5.6, color=INK)
    a1.set_ylabel("Dynamic power (mW)")
    a1.set_ylim(0, (internal + switching).max() * 1.17)
    a1.legend(loc="upper left", ncol=2)
    cols = {"ss": SLOT[7], "tt": SLOT[0], "ff": SLOT[2]}
    a2.vlines(x, 1, leak, color=[cols[c["process"]] for _, c in items], lw=1.2, zorder=2)
    a2.scatter(x, leak, s=18, c=[cols[c["process"]] for _, c in items], zorder=3, edgecolor="white", lw=0.5)
    a2.set_yscale("log")
    a2.set_ylim(8, leak.max() * 3)
    a2.set_yticks([10, 100, 1000])
    a2.set_yticklabels(["10", "100", "1000"])
    a2.set_ylabel("Leakage (nW)")
    a2.set_xticks(x)
    a2.set_xticklabels([f"{c['process'].upper()}\n{c['temp']}$\\,^{{\\circ}}$C\n{c['vdd']:.2f} V".replace("-", "$-$")
                        for _, c in items], fontsize=5.8)
    for b in (5.5, 8.5):
        for a in (a1, a2):
            a.axvline(b, color=INK3, lw=0.5, ls=":")
    a1.set_title("Input activity 0.2 per cycle, 50 MHz, nominal RC", loc="left", fontsize=6.8, color=INK2)
    save(fig, out, "pvt03_power_breakdown")


# 4. energy per decode against delay
def fig_energy_delay(d, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.7))
    grid(ax)
    xs, ys = [], []
    for p, t, lab, col, mk, ls in PT:
        for n, c in corners_of(d, p, t):
            r = c["rc"]
            e = [r[k]["power"]["total"] * PERIOD_NS * 1e-9 * 1e12 for k in ("min", "nom", "max")]
            dl = [r[k]["max_delay"] for k in ("min", "nom", "max")]
            ax.plot([dl[0], dl[2]], [e[1], e[1]], color=col, lw=0.8, alpha=0.7)
            ax.scatter(dl[1], e[1], s=26, marker=mk, color=col, edgecolor="white", lw=0.5, zorder=3)
            xs.append(dl[1])
            ys.append(e[1])
            if p == "tt" or (p == "ff" and t == -40 and c["vdd"] > 5) or (p == "ss" and t == 125 and c["vdd"] < 2):
                off = (-4, -11) if c["vdd"] < 1.7 else (4, 3)
                ax.annotate(f"{c['vdd']:.2f} V", xy=(dl[1], e[1]), xytext=off, textcoords="offset points",
                            fontsize=5.8, color=col, ha="center" if c["vdd"] < 1.7 else "left")
    edp = np.array(xs) * np.array(ys)
    xx = np.logspace(np.log10(4), np.log10(150), 100)
    for k in (250, 500, 1000):
        ax.plot(xx, k / xx, color=INK3, lw=0.5, ls=(0, (3, 2)), zorder=1)
        xl = min(k / 4.6, 128)
        ax.text(xl, k / xl, f"{k}", fontsize=5.6, color=INK3, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
    i = int(np.argmin(edp))
    ax.annotate(f"min. EDP {edp[i]:.0f} pJ$\\cdot$ns", xy=(xs[i], ys[i]), xytext=(9.5, 5.6), fontsize=6.0,
                color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(4.5, 150)
    ax.set_ylim(4, 200)
    ax.set_xlabel("Critical-path delay (ns)")
    ax.set_ylabel("Energy per decode (pJ)")
    ax.set_xticks([5, 10, 20, 50, 100])
    ax.set_xticklabels(["5", "10", "20", "50", "100"])
    ax.set_yticks([5, 10, 20, 50, 100])
    ax.set_yticklabels(["5", "10", "20", "50", "100"])
    h = [Line2D([], [], color=col, marker=mk, ls="", ms=4.5, label=lab) for _, _, lab, col, mk, _ in PT]
    ax.legend(handles=h, loc="upper right", ncol=1, fontsize=6.2)
    ax.set_title("Dashed: constant energy-delay product (pJ$\\cdot$ns)", loc="left", fontsize=6.8, color=INK2)
    save(fig, out, "pvt04_energy_vs_delay")


def out_order(names):
    def key(n):
        m = re.match(r"(\w+)(?:\[(\d+)\])?", n)
        base, idx = m.group(1), int(m.group(2) or 0)
        rank = {"S": 0, "inf": 1, "reg_O": 2, "EXP_O": 3, "Mantissa": 4}[base]
        return rank, -idx
    return sorted(names, key=key)


# 5. per-output delay heat map
def fig_output_heatmap(d, out):
    items = ordered(d)
    names = out_order(items[0][1]["rc"]["nom"]["out_max"].keys())
    M = np.array([[c["rc"]["nom"]["out_max"][o] / c["rc"]["nom"]["max_delay"] for _, c in items] for o in names])
    fig, ax = plt.subplots(figsize=(COL2, 4.4))
    im = ax.imshow(M, aspect="auto", cmap=SEQ_CMAP, vmin=0.3, vmax=1.0, interpolation="nearest")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=5.4)
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels([f"{c['process'].upper()} {c['temp']}$\\,^{{\\circ}}$C\n{c['vdd']:.2f} V".replace("-", "$-$")
                        for _, c in items], fontsize=5.6)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(items)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(names)), minor=True)
    ax.grid(which="minor", color="white", lw=0.6)
    ax.tick_params(which="minor", length=0)
    for b in (5.5, 8.5):
        ax.axvline(b, color="white", lw=2.2)
    for j, (_, c) in enumerate(items):
        i = int(np.argmax(M[:, j]))
        ax.text(j, i, "1.00", ha="center", va="center", fontsize=4.8, color="white", fontweight="bold")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.012)
    cb.set_label("Output delay / critical-path delay", fontsize=6.8)
    cb.ax.tick_params(labelsize=6)
    cb.outline.set_visible(False)
    ax.set_title("Per-output worst arrival at each corner (nominal RC)", loc="left", fontsize=7, color=INK2)
    save(fig, out, "pvt05_output_delay_heatmap")


# 6. power against frequency and input activity
def fig_power_contour(d, out):
    g = d["power_grid"]
    per = sorted({float(k.split("|")[0]) for k in g})
    act = sorted({float(k.split("|")[1]) for k in g})
    key = {}
    for k in g:
        p, a = k.split("|")
        key[(float(p), float(a))] = g[k]["total"] * 1e3
    F = np.array([1e3 / p for p in per])
    Z = np.array([[key[(p, a)] for p in per] for a in act])
    fi = np.argsort(F)
    fig, ax = plt.subplots(figsize=(COL1, 2.6))
    lv = np.array([0.25, 0.5, 1, 2, 4, 8, 16, 32])
    cf = ax.contourf(F[fi], act, Z[:, fi], levels=np.geomspace(Z.min(), Z.max(), 40), cmap=SEQ_CMAP,
                     norm=mcolors.LogNorm(Z.min(), Z.max()))
    cs = ax.contour(F[fi], act, Z[:, fi], levels=lv[(lv > Z.min()) & (lv < Z.max())], colors="white", linewidths=0.7)
    ax.clabel(cs, fmt=lambda v: f"{v:g} mW", fontsize=5.8, inline_spacing=2)
    ax.scatter(F, np.full(len(F), act[0]), s=0)
    for a in act:
        ax.scatter(F, [a] * len(F), s=3, color="white", alpha=0.6, lw=0)
    ax.scatter([50], [0.2], s=46, marker="*", color=SLOT[3], edgecolor=INK, lw=0.5, zorder=4)
    ax.annotate(f"{key[(20.0, 0.2)]:.2f} mW", xy=(50, 0.2), xytext=(56, 0.27), fontsize=6.3, color=INK,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85),
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.6))
    ax.set_xlabel("Operating frequency (MHz)")
    ax.set_ylabel("Input switching activity")
    cb = fig.colorbar(cf, ax=ax, pad=0.02, ticks=[0.1, 0.3, 1, 3, 10, 30])
    cb.ax.set_yticklabels(["0.1", "0.3", "1", "3", "10", "30"], fontsize=6)
    cb.set_label("Total power (mW)", fontsize=7)
    cb.outline.set_visible(False)
    ax.set_title(r"TT, 25$\,^{\circ}$C, 5.00 V, nominal RC", loc="left", fontsize=6.8, color=INK2)
    save(fig, out, "pvt06_power_freq_activity")


def category(cell, pin, first, last):
    b = re.sub(r"_\d+$", "", cell.split("__")[-1])
    if first:
        return "Input buffer"
    if last:
        return "Output buffer"
    if b.startswith("dly"):
        return "Delay cell (dlyb)"
    if b in ("buf", "clkbuf", "inv", "clkinv"):
        return "Repair buffer"
    if b.startswith("mux"):
        return "Multiplexer"
    return "Logic gate"


CAT_COL = {"Input buffer": SLOT[6], "Logic gate": SLOT[0], "Repair buffer": SLOT[3], "Delay cell (dlyb)": SLOT[7],
           "Multiplexer": SLOT[2], "Output buffer": SLOT[4]}


# 7. critical-path anatomy at the three 5 V sign-off corners
def fig_critical_path(d, out):
    sel = [("ss_125C_4v50", r"SS, 125$\,^{\circ}$C, 4.50 V", SLOT[7]), ("tt_025C_5v00", r"TT, 25$\,^{\circ}$C, 5.00 V", SLOT[0]),
           ("ff_n40C_5v50", r"FF, $-$40$\,^{\circ}$C, 5.50 V", SLOT[2])]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL2, 2.6), gridspec_kw=dict(width_ratios=[1.25, 1], wspace=0.32))
    grid(a1)
    shares = {}
    for n, lab, col in sel:
        st = d["corners"][n]["path_max"]["stages"]
        arr = [0] + [s["arrival"] for s in st]
        a1.step(range(len(arr)), arr, where="post", color=col, lw=1.3, label=lab)
        for i, s in enumerate(st):
            c = category(s["cell"], s["pin"], i == 0, i == len(st) - 1)
            if c == "Delay cell (dlyb)":
                a1.plot([i + 1, i + 1], [arr[i], arr[i + 1]], color=col, lw=4.5, alpha=0.3, solid_capstyle="butt")
            shares.setdefault(n, {}).setdefault(c, 0.0)
            shares[n][c] += s["delay"]
    a1.set_xlabel("Stage on the critical path")
    a1.xaxis.set_major_locator(plt.MultipleLocator(2))
    a1.set_ylabel("Arrival time (ns)")
    a1.legend(loc="upper left")
    a1.set_xlim(0, max(len(d["corners"][n]["path_max"]["stages"]) for n, _, _ in sel) + 0.5)
    tt = d["corners"]["tt_025C_5v00"]["path_max"]
    a1.set_title(f"{tt['start']} $\\rightarrow$ {tt['end']} (TT); shaded: dlyb stages", loc="left", fontsize=6.6,
                 color=INK2)
    cats = list(CAT_COL)
    y = np.arange(len(sel))
    left = np.zeros(len(sel))
    for c in cats:
        v = np.array([shares[n].get(c, 0.0) for n, _, _ in sel])
        a2.barh(y, v, left=left, color=CAT_COL[c], height=0.58, edgecolor="white", lw=0.5, label=c)
        for yi, (l, w) in enumerate(zip(left, v)):
            tot = sum(shares[sel[yi][0]].values())
            if w / tot > 0.09:
                a2.text(l + w / 2, yi, f"{100 * w / tot:.0f}%", ha="center", va="center", fontsize=5.8, color="white")
        left += v
    a2.set_yticks(y)
    a2.set_yticklabels([lab for _, lab, _ in sel], fontsize=6.3)
    a2.invert_yaxis()
    a2.set_xlabel("Path delay by cell type (ns)")
    a2.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=3, fontsize=5.9, handlelength=1.2,
              columnspacing=0.8)
    grid(a2, "x")
    save(fig, out, "pvt07_critical_path_anatomy")


# 8. delay window (shortest to longest output path)
def fig_delay_window(d, out):
    items = sorted(d["corners"].items(), key=lambda x: x[1]["rc"]["nom"]["max_delay"])
    fig, ax = plt.subplots(figsize=(COL1, 3.1))
    grid(ax, "x")
    cols = {"ss": SLOT[7], "tt": SLOT[0], "ff": SLOT[2]}
    for i, (n, c) in enumerate(items):
        r = c["rc"]
        col = cols[c["process"]]
        ax.plot([r["nom"]["min_delay"], r["nom"]["max_delay"]], [i, i], color=col, lw=2.2, alpha=0.35,
                solid_capstyle="round")
        ax.plot([r["min"]["max_delay"], r["max"]["max_delay"]], [i, i], color=col, lw=0.8)
        ax.scatter(r["nom"]["min_delay"], i, s=16, color="white", edgecolor=col, lw=1.0, zorder=3)
        ax.scatter(r["nom"]["max_delay"], i, s=18, color=col, edgecolor="white", lw=0.5, zorder=3)
        ax.text(r["nom"]["max_delay"] * 1.12, i, f"{r['nom']['max_delay']:.1f}", va="center", fontsize=5.6,
                color=INK2, zorder=4, bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none"))
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([short(n, c) for n, c in items], fontsize=5.8)
    ax.set_xscale("log")
    ax.set_xlim(0.8, 200)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100])
    ax.set_xticklabels(["1", "2", "5", "10", "20", "50", "100"])
    ax.axvline(PERIOD_NS, color=INK2, lw=0.7, ls=(0, (4, 2)), zorder=1)
    ax.set_xlabel("Input-to-output delay (ns), nominal RC")
    h = [Line2D([], [], marker="o", ls="", mfc="white", mec=INK2, ms=4, label="Shortest path"),
         Line2D([], [], marker="o", ls="", color=INK2, ms=4, label="Critical path"),
         Line2D([], [], color=INK2, lw=0.8, label="RC spread")]
    ax.legend(handles=h, loc="lower right", fontsize=6)
    save(fig, out, "pvt08_delay_window")


# 9. sensitivity to the input transition
def fig_slew(d, out):
    fig, ax = plt.subplots(figsize=(COL1, 2.4))
    grid(ax)
    vc = {}
    cmap = plt.get_cmap("viridis")
    for p, t, lab, col, mk, ls in PT:
        for n, c in corners_of(d, p, t):
            s = sorted((float(k), v) for k, v in c["slew"].items())
            base = dict(s)[0.5]
            ax.plot([a for a, _ in s], [100 * (v - base) / base for _, v in s], color=col, ls=ls, marker=mk, ms=3.2,
                    lw=1.0, mec="white", mew=0.4, alpha=0.4 + 0.6 * (c["vdd"] > 4))
    ax.axhline(0, color=INK3, lw=0.5)
    ax.set_xscale("log")
    ax.set_xticks([0.1, 0.25, 0.5, 1, 2])
    ax.set_xticklabels(["0.1", "0.25", "0.5", "1", "2"])
    ax.set_xlabel("Input transition time (ns)")
    ax.set_ylabel(r"Critical-path delay change (%)")
    h = [Line2D([], [], color=col, ls=ls, marker=mk, ms=3.5, label=lab) for _, _, lab, col, mk, ls in PT]
    ax.legend(handles=h, loc="upper left", fontsize=6.0)
    ax.set_title("Relative to 0.5 ns; faint lines: 1.62 to 3.60 V corners", loc="left", fontsize=6.6, color=INK2)
    save(fig, out, "pvt09_input_slew_sensitivity")


def main():
    d = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    setup_style()
    for f in (fig_delay_vdd, fig_leakage, fig_power_breakdown, fig_energy_delay, fig_output_heatmap,
              fig_power_contour, fig_critical_path, fig_delay_window, fig_slew):
        f(d, out)
        print("ok", f.__name__)


if __name__ == "__main__":
    main()
