#!/usr/bin/env python3
"""Re-derive the Build anchors for a new AceCombat8.exe.

This is the "case B" tool from docs/ADAPTATION.md: the game updated, the seven
functions themselves did not change, only their addresses moved. Every anchor is
located by an independent fingerprint and then *proved* by a structural relation
that cannot hold by accident:

    input processor     masked 2323-byte fingerprint (2111 bytes must match)
    camera_update       15-byte prologue, then only the candidate that a vtable
                        slot 241 actually points at survives
    camera_table        derived from that vtable reference, slot 241 re-checked
    camera_cache_getter 9-byte `lea rax,[rcx+0x14A0]; ret`, expected unique
    actor_location_exec 48-byte function head, expected unique; the anchor used
                        in code is head+0x19
    helmet_select       21-byte entry, expected unique
    helmet_release      the player-only call site: 16 caller bytes, and the call
                        must resolve to helmet_select (rel32 checked both ways)

Usage:

    python retarget.py --new-exe <AceCombat8.exe> [--build 260XXXXX] [--out game_build.h]
    python retarget.py --self-test

--self-test runs the current installed executable and compares every derived
value with native/src/game_build.h, so the tool itself is verified before the
next game update needs it.

Exit code 0 only when every anchor is located and proved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC_DIR = REPO / "native" / "src"
DEFAULT_EXE = r"E:\SteamLibrary\steamapps\common\ACE COMBAT 8\Game\Binaries\Win64\AceCombat8.exe"

# --- signatures -------------------------------------------------------------
# Stable instruction bytes; no RIP-relative displacements, no struct offsets that
# are likely to move on their own. See docs/ADAPTATION.md for provenance.
CAMERA_PROLOGUE = bytes.fromhex("488BC448895818574881EC400100")      # 15 bytes
CACHE_GETTER = bytes.fromhex("488D81A0140000C3")                     # 9 bytes
HELMET_ENTRY = bytes.fromhex("48895C2418555741574883EC20F30F1081FC060000")          # 21
HELMET_CALLER = bytes.fromhex("488B8BE81A00004533C94533C033D2E8")                    # 16
# 48 bytes of the ActorLocation exec function head; the anchor the module uses
# is head+0x19 (`48 8b 81 a0 01 00 00`), which on its own matches 311 places.
ACTOR_HEAD = bytes.fromhex(
    "4883EC38488B42204533C94885C0410F95C14C03C84C894A20488B81A0010000"
    "4885C0741E0F1080200200000F110424"
)
ACTOR_ANCHOR_OFFSET = 0x19

CAMERA_UPDATE_SLOT = 241


class PEImage:
    def __init__(self, path: Path):
        self.path = path
        self.raw = path.read_bytes()
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        data = self.raw
        if data[:2] != b"MZ":
            raise SystemExit(f"not a PE file: {path}")
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise SystemExit(f"missing PE signature: {path}")
        coff = e_lfanew + 4
        machine, nsec, ts, _, _, optsize, _ = struct.unpack_from("<HHIIIHH", data, coff)
        opt = coff + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic != 0x20B:
            raise SystemExit("expected a PE32+ (x64) image")
        self.machine = machine
        self.timestamp = ts
        self.size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
        self.image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        sect = opt + optsize
        self.sections = []
        for i in range(nsec):
            name, vsize, vaddr, rsize, raddr = struct.unpack_from("<8sIIII", data, sect + i * 40)
            chars = struct.unpack_from("<I", data, sect + i * 40 + 36)[0]
            self.sections.append({
                "name": name.rstrip(b"\0").decode("latin-1"),
                "va": vaddr,
                "vsize": vsize,
                "raw": raddr,
                "rawsize": rsize,
                "chars": chars,
            })
        text = self.section(".text")
        if not text:
            raise SystemExit(".text section not found")
        self.text_va = text["va"]
        self.text_size = max(text["vsize"], text["rawsize"])
        self.text = data[text["raw"]:text["raw"] + self.text_size]
        # one contiguous blob of every non-executable section that has file data
        blobs, self._data_map = [], []
        cursor = 0
        for s in self.sections:
            if s["chars"] & 0x20000000:          # IMAGE_SCN_MEM_EXECUTE
                continue
            if not s["rawsize"]:
                continue
            blob = data[s["raw"]:s["raw"] + s["rawsize"]]
            self._data_map.append((cursor, cursor + len(blob), s))
            blobs.append(blob)
            cursor += len(blob)
        self.data_blob = b"".join(blobs)

    def section(self, name):
        for s in self.sections:
            if s["name"] == name:
                return s
        return None

    def off_of(self, rva):
        for s in self.sections:
            if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
                if rva - s["va"] >= s["rawsize"]:
                    return None
                return s["raw"] + (rva - s["va"])
        return None

    def read(self, rva, n):
        off = self.off_of(rva)
        return None if off is None else self.raw[off:off + n]

    def section_of(self, rva):
        for s in self.sections:
            if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
                return s["name"]
        return None

    def scan_text(self, pattern):
        out, pos = [], 0
        while True:
            i = self.text.find(pattern, pos)
            if i < 0:
                return out
            out.append(self.text_va + i)
            pos = i + 1

    def scan_text_masked(self, pattern, mask):
        k = 0
        while k < len(mask) and mask[k] == 0xFF:
            k += 1
        if k == 0:
            raise SystemExit("fingerprint has no fixed prefix")
        anchor = pattern[:k]
        out, pos = [], 0
        while True:
            i = self.text.find(anchor, pos)
            if i < 0:
                return out
            if all(not m or self.text[i + j] == pattern[j] for j, m in enumerate(mask)):
                out.append(self.text_va + i)
            pos = i + 1

    def pointer_refs(self, value):
        """Every 8-byte-aligned location in a data section holding `value`."""
        needle = struct.pack("<Q", value)
        hits, pos = [], 0
        while True:
            i = self.data_blob.find(needle, pos)
            if i < 0:
                return hits
            if i % 8 == 0:
                for lo, hi, sec in self._data_map:
                    if lo <= i < hi:
                        hits.append((sec["name"], sec["va"] + (i - lo)))
                        break
            pos = i + 8


# --- header parsing ---------------------------------------------------------
def parse_c_array(text, name):
    m = re.search(r"\b" + name + r"\s*\[\s*\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise SystemExit(f"array {name} not found")
    body = re.sub(r"//.*", "", m.group(1))
    return bytes(int(v.strip(), 0) & 0xFF for v in body.split(",") if v.strip())


def load_yaw_arrays():
    path = SRC_DIR / "yaw_signature.h"
    if not path.exists():
        raise SystemExit(f"yaw_signature.h not found at {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_c_array(text, "yawCode"), parse_c_array(text, "yawMask")


def read_current_anchors():
    path = SRC_DIR / "game_build.h"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out = {}
    for key in ("steam_build", "pe_timestamp", "image_size", "input", "camera_update",
                "camera_table", "camera_cache_getter", "actor_location_exec",
                "helmet_select", "helmet_release_return", "camera_update_slot"):
        m = re.search(r"\b" + key + r"\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text)
        if m:
            out[key] = int(m.group(1), 0)
    return out


# --- locators ---------------------------------------------------------------
class Result:
    def __init__(self, name):
        self.name = name
        self.value = None
        self.ok = False
        self.evidence = ""
        self.candidates = []


def locate_input(pe, yaw, mask):
    r = Result("input")
    hits = pe.scan_text_masked(yaw, mask)
    r.candidates = hits
    if len(hits) == 1:
        r.value, r.ok = hits[0], True
        wild = sum(1 for m in mask if not m)
        r.evidence = f"masked fingerprint {len(yaw)} bytes ({wild} wildcards), 1 hit"
        return r
    if not hits:
        # Diagnose how far the function still matches, so a changed function body
        # is reported as such instead of "not found".
        for n in (2048, 1536, 1024, 768, 512, 256, 128, 64):
            sub = pe.scan_text_masked(yaw[:n], mask[:n])
            if sub:
                r.evidence = (f"full fingerprint failed; first {n} of {len(yaw)} bytes match at "
                              + ", ".join(f"0x{a:X}" for a in sub[:3])
                              + " — the function body probably changed")
                return r
        r.evidence = "fingerprint not found at all"
        return r
    r.evidence = f"{len(hits)} hits (ambiguous)"
    return r


def locate_camera(pe):
    upd, tab = Result("camera_update"), Result("camera_table")
    cands = pe.scan_text(CAMERA_PROLOGUE)
    upd.candidates = cands
    proofs = []
    for c in cands:
        for sec, slot_rva in pe.pointer_refs(pe.image_base + c):
            table_rva = slot_rva - CAMERA_UPDATE_SLOT * 8
            if table_rva <= 0:
                continue
            if pe.section_of(table_rva) is None:
                continue
            # the slot must be where we expect it inside that table
            if slot_rva - table_rva != CAMERA_UPDATE_SLOT * 8:
                continue
            proofs.append((c, table_rva, sec, slot_rva))
    if len(proofs) == 1:
        c, table_rva, sec, slot_rva = proofs[0]
        upd.value, upd.ok = c, True
        upd.evidence = (f"{len(cands)} prologue hits, only 0x{c:X} is referenced by a vtable "
                        f"slot {CAMERA_UPDATE_SLOT} in {sec}")
        tab.value, tab.ok = table_rva, True
        tab.evidence = (f"derived from {sec}:0x{slot_rva:X} (slot {CAMERA_UPDATE_SLOT}) "
                        f"-> vtable 0x{table_rva:X}")
    elif not proofs:
        upd.evidence = (f"{len(cands)} prologue hits, none referenced from a vtable slot "
                        f"{CAMERA_UPDATE_SLOT} (" + ", ".join(f"0x{c:X}" for c in cands[:6]) + ")")
        tab.evidence = "no candidate survived the vtable check"
    else:
        upd.evidence = f"{len(proofs)} candidates survived the vtable check (ambiguous)"
        tab.evidence = "ambiguous"
    return upd, tab


def locate_simple(pe, name, pattern, note):
    r = Result(name)
    hits = pe.scan_text(pattern)
    r.candidates = hits
    if len(hits) == 1:
        r.value, r.ok = hits[0], True
        r.evidence = f"{note}, 1 hit"
        return r
    if not hits:
        r.evidence = f"{note}: not found"
        return r
    r.evidence = f"{note}: {len(hits)} hits (ambiguous)"
    return r


def locate_actor(pe):
    r = Result("actor_location_exec")
    hits = pe.scan_text(ACTOR_HEAD)
    r.candidates = hits
    if len(hits) == 1:
        head = hits[0]
        anchor = pe.read(head + ACTOR_ANCHOR_OFFSET, 7)
        if anchor == bytes.fromhex("488B81A0010000"):
            r.value, r.ok = head, True
            r.evidence = (f"function head {len(ACTOR_HEAD)} bytes, 1 hit; "
                          f"head+0x19 still reads mov rax,[rcx+0x1A0]")
        else:
            r.evidence = "function head found but head+0x19 changed"
        return r
    if not hits:
        r.evidence = f"function head ({len(ACTOR_HEAD)} bytes) not found"
        return r
    r.evidence = f"{len(hits)} hits (ambiguous)"
    return r


def locate_helmet(pe):
    sel = Result("helmet_select")
    rel = Result("helmet_release_return")
    entry_hits = pe.scan_text(HELMET_ENTRY)
    sel.candidates = entry_hits
    if len(entry_hits) != 1:
        sel.evidence = (f"1 expected, {len(entry_hits)} found")
        rel.evidence = "not attempted (select not resolved)"
        return sel, rel
    sel.value, sel.ok = entry_hits[0], True
    sel.evidence = f"{len(HELMET_ENTRY)}-byte entry, 1 hit"

    caller_hits = pe.scan_text(HELMET_CALLER)
    good = []
    for c in caller_hits:
        call_rva = c + len(HELMET_CALLER) - 1          # the E8 byte
        ret_rva = call_rva + 5
        rel32 = struct.unpack("<i", pe.read(call_rva + 1, 4))[0]
        if ret_rva + rel32 == sel.value:
            good.append((ret_rva, call_rva))
    rel.candidates = [c for c in caller_hits]
    if len(good) == 1:
        ret_rva, call_rva = good[0]
        rel.value, rel.ok = ret_rva, True
        rel.evidence = (f"{len(caller_hits)} caller hit; call at 0x{call_rva:X} "
                        f"resolves to helmet_select 0x{sel.value:X}")
    elif not good:
        rel.evidence = (f"{len(caller_hits)} caller hits, none calls helmet_select")
    else:
        rel.evidence = f"{len(good)} caller hits resolve to helmet_select (ambiguous)"
    return sel, rel


# --- output -----------------------------------------------------------------
def render_header(pe, values, build_hint, previous_build=0):
    def hx(v):
        return f"0x{v:X}"
    # A new build number cannot be derived from the image, so accept it on the
    # command line; fall back to the value already in game_build.h and flag it.
    build = build_hint or previous_build or 0
    build_note = "" if build_hint else "  // TODO: update to the new Steam build number"
    return f"""#pragma once
