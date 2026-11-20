#!/usr/bin/env python3
"""Attribute every cell of the signed-off (flat) posit<32,2> decoder netlist to an
architectural component, by bit-parallel simulation and signature matching.

1. Simulate the gate-level netlist on random inputs (64 vectors per machine word).
2. Simulate the RTL (posit_decoder_32_2.v) at signal level: the AND-OR outputs a_k,
   comparator outputs c_k, shifter outputs d_k and the output fields.
3. A net whose signature equals an RTL signal (or its complement) carries that signal.
4. Each logic cell takes the component of the first matched signals downstream of it
   (stopping at matched nets), so the cells between two component boundaries go to the
   component that produces the later boundary.
Usage: comp_attrib.py <netlist.v[.gz]> <out.json> [words]
"""
import gzip
import json
import re
import sys
from collections import defaultdict, deque

import numpy as np

SC = "gf180mcu_fd_sc_mcu7t5v0__"
M = np.uint64(0xFFFFFFFFFFFFFFFF)


def fn(base, p):
    a = lambda *k: [p[x] for x in k if x in p]
    AND = lambda xs: np.bitwise_and.reduce(xs)
    OR = lambda xs: np.bitwise_or.reduce(xs)
    if base in ("buf", "clkbuf", "dlya", "dlyb", "dlyc", "dlyd"):
        return p["I"]
    if base in ("inv", "clkinv"):
        return ~p["I"]
    if base == "tiel":
        return np.zeros_like(next(iter(p.values()))) if p else None
    if base in ("and2", "and3", "and4"):
        return AND(a("A1", "A2", "A3", "A4"))
    if base in ("nand2", "nand3", "nand4"):
        return ~AND(a("A1", "A2", "A3", "A4"))
    if base in ("or2", "or3", "or4"):
        return OR(a("A1", "A2", "A3", "A4"))
    if base in ("nor2", "nor3", "nor4"):
        return ~OR(a("A1", "A2", "A3", "A4"))
    if base == "xor2":
        return p["A1"] ^ p["A2"]
    if base == "xnor2":
        return ~(p["A1"] ^ p["A2"])
    if base == "mux2":
        return (p["S"] & p["I1"]) | (~p["S"] & p["I0"])
    if base == "mux4":
        lo = (p["S0"] & p["I1"]) | (~p["S0"] & p["I0"])
        hi = (p["S0"] & p["I3"]) | (~p["S0"] & p["I2"])
        return (p["S1"] & hi) | (~p["S1"] & lo)
    if base.startswith("aoi") or base.startswith("oai"):
        groups = {"A": a("A1", "A2", "A3", "A4"), "B": a("B", "B1", "B2", "B3"), "C": a("C", "C1", "C2")}
        inner, outer = (AND, OR) if base.startswith("aoi") else (OR, AND)
        terms = [inner(v) if len(v) > 1 else v[0] for v in groups.values() if v]
        return ~outer(terms)
    raise ValueError(f"no model for {base}")


def parse(path):
    op = gzip.open if path.endswith(".gz") else open
    txt = op(path, "rt").read()
    cells = []
    for m in re.finditer(r"\b" + SC + r"(\w+)\s+(\\?\S+)\s*\((.*?)\);", txt, re.S):
        base = re.sub(r"_\d+$", "", m.group(1))
        if base.startswith(("fill", "endcap", "antenna")) or base == "filltie":
            continue
        pins = dict(re.findall(r"\.(\w+)\(([^)]*)\)", m.group(3)))
        pins = {k: v.strip() for k, v in pins.items() if v.strip()}
        out = [k for k in pins if k in ("Z", "ZN")]
        cells.append(dict(cell=m.group(1), base=base, name=m.group(2).lstrip("\\"),
                          ins={k: v for k, v in pins.items() if k not in ("Z", "ZN")},
                          out=pins[out[0]] if out else None))
    assigns = re.findall(r"assign\s+(\S+)\s*=\s*(\S+?)\s*;", txt)
    return cells, assigns


