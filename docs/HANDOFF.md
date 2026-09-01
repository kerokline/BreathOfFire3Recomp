# Handoff — next session

**Status:** IN PROGRESS (updated 2026-08-31, end of the Axis-B / §9 / enrichment
session — §9 resolved, first full Axis B iteration landed, PC-enrichment tooling
added)

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
result. Combat runs native. **§9 is resolved** (2026-08-31 — it was an
unregistered *interior* address, fixed for free by the observed→alias pipeline),
and the **first full Axis B iteration landed**: a content-rich boss savestate was
harvested, and the battle overlay's hot interior points (`0x801E6C60` etc.) went
native, exactly as PLCHAR/§9 did. What is left is pushing the framework fixes
upstream, the **tier-1/2 runtime enrichment** (record resident-occupant + reach
per PC — see the enrichment section), and continued Axis B coverage as new game
content is played (the loop is proven and converging — 325→56→20→6 new PCs).

## Where the overlay work stands

**Static extraction works, and all ten bands are compiled.** See
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) for the full evidence. In
short: all 880 `.EMI` files are enumerated (`analysis/emi_sections.json`), the
code lands in exactly **ten** RAM bands totalling **405 unique sections /
3.61 MB**, and `GAME.EMI` §0 (`0x80196800`, the field engine) is compiled into
the runtime and linked. On a live run the overlay dispatcher logged
**603,391 content checks with 603,391 hits and zero CRC misses**, and band 1
recorded **zero** interpreted PCs against 558 before.

**The overlay *bytes* come from the disc, never from capture** — no
`[runtime] overlay_cache`, no DLL loader; that path stays inert. Entry *points*
are a different matter: the pipeline already blends statically derived roots
with PCs observed on a live run, and deepening that is Axis B. See "capture and
disc extraction are not rivals" below.

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

> **2026-08-31 update.** The Axis B loop below is now **proven end-to-end and
> converging**, and the current build already banks one content-rich iteration.
> The remaining threads, in priority order:
>
> 1. **The current build is all-bands + boss coverage** — `overlay_captures_all.json`
>    has **18,842 dispatch entries** from **956 observed distinct PCs (850
>    entered)**; `generated/overlays_static.c` is built from it and linked into
>    `build-dbg`. `analysis/` is gitignored, so a fresh checkout regenerates.
> 2. **Continued Axis B** as *new* game content is played (further than the intro
>    boss). The loop is mechanical; the one blocking input is a play session
>    reaching new content. Convergence on already-seen content is confirmed
>    (325→56→20→6 new PCs), so repetition is spent — new areas/characters/battles
>    are what still add.
> 3. **Tier-1/2 runtime enrichment** (see the new enrichment section below) — the
>    highest-value *tooling* investment; the mixed bands prove its need.
> 4. **Two residual battle interior points** — `0x801D1014` / `0x801E739C` still
>    interpret (down ~30× from pre-rebuild); the loop's next layer would peel them.
> 5. **DONE / held.** The **persuasive writeup** (thread 2) is reworked and
>    republished (2026-08-31), and the **upstream PR is held as a draft** — the
>    fork is now a living integration branch synced with upstream master
>    (2026-09-01), verified booting. See "Shipping state" below.

### 1. Axis B — the loop (mechanical, proven, converging)

A compiled band is not a fully native band: interior entry points reached only
by dynamic dispatch are invisible to the static call-edge walk, so they
address-miss to the interpreter *inside* a compiled band. The observed→alias
pipeline fixes them. This session proved it end-to-end — the intro-boss harvest
took the battle overlay's hot interior points (`0x801E6C60`, was 14.2 M interp
insns/#1 sink) **native**, the same mechanism that resolved §9's `0x801CEEDC`.

The loop is mechanical and self-improving:

1. Play a live `build-dbg` session covering as much as possible.
2. `python tools/harvest_interp_pcs.py` — **unions** this session's entered PCs
   into `analysis/observed_interp_pcs.json` as a distinct set (one row per PC,
   no duplicates), and reports how many are newly seen.
3. Re-run `tools/extract_overlays.py "isos/…Japan.cue"
   --out analysis/overlay_captures_all.json` (it reads the observed file by
   default via `--observed`) → `analysis/overlay_captures_all.json`.
