# Loader records — the engine's own entry points into every overlay family

**Status:** STABLE (found 2026-09-12; all four tables proven statically with 0
counter-examples; seeded into the extractor by default the same day — see
*Seeding* — and compiled into `build-relprof`). Evidence: the four research
reports in [`loader_records/`](loader_records/) (one per family, with the
disassembly), `tools/loader_records.py` (reproduces every number here off
`disc/SLPS_009.90` and `analysis/overlay_captures_all.json`), and the
`names/*_records.toml` sidecars it writes.

## Why this exists

The Axis B loop harvests interior entry points from play because the static
walk cannot see them: an overlay function reached only through `jalr` has no
JAL edge, is often a leaf without a stack frame, and the overlay header's
entry run (seeded since 2026-09-08) turned out to be something the *overlay's
own* code consumes, not the path the engine takes in. The question on
2026-09-11 was what play actually discovers that the disc does not hold. The
answer for every overlay family is: nothing. The engine keeps a record of
where it enters each image, and that record is in the disc bytes.

The spell path had already shown the shape (`Magic_EffectTable`: file id plus
handler pc, [`OVERLAY_HEADERS.md`](OVERLAY_HEADERS.md) "The loader"). The four
reports found the analogue for every other family in one pass.

## The four tables

| family | keyed by | file id | entry pc(s) | verified |
|---|---|---|---|---|
| **AREA** (200, band `0x801F2C00`) | area number `u16[0x80143F00]` | `area + 0x2AB` at GAME.EMI `0x801A0BB0` | boot table `0x801802EC[area]` → a 0x44-byte descriptor at the *end* of the area's section; `+0x40` init pc (called once after load, may be 0), `+0x3C` → array of native handlers bounded by the descriptor (script opcodes `0x03`/`0xDE`, entity dispatch `0x801ADE10`) | 200/200 pointers in-section, 67/67 init, 671/671 handlers |
| AREA hook rows (11 areas) | area number matched at `+0x18` | — | GAME.EMI `0x801C8F54`, 11 × 0x1C: six pcs per row (`Area_HookRow 0x8019B19C`), plus a parallel `u32[11]` at `0x801C95BC` | 63/63 + 11/11 |
| **SCENARIO** (20 chapters, `0x801F6C00`) | chapter `s8[0x8014686C]` | `chapter + 0x295` at GAME.EMI `0x801A881C` | GAME.EMI `0x801C944C[chapter]` → a 5-slot vtable inside the image (thunks `0x801A8834/8880/891C/89AC/8A3C`, slot 4 optional); two more tables `0x801CDC4C`/`0x801CDC9C` → arrays of pcs the scenario's own code calls through `Scenario_CallA/B 0x801C2DE8/0x801C2E34` | 20/20 records, 89/89 slots, 159 + 52 sub-table pcs, 0 invalid |
| **BOSS** (55 ids, 40 files, `0x800C1800`) | boss id `u8[0x801462E6]` (set by `Battle_StartBoss 0x801C8A4C`, 49 immediate callers in SCENA00..15) | row `u8[0x801CDF18 + id*4 + 3]`, file `u16[0x801CDFF8 + row*2]` | battle engine `0x800B2048[id]`, called by `jalr` at `0x800A8B40` | 55/55 in-section, 41/41 file ids resolve |
| **PLCHAR** (19 combos, `0x801CE400`) | party combo index `u8[0x80145020] & 0x7F`, rows of the combo table `0x801824AC` (3 char ids each) | `0x27D + combo` at boot `0x80167CA4` (the only loader for all four PL families) | GAME.EMI `0x801CD8F0[combo]` (jalr `0x801B46B0`) and `0x801CD964[combo]` (jalr `0x801B3C78`, `0x801BE508`); both are thunks into the image's last six words, a `u32[2][3]` per-party-slot dispatch | 19/19 + 19/19; thunk shape 19/19 |

