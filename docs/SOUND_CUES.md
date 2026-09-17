# SOUND_CUES.md — the sound-effect trigger `SE_Play` and its cue tables

**Status:** STABLE (established 2026-09-17 from the Ghidra decompile of the
boot EXE and the live tables in three savestates; no trace yet ties a cue id
to a heard sound — that is the one open item)

`0x8015E908` was the "sound trigger" every text-engine and battle document
cited by address ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) `0x0A`, the menu cues
`0x100..0x107`, `Field_GiveZenny`'s `0x106`, 69 sites in the battle engine).
It is now `SE_Play` in `symbols.toml`, with the seven bank handlers, the
volume/distance wrappers, the per-frame key-status poll and the sound-set
layout function that fills the tables it reads. Decompiles:
`analysis/ghidra/SLPS_009.90_decomp/8015E908_*.c` and neighbours
(`ghidra_run.py export --program SLPS_009.90 --decompile 0x8015E908,...`).

## The call

```
SE_Play(cue)        cue = flags<<12 | bank<<8 | id
```

| Field | Bits | Meaning |
|---|---|---|
| `id` | 0..7 | index into the bank's 31-entry cue table |
| `bank` | 8..11 | 0..6, indexes the handler table `0x80182CA4` (`SE_CueSetup_Bank0..6`) |
| `0x8000` | 15 | keep the caller's L/R volume in `0x8018BD50/54`; without it a *panned* cue resets both to `0x17FF` |

Only bits 8..11 select the handler, so a cue byte in a script (`0x0A nn` →
`SE_Play(nn | 0x200)`) always lands in bank 2. The menu cues `0x100..0x107`
are bank 1; field and battle code use banks 3..6 as well. Banks 7..15 have
no handler: the words after the seven pointers at `0x80182CA4` are the
`SoundSet_Layout` tables, so a bank above 6 would jump into data.

## The banks — working model (player-verified 2026-09-17)

| bank | what | evidence |
|---|---|---|
| 0 | title screen only | only `slot00` has entries |
| 1 | the menu set `0x100..0x107`, context-free | same sound on every screen (player); the rest of the table differs field vs battle, and a loaded spell fires `0x100` with its own samples |
| 2 | field / general sounds and the script `0x0A` cue; in battle the hit family and `0x204..0x206` | table swapped for battle; AREA052 conveyor = `0x202` in the field, a hit in a fight |
| 3, 4, 5 | character voice slots, **dealt when the party's voice set loads and frozen until the next composition change** | Ryu/Nina/Momo = 3/4/5; field moves and menu reorders changed nothing; swapping Nina for Peco re-dealt Ryu/Momo/Peco = 3/4/5, which then held through a formation change |
| 6 | creature sounds: 8 types x 2 tones from the object's type byte `+0xE0` | `Battle_PlayCreatureCue`; heard on enemies, but the code keys on any object |

## What one call does (`SE_Play`, 0x8015E908)

1. `0x8018BD80 = bank` (the *first* store, `sh` at `0x8015E91C`), then
   `0x8018BD7C = id` (`0x8015E93C`) — the decompiler prints them the other
   way round, which cost the first `se_watch` session — then `SE_CueSetup_Bank<bank>()`
   fills the voice parameter block `0x8018BC80..0x8018BD84` from the bank's
   cue table entry and its VAB header (below).
2. If the cue is panned (`0x8018BD6C == 0x80`), each of the 1..4 voices'
   `volL/volR` become `volL*(0x80-pan)>>7`, `volR*pan>>7`; then unless
   `0x8000` was set, `0x8018BD50 = 0x8018BD54 = 0x17FF`.
3. First call ever (`0x80182CA2 == 0`): key every voice on with
   `SsUtKeyOnV(voice, vab, prog, tone, note, fine, volL, volR)`, apply
   `SsUtSetDetVVol(voice, L, R)` to panned cues, remember the primary voice
   in `0x8018BD68` and its priority in `0x8018BD64`, set the flag to `0xFF`.
4. Every later call: if the new cue's primary voice is the same one as the
   last cue's **and** its priority is lower (`0x8018BD60 < 0x8018BD64`)
   **and** `SE_PollKeyStatus` still shows that voice keyed
   (`0x8018EAB8[voice] != 0`), the cue is dropped. Otherwise key on as in 3.

