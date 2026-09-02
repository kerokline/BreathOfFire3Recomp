# Breath of Fire III Recompiled

<!-- retcomm-readme-metrics -->
[![GitHub downloads (all assets, all releases)](https://img.shields.io/github/downloads/TechnicallyComputers/BreathOfFire3Recomp/total)](https://github.com/TechnicallyComputers/BreathOfFire3Recomp/releases)
[![GitHub downloads (latest release)](https://img.shields.io/github/downloads/TechnicallyComputers/BreathOfFire3Recomp/latest/total)](https://github.com/TechnicallyComputers/BreathOfFire3Recomp/releases/latest)
[![GitHub release](https://img.shields.io/github/v/release/TechnicallyComputers/BreathOfFire3Recomp)](https://github.com/TechnicallyComputers/BreathOfFire3Recomp/releases/latest)
<!-- /retcomm-readme-metrics -->

![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)
![License: PolyForm NC 1.0.0](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-blue)

<!-- retcomm-readme-boxart -->
<p align="center">
  <img src="launcher_assets/img/boxart.png" alt="BreathOfFire3 box art" width="280">
</p>
<!-- /retcomm-readme-boxart -->

A **static recompilation** of Capcom's 1997 PlayStation RPG *Breath of Fire III*
— Japanese release, SLPS-00990. The game's MIPS R3000A machine code is
translated ahead of time into C, then compiled into a native executable. This is
not an emulator: there is no interpreter in the hot path, and the game's own code
becomes your CPU's code.

Built on [psxrecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/mstan/recomp-ui), both pinned as submodules.

| | |
|---|---|
| Title | Breath of Fire III |
| Serial | SLPS-00990 |
| Region | Japan |
| Publisher | Capcom |
| Year | 1997 |
| Players | 1 |
| Boot EXE | `SLPS_009.90` |

> **This project ships no game content.** You must supply your own legal disc
> dump. See [Legal](#legal).

## Status

**Pre-alpha — playable into the game, not playable through yet.** The game
boots, renders, plays audio, accepts input, and has been played past the
opening prologue and intro boss into the world map, shops and save screens, with
area transitions, name entry, menus, combat and in-game memory-card saves all
working. It has not been played end to end.

Most of the game's code lives in runtime-loaded overlays, and **those overlays
are now statically recompiled** — all ten RAM bands are compiled in and dispatch
natively at ~99% hit rates, extracted deterministically from the disc rather
than captured at runtime (see [`docs/OVERLAYS.md`](docs/OVERLAYS.md)). What
remains is *coverage inside* those bands — interior entry points reached only by
dynamic dispatch, which the static call-graph walk can't see, are fed back from
live play and recompiled (the "Axis B" loop). That, plus per-title enhancement,
is the main remaining engineering work.

What works:

- [x] Full toolchain: emitters → generate → native runtime, all stages clean
- [x] Disc verification against known MD5/SHA-1/size
- [x] **Recompilation is clean under `strict = true`** — 2.5M lines across 35
      shards with **zero skipped functions and zero unsupported instructions**
- [x] Function discovery grows 523 seed targets → **1467** dispatch entries
- [x] Boots into game code with a live stack and a healthy vblank/IRQ path
- [x] **Renders.** Title screen and opening prologue, ~1.2M GPU draw commands,
      double-buffered, 3D geometry submitting
- [x] **Input.** Start advances the title screen; the buffer flip engages
- [x] **Overlays compiled.** All ten RAM bands (405 unique code sections,
      3.6 MB) are extracted from the disc and compiled in, dispatching natively —
      a live battle logged 904,076 content checks with zero CRC misses, and combat
      runs native. Entry-point coverage *inside* the bands grows from live play
      (the Axis B loop)
- [x] **Savestates.** Save and load, round-trip verified on the LLE backend, and
      confirmed to survive a rebuild. In-game slot saving now works, including in
      combat; savestate *files* can still refuse in overlay-heavy code (an
      interrupt taken inside the dirty-RAM interpreter is never snapshot-safe), so
      in-game memory-card saves remain the reliable way to preserve progress
- [x] **Audio.** Music and sound effects play
- [x] **Memory cards.** In-game saves write a 128 KB card through the SIO path
- [x] **Played past the opening.** Prologue → mines → area transitions, name
      entry, and menus, with the debug server attached throughout
- [x] **Text engine identified and confirmed on a live run** — the message
      table walks correctly on both block shapes
      ([`docs/TEXT_ENGINE.md`](docs/TEXT_ENGINE.md))
- [x] **Full speed.** Capcom logo, world map and memory-card screens hold 60 fps
      with clean audio on an optimised build (2026-09-01), after two framework
      fixes that are now merged upstream
- [x] **CRT scanlines** as an optional, off-by-default present-time effect
      (framework feature; the launcher toggle is pending upstream)

What does not work yet:

- [ ] **Overlay entry-point coverage — the main remaining work.** The overlay
      *bands* are compiled (above), but a compiled band is not a fully native
      band: interior entry points reached only by dynamic dispatch are invisible
      to the static call-graph walk, so they fall to the interpreter until live
      play surfaces them and they are recompiled. This coverage loop is proven
      and converging; deepening it (and eventually per-occupant attribution)
      still gates performance on some screens ([`docs/OVERLAYS.md`](docs/OVERLAYS.md))
- [ ] No end-to-end playthrough, and no soak past the early game. (The
      screens that used to run slow — Capcom logo, world map, memory-card — hold
      60 fps as of 2026-09-01 after two framework fixes, both merged upstream)
- [ ] JP→EN runtime string translation — the script is located, the engine is
      identified and the lookup confirmed live; what remains is variable-width
      glyph advance, line-break policy, and applying translated text
- [ ] Menus, items and name entry are a **separate** text pool from the `.EMI`
      area script — translating only the script leaves them in Japanese

### Localization research

The Japanese script does **not** live in the boot executable. It sits in
per-area `.EMI` container sections — the section whose destination address is
`0x80010000` — and reaches RAM by CD-ROM DMA, so translation aligns by file and
slot rather than by address. The message engine is identified and confirmed
live ([`docs/TEXT_ENGINE.md`](docs/TEXT_ENGINE.md)); the whole translation
surface (area script, a separate menu/item pool, a string table inside
`GAME.EMI`, and 37 language-bearing images) is enumerated in
[`docs/regional-builds.md`](docs/regional-builds.md). What remains is applying
it: variable-width glyph advance, a line-break policy, and the hook at the
message-table lookup ([`docs/LOCALIZATION.md`](docs/LOCALIZATION.md)).

Current state, evidence, and next actions live in
[`docs/STATUS.md`](docs/STATUS.md) and [`docs/HANDOFF.md`](docs/HANDOFF.md).
Claims in those docs cite the trace or run that established them — that is the
project's standard, inherited from the framework.

## Requirements

### You must own the game

This repository contains **no game code, assets, or disc data**, and never will.
You need your own legal dump of Breath of Fire III (Japan). `.bin`/`.cue`/`.iso`
files are gitignored and must never be committed.

A retail PlayStation BIOS is **not** required and is not redistributed — the
build uses OpenBIOS by default. You may supply your own SCPH dump locally with
`--bios` if you prefer.

### Toolchain

| Tool | Version built against | Notes |
|---|---|---|
| GCC / G++ | 16.2.0 | Default compiler |
| Clang | 22.1.8 | Optional alternative |
| CMake | 4.4.2 | ≥ 3.20 required |
| Ninja | 1.13.2 | Generator used throughout |
| ccache | 4.14 | Optional; greatly speeds rebuilds |
| SDL3 | 3.4.14 | Default backend; CMake falls back to `FetchContent` without a system package |
| SDL2 | 2.32.10 | Only for `-DPSX_SDL_BACKEND=SDL2` |
| Python | 3.14 | Needs `tomllib` |

Linux/macOS equivalents are in `psxrecomp/docs/BUILDING.md`.

## Setup

### Windows

Windows uses **MSYS2 MinGW-w64**, the toolchain `psxrecomp/docs/BUILDING.md`
recommends for release parity.

```powershell
winget install --id MSYS2.MSYS2 --exact
```

```bash
# In the MSYS2 shell. Run -Syu twice: the first pass upgrades msys2-runtime
# and closes the shell before the rest of the update can apply.
pacman -Syu --noconfirm
pacman -Syu --noconfirm

pacman -S --needed --noconfirm \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-ccache mingw-w64-x86_64-clang \
  mingw-w64-x86_64-sdl3 mingw-w64-x86_64-SDL2
```

Mind the SDL casing: SDL3 is lowercase `sdl3`, SDL2 is uppercase `SDL2`. pacman
aborts the entire transaction on one unknown target, so a single typo installs
nothing at all rather than partially succeeding.

MSYS2 does not put its tools on the system `PATH`. **Every build shell needs:**

```bash
export PATH=/c/msys64/mingw64/bin:$PATH
```

That one prepend supplies the compilers, CMake, Ninja *and* a working `python3`.
Two Windows traps it avoids:

- Without it, bare `python3` hits the Microsoft Store alias stub, which prints
  "Python was not found" and exits **9009**. It resolves as a command, so
  scripts see it as present and then fail confusingly.
- `C:\msys64\usr\bin\bash.exe` is the **MSYS** environment, a different prefix —
  it has neither `python` nor `cmake`. Use Git Bash with the prepend above, or
  the MSYS2 **MINGW64** shell.

### Build

Place your dump in `isos/` (gitignored), then:

```bash
export PATH=/c/msys64/mingw64/bin:$PATH   # Windows only
git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh
python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . \
  --disc "isos/Breath of Fire III (Japan).cue"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

The emitter step is a shell script, so on Windows run the loop from **Git Bash**
or the MSYS2 MINGW64 shell rather than PowerShell.

`[game].disc` in `game.toml` is **repo-relative** (`isos/…cue`) and resolves
against the detected project root, so it works from any checkout and from
`build-release/` without editing. Only the filename needs to match your dump.

Generating takes a while — it emits ~2.5M lines of C, and the first compile of
that is the long pole. `ccache` makes subsequent rebuilds much cheaper.

#### Compile the overlays (do not skip this)

Most of this game's code is in runtime-loaded `.EMI` overlays, not the boot
EXE. They are extracted from your disc and compiled as a second generated
source, `generated/overlays_static.c`. **If that file is absent, CMake silently
builds a runtime without overlay dispatch** — it runs, but ~90% interpreted and
far below full speed. Run this between `generate` and the CMake build:

```bash
python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue" --out analysis/emi_sections.json
python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" --out analysis/overlay_captures_all.json
python tools/extract_logo_overlay.py "isos/Breath of Fire III (Japan).cue" \
  --out analysis/logo_capture.json --append-to analysis/overlay_captures_all.json
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psxrecomp_codegen_hash     # must precede the overlay compile
python psxrecomp/tools/compile_overlays.py --static --force --cps \
  --captures analysis/overlay_captures_all.json --game-toml game.toml \
  --recompiler build-recompiler/psxrecomp-game.exe \
  --runtime-include psxrecomp/runtime/include --out-dir generated \
  --gcc /c/msys64/mingw64/bin/gcc.exe
cmake -S . -B build-release      # re-run configure so the new source is picked up
```

The overlay compile exits 2 with a handful of `SHARD FAIL [audit] … 0 unknown_bad,
N unsupported` lines. That is expected (data being walked as code; those
occupants fall to the interpreter). Any other failure class is a real problem.
`tools/axis_b_loop.sh` wraps all of this for later rebuilds; the full story is
in [`docs/HANDOFF.md`](docs/HANDOFF.md).

### Run

The build produces the launch binary `BreathOfFire3_Recompiled` (Windows appends
`.exe`; Linux and macOS use the bare name). This is the executable inside each
OS release archive, so it is what a launcher runs after install:

<!-- retcomm-launch-binaries -->
| OS | Release archive | Launch binary |
|---|---|---|
| Windows | `bof3-<version>-windows-x64.zip` | `BreathOfFire3_Recompiled.exe` |
| Linux | `bof3-<version>-linux-x64.zip` | `BreathOfFire3_Recompiled` |
| macOS (Apple Silicon) | `bof3-<version>-macos-arm64.zip` | `BreathOfFire3_Recompiled` |
| macOS (Intel) | `bof3-<version>-macos-x64.zip` | `BreathOfFire3_Recompiled` |
<!-- /retcomm-launch-binaries -->

The `bof3-` prefix and per-OS `<artifact>` tags come from
`scripts/package_setup_release.sh` (`--zip-prefix bof3`) and the release
workflow matrix (`.github/workflows/release.yml`); `<version>` is the release
tag.

```bash
cd build-release
./BreathOfFire3_Recompiled.exe                      # launcher
./BreathOfFire3_Recompiled.exe --headless --no-launcher   # CI / soak
```

Flags are parsed in `psxrecomp/runtime/src/main.cpp`: `--bios`, `--game`,
`--disc`, `--debug-port`, `--memcard-dir`, `--renderer`, `--window-title`,
`--launcher`, `--no-launcher`, `--headless`, `--netplay`, `--net-*`.

> `--help` is **not** a recognized flag. The runtime ignores unknown arguments
> and launches normally, so `--help` opens a window instead of printing usage.

`--headless` implies `--no-launcher`, opens no window or audio device, and
suppresses blocking modal dialogs — it is the right frontend for unattended
soak runs. A hung or slow run writes `psx_freeze_heartbeat.json` next to the
executable.

> **A Release build cannot be inspected.** `PSX_DEBUG_TOOLS` defaults **off**
> for Release, which compiles out the TCP debug server entirely — `--debug-port`
> is silently inert and the heartbeat file is your only diagnostic. This cost a
> misdiagnosis once already ([`docs/BRINGUP.md`](docs/BRINGUP.md), Boot 001).

For anything diagnostic, build a second tree with the tools enabled. The one
that both plays at full speed and can be inspected is RelWithDebInfo:

```bash
cmake -S . -B build-relprof -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DPSX_DEBUG_TOOLS=ON -DPSX_STATIC_RUNTIME=ON
cmake --build build-relprof --target psx-runtime
```

`PSX_STATIC_RUNTIME` defaults off outside Release; without it the exe loads
whatever `libstdc++-6.dll` is first on `PATH` and can die at startup. A
`-DCMAKE_BUILD_TYPE=Debug` tree (`build-dbg`) is useful for stepping but is too
slow (-O0) to judge performance by.

That build serves a JSON debug server (default port 4370) offering screenshots,
GPU state, RAM reads, write tracing, input injection and savestates.
`tools/playsession.py` wraps the common operations:

```bash
python tools/playsession.py status          # frame, GPU state, armed traces
python tools/playsession.py shot out.png    # needs --renderer software
python tools/playsession.py state save 1    # savestate slot 1
```

Screenshots require `--renderer software`; with OpenGL in headless there is no
GL context and captures come back black. The GPU inspection command is
`gpu_state`, not `gpu`. Debug-tool builds also carry a starvation watchdog that
exits after a 4 s emu-thread stall (savestate writes and disc seeks can trip
it); set `PSX_STARVATION_TIMEOUT_US=0` when playing.

<!-- retcomm-readme-launcher -->
## RetComM Launcher

You can run this title **standalone** (release zip + the built-in recomp-ui
Generate & Build flow), or manage installs, updates, ROM/BIOS wiring, and queued
builds more intuitively with
**[RetComM Launcher](https://github.com/TechnicallyComputers/RetComM-Launcher)** —
the Retro Compilation Manager hub for self-compiling recomps.

[Downloads](https://github.com/TechnicallyComputers/RetComM-Launcher/releases) ·
[Full README & features](https://github.com/TechnicallyComputers/RetComM-Launcher#readme)

<p align="center">
  <img src="https://raw.githubusercontent.com/TechnicallyComputers/RetComM-Launcher/main/docs/screenshots/hub-and-game-launcher.png" alt="RetComM hub with a background build, next to a title’s recomp-ui launcher" width="720">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/TechnicallyComputers/RetComM-Launcher/main/docs/screenshots/queue-and-background-build.png" alt="Background cmake build with titles queued" width="720">
</p>

RetComM checks for updates, rebuilds with existing build data when possible,
shares the portable toolchain used by per-title launchers, and automates
BIOS/ROM/save plumbing so you are not stuck repeating each game’s wizard by hand.
<!-- /retcomm-readme-launcher -->

## Project structure

```
game.toml              title config — identity, digests, recompiler, runtime, localization
game_options.toml      native in-game OPTION persistence (template)
symbols.toml     ──▶   tools/sync_symbols.py  ──▶  psx_symbols.h  (PSX_FN_*)
seeds/                 ghidra_funcs.txt — recompilation seed targets
codegen_setup.c/.h     setup-wizard host wiring
CMakeLists.txt         psxrecomp_add_game_runtime(psx-runtime …)
catalog_identity.json  marketing + ROM identity for launcher catalogs
docs/                  title-owned notes — index in docs/README.md
tools/                 sync_symbols.py, the overlay coverage loop, disc/EMI/disasm/session helpers
isos/                  your legal dump          (gitignored, never committed)
disc/                  staged boot EXE          (gitignored)
analysis/              EMI survey, observed PCs, overlay captures (gitignored, regenerated)
generated/             recompiled C output + overlays_static.c (gitignored)
build-recompiler/      emitter binaries         (gitignored)
build-release/         native runtime           (gitignored)
build-relprof/         runtime + debug server, full speed (gitignored, RelWithDebInfo)
build-dbg/             runtime + debug server, -O0   (gitignored, Debug)
psxrecomp/             SUBMODULE — framework    (read-only here)
recomp-ui/             SUBMODULE — launcher     (read-only here)
```

### How it works

1. **Emitters build.** `psxrecomp-game` and `psxrecomp-bios` are compiled from
   the framework submodule.
2. **Generate.** The boot EXE is parsed, functions are discovered by following
   JAL targets to closure from the seed list, and each is translated to C.
   OpenBIOS is recompiled the same way. `strict = true` means anything the
   translator cannot faithfully express **aborts loudly** rather than emitting
   a stub.
3. **Overlays.** The `.EMI` containers on the disc declare where each section
   loads in RAM. Every code section is extracted, translated the same way, and
   registered as a CRC-guarded native variant: at runtime the live bytes are
   hashed before a call is allowed, so whichever overlay is resident wins and
   a non-resident one falls back to the interpreter. Entry points the static
   call-graph walk cannot see are fed back from live play.
4. **Native build.** The generated C is compiled and linked against the
   framework runtime — which simulates the GPU, SPU, CD-ROM, DMA, timers, and
   interrupt controller — plus the recomp-ui launcher.
5. **Run.** The result is a native executable that mounts your disc, verifies
   it, and executes the game's own translated code.

## Symbols

Progressive symbol map — discover, label, then manipulate via `PSX_FN_*`:

```bash
python3 tools/sync_symbols.py    # symbols.toml → psx_symbols.h
```

Never hand-edit `psx_symbols.h`; it is generated. Gate `emit = true` only when
an entry is safe to own. See `psxrecomp/docs/SYMBOLS.md`.

## Framework pins

Submodule gitlinks (`psxrecomp`, `recomp-ui`, nested `recomp-net`) are
authoritative. `framework_pins.txt` is an optional scaffold snapshot; release CI
logs SHAs with `record_pins.sh` but builds whatever the gitlinks resolve to.
Bump submodules deliberately — never float on `main`/`master` in release CI.

The framework submodules are **read-only from here**. Fixes to psxrecomp or
recomp-ui belong upstream in their own repositories, not as local patches.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/STATUS.md`](docs/STATUS.md) | Living status — where the project stands, what's in flight, what's blocked |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Next-session handoff — what to pick up, and the traps already paid for |
| [`docs/BRINGUP.md`](docs/BRINGUP.md) | Boot/soak log — what runs, where it stops, what was fixed |
| [`docs/LOCALIZATION.md`](docs/LOCALIZATION.md) | JP→EN: where the script lives on disc, the `.EMI` container, what blocks applying a translation |
| [`docs/OVERLAYS.md`](docs/OVERLAYS.md) | Why most of this game is overlays, and the `.EMI` finding that makes them extractable from the disc |
| [`docs/OVERLAY_EXTRACTION.md`](docs/OVERLAY_EXTRACTION.md) | The ten-band overlay map, the extraction/compile pipeline, and the measured dispatch results |
| [`docs/TEXT_ENGINE.md`](docs/TEXT_ENGINE.md) | The message interpreter, renderer and glyph path, confirmed live |
| [`docs/regional-builds.md`](docs/regional-builds.md) | JP/US/EN/FR/DE comparison — where every localized byte lives |
| [`docs/SAVESTATES.md`](docs/SAVESTATES.md) | What each savestate slot holds, and why saves sometimes refuse |
| [`docs/ENHANCEMENTS.md`](docs/ENHANCEMENTS.md) | Post-faithfulness work: scanlines (shipped upstream), pause/frame-advance, backlog |
| [`docs/INVENTORY.md`](docs/INVENTORY.md) | What is actually in this repo |
| [`docs/README.md`](docs/README.md) | Documentation index and conventions |
| `CLAUDE.md` | Session bootstrap for AI agents working in this repo |

Framework reference lives in `psxrecomp/docs/` — `GAME_PROJECT_SETUP.md`,
`BUILDING.md`, `SYMBOLS.md`, `STRING_TRANSLATION.md`, `overlay-discovery.md`,
`FUNCTION_DISCOVERY.md`, `config_schema.md`, `TESTING.md`.

## Contributing

The highest-value contributions right now, in order:

1. **Play it and find where it breaks.** The game runs at full speed but has
   never been played through. Crashes, hangs, and wrong output are all useful.
   Use a debug-tools tree (`build-relprof`) so the run can be inspected live
   rather than post-mortem, and say which screen and which area. Playing *new*
   content also directly advances overlay coverage — a live session is the one
   manual input the Axis B loop needs.
2. **Apply the translation.** The message engine is identified and confirmed
   live; what remains is variable-width glyph advance, a line-break policy,
   applying translated text, and the separate menus/items/name-entry text pool.
3. **Deepen overlay coverage.** The ten overlay bands are compiled; the open work
   is interior entry points reached only by dynamic dispatch (Axis B) and
   per-occupant attribution inside multi-tenant bands.
4. **Reverse engineering.** Identify functions and record them in
   `symbols.toml` with the rationale for how they were identified.

Ground rules:

- **You must legally own the game.** Never commit disc data, BIOS dumps, or
  ripped assets — not as files, not pasted into a document or commit message.
- **No stubs.** A function is fully implemented or it fails loudly. `return 0;`,
  `// TODO`, and `// for now` are all stubs.
- **Evidence over assertion.** Accuracy claims are cross-referenced against an
  external comparative — psx-spx, the in-tree Beetle oracle, DuckStation, or
  hardware test ROMs — not asserted.
- **No per-game hacks during foundation work.** If the recompiler or the
  hardware simulation is wrong, fix *that*. Per-title shims become legitimate
  only in the enhancement phase, after the faithful core is proven.
- **Disclose AI assistance** in pull requests.

## AI-assisted development

Parts of this project — bringup diagnosis, documentation, and configuration —
are developed with AI assistance. Generated work is held to the same standard as
everything else: it is verified against real runs and real traces before it is
committed, and findings cite the evidence that established them. AI output that
cannot be verified does not land.

## Legal

This is a **clean-room recompilation project**. It contains no game code,
assets, text, audio, or disc data, and it never will.

**Not included and not distributed:**

- Breath of Fire III — its code, assets, text, audio, or disc images. Those
  remain the property of **Capcom Co., Ltd.**
- Any PlayStation BIOS image. Those rights are Sony Interactive Entertainment's.
  The build uses OpenBIOS instead.

**Tracked in this repository:** build configuration, recompilation seeds
(addresses only), symbol maps, tooling, documentation, and host glue code.

Running this software requires a disc dump you produced from your own legally
purchased copy. Obtaining the game any other way is your responsibility, not
this project's.

Licensed under the **PolyForm Noncommercial License 1.0.0** — see
[`LICENSE`](LICENSE). Noncommercial use is welcome; commercial use is not
granted. The framework this builds on, psxrecomp, is licensed the same way;
recomp-ui is MIT. Each submodule retains its own terms.

Default app icon: `assets/psxrecomp.ico` (and `.png` / `.svg`) — RetComM-themed
controller mark from `psxrecomp/assets/`. Windows builds embed it via
`APP_ICON`. Optional box art under `launcher_assets/img/` may come from
[libretro-thumbnails](https://github.com/libretro-thumbnails/libretro-thumbnails)
(`Named_Boxarts`); see `BOXART_SOURCE.txt` when present.

Breath of Fire is a trademark of Capcom Co., Ltd. This project is not
affiliated with, endorsed by, or sponsored by Capcom or Sony Interactive
Entertainment.

## Acknowledgments

- **[mstan](https://github.com/mstan)** — for
  [psxrecomp](https://github.com/mstan/psxrecomp) and
  [recomp-ui](https://github.com/mstan/recomp-ui), the framework and launcher
  this title is built on.
- The **[OpokXeno/xenogears-recomp](https://github.com/OpokXeno/xenogears-recomp)**
  project, whose repository served as the model for this README.
- The PSX documentation community — **psx-spx** above all — without which none
  of the hardware simulation would be verifiable.

<!-- retcomm-readme-raid -->
---

<p align="center">
  <sub><b>R.A.I.D. — Retro AI Development</b> · a Discord for AI-assisted retro reverse-engineering, decomp &amp; recomp</sub>
</p>

<p align="center">
  <a href="https://discord.gg/Ad9BwSzctP"><img src=".github/raid-discord.png" alt="Join the Retro AI Development (R.A.I.D.) Discord" width="200"></a>
</p>
<!-- /retcomm-readme-raid -->
