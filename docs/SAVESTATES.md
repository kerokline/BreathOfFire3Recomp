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
| 1 | `slot00` | 2026-09-05 | **Title / start screen** | Quick restarts |
| 2 | `slot01` | 2026-09-05 | **Just before the intro-boss battle** | Auto-advances into the battle; after it, any command auto-advances through several scene transitions of auto-playing dialogue and areas — a long scripted stretch from one load |
| 3 | `slot02` | 2026-09-05 | **Inside the Nu boss fight** | Boss-battle anchor |
| 4 | `slot03` | 2026-09-05 | **Inside a regular field battle** | `tools/callstack_diff.py` differential anchor (Attack / Defend / Watch / Auto / Run — see the command-menu note below) |
| 5–12 | `slot04`–`slot11` | earlier | **Overwritten or stale** (user, 2026-09-05) — the 2026-09-03/04 anchors listed in the Log below no longer hold what they said | Re-save before use |

**Hidden command-menu entries.** Auto-attack and Run do not appear in the
battle command list: **hold L1** to hover Auto-attack, **hold R1** to hover
Run, then Circle to confirm (user, 2026-09-05). Run is a randomised check, so
its call path differs on success (ends combat) vs failure. In
`callstack_diff.py` terms: `--hold l1 --press circle` / `--hold r1 --press
circle`, the same mechanism as `--hold right` for Defend.

Former contents (2026-09-03/04, for the Log's cross-references): `slot01`
mid-battle DMA2 anchor, `slot02` world map, `slot03` merchant, `slot04`/`05`
the herb-effect battle with Rei, `slot06` mid-FMV, `slot07` world map,
`slot08` memory-card screen, `slot09` pre-merchant, `slot10` battle menu on
Attack (AREA020), `slot11` Watch armed vs Nu.

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
