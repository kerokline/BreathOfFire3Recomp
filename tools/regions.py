#!/usr/bin/env python
"""names/regions.toml — human names for RAM *regions* (see tools/xref.py).

The naming layer had no home for a span. symbols.toml holds [[func]] entries,
names/functions.toml and names/data.toml key single PCs inside an overlay image,
and names/overlays.toml keys content by md5 with no destination field. So the
addresses this repo cites most often -- the overlay band bases, the two message
pools -- could only be named in prose, and `tools/xref.py queue` ranked them at
the top of the unnamed list for exactly that reason.

This sidecar closes that. Every row is DERIVED from a committed source and says
which one; nothing here is typed in from memory:

  docs/OVERLAY_EXTRACTION.md  the ten-band map (tools/emi_survey.py over the
                              disc: occupants, unique sections, unique bytes)
  docs/OVERLAYS.md §1         the zero-run scan of the boot EXE image -- the
                              window each band's occupants land in
  docs/band-overlap-attribution.md  measured occupant spans for the three bands
                              that overlap, including LOGO.EXE's own band
  src/bof3_localize.c         AREA_BLOCK_LO / AREA_BLOCK_HI and the insert
                              scratch record geometry, as the shipping plugin
                              defines them
  docs/TEXT_ENGINE.md         the live text block's end, which splits the two
                              message pools
  disc_probe.json             the EXE image bounds
  psx-spx                     the BIOS kernel area (external comparative)

    python tools/regions.py seed     # merge into names/regions.toml
    python tools/regions.py check    # re-derive and compare; fails on drift
    python tools/regions.py list     # the map, widths, and overlaps

`seed` is a MERGE, like tools/name_map.py init: it rewrites the derived fields
and keeps `alias`, `note` and any hand-raised `status`. Delete a row to have it
re-seeded from scratch.

Two conventions that matter when reading a row:

  * `end` is EXCLUSIVE. A region is [base, end).
  * `bound` says what `end` actually is, because the sources are not equally
    strong. `measured occupant span` came from the capture data. `zero-fill
    window` is the image's zero run, which bounds where occupants may land but
    is not proof any occupant reaches it. Never quote an `end` without its
    `bound`.

Regions OVERLAP and that is not an error: LOGO.EXE covers the PLCHAR band
entirely and 107 KB of the swap slot, because they are resident at different
times (docs/band-overlap-attribution.md). Any consumer must report every
containing region, not the first match -- the first-match bug in pc_coverage.py
is what that document was written about.
"""
import argparse
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_map import _emit_table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS_TOML = os.path.join(ROOT, "names", "regions.toml")
DOCS = os.path.join(ROOT, "docs")
PROBE = os.path.join(ROOT, "disc_probe.json")
LOCALIZE_C = os.path.join(ROOT, "src", "bof3_localize.c")

KINDS = ("overlay band", "message pool", "exe image", "kernel", "scratch array")

HEADER = """\
# names/regions.toml — human names for RAM REGIONS, seeded by tools/regions.py.
# Do not hand-edit the derived fields (base, end, bound, kind, evidence): they
# are re-derived from committed sources by `python tools/regions.py seed`, and
# `check` fails if a row drifts from them. Edit `alias` and `note` freely; those
# survive a re-seed.
#
#   base / end  the span, end EXCLUSIVE
#   bound       what `end` IS — a measured occupant span, the image's zero-fill
#               window, a documented block end, or the EXE layout. The sources
#               are not equally strong; never quote an end without its bound.
#   kind        overlay band | message pool | exe image | kernel | scratch array
#   nature      what the source says the region holds, verbatim (may be empty)
#   status      unnamed | hypothesis | evidence | verified
#   evidence    which committed source the row was derived from
#
# Regions OVERLAP legitimately (LOGO.EXE covers the PLCHAR band entirely and
# 107 KB of the swap slot; they are resident at different times —
# docs/band-overlap-attribution.md). A consumer must report EVERY containing
# region, never the first match.
"""


def _read_rows():
    if not os.path.exists(REGIONS_TOML):
        return []
    with open(REGIONS_TOML, "rb") as f:
        return tomllib.load(f).get("region", [])


