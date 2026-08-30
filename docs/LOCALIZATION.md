# Localization — JP→EN for SLPS-00990

**Status:** IN PROGRESS (last verified 2026-08-30, revised same day)

Scope: what it will actually take to run the Japanese release in English, and
whether the official US release (SLUS-00422) can supply the script. Companion
to [`BRINGUP.md`](BRINGUP.md).

Evidence for everything below is the 2026-08-30 capture run — `build-dbg`
(`PSX_DEBUG_TOOLS=ON`), `PSX_XLATE_CAPTURE=1`, software renderer, headless,
driven over the TCP debug server on port 4370.

## Headline

**A disc-derived translation is tractable, and most of the hard work already
exists.** The script is not in the boot EXE — it lives in per-area `.EMI`
container sections, which makes the EXE address mismatch irrelevant.

Established 2026-08-30:

1. Both discs carry **887 files with identical names** (only the boot EXE name
   differs) and identical directory structure.
2. The script sits in the `.EMI` section whose **destination is `0x80010000`**.
   This selector is unambiguous: across 880 `.EMI` files per disc, **200 have
   exactly one such section on both discs, and 0 are ambiguous**.
3. Prior decode work at `D:\BoFIII` already supplies the character table and an
   11,491-line slot-aligned JP/EN corpus. See §4.

Superseded: the earlier conclusion that the US release "cannot be reused" was
about *addresses* and remains true for addresses — but it is the wrong axis.
Alignment is by **filename → EMI section → slot index**, which is far stronger.

The two runtime-capture findings in §1 still stand and still matter, because the
runtime still has to *apply* the translation.

## 1. The capture pipeline

### It is not "always-on" — the docs are stale

`psxrecomp/docs/STRING_TRANSLATION.md` §0 describes the capture ring as
"always-on … no arm-then-capture". **That is no longer true of the code.**
`runtime/src/text_xlate.cpp:420`:

```cpp
std::atomic<bool> g_capture_on{false};    // inventory capture DEFAULT OFF:
    // the always-on Shift-JIS string-inventory scan costs 26-35% of
    // whole-lane throughput on streaming-heavy titles ...
    // PSX_XLATE_CAPTURE=1 re-enables the scan for translation authoring.
```

So `STATUS.md`'s previous plan — "capture runs unconditionally, so a soak builds
the string inventory" — would have silently collected nothing. Capture requires
`PSX_XLATE_CAPTURE=1` **and** a build with `PSX_DEBUG_TOOLS=ON` (see
[`BRINGUP.md`](BRINGUP.md) → Boot 002 for why the Release build sees nothing).

Doc drift belongs upstream in `mstan/psxrecomp`; recorded here as **F-3**.

### The chokepoint is real and hot

The hook is called from `psxrecomp/runtime/src/fntrace.c:174`, at the top of
each `psx_dispatch_impl` iteration. It is genuinely on the call chokepoint:

| Signal | Value |
|---|---|
| `xlate.calls` | 39,634,898 |
| `dispatch_stats.static_hits` | 30,377,466 |
| `dispatch_stats.miss_total` | 0 |

The earlier read that BoF3 "bypasses dispatch" (from heartbeat
`dispatch_count: 0`) was wrong — that counter tracks runtime *misses*, not
dispatch volume.

### What it captured: 3 false positives, 0 real strings

| hash | addr | pc | ra | len | payload |
|---|---|---|---|---|---|
| `91a95a3f…` | `0x0000166C` | `0xBFC060E4` | `0x8014AB20` | 8 | `701082ac7410828c` |
| `14f9f260…` | `0x000015E4` | `0xBFC060E4` | `0x8014AB20` | 8 | `701082ac7010828c` |
| `751c9d59…` | `0x000015D4` | `0xBFC060E4` | `0x8014AB20` | 8 | `741082ac7010828c` |

All three are spurious:

- `pc = 0xBFC060E4` is **BIOS** space, not game code.
- The addresses are low kernel RAM (`0x15D4`–`0x166C`), not text buffers.
- The payloads are **MIPS instructions**, not Shift-JIS. Little-endian
  `70 10 82 ac` = `0xAC821070` = `sw $v0,0x1070($a0)`; `8c 82 10 74` =
  `lw $v0,0x1074($a0)`.

The Shift-JIS validator is accepting kernel instruction words as text. This is
the same failure class as **F-2** in `BRINGUP.md` (instruction encodings taken
for addresses) and is recorded as **F-4**.

### Why no real strings yet

The intro prologue *does* render (Boot 002 screenshot), so text is being drawn
while capture was armed. The capture convention is "an argument register points
at a NUL-terminated string" — so BoF3 most likely does **not** pass `char*` per
draw call. The candidates, in order of likelihood:

1. Text is copied into a **message buffer** and drawn from there, so the pointer
   never appears in `a0`–`a3` at a dispatch boundary.
