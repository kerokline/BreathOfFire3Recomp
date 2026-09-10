#!/usr/bin/env python
"""Ability -> battle-effect overlay, read off the disc (docs/OVERLAY_HEADERS.md
"The loader and the spell->overlay link").

The battle engine (BATTLE.EMI#15 at 0x80093800) loads a spell's effect overlay
through the boot loader `File_LoadRequest(file_id)` (0x801629CC), and picks the
file with two tables of its own:

    row      = u8 [0x800B3450 + ability_id]           (227 abilities, 232 B)
    file_id  = u16[0x800B3538 + row*8]                 (151 rows; 0xFFFF = engine-side handler)
    entry    = u32[0x800B3538 + row*8 + 4]             (handler pc inside the loaded image, or the engine)

`file_id` indexes the boot EXE's LBA table (tools/file_ids.py), so every row
names a BIN/BMAGIC/*.EMI file; that file's code section is the overlay, and its
first word is the registry id. Items go through the same row table via four
u8 sub-tables selected by a 16-bit id's high byte (pointer list 0x800B39F0).

Writes names/magic.toml (one row per ability) and, with --alias-overlays,
labels every BMAGIC row of names/overlays.toml with the abilities that load it.

    python tools/magic_map.py                     # names/magic.toml + summary
    python tools/magic_map.py --alias-overlays    # also fill overlays.toml aliases (hand aliases are kept)
"""
import argparse
import base64
import collections
import json
import os
import struct
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import name_map  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES = os.path.join(ROOT, "analysis", "overlay_captures_all.json")
FILE_IDS = os.path.join(ROOT, "analysis", "file_ids.json")
SURVEY = os.path.join(ROOT, "analysis", "emi_sections.json")
ABILITIES = os.path.join(ROOT, "names", "abilities.toml")
OUT = os.path.join(ROOT, "names", "magic.toml")

ENGINE_FILE, ENGINE_INDEX = "BIN/BATTLE/BATTLE.EMI", 15
ABILITY_ROW_TABLE = 0x800B3450
ROW_TABLE = 0x800B3538
ROW_COUNT = 151
ITEM_PTR_TABLE = 0x800B39F0
LOADER = 0x801629CC
# file ids seen loading live (callstack_diff capture --watch 0x80146464 on a cast):
# rows for these are emitted at status = verified
VERIFIED_FILE_IDS = {0x156: "cast_magic.json 2026-09-08 f+336 (Nina, Rejuvenate)",
                     0x170: "cast_magic.json 2026-09-08 f+724 (Nina, Typhoon)"}

