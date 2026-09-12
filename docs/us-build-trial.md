# Rebuilding the US release with the current tooling

**Status:** STABLE (measured 2026-09-12). One question, answered end to end:
does `BreathOfFire3EnglishRecomp` (SLUS-00422) come up on the framework this
project is pinned to, and can one pipeline serve both discs?

**Answer: the pipeline is shared, the address-keyed knowledge is not.** The US
disc generated, built and booted on the first attempt with no game-specific
work. Nothing learned about the JP boot EXE transfers.

## What was run

`BreathOfFire3EnglishRecomp` was scaffolded (probe only, one commit) against
`psxrecomp` `47bda817` (v0.3.2-alpha-78) — 198 commits behind this project's pin.
Both submodules were moved to this project's pins locally, nothing committed:

| Submodule | Was | Now |
|---|---|---|
| `psxrecomp` | `47bda817` (alpha-78) | `baca0a8a` (alpha-276) |
| `recomp-ui` | `d5822a0e` master | `26756c20` `feat/additional-ui-functionality` |

The `recomp-ui` bump is not optional. On the old pin the runtime does not
compile: `main.cpp` wants `RecompLauncherCNetplayChatMessage`,
`RecompLauncherCNetplayOnlinePlayer` and three `RecompLauncherCNetplayLobby`
fields that pin does not have. This is a framework pin skew, not a regional
problem — the two submodules must move together.

Then the standard three stages, unmodified:

```bash
python -u psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . \
  --disc "../BreathOfFire3Recomp/isos/Breath of Fire III (USA).cue"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

## Result — the US disc is as clean as the JP one

Generate emitted completely clean under `strict = true`: no skipped functions,
no unsupported instructions. The two discs are the same program built twice, and
the recompiler sees them that way.

| | JP `SLPS_009.90` | US `SLUS_004.22` |
|---|---:|---:|
| functions emitted | 1468 | **1480** |
| generated C lines | 2,523,685 | **2,533,593** |
| shards | 35 | **35** |
| dispatch entries | 1467 | **1479** |
| skipped / unsupported | 0 / 0 | **0 / 0** |
| first-pass seeds | 523 | 526 |

The eleven "out-of-function branch, emitting fallthrough" notes are the same
class of adjacent-fallthrough warning the JP side produces, at US addresses.

`psx-runtime` linked to a 24 MB exe and ran headless against the USA disc until
it was stopped by hand: 50,950 frames, 50,595 vblanks delivered, zero bails, no
freeze, `last_store_pc` parked in game code at `0x8017487C`. That is a live
render loop, the same shape as JP Boot 001. Nothing beyond "it runs" was probed
— no screenshot, no title-screen confirmation.

**Caveat: this is the boot EXE only.** No overlays were extracted or compiled,
so every `.EMI` overlay runs interpreted, exactly as this project did before
Layer B. The US build is at our 2026-08-29 state, not our current one.

## Nothing address-keyed transfers

[`regional-builds.md`](regional-builds.md) established that the US EXE is not
address-compatible with JP. Measured again directly, boot EXE against boot EXE:

| Comparison | Result |
|---|---:|
| words identical at the same RAM address (nonzero) | **1.4%** |
| words identical at `+0x3000` file-offset alignment | 0.1% |
| words sharing only the opcode field | 20.7% |
| first-pass seeds in common | 24 / 523 = **4.6%** |
| emitted function entry addresses in common | 264 / 1468 = 18.0% |

The 18% entry-address overlap is coincidence, not identity. Of this project's
537 hand-derived `symbols.toml` entries, **21 land on a US function entry**, and
those 21 are the PSY-Q and BIOS-thunk tail that sits at the same address because
the image is anchored at its end (`InitGeom`, `SetPolyFT4`, `strlen`, `printf`,
`SsVabOpenHead`), plus `BootEntry`. Spot-checking the bytes:

| Address | JP | US | first 8 words identical |
|---|---|---|---:|
| `0x8015042C` | `MsgBox_Reset` | different function | 0 / 8 |
| `0x80150F3C` | `MsgBox_DelayState` | different function | 0 / 8 |
| `0x80178FD8` | `InitGeom` | different code | 0 / 8 |
| `0x8017ED2C` | `strlen` thunk | a thunk, different `A0` index | 4 / 8 |

Even the library thunks differ: JP dispatches `A0:0x1B` where US dispatches
`A0:0x07` at the same address. **Treat a matching address as a collision until
the bytes agree.** Both localization hook PCs are in that trap.

## So: one pipeline or two?

One pipeline, two instantiations. The split runs along a clean seam.

**Shared — no work per region:**

- the whole `psxrecomp` framework and the three-stage generate/configure/build
- the project `CMakeLists.txt`. Diffing the two: project name, `GEN_MARKER`,
  `GEN_FULL_GLOB`, window title, and this project's extra
  `GAME_OVERLAY_STATIC_C` and `PSX_SPLIT_DEBUG` blocks. Nothing structural.
- `game.toml`'s shape; the probe autofills the region-specific half
- the disc and `.EMI` readers. `emi_survey.py` and `extract_overlays.py` carry
  no region constants and would run on the US disc as they stand
- everything in `BreathOfFire3Translations`. It already reads all four discs;
  `corpus/us/` holds 14,458 messages extracted with the same code path as JP

**Per region — redone, not ported:**

- `seeds/ghidra_funcs.txt` (auto-scanned, so free) and `symbols.toml` (537
  entries of hand decomp, so not)
- overlay extraction and static compilation, re-run against the US disc
- the localization apply path. `src/bof3_localize.c` is built from five JP RAM
  addresses — `MSGBOX_RESET_PC`, `MSGBOX_DELAY_PC`, `MSG_STR_BASE`,
  `MSG_STR_CUR`, `INSERT_RECORD_BASE` — and every one must be re-derived. Of
  the two message pools, `0x80010000` does not move in any release, but the
  system pool at JP `0x80014000` is at `0x8001A000` on US
- 13 of this project's 54 `tools/*.py` carry a JP address or the JP serial:
  `area_pcs`, `disasm_exe`, `file_ids`, `ghidra_run`, `ghidra_seed`,
  `harvest_interp_pcs`, `loader_records`, `magic_map`, `page_rows`,
  `pc_coverage`, `psyq_sigs`, `subsystem_map`, `world_items`. They are
  parameterizable — the constants sit in tables, not in the logic

The cost of a second region is therefore a Ghidra pass and a re-run of the
overlay stages, on a framework and a toolchain that already work. It is not a
second pipeline.

## What the trial changed on disk

In `BreathOfFire3EnglishRecomp`, all uncommitted: the two submodule pointers
above, a `jp` remote on each pointing at this checkout, `generated/` (64 MB) and
`build-release/` (55 MB), both gitignored, and `build-release/disc.cfg` pointing
at the USA dump. `git checkout psxrecomp recomp-ui` reverts the repo.
