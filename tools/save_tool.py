#!/usr/bin/env python
"""save_tool.py -- read Breath of Fire III (JP) saves off a raw memory-card image.

The format comes from docs/BATTLE_RAM.md ("The save block and the file
format"): a BoF3 save is one 8 KiB card block holding a title frame, three
icon frames, and at file +0x200 a raw copy of the 0x10B0-byte persistent
game block that lives at RAM 0x801448D4 (character records, flags, zenny,
party, inventory, the slot summary the load screen reads).  Every byte of
that block is summed into the u16 at file +0x270 (RAM 0x80144944, zeroed
before the copy) by Save_BuildImage (SHOP.EMI 0x801D69F0).

    python tools/save_tool.py list   saves/card1.mcd
    python tools/save_tool.py dump   saves/card1.mcd 1 [--raw] [--all-records]
    python tools/save_tool.py verify saves/card1.mcd [SLOT]
    python tools/save_tool.py diff   saves/card1.mcd 2 3 [--file2 other.mcd]

SLOT is the 1-based card directory index that `list` prints (the in-game
load screen shows the files in the same order).  Works on the runtime's
`.mcr` and Mednafen's `.mcd` alike -- both are the raw 128 KiB image.

Nothing here writes to the card.  Any mismatch `verify` reports is a bug in
the RAM map (docs/BATTLE_RAM.md), which is the point of the tool.
"""
import argparse
import json
import os
import struct
import sys

CARD_SIZE = 0x20000
FRAME = 128
BLOCK = 0x2000
FILE_LEN = 0x1300              # bytes Card_WriteFile writes
GAME_OFF = 0x200               # game block inside the file
GAME_LEN = 0x10B0
GAME_RAM = 0x801448D4          # RAM address of game-block byte 0
CKSUM_RAM = 0x80144944         # u16 byte-sum slot

REC_BASE = 0x80144964
REC_STRIDE = 0xA4
REC_COUNT = 8

# --- RAM addresses (docs/BATTLE_RAM.md) -------------------------------------
A = {
    "timers": 0x801448D4,       # 4 u32 snapshot of 0x8014686C..0x80146878 (unlabelled)
    "date": 0x801448F4,         # 4 bytes from 0x80146860..63 (unlabelled)
    "map_u16": 0x801448F8,      # lhu 0x80143F00 (boot 0x8015C03C reads it as u16)
    "facing": 0x801448FB,       # 0x80145E94 slot-0 actor facing
    "world_x": 0x801448FC,      # 0x80145EC0 slot-0 actor world x (16.16)
    "world_z": 0x80144900,      # 0x80145EC4
    "cksum": CKSUM_RAM,
    "records": REC_BASE,
    "flags": 0x80144F24,        # progress flag bit array (Flag_Test 0x8015BFC4)
    "zenny": 0x80144F4C,
    "formation": 0x80144F54,    # u16 keyed by Formation_ApplyStatMods
    "party_ids": 0x80144F56,    # 3 formations x 3 character ids
    "play_time": 0x80144FBC,    # h, m, s, frame bytes
    "form_byte": 0x80145020,    # & 0x7F compared to 5 / 0xC in the Peco special case
    "unk_80145021": 0x80145021, # <- low byte of 0x80146254 at save time
    "zenny_lifetime": 0x8014502C,
    "inv_ids": 0x80145048,      # 4 x 128
    "inv_counts": 0x80145248,   # 4 x 128
    "key_items": 0x80145448,    # 128 ids
    "abilities": 0x80145468,    # AbilityList_Add's 128-byte list
    "slot_window": 0x80145554,  # what Card_ReadSlotHeader reads back (file 0xE80..0xEFF)
    "slot_summary": 0x80145574,
    "slot_u16x9": 0x80145590,   # 9 u16 copied from 0x80145AB0
}
INV_CATEGORIES = ["cat0 (consumables)", "cat1 (weapons)", "cat2 (armour/shield/helm)",
                  "cat3 (accessories)"]
EQUIP_CATEGORY = [1, 2, 2, 2, 3, 3]      # START.EMI table 0x801EC3E8, slot 0 = weapon
FLAG_SUMMARY_BIT = 0x92                  # Save_BuildImage: Flag_Test(flags, 0x92)

