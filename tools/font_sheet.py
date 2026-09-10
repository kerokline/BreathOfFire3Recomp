#!/usr/bin/env python
r"""font_sheet.py -- the single-byte half of the text encoding, off the disc.

The kanji half of BoF3's encoding (`0x12xx` / `0x13xx`) was decoded by the
prior work; the single-byte codes were not, which blocked writing text rather
than reading it.  This closes that: it rebuilds the font sheet from
`BIN/ETC/ENDKANJI.EMI`, lays the engine's own index arithmetic over it, and
emits `names/font.toml`.

    python tools/font_sheet.py render --bin-root D:\BoFIII\BIN    # labelled PNGs
    python tools/font_sheet.py table  --bin-root D:\BoFIII\BIN    # -> names/font.toml
    python tools/font_sheet.py show 3b --bin-root D:\BoFIII\BIN   # one glyph, big

## The sheet

`ENDKANJI.EMI` section 0 (offset `0x800`, 32 KiB, VRAM `1E000200`) is 4bpp,
low-nibble-first, row-major, stride 64 bytes = 128 px, 512 rows, stored as two
interleaved streams of 2048-byte (32-row) chunks: even chunks are the left half
of the sheet, odd chunks the right.  De-interleaved it is a **252 px = 21 cells
of 12 px** wide, 256 px tall sheet -- the same geometry `extract_glyphs.py` in
the prior work solved for the kanji block, and the same 21-wide/12 px atlas the
box's glyph mapper walks (docs/TEXT_ENGINE.md "Glyph path").

## The index arithmetic, from the box's mapper at 0x80151F4C

| byte | cell index | disassembly |
|---|---|---|
| `< 0x5B` | the byte itself | `sltiu 0x5B` at `0x80152740`, then divide by 21 |
| `>= 0x5B` | byte + `0x23` | `addiu 0x23` at `0x801529B8` |
| `0x15 nn` | nn + `0x5B` | third-page bias, docs/TEXT_ENGINE.md |
| `0x12`/`0x13 nn` | the kanji sheet (section 1) | prior work |

Cell `i` sits at `(12 * (i % 21), 12 * (i // 21))`, origin at the sheet's top
left.  The two rules meet exactly: `0x5A` = `Z` is the last cell before the
symbol block, and `0x5B` = `あ` lands at row 6 column 0 -- which is what the
sheet shows, and what makes the whole mapping falsifiable in one look.

The glyph names below were **read off the rendered sheet by eye on
2026-09-09** and cross-checked against use in the script (`0x3E` heavy at
sentence ends is the two-dot leader, `0x48 0x50` spells `HP`, `0x2D` is the
long-vowel bar the name fields already showed).  `render` regenerates the
labelled sheet so anyone can re-check a row in one image.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from emi import Emi                                 # noqa: E402
from text_tables import Disc, default_cue           # noqa: E402

EMI_PATH = "BIN/ETC/ENDKANJI.EMI"
BLOCK = 0                     # section 0: ASCII / symbols / kana
CELL = 12
COLS = 21
KANA_BIAS = 0x23              # added to bytes >= 0x5B  (0x801529B8)
PAGE15_BIAS = 0x5B            # added to the byte after a 0x15 lead

# Read off the rendered sheet 2026-09-09.  Codes below 0x2A are the small
# 8 px UI font (button labels, "START", "SELECT") on a different pitch and are
# not used as glyphs anywhere in the 200 area scripts.
SINGLE = {
    0x28: "(", 0x29: ")",
    0x2A: "\u300c", 0x2B: "\u300d", 0x2C: ",", 0x2D: "\u30fc", 0x2E: ".",
    0x2F: "/",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4", 0x35: "5",
    0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x3A: "\u30fb", 0x3B: "\u300e", 0x3C: "\u300f", 0x3D: "=",
    0x3E: "\u2025", 0x3F: "\uff1f", 0x40: "\uff01",
}
SINGLE.update({c: chr(ord("A") + c - 0x41) for c in range(0x41, 0x5B)})
# 0xFD / 0xFE are the fullwidth stops; 0xFF is special-cased by the mapper
# (0x80152010) and reads as a word separator in every script use.
TAIL = {0xFB: "\u30f4", 0xFD: "\u3002", 0xFE: "\u3001", 0xFF: " "}

# Kanji past 0x13AD, where the prior work's table stops.  Read off the kanji
# sheet and pinned by context in the script: 0x13AF in \u554f\u3046\u304c\u3044\u3044 and
# \u4eca\u306a\u3093\u3058\u3089\u306b\u554f\u3046, 0x13B1 in \u795e\u306e\u610f\u5fd7, 0x13B3 in \u706b\u661f\u30c0\u30b3 and \u30d0\u30cb\u30fc\u306e\u661f,
# 0x13B7 in \u611b\u3059\u3079\u304d\u751f\u547d, 0x13B8 in \u7ba1\u7406\u3059\u308b.
KANJI_EXTRA = {0x13AF: "\u554f", 0x13B1: "\u5fd7", 0x13B3: "\u661f", 0x13B5: "\u53ef",
               0x13B7: "\u611b", 0x13B8: "\u7ba1"}

# The 0x15 page is symbols plus a handful of kanji that did not fit the kanji
# sheet: \u8b77 \u653e \u65e9 \u6d88 \u65b0 \u696d live here, not in the 0x12xx/0x13xx space.  Each was
# read off the sheet and confirmed by context in the script -- 0x0E in \u52a0\u8b77 and
# \u305d\u308c\u3092\u8b77\u3089\u306a\u3044\u3068, 0x10 in \u624b\u653e\u3055\u305a and \u898b\u653e\u3055\u308c\u3066, 0x18 in \u65e9\u30af\u52d5\u3051 and \u3059\u65e9\u304f,
# 0x1D in \u59ff\u3092\u6d88\u3057\u305f, 0x1E in \u65b0\u4eba and \u65b0\u305f\u306b, 0x1F in \u65e5\u3005\u3053\u308c\u696d\u3092\u4fee\u3080\u308b\u3079\u3057,
# 0x06 as the zenny mark in 1000Z, 0x1A as the & of \u30cf\u30a4&\u30ed\u30fc.
PAGE15 = {
    0x00: "\u2191", 0x01: "\u2193", 0x02: "\u2190", 0x03: "\u2192",
    0x04: "\u2665", 0x05: "\u266a", 0x06: "\uff3a", 0x07: "\uff5e",
    0x08: "\u25cb", 0x09: "\u00d7", 0x0a: "\u25b3", 0x0b: "\u25a1",
    0x0c: "\u2605", 0x0e: "\u8b77", 0x0f: "\u25b6", 0x10: "\u653e",
    0x11: "\u2196", 0x12: "\u2198", 0x13: "\u2197", 0x14: "\u2199",
    0x18: "\u65e9", 0x1a: "\uff06", 0x1d: "\u6d88", 0x1e: "\u65b0",
    0x1f: "\u696d",
}


def sheet(disc):
    """The de-interleaved 256 x 252 sheet as a list of rows of nibbles."""
    try:
        import numpy as np
    except ImportError:
        raise SystemExit("font_sheet needs numpy")
    emi = Emi(disc.read(EMI_PATH), EMI_PATH)
    data = emi.data(BLOCK)
    if len(data) != 0x8000:
        raise SystemExit("%s section %d is %d bytes, expected 32768"
                         % (EMI_PATH, BLOCK, len(data)))
    a = np.frombuffer(data, dtype=np.uint8).reshape(512, 64)
    px = np.empty((512, 128), np.uint8)
    px[:, 0::2] = a & 0x0F
    px[:, 1::2] = a >> 4
    left = np.concatenate([px[32 * k:32 * k + 32] for k in range(0, 16, 2)], axis=0)
    right = np.concatenate([px[32 * k:32 * k + 32] for k in range(1, 16, 2)], axis=0)
    return np.concatenate([left, right], axis=1)[:, :COLS * CELL]


def cell_of(code, lead=None):
    """Cell index for a code, by the engine's own arithmetic."""
    if lead == 0x15:
        return code + PAGE15_BIAS
    return code if code < 0x5B else code + KANA_BIAS


