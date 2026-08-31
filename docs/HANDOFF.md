# Handoff — next session

**Status:** IN PROGRESS (rewritten 2026-08-30, end of the play/diagnosis session)

Read [`STATUS.md`](STATUS.md) for where the project stands and
[`OVERLAYS.md`](OVERLAYS.md) for the finding the next task rests on. This file
is what to pick up and the traps already paid for.

## Where things stand in one paragraph

The game **plays**. It boots, renders, has audio, takes input, writes memory
cards, and has been played past the prologue into the mines with area
transitions, name entry and menus. The **text engine is identified and confirmed
on a live run** — that work is done. The one thing standing between here and a
real playthrough is that **most of BoF3's code lives in overlays that are not
statically recompiled**: 81.6% of the boot EXE's text segment is zero-fill, and
a measured session put 93.6% of interpreted instructions in that space.

## The next task — static overlay extraction

**Do not build DMA-time capture, and do not enable `[runtime] overlay_cache`.**
The framework's "disc extraction does not work" advice is Tomba-specific;
BoF3's `.EMI` TOC states each section's RAM destination and the sections are
contiguous. Evidence in [`OVERLAYS.md`](OVERLAYS.md) section 5.

Suggested order:

1. **Enumerate.** Walk all 880 `.EMI` files, read each TOC, collect every
   section whose destination lands in the code region. `tools/emi.py` already
   parses the format; `tools/disc_ls.py` extracts files. Beware: `disc_ls.py`
   extracts whole files, and the set is 259 MB — consider reading just the
   first 2 KB (header + TOC) per file.
2. **Code-test each candidate.** Not every zero-fill destination is code.
   `AREA004.EMI` section 8 at `0x80104000` has **zero** `jr $ra` and zero
   prologues — it is data. The cheap discriminator used so far is `jr $ra`
   (`0x03E00008`) and `addiu sp,sp,-N` (`0x27BDxxxx` with bit 15 set) counts.
3. **Start with band 1.** `GAME.EMI` section 0 goes to `0x80196800`, 227,556
   bytes, one occupant, and it is where field-play interpretation concentrates.
   Feed it to Layer B (`game.toml [[overlays]]` +
   `psxrecomp/tools/compile_overlays.py`), which wants
   `(load_addr, bytes, seeds)` — the TOC gives the first two.