Chords: the cue entry's bits 5..6 of byte 3 give 0..3 extra voices; the
handler assigns them `tone+n` and `voice+n`, wrapping the voice back into
16..23. Every live cue uses voices 16..23, leaving 0..15 for the sequencer.

`SE_PollKeyStatus` (`0x8015DA34`) runs once per frame from `Main_FrameLoop`
and stores `SpuGetKeyStatus(1 << v)` for `v = 0..23` into `0x8018EAB8[24]`.

## The wrappers

| Function | pc | What it adds |
|---|---|---|
| `SE_PlayVol` | `0x8015E1B8` | `(cue, volL_idx, volR_idx)`: looks both indices up in the attenuation curve `0x80182C00` (0x51 shorts, `0x3FFF` down to 0), then `SE_Play(cue)`. The caller has to OR `0x8000` into a panned cue or the volume is reset |
| `SE_PlayAtObject` | `0x8015E210` | `(cue, obj)`: the field object `0x801468B8 + obj*0x98` (`+2` x, `+6` z) against the listener `0x80145EC0/EC4`, five nested boxes of half-width `0x16/0x12/0xC/8/6` picking curve index `0x40/0x40/0x31/0x21/0x11`, one `SE_Play` per box the object is inside |
| `SE_PlayNearSelf` | `0x8015E5F8` | same boxes for the current object `*0x1F800044` (`+0x36` x, `+0x3A` z) against `0x80149304/308`, and `SE_Play(cue | 0x8000)` so the picked volume survives |

None of the three has a boot-EXE caller; they are overlay entry points.

## The cue tables

Each bank has a 31-entry, 4-byte cue table at `0x8014869C + bank*0x7C`
(`0x8014869C`, `0x80148718`, `0x80148794`, `0x80148810`, `0x8014888C`,
`0x80148908`, `0x80148984`). They are **zero in the EXE image** and filled
at runtime from the sound bank file, so read them from a savestate
(`tools/pst_tool.py ram`), not from `disc/SLPS_009.90`.

| Byte | Bits | Field |
|---|---|---|
| 0 | 0..2 | VAB override: when non-zero, tone attributes and the voice come from bank `n`'s header and table instead |
| 1 | 7 | pan flag (`0x8018BD6C`) |
| 1 | 0..6 | VAB program |
| 2 | 4..7 | tone |
| 2 | 0..3 | priority (higher wins a busy voice) |
| 3 | 5..6 | chord: extra voices |
| 3 | 0..4 | SPU voice |

Tone attributes come from the bank's VAB header `0x80148A14[bank]` at
`+0x820 + 0x80182B58[prog] + 0x80182B60[tone]` (`+2` volume, `+3` pan,
`+5` centre note, `+6` shift) — the standard `VagAtr` layout behind the
`VabHdr` and program table.

### Live contents

Read from `saves/openbios/state_8014AA0C_slot00/02/03.pst` (title screen,
AREA014 field, regular field battle). Counts per bank:

| State | Banks |
|---|---|
| title (`slot00`) | bank 0: 5, bank 1: 15, bank 2: 21, bank 3: 0, bank 4: 0, bank 5: 0, bank 6: 0 |
| field (`slot02`) | bank 0: 0, bank 1: 15, bank 2: 21, bank 3: 6, bank 4: 6, bank 5: 6, bank 6: 16 |
| battle (`slot03`) | bank 0: 0, bank 1: 15, bank 2: 21, bank 3: 6, bank 4: 6, bank 5: 6, bank 6: 16 |

Banks 3..6 are byte-identical between field and battle; banks 1 and 2 are
both re-filled for battle. The title screen carries the only non-empty bank
0, and the same bank 2 as the field.

**Bank 1 — field (menu / system cues, `0x100..`)**