# Persistent character record (offset, size, name); '?' = one-route evidence.
REC_FIELDS = [
    # char_id = roster for 0..6; 10 = record 7 (the intro whelp); table 0x80182488 maps the rest
    (0x05, 1, "char_id"), (0x06, 1, "level"), (0x07, 1, "unk_07"),
    (0x08, 4, "exp"), (0x0C, 2, "status"), (0x14, 2, "hp"), (0x16, 2, "ap"),
    (0x18, 1, "unk_18?"), (0x19, 1, "halve_bits"), (0x1A, 1, "maxhp_pct_penalty?"),
    (0x1C, 2, "max_hp"), (0x1E, 2, "max_ap"), (0x20, 2, "atk"), (0x22, 2, "def"),
    (0x24, 2, "agl_eff"), (0x26, 2, "int_eff"), (0x28, 2, "unk_28"), (0x2A, 2, "unk_2A?"),
    (0x2C, 2, "unk_2C"), (0x2E, 2, "unk_2E"), (0x30, 1, "size_class"), (0x31, 1, "unk_31"),
    (0x32, 2, "unk_32"), (0x34, 1, "unk_34"), (0x35, 1, "unk_35"), (0x36, 1, "unk_36"),
    (0x37, 1, "evade_pct"), (0x38, 1, "hit_pct"),
    (0x3C, 2, "base_max_hp"), (0x3E, 2, "base_max_ap"), (0x40, 2, "pwr"),
    (0x42, 2, "def_base"), (0x44, 2, "agl"), (0x46, 2, "int"),
]

# --- in-game text encoding (D:\BoFIII kana_table.py, docs/TEXT_ENGINE.md) ---
_HIRA = list("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん")
_SMALL = list("ぁぃぅぇぉっゃゅょ")
_DAKU = list("がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ")


def _kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)


KANA = {}
_b = 0x5B
for _ch in _HIRA + _SMALL + _DAKU:
    KANA[_b] = _ch
    _b += 1
for _ch in _kata("".join(_HIRA + _SMALL + _DAKU)):
    KANA[_b] = _ch
    _b += 1
KANA[0xFC] = "ー"
KANJI = {}


def load_kanji(path):
    """Optional two-byte kanji table (0x12xx/0x13xx) from the prior decode work."""
    if not path or not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        t = json.load(f)
    KANJI.update({k: v for k, v in t.items() if isinstance(v, str)})
    return True


def decode_text(d):
    out = []
    i = 0
    while i < len(d):
        b = d[i]
        if b == 0:
            break
        if b in (0x12, 0x13) and i + 1 < len(d):
            key = "%02x%02x" % (b, d[i + 1])
            out.append(KANJI.get(key, "[" + key + "]"))
            i += 2
            continue
        out.append(KANA.get(b, "<%02x>" % b))
        i += 1
    return "".join(out)


# --- card parsing -----------------------------------------------------------
class Slot:
    def __init__(self, card, index, dirent, first_block):
        self.index = index                     # 1-based directory index
        self.dirent = dirent
        self.first_block = first_block
        self.state = struct.unpack_from("<I", dirent, 0)[0]
        self.size = struct.unpack_from("<I", dirent, 4)[0]
        self.name = dirent[10:31].split(b"\0")[0].decode("ascii", "replace")
        self.data = card[first_block * BLOCK:first_block * BLOCK + BLOCK]

    @property
    def is_bof3(self):
        return self.name.startswith("BISLPS-00990BOF3") and self.data[:2] == b"SC"

    @property
    def title(self):
        raw = self.data[4:0x44].split(b"\0")[0]
        return raw.decode("shift_jis", "replace")

    @property
    def game(self):
        return self.data[GAME_OFF:GAME_OFF + GAME_LEN]

    def ram(self, addr, size=None):
        """Bytes of the game block at RAM address addr."""
        off = addr - GAME_RAM
        if off < 0 or off >= GAME_LEN:
            raise ValueError("RAM %#x is outside the save block" % addr)
        g = self.game
        return g[off:off + size] if size is not None else g[off:]

    def u8(self, a):
        return self.ram(a, 1)[0]

    def u16(self, a):
        return struct.unpack("<H", self.ram(a, 2))[0]

    def u32(self, a):
        return struct.unpack("<I", self.ram(a, 4))[0]

    def s32(self, a):
        return struct.unpack("<i", self.ram(a, 4))[0]

    def checksum(self):
        g = self.game
        stored = struct.unpack_from("<H", g, CKSUM_RAM - GAME_RAM)[0]
        calc = (sum(g) - g[CKSUM_RAM - GAME_RAM] - g[CKSUM_RAM - GAME_RAM + 1]) & 0xFFFF
        return stored, calc

    def record(self, roster):
        return self.ram(REC_BASE + roster * REC_STRIDE, REC_STRIDE)

    def play_time(self):
        h, m, s, f = self.ram(A["play_time"], 4)
        return h, m, s, f

    def flag(self, bit):
        return (self.u8(A["flags"] + (bit >> 3)) >> (bit & 7)) & 1

    def inventory(self, cat):
        ids = self.ram(A["inv_ids"] + cat * 128, 128)
        cnt = self.ram(A["inv_counts"] + cat * 128, 128)
        return [(slot, i, n) for slot, (i, n) in enumerate(zip(ids, cnt)) if i or n]

    def party_ids(self, formation=0):
        return list(self.ram(A["party_ids"] + formation * 3, 3))


