# Overlay bands overlap, so address-only attribution has a floor

**Status:** DONE (found 2026-09-06 while asking why the Capcom intro band would
not capture). Fixes `pc_coverage.py` binning; the underlying limit is real and
only residency data can lift it.

## The question

*"Running the intro should just be a boot with the poller attached — I'm sure
I've done it, but `0x801CE000 Capcom logo intro` still reads NEVER SAMPLED."*

The poller was never the problem. **That stratum could not be credited a PC no
matter how many times the intro ran.**

## Bands share RAM, because their occupants are resident at different times

Band spans, computed from `analysis/overlay_captures_all.json`:

| Band | Span | Width | Exclusive |
|---|---|---|---|
| `0x801CE000` Capcom logo | `801CE000..801EB800` | 118.0 KB | **1.1 KB (0.9%)** |
| `0x801CE400` PLCHAR | `801CE400..801D0ACC` | 9.7 KB | **0.0 KB (0.0%)** |
| `0x801D0C00` BATTLE/SHOP/… | `801D0C00..801ED940` | 115.3 KB | 8.3 KB (7.2%) |
| every other band | — | — | 99.9-100% |

`LOGO.EXE` covers **PLCHAR entirely** and **107 KB of the `0x801D0C00` swap
slot**. That is not a bug in the capture data: the logo plays at boot and is
gone before a battle or shop ever loads, so the same RAM legitimately belongs to
different code at different times.

## Two consequences, one fixable

**1. The binning was order-dependent (fixed).** `strata()` matched the first
containing span in `dict` order:

```python
for base, (lo, hi) in spans.items():
    if lo <= pc < hi: ...; break
```

The captures file happened to list `0x801CE000` **last**, so every one of the
**1,233 observed PCs physically inside its span** was claimed by an earlier
band — 1,174 to `0x801D0C00`, 59 to `0x801CE400`. The logo band could never win
one. Worse, the order came from file iteration, so it could flip on any
re-extract and silently move hundreds of PCs between strata.

Now the **narrowest** containing band wins: deterministic, and the most specific
claim is the least wrong one available from an address alone.

**2. The floor is real (not fixable by playing).** Even with perfect ordering,
an address in `801CE400..801D0ACC` is genuinely ambiguous — it belongs to
whichever overlay was resident *at that moment*. Arithmetic on the address
cannot recover that. So `pc_coverage.py` now prints

```
0x801CE000 Capcom logo intro   ...   SHADOWED (1% exclusive) -- not playable-to-fix
```

and **excludes shadowed bands from "go play these next"**, which had been
recommending a session that could not move the number.

Read PLCHAR's row with the same caution: 0% exclusive space means its 14 PCs are
a most-specific guess, not an attribution.

## What actually resolves it

Residency, which the tree already has:

- **`occ_crc` / `occ_ok`** — the dirty-PC enrichment stamps which compiled piece
  was resident when the PC was entered. This is the correct join key, and it is
  in `build-relprof` today.
- **`area_poller.py watch`** — the overlay native ring plus the area timeline,
  recorded live.

Attributing the shadowed bands by residency rather than by address is the
follow-up. Until then, treat `0x801CE000`, `0x801CE400` and `0x801D0C00` as one
pooled region in any coverage argument.

## Also worth knowing about the intro

Separately from attribution, the intro is a poor harvest target: `LOGO.EXE` was
compiled as an overlay 2026-09-01 and runs ~native, and the observed set records
**interpreted** entry PCs only. `fn starts = 236` is a static ceiling, not a
backlog — `pc_coverage.py`'s own docstring notes most such functions "are
reached by static call edges and are already native, so they will never appear
as an interpreted PC." And the intro does not execute headless at all
([`IDEAS.md`](IDEAS.md) I6), so it can only be observed windowed.

**Genuine never-sampled stratum, by contrast: `0x80117000` WORLD01** — 4.5 KB,
100% exclusive, 25 function starts, 0 registered. That one is real, and playing
it does move the number.
