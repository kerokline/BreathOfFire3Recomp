#!/usr/bin/env python
"""Differential call-stack tracer for BoF3 (docs/IDEAS.md I1, NAME_MAP route 3).

Records the runtime's function entry/exit rings around one injected input,
rebuilds the call forest, and diffs two such captures so that "the Attack
path" is a set difference and "Battle_Init" is a common prefix.

    # one capture per input, from the same savestate anchor (FILE number)
    python tools/callstack_diff.py capture --label attack --slot 1 --press circle \
        --lo 0x801D0C00 --hi 0x801F0000 --settle-frames 30 --window-frames 60 \
        --out analysis/callstacks/attack.json
    python tools/callstack_diff.py capture --label defend --slot 1 --press down --press circle ...
    # repeated --press flags are a SEQUENCE (down, then circle, --press-gap frames apart);
    # "a+b" inside one flag holds two buttons together
    python tools/callstack_diff.py tree analysis/callstacks/attack.json --max-depth 6
    python tools/callstack_diff.py diff analysis/callstacks/attack.json analysis/callstacks/defend.json --prefix
    python tools/callstack_diff.py venn analysis/callstacks/{attack,defend,watch}.json   # 3-way membership
    python tools/callstack_diff.py propose analysis/callstacks/*.json            # dry
    python tools/callstack_diff.py propose analysis/callstacks/*.json --apply    # -> names/functions.toml

    # read-only smoke test against a running game: no savestate, no input,
    # no filter change -- drains whatever the rings hold right now
    python tools/callstack_diff.py capture --label probe --dry-run --out /tmp/probe.json

    # DATA ANCHORS (NAME_MAP route 4). Step 1: find the RAM cell without a RAM
    # map -- snapshot RAM, do the thing, snapshot again, keep the 16-bit cells
    # that moved by exactly the number on screen (damage 37 -> --delta -37):
    python tools/callstack_diff.py ramdiff --slot 10 --press circle --press circle --press circle \
        --window-frames 600 --label atk1     # prompts for the damage numbers once the round is over
    python tools/callstack_diff.py ramfilter analysis/ramdiff/atk1.json --delta 37,41,12   # re-query later
    python tools/callstack_diff.py ramfilter analysis/ramdiff/atk3.json --delta 29,38,11 \
        --intersect analysis/ramdiff/atk1.json=37,41,12 --intersect analysis/ramdiff/atk2.json=33,40,15
    # Step 2: arm the runtime's write trace on that cell during a capture; every
    # write is attributed to the compiled function containing the store PC:
    python tools/callstack_diff.py capture --label attack --slot 10 --press circle ... \
        --watch 0x8010A3C4 --watch 0x8010A400-0x8010A480 --out analysis/callstacks/attack_w.json
    python tools/callstack_diff.py writes analysis/callstacks/attack_w.json --changes-only
    # Step 3: name the writer (second route for a hypothesis -> evidence):
    python tools/callstack_diff.py name 0x801DFB18 Battle_ApplyDamage --args target,amount \
        --status evidence --evidence "wtrace: only writer of party HP under Attack (attack_w.json)" --apply

Capture sequence (non dry-run): fn_stats (remember the previous filter) ->
savestate load + poll savestate_status until pending==0 -> wait
--settle-frames -> fn_clear -> fn_filter lo/hi (arms the trace) -> press ->
wait --window-frames -> fn_disable -> fn_stats -> overlay_native_ring +
resident script-block md5 -> page fn_entry_dump / fn_exit_dump -> restore the
previous filter (and fn_disable if it was inactive) -> write JSON.

Traps, all paid for (read the debug server for the exact shapes:
psxrecomp/runtime/src/debug_server.c, handlers near handle_fn_filter):

* fn_filter compares the address it is handed RAW against the stamped
  address, and the two stamp paths use different forms: the direct entry
  stamp at the top of every compiled function passes KSEG0 (0x80xxxxxx);
  the psx_dispatch path passes physical. Since every compiled function
  stamps on entry, a KSEG0 range catches everything and is the default;
  a physical range catches only dispatched (cross-unit) calls and recorded
  0 entries over 146 battle frames (2026-09-04). --phys-filter selects it.
  `func` comes back in whichever form stamped it; `ra` is the raw $ra.
  Both are stored raw and normalised to 0x80xxxxxx.
* fn_filter ACTIVATES the trace as a side effect; fn_disable is the only off
  switch. fn_clear resets both rings and the shadow stack but not the filter.
* fn_entry_dump / fn_exit_dump cap `count` at 2048 and default the window to
  the last 1M seqs; seq_lo/seq_hi are strtoull(base 0) strings, so page by
  decimal seq. fn_entry_dump does NOT skip overwritten slots (only
  fn_entry_tail checks e->seq == s), so the client re-checks `seq`.
* `exit_seq` 0 on an entry means "still open" -- but the first real exit is
  also seq 0. Exits are joined through exit.entry_seq, never through
  entry.exit_seq alone.
* `depth` is the shadow-stack top AFTER the push, so a top-level entry has
  depth 1. The shadow stack tracks every dispatch, filtered or not; an entry
  whose depth jumps by more than one from its parent sits below frames the
  filter dropped or the interpreter ran (analysis/observed_interp_pcs.json
  lists the holes). The forest records that as `gap`.
* Tail calls: the runtime replaces the top frame in place and records an
  exit for the old func + an entry for the new one at the same depth with
  the same ra. They are flagged, counted, and kept as siblings.
* Ring capacity is 262 144 entries -- under a second of a hot battle loop
  without a filter. Keep the filter tight and the window short.
* 0x801D0C00 is a mixed band. A func address names a slot, not an occupant;
  the resident script-block md5 and the native-ring body CRCs are stored in
  the capture and `propose` refuses to write a name whose overlay is
  ambiguous unless --overlay is given.
* savestate `slot` is the FILE number (in-game N writes slotN-1; see
  docs/SAVESTATES.md). A TCP load on a windowed run needs the starvation
  watchdog off (PSX_STARVATION_TIMEOUT_US=0, persisted on this machine).
* The shadow stack can saturate: a live session showed stack_top 4096 with
  67k overflows and 1.8M tail calls while the trace was armed on a 4-byte
  window (every out-of-filter dispatch still pushes). fn_clear resets it,
  which is why capture clears right before arming; if a capture's depths
  climb monotonically the stack leaked during the window -- shorten it.
* `press` takes the PS1 pad word (1 = released) as an integer and
  auto-releases after `frames` (default 2); set_input holds until
  clear_input. Plain presses use `press`; a `--hold` sequence is driven
  with set_input/clear_input because the battle command menu is a
  hold-direction menu (Right = Defend, Left = Watch, release = Attack).
* The native ring can be empty at capture time and the resident image's
  data tail is modified at runtime, so an exact md5 never identifies the
  band occupant; `resident_overlays()` stores the longest RAM-prefix match
  against the captured section bytes instead (>= 4 KB to count).
* Write trace (`--watch`): wtrace_arm takes physical-masked lo/hi and there
  are boot-default ranges already armed (~15 of 64 slots); capture records
  them (wtrace_ranges), disarms all, resets the ring, arms ours, and puts
  the old set back afterwards. wtrace_dump has NO seq paging -- it walks
  oldest-first and caps at 2048 rows -- so the drain pages by frame window
  (frame_lo/frame_hi, inclusive) and bisects any window that fills a page;
  a single frame with > 2048 writes is reported as truncated. The entry's
  `func` is g_debug_current_func_addr, which only the dispatch path
  maintains (stale for direct calls); `pc` is g_debug_last_store_pc, which
  every compiled store sets exactly, so writers are attributed by pc ->
  containing function start (overlay starts + analysis/functions.tsv for
  the boot EXE), never by `func`.
* names/functions.toml rows are `[[function]]` (the file's header); an older
  revision of this tool wrote `[[func]]`. Both are read; writes use the
  table name the file already has.
"""
import argparse
import glob
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "analysis")
NAMES_DIR = os.path.join(ROOT, "names")
FUNCTIONS_TOML = os.path.join(NAMES_DIR, "functions.toml")
OVERLAYS_TOML = os.path.join(NAMES_DIR, "overlays.toml")
CAPTURES_JSON = os.path.join(AN, "overlay_captures_all.json")
EMI_SECTIONS_JSON = os.path.join(AN, "emi_sections.json")

HOST = "127.0.0.1"
PORT = 4370
SCRIPT_DEST = 0x80010000
PAGE = 2048

# Standard PSX digital pad bits (pad word: bit clear = pressed).
BUTTONS = {
    "select": 0x0001, "start": 0x0008,
    "up": 0x0010, "right": 0x0020, "down": 0x0040, "left": 0x0080,
    "l2": 0x0100, "r2": 0x0200, "l1": 0x0400, "r1": 0x0800,
    "triangle": 0x1000, "circle": 0x2000, "cross": 0x4000, "square": 0x8000,
}

SCHEMA = "callstack-diff-v1"
FUNCTIONS_TSV = os.path.join(AN, "functions.tsv")   # boot-EXE function starts (psxrecomp-analyze)
RAM_LO, RAM_HI = 0x80000000, 0x80200000
WTRACE_MAX_RANGES = 64


# ---------------------------------------------------------------- transport

def send(cmd, port=None, timeout=30.0):
    """One JSON request -> one JSON reply line (same as tools/playsession.py)."""
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
        raise SystemExit("empty reply from debug server (%s)" % cmd.get("cmd"))
    try:
        return json.loads(line)
    except ValueError:
        return {"raw": line}


def q(port, cmd, **kw):
    r = send(dict(cmd=cmd, **kw), port=port)
    if not r.get("ok", False):
        raise SystemExit("%s failed: %s" % (cmd, r.get("error", r)))
    return r


