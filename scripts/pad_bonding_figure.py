#!/usr/bin/env python3
"""Pad ring + floorplan + QFN-40 bonding diagram of the v3 SoC in one figure.

Package, exposed pad, die, pad positions, core ring and macro placements are
to scale (die coordinates from the final DEF / floorplan). Pad cells are drawn
wider than their true 75 um so that their names stay readable.
Usage: pad_bonding_figure.py out_basename
"""
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib import patches                      # noqa: E402

INK, INK2, INK3, SURF = "#0b0b0b", "#52514e", "#8c8b86", "#ffffff"
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
PADCOL = {"io": "#2a78d6", "in": "#1baf7a", "clk": "#eb6834", "vdd": "#e34948", "vss": "#3a3936"}
DIE = 3.602
C = DIE / 2                                         # die centre (mm)
PKG, PIN_LEN, PIN_W, PITCH = 6.0, 0.40, 0.25, 0.5
EPAD = 4.1
PAD_DEPTH, PAD_DRAW_W = 0.350, 0.205               # true depth; drawn width (true 0.075)
PAD_C = [0.6085 + 0.265 * i for i in range(10)]     # pad centres along an edge (mm, die coords)

# QFN pin order: counter-clockwise from the top of the west side
SIDES = [
    ("W", ["gpio06", "dvdd1", "gpio05", "gpio04", "dvss0", "gpio03", "gpio02", "dvdd0", "gpio01", "gpio00"]),
    ("S", ["clk", "flash_csb", "dvss4", "flash_clk", "flash_io0", "dvdd5", "flash_io1", "flash_io2", "dvss5", "flash_io3"]),
    ("E", ["gpio14", "gpio15", "dvdd3", "irq5", "irq6", "dvss3", "ser_rx", "ser_tx", "dvdd4", "rst_n"]),
    ("N", ["gpio13", "dvss2", "gpio12", "gpio11", "dvdd2", "gpio10", "gpio09", "dvss1", "gpio08", "gpio07"]),
]
GROUP = {"W": "GPIO[0:6]", "S": "clock · SPI flash (QSPI)", "E": "GPIO[14:15] · IRQ · UART · reset", "N": "GPIO[7:13]"}


def short(n):
    if n.startswith("gpio"):
        return f"GPIO{int(n[4:])}"
    if n.startswith("dvdd"):
        return "VDD"
    if n.startswith("dvss"):
        return "VSS"
    return {"clk": "CLK", "flash_csb": "CSB", "flash_clk": "SCK", "flash_io0": "IO0", "flash_io1": "IO1",
            "flash_io2": "IO2", "flash_io3": "IO3", "irq5": "IRQ5", "irq6": "IRQ6", "ser_rx": "RX",
            "ser_tx": "TX", "rst_n": "RSTn"}[n]


def kind(n):
    if n.startswith("dvdd"):
        return "vdd"
    if n.startswith("dvss"):
        return "vss"
    if n == "clk":
        return "clk"
    if n in ("irq5", "irq6", "ser_rx", "rst_n"):
        return "in"
    return "io"


def d2f(x, y):
    """die coordinates (mm, origin lower-left) -> figure coordinates (origin die centre)"""
    return x - C, y - C


def pad_geom(side, i):
    """Pad rectangle (x0, y0, w, h), bond point on the die edge, label centre, text rotation."""
    if side == "W":
        yc = PAD_C[9 - i]
        x0, y0 = 0.026, yc - PAD_DRAW_W / 2
        r = (x0, y0, PAD_DEPTH, PAD_DRAW_W)
        bond = (0.026 + 0.03, yc)
        lab, rot = (0.026 + PAD_DEPTH / 2, yc), 0
    elif side == "S":
        xc = PAD_C[i]
        r = (xc - PAD_DRAW_W / 2, 0.026, PAD_DRAW_W, PAD_DEPTH)
        bond = (xc, 0.026 + 0.03)
        lab, rot = (xc, 0.026 + PAD_DEPTH / 2), 90
    elif side == "E":
        yc = PAD_C[i]
        r = (DIE - 0.026 - PAD_DEPTH, yc - PAD_DRAW_W / 2, PAD_DEPTH, PAD_DRAW_W)
        bond = (DIE - 0.026 - 0.03, yc)
        lab, rot = (DIE - 0.026 - PAD_DEPTH / 2, yc), 0
    else:
        xc = PAD_C[9 - i]
        r = (xc - PAD_DRAW_W / 2, DIE - 0.026 - PAD_DEPTH, PAD_DRAW_W, PAD_DEPTH)
        bond = (xc, DIE - 0.026 - 0.03)
        lab, rot = (xc, DIE - 0.026 - PAD_DEPTH / 2), 90
    return r, bond, lab, rot


