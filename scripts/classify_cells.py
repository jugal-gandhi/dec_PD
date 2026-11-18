#!/usr/bin/env python3
"""Assign every standard cell of the final netlist to a functional block.

Yosys keeps the hierarchical names of named wires (e.g. u_soc.soc.cpu.alu_out),
so a cell whose output drives such a wire belongs to that block. Cells that
drive anonymous nets (helper gates, resizer buffers) take the majority label
of their neighbours, propagated through the netlist for a few rounds.

Usage: classify_cells.py <final.nl.v> <out.json>
"""
import collections
import json
import re
import sys

RULES = [  # (substring in net name, block label) -- first match wins
    ("cpu.cpuregs", "Register file"),
    ("pcpi_mul", "Multiplier"),
    ("pcpi_div", "Divider"),
    ("cpu.alu", "ALU"),
    ("spimemio", "SPI flash controller"),
    ("simpleuart", "UART"),
    ("u_soc.posit_in", "Bus peripherals"),
    ("u_soc.gpio", "Bus peripherals"),
    ("u_soc.iomem", "Bus peripherals"),
    ("u_soc.soc.cpu.", "CPU control"),
]
OUT_PINS = {"Z", "ZN", "Q", "QN", "Y"}
SKIP = ("fill", "endcap", "tap", "antenna", "dieart", "sram", "posit_decoder", "fd_io")


def rule(net):
    for key, label in RULES:
        if key in net:
            return label
    return None


def main():
    text = open(sys.argv[1]).read()
    inst_re = re.compile(r"^\s*(\S+)\s+(\S+)\s*\((.*?)\);", re.S | re.M)
    pin_re = re.compile(r"\.(\w+)\s*\(\s*(.*?)\s*\)\s*(?:,|$)", re.S)
    cells = {}
    net_cells = collections.defaultdict(set)
    for m in inst_re.finditer(text):
        ctype, name, body = m.group(1), m.group(2), m.group(3)
        if ctype in ("module", "wire", "input", "output", "inout", "assign") or not ctype.startswith("gf180"):
            continue
        if any(k in ctype for k in SKIP):
            continue
        pins = {p: n.strip() for p, n in pin_re.findall(body)}
        outs = [n for p, n in pins.items() if p in OUT_PINS]
        ins = [n for p, n in pins.items() if p not in OUT_PINS and p not in ("VDD", "VSS", "VNW", "VPW")]
        cells[name] = {"type": ctype, "outs": outs, "ins": ins, "label": None}
        for n in outs + ins:
            net_cells[n].add(name)

    for c in cells.values():                       # pass 1: named output nets
        for n in c["outs"]:
            lab = rule(n)
            if lab:
                c["label"] = lab
                break

    # Pass 2: a helper gate belongs to the named signal its output cone feeds.
    # Walk forward (output -> sink cells) to the nearest labelled cells.
    sinks = collections.defaultdict(set)           # net -> cells reading it
    for name, c in cells.items():
        for n in c["ins"]:
            sinks[n].add(name)
    base = {n: c["label"] for n, c in cells.items()}
    for name, c in cells.items():
        if base[name]:
            continue
        frontier, seen = {name}, {name}
        for _depth in range(10):
            votes = collections.Counter()
            nxt = set()
            for cell in frontier:
                for n in cells[cell]["outs"]:
                    for s_ in sinks[n]:
                        if s_ in seen:
                            continue
                        seen.add(s_)
                        if base[s_]:
                            votes[base[s_]] += 1
                        else:
                            nxt.add(s_)
            if votes:
                c["label"] = votes.most_common(1)[0][0]
                break
            frontier = nxt
            if not frontier:
                break

    # Pass 3: anything left (e.g. cells driving pads) takes its inputs' label.
    for _ in range(4):
        for name, c in cells.items():
            if c["label"]:
                continue
            votes = collections.Counter()
            for n in c["ins"]:
                lab = rule(n)
                if lab:
                    votes[lab] += 2
                for other in net_cells[n]:
                    if other != name and cells[other]["label"]:
                        votes[cells[other]["label"]] += 1
            if votes:
                c["label"] = votes.most_common(1)[0][0]

    out = {n: (c["label"] or "Other glue") for n, c in cells.items()}
    json.dump(out, open(sys.argv[2], "w"))
    for lab, k in collections.Counter(out.values()).most_common():
        print(f"{k:6d}  {lab}")


if __name__ == "__main__":
    main()
