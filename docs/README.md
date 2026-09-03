# `docs/` — agent + developer notes for BreathOfFire3Recomp

This folder holds **title-owned** documentation: notes, plans, and findings that
belong to *this game*, not to the framework.

## Where documentation lives

| Location | Owner | Rule |
|---|---|---|
| `docs/` (here) | This repo | Title-specific work: boot/soak logs, overlay findings, symbol archaeology, translation notes, enhancement plans |
| `psxrecomp/docs/` | Framework submodule | Read-only reference. **Never edit** — changes there belong upstream in `mstan/psxrecomp` |
| `psxrecomp/CLAUDE.md` | Framework submodule | Framework constitution. Read it before touching anything under `psxrecomp/` |
| `recomp-ui/docs/` | Launcher submodule | Read-only reference |
| `/CLAUDE.md` | This repo | Session bootstrap — keep it short and current |

## Index

Read in this order at session start: `STATUS.md`, `HANDOFF.md`, then whatever
the task touches.

| Doc | Kind | Contents |
|---|---|---|
| [`STATUS.md`](STATUS.md) | living | Where the project stands, what's in flight, what's next, and the dated Log. Update this as work lands |
| [`HANDOFF.md`](HANDOFF.md) | living | What to pick up, how to build against the current pin, traps already paid for, the tooling table |
| [`INVENTORY.md`](INVENTORY.md) | snapshot | What is in the repo and on this machine |
| [`OVERLAYS.md`](OVERLAYS.md) | evidence | *Why* most of the game is overlays, why seeding cannot substitute, and the `.EMI` TOC finding that made disc extraction possible |
| [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) | evidence | *How*: the ten-band map, extraction, compilation, build wiring, and the numbered measurement sections (§5–§12) other docs cite — including the three upstream dispatch fixes and the all-bands result |
| [`BRINGUP.md`](BRINGUP.md) | log | Boot 001/002 (first boot, the retracted "wait loop"), and framework observations F-1 / F-2 |
| [`TEXT_ENGINE.md`](TEXT_ENGINE.md) | evidence | The message interpreter, renderer, glyph path, control codes, and the per-block message-table formula confirmed live |
| [`LOCALIZATION.md`](LOCALIZATION.md) | plan + evidence | JP→EN: the capture-pipeline findings (F-3 / F-4), the `.EMI` container format, the `0x80010000` selector, prior decode work at `D:\BoFIII` |
| [`regional-builds.md`](regional-builds.md) | evidence | JP/US/EN/FR/DE comparison: no runtime language support, no address-compatible donor, the full section census, the four text locations and 37 language-bearing images |
| [`MEDNAFEN.md`](MEDNAFEN.md) | reference | Stock Mednafen in `./mednafen/` as an isolated oracle: what crosses over (memcards yes, savestates no), the card naming, and driving it with `tools/mednafen_ctl.py` |
| [`SAVESTATES.md`](SAVESTATES.md) | index | What each savestate slot holds; the in-game-vs-file off-by-one |
| [`NAME_MAP.md`](NAME_MAP.md) | plan + evidence | The readability track: `names/` sidecars (overlays / functions / areas), the status+evidence rule, the area poller, routes to earn names |
| [`subsystem_map.html`](subsystem_map.html) | generated | Browsable map (bands → overlays → functions, boot EXE, areas). Regenerate with `tools/subsystem_map.py`; never hand-edit |
| [`ENHANCEMENTS.md`](ENHANCEMENTS.md) | plan | Post-faithfulness work: scanlines (shipped upstream), pause/frame-advance (designed), costed backlog |
| [`vblank-pacing-bug.md`](vblank-pacing-bug.md) | investigation | The Capcom FMV slowdown: root cause (SPU snapshot gate), fix, and the two wrong theses |
| [`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md) | investigation | One unreproduced fail-fast into kernel RAM on a savestate resume |
| [`battle-icon-strip-rows.md`](battle-icon-strip-rows.md) | investigation | Enlarged command icon loses its top six texture rows: VRAM vs disc vs Beetle oracle, loss localised to the boot-time load of `FIRST.EMI` |
| [`battle-depth-order.md`](battle-depth-order.md) | investigation | Sprites lunging behind the battle doorway: list order honoured, Beetle shows the same, game behaviour |
| [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md) | investigation + proposal | build-dbg "crashes" were the starvation watchdog exiting on a cross-thread clock race and reporting itself as `atexit`; evidence, upstream diff, verification plan |
| [`pr302-dma2-ot-cost-review.md`](pr302-dma2-ot-cost-review.md) | review + evidence | Cross-title check of upstream psxrecomp #302 (DMA2 linked-list cost 8+5 → 1+0): BoF3 A/B census, no regression, plus the hardware argument the PR is missing |

## Conventions

- **One document per concern.** A doc is a durable artifact, not a chat log.
  If a finding is worth keeping, it gets a file; if it isn't, it doesn't.
- **No dated banners stacked on top of living docs.** When something changes,
  update the sections and add a `STATUS.md` Log row. A doc that needs a
  correction gets the correction *in place* with a date; superseded material is
  condensed to what a reader needs to not re-derive it, not preserved verbatim.
- **Filenames:** `UPPER_SNAKE.md` for standing references, `lower-kebab.md`
  for narrow investigations.
- **Status header.** Every doc opens with a status line so a new session knows
  whether to trust it:

  ```markdown
  **Status:** IN PROGRESS | STABLE | DONE | RESOLVED | SUPERSEDED by [X](X.md) | STALE (last verified YYYY-MM-DD)
  ```

- **Absolute dates.** Write `2026-08-29`, never "last week".
- **Verify before you cite.** Addresses, PCs, and file paths drift. If a doc
  names `0x8014AA0C` or `tools/sync_symbols.py`, confirm it still exists
  before acting on it.
- **Findings need evidence.** Record how a claim was established (which trace,
  which oracle run, which disassembly) — the framework rule is that accuracy
  claims are cross-referenced against an external comparative, not asserted.
- **Never commit disc data.** No `.bin`/`.cue`/`.iso` excerpts, no ripped
  assets, no BIOS bytes — not even inline in a markdown file. `.gitignore`
  blocks the files; it can't block a paste.
