# Handoff — next session

**Status:** IN PROGRESS (written 2026-08-30, updated 2026-08-30)

What to pick up, in order, and the traps already paid for. This is a *pointer*
document — the evidence lives in [`STATUS.md`](STATUS.md),
[`BRINGUP.md`](BRINGUP.md), [`LOCALIZATION.md`](LOCALIZATION.md),
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) and
[`regional-builds.md`](regional-builds.md); read those for why, read this for
what next.

## Where things stand in one paragraph

The game **loads**. It boots, renders its title screen, accepts input, and plays
the opening prologue with text drawing. Savestates save and load. The previous
session's "parks in a wait loop" diagnosis was wrong and is retracted — the
pinned PCs were `DrawOTag()` and `VSync()`, a healthy render loop. Separately,
the Japanese script has been located on disc: it lives in per-area `.EMI`
container sections, selected by destination address `0x80010000`. As of
2026-08-30 the **text engine is identified** — renderer, stepper, immediate
draw, font-atlas mapper and the message-index formula — which closes the one
blocker this document was previously built around. See
[`TEXT_ENGINE.md`](TEXT_ENGINE.md).

## The blocker is resolved

**The text engine is identified.** Full evidence in
[`TEXT_ENGINE.md`](TEXT_ENGINE.md); the short version:

| Function | Role |
|---|---|
| `0x80150598` | dialogue-box renderer (contains lead `0x80150770`) |
| `0x8015096C` | dialogue-box stepper (contains lead `0x80150DB0`) |
| `0x8015AD34` | `byte *draw(short x, short y, byte *str)` — menu/immediate path |
| `0x80151F4C` | font-atlas mapper — 21-glyph rows, 12 px cells |
| `0x8014F6BC` | glyph blitter wrapper → `0x8014F708` |

The three leads were `lw` instructions *inside* functions, not entries.
Resolving their containers is what cracked it.

`0x80010004` holds an **offset from `0x80010000`** to a `u16` message-offset
table. With `W = *(u32 *)0x80010004`:

```
base   = 0x80010000 + W
string = base + *(u16 *)(base + 2 * index)
```

Control code `8` + one index byte is a message reference. **That is the
translation interception point** — where a message number becomes a string
pointer — not the glyph blitter.

Corroborated independently: across the EN/FR/DE PAL releases the `0x80010000`
`.EMI` section is replaced wholesale (93.4% of bytes) and is the only section
that changes size, while audio/images/geometry stay byte-identical. Capcom grew
it freely per language, so **a translation is not limited to the JP byte
budget**. No Western EXE is an address-compatible donor, and none of them
contain runtime language support — each language was a separate build on its own
SKU. See [`regional-builds.md`](regional-builds.md).

### Next, in order

