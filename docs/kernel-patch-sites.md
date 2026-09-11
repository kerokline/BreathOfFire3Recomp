# Kernel patch sites — why the BIOS exception handler runs interpreted

**Status:** MEASURED 2026-09-11 on both images, clean: OpenBIOS and retail
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
