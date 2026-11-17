#!/usr/bin/env python3
"""Generate die-art corner badges (text in Metal1..Metal5) for GF180MCU.

Each badge becomes a hard macro with GDS, LEF, Liberty and blackbox Verilog
views, following the footprint of the wafer.space logo macro (143.25 um
square, 0.75 um pixels). Only Pillow is required.

Design rules applied to the bitmap before export:
  * strokes and gaps are at least MIN_FEATURE pixels (opening/closing),
  * no diagonal-only pixel contacts (these cause notch/spacing violations).
"""
import argparse
import math
import os
import struct

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PIXEL_UM = 0.75
SIZE_PX = 191                      # 191 * 0.75 = 143.25 um
METAL_LAYERS = [(34, 0), (36, 0), (42, 0), (46, 0), (81, 0)]  # Metal1..Metal5
BOUNDARY_LAYERS = [(0, 0), (152, 5)]
LEF_LAYERS = ["Metal1", "Metal2", "Metal3", "Metal4", "Metal5"]

BADGES = {
    "dieart_tl": [("RISC-V", 38), ("+ POSIT", 32), ("SOC", 30)],
    "dieart_tr": [("VLSI", 46), ("DESIGN LAB", 24), ("CSIR-CEERI", 24)],
    "dieart_bl": [("GF180", 46), ("MCU", 46)],
    "dieart_br": [("2026", 58), ("RV32IMC", 28)],
}
SUPERSAMPLE = 4
TRACKING_PX = 1.5


# --------------------------------------------------------------------------
# Bitmap generation
# --------------------------------------------------------------------------
def render_badge(lines, font_path):
    """Render at SUPERSAMPLE x resolution, then downsample for smooth glyphs."""
    ss = SUPERSAMPLE
    n = SIZE_PX * ss
    img = Image.new("L", (n, n), 0)
    draw = ImageDraw.Draw(img)
    # Frame: two nested rectangles give a clean "chip badge" look.
    draw.rectangle([0, 0, n - 1, n - 1], outline=255, width=5 * ss)
    draw.rectangle([10 * ss, 10 * ss, n - 1 - 10 * ss, n - 1 - 10 * ss], outline=255, width=3 * ss)

    fonts = [ImageFont.truetype(font_path, size * ss) for _, size in lines]
    track = TRACKING_PX * ss

    def text_box(text, f):
        x, top, bottom = 0, None, None
        for ch in text:
            b = draw.textbbox((x, 0), ch, font=f)
            top = b[1] if top is None else min(top, b[1])
            bottom = b[3] if bottom is None else max(bottom, b[3])
            x += draw.textlength(ch, font=f) + track
        return (0, top, x - track, bottom)

    def draw_tracked(x, y, text, f):
        for ch in text:
            draw.text((x, y), ch, fill=255, font=f)
            x += draw.textlength(ch, font=f) + track

    boxes = [text_box(text, f) for (text, _), f in zip(lines, fonts)]
    heights = [b[3] - b[1] for b in boxes]
    gap = 10 * ss
    total = sum(heights) + gap * (len(lines) - 1)
    y = (n - total) / 2
    for (text, _), f, b, h in zip(lines, fonts, boxes, heights):
        w = b[2] - b[0]
        if w > n - 34 * ss:
            raise SystemExit(f"Text '{text}' is too wide ({w // ss}px)")
        draw_tracked((n - w) / 2 - b[0], y - b[1], text, f)
        y += h + gap
    return img.resize((SIZE_PX, SIZE_PX), Image.LANCZOS)


def clean_bitmap(img, min_feature):
    bw = img.point(lambda v: 255 if v >= 128 else 0)
    k = min_feature if min_feature % 2 == 1 else min_feature - 1
    # Opening removes slivers thinner than min_feature; closing fills narrow gaps.
    bw = bw.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    bw = bw.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    px = [[1 if bw.getpixel((x, y)) else 0 for x in range(SIZE_PX)] for y in range(SIZE_PX)]
    # Remove diagonal-only contacts by filling one orthogonal neighbour.
    changed = True
    while changed:
        changed = False
        for y in range(SIZE_PX - 1):
            for x in range(SIZE_PX - 1):
                a, b, c, d = px[y][x], px[y][x + 1], px[y + 1][x], px[y + 1][x + 1]
                if a and d and not b and not c:
                    px[y][x + 1] = 1
                    changed = True
                elif b and c and not a and not d:
                    px[y][x] = 1
                    changed = True
    return px


def min_run(px):
    """Smallest horizontal/vertical run of set pixels and of gaps between them."""
    def runs(seq):
        out_set, out_gap, cur, val, seen_set = [], [], 0, None, False
        for v in seq + [None]:
            if v == val:
                cur += 1
                continue
            if val == 1:
                out_set.append(cur)
                seen_set = True
            elif val == 0 and seen_set and v == 1:
                out_gap.append(cur)
            val, cur = v, 1
        return out_set, out_gap
    s_all, g_all = [], []
    for row in px:
        s, g = runs(row)
        s_all += s
        g_all += g
    for x in range(SIZE_PX):
        s, g = runs([px[y][x] for y in range(SIZE_PX)])
        s_all += s
        g_all += g
    return min(s_all), (min(g_all) if g_all else None)


