# SCENARIO overlays: who loads them, how they are entered, and the record tables

**Status:** static analysis only, 2026-09-12. No Ghidra, no build, no writes to the repo.
Evidence = the staged boot EXE `disc/SLPS_009.90` and the 406 compiled sections in
`analysis/overlay_captures_all.json` (decoded from `bytes_b64` and disassembled
directly), cross-checked against `analysis/file_ids.json` and
`analysis/emi_sections.json`.

## Summary

The SCENARIO path is the **same two-table shape as the spell path**, but split
differently: the *file id* comes from a single global byte, and the *entry pc*
comes from a table in GAME.EMI that is indexed by that same byte.

```
n        = s8 [0x8014686C]                    Scenario_Number      (0..19, signed byte)
file_id  = n + 0x295                          SCENA<nn>.EMI        (0x295..0x2A8)
record   = u32[0x801C944C + n*4]              Scenario_EntryTable  (in GAME.EMI, 20 entries)
entry_pc = u32[record + 0x00 .. +0x10]         5-slot vtable inside the loaded image
```

Verification: **20/20** table entries point inside the correct `SCENA<nn>.EMI`
code section; **89/89** non-zero vtable slots are pcs inside that same section;
**0** invalid. Two further per-scenario tables (`0x801CDC4C`, `0x801CDC9C`) add
211 more verified in-image pcs. Confidence: **proven** (static, exhaustive, 0
counter-examples).

Negative result: **there is no script opcode that computes a SCENARIO file id.**
No `File_LoadRequest` call site anywhere forms an id in `0x290..0x2A8` except the
five listed below, and none of them takes a script operand.

---

## 1. Who loads `SCENA<nn>.EMI`, and how the number is chosen

### 1.1 The only loader

`Scenario_LoadRequest()` — **GAME.EMI `0x801A880C`** (band `0x80196800`):

```
801A880C  3C048014  lui   $a0,0x8014
801A8810  8084686C  lb    $a0,0x686C($a0)     ; n = (s8)*0x8014686C
801A8814  27BDFFE8  addiu $sp,$sp,-24
801A8818  AFBF0010  sw    $ra,16($sp)
801A881C  0C058A73  jal   0x801629CC           ; File_LoadRequest
801A8820  24840295  addiu $a0,$a0,661          ; +0x295  = SCENA00.EMI
```

`0x295` is `BIN/SCENARIO/SCENA00.EMI` and ids run contiguously to `0x2A8` =
`SCENA19.EMI` (`analysis/file_ids.json`). So `file_id = n + 0x295`, `n` in
`0..19`. Callers: `0x801A8794` (inside `Scenario_Set`, below) and START.EMI
`0x801E614C` (continue-from-save).

I scanned **every** compiled section plus the boot EXE for `jal 0x801629CC`
(65 sites) and constant-propagated `a0`. Only these five sites can produce a
SCENARIO id, all with immediates, none from a script operand:

| site | `a0` | file |
|---|---|---|
| GAME.EMI `0x801A881C` | `n + 0x295` | `SCENA00..19` (the loader) |
| SCENA10 `0x801F8C40` | `0x290` | `SCE10EFF.EMI` |
| SCENA15 `0x801FAFE0` / `0x801FB7C0` / `0x801FCC28` / `0x801FD090` | `0x291`/`0x292`/`0x293`/`0x294` | `SCE15EF0..3` |

(The `SCE15EF*` sub-loads were already known; `SCE10EFF` from SCENA10 at
`0x801F8C40` is the same pattern and appears not to be recorded yet.)

### 1.2 `0x8014686C` is the scenario number

`refscan` over all 407 images finds exactly **three writers** of `0x8014686C`:

| writer | what it does |
|---|---|
| GAME.EMI `0x801A0D48` / `0x801A0D60` | the advance: `n+1`, and `n+2` if that would be 16 |
| GAME.EMI `0x801A8728` (`Scenario_Set(a0)`) | stores the argument |
| SCENA17 `0x801F95DC` | forces `n = 15` (SCENA17 is a side branch that rejoins the timeline at 15) |

The advance, in the field loop function `0x801A0AA8` (called from `0x80198224`):

