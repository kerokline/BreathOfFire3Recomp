# BOSS and ENEMY overlays — how they are chosen, loaded and entered

**Status:** PROVEN (static). 2026-09-12. Read-only; no Ghidra, no git, no edits.
Evidence: `disc/SLPS_009.90`, `analysis/overlay_captures_all.json`,
`analysis/emi_sections.json`, `analysis/file_ids.json`,
`analysis/ghidra/GAME_EMI0_80196800_decomp/80198C94_FUN_80198c94.c`, and
`D:\BoFIII\BIN` raw EMI reads for non-compiled sections.

---

## 1. Executive summary

A boss fight is **one `u8` in RAM**: `0x801462E6` (already called "boss flag"
in `docs/BATTLE_RAM.md`). It is 0 for a random encounter and 1..55 for a boss.
Everything else is table-driven off it:

```
boss_id   = u8 [0x801462E6]                          set by Battle_StartBoss 0x801C8A4C (GAME.EMI)
rec       = 0x801CDF18 + boss_id*4                   Boss_EncounterTable, 56 records, stride 4  (GAME.EMI image)
  +0x00 u8  battle flags   -> 0x80146321  (0x80146320 cleared)
  +0x01 u8  arena/camera id-> 0x801462E8
  +0x02 u8  formation index-> row in the AREA's formation table at 0x800E4000, stride 9
  +0x03 u8  row            -> Boss_FileTable
file_id   = u16[0x801CDFF8 + row*2]                  Boss_FileTable, 41 entries; row 0 = 0x006 BATTLE.EMI,
                                                     rows 1..40 = the 40 BIN/BOSS/BOSS*.EMI file ids 0x1B3..0x1DA
entry_pc  = u32[0x800B2048 + boss_id*4]              Boss_EntryTable, 56 entries, in the BATTLE ENGINE image;
                                                     [0] = 0x800A8B58 (engine-side `jr ra`), [1..55] land in 0x800C1800
```

`BOSS<nnn>.EMI` is **not an overlay grafted onto a running battle — it is a
self-contained battle bundle**. Every one of the 40 files ships a
byte-identical copy of `BATTLE.EMI`'s engine (`0x80093800`, md5
`4065db04716614f63106a242d5160285`) and game-mode section (`0x801D0C00`, md5
`8a80230efd4a882da0558fde6eb0badb`), plus boss-only data at `0x80014000`,
`0x8002EE00`, `0x800F0800` and the boss-only code at `0x800C1800`. That is why
the files are 440–765 KB and why the engine can carry a static entry table for
all 55 bosses: the boss images are linked against it.

`ENEMY<nnn>.EMI` is **pure graphics — no code, no RAM section**, chosen as
`area + 9`, and **skipped entirely when `0x801462E6 != 0`** (the boss bundle
brings its own art).

---

## 2. Q1 — how the BOSS file is chosen

### 2.1 The trigger: `Battle_StartBoss` `0x801C8A4C` (GAME.EMI#0)

```
801C8A4C  addiu v0,zero,0x5
801C8A50  lui   at,0x8014
801C8A54  sb    a0,0x62E6(at)        ; 0x801462E6 = boss id   <-- THE DIALER CELL
801C8A58  andi  a0,a0,0xFF
801C8A5C  lui   v1,0x8014
801C8A60  lhu   v1,0x6316(v1)
801C8A64  sll   a0,a0,2              ; boss_id * 4
801C8A6C  sb    v0,0x5E8D(at)        ; 0x80145E8D actor[0] state = 5 (enter battle)
801C8A74  sb    zero,0x5E8E(at)
801C8A7C  sb    zero,0x5E8F(at)
801C8A84  sb    zero,0x5E90(at)
801C8A88  ori   v1,v1,0x1000
801C8A90  sh    v1,0x6316(at)        ; 0x80146316 |= 0x1000  (battle requested)
801C8A94  lui   at,0x801D
801C8A98  addu  at,at,a0
801C8A9C  lbu   v0,-0x20E8(at)       ; rec+0x00  @ 0x801CDF18 + id*4
801C8AA4  sb    zero,0x6320(at)      ; 0x80146320 = 0
801C8AAC  sb    v0,0x6321(at)        ; 0x80146321 = battle flags
801C8AB0  jr    ra
```