def load_regions():
    """Sorted [(base, end_or_None, row)] for tooling (tools/xref.py)."""
    out = []
    for r in _read_rows():
        base = int(str(r["base"]), 16) if isinstance(r["base"], str) else int(r["base"])
        end = r.get("end")
        end = (int(str(end), 16) if isinstance(end, str) else int(end)) if end else None
        out.append((base, end, r))
    out.sort(key=lambda t: (t[0], t[1] or t[0]))
    return out


def containing(addr, regions):
    """EVERY region containing addr, widest last. Never first-match-wins."""
    hits = [(b, e, r) for b, e, r in regions if e and b <= addr < e]
    hits.sort(key=lambda t: t[1] - t[0])
    return hits


# ------------------------------------------------------- committed sources

def _clean(cell):
    return cell.replace("**", "").replace("`", "").strip()


def _md_table(path, header_cells):
    """Rows of the one markdown table whose header matches, as cleaned lists."""
    want = [c.lower() for c in header_cells]
    rows, in_table = [], False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.lstrip().startswith("|"):
                if in_table:
                    break
                continue
            cells = [_clean(c) for c in line.strip().strip("|").split("|")]
            if not in_table:
                if [c.lower() for c in cells] == want:
                    in_table = True
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
    if not rows:
        raise SystemExit(f"{os.path.relpath(path, ROOT)}: no table with header"
                         f" {header_cells} — the doc changed shape, so this"
                         f" seeder must be updated rather than guessing")
    return rows


def ten_band_map():
    """base -> (occupants, unique, unique_bytes, nature) from the ten-band map."""
    path = os.path.join(DOCS, "OVERLAY_EXTRACTION.md")
    rows = _md_table(path, ["Band", "Occupants", "Unique", "Unique bytes", "Nature"])
    out = {}
    for cells in rows:
        base = int(cells[0], 16)
        out[base] = (int(cells[1].replace(",", "")), int(cells[2].replace(",", "")),
                     int(cells[3].replace(",", "")), cells[4])
    if len(out) != 10:
        raise SystemExit(f"OVERLAY_EXTRACTION.md: expected the ten-band map,"
                         f" parsed {len(out)} bands")
    return out


def zero_runs():
    """start_of_run -> end_of_run EXCLUSIVE, from the image zero-run scan.

    The table's dash is exclusive at the top: its own byte count proves it
    (0x80093801-0x800C1800 is given as 188,415 = 0x800C1800 - 0x80093801), and
    the top of each run is the next band's base, which is not part of it. The
    count is asserted per row so a doc edit cannot silently shift a bound."""
    path = os.path.join(DOCS, "OVERLAYS.md")
    rows = _md_table(path, ["Region", "Bytes"])
    out = {}
    for cells in rows:
        m = re.match(r"(0x[0-9A-Fa-f]+)\s*[–-]\s*(0x[0-9A-Fa-f]+)", cells[0])
        if not m:
            raise SystemExit(f"OVERLAYS.md §1: cannot parse zero run {cells[0]!r}")
        lo, hi = int(m.group(1), 16), int(m.group(2), 16)
        stated = int(cells[1].replace(",", ""))
        if hi - lo != stated:
            raise SystemExit(
                f"OVERLAYS.md §1: run 0x{lo:08X}-0x{hi:08X} is {hi - lo} bytes"
                f" exclusive but the table says {stated}. The convention this"
                f" seeder relies on no longer holds; fix it here, do not guess")
        out[lo] = hi
    return out


def measured_spans():
    """base -> (end_exclusive, label) from the band-overlap measurement."""
    path = os.path.join(DOCS, "band-overlap-attribution.md")
    rows = _md_table(path, ["Band", "Span", "Width", "Exclusive"])
    out = {}
    for cells in rows:
        m = re.match(r"(0x[0-9A-Fa-f]+)", cells[0])
        span = re.match(r"([0-9A-Fa-f]+)\.\.([0-9A-Fa-f]+)$", cells[1])
        if not m or not span:
            continue  # the table's "every other band | — |" summary row
        out[int(m.group(1), 16)] = (int(span.group(2), 16), cells[0])
    if not out:
        raise SystemExit("band-overlap-attribution.md: parsed no measured spans")
    return out