```
801A0D1C  lui  $v0,0x8014
801A0D20  lb   $v0,0x686D($v0)
801A0D28  andi $v0,$v0,0x0080      ; advance requested?
801A0D2C  beq  $v0,$zr,0x801A0D74
801A0D30  addiu $v1,$zr,16
801A0D38  lbu  $a0,0x686C($a0)     ; n
801A0D40  addiu $v0,$a0,1
801A0D48  sb   $v0,0x686C($at)     ; n = n+1
801A0D54  bne  $v0,$v1,0x801A0D64  ; ... unless that is 16
801A0D58  addiu $v0,$a0,2
801A0D60  sb   $v0,0x686C($at)     ; then n = n+2
801A0D68  lbu  $a0,0x686C($a0)
801A0D6C  jal  0x801A870C          ; Scenario_Set(n)
```

The request bit is set by `Scenario_RequestAdvance()` **`0x801A8900`**
(`*0x8014686D |= 0x80`), which is called from **16 of the 20 scenario overlays**
(SCENA00..SCENA15, one call each — `0x801FBE6C`, `0x801FC69C`, … `0x801FDB58`).
Scenario progression is therefore a linear chain driven by the running scenario
itself; **16 is reserved** and never reached by the advance.

Other entries into `Scenario_Set` `0x801A870C`:

| caller | `a0` | meaning |
|---|---|---|
| START.EMI `0x801E2464` | `0` | new game → SCENA00 |
| GAME.EMI#1 `0x801D0EC0` (band `0x801D0C00` mode thunk) | `16` | the reserved SCENA16, entered by game mode, not by the chain |
| GAME.EMI `0x801A0D6C` | `n+1`/`n+2` | the advance |

START.EMI `0x801E60A4` restores the state block on a load: it copies 16 bytes
from the save summary `0x801448D4` into `0x8014686C..0x8014687B`, then calls
`Scenario_LoadRequest`. This **identifies the four unlabelled u32 at
`0x8014686C..0x80146878`** recorded as unknown in `docs/BATTLE_RAM.md`
(block head) and HANDOFF row 9: the first byte is the scenario number and the
rest is the scenario state block.

### 1.3 `Scenario_Set` `0x801A870C` — the state block

```
0x8014686C  s8    scenario number n
0x8014686D  u8    flags; bit 0x80 = "advance requested" (set by 0x801A8900)
0x8014686E  u8    cleared on set
0x8014686F  u8    cleared on set
0x80146870  u8    cleared on set     (written by SCENA17 0x801F8598)
0x80146871  u8    cleared on set     (written by SCENA08 0x801FB6A8, SCENA15 0x801FCC20)
0x80146872  u16   cleared on set
0x80146874  u16   cleared on set
0x80146868  u32   = 0x80144E84 + n*8   pointer to this scenario's 8-byte progress record
                                        (the record is zeroed by Scenario_Set)
```

`Scenario_Set` then: `jal 0x801A880C` (issue the load) → spin on
`File_LoadDone` `0x801636F0` while pumping `0x8014B770` → `jal 0x801A8834`
(enter the overlay, §2).

Bonus, same cell: GAME.EMI `0x80198DD0` picks the **battle overlay** from the
scenario number — `n < 8` → file `0x006` `BATTLE.EMI`, `n >= 8` → file `0x007`
`BATTLE2.EMI`.

---

## 2. How a loaded SCENA image is entered — `Scenario_EntryTable` `0x801C944C`

`Scenario_Enter()` **GAME.EMI `0x801A8834`**:

```
801A8834  lui   $v0,0x8014
801A8838  lb    $v0,0x686C($v0)      ; n
801A8844  sll   $v0,$v0,2
801A8848  lui   $at,0x801D
801A884C  addu  $at,$at,$v0
801A8850  lw    $v0,-27572($at)      ; record = u32[0x801C944C + n*4]
801A8858  lw    $v0,0($v0)           ; entry  = u32[record + 0x00]
801A8860  jalr  $ra,$v0              ; <-- the indirect call into band 0x801F6C00
801A8868  jal   0x801A8BF8
```

So: **a record with an entry pc**, not a header entry table and not a fixed
offset. The header entry table (`docs/OVERLAY_HEADERS.md`) is *not* used here —
see §5.

