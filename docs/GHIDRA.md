# Ghidra — headless exports of the boot EXE and the battle overlays

**Status:** IN PROGRESS (opened 2026-09-04). Every number below was
produced by `tools/ghidra_run.py` on that date against the pins in
[`HANDOFF.md`](HANDOFF.md); re-run `report` rather than trusting a number
here.

Ghidra is the **second route** the name map needs
([`NAME_MAP.md`](NAME_MAP.md)): a trace says *when* a function runs, the
decompiled body says *what* it does. Two routes that agree promote a
`hypothesis` to `evidence`. This file is how the Ghidra side is driven
without the GUI, what has been imported, and what the first reads found.

## Setup (this machine)

| What | Where |
|---|---|
| Ghidra 12.1.3 + GhidraMCP extension | `D:\Utilities\ghidra_12.1.3_PUBLIC` |
| Project | `D:\Utilities\GhidraProjects\BoF3` (flat layout: `BoF3.gpr` in that directory) |
| Boot EXE program | `SLPS_009.90`, Raw Binary at `0x80093000`, 1025 functions ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)) |
| PyGhidra | 3.1.0 in the Anaconda `python` |

**Headless is the driver, not the GUI.** `pyghidra.start()` in-process dies
with `RecursionError` in the launcher's `find_spec` on this machine, and
`analyzeHeadless.bat` cannot run `.py` scripts; what works is

```
python -m pyghidra.ghidra_launch --install-dir <ghidra> ghidra.app.util.headless.AnalyzeHeadless <projdir> BoF3 ...
```

which `tools/ghidra_run.py` composes. **The GUI holds the project lock**:
close it before running the driver (it refuses while `BoF3.lock` exists),
or use the ghidra-mcp bridge while the GUI is open — the bridge only
discovers a running GUI instance.

## Tools

```bash
python tools/ghidra_run.py list
python tools/ghidra_run.py import --source BATTLE.EMI --load-addr 0x801D0C00     # one section -> one program
python tools/ghidra_run.py import --source PLP034 --source MAGIC069 --all
python tools/ghidra_run.py export [--program NAME] [--decompile all|named|0x..,0x..]
python tools/ghidra_run.py report BATTLE_EMI3_801D0C00 [--calls-to 0x8015034C]
python tools/ghidra_run.py merge [--apply] [--symbols]
```

| Piece | Does |
|---|---|
| `tools/ghidra_run.py` | driver: lock check, headless command lines, program naming `<FILE>_EMI<idx>_<LOADADDR>`, `report`, `merge` |
| `tools/ghidra/seed_overlay.py` | `-preScript` on import: disassemble + `createFunction` at every `static_discovery_entry_pcs`; `dispatch_entry_pcs` become functions only behind an `addiu sp,sp,-N` prologue, else `ov_entry_XXXXXXXX` labels (a function created at a jump-table interior splits its owner) |
| `tools/ghidra/export_program.py` | `-postScript`: per function entry/size/name/source/prototype, insn/load/store counts, **cop2 flag** (GTE = drawing), callees, `jalr` count, computed-jump targets, external refs; program-wide `globals` (r/w counts + functions), `ext_targets`, `jump_tables`, `call_sites` with a constant `a0`; optional decompile to `_decomp/<addr>_<name>.c` |
| `tools/ghidra/list_programs.py` | project listing (headless needs a program to `-process`, so it runs against the boot EXE read-only) |

Outputs go to `analysis/ghidra/` (gitignored — decompiled text is derived
from the disc): `<program>.json`, `<program>.meta.json` (the overlay md5
that joins the program back to `names/overlays.toml`), `<program>.seed.json`,
`<program>_decomp/`. `merge` is the step that writes committable names
(`names/functions.toml` as `hypothesis`, and with `--symbols` the boot-EXE
names into `symbols.toml`, `emit = false`).

`tools/callstack_diff.py` reads the exports too: `known_starts()` unions
Ghidra's function entries into the starts it nests the call forest by.

## Programs in the project (2026-09-05)

