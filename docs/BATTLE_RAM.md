# Battle RAM map and damage path — first data anchors

**Status:** IN PROGRESS (opened 2026-09-04, last extended 2026-09-05 with level-up, inventory, equipment, the save format, then turn order, kills/drops/results, the command menus, escape, enemy AI and `Effect_ApplyResult`; 2026-09-05 afternoon: the save-file verifier `tools/save_tool.py` checked the map against the three card saves and the Mednafen load screen, correcting three rows — `Flag_Test`, the play time, the ability lists — and reading the whole roster order off the record names). It began as one
evening: a `ramdiff` on an Attack anchor found the enemy HP cell, a
`capture --watch` on it named the writers, and the Ghidra bodies of those
writers gave the record layouts and the formula skeleton
([`GHIDRA.md`](GHIDRA.md), [`IDEAS.md`](IDEAS.md) I1). Offsets marked *?*
are read from one decompilation and not yet confirmed by a second route.
Addresses are JP SLPS-00990; the game-mode overlay is `BATTLE.EMI#3`
(md5 `8a80230e…`) at `0x801D0C00`.

## How the enemy HP was found

1. `ramdiff --slot 10 --press circle ×3` kept two RAM snapshots; the
   damage numbers read off the screen afterwards selected the 16-bit cells
   that dropped by exactly those amounts. Two cells matched for one enemy:
   `0x801EB74C` and `0x801484CC`.
2. `capture --watch` on both: in the same frame, `0x801EB74C` was written
   first (26 → 14) from store PC `0x801DBEAC` inside `0x801DBB40`, then
   `0x801484CC` from `0x801EA4D0` inside `0x801EA204`, whose arguments were
   `(0x801484C3, 0x801EB758, 0x801484D4, 0x801484CC)` — a gauge byte, the
   working max HP, and two HUD fields.
3. Decompiling the two writers settled which copy is which.

## Three record arrays

**Actor index convention.** Battle code takes `actor` as a byte: `0..2` are
the party slots, `3..` are enemies (`enemy = actor - 3`). Every function
below branches on `actor < 3`.

### Party working records — boot-EXE data, stride `0x140`

**Proven by `Battle_InitPartyContexts` (GAME.EMI `0x801C23F8`, battlebegin
trace + decompile):** each battle slot has a **context** `C = 0x80145E8C +
slot*0x140`, and at `C+0x74 = 0x80145F00 + slot*0x140` it holds a **verbatim
copy of the persistent character record** (`memcpy` of `0xA8` bytes from
`0x80144964 + roster*0xA4`). So every persistent offset below applies to
the working record too: HP `0x80145F14` = persistent `+0x14`, AP `+0x16`,
level `0x80145F06`, EXP `0x80145F08`, character id `0x80145F05` = `+5`.
Context-only fields sit before and after the copy:

`C` is the game's general **party actor object** (0x140 bytes), used on
the field and in battle alike: the full-battle trace (`battlebegin.json`,
22 114 writes, 43 writers) shows boot-EXE sprite code writing it every
frame in both phases, GAME.EMI writing it during the field/encounter
transition, and the battle overlay writing it from `Battle_Init` on.

| Address (slot 0) | `C+` | Field | Writers seen |
|---|---|---|---|
| `0x80145E8C` | `+0` | present flag (`1`) | `Actor_Task` every frame, `Battle_InitPartyContexts` |
| `0x80145E8D..90` | `+1..+4` | actor state bytes (`+1` = mode: `2` set by `Battle_InitMemberActor`) | field + battle state machines |
| `0x80145E91` | `+5` | battle slot index | `Battle_InitPartyContexts` |
| `0x80145E94` | `+8` | facing / direction (`DAT_801462E8` at battle start) | GAME `0x801B69AC`, `Battle_InitMemberActor` |
| `0x80145E95` | `+9` | animation state (124 writes each from two field functions) | GAME `0x801B1E3C`, `0x801C3530` |
| `0x80145E97` | `+0xB` | actor mode (`1` set by `Encounter_PlaceParty`; `0`/`1` selects the encounter branch) | GAME |
| `0x80145E98..EAC` | `+0xC..+0x20` | motion words (zeroed by `Battle_InitMemberActor`; `+0xC/+0x10/+0x14` written per frame while walking) | GAME `0x801C6790`/`0x801C3530` |
| `0x80145EB0` | `+0x24` | flags (bit 7 skips the screen-pos update) | |
| `0x80145EB5` | `+0x29` | sprite / model id (`4` in battle, `0x8014933A` on encounter) | `Battle_InitMemberActor`, `Encounter_PlaceParty` |
| `0x80145EB7` | `+0x2B` | sprite sub-id (indexes the 3-byte table at `0x8017FED4`) | |
| `0x80145EBA..EBE` | `+0x2E,+0x30,+0x32` | **screen position** (s16), recomputed every frame | `Actor_UpdateScreenPos` (10 824 writes) |
| `0x80145EC0`, `+0x38` | `+0x34,+0x38` | **world x, z** (32-bit fixed) | GAME `0x801C67AC` (field), `0x801DF3AC` (battle, 2 217 writes) |
| `0x80145ECA` | `+0x3E` | depth / sort key = boot `0x80155238(x, z)` | both |
| `0x80145ED4` | `+0x48` | zeroed at both inits | |
| `0x80145ED6..EE6` | `+0x4A,+0x58,+0x5A` | animation counters | `Actor_AnimTick` and siblings |
| `0x80145EE8..EEB` | `+0x5C..+0x5F` | colour / fade bytes | `Encounter_PlaceParty`, GAME `0x801C3998`/`0x801C388C`, `0x801DF3AC` |
| `0x80145EEC` | `+0x60` | written every frame with the screen position | `Actor_UpdateScreenPos` |
| `0x80145F00..FA7` | `+0x74..+0x11B` | **persistent record copy** (`0xA8` bytes; see the table two sections down) | `Battle_InitPartyContexts`, `Battle_ReloadPartyRecords`, `Battle_Init` (+0x80, +0x90..), `Battle_ApplyDamage` |
| `0x80145F1C..F38` | `+0x90..+0xAC` | **effective stat block** = persistent `+0x1C..+0x38` (max HP/AP, ATK, DEF, AGI, `+0x26`, `+0x2A`, …, evade/hit): `Battle_Init` snapshots it to `+0xB0..+0xCC`, lets `Formation_ApplyStatMods` (engine `0x800A79AC`, keyed on `0x80144F54`) adjust the scratch, and copies it back — this is what `Battle_BeginAction` copies to `0x801EC278` per action | `Battle_Init` (store `0x801D13D8..` then `0x801D15A4..`) |
| `0x80145F3C..F58` | `+0xB0..+0xCC` | scratch copy of the block above (holds the previous battle's values until `Battle_Init` overwrites it) | `Battle_Init`, `Formation_ApplyStatMods` |
| `0x80145F0C` | `+0x80` | status halfword: `Battle_Init` sets `0x2000` when HP < max/4 (the low-HP bit read by the enemy AI opcode `0xE` and by `Escape_Chance`) | `Battle_Init` |
| `0x80145FA4/A5/A6` | `+0x118/+0x119/+0x11A` | **target / command / parameter** (see "Commands, Auto, Run and the enemy AI"); `Battle_Init` zeroes the command, `+0x121`, `+0x12C..+0x133`, `+0x136..+0x139` | menus, `Battle_Init` |
| `0x80145FA8` | `+0x11C` | written per frame on the field (`0x801B1C80`) | |
| `0x80145FAC` | `+0x120` | battle status byte | `Battle_ApplyDamage` |
| `0x80145FB0` | `+0x124` | battle flags u32 (`0x100` pending effect, `0x10000` no damage) | `0x801DB45C`, engine `0x800A783C` |
| `0x80145FB4` | `+0x128` | battle flags u32 (`0x1`, `0x2`, `0x40` charge) | GAME `0x801B4CC4` at battle end |
| `0x80145FB6..B7` | `+0x12A,+0x12B` | field animation bytes (630 writes from GAME `0x801B6444`) | |
| `0x80145FB8` | `+0x12C` | bit 0 cleared at init | |
| `0x80145FC0`, `+0x138` | `+0x134,+0x138` | `0x10000` fixed-point pair (scale 1.0) set at init; charge byte at `+0x138` low | |
| `0x80145FC8` | `+0x13C` | **roster index** | `Battle_InitPartyContexts` |

The scratchpad word `0x1F800044` and the boot global `0x8014624C` both
point at the current slot's `C` (so `Battle_ApplyDamage`'s `ctx+0x79` is the
character id, `ctx+0x80` the status flags, `ctx+0x124`/`+0x128` the battle
flags). Party composition comes from `0x80144F56 + slot + formation*3`
(character ids), party size from `0x80146250`, and the character-id →
roster map is the byte table at `0x80182488` (what `CharId_ToRosterIndex`
reads). Addresses first seen through individual functions, kept for the
record:

| Address (m=0) | Field | Source |
|---|---|---|
| `0x80145F05` | character id byte (→ roster index via `CharId_ToRosterIndex`) | `BattleResult_AddExp` |
| `0x80145F0E` | weapon id byte (compared to `'J'`,`'L'`,`'O'`,`0x13`,`0x16`,`0x17`,`0x33`,`0x35`,`0x40` — weapon type/element) | `Battle_ApplyDamage`, `Battle_CalcDamage` |
| `0x80145F0C` | status-flag halfword (bits `0x04`,`0x20`,`0x40`,`0x80`, mask `100`) *?* | `Battle_CalcDamage` (`-0x7feba0f4`) |
| `0x80145F14` | **HP** (u16) | `Battle_ApplyDamage` writes it |
| `0x80145F18` | byte compared with overkill on a kill (survive/guts check) *?* | `Battle_ApplyDamage` |
| `0x80145F16` | **AP** (u16) — written back to the record at battle end | `Battle_WriteBackMember` |
| `0x80145F1C` | **max HP** (u16); `+2` = max AP (the HUD gauges are fed `0x80145F1C` then `0x80145F1E`) | `Battle_ApplyDamage`, `HUD_GaugesTick` |
| `0x80145FAC` | status byte (`0x11` written at attack start; `\|= 4` on clamp) | `Battle_ApplyDamage` |
| `0x80145FB0` | flags u32 (`0x100` pending-effect, `0x4`, `0x10000` = takes no damage) | both |
| `0x80145FB4` | flags u32 (`0x1`,`0x2`,`0x40` charge) | `Battle_CalcDamage` |
| `0x80145FC4` | charge multiplier byte (consumed with flag `0x40`) *?* | `Battle_CalcDamage` |
| `0x80145FC8` | **roster index** byte (indexes the persistent records; `Battle_ApplyDamage` tests `== 5` for the weapon-status attacker) | `Battle_WriteBackMember`, `Battle_ApplyDamage` |

### Enemy working records — game-mode overlay data, stride `0x118`

Base for enemy *n*: **`0x801EB620 + n*0x118`** (the record proper; the
earlier "`0x801EB634` base" was the HP cell). Offsets below are from
`0x801EB620`; the addresses are for n = 0. The stat block `+0x20..+0x3F`
mirrors the party block `+0x1C..+0x3B` shifted by 4.

| Address (n=0) | Field | Source |
|---|---|---|
| `0x801EB5A5` | byte passed to engine `0x800A0680` on status clear (actor/sprite id) *?* | `Battle_CalcDamage` |
| `0x801EB61D` | family/type byte (`1`, `4` double specific weapon types) | `Battle_CalcDamage` |
| `0x801EB620` | `+0x00` halfword: bit 4 = 50 % miss chance against it (`0xE0` in `slot03`) | `Battle_HitCheck_EnemyTarget` |
| `0x801EB622` | `+0x02` status-flag halfword (`0x4000` set on death by `Battle_EnemyDefeated`) | `Battle_CalcDamage` |
| `0x801EB624` | `+0x04` **zenny yield** (u16, 10) — added to the battle total `0x8014632C` on death and then zeroed | `Battle_EnemyDefeated` (`c_order.json`) |
| `0x801EB626` | `+0x06` **EXP yield** (u16, 8) — added to `0x80146328` on death | `Battle_EnemyDefeated` |
| `0x801EB628` | `+0x08` **level** (u16, 10): the damage bonus term `+0x08 * (2..3) / 10` and the row-0 class for the turn-order variance (`Battle_LevelClass`) | `Battle_BaseDamage`, `Battle_BuildTurnOrder` |
| `0x801EB634` | `+0x14` **HP** (u16) — `0x801EB74C` is enemy 1 | `Battle_ApplyDamage` |
| `0x801EB638` | `+0x18` drop 1: u16 item (`category<<8 \| id`, `0x0004`), `+0x1A` chance class (3); `+0x1C`/`+0x1E` drop 2 (`0x0019`, class 1). Zeroed once dropped | `Battle_RollDrops` |
| `0x801EB640` | `+0x20` **max HP** (u16) — `0x801EB758` fed to the HUD; `+0x22` max AP (18) | `Battle_ApplyDamage`, `Battle_BeginAction` |
| `0x801EB644` | `+0x24` **ATK** (19), `+0x26` **DEF** (11), `+0x28` **AGI** (7; the turn-order base, mirrors party `+0x24`), `+0x2A` (20) | `Battle_BeginAction` → `0x801EC27C`, `Battle_BuildTurnOrder` |
| `0x801EB654` | `+0x34` type / size class byte (5) | `Battle_ScaleDamage` |
| `0x801EB69C` | status byte | `Battle_ApplyDamage` |
| `0x801EB69D` | byte zeroed on status clear | `Battle_CalcDamage` |
| `0x801EB6A0` | flags u32 (`0x100`, `0x10000`) | both |
| `0x801EB6A4` | flags u32 (`0x40` charge) | `Battle_CalcDamage` |
| `0x801EB6B4` | charge multiplier byte | `Battle_CalcDamage` |

### Persistent character records — boot-EXE data, `0x80144964 + roster*0xA4`, 8 records

