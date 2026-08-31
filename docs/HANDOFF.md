# Handoff — next session

**Status:** IN PROGRESS (updated 2026-08-31, end of the overlay-dispatch session)

Read [`STATUS.md`](STATUS.md) for where the project stands and
[`OVERLAYS.md`](OVERLAYS.md) for the finding the next task rests on. This file
is what to pick up and the traps already paid for.

## Where things stand in one paragraph

The game **plays**. It boots, renders, has audio, takes input, writes memory
cards, and has been played past the prologue into the mines with area
transitions, name entry and menus. The **text engine is identified and confirmed
on a live run** — that work is done. **Most of BoF3's code lives in overlays**
(81.6% of the boot EXE's text segment is zero-fill, and a measured session put
93.6% of interpreted instructions in that space). **All ten bands are now
compiled in and are the current configuration**, after a three-step upstream fix
to overlay dispatch that overturned the earlier "do not compile all bands"
result. Combat runs native. What is left is not band coverage but the §9
dispatch bypass, the coverage gaps *inside* bands, and pushing the framework
fixes upstream.

## Where the overlay work stands

**Static extraction works, and all ten bands are compiled.** See
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) for the full evidence. In
short: all 880 `.EMI` files are enumerated (`analysis/emi_sections.json`), the
code lands in exactly **ten** RAM bands totalling **405 unique sections /
3.61 MB**, and `GAME.EMI` §0 (`0x80196800`, the field engine) is compiled into
the runtime and linked. On a live run the overlay dispatcher logged
**603,391 content checks with 603,391 hits and zero CRC misses**, and band 1
recorded **zero** interpreted PCs against 558 before. No capture, no
`[runtime] overlay_cache`, no DLL loader — that path stays inert.

## Band 2 is done — battle engine, `0x80093800`

