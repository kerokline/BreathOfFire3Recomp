# AREA overlays — how the field side loads them and how it enters them

**Status:** research pass, 2026-09-12. Read-only; nothing in the repo was
modified. Evidence is the staged boot EXE `disc/SLPS_009.90`, the static
captures in `analysis/overlay_captures_all.json`, `analysis/emi_sections.json`,
`analysis/file_ids.json`, and the Ghidra exports under `analysis/ghidra/`.

## Headline

There **is** an analogue of the magic `(file id, entry pc)` convention on the
field side, and it is stronger than the magic one: the boot EXE carries a
**200-entry pointer table at `0x801802EC`, indexed by area number, whose entries
point *into the freshly loaded AREA image*.** The struct they point at is the
AREA image's last 0x44 bytes and it carries **two code-pointer fields**:

| field | what | verified |
|---|---|---|
| `+0x40` | one-shot area-init handler, called via `jalr` immediately after the load | 67 populated, all 67 inside their own section |
| `+0x3C` | pointer to an array of native handlers, called by field-script opcodes `0x03` and `0xDE` and by the entity-behaviour dispatch | 119 areas, 671 array entries, all inside their own section |

**All 200 table entries land inside their own `AREA<n>.EMI` section: 200/200.**

Crucially these pcs are **disjoint from the overlay header entry table** that the
extractor already seeds: intersection of the 336 AREA header entry pcs with the
738 record pcs is **zero**. 228 of the 738 are in none of the capture's four seed
sets, and 226 of those 228 immediately follow a `jr $ra` delay slot — they are
real function entries.

A second, fully-proven record table exists for SCENARIO: `0x801C944C` in
GAME.EMI, 20 chapters, **20/20 verified**.

There is **no door/map-transition table** carrying an area number next to a code
pointer. Transitions go through one function with an immediate or a saved global.

---

## 1. Every `File_LoadRequest` (0x801629CC) call site on the field side

Found by scanning for the encoded `jal 0x801629CC` = `0x0C058A73` over the whole
boot EXE `.text` and over every compiled section in
`analysis/overlay_captures_all.json` (61 sites game-wide; the Ghidra
`call_sites[]` lists only 2 + 7 and is incomplete — do not rely on it here).

### Boot EXE — 4 sites

| site | owning fn | a0 | class |
|---|---|---|---|
| `0x8014E9A0` | `0x8014E974` | `addiu $a0,$zr,0x261` | immediate → `BIN/ETC/FIRST.EMI` |
| `0x8014EB28` | `0x8014EB20` | `addiu $a0,$zr,0x262` | immediate → `BIN/ETC/GAME.EMI` |
| `0x801625F4` | `0x801625AC` | `lhu $a0, 0x2830($at)`, `$at = 0x80180000 + (id&0xFF)*4` | **table-driven** (BGM, below) |
| `0x80167CA4` | `0x80167C04` | `addiu $a0,$a0,{0x1DB,0x1EE,0x26A,0x27D}` selected by `a1 = 0..3` | base + index (player models) |

`0x80167C04` is `Model_Load(char_index, kind)`: the four bases resolve to
`BPLD012`/`BPLU012`/`PL012`/`PLP012`, i.e. the `BPLCHAR`-down, `BPLCHAR`-up,
`PLCHAR` and `PLCHAR`-portrait directories. It also caches the request at
`0x80145020`. No entry-pc field; these are model/anim data, not code.

### GAME.EMI#0 (`0x80196800`) — 11 sites, GAME.EMI#1 (`0x801D0C00`) — 1 site

| site | a0 | class | target |
|---|---|---|---|
| `0x80198004` | `0x268` | immediate | `ETC/START.EMI` |
| `0x80198628` | `0x269` | immediate | `ETC/STATUS.EMI` |
| `0x801987C4` | `0x258` | immediate | `ETC/COMMU00.EMI` |
| `0x80198DEC` | `u16[0x801CDFF8 + u8[0x801CDF1B + i*4]*2]`, else `6`/`7` | **table-driven, runtime-filled** | `BATTLE.EMI` / `BATTLE2.EMI` fallback |
| `0x80199358` | `0x266` | immediate | `ETC/SHOP.EMI` |
| `0x80199440` | `0x258` | immediate | `ETC/COMMU00.EMI` |
| `0x801997D8` | `0x257` | immediate | `ETC/BATE.EMI` |
| `0x80199998` | `0x265` | immediate | `ETC/SHISU.EMI` |
| **`0x801A0BB0`** | `addiu $a0,$a0,0x2AB` with `$a0 = area` | **`area + 0x2AB`** | `AREA<n>.EMI` |
| `0x801A881C` | `addiu $a0,$a0,0x295` with `$a0 = s8[0x8014686C]` | base + chapter | `SCENARIO/SCENA<c>.EMI` |
| `0x801A8D44` | `0x267` | immediate | `ETC/SISYOU.EMI` |
| `0x801D0CA0` | `0x25F` | immediate | `ETC/DEMO.EMI` |

