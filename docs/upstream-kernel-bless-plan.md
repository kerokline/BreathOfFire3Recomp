# Upstream plan — make the patched BIOS exception handler run native

**Status:** DONE 2026-09-11 (same day) — implemented as ONE change, not three
PRs, on `psxrecomp` branch `feat/kernel-install-slot-ranges` (`c12f0371`, off
upstream master `6f77dcc3`). Steps 1-3 do not pay off separately, and the plan
was missing a fourth part (the interpreter hand-back at the range end) plus a
trap that wedged the boot (a dispatch key inside a declared range). Results and
both corrections are in
[`kernel-patch-sites.md`](kernel-patch-sites.md) → *The fix and what it bought*.
Step 4 (measure) is done; the pin bump and the PR are the open items, along
with re-measuring on a second title before merge. Step 5 (vector trampolines)
is untouched and is now 87% of what OpenBIOS kernel RAM still interprets.

**Was:** PLAN (written 2026-09-11, after [`kernel-patch-sites.md`](kernel-patch-sites.md)).
Target repo: `RetroPortingToolKit/psxrecomp` (we can push there). Work in a
fork branch off the current pin (`ed55299b`, see HANDOFF → *Pins and
branches*), open one PR per step below, bump the gitlink here when merged.
Nothing in this plan touches this title's repo except the pin and the
measurement re-run.

## Why

44.6 % of every interpreted instruction this title executes is kernel RAM,
and 1.22 of those 1.48 billion are the BIOS exception handler. It is compiled
on both BIOSes; it interprets because the game's Psy-Q patchers rewrite its
bytes at boot and the kernel-bless verifier then refuses it for the life of
the process. Retail v2.2 proves the framework's existing answer does not
work: the card stub lands exactly in the declared `install_slots` 0xCF0 and
the handler body still fails the bless check. Evidence, both images:
[`kernel-patch-sites.md`](kernel-patch-sites.md).

## The mechanism today (what the PRs change)

| Piece | Where | What it does now | Gap |
|---|---|---|---|
| Install-slot hook | `recompiler/src/full_function_emitter.cpp` ~L1195 (`is_install_slot`) | At a declared slot PC, emits `if (read_word(slot) != 0) { pc = slot; return; }` and registers `slot+0x10` as a continuation | Assumes a 4-word `lui/addiu/jalr/nop` stub over ROM **zeros**; fires on `!= 0` only; one PC, no range |
| Slot declaration | `bios/<stem>.toml` `[[recompiler.install_slots]] ram_addr` → `config_loader.cpp` L1063, `bios_address_model.cpp` L94/L204 | Single 4-aligned RAM address | No length, no expected-ROM-word; OpenBIOS declares none |
| Bless verifier | `runtime/src/memory.c` `psx_kernel_bless_dispatchable` (L248) + `kbless_note_write` | Per body, lazy `memcmp(ram, rom, body_hi-body_lo)`; any mismatch → interpreter, re-verified only after a write inside the body | **Knows nothing about slots** (`grep install_slot runtime/` is empty); slot words are inside the compared range, so a live stub unblesses its body forever |
| Body table | emitted `PsxKernelBody {key, body_lo, body_hi}` (`psx_bios_image.h` L23), `<stem>_dispatch.c` | One extent per dispatch key; continuation keys share their parent's extent | No per-body list of "words the runtime may legitimately find changed" |

## Step 1 — publish slots to the runtime and verify around them (the fix that matters)

PR title: *kernel-bless: exclude declared install slots from body verification*

1. Emitter: next to `psx_bios_kernel_bodies`, emit a per-image
   `PsxKernelPatchRange { uint32_t lo, hi; }` table from the profile's
   install slots (`hi = lo + 0x10` for the legacy 4-word form; see Step 2
   for ranges), and publish it through the backend descriptor the same way
   the body table is (`psx_bios_backend.c` sets the active pointers).
2. `memory.c`: in `psx_kernel_bless_dispatchable`, compare the body in
   segments that skip every patch range intersecting `[body_lo, body_hi)`.
   Keep `kbless_note_write` as is — a write *into a slot* still invalidates
   the cached CLEAN state, which is correct (the next dispatch re-verifies
   the non-slot bytes and passes).
3. The emitted hook stays as the thing that actually executes the stub; the
   body is now allowed to be CLEAN with a live stub inside it, so native
   code reaches the hook, dispatches into the interpreter for the stub, and
   comes back through the registered continuation.
4. Tests: extend `recompiler/tests/bios_address_model_test.cpp` (slot →
   range emission) and add a runtime unit test that builds a fake body +
   ROM, patches a word inside a declared range, and asserts
   `psx_kernel_bless_dispatchable` returns 1; patch a word *outside* the
   range and assert 0. The runtime tests live in `runtime/tests/` (see
   `test_bios_hle_plan.c` for the harness shape).
5. Acceptance on retail v2.2 (`tools/kernel_patch_diff.py --bios …` here):
   `kernel_bless.mismatch` drops from 75 and the exception handler body
   `0x0C80..0x0EA0` is no longer listed under "bodies containing a patched
   word (these interpret)" — *once Step 2 also covers the Cause patch*.
   Step 1 alone fixes the 0xCF0 stub only.

Rule check: this is Rule 18 territory and stays LLE — the stub still runs
its own instructions on the dirty-RAM interpreter; nothing is synthesised.

## Step 2 — generalise the slot model to what the Psy-Q patches actually do

PR title: *install slots: ranges and expected-ROM-word compare*

