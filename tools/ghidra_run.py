#!/usr/bin/env python
"""Headless Ghidra driver for the BoF3 project (docs/NAME_MAP.md route 2/4,
IDEAS.md I1 "Ghidra is the second route").

    python tools/ghidra_run.py list
    python tools/ghidra_run.py import --source BATTLE.EMI --load-addr 0x801D0C00   # game-mode overlay
    python tools/ghidra_run.py import --source BATTLE.EMI --load-addr 0x80093800   # battle engine
    python tools/ghidra_run.py import --source PLP034 --source MAGIC069 --source BOSS001
    python tools/ghidra_run.py export                        # every program -> analysis/ghidra/<program>.json
    python tools/ghidra_run.py export --program SLPS_009.90 --decompile named
    python tools/ghidra_run.py report BATTLE_EMI3_801D0C00 [--calls-to 0x8015034C]
    python tools/ghidra_run.py merge [--apply] [--symbols]   # Ghidra names -> names/functions.toml (+ symbols.toml)

Everything runs through AnalyzeHeadless via `python -m pyghidra.ghidra_launch`
(analyzeHeadless.bat cannot run .py scripts, and pyghidra.start() in-process
hits a recursion error on this machine, 2026-09-04). The scripts it runs are
in tools/ghidra/. Outputs land in analysis/ghidra/ (gitignored: decompiled
text is derived from the disc); `merge` is the step that writes committable
names.

The Ghidra GUI holds the project lock: close it (or use the ghidra-mcp
bridge instead) before running anything here. The driver refuses to start
while BoF3.lock exists.

Import names programs `<FILE>_EMI<index>_<LOADADDR>` (BATTLE_EMI3_801D0C00)
so the same overlay at two load addresses stays two programs; the md5 that
joins a program back to names/overlays.toml is kept in
analysis/ghidra/<program>.meta.json.
"""
import argparse
import base64
import glob
import json
import os
import re
import subprocess
import sys
import time
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SCRIPTS = os.path.join(TOOLS, "ghidra")
AN = os.path.join(ROOT, "analysis")
OUT = os.path.join(AN, "ghidra")
BIN = os.path.join(OUT, "bin")
CAPTURES_JSON = os.path.join(AN, "overlay_captures_all.json")
FUNCTIONS_TOML = os.path.join(ROOT, "names", "functions.toml")
OVERLAYS_TOML = os.path.join(ROOT, "names", "overlays.toml")
SYMBOLS_TOML = os.path.join(ROOT, "symbols.toml")
BOOT_EXE = os.path.join(ROOT, "disc", "SLPS_009.90")            # PS-X EXE, 0x800 header, text at 0x80093800
BOOT_RANGES = os.path.join(ROOT, "generated", "SLPS_009.90_full.ranges")   # recompiler code-range manifest
BOOT_TEXT = 0x80093800
BOOT_HEADER = 0x800

GHIDRA_DIR = os.environ.get("PSX_GHIDRA_DIR", r"D:\Utilities\ghidra_12.1.3_PUBLIC")
PROJECT_DIR = os.environ.get("PSX_GHIDRA_PROJECT_DIR", r"D:\Utilities\GhidraProjects")
PROJECT = os.environ.get("PSX_GHIDRA_PROJECT", "BoF3")
BOOT_PROGRAM = "SLPS_009.90"
LANG = "MIPS:LE:32:default"

# Load-address bands (docs/OVERLAY_EXTRACTION.md) for classifying references
# that leave an overlay program. Anything else in 0x80093000-0x801F7000 is
# the boot EXE.
BANDS = [
    (0x80093800, 0x800B4004, "battle engine (BATTLE.EMI#15)"),
    (0x800C1800, 0x800C3600, "BOSS"),
    (0x80196800, 0x801CE400, "field"),
    (0x801CE400, 0x801D0C00, "PLCHAR"),
    (0x801D0C00, 0x801EEC00, "game-mode swap slot (BATTLE/SHOP/STATUS/START)"),
    (0x801EEC00, 0x801F2C00, "BMAGIC"),
    (0x801F2C00, 0x801F6C00, "WORLD"),
    (0x801F6C00, 0x80200000, "SCENARIO"),
]
BOOT_LO, BOOT_HI = 0x80093000, 0x801F7000

