# Kernel patch sites — why the BIOS exception handler runs interpreted

**Status:** FIXED UPSTREAM 2026-09-11 — see *The fix and what it bought* at the
bottom of this file. The finding below stands as the measurement that motivated
it; the numbers describe the state BEFORE the fix.

**Was:** MEASURED 2026-09-11 on both images, clean: OpenBIOS and retail
SCPH-1001 **v2.2** (CRC32 `37157331`, the image the framework profile, seeds
and `docs/psx_bios_disasm.txt` describe). An earlier retail pass on a v2.0
dump (CRC32 `55847D8C`) is retracted below. Upstream action needed; nothing
in this repo fixes it. Evidence: `analysis/kernel_patch_diff.json`
(OpenBIOS), `analysis/kernel_patch_diff_scph1001.json` (retail),
`analysis/scph1001_table_gaps.json`, tool `tools/kernel_patch_diff.py`.

## The finding in one paragraph

Across every harvested play session, the kernel accounts for **44.6 % of all
interpreted instructions** (1.48 of 3.31 billion), and 1.22 billion of those
are one function: the BIOS **exception handler**. It is compiled; the runtime
refuses to run it native because the game patches its bytes at boot, so the
kernel-bless byte check (`memory.c psx_kernel_bless_dispatchable`) fails and
the body stays on the interpreter for the life of the process. Every
interrupt (vblank, CD, SIO, timers) and every syscall crosses it, so the cost
is paid in every scene, not only on the card screens. The same thing happens
on retail SCPH-1001, and there the profile's install slot does not help.

| Interpreted instructions, all sessions (`analysis/observed_interp_pcs.json`) | Count |
|---|---|
| Total, every band | 3,311,409,583 |
| Kernel RAM below 0x10000 | 1,475,506,869 (44.6 %) |
| exceptionHandler 0x27AC..0x296C (OpenBIOS) | 1,222,787,511 |
| A0/B0 vector trampolines | 187,286,684 |
| exceptionHandlerCardFastTrack 0x3554..0x36D8 | 65,432,674 |

## What patches what — the Psy-Q kernel patches

The boot EXE carries the libapi patchers (`_patch_gte 0x8017AC30`,
`_patch_card 0x8017EAE4`, `_patch_card2 0x8017EB9C`, `_patch_pad 0x8017FD5C`;
`symbols.toml`). They write into kernel RAM. Live diff of the kernel copy
against the ROM source, 30 s into a headless boot:

### OpenBIOS (`bios/openbios.bin`) — 3 sites, all in compiled bodies

| RAM | Words | Body | What the live code is |
|---|---|---|---|
| 0x27B4..0x27E4 | 11 | `exceptionHandler` 0x27AC..0x2810 | The register-save prologue shifted up two words plus an inserted `mfc0 v0, Cause` (`40026800`). The GTE/Cause patch. Present at t+8 s. |
| 0x281C..0x2828 | 3 | `exceptionHandler` cont. 0x2810..0x296C | `lui v0,0; addiu v0,0x3554; jalr v0` — stub into `exceptionHandlerCardFastTrack`. Installed on first card access (absent at t+8 s, present at t+30 s). Same shape as the retail 0xCF0 slot. |
| 0x357C..0x358C | 4 | `exceptionHandlerCardFastTrack` 0x3554..0x36D8 | `lui v0,0x8018; addiu v0,0xEAA0; jr v0; nop` → boot EXE 0x8017EAA0 (`StopCARD_2`+0x24, the `_patch_card` payload). The game replaces the kernel's card handler with its own. |

Three more words differ in a pad table after `readPadHighLevel` (0x45FC,
0x460C, 0x461C); they are data and unbless nothing. `kernel_bless` at t+30 s:
907 bodies, 264 clean, **22 mismatch** — all continuation keys of the three
bodies above.

### Retail SCPH-1001 v2.2 — 6 sites in 5 bodies; the 0xCF0 slot is hit and still does not help

Headless boot with `--bios`, uncapped: frame 2188 at t+8 s, frame 9534 at
t+30 s, no halt. 134 differing words in the kernel copy, 35 inside compiled
code bodies, identical at both snapshots (all patches land before frame
2188).