There are exactly **49 static callers**, all in `BIN/SCENARIO/SCENA00..15`,
all with an immediate `a0` — a complete boss dialer map:

| SCENA | boss ids passed |
|---|---|
| 00 | 1, 4, 5, 6, 7 |
| 01 | 2, 3 |
| 02 | 8, 9, A, B, C, D, E, F |
| 03 | 10 |
| 05 | 11, 12 (×3), 13, 14, 15, 16 |
| 06 | 17, 18, 19, 1A, 1B, 1C |
| 07 | 1D, 1E, 1F |
| 08 | 20, 21, 22 |
| 09 | 35, 36 |
| 10 | 23, 24 |
| 12 | 26 (×2) |
| 13 | 25 |
| 14 | 31, 32, 33, 34 |
| 15 | 37, + one dynamic (`lbu a0,…` at `0x801FAEFC`) |

Ids `0x27..0x30` (39..48) never appear as an immediate — they come from the one
dynamic call in SCENA15 (and/or unreached code). The setter does **no bounds
check** (`andi a0,0xFF` only), so a dialer harness must stay in 1..55.

Clears of the cell: `GAME.EMI#0 0x80198174`, `0x8019910C`, `BATL_OVR.EMI#0
0x801EF118` (`sb zero,0x62E6(at)`) — i.e. the flag is cleared when the battle
ends / the field resumes.

### 2.2 The choice: `FUN_80198C94` (GAME.EMI#0, `0x80198C94`)

Ghidra decompile (`analysis/ghidra/GAME_EMI0_80196800_decomp/80198C94_FUN_80198c94.c`):

```c
if (DAT_801462e6 == 0) {                                   /* random encounter */
    uVar3 = 7;
    if (DAT_8014686c < '\b') uVar3 = 6;                    /* chapter < 8 -> BATTLE.EMI else BATTLE2.EMI */
} else {                                                   /* boss */
    uVar3 = *(undefined2 *)(&DAT_801cdff8 +
              (uint)(byte)(&DAT_801cdf1b)[(uint)DAT_801462e6 * 4] * 2);
}
func_0x801629cc(uVar3);                                    /* File_LoadRequest */
```

Matching disassembly (same image):

```
80198DD0  lui  v0,0x8014
80198DD4  lb   v0,0x686C(v0)       ; scenario/chapter number
80198DDC  slti v0,v0,0x8
80198DE0  beq  v0,zero,0x80198DEC
80198DE4  addiu a0,zero,0x7        ; 0x007 BIN/BATTLE/BATTLE2.EMI
80198DE8  addiu a0,zero,0x6        ; 0x006 BIN/BATTLE/BATTLE.EMI
...
80198DA8  sll  v0,v0,2             ; boss_id*4
80198DAC  addu at,at,v0            ; at = 0x801D0000 + boss_id*4
80198DB0  lbu  v0,-0x20E5(at)      ; rec+0x03  @ 0x801CDF1B + id*4   -> row
80198DBC  addu at,at,v0            ; at = 0x801D0000 + row*2
80198DC4  lhu  a0,-0x2008(at)      ; Boss_FileTable @ 0x801CDFF8 + row*2
80198DEC  jal  0x801629CC          ; File_LoadRequest(file_id)
```

Both tables live inside the **GAME.EMI#0 image** (`0x80196800 .. 0x801CE0E4`),
which stays resident through the battle (the battle overlay starts at
`0x801D0C00`), so they are readable whenever the engine needs them.

### 2.3 `Boss_EncounterTable` `0x801CDF18` — 56 records, stride 4

