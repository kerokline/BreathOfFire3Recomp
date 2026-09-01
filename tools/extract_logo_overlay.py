#!/usr/bin/env python
"""Build a static-emi-v1 overlay capture for LOGO/LOGO.EXE.

The opening/Capcom logo sequence runs from LOGO/LOGO.EXE, a standalone PS-EXE
loaded to 0x801CE000 (text size 0x1D800). It is NOT an .EMI section, so
tools/extract_overlays.py never captured it, and it runs 100% in the dirty-RAM
interpreter -- the Capcom-logo lag (root-caused 2026-09-01: ~19 present-fps,
0 native dispatch, one PC 0x801CEEDC = 84.5% of interp work).

This produces one capture the same shape as an .EMI capture, so
compile_overlays.py --static compiles the logo player natively like any other
overlay. The CRC gate handles its RAM overlap with the PLCHAR/battle bands: the
logo bytes and a PLCHAR occupant are two content-guarded variants of the same
addresses, and the resident one wins the dispatch.

Discovery is identical to extract_overlays: in-region JAL targets + prologue
roots, plus any observed interpreted PCs in range and the EXE entry point.
compile_overlays re-validates every root against its own callable test, so a
false root in the EXE's data/BSS tail is dropped, not fabricated.

    python tools/extract_logo_overlay.py "isos/Breath of Fire III (Japan).cue" \
        --out analysis/logo_capture.json
"""
import argparse
import base64
import binascii
import hashlib
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls
from extract_overlays import jal_targets, prologue_roots, load_observed

EXE_PATH = "LOGO/LOGO.EXE"


def read_disc_file(cue, want):
    """Return the raw bytes of one file inside the ISO9660 tree."""
    binpath = (disc_ls.resolve_cue(cue) if cue.lower().endswith(".cue") else cue)
    with open(binpath, "rb") as fh:
        data = fh.read()
    read, _ = disc_ls.make_reader(data)
    pvd = read(16)
    tree = disc_ls.walk(read, struct.unpack_from("<I", pvd, 158)[0],
                        struct.unpack_from("<I", pvd, 166)[0])
    want_u = want.upper()
    for path, ext, sz, is_dir in tree:
        if not is_dir and path.upper() == want_u:
            return disc_ls.read_extent(read, ext, sz)
    raise SystemExit("not found on disc: %s" % want)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--out", default="analysis/logo_capture.json")
    ap.add_argument("--append-to",
                    help="also merge the LOGO capture into this existing captures "
                         "list (e.g. analysis/overlay_captures_all.json), replacing "
                         "any prior LOGO.EXE entry. This is what keeps LOGO in the "
                         "canonical set that the build reads, so a re-run of "
                         "extract_overlays (which rebuilds that file from .EMI only) "
                         "does not silently drop the compiled logo player.")
    ap.add_argument("--observed", default=None,
                    help="observed_interp_pcs.json to draw interior dispatch "
                         "entries from. OFF by default: the global observed file "
                         "accumulates PCs across ALL overlays that share this RAM "
                         "(PLCHAR/battle), and attributing those to LOGO produces "
                         "spurious dispatch entries with no LOGO body (the "
                         "static_unresolved class). Pass a LOGO-resident-only "
                         "harvest here for the pass-2 interior-entry refinement.")
    args = ap.parse_args()

    exe = read_disc_file(args.cue, EXE_PATH)
    if exe[:8] != b"PS-X EXE":
        raise SystemExit("%s is not a PS-X EXE (magic=%r)" % (EXE_PATH, exe[:8]))
    entry_pc, _gp, t_addr, t_size = struct.unpack_from("<IIII", exe, 0x10)
    text = exe[0x800:0x800 + t_size]
    if len(text) != t_size:
        raise SystemExit("short text: have %d want %d" % (len(text), t_size))

    load = t_addr
    roots = jal_targets(text, load) | prologue_roots(text, load)

    # Interior dispatch entries. Static discovery drives the call-graph walk; the
    # EXE entry point is always seeded. The function-pointer handlers LOGO installs
    # at runtime are invisible to the static walk (see tools/harvest_logo_handlers.py),
    # so we also seed a TRACKED, committed list of them — harvested once from a live
    # LOGO-resident run and kept in tools/logo_dispatch_pcs.json — so a fresh
    # checkout reproduces the full fix without a live harvest. --observed unions in
    # any additional freshly-harvested interiors on top.
    phys_lo = load & 0x1FFFFFFF
    hits = {entry_pc}
    here = os.path.dirname(os.path.abspath(__file__))
    for src in (os.path.join(here, "logo_dispatch_pcs.json"), args.observed):
        if src and os.path.exists(src):
            hits |= {(load & 0xF0000000) | p for p in load_observed(src)
                     if phys_lo <= p < phys_lo + t_size}

    cap = {
        "schema": "static-emi-v1",
        "load_addr": "0x%08X" % load,
        "size": t_size,
        "bytes_b64": base64.b64encode(text).decode("ascii"),
        "static_discovery_entry_pcs": ["0x%08X" % a for a in sorted(roots)],
        "dispatch_entry_pcs": ["0x%08X" % a for a in sorted(hits)],
        "source_file": EXE_PATH,
        "source_index": 0,
        "source_md5": hashlib.md5(text).hexdigest(),
        "crc32": "0x%08X" % (binascii.crc32(text) & 0xFFFFFFFF),
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump([cap], fh, indent=1)

    if args.append_to:
        existing = []
        if os.path.exists(args.append_to):
            with open(args.append_to) as fh:
                existing = json.load(fh)
        # drop any prior LOGO.EXE capture so re-runs stay idempotent
        existing = [c for c in existing
                    if c.get("source_file", "").upper() != EXE_PATH.upper()]
        existing.append(cap)
        with open(args.append_to, "w") as fh:
            json.dump(existing, fh, indent=1)
        print("merged into %s (%d captures total)" % (args.append_to, len(existing)))

    print("LOGO.EXE  load=0x%08X  entry=0x%08X  text=%d bytes" % (load, entry_pc, t_size))
    print("  spans 0x%08X .. 0x%08X" % (load, load + t_size))
    print("  static roots : %d  (jal targets + prologues)" % len(roots))
    print("  dispatch pcs : %d  (observed-in-range + entry)" % len(hits))
    print("-> %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
