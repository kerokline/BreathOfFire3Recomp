# Current state

**Status:** IN PROGRESS (last verified 2026-08-30)

Living status doc — the one place a new session learns where the project
actually stands. Update this rather than `CLAUDE.md`. Durable findings graduate
into their own `docs/` file (see [`README.md`](README.md)); this stays a short
"where we are, what's next".

## Where we are

**Most of Breath of Fire III is overlays (measured 2026-08-30).** The boot EXE
declares a 1,456,128-byte text segment, but **1,187,899 bytes of it — 81.6% —
are zero-fill** in the image, in 11 runs of 2 KB or more spanning
`0x80093801`-`0x801F6C00`. Only ~268 KB is real static code; everything else is
space that overlays load into at runtime. Static recompilation therefore covers
a minority of the game's code by construction, and the dirty-RAM interpreter
carries the rest — which is why execution measures 84-93% interpreted and why
savestates refuse. **The overlay capture/compile path is not an optimisation for
this title; it is the main remaining engineering task.** Full evidence in
[`OVERLAYS.md`](OVERLAYS.md).

**The game loads (2026-08-30).** Title screen renders, Start is accepted, and
the opening prologue plays with Japanese text drawing correctly. Evidence and
method in [`BRINGUP.md`](BRINGUP.md) → Boot 002.

**Boot 001's "wait loop" was a misreading and is retracted.** The two pinned
`store_pc` values are `DrawOTag()` and `VSync()` — a healthy render loop. The
CD-ROM hypothesis is dead. What actually hid this: the Release build sets
`PSX_DEBUG_TOOLS=OFF`, which compiles out the TCP debug server, so there was no
way to look at the screen.

**The text engine is identified (2026-08-30)** — renderer, stepper, immediate
draw, font-atlas mapper, and the `0x80010004` message-index formula. This closed
the standing translation blocker. Confirmed independently by cross-language
`.EMI` diffing. [`TEXT_ENGINE.md`](TEXT_ENGINE.md),
[`regional-builds.md`](regional-builds.md).

Headlines:

- Game still emits **completely clean under `strict = true`** — 2.5M lines, 35
  shards, 0 skipped, 0 unsupported, 1467 dispatch entries.
- `build-dbg/` is the new diagnosis tree (`-DPSX_DEBUG_TOOLS=ON`, 232/232).
  `build-release/` is untouched and stays the shipping config.
- GPU is live: 1,198,959 draw commands, `disabled=0`, double-buffered,
  3D geometry submitting.
- `tools/disasm_exe.py` added — disassembles the staged boot EXE and resolves
  `lui`/`lw` pairs to absolute addresses, naming MMIO. This is what turned the
  "wait loop" into `DrawOTag`/`VSync` instead of another guess.
- **No Western release is an address-compatible donor, and none has runtime
  language support.** All five releases compared (JP, US, EN, FR, DE): one EXE
  per disc, a separate SKU per language, EU vs US only ~21% word-identical over
  the real code region. The earlier "US not address-compatible with JP" finding
  (0x3000 shift, 4.6% seed overlap) is confirmed and generalised.
  [`regional-builds.md`](regional-builds.md).
- **The script section is variable-size.** Capcom grew `0x80010000` freely per
  language (EN 7912 -> FR 8085 -> DE 8412 in one area file), so a translation is
  **not** bound by the JP byte budget, and only that one section needs replacing.

## In flight

- `docs/LOCALIZATION.md` — new; the JP→EN assessment and the two upstream bugs
  it turned up (F-3, F-4).
- `docs/TEXT_ENGINE.md` — new; the text engine identified end to end.
- `docs/OVERLAYS.md` — new; the measured case that overlays dominate this
  title, and why seeding cannot substitute.
- `docs/regional-builds.md` — new; the JP/US/EN/FR/DE comparison, and the
  independent confirmation of the `0x80010000` script section.
- `tools/ghidra_seed.py` — new; second-pass Ghidra function seeder.
- `docs/SAVESTATES.md` — new; what each savestate slot holds, and the in-game
  vs file off-by-one. Seven states catalogued, covering name entry, field,
  dialogue and a response prompt.
- `BreathOfFire3EnglishRecomp/` — scaffolded but **not** generated or built. Its
  `psxrecomp` gitlink floated to master (`47bda817`) vs this repo's `f24b7e5d`,
  and its `disc =` is an absolute machine-local path. Both need a decision
  before it is built.

