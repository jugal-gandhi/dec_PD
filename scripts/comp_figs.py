#!/usr/bin/env python3
"""Component-wise area, delay and power figures of the signed-off posit<32,2> decoder.
Usage: comp_figs.py <breakdown.json> <out_dir>"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paper_figs3 import COL1, GRID, INK, INK2, save, setup_style    # noqa: E402

MATTE = {"AND-OR network": "#a9c1da", "Boundary comparator": "#e6d2a6", "In-line shifter": "#cfcdc9",
         "Output encoding": "#e6bccb", "Timing-repair buffers": "#eec5ad", "I/O buffers": "#c7badd",
         "Physical cells": "#ebe8e1"}
SHORT = {"AND-OR network": "AND-OR network", "Boundary comparator": "1-bit boundary comparator",
         "In-line shifter": "In-line shifter", "Output encoding": "Output encoding",
         "Timing-repair buffers": "Timing-repair buffers", "I/O buffers": "I/O buffers",
         "Physical cells": "Tap / endcap cells"}
CORN = [("ss_125C_4v50", r"SS, 125$\,^{\circ}$C, 4.50 V"), ("tt_025C_5v00", r"TT, 25$\,^{\circ}$C, 5.00 V"),
        ("ff_n40C_5v50", r"FF, $-$40$\,^{\circ}$C, 5.50 V")]


def light(c):
    r, g, b = matplotlib.colors.to_rgb(c)
    return 0.299 * r + 0.587 * g + 0.114 * b > 0.62


def shares(b, folded):
    area = b["area_folded"] if folded else b["area"]
    dly = b["delay"]["tt_025C_5v00"]["by_owner" if folded else "by_cat"]
    pw = {k: v[3] for k, v in (b["power_folded"] if folded else b["power"])["tt_025C_5v00"].items()}
    cats = [c for c in MATTE if (area.get(c, 0) > 0 or dly.get(c, 0) > 0 or pw.get(c, 0) > 0)]
    rows = [("Area", area, sum(area.values()), "$\\mu$m$^2$"), ("Power", pw, sum(pw.values()), "mW"),
            ("Delay", dly, sum(dly.values()), "ns")]
    return cats, rows


LEG1 = {"AND-OR network": "AND-OR network", "Boundary comparator": "Comparator", "In-line shifter": "Shifter",
        "Output encoding": "Output enc.", "Timing-repair buffers": "Repair buffers", "I/O buffers": "I/O buffers",
        "Physical cells": "Tap/endcap"}


FLOW_POWER_MW = 2.57          # sign-off power reported by the flow (power__total)


def fig_share(b, out, folded, name):
    cats, rows = shares(b, folded)
    fig, ax = plt.subplots(figsize=(COL1 * 1.25, 1.95))
    pitch = 1.0
    for i, (lab, d, tot, unit) in enumerate(rows):
        y = i * pitch
        left = 0.0
        for c in cats:
            v = 100 * d.get(c, 0.0) / tot
            if v <= 0:
                continue
            ax.barh(y, v, left=left, color=MATTE[c], height=0.56, edgecolor="white", lw=0.6)
            if v >= 5.5:
                ax.text(left + v / 2, y, f"{v:.0f}%", ha="center", va="center", fontsize=6.0,
                        color=INK if light(MATTE[c]) else "white")
            left += v
        val = f"{tot:,.0f} {unit}" if lab == "Area" else (f"{FLOW_POWER_MW:.2f} {unit}" if lab == "Power"
                                                          else f"{tot:.2f} {unit}")
        ax.text(100, y + 0.3, f"Total: {val}", ha="right", va="top", fontsize=5.6, color=INK2)
    ax.set_yticks([i * pitch for i in range(len(rows))])
    ax.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax.set_ylim((len(rows) - 1) * pitch + 0.55, -0.4)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Component-wise APD contribution (%)")
    ax.grid(True, axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    h = [plt.Rectangle((0, 0), 1, 1, color=MATTE[c]) for c in cats]
    ax.legend(h, [LEG1[c] for c in cats], loc="lower center", bbox_to_anchor=(0.46, 1.0), ncol=len(cats),
              fontsize=5.6, handlelength=0.9, handletextpad=0.3, columnspacing=0.7, frameon=False,
              borderaxespad=0.2)
    save(fig, out, name)


def fig_path(b, out):
    fig, ax = plt.subplots(figsize=(COL1 * 1.25, 1.75))
    seen = set()
    for i, (corner, lab) in enumerate(CORN):
        left = 0.0
        for c, d, cell, owner in b["delay"][corner]["seq"]:
            ax.barh(i, d, left=left, color=MATTE[owner], height=0.58, edgecolor="white", lw=0.35)
            if "dly" in cell:
                ax.barh(i, d, left=left, color="none", height=0.58, edgecolor="#8a857e", lw=0, hatch="////")
            left += d
            seen.add(owner)
        ax.text(left + 0.25, i, f"{left:.2f} ns", va="center", fontsize=6.2, color=INK)
    ax.set_yticks(range(len(CORN)))
    ax.set_yticklabels([l for _, l in CORN], fontsize=6.4)
    ax.invert_yaxis()
    ax.set_xlim(0, b["delay"]["ss_125C_4v50"]["total"] * 1.13)
    tt = b["delay"]["tt_025C_5v00"]
    ax.set_xlabel(f"Critical path, stage by stage (ns): {tt['start']} $\\rightarrow$ {tt['end']} at TT")
    ax.grid(True, axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    order = [c for c in MATTE if c in seen]
    h = [plt.Rectangle((0, 0), 1, 1, color=MATTE[c]) for c in order] + \
        [plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor="#8a857e", lw=0.4, hatch="////")]
    ax.legend(h, [SHORT[c] for c in order] + ["Delay cell (dlyb)"], loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=4, fontsize=5.8, handlelength=1.0, handletextpad=0.4, columnspacing=0.9, frameon=False)
    save(fig, out, "comp03_critical_path_by_component")


def fig_bubble(b, out):
    area = b["area_folded"]
    pw = {k: v[3] * 1e3 for k, v in b["power_folded"]["tt_025C_5v00"].items()}
    dly = b["delay"]["tt_025C_5v00"]["by_owner"]
    cats = [c for c in MATTE if c not in ("Timing-repair buffers", "Physical cells") and area.get(c, 0) > 0]
    fig, ax = plt.subplots(figsize=(COL1, 2.5))
    ax.grid(True, color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for c in cats:
        s = 40 + 140 * dly.get(c, 0.0)
        ax.scatter(area[c], pw.get(c, 0), s=s, color=MATTE[c], edgecolor="white", lw=0.8, alpha=0.95, zorder=3)
        txt = f"{SHORT[c]}\n{dly.get(c, 0):.2f} ns"
        r = np.sqrt(s / np.pi) + 3
        side = -1 if c == "In-line shifter" else 1
        ax.annotate(txt, (area[c], pw.get(c, 0)), xytext=(side * r, 0), textcoords="offset points",
                    ha="right" if side < 0 else "left", va="center", fontsize=6.0, color=INK, linespacing=1.15)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(150, 20000)
    ax.set_ylim(0.04, 6)
    ax.set_xticks([200, 500, 1000, 2000, 5000, 10000])
    ax.set_xticklabels(["200", "500", "1k", "2k", "5k", "10k"])
    ax.set_yticks([0.05, 0.1, 0.2, 0.5, 1, 2, 5])
    ax.set_yticklabels(["0.05", "0.1", "0.2", "0.5", "1", "2", "5"])
    ax.set_xlabel("Area with its buffering ($\\mu$m$^2$)")
    ax.set_ylabel("Power at TT (mW)")
    ax.text(0.02, 0.97, "Bubble size: critical-path delay share (TT)", transform=ax.transAxes, fontsize=6.0,
            color=INK2, va="top")
    save(fig, out, "comp04_area_power_delay_bubble")


def main():
    b = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    setup_style()
    fig_share(b, out, True, "comp01_apd_share_by_component")
    fig_share(b, out, False, "comp02_apd_share_repair_separate")
    fig_path(b, out)
    fig_bubble(b, out)


if __name__ == "__main__":
    main()
