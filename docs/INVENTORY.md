# Repo inventory

**Status:** STABLE (re-snapshotted 2026-09-01; the original 2026-08-29 snapshot
at `40185ff` described a scaffold that had never been built)

What exists in this repository so a new session doesn't have to re-derive it.
Re-verify anything you're about to depend on.

## Provenance

Scaffolded 2026-08-29 by psxrecomp's **New Project Layout** generator
(`psxrecomp/tools/new_project_layout/setup_project.ps1`) against a legal
Redump dump of *Breath of Fire III (Japan)*. Since then: first boot 2026-08-29,
playable 2026-08-30, all overlay bands compiled 2026-08-31, 60 fps and all
framework PRs merged upstream 2026-09-01. History in [`STATUS.md`](STATUS.md) →
Log.

## Title identity (from `disc_probe.json` / `catalog_identity.json`)

| Field | Value |
|---|---|
| Serial | `SLPS-00990` (Japan, Capcom, 1997) |
| Boot EXE | `SLPS_009.90` (staged at `disc/SLPS_009.90`, 1,458,176 bytes) |
| Load address | `0x80093800` |
| Entry PC | `0x8014AA0C` |
| `.text` size | `0x00163800` — 81.6% zero-fill that overlays load into |
| Stack base | `0x801FFFF0` |
| Data track | 479,812,704 bytes · md5 `cb8d17ce…` · sha1 `ee7b2031…` |
| Tracks | 2 (multi-track cue required) |
| Disc fingerprint | `2489523d…` (`psxrecomp-toc-v1`) |
| Players | 1 (netplay auto-disabled) |

`game.toml`'s `disc =` is **repo-relative**: `isos/Breath of Fire III (Japan).cue`.
TOML paths resolve against the detected project root (nearest ancestor with
`.git` / `.gitignore` / `CMakeLists.txt`), not the working directory, so it holds
when the exe runs from a build tree. `/isos/` is gitignored.

## Top-level files

| Path | Role |
|---|---|
| `CMakeLists.txt` | `psxrecomp_add_game_runtime(psx-runtime …)`; `PSX_SETUP_WIZARD=ON`, recomp-ui on, netplay off. Passes `GAME_OVERLAY_STATIC_C` (keep it after `APP_ICON`). Stages `game.toml` / `game_options.toml` next to the exe |
| `game.toml` | Title config: identity, `[prepare_disc]` digests, `[recompiler]` (`strict = true`), `[runtime]`, `[localization]` (`en` + `jp`), `[video]` (opengl, 4:3), `[controller]`, `[netplay]` |
| `game_options.toml` | Native in-game OPTION persistence (all-comment template) |
| `symbols.toml` → `psx_symbols.h` | Progressive symbol map via `tools/sync_symbols.py`. **Do not hand-edit the header.** Text-engine functions are still unnamed (see `TEXT_ENGINE.md`) |
| `codegen_setup.c/.h` | Setup-wizard host config: display name, `BREATHOFFIRE3RECOMP_*` env names, gen marker `generated/SLPS_009.90_dispatch.c`, exe basename `BreathOfFire3_Recompiled` |
| `catalog_identity.json`, `disc_probe.json` | Launcher/RetComM identity; full `probe_disc.py` dump |
| `framework_pins.txt` | Informational snapshot of submodule SHAs — the **gitlinks are authoritative** |
| `.mcp.json` | ghidra-mcp stdio bridge on `127.0.0.1:8089` (needs the Ghidra GUI running) |
| `VERSION` | `0.1.0` |
| `.gitignore` | Blocks `generated/`, `build*/`, `disc/`, `isos/`, `analysis/`, `saves/`, all disc/memcard formats, root `*.json` except catalog/probe |
| `README.md` | Public-facing: status, setup, build, run, docs index, legal |

## Directories