| Program | Section | Base | Functions | Notes |
|---|---|---|---|---|
| `SLPS_009.90` | boot EXE | `0x80093000` | 1025 (56 human/BIOS names) | 52 cop2 functions, 77 jump tables, 1676 in-program globals |
| `BATTLE_EMI3_801D0C00` | `BIN/BATTLE/BATTLE.EMI#3`, md5 `8a80230e…` | `0x801D0C00` | 495 | game-mode overlay; 0 cop2; 50 with `jalr`; 431 globals |
| `BATTLE_EMI15_80093800` | `BIN/BATTLE/BATTLE.EMI#15`, md5 `4065db04…` | `0x80093800` | 347 | battle engine; 0 cop2; 24 with `jalr` |
| `BATL_END_EMI0_801EEC00` | `BIN/BATTLE/BATL_END.EMI#0` | `0x801EEC00` | 94 | results screen (zenny/EXP tally callers) |
| `GAME_EMI0_80196800` | `BIN/ETC/GAME.EMI#0` (227 KB) | `0x80196800` | 582 | resident field/system module: `Char_LevelUp`, `Battle_InitPartyContexts`, the level table at `0x801CC068` |
| `SHOP_EMI0_801D0C00` | `BIN/ETC/SHOP.EMI#0` | `0x801D0C00` | 438 | shop / inn / save UI: `Save_BuildImage` |
| `SHOP_EMI8_801EEC00` | `BIN/ETC/SHOP.EMI#8` (5 KB, also in START.EMI) | `0x801EEC00` | 87 | memory-card manager: `Card_*` |
| `START_EMI8_801D0C00` | `BIN/ETC/START.EMI#8` | `0x801D0C00` | 623 | field main menu: `Menu_EquipConfirm` |

Imports now seed every traced entry PC (`analysis/callstacks/*.json`) and
create functions in descending address order (2026-09-05); the BATTLE
game-mode program grew 302 -> 495 functions from that alone.

Not imported yet: PLCHAR (`PLP034`), BOSS (`BOSS001`), BMAGIC (`MAGIC069`),
`STATUS.EMI`, `FIRST.EMI`. One `import` line each.

## First reads

**Boot EXE → overlay slots.** The boot EXE calls exactly one address in the
game-mode swap slot, `0x801D0C04`, from `0x8014EB20` — that is the
game-mode dispatcher — and one in the WORLD band, `0x801F2C04`, from
`0x801532A0`; eleven targets in the field band from `0x8015B1D8`,
`0x8015D508`/`0x8015D5F0`, `0x80167DA0`/`0x80168178`, `0x8014D5D0`. So every
game-mode overlay has its entry at `base + 4`.

**The battle context lives in scratchpad.** `0x1F800044` is read by 105 of
the 302 game-mode functions (321 references) and 48 engine functions: it
holds a pointer to the current battle/actor context. Bytes `+2`, `+3`,
`+5`, `+8` are state selectors; `+0x34`/`+0x38` are positions;
`+0x5D..+0x5F` colour bytes. This is the first data anchor for
`callstack_diff.py capture --watch`.

**State machines, not procedures.** The three traced battle roots are
table dispatchers:

| Name | Body |
|---|---|
| `Battle_FrameTask` `0x801E8FAC` | `(*table[*(u8*)(0x80148644+2)])()` over eight thunks at `0x801D0F80..0x801D0F9C` — the game-mode state machine (those thunks sit in the `0x801D0C00..0x801D112C` header region Ghidra did not disassemble; see Traps) |
| `Defend_Action` `0x801E0400` | `(*PTR_801EB154[*(u8*)(ctx+3)])()` on the scratchpad context — the defend logic is in the table's targets |
| `ov_entry_801DF3AC` (encloses the traced `Attack_Action` `0x801DFA04`) | `(*PTR_801EB0C8[*(u8*)(ctx+2)])()` then per-actor position/colour updates on `ctx`, reading the party record at `*(0x8014624C)` (`+0x79`, `+0x80`, `+0x124`, `+0x128` flags) |

**`BattleMenu_TargetCursor(x, y)`** is confirmed by body: it draws the
cursor box with the theme colour from `0x8002BA08[DAT_8014494E<<6 | 0x20]`
through the rect/line draws `0x801D9C50`/`0x801D9A84`/`0x801DA578`/`0x801DA484`.
Promoted to `evidence` with args.

