#!/usr/bin/env python3
"""Export the v3 pad-ring + floorplan + QFN-40 bonding figure as an editable draw.io file.

Geometry comes from pad_bonding_figure.py, so both outputs stay identical.
Every pad, pin, macro and label is a separate shape. Bond wires are edges that
attach to their pad and pin, so a moved pad keeps its wire. Layers group the
package, die, macros, wires, annotations and legend.
Usage: pad_bonding_drawio.py out.drawio
"""
import math
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pad_bonding_figure as F                       # noqa: E402

S = 150.0                     # px per mm
FS = 2.3                      # matplotlib pt -> draw.io px
H = F.PKG / 2
OX, OY = H + 1.0, H + 1.75    # figure origin (package centre) in mm from the page top-left
FONT = "Times New Roman"

root_model = ET.Element("mxGraphModel", dict(dx="1600", dy="1800", grid="0", gridSize="10", guides="1",
                                             tooltips="1", connect="1", arrows="1", fold="1", page="1",
                                             pageScale="1", pageWidth=str(int((2 * H + 2.0) * S)),
                                             pageHeight=str(int((2 * H + 4.0) * S)), math="0", shadow="0",
                                             background="#ffffff"))
cells = ET.SubElement(root_model, "root")
ET.SubElement(cells, "mxCell", id="0")
_n = [0]


