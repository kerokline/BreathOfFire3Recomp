# Why `generated/` is 1.6 GB — measured, 2026-09-06

Status: **EVIDENCE**. Numbers measured on the current `generated/` tree
(`fix/static-fragments-per-variant`, 819 files, 1.6 GB). Every figure below is
reproducible from `analysis/emi_sections.json` plus a scan of
`generated/overlays_static_*.c`.

## The headline

| | MIPS bytes | Generated C | Expansion |
|---|---:|---:|---:|
| Main EXE (`SLPS_009.90_full_*.c`, 36 shards) | 1.42 MB | 66 MB | **47x** |
| Overlays (`overlays_static_*.c`, 780 shards) | 3.70 MB | 1.64 GB | **~440x** |

Same recompiler, same `strict = true`. The overlay path expands ~9x worse than
the main EXE path. That gap is the entire size problem.

Of the overlay output, **331 MB is whole-image translation units and 1,225 MB
(79%) is fragments** — 395 of the 779 shards contain only `ov_frag_*` symbols.

## Falsified: it is not occupants-per-band

The obvious hypothesis was that BoF3 goes "wide" because its overlay inventory
is shallow and crowded (405 unique code images landing on **10 destination
addresses**, 309 of them on just two). Under that theory, cost would scale with
occupants x band extent.

**It does not.** Measured per band:

| Band | Occupants | MIPS | Generated C | Expansion | Frag entries | Bodies | Unique | Dup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `0x801EEC00` | 128 | 965 KB | 770 MB | **798x** | 9,415 | 88,726 | 19,003 | 4.7x |
| `0x801F2C00` | **181** | 1,053 KB | 280 MB | 266x | 6,558 | 57,270 | 15,739 | 3.6x |
| `0x801F6C00` | 20 | 442 KB | 224 MB | 507x | 1,779 | 76,205 | 10,742 | 7.1x |
| `0x801D0C00` | 18 | 581 KB | 197 MB | 339x | 1,323 | 38,379 | 6,671 | 5.8x |
| `0x801CE400` | 19 | 135 KB | 25.5 MB | 189x | 418 | 4,861 | 2,251 | 2.2x |
| `0x80196800` | 1 | 222 KB | 20.6 MB | **93x** | 19 | 106 | 80 | 1.3x |
| `0x800C1800` | 35 | 73 KB | 16.9 MB | 232x | 666 | 2,666 | 1,285 | 2.1x |
| `0x80093800` | 1 | 130 KB | 11.9 MB | **92x** | 40 | 676 | 374 | 1.8x |
| `0x800F5000` | **1** | 9 KB | 5.6 MB | **622x** | 30 | 1,576 | 198 | 8.0x |

The decisive case is `0x800F5000`: **one occupant**, so band sharing is
impossible, and it still expands 622x. Meanwhile the 181-occupant band is one
of the *cheapest* at 266x. Occupancy and expansion are uncorrelated.

**Consequence: per-occupant attribution — the open item carried in
[`fragment-fix-perf-ab`](STATUS.md) and the framework's AOT plan — would recover
close to nothing on this title.** It is aimed at a cost that is not the cost.

## What actually drives it: interior-entry fragmentation

Expansion tracks **fragment entries per KB of code**. The two cheapest bands
(92x, 93x) are exactly the two emitted as whole images with almost no fragments
— and 92x is the honest whole-image baseline for overlay code, against the main
EXE's 47x.

Fragment symbols are named `ov_frag_<band>_<crc>_<entry>_func_<pc>`. Each
interior entry point becomes **its own translation unit that re-emits its entire
forward reachable closure**. From `overlays_static_0578.c`
(`ov_frag_001EEC00_D6C0ABF8_fragments`):

```
frag @801EF148 -> 801EF148, 801EF178, 801EF1A0, 801EF1AC, 801EF1B4, 801EF1D4, ... 801EF27C
frag @801EF15C -> 801EF15C, 801EF178, 801EF1A0, 801EF1AC, 801EF1B4, 801EF1D4, ... 801EF27C
frag @801EF184 ->           801EF184, 801EF1A0, 801EF1AC, 801EF1B4, 801EF1D4, ... 801EF23C
frag @801EF1D0 ->                                         801EF1DC, 801EF200, ... 801EF23C
```

A suffix chain. Each fragment additionally carries private copies of the
`psx_lwl` / `psx_lwr` / `psx_swl` / `psx_swr` helpers.

