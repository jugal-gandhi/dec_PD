#!/usr/bin/env python3
"""Functional-block map of the v3 SoC: every standard cell, in every hard
macro and in the top level, gets a block label and a die-level rectangle.

A cell whose output drives a named net takes that net's block (rules below,
matched on the net name with bit indices removed). Helper gates feeding
named logic take the majority label of the cells they drive; leftovers take
the label of their neighbours. Placements come from the DEF files.

Usage: blockmap3.py <results-soc3 dir> <cell_sizes.json> <out.json>
"""
import collections
import gzip
import json
import os
import re
import sys

R = re.compile
RULES = {
    "cpu_core": [
        (R(r"cpuregs"), "Register file"),
        (R(r"pcpi_mul"), "Multiplier"),
        (R(r"pcpi_div"), "Divider"),
        (R(r"alu_add_sub"), "ALU adder"),
        (R(r"alu_sh[lr]"), "Barrel shifter"),
        (R(r"alu_(eq|lt|ltu|lts)"), "ALU comparator"),
        (R(r"alu_"), "ALU logic"),
        (R(r"\.(instr_|decoded_|is_|decoder_)"), "Instruction decoder"),
        (R(r"\.(count_cycle|count_instr)"), "Perf counters"),
        (R(r"\.irq"), "Interrupt unit"),
        (R(r"\.(reg_pc|reg_next_pc|next_pc|current_pc)"), "PC / fetch"),
        (R(r"\.(mem_|pcpi_)"), "Bus interface"),
        (R(r"\.(reg_op|reg_out|reg_sh|cpu_state|latched_|dbg_|trap)"), "Control FSM"),
        (R(r"."), "Control FSM"),
    ],
    "dsp_mac": [
        (R(r"^(product|prod_q)$"), "Multiplier array"),
        (R(r"^(acc_sum|acc_q|prod_x)$"), "Accumulator"),
        (R(r"^(a_q|b_q|a_s|count_q|v1|v2|m1|m2)$"), "Pipeline regs"),
        (R(r"^rdata$"), "Pipeline regs"),
    ],
    "simd_alu": [
        (R(r"^lane0\.|^(add0|sub0|sat0|ad0|mn0|mx0)$"), "Lane 0"),
        (R(r"^lane1\.|^(add1|sub1|sat1|ad1|mn1|mx1)$"), "Lane 1"),
        (R(r"^lane2\.|^(add2|sub2|sat2|ad2|mn2|mx2)$"), "Lane 2"),
        (R(r"^lane3\.|^(add3|sub3|sat3|ad3|mn3|mx3)$"), "Lane 3"),
        (R(r"u_popcount|^popcnt$"), "Popcount"),
        (R(r"u_clz|^clz$"), "Leading-zero count"),
        (R(r"^sad$"), "SAD adder tree"),
        (R(r"."), "SIMD registers"),
    ],
    "spimemio": [
        (R(r"^xfer\."), "SPI shift engine"),
        (R(r"^(config_|softreset)"), "Flash config"),
        (R(r"^(buffer|rdata|rd_)"), "XIP read buffer"),
        (R(r"."), "XIP control"),
    ],
    "simpleuart": [
        (R(r"^recv_"), "UART RX"),
        (R(r"^send_"), "UART TX"),
        (R(r"^cfg_divider"), "Baud generator"),
        (R(r"."), "UART RX"),
    ],
    "posit_decoder_32_2": [
        (R(r"^(d[0-5]|d_and_[0-4]|count[0-4])$"), "Regime shifter"),
        (R(r"^(k|reg_O)$"), "Regime value"),
        (R(r"^(EXP_O|Mantissa)$"), "Exponent / fraction"),
        (R(r"^(inf|zero_check|S|sign)$"), "Sign / NaR"),
    ],
    "top": [
        (R(r"u_soc\.posit"), "Posit I/O regs"),
        (R(r"u_soc\.(gpio|io_)"), "Bus / GPIO glue"),
        (R(r"u_soc\.u_(ram|scratch)"), "SRAM interface"),
        (R(r"u_soc\."), "Bus / GPIO glue"),
        (R(r"."), "Pad interface"),
    ],
}
OUT_PINS = {"Z", "ZN", "Q", "QN", "Y", "CO", "S"}
SKIP = ("fill", "endcap", "tap", "antenna", "dieart", "sram", "fd_io")