Observed shapes (both images, `kernel-patch-sites.md`):

| Shape | Example | Fits today's model? |
|---|---|---|
| 4-word `jalr` stub over ROM zeros | retail 0xCF0, OpenBIOS 0x281C | yes |
| 4-word `jr` stub over **real ROM instructions** | retail 0x6444, OpenBIOS 0x357C (card handler → boot EXE 0x8017EAA0) | no: `!= 0` never fires, and the hook expects a `jalr` return at `+0x10` (a `jr` never returns) |
| 11-word prologue rewrite + inserted `mfc0 Cause` | retail 0x0C88..0x0CB8, OpenBIOS 0x27B4..0x27E4 | no: not a stub, no return; the patched words *are* the function |
| 11 words NOP'd | retail 0x4964, OpenBIOS none (pad clear removed) | no |
| 5-word `jalr` into the boot EXE | retail 0x4D98 | almost (ROM words non-zero) |

Schema change (`config_schema.md` § BIOS profiles), backward compatible:

```toml
[[recompiler.install_slots]]
ram_addr = "0x00000CF0"          # legacy: len 0x10, jalr-return continuation at +0x10
[[recompiler.install_slots]]
ram_addr = "0x00000C88"
len      = "0x30"                 # patched RANGE [ram_addr, ram_addr+len)
resume   = "fallthrough"          # continuation = ram_addr+len (default); "jalr" = legacy +0x10
```

Emitter: the hook becomes "if any word in the range differs from its
ROM-baked value, dispatch to `ram_addr`"; register `ram_addr + len` (or
`+0x10` for `jalr`) as block leader + local continuation, exactly as the
existing code does for `post_stub_rom`. `memory.c` reads the same ranges
from Step 1's table. `bios_address_model.cpp` validates 4-alignment of
both ends and non-overlap.

Why this is still not HLE: the interpreter executes the game's patched
instructions as written; the only thing that changes is that the *rest* of
the function is allowed to run native around them.

## Step 3 — declare the slots

PR title: *bios profiles: install slots for the Psy-Q kernel patches*

Retail `bios/SCPH1001.toml` (v2.2), from `analysis/kernel_patch_diff_scph1001.json`:

| ram_addr | len | shape |
|---|---|---|
| 0x0500 | 0x4 | trampoline word (verify what writes it before declaring) |
| 0x0C88 | 0x30 | prologue rewrite + `mfc0` (fallthrough) |
| 0x0CF0 | 0x10 | existing slot, `jalr` |
| 0x4964 | 0x2C | pad clear NOP'd (fallthrough) |
| 0x4D98 | 0x14 | `jalr` into boot EXE (`_patch_card2`) |
| 0x6444 | 0x10 | `jr` into boot EXE (`_patch_card`); no return — `resume` irrelevant |

OpenBIOS `bios/OpenBIOS.toml`, from `analysis/kernel_patch_diff.json`:

| ram_addr | len | shape |
|---|---|---|
| 0x27B4 | 0x30 | prologue rewrite + `mfc0` (fallthrough) |
| 0x281C | 0x10 | `jalr` stub into `exceptionHandlerCardFastTrack` |
| 0x357C | 0x10 | `jr` into boot EXE |

Also fill `[program.image] sha256` in `SCPH1001.toml` with the v2.2 hash
(`sha256sum` of the CRC-`37157331` image) so a wrong revision refuses to
generate instead of producing phantom discovery gaps (the v2.0 detour in
`kernel-patch-sites.md`).

These addresses are one title's observations. Before merging, run the same
diff on the framework's other titles (Tomba is the reference project) — the
Psy-Q patchers are per-SDK-version and the ranges may differ by a word or
two between libapi releases; the schema in Step 2 tolerates that (declare
the union), the numbers must not be assumed.

## Step 4 — measure here, then bump the pin

1. Bump `psxrecomp` gitlink to the merged commit, `axis_b_loop.sh
   --skip-harvest` if the overlay layer moved (HANDOFF → *Building against
   the pin*), rebuild `build-relprof`.
2. `python tools/kernel_patch_diff.py` on both images: the "bodies
   containing a patched word" list should be empty for the exception
   handler; `kernel_bless.mismatch` ≈ 0.
3. One play session, then `tools/harvest_interp_pcs.py`: the `kernel`
   owner line should fall from ~1.5 B instructions to the vector
   trampolines only (~190 M). Record in STATUS.
4. If it does not: the enrichment tool (`tools/enrich_pcs.py`) on the
   surviving kernel PCs says which body is still unblessed and why.

## Step 5 (optional, discuss first) — the A0/B0/C0 vector trampolines

187 M interpreted instructions but 90 M *entries* at 0xB0: the cost is a
dispatch round-trip per kernel call, not instruction count. The profile
excludes the 4×16-byte vector stubs by design ("runtime-written
trampolines → dirty-RAM interp, rule 18"). Two options if it matters after
Steps 1–3: model them as a Step-2 range whose ROM source is the copy loop's
constant, or leave them and accept the per-call overhead. Measure before
choosing; do not bundle with the PRs above.

## Not in scope

- Kernel-call HLE on OpenBIOS (`deliver_event_ret`): a separate validation
  job against the Beetle oracle, only worth it if card-screen polling still
  shows after Step 4.
- Any C reimplementation of card, pad or event services
  (`docs/dynamic_handler_install.md` "NOT HLE").
- Per-title shims in `game.toml`: the patches are Psy-Q's, every SDK title
  does this, the fix belongs in the framework.