sys.path.insert(0, TOOLS)
import callstack_diff as cd   # noqa: E402  (TOML read/emit, overlay ranges)


def hx(v):
    return "0x%08X" % (int(v) & 0xFFFFFFFF)


def band_of(addr):
    a = int(addr, 0) if isinstance(addr, str) else int(addr)
    for lo, hi, nm in BANDS:
        if lo <= a < hi:
            return nm
    if BOOT_LO <= a < BOOT_HI:
        return "boot EXE"
    if 0x80000000 <= a < 0x80010000:
        return "kernel/low RAM"
    if 0x80010000 <= a < BOOT_LO:
        return "script/data (0x80010000 section)"
    if 0x1F800000 <= a < 0x1F800400 or 0x9F800000 <= a < 0x9F800400:
        return "scratchpad"
    if 0x1F801000 <= a < 0x1F802000 or 0x9F801000 <= a < 0x9F802000:
        return "MMIO"
    return "other"


# ---------------------------------------------------------------- headless

def check_lock(force):
    lock = os.path.join(PROJECT_DIR, PROJECT + ".lock")
    if os.path.exists(lock) and not force:
        raise SystemExit("%s exists: the Ghidra GUI has the project open. Close it first (or --force if stale)." % lock)


def headless(args, show=("PROG", "EXPORT", "DECOMP", "SEED", "ERROR", "Exception", "REPORT SCRIPT ERROR"),
             verbose=False, timeout=3600):
    cmd = [sys.executable, "-m", "pyghidra.ghidra_launch", "--install-dir", GHIDRA_DIR,
           "ghidra.app.util.headless.AnalyzeHeadless", PROJECT_DIR, PROJECT] + list(args)
    if verbose:
        print("+ " + " ".join(cmd))
    t0 = time.time()
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    lines = p.stdout.splitlines()
    kept = []
    for ln in lines:
        if verbose or any(k in ln for k in show):
            kept.append(ln)
            print(ln)
    if p.returncode != 0:
        print("headless exited %d (%.0fs); last lines:" % (p.returncode, time.time() - t0))
        for ln in lines[-15:]:
            print("  " + ln)
    else:
        print("headless ok (%.0fs)" % (time.time() - t0))
    return p.returncode, lines


# ---------------------------------------------------------------- import

def load_captures():
    if not os.path.exists(CAPTURES_JSON):
        raise SystemExit("%s missing: run the Axis B loop / extract_overlays.py first" % CAPTURES_JSON)
    return json.load(open(CAPTURES_JSON, encoding="utf-8"))


