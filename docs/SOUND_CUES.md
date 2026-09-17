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
party slot's kind, id = index**, and the three banks carry identical
six-cue tables because they are the three characters' personal sets. What
the six indices are, from the callers:

| index | chosen by | evidence |
|---|---|---|
| 2, then 4 | `Battle_SwingCue_Step` (`0x801DFA14`, twin `0x801E1FA8`): the normal swing pair | Ryu `0x402+0x404`, Nina `0x502+0x504` in one frame |
| 3, then 4 | same, when `Rand(3) % 100 < ctx+0xAA` (the crit roll — it also sets bit 7 of `0x801462E4`) | the crit variant |
| 1 / 0 | `Battle_Impact_Step` (`0x801DFF0C`) on damage, by `ctx+0x128 & 2` | |
| 5, then 3 | `0x801E1814` | unnamed step |

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
sound per spell cast, and Ryu's `0x305` a different line on two casts. The
`.EMI` census explains it: **80 of the 144 `BMAGIC` overlays carry a type-3
section of 8..64 KB** (dests like `0x1A080200` / `0x1C080200`, a sample
payload for the SPU), and the bank 1+2 cue tables were rewritten five
times in one session (five distinct hashes). A spell therefore loads its
own samples behind the same program slot and fires them as `0x100` (one
overlay call site seen at `0x801EEF8C`, plus the interpreter path), so the
identity of a battle sound is **cue + the resident spell overlay**.
`se_watch` keys labels by that context (`magic:<name>`, else
`field`/`battle`, else `tables:<hash>`) and dumps every new table to
`analysis/se_tables/`. The per-slot banks 3/4/5 follow **party position**
(the `obj+0x2C` column: Ryu in slot 0 = bank 3, Nina slot 1 = bank 4, Momo
slot 2 = bank 5), not the character id — swap the formation to confirm.

**Spells.** `MAGIC008.EMI` (毒撃) contains no call to the `SE_Play`
family, and across all 141 `BMAGIC` overlays only 12 call it, all with
bank 1 (menu) constants. Whatever distinctive sound a spell has therefore
comes through the effect interpreter, most likely `SE_PlayTracked`
(`0x8015E10C`, which records the keyed voices in the effect object) —
and the write trace cannot see past that wrapper because `SE_Play`'s `ra`
is inside it. Next step for spells: arm the trace on `SE_PlayTracked`'s
own first store (`0x8018BC94`) or add the wrapper to `se_watch`.

## Open

- **Hear one.** No trace yet pairs a cue id with an audible sound.
  `tools/se_watch.py` is the hook: a write trace on the two halfwords
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
