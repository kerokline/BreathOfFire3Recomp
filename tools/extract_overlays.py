#!/usr/bin/env python
"""Build overlay_captures.json from .EMI sections, statically.

BoF3's overlays are contiguous on disc and each .EMI TOC states the section's
RAM destination, so the (load_addr, bytes) pair the framework's Layer B wants
can be produced offline -- no DMA-time capture, no `[runtime] overlay_cache`.
See docs/OVERLAYS.md section 5 for why that is true here and not for Tomba.

Reads the survey written by tools/emi_survey.py, selects the sections that hold
code, and emits captures with statically derived entry seeds.

Both `code` and `mixed` survey classes are taken. `mixed` is not a third kind
of section -- it is what the survey's classifier says when a section holds code
but misses the `jr>=4 AND prologues>=4` gate, which leaf-heavy code does
routinely (WORLD04 AREA176-180: 34 `jr ra`, 3 prologues). Excluding it left 58
of 200 AREA files with nothing compiled at all. `--no-mixed` restores the old
behaviour for A/B work.

    python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue"
    python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" \
        --dest 0x80196800 --out analysis/overlay_captures.json

Seeds are call-edge evidence read out of the bytes themselves:

  * `static_discovery_entry_pcs` -- in-region JAL targets, plus prologues that
    directly follow a `jr $ra` delay slot. compile_overlays.py re-validates
    each against its own callable test and classifies survivors
    STATIC_DISCOVERY_ROOT, so a bad guess is dropped, not fabricated.
  * `dispatch_entry_pcs` -- PCs a live session actually interpreted, if
    analysis/observed_interp_pcs.json exists. Optional; purely additive.

Nothing here invents bytes: every capture is a verbatim disc section whose
TOC preview checksum matched (tools/emi_survey.py records `preview_ok`).
"""
import argparse
import base64
import binascii
import json
import mmap
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls
from emi_survey import DiscFile

JR_RA = 0x03E00008


