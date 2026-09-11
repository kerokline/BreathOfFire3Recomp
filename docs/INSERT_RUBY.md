# Readings on inserted names — built (2026-09-10)

**Status:** DONE — **user-verified in play 2026-09-11**: a real item pickup
and a master's skill line both draw with readings under *Japanese (Ruby)*,
so record 0 *and* record 1 are rewritten before the box reads them (the
record-1 fallback below was not needed). Designed in the
morning, the two open checks answered from the disassembly instead of a live
print, implemented, linked into `build-relprof` and exercised over the debug
port the same day.

## The problem

The Ruby tables re-author *messages*. An item, skill or zenny amount is not
in the message: the box shows `<07><nn>` and the stepper fetches the name
at draw time from a scratch record the caller filled. So
`シェザーガ を教（おし）えてもらった！` reads the verb but not the skill,
and every pickup line (`<07><00> を手に入れた`, system block slot 2) shows
the item bare. 75 of 311 item names and 35 of 227 ability names contain
kanji; place names are all katakana.

## How the insert works (stepper `MsgBox_Step` `0x8015096C`, decompiled)

```
case 0x07:  b0  = ac + 1                       // saved resume pointer (the index byte)
            a0 |= 1                            // "inside substitution"
            a3  = 0x21                         // 33 steps at most
            ac  = 0x801490D3 + *b0 * 0x20      // the record, one BEFORE the data
            ...                                // every iteration ends with ac++
case 0x00:  if (a0 & 1) { ac = b0; a0 &= ~1 }  // return to the message (ac++ skips the index byte)
```

(`ac` = `0x801490AC` current pointer, `b0` = `0x801490B0`, `a0` = flags
`0x801490A0`, `a3` = `0x801490A3` remaining steps.) The loop post-increments
`ac` at the end of every iteration, so the first byte drawn is
**`0x801490D4 + 0x20 * nn`** and the "`0x801490D3`" in the decompile is the
pre-increment form, not a colour byte (the `0x03`/`0x04` character insert
has the same shape: `0x80144963 + roster * 0xA4`, one before the name at
`+0` of the character record). `a3` is decremented before each read, so a
record is drawn to its NUL or to 32 bytes, whichever comes first. A record
is an ordinary glyph string drawn by the same stepper as the message: kana,
parens and kanji in it render exactly like message text. The other inserts
differ: `0x03` / `0x04` read six glyphs from the character record (katakana
names, fixed length — left alone), `0x08` reads a sub-message from the area
table (17 steps).

### Who fills record 0, and when — the two open checks, answered

Every writer of the record base in GAME.EMI (`tools/disasm_exe.py --exe
<section> --load 0x80196800`, immediate scan for `0x90D4`/`-28460`):

| site | what it writes to `0x801490D4` | then |
|---|---|---|
| `0x801B4094` (search-spot item branch, inside `Field_SearchSpot`) | 8 bytes from `Item_NamePtr(cat, id)` `0x80166720`, then `sb $zr` at `0x801490DC` | `Inventory_Add`, cue `0x106`, `Msg_OpenSystem(2)` |
| `0x801B3870` (a second item-award path, same shape) | same 8-byte copy + NUL at `+8` | `Inventory_Add` |
| `Field_GiveZenny` `0x801B6E50` | `sprintf(fmt 0x80196FBC, amount)` | `Msg_OpenSystem(5)` |
| `0x801AD93C` / `0x801AD9D0` | `sprintf(fmt 0x80196F0C, 2 / 5)` | `Msg_OpenSystem(5)` |
| `0x801A8C58` (key item, `FUN_801a93e4`) | `memcpy(Msg_SystemPtr(id + 0x4172), 8)` | `Msg_OpenSystem(0xFA)` |
| BATL_END `BattleResult_Setup` | `sprintf` of the zenny total | `Msg_SystemPtr(5)` |

So: **(1) the record is filled before `MsgBox_Reset` fires** — every site
writes it and then opens the message; **(2) it starts with the name, no
leading byte** — the copy targets `0x801490D4`, which is the stepper's
first read. The item copy is 8 bytes + a NUL at `+8`, so a record holds the
table's `name[8]` up to its first NUL (103 of the 538 names fill all 8
bytes and rely on that NUL). Records 1+ (`<0701>` in the skill-learned
lines, AREA061 slot 14: `<0502><0701><06> を教えて`) are filled by the area
script before it opens the message; no immediate-form writer exists for
them, so the copy goes through a computed pointer — the plugin handles them
the same way and the on-screen check covers that path.

## What was built

Three parts, all on the title side (no framework change):

1. **A second generated table**, `generated/bof3_insert_<code>.c`, emitted
   by `tools/build_ruby_script.py` alongside the message table for each
   Ruby scope (`insert_entries()`): FNV-1a64 of the record's bytes — the
   raw `name[8]` field of the five item tables and the ability table
   (`text_tables.scan_records`), cut at the first NUL, exactly what the
   stepper reads — → the same name annotated by the `Annotator`
   (`annotate_name()`, every kanji word read, same kana codes and `( )`
   brackets). 109 names change (75 item + 35 ability, one duplicate); a
   name that would exceed 16 cells or 31 bytes is left unannotated (none
   does; the widest is 強化（きょうか）薬草（やくそう） at 16 cells). The
   symbols are `bof3_insert_<code>_*` through the same `emit_c`
   (`prefix="bof3_insert"`), declared by `BOF3_INSERT_DECLARE` in
   `src/bof3_xlate_table.h`; CMake globs the files and defines
   `BOF3_INSERT_HAVE_<CODE>`. `--insert-review FILE` writes the
   name → annotated list for proofreading.