The two tables in this set that are actually tables:

**BGM table — `0x80182830`, stride 4, 165 entries, ends at `0x80182AC4`.**
Layout `{u16 file_id, u8 ?, u8 variant}`. Evidence:

```
0x801625B0: andi $a0,$a0,0xFF
0x801625B4: lui  $v1,0x8014
0x801625B8: lbu  $v1,0x5025($v1)      ; currently loaded BGM index @0x80145025
0x801625BC: sll  $a0,$a0,2
0x801625C8: addu $at,$at,$a0
0x801625CC: lhu  $a0,0x2830($at)      ; -> 0x80182830 + idx*4
...
0x801625F4: jal  0x801629CC
```

Decoded rows resolve cleanly to `BIN/BGM/BGM*.EMI` for indices 0..164 and to
nothing from 165 on; the end address `0x80182AC4` is independently confirmed
because `FUN_801a0aa8` passes `0x80182AC4` as the *default* argument to
`func_0x801799b0` when the area struct has no override (see §2). The `+2`/`+3`
bytes are read at `0x80198CF0`/`0x80198CFC`. **No entry pc field. Proven.**

**`0x80198DEC`'s two tables are BSS**: `0x801CDF18` (stride 4, byte at `+3`) and
`0x801CDFF8` (u16 file ids) read as all-zero in the EXE image, so they are
filled at run time. Not statically decodable; not area-related (the fallback is
`BATTLE.EMI` / `BATTLE2.EMI`). Left unresolved deliberately.

---

## 2. The AREA load, and how the image is entered

### The loader

`FUN_801a0aa8` @ `0x801A0AA8` in GAME.EMI#0 — the field area-transition body.
Decompile at `analysis/ghidra/GAME_EMI0_80196800_decomp/801A0AA8_FUN_801a0aa8.c`:

```c
if (((uint)_DAT_80143f00 != (uint)param_1) && (DAT_80143bb0 == '\x05')) {
    _DAT_80143f00 = param_1;                       // area number
    func_0x801629cc(param_1 + 0x2ab);              // File_LoadRequest(AREA<n>)
    while (iVar4 = func_0x801636f0(), iVar4 == 0)  // File_LoadDone() spin
      func_0x8014b770(1);
    DAT_80143f02 = *(u8 *)(*(int *)((uint)_DAT_80143f00 * 4 + -0x7fe7fd14) + 0x32);
    func_0x8014e178();
    DAT_80145984 = 1;
}
...
FUN_801a4e58(**(u32 **)((uint)_DAT_80143f00 * 4 + -0x7fe7fd14));
pcVar5 = *(code **)(*(int *)((uint)_DAT_80143f00 * 4 + -0x7fe7fd14) + 0x40);
if (pcVar5 != (code *)0x0) {
    (*pcVar5)();                                   // <-- enters the AREA image
}
```

`-0x7fe7fd14` is `0x801802EC`. Disassembly of the load itself:

```
0x801A0BA8: lui  $at,0x8014
0x801A0BAC: sh   $s0,0x3F00($at)      ; 0x80143F00 = current area number
0x801A0BB0: jal  0x801629CC           ; File_LoadRequest
0x801A0BB4: addiu $a0,$a0,0x2AB       ; a0 = area + 0x2AB
```

The `pcVar5` call is the function's only `jalr` (Ghidra `jalr: 1`).

### Candidate record table A — the per-area struct pointer table

| | |
|---|---|
| **address** | `0x801802EC` (boot EXE `.data`) |
| **stride** | 4 |
| **count** | **exactly 200** (entry 200 onward is unrelated data) |
| **index** | area number, i.e. `u16[0x80143F00]` |
| **entry** | `u32` pointer into the freshly loaded `AREA<n>.EMI` section at `0x801F2C00` |
| **file id** | *not stored here* — formed as `area + 0x2AB` at the call site |
| **entry pc** | yes: `struct+0x40` (init), and `struct+0x3C` → array of handlers |
| **confidence** | **proven** |

