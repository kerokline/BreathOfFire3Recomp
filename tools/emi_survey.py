#!/usr/bin/env python
"""Survey every .EMI on the disc: read each TOC, code-test each section.

Step 1+2 of the static overlay extraction plan (docs/OVERLAYS.md section 5).
Reads only what it needs -- header/TOC sectors for every container, and the
section bytes for candidates whose RAM destination lands in the code region --
so the 259 MB of .EMI data is never staged to disk.

    python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue"
    python tools/emi_survey.py <cue> --out analysis/emi_sections.json

Code test: a section is called code when it carries `jr $ra` (0x03E00008)
and `addiu sp,sp,-N` (0x27BD with bit 15 of the immediate set) at a density a
data blob does not reach.  AREA004.EMI section 8 (0x80104000) is the known
negative control -- zero of both.
"""
import argparse
import hashlib
import json
import mmap
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls
from emi import Emi

USER = disc_ls.USER

# PSX main RAM, kernel area excluded.  Anything a code overlay can land in.
RAM_LO = 0x80010000
RAM_HI = 0x80200000

JR_RA = 0x03E00008


class DiscFile(object):
    """Random access to one ISO9660 file without materialising it."""

    def __init__(self, read, extent, size):
        self.read, self.extent, self.size = read, extent, size

    def __getitem__(self, sl):
        start, stop = sl.start or 0, self.size if sl.stop is None else sl.stop
        start = max(0, min(start, self.size))
        stop = max(start, min(stop, self.size))
        out = bytearray()
        lba = self.extent + start // USER
        skip = start % USER
        want = stop - start
        while want > 0:
            chunk = self.read(lba)[skip:]
            out += chunk[:want]
            want -= len(chunk[:want])
            skip = 0
            lba += 1
        return bytes(out)


def code_stats(blob):
    """(words, jr_ra, prologues) for a candidate section."""
    n = len(blob) // 4
    jr = pro = 0
    for w, in struct.iter_unpack("<I", blob[:n * 4]):
        if w == JR_RA:
            jr += 1
        elif (w >> 16) == 0x27BD and (w & 0x8000):
            pro += 1
    return n, jr, pro


def classify(words, jr, pro):
    if words == 0:
        return "empty"
    if jr == 0 and pro == 0:
        return "data"
    # One function per ~100 words is already sparse for MIPS; data blobs that
    # happen to contain a 0x03E00008 word land far below this.
    per_kword = 1000.0 * (jr + pro) / words
    if jr >= 4 and pro >= 4 and per_kword >= 2.0:
        return "code"
    return "mixed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--out", default="analysis/emi_sections.json")
    ap.add_argument("--limit", type=int, help="stop after N .EMI files (smoke test)")
    args = ap.parse_args()

    binpath = (disc_ls.resolve_cue(args.cue)
               if args.cue.lower().endswith(".cue") else args.cue)
    fh = open(binpath, "rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    read, mode = disc_ls.make_reader(mm)

    pvd = read(16)
    root_extent = struct.unpack_from("<I", pvd, 158)[0]
    root_size = struct.unpack_from("<I", pvd, 166)[0]
    entries = disc_ls.walk(read, root_extent, root_size)
    emis = [e for e in entries if not e[3] and e[0].upper().endswith(".EMI")]
    emis.sort(key=lambda e: e[0])
    if args.limit:
        emis = emis[:args.limit]

    print("# %s (%s)" % (binpath, mode))
    print("# %d .EMI containers, %d bytes total"
          % (len(emis), sum(e[2] for e in emis)))

    records = []
    bad = []
    for path, extent, size, _ in emis:
        df = DiscFile(read, extent, size)
        head = df[0:0x800]
        try:
            emi = Emi(head + b"\x00" * max(0, 0x800 - len(head)), path)
        except ValueError as exc:
            bad.append((path, str(exc)))
            continue
        for e in emi.entries:
            dest = e["dest"]
            rec = {
                "file": path, "index": e["index"], "size": e["size"],
                "dest": dest, "type": e["type"], "offset": e["offset"],
            }
            if e["size"] == 0:
                rec["class"] = "empty"
                records.append(rec)
                continue
            # Every section is hashed, RAM-bound or not: VRAM image sections
            # (type 3) and audio need content identity too, because a regional
            # redraw can keep the size and change the pixels.
            blob = df[e["offset"]:e["offset"] + e["size"]]
            rec["preview_ok"] = blob[:4] == e["preview"]
            rec["md5"] = hashlib.md5(blob).hexdigest()
            if not (RAM_LO <= dest < RAM_HI) or e["size"] < 64:
                rec["class"] = "not-ram"
                records.append(rec)
                continue
            words, jr, pro = code_stats(blob)
            rec.update(words=words, jr_ra=jr, prologues=pro,
                       cls=classify(words, jr, pro))
            rec["class"] = rec.pop("cls")
            records.append(rec)
        print("  %-28s %3d sections" % (path, emi.count))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as out:
        json.dump({"disc": os.path.basename(binpath),
                   "files": len(emis), "sections": records}, out, indent=1)

    code = [r for r in records if r.get("class") == "code"]
    mixed = [r for r in records if r.get("class") == "mixed"]
    print("\n# %d sections total: %d code, %d mixed, %d data, %d other"
          % (len(records), len(code), len(mixed),
             sum(1 for r in records if r.get("class") == "data"),
             sum(1 for r in records if r.get("class") in ("not-ram", "empty"))))
    if bad:
        print("# %d container(s) failed to parse" % len(bad))
        for p, m in bad[:10]:
            print("#   %s: %s" % (p, m))
    print("# wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
