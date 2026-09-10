#!/usr/bin/env python
r"""page_rows.py -- how the shipped script actually uses the message box.

Three censuses over the 200 area script blocks (the `.EMI` section whose RAM
destination is 0x80010000, selected by destination, never by index):

  rows    lines per page, split by which page-break code ended the page.
          A page ends at 0x02 (wait for confirm) or 0x16 <frames> (timed
          auto-advance); rows = 0x01 newlines + 1.
  codes   control-code frequency with the argument histogram of every code
          that takes one.
  styles  every 0x0F text-effect use, resolved against the 26-entry preset
          table at 0x8017FF30 read out of the staged boot EXE.

    python tools/page_rows.py rows   --bin-root D:\BoFIII\BIN
    python tools/page_rows.py codes  --cue "<legal .cue>"
    python tools/page_rows.py styles --bin-root D:\BoFIII\BIN --examples 3

Disc bytes come from the .cue in game.toml or an already-extracted BIN/ tree,
through the same read-only reader `tools/text_tables.py` uses.  The preset
table is read from `disc/SLPS_009.90` at its load address, not hard-coded.
Japanese is decoded with the character table of the prior decode work
(BOF3_DECODER, default D:\BoFIII); without it the census still runs and the
examples print as hex.

Every number this prints is a byte count, not a hypothesis: the walker knows
which codes carry an argument byte and which byte values are multi-byte glyph
lead bytes, so a trailing 0x01 inside a kanji code is never miscounted as a
newline.  See docs/TEXT_ENGINE.md for what the codes mean.
"""
import argparse
import collections
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from emi import Emi                          # noqa: E402
from text_tables import Disc, default_cue    # noqa: E402

SCRIPT_DEST = 0x80010000
EXE = os.path.join(ROOT, "disc", "SLPS_009.90")
EXE_LOAD = 0x80093800          # docs/INVENTORY.md
EXE_HEADER = 0x800
STYLE_TABLE = 0x8017FF30       # 4 bytes per preset: type, param, u16 duration
STYLE_COUNT = 26               # entries 26.. are other tables, not presets

DECODER_DIR = os.environ.get("BOF3_DECODER", r"D:\BoFIII")

# Codes that consume one argument byte, and the multi-byte glyph lead bytes.
ARG1 = {0x04, 0x05, 0x07, 0x08, 0x0A, 0x0C, 0x0F, 0x14, 0x16}
LEAD = {0x12, 0x13, 0x15}
PAGE_BREAK = {0x02, 0x16}
NEWLINE = 0x01

EFFECT = {1: "reset to normal", 2: "grow", 3: "shrink"}


def load_decoder():
    """The prior decode work's character table, or None if it is not here."""
    if DECODER_DIR not in sys.path:
        sys.path.insert(0, DECODER_DIR)
    try:
        import decode_text
    except ImportError:
        return None
    return decode_text.decode


def tokens(buf, start):
    """Walk one message, yielding (code, arg, next_offset).

    `code` is the control byte, or 'g' for a glyph.  Stops at the 0x00
    terminator or the end of the block.
    """
    i, n = start, len(buf)
    while i < n:
        b = buf[i]
        if b == 0x00:
            return
        if b in LEAD:
            i += 2
            yield "g", None, i
        elif b in ARG1:
            arg = buf[i + 1] if i + 1 < n else None
            i += 2
            yield b, arg, i
        elif b <= 0x11 or b == 0x14:
            i += 1
            yield b, None, i
        else:
            i += 1
            yield "g", None, i


def area_paths(disc):
    """BIN/WORLDnn/AREAnnn.EMI, disc order."""
    if disc.bin_root:
        import glob
        found = glob.glob(os.path.join(disc.bin_root, "WORLD*", "AREA*.EMI"))
        rel = ["BIN/" + os.path.relpath(f, disc.bin_root).replace(os.sep, "/") for f in found]
    else:
        rel = [k for k in disc._entries if re.fullmatch(r"BIN/WORLD\d+/AREA\d+\.EMI", k)]
    return sorted(rel)


def script_blocks(disc):
    """Yield (path, section index, block bytes) for every area script block.

    The block *is* the u16 message-offset table: entry 0 is the offset of
    message 0, so entry0 / 2 is the message count.  A block whose entry 0 is
    odd, zero or past the end is not a table and is refused, not guessed at.
    """
    for path in area_paths(disc):
        emi = Emi(disc.read(path), path)
        for e in emi.entries:
            if e["dest"] != SCRIPT_DEST or e["size"] < 16:
                continue
            data = emi.data(e["index"])
            first, = struct.unpack_from("<H", data, 0)
            if first == 0 or first % 2 or first > len(data):
                raise SystemExit("%s section %d: offset table starts at %d, not a table"
                                 % (path, e["index"], first))
            yield path, e["index"], data