| cue | flags | pan | prog | tone | pri | voice | chord |
|---|---|---|---|---|---|---|---|
| `0x100` | 0x00 | 1 | 0 | 0 | 10 | 22 | +1 |
| `0x101` | 0x00 | 1 | 0 | 2 | 10 | 22 | +1 |
| `0x102` | 0x00 | 1 | 0 | 4 | 10 | 18 | +1 |
| `0x103` | 0x00 | 1 | 0 | 6 | 10 | 20 | +1 |
| `0x104` | 0x00 | 1 | 0 | 8 | 10 | 20 | +1 |
| `0x105` | 0x00 | 1 | 0 | 10 | 10 | 20 | +1 |
| `0x106` | 0x00 | 1 | 0 | 12 | 10 | 20 | +1 |
| `0x107` | 0x00 | 1 | 0 | 14 | 10 | 20 | +1 |
| `0x108` | 0x00 | 1 | 1 | 0 | 10 | 22 | +1 |
| `0x109` | 0x00 | 1 | 1 | 2 | 10 | 20 | +1 |
| `0x10A` | 0x00 | 1 | 1 | 4 | 10 | 22 | +1 |
| `0x10B` | 0x00 | 1 | 1 | 9 | 10 | 22 | +1 |
| `0x10C` | 0x00 | 1 | 1 | 11 | 10 | 20 | +1 |
| `0x10D` | 0x00 | 1 | 1 | 13 | 10 | 18 | +0 |
| `0x10E` | 0x00 | 1 | 1 | 14 | 10 | 20 | +1 |

**Bank 1 — battle**

| cue | flags | pan | prog | tone | pri | voice | chord |
|---|---|---|---|---|---|---|---|
| `0x100` | 0x00 | 1 | 0 | 0 | 10 | 18 | +1 |
| `0x101` | 0x00 | 1 | 0 | 2 | 10 | 18 | +1 |
| `0x102` | 0x00 | 1 | 0 | 4 | 10 | 18 | +1 |
| `0x103` | 0x00 | 1 | 2 | 0 | 10 | 22 | +0 |
| `0x104` | 0x00 | 1 | 1 | 0 | 10 | 18 | +1 |
| `0x105` | 0x00 | 1 | 1 | 2 | 10 | 22 | +1 |
| `0x106` | 0x00 | 1 | 1 | 4 | 10 | 22 | +1 |
| `0x107` | 0x00 | 1 | 1 | 6 | 10 | 23 | +0 |
| `0x108` | 0x00 | 1 | 1 | 7 | 10 | 22 | +1 |
| `0x109` | 0x00 | 1 | 2 | 1 | 10 | 22 | +0 |
| `0x10A` | 0x00 | 1 | 2 | 2 | 10 | 22 | +0 |
| `0x10B` | 0x00 | 1 | 1 | 9 | 10 | 22 | +1 |
| `0x10C` | 0x00 | 1 | 1 | 11 | 10 | 20 | +1 |
| `0x10D` | 0x00 | 1 | 1 | 13 | 10 | 18 | +0 |
| `0x10E` | 0x00 | 1 | 1 | 14 | 10 | 20 | +1 |

**Bank 2 — field (the `0x0A` message cues and field effects, `0x200..`)**,
identical on the title screen:

| cue | flags | pan | prog | tone | pri | voice | chord |
|---|---|---|---|---|---|---|---|
| `0x200` | 0x00 | 1 | 0 | 0 | 10 | 16 | +1 |
| `0x201` | 0x00 | 1 | 0 | 2 | 10 | 16 | +1 |
| `0x202` | 0x00 | 1 | 0 | 4 | 10 | 16 | +0 |
| `0x203` | 0x00 | 1 | 0 | 5 | 10 | 16 | +2 |
| `0x204` | 0x00 | 1 | 0 | 8 | 10 | 16 | +1 |
| `0x205` | 0x00 | 1 | 0 | 10 | 10 | 18 | +1 |
| `0x206` | 0x00 | 1 | 0 | 12 | 10 | 16 | +1 |
| `0x207` | 0x00 | 1 | 1 | 0 | 10 | 16 | +0 |
| `0x208` | 0x00 | 1 | 1 | 1 | 10 | 22 | +1 |
| `0x209` | 0x00 | 1 | 1 | 3 | 10 | 20 | +1 |
| `0x20A` | 0x00 | 1 | 1 | 5 | 10 | 22 | +1 |
| `0x20B` | 0x00 | 1 | 1 | 7 | 10 | 22 | +1 |
| `0x20C` | 0x00 | 1 | 1 | 9 | 10 | 20 | +1 |
| `0x20D` | 0x00 | 1 | 1 | 11 | 10 | 20 | +1 |
| `0x20E` | 0x00 | 1 | 1 | 13 | 10 | 20 | +1 |
| `0x20F` | 0x00 | 1 | 1 | 15 | 10 | 21 | +0 |
| `0x210` | 0x00 | 1 | 1 | 13 | 10 | 16 | +1 |
| `0x211` | 0x00 | 1 | 1 | 13 | 10 | 18 | +1 |
| `0x212` | 0x00 | 1 | 1 | 13 | 10 | 22 | +1 |
| `0x213` | 0x00 | 1 | 2 | 0 | 10 | 16 | +3 |
| `0x214` | 0x00 | 1 | 2 | 4 | 10 | 20 | +3 |