def program_name(c):
    base = c["source_file"].rsplit("/", 1)[-1]
    stem = re.sub(r"\.EMI$", "", base, flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    idx = c.get("source_index")
    la = int(c["load_addr"], 0)
    return "%s_EMI%s_%08X" % (stem, idx if idx is not None else "x", la)


def select_captures(caps, sources, md5s, load_addr):
    out = []
    for c in caps:
        if not c.get("bytes_b64"):
            continue
        ok = False
        for s in sources or []:
            if s.lower() in c["source_file"].lower():
                ok = True
        for m in md5s or []:
            if c["source_md5"].startswith(m.lower()):
                ok = True
        if not ok:
            continue
        if load_addr is not None and int(c["load_addr"], 0) != load_addr:
            continue
        out.append(c)
    return out


def boot_seed(lo_b, hi_b):
    """The boot EXE as memory for an overlay program, so calls into it resolve.

    Without it every overlay decompile is cut off at the first `jal` into the
    boot EXE: the callee has no memory, Ghidra treats the call as no-return,
    and the body after it (the whole damage formula after `Rand()`,
    2026-09-05) silently disappears from the C. The seed carries the code
    ranges the recompiler proved (`generated/SLPS_009.90_full.ranges`, `R`
    lines), clipped around the overlay's own load range because overlays land
    in the boot image's zero-fill, plus the function entries (`F` lines) and
    the names in symbols.toml. seed_overlay.py turns them into `boot_*`
    blocks; export_program.py keeps those out of the overlay's own function
    list and still reports references into them as external."""
    if not (os.path.exists(BOOT_EXE) and os.path.exists(BOOT_RANGES)):
        print("boot seed: skipped (%s / %s missing) -- decompiles will truncate at boot-EXE calls"
              % (BOOT_EXE, BOOT_RANGES))
        return None
    ranges, entries = [], []
    with open(BOOT_RANGES, encoding="utf-8") as fh:
        for line in fh:
            t = line.split()
            if len(t) == 3 and t[0] == "R":
                lo, ln = int(t[1], 16) | 0x80000000, int(t[2], 16)
                for a, b in ((lo, min(lo + ln, lo_b)), (max(lo, hi_b), lo + ln)):
                    if b > a:
                        ranges.append([hx(a), b - a])
            elif len(t) == 2 and t[0] == "F":
                e = int(t[1], 16) | 0x80000000
                if not (lo_b <= e < hi_b):
                    entries.append(hx(e))
    names = {}
    with open(SYMBOLS_TOML, "rb") as fh:
        for r in tomllib.load(fh).get("func", []):
            pc = int(r["pc"]) | 0x80000000
            if not (lo_b <= pc < hi_b):
                names[hx(pc)] = r["name"]
    # The manifest repeats an R line per F line and adjacent ranges abut;
    # coalesce so each byte lands in exactly one block.
    merged = []
    for lo, ln in sorted((int(a, 0), n) for a, n in ranges):
        if merged and lo <= merged[-1][0] + merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], lo + ln - merged[-1][0])
        else:
            merged.append([lo, ln])
    ranges = [[hx(lo), ln] for lo, ln in merged]
    return {"exe": BOOT_EXE, "header": BOOT_HEADER, "text": hx(BOOT_TEXT),
            "ranges": ranges, "entries": sorted(set(entries)), "names": names}


