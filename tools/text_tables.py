#!/usr/bin/env python
"""text_tables.py -- id->name tables straight from the JP disc's .EMI files.

The non-dialogue names (items, abilities, places, the roster) do not live in
the script blocks; they sit in fixed-stride RECORD tables inside GAME.EMI,
MTEST.EMI and COMMU02.EMI.  The record index IS the id the saves and the RAM
hold, so reading the tables gives the id order plus the record fields (price,
type bits, AP cost) as a side effect.  See docs/IDEAS.md I4 and
docs/TEXT_TABLES.md for the layouts and how each one was established.

    python tools/text_tables.py extract                   # -> names/{items,abilities,places,characters}.toml
    python tools/text_tables.py show items [--category weapon]
    python tools/text_tables.py show abilities | places | characters

Disc bytes come from the .cue in game.toml (read through tools/disc_ls.py,
never modified) or, with --bin-root, from an already-extracted BIN/ tree.
Kanji (0x12xx/0x13xx) decode through the character table of the prior decode
work (BOF3_KANJI_TABLE, default D:\\BoFIII\\bof3_character_table.json); the
English column comes from a wiki glossary TSV (BOF3_GLOSSARY, default
D:\\BoFIII\\wiki_terms.tsv) and is empty where the glossary has no row.

Nothing here is a hypothesis about the game's code: every table start, stride
and count is checked against the bytes (a record whose name does not decode
ends the table), and `extract` refuses to write a table whose count does not
match the expected one.  Wrong expectations fail loudly, not silently.
"""
import argparse
import csv
import hashlib
import json
import mmap
import os
import re
import struct
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc_ls  # noqa: E402
from emi import Emi  # noqa: E402

DEFAULT_KANJI = os.environ.get("BOF3_KANJI_TABLE", r"D:\BoFIII\bof3_character_table.json")
DEFAULT_GLOSSARY = os.environ.get("BOF3_GLOSSARY", r"D:\BoFIII\wiki_terms.tsv")

# --- the in-game text encoding, name-field flavour ---------------------------
# Kana half as in docs/TEXT_ENGINE.md / D:\BoFIII\kana_table.py.  Name fields
# additionally carry raw ASCII digits and capitals (パーツA..H, アリーナ1..4,
# ぜんたいマップ1), 0xFF as a word separator (マクニールむら S, つりば みずうみ),
# 0x2D as a long-vowel mark (シャ-リィ, ス-パ-コンボ; the glyph reads as ー)
# and 0x3A as the middle dot (ウルカン・タパ).
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
assert _b == 0xFB, hex(_b)
KANA[0xFB] = "ヴ"
KANA[0xFC] = "ー"
KANA[0x2D] = "ー"
KANA[0x3A] = "・"
KANA[0xFE] = "、"
KANJI = {}


def load_kanji(path):
    if not path or not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        t = json.load(f)
    KANJI.update({k: v for k, v in t.items() if isinstance(v, str)})
    return True


class Undecodable(ValueError):
    pass


def decode_name(d):
    """Decode one name field.  Raises Undecodable on any byte outside the
    name alphabet, which is how a table's end is detected."""
    out = []
    i = 0
    while i < len(d):
        b = d[i]
        if b == 0:
            break
        if b in (0x12, 0x13):
            if i + 1 >= len(d):
                raise Undecodable("truncated kanji at +%d" % i)
            key = "%02x%02x" % (b, d[i + 1])
            # the prior decode's table covers 435 of the glyphs; a code it
            # lacks (火[13b3]ダコ) is still a kanji, not the table's end
            out.append(KANJI.get(key, "[" + key + "]"))
            i += 2
            continue
        if b == 0xFF:
            # separator inside a name: マクニールむら|S, つりば|みずうみ, けんじゅ|A045
            out.append(" ")
            i += 1
            continue
        if 0x30 <= b <= 0x39 or 0x41 <= b <= 0x5A:
            out.append(chr(b))
            i += 1
            continue
        if b in KANA:
            out.append(KANA[b])
            i += 1
            continue
        raise Undecodable("byte %#04x at +%d" % (b, i))
    return "".join(out)