4. **Band 2 is the hard one, and it is optional at first.** `0x801D0C00` is a
   swap slot shared by `SHOP` / `STATUS` / `BATTLE` / `START`. Pre-compiling
   more than one occupant means the runtime must register *and unregister* by
   mode — get it wrong and it is OV-1 in
   `psxrecomp/docs/overlay-status.md` (stale registration, wrong native code,
   Tomba's blue screen). Prove band 1 first.

Expectation management: `overlay-status.md` records that Tomba's first result
was **correctness only**, near-0% native, because one overlay is not coverage.
Do not promise a speed win from step 3 alone.

## Traps paid for today — do not re-pay them

- **PowerShell has no inline env-var prefix.** `VAR=x cmd` is a parse error.
  Use `$env:VAR = "0"` then `.\path\to.exe`. The framework docs are bash.
- **The "crashes" were the starvation watchdog**, not the game.
  `starvation_ring.c` calls `exit(2)` after 4 s without an emu-thread
  heartbeat. Signature: `reason: atexit` with `exit_origin: "unknown"` (the
  tagged paths are `tcp_quit` / `sdl_window_close`). Disable with
  `PSX_STARVATION_TIMEOUT_US=0`.
- **Two ~87 MB freeze dumps are written at EVERY boot**, at frame ~328, from a
  `slow_frames` then `hard_freeze` false positive. ~160 MB per launch. Prune
  `build-dbg/psx_freeze_dump_*.json` between sessions.
- **Savestates refuse in overlay-heavy code, by design.**
  `psx_irq_resume_context_snapshot_safe()` is `g_cosim_dirty_pump_site == 0`
  (`interrupts.c:629`) — an interrupt taken inside the dirty-RAM interpreter is
  never snapshot-safe. Retrying does not help; it tracks the *interrupt path*,
  not the aggregate ratio. **Use in-game memory-card saves** to preserve
  progress. Savestates *do* survive a rebuild (verified).
- **`tools/playsession.py state load` is broken** — it exceeds the I/O thread's
  30 s bound (`emu busy or frozen`) and leaves the listener dead. The in-game
  **X** key also kills the process; **Enter/Start** works. Load in-game, then
  read RAM over TCP.
- **In-game savestate slot N is file `slotN-1`.** Established from write
  timestamps, see [`SAVESTATES.md`](SAVESTATES.md).
- **Seeding is a dead end, proven three ways.** Extending
  `seeds/ghidra_funcs.txt` from 523 to 868 gave a **byte-identical generate**;
  seeding interior PCs produced aliases into a parent compiled from zero bytes;
  and the session profile shows static EXE code with **`entries = 0`**, so the
  interpreter never *enters* static code at all. Do not revisit this.
- **A generate that changes the shard count needs a CMake reconfigure**, or the
  link fails with undefined `func_*`. The generated source list is captured at
  configure time.
- **Keep the `psxrecomp` submodule on the pin.** It had floated to `a91884a4`;
  it is back at `f24b7e5d`. Reset with
  `git submodule update --init --recursive psxrecomp`.
- Earlier retracted-in-place diagnoses, left visible in `STATUS.md` so they are
  not re-derived: overlays as the cause of a *crash* (there was no crash),
  savestate load as the cause of the freeze dumps, and the seed list as the
  interpretation bottleneck.

## Tooling added today

| Tool | Use |
|---|---|
| `tools/harvest_interp_pcs.py` | Against a live run: interpreted/native ratio plus proven interpreted entry PCs, written to `analysis/observed_interp_pcs.json` |
| `tools/verify_msgtable.py` | Walks the message table on a running game |
| `tools/export_seeds.py` | Analyser to seeds merge. **Kept only for the record — its result was null.** |

Existing and still useful: `tools/emi.py` (parse/extract `.EMI`),
`tools/disc_ls.py` (list/extract the ISO9660 tree), `tools/disasm_exe.py`.

## Open questions

- **`0x801CEEDC`** accounted for 91 M interpreted instructions at boot but lies
  *past* the end of `GAME.EMI` section 0 (`0x801CE0E4`). Which overlay owns it?
- **211 of 8,694 dispatch addresses are zero-fill**, from 18 of 523 seeds (all
  `low` confidence). Those are registered native entries compiled from nothing.
  Dirty-RAM invalidation masks them today; audit before trusting native
  dispatch in that range.
- **Text paths not yet seen live:** a shop, an equipment menu, and battle text.
  Each is a sub-minute check against a running game with
  `tools/verify_msgtable.py` and a screenshot.
- **Translation still needs** variable-width glyph advance (the JP interpreter
  hard-codes 12 px) and a line-break policy; mine `SLUS_004.22` rather than
  inventing one. And menus/items/name entry are a **separate text pool** from
  the `.EMI` area script.

## Environment

- `python`, not `python3`.
- MSYS2 toolchain is **not** on PATH by default:
  `export PATH="/c/msys64/mingw64/bin:$PATH"` (GCC 16.2.0, CMake 4.4.2,
  Ninja 1.13.2, ccache).
- Build: `./psxrecomp/tools/ci/build_emitters.sh`, then
  `python psxrecomp/psxrecomp_cli.py generate --config game.toml
  --project-root . --disc "isos/Breath of Fire III (Japan).cue"`, then
  `cmake --build build-dbg --target psx-runtime`.
- `build-dbg` is the diagnosis tree (`-DPSX_DEBUG_TOOLS=ON`). A Release build
  has no debug server and cannot be inspected at all.
- Ghidra project at `D:\Utilities\GhidraProjects\BoF3` (1025 functions),
  deliberately outside the repo. `analyzeHeadless.bat` cannot run `.py` —
  use `python -m pyghidra.ghidra_launch`.
- Prior decode work at `D:\BoFIII`: character table plus `decode_text.py`,
  reused by `tools/verify_msgtable.py`. Open the JSON as UTF-8.
