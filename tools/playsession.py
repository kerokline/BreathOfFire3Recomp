#!/usr/bin/env python
"""Drive a BreathOfFire3_Recompiled debug session while you play.

Talks to the runtime's TCP debug server (build-dbg only -- a Release build has
PSX_DEBUG_TOOLS=OFF and no server at all).

    python tools/playsession.py arm      # watch writes into the text buffer
    python tools/playsession.py status   # is it alive, what frame, what's armed
    python tools/playsession.py shot out.png
    python tools/playsession.py dump text_writes.json
    python tools/playsession.py raw gpu_state

`arm` watches the script buffer at 0x80010000 -- every area's dialogue block is
loaded there (see docs/LOCALIZATION.md section 4), so the trace records which
code writes it. Ranges are stored as physical addresses; `status` echoes what
the server actually kept, so a wrong mask is visible rather than assumed.
"""
import argparse
import json
import socket
import sys
import time

HOST = "127.0.0.1"
PORT = 4370

# The .EMI section whose destination is 0x80010000 holds the area's script.
# The largest such section observed is a few KB; 16 KB covers every area.
TEXT_LO = 0x80010000
TEXT_HI = 0x80014000


def send(cmd, port=None, timeout=20.0):
    # Resolved at call time, not bound as a default -- otherwise --port is
    # captured at import and silently ignored.
    s = socket.socket()
    s.settimeout(timeout)
    s.connect((HOST, PORT if port is None else port))
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
    line = buf.split(b"\n", 1)[0].decode(errors="replace")
    if not line:
        raise SystemExit("empty reply from debug server")
    try:
        return json.loads(line)
    except ValueError:
        return {"raw": line}


def need_ok(r, what):
    if not r.get("ok", False):
        raise SystemExit("%s failed: %s" % (what, r.get("error", r)))
    return r


def cmd_arm(args):
    need_ok(send({"cmd": "wtrace_add",
                  "lo": "0x%08X" % TEXT_LO, "hi": "0x%08X" % TEXT_HI}),
            "wtrace_add")
    # wtrace_arm may not exist as a separate step on every build; ignore refusal.
    r = send({"cmd": "wtrace_arm"})
    if not r.get("ok", False) and "unknown command" not in str(r.get("error", "")):
        print("note: wtrace_arm said %r" % r.get("error"), file=sys.stderr)
    ranges = send({"cmd": "wtrace_ranges"})
    print("armed. ranges the server actually kept:")
    print(json.dumps(ranges, indent=2))
    print("\nNow play. Enter a few areas with dialogue, then:")
    print("  python tools/playsession.py dump text_writes.json")
    return 0


def cmd_status(args):
    for c in ("ping", "frame", "wtrace_ranges", "wtrace_stats", "gpu_state"):
        r = send({"cmd": c})
        if c == "gpu_state" and r.get("ok"):
            keep = {k: r.get(k) for k in
                    ("width", "height", "display_y", "disabled", "gp0_draw")}
            print("%-14s %s" % (c, json.dumps(keep)))
        else:
            print("%-14s %s" % (c, json.dumps(r)[:400]))
    return 0


def cmd_dump(args):
    r = need_ok(send({"cmd": "wtrace_dump", "count": args.count}, timeout=60.0),
                "wtrace_dump")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=2)
    entries = r.get("entries", r.get("writes", []))
    print("wrote %s (%d entries)" % (args.out, len(entries) if
                                     isinstance(entries, list) else -1))
    if isinstance(entries, list) and entries:
        pcs = {}
        for e in entries:
            pc = e.get("pc") or e.get("func_addr")
            pcs[pc] = pcs.get(pc, 0) + 1
        print("distinct writing PCs: %d" % len(pcs))
        for pc, n in sorted(pcs.items(), key=lambda kv: -kv[1])[:15]:
            print("   %s  %d writes" % (pc, n))
    return 0


def cmd_shot(args):
    r = need_ok(send({"cmd": "screenshot_file", "path": args.out}, timeout=60.0),
                "screenshot_file")
    print("wrote %s (%sx%s) next to the exe"
          % (r.get("path"), r.get("width"), r.get("height")))
    return 0


def cmd_state(args):
    """Save/load a runtime savestate slot.

    Files land in saves/openbios/state_<entrypc>_slotNN.pst next to a .thumb.
    Verified working on the LLE backend (save and load both restore RAM).
    """
    r = send({"cmd": "savestate", "slot": args.slot, "op": args.op}, timeout=60.0)
    if not r.get("ok", False):
        raise SystemExit("savestate %s slot %d refused: %s"
                         % (args.op, args.slot, r.get("error", r)))
    time.sleep(2.0)   # the op is staged; let the emulator thread apply it
    st = send({"cmd": "savestate_status"})
    print("%s slot %d -> %s" % (args.op, args.slot, json.dumps(st)))
    if st.get("last_ok") != 1:
        print("warning: last_ok != 1, the operation may not have completed",
              file=sys.stderr)
    return 0


def cmd_raw(args):
    body = {"cmd": args.name}
    for kv in args.kv:
        k, _, v = kv.partition("=")
        body[k] = int(v, 0) if v.lstrip("-").isdigit() or v.startswith("0x") else v
    print(json.dumps(send(body, timeout=60.0), indent=2)[:8000])
    return 0


def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("arm").set_defaults(fn=cmd_arm)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("dump"); p.add_argument("out", nargs="?", default="text_writes.json")
    p.add_argument("--count", type=int, default=65536); p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("shot"); p.add_argument("out", nargs="?", default="shot.png")
    p.set_defaults(fn=cmd_shot)
    p = sub.add_parser("state"); p.add_argument("op", choices=("save", "load"))
    p.add_argument("slot", type=int); p.set_defaults(fn=cmd_state)
    p = sub.add_parser("raw"); p.add_argument("name"); p.add_argument("kv", nargs="*")
    p.set_defaults(fn=cmd_raw)
    args = ap.parse_args()

    PORT = args.port
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
