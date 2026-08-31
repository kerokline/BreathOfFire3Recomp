# Savestate catalogue

**Status:** IN PROGRESS (last verified 2026-08-30)

What each savestate slot holds, so a later session can jump straight to the
screen it needs instead of replaying the prologue. Files are gitignored — this
document is the index, the states live only on Kevin's machine at
`saves/openbios/`.

## The numbering is off by one

**In-game slot *N* writes the file `state_8014AA0C_slot(N-1).pst`.**

Not a guess — established from write timestamps on 2026-08-30: the pair the
player saved as in-game slots 3 and 4, nine seconds apart, landed as `slot02`
(17:43:55) and `slot03` (17:44:04). The same −1 offset holds for every slot
observed. Quote the *file* number when scripting, the *in-game* number when
asking the player to load one.

## Contents

| In-game | File | Saved | Contents | Verified |
|---|---|---|---|---|
| 1 | `slot00` | 17:38 | Name-entry screen | **Yes** — read live at this screen; on-screen string located at `0x80014A86`, `0x80010000` block empty |
| 2 | `slot01` | 17:40 | Opening mine area, field | **Yes** — read live; area script loaded at `0x80010000` (1,124 B), decodes as the モーグ/ギリー prologue |
| 3 | `slot02` | 17:43 | Dialogue box, first frame of a message | Player-reported |
| 4 | `slot03` | 17:44 | Same box advanced once — **also carries a response prompt** | Player-reported |
| 5 | `slot04` | 18:04 | Overwritten during the watchdog investigation — contents unlabelled | No |
| 6 | `slot05` | 11:35 | Dialogue in an open box | Player-reported |
| 7 | `slot06` | 11:35 | That box advanced by one, same dialogue | Player-reported |

In-game **4** (`slot03`) is the most valuable of the set: a response prompt means
the engine is holding a choice list, which is a distinct text path from a plain
message and has its own layout constraints for translation.

## Loading them — use Enter, not X

**The X key kills the process, and so does `tools/playsession.py state load`.**
Enter/Start loads correctly. The kill is the **starvation watchdog**
(`exit(2)` after a 4 s emu-thread stall), not a savestate bug — launch with
`PSX_STARVATION_TIMEOUT_US=0` and the 4 s ceiling goes away (PowerShell:
`$env:PSX_STARVATION_TIMEOUT_US = "0"` on its own first — there is no inline
env-var prefix in PowerShell). Saving itself is
fine: `slot04` wrote complete and the process ran on for another 58 s. See
*Blockers* in [`STATUS.md`](STATUS.md).

The working loop is therefore: the player loads with Enter, and the analysis
side reads the live machine over the debug server. No TCP savestate command is
needed for any of the work done so far.

```bash
python tools/playsession.py shot look.png     # what is on screen
python tools/verify_msgtable.py               # walk the live message table
```

## Cheap to recreate — do not treat them as precious

Every state in the table is **within ~30 seconds of gameplay from boot**, so if
a rebuild invalidates them the cost is a couple of minutes, not a lost asset.
In-game **5, 6 and 7** are explicitly free to overwrite as better screens turn
up (a shop and an equipment menu are the two uncovered high-value ones). This
also means the rebuild question below is not worth a careful experiment — just
rebuild, and re-save if they break.

## Caveats

- **States survive a rebuild — answered 2026-08-30.** A state written by the
  `Aug 30 2026 09:26:46` build was loaded by the 19:45 rebuild (submodule reset
  to the pin, regenerated, relinked) and resumed correctly at the expected
  spot. So the format does not embed anything the rebuild invalidated. This is
  one observation and a behavioural check rather than a rigorous one, but the
  earlier worry that a rebuild breaks states is not borne out — and since every
  state here is ~30 seconds from boot, the cheap move on any doubt is still to
  re-save rather than investigate.
- The header carries magic + version + BIOS checksum, but **no build or
  recompiler-layout stamp**, so a mismatched binary would not be refused at
  load. Treat a strange post-load state as suspect rather than assuming the
  file is bad.
