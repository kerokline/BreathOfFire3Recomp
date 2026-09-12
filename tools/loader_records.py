#!/usr/bin/env python
"""The engine's own entry records for AREA and SCENARIO overlays, read off the disc.

The field engine does not enter an AREA image through the overlay header: the
boot EXE keeps a 200-entry pointer table at 0x801802EC, indexed by the area
number (u16[0x80143F00]), and each pointer lands on a 0x44-byte descriptor at
the END of that area's 0x801F2C00 section. GAME.EMI `FUN_801a0aa8` loads
`area + 0x2AB`, spins on File_LoadDone, then calls `desc+0x40` (one-shot init,
may be 0); the field-script opcodes 0x03/0xDE and the entity dispatch at
0x801ADE10 call `u32[desc+0x3C][k]`, an array of native handlers that runs up
to the descriptor itself. Every one of those pcs is an interior entry reached
only by `jalr`, invisible to the JAL / prologue / header seeds (intersection
with the header tables is 0), and exactly what a play session would otherwise
have to harvest.

SCENARIO is the same shape one level up: GAME.EMI holds a 20-entry table at
0x801C944C indexed by the chapter (s8[0x8014686C]); `FUN_801a880c` loads
`0x295 + chapter` and `FUN_801a8834` calls `u32[u32[table[c]]]`, the first word
of the pointed-at struct inside SCENA<cc>.EMI at 0x801F6C00.

BOSS is the exact magic shape, one table each side: GAME.EMI's
Boss_EncounterTable 0x801CDF18 (56 x {flags, arena, formation, row}) and
Boss_FileTable 0x801CDFF8 (u16 file id per row) pick the BOSS<nnn>.EMI bundle
for boss id u8[0x801462E6]; the battle engine then jalr's
u32[0x800B2048 + id*4] (Boss_EntryTable, 0x800A8B40), a pc inside that
bundle's 0x800C1800 section. PLCHAR is keyed by the party combo index
(0..18, PLP<combo>.EMI = file 0x27D + index); GAME.EMI enters the resident
image through two u32[19] tables, 0x801CD8F0 (jalr 0x801B46B0) and
0x801CD964 (jalr 0x801B3C78 / 0x801BE508), and each image's last six words
are a u32[2][3] per-party-slot dispatch those two thunks index.

All four were found 2026-09-12 (docs/OVERLAY_HEADERS.md "Loader records").

    python tools/loader_records.py            # -> names/{area,scenario,boss,plchar}_records.toml

Output rows carry the section md5 and the entry pc, which is what
tools/extract_overlays.py joins on (ENGINE_RECORD_FILES). Nothing here invents
bytes: a pc is emitted only when it is 4-aligned and inside the section the
record belongs to; anything else is reported and dropped.
"""
import argparse
import base64
import json
import os
import struct
import sys

EXE = "disc/SLPS_009.90"
EXE_LOAD = 0x80093000            # file offset 0 = 0x80093000 (0x800 header)
CAPTURES = "analysis/overlay_captures_all.json"

AREA_TABLE = 0x801802EC          # boot EXE, u32[200], index = area number
AREA_COUNT = 200
AREA_BAND = 0x801F2C00
AREA_FILE0 = 0x2AB               # AREA000.EMI disc-file id
DESC_INIT = 0x40                 # one-shot init handler (or 0)
DESC_HANDLERS = 0x3C             # -> u32[] native handlers, bounded by the descriptor
DESC_SIZE = 0x44
WORLD_MAP_AREAS = (30, 89, 129)  # share the world-map code; their descriptor is not this type

SCEN_TABLE = 0x801C944C          # in GAME.EMI#0 (0x80196800), u32[20], index = chapter
SCEN_COUNT = 20
SCEN_BAND = 0x801F6C00
SCEN_FILE0 = 0x295               # SCENA00.EMI
SCEN_VTABLE_SLOTS = 5            # record = 5-slot vtable; GAME.EMI thunks 0x801A8834/8880/891C/89AC/8A3C
SCEN_SUBTABLES = ((0x801CDC4C, "A"), (0x801CDC9C, "B"))  # u32[20] -> u32[] inside the image,
                                 # indexed by a u8 from Scenario_CallA/B 0x801C2DE8 / 0x801C2E34