def traced_entries(lo, hi):
    """Distinct `func` values (KSEG0) inside [lo, hi) across every callstack
    capture in analysis/callstacks/ -- entry stamps of compiled functions."""
    out = set()
    for p in glob.glob(os.path.join(AN, "callstacks", "*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("schema") != "callstack-diff-v1":
            continue
        for e in d.get("entries", []):
            f = int(e["func"], 0)
            if lo <= f < hi:
                out.add(hx(f))
    return out


def cmd_import(a):
    check_lock(a.force)
    caps = load_captures()
    la = int(a.load_addr, 0) if a.load_addr else None
    sel = select_captures(caps, a.source, a.md5, la)
    if not sel:
        raise SystemExit("no captured overlay matches (--source substring of source_file, --md5 prefix, --load-addr)")
    if len(sel) > 1 and not a.all:
        print("%d overlays match; pass --all to import every one, or narrow with --load-addr / --md5:" % len(sel))
        for c in sel:
            print("  %s %s %s %6d B  md5 %s" % (program_name(c), c["source_file"], c["load_addr"],
                                                int(c["size"]), c["source_md5"][:12]))
        return 1
    os.makedirs(BIN, exist_ok=True)
    rc_all = 0
    for c in sel:
        pn = program_name(c)
        bin_path = os.path.join(BIN, pn)
        with open(bin_path, "wb") as fh:
            fh.write(base64.b64decode(c["bytes_b64"]))
        # Entry PCs the fn-entry ring actually stamped in the callstack captures
        # are compiled-function entries by construction; several (0x801DD56C,
        # the EXP tick) are missing from the static roots and Ghidra otherwise
        # never gets a function there.
        lo_b, hi_b = int(c["load_addr"], 0), int(c["load_addr"], 0) + int(c["size"])
        traced = traced_entries(lo_b, hi_b)
        static = {hx(int(x, 0)) for x in (c.get("static_discovery_entry_pcs") or [])}
        extra = {hx(int(x, 0)) for x in (a.start or []) if lo_b <= int(x, 0) < hi_b}
        seed = {"name": pn, "label_prefix": "ov",
                "starts": sorted(static | traced | extra),
                "traced_extra": sorted(traced - static),
                "interior": [hx(int(x, 0)) for x in (c.get("dispatch_entry_pcs") or [])
                             if hx(int(x, 0)) not in {hx(int(y, 0)) for y in (c.get("static_discovery_entry_pcs") or [])}]}
        if not a.no_boot:
            seed["boot"] = boot_seed(lo_b, hi_b)
        seed_path = os.path.join(OUT, pn + ".seed.json")
        with open(seed_path, "w", encoding="utf-8") as fh:
            json.dump(seed, fh, indent=1)
        meta = {"program": pn, "source_file": c["source_file"], "source_index": c.get("source_index"),
                "load_addr": c["load_addr"], "size": int(c["size"]), "source_md5": c["source_md5"],
                "crc32": c.get("crc32"), "imported_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(os.path.join(OUT, pn + ".meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        print("== import %s  (%s @ %s, %d B, %d starts [%d from traces only], %d interior)" % (
            pn, c["source_file"], c["load_addr"], meta["size"], len(seed["starts"]),
            len(seed["traced_extra"]), len(seed["interior"])))
        args = ["-import", bin_path, "-loader", "BinaryLoader", "-loader-baseAddr", c["load_addr"],
                "-processor", LANG, "-cspec", "default",
                "-scriptPath", SCRIPTS,
                "-preScript", "seed_overlay.py", seed_path,
                "-postScript", "export_program.py", OUT, a.decompile or ""]
        if a.overwrite:
            args.append("-overwrite")
        if a.no_analysis:
            args.append("-noanalysis")
        rc, _ = headless(args, verbose=a.verbose)
        rc_all |= rc
    return rc_all


# ---------------------------------------------------------------- list / export

def cmd_list(a):
    check_lock(a.force)
    rc, _ = headless(["-process", BOOT_PROGRAM, "-noanalysis", "-readOnly",
                      "-scriptPath", SCRIPTS, "-postScript", "list_programs.py"], verbose=a.verbose)
    metas = sorted(glob.glob(os.path.join(OUT, "*.meta.json")))
    if metas:
        print("overlay programs with metadata (analysis/ghidra/*.meta.json):")
        for m in metas:
            d = json.load(open(m, encoding="utf-8"))
            print("  %-28s %s @ %s md5 %s" % (d["program"], d["source_file"], d["load_addr"], d["source_md5"][:12]))
    return rc


def cmd_export(a):
    check_lock(a.force)
    os.makedirs(OUT, exist_ok=True)
    progs = a.program or [None]
    rc_all = 0
    for p in progs:
        args = ["-process"] + ([p] if p else []) + ["-recursive", "-noanalysis", "-readOnly",
                                                   "-scriptPath", SCRIPTS,
                                                   "-postScript", "export_program.py", OUT, a.decompile or ""]
        rc, _ = headless(args, verbose=a.verbose)
        rc_all |= rc
    return rc_all


# ---------------------------------------------------------------- report

def load_export(name):
    p = os.path.join(OUT, name + ".json")
    if not os.path.exists(p):
        p2 = glob.glob(os.path.join(OUT, name + "*.json"))
        p2 = [x for x in p2 if not x.endswith((".meta.json", ".seed.json"))]
        if len(p2) == 1:
            p = p2[0]
        else:
            raise SystemExit("no export %s (run: ghidra_run.py export --program %s)" % (p, name))
    return json.load(open(p, encoding="utf-8"))


def cmd_report(a):
    d = load_export(a.program)
    fs = d["functions"]
    names = cd.known_names()
    nm = lambda e: names.get(e, "")
    print("%s  base %s  %d functions (%d named by Ghidra, %d named in names/), %d cop2 (GTE) functions, %d with jalr"
          % (d["program"], d["image_base"], len(fs), d["named_count"],
             sum(1 for f in fs if nm(f["entry"])), sum(1 for f in fs if f["cop2"]),
             sum(1 for f in fs if f["jalr"])))
    print("blocks: " + ", ".join("%s %s-%s" % (b["name"], b["start"], b["end"]) for b in d["blocks"]))

    print("\n== largest functions (size, insns, stores, cop2, callees, ext calls)")
    for f in sorted(fs, key=lambda f: -f["size"])[:a.top]:
        print("  %s %-26s %6d B %5d i %4d st %s  callees %3d  ext %3d  %s" % (
            f["entry"], (f["name"] if f["source"] != "DEFAULT" else "") or nm(f["entry"]) or "-",
            f["size"], f["insns"], f["stores"], "GTE" if f["cop2"] else "   ",
            len(f["callees"]), len(f["ext_calls"]), f["proto"][:50]))

    print("\n== rules-vs-draw split: functions with stores and NO cop2 (candidates for game logic)")
    logic = [f for f in fs if f["stores"] and not f["cop2"]]
    print("  %d of %d; top by stores:" % (len(logic), len(fs)))
    for f in sorted(logic, key=lambda f: -f["stores"])[:a.top]:
        print("  %s %-26s %4d stores %4d loads %5d insns" % (
            f["entry"], f["name"] if f["source"] != "DEFAULT" else (nm(f["entry"]) or "-"),
            f["stores"], f["loads"], f["insns"]))

    print("\n== most-written in-program globals (data anchors)")
    gl = sorted(d["globals"].items(), key=lambda kv: -(kv[1]["w"] * 4 + kv[1]["r"]))
    for addr, g in gl[:a.top]:
        print("  %s  w%-4d r%-4d by %d fn: %s" % (addr, g["w"], g["r"], len(g["funcs"]), ", ".join(g["funcs"][:5])))

    print("\n== references leaving the program, by band")
    by_band = {}
    for addr, e in d["ext_targets"].items():
        by_band.setdefault(band_of(addr), []).append((addr, e))
    for band, lst in sorted(by_band.items(), key=lambda kv: -len(kv[1])):
        calls = sum(e["calls"] for _, e in lst)
        data = sum(e["data"] for _, e in lst)
        print("  %-52s %4d targets  %5d calls %5d data" % (band, len(lst), calls, data))
        for addr, e in sorted(lst, key=lambda kv: -(kv[1]["calls"] * 4 + kv[1]["data"]))[:a.ext_top]:
            print("      %s %-24s calls %4d data %4d from %d fn" % (addr, nm(addr) or "", e["calls"], e["data"], len(e["funcs"])))

    # The boot-EXE program's memory block spans the overlay bands, so its
    # calls into them are in-program callees, not ext_targets: split those
    # by band here (the game-mode dispatcher, the actor entry vectors).
    band_calls = {}
    for f in fs:
        for c in f["callees"]:
            b = band_of(c)
            if b != "boot EXE" and b != band_of(f["entry"]):
                band_calls.setdefault(b, {}).setdefault(c, set()).add(f["entry"])
    if band_calls:
        print("\n== in-program calls that cross a band boundary (callers of overlay slots)")
        for band, tg in sorted(band_calls.items(), key=lambda kv: -len(kv[1])):
            print("  %-52s %d targets" % (band, len(tg)))
            for c, callers in sorted(tg.items(), key=lambda kv: -len(kv[1]))[:a.ext_top]:
                print("      %s %-24s from %s%s" % (c, nm(c), ", ".join(sorted(callers)[:4]),
                                                    " ..." if len(callers) > 4 else ""))

    print("\n== jump tables: %d (interior entry points for Axis B)" % len(d["jump_tables"]))
    for jt in d["jump_tables"][:a.top]:
        print("  %s in %s -> %d targets %s%s" % (jt["at"], jt["func"], len(jt["targets"]),
                                                 " ".join(jt["targets"][:6]), " ..." if len(jt["targets"]) > 6 else ""))

    if a.calls_to:
        tgt = hx(int(a.calls_to, 0))
        print("\n== call sites of %s with a constant a0 (message index / mode id anchors)" % tgt)
        for cs in sorted((c for c in d["call_sites"] if c["to"] == tgt), key=lambda c: c["a0"]):
            print("  a0=%-6d at %s in %s %s" % (cs["a0"], cs["from"], cs["func"], nm(cs["func"])))
    else:
        tops = {}
        for cs in d["call_sites"]:
            tops[cs["to"]] = tops.get(cs["to"], 0) + 1
        print("\n== call targets most often called with a constant a0 (try --calls-to)")
        for to, n in sorted(tops.items(), key=lambda kv: -kv[1])[:10]:
            print("  %s %-24s x%d" % (to, nm(to), n))
    return 0


# ---------------------------------------------------------------- merge

def cmd_merge(a):
    exports = [p for p in glob.glob(os.path.join(OUT, "*.json"))
               if not p.endswith((".meta.json", ".seed.json"))]
    if not exports:
        raise SystemExit("nothing exported yet (analysis/ghidra/*.json)")
    known_overlays = set()
    if os.path.exists(OVERLAYS_TOML):
        with open(OVERLAYS_TOML, "rb") as f:
            known_overlays = {r["md5"] for r in tomllib.load(f).get("overlay", [])}
    header, rows = cd.read_functions_toml()
    existing = {(r["overlay"], int(r["pc"])): r for r in rows}
    added = touched = skipped = 0
    sym_rows = []
    for p in exports:
        d = json.load(open(p, encoding="utf-8"))
        meta_p = os.path.join(OUT, d["program"] + ".meta.json")
        named = [f for f in d["functions"] if f["source"] != "DEFAULT"
                 and not re.match(r"^(FUN|func|thunk_FUN|ov_entry)_", f["name"])]
        if os.path.exists(meta_p):
            meta = json.load(open(meta_p, encoding="utf-8"))
            md5 = meta["source_md5"]
            if md5 not in known_overlays:
                print("skip %s: overlay %s not in names/overlays.toml (name_map.py init)" % (d["program"], md5[:12]))
                continue
            for f in named:
                pc = int(f["entry"], 0)
                ev = "ghidra %s: %s (%s)" % (d["program"], f["proto"], f["source"])
                key = (md5, pc)
                if key in existing:
                    r = existing[key]
                    if ev not in (r.get("evidence") or ""):
                        r["evidence"] = ((r.get("evidence") or "").rstrip() + (" | " if r.get("evidence") else "") + ev)
                        touched += 1
                    continue
                rows.append({"overlay": md5, "pc": pc, "name": f["name"], "args": [],
                             "status": "hypothesis", "evidence": ev,
                             "note": "ghidra export merge %s" % time.strftime("%Y-%m-%d")})
                existing[key] = rows[-1]
                added += 1
        elif d["program"] == BOOT_PROGRAM:
            for f in named:
                sym_rows.append((int(f["entry"], 0), f["name"], f["proto"], f["source"]))
        else:
            skipped += 1
            print("skip %s: no .meta.json (not imported by this driver)" % d["program"])
    print("names/functions.toml: +%d rows, %d evidence appends%s" % (added, touched, "" if a.apply else " (dry run)"))
    if a.apply and (added or touched):
        rows.sort(key=lambda r: (r["overlay"], int(r["pc"])))
        with open(FUNCTIONS_TOML, "w", encoding="utf-8", newline="\n") as f:
            f.write(cd.emit_functions_toml(header, rows))
        subprocess.run([sys.executable, os.path.join(TOOLS, "name_map.py"), "check"])
    if sym_rows:
        print("symbols.toml: %d Ghidra-named boot-EXE functions%s" % (len(sym_rows), "" if a.symbols else " (pass --symbols to merge)"))
        if a.symbols:
            merge_symbols(sym_rows, a.apply)
    return 0


def merge_symbols(sym_rows, apply):
    """Upsert `[[func]]` rows (framework schema: pc/name/emit/status/note) for
    boot-EXE functions Ghidra has named. emit stays false; status 'guessed'.
    Existing rows keep their name; the Ghidra prototype goes into note."""
    text = open(SYMBOLS_TOML, encoding="utf-8").read() if os.path.exists(SYMBOLS_TOML) else ""
    doc = tomllib.loads(text) if text else {}
    rows = doc.get("func", [])
    by_pc = {int(r["pc"]): r for r in rows}
    header = text.split("[[func]]", 1)[0].rstrip() + "\n" if "[[func]]" in text else text.rstrip() + "\n"
    added = 0
    for pc, name, proto, src in sym_rows:
        if pc in by_pc:
            continue
        rows.append({"pc": pc, "name": name, "emit": False, "status": "guessed",
                     "note": "ghidra %s: %s" % (src, proto)})
        added += 1
    print("symbols.toml: +%d rows%s" % (added, "" if apply else " (dry run)"))
    if not apply or not added:
        return
    rows.sort(key=lambda r: int(r["pc"]))
    out = [header]
    for r in rows:
        out.append("\n[[func]]\n")
        for k, v in r.items():
            if isinstance(v, bool):
                out.append("%s = %s\n" % (k, "true" if v else "false"))
            elif isinstance(v, int):
                out.append("%s = 0x%08X\n" % (k, v) if k == "pc" else "%s = %d\n" % (k, v))
            else:
                out.append("%s = %s\n" % (k, cd._q(v)))
    with open(SYMBOLS_TOML, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))
    subprocess.run([sys.executable, os.path.join(TOOLS, "sync_symbols.py")])


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--verbose", "-v", action="store_true", help="show the whole headless log")
    ap.add_argument("--force", action="store_true", help="ignore the project lock file")
    sub = ap.add_subparsers(dest="cmd", required=True)

    l = sub.add_parser("list", help="programs in the project")
    l.set_defaults(fn=cmd_list)

    i = sub.add_parser("import", help="import overlay section(s) from analysis/overlay_captures_all.json as new programs, seed, analyse, export")
    i.add_argument("--source", action="append", default=None, help="substring of source_file (BATTLE.EMI, PLP034); repeatable")
    i.add_argument("--md5", action="append", default=None, help="source_md5 prefix; repeatable")
    i.add_argument("--load-addr", default=None, help="only this load address (0x801D0C00)")
    i.add_argument("--all", action="store_true", help="import every match instead of listing them")
    i.add_argument("--overwrite", action="store_true", help="replace an existing program of the same name")
    i.add_argument("--no-analysis", action="store_true")
    i.add_argument("--no-boot", action="store_true",
                   help="do not map the boot EXE into the program (decompiles then truncate at every boot-EXE call)")
    i.add_argument("--decompile", default=None, help="all | named | 0x..,0x.. (written next to the export)")
    i.add_argument("--start", action="append", default=None,
                   help="extra function start to seed (repeatable), e.g. a store PC's gap found by callstack_diff writes")
    i.set_defaults(fn=cmd_import)

    e = sub.add_parser("export", help="dump program(s) to analysis/ghidra/<program>.json")
    e.add_argument("--program", action="append", default=None, help="program name (default: every program)")
    e.add_argument("--decompile", default=None, help="all | named | 0x..,0x..")
    e.set_defaults(fn=cmd_export)

    r = sub.add_parser("report", help="summarise one export")
    r.add_argument("program")
    r.add_argument("--top", type=int, default=15)
    r.add_argument("--ext-top", type=int, default=8)
    r.add_argument("--calls-to", default=None, help="list constant-a0 call sites of this target")
    r.set_defaults(fn=cmd_report)

    m = sub.add_parser("merge", help="Ghidra-named functions -> names/functions.toml as hypothesis rows")
    m.add_argument("--apply", action="store_true")
    m.add_argument("--symbols", action="store_true", help="also merge boot-EXE names into symbols.toml")
    m.set_defaults(fn=cmd_merge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