# --- glossary ----------------------------------------------------------------
# --- kana -> wapuro romaji, the convention the wiki's romaji column uses
# (ou / uu / ii doubled, ー repeats the vowel, っ doubles the consonant)
_ROMA = {}
for _row, _cons in (("あいうえお", ""), ("かきくけこ", "k"), ("さしすせそ", "s"), ("たちつてと", "t"),
                    ("なにぬねの", "n"), ("はひふへほ", "h"), ("まみむめも", "m"), ("らりるれろ", "r"),
                    ("がぎぐげご", "g"), ("ざじずぜぞ", "z"), ("だぢづでど", "d"), ("ばびぶべぼ", "b"),
                    ("ぱぴぷぺぽ", "p")):
    for _k, _v in zip(_row, "aiueo"):
        _ROMA[_k] = _cons + _v
_ROMA.update({"し": "shi", "ち": "chi", "つ": "tsu", "ふ": "fu", "じ": "ji", "ぢ": "ji", "づ": "zu",
              "や": "ya", "ゆ": "yu", "よ": "yo", "わ": "wa", "を": "wo", "ん": "n",
              "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o", "ヴ": "vu"})
_SMALLY = {"ゃ": "ya", "ゅ": "yu", "ょ": "yo"}


def romaji(s):
    """wapuro romaji of a kana string; None if it holds anything but kana."""
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ン" else c for c in s)
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in (" ", "・", "、"):
            i += 1
            continue
        if c == "っ":
            j = i + 1
            if j < len(s) and s[j] in _ROMA:
                out.append(_ROMA[s[j]][0] if _ROMA[s[j]][0] not in "aiueo" else "")
            i += 1
            continue
        if c == "ー":
            if out and out[-1]:
                out.append(out[-1][-1])
            i += 1
            continue
        if c in _ROMA:
            r = _ROMA[c]
            if i + 1 < len(s) and s[i + 1] in _SMALLY and r.endswith("i"):
                y = _SMALLY[s[i + 1]]
                # しゃ sha / ちゃ cha / じゃ ja, otherwise きゃ kya
                r = r[:-1] + (y[1:] if r in ("shi", "chi", "ji") else y)
                i += 2
            else:
                i += 1
            out.append(r)
            continue
        if c in _SMALLY:
            out.append(_SMALLY[c])
            i += 1
            continue
        return None
    return "".join(out)


class Glossary:
    """D:\\BoFIII\\wiki_terms.tsv: section, japanese, romaji, english_literal,
    english_official.  For spells the wiki's 'official' column carries a
    history note instead of a name, so a long or sentence-like official
    falls back to the literal column and the note is kept separately."""

    def __init__(self, path):
        self.rows = {}
        self.path = path
        if not path or not os.path.exists(path):
            self.path = None
            return
        self.by_romaji = {}
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.DictReader(f, delimiter="\t")
            for r in rd:
                jp = (r.get("japanese") or "").strip()
                if jp:
                    self.rows.setdefault(jp, []).append(r)
                    key = re.sub(r"[^a-z]", "", (r.get("romaji") or "").lower())
                    if key:
                        self.by_romaji.setdefault(key, []).append(r)

    def lookup_romaji(self, kana, sections):
        """Match a kana string to a glossary row through the wiki's romaji
        column (the kana debug names vs the kanji wiki names).  Exact match
        only, within the listed sections."""
        key = romaji(kana)
        if not key:
            return None, None, None
        for sec in sections:
            for r in self.by_romaji.get(key, []):
                if r["section"] == sec:
                    return self._pick(r)
        return None, None, None

    @staticmethod
    def _is_note(s):
        return len(s) > 28 or s.endswith(".") or s.startswith("Also ") or s.startswith("In ")

    def lookup(self, jp, sections, strict=False):
        """-> (en, section, note) or (None, None, None).  strict: only the
        listed sections may match (places must not fall through to a person)."""
        rows = self.rows.get(jp)
        if not rows:
            return None, None, None
        for sec in sections:
            for r in rows:
                if r["section"] == sec:
                    return self._pick(r)
        if strict:
            return None, None, None
        return self._pick(rows[0])

    def _pick(self, r):
        official = (r.get("english_official") or "").strip()
        literal = (r.get("english_literal") or "").strip()
        note = None
        en = official
        if not official or self._is_note(official):
            en = literal
            note = official or None
        return en or None, r["section"], note