| off | width | field | consumer |
|---|---|---|---|
| +0x00 | u8 | battle flags (`0x00,0x05,0x07,0x0D,0x25,0x27,0x45,0x47,0x4F,0x67,0x87,0x8F,0xC7`) | `0x801C8A9C` → `0x80146321` |
| +0x01 | u8 | arena / camera id (0..3) | `0x801C0E50` → `0x801462E8` (camera target comes from `DAT_801CDBE4[0x801462E8]`, `names/functions.toml`) |
| +0x02 | u8 | formation index (4..7) | `0x800A8ED0` (engine) → row in the area formation table `0x800E4000`, stride 9 |
| +0x03 | u8 | row into `Boss_FileTable` (0..40) | `0x80198DB0` |

Record 0 is all zeros (the non-boss slot). The table ends exactly where
`Boss_FileTable` begins (`0x801CDFF8 - 0x801CDF18 = 0xE0 = 56*4`).

### 2.4 `Boss_FileTable` `0x801CDFF8` — 41 `u16`, disc-file ids

Row 0 = `0x006` (`BIN/BATTLE/BATTLE.EMI`); rows 1..40 = every BOSS file,
`0x1B3..0x1DA`, one per file, in the order
BOSS002, 004, 007, **001**, 008, 012, 013, 014, 015, 017, 018, 019, 020, 021,
022, 023, 024, 025, 027, 028, 029, 030, 031, 032, 033, 034, 035, 036, 037, 038,
040, 049, 050, 051, 052, 054, 055, 042, 046, 047. The first zero word after the
40th row (`0x801CE04A`) terminates it. **The boss number in the filename is not
the boss id and not derivable from it** — BOSS files are non-contiguous
(001,002,004,007,012,…,055) while the file ids are contiguous `0x1B3..0x1DA`.

Boss-id → filename (from the two tables, all 55):

```
 1 BOSS001   12 BOSS012   23 BOSS023   34 BOSS034   45 BOSS049
 2 BOSS002   13 BOSS013   24 BOSS024   35 BOSS035   46 BOSS046
 3 BOSS002   14 BOSS014   25 BOSS025   36 BOSS036   47 BOSS047
 4 BOSS004   15 BOSS015   26 BOSS025   37 BOSS037   48 BOSS024
 5 BOSS004   16 BOSS013   27 BOSS027   38 BOSS038   49 BOSS049
 6 BOSS004   17 BOSS017   28 BOSS028   39 BOSS002   50 BOSS050
 7 BOSS007   18 BOSS018   29 BOSS029   40 BOSS040   51 BOSS051
 8 BOSS008   19 BOSS019   30 BOSS030   41 BOSS034   52 BOSS052
 9 BOSS008   20 BOSS020   31 BOSS031   42 BOSS042   53 BOSS040
10 BOSS008   21 BOSS021   32 BOSS032   43 BOSS036   54 BOSS054
11 BOSS008   22 BOSS022   33 BOSS033   44 BOSS038   55 BOSS055
```

**Confidence: proven.** Decompile + disassembly + both tables read off the disc
image, and the entry-pc cross-check in §5.

---

## 3. Q2 — how a loaded BOSS image is ENTERED

Not the header entry table, not a fixed offset: **one `jalr` through a
56-entry pointer table inside the battle engine**, indexed by the same boss id.

`BATTLE.EMI#15` (`0x80093800`), `Battle_SetupEncounter` `0x800A8AD4`:

```
800A8AD4  lui   v0,0x8014
800A8AD8  lbu   v0,0x62E6(v0)          ; boss id
800A8AE0  beq   v0,zero,0x800A8AF8     ; 0 -> random-encounter path 0x800A8B60
800A8AE8  jal   0x800A8B10             ; boss path

800A8B10  addiu sp,sp,0xFFE8
800A8B14  sw    ra,16(sp)
800A8B18  jal   0x800A8E8C             ; build the formation (see below)
800A8B20  lui   v0,0x8014
800A8B24  lbu   v0,0x62E6(v0)          ; boss id
800A8B2C  sll   v0,v0,2
800A8B30  lui   at,0x800B
800A8B34  addu  at,at,v0
800A8B38  lw    v0,0x2048(at)          ; Boss_EntryTable @ 0x800B2048 + id*4
800A8B40  jalr  ra,v0                  ; <-- ENTERS THE 0x800C1800 BOSS IMAGE
800A8B48  lw    ra,16(sp)
...
800A8B58  jr    ra                     ; <-- Boss_EntryTable[0], the engine-side no-op
```

