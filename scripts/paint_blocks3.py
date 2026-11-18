#!/usr/bin/env python3
"""Colour-by-block and labelled renders of the v3 SoC.

Inputs: the block map from blockmap3.py, the classic layer render of a view
and that view's box (views.json from render_masks.py).
Outputs:
  --colour   every standard cell painted with its block colour over the
             layer render, foundry SRAMs tinted, legend panel on the right
  --labels   white bold boxes naming each hard macro and the main sub-blocks
             (drawn over --label-base, the colour image by default)
Usage: paint_blocks3.py --map blockmap.json --image die.jpg --views views.json
        --view die --colour die_blocks.png --labels die_blocks_labelled.png
"""
import argparse
import collections
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_B = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"

# group -> (title, [(label, colour)])
PALETTE = [
    ("cpu_core", "RV32IMC CPU CORE", [
        ("Register file", "#3d7bff"),
        ("ALU logic", "#ff2bd6"),
        ("ALU adder", "#ff7ae6"),
        ("Barrel shifter", "#b04dff"),
        ("ALU comparator", "#ff9ad9"),
        ("Multiplier", "#00d9ff"),
        ("Divider", "#00ffa6"),
        ("Instruction decoder", "#7dff3d"),
        ("PC / fetch", "#ffe23d"),
        ("Bus interface", "#ff9a3d"),
        ("Operand / writeback", "#2ec5ff"),
        ("Perf counters", "#8fa8ff"),
        ("Interrupt unit", "#ff5b5b"),
        ("Control FSM", "#8d6e63"),
    ]),
    ("dsp_mac", "DSP ARRAY · 4 × MAC", [
        ("Multiplier array", "#ff6a00"),
        ("Accumulator", "#ffc400"),
        ("Operand regs", "#ff9e80"),
        ("Control / read mux", "#c45a2b"),
    ]),
    ("simd_alu", "SIMD ALU", [
        ("Lane 0", "#00e676"),
        ("Lane 1", "#33ffcc"),
        ("Lane 2", "#9cff57"),
        ("Lane 3", "#00bfa5"),
        ("SAD adder tree", "#d4ff00"),
        ("Popcount / CLZ", "#5ce1e6"),
        ("Operand regs", "#a5d6a7"),
        ("Result select", "#2e9e6b"),
    ]),
    ("spimemio", "SPI FLASH CONTROLLER", [
        ("SPI shift engine", "#ff2e93"),
        ("XIP read buffer", "#ff8cc6"),
        ("XIP control", "#c2185b"),
        ("Flash config", "#f48fb1"),
    ]),
    ("simpleuart", "UART", [
        ("UART RX", "#ff1744"),
        ("UART TX", "#ff8a65"),
        ("Baud generator", "#ffd180"),
    ]),
    ("posit_decoder_32_2", "POSIT<32,2> DECODER · MY WORK", [
        ("Regime shifter", "#fff200"),
        ("Regime value", "#ffffff"),
        ("Exponent / fraction", "#ffb300"),
        ("Sign / NaR", "#ff4081"),
    ]),
    ("top", "TOP-LEVEL GLUE", [
        ("Bus read mux", "#e0e0e0"),
        ("Posit I/O regs", "#fff59d"),
        ("SRAM interface", "#90caf9"),
        ("GPIO", "#b39ddb"),
        ("Reset sync", "#ef9a9a"),
        ("Long-wire repeaters", "#80deea"),
        ("Hold-fix delay cells", "#ffab91"),
        ("Pad interface", "#78909c"),
    ]),
]
SRAM_COL = "#4fc3f7"
CLOCK_COL = "#ffffff"

