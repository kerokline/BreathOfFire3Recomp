#!/usr/bin/env python
"""Headless scene harness -- turn a savestate into a re-interrogable offline asset.

Every other debug tool in `tools/` attaches to a game someone is already
playing (`callstack_diff.py`, `area_poller.py`, `verify_msgtable.py`, the
harvest loop). That made each scene-specific question cost another live play
session. This launches the runtime headless, lands it on a savestate, *proves
the scene is actually running*, and hands the live debug port to whatever you
want to ask -- so one capture answers questions forever.

    # offline, no boot: can these states load against this build at all?
    python tools/scene.py preflight

    # boot + load + verify every slot (the savestate-wedge regression test)
    python tools/scene.py check

    # land on the Nu boss fight and hold the port open for manual poking
    python tools/scene.py run --slot 2

    # land on the battle-menu scene, press Circle, screenshot, exit
    python tools/scene.py run --slot 3 --press circle --shot attack.png

    # land on a scene and hand the port to an existing tool
    python tools/scene.py run --slot 3 -- \
        python tools/callstack_diff.py capture --label attack --port {port} \
            --press circle

`{port}` in the trailing command is substituted with the port this harness
actually used; `PSX_SCENE_PORT` is exported for tools that read the env.

## The wedge guard

`savestate load` acknowledges as soon as the request is *staged*, and
`savestate_status` reports `last_ok: 1` once `savestate_poll` restored the
sections -- neither says the guest resumed. On 2026-09-05 a Debug tree loaded
with `last_ok: 1` and then sat in a BIOS `B0` call loop with the VSync counter
frozen (docs/STATUS.md, Known issues). So every load here is followed by
`verify_running()`: sample the game's own VSync counter across two windows and
require it to advance. A wedge is reported as a wedge instead of silently
poisoning whatever measurement runs next.

Verified 2026-09-06 on `build-relprof`: slots 0-7 and 9-11 all load and resume
headless. Slot 8 is refused at the header (format v5, pre-v7) -- `preflight`
names that offline, before spending a 13 s boot on it.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import zlib
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps
from callstack_diff import BUTTONS, button_mask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TREE = "build-relprof"          # Release+tools; Release has no debug server
DEFAULT_PORT = 4390                     # away from 4370, the live-play port
CUE = "isos/Breath of Fire III (Japan).cue"
SAVES = os.path.join(ROOT, "saves", "openbios")
STATE_GLOB = "state_%08X_slot%02d.pst"

# BoF3's own VSync counter -- guest progress, not frontend progress. A frozen
# frontend still answers `frame`; a wedged guest does not move this word.
VSYNC_ADDR = 0x8018603C

BOOT_STATE_MAGIC = 0x50535842           # 'BXSP'
HDR = "<9I"                             # magic ver bios entry codegen abi cgver secs rsvd
BS_SEC_CPU = 0x01


# ---------------------------------------------------------------- build stamps

def build_expectations():
    """What the current source tree will demand of a .pst header.

    Read from the headers the runtime itself compiles against, so preflight
    cannot drift from `boot_state_load`'s integrity gate.
    """
    inc = os.path.join(ROOT, "psxrecomp", "runtime", "include")

    def grab(fname, macro, base=0):
        path = os.path.join(inc, fname)
        try:
            for line in open(path, encoding="utf-8", errors="replace"):
                if line.startswith("#define " + macro):
                    tok = line.split(macro, 1)[1].strip().rstrip("u").rstrip()
                    return int(tok, base)
        except OSError:
            pass
        return None

    return {
        "version": grab("boot_state.h", "BOOT_STATE_VERSION"),
        "version_min": grab("boot_state.h", "BOOT_STATE_VERSION_MIN_READ"),
        "codegen_hash": grab("overlay_codegen_hash.h", "PSX_OVERLAY_CODEGEN_HASH", 16),
        "codegen_ver": grab("overlay_api.h", "PSX_OVERLAY_CODEGEN_VER"),
    }


def entry_pc():
    """Game entry PC -- names the savestate files. Parsed from game.toml."""
    try:
        for line in open(os.path.join(ROOT, "game.toml"), encoding="utf-8"):
            if line.strip().startswith("entry_pc"):
                return int(line.split("=", 1)[1].strip().strip('"'), 16)
    except OSError:
        pass
    return 0x8014AA0C


def slot_path(slot):
    return os.path.join(SAVES, STATE_GLOB % (entry_pc(), slot))


def read_header(slot):
    """Header + resume PC for one slot, or None when the file is absent."""
    path = slot_path(slot)
    try:
        blob = open(path, "rb").read()
    except OSError:
        return None
    if len(blob) < 36:
        return {"path": path, "error": "truncated (%d bytes)" % len(blob)}
    h = struct.unpack(HDR, blob[:36])
    out = dict(zip(("magic", "version", "bios_checksum", "entry_pc",
                    "codegen_hash", "abi_tag", "codegen_ver", "section_count"), h))
    out["path"] = path
    out["bytes"] = len(blob)
    out["mtime"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    # Resume PC lives in the CPU section; walk the stream far enough to find it.
    # Payloads carry BOOT_STATE_SEC_ZLIB (pad bit0) = u32 raw_len + deflate.
    off = 36
    for _ in range(min(out["section_count"], 64)):
        if off + 16 > len(blob):
            break
        tag, flags, ln = struct.unpack("<IIQ", blob[off:off + 16])
        off += 16
        if tag == BS_SEC_CPU:
            pay = blob[off:off + ln]
            if flags & 1:
                try:
                    pay = zlib.decompress(pay[4:])
                except zlib.error:
                    pay = b""
            if len(pay) >= 132:
                out["pc"] = struct.unpack("<I", pay[128:132])[0]
            break
        off += ln
    return out


def preflight_reasons(hdr, exp):
    """The subset of boot_state_load's rejects that is knowable offline."""
    bad = []
    if hdr.get("error"):
        return [hdr["error"]]
    if hdr["magic"] != BOOT_STATE_MAGIC:
        bad.append("magic=%08X" % hdr["magic"])
    if exp["version"] and not (exp["version_min"] <= hdr["version"] <= exp["version"]):
        bad.append("version=%d(want %d..%d)"
                   % (hdr["version"], exp["version_min"], exp["version"]))
    if hdr["entry_pc"] != entry_pc():
        bad.append("entry=%08X(want %08X)" % (hdr["entry_pc"], entry_pc()))
    if exp["codegen_hash"] and hdr["codegen_hash"] != exp["codegen_hash"]:
        bad.append("codegen_hash=%08X(want %08X)"
                   % (hdr["codegen_hash"], exp["codegen_hash"]))
    if exp["codegen_ver"] and hdr["codegen_ver"] != exp["codegen_ver"]:
        bad.append("codegen_ver=%d(want %d)" % (hdr["codegen_ver"], exp["codegen_ver"]))
    return bad