Formation build, `0x800A8E8C`:

```
800A8E90  lui   a0,0x800E
800A8E9C  ori   a0,a0,0x4000           ; a0 = 0x800E4000, the AREA file's formation table
800A8E98  lbu   v0,0x62E6(v0)          ; boss id
800A8EC4  sll   v0,v0,2
800A8ED0  lbu   v1,-0x20E6(at)         ; rec+0x02 @ 0x801CDF1A + id*4 = formation index
800A8ED8  sll   v0,v1,3 ; addu v0,v0,v1 ; addu s2,v0,a0     ; s2 = 0x800E4000 + idx*9
800A8EE8..800A8F18                      ; 8 slots, byte 0xFF terminates, 0x800A8F4C spawns each
```

`0x800E4000` is section data shipped by the **AREA** file (1160 bytes, present
in all 200 `BIN/WORLD0*/AREA*.EMI`), and no BOSS section targets `0x800E4000`,
so the area's formation table survives the boss load — which is what makes a
9-byte-row index in the boss record meaningful.

### The header entry table is not the entry path

Counter-evidence, `BOSS034.EMI`: its `0x800C1800` header entry run is
`0x800C207C, 0x800C1F60, 0x800C207C ×3, 0x800C2020`, while `Boss_EntryTable`
sends boss ids 34 and 41 to `0x800C1EA8` and `0x800C2324` — neither is in the
header run. 18 of the 35 distinct BOSS images have **no** header table at all
(code starts at `+0x04`) yet all 55 ids have a valid entry pc. A scan of the
boot EXE, `BATTLE.EMI#15` and `BATTLE.EMI#3` for any `jal`/`j`/`lui 0x800C`
reference into `0x800C1800..0x800C2800` found **nothing** except the indirect
above. The header pointers are consumed by the boss's own code (and by
`extract_overlays.py` seeding); the engine never reads them.

**Confidence: proven** for the `0x800B2048` route; **likely** (negative,
evidence-backed) for "the header table is internal to the boss image".

---

## 4. Q3 — `ENEMY<nnn>.EMI`

**Which band: none. They contain no RAM section and no code.**
All 200 files have exactly 3 sections, every one `class = "not-ram"` with
`dest = 6` (a VRAM/TIM destination code, not an address):
600 sections, `Counter({('0x6','not-ram'): 600})`. Sizes: section 0 = 6688 B
(constant), section 1 = 64 B, section 2 = per-file texture data. They are enemy
sprite sheets DMA'd to VRAM.

**How chosen: `area + 9`, an immediate-free but table-free computation** in
`Battle_Init`'s region, `BATTLE.EMI#3`:

```
801D1718  lui   v0,0x8014
801D171C  lbu   v0,0x62E6(v0)      ; boss id
801D1724  bne   v0,zero,0x801D1740 ; BOSS -> skip the ENEMY load entirely
801D172C  lui   a0,0x8014
801D1730  lhu   a0,0x3F00(a0)      ; 0x80143F00 = current AREA number
801D1734  jal   0x801629CC         ; File_LoadRequest
801D1738  addiu a0,a0,0x9          ; file id = area + 9
```

Verified against `analysis/file_ids.json`: `BIN/BENEMY/ENEMY000..199.EMI` are
file ids `0x009..0x0D0`, **contiguous, 200/200**, and `ENEMY<i>` is exactly id
`9+i` for every i. This is the same shape as `AREA<i>` = `0x2AB + i`
(`0x2AB..0x372`, 200/200).

**How entered: never.** No code, no entry, no registry-id header (the header
convention applies to RAM-destination sections only).

**Confidence: proven.**

---

## 5. Q4 — verification counts

### 5.1 Entry pcs land inside the named file's `0x800C1800` section

