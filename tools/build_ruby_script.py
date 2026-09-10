#!/usr/bin/env python
r"""build_ruby_script.py -- the Japanese (Ruby) script table, from the JP disc.

The third selectable script (docs/FURIGANA.md): the JP area dialogue with
the reading written inline after each kanji word, `漢字（かんじ）`, once per
word per area, re-flowed to the box.  It is delivered exactly like the
English table -- one more `generated/bof3_xlate_<code>.c` for the
`MsgBox_Reset` plugin (docs/LOCALIZATION_APPLY.md), selected by the
launcher's Localization dropdown as `jp_ruby`.

    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --review analysis/ruby_review.txt
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --selftest
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --scope every   # jp_ruby_all

## How a message is rebuilt

Every glyph keeps its **original bytes**: the message is walked into glyph
and control items, readings are inserted as new kana glyphs between them,
and the bytes are joined back.  Nothing is decoded and re-encoded, so a
message with no annotation and no re-flow comes back byte-identical --
`--selftest` proves that over the whole disc (the acceptance test
docs/FURIGANA.md asked for).  Readings come from SudachiPy (mode C) the same
way `tools/ruby_fit.py` costed them, with okurigana already on the page
trimmed off, and are emitted only if every kana has a glyph code.

Layout follows the FURIGANA.md rules: a word and its reading are one unit
that never splits across rows (unless it is wider than the box on its own),
closing punctuation clings to the unit before it, authored `0x01` breaks are
soft, rows are `--width` cells (16, the measured frame), and a page that
needs more than `--rows` rows is split with a `0x02` confirm break, not a
fourth row.  Controls -- speaker head, inserts, colour, sound, pause, spans,
flags, timed breaks and the whole `0x14` choice block -- pass through byte
for byte.  Only messages whose bytes actually change get a table entry; the
rest miss the lookup at runtime and render as shipped.
"""
import argparse
import collections
import os
import re
import struct
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from text_tables import Disc, default_cue                                  # noqa: E402
import page_rows                                                            # noqa: E402
from build_script_xlate import (message_extent, fnv1a64, emit_c, load_jp_tables,  # noqa: E402
                                decode_jp, ARG1, LEAD, CHOICE, NEWLINE, PAGE, TIMED, SPACE)
import ruby_fit                                                             # noqa: E402

KANJI_RE = re.compile(r"[\u4e00-\u9fff\u3005]")
HIRA_RE = re.compile(r"[\u3040-\u309f\u30fc]+")
# Characters that must not begin a row: they cling to the unit before them.
CLOSERS = set("」』）。、‥？！ー")
OPEN_BRACKET, CLOSE_BRACKET = 0x28, 0x29      # ( ) on the JP sheet
STRETCH = set("ーァィゥェォぁぃぅぇぉ")          # glued to a kanji: dialect stretching
READINGS_TOML = os.path.join(ROOT, "names", "readings.toml")
DICT_FOR_SCOPE = {"area": "core", "every": "full"}


def load_overrides(path=READINGS_TOML):
    """surface -> hiragana reading, from names/readings.toml ([[reading]]
    entries).  Consulted before SudachiPy; the auditable answer to the words
    the dictionary reads by convention rather than by context (私 -> ワタクシ)."""
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    out = {}                    # surface -> [(next_set | None, prev_tuple | None, reading)]
    for row in doc.get("reading", []):
        surface, reading = row["surface"], ruby_fit.kata_to_hira(row["reading"])
        if not HIRA_RE.fullmatch(reading):
            raise SystemExit("%s: reading for %s is not kana: %r" % (path, surface, row["reading"]))
        nxt = row.get("next")
        nxt = frozenset(nxt) if nxt is not None else None
        prv = row.get("prev")
        prv = tuple(prv) if prv is not None else None
        rules = out.setdefault(surface, [])
        if any((n, p) == (nxt, prv) for n, p, _ in rules):
            raise SystemExit("%s: %s listed twice for the same context" % (path, surface))
        rules.append((nxt, prv, reading))
    for rules in out.values():                      # context rules first, the default last
        rules.sort(key=lambda r: r[0] is None and r[1] is None)
    return out


