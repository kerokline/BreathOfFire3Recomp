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
| [`LOADER_RECORDS.md`](LOADER_RECORDS.md) | evidence + built | **The engine's own entry records for every overlay family** (2026-09-12): AREA descriptors off the boot table `0x801802EC`, SCENARIO vtables off `0x801C944C`, `Boss_EntryTable 0x800B2048`, the PLCHAR combo tables — all read off the disc, all disjoint from the header entry runs, seeded by `tools/loader_records.py` → `names/*_records.toml` → `extract_overlays.py`. Raw reports per family in [`loader_records/`](loader_records/) |
| [`OVERLAY_SIZE.md`](OVERLAY_SIZE.md) | evidence | *Why `generated/` is 1.6 GB*: per-band expansion measurements; falsifies occupants-per-band as the cause, identifies interior-entry fragmentation, and gives the dedup estimate |
| [`WALK_ROOTS_HANDOFF.md`](WALK_ROOTS_HANDOFF.md) | reference (cross-title) | **For other psxrecomp titles hitting psxrecomp#380** (runtime captures carry no function entries, so CPS images get no walk roots and fragment into islands): the `static_discovery_entry_pcs` capture field the compiler already consumes, our six root sources as portable algorithms (JAL targets, post-return prologues, in-image pointer tables with the CFG proof, header runs, the engine's loader records, harvested entries), the traps, a 20-line enrichment recipe over a runtime `overlay_captures.json`, and the three upstream asks |
| [`BRINGUP.md`](BRINGUP.md) | log | Boot 001/002 (first boot, the retracted "wait loop"), and framework observations F-1 / F-2 |
| [`TEXT_ENGINE.md`](TEXT_ENGINE.md) | evidence | The message interpreter, renderer, glyph path, control codes, and the per-block message-table formula confirmed live |
| [`GFX_PACKETS.md`](GFX_PACKETS.md) | evidence | **`Packet_Commit` `0x8014E494`** (2026-09-17): the per-frame packet arena (two 36 KB buffers, cursor `0x80145988`), the eight OT layers and their draw order, the silent-drop overflow rule, and `Main_FrameLoop` / `Packet_FrameReset` / `Packet_FlushToOT` around it — the function the furigana plugin hooks |
| [`SOUND_CUES.md`](SOUND_CUES.md) | evidence | **`SE_Play` `0x8015E908`** (2026-09-17): the cue word (`bank<<8 \| id`, `0x8000` keeps volume), the seven bank handlers and their 31-entry cue tables (zero on disc, decoded live from three savestates), priority/voice arbitration on SPU voices 16..23, the distance wrappers, and `SoundSet_Layout`. Left: hear one |
| [`LOCALIZATION.md`](LOCALIZATION.md) | plan + evidence | JP→EN: the capture-pipeline findings (F-3 / F-4), the `.EMI` container format, the `0x80010000` selector, prior decode work at `D:\BoFIII` |
| [`LOCALIZATION_APPLY.md`](LOCALIZATION_APPLY.md) | evidence + build | **The apply path, verified on screen 2026-09-09**: the framework function-entry plugin at `MsgBox_Reset`, the US-disc slot-for-slot English table (`tools/build_script_xlate.py` to `generated/bof3_xlate_en.c`, never committed), the US byte table, the `0x14` choice layout, the 192 px / 16-cell box, the build recipe and the open items (lowercase, apostrophe, per-area conflicts) |
| [`regional-builds.md`](regional-builds.md) | evidence | JP/US/EN/FR/DE comparison: no runtime language support, no address-compatible donor, the full section census, the four text locations and 37 language-bearing images |
| [`PC_PORT_CROSS_REFERENCE.md`](PC_PORT_CROSS_REFERENCE.md) | reference (external) | **The 2001 Chinese PC port and the `bof3ext` hook project as a second opinion** (2026-09-18): what kinship is provable (the 164-byte character record, the area-number byte, the box re-point), their independently derived control-code table against ours and the two `TEXT_ENGINE.md` rows it flushed out (`0x10`/`0x11` instant print, `0x0C` not head-only), their struct field names for bytes we call gaps, and what does *not* transfer — the repacked `.DAT` containers, the Chinese script, the DirectDraw-era rendering. Local clone only, **no `LICENSE`** |
| [`MEDNAFEN.md`](MEDNAFEN.md) | reference | Stock Mednafen in `./mednafen/` as an isolated oracle: what crosses over (memcards yes, savestates no), the card naming, and driving it with `tools/mednafen_ctl.py` |
| [`SAVE_IMPORT.md`](SAVE_IMPORT.md) | evidence | US `SLUS-00422` and JP `SLPS-00990` write the **same save block**: the checksum rule/offset match and 43 of 46 `save_tool verify` cross-checks against the JP `.EMI` tables pass on a US save, so item/ability/equipment ids are shared. Only the card directory filename needs rewriting — `tools/save_import.py`. Gets late-game areas onto card 2 without playing there |
| [`SAVESTATES.md`](SAVESTATES.md) | index | What each savestate slot holds; the in-game-vs-file off-by-one |
| [`INSERT_RUBY.md`](INSERT_RUBY.md) | built + evidence | Readings on names the box *inserts* (`<07>` item / skill records at `0x801490D4 + 0x20·nn`): the stepper mechanics from the decompile, every record-0 writer from the GAME.EMI disassembly (filled before the open, no leading byte), the second generated table `generated/bof3_insert_<code>.c`, the plugin write-back into the scratch record, the 16-cell budget and the narration-check trap it set, and the live synthetic pickup that drew 薬草（やくそう） (2026-09-10). Left: a real pickup and a skill line in play |
| [`NAME_MAP.md`](NAME_MAP.md) | plan + evidence | The readability track: `names/` sidecars (overlays / functions / areas), the status+evidence rule, the area poller, routes to earn names |
| [`TEXT_TABLES.md`](TEXT_TABLES.md) | evidence | Id→name tables read straight from the `.EMI`: the five item tables, abilities, the MTEST place list (= AREA numbers, joined to each area's kanji caption), the roster; the encoding facts the names taught; the save cross-checks that prove weapon/armour power and ability type; **the world-map place names as painted texture plates** (format, `tools/plates.py`, `names/plates.toml`, the text-swap constraints); `tools/text_tables.py` → `names/items.toml` etc. |
| [`FURIGANA.md`](FURIGANA.md) | built + evidence | **Japanese (Furigana)**, the third selectable script (`jp_furigana`: readings in an 8 px row above the kanji from the game's own small font, shipped 2026-09-12; the inline `jp_ruby` it replaced was built 2026-09-09): the rendering route and its four on-screen proofs, the 8 px font, and the inline variant's history — the 15-glyph box line, what annotating costs in rows over all 3,793 confirm pages, the re-authoring rules, the byte budget against the 16 KiB window, and the next session's build order — `tools/ruby_fit.py` |
| [`STEAL.md`](STEAL.md) | evidence + built | **The steal roll** (2026-09-13): Pilfer/Steal roll inside their own BMAGIC overlays (MAGIC065/MAGIC216 at `0x801EEC00`), `rand byte < rate[drop class] × agility mod`, matches the wiki table; the stolen item is drop slot 1 and is cleared on success. The `bof3.steal-always` mod package (two guarded `disc_user` patches), its 6/6 vs 0/22 proof, `tools/steal_hunt.py`, and the abilities/magic name-shift trap |
| [`EXP_BOOST.md`](EXP_BOOST.md) | built | **EXP / zenny multiplier sliders** (2026-09-13): the first trusted static plugin (`src/bof3_exp_boost.c`), three BATL_END hook PCs (`BattleResult_Setup` / `ExpTick` / `ZennyTick`) scaling the battle totals once at the results screen; why a byte patch could not do it, the fire-whether-enabled and shared-band traps, the build order and the proof recipe |
| [`WORLD_ITEMS.md`](WORLD_ITEMS.md) | evidence | The searchable spots (dressers, pots, ground): the 8-byte record, the `0x80145000` world-item flag array and its `Flag_Set`/`Clear`/`Toggle` family, and the boot-EXE table `0x801802EC` that makes the whole placement readable off the disc — `tools/world_items.py`, 517 records over 200 areas (98 items, 24 zenny caches, 6 640z) |
| [`AREA_PCS.md`](AREA_PCS.md) | evidence | Per-area PCs in the `0x801F2C00` world band: the constant search path, the per-occupant entry-PC census that turns `band-shared(181)` into a membership test (317 of its 1,058 distinct addresses are claimed by 2+ areas, one by 18), and the 75 entered PCs with no static root — `tools/area_pcs.py`, 181/181 agreement with the overlay catalog |
| [`DATA_ISLANDS.md`](DATA_ISLANDS.md) | evidence | What the compile's "data walked as code" rejections are: tables and strings that share an address with a sibling occupant's function (boss handler tables, the results-screen printf formats, the save-file name template, the staff roll), the memo-to-occupant join rule and its walk tiebreaker, and the whole-memo classification. **Corrected 2026-09-08: the "23 real-code gaps" were a classifier artifact; confirmed gaps are 0** — `tools/data_islands.py`, `names/data.toml`, loop phase 5a' |
| [`EMI_TYPES.md`](EMI_TYPES.md) | evidence | The `.EMI` section-type census over the JP disc (6,344 sections): the two types the community doc does not name — **type 8** (audio bank companion, whose `+0x04` is a bank id, not a RAM pointer) and **type 1** (character payload at `0x80033800`) — plus why the type id rules assets out but cannot separate code from data |
| [`OVERLAY_HEADERS.md`](OVERLAY_HEADERS.md) | evidence | Every overlay opens with a **registry id** (unique across all 405 compiled EMI overlays, `0x010..0x1BF`, zero duplicates) and a variable-length entry-pointer table. Explains the `0x801EEC10` "data pad"; the ability→overlay link is still open |
| [`subsystem_map.html`](subsystem_map.html) | generated | Browsable map (bands → overlays → functions, boot EXE, areas). Regenerate with `tools/subsystem_map.py`; never hand-edit |
| [`loader_records/`](loader_records/) + `tools/warp.py`, `tools/warp_gap.py` | built | **Headless area sweep**: warp through all 200 AREA overlays from one field savestate in ~8 min, harvest, and classify every residual interpreted pc against its own room's image. The proof loop for `LOADER_RECORDS.md` and the new Axis B stop condition |
| [`ADDRESS_MAPS.md`](ADDRESS_MAPS.md) | reference | **How to resolve a raw address.** The two maps added 2026-09-12 — `names/regions.toml` (spans: the eleven overlay bands, the two message pools, the insert scratch array, the EXE image, the kernel area) and [`XREF.md`](XREF.md) (prose → the naming layer) — with the region table, the source of every field, the three rules for reading a bound, and the range-convention trap that cost two wrong ends. Read this before quoting a region `end` |
| [`XREF.md`](XREF.md) | generated | Every `0x80xxxxxx` address cited in these documents, joined to what the naming layer claims about it (`symbols.toml` boot symbols, `names/functions.toml` overlay functions, `names/data.toml` islands, the probe's layout landmarks), plus which documents cite it. Answers "is this address named, and who else discussed it" without a grep. Regenerate with `tools/xref.py index --out docs/XREF.md`; never hand-edit |
| [`IDEAS.md`](IDEAS.md) | intake | Proposed improvements with feasibility: combat call-stack mapping (I1), programmatic area labels from map text (I2), 1.5x dialogue box + furigana (I3), name tables straight from the `.EMI` (I4, done 2026-09-05 → [`TEXT_TABLES.md`](TEXT_TABLES.md)) |
| [`ENHANCEMENTS.md`](ENHANCEMENTS.md) | plan | Post-faithfulness work: scanlines (shipped upstream), pause/frame-advance (designed), costed backlog |
| [`vblank-pacing-bug.md`](vblank-pacing-bug.md) | investigation | The Capcom FMV slowdown: root cause (SPU snapshot gate), fix, and the two wrong theses |
| [`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md) | investigation | One unreproduced fail-fast into kernel RAM on a savestate resume |
| [`upstream-kernel-bless-plan.md`](upstream-kernel-bless-plan.md) | plan | **Next big compile target.** The psxrecomp PRs that let the patched exception handler run native: slots published to the bless verifier, range slots with ROM-word compare, declared slots for both profiles, re-measure here |
| [`computed-stride-jump.md`](computed-stride-jump.md) | investigation (fixed) | **The last non-kernel residual, done 2026-09-17.** The decompressor's unrolled byte copy entered mid-body by a computed `jr` (Duff's device) had no native entry, so every load interpreted it; live RAM equals the disc image (not dirty text); the emitter's new `resolve_computed_stride_jump` (fork branch `feat/computed-stride-jump`) switches on the runtime target like a jump table; 684,626 → 0 interpreted instructions over twenty headless area loads |
| [`frameless-dispatch-roots.md`](frameless-dispatch-roots.md) | investigation (fixed) | **The all-bands compile exits 0, done 2026-09-18.** The `[audit]` shard failures were never a drift: all 27 were one predicate — a band-shared dispatch entry admitted as a walk root by the weak "a `jr $ra` two words back" arm of `_callable_legacy_seed`, landing on the pointer table / packed record array / zero fill that follows the image's last function, walked to the image end. Prologue-less dispatch entries now need `plausible_callable_target`, the probe the discovery roots already use (fork branch `fix/frameless-dispatch-root-cfg-proof`); 41 rejections in 5,339 roots, all data by inspection, zero fragment demands lost, `failed=27` → `failed=0` |
| [`vector-stub-shapes.md`](vector-stub-shapes.md) | investigation (fixed) | **Plan step 5, done 2026-09-17.** The A0/B0/C0 call vectors interpreted on OpenBIOS only because the emitted native-stub guard knew the retail stub shape (`lui/addiu/jr/nop`) and not OpenBIOS's (`addiu $t0,$zero/jr/nop/nop`); live bytes, the game's ~230 `ChangeTh` yields per frame, the two-shape guard on fork branch `feat/openbios-vector-stub-shape`, vectors 459 → 0 per frame, wall clock unproven |
| [`kernel-patch-sites.md`](kernel-patch-sites.md) | investigation | **MEASURED 2026-09-11.** 44.6 % of interpreted work is the BIOS exception handler, unblessed by the Psy-Q kernel patches on OpenBIOS *and* retail v2.2 (where the declared 0xCF0 slot is hit and still does not help); the patch sites and the upstream asks |
| [`zero-fill-dispatch-audit.md`](zero-fill-dispatch-audit.md) | investigation | **DONE 2026-09-06.** The 211 zero-fill dispatch entries audited: 182 are now real overlay code, the guard is sound, no live bug; the entry-word metric misclassifies 64 NOP delay slots |
| [`band-overlap-attribution.md`](band-overlap-attribution.md) | investigation | **DONE 2026-09-06.** Overlay bands share RAM: the Capcom logo band has 0.9% exclusive address space, so it could never be credited a PC. Binning made deterministic; the residual limit needs residency, not addresses |
| [`battle-icon-strip-rows.md`](battle-icon-strip-rows.md) | investigation | **RESOLVED 2026-09-06.** Enlarged command icon lost its top six texture rows; VRAM vs disc vs Beetle oracle traced it to the GP0 polyline terminator bug, fixed upstream and confirmed by player retest |
| [`battle-depth-order.md`](battle-depth-order.md) | investigation | Sprites lunging behind the battle doorway: list order honoured, Beetle shows the same, game behaviour |
| [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md) | investigation + proposal | build-dbg "crashes" were the starvation watchdog exiting on a cross-thread clock race and reporting itself as `atexit`; evidence, upstream diff, verification plan |
| [`pr302-dma2-ot-cost-review.md`](pr302-dma2-ot-cost-review.md) | review + evidence | Cross-title check of upstream psxrecomp #302 (DMA2 linked-list cost 8+5 → 1+0): BoF3 A/B census, no regression, plus the hardware argument the PR is missing |
| [`gpu-polyline-terminator.md`](gpu-polyline-terminator.md) | investigation (resolved) | Ground plane vanishing after the herb effect: GP0 shaded-polyline terminator tested on colour words, a junk-byte colour matched, the de-phased stream produced a 341×341 FILL over the terrain texture; hardware rule from Beetle + DuckStation, framework fix |
| [`remote-plan-2026-09-05.md`](remote-plan-2026-09-05.md) | plan | Six-track plan for the 2026-09-05 morning run remotely: base-damage decompile, `Battle_Init`, battle command venn + victory, Capcom-intro sampling, save-file verifier, housekeeping; outcomes table at the end |

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