4. Recompile all bands and rebuild.
5. Re-measure. Repeat until a session stops producing new entered PCs.

**It needs a play session to harvest against — that is the only blocking
input.** Everything after step 2 is mechanical.

**The observed set accumulates across sessions — union only, never replace.**
Two play sessions enter almost *disjoint* PC sets (measured 2026-08-31: two
sessions shared only 323 of ~17,500 PCs), because which `.EMI` area is resident
decides which addresses bucket to a band. So each session covers areas the last
did not, and overwriting would throw that away. `harvest_interp_pcs.py` now
unions distinctly, so the set only grows and `extract` reproduces full coverage
from the observed file with no manual capture merge. (This is why band-level
attribution inflating one PC into many is harmless: duplicates are collapsed in
the observed file and re-derived per band at extract time.)

### 1b. Enrichment — understanding what the captured PCs *are*

New this session: [`tools/enrich_pcs.py`](../tools/enrich_pcs.py) turns a bare
observed PC into an explained one, joining data we already have:

- **Identity** — reads the live band bytes and byte-matches them to the resident
  `.EMI` occupant (so `0x801CEEDC` → "`PLP27A` resident").
- **Boundary** — FUNCTION-START (prologue, or preceded by `jr ra`) vs INTERIOR,
  plus whether the PC is a static root or observed-only. This is how §9 was
  finally understood: `0x801CEEDC` is INTERIOR, `static_root_in=0`.
- **Semantics** — a disassembly window and the outgoing `jal` targets ("linked
  calls" — the subsystem edges).
- **Reach** — callers + args + frame span from the live `dirty_block_log` ring
  (4 M-entry, filterable by target). A **native** PC shows **0 ring hits** (the
  ring logs interp only), a free cross-check that a fix took.
- `--group` — offline interp-weighted **subsystem breakdown** by band+family
  (PLCHAR / BATTLE / SCENARIO / field / boss / kernel), the first cut at the
  "these calls are one subsystem" clustering.

**The offline slice is done; the durable upgrade is tier-1/2 in the runtime.**
The reach data only reaches as far back as the ring, and mixed bands
(`0x801D0C00` = BATTLE+ETC+SCENARIO+WORLD) can't be resolved to an occupant
offline. Recording, *per PC at entry time*, the **resident-occupant CRC**
(tier 1) and a **transfer-type histogram** (call/jalr/jr/branch/irq-resume,
tier 2) in `DirtyRamPcEntry` (`dirty_ram_interp.c`, emitted via
`dirty_ram_stats.per_pc`) makes both durable and session-long. Tier 2 is the one
that would have diagnosed §9 in minutes instead of an afternoon. This is a
framework change on the `fix/static-overlay-residency-signal` branch. Endgame
(per the user): once calls are grouped by shared caller/callee, "contextually
bound / philosophically linked" subsystems fall out — the unit for modding,
performance, and extensibility.

### 2. A short persuasive writeup of the static compile path and dispatch map

**DONE — reworked and republished 2026-08-31.** Audience is the other people
working on the wider psxrecomp ecosystem, who have only seen the capture-based
bringup used for Tomba / MMX6 / Ape Escape. The goal is a concise, persuasive,
layman-readable explanation of what this title does differently and why.

Published as a private artifact (same URL, updated in place):
<https://claude.ai/code/artifact/37f5d9d1-64c9-4db6-bb65-aad75e0ab4f4>
— **retitled "The Disc Ships the Map"** (the old title "Overlays Without
Capture" contradicted the corrected framing, since entry points legitimately
*do* come from play). It covers the normal capture path, the bytes/entry-points
decomposition, the disc's inherent grouping, the three-tool compile path, the
dispatch map, the frozen-gate bug, the measured result, and what transfers to
other titles.

**The two parked blockers are resolved:**

- **Reframed off the either/or.** The spine is now the decomposition from the
  next section — capture bundles *bytes* and *entry points*, which have opposite
  value here — plus the user's sharper thesis: for an EMI-styled RPG the disc
  ships the game's *own grouping* (named/typed `.EMI` containers → graphics vs
  sound vs logic vs area script), and that grouping is trivial to read but a
  research project to reconstruct from an address-keyed capture bucket. That
  grouping is the unit for the enrichment/subsystem-clustering endgame.
