# World items — the searchable spots, and how to read them all off the disc

**Status:** DONE for the mechanism and the extraction (2026-09-07). Open
questions are listed at the bottom; none of them block using the table.

Every dresser, pot, barrel, shelf and patch of ground the game lets you
"search" is one **8-byte record** in a per-area array. The array is reached
through a table that is *constant data in the boot EXE*, so the whole world's
item placement can be read statically — no emulator, no play session.

    python tools/world_items.py                 # all 200 areas -> analysis/world_items.json
    python tools/world_items.py --area 27       # one area, printed in full

**517 records across 200 areas: 98 items, 24 zenny caches (6 640z in total),
395 empty spots.** 105 areas have nothing to search.

## How it was found

Kevin left a savestate parked in front of a dresser in マクニールていない
(McNeil Manor interior, AREA027) that pays 120 zenny. `slot03`, Circle opens
「何かないかな」 and a second Circle pays out.

The idle animation matters: `scene.py enter()` settles ~2 s of real time and
then spends another ~2 s proving the guest resumed, and by then Ryu has turned
round to eat an apple and is no longer facing the dresser. Press within ~50
emulated frames of the restore (`analysis/dresser/probe.py`), or hold up+left
first to re-face him.

One `callstack_diff.py capture --watch` over the whole save block caught the
entire mechanism in a single frame (`analysis/callstacks/dresser_flag.json`,
frame +80):

| Write | Writer | Meaning |
|---|---|---|
| `0x80144F4C` `0x108` → `0x180` | `Zenny_Add` `0x80166FFC`, ra `0x801B6EA0` | +120 zenny |
| `0x8014502C` +120 | same | lifetime zenny |
| `0x80145030` `0x0A` → `0x0B` | store pc `0x801B4028` | world items found, +1 |
| `0x80145002` bit 1 set | `0x8015BF70`, ra `0x801B4044` | "this spot is emptied" |

A byte-level `ramdiff` over `0x80144000-0x80146000` confirmed those were the
only save-block cells that moved (the rest are the play-time counter).

## The bit-array API (boot EXE)

`Flag_Test` had a family nobody had named. All four take `(base, bit index)`
and are 8–12 instructions:

| PC | Name | Body |
|---|---|---|
| `0x8015BF70` | **`Flag_Set`** | `base[i>>3] \|= 1 << (i&7)` |
| `0x8015BF98` | **`Flag_Clear`** | `base[i>>3] &= ~(1 << (i&7))` |
| `0x8015BFC4` | `Flag_Test` | `(base[i>>3] >> (i&7)) & 1` |
| `0x8015BFE4` | **`Flag_Toggle`** | `base[i>>3] ^= 1 << (i&7)` |

**There are two separate flag arrays**, and this is the trap: the story
progress array is at `0x80144F24` ([`BATTLE_RAM.md`](BATTLE_RAM.md)), but world
items use **`0x80145000`**. The first capture watched `0x80144F24-0x80144F50`
and saw the zenny move with *no* flag write, which is what sent the search
wider. Both arrays are inside the save image, so both persist.

`0x80145030` (u32) counts how many spots have been emptied — 10 on the
savestate, 11 after the dresser.

## The record

`GAME.EMI` **`Field_SearchSpot` `0x801B3FC0`** answers the search button. It
asks **`Field_FindSearchSpot` `0x801B6C4C`** which spot the player is facing;
that walks the per-area array of 8-byte records:

| Off | Size | Meaning |
|---|---|---|
| `+0` | u8 | X tile |
| `+1` | u8 | Y tile |
| `+2` | u8 | flags — bit `0x80` makes the run extend along **Y** instead of X; low bits unread |
| `+3` | u8 | run length in tiles; **0 disables the record** |
| `+4` | u8 | bit index into the `0x80145000` array; **`0xFF` = no flag → repeatable** |
| `+5` | u8 | item id, **or** zenny ÷ 40 when `+6` is `0xFF`; **bit `0x80` set = the spot is empty** |
| `+6` | u8 | inventory category, **`0xFF` = zenny** |
| `+7` | u8 | 0 in all 517 records |

and the handler is:

```c
rec = Field_FindSearchSpot();
if (Flag_Test(0x80145000, rec[4]))        Msg(1);              /* already taken */
else if (rec[6] == 0xFF)                  Field_GiveZenny(rec[5] * 40);
else                                      ok = Inventory_Add(rec[6], rec[5], 1),
                                          Msg(ok ? 2 : 3);     /* got it / no room */
if (ok && rec[4] != 0xFF) { Flag_Set(0x80145000, rec[4]); *(u32 *)0x80145030 += 1; }
```

**`Field_GiveZenny` `0x801B6E50`** is the small wrapper: cue `0x8015E908(0x106)`,
`sprintf(0x801490D4, fmt 0x80196FBC, amount)` into the message buffer,
`0x801503AC(5)`, `0x80143BB0 = 2`, `Zenny_Add(amount, 0)`.

