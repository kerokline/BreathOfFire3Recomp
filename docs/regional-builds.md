# Regional builds — what the EU/FR/DE discs prove

**Status:** IN PROGRESS (established 2026-08-30; extended the same day with a
complete JP-US section census - see *The complete census* below)

Five releases were compared: JP, US, and the three PAL SKUs. The question was
whether any Western release contains reusable multi-language machinery, and
whether the `.EMI` divergence confirms where the script lives.

## The releases

| Region | Serial | Publisher | Built |
|---|---|---|---|
| Japan | SLPS-00990 | Capcom | 1997-07-16 |
| USA | SLUS-00422 | Capcom | 1998-03-26 |
| Europe (English) | SLES-01304 | Infogrames Europe | 1998-07-23 |
| France | SLES-01319 | — | — |
| Germany | SLES-01320 | — | — |

Consecutive PAL serials, one language each. Product identity comes from the boot
filename and the ISO9660 primary volume descriptor; barcodes are packaging-side
and are not present in disc data.

## There is no runtime language support

Each disc carries **one** boot EXE, no language subdirectories, and no language
strings anywhere in the executable — the only ASCII in `SLES_013.04` is PSY-Q
library text (`CdlReadS`, `VSync: timeout`, `$Id: intr.c,v 1.74 ...`). No
`ENGLISH`/`FRANCAIS`/`DEUTSCH`, no `LANGUAGE`.

File counts: EU/FR/DE 889 each, US 887 — differing only by the PAL-only
`BIN/ETC/LOAD.EMI` and `BIN/ETC/WARNING.EMI`.

**Each language was a separate compiled build on its own SKU.** Nothing was
shared at runtime, so there is no in-engine language-switching path to borrow.

## The executables are not address-compatible

All Western EXEs are byte-identical in length (1,445,888) with the same
`t_addr 0x80096800`, `t_size 0x160800` and entry `0x8014AA0C`. JP differs only at
the front: `t_addr 0x80093800`, 0x3000 larger, **ending at the same
`0x801F7000`** — the image is anchored at its end.

That superficial similarity is misleading. Over the real code region
(`0x80146800`–`0x80196800`; everything outside it is zero-fill, so whole-file
byte-identity figures are meaningless) EU vs US is only ~21% word-identical.
The entry point shows why:

```
0x8014AA0C   EU  3C028019 2442B788 3C038019 24631130 ...
             US  3C028019 2442B2B8 3C038019 24630C60 ...
```

Same opcodes, relocated immediates — one codebase recompiled per release, with
every data address shifted. At `0x80150598` the two are unrelated code entirely.

This **confirms** the earlier finding recorded in [`LOCALIZATION.md`](LOCALIZATION.md)
that the US build is not address-compatible with JP (0x3000 shift, 4.6% seed
overlap). It extends it: EU and the FR/DE SKUs are no better. No Western EXE is
usable as an address-compatible donor.

## The `.EMI` divergence isolates the script — independent confirmation

Comparing the same `.EMI` file across EN/FR/DE, section by section, over a
sample of area files (EN vs DE, 12 files):

| Section dest | Type | % of bytes differing |
|---|---|---|
| **`0x80010000`** | misc/untyped | **93.4%** |
| `0x800D3800` | misc/untyped | 44.2% (2 files) |
| `0x800E4000` | misc/untyped | 2.2% |
| `0x0E001000` | image (256 KB) | 1.8% |
| `0x0A081000` | image (256 KB) | 0.4% |
| `0x801F2C00` | misc/untyped | 0.0% (3 bytes total) |

`0x80010000` is replaced wholesale, and among *area files compared between
Western languages* it is **the only section whose size changes**. That scoping
matters: the full JP-US census below finds 368 size changes, including a second
text pool that appears in no area file, and `0x800D3800` changing size in ten
area files. `BIN/WORLD00/AREA013.EMI` is the clean case — 14
sections, thirteen byte-identical across all three languages, one differing:

```
index 11   dest 0x80010000   EN 7912  ->  FR 8085 (+173)  ->  DE 8412 (+500)
```

The small image deltas are localized tiles inside the texture atlas (signs and
similar); the tiny `0x800E4000` deltas are consistent with pointer fixups.