- **The stale §9 claim is gone.** The old "Still open" section said `0x801CEEDC`
  "is still being interpreted"; §9 is resolved, so that bullet was removed.

The one **unverified** claim was softened rather than verified: the draft now
says Tomba *reportedly* uses a scatter-load format "per the framework's own
notes; we haven't verified it against that project," instead of asserting it as
fact. If anyone wants it stated flatly, verify against the Tomba project first
([`OVERLAYS.md`](OVERLAYS.md) §5 / `psxrecomp/docs/overlay-discovery.md`).

**Remaining in thread 5:** the upstream PR is **held as a draft** by decision
(2026-09-01) — see "Shipping state" below for the living-integration-branch
workflow that replaced "merge it upstream."

### The framing both threads share: capture and disc extraction are not rivals

Established by inspection on 2026-08-31, and it reframes Axis B. **Capture
supplies two separable things, and they have opposite value here:**

| | disc extraction | runtime capture |
|---|---|---|
| **the bytes** | **wins decisively** — complete by construction, deterministic, reviewable, shippable, no playtime | strictly worse here; carries every objection (privacy, non-determinism, playtime-bound coverage) |
| **the entry points** | cannot see anything reached only by indirect dispatch | **wins decisively** — an executed PC with `entries > 0` is empirical proof of a callable boundary |

So the right architecture is **bytes from the disc, entry points from play** —
and *that is already what the pipeline does.* The current all-bands captures
carry **5,540** static call-graph roots plus **10,109** observed-PC attributions
(from 443 unique entered PCs), across 333 of 338 captures.

Note the asymmetry in risk: every objection to capture attaches to the *bytes*.
Entry points are a list of integers — no disc content, diffable, and purely
additive, since a bad one is rejected by the compiler's own validation. Axis B
is therefore capture's unique benefit at almost none of its cost.

Two known weaknesses in the current hybrid:

- **~~The observed set is a single session~~ — FIXED 2026-08-31.** It used to be
  a single session (443 entered PCs, 2026-08-30), the direct cause of the
  remaining gaps. `harvest_interp_pcs.py` now unions each session into a distinct
  accumulated `observed_interp_pcs.json`; the current set is **874 distinct PCs
  (768 entered)** from two sessions, and it only grows. The prior tool overwrote
  the file *and* appended to the dead seed lane — both removed.
- **Attribution is band-level, not occupant-level.** An observed PC is attached
  to *every* occupant of its address band — which is why the distinct entered
  PCs become ~17,854 attributions. Harmless (validation filters them) but it
  inflates seed counts and cannot tell you which of 181 area scripts actually
  ran an address.

**One case where capture's bytes would still win, even here.** If the game ever
patches or relocates overlay code *after* load, the disc bytes will not match
RAM, every variant will fail the checksum, and that address falls to the
interpreter silently — it looks like an ordinary miss. No evidence of this so
far (compiled bands run at ~100% hit rates and every CRC miss observed is
explained as a non-resident tenant). **The diagnostic:** a band where *every*
variant consistently misses means the disc bytes are not what reaches RAM, and
that band specifically would need captured bytes.

---

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

### Shipping state — updated 2026-09-01 (fork is now a living integration branch)

**Decision (2026-09-01):** the upstream PR is **held as a draft, not merged** —
we would rather fix any snag in-tree than round-trip through framework review.
So `fix/static-overlay-residency-signal` is now a **living integration branch**:
it carries our three commits *and* tracks upstream `mstan/master`, and we keep
pulling master into it as work continues. The proof-of-process goal is a full
BoF3 decompile with the `.EMI` subsystems intact — see the writeup thread above.

Current pins (both submodules bumped 2026-09-01, verified booting):

- `psxrecomp` branch `fix/static-overlay-residency-signal` on `origin`
  (`kerokline/psxrecomp`) at **`ecc0de16`** = upstream `master` merged over our
  three commits (`aa6fa2c9`, `69d783f5`, `70153175`). 3 ahead / 0 behind
  upstream at merge time.
