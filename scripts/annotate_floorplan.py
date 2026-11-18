#!/usr/bin/env python3
"""Overlay labelled boxes (white, bold) on SoC layout renders.

Hard macros, pad ring and power ring come from their exact coordinates
(DEF / flow config). Standard-cell blocks (ALU, register file, ...) come from
cell placements in the final DEF, grouped by classify_cells.py: each box is
the extent of the largest connected region of a density grid in which that
block holds the plurality of cells.

Usage: annotate_floorplan.py --def chip.def --labels labels.json
        --views views.json --image die.png --view die --out die_annotated.png
"""
import argparse
import collections
import gzip
import json
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

BLOCK_TEXT = {
    "ALU": "ALU",
    "Register file": "REGISTER FILE 32×32",
    "Multiplier": "MULTIPLIER (RV32M)",
    "Divider": "DIVIDER (RV32M)",
    "CPU control": "CPU FETCH / DECODE / CONTROL",
    "SPI flash controller": "SPI FLASH CONTROLLER",
    "UART": "UART",
    "Bus peripherals": "BUS · GPIO · POSIT REGS",
}


def read_def(path):
    op = gzip.open if path.endswith(".gz") else open
    txt = op(path, "rt").read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    comps = {}
    sec = txt[txt.index("COMPONENTS"):txt.index("END COMPONENTS")]
    for m in re.finditer(r"-\s+(\S+)\s+(\S+).*?\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)", sec, re.S):
        name = m.group(1).replace("\\", "")
        comps[name] = (m.group(2), int(m.group(3)) / units, int(m.group(4)) / units, m.group(5))
    return comps


def block_regions(comps, labels, core, nbins=48):
    x0, y0, x1, y1 = core
    bw, bh = (x1 - x0) / nbins, (y1 - y0) / nbins
    counts = collections.defaultdict(lambda: np.zeros((nbins, nbins)))
    total = np.zeros((nbins, nbins))
    for name, lab in labels.items():
        c = comps.get(name)
        if not c:
            continue
        i = int((c[1] - x0) / bw)
        j = int((c[2] - y0) / bh)
        if 0 <= i < nbins and 0 <= j < nbins:
            counts[lab][j, i] += 1
            total[j, i] += 1
    stack = np.stack([counts[k] for k in BLOCK_TEXT])
    winner = np.argmax(stack, axis=0)
    regions = {}
    for k, lab in enumerate(BLOCK_TEXT):
        mask = (winner == k) & (total >= 3) & (stack[k] >= 2)
        # largest 4-connected component
        seen = np.zeros_like(mask)
        best = []
        for j in range(nbins):
            for i in range(nbins):
                if mask[j, i] and not seen[j, i]:
                    comp, st = [], [(j, i)]
                    seen[j, i] = True
                    while st:
                        a, b = st.pop()
                        comp.append((a, b))
                        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            na, nb = a + da, b + db
                            if 0 <= na < nbins and 0 <= nb < nbins and mask[na, nb] and not seen[na, nb]:
                                seen[na, nb] = True
                                st.append((na, nb))
                    if sum(stack[k][a, b] for a, b in comp) > sum(stack[k][a, b] for a, b in best):
                        best = comp
        if best:
            js = [a for a, _ in best]
            is_ = [b for _, b in best]
            regions[lab] = (x0 + min(is_) * bw, y0 + min(js) * bh,
                            x0 + (max(is_) + 1) * bw, y0 + (max(js) + 1) * bh,
                            int(sum(stack[k][a, b] for a, b in best)), int(stack[k].sum()))
    return regions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--def", dest="defp", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--views", required=True)
    ap.add_argument("--view", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--core", nargs=4, type=float, default=[442, 442, 1950, 1950])
    args = ap.parse_args()

    comps = read_def(args.defp)
    labels = json.load(open(args.labels))
    view = json.load(open(args.views))["views"][args.view]
    vx0, vy0, vx1, vy1 = view["box_um"]
    img = Image.open(args.image).convert("RGB")
    W, H = img.size

    def px(x, y):
        return ((x - vx0) / (vx1 - vx0) * W, (1 - (y - vy0) / (vy1 - vy0)) * H)

    def rect(x0, y0, x1, y1):
        a, b = px(x0, y1)
        c, d = px(x1, y0)
        return [a, b, c, d]

    s = W / 4096 * (2392 / (vx1 - vx0))           # scale relative to full-die view
    lw = max(3, int(7 * W / 4096))
    f_big = ImageFont.truetype(FONT, max(18, int(54 * W / 4096 * min(2.2, s))))
    f_small = ImageFont.truetype(FONT, max(14, int(36 * W / 4096 * min(2.2, s))))

    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)

    def box(r, text, sub=None, width=lw, where="top"):
        x0, y0, x1, y1 = r
        if x1 < 0 or y1 < 0 or x0 > W or y0 > H:
            return
        d.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 200), width=width + 4)
        d.rectangle([x0, y0, x1, y1], outline=(255, 255, 255, 255), width=width)
        lines = [(text, f_big)] + ([(sub, f_small)] if sub else [])
        tw = max(d.textlength(t, font=f) for t, f in lines)
        th = sum(f.getbbox("Ag")[3] + 6 for _, f in lines)
        pad = int(10 * W / 4096) + 4
        cx = (x0 + x1) / 2
        ty = y0 + width + pad if where == "top" else (y0 + y1) / 2 - th / 2
        bx0, by0 = cx - tw / 2 - pad, ty - pad
        d.rounded_rectangle([bx0, by0, cx + tw / 2 + pad, ty + th + pad], radius=pad,
                            fill=(0, 0, 0, 175))
        y = ty
        for t, f in lines:
            d.text((cx - d.textlength(t, font=f) / 2, y), t, font=f, fill=(255, 255, 255, 255))
            y += f.getbbox("Ag")[3] + 6

    # Hard macros (exact positions from the DEF)
    for name, (cell, x, y, orient) in comps.items():
        if "sram512x8" in cell:
            w_, h_ = 431.86, 484.88
            bank = name.rsplit("sram", 1)[-1]
            box(rect(x, y, x + w_, y + h_), f"SRAM BANK {bank}", "512×8 foundry hard macro", where="mid")
        elif cell == "posit_decoder_32_2":
            box(rect(x, y, x + 200, y + 200), "POSIT‹32,2› DECODER", "MY WORK · hard macro",
                width=lw * 2, where="mid")

    # Standard-cell blocks
    regs = block_regions(comps, labels, args.core)
    for lab, (x0, y0, x1, y1, n_in, n_all) in regs.items():
        if (x1 - x0) < 25 or (y1 - y0) < 25:
            continue
        box(rect(x0, y0, x1, y1), BLOCK_TEXT[lab], f"{n_all:,} cells", where="mid")
        print(f"{lab:22s} box {x0:7.1f},{y0:7.1f} - {x1:7.1f},{y1:7.1f}  ({n_in}/{n_all} cells inside)")

    # Rings (die-level views only)
    if args.view == "die":
        die = 2392
        box(rect(26, 26, die - 26, die - 26), "I/O PAD RING · 40 PADS", where="top")
        box(rect(395, 395, 1997, 1997), "CORE POWER RING", where="top")

    out = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    out.save(args.out, quality=94) if args.out.endswith(".jpg") else out.save(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