2. **Plugin**, `src/bof3_localize.c`: `msg_extent()` now records the `nn`
   of every `<07><nn>` it walks (it already knows which `0x07` is a control
   and which is the second byte of a kanji pair), and `apply_inserts()`
   runs before the message lookup — on the miss path too, since a message
   with no kanji of its own still carries the insert. Per distinct record:
   read `0x801490D4 + 0x20*nn` to its NUL (no NUL in 32 = not a name,
   skip), hash, look up in the active language's insert table, and on a
   hit write the annotated bytes + NUL back with `psx_mod_write_byte`
   (≤ 31 bytes). This is the plugin's first write into guest RAM: the
   stepper's own scratch for the message being opened, not game state,
   and only while a language with an insert table is active. Idempotent:
   the annotated bytes hash to nothing, so a re-open on the same record
   leaves it alone. Zenny digits miss and pass through.
3. **Width budget**: `Annotator(insert_width={0x07: 16})` — the budget is
   now a per-annotator parameter (`--insert-width`, default 16 for the Ruby
   scopes) instead of the module-global `INSERT_WIDTH` (which keeps 8 for
   the English table). Messages carrying `<07>` re-flow so a row holding
   an annotated name holds only the name. Cost: pages split for a fourth
   row 554 → 640 (first-per-area) and 1,471 → 1,642 (every word); tables
   5,910 / 6,155 entries.

   **Trap paid for:** the narration check (`is_box_page`, "a page authored
   wider than the box is the full-screen path, leave it verbatim") measured
   inserts with the same 16-cell budget, so every authored row holding an
   item name overran 16 and the whole message was misfiled as narration —
   no readings at all on exactly the lines this work targets (the synthetic
   pickup below missed the message table on its first run). The check now
   measures the shipped layout with the shipped widths (`INSERT_WIDTH`);
   narration pages 276 → 170, i.e. 106 insert-bearing pages had been left
   verbatim, some of them since the 2026-09-10 morning `INSERT_WIDTH` change.

## Verified on a live guest (2026-09-10 midday)

`analysis/insert_test.py`-style drive over the debug port (the script lives
in the session scratchpad; the recipe is what matters): `tools/scene.py`'s
`Scene` loads savestate slot 0 (AREA004, field, `jp_ruby_all` from
`settings.toml`), `write_ram` points every entry of the area's message
offset table at a copy of system slot 2 (`07 00 ff 87 12 66 70 12 03 84 6a
00`, `<0700> を手に入れた`) written over message 0, pre-fills record 0 with
薬草's table bytes `13 1a 12 8b 00`, and presses Circle. Result:

```
bof3_localize:   jp_ruby: 109 insert names
bof3_localize:   jp_ruby_all: 109 insert names
bof3_localize: insert hit #1 rec=0 at 801490D4 (4 -> 10 bytes)
bof3_localize: hit #3 ptr=80010200 -> 9F001000 (12 -> 18 bytes)
record0 now: 131a128b287e62695d29  薬草(やくそう)
```

and the box draws 薬草（やくそう） on its own row, then を手（て）に入（い）れた
(`analysis/xlate_shots/insert_pickup_synthetic.png`, mid-typewriter). A
second and third open of the same message logged `insert miss` on the
already-annotated record and left it alone — the idempotence the design
asked for.

Readings the review exposed and fixed in `names/readings.toml` (a bare
name gives the tokenizer no context): 光合成 (光 + 合成, `next` rule 光 = こう),
さかなのお頭 (one token お頭 = オツム → おかしら), とっこう薬 (薬 = やく after
とっこう), 気つけ薬 (薬 = ぐすり after 気つけ). Left as the dictionary reads
them, for the proofreading pass: 知力の研 / 木の研 (研 = けん), 土器
(かわらけ), 夢氷撃 (ゆめ・こおり・げき), 神風だま (かみ・かぜ).

## Verify in play — done 2026-09-11 (user, real play)

Both cases below were confirmed on `build-relprof`; the text that follows is
the original check, kept for the fallback it describes.

With *Japanese (Ruby)* selected in the launcher, search a chest or shelf
that gives a kanji item — 薬草 is the commonest — and expect the synthetic
result above on a real pickup; then a master's skill line with a kanji
skill name (会心撃 → 会心（かいしん）撃（げき）) in a 16-cell row of its own.
The plugin prints `insert hit #n rec=N at ... (m -> k bytes)` on stdout for
the first five, and `insert miss` lines for records that did not match (a
zenny amount, or a record already rewritten, is an expected miss). If the
skill line shows the bare name while the pickup reads, record 1 is filled
*after* the open and the write-back for records 1+ has to move to the
stepper's first step (`mod_function_entry_funcs` takes more than one PC).

## What this does not cover

- Character names (`0x03` / `0x04`): fixed six glyphs from the character
  record, katakana — nothing to read.
- Menu item lists, shop lists, the status screen: drawn by `Msg_SystemPtr`
  readers, never through the box; a separate track (menus wait, by decision).
- Numbers: no kanji.