# ---------------------------------------------------------------- addresses

def phys(a):
    return int(a) & 0x1FFFFFFF


def kseg0(a):
    """Normalise a RAM address to 0x80xxxxxx for display; leave BIOS/MMIO alone."""
    a = int(a)
    p = a & 0x1FFFFFFF
    if p < 0x00800000:
        return 0x80000000 | p
    return a


def hx(a):
    return "0x%08X" % int(a)


def parse_int(s):
    return int(str(s), 0)


# ---------------------------------------------------------------- inventories

def crc_index():
    """crc32 (int) -> {source_file, load_addr, size, source_md5} from the captures."""
    if not os.path.exists(CAPTURES_JSON):
        return {}
    out = {}
    for c in json.load(open(CAPTURES_JSON, encoding="utf-8")):
        out[int(c["crc32"], 16)] = {
            "source_file": c["source_file"], "load_addr": c["load_addr"],
            "size": c["size"], "source_md5": c["source_md5"]}
    return out


def overlay_ranges():
    """[(lo, hi, md5, source_file)] for every captured overlay body (KSEG0)."""
    if not os.path.exists(CAPTURES_JSON):
        return []
    out = []
    for c in json.load(open(CAPTURES_JSON, encoding="utf-8")):
        lo = parse_int(c["load_addr"])
        out.append((lo, lo + int(c["size"]), c["source_md5"], c["source_file"]))
    return out


def script_sections():
    """size -> [(md5, file, index)] for every 0x80010000 section on the disc."""
    if not os.path.exists(EMI_SECTIONS_JSON):
        return {}
    secs = json.load(open(EMI_SECTIONS_JSON, encoding="utf-8"))["sections"]
    by_size = {}
    for s in secs:
        if s["dest"] == SCRIPT_DEST:
            by_size.setdefault(s["size"], []).append((s["md5"], s["file"], s["index"]))
    return by_size


def resident_area(port, by_size):
    """{file, index, md5, size} of the script block at 0x80010000, or None."""
    if not by_size:
        return None
    max_size = max(by_size)
    r = q(port, "read_ram", addr=hx(SCRIPT_DEST), len=max_size)
    ram = bytes.fromhex(r["hex"]) if r.get("hex") else b""
    if len(ram) < max_size:
        return None
    for size in sorted(by_size):
        h = hashlib.md5(ram[:size]).hexdigest()
        for md5, f, i in by_size[size]:
            if md5 == h:
                return {"file": f, "index": i, "md5": md5, "size": size}
    return None


def native_ring_summary(port, crcs):
    """overlay_native_ring compressed to one row per body CRC. The server
    nests the ring under `ring`; `recent` is newest-first per native CALL."""
    r = q(port, "overlay_native_ring")
    ring = r.get("ring", {}) if isinstance(r, dict) else {}
    recent = ring.get("recent", []) if isinstance(ring, dict) else []
    per = {}
    for e in recent:
        crc = e.get("crc")
        d = per.setdefault(crc, {"calls": 0, "addrs": set(), "first_frame": None,
                                 "last_frame": None})
        d["calls"] += 1
        d["addrs"].add(e.get("addr"))
        fr = int(e.get("frame", 0))
        d["first_frame"] = fr if d["first_frame"] is None else min(d["first_frame"], fr)
        d["last_frame"] = fr if d["last_frame"] is None else max(d["last_frame"], fr)
    bodies = {}
    for crc, d in per.items():
        src = crcs.get(int(crc, 16)) if crc else None
        bodies[crc] = {"calls": d["calls"], "addrs": sorted(d["addrs"]),
                       "first_frame": d["first_frame"], "last_frame": d["last_frame"],
                       "source_file": src["source_file"] if src else None,
                       "load_addr": src["load_addr"] if src else None,
                       "source_md5": src["source_md5"] if src else None}
    return {"native_exec": ring.get("native_exec"), "calls_total": ring.get("calls_total"),
            "in_progress": ring.get("in_progress"), "recent_count": len(recent),
            "bodies": bodies}


# ---------------------------------------------------------------- live helpers

def cur_frame(port):
    return int(q(port, "frame")["frame"])


def wait_frames(port, n, timeout=120.0):
    """Block until the frame counter has advanced by n (polls; never sleeps
    longer than a frame so a paused game is noticed by the timeout)."""
    start = cur_frame(port)
    target = start + n
    deadline = time.time() + timeout
    f = start
    while f < target:
        if time.time() > deadline:
            raise SystemExit("frame counter stuck at %d (wanted %d)" % (f, target))
        time.sleep(max(0.004, min(0.05, (target - f) / 60.0)))
        f = cur_frame(port)
    return start, f


def load_state(port, slot, timeout=60.0):
    st0 = q(port, "savestate_status")
    gen0 = int(st0.get("generation", 0))
    q(port, "savestate", op="load", slot=int(slot))
    deadline = time.time() + timeout
    while True:
        st = q(port, "savestate_status")
        if int(st.get("pending", 0)) == 0 and int(st.get("generation", 0)) != gen0:
            break
        if time.time() > deadline:
            raise SystemExit("savestate load of file slot %d never completed: %s" % (slot, st))
        time.sleep(0.05)
    if int(st.get("last_ok", 0)) != 1 or st.get("last_op") != "load":
        raise SystemExit("savestate load of file slot %d failed: %s" % (slot, st))
    return st


def button_mask(spec):
    mask = 0
    for n in spec.split("+"):
        key = n.strip().lower()
        if key not in BUTTONS:
            raise SystemExit("unknown button %r (known: %s)" % (n, ", ".join(BUTTONS)))
        mask |= BUTTONS[key]
    return mask


def press_buttons(port, presses, frames, gap, hold=None):
    """Inject `presses` IN SEQUENCE: each element is one press, e.g. "down"
    then "circle"; buttons joined with "+" inside one element ("select+r1")
    are held together. `gap` frames elapse between consecutive presses so
    the game sees them as separate taps. `hold` (a list of button specs) is
    kept DOWN for the whole sequence -- BoF3's battle command menu is a
    hold-direction menu (Defend is selected only while Right is held; release
    and the cursor snaps back to Attack, 2026-09-04). With a hold the server's
    one-shot `press` cannot be used (it replaces the single override word and
    auto-releases everything), so the sequence is driven with set_input /
    clear_input instead. Returns the pad words sent."""
    hold_mask = 0
    for h in hold or []:
        hold_mask |= button_mask(h)
    words = []
    if hold_mask:
        q(port, "set_input", buttons=hx(0xFFFF & ~hold_mask))
        wait_frames(port, int(gap))          # let the menu register the hold
    for i, item in enumerate(presses):
        mask = button_mask(item) | hold_mask
        if i:
            wait_frames(port, int(gap))
        word = 0xFFFF & ~mask
        if hold_mask:
            q(port, "set_input", buttons=hx(word))
            wait_frames(port, int(frames))
            q(port, "set_input", buttons=hx(0xFFFF & ~hold_mask))
        else:
            q(port, "press", buttons=word, frames=int(frames))
        words.append(hx(word))
    if hold_mask:
        wait_frames(port, int(gap))
        q(port, "clear_input")
    return words


def page_ring(port, cmd, seq_lo, seq_hi, addr_lo=None, addr_hi=None):
    """Drain [seq_lo, seq_hi) of fn_entry_dump / fn_exit_dump in 2048-row pages.
    Rows whose `seq` is not the slot we asked for were overwritten (the entry
    dump does not check); they are dropped and counted."""
    rows, dropped = [], 0
    s = seq_lo
    t0 = time.time()
    pages = 0
    while s < seq_hi:
        pages += 1
        if pages % 16 == 0:
            print("  draining %s: %d / %d entries (%.0fs)" % (cmd, len(rows), seq_hi - seq_lo, time.time() - t0), flush=True)
        kw = dict(seq_lo=str(s), seq_hi=str(seq_hi), count=PAGE)
        if addr_lo is not None:
            kw["addr_lo"] = hx(addr_lo)
            kw["addr_hi"] = hx(addr_hi)
        r = q(port, cmd, **kw)
        ents = r.get("entries", [])
        if not ents:
            break
        for e in ents:
            if int(e["seq"]) < s:
                dropped += 1
                continue
            rows.append(e)
        last = int(ents[-1]["seq"])
        if last < s:
            break
        s = last + 1
        if r.get("emitted", 0) < PAGE and s >= seq_hi:
            break
    return rows, dropped


# ---------------------------------------------------------------- normalise + forest

def normalise_entries(raw_entries, raw_exits):
    """Server rows -> flat entry list with both raw and 0x80-normalised
    addresses, exits joined by exit.entry_seq."""
    exits_by_entry = {}
    for x in raw_exits:
        exits_by_entry[int(x["entry_seq"])] = x
    out = []
    for e in raw_entries:
        seq = int(e["seq"])
        func_raw = parse_int(e["func"])
        ra_raw = parse_int(e["ra"])
        x = exits_by_entry.get(seq)
        out.append({
            "seq": seq,
            "func": hx(kseg0(func_raw)), "func_raw": hx(func_raw),
            "ra": hx(kseg0(ra_raw)), "ra_raw": hx(ra_raw),
            "args": [e.get("a0"), e.get("a1"), e.get("a2"), e.get("a3")],
            "t1": e.get("t1"),
            "s": [e.get("s0"), e.get("s1"), e.get("s2"), e.get("s3")],
            "depth": int(e.get("depth", 0)),
            "frame": int(e.get("frame", 0)),
            "exit_seq_field": int(e.get("exit_seq", 0)),
            "exit": ({"seq": int(x["seq"]), "v0": x.get("v0"), "v1": x.get("v1"),
                      "depth": int(x.get("depth", 0)), "frame": int(x.get("frame", 0))}
                     if x else None),
        })
    out.sort(key=lambda r: r["seq"])
    return out


