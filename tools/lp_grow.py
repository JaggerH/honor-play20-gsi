#!/usr/bin/env python3
"""Grow one logical partition over the partition that directly follows it in
`super`, by editing the LP metadata (both copies), and emit a sparse image
that rewrites only the metadata blocks.

Used to fit a ~3.3 GB GSI into a device whose `system` extent is 2.4 GB:
`system` is grown over the adjacent, GSI-irrelevant `hw_product`, which is
left as a zero-length partition (fs_mgr skips zero-length partitions).

The sparse image starts with a DONT_CARE chunk on purpose: Unisoc FDL2
erases the WHOLE target partition before writing a sparse image whose first
chunk is not DONT_CARE.

usage: lp_grow.py super_head.bin GROW_PART EATEN_PART SUPER_SIZE out_head.bin out.sparse.img
       (super_head.bin = first 2 MiB of the super partition)
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lp_meta as L

BS = 4096


def main():
    src, grow, eaten, super_size, out_head, out_sparse = sys.argv[1:7]
    super_size = int(super_size, 0)
    buf = bytearray(open(src, "rb").read())
    maxsz, slots = struct.unpack_from("<II", buf, L.GEO + 40)
    if slots != 1:
        sys.exit("only metadata_slot_count == 1 is handled")
    copies = (L.META0, L.META0 + maxsz * slots)
    for off in copies:
        if not L.verify(buf, off):
            sys.exit(f"bad checksum in metadata copy at {hex(off)}")
        _, parts, exts = L.dump(buf, off)
        byname = {p[0]: p for p in parts}
        g, e = byname[grow], byname[eaten]
        if g[3] != 1 or e[3] != 1:
            sys.exit("both partitions must have exactly one extent")
        ge, ee = exts[g[2]], exts[e[2]]
        if ge[2] + ge[0] != ee[2]:
            sys.exit(f"{eaten} does not directly follow {grow}")
        struct.pack_into("<Q", buf, ge[4], ge[0] + ee[0])
        struct.pack_into("<I", buf, e[5] + 44, 0)  # num_extents = 0
        L.fix_checksums(buf, off)
        assert L.verify(buf, off)
        print(f"{grow}: {ge[0]} -> {ge[0] + ee[0]} sectors; {eaten}: 0 extents")
    open(out_head, "wb").write(buf)
    nmeta = (copies[1] + maxsz) // BS
    tot = super_size // BS
    chunks = [(0xCAC3, 1, b""), (0xCAC1, nmeta - 1, bytes(buf[BS:nmeta * BS])), (0xCAC3, tot - nmeta, b"")]
    with open(out_sparse, "wb") as f:
        f.write(struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, BS, tot, len(chunks), 0))
        for t, n, p in chunks:
            f.write(struct.pack("<HHII", t, 0, n, 12 + len(p)))
            f.write(p)


if __name__ == "__main__":
    main()
