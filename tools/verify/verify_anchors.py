"""Verify every Build-26002268 anchor used by the AC8 mouse-aim native module
against an installed AceCombat8.exe.

Usage:
    python verify_anchors.py [AceCombat8.exe] [native/src dir]
Both arguments default to the local development layout.
"""
from __future__ import annotations

import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXE = r"E:\SteamLibrary\steamapps\common\ACE COMBAT 8\Game\Binaries\Win64\AceCombat8.exe"
DEFAULT_SRC = os.path.normpath(os.path.join(HERE, "..", "..", "native", "src"))

# Build 26002268 constants (mirror of native/src/game_build.h)
TS = 0x6AD2D0A7
IMAGE_SIZE = 0x215A2000
RVA = {
    "input": 0x4D2C040,
    "camera_update": 0x70B4960,
    "camera_table": 0xC9BCE20,
    "camera_update_slot": 241,
    "camera_cache_getter": 0x48EF260,
    "actor_location_exec": 0x3FCABB0,
    "helmet_select": 0x7283700,
    "helmet_release_return": 0x7D529E0,
}

fails: list[str] = []


def check(label, cond, detail=""):
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {label}{(' — ' + detail) if detail else ''}")
    if not cond:
        fails.append(label)


def parse_c_array(path, name):
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\b" + name + r"\s*\[\s*\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise SystemExit(f"array {name} not found in {path}")
    body = re.sub(r"//.*", "", m.group(1))
    vals = [int(v.strip(), 0) for v in body.split(",") if v.strip()]
    return bytes(v & 0xFF for v in vals)


def load_headers(fh):
    fh.seek(0)
    dos = fh.read(0x40)
    assert dos[:2] == b"MZ"
    e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
    fh.seek(e_lfanew)
    nt = fh.read(0x108)
    assert nt[:4] == b"PE\0\0"
    _, nsec, ts, _, _, optsize, _ = struct.unpack_from("<HHIIIHH", nt, 4)
    opt_off = 24  # PE sig (4) + COFF header (20)
    size_of_image = struct.unpack_from("<I", nt, opt_off + 56)[0]
    fh.seek(e_lfanew + opt_off + optsize)
    raw = fh.read(nsec * 40)
    secs = []
    for i in range(nsec):
        name, vsize, vaddr, rsize, raddr = struct.unpack_from("<8sIIII", raw, i * 40)
        secs.append((name, vsize, vaddr, rsize, raddr))
    return ts, size_of_image, secs


def rva_off(secs, rva):
    for _, vsize, vaddr, rsize, raddr in secs:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def read_rva(fh, secs, rva, n):
    off = rva_off(secs, rva)
    if off is None:
        return None
    fh.seek(off)
    return fh.read(n)


def main():
    exe = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXE
    src = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SRC
    print(f"exe : {exe}")
    print(f"src : {src}")
    print()

    with open(exe, "rb") as fh:
        ts, size_of_image, secs = load_headers(fh)
        check("PE TimeDateStamp == 0x6AD2D0A7", ts == TS, f"0x{ts:08X}")
        check("PE SizeOfImage == 0x215A2000", size_of_image == IMAGE_SIZE, f"0x{size_of_image:08X}")

        yaw = parse_c_array(os.path.join(src, "yaw_signature.h"), "yawCode")
        mask = parse_c_array(os.path.join(src, "yaw_signature.h"), "yawMask")
        got = read_rva(fh, secs, RVA["input"], len(yaw))
        ok = got is not None and len(got) == len(yaw) and all(
            (m == 0) or (got[i] == yaw[i]) for i, m in enumerate(mask)
        )
        wild = sum(1 for m in mask if m == 0)
        check(f"input processor yaw signature @0x{RVA['input']:X}", ok, f"{len(yaw)} bytes, {wild} masked")

        update_bytes = bytes([0x48, 0x8B, 0xC4, 0x48, 0x89, 0x58, 0x18, 0x57, 0x48, 0x81, 0xEC, 0x40, 0x01, 0, 0])
        got = read_rva(fh, secs, RVA["camera_update"], len(update_bytes))
        check(f"camera_update prologue @0x{RVA['camera_update']:X}", got == update_bytes)

        cache_bytes = bytes([0x48, 0x8D, 0x81, 0xA0, 0x14, 0, 0, 0xC3])
        got = read_rva(fh, secs, RVA["camera_cache_getter"], len(cache_bytes))
        check(f"camera_cache_getter @0x{RVA['camera_cache_getter']:X}", got == cache_bytes)

        actor_bytes = bytes([0x48, 0x8B, 0x81, 0xA0, 0x01, 0, 0])
        got = read_rva(fh, secs, RVA["actor_location_exec"] + 0x19, len(actor_bytes))
        check(f"actor_location_exec+0x19 @0x{RVA['actor_location_exec'] + 0x19:X}", got == actor_bytes)

        slot_rva = RVA["camera_table"] + RVA["camera_update_slot"] * 8
        got = read_rva(fh, secs, slot_rva, 8)
        if got is None:
            check(f"camera vtable slot {RVA['camera_update_slot']} @0x{slot_rva:X}", False, "unmapped")
        else:
            target = struct.unpack("<Q", got)[0]
            want = 0x140000000 + RVA["camera_update"]
            check(
                f"camera vtable slot {RVA['camera_update_slot']} @0x{slot_rva:X} -> camera_update",
                target == want,
                f"0x{target:X} vs 0x{want:X}",
            )

        entry = parse_c_array(os.path.join(src, "helmet_selection.h"), "entry_bytes")
        caller = parse_c_array(os.path.join(src, "helmet_selection.h"), "caller")
        got = read_rva(fh, secs, RVA["helmet_select"], len(entry))
        check(f"helmet select entry @0x{RVA['helmet_select']:X}", got == entry, f"{len(entry)} bytes")

        rel = RVA["helmet_select"] - RVA["helmet_release_return"]
        rel_off = RVA["helmet_release_return"] - 4
        got_caller = read_rva(fh, secs, rel_off - len(caller), len(caller))
        check(f"helmet release call site @0x{rel_off - len(caller):X}", got_caller == caller)
        got_rel = read_rva(fh, secs, rel_off, 4)
        actual_rel = struct.unpack("<i", got_rel)[0] if got_rel else None
        check(f"helmet release rel32 @0x{rel_off:X}", actual_rel == rel, f"{actual_rel} vs {rel}")

    print()
    if fails:
        print(f"RESULT: {len(fails)} anchor(s) FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("RESULT: all anchors match Build 26002268")
    return 0


if __name__ == "__main__":
    sys.exit(main())
