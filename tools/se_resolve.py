#!/usr/bin/env python
"""Resolve an SE_Play cue word to the sound it will actually make right now.

A cue word (docs/SOUND_CUES.md) is a slot, not a sound: bank<<8 | id picks
a 4-byte entry in the bank's cue table, that entry names a VAB program and
tone, libsnd's own VAB registry turns those into a VAG index, and the VAG
is whatever sample data is loaded at that SPU RAM address right now -- and
spells, areas and party changes replace the tables and the samples behind
the same words. So a catalogue keyed by cue word cannot be stable; one
keyed by the resolved sample can. This module does the resolution from any
pair of readers (live debug server, or a .pst savestate), the same way the
runtime does it:

    cue entry   0x8014869C + bank*0x7C + id*4      {flags, pan|prog, tone|pri, chord|voice}
    vab         flags & 7 if non-zero else bank     (SE_CueSetup_Bank*)
    header      libsnd registry 0x8018EB18[vab]    ("pBAV"; SsVabOpenHead writes it)
    tone attr   libsnd tone table 0x8018EB60[vab] + prog*0x200 + tone*0x20
                +2 vol, +3 pan, +4 centre note, +5 shift, +0x16 VAG index (1-based)
    VAG sizes   header + 0x20 + nprog*0x10 + ps*0x200, u16 x 256, units of 8 bytes
                (nprog = 0x80 when header[0] == 0x70 and version > 4, else 0x40)
    SPU start   libsnd 0x80191550[vab]  ->  sample = start + sum(sizes[1..vag-1])*8

    python tools/se_resolve.py saves/openbios/state_8014AA0C_slot03.pst 0x202 0x302 0x100

The sound id is the md5 of the sample bytes; the centre note and shift are
reported beside it because the same VAG at another pitch is another sound
to the ear.
"""
import hashlib
import struct
import sys

CUE_TABLES = 0x8014869C
CUE_STRIDE = 0x7C
VAB_HDR = 0x8018EB18        # libsnd: header pointer per vab id
VAB_TONE = 0x8018EB60       # libsnd: tone table pointer per vab id
VAB_SPU = 0x80191550        # libsnd: SPU RAM start per vab id
SPU_RAM_SIZE = 0x80000


class Unresolved(Exception):
    pass


def resolve(read_ram, read_spu, cue, want_sample=True):
    """read_ram(addr, n) -> bytes (guest RAM); read_spu(addr, n) -> bytes (SPU RAM).
    Returns a dict; raises Unresolved with a reason when the chain is broken."""
    bank, cid = (cue >> 8) & 0xF, cue & 0xFF
    if bank > 6 or cid > 30:
        raise Unresolved("cue 0x%04X: bank %d / id %d out of range" % (cue, bank, cid))
    e = read_ram(CUE_TABLES + bank * CUE_STRIDE + cid * 4, 4)
    if len(e) != 4 or e == b"\0\0\0\0":
        raise Unresolved("cue 0x%04X: empty cue entry" % cue)
    flags, pp, tp, cv = e
    vab = flags & 7 or bank
    prog, tone = pp & 0x7F, tp >> 4
    hdr = struct.unpack("<I", read_ram(VAB_HDR + vab * 4, 4))[0]
    if not (0x80000000 <= hdr < 0x80200000):
        raise Unresolved("cue 0x%04X: vab %d not open (header 0x%08X)" % (cue, vab, hdr))
    head = read_ram(hdr, 0x20)
    if head[:4] != b"pBAV":
        raise Unresolved("cue 0x%04X: vab %d header at 0x%08X is not a VAB" % (cue, vab, hdr))
    ver = struct.unpack_from("<I", head, 4)[0]
    ps = struct.unpack_from("<H", head, 0x12)[0]
    vs = struct.unpack_from("<H", head, 0x16)[0]
    nprog = 0x80 if (head[0] == 0x70 and ver > 4) else 0x40
    tonetab = struct.unpack("<I", read_ram(VAB_TONE + vab * 4, 4))[0]
    attr = read_ram(tonetab + prog * 0x200 + tone * 0x20, 0x20)
    vag = struct.unpack_from("<H", attr, 0x16)[0]
    if not (1 <= vag <= vs):
        raise Unresolved("cue 0x%04X: vab %d prog %d tone %d has VAG %d of %d" % (cue, vab, prog, tone, vag, vs))
    sizes = read_ram(hdr + 0x20 + nprog * 0x10 + ps * 0x200, 2 * (vag + 1))
    sz = struct.unpack("<%dH" % (vag + 1), sizes)
    off = sum(sz[1:vag]) * 8
    size = sz[vag] * 8
    base = struct.unpack("<I", read_ram(VAB_SPU + vab * 4, 4))[0]
    addr = base + off
    out = dict(cue="0x%04X" % cue, bank=bank, id=cid, vab=vab, prog=prog, tone=tone, vag=vag, vags=vs,
               centre=attr[4], shift=attr[5], vol=attr[2], pan=attr[3], priority=tp & 0xF,
               voice=cv & 0x1F, chord=(cv >> 5) & 3, spu="0x%05X" % addr, size=size)
    if addr + size > SPU_RAM_SIZE or size == 0:
        raise Unresolved("cue 0x%04X: VAG %d at 0x%05X size %d is outside SPU RAM" % (cue, vag, addr, size))
    if want_sample:
        smp = read_spu(addr, size)
        if len(smp) != size:
            raise Unresolved("cue 0x%04X: SPU read returned %d of %d bytes" % (cue, len(smp), size))
        out["sound"] = hashlib.md5(smp).hexdigest()[:12]
    return out


# ----------------------------------------------------------------- readers

def pst_readers(path):
    """(read_ram, read_spu) over a psxrecomp .pst savestate."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pst_tool
    _hdr, secs = pst_tool.load(path)
    ram, spu = secs[2], secs.get(10, b"")
    return (lambda a, n: ram[a - 0x80000000:a - 0x80000000 + n],
            lambda a, n: spu[a:a + n])


def live_readers(port):
    """(read_ram, read_spu) over the debug server (spu_ram reads at most 4 KB per call)."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import resident

    def read_ram(a, n):
        r = resident.q("read_ram", port, addr="0x%08X" % a, len=n)
        return bytes.fromhex(r["hex"]) if r.get("hex") else b""

    def read_spu(a, n):
        out = b""
        while len(out) < n:
            chunk = min(4096, n - len(out))
            r = resident.q("spu_ram", port, addr=a + len(out), len=chunk)
            got = bytes.fromhex(r["hex"]) if r.get("hex") else b""
            if not got:
                break
            out += got
        return out
    return read_ram, read_spu


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    read_ram, read_spu = pst_readers(argv[0])
    for a in argv[1:]:
        cue = int(a, 0)
        try:
            r = resolve(read_ram, read_spu, cue)
            print("%s -> sound %s  vab%d prog%d tone%d vag%d/%d  spu %s size %d  centre %d shift %d vol %d pan %d"
                  % (r["cue"], r["sound"], r["vab"], r["prog"], r["tone"], r["vag"], r["vags"], r["spu"], r["size"],
                     r["centre"], r["shift"], r["vol"], r["pan"]))
        except Unresolved as ex:
            print(ex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
