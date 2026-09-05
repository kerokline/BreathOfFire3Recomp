# Name map — making the recompiled code human-readable

**Status:** IN PROGRESS (last verified 2026-09-01)

The generated C is `func_XXXXXXXX` (boot EXE) and `<overlay>_func_XXXXXXXX`
(overlays) and is regenerated on every Axis-B pass, so it cannot carry names.
Names live in a **sidecar** that tooling re-applies, and a **browsable map**
renders the sidecar over the catalog. The long-term goal — generated C that
reads `Battle_Init(location, actor)` — is the framework's reserved
"friendly-name promotion" (`psxrecomp/docs/SYMBOLS.md`); this sidecar is the
input it will consume. Nothing here touches the submodules.

## Files

| File | What | Key |
|---|---|---|
| `names/overlays.toml` | alias / role / status / evidence per overlay | `md5` of the section bytes |
| `names/functions.toml` | name / args / ret / status / evidence per overlay function | (`overlay` md5, `pc`) |
| `names/areas.toml` | alias / status / evidence / sightings / shots per **area (place)** | area file + script-block md5 |
| `names/items.toml`, `abilities.toml`, `places.toml`, `characters.toml` | **id → name data tables** generated from the disc by `tools/text_tables.py` (never hand-edited; re-run `extract`) — see [`TEXT_TABLES.md`](TEXT_TABLES.md) | (category, id) / id; `[meta]` carries the section md5 |
| `names/plates.toml` | the **painted world-map name plates**: rectangle on the map's texture page + by-eye transcription + wiki English (`tools/plates.py` for the rectangles; the `jp` column is hand-read) | (world-map area, plate index) |
| `symbols.toml` | boot-EXE function names (framework `PSX_FN_*` path) | `pc` |
| `docs/subsystem_map.html` | generated map: bands → overlays → functions, boot EXE, search | — |

**Why md5, not PC.** Eleven bands share load addresses across 339 overlays. A
PC names a slot; (md5, pc) names a function. `analysis/overlay_catalog.json`
carries the same md5 as `content_md5`, so the join is exact and survives
re-extraction.

## Tools

```bash
python tools/name_map.py init      # merge new catalog overlays into names/overlays.toml (never overwrites hand edits)
python tools/name_map.py check     # md5s exist, statuses valid, alias implies status != unnamed
python tools/name_map.py stats     # coverage
python tools/subsystem_map.py      # regenerate docs/subsystem_map.html
```

The map is a pure offline join (catalog + captures + observed PCs +
functions.tsv/edges.json + names). It embeds **no overlay bytes and no
disassembly** — addresses, sizes, hashes, edge counts, names only — so it is
committable although `analysis/` is not. Regenerate it after `axis_b_loop.sh`
(the catalog changes) or after editing `names/`.

Serve it locally with `.claude/launch.json` → `docs-static`
(`python -m http.server 8765 -d docs`) or open the file directly.

## Status vocabulary

| status | meaning |
|---|---|
| `unnamed` | seeded, nobody has looked |
| `hypothesis` | name proposed from filename / directory / pattern; no runtime evidence |
| `evidence` | backed by a trace, a rendered string, a data-doc citation, or a documented finding |
| `verified` | evidence confirmed by a second independent route |

The `evidence` field says *how* — which trace, which string, which doc. An
alias without evidence stays `hypothesis`. This is the docs/README.md
evidence rule applied to names.

## What is named today (2026-09-05)

- **overlays, evidence with roles:** `LOGO.EXE`; `BATTLE.EMI#3` (battle
  game-mode); `BATL_END.EMI` (results screen); `SHOP.EMI#0` (shop / inn /
  save-point game-mode); the 5 KB memory-card manager module shipped in
  SHOP.EMI#8 and START.EMI; `START.EMI` (field main menu). Plus 25 area
  sightings from `area_poller.py`.
- **overlay functions:** 23 `evidence`, 23 `hypothesis` across BATTLE,
  GAME.EMI, SHOP, START, BATL_END and the card module: the battle command
  roots, the damage path (`Battle_ApplyDamage` -> `Battle_CalcDamage` ->
  `Battle_BaseDamage`), the HUD gauges, battle start/end record copies,
  `Char_LevelUp`, `Menu_EquipConfirm`, the results-screen tallies, and the
  save serialiser. See [`BATTLE_RAM.md`](BATTLE_RAM.md).
- **boot EXE (`symbols.toml`):** 14: `Rand`, `Zenny_Add/Sub`, `Inventory_Add/Remove`,
  `Char_RecalcStats`, `Stat_AddClamped`, `AbilityList_Add`, `AbilityList_ForType`, `Actor_Task`,
  `Actor_UpdateScreenPos`, `Actor_AnimTick`, `Flag_Test` (was `Save_FlagsChecksum` until
  2026-09-05), `BootEntry`.
- **Routes that produced them:** route 3 (differential traces) named the
  first twelve; route 4 (data anchors: `ramdiff` -> `capture --watch` ->
  decompile) named everything since and is the productive route. Route 2
  (Psy-Q signatures) is still unrun.

## Gathering evidence — savestates vs. live commands

Savestates are anchors, not data; the data comes from the debug server while
the game runs (`--debug-port 4370`, debug-tools build). Two tools:

- **During play:** `python tools/area_poller.py watch` polls every 0.5 s
  and, since 2026-09-02, also unions the runtime's interpreted-PC table into
  `analysis/observed_interp_pcs.json` every 15 min and on Ctrl-C
  (`--harvest-every MIN`, 0 disables) so a session that dies before the
  end-of-run harvest keeps its coverage. It
  identifies the resident area with certainty by hashing the script block at
  `0x80010000` (every AREA file has exactly one such section; md5 from
  `emi_sections.json`), takes a screenshot to `analysis/area_shots/` on each
  change so the on-screen location can be read back, and drains the runtime's
  overlay native ring (body CRC + frame) incrementally. Output:
  `analysis/area_timeline.jsonl`, append-only. It reads `names/areas.toml`
  first: an area that already has an alias is logged as `AREA001 = Dauna
  Mines - Outside Entrance` and **not screenshotted again** (`--shots-always`
  overrides). An unnamed area is shot, then the poller **pauses and asks for
  the name** you can see on screen; a non-empty answer lands in
  `names/areas.toml` immediately (`status = "evidence"`, the shot as
  evidence) and as a `named` row in the timeline. Enter skips; `--no-prompt`
  (or a non-terminal stdin) disables the pause. The game keeps running
  while the poller waits.
- **End of session:** `axis_b_loop.sh` phase 2a runs `area_poller.py harvest`
  (also in `--harvest-only`): one snapshot of the resident area plus the whole
  native ring (16 384 most recent activations). It cannot recover areas walked
  through earlier once the ring wrapped; that is what `watch` is for.
- **Offline:** `area_poller.py summarize --apply` upserts every sighted area
  into `names/areas.toml` (sightings and shots merge; alias/status/evidence
  are never overwritten) and stamps the sighting as `evidence` on any *code*
  overlay of that file in `names/overlays.toml`. **An area is a place, not an
  overlay**: 10 of the first 15 sighted areas ship no code section at all
  (only data, assets, and a "mixed" section the extractor skips by default),
  so they have no overlay entry to carry a name. That is why areas get their
  own sidecar. Alias and status stay for a human: read the shot, type the
  alias, set `status = "evidence"`. The map lists them under "Areas sighted".
- `axis_b_loop.sh` phase 6 (every non-harvest-only path, including
  `--skip-harvest`) then re-merges `names/` and regenerates the map.

Savestates earn their keep for **differential** questions (Attack vs Defend):
two runs must start identical. The interpreter caller ring logs interpreted
transfers only, but the runtime's `overlay_native_ring` is a **per-call native
trace** (entry address, body CRC, frame; 16 384 slots, always on, in
`overlay_loader.c`). It fills in well under a second when hot, so it is a
window, not a history: the poller compresses it to one row per overlay body
per area with a call count and the entry addresses seen. A differential tracer
can drain it right after an input; that is now a tool, not a framework change.

First live run (2026-09-01): six WORLD00 areas identified with certainty
(AREA001/002/006/009/024/031) in one walk. Lesson paid for: the script block
lands during the fade, so a screenshot at the change instant is black — the
poller now shoots `--shot-delay` seconds later (default 4) once the area has
settled. The native ring came back empty on that run because the response is
nested under `ring`; fixed.

## How names get earned — the routes, in the order to run them

1. **Resident script block + screenshot → area aliases.** `area_poller.py
   watch` (above). The always-on string capture ring described in
   `STRING_TRANSLATION.md` is **not in the current code** (LOCALIZATION.md §1),
   so the banner is read from the screenshot, not from a string log. Offline
   cross-check: the per-EMI dialogue corpus in `D:\BoFIII\_claude_work` names
   speakers and places per section.
2. **Psy-Q signatures → boot-EXE library names.** The boot EXE links libgpu /
   libspu / libcd. FLIRT-style byte signatures name hundreds of functions at
   once and expose which game functions are thin wrappers. Lands in
   `symbols.toml` via the Ghidra round-trip (`ghidra-mcp` is connected).
3. **Differential traces → behavior classes.** "Does Attack always enter the
   same way": load the battle-menu savestate, press Attack, record the entry
   sequence from the caller ring; reload, press Defend, record again; the set
   difference is the Attack path. Intersect the first N entries across five
   battles for `Battle_Init`. The ring/args/frame data `enrich_pcs.py` reads
   is sufficient; the tool is not written yet.
4. **Data anchors.** Functions writing documented RAM structures (party
   stats, inventory — community data doc) name themselves by effect.
5. **Message-table anchors.** Functions referencing a message index whose
   decoded string is a menu label are that menu's handler (`verify_msgtable.py`).

Then cluster: community detection over in-overlay jal edges + ring callers
gives subsystems; name twenty clusters before a thousand functions (the
HANDOFF §1b endgame).

## Traps

- **Heat attribution.** Per-function `interp insns` in the map is populated
  only for single-occupant bands. In a mixed band (`0x801D0C00`,
  `0x801F2C00`, `0x801EEC00`, `0x800C1800`) a PC cannot be attributed to an
  occupant offline — the map says "band-shared" rather than guess. The
  durable fix is the tier-1 resident-CRC runtime capture (HANDOFF §1b).
- **Span is an upper bound.** A function's `span` runs to the next discovered
  root, so a root followed by a data blob (e.g. `0x801DCD40` in LOGO, span
  59 KB) absorbs the blob's observed PCs. Treat a huge span with heat as
  "undiscovered roots or data in here", not as a hot function.
- **Edges are in-overlay `jal` only.** Calls into the boot EXE, other bands,
  and function-pointer dispatch are invisible; see
  `harvest_logo_handlers.py` for the `jalr`-table case.
- **`symbols.toml` keeps its own status words** (`guessed`, …) — the map
  shows them as-is; `name_map.py check` validates only `names/`.
