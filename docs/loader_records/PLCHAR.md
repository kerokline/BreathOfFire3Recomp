# PLCHAR / PLP overlays — who loads them, how the number is chosen, how they are entered

**Status:** the chain is **proven statically end-to-end** (19/19 on every table,
plus the developers' own error string). Read-only research, 2026-09-12. Nothing
in the repo was modified; Ghidra was not launched.

## TL;DR — the answer, and why it is not the `Magic_EffectTable` shape

There is **no per-character record carrying `{file id, entry pc}`**. PLCHAR is
not keyed by character id at all. It is keyed by the **whole party as one unit**:
19 pre-authored 3-character combinations, numbered 0..18, and four parallel
families of 19 contiguous disc files:

| family | id base | files | what |
|---|---|---|---|
| `BIN/BPLCHAR/BPLD<combo>.EMI` | `0x1DB` | 19 | battle models, "D" set |
| `BIN/BPLCHAR/BPLU<combo>.EMI` | `0x1EE` | 19 | battle models, "U" set |
| `BIN/PLCHAR/PL<combo>.EMI` | `0x26A` | 19 | field models/animation (`0x80033800` data) |
| `BIN/PLCHAR/PLP<combo>.EMI` | `0x27D` | 19 | **field behaviour code, band `0x801CE400`** |

The file id is formed by pure arithmetic — `base + combo_index` — so there is no
id field to find. The only table on the load side is the combo table that turns
three character ids into the index. The entry side is two resident `u32[19]`
function-pointer tables in `GAME.EMI`.

This also closes the OVERLAY_HEADERS "Open" item *"the `BPLCHAR` picks
(`0x201/0x205`, `0x23C/0x23D/0x23F`…) — character battle models by form, not read
yet"*: those immediates are unrelated single files; the real BPLCHAR selection is
`0x1DB`/`0x1EE` + combo index through the same `0x80167C04`.

---

## 1. Who loads it, and how the number is chosen

### 1.1 `PLCHAR_ResolveCombo(c0, c1, c2)` — boot EXE `0x80167970`  *(proven)*

Takes three **character ids** (the same id space as the `0x80144F56` party ids
and the `0x80182488` char-id→roster table: 0..6 roster, 7/8/9/14 alternate forms,
10 = パピー). Returns the combo index 0..18 in `v0`.

```
0x80167984: A0E40000  sb   $a0,0($a3)          ; scratchpad 0x1F800000 = c0
0x80167994: A0250001  sb   $a1,1($at)          ;            0x1F800001 = c1
0x8016799C: A0260002  sb   $a2,2($at)          ;            0x1F800002 = c2
0x801679A0: 90830000  lbu  $v1,0($a0)          ; cur = u8[0x80145020]
0x801679A8: 10620025  beq  $v1,$v0,0x80167A40  ; cur == 0xFF -> nothing resident
0x801679BC: 250824AC  addiu $t0,$t0,0x24AC     ; $t0 = 0x801824AC   <-- COMBO TABLE
0x801679D8: 3063007F  andi $v1,$v1,0x7F        ; row = cur & 0x7F
0x801679DC: 00031040  sll  $v0,$v1,1
0x801679E0: 00431021  addu $v0,$v0,$v1         ; row * 3
0x801679E4: 00481821  addu $v1,$v0,$t0         ; &0x801824AC[row*3]
...   fast path: if all three requested ids are already in the resident row, return cur
0x80167A74..0x80167AF0                          ; else: 3-element bubble sort of c0..c2 ascending
0x80167AF8: 24080013  addiu $t0,$zr,0x13       ; 0x13 = 19 rows
0x80167B0C: 25CE24AC  addiu $t6,$t6,0x24AC     ; linear search of the 19 rows
0x80167BE4: 0C059DDB  jal  0x8016776C          ; not found -> on-screen panic
0x80167BEC: 02001021  addu $v0,$s0,$zr         ; return index (0xFF if not found)
```

`0x8016776C` is the developers' own failure screen — it formats the three ids
with the strings at `0x80149F9C` / `0x80149FAC`:

```
0x80149F9C: "FILE NOT FOUND\0"
0x80149FAC: "ID %02X/%02X/%02X\0"
```

Independent confirmation of what the function is for.

### 1.2 `PLCHAR_ComboTable` — boot EXE `0x801824AC`  *(proven, 19/19)*

**Base `0x801824AC`, stride 3, count 19, field: `u8 char_id[3]` ascending.**
It sits immediately after the char-id→roster table `0x80182488` (0x24 bytes).

| idx | bytes | suffix | PL | PLP | PLP registry id |
|---:|---|---|---|---|---|
| 0 | `00 01 02` | `012` | `0x26A` | `0x27D` | `0x021` |
| 1 | `00 01 05` | `015` | `0x26B` | `0x27E` | `0x022` |
| 2 | `00 01 06` | `016` | `0x26C` | `0x27F` | `0x023` |
| 3 | `00 02 05` | `025` | `0x26D` | `0x280` | `0x024` |
| 4 | `00 02 06` | `026` | `0x26E` | `0x281` | `0x025` |
| 5 | `00 03 04` | `034` | `0x26F` | `0x282` | `0x026` |
| 6 | `00 05 06` | `056` | `0x270` | `0x283` | `0x027` |
| 7 | `02 04 07` | `247` | `0x271` | `0x284` | `0x028` |
| 8 | `02 05 07` | `257` | `0x272` | `0x285` | `0x029` |
| 9 | `02 06 07` | `267` | `0x273` | `0x286` | `0x02A` |
| 10 | `02 07 08` | `278` | `0x274` | `0x287` | `0x02B` |
| 11 | `02 07 0A` | `27A` | `0x275` | `0x288` | `0x02C` |
| 12 | `03 04 09` | `349` | `0x276` | `0x289` | `0x02D` |
| 13 | `04 05 07` | `457` | `0x277` | `0x28A` | `0x02E` |
| 14 | `04 06 07` | `467` | `0x278` | `0x28B` | `0x02F` |
| 15 | `04 07 08` | `478` | `0x279` | `0x28C` | `0x030` |
| 16 | `05 06 07` | `567` | `0x27A` | `0x28D` | `0x031` |
| 17 | `05 07 08` | `578` | `0x27B` | `0x28E` | `0x032` |
| 18 | `06 07 08` | `678` | `0x27C` | `0x28F` | `0x033` |

**Verification: 19/19.** The three bytes of every row are exactly the three hex
digits of the filename suffix (`0A` = `A` in `PLP27A`), and the ordinal position
of every row equals `file_id - base` for all four families *and*
`registry_id - 0x021`. Raw bytes:

```
801824AC: 00 01 02 00 01 05 00 01 06 00 02 05 00 02 06 00
801824BC: 03 04 00 05 06 02 04 07 02 05 07 02 06 07 02 07
801824CC: 08 02 07 0A 03 04 09 04 05 07 04 06 07 04 07 08
801824DC: 05 06 07 05 07 08 06 07 08
```

### 1.3 `PLCHAR_Load(index, kind)` — boot EXE `0x80167C04`  *(proven)*

The only `jal File_LoadRequest` site in the whole game that reaches a PLCHAR
file (`0x80167CA4`). `a0` = combo index, `a1` = kind:

```
0x80167C28: 14600003  bne  $v1,$zr,0x80167C38     ; kind != 0 ?
0x80167C2C: 34C20080  ori  $v0,$a2,0x80           ;   (ds) index | 0x80
0x80167C34: A0E20000  sb   $v0,0($a3)             ; kind==0 -> u8[0x80145020] = index|0x80
0x80167C38: A0E40000  sb   $a0,0($a3)             ; kind 1/2 -> u8[0x80145020] = index
                                                  ; kind==3 -> no write at all
0x80167C84: 2484026A  addiu $a0,$a0,0x26A         ; kind 0 -> PL<combo>.EMI
0x80167C90: 248401DB  addiu $a0,$a0,0x1DB         ; kind 1 -> BPLD<combo>.EMI
0x80167C9C: 248401EE  addiu $a0,$a0,0x1EE         ; kind 2 -> BPLU<combo>.EMI
0x80167CA0: 2484027D  addiu $a0,$a0,0x27D         ; kind 3 -> PLP<combo>.EMI
0x80167CA4: 0C058A73  jal  0x801629CC             ; File_LoadRequest(file_id)
```

Any other `kind` falls through to `0x80167CAC` and loads nothing.

**`0x80145020` is the PLCHAR residency cell**, not a "form byte" in the loose
sense `BATTLE_RAM.md:314` gives it: low 7 bits = combo index 0..18 into
`0x801824AC`, bit 7 = "the `PL` family is the resident one", `0xFF` = nothing
resident. `0xFF` is written by boot `0x8014EA20` (inside the `FIRST.EMI`
game-mode function `0x8014E974`) and by `GAME.EMI#1` `0x801D0FD4`.

### 1.4 The wrappers above it

| addr | image | signature | effect |
|---|---|---|---|
| `0x801678B4` | boot | `(c0,c1,c2)` | resolve; if `(u8[0x80145020] & 0x7F) != index` → `PLCHAR_Load(index, 3)` (PLP) |
| `0x801678FC` | boot | `(c0,c1,c2,kind)` | resolve; residency check (against `index\|0x80` when `kind==0`) → `PLCHAR_Load(index, kind)` |
| `0x80167800` | boot | `(c0,c1,c2,kind)` | `kind==0` → `0x801678B4`; else → `0x801678FC`; then spins on `File_LoadDone` `0x801636F0` |

`0x80167800` has **91 callers**: `GAME.EMI#0 0x80198740`, `SHOP.EMI#0`,
`START.EMI#8`, and every `SCENARIO/SCENA00..19` overlay (the scripted party
changes). The `GAME.EMI` caller shows where the triple comes from:

```
0x8019872C: 90844F56  lbu $a0,20310($a0)   ; -> 0x80144F56   party id slot 0
0x80198734: 90A54F57  lbu $a1,20311($a1)   ; -> 0x80144F57   party id slot 1
0x8019873C: 90C64F58  lbu $a2,20312($a2)   ; -> 0x80144F58   party id slot 2
0x80198740: 0C059E00  jal 0x80167800
0x80198744: 00003821  addu $a3,$zr,$zr     ; (ds) kind = 0  -> PLP
```

`PLCHAR_Load` is also called **directly** (15 sites) with the already-resolved
index read back out of `0x80145020`, to pull a different family for the same
party — e.g. `GAME.EMI 0x801993E0`:

```
0x801993E4: 90845020  lbu $a0,20512($a0)   ; -> 0x80145020
0x801993E8: 00002821  addu $a1,$zr,$zr     ; kind = 0 -> PL<combo>.EMI
0x801993F8: 0C059F01  jal 0x80167C04
0x801993FC: 3084007F  andi $a0,$a0,0x7F
```

Direct callers of `0x80167C04`: boot ×2 (`0x801678E4`, `0x80167954`),
`GAME.EMI#0` ×7 (`0x80198784 0x80198BC0 0x801993F8 0x801995FC 0x8019986C
0x80199A2C 0x801A8DB8`), `START.EMI#8` ×2, `BATL_END.EMI#0 0x801EED78`,
`BATTLE.EMI#3 0x801D709C`, `MAGIC131.EMI#3 0x801EF39C`,
`COMMU00.EMI#0 0x801F1834`.

**So there is exactly one `File_LoadRequest` call site for all four PLCHAR
families: `0x80167CA4`.** It never appears in the Ghidra `call_sites` export
because `a0` is computed — which is why the id had not turned up by the usual
route.

---

## 2. How a loaded PLP image is entered

**Not through the overlay header.** All 19 PLP captures have
`header_entry_pcs == []`; the header is just the registry id at `+0x00`, code
from `+0x04`.

Entry is through **two resident `u32[19]` function-pointer tables at the tail of
`GAME.EMI#0`**, indexed by the same residency byte:

| | address | stride | count | index expression | how used |
|---|---|---:|---:|---|---|
| **Table A** | `0x801CD8F0` | 4 | 19 | `(u8[0x80145020] & 0x7F) * 4` | `jalr` at `0x801B46B0` |
| **Table B** | `0x801CD964` | 4 | 19 | same | `jalr` at `0x801B3C78` and `0x801BE508` |

```
; GAME.EMI#0, table B read + call (identical shape at 0x801B3C54 and 0x801BE4E4)
0x801BE4E8: 90425020  lbu   $v0,20512($v0)     ; -> 0x80145020
0x801BE4F0: 3042007F  andi  $v0,$v0,0x7F
0x801BE4F4: 00021080  sll   $v0,$v0,2
0x801BE4F8: 3C01801D  lui   $at,0x801D
0x801BE4FC: 00220821  addu  $at,$at,$v0
0x801BE500: 8C22D964  lw    $v0,-9884($at)     ; 0x801CD964 + idx*4
0x801BE508: 0040F809  jalr  $ra,$v0

; table A
0x801B468C: 90425020  lbu   $v0,20512($v0)
0x801B46A8: 8C22D8F0  lw    $v0,-10000($at)    ; 0x801CD8F0 + idx*4
0x801B46B0: 0040F809  jalr  $ra,$v0
```

The `0x801BE508` site is already in the Ghidra output, in `FUN_801be38c`
(`analysis/ghidra/GAME_EMI0_80196800_decomp/801BE38C_FUN_801be38c.c:47`):

```c
(**(code **)(&DAT_801cd964 + (DAT_80145020 & 0x7f) * 4))();
```

**Verification: 38/38.** Every entry of both tables lands inside the code
section of the PLP file at the matching index, checked against
`analysis/emi_sections.json` (`dest` + `size`) joined through
`analysis/file_ids.json`: Table A **19/19**, Table B **19/19**.
`A[i] - B[i] == 0x44` for all 19 (B is a 68-byte function ending immediately
before A).

| idx | file | size | image end | A | B |
|---:|---|---:|---|---|---|
| 0 | PLP012 | 6616 | 801CFDD8 | 801CFD3C | 801CFCF8 |
| 1 | PLP015 | 6112 | 801CFBE0 | 801CFB40 | 801CFAFC |
| 2 | PLP016 | 8872 | 801D06A8 | 801D05EC | 801D05A8 |
| 3 | PLP025 | 7172 | 801D0004 | 801CFF64 | 801CFF20 |
| 4 | PLP026 | 9932 | 801D0ACC | 801D0A10 | 801D09CC |
| 5 | PLP034 | 8036 | 801D0364 | 801D02B0 | 801D026C |
| 6 | PLP056 | 9428 | 801D08D4 | 801D0814 | 801D07D0 |
| 7 | PLP247 | 5964 | 801CFB4C | 801CFAB8 | 801CFA74 |
| 8 | PLP257 | 6968 | 801CFF38 | 801CFE98 | 801CFE54 |
| 9 | PLP267 | 9728 | 801D0A00 | 801D0944 | 801D0900 |
| 10 | PLP278 | 6412 | 801CFD0C | 801CFC70 | 801CFC2C |
| 11 | PLP27A | 5444 | 801CF944 | 801CF8BC | 801CF878 |
| 12 | PLP349 | 4676 | 801CF644 | 801CF5A8 | 801CF564 |
| 13 | PLP457 | 5460 | 801CF954 | 801CF8BC | 801CF878 |
| 14 | PLP467 | 8220 | 801D041C | 801D0368 | 801D0324 |
| 15 | PLP478 | 4904 | 801CF728 | 801CF694 | 801CF650 |
| 16 | PLP567 | 9224 | 801D0808 | 801D0748 | 801D0704 |
| 17 | PLP578 | 5908 | 801CFB14 | 801CFA74 | 801CFA30 |
| 18 | PLP678 | 8668 | 801D05DC | 801D0520 | 801D04DC |

(PLP27A and PLP457 legitimately share `801CF8BC` / `801CF878` — different
images, equal entry offsets from the band base.)

### 2.1 A third level: the per-slot table at the image tail  *(proven, 19/19)*

Both A and B are **thunks with byte-identical shape in all 19 images**:

```
; PLP012, A = 0x801CFD3C
0x801CFD3C: 3C021F80  lui   $v0,0x1F80
0x801CFD40: 8C420044  lw    $v0,68($v0)       ; ctx = u32[0x1F800044]  (party-member context)
0x801CFD4C: 9442002C  lhu   $v0,44($v0)       ; i = u16[ctx + 0x2C]
0x801CFD54: 00021080  sll   $v0,$v0,2
0x801CFD58: 3C01801D  lui   $at,0x801D
0x801CFD60: 8C22FDCC  lw    $v0,-564($at)     ; u32[0x801CFDCC + i*4]  (= image_end - 0x0C)
0x801CFD68: 0040F809  jalr  $ra,$v0
```

`0x1F800044` is the scratchpad pointer to the working party-member context
`C = 0x80145E8C + slot*0x140` (STATUS.md 2026-09-05,
`Battle_InitPartyContexts`).

Pattern match across all 19 images: **A 19/19, B 19/19**, and in every image

- B's sub-table base = `image_end - 0x18` (3 words)
- A's sub-table base = `image_end - 0x0C` (3 words)
- `A_table - B_table == 12` in all 19, both bases inside the image 19/19

i.e. the last 6 words of every PLP image are a `u32[2][3]` dispatch table: two
handler groups × three party slots. Example (PLP012):

```
801CFDC0: 801CE404 801CF12C 801CF500   <- B group (slots 0,1,2)
801CFDCC: 801CE72C 801CF338 801CF70C   <- A group (slots 0,1,2)
801CFDD8: <end of image>
```

Ahead of those six words each image has a further run of 11..25 aligned
pointers (starting at `image_end - 0x44` .. `- 0x7C` depending on the image),
2–3 of which point *out* of the band at `GAME.EMI 0x801B3D4C` — a shared default
handler. The grouping inside that longer run is **not** established here.

---

## 3. Every pointer table landing in `0x801CE400..0x801D0C00`

Scan of all aligned 32-bit words in the boot EXE and in every compiled section
of `analysis/overlay_captures_all.json` (406 captures):

| image | load range | words in band |
|---|---|---:|
| **boot `disc/SLPS_009.90`** | `80093800..80182F5C` | **0** |
| `BIN/ETC/GAME.EMI#0` | `80196800..801CE0E4` | **38** (= tables A and B, nothing else) |
| `BIN/ETC/GAME.EMI#1` | `801D0C00..801D1CB2` | 0 |
| `LOGO/LOGO.EXE#0` | `801CE000..801EB800` | 10 (self-references; LOGO.EXE occupies the same addresses, unrelated) |
| every other image | — | 0 |

**The boot EXE holds no pointer into the PLCHAR band at all.** Firm negative:
the band is entered only from `GAME.EMI`, through the two tables above, and from
inside the resident PLP image itself.

---

## 4. Candidate summary

| # | table | address | stride | count | fields | file id formed | entry pc field | verification | confidence |
|---|---|---|---:|---:|---|---|---|---|---|
| 1 | `PLCHAR_ComboTable` | `0x801824AC` (boot) | 3 | 19 | `u8 char_id[3]`, ascending | indirectly: row ordinal + `0x1DB`/`0x1EE`/`0x26A`/`0x27D` | no | 19/19 rows equal the filename digits; ordinal == `file_id - base` for all four families == `registry_id - 0x021` | **proven** |
| 2 | `PLCHAR_EntryTableA` | `0x801CD8F0` (`GAME.EMI#0`) | 4 | 19 | `u32 entry_pc` | — | **yes** | 19/19 inside the code section of `PLP<combo>.EMI` at the same index; `jalr` `0x801B46B0` | **proven** |
| 3 | `PLCHAR_EntryTableB` | `0x801CD964` (`GAME.EMI#0`) | 4 | 19 | `u32 entry_pc` | — | **yes** | 19/19 inside; `A[i]-B[i]==0x44`; `jalr` `0x801B3C78`, `0x801BE508`; matches the existing Ghidra decompile | **proven** |
| 4 | per-image slot table | `image_end - 0x18` | 4 | 3 + 3 | `u32 handler[2][3]`, index `u16[ctx+0x2C]` | — | yes (interior) | thunk shape 19/19; both sub-table bases inside the image 19/19 | **proven** for the last 6 words |
| 5 | longer tail run | `image_end - 0x44 .. - 0x7C` | 4 | 11..25 | unknown grouping | — | mixed (2–3 entries → `GAME.EMI 0x801B3D4C`) | run boundary measured, semantics not | **speculative** |
| — | a per-character (roster 0..7) function table into the band | — | — | — | — | — | — | whole boot EXE + `GAME.EMI` scanned: **does not exist** | **proven negative** |

## 5. Corrections / additions to existing docs (not applied — read-only run)

- `docs/BATTLE_RAM.md:314` calls `0x80145020` a "form byte". It is the PLCHAR
  residency cell: `& 0x7F` = combo index 0..18 into `0x801824AC`, bit 7 = the
  `PL` family is resident, `0xFF` = none. The doc's "`& 0x7F` = 5 or 0xC exempts
  Peco" note reads naturally now: combos 5 (`034`) and 12 (`0x0C`, `349`) are the
  two rows with no Peco (id 6) in them.
- `docs/OVERLAY_HEADERS.md` "Open" → *the `BPLCHAR` picks … chosen by a form byte
  `< 2`*: answered. `kind` 1/2 in `PLCHAR_Load 0x80167C04` selects `BPLD`
  (`0x1DB`) vs `BPLU` (`0x1EE`) for the same combo index.
- Candidate `symbols.toml` / `names/*.toml` rows:
  `PLCHAR_ResolveCombo 0x80167970`, `PLCHAR_ComboNotFound 0x8016776C`,
  `PLCHAR_Load 0x80167C04`, `PLCHAR_LoadPLP 0x801678B4`,
  `PLCHAR_LoadKind 0x801678FC`, `PLCHAR_LoadPartyBlocking 0x80167800`;
  data `PLCHAR_ComboTable 0x801824AC`, `PLCHAR_Resident 0x80145020`,
  `PLCHAR_EntryTableA 0x801CD8F0`, `PLCHAR_EntryTableB 0x801CD964`.
- The 19 `names/overlays.toml` PLCHAR rows can now be named by party
  composition instead of filename, using the combo table + roster names
  (0 リュウ, 1 ニーナ, 2 ガーランド, 3 ティーポ, 4 レイ, 5 モモ, 6 ペコロス,
  7/8/9/14 alternate forms, 10 パピー).

## 6. Open

- What A vs B are (two per-frame phases? update vs draw?). Both are called from
  `GAME.EMI` field code; `0x801BE38C` calls B only when a cutscene/flag gate is
  clear and writes `ctx[299] = 0` instead when it is set.
- The grouping of the longer tail-pointer run in each PLP image, and what
  `GAME.EMI 0x801B3D4C` is (the shared handler 2–3 slots point at).
- `u16[ctx + 0x2C]` is *assumed* to be the party-slot/model index 0..2 because
  the sub-tables have exactly 3 entries. Not observed live.
- A live confirmation is cheap and would move this to `verified`:
  `tools/load_watch.py` (write trace on `0x80146464`) plus a watch on
  `0x80145020` across a scripted party change should show `0x27D + index`, then
  the band header word at `0x801CE400` going to `0x021 + index`.

## Method

All static. `disc/SLPS_009.90` (load `0x80093800`, header `0x800`) and the 406
compiled sections in `analysis/overlay_captures_all.json` were scanned for
(a) `jal 0x801629CC` = `0x0C058A73` — 65 sites game-wide, of which the PLCHAR
one is `0x80167CA4`; (b) aligned words inside `0x801CE400..0x801D0C00`;
(c) `lui`/`lw` pairs resolving to the candidate table addresses;
(d) `addiu` immediates equal to the four family id bases. Joins used
`analysis/emi_sections.json` (dest/size/md5) and `analysis/file_ids.json`.
Disassembly via `tools/disasm_exe.py` (with `--exe` / `--load` / `--header 0`
for the overlay images).