- `recomp-ui` bumped `8c30e004` → **`4eda654`** (upstream `mstan/master` tip) —
  **required**, because the merged psxrecomp `main.cpp` uses the multi-disc
  launcher API (`RecompLauncherCGameInfo.discs/num_discs`,
  `RecompLauncherCSettings.disc_index`) that lives in recomp-ui. The two
  submodules must move together.

**The draft PR still stands** for eventual upstream consideration: all three of
our commits are framework-level with no BoF3 content, landing in order
(`aa6fa2c9` correctness prerequisite; `69d783f5`+`70153175` the load-bearing
performance pair). Blast radius is the static-overlay path only — verified
per-hunk (the DLL-loader capture path Tomba/MMX6/Ape Escape use is untouched).

#### Keeping the fork current — the recipe (conflict-free so far)

```bash
git -C psxrecomp fetch upstream
git -C psxrecomp checkout fix/static-overlay-residency-signal
git -C psxrecomp merge --no-edit upstream/master
# then bump recomp-ui to a matching upstream tip if the launcher ABI moved
```

Stays clean as long as upstream keeps clear of `overlay_loader.c` and
`generate_overlay_dispatch()` in `compile_overlays.py` — our only two touched
files. A conflict there lands in code you know.

#### Two gotchas the 2026-09-01 sync paid for — do not re-pay

- **After any framework bump, regenerate `overlay_codegen_hash.h` BEFORE
  compiling overlays.** The stale-recompiler guard (`verify_recompiler_matches_tag`)
  compares the recompiler's baked codegen hash against
  `psxrecomp/runtime/include/overlay_codegen_hash.h`. That header is regenerated
  by a **runtime** build step (`cmake --build build-dbg --target
  psxrecomp_codegen_hash`), so the correct order is: build emitters → base
  generate → **build the `psxrecomp_codegen_hash` target** → compile overlays →
  build `psx-runtime`. Compiling overlays first trips `FATAL: STALE RECOMPILER
  BINARY` (the guard doing its job, not a bug).
- **recomp-ui must be bumped in lockstep** with a psxrecomp master sync whenever
  the launcher ABI changes (as it did with `feat/multi-disc-launcher`). Symptom
  if you forget: the runtime build fails compiling `psxrecomp/runtime/src/main.cpp`
  with `RecompLauncherCGameInfo has no member 'discs'` etc.

#### Verified booting on the merged tree (2026-09-01)

Full rebuild (emitters → generate → overlays, all ten bands → `psx-runtime`)
succeeded, `BreathOfFire3_Recompiled.exe` produced. Headless free-run boots
clean, VSync advances, and overlays dispatch **native at ~99.6% steady-state hit
rate** once content loads (checks +104,317 / hits +103,934 in a late window),
`gen_fastpath` ~96%, miss counters frozen after load, `aborts` 0. **The merged
CD-ROM/DMA changes did not perturb the residency signal** (`aa6fa2c9`).
Follow-up, non-blocking: a slot-4 savestate load returned `last_ok: 0` — the
merge changed `savestate.c` (+123 lines, "fix savestates at dirty boundaries")
and the existing `.pst` files predate it, so cross-merge savestate
compatibility needs its own check. In-game/memory-card saves remain the reliable
path.

**Do not assume the whole transition problem is solved.** The stall is much
cheaper but not eliminated. The §9 bypass below is now **resolved**.

### §9 `0x801CEEDC` — RESOLVED 2026-08-31 (it was never a control-flow bypass)

**The diagnosis was wrong, and the observed-PC feedback loop fixed it for
free.** `0x801CEEDC` is **not** a function start — it is a mid-function store
(`sb v0,0x3BB0($at)`) inside a PLCHAR routine, in `static_discovery_entry_pcs`
of **zero** occupants. §9's "it is a real `case` in `psx_overlay_dispatch`"
mistook the **184 interior CPS `case ...: goto block_` resume labels** (inside
function bodies) for a real dispatch registration. In the band-3-era build it
was measured on, `0x801CEEDC` was **not a registered dispatch key**, so
`psx_overlay_dispatch(0x801CEEDC)` returned via the **address-miss** path (empty
slot) — which touches neither `variant_misses` nor `crc_misses`. That is why
those two counters read 0; "never failed the CRC" was misread as "never
consulted." There was no bypass of the line-2796 call site.