def override_lookup(overrides, surface, next_surface, prev_text):
    """The sidecar reading for `surface` in context, or None: the first rule
    whose `next` list holds the following token and whose `prev` list holds
    a suffix of the text before the word (旅の方: `prev = ["旅の"]`), else the
    rule with neither."""
    for nxt, prv, reading in overrides.get(surface, ()):
        if nxt is not None and next_surface not in nxt:
            continue
        if prv is not None and not any(prev_text.endswith(p) for p in prv):
            continue
        return reading
    return None


def load_maps():
    """char -> bytes for what the annotator emits (kana), and the full decode."""
    import jptext
    kana_enc = {}
    for code, ch in jptext.KANA.items():
        kana_enc.setdefault(ch, bytes([code]))
    single, page15, _ = load_jp_tables()
    kanji_dec = dict(jptext.KANJI)
    return kana_enc, single, page15, kanji_dec


def parse(raw, single, page15, kanji_dec):
    """Split a JP message into (head, pages, tail); page items are
    ('g', bytes, char) glyphs, ('nl',) authored newlines, ('c', bytes)
    inline controls.  tail is the verbatim 0x14 block or b''."""
    i, n = 0, len(raw)
    head = b""
    if n >= 2 and raw[0] == 0x0C:
        head, i = raw[0:2], 2
    pages, items = [], []
    tail = b""
    while i < n:
        b = raw[i]
        if b == 0:
            break
        if b == CHOICE:
            tail = raw[i:]
            break
        if b == NEWLINE:
            items.append(("nl",)); i += 1
        elif b == PAGE:
            pages.append((items, b"\x02")); items = []; i += 1
        elif b == TIMED:
            pages.append((items, raw[i:i + 2])); items = []; i += 2
        elif b in ARG1:
            items.append(("c", raw[i:i + 2])); i += 2
        elif b < 0x12:
            items.append(("c", raw[i:i + 1])); i += 1
        elif b in LEAD:
            two = raw[i:i + 2]
            if b == 0x15:
                ch = page15.get(two[1], "\u3013")
            else:
                ch = kanji_dec.get(two.hex(), "\u3013")
            items.append(("g", two, ch)); i += 2
        else:
            ch = " " if b == SPACE else single.get(b) or ruby_fit.load_decoder().KANA.get(b, "\u3013")
            items.append(("g", raw[i:i + 1], ch)); i += 1
    if items or not pages:
        pages.append((items, b""))
    return head, pages, tail


