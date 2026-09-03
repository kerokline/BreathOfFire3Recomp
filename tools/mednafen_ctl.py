#!/usr/bin/env python
"""Drive the Mednafen oracle in ./mednafen from the command line.

Mednafen (the parent of Beetle PSX) has no scripting interface: `-remote` is a
bare flag in 1.32 and the only control surface is its own hotkeys. This tool
launches it with command-line setting overrides, then injects keystrokes into
its window using the scancodes it reads from `mednafen/mednafen.cfg`, so the
bindings never drift from what the emulator actually listens for.

Memory cards are the exchange format with psx-runtime (raw 128 KiB, identical
bytes): `launch --card saves/card1.mcd` copies our card to the name Mednafen
expects and boots from it. Savestates are NOT interchangeable.

    python tools/mednafen_ctl.py launch [--card [saves/card1.mcd]] [--fs] [--set k=v ...]
    python tools/mednafen_ctl.py press start cross ...  [--hold 0.12] [--gap 0.25] [--chord]
    python tools/mednafen_ctl.py hold up --hold 2.0
    python tools/mednafen_ctl.py key save_state | load_state | pause | exit ...
    python tools/mednafen_ctl.py state save N | load N
    python tools/mednafen_ctl.py snap [--out file.png]
    python tools/mednafen_ctl.py frame N            (frame-advance N frames; leaves emu paused)
    python tools/mednafen_ctl.py card export        (Mednafen card -> saves/card1.mcd, with backup)
    python tools/mednafen_ctl.py status | log [--tail N] | quit

Every command except launch/status/log/quit refuses to inject unless the
Mednafen window is the foreground window (it focuses it first), so keys never
land in another app.
"""
import argparse
import ctypes
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MDFN_DIR = os.path.join(ROOT, "mednafen")
MDFN_EXE = os.path.join(MDFN_DIR, "mednafen.exe")
MDFN_CFG = os.path.join(MDFN_DIR, "mednafen.cfg")
STATE_FILE = os.path.join(MDFN_DIR, ".ctl.json")
DEFAULT_DISC = os.path.join(ROOT, "isos", "Breath of Fire III (Japan).cue")
DEFAULT_CARD = os.path.join(ROOT, "saves", "card1.mcd")

# ---------------------------------------------------------------- scancodes
# SDL2 scancode -> (Windows set-1 scancode, extended). SDL on Windows keys off
# the hardware scancode in WM_KEYDOWN, so injecting scancodes reproduces
# exactly what the cfg binds.
_SDL_TO_WIN = {}
for _i, _sc in enumerate([0x1E, 0x30, 0x2E, 0x20, 0x12, 0x21, 0x22, 0x23, 0x17, 0x24,
                          0x25, 0x26, 0x32, 0x31, 0x18, 0x19, 0x10, 0x13, 0x1F, 0x14,
                          0x16, 0x2F, 0x11, 0x2D, 0x15, 0x2C]):
    _SDL_TO_WIN[4 + _i] = (_sc, False)                     # a..z
for _i in range(9):
    _SDL_TO_WIN[30 + _i] = (0x02 + _i, False)              # 1..9
_SDL_TO_WIN[39] = (0x0B, False)                            # 0
_SDL_TO_WIN.update({
    40: (0x1C, False), 41: (0x01, False), 42: (0x0E, False), 43: (0x0F, False),
    44: (0x39, False), 45: (0x0C, False), 46: (0x0D, False), 47: (0x1A, False),
    48: (0x1B, False), 49: (0x2B, False), 51: (0x27, False), 52: (0x28, False),
    53: (0x29, False), 54: (0x33, False), 55: (0x34, False), 56: (0x35, False),
    57: (0x3A, False),
    70: (0x37, True), 71: (0x46, False), 72: (0x45, False),          # prtsc, scroll, pause
    73: (0x52, True), 74: (0x47, True), 75: (0x49, True), 76: (0x53, True),
    77: (0x4F, True), 78: (0x51, True),
    79: (0x4D, True), 80: (0x4B, True), 81: (0x50, True), 82: (0x48, True),  # arrows
    83: (0x45, True), 84: (0x35, True), 85: (0x37, False), 86: (0x4A, False),
    87: (0x4E, False), 88: (0x1C, True),
    89: (0x4F, False), 90: (0x50, False), 91: (0x51, False), 92: (0x4B, False),
    93: (0x4C, False), 94: (0x4D, False), 95: (0x47, False), 96: (0x48, False),
    97: (0x49, False), 98: (0x52, False), 99: (0x53, False),
    224: (0x1D, False), 225: (0x2A, False), 226: (0x38, False), 227: (0x5B, True),
    228: (0x1D, True), 229: (0x36, False), 230: (0x38, True), 231: (0x5C, True),
})
for _i in range(10):
    _SDL_TO_WIN[58 + _i] = (0x3B + _i, False)              # F1..F10