Base and stride are **proven by code**: `Char_RecalcStats` compares its
argument against `&0x80144964 + n*0xA4` for n in 0..7, and `Char_LevelUp`
indexes the same array. Records are indexed by **roster index**, not by
battle slot. The order is now complete, read off the 5-byte name field at
record `+0x00` in the card saves (`save_tool.py dump`, 2026-09-05; Ryu 0 and
Teepo 3 had been confirmed over two battles, Rei 4 off `slot03`): **0 リュウ
Ryu, 1 ニーナ Nina, 2 ガーランド Garr, 3 ティーポ Teepo, 4 レイ Rei, 5 モモ Momo,
6 ペコロス Peco, 7 パピー** — the **intro's baby dragon** (user, 2026-09-05;
name bytes `f6 f7 fc` = パピー, character id **10**, level 0). Proven live the
same afternoon from `slot01`: through the intro boss the party is `[0x0A, -,
-]`, the working record's roster byte `0x80145FC8` is **7** for the whole
stretch, and `Battle_WriteBackMember` wrote HP 11 → 7, AP and status into
record 7 at battle end while record 0 stayed untouched (`papi_intro.json`).
The char-id → roster table `0x80182488` (boot EXE bytes) is
`00 01 02 03 04 05 06 | 00 01 00 07 | 00 00 00 04`: ids 0..6 are the roster,
**7 → 0, 8 → 1** (adult Ryu / Nina?), **9 → 0** (the id save 1 carries at 28
min — the boy Ryu alone, after the transformation; not the whelp as first
guessed), **10 → 7** (パピー), 14 → 4 (a Rei form). In battle, the working record's byte at `0x80145FC8` holds the roster
index and `CharId_ToRosterIndex` maps the character-id byte to it.

**Static copy of all eight records:** `START.EMI` §8 carries the new-game
templates at **`0x801EB4A4`** (stride `0xA4`), byte-identical to the saves'
untouched records (ニーナ Lv 5 EXP 90, ガーランド Lv 13 EXP 3000, モモ Lv 10
EXP 1000, パピー id 10). Read a record offset there before tracing it
([`IDEAS.md`](IDEAS.md) I4). `COMMU02.EMI` holds the character-name strings
at `0x801DB214` in the same roster order.

