# Static overlay extraction — the .EMI route, proven end to end

**Status:** DONE. **All ten bands are compiled and are the current
configuration** (2026-08-31). Sections 1-7 record the original band-1 bringup;
§8-§9 record the all-bands revert and the dispatch bug that followed; §10-§12
record the three-step upstream dispatch fix that made all ten bands viable and
**supersede §8's recommendation**. Read §12 first for where things actually
stand.

[`OVERLAYS.md`](OVERLAYS.md) §5 argued that BoF3's overlays can be pulled off
the disc statically, without DMA-time capture. This document is the execution
of that plan and the measurements that confirm it.

**Headline:** the field-engine overlay is now compiled into the runtime. Over a
live run the content-validated overlay dispatcher recorded **603,391 checks and
603,391 hits — zero CRC misses**, and band 1 went from *558 interpreted PCs* to
**zero**. Capture was never needed.

## 1. The full overlay map

`tools/emi_survey.py` walks every `.EMI` on the disc, reads each TOC, and
code-tests every section whose destination lands in RAM. It reads only the
header sector plus the candidate sections, so the 259 MB of `.EMI` payload is
never staged to disk.

```bash
python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue"
```

880 containers, 6,344 sections, of which **527 are code**. They land in exactly
**ten** RAM bands — and those bands reproduce the zero-fill map in
[`OVERLAYS.md`](OVERLAYS.md) §1 almost exactly, which is the cross-check that
the TOC destinations mean what we think they mean.

| Band | Occupants | Unique | Unique bytes | Nature |
|---|---:|---:|---:|---|
| `0x80093800` | 42 | **1** | 133,124 | battle engine — 42 copies of one identical blob |
| `0x800C1800` | 40 | 35 | 74,504 | `BOSS/BOSSnnn.EMI` |
| `0x800F5000` | 3 | 1 | 8,808 | |
| `0x80117000` | 1 | 1 | 4,576 | |
| **`0x80196800`** | **1** | **1** | **227,556** | **field engine — `GAME.EMI` §0. Compiled.** |
| `0x801CE400` | 19 | 19 | 137,744 | `PLCHAR/PLPnnn.EMI` §0 |
| `0x801D0C00` | 63 | 18 | 594,824 | swap slot — `SHOP`/`STATUS`/`BATTLE`/`START` |
| `0x801EEC00` | 157 | 128 | 988,043 | |
| `0x801F2C00` | 181 | 181 | 1,078,019 | 67 of these classify `mixed` |
| `0x801F6C00` | 20 | 20 | 452,782 | `SCENARIO` |

**405 unique code sections, 3.61 MB.** Deduplicating by content matters: the
battle engine appears 42 times and is one blob, and the swap slot's 63
occupants are 18 distinct modules.

**Every one of the 405 passed the TOC preview checksum.** The offset arithmetic
is verified per section, not assumed.

### Open question closed: who owns `0x801CEEDC`

[`OVERLAYS.md`](OVERLAYS.md) §5 left this hanging — the address accounted for
91 M interpreted instructions at boot but lies past the end of `GAME.EMI` §0.
It belongs to band `0x801CE400`, whose sole occupants are the 19
`BIN/PLCHAR/PLPnnn.EMI` §0 player-character modules (max extent `0x801D0ACC`).
A later measurement puts 41 M interpreted instructions there in 10 PCs, so it
is the single largest remaining target.

## 2. Extraction

```bash
python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" --dest 0x80196800 --out analysis/overlay_captures_band1.json
```

Emits the framework's `overlay_captures.json` shape — `load_addr`, `size`,
`bytes_b64` — straight from the disc, plus provenance (`source_file`,
`source_index`, `source_md5`, `crc32`) so any capture can be traced back and
re-derived.

**Seeds are call-edge evidence read out of the bytes, never invented:**

- `static_discovery_entry_pcs` — in-region `jal` targets, plus `addiu sp,sp,-N`
  prologues that directly follow a `jr $ra` delay slot. `compile_overlays.py`
  re-validates each against its own callable test; a bad guess is dropped.
- `dispatch_entry_pcs` — PCs a live session actually *entered*
  (`entries > 0` in `analysis/observed_interp_pcs.json`). Optional and purely
  additive. A PC the interpreter merely fell through is **not** evidence of a
  callable boundary and is not passed on.

### Trap: do not seed the `GAME.EMI` §0 header table

Section 0 opens with a count word (`30`) and a pointer table, 26 of whose
entries land in-region. They look like a gift — 26 entry points the `jal` scan
cannot see. They are not:

- **0 of 26** open with a stack prologue.
- **0 of 26** are preceded by a `jr $ra` + delay slot (a clean boundary).
- They all begin with the same four words (`lui v1,0x8014` / `addiu v1,v1,0x5D50`
  / `sll v0,a1,4` / `addu v0,v0,v1`) and the preceding block ends in `jr v0`.

They are chained jump-table cases, not callable functions. The framework would
classify them `FUNCTION_POINTER_TARGET`, which is **exempt from the boundary
gate** — so seeding them would truncate their host functions. That is the
mid-function-seed softlock class. They are deliberately left out.

## 3. Compilation

```bash
export PATH="/c/msys64/mingw64/bin:$PATH"
```

```bash
python psxrecomp/tools/compile_overlays.py --static --captures analysis/overlay_captures_band1.json --game-toml game.toml --recompiler build-recompiler/psxrecomp-game.exe --runtime-include psxrecomp/runtime/include --out-dir generated --gcc C:/msys64/mingw64/bin/gcc.exe --cps
```

