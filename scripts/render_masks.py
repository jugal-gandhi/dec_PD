#!/usr/bin/env python3
"""Export per-layer coverage masks of a GDS for off-line compositing.

Runs with KLayout's Python module (pya), as provided by the LibreLane Nix shell.
For every view and layer, the script renders the layer alone (solid white on
black, oversampled), converts it to 8-bit grayscale and writes
<out>/<view>/<layer>.png. A views.json file records the geometry.

Usage: python3 render_masks.py <gds> <out_dir> --pdk gf180|sky130
"""
import argparse
import json
import os

import pya
from PIL import Image

GF180 = {
    "nwell": (21, 0), "comp": (22, 0), "poly": (30, 0), "contact": (33, 0),
    "m1": (34, 0), "via1": (35, 0), "m2": (36, 0), "via2": (38, 0),
    "m3": (42, 0), "via3": (40, 0), "m4": (46, 0), "via4": (41, 0),
    "m5": (81, 0), "pad": (37, 0), "mtop": (53, 0),
    "comp_fill": (22, 4), "poly_fill": (30, 4),
    "m1_fill": (34, 4), "m2_fill": (36, 4), "m3_fill": (42, 4),
    "m4_fill": (46, 4), "m5_fill": (81, 4),
}
SKY130 = {
    "nwell": (64, 20), "diff": (65, 20), "tap": (65, 44), "poly": (66, 20),
    "licon": (66, 44), "li1": (67, 20), "mcon": (67, 44),
    "m1": (68, 20), "via": (68, 44), "m2": (69, 20), "via2": (69, 44),
    "m3": (70, 20), "via3": (70, 44), "m4": (71, 20), "via4": (71, 44),
    "m5": (72, 20),
}
LOGIC_EXCLUDE = ("fill", "endcap", "tap", "decap", "filler")


def logic_bbox(layout, top, scl_prefix):
    """Bounding box (um) of standard-cell instances that carry logic."""
    box = pya.DBox()
    count = 0
    for inst in top.each_inst():
        name = inst.cell.name
        if name.startswith(scl_prefix) and not any(k in name.lower() for k in LOGIC_EXCLUDE):
            box += inst.dbbox()
            count += 1
    return box, count


def square_around(center, size):
    h = size / 2.0
    return pya.DBox(center.x - h, center.y - h, center.x + h, center.y + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gds")
    ap.add_argument("out")
    ap.add_argument("--pdk", choices=["gf180", "sky130"], required=True)
    ap.add_argument("--oversampling", type=int, default=2)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    lv = pya.LayoutView()
    lv.set_config("background-color", "#000000")
    lv.set_config("grid-visible", "false")
    lv.set_config("text-visible", "false")
    lv.set_config("cell-box-visible", "false")
    lv.load_layout(args.gds)
    lv.max_hier()
    layout = lv.active_cellview().layout()
    top = layout.top_cell()
    die = top.dbbox()

    if args.pdk == "gf180":
        layers = GF180
        logic, n_logic = logic_bbox(layout, top, "gf180mcu_fd_sc_")
        c = logic.center() if not logic.empty() else die.center()
        core_size = max(logic.width(), logic.height(), 300.0) * 1.15
        views = {
            "die": (die.enlarged(pya.DVector(die.width() * 0.01, die.height() * 0.01)), 4096,
                    ["comp", "poly", "m1", "m2", "m3", "m4", "m5", "pad", "mtop",
                     "comp_fill", "poly_fill", "m1_fill", "m2_fill", "m3_fill", "m4_fill", "m5_fill"]),
            "core": (square_around(c, core_size), 3072, list(GF180)),
            "corner": (pya.DBox(die.left, die.bottom, die.left + 900, die.bottom + 900), 3072, list(GF180)),
            "cells": (square_around(c, 60.0), 2048, list(GF180)),
        }
    else:
        layers = SKY130
        logic, n_logic = logic_bbox(layout, top, "sky130_fd_sc_")
        c = logic.center() if not logic.empty() else die.center()
        views = {
            "die": (die.enlarged(pya.DVector(die.width() * 0.02, die.height() * 0.02)), 4096, list(SKY130)),
            "cells": (square_around(c, 25.0), 2048, list(SKY130)),
        }

    meta = {"die_um": [die.left, die.bottom, die.right, die.top],
            "logic_bbox_um": [logic.left, logic.bottom, logic.right, logic.top] if not logic.empty() else None,
            "logic_instances": n_logic, "views": {}}

    for vname, (box, px, names) in views.items():
        vdir = os.path.join(args.out, vname)
        os.makedirs(vdir, exist_ok=True)
        h = int(round(px * box.height() / box.width()))
        meta["views"][vname] = {"box_um": [box.left, box.bottom, box.right, box.top],
                                "width": px, "height": h, "layers": []}
        for lname in names:
            l, d = layers[lname]
            lv.clear_layers()
            node = pya.LayerPropertiesNode()
            node.source = f"{l}/{d}@1"
            node.fill_color = 0xFFFFFF
            node.frame_color = 0xFFFFFF
            node.dither_pattern = 0
            node.visible = True
            lv.insert_layer(lv.end_layers(), node)
            tmp = os.path.join(vdir, f"_{lname}.png")
            lv.save_image_with_options(tmp, px, h, 0, args.oversampling, 0, box, False)
            im = Image.open(tmp).convert("L")
            os.remove(tmp)
            if im.getbbox() is None:
                continue  # layer absent in this view
            im.save(os.path.join(vdir, f"{lname}.png"), optimize=True)
            meta["views"][vname]["layers"].append(lname)
            print(f"[{vname}] {lname}")

    with open(os.path.join(args.out, "views.json"), "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
