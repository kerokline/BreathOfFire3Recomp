#!/usr/bin/env python
"""Harvest observed interpreted entry PCs from a LIVE run into the seed list.

Why this exists: `psxrecomp-analyze` is deliberately static-only (see
`psxrecomp/docs/FUNCTION_DISCOVERY.md` rule 1 — "no executed-PC feedback"), so
it cannot see that the game jumps into the *middle* of an oversized
low-confidence span. The recompiler registers the span's start, the game enters
at an interior address, that address has no dispatch entry, and every
instruction from there runs in the dirty-RAM interpreter.

Measured 2026-08-30 before any of this was fixed: 264,004,486 interpreted
instructions against 28,021,168 native dispatches — roughly 90% interpreted.

The runtime knows exactly where it entered. `dirty_ram_stats.per_pc` records
each interpreted PC with an `entries` count; a PC with `entries > 0` is an
empirically proven function entry. Feed those back as seeds.

Run it with the game running (build-dbg, --debug-port), ideally after playing
through as much as possible — coverage is only as good as what you exercised.

    python tools/harvest_interp_pcs.py                 # report only
    python tools/harvest_interp_pcs.py --write         # append new seeds

Then regenerate and rebuild, and re-measure the ratio with --report-only.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playsession import send, need_ok      # noqa: E402

SEEDS = "seeds/ghidra_funcs.txt"


def load_seeds(path):
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("0x"):
                out.add(int(s, 16))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--min-insns", type=int, default=0,
                    help="ignore entries with fewer interpreted instructions")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--save-json", default="analysis/observed_interp_pcs.json")
    args = ap.parse_args()

    d = need_ok(send({"cmd": "dirty_ram_stats"}, port=args.port, timeout=120.0),
                "dirty_ram_stats")
    s = need_ok(send({"cmd": "dispatch_stats"}, port=args.port, timeout=60.0),
                "dispatch_stats")
    interp, native = d["insns_run"], s["static_hits"]
    total = interp + native
    print("interpreted : {:>14,}  ({:.1f}%)".format(interp, 100.0 * interp / max(total, 1)))
    print("native      : {:>14,}  ({:.1f}%)".format(native, 100.0 * native / max(total, 1)))
    print("aborts      : %s   dispatch misses: %s" % (d["aborts"], s["miss_total"]))

    per_pc = d.get("per_pc") or []
    if args.save_json:
        os.makedirs(os.path.dirname(args.save_json), exist_ok=True)
        json.dump(per_pc, open(args.save_json, "w"), indent=1)
        print("\nwrote %s (%d tracked PCs)" % (args.save_json, len(per_pc)))

    have = load_seeds(SEEDS)
    cands = []
    for e in per_pc:
        if e.get("entries", 0) <= 0:
            continue
        if e.get("insns", 0) < args.min_insns:
            continue
        pc = 0x80000000 | int(e["pc"], 16)
        if pc in have:
            continue
        cands.append((pc, e["entries"], e["insns"]))
    cands.sort(key=lambda c: -c[2])

    print("\nproven entries not yet seeded: %d" % len(cands))
    for pc, ent, ins in cands[:20]:
        print("   0x%08X  entries=%-8d insns=%d" % (pc, ent, ins))
    if len(cands) > 20:
        print("   ... and %d more" % (len(cands) - 20))

    if not args.write:
        print("\nreport only — pass --write to append to %s" % SEEDS)
        return 0
    if not cands:
        print("\nnothing new to add.")
        return 0

    with open(SEEDS, "a", encoding="utf-8") as fh:
        fh.write("# harvested %d entries from a live run "
                 "(tools/harvest_interp_pcs.py)\n" % len(cands))
        for pc, _, _ in sorted(cands):
            fh.write("0x%08X\n" % pc)
    print("\nappended %d seeds to %s — regenerate and rebuild next." % (len(cands), SEEDS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
