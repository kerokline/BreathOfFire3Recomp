# Delivering replacement scripts — the `MsgBox_Reset` repoint

**Status:** IN PROGRESS (English **verified on screen 2026-09-09**, and the
same evening the plugin became multi-table and the **Japanese (Ruby)**
variant went through it, verified the same way; see *Verification* and
*Open* for what is deliberately not done yet)

> **2026-09-18 — localization work has moved to `BreathOfFire3PCPort`**
> ([`STATUS.md`](STATUS.md) banner). The plugin and the tables described here
> stay in the build and are **maintained, not extended**: the build recipe and
> traps below are current, the *Open* items are pursued in the other repo.

This is the apply path that [`LOCALIZATION.md`](LOCALIZATION.md) §4.3 item 3
and [`TEXT_ENGINE.md`](TEXT_ENGINE.md) "The resolver" left open: how English
bytes reach the dialogue box of the JP build without touching the disc, the
framework, or the `0x80010000` script block in RAM. Scope is the **area
script only** — dialogue, captions and choice prompts that go through
`Msg_OpenScript`. Menus, items, name entry and everything else in the
`0x80014000` system pool are untouched by design (2026-09-05 decision,
[`STATUS.md`](STATUS.md)).

## The shape, in one paragraph

Every message open is `Msg_OpenScript(idx)` (`0x8015034C`) resolving
`0x80010000 + u16[0x80010000 + 2*idx]`, storing that pointer into
`0x801490A8` (renderer base) and `0x801490AC` (stepper cursor), and calling
`MsgBox_Reset` (`0x8015042C`). `game.toml` lists `0x8015042C` under
`[recompiler].mod_function_entry_funcs`, so the generated C for that function
begins with `psx_mod_function_entry(cpu, 0x8015042C)` — the framework's
trusted static-plugin hook (`psxrecomp/runtime/include/mod_plugins.h`). The
title plugin `src/bof3_localize.c` registers for that address at static-init
time, and on each call: reads the pointer back, walks the JP message to its
real end, hashes those bytes (FNV-1a64), looks the hash up in a table
compiled into the exe, copies the English bytes into **enhancement memory**
(`psx_mod_alloc_guest_memory`, Expansion 1 at `0x9F000000`, host-backed and
readable by ordinary guest loads), and rewrites both globals to point there.
`MsgBox_Reset` then runs unchanged: it eats the leading `0x0C` box-selector byte
from the English copy, and the stepper and renderer read the English stream
with no idea anything happened. A miss (no table entry, a system-pool
pointer, another language) leaves everything alone, so the failure mode is
"that line is Japanese", never a broken box.

