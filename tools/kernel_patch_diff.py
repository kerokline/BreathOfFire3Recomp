"""Which kernel-RAM words does the game patch at runtime?

Boots the runtime headless, then diffs live kernel RAM against the BIOS
image's boot-time copy (the [[recompiler.address_model.copy]] window that is
kernel_bless = true) and reports every differing word, joined to the
compiled kernel bodies from <stem>_dispatch.c so the output says which
*functions* fail the bless check and therefore run interpreted.

    python tools/kernel_patch_diff.py                       # OpenBIOS, build-relprof
    python tools/kernel_patch_diff.py --at 5 --at 30        # snapshots at t+5s, t+30s
    python tools/kernel_patch_diff.py --no-launch --port 4370   # against a running game

Evidence for an upstream [[recompiler.install_slots]] entry: each reported
word inside a code body is a runtime-installed patch (Rule 18).
"""
import argparse, os, re, struct, subprocess, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=30.0)

def wait_port(port, secs=120):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            r = q("frame", port)
            if r.get("ok") or "frame" in r:
                return time.time() - t0
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("debug port never came up")

def parse_profile(path):
    """Return (rom_path, [(name, rom_lo, ram_lo, length, bless)])."""
    txt = open(path, encoding="utf-8").read()
    rom = re.search(r'^rom\s*=\s*"([^"]+)"', txt, re.M).group(1)
    copies = []
    for m in re.finditer(r'\[\[recompiler\.address_model\.copy\]\](.*?)(?=\n\[|\Z)', txt, re.S):
        blk = m.group(1)
        g = lambda k: re.search(r'^\s*%s\s*=\s*"?([^"\n]+)"?' % k, blk, re.M).group(1).strip()
        rom_lo = int(g("rom_lo"), 16); rom_hi = int(g("rom_hi"), 16)
        ram_lo = int(g("ram_lo"), 16)
        bless = "true" in g("kernel_bless")
        copies.append((g("name"), rom_lo, ram_lo, rom_hi - rom_lo, bless))
    return rom, copies

def parse_bodies(dispatch_c):
    """[(key, body_lo, body_hi)] from the PsxKernelBody table."""
    txt = open(dispatch_c, encoding="utf-8", errors="replace").read()
    m = re.search(r'psx_bios_kernel_bodies\[\d+\]\s*=\s*\{(.*?)\};', txt, re.S)
    if not m:
        return []
    return [(int(a, 16), int(b, 16), int(c, 16)) for a, b, c in
            re.findall(r'\{\s*0x([0-9A-Fa-f]+)u,\s*0x([0-9A-Fa-f]+)u,\s*0x([0-9A-Fa-f]+)u\s*\}', m.group(1))]