def localize_defines():
    """The shipping plugin's own constants — the strongest source for the pools."""
    want = {"AREA_BLOCK_LO", "AREA_BLOCK_HI", "INSERT_RECORD_BASE",
            "INSERT_RECORD_SIZE", "INSERT_MAX"}
    out = {}
    with open(LOCALIZE_C, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)u?\b", line)
            if m and m.group(1) in want:
                out[m.group(1)] = int(m.group(2), 0)
    missing = want - set(out)
    if missing:
        raise SystemExit(f"src/bof3_localize.c: missing {sorted(missing)} —"
                         f" the plugin changed, so re-derive rather than guess")
    return out


def live_text_block():
    """(base, end EXCLUSIVE, stated_bytes) of the system pool.

    The row reads `0x80014000 - 0x80017628 (13,864 bytes)` and 0x80017628 minus
    0x80014000 is exactly 13,864, so the top address is one past the end -- the
    same convention src/bof3_localize.c uses for AREA_BLOCK_HI. Asserted, not
    assumed, because off-by-one here would put a byte of RAM in the wrong pool."""
    path = os.path.join(DOCS, "TEXT_ENGINE.md")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "Live text block" in line:
                a = re.findall(r"0x[0-9A-Fa-f]{8}", line)
                n = re.search(r"\(([\d,]+) bytes\)", line)
                if len(a) == 2 and n:
                    lo, hi = int(a[0], 16), int(a[1], 16)
                    stated = int(n.group(1).replace(",", ""))
                    if hi - lo != stated:
                        raise SystemExit(
                            f"TEXT_ENGINE.md: live text block 0x{lo:08X}-"
                            f"0x{hi:08X} is {hi - lo} bytes exclusive but the row"
                            f" says {stated}; resolve the convention here")
                    return lo, hi, stated
    raise SystemExit("TEXT_ENGINE.md: no parseable 'Live text block' row")


def probe_layout():
    with open(PROBE, encoding="utf-8") as f:
        p = json.load(f)
    load = int(p["load_address"], 16)
    return load, load + int(p["text_size"], 16)


# ------------------------------------------------------------- derivation