def pin_geom(side, i):
    """QFN pin rectangle (figure coords), inner bond point, number position."""
    h = PKG / 2
    off = (4.5 - i) * PITCH                          # i = 0 .. 9 along the numbering direction
    if side == "W":
        y = off
        return (-h, y - PIN_W / 2, PIN_LEN, PIN_W), (-h + PIN_LEN, y), (-h - 0.14, y), "right"
    if side == "S":
        x = -off
        return (x - PIN_W / 2, -h, PIN_W, PIN_LEN), (x, -h + PIN_LEN), (x, -h - 0.16), "center"
    if side == "E":
        y = -off
        return (h - PIN_LEN, y - PIN_W / 2, PIN_LEN, PIN_W), (h - PIN_LEN, y), (h + 0.14, y), "left"
    x = off
    return (x - PIN_W / 2, h - PIN_LEN, PIN_W, PIN_LEN), (x, h - PIN_LEN), (x, h + 0.16), "center"


MACROS = [  # inst label, x, y, w, h (um), colour, text
    ("CPU", 1213.0, 2171.5, 930.72, 948.64, SLOT[0], "RV32IMC CPU core\n(PicoRV32)"),
    ("POSIT", 2189.0, 2600.5, 200.0, 200.0, SLOT[5], ""),
    ("SPI", 1347.0, 1592.0, 286.63, 304.56, SLOT[3], "SPI flash\nctrl"),
    ("UART", 1972.5, 1596.0, 278.54, 296.46, SLOT[4], "UART"),
    ("DSP0", 1210.5, 934.5, 364.44, 382.36, SLOT[1], "DSP0\nMAC"),
    ("DSP1", 1645.0, 934.5, 364.44, 382.36, SLOT[1], "DSP1\nMAC"),
    ("DSP2", 1210.5, 482.0, 364.44, 382.36, SLOT[1], "DSP2\nMAC"),
    ("DSP3", 1645.0, 482.0, 364.44, 382.36, SLOT[1], "DSP3\nMAC"),
    ("SIMD", 2079.0, 734.0, 312.50, 330.42, SLOT[2], "SIMD\nALU"),
]
SRAM_Y = [726.0, 1281.0, 1836.0, 2391.0]


