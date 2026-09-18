# The `[audit]` shard failures are one predicate, not a drift

**Status:** FIXED, MEASURED 2026-09-18 — `_frameless_dispatch_root_proven` in
`psxrecomp/tools/compile_overlays.py`, fork branch
`fix/frameless-dispatch-root-cfg-proof` (`8e8a4f13`, off upstream `master`
`1a0897ca`; `compile_overlays.py` was byte-identical there, so the commit is
independent of the other open work). Cherry-picked onto
`integration/vector-stub-plus-367` as `aba55c55` (on top of `88f4582a`, which the
branch ref was behind — a fast-forward, nothing rewritten) for the local build. The
all-bands overlay compile goes from **exit 2, `failed=27`** to **exit 0,
`failed=0`** on the same captures, the same recompiler binary and the same
command. Evidence: the A/B below, run back to back on 2026-09-18.

This retires the standing claim in [`STATUS.md`](STATUS.md) and
[`HANDOFF.md`](HANDOFF.md) that the compile "exits 2 and that is correct", and
that the failure count "drifts upward as the observed set grows". The count
drifted because nothing stopped it; the shape was never benign in the sense of
*unavoidable*, only in the sense of *not wrong at runtime*.

## What every one of them was

Overlay bands are shared address windows, so every observed interpreted PC is
demanded for every occupant of its band ([`DATA_ISLANDS.md`](DATA_ISLANDS.md)).
`classify_overlay_seeds` promotes such a demand to a **linear walk root**
whenever `_callable_legacy_seed` accepts it, and that predicate accepts three
unequal grades of evidence:

| grade | test | strength |
|---|---|---|
| image entry | `addr == load_addr` | structural |
| prologue | `addiu sp, sp, -imm` not preceded by control flow | strong |
| post-return | the word two slots back is `jr $ra` | **weak** |

The third grade fires exactly where it is least trustworthy. The first word
after a function's return is also the first word of whatever the linker laid
down next — and in an overlay image that is routinely a pointer table, a packed
record array or zero fill. The walk starts at the table head, never reaches a
return, and runs to the image end; the generated-C audit then reports a column
of `UNSUPPORTED_INSTRUCTION` and the shard fails.

All 27 failing shards on the 2026-09-18 tree have this shape, and each has
**exactly one** such root. The bands differ only in what data follows their
last function:

| band | shards | the root, and what is at it |
|---|---|---|
| `0x801EEC00` (BMAGIC / BATL_END) | 4 | `0x801EF5F8` in `BATL_OVR.EMI` — five in-image code pointers (`801EEC40`, `801EEC7C`, `801EEEB8`, `801EEF10`, `801EF0A8`, every one a dispatch entry of the same image) followed by a small word table; `0x801EF124` a halfword table; `0x801EFE54` a word table |
| `0x800C1800` (BOSS) | 5 | `0x800C1B28`/`1B34`/`1B44`/`1F9C`/`0x800C2140` — the per-boss behaviour tables already named in [`DATA_ISLANDS.md`](DATA_ISLANDS.md), byte flags then `FF` padding then handler pointers |
| `0x801F2C00` (AREA / WORLD) | 17 | `0x801F2C44` … `0x801F44B8` — 12-byte script records (`00322F08 93800500 00070201`), and in six shards a run of in-image pointers first |
| `0x801F6C00` (SCENARIO) | 1 | `0x801FBEF0` — eight consecutive in-image code pointers |

The three addresses the session started from (`0x800C1800`, `0x801F2C00`,
`0x801EEC00`) are not three separate misclassifications. They are one
predicate, seen in three bands.

## The fix

The framework already owns the discriminator. `plausible_callable_target` is a
bounded CFG probe — first word decodes and is non-zero, not the head of a dense
local pointer table, and a bounded forward walk in which every word decodes, no
branch leaves the image, and **a return is reachable**. It already gates the
static discovery roots, and [`WALK_ROOTS_HANDOFF.md`](WALK_ROOTS_HANDOFF.md)
§3.1 records the precedent in this very repo: our first `pointer_roots` pass
doubled the audit-failed shards 26 → 53 until that proof was added.

Dispatch entries were the one root source that never got it. The fix requires
the same probe of a dispatch entry that has **no prologue** — i.e. one riding
on the weak post-return grade alone. The image entry and the prologue keep
their own evidence and are not probed.

Failing the probe is not a discard. The entry is demoted to
`DISPATCH_INTERIOR`, which keeps the dispatch evidence and the isolated
fragment demand and only declines to *start a walk* there; a hostless interior
then falls out to `excluded: UNKNOWN` with its fragment demand intact, which is
the documented path for exactly this case.

## A/B — the classifier, over all 406 captures

Same capture file, `_frameless_dispatch_root_proven` forced true vs. real:

| | before | after | delta |
|---|---|---|---|
| `DISPATCH_ENTRY` (walk roots) | 1,141 | 1,100 | **−41** |
| `DISPATCH_INTERIOR` | 81,474 | 80,851 | −623 |
| `STATIC_DISCOVERY_ROOT` | 10,741 | 10,741 | 0 |
| `STATIC_DISPATCH_ENTRY` | 194 | 194 | 0 |
| `FUNCTION_POINTER_TARGET` | 20 | 20 | 0 |
| isolated fragment demands | 105,891 | 105,891 | **0** |

