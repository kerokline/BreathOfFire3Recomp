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
  * `pointer_roots` (folded into `static_discovery_entry_pcs`) -- every
    aligned word in the image that points at a code-shaped location inside
    the same image: the target follows a `jr $ra` delay slot or opens with a
    prologue. These are the small per-entity handler tables that sit in the
    middle of an area image and hang off nothing the loader records walk
    (2026-09-12 warp sweep: all 19 residual (area, pc) pairs were exactly
    this, 2,393 candidates game-wide). compile_overlays re-validates each
    with its callable test like any other discovery root. `--no-pointer-seeds`
    drops them for A/B work.
  * `dispatch_entry_pcs` -- PCs a live session actually interpreted, if
    analysis/observed_interp_pcs.json exists. Optional; purely additive.
  * `header_entry_pcs` -- the overlay's own exported entry table. Every .EMI
    overlay opens with a u32 registry id and then a run of pointers into its
    image (docs/OVERLAY_HEADERS.md); the game reaches these by dispatch, so
    they are exactly the interior entries a play session would otherwise have
    to harvest. Unioned into `dispatch_entry_pcs` and declared in
    `static_dispatch_entry_pcs` (compile_overlays classifies them
    STATIC_DISPATCH_ENTRY). `--no-header-seeds` drops them for A/B work.
    The registry id itself is emitted as `registry_id`.
  * `engine_entry_pcs` -- entry pcs the ENGINE holds for an overlay, read off
    the disc into names/ sidecars (docs/LOADER_RECORDS.md). The engine never
    enters an overlay through its header: the battle engine keeps a handler pc
    per ability (names/magic.toml) and per boss (boss_records.toml), the boot
    EXE a descriptor per area with an init pc and a handler array
    (area_records.toml), GAME.EMI a 5-slot vtable plus two sub-tables per
    scenario chapter (scenario_records.toml) and two u32[19] tables per party
    combo (plchar_records.toml). Each row names its section by md5 and this
    joins it back to the capture. They are interior entries reached by `jalr`,
    i.e. exactly what a play session would otherwise have to harvest, and
    they are disjoint from the header run (2026-09-12: 1398 pcs, 914 of them
    in no other seed set). Unioned into `dispatch_entry_pcs` /
    `static_dispatch_entry_pcs` like the header run; `--no-engine-seeds`
    drops them for A/B work.

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
# The framework's CFG proof for a call target without a prologue (bounded valid
# CFG with a reachable return, rejects pointer tables / NOP runways). Read-only
# use of the submodule's tool, the same one the compile itself runs.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "psxrecomp", "tools"))
from compile_overlays import plausible_callable_target  # noqa: E402

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


