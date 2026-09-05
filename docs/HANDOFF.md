# Handoff — next session

**Status:** IN PROGRESS (rewritten 2026-09-01 night after the framework pin
returned to upstream master; section 0 added 2026-09-05 after the data-anchor weekend; the dated banner history this file used to carry
is in the [`STATUS.md`](STATUS.md) Log)

Read [`STATUS.md`](STATUS.md) for where the project stands. This file is what
to pick up, how to build against the current pin, and the traps already paid
for. It points at evidence rather than restating it.

## Where things stand in one paragraph

The game **plays at 60 fps** on `build-relprof` (Capcom logo, world map,
memory-card screens all user-verified 2026-09-01 with clean audio). All ten
overlay bands plus `LOGO/LOGO.EXE` are compiled from the disc and dispatch
~99% native. The Axis B loop now takes **90 s** instead of ~16 min (parallel
static compile + split translation units, `psxrecomp` fork branch
`perf/static-overlay-parallel` `7ab698ca`, draft PR mstan/psxrecomp#296 —
play-test more, then request the merge and re-pin to `mstan/master`);
`recomp-ui` waits on one launcher PR. The text engine is identified and
confirmed live. A **readability track** is open: `names/` sidecars
(overlays, functions, areas), `tools/area_poller.py` (which area is resident,
with certainty, plus screenshots), and the browsable
`docs/subsystem_map.html` — 15 areas sighted, 5 aliased. What is left: Axis B
coverage inside the bands as new content is played, naming areas off their
screenshots, the tier-1/2 runtime enrichment, and the translation apply path.
**2026-09-05:** a second track produced most of the names so far: the
data-anchor loop (section 0 below) decoded the damage formula, level-up,
inventory, equipment and the save format in one weekend, with the RAM map in
[`BATTLE_RAM.md`](BATTLE_RAM.md).

## Start here

### 0. The data-anchor loop — where the names now come from (2026-09-05)

The weekend of 2026-09-04/05 replaced "differential traces name a function"
with a loop that names a function *and* the RAM it touches, and it ran
eleven times without a miss. Read [`BATTLE_RAM.md`](BATTLE_RAM.md) first: it
holds the party actor object, the persistent character records (base and
stride proven by code), the level table, inventory, zenny, the HUD, and
the complete save-file format. Then [`GHIDRA.md`](GHIDRA.md) for the
headless driver. The loop:

1. `callstack_diff.py ramdiff` around one action; type the numbers you saw
   on screen afterwards (`ramfilter --intersect FILE=n,n` across rounds).
2. `capture --watch LO-HI` on the cell(s); `writes` names the store PCs.
3. `ghidra_run.py export --decompile PC` (import the overlay first if new;
   `--start` seeds a gap the static walk missed).
4. `name PC Name --status evidence` when trace and body agree; document the
   RAM in BATTLE_RAM.md.

**Highest-value targets left, in order:**

| # | Target | Why it pays | How |
|---|---|---|---|
| 1 | **`Battle_BaseDamage` + the two defence steps** (`0x801DCAA0`, `0x801DC704`, `0x801DC85C`) | the only part of the damage formula not read; gives the ATK/DEF fields of both record types | `ghidra_run.py export --program BATTLE_EMI3_801D0C00 --decompile 0x801DCAA0,0x801DC704,0x801DC85C`, no game needed |
| 2 | **`Battle_Init` `0x801D1228`** to evidence | 1428-byte battle setup, hypothesis only; decompile + the battlebegin trace (33 fields at +563) | decompile; compare against BATTLE_RAM's actor table |
| 3 | **Enemy record layout** (`0x801EB634 + n*0x118`) | only HP/max/status/flags known; ATK/DEF/EXP-yield/drop table unknown | `capture --watch 0x801EB5A0-0x801EB8D0` over a battle start, then the writers' bodies |
| 4 | **Item drop + EXP yield** at battle end | closes the results screen: `BATL_END` calls `Inventory_Add` and `BattleResult_AddExp` from somewhere | `capture --watch 0x80145040-0x80145470` on a battle with a drop, window 1500+ |
| 5 | **Magic / Item / Run command paths** | same venn method as Attack/Defend/Watch; identifies the BMAGIC overlay ABI via the resident md5 | three captures from the slot-10 anchor with `--hold` |
| 6 | **Roster order** (who is roster 1, 2, 4..7) | one kill with Rei or Nina in the party | `--watch` on the `0x80144A10` / `0x80144AB4` EXP cells |
| 7 | **Dialogue engine anchors** (IDEAS I2) | the translation apply path still needs the box-string writers named | `capture --watch 0x801490A0-0x801490C0` on a dialogue open |
| 8 | **Psy-Q signatures on the boot EXE** | hundreds of libgpu/libspu/libcd names at once; needs a signature set | Ghidra GUI session; then `ghidra_run.py merge --symbols` |
| 9 | **Save editor / verifier script** | the format is complete: contiguous `0x10B0` block, u16 byte-sum at `+0x270` | small host tool over `.mcr` files; validates the RAM map end to end |