def derive():
    bands = ten_band_map()
    runs = zero_runs()
    spans = measured_spans()
    dfn = localize_defines()
    sys_lo, sys_end, sys_bytes = live_text_block()
    load, text_end = probe_layout()
    rows = []

    def add(base, end, name, kind, bound, evidence, nature=""):
        rows.append({"base": base, "end": end, "name": name, "kind": kind,
                     "bound": bound, "nature": nature, "alias": "",
                     "status": "evidence", "evidence": evidence, "note": ""})

    # 1. The BIOS kernel area. External comparative, per the framework rule.
    add(0x80000000, 0x80010000, "kernel_area", "kernel", "architecture",
        "psx-spx: the first 64 KiB of main RAM is the BIOS kernel area."
        " docs/kernel-patch-sites.md measures 44.6% of interpreted work here")

    # 2. The two message pools, from the shipping plugin's own constants.
    add(dfn["AREA_BLOCK_LO"], sys_lo, "area_script_block", "message pool",
        "documented block end",
        f"src/bof3_localize.c AREA_BLOCK_LO = 0x{dfn['AREA_BLOCK_LO']:08X}, the"
        f" per-area script block the box reads (ptr = base + u16[base + 2*idx]);"
        f" ends where the system pool begins at 0x{sys_lo:08X} — the 16 KiB"
        f" window of docs/FURIGANA.md. docs/TEXT_ENGINE.md, names/areas.toml"
        f" keys areas by this section's md5")
    add(sys_lo, sys_end, "system_message_block", "message pool",
        "documented block end",
        f"BIN/ETC/AFLDKWA.EMI dest 0x{sys_lo:08X}, the 'Live text block' row of"
        f" docs/TEXT_ENGINE.md: 0x{sys_lo:08X} to 0x{sys_end:08X} exclusive,"
        f" {sys_bytes:,} bytes as that row states, 309 slots of menu / shop /"
        f" memcard text. src/bof3_localize.c gates on AREA_BLOCK_HI ="
        f" 0x{dfn['AREA_BLOCK_HI']:08X}, the same one-past-the-end address")

    # 3. The boot EXE image.
    add(load, text_end, "boot_exe_image", "exe image", "exe layout",
        f"disc_probe.json load_address + text_size. 81.6% of it is zero fill"
        f" that overlays load into (docs/OVERLAYS.md §1), so an address here"
        f" says nothing about code vs data")

    # 4. The ten .EMI overlay bands, plus LOGO.EXE's own band.
    for base in sorted(bands):
        occ, uniq, ubytes, nature = bands[base]
        ev = (f"docs/OVERLAY_EXTRACTION.md ten-band map (tools/emi_survey.py"
              f" over the disc, every section's TOC preview checksum verified):"
              f" {occ} occupants, {uniq} unique, {ubytes:,} unique bytes"
              + (f" — {nature}" if nature else ""))
        if base in spans:
            end, label = spans[base]
            bound = "measured occupant span"
            ev += (f". End from docs/band-overlap-attribution.md, measured over"
                   f" analysis/overlay_captures_all.json: {label} span ends"
                   f" 0x{end:08X}")
        elif base + 1 in runs:
            end = runs[base + 1]
            bound = "zero-fill window"
            ev += (f". End is the image's zero run 0x{base + 1:08X}–0x{end:08X}"
                   f" (docs/OVERLAYS.md §1): where occupants may land, NOT proof"
                   f" one reaches it")
        else:
            # No committed bound. A row with no end still names the base, and
            # containment simply does not apply to it -- better than inventing
            # a width.
            end = None
            bound = "base only — no committed end"
            ev += (". No zero run starts at base+1 and no measured span exists,"
                   " so the extent is unknown from committed sources")
        add(base, end, f"band_{base:08X}", "overlay band", bound, ev, nature)

    for base, (end, label) in sorted(spans.items()):
        if base in bands:
            continue
        add(base, end, f"band_{base:08X}", "overlay band",
            "measured occupant span",
            f"docs/band-overlap-attribution.md, measured over"
            f" analysis/overlay_captures_all.json: {label} span"
            f" 0x{base:08X}..0x{end:08X}. LOGO/LOGO.EXE is a standalone PS-EXE,"
            f" not an .EMI section, so it is absent from the ten-band map"
            f" (tools/extract_logo_overlay.py)",
            re.sub(r"^0x[0-9A-Fa-f]+\s*", "", label))

    # 5. The message box's insert scratch records.
    ibase = dfn["INSERT_RECORD_BASE"]
    add(ibase, ibase + dfn["INSERT_RECORD_SIZE"] * dfn["INSERT_MAX"],
        "insert_scratch_records", "scratch array", "documented geometry",
        f"src/bof3_localize.c INSERT_RECORD_BASE = 0x{ibase:08X},"
        f" INSERT_RECORD_SIZE = 0x{dfn['INSERT_RECORD_SIZE']:X},"
        f" INSERT_MAX = {dfn['INSERT_MAX']}: the 32-byte records MsgBox_Step"
        f" draws for <07><nn> item / skill inserts (docs/INSERT_RUBY.md)")

    rows.sort(key=lambda r: (r["base"], r["end"] or r["base"]))
    for r in rows:
        if r["end"] is not None and r["end"] <= r["base"]:
            raise SystemExit(f"derived a non-positive span for {r['name']}")
        if r["kind"] not in KINDS:
            raise SystemExit(f"{r['name']}: unknown kind {r['kind']!r}")
    return rows


DERIVED_FIELDS = ("base", "end", "name", "kind", "bound", "nature", "evidence")
KEPT_FIELDS = ("alias", "note")


def cmd_seed(args):
    derived = derive()
    existing = {}
    for r in _read_rows():
        base = int(str(r["base"]), 16) if isinstance(r["base"], str) else int(r["base"])
        existing[(base, r.get("name"))] = r
    rows, kept = [], 0
    for d in derived:
        old = existing.get((d["base"], d["name"]))
        if old:
            kept += 1
            for k in KEPT_FIELDS:
                if old.get(k):
                    d[k] = old[k]
            # a hand-raised status (evidence -> verified) survives; a lowered one
            # does not, because the evidence string is re-derived above it
            if old.get("status") == "verified":
                d["status"] = "verified"
        rows.append(d)
    orphans = [r for k, r in existing.items()
               if k not in {(d["base"], d["name"]) for d in derived}]
    for o in orphans:
        o = dict(o)
        o["note"] = (str(o.get("note", "")) + " [no longer derivable from the"
                     " committed sources]").strip()
        rows.append(o)
    os.makedirs(os.path.dirname(REGIONS_TOML), exist_ok=True)
    with open(REGIONS_TOML, "w", encoding="utf-8", newline="\n") as f:
        f.write(_emit_table("region", rows, HEADER))
    print(f"names/regions.toml: {len(rows)} regions"
          f" ({len(derived) - kept} added, {kept} kept, {len(orphans)} orphaned)")
    return 0


