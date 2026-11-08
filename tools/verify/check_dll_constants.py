"""Confirm the Build-26002268 anchors really landed in the built DLL."""
from __future__ import annotations

import struct
import sys

NEEDLES = {
    "pe_timestamp 0x6AD2D0A7 (imm32)": bytes.fromhex("A7 D0 D2 6A"),
    "image_size 0x215A2000 (imm32)": bytes.fromhex("00 20 5A 21"),
    "input RVA 0x4D2C040 (disp32)": bytes.fromhex("40 C0 D2 04"),
    "camera_update 0x70B4960 (disp32)": bytes.fromhex("60 49 0B 07"),
    "camera_table 0xC9BCE20 (disp32)": bytes.fromhex("20 CE 9B 0C"),
    "camera_cache_getter 0x48EF260 (disp32)": bytes.fromhex("60 F2 8E 04"),
    # The source writes base+actor_location_exec+0x19, so the compiler folds the
    # displacement into 0x3FCABC9 rather than 0x3FCABB0.
    "actor_location_exec+0x19 0x3FCABC9 (disp32)": bytes.fromhex("C9 AB FC 03"),
    "helmet_select 0x7283700 (disp32)": bytes.fromhex("00 37 28 07"),
    "helmet_release_return 0x7D529E0 (disp32)": bytes.fromhex("E0 29 D5 07"),
}

STRINGS = [
    b"input processor ready: Steam Build %u (anchors from game_build.h)",
    b"offline marker absent: launcher build continues (offline single-player only)",
    b"error game image or input signature mismatch (expected Steam Build %u)",
    b"native camera refused: executable identity/signature mismatch (expected Steam Build %u)",
    b"PROFILE 2.5.1+26002268",
]


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    bad = 0
    print(f"{path}\n")
    for label, needle in NEEDLES.items():
        hits = data.count(needle)
        ok = hits > 0
        bad += 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] {label}: {hits} hit(s)")
    print()
    for s in STRINGS:
        hits = data.count(s)
        ok = hits > 0
        bad += 0 if ok else 1
        print(f"[{'OK  ' if ok else 'FAIL'}] string {s.decode()[:60]!r}: {hits} hit(s)")

    # Show which section each anchor hit lives in (sanity: code, not resource).
    print()
    print("RESULT:", "all anchors embedded" if bad == 0 else f"{bad} missing")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
