# Stealing — the roll, where it lives, and the "always succeeds" mod

**Status:** EVIDENCE + BUILT (2026-09-13). The steal roll was found live
(write trace + RNG call-site trace from the user's Pilfer anchor, file slot
`slot03`), decoded from the resident overlay bytes, matched word for word
against the community formula, and turned into a declarative mod package
(`mods/preloaded/packages/bof3.steal-always/`) that stole on 6 of 6
headless replays where the stock game stole on 0 of 22.

## Where the roll is

Pilfer (ぶんどり, Rei) and Steal (盗む) are **not** resolved by the battle
engine's effect handler. Each ability loads its own BMAGIC overlay
(`Magic_LoadForAbility`, [`names/magic.toml`](../names/magic.toml)) at
`0x801EEC00`, and the steal roll is inside that overlay:

| Ability | Engine id (`C+0x11A`) | Overlay | Registry id | `andi` word (guest) | `slt` word (guest) | File offset of `andi` | LBA |
|---|---|---|---|---|---|---|---|
| Pilfer ぶんどり | `0x41` | `BIN/BMAGIC/MAGIC065.EMI` (file id `0x151`) | `0x169` | `0x801EEF20` | `0x801EEF24` | `0xB20` | 15210 |
| Steal 盗む | `0xD8` | `BIN/BMAGIC/MAGIC216.EMI` (file id `0x1A8`) | `0x1B7` | `0x801EEDD4` | `0x801EEDD8` | `0x9D4` | 19376 |

Both overlays are single-section (data at file `+0x800`, dest `0x801EEC00`),
so guest address = `0x801EEC00 + file_offset − 0x800`. Both hold the same
routine; the Pilfer copy, read off the resident band (`read_ram
0x801EEC00..0x801F2C00` after the cast, `tools/disasm_exe.py --header 0`):

```
801EEE74  lhu  v1, 0x80145F24(a0)     ; party working record C+0x98 = AGI (a0 = actor*0x140)
801EEE80  lhu  v0, 0x801EB648(a1)     ; enemy record +0x28 = AGI      (a1 = (target-3)*0x118)
801EEE88  subu s0, v1, v0             ; agility difference
801EEE8C..EEF0  nine slti/branch steps -> a0 = steal mod 12/11/10/9/8/7/6/5/4
801EEEFC  lbu  s0, 0x801EB63A(a1)     ; enemy record +0x1A = drop-1 chance class = steal level
801EEF08  lb   v0, 0x801EF4FC(s0)     ; overlay table [0,1,3,6,12,16,32,32] = steal rate
801EEF10  mult v0, a0 ; mflo s0       ; threshold = rate * mod
801EEF18  jal  Rand (0x8017ED4C)      ; BIOS rand() via the A0 stub
801EEF20  andi v0, v0, 0xFF           ; random byte            <-- the mod patches this
801EEF24  slt  v0, v0, s0             ; byte < threshold ?
801EEF28  beq  v0, zr, fail
801EEF5C  lhu  s0, 0x801EB638(target) ; enemy record +0x18 = drop-1 item (category<<8|id)
801EEF64  beq  s0, zr, nothing        ; message 0x3A "nothing to steal"
801EEF74  jal  Inventory_Add(cat, id, 1, 0)   ; ra 0x801EEF7C
801EEF7C  beq  v0, zr, full           ; message 0x39
801EEF90  sb   0x38 -> ctx+0x0A       ; message "ぶんどった!"
801EEFA0  sh   s0 -> ctx+0x2C         ; the item, for the banner
801EEFD0  sb   0 -> enemy +0x1A       ; steal level cleared
801EF000  sh   0 -> enemy +0x18       ; item cleared: cannot be stolen or dropped again
```

Steal mod by agility difference (attacker − target): `≥49 → 12`, `≥29 → 11`,
`≥19 → 10`, `≥9 → 9`, `≥−10 → 8`, `≥−20 → 7`, `≥−30 → 6`, `≥−50 → 5`, else 4.
Success = `mod × rate / 256`. This is exactly the table on the community wiki
(bof.fandom.com/wiki/Steal_Rate, read 2026-09-13), which also confirms the
stolen item is the drop-1 slot and that Charm raises the level byte.

The anchor's enemy (サンダークライ, enemy 0 of `slot03`): drop 1 = `0x0012`
サンダークラッカ (Taser), class 2 → rate 3; enemy AGI 9. At Rei's agility the
mod is 8–12, so the chance is 24–36/256 ≈ 9–14 % per attempt, which is why
the stock harness saw 0 steals in 22 replays and the user saw one in the
first capture.

## How it was found (and the false lead)

1. `tools/steal_hunt.py` (new): replays the round from the anchor with a
   write trace on the loot list and the inventory arrays. The first replay
   stole; the only inventory write was `Inventory_Add` from
   `ra = 0x801EEF7C` — a BMAGIC-band return address.