For every boss id 1..55: `row = u8[0x801CDF1B+id*4]`, `file =
u16[0x801CDFF8+row*2]`, `size = ` that file's `dest == 0x800C1800` section size
from `analysis/emi_sections.json`, `entry = u32[0x800B2048+id*4]` read out of
`BATTLE.EMI`'s own `0x80093800` section.

```
in range 55 / 55      out of range 0
```

Spot rows: id 1 → BOSS001, entry `0x800C1E50`, size 2684 (`0x800C1800..0x800C2274`) ✓;
id 34 → BOSS034, `0x800C1EA8`, 3936 ✓; id 55 → BOSS055, `0x800C2488`, 7676 ✓;
id 19/20 → BOSS019/020, `0x800C23F8`/`0x800C26DC`, 5588 ✓ (both near the top of
the largest image, as expected for a shared 3-boss build).
Entry 0 = `0x800A8B58`, inside the engine image — the exact `Magic_EffectTable`
row-0 convention.

### 5.2 File ids resolve

41/41 `Boss_FileTable` entries resolve through `analysis/file_ids.json`:
row 0 → `BIN/BATTLE/BATTLE.EMI`, rows 1..40 → 40 distinct `BIN/BOSS/BOSS*.EMI`,
covering every BOSS file on the disc exactly once.

### 5.3 Section shape of the 40 BOSS files

Every BOSS file has exactly one code/data section at each of
`0x80014000` (data), `0x8002EE00` (data), `0x80093800` (code), `0x800C1800`
(code), `0x800F0800` (data), `0x801D0C00` (code) — 40/40 each. The
`0x80093800` and `0x801D0C00` sections are **one md5 across all 40 and equal to
`BATTLE.EMI`'s** (`4065db04…` / `8a80230e…`). `0x800C1800` is used by BOSS files
and by nothing else on the disc (40/40, 0 from any other directory).

**Dedup trap (same as BMAGIC):** the 40 `0x800C1800` sections are only 35
distinct md5s, so `overlay_captures_all.json` holds 35 BOSS captures with
registry ids `0x11E..0x140`. The collisions are
`BOSS014 = BOSS046`, `BOSS018 = BOSS019 = BOSS020`, `BOSS025 = BOSS027`,
`BOSS035 = BOSS047`. Join by section md5, never by filename.

---

## 6. Where the encounter id lives in RAM (boss-dialer harness)

| cell | width | meaning |
|---|---|---|
| `0x801462E6` | u8 | **boss id, 0 = random encounter.** Written only by `Battle_StartBoss 0x801C8A4C`; cleared at `GAME 0x80198174 / 0x8019910C`, `BATL_OVR 0x801EF118` |
| `0x80146316` | u16 | `\|= 0x1000` requests the battle transition |
| `0x80145E8D` | u8 | party leader state, set to 5 by the same setter |
| `0x80146321` | u8 | battle flags copied from record `+0x00` (`0x80146320` zeroed alongside) |
| `0x801462E8` | u8 | arena/camera id from record `+0x01` |
| `0x80143F00` | u16 | area number (already documented) — picks `ENEMY`/`AREA` |
| `0x80146464` | u16 | the loader's file-id cell (`tools/load_watch.py` / `tools/resident.py`) |

A harness only needs to reproduce the setter: write `boss_id` to `0x801462E6`,
`5` to `0x80145E8D`, zero `0x80145E8E/8F/90`, OR `0x1000` into `0x80146316`, and
copy `u8[0x801CDF18 + id*4]` to `0x80146321` with `0x80146320 = 0`. Everything
downstream (file choice, formation, arena, entry pc) is table-driven off the one
byte. A `--watch 0x80146464` should then show `0x1B3..0x1DA`, and
`tools/resident.py` should report registry id `0x11E..0x140` at `0x800C1800`.

Caveat: there is no bounds check anywhere on the path, and the boss record also
selects a formation row in the **current area's** `0x800E4000` table, so dialing
a boss from the wrong area will index a formation that was authored for another
fight. Dial from the area the scenario normally triggers it in.

