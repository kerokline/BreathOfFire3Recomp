# Japanese (Ruby) — a third script variant for learners

**Status:** BUILT and on screen (2026-09-09 evening). The variant ships as
`jp_ruby` in `[localization].languages`, built by `tools/build_ruby_script.py`
into `generated/bof3_xlate_jp_ruby.c` and delivered by the same `MsgBox_Reset`
plugin as English ([`LOCALIZATION_APPLY.md`](LOCALIZATION_APPLY.md)). Verified
headless on AREA150 slot 45: 夜を待（ま）って‥砂漠に出ますか？. Readings are
still SudachiPy's, not proofread — that review pass is what remains.

The goal is a reading aid, not a translation: the Japanese script with the
readings shown, selectable next to English and Japanese. The decision taken
2026-09-09 is to do it **as data** — a re-authored script variant with the
reading inline, `漢字（かんじ）` — rather than by rendering ruby glyphs above
the line.

## Why inline, and not real ruby

Real ruby is closer than it looks and still not close. The box already draws
scaled glyphs: a `0x0F` size preset switches it from an unscalable `SPRT` to a
`POLY_FT4` quad whose size is `12 + P` px, so half-height kana need no new
primitive and no second font in VRAM
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Two blitters"). What is missing is the
**metrics**: the cursor advance is a hard 12 px add at `0x801508A0` shared by
both blitters and does not track the drawn size, the newline is a hard 14 px at
`0x80150690`, the size is one global rather than per-row, and the typewriter
reveals by character count, so a ruby row would type out separately from the
word it annotates. Two of those are single immediates; the rest is upstream
psxrecomp work under the enhancement gate. Inline needs none of it.

## The constraint: 15 glyphs per line, 3 rows per page

Measured over 8,323 box lines (`python tools/ruby_fit.py width`):

| page kind | lines | longest line |
|---|---:|---:|
| box, confirm-advance | 8,323 | 15 |
| box, timed `0x16` | 1,724 | 15 |
| no break (narration, choice menus) | 13,576 | 28 |

15 is an **observed maximum, not a measured clip boundary**. Nothing in the
shipped script puts a 16th glyph in a box line; the 16–28 glyph lines are all
full-screen narration or choice menus, where the option list joins the prompt.
If the box really holds 16–18, every figure below improves. Rows are settled
separately: three rows are ordinary and four never appear on a confirm page
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Rows per page").

## What inline costs, page by page

`python tools/ruby_fit.py cost`, over all 3,793 distinct confirm pages.
Readings come from SudachiPy mode C over the decoded text with okurigana
trimmed, so each annotation is its real length: **15,610 words, 2.41 kana
each**, or about 4.4 glyphs with the brackets. Only 42 words had no usable
reading.

| annotation scope | layout | pages over 3 rows | 2-row pages that need a 4th |
|---|---|---:|---:|
| every word | keep authored breaks | 1,199 (31.6%) | 320 of 2,100 (15.2%) |
| every word | reflow the page | 343 (9.0%) | 47 of 2,100 (2.2%) |
| first per page | keep authored breaks | 1,190 (31.4%) | 314 (15.0%) |
| first per page | reflow the page | 339 (8.9%) | 47 (2.2%) |
| **first per area** | keep authored breaks | 809 (21.3%) | 138 (6.6%) |
| **first per area** | reflow the page | **163 (4.3%)** | **19 (0.9%)** |

Two things to take from that. The spare third row **is not spare**: it is
already used on 1,215 pages, and 72% of those overflow when every word is
annotated. And suppressing repeats is the cheapest lever available — annotating
only a word's first appearance in an area suppresses 5,488 annotations and
roughly halves the overflow, at no cost to a first-time reader.

`python tools/ruby_fit.py sample AREA000:19` shows the shape, a two-row page
becoming three:

```
shipped                        furigana, page reflowed
|。あさ 起きたら       |        |。あさ 起き（お）たら家（いえ|
|家の前に お金があってね。  |        |）の前（まえ）に お金（かね）|
                               |があってね。         |
```

**These readings are costed, not proofread.** Spot checks show the usual
tokenizer artifacts: `言う` gets Sudachi's normalized reading form and comes out
`ゆ` after okurigana trimming, and mode C sometimes splits a compound (`何年` →
`何（なん）年（ねん）`), which costs an extra bracket pair. Splits inflate the
numbers above rather than flattering them, and a wrong reading is the same
length as a right one, so the row cost stands; the shipped variant still needs
the reviewed reading pass.

## The re-authoring rules that follow

The user's call, 2026-09-09: **re-authoring line and page breaks is accepted.**
Some intended screens will break differently; the readings are worth it. So:

1. **Re-flow each page** rather than preserving authored line breaks. Keeping
   them costs five times the overflow for no reading benefit.