This is **independent confirmation, by a completely different method**, of the
static Ghidra finding in [`TEXT_ENGINE.md`](TEXT_ENGINE.md) that `0x80010000` is
the script buffer. Cross-language disc diffing and decompilation agree.

## The complete census - all 6,344 sections, JP vs US

The section above sampled twelve area files EN vs DE. `tools/emi_survey.py` now
hashes **every** section on a disc (RAM-bound or not), so the comparison can be
exhaustive. JP vs US, both discs surveyed in full:

```bash
python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue" --out analysis/emi_sections.json
```

**6,344 sections on each disc, zero unique to either**, same `(file, index)`
keys throughout. The discs are the same build with different content in specific
sections.

| | count |
|---|---:|
| identical across regions | 5,372 (84.7%) |
| **differ** | **972 (15.3%)** |
| - type 0, size differs | 368 |
| - type 0, **same size, different bytes** | 502 |
| - type 3 (image), same size, different bytes | 37 |
| - type 8, same size, different bytes | 65 |

> **A size diff alone undercounts by more than half.** 502 type-0 sections and
> all 37 image differences keep their size and change their bytes. Any regional
> comparison must hash content, not compare sizes.

## Where the text is - and where it is not

### The boot EXE carries no regional text

Scanning both boot EXEs for word-like ASCII runs:

| | JP `SLPS_009.90` | US `SLUS_004.22` |
|---|---:|---:|
| word-like runs | **54** | **54** |
| density within span | 0.2% | 0.2% |

Identical counts and densities, spans differing only by the `0x3000` EXE-size
delta - the noise floor of the heuristic (file paths, BIOS strings), not
content. **Nothing requiring translation lives in the statically recompiled
program.** This is the result that makes the donor-disc approach viable: every
localized byte is in an `.EMI`, which is a file you read, not a program you run.

### Four text locations, all in `.EMI` files

Measured as word-like ASCII density, JP (encoded, so near-zero by construction)
against US:

| Location | JP | US | What it is |
|---|---:|---:|---|
| `0x80010000` | 9.9% | **54.7%** | area dialogue script, per area file |
| `0x8001A000` (US) / `0x80014000` (JP) | 5.1-5.4% | **51-66%** | items, skills, battle commands, menu labels |
| `GAME.EMI` section 0, offset ~`0x32430` | 0.4% | **19.9%** | a string table *inside* a code section |
| `STATUS` / `SHOP` section 0 | 0.1% | 0.4% | noise - **no** string table |

Two of these are new relative to the area-file sample above:

- **The second pool** is a shared ~14-17 KB blob duplicated into `BIN/BATTLE`
  (2), `BIN/BOSS` (40) and `BIN/ETC` (2 - `FIRST.EMI`, `AFLDKWA.EMI`). It is
  pure data, and it is where battle options and menu/item names live. The
  area-file sample never contained it, because it appears in no area file.
- **`GAME.EMI` section 0 contains a string table**, but the strings are *not*
  interleaved with instructions: all 505 word-like runs sit in one contiguous
  ~15 KB window (6.7% of the 230 KB section) at 19.9% density, and the JP
  equivalent begins at `0x03242C` against the US `0x032434` - **eight bytes
  apart**. It is a data region that happens to live inside a code section, and
  it is localizable as data.

Menu *code* (`STATUS`, `SHOP` at `0x801D0C00`) carries no table: its word-like
runs stay at 0.1-0.4% density spread across 99% of the section, which is noise.

### `0x800E4000` is not text

106 of ~200 of these 1,160-byte sections differ JP-US at identical size, which
looks suspicious. It is a bitmask: **94.5% zero bytes, 5.5% `0xFF`, and zero
word-like runs in either region**. Whatever it encodes (collision, visibility,
event flags), it is not a text pool. The earlier note that its deltas are
"consistent with pointer fixups" is not supported by the byte composition.

## Language-bearing artwork - exactly 37 sections

The 37 image sections that change content at identical size were hashed across
all five releases. **36 of 37 give the identical pattern `A B B C D`**: JP one
image, US and EU sharing a second, France a third, Germany a fourth. Four
distinct images across five releases, with the two English SKUs sharing - the
unambiguous signature of art that carries language.