2. **False lead:** the game-mode overlay function `0x801E42C0` (BATTLE.EMI#3)
   also rolls `Rand() % 100 < 70` behind enemy-flag gates (`+0x80 & 2`,
   `+0x100 & 0x8000`) and its caller `0x801E40B4` sets round flag
   `0x801462E4 |= 0x40` on success. It ran once per Pilfer at f+166, but a
   Rand-only function filter (`--lo 0x8017ED4C --hi 0x8017ED50`) showed it
   never reaches its `Rand` call on this enemy. It is not the steal roll;
   what it is remains open.
3. The Rand-only capture listed every RNG call with its return address: the
   damage rolls at f+151 (`0x801DC9F8`, `0x801DCC38`, `0x801DCD74`) and one
   at f+91 from `0x801EEF20` — the overlay. Reading the resident band gave
   the routine above, and the disc file's bytes at the same offsets match.
4. The stolen item goes straight to the inventory at the roll, not through
   the battle loot list; the results screen never sees it.

**Naming trap surfaced here:** `names/abilities.toml` / `names/magic.toml`
label record `0x41` as つなみ (Tsunami) and `0x40` as ぶんどり, but the engine's
`C+0x11A = 0x41` for Rei's Pilfer loads MAGIC065.EMI, whose code is the
steal routine, and the effect-table entry for `0x41` (`0x800B1438[0x41] = 31
→ 0x8009BA44`) is the half-damage handler Pilfer needs. The tables' *names*
are shifted by one record against the engine's ids (the name[8] field
belongs to the previous record, or the extractor pairs it wrongly);
`tools/text_tables.py` needs a look before those names are trusted for ids.
The per-id *rows* (file ids, overlay ids) are right.
**Direction confirmed by ear 2026-09-17 ([`SOUND_CUES.md`](SOUND_CUES.md)):** the
name of engine id N is abilities row N-1 — `MAGIC070` played the spell the
player knows as リリフ (row 69, Heal) and `MAGIC069` the targeting skill
めいれい (row 68, Influence). `tools/audio_banks.py` applies the shift when
it names a spell's samples; `text_tables.py` still does not.

## The mod

`mods/preloaded/packages/bof3.steal-always/1.0.0/manifest.toml` — format 6,
one default-off feature `steal-always`, two guarded `disc_user` patches:

| Overlay | `disc_user` offset (`LBA·2048 + file offset`) | expected | replace |
|---|---|---|---|
| MAGIC065.EMI | 31152928 | `ff 00 42 30` (`andi v0,v0,0xFF`) | `00 00 42 30` (`andi v0,v0,0`) |
| MAGIC216.EMI | 39684564 | same | same |

Forcing the random byte to 0 makes `0 < rate × mod` pass whenever the
enemy's steal chance was nonzero. Enemies at steal level 0 stay unstealable,
an enemy with no item still says "nothing to steal", and because the game
clears the item on success, the *first* attempt takes it and later attempts
report nothing — no farming. The alternative (`slt` → `addiu v0,zr,1`) would
also open level-0 enemies; not chosen.

Why declarative rather than the plugin route first discussed: the roll lives
in a 2.3 KB per-ability overlay, so the CRC miss the patch causes (the
runtime's static-match check, `overlay_loader.c`) drops only that overlay to
the interpreter while it is resident during a cast — no measurable cost —
and no regenerate, no C, no hook PC in `game.toml`. A `[[plugin]]` hook would
have needed `Rand`'s entry PC added to `mod_function_entry_funcs` (a
regenerate) to reach the same bytes from data.

Wiring: `CMakeLists.txt` now passes `PRELOADED_MODS_DIR mods/preloaded`, so a
build stages the package to `<exe-dir>/mods/bundled/bof3.steal-always/`
(before that build, it was copied there by hand for the proof). The launcher's
Mods manager toggles the feature; `mods/state.toml` in `build-relprof` has it
**enabled** as of 2026-09-13.

## Proof

```
python tools/scene.py run --slot 3 --port 4390 -- \
    python tools/steal_hunt.py --slot 3 --port {port} --attempts 6 \
        --window-frames 400 --no-stop --settle-step 11 --out-dir analysis/callstacks/steal_mod
```

Runtime log: `applied mod plan 85268367…` and no expected-byte guard
rejection. Result: `steals: 6 / 6` (settle 30..85), each with the single
`Inventory_Add` write `0x8014525F 2 → 3` from `ra 0x801EEF7C`. Stock build,
same replays (`scratchpad steal_rate_probe`, write trace on the round flag
and the Taser count): 0 / 22.

## Harness notes

- `tools/steal_hunt.py --slot N [--no-stop] [--lo/--hi] [--watch]`: one
  `callstack_diff.py capture` per attempt, success = a watched cell changed
  or a changing traced write; keeps `steal_ok.json` / `steal_fail.json`.
  Vary the settle delay (`--settle-step`) or the RNG replays the same round.
- A Rand-only function filter (`--lo 0x8017ED4C --hi 0x8017ED50`) is the
  cheap way to attribute every roll in a round: ~200 entries, each with the
  caller's `ra`.
- Polling RAM over TCP misses one-tick flags; use the write trace.
- `tools/disasm_exe.py` defaults to a `0x800` header; pass `--header 0` for
  a captured section (`analysis/ghidra/bin/*`) or a RAM dump.
