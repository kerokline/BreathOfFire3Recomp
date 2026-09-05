# Battle RAM map and damage path — first data anchors

**Status:** IN PROGRESS (opened 2026-09-04, last extended 2026-09-05 with level-up, inventory, equipment and the save format). It began as one
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
| `0x80145FA4..FA5` | `+0x118,+0x119` | battle bytes (`0x801DD264`, `0x801DB45C`) | |
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
| `0x801EB622` | `+0x02` status-flag halfword | `Battle_CalcDamage` |
| `0x801EB628` | `+0x08` u16 (10 for both `slot03` enemies) — the enemy's damage bonus term `+0x08 * (2..3) / 10`; level? *?* | `Battle_BaseDamage` |
| `0x801EB634` | `+0x14` **HP** (u16) — `0x801EB74C` is enemy 1 | `Battle_ApplyDamage` |
| `0x801EB640` | `+0x20` **max HP** (u16) — `0x801EB758` fed to the HUD; `+0x22` max AP (18) | `Battle_ApplyDamage`, `Battle_BeginAction` |
| `0x801EB644` | `+0x24` **ATK** (19), `+0x26` **DEF** (11), `+0x28` (7), `+0x2A` (20) | `Battle_BeginAction` → `0x801EC27C` |
| `0x801EB654` | `+0x34` type / size class byte (5) | `Battle_ScaleDamage` |
| `0x801EB69C` | status byte | `Battle_ApplyDamage` |
| `0x801EB69D` | byte zeroed on status clear | `Battle_CalcDamage` |
| `0x801EB6A0` | flags u32 (`0x100`, `0x10000`) | both |
| `0x801EB6A4` | flags u32 (`0x40` charge) | `Battle_CalcDamage` |
| `0x801EB6B4` | charge multiplier byte | `Battle_CalcDamage` |

### Persistent character records — boot-EXE data, `0x80144964 + roster*0xA4`, 8 records

Base and stride are **proven by code**: `Char_RecalcStats` compares its
argument against `&0x80144964 + n*0xA4` for n in 0..7, and `Char_LevelUp`
indexes the same array. Records are indexed by **roster index** (Ryu 0,
Teepo 3 — confirmed over two battles; **Rei 4**, read off `slot03` where
slot 2 carries character id 4 and roster byte 4 — Nina / Momo / Peco /
Garr still unplaced), not by
battle slot; the working record's byte at `0x80145FC8` holds the roster
index and `CharId_ToRosterIndex` maps the character-id byte to it.

| Offset | Field | Evidence |
|---|---|---|
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
| `+0x71..` | learned ability list (first free byte gets the new id; 10 slots via a lookup) — Teepo gained `0x5E` at L4 | `AbilityList_Add` |
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
| `0x801448D4` | summary block written at save time: play time (from `0x8014686C..`), date bytes (`0x80146860..`), slot-0 world x/z (`0x80145EC0/C4`), facing (`0x80145E94`), `0x80143F00`, nine u16 from `0x80145AB0` |
| `0x80144944` | **u16 checksum slot** (zeroed before the copy; file `+0x270`) |
| `0x80144964` | 8 character records × `0xA4` |
| `0x80144E84..0x80144F4C` | unlabelled |
| `0x80144F24` | `0x92` bytes hashed by boot `Save_FlagsChecksum` `0x8015BFC4` → `0x80145588` |
| `0x80144F4C` | zenny; `0x80144F56` party ids × formations; `0x80144FBC..` |
| `0x8014502C` | lifetime zenny; `0x80145048..0x80145448` inventory (4 × 128 ids, 4 × 128 counts); `0x80145448` key items; `0x80145468` ability list |
| `0x80145574` | save-slot summary: 5 bytes from `0x80144964`, party ids (`+5..+7`, Peco special-cased), level `+8`, `+0xC` ← `0x80144FBC`, `+9/+A` ← `0x8014494E/F`, EXP `+0x10`, flags checksum `+0x14` |
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
  affinity function `0x8009FA78` (BATTLE.EMI#15), what enemy `+0x08` is,
  and the party `+0x24`/`+0x26`/`+0x2A` derived stats.