class Annotator:
    def __init__(self, width, rows, annotate=True, reflow=True, dict_name="core",
                 overrides=None, ambiguous=None):
        self.kana_enc, self.single, self.page15, self.kanji_dec = load_maps()
        self.width, self.rows = width, rows
        self.do_annotate, self.do_reflow = annotate, reflow
        self.stats = collections.Counter()
        self.dict_name = dict_name
        self.tok, self.mode = ruby_fit.tokenizer(dict_name)
        self.overrides = overrides or {}
        self.override_hits = collections.Counter()
        # surface -> Counter(reading printed) over every annotated occurrence,
        # for the ambiguity report (None = not collecting)
        self.ambiguous = ambiguous
        self._lexicon_readings = {}

    def lexicon_readings(self, surface):
        """Distinct readings the dictionary holds for this exact surface."""
        if surface not in self._lexicon_readings:
            seen = []
            for m in ruby_fit.sudachi_dictionary(self.dict_name).lookup(surface):
                r = ruby_fit.kata_to_hira(m.reading_form())
                if r not in seen:
                    seen.append(r)
            self._lexicon_readings[surface] = seen
        return self._lexicon_readings[surface]

    # -- readings -------------------------------------------------------------
    def override_for(self, surface, token, next_surface="", prev_text=""):
        """The sidecar reading for this token, or None.  An entry keys on the
        exact surface, or on the token's dictionary form: `言う = いう` then
        also reads 言っ / 言わ / 言え, by swapping the dictionary form's kana
        tail for the conjugated surface's (来る = くる gives 来 -> く, not き:
        list the irregular surfaces themselves).  An entry with `next` applies
        only when the following token is listed (何 + を = なに)."""
        r = override_lookup(self.overrides, surface, next_surface, prev_text)
        if r is not None:
            return r
        base = token.dictionary_form()
        r = override_lookup(self.overrides, base, next_surface, prev_text)
        if r is None or base == surface:
            return r
        cut = max((k for k, c in enumerate(base) if KANJI_RE.match(c)), default=-1) + 1
        scut = max((k for k, c in enumerate(surface) if KANJI_RE.match(c)), default=-1) + 1
        if not cut or base[:cut] != surface[:scut]:
            return None                             # different stem: not this word
        base_tail = base[cut:]
        if base_tail and not r.endswith(base_tail):
            return None                             # the override's kana do not end like the word
        stem = r[:len(r) - len(base_tail)] if base_tail else r
        return stem + surface[scut:]

    # Tokens that hang off the word before them: a row never opens on one.
    ATTACH_POS = ("助詞", "助動詞", "接尾辞")

    def annotate_run(self, run, seen):
        """run: list of glyph items.  Returns a list of units, each a list of
        items.  A unit is one Sudachi token -- a kanji word carries its
        reading -- with particles, auxiliaries and suffixes attached to the
        word before them, so the re-flow breaks rows between phrases
        (つぎは / やっつけて くれるんじゃ), never inside a word."""
        if not self.do_annotate:
            return [[it] for it in run]
        # A long-vowel mark or small kana glued to a kanji (気ィ, 設備ーい,
        # 起動ーう: dialect stretching) is not in any lexicon and breaks the
        # token boundary (設 + 備ーい).  Tokenize with it stripped and hand the
        # glyphs back to the token they followed, after the reading.
        chars = [it[2] for it in run]
        keep = []                                   # run indices the tokenizer sees
        for k, c in enumerate(chars):
            stretched = k and c in STRETCH and (KANJI_RE.match(chars[k - 1]) or (k - 1) not in keep)
            if not stretched:
                keep.append(k)
        text = "".join(chars[k] for k in keep)
        units, attach, pos = [], [], 0
        tokens = list(self.tok.tokenize(text, self.mode))
        for ti, t in enumerate(tokens):
            surface = t.surface()
            next_surface = tokens[ti + 1].surface() if ti + 1 < len(tokens) else ""
            prev_text = text[:pos]
            span = keep[pos:pos + len(surface)]
            pos += len(surface)
            if not span:                            # Sudachi can emit an empty token
                continue
            end = span[-1] + 1                      # then the stripped glyphs that followed
            stop = keep[pos] if pos < len(keep) else len(run)
            word = [run[k] for k in span] + run[end:stop]
            attach.append(t.part_of_speech()[0] in self.ATTACH_POS)
            if not KANJI_RE.search(surface):
                units.append(word)
                continue
            if surface in seen:
                self.stats["repeat"] += 1
                units.append(word)
                continue
            # A token with kana between its kanji (最後の夜, 会いに行こう) is one
            # concept: its whole reading follows the whole token.  Otherwise the
            # reading follows the kanji stem with the page's own kana trimmed.
            whole = ruby_fit.inner_kana(surface)
            reading = self.override_for(surface, t, next_surface, prev_text)
            if reading is not None:
                self.override_hits[surface] += 1
            else:
                reading = t.reading_form()
            ruby = ruby_fit.ruby_for(surface, reading, trim=not whole)
            if self.ambiguous is not None:
                self.ambiguous.setdefault(surface, collections.Counter())[ruby] += 1
            if not ruby or not HIRA_RE.fullmatch(ruby):
                self.stats["unread"] += 1
                units.append(word)
                continue
            enc = [self.kana_enc.get(c) for c in ruby]
            if any(e is None for e in enc):
                self.stats["unencodable"] += 1
                units.append(word)
                continue
            seen.add(surface)
            self.stats["words"] += 1
            self.stats["kana"] += len(ruby)
            # The reading follows the kanji stem: `\u8d77(\u304a)\u304d\u308b`, not `\u8d77\u304d\u308b(\u304a)`.
            # Head kana (rare, e.g. \u304a\u5ba2\u69d8) stay in front of it.
            last_kanji = len(surface) - 1 if whole else \
                max(k for k, c in enumerate(surface) if KANJI_RE.match(c))
            unit = list(word[:last_kanji + 1])
            unit.append(("g", bytes([OPEN_BRACKET]), "\uff08"))
            unit.extend(("g", e, c) for e, c in zip(enc, ruby))
            unit.append(("g", bytes([CLOSE_BRACKET]), "\uff09"))
            unit.extend(word[last_kanji + 1:])
            units.append(unit)
        merged = []
        for u, hang in zip(units, attach):
            prev = merged[-1] if merged else None
            if hang and prev and not (len(prev) == 1 and prev[0][2] == " "):
                merged[-1] = prev + u
            else:
                merged.append(u)
        done = keep[pos - 1] + 1 if pos else 0
        merged.extend([it] for it in run[done:])
        return merged

    # -- layout ---------------------------------------------------------------
    def units_for_page(self, items, seen):
        """Items -> units in order; controls ride as zero-width units and
        closing punctuation merges into the previous unit."""
        units, run = [], []

        def flush():
            if run:
                units.extend(self.annotate_run(run, seen))
                run.clear()

        for it in items:
            if it[0] == "g":
                run.append(it)
            elif it[0] == "nl":
                flush()
                if not self.do_reflow:
                    units.append([("nl",)])
            else:
                flush()
                units.append([it])
        flush()
        merged = []
        for u in units:
            first = u[0]
            if merged and first[0] == "g" and first[2] in CLOSERS and merged[-1][0][0] == "g":
                merged[-1] = merged[-1] + u
            else:
                merged.append(u)
        return merged

    @staticmethod
    def cells(unit):
        return sum(1 for it in unit if it[0] == "g")

    def rows_for(self, units):
        rows, row, used = [], [], 0
        for u in units:
            if u[0][0] == "nl":                         # authored break kept (no reflow)
                rows.append(row); row, used = [], 0
                continue
            w = self.cells(u)
            if w == 0:
                row.append(u); continue
            if used and used + w > self.width:
                rows.append(row); row, used = [], 0
                if u[0][0] == "g" and u[0][2] == " ":  # never open a row with a space
                    u = u[1:]
                    w -= 1
                    if not u:
                        continue
            if w > self.width:                          # wider than the box: split by glyph
                for it in u:
                    c = 1 if it[0] == "g" else 0
                    if used + c > self.width:
                        rows.append(row); row, used = [], 0
                    row.append([it]); used += c
                continue
            row.append(u); used += w
        if row or not rows:
            rows.append(row)
        return rows

    @staticmethod
    def row_bytes(row):
        return b"".join(it[1] for u in row for it in u if it[0] in ("g", "c"))

    def is_box_page(self, items):
        """The talk box holds up to self.rows rows of self.width cells. A page
        authored wider or taller than that is the full-screen narration path
        (docs/TEXT_ENGINE.md "Rows per page"), which is left exactly as shipped:
        no readings, no re-flow, no split."""
        rows, cur = 1, 0
        for it in items:
            if it[0] == "nl":
                rows += 1; cur = 0
            elif it[0] == "g":
                cur += 1
                if cur > self.width:
                    return False
        return rows <= self.rows

    @staticmethod
    def verbatim(items):
        return b"".join(it[1] if it[0] in ("g", "c") else bytes([NEWLINE]) for it in items)

    def encode(self, parsed, seen):
        head, pages, tail = parsed
        out = bytearray(head)
        for items, term in pages:
            if not self.is_box_page(items):
                self.stats["narration_pages"] += 1
                out += self.verbatim(items) + term
                continue
            rows = self.rows_for(self.units_for_page(items, seen))
            if len(rows) > self.rows:
                self.stats["split_pages"] += 1
            for r0 in range(0, len(rows), self.rows):
                chunk = rows[r0:r0 + self.rows]
                for ri, row in enumerate(chunk):
                    if ri:
                        out.append(NEWLINE)
                    out += self.row_bytes(row)
                if r0 + self.rows < len(rows):
                    out.append(PAGE)
            out += term
        if tail:
            out += tail
        else:
            out.append(0)
        return bytes(out)