2. **Annotate first occurrence per area.** The area is the natural scope — it
   is one script block, one load, one visit.
3. **Spend a page break, not a fourth row, on overflow.** `0x02` is one byte
   and nothing anywhere counts pages
   ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) control codes), so the ~163 pages that
   still exceed three rows are split rather than grown. Four-row pages stay
   untested territory and this avoids needing them.
4. **Leave the non-dialogue paths alone.** Choice menus (`0x14`), the narration
   pages and the fishing guide are not confirm boxes and are out of scope for
   the first pass, the same scope decision the translation track already took.

## As built (2026-09-09)

`tools/build_ruby_script.py` does what the sections below planned, with these
decisions taken while building it:

- **Bytes, not text.** Every glyph keeps its original bytes; readings are
  inserted as new kana glyphs (the sheet's `(`/`)` at `0x28`/`0x29` bracket
  them), and the message is joined back. `--selftest` (no readings, no
  re-flow) reproduces all 6,768 distinct messages byte for byte.
- **The reading follows the kanji stem**, `起（お）きる`, with head and tail
  kana trimmed off the reading (`ruby_fit.ruby_for`).
- **Box pages only.** A page authored wider than 16 cells or taller than 3
  rows is the narration path and passes through verbatim (101 pages).
- **Layout:** a word and its reading are one unit; closing punctuation
  clings to the unit before it; rows are 16 cells (the measured frame, one
  more than the 15 below); over-3-row pages split with `0x02` (400 pages).
- **Numbers:** 5,926 messages change; 11,070 readings at 2.31 kana each;
  10,526 repeats suppressed by first-occurrence-per-area; 45 words with no
  usable reading; 0 unencodable kana; 314 KB table.
- **A second variant, `jp_ruby_all`** (`--scope every`, launcher label
  *Japanese (Ruby, every word)*), reads every occurrence: 6,063 messages
  change, 21,596 readings, 1,096 page splits (against 400), 366 KB. The
  budget that matters at runtime is the plugin's 2 KiB slot per message, not
  the 16 KiB window (the copy lives in enhancement memory); the longest
  message is 702 bytes, so no area needs re-evaluating. Verified on the same
  AREA150 prompt: 夜（よる）を待（ま）って‥砂漠（さばく）に出（で）ますか？.

## Delivery — what is config and what is open

The variant is a third entry in the framework's language list, which already
drives the launcher dropdown:

```toml
[localization]
languages = [
    { code = "en", label = "English" },
    { code = "jp", label = "Japanese" },
    { code = "jp_ruby", label = "Japanese (Ruby)" },
]
```

That part is config (`psxrecomp/docs/STRING_TRANSLATION.md` §3.5). What is
**not** settled is how the bytes reach the box for this title. The framework's
generic capture/apply hook found no strings here (F-3 / F-4 in
[`LOCALIZATION.md`](LOCALIZATION.md)) because BoF3 never passes a string
through `psx_dispatch`; the route chosen for the translation track is a
**pointer repoint at `MsgBox_Reset`** ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "The
resolver"). A ruby variant rides the same mechanism — it is one more source of
replacement message bytes — so it should not need its own. The alternative,
replacing the whole `0x80010000` section per area, is proven possible by
Capcom's own localizations growing that section freely
([`regional-builds.md`](regional-builds.md)) but has no loader-side
implementation here.

## What an encoder has to do, and what it does not

**The compiler is not in this path.** None of the 406 compiled overlays loads at
`0x80010000`; the eleven load addresses are the band bases and the boot EXE.
184 `AREA*.EMI` files do contribute overlays, but those are their *code*
sections at the band addresses. The script block is data that arrives by
CD-ROM DMA and never goes through codegen, so a re-authored script is never
"accepted" or rejected by a build step. It has to satisfy the **box stepper**,
not the recompiler.

That means the encoder owns three things: glyph codes, the control-code stream
(`0x01` newline, `0x02` page break, and every code it must carry through
untouched — speaker `0x0C`, substitutions `0x03`/`0x04`/`0x07`/`0x08`, choices
`0x14`), and the `u16` offset table at the head of the block, which every index
resolves through.

**The character-table gap is closed, 2026-09-09.** The single-byte half of the
encoding was read off the font sheet and is now
[`names/font.toml`](../names/font.toml) (`tools/font_sheet.py`,
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) "The single-byte codes"). Coverage of the
area scripts went from 82.35% of glyph cells to **100.00%** — all 204,356 cells,
nothing left unnamed. The encoder has both directions for every byte a
re-authored script needs.

Brackets in particular are settled, and there are three pairs to choose from:

| pair | codes | note |
|---|---|---|
| `（ ）` | `0x28` `0x29` | unused by the script, so it carries no existing meaning |
| `「 」` | `0x2A` `0x2B` | the speech quote, 5,740 uses — do not reuse |
| `『 』` | `0x3B` `0x3C` | 135 uses, already paired in the script |

