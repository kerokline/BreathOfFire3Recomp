# Per-area PCs in the world band

**Status:** DONE for the census and the agreement check (2026-09-07). The
coverage gap it surfaces is open work, not a conclusion.

Which PCs does a *place* need? Asked of the 122 searchable spots in
[`WORLD_ITEMS.md`](WORLD_ITEMS.md), the answer splits cleanly in two, and only
one half is per-area.

    python tools/area_pcs.py --chain          # the constant search path
    python tools/area_pcs.py --area 27        # one area, in full
    python tools/area_pcs.py --items-only     # the 54 areas that hold something
    python tools/area_pcs.py --verify         # agreement with the overlay catalog

## Half one: the search path is constant

Searching a dresser is entirely engine code. The area section contributes the
8-byte record array and nothing else — so these eleven PCs are exercised by
every one of the 54 areas that hold anything, and by no others:

| PC | Name | Module |
|---|---|---|
| `0x801B3FC0` | `Field_SearchSpot` | GAME.EMI |
| `0x801B6C4C` | `Field_FindSearchSpot` | GAME.EMI |
| `0x801B6E50` | `Field_GiveZenny` | GAME.EMI |
| `0x8015BFC4` | `Flag_Test` | boot EXE |
| `0x8015BF70` | `Flag_Set` | boot EXE |
| `0x80166FFC` | `Zenny_Add` | boot EXE |
| `0x80165AA4` | `Inventory_Add` | boot EXE |
| `0x80166720` | item-name pointer | boot EXE |
| `0x801503AC` | message open | boot EXE |
| `0x8015E908` | `SE_Play` | boot EXE |
| `0x8017ED6C` | sprintf | boot EXE |

All eleven are in bands the current `generated/` tree compiles (GAME.EMI
`0x80196800`, and the boot EXE itself), so the searching path itself is
already native.

## Half two: the area's own code, which is the hard half

`0x801F2C00` is the one band that **cannot be attributed by address**. 181
distinct area sections load there, so a PC observed in the band names a slot,
not an occupant — the overlay catalog marks every AREA overlay
`heat_attribution: band-shared(181)`, and
[`band-overlap-attribution.md`](band-overlap-attribution.md) is why that is
not fixable from addresses.

`tools/area_pcs.py` walks each `AREAnnn.EMI`'s section on the disc and emits
the entry PCs *that area* contributes, which turns the ambiguity into a
membership test: given a band PC, which areas actually contain it?

| | all 200 areas | the 54 reward areas |
|---|---:|---:|
| areas carrying any code | 156 | 46 |
| entry PCs | 1,546 | 434 |
| distinct addresses | 1,058 | 368 |
| addresses claimed by 2+ areas | **317** | 55 |
| worst collision | **18 areas on one address** | 7 |
| distinct engine PCs called from area code | 186 | 106 |

So a third of the band's discovered entry addresses are ambiguous, and one
address is a function entry in eighteen different areas. That is the number
`band-shared(181)` was standing in for.

Per area the sections are small — 9.9 entry PCs on average across the
code-bearing areas, 9.4 across the reward areas, and 44 of the 200 AREA files
carry no code in this band at all — and most of the work is elsewhere: the area code
calls out to 186 distinct engine functions, led by `0x8014E494` (357 call
sites, still unnamed), `GetGraphType`, `0x801A5BC8` (GAME.EMI, unnamed),
`rsin`/`rcos`, and `Flag_Test` at 253.

That last one is worth noting on its own: **area code tests progress flags
directly, 253 times across the 200 areas**, and calls `Flag_Set` and
`Flag_Clear` too. The searching path is not the only user of the bit arrays —
per-area scripts gate themselves on them.

## Agreement, not assertion

Entry discovery is **not** reimplemented here. `tools/area_pcs.py` calls
`jal_targets` and `prologue_roots` out of `tools/extract_overlays.py` — the
same two functions `tools/overlay_catalog.py` uses to fill each overlay's
`roots` — so the counts are identical to the catalog's by construction, and
`--verify` proves it: **181 of 181 areas agree on both counts, 0 disagree.**

That delegation was earned. A hand-written first pass matched `roots.jal`
exactly on all 181 areas but over-counted prologues on 163 of them, by 1,088
entries in total. The missing rule is a boundary constraint: an
`addiu $sp, $sp, -N` only opens a function when it is the section's first word
or **follows a `jr $ra` delay slot**. Scanning for the instruction alone finds
every mid-function stack adjustment as well.

One thing the tool does bound on its own: external call targets are collected
only below the **data floor** — the lowest pointer in the per-area struct the
boot table `0x801802EC` points at (see [`WORLD_ITEMS.md`](WORLD_ITEMS.md)).
Without it, the area's data tables decode as instructions and invent call
targets like `0x89600000` and `0x843813E0`. AREA027 reports 33 external
targets bounded, 52 unbounded — 19 of them fiction.