41 of 406 captures change at all. Nothing proven is touched, and **not one
fragment demand is lost** — every dispatch PC keeps its isolated-fragment path,
so no dispatch coverage is traded away. The 623 interiors that fall out are the
interiors *of the fabricated walks*: addresses that were only "hosted" because
a walk over data covered them.

### Why the probe is not trigger-happy

Of the 5,339 dispatch entries already accepted as walk roots, 2,066 have a
prologue and are untouched; 3,273 ride on the preceding `jr $ra` alone. The
probe rejects **41** of those 3,273 — 1.3 %. Frameless leaf functions pass the
probe and keep their root; that is the whole point of the probe over the shape
test, and `WALK_ROOTS_HANDOFF.md` §3.2 says so outright.

All 41 were read by hand. Every one is data:

- **in-image code-pointer runs** — `801EF058`; `801EEFB4 801EF1F0`;
  `801EEE9C 801EEF3C 801EF0D8 801EF1DC 801EF358`; eight-long in `SCENA`
- **packed 12-byte script records** — `00322F08 93800500 00070201` (AREA050,
  AREA056 and the `0x801F2C00` failures)
- **signed halfword delta pairs** — `FFEC0000 FFE90001 FFE4FFF9` (MAGIC042),
  `00380008 0038FFF0 00180000` (MAGIC073) — sprite or motion offsets
- **zero fill** — MAGIC116

27 of the 41 are the 27 failing shards, one bad root each. The other **14 are
the same defect in shards that passed**: their data happened to decode all the
way to the image end without meeting an opcode the R3000A lacks, so the audit
never fired. Those 14 were emitting a fabricated function over a table.

## A/B — the all-bands compile, same inputs, back to back

`python psxrecomp/tools/compile_overlays.py --static --force --captures
analysis/overlay_captures_all.json --game-toml game.toml --recompiler
build-recompiler/psxrecomp-game.exe --out-dir generated --gcc … --cps`

Run back to back on 2026-09-18, same captures, same
`build-recompiler/psxrecomp-game.exe`, the only difference being
`compile_overlays.py` before vs after the commit:

| | without the fix | with the fix |
|---|---|---|
| exit code | **2** | **0** |
| `PSX_SHARD_RESULT` | `ok=376 failed=27 skipped=9776` | `ok=402 failed=0 skipped=9770` |
| `SHARD FAIL [audit]` lines | 27 | 0 |
| isolated interior fragment demands | 18,431 | **15,667** (−2,764) |
| CPS resume wrappers | 240,567 | 206,378 |
| exact function identities | 351,468 | 316,319 |
| translation units | 773 | **800** (+27) |

### The failures were costing size, not just noise

The last four rows were not expected, and they are the more interesting
result. A whole-image shard that fails the audit is rejected *entirely* — so
every demanded entry in those 27 images fell through to the isolated-fragment
path, one compiled fragment per (entry, image). Fixing the root lets the 27
images compile as images again: +27 translation units (one per shard that now
builds), and **2,764 fragment demands stop existing** because the whole-image
compile already serves them. The identity and CPS-wrapper counts fall with
them — that is duplication removed, not coverage lost; the offline A/B above
shows the candidate fragment-demand set unchanged at 105,891 and nothing but
the 41 data roots and their 623 fabricated interiors dropped.

Interior-entry fragmentation is what
[`OVERLAY_SIZE.md`](OVERLAY_SIZE.md) identifies as the reason `generated/` is
1.6 GB, so this is a small bite out of that too: **1,711 MB → 1,681 MB**
(773 → 799 `overlays_static_NNNN.c`). Not the lever that closes that gap —
per-occupant attribution is — but free.

The fixed compile was run twice, before and after the baseline, and produced
identical figures both times (`ok=402 failed=0 skipped=9770`, 316,319
identities, 800 translation units).

**`build-relprof` needs a relink**, and a CMake reconfigure with it: the
translation-unit count changed, which `axis_b_loop.sh` phase 5b warns is the
cause of a link failure with undefined `func_*`.

## What this does and does not fix

It fixes the **static side**: a demand at an address that is data *in this
image* can no longer fabricate a function there. It does not fix the reason the
demand exists — the harvest still expands every observed PC to every occupant
of the band, because the resident-image stamp is still the open framework item
(`HANDOFF.md` → *Next on this track*: key harvest rows and extract demands on
`(image, PC)`). That work remains worth doing; this change makes its absence
harmless rather than noisy.

**The `[audit]` failure class is now a signal again.** Before, a non-zero count
was expected and unreadable; a real regression could hide inside the drift.
After, `failed=0` is the baseline, and any `[audit]` shard failure means a data
shape the CFG probe does not yet recognise — worth reading, not waving through.
`tools/axis_b_loop.sh` and the docs are updated to say so.

## Regression test

`psxrecomp/tools/tests/test_frameless_dispatch_root_cfg_proof.py`, registered
as CTest `frameless_dispatch_root_cfg_proof`. Six cases, built from the real
bytes above: the pointer table, the packed record table and zero fill must not
be roots; a frameless leaf after a return and any prologue must stay roots (the
prologue case uses a function with *no* reachable return inside the probe, to
pin that a prologue is never probed); the image entry is never probed.
