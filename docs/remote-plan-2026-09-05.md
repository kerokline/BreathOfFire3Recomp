# Remote work plan — morning of 2026-09-05

**Status:** IN PROGRESS (written 2026-09-05 08:10, before the user left; the
machine stays up with build-dbg on port 4370 and this chat drives it)

Six tracks, ordered so that the ones needing nothing from the user run first.
Each track names its inputs, the exact loop, and what "done" writes where.
Results land in [`BATTLE_RAM.md`](BATTLE_RAM.md), `names/functions.toml`, and a
`STATUS.md` Log row per track; this file gets a one-line outcome per track at
the end of the morning and is then marked DONE.

## Starting state

- `psxrecomp` re-pinned to plain upstream `master` `17f49ad3` this morning
  (title commit `de4ee02`); `build-dbg` rebuilt and boot-checked: title screen,
  60 fps past the intro, static dispatch 99.94 % hits, 0 aborts, 0 new
  interpreted entries at boot. `build-relprof` **not** rebuilt yet.
- Ghidra exports already on disk for the boot EXE, GAME.EMI, both BATTLE.EMI
  code sections, BATL_END, SHOP (both), START. The decompile of `0x801D1228`
  (`Battle_Init`) exists; `0x801DCAA0` / `0x801DC704` / `0x801DC85C` do not.
- Savestate anchors (file numbers): `slot10` = battle command menu, cursor on
  Attack (AREA020 field battle); `slot11` = Watch armed, Nu about to stomp;
  `slot01` = mid-battle with effects queued; `slot04`/`slot05` = the herb-effect
  battle with Rei. See [`SAVESTATES.md`](SAVESTATES.md).

## What the user supplies (before leaving, or remotely)

1. **A combat savestate with Rei in the party**, ideally the first command menu
   of the battle, and the **file slot number**. Without it, track C runs on
   `slot10` (Ryu + Teepo only) and the Rei roster check waits.
2. Permission to **rebuild `build-relprof`** (≈3 min) if the Capcom-intro
   perf number in track D is wanted; the interpreted-PC sampling half of track
   D does not need it.
3. Confirmation that "auto attack" means the in-game **Auto** command.

## Track A — `Battle_BaseDamage` and the two defence steps (offline, first)

Inputs: none live. Target 1 in HANDOFF §0.

```bash
python tools/ghidra_run.py export --program BATTLE_EMI3_801D0C00 \
    --decompile 0x801DCAA0,0x801DC704,0x801DC85C
```

Loop: read the three bodies against `Battle_CalcDamage`'s known call sites
(the `mode 0` base call and the `mode 1` re-call under the defend flag), map
every record offset they read to the actor table in BATTLE_RAM (`C+0x74` is
the persistent copy, so persistent offsets apply). The two defence steps are
expected to read the target's DEF-class fields and the row/defend bits; name
them from what they do, not from their position.

Done = the full formula written out in BATTLE_RAM.md "Damage path" with the
ATK/DEF field offsets of **both** record types, the three functions at
`status = "evidence"` in `names/functions.toml`, and a cross-check: recompute
one damage number already logged in a `ramfilter` round from the fields alone.

Risk: the decompile may bottom out in a `jalr` through the BMAGIC ABI or a
table in GAME.EMI data. If so, record the table address and stop at
`hypothesis` rather than guess.

## Track B — `Battle_Init` `0x801D1228` to evidence (offline)

Inputs: the existing decompile
`analysis/ghidra/BATTLE_EMI3_801D0C00_decomp/801D1228_FUN_801d1228.c` and the
`battlebegin.json` watch capture (33 offsets written at +563, once per slot).

Loop: walk the 1428-byte body store by store; match each store to the +563
write set and to the actor-table offsets (`C+0x80` status flags, `C+0x90..`
effective stats). The four engine/boot callees (`0x800A79AC`, `0x800A8AD4`,
`0x8014E294`, `0x801629CC`) get looked up in the BATTLE_EMI15 and boot
exports and named if their bodies are unambiguous.

Done = every field the trace saw is explained by a store in the body (or the
gap is listed), `Battle_Init` promoted with the evidence string citing both,
and the "effective stats" block of the actor table filled in.

## Track C — battle command venn + victory (needs the Rei savestate)

Inputs: the user's slot number (fallback `slot10`). One game process at a
time, so this runs after track D's fresh boot.

