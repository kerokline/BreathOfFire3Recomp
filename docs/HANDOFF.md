# Handoff — next session

**Status:** IN PROGRESS (rewritten 2026-09-01 night after the framework pin
returned to upstream master; section 0 added 2026-09-05 after the data-anchor
weekend; refreshed 2026-09-11 after the kernel fix — **the next target is a
play session, see the paragraph below**; the dated banner history this file
used to carry is in the [`STATUS.md`](STATUS.md) Log)

Read [`STATUS.md`](STATUS.md) for where the project stands. This file is what
to pick up, how to build against the current pin, and the traps already paid
for. It points at evidence rather than restating it.

## Where things stand in one paragraph

The game **plays at 60 fps** on `build-relprof` (Capcom logo, world map,
memory-card screens all user-verified 2026-09-01 with clean audio). All ten
overlay bands plus `LOGO/LOGO.EXE` are compiled from the disc and dispatch
~99% native. The Axis B loop now takes **90 s** instead of ~16 min (parallel
static compile + split translation units, merged upstream as
mstan/psxrecomp#296; `psxrecomp` is pinned to `ed55299b` plus our open
[#346](https://github.com/RetroPortingToolKit/psxrecomp/pull/346));
`recomp-ui` waits on one launcher PR (#48). The text engine is identified and
confirmed live. A **readability track** is open: `names/` sidecars
(overlays, functions, areas), `tools/area_poller.py` (which area is resident,
with certainty, plus screenshots), and the browsable
`docs/subsystem_map.html` — 15 areas sighted, 5 aliased.

**The single most valuable thing anyone can do next is play new content on
`build-relprof` and run the Axis B loop.** With the kernel retired (below), the
game-text + overlay region is the whole remaining interpreted cost — 1.54 G
instructions across 2 911 PCs — and the harvest behind it turns out to be far
thinner than its session count suggested: `pc_coverage.py --merge-duplicates`
puts every band between **3.3 % and 18.8 %**, with `0x80117000` (Research
Plant) never sampled at all. 11 of the 14 recorded session ids are provable
subsets of `20260904T093558`, i.e. re-harvests of one running process rather
than new coverage, so Axis B has had no genuinely new content since
2026-09-04. Worst-covered first: Research Plant, BOSS (3.3 %), the field/map
core (4.7 %), PLCHAR (9.0 %), BATTLE+ETC+SCENARIO (11.4 %). Everything after
the harvest is mechanical — §1 below. Also left: naming areas off their
screenshots, the tier-1/2 runtime enrichment, per-occupant fragment demands
(would cut `generated/` 1.6 GB → ~400 MB), and the translation reading review.

**2026-09-16:** the "3.3 % to 18.8 %" and "11 of 14 session ids are subsets"
claims in the paragraph above were a bug in `pc_coverage.py`'s subset
detector (union-find bridged through zero-gain sessions) and are withdrawn;
the boss session it discounted holds 29 exclusive PCs. Coverage is retired
as the Axis B headline — read **interpreted instructions per frame** from
`tools/interp_rate.py` instead (long walks: 290–390, 0.05–0.07 % of the
guest, all kernel trampolines + owned boot-EXE text). STATUS.md → *Next up 1*.
**2026-09-12:** the premise of the paragraph above changed. Play was never
finding anything the disc does not hold: every overlay family's entry points
live in engine records — the AREA descriptor table `0x801802EC`, the SCENARIO
vtable table `0x801C944C`, `Boss_EntryTable 0x800B2048`, the PLCHAR tables
`0x801CD8F0`/`0x801CD964` — all proven statically and seeded by default
(`tools/loader_records.py` → `names/*_records.toml` → `extract_overlays.py`;
914 entries no session had seen, static-dispatch entries 594 → 1,229, audit
set unchanged). What play still supplies is **proof and weight**: the next
session on `build-relprof` should visit an unplayed area, a boss and a party
change and read what `harvest_interp_pcs.py` still reports.
[`LOADER_RECORDS.md`](LOADER_RECORDS.md). **Same evening:** the AREA half of
that proof is done without play — `tools/warp.py` visits all 200 areas from
the slot-5 field anchor in ~8 min, `tools/warp_gap.py` explains what is left,
and the last static gap (in-image code-pointer runs) is now a default seed
source; on the 15:30 build the sweep reads **0 unseeded** across all 200 areas.
Re-anchor slot 5 after any regenerate (the hash stales every `.pst`).
**2026-09-11:** the largest remaining interpreted sink was not an overlay band
at all but the BIOS exception handler (44.6 % of interpreted work, both
BIOSes). **Fixed the same day** and open upstream as
[psxrecomp#346](https://github.com/RetroPortingToolKit/psxrecomp/pull/346)
(branch `feat/kernel-install-slot-ranges`, `baca0a8a`): kernel interpreted work
is down 87.6 % on OpenBIOS and 97.8 % on retail, `kernel_bless.mismatch` is 0
on both images and on both titles measured (Mega Man X6 too),
and the card read trace is byte-identical across the A/B. Evidence and the two
traps in [`kernel-patch-sites.md`](kernel-patch-sites.md) → *The fix and what
it bought*; the plan it came from is
[`upstream-kernel-bless-plan.md`](upstream-kernel-bless-plan.md). Remaining on
that track: land the PR, then bump the pin to the merged commit. What is left
interpreting in kernel RAM afterwards is the A0/B0/C0 vector trampolines —
180 M instructions over **90 M entries**, so ~2 each: per-call dispatch
overhead, not instruction count. That is plan step 5, it is excluded by the
profile on purpose (rule 18), and it is a smaller and riskier prize than the
overlay region. Discuss before touching, and not before the Axis B round. The
A0/B0/C0 vector trampolines are untouched by design and are now 87 % of what
OpenBIOS kernel RAM still interprets — the next lever if one is needed.
**2026-09-17: pulled.** They were not untouched by design — the generated
dispatch already had a native path for the vectors whose byte guard knew
only the retail stub shape; OpenBIOS's shape now matches too
([`vector-stub-shapes.md`](vector-stub-shapes.md), fork branch
`feat/openbios-vector-stub-shape`, vectors 459 → 0 per frame headless).
The kernel residual is now the declared patch ranges only.
**2026-09-09:** the text encoding is fully readable *and writable* — the
single-byte half was read off the font sheet (`tools/font_sheet.py` →
[`names/font.toml`](../names/font.toml)) and 100% of the area scripts' glyph
cells now decode — so the next deliverable is the **Japanese (Ruby)** script
variant, costed end to end in [`FURIGANA.md`](FURIGANA.md) (section 3 below).
**2026-09-05:** a second track produced most of the names so far: the
data-anchor loop (section 0 below) decoded the damage formula, level-up,
inventory, equipment and the save format in one weekend, with the RAM map in
[`BATTLE_RAM.md`](BATTLE_RAM.md); the morning of 2026-09-05 added the turn
order, the command menus, escape, the enemy AI tables, the results tally and
the effect applier (~70 names, most at `evidence`). **2026-09-05 evening:**
the game's own data tables are readable off the disc — items (five tables),
abilities, the 200-entry place list (= AREA numbers) and the roster are in
`names/*.toml` with English where the wiki has it, `save_tool.py` prints
names and proves weapon/armour power against the saves, and the world-map
place names turned out to be **painted plates** in the map textures, now
decoded and transcribed (`tools/plates.py`, `names/plates.toml`,
[`TEXT_TABLES.md`](TEXT_TABLES.md)).

## Start here

### 0. The data-anchor loop — where the names now come from (2026-09-05)

The weekend of 2026-09-04/05 replaced "differential traces name a function"
with a loop that names a function *and* the RAM it touches, and it ran
eleven times without a miss. Read [`BATTLE_RAM.md`](BATTLE_RAM.md) first: it
holds the party actor object, the persistent character records (base and
stride proven by code), the level table, inventory, zenny, the HUD, and
the complete save-file format. Then [`GHIDRA.md`](GHIDRA.md) for the
headless driver. The loop:

1. `callstack_diff.py ramdiff` around one action; type the numbers you saw
   on screen afterwards (`ramfilter --intersect FILE=n,n` across rounds).
2. `capture --watch LO-HI` on the cell(s); `writes` names the store PCs.
3. `ghidra_run.py export --decompile PC` (import the overlay first if new;
   `--start` seeds a gap the static walk missed).
4. `name PC Name --status evidence` when trace and body agree; document the
   RAM in BATTLE_RAM.md.

**Highest-value targets left, in order:**

| # | Target | Why it pays | How |
|---|---|---|---|
| 1 | ~~`Battle_BaseDamage` + the two defence steps~~ **DONE 2026-09-05** — full formula + ATK/DEF/hit/evade fields in BATTLE_RAM.md; the "defence steps" were to-hit rolls | ~~remaining: elemental affinity `0x8009FA78`~~ **DONE 2026-09-18** — the resistance grid is species `+0xC0..+0xC4` into the percent table `0x800B187C`; BATTLE_RAM.md *The resistance grid*. The grid is nine bytes `+0xC0..+0xC8` = fire / ice / lightning / earth / wind / holy / psionic / status / death, against three different percent tables; bit order proven from the weapon table (`+0x0B`). Left: the ability -> effect-handler index mapping, which is where a spell's element lives | (was already decompiled in `analysis/ghidra/BATTLE_EMI15_80093800_decomp/`) |
| 2 | ~~`Battle_Init` `0x801D1228` to evidence~~ **DONE 2026-09-05** — all 33 traced offsets explained (effective-stat snapshot + `Formation_ApplyStatMods`, low-HP bit, resets) | left: boot helpers `0x8014E294`, `0x801629CC` unnamed | — |
| 3 | ~~Enemy record layout~~ **DONE 2026-09-05** — `+0x04` zenny, `+0x06` EXP, `+0x08` level, `+0x18..+0x1F` drop slots, `+0x28` AGI, `+0x60` AI script, obj `+0xE1` AI row mask | left: `+0x2A`, the AI row semantics | BATTLE_RAM.md enemy table |
| 4 | ~~Item drop + EXP yield~~ **DONE 2026-09-05** — `Battle_EnemyDefeated` → `Battle_RollDrops` → BATL_END `BattleResult_Setup` / `_ExpTick` / `_ZennyTick` / `_AwardDrops` | left: a battle where a drop actually lands (`AwardDrops` is body-only) | `--watch 0x80146320-0x80146360` on a kill |
| 5 | ~~Magic / Item / Run command paths~~ **DONE 2026-09-05** — command byte `C+0x119` (+target `+0x118`, parameter `+0x11A`), engine-band menus, `Escape_Roll`/`Escape_Chance`, `Effect_ApplyResult` and its handler table `0x800B165C` | left: per-skill/item handler indices (user: read directly later), Defend confirm body (Ghidra gap `0x801D2520`) | engine band needs `--lo 0x80093800 --hi 0x801D0C00` and ≤ ~130-frame windows |
| 6 | ~~Roster order~~ **DONE 2026-09-05** — read off the record name bytes in the card saves (`save_tool.py dump`): 0 リュウ, 1 ニーナ, 2 ガーランド, 3 ティーポ, 4 レイ, 5 モモ, 6 ペコロス, 7 パピー = the intro's baby dragon (char id 10; proven live on `slot01`: roster byte 7, write-back into record 7); char id = roster for 0..6, ids 7/8/9/14 are alternate forms via table `0x80182488` (9 = the lone boy Ryu of save 1) | left: which forms 7, 8, 14 are | — |
| 7 | ~~Dialogue engine anchors~~ **DONE 2026-09-05** — `capture --watch 0x801490A4-0x801490B0` on an NPC talk (`slot04`, `npc_talk.json`): GAME.EMI `Script_ShowMessage` → boot `Msg_OpenScript(idx)` / `Msg_OpenSystem(id)` are the only box-string *openers* (**corrected 2026-09-11:** `MsgBox_Replay` `0x801515F8` re-points the box without a reset — see TEXT_ENGINE.md); 13 text-engine functions named `confirmed` in `symbols.toml`, control codes `0x02/0x0A/0x0C/0x0F/0x10/0x14` read, box frame drawer found. TEXT_ENGINE.md "The resolver" | left: the hook *shape* — the pointer is never a dispatch arg, so the framework's a0..a3 hook can't see it (in-place patch needs a BoF3 encoding profile upstream, or repoint at `MsgBox_Reset`) | — |
| 8 | ~~Psy-Q signatures on the boot EXE~~ **DONE 2026-09-05** — `tools/psyq_sigs.py` against lab313ru/psx_psyq_signatures (sibling checkout): SDK 3.70, 246 objects, **500 names** appended to `symbols.toml` (libgpu 101, libsnd 121, libgte 63, libcd 53, libspu 45, libetc 29, libapi thunks incl. `open`/`read`/`write`/`firstfile`). No Ghidra needed | `0x8014E494` = `Packet_Commit` and `0x8015E908` = `SE_Play` named 2026-09-17 (GFX_PACKETS.md, SOUND_CUES.md); the `0x8017F7B0` file-API range is the `open`/`lseek`/`read`/`write`/`close`/`firstfile`/`nextfile` thunk block. Names are pushed into the Ghidra boot program with `ghidra_run.py names` | — |
| 10 | ~~Name tables from the `.EMI`~~ **DONE 2026-09-05** — `tools/text_tables.py extract` → `names/items.toml` (consumables 92 / key 16 / weapons 83 / armour 68 / accessories 52, five tables with five strides), `abilities.toml` (227, `type = b1 & 3`), `places.toml` (200 MTEST entries = AREA000..199, joined to each area's kanji entry banner and dev label, 45 with English), `characters.toml`; `save_tool.py` prints names and `verify` proves ability types and weapon ATK / armour DEF against the saves | left: the `ref` index, accessory effect codes, the ability param bytes, masters (a message block, not a table), promoting places into `areas.toml` | [`TEXT_TABLES.md`](TEXT_TABLES.md) |
| 9 | ~~Save verifier script~~ **DONE 2026-09-05** — `tools/save_tool.py`; card1's three saves verify and match the Mednafen load screen; three RAM-map corrections (`Flag_Test`, play time `0x80144FBC`, four ability lists); names since row 10 | left: the `0x8014686C..` words at the block head, record `+0x84` | `python tools/save_tool.py verify saves/card1.mcd` |

**Trap paid for 2026-09-05 (GHIDRA.md → Traps):** every overlay decompile
was silently truncated at the first call into the boot EXE — `Rand` is a
BIOS thunk (`jr` to `0xA0`) that Ghidra marked no-return. Fixed in the
seeder (boot EXE mapped into each overlay program, thunks made returning);
**re-import any program from before 2026-09-05 08:40 with `--overwrite`
before trusting its decompiles.**

**Track C outcome (2026-09-05 morning, remote plan):** targets 3, 4 and 5
above are closed as far as the compiled code allows — enemy record yields
/ level / drop slots, the kill → drop roll → BATL_END tally chain, and the
finding that **no battle command has its own compiled function** (the
five-way venn is empty for Auto and Defend; Run and Watch differ only in
exit/Examine states). BATTLE_RAM.md "Turn order, kills, drops and the
results tally" has the RAM; 30 names landed. Follow-up the same morning: widening the
`fn_filter` to the engine band (`--lo 0x80093800 --hi 0x801D0C00`, 100-frame
windows) found the command menu, the Run roll (`Escape_Roll` /
`Escape_Chance`), Auto's flag + fill, and the table-driven enemy AI
(`EnemyAI_ChooseActions`) — BATTLE_RAM.md "Commands, Auto, Run and the
enemy AI". Skill and item rounds were captured after that (`c_skill`,
`c_item`, `nu_item`) and the engine's `Effect_ApplyResult` `0x8009A160`
(the one function behind skill, item and enemy-special HP changes) was
seeded and read. Left from C: the Defend confirm body (Ghidra gap at
`0x801D2520`), the Defend flag `0x80`, a real drop, the per-skill/item
handler indices behind `0x800B165C` (user: read directly later). **Rule learned:
the default `fn_filter` sees only the game-mode band; anything the engine
does (menus, escape, AI) needs the engine band in the filter, and then
only ~130 frames fit the ring.**

**Traps paid for on track C (2026-09-05):** the fn-entry ring wraps at
262 144 entries and keeps the *newest*, so with the default filter a
battle window over ~1 000 frames loses the presses (`WARNING: entry ring
wrapped` — trust the tail, not the head); `slot03` opens on the *first*
member's menu, so one Circle-pair only enters Ryu's command and nothing
resolves — a round is Circle ×6 (or `--hold l1 --press circle` for Auto,
which resolves everything in one press); the results screen waits for
Circle — use `--press circle` ×18 with `--press-gap 150` to page through
it; `BATL_END.EMI` shares `0x801EEC00` with `SHOP.EMI#8`, so `name` there
needs `--overlay 18ce968c…`; `playsession.py dump` is not a RAM dump —
snapshot RAM with `ramdiff --range LO-HI --no-ask` and read the
`.before.bin`.

**Traps paid for this weekend** (details in BATTLE_RAM.md / GHIDRA.md):
long `ramdiff` windows net out later hits; a same-state save rewrites
identical bytes (use the write trace, not the diff); `wtrace_dump` truncates
a frame with more than 2 048 stores (the decompile fills in); a boot-EXE fn
filter wraps the ring in ~160 frames and the libcard range is flooded by
the `TestEvent` wait loop, so filter on the file-API wrappers
`0x8017F7B0-0x8017F830` instead; store PCs inside a shared band must be
attributed against the *resident* overlay only; `ghidra_run.py import` now
seeds traced entries and creates functions in descending order so lower
functions cannot swallow higher starts.

### 1. Axis B — the loop (mechanical, proven, converging)

A compiled band is not a fully native band: interior entry points reached only
by dynamic dispatch are invisible to the static call-edge walk, so they
address-miss to the interpreter *inside* a compiled band. The observed→alias
pipeline fixes them. This session proved it end-to-end — the intro-boss harvest
took the battle overlay's hot interior points (`0x801E6C60`, was 14.2 M interp
insns/#1 sink) **native**, the same mechanism that resolved §9's `0x801CEEDC`.

The loop is mechanical and self-improving:

1. Play a live session covering as much as possible. **Play `build-relprof`,
   not `build-dbg`** (corrected 2026-09-06): the harvest is port-based and reads
   whichever build is live, but only a tree built since 2026-09-05 carries the
   dirty-PC enrichment (`occ_crc` / `occ_ok` / `ext_ra`). `build-dbg` predates
   it, so a session there yields bare PCs and the seedable / attribution /
   outside split — the reason the enrichment exists — cannot be computed.
   `harvest_interp_pcs.py` now prints a loud WARNING instead of falling silent.
   `build-relprof` also holds 60 fps; `build-dbg` runs below real time.
   `axis_b_loop.sh` defaults to `build-relprof` and takes `--build DIR`.
2. `python tools/harvest_interp_pcs.py` — **unions** this session's entered PCs
   into `analysis/observed_interp_pcs.json` as a distinct set (one row per PC,
   no duplicates), and reports how many are newly seen.
3. Re-run `tools/extract_overlays.py "isos/…Japan.cue"
   --out analysis/overlay_captures_all.json` (it reads the observed file by
   default via `--observed`) → `analysis/overlay_captures_all.json`.
4. Recompile all bands and rebuild.
5. Re-measure. Repeat until `tools/pc_coverage.py` shows every stratum near
   saturation — **not** until a session produces 0 new PCs (see *The stop
   condition* below; 0 new is not evidence of a complete set).

**It needs a play session to harvest against — that is the only blocking
input.** Everything after step 2 is mechanical.

**The observed set accumulates across sessions — union only, never replace.**
Two play sessions enter almost *disjoint* PC sets (measured 2026-08-31: two
sessions shared only 323 of ~17,500 PCs), because which `.EMI` area is resident
decides which addresses bucket to a band. So each session covers areas the last
did not, and overwriting would throw that away. `harvest_interp_pcs.py` now
unions distinctly, so the set only grows and `extract` reproduces full coverage
from the observed file with no manual capture merge. (This is why band-level
attribution inflating one PC into many is harmless: duplicates are collapsed in
the observed file and re-derived per band at extract time.)

### 1b. Enrichment — understanding what the captured PCs *are*

New this session: [`tools/enrich_pcs.py`](../tools/enrich_pcs.py) turns a bare
observed PC into an explained one, joining data we already have:

- **Identity** — reads the live band bytes and byte-matches them to the resident
  `.EMI` occupant (so `0x801CEEDC` → "`PLP27A` resident").
- **Boundary** — FUNCTION-START (prologue, or preceded by `jr ra`) vs INTERIOR,
  plus whether the PC is a static root or observed-only. This is how §9 was
  finally understood: `0x801CEEDC` is INTERIOR, `static_root_in=0`.
- **Semantics** — a disassembly window and the outgoing `jal` targets ("linked
  calls" — the subsystem edges).
- **Reach** — callers + args + frame span from the live `dirty_block_log` ring
  (4 M-entry, filterable by target). A **native** PC shows **0 ring hits** (the
  ring logs interp only), a free cross-check that a fix took.
- `--group` — offline interp-weighted **subsystem breakdown** by band+family
  (PLCHAR / BATTLE / SCENARIO / field / boss / kernel), the first cut at the
  "these calls are one subsystem" clustering.

**The offline slice is done; the durable upgrade is tier-1/2 in the runtime.**
The reach data only reaches as far back as the ring, and mixed bands
(`0x801D0C00` = BATTLE+ETC+SCENARIO+WORLD) can't be resolved to an occupant
offline. Recording, *per PC at entry time*, the **resident-occupant CRC**
(tier 1) and a **transfer-type histogram** (call/jalr/jr/branch/irq-resume,
tier 2) in `DirtyRamPcEntry` (`dirty_ram_interp.c`, emitted via
`dirty_ram_stats.per_pc`) makes both durable and session-long. Tier 2 is the one
that would have diagnosed §9 in minutes instead of an afternoon. This is a
framework change on the `fix/static-overlay-residency-signal` branch. Endgame
(per the user): once calls are grouped by shared caller/callee, "contextually
bound / philosophically linked" subsystems fall out — the unit for modding,
performance, and extensibility.


**2026-09-01 late — the readability sidecar exists.** The "name the subsystems"
endgame above now has a home: `names/overlays.toml` + `names/functions.toml`
(keyed by section md5 + pc), `tools/name_map.py` (init/check/stats) and
`tools/subsystem_map.py` → `docs/subsystem_map.html`. Read
[`NAME_MAP.md`](NAME_MAP.md) for the schema, the status/evidence rule, and the
ordered routes to earn names. `axis_b_loop.sh` phase 6 regenerates the map on
every rebuild path; after a `--harvest-only` session or a `names/` edit, run
`name_map.py init` + `subsystem_map.py` by hand.

**Area naming is live (route 1 in NAME_MAP.md), not a banner-string join** —
there is no string-capture log in the current code. `tools/area_poller.py watch`
runs during play: it identifies the resident `AREAnnn` with certainty by
hashing the script block at `0x80010000` against `emi_sections.json`, takes a
settled screenshot a few seconds after each change (the change-instant frame is
black — the block lands during the fade), and compresses the runtime's per-call
`overlay_native_ring` to one row per overlay body per area.
`axis_b_loop.sh --harvest-only` runs the poller's one-shot `harvest` too. Both
append to `analysis/area_timeline.jsonl`; gather as many sessions as you like,
then `area_poller.py summarize --apply` writes sightings as `evidence` (never
overwrites). The alias is read off the screenshot by a human and typed into
`names/overlays.toml` with `status = "evidence"`. Seven WORLD00 areas sighted so
far (AREA001/002/006/009/024/031 + one more), zero aliased — that is the next
task.

### 2. A short persuasive writeup of the static compile path and dispatch map

**DONE — reworked and republished 2026-08-31.** Audience is the other people
working on the wider psxrecomp ecosystem, who have only seen the capture-based
bringup used for Tomba / MMX6 / Ape Escape. The goal is a concise, persuasive,
layman-readable explanation of what this title does differently and why.

Published as a private artifact (same URL, updated in place):
<https://claude.ai/code/artifact/37f5d9d1-64c9-4db6-bb65-aad75e0ab4f4>
— **retitled "The Disc Ships the Map"** (the old title "Overlays Without
Capture" contradicted the corrected framing, since entry points legitimately
*do* come from play). It covers the normal capture path, the bytes/entry-points
decomposition, the disc's inherent grouping, the three-tool compile path, the
dispatch map, the frozen-gate bug, the measured result, and what transfers to
other titles.

**The two parked blockers are resolved:**

- **Reframed off the either/or.** The spine is now the decomposition from the
  next section — capture bundles *bytes* and *entry points*, which have opposite
  value here — plus the user's sharper thesis: for an EMI-styled RPG the disc
  ships the game's *own grouping* (named/typed `.EMI` containers → graphics vs
  sound vs logic vs area script), and that grouping is trivial to read but a
  research project to reconstruct from an address-keyed capture bucket. That
  grouping is the unit for the enrichment/subsystem-clustering endgame.
- **The stale §9 claim is gone.** The old "Still open" section said `0x801CEEDC`
  "is still being interpreted"; §9 is resolved, so that bullet was removed.

The one **unverified** claim was softened rather than verified: the draft now
says Tomba *reportedly* uses a scatter-load format "per the framework's own
notes; we haven't verified it against that project," instead of asserting it as
fact. If anyone wants it stated flatly, verify against the Tomba project first
([`OVERLAYS.md`](OVERLAYS.md) §5 / `psxrecomp/docs/overlay-discovery.md`).

**Remaining in thread 5:** the upstream PR is **held as a draft** by decision
(2026-09-01) — see "Shipping state" below for the living-integration-branch
workflow that replaced "merge it upstream."

### The framing both threads share: capture and disc extraction are not rivals

Established by inspection on 2026-08-31, and it reframes Axis B. **Capture
supplies two separable things, and they have opposite value here:**

| | disc extraction | runtime capture |
|---|---|---|
| **the bytes** | **wins decisively** — complete by construction, deterministic, reviewable, shippable, no playtime | strictly worse here; carries every objection (privacy, non-determinism, playtime-bound coverage) |
| **the entry points** | cannot see anything reached only by indirect dispatch | **wins decisively** — an executed PC with `entries > 0` is empirical proof of a callable boundary |

So the right architecture is **bytes from the disc, entry points from play** —
and *that is already what the pipeline does.* The current all-bands captures
carry **5,540** static call-graph roots plus **10,109** observed-PC attributions
(from 443 unique entered PCs), across 333 of 338 captures.

Note the asymmetry in risk: every objection to capture attaches to the *bytes*.
Entry points are a list of integers — no disc content, diffable, and purely
additive, since a bad one is rejected by the compiler's own validation. Axis B
is therefore capture's unique benefit at almost none of its cost.

Two known weaknesses in the current hybrid:

- **~~The observed set is a single session~~ — FIXED 2026-08-31.** It used to be
  a single session (443 entered PCs, 2026-08-30), the direct cause of the
  remaining gaps. `harvest_interp_pcs.py` now unions each session into a distinct
  accumulated `observed_interp_pcs.json`; the current set is **874 distinct PCs
  (768 entered)** from two sessions, and it only grows. The prior tool overwrote
  the file *and* appended to the dead seed lane — both removed.
- **Attribution is band-level, not occupant-level.** An observed PC is attached
  to *every* occupant of its address band — which is why the distinct entered
  PCs become ~17,854 attributions. Harmless (validation filters them) but it
  inflates seed counts and cannot tell you which of 181 area scripts actually
  ran an address.

**One case where capture's bytes would still win, even here.** If the game ever
patches or relocates overlay code *after* load, the disc bytes will not match
RAM, every variant will fail the checksum, and that address falls to the
interpreter silently — it looks like an ordinary miss. No evidence of this so
far (compiled bands run at ~100% hit rates and every CRC miss observed is
explained as a non-resident tenant). **The diagnostic:** a band where *every*
variant consistently misses means the disc bytes are not what reaches RAM, and
that band specifically would need captured bytes.

---

**The upstream dispatch fix is DONE — all three steps.** Full evidence in
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §10-§12.

The §8 plan called for two upstream fixes: memoize the resident variant per
band, and make address lookup O(1). Investigating the first turned up a
prerequisite nobody knew about — **the static path had no residency signal at
all.** `overlay_page_gen` only advances for pages in `overlay_watch_bitmap`, and
the only callers of `overlay_watch_set_range` were in the DLL loader, which is
inert here. So the CRC gate was consulted *once per variant per process*, and
cached negatives were permanent: a variant checked before its content loaded was
locked out of native dispatch forever.

| Step | State |
|---|---|
| 1. Arm the page watch for static ranges | **DONE** — `psxrecomp` `aa6fa2c9` (§10) |
| 2. O(1) address lookup (kills §8 Finding 2) | **DONE** — `psxrecomp` `69d783f5` (§11) |
| 3. Resident-occupant memo (kills §8 Finding 1) | **DONE** — `psxrecomp` `70153175` (§12) |

All three are committed on branch `fix/static-overlay-residency-signal`,
branched from the pin `f24b7e5d`.

**ALL TEN BANDS ARE NOW THE CONFIGURATION.** §8's "do not compile all bands" is
overturned: all-bands beats three-band on both workloads measured — **131.4 vs
107.9** emulated fps at boot, parity on a savestate workload. The relationship
inverted, because once dispatch is cheap, more compiled code means more native
execution. Build it from `analysis/overlay_captures_all.json`; §12 has the
exact commands.

Headline numbers, all headless VSync throughput on identical protocols:

| | boot (140 s) | savestate (200 s) |
|---|---:|---:|
| 3-band switch (the old build) | — | 106.5 |
| 3-band table | 107.9 | 113.2 |
| all-bands table, no memo | 99.0 | 115.1 |
| **all-bands table + memo** | **131.4** | 114.2 |

Note the third row: **without the memo, all-bands is slower than three bands at
boot.** Both steps 2 and 3 are load-bearing for the all-bands result.

### Shipping state — updated 2026-09-02 (perf branch on the fork, PR pending)

**2026-09-02:** `psxrecomp` is pinned to fork branch
`perf/static-overlay-parallel` at **`7ab698ca`** = upstream `mstan/master`
`04d9184b` (ABI v22 shim + shared release staging) + one commit: parallel
static compile (`--jobs` process pool), linear CPS resume-wrapper pass, and
split output (`overlays_static.c` dispatcher + `overlays_static_NNNN.c` per
overlay, globbed by `runtime.cmake`). Measured on build-dbg: phase 5a 12 min →
20 s, runtime build 4 min → 69 s, whole `axis_b_loop.sh --skip-harvest` ~16 min
→ 90 s; **build-relprof `psx-runtime` 1016 s → 162 s** (one 303 MB unit vs 358
units); shard summary and 79,688 identities unchanged; headless boot 99.92 %
static hit rate, miss_total 0. Upstream PR mstan/psxrecomp#296 is a **draft by
decision (2026-09-02): play-test the split/parallel build more before asking for
the merge**; **re-pin to plain `mstan/master` when it merges** (recipe below still applies). The bump required
rebuilding the emitters (`build_emitters.sh`; codegen tag `a4319b6f` →
`ecd487f7`) and a build-dbg reconfigure; `generate` was a no-op.

The 2026-09-01 "living integration branch" decision below is **superseded**:
that branch's commits were merged upstream and the pin went back to plain
master the same night; the perf branch above is an ordinary upstream PR, not
a new integration branch.

#### (superseded) 2026-09-01 — fork as a living integration branch

**Decision (2026-09-01):** the upstream PR is **held as a draft, not merged** —
we would rather fix any snag in-tree than round-trip through framework review.
So `fix/static-overlay-residency-signal` is now a **living integration branch**:
it carries our three commits *and* tracks upstream `mstan/master`, and we keep
pulling master into it as work continues. The proof-of-process goal is a full
BoF3 decompile with the `.EMI` subsystems intact — see the writeup thread above.

Current pins (both submodules bumped 2026-09-01, verified booting):

- `psxrecomp` branch `fix/static-overlay-residency-signal` on `origin`
  (`kerokline/psxrecomp`) at **`ecc0de16`** = upstream `master` merged over our
  three commits (`aa6fa2c9`, `69d783f5`, `70153175`). 3 ahead / 0 behind
  upstream at merge time.
- `recomp-ui` bumped `8c30e004` → **`4eda654`** (upstream `mstan/master` tip) —
  **required**, because the merged psxrecomp `main.cpp` uses the multi-disc
  launcher API (`RecompLauncherCGameInfo.discs/num_discs`,
  `RecompLauncherCSettings.disc_index`) that lives in recomp-ui. The two
  submodules must move together.

**The draft PR still stands** for eventual upstream consideration: all three of
our commits are framework-level with no BoF3 content, landing in order
(`aa6fa2c9` correctness prerequisite; `69d783f5`+`70153175` the load-bearing
performance pair). Blast radius is the static-overlay path only — verified
per-hunk (the DLL-loader capture path Tomba/MMX6/Ape Escape use is untouched).

#### Keeping the fork current — the recipe (conflict-free so far)

```bash
# game running: BreathOfFire3_Recompiled.exe --game game.toml --no-launcher --debug-port 4370
tools/axis_b_loop.sh            # harvest → extract → LOGO merge → catalog → codegen hash → compile → build-dbg
tools/axis_b_loop.sh --skip-harvest   # rebuild from the observed set as-is
```

Phases, for when you need to run one by hand:

1. Play a live session on a debug-tools build covering **new** content.
2. `python tools/harvest_interp_pcs.py` — **unions** the session's entered PCs
   into `analysis/observed_interp_pcs.json` (distinct, never replaced).
3. `python tools/extract_overlays.py "isos/…Japan.cue" --out analysis/overlay_captures_all.json`
   then `python tools/extract_logo_overlay.py … --append-to` the same file
   (extract rebuilds from `.EMI` only and would drop LOGO).
4. `cmake --build build-dbg --target psxrecomp_codegen_hash` (must precede the
   overlay compile after any framework change).
5. `python psxrecomp/tools/compile_overlays.py --static --force --cps …` — all
   bands; output is `generated/overlays_static.c` (dispatcher) plus one
   translation unit per overlay, `overlays_static_NNNN.c` (358 today), which
   `runtime.cmake` globs. Runs in a process pool (`--jobs`, default cores−2).
   **Exit 0 with `failed=0` is the expected outcome since 2026-09-18**
   ([`frameless-dispatch-roots.md`](frameless-dispatch-roots.md)); an `[audit]`
   `0 unknown_bad, N unsupported` failure now means a data shape the CFG probe
   does not recognise and is worth reading. Since 2026-09-02 this phase takes
   ~20 s, not ~12 min.
6. Build `psx-runtime`; re-measure per PC with `harvest_interp_pcs.py`.

**It needs a play session reaching new content — that is the only blocking
input.** Replaying seen content converges to ~0 new PCs (325→56→20→6). The
observed set accumulates across sessions because two sessions enter almost
disjoint PC sets (which `.EMI` is resident decides what buckets to a band).

### Mixed sections are extracted by default (2026-09-04)

`extract_overlays.py` takes both `code` and `mixed` survey classes now. The old
`--include-mixed` opt-in is accepted and ignored; `--no-mixed` restores the old
behaviour for A/B work and prints a warning when used. `axis_b_loop.sh` follows.

The measurement that settled the open question:

| | default | `--no-mixed` |
|---|---|---|
| sections extracted | 405 | 338 |
| AREA files with ≥1 selectable section | **184 of 200** | **126 of 200** |

- **58 of 200 AREA files ship no `code` section at all** — their `mixed`
  section is the only compilable code they have. That list is not obscure
  content: AREA000 (MacNeil Village), AREA001/002 (Dauna Mines). Excluded, those
  areas have **zero** compiled code and run entirely in the dirty-RAM
  interpreter.
- **All 67 mixed sections load to one band, `0x801F2C00`** (the WORLD band), at
  section index 13 of each AREA file, 67 distinct md5s — one per area, as
  area-specific code should be. `0x801F2C00` is a known remaining interpreted
  sink, and `pc_coverage.py` ranks it the least-covered band.
- **`mixed` is a classifier artifact, not a third kind of section.**
  `emi_survey.classify` demands `jr>=4 AND prologues>=4 AND density>=2/kword`;
  the mixed sections are small (median 710 words vs 1957 for `code`) and
  leaf-heavy, so they fail the *absolute* prologue count while passing density
  by a wide margin (median 11.9/kword). WORLD04 AREA176–180 have **34 `jr ra`
  and 3 prologues** — unambiguously code, one prologue short of the gate.

**The cost of the old default was performance, not correctness.** Nothing was
"missed" in the sense of unexecuted or wrong: the dirty-RAM interpreter runs
whatever bytes are resident. What was missed is *compilation* — 58 areas' worth.
The tail of the mixed class does look like genuine data (AREA090: 1359 words,
2 `jr ra`, 0 prologues); compiling those costs a dead translation unit and some
audit noise, which is the cheaper error than leaving 58 areas interpreted.

### The stop condition — estimated coverage, not "0 new PCs"

"Play until a session produces no new entered PCs" is unfalsifiable: it is
equally consistent with *the set is complete* and with *the player walked the
same three rooms twice*. Since the sessions are nearly disjoint by construction,
the second reading is the likelier one, and the criterion also says nothing
about **where** the gaps are.

[`tools/pc_coverage.py`](../tools/pc_coverage.py) replaces it. Each play
session is a sampling unit, each PC a species, and the unseen remainder is a
Chao2 richness estimate over session incidence:

```
N = S_obs + ((m-1)/m) · Q1² / (2·Q2)        Q1/Q2 = PCs seen in exactly 1 / 2 sessions
```

```bash
python tools/pc_coverage.py            # by band (+ static fn-start ceiling)
python tools/pc_coverage.py --by area  # by resident area, named from names/areas.toml
```

Three things to hold onto when reading the output:

- **Stratify, and trust the strata over the global row.** Chao2 assumes samples
  drawn from one pool; these are not (the 323-of-17,500 overlap). Within one
  band or one area the sampling is far closer to homogeneous, so the per-stratum
  estimates are sounder, and their sum exceeds the global estimate — that gap
  *is* the heterogeneity. Read the global row as a lower bound.
- **Coverage is harvest completeness, not nativeness.** A band at 100 % can
  still be slow until its PCs are compiled in. That axis is the interpreted/
  native ratio, same tool, different number.
- **Two denominators.** `est. total` is what remains to be *found*; `fn starts`
  is the static function count in the band (`jr ra`, fingerprint-deduped) — a
  ceiling, not a target, since most of those are already native via static call
  edges and can never appear as an interpreted PC.
- **The one way this can mislead: replayed content.** Chao2's whole signal is
  singletons. Two sessions covering the *same* content see almost every PC
  twice, Q1 collapses, and coverage prints ~100 % — which is indistinguishable,
  to the estimator, from genuine saturation. The report warns when Q1 falls
  below 10 % of the observed set, or when coverage exceeds 95 % on fewer than
  four sessions. **Vary what you play**; a coverage number is only ever about
  the content the sessions actually reached.
- **`NEVER SAMPLED` rows are the honest gaps.** Every known band is listed even
  with zero observations, and unsampled bands lead the "go play these next"
  line, because a stratum with no draws is a bigger hole than one at 40 % — and
  a table that quietly omitted them would read as far better news than it is.
- **Always pass `--merge-duplicates`, and read the DUPLICATE SESSIONS warning
  when it fires** (paid for 2026-09-11). The tool detects session ids whose PC
  sets are provable subsets of another id, which only happens when both sample
  the *same process* — a re-harvest, not a new sample. 11 of the 14 ids
  recorded here are subsets of `20260904T093558`, because `area_poller.py
  watch` re-harvests a running session every 15 minutes and each pass was
  banked under its own id. Counted separately they inflate the sampling unit
  count, which inflates coverage: the same data reads 3.8–31.5 % unmerged and
  **3.3–18.8 % merged**, and four bands stop being estimable at all. The
  merged figures are the real ones. The harvest is early, not nearly done.

**Current state, 2026-09-11 (merged):** `0x80117000` Research Plant never
sampled; `0x800C1800` BOSS 3.3 %; `0x80196800` field/map core 4.7 %;
`0x801CE400` PLCHAR 9.0 %; `0x801D0C00` BATTLE+ETC+SCENARIO 11.4 %;
`0x801F2C00` WORLD 15.6 %; `0x801EEC00` BATTLE+BMAGIC+ETC 18.8 %. Play in that
order. One long session through unseen areas beats ten polls of a running one.

The estimate needs **session incidence**, added to `observed_interp_pcs.json`
on 2026-09-04 as a per-row `sessions` list (plus `areas`, stamped on PCs newly
seen in a poller pass while that area was resident). Rows harvested before that
have no `sessions` key; they count as seen but cannot contribute Q1/Q2, so the
report is pessimistic and calls out the legacy count until they are re-observed.
**Chao2 needs at least two sessions carrying ids** — the report says so plainly
rather than printing a number it cannot support.

**Strata are named.** `pc_coverage.py` labels each band from
`analysis/overlay_catalog.json` (refreshed by the loop's phase 3b), so rows read
`0x801F6C00 SCENARIO x20` and `0x801D0C00 BATTLE+ETC+SCENARIO +1 x18` rather
than bare addresses. Numbered siblings collapse (`WORLD00..04` → `WORLD*5`), and
a single-occupant band with an alias in `names/overlays.toml` uses the alias
(`0x801CE000 Capcom logo intro`, `0x80196800 Field/map core (large)`) — that is
the readability track paying off. `--by area` names rows from
`names/areas.toml`. Missing catalog degrades to bare addresses.

**A session id identifies the RUNNING PROCESS, not the wall clock.** This bit
us within hours of shipping it: harvesting the same live game twice (the loop's
end-of-run pass after the poller's timed one) minted ids `…093558` and
`…094409` over one play session. Both saw the same 196 PCs, none unique to
either, so Q1 = 0 and the harvest line printed **100.0 % coverage** of a set
nobody had finished exploring. `resolve_session()` now reads the runtime's
`frame` counter against `analysis/harvest_session.json`: a frame below the
stored one means the game restarted (a real new sample), anything else
continues the stored id. `area_poller.py watch` still passes its own id
explicitly, which wins. The two phantom ids were merged in the observed file on
2026-09-04 (backup: `analysis/observed_interp_pcs.prefix.bak`).

**The same bug had a second mouth: `area_poller.py watch`.** It passed its own
per-watch-run timestamp, which bypassed `resolve_session` entirely — so
starting the poller late, or restarting it mid-game, split one play session
again (ids `…101508-b053` and `…101601`, byte-identical PC sets 53 seconds
apart). The poller now passes `session=None` and lets the process decide; its
own run id stays on the *timeline* rows, where per-watch-run is the right grain.

**Detecting the split after the fact.** A cumulative per-PC table only grows
within a process, so if session A's PC set is a **subset** of session B's, A is
not a separate session — it is an earlier snapshot of the same one.
`pc_coverage.py` reports such ids as `DUPLICATE SESSIONS` and
`--merge-duplicates` collapses them (backup: `<observed>.premerge.bak`,
idempotent). Merging the 2026-09-04 set took 6 ids → 3 real sessions and the
global estimate from a flattering **97.6 %** to an honest **72.0 %** — the
clearest measurement yet of how badly a split sampling unit distorts Chao2.

**Pending right now:** the 239 PCs from the world-map / shop / save-screen
session are compiled in but not re-measured. Remaining interpreted sinks:
SCENARIO band `0x801F6C00`, mixed BATTLE band `0x801D0C00`, and two residual
battle interior points `0x801D1014` / `0x801E739C`.

**Function-pointer tables need a registered dispatch entry, not just a
compiled root.** LOGO dispatches per-frame effect handlers through tables that
are zero in the image and populated at runtime (`lw v0,0(sN); jalr ra,v0`). A
compiled static *root* is not reachable by `jalr` unless its address is also a
dispatch entry (`0x801D22EC` was compiled and still interpreted).
[`tools/harvest_logo_handlers.py`](../tools/harvest_logo_handlers.py) locates
such tables statically, reads them from a live session, and emits every handler
at once. The pattern recurs in any title with effect/handler tables.

### 2. Enrichment — understanding what the captured PCs are

[`tools/enrich_pcs.py`](../tools/enrich_pcs.py) explains an observed PC
offline: resident `.EMI` occupant (live byte-match), FUNCTION-START vs
INTERIOR, a disassembly window with outgoing `jal` targets, callers from the
live `dirty_block_log` ring (a native PC shows **0 ring hits** — a free check
that a fix took), and `--group` for an interp-weighted subsystem breakdown.
[`tools/overlay_catalog.py`](../tools/overlay_catalog.py) is the offline
sidecar (`analysis/overlay_catalog.json`): family, band co-residency, root
provenance, honestly-attributed heat.

**Tier-1/2 landed in the runtime (2026-09-05, psxrecomp fork branch
`feat/dirty-pc-enrichment`, off the `17f49ad3` pin).** `DirtyRamPcEntry`
gained two fields, stamped only on **external** entries (arrived from native
dispatch, not interp block chaining) and emitted per row in
`dirty_ram_stats.per_pc`:

- `occ_crc` + `occ_ok` (tier 1) — `psx_overlay_resident_crc_at(pc)`: a scan
  of the static-match cache for the compiled piece whose code ranges span the
  PC. **The runtime validates per function / fragment, not per section**, so
  `occ_crc` is that piece's CRC; [`tools/occ_resolve.py`](../tools/occ_resolve.py)
  joins it back to the piece's symbol, band and source-section crc32 from
  `generated/overlays_static.c` (`ov_<band>_<sectioncrc>_…_func_<pc>`, cached
  in `analysis/static_variants.json`). `occ_ok = 1`: the piece validated —
  an interior gap inside live native code, the Axis B seed case. `occ_ok = 0`
  with a CRC: the piece is resident but CRC-missing — compiled from *another*
  section's bytes, or rewritten at run time; no seed helps, the resident
  section needs its own piece. `0`: nothing compiled spans the PC (BIOS,
  kernel, boot EXE). The first draft read the loader's process-global last
  hash, which the static path never sets — all zeros on a real boot; the
  per-PC scan replaced it.
- `ext_ra` (tier 2) — `$ra` at the most recent external entry: the caller
  that reached this interior. A PC reached only through a function-pointer
  table shows the dispatcher's `ra`, so the §9 LOGO diagnosis (find the table's
  call site) comes out of the session-long snapshot with no ring window.
  `ext_ra == pc` is a `jr ra` **return** into interpreted code (native callee
  returning to an interpreted continuation), not a call. The full
  call/jalr/jr/irq histogram was **not** built — the fp-log ring still carries
  the transfer split when one is needed.

**First result (title screen, headless boot):** resident SCENARIO-band section
= SCENA16 (`enrich_pcs.py --pc 0x801F6C90`), yet `occ_resolve` shows every
interpreted PC there spanned by a piece from SCENA19 / SCENA04 / SCENA06 …
with `occ_ok = 0` — 517 + 235 + 235 entries in one title visit. The band is
"compiled" but the resident section has no pieces at those PCs.

**Root-caused and fixed the same evening (2026-09-05) — it was the compile
side, not extract-side attribution.** `extract_overlays.py` does attach every
observed PC to every occupant of its band (SCENA16's capture listed all 53),
but `compile_overlays.py --static`'s isolated-fragment pass resolved demands
by **bare address** across all captures: once any part had a variant at an
address, the address counted as served for every capture in the band, and
`static_entry_sources` kept only the *last* capture's bytes. So exactly one
occupant per multi-section band ever got fragments (BOSS055 35/35, PLP678
19/19, SCENA19 20/20; the 128-occupant `0x801EEC00` and 181-area
`0x801F2C00` bands got none) — 23,728 (entry, image) demands unserved, and
`STATIC COVERAGE WARNING` never fired because by address everything looked
served. Fix on psxrecomp fork branch **`fix/static-fragments-per-variant`
`2fa3472a`** (stacked on `feat/dirty-pc-enrichment` `6e760748`, both pushed
to `kerokline/psxrecomp`): demands keyed `(entry, image crc)`, parts carry
`image_crc`, fragments compiled on the `--jobs` pool (image table sent once
per worker), deterministic data-as-code verdicts (generated-C audit, and the
recompiler *throwing* on a walk that runs off the image) memoized in
`generated/interior_fail_memo.txt` and counted as *skipped* rather than
`SHARD FAIL`; fragment parts grouped one translation unit per image.
Unit test `psxrecomp/tools/tests/test_static_fragment_variant_keys.py`.
Numbers (full BoF3 run): 20,250 fragments built, 3,570 memoized rejections,
**238 s cold / ~3 min warm** for phase 5a (was ~80 s), served keys 99,778 →
138,148 with nothing lost, `PSX_SHARD_RESULT failed=17` unchanged (the loop's
gate passes). Cost: `generated/` is now **1.6 GB of C in 779 units** (was
358 MB / 480) and the build-dbg exe 699 MB — a cold `psx-runtime` build is
minutes, not 69 s; incremental rebuilds only touch changed units.
**Verified headless at the title screen** (same injected Start/Start/Circle
protocol, `scratchpad/title_probe.py` pattern): interpreted SCENARIO-band
entries **12 → 2**, and the two left (`0x801F7144`, `0x801F7170`, spanned by
a SCENA00 piece) are simply not in the observed set yet — the ordinary Axis B
harvest case. Overall interp/native at the title is unchanged (~14 M / 11 M
insns): the residue there is BIOS kernel entries (`0x000000B0`, 2.6 M
entries), not overlay code.

**Follow-up that would cut the 1.6 GB:** most of the 20k fragments are for
band siblings that never ran the PC (an observed PC attributed to all 181
areas). The observed rows now carry `areas` (resident area at first sight)
and, after one play session on this build, `occ_crc`/`occ_ok` — enough to
attribute a PC to the occupant that actually ran it and demand fragments
only there. Not done; the current output is correct, just large. A
batched-per-image fragment compile with bisection on audit failure (the DLL
path's hosted-fragment idea) would dedupe the overlapping walks too.

`build-relprof` has **not** been rebuilt since 08:17 and carries neither the
enrichment nor the fragment fix — rebuild it before measuring play.

`tools/harvest_interp_pcs.py` merges all three (newest non-zero wins, they are
not counts); `analysis/observed_interp_pcs.json` rows carry them from the
first harvest against an enriched build. The debug-server reply buffer grew
32 → 64 KiB for the wider rows. Play/harvest builds must be rebuilt from the
branch (`build-enrich` = Debug, mirrors build-dbg, was the test bed; headless
TCP savestate loads wedged on that Debug tree, so scenes were reached by
injected input from a cold boot — **that no longer applies**: the wedge does
not reproduce on `build-relprof`, 11 of 12 slots load and resume headless, and
`tools/scene.py` drives them, 2026-09-06). `docs/TCP_COMMANDS.md` in the submodule documents
the fields. **Branch state: committed as `6e760748` and pushed to
`kerokline/psxrecomp`; the fragment fix `2fa3472a` sits on top.** Open the
two upstream PRs (rebase the fix onto `mstan/master` if they should be
independent — the files are disjoint), then bump the pin. The `area_poller.py
watch` / `harvest_interp_pcs.py` report now prints the gap split per harvest
(`seedable` / `new interior` / `attribution undemanded` / `attribution RESIDUAL` / owned
`kernel` + `boot-EXE` / `outside compiled code`, stored on the timeline
`harvest` row as `occ_seed` / `occ_interior_new` / `occ_attrib_new` / `occ_attrib_residual` (+
`occ_residual_pcs`) / `occ_kernel` / `occ_bootexe` / `occ_none`), so a session
on an enriched build says at once whether the next loop will help.
**Reclassified 2026-09-07:** "attribution gap" used to mean "compile-side,
harvesting won't help", which was true before #325 and wrong after it. Now
an attribution gap whose PC no capture has demanded yet (`attrib_new`) is
ordinary harvest work — the next extract demands it for every occupant and
the per-variant compile serves the resident; 8 of the 9 so labelled on
2026-09-07 were this. Only a PC already in `dispatch_entry_pcs` that still
has no validated resident piece (`attrib_residual`) needs a compile-side
answer (memo rejection, run-time-rewritten bytes, or an occupant the survey
never compiled). Kernel RAM (`<0x10000`, 57 % of all interpreted
instructions in the observed set) and boot-EXE dirty text (`0x80164E84..`,
`0x8017EAA0..`) are OWNED by images that ship as-is: `pc_coverage.py` gives
them their own strata, keeps them out of the overlay estimate and never
recommends playing them. A zero `occ_crc` INSIDE a band is `interior_new` —
a first-sighting interior entry no occupant has a piece for (the 12 "outside
compiled code" rows of the 2026-09-07 evening summary were all this, 7 of
them in the single-occupant battle engine band); `none` is reserved for no
band and no owner. Caveat for the offline run over the accumulated
file: `occ_*` fields are last-seen values, so rows last observed on a
pre-fix build (the `0x801CE404` PLCHAR row, the `0x801EEExx` BATL_END rows
from the 2026-09-07 morning session) read as residual until re-observed on
the rebuilt tree — trust the live end-of-session harvest, not the file.
The compile's `[audit] ... N unsupported` rejections are explained by
`tools/data_islands.py` (loop phase 5a'): what the bytes are per occupant,
with names from `names/data.toml`. **Retracted 2026-09-08:** this file used to
say the tool's "code, walk failed downstream" list (23 pairs) was a real gap
and the compile-side worklist. It was not — the row was a classifier artifact
(zero fill scored as nops, tables decoding as `jal`/`beq`, one misattributed
memo line), and the audited count of real gaps is **0**. The classifier and
the join tiebreaker are fixed; nothing in the memo needs compile-side work —
[`DATA_ISLANDS.md`](DATA_ISLANDS.md).
Next on this track: stamp the *resident image* checksum at entry (today's
`occ_crc` is the spanning piece's function-level CRC, by construction the
wrong occupant whenever `occ_ok=0`), then key harvest rows and extract
demands on (image, PC) instead of expanding every PC to every occupant. Endgame unchanged: once calls are grouped by
shared caller/callee, the `.EMI`-shaped subsystems fall out — the unit for
modding, performance and extensibility.

### 4. Upstream: the patched BIOS exception handler — **the next big compile target** (2026-09-11)

44.6 % of every interpreted instruction is kernel RAM, almost all of it the
BIOS exception handler, unblessed on both BIOSes by the Psy-Q kernel patches
([`kernel-patch-sites.md`](kernel-patch-sites.md)). The fix is in psxrecomp,
not here, and we can push there: [`upstream-kernel-bless-plan.md`](upstream-kernel-bless-plan.md)
is the step list — publish install slots to the runtime and verify around
them (Step 1), generalise slots to ranges with a ROM-word compare (Step 2),
declare the observed slots in both profiles and pin the retail sha256
(Step 3), bump the pin and re-measure with `psxrecomp/tools/kernel_patch_diff.py`
(Step 4). One PR per step, off the current pin.

### 3. Translation, and the ruby variant — **pick this up next** (2026-09-09)

**2026-09-10 — inserted names read too; see [`INSERT_RUBY.md`](INSERT_RUBY.md).**
**2026-09-12 — true ruby (readings above the kanji) is back on the table.**
The quad blitter advances by 12 + P, not a flat 12, and per-glyph placement is
overridable from the plugin through the blitter entry hooks; the plan and the
shrink probe (`tools/ruby_shrink_probe.py`, stage = `slot02`) are
in [`FURIGANA.md`](FURIGANA.md) "The rendering route, reopened" and
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Per-glyph placement". **Steps 1 and 2
of that plan are done the same evening:** 12 + P advance and the fixed 14 px
newline are measured on screen, and a `gpr[5]` write from a function-entry
hook on the sprite blitter moves the text (env-gated `BOF3_RUBY_YBUMP`,
third `mod_function_entry_funcs` entry). **Step 3 collapsed to a row rule
and is demonstrated on screen** (`analysis/xlate_shots/ruby_rows_demo.png`):
ruby rows are ordinary rows in the string, x aligns by glyph count with
`0x09` half-cell gaps, and the plugin only sets y per row
(five hook entries now). **The builder variant is built and verified in
play-shaped conditions** (code `jp_furigana`, every word, the builder's
default since the inline jp_ruby / jp_ruby_all and the first-occurrence
scope were retired 2026-09-12; `analysis/xlate_shots/furigana_area014_pages.png`);
the plugin applies the row rule only to pages that start with `<0f><13>`.
**Readings draw from the game's own 8 x 8 kana font** (FURIGANA.md "The
8 px font"): the plugin re-points each reading glyph's `POLY_FT4` at the
small cell on the packet-commit hook `0x8014E494`; ruby row first, text
row second, offsets -2 / 6 / 19 / 27. Left: the reading review pass, and
the readings dropped after runtime inserts. Original pointer:
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Per-glyph placement". Two doc errors were
corrected on the way (advance vs size; `0x0B` never moved y).
The Ruby tables are in play (user-verified in real play, both scopes, system
block included), the readings have an override sidecar (`names/readings.toml`:
surface / dictionary-form / `next` / `prev` rules) and an audit list
(`--ambiguous`), the kanji table is in-tree (`names/kanji.toml`,
`tools/jptext.py`, 0x132C corrected 賃 → 代), and unread words are 0. The
text the box *inserts* at draw time — item and skill names through
`<07><nn>`, a 32-byte scratch record at `0x801490D4 + 0x20*nn` — is now
covered as well: `tools/build_ruby_script.py` emits a second table
(`generated/bof3_insert_<code>.c`, hash of the record bytes → the name with
readings, 109 names) next to each Ruby message table, and the plugin
rewrites the record at `MsgBox_Reset` before the message opens. The two
design checks were answered from the GAME.EMI disassembly (record filled
before the open; no leading byte) and the whole path ran on a live guest:
a synthetic pickup line drew 薬草（やくそう） を手に入れた (screenshot in
`INSERT_RUBY.md`). ~~**Left:** see one real pickup and one master's skill line
on screen~~ — **DONE 2026-09-11, user-verified in play**: both draw with
readings, so record 1 (filled by the area script through a pointer the
immediate scan could not see) is rewritten in time too. `build-relprof` is
linked with all five tables.

**Traps from 2026-09-10** (details in FURIGANA.md): the plugin's pointer
gate must cover the system block (`0x80010000`–`0x80017628`); a regenerated
table needs a rebuild *and* the game closed for the link; runtime inserts
must carry a width in the re-flow or a line runs 19 cells; savestates from
before the framework bump are refused (codegen hash), memcard saves are fine.

**The apply path exists and is verified on screen (2026-09-09 afternoon):**
[`LOCALIZATION_APPLY.md`](LOCALIZATION_APPLY.md). `game.toml` hooks
`MsgBox_Reset` through `[recompiler].mod_function_entry_funcs`,
`src/bof3_localize.c` repoints the box, `tools/build_script_xlate.py` builds
`generated/bof3_xlate_en.c` from the US disc (slot for slot, capitals, 16
cells per line). Build recipe and the three traps paid for are in that doc.
What is left on the English track: play through several areas and read the
plugin's `miss` lines, decide lowercase (the sheet is full), give `'` a cell,
key the 691 shared-string conflicts by area. **The ruby variant is built
too** (`tools/build_ruby_script.py` → `jp_ruby`, verified on screen the same
evening); what it needs is the reading review pass.

The engine, the interception point and now the **whole encoding** are known
([`TEXT_ENGINE.md`](TEXT_ENGINE.md)). The Latin/digit question is settled:
`0x41`..`0x5A` and `0x30`..`0x39` really are ASCII letters and digits, but
`0x3E`/`0x3F`/`0x40` are `‥`/`？`/`！`, and the single-byte table is
[`names/font.toml`](../names/font.toml) via `tools/font_sheet.py`. **100% of the
204,356 glyph cells in the 200 area scripts decode**, so text can now be written
as well as read.

The next concrete deliverable is the **Japanese (Ruby)** variant
([`FURIGANA.md`](FURIGANA.md)): the JP script re-authored with the reading
inline, `漢字（かんじ）`, as a third `[localization].languages` entry. It is
measured, not speculative — box lines hold 15 glyphs, three rows is ordinary and
four never appears on a confirm page, annotating first-occurrence-per-area and
re-flowing pages leaves 4.3% of pages over three rows (spend a `0x02` page break
on those, not a fourth row), and the whole thing costs +13.8% bytes with the
worst block at 90% of the 16 KiB window. In order:

1. The **reading sidecar** (per message, per word, reviewed — the Sudachi pass
   is costed, not proofread).
2. The **encoder**, whose acceptance test exists today: encode the *unmodified*
   script and diff byte for byte against the disc.
3. The **variant blocks**, checked against the window and the row budget.

~~Still unbuilt: the apply path.~~ **Built 2026-09-09**: the `MsgBox_Reset`
repoint is code now (above), shared with the English track. The box width is
**measured on screen**: 192 px interior, 16 cells (window record `0x80148644`
`+0x10` = 16 in 12.4 fixed), so the 15-glyph figure above was one cell
inside the frame. Menus/items/name entry
are a **separate** pool at `0x80014000`.
The prior decode work at `D:\BoFIII` supplies the kanji table and 11,491
aligned JP/EN lines ([`LOCALIZATION.md`](LOCALIZATION.md) §4.2).

## Building against the pin

**Trap (paid for 2026-09-15): `build-relprof` silently became a Release tree
with no debug server.** After the pin bump the game booted headless but every
debug port refused connections, and the log never printed
`debug server LISTENING`. The cache read `CMAKE_BUILD_TYPE=Release`,
`PSX_DEBUG_TOOLS=OFF`, `PSX_SPLIT_DEBUG=OFF`. Mechanism, from the source:
`runtime.cmake` sets an **unset** build type to Release, and `PSX_DEBUG_TOOLS`
defaults OFF under Release; once those land in the cache they persist, so a
bare `cmake -S . -B build-relprof` never puts them back. When or how the build
type went missing was not recorded. The check is one line, and the fix names
every option:

```bash
grep -E "^CMAKE_BUILD_TYPE:|^PSX_DEBUG_TOOLS:" build-relprof/CMakeCache.txt
cmake -S . -B build-relprof -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DPSX_DEBUG_TOOLS=ON -DPSX_STATIC_RUNTIME=ON -DPSX_SPLIT_DEBUG=ON
```

A symptom worth recognising: a `build-relprof` exe with no `.exe.debug` sidecar
next to it is a Release build.

**Trap (paid for 2026-09-11): a RelWithDebInfo exe over ~1.9 GiB of image will not load.** Windows says "this app can't run on your PC" for a perfectly valid PE once the DWARF sections push SizeOfImage past that; `.bss` is not the problem, `.debug_*` is. `CMakeLists.txt` now splits the DWARF into `<exe>.debug` after every link (`PSX_SPLIT_DEBUG`, default ON outside Release). Keep the sidecar next to the exe: gdb and `addr2line` find it through `.gnu_debuglink`. If an old tree still fails to launch, `objcopy --strip-debug` the exe by hand.

**Trap (paid for 2026-09-06): stale overlay objects survive a regeneration.**
`build-relprof` failed to link with `multiple definition of
ov_frag_001F6C00_1E5EE588_801F6C90_func_801F6C90` across
`overlays_static_0478.c.obj` and `overlays_static_0760.c.obj`, although **one**
source defines that symbol. #325 regroups fragments one translation unit per
image, which **renumbers every `overlays_static_NNNN.c`**; objects from the old
numbering stayed in the tree with mtimes newer than the regenerated sources, so
ninja considered them current and linked them in. It is not a codegen bug — do
not go looking for one. Clear them and rebuild (ccache makes it cheap: 779 units
relinked in ~15 s):

```bash
rm -f build-<tree>/CMakeFiles/psx-runtime.dir/generated/overlays_static_*.obj
cmake --build build-<tree> --target psx-runtime
```

Do this in **every** tree after any run that changes the unit count or numbering.


```bash
export PATH="/c/msys64/mingw64/bin:$PATH"          # or cc1 crashes silently
./psxrecomp/tools/ci/build_emitters.sh              # → build-recompiler/
python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc "isos/Breath of Fire III (Japan).cue"   # base EXE + BIOS → generated/
cmake -S . -B build-dbg                              # reconfigure if the shard count changed
cmake --build build-dbg --target psxrecomp_codegen_hash   # BEFORE compiling overlays
tools/axis_b_loop.sh --skip-harvest                  # overlays + build-dbg
cmake --build build-relprof --target psx-runtime     # the play/measure tree
```

Tree configs are in [`STATUS.md`](STATUS.md) → Build trees. `build-relprof` is
RelWithDebInfo + `PSX_DEBUG_TOOLS=ON` + **`PSX_STATIC_RUNTIME=ON`** (defaults
OFF there; the dynamic exe dies on a stale PATH `libstdc++-6.dll`).

Order matters, and each of these cost a session once:

- **Regenerate `overlay_codegen_hash.h` before compiling overlays** after any
  framework change. The stale-recompiler guard compares the recompiler's baked
  hash against `psxrecomp/runtime/include/overlay_codegen_hash.h`, which a
  *runtime* build step writes. Overlays first trips `FATAL: STALE RECOMPILER
  BINARY` — the guard working, not a bug.
- **A generate that changes the shard count needs a CMake reconfigure**, or the
  link fails with undefined `func_*`.
- **recomp-ui moves in lockstep** with a psxrecomp bump when the launcher ABI
  changes (`RecompLauncherCGameInfo.discs` etc.). Symptom: `main.cpp` fails to
  compile with "has no member".
- **`--cps` is required** when compiling overlays (the runtime is a CPS build).
- **`GAME_OVERLAY_STATIC_C` must not follow a multi-value CMake keyword** in
  `CMakeLists.txt` — keep it after `APP_ICON`
  ([`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md) §4).
- **All bands compile together.** `compile_overlays.py --static` writes one
  file per run; compiling one band alone silently drops the rest.
- `analysis/` is gitignored. A fresh checkout regenerates it with
  `emi_survey.py` → `extract_overlays.py` (+ `extract_logo_overlay.py`) before
  overlays can build. All-bands compile ~13 min, build ~7.

## Pins and branches

- **2026-09-17: the submodule checkout sits on fork branch
  `integration/vector-stub-plus-367` `88f4582a` = upstream `master`
  `193a60b8` + `8b50cd09` (the two-shape call-vector guard, open as
  [#381](https://github.com/RetroPortingToolKit/psxrecomp/pull/381), branch `feat/openbios-vector-stub-shape`) + the #367
  cherry-pick.** Same content as `4a792379` + the fix, which is what
  `build-relprof` and both BIOS backends in `psxrecomp/generated/` were
  built and measured from ([`vector-stub-shapes.md`](vector-stub-shapes.md)).
  + `85894111` + `88f4582a` (the computed-stride jump and self-limited
  table resolvers, PR branch `feat/computed-stride-jump` = [#382](https://github.com/RetroPortingToolKit/psxrecomp/pull/382),
  [`computed-stride-jump.md`](computed-stride-jump.md)).
  Bump the title gitlink to `88f4582a` now, or straight to master once
  #367, #381 and #382 merge; the integration branch exists only so
  the gitlink points at something pushed. **Regenerate across it:** the
  codegen hash changed, so the overlays were recompiled
  (`axis_b_loop.sh --skip-harvest --force`) and `build-relprof` rebuilt.
- **`psxrecomp` is pinned to `4a792379` = upstream `master` `193a60b8` + one
  commit on `fix/static-overlay-reconcile-cache-dir`, open as
  [#367](https://github.com/RetroPortingToolKit/psxrecomp/pull/367)**
  (2026-09-15). Bumped 62 commits from `baca0a8a`; our
  [#346](https://github.com/RetroPortingToolKit/psxrecomp/pull/346) (kernel
  install-slot ranges) **merged 2026-09-12** as `c5390e42` and is in that base.
  The extra commit exists because plain master **cannot regenerate this
  title**: upstream `3a174fab` calls a DLL-only reconciliation at the tail of
  `compile_overlays.main()` with `cache_dir`, which `--static` never binds, so
  every static run ends in `UnboundLocalError` after its output is written and
  `axis_b_loop.sh` (accepts only 0 or 2) aborts before the rebuild. #367 guards
  the call on the DLL path and adds `compile_overlays_static_tail`, which fails
  on master and passes on the fix. When #367 merges, bump straight to its merge
  commit. **Regenerate across this bump**: 7 base-EXE shards moved and the
  overlay codegen hash changed (`0x4fe894d2`). The BIOS backends regenerate
  with unchanged dispatch totals (OpenBIOS 3990, retail 13012) and still no
  dispatch key inside a declared range; the emitter's "dropped N continuation
  key(s)" line now reads 20 / 36 instead of 1 / 5 because it counts duplicate
  continuation records before they collapse to the same keys.
- **`recomp-ui` is pinned to `20e0540`**, fork branch
  `feat/additional-ui-functionality` =
  [#48](https://github.com/RetroPortingToolKit/recomp-ui/pull/48) refreshed
  by **merging** upstream `master` `cb7e54b` (32 commits: netplay
  account/Discord sign-in, automatch, block/report, LAN vs online, frame-blend
  holding apply, snes deadzones, N64 pad profiles). One conflicting file,
  `launcher_imgui.cpp`, where master's `cb7e54b` had independently fixed two
  bugs this branch also fixed — resolved upstream-first: master's per-column
  `PushID("key")`/`PushID("pad")` replaces our `##key`/`##pad` suffixes, with
  the pad scope moved inside our "no gamepad, no pad column" branch so a hidden
  column cannot pop the row ID; master's single Backspace-unbinds handler
  replaces our three per-path ones, which had become unreachable. Our
  `launcher_binds.c` half stays (it writes the `None` the PSX runtime reads as
  an explicit unbind). psxrecomp's newer launcher features are all
  `#if defined(RECOMP_LAUNCHER_HAS_*)`-gated, so the two pins move together
  without an ABI break.
- Previous `psxrecomp` pin, for the record: `baca0a8a` = `ed55299b` + the two
  #346 commits, rebased off `6f77dcc3` so that PR carried only its change. The
  description of the `ed55299b` base follows.
- `psxrecomp` base **`ed55299b`** = plain upstream `master` on
  `RetroPortingToolKit/psxrecomp` (the org the project moved to on 2026-09-09;
  `mstan/*` URLs still redirect). Bumped 2026-09-10 from `2fa3472a`, 68 commits.
  The old pin's reason for existing is gone: it was held on the fork branch
  because upstream master read six netplay fields
  (`guest_memcard`, `is_spectator`, `spectator_wire_slot`, `host_spectates`,
  `slot_port`, `slot_port_valid`) that lived only in mstan's unmerged WIP branch
  `merge/frameblend-localization`. **That branch is now merged into recomp-ui
  master** (`13d7d69`), so upstream psxrecomp builds against a published
  recomp-ui for the first time. Our `fix/gpu-polyline-terminator` also merged
  ([#313](https://github.com/RetroPortingToolKit/psxrecomp/pull/313)), so no
  fork branch carries anything the pin lacks.
  **A regenerate is mandatory across this bump** — do not skip it. The new
  `dirty_ram_interp.c` calls `psx_overlay_static_can_dispatch`, which
  `compile_overlays.py` only started emitting after the old pin, so a stale
  `generated/` fails at link with an undefined reference. Base-EXE codegen came
  out byte-identical (35 shards, 0 updated, dispatch unchanged) — only the
  overlay layer actually changes, but `axis_b_loop.sh --skip-harvest` is the
  supported way to redo it. **Verified 2026-09-10:** regenerate + Axis B +
  `build-relprof` links a 1.11 GB exe that boots to an OpenGL 3.3 context at
  60 Hz with all three localization tables registered.
- **What the bump changes for us, beyond the link fix:** the freeze detector no
  longer fires during host pause loops
  ([#339](https://github.com/RetroPortingToolKit/psxrecomp/pull/339)), which
  retires the `slow_frames`/`hard_freeze` false pairs (they were the
  savestate/rewind menu pausing the guest on purpose); PR #327's interlaced row submission was
  reverted to restore retail BIOS boot; `ExitCriticalSection` now preserves
  registers; and optional native-wide HUD / tiled-background support arrived
  (enhancement-phase only — leave it off during faithful-core work). The
  framework license is unchanged (PolyForm Noncommercial 1.0.0).
- `recomp-ui` **`26756c2`** = a commit on fork branch
  `feat/additional-ui-functionality` (`kerokline/recomp-ui`) = upstream `master`
  `8bf4738` + the launcher UI work
  ([recomp-ui#48](https://github.com/RetroPortingToolKit/recomp-ui/pull/48),
  still **open**), and it is that branch's tip. Refreshed 2026-09-10
  (`69eecdc` → `26756c2`) by **merging** upstream master in — not rebasing, so
  the open PR's review history survives; it had fallen 53 commits behind (the
  netplay lobby/chat series, frame blending, per-GUID pad binds, the display
  aspect row, HiDPI fixes). Three conflicts, all resolved upstream-first:
  `recomp_launcher.h` keeps both capability defines (`HAS_FRAME_BLEND` from
  master, `HAS_SCANLINES` from us); the bind grid takes master's restructure,
  which splits the pad-source and keyboard-source chips into separate branches
  and supersedes our KEY+GAMEPAD pairing, with `db12620`'s `!capture_assist`
  guard re-applied to both capture predicates so capturing a host shortcut does
  not light up the matching pad slot; the capture handlers keep our
  Backspace-clears path. `ctest` gives an identical 12/14 on the merged branch
  and on pristine master `8bf4738` (`recomp-ui-psx-binds` and
  `recomp-ui-launcher-setup-bios` both fail upstream too) — the merge introduces
  no regression. #42 (the standalone Scanlines toggle) stays **closed unmerged
  on purpose**: its card was folded into #48, so #48 is the only launcher PR to
  track. Pin back to upstream `master` when it merges.
- `.gitmodules` now points at `RetroPortingToolKit/*`. Note that
  `git submodule sync` rewrites each submodule's `origin` URL from that file, so
  it will overwrite a fork `origin`; both submodules keep the fork reachable
  under a second remote (`psxrecomp` → `origin` fork + `upstream` org;
  `recomp-ui` → `origin` org + `fork` fork).
- **Open fork branches: none.** The walk-HLE prototype `d725af45` (the refuted
  `fix/vblank-cadence-pacing`) was retired 2026-09-05; its two reusable mechanics
  live in [`vblank-pacing-bug.md`](vblank-pacing-bug.md) → *Reusable mechanics*
  and the commit is parked on the fork as `archive/vblank-intrp-hle-prototype`.
- **`PSX_STARVATION_TIMEOUT_US=0` can now be cleared.** It was persisted with
  `setx` on 2026-09-02 to work around the false trips #321 fixes, and that fix is
  in this pin. `setx PSX_STARVATION_TIMEOUT_US ""` (new shell to take effect)
  puts the watchdog back — see
  [`starvation-watchdog-false-trip.md`](starvation-watchdog-false-trip.md).
- Fork branches on `kerokline/psxrecomp` that are now history (all merged):
  `fix/static-overlay-residency-signal`, `feat/present-scanlines`,
  `perf/spu-sample-event-gate`, `perf/static-overlay-parallel`,
  `feat/fast-forward-pad`, `fix/gpu-polyline-terminator`,
  `feat/fast-forward-toggle`, `feat/keymap-explicit-unbind`;
  `integrate/scanlines`, `bof3/int-fast-forward`, `bof3/int-scanlines-master`
  were local integration builds, obsolete. `fix/vblank-cadence-pacing` still
  holds the **walk-HLE prototype** `d725af45` (`PSX_HLE_INTRP_WALK=1`, 170
  lines in `dirty_ram_interp.c` / `debug_server.c`): not needed for any current
  fix, kept because its callback-dispatch mechanics are proven
  ([`vblank-pacing-bug.md`](vblank-pacing-bug.md) → Prototype lessons).
- `framework_pins.txt` is informational (and stale); the gitlinks are authoritative.

## Capture and disc extraction are not rivals

Capture supplies two separable things with opposite value here. **The bytes**:
disc extraction wins decisively — complete by construction, deterministic,
reviewable, no playtime. **The entry points**: runtime observation wins — an
executed PC with `entries > 0` is empirical proof of a callable boundary, and
nothing reached only by indirect dispatch is visible statically. So the
architecture is *bytes from the disc, entry points from play*, and that is what
the pipeline does. Every objection to capture (privacy, non-determinism,
coverage bound by playtime) attaches to the bytes; entry points are a list of
integers, diffable and additive, and a bad one is rejected by the compiler's own
validation.

One case where captured bytes would still win: if the game ever patches or
relocates overlay code *after* load, every variant of that band would miss the
CRC and fall to the interpreter silently. No evidence of this so far; the
diagnostic is a band where every variant consistently misses.

The persuasive writeup for the wider ecosystem ("The Disc Ships the Map") is a
private artifact:
<https://claude.ai/code/artifact/37f5d9d1-64c9-4db6-bb65-aad75e0ab4f4>.

## Traps paid for — do not re-pay them

Measurement:

- **Never infer success from `static_hits` or any aggregate counter.** Band 3
  looked perfect by every aggregate while `0x801CEEDC` ran fully interpreted.
  Verify per PC with `tools/harvest_interp_pcs.py` after every rebuild.
- **`overlay_loader_status` is the measurement that matters** —
  `static_checks` / `static_hits` / `static_crc_misses` — not the
  interpreted/native ratio, which is workload-dependent.
- **Measure dispatch changes on both a variant-heavy (boot) and a hit-heavy
  (savestate) workload** — they disagree in sign. `tools/headless_ab.py`.
- **`frame_perf` fps is a rolling 256-frame average** and smears stalls; use
  `all.total_ms_max` for anything stall-shaped. `frame_perf` is unavailable
  headless — use the VSync counter at `0x8018603C` via `read_ram`, and note the
  BIOS VSync counter is **frozen during the intro FMV** (use the host `frame`
  counter there).
- **Frame-number comparisons across runs are invalid** — boot phases do not
  line up. Anchor performance claims to a named screen.
- **Profile the Capcom FMV on a clean boot only.** The mid-FMV savestates
  resume *past* the FMV. `tools/fmv_bench.py` does this.
- **Guest-side counters cannot see host-side overhead.** The FMV fix came from
  gdb stack sampling of the emu thread, after two wrong guest-side theses.
  `phase_profile` mislabels static-overlay code entered from the dirty
  dispatcher as "interp".
- **Headless is uncapped**, so emulated frames per wall second is a better
  dispatch-cost metric than fps.

Pipeline:

- **The all-bands compile exits 0 with `failed=0`** (2026-09-18). This entry
  used to say it exits 2 and that this is correct, with the count drifting up
  one occupant at a time as the observed set grows (4 → 6 → 7 → 27). That was
  wrong: all 27 were one predicate — a dispatch entry admitted as a walk root
  by the weak "a `jr $ra` two words back" arm of `_callable_legacy_seed`, at
  the head of the pointer table / record array / zero fill that follows the
  image's last function, walked to the image end. Prologue-less dispatch
  entries now need `plausible_callable_target`, the same bounded CFG probe the
  discovery roots already use. **Any `[audit]` failure is now a real signal**:
  a data shape the probe does not recognise. `axis_b_loop.sh` still tolerates
  exit 2 but says so loudly. [`frameless-dispatch-roots.md`](frameless-dispatch-roots.md).
- **`harvest_interp_pcs.py` writes PCs as physical addresses.** Mask with
  `(pc & 0x1FFFFFFF) | 0x80000000` before bucketing, or everything is "unmapped".
- **Do not seed the `GAME.EMI` §0 header pointer table** — chained jump-table
  cases, not function starts; they would truncate their hosts.
- **A loader immediate is a disc-file id, not a registry id** (2026-09-08):
  `jal 0x801629CC` with `a0 = 0x125` means `MAGIC001.EMI` (file table
  `0x80182DBC`), whose registry id is `0x144`. Resolve with
  `tools/file_ids.py`; never search the ability tables for registry ids.
- **`extract_overlays.py` dedups identical sections at one address**, so a
  file can be compiled under a sibling's name (20 MAGIC files). Join
  captures by `source_md5`, not by filename — [`OVERLAY_HEADERS.md`](OVERLAY_HEADERS.md).
- **`dispatch_entry_pcs` is no longer "harvested PCs"** (2026-09-08): it also
  carries every overlay's header entry table, declared in
  `static_dispatch_entry_pcs`. Anything that wants *harvest evidence* must
  subtract that set (catalog `observed_entries` and `pc_coverage.py` already
  do). The overlay header table is a different thing from the GAME.EMI §0
  table above: exported function entries, not jump-table cases —
  [`OVERLAY_HEADERS.md`](OVERLAY_HEADERS.md).
- **Seeding the boot EXE is a dead end, proven three ways** — byte-identical
  generate at 523 vs 868 seeds; interior seeds alias into zero-fill parents;
  static code has `entries = 0` ([`OVERLAYS.md`](OVERLAYS.md) §3).
- **Compare discs by content hash, not size** (972 vs 368 changed sections),
  and **section destinations are region-specific** — select by destination
  *within* a region ([`regional-builds.md`](regional-builds.md)).
- **Band 2's compiled region is `0x80093800`–`0x800B4003`**; `0x800C1800` is a
  different band.
- **OV-1 does not apply to the static path.** The CRC gate *is* the dispatch
  condition, so stale code cannot run; multi-occupant bands need no
  register/unregister mechanism. The DLL loader that has the OV-1 defect is
  inert here.
- **Do not build residency detection for the relocated BIOS handler by
  matching ROM bytes.** OpenBIOS rebuilds the exception handler in RAM at boot
  (diverges from the ROM image at `0x27DC`), so no ROM-compiled function can be
  entered at `0x27AC`. Also not needed — that handler was never the FMV cost.

Runtime:

- **The "crashes" are the starvation watchdog** (`exit(2)` after 4 s,
  `exit_origin: "unknown"`). `PSX_STARVATION_TIMEOUT_US=0`.
- **Two ~87 MB freeze dumps at every boot.** Prune them.
- **The launcher is the default.** Use `--game game.toml --no-launcher
  --debug-port 4370`, or the exe sits waiting for a GUI click. Prefer
  `tools
un_dbg.cmd` (`relprof` / `--launcher` / extra args pass through): it
  runs the exe under a classic `conhost.exe` window so a Windows Terminal crash
  cannot take the game down, keeps stderr in `build-*/stderr.log`, and holds the
  window open on a non-zero exit. A bare `conhost.exe <exe> …` typed into a
  terminal loses the startup error with the window (2026-09-02 20:49 attempt:
  exited before any guest code, `frame 0`, reason lost).
- **PowerShell has no inline env-var prefix**; use `$env:VAR = "x"` then run.
  Git Bash env prefixes do not reliably reach the native child either — run the
  exe from PowerShell.
- **Scanlines are a per-build-tree setting.** `[video] scanlines` /
  `scanline_strength` live in each tree's `settings.toml`, and the runtime only
  writes those keys back once it has seen them, so a tree that never had them
  defaults to off. "Scanlines went missing" after a rebuild (2026-09-01) was
  `build-dbg/settings.toml` lacking the keys, not the pin. Verify over TCP with
  `{"cmd": "scanline"}`. Also: `build-dbg` (-O0) runs the intro FMV at ~40
  vblank/s windowed and always will — judge the intro on `build-relprof`.
- **`playsession.send()` takes a dict**, not a string.
- **In-game savestate slot N is file `slotN-1`.** Load with Enter/Start; the
  windowed TCP `state load` wedges the listener (it works headless — that is
  the starvation watchdog, which `scene.py` disables). Savestates carry a
  build stamp and are refused outright when it mismatches, with **no reason
  over TCP** — run `python tools/scene.py preflight` to see why offline, then
  re-save rather than investigate; every anchor is minutes from boot
  ([`SAVESTATES.md`](SAVESTATES.md)).
- **Kernel-RAM `jalr` targets can fail-fast** once (`0x00002934`, not
  reproduced) — [`crash-kernel-ram-2934.md`](crash-kernel-ram-2934.md).

## Tooling

| Tool | Use |
|---|---|
| `tools/axis_b_loop.sh` | **The Axis B loop in one command** (harvest → extract → LOGO merge → catalog → hash → compile → build). Gates on 0 new PCs (`--force`) — that gate means "nothing new to compile", **not** "the set is complete"; for completeness read `pc_coverage.py`. Tolerates only the benign exit-2 shape, refuses to link a running exe. **Re-prints the `pc_coverage.py` table as the last thing it prints on every path** (including both early exits), so the number that decides whether to keep playing survives the compile/link scrollback. `--harvest-only`, `--skip-harvest`, `--skip-hash`, `--no-mixed`, `--no-coverage`. |
| `tools/harvest_interp_pcs.py` | Live run → interpreted/native ratio + proven interpreted entry PCs, **unioned** into `analysis/observed_interp_pcs.json` with per-row session incidence (`--session`, `--area`); prints estimated coverage. |
| `tools/pc_coverage.py` | Chao2 coverage estimate over the observed set, stratified `--by band` (default) / `area` / `none`. The Axis B **stop condition** — replaces "0 new PCs". `--json` for the full report. |
| `tools/extract_overlays.py` | `.EMI` survey → `overlay_captures_all.json` with static roots + observed entries. Reads the observed file by default. |
| `tools/extract_logo_overlay.py` | `LOGO/LOGO.EXE` (a PS-EXE at `0x801CE000`) → `static-emi-v1` capture; `--append-to` the all-bands file. |
| `tools/harvest_logo_handlers.py` | Locate runtime-populated function-pointer tables statically, read them live, emit every handler as a dispatch entry. |
| `tools/enrich_pcs.py` | Explain an observed PC: occupant, boundary, disassembly, linked calls, callers; `--group` subsystem breakdown. |
| `tools/overlay_catalog.py` | Offline catalog sidecar → `analysis/overlay_catalog.json` (overwrite, not merge). |
| `tools/emi_survey.py` | Walk every `.EMI`, hash every section, code-test RAM-bound ones → `analysis/emi_sections.json`. Per region. |
| `tools/fmv_bench.py` | Clean-boot headless FMV benchmark (vblank/present window) with optional gdb sampling of the emu thread. |
| `tools/headless_ab.py` | Headless A/B on a savestate workload (skip the load step for the boot workload). |
| `tools/interp_bench.py` | **Per-scene interpreted-work A/B**: `scene.py run --slot N -- python tools/interp_bench.py --port {port} --label A --slot N` appends one row (interp insns/frame, address misses/frame, emu fps); `compare FILE A B` prints the per-slot ratio table. Wall-clock independent, so it compares builds. |
| `tools/interp_bucket.py` | **Where the residual interpreted work is**: buckets `dirty_ram_stats.per_pc` deltas by region (kernel / boot EXE / band) over a window and lists the hottest PCs with `occ_crc`. The bench says how much, this says where. |
| `tools/file_ids.py` | **Disc-file id → path** from the boot LBA table `0x80182DBC` (the loader's argument space): `python tools/file_ids.py 0x262` → GAME.EMI; `--name MAGIC0` reverse; writes `analysis/file_ids.json`. |
| `tools/enemy_table.py` | **Every area's enemy species table off the disc**: the `0x800E4000` section of each `AREAnnn.EMI`, 8 records with the 8-byte name at `+0x48` and stats at `+0x54`; `extract` → `names/enemies.toml` (448 rows, 168 species), `--us-cue` adds the US disc's own 8-character in-game name (`us`, all rows; the wiki's titles in `names/enemy_gloss.toml` are editorial and wrong on 13, two swapped), `show AREA048`, `species` |
| `tools/audio_banks.py` | **Every audio triplet on the disc, decoded**: the (6, 8, 7) sections are a VAB header, the cue-table entries the file installs at the head of its bank, and the VAB body; `show FILE` prints one file's sheet (cue → tone → VAG, sizes, md5, catalogue label), `index` writes `names/audio_banks.toml` (901 triplets, 833 distinct samples), `join --apply` stamps each labelled sound in `names/se_cues.toml` with its disc homes (`FILE.EMI#bN#vagM`), `names --apply` gives all 833 samples a deterministic `auto` name (owner file's ability / area / character + VAG number) |
| `tools/se_watch.py` + `tools/se_resolve.py` | **Sound catalogue**: every `SE_Play` call live via a write trace on its two stores (bank then id, no plugin), each cue **resolved to the sample it plays** (cue entry → libsnd VAB registry → VAG → SPU RAM bytes, hashed); `--label` asks what you heard and writes `names/se_cues.toml` keyed by sample md5 with every `cue@context` it arrived through. Cue words are slots that spells / areas / party loads re-point (SOUND_CUES.md). Runs beside `area_poller.py` |
| `tools/resident.py` | **Resident overlay set from the header words**: one u32 per band base, validated against the 405 registry ids, plus the loader's file-id cell and the area number; `--watch` prints on change. Library for `area_poller.py`. |
| `tools/load_watch.py` | **File-load timeline**: write trace on `0x80146464` = every `File_LoadRequest` with file id → path, caller `ra` (nearest known name), `a0..a3`; `--press/--hold` to drive a round; appends `analysis/load_timeline.jsonl`. |
| `tools/magic_map.py` | **Ability → BMAGIC overlay** off the engine tables `0x800B3450` / `0x800B3538` → `names/magic.toml`; `--alias-overlays` writes the spell names into the BMAGIC rows of `names/overlays.toml`. |
| `tools/scene.py` | **Headless scene harness** — boots the runtime, lands it on a savestate, proves the guest resumed, and hands the live debug port to any other tool (`{port}` / `PSX_SCENE_PORT`). `preflight` checks every `.pst` header offline against this build (names a stale slot before a 13 s boot is spent on it); `check` boots+loads+resumes every slot as the savestate regression test; `run --slot N [--press ...] [--shot p.png] [-- CMD]` is the one to reach for. Every load is followed by a VSync-advance check, so a wedge is reported as a wedge instead of a `last_ok: 1` poisoning the next measurement. |
| `tools/verify_msgtable.py` | Walk the message table on a running game. |
| `tools/mednafen_ctl.py` | Drive the stock Mednafen oracle in `./mednafen/`: `launch --card` boots from our `card1.mcd`, `press`/`hold`/`key` inject pad and hotkeys via scancodes read from its cfg, `snap`, `state save/load`, `frame`, `card export`, `quit`. See [`MEDNAFEN.md`](MEDNAFEN.md). |
| `tools/playsession.py` | Debug-server wrapper: status, screenshot (`--renderer software`), savestates, traces. |
| `tools/save_tool.py` | **Save-file reader/verifier** over raw card images (`saves/*.mcd`, `*.mcr`): `list` (slots, SJIS title, checksum OK/BAD, play time, lead level, zenny, party), `dump SLOT` (summary block, all eight character records with the BATTLE_RAM offsets and kana-decoded names, equipment, the four ability lists, inventory by category, key items, slot summary — **item / ability / character names from `names/*.toml`** since 2026-09-05; `--raw` hexdumps the unlabelled ranges), `verify` (u16 byte-sum + every load-screen cross-check + title parse + the table cross-checks: every id is a record, ability list ↔ table type, ATK = base + weapon power, DEF = base + armour powers), `diff A B` (byte runs annotated with the RAM map; `--file2` for a second card). Read-only. Any FAIL is a RAM-map bug. |
| `tools/text_tables.py` | **Id→name tables off the disc** ([`TEXT_TABLES.md`](TEXT_TABLES.md)): `extract` reads the five item tables, the ability table (GAME.EMI), the MTEST place list and the roster (COMMU02 / START templates) through the `.cue` into `names/items.toml`, `abilities.toml`, `places.toml`, `characters.toml` with the wiki glossary's English; `show TABLE` prints one. Refuses to write if a table's count moves. `save_tool.py` reads the sidecars (`--names`). |
| `tools/font_sheet.py` | **The single-byte encoding, off the disc** ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "The single-byte codes"): de-interleaves `BIN/ETC/ENDKANJI.EMI` section 0 into the 21-cell x 12 px atlas, applies the mapper's index rules (`byte`, `byte + 0x23`, `0x15 nn + 0x5B`), and writes [`names/font.toml`](../names/font.toml). `render` produces the labelled sheet to re-check a row by eye; `show <hex>` blows up one glyph. **`kanji` (2026-09-10): the kanji proof page** — every `0x12xx`/`0x13xx` cell of ENDKANJI section 1 beside the kanji `names/kanji.toml` claims, drawn in MS Gothic, `analysis/font/kanji_proof.png`; the check that would have caught `0x1354` (冒 for 探) and `0x132C` (賃 for 代) at transcription time. All 441 cells eyeballed against it 2026-09-10: no further mismatch. |
| `tools/page_rows.py` | **How the script uses the box** ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)): `rows` = lines-per-page census split by which page break ended the page (`0x02` confirm, `0x16` timed), `codes` = control-code frequency with argument histograms, `styles` = every `0x0F` text-effect use resolved against the preset table read out of the boot EXE. Counts distinct messages, not table slots. |
| `tools/ruby_fit.py` | **What inline furigana costs, in rows** ([`FURIGANA.md`](FURIGANA.md)): `width` measures the box line capacity from shipped content, `cost` gives rows-before against rows-after for two layout policies and three annotation scopes, `sample` renders one page three ways. Readings from SudachiPy mode C with okurigana trimmed. |
| `tools/plates.py` | **World-map name plates** ([`TEXT_TABLES.md`](TEXT_TABLES.md) "World-map plates"): decodes each world map's 8-bit texture page (tiled section `dest 0x0E001000`, CLUTs from `0x8002BE00`) off the disc, finds the painted place-name plates by their rim, joins the ones that wrap at texel 256, writes `analysis/plates/` (page PNGs, `plates.json`, a contact sheet). Transcriptions live in `names/plates.toml`. |
| `tools/pst_tool.py` | Read `.pst` savestates offline: `info`, `vram` (1024×512 PNG), `ram` (raw 2 MB), `diff A B` (VRAM zero-map, per-block diff map, blocks that went populated→zero, RAM diff ranges). Compare two states without loading them into a running game. |
| `tools/emi.py`, `tools/disc_ls.py`, `tools/disasm_exe.py` | Parse/extract `.EMI`; list the ISO9660 tree; disassemble the boot EXE with MMIO naming. |
| `tools/name_map.py` | `names/` sidecars (overlays / functions / areas): `init` merges new catalog overlays (never overwrites hand edits), `check`, `stats`. See [`NAME_MAP.md`](NAME_MAP.md). |
| `tools/regions.py` | `names/regions.toml`, the sidecar for RAM *spans* (eleven overlay bands, the two message pools, the insert scratch array, the EXE image, the kernel area): `seed` merges rows derived from the committed sources and keeps hand edits, `check` re-derives and exits nonzero on drift, `list` prints widths and the two real overlaps. `end` is exclusive and `bound` says what it is — a measured occupant span, a zero-fill window, or a documented block end. See [`ADDRESS_MAPS.md`](ADDRESS_MAPS.md). |
| `tools/xref.py` | Joins addresses cited in prose to the naming layer, offline, from committed files only (`analysis/` not needed): `lookup <addr>` for identity + every doc citing it, `index --out docs/XREF.md`, `queue` for cited-but-unnamed ranked by how many docs discuss it, `shared` for addresses two or more docs discuss, `stats`. Scans `docs/` **recursively** (so `loader_records/` counts) and resolves engine loader entries out of `names/*_records.toml` via `extract_overlays.py ENGINE_RECORD_FILES`. Reports the region and the nearest named entry below; never guesses code vs data. See [`ADDRESS_MAPS.md`](ADDRESS_MAPS.md). |
| `tools/subsystem_map.py` | Regenerates [`subsystem_map.html`](subsystem_map.html): bands → overlays → functions, boot EXE, areas, search. No bytes embedded. Phase 6 of the loop. |
| `tools/run_dbg.cmd` | Launch build-dbg (or `relprof`) under legacy conhost, stderr to `build-*/stderr.log`, window held open on failure. |
| `tools/area_poller.py` | `watch` during play (resident AREA by script-block md5, settled screenshot, native-ring compression, timed interp-PC harvest every 15 min + on Ctrl-C so a dead game costs ≤ one interval), `harvest` at end of session (loop phase 2a), `summarize --apply` → `names/areas.toml` + evidence. |
| [`BATTLE_RAM.md`](BATTLE_RAM.md) | **Battle RAM map + damage path** (2026-09-04): enemy records `0x801EB634+n*0x118`, party `0x80145F0C+m*0x140`, HUD gauges `0x801484B8+n*0x24`; `Battle_ApplyDamage` → `Battle_CalcDamage` → `Battle_BaseDamage` with the variance table and `Rand`. The loop that produced it: `callstack_diff.py ramdiff` (damage read afterwards, `ramfilter --intersect`) → `capture --watch` → `ghidra_run.py export --decompile` → `name`. |
| `tools/ghidra_run.py`, `tools/ghidra/*.py` | **Headless Ghidra driver** ([`GHIDRA.md`](GHIDRA.md)): `import` an overlay section from `overlay_captures_all.json` as its own program (seeded from the recompiler's roots), `export` every program to `analysis/ghidra/<program>.json` (functions, cop2 flag, callees, globals r/w, cross-band refs, jump tables, constant-`a0` call sites, optional decompile), `report`, `merge` → `names/functions.toml`. GUI must be closed (project lock). 2026-09-04: boot EXE + both BATTLE.EMI code sections exported; `Battle_FrameTask` / `BattleMenu_TargetCursor` promoted to `evidence` from the bodies. |
| `tools/callstack_diff.py` | **Differential call-stack tracer** (IDEAS I1 / NAME_MAP route 3): `capture` loads a savestate, arms `fn_filter` (sent physical — the server does not mask KSEG0), presses one button, drains the fn entry/exit rings and rebuilds the call forest with the resident area md5 + native-ring body CRCs; `tree`, `diff --prefix` (Attack vs Defend set difference, common-prefix = `Battle_Init` candidate), `propose --apply` upserts `hypothesis` rows into `names/functions.toml` (refuses ambiguous mixed-band occupants without `--overlay`). `--dry-run` drains the rings read-only. |
| `tools/export_seeds.py`, `tools/ghidra_seed.py` | Kept for the record — the seed experiments were null. |

## Open questions

- ~~The ~15 KB string table inside `GAME.EMI` §0 — nobody has read it.~~
  Read 2026-09-17: it is the item/ability name tables of `TEXT_TABLES.md`,
  now paired with the US disc's names (`text_tables.py --us-cue`, `us` column
  in `names/items.toml` / `abilities.toml`).
- **The BIOS exception handler interprets on both BIOSes** (Psy-Q kernel patches unbless it; 44.6 % of all interpreted work) — [`kernel-patch-sites.md`](kernel-patch-sites.md), upstream asks listed there.
- Why `DEMO.EMI` §5 ships the JP image on the PAL English disc.
- Whether the Western builds use proportional glyph advance.
- ~~**211 of 8,694 dispatch addresses are zero-fill**~~ — **RESOLVED 2026-09-06**,
  [`zero-fill-dispatch-audit.md`](zero-fill-dispatch-audit.md): 182 of the 211
  are now compiled as real overlay code, the dispatch guard is sound against the
  rest, and the entry-word metric that suggests 275 misclassifies 64 NOP delay
  slots as fabrications.
- Text paths not yet seen live: a shop, an equipment menu, battle text.
- ~~`--include-mixed`~~ — **RESOLVED 2026-09-04, mixed is now the default.**
  See "Mixed sections are extracted by default" below.

## Environment

See [`STATUS.md`](STATUS.md) → Environment. Short form: `python` not
`python3`; prepend `/c/msys64/mingw64/bin`; run the exe from PowerShell with
`$env:`; Ghidra project at `D:\Utilities\GhidraProjects\BoF3`
(`analyzeHeadless.bat` cannot run `.py` — use `python -m pyghidra.ghidra_launch`);
prior decode work at `D:\BoFIII` (open the JSON as UTF-8).