`0x801EEC00` runs ~9,415 fragment entries over 965 KB of code — **one entry per
~26 instructions** — averaging 9.4 bodies per entry. `0x801F6C00` averages 42.8.

## The dedup estimate

Deduplicating identical `(crc, pc)` bodies across fragments within a band, and
emitting the load/store helpers once per variant instead of once per entry:

**1,556 MB -> ~1,148 MB. Only 1.4x smaller.**

Body duplication is 4.7x by *count* but the duplicated bodies are small; the
byte mass sits in bodies emitted once or twice. Tail dedup is real and worth
having, but it is not the win.

## Where the win would be

Emit **one translation unit per variant**, with interior entries as labels into
it, instead of one unit per entry re-emitting a closure. That is what the two
whole-image bands already do, and they sit at 92x.

Naive extrapolation of the 92x baseline over 3.70 MB of overlay MIPS gives
~340 MB. That is **an untested prediction, not a measurement** — it assumes
interior entries can be reached by label without the closure duplication, which
nobody has demonstrated. Treat 150-350 MB as the plausible band and measure
before planning against it.

## Why this is a framework finding, not a BoF3 one

Nothing above depends on BoF3's disc layout. The multiplier is a property of
how `compile_overlays.py --static` emits interior entry points, and it fires on
a single-occupant band as hard as on a 128-occupant one. Any title whose
discovery pass demands many interior entries pays it.

Kept in title docs for now (2026-09-06). It belongs in
`psxrecomp/docs/AOT_OVERLAY_PLAN.md` once the per-variant-with-labels claim is
either demonstrated or refuted.

## 2026-09-06 addendum: the i-cache attribution is unproven

The ~9-10% headless throughput cost recorded for the 950 MB binary
([`fragment-fix-perf-ab`](STATUS.md)) was attributed to i-cache pressure. That
attribution has NOT been confirmed, and one measurement now complicates it.

Section sizes, `size -A` on the two trees:

| Section | `build-relprof` (RelWithDebInfo, tools ON) | `build-release` (Release, tools OFF) |
|---|---:|---:|
| `.text` | 159.7 MB | **215.7 MB** (+35%) |
| `.debug_info` | 432.3 MB | 0.36 MB |
| file on disk | 918 MB | 287 MB |

**Most of the 918 MB is DWARF, which is never executed and never enters the
i-cache.** The executable code is 35% *larger* in Release, not smaller. So
"the binary is huge" and "the hot code footprint is huge" are different claims,
and only the second one could cost throughput.

Windowed fast-forward measurements, both builds fully uncapped
(`PSX_FAST_FORWARD_SPEED=max` + `PSX_VSYNC=0`, FF latched):

| Scene | `build-relprof` | `build-release` | ms/frame | ratio |
|---|---:|---:|---:|---:|
| Intro / memcard reads | 1.75x | 5.0x | 9.53 -> 3.34 | **2.86** |
| Start screen | 6.0x | 16.0x | 2.78 -> 1.04 | **2.67** |
| Transitions / areas | 3.5x | 8.0x | 4.77 -> 2.09 | **2.29** |
| Combat | 4.5x | 9.5x | 3.71 -> 1.76 | **2.11** |

**Both builds must be uncapped or the numbers are worthless.** Two limiters
masquerade as results:

1. The FF pacer defaults to 4x (`PSX_FAST_FORWARD_SPEED`, `main.cpp:602`).
2. With FF active, `present_every` is 4 and driver vsync owns cadence on a
   60 Hz panel (`present_vsync_owns_cadence`, `main.cpp:2930`), so a blocking
   swap every 4th guest frame pins the run at exactly 4 x 59.94 = 240 fps
   regardless of scene or build. An early Release run read a flat 3.99-4.01x
   across intro, card screen and combat for this reason alone.

### Debug-tool overhead is multiplicative, not per-frame

Testing a fixed ms/frame offset against a constant ratio over the four scenes:

- offset model: 1.74-6.20 ms, 3.57x spread, **CV 0.66**
- ratio model: 2.11-2.86x, 1.35x spread, **CV 0.14**

The ratio is ~5x more consistent, so the cost scales with work done rather than
arriving once per frame. That points at the per-call and per-block hooks
(`debug_server_log_call_entry`, `cyc_watch_observe` at `debug_server.c:2069`),
not the per-frame ones (`disp_ring_capture`, watchpoint checks).

