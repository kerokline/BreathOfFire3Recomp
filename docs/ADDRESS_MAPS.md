# Address maps — resolving a raw address to what the repo knows about it

**Status:** STABLE (built and verified 2026-09-12). The region table below is a
**snapshot**; `python tools/regions.py list` is authoritative and
`python tools/regions.py check` proves the sidecar still agrees with its sources.

Two maps were added on 2026-09-12 so that a raw address read anywhere in this
repo can be resolved without a grep:

| Map | File | What it answers |
|---|---|---|
| **Region sidecar** | `names/regions.toml` (`tools/regions.py`) | *What span is this address in?* — the eleven overlay bands, the two message pools, the insert scratch array, the EXE image, the kernel area |
| **Prose cross-reference** | [`XREF.md`](XREF.md) (`tools/xref.py`) | *Is this address named, and which documents discuss it?* — every `0x80xxxxxx` literal cited in `docs/*.md`, joined to the naming layer |

Both are **offline joins over committed files**. Neither needs `analysis/`, a
disc, or a running game, so they work on a fresh checkout. Nothing in either is
typed in from memory: every row carries the source it was derived from.

## Why they exist

The structured naming layer was already a graph, keyed so it survives
re-extraction:

| File | Keys | Holds |
|---|---|---|
| `symbols.toml` | `pc` | boot-EXE functions (the framework `PSX_FN_*` path) |
| `names/functions.toml` | (`overlay` md5, `pc`) | overlay-resident functions |
| `names/data.toml` | (`overlay` md5, `pc`) | data islands inside overlay images |
| `names/overlays.toml` | section md5 | overlays, with the game's own registry id |
| `names/regions.toml` | `base` | **spans** — new |
| `seeds/ghidra_funcs.txt` | address | JAL targets: known function roots, named or not |

Two gaps followed from that shape. First, **the prose was joined to none of it**:
10,700 lines in `docs/` cite addresses, and a session reading one could not tell
whether it was named. Second, **nothing could hold a span.** Every key above is a
point or a whole section, so the addresses this repo cites most — the overlay
band bases — could only be named in prose. `tools/xref.py queue` made that
visible immediately: the top of the unnamed list was `0x801D0C00` (14
documents), `0x801EEC00` (13), `0x801F2C00` (12), then the two `.EMI` block
dests.

## The regions

Derived, not asserted. Every row's `evidence` field names its source.

| Span | Width | Kind | `bound` | Nature |
|---|---:|---|---|---|
| `0x80000000`–`0x80010000` | 65,536 | kernel | architecture | BIOS kernel area (psx-spx) |
| `0x80010000`–`0x80014000` | 16,384 | message pool | documented block end | per-area script block |
| `0x80014000`–`0x80017628` | 13,864 | message pool | documented block end | system block (`AFLDKWA.EMI`) |
| `0x80093800`–`0x800C1800` | 188,416 | overlay band | zero-fill window | battle engine, 42 copies of one blob |
| `0x80093800`–`0x801F7000` | 1,456,128 | exe image | exe layout | the boot EXE `.text` span |
| `0x800C1800`–`0x800F5000` | 210,944 | overlay band | zero-fill window | `BOSS/BOSSnnn.EMI` |
| `0x800F5000`–`0x80117000` | 139,264 | overlay band | zero-fill window | |
| `0x80117000`–`0x80149800` | 206,848 | overlay band | zero-fill window | |
| `0x801490D4`–`0x801492D4` | 512 | scratch array | documented geometry | `<07><nn>` insert records |
| `0x80196800`–`0x801CE400` | 228,352 | overlay band | zero-fill window | field engine — `GAME.EMI` §0 |
| `0x801CE000`–`0x801EB800` | 120,832 | overlay band | measured occupant span | Capcom logo (`LOGO.EXE`) |
| `0x801CE400`–`0x801D0ACC` | 9,932 | overlay band | measured occupant span | `PLCHAR/PLPnnn.EMI` §0 |
| `0x801D0C00`–`0x801ED940` | 118,080 | overlay band | measured occupant span | swap slot — `SHOP`/`STATUS`/`BATTLE`/`START` |
| `0x801EEC00`–`0x801F2C00` | 16,384 | overlay band | zero-fill window | |
| `0x801F2C00`–`0x801F6C00` | 16,384 | overlay band | zero-fill window | |
| `0x801F6C00`– **(no end)** | — | overlay band | base only | `SCENARIO` |

`0x801CE000` is the eleventh band and is absent from the ten-band map in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) because `LOGO/LOGO.EXE` is a
standalone PS-EXE, not an `.EMI` section.

### Where each field comes from