def load_card(path):
    d = open(path, "rb").read()
    if len(d) != CARD_SIZE:
        raise SystemExit("%s: %d bytes, expected a raw 128 KiB card image" % (path, len(d)))
    if d[:2] != b"MC":
        raise SystemExit("%s: header frame does not start with 'MC'" % path)
    slots = []
    for i in range(1, 16):
        ent = d[i * FRAME:(i + 1) * FRAME]
        state = struct.unpack_from("<I", ent, 0)[0]
        if state & 0xF0 == 0x50 and state & 0x0F == 0x01:     # first block of a file
            slots.append(Slot(d, i, ent, i))
    return slots


def pick(slots, index):
    for s in slots:
        if s.index == index:
            if not s.is_bof3:
                raise SystemExit("slot %d is %r, not a BoF3 save" % (index, s.name))
            return s
    raise SystemExit("no file at directory slot %d (have %s)" % (index, [s.index for s in slots]))


# --- record decoding --------------------------------------------------------
def rec_fields(rec):
    out = {}
    for off, size, name in REC_FIELDS:
        if size == 1:
            out[name] = rec[off]
        elif size == 2:
            out[name] = struct.unpack_from("<H", rec, off)[0]
        else:
            out[name] = struct.unpack_from("<I", rec, off)[0]
    return out


def rec_name(rec):
    return decode_text(rec[0:5])


def rec_equipment(rec):
    return [(EQUIP_CATEGORY[i], rec[0x0E + i]) for i in range(6)]


ABILITY_LISTS = [(0x5C, "type0"), (0x66, "type1"), (0x70, "type2"), (0x7A, "type3")]


def rec_abilities(rec):
    """Four 10-slot ability lists.  AbilityList_Add (boot 0x80165BCC) asks
    0x80167514 for the list: record + {0x5C, 0x66, 0x70, 0x7A} by the ability's
    type byte (table 0x801CB231 + id*16, & 3), then stores into the first zero
    slot of ten."""
    return [(name, [b for b in rec[off:off + 10] if b]) for off, name in ABILITY_LISTS]


def rec_growth(rec):
    return list(struct.unpack_from("<6b", rec, 0x85))


def rec_is_empty(rec):
    return not any(rec[0:5]) and rec[0x06] == 0 and rec[0x1C] == 0 and rec[0x1D] == 0


# --- id -> name sidecars (names/*.toml from tools/text_tables.py) -----------
NAMES = {"item": {}, "key": {}, "ability": {}, "character": {}}