RESIDENT_MD5S = None    # set by cmd_capture from the resident-overlay probe; None = no filter


def known_starts(lo, hi, extra=()):
    """Function start addresses (KSEG0) inside [lo, hi): the dispatch entry
    PCs of every overlay whose load address lies in the range (from
    analysis/overlay_captures_all.json) plus whatever the caller adds (the
    funcs observed in the capture itself). When RESIDENT_MD5S is set, only
    overlays resident at capture time contribute -- bands are shared, and
    2026-09-05 a SHOP.EMI zenny store was attributed to a BATTLE.EMI start
    at the same address because every occupant's starts were merged."""
    starts = set(int(x) for x in extra)
    p = os.path.join(AN, "overlay_captures_all.json")
    if os.path.exists(p):
        for c in json.load(open(p, encoding="utf-8")):
            base = kseg0(parse_int(c.get("load_addr", "0")))
            if not (lo <= base < hi):
                continue
            if RESIDENT_MD5S is not None and c.get("source_md5") not in RESIDENT_MD5S:
                continue
            # static_discovery_entry_pcs are jal targets + prologues (function
            # starts). dispatch_entry_pcs also hold jump-table INTERIOR entries
            # harvested from the interpreter, which are not starts and would
            # fragment a function so its callees look like someone else's.
            for pc in c.get("static_discovery_entry_pcs") or []:
                starts.add(kseg0(parse_int(pc)))
    # Ghidra's view of the same bands (tools/ghidra_run.py export): its
    # function starts split what the recompiler's roots merge and vice versa.
    # 2026-09-04: 4 of the 12 traced battle "functions" (0x801DFA04
    # Attack_Action among them) are interior stamps of larger Ghidra
    # functions, so the Ghidra starts make the forest nest by real units.
    for p in glob.glob(os.path.join(AN, "ghidra", "*.json")):
        if p.endswith((".meta.json", ".seed.json")):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("schema") != "ghidra-export-v1":
            continue
        mp = p[:-5] + ".meta.json"
        if RESIDENT_MD5S is not None and os.path.exists(mp):
            md5 = json.load(open(mp, encoding="utf-8")).get("source_md5")
            if md5 not in RESIDENT_MD5S:
                continue
        for f in d.get("functions", []):
            e = kseg0(parse_int(f["entry"]))
            if lo <= e < hi:
                starts.add(e)
    return sorted(starts)


def containing_start(starts, addr):
    """Greatest known function start <= addr, or None."""
    import bisect
    i = bisect.bisect_right(starts, addr)
    return starts[i - 1] if i else None


def boot_starts():
    """Boot-EXE function starts (KSEG0) from analysis/functions.tsv, first
    column hex. Empty if the file is absent."""
    out = set()
    if not os.path.exists(FUNCTIONS_TSV):
        return out
    for line in open(FUNCTIONS_TSV, encoding="utf-8", errors="replace"):
        tok = line.split()
        if not tok:
            continue
        try:
            out.add(kseg0(int(tok[0], 16)))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------- write trace (--watch)

def parse_range(spec, default_len=4):
    """'LO-HI' (exclusive hi), 'LO+LEN', or 'ADDR' (default_len bytes) -> (lo, hi) KSEG0."""
    s = str(spec).strip()
    if "-" in s[1:]:
        lo, hi = s.split("-", 1)
        lo, hi = kseg0(parse_int(lo)), kseg0(parse_int(hi))
    elif "+" in s[1:]:
        lo, n = s.split("+", 1)
        lo = kseg0(parse_int(lo))
        hi = lo + parse_int(n)
    else:
        lo = kseg0(parse_int(s))
        hi = lo + default_len
    if hi <= lo:
        raise SystemExit("empty range %r" % spec)
    return lo, hi


def wtrace_arm_ranges(port, ranges):
    """Replace the armed write-trace ranges with `ranges` [(lo, hi)]; returns
    the previous set so the caller can restore it."""
    prev = q(port, "wtrace_ranges").get("ranges", [])
    if len(ranges) > WTRACE_MAX_RANGES:
        raise SystemExit("too many --watch ranges (%d > %d)" % (len(ranges), WTRACE_MAX_RANGES))
    q(port, "wtrace_disarm_all")
    q(port, "wtrace_reset")
    armed = []
    for lo, hi in ranges:
        r = q(port, "wtrace_arm", lo=hx(lo), hi=hx(hi))
        armed.append({"lo": r.get("lo"), "hi": r.get("hi"), "slot": r.get("slot")})
    return prev, armed


def wtrace_restore(port, prev):
    q(port, "wtrace_disarm_all")
    for r in prev:
        q(port, "wtrace_arm", lo=r["lo"], hi=r["hi"])


def drain_writes(port, frame_lo, frame_hi):
    """Every write-trace row with frame in [frame_lo, frame_hi] (inclusive,
    the server's filter). wtrace_dump cannot page by seq, so a window that
    fills a 2048-row page is bisected; a single frame that still fills a
    page is recorded in `truncated`."""
    rows, truncated = [], []
    stack = [(frame_lo, frame_hi)]
    while stack:
        lo, hi = stack.pop()
        r = q(port, "wtrace_dump", frame_lo=int(lo), frame_hi=int(hi), count=PAGE, newest=0)
        ents = r.get("entries", [])
        if int(r.get("emitted", len(ents))) >= PAGE:
            if hi > lo:
                mid = (lo + hi) // 2
                stack.append((mid + 1, hi))
                stack.append((lo, mid))
                continue
            truncated.append(lo)
        rows.extend(ents)
    rows.sort(key=lambda e: int(e["seq"]))
    return rows, truncated


def normalise_writes(raw, starts_sorted, overlay_starts=None, bands=None):
    """Server rows -> flat write list; `writer` is the compiled function whose
    start is the greatest known start <= the store PC. A store PC inside a
    captured overlay body is attributed against OVERLAY starts only: the boot
    EXE image spans the same addresses with different code, so a boot start
    there is a coincidence (2026-09-04: the EXP tick's store at 0x801DD644
    got a boot-EXE label; the real function was an undiscovered, interpreted
    stretch of the game-mode overlay). writer None = no known start covers it."""
    out = []
    bands = bands or []
    for e in raw:
        pc = kseg0(parse_int(e["pc"]))
        in_band = any(lo <= pc < hi for lo, hi, _m, _s in bands)
        if in_band and overlay_starts is not None:
            w = containing_start(overlay_starts, pc)
            # a start from BEFORE the previous Ghidra/static function's end is
            # still a guess; keep it but the gap is reported by `writes`
        else:
            w = containing_start(starts_sorted, pc)
        out.append({
            "seq": int(e["seq"]),
            "addr": hx(kseg0(parse_int(e["addr"]))),
            "old": e.get("old"), "new": e.get("new"), "w": int(e.get("w", 4)),
            "pc": hx(pc), "ra": hx(kseg0(parse_int(e["ra"]))),
            "func_server": e.get("func"),
            "writer": hx(w) if w is not None else None,
            "args": [e.get("a0"), e.get("a1"), e.get("a2"), e.get("a3")],
            "s": [e.get("s0"), e.get("s1"), e.get("s2"), e.get("s3")],
            "frame": int(e.get("frame", 0)),
            "dma_ch": int(e.get("dma_ch", -1)),
        })
    return out


def all_starts(lo, hi, extra=()):
    """(all starts, overlay-only starts) inside [lo, hi), sorted (KSEG0)."""
    ov = sorted(set(known_starts(lo, hi, extra)))
    return sorted(set(ov) | boot_starts()), ov


def read_ram(port, lo, hi, chunk=0x10000):
    """RAM [lo, hi) as bytes via read_ram, in chunks (the server caps len at 2 MB)."""
    buf = bytearray()
    a = lo
    while a < hi:
        n = min(chunk, hi - a)
        r = q(port, "read_ram", addr=hx(a), len=n)
        b = bytes.fromhex(r.get("hex", ""))
        if len(b) != n:
            raise SystemExit("read_ram %s+%d returned %d bytes" % (hx(a), n, len(b)))
        buf += b
        a += n
    return bytes(buf)


