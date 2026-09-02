# Capcom FMV slowdown — root cause, fix, and the two wrong theses

**Status:** RESOLVED (2026-09-01) — fixed upstream in
[mstan/psxrecomp#292](https://github.com/mstan/psxrecomp/pull/292), user-verified
at 60 fps with clean audio on `build-relprof`. Filename kept for link stability;
the title it originally carried ("VBlank cadence is throttled to the presented
frame rate") was the first of two wrong diagnoses, recorded below.

## The bug

The Capcom gold-cubes logo — an MDEC FMV streamed from `CAPCOM30.STR`, the first
screen after boot — ran at a rock-steady ~28 fps with audio pops. The rate did
not move with renderer (HW vs SW), disc speed, PGXP, windowed vs `PSX_VSYNC=0`
vs `--headless`. The crackle was downstream: the SPU/audio pump is
(correctly) synchronous with the VBlank edge, so a guest running at half speed
starves the host audio device.

## Root cause

Host-side stack sampling (`gdb`, `thread apply 1 bt`, clean boot, live FMV)
found the emu thread spending **~40% of its time in `spu_get_global_state()`** —
a memset, ~40 register reads and three 24-voice loops building a full
`SpuGlobalState` snapshot — called from both `psx_spu_sample_event_service()`
(every `advance_devices()` chunk) and `psx_spu_sample_event_cycles_to_next()`
(every deadline recompute), each time **just to read one bit** (`ctrl & 0x40`,
SPU IRQ9 enable). The FMV's LOGO overlay runs a *native* MMIO-polling wait loop
whose every tiny basic block flushes cycles → services devices → recomputes the
deadline, so the snapshot ran at enormous frequency. Every screen pays this
gate; the FMV paid it loudest.

## The fix

`runtime/src/spu.c` + `include/spu.h` + `src/interrupts.c`: a cheap accessor
`spu_ctrl_read()` (one array load) used by both hot gates. Same register, same
bit, identical semantics. Upstream as #292 (`8eb29d25` on `mstan/master`).

| build | FMV vblank/s (clean boot, headless, uncapped) |
|---|---:|
| Debug, pre-fix | ~28.5 |
| Debug, post-fix | ~49–52 (the remaining gap is -O0 tax) |
| RelWithDebInfo, post-fix | **~97.6** (~1.6× realtime → holds 60 with ~40% headroom) |

After the fix the host profile is diffuse: device catch-up walk
(cdrom/dma/timers ~14/25 samples), per-instruction cycle accounting (~10/25),
real MDEC SSE2 decode (~2/25), debug rings (~3/25). No single hotspot.

**User-verified 2026-09-01 (windowed, by eye and ear):** Capcom logo, world map
and memcard screens all hold 60 fps with clean audio on `build-relprof`
(`-DPSX_STATIC_RUNTIME=ON` — see [`STATUS.md`](STATUS.md) → Build trees). On
`build-dbg` (-O0) the same screens read ~50/60/55; that tree cannot hold 60 on
the FMV and is not evidence of a regression.

## Reproduce / verify

```bash
python tools/fmv_bench.py [--exe build-relprof/BreathOfFire3_Recompiled.exe] [--window 4] [--gdb N]
```

Launches a clean boot headless, catches the FMV via `mdec_state.trace_total`,
measures an unperturbed vblank/present window, then optionally gdb-samples the
emu thread (after the rate window; attaching pauses the process). Debug-server
probes that matter: `vblank_rate`, `frame`, `audio_stats`, `mdec_state`,
`phase_profile`, `dirty_ram_stats`. The formal close is the Beetle oracle
(`psx-beetle.exe`, port 4380, same protocol) reading ~60 on the same content —
not yet run; the user-verified windowed result stands as the acceptance.

**Traps:** profile the FMV on a **clean boot only** — the mid-FMV savestates
(`PSX_LOAD_SLOT=6`) resume *past* the FMV. The BIOS VSync counter at
`0x8018603C` is frozen during the intro; use the host `frame` counter. Run the
exe from PowerShell with `$env:` (Git Bash env prefixes do not reliably reach
the native child).

## The two wrong theses, and why they fell

Kept so they are not re-derived. Both had real measurements; both profiled the
wrong layer.

### Thesis 1 — "VBlank is paced to the presented frame rate" (wrong)

The claim: on a 30-fps-content screen the runtime raised VBlank at the
*presented* rate with the CPU idle, so emulated time advanced at half speed and
the VBlank-tied audio pump starved. Refuted by direct measurement: the symptom
was identical windowed, with `PSX_VSYNC=0`, and `--headless` (no present at
all), and the process pegged **~98–100% of one core** during the FMV, jumping
to 94–150 Hz headless the moment MDEC went idle. It was saturation, not a cap.
The "CPU idle" premise had been assumed, never measured. Decoupling VBlank from
present would not have helped.

### Thesis 2 — "the interpreted BIOS IRQ handler" (wrong)

The claim: kernel RAM is install-at-runtime (Rule 18) so the boot-relocated
exception handler at `0x27AC` → I_STAT dispatch → B0 trampoline
(`0x000000B0`) → handler → restore ran interpreted on every interrupt, and the
FMV's IRQ storm (VBlank + CD sector + DMA) made that the cost. Guest-side
counters looked supportive (`phase_profile` interp 46–49%, hot interp PCs in
`0x2914`–`0x2968` and `0xB0`). Refuted on a clean boot: global interp counters
during the FMV were **~10K insns/s in ~1.1K blocks/s** — ~25 instructions per
IRQ, trivial — and `phase_profile`'s "interp" share was a **mislabel** (static
overlay code entered from the dirty dispatcher runs with the interp phase flag
still set). An earlier sub-thesis fingered the IntRP 4-queue walk at `0x2914`;
that path is only reached on `ExcCode != 0` (syscalls, during FMV *startup*)
and takes **0 hits** in steady playback.

Two durable findings from that detour:

- **OpenBIOS rebuilds the exception handler in RAM at boot.** The RAM image
  matches the ROM source (`openbios.bin` offset `0x20790`) for ~10 instructions
  then diverges at `0x27DC` (inlined call, reordered register-save block). No
  ROM-compiled BIOS function can be entered at its RAM-relocated address, so
  "native handoff for relocated kernel code by ROM byte-match" is dead. The
  static dispatch table has no kernel-RAM entries and the `overlay_loader`
  runtime cache is inert here (`active:0, registered:0`).
- **Prototype lessons (walk-HLE, `PSX_HLE_INTRP_WALK=1`, `d725af45` on fork
  branch `fix/vblank-cadence-pacing`, not upstream, not needed).** Calling a
  guest callback from a native hook via `psx_dispatch_call` needs (1)
  `g_precise_mode` / `g_dirty_interp_active` cleared around the call — in
  precise mode the callee's `jr ra` surfaces instead of returning — and (2)
  `cpu->gpr[31]` (ra) set before the call, as the real `jalr` would. With those
  the native walk fired cleanly (`bails=0`, 200–2000 walks/s post-FMV). Reuse
  the pattern if a faithful HLE is ever the right shape.

## Pointers

| Where | What |
|---|---|
| `psxrecomp/runtime/src/spu.c`, `include/spu.h` | `spu_ctrl_read()`, the fix |
| `psxrecomp/runtime/src/interrupts.c` | `fire_vblank_edge`, `s_midframe_audio_pump`, `psx_spu_sample_event_service` / `_cycles_to_next` call sites |
| `psxrecomp/runtime/src/debug_server.c` | `vblank_rate`, `audio_stats`, `audio_wav`, `mdec_state`, `frame` handlers |
| `tools/fmv_bench.py` | The repro/verify harness |
