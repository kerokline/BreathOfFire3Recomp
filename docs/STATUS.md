# Current state

**Status:** IN PROGRESS (last verified 2026-09-05)

> **2026-09-04 — mixed sections are extracted by default.** `extract_overlays.py`
> now takes `code` + `mixed` (405 sections, 184 of 200 AREA files) instead of
> `code` alone (338, 126 files); `--include-mixed` is accepted and ignored,
> `--no-mixed` is the A/B escape hatch, `axis_b_loop.sh` follows. Settles the
> open question from 2026-09-02 with the evidence it asked for: **58 of 200 AREA
> files ship no `code` section at all**, so their `mixed` section is their only
> compilable code (AREA000 MacNeil Village, AREA001/002 Dauna Mines) — excluded,
> those areas ran fully interpreted. All 67 mixed sections are section 13 of an
> AREA file loading to `0x801F2C00`, the WORLD band that is already a known
> interpreted sink. `mixed` turns out to be a classifier artifact: the sections
> are leaf-heavy and small, failing `emi_survey`'s absolute `prologues>=4` gate
> while passing density comfortably (WORLD04 AREA176-180: 34 `jr ra`, 3
> prologues). Cost of the old default was performance, not correctness — the
> interpreter ran them. Details: HANDOFF "Mixed sections are extracted by
> default".
>
> **2026-09-04 — the Axis B stop condition is now an estimate, not "0 new PCs".**
> [`tools/pc_coverage.py`](../tools/pc_coverage.py) reports estimated harvest
> coverage (Chao2 over per-session incidence), stratified `--by band` (default,
> with a static `jr ra` function-start ceiling per band) or `--by area` (named
> from `names/areas.toml`), so the report says *which* parts of the game are
> under-sampled instead of only whether the last session found anything.
> `harvest_interp_pcs.py` now writes the incidence it needs: a per-row
> `sessions` list (`--session`, default a timestamp) plus `areas` stamped on PCs
> newly seen in a pass (`--area`); `area_poller.py watch` passes its own session
> id so 15-minute re-harvests fold into one sampling unit, and stamps the
> resident area. It prints a coverage line after each harvest.
> **Not yet meaningful:** the accumulated 1 689 PCs (1 574 entered) are all
> legacy rows with no session id — Chao2 needs **two** sessions carrying ids, so
> the report says "not estimable yet" until two more play sessions land. Static
> ceiling for context: 9 705 distinct function starts across all `.EMI` sections
> + boot EXE. Rationale and how to read the output: HANDOFF "The stop
> condition". Host tooling only — no runtime, build, or submodule change.
>
> **2026-09-02 — static overlay compile is fast now (framework PR pending).**
> `axis_b_loop.sh` on build-dbg: ~16 min → **90 s** (phase 5a 12 min → 20 s via
> a process pool + a linear CPS resume-wrapper pass — cProfile showed 87 % of
> 5a was `add_cps_resume_case` re-scanning a 19 MB string 7,386 times; phase 5b
> 4 min → 69 s via one translation unit per overlay, 358 units, globbed by
> `runtime.cmake`; **build-relprof 1016 s → 162 s** for the same rebuild). Outputs
> byte-identical to the old path (diff -r), same
> shard summary, headless boot 99.92 % static hits. Lives in `psxrecomp` fork
> branch `perf/static-overlay-parallel` (`7ab698ca`, = upstream `04d9184b` +
> 1); PR mstan/psxrecomp#296 held as a **draft until play-tested more**; pin back to
> `mstan/master` when it merges. See HANDOFF "Shipping
> state". The harvest log is now kept (`analysis/harvest_last.log`,
> `harvest_sessions.log`).

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

**The game's data is readable off the disc (2026-09-05).** Items, abilities,
places and the roster are id→name sidecars in `names/` generated by
`tools/text_tables.py`; the save verifier proves them against the card saves
(ability list types, weapon ATK, armour DEF all match). The world-map place
names are painted plates in the map textures, decoded by `tools/plates.py`
and transcribed in `names/plates.toml`. [`TEXT_TABLES.md`](TEXT_TABLES.md).