def build_forest(entries, lo=None, hi=None):
    """Nest by RETURN ADDRESS, not by the ring's `depth`.

    The ring's `depth` is the psx_dispatch shadow-stack top, which the direct
    entry stamps (the majority of entries on a KSEG0 filter) never pop, so it
    climbs monotonically and means nothing (2026-09-04: 31, 62, 93 ... over a
    battle round). Exits are likewise only recorded on the dispatch path.
    What every entry does carry is `ra`; the caller is the function whose
    start is the greatest known start <= ra. Nesting: an open stack of
    frames; an entry whose caller is on the stack pops back to it and
    becomes its child; an entry whose caller is unknown or not on the stack
    becomes a root (gap = 1 flags "caller not seen", e.g. a boot-EXE or
    interpreted frame in between). Node = {"e": index, "gap", "tail",
    "caller", "c": [children]}. Returns (roots, counts)."""
    funcs = [parse_int(e["func"]) for e in entries]
    if lo is None:
        lo, hi = (min(funcs), max(funcs) + 1) if funcs else (0, 0)
    starts = known_starts(lo, hi, funcs)
    roots = []
    open_stack = []      # [(func, node)]
    # func -> positions in open_stack, newest last: the caller lookup was a
    # backward scan of the whole stack per entry, and since direct stamps
    # never pop, a 262 144-entry boot-EXE capture made that quadratic (a
    # save capture ran for minutes and was Ctrl-C'd here, 2026-09-05).
    where = {}
    MAX_OPEN = 4096      # leaked frames beyond this are dropped from the bottom

    def push(f, node):
        open_stack.append((f, node))
        where.setdefault(f, []).append(len(open_stack) - 1)
        if len(open_stack) > MAX_OPEN:
            drop = len(open_stack) - MAX_OPEN
            del open_stack[:drop]
            for k in list(where):
                lst = [x - drop for x in where[k] if x >= drop]
                if lst:
                    where[k] = lst
                else:
                    del where[k]

    def truncate(n):
        """Keep open_stack[:n]."""
        for f, _ in open_stack[n:]:
            lst = where.get(f)
            if lst:
                lst.pop()
                if not lst:
                    del where[f]
        del open_stack[n:]

    counts = {"tail_calls": 0, "gaps": 0, "gap_frames": 0, "unmatched_exits": 0,
              "open_entries": 0, "roots": 0, "unknown_caller": 0}
    prev = None
    for i, e in enumerate(entries):
        f = funcs[i]
        ra = parse_int(e["ra"])
        caller = containing_start(starts, kseg0(ra))
        if caller is not None and caller == f:
            # ra inside the function itself: a CPS continuation / loop
            # re-entry stamp, not a new call. Attach to the current top
            # frame without pushing, so a function never nests under itself.
            counts["continuations"] = counts.get("continuations", 0) + 1
            node = {"e": i, "gap": 0, "tail": False, "cont": True, "c": [], "caller": hx(caller)}
            (open_stack[-1][1]["c"] if open_stack else roots).append(node)
            prev = e
            continue
        node = {"e": i, "gap": 0, "tail": False, "c": [],
                "caller": hx(caller) if caller is not None else None}
        tail = (prev is not None and prev["ra"] == e["ra"] and prev["func"] != e["func"]
                and open_stack and open_stack[-1][0] == parse_int(prev["func"]))
        if tail:
            node["tail"] = True
            counts["tail_calls"] += 1
            truncate(len(open_stack) - 1)
        # pop until the caller is on top (a return to it happened in between)
        idx = None
        if caller is not None and caller in where:
            idx = where[caller][-1]
        if idx is not None:
            truncate(idx + 1)
            open_stack[idx][1]["c"].append(node)
        else:
            if caller is None:
                counts["unknown_caller"] += 1
            node["gap"] = 1
            counts["gaps"] += 1
            roots.append(node)
            counts["roots"] += 1
        push(f, node)
        if e.get("exit") is None:
            counts["open_entries"] += 1
        prev = e
    return roots, counts


def caller_of(entries, node, parent):
    """Caller key for edge sets: the parent func when the nesting is tight,
    else the (normalised) ra, which is all the trace knows."""
    if parent is not None and node["gap"] == 0:
        return entries[parent["e"]]["func"]
    if node.get("caller"):
        return node["caller"]
    return "ra:" + entries[node["e"]]["ra"]


def walk(entries, roots):
    """Yield (node, parent) in seq order."""
    stack = [(n, None) for n in reversed(roots)]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        for c in reversed(node["c"]):
            stack.append((c, node))


# ---------------------------------------------------------------- capture

def resident_overlays(port, lo, hi):
    """Which overlay body is resident in each band inside [lo, hi): longest
    RAM prefix match (256-byte steps) against every captured section whose
    load address is that band. Needed because the runtime's native ring can
    be empty at capture time and the resident image's data tail is modified
    at runtime, so an exact md5 never matches (2026-09-04: the battle band
    matched BATTLE.EMI#3 for 108 544 of 118 080 bytes). Returns
    {band_hex: {"md5", "source_file", "matched", "size"}}."""
    import base64
    p = os.path.join(AN, "overlay_captures_all.json")
    if not os.path.exists(p):
        return {}
    by_band = {}
    for c in json.load(open(p, encoding="utf-8")):
        base = kseg0(parse_int(c.get("load_addr", "0")))
        if lo <= base < hi and c.get("bytes_b64"):
            by_band.setdefault(base, []).append(c)
    out = {}
    for base, cands in by_band.items():
        n = max(int(c["size"]) for c in cands)
        r = q(port, "read_ram", addr=hx(base), len=n)
        ram = bytes.fromhex(r.get("hex", ""))
        best = None
        for c in cands:
            sec = base64.b64decode(c["bytes_b64"])
            m = 0
            while m + 256 <= min(len(sec), len(ram)) and sec[m:m + 256] == ram[m:m + 256]:
                m += 256
            if best is None or m > best[0]:
                best = (m, c)
        if best and best[0] >= 4096:
            m, c = best
            out[hx(base)] = {"md5": c.get("source_md5"), "source_file": c.get("source_file"),
                             "matched": m, "size": int(c["size"])}
    return out


def cmd_capture(a):
    port = a.port
    crcs = crc_index()
    by_size = script_sections()
    stats_before = q(port, "fn_stats")
    prev_filter = {"lo": stats_before.get("filter_lo"), "hi": stats_before.get("filter_hi"),
                   "active": int(stats_before.get("active", 0))}
    meta = {"schema": SCHEMA, "label": a.label, "port": port,
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": bool(a.dry_run), "slot": a.slot, "press": a.press or [],
            "press_word": None, "press_frames": a.press_frames, "hold": a.hold or [],
            "settle_frames": a.settle_frames, "window_frames": a.window_frames,
            "filter": None, "filter_before": prev_filter}
    lo, hi = parse_int(a.lo), parse_int(a.hi)
    watch_ranges = [parse_range(w) for w in (a.watch or [])]
    prev_wranges = []
    if a.dry_run:
        # Read-only: no state load, no input, no filter change, no clear.
        meta["filter"] = {"lo": hx(kseg0(parse_int(stats_before["filter_lo"]))),
                          "hi": hx(kseg0(parse_int(stats_before["filter_hi"]))),
                          "lo_phys": stats_before["filter_lo"],
                          "hi_phys": stats_before["filter_hi"]}
        frame_start = cur_frame(port)
        seq_lo_entry = 0
        seq_lo_exit = 0
    else:
        if a.slot is not None:
            print("loading savestate file slot %d ..." % a.slot)
            meta["savestate_status"] = load_state(port, a.slot)
        if a.settle_frames:
            wait_frames(port, a.settle_frames)
        q(port, "fn_clear")
        # KSEG0 form on purpose: the entry stamp at the top of every compiled
        # function (debug_server_log_call_entry) passes the 0x80xxxxxx address
        # and fn_trace_in_filter compares it raw, so a KSEG0 range catches
        # EVERY entry to a compiled function however it was reached. The
        # physical form only matches the psx_dispatch path (cross-unit calls),
        # which is the minority -- a physical range recorded 0 entries over
        # 146 frames of battle on 2026-09-04. --phys-filter restores that.
        fr = q(port, "fn_filter", lo=hx(phys(lo) if a.phys_filter else kseg0(lo)),
               hi=hx(phys(hi) if a.phys_filter else kseg0(hi)))
        meta["filter"] = {"lo": hx(kseg0(lo)), "hi": hx(kseg0(hi)),
                          "lo_phys": fr.get("lo"), "hi_phys": fr.get("hi")}
        if watch_ranges:
            prev_wranges, armed = wtrace_arm_ranges(port, watch_ranges)
            meta["watch"] = {"ranges": [[hx(l), hx(h)] for l, h in watch_ranges],
                             "armed": armed, "ranges_before": prev_wranges,
                             "values_at_arm": [read_ram(port, l, h).hex() for l, h in watch_ranges]}
        frame_start = cur_frame(port)
        seq_lo_entry = seq_lo_exit = 0
        if a.press:
            meta["press_words"] = press_buttons(port, a.press, a.press_frames, a.press_gap, a.hold)
        wait_frames(port, a.window_frames)
        q(port, "fn_disable")
    frame_end = cur_frame(port)
    stats_after = q(port, "fn_stats")
    meta["frame_start"], meta["frame_end"] = frame_start, frame_end
    meta["fn_stats"] = stats_after
    raw_w, trunc_w, wstats = [], [], None
    if watch_ranges and not a.dry_run:
        wstats = q(port, "wtrace_stats")
        raw_w, trunc_w = drain_writes(port, frame_start, frame_end)
        # Untraced-write detector: a watched cell whose bytes differ between
        # arm and now, with no traced write to it, changed through a path the
        # write hook does not see (or before/after the window edges). Report
        # it rather than let "0 writes" read as "nothing happened".
        meta["watch"]["values_at_end"] = [read_ram(port, l, h).hex() for l, h in watch_ranges]
        wtrace_restore(port, prev_wranges)
    try:
        # Always probe the two swap slots as well as the filter range: a boot-EXE
        # filter (BIOS wrappers) says nothing about which menu/save overlay was
        # driving the calls, and the slots are where those live (2026-09-05).
        ov = resident_overlays(port, kseg0(lo), kseg0(hi))
        for band_lo, band_hi in ((0x801D0C00, 0x801D0C01), (0x801EEC00, 0x801EEC01)):
            if not (kseg0(lo) <= band_lo < kseg0(hi)):
                ov.update(resident_overlays(port, band_lo, band_hi))
        meta["resident"] = {"area": resident_area(port, by_size),
                            "native_ring": native_ring_summary(port, crcs),
                            "overlays": ov}
    except SystemExit as ex:
        meta["resident"] = {"error": str(ex)}

    total_e = int(stats_after["entry_total"])
    total_x = int(stats_after["exit_total"])
    oldest_e = max(0, total_e - int(stats_after.get("entry_capacity", 1 << 18)))
    oldest_x = max(0, total_x - int(stats_after.get("exit_capacity", 1 << 18)))
    raw_e, drop_e = page_ring(port, "fn_entry_dump", max(seq_lo_entry, oldest_e), total_e)
    raw_x, drop_x = page_ring(port, "fn_exit_dump", max(seq_lo_exit, oldest_x), total_x)

    if not a.dry_run and not a.keep_filter:
        # Put the trace back the way it was for whoever else is using it.
        if prev_filter["lo"] is not None:
            q(port, "fn_filter", lo=prev_filter["lo"], hi=prev_filter["hi"])
        if not prev_filter["active"]:
            q(port, "fn_disable")

    entries = normalise_entries(raw_e, raw_x)
    roots, counts = build_forest(entries, kseg0(lo), kseg0(hi))
    counts.update({"entries": len(entries), "exits": len(raw_x),
                   "entries_overwritten": drop_e, "exits_overwritten": drop_x,
                   "entries_lost_to_wrap": oldest_e,
                   "server_unmatched_returns": int(stats_after.get("unmatched_returns", 0)),
                   "server_stack_overflows": int(stats_after.get("stack_overflows", 0)),
                   "server_tail_calls": int(stats_after.get("tail_calls", 0))})
    doc = dict(meta)
    doc["counts"] = counts
    doc["entries"] = entries
    doc["forest"] = roots
    if watch_ranges:
        global RESIDENT_MD5S
        res_ov = (meta.get("resident") or {}).get("overlays") or {}
        RESIDENT_MD5S = {v["md5"] for v in res_ov.values() if v.get("md5")} or None
        starts, ov_starts = all_starts(kseg0(lo), kseg0(hi), [parse_int(e["func"]) for e in entries])
        writes = normalise_writes(raw_w, starts, ov_starts, overlay_ranges())
        doc["writes"] = writes
        doc["counts"]["writes"] = len(writes)
        doc["counts"]["writes_truncated_frames"] = trunc_w
        doc["counts"]["writes_unattributed"] = sum(1 for w in writes if w["writer"] is None)
        doc["counts"]["wtrace_total"] = int(wstats.get("total", 0)) if wstats else None
        doc["counts"]["wtrace_lost_to_wrap"] = int(wstats.get("oldest_seq", 0)) if wstats else None
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("%s: frames %d-%d, %d entries (%d exits joined), %d roots, %d gaps, %d tail calls -> %s"
          % (a.label, frame_start, frame_end, len(entries),
             sum(1 for e in entries if e["exit"]), counts["roots"], counts["gaps"],
             counts["tail_calls"], a.out))
    if watch_ranges:
        ws = doc["writes"]
        written = {w["addr"] for w in ws}
        silent = []
        for (l, h), b0, b1 in zip(watch_ranges, meta["watch"]["values_at_arm"], meta["watch"]["values_at_end"]):
            if b0 != b1 and not any(l <= parse_int(x) < h for x in written):
                silent.append("%s %s->%s" % (hx(l), b0, b1))
        doc["counts"]["writes_untraced_changes"] = silent
        if silent:
            print("WARNING: watched cells CHANGED with no traced write: %s -- the store bypassed the write hook "
                  "(DMA/accelerated copy/host-side) or happened outside the window edges" % "; ".join(silent))
        print("writes: %d in %d range(s), %d unattributed, %d distinct writer(s)%s%s"
              % (len(ws), len(watch_ranges), doc["counts"]["writes_unattributed"],
                 len({w["writer"] for w in ws if w["writer"]}),
                 ("; TRUNCATED frames %s" % trunc_w) if trunc_w else "",
                 ("; ring wrapped, %d lost" % doc["counts"]["wtrace_lost_to_wrap"])
                 if doc["counts"]["wtrace_lost_to_wrap"] else ""))
    if oldest_e:
        print("WARNING: entry ring wrapped; the first %d entries are gone -- tighten the filter or the window"
              % oldest_e)
    res = doc["resident"]
    if isinstance(res, dict) and res.get("area"):
        print("resident area: %s (%s)" % (res["area"]["file"], res["area"]["md5"]))
    if isinstance(res, dict) and res.get("native_ring"):
        for crc, b in res["native_ring"]["bodies"].items():
            print("native body %s x%d %s %s" % (crc, b["calls"], b["source_file"], b["source_md5"]))
    return 0


