#!/usr/bin/env python
"""pst_tool.py -- read psxrecomp .pst savestates offline (no running game).

Format: docs in psxrecomp/runtime/include/boot_state.h ("PSXB" v5). Header is
nine LE u32; then section_count records of (u32 tag, u32 flags, u64 len,
payload). flags bit0 = zlib: payload is u32 raw_len + deflate stream.

    python tools/pst_tool.py info  saves/openbios/state_8014AA0C_slot04.pst
    python tools/pst_tool.py vram  A.pst out.png            # VRAM as 1024x512 RGB
    python tools/pst_tool.py diff  A.pst B.pst [--png out]  # VRAM diff + zero map
    python tools/pst_tool.py ram   A.pst out.bin            # raw 2 MB RAM
"""
import argparse
import struct
import sys
import zlib

SEC = {1: "CPU", 2: "RAM", 3: "SPAD", 4: "IRQ", 5: "TIMER", 6: "CLOCK", 7: "GPU",
       8: "VRAM", 9: "SPU", 10: "SPURAM", 11: "CDROM", 12: "DMA", 13: "SIO",
       14: "DIRTY", 15: "MDEC", 16: "ICACHE"}
VRAM_W, VRAM_H = 1024, 512


def load(path):
    d = open(path, "rb").read()
    hdr = struct.unpack("<9I", d[:36])
    if hdr[0] != 0x50535842:
        raise SystemExit(f"{path}: bad magic {hdr[0]:#x}")
    secs = {}
    off = 36
    for _ in range(hdr[7]):
        tag, flags, ln = struct.unpack("<IIQ", d[off:off + 16])
        off += 16
        pay = d[off:off + ln]
        off += ln
        if flags & 1:
            raw_len = struct.unpack("<I", pay[:4])[0]
            pay = zlib.decompress(pay[4:])
            assert len(pay) == raw_len, (tag, len(pay), raw_len)
        secs[tag] = pay
    return hdr, secs


def cpu_regs(secs):
    c = secs[1]
    gpr = struct.unpack("<32I", c[:128])
    pc, hi, lo = struct.unpack("<3I", c[128:140])
    return gpr, pc


def vram_u16(secs):
    import numpy as np
    return np.frombuffer(secs[8], dtype="<u2").reshape(VRAM_H, VRAM_W)


def vram_png(v, path):
    import numpy as np
    from PIL import Image
    r = ((v & 0x1F) << 3).astype("u1")
    g = (((v >> 5) & 0x1F) << 3).astype("u1")
    b = (((v >> 10) & 0x1F) << 3).astype("u1")
    Image.fromarray(np.dstack([r, g, b])).save(path)


def cmd_info(a):
    hdr, secs = load(a.file)
    print("magic %#x ver %d bios %#x entry %#x codegen %#x abi %#x ver %d sections %d"
          % hdr[:8])
    for t, p in secs.items():
        print(f"  {SEC.get(t, t):7s} {len(p):>9d}")
    gpr, pc = cpu_regs(secs)
    print(f"  pc={pc:#010x} ra={gpr[31]:#010x} sp={gpr[29]:#010x}")


def cmd_vram(a):
    _, secs = load(a.file)
    vram_png(vram_u16(secs), a.out)
    print("wrote", a.out)


def cmd_ram(a):
    _, secs = load(a.file)
    open(a.out, "wb").write(secs[2])
    print("wrote", a.out, len(secs[2]))


def zero_map(v, label):
    print(f"VRAM zero map [{label}] 64x64 blocks ('.'=all zero, '#'=no zero, digit=nonzero tenths)")
    print("      " + "".join(f"{x // 64:2d}" for x in range(0, VRAM_W, 64)))
    for y in range(0, VRAM_H, 64):
        line = ""
        for x in range(0, VRAM_W, 64):
            nz = int((v[y:y + 64, x:x + 64] != 0).sum())
            line += " ." if nz == 0 else (" #" if nz == 4096 else f" {min(9, nz * 10 // 4096)}")
        print(f"y{y:3d} " + line)


def cmd_diff(a):
    import numpy as np
    _, sa = load(a.a)
    _, sb = load(a.b)
    va, vb = vram_u16(sa), vram_u16(sb)
    zero_map(va, a.a)
    zero_map(vb, a.b)
    d = va != vb
    print(f"differing halfwords: {int(d.sum())}")
    # coarse blocks of change
    print("diff map (halfwords differing per 64x64 block, '.'=0)")
    print("      " + "".join(f"{x // 64:5d}" for x in range(0, VRAM_W, 64)))
    for y in range(0, VRAM_H, 64):
        line = ""
        for x in range(0, VRAM_W, 64):
            n = int(d[y:y + 64, x:x + 64].sum())
            line += "    ." if n == 0 else f"{n:5d}"
        print(f"y{y:3d} " + line)
    # blocks that went from populated in A to all-zero in B
    print("blocks populated in A but all-zero in B (32x32):")
    for y in range(0, VRAM_H, 32):
        for x in range(0, VRAM_W, 32):
            ba, bb = va[y:y + 32, x:x + 32], vb[y:y + 32, x:x + 32]
            if (ba != 0).any() and not (bb != 0).any():
                print(f"  ({x},{y}) A nonzero={int((ba != 0).sum())}")
    if a.png:
        r = (d.astype("u1") * 255)
        from PIL import Image
        Image.fromarray(r).save(a.png)
        print("wrote", a.png)
    ra, rb = np.frombuffer(sa[2], dtype="u1"), np.frombuffer(sb[2], dtype="u1")
    rd = np.nonzero(ra != rb)[0]
    print(f"RAM bytes differing: {len(rd)}")
    if len(rd):
        # summarize as ranges
        ranges = []
        start = prev = int(rd[0])
        for i in rd[1:]:
            i = int(i)
            if i > prev + 64:
                ranges.append((start, prev))
                start = i
            prev = i
        ranges.append((start, prev))
        ranges.sort(key=lambda r: -(r[1] - r[0]))
        for s, e in ranges[:25]:
            print(f"  0x{0x80000000 + s:08x}..0x{0x80000000 + e:08x} ({e - s + 1} bytes)")
        print(f"  ... {len(ranges)} ranges total")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info"); p.add_argument("file"); p.set_defaults(fn=cmd_info)
    p = sub.add_parser("vram"); p.add_argument("file"); p.add_argument("out"); p.set_defaults(fn=cmd_vram)
    p = sub.add_parser("ram"); p.add_argument("file"); p.add_argument("out"); p.set_defaults(fn=cmd_ram)
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--png")
    p.set_defaults(fn=cmd_diff)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