def write_ambiguous(path, ann, overrides):
    """The audit list: every annotated surface the lexicon reads more than one
    way, most frequent first, with the candidates and what was printed.  The
    printed reading is after the trim (良い -> い); the candidates are whole."""
    rows = []
    for surface, used in ann.ambiguous.items():
        cands = ann.lexicon_readings(surface)
        if len(cands) < 2 and surface not in overrides:
            continue
        rows.append((sum(used.values()), surface, cands, used))
    rows.sort(key=lambda r: (-r[0], r[1]))
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Ambiguous readings -- %d surfaces the %s lexicon reads more than one way\n"
                "# (annotated occurrences, surface, candidates | printed reading x count | override)\n"
                "# Choose in names/readings.toml: [[reading]] surface = \"...\" reading = \"...\"\n"
                "# Surface-only overrides cannot separate context readings (何 = なに / なん).\n\n"
                % (len(rows), ann.dict_name))
        for n, surface, cands, used in rows:
            printed = " ".join("%s x%d" % (r, c) for r, c in used.most_common())
            ov = "  override=%s" % " ".join(
                "%s%s%s" % (r, "" if n is None else "(before %s)" % "/".join(sorted(n)),
                            "" if p is None else "(after %s)" % "/".join(p))
                for n, p, r in overrides[surface]) if surface in overrides else ""
            f.write("%6d  %s\t%s\t| %s%s\n" % (n, surface, " / ".join(cands), printed, ov))
    print("ambiguity list: %d surfaces -> %s" % (len(rows), path))