# ---------------------------------------------------------------- tree

def load_capture(path):
    d = json.load(open(path, encoding="utf-8"))
    if d.get("schema") != SCHEMA:
        raise SystemExit("%s: not a %s file" % (path, SCHEMA))
    return d


def subtree_sig(entries, node):
    return (entries[node["e"]]["func"], tuple(subtree_sig(entries, c) for c in node["c"]))


def fmt_entry(e):
    ret = e["exit"]["v0"] if e["exit"] else "open"
    return "%s ra=%s a=(%s) ret=%s f%d" % (
        e["func"], e["ra"], ",".join(x or "?" for x in e["args"]), ret, e["frame"])


def print_tree(entries, nodes, depth, max_depth, out, names=None):
    if max_depth is not None and depth > max_depth:
        return
    i = 0
    while i < len(nodes):
        node = nodes[i]
        sig = subtree_sig(entries, node)
        n = 1
        while i + n < len(nodes) and subtree_sig(entries, nodes[i + n]) == sig:
            n += 1
        e = entries[node["e"]]
        marks = []
        if node["gap"]:
            marks.append("gap+%d" % node["gap"])
        if node["tail"]:
            marks.append("tail")
        if node.get("cont"):
            marks.append("cont")
        if n > 1:
            marks.append("x%d" % n)
        nm = ""
        if names:
            nm = names.get(e["func"], "")
            nm = (" " + nm) if nm else ""
        out.append("%s%s%s%s" % ("  " * depth, fmt_entry(e), nm,
                                  (" [" + " ".join(marks) + "]") if marks else ""))
        print_tree(entries, node["c"], depth + 1, max_depth, out, names)
        i += n


def cmd_tree(a):
    d = load_capture(a.file)
    entries = d["entries"]
    roots, d["counts"] = build_forest(entries, parse_int(d["filter"]["lo"]), parse_int(d["filter"]["hi"]))
    if a.top:
        roots = roots[:a.top]
    out = []
    print("%s: frames %d-%d filter %s-%s, %d entries, %s" % (
        d["label"], d["frame_start"], d["frame_end"], d["filter"]["lo"], d["filter"]["hi"],
        len(entries), json.dumps(d["counts"])))
    names = known_names()
    # Roots are entries whose caller frame was not traced (entered before the
    # window, boot EXE, or interpreted). Group them by that caller so the
    # per-frame loop reads as "<caller> -> {callees}" instead of a flat list.
    groups = {}
    for r in roots:
        groups.setdefault(r.get("caller") or "?", []).append(r)
    for caller, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        nm = names.get(caller, "")
        out.append("caller %s%s (not traced) -> %d roots" % (caller, (" " + nm) if nm else "", len(rs)))
        print_tree(entries, rs, 1, a.max_depth, out, names)
    print("\n".join(out))
    return 0


def known_names():
    """func (0x80 KSEG0) -> name from names/functions.toml, overlay-blind."""
    out = {}
    if not os.path.exists(FUNCTIONS_TOML):
        return out
    with open(FUNCTIONS_TOML, "rb") as f:
        doc = tomllib.load(f)
    for r in doc.get("function", []) + doc.get("func", []):
        out[hx(kseg0(int(r["pc"])))] = r.get("name", "")
    return out


# ---------------------------------------------------------------- diff

def func_first_seen(d):
    out = {}
    for e in d["entries"]:
        out.setdefault(e["func"], e["seq"])
    return out


def edge_first_seen(d):
    entries = d["entries"]
    out = {}
    roots, _ = build_forest(entries, parse_int(d["filter"]["lo"]), parse_int(d["filter"]["hi"]))
    for node, parent in walk(entries, roots):
        e = entries[node["e"]]
        out.setdefault((e["func"], caller_of(entries, node, parent)), e["seq"])
    return out


def func_sequence(d):
    return [e["func"] for e in d["entries"]]


def common_prefix(seqs):
    if not seqs:
        return []
    n = min(len(s) for s in seqs)
    i = 0
    while i < n and all(s[i] == seqs[0][i] for s in seqs):
        i += 1
    return seqs[0][:i]


def cmd_diff(a):
    A, B = load_capture(a.a), load_capture(a.b)
    names = known_names()

    def show(title, keys, order, fmt):
        print("\n%s (%d)" % (title, len(keys)))
        for k in sorted(keys, key=lambda k: order[k]):
            print("  " + fmt(k))

    fa, fb = func_first_seen(A), func_first_seen(B)
    order = {k: min(fa.get(k, 1 << 62), fb.get(k, 1 << 62)) for k in set(fa) | set(fb)}
    nm = lambda f: ("%s %s" % (f, names.get(f, ""))).rstrip()
    print("A = %s (frames %d-%d), B = %s (frames %d-%d)" % (
        A["label"], A["frame_start"], A["frame_end"], B["label"], B["frame_start"], B["frame_end"]))
    print("\n== functions ==")
    show("only in A", set(fa) - set(fb), order, nm)
    show("only in B", set(fb) - set(fa), order, nm)
    show("common", set(fa) & set(fb), order, nm)

    ea, eb = edge_first_seen(A), edge_first_seen(B)
    order = {k: min(ea.get(k, 1 << 62), eb.get(k, 1 << 62)) for k in set(ea) | set(eb)}
    ef = lambda k: "%s <- %s" % (nm(k[0]), k[1] if k[1].startswith("ra:") else nm(k[1]))
    print("\n== (func, caller) edges ==")
    show("only in A", set(ea) - set(eb), order, ef)
    show("only in B", set(eb) - set(ea), order, ef)
    show("common", set(ea) & set(eb), order, ef)

    if a.prefix:
        pre = common_prefix([func_sequence(A), func_sequence(B)])
        print("\n== longest common prefix of the entry sequences (%d entries, %d distinct) =="
              % (len(pre), len(set(pre))))
        for i, f in enumerate(pre):
            ea_ = A["entries"][i]
            eb_ = B["entries"][i]
            same_args = ea_["args"] == eb_["args"]
            print("  %4d %s d%d a=(%s)%s" % (i, nm(f), ea_["depth"],
                                             ",".join(x or "?" for x in ea_["args"]),
                                             "" if same_args else "  B a=(%s)" % ",".join(x or "?" for x in eb_["args"])))
    return 0