`（ ）` is the one to use: one cell each, like every other glyph, and free of
prior meaning — which is exactly what the cost model above assumed, so those
numbers stand. Note that `0x2A` and `0x3B` are the two hanging-punctuation
cases (`x -= 0x0C` at line start), which is a reason to avoid `『』` for ruby —
a reading that wraps to the start of a line would hang into the margin.

What the encoder still owes, none of it blocked:

1. **The control-code stream.** Carry through speaker `0x0C`, the
   substitutions `0x03`/`0x04`/`0x07`/`0x08`, choices `0x14`, effects
   `0x0D`/`0x0E`/`0x0F`, and re-author only `0x01` and `0x02`.
2. **The `u16` offset table** at the head of the block, which every message
   index resolves through.
3. **The reviewed reading pass** ([`IDEAS.md`](IDEAS.md) Part 1). This
   document's numbers generate readings on the fly; the shipped variant wants
   them stored and checked.

## The byte budget — it fits, with 10% to spare

The area script block loads at `0x80010000` and the system/UI pool sits at
`0x80014000`, so the block has a **16 KiB window**
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Live confirmation"). Annotating first
occurrence per area, with each annotation costing one byte per kana plus two
for the brackets:

| | bytes |
|---|---:|
| all 200 blocks today | 562,543 |
| after annotation | 640,304 (+13.8%, median +13.3%) |
| largest block today | 13,008 (79.4% of the window) |
| largest block after | 14,737 (**89.9%** of the window) |

No block passes 16 KiB and none comes near the `u16` offset table's 65,535
limit, so the re-authored script fits the RAM the game already gives it. The
worst case is AREA185 and its siblings at 90% full, which is the number to
watch if the annotation scope ever widens back to every word.

## Reproducing

```bash
python tools/ruby_fit.py width  --bin-root D:\BoFIII\BIN
python tools/ruby_fit.py cost   --bin-root D:\BoFIII\BIN
python tools/ruby_fit.py sample AREA000:19 AREA001:33 --bin-root D:\BoFIII\BIN
python tools/page_rows.py rows                     # the rows-per-page census
```

`ruby_fit` needs SudachiPy (`pip install sudachipy sudachidict_core`; the
every-word scope also `sudachidict_full`). Text decodes through the in-tree
tables, `names/kanji.toml` (the 441 two-byte codes, moved in from the prior
decode work 2026-09-10 with one correction: `0x132C` is 代, not 賃) and
`names/font.toml`, via `tools/jptext.py`; nothing outside the repo is read.
Disc bytes come from the `.cue` in `game.toml` or an extracted `BIN/` tree; the
disc is never written.

## Next session — the build order, and what is genuinely unresolved

Everything needed to *produce* the script exists. Nothing needed to *see it on
screen* does. Those are separate tracks and the first does not wait on the
second.

**Writing the variant (unblocked, this is the next session's work):**

1. **The reading sidecar.** Per message, per word, the kana — stored and
   reviewable rather than generated on the fly, in the slot-aligned shape the
   translation table uses ([`IDEAS.md`](IDEAS.md) Part 1).
2. **The encoder.** Text back to bytes: glyphs via
   [`names/font.toml`](../names/font.toml), the control stream carried through
   untouched, `0x01` and `0x02` re-authored per the rules above, and the `u16`
   offset table rebuilt. Round-trip test: encode the *unmodified* script and
   compare byte for byte against the disc. That test is the whole proof, and it
   is available today.
3. **The variant blocks**, one per area, checked against the 16 KiB window and
   the three-row budget.

**Seeing it run (still unbuilt, and honest about it):**

- **Delivery.** The `MsgBox_Reset` repoint is a design. No code in this repo or
  the runtime substitutes message bytes for this title yet, and the framework's
  generic hook does not fit (F-3 / F-4 in [`LOCALIZATION.md`](LOCALIZATION.md)).
  This is the real gate on a playable build, and it is shared with the English
  translation track rather than specific to ruby.
- **The 15-glyph width is an assumption.** It is the widest line the shipped
  script ever uses, not a measured clip boundary. Worth settling either by
  finding the box frame's width where `Window_DrawFrame` `0x8015A58C` draws it,
  or by putting one over-long line on screen once delivery exists. If the real
  width is 16–18, the overflow numbers above all improve.
- **Reading quality.** The Sudachi pass is costed, not proofread. Since
  2026-09-10 the tool has the levers for it: `names/readings.toml` overrides
  a word's reading before the dictionary (keyed on the surface or on a verb's
  dictionary form, so `言う = いう` also reads 言っ / 言わ / 言え, or on the
  surface plus a `next` list of following tokens or a `prev` list of text
  the line must end with before the word, for a phrase rule: `何 = なに`
  before を / が / も / か / a particle or punctuation, なん otherwise; `方 =
  かた` after 旅の or 若い, where the lexicon's ほう is the direction sense;
  seeded with 私, 言う, 何 and 方), and `--ambiguous FILE` writes the audit list — every annotated
  surface the lexicon reads more than one way, most frequent first, with the
  candidates and what was printed (540 surfaces on the every-word table; 何,
  事, 船, 竜, 様, 力, 人 at the top). A surface key cannot split context
  readings (何 = なに / なん); those stay with the dictionary. Dictionary
  choice: `core` and `full` give identical readings over the whole script (0
  kanji differ), `full` only merges compounds (武器屋 as one token, 130 runs
  of 43,075), so the every-word table uses `full` and first-per-area stays on
  `core` (a merged surface would count as a new first occurrence). A token
  with kana between its kanji prints its whole reading after the whole token
  (最後の夜（さいごのよる）, 会いに行こう（あいにいこう）) instead of a
  stem split. Also fixed: katakana on the page was not trimmed from the
  reading (方向キー printed ほうこうき).
