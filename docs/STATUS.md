# Current state

**Status:** IN PROGRESS (last verified 2026-09-01, evening)

> **2026-09-01 late — readability track opened: name sidecar + subsystem map.**
> Human names now live outside the regenerated C: `names/overlays.toml` (alias /
> role / status / evidence per overlay, keyed by section **md5**, not PC — bands
> overlap) and `names/functions.toml` ((md5, pc) per overlay function; boot-EXE
> names stay in `symbols.toml`). [`tools/name_map.py`](../tools/name_map.py)
> seeds/merges/validates them; [`tools/subsystem_map.py`](../tools/subsystem_map.py)
> renders [`docs/subsystem_map.html`](subsystem_map.html) — bands → overlays →
> 29 036 overlay functions (roots, spans, in-overlay jal edges, honest heat) +
> the 1 026 boot-EXE functions, searchable by name/alias/PC/md5, no bytes
> embedded. Coverage: 2 overlays `evidence`, 204 `hypothesis` (filename-derived),
> 133 `unnamed` (all AREA/COMMU), 0 overlay functions. Routes to earn names
> (resident script block + screenshot → areas, Psy-Q signatures → boot EXE,
> differential traces → Attack/Battle_Init) are in [`NAME_MAP.md`](NAME_MAP.md).
> Evidence gathering: [`tools/area_poller.py`](../tools/area_poller.py) —
> `watch` during play (identifies the resident AREA with certainty by hashing
> the `0x80010000` script block against `emi_sections.json`, screenshots each
> change, drains the overlay native ring), `harvest` once at end of session
> (now `axis_b_loop.sh` phase 2a, incl. `--harvest-only`), `summarize --apply`
> to write sightings as `evidence`. `axis_b_loop.sh` phase 6 refreshes `names/`
> + the map on every rebuild path. First live run done 2026-09-01: 6 WORLD00 areas identified
> (AREA001/002/006/009/024/031); transition shots were black → fixed with a
> settled-shot delay; native-ring parse fixed (nested `ring`) — it is a per-call
> native trace, which unblocks the differential tracer.

> **2026-09-01 — Capcom-logo lag FIXED (root-caused + compiled).** The opening/
> Capcom logo sequence runs from **`LOGO/LOGO.EXE`** — a standalone 120 KB PS-EXE
> loaded to **`0x801CE000`** (text 0x1D800, entry 0x801CE724), NOT an `.EMI`
> overlay. The `.EMI` extraction pipeline never captured it, so it ran **100%
> interpreted** (~19 present-fps, native dispatch ≈0, one PC `0x801CEEDC` = 84.5%
> of all interp work / 91 M insns). **This corrects the earlier "Capcom slow =
> dispatcher overhead" theory** (below): it was never dispatch *cost* — it was a
> whole uncompiled executable. The RAM overlap with the PLCHAR/battle bands
> (which reuse `0x801CE400+` later) only *camouflaged* it as a CRC-missing PLCHAR
> band. **Fix:** new tool [`tools/extract_logo_overlay.py`](../tools/extract_logo_overlay.py)
> synthesizes a `static-emi-v1` capture from the disc EXE (same jal+prologue
> discovery as `extract_overlays.py`, no external analyzer); `compile_overlays.py`
> compiles it natively like any overlay (1609→1656 funcs, 0 new audit fails); the
> CRC gate handles the RAM overlap. **Result:** `0x801CEEDC` fully native (gone
> from the profile), Capcom interp 5.0M/s→0.25M/s (20×), cumulative interp
> 107.8M→16.3M, present fps **19→steady ~30**, wall-time ~22s→~14s, no visual/boot
> regression. The residual ~30fps is now **pacing-limited** (CPU idle during the
> intro — FMV/CD streaming of `CAPCOM30.STR`), not CPU-limited. Durability: LOGO
> merged into `analysis/overlay_captures_all.json` and re-merged every run by
> `axis_b_loop.sh` phase 3a (extract_overlays rebuilds that file from `.EMI` only
> and would otherwise drop it). Pass-2 (harvest LOGO-resident interiors →
> `logo_observed.json`) landed the 10 jump-table interior entries.
>
> **The residual interior "whack-a-mole" is root-caused and generalized.** LOGO
> dispatches per-frame effect handlers through **function-pointer tables** that
> are zero in the image and populated at runtime (`lw v0,0(sN); jalr ra,v0`) — the
> static walk can't see the targets, so each pass makes the last handler native
> and the interpreter entry just shifts to the next unregistered `jalr` target.
> Traced via the caller ring → dispatcher (`0x801CF980`, walks a 7-slot table at
> `0x801D9CA4`). **Key rule:** a compiled static *root* is NOT automatically
> reachable by `jalr` — a function-pointer call needs the address registered as a
> *dispatch* entry too (`0x801D22EC` was a compiled root yet still interpreted).
> New [`tools/harvest_logo_handlers.py`](../tools/harvest_logo_handlers.py)
> generalizes the fix: statically locate the fn-ptr dispatch tables (forward
> const-prop), read them from a live LOGO-resident session, callable-boundary
> filter, emit every handler at once (found 12 tables → 18 real handlers, 26
> data-array false positives dropped). Rebuilt with all 18 registered. This
> pattern recurs in any title with effect/handler tables.

