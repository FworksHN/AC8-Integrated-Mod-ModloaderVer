"""Inspect the built AC8 mouse-aim DLL: exports, UE4SS imports, PE identity."""
from __future__ import annotations

import struct
import sys


def parse(path):
    data = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew : e_lfanew + 4] == b"PE\0\0"
    coff = e_lfanew + 4
    machine, nsec, ts, _, _, optsize, chars = struct.unpack_from("<HHIIIHH", data, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    # PE32+ data directories start at opt+112
    dd_off = opt + (112 if magic == 0x20B else 96)
    export_rva, export_size = struct.unpack_from("<II", data, dd_off)
    import_rva, import_size = struct.unpack_from("<II", data, dd_off + 8)
    sec_tab = opt + optsize
    secs = []
    for i in range(nsec):
        name, vsize, vaddr, rsize, raddr = struct.unpack_from("<8sIIII", data, sec_tab + i * 40)
        secs.append((vaddr, max(vsize, rsize), raddr))

    def rva2off(rva):
        for vaddr, size, raddr in secs:
            if vaddr <= rva < vaddr + size:
                return raddr + (rva - vaddr)
        return None

    def cstr(rva):
        off = rva2off(rva)
        end = data.index(b"\0", off)
        return data[off:end].decode("latin-1")

    exports, imports = [], {}
    if export_rva:
        eo = rva2off(export_rva)
        n_names = struct.unpack_from("<I", data, eo + 24)[0]
        names_rva = struct.unpack_from("<I", data, eo + 32)[0]
        for i in range(n_names):
            name_rva = struct.unpack_from("<I", data, rva2off(names_rva) + i * 4)[0]
            exports.append(cstr(name_rva))
    if import_rva:
        io = rva2off(import_rva)
        i = 0
        while True:
            desc = data[io + i * 20 : io + i * 20 + 20]
            if len(desc) < 20 or desc == b"\0" * 20:
                break
            oft, _, _, name_rva, ft = struct.unpack("<IIIII", desc)
            dll = cstr(name_rva)
            thunk_rva = oft or ft
            syms = []
            to = rva2off(thunk_rva)
            j = 0
            while True:
                val = struct.unpack_from("<Q", data, to + j * 8)[0]
                if val == 0:
                    break
                if val & (1 << 63):
                    syms.append(f"#{val & 0xFFFF}")
                else:
                    syms.append(cstr((val & 0x7FFFFFFF) + 2))
                j += 1
            imports[dll] = syms
            i += 1
    return {
        "machine": machine,
        "timestamp": ts,
        "size_of_image": size_of_image,
        "exports": exports,
        "imports": imports,
        "bytes": len(data),
    }


def main():
    path = sys.argv[1]
    info = parse(path)
    print(f"file        : {path}")
    print(f"size        : {info['bytes']:,} bytes")
    print(f"machine     : 0x{info['machine']:04X}")
    print(f"timestamp   : 0x{info['timestamp']:08X}")
    print(f"ImageSize   : 0x{info['size_of_image']:X}")
    print(f"exports     : {len(info['exports'])}")
    for e in sorted(info["exports"]):
        print(f"   {e}")
    print("imports:")
    total = 0
    for dll, syms in sorted(info["imports"].items()):
        print(f"   {dll} ({len(syms)})")
        total += len(syms)
        for s in syms:
            print(f"      {s}")
    print(f"imported symbols total: {total}")

    lua_syms = [
        s for dll, syms in info["imports"].items() if dll.lower() == "ue4ss.dll" for s in syms
    ]
    print()
    print(f"UE4SS.dll imports: {len(lua_syms)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