def base_net(n):
    n = n.strip().lstrip("\\")
    return re.sub(r"\s*\[\d+\]$", "", n).strip()


def read_netlist(path, module):
    op = gzip.open if path.endswith(".gz") else open
    text = op(path, "rt").read()
    m = re.search(r"^module\s+%s\b.*?^endmodule" % re.escape(module), text, re.S | re.M)
    text = m.group(0) if m else text
    inst_re = re.compile(r"^\s*(gf180mcu_fd_sc\S+)\s+(\S+)\s*\((.*?)\);", re.S | re.M)
    pin_re = re.compile(r"\.(\w+)\s*\(\s*(.*?)\s*\)\s*(?:,|$)", re.S)
    cells = {}
    for mm in inst_re.finditer(text):
        ctype, name, body = mm.groups()
        if any(k in ctype for k in SKIP):
            continue
        pins = {p: n.strip() for p, n in pin_re.findall(body)}
        outs = [n for p, n in pins.items() if p in OUT_PINS]
        ins = [n for p, n in pins.items() if p not in OUT_PINS and p not in ("VDD", "VSS", "VNW", "VPW")]
        cells[name.lstrip("\\").replace("\\", "")] = {"type": ctype, "outs": outs, "ins": ins}
    return cells


def classify(cells, rules):
    def rule(net):
        b = base_net(net)
        for rx, lab in rules:
            if rx.search(b):
                return lab
        return None

    # Nets driven by a cell named like a public wire
    named = {}
    for c in cells.values():
        for n in c["outs"]:
            if not base_net(n).startswith("_") and "$" not in n:
                lab = rule(n)
                if lab:
                    named[n] = lab
    label = {}
    for name, c in cells.items():
        for n in c["outs"]:
            if n in named:
                label[name] = named[n]
                break
    sinks = collections.defaultdict(list)
    drivers = {}
    for name, c in cells.items():
        for n in c["ins"]:
            sinks[n].append(name)
        for n in c["outs"]:
            drivers[n] = name
    base = dict(label)
    for name, c in cells.items():                       # forward cone vote
        if name in base:
            continue
        frontier, seen = [name], {name}
        for _ in range(12):
            votes = collections.Counter()
            nxt = []
            for cell in frontier:
                for n in cells[cell]["outs"]:
                    for s_ in sinks[n]:
                        if s_ in seen:
                            continue
                        seen.add(s_)
                        if s_ in base:
                            votes[base[s_]] += 1
                        else:
                            nxt.append(s_)
            if votes:
                label[name] = votes.most_common(1)[0][0]
                break
            frontier = nxt[:400]
            if not frontier:
                break
    for _ in range(6):                                   # neighbours
        changed = False
        for name, c in cells.items():
            if name in label:
                continue
            votes = collections.Counter()
            for n in c["ins"]:
                lab = named.get(n) or rule(n)
                if lab:
                    votes[lab] += 2
                d = drivers.get(n)
                if d in label:
                    votes[label[d]] += 1
            for n in c["outs"]:
                for s_ in sinks[n]:
                    if s_ in label:
                        votes[label[s_]] += 1
            if votes:
                label[name] = votes.most_common(1)[0][0]
                changed = True
        if not changed:
            break
    return label