> **2026-09-01 evening session.** The **Axis B loop is now a one-command script**
> ([`tools/axis_b_loop.sh`](../tools/axis_b_loop.sh): harvest → extract →
> catalog → codegen-hash → compile → build) and is **proven end-to-end**. A
> second play session **banked 239 new PCs** (world map, shops, save/memcard
> screens) → observed set **1195 distinct PCs (1080 entered)**, up from 956/850;
> the new interpreted sinks are SCENARIO band `0x801F6C00` (67 M, doubled) and
> mixed BATTLE band `0x801D0C00` (124 M). Added the **overlay catalog sidecar**
> ([`tools/overlay_catalog.py`](../tools/overlay_catalog.py) →
> `analysis/overlay_catalog.json`): family/subsystem, band membership +
> co-residency, root provenance, honestly-attributed heat. Rebuilt and
> **verified healthy** (headless: 99.29% native dispatch, crc_misses Δ0, 152.9
> emu fps). Benign audit-failure count drifted 4 → 6 (expected). **Pending:** the
> per-PC re-measure confirming those 239 went native needs a play session
> re-exercising that content. Perf: world map + memcard ~50 fps, Capcom still
> ~10-20 fps (savestate anchors slot 08/09/10 — see [`HANDOFF.md`](HANDOFF.md)).

> **2026-09-01 session.** Synced the framework: merged upstream `mstan/master`
> into our fork branch `fix/static-overlay-residency-signal` (`psxrecomp` now
> `ecc0de16` = our 3 commits + 77 upstream), and bumped `recomp-ui` `8c30e004`
> → `4eda654` (**required** — the merged psxrecomp uses the multi-disc launcher
> API that lives in recomp-ui). **Upstream PR held as a draft by decision** — the
> fork is a living integration branch we keep pulling master into; the
> proof-of-process is a full BoF3 decompile with subsystems intact. Full rebuild
> **verified booting**: overlays dispatch native at ~99.6% steady-state hit rate,
> residency signal intact — the CD-ROM/DMA merge did not regress it. Two sync
> gotchas + the recipe are in [`HANDOFF.md`](HANDOFF.md) → "Shipping state".
> Non-blocking follow-up: pre-merge savestates load with `last_ok: 0` (merge
> reworked `savestate.c`).

