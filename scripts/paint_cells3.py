#!/usr/bin/env python3
"""Colour every placed standard cell by its class under the layer render.

The tint shows the real cell types from the DEF placements: logic classes,
clock cells, flip-flops, tie cells, antenna diodes and the physical-only cells
(tap/filltie, endcap, filler, decap filler). Thin cell outlines appear in
close views. Metal and device layers are drawn on top, as in the classic render.

Usage:
  paint_cells3.py macro <macro.def.gz> <masks_dir> <out_dir> [views...]
  paint_cells3.py soc   <res_dir>      <masks_dir> <out_dir> [views...]
"""
import gzip
import json
import os
import re
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compose_showcase import CLASSIC_GF180, compose_classic, save  # noqa: E402

SC = "gf180mcu_fd_sc_mcu7t5v0__"
# class, colour, legend text (drawn bottom to top in this order)
CLASSES = [
    ("fill", "#64748b", "Filler"),
    ("fillcap", "#14b8a6", "Decap filler"),
    ("tap", "#a3e635", "Tap (well tie)"),
    ("endcap", "#f472b6", "Endcap"),
    ("comb", "#f97316", "Combinational logic"),
    ("buf", "#facc15", "Buffer / inverter / delay"),
    ("clk", "#dc2626", "Clock-tree buffer"),
    ("seq", "#a855f7", "Flip-flop"),
    ("tie", "#7dd3fc", "Tie cell"),
    ("ant", "#f8fafc", "Antenna diode"),
]
ALPHA = {"fill": 0.42, "fillcap": 0.42, "tap": 0.60, "endcap": 0.60, "comb": 0.36, "buf": 0.48,
         "clk": 0.50, "seq": 0.42, "tie": 0.55, "ant": 0.60}
COMP_RE = re.compile(r"^\s*-\s+(\S+)\s+(\S+)\s.*?\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)")


def cls_of(cell, inst=""):
    if not cell.startswith(SC):
        return None
    b = re.sub(r"_\d+$", "", cell[len(SC):])
    if b == "fill":
        return "fill"
    if b == "fillcap":
        return "fillcap"
    if b == "filltie":
        return "tap"
    if b == "endcap":
        return "endcap"
    if b == "antenna":
        return "ant"
    if b in ("tiel", "tieh"):
        return "tie"
    if b.startswith("dff") or b.startswith("latq") or b.startswith("sdff"):
        return "seq"
    leaf = inst.split(".")[-1].split("/")[-1]
    if b in ("clkbuf", "clkinv") and (leaf.startswith("clkbuf_") or leaf.startswith("clkload")):
        return "clk"                           # clock-tree cells named by CTS
    if b in ("clkbuf", "clkinv"):
        return "buf"                           # clkbuf used as a repair buffer
    if b in ("buf", "inv", "dlya", "dlyb", "dlyc", "dlyd"):
        return "buf"
    return "comb"


def read_def(path):
    op = gzip.open if path.endswith(".gz") else open
    units, comps, inside = 1000, [], False
    with op(path, "rt") as f:
        for ln in f:
            if ln.startswith("UNITS DISTANCE MICRONS"):
                units = int(ln.split()[3])
            elif ln.startswith("COMPONENTS"):
                inside = True
            elif ln.startswith("END COMPONENTS"):
                break
            elif inside:
                m = COMP_RE.match(ln)
                if m:
                    comps.append((m.group(1), m.group(2), int(m.group(3)) / units, int(m.group(4)) / units,
                                  m.group(5)))
    return comps


def lef_size(path):
    for ln in open(path):
        if ln.strip().startswith("SIZE"):
            p = ln.split()
            return float(p[1]), float(p[3])
    raise ValueError(path)


def place(x, y, w, h, X, Y, W, H, o):
    """local rect inside a macro of size W x H placed at (X, Y) with orientation o"""
    if o in ("FN", "S"):
        x = W - x - w
    if o in ("FS", "S"):
        y = H - y - h
    return X + x, Y + y


def collect(mode, src, sizes):
    rects = []                                     # (cls, x0, y0, w, h) in um
    if mode == "macro":
        for inst, cell, x, y, _ in read_def(src):
            c = cls_of(cell, inst)
            if c:
                w, h = sizes[cell]
                rects.append((c, x, y, w, h))
        return rects
    top = read_def(os.path.join(src, "soc3_chip_top.def.gz"))
    mdir = os.path.join(src, "macros")
    macros = {m: (read_def(os.path.join(mdir, m, f"{m}.def.gz")), lef_size(os.path.join(mdir, m, f"{m}.lef")))
              for m in os.listdir(mdir)}
    for inst, cell, x, y, o in top:
        if cell in macros:
            inner, (W, H) = macros[cell]
            for iname, ic, ix, iy, _ in inner:
                c = cls_of(ic, iname)
                if c:
                    w, h = sizes[ic]
                    gx, gy = place(ix, iy, w, h, x, y, W, H, o)
                    rects.append((c, gx, gy, w, h))
        else:
            c = cls_of(cell, inst)
            if c:
                w, h = sizes[cell]
                rects.append((c, x, y, w, h))
    return rects


