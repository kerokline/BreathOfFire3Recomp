# Japanese (Furigana) — a third script variant for learners

**Status:** SHIPPED as `jp_furigana` (2026-09-12): every kanji word's reading
drawn in an 8 px row above it, from the game's own small kana font, with
the authored line breaks kept — see *The 8 px font* and *The rendering
route, reopened* at the foot of this file. Built by
`tools/build_ruby_script.py` into `generated/bof3_xlate_jp_furigana.c` and
delivered by the same `MsgBox_Reset` plugin as English
([`LOCALIZATION_APPLY.md`](LOCALIZATION_APPLY.md)), whose row rule and
packet hooks do the drawing. Readings are still SudachiPy's, not proofread —
that review pass is what remains.

**Retired the same day (user's call):** the inline-bracket variants
`jp_ruby` / `jp_ruby_all` (`漢字（かんじ）`, pages re-flowed) and the
first-occurrence-per-area scope. Furigana rows cost no width, so the
first-time-only scope had nothing left to save, and the brackets are
strictly worse than readings above the line. Both remain buildable
(`--inline`, `--scope area`) but are out of `game.toml`'s language list and
the plugin. Everything below the *As built* section is the history of how
the inline variant was costed and built; it still documents the encoder,
the byte budget and the reading pipeline the furigana variant inherits.

The goal is a reading aid, not a translation: the Japanese script with the
readings shown, selectable next to English and Japanese. The decision taken
2026-09-09 is to do it **as data** — a re-authored script variant with the
reading inline, `漢字（かんじ）` — rather than by rendering ruby glyphs above
the line.

## Why inline, and not real ruby

**Superseded in part, 2026-09-12:** the advance *does* track size on the
quad path, and per-glyph placement is overridable from the plugin. See *The
rendering route, reopened* at the foot of this file. The paragraph below is
kept as the reasoning of 2026-09-09.

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
  menus come into scope. **Trap paid for:** the plugin gated the pointer to
  the area block (`0x80010000`–`0x80014000`) and skipped every system-block
  message before the lookup, so the new entries were inert until
  `AREA_BLOCK_HI` became `0x80017628`, the end of the system section
  (`src/bof3_localize.c`). Also checked on the way: a headless boot with only
  `settings.toml` resolves `lang=jp_ruby_all` immediately (debug port
  `{"cmd":"xlate"}`), and the plugin registers all three tables.

## The 8 px font (2026-09-12, late)

The 6 px readings were legible only with effort: a 12 px bitmap point-
sampled to half height loses every other row, at native resolution and
at 4x alike (user screenshot). The fix needed no new art and no VRAM: the
single-byte page of `BIN/ETC/ENDKANJI.EMI` carries **the game's own 8 x 8
kana font** below the 12 px cells, page rows 168-215, 8 px pitch both
ways, five rows of 32 -- 46 hiragana, all 25 voiced forms, the 9 small
kana, the long vowel bar, and the katakana (`analysis/font/small_font_grid.png`,
transcribed in [`names/font_small.toml`](../names/font_small.toml),
`tools/sync_small_font.py` -> `src/bof3_small_font.h`). The atlas has no
spare cells at all (one empty cell of 882; the six kanji no script
references are battle and item words), so a custom font would have had to
displace something; this one is already there.

**How a reading glyph reaches it.** The box mapper only knows 12 px cells,
but the quad blitter builds an ordinary `POLY_FT4` in RAM and commits it
through `0x8014E494(1, 0x28)` with the packet at `*0x80145988` and every
field written (`SetDrawTPage`, `GetClut`, u/v/tpage, the four vertices,
`SetSemiTrans`, then the commit -- Psy-Q PRIM.OBJ calls, `symbols.toml`).
The plugin hooks that commit (sixth `mod_function_entry_funcs` entry),
filtered by the blitter's return address `0x80152D84`, and for a reading
glyph rewrites the packet: UV origin to the small cell of the same kana,
7-texel extent, an 8 px square from the game's own x0/y0, same texture page
and CLUT. The dialogue palette draws the small font white (its strokes are
nibble 2 where the main font uses 7 and 1; `BOF3_RUBY_PAL=n` overrides the
CLUT to palette n if another box's palette ever differs). The renderer's
advance is still 12 + P = 6, so kana after the first in a reading get +2
for an 8 px pitch; the builder sizes a reading as ceil(8n / 6) half-cells.

**Rows.** Ruby row FIRST, then its text row: the next-page arrow places
itself off the last row (user's screenshot: it sat under the ruby row), so
a page ends on text. Offsets from the origin: ruby -2 and 19, text 6 and
27 -- 8 px bands, the block moved up 2 px so the two extra pixels per band
are shared between the margins (user's call). A ruby row with no reading
draws nothing, so the first glyph of a frame derives its row from the
game's own y (origin + 14 x newlines) rather than assuming row 0. One
consequence: a reading now types in just before its word rather than
after it, which is how furigana reads.

Verified on the AREA014 scarecrow talk, four pages
(`analysis/xlate_shots/furigana_area014_8px.png`): はな over 話, みあ over
見上, こころ over 心, ちょうし over 調子, もの / はな / しら / い / き,
all at 1:1 from the 8 px design. Tables regenerated: 4,542 / 5,699 entries,
11,091 / 21,258 readings placed.

**Three corrections from the user's first play frame (same night):**

- **The glyph rows start at page y 169, not 168** (the 168 grid line is
  empty), and the **UV extent must be the size, not size − 1**: u is
  interpolated from the vertex, so an extent of 7 over 8 px never reaches
  the eighth texel row (the game's own 11-for-12 drops its cells' last
  row, which is empty). Together those cut 2 px off every reading's foot
  (こころ lost its bottom stroke). `names/font_small.toml` `page_y = 169`,
  extent `RUBY_PX`.
- **The next-page arrow goes through the same sprite blitter** from a
  caller outside the renderer, and the row rule re-placed it onto the
  current row at whatever x the game gave it — the "stray glyph" over け in
  the user's frames. Both blitter hooks now act only on the renderer's own
  calls (return addresses `0x80150870` sprite, `0x80150800` quad).
- **The arrow's y is cursor y + 14 + P** (measured on plain 1-, 2- and
  3-row probe pages: +14 with P = 0), and a furigana page keeps P = −6, so
  it landed 6 px inside the last text row. On the page's last glyph — a
  text glyph, since ruby rows come first — the sprite hook leaves the RAM
  cursor y at row y − P while the glyph itself takes y from a1; the arrow
  then lands one row under the text (`analysis/xlate_shots/furigana_area014_arrow.png`).

**Gap arithmetic, corrected on the user's second play frame (レイ's
「人が来る前に, readings drifting left along the row):** a reading's kana
advance 8 each but the renderer adds only 6 after the last, so the cursor
sits 8n − 2 past the reading's start — off the 6 px half-cell grid — and
every later reading on the row started early by the remainder. The plugin
now snaps the cursor up to the next half-cell from the row's origin before
it counts gap bytes, and the builder counts a reading's consumed cells the
same way (ceil((8n − 2) / 6)), keeping the wider ink footprint
(ceil(8n / 6)) only to keep a later reading off it. A reading wider than
its stem hangs right, aligned with the stem's left edge, and takes a free
half-cell on the left only past half a cell of overhang. Verified by
encoding AREA018 slot 25 through the builder and injecting it on a field
state: ひと / く / まえ each on their kanji.

Left: the reading review pass; the 297 readings dropped after a runtime
insert.

## The rendering route, reopened (2026-09-12)

The user's framing: if the y spacing is controllable, the existing script
re-flows to a **two-row box with a reading band above each row** instead of
the three-row inline layout, and nothing has to be spelled out in brackets.
Taking stock against the disassembly changed two of the 2026-09-09 blockers
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Per-glyph placement"):

- **The advance tracks size on the quad path.** `0x80151F4C` adds `P` to the
  cursor before the renderer's 12, so a span drawn at P = −6 is 6 px kana at
  6 px pitch. The doc's "hard 12 px add shared by both blitters" was wrong.
- **Per-glyph placement is overridable without guest code.** The cursor is
  re-read from RAM before every glyph, both blitters are hookable function
  entries, and the hook gets `CPUState`. A build-time layout table (glyph
  index → x, y) driven from a per-frame counter places everything; the
  engine's newline and advance stop mattering.

What did not change: the typewriter reveals by glyph count (a reading types
out after its word, which is acceptable); the span flag is a register, so ruby
runs must be `<0d>…<0e>` in the string; `P` is one global per message; the box
frame height is still unlocated (set through a struct pointer, not an
immediate), so a taller box stays uncosted. Width is now settled: 15 cells
fit, 16 touches the wall.

**Row budget under this layout.** A text row plus its 6 px band needs about
20 px, so the 42 px interior holds **two** annotated rows. Pages that use a
third row today (1,215 confirm pages) split; every other page keeps its
authored rows, because the readings no longer cost width. That is a cleaner
trade than the inline variant's re-flow of nearly every page.

**Order of work:**

1. ~~**Shrink probe, on screen.**~~ **DONE 2026-09-12 (evening), on
   `slot02`** — a field state facing a talkable NPC in AREA014, saved by the
   user. `tools/ruby_shrink_probe.py --slot 2 --variant span|span3|plain|
   bracket`; crops in `analysis/xlate_shots/ruby_shrink_compare.png`. What
   it settled:
   - **12 + P advance holds in play.** `<0f><13>` (P = −6) drew every
     `<0d>…<0e>` run as 6 px kana at 6 px pitch; `<0f><12>` (P = −3) as 9 px
     at 9 px. Glyphs outside the span stayed 12 px on the sprite path with
     P = −6 live, so the span flag really is the only switch between the two
     blitters, and the preset survives the `<01>` newline (flags `0x0008`,
     P = −6 read back after the page finished).
   - **The shrunk glyph sits at the top of its cell.** The quad is anchored
     at the cursor, so a 6 px reading already occupies the upper half of the
     12 px row. A ruby band above the row is a y shift of about −6 and an x
     step back over the word — exactly what step 2's placement hook writes —
     not a second layout.
   - **6 px is legible, barely.** むら / ひと / よる / さばく / で all read at
     native resolution but the point-sampled strokes are thin; 9 px (P = −3)
     is comfortably readable and would fit a band if the box grew by 3 px
     per row, which the row budget below does not assume. Compare both crops
     before choosing.
   - **The bracket variant overflows the frame** on this sentence (夜（よ cut
     at the wall), which is the inline cost the row-budget table already
     priced.
   - **The newline does not track the row's size** (user's follow-up test,
     `analysis/xlate_shots/ruby_shrink_newline.png`): a 30-kana row drawn at
     P = −6, with `<01>` inside or outside the span, put the next 12 px row
     at screen y 191 either way — the same y the plain text takes. Measured
     bands: shrunk row 177–181, full row 178–187, second row 191–201 in all
     three. So the 14 px step at `0x80150690` is a hard immediate as
     documented, and a reading row costs a full row of height unless the
     placement hook (step 2) moves y itself. Two annotated rows at 14 + 14
     per pair would need 56 px of a 42 px interior, which is why the hook
     is the route and not a `<01>` between band and text. One thing the
     measurement gives for free: a 6 px reading row sits 14 px above the
     next text row, which is roughly the band-above look already.

   Two traps paid for: the probe's decoded-text echo is Japanese and the
   console is cp1252 (the tool now re-wraps stdout as utf-8), and the field
   idle animation walks the party off the NPC while `scene.enter()` settles,
   so the tool now loads, writes, and presses Circle in one go (3.6 s of
   single-byte `write_ram` calls is still inside the window) and waits for
   game mode 4 before the screenshot. `jptext.decode` does not know `<0f>`
   takes a parameter byte, so its echo of the span variants misreads the
   preset byte as a kanji — cosmetic.
2. ~~**Hook feasibility.**~~ **DONE 2026-09-12 (evening): register writes
   from a function-entry plugin are honoured.** `0x8014F6BC` (the sprite
   blitter, x in a0, y in a1) is the third entry in
   `mod_function_entry_funcs`; `src/bof3_localize.c` registers
   `on_sprite_glyph` there only when `BOF3_RUBY_YBUMP=n` is set and adds n
   to `gpr[5]`. With n = 8 on the span probe
   (`analysis/xlate_shots/ruby_ybump_compare.png`) every full-size glyph
   moved from y 177 to 185 and the second row from 190 to 199, while the
   6 px readings, which take the unhooked quad path, stayed at 177–181 and
   191–195. The generated code reads `cpu->gpr[]` directly at each
   instruction, so there is no cached local to fight. Adding the hook
   regenerated one shard in 3 s, needed no overlay recompile, and did not
   change `PSX_OVERLAY_CODEGEN_HASH` (that is a hash of the emitter sources,
   not the config), so savestates survive. Two things the frame shows on
   the way: the readings sit at the cursor x *after* their word, so x has to
   step back by the word's width for a band; and the second row's readings
   drew into the bumped first row, because the hook moved the argument and
   not the RAM cursor — the layout table has to own both x and y for every
   glyph, both paths, or the two drift apart.
3. ~~**Layout table + builder.**~~ **Replaced by the row rule, and
   demonstrated on screen 2026-09-12 (evening)** — the user's cut: a ruby row
   is its own row in the string, so x aligns by glyph count (a 6 px glyph is
   half a text cell: ruby half-cell 2c sits over text cell c) and the plugin
   only owns y, per row. No per-glyph table, no re-flow; authored line
   breaks stay, and a page's third row moves to a new page.
   `analysis/xlate_shots/ruby_rows_demo.png`: むら over 村, ひと over 人, よる
   over 夜, さばく over 砂漠, で over 出, both pairs inside the 42 px box.

   **String shape** (`tools/ruby_shrink_probe.py --variant rows --blank 09`):
   `<0f><13>` at the head, then per authored row `text <01> <0d> ruby <0e>`,
   rows joined by `<01>`. The ruby row is half-cells: a reading starts at
   2 × (its stem's cell), padded with **`0x09` gap bytes** — the renderer
   ignores `0x09` and the stepper does not count it, so gaps cost no bytes
   of font, no reveal ticks and no advance of their own. (`0xFF`, the word
   separator, is a separator only at full size: drawn shrunk it is a junk
   cell, and the single-byte sheet has no empty cell at all.)

   **Plugin** (`src/bof3_localize.c`, env-gated so the play build is
   unchanged without the variables; `BOF3_RUBY_ROWY=8,1,29,22
   BOF3_RUBY_GAP=9` is the demo): three more entries in
   `mod_function_entry_funcs` — the renderer `0x80150598` resets the row
   counter each frame; both blitters call `place_row`, which reads the
   cursor y `0x801490BA`, treats a value it did not write and the game did
   not hold for this row as the newline having fired (+14 → next row), and
   writes `origin + offset[row]` back (plus the same delta into a1 on the
   sprite path, which already carries y). Offsets are chosen so no written
   y is a multiple of 14 from the origin, which keeps the two sets apart.
   On odd rows the quad hook reads the string walk pointer from a1, counts
   the `0x09` bytes before the glyph and adds `n × (12 + P)` to the cursor
   x `0x801490B8`. Measured bands: ruby 177–182 and 198–203, text 185–195
   and 206–216 (origin y 176).

   **Corrections to this file's own step-1 and step-2 notes, from the
   demo:** the shrunk glyphs *do* go through the quad blitter `0x80151F4C`
   (a1 = the string pointer, same `s0` the sprite call stores at sp+0x10);
   the step-2 sentence saying they take the sprite path was a debugging
   misread and is wrong. And on a two-row-plus-ruby page the box drew four
   `<01>` rows without complaint, so a four-row string is fine when the
   plugin keeps them inside the frame.

   ~~**What the builder now owes**~~ **BUILT 2026-09-12 (late evening) and
   verified on a real conversation:** `tools/build_ruby_script.py --furigana`
   (`--scope every` for `jp_furigana_all`) emits `generated/bof3_xlate_jp_furigana.c`;
   both codes are in `game.toml`'s language list as *Japanese (Furigana)* and
   *(Furigana, every word)*; `analysis/xlate_shots/furigana_area014_pages.png`
   is the AREA014 scarecrow talk, four pages, from the table with no probe
   bytes. Numbers (first-per-area): 4,542 entries, 358 KB, 6,212 furigana
   pages, 11,091 readings placed, 112 dropped after a runtime insert (the
   insert's width is only known at draw time, so nothing to its right can be
   aligned), 0 with no room, 2,301 pages split at two text rows, 106 pages
   kept verbatim behind a reset preset for their own span or preset, longest
   message 837 bytes. No insert table: an inserted item or skill name draws
   inline in the text row and goes unread. `--selftest --furigana` round-trips
   all 7,014 messages byte for byte — and fixing that exposed a regression in
   the inline variant's own selftest (87 mismatches since the 16-cell insert
   budget, 2026-09-11: with re-flow off the layout still wrapped rows at the
   budget), now 0 on both.

   **How the plugin knows a page** (`src/bof3_localize.c`): hooks on the
   renderer and both blitters are always registered; once per page the
   renderer-entry hook reads the page base `0x801490A8` and applies the row
   rule only to a page whose bytes start with `<0f><13>` (past an optional
   `<0c>xx` head) — the builder writes that preset at the head of every
   annotated page and no shipped page starts with a preset. Every other
   page, in any language, is untouched (checked: `jp_ruby` still draws three
   rows at the 14 px pitch). Row offsets 8, 1, 29, 22 and the gap code 0x09
   are compiled in; `BOF3_RUBY_ROWY`, `BOF3_RUBY_GAP` and `BOF3_RUBY_FORCE=1`
   (rule on every page, for the probe tool's demo) override them. **Trap
   paid for:** the hooks gated the base and glyph pointers to guest RAM and
   a redirected message lives in the plugin's ring at `0x9F000000`, so the
   first run drew every page at the plain pitch with the readings bunched at
   the row start — `readable_text()` now accepts the ring. Also settled on
   the way: `0x801490A8` really is the *page* base (it walked `+0x00`,
   `+0x43`, `+0x81`, `+0x94` through the four pages), and a text row with no
   reading still gets its empty `<0d><0e>` ruby row so the alternation
   holds — an empty row draws no glyph, so the plugin advances the row
   counter by however many 14 px steps the newline fired.

   Open before shipping: ~~messages that carry their own `<0d>…<0e>` (a shout span would
   shrink under the message-wide preset — count them)~~ **counted,
   `tools/emphasis_census.py` (2026-09-12 evening)**: over 6,924 distinct
   messages (200 areas + system block), 96 carry a span or preset, 29 of
   those have no kanji at all and are left verbatim. Per distinct *page*,
   which is the unit that matters because every page after the first is
   opened by its own replay and the size parameter only affects what is on
   screen: **78 pages carry a span or preset, 26 of them also hold kanji,
   and in 8 the span itself holds kanji** (殺してやるッ, な‥な‥何だ,
   だだ‥誰だ, お前らが, 爆音で, 道を, 教えて, 動いて). Effects in use: 58
   resets, 34 grows, 3 shrinks (all −3), 12 shake/drop. So the collision set
   is 26 pages; the builder's choice per such page is to keep the shout and
   drop that page's readings (emit it verbatim behind a reset preset, then
   re-arm the shrink preset on the next page), or to strip the effect and
   annotate. **Decided 2026-09-12 (user): keep the shout and drop the
   readings for that page** — a page that carries any `<0d>…<0e>` or `<0f>`
   is emitted verbatim (no ruby rows, no gaps) behind a reset preset, and
   the next page with readings re-arms the shrink preset. 26 pages, 8
   kanji-in-span, go unread.
   Also from the census: a message's own preset (`<0f>` with a `reset` or
   `grow`) changes P for the rest of *its page*, so the builder re-emits the
   head preset after any foreign `<0f>` on a page that still has ruby rows
   to come — or, simpler, treats any page with a preset as verbatim.
   Remaining open items: readings are still SudachiPy's, unproofread (the
   same `names/readings.toml` sidecar and `--ambiguous` audit apply); the typewriter
   (readings reveal after their row's text, which the demo showed is fine),
   and whether the gap code should be `0x09` or `0x11` (both unused; `0x10`
   toggles a flag). The row offsets belong in `game.toml` or the table
   header rather than an env var once the variant exists.

