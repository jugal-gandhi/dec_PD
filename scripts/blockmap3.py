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
        (R(r"alu_out$"), "ALU logic"),
        (R(r"\.(alu_out_q|reg_out|reg_op)"), "Operand / writeback"),
        (R(r"\.(instr_|decoded_|is_|decoder_|compressed_instr)"), "Instruction decoder"),
        (R(r"\.(count_cycle|count_instr)"), "Perf counters"),
        (R(r"\.(irq|timer|do_waitirq)"), "Interrupt unit"),
        (R(r"\.(reg_pc|reg_next_pc|next_pc|current_pc)"), "PC / fetch"),
        (R(r"(^|\.)(mem_|pcpi_|prefetched_|clear_prefetched|last_mem)"), "Bus interface"),
        (R(r"."), "Control FSM"),
    ],
    "dsp_mac": [
        (R(r"^(a_q|b_q|a_s)$"), "Operand regs"),
        (R(r"^prod_q$"), "Multiplier array"),
        (R(r"^acc_q$"), "Accumulator"),
        (R(r"."), "Control / read mux"),
    ],
    "simd_alu": [
        (R(r"^(a_q|b_q)$"), "Operand regs"),
        (R(r"^res_q$"), "Result select"),
        (R(r"."), "Result select"),
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
        (R(r"^reg_O$"), "Regime value"),
        (R(r"^(EXP_O|Mantissa)$"), "Exponent / fraction"),
        (R(r"^(inf|S)$"), "Sign / NaR"),
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


CLOCK_PREFIX = ("clkbuf_", "clkload", "clkinv_", "delaybuf_")


def cones(cells, port_ins=()):
    """Named sources (flop outputs, input ports) feeding each cell, and the
    named sinks (flop data inputs, output ports) each cell reaches."""
    drivers = {}
    for name, c in cells.items():
        for n in c["outs"]:
            drivers[n] = name
    is_ff = {n: ("dff" in c["type"] or "latq" in c["type"] or "sdff" in c["type"]) for n, c in cells.items()}

    def src_of(net):
        d = drivers.get(net)
        b = base_net(net)
        if d is None:
            return ("port", b, net)
        if is_ff[d]:
            return ("ff", b, net)
        return None

    order, state = [], {}
    for start in cells:                       # iterative DFS topological order (comb only)
        if start in state:
            continue
        stack = [(start, 0)]
        while stack:
            n, i = stack.pop()
            if i == 0:
                if state.get(n) == 2:
                    continue
                state[n] = 1
            ins = cells[n]["ins"] if not is_ff[n] else []
            pushed = False
            while i < len(ins):
                d = drivers.get(ins[i])
                i += 1
                if d is not None and not is_ff[d] and state.get(d) is None:
                    stack.append((n, i))
                    stack.append((d, 0))
                    pushed = True
                    break
            if not pushed:
                state[n] = 2
                order.append(n)
    fin = {}
    for n in order:
        acc = set()
        for net in cells[n]["ins"]:
            sname = src_of(net)
            if sname:
                acc.add(sname[2])
            else:
                d = drivers.get(net)
                if d in fin and not is_ff[n] or (d in fin and is_ff[n] and False):
                    acc |= fin[d]
        fin[n] = acc if not is_ff[n] else set()
    # Flops: fan-in = their D cone
    for n in cells:
        if is_ff[n]:
            acc = set()
            for net in cells[n]["ins"]:
                sname = src_of(net)
                if sname:
                    acc.add(sname[2])
                elif drivers.get(net) in fin:
                    acc |= fin[drivers[net]]
            fin[n] = acc
    return fin, is_ff


def classify_cone(cells, group, base_label):
    """Datapath blocks whose internal wires lose their names: label each
    combinational cell from the named registers and ports in its fan-in."""
    fin, is_ff = cones(cells)
    out = dict(base_label)

    def bit(net):
        m = re.search(r"\[(\d+)\]\s*$", net)
        return int(m.group(1)) if m else 0

    for n, c in cells.items():
        if (is_ff[n] and n in out) or out.get(n) == "Clock tree":
            continue
        srcs = fin.get(n, set())
        bases = collections.Counter(base_net(x) for x in srcs)
        if group == "simd_alu":
            a = {bit(x) // 8 for x in srcs if base_net(x) == "a_q"}
            b = {bit(x) // 8 for x in srcs if base_net(x) == "b_q"}
            op = "op_q" in bases
            if not a and not b:
                lab = "Result select"
            elif op:
                lab = "Result select"
            elif b and len(a | b) == 1:
                lab = f"Lane {(a | b).pop()}"
            elif b:
                lab = "SAD adder tree"
            else:
                lab = "Popcount / CLZ"
        elif group == "dsp_mac":
            if "acc_q" in bases or "prod_q" in bases:
                lab = "Accumulator" if "addr" not in bases else "Control / read mux"
            elif "a_s" in bases or "b_q" in bases and "a_q" not in bases and "wdata" not in bases:
                lab = "Multiplier array"
            elif "a_s" in bases:
                lab = "Multiplier array"
            elif bases.keys() & {"a_q", "wdata"}:
                lab = "Operand regs"
            else:
                lab = "Control / read mux"
        else:
            continue
        out[n] = lab
    return out


def classify_reach(cells, base_label):
    """Purely combinational block: label each cell by the output ports it reaches."""
    drivers = {}
    sinks = collections.defaultdict(list)
    for name, c in cells.items():
        for n in c["outs"]:
            drivers[n] = name
        for n in c["ins"]:
            sinks[n].append(name)
    reach = {}

    def get(n, depth=0):
        if n in reach:
            return reach[n]
        reach[n] = set()
        acc = set()
        for net in cells[n]["outs"]:
            b = base_net(net)
            if b in ("reg_O", "EXP_O", "Mantissa", "inf", "S"):
                acc.add(b)
            for s_ in sinks[net]:
                acc |= get(s_, depth + 1) if depth < 400 else set()
        reach[n] = acc
        return acc

    import sys as _s
    _s.setrecursionlimit(20000)
    out = {}
    for n in cells:
        r = get(n)
        if {"reg_O"} & r and {"Mantissa", "EXP_O"} & r:
            lab = "Regime shifter"
        elif "reg_O" in r:
            lab = "Regime value"
        elif {"Mantissa", "EXP_O"} & r:
            lab = "Exponent / fraction"
        else:
            lab = "Sign / NaR"
        out[n] = lab
    return out


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
    generic = rules[-1][1] if rules and rules[-1][0].pattern == "." else None
    if generic:                                          # backward vote replaces the catch-all
        for name, c in cells.items():
            if label.get(name) != generic or name in base:
                continue
            frontier, seen = [name], {name}
            for _ in range(6):
                votes = collections.Counter()
                nxt = []
                for cell in frontier:
                    for n in cells[cell]["ins"]:
                        d = drivers.get(n)
                        if d is None or d in seen:
                            continue
                        seen.add(d)
                        if d in base and base[d] != generic:
                            votes[base[d]] += 1
                        elif d not in base:
                            nxt.append(d)
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
    for name, c in cells.items():                        # clock tree
        if name.startswith(CLOCK_PREFIX):
            label[name] = "Clock tree"
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
            lab0 = classify(mcells, RULES[cell])
            if cell in ("simd_alu", "dsp_mac"):
                lab0 = classify_cone(mcells, cell, {k: v for k, v in lab0.items() if v == "Clock tree"
                                                    or "dff" in mcells[k]["type"]})
            elif cell == "posit_decoder_32_2":
                lab0 = classify_reach(mcells, lab0)
            cache[cell] = (mdie, mcomps, lab0)
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