**Practical rule: `build-relprof` x ~2.5 estimates `build-release`,** within
about +/-15% across these scenes.

The residual gradient is itself evidence: the ratio is highest where work per
call is lowest (2.86 on the card-poll screen, where `card_mgr_trace_record`
fires on a `TestEvent` spin the source describes as re-entering "millions of
times") and lowest where the engine does real work per call (2.11 in combat).

### Three trees: both axes are multiplicative, and they anti-correlate

Adding `build-dbg` (`-O0`, tools ON) gives a second, independent factor.
dbg -> relprof is **purely the optimizer** (tools on in both); relprof ->
release is **tools removal plus `-O2`->`-O3`**. All uncapped as above.

| Scene | dbg | relprof | release | dbg->rp | rp->rl | dbg->rl |
|---|---:|---:|---:|---:|---:|---:|
| Intro / Capcom | 0.8x | 1.75x | 5.0x | 2.19 | 2.86 | 6.25 |
| Memory-card | 0.9x | 1.75x | 5.0x | 1.94 | 2.86 | 5.56 |
| Start screen | 2.3x | 6.0x | 16.0x | 2.61 | 2.67 | 6.96 |
| Transitions / areas | 1.75x | 3.5x | 8.0x | 2.00 | 2.29 | 4.57 |
| Combat | 1.75x | 4.5x | 9.5x | 2.57 | 2.11 | 5.43 |

| Step | Mean | Range | CV |
|---|---:|---|---:|
| dbg -> relprof (optimizer only) | **2.26x** | 1.94-2.61 | 0.14 |
| relprof -> release (tools + O3) | **2.56x** | 2.11-2.86 | 0.13 |
| dbg -> release (composed) | **5.75x** | 4.57-6.96 | 0.16 |

The optimizer axis is multiplicative too (CV 0.14), so the chain composes:
**dbg x ~5.75 estimates release.**

**The two axes anti-correlate (Pearson r = -0.34)**, with near-reversed rank
order:

```
optimizer gain:  start > combat > intro > areas > memcard
tools gain:      memcard > intro > start > areas > combat
```

The optimizer pays off where there is real recompiled guest work to optimise
(combat, start screen); removing per-call hooks pays off where call rate is
high but work per call is near zero (the `TestEvent` card poll, the intro).
The two partly cancel, which is why the composed ratio stays inside 4.6-7.0x
even though each axis varies by ~35%.

Note that **`build-dbg` runs below real time** on the intro (0.8x) and the
memory-card screen (0.9x) - it cannot hold 60 fps there at all. Treat dbg
numbers as unusable for performance judgement, even relative ones.

### Consequences

- **The 4x speed target is met on a shipping build with margin.** Worst case is
  5x (intro / memcard); everything else runs 8-16x.
- **`IDEAS.md` I5 (faster save/card) is largely a debug-tree artifact.** It was
  scoped from dbg/relprof measurements where the card screen manages 1.75x. On
  Release it runs 5x, i.e. 5x headroom against the 60 fps cap. Re-scope or close
  it rather than spending effort on the BIOS card path.
- **The i-cache attribution stays unproven, but its stakes drop.** Release
  carries 35% more `.text` and still runs 2.1-2.9x faster, so code size is not
  dominating anything measurable here.

Method note: Release links `-mwindows` (`psxrecomp/runtime/runtime.cmake:2124`),
so it has no console and cannot capture `PSX_FPS_TELEMETRY` to stderr. A
console-subsystem equivalent is
`-DCMAKE_BUILD_TYPE=RelWithDebInfo -DPSX_DEBUG_TOOLS=OFF -DCMAKE_C_FLAGS_RELWITHDEBINFO="-O3 -DNDEBUG"`.

## Reproducing

- Section inventory and per-band MIPS bytes: `analysis/emi_sections.json`,
  filtering `class` in `{code, mixed}` and deduplicating on `md5` (527 sections,
  405 unique images, 10 destinations).
- Generated bytes: scan `generated/overlays_static_*.c` for
  `void ov[_frag]_<band>_<crc>[_<entry>]_(func_<pc>|psx_[ls]w[lr])(CPUState *cpu) {`
  and attribute bytes to the next definition boundary. Exclude the last body in
  each shard — it absorbs the file tail and inflates its attribution.