# ------------------------------------------------------------------ the runtime

class Scene:
    """A booted headless runtime, optionally parked on a savestate."""

    def __init__(self, tree=DEFAULT_TREE, port=DEFAULT_PORT, disc=True,
                 log=None, verbose=True):
        self.tree, self.port, self.verbose = tree, port, verbose
        self.exe = os.path.join(ROOT, tree, "BreathOfFire3_Recompiled.exe")
        self.disc = disc
        self.log_path = log
        self.proc = None
        self._log = None

    # -- plumbing ------------------------------------------------------------
    def q(self, cmd, **kw):
        return ps.send(dict(cmd=cmd, **kw), port=self.port, timeout=20.0)

    def vsync(self):
        r = self.q("read_ram", addr=hex(VSYNC_ADDR), len=4)
        return struct.unpack("<I", bytes.fromhex(r["hex"]))[0]

    def say(self, msg):
        if self.verbose:
            print(msg, flush=True)

    # -- lifecycle -----------------------------------------------------------
    def launch(self, boot_timeout=240):
        if not os.path.exists(self.exe):
            raise SystemExit("no exe at %s -- build the tree first" % self.exe)
        argv = [self.exe, "--game", "game.toml", "--no-launcher", "--headless",
                "--debug-port", str(self.port)]
        if self.disc:
            argv += ["--disc", CUE]
        # The starvation watchdog exits(2) on a 4 s emu-thread stall; a
        # savestate restore is legitimately longer than that.
        env = dict(os.environ, PSX_STARVATION_TIMEOUT_US="0")
        env.pop("PSX_LOAD_SLOT", None)   # we load over TCP, not at boot
        out = subprocess.DEVNULL
        if self.log_path:
            self._log = open(self.log_path, "wb")
            out = self._log
        self.proc = subprocess.Popen(
            argv, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        t0 = time.time()
        while True:
            try:
                if self.q("dma_state").get("ok"):
                    break
            except Exception:
                if self.proc.poll() is not None:
                    raise SystemExit("runtime exited rc=%s before listening%s"
                                     % (self.proc.returncode,
                                        " (see %s)" % self.log_path if self.log_path else ""))
                if time.time() - t0 > boot_timeout:
                    raise SystemExit("debug server never came up on port %d" % self.port)
                time.sleep(1)
        # Wait for the guest to actually be running frames, not just listening.
        prev, stable, tries = -1, 0, 0
        while stable < 3 and tries < boot_timeout:
            v = self.vsync()
            stable = stable + 1 if v > prev else 0
            prev, tries = v, tries + 1
            time.sleep(1)
        if stable < 3:
            raise SystemExit("booted but never ran frames (vsync stuck at %d)" % prev)
        self.say("  booted in %.0fs on port %d (vsync=%d)"
                 % (time.time() - t0, self.port, prev))
        return prev

    def quit(self):
        """Graceful shutdown. `quit` lets the runtime flush its own savestate
        diagnostics; killing the process buffers them into oblivion."""
        if self.proc is None:
            return
        try:
            self.q("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=15)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        if self._log:
            self._log.close()
            self._log = None
        self.proc = None

    # -- the scene ------------------------------------------------------------
    def load(self, slot, timeout=45):
        """Stage a load and wait for savestate_poll to report on it.

        Returns the savestate_status dict. `last_ok: 1` means the sections
        restored -- it does NOT mean the guest resumed; call verify_running().
        """
        self.q("savestate", slot=slot, op="load")
        st = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.q("savestate_status")
            if st.get("pending") == 0 and st.get("last_op") == "load":
                return st
            time.sleep(0.5)
        return st or {}

    def verify_running(self, window=2.0, samples=3):
        """Prove the guest is executing after a restore -- the wedge guard.

        A wedged restore reports `last_ok: 1` and then freezes: VSync stops,
        `static_hits` stops, and the guest spins in a BIOS call loop. Sample
        the guest's own frame counter across `samples` windows; every window
        must advance.
        """
        seen = [self.vsync()]
        for _ in range(samples):
            time.sleep(window)
            seen.append(self.vsync())
        ok = all(b > a for a, b in zip(seen, seen[1:]))
        info = {"ok": ok, "vsync": seen,
                "fps": round((seen[-1] - seen[0]) / (window * samples), 1)}
        if not ok:
            # Capture why, while it is still frozen -- this is the evidence the
            # 2026-09-05 wedge report had to be assembled by hand.
            for cmd in ("get_registers", "irq_state", "overlay_loader_status"):
                try:
                    info[cmd] = self.q(cmd)
                except Exception as e:
                    info[cmd] = "ERR %s" % type(e).__name__
        return info

    def wait_frames(self, n):
        target = self.vsync() + n
        deadline = time.time() + max(10.0, n / 30.0 + 5.0)
        while time.time() < deadline and self.vsync() < target:
            time.sleep(0.05)

    def press(self, presses, hold=None, frames=4, gap=12):
        """Inject a press SEQUENCE, `hold` down throughout (see callstack_diff)."""
        hold_mask = 0
        for h in hold or []:
            hold_mask |= button_mask(h)
        if hold_mask:
            self.q("set_input", buttons="0x%04X" % (0xFFFF & ~hold_mask))
            self.wait_frames(gap)
        for i, item in enumerate(presses):
            if i:
                self.wait_frames(gap)
            word = 0xFFFF & ~(button_mask(item) | hold_mask)
            if hold_mask:
                self.q("set_input", buttons="0x%04X" % word)
                self.wait_frames(frames)
                self.q("set_input", buttons="0x%04X" % (0xFFFF & ~hold_mask))
            else:
                self.q("press", buttons=word, frames=int(frames))
        if hold_mask:
            self.wait_frames(gap)
            self.q("clear_input")

    def enter(self, slot, settle=2.0):
        """launch + load + verify. Raises with the diagnostics on a wedge."""
        self.launch()
        st = self.load(slot)
        if st.get("last_ok") != 1:
            hdr = read_header(slot)
            why = ", ".join(preflight_reasons(hdr, build_expectations())) if hdr else "no file"
            raise SystemExit("slot %d refused by the runtime (%s); status=%s"
                             % (slot, why or "reason not exposed over TCP", st))
        time.sleep(settle)
        run = self.verify_running()
        if not run["ok"]:
            raise SystemExit("slot %d WEDGED after load -- vsync %s did not advance.\n%s"
                             % (slot, run["vsync"], json.dumps(run, indent=2)))
        self.say("  slot %d live at %.0f emulated fps (vsync %d)"
                 % (slot, run["fps"], run["vsync"][-1]))
        return run


# --------------------------------------------------------------------- commands

def parse_slots(spec):
    if spec in (None, "", "all"):
        return list(range(12))
    out = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            out += list(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def cmd_preflight(a):
    exp = build_expectations()
    print("build wants: version %s..%s  codegen_hash %08X  codegen_ver %s  entry %08X"
          % (exp["version_min"], exp["version"], exp["codegen_hash"] or 0,
             exp["codegen_ver"], entry_pc()))
    print("%-5s %-16s %-9s %-4s %-10s %-10s %s"
          % ("slot", "written", "bytes", "ver", "codegen", "pc", "verdict"))
    bad = 0
    for slot in parse_slots(a.slots):
        hdr = read_header(slot)
        if hdr is None:
            print("%-5d %s" % (slot, "-- no file --"))
            continue
        reasons = preflight_reasons(hdr, exp)
        if reasons:
            bad += 1
        print("%-5d %-16s %-9d %-4s %-10s %-10s %s"
              % (slot, hdr.get("mtime", "?"), hdr.get("bytes", 0),
                 hdr.get("version", "?"),
                 "%08X" % hdr.get("codegen_hash", 0),
                 "%08X" % hdr.get("pc", 0),
                 "STALE: " + ", ".join(reasons) if reasons else "loadable"))
    if bad:
        print("\n%d slot(s) cannot load against this build -- re-save them "
              "(docs/SAVESTATES.md: states are cheap to recreate)." % bad)
    return 1 if bad and a.strict else 0


def cmd_check(a):
    """The savestate-wedge regression test: does every state still resume?"""
    exp = build_expectations()
    results = []
    for slot in parse_slots(a.slots):
        hdr = read_header(slot)
        if hdr is None:
            results.append({"slot": slot, "verdict": "missing"})
            print("slot %-2d missing" % slot)
            continue
        reasons = preflight_reasons(hdr, exp)
        if reasons and not a.force:
            results.append({"slot": slot, "verdict": "stale", "why": reasons})
            print("slot %-2d STALE (%s) -- skipped, no boot spent" % (slot, ", ".join(reasons)))
            continue
        log = os.path.join(a.logdir, "scene_slot%02d.log" % slot) if a.logdir else None
        sc = Scene(a.tree, a.port + slot, log=log)
        print("slot %-2d ..." % slot, flush=True)
        try:
            run = sc.enter(slot)
            results.append({"slot": slot, "verdict": "ok", "fps": run["fps"],
                            "vsync": run["vsync"]})
            print("slot %-2d OK  %.0f emulated fps" % (slot, run["fps"]))
        except SystemExit as e:
            results.append({"slot": slot, "verdict": "FAIL", "why": str(e)})
            print("slot %-2d FAIL %s" % (slot, str(e).splitlines()[0]))
        finally:
            sc.quit()
    ok = sum(1 for r in results if r["verdict"] == "ok")
    fail = [r for r in results if r["verdict"] == "FAIL"]
    print("\n%d/%d slots load and resume headless%s"
          % (ok, len(results), "" if not fail else
             "; FAILED: " + ", ".join(str(r["slot"]) for r in fail)))
    if a.json:
        json.dump(results, open(a.json, "w"), indent=2)
        print("wrote", a.json)
    return 1 if fail else 0


def cmd_run(a):
    log = a.log or None
    sc = Scene(a.tree, a.port, disc=not a.no_disc, log=log)
    rc = 0
    try:
        sc.enter(a.slot)
        if a.press or a.hold:
            sc.press(a.press or [], hold=a.hold, frames=a.press_frames, gap=a.press_gap)
            sc.wait_frames(a.settle_frames)
            run = sc.verify_running(window=1.0, samples=2)
            if not run["ok"]:
                raise SystemExit("guest stopped advancing after the input sequence:\n%s"
                                 % json.dumps(run, indent=2))
        if a.shot:
            shot = a.shot if os.path.isabs(a.shot) else os.path.join(os.getcwd(), a.shot)
            # The ack means "queued": the PNG lands on a later present, so poll
            # for the file rather than reporting a write that never happened.
            before = os.path.getmtime(shot) if os.path.exists(shot) else 0
            reply = sc.q("screenshot", path=shot)
            deadline = time.time() + 10.0
            while time.time() < deadline:
                if os.path.exists(shot) and os.path.getmtime(shot) > before:
                    break
                time.sleep(0.25)
            else:
                raise SystemExit("screenshot never appeared at %s (server said %s)"
                                 % (shot, reply))
            print("wrote", shot)
        if a.cmd:
            argv = [x.replace("{port}", str(a.port)) for x in a.cmd]
            env = dict(os.environ, PSX_SCENE_PORT=str(a.port))
            print("+ " + " ".join(argv), flush=True)
            rc = subprocess.call(argv, cwd=ROOT, env=env)
        elif a.seconds:
            time.sleep(a.seconds)
        else:
            print("\nscene is live on port %d -- attach with e.g.\n"
                  "    python tools/playsession.py status --port %d\n"
                  "Ctrl-C here to shut it down." % (a.port, a.port), flush=True)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                print()
    finally:
        sc.quit()
    return rc


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="sub", required=True)

    p = sub.add_parser("preflight", help="offline .pst header check against this build")
    p.add_argument("--slots", default="all", help='e.g. "0-3,7" (default all)')
    p.add_argument("--strict", action="store_true", help="exit 1 if any slot is stale")
    p.set_defaults(fn=cmd_preflight)

    p = sub.add_parser("check", help="boot+load+resume every slot (wedge regression test)")
    p.add_argument("--slots", default="all")
    p.add_argument("--tree", default=DEFAULT_TREE)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--force", action="store_true", help="boot even for stale headers")
    p.add_argument("--logdir", default=None, help="keep each runtime's stdout here")
    p.add_argument("--json", default=None)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("run", help="land on a scene and hand the port to a command")
    p.add_argument("--slot", type=int, required=True, help="savestate FILE number")
    p.add_argument("--tree", default=DEFAULT_TREE)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-disc", action="store_true", help="boot without the CD image")
    p.add_argument("--press", action="append", default=[],
                   help="one press; repeat for a SEQUENCE; 'a+b' holds together (%s)"
                        % ", ".join(BUTTONS))
    p.add_argument("--hold", action="append", default=[],
                   help="held down for the whole sequence (BoF3 menus are hold-direction)")
    p.add_argument("--press-frames", type=int, default=4)
    p.add_argument("--press-gap", type=int, default=12)
    p.add_argument("--settle-frames", type=int, default=60,
                   help="frames to let the scene settle after the input sequence")
    p.add_argument("--shot", default=None, help="screenshot PNG once the scene is up")
    p.add_argument("--seconds", type=float, default=None,
                   help="hold the scene this long, then quit (default: until Ctrl-C)")
    p.add_argument("--log", default=None, help="keep the runtime's stdout here")
    p.add_argument("cmd", nargs=argparse.REMAINDER,
                   help="after --, a command to run against the live port ({port})")
    p.set_defaults(fn=cmd_run)

    a = ap.parse_args()
    if getattr(a, "cmd", None) and a.cmd and a.cmd[0] == "--":
        a.cmd = a.cmd[1:]
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
