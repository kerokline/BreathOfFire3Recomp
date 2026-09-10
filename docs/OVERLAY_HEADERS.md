# Overlay headers — the registry id and the entry-pointer table

**Status:** STABLE (established 2026-09-08; the id census covers all 405
compiled EMI overlays; the entry table is **seeded into the extractor by
default** and A/B-measured the same day — see *Seeding the extractor*; the
ability→overlay link is **found, read off the disc and verified live** — see
*The loader and the spell→overlay link*; what is left is in *Open*). Evidence: the compiled
captures in `analysis/overlay_captures_all.json`, read directly;
`analysis/interp_bench_header.jsonl` for the A/B; `names/magic.toml` for the
link.

## The header

Every overlay section in the compiled bands opens with the same two-part
header, ahead of its first function:

```
+0x00  u32     registry id      unique per overlay, contiguous per category
+0x04  u32[]   entry pointers   variable length, 0..59 entries, into this image
       ...     code
```

The pointer run is found by reading words from `+0x04` until one is not a
4-byte-aligned address inside the image. Across the 124 `BMAGIC` overlays:

| pointers | 0 | 3 | 4 | 5 | 6 | 8 | 9 | 13 | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| images | 32 | 21 | 11 | 10 | 8 | 8 | 15 | 4 | 15 |

32 images have no table at all — their code starts at `+0x04`.

## The registry id is one global id space

The word at `+0x00` is **unique across all 405 compiled EMI overlays — 405
distinct ids, zero duplicates** — in the dense range `0x010..0x1BF` (432 slots,
27 unused). Ids are assigned in blocks that broadly follow the directory, and
several blocks are exactly contiguous:

| directory | overlays | id range | contiguous | band |
|---|---:|---|---|---|
| `BIN/BATTLE` | 4 | `0x010..0x143` | no | `0x801D0C00` |
| `BIN/ETC` | 14 | `0x012..0x141` | no | `0x801D0C00` |
| `BIN/WORLD00` | 35 | `0x016..0x059` | no | `0x801D0C00` |
| `BIN/PLCHAR` | 19 | `0x021..0x033` | **yes** | `0x801CE400` |
| `BIN/WORLD01` | 37 | `0x05A..0x104` | no | `0x801F2C00` |
| `BIN/WORLD02` | 35 | `0x080..0x0A5` | no | `0x801F2C00` |
| `BIN/WORLD03` | 33 | `0x0A6..0x0CB` | no | `0x801F2C00` |
| `BIN/WORLD04` | 44 | `0x0CC..0x0FB` | no | `0x801F2C00` |
| `BIN/SCENARIO` | 25 | `0x105..0x11D` | **yes** | `0x801F6C00` |
| `BIN/BOSS` | 35 | `0x11E..0x140` | **yes** | `0x800C1800` |
| `BIN/BMAGIC` | 124 | `0x144..0x1BF` | **yes** | `0x801EEC00` |

The id space is global, not per-directory: the small `BATTLE` and `ETC` sets
are scattered across it, and the `WORLD01..04` ranges interleave without ever
colliding. Zero duplicates across 405 overlays is the load-bearing fact — this
is a registry, and the id is an overlay's identity.

**It is not derivable from the filename.** `MAGIC001` = `0x144`, `002` =
`0x145`, `003` = `0x146` — but `MAGIC008` = `0x14F`, out of run. The header is
therefore the authoritative overlay→id mapping and has to be read, not computed.

**Exception:** `LOGO/LOGO.EXE` has no such header — its first word is
`0x6E795356` (`"VSyn"` in ASCII), because it is a PS-EXE compiled as an overlay
(`tools/extract_logo_overlay.py`), not an `.EMI` section.

## Why this matters

It explains a long-standing confusion in the `0x801EEC00` band. The address
`0x801EEC10` is *inside the pointer table* for most MAGIC images, *already
code* for the 20 with short tables, and for `MAGIC002` — which has a 3-entry
table — it is 8 bytes of something else between the table and the code at
`+0x18`. That is the "data pad" rejection in [`DATA_ISLANDS.md`](DATA_ISLANDS.md),
now explained structurally rather than by byte heuristics.

