# Ideas catalog — proposed improvements, with feasibility

**Status:** IN PROGRESS (opened 2026-09-04). Each entry records what was
asked, what in the tree already serves it, what is missing, a feasibility
rating, and the first concrete step. Nothing here is scheduled. Enhancements
with a design go to [`ENHANCEMENTS.md`](ENHANCEMENTS.md); naming/readability
routes go to [`NAME_MAP.md`](NAME_MAP.md); this file is the intake.

Ratings: **HIGH** = host tooling only, all inputs exist; **MEDIUM** = tooling
plus one unknown that a short investigation settles; **LOW** = needs runtime
code that must land upstream first, or an enhancement-phase gate.

Line numbers were taken against the 2026-09-04 pins and drift; re-verify.

---

## I1 — Map combat functions to call stacks

**Outcome (2026-09-05):** done and superseded by the data-anchor loop (HANDOFF section 0, [`BATTLE_RAM.md`](BATTLE_RAM.md)); 46 named functions, the damage formula, level-up, inventory and the save format came out of it.

**Ask (2026-09-04):** actively map combat functions to call stacks so the
different combat calls can be deciphered.

**Kind:** host tooling. **Feasibility: HIGH.**

### What already exists

- The runtime keeps an always-on **function entry/exit trace** in
  debug-tools builds: `fn_entry_dump` / `fn_entry_tail` / `fn_exit_dump`
  over two 262 144-entry rings
  ([`debug_server.c:1150`](../psxrecomp/runtime/src/debug_server.c),
  handlers at `:11644`). Each entry carries `func`, `ra`, `a0–a3`, `t1`,
  `s0–s3`, **`depth`** (a shadow stack), `frame`, and a paired
  `exit_seq`; each exit carries `v0`/`v1`. `fn_filter lo/hi` restricts
  capture to an address range (the BATTLE band, say) so the ring is not
  flooded by the boot EXE. That is a call-stack recorder; it just has no
  BoF3-side consumer yet.
- The entry stamp is emitted at the top of every recompiled function,
  including statically compiled overlays
  ([`full_function_emitter.cpp:1614`](../psxrecomp/recompiler/src/full_function_emitter.cpp))
  and the overlay CPS path ([`overlay_loader.c:2258`](../psxrecomp/runtime/src/overlay_loader.c)).
  `build-relprof` has `PSX_DEBUG_TOOLS=ON`, so it works on the play tree.
- Savestate anchors for differential runs exist ([`SAVESTATES.md`](SAVESTATES.md));
  NAME_MAP route 3 ("differential traces → behaviour classes") already
  describes the method and states the tool is not written.
- Static in-overlay `jal` edges are in `analysis/edges.json` and rendered
  in [`subsystem_map.html`](subsystem_map.html); `tools/enrich_pcs.py`
  explains a PC (occupant, callers, disassembly).
- `names/functions.toml` is the sink for earned names, keyed by
  (overlay md5, pc) — see [`NAME_MAP.md`](NAME_MAP.md).

### What is missing

**2026-09-04 → exists and live-tested.** `tools/callstack_diff.py`
(capture / tree / diff --prefix / propose --apply). First real run: a battle
anchor saved to **file slot 10** (in-game 11) at the command menu, then
`capture --slot 10 --press circle ×6` (Attack for all three, full round)
and `capture --slot 10 --hold right --press circle ×3` (Defend). Both
~85 k entries over 240 frames in `0x801CE400–0x801F2C00`. Result:
13 functions only in Attack (the `0x801D8060` cluster + `0x801E9538` /
`0x801E9A50` / `0x801E995C`, firing every frame with constant args from the
first menu frame — the highlighted-icon drawing, not the command), 4 only
in Defend (`0x801D2198` on the Right press; `0x801EF554` / `0x801EF9C4` /
`0x801EFA84` at the last window frame — the defend action starting),
185 common. The per-member pattern is real but in the common set:
`0x801DB4EC` is called with actor 0, 1, 2 every frame from `0x801E6C60`.
Captures live in `analysis/callstacks/` (gitignored).

