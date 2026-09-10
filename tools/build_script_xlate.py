#!/usr/bin/env python
r"""build_script_xlate.py -- the English script table, from the US disc.

The JP and US releases carry the area script in the same place (the .EMI
section whose destination is 0x80010000), with the same 256-slot u16 offset
table in every one of the 200 AREA files and the same control-code stream
(docs/TEXT_ENGINE.md).  So the English for a JP message is the US message in
the same slot of the same file -- no address work, no alignment heuristics.

This walks both discs slot by slot, re-encodes the US bytes into the JP
build's own glyph codes (names/font.toml), re-wraps every page to the JP box,
and emits a C table keyed by the FNV-1a64 hash of the JP bytes exactly as
they sit in guest RAM.  The runtime plugin src/bof3_localize.c looks the hash
up at MsgBox_Reset and repoints the box at the English bytes
(docs/LOCALIZATION_APPLY.md).

    python tools/build_script_xlate.py --bin-root D:\BoFIII\BIN \
        --us-cue "isos/Breath of Fire III (USA).cue"
    python tools/build_script_xlate.py ... --width 15     # the JP script's own habit
    python tools/build_script_xlate.py ... --review analysis/xlate_review.txt

Output goes to generated/bof3_xlate_en.c (gitignored, like the game C: the
English script is Capcom's, and it is built locally from the player's own US
dump, never committed).

## What the encoder does and does not do

* Glyphs: the JP sheet has A-Z, digits and a handful of punctuation but no
  lowercase (docs/TEXT_ENGINE.md "The single-byte codes"), so English is
  emitted in capitals for this first pass.  Characters with no JP glyph are
  counted and reported; an apostrophe is dropped, anything else prints as
  `?` so the gap is visible on screen rather than silent.
* Controls are carried through byte for byte: speaker head 0x0C, name and
  record inserts 0x03/0x04/0x07, colour 0x05/0x06, sound 0x0A, pause 0x0B,
  spans 0x0D/0x0E/0x0F, flags 0x10/0x11, timed break 0x16, and the 0x14
  choice menu (three argument bytes, then count NUL-terminated options).
* Layout is re-authored: US 0x01 newlines are soft (the US box is wider and
  proportional), each page is word-wrapped to --width cells, and a page that
  needs more than --rows rows is split with a 0x02 confirm break instead of a
  fourth row -- the same policy docs/FURIGANA.md chose, for the same reason.
* Slots whose US text is untranslated (leftover JP bytes) are skipped: the
  JP message stays JP at runtime, which is the plugin's miss path anyway.
"""
import argparse
import collections
import os
import struct
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from text_tables import Disc, default_cue  # noqa: E402
import page_rows                            # noqa: E402

SCRIPT_DEST = 0x80010000
ARG1 = {0x04, 0x05, 0x07, 0x08, 0x0A, 0x0C, 0x0F, 0x16}
CHOICE = 0x14
LEAD = {0x12, 0x13, 0x15}
NEWLINE = 0x01
PAGE = 0x02
TIMED = 0x16
SPACE = 0xFF

# Widths, in 12 px cells, that an insert occupies for wrapping. Party names
# are at most five letters in the US script (Teepo, Garr, Momo, Peco, Nina);
# the 32-byte record insert (0x07) holds item / place names.
INSERT_WIDTH = {0x03: 5, 0x04: 5, 0x07: 8, 0x08: 11}

# --- the US byte table ------------------------------------------------------
# Read off the script (contexts in docs/LOCALIZATION_APPLY.md): letters and
# digits are ASCII, the rest is the US font's own order.
US_TABLE = {0xFF: " ", 0x3E: ".", 0x3C: ",", 0x3D: "-", 0x5C: "?", 0x5D: "!",
            0x3A: "(", 0x3B: ")", 0x8E: "'", 0x8F: ":", 0x90: '"', 0x8D: "&",
            0x8B: "#"}
for _b in range(0x30, 0x3A):
    US_TABLE[_b] = chr(_b)
for _b in range(0x41, 0x5B):
    US_TABLE[_b] = chr(_b)
for _b in range(0x61, 0x7B):
    US_TABLE[_b] = chr(_b)

# --- the JP byte table (names/font.toml + the kanji table) -------------------
def load_jp_tables():
    with open(os.path.join(ROOT, "names", "font.toml"), "rb") as f:
        font = tomllib.load(f)
    single = {int(k, 16): v for k, v in font["single"].items()}
    page15 = {int(k, 16): v for k, v in font["page15"].items()}
    encode = {}
    for code, ch in single.items():
        encode.setdefault(ch, bytes([code]))
    for code, ch in page15.items():
        encode.setdefault(ch, bytes([0x15, code]))
    return single, page15, encode


