# EXP / Zenny Boost — the second gameplay mod, and the first trusted plugin

**Status:** BUILT + PROVEN 2026-09-13 (headless replay of the user's
one-attack-left anchor: the kill's 84 EXP / 6 zenny became 840 / 60, Teepo's
record gained exactly the scaled total, the wallet exactly 60, the counter
took the same number of ticks as stock — see *Proof*). Package
`mods/preloaded/packages/bof3.exp-boost/`, plugin
[`src/bof3_exp_boost.c`](../src/bof3_exp_boost.c), one overlay hook PC in
`game.toml`.

## Why a plugin, not a byte patch

Every place EXP and zenny move is overlay code: the kill adds the enemy's
yield to the battle totals in BATTLE.EMI#3 (`Battle_EnemyDefeated`,
`0x80146328 += rec+0x06`, `0x8014632C += rec+0x04`), the results screen
overlay BATL_END ticks the totals into the party (`BattleResult_Setup` →
`ExpTick` → `ZennyTick` → `AwardDrops`, [`BATTLE_RAM.md`](BATTLE_RAM.md)),
and `Char_LevelUp` in GAME.EMI resolves levels. A multiplier is three MIPS
words with no free immediate, and a code patch in BATTLE.EMI#3 would drop the
whole game-mode battle band to the interpreter (the static-match CRC covers
the overlay's code ranges, `overlay_loader.c`). So: data-only, from a hook.

## The hook

The recompiler emits `psx_mod_function_entry()` at the entry of every
function listed in `mod_function_entry_funcs`, overlay functions included
(`code_generator.cpp:2783` tests each function's start address; the overlay
compile hashes the list into its cache tag, so a change means a
`compile_overlays.py` run, not a main-EXE generate).

**First attempt (failed, kept as the trap):** the three BATL_END phases
`BattleResult_Setup 0x801EF390` / `ExpTick 0x801EEF58` / `ZennyTick
0x801EF810`. The compile classifies them `DISPATCH_INTERIOR`: the phase
table jumps into the middle of larger host functions, and the generated
unit gives them only an *alias entry* (`func_801EF390` → `alias_body_801EF34C(cpu,
0x801EF390)`), which bypasses the prologue where the hook is emitted. The
units for BATL_END came out byte-identical, the plugin logged its
activation and never its hook, and the totals stayed stock. Rule: **hook
only plain `jal` targets** — check the generated unit for a real body
(`void ov_..._func_<pc>(CPUState* cpu)` followed by the block-cycle guard,
not `alias_body_`), and check `mtime` of that unit after the compile.

**What works:** one BATTLE.EMI#3 function (band `0x801D0C00`, registry id
`0x10`), a plain `jal` target:

| PC | Function | Hook does |
|---|---|---|
| `0x801E542C` | `Battle_EnemyDefeated()` | scales the dying enemy's yields in its record before the body adds them to the battle totals: `obj+0x86` EXP `*= E`, `obj+0x84` zenny `*= Z` (u16, clamped). The body finds the enemy through the **current-object pointer `0x801EB458`**, not `a0` — the first build read `a0` (garbage at entry) and bailed |