Four things the run corrected in the tool, all paid for:

1. **Filter form.** The entry stamp at the top of every compiled function
   passes the KSEG0 address and the filter compares raw, so a KSEG0 range
   catches every compiled-function entry; the physical form matches only
   the `psx_dispatch` path and recorded **0 entries over 146 battle
   frames**. Default is KSEG0 now (`--phys-filter` for the old form).
2. **Nesting by `ra`, not `depth`.** The ring's `depth` is the dispatch
   shadow stack, which direct stamps never pop (it read 31, 62, 93 …), and
   exits are only recorded on the dispatch path. The tree now nests by the
   function containing `ra` (observed funcs + `static_discovery_entry_pcs`;
   `dispatch_entry_pcs` are excluded because they include jump-table
   interiors that fragment functions). Entries whose `ra` lies inside their
   own function are CPS continuations (48 k of 83 k) and are attached
   without nesting. Roots are grouped by their untraced caller — the whole
   battle is `0x80159828` (boot EXE) → `0x801E8FAC` once per frame.
3. **Presses are a sequence** (repeat `--press`; `a+b` holds together),
   and **`--hold`** keeps buttons down across the sequence: the battle
   command menu is a hold-direction menu — Defend is selected only while
   Right is held, release snaps back to Attack, so the first "Defend" run
   was three Attacks (diff: 1 function).
4. **Common prefix is not usable across runs** (0 entries): the first
   frame's entry order differs with input timing. Alignment on the first
   input frame is the fix if `Battle_Init` is wanted from this route.

**Three-way run, 900-frame window (same session).** `venn` over Attack
(Circle ×6), Defend (`--hold right`, Circle ×3) and Watch (`--hold left`,
Circle ×6), ~230 k entries each — 900 frames is the ceiling for this band
before the 262 144-entry ring wraps:

| membership | n | reading |
|---|---|---|
| attack only | 22 | the attack executing: `0x801DFA04` (x36, 19 distinct a0) with `0x801DF9D0`/`0x801DFB18`/`0x801E3AE0`–`0x801E42C0`, frames +544..+1042 |
| defend only | 11 | the defend action: `0x801E0400`/`0x801E0434`/`0x801E04B4`–`0x801E06C8`, frames +556..+736 |
| attack + watch only | 24 | **target selection** — the `0x801D8060` cluster fires every frame from the first menu frame in both, and Defend (no target) never touches it. This corrects the 240-frame reading above, which called it the highlighted-icon draw |
| attack + defend only | 11 | an "action resolves" set Watch lacks (`0x801DBB40`, `0x801DC00C`, `0x801DCAA0` once each) |
| defend + watch only | 4 | `0x801D2198` once at +3/+4 frames = the held Right/Left that selects those commands |
| watch only | 0 | Watch has no code of its own until an enemy move happens — see the trigger captures below |
| all three | 225 | the battle loop and per-actor updates |

**Watch trigger, two captures (file slot 11, saved twice against different
enemies, no input, 900 frames).** 12 functions are in both trigger runs and
in none of the three command rounds, with the same shape nine frames apart,
so they are the Examine (みる) logic and not the enemy: `0x801D10DC` every
frame while Watch is armed; `0x801E6A68` once at +30/+39 then the
`0x801E69E0`–`0x801E6B58` cluster for ~45 frames = the question mark;
`0x801EF188` once at +124/+133 then `0x801E2500` (x10) and
`0x801E5230`/`0x801E524C` through +412/+421 = the observed enemy skill
(Nu Stomp) playing under Watch; `0x801E00EC` once at +440/+449 = the
learn check before the cannot-learn message. Player-reported sequence:
question mark → enemy skill → message. **Watch's own code only runs when an
enemy move happens while it is armed** — a plain Watch round has none of it.
Six more `hypothesis` rows (`Examine_*`) written. The intersection of two
trigger captures against different enemies is the pattern to reuse: one
capture per phenomenon is not enough in a mixed band, two with different
noise are.