`MAGIC002`'s `c3 f6 c3 f6 c3 f6 00 00` is unique across all 124 images. Three
identical halfwords after a three-entry pointer table is suggestive of a
parallel per-entry array, but with one instance there is nothing to compare
against and it is **not** identified.

## Where the id and the table now live

- `analysis/overlay_captures_all.json` — every capture carries `registry_id`
  and `header_entry_pcs` (`tools/extract_overlays.py`).
- `analysis/overlay_catalog.json` — `registry_id`, and `roots.header_entries`
  beside `roots.observed_entries` (which now counts harvested PCs only).
- `names/overlays.toml` — every row has `id = "0x144"` style, seeded by
  `name_map.py init`; `load_overlay_ids()` returns id → row for tools that
  want to key by the game's own identity. LOGO.EXE has no `id` (no header).

## The id as the residency signal (2026-09-08)

`CD_getsector` writes the header word with the section's first sector, so
one u32 read per band base names the occupant — no hashing, and immune to a
previous larger occupant's stale tail. `tools/resident.py` does the reads,
validates every word against the 405 known ids (a band base is not always an
overlay: `0x800C1800` is the memory-card staging buffer during a save, LOGO.EXE
has no header, an unused band holds leftovers) and reports the loader's
file-id cell `0x80146464`, the `File_LoadDone` state and the area number
`0x80143F00` beside it. `area_poller.py watch` prints the set on change and
`harvest_interp_pcs.py` stamps it on newly entered PCs (`resident`).
Caveat kept in the output: the id is valid the instant a load *starts*, so
`(in flight)` means the code behind it may not be there yet.

`tools/load_watch.py` is the loader hook without a framework change: a write
trace on `0x80146464` sees every `File_LoadRequest` with its file id, caller
`ra` and `a0..a3`. The native version and an on-screen readout are IDEAS I7 /
I8 (enhancement phase).

## Seeding the extractor from the table (2026-09-08)

The pointers are the overlay's *exported* entries — reached by dispatch, so
they are exactly the interior entries Axis B otherwise has to harvest by
playing. Measured against the two seed sets the extractor had:

| origin of the 2,064 header pointers | count |
|---|---:|
| already a static-discovery root (JAL target / prologue) | 221 |
| already an observed dispatch PC (harvested) | 256 |
| known to neither | **1,587** |

The unseen ones are where unplayed content is: SCENARIO 429, WORLD01–04 622,
BMAGIC 329, BOSS 97. They look like code: 349 follow a `jr ra`, the rest open
with `lui` like the game-mode state thunks at `0x801D0F80`.

