#!/usr/bin/env python
"""Cross-reference the prose in docs/ against the naming layer.

The structured side of this repo is already a graph: symbols.toml keys boot-EXE
functions by PC, names/functions.toml keys overlay functions by (section md5,
pc), names/data.toml keys data islands the same way, and tools/subsystem_map.py
joins them into a browsable map. The prose side is not joined to any of it. A
session reading `0x801EF400` in an investigation doc cannot tell whether that
address is named, which overlay owns it, or which other doc discussed it.

This tool builds that missing edge, offline, from committed files only:

    every address cited in prose  ->  its identity in the naming layer
    every named symbol            ->  the documents that discuss it

    python tools/xref.py lookup 0x801EF390 0x80144F4C   # identity + citations
    python tools/xref.py index --out docs/XREF.md       # the whole table
    python tools/xref.py queue                          # cited, not named
    python tools/xref.py shared                         # cited by 2+ documents
    python tools/xref.py stats                          # coverage

Scope and honesty limits, so nobody reads more into the output than is there:

  * Only main-RAM literals of the form 0x80xxxxxx are recognised. Instruction
    words (0x843813E0), hardware registers (0x1F801810) and bare decimal
    offsets are not addresses in this sense and are ignored.
  * 81.6% of the boot EXE's .text span is zero fill that overlays load into,
    and named data shares addresses with sibling code (docs/DATA_ISLANDS.md),
    so an address alone does NOT say whether it is code or data. This tool
    reports the region an address falls in and what the naming layer claims
    about it. It never guesses which.
  * Eleven bands share load addresses, so one address can resolve to several
    overlay functions (docs/AREA_PCS.md), and the named regions it falls inside
    can likewise overlap (docs/band-overlap-attribution.md). EVERY match is
    printed, never the first: first-match-wins is the bug that document records.
    Picking the right one needs residency, not arithmetic.
  * Falling inside a named region is context, not a name. An address in the swap
    slot is still unnamed; only an exact region base counts as resolved.
  * A boot symbol has no recorded span, so a non-exact hit is reported as the
    nearest symbol at or below the address with its delta, labelled as such.
    It is a reading aid, not a claim of containment.
  * An address being unnamed is not a defect. Most cited addresses are RAM
    variables, buffers and hardware-adjacent scratch that no naming file has a
    place for -- symbols.toml holds [[func]] entries only.

Sources scanned (all committed; analysis/ is NOT required):

    docs/*.md          kind `doc`     -- the prose corpus
    symbols.toml       kind `symbol`  -- the boot notes, which cite freely
    names/*.toml       kind `name`    -- evidence fields
    tools/*.py         kind `tool`    -- with --tools

Naming layer read: symbols.toml, names/functions.toml, names/data.toml,
names/overlays.toml (for overlay aliases), names/regions.toml (spans: the
overlay bands, the two message pools, the EXE image -- tools/regions.py),
seeds/ghidra_funcs.txt (a JAL target is a known function root even when it has
no name), disc_probe.json (the authoritative memory layout -- never hardcode it
here).
"""
import argparse
import bisect
import glob
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_overlays import ENGINE_RECORD_FILES  # noqa: E402
from name_map import (load_data_names, load_function_names,  # noqa: E402
                      load_overlay_names)
from regions import containing, load_regions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
NAMES_DIR = os.path.join(ROOT, "names")
SYMBOLS_TOML = os.path.join(ROOT, "symbols.toml")
SEEDS = os.path.join(ROOT, "seeds", "ghidra_funcs.txt")
PROBE = os.path.join(ROOT, "disc_probe.json")

# Generated prose: listing every address is its whole job, so scanning it would
# report each address as "cited" by the index that merely tabulates it.
GENERATED_DOCS = (os.path.join(DOCS, "XREF.md"),)