The struct is **0x44 bytes and sits at the very end of the AREA section.**
Minimum bytes between the pointer and the section end, over the 182 areas whose
section is captured: **exactly 68 = 0x44**, never less; for 82 of the 182 it is
exactly 68, i.e. the struct terminates the file.

Field layout (offsets from the struct pointer), from
`grep -rh "7fe7fd14" analysis/ghidra/*_decomp/` plus a byte dump of AREA000
(`struct @0x801F3FF8`, section `0x801F2C00..0x801F403C`):

| off | type | AREA000 value | used at |
|---|---|---|---|
| `+0x00` | ptr, dereferenced | `801F2E74` | `FUN_801a4e58(**(u32**)…)` |
| `+0x04` | ptr | `801F3FB8` | `FUN_801a238c`, `FUN_801ad1dc` |
| `+0x08` | ptr | `801F39C0` | `func_0x8015b67c(… +8 …)` |
| `+0x0C` | 0 | `00000000` | — |
| `+0x10` | ptr | `801F3980` | `FUN_801a27a8` |
| `+0x14` | ptr | `801F3E5C` | `FUN_801a1050` |
| `+0x18` | ptr | `801F3E78` | indexed `*param_2*4 + …` |
| `+0x1C` | ptr | `801F3F04` | `FUN_801a78c8` |
| `+0x20` | ptr | `801F2D18` | byte array (`pbVar8`) |
| `+0x24..+0x2C` | ptr | `801F2E0C/2E08/2E14` | — |
| `+0x30` | u8 | `0x10` (word `00000B10`) | `FUN_801b3dd4` |
| `+0x32` | u8 | `0x0B` | → `0x80143F02` (area flags; bit 4 gates the `COMMU00` load at `0x801987C4`/`0x80199440`) |
| `+0x34` | ptr | `801F3FE8` | — |
| `+0x38` | ptr or 0 | `00000000` | camera/bounds; when 0 the default `0x80182AC4` is used, reads `+0x20`/`+0x24` |
| **`+0x3C`** | **ptr → code-pointer array** | `801F3FF0` | script opcodes `0x03` and `0xDE`, entity dispatch |
| **`+0x40`** | **code ptr or 0** | `00000000` | called once after load |

**Verification of `+0x40`** (182 areas with a capture):

- 114 null (the `if (pcVar5 != 0)` guard covers these),
- **67 non-null, all 67 4-byte aligned and inside their own section**,
- 1 anomaly (area 30 — see *Exceptions*).

**Verification of `+0x3C`**: 119 areas carry a non-null, in-section pointer; 62
null; 1 anomaly (area 30). Walking words forward from it until one is not an
in-section aligned address, bounded by the struct itself, yields **671 entries,
every one inside its own section**. In 103 of the 119 the array runs contiguously
right up to the struct start, so the count is `(struct_ptr - u32[struct+0x3C])/4`;
in the other 16 something else sits between, so the walk-until-invalid rule is the
safe one and gives a lower bound.

### How the `+0x3C` array is called

Two script opcodes take a **byte operand that indexes this array** and call
through it:

`FUN_801a9f94` @ `0x801A9F94` (low-nibble opcode group), case 3:

```c
(**(code **)((uint)*(byte *)(param_2 + (uint)*(ushort *)(param_1 + 10) + 1) * 4 +
            *(int *)(*(int *)((uint)_DAT_80143f00 * 4 + -0x7fe7fd14) + 0x3c)))();
```

`FUN_801ab470` @ `0x801AB470`, case `0xDE`: byte-for-byte the same expression.

And the entity-behaviour dispatch `FUN_801ade10` @ `0x801ADE10`:

```c
uVar2 = *(byte *)(_DAT_80146880 + 0x94) & 0x7f;
if (uVar2 == 0x7f) pcVar1 = *(code **)((int)&PTR_FUN_801c9904 + ((param_1 << 0x10) >> 0xe));
else               pcVar1 = *(code **)(uVar2 * 4 + *(int *)(… + 0x3c));
(*pcVar1)();
```

So an entity whose behaviour byte is `< 0x7f` runs **area-local native code**;
`0x7f` falls back to GAME.EMI's own table at `0x801C9904`.

### Is this already covered by the header entry tables? No.