**The fix came from the Axis B pipeline itself.** Because `0x801CEEDC` was
*observed* with `entries > 0`, `extract_overlays.py` added it as a
`dispatch_entry_pc`, and `compile_overlays.py` emitted an **alias entry** —
`ov_..._alias_body_801CED1C(cpu, 0x801CEEDC)`, i.e. an independently dispatchable
key that jumps into the middle of host function `func_801CED1C`. In the current
all-bands build it is registered (`psx_ov_entries[] = { 0x801CEEDCu, 12870, 6 }`,
6 variants) and lives in `psx_ov_hash_addr[]`.

**Measured on the fresh build, in a live boss fight (savestate slot 4, PLCHAR
resident, attacks executing):** `0x801CEEDC` interprets **0** instructions
(+0 entries, +0 insns over the whole fight), and the *entire* PLCHAR band
`0x801CE400` — which was **60.5%** of interpreted work in the band-3 profile —
is now **0%**. Since the old build proved the function *is* invoked in combat
(206 entries), zero interpreted work means it dispatches native. Full evidence:
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §9.

**The general lesson:** an interior address reached only by dynamic dispatch is
invisible to the static call-edge walk, so it is never a registered key and
address-misses to the interpreter — *even inside a compiled band*. This is the
Axis B gap, and the observed→alias mechanism is its general fix. The same signature
is live right now for `BATTLE.EMI` interior points in band `0x801D0C00`
(`0x801E6C60` = 14.2 M interp insns, the current top interpreted PC) — harvested
2026-08-31, will go native on the next rebuild by the identical mechanism.

**Still true, and load-bearing:** **never infer success from `static_hits`.**
Band 3 looked perfect by every aggregate counter (chk/hit 1.00, 0 variant
misses, 0 CRC misses) while `0x801CEEDC` ran fully interpreted. Verify per-PC
with `tools/harvest_interp_pcs.py` after every rebuild — that is exactly how this
was caught and confirmed.

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

> **Corrected 2026-08-31.** The earlier version of this section said
> `0x801D0C00`, `0x801EEC00` and `0x801CE400` were *uncompiled* and that
> compiling them "waits on the upstream dispatch fix." Both claims are now
> stale — they described the three-band build. **All three are among the ten
> bands and all three are compiled in the current all-bands build** (verified:
> their entry PCs — e.g. `0x801EECD4`/`0x801EEEE0`, `0x801D112C`/`0x801D0C04`,
> `0x801CE448`/`0x801CEEDC` — are present in `generated/overlays_static.c`).
> Do not re-add them as "missing bands."

Still unfixed, but **not** because these regions are uncompiled. They are
compiled. What remains during a battle transition is two things, neither of
which is a missing band:

1. **Entry-point coverage *inside* those bands (Axis B).** A compiled band is
   not a fully native band. The battle-transition hot code surfaces to the
   interpreter at boundaries the static call-edge walk never named (jump-table /
   function-pointer targets), so it runs interpreted despite the band being
   compiled. This is the coverage layer, not the region layer — see Axis B.
2. **The §9 dispatch bypass.** `0x801CEEDC` (band `0x801CE400`) is compiled
   *and* is a real `case` in `psx_overlay_dispatch`, yet is still interpreted
   because the gate is never consulted. That is a routing defect, independent of
   coverage. See "Still open" above and `OVERLAY_EXTRACTION.md` §9.

**There are no more regions to capture.** The `.EMI` TOC survey is exhaustive
over the disc; the ten bands are all the RAM-bound code destinations that exist.
"All bands" is complete at the region *and* section (bytes) layer — the only
incompleteness left is entry points within bands (Axis B) plus §9.

### Axis B — coverage gaps inside bands already compiled

**13,682,184 interpreted instructions across 37 PCs sit inside band 1**, which
was recorded as having zero. That zero was true for a boot-and-idle run; a real
play session reaches entries the static call-edge walk never saw, because they
are only reached through dynamic dispatch. Band 2 has the same gap at 7 PCs.