- **Rows break between phrases (2026-09-10).** Every Sudachi token is a
  re-flow unit, and particles, auxiliaries and suffixes attach to the word
  before them, so a row never opens on は or splits つぎは / くれる the way
  the glyph-level fill did. Cost, at width 16: page splits 399 → 554
  (first-per-area) and 1,097 → 1,471 (every word); table entries 5,926 →
  5,835 and 6,063 → 6,042 because more pages now re-flow back to their
  authored breaks. Left: a split can strand one phrase on a page of its
  own (イナカは大変 → 大変 alone); balancing rows across the split would
  fix that.
- **Out-of-vocabulary words (2026-09-10).** A token the lexicon does not
  hold comes back with its own surface as the reading, which the kana check
  rejects, so the word printed bare. Two causes, both closed: dialect
  stretching glued to a kanji (気ィ, 設備ーい, 起動ーう) broke the token
  boundary, so the annotator now tokenizes with a ー / small kana after a
  kanji stripped and hands the glyphs back after the reading (気（き）ィ,
  設備（せつび）ーい); and coinages (闘場, 闘都) are sidecar entries. The
  sweep over the whole script (every kanji token Sudachi marks OOV, and
  every kanji seen only inside one) found no further misread cells after
  0x132C; what it did find is the numeral handler: 一 reads いち and the
  counter tokenizes separately, so 一回戦 / 一戦 / 一発 lost the sokuon and
  一晩 its native reading — two `next` rules on 一 cover the counters the
  script uses. Unread words: 45 → 0.
- **Runtime inserts have a width (2026-09-10, user screenshot).** The
  skill-learned line `<0700> は<0502><0701><06> を教えてもらった！` came out 19
  cells wide: the Ruby layout counted every control as zero width, so the
  name and skill inserts (0x03 / 0x04 / 0x07 / 0x08) took no room in the
  row. They are now budgeted at the widest name each can print (5 / 5 / 8 /
  11 cells, `INSERT_WIDTH`, the English encoder's numbers) in row filling,
  glyph splitting and the box-page test alike. That page re-flows back to
  its authored rows: name は / skill を / 教（おし）えてもらった！. Splits
  554 → 607 and 1,471 → 1,610 as pages with inserts now count them.
- **The field system messages are covered (2026-09-10, user screenshot).**
  何かないかな？ on examining furniture is not in any area script: it is slot
  0 of the **system message block**, `BIN/ETC/AFLDKWA.EMI`'s one section
  (also carried inside `FIRST.EMI`), dest `0x80014000`, an 8-byte header
  then the same u16 offset table as an area script, 309 slots. Most of the
  block is menu, shop and memory-card text (装備, いくつ買いますか, メモリ
  ーカードがありません), left alone by the scope decision and possibly drawn
  in windows of another size; the field-box slots are 0–7 (search / pickup),
  160–165 (inn), 203–218 (save point, けむしにさされた), 241–250 (dragon
  genes). A scan of every overlay for the openers settled how much of the
  block to take: `Msg_OpenSystem` (64 call sites, constant ids 0–3, 5, 208,
  209, 213, 215–217, 250, 262, plus one data-driven site in GAME.EMI = the
  scripts' bit-0x2000 path) is the **only** way system text reaches
  `MsgBox_Reset`, while menus / shops / battle read the block through
  `Msg_SystemPtr` (1,879 sites) and never pass the hook. So the hook is the
  filter, and `build_ruby_script.py` walks the **whole block** (`SYSTEM_BLOCK`,
  309 slots) after the 200 area scripts: a slot the box draws always
  matches, a slot a menu draws never does. +57 / +101 entries; selftest
  7,014 messages, 0 mismatches. The same holds for the English table when
  menus come into scope.