**Traps paid for this weekend** (details in BATTLE_RAM.md / GHIDRA.md):
long `ramdiff` windows net out later hits; a same-state save rewrites
identical bytes (use the write trace, not the diff); `wtrace_dump` truncates
a frame with more than 2 048 stores (the decompile fills in); a boot-EXE fn
filter wraps the ring in ~160 frames and the libcard range is flooded by
the `TestEvent` wait loop, so filter on the file-API wrappers
`0x8017F7B0-0x8017F830` instead; store PCs inside a shared band must be
attributed against the *resident* overlay only; `ghidra_run.py import` now
seeds traced entries and creates functions in descending order so lower
functions cannot swallow higher starts.

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
5. Re-measure. Repeat until `tools/pc_coverage.py` shows every stratum near
   saturation — **not** until a session produces 0 new PCs (see *The stop
   condition* below; 0 new is not evidence of a complete set).

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


**2026-09-01 late — the readability sidecar exists.** The "name the subsystems"
endgame above now has a home: `names/overlays.toml` + `names/functions.toml`
(keyed by section md5 + pc), `tools/name_map.py` (init/check/stats) and
`tools/subsystem_map.py` → `docs/subsystem_map.html`. Read
[`NAME_MAP.md`](NAME_MAP.md) for the schema, the status/evidence rule, and the
ordered routes to earn names. `axis_b_loop.sh` phase 6 regenerates the map on
every rebuild path; after a `--harvest-only` session or a `names/` edit, run
`name_map.py init` + `subsystem_map.py` by hand.

**Area naming is live (route 1 in NAME_MAP.md), not a banner-string join** —
there is no string-capture log in the current code. `tools/area_poller.py watch`
runs during play: it identifies the resident `AREAnnn` with certainty by
hashing the script block at `0x80010000` against `emi_sections.json`, takes a
settled screenshot a few seconds after each change (the change-instant frame is
black — the block lands during the fade), and compresses the runtime's per-call
`overlay_native_ring` to one row per overlay body per area.
`axis_b_loop.sh --harvest-only` runs the poller's one-shot `harvest` too. Both
append to `analysis/area_timeline.jsonl`; gather as many sessions as you like,
then `area_poller.py summarize --apply` writes sightings as `evidence` (never
overwrites). The alias is read off the screenshot by a human and typed into
`names/overlays.toml` with `status = "evidence"`. Seven WORLD00 areas sighted so
far (AREA001/002/006/009/024/031 + one more), zero aliased — that is the next
task.

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

### Shipping state — updated 2026-09-02 (perf branch on the fork, PR pending)