| RAM | Words | Body | What the live code is |
|---|---|---|---|
| 0x0500 | 1 | `kernel_trampoline_0` 0x0500..0x0510 | One word of the first kernel trampoline rewritten. |
| 0x0C88..0x0C98, 0x0C9C..0x0CB8 | 4 + 7 | exception handler 0x0C80..0x0EA0 | Same as OpenBIOS site 1: the register-save prologue shifted up two words plus an inserted `mfc0 v0, Cause` (`40026800`). |
| 0x0CF0..0x0CFC | 3 | exception handler 0x0C80..0x0EA0 | `lui v0,0; addiu v0,0x641C; jalr v0` — the SIO data-byte stub, at **exactly the profile's `install_slots` 0xCF0**. |
| 0x4964..0x4990 | 11 | `ghidra_BFC13F98` 0x4498..0x49BC | Eleven instructions NOP'd — the pad driver's clear routine removed (`RemovePatchPad` / ChgclrPAD family). |
| 0x4D98..0x4DAC | 5 | `kernel_BFC1486C` 0x4D6C..0x4F54 | Jump to boot EXE 0x8017EB6C (`_patch_card2` payload). |
| 0x6444..0x6454 | 4 | `dmiss_BFC15F1C` 0x641C..0x659C | `lui v0,0x8018; addiu v0,0xEAA0; jr v0; nop` → 0x8017EAA0 — same card-handler replacement as OpenBIOS site 3. |

`kernel_bless` at t+30 s: 1299 bodies, 245 clean, **75 mismatch** (the five
root bodies above plus their continuation keys), 133 invalidations. The
exception handler body 0x0C80..0x0EA0 is one of the 75 **even though the
card stub sits precisely in the declared 0xCF0 slot**: the install-slot hook
in `full_function_emitter.cpp` dispatches into the stub, but the bless
verifier in `memory.c` still `memcmp`s the whole body, slot words included,
so the hook is never reached natively. The two mechanisms were written
separately and do not compose. And the Cause patch at 0x0C88 would unbless
the handler on its own regardless.

The pattern is therefore identical on both images: the same Psy-Q patchers,
the same three payload shapes (prologue shift + `mfc0`, stub into the card
fast path, card handler replaced by a `jr` into the boot EXE), and on both
the exception handler runs interpreted for the life of the process.

### Retracted: the v2.0 pass

The first retail attempt used a SCPH-1001 **v2.0** dump (CRC32 `55847D8C`,
1994-09-22). It halted at boot three times (`0xBFC0192C`, `0xBFC08620`,
`0xBFC13F98` at frame 341) and the live A0 table showed 90 of 161 ROM targets
uncompiled. That was the revision mismatch — the seeds name v2.2 function
starts — not incomplete upstream seeds. The regenerated backend accepted the
dump because `psx_bios_image`'s identity is stamped from whatever image you
generate from and the profile's `[program.image] sha256` is empty. Its
artefacts (`analysis/scph1001_seeds_plus.json`, `scph1001_table_gaps.json`)
are kept only as the record of that detour.

## What upstream needs (psxrecomp)

1. **Install slots for OpenBIOS** — none are declared (`bios/OpenBIOS.toml`
   says "none identified yet"). The three sites above are the list.
2. **Generalise the install-slot model.** It assumes a 4-word
   `lui/addiu/jalr/nop` stub over ROM zeros and fires on `word != 0`. Only
   site 2 fits. Site 1 is eleven reorganised instructions; site 3 (and retail
   0x63D4) overwrite real ROM instructions with a `jr`, so the zero test never
   fires. Needed: compare against the ROM-baked word, accept a patched
   *range*, and put a continuation key at the range end so the compiled body
   resumes native after the interpreter runs the patched words.
3. **Exclude slot words from the bless memcmp** (or split bodies at slots),
   otherwise 1 and 2 change nothing: the body still mismatches.
4. **Pin the retail image.** `bios/SCPH1001.toml` has an empty
   `[program.image] sha256`, so a v2.0 dump generated silently and produced
   three boot halts that looked like discovery gaps. Fill the pin (v2.2,
   CRC32 `37157331`) so the recompiler refuses a wrong revision up front.
5. **Vector trampolines** (0x80/0xA0/0xB0/0xC0) stay interpreted by design;
   187 M instructions but 90 M *entries* at 0xB0 — the cost is dispatch
   overhead per kernel call. Lower priority; discuss before changing.