# --- disc access -------------------------------------------------------------
class Disc:
    """Open .EMI files either from the .cue (ISO9660 walk, read-only) or an
    extracted BIN/ tree."""

    def __init__(self, cue=None, bin_root=None):
        self.bin_root = bin_root
        self.cue = cue
        self._entries = None
        self._read = None
        if bin_root:
            self.label = bin_root
            return
        if not cue or not os.path.exists(cue):
            raise SystemExit("no disc: give --cue <.cue> (game.toml [game].disc) or --bin-root <BIN dir>")
        binpath = disc_ls.resolve_cue(cue) if cue.lower().endswith(".cue") else cue
        fh = open(binpath, "rb")
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        self._read, _mode = disc_ls.make_reader(mm)
        pvd = self._read(16)
        root_extent = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        self._entries = {p.upper(): (ext, sz) for p, ext, sz, is_dir in
                         disc_ls.walk(self._read, root_extent, root_size) if not is_dir}
        self.label = os.path.basename(binpath)

    def read(self, path):
        """path is disc-relative, e.g. BIN/ETC/GAME.EMI"""
        if self.bin_root:
            rel = path.split("/", 1)[1] if path.upper().startswith("BIN/") else path
            with open(os.path.join(self.bin_root, *rel.split("/")), "rb") as f:
                return f.read()
        key = path.upper()
        if key not in self._entries:
            raise SystemExit("%s: not on the disc (%s)" % (path, self.label))
        ext, sz = self._entries[key]
        return disc_ls.read_extent(self._read, ext, sz)

    def section(self, path, dest):
        """The section of an .EMI whose RAM destination is `dest` (select by
        destination, never by index -- the same rule as the script block)."""
        emi = Emi(self.read(path), path)
        for e in emi.entries:
            if e["dest"] == dest:
                if not emi.verify(e["index"]):
                    raise SystemExit("%s#%d: TOC preview mismatch" % (path, e["index"]))
                data = emi.data(e["index"])
                return Section(path, e["index"], dest, data)
        raise SystemExit("%s: no section with dest %#010x" % (path, dest))


class Section:
    def __init__(self, path, index, dest, data):
        self.path, self.index, self.dest, self.data = path, index, dest, data
        self.md5 = hashlib.md5(data).hexdigest()

    def at(self, ram, n):
        o = ram - self.dest
        if o < 0 or o + n > len(self.data):
            raise SystemExit("%s#%d: %#010x+%d outside the section" % (self.path, self.index, ram, n))
        return self.data[o:o + n]

    def source(self):
        return "%s#%d" % (self.path, self.index)


# --- table layouts -----------------------------------------------------------
# name_off/name_len: where the name sits in the record; fields: (name, offset,
# struct code).  `end` bounds the scan (the next table's start); the scan also
# stops at the first record whose name does not decode.  `expect` is the
# record count the bytes were read to have on 2026-09-05 -- a different count
# means the layout hypothesis broke and extract refuses to write.
GAME = ("BIN/ETC/GAME.EMI", 0x80196800)
ITEM_TABLES = [
    # category, start, stride, end, expect, name_off, name_len, fields
    dict(category="consumable", cat=0, start=0x801C995C, stride=14, end=0x801C9E64, expect=92,
         name=(0, 8), fields=[("flags", 8, "H"), ("ref", 10, "H"), ("price", 12, "H")]),
    dict(category="key", cat=None, start=0x801C9E64, stride=12, end=0x801C9F24, expect=16,
         name=(0, 8), fields=[("ref", 8, "H"), ("u16_10", 10, "H")]),
    dict(category="weapon", cat=1, start=0x801C9F24, stride=20, end=0x801CA5A0, expect=83,
         name=(0, 8), fields=[("u16_8", 8, "H"), ("u16_10", 10, "H"), ("u16_12", 12, "H"),
                              ("power", 14, "H"), ("ref", 16, "H"), ("price", 18, "H")]),
    dict(category="armour", cat=2, start=0x801CA5A0, stride=18, end=0x801CAA68, expect=68,
         name=(0, 8), fields=[("u16_8", 8, "H"), ("u16_10", 10, "H"), ("power", 12, "H"),
                              ("ref", 14, "H"), ("price", 16, "H")]),
    dict(category="accessory", cat=3, start=0x801CAA68, stride=16, end=0x801CB230, expect=None,
         name=(0, 8), fields=[("u16_8", 8, "H"), ("u16_10", 10, "H"), ("ref", 12, "H"), ("price", 14, "H")]),
]
ABILITY_TABLE = dict(start=0x801CB230, stride=16, end=0x801CC070, expect=227, name=(8, 8),
                     fields=[("b0", 0, "B"), ("b1", 1, "B"), ("b2", 2, "B"), ("b3", 3, "B"),
                             ("u16_4", 4, "H"), ("u16_6", 6, "H")])