**Bank 2 — battle**

| cue | flags | pan | prog | tone | pri | voice | chord |
|---|---|---|---|---|---|---|---|
| `0x200` | 0x00 | 1 | 0 | 0 | 10 | 22 | +1 |
| `0x201` | 0x00 | 1 | 0 | 2 | 10 | 20 | +1 |
| `0x202` | 0x00 | 1 | 0 | 4 | 10 | 20 | +1 |
| `0x203` | 0x00 | 1 | 1 | 0 | 10 | 22 | +1 |
| `0x204` | 0x00 | 1 | 1 | 2 | 10 | 20 | +1 |
| `0x205` | 0x00 | 1 | 1 | 4 | 10 | 19 | +0 |
| `0x206` | 0x00 | 1 | 1 | 5 | 10 | 18 | +1 |
| `0x207` | 0x00 | 1 | 1 | 7 | 10 | 18 | +1 |
| `0x208` | 0x00 | 1 | 2 | 0 | 10 | 16 | +3 |
| `0x209` | 0x00 | 1 | 2 | 4 | 10 | 20 | +3 |
| `0x20A` | 0x00 | 1 | 1 | 9 | 10 | 20 | +1 |
| `0x20B` | 0x00 | 1 | 0 | 6 | 10 | 22 | +1 |
| `0x20C` | 0x00 | 1 | 0 | 8 | 10 | 20 | +1 |
| `0x20D` | 0x00 | 1 | 0 | 10 | 10 | 20 | +0 |
| `0x20E` | 0x00 | 1 | 0 | 11 | 10 | 20 | +3 |
| `0x20F` | 0x00 | 1 | 1 | 15 | 10 | 21 | +0 |
| `0x210` | 0x00 | 1 | 1 | 13 | 10 | 16 | +1 |
| `0x211` | 0x00 | 1 | 1 | 13 | 10 | 18 | +1 |
| `0x212` | 0x00 | 1 | 1 | 13 | 10 | 22 | +1 |
| `0x213` | 0x00 | 1 | 2 | 0 | 10 | 16 | +3 |
| `0x214` | 0x00 | 1 | 2 | 4 | 10 | 20 | +3 |

**Bank 0 — title screen only**

| cue | flags | pan | prog | tone | pri | voice | chord |
|---|---|---|---|---|---|---|---|
| `0x000` | 0x00 | 1 | 2 | 0 | 10 | 16 | +1 |
| `0x001` | 0x00 | 1 | 2 | 2 | 10 | 21 | +0 |
| `0x002` | 0x00 | 1 | 2 | 3 | 10 | 23 | +0 |
| `0x003` | 0x00 | 1 | 2 | 4 | 10 | 23 | +0 |
| `0x004` | 0x00 | 1 | 2 | 5 | 10 | 22 | +0 |

Banks 3..5 hold the same 6-cue table each (programs 0..2, priority 11 on cue
1); bank 6 holds 16 cues = programs 0..7 × tones 0/2. Same savestates; the
decode is `tools/pst_tool.py ram` plus the 4-byte field split above.

## Where the tables come from — `SoundSet_Layout` (0x801621F8)

`SoundSet_Layout(set)` lays a set's seven VAB header/body pairs out back to
back from `0x8011A000` using three per-set tables of stride `0x1C`:

| Table | Per bank | Set 0 | Set 1 | Set 2 |
|---|---|---|---|---|
| `0x80182CC0` | SPU RAM start | `0x1010`, `0x3E0A0`, `0x4F210` | seven, `0x1010..0x71CC0` | `0x1010`, `0x6C6D0` |
| `0x80182D14` | header bytes | 10784, 4128, 4640 | 9760, 3616, 3104, 4128, 4128, 4128, 6688 | 12320, 4640 |
| `0x80182D68` | body bytes | 50080, 0, 4096 | 36192, 0… | 54176, 0 |