The record is a **5-slot vtable**; GAME.EMI has one thunk per slot, all with the
identical `0x801C944C + n*4` prologue:

| slot | thunk | signature seen | callers |
|---|---|---|---|
| `+0x00` | `0x801A8834` | `void f(void)` | `0x80198380`, `0x8019A238`, `0x8019A370`, `0x801A0DF4`, `0x801A87EC` |
| `+0x04` | `0x801A8880` | `void f(obj*)`, guarded by `obj->0x7C & 0x4000` | `0x801A290C`, `0x801B4230` |
| `+0x08` | `0x801A891C` | `u8 f(a,b)` with fallback `0x801A9728` | `0x801B2028` |
| `+0x0C` | `0x801A89AC` | `u8 f(a,b)` with fallback `0x801A9B84` | `0x801B29FC`, and area overlays AREA104 `0x801F4F80`, AREA121 `0x801F54C4`, AREA189 `0x801F5930` |
| `+0x10` | `0x801A8A3C` | optional — null-checked (`beq $v0,$zr`) before the call | `0x801B731C` |

Verification of all 20 records (5 slots each):

```
SCENA00 rec=801FC9FC  801F913C 801FC7D0 801FC818 801FC8F4 00000000
SCENA01 rec=801FE288  801F7FC4 801FD444 801FDA6C 801FDA64 801FE03C
SCENA02 rec=801FE274  801F719C 801FD084 801FD780 801FD6F4 00000000
SCENA03 rec=801FCFC0  801F8DA8 801FC46C 801FC704 801FCCDC 801FCDB4
SCENA04 rec=801FA1F0  801F8124 801F9D48 801F9DB4 801F9DAC 801FA010
SCENA05 rec=801FD5C8  801F7A78 801FCA58 801FCD68 801FCD60 801FD110
SCENA06 rec=801FE3C4  801F7298 801FCDD0 801FD800 801FD294 801FDD14
SCENA07 rec=801FDDE0  801FA65C 801FD3BC 801FD67C 801FD944 801FDA7C
SCENA08 rec=801FE950  801FA294 801FE018 801FE170 801FE2A0 00000000
SCENA09 rec=801FE3CC  801F78D0 801FC5E4 801FC91C 801FD278 801FD280
SCENA10 rec=801FE884  801F7F50 801FD464 801FDB14 801FE00C 00000000
SCENA11 rec=801FAEDC  801F7288 801FA5B8 801FAB64 801FAA74 801FAB6C
SCENA12 rec=801FD1A4  801F7F28 801FC574 801FC890 801FC80C 801FCC54
SCENA13 rec=801FBF34  801F7D14 801FB350 801FB464 801FBA34 00000000
SCENA14 rec=801FC404  801F6FD8 801FB37C 801FB648 801FB84C 00000000
SCENA15 rec=801FE5F4  801F9CAC 801FDD80 801FE024 801FE18C 00000000
SCENA16 rec=801F8524  801F6C90 801F8344 801F838C 801F8394 00000000
SCENA17 rec=801F9770  801F775C 801F88C4 801F9714 801F890C 00000000
SCENA18 rec=801F6D58  801F6C04 801F6CAC 801F6CFC 801F6CF4 00000000
SCENA19 rec=801F6DBC  801F6C04 801F6D10 801F6D60 801F6D58 00000000
```

Entries `[20]`/`[21]` of the table are `0x801A8C34`/`0x801A8CB4` — GAME.EMI-
resident fallbacks; `[22]` is `0x0A000008`, i.e. the array ends at 20.

Confidence: **proven**. 20/20 records land in the matching `SCENA<nn>.EMI` code
section (`class = code`, `dest = 0x801F6C00`, sizes from
`analysis/emi_sections.json`); 89 non-zero slots, all in-image, 0 out of range.

### 2.1 Two more per-scenario tables (second-level dispatch)

`0x801CDC4C` and `0x801CDC9C`, both 20 entries, stride 4, indexed by the same
`n`, each entry a pointer to an **array of function pointers inside the SCENA
image**, indexed by a `u8` argument:

```
801C2DE8  Scenario_CallA(u8 k):   t = u32[0x801CDC4C + n*4]; f = u32[t + k*4]; jalr f
801C2E34  Scenario_CallB(u8 k):   t = u32[0x801CDC9C + n*4]; f = u32[t + k*4]; jalr f
```

Both are called **only from inside scenario overlays** (145 sites for A across
SCENA00..16 and one stray in BOSS013 `0x800C2588`; 90 sites for B) — they are a
scenario's "call my own sub-routine k" helper, routed through GAME.EMI so the
callee address is not baked into the caller.

| n | A `0x801CDC4C` | entries | B `0x801CDC9C` | entries |
|---:|---|---:|---|---:|
| 0 | `801FCA88` | 1 | `00000000` (none) | 0 |
| 1 | `801FE364` | 4 | `801FE370` | 1 |
| 2 | `801FE370` | 3 | `801FE374` | 2 |
| 3 | `801FD03C` | 3 | `801FD044` | 1 |
| 4 | `801FA234` | 3 | `801FA23C` | 1 |
| 5 | `801FD67C` | 16 | `801FD6A8` | 5 |
| 6 | `801FE49C` | 18 | `801FE4C4` | 8 |
| 7 | `801FDF90` | 4 | `801FDF98` | 2 |
| 8 | `801FE9CC` | 8 | `801FE9E8` | 1 |
| 9 | `801FE4F4` | 24 | `801FE52C` | 10 |
| 10 | `801FE9B4` | 10 | `801FE9CC` | 4 |
| 11 | `801FAF60` | 14 | `801FAF84` | 5 |
| 12 | `801FD24C` | 15 | `801FD274` | 5 |
| 13 | `801FBFC8` | 9 | `801FBFE8` | 1 |
| 14 | `801FC488` | 14 | `801FC4BC` | 1 |
| 15 | `801FE724` | 5 | `801FE734` | 1 |
| 16 | `801F855C` | 2 | `801F8560` | 1 |
| 17 | `801F9E28` | 2 | `801F9E2C` | 1 |
| 18 | `801F6D80` | 2 | `801F6D84` | 1 |
| 19 | `801F6DE4` | 2 | `801F6DE8` | 1 |

Array lengths are "words that are in-image aligned addresses" and are therefore
upper-bound estimates where A and B are adjacent (B's array usually starts right
after A's). In-image counts: A **20/20**, B **19/20** (index 0 is a genuine
null, matching SCENA00 having no B calls). Total pcs A+B = **211**.
Confidence: **proven** for the table shape and the pointer targets; **likely**
for the exact per-scenario array lengths.

---

## 3. Pointer tables whose targets are in overlay bands

Scan: every 4-byte-aligned word in the boot EXE, `GAME.EMI#0` and `GAME.EMI#1`
that falls into a band's occupied range, grouped into runs, then each run's base
matched against code that indexes it (`lui` + `addu` + `lw`/`lbu` tracking).

| address | image | index | stride / shape | targets | status |
|---|---|---|---|---|---|
| `0x801C944C` | GAME.EMI | scenario `n` `0x8014686C` | 4, 20 entries → record with 5 slots | `0x801F6C00` SCENARIO | **proven** (§2) |
| `0x801CDC4C` | GAME.EMI | scenario `n` | 4, 20 entries → array of pcs | `0x801F6C00` | **proven** (§2.1) |
| `0x801CDC9C` | GAME.EMI | scenario `n` | 4, 20 entries → array of pcs | `0x801F6C00` | **proven** (§2.1) |
| `0x801802EC` | **boot EXE** | area `u16[0x80143F00]` | 4, **200 entries** → record ≥0x48 bytes | `0x801F2C00` AREA | **proven**; already documented as the world-item table (`docs/WORLD_ITEMS.md`), but the record's low words are **entry pcs**, not data |
| `0x801C8F54` | GAME.EMI | row 0..10 from `0x8019B19C` | **28 (0x1C)**, 11 rows: 6 pcs at `+0x00..+0x14`, key `u8` area number at `+0x18` | `0x801F2C00` AREA | **proven** (§4) |
| `0x801C95BC` | GAME.EMI | same row 0..10 | 4, 11 entries | `0x801F2C00` AREA | **proven** (11/11) |
| `0x801C95E8` | GAME.EMI | `u8 obj[+0x7A]` | 4 | `0x801EEC00` band (COMMU/ETC occupant), one AREA-band entry | speculative |
| `0x801C8C04` | GAME.EMI | `u8 obj[+0x03]` | 4, 10 entries | all GAME.EMI-resident | not an overlay table |
| `0x801C93B4`, `0x801C96F4` | GAME.EMI | `u8 obj[+0x02]`, stride-8 table of 28 | 4 / 8 | all GAME.EMI-resident | not an overlay table |
| `0x801C8C80 .. 0x801C9700` (rest) | GAME.EMI | — | — | mixed `0x8019xxxx`, `0x801D0C00`, `0x801EEC00`, `0x801F2C00`, `0x801F6C00`, `0x80117000` | **unattributed**: dozens of pointer runs in this data region were not matched to indexing code; some are probably further area-keyed hook tables of the `0x801C8F54` family |
| `0x801CD8F0`, `0x801CD964` | GAME.EMI | — | 4, 19 entries each | `0x801CE400` PLCHAR (19 PLCHAR overlays) | **likely** a per-PLCHAR record pair, not chased |