Two negatives worth keeping: **no script opcode requests a scenario** (all 65
`File_LoadRequest` sites game-wide were constant-propagated), and **no
per-character function table into the PLCHAR band exists** anywhere in the
boot EXE or GAME.EMI. `ENEMY<nnn>.EMI` (`area + 9`) is pure VRAM data with no
code and is skipped for bosses.

## What the records are worth

`tools/loader_records.py` → 1,267 rows, joined to the captures by section md5
alongside the 131 magic handler pcs:

| sidecar | rows | distinct (section, pc) |
|---|---:|---:|
| `names/area_records.toml` | 812 | 812 (146 areas; 18 areas have a data-classed section and no capture, the 3 world-map areas are skipped) |
| `names/scenario_records.toml` | 300 | 248 |
| `names/boss_records.toml` | 55 | 55 |
| `names/plchar_records.toml` | 152 | 152 |
| `names/magic.toml` | 222 | 131 |

Against the capture set built the same morning (observed set + header seeds +
magic seeds), **914 pcs were in no seed set at all**: 553 in the AREA band,
232 SCENARIO, 100 PLCHAR, 29 BOSS. For scale, every play session since
2026-08-31 had contributed about 1,080 *entered* pcs in total. The header
entry tables and these records are disjoint (intersection 0 for AREA, 0 for
SCENARIO).

## Seeding

`tools/extract_overlays.py` reads `ENGINE_RECORD_FILES` (the five sidecars),
keeps a row's pc only if it is 4-aligned and inside the section the row names,
and unions it into `dispatch_entry_pcs` / `static_dispatch_entry_pcs` like the
header run, so `compile_overlays.py` classifies them `STATIC_DISPATCH_ENTRY`.
`--no-engine-seeds` drops them for A/B work. Nothing is fabricated: every pc is
a word read out of the disc, inside the image it belongs to, and the compile's
own callable check still applies.

Rebuild recipe: `python tools/loader_records.py` (only after a change to the
table addresses or a new capture set), then the normal loop
`tools/axis_b_loop.sh --skip-harvest --force`.

## RAM cells the reports settled

| cell | meaning | corrects |
|---|---|---|
| `0x801462E6` | boss id, 0 = random encounter | BATTLE_RAM "boss flag" |
| `0x80145020` | PLCHAR residency: `& 0x7F` combo index 0..18, bit 7 = the `PL` family is resident, `0xFF` none | BATTLE_RAM "form byte" |
| `0x8014686C` | scenario chapter (s8); `+1` flags (`0x80` = advance requested); `0x80146868` → progress record `0x80144E84 + n*8` | the unlabelled block-head words in BATTLE_RAM / HANDOFF row 9 |
| `0x80143F10..1C` | pending area / x,z / y / flags stashed by `Field_ChangeArea 0x801A0A30` | — |
| `0x80182830` | BGM table, stride 4 (`u16` file id, seq, sub), indexed by `u8[0x80145025]` | — |

A boss dialer harness needs only the setter's writes (boss id, `0x80145E8D = 5`,
`0x80146316 |= 0x1000`, flags from the record) — but the record also indexes
the *current area's* formation table at `0x800E4000`, so dial from the area
that normally triggers the fight.

## Open

- Runtime proof that the new entries dispatch natively: a first visit to an
  unplayed area, a boss, or a party change on the rebuilt exe, then
  `harvest_interp_pcs.py` should report far fewer interior entries.
- The 18 areas whose `0x801F2C00` section is classed `data` (6, 9, 17, 31, 66,
  70, 83, 89, 101, 122, 126, 129, 137, 138, 159, 190, 194, 195) and the
  world-map descriptor type (areas 30/89/129).
- The longer tail-pointer run in each PLP image (11..25 words above the six
  seeded ones) and the ~dozen unattributed pointer runs in GAME.EMI
  `0x801C8C80..0x801C9700`, some of which are probably more area-keyed hooks.
- Names: the reports list candidate `symbols.toml` / `names/` rows
  (`PLCHAR_*`, `Boss_*`, `Scenario_*`, `Area_Hook*`); not applied yet.
