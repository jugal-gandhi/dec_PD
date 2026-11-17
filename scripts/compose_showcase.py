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
    ("nwell", "#141a33", 0.30, 0.00),
    ("diff",  "#0f766e", 0.50, 0.00),
    ("tap",   "#115e59", 0.50, 0.00),
    ("poly",  "#ff4d6d", 0.75, 0.00),
    ("licon", "#f8fafc", 0.55, 0.00),
    ("li1",   "#22d3ee", 0.22, 0.05),
    ("mcon",  "#ecfeff", 0.60, 0.00),
    ("m1",    "#38bdf8", 0.40, 0.15),
    ("via",   "#e0f2fe", 0.75, 0.00),
    ("m2",    "#6366f1", 0.50, 0.20),
    ("via2",  "#e0e7ff", 0.75, 0.00),
    ("m3",    "#a855f7", 0.48, 0.25),
    ("via3",  "#f3e8ff", 0.75, 0.00),
    ("m4",    "#ec4899", 0.45, 0.30),
    ("via4",  "#fce7f3", 0.75, 0.00),
    ("m5",    "#f59e0b", 0.42, 0.35),
]


# Classic EDA look: black background, hatched fills, crisp outlines.
# (layer, colour, fill opacity, outline opacity, pattern)
CLASSIC_GF180 = [
    ("nwell",   "#2f6b3a", 0.00, 0.55, "none"),
    ("comp",    "#22c55e", 0.55, 0.90, "dots"),
    ("poly",    "#ff3b3b", 0.70, 0.95, "back"),
    ("contact", "#ffffff", 0.90, 0.00, "solid"),
    ("m1",      "#3b82f6", 0.45, 0.95, "fwd"),
    ("via1",    "#e5e7eb", 0.85, 0.00, "solid"),
    ("m2",      "#ff2bd6", 0.45, 0.95, "back"),
    ("via2",    "#e5e7eb", 0.85, 0.00, "solid"),
    ("m3",      "#22d3ee", 0.45, 0.95, "fwd"),
    ("via3",    "#e5e7eb", 0.85, 0.00, "solid"),
    ("m4",      "#4f6bff", 0.60, 1.00, "back"),
    ("via4",    "#e5e7eb", 0.85, 0.00, "solid"),
    ("m5",      "#d9412b", 0.22, 0.85, "cross"),
    ("mtop",    "#d9412b", 0.15, 0.70, "cross"),
    ("pad",     "#facc15", 0.75, 1.00, "cross"),
]
CLASSIC_SKY130 = [
    ("nwell", "#2f6b3a", 0.00, 0.55, "none"),
    ("diff",  "#22c55e", 0.55, 0.90, "dots"),
    ("tap",   "#16a34a", 0.55, 0.90, "dots"),
    ("poly",  "#ff3b3b", 0.70, 0.95, "back"),
    ("licon", "#ffffff", 0.85, 0.00, "solid"),
    ("li1",   "#a3a3a3", 0.30, 0.80, "fwd"),
    ("mcon",  "#ffffff", 0.85, 0.00, "solid"),
    ("m1",    "#3b82f6", 0.45, 0.95, "back"),
    ("via",   "#e5e7eb", 0.85, 0.00, "solid"),
    ("m2",    "#ff2bd6", 0.45, 0.95, "fwd"),
    ("via2",  "#e5e7eb", 0.85, 0.00, "solid"),
    ("m3",    "#22d3ee", 0.45, 0.95, "back"),
    ("via3",  "#e5e7eb", 0.85, 0.00, "solid"),
    ("m4",    "#4f6bff", 0.85, 1.00, "fwd"),
    ("via4",  "#e5e7eb", 0.85, 0.00, "solid"),
    ("m5",    "#ff7a1a", 0.90, 1.00, "cross"),
]


OCCLUDE = 0.55


def pattern(kind, h, w, pitch):
    yy, xx = np.mgrid[0:h, 0:w]
    lw = max(1, pitch // 4)
    if kind == "solid":
        p = np.ones((h, w))
    elif kind == "none":
        p = np.zeros((h, w))
    elif kind == "fwd":
        p = ((xx + yy) % pitch) < lw
    elif kind == "back":
        p = ((xx - yy) % pitch) < lw
    elif kind == "cross":
        p = (((xx + yy) % pitch) < lw) | (((xx - yy) % pitch) < lw)
    elif kind == "dots":
        p = ((xx % pitch) < lw) & ((yy % pitch) < lw)
    return p.astype(np.float32)[..., None]


def compose_classic(view_dir, layers_present, style, pitch=None):
    first = Image.open(os.path.join(view_dir, f"{layers_present[0]}.png"))
    w, h = first.size
    pitch = pitch or max(6, w // 512)
    edge_px = max(1, w // 2048)
    canvas = np.zeros((h, w, 3), dtype=np.float32)
    for name, color, fa, la, kind in style:
        if name not in layers_present:
            continue
        mimg = Image.open(os.path.join(view_dir, f"{name}.png")).convert("L")
        m = np.asarray(mimg, dtype=np.float32)[..., None] / 255.0
        er = mimg
        for _ in range(edge_px):
            er = er.filter(ImageFilter.MinFilter(3))
        edge = np.clip(m - np.asarray(er, dtype=np.float32)[..., None] / 255.0, 0, 1)
        c = hex_rgb(color)
        # Partly occlude what lies below, so stacked layers stay saturated
        occ = 0.0 if kind == "solid" or fa == 0 else min(OCCLUDE, fa)
        canvas = canvas * (1 - m * occ)
        a = np.clip(m * fa * pattern(kind, h, w, pitch) + edge * la, 0, 1)
        canvas = canvas * (1 - a) + c * a
    return np.clip(canvas, 0, 1)


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
    ap.add_argument("--style", choices=["classic", "neon"], default="classic")
    ap.add_argument("--with-fill", action="store_true", help="draw dummy metal fill too")
    ap.add_argument("--views", nargs="*", default=None)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    meta = json.load(open(os.path.join(args.masks, "views.json")))
    for vname, v in meta["views"].items():
        if not v["layers"] or (args.views and vname not in args.views):
            continue
        layers = [l for l in v["layers"] if args.with_fill or not l.endswith("_fill")]
        vdir = os.path.join(args.masks, vname)
        if args.style == "classic":
            style = CLASSIC_GF180 if args.pdk == "gf180" else CLASSIC_SKY130
            arr = compose_classic(vdir, layers, style)
        else:
            style = STYLE_GF180 if args.pdk == "gf180" else STYLE_SKY130
            arr = compose(vdir, layers, style)
        save(arr, os.path.join(args.out, f"{args.pdk}_{vname}_{args.style}.png"))
        print("wrote", vname, args.style, arr.shape)


if __name__ == "__main__":
    main()