`--cps` is **required**: `generated/SLPS_009.90_dispatch.c` sets
`g_psx_cps_mode = 1`, so the runtime is a CPS build and the overlay code must
match it.

The seed audit came back clean on the first attempt:

```
dispatch_entry_pcs: 11          static_discovery_roots_included: 497
function_entry_pcs: 500         dispatch_interior_included: 2
                                observed_only_excluded: 0
                                unknown_excluded: 0
Unsupported instruction TODOs: 0
Unknown/bad targets: 0
recompiled: 500 functions, 500 exact identities
```

**All 497 static roots survived the compiler's own validation; none were
excluded as unknown.** 9 of the 11 observed dispatch entries were promoted to
full entries and 2 were classified `DISPATCH_INTERIOR` — the boundary gate
working exactly as designed. Zero unsupported instructions and zero bad targets
on 227 KB is itself evidence the bytes are real code correctly located: garbage
would produce noise in both counters.

## 4. Build wiring

`CMakeLists.txt` passes `GAME_OVERLAY_STATIC_C` to
`psxrecomp_add_game_runtime`. The pinned framework already supports this — no
submodule change was needed; the argument rides `UNPARSED_ARGUMENTS` into
`psxrecomp_add_runtime_target`, which appends the file and defines
`PSX_HAS_OVERLAY_DISPATCH=1`.

> **Trap, paid for.** The argument must **not** follow a *multi-value* keyword
> such as `GEN_FULL_GLOB` or `CODEGEN_SETUP_SOURCES`. `cmake_parse_arguments`
> swallows it into that list instead, and the failure is quiet and confusing:
> `overlays_static.c` still gets compiled (it lands in `GAME_GENERATED_FULL_C`),
> but `PSX_HAS_OVERLAY_DISPATCH` is never defined, so
> `psx_overlay_static_code_matches()` is `#ifdef`-ed out of `overlay_loader.c`
> and the **link** fails with hundreds of undefined references. Keep it after a
> single-value keyword such as `APP_ICON`.

A generate that changes the source list needs a CMake reconfigure before the
build, same as the shard-count rule.

## 5. Result, measured on a live run

Booted `build-dbg` with `PSX_STARVATION_TIMEOUT_US=0`, ran to frame ~2,400 at a
steady 60 fps, then queried the debug server.

**Correctness.** The game boots, renders and runs normally. `aborts: 0`,
`dispatch misses: 0`. No blue screen, no stale registration.

**`overlay_loader_status` — the direct proof:**

| Counter | Value | Meaning |
|---|---:|---|
| `static_checks` | 603,391 | content validations against the compiled overlay |
| `static_hits` | **603,391** | **all of them matched** |
| `static_crc_misses` | **0** | disc bytes ≡ RAM bytes, every time |
| `static_variant_misses` | 0 | |
| `static_address_misses` | 6,338,812 | PCs in the nine *uncompiled* bands, correctly falling through |
| `registered` / `loads` / `invalidations` | 0 / 0 / 0 | the DLL loader path is inert — OV-1 is not armed |

603,391 checks with **zero CRC misses** is the strongest statement available
that static extraction is sound: the bytes on the disc are bit-for-bit the
bytes the game executes, confirmed at runtime six hundred thousand times.

**Band 1 is no longer interpreted:**

| Band | Interpreted PCs before | after |
|---|---:|---:|
| `0x80196800` (compiled) | **558** (4,778,419 insns) | **0** |
| `0x801CE400` PLCHAR | — | 10 (41,143,320 insns) |
| `0x801D0C00` swap slot | 6 (157,786) | 60 (1,308,725) |
| `0x801EEC00` | — | 14 (4,045,604) |

> **Read the two columns as coverage, not as a speed benchmark.** They are
> different workloads — "before" was a play session into the mines, "after" is
> a boot-and-idle. The aggregate ratio moved 93.6% → 86.4% interpreted, but
> that number is not comparable across sessions and should not be quoted as a
> speedup. The meaningful result is the **zero**: not one PC in band 1 reached
> the interpreter, while 603k native entries were served there. This matches
> `overlay-status.md`'s note that Tomba's first result was correctness, not
> speed — one band of ten is not coverage.

## 5b. Band 2 — the battle engine, measured in combat

Second band through the same pipeline, run on 2026-08-30. `0x80093800`,
133,124 bytes, `BIN/BATTLE/BATTLE.EMI#15`, 42 occupants that are one identical
blob. Compiled alongside band 1 into a single `overlays_static.c`.

**Compile.** 303 static roots in, **303 functions out** — 100% acceptance, the
same as band 1. `unknown_excluded: 0`, `Unsupported instruction TODOs: 0`,
`Unknown/bad targets: 0`. Shard build `ok=2 failed=0 skipped=0`, 10,545 exact
function identities across both bands.

**The compiled region is `0x80093800`–`0x800B4003`**, not `0x800C1800` as an
earlier handoff said. `0x800C1800` is a *separate* band (7,676 bytes, 35
occupants) that happens to start near band 2's end. Do not conflate them.

**Live run.** Loaded a memory-card save, fought a battle, polled
`overlay_loader_status` across entry and exit.