def rtl(x):
    """signal-level model of posit_decoder_32_2.v on packed bit-vectors (list of 32 arrays)"""
    sign, rc = x[31], x[30]
    d = [x[i] for i in range(30)]                  # d[i] = bit i of d5
    sig = {}
    windows = [(4, 16, 16), (3, 9, 8), (2, 5, 4), (1, 3, 2)]
    for k, w, sh in windows:
        win = d[29 - w + 1:30]
        a = (rc & np.bitwise_and.reduce(win)) | (~rc & np.bitwise_or.reduce(win))
        c = ~(a ^ rc)
        sig[f"a{k}"], sig[f"c{k}"] = a, c
        d = [(c & (d[i - sh] if i >= sh else np.zeros_like(rc))) | (~c & d[i]) for i in range(30)]
        for i in range(30):
            sig[f"d{k - 1 if k else 0}_{i}" if False else f"d{k-1}[{i}]"] = d[i]
    a0 = d[29]
    c0 = ~(a0 ^ rc)
    sig["c0"] = c0
    d = [(c0 & (d[i - 1] if i >= 1 else np.zeros_like(rc))) | (~c0 & d[i]) for i in range(30)]
    for i in range(30):
        sig[f"dfin[{i}]"] = d[i]
    return sig, d


def main():
    nl, out = sys.argv[1], sys.argv[2]
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    cells, assigns = parse(nl)
    rng = np.random.default_rng(1)
    x = [rng.integers(0, 2**63, W, dtype=np.uint64) * np.uint64(2) + rng.integers(0, 2, W, dtype=np.uint64)
         for _ in range(32)]
    # bias half the words towards long regime runs so deep shifter stages switch
    for w in range(W // 2):
        run = int(rng.integers(1, 30))
        r0 = int(rng.integers(0, 2))
        for i in range(30, 30 - run, -1):
            x[i][w] = M if r0 else np.uint64(0)
    val = {f"posit_in[{i}]": x[i] for i in range(32)}
    # ports may be renamed by input buffers; resolve by simulation order
    by_out = {c["out"]: c for c in cells if c["out"]}
    pending = deque(cells)
    guard = 0
    while pending and guard < len(cells) ** 2:
        c = pending.popleft()
        guard += 1
        if c["out"] is None:
            continue
        if all(v in val for v in c["ins"].values()):
            val[c["out"]] = fn(c["base"], {k: val[v] for k, v in c["ins"].items()}) if c["base"] != "tiel" \
                else np.zeros(W, dtype=np.uint64)
        else:
            pending.append(c)
    for lhs, rhs in assigns:
        if rhs in val:
            val[lhs] = val[rhs]
    sig, dfin = rtl(x)
    sign, rc = x[31], x[30]
    k = [sig["c4"], sig["c3"], sig["c2"], sig["c1"], sig["c0"]]
    eq = ~(rc ^ sign)
    exp_reg = [(eq & ~k[4 - i]) | (~eq & k[4 - i]) for i in range(5)] + [eq]   # reg_O[i]
    zero = (k[0] & sign) | ~k[0]
    golden = {f"reg_O[{i}]": exp_reg[i] for i in range(6)}
    golden.update({"EXP_O[1]": dfin[28], "EXP_O[0]": dfin[27], "S": sign,
                   **{f"Mantissa[{i}]": dfin[i] for i in range(27)}, "Mantissa[27]": zero})
    bad = [n for n, g in golden.items() if n not in val or not np.array_equal(val[n], g)]
    print(f"cells {len(cells)}  outputs checked {len(golden)}  mismatches {len(bad)} {bad[:6]}")
    # signature matching
    key = lambda v: v.tobytes()
    lookup = {}
    for name, v in sig.items():
        lookup.setdefault(key(v), name)
        lookup.setdefault(key(~v), "~" + name)
    for i in range(32):
        lookup.setdefault(key(x[i]), f"in[{i}]")
        lookup.setdefault(key(~x[i]), f"~in[{i}]")
    net_sig = {n: lookup.get(key(v)) for n, v in val.items()}
    # component of an RTL signal
    def comp_of(s):
        s = s.lstrip("~")
        if s.startswith("in["):
            return "input"
        if s[0] == "a":
            return f"AND-OR network|{s[1]}"
        if s[0] == "c":
            return f"Boundary comparator|{s[1]}"
        if s.startswith("dfin"):
            return "In-line shifter|0"
        if s[0] == "d":
            return f"In-line shifter|{int(s[1]) + 1}"
        return "other"
    readers = defaultdict(list)
    for c in cells:
        for v in c["ins"].values():
            readers[v].append(c)
    outputs = set(golden)
    for lhs, rhs in assigns:
        if lhs in outputs:
            outputs.add(rhs)
    attrib = {}

    def downstream(net, seen):
        """components of the first matched signals (or outputs) reached from net"""
        res = set()
        for r in readers.get(net, []):
            o = r["out"]
            if o is None or o in seen:
                continue
            seen.add(o)
            s = net_sig.get(o)
            if s and comp_of(s) not in ("input", "other"):
                res.add(comp_of(s))
            elif o in outputs or any(o == rhs for _, rhs in assigns if _ in golden):
                res.add("Output encoding|-")
                res |= downstream(o, seen)
            else:
                res |= downstream(o, seen)
        return res

    for c in cells:
        o = c["out"]
        s = net_sig.get(o)
        if c["base"] in ("buf", "clkbuf", "dlya", "dlyb", "dlyc", "dlyd", "inv", "clkinv") and \
                net_sig.get(next(iter(c["ins"].values()), None)) is not None and s is not None and \
                s.lstrip("~") == (net_sig.get(next(iter(c["ins"].values()))) or "").lstrip("~"):
            comp = "I/O buffers|-" if c["name"].startswith(("input", "output")) else "Timing-repair buffers|-"
            attrib[c["name"]] = dict(cell=c["cell"], comp=comp, sig=s)
            continue
        if s and comp_of(s) not in ("input", "other"):
            attrib[c["name"]] = dict(cell=c["cell"], comp=comp_of(s), sig=s)
            continue
        ds = downstream(o, {o})
        fams = {d.split("|")[0] for d in ds}
        if not ds:
            comp = "Output encoding|-"
        elif fams == {"Boundary comparator"}:
            # cells that only feed the count_k drivers form the AND-OR reduction trees
            stages = sorted(d.split("|")[1] for d in ds)
            comp = "AND-OR network|" + (stages[0] if len(stages) == 1 else "*")
        elif len(fams) == 1:
            comp = next(iter(fams)) + "|" + (next(iter(ds)).split("|")[1] if len(ds) == 1 else "*")
        else:
            comp = "Shared|" + "+".join(sorted(fams))
        attrib[c["name"]] = dict(cell=c["cell"], comp=comp, sig=s)
    # owner of each buffer: the first non-buffer driver upstream (or the input port)
    drv = {c["out"]: c for c in cells if c["out"]}
    bufs = ("buf", "clkbuf", "dlya", "dlyb", "dlyc", "dlyd")
    chain = bufs + ("inv", "clkinv")
    for c in cells:
        if c["base"] not in bufs and not attrib[c["name"]]["comp"].startswith(("Timing-repair", "I/O")):
            continue
        net, hops = next(iter(c["ins"].values())), 0
        while net in drv and drv[net]["base"] in chain and \
                attrib[drv[net]["name"]]["comp"].startswith(("Timing-repair", "I/O")) and hops < 50:
            net, hops = next(iter(drv[net]["ins"].values())), hops + 1
        if net in drv:
            attrib[c["name"]]["owner"] = drv[net]["name"]
        else:
            attrib[c["name"]]["owner"] = "port:" + net
    summary = defaultdict(int)
    for v in attrib.values():
        summary[v["comp"]] += 1
    found = sorted({s.lstrip("~") for s in net_sig.values() if s and not s.lstrip("~").startswith("in[")})
    json.dump(dict(attrib=attrib, mismatches=bad, matched_signals=found), open(out, "w"), indent=1)
    print("matched RTL signals:", len(found), [f for f in found if not f.startswith("d")])
    for k2, v in sorted(summary.items()):
        print(f"  {k2:45s} {v}")


if __name__ == "__main__":
    main()