## Does this help with areas nobody has played?

Not in the way it first looks, and the reason is worth writing down because it
is easy to get backwards.

**Static discovery never needed a play session.**
`tools/extract_overlays.py` says so in its own opening line — it builds the
captures "from .EMI sections, statically... no DMA-time capture". It walks
every `AREAnnn.EMI` on the disc, so the entry PCs for a map nobody has ever
loaded were already discovered, already seeded, and already compiled by the
same pass that handled the maps you have played. Visiting a map adds nothing
to its static roots. The one play-dependent input is
`dispatch_entry_pcs`, described there as "optional; purely additive".

**And the world-item table yields no PCs at all.** The 8-byte records are
*data*. Knowing that AREA168 holds a Napalm at tile (109,29) says nothing
about which code runs there; the searching path that reads those records is
the same eleven engine PCs in every area.

So the honest answer is: extracting item locations for unreached areas does
not start you with a chunk of PCs, because the PCs were never the missing
part.

What *is* missing is the other 75 — and those cannot be reached by any static
scan, by construction. That is where the item table earns its place, in a role
it is genuinely good at: **it is a route.** For each unvisited area it gives
exact tile coordinates worth walking to, which converts "go play more of the
game" into a concrete, checkable errand list. Combine it with this census and
a play session becomes measurable rather than hopeful: before you go, you know
the area's static entry set; afterwards you can ask which of them were
actually entered, and which entered PCs were not in it.

## The coverage gap this surfaces

Two findings worth acting on, both open:

1. ~~**The world band is not compiled in the current `generated/` tree.**~~

   > **Retracted 2026-09-07 — this was never true.** It came from a
   > case-sensitive grep: band prefixes are emitted with uppercase hex
   > (`ov_001F2C00_`), and `[0-9a-f]{8}` matches only the all-digit bands
   > `00093800` / `00117000` / `00196800`. Every other band was invisible to
   > the pattern, not absent from the tree. All **11** bands are compiled and
   > have been throughout: `0x80093800`, `0x800C1800`, `0x800F5000`,
   > `0x80117000`, `0x80196800`, `0x801CE000`, `0x801CE400`, `0x801D0C00`,
   > `0x801EEC00`, `0x801F2C00`, `0x801F6C00`. Fixed in `area_pcs.py`
   > `compiled_band_bases()` and `harvest_interp_pcs.build_fingerprint()`.
   >
   > The cost of the error was believing a live measurement had to be wrong: a
   > slot-3 run produced **zero** world-band interpreted PCs, which is exactly
   > what a compiled band looks like, and it was explained away as a
   > short-window artifact instead of being taken as the evidence it was.

2. **Of the 140 PCs a live session has actually *entered* in this band, none
   that we can attribute is a static root of the area it ran in.**

   > **Corrected 2026-09-07.** This row first read "65 match a statistically
   > discovered area entry". That 65 was an **address-level** match against the
   > union of all 200 areas' roots — exactly the mistake this whole document
   > exists to warn about. 51 of the 140 rows carry a `.EMI` stamp naming the
   > occupant they ran under; matched per occupant, **0 of them** is a root of
   > their own area, while address matching would have claimed 22 of those same
   > 51. All 22 were collisions with a different area. In a band with 181
   > occupants sharing one address window, matching by address is not merely
   > imprecise, it is wrong.

   Run `tools/area_pcs.py --coverage` for the ledger.

   **Read `observed_interp_pcs.json` the right way round.** It is not a list of
   un-exercised code — being observed is the entry criterion. Every row RAN,
   and ran in the dirty-RAM interpreter because no native dispatch entry
   existed for that address; `entries > 0` is the harvester's "empirically
   proven function entry" (2,154 of the 2,364 rows; the other 210 were only
   fallen through and `load_observed()` drops them). What is *absent* from the
   file is the ambiguous half: a PC missing from it is either compiled and
   running native, or has simply never been executed, and the file cannot tell
   those apart. That is why it is unioned and never overwritten — two sessions
   were measured sharing only 323 of ~17,500 PCs, because which `.EMI` is
   resident decides which PCs bucket to a band. Four sessions are represented
   so far, so the 140 above is "everything uncompiled in the areas walked
   through", not "everything uncompiled in the band".

   And because the file only grows, a row harvested on 2026-09-04 may name a PC
   a later build now compiles. It accumulates history, not a snapshot of the
   current tree, so 75 is an upper bound until re-measured.

   The poller's end-of-run "N new PCs" is a discovery *rate* against that
   accumulated file, not a completeness measure -- `harvest_interp_pcs.py` says
   so at the print itself: "0 new PCs is not evidence of a complete set -- it is
   equally consistent with having replayed the same rooms."
   `tools/pc_coverage.py` is the falsifiable version (Chao2 over per-session
   incidence). As of the four sessions recorded, it puts this band at **68
   sampled of an estimated 165, 41.3%** -- the best-covered of the large
   strata, and still less than half. Its "go play these next" list is the
   direct consumer of a route: `0x80117000` WORLD01 has **never been sampled**,
   SCENARIO sits at 4.3%, the field/map core at 6.2%.