Five captures from the same state, one per command, via
`tools/callstack_diff.py capture --slot N --press … --hold …`, each with
`--watch` on the enemy record block `0x801EB5A0-0x801EB8D0` and the party
actors `0x80145E8C-0x80146250`:

| label | input (from the command menu, cursor on Attack) |
|---|---|
| attack | `--press circle --press circle` (confirm, first target) |
| defend | `--hold right --press circle` (the menu needs the hold) |
| watch | as the 2026-09-04 Watch capture |
| auto | Auto's position in the menu, taken from a screenshot first |
| run | Run's position, same |

Then `venn` across the five: the functions unique to each command are the
command handlers; the common prefix is the turn engine. `propose --apply`
writes `hypothesis` rows; anything whose body (Ghidra export, same program)
agrees with the trace goes to `evidence` with `name --apply`.

**Victory**: from the same state, `--press circle` repeated with
`--press-gap` sized to one turn, `--window-frames 3000+`, watching the
inventory arrays `0x80145040-0x80145470`, zenny `0x80144F4C`, and the EXP
cells `0x80144A10` / `0x80144AB4` / `0x8014496C` / `0x80144B58`. Done =
the `BATL_END` caller of `Inventory_Add` and `BattleResult_AddExp` named,
the drop-table read PC located, and the Rei roster index proven from which
EXP cell moves (target 6).

Also on the table if the party has a healer: cast a heal spell once and
screenshot the enlarged command icon afterwards — the retest
[`battle-icon-strip-rows.md`](battle-icon-strip-rows.md) is waiting for.

## Track D — Capcom intro: sample the never-sampled stratum

Inputs: a fresh boot (the current title-screen process is killed first; the
session-id logic keys on the frame counter restarting).

The coverage table lists `0x801CE000 Capcom logo intro` as NEVER SAMPLED
under session ids. The runtime is relaunched with `tools/run_dbg.cmd`, and
`harvest_interp_pcs.py --area LOGO` runs **during** the FMV (it is ~20 s
long on build-dbg; start the harvest as soon as the debug server answers).
That stamps the logo band's PCs with a session id and an area, so
`pc_coverage.py` can estimate it. A second boot later in the morning gives
the two-session minimum.

Optional perf half, only with the relprof rebuild: `tools/fmv_bench.py` on
`build-relprof` for the post-pin vblank/present number against the ~30 fps
pacing-limited baseline of 2026-09-01. build-dbg is -O0 and cannot judge this.

Done = the logo row in `pc_coverage.py` shows a session count and an
estimate; any *new* proven entries (expected 0 after the handler harvest of
2026-09-01) are listed in the outcome line.

## Track E — save-file verifier (offline host tool)

Target 9. The format is complete: contiguous `0x10B0` block from RAM
`0x801448D4` at file `+0x200`, u16 byte-sum at `+0x270`, title frame + three
icon frames before it, slot list at `0xE80..0xEFF`.

Write `tools/save_tool.py` over `.mcr` / `.mcd` images: `list` (slots, names,
checksum OK/BAD), `dump SLOT` (characters with the record offsets from
BATTLE_RAM, zenny, inventory by category, key items), `verify` (recompute
the checksum, cross-check the summary block's flag hash). Validate against
`saves/card1.mcd` (three saves) and, as an independent oracle, the same card
read by Mednafen's own save list.

Done = every field the tool prints for the three saves matches what the game
shows on its load screen (screenshot from `slot08`/the memcard screen), and
the checksum verifies on all three. Any mismatch is a bug in the RAM map and
goes back into BATTLE_RAM.md, which is the point of the tool.

## Track F — housekeeping that is ready to go

- **Starvation-watchdog false-trip fix**: the patch is drafted in
  [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md)
  and not filed. Cutting a fork branch off `17f49ad3`, applying it with its
  test, and opening the upstream PR is mechanical. **Not started without a
  go-ahead** — it is a framework change the user may want to review first.
- **`build-relprof` rebuild** against the pin (needed by D's perf half and by
  any play session).
- **HANDOFF "Tooling" table** gains `save_tool.py` when E lands.

## Order of execution

1. A, then B (Ghidra only, no game).
2. D first boot (kills the title-screen process; harvest during the FMV).
3. C on the user's slot, or `slot10` if none arrives.
4. E in the gaps while captures run.
5. D second boot at the end of the morning.
6. F only on explicit go-ahead.

## Outcomes

(filled in as tracks complete)

| Track | Outcome |
|---|---|
| A | |
| B | |
| C | |
| D | |
| E | |
| F | |
