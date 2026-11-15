#!/usr/bin/env python3
"""Rewrite the /data line of the vendor fstab inside a raw vendor image
(ext4 or erofs, uncompressed file data) in place, and emit a super-sized
sparse image that writes only the one changed 4 KiB block.

Default action removes `fileencryption=...` so /data is mounted unencrypted.
Why: Android 12+ vold always installs an `fscrypt-provisioning` key after
FS_IOC_ADD_ENCRYPTION_KEY. The Honor 4.14 kernel supports the ioctl but not
that key type ("Failed to insert fscrypt-provisioning key ... No such
device"), so FBE setup fails (v1 and v2 policies alike) and init reboots to
recovery with --reason=enablefilecrypto_failed.

The line keeps its length: removed bytes are replaced by trailing spaces.

usage:
  patch_vendor_fstab.py vendor.img SUPER_SIZE VENDOR_OFFSET_IN_SUPER out.sparse.img [out_block.bin]

  VENDOR_OFFSET_IN_SUPER = first sector of the vendor extent * 512 (lpdump / lp_meta.py)
"""
import re
import struct
import sys

BS = 4096


def main():
    img, super_size, vend_off, out = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0), sys.argv[4]
    d = open(img, "rb").read()
    hits = []
    pos = d.find(b"by-name/userdata")
    while pos != -1:
        s = d.rfind(b"\n", 0, pos) + 1
        e = d.find(b"\n", pos)
        cand = d[s:e]
        fields = cand.split()
        # init's fstab: <src> /data <type> <mnt_flags> <fs_mgr_flags>, fs_mgr flags contain `wait`
        if (re.search(rb"by-name/userdata\s+/data\s", cand) and not cand.lstrip().startswith(b"#")
                and len(fields) >= 5 and b"wait" in fields[4].split(b",")):
            hits.append((s, cand))
        pos = d.find(b"by-name/userdata", pos + 1)
    if len(hits) != 1:
        for s, c in hits:
            print(hex(s), c.decode(errors="replace"))
        sys.exit(f"expected exactly one init-style /data line, found {len(hits)}")
    start, line = hits[0]
    new = re.sub(rb"fileencryption=[^,\s]*,?", b"", line)
    new = new.replace(b",\x20", b"\x20")
    new += b" " * (len(line) - len(new))
    assert len(new) == len(line)
    if new == line:
        sys.exit("no fileencryption= option found; nothing to do")
    blk = start // BS
    if (start + len(line) - 1) // BS != blk:
        sys.exit("line crosses a block boundary; extend the script to emit two blocks")
    block = bytearray(d[blk * BS:(blk + 1) * BS])
    rel = start - blk * BS
    block[rel:rel + len(line)] = new
    print("old:", line.decode())
    print("new:", new.decode().rstrip())
    if vend_off % BS:
        sys.exit("vendor offset not 4K aligned")
    tot = super_size // BS
    off = vend_off // BS + blk
    chunks = [(0xCAC3, off, b""), (0xCAC1, 1, bytes(block)), (0xCAC3, tot - off - 1, b"")]
    with open(out, "wb") as f:
        f.write(struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, BS, tot, len(chunks), 0))
        for t, n, p in chunks:
            f.write(struct.pack("<HHII", t, 0, n, 12 + len(p)))
            f.write(p)
    if len(sys.argv) > 5:
        open(sys.argv[5], "wb").write(block)
    print(f"block {blk} of vendor -> super byte offset {hex(off * BS)}")


if __name__ == "__main__":
    main()
