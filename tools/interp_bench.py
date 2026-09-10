#!/usr/bin/env python
"""Per-scene interpreted-work benchmark for A/B compiles.

Attaches to a live debug port (tools/scene.py hands one over), samples the
dirty-RAM interpreter counters, the VSync counter and the static overlay
dispatch counters over a fixed window, and appends one JSON row per scene.
The number that decides an A/B is `interp_insns_per_frame`: interpreted work
per emulated frame, independent of wall-clock speed.

    python tools/scene.py run --slot 3 -- python tools/interp_bench.py --port {port} --label A --slot 3 --out analysis/ab.jsonl
    python tools/interp_bench.py compare analysis/ab.jsonl A B
"""
import argparse
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps  # noqa: E402

VSYNC_ADDR = 0x8018603C
KEYS = ("static_checks", "static_hits", "static_variant_misses",
        "static_address_misses", "static_rehashes", "static_crc_misses")


def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=15.0)


def snap(port):
    d = q("dirty_ram_stats", port)
    o = q("overlay_loader_status", port)
    v = struct.unpack("<I", bytes.fromhex(q("read_ram", port, addr="0x%08X" % VSYNC_ADDR,
                                              len=4)["hex"]))[0]
    row = {"t": time.time(), "vsync": v, "insns": d["insns_run"], "blocks": d["blocks_run"]}
    for k in KEYS:
        row[k] = o.get(k, 0)
    return row


def cmd_sample(a):
    port = a.port or int(os.environ.get("PSX_SCENE_PORT", 0))
    if not port:
        raise SystemExit("--port or PSX_SCENE_PORT required")
    s0 = snap(port)
    time.sleep(a.seconds)
    s1 = snap(port)
    dt = s1["t"] - s0["t"]
    frames = s1["vsync"] - s0["vsync"]
    if frames <= 0:
        raise SystemExit("VSync did not advance during the window; scene is not running")
    row = {"label": a.label, "slot": a.slot, "seconds": round(dt, 2), "frames": frames,
           "emu_fps": round(frames / dt, 1),
           "interp_insns": s1["insns"] - s0["insns"],
           "interp_blocks": s1["blocks"] - s0["blocks"],
           "interp_insns_per_frame": round((s1["insns"] - s0["insns"]) / frames, 1)}
    for k in KEYS:
        row[k.replace("static_", "")] = s1[k] - s0[k]
    row["address_misses_per_frame"] = round(row["address_misses"] / frames, 2)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    print(json.dumps(row))


def cmd_compare(a):
    rows = [json.loads(l) for l in open(a.file, encoding="utf-8") if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["slot"], {})[r["label"]] = r   # last row per (slot,label) wins
    print("%-4s %14s %14s %8s   %10s %10s %8s   %7s %7s"
          % ("slot", "interp/frame " + a.a, "interp/frame " + a.b, "ratio",
             "amiss/f " + a.a, "amiss/f " + a.b, "ratio", "fps " + a.a, "fps " + a.b))
    ta = tb = 0
    for slot in sorted(by):
        ra, rb = by[slot].get(a.a), by[slot].get(a.b)
        if not (ra and rb):
            continue
        ia, ib = ra["interp_insns_per_frame"], rb["interp_insns_per_frame"]
        ma, mb = ra["address_misses_per_frame"], rb["address_misses_per_frame"]
        ta += ia; tb += ib
        print("%-4d %14.0f %14.0f %8s   %10.2f %10.2f %8s   %7.0f %7.0f"
              % (slot, ia, ib, ("%.2fx" % (ib / ia)) if ia else "n/a",
                 ma, mb, ("%.2fx" % (mb / ma)) if ma else "n/a",
                 ra["emu_fps"], rb["emu_fps"]))
    if ta:
        print("sum  %14.0f %14.0f %8.2fx" % (ta, tb, tb / ta))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest="sub")
    p = sub.add_parser("sample")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--label", required=True)
    p.add_argument("--slot", type=int, required=True)
    p.add_argument("--seconds", type=float, default=15.0)
    p.add_argument("--out", default="analysis/interp_bench.jsonl")
    p.set_defaults(fn=cmd_sample)
    p = sub.add_parser("compare")
    p.add_argument("file")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(fn=cmd_compare)
    argv = sys.argv[1:]
    if argv and argv[0] not in ("sample", "compare"):
        argv = ["sample"] + argv
    a = ap.parse_args(argv)
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
