# The A0/B0/C0 call vectors interpret on OpenBIOS because the native stub guard knows one shape

**Status:** FIXED, MEASURED HEADLESS 2026-09-17 — psxrecomp fork branch
`feat/openbios-vector-stub-shape` (`8b50cd09`, one commit off upstream
`master` `193a60b8`), **open as [#381](https://github.com/RetroPortingToolKit/psxrecomp/pull/381)**; the
checkout here sits on `integration/vector-stub-plus-367` `b30cdcf5` (= the
PR + #367, the content that was built and measured). The
vector line reads **0.0 per frame on OpenBIOS** (was 459) and retail is
unchanged; see *Result* at the bottom. Left: a real walk on `build-relprof`
(`tools/interp_rate.py`) and the pin bump once #381 merges. Evidence: the live RAM dump
below (headless relprof boot, frame 1904),
`analysis/kernel_patch_ab_openbios{,_vecfix}.json`,
`analysis/kernel_patch_ab_scph1001{,_vecfix}.json`,
`analysis/observed_interp_pcs.json`, and the emitter source cited inline.

This is plan step 5 of [`upstream-kernel-bless-plan.md`](upstream-kernel-bless-plan.md)
and *Next up 1b* in [`STATUS.md`](STATUS.md). The plan offered two routes
("model them as a Step-2 range whose ROM source is the copy loop's constant,
or leave them"). Neither is needed: the framework already has a native path
for these vectors and it is simply not recognising OpenBIOS's bytes.

## The finding in one paragraph

Every kernel call from the game goes through a 16-byte stub the BIOS writes
into RAM at `0xA0`/`0xB0`/`0xC0` at boot. The generated dispatch trampoline
already carries `psx_bios_try_native_call_stub`, which reads the four live
words at the vector, and if they match the expected shape decodes the
target and tail-transfers straight to the kernel handler — no interpreter.
That guard is written for the **retail** stub (`lui t0,0; addiu t0,t0,X;
jr t0; nop`). **OpenBIOS writes a different stub** (`addiu t0,$zero,X;
jr t0; nop; nop`), so the guard fails closed and every call drops to the
dirty-RAM interpreter for two instructions plus an interpreter entry and
exit. That is the whole "vector trampoline" residual, and it is why the
same A/B reads 0 vector instructions on retail and ~463 per frame on
OpenBIOS ([`kernel-patch-sites.md`](kernel-patch-sites.md) → *Result*).

## Evidence

### The live bytes (headless relprof boot, OpenBIOS, frame 1904)

| RAM | Words | Decoded |
|---|---|---|
| `0x80` | `3C1A0000 275A27AC 03400008 00000000` | `lui k0,0; addiu k0,k0,0x27AC; jr k0; nop` — exception vector → `exceptionHandler` |
| `0xA0` | `24082A80 01000008 00000000 00000000` | `addiu t0,$zero,0x2A80; jr t0; nop; nop` |
| `0xB0` | `24082AA0 01000008 00000000 00000000` | `addiu t0,$zero,0x2AA0; jr t0; nop; nop` |
| `0xC0` | `24082AC0 01000008 00000000 00000000` | `addiu t0,$zero,0x2AC0; jr t0; nop; nop` |

The ROM source is `openbios.bin` offsets `0x6960`/`0x6970`/`0x6980`, copied
verbatim. Retail SCPH-1001 v2.2 copies ROM `0x10000..0x10040` instead:

| Retail ROM | Words | Decoded |
|---|---|---|
| `0x10010` (→ `0xA0`) | `3C080000 250805C4 01000008 00000000` | `lui t0,0; addiu t0,t0,0x5C4; jr t0; nop` |
| `0x10020` (→ `0xB0`) | `3C080000 250805E0 01000008 00000000` | `lui t0,0; addiu t0,t0,0x5E0; jr t0; nop` |

### The guard

`psxrecomp/recompiler/src/full_function_emitter.cpp` (emit of
`psx_bios_try_native_call_stub`, ~line 2079) requires

```
(w0 & 0xFFFF0000) == 0x3C080000   /* lui t0 */
(w1 & 0xFFFF0000) == 0x25080000   /* addiu t0,t0 */
w2 == 0x01000008                  /* jr t0 */
w3 == 0
```

and computes `t0 = (w0 & 0xFFFF) << 16 + sext16(w1)`. The OpenBIOS word 0
is `0x2408xxxx` (`addiu t0,$zero`), so the first test fails.

### Where the calls come from, and how many

The dirty-interp per-PC rows carry the external return address. On this
title all `0xB0` entries return to `0x8014B794`, inside `func_8014B770`,
which calls the Psy-Q thunk `ChangeTh` at `0x8017F734`
(`li t2,0xB0; jr t2; li t1,0x10` — B0:10h). It is the game's scheduler
yield: ~229 calls per frame in the field, ~1,300 per frame on the title
screen. Cumulative over every harvested session:

| PC | entries | interp insns | per entry |
|---|---:|---:|---:|
| `0xB0` | 90,091,821 | 180,183,644 | 2.0 |
| `0xA0` | 3,523,944 | 7,101,736 | 2.0 |
| `0xC0` | 33 | 66 | 2.0 |

The A/B harness reads the same thing per frame: 463 interpreted vector
instructions on OpenBIOS with the kernel ranges on, 0 on retail.

## The fix

Extend the emitted guard to accept the second shape:

```
shape A (retail):   w0 = lui t0,hi      w1 = addiu t0,t0,lo   w2 = jr t0   w3 = nop
shape B (OpenBIOS): w0 = addiu t0,$0,lo w1 = jr t0            w2 = nop     w3 = nop
```

Shape B's target is `sext16(w0 & 0xFFFF)`. Cycle accounting charges the
instructions the guest would execute: three for shape B (`addiu`, `jr`,
delay-slot `nop`), four for shape A. Everything else is unchanged: the words
are read from live RAM at every call, the target is decoded from them, and
any word that differs from either shape still fails closed to the
dirty-RAM interpreter. Rule 18 holds — the guest's own instructions decide
where control goes; nothing is synthesised.

This is a framework generalisation, not a title shim: any title on OpenBIOS
pays the same cost today. It lands as a psxrecomp PR; the title bumps the
pin afterwards.

## What it should buy, and what it will not

- The `interp insns, A0/B0/C0 vectors` line of
  `psxrecomp/tools/kernel_patch_ab.py` should read ~0 on OpenBIOS, as it
  already does on retail.
- `tools/interp_rate.py` on a long field walk should drop from 290–390
  per frame to roughly the declared-patch-range floor (`0x27B4` × entries,
  ~60–80) plus the boot-EXE stub run battle transitions dirty.
- Wall-clock: unknown and probably small. The cost per call is one
  interpreter entry and exit, and most calls are a cooperative-scheduler
  yield. The A/B reports `wall_s`; read it, do not assume fps moves.

## Open question carried from `kernel-patch-sites.md`

That note explains the Mega Man X6 result ("the B0 vector vanishes once the
bless verdict is clean, because the vector body dispatches native"). No
compiled body exists at `0xB0` and the guard above rejects OpenBIOS's bytes
regardless of bless state, so that explanation cannot be right as written.
Re-measure MMX6 on this fix rather than carrying the claim forward.

## Measure

```bash
# headless, one binary per side: rebuild build-relprof before and after the pin bump
python psxrecomp/tools/kernel_patch_ab.py
# a real walk on build-relprof, same route before and after
python tools/interp_rate.py --since 2026-09-17
```

## Result (headless, 11k frames, `PSX_BIOS_HLE=0`, ranges ON side)

`build-relprof` rebuilt on the branch; both BIOS backends regenerated with
unchanged dispatch totals (OpenBIOS 3990, SCPH1001 13012) and the same
dropped-continuation counts as the pin (20 / 36).

| Per frame | OpenBIOS before (2026-09-11) | OpenBIOS after | retail before | retail after |
|---|---:|---:|---:|---:|
| kernel-bless mismatch | 0 | 0 | 0 | 0 |
| interp insns, A0/B0/C0 vectors | 459.2 | **0.0** | 0.0 | 0.0 |
| interp insns, kernel bodies | 67.3 | 64.1 | 76.9 | 75.7 |
| interp insns, all | 844.9 | **143.7** (−83 %) | 274.4 | 259.2 |

Both images boot to 11k+ frames on both sides with no stall; the residual
kernel work is still exactly the declared patch ranges (`0x27B4`, `0x281C`,
`0x357C` on OpenBIOS). Retail is unchanged within noise, as it should be:
its stub already matched shape A.

**Wall clock is inconclusive from these runs.** The headless OpenBIOS run
went from 37.4 s to 27.4 s for 11k frames, but the retail run, which this
change does not touch, went from 34.3 s to 27.3 s on the same day, so the
difference is the machine and the intervening pin bump, not the vectors. A
wall-clock claim needs the same day, same tree, and the guard toggled; the
guard has no runtime toggle, so the honest statement is "the interpreter
entries are gone, the frame time was not measured".

The "kernel bodies" figure moved 67.3 → 64.1 without any change to the
bodies; that is run-to-run variation in how many frames the boot spends on
the card screen, not an effect.