**The second door (2026-09-11).** `MsgBox_Reset` is not the only place the
pointer is set. `MsgBox_Replay` (`0x801515F8`) re-derives
`0x80010000 + u16[0x80010000 + 2*idx]` from the *current* index `0x801490A4`
and stores it into both globals with no reset, then parks the stepper in
state 1 for 8 or 16 frames. It runs when the box is re-shown
(`MsgBox_ReplayIfShown` `0x80151554`, window state 2) and from one branch of
the page-break state; the master apprenticeship talk (AREA061 slot 2,
Mygas's 攻撃力 / 防御力 line with its colour spans) is the first sighting:
the box base read `0x80010371`, in the JP block, while the Ruby table held
the message's hash — the replay had thrown the redirect away. The plugin now
also hooks `MsgBox_DelayState` (`0x80150F3C`, the state-1 handler, second
entry in `mod_function_entry_funcs`): on entry, if base == cursor and both
point into the JP block, it is a fresh replay and the same lookup-and-copy
runs (`redirect_message`, shared with the reset hook); a `0x0B` prompt also
lands in state 1 but with the cursor past the base, so it is ignored; one
attempt per distinct base so a miss is hashed once, not per frame. The
replay does not eat a leading `0x0C` box-selector byte either, so the copy is
taken from the message start exactly as the game would read it.

Why this and not the framework's own text layer: `text_xlate`'s apply hook
scans `a0..a3` at dispatch for string pointers, and BoF3 never passes one
(the resolver stores into globals, 2026-09-05 trace). Its in-place message
patch would fit but transcodes to Shift-JIS with another title's framing.
The function-entry plugin is the framework's sanctioned title-side hook for
exactly this — no generated-code edit, no submodule change.

## Furigana (2026-09-12)

`tools/build_ruby_script.py` (defaults: furigana layout, every word) builds
`generated/bof3_xlate_jp_furigana.c`: readings in an 8 px row above each
text row instead of brackets, authored breaks kept, two text rows per
page. The only Japanese reading variant shipped since 2026-09-12; `--inline`
and `--scope area` rebuild the retired jp_ruby / jp_ruby_all / jp_furigana_area
tables, which are out of the language list and the plugin. Same plugin, same `MsgBox_Reset` repoint; the
plugin's row rule places the rows of a page that starts with `<0f><13>`
and draws the readings from the game's own 8 x 8 kana font by re-pointing
each reading quad on the packet-commit hook
([`FURIGANA.md`](FURIGANA.md) "The rendering route, reopened", "The 8 px
font"). No insert table for these codes: inserted names draw inline,
unread. Build order: `python tools/sync_small_font.py` after editing
`names/font_small.toml`, then the table, then the tree.

## One plugin, one table per language code

The plugin does not know what a table means. CMake globs
`generated/bof3_xlate_<code>.c` (`CONFIGURE_DEPENDS`, so a new table only
needs a build, not a reconfigure), defines `BOF3_XLATE_HAVE_<CODE>` on the
plugin source alone, and the plugin picks the table whose code equals the
resolved language string. Two exist today:

| code | built by | source | what changes |
|---|---|---|---|
| `en` | `tools/build_script_xlate.py` | the US disc, slot for slot | every translated slot, capitals, 16 cells |
| `jp_furigana` | `tools/build_ruby_script.py` | the JP disc itself | every kanji word read in an 8 px row above it, authored breaks kept, third rows split to a new page ([`FURIGANA.md`](FURIGANA.md)) |
| ~~`jp_ruby`~~, ~~`jp_ruby_all`~~ | `--inline` [`--scope area`] | the JP disc itself | retired 2026-09-12: `（reading）` inline, pages re-flowed |

Adding a code is three lines in the plugin (`BOF3_XLATE_DECLARE`, a
`BOF3_XLATE_TABLE` row) and one in `game.toml`. A code with no table (`jp`,
`off`) leaves every message alone. Symbols are
`bof3_xlate_<code>_{count,hash,off,len,blob}` (`src/bof3_xlate_table.h`).

## The English source — the US disc, slot for slot

Measured 2026-09-09 over both discs (`tools/build_script_xlate.py`):

| | JP (SLPS-00990) | US (SLUS-00422) |
|---|---|---|
| AREA files with a `0x80010000` section | 200 | 200 |
| slots per block (u16 table at +0) | 256 in every file | 256 in every file, **0 mismatches** |
| distinct messages | 6,696 | 6,352 |
| control codes used | `01 02 03 04 05 06 07 0A 0B 0C 0D 0E 0F 10 11 14 16` | the same set |
| total text bytes | 237,178 | 440,028 |

So the English for a JP message is the US message in the same slot of the
same file, control stream included. The US text is **not** ASCII: letters and
digits are, but the US font order puts `.` at `0x3E`, `,` at `0x3C`, `-` at
`0x3D`, `?` at `0x5C`, `!` at `0x5D`, `(`/`)` at `0x3A`/`0x3B`, `'` at
`0x8E`, `:` at `0x8F`, `"` at `0x90`, `&` at `0x8D`, and space at `0xFF`
(read off the script; the US sheet rendered through `tools/font_sheet.py`
confirms lowercase `a`–`z` sit on the sheet where the JP sheet has kana).
561 US slots still hold JP bytes (untranslated leftovers); those are skipped
and stay JP at runtime. 11,498 slots point at a string another slot already
covers (shared strings and suffixes); 691 of those carry *different* English
in different areas, and the first one seen wins.

### The choice menu, corrected

`0x14` is not a one-byte control. From the stepper (`MsgBox_Step`
decompile, `DAT_801490c0..c2`): `0x14 a b c` — `c0 = a`, the pointer
advances 3, `c2 = (c & 0xF) - 1` is the option count minus one, `c1 = c >> 4`
picks state 4 or 5 — and the options follow as **`c & 0xF` NUL-terminated
strings**. `a` is usually `0x00`, so `data.find(b'\0')` truncates every choice
message at its own argument. Both walkers here (`message_extent` in the tool,
`msg_extent` in the plugin) handle it; `tools/page_rows.py` does not yet, so
its census under-counts option glyphs.

### Encoding into the JP build

The JP sheet has `A`–`Z`, `0`–`9` and a handful of punctuation but **no
lowercase** ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "The single-byte codes"), and
it is full — 441 cells, the placeholder boxes are the only free ones — so
first light is **capitals**. The encoder (`tools/build_script_xlate.py`):

- carries every control through byte for byte, including the `0x0C nn`
  head, inserts `0x03/0x04/0x07`, colour, sound, pause, spans, flags, timed
  breaks and the whole `0x14` block;
- maps `"` to `「` (`0x2A`, the JP script's own opener, which hangs into the
  margin at line start exactly like the JP), runs of `.` to one `‥`
  (`0x3E`), `-` to `ー`, `:` to `・`, and **drops the apostrophe** (no glyph;
  see *Open*);
- treats US `0x01` newlines as soft, word-wraps each page to `--width`
  cells (default 16, the measured frame; the JP script never exceeds 15), and splits a page
  that needs more than `--rows` (3) rows with a `0x02` confirm break rather
  than printing a fourth row — the [`FURIGANA.md`](FURIGANA.md) policy;
- refuses anything over `--max-len` (2,040 bytes; the plugin slot is 2 KiB).

Output is `generated/bof3_xlate_en.c` — sorted hashes, offsets, lengths and
one blob — plus `--review` for a JP/EN side-by-side. It is **generated, not
committed**, like the game C: the English script is Capcom's and is built
from the player's own US dump. `CMakeLists.txt` compiles the plugin only when
the table exists, so a checkout without it builds exactly as before.

## Build recipe

```bash
export PATH="/c/msys64/mingw64/bin:$PATH"
# 1. the hook site (once; regenerates one shard, ~5 s)
python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc "isos/Breath of Fire III (Japan).cue"
# 2. the table (rerun after any encoder change)
python tools/build_script_xlate.py --bin-root D:\BoFIII\BIN \
    --us-cue "isos/Breath of Fire III (USA).cue" --review analysis/xlate_review.txt
# 3. the play tree
cmake --build build-relprof --target psx-runtime
```

Adding a hook address (either one) changes the **overlay config hash** (`mod_function_entry_funcs`
is an input to `overlay_codegen_config_hash`). That hash names the runtime's
*dynamic* shard cache directory; the static overlays compiled into the exe do
not carry it, and `compile_overlays.py --static --force` rewrote nothing
(content-identical), so no overlay recompile is needed. `tools/axis_b_loop.sh`
used to die on the unchanged mtime; fixed 2026-09-09 to accept an unchanged
file when the compile reported its shard result.

## Verification (2026-09-09, headless `build-relprof`)

`saves/openbios` slot 4 is not MacNeil village as the index said: the area
number at `0x80143F00` reads **150** and the 16 KiB at `0x80010000` is
byte-identical to `BIN/WORLD03/AREA150.EMI`'s script section (a desert
edge). Driven with `tools/scene.py`'s `Scene` over the debug port (Circle,
up, hold up, hold down puts the party on a talk trigger); frames are in
`analysis/xlate_shots/`.