Scaling at the kill means the on-screen totals, the per-member split
(`BattleResult_AddExp`) and multi-level gains (`Char_LevelUp` walks the
table until the EXP is spent) all follow. The results screen derives each
phase's tick step from that phase's own total (the EXP phase ticked 31 times
for 864 as it had 28 times for 108; the "`max(1, zenny/30)`" in
`BattleResult_Setup` is the zenny phase's step), so the counters take the
same time at any multiplier and no step adjustment is needed — the
`BattleResult_AddExp 0x801DD564` hook PC still in `game.toml` is from a
revision that adjusted it; nothing registers on it, drop it at the next
overlay recompile. The writers cap: `Zenny_Add` at 9,999,999 and the EXP
record likewise. A kill made *before* the feature was enabled (a savestate
mid-battle) is not scaled: its yield is already in the total.

Two things the runtime does that shaped the code:

- **Function-entry callbacks fire whether or not the feature is enabled**
  (`psx_mod_function_entry` dispatches by address only). Activation
  callbacks run only for enabled features. So the multipliers start at 1 and
  the activation callback reads the slider (`psx_mod_option_value`, decimal
  text) — with nothing enabled the hooks return at the first test.
- **The 0x801D0C00 band is shared** (BATTLE / SHOP / STATUS / START). Each
  hook checks the resident registry id at `0x801D0C00` is BATTLE.EMI#3's
  `0x10` before touching anything.

## The package

One default-off feature `boost` with two bounded integer options (`exp`
and `zenny`, 0..50, default 10) and one `[[plugin]]` (`bof3.exp-boost`).
Enabling it shows both sliders on one Mods-manager page; 10x is one
position, 1 leaves that stat stock, and **0 grants nothing** — the kill
adds zero, so the level-reached check never fires (a no-level-up run) and
zero zenny is awarded. **User-verified in play 2026-09-13:** with EXP at 0 and
zenny at 10 a won battle showed 0 EXP, no level-up, and positive zenny. (It started as two features with a
slider each; the user asked for one entry, 2026-09-13.) The build stages the package through
`PRELOADED_MODS_DIR` (CMakeLists), and the plugin source is always compiled
into the runtime — it is inert until activated.

## Build

```bash
export PATH="/c/msys64/mingw64/bin:$PATH"
/c/Users/kerok/anaconda3/python.exe psxrecomp/tools/compile_overlays.py --static --force \
    --captures analysis/overlay_captures_all.json --game-toml game.toml \
    --recompiler build-recompiler/psxrecomp-game.exe \
    --runtime-include psxrecomp/runtime/include --out-dir generated \
    --gcc C:/msys64/mingw64/bin/gcc.exe --cps        # ~13 min, game may stay open
rm -f build-relprof/CMakeFiles/psx-runtime.dir/generated/overlays_static_*.obj   # HANDOFF trap
cmake --build build-relprof --target psx-runtime      # needs the game closed (link)
```

Check the hook landed in the BATTLE.EMI#3 unit (crc `BD466258`):
`grep -n "psx_mod_function_entry(cpu, 0x801E542Cu)" generated/overlays_static_*.c`
— and that the unit's mtime moved; the compile leaves byte-identical units
untouched, which is how the alias-entry attempt hid.

## Proof

Anchor: the user's `slot03` of 2026-09-13 21:30 — a battle one attack from
over, Ryu and Rei down, two of three enemies already dead (their 24 EXP
already in the total), the last enemy worth 84 EXP / 6 zenny. Feature `boost` with
`exp = 10`, `zenny = 10` in `build-relprof/mods/state.toml`. Circle every 20 frames carries the
round and the results screen:

```
python tools/scene.py run --slot 3 --port 4390 --log exp10.log --     python tools/callstack_diff.py capture --label exp10 --port {port} --slot 3         --press circle (x70) --press-gap 20 --window-frames 1500         --lo 0x801E542C --hi 0x801E5430         --watch 0x80146328-0x80146330 --watch 0x80144B58-0x80144B5C         --watch 0x80144F4C-0x80144F50 --out analysis/callstacks/exp10.json
```

| | stock (same anchor, first build's inert hook) | boosted x10 |
|---|---|---|
| kill write to the EXP total | 24 → 108 | 24 → 864 |
| kill write to the zenny total | 0 → 6 | 0 → 60 |
| Teepo's EXP record `0x80144B58` | +108 | 0x108B → 0x13EB = **+864** |
| wallet `0x80144F4C` | +6 | 0x57A → 0x5B6 = **+60** |
| EXP counter ticks | 28 | 31 |
| runtime log | — | `bof3_exp_boost: kill 801EB5A0 EXP 84 -> 840, zenny 6 -> 60` |

The 108 matches the number the user read off the stock results screen.
