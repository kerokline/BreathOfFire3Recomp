# Walk roots for CPS overlays — a handoff for other psxrecomp titles

**Status:** reference, written 2026-09-17 for
[psxrecomp#380](https://github.com/RetroPortingToolKit/psxrecomp/issues/380)
(Ace Combat 3, "captures never record function entries"). Everything below is
measured on Breath of Fire III (SLPS-00990) against psxrecomp `b30cdcf5`
(master `193a60b8` plus two fork fixes). Nothing here is AC3-specific; the
point is that we hit the same failure a fortnight earlier, took a different
door out, and the door is generic.

**Audience:** an agent picking up another title's overlay compile. Read this,
then the files in *Where the code is*, and you can write the enrichment pass
for your own repo in an afternoon.

## 1. TL;DR

- `runtime/src/overlay_capture.c:438` really does write
  `"function_entry_pcs": []` as a literal. Confirmed at our pin. Runtime
  captures carry dispatch PCs only.
- You do **not** need `game.toml [[overlays]]` to supply the missing roots.
  `compile_overlays.py` reads a per-capture field
  **`static_discovery_entry_pcs`** and re-validates every address with its own
  callable test before promoting it to a walk root. Put your derived entries
  there. It is the sanctioned channel; it is just undocumented in
  `config_schema.md`.
- The derivation the reporter did by hand (JAL targets plus prologue-shaped
  words) is exactly what our extractor does by default, plus two more sources
  that turned out to matter more: **in-image pointer tables** and **the
  engine's own loader records**. Section 4 gives each one as an algorithm.
- The framework already ships the primitives:
  `psxrecomp/tools/aot_overlay_spike/extract_generic.py` has `direct_jal_roots`,
  `prologues` (handles the Psy-Q `lui`/`lw` prelude that starts a function
  eight bytes before `addiu sp`), and `pointer_table_targets`. What it lacks is
  a mode that takes an existing runtime `overlay_captures.json` and enriches
  it. That is a ~100-line script (section 6).
- The island explosion the issue describes is the same thing we measured as
  interior-entry fragmentation ([`OVERLAY_SIZE.md`](OVERLAY_SIZE.md)). Roots
  shrink it; they do not remove it.

## 2. The same failure, here

BoF3 is ~90% overlays (405 code images across eleven RAM bands, up to 181
occupants per band). The engine enters them by `jalr` through tables, not by
`jal`, so a live capture sees interior PCs and almost no prologues. Before the
static roots existed, the interpreter carried 1.65M instructions per frame in
one world band, and the "compiled band, still interpreted" symptom cost a full
session before it was traced to the compile side, not the capture side.

What the issue calls "104 of 160 images rootless" we saw as: a band declared
compiled, `SKIP: no shared walk-root seeds` deep in a long log, and every
entered PC served as an isolated `ov_frag_<band>_<crc>_<entry>` unit. Our
measured shape of that outcome, before roots:

| | value |
|---|---|
| overlay `generated/` size | 1.64 GB for 3.70 MB of MIPS (~440x; the main EXE is 47x) |
| share of that in fragments | 79% (395 of 779 shards contain only `ov_frag_*`) |
| worst band | one occupant, 9 KB of code, 622x expansion |
| interior entries in the densest band | ~1 per 26 instructions |
| dedup of identical `(crc, pc)` bodies | only 1.4x, because the bodies are small |

The 9-10% headless throughput cost of the fragment-heavy binary was real
(i-cache and TLB). One AC3-style symptom we never reproduced but should have
looked for: the reporter says a function compiled *wrong* as an island and
*right* inside a region. We only measured size and speed. If you see a
miscompile that vanishes when a root covers the function, that is the same
mechanism and worth an isolated report.

## 3. How the compiler consumes entries (read this before writing any)

`psxrecomp/tools/compile_overlays.py`, `classify_overlay_seeds` (around line
1500). Per capture it reads:

| field | meaning | what happens to it |
|---|---|---|
| `executed_pcs` / `observed_pcs` | every PC the interpreter ran | coverage only, never a root |
| `dispatch_entry_pcs` | PCs the runtime *entered* by dispatch | promoted to a root only if it passes the callable test, else `DISPATCH_INTERIOR` (served as a fragment) |
| `static_dispatch_entry_pcs` | subset of the above that came from a header/export table you trust | classified `STATIC_DISPATCH_ENTRY`; must be a subset of `dispatch_entry_pcs` or the compile raises |
| `function_entry_pcs` | runtime-proven function starts | always empty today (the bug) |
| **`static_discovery_entry_pcs`** | roots you derived from the bytes | each re-validated by `_callable_legacy_seed` / `plausible_callable_target`; survivors are `STATIC_DISCOVERY_ROOT` walk roots, failures are dropped and counted |
| `seeds` | legacy alias of dispatch entries | ignored when any split-schema key is present |
| `game.toml [[overlays]] entries` | the door the reporter used | unioned into the same pre-root set, keyed by `load_addr` and `bytes_crc` |

Two consequences:

1. Wrong guesses are cheap. A bad `static_discovery_entry_pcs` address is
   excluded with a count in the seed audit, never fabricated. Over-approximate
   freely, then read the audit line:
   ```
   dispatch_entry_pcs: 11          static_discovery_roots_included: 497
   function_entry_pcs: 500         dispatch_interior_included: 2
                                   observed_only_excluded: 0
                                   unknown_excluded: 0
   ```
   `unknown_excluded` climbing is your signal that a derivation rule admits
   data. Our first pointer-root pass doubled audit-failed shards (26 to 53)
   until the CFG proof was added; the audit line is where that showed.
2. The callable test is the gate, so learn what it accepts.
   `_callable_legacy_seed` (line 1079) is the shape test the issue describes
   (`addiu sp,sp,-N` not preceded by control flow, or a `jr $ra` two words
   back). `plausible_callable_target` (line 1193) is the stronger one: first
   word decodes and is non-zero, not the head of a dense local pointer table,
   and a bounded forward walk (16 KB cap) in which every word decodes, no
   branch leaves the image, and a return is reachable. **Frameless leaf
   functions pass the second test and fail the first.** Use the second for
   anything that is not a direct call target.

## 4. Where roots come from, in order of what they bought us

All of these read the capture's own bytes (or the disc). None invent an
address that is not in the image. Each is one function in
`tools/extract_overlays.py`; the algorithm is given so you can port it.

### 4.1 Direct call targets (`jal_targets`)

Every word with opcode 3; target = `(load_addr & 0xF0000000) | ((w & 0x03FFFFFF) << 2)`;
keep if inside `[load_addr, load_addr + len)`. Direct call-edge proof; no
further test needed. Cross-image JALs (into the boot EXE) are dropped because
they are not this image's functions.

### 4.2 Prologues after a return (`prologue_roots`)

`addiu sp,sp,-N` (`(w >> 16) == 0x27BD` and bit 15 set) at word index 0, or
where `words[i-2] == 0x03E00008` (`jr $ra`, so `i-1` is its delay slot). The
"two words back" rule is what keeps this from matching a stack adjust in the
middle of a function. Prefer the framework's `extract_generic.prologues`,
which also recovers the `lui`/`lw` prelude Psy-Q schedules before the `addiu`;
without it the root lands eight bytes late and the real dispatch entry stays
uncovered.

### 4.3 In-image pointer tables (`pointer_roots`) — the one that closed our residual

Every aligned word whose value is a 4-aligned address inside the same image.
Keep it if the target either follows a `jr $ra` delay slot or opens with a
prologue, **and** `plausible_callable_target` accepts it. These are the small
per-entity handler tables that sit in the middle of an image and hang off
nothing a static walk sees. In a headless sweep of all 200 of our area
overlays, every one of the 19 residual interpreted (area, pc) pairs was this
shape, and there were 2,393 such candidates game-wide. For a
continuation-passing engine this is the class most likely to hold your resume
points: the continuation is stored as a word somewhere, and that word is
often in the image.

### 4.4 Export/header tables (`header_entries`)

Our images open with `u32 registry_id` then a run of in-image pointers. The
run ends at the first word that is not an aligned in-image address. These are
`static_dispatch_entry_pcs` (a trusted subset of dispatch entries), not
discovery roots, because the game reaches them by dispatch. If your format has
a header (the `{count, ptr[count]}` producer in `extract_generic.py` handles
one common shape), seed it the same way.

**Trap:** one header table in our set (GAME.EMI section 0) is consumed by the
overlay's *own* code, not by the engine, and seeding it as an entry point was
wrong ([`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §2). A header run is
evidence the words are code, not evidence the engine enters there.

### 4.5 The engine's loader records (`load_engine_entries`) — what play was really discovering

The question we asked after weeks of harvesting entries from play was: what
does play find that the disc does not hold? For every overlay family the
answer was nothing. The engine keeps a table of where it enters each image:
an area descriptor with an init pc and a handler array, a per-ability handler
pc, a per-boss entry, a per-chapter vtable. All of it is in the boot EXE or a
resident image, read off the disc by `tools/loader_records.py` into
`names/*_records.toml`, and joined back to each capture by section hash.
1,398 entries, 914 of them in no other seed set, 0 counter-examples across
four families ([`LOADER_RECORDS.md`](LOADER_RECORDS.md)).

For a CPS title this is the high-value target. Whatever schedules the
continuations holds their addresses in a table or a struct field. Find the
`jalr` sites in the resident code, walk back to what loads the register, and
you will usually find a table with a file id or slot number beside the pc.
That table is worth more than any amount of play harvesting, because it is
complete. If the continuation pc is computed at runtime (stored into a task
struct by the function that yields), the store site tells you the shape and
`harvest_interp_pcs.py` (4.6) gives you the values.

### 4.6 Observed entries from play (`harvest_interp_pcs.py`) — additive only

`dirty_ram_stats.per_pc` records each interpreted PC with an `entries` count.
`entries > 0` is an empirically proven entry; a fall-through PC is not. Union
into `dispatch_entry_pcs` across sessions (two sessions of ours shared 323 of
~17,500 PCs; overwriting the file throws away every area you did not revisit).
This is what the runtime capture already gives you, so for the issue's case it
adds nothing until the static roots exist.

## 5. Traps we paid for

- **Islands keyed by bare address across variants.** `compile_overlays --static`
  resolved fragment demands by entry address across all captures, so in a band
  with 128 occupants only the last one ever got fragments. The runtime
  CRC-validates each unit against the exact bytes it was compiled from, so a
  fragment from occupant A can never serve occupant B. Fixed upstream (#325);
  if your pin predates it, "compiled band, still interpreted" is this.
- **Per-occupant attribution was the wrong lever for size.** We assumed
  fragment volume scaled with occupants per band. Measured: a one-occupant
  band expands 622x, the 181-occupant band 266x. The driver is interior
  entries per KB. Roots are the lever; the remaining lever is one translation
  unit per image with interior entries as labels (the two whole-image bands
  sit at 92x).
- **Seeding the boot-EXE analyser does nothing for overlays.** Extending the
  static seed list from 523 to 868 functions produced a byte-identical
  generate. Seeding observed interior overlay PCs into it made the emitter
  alias into zero-fill. The overlay lane and the seed lane are different
  tools ([`OVERLAYS.md`](OVERLAYS.md) §3).
- **A flat A/B after adding roots does not mean the roots dropped.** If the
  scenes you measure were already harvested by play, the roots only pay in
  unplayed content. Check `static_discovery_roots_included` in the compile
  log, then measure a fresh area.
- **A "dispatch" PC can be a jump-table case label.** It proves coverage, not
  a callable boundary; the compiler classifies it `DISPATCH_INTERIOR` on
  purpose. Do not force those into roots.
- **Zero-fill dispatch entries are usually real.** 182 of our 211 "entries into
  zeros" were overlay landing zones the boot image fills at runtime, not
  fabrications. Audit before deleting.
- **Shared bands need residency, not addresses.** When several images load at
  one address, an interpreted PC cannot be credited to an image by address
  alone. We byte-match live RAM to captures (`tools/enrich_pcs.py`).
- **The file-cap jam is silent by design today.** `capacity_fastpath=N` with
  `ok=0` means "every image skipped before decode". Treat that line as an
  error in your own wrapper until the framework does.

## 6. Recipe: enrich existing runtime captures

You have `overlay_captures.json` from the runtime with `load_addr`, `size`,
`bytes_b64`, `dispatch_entry_pcs`. Per record:

```python
import base64, struct, sys
sys.path.insert(0, 'psxrecomp/tools')
sys.path.insert(0, 'psxrecomp/tools/aot_overlay_spike')
import extract_generic as eg
from compile_overlays import plausible_callable_target

def enrich(rec):
    data = base64.b64decode(rec['bytes_b64'])
    base = int(rec['load_addr'], 16)
    roots = set(eg.direct_jal_roots(data, base))          # 4.1
    roots |= set(eg.prologues(data, base))                # 4.2, prelude-aware
    lo, hi = base, base + len(data)
    for (w,) in struct.iter_unpack('<I', data[:len(data) // 4 * 4]):   # 4.3
        if lo <= w < hi and not (w & 3) and plausible_callable_target(data, base, len(data), w, hi):
            roots.add(w)
    rec['static_discovery_entry_pcs'] = sorted('0x%08X' % a for a in roots)
    return rec
```

Then recompile with the same captures file and read the seed audit. Expect
`static_discovery_roots_included` in the high hundreds per image and a
non-zero `unknown_excluded`; the latter is the callable test doing its job.
Do 4.4 and 4.5 next, once you know your loader.

Smoke-tested 2026-09-17 on three of our own captures at pin `b30cdcf5`. It
recovers every root our production extractor emits and adds more candidates
(the framework's `prologues` is prelude-aware and the pointer scan is not
restricted to dense tables); the compile-time callable test is what trims
those back:

| image | bytes | JAL | +prologues | +pointers | extractor's roots | recovered |
|---|---|---|---|---|---|---|
| `0x80093800` | 133,124 | 107 | 433 | 576 | 303 | 303 |
| `0x80196800` | 227,556 | 357 | 643 | 953 | 497 | 496 |
| `0x801CE400` | 6,616 | 6 | 27 | 28 | 8 | 8 |

Check the `extract_generic` signatures against your pin before running; the
spike module is not a stable API. `eg.jal_targets(data)` is base-independent
and returns cross-image targets too, which is why the recipe uses
`direct_jal_roots(data, base)` instead.

## 7. Where the code is

| file | what to read it for |
|---|---|
| `tools/extract_overlays.py` (this repo) | `jal_targets`, `prologue_roots`, `pointer_roots`, `header_entries`, `load_engine_entries`, and the docstring that explains each seed class and its A/B flag |
| `tools/loader_records.py`, `docs/LOADER_RECORDS.md` | how the engine's entry tables were found and proven statically (the method transfers; the addresses do not) |
| `tools/harvest_interp_pcs.py` | union-across-sessions harvest of entered PCs from a live debug-tools build |
| `tools/enrich_pcs.py` | attribute an interpreted PC to the resident occupant of a shared band by byte-matching live RAM |
| `tools/interp_bucket.py`, `tools/interp_bench.py` | where the interpreter's time goes, per band and per PC, and the A/B harness |
| `docs/OVERLAY_SIZE.md` | the fragmentation measurements in section 2 |
| `docs/OVERLAY_EXTRACTION.md` §5-§12 | the compile/measure loop and the three upstream dispatch fixes |
| `psxrecomp/tools/compile_overlays.py` | `classify_overlay_seeds` (~1500), `_callable_legacy_seed` (1079), `plausible_callable_target` (1193), `_collect_toml_overlay_entries` (1467) |
| `psxrecomp/tools/aot_overlay_spike/extract_generic.py` | the framework's own `prologues` / `direct_jal_roots` / `pointer_table_targets` |
| `psxrecomp/docs/AOT_OVERLAY_PLAN.md` line ~238 | the capture schema as designed, including the never-filled `function_entry_pcs` |

## 8. What we would upstream, if the issue wants a patch

1. An `enrich` subcommand (or standalone script) that does section 6 over a
   runtime capture file, in `psxrecomp/tools`, reusing `extract_generic`.
2. A closing summary line listing images that yielded zero walk roots, next
   to `PSX_SHARD_RESULT`, so `ok=0 capacity_fastpath=N` cannot read as
   success.
3. `static_discovery_entry_pcs` documented in `config_schema.md` as the
   intended channel for derived roots, with the `[[overlays]]` TOML route
   noted as the manual fallback.

Filling `function_entry_pcs` from the runtime is a separate change and is not
needed for the CPS case; static derivation covers it.