## Burning areas down

`tools/area_pcs.py --coverage` prints the four-cell ledger and, under it, the
burn-down. Two changes made that possible.

**1. Harvest now stamps by delta, not by novelty** (`harvest_interp_pcs.py`).
It used to stamp the resident `.EMI` only on PCs *newly seen* by a pass, which
left 89 of the 140 world-band rows with no occupant at all — permanently, since
the file only accumulates. The naive fix is wrong and the old comment said why:
`dirty_ram_stats.per_pc` is cumulative for the whole session, so the area
resident *now* says nothing about a PC last entered twenty minutes and three
rooms ago. Stamping everything would manufacture false attributions.

What is sound is the **delta**. Between two passes of the poller's timed
re-harvest, a PC whose `entries` count grew was necessarily entered in that
interval, and the area resident across it is known. So a PC is stamped when it
is new *or when it moved*. Verified live (`analysis/dresser/test_stamp.py`):
two passes against one runtime under different area labels, 5 rows correctly
gained a second attribution that the old path would have dropped, and the 54
that did not move were correctly left alone.

**2. The burn-down unit is an area, and it comes from the residency log.**
This is the part the observed file structurally cannot supply: a fully native
area emits **no rows**, so "clean" and "never visited" are the same absence
there. `analysis/area_timeline.jsonl` — which `area_poller.py watch` writes on
every change of resident area, regardless of whether anything fell to the
interpreter — is the other half. Joining them:

| | areas |
|---|---:|
| visited, **clean** (no interpreted PC ever attributed) | **11** |
| visited, dirty (still yielding unknown entries) | 7 |
| never resident | 140 |

Clean today: AREA003, 007, 008, 010, 013, 015, 016, 019, 023, 024, 095.

So yes — areas can be burned down, but the ledger has to be
*residency × observations*, never observations alone. And note what burn-down
does **not** mean: it is a statement about discovery, not about speed. An area
with no interpreted PCs has had its dispatch entries found; whether they are
compiled in is the separate nativeness axis.

One caveat on the 11: absence of an attributed observation is weaker evidence
than it looks for areas visited before delta stamping existed, since a PC
entered there may have been recorded without a stamp. The list will firm up as
sessions accumulate under the new behaviour.

## The two columns age differently

KNOWN and PROVEN are not the same kind of fact, and conflating them is how the
ledger goes wrong.

**KNOWN is build-independent.** Entry PCs come off the disc. Rebuild, change
which bands compile, change codegen — the 1,546 stay 1,546. Nothing about a
build moves them.

**PROVEN is build-dependent, and unavoidably so.** "This PC ran interpreted" is
a statement *about a build*: compile the band it lives in and the same PC runs
native and never appears again. That is not a defect to engineer away — it is
what the number means. It also means KNOWN+PROVEN is a **compilation** measure,
not a discovery one: it reads 0 on a build where the band is compiled and
non-zero on one where it is not, for the same game and the same play.

So the property worth having is not "build-independent counts". It is: **never
reset, but never merge across builds either.** History is expensive — sessions
are near-disjoint, so a discarded row may be the only time that PC was ever
seen — while silently adding a three-band tree's rows to an all-bands tree's
rows is comparing two different experiments.

`harvest_interp_pcs.py` now stamps every row it touches with a build id
(`build_fingerprint()`: codegen hash plus the overlay bands present in
`generated/`, e.g. `cg:EA3D3259;b:117000,196800,93800`). Unlike the area stamp
this needs no delta — the build is constant for a whole session, so every row
in the snapshot honestly belongs to it. `--build` overrides the derived value
when the running exe came from a different tree; the runtime exposes no build
identity over TCP, so the derivation is local and its limits are stated rather
than hidden.

`area_pcs.py --coverage` lists observed rows by build and refuses to present a
mixed PROVEN column as a single fact:

```
  observed rows by build:
    (unstamped -- pre-2026-09-07)                  140
```

The 140 accumulated rows predate stamping, so the experiment they belong to is
lost — which is exactly why the KNOWN+PROVEN=0 reading above stays an
inference. Rows harvested from now on can be read exactly with `--build`.

This also gives the PC-level burn-down the area-level one already has: a PC
seen interpreted under build A and absent under build B **was fixed by B**.
Without build ids the file could not express "this got fixed" at all; it could
only grow.

## Files

| Path | What |
|---|---|
| `tools/area_pcs.py` | the census |
| `analysis/area_pcs.json` | all 200 areas: entry PCs, external calls, catalog check |
| `analysis/area_pcs_items.json` | the same for the 54 reward areas only |
| `analysis/area_timeline.jsonl` | the residency log — the burn-down denominator |