**The categories are `0` consumable, `1` weapon, `2` armour, `3` accessory** —
matching `names/items.toml`'s own `cat` field and the 4×128 inventory at
`0x80145048`. Key items are a *separate* list (`0x80145448`), which is why the
key rows in `names/items.toml` carry no `cat`; no search-spot record uses them.
Getting this wrong is easy and quiet: an early pass mapped `1` to "key" and
happily printed a Bent Sword as a key item.

### The two sentinels in `+5`

`0x80` (382 records) and `0xC0` (13) both mean "you searched it, there is
nothing here". No real id in any of the five item tables reaches `0x80`, so
`rec[5] & 0x80` is the test. What distinguishes `0xC0` from `0x80` is not
known — every `0xC0` record also has category 2 (armour), which suggests the
pair encodes *which* empty-handed message plays rather than anything about
items.

## Why it is static

```
struct_ptr = *(u32 *)(0x801802EC + area * 4)   /* boot EXE, 200 constant entries */
records    = *(u32 *)(struct_ptr + 0x2C)
count      = *(u8  *)(struct_ptr + 0x31)       /* n = count + 1; 0xFF or a null
                                                  array pointer = no spots */
```

All 200 entries of `0x801802EC` point into `0x801F2C00`, which is the section
every `AREAnnn.EMI` carries. So the boot EXE says *where in the area section*
the array sits, and the area file supplies the bytes.

Verified against the live game on AREA027: the boot table gives
`0x801F4D20`, which is exactly what the running game had; `+0x2C` =
`0x801F3BBC`, `+0x31` = `0x47` (72 records); record 35 is
`3c 04 87 02 11 03 ff 00` — tile (60,4), flag `0x11`, 3 × 40 = 120 zenny — the
dresser. The same bytes appear in `AREA027.EMI` at file offset `0x0CB8D4`,
inside the `0x801F2C00` section at `+0x10D4`.

## What the corpus says

Two independent checks that the decode is right, neither of them circular:

* **Every one of the 98 item records resolves to a real name**, and every id
  is inside its table's range (consumable ≤ 88 of 92, weapon ≤ 28 of 83,
  armour ≤ 33 of 68, accessory ≤ 44 of 52). A wrong stride or a swapped
  id/category field would scatter ids out of range immediately.
* **The flag indices run near-sequentially `0x01`–`0x68` in progression
  order** — McNeil Village `0x01`–`0x03`, Cedar Woods `0x04`, McNeil Manor
  `0x0A`–`0x1C`, Wyndia `0x1E`–`0x2D`, … the Desert `0x5C`, O-BARD
  `0x5D`–`0x65`. The designers allocated them as they built the game, which is
  exactly what a per-spot persistent flag should look like.

Seasonal and duplicate maps share flag indices with their twin (McNeil Village
S/A both use `0x01`–`0x03`; グラウスまえのもり S/A both `0x4E`–`0x50`), which is
correct — the array is global, so emptying a spot in one season empties it in
the other.

Two records have flag `0xFF` and are therefore **repeatable forever**: the
しずく (Croc Tear) in シーダのもり, in both the S and A variants (AREA003 tile
(42,45) and AREA008, the same tile). Whether that is a designer's oversight or
deliberate is unread.

The richest area by far is **AREA027 マクニールていない** — 72 records, 13 of
them rewarding, including the 600z and the 120z Kevin parked in front of.

## Left open

* The low bits of `+2` (values `0x01`–`0x08` seen) — only bit `0x80` is read by
  `Field_FindSearchSpot`. They may be a height/layer, or unused.
* What separates the `0x80` and `0xC0` empty sentinels.
* The rest of the per-area struct the table points at: `Field_FindSearchSpot`
  uses only `+0x2C` and `+0x31`, but the struct head holds a dozen more
  pointers into the same section (AREA027: `0x801F3DFC`, `0x801F4A30`,
  `0x801F4CE4`, …) — the other per-area object lists, unread.
* `names/items.toml` has no English for 知力の研 (AREA062, AREA171).
* `names/items.toml`'s key rows are missing a `cat` field — worth fixing in
  `tools/text_tables.py` so no later consumer repeats the collision.

## Files

| Path | What |
|---|---|
| `tools/world_items.py` | the static extractor |
| `tools/area_pcs.py` | which PCs each of these places needs — [`AREA_PCS.md`](AREA_PCS.md) |
| `analysis/world_items.json` | all 517 records, decoded and joined to item / place names (gitignored — derived from the disc) |
| `analysis/callstacks/dresser_flag.json` | the write-trace capture that found the mechanism |
| `analysis/ramdiff/dresser_flag.*` | the byte-level save-block diff |
| `analysis/dresser/probe.py` | load a slot and press before the idle animation turns Ryu around |