def cmd_render(disc, args):
    import numpy as np                                # noqa: F401
    from PIL import Image, ImageDraw
    grid = sheet(disc)
    rows = grid.shape[0] // CELL
    scale = args.scale
    im = Image.fromarray((grid * 17).astype("uint8"), "L").convert("RGB")
    im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for c in range(COLS + 1):
        d.line([(c * CELL * scale, 0), (c * CELL * scale, im.height)], fill=(180, 0, 0))
    for r in range(rows + 1):
        d.line([(0, r * CELL * scale), (im.width, r * CELL * scale)], fill=(180, 0, 0))
    for r in range(rows):
        for c in range(COLS):
            i = r * COLS + c
            if i < 0x5B:
                lab = "%02X" % i
            elif i < 0x5B + KANA_BIAS:
                lab = "15/%02X" % (i - PAGE15_BIAS)
            else:
                lab = "%02X" % (i - KANA_BIAS)
            d.text((c * CELL * scale + 2, r * CELL * scale + 2), lab, fill=(255, 220, 0))
    out = os.path.join(args.out_dir, "font_sheet.png")
    os.makedirs(args.out_dir, exist_ok=True)
    im.save(out)
    print("%s  (%d x %d, %d cells, %d per row)" % (out, im.width, im.height, rows * COLS, COLS))
    return 0