AREA_HOOK_TABLE = 0x801C8F54     # GAME.EMI#0: 11 x 0x1C {u32 pc[6], u8 area, ...}, row by Area_HookRow 0x8019B19C
AREA_HOOK_STRIDE = 0x1C
AREA_HOOK_ROWS = 11
AREA_HOOK_PCS = 6
AREA_HOOK_KEY = 0x18
AREA_HOOK_TABLE2 = 0x801C95BC    # GAME.EMI#0: u32[11], same row
GAME_EMI = "BIN/ETC/GAME.EMI"
GAME_BAND = 0x80196800

FILE_IDS = "analysis/file_ids.json"
SECTIONS = "analysis/emi_sections.json"

BOSS_ID_CELL = 0x801462E6
BOSS_ENC_TABLE = 0x801CDF18      # GAME.EMI#0: 56 x {u8 flags, u8 arena, u8 formation, u8 row}
BOSS_COUNT = 56
BOSS_FILE_TABLE = 0x801CDFF8     # GAME.EMI#0: u16 file id per row (row 0 = BATTLE.EMI)
BOSS_ENTRY_TABLE = 0x800B2048    # battle engine image (0x80093800): u32 entry per boss id
BOSS_BAND = 0x800C1800
BATTLE_ENGINE = ("BIN/BATTLE/BATTLE.EMI", 0x80093800)

PLP_FILE0 = 0x27D                # PLP<combo>.EMI, 19 combos
PLP_COUNT = 19
PLP_BAND = 0x801CE400
PLP_TABLES = ((0x801CD8F0, "A"), (0x801CD964, "B"))   # GAME.EMI#0, u32[19] each
PLP_TAIL_WORDS = 6               # u32[2][3] per-slot dispatch at the end of every PLP image


class Image:
    def __init__(self, cap):
        self.cap = cap
        self.lo = int(cap["load_addr"], 16)
        self.data = base64.b64decode(cap["bytes_b64"])
        self.hi = self.lo + len(self.data)

    def inside(self, a):
        return self.lo <= a < self.hi and not a & 3

    def u32(self, a):
        return struct.unpack_from("<I", self.data, a - self.lo)[0]


def load_captures(path):
    caps = json.load(open(path))
    return [Image(c) for c in caps]


def exe_u32(exe, a):
    return struct.unpack_from("<I", exe, a - EXE_LOAD)[0]


def area_number(cap):
    f = cap["source_file"].upper()
    if "/AREA" not in f:
        return None
    return int(f.split("/AREA")[1][:3])


def area_records(exe, images):
    """rows, notes for the 200-entry area descriptor table."""
    by_area = {}
    for im in images:
        n = area_number(im.cap)
        if n is not None and im.lo == AREA_BAND:
            by_area[n] = im
    rows, notes = [], []
    for n in range(AREA_COUNT):
        desc = exe_u32(exe, AREA_TABLE + n * 4)
        im = by_area.get(n)
        if im is None:
            notes.append("area %d: no compiled %#x section (data-classed), descriptor %#x unread" % (n, AREA_BAND, desc))
            continue
        if n in WORLD_MAP_AREAS:
            notes.append("area %d: world map, descriptor type differs, skipped" % n)
            continue
        if not (im.lo <= desc <= im.hi - DESC_SIZE):
            notes.append("area %d: descriptor %#x outside its section %#x..%#x" % (n, desc, im.lo, im.hi))
            continue
        base = dict(area=n, file=im.cap["source_file"], section=im.cap["source_md5"],
                    descriptor="0x%08X" % desc)
        init = im.u32(desc + DESC_INIT)
        if init:
            if im.inside(init):
                rows.append(dict(base, entry="0x%08X" % init, kind="init"))
            else:
                notes.append("area %d: +0x40 %#x outside section, dropped" % (n, init))
        arr = im.u32(desc + DESC_HANDLERS)
        if arr:
            if not im.inside(arr):
                notes.append("area %d: +0x3C %#x outside section, dropped" % (n, arr))
            else:
                a, k = arr, 0
                # Bounded by the descriptor: the array sits directly below it and
                # an unbounded walk would read the descriptor's own pointers back.
                while a < desc and im.inside(im.u32(a)):
                    rows.append(dict(base, entry="0x%08X" % im.u32(a), kind="handler[%d]" % k))
                    a += 4
                    k += 1
    # GAME.EMI's own per-area hook rows: 11 areas get six extra pcs each plus
    # one more in a parallel u32[11]; the row is found by matching the area
    # number byte at +0x18 (Area_HookRow 0x8019B19C).
    game = find_game(images)
    for r in range(AREA_HOOK_ROWS):
        row = AREA_HOOK_TABLE + r * AREA_HOOK_STRIDE
        n = game.data[row + AREA_HOOK_KEY - game.lo]
        im = by_area.get(n)
        if im is None:
            notes.append("hook row %d: area %d has no compiled section" % (r, n))
            continue
        base = dict(area=n, file=im.cap["source_file"], section=im.cap["source_md5"],
                    descriptor="0x%08X" % row)
        pcs = [game.u32(row + k * 4) for k in range(AREA_HOOK_PCS)] + [game.u32(AREA_HOOK_TABLE2 + r * 4)]
        for k, e in enumerate(pcs):
            if e == 0:
                continue
            if im.inside(e):
                rows.append(dict(base, entry="0x%08X" % e, kind="hook[%d]" % k))
            else:
                notes.append("hook row %d (area %d): pc %d = %#x outside section, dropped" % (r, n, k, e))
    return rows, notes


