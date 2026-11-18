#!/usr/bin/env python3
"""Write the size of every standard cell found in a GDS file.

The size is the bounding box of the cell's PR boundary (GF180: layer 0/0);
cells without one fall back to the bounding box of all their boundaries.
Usage: gds_cell_sizes.py <in.gds[.gz]> [more.gds ...] <out.json>
"""
import gzip
import json
import struct
import sys


def scan(path, sizes):
    op = gzip.open if path.endswith(".gz") else open
    data = op(path, "rb").read()
    i, name, layer, dtype, in_bnd = 0, None, None, None, False
    unit = 1e-3
    prb, anyb = {}, {}
    while i + 4 <= len(data):
        ln, rt, _dt = struct.unpack(">HBB", data[i:i + 4])
        if ln == 0:
            break
        body = data[i + 4:i + ln]
        i += ln
        if rt == 0x03:                              # UNITS
            # 8-byte GDS reals: user units per db unit, metres per db unit
            def real8(b):
                sign = -1 if b[0] & 0x80 else 1
                exp = (b[0] & 0x7F) - 64
                mant = int.from_bytes(b[1:8], "big") / (1 << 56)
                return sign * mant * 16 ** exp
            unit = real8(body[8:16]) * 1e6         # microns per db unit
        elif rt == 0x06:
            name = body.rstrip(b"\0").decode()
        elif rt == 0x08:                            # BOUNDARY
            in_bnd, layer, dtype = True, None, None
        elif rt == 0x0D and in_bnd:
            layer = struct.unpack(">h", body)[0]
        elif rt == 0x0E and in_bnd:
            dtype = struct.unpack(">h", body)[0]
        elif rt == 0x10 and in_bnd:
            pts = struct.unpack(">%di" % (len(body) // 4), body)
            xs, ys = pts[0::2], pts[1::2]
            box = (min(xs), min(ys), max(xs), max(ys))
            for store, ok in ((anyb, True), (prb, layer == 0 and dtype == 0)):
                if ok:
                    b = store.get(name)
                    store[name] = box if b is None else (min(b[0], box[0]), min(b[1], box[1]),
                                                         max(b[2], box[2]), max(b[3], box[3]))
        elif rt == 0x11:
            in_bnd = False
    for n in anyb:
        if "__" not in n or not n.startswith("gf180mcu_fd_sc"):
            continue
        b = prb.get(n, anyb[n])
        sizes[n] = [round((b[2] - b[0]) * unit, 3), round((b[3] - b[1]) * unit, 3)]


def main():
    sizes = {}
    for p in sys.argv[1:-1]:
        scan(p, sizes)
    json.dump(sizes, open(sys.argv[-1], "w"), indent=0, sort_keys=True)
    print(f"{len(sizes)} cell types; e.g.", list(sizes.items())[:3])


if __name__ == "__main__":
    main()