def nid(p="c"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def layer(name):
    i = "L_" + name.lower().replace(" ", "_").replace("&", "and")
    ET.SubElement(cells, "mxCell", id=i, value=name, parent="0")
    return i


def blend(col, a, bg="#ffffff"):
    c = [int(col[k:k + 2], 16) for k in (1, 3, 5)]
    b = [int(bg[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(a * x + (1 - a) * y):02x}" for x, y in zip(c, b))


def px(fx, fy):
    """figure coords (mm, origin package centre, y up) -> page px (y down)"""
    return (fx + OX) * S, (OY - fy) * S


def style(**kw):
    return ";".join(f"{k}={v}" for k, v in kw.items()) + ";"


def vertex(par, x0, y0, w, h, value="", st="", vid=None):
    """x0, y0 = lower-left corner in figure coords; w, h in mm."""
    X, Y = px(x0, y0 + h)
    vid = vid or nid("v")
    c = ET.SubElement(cells, "mxCell", id=vid, value=value, style=st, vertex="1", parent=par)
    ET.SubElement(c, "mxGeometry", x=f"{X:.2f}", y=f"{Y:.2f}", width=f"{w * S:.2f}", height=f"{h * S:.2f}",
                  **{"as": "geometry"})
    return vid


def text(par, cx, cy, value, fs, color=F.INK, w=None, h=None, align="center", rot=0, bold=False, vid=None):
    """Free text centred at (cx, cy); for align=left/right, cx is the anchor edge."""
    w = w if w is not None else max(0.3, 0.0105 * fs * len(value.split("<br>")[0]) + 0.1)
    h = h if h is not None else 0.03 * fs * (value.count("<br>") + 1) + 0.04
    x0 = cx - w / 2 if align == "center" else (cx if align == "left" else cx - w)
    st = style(text="", html=1, strokeColor="none", fillColor="none", align=align, verticalAlign="middle",
               whiteSpace="wrap", fontFamily=FONT, fontSize=f"{fs * FS:.1f}", fontColor=color,
               fontStyle=1 if bold else 0, rotation=rot, spacing=0)
    return vertex(par, x0, cy - h / 2, w, h, value, st, vid)


def line(par, p0, p1, color, lw, dash=None, end="none", start="none", src=None, tgt=None, srel=None, trel=None,
         startsize=None):
    st = dict(endArrow=end, startArrow=start, html=1, rounded=0, strokeColor=color, strokeWidth=f"{lw * FS:.2f}",
              endFill=1, startFill=1)
    if dash:
        st.update(dashed=1, dashPattern=dash)
    if startsize:
        st.update(startSize=startsize)
    if srel:
        st.update(exitX=f"{srel[0]:.4f}", exitY=f"{srel[1]:.4f}", exitDx=0, exitDy=0, exitPerimeter=0)
    if trel:
        st.update(entryX=f"{trel[0]:.4f}", entryY=f"{trel[1]:.4f}", entryDx=0, entryDy=0, entryPerimeter=0)
    attrs = dict(id=nid("e"), value="", style=style(**st), edge="1", parent=par)
    if src:
        attrs["source"] = src
    if tgt:
        attrs["target"] = tgt
    c = ET.SubElement(cells, "mxCell", attrs)
    g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
    for p, nm in ((p0, "sourcePoint"), (p1, "targetPoint")):
        X, Y = px(*p)
        ET.SubElement(g, "mxPoint", x=f"{X:.2f}", y=f"{Y:.2f}", **{"as": nm})


def rel(pt, rect):
    """relative position of a figure point in a vertex rect (x0, y0, w, h), draw.io orientation"""
    x0, y0, w, h = rect
    return (pt[0] - x0) / w, (y0 + h - pt[1]) / h


def box_style(fill, stroke, lw, **extra):
    st = dict(rounded=0, whiteSpace="wrap", html=1, fillColor=fill, strokeColor=stroke, strokeWidth=f"{lw * FS:.2f}",
              fontFamily=FONT, fontColor=F.INK)
    st.update(extra)
    return style(**st)


def main():
    out = sys.argv[1]
    L_pkg, L_die, L_mac, L_wire, L_ann, L_leg = (layer(n) for n in
                                                 ("Package", "Die and pad ring", "Macros", "Bond wires",
                                                  "Annotations", "Legend and title"))
    # ---- package
    vertex(L_pkg, -H, -H, F.PKG, F.PKG, "", box_style("#f7f6f3", F.INK3, 1.0, rounded=1, absoluteArcSize=1,
                                                         arcSize=f"{0.24 * S:.0f}"), "pkg_body")
    vertex(L_pkg, -F.EPAD / 2, -F.EPAD / 2, F.EPAD, F.EPAD, "", box_style("#e9e8e4", "#c9c8c3", 0.6), "pkg_epad")
    vertex(L_pkg, -H + 0.21, H - 0.35, 0.14, 0.14, "", style(ellipse="", fillColor=F.INK, strokeColor="none"),
           "pin1_mark")
    text(L_pkg, -F.EPAD / 2 + 0.05, -F.EPAD / 2 + 0.13, "exposed pad 4.1 mm → VSS", 5.2, F.INK2, w=1.6,
         align="left")

    # ---- die, corners, ring, core boundary
    dx0, dy0 = F.d2f(0, 0)
    vertex(L_die, dx0, dy0, F.DIE, F.DIE, "", box_style("#fbfbfa", F.INK, 1.1), "die")
    for cx, cy, nm in ((0.026, 0.026, "cornLL"), (F.DIE - 0.381, 0.026, "cornLR"),
                       (0.026, F.DIE - 0.381, "cornTL"), (F.DIE - 0.381, F.DIE - 0.381, "cornTR")):
        x, y = F.d2f(cx, cy)
        vertex(L_die, x, y, 0.355, 0.355, nm, box_style("#9fc1ea", "#5f86b8", 0.6, fontSize=f"{5 * FS:.1f}"), nm)
    rx, ry = F.d2f(0.420, 0.420)
    vertex(L_die, rx, ry, F.DIE - 0.84, F.DIE - 0.84, "", box_style("none", F.SLOT[7], 1.6), "core_ring")
    cx, cy = F.d2f(0.442, 0.442)
    vertex(L_die, cx, cy, F.DIE - 0.884, F.DIE - 0.884, "",
           box_style("none", F.INK, 0.7, dashed=1, dashPattern="4 2"), "core_boundary")

    # ---- macros
    for nm, x, y, w, hh, col, txt in F.MACROS:
        X, Y = F.d2f(x / 1000, y / 1000)
        a = 0.55 if nm == "POSIT" else 0.20
        extra = dict(fontSize=f"{(6.6 if nm == 'CPU' else 5.6) * FS:.1f}")
        if nm == "CPU":
            extra.update(fontStyle=1, spacingTop=f"{0.4 * S:.0f}")
        vertex(L_mac, X, Y, w / 1000, hh / 1000, txt.replace("\n", "<br>"),
               box_style(blend(col, a, "#fbfbfa"), col, 1.4 if nm == "POSIT" else 0.9, **extra), "m_" + nm.lower())
    X, Y = F.d2f(1.862, 2.707)
    vertex(L_mac, X, Y, 0.210, 0.117, "ALU",
           box_style("none", F.SLOT[0], 0.9, dashed=1, dashPattern="2 1", verticalLabelPosition="bottom",
                     verticalAlign="top", fontColor=F.SLOT[0], fontSize=f"{5.2 * FS:.1f}", spacing=0), "m_alu")
    for col_x, name in ((482.0, "Main RAM"), (2688.0, "Scratch")):
        for k, y in enumerate(F.SRAM_Y):
            X, Y = F.d2f(col_x / 1000, y / 1000)
            vertex(L_mac, X, Y, 0.43186, 0.48488, f"SRAM<br>512×8<br>#{k}",
                   box_style(blend(F.SLOT[6], 0.18, "#fbfbfa"), F.SLOT[6], 0.8, fontSize=f"{5 * FS:.1f}"),
                   f"m_{name.split()[0].lower()}_sram{k}")
        X, Yt = F.d2f(col_x / 1000 + (0.432 + 0.045 if name == "Main RAM" else -0.045), 1.80)
        text(L_ann, X, Yt, f"{name} 2 KB  (4 x 512 x 8)", 5.2, F.SLOT[6], w=1.6, h=0.12, rot=-90)
    # posit callout (edge attached to the posit macro and the label)
    TX, TY = F.d2f(2.42, 2.03)
    lab = text(L_ann, TX, TY, "Posit⟨32,2⟩ decoder<br>(this work)", 5.6, F.SLOT[5], w=1.05, h=0.27,
               align="right", bold=True, vid="posit_label")
    PX, PY = F.d2f(2.189, 2.6005)
    line(L_ann, (PX + 0.12, PY), (TX - 0.09, TY + 0.135), F.SLOT[5], 0.8, src="m_posit", tgt=lab,
         srel=(0.6, 1.0), trel=(0.915, 0.0))

    # ---- pads, pins, bond wires
    pin_no, wl = 1, []
    for side, names in F.SIDES:
        for i, n in enumerate(names):
            (x0, y0, w, hh), bond, _, rot = F.pad_geom(side, i)
            k = F.kind(n)
            X0, Y0 = F.d2f(x0, y0)
            prect = (X0, Y0, w, hh)
            lbl = F.short(n)
            fs = 4.5 if len(lbl) > 4 else 5.0
            pad = vertex(L_die, X0, Y0, w, hh, lbl,
                         box_style(blend(F.PADCOL[k], 0.22 if k == "vss" else 0.16, "#fbfbfa"), F.PADCOL[k], 0.7,
                                   fontSize=f"{fs * FS:.1f}", horizontal=0 if rot else 1, spacing=0),
                         f"pad_{pin_no:02d}_{n}")
            if k in ("vdd", "vss"):
                if side == "W":
                    seg = ((0.376, F.PAD_C[9 - i]), (0.420, F.PAD_C[9 - i]))
                elif side == "E":
                    seg = ((F.DIE - 0.376, F.PAD_C[i]), (F.DIE - 0.420, F.PAD_C[i]))
                elif side == "S":
                    seg = ((F.PAD_C[i], 0.376), (F.PAD_C[i], 0.420))
                else:
                    seg = ((F.PAD_C[9 - i], F.DIE - 0.376), (F.PAD_C[9 - i], F.DIE - 0.420))
                line(L_die, F.d2f(*seg[0]), F.d2f(*seg[1]), F.SLOT[7] if k == "vdd" else "#3a3936", 1.6)
            (qx, qy, qw, qh), pin_in, num_pos, ha = F.pin_geom(side, i)
            pin = vertex(L_pkg, qx, qy, qw, qh, "", box_style("#d8d7d2", F.INK3, 0.6), f"pin_{pin_no:02d}")
            nw = 0.3
            text(L_pkg, num_pos[0], num_pos[1], str(pin_no), 5.3, F.INK2, w=nw, h=0.14,
                 align={"right": "right", "left": "left", "center": "center"}[ha], bold=pin_no == 1)
            b = F.d2f(*bond)
            line(L_wire, b, pin_in, F.PADCOL[k], 0.55, start="oval", startsize=4, src=pad, tgt=pin,
                 srel=rel(b, prect), trel=rel(pin_in, (qx, qy, qw, qh)))
            wl.append(math.hypot(b[0] - pin_in[0], b[1] - pin_in[1]))
            pin_no += 1

    # ---- group labels and numbering arrows
    g = H + 0.42
    text(L_ann, -g - 0.05, 0, F.GROUP["W"], 6.3, F.INK2, w=2.4, h=0.16, rot=-90)
    text(L_ann, g + 0.05, 0, F.GROUP["E"], 6.3, F.INK2, w=2.4, h=0.16, rot=-90)
    text(L_ann, 0, -g - 0.07, F.GROUP["S"], 6.3, F.INK2, w=2.4, h=0.16)
    text(L_ann, 0, g + 0.07, F.GROUP["N"], 6.3, F.INK2, w=2.4, h=0.16)
    a = H + 0.62
    for p0, p1 in (((-a, 2.2), (-a, -2.2)), ((-2.2, -a), (2.2, -a)), ((a, -2.2), (a, 2.2)), ((2.2, a), (-2.2, a))):
        line(L_ann, p0, p1, F.INK, 1.1, end="block")

    # ---- title, legend, footnote
    tl = -H - 0.9
    text(L_leg, tl, H + 1.5, "POSIT-RV v3 SoC: pad ring, floorplan and QFN-40 bonding (top view)", 9.5, F.INK,
         w=7.6, h=0.2, align="left")
    text(L_leg, tl, H + 1.27, "GF180MCU · die 3.602 × 3.602 mm · 40 pads (28 signal, 6 VDD, 6 VSS) · "
         "QFN-40, 6 × 6 mm, 0.5 mm pitch", 6.6, F.INK2, w=7.6, h=0.16, align="left")
    items = [("Bidirectional I/O (bi_24t)", F.PADCOL["io"]), ("Input (in_c)", F.PADCOL["in"]),
             ("Clock input, Schmitt (in_s)", F.PADCOL["clk"]), ("VDD 5.0 V (dvdd)", F.PADCOL["vdd"]),
             ("VSS (dvss)", F.PADCOL["vss"])]
    ly, lx = -H - 1.05, -H - 0.55
    for j, (t, col) in enumerate(items):
        xx, yy = lx + (j % 3) * 2.45, ly - (j // 3) * 0.24
        vertex(L_leg, xx, yy - 0.07, 0.2, 0.14, "", box_style(blend(col, 0.3), col, 0.7))
        text(L_leg, xx + 0.28, yy, t, 6, F.INK, w=2.1, h=0.16, align="left")
    yy = ly - 0.48
    line(L_leg, (lx, yy), (lx + 0.2, yy), F.SLOT[7], 1.6)
    text(L_leg, lx + 0.28, yy, "Core power ring, 25 µm, Metal3/Metal4", 6, F.INK, w=2.15, h=0.16, align="left")
    line(L_leg, (lx + 2.45, yy), (lx + 2.65, yy), F.INK, 0.7, dash="4 2")
    text(L_leg, lx + 2.73, yy, "Core boundary (2.718 mm)", 6, F.INK, w=2.1, h=0.16, align="left")
    line(L_leg, (lx + 4.9, yy), (lx + 5.1, yy), F.INK, 1.1, end="block")
    text(L_leg, lx + 5.18, yy, "Pin numbering direction", 6, F.INK, w=1.8, h=0.16, align="left")
    text(L_leg, lx, yy - 0.42, "To scale: package, exposed pad, die, pad pitch (265 µm), core ring and macros. "
         "Pad cells are drawn 2.7× wider than their true 75 µm.<br>"
         f"Bond wires: {min(wl):.2f}–{max(wl):.2f} mm. Each die pad bonds to the QFN pin with the same number.",
         5.6, F.INK2, w=7.4, h=0.3, align="left")

    mxfile = ET.Element("mxfile", host="app.diagrams.net", type="device")
    diag = ET.SubElement(mxfile, "diagram", id="posit_rv_v3_padring", name="Pad ring + QFN-40")
    diag.append(root_model)
    ET.indent(mxfile)
    ET.ElementTree(mxfile).write(out, encoding="utf-8", xml_declaration=False)
    print("wrote", out, f"{_n[0]} cells, wires {min(wl):.2f}-{max(wl):.2f} mm")


if __name__ == "__main__":
    main()