| Offset | Field | Evidence |
|---|---|---|
| `+0x00..+0x04` | **name**, 5 bytes in the in-game kana encoding (`0x5B..` hiragana, `0xAB..` katakana, `0xFC` ー; 0-terminated) — copied verbatim into the save-slot summary | `Save_BuildImage` (`memcpy(0x80145574, rec0, 5)`), decoded in `save_tool.py` |
| `+0x05` | **character id** (u8; = roster for 0..6; 10 = パピー on record 7; 7/8/9/14 are alternate forms mapped by the `0x80182488` table) | party ids `0x80144F56` vs records, card saves, `papi_intro.json` |
| `+0x06` | **level** (u8) | `Char_LevelUp` wrote 3→4 (Teepo `0x80144B56`) |
| `+0x08` | **EXP** (u32, cap 9,999,999) — Ryu `0x8014496C`, Teepo `0x80144B58` | `BattleResult_AddExp`, three battles |
| `+0x0C` | **status flags** (u16), persistent subset `& 0x60A0` of the working halfword | `Battle_WriteBackMember` |
| `+0x14` | **HP** (u16) ← working `0x80145F14` at battle end; clamped to effective max by `Char_RecalcStats` | write-back, recalc |
| `+0x16` | **AP** (u16) ← working `0x80145F16` | write-back (Teepo 5→1 after casting) |
| `+0x18` | u8 ← working `0x80145F18` *?* | write-back |
| `+0x19` | status bits that halve the byte stats `+0x2B..+0x33` | `Char_RecalcStats` |
| `+0x1A` | percent-style byte: effective max HP −= (base max HP × this + 5)/10 *?* | `Char_RecalcStats` |
| `+0x1C..+0x38` | **effective stats**, recomputed from the base block + equipment (`Stat_AddClamped`, cap 999): `+0x1C` max HP, `+0x1E` max AP, **`+0x20` ATK**, **`+0x22` DEF**, `+0x24` (Agl-derived: 3 / 10 / 20), `+0x26` (Int-derived: 10 / 43 / 34), `+0x2A` (513 / 513 / 515) *?*. The whole `+0x1C..+0x3B` block is copied to `0x801EC278` / `0x801EC258` when the member acts / is targeted (damage path) | `Char_RecalcStats`, `Battle_BeginAction`, `Battle_ResolveAction_Party` |
| `+0x30` | **type / size class** byte (5 for all three; indexes the `0x801EAF70` percent table under weapon flag `0x20`) | `Battle_ScaleDamage` |
| `+0x34..+0x38` | 5 bytes checked against a per-roster 5-byte table at `0x80148668` — of which **`+0x37` = evade %** (6 / 4 / 25) and **`+0x38` = hit %** (95 / 95 / 100) | `Char_RecalcStats`, `Battle_HitCheck_*` |
| `+0x3C` | **base max HP** (u16) | `Char_LevelUp` +4 |
| `+0x3E` | **base max AP** | +4 |
| `+0x40` | **Pwr** | +2 |
| `+0x42` | **Def** | +2 |
| `+0x44` | **Agl** | +1 |
| `+0x46` | **Int** | +4 |
| `+0x4A..+0x58` | **base copy of the byte-stat block `+0x2A..+0x38`** (the same +0x20 shift as `+0x3C..+0x46` under `+0x1C..+0x26`): equal for unequipped records, differs by the equipment bonuses otherwise (Teepo `+0x34` 0x37 vs 0x32, evade 4 vs 6) | card saves, `save_tool.py dump` 2026-09-05 |
| `+0x5C`, `+0x66`, `+0x70`, `+0x7A` | **four learned-ability lists, 10 slots each**, one per ability *type*: `AbilityList_ForType` (boot `0x80167514`) reads `(0x801CB231 + id*16) & 3` and returns record `+0x5C` / `+0x66` / `+0x70` / `+0x7A`; `AbilityList_Add` then fills the first zero slot. In the card saves Momo holds `0x46 0x4B` at `+0x5C` and `0x3C 0x44 0x52 0x57` at `+0x66`, Teepo `0x5B 0x5E 0x67` at `+0x70` (so the L4 write "at `+0x71`" was slot 1 of this list), Rei `0x41 0x61` at `+0x70` and `0x45 0x08` at `+0x7A`, Ryu `0x76` at `+0x7A`. The table is in GAME.EMI at **`0x801CB230`** (16-byte records, name in the last 8 bytes): type 0 = healing (アプリフ, リバル), 1 = support (ねらい撃ち, ミカテクト), 2 = attack magic (パダーマ, レイギル, ドメガ), 3 = skills (会心撃, ダブルヒット, 毒撃) — a reading of the names, not of code ([`IDEAS.md`](IDEAS.md) I4) | `AbilityList_Add` disasm, saves, GAME.EMI bytes |
| `+0x84` | byte, `1` only on Teepo — the one record carrying growth modifiers (apprenticeship flag?) | saves |
| `+0x85..+0x8A` | six **signed growth modifiers** (one per stat, added to the table growth each level: BoF3's Master apprenticeship bonuses) | `Char_LevelUp` |

### Equip (field menu)

Two runs. `equip.json` (same weapon re-equipped) showed only
`Char_RecalcStats` and helpers on confirm: `+0x1C..+0x38` recomputed (base
Pwr 12 → +8 weapon = 20; Def 10 → +1 → +5 from two armour pieces = 16;
`+0x24` 8 → −2 → −3 = 3; max HP 20 → 10 through the `+0x1A` percent step).
`equip2` (`ramdiff --width 1`, weapon 28 → 3) found the slot:

| Address | Field | Change |
|---|---|---|
| `0x80144972` = record **`+0x0E`** | **equipped weapon id** (the byte `Battle_ApplyDamage` reads from the working copy at `0x80145F0E`) | 28 → 3 |
| `+0x0E..+0x13` | **six equipment slots** (item ids); `Menu_EquipConfirm` (START.EMI `0x801D6D94`) walks all six, and per slot the inventory category is the START.EMI table at `0x801EC3E8` = [1, 2, 2, 2, 3, 3] (slot 0 = weapon, category 1) | decompile + equip3 |
| `0x80144984` `+0x20`, `0x80144988` `+0x24` | effective stats recomputed | 14 → 20, 0 → 3 |
| `0x801450CD`, `0x801452CD` | inventory **category 1 = weapons**: slot 5 id 3 cleared, count → 0 | equipped item leaves the inventory |
| `0x801452CA` | category 1 slot 2 count 1 → 2 | the old weapon 28 stacks back in |

So equipment is stored in the character record and equipped items are
removed from (and returned to) the inventory rather than flagged. The
confirm routine, from its body: for each of the six slots whose pending
choice (`0x801ED5BC[i]`) differs from the record byte, `Inventory_Remove(cat,
new, 1)`, `Inventory_Add(cat, old, 1)`, store the new id; then
`Char_RecalcStats(record)`. The character is the party member under the
menu cursor (`0x8014850C` → `0x80144F56` → roster via `0x80182488`). The menu
overlay (`START.EMI`, resident at `0x801D0C00`) rewrites `+0x0C` every ~2
frames while open; `0x80144FBE` (u16) also advanced (3370 → 4148) — a
counter, unidentified.

### The level table — `GAME.EMI` data, `0x801CC068 + roster*0x318 + level*8`

Decoded from the disc bytes and matched against the trace: Teepo's L3→4
row is `hp+4 ap+4 pwr+2 def+2 agl+1 int+4, skill 0x5E`, exactly the six
writes and the ability add observed. Row layout (8 bytes, level 1..98):

| Byte | Meaning |
|---|---|
| `+0,+1` | u16 **EXP needed to go from this level to the next** (level = first L whose cumulative sum exceeds EXP) |
| `+2` | max HP growth |
| `+3` | max AP growth |
| `+4` | Pwr growth `>>4`, Def growth `&0xF` |
| `+5` | Agl growth `>>4`, Int growth `&0xF` |
| `+6,+7` | up to two ability ids learned (0 = none) |

Cumulative thresholds (JP disc): Ryu and Teepo `10, 30, 60, 105, 173,
275…`; roster 1 `8, 24, 48, 84, 138, 219…` (AP-heavy, no HP at L2→3: a
mage); roster 2 `12, 36, 72, 126, 207, 329…` (no AP growth early, high
HP/Pwr). **The community chart (10, 25, 62, 155) does not match this
disc**; the game's own arithmetic (EXP 65→77 with "next" 40→28 ⇒ 105) does.

`Char_LevelUp(roster)` `0x801AEDD4` lives in **`GAME.EMI`** (`0x80196800`,
the resident field/system overlay, 582 functions in Ghidra), is called
from `BATL_END` `0x801EF400` on the results screen, and finishes with
`Char_RecalcStats(rec)`. Boot helpers: `Stat_AddClamped(u16*, delta)` (0..999),
`AbilityList_Add(id, …)`, all in `symbols.toml`.

### Party globals — boot-EXE data

| Address | Field | Source |
|---|---|---|
| `0x80144F4C` | **zenny** (u32, cap 9,999,999) | `Zenny_Add` `0x80166FFC` (boot; `symbols.toml`), traced +1 ×40 on the results screen (`money.json`, two `ramdiff` rounds +40) |
| `0x8014502C` | **lifetime zenny earned** (u32): `Zenny_Add(amount, skip_total)` adds to it unless `skip_total`; the results screen passes 0, so both cells move together | same |
| — | `Zenny_Sub(amount)` `0x80166FCC`: subtracts if affordable, returns success. The **shop overlay does not use it**: SHOP.EMI subtracts inline at `0x801D1E9C` (price `*(0x801E5F94)` × quantity) and calls the interior `0x80166FD4` | ghidra + `buy.json` (four buys, −20 each) |

### Inventory — boot-EXE data, four categories × 128 slots (+ one id-only list)

`Inventory_Add(category, item_id, count)` `0x80165AA4` (boot; called by the
shop with the id byte at `0x801E5F7C`) indexes two pointer tables in
GAME.EMI data, `0x801C9934` (id lists) and `0x801C9948` (count lists):

| Category | ids (128 × u8) | counts (128 × u8, cap 99) |
|---|---|---|
| 0 | `0x80145048` | `0x80145248` |
| 1 | `0x801450C8` | `0x801452C8` |
| 2 | `0x80145148` | `0x80145348` |
| 3 | `0x801451C8` | `0x801453C8` |
| 4 | `0x80145448` | none (id-only: key items) |

A stack that already exists grows (returns 0 when it would exceed 99);
otherwise the first slot with id 0 or count 0 is taken and scratchpad
`0x1F800000` is set. The category is decided by the caller. The
`buy.json` capture watched `0x80145440..0x80145600` and saw nothing because
the arrays sit **below** that: watch `0x80145040-0x80145470` next time.
`AbilityList_Add`'s 128-byte list at `0x80145468` is a different list.

The results screen is its own overlay: **`BATL_END.EMI` resident at
`0x801EEC00`** during the tally (RAM-prefix match 7936 B; promoted to
`evidence` in `names/overlays.toml`). Its tick wrappers at `0x801EF810` /
`0x801EF840` call `Zenny_Add(1, 0)` once every two frames; the tally ran
at frames +562..+640 after the kill press in a 1200-frame window, and the
EXP tick at +769..+791 in an 800-frame window in another battle — the
results screen's start drifts with the battle, so give `--window-frames`
headroom (1200+) or the write trace sees nothing while `ramdiff` did.

### Saving — the memory-card path

Found with a fn-entry capture filtered to the BIOS file-API wrappers
(`open`/`lseek`/`read`/`write`/`close`/`firstfile`/`nextfile` at
`0x8017F7B4..0x8017F824`; `_card_write` is never used) while saving:

| Step | Call (from the memory-card module, SHOP/START `.EMI` section md5 `af7a685c…`, resident at `0x801EEC00`) |
|---|---|
| menu open | `Card_InfoPoll` → `_card_info`, `Card_LoadDirectory` → `_card_async_load_directory(port, 0x2000)` every ~75 frames |
| list slots | `Card_ListFiles` → `firstfile`, `Card_NextFile` → `nextfile` ×3 |
| per slot | `Card_Open(name, 1)`, `Card_ReadSlotHeader`: `lseek(fd, 0xE80)`, `read(fd, 0x800C2680, 0x80)`, `close` (the 128-byte title/icon frame) |
| save | `Card_Open(name, 2)`, `Card_WriteFile`: `lseek(fd, 0)`, **`write(fd, 0x800C1800, 0x1300)`**, `close` |

So the **save image is 0x1300 = 4,864 bytes staged at `0x800C1800`** — the
BOSS overlay band, idle outside battle — which is why no static reference
and no party-block `ramdiff` ever pointed at it (a same-state re-save
rewrites identical bytes). The BIOS `TestEvent` polling loop
(`0x8017F6E4`, 256 k calls) is the game waiting for the card; exclude it
from any wrapper-range trace. The serialiser that fills `0x800C1800` is the
remaining unknown: `capture --watch 0x800C1800-0x800C2B00` during a save
names it and gives the field order.

### The save block and the file format

`Save_BuildImage` (SHOP.EMI `0x801D69F0`, evidence from `save_ser.json` +
decompile) shows the whole persistent game state is **one contiguous
block of `0x10B0` = 4,272 bytes at `0x801448D4..0x80145984`**, saved raw:

| RAM | Contents (known so far) |
|---|---|
| `0x801448D4` | block head written at save time: four u32 from `0x8014686C..0x80146878` (**not** the play time — saves 2 and 3 differ by three minutes and carry identical words; unlabelled), `+0x20` four bytes from `0x80146860..63`, `+0x24` u16 from `0x80143F00` (read as `lhu` by boot `0x8015C03C`; 10 in save 1, 0 in saves 2/3 — an area/map id?), `+0x27` facing (`0x80145E94`), `+0x28`/`+0x2C` slot-0 world x/z (`0x80145EC0/C4`, 16.16) |
| `0x80144944` | **u16 checksum slot** (zeroed before the copy; file `+0x270`) |
| `0x80144964` | 8 character records × `0xA4` |
| `0x80144E84..0x80144F4C` | unlabelled |
| `0x80144F24` | **progress-flag bit array** (runs to the zenny cell at least): `Save_BuildImage` calls boot **`Flag_Test(0x80144F24, 0x92)`** `0x8015BFC4` — `(bits[idx>>3] >> (idx&7)) & 1`, eight instructions — and stores the bit in the summary byte `0x80145588`. It was recorded here as a hash over `0x92` bytes until `save_tool.py verify` checked the byte against the array (2026-09-05). `0x8015BFE4` is the matching toggle |
| `0x80144F4C` | zenny; `0x80144F54` formation u16; `0x80144F56` party ids × 3 formations (`0xFF` = empty); **`0x80144FBC` play time as four bytes h / m / s / frame** (the `0x80144FBE` u16 that "advanced 3370 → 4148" during the equip test was the s/frame pair ticking); `0x80145020` form byte (`& 0x7F` = 5 or 0xC exempts Peco from the id-`0xB` rewrite below); `0x80145021` ← low byte of `0x80146254` |
| `0x8014502C` | lifetime zenny; `0x80145048..0x80145448` inventory (4 × 128 ids, 4 × 128 counts); `0x80145448` key items; `0x80145468` ability list |
| `0x80145574` | save-slot summary = what the load screen shows: `+0..+4` record-0 name bytes, `+5..+7` formation-0 party ids (id 4 written as `0xB` unless form byte is 5 / 0xC — Peco), `+8` record-0 level, `+9/+A` ← `0x8014494E/F`, `+0xC` play time h/m/s/f ← `0x80144FBC`, `+0x10` record-0 EXP, `+0x14` flag bit `0x92`; `0x80145590` nine u16 from `0x80145AB0` (unlabelled) |
| `0x80145984` | end of block |

Card file layout (`0x1300` bytes, written by `Card_WriteFile`):

| File offset | Contents | Writer |
|---|---|---|
| `0x000..0x07F` | title frame (`'SC'`, icon flags, SJIS title, 16-colour CLUT at `+0x60`) | `Card_BuildTitleFrame(1, 0x13, 0x80145AD0)` |
| `0x080..0x1FF` | three 128-byte icon frames | `Card_CopyIconFrame0/1/2` |
| `0x200..0x12AF` | the game block, byte copy of `0x801448D4..` with every byte summed (u16) into `+0x270` | `Save_BuildImage` (store pc `0x801D6C58`) |
| `0x12B0..0x12FF` | zero fill | |

The slot list reads back `0xE80..0xEFF` of each file (`Card_ReadSlotHeader`),
i.e. block `+0xC80` = RAM `0x80145554..` — the summary written at
`0x80145574` sits 0x20 into that window. The card buffer is `0x800C1800`
(BOSS band, free outside battle); the `save_ser` write page for the confirm
frame was truncated at `+0x8B4` (more than 2 048 stores in one frame), the
decompile supplies the rest.

### The save tool, and what it verified (2026-09-05)

`tools/save_tool.py` (`list` / `dump SLOT` / `verify` / `diff A B`) reads the
block above straight off a raw card image and is the end-to-end check on
this map. On `saves/card1.mcd` (three saves, re-mapped by the user
2026-09-05):

- the u16 byte-sum recomputes on all three (`0x950B`, `0xA218`, `0xA22C`);
- every slot-summary field matches the block it was copied from — name bytes,
  party ids under the Peco rule, level, `+9/+A`, play time, EXP, flag bit —
  and the SJIS title's `HH時間MM分 レベルLL` agrees with `0x80144FBC` and
  record 0;
- `diff 2 3` on the pair the user described as "identical except time":
  exactly two runs differ, the checksum and the play time (block `+0x6E9`
  and its summary copy at `+0xCAD`);
- **independent oracle**: Mednafen booted from the same card image
  (`mednafen_ctl.py launch --card`, Start, Start, Circle, Circle) lists
  リュウ LV 1 at 00:28 / 05:13 / 05:10 with one portrait for file 1 and
  Teepo / Rei / Ryu for files 2 and 3 — the tool's output line for line
  (`analysis/mednafen_loadscreen_card1.png`).

The three rows it corrected are marked above (`Flag_Test`, the play time at
`0x80144FBC`, the four ability lists). Item and ability ids resolve to names
since the evening of 2026-09-05 (`names/*.toml` from `tools/text_tables.py`,
[`TEXT_TABLES.md`](TEXT_TABLES.md)); that also proved `+0x20` = `+0x40` +
weapon power and `+0x22` = `+0x42` + the three armour powers. Not yet readable
through it: the four `0x8014686C..` words at the block head and record `+0x84`. Record 7 is パピー, the intro's baby dragon
(live test on `slot01`, same day).

### HUD gauge records — boot-EXE data, stride `0x24`

Enemies at `0x801484B8 + n*0x24` (three seen: `0x801484B8`, `0x801484DC`,
`0x80148500`); party HP gauges at `0x8014850B`/`0x8014852F`-based records
with AP gauges two bytes on. This is the *displayed* state, so
`0x801484CC` (enemy 1 shown HP) trails the working HP by the shrink
animation.

| Offset | Field |
|---|---|
| `+0x0B` | gauge length byte, 0..55 (`0x37`), min 1 while HP > 0 |
| `+0x14` | shown HP (u16) |
| `+0x1C` | shown max HP (u16) |
| others | shrink delta / step / flag (stack args of `HUD_GaugeUpdate`) |

Formula: `gauge = hp * 55 / max_hp`, forced to 1 when HP > 0 rounds to 0.

## The damage path

Read in full on 2026-09-05 (Ghidra with the boot EXE mapped in and the
BIOS thunks made returning — see [`GHIDRA.md`](GHIDRA.md) → Traps; before
that fix every decompile stopped at the first `Rand()` and this section
ended at `Battle_BaseDamage`). Verified against one full round from
`slot03` (`analysis/callstacks/round1.json`): every hit lands on the
formula for one variance draw.

**Per-action stat blocks.** When an actor's turn starts,
`Battle_BeginAction` (`0x801D2B50`) copies the **actor's** 32-byte stat
block — persistent record `+0x1C..+0x3B` for a party member, enemy
record `+0x20..+0x3F` for an enemy — to `0x801EC278`; the resolve step
(`Battle_ResolveAction_Party` `0x801DFC68` / `_Enemy` `0x801E3B8C`) copies
the **target's** block to `0x801EC258`. The formula reads only those two
copies:

| Global | = | Field |
|---|---|---|
| `0x801EC27C` u16 | actor block `+4` | **ATK** (party `+0x20`, enemy `+0x24`) |
| `0x801EC27E` u16 | actor block `+6` | actor DEF |
| `0x801EC294` u8 | actor block `+0x1C` | **hit %** (party `+0x38`; 95 / 95 / 100 in `slot03`) |
| `0x801EC25E` u16 | target block `+6` | **DEF** (party `+0x22`, enemy `+0x26`) |
| `0x801EC273` u8 | target block `+0x1B` | **evade %** (party `+0x37`; 6 / 4 / 25), +25 capped 99 under target flag `0x124 & 1` |

```
Battle_CalcDamage(attacker, target, flags=0xFFFF)     0x801DC00C
  scratch 0x1F800000 = weapon table byte (0x801C9F2F + weapon_id*0x14) for a party attacker, else 0
  charge (flag 0x40): ATK += ATK * charge_byte / 2, both cleared
  base = Battle_BaseDamage(attacker, target, 0)
  x2 if weapon id in {0x13,0x17,0x33} and enemy family (enemy-3) == 4;  x2 if id in {0x16,0x35,0x40} and family == 1
  if target status & 100 == 0:
       base = Battle_HitCheck_PartyTarget / _EnemyTarget(base, attacker, target)      -> 0 on a miss
  else: status bits 0x40 / 0x20 wake the target (engine 0x800A0680) and floor at 1; bit 4 floors at 1
  if target flag byte & 2:  base = base * {50,50,50,50,60,60,60,70}[Rand & 7] / 100      (table 0x801D0C7C)
  if defend flag 0x801462E4 & 0x80:  base = base/2 + Battle_BaseDamage(attacker, target, 1)/4
  back row (target is party and 0x80144F54 == 2): base -= base/4;  target status & 0x80: base -= base/4
  floors at 1 for status 0x60 / the defend flag; target flag 0x10000 -> 0; clamp to +-9999

Battle_BaseDamage(attacker, target, mode)             0x801DCAA0
  party attacker, or enemy-vs-enemy:
       d = ATK - DEF                       (mode 1: d = ATK, the defend term above)
  enemy attacker vs party:
       d = ATK - Battle_PartyAvgDef()      0x801DCC78: (mean of every party member's DEF + target DEF) / 2
  d = max(d, 0)
  enemy attacker:  d += enemy+0x08 * (2 + Rand % 2) / 10     (+0x08 = 10 for both slot03 enemies: level? *?*)
  d += Rand & 1
  return Battle_ScaleDamage(attacker, target, d)

Battle_ScaleDamage(attacker, target, d)               0x801DCD18   (8.8 fixed point throughout)
  d *= 205/256                                              (0.80; the expression before the max() can never exceed 0xCD for d >= 0)
  d *= {0xDA,0xE6,0xF3,0x100,0x10D,0x11A,0x126,0x133}[Rand & 7] / 256     (0.85 .. 1.20, table 0x801EAF50)
  if scratch & 0x1F:  d = d * engine 0x8009FA78(target) / 100            (elemental affinity of the target; BATTLE.EMI#15, not read)
  if scratch & 0x20:  d = d * s16 table 0x801EAF70[type] / 100            (type = party rec+0x30 / enemy+0x34; {300,200,200,150,125,100,50,0})
  return round-half-up(d)

Battle_HitCheck_PartyTarget(amount, attacker, target) 0x801DC704     (target < 3)
  defend flag -> hit.  attacker status bit 8 -> 50 % miss (Rand & 2).
  miss iff Rand % 100 <= target evade %  (0x801EC273).  A miss returns 0 and clears bit 0x10 of the target's status byte 0x80145FAC.

Battle_HitCheck_EnemyTarget(amount, attacker, target) 0x801DC85C     (target >= 3)
  defend flag -> hit.  attacker status bit 8 -> 50 % miss.  party attacker flag 0x80145FB4 & 0x100 -> sure hit.
  enemy halfword +0 bit 4 -> 50 % miss.  party attacker hits iff Rand % 100 < attacker hit % (0x801EC294); enemy-vs-enemy always hits.
  A miss returns 0 and clears bit 0x10 of the enemy status byte +0x7C (0x801EB69C).
```

**Verification, `slot03` (Ryu L1 ATK 20, Teepo L8 ATK 28, Rei L10 ATK 47; two
enemies HP 31, ATK 19, DEF 11, `+0x08` = 10; party DEF 16 / 22 / 37, mean 25):**

| Hit | Observed | Formula |
|---|---|---|
| Rei → enemy 0 | 31 → 0 (31) | (47 − 11 + 1) = 37 → ×205/256 = 29.63 → ×0x10D = 31.13 → **31** |
| Teepo → enemy 1 | 31 → 18 (13) | (28 − 11) = 17 → 13.61 → ×0xF3 = 12.92 → **13** |
| Ryu → enemy 1 | 18 → 12 (6) | (20 − 11) = 9 → 7.21 → ×0xDA = 6.14 → **6** |
| enemy → Ryu, Teepo | 10 → 9, 49 → 48 (1 each) | ATK 19 < (25 + DEF)/2 → 0, + 10·(2|3)/10 = 2..3, ×0.8 ×0.85.. → **1..3** |

The `bytes_b64` weapon-table byte for weapon id 3 must have no element bits
set (or the affinity was 100 %) — the three party hits reproduce without
the `0x1F` term. The Rand draw is not observable, so each row is "exact for
one of the eight draws", not a unique fit.

## Turn order, kills, drops and the results tally (2026-09-05, track C)

Read from five command captures on `slot03` (Attack, Defend, Watch,
Auto-attack, Run), one on `slot02` (Nu), a victory capture that paged
through the results, and `c_order.json` (a write trace on
`0x80146300-0x80146360`), each cross-checked against the Ghidra body.
Captures are `analysis/callstacks/c_*.json`.

**The round commit.** When the last command is entered, `Battle_BuildTurnOrder`
(`0x801DAAB4`; the traced entry `0x801DAE14` is a continuation of it) runs
once and writes:

| Address | Field |
|---|---|
| `0x801EB4C0` | scratch pairs (u16 value, u16 actor) × 11, bubble-sorted descending on value |
| `0x80146308..12` | **turn order**: actor bytes, `0xFF`-terminated (`slot03`: `[2, 1, 3, 4, 0]` = Rei, Teepo, enemy 0, enemy 1, Ryu) |
| `0x8014631E` | cursor — `Battle_BeginAction` reads `list[cursor]` and increments it; `0xFF` entries are skipped |
| `0x8014631F` | count |

```
party m:   value = AGI (rec+0x24) + bonus × pct[Battle_LevelClass(level, row 1)] / 100
           bonus: command byte C+0x119 == 4 (skill/magic, id at C+0x11A) -> GAME table 0x801CB231[id*0x10] == 0 ? 4 : (1|3) ? 2 : 0
                  C+0x119 == 5 (item) -> 1;  else 0
           pct table 0x801EAEEC = {100, 125, 150, 200, 250}; party level thresholds 0x801EAF3E = {8, 16, 32, 48, 99, 99}
enemy n:   value = AGI (rec+0x28) + s8 table 0x801EAEF8[Battle_LevelClass(level rec+0x08, row 0) * 16 + Rand & 15]
           row 0 (level 0..15) = {4,2,2,2,0,0,0,0,0,0,-1,-1,-1,-2,-2,-4}; enemy level thresholds 0x801EAF38 = {16, 36, 64, 99, 99, 99}
Battle_ActorCanAct(actor) gates entry: present bit, status & 0x4944 (party) / 0x4144 (enemy) clear,
           and not the side excluded by 0x80146320 (1 = enemies, 2 = party, 3 = both).
```

So party `+0x24` is **AGI** (Ryu L1 = 3, Teepo L8 = 10) and enemy `+0x28`
mirrors it. The list carries only actor ids; the *command* rides on the
actor (next section). The first five-way venn (game-mode band only) found
no command-specific code because the command menu lives in the **battle
engine overlay** (`BATTLE.EMI#15` at `0x80093800`), outside the default
`fn_filter`; the `e_*.json` captures with `--lo 0x80093800 --hi 0x801D0C00`
found it.

### Commands, Auto, Run and the enemy AI (2026-09-05, engine-band captures)

Each party actor carries a **command byte at `C+0x119`** (slot 0 =
`0x80145FA5`) and a parameter halfword at `C+0x11A`; the engine writes it
through the pointer `0x801EB448` (= the choosing member's `C+0x118`) and
`0x801462FF` is the member whose menu is open (entry order here was slot 2,
1, 0). The round flags live in `0x801462E4`.

| Command | `C+0x119` | Written by | Cleared by |
|---|---|---|---|
| Attack | 1 | `Cmd_ConfirmAttack` `0x80093E14` (engine) | `Actor_ActionDone` `0x801E1D58` when the attack resolves |
| Defend | 2 | table target after `BattleMenu_ConfirmDispatch` `0x801D24CC` (store `0x801D2520`) | `Battle_ClearCommands` `0x801DB45C` at round end |
| Watch | 0, and `C+0x124 \|= 1` (Examine armed — the +25 evade bit) | `Cmd_ConfirmWatch` `0x8009521C` (engine) | — |
| Auto | 1 for every member at once | `Cmd_AutoBattle_Begin` `0x801D2598` sets `0x801462E4 \|= 0x10`, `AutoBattle_FillCommands` `0x801DD264` fills the bytes; `Battle_RoundStart` `0x801D1C88` refills every round while the flag stays | as Attack |
| Run | 0 | `Escape_Begin` `0x80098450` (engine) | battle ends |
| skill / magic | 4, skill id in `C+0x11A` (Rei's steal `0x41`, Teepo `0x67`, Ryu `0x46`) | `SkillMenu_Open` `0x80093FBC` sets 4, `SkillMenu_Confirm` `0x8009404C` writes the id, `Skill_TargetSetup` `0x80094768` picks the default target from the skill table `0x801CB230[id*0x10] & 0x20` | `Actor_SkillItemDone` `0x801E19A0`, which also deducts the AP cost `0x801463C4` from `C+0x8A` |
| item | 5, item id in `C+0x11A` (vitamin = 3) | `ItemMenu_Open` `0x800953D0`, `ItemMenu_Confirm` `0x80095418`; the count is decremented at confirm by `ItemMenu_Reserve` `0x80095F9C` (`0x8014524C` 0x1C → 0x19 over three picks) | `Actor_SkillItemDone` |

The third byte of the block, **`C+0x118`, is the target actor** (written by
`Attack_TargetSetup` `0x80093B24` the frame the menu opens on Attack, and by
the skill / item target setups after the confirm; self-targets leave it 0).
**Skills, items and enemy specials all land through one engine function,
`Effect_ApplyResult(actor)` `0x8009A160`** (seeded into Ghidra from the
only prologue in its gap): the effect handler is a `jalr` through the table
`0x800B165C`, indexed by `0x800B1438[skill id]` for a skill or by the
category × id table `0x800B164C` for an item; the handler fills a result
record at `0x8014639C` (`+4` signed HP delta, `+6` signed AP delta,
negative = heal) which the function then applies to the target
`0x80146390` — heal capped at max, damage clamped to ±9999, a kill at 0
with a survive check against the byte `C+0x8C`, enemy HP `0xFFFF` immune,
target flag `0x10000` = no effect. Seen: the steal on Gunhead 31 → 17
(`0x8009A6F8`), the vitamin on Ryu in the Nu fight 1 → 10 (`0x8009A608`),
and the −1 HP enemy specials on `slot03` / Nu. Plain Attack stays on
`Battle_ApplyDamage`. Capture note: a
direction has to be *held* across the Circle presses (`--hold up` / `--hold
down`), so every member picks from the same list; three presses per member
(open, select, target) commit the round.

**Commit.** `Battle_CommitRound` `0x801D2774`: `Battle_BuildTurnOrder`,
item commands consumed, `0x801462E4 |= 8`, then the engine's
`EnemyAI_ChooseActions` `0x80098F8C`. Execution is then per actor:
`Battle_BeginAction` pulls the next id off the list and the actor's own
state machine (the `ctx+2` / `ctx+3` dispatch tables) branches on its
command byte. There is no central switch on the command.

**Run.** `Escape_Roll` `0x80098278` runs on the Circle press (`+17`):

```
attempts 0x80146322++
boss flag 0x801462E6        -> no roll (sub-phase++)
attempts >= 3               -> success
0x80146320 == 1             -> success
else chance = Escape_Chance(mean party AGI (rec+0x24, living) - mean enemy AGI (rec+0x28, living))
     idx = (diff + 32) >> 4 ; chance = {32,36,40,44,48,52}[idx] (0x800B1430), 0x1C below, 0x38 above
     +8 on the 2nd attempt, +8 if a member has status 0x2000, cap 64
     success iff chance >= Rand & 63          (slot03: diff ~ +2 -> 40/64 = 62 %)
0x801462DF = 2 (success) / 1 (failure)
```

Success: `Escape_Begin` (banner for 60 frames, camera pans, everyone
turns and runs, commands cleared), a fade (`0x8014932E/F` toggling from
game-mode `0x801D10A8`), then mode `0x801462DC = 5` with sub-mode 3 from
the engine at `+183`, the exit steps and the field at `+409`. Failure
(`Escape_Failed` `0x800987F0`, body only): the party turns back, message
`0xF` shows for 45 frames, the turn order is rebuilt **without the party**
and the enemies take the round.

**Enemy AI is table-driven.** `EnemyAI_ChooseActions` walks, for each
living enemy, the 8-row × 16-byte script at `0x800E407C + (rec+0x60) * 0x88`
(engine data; Gunhead = script 1): byte 0 is a condition opcode (HP below
a quarter / half, AP below a fifth, an ally has status `0x2000`, fewer
enemies than at start, last enemy standing, turn counter `0x801463CC`
equal to 2 / 10 / odd, party level − enemy level ≥ 6, …), byte 1 the
action type applied by `EnemyAI_ApplyAction` (set `+0x80`, status change,
per-bit calls, drop class, **scale the EXP / zenny yield by a percentage**,
…); a fired row sets its bit in the enemy object's `+0xE1` mask so it
fires once. `EnemyAI_TurnCheck` `0x80098BB0` evaluates the per-turn
opcodes (`0..8` party weapon/skill flags, counter `+0xF8`, status bits)
when the enemy's turn comes. Row semantics beyond the opcodes are unread.

**A kill.** `Battle_EnemyDefeated` (`0x801E542C`, at the kill frame):
EXP total `0x80146328 += rec+0x06`, zenny total `0x8014632C += rec+0x04`
(then zeroed), status `|= 0x4000`, `Battle_RemoveFromTurnOrder(actor)`
(writes `0xFF` over the actor's turn slot — seen at `+153` in
`c_order.json`), `Battle_RollDrops`, enemies-remaining `0x801462EF--`
(`0x80146324 |= 2` at zero), engine `0x800A9FA4`, GAME `0x80197718`.

**Drops.** `Battle_RollDrops` (`0x801E525C`): for each of the enemy's two
drop slots (`+0x18`/`+0x1A`, `+0x1C`/`+0x1E`) with a non-zero item: drop iff
`Rand() & 0xFF <= 0x801D0CB8[class]`, table `{0, 0, 1, 3, 7, 31, 127, 255}`
(so class 3 = 4/256 ≈ 1.6 %, class 7 = certain). A drop is merged into the
result list — items u16 at `0x80146330`, counts at `0x80146350`, count byte
`0x80146323` (max 15) — and the enemy slot is zeroed so a second kill of the
same enemy cannot re-roll it. No drop landed in any capture (Gunhead: item
`0x0004` at 1.6 %, `0x0019` at 0.4 %), so `BattleResult_AwardDrops` is
body-only.

**The results screen (`BATL_END.EMI` at `0x801EEC00`, mostly interpreted —
only two of its functions stamped the ring).** `BattleResult_Setup`
(`0x801EF390`): per party slot, `Char_LevelUp(roster)` when `0x801EF92C`
says a level was reached (this is the `levelup3.json` caller); zenny total
`× 1.5` under `0x801EF6C4()` (unread — a bonus condition); tick step
`0x801463AC = max(1, zenny / 30)`; sorts the drop list. Then, one phase each
(`0x801462E0++`): `BattleResult_ExpTick` (`0x801EEF58`) feeds
`BattleResult_AddExp(step)` per member until the remaining counter is spent
— `c_victory2.json`: +1 every 2 frames × 6 into Ryu and Teepo for a 16-EXP
battle, i.e. 16 / 3 rounded up — `BattleResult_ZennyTick` (`0x801EF810`)
does the same through `Zenny_Add` (+1 × 20 into `0x80144F4C` and the
lifetime total `0x8014502C`), and `BattleResult_AwardDrops` (`0x801EF874`)
calls `Inventory_Add(category, id, count)` per list entry when the confirm
check `0x801636F0()` fires. The results need a button press: a 3 600-frame
window with no presses never left the victory banner.

**Banners and the escape.** The battle-end banners (the victory banner,
the escape notice) come from an 8-entry pool at `0x801EB460` (stride
`0xC`: `+0` active, `+1` kind bit, `+3` layer, `+4` text pointer, `+8`
timer). `BattleBanner_Dispatch` walks it every frame; `BattleBanner_Task`
(`0x801EA600`) runs slide-in / hold / slide-out on `0x80148644+6` (8 px per
frame between `-0x16` and `0x12`), `BattleBanner_DrawFrame(x, y)` draws the
`0x115 × 0x11` window in the theme colour and boot `0x8014F6BC` draws the
text. A successful Run (all three tries on `slot03` succeeded) plays the
kind-1 banner, then `Battle_PhaseStep_Escape` (`0x801D7114`, `0x801462DE++`)
and the common exit steps `0x801D71E0` / `0x801D72F8` that a victory also
runs after the tally, and the field returns ~400 frames after the press.

**Enemy skill damage bypasses `Battle_ApplyDamage`.** In `c_attack3` all
three members lost exactly 1 HP in one frame (`+583`) and in `nu_attack`
Teepo lost 1 HP, both from engine store PC `0x8009A3E4` (BATTLE.EMI#15,
`ra 0x8009A3E4`, args `(slot*0x140, 1, hp, …)`), while plain enemy attacks
in `c_defend4` / `c_watch4` went through `Battle_ApplyDamage`. The engine
PC sits in a Ghidra gap (no function covers it after the 2026-09-05
re-import) — seed it with `import --start` before reading the skill path.

## Game-mode overlay header

`0x801D0C00` starts with the word `0x10` and then a vector of 24 pointers
(`0x801D11D8`, `0x801D1C4C`, `0x801D2738`, …, many repeating
`0x801D51D8`). The boot dispatcher's reference to `0x801D0C04` is this
vector's first slot, so a game-mode overlay exports its entry points by
table, not by a fixed code entry. The same shape should hold for the
PLCHAR / BOSS / BMAGIC actor overlays — read one to get all.

## Open

- Confirm the flag-bit-2 variance reading (Defend vs something else) by a
  `capture --watch 0x801EB74C` during a Defend round against the same enemy.
- Party HP cell: `ramdiff` on a round where the enemy hits, deltas from
  the screen; expected `0x80145F14 + m*0x140`.
- ~~Decompile `Battle_BaseDamage` and the defence steps.~~ **Done 2026-09-05**
  (they are hit checks, not defence steps). Still unread: the elemental
  affinity function `0x8009FA78` (BATTLE.EMI#15) and the party
  `+0x26`/`+0x2A` derived stats. ~~What enemy `+0x08` is~~ — **level**, and
  party `+0x24` is **AGI** (turn order, 2026-09-05).
- ~~Where Run succeeds or fails, where Auto-attack fills the commands~~ —
  **found in the engine band** (section above). Still open: the Defend
  confirm body (store `0x801D2520` sits in a Ghidra gap after
  `BattleMenu_ConfirmDispatch`; seed it with `import --start`), the Defend
  flag `0x801462E4 & 0x80` (only `8` / `0x10` / `0x1C` were seen on the
  command captures, so `0x80` is set during the defender's own action), the
  effect handlers behind `Effect_ApplyResult`'s table `0x800B165C` (which
  index is the vitamin, which the steal — the handlers were not traced, the
  engine band being outside the round captures' filter), and the meaning of
  the AI script rows beyond the opcode byte. ~~Skill and item captures, the
  skill-damage function, where the heal lands~~ done (`c_skill` / `c_item` /
  `nu_item`; the slot03 party was at full HP, the Nu save shows the heal).
- The zenny bonus condition `0x801EF6C4()` and the level-reached check
  `0x801EF92C(roster, 0)` in `BattleResult_Setup`; the engine skill-damage
  writer `0x8009A3E4` (Ghidra gap).
- A drop capture: needs an enemy with a class-7 (certain) drop, or many
  kills; the writer to watch is `0x80146323` / `0x80146330`.
- From the save tool (2026-09-05): the meaning of the four ability *types*
  (`(0x801CB231 + id*16) & 3` — which list is magic, skill, gene), an
  id→name table for items/abilities (the tool prints ids), the block-head
  words `0x8014686C..0x80146878`, record `+0x84`, the block-head u16 from
  `0x80143F00` (10 vs 0 — area id?), and what forms ids 7, 8, 9 and 14 are
  (table `0x80182488`; 9 is the lone boy Ryu of save 1).