MACRO_TEXT = {
    "cpu_core": ("RV32IMC CPU CORE", "PicoRV32 · hard macro"),
    "dsp_mac": ("DSP {n}", "16×16 MAC · 40-bit acc"),
    "simd_alu": ("SIMD ALU", "4 × 8-bit lanes · SAD"),
    "spimemio": ("SPI FLASH XIP", "QSPI controller"),
    "simpleuart": ("UART", "RX / TX / baud"),
    "posit_decoder_32_2": ("POSIT<32,2> DECODER", "MY WORK"),
}


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--views", required=True)
    ap.add_argument("--view", default="die")
    ap.add_argument("--colour")
    ap.add_argument("--labels")
    ap.add_argument("--label-base", choices=["colour", "layout"], default="colour")
    ap.add_argument("--legend", action="store_true")
    ap.add_argument("--sub", action="store_true", help="label sub-blocks inside macros")
    ap.add_argument("--rings", action="store_true", help="label pad ring and core ring")
    ap.add_argument("--core", nargs=4, type=float, default=None)
    ap.add_argument("--sub-min-px", type=float, default=900, help="label sub-blocks of macros at least this wide")
    ap.add_argument("--posit-label", choices=["above", "below", "mid", "above-right"], default="above-right")
    ap.add_argument("--sub-all", action="store_true", help="box every sub-block, not only the headline ones")
    args = ap.parse_args()

    bm = json.load(open(args.map))
    vx0, vy0, vx1, vy1 = json.load(open(args.views))["views"][args.view]["box_um"]
    base = Image.open(args.image).convert("RGB")
    W, H = base.size
    sx, sy = W / (vx1 - vx0), H / (vy1 - vy0)

    def px(x, y):
        return (x - vx0) * sx, (vy1 - y) * sy

    labels = []
    colours = [np.zeros(3, np.float32)]
    lid = {}
    for g, _t, items in PALETTE:
        for lab, col in items:
            lid[(g, lab)] = len(colours)
            colours.append(hex2rgb(col))
            labels.append((g, lab))
    clock_id = len(colours)
    colours.append(hex2rgb(CLOCK_COL))
    colours = np.stack(colours)

    # Label raster
    ras = np.zeros((H, W), np.int16)
    for x0, y0, x1, y1, g, lab in bm["rects"]:
        k = clock_id if lab == "Clock tree" else lid.get((g, lab))
        if not k:
            continue
        a, b = px(x0, y1)
        c, d = px(x1, y0)
        i0, i1 = max(0, int(a)), min(W, int(np.ceil(c)))
        j0, j1 = max(0, int(b)), min(H, int(np.ceil(d)))
        if i1 > i0 and j1 > j0:
            ras[j0:j1, i0:i1] = k

    img = np.asarray(base, np.float32)
    gray = img.mean(axis=2, keepdims=True) / 255.0
    out = img * 0.42
    sram_mask = np.zeros((H, W), bool)
    for inst, cell, x0, y0, x1, y1 in bm["macros"]:
        if "sram" in cell:
            a, b = px(x0, y1)
            c, d = px(x1, y0)
            sram_mask[max(0, int(b)):min(H, int(d)), max(0, int(a)):min(W, int(c))] = True
    sc = hex2rgb(SRAM_COL)
    out[sram_mask] = img[sram_mask] * 0.55 + sc * (0.18 + 0.55 * gray[sram_mask])
    m = ras > 0
    col = colours[ras[m]]
    out[m] = col * (0.38 + 0.80 * gray[m]) + img[m] * 0.10
    colour_img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    # Macro outlines in their family colour
    dr = ImageDraw.Draw(colour_img)
    fam = {g: hex2rgb(items[0][1]) for g, _t, items in PALETTE}
    lw = max(2, int(3 * W / 4096))
    for inst, cell, x0, y0, x1, y1 in bm["macros"]:
        a, b = px(x0, y1)
        c, d = px(x1, y0)
        cc = tuple(int(v) for v in (sc if "sram" in cell else fam.get(cell, sc)))
        dr.rectangle([a, b, c, d], outline=cc, width=lw)

    final_colour = colour_img
    if args.legend:
        final_colour = add_legend(colour_img, bm, W, H)
    if args.colour:
        save(final_colour, args.colour)

    if args.labels:
        lbase = colour_img if args.label_base == "colour" else base
        lab_img = draw_labels(lbase.copy(), bm, px, W, args)
        if args.legend:
            lab_img = add_legend(lab_img, bm, W, H)
        save(lab_img, args.labels)


def save(im, path):
    if path.endswith(".jpg"):
        im.save(path, quality=93)
    else:
        im.save(path, optimize=True)
    print("wrote", path, im.size)


