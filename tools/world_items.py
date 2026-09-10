#!/usr/bin/env python
"""Static extractor for the BoF3 world "search spot" table -- every dresser, pot,
barrel and patch of ground the game lets you search, for all 200 areas, read
straight off the disc with no play session.

    python tools/world_items.py --cue "isos/Breath of Fire III (Japan).cue"
    python tools/world_items.py --area 27          # one area, printed in full

## How the game does it (traced 2026-09-07, docs/WORLD_ITEMS.md)

The field handler `GAME.EMI 0x801B3FC0` answers the search button. It asks
`0x801B6C4C` which spot the player is facing; that walks a per-area array of
**8-byte records**:

    +0 u8  X tile          +4 u8  progress-flag index (0xFF = no flag)
    +1 u8  Y tile          +5 u8  item id  /  zenny amount / 40
    +2 u8  flags (0x80 = the run extends along Y, not X)
    +3 u8  run length in tiles (0 = record disabled)
    +6 u8  item CATEGORY (0xFF = zenny)      +7 u8  (always 0 so far)

The handler then:

    if Flag_Test(0x80145000, rec[4]):  message 1   -- already taken
    elif rec[6] == 0xFF:               Field_GiveZenny(rec[5] * 40)
    else:                              Inventory_Add(rec[6], rec[5], 1)
                                       message 2 (got it) / 3 (no room)
    on success and rec[4] != 0xFF:     Flag_Set(0x80145000, rec[4])
                                       *(u32 *)0x80145030 += 1

`0x80145000` is the world-item bit array (distinct from the story-progress
array at `0x80144F24`), and `0x80145030` counts how many spots have been
emptied. Both sit inside the save image, so they persist.

## Why this is static

The array is reached through a table that is **constant data in the boot EXE**:

    struct_ptr = *(u32 *)(0x801802EC + area * 4)      -- 200 entries, boot EXE
    records    = *(u32 *)(struct_ptr + 0x2C)
    count      = *(u8  *)(struct_ptr + 0x31)          -- n = count + 1

Every entry points into `0x801F2C00`, the per-area section each `AREAnnn.EMI`
carries. So the boot EXE says *where* in the area section the array sits and
the area file supplies the bytes -- no emulator needed. Verified against the
live game on AREA027 (struct 0x801F4D20, array 0x801F3BBC, 72 records,
record 35 = the dresser worth 120 zenny).
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

try:
    import tomllib
except ImportError:                                   # pragma: no cover
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREA_TABLE = 0x801802EC          # boot EXE: 200 x u32 -> per-area struct
AREA_SECTION_DEST = 0x801F2C00   # the section each AREA file loads there
OFF_RECORDS = 0x2C               # struct + 0x2C -> record array pointer
OFF_COUNT = 0x31                 # struct + 0x31 -> record count - 1
REC_SIZE = 8
ZENNY_CAT = 0xFF                 # rec[6] == 0xFF means "zenny", not an item
ZENNY_UNIT = 40                  # rec[5] * 40 zenny
EMPTY_MASK = 0x80                # rec[5] & 0x80: searchable but holds nothing
                                 # (0x80 and 0xC0 are the two sentinels seen;
                                 #  no real id in any of the five tables reaches 0x80)
FLAG_BASE = 0x80145000           # the world-item bit array
# Inventory category numbering, read off names/items.toml's own `cat` field and
# BATTLE_RAM.md (0x80145048 = 4 x 128 ids; key items are a SEPARATE list at
# 0x80145448, which is why the key rows in names/items.toml carry no `cat`).
CATEGORIES = {0: "consumable", 1: "weapon", 2: "armour", 3: "accessory", 4: "key"}


# ----------------------------------------------------------------- inputs

def load_boot(path):
    raw = open(path, "rb").read()
    t_addr, = struct.unpack_from("<I", raw, 0x18)
    return raw[0x800:], t_addr


def area_struct_ptrs(boot, t_addr, n=200):
    return list(struct.unpack_from("<%dI" % n, boot, AREA_TABLE - t_addr))


def disc_area_files(cue):
    """-> (sector reader, {area id: (name, extent, size)}, disc mode)."""
    data = open(disc_ls.resolve_cue(cue), "rb").read()
    read, mode = disc_ls.make_reader(data)
    pvd = read(16)
    extent = struct.unpack_from("<I", pvd, 158)[0]
    size = struct.unpack_from("<I", pvd, 166)[0]
    out = {}
    for name, ext, sz, is_dir in disc_ls.walk(read, extent, size):
        m = re.search(r"AREA(\d{3})\.EMI", name, re.I)
        if m and not is_dir:
            out[int(m.group(1))] = (name, ext, sz)
    return read, out, mode


def area_section(read, ext, sz):
    """The AREAnnn.EMI section whose destination is 0x801F2C00."""
    blob = disc_ls.read_extent(read, ext, sz)
    e = emilib.Emi(blob)
    for entry in e.entries:
        if entry["dest"] == AREA_SECTION_DEST:
            return e.data(entry["index"])
    return None


# ----------------------------------------------------------------- names

def load_names():
    items, places = {}, {}
    if tomllib is None:
        return items, places
    p = os.path.join(ROOT, "names", "items.toml")
    if os.path.exists(p):
        for it in tomllib.load(open(p, "rb")).get("item", []):
            # Trust the `cat` field only. The key rows have none (separate list);
            # park them at 4 so they cannot collide with weapons at cat 1 -- no
            # search-spot record uses cat 4, so nothing depends on that guess.
            cat = it.get("cat", 4 if it.get("category") == "key" else None)
            if cat is None or "id" not in it:
                continue
            items[(cat, it["id"])] = (it.get("jp", ""), it.get("en", ""))
    p = os.path.join(ROOT, "names", "places.toml")
    if os.path.exists(p):
        for pl in tomllib.load(open(p, "rb")).get("place", []):
            key = pl.get("id", pl.get("area"))
            if key is not None:
                places[key] = (pl.get("jp", ""), pl.get("en", ""))
    return items, places


# ----------------------------------------------------------------- decode

def decode_area(section, struct_ptr, items):
    """-> (records, note). `section` is the 0x801F2C00 blob."""
    end = AREA_SECTION_DEST + len(section)

    def inside(a, n=1):
        return AREA_SECTION_DEST <= a and a + n <= end

    if not inside(struct_ptr, OFF_COUNT + 1):
        return [], "struct 0x%08X outside the area section (0x%08X..0x%08X)" % (
            struct_ptr, AREA_SECTION_DEST, end)
    so = struct_ptr - AREA_SECTION_DEST
    arr, = struct.unpack_from("<I", section, so + OFF_RECORDS)
    cnt = section[so + OFF_COUNT]
    if cnt == 0xFF:
        return [], "count byte 0xFF -- no search spots"
    if arr == 0:
        # the common shape for an area with nothing to search: null array, count 0
        return [], "no search spots (null array pointer)"
    n = cnt + 1
    if not inside(arr, n * REC_SIZE):
        return [], "record array 0x%08X x%d outside the section" % (arr, n)
    ao = arr - AREA_SECTION_DEST
    out = []
    for i in range(n):
        r = section[ao + i * REC_SIZE: ao + (i + 1) * REC_SIZE]
        x, y, fl, run, flag, iid, cat, tail = r
        rec = {"index": i, "addr": "0x%08X" % (arr + i * REC_SIZE),
               "x": x, "y": y, "axis": "y" if fl & 0x80 else "x",
               "flags": fl, "run": run, "flag_index": flag,
               "item_id": iid, "category": cat, "tail": tail,
               "bytes": r.hex()}
        if run == 0:
            rec["kind"] = "disabled"
        elif cat == ZENNY_CAT:
            rec["kind"] = "zenny"
            rec["zenny"] = iid * ZENNY_UNIT
        elif iid & EMPTY_MASK:
            rec["kind"] = "empty"
            rec["empty_code"] = iid
        else:
            rec["kind"] = "item"
            rec["category_name"] = CATEGORIES.get(cat, "cat%d" % cat)
            jp, en = items.get((cat, iid), ("", ""))
            rec["item_jp"], rec["item_en"] = jp, en
        if flag != 0xFF:
            rec["flag_addr"] = "0x%08X" % (FLAG_BASE + (flag >> 3))
            rec["flag_bit"] = flag & 7
        out.append(rec)
    return out, ""


def describe(rec):
    if rec["kind"] == "zenny":
        return "%d zenny" % rec["zenny"]
    if rec["kind"] == "empty":
        return "-- nothing --"
    if rec["kind"] == "disabled":
        return "(disabled)"
    return "%s #%d %s %s" % (rec.get("category_name"), rec["item_id"],
                             rec.get("item_jp", ""), rec.get("item_en", ""))


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cue", default="isos/Breath of Fire III (Japan).cue")
    ap.add_argument("--boot", default="disc/SLPS_009.90")
    ap.add_argument("--area", type=int, help="only this area, printed in full")
    ap.add_argument("--json", default="analysis/world_items.json")
    a = ap.parse_args()

    boot, t_addr = load_boot(os.path.join(ROOT, a.boot))
    ptrs = area_struct_ptrs(boot, t_addr)
    items, places = load_names()
    read, areas, mode = disc_area_files(os.path.join(ROOT, a.cue))
    print("disc %s, %d AREA files, boot .text at 0x%08X" % (mode, len(areas), t_addr))

    result, problems = {}, []
    todo = [a.area] if a.area is not None else sorted(areas)
    for aid in todo:
        if aid not in areas:
            problems.append((aid, "no AREA%03d.EMI on the disc" % aid))
            continue
        name, ext, sz = areas[aid]
        sec = area_section(read, ext, sz)
        if sec is None:
            problems.append((aid, "no 0x801F2C00 section in %s" % name))
            continue
        recs, note = decode_area(sec, ptrs[aid], items)
        if note:
            problems.append((aid, note))
        result[aid] = {"area": aid, "file": name, "struct": "0x%08X" % ptrs[aid],
                       "records": recs, "note": note,
                       "place_jp": places.get(aid, ("", ""))[0],
                       "place_en": places.get(aid, ("", ""))[1]}

    if a.area is not None:
        r = result.get(a.area, {})
        print("\nAREA%03d %s %s  struct %s  %d records  %s"
              % (a.area, r.get("place_jp", ""), r.get("place_en", ""), r.get("struct"),
                 len(r.get("records", [])), r.get("note", "")))
        print("  %-3s %-17s %-11s %-4s %-5s %s"
              % ("#", "bytes", "tile", "run", "flag", "gives"))
        for rec in r.get("records", []):
            print("  %-3d %-17s (%3d,%3d)%s %-4d %-5s %s"
                  % (rec["index"], rec["bytes"], rec["x"], rec["y"], rec["axis"],
                     rec["run"], "0x%02X" % rec["flag_index"], describe(rec)))
        return 0

    # ---- corpus summary
    tot = {"zenny": 0, "item": 0, "empty": 0, "disabled": 0}
    zsum = 0
    flags_used = set()
    cat_ids = {}
    unnamed = 0
    for aid, r in result.items():
        for rec in r["records"]:
            tot[rec["kind"]] += 1
            if rec["kind"] == "zenny":
                zsum += rec["zenny"]
            if rec["kind"] == "item":
                cat_ids.setdefault(rec["category"], set()).add(rec["item_id"])
                if not rec.get("item_jp"):
                    unnamed += 1
            if rec["flag_index"] != 0xFF:
                flags_used.add(rec["flag_index"])
    print("\n%d areas decoded, %d records total" % (len(result), sum(tot.values())))
    for k in ("item", "zenny", "empty", "disabled"):
        print("  %-9s %d" % (k, tot[k]))
    print("  zenny total across the world: %d" % zsum)
    print("  item records with no name row: %d" % unnamed)
    print("  distinct flag indices used: %d (max 0x%02X)"
          % (len(flags_used), max(flags_used) if flags_used else 0))
    for c in sorted(cat_ids):
        ids = cat_ids[c]
        print("  category %d (%-10s) ids %d..%d, %d distinct"
              % (c, CATEGORIES.get(c, "?"), min(ids), max(ids), len(ids)))
    if problems:
        print("\n%d area(s) with notes:" % len(problems))
        for aid, why in problems[:20]:
            print("  AREA%03d: %s" % (aid, why))

    out = os.path.join(ROOT, a.json)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"areas": [result[k] for k in sorted(result)]},
              open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\nwrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
