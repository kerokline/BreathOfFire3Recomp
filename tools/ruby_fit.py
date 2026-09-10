#!/usr/bin/env python
r"""ruby_fit.py -- what inline furigana costs the message box, in rows.

The cheap furigana route needs no engine change: re-author the script with the
reading inline, `漢字（かんじ）`, and ship it as a third script variant.  The
question that decides whether that is viable is how many pages stop fitting.
This measures it against the shipped script, page by page.

    python tools/ruby_fit.py width  --bin-root D:\BoFIII\BIN
    python tools/ruby_fit.py cost   --bin-root D:\BoFIII\BIN
    python tools/ruby_fit.py sample AREA000:19 AREA001:33 --bin-root D:\BoFIII\BIN

  width   line-length census, box pages against everything else.  The box
          number is an *observed maximum*, not a measured clip boundary: it is
          the longest line the shipped script ever puts in a page that waits
          for confirm.
  cost    rows before against rows after, for two layout policies (keep the
          authored line breaks and wrap, or re-flow the whole page) and three
          annotation scopes (every word, first per page, first per area).
  sample  one page rendered three ways, at the box width, for eyeballing.

Readings come from **SudachiPy** (mode C) over the decoded page text, so each
annotation is its real length rather than an average; okurigana already on the
page is trimmed off the reading.  Text decodes through the character table of
the prior decode work (`BOF3_DECODER`, default D:\BoFIII).  Roughly 14% of
glyphs have no entry there -- single-byte punctuation, digits and the `0x15`
atlas page -- and they are counted as one glyph each (correct for width) and
shown to the tokenizer as a full stop so they end a token instead of splitting
one.

Page and message walking is `tools/page_rows.py`; see docs/FURIGANA.md for the
findings and docs/TEXT_ENGINE.md for the control codes.
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import page_rows                                    # noqa: E402
from text_tables import Disc, default_cue           # noqa: E402

DECODER_DIR = os.environ.get("BOF3_DECODER", r"D:\BoFIII")
KANJI_RE = re.compile(r"[\u4e00-\u9fff\u3005]")
HIRA_RE = re.compile(r"[\u3040-\u309f\u30fc]+")
UNKNOWN = "\u3013"          # geta mark: a glyph the character table does not cover
CONFIRM = 0x02

_tok = {}
_dict = {}


def sudachi_dictionary(name="core"):
    """The SudachiPy Dictionary object (for lexicon lookups), one per name."""
    if name not in _dict:
        try:
            from sudachipy import dictionary
        except ImportError:
            raise SystemExit("ruby_fit needs SudachiPy: pip install sudachipy sudachidict_core")
        try:
            _dict[name] = dictionary.Dictionary(dict=name)
        except Exception as e:                      # the dictionary package is separate
            raise SystemExit("SudachiPy dictionary %r is not installed (pip install sudachidict_%s): %s"
                             % (name, name, e))
    return _dict[name]


def tokenizer(name="core"):
    """SudachiPy, mode C, over the named dictionary.  Loud if it is not
    installed -- there is no fallback worth having: an averaged reading length
    would be a guess wearing a number.

    `core` and `full` give the same readings (measured over the whole script,
    0 kanji read differently); `full` knows more compounds, so in mode C it
    yields 武器屋 where core yields 武器 + 屋 -- one reading for the word."""
    if name not in _tok:
        from sudachipy import tokenizer as sudachi_tokenizer
        _tok[name] = (sudachi_dictionary(name).create(), sudachi_tokenizer.Tokenizer.SplitMode.C)
    return _tok[name]


def load_decoder():
    if DECODER_DIR not in sys.path:
        sys.path.insert(0, DECODER_DIR)
    import decode_text
    return decode_text


def glyphs(dec, data, start):
    """Yield ('g', char), ('nl', None) or ('brk', code) for one message.

    One tuple per *drawn cell*: the box advances 12 px for every glyph byte
    whatever it is, so this is the width accounting as well as the text.
    """
    i, n = start, len(data)
    while i < n:
        b = data[i]
        if b == 0x00:
            return
        if b in page_rows.LEAD:
            key = "%02x%02x" % (b, data[i + 1]) if i + 1 < n else "%02x" % b
            yield "g", dec.KANJI.get(key, UNKNOWN)
            i += 2
        elif b in page_rows.ARG1:
            if b in page_rows.PAGE_BREAK:
                yield "brk", b
            i += 2
        elif b == 0x01:
            yield "nl", None
            i += 1
        elif b <= 0x11 or b == 0x14:
            if b in page_rows.PAGE_BREAK:
                yield "brk", b
            i += 1
        else:
            yield "g", dec.KANA.get(b, " " if b == 0xFF else UNKNOWN)
            i += 1


def pages(disc, dec):
    """(path, message number, [rows of glyphs], terminator) per distinct page."""
    for path, _index, m, data, off in page_rows.messages(disc):
        rows, cur = [], []
        for kind, val in glyphs(dec, data, off):
            if kind == "g":
                cur.append(val)
            elif kind == "nl":
                rows.append(cur)
                cur = []
            else:
                rows.append(cur)
                yield path, m, rows, val
                rows, cur = [], []
        rows.append(cur)
        yield path, m, rows, "end"


def kata_to_hira(s):
    return "".join(chr(ord(c) - 0x60) if "\u30a1" <= c <= "\u30f6" else c for c in s)


def inner_kana(surface):
    """True when kana sits between the first and last kanji (最後の夜, 会いに行こう):
    the reading belongs to the whole token, not to a stem."""
    ks = [i for i, c in enumerate(surface) if KANJI_RE.match(c)]
    return bool(ks) and any(not KANJI_RE.match(c) for c in surface[ks[0]:ks[-1] + 1])


def ruby_for(surface, reading, trim=True):
    """The kana to print for `surface`, with kana it already shows trimmed off
    the reading's ends.  The surface is compared in hiragana so katakana on
    the page (方向キー) trims like hiragana does; before that fix the キ leaked
    into the reading as 方向（ほうこうき）キー.  `trim=False` keeps the whole
    reading (a token with kana between its kanji prints it after the token)."""
    r = kata_to_hira(reading or "")
    if not r:
        return None
    if not trim:
        return r
    sf = kata_to_hira(surface)
    tail = 0
    while tail < len(sf) and tail < len(r) - 1 and sf[-1 - tail] == r[-1 - tail]:
        if KANJI_RE.match(sf[-1 - tail]):
            break
        tail += 1
    head = 0
    while head < len(sf) and head < len(r) - 1 and sf[head] == r[head]:
        if KANJI_RE.match(sf[head]):
            break
        head += 1
    core = r[head:len(r) - tail] if tail else r[head:]
    return core or r


def annotate(row, seen, stats):
    """One row of glyphs with `（reading）` inserted after each kanji word."""
    text = "".join(row).replace(UNKNOWN, "\u3002")
    if not KANJI_RE.search(text):
        return list(row)
    tok, mode = tokenizer()
    out = []
    for t in tok.tokenize(text, mode):
        surface = t.surface()
        out.extend(surface)
        if not KANJI_RE.search(surface):
            continue
        if seen is not None and surface in seen:
            stats["repeat"] += 1
            continue
        ruby = ruby_for(surface, t.reading_form())
        if not ruby or not HIRA_RE.fullmatch(ruby):
            stats["unread"] += 1
            continue
        if seen is not None:
            seen.add(surface)
        stats["words"] += 1
        stats["kana"] += len(ruby)
        out.append("\uff08")
        out.extend(ruby)
        out.append("\uff09")
    return out


def rows_needed(rows, width, reflow):
    if reflow:
        rows = [sum(rows, [])]
    return sum(max(1, -(-len(r) // width)) for r in rows)


def cmd_width(disc, dec, args):
    hist = collections.defaultdict(collections.Counter)
    for _path, _m, rows, term in pages(disc, dec):
        kind = {CONFIRM: "box (confirm)", 0x16: "box (timed)"}.get(term, "no break")
        for r in rows:
            hist[kind][len(r)] += 1
    print("# line lengths in glyphs -- %s" % disc.label)
    for kind in ("box (confirm)", "box (timed)", "no break"):
        c = hist[kind]
        print("  %-14s %6d lines, longest %2d, tail: %s"
              % (kind, sum(c.values()), max(c),
                 ", ".join("%d:%d" % (w, c[w]) for w in sorted(c) if w >= max(c) - 4)))
    print("\nThe box number is the width to plan against. Lines longer than that only")
    print("occur on pages with no break, which are the full-screen narration and the")
    print("choice menus, where the option list joins the prompt line.")
    return 0


def cmd_cost(disc, dec, args):
    allpages = [p for p in pages(disc, dec) if p[3] == CONFIRM]
    glyph_n = sum(len(r) for _p, _m, rows, _t in allpages for r in rows)
    unknown = sum(r.count(UNKNOWN) for _p, _m, rows, _t in allpages for r in rows)
    print("# %d confirm pages, %d glyphs, %d (%.2f%%) not in the character table"
          % (len(allpages), glyph_n, unknown, 100.0 * unknown / glyph_n))
    print("# box width %d glyphs\n" % args.width)
    for scope in ("every word", "first per page", "first per area"):
        stats = collections.Counter()
        for layout, reflow in (("authored breaks", False), ("reflow page", True)):
            matrix = collections.Counter()
            per_area, area = set(), None
            for path, _m, rows, _t in allpages:
                if path != area:
                    area, per_area = path, set()
                seen = {"every word": None, "first per page": set(),
                        "first per area": per_area}[scope]
                after = rows_needed([annotate(r, seen, stats) for r in rows],
                                    args.width, reflow)
                matrix[(len(rows), after)] += 1
            total = sum(matrix.values())
            over = sum(c for (_b, a), c in matrix.items() if a > 3)
            print("%-15s %-16s  over 3 rows: %5d of %d (%.1f%%)"
                  % (scope, layout, over, total, 100.0 * over / total))
            for b in sorted(set(b for b, _a in matrix)):
                per = {a: c for (bb, a), c in matrix.items() if bb == b}
                bad = sum(c for a, c in per.items() if a > 3)
                print("    %d-row shipped (%4d) -> %s   over 3: %d (%.1f%%)"
                      % (b, sum(per.values()),
                         ", ".join("%d:%d" % (a, per[a]) for a in sorted(per)),
                         bad, 100.0 * bad / sum(per.values())))
        print("   %d words annotated, %.2f kana each, %d had no usable reading, "
              "%d suppressed as repeats\n"
              % (stats["words"], stats["kana"] / max(1, stats["words"]),
                 stats["unread"], stats["repeat"]))
    return 0


def cmd_sample(disc, dec, args):
    want = set()
    for spec in args.pages:
        name, _, num = spec.partition(":")
        want.add((name.upper() if name.upper().endswith(".EMI") else name.upper() + ".EMI",
                  int(num)))
    for path, m, rows, term in pages(disc, dec):
        key = (os.path.basename(path).upper(), m)
        if key not in want or term != CONFIRM:
            continue
        want.discard(key)
        stats = collections.Counter()
        annotated = [annotate(r, None, stats) for r in rows]
        print("== %s msg%d -- %d rows shipped" % (key[0], m, len(rows)))
        for label, out in (("shipped", rows),
                           ("furigana, authored breaks", annotated),
                           ("furigana, page reflowed", [sum(annotated, [])])):
            print("  %s:" % label)
            for r in out:
                for k in range(0, max(1, len(r)), args.width):
                    print("    |%-*s|" % (args.width, "".join(r[k:k + args.width])))
    for key in sorted(want):
        print("not found as a confirm page: %s msg%d" % key)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["width", "cost", "sample"])
    ap.add_argument("pages", nargs="*", help="sample: AREA000:19 ...")
    ap.add_argument("--cue", default=default_cue(), help="legal .cue (default: game.toml [game].disc)")
    ap.add_argument("--bin-root", help="extracted BIN/ directory instead of the .cue")
    ap.add_argument("--width", type=int, default=15, help="box width in glyphs (default 15, measured)")
    args = ap.parse_args(argv)
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    dec = load_decoder()
    return {"width": cmd_width, "cost": cmd_cost, "sample": cmd_sample}[args.command](disc, dec, args)


if __name__ == "__main__":
    sys.exit(main())
