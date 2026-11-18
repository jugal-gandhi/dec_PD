#!/usr/bin/env python3
"""Gallery of the hardened v3 blocks, drawn at one common scale (µm -> px).

Usage: macro_gallery.py out.png  name:title:subtitle:image:width_um:cells ...
"""
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_B = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"


def main():
    out = sys.argv[1]
    items = []
    for spec in sys.argv[2:]:
        name, title, sub, img, w_um, cells = spec.split(":")
        items.append((name, title, sub, img, float(w_um), int(cells)))
    PX_PER_UM = 1.45
    pad, gap, head = 90, 80, 210
    tiles = []
    for name, title, sub, img, w_um, cells in items:
        im = Image.open(img).convert("RGB")
        w = int(w_um * PX_PER_UM)
        h = int(im.height * w / im.width)
        tiles.append((name, title, sub, im.resize((w, h), Image.LANCZOS), w_um, cells))
    # Row 1: the biggest block; row 2: the rest
    big, rest = tiles[0], tiles[1:]
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fb_ = ImageFont.truetype(FONT_B, 44)
    fm_ = ImageFont.truetype(FONT_R, 30)

    def slot(t):
        return int(max(t[3].width, probe.textlength(t[1], font=fb_), probe.textlength(t[2], font=fm_),
                       probe.textlength(f"{t[4]:.0f} µm wide · {t[5]:,} cells", font=fm_)))
    row2_w = sum(slot(t) for t in rest) + gap * (len(rest) - 1)
    W = max(big[3].width, row2_w) + 2 * pad
    row2_h = max(t[3].height for t in rest)
    H = 260 + head + big[3].height + head + row2_h + 220
    canvas = Image.new("RGB", (W, H), (6, 7, 10))
    d = ImageDraw.Draw(canvas)
    ft = ImageFont.truetype(FONT_B, 72)
    fs = ImageFont.truetype(FONT_R, 38)
    fb = ImageFont.truetype(FONT_B, 44)
    fm = ImageFont.truetype(FONT_R, 30)
    d.text((pad, 80), "HARD MACROS OF THE SoC · SAME SCALE", font=ft, fill=(255, 255, 255))
    d.text((pad, 175), "GF180MCU 180 nm · each block hardened on its own, then placed on the die",
           font=fs, fill=(165, 170, 180))

    def tile(t, x, y):
        name, title, sub, im, w_um, cells = t
        mine = name == "posit_decoder_32_2"
        col = (255, 226, 61) if mine else (255, 255, 255)
        d.text((x, y), title, font=fb, fill=col)
        d.text((x, y + 62), sub, font=fm, fill=(175, 180, 190))
        d.text((x, y + 104), f"{w_um:.0f} µm wide · {cells:,} cells", font=fm, fill=(120, 126, 138))
        canvas.paste(im, (x, y + head - 40))
        lw = 8 if mine else 3
        d.rectangle([x - lw, y + head - 40 - lw, x + im.width + lw, y + head - 40 + im.height + lw],
                    outline=col, width=lw)

    y = 260
    tile(big, pad + (W - 2 * pad - big[3].width) // 2, y)
    y += head + big[3].height + 40
    x = pad + (W - 2 * pad - row2_w) // 2
    for t in rest:
        tile(t, x, y + (row2_h - t[3].height))
        x += slot(t) + gap
    # scale bar: 200 µm
    sb = int(200 * PX_PER_UM)
    yb = H - 110
    d.rectangle([pad, yb, pad + sb, yb + 14], fill=(255, 255, 255))
    d.text((pad + sb + 30, yb - 18), "200 µm", font=fs, fill=(255, 255, 255))
    canvas.save(out, optimize=True)
    print("wrote", out, canvas.size)


if __name__ == "__main__":
    main()
