# BoF3 text engine — the message interpreter, renderer and glyph path

**Status:** IN PROGRESS (established 2026-08-30)

This resolves the blocker recorded in [`HANDOFF.md`](HANDOFF.md): *"nothing can
identify which code draws text."* It is now identified. Three entry points, one
shared control-code vocabulary, one glyph blitter.

## How it was established

Ghidra 12.1.3, project `D:\Utilities\GhidraProjects\BoF3`, boot EXE
`SLPS_009.90` imported as **Raw Binary**, `MIPS:LE:32:default`, base
**`0x80093000`** (= `t_addr 0x80093800` − the 0x800 PS-EXE header, so the header
absorbs itself and every text address lands correctly). 1025 functions, seeded
from `analysis/functions.tsv`. Decompiler output, not speculation — each claim
below is readable in the listing at the address given.

The three PCs in the handoff's lead table were `lw` instructions *inside*
functions, not function entries. Resolving their containers is what cracked it.

## The three entry points

| Lead PC | Containing function | Role |
|---|---|---|
| `0x80150770` | **`0x80150598`** | Dialogue-box **renderer** — redraws the visible characters |
| `0x80150DB0` | **`0x8015096C`** | Dialogue-box **stepper** — advances one step, handles substitution state |
| `0x8015AE78` | **`0x8015AD34`** | **Immediate string draw** — `byte *draw(short x, short y, byte *str)` |

`0x8015AD34` has a clean recovered signature and returns the pointer just past
the terminator. It is the menu/immediate path; the other two are the
typewriter-style dialogue box, split renderer/stepper.

Callers: `0x80150598` ← `0x80150570`; `0x8015096C` ← `0x80149A5C`, `0x80150910`;
`0x8015AD34` ← `0x8015AB2C`, `0x8015AB94`.

## The message table — the answer to `0x80010004`

All three leads read the same word for the same reason. With
`W = *(u32 *)0x80010004`, control code **8** resolves a message by index:

```
base   = 0x80010000 + W
string = base + *(u16 *)(base + 2 * index)
```

So the word at `0x80010004` is an **offset from `0x80010000`** to a `u16`
message-offset table, indexed by the byte following control code 8. This is the
per-area script index that arrives by CD-ROM DMA — which is why the static scan
found only three references and no writes.

**This is the correct interception point for translation**, not the glyph
blitter: it is where a message number becomes a string pointer.

**Independently confirmed.** Diffing the same `.EMI` across the English, French
and German PAL releases shows the `0x80010000` section replaced wholesale (93.4%
of bytes) and it is the only section whose *size* changes between languages —
while audio, images and geometry stay byte-identical. Cross-language disc
diffing and static decompilation agree on what `0x80010000` is. See
[`regional-builds.md`](regional-builds.md). That work also shows Capcom's own
localizations **grew** this section freely, so a translation is not constrained
to the JP byte budget.

## Control codes

Shared by `0x80150598`, `0x8015096C` and `0x8015AD34`.

| Code | Meaning |
|---|---|
| `0x00` | terminator (or return from substitution) |
| `0x01` | newline — `y += 0x0E` (box) / `0x0D` (immediate), `x` = left margin |
| `0x03` | insert current-character name — record at `0x80144963 + 0xA4 * DAT_80145F05` |
| `0x04` | insert named character — record at `0x80144963 + 0xA4 * next_byte` |
| `0x05` | set colour/palette from next byte |
| `0x06` | reset colour |
| `0x07` | insert from 32-byte record table at `0x801490D3 + 0x20 * next_byte` |
| `0x08` | **insert message by index** — see the table formula above |
| `0x0B` | page break / prompt (`0x8015096C` sets state 1, `y += 8`) |
| `0x0D` / `0x0E` | enable / disable drawing |
| `0x12`, `0x13`, `0x15` | **multi-byte character lead bytes** — consume one extra byte |
| `0x2A` `'*'`, `0x3B` `';'` | at line start, `x -= 0x0C` (hanging punctuation) |

Substitution is a single-level return: the interpreter saves the resume pointer,
walks the inserted record for a fixed count (6 for names, 0x11 for messages,
0x21 for the 32-byte table), then restores.

Layout constants: **12 px** per glyph advance (`x += 0x0C`), **14 px** line
height in the box, 13 px in the immediate path.

## Glyph path

```
0x80150598 ─┬─► 0x8014F6BC(x, y, palette, 1, charptr) ──► 0x8014F708
0x8015AD34 ─┘
0x80150598 ───► 0x80151F4C(palette, charptr)      (the shadowed/boxed variant)
```

`0x8014F6BC` is a thin wrapper: it stores `x`/`y` into `0x80145AC6`/`0x80145AC8`
(note `y + 1`) and tail-calls `0x8014F708`.

`0x80151F4C` is the **font-atlas mapper** and the most useful function for font
work. It converts a character code into sprite UVs on a **21-glyph-wide**
(`0x15`) atlas of **12 px** (`0x0C`) cells. The multi-byte lead byte selects the
atlas page:

| Lead byte | Index bias | Atlas page |
|---|---|---|
| `0x13` | `+0x100` | second page |
| `0x15` | `+0x5B` | third page |
| `0xFF` | — | special-cased |

That `21 × 12px` cell geometry is the bridge to the 435-character table in
`D:\BoFIII` (see [`LOCALIZATION.md`](LOCALIZATION.md) §4.2): the table's ordinal
is this atlas index.

## Interpreter state block

A contiguous block of globals drives the dialogue box:

| Address | Role |
|---|---|
| `0x8014909C` | stepper result/state (1 = page break, 2 = end, 3 = code 2) |
| `0x801490A0` | flags — bit 0 = "inside substitution", bit 3 selects the blitter |
| `0x801490A3` | characters remaining in the current substitution |
| `0x801490A8` | string base for the renderer |
| `0x801490AC` | current pointer (stepper) |
| `0x801490B0` | saved resume pointer for substitution |
| `0x801490B4` | palette/font bank |
| `0x801490B5` | total characters to draw this frame |
| `0x801490B6`/`B7` | x/y draw offset |
| `0x801490B8`/`BA` | current cursor x/y |
| `0x801490BC`/`BE` | origin (margin) x/y |
| `0x80145F05` | current speaker/character index (for control code 3) |

## What this unblocks and what is still open

Unblocks [`LOCALIZATION.md`](LOCALIZATION.md) §4.3.

Still open, in order:

1. **Confirm the message-table formula against a live run.** The *location*
   `0x80010000` is now corroborated externally by cross-language `.EMI` diffing
   ([`regional-builds.md`](regional-builds.md)), but the `base + u16[2*index]`
   formula itself is still only static evidence. Break at `0x80150770`, read
   `*(u32 *)0x80010004`, walk the `u16` table and check the pointer lands on
   text that matches what is on screen.
2. **Variable-width text.** The advance is a hard-coded 12 px. English at fixed
   12 px will be unreadable at dialogue length, so proportional advance is a
   change to the interpreter, not just the data.
3. **Line-break policy.** Code `0x01` is explicit in the script, so JP line
   breaks are authored. English re-wrapping needs re-authored breaks or a
   word-wrap pass in the interpreter.
4. **Name these in `symbols.toml`** and re-run `tools/sync_symbols.py`.
