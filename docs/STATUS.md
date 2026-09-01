# Current state

**Status:** IN PROGRESS (last verified 2026-09-01)

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
"where we are, what's next".

> **2026-08-31 session close.** (1) **§9 `0x801CEEDC` is RESOLVED** — it was an
> unregistered *interior* address that address-missed to the interpreter (not a
> control-flow bypass); the observed→alias pipeline registered it and it runs
> native in live combat (PLCHAR band 60.5%→0% interpreted). (2) **First full
> Axis B iteration landed** — a content-rich boss savestate was harvested and
> the battle overlay's hot interior points (`0x801E6C60`, was the 14.2 M-insn #1
> sink) went native. Observed set now **956 distinct PCs / 18,842 dispatch
> entries**; the loop is proven and converging (325→56→20→6 new PCs/session).
> (3) **Pipeline fixed** — `harvest_interp_pcs.py` now *unions* across sessions
> (was overwriting + seeding the dead lane). (4) **New tooling** —
> `tools/enrich_pcs.py` (identity / boundary / disasm / reach / `--group`
> subsystem breakdown). Full detail in [`HANDOFF.md`](HANDOFF.md).

## Where we are

**Most of Breath of Fire III is overlays (measured 2026-08-30).** The boot EXE
declares a 1,456,128-byte text segment, but **1,187,899 bytes of it — 81.6% —
are zero-fill** in the image, in 11 runs of 2 KB or more spanning
`0x80093801`-`0x801F6C00`. Only ~268 KB is real static code; everything else is
space that overlays load into at runtime. Static recompilation therefore covers
a minority of the game's code by construction, and the dirty-RAM interpreter
carries the rest — which is why execution measures 84-93% interpreted and why
savestates refuse. **The overlay path is not an optimisation for
this title; it is the main remaining engineering task.** Full evidence in
[`OVERLAYS.md`](OVERLAYS.md).

**Overlays are extracted statically from the disc — capture is not used
(2026-08-30).** BoF3's `.EMI` containers carry a TOC stating each section's RAM
destination, so the overlay set is a build input rather than a recording. All
880 containers are enumerated: **405 unique code sections, 3.61 MB, in exactly
ten RAM bands.** **All ten bands are compiled in** (since 2026-08-31; the
first two proven native were the field engine `GAME.EMI` §0, `0x80196800`,
227 KB, and the battle engine `BATTLE.EMI` §15, `0x80093800`, 133 KB). A live
run including a real battle
logged **904,076 overlay content checks, 904,076 hits, zero CRC misses**, with
`aborts: 0` and `dispatch misses: 0`; the battle band carries **0.0%** of
interpreted work, so combat runs native. The DLL loader and
`[runtime] overlay_cache` stay off, so the OV-1 stale-registration path is
never armed. Method and measurements in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md).

> **Read "zero CRC misses" with care (amended 2026-08-31).** That measurement
> predates `psxrecomp` `aa6fa2c9`. Static code ranges were not armed with the
> page watch, so the gate short-circuited on a frozen generation: the zero meant
> "never re-evaluated", not "always matched". The *hit* counts stand; the CRC
> counter carried no information. Post-fix numbers in §10.

**A compiled overlay entry is not being dispatched (2026-08-30).** `0x801CEEDC`
carries ~45% of all interpreted work. It was compiled as a third band and
confirmed to be a real `case` in `psx_overlay_dispatch`, yet it is still
interpreted (85.9 M instructions, 206 entries) while variant and CRC misses are
both 0 — the gate was never consulted. Only call site is
`dirty_ram_interp.c:2795`. **Compiling a band therefore does not guarantee its
hot code runs native**, and band 3 looked healthy by every counter while
achieving nothing. Top priority; see
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §9.

**All ten overlay bands were compiled, measured, and reverted (2026-08-30).**
Compiling is fast and correctness holds, but frame rate tracks the number of
dispatch cases: the Capcom logo runs ~18 fps on the two-band build, ~9 on a
96-capture build, ~5 on all 338, with memory-card reads tracking the same
curve. On those screens `static_hits` is **0** — no overlay code executes, so
the cost is the dispatcher itself, not the compiled code. A second, separate
cost is deep variant chains (41.25 checks per hit on the memory-card screen).
Both need upstream fixes in `psxrecomp` — per-band residency memoization and
O(1) address lookup — before more bands pay off. **Two bands is the best
measured configuration and is what is built.** Evidence in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §8.

