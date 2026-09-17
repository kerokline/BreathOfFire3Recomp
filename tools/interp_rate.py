#!/usr/bin/env python
"""Interpreted instructions per frame, per play session -- the Axis B headline.

    python tools/interp_rate.py [--timeline analysis/area_timeline.jsonl]
                                [--since 2026-09-12] [--min-frames 5000]

Lower is better. A PSX frame is ~560,000 guest instructions, so 400 per frame
means the interpreter is running 0.07 % of the game.

Why this number and not "estimated coverage": once the overlay bands were
seeded from the disc's own loader records (2026-09-12) the population of
interpreted PCs became tiny by design, and an incidence estimator over a tiny
population reports small, noisy percentages that read as "barely harvested"
when the truth is "nothing left to harvest". The cost the harvest exists to
remove is interpreted work, so measure that directly. Both runtime counters
start at process start, so each row is the whole-run average for one process;
a short run that sits in one screen (a memory-card menu, a battle) reads high
and is not comparable to a long walk -- hence --min-frames. Observed on
2026-09-15/16: the runtime's frame counter can go DOWN inside one watch
session (22 069 -> 21 779) while the interpreted-instruction counter keeps
climbing, so a row whose frames are small against its instructions is a run
whose counter restarted, not a slow one. Not root-caused; a savestate load
is the likely trigger. Compare long walks only.

Reads the `harvest` rows tools/area_poller.py appends to the timeline and
keeps the last row of each watch session (they are cumulative). Rows older
than 2026-09-16 carry no `interp_per_frame`; the same figure is derived from
their `interp` and `frame`.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMELINE = os.path.join(ROOT, "analysis", "area_timeline.jsonl")
GUEST_INSNS_PER_FRAME = 560_000        # ~33.87 MHz / 60 Hz, for the context column


def sessions(path):
    last = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("event") != "harvest":
                continue
            fr = int(r.get("frame") or 0)
            s = r.get("session")
            if s and (s not in last or fr >= int(last[s].get("frame") or 0)):
                last[s] = r
    return sorted(last.values(), key=lambda r: r.get("t") or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--timeline", default=TIMELINE)
    ap.add_argument("--since", default=None, help="ISO date; older sessions skipped")
    ap.add_argument("--min-frames", type=int, default=5000,
                    help="skip runs shorter than this (default 5000 = ~83 s)")
    a = ap.parse_args()
    if not os.path.exists(a.timeline):
        print("no timeline: %s" % a.timeline, file=sys.stderr)
        return 1
    rows = sessions(a.timeline)
    print("%-19s %-16s %9s %13s %9s %8s  %s"
          % ("started", "session", "frames", "interp insns", "per frame",
             "of guest", "last area"))
    shown = 0
    for r in rows:
        t = (r.get("t") or "")[:19]
        if a.since and t[:10] < a.since:
            continue
        fr = int(r.get("frame") or 0)
        if fr < a.min_frames:
            continue
        interp = int(r.get("interp") or 0)
        ipf = r.get("interp_per_frame")
        if ipf is None:
            ipf = interp / float(fr)
        area = (r.get("area_file") or "").split("/")[-1].replace(".EMI", "")
        print("%-19s %-16s %9s %13s %9.0f %7.2f%%  %s"
              % (t, (r.get("session") or "")[:16], "{:,}".format(fr),
                 "{:,}".format(interp), ipf,
                 100.0 * ipf / GUEST_INSNS_PER_FRAME, area))
        shown += 1
    if not shown:
        print("(no sessions match)")
    else:
        print("\nlower is better. whole-run averages; a run parked in one screen "
              "reads high.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