| Counter | Value |
|---|---:|
| `static_checks` | 904,076 |
| `static_hits` | **904,076** |
| `static_crc_misses` | **0** |
| `static_variant_misses` | 0 |
| `static_gen_fastpath` | 903,517 |
| `static_rehashes` | 559 |
| `aborts` / dispatch misses | 0 / 0 |

Zero CRC misses again, now including the battle band: the disc bytes are the
bytes the game executes in combat too.

**Interpreted work by band, from `tools/harvest_interp_pcs.py` over a session
that included a full battle** (82.7 M tracked interpreted instructions):

| Band | Interpreted insns | Share | Compiled | Occupants |
|---|---:|---:|---|---|
| `0x801D0C00` | 24,722,487 | 29.9% | no | 19 |
| `0x801EEC00` | 16,649,969 | 20.1% | no | 128 |
| unmapped (BIOS + boot EXE) | 15,899,574 | 19.2% | — | — |
| `0x80196800` field | 13,682,184 | 16.5% | **yes** | 1 |
| `0x801CE400` PLCHAR | 7,506,056 | 9.1% | no | 19 |
| `0x801F6C00` | 3,316,456 | 4.0% | no | 20 |
| `0x801F2C00` | 879,649 | 1.1% | no | 200 |
| `0x800C1800` | 47,865 | 0.1% | no | 35 |
| **`0x80093800` battle** | **17,053** | **0.0%** | **yes** | 1 |

Band 2 carries **0.0%** of interpreted work. Combat is native.

### The battle-transition slowdown is uncompiled code, not this band

Entering and leaving combat is visibly slow. Polling `overlay_loader_status`
every 2.5 s across a transition isolates it:

```
t+ 7.5s  (battle entry)  checks+1207   address_misses+457,260
t+42.5s  (battle exit)   checks+ 124   address_misses+695,002
steady-state combat      checks+ 308   address_misses+ 28,500
```

`static_checks` **collapses** during the transition while
`static_address_misses` spikes 16–24x. The dispatcher is being consulted for
hundreds of thousands of PCs that have no compiled case, so the transition runs
almost entirely interpreted. The cost is `0x801D0C00` + `0x801EEC00` +
`0x801CE400` — 59% of all interpreted work, none of it compiled.

Compiling band 2 did not cause this. It made combat native and thereby left the
uncompiled transition code as the remaining visible cost. There is no
before/after for battle transitions, because no prior session entered a battle
— so this is not a measured regression and must not be written up as one.

**These three bands are multi-occupant, and that is a cost question, not a
safety one.** See §7.

**The `static_match` cache is not the bottleneck.** 903,517 of 904,076 checks
took the page-generation fastpath; only 559 required a re-hash. The suspicion
that overlay writes force constant CRC recomputation is disproved.

### A compiled band is not a fully native band

**13,682,184 interpreted instructions across 37 PCs sit inside band 1**, which
§5 recorded as having zero interpreted PCs. That earlier zero was measured on a
boot-and-idle; a real play session reaches entries the static call-edge walk
never saw, because they are only reached through dynamic dispatch. Band 2 has
the same gap at a much smaller scale — 7 PCs, 17 K instructions.

Static discovery yields the statically reachable call graph, not the whole
module. Closing these gaps is a separate axis of work from adding new bands,
and `harvest_interp_pcs.py` against a live session is what finds them.

## 6. What's next

The remaining nine bands are already enumerated in
`analysis/emi_sections.json`; `tools/extract_overlays.py --dest <addr>` will
emit any of them today. In value order:

1. ~~**`0x80093800` (battle engine)**~~ — **done, see §5b.** 303/303 functions,
   zero CRC misses, 0.0% of interpreted work.
2. **`0x801CE400` (PLCHAR)** — 19 occupants, 137 KB total, and it owns
   `0x801CEEDC`, the largest single interpreted PC. Compile all 19 as variants;
   see §7 for why this needs no unregistration work.
3. **`0x801D0C00`** — 18 distinct occupants, 595 KB total, and the single
   biggest share of interpreted work (29.9%).

Band 2 in the handoff's numbering is item 3 here. Item 1 is the better next
step: it carries band 1's safety profile and covers all battle code.

## 7. OV-1 does not apply to this path

> **Amended 2026-08-31 — see §10.** The claim below that the gate runs "at
> **every** dispatch" was true of the generated code but not of the gate, which
> short-circuited on a page generation that never moved for static ranges. It
> holds only from `psxrecomp` commit `aa6fa2c9`. The section's *conclusion* —
> multi-occupant bands need no register/unregister mechanism — is unchanged.

`psxrecomp/docs/overlay-status.md` OV-1 — stale registration, the
village→overworld blue screen — is a defect in the **DLL loader**
(`[runtime] overlay_cache`). That loader registered 88 functions once, never
re-evaluated them, and when the game reused `0x800E7000` for different content
it dispatched into stale village code. **The loader is inert here**:
`registered`, `loads` and `invalidations` all read 0.

The static path is content-addressed at **every** dispatch.
`compile_overlays.py:generate_overlay_dispatch` emits one `case` per address,
with each occupant as its own CRC-guarded variant:

```c
case 0x801CE400u:
    psx_ov_static_checks++;
    if (psx_overlay_static_code_matches(ranges_A, 1u, 0xAAAAAAAAu)) {
        psx_ov_static_hits++; variant_A(cpu); return 1;
    }
    psx_ov_static_variant_misses++;
    if (psx_overlay_static_code_matches(ranges_B, 1u, 0xBBBBBBBBu)) {
        psx_ov_static_hits++; variant_B(cpu); return 1;
    }
    psx_ov_static_variant_misses++;
    return 0;   /* nothing resident matches -> interpreter */
```