def messages(disc):
    """Yield (path, index, message number, block, offset) once per *distinct*
    message.  The tables point several slots at the same string and at suffixes
    of longer ones, so counting slots would count the same page many times."""
    seen = set()
    for path, index, data in script_blocks(disc):
        first, = struct.unpack_from("<H", data, 0)
        for m in range(first // 2):
            off, = struct.unpack_from("<H", data, 2 * m)
            if off >= len(data):
                continue
            end = data.find(b"\x00", off)
            raw = data[off:end if end >= 0 else len(data)]
            if raw in seen:
                continue
            seen.add(raw)
            yield path, index, m, data, off


def _count(hist, by_term, areas, examples, newlines, term, path, m, data, start, end):
    hist[newlines] += 1
    by_term[(newlines, term)] += 1
    areas[newlines].add(path)
    if len(examples[newlines]) < 64:
        stop = end if end is not None else data.find(b"\x00", start)
        examples[newlines].append((path, m, data[start:stop if stop >= 0 else len(data)]))


def cmd_rows(disc, args):
    decode = load_decoder()
    hist = collections.Counter()
    by_term = collections.Counter()
    areas = collections.defaultdict(set)
    examples = collections.defaultdict(list)
    total = 0
    for path, index, m, data, off in messages(disc):
        total += 1
        newlines, page_start = 0, off
        for code, _arg, nxt in tokens(data, off):
            if code == NEWLINE:
                newlines += 1
            elif code in PAGE_BREAK:
                _count(hist, by_term, areas, examples, newlines, code, path, m, data, page_start, nxt)
                newlines, page_start = 0, nxt
        _count(hist, by_term, areas, examples, newlines, "end", path, m, data, page_start, None)

    print("# rows per page -- %s" % disc.label)
    print("# %d distinct messages, %d pages" % (total, sum(hist.values())))
    print("%5s %8s %9s %9s %9s %7s" % ("rows", "pages", "0x02", "0x16", "no break", "areas"))
    for n in sorted(hist):
        print("%5d %8d %9d %9d %9d %7d"
              % (n + 1, hist[n], by_term[(n, 0x02)], by_term[(n, 0x16)],
                 by_term[(n, "end")], len(areas[n])))
    if args.examples:
        for n in sorted(examples):
            if n + 1 < args.min_rows:
                continue
            print("\n## %d rows" % (n + 1))
            for path, m, page in examples[n][:args.examples]:
                print("  %s msg%-4d %s" % (os.path.basename(path), m,
                                           decode(page) if decode else page.hex(" ")))
    return 0


def cmd_codes(disc, args):
    codes = collections.Counter()
    argv = collections.defaultdict(collections.Counter)
    total = 0
    for path, index, m, data, off in messages(disc):
        total += 1
        for code, arg, _nxt in tokens(data, off):
            if code == "g":
                continue
            codes[code] += 1
            if arg is not None:
                argv[code][arg] += 1
    print("# control codes -- %s, %d distinct messages" % (disc.label, total))
    for code in sorted(codes):
        top = ", ".join("%02x:%d" % (a, n) for a, n in argv[code].most_common(args.top))
        print("  %02x  %6d   %s" % (code, codes[code], top))
    return 0


def read_style_table(exe_path):
    """The 0x0F preset table, read out of the staged boot EXE."""
    with open(exe_path, "rb") as fh:
        blob = fh.read()
    off = STYLE_TABLE - EXE_LOAD + EXE_HEADER
    if off + 4 * STYLE_COUNT > len(blob):
        raise SystemExit("%s: 0x%08X is past the end of the EXE" % (exe_path, STYLE_TABLE))
    out = []
    for i in range(STYLE_COUNT):
        kind, param, dur = struct.unpack_from("<BbH", blob, off + 4 * i)
        out.append((kind, param, dur))
    return out


def cmd_styles(disc, args):
    decode = load_decoder()
    table = read_style_table(args.exe)
    uses = collections.defaultdict(list)
    for path, index, m, data, off in messages(disc):
        for code, arg, _nxt in tokens(data, off):
            if code == 0x0F and arg is not None:
                end = data.find(b"\x00", off)
                uses[arg].append((path, m, data[off:end if end >= 0 else len(data)]))
    print("# 0x0F text-effect presets -- table at 0x%08X in %s"
          % (STYLE_TABLE, os.path.basename(args.exe)))
    print("# the size delta lands in 0x801490C4 and is added to the glyph quad's width and height")
    print("%5s %6s %-24s %-12s %s" % ("arg", "uses", "preset", "duration", "raw"))
    for i, (kind, param, dur) in enumerate(table):
        raw = "%02x %02x %04x" % (kind, param & 0xFF, dur)
        if kind in EFFECT:
            name = EFFECT[kind] + ("" if kind == 1 else " %+d px" % param)
            frames = "forever" if dur == 0xFFFF else "%d frames" % dur
        else:
            # Types 4 and 5 are not the size effect and their last two bytes do
            # not read as a frame count; print the bytes rather than a fiction.
            name = "type %d param %d" % (kind, param)
            frames = "?"
        print("%5d %6d %-24s %-12s %s" % (i, len(uses.get(i, [])), name, frames, raw))
    for i in sorted(uses):
        if not args.examples:
            break
        print("\n## arg %d" % i)
        for path, m, raw in uses[i][:args.examples]:
            print("  %s msg%-4d %s" % (os.path.basename(path), m,
                                       decode(raw) if decode else raw.hex(" ")))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["rows", "codes", "styles"])
    ap.add_argument("--cue", default=default_cue(), help="legal .cue (default: game.toml [game].disc)")
    ap.add_argument("--bin-root", help="extracted BIN/ directory instead of the .cue")
    ap.add_argument("--exe", default=EXE, help="staged boot EXE, for the style table")
    ap.add_argument("--examples", type=int, default=0, help="decoded examples per bucket")
    ap.add_argument("--min-rows", type=int, default=4, help="rows: only show examples this tall or taller")
    ap.add_argument("--top", type=int, default=12, help="codes: argument values to list per code")
    args = ap.parse_args(argv)
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    return {"rows": cmd_rows, "codes": cmd_codes, "styles": cmd_styles}[args.command](disc, args)


if __name__ == "__main__":
    sys.exit(main())