def make_encoder(encode):
    """char -> JP bytes, for the English pass.  Capitals only: the sheet has
    no lowercase.  Returns (bytes, ok)."""
    table = dict(encode)
    table[" "] = bytes([SPACE])
    table['"'] = bytes([0x2A])        # 「 -- the JP script's own speech opener
    table[":"] = bytes([0x3A])        # ・
    table[";"] = bytes([0x2C])
    table["'"] = b""                  # no apostrophe glyph on the sheet (yet)
    table["&"] = encode.get("＆", b"?")
    table["#"] = encode.get("＆", b"?")
    table["-"] = bytes([0x2D])        # ー doubles as the dash
    table["?"] = bytes([0x3F])        # the sheet's ？ and ！ are the ASCII slots
    table["!"] = bytes([0x40])
    for c in "abcdefghijklmnopqrstuvwxyz":
        table[c] = bytes([ord(c.upper())])
    return table


# --- walking a message ------------------------------------------------------
def message_extent(buf, off):
    """Length of the message at off, control-aware.  The 0x14 choice menu
    carries NULs inside it (its first argument is usually 0x00 and its options
    are NUL-terminated), so data.find(b'\\0') is wrong there.  Mirrors
    msg_extent() in src/bof3_localize.c -- keep the two in step."""
    i, n = off, len(buf)
    while i < n:
        b = buf[i]
        if b == 0:
            return i + 1 - off
        if b == CHOICE:
            if i + 3 >= n:
                return 0
            count = buf[i + 3] & 0xF
            i += 4
            for _ in range(count):
                e = buf.find(b"\0", i)
                if e < 0:
                    return 0
                i = e + 1
            return i - off
        if b in ARG1 or b in LEAD:
            i += 2
        else:
            i += 1
    return 0


def parse_message(raw):
    """Split a message into (head, pages, tail).

    head  -- the leading 0x0C nn speaker bytes, or b''
    pages -- list of (items, terminator) where items are
             ('w', text) a word, ('s',) a space, ('n',) a US newline,
             ('c', bytes, width) an inline control;
             terminator is b'\\x02', b'\\x16nn' or b'' (the last page)
    tail  -- the 0x14 choice block (verbatim bytes incl. options) or b''
    """
    i, n = 0, len(raw)
    head = b""
    if n >= 2 and raw[0] == 0x0C:
        head, i = raw[0:2], 2
    pages, items, word = [], [], []
    tail = b""

    def flush_word():
        if word:
            items.append(("w", "".join(word)))
            word.clear()

    while i < n:
        b = raw[i]
        if b == 0:
            break
        if b == CHOICE:
            flush_word()
            tail = raw[i:]
            break
        if b == NEWLINE:
            flush_word(); items.append(("n",)); i += 1
        elif b == PAGE:
            flush_word(); pages.append((items, b"\x02")); items = []; i += 1
        elif b == TIMED:
            flush_word(); pages.append((items, raw[i:i + 2])); items = []; i += 2
        elif b == SPACE:
            flush_word(); items.append(("s",)); i += 1
        elif b in ARG1:
            flush_word(); items.append(("c", raw[i:i + 2], INSERT_WIDTH.get(b, 0))); i += 2
        elif b < 0x12 or b == 0x10 or b == 0x11:
            flush_word(); items.append(("c", raw[i:i + 1], INSERT_WIDTH.get(b, 0))); i += 1
        elif b in LEAD:
            # a JP glyph left in the US slot: this slot was not translated
            return None
        elif b in US_TABLE:
            word.append(US_TABLE[b]); i += 1
        else:
            return None
    flush_word()
    if items or not pages:
        pages.append((items, b""))
    return head, pages, tail


