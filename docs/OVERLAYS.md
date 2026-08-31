# Overlays — why most of this game is not statically recompiled

**Status:** IN PROGRESS (evidence gathered 2026-08-30)

Breath of Fire III keeps the great majority of its code in runtime-loaded
overlays. Static recompilation reaches only a minority of the game by
construction, and the dirty-RAM interpreter carries the rest. This document is
the evidence for that claim and what follows from it.

## 1. The boot EXE is mostly empty space

`SLPS_009.90` declares `t_size = 0x163800` (1,456,128 bytes). Scanning the image
for zero runs of 2 KB or more:

| Region | Bytes |
|---|---|
| `0x80093801` – `0x800C1800` | 188,415 |
| `0x800C1801` – `0x800F5000` | 210,943 |
| `0x800F5001` – `0x80117000` | 139,263 |
| `0x80117001` – `0x80149800` | 206,847 |
| `0x80184F78` – `0x80185FE8` | 4,208 |
| `0x8018BC2C` – `0x80196800` | 43,988 |
| `0x80196801` – `0x801CE400` | 228,351 |
| `0x801CE401` – `0x801D0C00` | 10,239 |
| `0x801D0C01` – `0x801EEC00` | 122,879 |
| `0x801EEC01` – `0x801F2C00` | 16,383 |
| `0x801F2C01` – `0x801F6C00` | 16,383 |

**1,187,899 bytes — 81.6% of the text segment — are zero in the image.** Real
static code is roughly 268 KB. The zeroed span is where overlays land.

## 2. Execution is dominated by that space

Harvested from a live play session (`tools/harvest_interp_pcs.py`, 568 tracked
PCs, 5,271,600 tracked interpreted instructions):

| Origin of interpreted code | Instructions | Share | Interpreter entries |
|---|---|---|---|
| **Overlay** (zero in image) | 4,936,205 | **93.6%** | 37,986 |
| BIOS / kernel RAM | 220,808 | 4.2% | 106,820 |
| Static EXE code | 114,587 | 2.2% | **0** |

Whole-session ratios ran **84–93% interpreted**; a five-second live sample gave
a steady 9.0–9.1% native, a later one 18.5–19.1%. The mix moves with what is on
screen, but the interpreter always dominates.

The overlay PCs actually touched span **`0x801970B4` – `0x801DE098`**.

## 3. Seeding cannot fix this — proven twice

**The static-EXE row above has `entries = 0`.** The interpreter never *enters*
static code; it only falls through into it. There is no missing static entry
point to seed.

Two experiments confirm it:

- Extending `seeds/ghidra_funcs.txt` from 523 to 868 entries — every
  `verified`/`high`/`medium` function in `analysis/functions.tsv` that it lacked
  — produced a **byte-identical generate**: same 35 shards, same 1,467 dispatch
  entries. Verified by running `psxrecomp-game` out-of-band against both seed
  files, so it was not a cache. The recompiler's own discovery already exceeds
  the analyser's function list.
- Seeding observed *interior* entry PCs did raise the dispatch table
  (1,467 → 1,475) and stayed clean under `strict`, but those addresses are zero
  in the image. The emitter produced `psx_alias_body_801D0C04` aliases into a
  parent compiled from nothing. Reverted — seeding code that is not in the image
  is fabrication.

## 4. Consequences already observed

- **Savestates refuse.** `savestate_poll` needs
  `psx_irq_resume_context_snapshot_safe()`, which is
  `g_cosim_dirty_pump_site == 0` (`interrupts.c:629`). An interrupt taken inside
  the dirty-RAM interpreter can never be snapshotted. Interrupt entries arrive
  at the BIOS vector `0x800000A0` and flow into overlay code, so the 2 s defer
  window routinely expires with no safe poll. Note this tracks the *interrupt
  path*, not the aggregate ratio — saves got worse while the native share rose
  from 9% to 18.6%. **In-game memory-card saves are unaffected** and are the
  working way to preserve progress (`saves/card1.mcd`).
- **Boot is slow enough to trip watchdogs.** Two ~87 MB freeze dumps are written
  at frame ~328 of every launch (`slow_frames` then `hard_freeze`), and 4 s
  stalls trip `starvation_ring.c`'s `exit(2)`.
- **211 of 8,694 dispatch addresses are zero-fill**, from 18 of 523 seeds (3.4%,
  all `low` confidence). Those are registered native entries compiled from
  nothing. Dirty-RAM invalidation masks them today; it is the OV-1
  stale-registration failure mode in `psxrecomp/docs/overlay-status.md` sitting
  armed. Worth auditing before native dispatch is trusted in that range.

