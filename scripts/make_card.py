#!/usr/bin/env python3
"""Build a 3840x2160 showcase card from a composed hero image and flow metrics.

All numbers on the card are read from LibreLane's metrics.json.
Usage: make_card.py --hero hero.png --tiles a.png b.png c.png --metrics metrics.json
                    --out card.jpg --target gf180|sky130 [--fonts DIR]
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 3840, 2160
BG0, BG1 = (6, 9, 18), (14, 22, 46)
ACCENT = [(56, 189, 248), (168, 85, 247), (236, 72, 153), (245, 158, 11)]
TEXT = (235, 240, 250)
MUTED = (148, 163, 184)


def font(dir_, name, size):
    return ImageFont.truetype(os.path.join(dir_, name), size)


def gradient_bg():
    img = Image.new("RGB", (W, H), BG0)
    px = img.load()
    for y in range(H):
        for x in range(0, W, 4):
            t = min(1.0, ((x / W) * 0.6 + (1 - y / H) * 0.4))
            c = tuple(int(BG0[i] + (BG1[i] - BG0[i]) * t) for i in range(3))
            for k in range(4):
                if x + k < W:
                    px[x + k, y] = c
    return img


def accent_bar(draw, x0, y0, x1, h):
    n = len(ACCENT) - 1
    for x in range(x0, x1):
        t = (x - x0) / max(1, x1 - x0 - 1) * n
        i = min(int(t), n - 1)
        f = t - i
        c = tuple(int(ACCENT[i][k] + (ACCENT[i + 1][k] - ACCENT[i][k]) * f) for k in range(3))
        draw.line([(x, y0), (x, y0 + h)], fill=c)


def fmt_area_mm2(um2):
    return f"{um2 / 1e6:.2f} mm²"


def metric(m, *keys, default=None):
    for k in keys:
        if k in m and m[k] is not None:
            return m[k]
    return default


def specs_from_metrics(m, target, period, critical=None):
    die = metric(m, "design__die__bbox")
    if isinstance(die, str):
        x0, y0, x1, y1 = map(float, die.split())
    else:
        x0 = y0 = 0.0
        x1 = y1 = (metric(m, "design__die__area", default=0) ** 0.5)
    ws_tt = metric(m, "timing__setup__ws__corner:nom_tt_025C_5v00", "timing__setup__ws__corner:nom_tt_025C_1v80")
    ws_all = metric(m, "timing__setup__ws")
    stdcells = metric(m, "design__instance__count__stdcell", default=0)
    fill = metric(m, "design__instance__count__class:fill_cell", default=0) or 0
    tap = metric(m, "design__instance__count__class:tap_cell", default=0) or 0
    endcap = metric(m, "design__instance__count__class:endcap_cell", default=0) or 0
    logic = metric(m, "design__instance__count__class:multi_input_combinational_cell", default=0) or 0
    inv = metric(m, "design__instance__count__class:inverter", default=0) or 0
    buf = (metric(m, "design__instance__count__class:buffer", default=0) or 0) + \
          (metric(m, "design__instance__count__class:timing_repair_buffer", default=0) or 0)
    drc_k = metric(m, "klayout__drc_error__count")
    drc_m = metric(m, "magic__drc_error__count")
    lvs = metric(m, "design__lvs_error__count")
    # Sign-off antenna count comes from the KLayout deck when it ran
    ant = metric(m, "klayout__antenna_error__count", "antenna__violating__nets", "route__antenna_violation__count")
    rows = []
    if target == "soc":
        rows.append(("Process", "GlobalFoundries GF180MCU · 180 nm · 5 metals"))
        rows.append(("Die", f"{(x1 - x0) / 1000:.3f} × {(y1 - y0) / 1000:.3f} mm  ·  40-pad ring"))
        rows.append(("CPU", "PicoRV32 RISC-V RV32IMC · SPI-flash boot · UART · 16 GPIO"))
        rows.append(("Hard macros", "4 × 512×8 foundry SRAM (2 KB) · posit‹32,2› decoder"))
        rows.append(("Logic", f"{logic + inv:,} gates · {metric(m, 'design__instance__count__class:sequential_cell', default=0):,} flip-flops"))
        if critical:
            rows.append(("Clock", critical))
    elif target == "gf180":
        rows.append(("Process", "GlobalFoundries GF180MCU · 180 nm · 5 metals"))
        rows.append(("Die", f"{(x1 - x0) / 1000:.3f} × {(y1 - y0) / 1000:.3f} mm  ({fmt_area_mm2((x1 - x0) * (y1 - y0))})"))
        rows.append(("I/O ring", "88 pads · 32 in · 38 out · 18 supply"))
    else:
        rows.append(("Process", "SkyWater SKY130 · 130 nm · 5 metals"))
        rows.append(("Macro", f"{x1 - x0:.0f} × {y1 - y0:.0f} µm  ({(x1 - x0) * (y1 - y0):,.0f} µm²)"))
        rows.append(("Pins", "70 · 32 in · 38 out"))
    if target != "soc":
        rows.append(("Logic", f"{logic + inv:,} gates · {buf:,} buffers · {stdcells:,} cells placed"))
    if target == "soc":
        pass
    elif critical:
        rows.append(("Critical path", critical))
    elif ws_tt is not None:
        rows.append(("Timing slack", f"{ws_tt:.2f} ns typical · {ws_all:.2f} ns worst corner"))
    checks = []
    if drc_k is not None:
        checks.append(f"KLayout DRC {int(drc_k)}")
    if drc_m is not None:
        checks.append(f"Magic DRC {int(drc_m)}")
    if lvs is not None:
        checks.append(f"LVS {int(lvs)}")
    if ant is not None:
        checks.append(f"antenna {int(ant)}")
    rows.append(("Sign-off errors", " · ".join(checks)))
    rows.append(("Toolchain", "Yosys · OpenROAD · KLayout · Magic · Netgen · LibreLane"))
    return rows


def draw_posit_title(d, x, y, f):
    """Draw 'Posit<32,2>' with true mathematical angle brackets as strokes."""
    asc = f.getbbox("P")
    top, bottom = y + asc[1], y + asc[3]
    h = bottom - top
    lw = max(4, int(h * 0.11))
    d.text((x, y), "Posit", font=f, fill=TEXT)
    x += d.textlength("Posit", font=f) + h * 0.12
    bw = h * 0.30
    pad = -h * 0.08
    d.line([(x + bw, top + pad), (x, (top + bottom) / 2), (x + bw, bottom - pad)], fill=ACCENT[1],
           width=lw, joint="curve")
    x += bw + h * 0.16
    d.text((x, y), "32,2", font=f, fill=TEXT)
    x += d.textlength("32,2", font=f) + h * 0.16
    d.line([(x, top + pad), (x + bw, (top + bottom) / 2), (x, bottom - pad)], fill=ACCENT[1],
           width=lw, joint="curve")


def framed(img, size, radius=28):
    im = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(im, (0, 0), mask)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", required=True)
    ap.add_argument("--tiles", nargs="*", default=[])
    ap.add_argument("--tile-labels", nargs="*", default=[])
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--period", type=float, required=True)
    ap.add_argument("--critical", default=None, help="critical-path text taken from the STA reports")
    ap.add_argument("--target", choices=["gf180", "sky130", "soc"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", default="/usr/share/fonts/truetype/google-fonts")
    ap.add_argument("--inter", default="/usr/share/fonts/opentype/inter")
    args = ap.parse_args()

    m = json.load(open(args.metrics))
    rows = specs_from_metrics(m, args.target, args.period, args.critical)

    card = gradient_bg()
    d = ImageDraw.Draw(card)

    # Hero with soft glow behind it
    hs = 1960
    hx, hy = 100, (H - hs) // 2
    hero = framed(Image.open(args.hero).convert("RGB"), hs)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([hx - 10, hy - 10, hx + hs + 10, hy + hs + 10], radius=40,
                                           fill=(99, 102, 241, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(45))
    card = Image.alpha_composite(card.convert("RGBA"), glow)
    card.alpha_composite(hero, (hx, hy))
    d = ImageDraw.Draw(card)

    x = hx + hs + 150
    right = W - 120
    y = 170
    f_kicker = font(args.fonts, "Poppins-Bold.ttf", 46)
    f_title = font(args.fonts, "Poppins-Bold.ttf", 132)
    f_sub = font(args.fonts, "Poppins-Medium.ttf", 52)
    f_label = font(args.inter, "Inter-Medium.otf", 40)
    f_value = font(args.inter, "Inter-SemiBold.otf", 44)
    f_foot = font(args.fonts, "Poppins-Medium.ttf", 44)

    kicker = {"gf180": "OPEN-SOURCE RTL-TO-GDSII", "sky130": "OPEN-SOURCE RTL-TO-GDSII · CORE MACRO",
              "soc": "OPEN-SOURCE RTL-TO-GDSII · RISC-V SOC"}[args.target]
    d.text((x, y), kicker, font=f_kicker, fill=ACCENT[0])
    y += 80
    if args.target == "soc":
        d.text((x, y), "RISC-V SoC", font=f_title, fill=TEXT)
        y += 150
        f_t2 = font(args.fonts, "Poppins-Bold.ttf", 100)
        d.text((x, y + 20), "+ ", font=f_t2, fill=TEXT)
        draw_posit_title(d, x + d.textlength("+ ", font=f_t2), y + 20, f_t2)
    else:
        draw_posit_title(d, x, y, f_title)
        y += 150
        d.text((x, y), "Decoder", font=f_title, fill=TEXT)
    y += 185
    accent_bar(d, x, y, x + 520, 10)
    y += 60
    sub = {"gf180": "Chip with full I/O pad ring", "sky130": "Hardened standard-cell macro",
           "soc": "Hierarchical chip with posit accelerator"}[args.target]
    d.text((x, y), sub, font=f_sub, fill=MUTED)
    y += 120

    for label, value in rows:
        d.text((x, y), label.upper(), font=f_label, fill=MUTED)
        y += 54
        # wrap long values
        words, line = value.split(" "), ""
        for w_ in words:
            trial = (line + " " + w_).strip()
            if d.textlength(trial, font=f_value) > right - x:
                d.text((x, y), line, font=f_value, fill=TEXT)
                y += 58
                line = w_
            else:
                line = trial
        d.text((x, y), line, font=f_value, fill=TEXT)
        y += 84

    # Detail tiles
    if args.tiles:
        n = len(args.tiles)
        gap = 40
        ts = min(360, (right - x - gap * (n - 1)) // n)
        ty = H - 170 - ts - 50
        if ty > y:
            for i, t in enumerate(args.tiles):
                tx = x + i * (ts + gap)
                card.alpha_composite(framed(Image.open(t).convert("RGB"), ts, radius=18), (tx, ty))
                if i < len(args.tile_labels):
                    d.text((tx, ty + ts + 14), args.tile_labels[i], font=f_label, fill=MUTED)

    d.text((x, H - 150), "VLSI Design Lab, CSIR-CEERI  ·  2026", font=f_foot, fill=TEXT)
    card.convert("RGB").save(args.out, quality=93, subsampling=0, optimize=True)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
