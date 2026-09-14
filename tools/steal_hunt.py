#!/usr/bin/env python
"""Hunt the steal roll: replay one battle round from a savestate anchor until
a steal (ぶんどり / 盗む) succeeds, keeping the write-traced capture of the
successful round and the first failed one for a diff.

    python tools/steal_hunt.py --slot 3 --attempts 40
    python tools/steal_hunt.py --slot 3 --attempts 1 --window-frames 900   # sizing run

Each attempt is one `tools/callstack_diff.py capture` (savestate load, one
Circle press, fn_filter over the battle engine band BATTLE.EMI#15 at
0x80093800, write trace on the battle loot list 0x80146320-0x80146360 and
the inventory arrays 0x80145040-0x80145470). A steal is detected as a
watched cell that changed between arm and end of the window, or a traced
write whose old != new in those ranges. The settle delay is varied per
attempt so the RNG does not replay the same outcome from the same state.

Outputs: analysis/callstacks/steal/steal_fail.json (first miss),
steal_ok.json (the hit), steal_NN.json for every other attempt is deleted
unless --keep-all.

The steal item's writer PC (store pc -> containing function) is the
function to decompile next; the roll is in it or its caller.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
OUT_DIR = os.path.join(ROOT, "analysis", "callstacks", "steal")

LOOT = "0x80146320-0x80146360"
INVENTORY = "0x80145040-0x80145470"


def run_capture(a, i, settle):
    label = "steal_%02d" % i
    out = os.path.join(a.out_dir, label + ".json")
    cmd = [sys.executable, os.path.join(TOOLS, "callstack_diff.py"), "capture",
           "--label", label, "--out", out, "--port", str(a.port),
           "--slot", str(a.slot), "--press", "circle",
           "--settle-frames", str(settle), "--window-frames", str(a.window_frames),
           "--lo", a.lo, "--hi", a.hi,
           "--watch", LOOT, "--watch", INVENTORY]
    for w in a.watch or []:
        cmd += ["--watch", w]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("capture %s failed (rc %d)" % (label, r.returncode))
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-4:]
    return out, tail


def judge(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    watch = d.get("watch") or {}
    ranges = watch.get("ranges", [])
    changed = []
    for (lo, hi), b0, b1 in zip(ranges, watch.get("values_at_arm", []), watch.get("values_at_end", [])):
        if b0 != b1:
            a0, a1 = bytes.fromhex(b0), bytes.fromhex(b1)
            cells = [int(lo, 16) + k for k in range(len(a0)) if a0[k] != a1[k]]
            changed.append((lo, hi, cells))
    writes = [w for w in d.get("writes", []) if w["old"] != w["new"]]
    counts = d.get("counts", {})
    return d, changed, writes, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, required=True, help="savestate FILE number (in-game N = file N-1)")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--attempts", type=int, default=40)
    ap.add_argument("--window-frames", type=int, default=900)
    ap.add_argument("--settle-base", type=int, default=30)
    ap.add_argument("--settle-step", type=int, default=7, help="added per attempt to move the RNG")
    ap.add_argument("--lo", default="0x80093800", help="fn_filter low (default: battle engine band)")
    ap.add_argument("--hi", default="0x800B4004")
    ap.add_argument("--watch", action="append", default=None, help="extra write-trace ranges")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--keep-all", action="store_true")
    ap.add_argument("--no-stop", action="store_true",
                    help="run every attempt and count the steals (rate measurement / mod proof)")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    fail_kept = False
    steals = 0
    for i in range(a.attempts):
        settle = a.settle_base + a.settle_step * i
        out, tail = run_capture(a, i, settle)
        d, changed, writes, counts = judge(out)
        n_entries = counts.get("entries", len(d.get("entries", [])))
        print("attempt %02d settle %3d: %s fn entries, %d changing writes, %d changed range(s)"
              % (i, settle, n_entries, len(writes), len(changed)))
        for ln in tail:
            print("    " + ln)
        hit = bool(changed) or bool(writes)
        if hit:
            for lo, hi, cells in changed:
                print("  CHANGED %s-%s: %s" % (lo, hi, ", ".join("0x%08X" % c for c in cells[:16])))
            writers = {}
            for w in writes:
                writers.setdefault((w["writer"], w["pc"]), []).append(w)
            for (wr, pc), wl in sorted(writers.items(), key=lambda kv: -len(kv[1])):
                w0 = wl[0]
                print("  writer %s store pc %s x%d  first: %s %s -> %s ra=%s a0..3=%s"
                      % (wr, pc, len(wl), w0["addr"], w0["old"], w0["new"], w0["ra"],
                         ",".join(x or "?" for x in w0["args"])))
            steals += 1
            final = os.path.join(a.out_dir, "steal_ok.json")
            if os.path.exists(final):
                os.remove(final)
            os.replace(out, final)
            print("STEAL SUCCEEDED on attempt %d -> %s" % (i, final))
            if not a.no_stop:
                print("next: python tools/callstack_diff.py writes %s --changes-only" % final)
                return 0
            continue
        if not fail_kept:
            final = os.path.join(a.out_dir, "steal_fail.json")
            if os.path.exists(final):
                os.remove(final)
            os.replace(out, final)
            fail_kept = True
        elif not a.keep_all:
            os.remove(out)
    print("steals: %d / %d attempts" % (steals, a.attempts))
    return 0 if steals else 1


if __name__ == "__main__":
    sys.exit(main())
