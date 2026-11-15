#!/usr/bin/env python3
"""Neutralise the `avb` fs_mgr flag in the first-stage fstab embedded in a
boot image v2 DTB (/firmware/android/fstab/*/fsmgr_flags).

Why: on this Honor/Unisoc uboot the androidboot.vbmeta.digest handed to the
kernel is not recomputed when vbmeta is modified, so Android 10 first-stage
init (libfs_avb) rejects any patched vbmeta. Removing `avb` from the DT fstab
makes first-stage mount skip AVB/dm-verity entirely while vbmeta stays stock.

The token `avb` is replaced in place by `zzz` (same length, so the DTB layout
is untouched). fs_mgr only warns about unknown flags. `avb_keys=...` is left
alone. Booting the result needs an unlocked bootloader state.

usage: patch_boot_dtb_fstab.py boot.img out.img
"""
import struct
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fdt_dump import walk


def dtb_location(b):
    if b[:8] != b"ANDROID!":
        sys.exit("not an Android boot image")
    ks, _, rs, _, ss, _, _, ps = struct.unpack("<8I", b[8:40])
    version = struct.unpack("<I", b[40:44])[0]
    if version != 2:
        sys.exit(f"boot header v{version}; only v2 is handled")
    rdo_size = struct.unpack("<I", b[1632:1636])[0]
    dtb_size = struct.unpack("<I", b[1648:1652])[0]
    pg = lambda n: (n + ps - 1) // ps * ps
    return ps + pg(ks) + pg(rs) + pg(ss) + pg(rdo_size), dtb_size


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = bytearray(open(src, "rb").read())
    base, size = dtb_location(b)
    dtb = bytes(b[base:base + size])
    if dtb[:4] != b"\xd0\x0d\xfe\xed":
        sys.exit("DTB magic not found at computed offset")
    n = 0
    for path, name, val, voff in walk(dtb):
        if name != "fsmgr_flags" or "/firmware/android/fstab" not in path:
            continue
        flags = val.rstrip(b"\0").decode()
        toks = flags.split(",")
        if "avb" not in toks:
            continue
        new = ",".join("zzz" if t == "avb" else t for t in toks).encode()
        b[base + voff:base + voff + len(new)] = new
        print(f"{path}: {flags} -> {new.decode()}")
        n += 1
    open(dst, "wb").write(b)
    print(f"patched {n} fstab entries")


if __name__ == "__main__":
    main()
