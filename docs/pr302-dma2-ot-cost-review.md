# Upstream psxrecomp #302 (DMA2 linked-list cost): BoF3 cross-title check

**Status:** DONE (measured 2026-09-03 against pin `adf54eaa` and against
upstream master `2da25c18`, which carries the superseding #304)

[mstan/psxrecomp#302](https://github.com/mstan/psxrecomp/pull/302) resubmits
#299 (merged and reverted the same minute as #300). It lowers the per-node cost
of the sliced ordering-table walk introduced by #277 (`8af48ae9`) from
8 clocks per header + 5 setup clocks per non-empty node to 1 + 0, so a walk
costs exactly `nodes + words`. Validated only on FF7; the PR's own review gate
asks every supported title to confirm. This is BoF3's answer.

## Verdict for BoF3

**No regression. Neutral-to-positive.** Under the current 8+5 model BoF3
never comes near the failure the PR fixes, and under 1+0 nothing new appears.

| counter (20–40 s headless window per scene) | 8+5 (pin + PR counters) | 1+0 (PR as-is) |
|---|---:|---:|
| `starts_dropped` | 0 everywhere | 0 everywhere |
| `cancels` (guest cleared CHCR bit 24 mid-walk) | 0 everywhere | 0 everywhere |
| `completes` == `starts` | yes | yes |
| `cycles_max` (largest walk seen, world map) | 21,198 = 3.8 % of an NTSC frame | 9,254 = 1.6 % |
| World map, largest OT: nodes / words → cycles | 1,002 / 9,254 → 21,198 | → 9,254 |
| Battle (turns playing), typical OT | ~650 / ~4,400 → ~12,100 | → ~4,400 |
| Merchant, busy screen | 680 / 3,808 → 11,888 | → 3,808 |
| Field (opening mine) | 763 / 6,263 → 15,339 | → 6,263 |
| CHCR(2) reads while a walk was active, per walk | ~0.5 | ~0.5 (battle/map), ~0.08 (title) |

Scenes covered (two passes, 2026-09-03): boot/title; a **battle with several
turns and effects playing** (file `slot01`, re-saved by the user on
`build-pr302`); **world map** (`slot02`); a **busy merchant screen**
(`slot03`); the opening mine field, a dialogue box and a choice prompt (older
files). Every load reported `last_ok: 1`. BoF3's ordering tables top out around
1,000 nodes and are mostly non-empty, so the empty-node header tax that hurts
FF7's 4,094-entry tables barely registers: even the world map's biggest walk
is under 4 % of a frame on the current model, versus FF7's 88 %.

The user also played the battle, map and shop on `build-pr302` windowed while
making the states; no missing or broken geometry was reported.

## Superseded by #304 (merged 2026-09-03 as `71f3c8c3`)

[mstan/psxrecomp#304](https://github.com/mstan/psxrecomp/pull/304) (Alexbeav,
"preserve live linked-list reads with word-cost timing") landed on master
before #302 was resolved. Code comparison:

| | #302 | #304 (merged) |
|---|---|---|
| Cost constants | header 1, setup 0 | **identical** (same two `#define`s) |
| Walk cost | `nodes + words` | `nodes + words` — same identity |
| Empty-OT bound test | added | **copied verbatim**, comment included |
| Payload read timing | whole packet on the header service (fall-through) | **one live RAM word per one-clock event**, `payload_index` tracked |
| Late scheduler service | one boundary per call | **loops until every elapsed boundary is consumed** |
| Widescreen prepass | untouched | fingerprints cached nodes; discards on live change; `observe_header` op |
| Old `PSX_ND_SIB_FLAP_LAST` polygon-drop hack | untouched | removed |
| Savestate format | untouched | **boot-state v6; v5 files rejected** |
| `gpu_ot` counters, cancel ring, CHCR-poll stats, `starts_dropped` | added | **absent** |
| `PSX_GPU_LL_SYNC` diagnostic lever | added | absent |
| CPU stall on RAM/MMIO reads during DMA (the hardware root cause above) | not modelled | not modelled ("does not claim to implement complete physical-bus arbitration") |

So: **same root issue, same fix for it.** #304 is a strict superset on the
timing side (per-word live reads, catch-up service) and additionally fixes
the Vampire Hunter D / Spot mid-walk mutation cases #277 was for. #302's
DMA change is fully superseded; what #302 still uniquely offers is the
observability block, which is what this census ran on. Worth salvaging as a
small counters-only PR rebased on master — the cancel ring is the only way to
*see* the FF7-class abort without a screenshot.

**BoF3 on the merged head.** Built upstream master `2da25c18` (with #302's
counters cherry-picked on top; its walker/test conflicts resolved in master's
favour) against this title's `generated/` — it configures and builds clean,
which also clears the way for a pin bump. Boot/title/attract census, 30 s:
zero cancels, zero dropped starts, `cycles == words` on every walk,
`cycles_max` 8,157 — same as #302's build. The battle / world-map / merchant
states could **not** be measured on it: #304's boot-state v6 rejects every
existing `.pst` (`last_ok: 0` on all three), so **a pin bump past `71f3c8c3`
invalidates all eleven savestate anchors** and they must be re-saved. Given
the identical cost model and the small tables, nothing in those scenes is
expected to differ.

## Method

Two scratch clones of the framework at the pin, `PSXRECOMP_ROOT` pointed at
them, RelWithDebInfo + `PSX_DEBUG_TOOLS=ON` + `PSX_STATIC_RUNTIME=ON`
(the `build-relprof` recipe):

- **1+0** — commit `8d2daa92` (the PR's only DMA commit) cherry-picked onto
  `adf54eaa`, in `build-pr302/`.
- **8+5** — same commit, then `DMA_GPU_LL_HEADER_CYCLES`/`SETUP_CYCLES`
  restored to 8/5, so the baseline carries the PR's new `gpu_ot` counters.

Each exe ran `--headless --debug-port N`; `tools/ot_census.py` loaded each
slot over TCP and sampled `dma_state` (`gpu_ot`, `gpu_ot_chcr`,
`gpu_ot_cancels`) every 250 ms for 20 s (first pass) or 40 s (second pass, so
battle turns could play out). Emulation is uncapped headless, so guest cycles are the unit;
wall-clock fps in the raw logs is meaningless. The PR's cost identity held on
every sampled walk: `cycles_last == words_last` under 1+0.

## Review notes for upstream (what the PR is missing)

1. **8+5 was not "a substituted constant with no measurement".** It is
   DuckStation's model verbatim: `LINKED_LIST_HEADER_READ_TICKS = 8`,
   `LINKED_LIST_BLOCK_SETUP_TICKS = 5` in `src/core/dma.cpp`. The PR's claim
   that 1+0 is "the validated model" only means it is what psxrecomp charged
   before #277 — also unmeasured.
2. **The real defect is CPU/DMA concurrency, not the constant.** psx-spx
   (DMA channels, "DMA Transfer Rates"): the CPU keeps running during DMA only
   while it touches cache, scratchpad, COP0 and GTE; *any read from RAM or an
   I/O register stalls the CPU until the DMA is finished*, resuming only
   between SyncMode 2 list entries. FF7's libgpu poll reads CHCR — an I/O
   register — so on hardware the first poll blocks until the walk completes
   and the 790–890-poll abort can never fire. DuckStation gets the same
   outcome by charging the walk's ticks to the CPU (`CPU::AddPendingTicks`)
   rather than letting it run in parallel. #277 slices the walk while the
   guest runs freely; that is what created the abort, and 1+0 hides it by
   making walks short instead of modelling the stall. The faithful fix is a
   stall (or drain-to-completion) on guest RAM/MMIO reads while DMA2 is
   active. 1+0 is acceptable as an interim, but it should be labelled as such,
   not as the validated hardware cost.
3. **Branch hygiene.** The PR is `CONFLICTING` and carries two unrelated
   "bump" commits: the `psxmod` validator + catalog-diagnostic launcher ABI
   fields (`906a811f`, not on master) and gitlink moves of `lib/recomp-net`
   and `lib/retcomm-rbengine` (`dcae4f73`). Only `8d2daa92` is the DMA
   change; the rest should be rebased away before merge.
4. **Behavioural nit.** With setup = 0 the payload is now read on the *same*
   service as its header (the fall-through), not "at its own boundary" as the
   description says. Harmless — pre-#277 read everything at kick — but the
   comment overstates it.
5. **Counters are worth keeping regardless.** `gpu_ot` in `dma_state` is
   what made this census a ten-minute job; the `PSX_GPU_LL_SYNC` lever is
   fine as a diagnostic.

## Raw logs

The census script is `tools/ot_census.py`. Per-scene JSON for both builds is
in the table above; the full sample logs lived in the 2026-09-03 session
scratchpad (`ot_pr302.txt`, `ot_base.txt`, `ot2_*.txt`) and are reproducible in ~10 min.
