# The 211 zero-fill dispatch addresses — audited

**Status:** DONE (audited 2026-09-06). Verdict: **not a live correctness bug.**
86% are now legitimately compiled as overlay code; the remainder are masked by
a guard that is sound in every state correct execution reaches. The open item
in [`STATUS.md`](STATUS.md) is closed by this file.

## What was claimed

2026-08-30 recorded *"211 of 8,694 distinct dispatch addresses are zero-fill —
registered native entries whose bodies were compiled from nothing. Dirty-RAM
invalidation masks them today; it is the OV-1 stale-registration risk sitting
armed."* It was carried as an audit item ever since, on the assumption that a
registered entry compiled from zeros could execute.

## Reproduced, and the metric matters

Both figures reproduce exactly against the current tree
(`generated/SLPS_009.90_dispatch.c`, 8,690 entries, and `disc/SLPS_009.90`):

| Measure | Count |
|---|---|
| Dispatch entries inside a >=2 KB zero run | **211** |
| Seeds inside a zero run | **18** of 523 |
| Zero-run bytes total | **1,187,899** |

All three match the 2026-08-30 numbers, so the original metric was **zero-run
membership** and the audit is measuring the same population.

**A near-miss worth recording.** The intuitive metric — *"the entry's first
instruction is `0x00000000`"* — gives **275**, not 211. The extra 64 are **real
code**: a MIPS delay slot holding a NOP. The BIOS-call thunks are the clearest
case; at `0x8017F650`, in context:

```
01400008  jr    $t2          <- previous function
24090039  li    $t1, 0x39
00000000  nop                <- "zero first instruction" = the delay slot
240A00A0  li    $t2, 0xA0    <- real code: the A0 BIOS call stub
```

Their zero run is **4 bytes long**. Anything selecting on the entry word alone
misclassifies 64 correct functions as fabricated. Select on membership in a
large zero run.

## The finding: 86% are no longer fabrications

Cross-referencing the 211 against the 40,627 entries in
`generated/overlays_static.c`:

| | Count |
|---|---|
| Genuine zero-fill dispatch entries | 211 |
| **Now compiled as real overlay code** | **182 (86%)** |
| Not covered by any overlay entry | 29 |

This is the post-2026-08-30 work landing. The addresses were never fictional —
they are overlay landing zones, zero in the boot EXE because `.EMI` sections
load there at runtime. `0x801A27A8` is the clearest example: zero-fill in the
boot image, and `Script_ShowMessage` in `GAME.EMI`
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) — *The resolver*). The overlay extraction
and the Ghidra naming pass turned most of this population from *"compiled from
nothing"* into *"compiled from the right bytes, via the overlay path."*

The 29 that remain cluster tightly:

| Landing zone | Size | Uncovered entries |
|---|---|---|
| `0x801F2C01`..`0x801F6C00` | 15 KB | **22** |
| `0x80117001`..`0x80149800` | 201 KB | 3 |
| `0x80196801`..`0x801CE400` | 222 KB | 2 |
| `0x800C1801`..`0x800F5000` | 205 KB | 1 |
| `0x801D0C01`..`0x801EEC00` | 119 KB | 1 |

22 of 29 are in the WORLD/SCENARIO band that
[`STATUS.md`](STATUS.md) already names as the remaining interpreted sink, so
they are the same gap tracked by Axis B, not a separate defect.

## Why it is not a live bug

The dispatch site is guarded (`dirty_ram_interp.c`, `psx_game_text_native_ok`
before `psx_dispatch_game_compiled`), and the guard
(`memory.c:dirty_ram_text_native_ok_ranges_from`) decides on the **live bytes**:

- **Overlay resident** — the load dirtied the pages, so the `memcmp` against the
  reference image fails, the entry is blocked, and execution falls through to
  the interpreter or the overlay's own compiled code. **This is the state any
  legitimate call is made in**, and it is why these bands were always observed
  running interpreted rather than silently NOPping.
- **Overlay not resident** — RAM equals the reference image (both zero) and the
  pages are pristine, so the page-clean fast path returns valid **without a
  memcmp** and a NOP body would run. Reaching this requires calling into an
  overlay that was never loaded, which is already invalid execution.

So the hazard is real but unreachable from correct execution. Its practical cost
is **diagnostic, not behavioural**: in that window a bad call returns quietly
instead of aborting, which would disguise the very bug you were chasing.

## Recommendation

Remove the 18 zero-fill seeds from `seeds/ghidra_funcs.txt` and regenerate.

```
0x800DCD40 0x8011CD40 0x80142A2C 0x8019701C 0x8019CD40 0x801A27A8
0x801A28D0 0x801A4A10 0x801A4D24 0x801B1DF4 0x801B1E3C 0x801B69AC
0x801C224C 0x801C34C8 0x801C5C40 0x801D0C04 0x801DCD40 0x801F2C04
```

Removing them costs no coverage: the 182 covered addresses keep their real code
via the overlay path, and the 29 uncovered ones already interpret in every state
where they are legitimately called. What it buys is the removal of an armed
stale-registration path and of 211 misleading dispatch entries — including
several fabricated "functions" of 150-200 KB spanning an entire landing zone.

**But it is not a cheap edit.** The seed change is three minutes; the
regenerate plus a `psx-runtime` rebuild over 1.6 GB of generated C is the real
cost, and it invalidates `build-relprof`. Fold it into the next regeneration
rather than spending a rebuild cycle on it alone — nothing is broken while it
waits.

The durable fix belongs upstream: the recompiler should decline to register a
dispatch entry whose emitted body lies entirely inside image zero-fill, instead
of relying on every title to prune its own seeds.

## Reproducing

Audit script: `scratchpad/zf_audit.py` (session-local). The method is three
steps against `disc/SLPS_009.90` (PS-EXE, `t_addr 0x80093800`, 0x800 header):
map zero runs >= 2 KB; parse `k_psx_game_dispatch` and `k_psx_game_code_ranges`
out of the dispatch C; test entry membership, then intersect with the
`psx_ov_entries` addresses in `generated/overlays_static.c`.
