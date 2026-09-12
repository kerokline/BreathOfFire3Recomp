#!/usr/bin/env python
"""Which messages would collide with the furigana row rule (docs/FURIGANA.md)?

The furigana variant puts a shrink preset at the head of every message that
gets readings and draws each ruby row as an emphasis span, so the message's
size parameter P is spoken for. A message that carries its own span or preset
therefore collides -- but only if it has kanji, because a message without
kanji gets no readings, no ruby rows and no head preset, and is left verbatim.

    python tools/emphasis_census.py [--bin-root D:\\BoFIII\\BIN] [--examples N]

Counts distinct messages over the 200 area scripts plus the system block,
classifies every 0x0D..0x0E span and 0x0F preset, and lists the colliding
messages with their decoded text.
"""
import argparse
import collections
import io
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import page_rows
import text_tables

if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

SYSTEM_PATH, SYSTEM_DEST, SYSTEM_BASE = "BIN/ETC/AFLDKWA.EMI", 0x80014000, 8
KANJI_LEAD = {0x12, 0x13}


def system_messages(disc):
    data = disc.section(SYSTEM_PATH, SYSTEM_DEST).data
    first, = struct.unpack_from("<H", data, SYSTEM_BASE)
    seen = set()
    for m in range(first // 2):
        off, = struct.unpack_from("<H", data, SYSTEM_BASE + 2 * m)
        off += SYSTEM_BASE
        if off >= len(data):
            continue
        end = data.find(b"\x00", off)
        raw = data[off:end if end >= 0 else len(data)]
        if raw in seen:
            continue
        seen.add(raw)
        yield SYSTEM_PATH, "system", m, data, off


def classify(data, start, styles):
    """One message -> dict: kanji?, spans (with kanji-in-span), presets."""
    kanji = False
    spans, presets = [], []
    in_span = False
    span_kanji, span_len = False, 0
    prev = start
    for code, arg, nxt in page_rows.tokens(data, start):
        if code == "g":
            is_kanji = (nxt - prev == 2 and data[prev] in KANJI_LEAD)
            kanji |= is_kanji
            if in_span:
                span_len += 1
                span_kanji |= is_kanji
        elif code == 0x0D:
            in_span, span_kanji, span_len = True, False, 0
        elif code == 0x0E:
            spans.append((span_len, span_kanji))
            in_span = False
        elif code == 0x0F:
            kind, param, dur = styles[arg] if arg is not None and arg < len(styles) else (None, None, None)
            presets.append((arg, kind, param, dur))
        prev = nxt
    return {"kanji": kanji, "spans": spans, "presets": presets}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=text_tables.default_cue())
    ap.add_argument("--bin-root")
    ap.add_argument("--examples", type=int, default=40)
    a = ap.parse_args(argv)
    disc = text_tables.Disc(cue=a.cue, bin_root=a.bin_root)
    styles = page_rows.read_style_table(page_rows.EXE)
    decode = page_rows.load_decoder()

    total = with_kanji = 0
    styled = []           # (path, m, info, text)
    for path, index, m, data, off in list(page_rows.messages(disc)) + list(system_messages(disc)):
        info = classify(data, off, styles)
        total += 1
        with_kanji += info["kanji"]
        if info["spans"] or info["presets"]:
            end = data.find(b"\x00", off)
            styled.append((path, m, info, decode(bytes(data[off:end if end >= 0 else len(data)]))))

    print("distinct messages: %d, with kanji: %d" % (total, with_kanji))
    print("messages with a span or preset: %d" % len(styled))
    nk = [s for s in styled if not s[2]["kanji"]]
    coll = [s for s in styled if s[2]["kanji"]]
    print("  without kanji (left verbatim, no collision): %d" % len(nk))
    print("  with kanji (COLLIDE with the head preset):   %d" % len(coll))
    span_k = sum(1 for s in coll if any(k for _, k in s[2]["spans"]))
    print("    of which the span itself holds kanji:      %d" % span_k)

    kinds = collections.Counter()
    for s in styled:
        for arg, kind, param, dur in s[2]["presets"]:
            kinds[(page_rows.EFFECT.get(kind, "type %s" % kind), param, dur)] += 1
    print("\npreset uses (effect, P, frames): count")
    for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print("  %-16s %+4s %6s : %d" % (k[0], k[1], "forever" if k[2] == 0xFFFF else k[2], n))

    # Per page: a page is what is on screen, and every page after the first
    # is opened by its own replay, so a span on page 3 never meets the ruby
    # rows of page 1. Distinct by page bytes, which folds the suffix messages
    # (a cutscene entered at later lines) into one.
    pages = {}
    for path, index, m, data, off in list(page_rows.messages(disc)) + list(system_messages(disc)):
        end = data.find(b"\x00", off)
        raw = bytes(data[off:end if end >= 0 else len(data)])
        start = 0
        for code, arg, nxt in page_rows.tokens(raw, 0):
            if code in page_rows.PAGE_BREAK:
                pages.setdefault(raw[start:nxt - (2 if code == 0x16 else 1)], (path, m))
                start = nxt
        pages.setdefault(raw[start:], (path, m))
    page_styled = page_coll = page_span_kanji = 0
    unknown = collections.Counter()
    coll_pages = []
    for raw, (path, m) in pages.items():
        info = classify(raw + b"\x00", 0, styles)
        if not (info["spans"] or info["presets"]):
            continue
        page_styled += 1
        for arg, kind, _, _ in info["presets"]:
            if kind is None:
                unknown[arg] += 1
        if info["kanji"]:
            page_coll += 1
            page_span_kanji += any(k for _, k in info["spans"])
            coll_pages.append((path, m, info, decode(raw)))
    print("\nper distinct page: %d pages carry a span or preset; %d of them also hold kanji "
          "(the real collision set); in %d the span itself holds kanji" % (page_styled, page_coll, page_span_kanji))
    print("preset ids past the 26-entry table (arg: uses): %s" % dict(unknown))
    print("\ncolliding pages (%d):" % len(coll_pages))
    for path, m, info, text in coll_pages:
        eff = ", ".join("%s %+d/%s" % (page_rows.EFFECT.get(k, "type %s" % k), p, "inf" if d == 0xFFFF else d)
                        for _, k, p, d in info["presets"]) or "no preset"
        print("  %-12s msg %-4s %-28s %s" % (os.path.basename(path), m, eff, text.replace("<01>", " / ")))

    print("\ncolliding messages (%d shown):" % min(a.examples, len(coll)))
    for path, m, info, text in coll[:a.examples]:
        eff = ", ".join("%s %+d/%s" % (page_rows.EFFECT.get(k, "type %s" % k), p, "inf" if d == 0xFFFF else d)
                        for _, k, p, d in info["presets"]) or "no preset"
        print("  %-24s msg %-4s spans=%d  %s\n      %s" % (
            os.path.basename(path), m, len(info["spans"]), eff, text.replace("<01>", " / ")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
