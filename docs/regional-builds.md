# Regional builds — what the EU/FR/DE discs prove

**Status:** IN PROGRESS (established 2026-08-30)

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

`0x80010000` is replaced wholesale, and it is **the only section whose size
changes between languages**. `BIN/WORLD00/AREA013.EMI` is the clean case — 14
sections, thirteen byte-identical across all three languages, one differing:

```
index 11   dest 0x80010000   EN 7912  ->  FR 8085 (+173)  ->  DE 8412 (+500)
```

The small image deltas are localized tiles inside the texture atlas (signs and
similar); the tiny `0x800E4000` deltas are consistent with pointer fixups.

This is **independent confirmation, by a completely different method**, of the
static Ghidra finding in [`TEXT_ENGINE.md`](TEXT_ENGINE.md) that `0x80010000` is
the script buffer. Cross-language disc diffing and decompilation agree.

## Two consequences for the translation

1. **The script section is variable-size.** EN 7912 → DE 8412 in one area file,
   and German runs consistently longest. Capcom's own localizations grew this
   section freely, so a translation is **not** constrained to the JP byte budget
   — the container and its TOC absorb the change. This removes a constraint that
   would otherwise have shaped the whole approach.
2. **Only one section needs replacing.** Everything else in an area `.EMI` —
   audio, images, geometry — is untouched across languages. A translation is a
   `0x80010000`-section swap plus TOC size fixups, not a repack.

## Still open

- Whether the Western builds use **proportional glyph advance** or keep the JP
  fixed 12 px cell with narrower art. This is the one thing worth mining the US
  or EU EXE for, and it is now cheap: import `SLUS_004.22` as a second Ghidra
  program (Raw Binary, `MIPS:LE:32:default`, base `0x80096000`) and find its
  equivalent of `0x8015AD34`. Function addresses will not match JP.
- What `0x800D3800` is — 44% divergence in two of twelve files is unexplained.