### Area hook table `0x801C8F54` (the closest analogue to the spell record)

```
8019B19C  Area_HookRow():                  ; returns 0..11
  a1 = u16[0x80143F00]; a0 = 0; v1 = 0
  loop: v0 = u8[0x801C8F6C + a0]           ; key at record +0x18
        if (a1 == v0) return v1
        v1++; a0 += 0x1C; while (v1 < 11)
8019B1DC  Area_Hook14():  r = Area_HookRow(); return u32[0x801C8F68 + r*0x1C]
8019B240  (r*0x1C) -> lw 0x801C8F54 ... +0x14 ; then jalr
```

11 rows, key = area number, 6 entry pcs each. All 63 non-null pointers land
inside the keyed `AREA<nnn>.EMI` image:

| row | area | pcs |
|---:|---:|---|
| 0 | 16 | `801F2EEC 801F45CC 801F4178 801F341C 801F4768 801F4DA0` |
| 1 | 33 | `801F2E20 801F4500 801F40AC 801F3350 801F469C 801F4CC8` |
| 2 | 45 | `801F2EEC 801F45CC 801F4178 801F341C 801F4768 801F4DA4` |
| 3 | 65 | `801F2F24 801F4604 801F41B0 801F3454 801F47A0 801F4DE0` |
| 4 | 87 | `801F2F20 801F45FC 801F41A8 801F3450 801F4798 801F4DD4` |
| 5 | 88 | `801F3A50 801F512C 801F4CD8 801F3F80 801F52C8 801F591C` |
| 6 | 104 | `801F2FB0 0 0 801F34E0 801F4238 0` |
| 7 | 115 | `801F2EF0 801F45CC 801F4178 801F3420 801F4768 801F4D90` |
| 8 | 121 | `801F2F04 801F45E0 801F418C 801F3434 801F477C 801F64E8` |
| 9 | 151 | `801F2E5C 801F4538 801F40E4 801F338C 801F46D4 801F4D04` |
| 10 | 152 | `801F2DB0 801F448C 801F4038 801F32E0 801F4628 801F4C48` |

---

## 4. Verification counts

| table | entries | verified in the named file's code section | invalid | not checkable |
|---|---:|---:|---:|---:|
| `0x801C944C` records | 20 | 20 | 0 | 0 |
| `0x801C944C` vtable slots | 100 (89 non-zero) | 89 | 0 | 11 zeros |
| `0x801CDC4C` (A) records | 20 | 20 | 0 | 0 |
| `0x801CDC4C` (A) pcs | 159 | 159 | 0 | 0 |
| `0x801CDC9C` (B) records | 20 | 19 | 0 | 1 null (SCENA00) |
| `0x801CDC9C` (B) pcs | 52 | 52 | 0 | 0 |
| `0x801802EC` area records | 200 | 181 | 0 | 18 areas have no capture; area 30's capture is at band `0x801D0C00` |
| `0x801C8F54` hook pcs | 66 (63 non-zero) | 63 | 0 | 3 zeros |
| `0x801C95BC` | 11 | 11 | 0 | 0 |