Not on the table: C reimplementations of card reads or event services.
`docs/dynamic_handler_install.md` ends with "NOT HLE" and the inherited
no-hacks rule applies. Every item above keeps the kernel's own instructions
running; they change only where they execute.

## Reproduce

```bash
# OpenBIOS (default image)
python tools/kernel_patch_diff.py --exe build-relprof/BreathOfFire3_Recompiled.stripped.exe --at 8 --at 30
# retail (needs psxrecomp/bios/SCPH1001.BIN + the reseeded backend, see item 4)
python tools/kernel_patch_diff.py --exe build-relprof/BreathOfFire3_Recompiled.stripped.exe \
    --bios psxrecomp/bios/SCPH1001.BIN --profile psxrecomp/bios/SCPH1001.toml \
    --dispatch psxrecomp/generated/SCPH1001_dispatch.c \
    --seeds psxrecomp/recompiler/seeds/phase2_ghidra_seeds.json \
    --out analysis/kernel_patch_diff_scph1001.json
```

`.stripped.exe` was a hand `objcopy --strip-debug` of the relprof link,
needed for a few hours on 2026-09-11: with the DWARF sections mapped in, the
1.15 GB RelWithDebInfo image was 1.93 GiB virtual and Windows refused to
load it ("this app can't run on your PC"). `CMakeLists.txt` now splits the
DWARF into `<exe>.debug` after every link (`PSX_SPLIT_DEBUG`, on by default
for Debug/RelWithDebInfo), so the plain exe loads and the stripped copy is
redundant.

## Traps paid for

- `--bios` on the command line is the only way to pick the retail image
  headless; `bios.cfg` is empty on this machine and the launcher pick is
  remembered elsewhere. The runtime prints `image=SCPH-1001` on stdout.
- With `PSX_FAIL_FAST_UNKNOWN_DISPATCH=0` the retail boot dies silently
  instead of halting: the skipped function leaves stale registers, exactly as
  `traps.c` warns. Seed and regenerate instead.
- The retail backend is gitignored generated output; a fresh
  `cmake -S . -B build-relprof` is needed once so `PSXRECOMP_BIOS_STEMS`
  actually links it (the exe then contains `SCPH1001_psx_bios`).

## The fix and what it bought (2026-09-11, same day)

Fixed in `psxrecomp` branch `feat/kernel-install-slot-ranges` (`c12f0371`, off
upstream master `6f77dcc3`), as one change rather than the three PRs
[`upstream-kernel-bless-plan.md`](upstream-kernel-bless-plan.md) proposed —
the steps do not pay off separately. What the plan got right, and the one thing
it missed:

1. **Publish the ranges to the runtime** and skip them in the bless memcmp.
   As planned.
2. **A slot is a range** with a length and an explicit `resume` shape
   (`jalr` / `fallthrough` / `none`), compared against the ROM-baked word
   instead of against zero. As planned.
3. **Hand back from the interpreter at the range end.** *Not in the plan.*
   Kernel page 0 is permanently dirty — the handler saves registers there on
   every exception — so straight-line interpretation never leaves it, and
   without a hand-back the interpreter ran the whole function after the patch.
   The emitter registers the resume PC as a continuation key and
   `dirty_ram_interp.c` surfaces there.

**The trap, paid for in a wedged boot:** a PC inside a declared range must
never be a native dispatch key. Seven pre-existing jal-return continuations
sat inside the declared ranges (OpenBIOS `0x357C`; retail `0x4974`, `0x4980`,
`0x4984`, `0x4988`, `0x6444`). Dispatching one re-enters the compiled body,
whose patch-range hook sets `cpu->pc` back to that same PC and returns, so the
dispatch loop spins forever — the boot wedged at frame 0 and three gdb samples
showed the identical stack. The emitter now drops continuation keys inside a
range (dispatch misses through to the interpreter, the intended path) and
refuses to emit if a range covers a *function entry*.

### Result, headless, matched frames

`PSX_KERNEL_PATCH_RANGES=0` drops the declared ranges at runtime and restores
the whole-body memcmp, so one binary measures both sides
(`tools/kernel_patch_ab.py`; artefacts `analysis/kernel_patch_ab_openbios.json`,
`analysis/kernel_patch_ab_scph1001.json`).