It writes the bank descriptors `0x80146778 + bank*0x14` `{spu addr, header,
body, cue table, bank id}` and the header pointers `0x80148A14[7]` the
handlers read. The header pointers in the savestates identify the set:
`slot02`/`slot03` carry set 0's layout (`0x8011A000, 0x80128DC0,
0x80129DE0, 0x8012C000…`) and `slot00` carries set 2's (`0x8011A000,
0x8012A3C0, 0x8012B5E0…`). `Boot_Init` (`0x8014E974`) calls
`SoundSet_Layout(0)` and then `File_LoadRequest(0x261)`; the copy that fills
the cue tables is not visible statically (the tables have no boot-EXE
writer), so it is part of that file load or its DMA.

## Battle: how a cue is chosen (2026-09-17, second live session)

The battle cues are not looked up per spell. Three mechanisms, all now
named (`names/functions.toml`, `symbols.toml`):

**Per-character cues, banks 3/4/5.** `Battle_PlayActorCue(index)`
(`BATTLE.EMI 0x801DD820`) reads a 6 x 3 halfword table at `0x801EAF80`:
row = index 0..5, column = the actor's kind (`obj+0x2C`, 0..2), and the
entries are simply `0x03nn / 0x04nn / 0x05nn` — so **bank = 3 + the
actor's voice-set index, id = index**, and the three banks carry identical
six-cue tables because they are the three characters' personal sets. What
the six indices are, from the callers:

| index | chosen by | evidence |
|---|---|---|
| 2, then 4 | `Battle_SwingCue_Step` (`0x801DFA14`, twin `0x801E1FA8`): the normal swing pair | Ryu `0x402+0x404`, Nina `0x502+0x504` in one frame |
| 3, then 4 | same, when `Rand(3) % 100 < ctx+0xAA` (the crit roll — it also sets bit 7 of `0x801462E4`) | the crit variant |
| 1 / 0 | `Battle_Impact_Step` (`0x801DFF0C`) on damage, by `ctx+0x128 & 2` | |
| 5 | `0x801E1814` (then 3 conditionally) | **the character's spell-cast voice**: Momo `0x505` and Ryu `0x305` casting the same MAGIC070 (薬草 / アプリフ) resolved to different samples, while the spell's own `0x100` (from `0x801EEF8C` inside the overlay) and the `0x206` restore effect (via `SE_PlayTracked`) were the same sample for both — player + resolver, 2026-09-17 |

So Nina's `0x502+0x504` labelled "Chlorine" is her **slot's swing pair**,
fired for 毒撃 because 毒撃 (ability 8, type 3) is a physical skill; the
same pair plays for her normal attack. It is not the spell's sound.

**Hit sounds, bank 2.** `Battle_PlayHitSound` (engine `0x800A8764`):
`class` = the equipped **weapon record byte `+0x0D`** for a party member
(`0x801C9F24 + id*0x14`), or the **enemy record byte `+0x71`**
(`0x801EB620 + n*0x118`); cue = `0x800B202C[crit][class]`:

| class | weapons | normal | crit |
|---|---|---|---|
| 0 | staves, rods, sticks | `0x202` | `0x203` |
| 1 | daggers | `0x200` | `0x201` |
| 2 | swords | `0x200` | `0x201` |
| 3 | (none in the weapon table) | `0x200` | `0x201` |
| 4 | (none) | `0x202` | `0x203` |
| 5 | ammo, chrysms, shells | `0x202` | `0x203` |
| 6 | spears | `0x200` | `0x201` |

Constants elsewhere in the battle table: `0x204` (`0x801E4794`, the
enemy-side hit), `0x205` (miss, heard), `0x206` through `SE_PlayTracked`
from `Battle_Impact_Step`.

**Creature cues, bank 6.** `Battle_PlayCreatureCue` (`0x801E39BC`):
`SE_Play(0x600 | obj->0xE0 << 1)` — the object's byte `+0xE0` is its
creature sound type 0..7 and bank 6's 16 cues are 8 programs x tones 0/2.

**A cue word is not a sound once a spell is loaded.** Third session
(2026-09-17): the same `0x100` through `SE_PlayTracked` was a different
sound per spell cast, and Ryu's `0x305` a different line on two casts.
The reason is the audio triplet every sound-bearing `.EMI` carries (next
section): a spell ships its own miniature VAB and the cue entries that
point at it, installed over bank 1's slot. The identity of a battle sound
is therefore the **sample**, which is what `se_watch` now labels. (An
earlier reading blamed the type-3 sections; those are art.) The per-slot
banks 3/4/5 are dealt at party load — see the bank model above.

**Spells.** 12 of the 141 `BMAGIC` overlays call `SE_Play` directly, all
with bank 1 words — those are their own sample triggers (`MAGIC064`:
`0x100/0x101/0x102`, `MAGIC113` six calls); the rest fire through the
effect interpreter and `SE_PlayTracked`. `MAGIC008.EMI` (毒撃) contains no
call to the `SE_Play` family, and across all 141 `BMAGIC` overlays only 12 call it, all with
bank 1 (menu) constants. Whatever distinctive sound a spell has therefore
comes through the effect interpreter, most likely `SE_PlayTracked`
(`0x8015E10C`, which records the keyed voices in the effect object) —
and the write trace cannot see past that wrapper because `SE_Play`'s `ra`
is inside it. Next step for spells: arm the trace on `SE_PlayTracked`'s
own first store (`0x8018BC94`) or add the wrapper to `se_watch`.

## Inside an .EMI: the audio triplet (2026-09-17)

The "consistent spot" the player asked for. Every sound-bearing `.EMI`
carries a run of three sections with the same TOC `+0x04`, which for these
is the **bank id 0..6**, not an address ([`EMI_TYPES.md`](EMI_TYPES.md)):

| type | content | how the runtime uses it |
|---|---|---|
| 6 | a VAB header (`pBAV`, `0xC20` bytes for one program) | registered as VAB *bank* in libsnd (`0x8018EB18[bank]`); its tone attributes map tone → VAG, centre note, volume |
| 8 | **the cue-table entries**: 4 bytes per cue word `{flags, pan\|prog, tone\|priority, chord\|voice}` | copied to the head of bank's 31-entry table at `0x8014869C + bank*0x7C`; a 16-byte record defines `bank<<8 \| 0..3`. Entries past the record are **not cleared**, so the previous occupant's words stay reachable — which is why the live table hash keeps changing and why a menu word can play a spell's sample |
| 7 | the VAB body (the VAG samples) | uploaded to the bank's SPU RAM slot (`0x80191550[bank]`) |

`MAGIC069.EMI` (めいれい / Influence — the player's "Command"; the ability
table's names are one record off the engine ids, see [`STEAL.md`](STEAL.md),
so engine id 69 is row 68), the three-sound skill the player heard: one program, four VAGs; the type-8 record installs `0x100..0x103`
as tones 0/2/4/6 → VAG 1/2/3/4, and the catalogue hashes match the disc
bytes exactly — VAG 1 = "Target", VAG 2 = "Whisk Away", VAG 4 = "Locked
On" (VAG 3, 29,040 bytes, was not heard). The *order* of the three is the
spell's script, run by the effect interpreter; the sounds are the body.

Who lives in which bank, from the 901 triplets on the disc
(`tools/audio_banks.py index` → `names/audio_banks.toml`):

| bank | files | what |
|---|---|---|
| 1 | `COMN_SE.EMI`, `BATTLE*.EMI`, `BOSS*.EMI` (11 entries), `BATL_RET`/`BATL_SE` (4), `MAGIC*` (1..6) | the system set — the menu blings the player confirmed as context-free are `COMN_SE`'s VAGs 1..8, duplicated in every battle file — and each spell's own samples over `0x100..` |
| 2 | `BATTLE*.EMI`, `BOSS*.EMI` (7), `AREAnnn.EMI` (3..13) | field / battle effects |
| 3, 4, 5 | `BPLCHAR/BPLD*.EMI`, `BPLU*.EMI` (207 files) | the party voice slots; the file name carries the character ids of the party they were built for |
| 6 | `BENEMY/ENEMYnnn.EMI` (200), `BOSS*.EMI` | creature sounds, named by species from the area's table (`names/enemies.toml`): **one enemy file per area** (`ENEMYnnn` = `AREAnnn`'s encounter group, no area file carries a bank 6 of its own), 8 programs = 8 species slots, cue `0x600 + 2*slot + tone`; the object's creature byte `+0xE0` is its slot in that group. 58 distinct groups; the set in 123 files (towns, story rooms, the world map, Dauna Mine) is the generic one, and the 77 others are the fight areas (Cedar Woods, Nu Cave, McNeil Manor, the Tower, Mount Mourangi, the Dump Site…). Boss files add a 1-program set for the boss |

`tools/audio_banks.py join --apply` writes each catalogue sound's disc
homes into `names/se_cues.toml` (`disc = [...]`); 28 of the first 29
labelled sounds matched (the one miss is a 352-byte blip that appears in
1,548 files under other hashes' neighbours). `se_watch` prints the first
disc home beside each resolved cue.

## Cataloguing by sample, not by cue word (2026-09-17)

The player's diagnosis after three sessions: the cue word is a **slot**.
Battle saves an array, executes from the array, and the slot holds whatever
is needed to reach a sound — so `0x302+0x304` is "slot 0's swing" for any
character with any weapon, `0x100` is "the loaded spell's sample", and a
label on the word is only true for the state that was loaded. The stable
identity is the sample itself. `tools/se_resolve.py` follows the runtime's
own chain from a cue word to the bytes that will play:

| step | where | what |
|---|---|---|
| cue entry | `0x8014869C + bank*0x7C + id*4` | `{flags, pan\|prog, tone\|pri, chord\|voice}`; `flags & 7` overrides the VAB |
| VAB header | libsnd registry `0x8018EB18[vab]` | what `SsVabOpenHead` registered — **not** the game's `0x80148A14` pointers, which lag behind |
| tone attributes | libsnd `0x8018EB60[vab] + prog*0x200 + tone*0x20` | `+2` vol, `+3` pan, `+4` centre, `+5` shift, `+0x16` VAG index |
| VAG size table | header `+0x20 + nprog*0x10 + ps*0x200` | 256 u16 in 8-byte units; `nprog` is 0x80 for header byte `0x70` and version > 4 |
| sample | libsnd `0x80191550[vab]` + sum of the earlier VAG sizes | read from SPU RAM (`spu_ram`, 4 KB per call) and hashed |

Checked on the savestates: `0x202` is a 5,776-byte VAG at `0x60CF0`
(centre 52) in battle and a 9,584-byte one at `0x562E0` in the field;
`0x302` keeps its VAG slot but the bytes differ between `slot02` and
`slot03`, which is the party-slot behaviour heard in play. `se_watch`
now resolves every cue live, keys `names/se_cues.toml` by the sample's
md5, and records each `cue@context` a sample was reached through, so the
file accumulates the slot map as a by-product. The cue-keyed catalogue
from the first three sessions is kept as
`analysis/se_cues_by_cue_2026-09-17.toml` (the merged menu wording is in
the commit that reset it).

Limits: banks whose VAB libsnd has not reopened resolve to "not a VAB"
(the 2026-09-05 savestates show this for vabs 5 and 6; live play does
not), and the hash covers the sample only — the same VAG at another
centre note is listed once with its first pitch.

## Enemies: set groups per area, not a party-style concatenation (2026-09-17)

The party voice files are built per character combination; the enemy
files are not. Every `ENEMYnnn.EMI` is a ready-made **group of up to 8
species** — 8 programs, 16 cue entries `0x600..0x60F` = slot × 2 + tone —
and the number is the area's: no `AREA` file has a bank 6 of its own, and
the files with a non-generic set are precisely the areas with random
encounters (Cedar Woods 3/5/8/9/10, Nu Cave 22, McNeil Manor 27/28, the
Tower 40/42/44/48, Mount Mourangi 51, Dump Site 52 …), while towns, story
rooms and the world map carry the one generic set found in 123 files. So
an enemy's creature byte `+0xE0` selects its slot within the area's group,
and naming a bank-6 sample means naming the species in slot n of area
nnn's encounter table — the enemy table this repo does not have yet. The
boss fights add a `BOSSnnn` bank-6 set of one program for the boss itself.

**The names are on the disc.** Every `AREAnnn.EMI` carries a 1,160-byte
section at `0x800E4000`: eight `0x88`-byte species records — the table the
slot byte (record `+0x60`, also the AI-script row) indexes — with the
**8-byte name at `+0x48`** in the game's kana codes and the stat halfwords
at `+0x54` (zenny, EXP, level, …, max HP, AP, ATK, DEF, AGI, Int; the
wiki's Orc page matches やけっぱちオーク L18 HP100 AP20 50/17/11/30 EXP58
zenny62 field for field). `tools/enemy_table.py extract` writes all 200
tables to `names/enemies.toml` (448 species rows, 168 distinct names) and
merges English names from `names/enemy_gloss.toml`, seeded from the
Breath of Fire wiki's enemy list (168 of 168; the Tower frog is
named just Gi / ギ in both releases, filed by the wiki as Ice Toad). `se_watch` reads the name
live from the same table on every bank-6 cue, and `--label` only asks for
an English name when the gloss lacks one. The audio catalogue names bank-6
samples by species: `Lizard (ENEMY040) 1`.

## Names for every sample, by convention (2026-09-17)

The player's rule, now `tools/audio_banks.py names --apply`: a sample is
named **after the file that owns it plus its VAG number** — `Influence 1`,
`Rei 3`, `System 10`. Owner = the first file carrying those
bytes by family precedence (`COMN_SE`, `BATTLE`, `BATL_*`, `MAGIC`, `BOSS`,
`ENEMY`, the party files, then `AREA`), lowest-numbered within a family.
The display stem is the ability name (`names/magic.toml`), the area alias
(`names/areas.toml`), the character for a party-file bank
(`names/characters.toml`), else the file stem; two owners whose display
collides but whose samples differ keep the stem (`Ryu (BPLD012)` vs `Ryu (BPLD034)` — the adult and the child voice). All 833 samples got a unique name; `names/se_cues.toml` carries it
as `auto` beside the player's `label`, with status `derived` until someone
listens. The ten samples labelled so far all agree with their auto names
(Rei 1 = "Rei - Pilfer", Rei 6 = "Strike", Teepo 5 = "Nega", Influence
1/2/4 = Target / Whisk Away / Locked On). Spell stems apply the one-record
shift of the ability names (engine id N = abilities row N-1).

**The party voice files decode the slot behaviour.** `BPLD034.EMI` is the
party of character ids 0, 3, 4 (`names/characters.toml`: 0 Ryu, 1 Nina, 2
Garr, 3 Teepo, 4 Rei, 5 Momo, 6 Peco), its three triplets are banks 3/4/5
in digit order, and the digits are sorted — so the file for Ryu/Nina/Momo
is `BPLD015` (banks 3/4/5 = Ryu/Nina/Momo) and after Peco replaces Nina it
is `BPLD056` (Ryu/Momo/Peco) — which is exactly why Momo moved from bank 5 to bank 4 when Nina (1)
left and Peco (6) joined, and why neither the menu order nor the field
position moved anything. `BPLU*` is byte-identical to `BPLD*`; `BRTD/U`
carry a second set for the same characters (tagged `(BRT)`); `PL*` are the
field parties (bank 1); `RYUD/U` are the dragon forms.

## Open

- **Hear one.** No trace yet pairs a cue id with an audible sound.
  `tools/se_watch.py` is the hook (labels keyed by sample, see below): a write trace on the two halfwords
  `SE_Play` stores first (`0x8018BD7C` id, `0x8018BD80` bank) — the same
  no-framework-change trick as `tools/load_watch.py` — logs every cue with
  its caller to `analysis/se_timeline.jsonl` during any play session, and
  `--label` asks what was heard and writes `names/se_cues.toml`, keyed by
  cue *and* mode because both tables are swapped for battle. First live run
  2026-09-17: the write trace fires per call and the paired cues match
  what was heard (menu cursor left/right are two cues, item-list up/down
  one); that run's four labels are `hypothesis` because the pairing was
  wrong before the fix. The caller name is resolved against the overlay
  actually resident in the swap slot, falling back to the Ghidra export's
  `FUN_*` boundary for `START.EMI`, which has one human name so far.
  **Mode is the live table, not the resident overlay:** after a fight
  `BATTLE.EMI` stays in the swap slot while the area's own code is already
  cueing field sounds (AREA052's conveyor loop calls `SE_Play(0x202)` every
  ~36 frames from `0x801F3F18`, the same word that is a hit in battle), so
  `se_watch` hashes banks 1+2 at `0x80148718..0x80148810` against the two
  savestate tables to key a label.
- Set 1 (seven banks) has not been observed in a savestate.
- `0x8018BD5C` is the extra-voice count and `0x8018BD84` the tone-attribute
  offset; the rest of `0x8018BC80..0x8018BD84` is the per-voice parameter
  block and could go into `names/regions.toml`.