A compiled band is not a fully native band. `tools/harvest_interp_pcs.py`
against a live session is what finds these; feeding the observed PCs back as
extra roots and recompiling should be cheap. Axis A added *bands* and is now
closed; Axis B deepens coverage *within* a band.

**Axis B is now the main remaining band work — see "The next task" above** for
the loop, the blocking input (a play session), and the reason this is capture's
one genuine advantage over disc extraction. The mechanism is already wired:
`extract_overlays.py --observed` defaults to reading
`analysis/observed_interp_pcs.json`, and only PCs with `entries > 0` are passed
on, because a PC the interpreter merely fell *through* is not evidence of a
callable boundary.

**Why static extraction cannot close this on its own:** reading disc bytes
tells you where code is, not where a function *starts*. Anything reached only
through a jump table or function pointer is invisible to a call-edge scan.
Band 1 is the proof — it compiled clean, audited perfectly, and still had 37
entries nobody could derive statically.

This does **not** contradict `FUNCTION_DISCOVERY` rule 1 ("no executed-PC
feedback"), which governs the *analyser*. The feedback here happens at the
overlay layer instead, which is why it is legitimate.

## Traps paid for — do not re-pay them

- **The all-bands generate exits with code 2, and that is correct.** A handful
  of shards fail audit as `UNSUPPORTED_INSTRUCTION` — data walked as code. The
  core three are `0x800C1800` (BIN/BOSS, x2) and `0x801F2C00` (AREA038); as the
  observed set grows, a *new* observed entry PC can walk into a data region and
  add one more (2026-08-31: `0x801EEC00` crc AA2E2918, 1 unsupported → 4 total).
  **The count is expected to drift with the observed set — do not read a higher
  number as a regression.** Each failure just drops that one occupant to the
  interpreter; the rest of its band compiles. The output file is written and is
  correct. Automation must not treat exit 2 as fatal — check *which* shards
  failed and that the failure class is `UNSUPPORTED_INSTRUCTION`, not something new.
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
- **The core audit failures are `UNSUPPORTED_INSTRUCTION`, and that is
  correct.** Two in `BIN/BOSS` at `0x800C1800`, one in `BIN/WORLD01/AREA038` at
  `0x801F2C00`. Decoding the words gives `0xFFFFFFFF`, `0xFFFF0601`, and functs
  `0x30`/`0x32`/`0x01` — TGE/TLT/MOVCI, MIPS II/IV encodings the R3000A does not
  have. **This is data being walked as code**, not a recompiler opcode gap: a
  static root ran into a jump table or fill. The audit refusing them is the
  right outcome; those occupants fall to the interpreter. Expect the *set* to
  grow by one occupant at a time as observed entries expand into new bands (see
  the exit-code-2 trap above) — same class, same correct outcome.
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
| `tools/harvest_interp_pcs.py` | Against a live run: interpreted/native ratio plus proven interpreted entry PCs, **unioned** (distinct, no duplicates) into the accumulated `analysis/observed_interp_pcs.json`. Downstream is `extract_overlays.py --observed`, **not** the seed lane — the old seed-append was a proven dead end and is removed. |
| `tools/verify_msgtable.py` | Walks the message table on a running game |
| `tools/export_seeds.py` | Analyser to seeds merge. **Kept only for the record — its result was null.** |
| `tools/emi_survey.py` | Walks every `.EMI` on the disc, reads each TOC, hashes **every** section and code-tests the RAM-bound ones → `analysis/emi_sections.json`. Run it per region to diff discs. |
| `tools/extract_overlays.py` | Turns survey rows into `overlay_captures.json` with statically derived seeds — the input to `psxrecomp/tools/compile_overlays.py` |
| `tools/enrich_pcs.py` | **Understand** an observed PC: resident `.EMI` occupant (live RAM byte-match), FUNCTION-START vs INTERIOR, disassembly window, outgoing `jal` targets ("linked calls"), and callers from the live `dirty_block_log` ring. `--group` gives an offline interp-weighted **subsystem breakdown** by band+family. Native PCs show **0 ring hits** (the ring logs interp only) — a free cross-check that a fix took. |

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