def read_def(path):
    op = gzip.open if path.endswith(".gz") else open
    txt = op(path, "rt").read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    da = re.search(r"DIEAREA\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", txt)
    die = [int(v) / units for v in da.groups()]
    sec = txt[txt.index("\nCOMPONENTS"):txt.index("END COMPONENTS")]
    comps = {}
    for m in re.finditer(r"-\s+(\S+)\s+(\S+)[^;]*?\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)", sec):
        comps[m.group(1).replace("\\", "")] = (m.group(2), int(m.group(3)) / units,
                                               int(m.group(4)) / units, m.group(5))
    return die, comps


def main():
    res, sizes_path, out = sys.argv[1:4]
    sizes = json.load(open(sizes_path))
    die, top = read_def(os.path.join(res, "soc3_chip_top.def.gz"))
    rects = []          # [x0, y0, x1, y1, group, label]
    macros = []         # [inst, cell, x0, y0, x1, y1]
    counts = collections.Counter()

    def size_of(cell):
        return sizes.get(cell)

    # Top-level glue
    nl_top = os.path.join(res, "soc3_chip_top.nl.v.gz")
    if os.path.exists(nl_top):
        cells = read_netlist(nl_top, "soc3_chip_top")
        lab = classify(cells, RULES["top"])
        for name, l in lab.items():
            c = top.get(name)
            s = c and size_of(c[0])
            if s:
                rects.append([c[1], c[2], c[1] + s[0], c[2] + s[1], "top", l])
                counts[("top", l)] += 1

    lef_size = {}
    for m in os.listdir(os.path.join(res, "macros")):
        lp = os.path.join(res, "macros", m, f"{m}.lef")
        if os.path.exists(lp):
            g = re.search(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", open(lp).read())
            lef_size[m] = (float(g.group(1)), float(g.group(2)))
    lef_size["gf180mcu_fd_ip_sram__sram512x8m8wm1"] = (431.86, 484.88)

    cache = {}
    for inst, (cell, x, y, orient) in top.items():
        if cell not in lef_size:
            continue
        w, h = lef_size[cell]
        if orient in ("E", "W", "FE", "FW"):
            w, h = h, w
        macros.append([inst, cell, x, y, x + w, y + h])
        mdir = os.path.join(res, "macros", cell)
        if not os.path.isdir(mdir):
            continue
        if cell not in cache:
            mdie, mcomps = read_def(os.path.join(mdir, f"{cell}.def.gz"))
            mcells = read_netlist(os.path.join(mdir, f"{cell}.nl.v.gz"), cell)
            cache[cell] = (mdie, mcomps, classify(mcells, RULES[cell]))
        mdie, mcomps, lab = cache[cell]
        mw, mh = mdie[2] - mdie[0], mdie[3] - mdie[1]
        for name, l in lab.items():
            c = mcomps.get(name)
            s = c and size_of(c[0])
            if not s:
                continue
            lx, ly = c[1] - mdie[0], c[2] - mdie[1]
            if orient == "N":
                gx0, gy0, gx1, gy1 = x + lx, y + ly, x + lx + s[0], y + ly + s[1]
            elif orient == "S":
                gx0, gy0 = x + mw - lx - s[0], y + mh - ly - s[1]
                gx1, gy1 = gx0 + s[0], gy0 + s[1]
            elif orient == "FN":
                gx0, gy0, gx1, gy1 = x + mw - lx - s[0], y + ly, x + mw - lx, y + ly + s[1]
            elif orient == "FS":
                gx0, gy0, gx1, gy1 = x + lx, y + mh - ly - s[1], x + lx + s[0], y + mh - ly
            else:
                continue
            rects.append([round(gx0, 3), round(gy0, 3), round(gx1, 3), round(gy1, 3), cell, l])
            counts[(cell, l)] += 1

    json.dump({"die": die, "macros": macros, "rects": rects,
               "counts": [[g, l, n] for (g, l), n in sorted(counts.items())]}, open(out, "w"))
    for (g, l), n in sorted(counts.items()):
        print(f"{g:20s} {l:22s} {n:7d}")
    print(len(rects), "cell rectangles,", len(macros), "macros")


if __name__ == "__main__":
    main()
