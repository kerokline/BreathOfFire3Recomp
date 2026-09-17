# The decompressor's copy loop interprets: a computed-stride jump into an unrolled run

**Status:** FIXED, MEASURED HEADLESS 2026-09-17 — `resolve_computed_stride_jump`
in the psxrecomp game emitter, fork branch `feat/computed-stride-jump`
(`67c79e8f` + `ee4db282`, off upstream `master` `193a60b8`), **open as
[#382](https://github.com/RetroPortingToolKit/psxrecomp/pull/382)**. The copy loop's interpreted work over twenty headless area loads
went **684,626 → 0** with every other row unchanged; see *Result* at the
bottom. The checkout here sits on `integration/vector-stub-plus-367`
`88f4582a` (= #367 + #381 + both commits of #382), which is what
`build-relprof` was rebuilt from (overlays recompiled, 27 audit-only shard
failures as before). Evidence: the field probe below,
`analysis/observed_interp_pcs.json` (session `20260917T142556-0160`), the
disassembly of `func_80164CE4`, and `generated/SLPS_009.90_full_10.c`.

With the call vectors native ([`vector-stub-shapes.md`](vector-stub-shapes.md))
this is the whole non-kernel residual of a play session. It is also the
reason the first post-fix walk still read 384 interpreted instructions per
frame: a field walk with no loads reads ~118 (all of it the declared kernel
patch ranges); everything above that is this loop.

## What it is

`func_80164CE4` (boot EXE, 472 bytes, unnamed) is the literal-copy path of
the file decompressor. It copies `s0` bytes from `s5` to `t3` through a
32-way unrolled body of `lbu t5,k(s5); nop; sb t5,k(t3)` groups (12 bytes
each, `0x80164D1C..0x80164E9C`), then advances the pointers and loops
(`bne s0,zero` back to `0x80164D1C`). The first, partial iteration enters
the body **in the middle**, Duff's-device style:

```
80164CEC subu  t6,t4,s2        ; t6 = 32 - remaining (clamped at 0)
...
80164D00 sll   t7,t6,3
80164D04 sll   t5,t6,2
80164D08 addu  t7,t7,t5        ; t7 = t6 * 12
80164D0C addu  t7,s3,t7        ; t7 = base + t6 * 12
80164D14 jr    t7
80164D18 subu  t3,t3,t6        ; (delay slot)
80164D1C lbu   t5,0(s5)        ; group 0 — the run starts here
80164D20 nop
80164D24 sb    t5,0(t3)
80164D28 lbu   t5,1(s5)        ; group 1
...
80164E90 lbu   t5,31(s5)       ; group 31
80164E9C addu  s5,s5,t6        ; tail: advance, loop
```

`s3` is the run base. It is not computed in this function: the decoder
keeps its state in a context block and `func_80164CBC` restores `s0..s7`
from it; the base is planted there once by the context initialiser
(`lui/ori 0x80164D1C` at `0x80164A3C..A40`, stored to `0x1C(t0)`).

## Why it interprets

The recompiler resolves `jr` through the canonical bounded jump-table chain
(`sltiu/beq; sll; addu; lw; jr`) and nothing else. This `jr t7` has no load
and no table, so `code_generator.cpp` emits the CPS fallback
`cpu->pc = t7; return;`. The trampoline then looks the interior address up
in the dispatch table, finds nothing (the run is straight-line code with no
block leaders inside it), and hands the PC to the dirty-RAM interpreter,
which runs **the rest of the copy, every iteration, every call**. The
per-PC rows show it: entries only at the seven jump targets that actually
occur (`0x80164E48/54/60/6C/78/84/90`, i.e. 0 to 6 bytes remaining), and
the instruction counts climbing along the run to the tail, which executes
once per iteration.

| PC | entries (all sessions) | insns | note |
|---|---:|---:|---|
| `0x80164E78` | 1,870,312 | 5,605,292 | target for 2 bytes left |
| `0x80164E6C` | 816,521 | 3,734,980 | 3 bytes |
| `0x80164E60` | 492,641 | 2,918,459 | 4 bytes |
| `0x80164E84` | 399,632 | 6,004,924 | 1 byte |
| `0x80164E9C` (tail) | 0 | 6,299,599 | every iteration |

`harvest_interp_pcs.py` classes these rows `bootexe` and describes that
class as "a boot EXE page written at run time". For this run that is wrong:
live RAM over `0x80164D00..0x80164EC0` matches the disc image word for word
(`analysis/bootexe_stub_ram.hex`, headless probe from the slot-5 anchor).
Nothing is written; the PC simply has no native entry.

## Measured

Headless, `build-relprof` on the vector fix, booted from the slot-5 field
anchor, per-PC counters diffed over a 3,043-frame window with no loads:

| Field only, per frame | |
|---|---:|
| all interpreted | 117.5 |
| `0x27B4` exception prologue | 88.7 |
| card stubs `0x357C` + `0x281C` | 16.4 |
| this loop | 0.0 |

The user's real walk through AREA052 with battles the same afternoon
averaged 384 per frame. The difference is this loop firing on every load:
battle transitions, area changes, the card screen.

## The fix (framework, game emitter)

Recognise the idiom next to the jump-table resolver:

```
jr R          where R = B + I * stride,
              stride = 1<<k, or (1<<a) + (1<<b) from two slls of the same I,
              and the code right after the jr's delay slot is a straight-line
              run of N ≥ 2 shape-identical groups of `stride` bytes
              (same opcodes and registers, immediates free).
```

Targets are `run_start + k * stride` for `k = 0..N` (the last one is the
word after the run, the tail). The emitter then does what it already does
for a table: registers them as interior labels and emits a `switch` on the
computed register with `goto` cases, keeping the CPS tail-transfer as
`default`. The base register's value is never assumed: the switch tests the
actual runtime target, so a jump that lands anywhere else still takes the
existing fallback. A wrong guess costs dead cases, never correctness.

This is a recompiler fix (rule: fix the translator, not the title), it is
general (any Duff's-device copy in any title, boot EXE or overlay, since the
overlay compiler uses the same code generator), and it is measurable: the
`bootexe` rows in a battle-transition harvest go to zero, and
`tools/interp_rate.py` on a walk with loads falls toward the ~118 floor.

## The sibling gap in the same decoder: a table with no bounds check

The walk after the stride fix (384 → 152 per frame) left one boot-EXE row,
`0x80164AC4`, two instructions per entry. It is the decoder's state
dispatch in `func_80164A54`:

```
80164A90 lw    t4,16(t0)          ; stored, pre-scaled byte offset
80164A94 lui   t5,0x8016
80164A98 ori   t5,t5,0x4AB0       ; table base, in-function
80164A9C addu  t5,t4,t5
80164AA0 lw    t4,0(t5)
80164AA8 jr    t4
80164AB0 .word 80164AC4 80164B38 80164BE8 80164B20 80164BD0
80164AC4 ...                      ; entry 0 is the word right after the table
```

A real in-image pointer table, but the index is read from the context
block with no `sltiu/beq` guard and no `sll`, so the canonical bounded
resolver has nothing to prove the extent with. `resolve_self_limited_jump_table`
(second commit of the same branch) takes the extent from the table's own
layout instead: words from the base while each is a 4-aligned in-function
code address outside every delay slot, ending where the lowest target
begins, since a pointer table cannot overlap the code it points at. Same
safety argument as the stride resolver: the switch tests the real runtime
target and keeps the CPS default, so an index past the recovered extent
still falls back. One match in the boot EXE (five entries), every other
shard byte-identical.

## Left

- The `harvest_interp_pcs.py` description of the `bootexe` class should
  say "outside every compiled band, no native entry at this PC" rather than
  "written at run time"; whether a page is dirty is a separate question the
  tool does not check.
- Name `func_80164CE4` / `func_80164A54` / `func_80164CBC` (decompressor
  copy, decoder, context restore) once the decoder is read properly.

## Result

The emitter now matches exactly one site in the boot EXE, this loop
(`computed-stride jump into unrolled run 0x80164D1C, stride 12, 33
entries`); every other `jr` is emitted as before, and the boot EXE output
is otherwise byte-identical. Measured with the same headless procedure on
both builds: boot from the slot-5 anchor, `tools/warp.py` through areas
10–29 (each an area load, so a decompressor run), per-PC interpreter
counters diffed across the window (`analysis/load_probe_{before,after}.json`).

| Over the warp window (~81 k frames) | before | after |
|---|---:|---:|
| copy loop `0x80164D1C..EB4`, interp insns | 684,626 | **0** |
| kernel patch ranges, interp insns | 2,727,111 | 2,629,011 |
| all interpreted, per frame | 42.8 | 32.9 |

The only rows left above a few dozen instructions are the three declared
kernel patch ranges. The `bootexe` class of a harvest should now be
empty on a battle or area transition; the next real walk with
`tools/interp_rate.py` is the play-side proof.

The warp harness reported every area as "active mode 4 never settled to
field-walk" on both runs — the slot-5 anchor no longer sits in plain
field-walk state — but the loads themselves ran (1,417 copy-loop entries
before), so the comparison stands. Re-anchor slot 5 before the next sweep.
