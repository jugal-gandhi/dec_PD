#!/usr/bin/env python3
"""Plan the v3 SoC floorplan from the hardened macro sizes.

Reads SIZE from ip/v3/macros/<name>/lef/<name>.lef, arranges the blocks and
writes librelane/soc3/floorplan.yaml (DIE_AREA, CORE_AREA, MACROS,
PDN_MACRO_CONNECTIONS). Arrangement:
  left column   : main RAM, 4 SRAM macros
  right column  : scratchpad RAM, 4 SRAM macros
  centre, top   : CPU core; posit decoder on its right edge, level with
                  the CPU's ALU (the CPU is mirrored if its ALU sits on the
                  left half), so the two blocks are neighbours
  centre, middle: SPI flash controller and UART, the communication hub
                  between the SRAM banks, the CPU and the DSP array
  centre, bottom: DSP array (2x2 MAC slices), SIMD ALU beside it
The die is the smallest size whose 10-pad sides satisfy LibreLane's pad
placer grid rules (scripts mirror its Tcl arithmetic).
"""
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRAM_W, SRAM_H = 431.86, 484.88
EDGE, CORNER, PAD_W, PADS_PER_SIDE = 26.0, 355.0, 75.0, 10
RING = 442.0            # die edge to core edge (pads + core power ring)
M, G, CG = 40.0, 70.0, 110.0   # core margin, gap between blocks, channel beside SRAM columns