---

## 7. Negative results and closed false leads

- **`0x8014DC30` is not a boss loader.** It is called with `a0 = 0x1BD`,
  `0x1C7`, `0x1D1`, `0x1C1` from AREA `#13` sections and from `BOSS034#16` —
  values that sit inside the BOSS file-id range and look exactly like a boss
  pick. It is not: across all images it has **117 call sites** with immediates
  spanning **24..792**, far outside `0x1B3..0x1DA`. It is a key→record lookup
  over `count = u8[0x800E3800]`, `base = u32[0x801459F0]`, **stride 8**
  (`+0x00 u16` key, `+0x02 u16`, `+0x04 u8`, `+0x05 u8`, `+0x06 u8`, `+0x07 u8`)
  that fills the scratchpad context at `u32[0x1F800044]+0x24..+0x2C`, plus a
  second `u16`-stride table at `0x80181DFC` indexed by the key. `0x800E3800`
  is the per-AREA section that `docs/IDEAS.md` already flags as the candidate
  **world-map / area node list** — this is that table's reader, and it is the
  natural next target for that TODO.
- **`0x80182830` is the BGM table**, not a boss/encounter table. Stride 4:
  `+0x00 u16` file id, `+0x02 u8` sequence, `+0x03 u8` sub-song; indexed by the
  song id `u8[0x80145025]`; readers `0x801625AC`, `0x80162610`, `0x801626C0`,
  `0x80162710`. Entry 0 = `0x0D1` `BIN/BGM/BGM000.EMI`; all sampled entries
  resolve to `BIN/BGM/*`.
- **No encounter→(enemy file, boss file) pair record exists.** The two are
  independent: `ENEMY` is a pure function of the area and is suppressed for
  bosses; `BOSS` is a pure function of the boss id. The only "pair" is the boss
  record's formation index, which points at the *area's* enemy-id list.
- **`BOSS` images are not entered through their header entry table** (§3).

### Other file-id formulas found along the way (all immediate/linear, for completeness)

| formula | files | site |
|---|---|---|
| `area + 0x009` | `BENEMY/ENEMY000..199` | `BATTLE.EMI#3 0x801D1734` |
| `area + 0x2AB` | `WORLD0*/AREA000..199` | `BATL_END#0 0x801EF68C`, `BATTLE#3 0x801D710C`, `GAME#0 0x801A0BB0` |
| `chapter + 0x295` | `SCENARIO/SCENA00..` | `GAME#0 0x801A881C` (`chapter = s8[0x8014686C]`) |
| `idx + 0x26A` / `+0x1DB` / `+0x1EE` / `+0x27D` | `PLCHAR/PL*`, `BPLCHAR/BPLD*`, `BPLCHAR/BPLU*`, `PLCHAR/PLP*` | `0x80167C04` (boot), selector `a1` = 0..3 |
| `chapter < 8 ? 0x006 : 0x007` | `BATTLE.EMI` / `BATTLE2.EMI` | `GAME#0 0x80198DD0` |

---

## 8. Suggested names (not applied — read-only session)

```
0x801462E6  Battle_BossId            u8   (docs/BATTLE_RAM.md already says "boss flag")
0x801C8A4C  Battle_StartBoss         GAME.EMI#0
0x801CDF18  Boss_EncounterTable      56 x 4
0x801CDFF8  Boss_FileTable           41 x u16 (disc-file ids)
0x800B2048  Boss_EntryTable          56 x u32 (BATTLE.EMI#15 / every BOSS.EMI 0x80093800)
0x800A8AD4  Battle_SetupEncounter    BATTLE.EMI#15
0x800A8B10  Battle_SetupBoss
0x800A8E8C  Battle_BuildBossFormation
0x800E4000  Area_FormationTable      stride 9, from the AREA file
0x80182830  BGM_Table                stride 4 (file id, seq, sub)
0x8014DC30  Area_NodeLookup          stride 8 over u32[0x801459F0], count u8[0x800E3800]
0x8014686C  Scenario_Chapter         s8
```