| step | JP run (`PSX_LANG=jp`) | EN run |
|---|---|---|
| plugin log at boot | `registered at MsgBox_Reset (6721 table entries)` | same |
| first `MsgBox_Reset` | `ptr=800108C6, language other`, left alone | `ptr=800108C6, language en` then `hit #1 ptr=800108C6 -> 9F000000 (31 -> 70 bytes)` |
| `0x801490A8/AC` after the open | `800108C6/800108DE` | `9F000000/9F000034`, the stepper walking the English copy |
| on screen | 夜を待って‥砂漠に出ますか？ はい / いいえ | `DO YOU WANT TO WAIT / FOR NIGHT BEFORE / GOING INTO THE` then `DESERT?` then `YES / NO` (19-cell table; the first row overran the frame, see below) |
| choice handling | Circle x2 leaves state 5; Cross resolves (state 2) | identical: same states after the same presses |

The message is AREA150 slot 45 (`0x8C6`), a `0x14` choice prompt, so first
light exercised the selector-less head, word wrap, a page split (the English
needs four rows at either width, so the encoder spent a `0x02`), and the
re-encoded option strings. The English box behaves exactly as the JP box
under the same inputs, which is the equivalence the design promised.

Also measured, and corrected the same day: the frame in both captures runs
from x=59 to x=261, a **192 px interior = 16 cells** from the text origin at
x=69, and the window record's `+0x10` reads 16 in 12.4 fixed point (the raw
256 was first misread as pixels, which produced a 19-cell table whose first
row overran the frame by 29 px; the user caught it on the screenshot). So
`--width 16` is the default: the JP script's 15 was one cell inside the real
limit. Three rows is what the shipped script uses and nothing here changes
that.