**2026-09-02:** `psxrecomp` is pinned to fork branch
`perf/static-overlay-parallel` at **`7ab698ca`** = upstream `mstan/master`
`04d9184b` (ABI v22 shim + shared release staging) + one commit: parallel
static compile (`--jobs` process pool), linear CPS resume-wrapper pass, and
split output (`overlays_static.c` dispatcher + `overlays_static_NNNN.c` per
overlay, globbed by `runtime.cmake`). Measured on build-dbg: phase 5a 12 min →
20 s, runtime build 4 min → 69 s, whole `axis_b_loop.sh --skip-harvest` ~16 min
→ 90 s; **build-relprof `psx-runtime` 1016 s → 162 s** (one 303 MB unit vs 358
units); shard summary and 79,688 identities unchanged; headless boot 99.92 %
static hit rate, miss_total 0. Upstream PR mstan/psxrecomp#296 is a **draft by
decision (2026-09-02): play-test the split/parallel build more before asking for
the merge**; **re-pin to plain `mstan/master` when it merges** (recipe below still applies). The bump required
rebuilding the emitters (`build_emitters.sh`; codegen tag `a4319b6f` →
`ecd487f7`) and a build-dbg reconfigure; `generate` was a no-op.

The 2026-09-01 "living integration branch" decision below is **superseded**:
that branch's commits were merged upstream and the pin went back to plain
master the same night; the perf branch above is an ordinary upstream PR, not
a new integration branch.

#### (superseded) 2026-09-01 — fork as a living integration branch

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
   bands; output is `generated/overlays_static.c` (dispatcher) plus one
   translation unit per overlay, `overlays_static_NNNN.c` (358 today), which
   `runtime.cmake` globs. Runs in a process pool (`--jobs`, default cores−2).
   Exit 2 with `[audit]` `0 unknown_bad, N unsupported` failures is the
   expected outcome. Since 2026-09-02 this phase takes ~20 s, not ~12 min.
6. Build `psx-runtime`; re-measure per PC with `harvest_interp_pcs.py`.

**It needs a play session reaching new content — that is the only blocking
input.** Replaying seen content converges to ~0 new PCs (325→56→20→6). The
observed set accumulates across sessions because two sessions enter almost
disjoint PC sets (which `.EMI` is resident decides what buckets to a band).

### Mixed sections are extracted by default (2026-09-04)

`extract_overlays.py` takes both `code` and `mixed` survey classes now. The old
`--include-mixed` opt-in is accepted and ignored; `--no-mixed` restores the old
behaviour for A/B work and prints a warning when used. `axis_b_loop.sh` follows.

The measurement that settled the open question:

| | default | `--no-mixed` |
|---|---|---|
| sections extracted | 405 | 338 |
| AREA files with ≥1 selectable section | **184 of 200** | **126 of 200** |

- **58 of 200 AREA files ship no `code` section at all** — their `mixed`
  section is the only compilable code they have. That list is not obscure
  content: AREA000 (MacNeil Village), AREA001/002 (Dauna Mines). Excluded, those
  areas have **zero** compiled code and run entirely in the dirty-RAM
  interpreter.
- **All 67 mixed sections load to one band, `0x801F2C00`** (the WORLD band), at
  section index 13 of each AREA file, 67 distinct md5s — one per area, as
  area-specific code should be. `0x801F2C00` is a known remaining interpreted
  sink, and `pc_coverage.py` ranks it the least-covered band.
- **`mixed` is a classifier artifact, not a third kind of section.**
  `emi_survey.classify` demands `jr>=4 AND prologues>=4 AND density>=2/kword`;
  the mixed sections are small (median 710 words vs 1957 for `code`) and
  leaf-heavy, so they fail the *absolute* prologue count while passing density
  by a wide margin (median 11.9/kword). WORLD04 AREA176–180 have **34 `jr ra`
  and 3 prologues** — unambiguously code, one prologue short of the gate.

**The cost of the old default was performance, not correctness.** Nothing was
"missed" in the sense of unexecuted or wrong: the dirty-RAM interpreter runs
whatever bytes are resident. What was missed is *compilation* — 58 areas' worth.
The tail of the mixed class does look like genuine data (AREA090: 1359 words,
2 `jr ra`, 0 prologues); compiling those costs a dead translation unit and some
audit noise, which is the cheaper error than leaving 58 areas interpreted.

### The stop condition — estimated coverage, not "0 new PCs"