MTEST = ("BIN/ETC/MTEST.EMI", 0x801D0C00)
PLACES = dict(header=0x801D0C00, names=0x801D0D94, stride=10, expect=200)
COMMU02 = ("BIN/ETC/COMMU02.EMI", 0x801D0C00)
CHARS = dict(start=0x801DB214, stride=5, expect=7)
START = ("BIN/ETC/START.EMI", 0x801D0C00)
TEMPLATES = dict(start=0x801EB4A4, stride=0xA4, count=8)

GLOSS_SECTIONS = {
    "consumable": ["Items", "Fish", "Fishing gear", "Vital items", "Antiques", "Ammo", "Unused/dummy items"],
    "key": ["Vital items", "Items", "Antiques"],
    "weapon": ["Swords and knives", "Spears", "Staves", "Claws", "Fishing gear", "Ammo", "Unused/dummy items"],
    "armour": ["Armors", "Shields", "Helmets", "Unused/dummy items"],
    "accessory": ["Accessories", "Unused/dummy items"],
    "ability": ["Skills", "Attack type spells", "Assist type spells", "Heal type spells", "Dragon spells",
                "Enemy only skills", "In-Battle actions", "Unused/dummy skills"],
    "place": ["Locations"],
    "character": ["Party members"],
}


def scan_records(sec, start, stride, end, name, fields):
    """Read fixed-stride records from `start` until `end` or the first
    undecodable name.  Record 0 may be empty (なし / blank)."""
    recs = []
    ram = start
    while ram + stride <= end:
        raw = sec.at(ram, stride)
        nb = raw[name[0]:name[0] + name[1]]
        try:
            jp = decode_name(nb)
        except Undecodable as exc:
            if recs:
                break
            raise SystemExit("%s: record 0 at %#010x does not decode: %s" % (sec.source(), ram, exc))
        if not jp and recs:
            # an all-zero record inside a table is a real blank entry only if
            # the rest of the record is also zero; otherwise the table ended
            if any(raw):
                break
        rec = {"id": len(recs), "ram": ram, "jp": jp}
        for fname, off, code in fields:
            rec[fname] = struct.unpack_from("<" + code, raw, off)[0]
        rest = bytearray(raw)
        del rest[name[0]:name[0] + name[1]]
        rec["raw"] = bytes(rest).hex()
        recs.append(rec)
        ram += stride
    return recs


def read_items(disc, gloss):
    sec = disc.section(*GAME)
    out = []
    for t in ITEM_TABLES:
        recs = scan_records(sec, t["start"], t["stride"], t["end"], t["name"], t["fields"])
        if t["expect"] is not None and len(recs) != t["expect"]:
            raise SystemExit("%s table: read %d records, expected %d -- layout changed?"
                             % (t["category"], len(recs), t["expect"]))
        for r in recs:
            r["category"] = t["category"]
            if t["cat"] is not None:
                r["cat"] = t["cat"]
            r["en"], r["gloss_section"], r["note"] = gloss.lookup(r["jp"], GLOSS_SECTIONS[t["category"]])
        out.append((t, recs))
    return sec, out


def read_abilities(disc, gloss):
    sec = disc.section(*GAME)
    t = ABILITY_TABLE
    recs = scan_records(sec, t["start"], t["stride"], t["end"], t["name"], t["fields"])
    if len(recs) != t["expect"]:
        raise SystemExit("ability table: read %d records, expected %d" % (len(recs), t["expect"]))
    for r in recs:
        r["type"] = r["b1"] & 3
        r["en"], r["gloss_section"], r["note"] = gloss.lookup(r["jp"], GLOSS_SECTIONS["ability"])
    return sec, recs


# --- area scripts: the in-game kanji labels ----------------------------------
# The MTEST index is the AREA number (200 entries = AREA000..AREA199, names
# agree throughout), so each debug entry can be joined to its area's script
# block (the section with dest 0x80010000; u16 offset table at offset 0, see
# TEXT_ENGINE.md).  Two kinds of label live there:
#   caption   the on-entry banner the game draws: message text of the form
#             <0c> <param> (<ff>|<01>)* TEXT [<11>] <16> <frames>  -- グラウス山,
#             泉の牧場, ウインディア城.  This is what the player sees.
#   dev_label message 0 when it is a bare short string (鉱山の外, 港町,
#             オウガー街道, まくにーるむら): the developers' label for the map.
SCRIPT_DEST = 0x80010000
SEASON_WORDS = [("、泉", ""), ("泉の", ""), ("、秋", ""), ("秋の", "")]


