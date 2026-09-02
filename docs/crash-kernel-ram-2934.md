# Crash — unknown native dispatch into kernel RAM (`0x00002934`)

**Status:** STALE (last verified 2026-09-01) — single observation, **not
reproducible** on the same savestate slot. Kept as evidence in case it recurs.
Add a new occurrence to the table below rather than rewriting this.

## One-line

While resuming savestate **slot 7**, a native call site did `jalr` through a
function pointer into **kernel RAM** (`0x00002934`) that had no registered
native dispatch target, and the recompiler fail-fasted instead of falling to
the interpreter. Same run, same slot did **not** reproduce it → treated as a
transient IRQ-boundary routing race, not a fixed discovery gap.

## The fail-fast line (primary evidence — from console, authoritative)

```
savestate: LOADED slot 7 -> resuming pc=0x80175234 (boot=8.5 frontend=2.3 poll_total=10.8 ms)
FATAL: FAIL-FAST unknown dispatch: addr=0x00002934 phys=0x00002934
       ra=0x801A36BC a0=0x80146990 a1=0x00000000  -- see psx_last_run_report.json
```

- `addr = 0x00002934` — **kernel-in-RAM** (the 0x0000–0xFFFF region the BIOS
  copies down at boot: exception/event handlers, A/B/C jump tables). **Not**
  BIOS ROM (0xBFC00000), so the crash hint "if addr is BIOS ROM, seed it" does
  not apply.
- `ra = 0x801A36BC` — the caller, in the field/IRQ-dispatch band.
- `a0 = 0x80146990`, `a1 = 0x00000000` — callback args.

## Why it is kernel RAM, not a missing seed

- `0x00002934` is present in `generated/overlays_static.c` **only as a data
  word** inside a captured pointer/jump table (~line 8498603), i.e. a kernel
  callback address stored in game data — *not* a registered dispatch key.
- The runtime dispatches into this region constantly and fine. From the same
  run's `dispatch_tail` (19,064,537 dispatches, top targets): `0x00003D9C`
  (71), `0x00003B60` (70), `0x000000B0` (8), `0x00002AA0` (8), `0x000026E4`
  (5), `0x00004428` (4). Its immediate neighbors interpret without complaint.
- So the interpreter **can** run `0x00002934`; the crash is that one *native*
  dispatch site reached it and had no target, rather than a corrupted/missing
  function.

## Why savestate-flavored / why it is a race, not a fixed gap

- Snapshot was taken inside interrupt/event dispatch: `cause = 0x00000400`
  (IP2 pending), `sr = 0x40020401`, `k0 = 0x8014B70C`, resume
  `pc = 0x80175234`.
- Whether the resumed kernel callback is re-entered via the **native** path
  (fail-fasts on an unknown target) or the **interpreter** path (runs kernel
  RAM happily) depends on where the emu pump / IRQ boundary falls that run —
  same class as `psx_irq_resume_context_snapshot_safe()`
  (`interrupts.c:629`, see HANDOFF).
- **Reloading the identical slot did not reproduce it.** The RAM image and
  installed handler pointer are identical on every load of a slot, so a fixed
  unregistered callback would fail every time. It didn't → the target set is
  not fixed by the state alone; it's the resume landing.

## Environment

- Build `v0.3.2-alpha-126-gecc0de16` (Sep 1 2026 00:11:33), all-ten-bands
  overlay config, `build-dbg`.
- The `psx_last_run_report.json` on disk at capture time reads
  `reason: atexit / exit_origin: sdl_window_close` — that is the *later* clean
  window-close, not the fail-fast. Its ring buffers still hold the crash-moment
  context (resume region ~0x80175xxx, kernel-RAM dispatch active). Treat the
  console fail-fast line above as authoritative; the report corroborates.

## The fix, only if it recurs (framework-side, not a per-game shim)

Kernel-RAM indirect targets (`addr < 0x10000`) with no registered native
handler should **fall through to the interpreter** instead of fail-fasting —
that region is already interpreted everywhere else (see the `dispatch_tail`
neighbors above). That is an upstream `psxrecomp` change (the title pins plain
`mstan/master` as of 2026-09-01). Only worth doing with a live repro in hand; a
one-off does not justify touching the fail-fast contract.

Slot numbering: the console's "slot 7" is the *file* number (`slot07.pst` =
in-game slot 8, the world-map anchor — see [`SAVESTATES.md`](SAVESTATES.md)).

## Occurrence log

| Date | Slot | resume pc | addr | ra | a0 | Reproduced same slot? |
|---|---|---|---|---|---|---|
| 2026-09-01 | 7 | 0x80175234 | 0x00002934 | 0x801A36BC | 0x80146990 | No |