def cmd_check(args):
    rows = _read_rows()
    if not rows:
        print("names/regions.toml: absent or empty — run `regions.py seed`",
              file=sys.stderr)
        return 2
    derived = {(d["base"], d["name"]): d for d in derive()}
    onfile = {}
    for r in rows:
        base = int(str(r["base"]), 16) if isinstance(r["base"], str) else int(r["base"])
        onfile[(base, r.get("name"))] = r
    bad = 0
    for key, d in derived.items():
        r = onfile.get(key)
        if not r:
            print(f"missing: {d['name']} 0x{d['base']:08X}", file=sys.stderr)
            bad = 1
            continue
        for f in DERIVED_FIELDS:
            want, got = d[f], r.get(f)
            if f == "end" and got is not None:
                got = int(str(got), 16) if isinstance(got, str) else int(got)
            if f == "base":
                got = int(str(got), 16) if isinstance(got, str) else int(got)
            if want != got:
                shown = ((f"0x{got:08X}" if isinstance(got, int) else repr(got)),
                         (f"0x{want:08X}" if isinstance(want, int) else repr(want)))
                print(f"{d['name']}: {f} is {shown[0]}, derives to {shown[1]}",
                      file=sys.stderr)
                bad = 1
    for key, r in onfile.items():
        if key not in derived and "no longer derivable" not in str(r.get("note", "")):
            print(f"not derivable and not marked: {r.get('name')}", file=sys.stderr)
            bad = 1
        if not r.get("evidence"):
            print(f"{r.get('name')}: no evidence", file=sys.stderr)
            bad = 1
    print("names/regions.toml: "
          + ("drifted from its sources — re-run `seed`" if bad
             else f"{len(rows)} regions, all derived fields agree with their sources"))
    return bad


def cmd_list(args):
    regions = load_regions()
    if not regions:
        print("names/regions.toml: absent or empty — run `regions.py seed`",
              file=sys.stderr)
        return 2
    hdr = f"{'span':24} {'width':>10}  {'kind':14} {'bound':24} name"
    print(hdr)
    print("-" * len(hdr))
    for base, end, r in regions:
        span = f"0x{base:08X}..0x{end:08X}" if end else f"0x{base:08X}.. (no end)"
        width = f"{end - base:,}" if end else "—"
        name = r.get("alias") or r.get("name")
        nature = r.get("nature") or ""
        print(f"{span:24} {width:>10}  {r.get('kind', ''):14}"
              f" {r.get('bound', ''):24} {name}"
              + (f"  — {nature}" if nature else ""))
    contains, partial = [], []
    for i, (b1, e1, r1) in enumerate(regions):
        for b2, e2, r2 in regions[i + 1:]:
            if not (e1 and e2) or b2 >= e1 or b1 >= e2:
                continue
            pair = (r1.get("name"), r2.get("name"), max(b1, b2), min(e1, e2))
            # one inside the other is the layout working as described (every band
            # sits in the EXE image); a straddle is the interesting case
            if (b1 <= b2 and e2 <= e1) or (b2 <= b1 and e1 <= e2):
                contains.append(pair)
            else:
                partial.append(pair)
    print(f"\n{len(contains)} containment(s) by construction, and"
          f" {len(partial)} partial overlap(s) — legitimate, because the"
          f" occupants are resident at different times:")
    for a, b, lo, hi in partial:
        print(f"  {a} straddles {b}  0x{lo:08X}..0x{hi:08X}  ({hi - lo:,} bytes)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seed and check names/regions.toml.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("seed", help="merge derived regions into names/regions.toml")
    p.set_defaults(fn=cmd_seed)
    p = sub.add_parser("check", help="re-derive and compare; nonzero on drift")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("list", help="print the region map and its overlaps")
    p.set_defaults(fn=cmd_list)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
