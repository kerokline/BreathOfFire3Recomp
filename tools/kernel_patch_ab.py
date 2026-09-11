"""A/B the kernel install-slot ranges: how much interpreted work do they save?

Boots the runtime headless twice against the SAME binary, to the same frame,
once with the declared [[recompiler.install_slots]] ranges live and once with
PSX_KERNEL_PATCH_RANGES=0, which drops them and restores the whole-body
kernel-bless memcmp — the behaviour before the ranges existed. Reports, per
side: the kernel-bless verdict, total interpreted instructions, and the share
of those that are BIOS kernel RAM (PC < 0x10000).

    python tools/kernel_patch_ab.py                        # OpenBIOS, 1800 frames
    python tools/kernel_patch_ab.py --frames 3600
    python tools/kernel_patch_ab.py --bios psxrecomp/bios/SCPH1001.BIN

Uncapped and headless, so a frame is a unit of guest work, not wall time. The
two sides run the same boot, so the interpreted totals are comparable.
"""
import argparse, json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL_WINDOW_END = 0x10000
# The four 16-byte kernel call vectors. The BIOS profile excludes them on
# purpose (runtime-written trampolines -> dirty-RAM interp, rule 18), so
# they interpret on both sides of this A/B and are reported separately.
VECTOR_STUBS = (0x80, 0xA0, 0xB0, 0xC0)


def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=120.0)


def wait_port(port, secs=180):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            r = q("frame", port)
            if r.get("ok") or "frame" in r:
                return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("debug port never came up")