"Play until a session produces no new entered PCs" is unfalsifiable: it is
equally consistent with *the set is complete* and with *the player walked the
same three rooms twice*. Since the sessions are nearly disjoint by construction,
the second reading is the likelier one, and the criterion also says nothing
about **where** the gaps are.

[`tools/pc_coverage.py`](../tools/pc_coverage.py) replaces it. Each play
session is a sampling unit, each PC a species, and the unseen remainder is a
Chao2 richness estimate over session incidence:

```
N = S_obs + ((m-1)/m) · Q1² / (2·Q2)        Q1/Q2 = PCs seen in exactly 1 / 2 sessions
```

```bash
python tools/pc_coverage.py            # by band (+ static fn-start ceiling)
python tools/pc_coverage.py --by area  # by resident area, named from names/areas.toml
```

Three things to hold onto when reading the output:

- **Stratify, and trust the strata over the global row.** Chao2 assumes samples
  drawn from one pool; these are not (the 323-of-17,500 overlap). Within one
  band or one area the sampling is far closer to homogeneous, so the per-stratum
  estimates are sounder, and their sum exceeds the global estimate — that gap
  *is* the heterogeneity. Read the global row as a lower bound.
- **Coverage is harvest completeness, not nativeness.** A band at 100 % can
  still be slow until its PCs are compiled in. That axis is the interpreted/
  native ratio, same tool, different number.
- **Two denominators.** `est. total` is what remains to be *found*; `fn starts`
  is the static function count in the band (`jr ra`, fingerprint-deduped) — a
  ceiling, not a target, since most of those are already native via static call
  edges and can never appear as an interpreted PC.
- **The one way this can mislead: replayed content.** Chao2's whole signal is
  singletons. Two sessions covering the *same* content see almost every PC
  twice, Q1 collapses, and coverage prints ~100 % — which is indistinguishable,
  to the estimator, from genuine saturation. The report warns when Q1 falls
  below 10 % of the observed set, or when coverage exceeds 95 % on fewer than
  four sessions. **Vary what you play**; a coverage number is only ever about
  the content the sessions actually reached.
- **`NEVER SAMPLED` rows are the honest gaps.** Every known band is listed even
  with zero observations, and unsampled bands lead the "go play these next"
  line, because a stratum with no draws is a bigger hole than one at 40 % — and
  a table that quietly omitted them would read as far better news than it is.

The estimate needs **session incidence**, added to `observed_interp_pcs.json`
on 2026-09-04 as a per-row `sessions` list (plus `areas`, stamped on PCs newly
seen in a poller pass while that area was resident). Rows harvested before that
have no `sessions` key; they count as seen but cannot contribute Q1/Q2, so the
report is pessimistic and calls out the legacy count until they are re-observed.
**Chao2 needs at least two sessions carrying ids** — the report says so plainly
rather than printing a number it cannot support.