Compiled and verified in combat on 2026-08-30. 303 static roots in, **303
functions out**, `unknown_excluded: 0`, `Unknown/bad targets: 0`. On a live run
with a real battle: `static_checks` 904,076 = `static_hits` 904,076,
`static_crc_misses` **0**, aborts and dispatch misses 0. The band carries
**0.0%** of interpreted work (17,053 instructions in 7 stray PCs). Full evidence
in [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §5b.

All bands live in one `generated/overlays_static.c`, now built from
`analysis/overlay_captures_all.json` (**all ten bands, current since
2026-08-31** — see §12). `compile_overlays.py --static` writes a single file per
run, so **the whole set must always be recompiled together** — compiling one
band alone silently drops every other.

## The next task — start here

**The upstream dispatch fix is DONE — all three steps.** Full evidence in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §10-§12.

The §8 plan called for two upstream fixes: memoize the resident variant per
band, and make address lookup O(1). Investigating the first turned up a
prerequisite nobody knew about — **the static path had no residency signal at
all.** `overlay_page_gen` only advances for pages in `overlay_watch_bitmap`, and
the only callers of `overlay_watch_set_range` were in the DLL loader, which is
inert here. So the CRC gate was consulted *once per variant per process*, and
cached negatives were permanent: a variant checked before its content loaded was
locked out of native dispatch forever.

| Step | State |
|---|---|
| 1. Arm the page watch for static ranges | **DONE** — `psxrecomp` `aa6fa2c9` (§10) |
| 2. O(1) address lookup (kills §8 Finding 2) | **DONE** — `psxrecomp` `69d783f5` (§11) |
| 3. Resident-occupant memo (kills §8 Finding 1) | **DONE** — `psxrecomp` `70153175` (§12) |

All three are committed on branch `fix/static-overlay-residency-signal`,
branched from the pin `f24b7e5d`.

**ALL TEN BANDS ARE NOW THE CONFIGURATION.** §8's "do not compile all bands" is
overturned: all-bands beats three-band on both workloads measured — **131.4 vs
107.9** emulated fps at boot, parity on a savestate workload. The relationship
inverted, because once dispatch is cheap, more compiled code means more native
execution. Build it from `analysis/overlay_captures_all.json`; §12 has the
exact commands.

Headline numbers, all headless VSync throughput on identical protocols:

| | boot (140 s) | savestate (200 s) |
|---|---:|---:|
| 3-band switch (the old build) | — | 106.5 |
| 3-band table | 107.9 | 113.2 |
| all-bands table, no memo | 99.0 | 115.1 |
| **all-bands table + memo** | **131.4** | 114.2 |

Note the third row: **without the memo, all-bands is slower than three bands at
boot.** Both steps 2 and 3 are load-bearing for the all-bands result.

### The two decisions left on this work

1. **Push the branch and bump the parent gitlink.** The gitlink still points at
   `f24b7e5d`, so a fresh checkout does NOT get any of this. The branch is
   local-only — push it to `origin` (`kerokline/psxrecomp`) before bumping, or
   the gitlink will reference a commit nobody else has. A PR to
   `mstan/psxrecomp` is the eventual home; all three commits are framework-level
   fixes with no BoF3-specific content.
2. **The parent repo has never been committed** for any of this session's work,
   and it also still carries the previous session's uncommitted changes.

**Do not assume the whole transition problem is solved.** The stall is much
cheaper but not eliminated, and the §9 bypass below is untouched.

### Still open, and NOT explained by any of the above

**A compiled dispatch entry is not being dispatched.** `0x801CEEDC` (~45% of all interpreted work, 417 K
instructions per entry) was compiled as band 3 and verified to be a real `case`
in `psx_overlay_dispatch` — and it is *still interpreted*, 85.9 M instructions
over 206 entries, while `static_variant_misses` and `static_crc_misses` are both
0. The gate never failed; it was never consulted. The only call site is
`dirty_ram_interp.c:2795` in `dirty_ram_dispatch_inner()`. Full writeup:
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §9.

Until this is understood, **compiling a band does not guarantee its hot code
runs native**, which undercuts band-adding as a strategy independently of the
dispatch-cost problem in §8. Instrument that call site — log the addresses it is
consulted for — and find out how `0x801CEEDC` is entered without passing it.

**Never infer success from `static_hits`.** Band 3 looked perfect by every
counter (chk/hit 1.00, 0 variant misses, 0 CRC misses) while its entire purpose
went unachieved. Verify per-PC with `tools/harvest_interp_pcs.py` after every
band addition.

Axis A (more bands) was blocked on the §8 dispatch cost. **That blocker is
gone** — steps 1-3 removed both of its costs and all ten bands are now
compiled, so Axis A is complete. Axis B (coverage *inside* bands) is untouched
and is now the main band-related work left.

### Axis A — CLOSED, all ten bands are compiled

> **Superseded 2026-08-31.** The table and reasoning below describe the old
> dispatch design and are kept only so the result is not re-derived. All ten
> bands now build and outperform three bands; see §12. Do not act on the
> recommendation in this subsection.

**All ten bands were compiled and reverted on 2026-08-30. That revert has since
been undone.** Full evidence in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §8 and §12. Compiling was
always fast and correct; the problem was dispatch cost, now fixed.

| Build | Captures | Dispatch cases | Capcom screen | Memcard read |
|---|---:|---:|---:|---:|
| Two-band (current *at the time*) | 2 | 10,547 | ~18 fps | ~20 fps |
| Shallow (8 bands) | 96 | 29,500 | ~9 fps | ~9 fps |
| All bands | 338 | 39,036 | ~5 fps | ~5 fps |

Two independent costs, both measured:

1. **Deep variant chains.** The memory-card screen hit **41.25 checks per
   hit** — 4.4 M *failed* variant checks per 2 s — because the resident
   occupant sat ~41 deep in `0x801EEC00` (128 occupants) or `0x801F2C00`
   (114). Cutting those two bands fixed it (41.25 → 4.28 chk/hit, 430x less
   check volume).
2. **Total compiled volume, which is the bigger cost.** Frame rate tracks
   dispatch-case count, *not* chain depth — the shallow build caps chains at 35
   and still lost half the frame rate. And `static_hits` is **0** on those
   screens: no overlay code is running, so we pay for compiled code that never
   executes. `psx_overlay_dispatch` is consulted ~92,500x/sec at boot and is a
   switch over tens of thousands of sparse cases.

**The unblocking work is upstream in `psxrecomp`, and it is the same insight
both times: the runtime already knows which overlay just loaded, and throws
that away.** On hardware the game CD-reads a file to a fixed address and
`jal`s straight into it — no lookup, because identity is implicit in control
flow. Two fixes:

- **Memoize the resident variant per band.** Page generations are already
  tracked (`overlay_watch_pagegen_sum`); a generation change *is* the load
  event. Clear the memo, walk once to identify the new occupant, remember it.
  Every later call becomes one CRC check. Kills cost 1.
- **O(1) address lookup** instead of one monolithic switch. Kills cost 2.

Until those land, **two bands is the best measured configuration** and band
count is capped. Adding a third band is not obviously worth it — measure the
Capcom screen and a memcard read before and after, and revert if they regress.

**Do NOT re-try these dead ends:** raising `STATIC_MATCH_CACHE_CAP`
(`overlay_loader.c:560`) — `static_rehashes` stayed **0** throughout, the cache
never saturated; and page-faulting/binary size — working set was flat during
the slow screens.

### Axis A2 — the battle-transition slowdown itself

Still unfixed, and still caused by `0x801D0C00` (29.9% of interpreted work),
`0x801EEC00` (20.1%) and `0x801CE400` (9.1%) being uncompiled. But compiling
them costs more than it saves today — see above. This waits on the upstream
dispatch fix.

### Axis B — coverage gaps inside bands already compiled

**13,682,184 interpreted instructions across 37 PCs sit inside band 1**, which
was recorded as having zero. That zero was true for a boot-and-idle run; a real
play session reaches entries the static call-edge walk never saw, because they
are only reached through dynamic dispatch. Band 2 has the same gap at 7 PCs.

A compiled band is not a fully native band. `tools/harvest_interp_pcs.py`
against a live session is what finds these; feeding the observed PCs back as
extra roots and recompiling should be cheap. This is orthogonal to Axis A —
Axis A adds *bands*, Axis B deepens coverage *within* a band — and neither
blocks the other.

## Traps paid for — do not re-pay them

- **The all-bands generate exits with code 2, and that is correct.** 335 of 338
  shards build; the three failures are the known `UNSUPPORTED_INSTRUCTION` cases
  at `0x800C1800` (BIN/BOSS, x2) and `0x801F2C00` (AREA038) — data walked as
  code. The output file is written and is correct. Automation must not treat
  exit 2 as fatal without checking *which* shards failed.
- **Measure dispatch changes on a variant-heavy workload, not just a hit-heavy
  one — they disagree in sign.** The resident-occupant memo measured neutral to
  slightly *negative* on a savestate-loaded combat workload (chains already
  1.019-1.055 deep, nothing to shorten) and **+33%** on boot (chains 1.479).
  An early reading of the first table concluded the memo was not a win. It was
  the wrong workload. `tools/headless_ab.py` runs the savestate workload; the
  boot workload is the same harness with the savestate step skipped.

- **The build on disk was NOT the two-band configuration**, despite §8 and
  `STATUS.md` both saying two bands "is what is built". It was the §9
  **three-band** build (11,913 dispatch addresses / 12,522 variants). Every
  measurement taken on 2026-08-31 is therefore three-band. Check before
  trusting any claim about which bands are live:
  `grep -o "ov_00[0-9A-F]\{6\}_" generated/overlays_static.c | sort -u`
- **`savestate load` over TCP DOES work headless** — the trap below saying it is
  broken applies to the windowed path. Under
  `--headless --no-launcher --game game.toml` it returns immediately with
  `last_ok=1` and the listener stays alive. This is what makes the A/B harness
  (`tools/headless_ab.py`) possible.
- **`frame_perf` is unavailable headless** ("no frame_perf samples — GL timer
  queries unavailable"). Use the VSync counter at `0x8018603C` via `read_ram`
  and compute emulated frames per wall second. Headless is *uncapped*, so this
  is a better dispatch-cost metric than fps — it is not clamped at 60.
- **A generator/runtime hash mismatch would fail silently.** If
  `psx_ov_hash_slot` in the emitted C ever diverges from the Python that built
  the table, every lookup misses, everything falls to the interpreter, and the
  game still *runs* — just slowly. Any change to that hash must be re-verified
  across the whole address space; §11 has the check.

- **`static_crc_misses: 0` was never evidence of a healthy gate.** Before
  `aa6fa2c9` the gate short-circuited on a frozen page generation, so a zero
  there meant "never re-evaluated", not "always matched". Any pre-2026-08-31
  measurement of that counter says nothing about content validation. Same
  applies to a flat `static_rehashes`.
- **The launcher is the default.** `BreathOfFire3_Recompiled.exe --debug-port N`
  alone sits at `main() entered` with no debug server, waiting on a GUI click.
  Use `--game game.toml --no-launcher --debug-port 4370`.
- **`playsession.send()` takes a dict, not a string.** `send({"cmd":
  "overlay_loader_status"})`. A bare string returns `unknown command`, which
  reads like a missing feature rather than a caller error.
- **`frame_perf` fps is a rolling 256-frame average** — ~4.3 s at 60 fps, so it
  *smears transient stalls*. A sub-second dip to 20 fps shows up as a mild
  average. Use `all.total_ms_max` (a rolling max over the same window) for
  anything stall-shaped. An early revision of the §10 notes nearly claimed a
  transition improvement off the averaged number.
- **The submodule floated off the pin again**, this time to `47bda817` (two
  commits past `f24b7e5d`: a savestate fix and the multi-disc launcher merge).
  Both are on `upstream/master`, so nothing is lost by resetting. Check
  `git submodule status psxrecomp` for a leading `+` before trusting any
  measurement baseline.

- **PowerShell has no inline env-var prefix.** `VAR=x cmd` is a parse error.
  Use `$env:VAR = "0"` then `.\path\to.exe`. The framework docs are bash.
- **The "crashes" were the starvation watchdog**, not the game.
  `starvation_ring.c` calls `exit(2)` after 4 s without an emu-thread
  heartbeat. Signature: `reason: atexit` with `exit_origin: "unknown"` (the
  tagged paths are `tcp_quit` / `sdl_window_close`). Disable with
  `PSX_STARVATION_TIMEOUT_US=0`.
- **Two ~87 MB freeze dumps are written at EVERY boot**, at frame ~328, from a
  `slow_frames` then `hard_freeze` false positive. ~160 MB per launch. Prune
  `build-dbg/psx_freeze_dump_*.json` between sessions.
- **Savestates: in-game slot saving now works, including in combat.**
  User-reported on 2026-08-30 with bands 1+2 compiled, and used successfully to
  hold a mid-battle position for measurement. This softens the earlier trap
  below but does not delete it — the refusal mechanism is still in the code and
  nobody has re-derived why it stopped firing. Plausible reading: two compiled
  bands mean fewer interrupts land inside the dirty-RAM interpreter, so the
  snapshot-safe gate passes more often. **Unverified — do not state it as
  fact.** The mechanism: `psx_irq_resume_context_snapshot_safe()` is
  `g_cosim_dirty_pump_site == 0` (`interrupts.c:629`); an interrupt taken inside
  the dirty-RAM interpreter is never snapshot-safe, and retrying does not help
  because it tracks the *interrupt path*, not the aggregate ratio. In-game
  memory-card saves remain the reliable fallback. Savestates *do* survive a
  rebuild (verified).
- **`tools/playsession.py state load` is broken** — it exceeds the I/O thread's
  30 s bound (`emu busy or frozen`) and leaves the listener dead. The in-game
  **X** key also kills the process; **Enter/Start** works. Load in-game, then
  read RAM over TCP.
- **In-game savestate slot N is file `slotN-1`.** Established from write
  timestamps, see [`SAVESTATES.md`](SAVESTATES.md).
- **Seeding is a dead end, proven three ways.** Extending
  `seeds/ghidra_funcs.txt` from 523 to 868 gave a **byte-identical generate**;
  seeding interior PCs produced aliases into a parent compiled from zero bytes;
  and the session profile shows static EXE code with **`entries = 0`**, so the
  interpreter never *enters* static code at all. Do not revisit this.
- **A generate that changes the shard count needs a CMake reconfigure**, or the
  link fails with undefined `func_*`. The generated source list is captured at
  configure time.
- **`GAME_OVERLAY_STATIC_C` must not follow a multi-value CMake keyword.**
  Placed after `GEN_FULL_GLOB`, `cmake_parse_arguments` swallows it into that
  glob list: the file still compiles, but `PSX_HAS_OVERLAY_DISPATCH` is never
  defined and the link fails with hundreds of undefined
  `psx_overlay_static_code_matches`. Keep it after `APP_ICON`. Full writeup in
  [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §4.
- **`--cps` is required when compiling overlays.**
  `generated/SLPS_009.90_dispatch.c` sets `g_psx_cps_mode = 1`, so the runtime
  is a CPS build; omitting the flag produces mismatched overlay code.
- **Do not seed the `GAME.EMI` §0 header pointer table.** Its 26 in-region
  entries are chained jump-table cases, not function starts — 0 of 26 have a
  prologue or a preceding `jr $ra`. The framework would classify them
  `FUNCTION_POINTER_TARGET`, which is exempt from the boundary gate, so they
  would truncate their hosts. `OVERLAY_EXTRACTION.md` §2 has the disassembly.
- **Compare discs by content hash, not by size.** A JP↔US size diff finds 368
  changed sections; hashing finds **972**. The 502 same-size/different-bytes
  type-0 sections and all 37 language-bearing images are invisible to a size
  comparison. `emi_survey.py` now hashes every section for this reason.
- **Section destinations are region-specific.** 1,096 sections move between the
  JP and US discs, in systematic blocks (+0x8000, +0x6000, +0x3000). The
  existing "select by destination, never by index" rule needs the companion:
  destinations only mean something *within* one region. `0x80010000` (the area
  script) is the one address that does not move.
- **`harvest_interp_pcs.py` writes PCs as *physical* addresses.** The JSON has
  `"pc": "0x001D7524"`; the console report prints `0x801D7524`. Mask with
  `(pc & 0x1FFFFFFF) | 0x80000000` before bucketing against band destinations,
  or every PC silently falls out as "unmapped".
- **Band 2's compiled region is `0x80093800`–`0x800B4003`.** An earlier handoff
  said to check up to `0x800C1800`; that overshoots by ~56 KB and `0x800C1800`
  is a *different* band (7,676 bytes, 35 occupants).
- **A band that compiled clean is not a band that is fully native.** Static
  discovery yields the statically reachable call graph only. Band 1 shows 37
  interpreted PCs *inside* it on a real play session despite a clean compile and
  an earlier measured zero. Always re-measure with a live session, not a boot.
- **The static-match CRC cache is not a performance problem.** 903,517 of
  904,076 checks took the page-generation fastpath; 559 needed a re-hash. Do not
  go optimising `psx_overlay_static_code_matches` — measure first.
- **OV-1 does not apply to the static overlay path. Do not build an
  unregistration mechanism for it.** OV-1 in
  `psxrecomp/docs/overlay-status.md` is a defect in the **DLL loader**
  (`[runtime] overlay_cache`): it registered 88 functions once, never
  re-evaluated them, and when the game reused `0x800E7000` for other content it
  dispatched into stale native code — the blue screen. **That loader is inert
  here** (`registered`/`loads`/`invalidations` are all 0). The static path is
  content-addressed at *every* dispatch: `compile_overlays.py`
  (`generate_overlay_dispatch`, ~line 2315) emits one `case` per address with
  each occupant as a CRC-guarded variant, and
  `psx_overlay_static_code_matches()` hashes the live RAM bytes before the call
  is allowed. The CRC gate *is* the dispatch condition, so stale code cannot
  run; a non-resident variant simply misses and the address falls to the
  interpreter. `static_variant_misses` exists to count exactly this. Multi-
  occupant bands therefore need **no** register/unregister work — compile all
  occupants and let the gate choose. A session that reads "swap slot" as "must
  solve OV-1 first" will burn itself on a problem this design does not have.
- **Pre-existing slow screens, NOT overlay regressions.** The Capcom logo runs
  at ~18 fps (0.30x) and memory-card reads at ~20 fps **in the two-band build**,
  i.e. in the best configuration we have. Nobody has investigated either. They
  are the largest user-visible slowdowns outside battle transitions, and they
  are a separate problem from overlay coverage.
- **Frame-number comparisons across runs are invalid.** Boot phases do not line
  up between launches, so "frames 96-346 was the Capcom screen last time" is not
  sound — an early revision of this session's notes drew a wrong conclusion that
  way. Anchor performance claims to a named screen the user is actually looking
  at, not to a frame index.
- **All capture files are retained**, so any overlay configuration rebuilds:
  `analysis/overlay_captures_all.json` (338 captures, all ten bands,
  **current**), `_3band.json` (21), `_band1_battle.json` (2), `_band1.json` (1),
  `_shallow.json` (96). `analysis/` is **gitignored** — a fresh checkout must
  regenerate them with `emi_survey.py` then `extract_overlays.py` before it can
  build overlays. Note the all-bands generate takes ~13 min and the build ~7.
- **Three shards fail the audit as `UNSUPPORTED_INSTRUCTION`, and that is
  correct.** Two in `BIN/BOSS` at `0x800C1800`, one in `BIN/WORLD01/AREA038` at
  `0x801F2C00`. Decoding the words gives `0xFFFFFFFF`, `0xFFFF0601`, and functs
  `0x30`/`0x32`/`0x01` — TGE/TLT/MOVCI, MIPS II/IV encodings the R3000A does not
  have. **This is data being walked as code**, not a recompiler opcode gap: a
  static root ran into a jump table or fill. The audit refusing them is the
  right outcome; those occupants fall to the interpreter.
- **`overlay_loader_status` is the measurement that matters**, not the
  interpreted/native ratio. `static_checks` / `static_hits` / `static_crc_misses`
  say whether the compiled overlay is actually being used and whether the disc
  bytes still match RAM. The aggregate ratio is workload-dependent and is not
  comparable across sessions.
- **Keep the `psxrecomp` submodule on the pin.** It had floated to `a91884a4`;
  it is back at `f24b7e5d`. Reset with
  `git submodule update --init --recursive psxrecomp`.
- Earlier retracted-in-place diagnoses, left visible in `STATUS.md` so they are
  not re-derived: overlays as the cause of a *crash* (there was no crash),
  savestate load as the cause of the freeze dumps, and the seed list as the
  interpretation bottleneck.

## Tooling added today

| Tool | Use |
|---|---|
| `tools/harvest_interp_pcs.py` | Against a live run: interpreted/native ratio plus proven interpreted entry PCs, written to `analysis/observed_interp_pcs.json` |
| `tools/verify_msgtable.py` | Walks the message table on a running game |
| `tools/export_seeds.py` | Analyser to seeds merge. **Kept only for the record — its result was null.** |
| `tools/emi_survey.py` | Walks every `.EMI` on the disc, reads each TOC, hashes **every** section and code-tests the RAM-bound ones → `analysis/emi_sections.json`. Run it per region to diff discs. |
| `tools/extract_overlays.py` | Turns survey rows into `overlay_captures.json` with statically derived seeds — the input to `psxrecomp/tools/compile_overlays.py` |

Existing and still useful: `tools/emi.py` (parse/extract `.EMI`),
`tools/disc_ls.py` (list/extract the ISO9660 tree), `tools/disasm_exe.py`.

## Open questions

- **Where all the text lives is now settled** — four `.EMI` locations, none in
  the boot EXE, plus 37 language-bearing image sections. Full census in
  [`regional-builds.md`](regional-builds.md). Two things it left open: what the
  ~15 KB string table inside `GAME.EMI` section 0 actually contains (nobody has
  read it), and why `DEMO.EMI` section 5 ships the JP image on the PAL English
  disc but a distinct one on the US disc.
- **211 of 8,694 dispatch addresses are zero-fill**, from 18 of 523 seeds (all
  `low` confidence). Those are registered native entries compiled from nothing.
  Dirty-RAM invalidation masks them today; audit before trusting native
  dispatch in that range.
- **Text paths not yet seen live:** a shop, an equipment menu, and battle text.
  Each is a sub-minute check against a running game with
  `tools/verify_msgtable.py` and a screenshot.
- **Translation still needs** variable-width glyph advance (the JP interpreter
  hard-codes 12 px) and a line-break policy; mine `SLUS_004.22` rather than
  inventing one. And menus/items/name entry are a **separate text pool** from
  the `.EMI` area script.

## Environment

- `python`, not `python3`.
- MSYS2 toolchain is **not** on PATH by default:
  `export PATH="/c/msys64/mingw64/bin:$PATH"` (GCC 16.2.0, CMake 4.4.2,
  Ninja 1.13.2, ccache).
- Build: `./psxrecomp/tools/ci/build_emitters.sh`, then
  `python psxrecomp/psxrecomp_cli.py generate --config game.toml
  --project-root . --disc "isos/Breath of Fire III (Japan).cue"`, then
  `cmake --build build-dbg --target psx-runtime`.
- `build-dbg` is the diagnosis tree (`-DPSX_DEBUG_TOOLS=ON`). A Release build
  has no debug server and cannot be inspected at all.
- Ghidra project at `D:\Utilities\GhidraProjects\BoF3` (1025 functions),
  deliberately outside the repo. `analyzeHeadless.bat` cannot run `.py` —
  use `python -m pyghidra.ghidra_launch`.
- Prior decode work at `D:\BoFIII`: character table plus `decode_text.py`,
  reused by `tools/verify_msgtable.py`. Open the JSON as UTF-8.