| | count |
|---|---|
| AREA header entry pcs (`header_entry_pcs`, 40 of 182 areas non-empty) | 336 |
| record pcs from `+0x3C` ∪ `+0x40` (deduped per area) | 738 |
| **intersection** | **0** |

Against the union of all four seed sets the captures already carry
(`header_entry_pcs`, `static_discovery_entry_pcs`, `dispatch_entry_pcs`,
`static_dispatch_entry_pcs`):

| | count |
|---|---|
| record pcs already in a seed set | 510 |
| **record pcs in no seed set** | **228** |

Of those 228, **226 sit 8 bytes after a `jr $ra`** (i.e. follow a returning
function's delay slot) and 1 opens with `addiu $sp,$sp,-N`. They are function
entries, not data. The reason static discovery misses them is exactly the reason
`AREA_PCS.md` gives for prologue detection: these are small leaf handlers with
no stack frame that nothing `jal`s — they are only ever reached through this
table.

### Exceptions

- **18 areas have no capture** (6, 9, 17, 31, 66, 70, 83, 89, 101, 122, 126,
  129, 137, 138, 159, 190, 194, 195): their `0x801F2C00` section is classed
  `data` in `emi_sections.json`, so no overlay was compiled and the `+0x3C`/`+0x40`
  words could not be read here. Their `0x801802EC` pointers are still in range.
- **Areas 30 / 89 / 129 are the world map.** All three share the same 75,321-byte
  code section at `0x801D0C00` (plus `0x800F5000`), and their `0x801F2C00`
  section is only 128 bytes. `0x801802EC[30] = 0x801F2C3C`, and `0x3C + 0x44 =
  0x80 = 128`, so the struct still terminates the section exactly — but its
  contents are not pointers (`+0x34..+0x44` read `012C0064 03E801F4 07D005DC
  0FA00BB8 1B581388` = paired 16-bit values 100/300, 500/1000, 1500/2000,
  3000/4000, 5000/7000, which look like distance bands). Either the world-map
  mode never reaches the `+0x40` call, or the struct is a different type for it.
  **Not resolved statically — flag before any tool trusts `+0x40` for these three.**

---

## 3. Candidate record table B — SCENARIO chapters (proven, and it is the exact
   magic-convention analogue)

Found on the AREA-load path: `FUN_801a0aa8` ends with `FUN_801a8834()`, which is

```c
(*(code *)**(undefined4 **)(&DAT_801c944c + DAT_8014686c * 4))();
```

and its sibling `FUN_801a880c` @ `0x801A880C` is the loader:

```
0x801A880C: lui   $a0,0x8014
0x801A8810: lb    $a0,0x686C($a0)     ; chapter, s8 @0x8014686C
0x801A881C: jal   0x801629CC
0x801A8820: addiu $a0,$a0,0x295       ; SCENA00.EMI = file id 0x295
```

