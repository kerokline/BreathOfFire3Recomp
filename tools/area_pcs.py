#!/usr/bin/env python
"""Static PC census for the per-area code in the `0x801F2C00` world band.

    python tools/area_pcs.py                      # all 200 areas -> analysis/area_pcs.json
    python tools/area_pcs.py --area 27            # one area, printed in full
    python tools/area_pcs.py --items-only         # just the 54 areas that hold something

## Why this exists

The world band is the one band that cannot be attributed by address. 181
distinct area sections all load at `0x801F2C00`, so a PC observed there names
a *slot*, not an occupant -- `analysis/overlay_catalog.json` marks every AREA
overlay `heat_attribution: band-shared(181)`, and
[`band-overlap-attribution.md`](../docs/band-overlap-attribution.md) is the
write-up of why that is not fixable from addresses. Coverage in this band has
to be per-occupant or it is nothing.

This walks each `AREAnnn.EMI`'s `0x801F2C00` section on the disc and emits the
entry PCs *that area* contributes, so a band PC can be tested against the set
of areas that actually contain it, and so the areas reachable from a given
piece of content (say the 122 searchable spots in
[`WORLD_ITEMS.md`](../docs/WORLD_ITEMS.md)) can be turned into a concrete PC
list without playing them.

## Discovery, and how it is checked

Entry discovery is not reimplemented here: it calls `jal_targets` and
`prologue_roots` straight out of `tools/extract_overlays.py`, the same two
functions `tools/overlay_catalog.py` uses to fill each overlay's `roots`. So
the per-area counts are identical to the catalog's by construction, and
`--verify` proves it rather than asserting it (181/181 areas agree on both
counts). The union is the entry set; `both` is the high-confidence core.

Worth knowing if you write your own scan: a `jal` target only counts when it
lands inside the section, and an `addiu $sp, $sp, -N` only opens a function
when it is the section's first word or follows a `jr $ra` delay slot. Drop
that second boundary rule and you over-count by 1,088 entries across the 181
areas -- which is how this tool started.

External `jal` targets are collected too: those are the engine functions the
area's own code calls, named from `symbols.toml` and `names/functions.toml`
where a name exists. That is the other half of "which PCs does this place
need" -- the area section is small, and most of the work happens in GAME.EMI
and the boot EXE.

## The searching path specifically

Searching a spot is entirely engine code, shared by every area -- the area
section only supplies the record array. Those PCs are constant and are printed
by `--chain`; they are exercised by all 54 areas that hold anything.
"""
import argparse
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls
import emi as emilib
import world_items as wi
from extract_overlays import jal_targets, prologue_roots

try:
    import tomllib
except ImportError:                                   # pragma: no cover
    tomllib = None

ROOT = wi.ROOT
BAND = wi.AREA_SECTION_DEST                # 0x801F2C00
GAME_LO, GAME_HI = 0x80196800, 0x801CE0E4  # GAME.EMI #0, the resident field engine

# The search path, from docs/WORLD_ITEMS.md. Constant across every area.
SEARCH_CHAIN = [
    (0x801B3FC0, "Field_SearchSpot",     "GAME.EMI",  "the handler behind the search button"),
    (0x801B6C4C, "Field_FindSearchSpot", "GAME.EMI",  "walks the area's 8-byte record array"),
    (0x801B6E50, "Field_GiveZenny",      "GAME.EMI",  "zenny payout + its message"),
    (0x8015BFC4, "Flag_Test",            "boot EXE",  "has this spot been emptied?"),
    (0x8015BF70, "Flag_Set",             "boot EXE",  "mark it emptied"),
    (0x80166FFC, "Zenny_Add",            "boot EXE",  "credit the zenny"),
    (0x80165AA4, "Inventory_Add",        "boot EXE",  "credit the item"),
    (0x80166720, "(item name pointer)",  "boot EXE",  "name into the message buffer"),
    (0x801503AC, "(message open)",       "boot EXE",  "messages 1 / 2 / 3"),
    (0x8015E908, "(sound cue)",          "boot EXE",  "cue 0x106"),
    (0x8017ED6C, "(sprintf)",            "boot EXE",  "formats the zenny amount"),
]


# ----------------------------------------------------------------- decode

def jal_target(word, pc):
    """The target of a `jal`, or None if this word is not one."""
    if word >> 26 != 0x03:
        return None
    return (pc & 0xF0000000) | ((word & 0x03FFFFFF) << 2)