HEADER = """\
# names/magic.toml -- which BMAGIC overlay each ability loads, read off the disc
# by tools/magic_map.py (docs/OVERLAY_HEADERS.md "The loader and the spell->overlay link").
#
#   id        ability id (names/abilities.toml)
#   row       u8[0x800B3450 + id] -> row of the engine's effect table 0x800B3538
#   file_id   u16 in that row = index into the boot LBA table 0x80182DBC (tools/file_ids.py)
#   file      the BIN/BMAGIC/*.EMI it names ("" when file_id = 0xFFFF: engine-side handler)
#   section   md5 of that file's code section = the overlay row in names/overlays.toml
#   overlay_id  the registry id at +0x00 of that section
#   entry     u32 in the row: the handler pc (inside the loaded image, or the engine)
#   status    evidence = static chain, three-way consistent (file numbering, entry inside
#             the image, LBA table); verified = a live cast seen loading the file
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--alias-overlays", action="store_true",
                    help="write ability aliases into BMAGIC rows of names/overlays.toml (keeps hand aliases)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    caps = json.load(open(CAPTURES, encoding="utf-8"))
    fid = {int(r["id"], 16): r["path"] for r in json.load(open(FILE_IDS, encoding="utf-8"))}
    survey = json.load(open(SURVEY, encoding="utf-8"))["sections"]
    code_md5 = {}                       # file path -> md5 of its code section
    for s in survey:
        if "/BMAGIC/" in s["file"] and s["class"] in ("code", "mixed"):
            code_md5[s["file"]] = s["md5"]
    cap_by_md5 = {c["source_md5"]: c for c in caps}
    abilities = tomllib.load(open(ABILITIES, "rb"))["ability"]

    eng = [c for c in caps if c["source_file"] == ENGINE_FILE and c["source_index"] == ENGINE_INDEX][0]
    b = base64.b64decode(eng["bytes_b64"])
    base = int(eng["load_addr"], 16)
    rows = [struct.unpack_from("<HHI", b, ROW_TABLE - base + i * 8) for i in range(ROW_COUNT)]
    ability_row = [b[ABILITY_ROW_TABLE - base + i] for i in range(len(abilities))]

    out_rows, per_md5 = [], collections.defaultdict(list)
    for ab in abilities:
        i = ab["id"]
        row = ability_row[i]
        f, _, entry = rows[row]
        path = fid.get(f, "") if f != 0xFFFF else ""
        md5 = code_md5.get(path, "")
        cap = cap_by_md5.get(md5)
        rec = {
            "id": i, "jp": ab["jp"], "en": ab.get("en", ""), "type": ab["type"],
            "row": row, "file_id": "0x%03X" % f, "file": path.split("/")[-1] if path else "",
            "section": md5, "overlay_id": (cap or {}).get("registry_id", ""),
            "entry": "0x%08X" % entry,
            "status": "evidence" if path else "engine",
        }
        if path and not cap:
            rec["status"] = "unmatched"
        if f in VERIFIED_FILE_IDS and cap:
            rec["status"] = "verified"
            rec["live"] = VERIFIED_FILE_IDS[f]
        if cap:
            lo = int(cap["load_addr"], 16)
            rec["entry_in_image"] = lo <= entry < lo + int(cap["size"])
            per_md5[md5].append(rec)
        out_rows.append(rec)

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(name_map._emit_table("ability", out_rows, HEADER))

    n_file = sum(1 for r in out_rows if r["file"])
    n_in = sum(1 for r in out_rows if r.get("entry_in_image"))
    n_un = sum(1 for r in out_rows if r["status"] == "unmatched")
    print("magic.toml: %d abilities, %d load a BMAGIC file (%d distinct sections), "
          "%d engine-side, %d unmatched; entry inside the image for %d/%d"
          % (len(out_rows), n_file, len(per_md5), len(out_rows) - n_file, n_un, n_in, n_file))
    used_rows = {r["row"] for r in out_rows}
    print("effect rows used by abilities: %d of %d (the rest are reached by items via 0x800B39F0)"
          % (len(used_rows), ROW_COUNT))

    if a.alias_overlays:
        existing = name_map.load_overlay_names()
        rows_out, changed = [], 0
        for md5, r in existing.items():
            r = dict(r)
            # evidence outranks the filename-derived hypothesis rows; hand-written
            # evidence/verified aliases are kept
            if md5 in per_md5 and (not r.get("alias") or r.get("status") in ("unnamed", "hypothesis")
                                   or str(r.get("evidence", "")).startswith("magic_map.py")):
                names = []
                for rec in per_md5[md5]:
                    nm = rec["en"] or rec["jp"]
                    if nm not in names:
                        names.append(nm)
                extra = " (+%d)" % (len(names) - 6) if len(names) > 6 else ""
                r["alias"] = "Battle FX: " + ", ".join(names[:6]) + extra
                rws = sorted({x["row"] for x in per_md5[md5]})
                r["role"] = "battle effect overlay for %d abilit%s (row%s %s)" % (
                    len(per_md5[md5]), "y" if len(per_md5[md5]) == 1 else "ies",
                    "" if len(rws) == 1 else "s", ", ".join(str(x) for x in rws))
                fid0 = int(per_md5[md5][0]["file_id"], 16)
                live = VERIFIED_FILE_IDS.get(fid0)
                r["status"] = "verified" if live else "evidence"
                r["evidence"] = ("magic_map.py 2026-09-08: ability id -> u8 0x800B3450 -> row of 0x800B3538 "
                                 "(file id %s = this file via the boot LBA table 0x80182DBC); entry %s lies inside "
                                 "this image" % (per_md5[md5][0]["file_id"], per_md5[md5][0]["entry"]))
                if live:
                    r["evidence"] += ("; LIVE: %s -- File_LoadRequest called with this file id from "
                                      "Magic_LoadForAbility, then the band header word became this image's "
                                      "registry id" % live)
                changed += 1
            rows_out.append(r)
        with open(name_map.OVERLAYS_TOML, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(name_map._emit_table("overlay", rows_out, name_map.OVERLAYS_HEADER))
        print("overlays.toml: %d BMAGIC rows aliased" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