def add_legend(img, bm, W, H):
    counts = collections.Counter()
    for g, lab, n in bm["counts"]:
        counts[(g, lab)] += n
    pw = int(W * 0.30)
    canvas = Image.new("RGB", (W + pw, H), (8, 9, 12))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    s = H / 4096
    fh = ImageFont.truetype(FONT_B, int(58 * s))
    fg = ImageFont.truetype(FONT_B, int(40 * s))
    fi = ImageFont.truetype(FONT_R, int(34 * s))
    x = W + int(70 * s)
    y = int(90 * s)
    d.text((x, y), "FUNCTIONAL BLOCKS", font=fh, fill=(255, 255, 255))
    y += int(100 * s)
    d.text((x, y), "colour = block that owns each standard cell", font=fi, fill=(170, 175, 185))
    y += int(90 * s)
    sw = int(40 * s)
    for g, title, items in PALETTE:
        tot = sum(counts[(g, lab)] for lab, _ in items)
        if tot == 0:
            continue
        d.text((x, y), title, font=fg, fill=(255, 255, 255))
        y += int(62 * s)
        for lab, col in items:
            n = counts[(g, lab)]
            if n == 0:
                continue
            d.rectangle([x, y + int(6 * s), x + sw, y + int(6 * s) + sw], fill=col)
            d.text((x + sw + int(24 * s), y), lab, font=fi, fill=(225, 228, 235))
            t = f"{n:,}"
            d.text((W + pw - int(70 * s) - d.textlength(t, font=fi), y), t, font=fi, fill=(150, 155, 165))
            y += int(52 * s)
        y += int(34 * s)
    nclk = sum(n for (g, lab), n in counts.items() if lab == "Clock tree")
    if nclk:
        d.rectangle([x, y + int(6 * s), x + sw, y + int(6 * s) + sw], fill=CLOCK_COL)
        d.text((x + sw + int(24 * s), y), "Clock tree buffers", font=fi, fill=(225, 228, 235))
        t = f"{nclk:,}"
        d.text((W + pw - int(70 * s) - d.textlength(t, font=fi), y), t, font=fi, fill=(150, 155, 165))
        y += int(52 * s)
    d.rectangle([x, y + int(6 * s), x + sw, y + int(6 * s) + sw], fill=SRAM_COL)
    d.text((x + sw + int(24 * s), y), "Foundry SRAM 512×8 (8 banks)", font=fi, fill=(225, 228, 235))
    y += int(70 * s)
    d.text((x, y), "cell counts include all instances", font=fi, fill=(120, 125, 135))
    return canvas


BOX_MERGE = {  # labelled view: sub-blocks drawn as one box
    "ALU adder": "ALU",
    "Barrel shifter": "ALU",
    "ALU comparator": "ALU",
    "ALU logic": "ALU",
}
# Die-level view: only the headline sub-blocks get a box
SUB_KEY = {"Register file", "Multiplier", "Divider", "ALU", "Instruction decoder"}


def sub_regions(bm, inst_box, group, nb=22):
    """Largest plurality region of each label inside one macro instance."""
    x0, y0, x1, y1 = inst_box
    bw, bh = (x1 - x0) / nb, (y1 - y0) / nb
    cnt = collections.defaultdict(lambda: np.zeros((nb, nb)))
    for rx0, ry0, rx1, ry1, g, lab in bm["rects"]:
        if g != group:
            continue
        cx, cy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
        if not (x0 <= cx < x1 and y0 <= cy < y1):
            continue
        cnt[BOX_MERGE.get(lab, lab)][int((cy - y0) / bh), int((cx - x0) / bw)] += 1
    if not cnt:
        return {}
    labs = list(cnt)
    st = np.stack([cnt[k] for k in labs])
    tot = st.sum(0)
    win = st.argmax(0)
    out = {}
    for k, lab in enumerate(labs):
        mask = (win == k) & (tot >= 4)
        seen = np.zeros_like(mask)
        best, bestn = None, 0
        for j in range(nb):
            for i in range(nb):
                if mask[j, i] and not seen[j, i]:
                    comp, stack = [], [(j, i)]
                    seen[j, i] = True
                    while stack:
                        a, b = stack.pop()
                        comp.append((a, b))
                        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            na, nb_ = a + da, b + db
                            if 0 <= na < nb and 0 <= nb_ < nb and mask[na, nb_] and not seen[na, nb_]:
                                seen[na, nb_] = True
                                stack.append((na, nb_))
                    n = sum(st[k][a, b] for a, b in comp)
                    if n > bestn:
                        best, bestn = comp, n
        if best and len(best) >= 3:
            js = [a for a, _ in best]
            is_ = [b for _, b in best]
            out[lab] = (x0 + min(is_) * bw, y0 + min(js) * bh, x0 + (max(is_) + 1) * bw,
                        y0 + (max(js) + 1) * bh, int(st[k].sum()))
    return out