def scenario_records(images):
    game = next((im for im in images if im.cap["source_file"].upper() == GAME_EMI and im.lo == GAME_BAND), None)
    if game is None:
        raise SystemExit("GAME.EMI#0 at %#x not in %s" % (GAME_BAND, CAPTURES))
    by_ch = {}
    for im in images:
        name = os.path.basename(im.cap["source_file"]).upper()   # SCENA00.EMI, not SCENARIO/
        if name.startswith("SCENA") and name[5:7].isdigit() and im.lo == SCEN_BAND:
            by_ch[int(name[5:7])] = im
    rows, notes = [], []
    for c in range(SCEN_COUNT):
        sp = game.u32(SCEN_TABLE + c * 4)
        im = by_ch.get(c)
        if im is None:
            notes.append("chapter %d: no compiled SCENA%02d section" % (c, c))
            continue
        base = dict(chapter=c, file=im.cap["source_file"], section=im.cap["source_md5"])
        if not im.inside(sp):
            notes.append("chapter %d: vtable %#x outside SCENA%02d" % (c, sp, c))
        else:
            for k in range(SCEN_VTABLE_SLOTS):
                e = im.u32(sp + k * 4)
                if e == 0:
                    continue          # slot +0x10 is optional and null-checked
                if im.inside(e):
                    rows.append(dict(base, table="0x%08X" % sp, entry="0x%08X" % e, kind="vtable[%d]" % k))
                else:
                    notes.append("chapter %d: vtable slot %d = %#x outside SCENA%02d, dropped" % (c, k, e, c))
        for tbl, tag in SCEN_SUBTABLES:
            arr = game.u32(tbl + c * 4)
            if arr == 0:
                continue              # SCENA00 has no B sub-table
            if not im.inside(arr):
                notes.append("chapter %d: sub-table %s %#x outside SCENA%02d" % (c, tag, arr, c))
                continue
            # Walk while the words are in-image code addresses. A and B sit
            # next to each other, so this is an upper bound on the length; every
            # word it yields is still a real pc inside the image.
            a, k = arr, 0
            while a + 4 <= im.hi and im.inside(im.u32(a)):
                rows.append(dict(base, table="0x%08X" % arr, entry="0x%08X" % im.u32(a), kind="sub%s[%d]" % (tag, k)))
                a += 4
                k += 1
    return rows, notes


def file_paths():
    return {int(r["id"], 16): r["path"] for r in json.load(open(FILE_IDS))}


def survey_md5s():
    """{(disc path upper, dest): md5} for every surveyed section."""
    return {(sec["file"].upper(), sec["dest"]): sec["md5"]
            for sec in json.load(open(SECTIONS))["sections"]}


def find_game(images):
    game = next((im for im in images if im.cap["source_file"].upper() == GAME_EMI and im.lo == GAME_BAND), None)
    if game is None:
        raise SystemExit("GAME.EMI#0 at %#x not in %s" % (GAME_BAND, CAPTURES))
    return game