2. Glyphs are **blitted from a VRAM font atlas** — which is why the framework
   carries `vram_patches` / `msg_inplace` layers at all.
3. Script lives in **on-disc overlay/message files**, not the boot EXE.

Distinguishing these is the next concrete task, and it is a **text-draw PC
census**, not a translation-table task.

## 2. Can the official US script be reused?

**Not by address.** Both boot EXEs were probed directly from their PS-X EXE
headers on 2026-08-30:

| | JP (SLPS-00990) | US (SLUS-00422) |
|---|---|---|
| boot EXE | `SLPS_009.90`, 1,458,176 B | `SLUS_004.22`, 1,445,888 B |
| `load_address` | `0x80093800` | `0x80096800` (**+0x3000**) |
| `text_size` | `0x163800` | `0x160800` |
| `entry_pc` | `0x8014AA0C` | `0x8014AA0C` |
| first-pass JAL seeds | 523 | 526 |
| seeds at identical addresses | — | **24 (4.6%)** |

The matching `entry_pc` is a coincidence and a trap. With the load base shifted
by 0x3000, a different `.text` size, and only 4.6% of discovered call targets
landing on the same address, these are **separately-linked builds**. Nothing
can be lifted from US offsets onto JP offsets mechanically.

What the US disc *is* still good for:

- A **source of translated script text**, keyed by content//order rather than
  address, once the JP strings are enumerated.
- A **reference oracle** for how the English build lays out text (line widths,
  the ASCII font, name-entry limits) — BoF3's US release already solved the
  proportional-font and line-breaking problems that a JP→EN overlay hits.

**Revised by §4.** The alignment is *not* the bulk of the work, because it does
not happen at the address level at all: both discs share filenames, and the
script sits in a section identified by destination `0x80010000`, so JP and US
text align file-for-file and slot-for-slot. See §4.

## 4. The disc-derived path

### The `.EMI` container