| | |
|---|---|
| **address** | `0x801C944C` (inside GAME.EMI#0) |
| **stride** | 4 |
| **count** | **20** (chapters 0..19; index 20+ is GAME.EMI code, `0x801A8C34` etc.) |
| **index** | `s8[0x8014686C]` = scenario chapter |
| **file id** | `0x295 + chapter` → `SCENARIO/SCENA<cc>.EMI` |
| **entry pc** | `u32[ u32[0x801C944C + c*4] ]` — the first word of the pointed-at struct |
| **verified** | **20 / 20**: both the struct pointer and the entry pc are inside the corresponding `SCENA<cc>.EMI` section at `0x801F6C00` |
| **confidence** | **proven** |

Sample: chapter 0 → struct `0x801FC9FC`, entry `0x801F913C`, SCENA00 section
`0x801F6C00..0x801FDB70`. Chapter 15 → struct `0x801FE5F4`, entry `0x801F9CAC`.

The SCENARIO struct is *not* the area struct: it is a longer run of pointers
(`+0x00..+0x3C` all in-section for SCENA00), i.e. its own dispatch table. Not
explored further.

`SCENARIO` has 25 overlays but this table wires only 20; `SCENA15` loads its own
sub-files `0x291..0x294` directly (already in `OVERLAY_HEADERS.md`).

---

## 4. Map-transition / door tables — negative result

`Field_ChangeArea` @ **`0x801A0A30`** is the single funnel. It stashes its four
arguments and flips the game mode, and the mode-5 handler at `0x801981F0` reads
them back and calls `FUN_801a0aa8`:

```
0x801A0A4C: sh $a0,0x3F10($at)   ; 0x80143F10 = pending area
0x801A0A54: sw $s0,0x3F14($at)   ; 0x80143F14 = pending x/z
0x801A0A5C: sw $s1,0x3F18($at)   ; 0x80143F18 = pending y
0x801A0A64: sb $a3,0x3F1C($at)   ; 0x80143F1C = pending flags
0x801A0A8C: sb $v0,0x3BB0($at)   ; game mode = 5
```

Every `jal 0x801A0A30` in the game (full encoded scan of the boot EXE and all
406 captures): 12 in GAME.EMI#0, ~330 across `SCENARIO/SCENA00..17`, and ~55
inside `AREA*.EMI` code sections themselves. **None of them reads a table of
`(area, code pointer)` records.** The twelve GAME.EMI sites take their `a0`
from:

- `0x80143F04` — previous area, saved by `FUN_801a0aa8` on entry (`_DAT_80143f04 = _DAT_80143f00`) — the "back out of a sub-map" path (`0x801996D0`, `0x801B277C`);
- `0x80145044` — a separately stashed return area (`0x801A9680`, `0x801A9B5C`, `0x801B2868`, `0x801B7878`);
- `0x801448F8` — the area stored in the save file (`0x80198194`, written by `SHOP.EMI` `FUN_801d69f0` and by the save/load path);
- `0x80143F10` — the pending-area cell re-read (`0x801B25E8`);
- **immediates** — `0x801A8FAC` hardwires area `0x22` and area `0x04` with fixed coordinates (the escape/return warps).

Per-area doors therefore live in the AREA image's own script and code, which is
consistent with §2: an area's exits are among the handlers reached through
`struct+0x3C`, or are `jal 0x801A0A30` sites inside the area's own section with
an immediate area number in `$a0`. Those immediates *are* statically
extractable (55 call sites across the 184 AREA captures) and would give a real
map graph, but that is a separate job and is **not** a record table.

**Confidence: likely-complete negative.** The scan for `jal 0x801A0A30` is
exhaustive over every compiled image; what it cannot rule out is a table read by
an area's own code (each area would then carry its own), which is by
construction not a shared table.

---

## 5. Summary of candidates

| # | address | stride | count | index | file id | entry pc field | verified | confidence |
|---|---|---:|---:|---|---|---|---|---|
| A | `0x801802EC` | 4 | 200 | area number `u16[0x80143F00]` | not in the record; `area + 0x2AB` at `0x801A0BB0` | `+0x40` (init) and `+0x3C`→array | 200/200 pointers in-section; 67/67 `+0x40`; 671/671 `+0x3C` entries | **proven** |
| B | `0x801C944C` | 4 | 20 | chapter `s8[0x8014686C]` | not in the record; `0x295 + chapter` at `0x801A881C` | `u32[*entry]` | **20/20** | **proven** |
| C | `0x80182830` | 4 | 165 | BGM index `u8[0x80145025]` | `u16` at `+0x00` | none (data overlay) | 165/165 resolve to `BIN/BGM/*` | **proven** |
| D | `0x801CDF18` + `0x801CDFF8` | 4 / 2 | ? | runtime | `u16` | none | — | BSS, **not decodable statically** |
| E | player models, `0x80167C04` | — | — | char index + kind 0..3 | `{0x1DB,0x1EE,0x26A,0x27D} + idx` | none | 4 bases resolve | **proven**, no code |

## 6. What this is worth

228 previously unseeded, provably in-section, provably code-shaped entry pcs in
the `0x801F2C00` band, reachable only through table A. They are exactly the kind
of interior entry the extractor's header seeding was aimed at, and the header
tables miss all of them (intersection 0). Feeding table A's `+0x3C` array and
`+0x40` into `static_dispatch_entry_pcs` alongside the header pointers is the
obvious follow-up; the same walk over table B would do the same for SCENARIO.

The A/B caveat from `OVERLAY_HEADERS.md` applies unchanged: saved slots are
harvested content, so the win will not show on the 12 savestates. The place to
measure is a first visit to an unplayed area.

Two things to carry into any tool built on this:

1. **Bound the `+0x3C` walk by the struct pointer**, not by the section end —
   the array sits immediately below the struct in every observed case, and an
   unbounded walk reads the struct's own pointer fields back as array entries.
2. **Skip areas 30, 89 and 129** (the world map) until their struct type is
   settled; their `+0x3C`/`+0x40` words are not pointers.
