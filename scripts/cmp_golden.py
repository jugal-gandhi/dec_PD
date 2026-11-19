#!/usr/bin/env python3
"""Reference model of the LDD decoder outputs for posit<32,es> and test vectors.

Output word: {sign, regi[5:0], expo[es-1:0], frac[fs-1:0], allone, allzero}, fs = 29 - es.
Negative inputs are two's-complemented first (as in the LDD design). regi is the regime
value k in two's complement. When fewer than es bits follow the regime, the available
bits form the low exponent bits (the upstream convention). Fraction bits are left-aligned.
Usage: cmp_golden.py <es> <out_dir> [random_count]
"""
import os
import random
import sys

N = 32
M31 = (1 << 31) - 1


def decode(x, es):
    fs = N - es - 3
    sign = x >> 31
    low = x & M31
    t = ((~low) + 1) & M31 if sign else low
    r0 = (t >> 30) & 1
    m = 1
    while m < 31 and ((t >> (30 - m)) & 1) == r0:
        m += 1
    if m == 31:                                   # no terminating bit
        if r0:
            return sign, 30, 0, 0, 1, 0
        return sign, 63, 0, 0, 0, 1
    j = 30 - m                                    # bits left after the terminator
    k = (m - 1) if r0 else (-m) & 63
    expo = (t >> (j - es)) & ((1 << es) - 1) if j >= es else t & ((1 << j) - 1)
    frac = 0
    for q in range(fs):
        p = j + q - 29
        if p >= 0:
            frac |= ((t >> p) & 1) << q
    return sign, k, expo, frac, 0, 0


def pack(o, es):
    fs = N - es - 3
    s, k, e, f, a1, a0 = o
    return (((((s << 6 | k) << es | e) << fs | f) << 1 | a1) << 1) | a0


def main():
    es, out = int(sys.argv[1]), sys.argv[2]
    cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    os.makedirs(out, exist_ok=True)
    rnd = random.Random(2026)
    vec = [0, 0x80000000, 0x7FFFFFFF, 0xFFFFFFFF, 0x00000001, 0x80000001, 0x40000000, 0xC0000000]
    for m in range(1, 31):                        # every regime length, both signs and polarities
        for r0 in (0, 1):
            for _ in range(40):
                body = rnd.getrandbits(31)
                run = ((1 << m) - 1) << (31 - m) if r0 else 0
                term = (0 if r0 else 1) << (30 - m) if m < 31 else 0
                rest = body & ((1 << (30 - m)) - 1) if m < 30 else 0
                v = run | term | rest
                vec += [v, v | 0x80000000]
    vec += [rnd.getrandbits(32) for _ in range(cnt)]
    with open(os.path.join(out, "vin.hex"), "w") as f:
        f.write("\n".join(f"{v:08x}" for v in vec) + "\n")
    with open(os.path.join(out, "vexp.hex"), "w") as f:
        f.write("\n".join(f"{pack(decode(v, es), es):010x}" for v in vec) + "\n")
    print(len(vec))


if __name__ == "__main__":
    main()
