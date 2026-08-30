# Bringup — boot / soak log

**Status:** IN PROGRESS (last verified 2026-08-30)

What runs, where it stops, what was fixed. One entry per boot attempt that
taught us something. Companion to [`STATUS.md`](STATUS.md), which stays short.

## Boot 001 — 2026-08-29 — first boot, headless

> **SUPERSEDED IN PART by Boot 002 (2026-08-30).** The "parks in a wait
> loop" conclusion below is **wrong**. The two pinned `store_pc` values are
> `DrawOTag()` and `VSync()` — i.e. a healthy render loop, not a stall. The
> CD-ROM hypothesis is dead. The run genuinely reached the title screen; the
> Release build simply has `PSX_DEBUG_TOOLS=OFF`, so there was no way to see
> it. Everything else in this entry (generate stats, IRQ health, addresses)
> still holds.

**Result: the game boots and executes its own code without crashing, then
parks in a wait loop. Nothing died.**

### How it was produced

```bash
export PATH=/c/msys64/mingw64/bin:$PATH
./psxrecomp/tools/ci/build_emitters.sh --jobs 12
python -u psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . \
  --disc "isos/Breath of Fire III (Japan).cue"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
cd build-release && timeout --signal=KILL 90 \
  ./BreathOfFire3_Recompiled.exe --headless --no-launcher
```

All four stages exit 0. Evidence for everything below is that run's stdout plus
`build-release/psx_freeze_heartbeat.json` written by it.

### Generate

| Stage | Result |
|---|---|
| Disc verification | passed against `[prepare_disc]` md5/sha1/size |
| OpenBIOS emit | 651 emitted, 0 interpreted, **4 skipped**, 3989 dispatch entries |
| Game emit | 2,521,937 lines / 35 shards, **0 skipped, 0 unsupported** |
| Dispatch table | **1467 entries** (from 523 first-pass seeds, grown by closure discovery) |

The game side emitted **completely clean under `strict = true`** — no skipped
functions, no unsupported instructions. BoF3's boot EXE is fully inside the
Phase-1a translator's coverage. This was not assumed; strict mode would have
aborted otherwise.

Three benign notes, all "out-of-function branch/jump, emitting fallthrough":
`func_801546FC` to `func_80154720`, `func_80163348` to `func_80163354`,
`func_8017917C` to `func_80179190`. Not yet investigated; they are adjacent
fallthroughs, consistent with discovery splitting one real function into two.
Worth confirming before trusting those three.

The 4 skipped functions and the "cross-function target" warning spam are
**OpenBIOS, i.e. framework territory**, not this title — see *Framework
observations* below.

### Runtime boot

Executes from `PC=0xBFC00000`, with:

```
bios_backend=LLE (recompiled BIOS)  bios_boot=HLE (shell skipped)  image=OPENBIOS
thread scheduler = HLE (deterministic TCB)
text image guard armed (0x80093800..0x801F7000, local EXE)
```

The disc resolved correctly — the `no disc image selected; exiting` path in
`psxrecomp/runtime/src/main.cpp:12719` never fired, so the repo-relative
`isos/...cue` in `game.toml` resolves fine even with the exe running from
`build-release/`.

### Where it parks — the actual finding

After ~26,000 frames in 90 s wall (no crash, `fatal: null`,
`automatic_freeze_dumps: 0`), the heartbeat shows:

| Signal | Value | Reading |
|---|---|---|
| `frame_count` | 26,081+ | Running fast, not stalled |
| `vblank_raise/deliver/ack` | 23059 / 22701 / 22703 | **IRQ path is healthy** — raised, delivered, acked |
| `epc` | `0x8017E328` | **Inside game text** (0x80093800..0x801F7000) |
| `sp` / `gp` / `ra` | `0x801FFF90` / `0x8018BC2C` / `0x8017E23C` | Game stack live at the configured `stack_base` |
| `ring[].store_pc` | pinned to `0x8017DDA0` and `0x801751F4` | **The loop** |
| `dispatch_count` | 0 | Direct calls; dispatch table not needed yet |
| `exception_entries` | 81,073 | Exactly equals `irq_deliver_count` — all IRQ, no faults |

So this is **not** a BIOS hang. The game EXE is running its own code on its own
stack, servicing vblank normally, and spinning on a condition that never becomes
true. The pinned PCs land in:

| PC | Enclosing emitted function | Shard |
|---|---|---|
| `0x8017DDA0` | `func_8017DD60` | `SLPS_009.90_full_18.c` |
| `0x801751F4` | `func_801751C0` | `SLPS_009.90_full_15.c` |
| `0x8017E328` (epc) | `func_8017E0E0` | `SLPS_009.90_full_18.c` |