> **SUPERSEDED 2026-08-31.** Both upstream fixes landed. All ten bands are now
> compiled and outperform three bands. The paragraph above is kept as a record
> of the old dispatch design; do not act on its recommendation. See §12 and the
> all-bands entry below.

**The upstream dispatch fix is underway (2026-08-31).** Three steps: arm the
page watch for static ranges (**done**, `psxrecomp` `aa6fa2c9` — it was the
unrecognised prerequisite for memoization, since the "load event" the plan
relied on never fired); O(1) address lookup (**done**, `69d783f5`); per-band
residency memo (**done**, `70153175`). §8's cost mechanism is no longer
inference — the
transition stall is the address-miss fall-through, measured at ~264,000
lookups/sec against a 5,400/sec field baseline.

Step 2 landed the same day (`69d783f5`): the sparse dispatch `switch` is now a
compile-time hash table. Headless A/B on identical captures, savestate and
protocol gave **+6.3% throughput and +12% at p1**; at the transition the switch
build absorbed 160,970 misses/sec at 63.9 fps while the table absorbed
307,978/sec at **131.3 fps**. Behaviour verified identical, not assumed.
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §10 and §11.

**Correction: the build on disk was the three-band configuration, not two.**
The claim above that "two bands is what is built" was false for the working
tree — `generated/overlays_static.c` carried `ov_00093800_`, `ov_00196800_` and
`ov_001CE400_`. §11.

**ALL TEN BANDS ARE NOW THE CONFIGURATION (2026-08-31).** Step 3 — a
resident-occupant memo (`70153175`) — completed the upstream fix, and §8's "do
not compile all bands" is **overturned**. All-bands beats three-band on both
workloads measured: **131.4 vs 107.9** emulated fps over an identical 140 s boot
window, and parity on a 200 s savestate workload. The relationship inverted:
once dispatch is cheap, more compiled code means more native execution.