# ---------------------------------------------------------------- propose

def resolve_overlay(func, caps, ranges):
    """Pick the overlay md5 that owns `func` in these captures. Evidence order:
    a native-ring body CRC seen in every capture whose overlay contains the
    address; else a unique captured overlay body containing it. Returns
    (md5 or None, note)."""
    f = kseg0(parse_int(func))
    candidates = [(md5, src) for lo, hi, md5, src in ranges if lo <= f < hi]
    cand_md5 = {m for m, _ in candidates}
    if not candidates:
        return None, "no captured overlay body contains %s (boot EXE? use symbols.toml)" % func
    seen = None
    for d in caps:
        res = d.get("resident") or {}
        ring = res.get("native_ring") or {}
        here = {b["source_md5"] for b in (ring.get("bodies") or {}).values()
                if b.get("source_md5") in cand_md5}
        seen = here if seen is None else (seen & here)
    if seen and len(seen) == 1:
        m = next(iter(seen))
        return m, "native-ring body resident in every capture"
    if len(cand_md5) == 1:
        m = next(iter(cand_md5))
        return m, "only captured occupant of that address"
    names = sorted({s.rsplit("/", 1)[-1] for _, s in candidates})
    return None, ("ambiguous among %d occupants (%s%s); no native-ring body pins it -- pass --overlay MD5"
                  % (len(cand_md5), ", ".join(names[:6]), ", ..." if len(names) > 6 else ""))


FUNC_TABLE = "function"     # names/functions.toml table name; set by read_functions_toml


def read_functions_toml():
    """(header text, rows). Accepts both `[[function]]` (the file's documented
    form) and the older `[[func]]`; remembers which one the file uses so
    emit_functions_toml writes it back unchanged."""
    global FUNC_TABLE
    if not os.path.exists(FUNCTIONS_TOML):
        return "", []
    with open(FUNCTIONS_TOML, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    doc = tomllib.loads(text)
    if doc.get("function") or "[[function]]" in text:
        FUNC_TABLE = "function"
    elif doc.get("func"):
        FUNC_TABLE = "func"
    rows = doc.get("function", []) + doc.get("func", [])
    tag = "[[%s]]" % FUNC_TABLE
    header = text.split(tag, 1)[0].rstrip() + "\n" if tag in text else text.rstrip() + "\n"
    return header, rows


def _q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit_functions_toml(header, rows):
    out = [header]
    for r in rows:
        out.append("\n[[%s]]\n" % FUNC_TABLE)
        for k, v in r.items():
            if v is None:
                continue
            if isinstance(v, bool):
                out.append("%s = %s\n" % (k, "true" if v else "false"))
            elif isinstance(v, int):
                out.append("%s = 0x%08X\n" % (k, v) if k == "pc" else "%s = %d\n" % (k, v))
            elif isinstance(v, list):
                out.append("%s = [%s]\n" % (k, ", ".join(_q(x) for x in v)))
            else:
                out.append("%s = %s\n" % (k, _q(v)))
    return "".join(out)


def cmd_venn(a):
    """Membership of every function across N captures: which captures it
    appears in, and per capture the first/last frame offset from the capture
    start, the call count and the number of distinct a0 values. Functions in
    ALL captures are counted, not listed (they are the shared loop)."""
    caps = [load_capture(f) for f in a.files]
    labels = [c["label"] for c in caps]
    per = []
    for c in caps:
        d = {}
        for e in c["entries"]:
            r = d.setdefault(e["func"], [e["frame"], e["frame"], 0, set()])
            r[1] = e["frame"]
            r[2] += 1
            r[3].add(e["args"][0] if e.get("args") else None)
        per.append(d)
    names = known_names()
    allf = set()
    for d in per:
        allf |= set(d)
    groups = {}
    for f in allf:
        k = tuple(i for i, d in enumerate(per) if f in d)
        groups.setdefault(k, []).append(f)
    for i, c in enumerate(caps):
        print("%s = %s (frames %d-%d, %d entries)" % (chr(65 + i), c["label"], c["frame_start"], c["frame_end"], len(c["entries"])))
    for k in sorted(groups, key=lambda k: (len(k), k)):
        fs = sorted(groups[k])
        print("\n== in %s only: %d functions" % ("+".join(labels[i] for i in k), len(fs)))
        if len(k) == len(caps) and not a.all:
            continue
        for f in fs:
            parts = []
            for i in k:
                f0 = caps[i]["frame_start"]
                first, last, n, a0s = per[i][f]
                parts.append("%s: +%d..+%df x%d a0s=%d" % (labels[i], first - f0, last - f0, n, len(a0s)))
            nm = names.get(f, "")
            print("   %s%s  %s" % (f, (" " + nm) if nm else "", " | ".join(parts)))
    return 0


def cmd_propose(a):
    caps = [load_capture(p) for p in a.files]
    labels = [d["label"] for d in caps]
    pre = common_prefix([func_sequence(d) for d in caps])
    if not pre:
        print("no common prefix across %s" % ", ".join(labels))
        return 1
    fa = max(d["frame_start"] for d in caps)
    fb = max(d["frame_end"] for d in caps)
    evidence = "callstack_diff: %s, frames %d-%d" % (", ".join(labels), min(d["frame_start"] for d in caps), fb)
    ranges = overlay_ranges()
    known_overlays = set()
    if os.path.exists(OVERLAYS_TOML):
        with open(OVERLAYS_TOML, "rb") as f:
            known_overlays = {r["md5"] for r in tomllib.load(f).get("overlay", [])}
    header, rows = read_functions_toml()
    existing = {(r["overlay"], int(r["pc"])): r for r in rows}

    seen, order = set(), []
    for f in pre:
        if f not in seen:
            seen.add(f)
            order.append(f)
    print("common prefix across %s: %d entries, %d distinct functions" % (", ".join(labels), len(pre), len(order)))
    new_rows, touched = [], 0
    for idx, f in enumerate(order):
        if a.overlay:
            md5, note = a.overlay, "--overlay"
        else:
            md5, note = resolve_overlay(f, caps, ranges)
        pc = kseg0(parse_int(f))
        if md5 is None:
            print("  skip %s: %s" % (f, note))
            continue
        if md5 not in known_overlays:
            print("  skip %s: overlay %s is not in names/overlays.toml (run name_map.py init)" % (f, md5))
            continue
        key = (md5, pc)
        if key in existing:
            r = existing[key]
            if not r.get("evidence"):
                r["evidence"] = evidence
                touched += 1
                print("  keep %s %s (adding evidence only)" % (f, r.get("name", "")))
            else:
                print("  keep %s %s (already named, untouched)" % (f, r.get("name", "")))
            continue
        row = {"overlay": md5, "pc": pc, "name": "%s_%02d" % (a.name_prefix, idx),
               "args": [], "ret": None, "status": "hypothesis", "evidence": evidence,
               "note": "prefix position %d; overlay by %s" % (idx, note)}
        new_rows.append(row)
        print("  + %s -> %s @ %s (%s)" % (f, row["name"], md5, note))
    if not new_rows and not touched:
        print("nothing to write")
        return 0
    if not a.apply:
        print("dry run: %d new row(s), %d evidence fill(s); re-run with --apply" % (len(new_rows), touched))
        return 0
    rows = rows + sorted(new_rows, key=lambda r: (r["overlay"], r["pc"]))
    with open(FUNCTIONS_TOML, "w", encoding="utf-8", newline="\n") as f:
        f.write(emit_functions_toml(header, rows))
    print("wrote %s: +%d row(s), %d evidence fill(s)" % (FUNCTIONS_TOML, len(new_rows), touched))
    rc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "name_map.py"), "check"]).returncode
    return 0 if rc == 0 else 1


# ---------------------------------------------------------------- writes

def _sval(hexstr, width):
    """Signed value of a write's old/new field at its width."""
    v = parse_int(hexstr) & ((1 << (8 * width)) - 1)
    if v >= 1 << (8 * width - 1):
        v -= 1 << (8 * width)
    return v