def pointer_roots(data, load_addr):
    """Aligned in-image words whose target is a provable function.

    Boundary shape first (the word before the target's delay slot is `jr $ra`,
    or the target opens with a prologue), then the framework's CFG proof: a
    bounded walk from the target in which every word decodes and a return is
    reachable. The shape alone admitted data that happens to decode -- the
    2026-09-12 first attempt doubled the audit-failed shards (26 -> 53).
    """
    words = [w for w, in struct.iter_unpack("<I", data[:len(data) // 4 * 4])]
    lo, hi = load_addr, load_addr + len(words) * 4
    out, seen = set(), set()
    for w in words:
        if not (lo <= w < hi) or w & 3 or w in seen:
            continue
        seen.add(w)
        i = (w - lo) // 4
        if (i >= 2 and words[i - 2] == JR_RA) or (words[i] >> 16) == 0x27BD and (words[i] & 0x8000):
            if plausible_callable_target(data, lo, len(data), w, hi):
                out.add(w)
    return out


def header_entries(data, load_addr):
    """(registry_id, [entry pcs]) from the overlay header.

    +0x00 is the u32 registry id; from +0x04 the words are entry pointers for
    as long as they are 4-byte-aligned addresses inside this image. A word
    that fails the test ends the run (32 of 124 BMAGIC images have no run at
    all). LOGO.EXE has no such header and never reaches here (it is captured
    by tools/extract_logo_overlay.py).
    """
    if len(data) < 8:
        return None, []
    lo, hi = load_addr, load_addr + len(data)
    reg_id = struct.unpack_from("<I", data, 0)[0]
    out = []
    for off in range(4, len(data) - 3, 4):
        w = struct.unpack_from("<I", data, off)[0]
        if not (lo <= w < hi) or w & 3:
            break
        out.append(w)
    return reg_id, out


ENGINE_RECORD_FILES = (
    "names/magic.toml",             # tools/magic_map.py:   ability -> BMAGIC handler pc
    "names/area_records.toml",      # tools/loader_records.py: area descriptor init/handlers + GAME.EMI hook rows
    "names/scenario_records.toml",  # tools/loader_records.py: chapter vtable + sub-tables
    "names/boss_records.toml",      # tools/loader_records.py: Boss_EntryTable
    "names/plchar_records.toml",    # tools/loader_records.py: PLCHAR entry tables + per-slot tail
)


def load_engine_entries(paths=ENGINE_RECORD_FILES):
    """{section md5: set(entry pc)} from the engine's loader records.

    Each sidecar holds rows with `section` (md5 of the code section the record
    loads) and `entry` (the handler pc the engine jumps to once it is
    resident). Rows with no section (engine-side handlers) carry no overlay
    entry and are skipped. Any future record table (area, boss, scenario,
    character) joins the same way: add its sidecar to ENGINE_RECORD_FILES.
    """
    import tomllib
    out = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, "rb") as fh:
            doc = tomllib.load(fh)
        for rows in doc.values():
            if not isinstance(rows, list):
                continue
            for r in rows:
                sec = r.get("section") or ""
                if not sec or not r.get("entry"):
                    continue
                out.setdefault(sec, set()).add(int(r["entry"], 16))
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
    ap.add_argument("--no-header-seeds", action="store_true",
                    help="do not seed the header entry table (A/B experiments "
                         "only; header seeds are included by default)")
    ap.add_argument("--no-pointer-seeds", action="store_true",
                    help="do not seed in-image code pointers (A/B experiments only)")
    ap.add_argument("--no-engine-seeds", action="store_true",
                    help="do not seed the engine's loader-record entry pcs "
                         "(names/magic.toml; A/B experiments only)")
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
    engine = {} if args.no_engine_seeds else load_engine_entries()
    if engine:
        print("# %d engine loader-record entry PCs across %d sections"
              % (sum(len(v) for v in engine.values()), len(engine)))

    captures = []
    engine_joined = engine_dropped = 0
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
        ptr_roots = set() if args.no_pointer_seeds else pointer_roots(blob, load) - roots
        roots |= ptr_roots
        phys = load & 0x1FFFFFFF
        hits = set((load & 0xF0000000) | p for p in observed
                   if phys <= p < phys + s["size"])
        reg_id, hdr = header_entries(blob, load)
        hdr_set = set() if args.no_header_seeds else set(hdr)
        # Engine records name a section by md5; keep only pcs that are
        # 4-aligned and inside this image (a record whose pc is outside its
        # own file would be a decode error, not a seed).
        eng_all = engine.get(s["md5"], set())
        eng = {a for a in eng_all if load <= a < load + s["size"] and not a & 3}
        engine_joined += len(eng)
        engine_dropped += len(eng_all) - len(eng)
        static_set = hdr_set | eng
        dispatch = sorted(hits | static_set)
        captures.append({
            "schema": "static-emi-v1",
            "load_addr": "0x%08X" % load,
            "size": s["size"],
            "bytes_b64": base64.b64encode(blob).decode("ascii"),
            "registry_id": "0x%03X" % reg_id,
            "header_entry_pcs": ["0x%08X" % a for a in hdr],
            "static_discovery_entry_pcs": ["0x%08X" % a for a in sorted(roots)],
            "engine_entry_pcs": ["0x%08X" % a for a in sorted(eng)],
            "dispatch_entry_pcs": ["0x%08X" % a for a in dispatch],
            "static_dispatch_entry_pcs": ["0x%08X" % a for a in sorted(static_set)],
            "source_file": s["file"],
            "source_index": s["index"],
            "source_md5": s["md5"],
            "crc32": "0x%08X" % (binascii.crc32(blob) & 0xFFFFFFFF),
        })
        print("0x%08X  %8d bytes  id 0x%03X  %5d static roots (%3d ptr)  %4d observed  %3d header  %3d engine  %s#%d"
              % (load, s["size"], reg_id, len(roots), len(ptr_roots), len(hits), len(hdr),
                 len(eng), s["file"], s["index"]))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as out:
        json.dump(captures, out, indent=1)
    print("\n# %d capture(s), %d bytes of overlay code -> %s"
          % (len(captures), sum(c["size"] for c in captures), args.out))
    if engine:
        print("# engine records: %d entry pcs joined, %d outside their image (dropped)"
              % (engine_joined, engine_dropped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