1. **Confirm the formula on a live run** (the framework's evidence rule). Break
   at `0x80150770`, read `*(u32 *)0x80010004`, walk the table, check the pointer
   lands on the text that is on screen.
2. **Settle variable-width advance — start by mining the US build.** The JP
   interpreter advances a hard-coded 12 px per glyph; English at fixed pitch
   will not read. Capcom's own Latin-script build had to solve this, so read the
   answer out of `SLUS_004.22` rather than inventing one: import it as a second
   Ghidra program (Raw Binary, `MIPS:LE:32:default`, base `0x80096000`) and find
   its equivalent of `0x8015AD34`. **Its addresses will not match JP** — it needs
   its own analysis pass. Open question is whether it uses proportional advance
   or keeps the 12 px cell with narrower art.
3. **Line-break policy.** Code `0x01` is authored into the JP script, so English
   needs re-authored breaks or a word-wrap pass. The US/EU script sections are
   the reference for how Capcom handled it.
4. **Name the five functions in `symbols.toml`**, then
   `python tools/sync_symbols.py` (never hand-edit `psx_symbols.h`).

## Task 1 — Ghidra: DONE, and how to re-enter it

Fully stood up on 2026-08-30. Nothing to redo.

| Piece | Where |
|---|---|
| Ghidra 12.1.3 | `D:\Utilities\ghidra_12.1.3_PUBLIC` |
| GhidraMCP 6.0.0 | installed to `<ghidra>\Ghidra\Extensions\GhidraMCP` |
| ghidra-mcp bridge | `C:\Users\kerok\Documents\GitHub\ghidra-mcp`, pinned to tag **`v6.0.0`** |
| `uv` 0.12.7 | `C:\Users\kerok\.local\bin` |
| `pyghidra` 3.1.0 + `jpype1` | installed into Anaconda from Ghidra's bundled wheels (offline) |
| Ghidra project | `D:\Utilities\GhidraProjects\BoF3` — **outside the repo on purpose**, it embeds disc-derived code |
| `.mcp.json` | repo root, paths corrected; already covered by `.gitignore:77` |

### Import parameters that matter

Raw Binary, `MIPS:LE:32:default`, base **`0x80093000`**. That is
`t_addr 0x80093800` minus the 0x800 PS-EXE header, so the header absorbs itself
and every text address lands at its true runtime address. Entry `0x8014AA0C`.

### Running a Ghidra script headlessly

```bash
python -m pyghidra.ghidra_launch --install-dir "D:/Utilities/ghidra_12.1.3_PUBLIC" ghidra.app.util.headless.AnalyzeHeadless "D:/Utilities/GhidraProjects" BoF3 -process SLPS_009.90 -noanalysis -readOnly -scriptPath <dir> -postScript <script.py>
```

Drop `-noanalysis -readOnly` when the script should persist changes.

### Ghidra traps, already paid for

1. **`analyzeHeadless.bat` cannot run `.py` scripts** — *"Ghidra was not started
   with PyGhidra. Python is not available."* Use the
   `python -m pyghidra.ghidra_launch` form above. This is the one that will cost
   an hour if forgotten.
2. **The bridge on `main` is v7.0.0 and unreleased**, with a breaking 272→251
   tool consolidation that does not match the 6.0.0 jar. The checkout is pinned
   to `v6.0.0`; leave it pinned unless the jar is upgraded too.
3. **Version-match is looser than feared.** GhidraMCP declared `12.1.2`; Ghidra
   is `12.1.3`. A one-line edit to `extension.properties` was enough — no need
   to chase down 12.1.2.
4. **The upstream `.mcp.json` carries the author's hardcoded path**
   (`c:/Users/benam/...`). The repo-root copy is already repointed.
5. **`psxrecomp_import.py` under-seeds on a raw-binary import.** `createFunction`
   returns `None` on undisassembled bytes, so it seeded 276 of 1026 directly.
   Auto-analysis then filled the rest — the program has 1025 functions and
   `tools/ghidra_seed.py` confirms 1023/1026 present. If a future re-import
   comes up short, run `tools/ghidra_seed.py` (it disassembles first, and
   deliberately refuses to force-disassemble large `low`-confidence
   `leaf|orphan` spans, which are data misread as code).
6. **`0x80010000` is not in the imported memory block** (`80093000`-`801F6FFF`).
   References to the script buffer will not resolve in the listing until a block
   is added for low RAM.

## Task 2 — soak

The game has never been played past the opening. Crashes, hangs and wrong
output are all useful, and area transitions are the interesting moments because
that is when `.EMI` files load.

Run the instrumented tree so a hang can be inspected **live** rather than
post-mortem:

```bash
cd build-dbg && ./BreathOfFire3_Recompiled.exe --debug-port 4370
```

```bash
python tools/playsession.py status
```

If something breaks, **leave the process running** — attaching to the debug
server beats a post-mortem.

## What Kevin can most usefully produce

**A savestate sitting on an open dialogue box.** This is now a *verification*
instrument rather than a discovery one — the engine is identified, and what is
needed is a live run to confirm the message-table formula (step 1 above): read
`*(u32 *)0x80010004`, walk the `u16` table, and check the resulting pointer
lands on the text visibly on screen.

After that: an item/equipment menu and a shop (both should route through
`0x8015AD34`, the immediate path), battle text, and the name-entry screen.
Ordinary field-gameplay states are low value.

```bash
python tools/playsession.py state save 1
python tools/playsession.py state load 1
```

Files land in `saves/openbios/state_8014AA0C_slotNN.pst` (+ `.thumb`).

**Untested caveat:** whether states survive a rebuild of `build-dbg`. The format
almost certainly embeds runtime layout, so a rebuild may invalidate them. Verify
before building a large library — a handful of well-chosen states first.

## Traps that already cost time — do not re-pay them

- **A Release build cannot be inspected at all.** `PSX_DEBUG_TOOLS` defaults
  **off** for Release, compiling out the TCP debug server; `--debug-port` is
  silently inert. This caused the retracted wait-loop misdiagnosis. Use
  `build-dbg` (`-DPSX_DEBUG_TOOLS=ON`) for anything diagnostic.
- **`--headless` + `--renderer opengl` screenshots black** — no GL context. Use
  `--renderer software` for captures.
- **The command is `gpu_state`, not `gpu`.**
- **Do not enable `PSX_XLATE_CAPTURE=1` for a playthrough.** Proven to yield
  nothing for this title, and it costs 26–35% throughput.
- **The framework's "capture is always-on" docs are stale** (F-3). The code
  default is off.

## Repo state at handoff

Uncommitted, nothing staged:

```
 M CLAUDE.md
 M README.md
 M docs/LOCALIZATION.md
 M docs/README.md
 M docs/STATUS.md
?? docs/HANDOFF.md          this file
?? docs/TEXT_ENGINE.md      the text engine — the main result of 2026-08-30
?? docs/regional-builds.md  JP/US/EN/FR/DE comparison; confirms the script section
?? tools/ghidra_seed.py     second-pass Ghidra function seeder (see trap 5 above)
?? toolchain/               not created by this work
```

No disc data is in the repo. The Ghidra project lives at
`D:\Utilities\GhidraProjects\BoF3`, deliberately outside the repo, because it
embeds the boot EXE. Extracted `.EMI` sections stayed in the scratchpad;
`build-dbg/` and its screenshots are gitignored.

## External material this depends on

- **`D:\BoFIII`** — prior decode work: the 435/435 character table,
  `decode_text.py`, and an 11,491-line slot-aligned JP/EN corpus. Reuse it;
  do not redo it. Caveats in [`LOCALIZATION.md`](LOCALIZATION.md) §4.2.
- **`BreathOfFire3EnglishRecomp/`** — a **local-only donor** repo for the
  official English script, to be retired once a disc-derived translation path
  works. Do not publish it, and do not invest in its build health, submodule
  pins, or CI. Its `psxrecomp` gitlink floated to master and its `disc =` is an
  absolute path; neither matters unless it is ever actually built.
- **`isos/`** (gitignored) now holds five releases: Japan, USA, Europe/English,
  France and Germany. The three PAL discs are what proved the script section and
  the byte-budget freedom — keep them, they are the reference for any
  localization question. See [`regional-builds.md`](regional-builds.md).
- The `.EMI` format comes from the community data doc cited in
  [`LOCALIZATION.md`](LOCALIZATION.md) §4.