`extract_overlays.py` now unions them into `dispatch_entry_pcs` and declares
them in `static_dispatch_entry_pcs` — the framework's slot for "dispatch
entries that came from a static export/header/jump table", classified
`STATIC_DISPATCH_ENTRY` by `compile_overlays.py` (544 were newly classified
that way; the rest the compiler's own walk had already reached).
`--no-header-seeds` is the A/B escape hatch. Compile audit after: 19 shard
fails, all `0 unknown_bad, N unsupported` (was 17) — two more occupants where a
seed walked into data-as-code words that the audit rejects, the benign class.

**A/B on the 12 savestates: flat, 1.00x on every slot** (`tools/interp_bench.py
compare analysis/interp_bench_header.jsonl A B`; interpreted insns per frame
465–1,348 before, identical after; `address_misses` per frame identical).
Not a null result about the seeds — a result about the *scenes*: every saved
slot is content that has already been harvested, so its header entries were
already in the observed set or reachable from it. `tools/interp_bucket.py` on
the two hottest slots (10 and 2) shows the residual is not header-shaped at
all:

| region | share of interpreted insns | what |
|---|---:|---|
| SCENARIO band, **one PC** `0x801F92F4` | 59–62 % | SCENA12 (id `0x111`, header table empty): a `j 0x801F9EF8` **jump-table case label**, 1,100–1,300 entries per 8 s, **not in the observed set** — an ordinary unharvested interior entry; the next harvest + loop closes it |
| kernel RAM `0x800027AC..0x80003554` | 38–41 % | the relocated BIOS exception handler, deliberately not compiled (HANDOFF Traps) |

So the seeds' value is in areas not yet reached — the same conclusion as the
coverage tool's "go play these next" (WORLD01 never sampled, SCENARIO 2.2 %).
The measurement that would show it is a scene in unharvested content, which by
construction no savestate holds yet: the first time a new area is played on
this build, `harvest_interp_pcs.py` reports how many header entries it would
have had to find on its own.

## The loader and the spell→overlay link (2026-09-08)

The game never names a file. It names a **disc-file id**, and the boot EXE
turns it into a sector:

| function | what it is |
|---|---|
| `File_LoadRequest(file_id)` `0x801629CC` | stores the id at `0x80146464`, the buffer `0x800E4800` at `0x80146460`, clears a 24-byte slot array `0x8014649C`, resolves the LBA and kicks the CD state machine (`0x80146490` = 0 until done) |
| `File_LBA(file_id)` `0x80162B50` | `u32[0x80182DBC + id*4]` — the **LBA table**, one entry per disc file in directory-walk order. All 887 entries are exact LBAs (`tools/file_ids.py`, 887/887) |
| `File_LoadDone()` `0x801636F0` | `0x80146490 == 3`; every caller spins on it |

So a `jal 0x801629CC` with an immediate names a file: the game-mode
dispatcher `0x8014EB20` passes `0x262` = `GAME.EMI`, `0x8014E9A0` passes
`0x261` = `FIRST.EMI`; BATTLE and BATL_END pass `u16[0x80143F00] + 0x2AB`, so
**`0x80143F00` is the current AREA number** and `0x2AB` is `AREA000.EMI`
(the "area id?" cell in [`BATTLE_RAM.md`](BATTLE_RAM.md) is settled);
COMMU00 passes `0x259..0x25E` = `COMMU01..05`; SCENA15 passes `0x291..0x294` =
`SCE15EF0..3`. `analysis/file_ids.json` is the whole map.

**The file id is not the registry id.** `MAGIC001.EMI` is file `0x125` and
registry `0x144`. Two id spaces: the file id is the disc directory, the
registry id is the overlay's identity inside RAM. That is why the day's
searches for a `0x144..0x1BF` field found nothing — the ability path carries
file ids.

The battle engine (`BATTLE.EMI#15` at `0x80093800`) resolves a spell in two
tables of its own:

```
row     = u8 [0x800B3450 + ability_id]        Magic_AbilityRow   (232 B, 227 used; 0 = engine-side)
file_id = u16[0x800B3538 + row*8]             Magic_EffectTable  (151 rows; 0xFFFF = none)
entry   = u32[0x800B3538 + row*8 + 4]         handler pc inside the loaded image (or the engine)
```

`Magic_LoadForAbility(ability_id)` `0x800AB120` does exactly that and calls
`File_LoadRequest`. `Magic_LoadForItem(id16)` `0x800AB1FC` reaches the same
row table through four u8 sub-tables selected by the id's high byte (pointer
list `0x800B39F0` → `0x800B3A00` n=100, `0x800B3A64` n=92, `0x800B3AC0` n=72,
`0x800B3B08` n=96); `BATTLE.EMI#3` `0x801D3ED0` repeats that lookup inline.

**Verified live (2026-09-08, `analysis/callstacks/cast_magic.json`).** A
round on the new pre-fight save (file slot 1, Ryu + Nina, hold Up + Circle
×6, `--watch 0x80146464` and `0x801EEC00`) showed the whole chain in order:

| frame | event |
|---|---|
| +336 | `File_LoadRequest` store `0x801629F0` writes file id **`0x156`** = `MAGIC070.EMI`, `ra = 0x800AB160` inside `Magic_LoadForAbility` |
| +362 | band header word `0x801EEC00` goes `0x142` → **`0x16E`** = MAGIC070's registry id, written by `CD_getsector` `0x80177ACC` from `CdReadyCallback` |
| +724 | file id **`0x170`** = `MAGIC100.EMI`, same caller |
| +744 | header word → **`0x186`** = MAGIC100's registry id |

