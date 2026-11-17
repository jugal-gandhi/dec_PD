#!/usr/bin/env python3
"""Composite per-layer masks (from render_masks.py) into styled layout images.

Every pixel comes from real layout geometry; the script only assigns colours,
opacity and glow to each layer. Requires numpy and Pillow.

Usage: compose_showcase.py <masks_dir> <out_dir> [--pdk gf180|sky130]
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageFilter

# (colour, opacity, glow) per layer; drawn bottom to top in this order.
STYLE_GF180 = [
    ("nwell",     "#1d2440", 0.35, 0.00),
    ("comp",      "#14b8a6", 0.55, 0.00),
    ("comp_fill", "#14b8a6", 0.10, 0.00),
    ("poly",      "#ff4d6d", 0.70, 0.00),
    ("poly_fill", "#ff4d6d", 0.10, 0.00),
    ("contact",   "#f8fafc", 0.70, 0.00),
    ("m1_fill",   "#38bdf8", 0.10, 0.00),
    ("m1",        "#38bdf8", 0.55, 0.15),
    ("via1",      "#e0f2fe", 0.75, 0.00),
    ("m2_fill",   "#6366f1", 0.10, 0.00),
    ("m2",        "#6366f1", 0.55, 0.20),
    ("via2",      "#e0e7ff", 0.75, 0.00),
    ("m3_fill",   "#a855f7", 0.10, 0.00),
    ("m3",        "#a855f7", 0.50, 0.25),
    ("via3",      "#f3e8ff", 0.75, 0.00),
    ("m4_fill",   "#ec4899", 0.10, 0.00),
    ("m4",        "#ec4899", 0.45, 0.30),
    ("via4",      "#fce7f3", 0.75, 0.00),
    ("m5_fill",   "#f59e0b", 0.08, 0.00),
    ("m5",        "#f59e0b", 0.42, 0.35),
    ("mtop",      "#fde68a", 0.40, 0.30),
    ("pad",       "#fde047", 0.55, 0.60),
]
STYLE_SKY130 = [
    ("nwell", "#1d2440", 0.35, 0.00),
    ("diff",  "#14b8a6", 0.55, 0.00),
    ("tap",   "#0d9488", 0.55, 0.00),
    ("poly",  "#ff4d6d", 0.70, 0.00),
    ("licon", "#f8fafc", 0.70, 0.00),
    ("li1",   "#22d3ee", 0.45, 0.10),
    ("mcon",  "#ecfeff", 0.75, 0.00),
    ("m1",    "#38bdf8", 0.50, 0.15),
    ("via",   "#e0f2fe", 0.75, 0.00),
    ("m2",    "#6366f1", 0.50, 0.20),
    ("via2",  "#e0e7ff", 0.75, 0.00),
    ("m3",    "#a855f7", 0.48, 0.25),
    ("via3",  "#f3e8ff", 0.75, 0.00),
    ("m4",    "#ec4899", 0.45, 0.30),
    ("via4",  "#fce7f3", 0.75, 0.00),
    ("m5",    "#f59e0b", 0.42, 0.35),
]


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def background(w, h, inner="#0f1730", outer="#03050b"):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    t = np.clip(r, 0, 1)[..., None] ** 1.3
    return hex_rgb(inner) * (1 - t) + hex_rgb(outer) * t


def compose(view_dir, layers_present, style, glow_radius_frac=0.0025, only=None):
    first = Image.open(os.path.join(view_dir, f"{layers_present[0]}.png"))
    w, h = first.size
    canvas = background(w, h)
    glow_r = max(1.5, glow_radius_frac * w)
    for name, color, alpha, glow in style:
        if name not in layers_present or (only is not None and name not in only):
            continue
        mask_img = Image.open(os.path.join(view_dir, f"{name}.png")).convert("L")
        m = np.asarray(mask_img, dtype=np.float32)[..., None] / 255.0
        c = hex_rgb(color)
        canvas = canvas * (1 - m * alpha) + c * (m * alpha)
        if glow > 0:
            g = np.asarray(mask_img.filter(ImageFilter.GaussianBlur(glow_r)), dtype=np.float32)[..., None] / 255.0
            canvas = 1 - (1 - canvas) * (1 - c * g * glow)
    return np.clip(canvas, 0, 1)


def save(arr, path, quality=94):
    im = Image.fromarray((arr * 255 + 0.5).astype(np.uint8))
    if path.endswith(".jpg"):
        im.save(path, quality=quality, subsampling=0, optimize=True)
    else:
        im.save(path, optimize=True)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("masks")
    ap.add_argument("out")
    ap.add_argument("--pdk", choices=["gf180", "sky130"], default="gf180")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    meta = json.load(open(os.path.join(args.masks, "views.json")))
    style = STYLE_GF180 if args.pdk == "gf180" else STYLE_SKY130
    for vname, v in meta["views"].items():
        if not v["layers"]:
            continue
        arr = compose(os.path.join(args.masks, vname), v["layers"], style)
        save(arr, os.path.join(args.out, f"{args.pdk}_{vname}.png"))
        print("wrote", vname, arr.shape)


if __name__ == "__main__":
    main()