## Next up

1. **Overlay capture — the hot code is runtime-loaded, and cannot be seeded.**
   Measured on the rebuilt tree: **93.1% of executed instructions are
   interpreted** (131.5 M interpreted vs 9.7 M native at boot). A single
   address, **`0x801CEEDC`, accounts for 91,021,658 of them — 89% of all
   interpretation — from only 220 entries.** It and every other hot game-range
   PC (`0x801CF2F8`, `0x801D4F60`, `0x801D1844`, `0x801D7CA4`, …) lie in
   `0x801C0000`-`0x801E0000`, which is **entirely zero in the boot EXE image**.
   That code arrives at runtime. It is the genuine overlay case, and the
   framework answer is the capture/compile path
   (`overlay_captures.json`, `[runtime] overlay_cache`,
   `psxrecomp/tools/compile_overlays.py`) — see
   `psxrecomp/docs/overlay-status.md`, noting that work lives on
   `feat/overlay-jit-cache` and the pin `f24b7e5d` may not carry all of it.
   The remaining interpreted PCs are BIOS/kernel RAM below `0x80093800`
   (`0x800000B0`, `0x800027AC`, …), which is expected and not fixable here.

2. **Latent risk — zero-fill "functions" in the seed list.** `0x801D0C04` is a
   *pre-existing* seed and a `functions.tsv` row (confidence `low`, tags `leaf`,
   size 49,468) whose bytes are **all zero in the image**. The recompiler emits
   a body of NOPs for it and registers it in the dispatch table. Today
   dirty-RAM invalidation masks this (the region is written at runtime, so the
   interpreter wins), but it is exactly the OV-1 stale-registration failure mode
   from `psxrecomp/docs/overlay-status.md`. Audit `low`-confidence seeds against
   the image before trusting native dispatch in that range.

3. **Resume the soak** with `PSX_STARVATION_TIMEOUT_US` set (see *Blockers*),
   and run `python tools/harvest_interp_pcs.py` at the end of the session to
   measure coverage and capture the interpreted-PC profile.

4. ~~**Confirm the message-table formula on a live run.**~~ **DONE 2026-08-30.**
   Confirmed against both block shapes; the `0x80010004` `W` header turned out
   to be per-block, not universal. See [`TEXT_ENGINE.md`](TEXT_ENGINE.md)
   → *Live confirmation*. New next step: settle whether Latin/digit bytes are
   raw ASCII, since the area script uses the same byte range for control codes.
5. **Settle variable-width and line-break policy — mine the US build first.**
   Glyph advance is a hard-coded 12 px and JP line breaks are authored as
   control code `0x01`. Capcom's Latin-script build already solved both, so read
   the answer out of `SLUS_004.22` (import as a second Ghidra program, Raw
   Binary, `MIPS:LE:32:default`, base `0x80096000`; its addresses do **not**
   match JP) rather than inventing one.
6. **Settle the English repo's submodule pin and disc path**, then generate it
   if a second build is still wanted.

## Environment

Local build toolchain installed and verified 2026-08-29 — MSYS2 MinGW-w64 at
`C:\msys64`, the layout `psxrecomp/CLAUDE.md` §16 already assumes:

GCC 16.2.0 · Clang 22.1.8 · CMake 4.4.2 · Ninja 1.13.2 · ccache 4.14 ·
SDL3 3.4.14 · SDL2 2.32.10 · Python 3.14.7 (mingw64)

