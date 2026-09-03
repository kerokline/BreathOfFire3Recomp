# Savestate catalogue

**Status:** IN PROGRESS (refreshed 2026-09-01 from file timestamps and the
session notes that used each slot)

What each savestate slot holds, so a later session can jump straight to the
screen it needs instead of replaying from boot. Files are gitignored — this
document is the index, the states live only on Kevin's machine at
`saves/openbios/state_8014AA0C_slotNN.pst` (+ `.thumb`).

## The numbering is off by one

**In-game slot *N* writes the file `slotN-1`.** Established from write
timestamps on 2026-08-30 (in-game 3 and 4, nine seconds apart, landed as
`slot02` and `slot03`) and consistent for every slot since. The runtime's own
console (`savestate: LOADED slot 7`) and `PSX_LOAD_SLOT=N` use the **file**
number. Quote the file number when scripting, the in-game number when asking
the player to load one.

## Contents

| In-game | File | Written | Contents | Use |
|---|---|---|---|---|
| 1 | `slot00` | 2026-09-03 | Title / boot-shaped scene (small OTs) | Re-saved during the PR #302 census; replaced the name-entry state |
| 2 | `slot01` | 2026-09-03 | **Battle**, several turns and effects queued | DMA2 ordering-table anchor ([`pr302-dma2-ot-cost-review.md`](pr302-dma2-ot-cost-review.md)); replaced the opening-mine field state |
| 3 | `slot02` | 2026-09-03 | **World map** | Largest ordering tables in the game (~1,000 nodes); replaced the dialogue-box state |
| 4 | `slot03` | 2026-09-03 | **Merchant**, busy screen | Replaced the choice-prompt state |
| 5 | `slot04` | 2026-08-31 | **Intro boss fight**, PLCHAR resident, attacks executing | Axis B / dispatch measurement anchor (`OVERLAY_EXTRACTION.md` §9, §11–§12; `tools/headless_ab.py`). Loaded with `last_ok: 0` once after the `savestate.c` rework — re-save if it misbehaves |
| 6 | `slot05` | 2026-08-30 | Dialogue in an open box | Player-reported |
| 7 | `slot06` | 2026-09-01 | Capcom logo, mid-FMV | **Resumes *past* the FMV** — useless for FMV profiling; use a clean boot (`tools/fmv_bench.py`) |
| 8 | `slot07` | 2026-09-01 | **World map** | Perf anchor (now 60 fps). The one `0x00002934` fail-fast happened resuming this file ([`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md)); not reproduced |
| 9 | `slot08` | 2026-09-01 | **Save / memory-card screen** | Perf anchor (now 60 fps) |
| 10 | `slot09` | 2026-09-01 | **Just before a merchant transition** | Perf anchor; doubles as a shop-text capture point |

The text-path states (1–4, 6) were all within ~30 s of boot on 2026-08-30 and
predate every rebuild since; they have survived rebuilds before (verified
2026-08-30), but re-save rather than investigate if one loads strangely.

## Loading them — use Enter/Start, not X

Enter/Start loads correctly in-game. The **X** key killed the process on the
2026-08-30 build, and the TCP `state load` path (`tools/playsession.py state
load`) wedges the listener on a *windowed* run — both are the **starvation
watchdog** (`exit(2)` after a 4 s emu-thread stall), not a savestate bug.
Launch with `PSX_STARVATION_TIMEOUT_US=0` (PowerShell:
`$env:PSX_STARVATION_TIMEOUT_US = "0"` on its own line first). Headless, the
TCP load works and returns immediately with `last_ok=1`, which is what
`tools/headless_ab.py` relies on. `PSX_LOAD_SLOT=N` loads file `slotN` at boot.

The working loop for text work: the player loads with Enter, and the analysis
side reads the live machine over the debug server.

```bash
python tools/playsession.py shot look.png     # what is on screen (needs --renderer software)
python tools/verify_msgtable.py               # walk the live message table
```

## Cheap to recreate — do not treat them as precious

Every state is minutes from boot or from an in-game memory-card save. If a
rebuild invalidates one, re-save it. Uncovered high-value screens worth a slot:
an equipment menu, and battle text.

## Caveats

- **States survive a rebuild** (verified 2026-08-30 across a pin reset +
  regenerate + relink), but the header carries only magic + version + BIOS
  checksum — **no build or recompiler-layout stamp** — so a mismatched binary
  is not refused at load. The 2026-09-01 framework merge reworked
  `savestate.c` and one pre-merge file loaded `last_ok: 0`. Treat a strange
  post-load state as suspect rather than assuming the file is bad.
- **Saving can still refuse** where an interrupt lands inside the dirty-RAM
  interpreter (`psx_irq_resume_context_snapshot_safe()`); rare now that the
  overlay bands are compiled. In-game memory-card saves (`saves/card1.mcd`)
  are the reliable way to preserve progress.
