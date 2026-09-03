#!/usr/bin/env python
"""Harvest observed interpreted entry PCs from a LIVE run.

Why this exists: `psxrecomp-analyze` is deliberately static-only (see
`psxrecomp/docs/FUNCTION_DISCOVERY.md` rule 1 — "no executed-PC feedback"), so
it cannot see that the game jumps into the *middle* of an oversized
low-confidence span, or into an overlay entry only reached through dynamic
dispatch. The recompiler registers the span's start, the game enters at an
interior address, that address has no dispatch entry, and every instruction
from there runs in the dirty-RAM interpreter.

The runtime knows exactly where it entered. `dirty_ram_stats.per_pc` records
each interpreted PC with an `entries` count; a PC with `entries > 0` is an
empirically proven function entry.

Downstream is the OVERLAY lane, not the seed lane. These are overlay addresses
reached by dynamic dispatch; feeding them to `seeds/ghidra_funcs.txt` (the
boot-EXE analyser) is a proven dead end (a byte-identical generate — see
docs/HANDOFF.md "Seeding is a dead end"). The load-bearing output is
`analysis/observed_interp_pcs.json`, which `tools/extract_overlays.py --observed`
reads to attribute entered PCs to overlay bands.

Coverage accumulates across sessions. Each play session enters a DIFFERENT set
of overlay addresses (which .EMI area is resident decides which PCs bucket to a
band), so two sessions are nearly disjoint — measured 2026-08-31, two sessions
shared only 323 of ~17,500 PCs. Overwriting the observed file would therefore
throw away every area you did not revisit this run. So this tool UNIONs into the
existing file, keeping one distinct row per PC (no duplicates), and reports how
many are newly seen. Run it after every session; the set only grows. `area_poller.py watch` also
calls harvest() on a timer (default every 15 min) so a session that dies early
keeps most of its coverage.

    python tools/harvest_interp_pcs.py            # query, report, union-save
    python tools/harvest_interp_pcs.py --port N   # non-default debug port

Then re-run extract_overlays.py --observed, recompile all bands, rebuild,
re-measure (docs/HANDOFF.md, "The next task").
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playsession import send, need_ok      # noqa: E402


def norm_pc(pc_str):
    """Normalize a per_pc physical address to a stable hex key (see the
    HANDOFF trap: harvest writes PHYSICAL PCs, e.g. 0x001D7524)."""
    return "0x%08X" % (int(pc_str, 16) & 0x1FFFFFFF)


def load_existing(path):
    """Existing observed rows keyed by normalized PC. Missing/empty -> {}."""
    if not path or not os.path.exists(path):
        return {}
    try:
        rows = json.load(open(path))
    except (ValueError, OSError):
        return {}
    out = {}
    for r in rows:
        if "pc" in r:
            out[norm_pc(r["pc"])] = r
    return out


def merge_row(old, new):
    """Union one PC's observations across sessions. Keep the DISTINCT PC once;
    take the max of the count fields so a hot PC stays visible and a PC is not
    double-counted if the same run is harvested twice."""
    if old is None:
        return dict(new)
    out = dict(old)
    for k in ("entries", "insns", "entry_hits", "hits"):
        if k in new or k in old:
            out[k] = max(int(new.get(k, 0)), int(old.get(k, 0)))
    return out


def harvest(port=4370, save_json="analysis/observed_interp_pcs.json",
            no_save=False, min_insns=0, quiet=False):
    """Query the live runtime and union its per-PC table into save_json.

    Read-only on the runtime side (dirty_ram_stats walks the PC table; nothing
    is reset), so this is safe to call repeatedly during play -- area_poller.py
    watch does exactly that on a timer so a session that dies before its
    end-of-run harvest (2026-09-02: a Windows Terminal crash took a 74-minute
    session) loses at most one interval of coverage.

    The observed file is written atomically (temp file + os.replace) so a kill
    mid-write can never leave a truncated JSON behind.

    Returns a dict: interp, native, aborts, misses, before, after, new,
    entered, newly_seen (list of (pc, entries, insns)).
    """
    d = need_ok(send({"cmd": "dirty_ram_stats"}, port=port, timeout=120.0),
                "dirty_ram_stats")
    s = need_ok(send({"cmd": "dispatch_stats"}, port=port, timeout=60.0),
                "dispatch_stats")
    interp, native = d["insns_run"], s["static_hits"]
    total = interp + native
    if not quiet:
        print("interpreted : {:>14,}  ({:.1f}%)".format(interp, 100.0 * interp / max(total, 1)))
        print("native      : {:>14,}  ({:.1f}%)".format(native, 100.0 * native / max(total, 1)))
        print("aborts      : %s   dispatch misses: %s" % (d["aborts"], s["miss_total"]))

    per_pc = d.get("per_pc") or []

    # Union this session's rows into the accumulated distinct set.
    existing = load_existing(save_json)
    before = len(existing)
    newly_seen = []
    for e in per_pc:
        key = norm_pc(e["pc"])
        was_present = key in existing
        merged = merge_row(existing.get(key), e)
        merged["pc"] = key
        existing[key] = merged
        if not was_present and int(e.get("entries", 0)) > 0:
            newly_seen.append((key, int(e.get("entries", 0)), int(e.get("insns", 0))))

    merged_rows = sorted(existing.values(),
                         key=lambda r: -int(r.get("insns", 0)))
    entered = sum(1 for r in merged_rows if int(r.get("entries", 0)) > 0)

    if not no_save and save_json:
        os.makedirs(os.path.dirname(save_json) or ".", exist_ok=True)
        tmp = save_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(merged_rows, fh, indent=1)
        os.replace(tmp, save_json)
        if not quiet:
            print("\nobserved set: %d distinct PCs (%d entered), %d new this session "
                  "-> %s" % (len(merged_rows), entered, len(existing) - before,
                             save_json))

    shown = [c for c in newly_seen if c[2] >= min_insns]
    shown.sort(key=lambda c: -c[2])
    if not quiet:
        # Report the hottest entries this session that were not already accumulated.
        print("\nnew proven entries this session: %d" % len(shown))
        for pc, ent, ins in shown[:20]:
            print("   %s  entries=%-8d insns=%d" % (pc, ent, ins))
        if len(shown) > 20:
            print("   ... and %d more" % (len(shown) - 20))

    return {"interp": interp, "native": native, "aborts": d["aborts"],
            "misses": s["miss_total"], "before": before, "after": len(merged_rows),
            "new": len(existing) - before, "entered": entered, "newly_seen": shown}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-insns", type=int, default=0,
                    help="report filter only: hide entries with fewer "
                         "interpreted instructions (never affects what is saved)")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--save-json", default="analysis/observed_interp_pcs.json")
    ap.add_argument("--no-save", action="store_true",
                    help="report only; do not touch the observed file")
    args = ap.parse_args()
    harvest(port=args.port, save_json=args.save_json, no_save=args.no_save,
            min_insns=args.min_insns)
    print("\nnext: tools/extract_overlays.py --observed  (reads %s),\n"
          "      then recompile all bands and rebuild." % args.save_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