**Framework pins: `psxrecomp` is plain upstream `mstan/master` again
(2026-09-05, `17f49ad3`).** Every psxrecomp change this title produced is
merged upstream — the static overlay residency signal, O(1) dispatch and
resident-occupant memo ([#289](https://github.com/mstan/psxrecomp/pull/289)),
present-time scanlines ([#290](https://github.com/mstan/psxrecomp/pull/290)),
the cheap SPUCNT gate ([#292](https://github.com/mstan/psxrecomp/pull/292)),
the parallel static overlay compile
([#296](https://github.com/mstan/psxrecomp/pull/296)), the controller
fast-forward shortcut ([#307](https://github.com/mstan/psxrecomp/pull/307)),
the GP0 polyline terminator fix
([#313](https://github.com/mstan/psxrecomp/pull/313)), the fast-forward toggle
([#318](https://github.com/mstan/psxrecomp/pull/318)) and the explicit keymap
unbind ([#319](https://github.com/mstan/psxrecomp/pull/319)/#320). No fork
branch carries anything the pin needs. `recomp-ui` stays at `db12620` (fork
`feat/additional-ui-functionality`: upstream `master` + the Scanlines toggle
[mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42) + the host-
shortcut Select labels [#48](https://github.com/mstan/recomp-ui/pull/48)) until
those merge. The only fork-side psxrecomp work not upstream is the
`PSX_HLE_INTRP_WALK` walk-HLE prototype (`d725af45` on
`fix/vblank-cadence-pacing`), kept for its proven callback-dispatch mechanics
and not needed by any current fix. **Build trees have not been rebuilt against
`17f49ad3` yet** — do that (emitters, codegen hash, overlays, runtime) before
measuring anything.

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
- **GPU polyline terminator fix** merged upstream
  ([mstan/psxrecomp#313](https://github.com/mstan/psxrecomp/pull/313)) and in
  the `17f49ad3` pin. Retest the icon-strip damage on the fixed build
  ([`battle-icon-strip-rows.md`](battle-icon-strip-rows.md)).
- **recomp-ui #42** (launcher Scanlines toggle) and **#48** (host-shortcut
  Select labels) awaiting upstream merge; the `recomp-ui` pin moves back to
  upstream master when both land.
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
   message-table lookup. Menus/items/name entry are a separate pool — the
   item / ability / place pools now have their id order and 8-byte field
   widths in `names/*.toml` ([`TEXT_TABLES.md`](TEXT_TABLES.md)).
4. **Name the text-engine functions in `symbols.toml`** and re-run
   `tools/sync_symbols.py`.
5. **Audit the 211 zero-fill dispatch addresses** (from 18 `low`-confidence
   seeds) before trusting native dispatch in that range.

## Known issues, non-blocking

- **Starvation watchdog `exit(2)`**, reported as `reason: atexit` /
  `exit_origin: "unknown"`. Debug-tree safety net, not a game fault. The
  2026-09-02 15:01 trip (`build-dbg`, frame 5524, Glauss Mountain) fired with a
  **402 µs-old heartbeat**: `starvation_watchdog_check` reads the clock before
  the shared timestamp, and the debug-server IO thread stamps that timestamp
  from `send_all_blocking`, so a send landing between the two reads wraps the
  unsigned subtraction. Upstream patch drafted in
  [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md)
  (read heartbeat first, atomic store/load, exit-origin label); **filed 2026-09-05
  as [mstan/psxrecomp#321](https://github.com/mstan/psxrecomp/pull/321)**.
  **Disabled on this machine for debug testing**: `PSX_STARVATION_TIMEOUT_US=0`
  is persisted as a user environment variable (`setx`), so launcher and shell
  runs of every build tree inherit it. Not a config-file key — the runtime reads
  only the env var. Re-enable with `setx PSX_STARVATION_TIMEOUT_US ""` if a
  genuine emu-thread stall needs the SIO ring dump.
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
| 2026-09-05 | **World-map place names are painted plates, now read out.** The user's check (AREA007's map label is マクニール村 in kanji; no such string anywhere on disc or in RAM) led to the texture: each world map's 256 KB page (`dest 0x0E001000`, 32×32-halfword tiles, 1024 8-bit texels wide, CLUTs from `0x8002BE00`) carries a strip of pre-painted name plates (14-row body, widths 44/60/76 texels, wrapping at texel 256). Proof: the AREA033 section matches `slot07`'s VRAM byte for byte, and the JP/US disc diff of every area's images is exactly the nine world maps + three fishing spots + the Pompom dock. `tools/plates.py` decodes the pages and finds the plates by their rim; `names/plates.toml` holds 85 plates / 42 names transcribed from the contact sheet, 39 with wiki English. Pixel budget for English: 3 / 4 / 5 glyph cells at the game font. The "blank plate + rendered text" idea is written up with its constraints. [`TEXT_TABLES.md`](TEXT_TABLES.md). |
| 2026-09-05 | **Name tables read straight from the `.EMI` (IDEAS I4 done).** `tools/text_tables.py extract` parses the fixed-stride record tables off the disc through the `.cue`: GAME.EMI holds **five item tables** (consumables 92 × 14 B at `0x801C995C`, key items 16 × 12 B, weapons 83 × 20 B, armour 68 × 18 B, accessories 52 × 16 B — the four inventory categories are four tables, which settles the category question) and the ability table (227 × 16 B at `0x801CB230`); MTEST.EMI the 200-entry debug place list; COMMU02 / START the roster and the new-game templates. Written to `names/items.toml`, `abilities.toml`, `places.toml`, `characters.toml` with the wiki glossary's English (spells/items ~95 %). **The MTEST index is the AREA number** (200 entries = AREA000..199, names agree), so `places.toml` joins each debug entry to its area script: the on-entry kanji banner (`caption`, 11 areas — グラウス山 user-confirmed on screen), the developers' message-0 label (`dev_label`, 81), and English through the wiki (caption → dev label → kana → a wāpuro-romaji fold of the wiki's romaji column) = 45 of 200, all checked by eye. The world-map scripts hold region names and spot descriptions, not a spot-name list; most interiors never display a name. `save_tool.py dump` now prints `薬草(Healing Herb) x28`; `verify` gained four cross-checks and all pass on every save: every id is a record, every learned ability sits in the list its table type (`b1 & 3`) selects, **weapon `power` = ATK bonus, armour `power` = DEF bonus** (Garr's Titan Belt +10 is an accessory effect code, reported unverified). Encoding: `0xFB` = ヴ, digits/capitals are raw ASCII in name fields, `0xFF` separates words. Also fixed a `save_tool.py` bug (a comment had eaten the `level` field; `dump` raised). Masters are a message block, not a table. [`TEXT_TABLES.md`](TEXT_TABLES.md). |
| 2026-09-05 | **Starvation-watchdog fix filed upstream (track F).** The 2026-09-02 false-trip patch went to [mstan/psxrecomp#321](https://github.com/mstan/psxrecomp/pull/321) from fork branch `fix/starvation-watchdog-wrap` (`430c93b8` off the pin): heartbeat read before the clock through a pure `starvation_watchdog_stale()` helper, `_Atomic` heartbeat, and exit-origin labels (`starvation_watchdog`, `console_close`, `console_ctrl_*`, `signal_sig*`) so these exits stop reading `atexit`/`unknown`; new ctest `starvation_watchdog_test`. Verified on `build-dbg`: 10 min with `area_poller.py` at 1 s and the watchdog **enabled** at 4 s — no trip (pre-fix ~2 min); forced 1 ms trip labels the report correctly. Gitlink unchanged at `17f49ad3` (bump when merged, then drop the `setx PSX_STARVATION_TIMEOUT_US=0` workaround). [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md). |
| 2026-09-05 | **`Battle_Init` to evidence (track B).** Body vs the `battlebegin.json` +563 write set: all 33 offsets explained — the effective-stat block `C+0x90..+0xAC` is snapshotted to `C+0xB0..+0xCC`, engine `Formation_ApplyStatMods` (`0x800A79AC`, keyed on the formation id `0x80144F54`) adjusts the scratch, and it is copied back; low-HP status `0x2000` (< max/4) set here; command/flag bytes zeroed; battle globals reset. `0x800A8AD4` = normal/boss split. [`BATTLE_RAM.md`](BATTLE_RAM.md) actor table. |
| 2026-09-05 | **Capcom intro sampled twice (track D); relprof verified on the pin.** Two fresh boots harvested during the FMV (`--session d_boot1/2 --area LOGO/LOGO.EXE`): 0 new entries and **0 interpreted PCs in the logo band** — it is fully native, and `pc_coverage.py` reports it NEVER SAMPLED only because the estimator has no rows there (8 sessions total now, est. 46 % overall). `build-relprof` was already current against `17f49ad3`; `fmv_bench.py`: 99.6 present/s, 38.6 k interp insns/s during the FMV (baseline ~97.6 uncapped), `build-dbg` 50.1/s (baseline 49–52). No pacing regression from the pin. |
| 2026-09-05 | **Skill and item commands captured.** `--hold up` / `--hold down` with three Circles per member: skill = command 4 with the id in `C+0x11A` (`SkillMenu_Open` / `SkillMenu_Confirm` / `Skill_TargetSetup`, default target from the skill table `0x801CB230`), item = 5 (`ItemMenu_Open` / `ItemMenu_Confirm`, count reserved at confirm by `ItemMenu_Reserve`); **`C+0x118` is the target actor** (`Attack_TargetSetup` too); `Actor_SkillItemDone` clears the byte and deducts the AP cost. Rei's steal, the vitamin heal (Nu save, Ryu 1 → 10) and the enemy specials all land through **`Effect_ApplyResult` `0x8009A160`** (engine; seeded into Ghidra from the gap's only prologue): a `jalr` effect table `0x800B165C` indexed per skill (`0x800B1438`) or per item (`0x800B164C`) fills a result record `0x8014639C` (+4 HP delta, +6 AP delta) that it applies with heal cap, ±9999 clamp, kill + survive check. 10 names (9 evidence). [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **The command menu, Run and the enemy AI live in the battle engine band.** The first venn was blind because the default `fn_filter` (`0x801D0C00-0x801F0000`) excludes `BATTLE.EMI#15` at `0x80093800`; recapturing the five commands with `--lo 0x80093800 --hi 0x801D0C00` and a 100-frame window (the engine band stamps ~1 700 entries/frame, so anything longer wraps) found them. Each actor carries a command byte `C+0x119` (1 Attack, 2 Defend, 0 Watch with `C+0x124 \|= 1`, 4 skill, 5 item) written by `Cmd_ConfirmAttack` `0x80093E14` / `Cmd_ConfirmWatch` `0x8009521C` (engine) or the Defend table target; Auto sets `0x801462E4 \|= 0x10` and `AutoBattle_FillCommands` writes 1 to all three, refilled every round by `Battle_RoundStart`; `Battle_CommitRound` builds the order, consumes items and calls the engine's **`EnemyAI_ChooseActions`** (8-row scripts at `0x800E407C + (rec+0x60)*0x88`, condition opcodes + action types, once-only bits at obj `+0xE1`). **Run**: `Escape_Roll` `0x80098278` — 3rd attempt or preemptive = certain, else `Escape_Chance(mean party AGI − mean enemy AGI)` from `0x800B1430` `{32..52}/64` (+8 second try, +8 status `0x2000`, cap 64) vs `Rand & 63`; success → `Escape_Begin`, fade, mode 5/3; failure → `Escape_Failed` rebuilds the order without the party. 19 more names (13 evidence). Still open: Defend confirm body (Ghidra gap), Defend flag `0x80`, skill/item captures, AI row semantics. [`BATTLE_RAM.md`](BATTLE_RAM.md) "Commands, Auto, Run and the enemy AI". |
| 2026-09-05 | **Battle commands, turn order, kills, drops and the results tally (track C).** Five command captures from `slot03` (Attack, Defend, Watch, Auto, Run ×3 — every Run succeeded), one Nu round, and a victory capture paged through the results with `--press-gap 150`. The five-way venn has **no command-specific compiled code** (0 auto-only, 0 defend-only; watch-only = two Examine state entries; run-only = the escape exit), so the decision points are in shared or still-interpreted code. What the captures + Ghidra did give: `Battle_BuildTurnOrder` `0x801DAAB4` (party **AGI `+0x24`** + command bonus × level-class pct, enemy **AGI `+0x28`** + random byte; list at `0x80146308`, cursor `0x8014631E` consumed by `Battle_BeginAction`), `Battle_EnemyDefeated` `0x801E542C` (enemy **`+0x04` zenny, `+0x06` EXP, `+0x08` = level**), `Battle_RollDrops` `0x801E525C` (drop slots `+0x18/+0x1A`, `+0x1C/+0x1E`; `Rand & 0xFF <= {0,0,1,3,7,31,127,255}[class]`; list `0x80146330`/`0x80146350`/count `0x80146323`), and BATL_END's `BattleResult_Setup` (`Char_LevelUp` caller, zenny ×1.5 condition, tick step = max(1, total/30)) / `_ExpTick` / `_ZennyTick` / `_AwardDrops` (the `Inventory_Add` caller — body only, no drop landed at 1.6 %). Banner pool `0x801EB460` + slide states named. Enemy skill damage is applied by engine `0x8009A3E4`, not `Battle_ApplyDamage`. 30 names (17 evidence), BATTLE_EMI3 (663 fn) / BATL_END (109) / BATTLE_EMI15 re-imported. Interpreted PCs harvested (6 sessions, est. 50.8 % coverage; BATL_END runs almost entirely interpreted). Traps: ring wrap keeps the newest 262 144 entries; `slot03` is the first member's menu. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Damage formula read end to end; a Ghidra blind spot fixed.** `Battle_BaseDamage` = max(0, ATK − DEF) (enemy attackers: DEF = (party mean DEF + target DEF)/2, plus `enemy+0x08 × (2..3)/10`), + `Rand&1`, then `Battle_ScaleDamage`: ×205/256, × an 8-entry 0.85..1.20 table, × elemental affinity (`0x8009FA78`, unread) and × a type table under weapon flags. The "defence steps" are **to-hit rolls** (`Battle_HitCheck_PartyTarget` vs target evade % `rec+0x37`, `_EnemyTarget` vs attacker hit % `rec+0x38`). ATK/DEF are persistent `+0x20`/`+0x22` (enemy `+0x24`/`+0x26`), copied per action to `0x801EC278` (actor) / `0x801EC258` (target) by `Battle_BeginAction` / `Battle_ResolveAction_*`. One `slot03` round reproduces all four hits exactly (31 / 13 / 6 / 1). Rei = roster 4. **Tooling:** every overlay decompile had been silently cut at the first boot-EXE call because `Rand` is a BIOS thunk (`jr` to `0xA0`) Ghidra flagged no-return; `seed_overlay.py` now maps the boot EXE into each overlay program and makes the 55 thunks returning ([`GHIDRA.md`](GHIDRA.md) Traps). 8 names written (5 evidence, 3 hypothesis). [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **`psxrecomp` re-pinned to plain upstream `master` `17f49ad3`.** Upstream merged everything the fork carried (#296 parallel compile, #307 fast-forward pad, #313 polyline terminator, #318 fast-forward toggle, #319/#320 keymap explicit unbind); `3b8b98fa` → `17f49ad3` is fast-forward with no fork-only commits left behind. `recomp-ui` unchanged at `db12620` (#42 + #48 still open). Rebuild pending. |
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
| 2026-09-05 | **Save format decoded.** `capture --watch 0x800C1800-0x800C2B00` during a save: the card module builds the title frame + three icon frames (`Card_BuildTitleFrame`, `Card_CopyIconFrame0..2`, file `0x000..0x1FF`), then SHOP.EMI **`Save_BuildImage` `0x801D69F0`** copies **one contiguous `0x10B0`-byte game block `0x801448D4..0x80145984`** (character records, zenny, party, inventory, key items, abilities, a summary block) byte-by-byte to file `+0x200`, summing into a u16 checksum at `+0x270`; boot `0x8015BFC4` copies one progress-flag bit into the summary (it is `Flag_Test`, not a hash — corrected 2026-09-05 by the save tool; it was named `Save_FlagsChecksum` here for a few hours). Slot list reads file `0xE80..0xEFF`. SHOP.EMI#0 promoted to `evidence` as the shop/inn/save game-mode. Sidecar: 23 evidence / 23 hypothesis, 13 boot symbols. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Save path found: BIOS file API, 0x1300-byte image staged at `0x800C1800`.** Two dead ends paid for (a party-block `ramdiff` sees nothing because a same-state save rewrites identical bytes; a boot-EXE fn filter wraps the ring in ~160 frames, and the libcard range is flooded by the `TestEvent` wait loop). A fn capture on the file-API wrappers alone caught the whole sequence: `firstfile`/`nextfile`, per-slot `open`/`lseek 0xE80`/`read 0x80 → 0x800C2680`/`close`, then `open(mode 2)`/`lseek 0`/**`write(fd, 0x800C1800, 0x1300)`**/`close`. The caller is a **memory-card manager module** (5 KB section shipped identically in SHOP.EMI and START.EMI, resident at `0x801EEC00`; promoted to `evidence`): seven `Card_*` functions named with evidence. Tracer: forest builder made linear (bounded indexed open stack; a boot-EXE capture used to hang for minutes), drain progress line, both swap slots always identified. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Equipment slots and the equip routine.** Same-weapon re-equip showed only `Char_RecalcStats` (+8 Pwr from the weapon, +1/+5 Def from armour, max HP halved by the `+0x1A` step); `ramdiff --width 1` on a real swap found record **`+0x0E` = equipped weapon id** (28→3) with the weapon leaving inventory category 1; `capture --watch` on the swap back named **`Menu_EquipConfirm`** (START.EMI `0x801D6D94`, evidence): for each of **six equipment slots `+0x0E..+0x13`** whose pending choice differs, boot `Inventory_Remove` (`0x80166F30`, new symbol) then `Inventory_Add`, store the id, then `Char_RecalcStats`. Slot→category table at START `0x801EC3E8` = [1, 2, 2, 2, 3, 3]. START.EMI (field menu) promoted to `evidence` and imported into Ghidra (623 fn). [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Shop purchase → inventory arrays found.** `capture --watch` on zenny during four buys: SHOP.EMI subtracts zenny inline (`0x801D1E9C`, price × qty) and `jal`s boot **`Inventory_Add(category, id, count)` `0x80165AA4`**, whose pointer tables (`0x801C9934`/`0x801C9948` in GAME.EMI data) give the inventory: 4 categories × 128 ids at `0x80145048..` and counts at `0x80145248..` (cap 99), plus an id-only list at `0x80145448`. `Zenny_Sub` `0x80166FCC` named. SHOP.EMI (both sections) imported into Ghidra. Two tool fixes paid for: seeded functions are now created in descending address order (a lower start was swallowing a higher one), and write attribution only uses starts of overlays **resident at capture time** (a BATTLE.EMI start had been credited for a SHOP.EMI store in the shared band). [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Full-battle context trace: the party actor object mapped.** `capture --watch 0x80145E8C-0x80145FCC` over a whole battle (3600 frames, 22 114 writes, 43 writers, ring not wrapped) attributed every field of the 0x140-byte party actor `C` to its writers across field, transition and battle: boot sprite code (`Actor_Task` +0, `Actor_UpdateScreenPos` +0x2E/+0x30/+0x32/+0x60 every frame, `Actor_AnimTick` +0x4A/+0x58/+0x5A), GAME.EMI field motion (+0x9, +0xC..+0x14, +0x34/+0x38 world x/z, +0x3E depth), `Encounter_PlaceParty` (+355, positions from the table at `0x80143F2C`), `Battle_InitPartyContexts` (+409), `Battle_Init` + **`Battle_InitMemberActor`** (+563), `Battle_ApplyDamage`, `Battle_WriteBackMember` (+1749) then **`Battle_ReloadPartyRecords`** (+1769, persistent → working `memcpy` for every slot, the reverse of the write-back). Three new evidence names, three boot `guessed` symbols, full offset table in [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Battle start: the working record is a copy of the persistent one.** `capture --watch 0x80145F0C` across a battle transition caught three writers: GAME.EMI `0x801C253C` once at +481, game-mode `0x801D1490` once at +635, then `0x801E9B74` every ~2 frames. The first is **`Battle_InitPartyContexts(formation)` `0x801C23F8`** (evidence): per slot it builds a context `C = 0x80145E8C + slot*0x140` (present flag, slot, roster byte at `C+0x13C`) and `memcpy`s `0xA8` bytes of the persistent record into `C+0x74 = 0x80145F00 + slot*0x140` — so every persistent offset applies to the working record, and `0x1F800044` / `0x8014624C` are pointers to `C`. Party composition `0x80144F56 + slot + formation*3`, size `0x80146250`, char-id→roster table `0x80182488`. Hypotheses: `Battle_Init` `0x801D1228` (the first game-mode write, 1428 B setup), `Battle_MemberStatusTick`, `Battle_InitPartyMember`. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Level-up decoded end to end; persistent character records proven.** `capture --watch 0x80144B40-0x80144C10` on Teepo's L3→4 (user) caught the whole burst at one frame: six base-stat writes (+4,+4,+2,+2,+1,+4 at rec `+0x3C..+0x46`) and the level byte (`+6`) from `GAME.EMI` code, then boot `Char_RecalcStats` (`0x80165434`, whose body compares against `&0x80144964 + n*0xA4`, n<8 — the record base and stride are now code-proven), `Stat_AddClamped` (`0x80165EE4`, 0..999) from the equipment pass, and `AbilityList_Add` (`0x80165BCC`) storing skill `0x5E` at `+0x71`. `GAME.EMI` (`0x80196800`, 227 KB) imported into Ghidra (582 fn, all decompiled): **`Char_LevelUp(roster)` `0x801AEDD4`** walks a per-roster **level table at `0x801CC068 + roster*0x318 + level*8`** (u16 EXP-to-next, growth bytes hp/ap/pwr|def/agl|int, two skill ids) plus signed Master modifiers at rec `+0x85..+0x8A`. Decoding the table from the disc reproduces Teepo's observed growth byte-for-byte and gives cumulative thresholds 10/30/60/105/173/275 for Ryu — the community chart (10/25/62/155) is wrong for this disc; the 105 seen on screen is right. Also caught: end-of-battle `Battle_WriteBackMember`/`Battle_WriteBackParty` (working HP/AP/status → record), and `0x80145FC8` is the roster index, not an actor state. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-05 | **Save-file verifier (remote plan track E).** `tools/save_tool.py` reads raw 128 KiB card images (`.mcd`/`.mcr`): `list`, `dump SLOT`, `verify`, `diff A B`. On `saves/card1.mcd` the u16 byte-sum verifies on all three saves, and every load-screen field cross-checks against the block it came from (name bytes, party ids with the Peco rule, level, play time, EXP, flag bit; the SJIS title's hours/minutes/level too). Independent oracle: Mednafen booted from the same card and its load screen showed リュウ Lv 1 at 00:28 / 05:13 / 05:10 with one portrait for file 1 and Teepo / Rei / Ryu for files 2 and 3 — exactly the tool's output (`analysis/mednafen_loadscreen_card1.png`). `diff 2 3` on the user's "identical except time" pair: only the checksum and the play time differ (two runs). Three RAM-map corrections fell out: **`0x8015BFC4` is `Flag_Test`** (bit `0x92` → summary byte, not a hash); **play time is `0x80144FBC` as h/m/s/frame bytes** (the `0x8014686C..` words copied to the block head are something else); and the ability list is **four 10-slot lists at record `+0x5C/+0x66/+0x70/+0x7A`** chosen by ability type (`AbilityList_ForType` `0x80167514`), not one list at `+0x71`. Bonus: the record names give the **whole roster order** — 0 リュウ, 1 ニーナ, 2 ガーランド, 3 ティーポ, 4 レイ, 5 モモ, 6 ペコロス, 7 パピー (char id 10) — the intro's baby dragon (user), proven live from `slot01` the same afternoon: party id `0x0A`, roster byte 7 throughout, `Battle_WriteBackMember` wrote HP 11→7 into record 7 at the intro-boss end (`papi_intro.json`). Char-id→roster table `0x80182488`: 7→0, 8→1, 9→0 (save 1's lone boy Ryu), 10→7, 14→4. Mednafen trap: the title cursor defaults to LOAD GAME and the name-entry screen cannot be cancelled — restart. [`BATTLE_RAM.md`](BATTLE_RAM.md), [`remote-plan-2026-09-05.md`](remote-plan-2026-09-05.md). |
| 2026-09-05 | **Name tables located in the `.EMI` (staged as IDEAS I4).** Searching the overlays for one known name in the in-game encoding (薬草 = `13 1a 12 8b`) found fixed-stride record tables instead of loose strings: **items** at GAME.EMI `0x801C995C` (14-byte `name[8] flags type 0x40 price`; ids 0 なし 1 あおりんご 2 パン 3 薬草 match the saves and the shop's −20/buy), **abilities** at `0x801CB230` (16-byte, the table `AbilityList_ForType` reads — its address was mis-read as `0x801DB231` earlier today and is corrected; Teepo's 0x5B/0x5E/0x67 = パダーマ/レイギル/ドメガ, Momo's 0x46/0x4B = アプリフ/リバル), the **new-game character templates** in START.EMI at `0x801EB4A4` (8 × 0xA4, byte-identical to the saves' untouched records — the record format readable statically), **character names** in COMMU02.EMI (roster order 0..6 again), **place names** in MTEST.EMI and the **masters** list in FIRST.EMI. Nothing built yet; plan and acceptance test in [`IDEAS.md`](IDEAS.md) I4. Also today: パピー (record 7) proven to be the intro's baby dragon (see the track-E row). |
| 2026-09-04 | **Zenny, the lifetime-earned total, and the results overlay.** `ramdiff` (+40 read off the results screen, two rounds) → `capture --watch 0x80144F4C --watch 0x8014502C`: a 1000-frame window saw 0 writes, 1200 saw 80 (+1 ×40 into each) — the results screen's start drifts, so `--window-frames` needs headroom; `capture` now compares watched bytes at arm vs end and warns when a cell changed with no traced write. Writer is boot `Zenny_Add(amount, skip_total)` `0x80166FFC` (zenny `0x80144F4C` cap 9,999,999; lifetime total `0x8014502C` unless skip), called from `0x801EF824`/`0x801EF848` in **`BATL_END.EMI`, resident at `0x801EEC00` during the tally** → overlay promoted to `evidence`, imported into Ghidra (94 fn). EXP row confirmed by a second battle (user): `0x8014496C` = Ryu, `0x80144B58` = Teepo (roster 3) → `BattleResult_AddExp` back to `evidence`. `symbols.toml`: `Rand`, `Zenny_Add`. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-04 | **EXP and the persistent character records.** A kill anchor + `ramdiff` (+12 read off the results screen) + `capture --watch` found the EXP tick: +1 every 2 frames ×12 into `0x8014496C` (roster 0) and `0x80144B58` (roster 3) → **persistent character records `0x8014496C + roster*0xA4`** (EXP u32, cap 9,999,999; status-screen boot code reads `0x80144964..7C`). The store PC `0x801DD644` lay in a gap no static root or trace covered, and the writer had been misattributed to a boot-EXE start sharing the address; fixed the rule (overlay-band stores attribute to overlay starts only), added `ghidra_run.py import --start` to seed such gaps, decompiled it: `BattleResult_AddExp(amount)` `0x801DD564` + `BattleResult_MemberEligible` / `CharId_ToRosterIndex` (working record `+0x-7` = character id). "Next level" is threshold − EXP (65→77 with 40→28 ⇒ threshold 105). Import now also seeds every traced entry PC (449 starts vs 239; 495 Ghidra functions in the game-mode overlay). Two false positives paid for: `0x800E7CF0` was a CD-ROM DMA buffer (`dma_ch 3`), and long `ramdiff` windows net out later hits (heal +5 then −4) so party HP `0x80145F14` only matched on some rounds. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-04 | **First battle data anchors landed: enemy HP, the damage path, the HUD.** User ran `ramdiff` on an Attack anchor (damage read off the screen afterwards) → two cells per enemy; `capture --watch` on both showed the same-frame order (working HP `0x801EB74C` written by `0x801DBB40`, then HUD copy `0x801484CC` by `0x801EA204`); the Ghidra bodies gave the record layouts: **enemy working records `0x801EB634 + n*0x118`** (game-mode overlay), **party working records `0x80145F0C + m*0x140`** (boot data, HP `+8`, max `+0x10`), **HUD gauge records `0x801484B8 + n*0x24`** (gauge = hp*55/max). Named with evidence: `Battle_ApplyDamage(attacker,target)`, `Battle_CalcDamage(attacker,target,flags)` (weapon-vs-family doubling, status floors, variance `{50,50,50,50,60,60,60,70}%` via boot `Rand` `0x8017ED4C` mod 8 from the table at `0x801D0C7C`, defend/back-row cuts, 9999 cap), `Battle_BaseDamage`, `HUD_GaugeUpdate`; hypotheses for the two defence steps and `HUD_GaugesTick`; `Rand` into `symbols.toml`. Game-mode overlay header = count word + 24-pointer entry vector (`0x801D0C04` is slot 0). `ramdiff` keeps both snapshots and `ramfilter --intersect FILE=n,n,n` crosses rounds. [`BATTLE_RAM.md`](BATTLE_RAM.md). |
| 2026-09-04 | **Ghidra second route stood up headless; tracer grew data anchors.** `tools/ghidra_run.py` (+ `tools/ghidra/`) drives AnalyzeHeadless through `pyghidra.ghidra_launch` (in-process `pyghidra.start()` recurses on this machine): boot EXE exported (1025 fn, 52 GTE, 77 jump tables), `BATTLE.EMI#3` @ `0x801D0C00` (302 fn) and `#15` @ `0x80093800` (347 fn) imported as their own programs, seeded from the recompiler's roots. Reads: game-mode entry is `base+4` (`0x801D0C04` from boot `0x8014EB20`; WORLD `0x801F2C04` from `0x801532A0`); the battle context pointer lives in scratchpad `0x1F800044` (105 game-mode + 48 engine functions); the three traced roots are table dispatchers on that context; `BattleMenu_TargetCursor(x,y)` and `Battle_FrameTask` promoted to `evidence`; 4 of 12 traced PCs are interior stamps of larger Ghidra functions; `0x801EF188` was in MAGIC069, not BATTLE (row fixed). Tracer: `capture --watch` (runtime write trace, writers attributed by store PC), `writes`, `ramdiff` (find a RAM cell by its delta, no RAM map needed), `name` (single-row upsert); `names/functions.toml` `[[function]]` key now read by both tools (12 rows were invisible to `name_map.py`). [`GHIDRA.md`](GHIDRA.md). |
| 2026-09-04 | **I1 tracer live-tested.** `tools/callstack_diff.py` captured Attack (Circle ×6) vs Defend (`--hold right`, Circle ×3) from a battle-menu anchor (file slot 10): 13 Attack-only / 4 Defend-only / 185 common functions; the Attack-only cluster is the highlighted-icon draw, the per-member pattern (`0x801DB4EC` actor 0/1/2 per frame) is common. Tool fixes paid for: KSEG0 filter form (physical caught 0 entries), `ra`-based nesting (ring `depth` is junk on direct stamps, no exits), sequential presses + `--hold` (the command menu is hold-direction), common-prefix unusable across runs. Then a 900-frame three-way run (Attack / Defend / Watch) with the new `venn` subcommand: 22 attack-only, 11 defend-only, 24 attack+watch (= target selection, correcting the first reading), 0 watch-only; six `hypothesis` names written to `names/functions.toml` for the Battle game-mode overlay (`Battle_FrameTask`, `Attack_Action`, `Defend_Action`, …); `capture` now resolves the resident overlay per band by RAM-prefix match. Two Watch-trigger captures (file slot 11, different enemies) intersect to 12 Examine-only functions (question mark, observed skill, learn check) → six more `Examine_*` hypotheses; Watch's code runs only when an enemy move happens while armed. Details: [`IDEAS.md`](IDEAS.md) I1. |
| 2026-09-04 | **I2 live-tested → HIGH.** The world map is an area (AREA016) whose script block holds the region/node labels and the guide paragraphs (slots 5–16); a guide open is the WORLD-band caller `0x801F2E6C` → boot-EXE message resolver `0x8015034C(idx)` writing `0x801490A8` (observed idx 7 = Mt. Glaus), and entering it loaded AREA023. The aligned corpus already has slot-for-slot English. Write trace on `0x801490A0–C0` is the instrument; `fn_filter` on the immediate draw caught nothing. `tools/callstack_diff.py` (I1) written by subagent, live-tested read-only, battle differential still owed. Details: [`IDEAS.md`](IDEAS.md). |
| 2026-09-04 | **Ideas intake opened** — [`IDEAS.md`](IDEAS.md) catalogs three proposals with feasibility: I1 combat call-stack mapping (HIGH: the runtime's `fn_entry`/`fn_exit` rings already record `ra`/args/depth/`v0`; tool not written), I2 programmatic area labels from map text via the same ring + `decode_text.py` (MEDIUM: which pool holds the labels is the one unknown), I3 1.5x dialogue box + furigana (readings sidecar HIGH from the `D:\BoFIII` Sudachi work; box geometry MEDIUM pending the frame-draw function; runtime rendering LOW — needs an upstream hook, enhancement-phase). Premise corrected: line/page breaks are authored `0x01`/`0x0B`, not auto-wrapped. |
| 2026-09-01 | **Framework synced; both submodules bumped; verified booting.** Merged upstream `mstan/master` into fork branch `fix/static-overlay-residency-signal` (`psxrecomp` `70153175`→`ecc0de16`, clean, 0 conflicts — upstream never touched our two files) and pushed it to `origin`. Bumped `recomp-ui` `8c30e004`→`4eda654` (required: merged psxrecomp uses the multi-disc launcher ABI). Upstream PR **held as draft** — fork is now a living integration branch. Full rebuild (emitters→generate→overlays→psx-runtime) verified: headless boot clean, overlays native at **~99.6% steady-state hit rate**, `gen_fastpath` ~96%, misses frozen post-load, `aborts` 0 — CD-ROM/DMA merge did not perturb the residency signal (`aa6fa2c9`). Two gotchas paid: regenerate `overlay_codegen_hash.h` (target `psxrecomp_codegen_hash`) BEFORE compiling overlays or the stale-recompiler guard fires; recomp-ui must move in lockstep with a psxrecomp master sync. Non-blocking: pre-merge `.pst` savestates load `last_ok: 0` (merge reworked `savestate.c`). [`HANDOFF.md`](HANDOFF.md) → "Shipping state". |
| 2026-09-01 | **Capcom-logo lag root-caused and FIXED.** The opening logo runs from `LOGO/LOGO.EXE` — a standalone 120 KB PS-EXE at `0x801CE000` (not an `.EMI` overlay), which the extraction pipeline never captured, so it ran 100% interpreted (~19 present-fps; `0x801CEEDC` = 91 M insns / 84.5% of interp). Headless is the trivial repro (Capcom is the first screen). Identified by decomposing the phase (interp 5M/s, native ≈0, `frame` counter for fps since the BIOS VSync counter freezes during the intro), reading live bytes (matched no `.EMI` occupant), and a 20-byte disc signature search (one hit → `LOGO/LOGO.EXE`, PS-EXE header t_addr=0x801CE000/t_size=0x1D800/entry=0x801CE724). Fixed by compiling it as a static overlay: new [`tools/extract_logo_overlay.py`](../tools/extract_logo_overlay.py) → `static-emi-v1` capture, merged into `overlay_captures_all.json` (+ `axis_b_loop.sh` phase 3a re-merge). **Result: `0x801CEEDC` native, Capcom interp 20× down (5.0M→0.25M/s), present fps 19→steady ~30, no regression.** ~30 is now pacing-limited (idle CPU; `CAPCOM30.STR` FMV/CD streaming), not CPU-limited. Pass-2 harvested the 10 jump-table interior entries (`analysis/logo_observed.json`). Compares to MMX4/5/6 which absorb their logo EXE automatically via the runtime-capture path (`overlay_cache=true`) we keep off. |
| 2026-09-01 | **Capcom FMV slowdown root-caused and fixed in the framework.** Host gdb stack sampling on a clean boot found ~40% of emu-thread time building `SpuGlobalState` snapshots just to read one SPUCNT bit on every device-service gate. Fix: cheap `spu_ctrl_read()` gate, identical semantics — upstream [mstan/psxrecomp#292](https://github.com/mstan/psxrecomp/pull/292). Measured headless clean boot: build-dbg 28.5→~52 vblank/s; RelWithDebInfo 97.6/s uncapped (~1.6× realtime). **User-verified windowed on `build-relprof`: Capcom logo, world map and memcard all hold 60 fps with clean audio.** Two wrong theses on the way (present-rate pacing; the interpreted BIOS IRQ handler) are recorded in [`vblank-pacing-bug.md`](vblank-pacing-bug.md). New tool `tools/fmv_bench.py`. |
| 2026-09-01 | **All psxrecomp PRs merged upstream; pin returned to `mstan/master`.** #289 (overlay dispatch trio), #290 (scanlines), #292 (SPU gate) merged; `psxrecomp` gitlink `ecc0de16` → **`1bf70960`** (upstream master, no fork commits). `recomp-ui` gitlink `4eda654` → `fda07fe` (fork `feat/present-scanlines`, pending [mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42)). Full regenerate (emitters → generate → codegen hash → all overlay bands + LOGO → `build-dbg` and `build-relprof`). Benign audit-failure count 6 → 7 (`0x801EEC00` +1), expected shape. Smoke-tested headless on `build-relprof`: FMV 206 vblank/s uncapped (`fmv_bench.py`), overlay dispatch 98.3% hits with `crc_misses` frozen post-load, ~300 emu fps at the title. Docs cleaned for staleness: STATUS/HANDOFF/INVENTORY rewritten, vblank doc restructured around the fix, README index refreshed. |
| 2026-09-02 | **Gamepad input dead in-game: root-caused, fixed in `game.toml`.** The launcher recognised an Xbox Series X pad and wrote its GUID to `settings.toml`, but recomp-ui's `apply_default_pad_mode_for_source` sets every gamepad seat to **Analog** (poll id `0x73`), overriding the title's `default_mode = "digital"`. SLPS-00990 predates the DualShock and its pad reader ignores a `0x73` pad. Verified by A/B on the world-map savestate (`slot07`, headless `build-dbg`): with `p1_mode = "digital"` an injected Start opens the camp menu; with `"analog"` the screen never changes. Fix: `[controller] lock_mode = true` (the framework's digital-only-title key, as used for X4 / Tomba 2) — the launcher hides the selector and the runtime clamps a stale `settings.toml` mode. Keyboard was unaffected because keyboard seats are always digital. |
| 2026-09-02 | **Two battle rendering reports triaged.** (1) Enlarged command icon missing its top quarter: renderer is faithful (CPU mirror == GL FBO); the strip texture at VRAM (256..297, 480..503) has rows 480..485 zeroed, blocks 0-1 of `FIRST.EMI` section 6 lost exactly their first 384 bytes once at boot, Beetle savestate VRAM has all rows, so this is a runtime defect; the stage (CD read vs upload) awaits a watched relaunch. [`battle-icon-strip-rows.md`](battle-icon-strip-rows.md). (2) Rei drawn behind the house door during attacks: list order honoured; Beetle also phases attackers behind the door, so game behaviour. [`battle-depth-order.md`](battle-depth-order.md). |
| 2026-09-02 | **Build-dbg "hard crash" root-caused to a false starvation-watchdog trip.** No Windows crash record; `build-dbg/psx_last_run_report.json` (reason `atexit`, exit_origin `unknown`) has `starvation_watchdog_check → exit(2)` on its native stack, while `starvation_dump.jsonl` shows the heartbeat only 402 µs stale and the heartbeat ring shows 60 fps to the last sample. Cause: cross-thread read race in the watchdog (IO-thread heartbeat newer than the pre-read clock → unsigned wrap). Watchdog disabled machine-wide for debug testing via persisted `PSX_STARVATION_TIMEOUT_US=0`; upstream patch (read order + exit-origin label) to follow. Known-issues entry updated. |
| 2026-09-02 | **Second build-dbg exit of the day was a Windows Terminal crash, and it cost a 74-minute session's overlay harvest.** `WindowsTerminal.exe` faulted at 16:31:11 (`Windows.UI.Xaml.dll`, `0xc000027b`, first such event in 14 days); the game — a console-subsystem exe attached to that console — wrote `psx_last_run_report.json` four seconds later at frame 264564 with `reason: atexit` / `exit_origin: unknown` and no starvation dump (the persisted env var held). The runtime's `CTRL_CLOSE_EVENT` handler calls `exit(0)` without setting an origin — third unlabelled exit site, added to [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md). The interp-PC rings live only in the process, so that session's PCs are gone (area timeline survived). **Mitigation landed:** `area_poller.py watch` now calls `harvest_interp_pcs.harvest()` every 15 min and on Ctrl-C (`--harvest-every`), with an atomic temp+replace write of the observed file; `harvest_interp_pcs.py` refactored around that function (CLI unchanged). Unit-tested against a fake server. Launch tip: run the game under `conhost.exe …` so a Terminal crash cannot reach it. |
| 2026-09-02 | **Fast-forward gets a controller host shortcut.** Turbo was keyboard-only (`[KeyMap] Turbo`, Tab). psxrecomp `feat/fast-forward-pad` (`2ae78109`, off upstream `22fbbfca`): third assist binding `Fast-forward`, default chord Select+L1 (`1528`), same `hotkey_pad_binding_down()` matcher as Rewind / Save states, threaded through every settings hop and persisted as `[hotkeys] fast_forward_pad`; guard test extended, README documents the chord. recomp-ui `feat/fast-forward-pad` (`6c7cd32`, off upstream `d8187a4`): the Controller page's Host Shortcuts grid drew only two actions, now every one the runtime advertises. Both cherry-picked onto local integration branches `bof3/int-fast-forward` (psxrecomp `adf54eaa`, recomp-ui `b4c8f51`) and the gitlinks moved there; syntax-checked against the real build flags, then both `build-relprof` and `build-dbg` rebuilt clean (ninja rc 0, 2026-09-02 20:15) with the new strings in the exe; not yet play-tested. Runtime PR opened: [mstan/psxrecomp#307](https://github.com/mstan/psxrecomp/pull/307); launcher PR [mstan/recomp-ui#47](https://github.com/mstan/recomp-ui/pull/47) conflicted on arrival: upstream #46 (`42c2870`) had already replaced the two-row grid with a three-column table over every binding, so #47 is redundant — close it; the local cherry-pick stays only until the pin returns to upstream master. |
| 2026-09-02 | **recomp-ui pin moved to #42 + current upstream master.** New integration branch `bof3/int-scanlines-master` (`a736d57`) = `fda07fe` with `origin/master` `da80dc7` merged; one conflict in `recomp_launcher.h` where #42 and #46 both appended struct fields, resolved upstream-first (`virtual_stylus` before `scanlines`). Brings the NDS stylus work and the rewritten three-column Host Shortcuts grid, so Fast-forward shows on the Controller page without #47. Both `build-relprof` and `build-dbg` rebuilt clean (ninja rc 0, 2026-09-02 ~20:45); not yet play-tested. |
| 2026-09-03 | **Mednafen oracle wired up.** Stock Mednafen 1.32.1 (Beetle's parent) in `./mednafen/` (gitignored) loads our disc and, since memcards are the same raw 128 KiB image on both sides, boots straight from `saves/card1.mcd` copied to its name; savestates do not cross. No scripting surface exists (`-remote` is a bare flag), so `tools/mednafen_ctl.py` injects scancodes from its own cfg bindings, guarded by a foreground-window check. Verified end to end: Start/Down/Circle reached the load screen listing all three saves, savestate slot round-trip, snapshot, clean quit. Traps: `MEDNAFEN_HOME`, Circle confirms on the JP release. [`MEDNAFEN.md`](MEDNAFEN.md). |
| 2026-09-03 | **Ground plane vanishing after the herb effect: root-caused and fixed in the framework.** Player report with savestates (`slot04` reproduces ~35 frames after load). GP0 ring showed the terrain quads still drawn but the 8bpp texture page at VRAM (448,256) zeroed; `.pst` diff proved the file intact, so the wipe was emulated execution; a frame-exact trace found a stray 341×341 FILL that was really a colour word of a gouraud polyline: our GP0 parser tested **every** streamed word for the `0x50005000` terminator and a Psy-Q junk-top-byte colour `0x52545454` matched, de-phasing the stream. Both oracles (Beetle `INCMD_PLINE`, DuckStation `HandleRenderPolyLineCommand`) skip the first two vertices and test only the first word of each vertex unit. Fixed in `psxrecomp` fork branch `fix/gpu-polyline-terminator` `402cada6` (off `master` `d08d84a3`, savestate-size neutral); `build-relprof` rebuilt and verified (page intact over 6000+ frames, terrain renders). Upstream PR [mstan/psxrecomp#313](https://github.com/mstan/psxrecomp/pull/313) opened by the user; `build-dbg` rebuilt and verified the same day. New `tools/pst_tool.py` parses savestates offline. [`gpu-polyline-terminator.md`](gpu-polyline-terminator.md). |
| 2026-09-02 | **`tools/run_dbg.cmd` added** after a hand-typed `conhost.exe …` launch of build-dbg died at startup (report: `frame 0`, no guest code run, `reason: atexit`) with the error lost when the console closed. The exe launches fine from PowerShell and from `conhost.exe cmd /c …` here, so the cause is unknown; the script keeps stderr in `build-dbg/stderr.log` and holds the window open on failure so the next occurrence is readable. Verified: game up in 10 s via the script; bogus `--game` produces a readable log. |
