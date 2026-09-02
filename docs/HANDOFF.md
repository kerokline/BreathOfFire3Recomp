# Handoff — next session

**Status:** IN PROGRESS (rewritten 2026-09-01 night after the framework pin
returned to upstream master; the dated banner history this file used to carry
is in the [`STATUS.md`](STATUS.md) Log)

Read [`STATUS.md`](STATUS.md) for where the project stands. This file is what
to pick up, how to build against the current pin, and the traps already paid
for. It points at evidence rather than restating it.

## Where things stand in one paragraph

The game **plays at 60 fps** on `build-relprof` (Capcom logo, world map,
memory-card screens all user-verified 2026-09-01 with clean audio). All ten
overlay bands plus `LOGO/LOGO.EXE` are compiled from the disc and dispatch
~99% native. Every framework fix this title needed is **merged upstream** and
`psxrecomp` is pinned to plain `mstan/master` (`1bf70960`); `recomp-ui` waits
on one launcher PR. The text engine is identified and confirmed live. What is
left: Axis B coverage inside the bands as new content is played, the tier-1/2
runtime enrichment, and the translation apply path.

## Start here

### 1. Axis B — the loop (mechanical, proven, converging)

A compiled band is not a fully native band. Interior entry points reached only
by jump tables and function pointers are invisible to the static call-edge
walk, so they address-miss to the interpreter *inside* a compiled band. The
observed→alias pipeline fixes them: a PC the interpreter *entered* on a live run
becomes a registered dispatch alias on the next compile. This is how §9
(`0x801CEEDC`), the battle interior points (`0x801E6C60`) and the LOGO handler
tables were all resolved — see [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md)
§9 and the [`STATUS.md`](STATUS.md) Log for 2026-09-01.

The loop is one command:

```bash
# game running: BreathOfFire3_Recompiled.exe --game game.toml --no-launcher --debug-port 4370
tools/axis_b_loop.sh            # harvest → extract → LOGO merge → catalog → codegen hash → compile → build-dbg
tools/axis_b_loop.sh --skip-harvest   # rebuild from the observed set as-is
```

Phases, for when you need to run one by hand:

1. Play a live session on a debug-tools build covering **new** content.
2. `python tools/harvest_interp_pcs.py` — **unions** the session's entered PCs
   into `analysis/observed_interp_pcs.json` (distinct, never replaced).
3. `python tools/extract_overlays.py "isos/…Japan.cue" --out analysis/overlay_captures_all.json`
   then `python tools/extract_logo_overlay.py … --append-to` the same file
   (extract rebuilds from `.EMI` only and would drop LOGO).
4. `cmake --build build-dbg --target psxrecomp_codegen_hash` (must precede the
   overlay compile after any framework change).
5. `python psxrecomp/tools/compile_overlays.py --static --force --cps …` — all
   bands, one `generated/overlays_static.c`. Exit 2 with `[audit]`
   `0 unknown_bad, N unsupported` failures is the expected outcome.
6. Build `psx-runtime`; re-measure per PC with `harvest_interp_pcs.py`.

**It needs a play session reaching new content — that is the only blocking
input.** Replaying seen content converges to ~0 new PCs (325→56→20→6). The
observed set accumulates across sessions because two sessions enter almost
disjoint PC sets (which `.EMI` is resident decides what buckets to a band).

**Pending right now:** the 239 PCs from the world-map / shop / save-screen
session are compiled in but not re-measured. Remaining interpreted sinks:
SCENARIO band `0x801F6C00`, mixed BATTLE band `0x801D0C00`, and two residual
battle interior points `0x801D1014` / `0x801E739C`.

**Function-pointer tables need a registered dispatch entry, not just a
compiled root.** LOGO dispatches per-frame effect handlers through tables that
are zero in the image and populated at runtime (`lw v0,0(sN); jalr ra,v0`). A
compiled static *root* is not reachable by `jalr` unless its address is also a
dispatch entry (`0x801D22EC` was compiled and still interpreted).
[`tools/harvest_logo_handlers.py`](../tools/harvest_logo_handlers.py) locates
such tables statically, reads them from a live session, and emits every handler
at once. The pattern recurs in any title with effect/handler tables.

### 2. Enrichment — understanding what the captured PCs are

[`tools/enrich_pcs.py`](../tools/enrich_pcs.py) explains an observed PC
offline: resident `.EMI` occupant (live byte-match), FUNCTION-START vs
INTERIOR, a disassembly window with outgoing `jal` targets, callers from the
live `dirty_block_log` ring (a native PC shows **0 ring hits** — a free check
that a fix took), and `--group` for an interp-weighted subsystem breakdown.
[`tools/overlay_catalog.py`](../tools/overlay_catalog.py) is the offline
sidecar (`analysis/overlay_catalog.json`): family, band co-residency, root
provenance, honestly-attributed heat.

