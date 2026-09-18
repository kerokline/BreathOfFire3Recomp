#!/usr/bin/env python
"""Every area's enemy species table, read straight off the disc.

Each AREAnnn.EMI carries a 1,160-byte section with destination 0x800E4000:
eight species records on a 0x88 stride (slots 0..7, the byte an enemy's
working record keeps at +0x60 and its object at +0xE0 -- the index of its AI
script row AND of its bank-6 creature cue, docs/SOUND_CUES.md). Offsets below
are from `base + slot*0x88`:

    +0x00..0x47   per-species data the AI walks (docs/BATTLE_RAM.md "Enemy AI is table-driven")
    +0x48         name, 8 bytes, the game's 1-byte kana font codes, zero-padded (tools/jptext.py)
    +0x50, +0x52  two u16 (unread)
    +0x54         16 u16: [2] zenny, [3] EXP, [4] level, [10] max HP, [12] ATK, [13] DEF, [14] AGI
                  (the fields Battle_EnemyDefeated / Battle_BaseDamage read from the working copy)
    +0x74..0xBF   unread
    +0xC0..0xC8   the nine affinity classes -- fire, ice, lightning, earth, wind,
                  holy, psionic, status, death (docs/BATTLE_RAM.md "The resistance grid")

**The fields run past the stride.** They reach +0xCD while records repeat
every 0x88, so a record's own bytes are NOT the slice
`section[slot*0x88 : (slot+1)*0x88]` -- anything above +0x88 lands inside the
next slot's slice. Name and stats happen to sit below 0x88 and so survived
that reading for a year; the affinity block does not, and is read from the
whole section instead. Slot 7's block ends at 0x480, inside the 1,160 bytes,
which is what the trailing "0x48 bytes of zero" in an earlier version of this
note actually were.

Established 2026-09-17 on slot03 (AREA048): the live record 0's slot 3,
L18 HP100 EXP58 zenny62 ATK50 DEF17 AGI11 is species 3 of that table,
やけっぱちオーク, and the same stat halfwords sit in the disc section.

    python tools/enemy_table.py extract        # -> names/enemies.toml (generated; do not hand-edit)
    python tools/enemy_table.py --us-cue "isos/Breath of Fire III (USA).cue" extract
                                               # + the `us` column: the US disc's own 8-character names
    python tools/enemy_table.py show AREA048   # one area's species
    python tools/enemy_table.py species        # distinct species (name + stats) and where they appear

The US disc (SLUS-00422) ships the same table in the same section with the
name field in ASCII (0xFF = space): that is the string the US game prints,
8 characters at most ("BossGbln", "Ice Toad"), read with --us-cue into the
`us` column. `en` is the wiki's editorial full name from
names/enemy_gloss.toml (`[[gloss]] jp = "...", en = "..."`), hand-editable;
readable code should prefer `us`, then `en`, then `jp`.
"""
import argparse
import json
import os
import re
import struct
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import jptext  # noqa: E402

SECTIONS = os.path.join(ROOT, "analysis", "emi_sections.json")
OUT = os.path.join(ROOT, "names", "enemies.toml")
GLOSS = os.path.join(ROOT, "names", "enemy_gloss.toml")
BIN_ROOT = os.environ.get("BOF3_BIN_ROOT", r"D:\BoFIII")
TABLE_DEST = 0x800E4000
REC = 0x88
NAME_OFF, NAME_LEN, STATS_OFF = 0x48, 8, 0x54
STAT_IDX = dict(zenny=2, exp=3, level=4, max_hp=10, atk=12, df=13, agi=14)

# The nine affinity classes at record +0xC0..+0xC8 (docs/BATTLE_RAM.md "The
# resistance grid").  Note these sit PAST the 0x88 stride: the record's fields
# run +0x48..+0xCD against a stride of 0x88, so they must be read from the
# whole section, not from a sliced record.
AFF_OFF, AFF_LEN = 0xC0, 9
AFF_COLUMNS = ("fire", "ice", "lightning", "earth", "wind",
               "holy", "psionic", "status", "death")
# Each column indexes one of three percent tables, and they do not share a
# neutral class -- elements are neutral at 2, holy at 5, the status trio at 2.
AFF_TABLES = {
    "element": (300, 200, 100, 75, 50, 25, 0, -100, -1),   # 0x800B187C, summed over set bits
    "holy": (300, 200, 200, 150, 125, 100, 50, 0),         # 0x801EAF70, via Battle_ScaleDamage
    "status": (-1, 150, 100, 75, 50, 25, 0, 0),            # 0x800B188C, via 0x8009FD08
}
AFF_TABLE_OF = ("element",) * 5 + ("holy",) + ("status",) * 3