Verified by building the framework emitters end to end — 169/169 targets, with
`psxrecomp-game`, `psxrecomp-bios` and `psxrecomp-analyze` all produced and
executing. Setup steps and the Windows `PATH`/Python caveats live in the repo
[`README.md`](../README.md#development-environment).

## Blockers

None. The game loads and runs.

Open, non-blocking:

- **The "crashes" are the starvation watchdog killing the process on purpose.**
  Root-caused 2026-08-30. `starvation_ring.c` calls **`exit(2)`** after **4 s of
  wall clock without an emu-thread heartbeat**, printing
  `starvation_watchdog: ... aborting` to stderr. That is why every run report
  shows `reason: atexit` with `exit_origin: "unknown"` — `exit(2)` is untagged,
  unlike the `tcp_quit` / `sdl_window_close` paths. The last one measured a
  **4.027 s** gap. It is a debug-build safety net for "TCP died, BIOS still
  running", not a game fault, and `build-release` does not have it.

  **Fix — set the env override when playing.** PowerShell (the shell actually
  used on this machine) has **no inline env-var prefix**, so the bash form is a
  parse error there:

  ```powershell
  $env:PSX_STARVATION_TIMEOUT_US = "0"; .\BreathOfFire3_Recompiled.exe --debug-port 4370
  ```

  Git Bash form, for the same thing:

  ```bash
  PSX_STARVATION_TIMEOUT_US=0 ./BreathOfFire3_Recompiled.exe --debug-port 4370
  ```

  `0` disables the watchdog; any microsecond value raises the threshold. The
  4 s budget is easily blown by a savestate write, a disc seek, or — perversely
  — by the freeze-dump machinery itself, which writes two ~80 MB JSON files
  while holding the emu thread.

- **Two ~80 MB freeze dumps are written at every boot.** Both at frame ~328
  during BIOS boot, `wedge_kind` `slow_frames` then `hard_freeze` one second
  later; the game then recovers and runs normally. A watchdog false positive
  caused by slow dirty-RAM interpretation at boot (6.7 M interpreted
  instructions), costing ~160 MB per launch. Unrelated to savestates.

- **Why saves fail — the precise rule.** `savestate_poll` requires
  `psx_irq_resume_context_snapshot_safe()`, which is literally
  `return g_cosim_dirty_pump_site == 0;` ([`interrupts.c:629`]) — *"dirty
  interpreter pump sites are IRQ-precise but not save-state safe: they can
  publish a valid committed PC while CPUState still describes a helper/device
  or previous local context."* So **every interrupt taken from inside the
  dirty-RAM interpreter is unsavable by design.** With execution measured at
  **91% interpreted** (sampled live: 9.0-9.1% native over five one-second
  intervals), almost every poll lands on a pump site, the 2 s defer window
  expires without one safe sample, and the save is refused.

  This is not probabilistic bad luck — an earlier "roughly one attempt in six
  should work, just retry" reading was wrong, since the poll runs every frame
  for two seconds and would trivially win at those odds. It is structural, and
  it is the same root cause as everything else: **uncovered overlay code**.
  Saves succeed in stretches that execute recompiled static code (the text
  engine at `0x8015xxxx` is in the EXE and native; the hot overlay region
  `0x801Cxxxx`-`0x801Dxxxx` is not), which matches the history — name entry and
  both dialogue-box states saved fine, open-field states in the mine now refuse.

- **Savestate operations, corrected.** Saves work: `slot04` was written
  complete (1.47 MB) and the process survived **58 seconds** afterwards, so the
  save did not cause the exit. In-game load via **Enter/Start** works; the **X**
  key does not. `tools/playsession.py state load` still returns
  `emu busy or frozen` (the I/O thread's 30 s bound) and leaves the listener
  dead — use the in-game Enter path and read RAM over TCP instead. An earlier
  claim that savestate load caused the freeze dumps is **withdrawn**; the dumps
  are the boot-time artifact above.

- Four upstream framework issues, all documented, none affecting BoF3 booting:
  F-1 / F-2 in [`BRINGUP.md`](BRINGUP.md) (false-positive BIOS staleness
  warning; garbage cross-function targets), F-3 / F-4 in
  [`LOCALIZATION.md`](LOCALIZATION.md) (stale "capture is always-on" docs;
  Shift-JIS validator accepting MIPS instruction words). Fixes belong in
  `mstan/psxrecomp`.
- Release builds cannot be inspected at all (`PSX_DEBUG_TOOLS=OFF`). Expected,
  but worth knowing before diagnosing anything against `build-release/`.
- `gh` not installed; affects GitHub CLI flows only.
- Ghidra 12.1.3 + GhidraMCP 6.0.0 are now installed and the project is built
  (`D:\Utilities\GhidraProjects\BoF3`, 1025 functions). The repo-root
  `.mcp.json` points at the ghidra-mcp stdio bridge on `127.0.0.1:8089` — note
  the framework's own `.mcp.json` expects SSE on `localhost:7777`, a different
  implementation; follow ghidra-mcp's. The MCP server needs the Ghidra GUI
  running; headless scripting works without it.

## Log

| Date | Entry |
|---|---|
| 2026-08-29 | Repo inventoried; `docs/` and `CLAUDE.md` established. Localization intent recorded. |
| 2026-08-29 | Build toolchain installed (MSYS2 MinGW-w64) and proven by a full 169-target emitter build. Toolchain blocker cleared; README gained a *Development environment* section. |
| 2026-08-29 | Dump moved into gitignored `isos/`; `[game].disc` switched from an absolute machine-local path to repo-relative `isos/Breath of Fire III (Japan).cue`. Portable for any checkout. |
| 2026-08-29 | **First boot.** Emitters built (67/67); generate clean under `strict`; `psx-runtime` linked (232/232); headless boot reaches game code and runs ~26k frames. Logged in [`BRINGUP.md`](BRINGUP.md) with framework bugs F-1 / F-2. |
| 2026-08-30 | **The game loads.** Boot 001's wait-loop diagnosis retracted — the pinned PCs are `DrawOTag`/`VSync`. Root cause of the blindness: `PSX_DEBUG_TOOLS=OFF` in Release. Built `build-dbg/`, added `tools/disasm_exe.py`, captured title screen + prologue over the debug server. [`BRINGUP.md`](BRINGUP.md) → Boot 002. |
| 2026-08-30 | **Savestates verified working** on the LLE backend — save *and* load, round-trip confirmed against the VSync counter at `0x8018603C` (advanced 17,460 -> 20,312, rewound to ~17,828 on load). Files: `saves/openbios/state_8014AA0C_slotNN.pst` + `.thumb`. Driven by `tools/playsession.py state save|load N`. |
| 2026-08-30 | **Script load path measured.** `wtrace` on the text buffer shows the script arriving by CD-ROM DMA (channel 3) kicked from PC `0x80177B78`. `rtrace_*` is MMIO-only so it cannot see the *readers* — finding text-draw PCs is an open tooling gap. [`LOCALIZATION.md`](LOCALIZATION.md) 4.2b. |
| 2026-08-30 | **Localization assessed.** Capture pipeline armed via `PSX_XLATE_CAPTURE=1` (it is *not* always-on, contrary to framework docs — F-3); 39.6M calls scanned, 0 real strings, 3 false positives that decode as MIPS instructions (F-4). English scaffold generated; US build shown **not** address-compatible with JP (0x3000 shift, 4.6% seed overlap). [`LOCALIZATION.md`](LOCALIZATION.md). |
| 2026-08-30 | **Text engine identified - the translation blocker is closed.** Ghidra 12.1.3 + GhidraMCP 6.0.0 + PyGhidra stood up; boot EXE imported as Raw Binary at `0x80093000` (1025 functions). The three `0x80010004` leads resolve to `0x80150598` (box renderer), `0x8015096C` (stepper) and `0x8015AD34` (immediate `draw(x,y,str)`), sharing one control-code vocabulary and the glyph path `0x8014F6BC` / `0x80151F4C` (21-glyph, 12 px atlas). Message lookup is `0x80010000 + W + u16[base + 2*index]` where `W = *(u32 *)0x80010004`. [`TEXT_ENGINE.md`](TEXT_ENGINE.md). |
| 2026-08-30 | **Regional builds compared (JP/US/EN/FR/DE).** No release has runtime language support - one EXE per disc, no language strings, a separate SKU per language (SLES-01304/01319/01320). No Western EXE is address-compatible (EU vs US ~21% word-identical over the real code region; earlier whole-file similarity figures were zero-fill artifacts). Cross-language `.EMI` diffing isolates all divergence to the `0x80010000` section (93.4% of bytes, and the only section that changes size), **independently confirming** the Ghidra finding and showing translations are not bound by the JP byte budget. [`regional-builds.md`](regional-builds.md). |
| 2026-08-30 | **Message-table formula confirmed live — the last static-only claim is now evidenced.** Read directly off a running `build-dbg` session: the name-entry screen's on-screen string located at `0x80014A86`, and the formula walked from `0x80014000 + W` decoding 17/24 item descriptions; then the mine-area script at `0x80010000` decoding 16/16 slots of the モーグ/ギリー prologue. Correction: the `u16` table base is **per block** — the area script has no `W` header and its table starts at +0, so `*(u32 *)0x80010004` is not universal. Name-entry, config and item text live in the `0x80014000` pool, *not* the `.EMI` area script, so replacing only that section leaves menus Japanese. `tools/verify_msgtable.py` added. [`TEXT_ENGINE.md`](TEXT_ENGINE.md). |
| 2026-08-30 | **Savestate load found to wedge/crash the runtime.** TCP `savestate load` blocked the emu thread past 30 s, tripped the starvation watchdog into two ~100 MB freeze dumps, and killed the listener; the in-game **X** load path crashes the process. **Enter/Start loads work.** Recorded under Blockers → open, non-blocking. |
| 2026-08-30 | ~~**Reproducible crash isolated: unregistered overlays.**~~ **RETRACTED same day — the diagnosis was wrong.** See the retraction entry below. |
| 2026-08-30 | **Overlay crash diagnosis retracted.** The `interp_unsupported` record (`pc 0x801D0AA8`, `insn 0x00000000`, *instruction guard*) was read as a crash signature. It is not. A clean headless boot that never left the title screen, took no input and exited via `tcp_quit` produces the **identical** record, and `dirty_ram_unsupported` reports **`aborts: 0`** — the dirty-RAM interpreter probes that address once at boot, the guard rejects it, nothing aborts. Corroborating static evidence: the boot EXE contains **zero** JAL, J, lui/ori pairs or data words referencing the `0x801CE401`-`0x801D0C00` gap, and a seed (`0x801D0C04`) sits immediately past its end — so the gap is a zero-filled data/BSS region between code, not an overlay landing zone. `overlay_loader registered=0` is likewise expected: `[runtime] overlay_cache` defaults **off** and is a performance feature; overlay code runs via the dirty-RAM interpreter without it. **No crash artifact exists on disk** — both surviving run reports ended `atexit` via `tcp_quit` / `sdl_window_close`. |
| 2026-08-30 | **Freeze-dump disk cost noted.** Twelve automatic freeze dumps written in one afternoon, ~1.2 GB total in `build-dbg/` (gitignored, but they fill a disk fast). Each stall writes two ~100 MB JSON dumps. Worth capping or pruning between sessions. |
| 2026-08-30 | **The crashes are root-caused: the starvation watchdog, by design.** `starvation_ring.c` `exit(2)`s after 4 s without an emu-thread heartbeat (measured gap 4.027 s), which is why every report reads `reason: atexit` / `exit_origin: "unknown"` — `exit(2)` is untagged. Ruled out along the way: the save itself (`slot04` written complete, process lived 58 s more), SIO (~1,957 events/s is normal pad polling), a hard fault (no Windows Error Reporting record at all), and `psx_fatal_halt` (`fatal: None`). Override with `PSX_STARVATION_TIMEOUT_US=0`. Also found: two ~80 MB freeze dumps are written at *every* boot from a frame-328 watchdog false positive, ~160 MB per launch. |
| 2026-08-30 | **~90% of execution is interpreted — the seed list is the bottleneck.** Live measurement: 264.0 M interpreted instructions vs 28.0 M native dispatches (`dirty_ram_stats` / `dispatch_stats`, `miss_total: 0`, `aborts: 0`). `seeds/ghidra_funcs.txt` has 523 entries against 1,025 Ghidra functions, and all eight hot interpreted PCs sampled are missing from it; only 15 seeds are above `0x80190000` where the hot code sits. All are static-EXE addresses, so this is missed heuristics, not overlays. Unifies the day's symptoms: slow interpretation → boot freeze dumps + 4 s starvation `exit(2)`, and non-dispatchable PCs → `savestate_resume_pc_ok()` false → save refusals. |
| 2026-08-30 | **Save refusals explained.** `savestate_poll` defers 2 s then fails with `SAVE FAILED ... no safe resume PC` unless `psx_is_dispatchable(pc)` holds. Reproduced twice at one spot. The guard is correct behaviour — it refuses to write "a structurally valid but poisoned state" — so the fix is seed coverage, not the savestate code. |
| 2026-08-30 | **Submodule reset to the pin; regenerated and rebuilt.** `psxrecomp` had floated to `a91884a4`; reset to `f24b7e5d` (clean, one upstream commit, nothing local). Emitters already matched the pin. `build-dbg` rebuilt 199/199 after a reconfigure — note the generated shard count is captured at configure time, so a generate that changes the shard count needs `cmake -S . -B build-dbg ...` again or the link fails on undefined `func_*`. |
| 2026-08-30 | **Seed-list hypothesis tested and DISPROVEN.** Extending `seeds/ghidra_funcs.txt` from 523 to 868 (all `verified`/`high`/`medium` analyser functions it lacked) produced a **byte-identical generate** — same 35 shards, same 1467 dispatch entries — verified by running `psxrecomp-game` out-of-band against both seed files. The recompiler's own discovery already exceeds `functions.tsv`. Reverted to 523. `tools/export_seeds.py` kept for the record. |
| 2026-08-30 | **Interior-entry seeding works mechanically but is wrong here.** Adding 8 observed interior PCs raised dispatch 1467 → 1475 and made them dispatchable, staying clean under `strict`. Reverted anyway: those addresses are **zero in the EXE image**, so the emitted bodies are NOPs aliased into a zero-fill parent (`psx_alias_body_801D0C04`). Seeding code that is not in the image is fabrication, and it invites stale-registration bugs. The real answer is overlay capture. |
| 2026-08-30 | **Tools added:** `tools/harvest_interp_pcs.py` (reads `dirty_ram_stats`/`dispatch_stats` from a live run, reports the interpreted/native ratio and the proven interpreted entry PCs, writes `analysis/observed_interp_pcs.json`); `tools/export_seeds.py` (analyser → seeds merge, null result above). |
| 2026-08-30 | **Savestates survive a rebuild.** A slot written by the 09:26 build loaded correctly under the 19:45 rebuild (pin reset + regenerate + relink) and resumed at the expected spot. The open question in [`SAVESTATES.md`](SAVESTATES.md) is closed. Saving also works again on the rebuilt tree. |
| 2026-08-30 | **Save-failure mechanism pinned exactly.** Not the dispatchability of the resume PC as first thought, but `psx_irq_resume_context_snapshot_safe()` = `g_cosim_dirty_pump_site == 0`: an interrupt taken inside the dirty-RAM interpreter can never be snapshotted. Live sampling showed a steady 9.0-9.1% native / 91% interpreted mix, so the 2 s defer window routinely expires with no safe poll. Same root cause as the interpretation problem — overlay coverage. Second live profile captured to `analysis/observed_interp_pcs.json` (575 tracked PCs, 84.4% interpreted cumulative). |
| 2026-08-30 | **The zero-fill map: 81.6% of the text segment is runtime-loaded.** 1,187,899 of 1,456,128 bytes are zero in the image, in 11 runs >=2 KB from `0x80093801` to `0x801F6C00`; real static code is only ~268 KB. Confirms overlays dominate this title. Also quantified the contamination this causes: **18 of 523 seeds (3.4%) point at zero bytes** (all `low` confidence, plus the single `data` row), and **211 of 8,694 distinct dispatch addresses are zero-fill** — i.e. the runtime has 211 registered native entries whose bodies were compiled from nothing. Dirty-RAM invalidation masks them today; it is the OV-1 stale-registration risk. |
| 2026-08-30 | **Save failure is about the interrupt path, not the aggregate ratio.** Sampled live: native share *rose* from ~9% to ~18.6% while saves went from intermittent to consistently failing — so the overall mix does not predict it. What predicts it is where the interrupt lands: entries are at the BIOS vector `0x800000A0` and flow into game code at `0x801A1538`/`0x801A1720`/`0x801A19A8`, all of which are **zero-fill overlay addresses**. Every such interrupt sets `g_cosim_dirty_pump_site`, so no poll in the 2 s window is snapshot-safe. Refutes the "new areas are heavier on the interpreter" reading: overlay code is interpreted in *every* area, including ones where saves worked. |
| 2026-08-30 | **Play-session profile harvested; seeding formally ruled out.** 568 tracked PCs over a real session: **93.6% of interpreted instructions are overlay code** (zero in image), 4.2% BIOS/kernel, and just 2.2% static EXE — the last with **`entries = 0`**, meaning the interpreter never *enters* static code and there is no missing static entry point to seed. Overlay PCs touched span `0x801970B4`-`0x801DE098`. Written up in [`OVERLAYS.md`](OVERLAYS.md). |