def data_floor(section, struct_ptr, base=BAND):
    """Where the section stops being code.

    An AREA section is code followed by the area's data tables, and 67 of the
    181 classify `mixed` for exactly that reason. Scanning the tables as
    instructions invents both entry PCs and impossible call targets
    (0x89600000 and friends). The per-area struct the boot table points at
    holds pointers to those tables, so the lowest of them -- and the struct
    itself -- is a principled floor for where data begins.
    """
    end = base + len(section)
    floor = end
    if base <= struct_ptr < end:
        floor = struct_ptr
        so = struct_ptr - base
        for off in range(so, min(so + 0x40, len(section) - 3), 4):
            w, = struct.unpack_from("<I", section, off)
            if base < w < end:
                floor = min(floor, w)
    return floor


def external_calls(section, base=BAND, limit=None):
    """`jal`s that leave the section, counted -- the engine this area calls.

    Bounded by `limit` (the data floor): the area's data tables contain words
    that decode as `jal` and would otherwise invent targets like 0x89600000.
    Entry discovery deliberately does NOT use this bound -- it delegates to
    extract_overlays so the counts stay identical to the catalog's.
    """
    end = base + len(section)
    stop = min(len(section) & ~3, ((limit or end) - base) & ~3)
    external = {}
    for off in range(0, stop, 4):
        t = jal_target(struct.unpack_from("<I", section, off)[0], base + off)
        if t is None or base <= t < end:
            continue
        if 0x80000000 <= t < 0x80200000:
            external[t] = external.get(t, 0) + 1
    return external


# ----------------------------------------------------------------- names

def load_symbol_names():
    """PC -> name, from symbols.toml (boot) and names/functions.toml (overlays)."""
    names = {}
    if tomllib is None:
        return names
    p = os.path.join(ROOT, "symbols.toml")
    if os.path.exists(p):
        for f in tomllib.load(open(p, "rb")).get("func", []):
            if "pc" in f and "name" in f:
                names[int(f["pc"])] = f["name"]
    p = os.path.join(ROOT, "names", "functions.toml")
    if os.path.exists(p):
        d = tomllib.load(open(p, "rb"))
        for f in d.get("func", d.get("function", [])):
            pc = f.get("pc", f.get("addr"))
            if pc is None or "name" not in f:
                continue
            names[int(pc, 16) if isinstance(pc, str) else int(pc)] = f["name"]
    return names


