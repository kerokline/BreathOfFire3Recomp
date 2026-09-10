#!/usr/bin/env python
"""Wall-clock speed watcher for a LIVE session -- is the guest running fast?

Polls the debug server and derives, per sample window:

  emu_hz    cycle-paced VBlanks raised per WALL second. The guest's own clock.
            59.94 = realtime. 120 = the game is running at 2x speed.
  present   presents per wall second (present_ring total), i.e. what the eye
            sees.
  turbo     whether the turbo-through-loads pacer is engaged right now
            (`load_active`), and how many turbo frames it burned in the window.

Every sample is appended to a JSONL; a row is printed whenever the speed leaves
the realtime band or turbo changes state, so a long session prints only the
interesting moments.

    python tools/fps_watch.py [--port 4370] [--interval 0.25] [--out FILE] [--all]
"""
import argparse
import json
import socket
import sys
import time

NTSC_HZ = 59.94


def q(cmd, port, **kw):
    s = socket.socket()
    s.settimeout(5.0)
    s.connect(("127.0.0.1", port))
    d = {"cmd": cmd}
    d.update(kw)
    s.sendall((json.dumps(d) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(1 << 20)
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf.split(b"\n", 1)[0].decode())


def sample(port):
    vr = q("vblank_rate", port)
    tl = q("turbo_loads", port)
    pr = q("present_ring", port, n=1)
    return {
        "t": time.time(),
        "raise": vr["cycle_paced_raise"],
        "deliver": vr["delivered"],
        "present": pr["total"],
        "load_active": tl["load_active"],
        "turbo_frames": tl["turbo_frames"],
        "turbo_enabled": tl["enabled"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--out", default="analysis/fps_watch.jsonl")
    ap.add_argument("--all", action="store_true",
                    help="print every sample, not just the interesting ones")
    a = ap.parse_args()

    fh = open(a.out, "a", encoding="utf-8")
    prev = sample(a.port)
    print("watching -- emu_hz 59.94 = realtime. Ctrl-C to stop.", flush=True)
    try:
        while True:
            time.sleep(a.interval)
            try:
                cur = sample(a.port)
            except (socket.error, ValueError) as e:
                print("lost server: %s" % e, flush=True)
                break
            dt = cur["t"] - prev["t"]
            if dt <= 0:
                continue
            row = {
                "t": round(cur["t"], 3),
                "emu_hz": round((cur["raise"] - prev["raise"]) / dt, 2),
                "present_hz": round((cur["present"] - prev["present"]) / dt, 2),
                "deliver_hz": round((cur["deliver"] - prev["deliver"]) / dt, 2),
                "turbo_fps": round((cur["turbo_frames"] - prev["turbo_frames"]) / dt, 2),
                "load": cur["load_active"],
                "frame": cur["raise"],
            }
            row["speed"] = round(row["emu_hz"] / NTSC_HZ, 3)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            interesting = (row["speed"] > 1.08 or row["speed"] < 0.92
                           or row["turbo_fps"] > 0
                           or cur["load_active"] != prev["load_active"])
            if a.all or interesting:
                print("f%-8d speed %.2fx  emu %6.1f Hz  present %5.1f Hz  "
                      "turbo %5.1f f/s  load %d"
                      % (row["frame"], row["speed"], row["emu_hz"],
                         row["present_hz"], row["turbo_fps"], row["load"]),
                      flush=True)
            prev = cur
    except KeyboardInterrupt:
        pass
    fh.close()


if __name__ == "__main__":
    main()