| Source | Gives |
|---|---|
| [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) ten-band map | the ten `.EMI` band bases, occupants, unique sections, unique bytes (`tools/emi_survey.py`, every section's TOC preview checksum verified) |
| [`OVERLAYS.md`](OVERLAYS.md) §1 | the image zero-run scan → each band's zero-fill window |
| [`band-overlap-attribution.md`](band-overlap-attribution.md) | measured occupant spans for the three overlapping bands, including `0x801CE000` |
| `src/bof3_localize.c` | `AREA_BLOCK_LO` / `AREA_BLOCK_HI` and the insert record geometry, as the shipping plugin defines them |
| [`TEXT_ENGINE.md`](TEXT_ENGINE.md) | the live text block's end, which splits the two message pools |
| `disc_probe.json` | the EXE image bounds — never hardcoded in the tool |
| psx-spx | the BIOS kernel area (the framework's external-comparative rule) |

## Three rules for reading a region

**1. `end` is exclusive, and `bound` says what it *is*.** The sources are not
equally strong. A `measured occupant span` came from the capture data. A
`zero-fill window` is the image's zero run: it bounds where occupants *may* land
and is **not** proof that one reaches it. Band `0x801F6C00` has no `end` at all,
because no committed source gives one — its occupants total 452,782 bytes while
the EXE image ends 1,024 bytes past its base, so the extent is genuinely unknown
without the catalog. **Never quote an `end` without its `bound`.**

**2. Regions overlap, and every match must be reported.** `LOGO.EXE` covers the
PLCHAR band entirely and straddles 109,568 bytes of the swap slot, because they
are resident at different times. First-match-wins is the `pc_coverage.py` bug
that [`band-overlap-attribution.md`](band-overlap-attribution.md) was written
about, so `xref.py` lists **every** containing region, narrowest first, and
`regions.py list` separates 13 containments-by-construction from the 2 real
straddles.

**3. Containment is context, not a name.** An address inside the swap slot is
still unnamed. Only an exact `base` counts as resolved.

## Using them

```bash
python tools/regions.py list                     # the region map and its overlaps
python tools/regions.py check                    # re-derive; nonzero on drift
python tools/regions.py seed                     # merge (keeps alias / note)

python tools/xref.py lookup 0x801EF400           # identity + every citation
python tools/xref.py queue --min-docs 3          # cited but unnamed, ranked
python tools/xref.py shared                      # addresses 2+ documents discuss
python tools/xref.py stats                       # coverage
python tools/xref.py index --out docs/XREF.md    # regenerate the cross-reference
```

What `lookup` resolves, in order: an exact boot symbol, exact overlay
function(s), an exact data island, an exact region base, a layout landmark from
the probe, membership in `seeds/ghidra_funcs.txt`, then the nearest named entry
at or below within `0x1000` — across both boot symbols and overlay functions,
labelled as a *neighbourhood*, because neither side records a span. Three worked
answers from the current tree:

| Address | What comes back |
|---|---|
| `0x801EF400` | `≤ BattleResult_Setup +0x70` in `BATL_END.EMI#0` — which is what the hand-written evidence note in `names/functions.toml` says in prose |
| `0x801D0C04` | inside both `band_801D0C00` (+0x4, measured span) and `band_801CE000` (+0x2C04) — the overlap, surfaced without being asked |
| `0x80093800` | the boot EXE load address, *and* a band base: both are true |

Regenerate [`XREF.md`](XREF.md) when `docs/`, `symbols.toml` or `names/` change.
Run `regions.py check` after editing any source doc it parses; it exits nonzero
and names the field that drifted.

## Limits

- **Only main-RAM `0x80xxxxxx` literals are recognised.** Instruction words
  (`0x843813E0`), hardware registers (`0x1F801810`) and bare offsets are not
  addresses in this sense.
- **An address cannot say code vs data.** 81.6% of `.text` is overlay zero fill
  and named data shares addresses with sibling code
  ([`DATA_ISLANDS.md`](DATA_ISLANDS.md)). These maps report the span and what the
  layer claims; they never guess which.
- **Unnamed is not a defect.** Of 2,162 addresses cited across `docs/`,
  `symbols.toml` notes and `names/` evidence, 676 resolve to a name and 28 more
  are unnamed JAL roots. Most of the rest are RAM variables, which have no home
  at all — see below.
- **The region snapshot in this document can go stale.** The sidecar cannot:
  `check` re-derives it from the sources.

## Traps already paid for

**The dash in a documented range is not reliably inclusive.** Two bounds were
initially read wrong, and both were caught by a byte count the source itself
states. The zero-run table's `0x80093801`–`0x800C1800` is given as 188,415
bytes, which is the *exclusive* difference. The live text block's
`0x80014000`–`0x80017628` is given as 13,864 bytes, so `0x80017628` is one past
the end, not the last byte — the same convention `AREA_BLOCK_HI` uses. An
off-by-one there would have put a byte of RAM in the wrong message pool. Every
bound `regions.py` parses is now asserted against a stated count, and the parse
fails loudly rather than shifting a bound silently.

**A TOML emitter that writes addresses in decimal hides drift.** `name_map.py`'s
`_emit_table` wrote integer fields as decimal, which rendered the first sidecar
as `base = 2147483648` and silently defeated the first drift test (the tamper
never matched). `base` and `end` now emit as `0x%08X` like `pc`.

## Open

- **The single RAM variable has no home.** `symbols.toml` holds `[[func]]`
  entries only. `0x801490AC` is `MSG_STR_CUR` and `0x801490A8` is
  `MSG_STR_BASE` in `src/bof3_localize.c`, each cited in six or seven documents,
  and the naming layer cannot say so. A `names/variables.toml` seeded from the
  plugin's own defines and the confirmed RAM map in
  [`BATTLE_RAM.md`](BATTLE_RAM.md) would close it.
- **Band extents could be exact.** On a machine with `analysis/` populated,
  `regions.py` could take every band's real max occupant extent from
  `overlay_captures_all.json` instead of the zero-fill window, and give
  `0x801F6C00` the `end` it currently lacks.
- **The `queue` top is now real work:** `0x8015E908` (a JAL root, known game
  code rather than library — [`HANDOFF.md`](HANDOFF.md) → *The data-anchor loop*, the Psy-Q signatures row),
  `0x801CEEDC`, `0x80143F00`.