# Main RAM only. 0x80 covers the whole 2 MiB KSEG0 window (0x80000000..0x801FFFFF);
# anything wider would start matching instruction words out of disassembly dumps.
ADDR_RE = re.compile(r"0x80[0-9A-Fa-f]{6}")

# How far below an address to look for a boot symbol when the PC is not an exact
# entry. Boot symbols carry no span, so this is a display window, not a bound.
NEAR_WINDOW = 0x1000


# ------------------------------------------------------------------ layout

def load_layout():
    """Memory regions, read from disc_probe.json (the probe is authoritative)."""
    with open(PROBE, encoding="utf-8") as f:
        p = json.load(f)
    load = int(p["load_address"], 16)
    size = int(p["text_size"], 16)
    stack = int(p["stack_base"], 16)
    return {
        "load": load,
        "text_end": load + size,
        "stack": stack,
        "entry": int(p["entry_pc"], 16),
    }


def landmarks(L):
    """Addresses the disc probe names outright. Not code names — layout facts."""
    return {
        L["load"]: "boot EXE load address (disc_probe.json)",
        L["entry"]: "boot EXE entry PC (disc_probe.json)",
        L["text_end"]: "end of the boot EXE .text span (load + text_size)",
        L["stack"]: "stack base (disc_probe.json)",
    }


def region_of(addr, L):
    if addr < 0x80010000:
        return "kernel"
    if addr < L["load"]:
        return "pre-text"
    if addr < L["text_end"]:
        return "text"
    if addr <= L["stack"]:
        return "post-text"
    if addr <= 0x801FFFFF:
        return "post-text"
    return "above-ram"


REGION_NOTE = {
    "kernel": "BIOS kernel work area (first 64 KiB of RAM)",
    "pre-text": "below the EXE image (the 0x80010000 .EMI script-block dest lands here)",
    "text": "inside the boot EXE .text span -- mostly zero fill that overlays load into",
    "post-text": "above the EXE image: heap / stack",
    "above-ram": "outside 2 MiB main RAM",
}


# ------------------------------------------------------------ naming layer