| VRAM dest | Size | Count | What |
|---|---:|---:|---|
| `0x1C080200` | 32 KB | 17 | the glyph atlas, duplicated into every module that draws menus (`BATE`, `COMMU*`, `FIRST`, `SHISU`, `SHOP`, `SISYOU`, `START`, `STATUS`) plus 3 area files |
| `0x1E000200` | 32 KB | 2 | `ENDKANJI.EMI` section 0 and `FIRST.EMI` section 3 - the ending/kanji font |
| `0x0E001000` | 256 KB | 10 | area textures, paired with the next row |
| `0x0A081000` | 256 KB | 11 | area textures - 11 areas across `WORLD00`-`WORLD04` |
| `0x1A080400` | 64 KB | 1 | `DEMO.EMI` section 5 - **the one anomaly**, pattern `A B A C D`: EU matches *JP*, not US |

So a JP-EN build needs an English glyph atlas regardless (the font is a
texture, not code), and ~11 areas have art with text baked in. That is an art
task, not a substitution task - but the list is short, enumerable, and every
one of those sections is readable from a donor disc.

`DEMO.EMI` section 5 is unexplained: the PAL English release ships the Japanese
asset where the US release ships its own. Flagged, not diagnosed.

## Destinations shift between regions - select carefully

1,096 sections land at a different RAM address on the US disc. The shifts are
systematic, not random:

| JP | US | Delta | Sections |
|---|---|---:|---:|
| `0x8002BE00` | `0x80033E00` | +0x8000 | 201 |
| `0x8002D800` | `0x80035800` | +0x8000 | 200 |
| `0x8002A000` | `0x80032000` | +0x8000 | 200 |
| `0x80014000` | `0x8001A000` | +0x6000 | 44 |
| `0x80093800` | `0x80096800` | +0x3000 | 42 |

The `0x3000` on the battle-engine band is exactly the boot-EXE load-address
delta. **`0x80010000` (the area script) is the notable exception - it does not
move in any of the five releases.**

The existing rule "select by destination, never by index" therefore needs a
companion: *destinations are themselves region-specific*. Select by destination
within a region, and map destinations across regions.

## Two consequences for the translation

1. **The script section is variable-size.** EN 7912 → DE 8412 in one area file,
   and German runs consistently longest. Capcom's own localizations grew this
   section freely, so a translation is **not** constrained to the JP byte budget
   — the container and its TOC absorb the change. This removes a constraint that
   would otherwise have shaped the whole approach.
2. **Only one section needs replacing *in an area file*.** Everything else in
   an area `.EMI` — audio, geometry, and all but a handful of images — is
   untouched across languages, so per-area work is a `0x80010000`-section swap
   plus TOC size fixups, not a repack.

   The **whole** translation surface is wider than that, and the census above
   enumerates it: the area script, the second pool at `0x80014000` (JP) /
   `0x8001A000` (US) carrying items, skills, battle commands and menu labels,
   a ~15 KB string table inside `GAME.EMI` section 0, and 37 image sections that
   carry language — the glyph atlas plus baked-in art text in about eleven
   areas. Four text locations and one art task. **None of it is in the boot
   EXE**, which is the finding that keeps the whole approach viable.

## Still open

- **`DEMO.EMI` section 5** ships the JP image on the PAL English disc but a
  distinct one on the US disc (pattern `A B A C D`, the only section of 37 that
  breaks the language pattern). Unexplained.
- **Whether the `GAME.EMI` section 0 string table needs translating at all**, or
  is debug/internal. It is ~15 KB and 505 word-like runs in the US build; nobody
  has read what it contains.
- Whether the Western builds use **proportional glyph advance** or keep the JP
  fixed 12 px cell with narrower art. This is the one thing worth mining the US
  or EU EXE for, and it is now cheap: import `SLUS_004.22` as a second Ghidra
  program (Raw Binary, `MIPS:LE:32:default`, base `0x80096000`) and find its
  equivalent of `0x8015AD34`. Function addresses will not match JP.
- What `0x800D3800` is - 44% divergence in two of twelve files is unexplained,
  and the full census shows it changing *size* in ten area files, so it
  is not a fixed-layout table.