# --- layout + encoding -------------------------------------------------------
class Encoder:
    def __init__(self, width, rows):
        _, _, enc = load_jp_tables()
        self.table = make_encoder(enc)
        self.width, self.rows = width, rows
        self.unknown = collections.Counter()
        self.split_pages = 0

    def glyphs(self, text):
        """text -> list of (bytes, cells).  '...' runs collapse to one ‥."""
        out = []
        i = 0
        while i < len(text):
            c = text[i]
            if c == ".":
                j = i
                while j < len(text) and text[j] == ".":
                    j += 1
                if j - i >= 2:
                    out.append((self.table["‥"], 1)); i = j; continue
            b = self.table.get(c)
            if b is None:
                self.unknown[c] += 1
                b = self.table["？"]
            if b:
                out.append((b, 1))
            i += 1
        return out

    def layout_page(self, items):
        """Word-wrap one page into rows of at most self.width cells.
        Returns a list of rows, each a list of byte strings."""
        rows, row, used = [], [], 0
        pending_space = False
        lead = 0                       # leading spaces of the page, kept
        k = 0
        while k < len(items) and items[k][0] == "s":
            lead += 1; k += 1
        if lead:
            row.append(bytes([SPACE]) * lead); used = lead
        for it in items[k:]:
            kind = it[0]
            if kind in ("s", "n"):
                pending_space = True
                continue
            if kind == "c":
                w = it[2]
                if w and used and used + (1 if pending_space else 0) + w > self.width:
                    rows.append(row); row, used = [], 0; pending_space = False
                if pending_space and used:
                    row.append(bytes([SPACE])); used += 1
                pending_space = False
                row.append(it[1]); used += w
                continue
            gl = self.glyphs(it[1])
            w = sum(c for _, c in gl)
            if w == 0:
                continue
            if used and used + (1 if pending_space else 0) + w > self.width:
                rows.append(row); row, used = [], 0; pending_space = False
            if pending_space and used:
                row.append(bytes([SPACE])); used += 1
            pending_space = False
            if w > self.width:             # a word longer than the box
                for b, c in gl:
                    if used + c > self.width:
                        rows.append(row); row, used = [], 0
                    row.append(b); used += c
            else:
                row.extend(b for b, _ in gl); used += w
        if row or not rows:
            rows.append(row)
        return rows

    def encode(self, parsed):
        head, pages, tail = parsed
        out = bytearray(head)
        for items, term in pages:
            rows = self.layout_page(items)
            if len(rows) > self.rows:
                self.split_pages += 1
            for r0 in range(0, len(rows), self.rows):
                chunk = rows[r0:r0 + self.rows]
                for ri, row in enumerate(chunk):
                    if ri:
                        out.append(NEWLINE)
                    for b in row:
                        out += b
                if r0 + self.rows < len(rows):
                    out.append(PAGE)
            out += term
        if tail:
            out += self.encode_choice(tail)
        else:
            out.append(0)
        return bytes(out)

    def encode_choice(self, tail):
        count = tail[3] & 0xF
        out = bytearray(tail[:4])
        i = 4
        for _ in range(count):
            e = tail.find(b"\0", i)
            text = "".join(US_TABLE.get(b, "?") for b in tail[i:e])
            for b, _ in self.glyphs(text):
                out += b
            out.append(0)
            i = e + 1
        return bytes(out)


def fnv1a64(data):
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def decode_jp(raw, single, page15):
    """Rough JP decode for the review file (kanji through the prior table)."""
    dec = page_rows.load_decoder()
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x12, 0x13) and i + 1 < len(raw):
            out.append(dec(raw[i:i + 2]) if dec else "[%02x%02x]" % (b, raw[i + 1])); i += 2
        elif b == 0x15 and i + 1 < len(raw):
            out.append(page15.get(raw[i + 1], "[15%02x]" % raw[i + 1])); i += 2
        elif b == NEWLINE:
            out.append("/"); i += 1
        elif b == PAGE:
            out.append(" ⏎ "); i += 1
        elif b in ARG1:
            out.append("<%02x%02x>" % (b, raw[i + 1] if i + 1 < len(raw) else 0)); i += 2
        elif b < 0x12 or b == CHOICE:
            out.append("<%02x>" % b); i += 1
        elif dec and b >= 0x5B and b != SPACE:
            out.append(dec(bytes([b]))); i += 1
        else:
            out.append(single.get(b, "<%02x>" % b)); i += 1
    return "".join(out)


def decode_en(raw, single, page15):
    return decode_jp(raw, single, page15)