def run_side(exe, port, frames, bios, ranges_on, timeout, stall):
    env = dict(os.environ, PSX_STARVATION_TIMEOUT_US="0")
    env.pop("PSX_LOAD_SLOT", None)
    if not ranges_on:
        env["PSX_KERNEL_PATCH_RANGES"] = "0"
    else:
        env.pop("PSX_KERNEL_PATCH_RANGES", None)
    argv = [exe, "--game", "game.toml", "--no-launcher", "--headless",
            "--debug-port", str(port)]
    if bios:
        argv += ["--bios", os.path.join(ROOT, bios)]
    proc = subprocess.Popen(argv, cwd=ROOT, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        wait_port(port)
        t0 = time.time()
        # A wedge shows up as a frame counter that stops advancing while the
        # debug server still answers, so watch for STALL as well as the overall
        # timeout — a boot that hangs at frame 0 should not burn the full
        # budget before saying so (it did once, 2026-09-11: a dispatch key
        # inside a declared range spun the dispatch loop).
        last_fr, last_move = -1, time.time()
        while True:
            try:
                fr = q("frame", port).get("frame") or 0
            except Exception:
                fr = last_fr      # transient; the stall check still applies
            if fr >= frames:
                break
            if fr != last_fr:
                last_fr, last_move = fr, time.time()
            elif time.time() - last_move > stall:
                raise SystemExit("WEDGED: frame stuck at %s for %ds "
                                 "(target %d)" % (fr, stall, frames))
            if time.time() - t0 > timeout:
                raise SystemExit("only reached frame %s of %d in %ds"
                                 % (fr, frames, timeout))
            time.sleep(1.0)
        kb = q("kernel_bless", port)
        st = q("dirty_ram_stats", port)
        rows = [r for r in st.get("per_pc", [])
                if int(r["pc"], 16) < KERNEL_WINDOW_END]
        kernel = sum(r["insns"] for r in rows)
        # The A0/B0/C0 call vectors are runtime-written trampolines the BIOS
        # profile excludes on purpose (rule 18), so they interpret on both
        # sides and would mask the change if left in the headline. Split them
        # out: "bodies" is the kernel work the install-slot ranges can move.
        tramp = sum(r["insns"] for r in rows
                    if int(r["pc"], 16) in VECTOR_STUBS)
        top = sorted(rows, key=lambda r: -r["insns"])[:12]
        return {
            "ranges_on": ranges_on,
            "frame": fr,
            "wall_s": round(time.time() - t0, 1),
            "bless_entries": kb.get("entries"),
            "bless_clean": kb.get("clean"),
            "bless_mismatch": kb.get("mismatch"),
            "bless_native_hits": kb.get("native_hits"),
            "patch_ranges": kb.get("patch_ranges"),
            "patch_skips": kb.get("patch_skips"),
            "interp_insns_total": st.get("insns_run"),
            "interp_insns_kernel": kernel,
            "interp_insns_vectors": tramp,
            "interp_insns_kernel_bodies": kernel - tramp,
            "native_handoffs": st.get("native_handoffs"),
            "top_kernel_pcs": [{"pc": r["pc"], "insns": r["insns"],
                                "entries": r["entries"]} for r in top],
        }
    finally:
        proc.kill()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10) + chr(10), 1)[0])
    ap.add_argument("--exe", default="build-relprof/BreathOfFire3_Recompiled.exe")
    ap.add_argument("--frames", type=int, default=1800,
                    help="frame target for both sides (default 1800)")
    ap.add_argument("--bios", default=None,
                    help="BIOS image to launch with (default = the runtime's pick, OpenBIOS)")
    ap.add_argument("--port", type=int, default=4372)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--stall", type=int, default=90,
                    help="fail if the frame counter does not advance for this long")
    ap.add_argument("--out", default="analysis/kernel_patch_ab.json")
    a = ap.parse_args()

    exe = os.path.join(ROOT, a.exe)
    if not os.path.exists(exe):
        raise SystemExit("no exe at " + exe)

    rows = []
    for ranges_on in (False, True):
        label = "ranges ON (declared install slots)" if ranges_on else                 "ranges OFF (PSX_KERNEL_PATCH_RANGES=0, pre-change behaviour)"
        print("=== %s" % label, flush=True)
        r = run_side(exe, a.port, a.frames, a.bios, ranges_on, a.timeout, a.stall)
        rows.append(r)
        print("    frame %(frame)s in %(wall_s)ss  bless: %(bless_clean)s clean / "
              "%(bless_mismatch)s mismatch of %(bless_entries)s  "
              "ranges=%(patch_ranges)s skips=%(patch_skips)s" % r, flush=True)
        print("    interpreted: %(interp_insns_total)s total, "
              "%(interp_insns_kernel)s kernel RAM "
              "(%(interp_insns_kernel_bodies)s bodies + "
              "%(interp_insns_vectors)s A0/B0/C0 vectors)" % r, flush=True)
        for t in r["top_kernel_pcs"][:6]:
            print("      %s insns=%-10s entries=%s"
                  % (t["pc"], t["insns"], t["entries"]), flush=True)

    off, on = rows[0], rows[1]
    print()
    print("frames: OFF %s, ON %s; counts below are PER FRAME, since headless "
          "runs uncapped" % (off["frame"], on["frame"]))
    print("%-30s %14s %14s %9s" % ("", "ranges OFF", "ranges ON", "change"))

    def line(label, key, per_frame=True):
        o, n = off.get(key) or 0, on.get(key) or 0
        if per_frame:
            o = o / float(off["frame"] or 1)
            n = n / float(on["frame"] or 1)
            os_, ns_ = "%.1f" % o, "%.1f" % n
        else:
            os_, ns_ = str(o), str(n)
        ch = ("%+.1f%%" % (100.0 * (n - o) / o)) if o else "n/a"
        print("%-30s %14s %14s %9s" % (label, os_, ns_, ch))

    line("kernel-bless mismatch", "bless_mismatch", False)
    line("kernel-bless clean", "bless_clean", False)
    line("interp insns / frame, bodies", "interp_insns_kernel_bodies")
    line("interp insns / frame, vectors", "interp_insns_vectors")
    line("interp insns / frame, kernel", "interp_insns_kernel")
    line("interp insns / frame, all", "interp_insns_total")

    os.makedirs(os.path.dirname(os.path.join(ROOT, a.out)), exist_ok=True)
    json.dump({"frames": a.frames, "bios": a.bios, "sides": rows},
              open(os.path.join(ROOT, a.out), "w", encoding="utf-8"), indent=1)
    print(chr(10) + "wrote " + a.out)


if __name__ == "__main__":
    main()