**Resident overlay.** The native ring was empty at capture time and the
band's data tail is modified at runtime, so an exact md5 never matches;
`capture` now stores the longest RAM-prefix match against the captured
section bytes per band: `0x801D0C00` = BATTLE.EMI#3 (`8a80230e…`, the
Battle game-mode overlay already `evidence` in `names/overlays.toml`,
108 544 of 118 080 bytes), `0x801CE400` = PLP034, `0x801EEC00` = MAGIC069.

**Names written** (`names/functions.toml`, all `hypothesis`, overlay
`8a80230e…`): `Battle_FrameTask` `0x801E8FAC` (once per frame from boot EXE
`0x80159828`), `Battle_ActorFrameUpdate` `0x801DB4EC` (a0 = actor 0/1/2),
`BattleMenu_TargetCursor` `0x801D8060`, `BattleMenu_DirectionHold`
`0x801D2198`, `Attack_Action` `0x801DFA04`, `Defend_Action` `0x801E0400`.
Promotion to `evidence` needs a second route (Ghidra read of the body, or a
data anchor such as HP writes under `Attack_Action`).

A `tools/callstack_diff.py` that: loads a battle-menu savestate, arms
`fn_filter` on the battle bands (`0x801D0C00` BATTLE game-mode,
`0x801CE400+` PLCHAR/BOSS, the `BMAGIC`/`BENEMY` bands per
[`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md)), injects one input
(Attack), drains `fn_entry_dump` for the frame window, rebuilds trees from
`depth`/`ra`, and diffs against the same run with Defend. Output: per-input
call trees with args and return values, written as `hypothesis` rows into
`names/functions.toml` with the trace as evidence.

**Second route + data anchors (2026-09-04, later).** Two additions close
the "promotion needs a second route" gap:

- `tools/ghidra_run.py` ([`GHIDRA.md`](GHIDRA.md)) imports the battle
  sections into the Ghidra project headless and exports bodies. First reads
  promoted `BattleMenu_TargetCursor(x, y)` and `Battle_FrameTask` to
  `evidence`, showed the traced roots are table dispatchers on a battle
  context whose pointer is in scratchpad `0x1F800044`, and found 4 of the
  12 traced PCs are interior stamps (the enclosing Ghidra function is the
  unit to name; `known_starts()` now unions Ghidra's entries).
- `callstack_diff.py capture --watch LO-HI` arms the runtime write trace
  during the window and attributes each store to the compiled function
  containing its PC; `writes` reports per-address writers and value
  transitions; `ramdiff --delta -37 --width 2` finds the HP cell from the
  damage number on screen with no RAM map (the community data doc has no
  RAM chapter yet); `name` upserts one row. The intended run: `ramdiff` on
  an Attack anchor → `capture --watch <hp cell> --watch <ctx>` → the writer
  under Attack is the damage-apply function → `name ... --status evidence`.

### Traps, already paid for elsewhere

- **Band sharing.** `0x801D0C00` is a mixed band; a bare function address
  does not identify the occupant. Join each trace against the resident
  overlay (script md5 from `area_poller.py`, body CRC from the overlay
  native ring) before writing a name.
- **Interpreted code is invisible to the ring.** Only recompiled functions
  stamp an entry, so any battle PC still missing from
  `observed_interp_pcs.json` is a hole in the tree. Run the Axis B loop on
  the battle content first ([`HANDOFF.md`](HANDOFF.md)), or the tree will
  have unexplained jumps in `depth`.
- **Ring capacity.** 262 144 entries is well under a second of a hot
  battle loop with no filter. Always set `fn_filter`, and drain within a
  few frames of the input.
- Ghidra is the second route for static call graphs, but the ghidra-mcp
  bridge found no running instance on 2026-09-04; the project is
  `D:\Utilities\GhidraProjects\BoF3` ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)).

### First step

Write the tracer against battle savestate anchors, prove one differential
(Attack vs Defend) yields a stable set difference across three battles,
then name `Battle_Init` from the common prefix.

---

## I2 — Map the world-map "guide" text to the area it describes

**Ask (2026-09-04):** link the location/guide information the map shows to
the AREA file it describes, programmatically.

**Kind:** host tooling. **Feasibility: HIGH** — upgraded from MEDIUM after
the live test below (2026-09-04): the unknowns are settled, and every input
the poller mode needs is a documented global or an existing corpus.

### What already exists

- `names/areas.toml` maps AREA script-block md5 → human alias, but today
  the alias is **typed by a person** reading a screenshot
  (`area_poller.py watch` pauses and prompts). The area identification
  itself is already certain and programmatic (script-block md5).
- The text engine is pinned: the immediate string draw is
  `0x8015AD34(x, y, str)` and the dialogue box reads its string from
  `0x801490A8` ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)). Whichever path draws
  the map label, the **string pointer is in a register or a known global**
  at a known function entry.
- The fn-entry ring (I1) records `a2` at every `0x8015AD34` entry with a
  frame stamp, so the label text is recoverable without OCR: filter on
  that function, read the bytes at `a2` via `read_ram` (or
  `read_frame_ram` for the exact frame), decode with
  `D:\BoFIII\decode_text.py` (435/435 character table).
- `area_timeline.jsonl` already stamps every area transition with a frame,
  so a decoded label seen in the frames just before a transition joins to
  the new area's md5 by frame order.
- The 11 491-line JP/EN corpus (`D:\BoFIII\_claude_work\pairs.json`) and
  `extract_menu_text.py` (non-dialogue pools) give the English side for
  free when the label string also appears there.

### Live test, 2026-09-04 — settled

Run against the playing `build-relprof` session (debug port 4370) with the
player opening guides on the Yraall world map and entering Mt. Glaus.
Everything below was read from the machine, not inferred.

**Where the guide text lives.** The world map is itself an area
(`BIN/WORLD00/AREA016.EMI`, alias "World Map - Yraall Region - Spring"),
and its `0x80010000` script block holds the map's own strings: slot 4 is
the region label (`ウールオル地方`, "Yraall Region"), slots 2–3 are node
labels (`シーダの森` Cedar Woods, `西 ダウナ鉱山` West Dauna Mine), and
**slots 5–16 are the guide paragraphs**, one per node (5 Cedar Woods,
6 the forest toward Mt. Glaus, 7 Mt. Glaus, 8 McNeil village, 9 McNeil's
land, 10 the highway, 11 the mountain road, 12 the hut, 14–16 post-arrest
variants). The aligned corpus `D:\BoFIII\_claude_work\pairs.json` already
carries slot-for-slot English for the whole block (`AREA016/AREA016.11.bin`,
33 rows) — so the English side costs nothing.

**How the guide is shown.** Through the dialogue-box interpreter, not the
immediate draw. The world-map overlay code at `0x801F2E6C` (WORLD band,
AREA016 section 13) calls the boot-EXE **message resolver `0x8015034C(a0 =
message index)`**, which computes `0x80010000 + u16[0x80010000 + 2*idx]`
and writes it to `0x801490A8`/`AC`, then stores the index to
**`0x801490A4`**. Observed at frame 171998: `a0 = 7`, pointer
`0x800102A7`, decoded `険しいので あまり人が 近づく事のない山 / かつて ヌエが
住んでいた` = Mt. Glaus. The stepper `0x8015096C` then advances `0x801490AC`
one glyph every 6 frames (pc `0x80150F04`) and the renderer `0x80150598`
rewrites the cursor at `0x801490B8/BA` every frame; box origin was
(70, 176). A second resolver `0x801503AC` serves the `0x80014000` system
pool via `0x801503F8` (`W` header + `idx & 0x3FFF`), confirming the two
block shapes in [`TEXT_ENGINE.md`](TEXT_ENGINE.md).

**The map label.** The per-frame region label is drawn by `0x801F4154`
calling the glyph wrapper `0x8014F6BC(x=96, y=205, pal, 1, str)` with
`str = 0x80010000 + u16[0x80010008]` (slot 4); the string pointer is
visible as `v0` in the write-trace entry for the wrapper's `x` store at
`0x80145AC6`.

**The transition.** Entering Mt. Glaus from that guide loaded
`BIN/WORLD00/AREA023.EMI` (script md5 `6dd6f45b…`, already aliased
"Glauss Mountain - Fall" from a screenshot) — the same md5 route
`area_poller.py` uses, read ~4 s after the fade.

**What did not work, so nobody repeats it.** `fn_filter` on `0x8015AD34`
caught nothing in either address form: the immediate draw is not on this
path at all. The fn-entry ring also has two address conventions — direct
`jal` stamps carry the KSEG0 `0x80…` address, dispatched calls carry the
physical one — so a single `lo/hi` cannot cover both (recorded in I1 too).
The **write trace** is the better instrument here: `wtrace_add` on
`0x801490A0–C0` (interpreter block) and `0x80145AC0–D0` (glyph globals)
catches every text event with writer PC, `ra`, args and frame, at
`wtrace_dump addr_lo/addr_hi` cost only. Note `wtrace_dump` with the
box open is dominated by cursor writes; filter to `0x001490A4–AC` to see
only index/pointer sets.

### The mapping, programmatically

```
guide open : write to 0x801490A8 with ra in the resident WORLD band
             → (world-map area md5, message index a0)
             → JP = decode(u16 table walk), EN = pairs.json[blk, i]
entry      : next 0x80010000 script-md5 change → destination AREA file
```

**Decision (2026-09-04): no auto-label mode.** The guide paragraphs are
descriptions, not names, and the live join is only temporal (the guide
opened last before an area change) — the pointers alone never say which
area a guide belongs to. Areas keep being named by hand from the screenshot
in `area_poller.py watch`. The poller-mode spec above is kept as the record
of what was tested.

**TODO — decode the world-map node table (static, no play needed).** The
map code walks section 12 of the world-map area (`0x80104000`, 53 324 bytes
in AREA016; the map code reads it at `0x801F46D4` / `0x801F4814`). Each node
record must carry at least its map position, its guide message index (the
`a0` handed to `0x8015034C`; index 7 = Mt. Glaus, observed) and its
destination area, because that is what the map needs when a node is
chosen. Decoding it yields **node → guide → destination AREA for all five
world maps from the disc**, explains the rest of the pointers the map code
follows, and gives every guide a `hypothesis`-grade area link that a single
sighting can promote to `evidence`. Route: start from the known values
(guide index 7, destination AREA023, label slot 4 drawn at (96, 205)) and
search section 12 for a record shape that holds them; the small section 3
(`0x800E3800`, 7 × 8-byte records after a `count, 0x0F, 0x10` header) is
the other candidate for the node list. Work it from a scratch extract
(`tools/emi.py extract … --index 12`), never from committed bytes.

---

## I3 — 1.5× dialogue box with a furigana band

**Ask (2026-09-04):** make the text feed 1.5× taller, pin the existing text
to the lower two thirds, and use the upper third for furigana (kana readings
over kanji). Premise offered: the game auto-detects text length and makes
multiple scrolls per language, so the window may be flexible.

**Kind:** three separable parts with very different costs.
**Feasibility: HIGH (readings data) / MEDIUM (box geometry) / LOW (runtime
furigana rendering — upstream framework hook + enhancement-phase gate).**

### A correction to the premise

The box does **not** auto-wrap or auto-paginate. Line breaks are control
code `0x01` and page breaks are `0x0B`, both **authored in the script**
([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Control codes"). The reason each
language paginates differently is that Capcom re-authored the breaks per
release: the `0x80010000` section is replaced wholesale, 93.4% of bytes,
and is the only section whose size changes
([`regional-builds.md`](regional-builds.md)). So the window is flexible only
in the sense that the script decides what goes in it. Any layout change is
an interpreter change, not a data change.

### Part 1 — readings sidecar (HIGH, can start now, offline)

The kanji→reading problem is mostly solved in the prior decode work:
`D:\BoFIII` carries Sudachi-based contextual readings with an adjudication
ladder (HANDOFF §12 there), `vocab_master.tsv` (1 698 words) and
`review_readings_v7.tsv`, all built over the same 5 519 distinct JP strings.
Missing: a pass that emits, **per message and per kanji span**, the kana
reading, in the same slot-aligned shape the translation table uses
(`translations/*.toml`, `psxrecomp/docs/STRING_TRANSLATION.md`). This is a
Python script with no runtime dependency and is worth doing first: it is
the input every rendering variant needs, and the readings can be reviewed
with the deck tooling that already exists.

### Part 2 — box geometry (MEDIUM, needs one investigation)

Known constants: 12 px glyph advance, **14 px line height** in the box
(`y += 0x0E` in the stepper/renderer), origin at `0x801490BC/BE`, cursor at
`0x801490B8/BA` ([`TEXT_ENGINE.md`](TEXT_ENGINE.md) "Interpreter state
block"). Pinning text to the lower two thirds is a change to the origin `y`
and possibly the per-page `y += 8` at `0x0B`; those are single immediates,
and the framework's `[[recompiler.patch]]` replaces exact 32-bit words at
build time with an `expected` guard (`psxrecomp/docs/config_schema.md`
"Recompiler block") — so the text-offset half is a config-level patch.

**Unknown:** what draws the box frame and how its height is chosen. The
renderer `0x80150598` and its caller `0x80150570` only draw glyphs; the
frame is elsewhere (likely a sprite or quad sized by a constant or by a
per-message line count). Until that function is found, "1.5× height" cannot
be costed. Static route: Ghidra xrefs from the box origin globals; live
route: `gpu_frame_dump` on a dialogue frame and match the frame quad to
its emitting PC via the GP0 attribution.

Also unknown: the glyph primitive. `0x8014F708` builds one primitive per
glyph through `0x8014FCE8` → `0x8017BC2C` / `0x8017CC50` (Psy-Q-region
helpers). Whether that is `SPRT` (unscalable) or a textured quad (UVs can be
mapped to a smaller output) decides whether half-height kana are free or
need a second, smaller font in VRAM. The atlas already holds full-size
hiragana (`0x5B+`, 12 px cells, 21 wide).

### Part 3 — rendering furigana at runtime (LOW today)

New drawing in the guest needs code that does not exist in the game, and
this repo cannot ship native code beyond the setup host: the title CMake
only takes `CODEGEN_SETUP_SOURCES` ([`CMakeLists.txt`](../CMakeLists.txt)),
mod packages cannot carry code (`MOD_PACKAGES.md` "Trusted static
plugins"), and `[[recompiler.patch]]` is single-word. The framework's text
hook (`g_psx_text_xlate_hook` at the `psx_dispatch` chokepoint,
`STRING_TRANSLATION.md` §3.4) swaps **string pointers**; it does not draw.
So furigana rendering means an upstream psxrecomp change — either a
generic "per-title draw callback at a registered PC" or a furigana feature
in the translation subsystem — followed by a gitlink bump, and it is
enhancement-phase work under the no-per-game-hacks rule
([`ENHANCEMENTS.md`](ENHANCEMENTS.md) "The gate").

**Data-only stepping stone, works through the existing hook:** emit the
readings inline as `漢字（かんじ）` in a translated script variant. Zero
engine change, but the authored `0x01`/`0x0B` breaks then overflow the box,
so the sidecar from Part 1 has to re-author the breaks (the same problem
the English translation already owns — "Line-break policy",
[`TEXT_ENGINE.md`](TEXT_ENGINE.md)). Useful for validating the readings
against real screens before any renderer work.

### Sequencing

1. Part 1 sidecar (offline).
2. Find the frame-draw function and the glyph primitive type (one session
   on a dialogue savestate with `gpu_frame_dump` + the fn-entry ring).
3. Only then cost the box geometry as `[[recompiler.patch]]` words vs an
   upstream hook, and file the design in `ENHANCEMENTS.md`.