`func_8017E0E0` (1952 lines emitted) appears to be the caller — it holds `ra`
and `epc`, and both spin targets are reached from it.

**Leading hypothesis, not yet established:** the game is waiting on CD-ROM —
it has issued a read for its first overlay / data file and the completion never
arrives, so it loops. This fits the shape (healthy vblank, live stack, no
faults, pinned store PC) and fits the framework's expectation that overlay
bringup follows a clean first emit. It is **not yet evidenced**: nobody has
confirmed these functions touch `0x1F801800`-range CD registers or traced a CD
command. Establish that before acting on it.

`mc_max_state: 18` with `tx_writes: 156858` also shows heavy SIO traffic
(controller / memcard polling), an alternative candidate to rule in or out at
the same time.

### Next actions

1. Read `func_8017E0E0`, `func_8017DD60`, `func_801751C0` in the generated C
   and identify the loop condition and which MMIO it polls.
2. Confirm or kill the CD-ROM hypothesis with a device trace
   (`psxrecomp/runtime/src/device_trace.c`, `cdrom.c`) rather than by inference.
3. Label whatever these turn out to be in `symbols.toml` (`emit = false` until
   proven) and re-run `tools/sync_symbols.py`.
4. Only then consider overlay work — see `psxrecomp/docs/overlay-discovery.md`.

## Boot 002 — 2026-08-30 — the game loads

**Result: title screen renders, input is accepted, the opening prologue plays.
Boot 001 was never hung.**

### The tooling gap that hid it

Boot 001 could only reason from `psx_freeze_heartbeat.json` because the Release
build strips every inspection path:

```
build-release/build.ninja:  ... -DPSX_NO_DEBUG_TOOLS=1 ...
```

`psxrecomp/runtime/runtime.cmake:60` defaults `PSX_DEBUG_TOOLS` **OFF** for
Release, and `main.cpp:13084` guards `debug_server_init(debug_port)` behind
`#ifndef PSX_NO_DEBUG_TOOLS`. So the TCP debug server never listened, and
`--debug-port` was silently inert. Fixed by building a second tree:

```bash
export PATH=/c/msys64/mingw64/bin:$PATH
cmake -S . -B build-dbg -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON
cmake --build build-dbg --target psx-runtime          # 232/232
```

`build-release/` is left alone; `build-dbg/` is the diagnosis tree.

### Reading the Boot 001 "wait loop"

`tools/disasm_exe.py` (added this session) disassembles the staged boot EXE, so
the loop could be read instead of guessed:

```bash
python tools/disasm_exe.py 8017DD60:19 801751C0:39
```

**`func_8017DD60` is `DrawOTag()`.** It writes four globals that the EXE image
initialises to GPU/DMA registers:

| Global | Initial value | Register |
|---|---|---|
| `0x8018BBA8` | `0x1F801814` | GP1 |
| `0x8018BBAC` | `0x1F8010A0` | D2_MADR |
| `0x8018BBB0` | `0x1F8010A4` | D2_BCR |
| `0x8018BBB4` | `0x1F8010A8` | D2_CHCR |

It stores `GP1(04)=2` (DMA direction CPU→GPU), `MADR=a0`, `BCR=0`, then
`CHCR=0x01000401` — SyncMode 2, from RAM, start. That is the canonical libgpu
linked-list DMA kick.

**`func_801751C0` is `VSync()`.** Its timeout branch loads `0x8014A0DC`, which
is the string `VSync: timeout`. It spins until the libetc counter at
`0x8018603C` reaches `a0`, decrementing an `a1<<15` timeout.

So `store_pc` pinned to `DrawOTag` + `VSync` is what a **healthy game loop**
looks like. There was no CD-ROM wait to diagnose.

### What the GPU was actually doing

`gpu_state` over the debug server, mid-run:

| Signal | Value | Reading |
|---|---|---|
| `gp0_draw` | 1,198,959 | Draw commands executing |
| `gp0_writes` | 25,464,573 | GP0 firehose is live |
| `disabled` | 0 | Display enabled |
| `draw_offset` | `[0, 240]` | Double-buffered, drawing lower half |
| `last_world3d_frame` | 11,629 | 3D geometry being submitted |

### Pixels

`--headless` with `renderer = opengl` screenshots **black** — there is no GL
context to read back. With the software rasteriser the frames are correct:

```bash
./BreathOfFire3_Recompiled.exe --headless --no-launcher     --renderer software --debug-port 4370
```

| Capture | Result |
|---|---|
| `shot_sw_later.png` | Title screen — logo, `PRESS START BUTTON`, Capcom 1997 notice |
| `shot_after_start.png` | Opening prologue, Japanese text rendering correctly |

`press` with `buttons=0x0008` (Start, PSX pad bit 3) advances the title; on the
press `display_y` begins alternating `0`/`240`, i.e. the buffer flip engages.

Screenshots live in the gitignored `build-dbg/` and are deliberately not
committed.

### Standing caveats

- Headless is unthrottled: ~26k frames in 90 s wall. `vblank_raise_count`
  equals `frame_count` exactly (45,723 each), so the *guest* pacing is right —
  it is only wall-clock that runs fast. Not a bug; do not "fix" it.
- `gpu` is not a debug command; the real one is **`gpu_state`**.

### Next actions

1. Soak from the prologue into gameplay and log where it stops next.
2. Text-draw PC census — see [`LOCALIZATION.md`](LOCALIZATION.md).
3. Grow `seeds/ghidra_funcs.txt` as overlay paths surface.

## Framework observations

Two issues that belong **upstream in `mstan/psxrecomp`**, recorded here so they
are not re-diagnosed. Neither is patched locally; the submodules stay untouched
per `CLAUDE.md`.

### F-1. CMake always reports the BIOS as STALE after a CLI generate

Configure prints:

```
CMake Warning at psxrecomp/runtime/runtime.cmake:715 (message):
  BIOS generated/ is STALE vs the recompiler emitter (fingerprint mismatch).
```

**This is a false positive.** Mechanism:

- The check at `psxrecomp/runtime/runtime.cmake:715` compares a freshly
  computed fingerprint against the stamp file
  `psxrecomp/generated/OpenBIOS.emitter.sha`.
- That stamp is written **only** by `psxrecomp/tools/regen_bios.sh:158`.
- But `psxrecomp_cli.py generate` regenerates the BIOS by invoking
  `psxrecomp-bios.exe` directly — `regen_bios_profile()` at
  `psxrecomp/psxrecomp_cli.py:800` — and never writes the stamp.

Verified: `psxrecomp/generated/` contains only `OpenBIOS_full.c`,
`OpenBIOS_dispatch.c`, and `OpenBIOS_skipped_functions.json` — no
`.emitter.sha`. The comparison is therefore against an empty string and can
never match. Our BIOS was in fact regenerated at 23:47 by the emitter built
minutes earlier.

Consequence: **every title using the documented CLI generate path sees this
warning permanently**, training a deliberately "impossible to miss" staleness
signal into noise. The fix belongs in `regen_bios_profile()` (write the stamp)
or in the check (treat a missing stamp as unknown rather than stale).

### F-2. OpenBIOS discovery emits garbage cross-function targets

Generate logs ~25 warnings of the form:

```
psxrecomp-bios: WARNING: cross-function target 0xAC850000 (parent guess 0x00004810)
  is in no emitted function — dispatching it at runtime will fail
```

The reported "targets" (`0xAC850000`, `0xAC850004`, `0xAC850008`, ... ascending
by 4, plus `0x2508FFFF`, `0x24840001`) are **raw MIPS instruction encodings, not
addresses** — `0xAC85xxxx` is `sw $a1, xxxx($a0)`. Discovery is walking a store
sequence as if it were branch targets, with a non-address "parent guess" of
`0x00004810`. Cosmetic for us (BoF3 boots), but real misparsing in the
framework's BIOS function discovery.

Separately, 4 OpenBIOS functions are genuinely skipped on unimplemented opcodes
— `0x2F` (`CACHE`) at `0xBFC22674`, `0xBFC227D4`, `0xBFC227E4`, and
`SPECIAL funct 0x3C` at `0xBFC095F8`. Harmless unless a boot path reaches them.

## Environment note

`BreathOfFire3_Recompiled.exe --help` is **not** a supported flag — the runtime
ignores unknown args and launches normally, so `--help` opens a window and
blocks. The real flags are parsed at `psxrecomp/runtime/src/main.cpp:10765`:
`--bios --game --disc --debug-port --memcard-dir --renderer --window-title
--launcher --no-launcher --headless --netplay --net-*`.

`--headless` (`main.cpp:10790`) implies `--no-launcher`, opens no SDL window or
audio device, and — important for unattended runs — suppresses the blocking
`MessageBoxA` modals (`main.cpp:2150`). It is the right frontend for soak.