Both later steps are load-bearing — *without* the memo, all-bands is **slower**
than three bands at boot (99.0 vs 107.9), because deep bands (128 and 181
occupants) push chk/hit to 1.479. The memo brings it to 1.069 and cuts wasted
gate calls 4.5x. Built from `analysis/overlay_captures_all.json`; commands and
caveats in [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §12.

**Not established:** single runs, so differences under ~2% are a tie. §8 Finding
1's actual worst case — 41.25 chk/hit on the **memory-card screen** — has still
not been re-measured, and the Capcom logo remains slow for reasons that are
**not** dispatch (during the pre-hit boot window the dispatcher runs at only
~750-1,100 address misses/sec, against ~264,000/sec at a transition).

**The Capcom logo (~18 fps) and memory-card reads (~20 fps) are slow even in
the two-band build.** Pre-existing, never investigated, and unrelated to
overlay work — the largest user-visible slowdowns outside battle transitions.

**Battle transitions are slow, and the cause is measured (2026-08-30).**
Entering and leaving combat drops hard while steady-state combat is fine. Three
bands — `0x801D0C00` (29.9% of interpreted work), `0x801EEC00` (20.1%) and
`0x801CE400` (9.1%) — are what runs during the transition; **all three are
compiled as of 2026-08-31**, and the transition is much cheaper but not fixed.
At entry
and exit `static_checks` collapses while `static_address_misses` spikes to
457 K / 695 K per 2.5 s. This is not a regression from compiling the battle
band; no earlier session ever entered a battle, so there is no before. All
three are multi-occupant swap slots, which is a dispatch-cost question and
**not** a safety one — see the OV-1 note below.

**A compiled band is not a fully native band (2026-08-30).** Band 1 shows
**37 interpreted PCs and 13.7 M interpreted instructions inside it** on a real
play session, despite a clean compile and an earlier measured zero on a
boot-and-idle run. Static discovery finds the statically reachable call graph;
dynamically dispatched entries are missed. Coverage must be re-measured with
`tools/harvest_interp_pcs.py` against live play, not at boot.

**The game loads (2026-08-30).** Title screen renders, Start is accepted, and
the opening prologue plays with Japanese text drawing correctly. Evidence and
method in [`BRINGUP.md`](BRINGUP.md) → Boot 002.

**Boot 001's "wait loop" was a misreading and is retracted.** The two pinned
`store_pc` values are `DrawOTag()` and `VSync()` — a healthy render loop. The
CD-ROM hypothesis is dead. What actually hid this: the Release build sets
`PSX_DEBUG_TOOLS=OFF`, which compiles out the TCP debug server, so there was no
way to look at the screen.

**The text engine is identified (2026-08-30)** — renderer, stepper, immediate
draw, font-atlas mapper, and the `0x80010004` message-index formula. This closed
the standing translation blocker. Confirmed independently by cross-language
`.EMI` diffing. [`TEXT_ENGINE.md`](TEXT_ENGINE.md),
[`regional-builds.md`](regional-builds.md).

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
- **No Western release is an address-compatible donor, and none has runtime
  language support.** All five releases compared (JP, US, EN, FR, DE): one EXE
  per disc, a separate SKU per language, EU vs US only ~21% word-identical over
  the real code region. The earlier "US not address-compatible with JP" finding
  (0x3000 shift, 4.6% seed overlap) is confirmed and generalised.
  [`regional-builds.md`](regional-builds.md).
- **The script section is variable-size.** Capcom grew `0x80010000` freely per
  language (EN 7912 -> FR 8085 -> DE 8412 in one area file), so a translation is
  **not** bound by the JP byte budget, and only that one section needs replacing.

## In flight

- `docs/LOCALIZATION.md` — new; the JP→EN assessment and the two upstream bugs
  it turned up (F-3, F-4).
- `docs/TEXT_ENGINE.md` — new; the text engine identified end to end.
- `docs/OVERLAYS.md` — the measured case that overlays dominate this
  title, and why seeding cannot substitute.
- `docs/OVERLAY_EXTRACTION.md` — new; the ten-band overlay map, the static
  extraction pipeline, and the live proof that bands 1 (field) and 2 (battle)
  are native. Eight bands remain, all multi-occupant swap slots. §5b has the
  battle-band result and the transition-slowdown measurement; §10 has the
  residency-signal fix and the measured cause of the transition stall.
  (An earlier revision of this line said the next band "needs OV-1
  unregistration solved". It does not — see §7 and the OV-1 section below.)
- `docs/regional-builds.md` — new; the JP/US/EN/FR/DE comparison, and the
  independent confirmation of the `0x80010000` script section.
- `tools/ghidra_seed.py` — new; second-pass Ghidra function seeder.
- `docs/SAVESTATES.md` — new; what each savestate slot holds, and the in-game
  vs file off-by-one. Seven states catalogued, covering name entry, field,
  dialogue and a response prompt.
- `BreathOfFire3EnglishRecomp/` — scaffolded but **not** generated or built. Its
  `psxrecomp` gitlink floated to master (`47bda817`) vs this repo's `f24b7e5d`,
  and its `disc =` is an absolute machine-local path. Both need a decision
  before it is built.

## Next up

1. **Axis B — close the coverage gaps inside compiled bands.** Now the main
   remaining band work, and deferred to a clean session. 37 interpreted PCs
   inside band 1 (13.7 M instructions) and 7 inside band 2, all reachable only
   through dynamic dispatch and therefore invisible to the static call-edge
   walk. Play → `harvest_interp_pcs.py` → re-run `extract_overlays.py` (which
   reads `analysis/observed_interp_pcs.json` by default) → recompile all bands.
   Self-improving, and it converges when a session stops producing new entered
   PCs. **A play session is the only blocking input.**

   This is where runtime capture genuinely beats disc extraction, and the two
   are not rivals: **bytes from the disc, entry points from play** — which is
   already what the pipeline does (5,540 static roots plus 10,109 observed-PC
   attributions from 443 unique entered PCs). Reading bytes tells you where code
   *is*, never where a function *starts* when nothing statically calls it. Full
   framing in [`HANDOFF.md`](HANDOFF.md).

2. **A concise, persuasive writeup of the static compile path and dispatch
   map**, for the wider ecosystem team who have only seen the capture-based
   bringup. Draft published (private artifact, "Overlays Without Capture");
   parked because it frames capture and disc extraction as either/or, which the
   decomposition above supersedes.

3. **DONE — more bands.** All ten are compiled and are the current
   configuration; the upstream dispatch fixes landed (`OVERLAY_EXTRACTION.md`
   §10-§12). The note below is kept because its *safety* reasoning is still
   correct and worth not re-deriving:
   `0x801CE400`, `0x801D0C00` and `0x801EEC00` hold multiple distinct occupants
   at one address. **This needs no new safety mechanism** — compile every
   occupant, and `compile_overlays.py` emits them as CRC-guarded variants under
   one `case`, so the resident one wins the content test and a non-resident one
   simply misses to the interpreter. The open question is dispatch *cost*: the
   variant chain is linear, so a resident occupant late in a 128-variant chain
   pays every failed CRC ahead of it. `0x801CE400` is the cheapest place to
   measure that — 19 variants, 9,932 bytes, and it owns `0x801CEEDC`, the single
   largest interpreted PC (7.2 M instructions). Note the runtime-capture path (`[runtime] overlay_cache`,
   `overlay_captures.json` from DMA) is **not** used and should stay off. The
   remaining non-overlay interpreted PCs are BIOS/kernel RAM
   (`0x800027AC`, `0x80002818`, …) plus boot-EXE static code around
   `0x80164E9C` — expected, and not addressable here.

   **All bands share one `generated/overlays_static.c`.** Add each new band to
   `analysis/overlay_captures_band1_battle.json` and recompile the whole set;
   `compile_overlays.py --static` writes one file per run, so compiling a band
   alone silently drops the ones that already work.

3. **Latent risk — zero-fill "functions" in the seed list.** `0x801D0C04` is a
   *pre-existing* seed and a `functions.tsv` row (confidence `low`, tags `leaf`,
   size 49,468) whose bytes are **all zero in the image**. The recompiler emits
   a body of NOPs for it and registers it in the dispatch table. Today
   dirty-RAM invalidation masks this (the region is written at runtime, so the
   interpreter wins), but it is exactly the OV-1 stale-registration failure mode
   from `psxrecomp/docs/overlay-status.md`. Audit `low`-confidence seeds against
   the image before trusting native dispatch in that range.

4. **Resume the soak** with `PSX_STARVATION_TIMEOUT_US` set (see *Blockers*),
   and run `python tools/harvest_interp_pcs.py` at the end of the session to
   measure coverage and capture the interpreted-PC profile.

5. ~~**Confirm the message-table formula on a live run.**~~ **DONE 2026-08-30.**
   Confirmed against both block shapes; the `0x80010004` `W` header turned out
   to be per-block, not universal. See [`TEXT_ENGINE.md`](TEXT_ENGINE.md)
   → *Live confirmation*. New next step: settle whether Latin/digit bytes are
   raw ASCII, since the area script uses the same byte range for control codes.
6. **Settle variable-width and line-break policy — mine the US build first.**
   Glyph advance is a hard-coded 12 px and JP line breaks are authored as
   control code `0x01`. Capcom's Latin-script build already solved both, so read
   the answer out of `SLUS_004.22` (import as a second Ghidra program, Raw
   Binary, `MIPS:LE:32:default`, base `0x80096000`; its addresses do **not**
   match JP) rather than inventing one.
7. **Settle the English repo's submodule pin and disc path**, then generate it
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

## OV-1 is not a blocker for the static path

`psxrecomp/docs/overlay-status.md` OV-1 (stale registration → blue screen) is a
defect in the **DLL loader** (`[runtime] overlay_cache`), which registers
functions once and never re-evaluates them. **That loader is inert in this
title** — `registered`, `loads` and `invalidations` are all 0.

The static path cannot have that failure. `compile_overlays.py`
(`generate_overlay_dispatch`) emits one `case` per address with each occupant as
a separate CRC-guarded variant, and `psx_overlay_static_code_matches()` hashes
the live RAM bytes *before* the call is allowed. The CRC gate is the dispatch
condition, so stale native code cannot execute; a non-resident variant misses
(counted as `static_variant_misses`) and the address falls to the interpreter.

**Amended 2026-08-31.** That last paragraph was true of the generated code but
not of the gate. Until `psxrecomp` `aa6fa2c9`, static code ranges were never
registered with the page watch, so the gate's generation fast path answered
every dispatch after the first from cache — the CRC was checked once per variant
per process, and cached negatives were permanent. The hazard was latent (band 1
has one occupant, band 2's resident never changed) but would have become real on
the first multi-occupant band. Fixed and verified;
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §10. The conclusion below is
unchanged.

Multi-occupant bands therefore require **no** register/unregister mechanism.
Recorded because an earlier revision of this file said they did, and that
framing would cost a session real time.

## Blockers

None. The game loads and runs.

Open, non-blocking:

- **The "crashes" are the starvation watchdog killing the process on purpose.**
  Root-caused 2026-08-30. `starvation_ring.c` calls **`exit(2)`** after **4 s of
  wall clock without an emu-thread heartbeat**, printing
  `starvation_watchdog: ... aborting` to stderr. That is why every run report
  shows `reason: atexit` with `exit_origin: "unknown"` — `exit(2)` is untagged,
  unlike the `tcp_quit` / `sdl_window_close` paths. The last one measured a
  **4.027 s** gap. It is a debug-build safety net for "TCP died, BIOS still
  running", not a game fault, and `build-release` does not have it.

  **Fix — set the env override when playing.** PowerShell (the shell actually
  used on this machine) has **no inline env-var prefix**, so the bash form is a
  parse error there:

  ```powershell
  $env:PSX_STARVATION_TIMEOUT_US = "0"; .\BreathOfFire3_Recompiled.exe --debug-port 4370
  ```

  Git Bash form, for the same thing:

  ```bash
  PSX_STARVATION_TIMEOUT_US=0 ./BreathOfFire3_Recompiled.exe --debug-port 4370
  ```

  `0` disables the watchdog; any microsecond value raises the threshold. The
  4 s budget is easily blown by a savestate write, a disc seek, or — perversely
  — by the freeze-dump machinery itself, which writes two ~80 MB JSON files
  while holding the emu thread.

- **Two ~80 MB freeze dumps are written at every boot.** Both at frame ~328
  during BIOS boot, `wedge_kind` `slow_frames` then `hard_freeze` one second
  later; the game then recovers and runs normally. A watchdog false positive
  caused by slow dirty-RAM interpretation at boot (6.7 M interpreted
  instructions), costing ~160 MB per launch. Unrelated to savestates.

- **Why saves fail — the precise rule.** `savestate_poll` requires
  `psx_irq_resume_context_snapshot_safe()`, which is literally
  `return g_cosim_dirty_pump_site == 0;` ([`interrupts.c:629`]) — *"dirty
  interpreter pump sites are IRQ-precise but not save-state safe: they can
  publish a valid committed PC while CPUState still describes a helper/device
  or previous local context."* So **every interrupt taken from inside the
  dirty-RAM interpreter is unsavable by design.** With execution measured at
  **91% interpreted** (sampled live: 9.0-9.1% native over five one-second
  intervals), almost every poll lands on a pump site, the 2 s defer window
  expires without one safe sample, and the save is refused.

  This is not probabilistic bad luck — an earlier "roughly one attempt in six
  should work, just retry" reading was wrong, since the poll runs every frame
  for two seconds and would trivially win at those odds. It is structural, and
  it is the same root cause as everything else: **uncovered overlay code**.
  Saves succeed in stretches that execute recompiled static code (the text
  engine at `0x8015xxxx` is in the EXE and native; the hot overlay region
  `0x801Cxxxx`-`0x801Dxxxx` is not), which matches the history — name entry and
  both dialogue-box states saved fine, open-field states in the mine now refuse.

- **Savestate operations, corrected.** Saves work: `slot04` was written
  complete (1.47 MB) and the process survived **58 seconds** afterwards, so the
  save did not cause the exit. In-game load via **Enter/Start** works; the **X**
  key does not. `tools/playsession.py state load` still returns
  `emu busy or frozen` (the I/O thread's 30 s bound) and leaves the listener
  dead — use the in-game Enter path and read RAM over TCP instead. An earlier
  claim that savestate load caused the freeze dumps is **withdrawn**; the dumps
  are the boot-time artifact above.

- Four upstream framework issues, all documented, none affecting BoF3 booting:
  F-1 / F-2 in [`BRINGUP.md`](BRINGUP.md) (false-positive BIOS staleness
  warning; garbage cross-function targets), F-3 / F-4 in
  [`LOCALIZATION.md`](LOCALIZATION.md) (stale "capture is always-on" docs;
  Shift-JIS validator accepting MIPS instruction words). Fixes belong in
  `mstan/psxrecomp`.
- Release builds cannot be inspected at all (`PSX_DEBUG_TOOLS=OFF`). Expected,
  but worth knowing before diagnosing anything against `build-release/`.
- `gh` not installed; affects GitHub CLI flows only.
- Ghidra 12.1.3 + GhidraMCP 6.0.0 are now installed and the project is built
  (`D:\Utilities\GhidraProjects\BoF3`, 1025 functions). The repo-root
  `.mcp.json` points at the ghidra-mcp stdio bridge on `127.0.0.1:8089` — note
  the framework's own `.mcp.json` expects SSE on `localhost:7777`, a different
  implementation; follow ghidra-mcp's. The MCP server needs the Ghidra GUI
  running; headless scripting works without it.

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