## 5. The overlays are statically extractable — capture is NOT required

**This is the important finding, and it contradicts the framework's default
advice for a good reason.** `psxrecomp/docs/overlay-discovery.md` argues that
disc extraction "does not work", but that argument is **Tomba-specific**: Tomba
uses a scatter-load format where overlay bytes exist nowhere contiguously on
disc. Breath of Fire III does not. Its `.EMI` containers carry a TOC that states
each section's **RAM destination**, and the sections are contiguous.

`BIN/ETC/GAME.EMI` — the field engine:

| Section | Destination | Size |
|---|---|---|
| 0 | `0x80196800` | 227,556 |
| 1 | `0x801D0C00` | 4,274 |

Section 0 spans `0x80196800`-`0x801CE0E4` and is unambiguously MIPS code:
**681 `jr $ra`** and **572 `addiu sp,sp,-N` prologues** across 56,889 words. The
PCs harvested from the live session disassemble correctly inside it —
`0x801970B4` is `lw v0,0x44(v0) / jr ra / sb zero,4(v0)`, a textbook function
tail. It exactly covers the zero-fill run `0x80196801`-`0x801CE400` mapped in §1.

### The layout: two bands

| Band | Occupants | Nature |
|---|---|---|
| `0x80196800` | `GAME.EMI` §0 (227 KB) | the field engine — effectively persistent |
| `0x801D0C00` | `SHOP.EMI` (87 KB), `STATUS.EMI` (118 KB), `BATTLE.EMI` (118 KB), `START.EMI` (118 KB) | a **swap slot**, mutually exclusive by game mode |

Area files (`BIN/WORLDnn/AREAnnn.EMI`) carry their own sections — e.g.
`AREA004.EMI` targets `0x800D3800`, `0x800E3800`, `0x80104000`, `0x801F2C00`
and the `0x80010000` script. Note that not every zero-fill destination is code:
`AREA004.EMI` §8 at `0x80104000` has **zero** `jr $ra` and zero prologues — it
is data. Each candidate section must be code-tested before it is compiled.

### What this changes

- **No runtime capture, and no `[runtime] overlay_cache`.** The risky Layer A
  DLL cache can stay off, and the OV-1 stale-registration path stays unused.
- **No playtime needed for discovery.** All 880 `.EMI` files can be enumerated
  offline; coverage is complete by construction rather than limited to what a
  session happened to touch.
- **Deterministic and reviewable** — the overlay set becomes a build input, not
  a recording.

### The hard part that remains

Band 2 is one address range holding four different modules at different times.
Pre-compiling all four means the runtime must register and *unregister* by
mode; getting that wrong is precisely OV-1 (stale registration → wrong native
code → the Tomba blue screen). Band 1 is the easy, high-value start: one
occupant, 227 KB, and it is where the field-play interpretation is concentrated.

Still unresolved: `0x801CEEDC` — the address that accounted for 91 M
interpreted instructions at boot — lies **past** the end of `GAME.EMI` §0
(`0x801CE0E4`), so it belongs to some other overlay not yet identified.

## 6. What to do

Prefer the **static extraction** route in §5 over DMA-time capture. The
framework's Layer B (`game.toml [[overlays]]` + `compile_overlays.py`) is the
right consumer — it wants `(load_addr, bytes, seeds)`, and the `.EMI` TOC
supplies the first two directly. Two cautions on the framework docs:

1. That work is described on branch `feat/overlay-jit-cache`. This repo is
   pinned to `f24b7e5d`. **Confirm what the pin actually carries** before
   planning against those docs — `[runtime] overlay_cache` and
   `psxrecomp/tools/compile_overlays.py` do exist in the pinned tree, but the
   status doc's fixes (Inc1-D write-invalidation, boundary-gated promotion) need
   verifying.
2. `overlay-status.md` records that Tomba's benefit was **correctness only** at
   first — `dispatch_native ≈ 122` against ~31 M interpreted — because only one
   overlay was compiled and an invalidated region was not re-registered. Expect
   the same here until coverage is broad. Set expectations accordingly rather
   than promising a speed win.

## Reproducing

```bash
# with the game running (build-dbg, --debug-port 4370)
python tools/harvest_interp_pcs.py
```

Writes `analysis/observed_interp_pcs.json` and prints the interpreted/native
split. Coverage is only as good as what the session exercised.
