#!/usr/bin/env python3
"""Resolve the runtime's per-PC occupant fingerprint (dirty_ram_stats.per_pc
`occ_crc` / `occ_ok`, psxrecomp feat/dirty-pc-enrichment) back to the compiled
static-overlay variant, its source .EMI section and its function.

The runtime validates static overlays PER FUNCTION (or per interior fragment):
every row of the dispatch table in generated/overlays_static.c is
{ranges, count, crc, symbol}, and the symbol names the band, the source
section's crc32 and the function:  ov_001F6C00_A6809668_DBD46A34_func_801F6CAC
(band 0x801F6C00, section crc32 0xA6809668 = SCENA18.EMI, func 0x801F6CAC) or
ov_frag_001F6C00_1E5EE588_801F6C90_func_801F6C90 (an interior fragment).  So
`occ_crc` is a function-level CRC, not a section CRC; joining it needs the
table.  This tool parses the table once (cached in analysis/static_variants.json,
keyed by the .c file's mtime) and annotates any per_pc-shaped rows.

  python tools/occ_resolve.py analysis/observed_interp_pcs.json          # harvest rows
  python tools/occ_resolve.py build-enrich/probe3_dirty_ram_stats.json   # a raw dump
  python tools/occ_resolve.py FILE --json-out annotated.json

Reading a row:  occ_ok=1  -> interior gap inside live native code (alias seed)
                occ_ok=0  -> the spanning compiled piece is resident but CRC-
                             missing: it was compiled from ANOTHER section's
                             bytes (the `section` column says which), or the
                             bytes are rewritten at run time.  No seed helps;
                             the resident section needs its own piece.
                0x00000000 -> nothing compiled spans the PC (BIOS/kernel/boot).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATIC_C = ROOT / "generated" / "overlays_static.c"
CACHE = ROOT / "analysis" / "static_variants.json"
CAPTURES = ROOT / "analysis" / "overlay_captures_all.json"

RANGES_RE = re.compile(r"static const uint32_t psx_ov_static_ranges_(\d+)\[\] = \{ ([^}]*) \};")
ROW_RE = re.compile(r"\{ psx_ov_static_ranges_(\d+), (\d+)u, 0x([0-9A-Fa-f]+)u, (ov_\w+) \}")
SYM_RE = re.compile(r"^ov_(frag_)?([0-9A-F]{8})_([0-9A-F]{8})_(?:([0-9A-F]{8})_)?(?:[0-9A-F]{8}_)?func_([0-9A-F]{8})$")


def build_index(static_c=STATIC_C, cache=CACHE):
    mtime = os.path.getmtime(static_c)
    if cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("mtime") == mtime and d.get("source") == str(static_c):
                return d["variants"]
        except Exception:  # noqa: BLE001
            pass
    text = static_c.read_text(encoding="utf-8", errors="replace")
    ranges = {}
    for m in RANGES_RE.finditer(text):
        vals = [int(x.strip().rstrip("u"), 0) for x in m.group(2).split(",") if x.strip()]
        ranges[m.group(1)] = vals
    variants = []
    for m in ROW_RE.finditer(text):
        rid, count, crc, sym = m.group(1), int(m.group(2)), int(m.group(3), 16), m.group(4)
        vals = ranges.get(rid)
        if not vals:
            continue
        pairs = [(vals[i] & 0x1FFFFFFF, vals[i + 1]) for i in range(0, min(len(vals), 2 * count), 2)]
        lo = min(p[0] for p in pairs)
        hi = max(p[0] + p[1] for p in pairs)
        sm = SYM_RE.match(sym)
        variants.append({
            "crc": "0x%08X" % crc,
            "lo": "0x%08X" % lo,
            "hi": "0x%08X" % hi,
            "ranges": ["0x%08X+0x%X" % p for p in pairs],
            "sym": sym,
            "frag": bool(sm and sm.group(1)),
            "band": ("0x%08X" % (int(sm.group(2), 16) | 0x80000000)) if sm else None,
            "section_crc": ("0x%s" % sm.group(3)) if sm else None,
            "func": ("0x%s" % sm.group(5)) if sm else None,
        })
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps({"source": str(static_c), "mtime": mtime, "variants": variants}), encoding="utf-8")
    return variants


def load_captures():
    if not CAPTURES.exists():
        return {}
    caps = json.load(open(CAPTURES, encoding="utf-8"))
    out = {}
    for c in caps:
        out[c["crc32"].upper()] = {"file": c["source_file"], "load_addr": c["load_addr"],
                                   "md5": c.get("source_md5")}
    return out


class Resolver:
    def __init__(self):
        self.variants = build_index()
        self.by_crc = defaultdict(list)
        for v in self.variants:
            self.by_crc[v["crc"].upper()].append(v)
        self.caps = load_captures()

    def resolve(self, pc, occ_crc):
        """-> list of matching variants (usually one; several when identical
        code was compiled from more than one section)."""
        if not occ_crc or int(occ_crc, 16) == 0:
            return []
        phys = int(pc, 16) & 0x1FFFFFFF
        hits = []
        for v in self.by_crc.get(occ_crc.upper(), []):
            if int(v["lo"], 16) <= phys < int(v["hi"], 16):
                hits.append(v)
        return hits

    def section_name(self, section_crc):
        c = self.caps.get((section_crc or "").upper().replace("0X", "0x"))
        if not c:
            c = self.caps.get((section_crc or "").upper())
        return c["file"].rsplit("/", 1)[-1] if c else None


def rows_from(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "per_pc" in d:
        return d["per_pc"]
    if isinstance(d, dict) and "rows" in d:
        return d["rows"]
    if isinstance(d, dict) and "pcs" in d:
        return d["pcs"]
    if isinstance(d, list):
        return d
    # harvest file: {pc_key: row}
    return [dict(v, pc=v.get("pc", k)) for k, v in d.items() if isinstance(v, dict)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="dirty_ram_stats dump or analysis/observed_interp_pcs.json")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--all", action="store_true", help="include rows with entries == 0")
    a = ap.parse_args()
    r = Resolver()
    print("%d static variants indexed from %s" % (len(r.variants), STATIC_C.name))
    rows = rows_from(a.file)
    if not a.all:
        rows = [x for x in rows if int(x.get("entries", 0)) > 0]
    annotated = []
    by_section = defaultdict(lambda: Counter())
    for x in rows:
        pc = x.get("pc")
        occ = x.get("occ_crc")
        ok = x.get("occ_ok")
        hits = r.resolve(pc, occ) if pc else []
        secs = sorted({h["section_crc"] for h in hits if h["section_crc"]})
        names = [r.section_name(s) or s for s in secs]
        funcs = sorted({h["sym"] for h in hits})
        y = dict(x)
        y["occ_sections"] = names
        y["occ_funcs"] = funcs
        annotated.append(y)
        key = ", ".join(names) if names else ("(none)" if not occ or int(occ, 16) == 0 else "(crc not in table)")
        by_section[key]["rows"] += 1
        by_section[key]["entries"] += int(x.get("entries", 0))
        by_section[key]["ok" if ok else "stale"] += 1
    print("\n%-34s %6s %10s %5s %5s" % ("compiled piece from", "rows", "entries", "ok", "stale"))
    for k, c in sorted(by_section.items(), key=lambda kv: -kv[1]["entries"]):
        print("%-34s %6d %10d %5d %5d" % (k[:34], c["rows"], c["entries"], c["ok"], c["stale"]))
    print("\nhottest rows:")
    for y in sorted(annotated, key=lambda z: -int(z.get("entries", 0)))[:25]:
        occ = y.get("occ_crc") or "-"
        print("  pc=%s entries=%-7s occ=%s ok=%s  %s  %s  ra=%s" % (
            y.get("pc"), y.get("entries"), occ, y.get("occ_ok", "-"),
            ",".join(y["occ_sections"]) or "-",
            ",".join(f.split("_func_")[0] for f in y["occ_funcs"])[:40] or "-",
            y.get("ext_ra", "-")))
    if a.json_out:
        json.dump(annotated, open(a.json_out, "w", encoding="utf-8"), indent=1)
        print("\nwrote %s" % a.json_out)


if __name__ == "__main__":
    main()