_SDL_TO_WIN[68] = (0x57, False)
_SDL_TO_WIN[69] = (0x58, False)
_MOD_SDL = {"shift": 225, "ctrl": 224, "alt": 226}
_SDL_NAMES = {}
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _SDL_NAMES[4 + _i] = _ch
for _i in range(9):
    _SDL_NAMES[30 + _i] = str(_i + 1)
_SDL_NAMES[39] = "0"
_SDL_NAMES.update({40: "Return", 41: "Esc", 42: "Backspace", 43: "Tab", 44: "Space",
                   45: "-", 46: "=", 53: "`", 72: "Pause", 79: "Right", 80: "Left",
                   81: "Down", 82: "Up", 95: "KP7", 97: "KP9", 224: "LCtrl",
                   225: "LShift", 226: "LAlt"})
for _i in range(12):
    _SDL_NAMES[58 + _i] = "F%d" % (_i + 1)

PAD_BUTTONS = ["up", "down", "left", "right", "cross", "circle", "square", "triangle",
               "start", "select", "l1", "l2", "r1", "r2"]


def read_bindings():
    """Return {name: [(sdl_scancode, [mods])]} for pad buttons and command.* hotkeys."""
    binds = {}
    rx = re.compile(r"^(psx\.input\.port1\.gamepad\.(\w+)|command\.(\w+))\s+(.*)$")
    with open(MDFN_CFG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.match(line.rstrip("\r\n"))
            if not m:
                continue
            name = m.group(2) or m.group(3)
            spec = m.group(4).split()
            combos = []
            i = 0
            while i + 2 < len(spec):
                if spec[i] == "keyboard":
                    code, *mods = spec[i + 2].split("+")
                    combos.append((int(code), mods))
                    i += 3
                else:
                    i += 1
            if combos:
                binds[name] = combos
    return binds


# ---------------------------------------------------------------- SendInput
_user32 = ctypes.WinDLL("user32", use_last_error=True)
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


def _send(sdl_code, up):
    if sdl_code not in _SDL_TO_WIN:
        sys.exit("no Windows scancode for SDL scancode %d" % sdl_code)
    scan, ext = _SDL_TO_WIN[sdl_code]
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT(type=1)
    inp.u.ki = KEYBDINPUT(0, scan, flags, 0, 0)
    if _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def key_down(codes):
    for c in codes:
        _send(c, False)


def key_up(codes):
    for c in reversed(codes):
        _send(c, True)


def tap(codes, hold):
    key_down(codes)
    time.sleep(hold)
    key_up(codes)


def combo_codes(combo):
    code, mods = combo
    return [_MOD_SDL[m] for m in mods] + [code]


def combo_name(combo):
    code, mods = combo
    return "+".join(mods + [_SDL_NAMES.get(code, "sc%d" % code)])


# ---------------------------------------------------------------- window
def _load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(d):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f)


def _pid_alive(pid):
    import win32api
    import win32con
    import win32process
    try:
        h = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
    except Exception:
        return False
    try:
        return win32process.GetExitCodeProcess(h) == 259  # STILL_ACTIVE
    finally:
        win32api.CloseHandle(h)


def find_window(pid):
    import win32gui
    import win32process
    found = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        if wpid == pid and win32gui.GetWindowText(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def running():
    st = _load_state()
    pid = st.get("pid")
    if not pid or not _pid_alive(pid):
        return None, None
    return pid, find_window(pid)


def require_focus():
    import win32gui
    import win32process
    pid, hwnd = running()
    if not pid:
        sys.exit("mednafen is not running (use `launch`)")
    if not hwnd:
        sys.exit("mednafen pid %d has no visible window yet" % pid)
    for _ in range(3):
        try:
            # An ALT tap releases the foreground lock so SetForegroundWindow
            # works from a console process.
            _send(226, False)
            _send(226, True)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.15)
        fg = win32gui.GetForegroundWindow()
        _, fpid = win32process.GetWindowThreadProcessId(fg)
        if fpid == pid:
            return hwnd
    sys.exit("could not bring the mednafen window to the foreground; refusing to inject keys")


# ---------------------------------------------------------------- game files
def disc_base(disc):
    return os.path.splitext(os.path.basename(disc))[0]