def main():
    out = sys.argv[1]
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Liberation Serif", "DejaVu Serif"],
                         "pdf.fonttype": 42, "savefig.dpi": 600})
    fig, ax = plt.subplots(figsize=(7.16, 7.9))
    h = PKG / 2

    # package body, exposed pad
    ax.add_patch(patches.FancyBboxPatch((-h, -h), PKG, PKG, boxstyle="round,pad=0,rounding_size=0.12",
                                        facecolor="#f7f6f3", edgecolor=INK3, linewidth=1.0, zorder=1))
    ax.add_patch(patches.Rectangle((-EPAD / 2, -EPAD / 2), EPAD, EPAD, facecolor="#e9e8e4", edgecolor="#c9c8c3",
                                   linewidth=0.6, zorder=1))
    ax.add_patch(patches.Circle((-h + 0.28, h - 0.28), 0.07, color=INK, zorder=3))
    ax.text(-EPAD / 2 + 0.05, -EPAD / 2 + 0.05, "exposed pad 4.1 mm → VSS", fontsize=5.2, color=INK2,
            va="bottom", ha="left", zorder=7, bbox=dict(boxstyle="round,pad=0.15", fc="#e9e8e4", ec="none"))

    # die
    dx0, dy0 = d2f(0, 0)
    ax.add_patch(patches.Rectangle((dx0, dy0), DIE, DIE, facecolor="#fbfbfa", edgecolor=INK, linewidth=1.1, zorder=2))
    # corner cells
    for cx, cy, nm in ((0.026, 0.026, "cornLL"), (DIE - 0.381, 0.026, "cornLR"), (0.026, DIE - 0.381, "cornTL"),
                       (DIE - 0.381, DIE - 0.381, "cornTR")):
        x, y = d2f(cx, cy)
        ax.add_patch(patches.Rectangle((x, y), 0.355, 0.355, facecolor="#9fc1ea", edgecolor="#5f86b8",
                                       linewidth=0.6, zorder=3))
        ax.text(x + 0.1775, y + 0.1775, nm, fontsize=5, ha="center", va="center", color=INK, zorder=4)

    # core power ring (25 um, drawn at the core boundary)
    rx, ry = d2f(0.420, 0.420)
    ax.add_patch(patches.Rectangle((rx, ry), DIE - 0.84, DIE - 0.84, fill=False, edgecolor=SLOT[7],
                                   linewidth=1.6, zorder=3))
    cx, cy = d2f(0.442, 0.442)
    ax.add_patch(patches.Rectangle((cx, cy), DIE - 0.884, DIE - 0.884, fill=False, edgecolor=INK, linewidth=0.7,
                                   linestyle=(0, (4, 2)), zorder=3))

    # macros
    for nm, x, y, w, hh, col, txt in MACROS:
        X, Y = d2f(x / 1000, y / 1000)
        ax.add_patch(patches.Rectangle((X, Y), w / 1000, hh / 1000, facecolor=col, alpha=0.20 if nm != "POSIT" else 0.55,
                                       edgecolor=col, linewidth=1.4 if nm == "POSIT" else 0.9, zorder=4))
        if txt:
            ty = Y + hh / 2000 - (0.2 if nm == "CPU" else 0)
            ax.text(X + w / 2000, ty, txt, ha="center", va="center", fontsize=6.6 if nm == "CPU" else 5.6,
                    color=INK, zorder=6, linespacing=1.1, fontweight="bold" if nm == "CPU" else "normal")
    # ALU region inside the CPU (cell 10-90 percentile box)
    X, Y = d2f(1.862, 2.707)
    ax.add_patch(patches.Rectangle((X, Y), 0.210, 0.117, fill=False, edgecolor=SLOT[0], linewidth=0.9,
                                   linestyle=(0, (2, 1)), zorder=5))
    ax.text(X + 0.105, Y - 0.03, "ALU", fontsize=5.2, ha="center", va="top", color=SLOT[0], zorder=6)
    # posit callout
    X, Y = d2f(2.289, 2.6005)
    TX, TY = d2f(2.42, 2.03)
    ax.annotate(r"Posit$\langle 32,2\rangle$ decoder" + "\n(this work)", xy=(X + 0.02, Y), xytext=(TX, TY), fontsize=5.6,
                fontweight="bold", color=SLOT[5], ha="right", va="center", zorder=7, multialignment="right",
                arrowprops=dict(arrowstyle="-", color=SLOT[5], lw=0.8, relpos=(0.915, 1.0)))
    # SRAM columns
    for col_x, name in ((482.0, "Main RAM"), (2688.0, "Scratch")):
        for k, y in enumerate(SRAM_Y):
            X, Y = d2f(col_x / 1000, y / 1000)
            ax.add_patch(patches.Rectangle((X, Y), 0.43186, 0.48488, facecolor=SLOT[6], alpha=0.18, edgecolor=SLOT[6],
                                           linewidth=0.8, zorder=4))
            ax.text(X + 0.216, Y + 0.242, f"SRAM\n512×8\n#{k}", ha="center", va="center", fontsize=5, color=INK, zorder=6,
                    linespacing=1.05)
        X, Yt = d2f(col_x / 1000 + (0.432 + 0.045 if name == "Main RAM" else -0.045), 1.80)
        ax.text(X, Yt, f"{name} 2 KB  (4 x 512 x 8)", rotation=90, ha="center", va="center", fontsize=5.2,
                color=SLOT[6], zorder=6)

    # pads, bond wires, pins
    pin_no = 1
    wire_len = []
    for side, names in SIDES:
        for i, n in enumerate(names):
            (x0, y0, w, hh), bond, lab, rot = pad_geom(side, i)
            k = kind(n)
            X0, Y0 = d2f(x0, y0)
            ax.add_patch(patches.Rectangle((X0, Y0), w, hh, facecolor=PADCOL[k], alpha=0.16 if k not in ("vss",) else 0.22,
                                           edgecolor=PADCOL[k], linewidth=0.7, zorder=5))
            lx, ly = d2f(*lab)
            ax.text(lx, ly, short(n), rotation=rot, ha="center", va="center",
                    fontsize=4.5 if len(short(n)) > 4 else 5.0, color=INK, zorder=6)
            # supply pads tie into the core ring
            if k in ("vdd", "vss"):
                if side == "W":
                    seg = ((0.376, PAD_C[9 - i]), (0.420, PAD_C[9 - i]))
                elif side == "E":
                    seg = ((DIE - 0.376, PAD_C[i]), (DIE - 0.420, PAD_C[i]))
                elif side == "S":
                    seg = ((PAD_C[i], 0.376), (PAD_C[i], 0.420))
                else:
                    seg = ((PAD_C[9 - i], DIE - 0.376), (PAD_C[9 - i], DIE - 0.420))
                (a, b), (c, d) = d2f(*seg[0]), d2f(*seg[1])
                ax.plot([a, c], [b, d], color=SLOT[7] if k == "vdd" else "#3a3936", linewidth=1.6, zorder=4,
                        solid_capstyle="butt")
            (px0, py0, pw, ph), pin_in, num_pos, ha = pin_geom(side, i)
            ax.add_patch(patches.Rectangle((px0, py0), pw, ph, facecolor="#d8d7d2", edgecolor=INK3, linewidth=0.6,
                                           zorder=3))
            ax.text(*num_pos, str(pin_no), fontsize=5.3, ha=ha, va="center", color=INK2,
                    fontweight="bold" if pin_no == 1 else "normal")
            bx, by = d2f(*bond)
            ax.plot([bx, pin_in[0]], [by, pin_in[1]], color=PADCOL[k], linewidth=0.55, zorder=4)
            ax.add_patch(patches.Circle((bx, by), 0.018, color=PADCOL[k], zorder=6))
            wire_len.append(math.hypot(bx - pin_in[0], by - pin_in[1]))
            pin_no += 1

    # group labels and numbering-direction arrows outside the package
    g = h + 0.42
    ax.text(-g - 0.05, 0, GROUP["W"], rotation=90, ha="center", va="center", fontsize=6.3, color=INK2)
    ax.text(g + 0.05, 0, GROUP["E"], rotation=90, ha="center", va="center", fontsize=6.3, color=INK2)
    ax.text(0, -g - 0.07, GROUP["S"], ha="center", va="center", fontsize=6.3, color=INK2)
    ax.text(0, g + 0.07, GROUP["N"], ha="center", va="center", fontsize=6.3, color=INK2)
    a = h + 0.62
    arr = dict(arrowstyle="-|>", color=INK, lw=1.1, mutation_scale=8)
    ax.annotate("", xy=(-a, -2.2), xytext=(-a, 2.2), arrowprops=arr)
    ax.annotate("", xy=(2.2, -a), xytext=(-2.2, -a), arrowprops=arr)
    ax.annotate("", xy=(a, 2.2), xytext=(a, -2.2), arrowprops=arr)
    ax.annotate("", xy=(-2.2, a), xytext=(2.2, a), arrowprops=arr)

    # legend
    items = [("Bidirectional I/O (bi_24t)", PADCOL["io"]), ("Input (in_c)", PADCOL["in"]),
             ("Clock input, Schmitt (in_s)", PADCOL["clk"]), ("VDD 5.0 V (dvdd)", PADCOL["vdd"]),
             ("VSS (dvss)", PADCOL["vss"])]
    ly = -h - 1.05
    lx = -h - 0.55
    for j, (t, col) in enumerate(items):
        xx = lx + (j % 3) * 2.45
        yy = ly - (j // 3) * 0.24
        ax.add_patch(patches.Rectangle((xx, yy - 0.07), 0.2, 0.14, facecolor=col, alpha=0.3, edgecolor=col, lw=0.7))
        ax.text(xx + 0.28, yy, t, fontsize=6, va="center", color=INK)
    yy = ly - 0.48
    ax.plot([lx, lx + 0.2], [yy, yy], color=SLOT[7], lw=1.6)
    ax.text(lx + 0.28, yy, "Core power ring, 25 µm, Metal3/Metal4", fontsize=6, va="center", color=INK)
    ax.plot([lx + 2.45, lx + 2.65], [yy, yy], color=INK, lw=0.7, linestyle=(0, (4, 2)))
    ax.text(lx + 2.73, yy, "Core boundary (2.718 mm)", fontsize=6, va="center", color=INK)
    ax.annotate("", xy=(lx + 5.1, yy), xytext=(lx + 4.9, yy), arrowprops=arr)
    ax.text(lx + 5.18, yy, "Pin numbering direction", fontsize=6, va="center", color=INK)
    ax.text(lx, yy - 0.3, f"To scale: package, exposed pad, die, pad pitch (265 µm), core ring and macros. Pad cells are "
            f"drawn 2.7× wider than their true 75 µm.\nBond wires: {min(wire_len):.2f}–{max(wire_len):.2f} mm. "
            f"Each die pad bonds to the QFN pin with the same number.", fontsize=5.6, va="top", color=INK2,
            linespacing=1.3)

    ax.set_title("POSIT-RV v3 SoC: pad ring, floorplan and QFN-40 bonding (top view)", fontsize=9.5, loc="left", pad=16)
    ax.text(0.0, 1.012, "GF180MCU · die 3.602 × 3.602 mm · 40 pads (28 signal, 6 VDD, 6 VSS) · "
            "QFN-40, 6 × 6 mm, 0.5 mm pitch", transform=ax.transAxes, fontsize=6.6, color=INK2)
    ax.set_xlim(-h - 0.9, h + 0.9)
    ax.set_ylim(-h - 2.05, h + 0.9)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(out + ".pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(out + ".png", bbox_inches="tight", pad_inches=0.03)
    print("wrote", out, f"wires {min(wire_len):.2f}-{max(wire_len):.2f} mm")


if __name__ == "__main__":
    main()