**The durable upgrade is tier-1/2 in the runtime**: record, per PC at entry
time, the resident-occupant CRC (tier 1) and a transfer-type histogram
(call/jalr/jr/branch/irq-resume, tier 2) in `DirtyRamPcEntry`
(`dirty_ram_interp.c`, emitted via `dirty_ram_stats.per_pc`). Mixed bands
(`0x801D0C00` = BATTLE+ETC+SCENARIO+WORLD) cannot be resolved to an occupant
offline; tier 2 would have diagnosed §9 in minutes. This is now an ordinary
upstream `psxrecomp` PR — there is no fork branch to carry it. Endgame: once
calls are grouped by shared caller/callee, the `.EMI`-shaped subsystems fall
out — the unit for modding, performance and extensibility.

### 3. Translation

The engine and the interception point are known ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)).
In order: settle whether Latin/digit bytes are raw ASCII (read `0x8015AD34`),
variable-width glyph advance (the JP interpreter hard-codes 12 px — mine
`SLUS_004.22` for Capcom's own answer), line-break policy, then the apply hook
at the message-table lookup. Menus/items/name entry are a **separate** pool at
`0x80014000`. The prior decode work at `D:\BoFIII` supplies the character table
and 11,491 aligned JP/EN lines ([`LOCALIZATION.md`](LOCALIZATION.md) §4.2).

## Building against the pin

```bash
export PATH="/c/msys64/mingw64/bin:$PATH"          # or cc1 crashes silently
./psxrecomp/tools/ci/build_emitters.sh              # → build-recompiler/
python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc "isos/Breath of Fire III (Japan).cue"   # base EXE + BIOS → generated/
cmake -S . -B build-dbg                              # reconfigure if the shard count changed
cmake --build build-dbg --target psxrecomp_codegen_hash   # BEFORE compiling overlays
tools/axis_b_loop.sh --skip-harvest                  # overlays + build-dbg
cmake --build build-relprof --target psx-runtime     # the play/measure tree
```

Tree configs are in [`STATUS.md`](STATUS.md) → Build trees. `build-relprof` is
RelWithDebInfo + `PSX_DEBUG_TOOLS=ON` + **`PSX_STATIC_RUNTIME=ON`** (defaults
OFF there; the dynamic exe dies on a stale PATH `libstdc++-6.dll`).

Order matters, and each of these cost a session once:

- **Regenerate `overlay_codegen_hash.h` before compiling overlays** after any
  framework change. The stale-recompiler guard compares the recompiler's baked
  hash against `psxrecomp/runtime/include/overlay_codegen_hash.h`, which a
  *runtime* build step writes. Overlays first trips `FATAL: STALE RECOMPILER
  BINARY` — the guard working, not a bug.
- **A generate that changes the shard count needs a CMake reconfigure**, or the
  link fails with undefined `func_*`.
- **recomp-ui moves in lockstep** with a psxrecomp bump when the launcher ABI
  changes (`RecompLauncherCGameInfo.discs` etc.). Symptom: `main.cpp` fails to
  compile with "has no member".
- **`--cps` is required** when compiling overlays (the runtime is a CPS build).
- **`GAME_OVERLAY_STATIC_C` must not follow a multi-value CMake keyword** in
  `CMakeLists.txt` — keep it after `APP_ICON`
  ([`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §4).
- **All bands compile together.** `compile_overlays.py --static` writes one
  file per run; compiling one band alone silently drops the rest.
- `analysis/` is gitignored. A fresh checkout regenerates it with
  `emi_survey.py` → `extract_overlays.py` (+ `extract_logo_overlay.py`) before
  overlays can build. All-bands compile ~13 min, build ~7.

## Pins and branches

- `psxrecomp` **`1bf70960` = upstream `mstan/master`.** No fork commits. Bump
  by fetching upstream, fast-forwarding the submodule's `master`, and
  committing the gitlink — never float.
- `recomp-ui` **`fda07fe`** = fork `kerokline/recomp-ui` branch
  `feat/present-scanlines` = upstream `4eda654` + the launcher Scanlines toggle.
  Pending [mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42);
  pin back to upstream when it merges.
- Fork branches on `kerokline/psxrecomp` that are now history:
  `fix/static-overlay-residency-signal`, `feat/present-scanlines`,
  `perf/spu-sample-event-gate` (all merged), `integrate/scanlines` (local
  integration build, obsolete). `fix/vblank-cadence-pacing` still holds the
  **walk-HLE prototype** `d725af45` (`PSX_HLE_INTRP_WALK=1`, 170 lines in
  `dirty_ram_interp.c` / `debug_server.c`): not needed for any current fix, kept
  because its callback-dispatch mechanics are proven
  ([`vblank-pacing-bug.md`](vblank-pacing-bug.md) → Prototype lessons).
- `framework_pins.txt` is informational; the gitlinks are authoritative.

## Capture and disc extraction are not rivals

Capture supplies two separable things with opposite value here. **The bytes**:
disc extraction wins decisively — complete by construction, deterministic,
reviewable, no playtime. **The entry points**: runtime observation wins — an
executed PC with `entries > 0` is empirical proof of a callable boundary, and
nothing reached only by indirect dispatch is visible statically. So the
architecture is *bytes from the disc, entry points from play*, and that is what
the pipeline does. Every objection to capture (privacy, non-determinism,
coverage bound by playtime) attaches to the bytes; entry points are a list of
integers, diffable and additive, and a bad one is rejected by the compiler's own
validation.

One case where captured bytes would still win: if the game ever patches or
relocates overlay code *after* load, every variant of that band would miss the
CRC and fall to the interpreter silently. No evidence of this so far; the
diagnostic is a band where every variant consistently misses.

The persuasive writeup for the wider ecosystem ("The Disc Ships the Map") is a
private artifact:
<https://claude.ai/code/artifact/37f5d9d1-64c9-4db6-bb65-aad75e0ab4f4>.

## Traps paid for — do not re-pay them

Measurement:

- **Never infer success from `static_hits` or any aggregate counter.** Band 3
  looked perfect by every aggregate while `0x801CEEDC` ran fully interpreted.
  Verify per PC with `tools/harvest_interp_pcs.py` after every rebuild.
- **`overlay_loader_status` is the measurement that matters** —
  `static_checks` / `static_hits` / `static_crc_misses` — not the
  interpreted/native ratio, which is workload-dependent.
- **Measure dispatch changes on both a variant-heavy (boot) and a hit-heavy
  (savestate) workload** — they disagree in sign. `tools/headless_ab.py`.
- **`frame_perf` fps is a rolling 256-frame average** and smears stalls; use
  `all.total_ms_max` for anything stall-shaped. `frame_perf` is unavailable
  headless — use the VSync counter at `0x8018603C` via `read_ram`, and note the
  BIOS VSync counter is **frozen during the intro FMV** (use the host `frame`
  counter there).
- **Frame-number comparisons across runs are invalid** — boot phases do not
  line up. Anchor performance claims to a named screen.
- **Profile the Capcom FMV on a clean boot only.** The mid-FMV savestates
  resume *past* the FMV. `tools/fmv_bench.py` does this.
- **Guest-side counters cannot see host-side overhead.** The FMV fix came from
  gdb stack sampling of the emu thread, after two wrong guest-side theses.
  `phase_profile` mislabels static-overlay code entered from the dirty
  dispatcher as "interp".
- **Headless is uncapped**, so emulated frames per wall second is a better
  dispatch-cost metric than fps.

Pipeline:

- **The all-bands compile exits 2, and that is correct.** Benign iff class is
  `[audit]` and the detail is `0 unknown_bad, N unsupported` (data walked as
  code — TGE/TLT/MOVCI words the R3000A lacks). The count drifts up one
  occupant at a time as the observed set grows (4 → 6 → **7** on 2026-09-01).
  Anything else is a real regression. `axis_b_loop.sh` matches on that shape.
- **`harvest_interp_pcs.py` writes PCs as physical addresses.** Mask with
  `(pc & 0x1FFFFFFF) | 0x80000000` before bucketing, or everything is "unmapped".
- **Do not seed the `GAME.EMI` §0 header pointer table** — chained jump-table
  cases, not function starts; they would truncate their hosts.
- **Seeding the boot EXE is a dead end, proven three ways** — byte-identical
  generate at 523 vs 868 seeds; interior seeds alias into zero-fill parents;
  static code has `entries = 0` ([`OVERLAYS.md`](OVERLAYS.md) §3).
- **Compare discs by content hash, not size** (972 vs 368 changed sections),
  and **section destinations are region-specific** — select by destination
  *within* a region ([`regional-builds.md`](regional-builds.md)).
- **Band 2's compiled region is `0x80093800`–`0x800B4003`**; `0x800C1800` is a
  different band.
- **OV-1 does not apply to the static path.** The CRC gate *is* the dispatch
  condition, so stale code cannot run; multi-occupant bands need no
  register/unregister mechanism. The DLL loader that has the OV-1 defect is
  inert here.
- **Do not build residency detection for the relocated BIOS handler by
  matching ROM bytes.** OpenBIOS rebuilds the exception handler in RAM at boot
  (diverges from the ROM image at `0x27DC`), so no ROM-compiled function can be
  entered at `0x27AC`. Also not needed — that handler was never the FMV cost.

Runtime:

- **The "crashes" are the starvation watchdog** (`exit(2)` after 4 s,
  `exit_origin: "unknown"`). `PSX_STARVATION_TIMEOUT_US=0`.
- **Two ~87 MB freeze dumps at every boot.** Prune them.
- **The launcher is the default.** Use `--game game.toml --no-launcher
  --debug-port 4370`, or the exe sits waiting for a GUI click.
- **PowerShell has no inline env-var prefix**; use `$env:VAR = "x"` then run.
  Git Bash env prefixes do not reliably reach the native child either — run the
  exe from PowerShell.
- **`playsession.send()` takes a dict**, not a string.
- **In-game savestate slot N is file `slotN-1`.** Load with Enter/Start; the
  windowed TCP `state load` wedges the listener (it works headless). Savestates
  survive a rebuild, but a `savestate.c` rework once made old files load
  `last_ok: 0` — re-save rather than investigate; every anchor is minutes from
  boot ([`SAVESTATES.md`](SAVESTATES.md)).
- **Kernel-RAM `jalr` targets can fail-fast** once (`0x00002934`, not
  reproduced) — [`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md).

## Tooling

| Tool | Use |
|---|---|
| `tools/axis_b_loop.sh` | **The Axis B loop in one command** (harvest → extract → LOGO merge → catalog → hash → compile → build). Gates on 0 new PCs (`--force`), tolerates only the benign exit-2 shape, refuses to link a running exe. `--harvest-only`, `--skip-harvest`, `--skip-hash`. |
| `tools/harvest_interp_pcs.py` | Live run → interpreted/native ratio + proven interpreted entry PCs, **unioned** into `analysis/observed_interp_pcs.json`. |
| `tools/extract_overlays.py` | `.EMI` survey → `overlay_captures_all.json` with static roots + observed entries. Reads the observed file by default. |
| `tools/extract_logo_overlay.py` | `LOGO/LOGO.EXE` (a PS-EXE at `0x801CE000`) → `static-emi-v1` capture; `--append-to` the all-bands file. |
| `tools/harvest_logo_handlers.py` | Locate runtime-populated function-pointer tables statically, read them live, emit every handler as a dispatch entry. |
| `tools/enrich_pcs.py` | Explain an observed PC: occupant, boundary, disassembly, linked calls, callers; `--group` subsystem breakdown. |
| `tools/overlay_catalog.py` | Offline catalog sidecar → `analysis/overlay_catalog.json` (overwrite, not merge). |
| `tools/emi_survey.py` | Walk every `.EMI`, hash every section, code-test RAM-bound ones → `analysis/emi_sections.json`. Per region. |
| `tools/fmv_bench.py` | Clean-boot headless FMV benchmark (vblank/present window) with optional gdb sampling of the emu thread. |
| `tools/headless_ab.py` | Headless A/B on a savestate workload (skip the load step for the boot workload). |
| `tools/verify_msgtable.py` | Walk the message table on a running game. |
| `tools/playsession.py` | Debug-server wrapper: status, screenshot (`--renderer software`), savestates, traces. |
| `tools/emi.py`, `tools/disc_ls.py`, `tools/disasm_exe.py` | Parse/extract `.EMI`; list the ISO9660 tree; disassemble the boot EXE with MMIO naming. |
| `tools/export_seeds.py`, `tools/ghidra_seed.py` | Kept for the record — the seed experiments were null. |

## Open questions

- The ~15 KB string table inside `GAME.EMI` §0 — nobody has read it.
- Why `DEMO.EMI` §5 ships the JP image on the PAL English disc.
- Whether the Western builds use proportional glyph advance.
- **211 of 8,694 dispatch addresses are zero-fill** (18 `low` seeds) —
  registered native entries compiled from nothing; dirty-RAM invalidation masks
  them today.
- Text paths not yet seen live: a shop, an equipment menu, battle text.

## Environment

See [`STATUS.md`](STATUS.md) → Environment. Short form: `python` not
`python3`; prepend `/c/msys64/mingw64/bin`; run the exe from PowerShell with
`$env:`; Ghidra project at `D:\Utilities\GhidraProjects\BoF3`
(`analyzeHeadless.bat` cannot run `.py` — use `python -m pyghidra.ghidra_launch`);
prior decode work at `D:\BoFIII` (open the JSON as UTF-8).