Format per the community data doc
(<https://glitcheddragon-dev.github.io/BoF3-Data-Doc/DataStructures/1_TheEmiFiles.html>):

```
header (16 bytes)
    0x00 u32   entry count
    0x04 u32   version
    0x08 u8[8] magic "MATH_TBL"
TOC, count x 16 bytes
    0x00 u32   data size
    0x04 u32   RAM destination pointer
    0x08 u8[4] first 4 bytes of the section's data
    0x0C u16   type id   (0 misc, 3 image, 6 VH, 7 VB, 10 SEQ)
    0x0E u16   garbage
```

Section data starts at `0x800`, each padded to 2048:
`next = cur + ((size + 0x7FF) >> 0xB) * 0x800`.

The `u8[4]` preview is a free integrity check on that arithmetic —
`tools/emi.py list` verifies every section against it, so a wrong offset is
loud rather than silent. All 23 sections of `AREA030.EMI` verify.

### Locating the script

The text section is the TOC entry with **`dest == 0x80010000`**. Verified on the
full disc, both regions:

| Measure | Value |
|---|---|
| `.EMI` files parsed per disc | 880 (all `MATH_TBL`) |
| files with exactly one `0x80010000` section in **both** | **200** |
| files with none | 680 |
| ambiguous / multiple | **0** |
| text bytes JP → US | 562,543 → 852,489 (**+289,946**) |
| TOC index used | `{7: 2, 11: 194, 12: 1, 18: 3}` |

The index varies per area, so **select by destination, not by index**.

Sections 4 and 5 of an area (`0x801D0C00`, `0x800F5000`) also change size
between regions but profile identically in both — they are event/script
bytecode referencing the text, not the text itself.

Encoding profile of the `0x80010000` section in `AREA030.EMI`:

| | JP | US |
|---|---|---|
| printable ASCII | 29.3% | 68.7% |
| bytes >= 0x80 | 41.1% | 12.8% |
| ASCII runs >= 4 | 76 | 425 |

Japanese uses the game's own encoding (§4.2); English is plain ASCII in the
same slot structure.

### 4.2 Prior decode work — `D:\BoFIII`

Kevin's earlier sessions already solved the text encoding. Reuse, do not redo:

| Artifact | What it is |
|---|---|
| `bof3_character_table.json` | code → character, **435/435 complete** kanji table |
| `decode_text.py` | the decoder: kana single-byte `0x5B`–`0xFC`, kanji two-byte `0x12xx`/`0x13xx`, else control |
| `kana_table.py` | kana layout: hiragana `0x5B`, small `0x89`, dakuten `0x92`, katakana from `0xAB`; `ー=0xFC` |
| `_claude_work/pairs.json` | **11,491 slot-aligned JP/EN lines** across 197 blocks, 5,519 distinct JP strings |
| `_claude_work/corpus2_marked.txt` | per-EMI-entry dialogue extraction |
| `PIPELINE.md`, `HANDOFF.md` | the reasoning, and which approaches were measured and failed |

The text is **not Shift-JIS** — it is a custom table. Any Shift-JIS statistic in
an earlier revision of this document was coincidence.

Two caveats on `pairs.json`:

- Its `jp` field predates the completed character table (Aug 27 vs Aug 28), so
  every record still carries `[xxxx]` placeholders. Re-decode from the `.EMI`
  rather than trusting that field.
- Its block ids (`AREA000/AREA000.12.bin`) are **one-based** — `AREA030.19`
  is TOC index 18 in `tools/emi.py`. Confirmed on AREA004 and AREA030.

### 4.2b How the script reaches RAM (measured 2026-08-30)

A `wtrace` range on the text buffer (physical `0x00010000`–`0x00014000`, added
with `tools/playsession.py arm`) shows the script arriving by **CD-ROM DMA,
channel 3**, kicked from PC `0x80177B78`:

```
0x80177B6C: lui  $v1,0x8018
0x80177B70: lw   $v1,25600($v1)     ; -> [0x80186400] = DMA reg pointer
0x80177B78: sw   $v0,0($v1)         ; CHCR = 0x11000000
0x80177B88: lw   $v0,0($a0)         ; poll ...
0x80177B90: and  $v0,$v0,0x01000000 ; ... for the busy bit
```

Trace rows carry `dma_ch: 3`, so the bytes are DMA-delivered, not CPU stores —
the PC is the transfer *initiator*, not a `memcpy`. This confirms the loader
path but says nothing about the renderer.

**The write trace cannot find the text-draw PCs**, because those *read* the
buffer. `rtrace_*` is MMIO-only (`debug_server_trace_mmio_read`, called from
`memory.c`'s `mmio_read` wrappers), so it will not see RAM reads at
`0x80010000`. Finding the renderer needs a mechanism that does not exist yet —
that is the open tooling gap, not a data-collection gap.

### 4.3 What remains

The chain disc → aligned JP/EN is proven. What is not yet built:

1. **Slot splitting** inside a `0x80010000` section — how a block divides into
   the `i` indices `pairs.json` uses. This is the one mechanical gap.
2. **Keying for the runtime.** The framework table is keyed by a hash of the
   **raw JP source bytes**, so the emitter must hash the bytes as they sit in
   guest RAM, not decoded Unicode.
3. **Applying it** — blocked on §1's text-draw PC census, since the apply hook
   fires on dispatch and BoF3 does not pass `char*` at those boundaries.
4. **Font.** English needs the ASCII glyph set present; the US disc is the
   reference for line widths and breaking.

Item 3 is the real risk, not the script extraction.

## 3. The English scaffold

`BreathOfFire3EnglishRecomp/` was scaffolded 2026-08-30 from the USA dump via
`psxrecomp/tools/new_project_layout/setup_project.sh` (no generate, no build, no
GitHub). It probed cleanly: SLUS-00422, 2 tracks, 526 seeds, boot EXE extracted.

Two things about it need a deliberate decision before it is built:

- **Its `psxrecomp` gitlink floated to `master` HEAD (`47bda817`)**, while this
  repo is pinned at `f24b7e5d`. Root `CLAUDE.md` says never float on master.
  Results from the two repos are not comparable until the pins agree — decide
  whether to pin the English repo back to `f24b7e5d` or bump both.
- **`game.toml disc =` is an absolute machine-local path** into this repo's
  `isos/`. This repo already learned that lesson (2026-08-29 log entry). It
  needs a repo-relative path plus the dump moved into its own `isos/`, or it is
  not portable to another checkout.

## Next actions

1. **Text-draw PC census on the JP build.** Establish which PCs render the
   prologue text and how the string reaches them (buffer vs VRAM blit vs disc
   overlay). Everything else depends on this.
2. **Report F-3 and F-4 upstream** (stale "always-on" doc; Shift-JIS validator
   accepting kernel instruction words).
3. **Settle the English repo's submodule pin and disc path** before generating.
4. Only then author `translations/bof3.toml`.

## Framework observations (upstream, `mstan/psxrecomp`)

Continues the F-numbering from [`BRINGUP.md`](BRINGUP.md).

### F-3. `STRING_TRANSLATION.md` still claims capture is always-on

§0 and §1.1 both state capture is unconditional with "no arm-then-capture". The
code default flipped to off (`text_xlate.cpp:420`) for a documented 26–35%
throughput reason. Any title following the doc will soak and collect nothing.
Fix: correct the doc, or have `text_xlate_init` warn when a `[localization]`
block is configured while capture is off.

### F-4. Shift-JIS capture validator accepts MIPS instruction words

Evidence in §1 above: three inventory records whose payloads are `sw`/`lw`
encodings out of kernel RAM at a BIOS PC. The range check should reject
`pc` outside game text and addresses below the game's load address.