| Path | Contents |
|---|---|
| `docs/` | Title-owned notes — index in [`README.md`](README.md) |
| `tools/` | The Axis B loop and its phases, `.EMI`/disc/disasm helpers, debug-server wrappers, benchmarks — table in [`HANDOFF.md`](HANDOFF.md) → Tooling |
| `seeds/ghidra_funcs.txt` | 523 first-pass JAL targets + entry. Extending it is a proven null result; overlay entry points go through `analysis/observed_interp_pcs.json` instead |
| `scripts/package_setup_release.sh` | Thin wrapper over the framework's setup-host packager (`--zip-prefix bof3`) |
| `mods/preloaded/packages/` | Empty (`.gitkeep`) |
| `launcher_assets/img/` | `boxart.png` / `.tga` + `BOXART_SOURCE.txt` |
| `assets/` | Default app icon |
| `.github/workflows/release.yml` | Setup-host multi-platform release workflow (never ships `generated/`) |
| `names/` | Human-name sidecars: `overlays.toml` (339, keyed by section md5), `functions.toml` (overlay functions, keyed by md5+pc), `areas.toml` (15 sighted places, keyed by script-block md5). See `docs/NAME_MAP.md` |
| `.claude/launch.json` | `docs-static`: `python -m http.server 8765 -d docs` to browse `docs/subsystem_map.html` |
| `psxrecomp/` | **Submodule** @ `7ab698ca` = fork branch `perf/static-overlay-parallel` = upstream `mstan/master` `04d9184b` + parallel/split static compile (draft PR mstan/psxrecomp#296; re-pin to master when merged) |
| `recomp-ui/` | **Submodule** @ `fda07fe` = fork `feat/present-scanlines` (upstream `4eda654` + launcher Scanlines toggle; PR mstan/recomp-ui#42 open) |

Gitignored, present on this machine (regenerate on a fresh checkout):

| Path | Contents |
|---|---|
| `isos/` | JP dump plus US / EU / FR / DE dumps used for the regional comparison |
| `disc/SLPS_009.90` | Staged boot EXE |
| `generated/` | Base EXE + BIOS shards (39 files), `overlays_static.c` (overlay dispatcher) + `overlays_static_NNNN.c` (one unit per overlay, all ten bands + LOGO) |
| `analysis/` | `emi_sections.json` (survey), `observed_interp_pcs.json` (cross-session union — **the one file that accumulates**), `overlay_captures_all.json`, `logo_capture.json`, `overlay_catalog.json`, `functions.tsv`, plus historical capture sets |
| `build-recompiler/`, `build-dbg/`, `build-relprof/`, `build-release/` | See [`STATUS.md`](STATUS.md) → Build trees |
| `saves/openbios/` | Savestates `state_8014AA0C_slotNN.pst` — index in [`SAVESTATES.md`](SAVESTATES.md); `card1.mcd` memory card |

## Local environment

Machine state, not repo state. Installed and verified: MSYS2 MinGW-w64 at
`C:\msys64` (GCC 16.2.0 · Clang 22.1.8 · CMake 4.4.2 · Ninja 1.13.2 · ccache
4.14 · SDL3 3.4.14 · SDL2 2.32.10 · Python 3.14.7) · JDK 21 · Ghidra 12.1.3 +
GhidraMCP 6.0.0 (project `D:\Utilities\GhidraProjects\BoF3`) · `gh` 2.98.0 at
`C:\Program Files\GitHub CLI` (not on PATH; authenticated as `kerokline`).

**Python is the sharp edge.** Which interpreter answers depends on the shell:

| Shell | `python` | `python3` |
|---|---|---|
| Git Bash / PowerShell (no prepend) | Anaconda 3.13.9 | Microsoft Store **stub** — "Python was not found", exit 9009 |
| With `/c/msys64/mingw64/bin` prepended | mingw64 3.14.7 | mingw64 3.14.7 |
| MSYS2 `usr/bin` shell | absent | absent |

CMake independently picks `…\Programs\Python\Python312\python.exe` for its own
use. Prepending `/c/msys64/mingw64/bin` is the recommended shell setup; it also
supplies the compiler, without which `cc1` crashes silently. Prior text-decode
work (character table, decoder, aligned JP/EN corpus) lives at `D:\BoFIII`.