def cmd_show(disc, args):
    from PIL import Image
    grid = sheet(disc)
    code = int(args.code, 16)
    i = cell_of(code, 0x15 if args.page15 else None)
    r, c = divmod(i, COLS)
    crop = grid[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
    im = Image.fromarray((crop * 17).astype("uint8"), "L")
    im = im.resize((CELL * 24, CELL * 24), Image.NEAREST)
    out = os.path.join(args.out_dir, "glyph_%02x.png" % code)
    os.makedirs(args.out_dir, exist_ok=True)
    im.save(out)
    name = (PAGE15 if args.page15 else SINGLE).get(code) or TAIL.get(code) or "?"
    print("%s  code 0x%02X -> cell %d (row %d, col %d)  read as %s" % (out, code, i, r, c, name))
    return 0


def cmd_table(disc, args):
    grid = sheet(disc)
    rows = grid.shape[0] // CELL
    lines = [
        "# names/font.toml -- the single-byte half of the text encoding.",
        "# Generated by tools/font_sheet.py from BIN/ETC/ENDKANJI.EMI section 0.",
        "# Do not hand-edit: change the table in the tool and regenerate.",
        "# See docs/TEXT_ENGINE.md \"The single-byte codes\".",
        "",
        "[sheet]",
        'source = "%s"' % EMI_PATH,
        "section = %d" % BLOCK,
        "cell_px = %d" % CELL,
        "cols = %d" % COLS,
        "rows = %d" % rows,
        'index_rule_low = "byte < 0x5B: cell = byte"',
        'index_rule_high = "byte >= 0x5B: cell = byte + 0x23"',
        'index_rule_page15 = "0x15 nn: cell = nn + 0x5B"',
        'evidence = "mapper 0x80151F4C; sltiu 0x5B at 0x80152740, addiu 0x23 at 0x801529B8"',
        "",
        "[single]",
    ]
    for code in sorted(SINGLE) + sorted(TAIL):
        ch = SINGLE.get(code, TAIL.get(code))
        lines.append('"%02x" = "%s"' % (code, ch.replace('"', '\\"')))
    lines += ["", "[kanji_extra]  # past 0x13AD, where the prior table stops"]
    for code in sorted(KANJI_EXTRA):
        lines.append('"%04x" = "%s"' % (code, KANJI_EXTRA[code]))
    lines += ["", "[page15]"]
    for code in sorted(PAGE15):
        lines.append('"%02x" = "%s"' % (code, PAGE15[code]))
    lines += ["", "# Codes below 0x2A are the small 8 px UI font (button labels, START,",
              "# SELECT) on a different pitch, and no area script uses one as a glyph.",
              "# Codes 0x5B..0xFC are the kana, already in the prior work's table.",
              "# 0xFF is special-cased by the mapper and reads as a word separator."]
    out = os.path.join(ROOT, "names", "font.toml")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("%s  (%d single-byte codes, %d on the 0x15 page, %d kanji past 0x13AD)"
          % (out, len(SINGLE) + len(TAIL), len(PAGE15), len(KANJI_EXTRA)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["render", "table", "show"])
    ap.add_argument("code", nargs="?", help="show: a hex byte, e.g. 3b")
    ap.add_argument("--page15", action="store_true", help="show: the byte after a 0x15 lead")
    ap.add_argument("--cue", default=default_cue())
    ap.add_argument("--bin-root", help="extracted BIN/ directory instead of the .cue")
    ap.add_argument("--scale", type=int, default=8, help="render: pixel scale")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "analysis", "font"))
    args = ap.parse_args(argv)
    if args.command == "show" and not args.code:
        ap.error("show needs a hex code")
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    return {"render": cmd_render, "table": cmd_table, "show": cmd_show}[args.command](disc, args)


if __name__ == "__main__":
    sys.exit(main())
