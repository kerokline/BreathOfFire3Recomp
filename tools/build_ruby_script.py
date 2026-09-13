#!/usr/bin/env python
r"""build_ruby_script.py -- the Japanese (Furigana) script table, from the JP disc.

The third selectable script (docs/FURIGANA.md): the JP area dialogue with
every kanji word's reading in an 8 px row above it, authored line breaks
kept, two text rows per page.  It is delivered exactly like the English
table -- one more `generated/bof3_xlate_<code>.c` for the `MsgBox_Reset`
plugin (docs/LOCALIZATION_APPLY.md), selected by the launcher's
Localization dropdown as `jp_furigana`; the plugin's row rule and 8 px
font hooks do the drawing.

    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --review analysis/furigana_review.txt
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --selftest
    python tools/build_ruby_script.py --bin-root D:\BoFIII\BIN --inline --scope area   # retired jp_ruby

Retired 2026-09-12 (still buildable, not in game.toml's language list): the
inline-bracket layout `漢字（かんじ）` with re-flowed pages (`--inline`,
jp_ruby / jp_ruby_all) and the first-occurrence-per-area scope (`--scope
area`), which only ever saved width the furigana rows do not spend.

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
                                decode_jp, ARG1, LEAD, CHOICE, NEWLINE, PAGE, TIMED, SPACE,
                                INSERT_WIDTH)
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
                 overrides=None, ambiguous=None, insert_width=None, furigana=False,
                 rows_out=2):
        self.kana_enc, self.single, self.page15, self.kanji_dec = load_maps()
        self.width, self.rows = width, rows
        # Furigana layout (docs/FURIGANA.md "The rendering route, reopened"):
        # readings go into a half-height ruby row above each text row instead
        # of brackets inline, authored breaks are kept, and a page with
        # readings holds `rows_out` text rows (two pairs fit the 42 px box).
        self.furigana, self.rows_out = furigana, rows_out
        self.lint = None                   # list of (text row, ruby row, [(reading, want, drawn)]) or None
        self.last_placements = []
        # Cells budgeted for each runtime insert when a row is laid out.  The
        # English encoder's numbers, with the Ruby scopes raising 0x07 to a
        # whole row: an annotated item / skill name reaches 16 cells
        # (docs/INSERT_RUBY.md), and the record is re-authored at runtime by
        # the same plugin, so the message must leave the room.
        self.insert_width = dict(INSERT_WIDTH)
        self.insert_width.update(insert_width or {})
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
            if self.furigana:
                # A zero-width marker after the stem: the reading bytes and
                # the stem's width in cells (the whole token when kana sit
                # between its kanji), for the ruby row above this text row.
                first_kanji = 0 if whole else \
                    min(k for k, c in enumerate(surface) if KANJI_RE.match(c))
                unit.append(("ruby", b"".join(enc), last_kanji + 1 - first_kanji))
            else:
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

    def item_cells(self, it, budget=None):
        """Width of one item: a glyph is one cell; a runtime insert (0x03 /
        0x04 / 0x07 / 0x08: character, item, skill, message) is budgeted at
        the widest name it can print, as the English encoder does -- a zero
        here laid <0701> を教（おし）えてもらった！ out 19 cells wide.
        `budget` overrides the per-annotator table (is_box_page measures the
        shipped layout with the shipped widths)."""
        if it[0] == "g":
            return 1
        if it[0] == "c":
            return (budget or self.insert_width).get(it[1][0], 0)
        return 0

    def cells(self, unit):
        return sum(self.item_cells(it) for it in unit)

    # -- runtime inserts (docs/INSERT_RUBY.md) --------------------------------
    def annotate_name(self, nb):
        """One 0x07 record: the name bytes the game copies from an item /
        ability table (up to the first NUL), annotated the way a message word
        is, every kanji word read.  Returns the new bytes, or None when the
        name has nothing to read, would not fit the row (self.width cells),
        or would overflow the 32-byte record (31 bytes + NUL)."""
        nb = nb.split(b"\0", 1)[0]
        if not nb:
            return None
        _, pages, _ = parse(nb, self.single, self.page15, self.kanji_dec)
        items = pages[0][0] if pages else []
        units = self.units_for_page(items, _NeverSeen())
        out = b"".join(self.row_bytes([u]) for u in units)
        if out == nb:
            return None
        if self.cells(sum(units, [])) > self.width or len(out) > 31:
            self.stats["insert_too_wide"] += 1
            return None
        return out

    def rows_for(self, units):
        rows, row, used = [], [], 0
        if not self.do_reflow:
            # Authored rows only: never wrap, whatever an insert is budgeted at
            # (the budget wrapped 87 shipped rows in --selftest, and would
            # break authored rows in the furigana layout, 2026-09-12).
            for u in units:
                if u[0][0] == "nl":
                    rows.append(row); row = []
                else:
                    row.append(u)
            rows.append(row)
            return rows
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
                    c = self.item_cells(it)
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
        no readings, no re-flow, no split.  Inserts count at the SHIPPED
        widths here (INSERT_WIDTH), not the Ruby budget: a 16-cell 0x07
        would push every authored row holding an item name past the frame
        and misfile the message as narration (2026-09-10, caught on the
        pickup line by the synthetic insert test)."""
        rows, cur = 1, 0
        for it in items:
            if it[0] == "nl":
                rows += 1; cur = 0
            elif it[0] in ("g", "c"):
                cur += self.item_cells(it, INSERT_WIDTH)
                if cur > self.width:
                    return False
        return rows <= self.rows

    @staticmethod
    def verbatim(items):
        return b"".join(it[1] if it[0] in ("g", "c") else bytes([NEWLINE]) for it in items)

    # -- furigana rows (docs/FURIGANA.md step 3) ------------------------------
    FURIGANA_HEAD = b"\x0f\x13"        # shrink -6 forever: the page signature the plugin keys on
    RESET_HEAD = b"\x0f\x02"           # reset to 12 px forever, ahead of a page with its own effect
    GAP = 0x09                         # renderer no-op, stepper does not count it: a half-cell gap
    INSERT_MARK = 0x11                 # never reaches the engine: the plugin expands it at open
    SPAN_OPEN, SPAN_CLOSE, PRESET = 0x0D, 0x0E, 0x0F
    INSERTS = (0x03, 0x04, 0x07, 0x08)
    HANGING = (0x2A, 0x3B)             # drawn one cell left of the origin at a row start

    @staticmethod
    def has_effect(items):
        return any(it[0] == "c" and it[1][0] in (Annotator.SPAN_OPEN, Annotator.SPAN_CLOSE,
                                                 Annotator.PRESET) for it in items)

    RUBY_PX = 8                        # a reading glyph is drawn 8 px wide (the 8 x 8 font)
    HALF_PX = 6                        # one gap byte / one half-cell

    def ruby_row_for(self, row, limit=None):
        """The half-cell ruby row above one text row, as bytes (b'' when the
        row has no reading). A reading starts at 2 x its stem's first cell;
        one wider than its stem takes a free half-cell on the left first,
        and one that would overlap an earlier reading moves right. Glyphs
        are 8 px wide on a 6 px half-cell grid, so a reading of n kana
        occupies ceil(8n / 6) half-cells and its kana are emitted back to
        back (the plugin advances 8 px per kana). A reading past a runtime
        insert is dropped: the insert's width is only known at draw time."""
        half = [None] * (2 * self.width)
        markers = []                       # (half-cell, ) where a runtime insert begins
        placements = []                    # (half-cell, kana count, stem cell) per reading, for the lint
        self.last_placements = placements
        x, first = 0, True
        for u in row:
            for it in u:
                if it[0] == "g":
                    if first and it[1][0] in self.HANGING:
                        x -= 1
                    first = False
                    x += 1
                elif it[0] == "c":
                    if it[1][0] in self.INSERTS:
                        # A runtime insert: its width is only known at draw
                        # time, so the ruby row carries INSERT_MARK where it
                        # begins and is laid out as if it were zero width;
                        # the plugin expands the marker into the inserted
                        # name's own ruby fragment, or into gaps of its
                        # real width, when the message opens.
                        markers.append(2 * max(x, 0))
                        self.stats["ruby_insert_markers"] += 1
                    else:
                        x += self.item_cells(it)
                elif it[0] == "ruby":
                    kana, stem = it[1], it[2]
                    px = self.RUBY_PX * len(kana)
                    w = -(-px // self.HALF_PX)                      # half-cells the ink covers
                    # Half-cells the cursor consumes: the renderer advances 6
                    # after the last kana, the plugin 8 between kana, so a
                    # reading ends 8n - 2 past its start; the plugin snaps
                    # that up to the next half-cell before counting gaps, and
                    # the builder must count gaps from the same place.
                    c = -(-(px - (self.RUBY_PX - self.HALF_PX)) // self.HALF_PX)
                    s = 2 * (x - stem)
                    # A reading wider than its stem hangs right, aligned with
                    # the stem's left edge; only past half a cell of overhang
                    # does it take a free half-cell on the left as well (まえ
                    # over 前 stays on 前; さばく over 砂 straddles it).
                    if px - 12 * stem > self.HALF_PX and s > 0 and half[s - 1] is None:
                        s -= 1
                    # In a fragment (an inserted name) the cursor must end
                    # exactly at the name's width, or every reading after the
                    # insert starts late by the overrun: a reading that would
                    # run past `limit` moves left while there is room.
                    while limit and s + c > limit and s > 0 and half[s - 1] is None:
                        s -= 1
                    s = max(s, 0)
                    # Move right past any earlier reading's cells -- and never
                    # start directly after one's consumed cells (True): the
                    # plugin tells readings apart only by a gap byte between
                    # them, and without one the second reading continued the
                    # first at the kana pitch (村の連中に: れんちゅう drawn
                    # against むら, 2026-09-12).
                    while s + w <= len(half) and (any(h is not None for h in half[s:s + w])
                                                  or (s > 0 and half[s - 1] is True)):
                        s += 1
                    if s + w > len(half):
                        # Against the right wall: only if that leaves the
                        # boundary gap (the clamp put しゅうりょう straight after
                        # ちょうせい's consumed cells on 調整終了 -- the one row
                        # the lint caught).
                        s = len(half) - w
                        if s < 0 or any(h is not None for h in half[s:]) or (s > 0 and half[s - 1] is True):
                            self.stats["ruby_no_room"] += 1
                            continue
                    # The kana go back to back from half-cell s. Cells up to
                    # c are what the cursor consumes and emit nothing; cells
                    # from c to w are covered by ink but not by the cursor,
                    # so they are reserved against a later reading (False)
                    # yet still emit a gap byte.
                    for k in range(w):
                        half[s + k] = kana[k:k + 1] if k < len(kana) else (True if k < c else False)
                    self.stats["ruby_placed"] += 1
                    placements.append((s, len(kana), x - stem))
        while half and half[-1] in (None, False):
            half.pop()
        out = bytearray()
        for i, h in enumerate(half + [None] * (max(markers) + 1 - len(half) if markers else 0)):
            out += bytes([self.INSERT_MARK]) * markers.count(i)
            if i < len(half):
                out += h if isinstance(h, bytes) else (b"" if h is True else bytes([self.GAP]))
        while out and out[-1] == self.GAP:
            out.pop()
        return bytes(out)

    def ruby_fragment(self, nb):
        """The ruby-row fragment for one inserted name (docs/FURIGANA.md
        "Inserts"): the name's readings laid out as a row of their own,
        padded with gaps so the cursor ends exactly at the name's width
        (2 half-cells per cell), or None when the name has nothing to read."""
        nb = nb.split(b"\0", 1)[0]
        if not nb:
            return None
        _, pages, _ = parse(nb, self.single, self.page15, self.kanji_dec)
        items = pages[0][0] if pages else []
        units = self.units_for_page(items, _NeverSeen())
        cells = sum(self.cells(u) for u in units)
        frag = bytearray(self.ruby_row_for(units, limit=2 * cells))
        if not any(b != self.GAP for b in frag):
            return None
        # Cursor model: kana consume 8 px each less 2 at the end of a run,
        # gaps 6; pad to the name's width. A run overhanging the name (やくそう
        # over 薬草: 32 px on 24) cannot be padded away here; the plugin
        # measures the same cursor over the fragment at open time and drops
        # one gap byte after the marker per half-cell of overrun
        # (expand_markers, 2026-09-13 -- readings after 薬草 sat 6 px right).
        consumed, run = 0, 0
        for b in frag:
            if b == self.GAP:
                if run:
                    consumed += -(-(self.RUBY_PX * run - 2) // self.HALF_PX) * self.HALF_PX
                    run = 0
                consumed += self.HALF_PX
            else:
                run += 1
        if run:
            consumed += -(-(self.RUBY_PX * run - 2) // self.HALF_PX) * self.HALF_PX
        while consumed < 12 * cells:
            frag.append(self.GAP)
            consumed += self.HALF_PX
        return bytes(frag)

    def lint_row(self, ruby, placements):
        """Simulate the plugin's draw-time cursor over one ruby row and check
        that every reading's first kana lands where the builder put it
        (6 px per half-cell). The plugin's rules: a gap byte is 6 px; a
        kana right after gaps starts at the cursor snapped up to the next
        half-cell plus the gaps; a kana right after another kana is drawn
        8 px after it (the renderer advances 6, the plugin adds 2); the
        renderer advances 6 after the last kana of a run. Rows with an
        insert marker are skipped (the insert's width is a draw-time
        value). Returns a list of (reading index, wanted x, drawn x)."""
        if self.INSERT_MARK in ruby:
            self.stats["lint_skipped_insert_rows"] += 1
            return []
        x, gaps, prev_kana, drawn = 0, 0, False, []
        for b in ruby:
            if b == self.GAP:
                gaps += 1
                prev_kana = False
                continue
            if gaps:
                x = -(-x // self.HALF_PX) * self.HALF_PX + self.HALF_PX * gaps
                gaps = 0
            elif prev_kana:
                x += self.RUBY_PX - self.HALF_PX
            drawn.append(x)
            x += self.HALF_PX                      # the renderer's own advance
            prev_kana = True
        bad, i = [], 0
        for k, (s, n, stem_cell) in enumerate(placements):
            if i >= len(drawn):
                break
            want = self.HALF_PX * s
            if drawn[i] != want:
                bad.append((k, want, drawn[i]))
            if abs(want - 12 * stem_cell) > self.HALF_PX:
                self.stats["lint_off_stem"] += 1
            i += n
        self.stats["lint_rows"] += 1
        if bad:
            self.stats["lint_bad_rows"] += 1
        return bad

    def encode_furigana_page(self, items, term, seen, out):
        """One box page in the furigana layout, appended to `out`."""
        if self.do_annotate and self.has_effect(items):
            # Keep the shout, drop this page's readings (decision 2026-09-12):
            # verbatim, behind a reset so a shrink left over from an earlier
            # page does not draw the shout small.
            self.stats["effect_pages"] += 1
            out += self.RESET_HEAD + self.verbatim(items) + term
            return
        rows = self.rows_for(self.units_for_page(items, seen))
        text = [self.row_bytes(r) for r in rows]
        ruby = []
        for r in rows:
            rb = self.ruby_row_for(r)
            ruby.append(rb)
            if self.lint is not None and rb:
                bad = self.lint_row(rb, self.last_placements)
                if bad:
                    self.lint.append((decode_jp(self.row_bytes(r), self.single, self.page15),
                                      decode_jp(rb, self.single, self.page15), bad))
        if not any(ruby):
            out += bytes([NEWLINE]).join(text) + term
            return
        self.stats["furigana_pages"] += 1
        if len(rows) > self.rows_out:
            self.stats["split_pages"] += 1
        # Ruby row first, then its text row, so the page ends on a text row:
        # the next-page arrow places itself off the last row (2026-09-12).
        for r0 in range(0, len(rows), self.rows_out):
            out += self.FURIGANA_HEAD
            for ri in range(r0, min(r0 + self.rows_out, len(rows))):
                if ri > r0:
                    out.append(NEWLINE)
                out += bytes([self.SPAN_OPEN]) + ruby[ri] + bytes([self.SPAN_CLOSE, NEWLINE]) + text[ri]
            out += bytes([PAGE]) if r0 + self.rows_out < len(rows) else term

    def encode(self, parsed, seen):
        head, pages, tail = parsed
        out = bytearray(head)
        for items, term in pages:
            if not self.is_box_page(items):
                self.stats["narration_pages"] += 1
                out += self.verbatim(items) + term
                continue
            if self.furigana:
                self.encode_furigana_page(items, term, seen, out)
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


# The system message block: BIN/ETC/AFLDKWA.EMI's one section (also carried
# inside FIRST.EMI), dest 0x80014000, an 8-byte header and then the same u16
# offset table as an area script, 309 slots.  Most of it is menu, shop and
# memory-card text, but the whole block goes in: the box has one door for
# system text (Msg_OpenSystem -> MsgBox_Reset, 64 call sites, where the
# plugin hooks), while menus / shops / battle read the block through
# Msg_SystemPtr (1,879 sites) and never pass the hook.  So a slot the box
# draws always matches and a slot a menu draws never does, whichever overlay
# asked -- including the ids the area scripts pass through Script_ShowMessage
# with bit 0x2000, which no static scan can enumerate.
SYSTEM_BLOCK = ("BIN/ETC/AFLDKWA.EMI", 0x80014000, 8, None)   # None = every slot


def message_blocks(disc):
    """(path, section bytes, table base, slot indices) for every message
    block the tables cover: the 200 area scripts, then the field slots of
    the system block."""
    for path in page_rows.area_paths(disc):
        data = disc.section(path, 0x80010000).data
        yield path, data, 0, range(struct.unpack_from("<H", data, 0)[0] // 2)
    path, dest, base, slots = SYSTEM_BLOCK
    data = disc.section(path, dest).data
    n = struct.unpack_from("<H", data, base)[0] // 2
    yield path, data, base, range(n) if slots is None else [m for m in slots if m < n]


class _NeverSeen(set):
    """A `seen` set that forgets: every occurrence gets its reading."""
    def add(self, item):
        pass


def insert_entries(disc, ann, review=None, fragment=False):
    """The runtime-insert table (docs/INSERT_RUBY.md): FNV-1a64 of the name
    bytes a 0x07 record holds -> the same name with readings.  The bytes the
    game copies into the record are the item tables' and the ability table's
    name[8] fields (GAME.EMI, tools/text_tables.py), NUL-terminated at 8 by
    the pickup code, so the hash is over the raw table bytes up to the first
    NUL -- exactly what the plugin reads back from 0x801490D4 + 0x20 * n."""
    import text_tables
    sec = disc.section(*text_tables.GAME)
    names = []
    for t in text_tables.ITEM_TABLES:
        for r in text_tables.scan_records(sec, t["start"], t["stride"], t["end"], t["name"], t["fields"]):
            names.append((t["category"], r["id"], sec.at(r["ram"] + t["name"][0], t["name"][1])))
    a = text_tables.ABILITY_TABLE
    for r in text_tables.scan_records(sec, a["start"], a["stride"], a["end"], a["name"], a["fields"]):
        names.append(("ability", r["id"], sec.at(r["ram"] + a["name"][0], a["name"][1])))
    entries, seen, stats = [], {}, collections.Counter()
    for cat, rid, nb in names:
        nb = nb.split(b"\0", 1)[0]
        if not nb:
            continue
        h = fnv1a64(nb)
        if h in seen:
            stats["duplicate"] += 1
            continue
        enc = ann.ruby_fragment(nb) if fragment else ann.annotate_name(nb)
        if enc is None:
            stats["unchanged"] += 1
            continue
        seen[h] = enc
        entries.append((h, enc))
        stats["annotated"] += 1
        if review:
            review.write("%-10s %3d  %-16s -> %s\n" % (cat, rid, decode_jp(nb, ann.single, ann.page15),
                                                      enc.hex() if fragment else decode_jp(enc, ann.single, ann.page15)))
    return entries, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=default_cue(), help="JP disc .cue")
    ap.add_argument("--bin-root", help="extracted JP BIN/ tree instead of the .cue")
    ap.add_argument("--width", type=int, default=16, help="box width in cells (16 measured)")
    ap.add_argument("--rows", type=int, default=3, help="rows per page before a split")
    ap.add_argument("--scope", choices=["area", "every"], default="every",
                    help="annotate every occurrence (default, the shipped jp_furigana) or only "
                         "a word's first occurrence per area (retired: the furigana rows cost "
                         "no width, so there is nothing to save)")
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
    ap.add_argument("--insert-width", type=int, default=16,
                    help="cells budgeted for a 0x07 item / skill insert when a row is laid out "
                         "(16: an annotated name fills a row; docs/INSERT_RUBY.md)")
    ap.add_argument("--insert-out", help="default generated/bof3_insert_<code>.c: the runtime-"
                         "insert table (annotated item / ability names), built alongside")
    ap.add_argument("--insert-review", help="write the name -> annotated name list here")
    ap.add_argument("--inline", action="store_true",
                    help="the retired layout: readings inline in brackets after each word, "
                         "pages re-flowed (jp_ruby / jp_ruby_all). Default is furigana: "
                         "readings in an 8 px row above each text row, authored breaks kept, "
                         "two text rows per page, pages with their own span or preset kept "
                         "verbatim (docs/FURIGANA.md)")
    ap.add_argument("--rows-out", type=int, default=2,
                    help="furigana: text rows per page (two pairs fit the 42 px box)")
    ap.add_argument("--lint", help="furigana: simulate the plugin's draw-time cursor over every ruby "
                         "row and write the rows whose readings would not land where the builder "
                         "put them (the check that would have caught 村の連中に)")
    args = ap.parse_args(argv)
    if not args.dict:
        args.dict = DICT_FOR_SCOPE[args.scope]

    args.furigana = not args.inline
    if args.furigana:
        code = {"every": "jp_furigana", "area": "jp_furigana_area"}[args.scope]
    else:
        code = {"every": "jp_ruby_all", "area": "jp_ruby"}[args.scope]
    if not args.out:
        args.out = os.path.join(ROOT, "generated", "bof3_xlate_%s.c" % code)
    if not args.insert_out:
        args.insert_out = os.path.join(ROOT, "generated", "bof3_insert_%s.c" % code)
    disc = Disc(cue=args.cue, bin_root=args.bin_root)
    overrides = load_overrides()
    ann = Annotator(args.width, args.rows, annotate=not args.selftest,
                    reflow=not args.selftest and not args.furigana,
                    dict_name=args.dict, overrides=overrides,
                    ambiguous={} if args.ambiguous else None,
                    insert_width={0x07: args.insert_width},
                    furigana=args.furigana, rows_out=args.rows_out)
    if args.lint and args.furigana:
        ann.lint = []
    review = open(args.review, "w", encoding="utf-8") if args.review else None
    entries, seen_hash = [], set()
    stats = collections.Counter()
    longest = (0, None)

    for path, data, base, slots in message_blocks(disc):
        seen_words = set()                       # first occurrence per area
        for m in slots:
            off = base + struct.unpack_from("<H", data, base + 2 * m)[0]
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
          % (args.rows_out if args.furigana else args.rows, args.width,
             ann.stats["split_pages"], ann.stats["narration_pages"]))
    if args.furigana:
        print("furigana pages %d (readings placed %d, insert markers %d, no room %d); "
              "pages with their own span / preset kept verbatim behind a reset: %d"
              % (ann.stats["furigana_pages"], ann.stats["ruby_placed"], ann.stats["ruby_insert_markers"],
                 ann.stats["ruby_no_room"], ann.stats["effect_pages"]))
    if ann.lint is not None:
        with open(args.lint, "w", encoding="utf-8") as f:
            f.write("# Ruby rows whose readings would not draw where the builder put them\n"
                    "# (text row / ruby row / reading index: wanted x -> drawn x, px from the row origin)\n\n")
            for text_row, ruby_row, bad in ann.lint:
                f.write("%s\n  %s\n  %s\n\n" % (text_row, ruby_row,
                        "; ".join("#%d: %d -> %d" % b for b in bad)))
        print("lint: %d ruby rows simulated, %d with a misplaced reading (%s), %d rows with an "
              "insert skipped, %d readings placed more than a half-cell off their stem"
              % (ann.stats["lint_rows"], ann.stats["lint_bad_rows"], args.lint,
                 ann.stats["lint_skipped_insert_rows"], ann.stats["lint_off_stem"]))
    print("longest encoded message: %d bytes (%s); slot cap %d" % (longest + (args.max_len,)))
    top = sorted(((len(e), h) for h, e in entries), reverse=True)[:5]
    print("five longest: %s" % ", ".join("%d" % n for n, _ in top))
    if args.furigana:
        # The runtime-insert table for the furigana layout holds ruby-row
        # FRAGMENTS, not annotated names: the plugin splices one in place of
        # the INSERT_MARK above the inserted name (docs/FURIGANA.md "Inserts").
        ireview = open(args.insert_review, "w", encoding="utf-8") if args.insert_review else None
        ientries, istats = insert_entries(disc, ann, ireview, fragment=True)
        if ireview:
            ireview.close()
        iblob = emit_c(args.insert_out, ientries, code=code, tool="tools/build_ruby_script.py",
                       what="Japanese (Furigana) runtime-insert table (ruby fragments for item / ability names)",
                       prefix="bof3_insert")
        print("wrote %s: %d name fragments (%d blob bytes); %d names without kanji, %d duplicates"
              % (args.insert_out, istats["annotated"], iblob, istats["unchanged"], istats["duplicate"]))
        return 0

    # The runtime-insert table: the same annotator over the item / ability
    # names the game copies into the 0x07 records (docs/INSERT_RUBY.md).
    ireview = open(args.insert_review, "w", encoding="utf-8") if args.insert_review else None
    ientries, istats = insert_entries(disc, ann, ireview)
    if ireview:
        ireview.close()
    iblob = emit_c(args.insert_out, ientries, code=code, tool="tools/build_ruby_script.py",
                   what="Japanese (Ruby) runtime-insert table (item / ability names)",
                   prefix="bof3_insert")
    print("wrote %s: %d names annotated (%d blob bytes); %d unchanged (no kanji), "
          "%d duplicates, %d too wide for a %d-cell row / 31 bytes"
          % (args.insert_out, istats["annotated"], iblob, istats["unchanged"], istats["duplicate"],
             ann.stats["insert_too_wide"], args.width))
    return 0


if __name__ == "__main__":
    sys.exit(main())