Living status doc — the one place a new session learns where the project
actually stands. Update this rather than `CLAUDE.md`. Durable findings graduate
into their own `docs/` file (see [`README.md`](README.md)); this stays a short
"where we are, what's next". History lives in the [Log](#log) at the bottom —
do not stack dated banners above this paragraph; add a Log row and update the
sections instead.

## Where we are

**The game plays at full speed.** It boots, renders, has audio, takes input,
writes memory cards, and has been played past the prologue and intro boss into
the world map, shops and save screens. On the optimised tree (`build-relprof`)
the Capcom logo, world map and memory-card screens all hold a user-verified
60 fps with clean audio (2026-09-01). It has not been played end to end.

**Framework pins are upstream `mstan/master` again (2026-09-01).** Every
psxrecomp change this title produced has been merged upstream — the static
overlay residency signal, O(1) dispatch and resident-occupant memo
([#289](https://github.com/mstan/psxrecomp/pull/289)), present-time scanlines
([#290](https://github.com/mstan/psxrecomp/pull/290)), the cheap SPUCNT gate
that fixed the FMV slowdown
([#292](https://github.com/mstan/psxrecomp/pull/292)), and the earlier
present-skip pacing fix ([#273](https://github.com/mstan/psxrecomp/pull/273)).
`psxrecomp` is pinned at `1bf70960` (upstream master). `recomp-ui` stays on the
fork branch `feat/present-scanlines` (`fda07fe` = upstream `4eda654` + the
launcher Scanlines toggle) until
[mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42) merges. The
only fork-side psxrecomp work not upstream is the `PSX_HLE_INTRP_WALK` walk-HLE
prototype (`d725af45` on `fix/vblank-cadence-pacing`), kept for its proven
callback-dispatch mechanics and not needed by any current fix.

**Most of the game is overlays, and they are all compiled.** 81.6% of the boot
EXE's text segment is zero-fill that `.EMI` sections load into at runtime
([`OVERLAYS.md`](OVERLAYS.md)). All 880 containers are enumerated, the code
lands in exactly ten RAM bands (405 unique sections, 3.61 MB), and **all ten
bands plus the standalone `LOGO/LOGO.EXE`** are extracted from the disc and
compiled in as CRC-guarded static overlays — bytes from the disc, entry points
from play ([`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md)). Steady-state
dispatch is ~99% native with `aborts: 0`. The runtime capture path
(`[runtime] overlay_cache`, the DLL loader) stays off, so OV-1 never arms.

**Coverage inside the bands is the remaining performance work (Axis B).** A
compiled band is not a fully native band: interior entry points reached only
through jump tables and function pointers are invisible to the static call-edge
walk and fall to the interpreter until a live session observes them. The loop
is one command ([`tools/axis_b_loop.sh`](../tools/axis_b_loop.sh)) and is
converging (325→56→20→6 new PCs per replayed session; new content still adds —
the last new-content session banked 239). Observed set: **1195 distinct PCs
(1080 entered)**. Detail and the traps in [`HANDOFF.md`](HANDOFF.md).

**The text engine is identified and confirmed live.** Renderer, stepper,
immediate draw, font-atlas mapper and the per-block message-table formula are
all pinned ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)); cross-language disc diffing
independently isolates the script to the `0x80010000` `.EMI` section, and the
whole translation surface is enumerated ([`regional-builds.md`](regional-builds.md)).
No Western release is an address-compatible donor, and none has runtime
language support. Translation is not bound by the JP byte budget.

**Headlines that still hold:**

- Recompilation is clean under `strict = true` — 2.5M lines, 35 shards, 0
  skipped, 0 unsupported, 1467 dispatch entries.
- Seeding is a dead end, proven three ways ([`OVERLAYS.md`](OVERLAYS.md) §3).
- The all-bands overlay compile exits 2 with a handful of `[audit]`
  `0 unknown_bad, N unsupported` shard failures (data walked as code). That
  set drifts upward as the observed set grows — **7** on the 2026-09-01 rebuild
  (`0x800C1800` ×3, `0x801F2C00` ×3, `0x801EEC00` ×1). Not a regression.

## Build trees

| Tree | Config | Use |
|---|---|---|
| `build-relprof` | RelWithDebInfo, `PSX_DEBUG_TOOLS=ON`, `PSX_STATIC_RUNTIME=ON` | **Play and measure.** Holds 60 fps; has the debug server |
| `build-dbg` | Debug (-O0), `PSX_DEBUG_TOOLS=ON`, `PSX_STATIC_RUNTIME=ON` | Diagnosis only. Cannot hold 60 on the FMV — not evidence of a regression |
| `build-release` | Release, `PSX_DEBUG_TOOLS=OFF` | Shipping config. Cannot be inspected at all |
| `build-recompiler` | Release | Emitters (`psxrecomp-game`, `psxrecomp-bios`) |

`PSX_STATIC_RUNTIME` defaults OFF outside Release/MinSizeRel; a dynamic exe
picks up a stale `libstdc++-6.dll` from PATH and dies at startup, so force it
ON. Both debug-tool trees were regenerated and rebuilt against the `1bf70960`
pin on 2026-09-01 (see Log).

## In flight

- **Axis B per-PC re-measure.** The 239 PCs banked from the world-map / shop /
  save-screen session are compiled in but not yet re-measured against a play
  session that re-exercises that content. That session is the one manual input.
- **recomp-ui #42** (launcher Scanlines toggle) awaiting upstream merge; the
  `recomp-ui` pin moves back to upstream master when it lands.
- **Savestate compatibility across the framework bump** is unchecked; the
  `savestate.c` rework (`47bda817`) made pre-merge `.pst` files load with
  `last_ok: 0` once already. In-game memory-card saves are the reliable path.

## Next up

1. **Play new content on `build-relprof` and run the Axis B loop** — the
   remaining interpreted sinks are SCENARIO band `0x801F6C00` and the mixed
   BATTLE band `0x801D0C00`, plus two residual battle interior points
   (`0x801D1014` / `0x801E739C`). Repetition of seen content adds ~0.
2. **Tier-1/2 runtime enrichment** — record resident-occupant CRC and a
   transfer-type histogram per PC in `DirtyRamPcEntry` so mixed bands resolve
   to an occupant. Now an ordinary upstream `psxrecomp` change (there is no
   fork branch to carry it). [`HANDOFF.md`](HANDOFF.md) → Enrichment.
3. **Translation** — settle whether Latin/digit bytes are raw ASCII (against
   `0x8015AD34`), then variable-width advance and line-break policy (mine
   `SLUS_004.22` rather than inventing one), then the apply hook at the
   message-table lookup. Menus/items/name entry are a separate pool.
4. **Name the text-engine functions in `symbols.toml`** and re-run
   `tools/sync_symbols.py`.
5. **Audit the 211 zero-fill dispatch addresses** (from 18 `low`-confidence
   seeds) before trusting native dispatch in that range.

## Known issues, non-blocking

- **Starvation watchdog `exit(2)`** after 4 s without an emu-thread heartbeat,
  reported as `reason: atexit` / `exit_origin: "unknown"`. Debug-tree safety
  net, not a game fault. Disable with `PSX_STARVATION_TIMEOUT_US=0` (PowerShell:
  `$env:PSX_STARVATION_TIMEOUT_US = "0"` on its own line first).
- **Two ~87 MB freeze dumps at every boot** (frame ~328, `slow_frames` then
  `hard_freeze` false positive). Prune `build-*/psx_freeze_dump_*.json`;
  `axis_b_loop.sh` does this for `build-dbg`.
- **Savestate files can refuse** in overlay-heavy code: `savestate_poll` needs
  `psx_irq_resume_context_snapshot_safe()` (`g_cosim_dirty_pump_site == 0`), and
  an interrupt taken inside the dirty-RAM interpreter is never snapshot-safe.
  Much rarer now that the bands are compiled; in-game slot saving works,
  including in combat. Load with Enter/Start; the TCP `state load` path wedges
  the listener on the windowed build (works headless).
- **One unreproduced fail-fast** into kernel RAM `0x00002934` on a slot-7
  resume — [`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md). Fix only
  with a live repro.
- **Four upstream framework observations**, none affecting BoF3: F-1 / F-2 in
  [`BRINGUP.md`](BRINGUP.md), F-3 / F-4 in [`LOCALIZATION.md`](LOCALIZATION.md).

## Environment

MSYS2 MinGW-w64 at `C:\msys64` (GCC 16.2.0, CMake 4.4.2, Ninja 1.13.2, ccache,
SDL3). Not on PATH by default — every build shell needs
`export PATH=/c/msys64/mingw64/bin:$PATH`, or `cc1` crashes silently. `python`
is Anaconda 3.13; `python3` without the prepend is the Store stub. Run the exe
from PowerShell with `$env:` for env vars. `gh` 2.98 is installed and
authenticated as `kerokline`. Ghidra 12.1.3 + GhidraMCP project at
`D:\Utilities\GhidraProjects\BoF3` (1025 functions); the repo-root `.mcp.json`
points at the ghidra-mcp stdio bridge (`127.0.0.1:8089`), which needs the
Ghidra GUI running. Prior text-decode work at `D:\BoFIII`.

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
| 2026-08-30 | **Text engine identified - the translation blocker is closed.** Ghidra 12.1.3 + GhidraMCP 6.0.0 + PyGhidra stood up; boot EXE imported as Raw Binary at `0x80093000` (1025 functions). The three `0x80010004` leads resolve to `0x80150598` (box renderer), `0x8015096C` (stepper) and `0x8015AD34` (immediate `draw(x,y,str)`), sharing one control-code vocabulary and the glyph path `0x8014F6BC` / `0x80151F4C` (21-glyph, 12 px atlas). Message lookup is `0x80010000 + W + u16[base + 2*index]` where `W = *(u32 *)0x80010004`. [`TEXT_ENGINE.md`](TEXT_ENGINE.md). |
| 2026-08-30 | **Regional builds compared (JP/US/EN/FR/DE).** No release has runtime language support - one EXE per disc, no language strings, a separate SKU per language (SLES-01304/01319/01320). No Western EXE is address-compatible (EU vs US ~21% word-identical over the real code region; earlier whole-file similarity figures were zero-fill artifacts). Cross-language `.EMI` diffing isolates all divergence to the `0x80010000` section (93.4% of bytes, and the only section that changes size), **independently confirming** the Ghidra finding and showing translations are not bound by the JP byte budget. [`regional-builds.md`](regional-builds.md). |
| 2026-08-30 | **Message-table formula confirmed live — the last static-only claim is now evidenced.** Read directly off a running `build-dbg` session: the name-entry screen's on-screen string located at `0x80014A86`, and the formula walked from `0x80014000 + W` decoding 17/24 item descriptions; then the mine-area script at `0x80010000` decoding 16/16 slots of the モーグ/ギリー prologue. Correction: the `u16` table base is **per block** — the area script has no `W` header and its table starts at +0, so `*(u32 *)0x80010004` is not universal. Name-entry, config and item text live in the `0x80014000` pool, *not* the `.EMI` area script, so replacing only that section leaves menus Japanese. `tools/verify_msgtable.py` added. [`TEXT_ENGINE.md`](TEXT_ENGINE.md). |
| 2026-08-30 | **Savestate load found to wedge/crash the runtime.** TCP `savestate load` blocked the emu thread past 30 s, tripped the starvation watchdog into two ~100 MB freeze dumps, and killed the listener; the in-game **X** load path crashes the process. **Enter/Start loads work.** Recorded under Blockers → open, non-blocking. |
| 2026-08-30 | ~~**Reproducible crash isolated: unregistered overlays.**~~ **RETRACTED same day — the diagnosis was wrong.** See the retraction entry below. |
| 2026-08-30 | **Overlay crash diagnosis retracted.** The `interp_unsupported` record (`pc 0x801D0AA8`, `insn 0x00000000`, *instruction guard*) was read as a crash signature. It is not. A clean headless boot that never left the title screen, took no input and exited via `tcp_quit` produces the **identical** record, and `dirty_ram_unsupported` reports **`aborts: 0`** — the dirty-RAM interpreter probes that address once at boot, the guard rejects it, nothing aborts. Corroborating static evidence: the boot EXE contains **zero** JAL, J, lui/ori pairs or data words referencing the `0x801CE401`-`0x801D0C00` gap, and a seed (`0x801D0C04`) sits immediately past its end — so the gap is a zero-filled data/BSS region between code, not an overlay landing zone. `overlay_loader registered=0` is likewise expected: `[runtime] overlay_cache` defaults **off** and is a performance feature; overlay code runs via the dirty-RAM interpreter without it. **No crash artifact exists on disk** — both surviving run reports ended `atexit` via `tcp_quit` / `sdl_window_close`. |
| 2026-08-30 | **Freeze-dump disk cost noted.** Twelve automatic freeze dumps written in one afternoon, ~1.2 GB total in `build-dbg/` (gitignored, but they fill a disk fast). Each stall writes two ~100 MB JSON dumps. Worth capping or pruning between sessions. |
| 2026-08-30 | **The crashes are root-caused: the starvation watchdog, by design.** `starvation_ring.c` `exit(2)`s after 4 s without an emu-thread heartbeat (measured gap 4.027 s), which is why every report reads `reason: atexit` / `exit_origin: "unknown"` — `exit(2)` is untagged. Ruled out along the way: the save itself (`slot04` written complete, process lived 58 s more), SIO (~1,957 events/s is normal pad polling), a hard fault (no Windows Error Reporting record at all), and `psx_fatal_halt` (`fatal: None`). Override with `PSX_STARVATION_TIMEOUT_US=0`. Also found: two ~80 MB freeze dumps are written at *every* boot from a frame-328 watchdog false positive, ~160 MB per launch. |
| 2026-08-30 | **~90% of execution is interpreted — the seed list is the bottleneck.** Live measurement: 264.0 M interpreted instructions vs 28.0 M native dispatches (`dirty_ram_stats` / `dispatch_stats`, `miss_total: 0`, `aborts: 0`). `seeds/ghidra_funcs.txt` has 523 entries against 1,025 Ghidra functions, and all eight hot interpreted PCs sampled are missing from it; only 15 seeds are above `0x80190000` where the hot code sits. All are static-EXE addresses, so this is missed heuristics, not overlays. Unifies the day's symptoms: slow interpretation → boot freeze dumps + 4 s starvation `exit(2)`, and non-dispatchable PCs → `savestate_resume_pc_ok()` false → save refusals. |
| 2026-08-30 | **Save refusals explained.** `savestate_poll` defers 2 s then fails with `SAVE FAILED ... no safe resume PC` unless `psx_is_dispatchable(pc)` holds. Reproduced twice at one spot. The guard is correct behaviour — it refuses to write "a structurally valid but poisoned state" — so the fix is seed coverage, not the savestate code. |
| 2026-08-30 | **Submodule reset to the pin; regenerated and rebuilt.** `psxrecomp` had floated to `a91884a4`; reset to `f24b7e5d` (clean, one upstream commit, nothing local). Emitters already matched the pin. `build-dbg` rebuilt 199/199 after a reconfigure — note the generated shard count is captured at configure time, so a generate that changes the shard count needs `cmake -S . -B build-dbg ...` again or the link fails on undefined `func_*`. |
| 2026-08-30 | **Seed-list hypothesis tested and DISPROVEN.** Extending `seeds/ghidra_funcs.txt` from 523 to 868 (all `verified`/`high`/`medium` analyser functions it lacked) produced a **byte-identical generate** — same 35 shards, same 1467 dispatch entries — verified by running `psxrecomp-game` out-of-band against both seed files. The recompiler's own discovery already exceeds `functions.tsv`. Reverted to 523. `tools/export_seeds.py` kept for the record. |
| 2026-08-30 | **Interior-entry seeding works mechanically but is wrong here.** Adding 8 observed interior PCs raised dispatch 1467 → 1475 and made them dispatchable, staying clean under `strict`. Reverted anyway: those addresses are **zero in the EXE image**, so the emitted bodies are NOPs aliased into a zero-fill parent (`psx_alias_body_801D0C04`). Seeding code that is not in the image is fabrication, and it invites stale-registration bugs. The real answer is overlay capture. |
| 2026-08-30 | **Tools added:** `tools/harvest_interp_pcs.py` (reads `dirty_ram_stats`/`dispatch_stats` from a live run, reports the interpreted/native ratio and the proven interpreted entry PCs, writes `analysis/observed_interp_pcs.json`); `tools/export_seeds.py` (analyser → seeds merge, null result above). |
| 2026-08-30 | **Savestates survive a rebuild.** A slot written by the 09:26 build loaded correctly under the 19:45 rebuild (pin reset + regenerate + relink) and resumed at the expected spot. The open question in [`SAVESTATES.md`](SAVESTATES.md) is closed. Saving also works again on the rebuilt tree. |
| 2026-08-30 | **Save-failure mechanism pinned exactly.** Not the dispatchability of the resume PC as first thought, but `psx_irq_resume_context_snapshot_safe()` = `g_cosim_dirty_pump_site == 0`: an interrupt taken inside the dirty-RAM interpreter can never be snapshotted. Live sampling showed a steady 9.0-9.1% native / 91% interpreted mix, so the 2 s defer window routinely expires with no safe poll. Same root cause as the interpretation problem — overlay coverage. Second live profile captured to `analysis/observed_interp_pcs.json` (575 tracked PCs, 84.4% interpreted cumulative). |
| 2026-08-30 | **The zero-fill map: 81.6% of the text segment is runtime-loaded.** 1,187,899 of 1,456,128 bytes are zero in the image, in 11 runs >=2 KB from `0x80093801` to `0x801F6C00`; real static code is only ~268 KB. Confirms overlays dominate this title. Also quantified the contamination this causes: **18 of 523 seeds (3.4%) point at zero bytes** (all `low` confidence, plus the single `data` row), and **211 of 8,694 distinct dispatch addresses are zero-fill** — i.e. the runtime has 211 registered native entries whose bodies were compiled from nothing. Dirty-RAM invalidation masks them today; it is the OV-1 stale-registration risk. |
| 2026-08-30 | **Save failure is about the interrupt path, not the aggregate ratio.** Sampled live: native share *rose* from ~9% to ~18.6% while saves went from intermittent to consistently failing — so the overall mix does not predict it. What predicts it is where the interrupt lands: entries are at the BIOS vector `0x800000A0` and flow into game code at `0x801A1538`/`0x801A1720`/`0x801A19A8`, all of which are **zero-fill overlay addresses**. Every such interrupt sets `g_cosim_dirty_pump_site`, so no poll in the 2 s window is snapshot-safe. Refutes the "new areas are heavier on the interpreter" reading: overlay code is interpreted in *every* area, including ones where saves worked. |
| 2026-08-30 | **Play-session profile harvested; seeding formally ruled out.** 568 tracked PCs over a real session: **93.6% of interpreted instructions are overlay code** (zero in image), 4.2% BIOS/kernel, and just 2.2% static EXE — the last with **`entries = 0`**, meaning the interpreter never *enters* static code and there is no missing static entry point to seed. Overlay PCs touched span `0x801970B4`-`0x801DE098`. Written up in [`OVERLAYS.md`](OVERLAYS.md). |
| 2026-08-31 | **The static overlay path had no residency signal.** `overlay_page_gen` only advances for pages armed via `overlay_watch_set_range`, whose only callers were in the inert DLL loader — so the CRC gate was consulted once per variant per process and cached negatives were permanent. Armed the watch on the cold path (`psxrecomp` `aa6fa2c9`, branch `fix/static-overlay-residency-signal`, off the pin `f24b7e5d`; parent gitlink NOT bumped). Verified live: 99.93% gen fastpath, gate re-fires only on real load events, no false invalidation. Also **measured** §8's previously-inferred cost mechanism — the transition stall is the address-miss fall-through at ~264,000 lookups/sec, 49x the field baseline. [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §10. |
| 2026-08-31 | **O(1) overlay dispatch (step 2 of the upstream fix).** Replaced the sparse `switch` in `generate_overlay_dispatch` with a compile-time open-addressed hash table (`psxrecomp` `69d783f5`). Headless A/B, identical captures/savestate/protocol: throughput 106.5 -> 113.2 emulated fps (+6.3%), p1 93.9 -> 105.2; at the transition 63.9 -> 131.3 fps while absorbing twice the address-miss rate. Behaviour verified identical (same address sets, hashes agree across all 524,288 word-aligned addresses, zero false hits). Also established that the on-disk build was **three-band**, not two, and that headless savestate load works. [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §11. |
| 2026-08-31 | **All ten overlay bands reinstated as the configuration.** Step 3 of the upstream dispatch fix — a resident-occupant memo (`psxrecomp` `70153175`) — cut chk/hit 1.479 -> 1.069 and wasted gate calls 4.5x on the all-bands build, worth **+33% throughput** at boot (99.0 -> 131.4 emulated fps). With steps 1-2 this overturns §8: all-bands now beats three-band on both workloads measured. Also recorded the workload trap — the memo measures neutral-to-negative on a hit-heavy savestate run and +33% on a variant-heavy boot run, so dispatch changes must be measured on both. [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §12. |
| 2026-09-01 | **Framework synced; both submodules bumped; verified booting.** Merged upstream `mstan/master` into fork branch `fix/static-overlay-residency-signal` (`psxrecomp` `70153175`→`ecc0de16`, clean, 0 conflicts — upstream never touched our two files) and pushed it to `origin`. Bumped `recomp-ui` `8c30e004`→`4eda654` (required: merged psxrecomp uses the multi-disc launcher ABI). Upstream PR **held as draft** — fork is now a living integration branch. Full rebuild (emitters→generate→overlays→psx-runtime) verified: headless boot clean, overlays native at **~99.6% steady-state hit rate**, `gen_fastpath` ~96%, misses frozen post-load, `aborts` 0 — CD-ROM/DMA merge did not perturb the residency signal (`aa6fa2c9`). Two gotchas paid: regenerate `overlay_codegen_hash.h` (target `psxrecomp_codegen_hash`) BEFORE compiling overlays or the stale-recompiler guard fires; recomp-ui must move in lockstep with a psxrecomp master sync. Non-blocking: pre-merge `.pst` savestates load `last_ok: 0` (merge reworked `savestate.c`). [`HANDOFF.md`](HANDOFF.md) → "Shipping state". |
| 2026-09-01 | **Capcom-logo lag root-caused and FIXED.** The opening logo runs from `LOGO/LOGO.EXE` — a standalone 120 KB PS-EXE at `0x801CE000` (not an `.EMI` overlay), which the extraction pipeline never captured, so it ran 100% interpreted (~19 present-fps; `0x801CEEDC` = 91 M insns / 84.5% of interp). Headless is the trivial repro (Capcom is the first screen). Identified by decomposing the phase (interp 5M/s, native ≈0, `frame` counter for fps since the BIOS VSync counter freezes during the intro), reading live bytes (matched no `.EMI` occupant), and a 20-byte disc signature search (one hit → `LOGO/LOGO.EXE`, PS-EXE header t_addr=0x801CE000/t_size=0x1D800/entry=0x801CE724). Fixed by compiling it as a static overlay: new [`tools/extract_logo_overlay.py`](../tools/extract_logo_overlay.py) → `static-emi-v1` capture, merged into `overlay_captures_all.json` (+ `axis_b_loop.sh` phase 3a re-merge). **Result: `0x801CEEDC` native, Capcom interp 20× down (5.0M→0.25M/s), present fps 19→steady ~30, no regression.** ~30 is now pacing-limited (idle CPU; `CAPCOM30.STR` FMV/CD streaming), not CPU-limited. Pass-2 harvested the 10 jump-table interior entries (`analysis/logo_observed.json`). Compares to MMX4/5/6 which absorb their logo EXE automatically via the runtime-capture path (`overlay_cache=true`) we keep off. |
| 2026-09-01 | **Capcom FMV slowdown root-caused and fixed in the framework.** Host gdb stack sampling on a clean boot found ~40% of emu-thread time building `SpuGlobalState` snapshots just to read one SPUCNT bit on every device-service gate. Fix: cheap `spu_ctrl_read()` gate, identical semantics — upstream [mstan/psxrecomp#292](https://github.com/mstan/psxrecomp/pull/292). Measured headless clean boot: build-dbg 28.5→~52 vblank/s; RelWithDebInfo 97.6/s uncapped (~1.6× realtime). **User-verified windowed on `build-relprof`: Capcom logo, world map and memcard all hold 60 fps with clean audio.** Two wrong theses on the way (present-rate pacing; the interpreted BIOS IRQ handler) are recorded in [`vblank-pacing-bug.md`](vblank-pacing-bug.md). New tool `tools/fmv_bench.py`. |
| 2026-09-01 | **All psxrecomp PRs merged upstream; pin returned to `mstan/master`.** #289 (overlay dispatch trio), #290 (scanlines), #292 (SPU gate) merged; `psxrecomp` gitlink `ecc0de16` → **`1bf70960`** (upstream master, no fork commits). `recomp-ui` gitlink `4eda654` → `fda07fe` (fork `feat/present-scanlines`, pending [mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42)). Full regenerate (emitters → generate → codegen hash → all overlay bands + LOGO → `build-dbg` and `build-relprof`). Benign audit-failure count 6 → 7 (`0x801EEC00` +1), expected shape. Smoke-tested headless on `build-relprof`: FMV 206 vblank/s uncapped (`fmv_bench.py`), overlay dispatch 98.3% hits with `crc_misses` frozen post-load, ~300 emu fps at the title. Docs cleaned for staleness: STATUS/HANDOFF/INVENTORY rewritten, vblank doc restructured around the fix, README index refreshed. |
