#!/usr/bin/env python
"""Parse and extract sections from a BoF3 .EMI container.

Format per the community data doc:
https://glitcheddragon-dev.github.io/BoF3-Data-Doc/DataStructures/1_TheEmiFiles.html

    header (16 bytes)
        0x00 u32   entry count
        0x04 u32   version
        0x08 u8[8] magic "MATH_TBL"
    TOC, `count` x 16 bytes
        0x00 u32   data size
        0x04 u32   RAM destination pointer
        0x08 u8[4] first 4 bytes of the section's data
        0x0C u16   type id
        0x0E u16   garbage

Section data starts at 0x800 and each section is padded to a 2048-byte
boundary:  next = cur + ((size + 0x7FF) >> 0xB) * 0x800

The u8[4] preview is a free integrity check on that arithmetic -- `list`
verifies every section and flags any mismatch, so a wrong offset is loud
rather than silent.

    python tools/emi.py list  area.EMI
    python tools/emi.py diff  jp.EMI us.EMI
    python tools/emi.py extract area.EMI --index 18 --out sec18.bin
"""
import argparse
import struct
import sys

TYPES = {
    0: "misc/untyped",
    3: "image",
    6: "audio header (VH)",
    7: "audio samples (VB)",
    10: "sequence (SEQ)",
}


class Emi:
    def __init__(self, blob, name="<mem>"):
        self.blob = blob
        self.name = name
        if len(blob) < 16:
            raise ValueError("%s: too small to be an EMI" % name)
        self.count, self.version = struct.unpack_from("<II", blob, 0)
        self.magic = blob[8:16]
        if self.magic != b"MATH_TBL":
            raise ValueError("%s: bad magic %r (expected MATH_TBL)" % (name, self.magic))
        self.entries = []
        pos = 0x800
        for i in range(self.count):
            o = 0x10 + i * 16
            if o + 16 > len(blob):
                raise ValueError("%s: TOC entry %d runs past EOF" % (name, i))
            size, dest = struct.unpack_from("<II", blob, o)
            preview = blob[o + 8:o + 12]
            type_id, = struct.unpack_from("<H", blob, o + 12)
            self.entries.append({
                "index": i, "size": size, "dest": dest, "preview": preview,
                "type": type_id, "offset": pos,
            })
            pos += ((size + 0x7FF) >> 0xB) * 0x800

    def data(self, i):
        e = self.entries[i]
        return self.blob[e["offset"]:e["offset"] + e["size"]]

    def verify(self, i):
        """True if the section's real first 4 bytes match the TOC preview."""
        e = self.entries[i]
        if e["size"] == 0:
            return True
        return self.blob[e["offset"]:e["offset"] + 4] == e["preview"]


def load(path):
    with open(path, "rb") as fh:
        return Emi(fh.read(), path)


def fmt_type(t):
    return "%2d %s" % (t, TYPES.get(t, "?"))


def cmd_list(args):
    emi = load(args.emi)
    print("# %s" % emi.name)
    print("# count=%d version=%d magic=%s size=%d"
          % (emi.count, emi.version, emi.magic.decode(), len(emi.blob)))
    bad = 0
    print("%3s %10s %10s %12s  %-22s %s"
          % ("i", "offset", "size", "dest", "type", "ok"))
    for e in emi.entries:
        ok = emi.verify(e["index"])
        bad += (not ok)
        print("%3d 0x%08X %10d   0x%08X  %-22s %s"
              % (e["index"], e["offset"], e["size"], e["dest"],
                 fmt_type(e["type"]), "ok" if ok else "MISMATCH"))
    end = emi.entries[-1]["offset"] + emi.entries[-1]["size"] if emi.entries else 0
    print("# last section ends at %d (file %d, slack %d)"
          % (end, len(emi.blob), len(emi.blob) - end))
    if bad:
        print("# %d section(s) failed the preview check" % bad)
        return 1
    return 0


def cmd_diff(args):
    a, b = load(args.a), load(args.b)
    print("# A %s  (count=%d)" % (a.name, a.count))
    print("# B %s  (count=%d)" % (b.name, b.count))
    if a.count != b.count:
        print("# entry counts differ -- not the same area layout")
    n = min(a.count, b.count)
    print("%3s %12s  %10s %10s %9s  %-22s %s"
          % ("i", "dest", "A size", "B size", "delta", "type", "note"))
    for i in range(n):
        ea, eb = a.entries[i], b.entries[i]
        d = eb["size"] - ea["size"]
        same_prev = ea["preview"] == eb["preview"]
        if d == 0 and same_prev and ea["dest"] == eb["dest"]:
            continue
        note = []
        if d:
            note.append("SIZE")
        if not same_prev:
            note.append("DATA")
        if ea["dest"] != eb["dest"]:
            note.append("DEST")
        print("%3d   0x%08X  %10d %10d %+9d  %-22s %s"
              % (i, ea["dest"], ea["size"], eb["size"], d,
                 fmt_type(ea["type"]), ",".join(note)))
    return 0


def cmd_extract(args):
    emi = load(args.emi)
    i = args.index
    if not 0 <= i < emi.count:
        raise SystemExit("index %d out of range (0..%d)" % (i, emi.count - 1))
    if not emi.verify(i):
        print("warning: section %d failed the preview check" % i, file=sys.stderr)
    out = args.out or ("section_%02d.bin" % i)
    with open(out, "wb") as fh:
        fh.write(emi.data(i))
    e = emi.entries[i]
    print("wrote %s (%d bytes, offset 0x%X, dest 0x%08X, type %s)"
          % (out, e["size"], e["offset"], e["dest"], fmt_type(e["type"])))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("emi"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b"); p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("extract"); p.add_argument("emi")
    p.add_argument("--index", type=int, required=True); p.add_argument("--out")
    p.set_defaults(fn=cmd_extract)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