def jal_targets(data, load_addr):
    """In-region JAL destinations -- direct call-edge proof of a function."""
    lo, hi = load_addr, load_addr + len(data)
    out = set()
    for w, in struct.iter_unpack("<I", data[:len(data) // 4 * 4]):
        if (w >> 26) == 3:
            tgt = (load_addr & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if lo <= tgt < hi:
                out.add(tgt)
    return out


def prologue_roots(data, load_addr):
    """`addiu sp,sp,-N` that opens a function: it follows a `jr $ra` delay
    slot, or it is the very first word of the section."""
    words = [w for w, in struct.iter_unpack("<I", data[:len(data) // 4 * 4])]
    out = set()

    def is_prologue(w):
        return (w >> 16) == 0x27BD and (w & 0x8000)

    for i, w in enumerate(words):
        if not is_prologue(w):
            continue
        if i == 0 or (i >= 2 and words[i - 2] == JR_RA):
            out.add(load_addr + i * 4)
    return out


def load_observed(path):
    """Physical PCs a live session actually *entered* (entries > 0).

    A PC the interpreter merely fell through is not evidence of a callable
    boundary, so only entered PCs are passed on as dispatch entries.
    """
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for item in doc:
        if item.get("entries", 0) <= 0:
            continue
        out.append(int(item["pc"], 16) & 0x1FFFFFFF)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--survey", default="analysis/emi_sections.json")
    ap.add_argument("--out", default="analysis/overlay_captures.json")
    ap.add_argument("--dest", action="append",
                    help="only this RAM destination (repeatable), e.g. 0x80196800")
    ap.add_argument("--file", action="append",
                    help="only sections from this disc path (repeatable)")
    # Mixed sections are taken BY DEFAULT since 2026-09-04. 58 of 200 AREA
    # files ship no `code` section at all -- their `mixed` section is the only
    # compilable code they have (AREA000 MacNeil Village, AREA001/002 Dauna
    # Mines, ...), so excluding it leaves those areas running fully
    # interpreted. See docs/HANDOFF.md "Mixed sections are extracted by
    # default" for the measurement that settled this.
    ap.add_argument("--no-mixed", action="store_true",
                    help="take only sections the survey classed 'code'. Drops "
                         "the only code 58 AREA files have -- for A/B "
                         "experiments, not normal runs")
    ap.add_argument("--include-mixed", action="store_true",
                    help="accepted and ignored; mixed sections are the default "
                         "now (kept so existing scripts and muscle memory "
                         "keep working)")
    ap.add_argument("--observed", default="analysis/observed_interp_pcs.json")
    args = ap.parse_args()

    with open(args.survey) as fh:
        survey = json.load(fh)

    want_cls = {"code"} if args.no_mixed else {"code", "mixed"}
    print("[extract] section classes: %s" % ", ".join(sorted(want_cls)))
    if args.no_mixed:
        print("[extract] WARNING --no-mixed: 58 AREA files have no 'code' section "
              "and contribute nothing to this capture set")
    dests = {int(d, 0) for d in args.dest} if args.dest else None
    files = {f.upper() for f in args.file} if args.file else None

    picked = []
    seen = set()
    for s in survey["sections"]:
        if s.get("class") not in want_cls:
            continue
        if dests is not None and s["dest"] not in dests:
            continue
        if files is not None and s["file"].upper() not in files:
            continue
        key = (s["dest"], s["md5"])
        if key in seen:            # identical bytes at the same address
            continue
        seen.add(key)
        picked.append(s)
    if not picked:
        raise SystemExit("no sections matched -- check --dest/--file")

    binpath = (disc_ls.resolve_cue(args.cue)
               if args.cue.lower().endswith(".cue") else args.cue)
    fh = open(binpath, "rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    read, _ = disc_ls.make_reader(mm)
    pvd = read(16)
    tree = disc_ls.walk(read, struct.unpack_from("<I", pvd, 158)[0],
                        struct.unpack_from("<I", pvd, 166)[0])
    locate = {p.upper(): (e, sz) for p, e, sz, d in tree if not d}

    observed = load_observed(args.observed)
    if observed:
        print("# %d observed interpreted PCs available" % len(observed))

    captures = []
    for s in picked:
        extent, fsize = locate[s["file"].upper()]
        blob = DiscFile(read, extent, fsize)[s["offset"]:s["offset"] + s["size"]]
        if len(blob) != s["size"]:
            raise SystemExit("%s#%d: short read" % (s["file"], s["index"]))
        import hashlib
        if hashlib.md5(blob).hexdigest() != s["md5"]:
            raise SystemExit("%s#%d: bytes differ from the survey" % (s["file"], s["index"]))
        load = s["dest"]
        roots = jal_targets(blob, load) | prologue_roots(blob, load)
        phys = load & 0x1FFFFFFF
        hits = sorted((load & 0xF0000000) | p for p in observed
                      if phys <= p < phys + s["size"])
        captures.append({
            "schema": "static-emi-v1",
            "load_addr": "0x%08X" % load,
            "size": s["size"],
            "bytes_b64": base64.b64encode(blob).decode("ascii"),
            "static_discovery_entry_pcs": ["0x%08X" % a for a in sorted(roots)],
            "dispatch_entry_pcs": ["0x%08X" % a for a in hits],
            "source_file": s["file"],
            "source_index": s["index"],
            "source_md5": s["md5"],
            "crc32": "0x%08X" % (binascii.crc32(blob) & 0xFFFFFFFF),
        })
        print("0x%08X  %8d bytes  %5d static roots  %4d observed  %s#%d"
              % (load, s["size"], len(roots), len(hits), s["file"], s["index"]))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as out:
        json.dump(captures, out, indent=1)
    print("\n# %d capture(s), %d bytes of overlay code -> %s"
          % (len(captures), sum(c["size"] for c in captures), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