def affinity_percent(column, cls):
    """The damage percent a class byte means, or None if it is out of range."""
    t = AFF_TABLES[AFF_TABLE_OF[column]]
    return t[cls] if cls < len(t) else None


def decode_record(r):
    """One 0x88-byte species record -> dict, or None when the slot is empty."""
    if not any(r):
        return None
    name = r[NAME_OFF:NAME_OFF + NAME_LEN].rstrip(b"\0")
    st = struct.unpack_from("<16H", r, STATS_OFF)
    if not name and st[STAT_IDX["level"]] == 0 and st[STAT_IDX["max_hp"]] == 0:
        return None      # an unused slot whose AI bytes are leftovers
    d = {k: st[i] for k, i in STAT_IDX.items()}
    # the font keeps ASCII digits at 0x30..0x39 (サンプル1, プラント42); jptext leaves them as <3n>
    d["jp"] = re.sub(r"<3([0-9])>", lambda m: m.group(1), jptext.decode(name))
    d["name_hex"] = name.hex()
    return d


def tables(bin_root=BIN_ROOT):
    """{area number: [(slot, record dict)]} for every AREAnnn.EMI on the disc."""
    secs = json.load(open(SECTIONS, encoding="utf-8"))["sections"]
    out = {}
    for s in secs:
        m = re.search(r"/AREA(\d+)\.EMI$", s["file"])
        if not m or s["dest"] != TABLE_DEST:
            continue
        p = os.path.join(bin_root, s["file"].replace("/", os.sep))
        if not os.path.exists(p):
            continue
        b = open(p, "rb").read()[s["offset"]:s["offset"] + s["size"]]
        rows = []
        for k in range(8):
            d = decode_record(b[k * REC:(k + 1) * REC])
            if not d:
                continue
            # +0xC0..+0xC8 lie past this record's 0x88 slice, so read them from
            # the section.  Refuse rather than guess if the section is short or
            # a byte is not a class index -- a silent 0 would read as "300%".
            lo = k * REC + AFF_OFF
            aff = b[lo:lo + AFF_LEN]
            if len(aff) != AFF_LEN:
                raise SystemExit("%s slot %d: affinity block runs past the section (%d bytes)"
                                 % (s["file"], k, len(b)))
            bad = [x for x in aff if x > 8]
            if bad:
                raise SystemExit("%s slot %d: affinity bytes out of range 0..8: %s"
                                 % (s["file"], k, list(aff)))
            d["affinity"] = list(aff)
            rows.append((k, d))
        out[int(m.group(1))] = rows
    return out


def us_tables(cue):
    """{area number: {slot: US name}} from the US disc, same section, ASCII names."""
    import text_tables as tt
    disc = tt.Disc(cue=cue)
    out = {}
    for path in disc._entries:
        m = re.search(r"/AREA(\d+)\.EMI$", path)
        if not m:
            continue
        raw = disc.read(path)
        emi = tt.Emi(raw, path)
        sec = [e for e in emi.entries if e["dest"] == TABLE_DEST]
        if not sec:
            continue
        b = raw[sec[0]["offset"]:sec[0]["offset"] + sec[0]["size"]]
        names = {}
        for k in range(8):
            r = b[k * REC:(k + 1) * REC]
            st = struct.unpack_from("<16H", r, STATS_OFF)
            if st[STAT_IDX["level"]] or st[STAT_IDX["max_hp"]]:
                names[k] = tt.decode_us_name(r[NAME_OFF:NAME_OFF + NAME_LEN])
        out[int(m.group(1))] = names
    return out


def gloss():
    if not os.path.exists(GLOSS):
        return {}
    return {g["jp"]: g["en"] for g in tomllib.load(open(GLOSS, "rb")).get("gloss", []) if g.get("en")}


def signature(d):
    return (d["jp"], d["level"], d["max_hp"], d["exp"], d["zenny"], d["atk"], d["df"], d["agi"])


# ----------------------------------------------------------------- commands