Section bounds came from each capture's `load_addr` + `len(bytes)`, cross-checked
against `analysis/emi_sections.json` (`dest = 0x801F6C00`, `class = code`) for all
20 SCENA files.

## 5. Relation to the header entry table — a disjoint seed source

The 300 scenario entry pcs (vtable + A + B, duplicates included) versus the
extractor's existing seed sets in `analysis/overlay_captures_all.json`:

| already known as | count |
|---|---:|
| `header_entry_pcs` | **0** |
| `dispatch_entry_pcs` (harvested) | 17 |
| `static_discovery_entry_pcs` (JAL/prologue walk) | 235 |
| in any set | 247 |
| **new to all three** | **53** |

Zero overlap with the header table is the notable part: five of the 20 SCENA
images (00, 10, 12, 17, 18, 19) have an **empty** header entry table, and even
where it is populated the header never lists these pcs. The entry into a
scenario overlay is **not** header-driven — this is a distinct mechanism from
the one `docs/OVERLAY_HEADERS.md` seeds from. The same holds for the area hook
tables. Feeding `0x801C944C`/`0x801CDC4C`/`0x801CDC9C`/`0x801C8F54`/`0x801C95BC`
into `static_dispatch_entry_pcs` would add seeds the header pass cannot reach —
including SCENA12, whose unharvested interior entry `0x801F92F4` is the 59–62 %
interpreter hot spot recorded in `OVERLAY_HEADERS.md`.

## 6. Negative results (with evidence)

- **No script opcode requests a scenario.** All 65 `jal 0x801629CC` sites were
  disassembled with their `a0` setup; the only non-immediate forms are
  `n + 0x295` (scenario), `area + 0x2AB` (BATL_END `0x801EF68C`, BATTLE#3
  `0x801D710C`, GAME.EMI `0x801A0BB0`), `u16[0x800B3538 + row*8]` (the known
  spell path) and two indexed `lhu` loads in BATTLE#3/MAGIC131/MAGIC151. None
  reads a script operand.
- **No `File_LoadRequest` call site exists in any `AREA*.EMI` code section.**
  Area overlays never load a file themselves; they go through GAME.EMI.
- **No pointer table in GAME.EMI or the boot EXE targets the `0x800C1800`
  (BOSS) or `0x801CE400`-with-entry-record bands** beyond the two 19-entry
  PLCHAR runs noted above; `0x800C1800` has no pointer run at all in either
  image.
- The battle-engine convention (`u8` row table → `u16` file id + `u32` entry pc
  packed 8 bytes apart) has **no analogue** here: the scenario path keeps the
  file id implicit (`n + 0x295`) and the entry pc in a separate, differently
  indexed table.

## 7. Suggested names (not applied — this was a read-only pass)

| address | suggested name |
|---|---|
| `0x8014686C` | `Scenario_Number` (resolves the `0x8014686C..` block head in `BATTLE_RAM.md` / HANDOFF row 9) |
| `0x8014686D` | `Scenario_Flags` (bit `0x80` = advance requested) |
| `0x80146868` | `Scenario_ProgressPtr` (`= 0x80144E84 + n*8`) |
| `0x80144E84` | `Scenario_ProgressTable` (8 bytes per scenario) |
| `0x801A870C` | `Scenario_Set` |
| `0x801A880C` | `Scenario_LoadRequest` |
| `0x801A8834` | `Scenario_Enter` (vtable `+0x00`) |
| `0x801A8880` / `0x801A891C` / `0x801A89AC` / `0x801A8A3C` | `Scenario_Vtbl04/08/0C/10` |
| `0x801A8900` | `Scenario_RequestAdvance` |
| `0x801C944C` | `Scenario_RecordTable` (20 × u32 → 5-slot vtable) |
| `0x801CDC4C` / `0x801CDC9C` | `Scenario_SubTableA` / `Scenario_SubTableB` |
| `0x801C2DE8` / `0x801C2E34` | `Scenario_CallA` / `Scenario_CallB` |
| `0x801C8F54` | `Area_HookTable` (11 × 0x1C, key `u8` at `+0x18`) |
| `0x8019B19C` | `Area_HookRow` |
| `0x801C95BC` | `Area_HookTable2` (11 × u32) |
