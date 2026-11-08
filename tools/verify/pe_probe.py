"""Minimal PE probe for AC8 build identification and RVA signature checks."""
from __future__ import annotations

import struct
import sys

SECTION_CHARS = {}


def read_headers(fh):
    fh.seek(0)
    dos = fh.read(0x40)
    if dos[:2] != b"MZ":
        raise SystemExit("not MZ")
    e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
    fh.seek(e_lfanew)
    nt = fh.read(0x108)
    if nt[:4] != b"PE\0\0":
        raise SystemExit("not PE")
    machine, nsec, timestamp, _, _, optsize, chars = struct.unpack_from("<HHIIIHH", nt, 4)
    opt_off = 4 + 20
    magic = struct.unpack_from("<H", nt, opt_off)[0]
    size_of_image = struct.unpack_from("<I", nt, opt_off + 56)[0]
    image_base = struct.unpack_from("<Q", nt, opt_off + 24)[0]
    entry = struct.unpack_from("<I", nt, opt_off + 16)[0]
    # section table follows the optional header
    sec_off = e_lfanew + 4 + 20 + optsize
    fh.seek(sec_off)
    raw = fh.read(nsec * 40)
    sections = []
    for i in range(nsec):
        name, vsize, vaddr, rsize, raddr = struct.unpack_from("<8sIIII", raw, i * 40)
        ch = struct.unpack_from("<I", raw, i * 40 + 36)[0]
        sections.append((name.rstrip(b"\0").decode("latin-1"), vsize, vaddr, rsize, raddr, ch))
    return {
        "machine": machine,
        "nsec": nsec,
        "timestamp": timestamp,
        "size_of_image": size_of_image,
        "image_base": image_base,
        "entry": entry,
        "optsize": optsize,
        "magic": magic,
        "sections": sections,
    }


def rva_to_off(hdr, rva):
    for name, vsize, vaddr, rsize, raddr, ch in hdr["sections"]:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def main():
    path = sys.argv[1]
    with open(path, "rb") as fh:
        hdr = read_headers(fh)
        print(f"timestamp        : 0x{hdr['timestamp']:08X}")
        print(f"size_of_image    : 0x{hdr['size_of_image']:08X}")
        print(f"image_base       : 0x{hdr['image_base']:X}")
        print(f"machine          : 0x{hdr['machine']:04X}")
        print(f"sections         : {hdr['nsec']}")
        for s in hdr["sections"]:
            print(f"  {s[0]:<8} va=0x{s[2]:08X} vs={s[1]:#x} raw=0x{s[4]:08X} rs={s[3]:#x} ch=0x{s[5]:08X}")

        for arg in sys.argv[2:]:
            rva_s, _, hexstr = arg.partition("=")
            rva = int(rva_s, 16)
            expect = bytes.fromhex(hexstr)
            off = rva_to_off(hdr, rva)
            if off is None:
                print(f"RVA 0x{rva:08X}: not mapped")
                continue
            fh.seek(off)
            actual = fh.read(len(expect))
            ok = actual == expect
            print(f"RVA 0x{rva:08X}: {'MATCH' if ok else 'MISMATCH'}")
            if not ok:
                print(f"  expected {expect.hex(' ')}")
                print(f"  actual   {actual.hex(' ')}")


if __name__ == "__main__":
    main()
