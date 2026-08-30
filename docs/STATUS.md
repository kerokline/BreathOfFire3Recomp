# Current state

**Status:** IN PROGRESS (last verified 2026-08-30)

Living status doc — the one place a new session learns where the project
actually stands. Update this rather than `CLAUDE.md`. Durable findings graduate
into their own `docs/` file (see [`README.md`](README.md)); this stays a short
"where we are, what's next".

## Where we are

**The game loads (2026-08-30).** Title screen renders, Start is accepted, and
the opening prologue plays with Japanese text drawing correctly. Evidence and
method in [`BRINGUP.md`](BRINGUP.md) → Boot 002.

**Boot 001's "wait loop" was a misreading and is retracted.** The two pinned
`store_pc` values are `DrawOTag()` and `VSync()` — a healthy render loop. The
CD-ROM hypothesis is dead. What actually hid this: the Release build sets
`PSX_DEBUG_TOOLS=OFF`, which compiles out the TCP debug server, so there was no
way to look at the screen.

Headlines:

- Game still emits **completely clean under `strict = true`** — 2.5M lines, 35
  shards, 0 skipped, 0 unsupported, 1467 dispatch entries.
- `build-dbg/` is the new diagnosis tree (`-DPSX_DEBUG_TOOLS=ON`, 232/232).
  `build-release/` is untouched and stays the shipping config.
- GPU is live: 1,198,959 draw commands, `disabled=0`, double-buffered,
  3D geometry submitting.
- `tools/disasm_exe.py` added — disassembles the staged boot EXE and resolves
  `lui`/`lw` pairs to absolute addresses, naming MMIO. This is what turned the
  "wait loop" into `DrawOTag`/`VSync` instead of another guess.
- English scaffold `BreathOfFire3EnglishRecomp/` generated from the USA dump
  (SLUS-00422, 526 seeds). **The US build is not address-compatible with JP** —
  0x3000 load-base shift, 4.6% seed overlap. See [`LOCALIZATION.md`](LOCALIZATION.md).

## In flight

- `docs/LOCALIZATION.md` — new; the JP→EN assessment and the two upstream bugs
  it turned up (F-3, F-4).
- `tools/disasm_exe.py` — new, uncommitted.
- `BreathOfFire3EnglishRecomp/` — scaffolded but **not** generated or built. Its
  `psxrecomp` gitlink floated to master (`47bda817`) vs this repo's `f24b7e5d`,
  and its `disc =` is an absolute machine-local path. Both need a decision
  before it is built.

## Next up

1. **Soak from the prologue into gameplay.** The game runs; find where it stops
   next and grow `seeds/ghidra_funcs.txt` as overlay paths surface.
2. **Text-draw PC census.** Capture is armed but yields no real strings — BoF3
   does not appear to pass `char*` at dispatch boundaries. Establishing how text
   reaches the renderer gates all translation work. See `LOCALIZATION.md`.
3. **Settle the English repo's submodule pin and disc path**, then generate it
   if a second build is still wanted.

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

None. The game loads and runs.

Open, non-blocking:

- Four upstream framework issues, all documented, none affecting BoF3 booting:
  F-1 / F-2 in [`BRINGUP.md`](BRINGUP.md) (false-positive BIOS staleness
  warning; garbage cross-function targets), F-3 / F-4 in
  [`LOCALIZATION.md`](LOCALIZATION.md) (stale "capture is always-on" docs;
  Shift-JIS validator accepting MIPS instruction words). Fixes belong in
  `mstan/psxrecomp`.
- Release builds cannot be inspected at all (`PSX_DEBUG_TOOLS=OFF`). Expected,
  but worth knowing before diagnosing anything against `build-release/`.
- `gh` not installed; affects GitHub CLI flows only.
- Ghidra / GhidraMCP not installed, so the framework `.mcp.json` entries for
  `localhost:7777` fail to connect. Not required to build, generate, or boot.

## Log

| Date | Entry |
|---|---|
| 2026-08-29 | Repo inventoried; `docs/` and `CLAUDE.md` established. Localization intent recorded. |
| 2026-08-29 | Build toolchain installed (MSYS2 MinGW-w64) and proven by a full 169-target emitter build. Toolchain blocker cleared; README gained a *Development environment* section. |
| 2026-08-29 | Dump moved into gitignored `isos/`; `[game].disc` switched from an absolute machine-local path to repo-relative `isos/Breath of Fire III (Japan).cue`. Portable for any checkout. |
| 2026-08-29 | **First boot.** Emitters built (67/67); generate clean under `strict`; `psx-runtime` linked (232/232); headless boot reaches game code and runs ~26k frames. Logged in [`BRINGUP.md`](BRINGUP.md) with framework bugs F-1 / F-2. |
| 2026-08-30 | **The game loads.** Boot 001's wait-loop diagnosis retracted — the pinned PCs are `DrawOTag`/`VSync`. Root cause of the blindness: `PSX_DEBUG_TOOLS=OFF` in Release. Built `build-dbg/`, added `tools/disasm_exe.py`, captured title screen + prologue over the debug server. [`BRINGUP.md`](BRINGUP.md) → Boot 002. |
| 2026-08-30 | **Savestates verified working** on the LLE backend — save *and* load, round-trip confirmed against the VSync counter at `0x8018603C` (advanced 17,460 -> 20,312, rewound to ~17,828 on load). Files: `saves/openbios/state_8014AA0C_slotNN.pst` + `.thumb`. Driven by `tools/playsession.py state save|load N`. |
| 2026-08-30 | **Script load path measured.** `wtrace` on the text buffer shows the script arriving by CD-ROM DMA (channel 3) kicked from PC `0x80177B78`. `rtrace_*` is MMIO-only so it cannot see the *readers* — finding text-draw PCs is an open tooling gap. [`LOCALIZATION.md`](LOCALIZATION.md) 4.2b. |
| 2026-08-30 | **Localization assessed.** Capture pipeline armed via `PSX_XLATE_CAPTURE=1` (it is *not* always-on, contrary to framework docs — F-3); 39.6M calls scanned, 0 real strings, 3 false positives that decode as MIPS instructions (F-4). English scaffold generated; US build shown **not** address-compatible with JP (0x3000 shift, 4.6% seed overlap). [`LOCALIZATION.md`](LOCALIZATION.md). |