def boss_records(images):
    """Boss id -> (BOSS file, 0x800C1800 section, entry pc) via the three tables.

    The capture set dedups identical sections, so several BOSS files share one
    capture; the join is by the file's section md5 from the survey, which maps
    to the deduped capture, never by filename.
    """
    game = find_game(images)
    engine = next((im for im in images if (im.cap["source_file"].upper(), im.lo) == BATTLE_ENGINE), None)
    if engine is None:
        raise SystemExit("battle engine %s@%#x not in captures" % BATTLE_ENGINE)
    paths, md5s = file_paths(), survey_md5s()
    by_md5 = {im.cap["source_md5"]: im for im in images if im.lo == BOSS_BAND}
    rows, notes = [], []
    for bid in range(1, BOSS_COUNT):
        row = game.data[BOSS_ENC_TABLE + bid * 4 + 3 - game.lo]
        fid = struct.unpack_from("<H", game.data, BOSS_FILE_TABLE + row * 2 - game.lo)[0]
        path = paths.get(fid, "")
        entry = engine.u32(BOSS_ENTRY_TABLE + bid * 4)
        if "/BOSS/" not in path.upper():
            notes.append("boss %d: row %d -> file %#x %s is not a BOSS bundle, skipped" % (bid, row, fid, path))
            continue
        md5 = md5s.get((path.upper(), BOSS_BAND))
        im = by_md5.get(md5)
        if im is None:
            notes.append("boss %d: %s has no compiled %#x capture" % (bid, path, BOSS_BAND))
            continue
        if not im.inside(entry):
            notes.append("boss %d: entry %#x outside %s %#x..%#x, dropped" % (bid, entry, path, im.lo, im.hi))
            continue
        rows.append(dict(boss=bid, file=path, section=md5, file_id="0x%03X" % fid,
                         entry="0x%08X" % entry, kind="boss"))
    return rows, notes