def parse_seeds(path):
    """{ram_addr: label} for seeds that land in kernel RAM (ROM-LMA form too)."""
    d = json.load(open(path, encoding="utf-8"))
    rows = d if isinstance(d, list) else (d.get("functions") or d.get("seeds") or [])
    return [(int(r["address"], 16) & 0x1FFFFFFF, r.get("label", "?")) for r in rows if isinstance(r, dict)]

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--exe", default="build-relprof/BreathOfFire3_Recompiled.exe")
    ap.add_argument("--profile", default="psxrecomp/bios/OpenBIOS.toml")
    ap.add_argument("--dispatch", default="psxrecomp/generated/OpenBIOS_dispatch.c")
    ap.add_argument("--seeds", default="psxrecomp/recompiler/seeds/openbios_elf_seeds.json")
    ap.add_argument("--port", type=int, default=4371)
    ap.add_argument("--at", type=float, action="append", default=None,
                    help="seconds after the port is up to snapshot (repeatable; default 8 and 30)")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--bios", default=None, help="BIOS image to launch with (--bios passthrough; default = the runtime's pick, OpenBIOS)")
    ap.add_argument("--out", default="analysis/kernel_patch_diff.json")
    a = ap.parse_args()
    ats = a.at or [8.0, 30.0]

    rom_rel, copies = parse_profile(os.path.join(ROOT, a.profile))
    rom = open(os.path.join(ROOT, "psxrecomp", rom_rel), "rb").read()
    bodies = parse_bodies(os.path.join(ROOT, a.dispatch))
    seeds = parse_seeds(os.path.join(ROOT, a.seeds))
    # map ROM-LMA seeds into RAM for each copy
    ram_names = {}
    for name, rom_lo, ram_lo, ln, bless in copies:
        for addr, label in seeds:
            if rom_lo <= addr < rom_lo + ln:
                ram_names[addr - rom_lo + ram_lo] = label
            elif ram_lo <= addr < ram_lo + ln:
                ram_names[addr] = label
    def fn_of(ram):
        best = [k for k in ram_names if k <= ram]
        return ("%s+0x%X" % (ram_names[max(best)], ram - max(best))) if best else "?"

    proc = None
    if not a.no_launch:
        exe = os.path.join(ROOT, a.exe)
        env = dict(os.environ, PSX_STARVATION_TIMEOUT_US="0")
        env.pop("PSX_LOAD_SLOT", None)
        argv = [exe, "--game", "game.toml", "--no-launcher", "--headless", "--debug-port", str(a.port)]
        if a.bios:
            argv += ["--bios", os.path.join(ROOT, a.bios)]
        proc = subprocess.Popen(argv, cwd=ROOT, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print("launched pid %d" % proc.pid, flush=True)
    t_up = wait_port(a.port)
    print("port up after %.1fs" % t_up, flush=True)
    t0 = time.time()

    report = {"copies": [], "snapshots": []}
    try:
        for at in sorted(ats):
            while time.time() - t0 < at:
                time.sleep(0.5)
            fr = q("frame", a.port)
            kb = q("kernel_bless", a.port)
            snap = {"t": round(time.time() - t0, 1), "frame": fr.get("frame"), "kernel_bless": kb, "diffs": []}
            print("\n=== t+%.0fs frame %s  kernel_bless: %s" % (at, fr.get("frame"),
                  {k: v for k, v in kb.items() if k not in ("id", "ok")}), flush=True)
            for name, rom_lo, ram_lo, ln, bless in copies:
                if not bless:
                    continue  # only the kernel_bless window gates native dispatch
                live = bytes.fromhex(q("read_ram", a.port, addr="0x%08X" % ram_lo, len=ln)["hex"])
                src = rom[rom_lo - 0x1FC00000: rom_lo - 0x1FC00000 + ln]
                words = []
                for off in range(0, ln - 3, 4):
                    if live[off:off + 4] != src[off:off + 4]:
                        ram = ram_lo + off
                        inb = [b for b in bodies if b[1] <= ram < b[2]]
                        words.append({"ram": "0x%04X" % ram, "rom": struct.unpack("<I", src[off:off+4])[0],
                                      "live": struct.unpack("<I", live[off:off+4])[0],
                                      "in_code_body": bool(inb), "fn": fn_of(ram)})
                # collapse runs
                runs = []
                for w in words:
                    r = int(w["ram"], 16)
                    if runs and r == runs[-1]["end"] and runs[-1]["in_code_body"] == w["in_code_body"]:
                        runs[-1]["end"] = r + 4; runs[-1]["n"] += 1
                    else:
                        runs.append({"start": r, "end": r + 4, "n": 1, "in_code_body": w["in_code_body"], "fn": w["fn"]})
                code_words = sum(1 for w in words if w["in_code_body"])
                print("copy %-16s RAM 0x%04X..0x%04X: %d differing words, %d inside compiled code bodies, %d runs"
                      % (name, ram_lo, ram_lo + ln, len(words), code_words, len(runs)), flush=True)
                for r in runs:
                    tag = "CODE" if r["in_code_body"] else "data"
                    print("   %s 0x%04X..0x%04X (%d words)  %s" % (tag, r["start"], r["end"], r["n"], r["fn"]), flush=True)
                    if r["in_code_body"]:
                        for w in words:
                            if r["start"] <= int(w["ram"], 16) < r["end"]:
                                print("        %s rom %08X -> live %08X" % (w["ram"], w["rom"], w["live"]), flush=True)
                snap["diffs"].append({"copy": name, "words": words, "runs": runs})
            report["snapshots"].append(snap)
            # which compiled bodies are now un-runnable?
            dirty = set()
            for s in snap["diffs"]:
                for w in s["words"]:
                    r = int(w["ram"], 16)
                    for key, lo, hi in bodies:
                        if lo <= r < hi:
                            dirty.add((lo, hi))
            if dirty:
                print("compiled kernel bodies containing a patched word (these interpret):", flush=True)
                for lo, hi in sorted(dirty):
                    print("   0x%04X..0x%04X  %s" % (lo, hi, fn_of(lo)), flush=True)
            snap["dirty_bodies"] = ["0x%04X..0x%04X %s" % (lo, hi, fn_of(lo)) for lo, hi in sorted(dirty)]
    finally:
        if proc:
            proc.kill()
    os.makedirs(os.path.dirname(os.path.join(ROOT, a.out)), exist_ok=True)
    json.dump(report, open(os.path.join(ROOT, a.out), "w", encoding="utf-8"), indent=1)
    print("\nwrote", a.out)

if __name__ == "__main__":
    main()