def load_seeds():
    """JAL targets from the boot EXE: known function roots, named or not."""
    out = set()
    if not os.path.exists(SEEDS):
        return out
    with open(SEEDS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(int(line, 16))
    return out


def load_engine_records():
    """pc -> [(section md5, row)] from the engine's loader-record sidecars.

    The file list comes from tools/extract_overlays.py ENGINE_RECORD_FILES, so a
    sidecar added there is picked up here without a second edit. A row says the
    engine itself jalrs into that pc once the section is resident
    (docs/LOADER_RECORDS.md) -- a proven identity, but not a human name, so it is
    reported in the same tier as a seed list root rather than counted as named."""
    out = {}
    for rel in ENGINE_RECORD_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            rows = tomllib.load(f).get("record", [])
        for r in rows:
            entry, md5 = r.get("entry"), r.get("section")
            if not entry:
                continue
            pc = int(str(entry), 16)
            out.setdefault(pc, []).append((md5, dict(r, _file=rel)))
    return out


def record_label(md5, row, layer):
    """`AREA 12 handler[3] in <overlay>` — whichever key the family uses."""
    for key in ("area", "boss", "chapter", "combo", "ability", "id"):
        if key in row:
            who = f"{key.upper() if len(key) < 3 else key} {row[key]}"
            break
    else:
        who = os.path.basename(str(row.get("_file", "record")))
    kind = row.get("kind") or "entry"
    where = f" in {overlay_label(md5, layer)}" if md5 else ""
    return f"{who} {kind}{where}"


def load_boot_symbols():
    """pc -> symbols.toml row, for the boot EXE (the PSX_FN_* path)."""
    with open(SYMBOLS_TOML, "rb") as f:
        rows = tomllib.load(f).get("func", [])
    return {int(r["pc"]): r for r in rows}


def build_naming_layer(L=None):
    L = L or load_layout()
    boot = load_boot_symbols()
    overlays = load_overlay_names()
    funcs = load_function_names()
    # load_function_names() merges symbols.toml under the "boot" key; the
    # overlay-resident half is what boot symbols cannot answer for.
    ov_funcs = {}
    for (key, pc), row in funcs.items():
        if key != "boot":
            ov_funcs.setdefault(pc, []).append((key, row))
    data = {}
    for (key, pc), row in load_data_names().items():
        data.setdefault(pc, []).append((key, row))
    return {
        "boot": boot,
        "boot_pcs": sorted(boot),
        "nearest_pcs": sorted(set(boot) | set(ov_funcs)),
        "overlays": overlays,
        "ov_funcs": ov_funcs,
        "data": data,
        "seeds": load_seeds(),
        "landmarks": landmarks(L),
        "regions": load_regions(),
        "engine": load_engine_records(),
    }


def overlay_label(md5, layer):
    row = layer["overlays"].get(md5)
    if not row:
        return f"{md5[:8]}… (not in names/overlays.toml)"
    label = row.get("alias") or row.get("name") or md5[:8]
    src = row.get("source")
    return f"{label} ({src})" if src else str(label)


def nearest_below(addr, layer):
    """Nearest named entry at or below addr, within NEAR_WINDOW, over both the
    boot symbols and the overlay functions. Neither records a span, so this
    locates a neighbourhood; it does not prove containment. Ties go to the
    overlay side, which is the finer-grained claim."""
    pcs = layer["nearest_pcs"]
    i = bisect.bisect_right(pcs, addr)
    if i == 0:
        return None
    best = pcs[i - 1]
    delta = addr - best
    if delta == 0 or delta > NEAR_WINDOW:
        return None
    if best in layer["ov_funcs"]:
        md5, row = layer["ov_funcs"][best][0]
        label = f"{row.get('name', '?')} (overlay {overlay_label(md5, layer)})"
    else:
        label = f"{layer['boot'][best]['name']} (boot)"
    return best, delta, label


def resolve(addr, layer):
    """Everything the naming layer claims about one address."""
    return {
        "addr": addr,
        "landmark": layer["landmarks"].get(addr),
        "boot": layer["boot"].get(addr),
        "ov_funcs": layer["ov_funcs"].get(addr, []),
        "data": layer["data"].get(addr, []),
        "seed": addr in layer["seeds"],
        "engine": layer["engine"].get(addr, []),
        "region_base": [r for b, e, r in layer["regions"] if b == addr],
        "in_regions": containing(addr, layer["regions"]),
        "near": nearest_below(addr, layer),
    }


def is_named(res):
    """Resolved by the naming layer, a region base, or the probe's layout facts.

    Falling INSIDE a region is not a name — an address in the swap slot is still
    unnamed — so res["in_regions"] deliberately does not count here."""
    return bool(res["boot"] or res["ov_funcs"] or res["data"] or res["landmark"]
                or res["region_base"])


def identity_line(res, layer):
    """One-line identity for table output."""
    if res["boot"]:
        r = res["boot"]
        return f"{r['name']} [{r.get('status', 'guessed')}] boot"
    if res["ov_funcs"]:
        parts = []
        for md5, row in res["ov_funcs"]:
            parts.append(f"{row.get('name', '?')} [{row.get('status', 'unnamed')}]"
                         f" in {overlay_label(md5, layer)}")
        return " · ".join(parts)
    if res["data"]:
        parts = []
        for md5, row in res["data"]:
            parts.append(f"{row.get('name', '?')} ({row.get('kind', 'data')})"
                         f" in {overlay_label(md5, layer)}")
        return " · ".join(parts)
    if res["landmark"]:
        return res["landmark"]
    if res["region_base"]:
        return " · ".join(region_label(r) + " (base)" for r in res["region_base"])
    if res["engine"]:
        md5, row = res["engine"][0]
        more = f" (+{len(res['engine']) - 1} more)" if len(res["engine"]) > 1 else ""
        return f"engine loader entry: {record_label(md5, row, layer)}{more}"
    if res["seed"]:
        return "unnamed function root (seeds/ghidra_funcs.txt)"
    if res["near"]:
        pc, delta, label = res["near"]
        return f"≤ {label} +0x{delta:X} (nearest below, span unknown)"
    if res["in_regions"]:
        b, e, r = res["in_regions"][0]
        return f"in {region_label(r)} +0x{res['addr'] - b:X}"
    return "unknown"


def region_label(row):
    name = row.get("alias") or row.get("name")
    kind = row.get("kind")
    return f"{name} [{kind}]" if kind and kind not in str(name) else str(name)


# --------------------------------------------------------------- citations

def source_files(include_tools):
    out = []
    # recursive: docs/loader_records/*.md and any future subdirectory of notes
    # count as prose too (they were missed until 2026-09-12)
    skip = {os.path.abspath(p) for p in GENERATED_DOCS}
    for p in sorted(glob.glob(os.path.join(DOCS, "**", "*.md"), recursive=True)):
        if os.path.abspath(p) not in skip:
            out.append((p, "doc"))
    out.append((SYMBOLS_TOML, "symbol"))
    # The engine record sidecars are an IDENTITY source, not prose: a row saying
    # the engine enters 0x801F2C8C is not a document citing that address, and
    # counting 1,319 generated rows as citations would swamp the census.
    generated = {os.path.abspath(os.path.join(ROOT, r)) for r in ENGINE_RECORD_FILES}
    for p in sorted(glob.glob(os.path.join(NAMES_DIR, "*.toml"))):
        if os.path.abspath(p) not in generated:
            out.append((p, "name"))
    if include_tools:
        for p in sorted(glob.glob(os.path.join(ROOT, "tools", "*.py"))):
            out.append((p, "tool"))
    return out


def scan_citations(include_tools=False, exclude=()):
    """addr -> list of (relpath, lineno, kind), in file order."""
    excl = {os.path.abspath(e) for e in exclude}
    cites = {}
    for path, kind in source_files(include_tools):
        if os.path.abspath(path) in excl or not os.path.exists(path):
            continue
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                if "0x80" not in line:
                    continue
                for m in set(ADDR_RE.findall(line)):
                    cites.setdefault(int(m, 16), []).append((rel, n, kind))
    return cites


def doc_files_citing(cl):
    return sorted({rel for rel, _, kind in cl if kind == "doc"})


def doc_label(rel):
    """`FOO.md` for a top-level doc, `loader_records/AREA.md` for a nested one —
    a bare basename would make docs/loader_records/AREA.md ambiguous."""
    inner = rel[len("docs/"):] if rel.startswith("docs/") else rel
    return inner


# ----------------------------------------------------------------- reports

def cmd_lookup(args):
    L = load_layout()
    layer = build_naming_layer(L)
    cites = scan_citations(args.tools)
    bad = 0
    for raw in args.addr:
        try:
            addr = int(raw, 16)
        except ValueError:
            print(f"{raw}: not a hex address", file=sys.stderr)
            bad = 1
            continue
        res = resolve(addr, layer)
        reg = region_of(addr, L)
        print(f"\n0x{addr:08X}  {reg} — {REGION_NOTE[reg]}")
        if addr % 4:
            print("  unaligned: cannot be a function entry (MIPS words are 4-byte aligned)")
        if res["boot"]:
            r = res["boot"]
            print(f"  boot symbol: {r['name']}  [{r.get('status', 'guessed')}]"
                  f"  emit={'true' if r.get('emit') else 'false'}  (symbols.toml)")
            if r.get("note"):
                print(f"    evidence: {r['note']}")
        for md5, row in res["ov_funcs"]:
            print(f"  overlay function: {row.get('name', '?')}"
                  f"  [{row.get('status', 'unnamed')}]"
                  f"  in {overlay_label(md5, layer)}  (names/functions.toml)")
            if row.get("evidence"):
                print(f"    evidence: {row['evidence']}")
        for md5, row in res["data"]:
            print(f"  data island: {row.get('name', '?')} ({row.get('kind', 'data')})"
                  f"  [{row.get('status', 'unnamed')}]"
                  f"  in {overlay_label(md5, layer)}  (names/data.toml)")
            if row.get("evidence"):
                print(f"    evidence: {row['evidence']}")
        for r in res["region_base"]:
            print(f"  region base: {region_label(r)}"
                  f"  bound={r.get('bound')}  (names/regions.toml)")
            if r.get("evidence"):
                print(f"    evidence: {r['evidence']}")
        if res["in_regions"]:
            print("  inside, narrowest first (regions overlap legitimately —"
                  " every match is listed):")
            for b, e, r in res["in_regions"]:
                print(f"    {region_label(r)}  0x{b:08X}..0x{e:08X}"
                      f"  +0x{addr - b:X}  bound={r.get('bound')}")
        if res["landmark"]:
            print(f"  layout landmark: {res['landmark']}")
        if res["engine"]:
            print(f"  engine loader entry — the engine jalrs here once the"
                  f" section is resident ({len(res['engine'])} record(s),"
                  f" docs/LOADER_RECORDS.md):")
            for md5, row in res["engine"][:6]:
                print(f"    {record_label(md5, row, layer)}  [{row['_file']}]")
            if len(res["engine"]) > 6:
                print(f"    … {len(res['engine']) - 6} more record(s)")
        if res["seed"] and not res["boot"]:
            print("  known function root: listed in seeds/ghidra_funcs.txt, unnamed")
        if not is_named(res):
            if res["near"]:
                pc, delta, label = res["near"]
                print(f"  no exact name. Nearest named entry at or below:"
                      f" {label} 0x{pc:08X} +0x{delta:X}"
                      f" — no span is recorded on either side, so this is a"
                      f" neighbourhood, not containment")
            else:
                print("  no exact name, and nothing named within"
                      f" 0x{NEAR_WINDOW:X} below")
        cl = cites.get(addr, [])
        if cl:
            print(f"  cited {len(cl)}× in {len(doc_files_citing(cl))} document(s):")
            for rel, n, kind in cl:
                print(f"    {rel}:{n}  ({kind})")
        else:
            print("  not cited in docs/, symbols.toml or names/")
    return bad


def rows_for_index(args, layer, L, cites):
    rows = []
    for addr, cl in cites.items():
        res = resolve(addr, layer)
        docs = doc_files_citing(cl)
        rows.append({
            "addr": addr,
            "region": region_of(addr, L),
            "named": is_named(res),
            "identity": identity_line(res, layer),
            "docs": docs,
            "cites": len(cl),
        })
    rows.sort(key=lambda r: r["addr"])
    return rows


def cmd_index(args):
    L = load_layout()
    layer = build_naming_layer(L)
    out_path = os.path.join(ROOT, args.out) if args.out else None
    cites = scan_citations(args.tools, exclude=[out_path] if out_path else ())
    rows = rows_for_index(args, layer, L, cites)
    if not args.include_notes:
        # The table exists to serve someone reading docs/. An address cited only
        # in a symbols.toml note or a names/ evidence field is already sitting
        # next to its own name and does not need a row here.
        rows = [r for r in rows if r["docs"]]
    if args.named_only:
        rows = [r for r in rows if r["named"]]
    if args.json:
        payload = {
            "generator": "tools/xref.py",
            "rows": [dict(r, addr=f"0x{r['addr']:08X}") for r in rows],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    else:
        text = render_markdown(rows, layer, L, cites)
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{args.out}: {len(rows)} addresses")
    else:
        sys.stdout.write(text)
    return 0


def render_markdown(rows, layer, L, cites):
    named = sum(1 for r in rows if r["named"])
    out = [
        "# Address cross-reference (`docs/` prose → the naming layer)\n",
        "\n**Status:** STABLE (generated). Regenerate with `python tools/xref.py"
        " index --out docs/XREF.md` after editing docs, `symbols.toml` or"
        " `names/`; never hand-edit.\n",
        "\nEvery `0x80xxxxxx` literal cited in `docs/*.md`, joined to what"
        " the naming layer claims"
        " about it. An address alone does not say whether it is code or data"
        " (81.6% of `.text` is overlay zero fill, and named data shares"
        " addresses with sibling code — `DATA_ISLANDS.md`), and one address can"
        " resolve to several overlay functions because bands share load"
        " addresses (`AREA_PCS.md`). Unnamed is not a defect: most cited"
        " addresses are RAM variables, which `symbols.toml` has no table for.\n",
        f"\n{len(rows)} distinct addresses · {named} resolve to a name ·"
        f" {len(rows) - named} do not.\n",
        "\n| Address | Region | Identity | Cited by |\n|---|---|---|---|\n",
    ]
    for r in rows:
        docs = ", ".join(f"`{doc_label(d)}`" for d in r["docs"]) or "—"
        ident = r["identity"].replace("|", "\\|")
        out.append(f"| `0x{r['addr']:08X}` | {r['region']} | {ident} | {docs} |\n")
    return "".join(out)


def cmd_queue(args):
    L = load_layout()
    layer = build_naming_layer(L)
    cites = scan_citations(args.tools)
    cand = []
    for addr, cl in cites.items():
        res = resolve(addr, layer)
        if is_named(res) or res["engine"]:
            continue
        docs = doc_files_citing(cl)
        if len(docs) < args.min_docs:
            continue
        if args.aligned_only and addr % 4:
            continue
        if args.region and region_of(addr, L) != args.region:
            continue
        cand.append((len(docs), len(cl), addr, res, docs))
    cand.sort(key=lambda t: (-t[0], -t[1], t[2]))
    print(f"{len(cand)} cited address(es) with no entry in symbols.toml,"
          f" names/functions.toml or names/data.toml"
          f"{' (word-aligned only)' if args.aligned_only else ''}"
          f"{f', region {args.region}' if args.region else ''}"
          f"{f', cited in ≥{args.min_docs} document(s)' if args.min_docs > 1 else ''}.")
    print("Ranked by how many documents discuss it. A row is a candidate for"
          " naming, not proof that a name is missing.\n")
    hdr = f"{'address':11} {'region':10} {'docs':4} {'cites':5} {'root':5} context"
    print(hdr)
    print("-" * len(hdr))
    for ndocs, ncites, addr, res, docs in cand[:args.limit]:
        root = "yes" if res["seed"] else "—"
        ctx = ""
        if res["near"]:
            pc, delta, label = res["near"]
            ctx = f"≤ {label} +0x{delta:X}"
        elif docs:
            ctx = doc_label(docs[0])
        print(f"0x{addr:08X}  {region_of(addr, L):10} {ndocs:<4} {ncites:<5}"
              f" {root:5} {ctx}")
    if len(cand) > args.limit:
        print(f"\n… {len(cand) - args.limit} more (--limit)")
    return 0


def cmd_shared(args):
    """Addresses discussed by more than one document — the prose-to-prose edge
    the docs index cannot show."""
    L = load_layout()
    layer = build_naming_layer(L)
    cites = scan_citations(args.tools)
    rows = []
    for addr, cl in cites.items():
        docs = doc_files_citing(cl)
        if len(docs) >= args.min_docs:
            rows.append((len(docs), addr, docs, resolve(addr, layer)))
    rows.sort(key=lambda t: (-t[0], t[1]))
    print(f"{len(rows)} address(es) cited by {args.min_docs}+ documents"
          f" in docs/.\n")
    for ndocs, addr, docs, res in rows[:args.limit]:
        print(f"0x{addr:08X}  {region_of(addr, L):10} {ndocs} docs"
              f"  {identity_line(res, layer)}")
        for d in docs:
            print(f"    {d}")
    if len(rows) > args.limit:
        print(f"\n… {len(rows) - args.limit} more (--limit)")
    return 0


def cmd_stats(args):
    L = load_layout()
    layer = build_naming_layer(L)
    cites = scan_citations(args.tools)
    by_region = {}
    named = 0
    seed_only = 0
    engine_only = 0
    for addr, cl in cites.items():
        res = resolve(addr, layer)
        reg = region_of(addr, L)
        b = by_region.setdefault(reg, {"cited": 0, "named": 0})
        b["cited"] += 1
        if is_named(res):
            named += 1
            b["named"] += 1
        elif res["engine"]:
            engine_only += 1
        elif res["seed"]:
            seed_only += 1
    doc_cited = {a for a, cl in cites.items() if any(k == "doc" for _, _, k in cl)}

    print("Naming layer")
    print(f"  symbols.toml            {len(layer['boot']):5} boot functions")
    print(f"  names/functions.toml    {sum(len(v) for v in layer['ov_funcs'].values()):5}"
          f" overlay functions over {len(layer['ov_funcs'])} distinct PCs")
    print(f"  names/data.toml         {sum(len(v) for v in layer['data'].values()):5}"
          f" data islands")
    print(f"  names/overlays.toml     {len(layer['overlays']):5} overlays")
    print(f"  names/*_records.toml    {sum(len(v) for v in layer['engine'].values()):5}"
          f" engine loader entries over {len(layer['engine'])} distinct PCs")
    print(f"  seeds/ghidra_funcs.txt  {len(layer['seeds']):5} JAL targets")
    print("\nAddresses cited in prose")
    print(f"  {len(cites):5} distinct, of which {len(doc_cited)} appear in docs/*.md")
    print(f"  {named:5} resolve to a name"
          f"  ({100.0 * named / max(1, len(cites)):.1f}%)")
    print(f"  {engine_only:5} more are engine loader entries with no name")
    print(f"  {seed_only:5} more are known function roots with no name")
    print(f"  {len(cites) - named - engine_only - seed_only:5} unresolved")
    print("\nBy region")
    for reg in ("kernel", "pre-text", "text", "post-text", "above-ram"):
        b = by_region.get(reg)
        if not b:
            continue
        print(f"  {reg:10} {b['cited']:5} cited, {b['named']:5} named"
              f"  — {REGION_NOTE[reg]}")
    print("\nsymbols.toml holds [[func]] entries only, so a cited RAM variable"
          "\nhas nowhere to be named. That is most of what 'unresolved' counts.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Join addresses cited in prose to the naming layer.")
    ap.add_argument("--tools", action="store_true",
                    help="also scan tools/*.py for cited addresses")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lookup", help="identity and citations for one or more addresses")
    p.add_argument("addr", nargs="+")
    p.set_defaults(fn=cmd_lookup)

    p = sub.add_parser("index", help="the whole cited-address table")
    p.add_argument("--out", help="write to this repo-relative path instead of stdout")
    p.add_argument("--json", action="store_true")
    p.add_argument("--named-only", action="store_true")
    p.add_argument("--include-notes", action="store_true",
                   help="also table addresses cited only in symbols.toml /"
                        " names/ evidence, not in docs/*.md")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("queue", help="cited addresses with no name, ranked")
    p.add_argument("--min-docs", type=int, default=1)
    p.add_argument("--aligned-only", action="store_true",
                   help="drop addresses that cannot be function entries")
    p.add_argument("--region", choices=sorted(REGION_NOTE))
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("shared", help="addresses cited by several documents")
    p.add_argument("--min-docs", type=int, default=2)
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_shared)

    p = sub.add_parser("stats", help="coverage of prose citations by the naming layer")
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
