#!/usr/bin/env python
"""Capcom-FMV benchmark: boot, catch the FMV live, measure it.

The Capcom gold-cubes FMV is the first screen after boot, and a clean boot is
the ONLY valid repro: the mid-FMV savestates (slot06 etc.) resume *past* the
FMV, so a held state silently measures a light free-run screen instead
(2026-09-01 finding — see docs/vblank-pacing-bug.md).

What it does:
  1. launches the given runtime headless (PSX_STARVATION_TIMEOUT_US=0),
  2. waits for the debug port, then for MDEC activity (mdec_state.trace_total),
  3. delta-measures vblank raises/s + present/s + interp counters + the
     bioscall B0 route over a window inside the FMV,
  4. optionally gdb-samples the emu thread's host stacks (--gdb N) — the tool
     that actually found the spu_get_global_state hotspot.

Usage:
  python tools/fmv_bench.py                          # build-dbg, port 4370
  python tools/fmv_bench.py --exe build-relprof/BreathOfFire3_Recompiled.exe
  python tools/fmv_bench.py --window 4 --gdb 25
  python tools/fmv_bench.py --no-launch              # attach to a running boot

Interpretation: a healthy FMV reads ~59.9 vblank raises/s. 28-29 was the
pre-fix CPU-bound rate. Post-FMV free-run is uncapped headless (>60 is normal).
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

GDB = r"C:\msys64\mingw64\bin\gdb.exe"


def send(cmd, port, timeout=25.0):
    s = socket.socket()
    s.settimeout(timeout)
    s.connect(("127.0.0.1", port))
    s.sendall((json.dumps(cmd) + "\n").encode())
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = s.recv(1 << 20)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        if b"\n" in buf:
            break
    s.close()
    return json.loads(buf.split(b"\n", 1)[0].decode(errors="replace"))


def wait_port(port, budget=60.0):
    t0 = time.time()
    while time.time() - t0 < budget:
        try:
            send({"cmd": "ping"}, port, timeout=3.0)
            return time.time() - t0
        except Exception:
            time.sleep(0.5)
    sys.exit(f"debug port {port} never came up (is the exe a PSX_DEBUG_TOOLS build?)")


def wait_fmv(port, budget=90.0):
    t0 = time.time()
    while time.time() - t0 < budget:
        try:
            m = send({"cmd": "mdec_state"}, port, timeout=5.0)
            if m.get("trace_total", 0) > 0:
                return time.time() - t0
        except Exception:
            pass
        time.sleep(0.3)
    sys.exit("no MDEC activity within budget — FMV missed (already played?) "
             "or boot stalled. Re-run; this tool must observe a fresh boot.")


def snap(port):
    return {
        "t": time.time(),
        "bios": send({"cmd": "bioscall_dump"}, port),
        "dirty": send({"cmd": "dirty_ram_stats"}, port),
        "vb": send({"cmd": "vblank_rate"}, port),
        "frame": send({"cmd": "frame"}, port),
        "mdec": send({"cmd": "mdec_state"}, port),
    }


def gdb_sample(pid, n, outpath):
    """N one-shot attaches, backtracing thread 1 (the emu thread)."""
    with open(outpath, "w") as f:
        for i in range(n):
            f.write(f"=== SAMPLE {i + 1} ===\n")
            f.flush()
            subprocess.run(
                [GDB, "-batch", "-p", str(pid),
                 "-ex", "set pagination off",
                 "-ex", "thread apply 1 bt 12"],
                stdout=f, stderr=subprocess.STDOUT)
    # frame-0 histogram
    import re
    hist = {}
    for line in open(outpath, errors="replace"):
        m = re.match(r"#0\s+(?:0x[0-9a-f]+ in )?([A-Za-z_][A-Za-z0-9_]*)", line)
        if m:
            hist[m.group(1)] = hist.get(m.group(1), 0) + 1
    return sorted(hist.items(), key=lambda kv: -kv[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="build-dbg/BreathOfFire3_Recompiled.exe")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--window", type=float, default=4.0,
                    help="measurement window inside the FMV, seconds")
    ap.add_argument("--gdb", type=int, default=0, metavar="N",
                    help="also take N gdb stack samples of the emu thread")
    ap.add_argument("--no-launch", action="store_true",
                    help="attach to an already-booting process instead")
    ap.add_argument("--keep", action="store_true",
                    help="leave the launched process running on exit "
                         "(default kills it — a lingering exe locks the "
                         "linker's output file on the next build)")
    args = ap.parse_args()

    proc = None
    if not args.no_launch:
        exe = os.path.abspath(args.exe)
        if not os.path.exists(exe):
            sys.exit(f"not found: {exe}")
        env = dict(os.environ, PSX_STARVATION_TIMEOUT_US="0")
        env.pop("PSX_LOAD_SLOT", None)  # savestates invalidate the repro
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.Popen(
            [exe, "--game", "game.toml", "--no-launcher", "--headless",
             "--debug-port", str(args.port)],
            cwd=repo_root,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(f"launched {exe} (pid {proc.pid})")

    dt_port = wait_port(args.port)
    print(f"port up after {dt_port:.1f}s")
    dt_fmv = wait_fmv(args.port)
    print(f"FMV active at t+{dt_fmv:.1f}s — measuring {args.window:.0f}s window")

    if args.gdb and not proc:
        sys.exit("--gdb needs the tool to own the launch (drop --no-launch)")

    # Rate window first, unperturbed — gdb attaches PAUSE the process and
    # would corrupt the vblank/s reading if interleaved.
    a = snap(args.port)
    time.sleep(args.window)
    b = snap(args.port)
    dt = b["t"] - a["t"]

    gdb_hist = None
    if args.gdb:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "analysis", "fmv_gdb_samples.txt")
        out = os.path.abspath(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        gdb_hist = gdb_sample(proc.pid, args.gdb, out)
        m = send({"cmd": "mdec_state"}, args.port)
        tail = "" if m["trace_total"] > b["mdec"]["trace_total"] else \
               "  (WARNING: FMV ended during sampling — histogram tail is post-FMV)"
        print(f"gdb samples -> {out}{tail}")

    vb = (b["vb"]["cycle_paced_raise"] - a["vb"]["cycle_paced_raise"]) / dt
    fr = (b["frame"]["frame"] - a["frame"]["frame"]) / dt
    mdec_alive = b["mdec"]["trace_total"] > a["mdec"]["trace_total"]
    print(f"\n=== FMV window ({dt:.2f}s"
          f"{', mdec advancing' if mdec_alive else ', MDEC WENT IDLE — window overlapped FMV end, rerun'}) ===")
    print(f"vblank raises/s : {vb:6.1f}   (healthy ~59.9; pre-fix bound ~28)")
    print(f"present/s       : {fr:6.1f}")

    di = (b["dirty"]["insns_run"] - a["dirty"]["insns_run"]) / dt
    db = (b["dirty"]["blocks_run"] - a["dirty"]["blocks_run"]) / dt
    print(f"interp          : {di:,.0f} insns/s in {db:,.0f} blocks/s")

    ma = {(e["table"], e["index"]): e["count"] for e in a["bios"].get("counts", [])}
    mb = {(e["table"], e["index"]): e["count"] for e in b["bios"].get("counts", [])}
    rows = sorted(((mb[k] - ma.get(k, 0)) / dt, k) for k in mb if mb[k] - ma.get(k, 0))
    print("BIOS vector calls/s:")
    for r, (tab, idx) in rows[::-1][:8]:
        print(f"  {tab}:{idx:<4} {r:8.1f}/s")

    if gdb_hist is not None:
        print("\nemu-thread frame-0 histogram (gdb samples):")
        for name, n in gdb_hist[:15]:
            print(f"  {n:3d}  {name}")

    if proc and not args.keep:
        proc.kill()
        print("\n(launched process killed; --keep to leave it running)")


if __name__ == "__main__":
    main()