def decode_script(d):
    """Script text with control bytes shown as <xx>; kanji leads 0x12/0x13/0x15."""
    out = []
    i = 0
    while i < len(d):
        b = d[i]
        if b == 0:
            break
        if b in (0x12, 0x13, 0x15) and i + 1 < len(d):
            key = "%02x%02x" % (b, d[i + 1])
            out.append(KANJI.get(key, "[" + key + "]"))
            i += 2
            continue
        if b in KANA:
            out.append(KANA[b])
        elif 0x30 <= b <= 0x39 or 0x41 <= b <= 0x5A:
            out.append(chr(b))
        else:
            out.append("<%02x>" % b)
        i += 1
    return "".join(out)


def script_messages(d):
    first = struct.unpack_from("<H", d, 0)[0]
    out = []
    for i in range(first // 2):
        off = struct.unpack_from("<H", d, 2 * i)[0]
        end = d.find(b"\x00", off)
        out.append(d[off:end if end >= 0 else len(d)])
    return out


_CAPTION = re.compile(r"<0c>(?:.|<[0-9a-f]{2}>)(?:<ff>|<01>|<10>)*([^<]+?)(?:<11>)?<16>")
_CLEAN = re.compile(r"<[0-9a-f]{2}>")


def area_labels(disc, area_path):
    """-> (caption, dev_label) for one AREA file, either may be None."""
    emi = Emi(disc.read(area_path), area_path)
    secs = [e for e in emi.entries if e["dest"] == SCRIPT_DEST]
    if not secs:
        return None, None
    msgs = [decode_script(m) for m in script_messages(emi.data(secs[0]["index"]))]
    caption = None
    for m in msgs[:16]:
        mm = _CAPTION.search(m)
        if mm:
            caption = mm.group(1).strip()
            break
    dev = None
    if msgs:
        m0 = msgs[0]
        bare = _CLEAN.sub("", m0)
        # a label, not a line of dialogue: one short line with no newline,
        # speaker, quote, colour or banner codes anywhere in the message
        if bare and len(bare) <= 12 and not re.search(r"<(01|02|03|04|05|06|0b|0c|10|2a)>", m0):
            dev = bare
    return caption, dev


def fold_season(s):
    for a, b in SEASON_WORDS:
        s = s.replace(a, b)
    return s


def read_places(disc, gloss):
    sec = disc.section(*MTEST)
    p = PLACES
    n = (len(sec.data) - (p["names"] - p["header"])) // p["stride"]
    if n != p["expect"]:
        raise SystemExit("MTEST list: %d names, expected %d" % (n, p["expect"]))
    head = sec.at(p["header"], p["names"] - p["header"])
    head_u32 = struct.unpack_from("<I", head, 0)[0]
    pairs = [(head[4 + 2 * i], head[5 + 2 * i]) for i in range(n)]
    if len(head) != 4 + 2 * n:
        raise SystemExit("MTEST head is %d bytes, not 4 + 2*%d" % (len(head), n))
    area_files = {}
    if disc.bin_root:
        import glob as _glob
        for f in _glob.glob(os.path.join(disc.bin_root, "WORLD*", "AREA*.EMI")):
            area_files[int(re.search(r"AREA(\d+)", f).group(1))] = "BIN/" + os.path.relpath(f, disc.bin_root).replace(os.sep, "/")
    else:
        for key in disc._entries:
            m = re.fullmatch(r"BIN/WORLD\d+/AREA(\d+)\.EMI", key)
            if m:
                area_files[int(m.group(1))] = key
    if len(area_files) != n:
        raise SystemExit("MTEST has %d entries but the disc has %d AREA files" % (n, len(area_files)))
    recs = []
    for i in range(n):
        raw = sec.at(p["names"] + i * p["stride"], p["stride"])
        jp = decode_name(raw)
        parts = jp.split(" ")
        season = parts[1] if len(parts) == 2 and parts[1] in ("S", "A") else None
        caption, dev = area_labels(disc, area_files[i])
        # English: the on-screen caption first (season words folded), then the
        # dev label, then the debug kana name; say which one matched
        en = gsec = note = src = None
        for cand, tag in ((caption, "caption"), (fold_season(caption) if caption else None, "caption"),
                          (dev, "dev_label"), (jp, "jp"), (parts[0].rstrip("0123456789"), "jp")):
            if cand:
                en, gsec, note = gloss.lookup(cand, GLOSS_SECTIONS["place"], strict=True)
                if en:
                    src = tag
                    break
        if not en:
            for cand, tag in ((dev, "romaji dev_label"), (parts[0].rstrip("0123456789"), "romaji jp")):
                if cand:
                    en, gsec, note = gloss.lookup_romaji(cand, GLOSS_SECTIONS["place"])
                    if en:
                        src = tag
                        break
        rec = {"id": i, "ram": p["names"] + i * p["stride"], "jp": jp, "area_file": area_files[i],
               "season": season, "caption": caption, "dev_label": dev, "en": en, "en_source": src,
               "gloss_section": gsec, "note": note, "sel": list(pairs[i])}
        recs.append(rec)
    # The S and A variants of one place carry the same two `sel` bytes, so a
    # label read from one variant's script names the other as well.
    by_sel = {}
    for r in recs:
        by_sel.setdefault(tuple(r["sel"]), []).append(r)
    for group in by_sel.values():
        named = [r for r in group if r["en"]]
        if len(named) == 1 and len(group) == 2:
            src, other = named[0], [r for r in group if r is not named[0]][0]
            if other["season"] and src["season"] and other["season"] != src["season"]:
                other["en"], other["gloss_section"], other["note"] = src["en"], src["gloss_section"], src["note"]
                other["en_source"] = "sibling %s %s" % (os.path.basename(src["area_file"]), src["en_source"])
    return sec, head_u32, recs


def read_characters(disc, gloss):
    sec = disc.section(*COMMU02)
    recs = []
    for i in range(16):
        raw = sec.at(CHARS["start"] + i * CHARS["stride"], CHARS["stride"])
        if not raw[0]:
            break
        jp = decode_name(raw)
        en, gsec, note = gloss.lookup(jp, GLOSS_SECTIONS["character"])
        recs.append({"id": i, "ram": CHARS["start"] + i * CHARS["stride"], "jp": jp, "en": en,
                     "gloss_section": gsec, "note": note})
    if len(recs) != CHARS["expect"]:
        raise SystemExit("roster names: %d, expected %d" % (len(recs), CHARS["expect"]))
    tsec = disc.section(*START)
    templates = []
    for r in range(TEMPLATES["count"]):
        rec = tsec.at(TEMPLATES["start"] + r * TEMPLATES["stride"], TEMPLATES["stride"])
        templates.append({"roster": r, "jp": decode_name(rec[0:5]), "char_id": rec[5], "level": rec[6],
                          "exp": struct.unpack_from("<I", rec, 8)[0],
                          "hp": struct.unpack_from("<H", rec, 0x14)[0],
                          "ap": struct.unpack_from("<H", rec, 0x16)[0]})
    for t in templates[:len(recs)]:
        if t["jp"] != recs[t["roster"]]["jp"]:
            raise SystemExit("START.EMI template %d is %s, COMMU02 says %s" % (t["roster"], t["jp"], recs[t["roster"]]["jp"]))
    return sec, tsec, recs, templates


# --- TOML out ----------------------------------------------------------------
def tq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tval(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return tq(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(tval(x) for x in v) + "]"
    raise TypeError(type(v))


def emit(path, header, meta, kind, recs, keys):
    lines = [header.rstrip("\n"), ""]
    lines.append("[meta]")
    for k, v in meta:
        lines.append("%s = %s" % (k, tval(v)))
    lines.append("")
    for r in recs:
        lines.append("[[%s]]" % kind)
        for k in keys:
            if k not in r or r[k] is None:
                continue
            v = r[k]
            if k == "ram" or (k in ("ref",) and isinstance(v, int)):
                lines.append("%s = %s" % (k, "0x%08X" % v if k == "ram" else "%#06x" % v))
            else:
                lines.append("%s = %s" % (k, tval(v)))
        lines.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def common_meta(disc, sec, extra):
    return [("generator", "tools/text_tables.py"), ("disc", disc.label), ("source", sec.source()),
            ("section_md5", sec.md5), ("section_dest", "0x%08X" % sec.dest)] + extra


def cmd_extract(args, disc, gloss):
    outdir = args.out_dir
    os.makedirs(outdir, exist_ok=True)
    written = []

    sec, tables = read_items(disc, gloss)
    recs = [r for _, rs in tables for r in rs]
    layout = ["%s: %#010x stride %d count %d" % (t["category"], t["start"], t["stride"], len(rs)) for t, rs in tables]
    header = ("# names/items.toml -- id->name for every item table in GAME.EMI, generated by\n"
              "# tools/text_tables.py extract (do not hand-edit; re-run instead).\n"
              "# Five separate tables, one per inventory category (docs/TEXT_TABLES.md):\n"
              "#   category   cat  (inventory list at 0x80145048 + cat*128; key items 0x80145448)\n"
              "#   id         record index = the byte the saves and the RAM hold\n"
              "#   jp / en    the name as stored / the wiki glossary's English (empty = no row)\n"
              "#   price      u16 shop price (consumables: the -20 per 薬草 seen in the shop trace)\n"
              "#   power      u16 ATK (weapon) / DEF (armour) bonus -- hypothesis until save_tool verifies it\n"
              "#   ref        u16, 0x40xx/0x41xx -- an index into something shared with the ability table (unread)\n"
              "#   flags / u16_* / raw   the other record bytes, undecoded")
    emit(os.path.join(outdir, "items.toml"), header,
         common_meta(disc, sec, [("layout", layout)]), "item", recs,
         ["category", "cat", "id", "ram", "jp", "en", "note", "gloss_section", "price", "power", "flags",
          "ref", "u16_8", "u16_10", "u16_12", "raw"])
    written.append(("items.toml", len(recs)))

    sec, recs = read_abilities(disc, gloss)
    header = ("# names/abilities.toml -- id->name for the ability/skill table GAME.EMI 0x801CB230\n"
              "# (16-byte records: 8 param bytes then name[8]), generated by tools/text_tables.py.\n"
              "#   id      record index = the byte in the record's four ability lists (+0x5C/+0x66/+0x70/+0x7A)\n"
              "#   type    b1 & 3 -- which of the four lists AbilityList_ForType (boot 0x80167514) files it in\n"
              "#           (0 healing, 1 support, 2 attack magic, 3 skills -- a reading of the names)\n"
              "#   b0      & 0x20 = default target on the enemy side (Skill_TargetSetup 0x80094768)\n"
              "#   u16_4   flags read by Actor_SkillItemDone (& 0x800) and the enemy-AI mask\n"
              "#   u16_6   flags read by SkillMenu_Confirm; runs 0x40FC + id for the first 200-odd ids\n"
              "#   b2, b3, raw   undecoded (b5 = AP cost is a hypothesis; see docs/TEXT_TABLES.md)")
    emit(os.path.join(outdir, "abilities.toml"), header,
         common_meta(disc, sec, [("start", "0x801CB230"), ("stride", 16), ("count", len(recs))]),
         "ability", recs, ["id", "ram", "jp", "en", "note", "gloss_section", "type", "b0", "b1", "b2", "b3", "u16_4", "u16_6", "raw"])
    written.append(("abilities.toml", len(recs)))

    sec, head_u32, recs = read_places(disc, gloss)
    header = ("# names/places.toml -- one entry per AREA file: the debug map-select list in MTEST.EMI\n"
              "# (200 x 10-byte kana names at 0x801D0D94; id = AREA number) joined to the area's own\n"
              "# script block (docs/TEXT_TABLES.md 'Places').\n"
              "#   jp         the debug list's kana name; ' S' / ' A' = the spring / autumn variant (season)\n"
              "#   area_file  BIN/WORLDnn/AREAnnn.EMI -- the key names/areas.toml uses\n"
              "#   caption    the on-entry banner the game draws (<0c> ... <16> message), kanji as displayed\n"
              "#   dev_label  message 0 of the script when it is a bare label (developer's map name)\n"
              "#   en         wiki glossary English; en_source says which string matched (caption / dev_label / jp)\n"
              "#   sel        the two bytes the list head holds for this entry (0x801D0C04 + 2*id), undecoded")
    emit(os.path.join(outdir, "places.toml"), header,
         common_meta(disc, sec, [("names", "0x801D0D94"), ("stride", 10), ("count", len(recs)),
                                 ("head_u32", head_u32), ("status", "caption = evidence (what the game draws); dev_label and en = hypothesis")]),
         "place", recs, ["id", "ram", "jp", "area_file", "season", "caption", "dev_label", "en", "en_source", "note", "sel"])
    written.append(("places.toml", len(recs)))

    sec, tsec, recs, templates = read_characters(disc, gloss)
    header = ("# names/characters.toml -- the roster names (COMMU02.EMI 0x801DB214, 5-byte stride, roster\n"
              "# order 0..6 = the character record order at 0x80144964) and the new-game record\n"
              "# templates START.EMI 0x801EB4A4 (8 x 0xA4; roster 7 = the intro whelp, char_id 10).")
    emit(os.path.join(outdir, "characters.toml"), header,
         common_meta(disc, sec, [("templates_source", tsec.source()), ("templates_md5", tsec.md5),
                                 ("templates", "0x801EB4A4")]),
         "character", recs, ["id", "ram", "jp", "en"])
    with open(os.path.join(outdir, "characters.toml"), "a", encoding="utf-8", newline="\n") as f:
        for t in templates:
            f.write("[[template]]\n")
            for k in ("roster", "jp", "char_id", "level", "exp", "hp", "ap"):
                f.write("%s = %s\n" % (k, tval(t[k])))
            f.write("\n")
    written.append(("characters.toml", len(recs)))
    for name, n in written:
        print("wrote %s  (%d records)" % (os.path.join(outdir, name), n))
    return 0


def cmd_show(args, disc, gloss):
    if args.table == "items":
        _, tables = read_items(disc, gloss)
        for t, recs in tables:
            if args.category and t["category"] != args.category:
                continue
            print("# %s  %#010x stride %d  %d records" % (t["category"], t["start"], t["stride"], len(recs)))
            for r in recs:
                extra = " ".join("%s=%d" % (k, r[k]) for k in ("price", "power") if k in r)
                print("%3d %-10s %-22s %s  raw %s" % (r["id"], r["jp"], r["en"] or "", extra, r["raw"]))
    elif args.table == "abilities":
        _, recs = read_abilities(disc, gloss)
        for r in recs:
            print("%3d %#04x t%d %-10s %-18s raw %s" % (r["id"], r["id"], r["type"], r["jp"], r["en"] or "", r["raw"]))
    elif args.table == "places":
        _, head, recs = read_places(disc, gloss)
        print("# head u32 %#x" % head)
        for r in recs:
            print("%3d %-16s %-8s cap=%-14s dev=%-14s %-22s %-9s sel %02x %02x"
                  % (r["id"], r["jp"], r["area_file"][4:11], r["caption"] or "", r["dev_label"] or "",
                     r["en"] or "", r["en_source"] or "", r["sel"][0], r["sel"][1]))
    elif args.table == "characters":
        _, _, recs, templates = read_characters(disc, gloss)
        for r in recs:
            print("%d %-6s %s" % (r["id"], r["jp"], r["en"] or ""))
        for t in templates:
            print("template roster %d %-6s char_id %d Lv %d EXP %d HP %d AP %d"
                  % (t["roster"], t["jp"], t["char_id"], t["level"], t["exp"], t["hp"], t["ap"]))
    return 0


def default_cue():
    try:
        with open(os.path.join(ROOT, "game.toml"), "rb") as f:
            d = tomllib.load(f)["game"]["disc"]
        return d if os.path.isabs(d) else os.path.join(ROOT, d)
    except (OSError, KeyError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=default_cue(), help="legal .cue (default: game.toml [game].disc)")
    ap.add_argument("--bin-root", help="extracted BIN/ directory instead of the .cue")
    ap.add_argument("--kanji-table", default=DEFAULT_KANJI)
    ap.add_argument("--glossary", default=DEFAULT_GLOSSARY)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract", help="write names/*.toml")
    p.add_argument("--out-dir", default=os.path.join(ROOT, "names"))
    p.set_defaults(fn=cmd_extract)
    p = sub.add_parser("show", help="print one table")
    p.add_argument("table", choices=["items", "abilities", "places", "characters"])
    p.add_argument("--category", help="items only: consumable | key | weapon | armour | accessory")
    p.set_defaults(fn=cmd_show)
    args = ap.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not load_kanji(args.kanji_table):
        print("warning: no kanji table at %s -- kanji come out as [12xx]" % args.kanji_table, file=sys.stderr)
    gloss = Glossary(args.glossary)
    if gloss.path is None:
        print("warning: no glossary at %s -- en column left empty" % args.glossary, file=sys.stderr)
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    return args.fn(args, disc, gloss)


if __name__ == "__main__":
    sys.exit(main())
