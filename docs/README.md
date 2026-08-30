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

`HANDOFF.md` is the next-session entry point: what to pick up, in order, and
the traps already paid for. It points at evidence rather than restating it.

`STATUS.md` is the living status doc — where the project stands, what's in
flight, what's blocked. It is the first thing a new session reads after
`CLAUDE.md`, and the file that gets updated as work lands. `CLAUDE.md` stays
rules-and-shape only.

## Conventions

- **One document per concern.** A doc is a durable artifact, not a chat log.
  If a finding is worth keeping, it gets a file; if it isn't, it doesn't.
- **Filenames:** `UPPER_SNAKE.md` for standing references
  (`OVERLAY_STATUS.md`), `lower-kebab.md` for narrow investigations
  (`text-draw-pc-census.md`).
- **Status header.** Every doc opens with a status line so a new session knows
  whether to trust it:

  ```markdown
  **Status:** IN PROGRESS | STABLE | SUPERSEDED by [X](X.md) | STALE (last verified YYYY-MM-DD)
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

## Suggested docs as work begins

Create these when the work actually starts — empty stubs are noise:

| File | Contents |
|---|---|
| `BRINGUP.md` | Boot/soak log: what runs, where it dies, what was fixed |
| `OVERLAY_STATUS.md` | BoF3 overlay map — discovered overlays, load addresses, seed gaps |
| `SYMBOLS_NOTES.md` | Rationale behind `symbols.toml` entries; how each was identified |
| `LOCALIZATION.md` | JP→EN string translation: capture inventory, text-draw PC census, font work |
| `TEXT_ENGINE.md` | **Exists.** The message interpreter, renderer and glyph path — control codes, the `0x80010004` message-index formula, interpreter state block |
| `regional-builds.md` | **Exists.** JP/US/EN/FR/DE comparison — no runtime language support, no address-compatible donor, and the `.EMI` evidence isolating the script section |
| `ENHANCEMENTS.md` | Post-faithfulness work: load-time reduction, widescreen, etc. |