def cmd_writes(a):
    """Report the write trace of a capture: per watched address, which
    compiled function stored to it, how often, and the value transitions,
    so 'the only writer of party HP under Attack' is one line."""
    d = load_capture(a.file)
    ws = d.get("writes")
    if ws is None:
        raise SystemExit("%s has no write trace (capture with --watch)" % a.file)
    names = known_names()
    f0 = d["frame_start"]
    only = {hx(kseg0(parse_int(x))) for x in (a.addr or [])}
    rows = []
    for w in ws:
        if only and w["addr"] not in only:
            continue
        if a.changes_only and w["old"] == w["new"]:
            continue
        delta = _sval(w["new"], w["w"]) - _sval(w["old"], w["w"])
        if a.dec and delta >= 0:
            continue
        rows.append((w, delta))
    print("%s: %d writes (%d shown), frames %d-%d, watched %s" % (
        d["label"], len(ws), len(rows), f0, d["frame_end"],
        " ".join("%s-%s" % tuple(r) for r in (d.get("watch") or {}).get("ranges", []))))
    nm = lambda f: ("%s %s" % (f, names.get(f, ""))).rstrip() if f else "?"
    by_addr = {}
    for w, delta in rows:
        by_addr.setdefault(w["addr"], []).append((w, delta))
    for addr in sorted(by_addr):
        lst = by_addr[addr]
        print("\n%s  (%d writes)" % (addr, len(lst)))
        by_writer = {}
        for w, delta in lst:
            by_writer.setdefault(w["writer"], []).append((w, delta))
        for writer, wl in sorted(by_writer.items(), key=lambda kv: -len(kv[1])):
            frames = [w["frame"] - f0 for w, _ in wl]
            pcs = sorted({w["pc"] for w, _ in wl})
            print("  writer %-30s x%-4d frames +%d..+%d  store pc %s%s" % (
                nm(writer), len(wl), min(frames), max(frames), ", ".join(pcs[:4]),
                " ..." if len(pcs) > 4 else ""))
            shown = 0
            for w, delta in wl:
                if w["old"] == w["new"] and not a.verbose:
                    continue
                print("      f+%-5d %s -> %s (%+d) w%d ra=%s a=(%s)" % (
                    w["frame"] - f0, w["old"], w["new"], delta, w["w"], w["ra"],
                    ",".join(x or "?" for x in w["args"])))
                shown += 1
                if shown >= a.max_per_writer and not a.verbose:
                    rest = sum(1 for w2, _ in wl if w2["old"] != w2["new"]) - shown
                    if rest > 0:
                        print("      ... %d more changing writes" % rest)
                    break
    tr = d["counts"].get("writes_truncated_frames") or []
    if tr:
        print("\nWARNING: frames %s exceeded one 2048-row page; their writes are incomplete" % tr)
    return 0


# ---------------------------------------------------------------- ramdiff

RAMDIFF_DIR = os.path.join(AN, "ramdiff")


def _cells(before, after, base, width, aligned):
    """Yield (addr, vb, va, delta) for every width-byte cell that changed."""
    step = width if aligned else 1
    half = 1 << (8 * width - 1)
    full = 1 << (8 * width)
    for off in range(0, len(before) - width + 1, step):
        vb = int.from_bytes(before[off:off + width], "little")
        va = int.from_bytes(after[off:off + width], "little")
        if vb == va:
            continue
        sb = vb - full if vb >= half else vb
        sa = va - full if va >= half else va
        yield base + off, vb, va, sa - sb


def filter_snapshots(snaps, width, deltas, aligned, min_before=None, max_hits=60, label=""):
    """snaps = [(lo, before_bytes, after_bytes)]. deltas: list of signed ints
    (a cell matching ANY of them is a hit; damage is per member so three
    numbers are three deltas) or empty = every changed cell."""
    hits, changed = [], 0
    for lo, b, c in snaps:
        for addr, vb, va, delta in _cells(b, c, lo, width, aligned):
            changed += 1
            if deltas and delta not in deltas:
                continue
            if min_before is not None and vb < min_before:
                continue
            hits.append((addr, vb, va, delta))
    print("%s%d %d-byte cells changed; %d match%s" % (
        (label + ": ") if label else "", changed, width, len(hits),
        (" deltas %s" % ",".join("%+d" % d for d in deltas)) if deltas else ""))
    for addr, vb, va, delta in hits[:max_hits]:
        print("  %s  %d -> %d (%+d)" % (hx(addr), vb, va, delta))
    if max_hits and len(hits) > max_hits:
        print("  ... %d more (raise --max-hits, add --aligned, or tighten --delta)" % (len(hits) - max_hits))
    return hits, changed


def parse_deltas(items):
    out = []
    for it in items or []:
        for tok in str(it).replace(";", ",").split(","):
            tok = tok.strip()
            if tok:
                out.append(int(tok, 0))
    return out


def cmd_ramdiff(a):
    """Find a RAM cell by its effect. Snapshot [ranges] after settling, run
    the press sequence, wait the window, snapshot again, and KEEP BOTH
    SNAPSHOTS in analysis/ramdiff/<label>.*.bin so the delta can be supplied
    afterwards -- BoF3 damage is randomised, so the numbers are read off the
    screen after the round, not known in advance. With no --delta the tool
    prompts for them once the window has elapsed (--no-ask to skip);
    `ramfilter` re-queries the saved pair with any deltas/width later.
    Damage 37 on screen -> delta -37 (--width 2 default)."""
    port = a.port
    ranges = [parse_range(r) for r in (a.range or [])] or [(RAM_LO, RAM_HI)]
    if a.slot is not None:
        print("loading savestate file slot %d ..." % a.slot)
        load_state(port, a.slot)
    if a.settle_frames:
        wait_frames(port, a.settle_frames)
    before = {lo: read_ram(port, lo, hi) for lo, hi in ranges}
    f0 = cur_frame(port)
    if a.press:
        press_buttons(port, a.press, a.press_frames, a.press_gap, a.hold)
    print("frame %d: pressed; waiting %d frames (read the damage numbers now) ..." % (f0, a.window_frames))
    wait_frames(port, a.window_frames)
    after = {lo: read_ram(port, lo, hi) for lo, hi in ranges}
    f1 = cur_frame(port)

    os.makedirs(RAMDIFF_DIR, exist_ok=True)
    label = a.label or ("slot%s_%s" % (a.slot if a.slot is not None else "live", time.strftime("%H%M%S")))
    meta_path = os.path.join(RAMDIFF_DIR, label + ".json")
    snaps = []
    for lo, hi in ranges:
        bp = os.path.join(RAMDIFF_DIR, "%s.%08X.before.bin" % (label, lo))
        ap = os.path.join(RAMDIFF_DIR, "%s.%08X.after.bin" % (label, lo))
        open(bp, "wb").write(before[lo])
        open(ap, "wb").write(after[lo])
        snaps.append({"lo": hx(lo), "hi": hx(hi), "before": os.path.basename(bp), "after": os.path.basename(ap)})
    meta = {"schema": "ramdiff-v2", "label": label, "slot": a.slot, "press": a.press or [], "hold": a.hold or [],
            "frames": [f0, f1], "ranges": snaps, "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "queries": []}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print("snapshots kept: %s  (re-query any time: ramfilter %s --delta N,N,N)" % (meta_path, meta_path))

    deltas = parse_deltas(a.delta)
    if not deltas and not a.no_ask and sys.stdin.isatty():
        try:
            ans = input("%s seen this round (comma-separated, e.g. %s; Enter = list all changes): "
                        % (("signed deltas", "+120,-37") if a.signed else ("damage numbers", "37,41,12"))).strip()
        except EOFError:
            ans = ""
        if ans:
            deltas = parse_deltas([ans]) if a.signed else [-abs(d) for d in parse_deltas([ans])]
    return _run_filter(meta_path, a.width, deltas, a.aligned, a.min_before, a.max_hits)


def _load_snaps(meta_path):
    meta = json.load(open(meta_path, encoding="utf-8"))
    d = os.path.dirname(os.path.abspath(meta_path))
    snaps = []
    for r in meta["ranges"]:
        snaps.append((parse_int(r["lo"]), open(os.path.join(d, r["before"]), "rb").read(),
                      open(os.path.join(d, r["after"]), "rb").read()))
    return meta, snaps


def _run_filter(meta_path, width, deltas, aligned, min_before, max_hits, intersect=None, signed=False):
    meta, snaps = _load_snaps(meta_path)
    hits, changed = filter_snapshots(snaps, width, deltas, aligned, min_before, max_hits, meta["label"])
    if intersect:
        # cells that also match in another ramdiff (different roll / enemy):
        # the HP cell survives, coincidental deltas do not.
        for other in intersect:
            # "file" or "file=37,41,12": each round has its own damage roll, so
            # each file gets its own deltas; a bare file reuses the deltas its
            # last ramfilter query stored (a first-time file needs the "=" form).
            path, _, dl = str(other).partition("=")
            m2, s2 = _load_snaps(path)
            if dl:
                d2 = [-abs(d) for d in parse_deltas([dl])] if not signed else parse_deltas([dl])
            else:
                qs = m2.get("queries") or []
                d2 = qs[-1]["deltas"] if qs else []
                if not d2:
                    raise SystemExit("%s has no stored query; pass it as %s=N,N,N" % (path, path))
            print("-- intersect with %s (deltas %s)" % (m2["label"], ",".join("%+d" % d for d in d2)))
            h2, _ = filter_snapshots(s2, width, d2, aligned, min_before, 0, m2["label"])
            keep = {h[0] for h in h2}
            hits = [h for h in hits if h[0] in keep]
        print("cells matching in every ramdiff: %d" % len(hits))
        for addr, vb, va, delta in hits[:max_hits]:
            print("  %s  %d -> %d (%+d)" % (hx(addr), vb, va, delta))
    meta.setdefault("queries", []).append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "width": width,
                                           "deltas": deltas, "aligned": aligned, "changed": changed,
                                           "hits": [hx(h[0]) for h in hits[:200]]})
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return 0


def cmd_ramfilter(a):
    """Re-query a saved ramdiff pair with deltas read off the screen after
    the fact. --delta 37 and --delta -37 both mean 'dropped by 37' unless
    --signed is given (then +N means grew by N: EXP, AP regen)."""
    deltas = parse_deltas(a.delta)
    if not a.signed:
        deltas = [-abs(d) for d in deltas]
    return _run_filter(a.file, a.width, deltas, a.aligned, a.min_before, a.max_hits, a.intersect, a.signed)


# ---------------------------------------------------------------- name