# --- main --------------------------------------------------------------------
def emit_c(path, entries, code="en", tool="tools/build_script_xlate.py",
           what="English area-script table", prefix="bof3_xlate"):
    """Write one language table: symbols <prefix>_<code>_* (src/bof3_xlate_table.h).
    prefix "bof3_xlate" is a message table (hash of the JP message bytes);
    "bof3_insert" is a runtime-insert table (hash of the 0x07 record bytes,
    docs/INSERT_RUBY.md) -- the same layout, read by the same plugin."""
    entries.sort(key=lambda e: e[0])
    blob = bytearray()
    offs, lens = [], []
    for h, enc in entries:
        offs.append(len(blob)); lens.append(len(enc)); blob += enc
    sym = "%s_%s" % (prefix, code)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("/* Generated by %s -- do not edit, do not commit.\n"
                " * %s for src/bof3_localize.c: FNV-1a64 of the JP\n"
                " * bytes (as they sit in guest RAM) -> replacement bytes.\n"
                " * docs/LOCALIZATION_APPLY.md */\n" % (tool, what))
        f.write("#include <stdint.h>\n#include \"bof3_xlate_table.h\"\n\n")
        f.write("const uint32_t %s_count = %du;\n" % (sym, len(entries)))
        f.write("const uint64_t %s_hash[%d] = {\n" % (sym, max(1, len(entries))))
        for i, (h, _) in enumerate(entries):
            f.write("0x%016xull,%s" % (h, "\n" if i % 4 == 3 else " "))
        f.write("};\n")
        f.write("const uint32_t %s_off[%d] = {\n" % (sym, max(1, len(entries))))
        for i, o in enumerate(offs):
            f.write("%du,%s" % (o, "\n" if i % 8 == 7 else " "))
        f.write("};\n")
        f.write("const uint16_t %s_len[%d] = {\n" % (sym, max(1, len(entries))))
        for i, l in enumerate(lens):
            f.write("%du,%s" % (l, "\n" if i % 8 == 7 else " "))
        f.write("};\n")
        f.write("const uint8_t %s_blob[%d] = {\n" % (sym, max(1, len(blob))))
        for i in range(0, len(blob), 24):
            f.write(",".join("%d" % b for b in blob[i:i + 24]) + ",\n")
        f.write("};\n")
    return len(blob)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=default_cue(), help="JP disc .cue")
    ap.add_argument("--bin-root", help="extracted JP BIN/ tree instead of the .cue")
    ap.add_argument("--us-cue", required=True, help="US disc .cue (SLUS-00422)")
    ap.add_argument("--width", type=int, default=16,
                    help="box width in cells: the frame interior is 192 px = 16 cells "
                         "(window record w=16 in 12.4 fixed; measured on screen 2026-09-09)")
    ap.add_argument("--rows", type=int, default=3, help="rows per page before a split")
    ap.add_argument("--out", default=os.path.join(ROOT, "generated", "bof3_xlate_en.c"))
    ap.add_argument("--review", help="write a JP / EN side-by-side text file here")
    ap.add_argument("--max-len", type=int, default=2040,
                    help="refuse an encoded message longer than this (plugin slot size)")
    args = ap.parse_args(argv)

    jp = Disc(cue=args.cue, bin_root=args.bin_root)
    us = Disc(cue=args.us_cue)
    single, page15, _ = load_jp_tables()
    enc = Encoder(args.width, args.rows)

    seen = {}
    entries = []
    stats = collections.Counter()
    conflicts = 0
    review = open(args.review, "w", encoding="utf-8") if args.review else None
    longest = (0, None)

    for path in page_rows.area_paths(jp):
        jd = jp.section(path, SCRIPT_DEST).data
        ud = us.section(path, SCRIPT_DEST).data
        jn = struct.unpack_from("<H", jd, 0)[0] // 2
        un = struct.unpack_from("<H", ud, 0)[0] // 2
        if jn != un:
            raise SystemExit("%s: slot count differs JP %d / US %d" % (path, jn, un))
        for m in range(jn):
            joff = struct.unpack_from("<H", jd, 2 * m)[0]
            uoff = struct.unpack_from("<H", ud, 2 * m)[0]
            jl = message_extent(jd, joff)
            ul = message_extent(ud, uoff)
            stats["slots"] += 1
            if not jl or not ul:
                stats["unterminated"] += 1
                continue
            jraw = jd[joff:joff + jl]
            uraw = ud[uoff:uoff + ul]
            h = fnv1a64(jraw)
            parsed = parse_message(uraw)
            if parsed is None:
                stats["untranslated_slot"] += 1
                continue
            if h in seen:
                if seen[h] != uraw:
                    conflicts += 1
                stats["duplicate"] += 1
                continue
            e = enc.encode(parsed)
            if len(e) > args.max_len:
                stats["too_long"] += 1
                continue
            seen[h] = uraw
            entries.append((h, e))
            if len(e) > longest[0]:
                longest = (len(e), "%s slot %d" % (path, m))
            if review:
                review.write("== %s slot %d  jp %d B  en %d B  %016x\n" % (path, m, jl, len(e), h))
                review.write("JP  " + decode_jp(jraw, single, page15) + "\n")
                review.write("EN  " + decode_en(e, single, page15) + "\n\n")
    if review:
        review.close()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    blob = emit_c(args.out, entries)
    print("wrote %s: %d entries, %d blob bytes" % (args.out, len(entries), blob))
    print("slots %d, duplicate JP strings %d (conflicting English %d), "
          "untranslated US slots %d, unterminated %d, too long %d"
          % (stats["slots"], stats["duplicate"], conflicts,
             stats["untranslated_slot"], stats["unterminated"], stats["too_long"]))
    print("pages split for exceeding %d rows at width %d: %d"
          % (args.rows, args.width, enc.split_pages))
    print("longest encoded message: %d bytes (%s)" % longest)
    if enc.unknown:
        print("characters with no JP glyph (printed as ？): %s"
              % ", ".join("%r x%d" % kv for kv in enc.unknown.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
