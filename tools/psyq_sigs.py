#!/usr/bin/env python3
"""Psy-Q library signatures -> boot-EXE names (docs/NAME_MAP.md route 2).

Matches the whole-object-file signatures from lab313ru/psx_psyq_signatures
(one JSON per LIB per SDK version: hex machine code with `??` where the linker
patched a relocation, plus the labels inside the object) against the text of
the disc boot EXE.  A hit is a whole object file's code found byte-for-byte
under the wildcard mask, so every global label inside it names a function at
once and false positives are negligible.

  python tools/psyq_sigs.py scan                 # every version: objs / funcs matched
  python tools/psyq_sigs.py scan --version 400   # one version, list the matches
  python tools/psyq_sigs.py apply --version 400  # append [[func]] rows to symbols.toml
  python tools/psyq_sigs.py apply --version 400 --dry-run

Defaults: EXE = disc/SLPS_009.90 (PS-EXE header, t_addr from the header),
signatures = ../psx_psyq_signatures next to this repo (or $PSYQ_SIGS).
Writes analysis/psyq_matches.json on every scan.  Never hand-edit
psx_symbols.h: `apply` is followed by `python tools/sync_symbols.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import struct
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEF_EXE = ROOT / "disc" / "SLPS_009.90"
DEF_SIGS = pathlib.Path(os.environ.get("PSYQ_SIGS", ROOT.parent / "psx_psyq_signatures"))
OUT = ROOT / "analysis" / "psyq_matches.json"
SYMBOLS = ROOT / "symbols.toml"

# labels the generator emits for local branch targets / data, never functions
LOCAL = re.compile(r"^(loc|text|data|bss|sbss|sdata|rdata|off|jpt|def|ctor|dtor)_[0-9A-Fa-f]+$")
MIN_FIXED = 32   # fixed bytes an object needs to count on its own
MIN_ANCHOR = 12  # bytes of consecutive non-wildcard code needed to seed a search


def load_exe(path: pathlib.Path):
    d = path.read_bytes()
    if d[:8] != b"PS-X EXE":
        sys.exit(f"{path}: not a PS-X EXE")
    t_addr = struct.unpack_from("<I", d, 0x18)[0]
    t_size = struct.unpack_from("<I", d, 0x1C)[0]
    text = d[0x800:0x800 + t_size]
    return t_addr, text


def parse_sig(sig: str):
    toks = sig.split()
    pat = bytearray(len(toks))
    mask = bytearray(len(toks))  # 1 = must match
    for i, t in enumerate(toks):
        if t == "??":
            continue
        pat[i] = int(t, 16)
        mask[i] = 1
    return bytes(pat), bytes(mask)


def best_anchor(pat: bytes, mask: bytes):
    """Longest run of fixed bytes; returns (offset, bytes) or None."""
    best = (0, 0)
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 1
    if best[1] - best[0] < MIN_ANCHOR:
        return None
    return best[0], pat[best[0]:best[1]]


def verify(text: bytes, at: int, pat: bytes, mask: bytes) -> bool:
    if at < 0 or at + len(pat) > len(text):
        return False
    seg = text[at:at + len(pat)]
    for i in range(len(pat)):
        if mask[i] and seg[i] != pat[i]:
            return False
    return True


def scan_version(text: bytes, t_addr: int, vdir: pathlib.Path):
    """-> list of matches: {lib, obj, version, addr, size, labels:[(name, addr)]}"""
    matches = []
    for jf in sorted(vdir.glob("*.json")):
        if jf.name == "patches.json":
            continue
        try:
            objs = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! {jf}: {e}", file=sys.stderr)
            continue
        for o in objs:
            sig = o.get("sig") or ""
            if not sig:
                continue
            pat, mask = parse_sig(sig)
            if len(pat) < 16:
                continue
            anc = best_anchor(pat, mask)
            if anc is None:
                continue
            aoff, abytes = anc
            start = 0
            while True:
                hit = text.find(abytes, start)
                if hit < 0:
                    break
                at = hit - aoff
                if verify(text, at, pat, mask):
                    labels = []
                    for lb in o.get("labels", []):
                        nm = lb["name"]
                        off = lb["offset"]
                        if LOCAL.match(nm) or off % 4 or off >= len(pat):
                            continue
                        labels.append((nm, t_addr + at + off))
                    matches.append({
                        "lib": jf.name.replace(".json", ""),
                        "obj": o["name"],
                        "version": vdir.name,
                        "addr": t_addr + at,
                        "size": len(pat),
                        "fixed_bytes": sum(mask),
                        "labels": labels,
                    })
                start = hit + 1
    return matches


def dedupe(matches):
    """The same object file often ships unchanged across SDK versions; keep
    one row per (addr, obj) and remember every version that agreed."""
    by = {}
    for m in matches:
        k = (m["addr"], m["obj"], m["lib"])
        if k in by:
            by[k]["versions"].append(m["version"])
        else:
            m = dict(m)
            m["versions"] = [m.pop("version")]
            by[k] = m
    return sorted(by.values(), key=lambda m: m["addr"])


def prune(dd):
    """Largest objects win: a match whose span overlaps an already accepted
    match of a *different* object is dropped (16-byte stubs like COMB_3 /
    DMYNOT1 / SMP_12 match inside real objects).  Also drop stubs under
    MIN_FIXED fixed bytes that stand alone -- too little code to trust."""
    acc = []
    # distinct addresses per object (the same OBJ is listed by several LIBs)
    placements = Counter(obj for obj, _ in {(m["obj"], m["addr"]) for m in dd})
    for m in sorted(dd, key=lambda m: (-m["fixed_bytes"], m["addr"])):
        lo, hi = m["addr"], m["addr"] + m["size"]
        clash = any(lo < b["addr"] + b["size"] and b["addr"] < hi and b["obj"] != m["obj"] for b in acc)
        # A wildcard-free object is exact machine code and may be small: the
        # LIBAPI BIOS thunks (li t2,0xA0/B0/C0; jr t2; li t1,N) are 16 bytes
        # and unique per call number, and they name rand / printf / open ...
        # -- but only when the bytes occur ONCE in the EXE (VM_VIB.OBJ is two
        # `jr ra; nop` stubs and matched six unrelated places).
        exact = m["fixed_bytes"] == m["size"] and m["size"] >= 16 and placements[m["obj"]] == 1
        if clash or (m["fixed_bytes"] < MIN_FIXED and not exact):
            continue
        acc.append(m)
    return sorted(acc, key=lambda m: m["addr"])


def cmd_scan(a):
    t_addr, text = load_exe(a.exe)
    versions = [a.version] if a.version else sorted(
        p.name for p in a.sigs.iterdir() if p.is_dir() and p.name.isdigit())
    per_version = {}
    allm = []
    for v in versions:
        ms = scan_version(text, t_addr, a.sigs / v)
        funcs = sum(len(m["labels"]) for m in ms)
        libs = Counter(m["lib"] for m in ms)
        per_version[v] = {"objs": len(ms), "funcs": funcs, "libs": dict(libs)}
        allm += ms
        print(f"{v:>5}: {len(ms):3d} objs  {funcs:4d} named functions  "
              + " ".join(f"{k.replace('.LIB','')}={n}" for k, n in sorted(libs.items())))
    dd = prune(dedupe(allm))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"exe": str(a.exe), "t_addr": t_addr, "per_version": per_version,
                               "matches": dd}, indent=1), encoding="utf-8")
    print(f"\n{len(dd)} object placements after pruning, "
          f"{sum(len(m['labels']) for m in dd)} named functions -> {OUT}")
    bylib = defaultdict(Counter)
    for m in dd:
        for v in m["versions"]:
            bylib[m["lib"]][v] += 1
    for lib, c in sorted(bylib.items()):
        print(f"  {lib:12s} " + " ".join(f"{v}:{n}" for v, n in sorted(c.items())))
    if a.version:
        for m in dd:
            print(f"\n{m['lib']} {m['obj']} @ 0x{m['addr']:08X} ({m['size']} B, {m['fixed_bytes']} fixed)")
            for nm, ad in m["labels"]:
                print(f"    0x{ad:08X} {nm}")
    # overlap check: two different objects claiming the same bytes
    spans = sorted((m["addr"], m["addr"] + m["size"], m["obj"]) for m in dd)
    for (s1, e1, o1), (s2, e2, o2) in zip(spans, spans[1:]):
        if s2 < e1 and o1 != o2:
            print(f"  ! overlap {o1} [{s1:08X}-{e1:08X}) vs {o2} [{s2:08X}-{e2:08X})")


def existing_pcs():
    import tomllib
    data = tomllib.loads(SYMBOLS.read_text(encoding="utf-8"))
    pcs, names = {}, set()
    for f in data.get("func", []):
        pc = f["pc"] if isinstance(f["pc"], int) else int(f["pc"], 0)
        pcs[pc] = f["name"]
        names.add(f["name"])
    return pcs, names


def cmd_apply(a):
    t_addr, text = load_exe(a.exe)
    versions = [a.version] if a.version else sorted(
        p.name for p in a.sigs.iterdir() if p.is_dir() and p.name.isdigit())
    allm = []
    for v in versions:
        allm += scan_version(text, t_addr, a.sigs / v)
    ms = prune(dedupe(allm))
    pcs, names = existing_pcs()
    rows, skipped, renamed = [], [], []
    seen_pc = set()
    for m in ms:
        for nm, ad in m["labels"]:
            if ad in pcs:
                skipped.append((ad, nm, pcs[ad]))
                continue
            if ad in seen_pc:
                continue
            cname = re.sub(r"[^A-Za-z0-9_]", "_", nm)
            if not re.match(r"[A-Za-z_]", cname):
                cname = "_" + cname
            base = cname
            k = 2
            while cname in names:
                cname = f"{base}_{k}"
                k += 1
            if cname != nm:
                renamed.append((nm, cname))
            names.add(cname)
            seen_pc.add(ad)
            vers = "/".join(m["versions"])
            lib, obj, oaddr, size, fixed = m["lib"], m["obj"], m["addr"], m["size"], m["fixed_bytes"]
            note = (f"Psy-Q {lib} {obj} +0x{ad - oaddr:X}: whole-object signature match "
                    f"(lab313ru/psx_psyq_signatures {vers}, object at 0x{oaddr:08X}, {size} B, "
                    f"{fixed} fixed bytes) -- tools/psyq_sigs.py apply {a.version or 'all'}")
            rows.append("".join([
                "\n[[func]]\n",
                "pc = 0x%08X\n" % ad,
                'name = "%s"\n' % cname,
                "emit = false\n",
                'status = "confirmed"\n',
                'note = "%s"\n' % note,
            ]))
    print(f"{len(rows)} new rows, {len(skipped)} already named, {len(renamed)} renamed for C")
    for ad, nm, have in skipped:
        print(f"  keep 0x{ad:08X} {have}  (Psy-Q says {nm})")
    for nm, c in renamed:
        print(f"  {nm} -> {c}")
    if a.dry_run:
        return
    with SYMBOLS.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n# --- Psy-Q library names, tools/psyq_sigs.py apply --version {a.version} ---\n")
        f.writelines(rows)
    print(f"appended to {SYMBOLS}; now run: python tools/sync_symbols.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", type=pathlib.Path, default=DEF_EXE)
    ap.add_argument("--sigs", type=pathlib.Path, default=DEF_SIGS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--version")
    s.set_defaults(fn=cmd_scan)
    p = sub.add_parser("apply")
    p.add_argument("--version", help="one SDK folder; default: all, largest object wins per span")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_apply)
    a = ap.parse_args()
    if not a.sigs.is_dir():
        sys.exit(f"signature repo not found at {a.sigs} (set $PSYQ_SIGS)")
    a.fn(a)


if __name__ == "__main__":
    main()