def cmd_extract(a):
    t = tables(a.bin_root)
    g = gloss()
    us = us_tables(a.us_cue) if a.us_cue else {}
    lines = ["# names/enemies.toml -- every area's enemy species table, read off the disc by",
             "# tools/enemy_table.py extract (do not hand-edit; English names go in names/enemy_gloss.toml).",
             "#   area    AREAnnn: the table is that file's 0x800E4000 section (ENEMYnnn.EMI is its audio)",
             "#   slot    species index 0..7 = enemy record +0x60 = AI script row = bank-6 cue 0x600 + 2*slot",
             "#   jp      the 8-byte name field at record +0x48 (game kana codes -> tools/jptext.py)",
             "#   us      the US disc's own name at the same slot (ASCII, 8 chars max; with --us-cue) -- the",
             "#           string the US game prints; prefer it over en for readability",
             "#   en      the wiki's full name from names/enemy_gloss.toml (editorial, not the name card)",
             "#   level / max_hp / exp / zenny / atk / def / agi   the stat halfwords at record +0x54",
             "#   affinity  the nine class bytes at record +0xC0..+0xC8, in this fixed order:",
             "#             [%s]" % ", ".join(AFF_COLUMNS),
             "#             Each is an index into a percent table, and the three tables differ --",
             "#             elements (0x800B187C) {300,200,100,75,50,25,0,-100,-1} neutral at class 2",
             "#             and SUMMED over every set element bit; holy (0x801EAF70)",
             "#             {300,200,200,150,125,100,50,0} neutral at class 5; psionic/status/death",
             "#             (0x800B188C) {-1,150,100,75,50,25,0,0} neutral at class 2, assigned not",
             "#             summed.  docs/BATTLE_RAM.md 'The resistance grid'.",
             "", "[meta]", 'generator = "tools/enemy_table.py"', "areas = %d" % len(t),
             "species_rows = %d" % sum(len(v) for v in t.values()), ""]
    for n in sorted(t):
        for k, d in t[n]:
            lines.append("[[enemy]]")
            lines.append('area = "AREA%03d"' % n)
            lines.append("slot = %d" % k)
            lines.append('jp = "%s"' % d["jp"].replace('"', "'"))
            if us:
                lines.append('us = "%s"' % us.get(n, {}).get(k, "").replace('"', "'"))
            lines.append('en = "%s"' % g.get(d["jp"], "").replace('"', "'"))
            for k2 in ("level", "max_hp", "exp", "zenny", "atk", "df", "agi"):
                lines.append("%s = %d" % ("def" if k2 == "df" else k2, d[k2]))
            lines.append("affinity = [%s]" % ", ".join(str(x) for x in d["affinity"]))
            lines.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("%s: %d areas, %d species rows" % (OUT, len(t), sum(len(v) for v in t.values())))
    return 0


def cmd_show(a):
    n = int(re.sub(r"\D", "", a.area))
    g = gloss()
    rows = tables(a.bin_root).get(n, [])
    for k, d in rows:
        print("slot %d  %-12s %-16s L%-3d HP%-4d EXP%-4d zenny%-4d ATK%-3d DEF%-3d AGI%-3d" % (
            k, d["jp"], g.get(d["jp"], ""), d["level"], d["max_hp"], d["exp"], d["zenny"], d["atk"], d["df"], d["agi"]))
    if rows:
        print()
        print("%-8s %s" % ("affinity", " ".join("%9s" % c for c in AFF_COLUMNS)))
        for k, d in rows:
            cells = []
            for i, cls in enumerate(d["affinity"]):
                pct = affinity_percent(i, cls)
                cells.append("%9s" % ("-" if pct == -1 else "%d%%" % pct))
            print("slot %-3d %s" % (k, " ".join(cells)))
    return 0


def cmd_species(a):
    t = tables(a.bin_root)
    where = {}
    for n in sorted(t):
        for k, d in t[n]:
            where.setdefault(signature(d), []).append("AREA%03d/%d" % (n, k))
    g = gloss()
    for sig, ws in sorted(where.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print("%-12s %-14s L%-3d HP%-4d EXP%-4d  %d area(s): %s%s" % (
            sig[0], g.get(sig[0], ""), sig[1], sig[2], sig[3], len(ws), ", ".join(ws[:5]), " ..." if len(ws) > 5 else ""))
    print("%d distinct species (name + stats) over %d areas" % (len(where), len(t)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--bin-root", default=BIN_ROOT)
    ap.add_argument("--us-cue", default=None, help="the US disc .cue: adds the `us` (in-game 8-char) name column")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("extract"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("show"); s.add_argument("area"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("species"); s.set_defaults(fn=cmd_species)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