**Strata are named.** `pc_coverage.py` labels each band from
`analysis/overlay_catalog.json` (refreshed by the loop's phase 3b), so rows read
`0x801F6C00 SCENARIO x20` and `0x801D0C00 BATTLE+ETC+SCENARIO +1 x18` rather
than bare addresses. Numbered siblings collapse (`WORLD00..04` → `WORLD*5`), and
a single-occupant band with an alias in `names/overlays.toml` uses the alias
(`0x801CE000 Capcom logo intro`, `0x80196800 Field/map core (large)`) — that is
the readability track paying off. `--by area` names rows from
`names/areas.toml`. Missing catalog degrades to bare addresses.

**A session id identifies the RUNNING PROCESS, not the wall clock.** This bit
us within hours of shipping it: harvesting the same live game twice (the loop's
end-of-run pass after the poller's timed one) minted ids `…093558` and
`…094409` over one play session. Both saw the same 196 PCs, none unique to
either, so Q1 = 0 and the harvest line printed **100.0 % coverage** of a set
nobody had finished exploring. `resolve_session()` now reads the runtime's
`frame` counter against `analysis/harvest_session.json`: a frame below the
stored one means the game restarted (a real new sample), anything else
continues the stored id. `area_poller.py watch` still passes its own id
explicitly, which wins. The two phantom ids were merged in the observed file on
2026-09-04 (backup: `analysis/observed_interp_pcs.prefix.bak`).

**The same bug had a second mouth: `area_poller.py watch`.** It passed its own
per-watch-run timestamp, which bypassed `resolve_session` entirely — so
starting the poller late, or restarting it mid-game, split one play session
again (ids `…101508-b053` and `…101601`, byte-identical PC sets 53 seconds
apart). The poller now passes `session=None` and lets the process decide; its
own run id stays on the *timeline* rows, where per-watch-run is the right grain.

**Detecting the split after the fact.** A cumulative per-PC table only grows
within a process, so if session A's PC set is a **subset** of session B's, A is
not a separate session — it is an earlier snapshot of the same one.
`pc_coverage.py` reports such ids as `DUPLICATE SESSIONS` and
`--merge-duplicates` collapses them (backup: `<observed>.premerge.bak`,
idempotent). Merging the 2026-09-04 set took 6 ids → 3 real sessions and the
global estimate from a flattering **97.6 %** to an honest **72.0 %** — the
clearest measurement yet of how badly a split sampling unit distorts Chao2.

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

- `psxrecomp` **`adf54eaa`** = local integration branch `bof3/int-fast-forward`
  = fork `perf/static-overlay-parallel` `7ab698ca` (draft PR
  mstan/psxrecomp#296) + cherry-pick of `feat/fast-forward-pad` `2ae78109`
  (controller fast-forward host shortcut, `[hotkeys] fast_forward_pad`; branch
  cut from upstream `22fbbfca`, PR [mstan/psxrecomp#307](https://github.com/mstan/psxrecomp/pull/307)). Two PRs
  outstanding, so the pin is a temporary fork state; bump back to plain
  `mstan/master` when both merge — fetch upstream, fast-forward the
  submodule's `master`, commit the gitlink, never float.
- **2026-09-03 — `psxrecomp` working tree is on fork branch
  `fix/gpu-polyline-terminator` `402cada6`** = upstream `master` `d08d84a3` + one
  commit (GP0 polyline terminator tested only at vertex-unit boundaries after
  the first two vertices — [`gpu-polyline-terminator.md`](gpu-polyline-terminator.md)).
  PR [mstan/psxrecomp#313](https://github.com/mstan/psxrecomp/pull/313) open;
  re-pin to `mstan/master` if it merges. Both `build-relprof` and `build-dbg`
  are built from it. The gitlink in the
  title repo was already dirty (mid re-pin to master) before this change.
- `recomp-ui` **`a736d57`** = local integration branch
  `bof3/int-scanlines-master` = fork `feat/present-scanlines` `fda07fe`
  (pending [mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42))
  with upstream `master` `da80dc7` merged in. The merge conflicted in
  `recomp_launcher.h`: #42 and upstream #46 both appended to the tail of
  `Settings` / `GameInfo`; resolved with upstream's `virtual_stylus` /
  `has_virtual_stylus` first and the scanline fields after — #42 should be
  rebased the same way before merge. Upstream #46 already draws every host
  shortcut on the Controller page, so the Fast-forward row needs no launcher
  change; [mstan/recomp-ui#47](https://github.com/mstan/recomp-ui/pull/47) is
  redundant (close it) and the old `bof3/int-fast-forward` branch is dead.
  Pin back to upstream `master` when #42 merges.
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
  --debug-port 4370`, or the exe sits waiting for a GUI click. Prefer
  `tools
un_dbg.cmd` (`relprof` / `--launcher` / extra args pass through): it
  runs the exe under a classic `conhost.exe` window so a Windows Terminal crash
  cannot take the game down, keeps stderr in `build-*/stderr.log`, and holds the
  window open on a non-zero exit. A bare `conhost.exe <exe> …` typed into a
  terminal loses the startup error with the window (2026-09-02 20:49 attempt:
  exited before any guest code, `frame 0`, reason lost).
- **PowerShell has no inline env-var prefix**; use `$env:VAR = "x"` then run.
  Git Bash env prefixes do not reliably reach the native child either — run the
  exe from PowerShell.
- **Scanlines are a per-build-tree setting.** `[video] scanlines` /
  `scanline_strength` live in each tree's `settings.toml`, and the runtime only
  writes those keys back once it has seen them, so a tree that never had them
  defaults to off. "Scanlines went missing" after a rebuild (2026-09-01) was
  `build-dbg/settings.toml` lacking the keys, not the pin. Verify over TCP with
  `{"cmd": "scanline"}`. Also: `build-dbg` (-O0) runs the intro FMV at ~40
  vblank/s windowed and always will — judge the intro on `build-relprof`.
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
| `tools/axis_b_loop.sh` | **The Axis B loop in one command** (harvest → extract → LOGO merge → catalog → hash → compile → build). Gates on 0 new PCs (`--force`) — that gate means "nothing new to compile", **not** "the set is complete"; for completeness read `pc_coverage.py`. Tolerates only the benign exit-2 shape, refuses to link a running exe. **Re-prints the `pc_coverage.py` table as the last thing it prints on every path** (including both early exits), so the number that decides whether to keep playing survives the compile/link scrollback. `--harvest-only`, `--skip-harvest`, `--skip-hash`, `--no-mixed`, `--no-coverage`. |
| `tools/harvest_interp_pcs.py` | Live run → interpreted/native ratio + proven interpreted entry PCs, **unioned** into `analysis/observed_interp_pcs.json` with per-row session incidence (`--session`, `--area`); prints estimated coverage. |
| `tools/pc_coverage.py` | Chao2 coverage estimate over the observed set, stratified `--by band` (default) / `area` / `none`. The Axis B **stop condition** — replaces "0 new PCs". `--json` for the full report. |
| `tools/extract_overlays.py` | `.EMI` survey → `overlay_captures_all.json` with static roots + observed entries. Reads the observed file by default. |
| `tools/extract_logo_overlay.py` | `LOGO/LOGO.EXE` (a PS-EXE at `0x801CE000`) → `static-emi-v1` capture; `--append-to` the all-bands file. |
| `tools/harvest_logo_handlers.py` | Locate runtime-populated function-pointer tables statically, read them live, emit every handler as a dispatch entry. |
| `tools/enrich_pcs.py` | Explain an observed PC: occupant, boundary, disassembly, linked calls, callers; `--group` subsystem breakdown. |
| `tools/overlay_catalog.py` | Offline catalog sidecar → `analysis/overlay_catalog.json` (overwrite, not merge). |
| `tools/emi_survey.py` | Walk every `.EMI`, hash every section, code-test RAM-bound ones → `analysis/emi_sections.json`. Per region. |
| `tools/fmv_bench.py` | Clean-boot headless FMV benchmark (vblank/present window) with optional gdb sampling of the emu thread. |
| `tools/headless_ab.py` | Headless A/B on a savestate workload (skip the load step for the boot workload). |
| `tools/verify_msgtable.py` | Walk the message table on a running game. |
| `tools/mednafen_ctl.py` | Drive the stock Mednafen oracle in `./mednafen/`: `launch --card` boots from our `card1.mcd`, `press`/`hold`/`key` inject pad and hotkeys via scancodes read from its cfg, `snap`, `state save/load`, `frame`, `card export`, `quit`. See [`MEDNAFEN.md`](MEDNAFEN.md). |
| `tools/playsession.py` | Debug-server wrapper: status, screenshot (`--renderer software`), savestates, traces. |
| `tools/pst_tool.py` | Read `.pst` savestates offline: `info`, `vram` (1024×512 PNG), `ram` (raw 2 MB), `diff A B` (VRAM zero-map, per-block diff map, blocks that went populated→zero, RAM diff ranges). Compare two states without loading them into a running game. |
| `tools/emi.py`, `tools/disc_ls.py`, `tools/disasm_exe.py` | Parse/extract `.EMI`; list the ISO9660 tree; disassemble the boot EXE with MMIO naming. |
| `tools/name_map.py` | `names/` sidecars (overlays / functions / areas): `init` merges new catalog overlays (never overwrites hand edits), `check`, `stats`. See [`NAME_MAP.md`](NAME_MAP.md). |
| `tools/subsystem_map.py` | Regenerates [`subsystem_map.html`](subsystem_map.html): bands → overlays → functions, boot EXE, areas, search. No bytes embedded. Phase 6 of the loop. |
| `tools/run_dbg.cmd` | Launch build-dbg (or `relprof`) under legacy conhost, stderr to `build-*/stderr.log`, window held open on failure. |
| `tools/area_poller.py` | `watch` during play (resident AREA by script-block md5, settled screenshot, native-ring compression, timed interp-PC harvest every 15 min + on Ctrl-C so a dead game costs ≤ one interval), `harvest` at end of session (loop phase 2a), `summarize --apply` → `names/areas.toml` + evidence. |
| [`BATTLE_RAM.md`](BATTLE_RAM.md) | **Battle RAM map + damage path** (2026-09-04): enemy records `0x801EB634+n*0x118`, party `0x80145F0C+m*0x140`, HUD gauges `0x801484B8+n*0x24`; `Battle_ApplyDamage` → `Battle_CalcDamage` → `Battle_BaseDamage` with the variance table and `Rand`. The loop that produced it: `callstack_diff.py ramdiff` (damage read afterwards, `ramfilter --intersect`) → `capture --watch` → `ghidra_run.py export --decompile` → `name`. |
| `tools/ghidra_run.py`, `tools/ghidra/*.py` | **Headless Ghidra driver** ([`GHIDRA.md`](GHIDRA.md)): `import` an overlay section from `overlay_captures_all.json` as its own program (seeded from the recompiler's roots), `export` every program to `analysis/ghidra/<program>.json` (functions, cop2 flag, callees, globals r/w, cross-band refs, jump tables, constant-`a0` call sites, optional decompile), `report`, `merge` → `names/functions.toml`. GUI must be closed (project lock). 2026-09-04: boot EXE + both BATTLE.EMI code sections exported; `Battle_FrameTask` / `BattleMenu_TargetCursor` promoted to `evidence` from the bodies. |
| `tools/callstack_diff.py` | **Differential call-stack tracer** (IDEAS I1 / NAME_MAP route 3): `capture` loads a savestate, arms `fn_filter` (sent physical — the server does not mask KSEG0), presses one button, drains the fn entry/exit rings and rebuilds the call forest with the resident area md5 + native-ring body CRCs; `tree`, `diff --prefix` (Attack vs Defend set difference, common-prefix = `Battle_Init` candidate), `propose --apply` upserts `hypothesis` rows into `names/functions.toml` (refuses ambiguous mixed-band occupants without `--overlay`). `--dry-run` drains the rings read-only. |
| `tools/export_seeds.py`, `tools/ghidra_seed.py` | Kept for the record — the seed experiments were null. |

## Open questions

- The ~15 KB string table inside `GAME.EMI` §0 — nobody has read it.
- Why `DEMO.EMI` §5 ships the JP image on the PAL English disc.
- Whether the Western builds use proportional glyph advance.
- **211 of 8,694 dispatch addresses are zero-fill** (18 `low` seeds) —
  registered native entries compiled from nothing; dirty-RAM invalidation masks
  them today.
- Text paths not yet seen live: a shop, an equipment menu, battle text.
- ~~`--include-mixed`~~ — **RESOLVED 2026-09-04, mixed is now the default.**
  See "Mixed sections are extracted by default" below.

## Environment

See [`STATUS.md`](STATUS.md) → Environment. Short form: `python` not
`python3`; prepend `/c/msys64/mingw64/bin`; run the exe from PowerShell with
`$env:`; Ghidra project at `D:\Utilities\GhidraProjects\BoF3`
(`analyzeHeadless.bat` cannot run `.py` — use `python -m pyghidra.ghidra_launch`);
prior decode work at `D:\BoFIII` (open the JSON as UTF-8).
