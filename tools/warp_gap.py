#!/usr/bin/env python
"""Explain a warp sweep's residual: for every (area, pc) the sweep attributed,
say why the static seeds did not already cover it.

Reads a `tools/warp.py --attribute` report (results[].entered_pcs, the dirty-PC
rows whose entry count grew while that area was resident) and, for each pc in
the AREA band, looks at THAT area's image on the disc:

  seeded        the pc is in the capture's seed sets already (then it was still
                interpreted: the compile dropped it, or the piece for another
                occupant answered) -- the self-heal loop's business, not ours
  ptr:<where>   a word in the image points at it: descriptor field, the
                +0x3C handler array, the header run, or elsewhere (a pointer
                table the records do not walk yet -- a seed source to add)
  imm           materialized in code by lui/addiu or lui/ori (address-taken)
  section:<d>   a word in one of the AREA file's OTHER RAM sections points at it
  fn-start      no reference at all, but a `jr $ra` delay slot precedes it:
                a function entered from outside the file (GAME.EMI hook rows,
                or a pointer built at run time)
  mid-fn        no reference and no boundary: a label inside a function -- a
                switch-table target the strict resolver refused, or a return
                continuation into an uncompiled span

    python tools/warp_gap.py analysis/warp_<ts>.json [--top 40] [--cue CUE]
"""
import argparse
import json
import mmap
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls                       # noqa: E402
import loader_records as LR          # noqa: E402
from emi_survey import DiscFile      # noqa: E402

JR_RA = 0x03E00008
CUE = "isos/Breath of Fire III (Japan).cue"


def seed_set(cap):
    s = {}
    for k in ("header_entry_pcs", "static_discovery_entry_pcs", "engine_entry_pcs",
              "static_dispatch_entry_pcs", "dispatch_entry_pcs"):
        for x in cap.get(k, []):
            s.setdefault(int(x, 16) & 0x1FFFFFFF, set()).add(k.replace("_entry_pcs", "").replace("_pcs", ""))
    return s


def materialized(words, v):
    for i, w in enumerate(words):
        if (w >> 26) != 0x0F:
            continue
        rt, imm = (w >> 16) & 31, w & 0xFFFF
        for j in range(i + 1, min(i + 9, len(words))):
            w2 = words[j]
            op = w2 >> 26
            if op in (0x09, 0x0D) and ((w2 >> 21) & 31) == rt:
                lo = w2 & 0xFFFF
                val = (imm << 16) + (lo - 0x10000 if (op == 0x09 and lo & 0x8000) else lo)
                if val & 0xFFFFFFFF == v:
                    return i * 4
    return None


class Disc:
    def __init__(self, cue):
        fh = open(disc_ls.resolve_cue(cue), "rb")
        self.mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        self.read, _ = disc_ls.make_reader(self.mm)
        pvd = self.read(16)
        tree = disc_ls.walk(self.read, struct.unpack_from("<I", pvd, 158)[0],
                            struct.unpack_from("<I", pvd, 166)[0])
        self.locate = {p.upper(): (e, sz) for p, e, sz, d in tree if not d}
        self.secs = json.load(open("analysis/emi_sections.json"))["sections"]
        self.cache = {}

    def other_sections(self, path):
        if path not in self.cache:
            ext, fsz = self.locate[path.upper()]
            df = DiscFile(self.read, ext, fsz)
            out = []
            for x in self.secs:
                if x["file"].upper() == path.upper() and x["dest"] >= 0x80000000 and x["dest"] != LR.AREA_BAND:
                    out.append((x["dest"], df[x["offset"]:x["offset"] + x["size"]]))
            self.cache[path] = out
        return self.cache[path]


def classify(area, pc, im, disc, exe):
    v = pc | 0x80000000
    cap = im.cap
    if not im.inside(v):
        return "outside-image"
    seeds = seed_set(cap)
    if pc in seeds:
        return "seeded(%s)" % ",".join(sorted(seeds[pc]))
    words = struct.unpack("<%dI" % (len(im.data) // 4), im.data[:len(im.data) // 4 * 4])
    desc = LR.exe_u32(exe, LR.AREA_TABLE + area * 4)
    arr = im.u32(desc + LR.DESC_HANDLERS) if im.lo <= desc <= im.hi - LR.DESC_SIZE else 0
    tgt = struct.pack("<I", v)
    refs = []
    i = im.data.find(tgt)
    while i >= 0:
        p = im.lo + i
        if i % 4:
            refs.append("unaligned+0x%X" % i)
        elif desc <= p < desc + LR.DESC_SIZE:
            refs.append("descriptor+0x%X" % (p - desc))
        elif arr and arr <= p < desc:
            refs.append("handler-array")
        elif p < im.lo + 0x100:
            refs.append("header")
        else:
            refs.append("word+0x%X" % i)
        i = im.data.find(tgt, i + 1)
    if refs:
        return "ptr:" + ",".join(refs[:3])
    m = materialized(words, v)
    if m is not None:
        return "imm@+0x%X" % m
    for dest, blob in disc.other_sections(cap["source_file"]):
        j = blob.find(tgt)
        if j >= 0:
            return "section:%#x+0x%X%s" % (dest, j, "" if j % 4 == 0 else "(unaligned)")
    if v - 8 >= im.lo and im.u32(v - 8) == JR_RA:
        return "fn-start"
    if (im.u32(v) >> 16) == 0x27BD:
        return "fn-start(prologue)"
    return "mid-fn"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--cue", default=CUE)
    a = ap.parse_args()
    rep = json.load(open(a.report))
    images = {LR.area_number(im.cap): im
              for im in LR.load_captures(LR.CAPTURES)
              if im.lo == LR.AREA_BAND and LR.area_number(im.cap) is not None}
    exe = open(LR.EXE, "rb").read()
    disc = Disc(a.cue)
    rows = []
    for r in rep["results"]:
        for e in r.get("entered_pcs") or []:
            pc = int(e["pc"], 16) & 0x1FFFFFFF
            band = "AREA" if LR.AREA_BAND & 0x1FFFFFFF <= pc < (LR.AREA_BAND & 0x1FFFFFFF) + 0x4000 else "other"
            im = images.get(r["area"])
            if band != "AREA":
                cls = "band:%s" % ("kernel" if pc < 0x10000 else "0x%08X" % (pc | 0x80000000))
            elif im is None:
                cls = "no-capture(data-classed area)"
            else:
                cls = classify(r["area"], pc, im, disc, exe)
            rows.append((r["area"], e["pc"], e["entries"], e["insns"], cls))
    rows.sort(key=lambda x: -x[3])
    import collections
    kinds = collections.Counter(x[4].split("(")[0].split(":")[0].split("@")[0] for x in rows)
    print("%d (area, pc) pairs entered during the sweep; by class: %s\n" % (len(rows), dict(kinds.most_common())))
    print("%-5s %-12s %8s %9s  %s" % ("area", "pc", "entries", "insns", "why the static seeds missed it"))
    for area, pc, en, ins, cls in rows[:a.top]:
        print("%-5d %-12s %8d %9d  %s" % (area, pc, en, ins, cls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