def sav_dir():
    with open(MDFN_CFG, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("filesys.path_sav "):
                p = line.split(None, 1)[1].strip()
                return p if os.path.isabs(p) else os.path.join(MDFN_DIR, p)
    return os.path.join(MDFN_DIR, "sav")


def game_hash(disc):
    """Mednafen's %m: the per-game MD5 it derives from the disc. Learned from
    files it has already written rather than recomputed."""
    base = disc_base(disc)
    cands = glob.glob(os.path.join(sav_dir(), base + ".*.0.mcr")) + \
        glob.glob(os.path.join(MDFN_DIR, "b", base + ".*"))
    for c in cands:
        m = re.search(re.escape(base) + r"\.([0-9a-f]{32})", os.path.basename(c))
        if m:
            return m.group(1)
    return None


def mednafen_card_paths(disc, slot=0):
    """Both names Mednafen may resolve for a card: plain (%M empty, tried
    first) and hash-qualified. Plain wins when it exists."""
    base = disc_base(disc)
    d = sav_dir()
    paths = [os.path.join(d, "%s.%d.mcr" % (base, slot))]
    h = game_hash(disc)
    if h:
        paths.append(os.path.join(d, "%s.%s.%d.mcr" % (base, h, slot)))
    return paths


def is_card(path):
    try:
        with open(path, "rb") as f:
            head = f.read(2)
        return os.path.getsize(path) == 131072 and head == b"MC"
    except OSError:
        return False


# ---------------------------------------------------------------- commands
def cmd_launch(a):
    pid, _ = running()
    if pid:
        sys.exit("mednafen already running (pid %d); `quit` it first" % pid)
    if not os.path.isfile(a.disc):
        sys.exit("disc not found: %s" % a.disc)
    if a.card:
        if not is_card(a.card):
            sys.exit("not a raw 128 KiB memcard image: %s" % a.card)
        for dst in mednafen_card_paths(a.disc, 0):
            shutil.copyfile(a.card, dst)
            print("card: %s -> %s" % (a.card, os.path.relpath(dst, ROOT)))
    args = [MDFN_EXE, "-video.fs", "1" if a.fs else "0"]
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        args += ["-" + k, v]
    args.append(a.disc)
    # Portable mode: without MEDNAFEN_HOME the base directory is ~/.mednafen
    # and the BIOS in mednafen/firmware is never found (Mednaffe sets this).
    env = dict(os.environ, MEDNAFEN_HOME=MDFN_DIR)
    p = subprocess.Popen(args, cwd=MDFN_DIR, stdin=subprocess.DEVNULL, env=env,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    _save_state({"pid": p.pid, "disc": a.disc, "card": a.card, "started": time.time()})
    hwnd = None
    for _ in range(int(a.timeout * 10)):
        time.sleep(0.1)
        if p.poll() is not None:
            sys.exit("mednafen exited early (code %s); see mednafen/stdout.txt" % p.returncode)
        hwnd = find_window(p.pid)
        if hwnd:
            break
    print("pid %d window %s" % (p.pid, hex(hwnd) if hwnd else "(none yet)"))


def _press_combos(combos, hold, gap, chord=False):
    if chord:
        codes = []
        for c in combos:
            codes += combo_codes(c)
        tap(codes, hold)
    else:
        for i, c in enumerate(combos):
            tap(combo_codes(c), hold)
            if i + 1 < len(combos):
                time.sleep(gap)


def cmd_press(a):
    b = read_bindings()
    combos = []
    for name in a.buttons:
        if name not in b:
            sys.exit("no binding for %r (known: %s)" % (name, ", ".join(sorted(b))))
        combos.append(b[name][0])
    require_focus()
    chord = getattr(a, "chord", False)
    _press_combos(combos, a.hold, a.gap, chord=chord)
    sep = "+" if chord else ", "
    print("pressed " + sep.join("%s(%s)" % (n, combo_name(c)) for n, c in zip(a.buttons, combos)))


def cmd_state(a):
    b = read_bindings()
    slot = b.get(str(a.slot))
    act = b.get("save_state" if a.op == "save" else "load_state")
    if not slot or not act:
        sys.exit("cfg lacks slot/state bindings")
    require_focus()
    tap(combo_codes(slot[0]), a.hold)
    time.sleep(0.3)
    tap(combo_codes(act[0]), a.hold)
    print("%s state slot %d" % (a.op, a.slot))


def cmd_snap(a):
    b = read_bindings()
    snapdir = os.path.join(MDFN_DIR, "snaps")
    before = set(glob.glob(os.path.join(snapdir, "*.png")))
    require_focus()
    tap(combo_codes(b["take_snapshot"][0]), a.hold)
    new = None
    for _ in range(50):
        time.sleep(0.1)
        cur = set(glob.glob(os.path.join(snapdir, "*.png"))) - before
        if cur:
            new = max(cur, key=os.path.getmtime)
            time.sleep(0.2)  # let the write finish
            break
    if not new:
        sys.exit("no snapshot appeared in %s" % snapdir)
    if a.out:
        shutil.copyfile(new, a.out)
        print(a.out)
    else:
        print(new)


def cmd_frame(a):
    b = read_bindings()
    require_focus()
    for _ in range(a.n):
        tap(combo_codes(b["advance_frame"][0]), a.hold)
        time.sleep(a.gap)
    print("advanced %d frame(s); emulator is paused (key pause to resume)" % a.n)


def cmd_card(a):
    st = _load_state()
    disc = st.get("disc") or a.disc
    srcs = [p for p in mednafen_card_paths(disc, 0) if os.path.isfile(p)]
    if not srcs:
        sys.exit("no Mednafen card for this disc in %s" % sav_dir())
    src = max(srcs, key=os.path.getmtime)
    if running()[0]:
        print("warning: mednafen is running; it rewrites the card on exit")
    if not is_card(src):
        sys.exit("%s is not a valid card image" % src)
    if os.path.isfile(a.dest):
        bak = a.dest + ".bak-%s" % time.strftime("%Y%m%d-%H%M%S")
        shutil.copyfile(a.dest, bak)
        print("backup: %s" % os.path.relpath(bak, ROOT))
    shutil.copyfile(src, a.dest)
    print("%s -> %s" % (os.path.relpath(src, ROOT), os.path.relpath(a.dest, ROOT)))


def cmd_status(a):
    pid, hwnd = running()
    st = _load_state()
    if not pid:
        print("not running")
        return
    import win32gui
    print("pid %d  window %s  title %r" % (pid, hex(hwnd) if hwnd else None,
                                           win32gui.GetWindowText(hwnd) if hwnd else None))
    print("disc  %s" % st.get("disc"))
    print("card  %s" % st.get("card"))
    print("up    %.0fs" % (time.time() - st.get("started", time.time())))


def cmd_log(a):
    for name in ("stdout.txt", "stderr.txt"):
        p = os.path.join(MDFN_DIR, name)
        if os.path.isfile(p) and os.path.getsize(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            print("== %s (last %d of %d)" % (name, min(a.tail, len(lines)), len(lines)))
            print("\n".join(lines[-a.tail:]))


def cmd_quit(a):
    pid, hwnd = running()
    if not pid:
        print("not running")
        return
    import win32con
    import win32gui
    if hwnd:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    for _ in range(100):
        time.sleep(0.1)
        if not _pid_alive(pid):
            print("exited")
            _save_state({})
            return
    subprocess.call(["taskkill", "/F", "/PID", str(pid)])
    _save_state({})
    print("killed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("launch")
    s.add_argument("--disc", default=DEFAULT_DISC)
    s.add_argument("--card", nargs="?", const=DEFAULT_CARD, default=None,
                   help="memcard image to boot from (bare flag = saves/card1.mcd)")
    s.add_argument("--fs", action="store_true", help="fullscreen")
    s.add_argument("--set", action="append", metavar="KEY=VAL", help="mednafen setting override")
    s.add_argument("--timeout", type=float, default=30)
    s.set_defaults(fn=cmd_launch)

    for name, fn in (("press", cmd_press), ("key", cmd_press)):
        s = sub.add_parser(name)
        s.add_argument("buttons", nargs="+")
        s.add_argument("--hold", type=float, default=0.12)
        s.add_argument("--gap", type=float, default=0.25)
        s.add_argument("--chord", action="store_true", help="press all together")
        s.set_defaults(fn=fn)

    s = sub.add_parser("hold")
    s.add_argument("buttons", nargs="+")
    s.add_argument("--hold", type=float, default=1.0)
    s.add_argument("--gap", type=float, default=0)
    s.set_defaults(fn=cmd_press, chord=True)

    s = sub.add_parser("state")
    s.add_argument("op", choices=["save", "load"])
    s.add_argument("slot", type=int, choices=range(10))
    s.add_argument("--hold", type=float, default=0.12)
    s.set_defaults(fn=cmd_state)

    s = sub.add_parser("snap")
    s.add_argument("--out")
    s.add_argument("--hold", type=float, default=0.12)
    s.set_defaults(fn=cmd_snap)

    s = sub.add_parser("frame")
    s.add_argument("n", type=int, nargs="?", default=1)
    s.add_argument("--hold", type=float, default=0.05)
    s.add_argument("--gap", type=float, default=0.05)
    s.set_defaults(fn=cmd_frame)

    s = sub.add_parser("card")
    s.add_argument("op", choices=["export"])
    s.add_argument("--dest", default=DEFAULT_CARD)
    s.add_argument("--disc", default=DEFAULT_DISC)
    s.set_defaults(fn=cmd_card)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("log")
    s.add_argument("--tail", type=int, default=40)
    s.set_defaults(fn=cmd_log)
    s = sub.add_parser("quit")
    s.set_defaults(fn=cmd_quit)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
