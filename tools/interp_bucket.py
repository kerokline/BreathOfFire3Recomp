#!/usr/bin/env python
"""Where does the residual interpreted work live? Bucket the dirty-RAM per-PC
counters by region (kernel / boot EXE / overlay band) over a sampling window
on a live scene, and list the hottest PCs. Companion to interp_bench.py: the
bench says how much, this says where.

    python tools/scene.py run --slot 10 -- python tools/interp_bucket.py --port {port} --seconds 8
"""
import argparse
import collections
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps  # noqa: E402

BANDS = [(0x000C1800, "band 0x800C1800"), (0x000F5000, "band 0x800F5000"),
         (0x00117000, "band 0x80117000"), (0x00196800, "band 0x80196800"),
         (0x001CE000, "LOGO.EXE"), (0x001CE400, "PLCHAR band 0x801CE400"),
         (0x001D0C00, "game-mode band 0x801D0C00"), (0x001EEC00, "BMAGIC band 0x801EEC00"),
         (0x001F2C00, "WORLD band 0x801F2C00"), (0x001F6C00, "SCENARIO band 0x801F6C00")]


def region(pc):
    if pc < 0x10000:
        return "kernel RAM"
    if pc < 0x93800:
        return "low RAM (data/loader)"
    r = "boot EXE"
    for base, name in BANDS:
        if pc >= base:
            r = name
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PSX_SCENE_PORT", 0)))
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    def q(c, **k):
        return ps.send(dict(cmd=c, **k), port=a.port, timeout=30.0)

    def snap():
        d = q("dirty_ram_stats")
        rows = {int(r["pc"], 16) & 0x1FFFFFFF: (int(r.get("insns", 0)), int(r.get("entries", 0)),
                                                 r.get("occ_crc")) for r in d.get("per_pc", [])}
        return rows, d

    s0, d0 = snap()
    time.sleep(a.seconds)
    s1, d1 = snap()
    total = d1["insns_run"] - d0["insns_run"]
    tot, cnt, top = collections.Counter(), collections.Counter(), []
    for pc, (i1, e1, crc) in s1.items():
        i0, e0, _ = s0.get(pc, (0, 0, None))
        d = i1 - i0
        if d <= 0:
            continue
        r = region(pc)
        tot[r] += d
        cnt[r] += 1
        top.append((d, pc, r, crc, e1 - e0))
    seen = sum(tot.values())
    print("window %.1fs: %d interp insns total, %d attributed in per_pc (%d rows)"
          % (a.seconds, total, seen, len(s1)))
    for r, v in tot.most_common():
        print("  %-28s %10d  %5.1f%%   pcs=%d" % (r, v, 100.0 * v / max(seen, 1), cnt[r]))
    print("hottest PCs:")
    for d, pc, r, crc, e in sorted(top, reverse=True)[:a.top]:
        print("  0x%08X %9d insns %6d entries  %-28s occ=%s" % (pc | 0x80000000, d, e, r, crc))


if __name__ == "__main__":
    main()