**Four of the twelve traced "functions" are not Ghidra functions.**
`0x801D10DC`, `0x801D2198`, `0x801DFA04`, `0x801E00EC` are interior entry
stamps (CPS continuations the recompiler treats as roots); the enclosing
Ghidra functions are `0x801D1E84`, `0x801DF3AC`, `0x801DFB90`. Their names
are still right as *labels on code regions*, but the unit to decompile and
to name is the enclosing function.

**One traced function was in the wrong overlay.** `0x801EF188`
(`Examine_EnemyMove_Begin`) lies past the game-mode section's end
(`0x801ED93F`), in the `0x801EEC00` BMAGIC band, whose resident at capture
was `MAGIC069`. Row corrected to md5 `c39f0a09…`.

**Cross-band edges the static map lacked.** The engine calls
`Battle_ActorFrameUpdate` `0x801DB4EC` from 24 functions (37 sites) and
`0x801DE074`/`0x801DC00C`/`0x801DB594`/`0x801E584C` in the game-mode overlay;
the game-mode overlay calls 29 engine entries (`0x800A0680` most). Both call
the boot EXE's `0x8014E494` (36 constant-`a0` sites in the game-mode
overlay), `0x8017ED4C`, `0x8017AF98`, `0x8017CC50`, `0x801503F8`, `0x8015E908`
(69 calls from the engine). Those six boot functions are the next Psy-Q /
signature targets.

**Rules vs draw.** Neither battle overlay touches the GTE (0 cop2
functions in each); the 52 GTE functions are all in the boot EXE. The
battle overlays are logic and 2D UI; 3D goes through boot-EXE helpers.

## Traps

- **`0x801D0C00..0x801D112C` is undisassembled.** A pcode error at
  `0x801D0C64` ("does not contain referenced instruction `0x801D0C68`")
  stopped the flow; no static root lies below `0x801D112C`, so Ghidra has no
  function there — yet `Battle_FrameTask` dispatches into `0x801D0F80+` and
  the boot EXE enters at `0x801D0C04`. It is the mode header + state thunks.
  Seed those addresses (from the `Battle_FrameTask` table and `0x801D0C04`)
  on the next import.
- **The boot-EXE program spans the overlay bands** (`0x80093000..0x801F6FFF`),
  so its calls into overlays are in-program callees, not `ext_targets`;
  `report` splits them by band separately.
- **`getImageBase()` is 0** for these Raw Binary imports; the block start is
  the base. Nothing depends on it.
- **`ov_entry_` names.** Analysis turns some labelled interior PCs into
  functions, which then carry the label as a name. `export` and `merge`
  treat those as unnamed.
- **Traced entries include CPS continuations.** Since `import` seeds every
  PC the fn-entry ring stamped (the game-mode overlay went 302 → 495
  functions), some Ghidra "functions" are fragments of a larger loop —
  the decompiler shows it as `in_v0` / `unaff_s0` parameters
  (`BATL_END` `0x801EF810` / `0x801EF840` around `Zenny_Add`). Read the
  enclosing code, not the fragment, and do not name fragments.
- **A store PC in a gap** (no function on either side reaches it) marks
  code neither the static walk nor a trace found — seed it with
  `import --start ADDR` (`BattleResult_AddExp` `0x801DD564`).

**Data anchors, same evening.** The `ramdiff` → `capture --watch` →
decompile loop ran once on enemy HP and produced the enemy / party / HUD
record layouts, `Battle_ApplyDamage`, `Battle_CalcDamage` with its
variance table and `Rand`, and the game-mode overlay's 24-pointer entry
vector at `0x801D0C04`. All of it is in [`BATTLE_RAM.md`](BATTLE_RAM.md).

## Next

1. ~~`capture --watch` on party/enemy HP; the writer under Attack is the
   damage-apply function.~~ **Done for enemy HP** (BATTLE_RAM.md). Party HP
   (`0x80145F14 + m*0x140` predicted) and the Defend-flag variance reading
   still want one round each.
2. Import `PLP034`, `MAGIC069`, `BOSS001`, `STATUS`; read one actor entry
   vector to get the schema for all occupants.
3. Seed the `0x801D0C00` header region; re-export; `merge --apply`.
4. Psy-Q signatures on the boot EXE, then `merge --symbols`.