class _NeverSeen(set):
    """A `seen` set that forgets: every occurrence gets its reading."""
    def add(self, item):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=default_cue(), help="JP disc .cue")
    ap.add_argument("--bin-root", help="extracted JP BIN/ tree instead of the .cue")
    ap.add_argument("--width", type=int, default=16, help="box width in cells (16 measured)")
    ap.add_argument("--rows", type=int, default=3, help="rows per page before a split")
    ap.add_argument("--scope", choices=["area", "every"], default="area",
                    help="annotate a word on its first occurrence per area (jp_ruby, default) "
                         "or every occurrence (jp_ruby_all)")
    ap.add_argument("--out", help="default generated/bof3_xlate_<code>.c for the scope's code")
    ap.add_argument("--review", help="write a shipped / ruby side-by-side text file here")
    ap.add_argument("--selftest", action="store_true",
                    help="no annotation, no reflow: every message must come back byte-identical")
    ap.add_argument("--max-len", type=int, default=2040)
    ap.add_argument("--dict", choices=["core", "full"],
                    help="SudachiPy dictionary; default core for --scope area, full for "
                         "--scope every (full merges compounds: 武器屋 as one word)")
    ap.add_argument("--ambiguous", help="write the audit list of annotated words whose surface "
                         "has more than one lexicon reading (candidates, the reading used, count)")
    args = ap.parse_args(argv)
    if not args.dict:
        args.dict = DICT_FOR_SCOPE[args.scope]

    code = {"area": "jp_ruby", "every": "jp_ruby_all"}[args.scope]
    if not args.out:
        args.out = os.path.join(ROOT, "generated", "bof3_xlate_%s.c" % code)
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    overrides = load_overrides()
    ann = Annotator(args.width, args.rows, annotate=not args.selftest, reflow=not args.selftest,
                    dict_name=args.dict, overrides=overrides,
                    ambiguous={} if args.ambiguous else None)
    review = open(args.review, "w", encoding="utf-8") if args.review else None
    entries, seen_hash = [], set()
    stats = collections.Counter()
    longest = (0, None)

    for path in page_rows.area_paths(disc):
        data = disc.section(path, 0x80010000).data
        n = struct.unpack_from("<H", data, 0)[0] // 2
        seen_words = set()                       # first occurrence per area
        for m in range(n):
            off = struct.unpack_from("<H", data, 2 * m)[0]
            ln = message_extent(data, off)
            stats["slots"] += 1
            if not ln:
                stats["empty"] += 1
                continue
            raw = data[off:off + ln]
            h = fnv1a64(raw)
            if h in seen_hash:
                stats["duplicate"] += 1
                continue
            seen_hash.add(h)
            parsed = parse(raw, ann.single, ann.page15, ann.kanji_dec)
            if args.scope == "every":
                seen_words = _NeverSeen()
            enc = ann.encode(parsed, seen_words)
            if args.selftest:
                if enc != raw:
                    print("ROUND-TRIP MISMATCH %s slot %d\n  %s\n  %s" % (path, m, raw.hex(), enc.hex()))
                    stats["mismatch"] += 1
                continue
            if enc == raw:
                stats["unchanged"] += 1
                continue
            if len(enc) > args.max_len:
                stats["too_long"] += 1
                continue
            entries.append((h, enc))
            if len(enc) > longest[0]:
                longest = (len(enc), "%s slot %d" % (path, m))
            if review:
                review.write("== %s slot %d  jp %d B  ruby %d B  %016x\n" % (path, m, ln, len(enc), h))
                review.write("JP    " + decode_jp(raw, ann.single, ann.page15) + "\n")
                review.write("RUBY  " + decode_jp(enc, ann.single, ann.page15) + "\n\n")
    if review:
        review.close()
    if args.ambiguous:
        write_ambiguous(args.ambiguous, ann, overrides)

    if args.selftest:
        print("selftest: %d slots, %d distinct messages checked, %d mismatches"
              % (stats["slots"], stats["slots"] - stats["empty"] - stats["duplicate"], stats["mismatch"]))
        return 1 if stats["mismatch"] else 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    blob = emit_c(args.out, entries, code=code, tool="tools/build_ruby_script.py",
                  what="Japanese (Ruby, %s) area-script table"
                  % ("first occurrence per area" if args.scope == "area" else "every occurrence"))
    print("wrote %s: %d entries, %d blob bytes" % (args.out, len(entries), blob))
    print("slots %d, empty %d, duplicate %d, unchanged (no kanji, fits) %d, too long %d"
          % (stats["slots"], stats["empty"], stats["duplicate"], stats["unchanged"], stats["too_long"]))
    print("annotated %d words (%.2f kana each), %d repeats suppressed, %d without a usable "
          "reading, %d with a kana the sheet cannot encode; dictionary %s, %d overrides "
          "applied to %d words (%d listed)"
          % (ann.stats["words"], ann.stats["kana"] / max(1, ann.stats["words"]),
             ann.stats["repeat"], ann.stats["unread"], ann.stats["unencodable"],
             args.dict, sum(ann.override_hits.values()), len(ann.override_hits), len(overrides)))
    print("pages split for exceeding %d rows at width %d: %d; narration pages left verbatim: %d"
          % (args.rows, args.width, ann.stats["split_pages"], ann.stats["narration_pages"]))
    print("longest encoded message: %d bytes (%s); slot cap %d" % (longest + (args.max_len,)))
    top = sorted(((len(e), h) for h, e in entries), reverse=True)[:5]
    print("five longest: %s" % ", ".join("%d" % n for n, _ in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