def raster(rects, box, wpx, hpx, ss):
    """per-class coverage masks (uint8) and a cell-outline mask"""
    x0, y0, x1, y1 = box
    sx, sy = wpx * ss / (x1 - x0), hpx * ss / (y1 - y0)
    lab = Image.new("L", (wpx * ss, hpx * ss), 0)
    d = ImageDraw.Draw(lab)
    order = {c: i + 1 for i, (c, _, _) in enumerate(CLASSES)}
    ppu = wpx / (x1 - x0)
    outl = Image.new("L", (wpx, hpx), 0) if ppu >= 8 else None
    do = ImageDraw.Draw(outl) if outl else None
    lw = max(1, round(ppu * 0.05))
    counts = {}
    for c, x, y, w, h in rects:
        if x + w < x0 or x > x1 or y + h < y0 or y > y1:
            continue
        counts[c] = counts.get(c, 0) + 1
        a, b = (x - x0) * sx, (y1 - y - h) * sy
        d.rectangle([round(a), round(b), round(a + w * sx) - 1, round(b + h * sy) - 1], fill=order[c])
        if do:
            p, q = (x - x0) * ppu, (y1 - y - h) * ppu
            do.rectangle([round(p), round(q), round(p + w * ppu) - 1, round(q + h * ppu) - 1], outline=255, width=lw)
    arr = np.asarray(lab)
    masks = {}
    for c, i in order.items():
        m = Image.fromarray(((arr == i) * 255).astype(np.uint8))
        masks[c] = m.resize((wpx, hpx), Image.BOX) if ss > 1 else m
    return masks, outl, counts


def legend(width, counts, scale):
    items = [(col, f"{txt} ({counts[c]:,})") for c, col, txt in CLASSES if counts.get(c)]
    fs = max(14, int(22 * scale))
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", fs)
    except OSError:
        font = ImageFont.load_default()
    cols = 5 if width >= 3000 else (4 if width >= 2000 else 3)
    rows = (len(items) + cols - 1) // cols
    rh = int(fs * 1.9)
    im = Image.new("RGB", (width, rows * rh + int(fs * 1.2)), "#05070d")
    d = ImageDraw.Draw(im)
    cw = width // cols
    for k, (col, txt) in enumerate(items):
        x, y = (k % cols) * cw + fs, (k // cols) * rh + int(fs * 0.6)
        d.rectangle([x, y, x + int(fs * 1.4), y + fs], fill=col)
        d.text((x + int(fs * 1.9), y - int(fs * 0.12)), txt, fill="#e5e7eb", font=font)
    return im


def main():
    mode, src, masks_dir, out = sys.argv[1:5]
    only = sys.argv[5:] or None
    os.makedirs(out, exist_ok=True)
    sizes = json.load(open(os.environ.get("CELL_SIZES", "/home/claude/work/v3/fin/res/cell_sizes.json")))
    rects = collect(mode, src, sizes)
    meta = json.load(open(os.path.join(masks_dir, "views.json")))
    for vname, v in meta["views"].items():
        if only and vname not in only:
            continue
        vdir = os.path.join(masks_dir, vname)
        if not os.path.isdir(vdir):
            continue
        w, h = v["width"], v["height"]
        ss = 1 if w / (v["box_um"][2] - v["box_um"][0]) >= 8 else 2
        cmasks, outl, counts = raster(rects, v["box_um"], w, h, ss)
        layers = [l for l in v["layers"] if not l.endswith("_fill") and os.path.exists(os.path.join(vdir, l + ".png"))]
        with tempfile.TemporaryDirectory() as td:
            for l in layers:
                os.symlink(os.path.abspath(os.path.join(vdir, l + ".png")), os.path.join(td, l + ".png"))
            ppu = w / (v["box_um"][2] - v["box_um"][0])
            tint = []
            for c, col, _ in CLASSES:
                cmasks[c].save(os.path.join(td, f"cls_{c}.png"))
                tint.append((f"cls_{c}", col, ALPHA[c] * (1.0 if ppu >= 15 else 1.25), 0.0, "solid"))
            have = [f"cls_{c}" for c, _, _ in CLASSES] + layers
            # close views: tint under the devices; coarse views: above Metal1, which covers the rows
            style = list(tint) if ppu >= 15 else []
            for row in CLASSIC_GF180:
                style.append(row)
                if row[0] == "m1" and ppu < 15:
                    style.extend(tint)
                if row[0] == "poly" and outl is not None:
                    outl.save(os.path.join(td, "cellbox.png"))
                    style.append(("cellbox", "#cbd5e1", 0.55, 0.0, "solid"))
                    have.append("cellbox")
            close = vname == "cells"
            arr = compose_classic(td, have, style, occlude=0.2 if close else None, lwfrac=0.45 if close else 0.25)
        img = Image.fromarray((arr * 255 + 0.5).astype(np.uint8))
        lg = legend(w, counts, w / 2048)
        full = Image.new("RGB", (w, h + lg.height), "#05070d")
        full.paste(img, (0, 0))
        full.paste(lg, (0, h))
        save(np.asarray(full, dtype=np.float32) / 255.0, os.path.join(out, f"{vname}_cells_coloured.png"))
        print("wrote", vname, w, h, "ss", ss, {k: counts[k] for k in counts})


if __name__ == "__main__":
    main()