`psx_overlay_static_code_matches()` (`overlay_loader.c:576`) hashes the live RAM
bytes and compares against the CRC the function was compiled from. **The CRC
gate is the dispatch condition.** Stale native code cannot run, because a
function whose bytes are no longer resident fails its own guard. Nothing is
"registered", so nothing can go stale and there is nothing to unregister.

**Consequence:** a multi-occupant band needs no new mechanism for
*correctness*. But the dispatch **cost** question is now measured, and the
answer is that compiling everything is a net loss. See §8.

This section exists because an earlier revision of the handoff told the next
session to "solve OV-1 unregistration first". That was wrong, and it would have
cost real time.

## 8. All-bands was tried and reverted — measured 2026-08-30

> **SUPERSEDED 2026-08-31 — see §12.** The conclusion below ("do not compile
> all bands") was correct *for the dispatch design of the time*. Steps 1-3 of
> the upstream fix removed both costs it identifies, and all ten bands are now
> the fastest configuration measured and the one in use. The measurements below
> stand as a record of the old design; the recommendation does not.

**Result (2026-08-30, superseded): do not compile all bands with the dispatch
design of the time.** Reverted
to the two-band build the same session. Every capture file is kept, so any
configuration rebuilds in minutes.

### What was built

| Build | Captures | Bytes | Fn identities | Dispatch cases | Variants | Generated C | Exe |
|---|---:|---:|---:|---:|---:|---:|---:|
| Two-band | 2 | 360,680 | 10,545 | 10,547 | 10,547 | — | 76 MB |
| Shallow | 96 | 1,633,918 | 39,055 | 29,500 | 36,287 | 127 MB | 120 MB |
| All-bands | 338 | 3,522,652 | 69,564 | 39,036 | 66,276 | 271 MB | 178 MB |

"Shallow" excludes the two deepest bands, `0x801EEC00` (128 occupants, 124 of
them `BIN/BMAGIC`) and `0x801F2C00` (114, the `WORLD00`–`WORLD04` area
scripts). Every other band is included; max chain depth 35.

Compilation itself is **fast** — extraction plus compile is a few minutes even
for 338 captures. Compile time is not the constraint.

### Finding 1 — deep variant chains are real, and severe

On the memory-card screen the all-bands build recorded **41.25 checks per
successful hit**: 4,539,360 checks and 4,429,315 *failed* variant checks every
2 seconds (2.27 M checks/sec). The resident occupant sat ~41 deep in one of the
big chains, so every call walked ~41 failed CRC gates first. Idle was 1.09
chk/hit; the field and startup were 1.09-2.66. Chain depth only bites where a
deep band is the hot one.

Cutting the two deep bands fixed exactly that: **41.25 → 4.28 chk/hit**, and
check volume fell from 4,539,360 to ~10,400 per 2 s — a 430x drop.

The match cache is *not* implicated: `static_rehashes` stayed at 0 through all
of it, and working set was flat. The `STATIC_MATCH_CACHE_CAP 4096` table
(`overlay_loader.c:560`) has no eviction and would degrade badly if saturated,
but 66,276 variants never saturated it in practice. **Predicted cliff, did not
occur — do not go optimising that cache without measuring first.**

### Finding 2 — the dominant cost is total compiled volume, not chain depth

Cutting the deep bands barely helped the boot screens. FPS on the Capcom logo,
user-observed on the same screen across three builds:

| Build | Dispatch cases | Capcom screen | Memory-card read |
|---|---:|---:|---:|
| Two-band | 10,547 | **~18 fps** | **~20 fps** |
| Shallow | 29,500 | **~9 fps** | **~9 fps** |
| All-bands | 39,036 | **~5 fps** | **~5 fps** |

Monotonic in compiled volume, not in chain depth — the shallow build has
max-depth 35 and still lost half the frame rate.

**During those screens `static_hits` is 0.** No overlay code is executing at
all. We are paying for compiled code that never runs. `psx_overlay_dispatch` is
consulted on every interpreted entry (~92,500/sec at boot) and is a `switch`
over tens of thousands of sparse cases; the plausible mechanism is that the
dispatcher's own code and jump table evict cache on every call, so the
*interpreter* slows in proportion to how much overlay code was compiled.
~~**The correlation is measured; the cache-eviction mechanism is inference and
has not been proven.**~~

> **Resolved 2026-08-31 — see §10, fixed in §11.** The mechanism is now
> measured, and it is narrower than guessed: the cost is the **address-miss
> fall-through**, not compiled code evicting cache in general. During a battle-transition stall the
> dispatcher is consulted ~264,000x/sec — 49x the field baseline — while
> `checks` collapses to 227/sec, i.e. ~1,160 fruitless `default:` walks per real
> lookup. That is why cost tracks case count rather than chain depth: every band
> added widens the miss path. O(1) address lookup is the fix.

### Finding 3 — the Capcom screen was always slow

It runs at **~18 fps (0.30x) in the two-band build too**, and memory-card
reads sit at ~20 fps there. Both are pre-existing, unrelated to overlay
compilation, and nobody has investigated either. Do not chase them as overlay
regressions — but they are real, and they are the largest user-visible
slowdowns left outside battle transitions.

### What the original hardware did, and why this is self-inflicted

The PS1 had no dispatch cost here. The game CD-reads `AREA038.EMI` §13 into
`0x801F2C00` and then executes `jal 0x801F2C00` — a direct jump to a
link-time-fixed address. It never asks "which of 114 occupants is resident",
because it loaded the thing three instructions ago; identity is implicit in
control flow. The only map that ever existed is the file→destination
assignment, and that *is* the `.EMI` TOC we already read.

Our dispatcher discards that provenance and pays to rediscover it by hashing
RAM on every call. The fix is therefore not a map to recreate but a **residency
signal**, in two parts, both upstream in the submodule:

1. **Memoize the resident variant per band.** The runtime already tracks page
   generations (`overlay_watch_pagegen_sum`) and already watches writes into
   overlay regions. A band's generation changing *is* the load event: clear the
   memo, do one full walk to identify the new occupant, then remember it. Every
   later call is a single CRC check — an assertion, not a search. Kills
   Finding 1.
2. **Make address lookup O(1)** rather than one monolithic switch over every
   compiled entry. Kills Finding 2.

With both, all-bands becomes viable. Without them, band count is capped by the
global tax, and **two bands is the best measured configuration.**

## 9. Band 3 (PLCHAR) — compiled, neutral, and it exposed a dispatch bug

> **RESOLVED 2026-08-31 — and the original diagnosis below was wrong.**
> `0x801CEEDC` is an **interior** address (a mid-function store `sb v0,0x3BB0($at)`,
> in `static_discovery_entry_pcs` of **zero** occupants), not a function start.
> The "it is a real `case` in `psx_overlay_dispatch`" claim below conflated the
> 184 interior CPS `case ...: goto block_` resume labels with a real dispatch
> registration. On the band-3 build it was measured on, `0x801CEEDC` was **not a
> registered key**, so the dispatcher returned via the **address-miss** path —
> which touches neither `variant_misses` nor `crc_misses`, exactly the zeros seen.
> There was no bypass of the line-2796 call site.
>
> The Axis B feedback loop fixed it: observed with `entries > 0` →
> `extract_overlays.py` added it as a `dispatch_entry_pc` →
> `compile_overlays.py` emitted an **alias entry**
> (`ov_..._alias_body_801CED1C(cpu, 0x801CEEDC)`, jumping into the middle of host
> `func_801CED1C`). The current all-bands build registers it
> (`psx_ov_entries[] = { 0x801CEEDCu, 12870, 6 }`, in `psx_ov_hash_addr[]`).
> **Measured on the fresh build in a live boss fight (savestate slot 4, attacks
> executing): `0x801CEEDC` interprets 0 instructions and the entire PLCHAR band
> is 0% of interpreted work (was 60.5%).** Since the old build proved the
> function is invoked in combat, zero interp = native dispatch. The prose below
> is kept for the record; do not act on its "unresolved / needs instrumentation"
> conclusion.

Tried after §8, as the cheap targeted alternative to all-bands: two bands plus
`0x801CE400` only. 21 captures, 498,424 bytes, **21/21 shards built, 0 audit
failures**. Dispatch cases 10,547 → **11,963 (+13%)**, exe 76.1 → 81.6 MB.

**Performance: unchanged. No gain, no regression.**

| Screen | Two-band | Three-band |
|---|---:|---:|
| Capcom logo | ~18 fps | ~17-18 fps |
| Memory-card read | ~20 fps | ~20 fps |
| Battle transition | ~20 fps | ~20 fps |

The +13% case growth confirms §8's model from the other direction: the global
dispatch tax is real but roughly proportional, so a small band is nearly free
(the shallow build's +180% cost half the frame rate). Health was perfect —
`chk/hit` 1.00, `static_variant_misses` 0, `static_crc_misses` 0, aborts 0 — so
PLCHAR's 19 occupants resolve on the first variant and chain depth is a
non-issue here.

### The real finding: a compiled entry that is never dispatched

`0x801CEEDC` was the target — 70.5 M interpreted instructions, ~45% of all
interpreted work, ~417,000 instructions per entry. After compiling it:

- It **is** a real `case` in `psx_overlay_dispatch` (verified inside the
  function body, not merely a CPS interior resume label — `case 0x801CEEDCu:
  goto block_...` lines appear 184 times as interior labels and are *not*
  evidence of an entry; check the dispatch function specifically).
- Its band is demonstrably live: hundreds of thousands of checks, all hits.
- **It is still interpreted**: 85,929,659 instructions over 206 entries, and
  total native execution *fell* (27.9 M → 24.2 M).

`static_variant_misses` and `static_crc_misses` are both **0**, so the CRC gate
never *failed* — it was never *consulted* for this address. The interpreter is
reaching `0x801CEEDC` by a path that bypasses the B-2 overlay-dispatch check at
`dirty_ram_interp.c:2795` (inside `dirty_ram_dispatch_inner()`), which is the
only call site of `psx_overlay_dispatch` in the runtime.

**Unresolved, and it needs upstream instrumentation.** Until it is understood,
*compiling a band does not guarantee its hot function runs native* — which
makes "compile more bands" unreliable as a performance strategy independent of
the §8 dispatch-cost problem. Verify per-PC with `harvest_interp_pcs.py` after
every band addition; do not infer success from `static_hits`.

### Post-band-3 interpreted profile

| Share | Insns | PCs | Region |
|---:|---:|---:|---|
| 60.5% | 89,146,711 | 10 | band 3 PLCHAR — **compiled, still interpreted** |
| 16.2% | 23,890,004 | 25 | kernel/BIOS RAM (LLE) |
| 13.7% | 20,238,188 | 20 | `0x801EEC00` (uncompiled) |
| 7.2% | 10,572,889 | 183 | `0x801D0C00` (uncompiled) |
| 0.9% | 1,324,753 | 10 | band 1 field (compiled) |
| — | 0 | 0 | band 2 battle (compiled) — fully native |

Note the kernel/BIOS share: startup logs `bios_hle kernel-call tier unavailable
on OPENBIOS (no DeliverEvent anchor); kernel calls stay LLE`. That is a real
16-18% of interpreted work and an untouched axis, but it is **not** the cause
of the transition slowdowns — that hypothesis was tested and rejected.

## 10. The static path had no residency signal — fixed 2026-08-31

**Status:** fixed upstream, verified on a live run. `psxrecomp` commit
`aa6fa2c9`, originally on fork branch `fix/static-overlay-residency-signal` off
the then-pin `f24b7e5d`; **merged into `mstan/master` via #289 on 2026-09-01**
together with §11 and §12, and the title now pins upstream master directly.

### The defect

`§8` prescribed memoizing the resident variant per band, on the grounds that
"page generations are already tracked (`overlay_watch_pagegen_sum`); a
generation change *is* the load event." That load event never fired.

`overlay_page_gen[pg]` is incremented only for pages set in
`overlay_watch_bitmap` (`memory.c:784`), and the only two callers of
`overlay_watch_set_range` were `cand_register()` (`overlay_loader.c:1044`) and
`rebuild_lazy_manifest_index()` (`overlay_loader.c:1530`) — **both in the DLL
loader, which is inert for this title**.

So every static overlay code range was unwatched. `overlay_watch_pagegen_sum`
returned a constant, and the generation fast path in
`psx_overlay_static_code_matches` (`overlay_loader.c:611`) answered every
dispatch after the first from its cached result. The consequences:

- **The CRC gate was consulted once per variant per process**, not once per
  code change. The only thing that ever cleared the cache was a savestate
  restore (`overlay_loader_resync_validation_after_restore`,
  `overlay_loader.c:2859`).
- **Cached negatives were permanent too.** A variant evaluated *before* its
  content finished loading cached `matches = 0` and could never re-evaluate —
  it fell to the interpreter for the rest of the process even once its bytes
  were resident.

This has almost certainly not bitten a two-band build: band 1 has a single
occupant and band 2's resident never changed in any measured run, which is
consistent with the `static_crc_misses: 0` reported in §5b. It becomes live the
moment a multi-occupant band is compiled.

### This corrects §7

§7 states the static path "is content-addressed at **every** dispatch" and that
"the CRC gate is the dispatch condition". That was true of the *generated code*
— which does call the gate on every dispatch — but not of the gate itself,
which short-circuited on a frozen generation. The claim holds only after
`aa6fa2c9`. §7's conclusion is unchanged: multi-occupant bands still need no
register/unregister mechanism.

### The fix

Arm the page watch over a variant's ranges on the cold path, before hashing
them. Arming only sets bitmap bits and does not advance a generation, so the
`gen_sum` already computed for the cache write stays valid.

The mechanism this depends on was checked before relying on it: overlays are
loaded by **CD DMA**, and the generation bump lives in the CPU store hook. The
DMA loop writes word-by-word through `psx_write_word` (`dma.c:1137` →
`memory.c:1670`), so a load does advance the generation of every page it
touches.

### Verified live, two-band build

| Measure | Result |
|---|---:|
| `gen_fastpath` / `checks` | **99.93%** |
| `static_rehashes` | 479 at boot, growing only on real writes |
| `static_crc_misses` | 43, flat all session |
| `static_variant_misses` | 36,400, flat all session |
| hit rate | 98.2% |

**Arming costs nothing on the hot path.** The gate re-fires on load events and
nowhere else. Across a battle transition, `rehash` stepped 1514 → 1651 in ~2 s
against a background of ~10 per 2 s window — the load event, which before this
fix could not have occurred at all.

`crc_misses` holding flat through that burst is the **correct** result, not a
null one: band 2's compiled occupant *is* the battle engine, so after the load
the bytes legitimately match again. Re-hash and match is right. A `crc_miss`
becomes expected only once a band whose resident occupant actually changes
identity is compiled.

Raw traces: `analysis/overlay_watch_arm_trace_2026-08-31.csv` (1 s samples over
field → encounter → stall → battle) and `..._boot_2026-08-31.csv`.

### §8's inferred mechanism is now measured, and it is more specific

§8 Finding 2 said the cache-eviction explanation "is inference and has not been
proven." The live trace pins it to a specific path — **the address-miss
fall-through**, not compiled code in the abstract:

| Phase | fps avg | worst frame | `addr_miss`/s | `checks`/s |
|---|---:|---:|---:|---:|
| Field (idle) | 60.0 | 25 ms | 5,400 | ~3,000 |
| Memory-card read | ~23 | — | 239,000 | 2,600 |
| **Battle transition stall** | **45.2** | **204.6 ms** | **264,000** | **227** |

During the stall `psx_overlay_dispatch` is consulted ~264,000 times a second —
**49x** the field baseline — and `checks` collapses to 227/s. That is ~1,160
fruitless lookups for every real one, each a walk into the `default:` case of a
sparse `switch` over 10,547 entries. `emu_cpu_ms_avg` rises 16.6 → 22.1 ms in
lockstep, so the cost is CPU-side, not GPU.

This is why cost tracked dispatch-case count rather than chain depth in §8: the
dominant term is the *miss* path, which every band addition makes wider.
**Making address lookup O(1) is therefore the fix, and this is the number to
beat.**

### What this does NOT explain

§9's `0x801CEEDC` bypass is untouched and still open. There
`static_variant_misses` was 0, meaning the dispatch `case` was never *reached* —
a different defect from a gate that answers from cache. Do not conflate them.

### Unverified, watch for it

Two things observed once, with no controlled comparison. Do not cite either as
a result:

- The user reported the battle transition felt **much quicker** while dipping to
  the same depth. Depth is set by the address-miss storm, which this fix does
  not touch, so unchanged depth is expected. A duration improvement would be
  consistent with the cached-negative lockout being released — but there is no
  before-duration baseline, so this is a hypothesis.
- **No freeze dumps were written this launch**, against the ~160 MB/launch the
  handoff records. Plausibly the `slow_frames` false positive not tripping, but
  it is a single observation.

## 11. O(1) dispatch — step 2, measured 2026-08-31

**Status:** done and measured. `psxrecomp` commit `69d783f5` on
`fix/static-overlay-residency-signal`. Parent gitlink still NOT bumped.

### The change

`generate_overlay_dispatch` emitted one `case` per address. GCC compiles a
sparse switch over tens of thousands of 32-bit values into a binary search tree
plus a jump table far larger than cache, so **every** fruitless call — the
common case — walked ~log2(N) compares through cold memory.

Replaced with a compile-time open-addressed hash table. Two parallel `uint32`
arrays (`psx_ov_hash_addr`, `psx_ov_hash_idx`) mean a miss touches one table and
returns; the entry and variant arrays are only reached on a real hit. Load
factor is held at ≤ 0.5. Three-band build: 11,913 addresses in a 32,768-slot
table, load 0.36, max probe 10.

Generated C shrank 44.8 MB → 30.5 MB.

### Behaviour is unchanged, and that was verified, not assumed

- On identical captures the two generators emit **the same address set and the
  same variant count** — 11,913 / 12,522 for three-band, 10,545 / 10,545 for
  two-band. Zero dropped, zero added.
- The C and Python hash functions agree on **all 524,288** word-aligned
  addresses in the 2 MB RAM window. This matters: had they disagreed, every
  lookup would miss, everything would fall to the interpreter, and the game
  would still *run* — just slowly. A silent failure.
- Every table entry resolves to its own index; variant runs tile the variant
  array exactly; **no** non-entry address produces a false hit.
- Per-address variant order is preserved, so the CRC gate still selects the
  resident occupant in the same order.

### Measured — headless A/B, identical protocol

Three bands, savestate slot 6, 200 s, `tools/headless_ab.py`. Headless is
uncapped, so VSync throughput measures raw emulation speed rather than being
clamped at 60.

| | mean | p1 | p50 | frames / 199 s |
|---|---:|---:|---:|---:|
| Switch | 106.5 | 93.9 | 107.9 | 21,156 |
| **Hash table** | **113.2** | **105.2** | **113.7** | **22,508** |

**+6.3% throughput overall, +12% at p1.** The gain is largest at the low end,
which is what a fix to the miss path should look like.

The transition tells the story better than the mean. Both runs hit the same
transition at t≈32-38 s:

| Build | address misses | throughput |
|---|---:|---:|
| Switch, window 1 | 160,970/s | **63.9 fps** |
| Switch, window 2 | 141,966/s | 93.9 fps |
| **Hash table, single window** | **307,978/s** | **131.3 fps** |

The table absorbs the same storm at **twice the miss rate while running twice
as fast**, and compresses it from three sampling windows to two — the
transition costs less wall time. Per-miss cost has collapsed.

Traces: `analysis/dispatch_ab_A_hashtable_3band_2026-08-31.csv` and
`..._B_switch_3band_2026-08-31.csv`.

### Two corrections this run forced

**The build on disk was never the two-band configuration.** `§8` and `STATUS.md`
both say "two bands is the best measured configuration and is what is built".
The `generated/overlays_static.c` actually present — the one the user has been
running, and the one §10's numbers were measured on — contained **three**
namespaces: `ov_00093800_` (battle), `ov_00196800_` (field) and `ov_001CE400_`
(PLCHAR). It was the §9 three-band build, at 11,913 addresses / 12,522 variants.
Verify with `grep -o "ov_00[0-9A-F]\{6\}_" generated/overlays_static.c | sort -u`
before trusting any claim about which bands are live.

**`savestate load` over TCP works headless.** The handoff records
`tools/playsession.py state load` as broken — exceeding the I/O thread's 30 s
bound and leaving the listener dead. Under
`--headless --no-launcher --game game.toml` it returned **immediately**,
`last_ok=1`, `generation=1`, listener alive, and the game ran on. Either the
failure was specific to the windowed path or it has since been fixed. Headless
savestate loading is now the basis of the A/B harness.

### Headless caveat

`frame_perf` needs GL frames and is unavailable headless ("no frame_perf
samples"). Use the VSync counter at `0x8018603C` via `read_ram` instead —
emulated frames per wall second. It is renderer-independent *and* uncapped,
which makes it a better dispatch-cost metric than fps.

## 12. Residency memo, and all-bands reinstated — 2026-08-31

**Status:** step 3 done. `psxrecomp` commit `70153175`. **All ten bands are now
the configuration**, reversing §8. Parent gitlink still NOT bumped.

### The memo

Walking a band's occupants and CRC-gating each in turn is how we rediscover
what the hardware knew for free. On a deep band that walk dominates. The memo
remembers which occupant last satisfied each address and tries it first.

**It is a hint, never an authority.** Every call still passes through
`psx_overlay_static_code_matches()`, so a band that swapped occupants fails the
memo and falls into the full walk, which re-seeds it. The memo only reorders
candidates, so correctness is unchanged by construction.

### It pays exactly where it was aimed, and nowhere else

Measured two ways, because the first workload nearly produced the wrong
conclusion.

**Savestate workload** (slot 6, 200 s — combat, then scripted scenes):

| build | throughput | p1 | chk/hit | variant misses |
|---|---:|---:|---:|---:|
| 3-band switch | 106.5 | 93.9 | 1.000 | 0 |
| 3-band table | 113.2 | 105.2 | 1.000 | 0 |
| 3-band table + memo | 113.7 | 106.0 | 1.000 | 0 |
| all-bands table | 115.1 | 107.6 | 1.055 | 122,126 |
| all-bands table + memo | 114.2 | 106.9 | 1.019 | 41,216 |

On this workload the memo looks **neutral to slightly negative**. Chains are
already shallow (1.019-1.055), so there is nothing to shorten and the extra
branch costs a little. An early reading of this table concluded the memo was
not a win. That conclusion was wrong — it was the wrong workload.

**Boot workload** (140 s, no savestate) is where deep chains actually bite:

| build | throughput | chk/hit | variant misses |
|---|---:|---:|---:|
| 3-band table | 107.9 | 1.060 | 36,400 |
| all-bands table | **99.0** | **1.479** | **368,479** |
| all-bands table + memo | **131.4** | **1.069** | **81,505** |

**+33% throughput and 4.5x fewer wasted gate calls.** Without the memo,
all-bands is *slower than three bands* at boot (99.0 vs 107.9) — §8's
regression, surviving the O(1) fix. With the memo it is the fastest build
measured.

**Lesson worth keeping:** a dispatch change must be measured on a
variant-heavy workload as well as a hit-heavy one. The two disagree in sign.

### §8 is overturned

All ten bands now beat three bands on both workloads — 131.4 vs 107.9 at boot,
parity on the savestate run. The relationship has inverted: it used to cost
frame rate to compile more code, and now more compiled code means more native
execution because dispatch is finally cheap.

All-bands build: 34,092 dispatch addresses, 66,276 variants (matching §8's
count exactly), 131,072-slot table at load 0.26, max probe 8. Generated C
259 MB, exe 180 MB.

### What is NOT established

Single runs, no repeats. **Differences under ~2% are not distinguishable** —
treat the 3-band table / +memo / all-bands-table rows on the savestate workload
as a tie.

- **§8 Finding 1's actual worst case is still untested.** The 41.25 chk/hit was
  measured on the **memory-card screen**, which neither harness visits. The
  memo is the fix aimed at it, and boot shows it working on the same *kind* of
  chain, but the specific screen has not been re-measured.
- **The Capcom logo is untested and unaffected.** §8 Finding 3 already found it
  slow (~18 fps) in the two-band build, i.e. before any of this. During the
  pre-hit boot window the dispatcher runs at only **~750-1,100 address
  misses/sec** — against ~264,000/sec at a battle transition — so dispatch is
  not what makes that screen slow. Do not attack it from this direction; it is
  an uninvestigated, separate problem.
- **Absolute numbers are not comparable to §8's.** §8 quotes windowed fps from
  user observation; these are headless VSync throughput, uncapped. Only
  build-vs-build within the same harness is meaningful.
- Boot phases do not align perfectly across runs, so the boot rows compare
  equal wall windows, not equal game progress.

Traces: `analysis/dispatch_ab_*.csv`, `analysis/boot_*.csv`.

## Reproducing

The capture files live in `analysis/`, which is **gitignored** — a fresh
checkout must regenerate them before it can build overlays.

```bash
python tools/emi_survey.py "isos/Breath of Fire III (Japan).cue"
```

All bands — omit `--dest` to take every RAM destination (this is the current
configuration):

```bash
python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" --out analysis/overlay_captures_all.json
```

```bash
python psxrecomp/tools/compile_overlays.py --static --force --captures analysis/overlay_captures_all.json --game-toml game.toml --recompiler build-recompiler/psxrecomp-game.exe --runtime-include psxrecomp/runtime/include --out-dir generated --gcc C:/msys64/mingw64/bin/gcc.exe --cps
```

> **This exits with code 2, and that is expected.** 335 of 338 shards build; the
> three failures are the documented `UNSUPPORTED_INSTRUCTION` cases at
> `0x800C1800` (BIN/BOSS, x2) and `0x801F2C00` (AREA038) — data being walked as
> code. The output file is still written and is correct. Any automation around
> this command must not treat exit 2 as fatal without checking which shards
> failed.

A single band, for comparison work:

```bash
python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" --dest 0x80196800 --out analysis/overlay_captures_band1.json
```

```bash
python tools/extract_overlays.py "isos/Breath of Fire III (Japan).cue" --dest 0x80196800 --out analysis/overlay_captures_band1.json
```