def plchar_records(images):
    """Combo index -> PLP<combo>.EMI entry pcs: GAME.EMI's two u32[19] tables
    plus the six-word per-slot dispatch the thunks they point at index."""
    game = find_game(images)
    paths, md5s = file_paths(), survey_md5s()
    by_md5 = {im.cap["source_md5"]: im for im in images if im.lo == PLP_BAND}
    rows, notes = [], []
    for idx in range(PLP_COUNT):
        path = paths.get(PLP_FILE0 + idx, "")
        im = by_md5.get(md5s.get((path.upper(), PLP_BAND)))
        if im is None or "/PLP" not in path.upper():
            notes.append("combo %d: file %#x %s has no compiled %#x capture" % (idx, PLP_FILE0 + idx, path, PLP_BAND))
            continue
        base = dict(combo=idx, file=path, section=im.cap["source_md5"], file_id="0x%03X" % (PLP_FILE0 + idx))
        for tbl, tag in PLP_TABLES:
            e = game.u32(tbl + idx * 4)
            if im.inside(e):
                rows.append(dict(base, entry="0x%08X" % e, kind="table%s" % tag))
            else:
                notes.append("combo %d: table %s entry %#x outside %s, dropped" % (idx, tag, e, path))
        for k in range(PLP_TAIL_WORDS):
            a = im.hi - PLP_TAIL_WORDS * 4 + k * 4
            e = im.u32(a)
            if im.inside(e):
                rows.append(dict(base, entry="0x%08X" % e, kind="slot[%d][%d]" % (k // 3, k % 3)))
            else:
                notes.append("combo %d: tail word %d = %#x not in image, dropped" % (idx, k, e))
    return rows, notes


def write_toml(path, header, rows, key_order):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header)
        for r in rows:
            fh.write("\n[[record]]\n")
            for k in key_order:
                v = r[k]
                fh.write("%s = %s\n" % (k, v if isinstance(v, int) else '"%s"' % v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", default=CAPTURES)
    ap.add_argument("--exe", default=EXE)
    ap.add_argument("--out-dir", default="names")
    args = ap.parse_args()

    exe = open(args.exe, "rb").read()
    images = load_captures(args.captures)

    rows, notes = area_records(exe, images)
    distinct = {(r["section"], r["entry"]) for r in rows}
    rows.sort(key=lambda r: (r["area"], r["kind"] != "init", r["kind"]))
    write_toml(os.path.join(args.out_dir, "area_records.toml"),
               "# names/area_records.toml -- the field engine's entry records for AREA overlays,\n"
               "# read off the disc by tools/loader_records.py (docs/OVERLAY_HEADERS.md \"Loader records\").\n"
               "#   area        area number = index into the boot table 0x801802EC\n"
               "#   descriptor  the 0x44-byte descriptor at the end of the area's 0x801F2C00 section\n"
               "#   entry       a pc the engine jalr's into: kind = init (desc+0x40), handler[k] (u32[desc+0x3C][k]),\n"
               "#               or hook[k] (GAME.EMI's 11-row Area_HookTable 0x801C8F54 / 0x801C95BC, descriptor = the row)\n"
               "#   section     md5 of the code section (joins names/overlays.toml and the capture set)\n",
               rows, ("area", "file", "section", "descriptor", "kind", "entry"))
    print("area: %d rows, %d distinct (section, pc), %d areas" %
          (len(rows), len(distinct), len({r["area"] for r in rows})))
    for n in notes:
        print("  note:", n)

    srows, snotes = scenario_records(images)
    write_toml(os.path.join(args.out_dir, "scenario_records.toml"),
               "# names/scenario_records.toml -- GAME.EMI's chapter table 0x801C944C for SCENARIO overlays,\n"
               "# read off the disc by tools/loader_records.py (docs/OVERLAY_HEADERS.md \"Loader records\").\n"
               "#   chapter  s8[0x8014686C]; file id = 0x295 + chapter\n"
               "#   table    vtable[k]: u32[0x801C944C + chapter*4], a 5-slot vtable inside SCENA<cc>.EMI\n"
               "#            (GAME.EMI thunks 0x801A8834 / 8880 / 891C / 89AC / 8A3C, slot 4 optional);\n"
               "#            subA[k] / subB[k]: u32[0x801CDC4C|0x801CDC9C + chapter*4] -> u32[] the\n"
               "#            scenario's own code calls through Scenario_CallA/B (0x801C2DE8 / 0x801C2E34)\n"
               "#   entry    the pc\n",
               srows, ("chapter", "file", "section", "table", "kind", "entry"))
    print("scenario: %d rows, %d distinct (section, pc)" % (len(srows), len({(r["section"], r["entry"]) for r in srows})))
    for n in snotes:
        print("  note:", n)

    brows, bnotes = boss_records(images)
    write_toml(os.path.join(args.out_dir, "boss_records.toml"),
               "# names/boss_records.toml -- the battle engine's entry records for BOSS bundles,\n"
               "# read off the disc by tools/loader_records.py (docs/OVERLAY_HEADERS.md \"Loader records\").\n"
               "#   boss     boss id u8[0x801462E6] (1..55); row = u8[0x801CDF18 + id*4 + 3]\n"
               "#   file_id  u16[0x801CDFF8 + row*2] -> BIN/BOSS/BOSS<nnn>.EMI (several ids share a file)\n"
               "#   entry    u32[0x800B2048 + id*4], the pc Battle_SetupBoss jalr's at 0x800A8B40\n"
               "#   section  md5 of the file's 0x800C1800 section (deduped: join by md5, not by name)\n",
               brows, ("boss", "file", "file_id", "section", "kind", "entry"))
    print("boss: %d rows, %d distinct (section, pc)" % (len(brows), len({(r["section"], r["entry"]) for r in brows})))
    for n in bnotes:
        print("  note:", n)

    prows, pnotes = plchar_records(images)
    write_toml(os.path.join(args.out_dir, "plchar_records.toml"),
               "# names/plchar_records.toml -- GAME.EMI's entry tables for the PLCHAR (PLP) overlays,\n"
               "# read off the disc by tools/loader_records.py (docs/OVERLAY_HEADERS.md \"Loader records\").\n"
               "#   combo    party combination index 0..18 (u8[0x80145020] & 0x7F, rows of 0x801824AC)\n"
               "#   file_id  0x27D + combo -> BIN/PLCHAR/PLP<combo>.EMI\n"
               "#   entry    kind tableA = u32[0x801CD8F0 + combo*4] (jalr 0x801B46B0),\n"
               "#            tableB = u32[0x801CD964 + combo*4] (jalr 0x801B3C78 / 0x801BE508),\n"
               "#            slot[g][s] = the image's last six words, u32[2][3] indexed by u16[ctx+0x2C]\n",
               prows, ("combo", "file", "file_id", "section", "kind", "entry"))
    print("plchar: %d rows, %d distinct (section, pc)" % (len(prows), len({(r["section"], r["entry"]) for r in prows})))
    for n in pnotes:
        print("  note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