Both sides run with `PSX_BIOS_HLE=0`, so the kernel-call HLE tier cannot move
the number. That matters only for retail — OpenBIOS exports no DeliverEvent
anchor, so its kernel calls are structurally LLE either way — and on retail the
tier turned out not to mask anything (`-94.2%` with it on, `-93.9%` off).
Numbers below are the rebased base (`ed55299b` + `3cbe6c1c`).

| Per frame | OpenBIOS OFF | OpenBIOS ON | retail OFF | retail ON |
|---|---|---|---|---|
| kernel-bless mismatch | 21 | **0** | 74 | **0** |
| kernel-bless clean | 264 | 273 | 254 | 278 |
| interp insns, kernel bodies | 546.1 | **67.5** (-87.6%) | 3456.2 | **76.9** (-97.8%) |
| interp insns, A0/B0/C0 vectors | 466.1 | 462.8 | 0 | 0 |
| interp insns, all | 1486.1 | **851.1** (-42.7%) | 4446.4 | **271.1** (-93.9%) |

The exception handler body no longer appears in the interpreted list at all.
The residual kernel-body work is exactly *declared words x entries* on every
range — `0x27B4` 620,916 / 51,743 = 12.0, `0x357C` 56,400 / 18,800 = 3.0,
retail `0x0C88` 604,020 / 50,335 = 12.0, `0x4964` 112,145 / 10,195 = 11.0,
`0x4D98` 7,648 / 1,912 = 4.0 — so nothing leaks past the hook and only the
guest's own patched instructions interpret (Rule 18).

Retail gains more than the plan predicted, because the declared `0x4964` range
sits inside the pad-driver body `0x4498..0x49BC`, and blessing that one body
retired ~24 M interpreted instructions per run that were never attributed to
the exception handler at all (`0x45C4`, `0x45FC`, `0x48FC`, `0x4614`, `0x4728`,
`0x4664`).

The A0/B0/C0 vector trampolines are unchanged, as intended: the profile
excludes them by design and they remain the separate job (plan step 5). On
OpenBIOS they are now **87% of what kernel RAM still interprets**, so they are
the next lever if this ever needs one.

### Correctness

Two of the declared ranges replace the kernel's card handler with a `jr` into
the boot EXE, so the card path carries the most risk. Card read traces are
**byte-identical across the A/B on both images** — all 32 entries, every field
(command, sector, checksum, data index, resident function, store PC, data
peek), with cycle counts within 0.0001%. Both images boot healthy to 11 k
frames on both sides.

### Second title (Mega Man X6)

The fix boots MMX6 clean to gameplay on the same framework tree, with the same
key-drop behaviour: OpenBIOS 1 key dropped (3992 -> 3990 dispatch entries),
retail 5 dropped (13018 -> 13012). The **after** totals match this repo's
exactly (3990 / 13012) and so do the drop counts, which is the meaningful
agreement: same emitter, same profiles, same output on two unrelated titles.

The **before** totals differ by exactly one entry per image (MMX6 3992/13018
vs 3991/13017 here), so MMX6's retail run reports "5 dropped, 6 entries lost".
That is a baseline difference, not a missed key: retail has exactly five keys
inside declared ranges, verified by scanning the emitted dispatch table, and
the only emitter change in the six upstream commits between the two bases is a
one-word comment edit. The likely cause is that MMX6's before-build already
carried these install-slot TOMLs while its emitter was not yet range-aware, so
the old code read `ram_addr` alone and registered a legacy `+0x10`
continuation per declared slot (note retail `0x4964 + 0x10 = 0x4974`, one of
the five). Regenerating both trees on the rebased base settles it.

**A true MMX6 before/after is still outstanding** — its first build was
alpha-261 plus part of this change, so it has no clean baseline yet. "It works
elsewhere" is established; "it buys the same elsewhere" is not.

### Not declared

- Retail RAM `0x0500`, one word of `kernel_trampoline_0` cleared to zero. What
  writes it is still unidentified, and a range declared on a guess tells the
  verifier to stop checking a word it should check. Undeclared costs
  performance in one body; declared wrongly costs correctness everywhere
  (Rule 14).
- The three OpenBIOS pad-table words after `readPadHighLevel` — data, not
  instructions, so they unbless nothing.