def load_names(dirpath):
    """Read names/items.toml, abilities.toml, characters.toml if present.
    Returns the list of files found; ids without a table print as idN."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    found = []
    for fname, kind in (("items.toml", "item"), ("abilities.toml", "ability"), ("characters.toml", "character")):
        path = os.path.join(dirpath, fname)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            doc = tomllib.load(f)
        for r in doc.get(kind, []):
            if kind == "item":
                if "cat" in r:
                    NAMES["item"][(r["cat"], r["id"])] = r
                else:
                    NAMES["key"][r["id"]] = r
            else:
                NAMES[kind][r["id"]] = r
        found.append(path)
    return found


def _label(r, fallback):
    if r is None:
        return fallback
    en = r.get("en")
    return "%s(%s)" % (r["jp"], en) if en else r["jp"]


def item_name(cat, i):
    return _label(NAMES["item"].get((cat, i)), "id%d" % i)


def key_item_name(i):
    return _label(NAMES["key"].get(i), "id%d" % i)


def ability_name(i):
    return _label(NAMES["ability"].get(i), "%#04x" % i)


def character_name(i):
    return _label(NAMES["character"].get(i), str(i))


# --- commands ---------------------------------------------------------------
def cmd_list(args):
    slots = load_card(args.card)
    if not slots:
        print("%s: no files" % args.card)
        return 0
    print("%-4s %-4s %-20s %-5s %-9s %-4s %-10s %-3s  %s" %
          ("slot", "blk", "file", "cksum", "time", "lv", "zenny", "pty", "title"))
    for s in slots:
        if not s.is_bof3:
            print("%-4d %-4d %-20s  (not a BoF3 save)" % (s.index, s.first_block, s.name))
            continue
        stored, calc = s.checksum()
        h, m, sec, _ = s.play_time()
        lead = s.record(0)
        print("%-4d %-4d %-20s %-5s %02d:%02d:%02d  %-4d %-10d %-3s  %s" %
              (s.index, s.first_block, s.name, "OK" if stored == calc else "BAD",
               h, m, sec, lead[0x06], s.u32(A["zenny"]),
               "".join("%x" % c if c != 0xFF else "-" for c in s.party_ids()), s.title))
    return 0


def hexrow(b, width=16):
    return " ".join("%02x" % x for x in b[:width])


def dump_record(roster, rec, out):
    f = rec_fields(rec)
    out.append("  roster %d  name=%s  char_id=%d  level=%d  exp=%d  status=%#06x" %
               (roster, rec_name(rec) or "(none)", f["char_id"], f["level"], f["exp"], f["status"]))
    out.append("    hp %d/%d  ap %d/%d  atk %d  def %d  agl_eff %d  int_eff %d  evade %d%%  hit %d%%  size %d" %
               (f["hp"], f["max_hp"], f["ap"], f["max_ap"], f["atk"], f["def"], f["agl_eff"],
                f["int_eff"], f["evade_pct"], f["hit_pct"], f["size_class"]))
    out.append("    base: max_hp %d  max_ap %d  pwr %d  def %d  agl %d  int %d   hp_pct_penalty %d  halve_bits %#04x" %
               (f["base_max_hp"], f["base_max_ap"], f["pwr"], f["def_base"], f["agl"], f["int"],
                f["maxhp_pct_penalty?"], f["halve_bits"]))
    out.append("    equipment (cat:id): %s" %
               "  ".join("%d:%d %s" % (c, i, item_name(c, i)) if i else "%d:0" % c for c, i in rec_equipment(rec)))
    out.append("    abilities: %s   growth_mods: %s  +84=%#04x" %
               ("  ".join("%s[%s]" % (n, " ".join(ability_name(a) for a in lst)) for n, lst in rec_abilities(rec) if lst)
                or "(none)", rec_growth(rec), rec[0x84]))
    out.append("    unlabelled: +07=%#04x +18=%#04x +28=%#06x +2A=%#06x +2C=%#06x +2E=%#06x +31=%#04x +32=%#06x +34..36=%s" %
               (f["unk_07"], f["unk_18?"], f["unk_28"], f["unk_2A?"], f["unk_2C"], f["unk_2E"],
                f["unk_31"], f["unk_32"], hexrow(rec[0x34:0x37])))
    base_copy = rec[0x4A:0x59] == rec[0x2A:0x39]
    out.append("    +48..+49: %s  +4A..+58 (%s the effective byte stats +2A..+38): %s  +59..+5B: %s" %
               (hexrow(rec[0x48:0x4A]), "equal to" if base_copy else "base of", hexrow(rec[0x4A:0x59], 15),
                hexrow(rec[0x59:0x5C])))
    out.append("    +8B..+A3: %s" % hexrow(rec[0x8B:0xA4], 0x19))


def cmd_dump(args):
    slots = load_card(args.card)
    s = pick(slots, args.slot)
    out = []
    stored, calc = s.checksum()
    out.append("%s  slot %d  block %d  %s" % (args.card, s.index, s.first_block, s.name))
    out.append("title: %s" % s.title)
    out.append("checksum: stored %#06x  computed %#06x  %s" %
               (stored, calc, "OK" if stored == calc else "BAD"))
    h, m, sec, f = s.play_time()
    out.append("play time: %02d:%02d:%02d +%d frames   (0x80144FBC h/m/s/f)" % (h, m, sec, f))
    out.append("map u16 %#06x  facing %d  world x %.4f  z %.4f  (0x80143F00 / 0x80145E94 / 0x80145EC0..)" %
               (s.u16(A["map_u16"]), s.u8(A["facing"]), s.s32(A["world_x"]) / 65536.0,
                s.s32(A["world_z"]) / 65536.0))
    out.append("summary timers (0x8014686C..): %s   date bytes (0x80146860): %s   +0x26: %#04x" %
               (" ".join("%#010x" % s.u32(A["timers"] + 4 * i) for i in range(4)),
                hexrow(s.ram(A["date"], 4)), s.u8(A["map_u16"] + 2)))
    out.append("zenny %d   lifetime %d   formation %#06x   party ids: %s   form_byte %#04x  unk_80145021 %#04x" %
               (s.u32(A["zenny"]), s.u32(A["zenny_lifetime"]), s.u16(A["formation"]),
                " / ".join("[%s]" % ", ".join("-" if c == 0xFF else character_name(c) for c in s.party_ids(k))
                           for k in range(3)),
                s.u8(A["form_byte"]), s.u8(A["unk_80145021"])))
    out.append("progress flags (0x80144F24, %d bytes shown): %s" %
               (0x28, hexrow(s.ram(A["flags"], 0x28), 0x28)))
    out.append("characters:")
    for r in range(REC_COUNT):
        rec = s.record(r)
        if rec_is_empty(rec) and not args.all_records:
            out.append("  roster %d  (empty)" % r)
            continue
        dump_record(r, rec, out)
    out.append("inventory:")
    for c in range(4):
        items = s.inventory(c)
        out.append("  %s: %s" % (INV_CATEGORIES[c],
                                 "  ".join("%s x%d" % (item_name(c, i), n) for _, i, n in items) or "(empty)"))
    keys = [b for b in s.ram(A["key_items"], 128) if b]
    out.append("  key items: %s" % (" ".join(key_item_name(k) for k in keys) or "(none)"))
    abil = [b for b in s.ram(A["abilities"], 128) if b]
    out.append("  ability list 0x80145468: %s" % (" ".join(ability_name(a) for a in abil) or "(none)"))
    ss = s.ram(A["slot_summary"], 0x18)
    out.append("slot summary (0x80145574, what the load screen reads): name=%s ids=%s level=%d "
               "+9/+A=%02x %02x time=%02d:%02d:%02d exp=%d flag[0x92]=%d" %
               (decode_text(ss[0:5]), list(ss[5:8]), ss[8], ss[9], ss[10], ss[0xC], ss[0xD], ss[0xE],
                struct.unpack_from("<I", ss, 0x10)[0], ss[0x14]))
    out.append("  9 u16 from 0x80145AB0: %s" %
               " ".join("%#06x" % v for v in struct.unpack("<9H", s.ram(A["slot_u16x9"], 18))))
    if args.raw:
        out.append("unlabelled ranges (RAM: bytes):")
        for lo, hi, why in [(0x80144904, 0x80144944, "between world z and the checksum"),
                            (0x80144946, 0x80144964, "between the checksum and record 0"),
                            (0x80144E84, 0x80144F24, "after record 7, before the flags"),
                            (0x80144F5F, 0x80144FBC, "after the party ids"),
                            (0x80144FC0, 0x80145020, "after the play time"),
                            (0x80145022, 0x8014502C, "before lifetime zenny"),
                            (0x80145030, 0x80145048, "before the inventory"),
                            (0x801454E8, 0x80145554, "before the slot window"),
                            (0x80145554, 0x80145574, "slot window head"),
                            (0x801455A2, 0x80145984, "tail of the block")]:
            data = s.ram(lo, hi - lo)
            if not any(data):
                out.append("  %#010x..%#010x  all zero  (%s)" % (lo, hi, why))
                continue
            out.append("  %#010x..%#010x  (%s)" % (lo, hi, why))
            for off in range(0, len(data), 32):
                out.append("    %#010x  %s" % (lo + off, hexrow(data[off:off + 32], 32)))
    print("\n".join(out))
    return 0


def verify_slot(s):
    """Cross-check everything the load screen shows against the block it came from."""
    checks = []
    stored, calc = s.checksum()
    checks.append(("u16 byte-sum at file +0x270", stored == calc,
                   "stored %#06x computed %#06x" % (stored, calc)))
    ss = s.ram(A["slot_summary"], 0x18)
    rec0 = s.record(0)
    checks.append(("summary name == record 0 bytes 0..4", ss[0:5] == rec0[0:5],
                   "%s vs %s" % (hexrow(ss[0:5]), hexrow(rec0[0:5]))))
    # Party ids, with Save_BuildImage's Peco special case (id 4 -> 0xB unless form 5 / 0xC).
    ids = s.party_ids(0)
    form = s.u8(A["form_byte"]) & 0x7F
    expect = [0xB if (c == 4 and form not in (5, 0xC)) else c for c in ids]
    checks.append(("summary party ids == formation 0 (Peco rule)", list(ss[5:8]) == expect,
                   "%s vs %s" % (list(ss[5:8]), expect)))
    checks.append(("summary level == record 0 +0x06", ss[8] == rec0[0x06], "%d vs %d" % (ss[8], rec0[0x06])))
    checks.append(("summary +9/+A == 0x8014494E/F", ss[9:11] == s.ram(0x8014494E, 2),
                   "%s vs %s" % (hexrow(ss[9:11]), hexrow(s.ram(0x8014494E, 2)))))
    checks.append(("summary play time == 0x80144FBC", ss[0xC:0x10] == s.ram(A["play_time"], 4),
                   "%s vs %s" % (hexrow(ss[0xC:0x10]), hexrow(s.ram(A["play_time"], 4)))))
    exp_sum = struct.unpack_from("<I", ss, 0x10)[0]
    exp_rec = struct.unpack_from("<I", rec0, 0x08)[0]
    checks.append(("summary EXP == record 0 +0x08", exp_sum == exp_rec, "%d vs %d" % (exp_sum, exp_rec)))
    checks.append(("summary +0x14 == Flag_Test(flags, 0x92)", ss[0x14] == s.flag(FLAG_SUMMARY_BIT),
                   "%d vs %d" % (ss[0x14], s.flag(FLAG_SUMMARY_BIT))))
    # The SJIS title carries hours, minutes and the lead level as full-width digits.
    title = s.title
    import re
    m = re.search(r"([０-９]+)時間([０-９]+)分\s*レベル([０-９]+)", title)
    if m:
        z2a = lambda t: int("".join(chr(ord(c) - 0xFEE0) for c in t))
        th, tm, tl = z2a(m.group(1)), z2a(m.group(2)), z2a(m.group(3))
        h, mi, _, _ = s.play_time()
        checks.append(("title hours/minutes == play time", (th, tm) == (h, mi),
                       "%02d:%02d vs %02d:%02d" % (th, tm, h, mi)))
        checks.append(("title level == record 0 level", tl == rec0[0x06], "%d vs %d" % (tl, rec0[0x06])))
    else:
        checks.append(("title parse (時間/分/レベル)", False, repr(title)))
    # Party members must map to occupied records (by character id == roster for ids < 8).
    for c in ids:
        if c == 0xFF or c >= REC_COUNT:
            continue
        rec = s.record(c)
        checks.append(("party id %d -> roster %d record populated" % (c, c), not rec_is_empty(rec),
                       "name %s level %d" % (rec_name(rec), rec[0x06])))
    # Stat sanity from the record layout (effective caps and HP within max).
    for r in range(REC_COUNT):
        rec = s.record(r)
        if rec_is_empty(rec):
            continue
        f = rec_fields(rec)
        ok = f["hp"] <= f["max_hp"] and f["ap"] <= f["max_ap"] and f["max_hp"] <= 999 and f["exp"] <= 9999999
        checks.append(("roster %d hp<=max, ap<=max, caps" % r, ok,
                       "hp %d/%d ap %d/%d exp %d" % (f["hp"], f["max_hp"], f["ap"], f["max_ap"], f["exp"])))
    for c in range(4):
        bad = [(i, n) for _, i, n in s.inventory(c) if n > 99]
        checks.append(("inventory %s counts <= 99" % INV_CATEGORIES[c], not bad, str(bad) if bad else "ok"))
    # Against the disc tables (names/*.toml): every id the save holds must be a
    # record, every learned ability must sit in the list its table type selects
    # (AbilityList_ForType: type = table byte +1 & 3 -> +0x5C/+0x66/+0x70/+0x7A),
    # and a record's effective ATK / DEF must be the base plus the equipment's power.
    if NAMES["item"]:
        for c in range(4):
            unknown = [i for _, i, n in s.inventory(c) if (c, i) not in NAMES["item"]]
            checks.append(("inventory %s ids are table records" % INV_CATEGORIES[c], not unknown,
                           "unknown %s" % unknown if unknown else "%d ids" % len(s.inventory(c))))
        unknown = [k for k in s.ram(A["key_items"], 128) if k and k not in NAMES["key"]]
        checks.append(("key item ids are table records", not unknown, "unknown %s" % unknown if unknown else "ok"))
    if NAMES["ability"]:
        for r in range(REC_COUNT):
            rec = s.record(r)
            if rec_is_empty(rec):
                continue
            wrong = []
            for k, (name, lst) in enumerate(rec_abilities(rec)):
                for a in lst:
                    t = NAMES["ability"].get(a, {}).get("type")
                    if t != k:
                        wrong.append("%s in %s has type %s" % (ability_name(a), name, t))
            checks.append(("roster %d ability lists match table types" % r, not wrong,
                           "; ".join(wrong) if wrong else "%d abilities" % sum(len(l) for _, l in rec_abilities(rec))))
    if NAMES["item"]:
        for r in range(REC_COUNT):
            rec = s.record(r)
            if rec_is_empty(rec):
                continue
            f = rec_fields(rec)
            cat, wid = rec_equipment(rec)[0]
            w = NAMES["item"].get((cat, wid), {}).get("power", 0)
            acc = [(c, i) for c, i in rec_equipment(rec)[4:6] if i]
            ok = f["atk"] == min(999, f["pwr"] + w)
            if not ok and acc:
                # accessories carry an effect code, not a stat (勇気のベルト: Garr's
                # ATK is base + spear + 10 with u16_10 = 5); unverifiable from the table
                ok = None
            checks.append(("roster %d ATK == base pwr + weapon power" % r, ok,
                           "atk %d = pwr %d + %s %d%s" % (f["atk"], f["pwr"], item_name(cat, wid), w,
                                                          "  + %d from %s (effect code, unread)" %
                                                          (f["atk"] - f["pwr"] - w, " ".join(item_name(c, i) for c, i in acc))
                                                          if ok is None else "")))
            d = sum(NAMES["item"].get((c, i), {}).get("power", 0) for c, i in rec_equipment(rec)[1:4])
            checks.append(("roster %d DEF == base def + armour powers" % r, f["def"] == min(999, f["def_base"] + d),
                           "def %d = base %d + %d" % (f["def"], f["def_base"], d)))
    return checks


def cmd_verify(args):
    slots = load_card(args.card)
    targets = [pick(slots, args.slot)] if args.slot else [s for s in slots if s.is_bof3]
    if not targets:
        print("%s: no BoF3 saves" % args.card)
        return 1
    failures = 0
    for s in targets:
        print("slot %d  %s  %s" % (s.index, s.name, s.title))
        for label, ok, detail in verify_slot(s):
            print("  [%s] %-48s %s" % ("--" if ok is None else "ok" if ok else "FAIL", label, detail))
            failures += ok is False
    print("%d check(s) failed" % failures)
    return 1 if failures else 0


def field_at(off):
    """Label a game-block offset from the RAM map, for diff annotation."""
    addr = GAME_RAM + off
    if REC_BASE <= addr < REC_BASE + REC_STRIDE * REC_COUNT:
        r, o = divmod(addr - REC_BASE, REC_STRIDE)
        name = "name" if o < 5 else next((n for fo, sz, n in REC_FIELDS if fo <= o < fo + sz), None)
        if name is None:
            name = ("equip%d" % (o - 0x0E) if 0x0E <= o < 0x14 else
                    "base byte stats" if 0x4A <= o < 0x59 else
                    "abilities %s" % next(n for lo, n in reversed(ABILITY_LISTS) if o >= lo) if 0x5C <= o < 0x84 else
                    "growth_mod%d" % (o - 0x85) if 0x85 <= o < 0x8B else "+%#04x" % o)
        return "record %d %s" % (r, name)
    for lo, hi, name in [
        (A["timers"], A["timers"] + 16, "summary timers"), (A["date"], A["date"] + 4, "date bytes"),
        (A["map_u16"], A["map_u16"] + 3, "map/unk"), (A["facing"], A["facing"] + 1, "facing"),
        (A["world_x"], A["world_x"] + 4, "world x"), (A["world_z"], A["world_z"] + 4, "world z"),
        (A["cksum"], A["cksum"] + 2, "checksum"), (A["flags"], A["zenny"], "progress flags"),
        (A["zenny"], A["zenny"] + 4, "zenny"), (A["formation"], A["formation"] + 2, "formation"),
        (A["party_ids"], A["party_ids"] + 9, "party ids"), (A["play_time"], A["play_time"] + 4, "play time"),
        (A["form_byte"], A["form_byte"] + 1, "form byte"), (A["unk_80145021"], A["unk_80145021"] + 1, "unk_80145021"),
        (A["zenny_lifetime"], A["zenny_lifetime"] + 4, "lifetime zenny"),
        (A["inv_ids"], A["inv_ids"] + 512, "inventory ids"), (A["inv_counts"], A["inv_counts"] + 512, "inventory counts"),
        (A["key_items"], A["key_items"] + 128, "key items"), (A["abilities"], A["abilities"] + 128, "ability list"),
        (A["slot_summary"], A["slot_summary"] + 0x18, "slot summary"),
        (A["slot_u16x9"], A["slot_u16x9"] + 18, "slot u16x9"),
    ]:
        if lo <= addr < hi:
            if name.startswith("inventory"):
                cat, sl = divmod(addr - lo, 128)
                return "%s cat%d slot %d" % (name, cat, sl)
            return name
    return "unlabelled"


def cmd_diff(args):
    a = pick(load_card(args.card), args.slot_a)
    b = pick(load_card(args.file2 or args.card), args.slot_b)
    ga, gb = a.game, b.game
    print("A: slot %d %s   B: slot %d %s" % (a.index, a.title, b.index, b.title))
    runs = []
    i = 0
    while i < GAME_LEN:
        if ga[i] != gb[i]:
            j = i
            while j < GAME_LEN and (ga[j] != gb[j] or (j + 1 < GAME_LEN and ga[j + 1] != gb[j + 1])):
                j += 1
            runs.append((i, j))
            i = j
        i += 1
    if not runs:
        print("game blocks identical")
    for lo, hi in runs:
        print("  block +%#06x..+%#06x  RAM %#010x  %-28s A: %s  B: %s" %
              (lo, hi, GAME_RAM + lo, field_at(lo), hexrow(ga[lo:hi], hi - lo), hexrow(gb[lo:hi], hi - lo)))
    print("%d differing run(s)" % len(runs))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kanji-table", default=os.environ.get("BOF3_KANJI_TABLE", r"D:\BoFIII\bof3_character_table.json"),
                    help="optional 0x12xx/0x13xx kanji table (JSON) for names; kana decode without it")
    ap.add_argument("--names", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "names"),
                    help="directory with items.toml / abilities.toml / characters.toml (tools/text_tables.py extract); "
                         "ids print bare when the files are absent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="slots, titles, checksum OK/BAD")
    p.add_argument("card")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("dump", help="decode one save")
    p.add_argument("card")
    p.add_argument("slot", type=int)
    p.add_argument("--raw", action="store_true", help="also hexdump the unlabelled ranges")
    p.add_argument("--all-records", action="store_true", help="print empty character records too")
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("verify", help="checksum + load-screen summary cross-checks")
    p.add_argument("card")
    p.add_argument("slot", type=int, nargs="?")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("diff", help="byte-run diff of two saves, annotated with the RAM map")
    p.add_argument("card")
    p.add_argument("slot_a", type=int)
    p.add_argument("slot_b", type=int)
    p.add_argument("--file2", help="take slot_b from another card image")
    p.set_defaults(fn=cmd_diff)
    args = ap.parse_args(argv)
    load_kanji(args.kanji_table)
    load_names(args.names)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