def load_catalog():
    """area id -> the catalog's own static-discovery counts, for the check."""
    p = os.path.join(ROOT, "analysis", "overlay_catalog.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for o in json.load(open(p, encoding="utf-8")).get("overlays", []):
        m = re.fullmatch(r"AREA(\d{3})", o.get("name", ""))
        if m and o.get("load_addr") == "0x%08X" % BAND:
            out[int(m.group(1))] = {"function_count": o.get("function_count"),
                                    "roots": o.get("roots", {}),
                                    "crc32": o.get("crc32"),
                                    "size": o.get("size")}
    return out


def compiled_band_bases():
    """Which overlay bands the current generated/ tree actually compiled."""
    p = os.path.join(ROOT, "generated", "overlays_static.c")
    if not os.path.exists(p):
        return None
    found = set()
    with open(p, "r", errors="replace") as fh:
        for line in fh:
            for m in re.finditer(r"\bov_([0-9A-Fa-f]{8})_", line):
                found.add(int(m.group(1), 16) | 0x80000000)
    return found




# ----------------------------------------------------------------- coverage

def coverage_report(result, build_filter=None):
    """The four-cell ledger: known/unknown x proven/unproven.

    KNOWN  = a static entry of THIS area (jal target or prologue root), so the
             recompiler emits a native function for it.
    PROVEN = the runtime entered it and ran it in the dirty-RAM interpreter.

    The two are near-mutually-exclusive by construction, and that is the whole
    point. A known entry that got compiled runs NATIVELY and therefore can
    never appear in the observed list -- its absence is success, not a gap. So
    `observed_interp_pcs.json` is not a sample of executed code; it is a list
    of DISCOVERY FAILURES, and "known but unproven" is the healthy state
    rather than a backlog to burn down.

    Attribution is per occupant, never by address. `harvest_interp_pcs.py`
    stamps the resident `.EMI` on PCs it newly sees, and only that stamp can
    say which of the 181 occupants of this band a PC belonged to. Matching by
    address instead is actively misleading here: 65 of the 140 band PCs match
    a static root of *some* area, but 0 of the 59 that carry a stamp match a
    root of *their own* area. Those 65 were collisions.
    """
    obs_path = os.path.join(ROOT, "analysis", "observed_interp_pcs.json")
    if not os.path.exists(obs_path):
        print("no analysis/observed_interp_pcs.json -- nothing to compare against")
        return
    obs = json.load(open(obs_path, encoding="utf-8"))
    static = {a["area"]: set(a["entries"]) for a in result.values()}
    byfile = {a["file"]: a["area"] for a in result.values()}

    band_rows = [x for x in obs
                 if BAND <= (int(x["pc"], 16) | 0x80000000) < BAND + 0x4000]

    # Which build each row was observed under decides whether it COULD appear
    # at all: a compiled band never yields interpreted PCs, so rows from a
    # three-band tree and rows from an all-bands tree are different
    # experiments and must not be added together.
    builds = {}
    for x in band_rows:
        for b in (x.get("builds") or ["(unstamped -- pre-2026-09-07)"]):
            builds[b] = builds.get(b, 0) + 1
    if build_filter:
        band_rows = [x for x in band_rows if build_filter in (x.get("builds") or [])]
        print("  filtered to build %s: %d rows" % (build_filter, len(band_rows)))
    print("  observed rows by build:")
    for b, n in sorted(builds.items(), key=lambda kv: -kv[1]):
        print("    %-46s %d" % (b, n))
    if len(builds) > 1 and not build_filter:
        print("    NOTE: more than one build contributed. The PROVEN column below")
        print("    mixes them; pass --build to read one experiment at a time.")
    seen = {}
    unattributed = 0
    for x in band_rows:
        pc = "0x%08X" % (int(x["pc"], 16) | 0x80000000)
        stamps = x.get("areas") or []
        if not stamps:
            unattributed += 1
            continue
        for f in stamps:
            aid = byfile.get(f)
            if aid is None:
                m = re.search(r"AREA(\d{3})", f)
                aid = int(m.group(1)) if m else None
            if aid is not None:
                seen.setdefault(aid, set()).add(pc)

    kp = ku = up = 0
    for aid, st in static.items():
        o = seen.get(aid, set())
        kp += len(st & o)
        ku += len(st - o)
        up += len(o - st)

    print("\nWorld-band coverage ledger (per occupant, never by address)")
    print("  observed band rows: %d, of which %d carry an area stamp"
          % (len(band_rows), len(band_rows) - unattributed))
    print("  areas with at least one attributed observation: %d of 200" % len(seen))
    print()
    print("                     PROVEN (ran interpreted)   UNPROVEN")
    print("  KNOWN   (static)   %-25d %d" % (kp, ku))
    print("  UNKNOWN            %-25d %s" % (up, "unmeasurable"))
    print()
    if kp == 0:
        print("  KNOWN+PROVEN is zero, which is what a COMPILED band looks like:")
        print("  every static root ran natively and never reached the interpreter.")
        print("  The world band IS compiled (all 11 bands are), so this is the")
        print("  expected healthy reading, not missing coverage.")
    print("  UNKNOWN+UNPROVEN cannot be counted, only estimated, and only for")
    print("  areas resident at least once (tools/pc_coverage.py, Chao2).")

    print("\n  per area with observations:")
    print("    %-9s %-7s %-7s %-8s %s" % ("area", "static", "proven", "unknown", "place"))
    for aid in sorted(seen):
        st, o = static.get(aid, set()), seen[aid]
        print("    AREA%03d   %-7d %-7d %-8d %s"
              % (aid, len(st), len(st & o), len(o - st),
                 result.get(aid, {}).get("place_jp", "")))

    # ---- the burn-down ledger.
    #
    # The observed file cannot answer "is this area done?", because a fully
    # native area emits NO rows -- success leaves no trace in a list of
    # failures, so "clean" and "never visited" look identical there. The
    # residency log is the missing half: area_poller.py records every change of
    # resident area whether or not it produced an interpreted PC.
    visited = set()
    tl = os.path.join(ROOT, "analysis", "area_timeline.jsonl")
    if os.path.exists(tl):
        for line in open(tl, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            m = re.search(r"AREA(\d{3})", row.get("file") or "")
            if m:
                visited.add(int(m.group(1)))

    code = {aid for aid, r in result.items() if r["total"] > 0}
    clean = sorted(visited & code - set(seen))
    dirty = sorted(visited & set(seen))
    never = sorted(code - visited)
    print("\n  Burn-down (residency log x observations):")
    print("    visited, CLEAN  (no interpreted PC ever attributed) : %d" % len(clean))
    print("    visited, dirty  (still yielding unknown entries)    : %d" % len(dirty))
    print("    never resident                                      : %d" % len(never))
    if not os.path.exists(tl):
        print("    (no analysis/area_timeline.jsonl -- run area_poller.py watch)")
    if clean:
        print("    clean: %s" % ", ".join("AREA%03d" % a for a in clean))
    print("    A clean area is the burn-down unit. It cannot be read off the")
    print("    observed file alone -- there, clean and unvisited are the same")
    print("    absence.")

    print("\n  %d code-bearing areas have never been attributed an observation."
          % len(code - set(seen)))
    print("  They contribute %d KNOWN entries (compiled, native, fine) and an"
          % sum(len(static[a]) for a in code - set(seen)))
    print("  unknown number of dispatch entries only a visit can reveal.")
    rew = [a for a in never if result[a]["rewarding_spots"]]
    print("  %d of the never-resident ones hold a searchable reward --"
          % len(rew))
    print("  docs/WORLD_ITEMS.md has the tile coordinates, which is the route in.")


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cue", default="isos/Breath of Fire III (Japan).cue")
    ap.add_argument("--area", type=int, help="only this area, printed in full")
    ap.add_argument("--items-only", action="store_true",
                    help="restrict to the areas that hold at least one item or zenny cache")
    ap.add_argument("--chain", action="store_true",
                    help="print the constant search-path PCs and exit")
    ap.add_argument("--verify", action="store_true",
                    help="compare the discovery counts against analysis/overlay_catalog.json")
    ap.add_argument("--build",
                    help="restrict the PROVEN column to rows observed under this "
                         "build id (see harvest_interp_pcs.build_fingerprint)")
    ap.add_argument("--coverage", action="store_true",
                    help="known/unknown x proven/unproven ledger against "
                         "analysis/observed_interp_pcs.json")
    ap.add_argument("--json", default="analysis/area_pcs.json")
    a = ap.parse_args()

    names = load_symbol_names()

    if a.chain:
        print("The search path -- constant, shared by every area:\n")
        print("  %-12s %-22s %-9s %s" % ("PC", "name", "module", "role"))
        for pc, nm, mod, role in SEARCH_CHAIN:
            print("  0x%08X   %-22s %-9s %s" % (pc, nm, mod, role))
        print("\n%d PCs. None of them live in the area section -- an area only "
              "supplies the record array." % len(SEARCH_CHAIN))
        return 0

    items = {}
    p = os.path.join(ROOT, "analysis", "world_items.json")
    if os.path.exists(p):
        for ar in json.load(open(p, encoding="utf-8"))["areas"]:
            n = sum(1 for r in ar["records"] if r["kind"] in ("item", "zenny"))
            if n:
                items[ar["area"]] = {"rewarding": n, "jp": ar["place_jp"], "en": ar["place_en"]}

    catalog = load_catalog()
    compiled = compiled_band_bases()
    boot, t_addr = wi.load_boot(os.path.join(ROOT, "disc", "SLPS_009.90"))
    ptrs = wi.area_struct_ptrs(boot, t_addr)
    read, areas, mode = wi.disc_area_files(os.path.join(ROOT, a.cue))
    print("disc %s, %d AREA files" % (mode, len(areas)))
    if compiled is not None:
        print("generated/ compiles overlay bands: %s"
              % ", ".join("0x%08X" % b for b in sorted(compiled)))
        print("world band 0x%08X is %s in this tree"
              % (BAND, "COMPILED" if BAND in compiled else "NOT compiled -- interpreted"))

    todo = [a.area] if a.area is not None else sorted(areas)
    if a.items_only:
        todo = [x for x in todo if x in items]

    result, disagree = {}, []
    for aid in todo:
        if aid not in areas:
            continue
        name, ext, sz = areas[aid]
        sec = wi.area_section(read, ext, sz)
        if sec is None:
            continue
        floor = data_floor(sec, ptrs[aid])
        jals = jal_targets(sec, BAND)          # identical to the catalog's roots.jal
        prologues = prologue_roots(sec, BAND)  # ... and its roots.prologue
        external = external_calls(sec, limit=floor)
        entries = sorted(jals | prologues)
        rec = {
            "area": aid, "file": name, "section_bytes": len(sec),
            "struct": "0x%08X" % ptrs[aid], "code_bytes": floor - BAND,
            "entries": ["0x%08X" % x for x in entries],
            "jal_only": len(jals - prologues), "prologue_only": len(prologues - jals),
            "both": len(jals & prologues), "total": len(entries),
            "external": [{"pc": "0x%08X" % t, "calls": c,
                          "name": names.get(t, ""),
                          "module": ("GAME.EMI" if GAME_LO <= t < GAME_HI
                                     else "boot" if 0x80093800 <= t < BAND else "?")}
                         for t, c in sorted(external.items(), key=lambda kv: -kv[1])],
            "rewarding_spots": items.get(aid, {}).get("rewarding", 0),
            "place_jp": items.get(aid, {}).get("jp", ""),
            "place_en": items.get(aid, {}).get("en", ""),
        }
        cat = catalog.get(aid)
        if cat:
            rec["catalog"] = cat
            r = cat.get("roots") or {}
            if (r.get("jal") is not None and
                    (r.get("jal") != len(jals) or r.get("prologue") != len(prologues))):
                disagree.append((aid, len(jals), len(prologues), r.get("jal"), r.get("prologue")))
        result[aid] = rec

    if a.coverage:
        coverage_report(result, a.build)
        return 0

    if a.area is not None:
        r = result.get(a.area)
        if not r:
            print("AREA%03d: nothing to report" % a.area)
            return 1
        print("\nAREA%03d %s %s   section %d bytes"
              % (a.area, r["place_jp"], r["place_en"], r["section_bytes"]))
        if r["rewarding_spots"]:
            print("  %d searchable spot(s) worth something" % r["rewarding_spots"])
        print("  %d entry PCs  (jal only %d, prologue only %d, both %d)"
              % (r["total"], r["jal_only"], r["prologue_only"], r["both"]))
        if r.get("catalog"):
            print("  catalog says function_count %s, roots %s"
                  % (r["catalog"]["function_count"], r["catalog"]["roots"]))
        print("\n  entry PCs inside the section:")
        for i in range(0, len(r["entries"]), 6):
            print("    " + "  ".join(r["entries"][i:i + 6]))
        print("\n  calls out of the section (%d distinct):" % len(r["external"]))
        for e in r["external"][:24]:
            print("    %s  x%-4d %-9s %s" % (e["pc"], e["calls"], e["module"], e["name"]))
        if len(r["external"]) > 24:
            print("    ... %d more" % (len(r["external"]) - 24))
        return 0

    # ---- corpus summary
    union = set()
    ext_union = {}
    with_items = 0
    for aid, r in result.items():
        for e in r["entries"]:
            union.add(e)
        for e in r["external"]:
            ext_union[e["pc"]] = ext_union.get(e["pc"], 0) + e["calls"]
        if r["rewarding_spots"]:
            with_items += 1
    tot = sum(r["total"] for r in result.values())
    print("\n%d areas scanned%s" % (len(result), " (items only)" if a.items_only else ""))
    print("  %d entry PCs in total, %d distinct addresses" % (tot, len(union)))
    print("  -> %.1f entry PCs per area on average" % (tot / max(1, len(result))))
    print("  %d areas hold at least one reward" % with_items)
    print("  %d distinct engine PCs called from area code" % len(ext_union))
    print("\n  most-called engine functions from area code:")
    for pc, c in sorted(ext_union.items(), key=lambda kv: -kv[1])[:12]:
        n = names.get(int(pc, 16), "")
        print("    %s  x%-5d %s" % (pc, c, n))

    if a.verify:
        print("\nAgreement with analysis/overlay_catalog.json:")
        checked = sum(1 for r in result.values() if r.get("catalog"))
        print("  %d of %d areas have a catalog row; %d disagree on the root counts"
              % (checked, len(result), len(disagree)))
        for aid, j, p_, cj, cp in disagree[:10]:
            print("    AREA%03d  here jal=%d prologue=%d   catalog jal=%s prologue=%s"
                  % (aid, j, p_, cj, cp))

    out = os.path.join(ROOT, a.json)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"band": "0x%08X" % BAND,
               "compiled_bands": sorted("0x%08X" % b for b in (compiled or [])),
               "search_chain": [{"pc": "0x%08X" % pc, "name": n, "module": m, "role": r}
                                for pc, n, m, r in SEARCH_CHAIN],
               "areas": [result[k] for k in sorted(result)]},
              open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\nwrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