def lef_size(name):
    path = os.path.join(ROOT, "ip", "v3", "macros", name, "lef", f"{name}.lef")
    m = re.search(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", open(path).read())
    return float(m.group(1)), float(m.group(2))


def alu_centroid(w, h):
    """Centre of the ALU cells inside the hardened CPU macro (macro coords).

    ALU cells are those driving PicoRV32's named alu_* nets; their positions
    come from the macro DEF. Returns None if the views are missing.
    """
    d = os.path.join(ROOT, "ip", "v3", "macros", "cpu_core")
    nl, df = os.path.join(d, "nl", "cpu_core.nl.v"), os.path.join(d, "def", "cpu_core.def")
    if not (os.path.exists(nl) and os.path.exists(df)):
        return None
    alu = set()
    for m in re.finditer(r"^\s*gf180mcu_fd_sc\S+\s+(\S+)\s*\((.*?)\);", open(nl).read(), re.S | re.M):
        for pin, net in re.findall(r"\.(Z|ZN|Q|Y)\s*\(\s*(.*?)\s*\)", m.group(2)):
            if re.search(r"cpu\.alu_", net):
                alu.add(m.group(1).lstrip("\\").replace("\\", ""))
    txt = open(df).read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    xs, ys = [], []
    for m in re.finditer(r"-\s+(\S+)\s+\S+[^;]*?\+\s+PLACED\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", txt):
        if m.group(1).replace("\\", "") in alu:
            xs.append(int(m.group(2)) / units)
            ys.append(int(m.group(3)) / units)
    if len(xs) < 20:
        return None
    xs.sort()
    ys.sort()
    cx, cy = xs[len(xs) // 2], ys[len(ys) // 2]
    print(f"CPU ALU: {len(xs)} cells, median at ({cx:.0f}, {cy:.0f}) of {w:.0f} x {h:.0f} um")
    return cx, cy


def tcl_round(x):
    return int(math.floor(x + 0.5))


def pad_side_ok(S):
    fill = S - 2 * EDGE - 2 * CORNER - PADS_PER_SIDE * PAD_W
    if fill < 0:
        return False
    b = tcl_round(math.floor(fill / (PADS_PER_SIDE + 1) / 0.1) * 0.1 * 1000) // 1000
    ss = tcl_round((fill - b * (PADS_PER_SIDE - 1)) / 2 * 1000) // 1000
    return ss == tcl_round(math.floor(ss / 0.1) * 0.1 * 1000) // 1000 and b == ss


def main():
    cpu = lef_size("cpu_core")
    pos = lef_size("posit_decoder_32_2")
    dsp = lef_size("dsp_mac")
    simd = lef_size("simd_alu")
    spi = lef_size("spimemio")
    uart = lef_size("simpleuart")
    for n, s in (("cpu_core", cpu), ("posit", pos), ("dsp_mac", dsp), ("simd_alu", simd),
                 ("spimemio", spi), ("simpleuart", uart)):
        print(f"{n:12s} {s[0]:8.2f} x {s[1]:8.2f} um")

    GP = 45.0                       # CPU-to-posit spacing: direct neighbours
    row_a_w = cpu[0] + GP + pos[0]
    row_b_w = 2 * dsp[0] + simd[0] + 2 * G
    row_b_h = max(2 * dsp[1] + G, simd[1])
    row_c_w = spi[0] + uart[0] + G
    mid_w = max(row_a_w, row_b_w, row_c_w) + 2 * G
    mid_h = cpu[1] + row_b_h + max(spi[1], uart[1]) + 4 * G + 160  # room for glue logic
    col_h = 4 * SRAM_H + 3 * G
    core_w = 2 * M + 2 * SRAM_W + 2 * CG + mid_w
    core_h = max(col_h, mid_h) + 2 * M
    side_needed = max(core_w, core_h) * 1.04

    S = int(math.ceil(side_needed + 2 * RING))
    while not pad_side_ok(float(S)):
        S += 1
    core = S - 2 * RING
    c0, c1 = RING, S - RING
    print(f"die {S} um, core {core:.1f} um (needed {side_needed:.1f})")

    place = {}
    col_y0 = c0 + (core - col_h) / 2
    for i in range(4):
        y = col_y0 + i * (SRAM_H + G)
        place[f"u_soc.u_ram.sram{i}"] = ("sram", c0 + M, y, "N")
        place[f"u_soc.u_scratch.sram{i}"] = ("sram", c1 - M - SRAM_W, y, "N")

    xl = c0 + M + SRAM_W + CG
    xr = c1 - M - SRAM_W - CG
    mw = xr - xl
    y_top = c1 - M
    x0 = xl + (mw - row_a_w) / 2
    alu = alu_centroid(*cpu)
    cpu_orient = "N"
    alu_y = y_top - cpu[1] / 2
    if alu:
        ax, ay = alu
        if ax < cpu[0] / 2:         # ALU on the left half: mirror so it faces the posit decoder
            cpu_orient = "FN"
            ax = cpu[0] - ax
        alu_y = y_top - cpu[1] + ay
        print(f"CPU orientation {cpu_orient}; ALU {cpu[0] - ax:.0f} um from the posit-side edge")
    place["u_soc.u_cpu"] = ("cpu_core", x0, y_top - cpu[1], cpu_orient)
    py = min(max(alu_y - pos[1] / 2, y_top - cpu[1]), y_top - pos[1])
    place["u_soc.u_posit"] = ("posit_decoder_32_2", x0 + cpu[0] + GP, py, "N")

    # Bottom row: DSP array (2x2) and the SIMD ALU
    y_b = c0 + M
    xb = xl + (mw - row_b_w) / 2
    for k, (cx, cy) in enumerate(((0, 1), (1, 1), (0, 0), (1, 0))):   # DSP0 DSP1 / DSP2 DSP3
        place[f"u_soc.u_dsp{k}"] = ("dsp_mac", xb + cx * (dsp[0] + G), y_b + cy * (dsp[1] + G), "N")
    place["u_soc.u_simd"] = ("simd_alu", xb + 2 * (dsp[0] + G), y_b + row_b_h / 2 - simd[1] / 2, "N")
    # Middle row: SPI and UART, centred between the CPU and the DSP array
    hub_h = max(spi[1], uart[1])
    y_c = ((y_top - cpu[1]) + (y_b + row_b_h)) / 2 - hub_h / 2
    place["u_soc.u_spi"] = ("spimemio", xl + mw * 0.30 - spi[0] / 2, y_c + (hub_h - spi[1]) / 2, "N")
    place["u_soc.u_uart"] = ("simpleuart", xl + mw * 0.70 - uart[0] / 2, y_c + (hub_h - uart[1]) / 2, "N")

    sizes = {"sram": (SRAM_W, SRAM_H), "cpu_core": cpu, "posit_decoder_32_2": pos, "dsp_mac": dsp,
             "simd_alu": simd, "spimemio": spi, "simpleuart": uart}
    boxes = []
    for inst, (kind, x, y, o) in place.items():
        w, h = sizes[kind]
        assert c0 <= x and x + w <= c1 and c0 <= y and y + h <= c1, f"{inst} outside core"
        for other, (ox, oy, ow, oh) in boxes:
            sep = x + w + 20 <= ox or ox + ow + 20 <= x or y + h + 20 <= oy or oy + oh + 20 <= y
            assert sep, f"{inst} overlaps {other}"
        boxes.append((inst, (x, y, w, h)))

    def r(v):
        return round(v * 2) / 2   # 0.5 um grid

    out = ["# Generated by scripts/plan_floorplan3.py -- do not edit by hand.",
           f"FP_SIZING: absolute", f"DIE_AREA: [0, 0, {S}, {S}]",
           f"CORE_AREA: [{c0}, {c0}, {c1}, {c1}]", "", "MACROS:"]
    sram_insts = [i for i, p in place.items() if p[0] == "sram"]
    out += ["  gf180mcu_fd_ip_sram__sram512x8m8wm1:",
            "    gds: [pdk_dir::libs.ref/gf180mcu_fd_ip_sram/gds/gf180mcu_fd_ip_sram__sram512x8m8wm1.gds]",
            "    lef: [pdk_dir::libs.ref/gf180mcu_fd_ip_sram/lef/gf180mcu_fd_ip_sram__sram512x8m8wm1.lef]",
            "    vh: [pdk_dir::libs.ref/gf180mcu_fd_ip_sram/verilog/gf180mcu_fd_ip_sram__sram512x8m8wm1__blackbox_pp.v]",
            "    lib:"]
    for c in ("tt_025C_5v00", "ff_n40C_5v50", "ss_125C_4v50"):
        out.append(f"      \"*_{c}\": [pdk_dir::libs.ref/gf180mcu_fd_ip_sram/lib/gf180mcu_fd_ip_sram__sram512x8m8wm1__{c}.lib]")
    out.append("    instances:")
    for i in sram_insts:
        _, x, y, o = place[i]
        out += [f"      {i}:", f"        location: [{r(x)}, {r(y)}]", f"        orientation: {o}"]
    for kind in ("cpu_core", "posit_decoder_32_2", "dsp_mac", "simd_alu", "spimemio", "simpleuart"):
        base = f"dir::../../ip/v3/macros/{kind}"
        vh = f"dir::../../ip/posit_macro/vh/{kind}.v" if kind == "posit_decoder_32_2" else f"dir::../../ip/v3/vh/{kind}.v"
        out += [f"  {kind}:", f"    gds: [{base}/gds/{kind}.gds]", f"    lef: [{base}/lef/{kind}.lef]",
                f"    vh: [{vh}]", f"    nl: [{base}/nl/{kind}.nl.v]", "    lib:"]
        for c in ("tt_025C_5v00", "ff_n40C_5v50", "ss_125C_4v50"):
            out.append(f"      \"*_{c}\": [{base}/lib/{kind}.{c}.lib]")
        out.append("    instances:")
        for i, (k, x, y, o) in place.items():
            if k == kind:
                out += [f"      {i}:", f"        location: [{r(x)}, {r(y)}]", f"        orientation: {o}"]
    corner = S - 169.25
    for tag, (x, y) in (("tl", (26, corner)), ("tr", (corner, corner)), ("bl", (26, 26)), ("br", (corner, 26))):
        base = "dir::../../ip/dieart"
        out += [f"  dieart_{tag}:", f"    gds: [{base}/gds/dieart_{tag}.gds]", f"    lef: [{base}/lef/dieart_{tag}.lef]",
                f"    vh: [{base}/vh/dieart_{tag}.v]", "    lib:", f"      \"*\": [{base}/lib/dieart_{tag}.lib]",
                "    instances:", f"      art_{tag}:", f"        location: [{x}, {y}]", "        orientation: N"]
    out += ["", "PDN_MACRO_CONNECTIONS:"]
    out += [f"- \"{i} VDD VSS VDD VSS\"" for i in place]
    # Close-up render views around the block groups
    def union(names, pad=40.0):
        bs = [b for n, b in boxes if any(n.endswith(k) for k in names)]
        x0 = min(b[0] for b in bs) - pad
        y0 = min(b[1] for b in bs) - pad
        x1 = max(b[0] + b[2] for b in bs) + pad
        y1 = max(b[1] + b[3] for b in bs) + pad
        side = max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return [round(cx - side / 2, 1), round(cy - side / 2, 1), round(cx + side / 2, 1), round(cy + side / 2, 1)]
    views = {"cpu_posit": union(["u_cpu", "u_posit"]) + [4096],
             "hub": union(["u_spi", "u_uart"], pad=60) + [3072],
             "dsp_simd": union(["u_dsp0", "u_dsp1", "u_dsp2", "u_dsp3", "u_simd"]) + [4096],
             "posit": union(["u_posit"], pad=30) + [3072]}
    json.dump(views, open(os.path.join(ROOT, "librelane", "soc3", "render_views.json"), "w"), indent=1)

    path = os.path.join(ROOT, "librelane", "soc3", "floorplan.yaml")
    open(path, "w").write("\n".join(out) + "\n")
    print(f"wrote {path}: {len(place)} macro instances")


if __name__ == "__main__":
    main()
