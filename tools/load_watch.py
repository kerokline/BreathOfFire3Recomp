#!/usr/bin/env python
"""File-load timeline: every File_LoadRequest, live, with its file and caller.

The boot loader `File_LoadRequest(file_id)` (0x801629CC) stores its argument at
0x80146464 before anything else happens (docs/OVERLAY_HEADERS.md "The loader"),
so a write trace on that one cell is a loader hook with no framework change:
each row carries the file id, the store PC and the caller's return address
(a0..a3 and s0..s3 at the store). The file id resolves through the boot LBA
table (tools/file_ids.py), the return address through symbols.toml and
names/functions.toml.

    python tools/scene.py run --slot 1 -- python tools/load_watch.py --port {port} --seconds 30 --hold up --press circle ...
    python tools/load_watch.py --port 4370 --seconds 600         # during play

Appends one JSON row per load to analysis/load_timeline.jsonl. The previous
write-trace ranges are put back on exit (callstack_diff's arm/restore).
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callstack_diff as cd  # noqa: E402
import name_map  # noqa: E402
import resident  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "load_timeline.jsonl")
CELL = 0x80146464


def function_starts():
    """sorted [(pc, name)] over symbols.toml + names/functions.toml."""
    starts = []
    p = os.path.join(ROOT, "symbols.toml")
    if os.path.exists(p):
        for f in tomllib.load(open(p, "rb")).get("func", []):
            starts.append((int(f["pc"]), f["name"]))
    for (_md5, pc), e in name_map.load_function_names().items():
        starts.append((int(pc), e["name"]))
    return sorted(starts)


def name_for(pc, starts):
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid][0] <= pc:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return ""
    spc, name = starts[lo - 1]
    # nearest known start at or below ra -- a label, not proof the ra is inside it
    return name if pc - spc < 0x4000 else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--port", type=int, default=int(os.environ.get("PSX_SCENE_PORT", 4370)))
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = until Ctrl-C)")
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--press", action="append", default=[], help="press sequence injected after arming")
    ap.add_argument("--hold", action="append", default=[])
    ap.add_argument("--press-frames", type=int, default=2)
    ap.add_argument("--press-gap", type=int, default=20)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    ix = resident._load_index()
    starts = function_starts()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prev, armed = cd.wtrace_arm_ranges(a.port, [(CELL, CELL + 4)])
    print("load_watch: armed 0x%08X (%s), session %s -> %s" % (CELL, armed, session, a.out), flush=True)
    t0 = time.time()
    last_frame = cd.cur_frame(a.port)
    n = 0
    try:
        if a.press or a.hold:
            cd.press_buttons(a.port, a.press, a.press_frames, a.press_gap, hold=a.hold or None)
        while True:
            time.sleep(a.interval)
            fr = cd.cur_frame(a.port)
            if fr > last_frame:
                rows, _trunc = cd.drain_writes(a.port, last_frame + 1, fr)
                for e in rows:
                    if int(e["addr"], 16) & 0x1FFFFFFF != CELL & 0x1FFFFFFF:
                        continue
                    fid = int(e["new"], 16)
                    ra = int(e["ra"], 16)
                    path = ix["file_ids"].get(fid, "")
                    row = {"session": session, "frame": int(e["frame"]),
                           "t": dt.datetime.now().isoformat(timespec="seconds"),
                           "file_id": "0x%03X" % fid, "file": path,
                           "store_pc": e["pc"], "ra": e["ra"], "caller_nearest": name_for(ra, starts),
                           "args": e.get("args"), "s": e.get("s")}
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    n += 1
                    print("[f%d] load 0x%03X %-32s ra=%s %s" % (
                        row["frame"], fid, os.path.basename(path) or "(not a file id)",
                        e["ra"], row["caller_nearest"]), flush=True)
                last_frame = fr
            if a.seconds and time.time() - t0 >= a.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cd.wtrace_restore(a.port, prev)
    print("load_watch: %d load(s) recorded" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
