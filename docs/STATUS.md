# Current state

**Status:** IN PROGRESS (last verified 2026-08-29)

Living status doc — the one place a new session learns where the project
actually stands. Update this rather than `CLAUDE.md`. Durable findings graduate
into their own `docs/` file (see [`README.md`](README.md)); this stays a short
"where we are, what's next".

## Where we are

**First boot achieved 2026-08-29.** The full chain — emitters → generate →
`psx-runtime` → headless boot — runs end to end, all stages exit 0. The game
executes its own code on its own stack with a healthy vblank/IRQ path, then
parks in a wait loop without crashing. Details, evidence, and next actions in
[`BRINGUP.md`](BRINGUP.md).

Headlines:

- Game emitted **completely clean under `strict = true`** — 2.5M lines, 35
  shards, 0 skipped functions, 0 unsupported instructions. Dispatch table grew
  523 → **1467** entries via closure discovery.
- Boot reaches game code (`epc = 0x8017E328`, inside game text), runs ~26k
  frames in 90 s, `fatal: null`, no freeze dumps.
- It then spins with `store_pc` pinned to `0x8017DDA0` (`func_8017DD60`) and
  `0x801751F4` (`func_801751C0`), called from `func_8017E0E0`. Cause not yet
  established — CD-ROM wait is the leading, *unevidenced* hypothesis.

Repo contents inventoried in [`INVENTORY.md`](INVENTORY.md).

## In flight

Uncommitted at last inventory:

- `game.toml` — added a `[localization]` block (`language = "en"`, dropdown
  offering `en` + `jp`), enabling the framework's runtime JP→EN string
  translation path. See `psxrecomp/docs/STRING_TRANSLATION.md`.
- `game_options.toml` — untracked, still the all-comment template.

## Next up

1. **Diagnose the boot-001 wait loop.** Read `func_8017E0E0`, `func_8017DD60`,
   `func_801751C0` in `generated/`, find the loop condition and the MMIO it
   polls, then confirm or kill the CD-ROM hypothesis with a device trace rather
   than by inference. See [`BRINGUP.md`](BRINGUP.md) → *Next actions*.
2. **Soak.** Once it gets past the loop, log where it stops next; grow
   `seeds/ghidra_funcs.txt` as overlay/runtime paths surface.
3. **Localization Phase 0.** Capture runs unconditionally, so a soak builds the
   string inventory and text-draw PC census before any translation exists.
   Blocked in practice until the boot progresses past the loop — nothing draws
   text yet.

## Environment

Local build toolchain installed and verified 2026-08-29 — MSYS2 MinGW-w64 at
`C:\msys64`, the layout `psxrecomp/CLAUDE.md` §16 already assumes:

GCC 16.2.0 · Clang 22.1.8 · CMake 4.4.2 · Ninja 1.13.2 · ccache 4.14 ·
SDL3 3.4.14 · SDL2 2.32.10 · Python 3.14.7 (mingw64)

Verified by building the framework emitters end to end — 169/169 targets, with
`psxrecomp-game`, `psxrecomp-bios` and `psxrecomp-analyze` all produced and
executing. Setup steps and the Windows `PATH`/Python caveats live in the repo
[`README.md`](../README.md#development-environment).

## Blockers

First boot is done. The boot-001 wait loop is the one thing standing between us
and a soak — not yet a "blocker" in the sense of being stuck, since it hasn't
been diagnosed yet.

Open, non-blocking:

- Two upstream framework bugs found during first boot (false-positive BIOS
  staleness warning; garbage cross-function targets in OpenBIOS discovery).
  Neither affects BoF3 booting. Documented as F-1 / F-2 in
  [`BRINGUP.md`](BRINGUP.md); fixes belong in `mstan/psxrecomp`, not here.

- `gh` not installed; affects GitHub CLI flows only, not builds.
- Ghidra / GhidraMCP **not installed**, so the framework `.mcp.json` entries for
  `localhost:7777` fail to connect. Not required to build, generate, or boot —
  static discovery is `psxrecomp-analyze`, which exports *into* Ghidra rather
  than depending on it. See README → *Optional: Ghidra*.

## Log

| Date | Entry |
|---|---|
| 2026-08-29 | Repo inventoried; `docs/` and `CLAUDE.md` established. Localization intent recorded. |
| 2026-08-29 | Build toolchain installed (MSYS2 MinGW-w64) and proven by a full 169-target emitter build. Toolchain blocker cleared; README gained a *Development environment* section. |
| 2026-08-29 | Dump moved into gitignored `isos/`; `[game].disc` switched from an absolute machine-local path to repo-relative `isos/Breath of Fire III (Japan).cue`. Portable for any checkout. |
| 2026-08-29 | **First boot.** Emitters built in this repo's submodule (67/67); generate clean under `strict` (0 skipped, 0 unsupported, 1467 dispatch entries); `psx-runtime` linked (232/232) as `BreathOfFire3_Recompiled.exe`; headless boot reaches game code and runs ~26k frames, then parks in a wait loop. Logged in [`BRINGUP.md`](BRINGUP.md), which also records two upstream framework bugs (false-positive BIOS staleness warning; garbage cross-function targets in OpenBIOS discovery). |
