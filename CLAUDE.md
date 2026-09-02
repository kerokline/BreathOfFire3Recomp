# BreathOfFire3Recomp — session bootstrap

Static recompilation of **Breath of Fire III (Japan), SLPS-00990** to native
code, built on the [psxrecomp](https://github.com/mstan/psxrecomp) framework
and [recomp-ui](https://github.com/mstan/recomp-ui), both pinned as root-level
submodules.

**Read at session start:**

1. This file.
2. [`psxrecomp/CLAUDE.md`](psxrecomp/CLAUDE.md) — the framework constitution.
   It governs anything you touch inside the submodule and sets the rules this
   title inherits (see *Inherited rules* below).
3. [`docs/HANDOFF.md`](docs/HANDOFF.md) — what to pick up next, and the traps
   already paid for. Read this before starting work.
4. [`docs/STATUS.md`](docs/STATUS.md) — where the project stands right now,
   what's in flight, and what's blocked.
5. [`docs/INVENTORY.md`](docs/INVENTORY.md) — what's actually in this repo.
6. [`docs/README.md`](docs/README.md) — where to put notes you produce.

## Repo shape

```
game.toml            title config (identity, digests, recompiler, runtime, localization)
game_options.toml    native in-game OPTION persistence (template)
symbols.toml    ──▶  tools/sync_symbols.py  ──▶  psx_symbols.h   (PSX_FN_*)
seeds/ghidra_funcs.txt   523 first-pass JAL targets from the boot EXE
codegen_setup.c/.h   setup-wizard host wiring
CMakeLists.txt       psxrecomp_add_game_runtime(psx-runtime …)
disc/                staged boot EXE (gitignored)
docs/                title-owned notes  ← put agent documents here
psxrecomp/           SUBMODULE @ 1bf70960 = upstream mstan/master (read-only);
                     all of this title's framework fixes are merged upstream
recomp-ui/           SUBMODULE @ fda07fe — launcher (read-only); fork branch
                     feat/present-scanlines = upstream 4eda654 + Scanlines toggle,
                     pending mstan/recomp-ui#42. Moves in lockstep with a
                     psxrecomp bump when the launcher ABI changes
```

## Workflow

```bash
git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh
python psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . --disc "<path to legal .cue>"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

Symbols, after editing `symbols.toml`:

```bash
python tools/sync_symbols.py
```

## Environment notes (this machine, verified 2026-08-29)

- **Use `python`, not `python3`.** `python3` does not resolve here; `python` is
  Anaconda 3.13.9. Framework docs say `python3` — translate as you go.
- The toolchain is installed but **not on PATH**: prepend
  `/c/msys64/mingw64/bin` (GCC, CMake, Ninja) in every build shell, or `cc1`
  crashes silently. `gh` is at `C:\Program Files\GitHub CLI`, authenticated.
- Windows: both a PowerShell tool and a Git Bash tool are available. The
  framework's `.sh` scripts want bash; run the game exe from PowerShell with
  `$env:VAR = "x"` for environment variables.
- Play/measure on `build-relprof` (RelWithDebInfo + debug tools +
  `PSX_STATIC_RUNTIME=ON`); `build-dbg` is -O0 and cannot judge performance.

## Inherited rules

From `psxrecomp/CLAUDE.md` — these bind work here, not just in the submodule:

- **No stubs.** A function is fully implemented or it aborts loudly.
  `return 0;`, `// TODO`, `// for now` are all stubs.
- **No per-game hacks during foundation work.** If the recompiler or the
  hardware simulation is wrong, fix *that* — do not paper over it with a
  `game.toml` workaround. Per-title shims become legitimate only in the
  *enhancement* phase, after the faithful core is proven.
- **Evidence over assertion.** Accuracy claims are cross-referenced against an
  external comparative (psx-spx, the in-tree Beetle oracle, DuckStation,
  hardware test ROMs).

## Hard constraints

- **Never commit disc data, BIOS dumps, or ripped assets** — no `.bin`/`.cue`/
  `.iso`, no memcard images, nothing out of `analysis/`. `.gitignore` covers
  the files, not a paste into a doc or a commit message.
- **Never edit `psxrecomp/` or `recomp-ui/`.** They are submodules; changes
  belong upstream. Bump the gitlink deliberately — never float on `master`.
- **Never hand-edit `psx_symbols.h`.** Edit `symbols.toml` and re-run
  `tools/sync_symbols.py`.
- **Don't touch `[prepare_disc]` digests or `[netplay]` fingerprints** in
  `game.toml` — they gate disc verification. The translation path deliberately
  leaves the disc unmodified so these stay valid.
- Releases are **setup-host only**: CI never ships `generated/`; players run
  Generate locally.

## Framework reference (read-only, in the submodule)

| Doc | For |
|---|---|
| `psxrecomp/docs/GAME_PROJECT_SETUP.md` | The whole title-bringup flow |
| `psxrecomp/docs/BUILDING.md` | Toolchain + dependencies |
| `psxrecomp/docs/SYMBOLS.md` | `symbols.toml` schema and the `emit` gate |
| `psxrecomp/docs/STRING_TRANSLATION.md` | JP→EN runtime translation (capture ring, apply hook, `translations/*.toml`) |
| `psxrecomp/docs/overlay-discovery.md`, `overlay-status.md` | Overlay bringup |
| `psxrecomp/docs/FUNCTION_DISCOVERY.md` | Growing the seed list past first-pass JALs |
| `psxrecomp/docs/config_schema.md` | Every `game.toml` key |
| `psxrecomp/docs/TESTING.md` | Test/soak harnesses |
| `psxrecomp/docs/MOD_PACKAGES.md` | `mods/preloaded/` format |
| `psxrecomp/docs/ci/README.md` | Release CI |

## Conventions for agents

- Title-specific findings go in `docs/` — see `docs/README.md` for naming,
  status headers, and the evidence rule.
- Project status lives in `docs/STATUS.md`, not here. Update that as work
  lands. This file changes only when the *rules or shape* of the repo change.
