# EMI section types — what the container declares, and what it can't tell you

**Status:** STABLE (established 2026-09-08). Source: `analysis/emi_sections.json`
(JP disc, 6,344 sections) via [`tools/emi.py`](../tools/emi.py); the format
itself is the community data doc
(https://glitcheddragon-dev.github.io/BoF3-Data-Doc/DataStructures/1_TheEmiFiles.html),
which [`tools/emi.py`](../tools/emi.py) already implements.

## Why this exists

Every `.EMI` TOC entry carries a type id at `+0x0C`. The community doc names
five (0, 3, 6, 7, 10). This is the census across the whole JP disc, the
identification of the two it does not name, and — the practical point — what
the type id can and cannot be used for.

## The census

| type | sections | meaning | our survey class |
|---:|---:|---|---|
| 0 | 2,623 | misc / untyped | 2,006 `data`, 460 `code`, 67 `mixed`, 90 `not-ram` |
| 6 | 1,020 | audio header (VH) | all `not-ram` |
| 7 | 1,020 | audio samples (VB) | all `not-ram` |
| **8** | **904** | **audio bank companion — see below** | all `not-ram` |
| 3 | 593 | image | all `not-ram` |
| 10 | 119 | sequence (SEQ) | all `not-ram` |
| **1** | **65** | **character payload — see below** | all `data` |

## Type 8 — an audio companion record, and `+0x04` is not a pointer

904 sections, 4–96 bytes (median 28). **901 of them are flanked by a type 6
before and a type 7 after, all three sharing the same `+0x04` value**; the
other 3 follow a type 10 instead of a type 6. So a type 8 is a small record
belonging to each VH/VB pair, not free-standing data.

**Decoded 2026-09-17 ([`SOUND_CUES.md`](SOUND_CUES.md) "Inside an .EMI"):** the
type 6 is the VAB header (`pBAV`), the type 7 the VAB body, and the type 8
record is the **cue-table entries** the file installs at the head of its
bank's table — 4 bytes per cue word, so 24 bytes = 6 cues, 64 = 16
(`tools/audio_banks.py`).

Its `+0x04` field takes only the values **0..6**. That field is the RAM
destination for every other type, so **the TOC's `+0x04` is type-dependent** —
for the audio triples it is a bank/slot id, not an address. Anyone reading the
community doc literally will mis-parse these; that is worth reporting upstream.

`BIN/BENEMY/*.EMI` is the clean illustration and a naming trap: all 200 files
consist of exactly `(6, 8, 7)` with bank id 6 and **nothing else**. The
directory holds enemy *sound*, not enemy stats. There are no RAM-destined
sections in it at all.

## Type 1 — the character payload at `0x80033800`

65 sections, 124–332 KB, in `BIN/BPLCHAR`, `BIN/PLCHAR` and `BIN/ETC`. Every
one is destined for **`0x80033800`**, and in 44 of the 65 files a type-0
section in the *same* file targets that same address — two alternate payloads
for one character buffer. Consistent with model/animation data; the exact
layout is not decoded.

`BIN/BPLCHAR/BPLD012.EMI` end to end:

| idx | type | size | `+0x04` |
|---:|---:|---:|---|
| 0,1,2 | 6, 8, 7 | 4128 / 24 / 29760 | bank 3 |
| 3 | 0 | 16,384 | `0x80033800` |
| 4,5,6 | 6, 8, 7 | 4128 / 24 / 30960 | bank 4 |
| 7 | **1** | 166,846 | `0x80033800` |
| 8,9,10 | 6, 8, 7 | 4128 / 24 / 30832 | bank 5 |

## What the type id is good for — and what it is not

**Good for: ruling assets out.** All 406 sections we compile as overlays are
**type 0** (405 matched by md5; the 406th is `LOGO/LOGO.EXE`, not an EMI
section). Not one image, audio or sequence section enters the overlay path. So
a question like "could this rejected entry be a pixel sheet?" is settled by the
container rather than by byte heuristics: it cannot, because art is type 3 and
type 3 is never compiled.

**Not good for: telling code from data.** The granularity is the whole section,
and *every* game-logic table lives in type 0 alongside the code that reads it —
the level/growth table (`0x801CC068 + roster*0x318 + level*8`, in `GAME.EMI`),
the ability table (`0x801CB230`), the item tables, and every data island in
[`DATA_ISLANDS.md`](DATA_ISLANDS.md). Since 100 % of compiled sections are
type 0, "this address is in a type-0 region" has no discriminating power — there
is no contrast class. A per-image code/data map has to come from elsewhere
(see [`DATA_ISLANDS.md`](DATA_ISLANDS.md) on why the reachability walk is sound
but incomplete, and the pointer-seeded version unsound).

## Reproducing

```bash
python tools/emi.py list "<an .EMI>"    # TOC with type ids, dests, and the preview check
python tools/emi_survey.py "<disc.cue>" --out analysis/emi_sections.json
```

The census in this doc is a group-by over `analysis/emi_sections.json`
(`type`, `class`, `dest`, `size`, `file`, `index`) — no extra tooling needed.