**Japanese (Ruby), same evening, same drive, `PSX_LANG=jp_ruby`:** boot log
`2 table(s) / en: 6721 / jp_ruby: 5926`, `hit #1 ptr=800108C6 -> 9F000000
(31 -> 34 bytes)`, and the box shows 夜を待（ま）って‥砂漠に出ます / か？
with はい / いいえ, ink inside the frame. Only 待 carries a reading on that
line because 夜, 砂漠 and 出 were annotated earlier in AREA150 (first
occurrence per area).

Two harness lessons paid for on the way: the runtime's stdout is fully
buffered under the harness and a killed process drops it, so the plugin
flushes every line; and blind field navigation is flaky at 350 fps headless.
The first three attempts produced no message at all while `pad_status`
proved the override was applied, so sequence the walk with holds rather than
taps and check the message globals rather than the frame.

## Open

1. **Lowercase.** The honest options are (a) paint `a`–`z` over cells the
   area script never uses but menus do (the small-kana rows, the katakana
   block) via the framework's `[[vram_patch]]` layer while English is
   active, which breaks item names in menus; (b) a second sheet in free VRAM
   with a patched mapper (`Font_MapGlyph` `0x80151F4C` tpage/V bias for a new
   lead byte) — engine surgery under the enhancement gate; (c) live with
   capitals. Decide after seeing (c) on screen.
2. **Ruby readings are not proofread.** SudachiPy mode C over 11,070 words;
   `tools/build_ruby_script.py --review` writes the side-by-side to read,
   `--ambiguous FILE` the audit list of words the lexicon reads more than one
   way, and `names/readings.toml` fixes a choice (FURIGANA.md "Reading
   quality"). Tables are compiled into the plugin: a regenerated table needs
   `cmake --build build-relprof --target psx-runtime` and a relaunch, and the
   link fails with *Permission denied* while the game is running.
   Also the `(`/`)` cells are the sheet's ASCII parens, drawn full-cell; a
   thinner pair would save two cells per word if one is ever painted.
3. **Apostrophe.** One placeholder cell (`0x15 0x20`, an X box on the JP
   sheet) repainted through `[[vram_patch]]` would give `'` for one byte
   pair; the encoder drops it today.
3. ~~**Box width.**~~ Measured on screen: 192 px interior, **16 cells** at
   the +10 origin (above). A 16th glyph's cell touches the frame line; its
   ink (about 10 px) does not.
4. **Dropped apostrophes** make `DONT`, `ILL`, `SWEIRD` (for `'Sweird`);
   readable, not pretty. Item 2 covers the glyph.
5. **`tools/page_rows.py`** still walks `0x14` as a one-byte code, so its
   row/width census under-counts choice pages; port `message_extent` there.
6. **Savestates.** Enhancement memory is not in the savestate; a state saved
   mid-line and restored reads a zeroed slot, i.e. an empty line, and the
   next open is fine.
7. **Conflicting English** for a shared JP string (691 cases): key by
   (area, hash); the area number is `0x80143F00`, verified live today.
8. **Language readback.** The plugin reads the resolved language from
   `text_xlate_debug_json("stats")` because the module exposes no getter. A
   one-line upstream accessor would remove that; worth a small PR.