def cmd_name(a):
    """Upsert one row in names/functions.toml. The overlay is resolved from
    the captured bodies containing the PC when unique; a mixed band needs
    --overlay. An existing row keeps its name unless --force; evidence is
    appended, never replaced."""
    pc = kseg0(parse_int(a.func))
    ranges = overlay_ranges()
    if a.overlay:
        md5, note = a.overlay, "--overlay"
    else:
        cands = sorted({(md5, src) for lo, hi, md5, src in ranges if lo <= pc < hi})
        if not cands:
            raise SystemExit("no captured overlay body contains %s (boot EXE? edit symbols.toml)" % hx(pc))
        if len({m for m, _ in cands}) > 1:
            raise SystemExit("ambiguous: %s -- pass --overlay MD5" % ", ".join(
                "%s (%s)" % (m[:8], s.rsplit("/", 1)[-1]) for m, s in cands))
        md5, note = cands[0][0], "only captured occupant of that address"
    known_overlays = set()
    if os.path.exists(OVERLAYS_TOML):
        with open(OVERLAYS_TOML, "rb") as f:
            known_overlays = {r["md5"] for r in tomllib.load(f).get("overlay", [])}
    if md5 not in known_overlays:
        raise SystemExit("overlay %s is not in names/overlays.toml (run name_map.py init)" % md5)
    header, rows = read_functions_toml()
    key = (md5, pc)
    existing = {(r["overlay"], int(r["pc"])): r for r in rows}
    args = [s for s in (a.args or "").split(",") if s]
    if key in existing:
        r = existing[key]
        before = dict(r)
        if r.get("name") != a.name:
            if not a.force:
                raise SystemExit("%s is already %s (%s); pass --force to rename" % (hx(pc), r.get("name"), r.get("status")))
            r["name"] = a.name
        if args:
            r["args"] = args
        if a.status:
            r["status"] = a.status
        if a.evidence and a.evidence not in (r.get("evidence") or ""):
            r["evidence"] = ((r.get("evidence") or "").rstrip() + (" | " if r.get("evidence") else "") + a.evidence)
        action = "update" if r != before else "unchanged"
    else:
        r = {"overlay": md5, "pc": pc, "name": a.name, "args": args,
             "status": a.status or "hypothesis", "evidence": a.evidence or "",
             "note": "overlay by %s" % note}
        rows.append(r)
        action = "add"
    print("%s %s -> %s [%s] overlay %s (%s)" % (action, hx(pc), r["name"], r["status"], md5[:8], note))
    if not a.apply:
        print("dry run; re-run with --apply")
        return 0
    rows.sort(key=lambda r: (r["overlay"], int(r["pc"])))
    with open(FUNCTIONS_TOML, "w", encoding="utf-8", newline="\n") as f:
        f.write(emit_functions_toml(header, rows))
    rc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "name_map.py"), "check"]).returncode
    return 0 if rc == 0 else 1


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="record one input's call forest from a running game")
    c.add_argument("--label", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--port", type=int, default=PORT)
    c.add_argument("--slot", type=int, default=None, help="savestate FILE number to load first")
    c.add_argument("--press", action="append", default=None,
                   help="one press after settling; repeat the flag for a SEQUENCE (down, then circle); "
                        "join with + to hold together (select+r1). Buttons: " + ", ".join(BUTTONS))
    c.add_argument("--press-frames", type=int, default=2, help="how long each press holds (frames)")
    c.add_argument("--press-gap", type=int, default=10, help="frames between consecutive presses")
    c.add_argument("--hold", action="append", default=None,
                   help="button(s) held DOWN for the whole press sequence (repeatable); the battle "
                        "command menu needs --hold right for Defend")
    c.add_argument("--lo", default="0x801D0C00", help="fn_filter low bound (KSEG0 ok; sent physical)")
    c.add_argument("--hi", default="0x801F0000", help="fn_filter high bound, exclusive")
    c.add_argument("--settle-frames", type=int, default=30)
    c.add_argument("--window-frames", type=int, default=60)
    c.add_argument("--keep-filter", action="store_true", help="leave our filter armed instead of restoring the previous one")
    c.add_argument("--phys-filter", action="store_true", help="send the filter in physical form (dispatch-path stamps only; default is KSEG0, which catches every compiled-function entry)")
    c.add_argument("--dry-run", action="store_true",
                   help="read-only: no savestate, no input, no filter/clear; drain what the rings hold")
    c.add_argument("--watch", action="append", default=None,
                   help="RAM range to write-trace during the window: LO-HI, LO+LEN or ADDR (4 bytes); "
                        "repeatable. Writers are attributed by store PC; see the `writes` subcommand")
    c.set_defaults(fn=cmd_capture)

    w = sub.add_parser("writes", help="per-address writers and value transitions of a --watch capture")
    w.add_argument("file")
    w.add_argument("--addr", action="append", default=None, help="only this watched address (repeatable)")
    w.add_argument("--changes-only", action="store_true", help="drop writes where old == new")
    w.add_argument("--dec", action="store_true", help="only writes that decreased the value (damage)")
    w.add_argument("--max-per-writer", type=int, default=12)
    w.add_argument("--verbose", action="store_true", help="every write, including old == new")
    w.set_defaults(fn=cmd_writes)

    r = sub.add_parser("ramdiff", help="find the RAM cell a press changes (snapshot / press / snapshot)")
    r.add_argument("--port", type=int, default=PORT)
    r.add_argument("--slot", type=int, default=None, help="savestate FILE number to load first")
    r.add_argument("--press", action="append", default=None, help="press sequence (as in capture)")
    r.add_argument("--press-frames", type=int, default=2)
    r.add_argument("--press-gap", type=int, default=10)
    r.add_argument("--hold", action="append", default=None)
    r.add_argument("--settle-frames", type=int, default=30)
    r.add_argument("--window-frames", type=int, default=600)
    r.add_argument("--range", action="append", default=None,
                   help="RAM range LO-HI to compare (repeatable; default all 2 MB)")
    r.add_argument("--width", type=int, default=2, choices=(1, 2, 4))
    r.add_argument("--aligned", action="store_true", help="only width-aligned cells")
    r.add_argument("--label", default=None, help="name for analysis/ramdiff/<label>.* (default slot+time)")
    r.add_argument("--delta", action="append", default=None,
                   help="signed after-before to match; repeatable or comma-separated (-37,-41). Omitted: prompt after the round")
    r.add_argument("--no-ask", action="store_true", help="never prompt; list every changed cell")
    r.add_argument("--signed", action="store_true",
                   help="numbers typed at the prompt keep their sign (+N = value grew, e.g. EXP); default treats them as drops. "
                        "--delta on the command line is always taken as written")
    r.add_argument("--min-before", type=int, default=None, help="ignore cells whose value before was below this")
    r.add_argument("--max-hits", type=int, default=60)
    r.set_defaults(fn=cmd_ramdiff)

    rf = sub.add_parser("ramfilter", help="re-query a saved ramdiff pair with damage numbers read after the round")
    rf.add_argument("file", help="analysis/ramdiff/<label>.json")
    rf.add_argument("--delta", action="append", required=True,
                    help="damage numbers seen (37,41,12); sign ignored unless --signed")
    rf.add_argument("--signed", action="store_true", help="take deltas as given (+N = value grew)")
    rf.add_argument("--width", type=int, default=2, choices=(1, 2, 4))
    rf.add_argument("--aligned", action="store_true")
    rf.add_argument("--min-before", type=int, default=None)
    rf.add_argument("--max-hits", type=int, default=60)
    rf.add_argument("--intersect", action="append", default=None,
                    help="another ramdiff .json, as FILE=37,41,12 with that round's own numbers (or bare FILE to reuse "
                         "its last stored query); repeatable -- only cells matching in EVERY file survive")
    rf.set_defaults(fn=cmd_ramfilter)

    n = sub.add_parser("name", help="upsert one row in names/functions.toml (dry run without --apply)")
    n.add_argument("func", help="function entry PC (KSEG0 or physical)")
    n.add_argument("name")
    n.add_argument("--args", default="", help="comma-separated parameter names, a0..a3 order")
    n.add_argument("--status", default=None, choices=(None, "hypothesis", "evidence", "verified"))
    n.add_argument("--evidence", default=None, help="appended to any existing evidence")
    n.add_argument("--overlay", default=None, help="overlay md5 (required in a mixed band)")
    n.add_argument("--force", action="store_true", help="rename an existing row")
    n.add_argument("--apply", action="store_true")
    n.set_defaults(fn=cmd_name)

    t = sub.add_parser("tree", help="print a capture as an indented call forest")
    t.add_argument("file")
    t.add_argument("--max-depth", type=int, default=None)
    t.add_argument("--top", type=int, default=None, help="only the first N roots")
    t.set_defaults(fn=cmd_tree)

    d = sub.add_parser("diff", help="set difference / intersection of two captures")
    d.add_argument("a")
    d.add_argument("b")
    d.add_argument("--prefix", action="store_true", help="also print the longest common entry prefix")
    d.set_defaults(fn=cmd_diff)

    v = sub.add_parser("venn", help="function membership across N captures (which command paths share what)")
    v.add_argument("files", nargs="+")
    v.add_argument("--all", action="store_true", help="also list functions present in every capture")
    v.set_defaults(fn=cmd_venn)
    p = sub.add_parser("propose", help="upsert hypothesis rows for the common prefix into names/functions.toml")
    p.add_argument("files", nargs="+")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--name-prefix", default="CommonPrefix")
    p.add_argument("--overlay", default=None, help="force the overlay md5 (mixed band, human decided)")
    p.set_defaults(fn=cmd_propose)

    a = ap.parse_args()
    files = getattr(a, "files", None)
    if files:
        # Windows shells do not expand globs.
        expanded = []
        for f in files:
            expanded.extend(sorted(glob.glob(f)) or [f])
        a.files = expanded
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