MAGIC070 is Rejuvenate (abilities 70/174) and MAGIC100 is Typhoon (100/202),
both Nina's. So the section lands straight from the CD buffer with its header
first, and the registry id read off the disc is the one the game runs with.
`Magic_LoadForAbility` is `verified` in `names/functions.toml`; the two
overlay rows and the five ability rows are `verified` in the sidecars
(`magic_map.py` carries the file ids in `VERIFIED_FILE_IDS` so regeneration
keeps them). Before that trace the chain already stood at `evidence` three
independent ways:

- **The developers numbered the files after the ability ids.** Ability 1
  Gambit → `MAGIC001`, 3 ThundrStrike → `MAGIC003`, 4 Flame Strike →
  `MAGIC004`, 45 Firebreath → `MAGIC045`, 133–136 the four Claws/Corona →
  `MAGIC133–136`.
- **Every handler pc lies inside its file's code section**: 222 of 222
  ability rows (`tools/magic_map.py`).
- **Every file id resolves through the LBA table** to a `BIN/BMAGIC/*.EMI`.

Numbers: 222 of 227 abilities load a file, 5 are engine-side (row 0, handler
`0x800AAF44`); 147 of the 151 rows are reached by abilities, the other 4 by
items; 122 distinct code sections serve the 222 (one file can host many
abilities — `MAGIC008` hosts 15, `MAGIC080` 9 — and one ability can pick a
file by state, e.g. rows 5/6/53/54/68 all in `MAGIC018`).

**Where it lives:** `names/magic.toml` (one row per ability: row, file id,
file, section md5, registry id, entry); `names/overlays.toml` — the 122 BMAGIC
rows now read `Battle FX: Super Combo, Blind, Chlorine, …` at `evidence`,
replacing the filename-derived hypothesis; `symbols.toml` has the three boot
functions; `names/functions.toml` / `names/data.toml` the engine functions and
tables.

**Trap:** `extract_overlays.py` dedups identical bytes at one address, so a
MAGIC file whose code section equals a sibling's (`MAGIC005` = `MAGIC133`'s
4,716 bytes, and 19 more) is compiled under the sibling's name. Join by
section **md5**, never by filename — `magic_map.py` does.

**Who cast it.** `Magic_LoadForAbility` receives only the ability id (from
the current-skill cell `0x801463BC`); the caster is implicit engine state, not
an argument. It is recoverable from the same capture by watching each slot's
command bytes `C+0x119/0x11A` (slot 0 `0x80145FA5`, slot 1 `0x801460E5`):
`Actor_SkillItemDone` clears the byte with the actor record in `a0` right
after that actor's effect resolves. `cast_who.json` (2026-09-08): skill id
`0x46` Rejuvenate + file `0x156` at f+372/374, then Ryu's byte cleared at
f+498 with `a0 = 0x80145E8C`; skill `0x64` Typhoon + file `0x170` at
f+760/762, then Nina's byte cleared at f+860 with `a0 = 0x80145FCC`. So the
heal was Ryu's, Typhoon Nina's. **Trap:** the position store to `0x80146382`
just before the call carries the *target* record in `a1` (Ryu healed
himself, so it read as Ryu; Typhoon's pointed at the enemy `0x801EB5A0`) —
do not read it as the caster.

## Open

- **Verify more rows the same way**: every cast adds two lines to
  `cast_magic`-style captures; 2 of 122 sections are `verified`, the rest
  `evidence`. A `--watch 0x80146464-0x80146468` on any battle round is enough.
- **Item sub-tables**: which item category each of the four `0x800B39F0`
  tables serves (sizes 100/92/72/96 match no `items.toml` table exactly).
- **`Magic_EffectTable` `+0x02`** is 0 in all 151 rows — padding or an
  unused field.
- **The other loader tables**: `0x800B19A4`/`0x800B19A8` (u16 lists indexed
  by `0x80145020`, used at `BATTLE.EMI#3` `0x801E7A3C`) and the
  `BPLCHAR` picks (`0x201/0x205`, `0x23C/0x23D/0x23F` chosen by a form byte
  `< 2`) — character battle models by form, not read yet.

## Method note

The finding came from a **cross-image differential**: reading the same offset
across 124 sibling images that share one load address. Eight unreadable bytes
in one image became a mapped header format in a single query, because the
siblings supply the contrast a single image cannot. Reuse it wherever a band
has many occupants.
