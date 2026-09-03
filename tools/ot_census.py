"""Headless DMA2 ordering-table walk census for one runtime build.

Launches the exe headless, waits for the guest to run, then for each savestate
slot: loads it, settles, and samples `dma_state` for WINDOW seconds. Reports
per-slot deltas of the PR #302 gpu_ot counters (starts/completes/cancels/
starts_dropped, CHCR polls) plus the distribution of sampled walk shapes
(nodes_last/words_last/cycles_last) so the two cost models can be compared.

    python tools/ot_census.py <ABSOLUTE exe path> <port> <window_s> <slot> [<slot> ...]

Needs a runtime carrying the gpu_ot counters from psxrecomp PR #302; see
docs/pr302-dma2-ot-cost-review.md for the 2026-09-03 A/B this was written for.
"""
import json, os, socket, struct, subprocess, sys, time

ROOT = r"C:\Users\kerok\Documents\GitHub\BreathOfFire3Recomp"
exe, port, window = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
slots = [int(s) for s in sys.argv[4:]]


def send(cmd, timeout=15.0):
    s = socket.socket(); s.settimeout(timeout); s.connect(("127.0.0.1", port))
    s.sendall((json.dumps(cmd) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(1 << 20)
        if not chunk: break
        buf += chunk
    s.close()
    return json.loads(buf.split(b"\n", 1)[0].decode(errors="replace"))


def vsync():
    r = send({"cmd": "read_ram", "addr": "0x8018603C", "len": 4})
    return struct.unpack("<I", bytes.fromhex(r["hex"]))[0]


def ot():
    d = send({"cmd": "dma_state"})
    return d["gpu_ot"], d["gpu_ot_chcr"], d.get("gpu_ot_cancels", [])


env = dict(os.environ, PSX_STARVATION_TIMEOUT_US="0"); env.pop("PSX_LOAD_SLOT", None)
proc = subprocess.Popen([exe, "--game", "game.toml", "--no-launcher", "--headless",
                         "--debug-port", str(port)], cwd=ROOT, env=env,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
print(f"launched pid {proc.pid}", flush=True)
try:
    t0 = time.time()
    while True:
        try:
            if send({"cmd": "dma_state"}).get("ok"): break
        except Exception:
            if proc.poll() is not None: sys.exit(f"exe exited early rc={proc.returncode}")
            if time.time() - t0 > 120: sys.exit("debug server never came up")
            time.sleep(1)
    prev, stable = -1, 0
    while stable < 3:
        v = vsync(); stable = stable + 1 if v > prev else 0; prev = v; time.sleep(1)
    print(f"booted after {time.time()-t0:.0f}s, vsync={prev}", flush=True)

    def census(label):
        a_ot, a_ch, _ = ot(); av, at = vsync(), time.time()
        shapes = {}
        deadline = time.time() + window
        while time.time() < deadline:
            time.sleep(0.25)
            o, _, _ = ot()
            k = (o["nodes_last"], o["words_last"], o["cycles_last"])
            shapes[k] = shapes.get(k, 0) + 1
        b_ot, b_ch, ring = ot(); bv, bt = vsync(), time.time()
        d = {k: b_ot[k] - a_ot[k] for k in ("starts", "starts_dropped", "completes", "cancels")}
        d["chcr_reads"] = b_ch["reads_total"] - a_ch["reads_total"]
        d["chcr_reads_in_walk"] = b_ch["reads_in_walk"] - a_ch["reads_in_walk"]
        d["frames"] = bv - av
        d["emu_fps"] = round((bv - av) / (bt - at), 1)
        d["cycles_max_lifetime"] = b_ot["cycles_max"]
        d["cancel_ring_count"] = b_ch["cancel_ring_count"]
        top = sorted(shapes.items(), key=lambda kv: -kv[1])[:6]
        d["walk_shapes_nodes_words_cycles"] = [list(k) + [n] for k, n in top]
        if d["cancels"]: d["cancel_ring"] = ring
        print(f"--- {label}: {json.dumps(d)}", flush=True)
        return d

    results = {"boot": census("boot (wherever the guest is after boot)")}
    for slot in slots:
        send({"cmd": "savestate", "slot": slot, "op": "load"})
        for _ in range(30):
            s = send({"cmd": "savestate_status"})
            if s["pending"] == 0 and s["last_op"] == "load":
                print(f"slot {slot} load last_ok={s['last_ok']}", flush=True); break
            time.sleep(1)
        time.sleep(4)
        results[f"slot{slot:02d}"] = census(f"slot{slot:02d}")
    print("RESULT " + json.dumps(results), flush=True)
finally:
    proc.kill()