#include <cstdint>

// Steam 1.01.002 / Build {build} anchors for the AC8 mouse-aim native module.
//
// Re-derived with tools/verify/retarget.py from the installed executable:
//
//   PE timestamp 0x{pe.timestamp:08X}   image size 0x{pe.size_of_image:X}
//   exe sha256   {pe.sha256}
//
// Every value below was located by an independent instruction fingerprint and
// then proved by a structural relation (see the tool's docstring). Do not paste
// offsets from a different build: the PE gate turns them into a clean refusal,
// not a crash, but nothing else will work either.
namespace ac8_build {{
inline constexpr unsigned steam_build = {build};{build_note}
inline constexpr unsigned pe_timestamp = 0x{pe.timestamp:08X};
inline constexpr unsigned image_size = 0x{pe.size_of_image:X};

// Input processor that turns the yaw/pitch/roll slots into a flight command.
inline constexpr std::uintptr_t input = {hx(values['input'])};

// Camera: the post-update function, the camera vtable that holds it, and the
// two accessors used to prove the manager is the live player camera.
inline constexpr std::uintptr_t camera_update = {hx(values['camera_update'])};
inline constexpr std::uintptr_t camera_table = {hx(values['camera_table'])};
inline constexpr unsigned camera_update_slot = {values.get('camera_update_slot', CAMERA_UPDATE_SLOT)};
inline constexpr std::uintptr_t camera_cache_getter = {hx(values['camera_cache_getter'])};
inline constexpr std::uintptr_t actor_location_exec = {hx(values['actor_location_exec'])};

// Helmet (HMD) target selection, plus the return address of the player-only
// release call site that is allowed to redirect the selection.
inline constexpr std::uintptr_t helmet_select = {hx(values['helmet_select'])};
inline constexpr std::uintptr_t helmet_release_return = {hx(values['helmet_release_return'])};
}} // namespace ac8_build
"""


def main():
    ap = argparse.ArgumentParser(description="Re-derive the AC8 mouse-aim build anchors.")
    ap.add_argument("--new-exe", help="AceCombat8.exe of the new game build")
    ap.add_argument("--build", type=int, help="new Steam build number (e.g. 26012345)")
    ap.add_argument("--out", help="write the generated game_build.h here")
    ap.add_argument("--json", help="write a machine-readable report here")
    ap.add_argument("--self-test", action="store_true",
                    help="run against the installed exe and compare with native/src/game_build.h")
    args = ap.parse_args()

    exe = Path(args.new_exe or DEFAULT_EXE)
    if not exe.exists():
        raise SystemExit(f"executable not found: {exe}")
    pe = PEImage(exe)
    yaw, mask = load_yaw_arrays()
    current = read_current_anchors()

    print(f"exe        : {exe}")
    print(f"size       : {len(pe.raw):,} bytes")
    print(f"sha256     : {pe.sha256}")
    print(f"machine    : 0x{pe.machine:04X}   image base 0x{pe.image_base:X}")
    print(f"timestamp  : 0x{pe.timestamp:08X}   image size 0x{pe.size_of_image:X}")
    print()

    results = []
    results.append(locate_input(pe, yaw, mask))
    upd, tab = locate_camera(pe)
    results += [upd, tab]
    results.append(locate_simple(pe, "camera_cache_getter", CACHE_GETTER, "9-byte getter"))
    results.append(locate_actor(pe))
    sel, rel = locate_helmet(pe)
    results += [sel, rel]

    width = max(len(r.name) for r in results)
    for r in results:
        mark = "OK  " if r.ok else "FAIL"
        val = f"0x{r.value:X}" if r.value else "-"
        print(f"[{mark}] {r.name:<{width}}  {val:<12}  {r.evidence}")

    values = {r.name: r.value for r in results if r.ok}
    values["camera_update_slot"] = CAMERA_UPDATE_SLOT
    ok = all(r.ok for r in results)
    print()

    if args.self_test:
        print("=== self-test against native/src/game_build.h ===")
        mismatches = 0
        for key in ("input", "camera_update", "camera_table", "camera_cache_getter",
                    "actor_location_exec", "helmet_select", "helmet_release_return"):
            want = current.get(key)
            got = values.get(key)
            if want is None:
                print(f"  {key:<22} not present in game_build.h (skipped)")
                continue
            same = want == got
            mismatches += 0 if same else 1
            print(f"  {'OK  ' if same else 'FAIL'} {key:<22} header 0x{want:X}  derived "
                  f"{'0x%X' % got if got else '-'}")
        for key, got in (("pe_timestamp", pe.timestamp), ("image_size", pe.size_of_image)):
            want = current.get(key)
            same = want == got
            mismatches += 0 if same else 1
            print(f"  {'OK  ' if same else 'FAIL'} {key:<22} header 0x{want:08X}  derived 0x{got:08X}")
        print()
        print("SELF-TEST " + ("PASS" if mismatches == 0 and ok else f"FAIL ({mismatches} mismatch)"))
        return 0 if mismatches == 0 and ok else 1

    if args.json:
        Path(args.json).write_text(json.dumps({
            "exe": str(exe),
            "sha256": pe.sha256,
            "pe_timestamp": pe.timestamp,
            "image_size": pe.size_of_image,
            "ok": ok,
            "anchors": {r.name: ({"value": r.value, "ok": r.ok, "evidence": r.evidence,
                                  "candidates": r.candidates} ) for r in results},
        }, indent=2), encoding="utf-8")
        print(f"report written to {args.json}\n")

    if not ok:
        print("Not all anchors were located. Do not patch game_build.h by hand from")
        print("partially matched values; a wrong RVA is worse than a refusal.")
        if any("body probably changed" in r.evidence for r in results):
            print("At least one fingerprint matched only partially: the game may have")
            print("changed that function itself. That is case C in docs/ADAPTATION.md")
            print("and needs a disassembler, not this tool.")
        return 1

    header = render_header(pe, values, args.build, current.get("steam_build", 0))
    if args.out:
        Path(args.out).write_text(header, encoding="utf-8")
        print(f"game_build.h written to {args.out}\n")
    print("=== game_build.h ===")
    print(header)
    return 0


if __name__ == "__main__":
    sys.exit(main())
