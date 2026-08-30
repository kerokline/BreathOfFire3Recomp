# Repo inventory

**Status:** STABLE (taken 2026-08-29, at commit `40185ff` "Initial New Project Layout scaffold")

Snapshot of what exists in this repository so a new session doesn't have to
re-derive it. Re-verify anything you're about to depend on.

## Provenance

Scaffolded by psxrecomp's **New Project Layout** generator
(`psxrecomp/tools/new_project_layout/setup_project.ps1`) against a legal
Redump dump of *Breath of Fire III (Japan)*. Exactly one commit exists; no
recompilation, build, or boot has happened yet in this repo.

## Title identity (from `disc_probe.json` / `catalog_identity.json`)

| Field | Value |
|---|---|
| Serial | `SLPS-00990` (Japan, Capcom, 1997) |
| Boot EXE | `SLPS_009.90` (staged at `disc/SLPS_009.90`, 1,458,176 bytes) |
| Load address | `0x80093800` |
| Entry PC | `0x8014AA0C` |
| `.text` size | `0x00163800` |
| Stack base | `0x801FFFF0` |
| Data track | 479,812,704 bytes · md5 `cb8d17ce…` · sha1 `ee7b2031…` |
| Tracks | 2 (multi-track cue required) |
| Disc fingerprint | `2489523d…` (`psxrecomp-toc-v1`) |
| Players | 1 (netplay auto-disabled) |

`game.toml`'s `disc =` is **repo-relative** as of 2026-08-29:
`isos/Breath of Fire III (Japan).cue`. TOML paths resolve against the detected
project root — the nearest ancestor with `.git` / `.gitignore` /
`CMakeLists.txt` (`psxrecomp/recompiler/src/config_loader.h:15`) — not the
working directory, so it holds when the exe runs from `build-release/`.
`/isos/` is gitignored, so the dump is never committed. (`[game].exe` was
already relative on the same rule.) Superseded the original absolute
machine-local path.

## Top-level files

| Path | Role |
|---|---|
| `CMakeLists.txt` | Calls `psxrecomp_add_game_runtime(psx-runtime …)`; `PSX_SETUP_WIZARD=ON`, recomp-ui on, netplay commented out. Stages `game.toml` / `game_options.toml` next to the exe post-build |
| `game.toml` | Title config: identity, `[prepare_disc]` digests, `[recompiler]` (seeds → `generated/`, `strict = true`), `[runtime]`, `[localization]`, `[video]` (opengl, 4:3), `[controller]` (digital), `[netplay]` gates |
| `game_options.toml` | Native in-game OPTION persistence. All-comment template; **untracked** |
| `symbols.toml` | Progressive symbol map. One entry: `BootEntry` @ `0x8014AA0C`, `emit = false`, `status = "guessed"` |
| `psx_symbols.h` | Generated from `symbols.toml` by `tools/sync_symbols.py`. **Do not hand-edit** |
| `codegen_setup.c/.h` | Setup-wizard host config: display name, env var names (`BREATHOFFIRE3RECOMP_*`), gen marker `generated/SLPS_009.90_dispatch.c`, exe basename `BreathOfFire3_Recompiled` |
| `catalog_identity.json` | Machine-readable identity + marketing + rom identity for the catalog / RetComM |
| `disc_probe.json` | Full `probe_disc.py` dump the scaffold produced |
| `framework_pins.txt` | UTF-16 snapshot of submodule SHAs. Informational — the **gitlinks are authoritative** |
| `VERSION` | `0.1.0` |
| `.gitignore` | Blocks `generated/`, `build*/`, `disc/`, `bios/`, all disc/memcard formats, `analysis/`, root `*.json` except catalog/probe |
| `README.md` | Public-facing; quick start, symbols flow, RetComM launcher, legal |

## Directories

| Path | Contents |
|---|---|
| `disc/` | `SLPS_009.90` (staged boot EXE). Gitignored — the `.cue`/`.bin` live outside the repo |
| `seeds/ghidra_funcs.txt` | 523 first-pass JAL targets + entry, scanned from the boot EXE. Overlay/runtime discoveries still need adding |
| `tools/sync_symbols.py` | `symbols.toml` → `psx_symbols.h`; supports `--check` |
| `scripts/package_setup_release.sh` | Thin wrapper over the framework's setup-host packager |
| `mods/preloaded/packages/` | Empty (`.gitkeep`). Preloaded mod packages ship here |
| `launcher_assets/img/` | `boxart.png` / `boxart.tga` + `BOXART_SOURCE.txt` |
| `assets/` | Default app icon (`psxrecomp.ico/.png/.svg`) |
| `.github/workflows/release.yml` | Setup-host multi-platform release workflow (host-only; never ships `generated/`) |
| `psxrecomp/` | **Submodule** @ `f24b7e5d` (`v0.3.2-alpha-45`) — recompiler, runtime, CLI, docs |
| `recomp-ui/` | **Submodule** @ `8c30e004` — launcher UI |

Absent (expected — all generated/build products): `generated/`, `build-release/`,
`translations/`, `saves/`, `bios/`.

## Working-tree state at snapshot

- `game.toml` modified vs. `40185ff`: adds the `[localization]` block
  (`language = "en"`; `en` + `jp` in the dropdown).
- `game_options.toml` untracked (all-comment template).

Together these mark the intent to run this Japanese release in English via the
framework's runtime string-translation path — see
`psxrecomp/docs/STRING_TRANSLATION.md`.

## Local environment (updated 2026-08-29, after toolchain install)

Machine state, not repo state. The build toolchain gap recorded in the original
snapshot has since been **resolved** — MSYS2 MinGW-w64 is installed at
`C:\msys64` and proven by a full 169-target emitter build. Setup steps live in
[`../README.md`](../README.md#development-environment); current status in
[`STATUS.md`](STATUS.md).

Installed: GCC 16.2.0 · Clang 22.1.8 · CMake 4.4.2 · Ninja 1.13.2 ·
ccache 4.14 · SDL3 3.4.14 · SDL2 2.32.10 · JDK 21.0.12.

Still absent: `gh`, and Ghidra / GhidraMCP (optional — see `STATUS.md`).

**Python is the sharp edge on this box.** Which interpreter answers depends
entirely on the shell, so pin it before trusting a command:

| Shell | `python` | `python3` |
|---|---|---|
| Git Bash / PowerShell (no prepend) | Anaconda 3.13.9 | Microsoft Store **stub** — prints "Python was not found", exits 9009 |
| With `/c/msys64/mingw64/bin` prepended | mingw64 3.14.7 | mingw64 3.14.7 ✅ |
| MSYS2 `usr/bin` shell (`C:\msys64\usr\bin\bash.exe`) | absent | absent |

CMake independently selected a *fourth* interpreter for its own use —
`…\Programs\Python\Python312\python.exe` (3.12.6).

Correcting the original snapshot: `python3` **does** resolve without the
prepend, but to the Store alias stub — which is worse than absent, because
scripts detect it as present and then fail with a confusing message. Prepending
`/c/msys64/mingw64/bin` fixes both spellings and is the recommended shell setup.