def draw_labels(img, bm, px, W, args):
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    s = W / 4096

    def rect(x0, y0, x1, y1):
        a, b = px(x0, y1)
        c, dd = px(x1, y0)
        return [a, b, c, dd]

    def box(r, text, sub=None, width=None, size=1.0, where="mid", fill_alpha=165):
        width = width or max(3, int(6 * s))
        x0, y0, x1, y1 = r
        fb = ImageFont.truetype(FONT_B, max(14, int(44 * s * size)))
        fs = ImageFont.truetype(FONT_B, max(12, int(30 * s * size)))
        d.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 210), width=width + max(2, int(4 * s)))
        d.rectangle([x0, y0, x1, y1], outline=(255, 255, 255, 255), width=width)
        lines = [(text, fb)] + ([(sub, fs)] if sub else [])
        tw = max(d.textlength(t, font=f) for t, f in lines)
        th = sum(f.getbbox("Ag")[3] + int(4 * s) for _, f in lines)
        pad = max(4, int(10 * s * size))
        cx = (x0 + x1) / 2
        if where == "above-right":
            cx = max(cx, x0 + tw / 2 + pad)
            where = "above"
        if where == "top":
            ty = y0 + width + pad
        elif where == "above":
            ty = y0 - th - pad - width
        elif where == "below":
            ty = y1 + width + 2 * pad
        else:
            ty = (y0 + y1) / 2 - th / 2
        d.rounded_rectangle([cx - tw / 2 - pad, ty - pad, cx + tw / 2 + pad, ty + th + pad],
                            radius=pad, fill=(0, 0, 0, fill_alpha))
        y = ty
        for t, f in lines:
            d.text((cx - d.textlength(t, font=f) / 2, y), t, font=f, fill=(255, 255, 255, 255))
            y += f.getbbox("Ag")[3] + int(4 * s)

    dsp_no = {}
    for inst, cell, x0, y0, x1, y1 in sorted(bm["macros"]):
        r = rect(x0, y0, x1, y1)
        if r[2] < 0 or r[3] < 0 or r[0] > img.size[0] or r[1] > img.size[1]:
            continue
        if "sram" in cell:
            bank = inst.split(".")[-1].replace("sram", "")
            kind = "SCRATCH" if "scratch" in inst else "MAIN RAM"
            box(r, f"SRAM {kind} · BANK {bank}", "512×8 foundry macro", size=0.9)
            continue
        if cell not in MACRO_TEXT:
            continue
        t, sub = MACRO_TEXT[cell]
        if cell == "dsp_mac":
            n = inst.split("u_dsp")[-1]
            t = t.format(n=n)
        if cell == "posit_decoder_32_2":
            box(r, t, "MY WORK · hard macro", width=max(5, int(11 * s)), size=0.95, where=args.posit_label,
                fill_alpha=225)
            continue
        if args.sub and (r[2] - r[0]) >= args.sub_min_px:
            regs = sub_regions(bm, (x0, y0, x1, y1), cell)
            for lab, (a, b, c, e, n) in sorted(regs.items(), key=lambda kv: -kv[1][4]):
                if not args.sub_all and lab not in SUB_KEY:
                    continue
                if (c - a) < (x1 - x0) * 0.12 or (e - b) < (y1 - y0) * 0.12:
                    continue
                box(rect(a, b, c, e), lab.upper(), f"{n:,} cells", width=max(2, int(3 * s)), size=0.62)
            box(r, t, sub, where="top", size=1.05)
        else:
            box(r, t, sub, size=1.05)

    if args.rings and args.core:
        die = bm["die"]
        box(rect(die[0] + 26, die[1] + 26, die[2] - 26, die[3] - 26), "I/O PAD RING · 40 PADS",
            where="top", size=1.1)
        c0, c1, c2, c3 = args.core
        box(rect(c0 - 47, c1 - 47, c2 + 47, c3 + 47), "CORE POWER RING", where="top", size=0.9)
    return Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")


if __name__ == "__main__":
    main()