def to_rects(px):
    """Merge pixels into rectangles: horizontal runs, then stack equal runs."""
    open_runs = {}
    rects = []
    for y in range(SIZE_PX):
        row = px[SIZE_PX - 1 - y]  # GDS y grows upward
        runs = []
        x = 0
        while x < SIZE_PX:
            if row[x]:
                x0 = x
                while x < SIZE_PX and row[x]:
                    x += 1
                runs.append((x0, x))
            else:
                x += 1
        new_open = {}
        for r in runs:
            if r in open_runs:
                new_open[r] = open_runs.pop(r)
            else:
                new_open[r] = y
        for (x0, x1), y0 in open_runs.items():
            rects.append((x0, y0, x1, y))
        open_runs = new_open
    for (x0, x1), y0 in open_runs.items():
        rects.append((x0, y0, x1, SIZE_PX))
    return rects


# --------------------------------------------------------------------------
# Minimal GDSII writer
# --------------------------------------------------------------------------
def _real8(v):
    if v == 0:
        return b"\x00" * 8
    sign = 0x80 if v < 0 else 0
    v = abs(v)
    exp = 64
    while v >= 1:
        v /= 16.0
        exp += 1
    while v < 1 / 16.0:
        v *= 16.0
        exp -= 1
    mant = int(round(v * (1 << 56)))
    return struct.pack(">B", sign | exp) + mant.to_bytes(7, "big")


def _rec(rtype, dtype, data=b""):
    return struct.pack(">HBB", 4 + len(data), rtype, dtype) + data


def _str(rtype, s):
    b = s.encode("ascii")
    if len(b) % 2:
        b += b"\x00"
    return _rec(rtype, 0x06, b)


def write_gds(path, cell, rects_um):
    ts = struct.pack(">12h", 2026, 11, 17, 0, 0, 0, 2026, 11, 17, 0, 0, 0)
    out = [_rec(0x00, 0x02, struct.pack(">h", 600)), _rec(0x01, 0x02, ts),
           _str(0x02, "DIEART"), _rec(0x03, 0x05, _real8(1e-3) + _real8(1e-9)),
           _rec(0x05, 0x02, ts), _str(0x06, cell)]
    for (layer, dt), (x0, y0, x1, y1) in rects_um:
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        xy = b"".join(struct.pack(">ii", int(round(px * 1000)), int(round(py * 1000))) for px, py in pts)
        out += [_rec(0x08, 0x00), _rec(0x0D, 0x02, struct.pack(">h", layer)),
                _rec(0x0E, 0x02, struct.pack(">h", dt)), _rec(0x10, 0x03, xy), _rec(0x11, 0x00)]
    out += [_rec(0x07, 0x00), _rec(0x04, 0x00)]
    with open(path, "wb") as f:
        f.write(b"".join(out))


# --------------------------------------------------------------------------
# Abstract views
# --------------------------------------------------------------------------
def write_views(root, cell):
    size = SIZE_PX * PIXEL_UM
    for sub in ("gds", "lef", "lib", "vh", "png"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    obs = "".join(f"      LAYER {l} ;\n        RECT 0.0 0.0 {size:.2f} {size:.2f} ;\n" for l in LEF_LAYERS)
    with open(os.path.join(root, "lef", f"{cell}.lef"), "w") as f:
        f.write(f"""VERSION 5.7 ;
  NOWIREEXTENSIONATPIN ON ;
  DIVIDERCHAR "/" ;
  BUSBITCHARS "[]" ;
MACRO {cell}
  CLASS BLOCK ;
  FOREIGN {cell} ;
  ORIGIN 0.000 0.000 ;
  SIZE {size:.2f} BY {size:.2f} ;
  OBS
{obs}  END
END {cell}
END LIBRARY
""")
    with open(os.path.join(root, "lib", f"{cell}.lib"), "w") as f:
        f.write(f"""library ({cell}) {{
  input_threshold_pct_fall: 50.0;
  input_threshold_pct_rise: 50.0;
  output_threshold_pct_fall: 50.0;
  output_threshold_pct_rise: 50.0;
  slew_lower_threshold_pct_fall: 20.0;
  slew_lower_threshold_pct_rise: 20.0;
  slew_upper_threshold_pct_fall: 80.0;
  slew_upper_threshold_pct_rise: 80.0;
  cell ({cell}) {{
  }}
}}
""")
    with open(os.path.join(root, "vh", f"{cell}.v"), "w") as f:
        f.write(f"(* blackbox *)\nmodule {cell};\nendmodule\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ip/dieart")
    ap.add_argument("--font", default="/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
    ap.add_argument("--min-feature", type=int, default=3, help="pixels (3 px = 2.25 um)")
    args = ap.parse_args()
    for cell, lines in BADGES.items():
        px = clean_bitmap(render_badge(lines, args.font), args.min_feature)
        ms, mg = min_run(px)
        rects = to_rects(px)
        rects_um = [((l, d), (x0 * PIXEL_UM, y0 * PIXEL_UM, x1 * PIXEL_UM, y1 * PIXEL_UM))
                    for (l, d) in METAL_LAYERS for (x0, y0, x1, y1) in rects]
        s = SIZE_PX * PIXEL_UM
        rects_um += [(bl, (0, 0, s, s)) for bl in BOUNDARY_LAYERS]
        write_views(args.out, cell)
        write_gds(os.path.join(args.out, "gds", f"{cell}.gds"), cell, rects_um)
        Image.frombytes("L", (SIZE_PX, SIZE_PX),
                        bytes(255 * v for row in px for v in row)).save(
            os.path.join(args.out, "png", f"{cell}.png"))
        print(f"{cell}: {len(rects)} rects/layer, min stroke {ms * PIXEL_UM:.2f} um, "
              f"min gap {mg * PIXEL_UM if mg else math.inf:.2f} um")


if __name__ == "__main__":
    main()
