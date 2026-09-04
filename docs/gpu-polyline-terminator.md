# Ground vanishes after an item-use effect: GP0 polyline terminator bug

**Status:** RESOLVED in the framework (psxrecomp fork branch
`fix/gpu-polyline-terminator` `402cada6`, 2026-09-03) — upstream PR
[mstan/psxrecomp#313](https://github.com/mstan/psxrecomp/pull/313) open; pin
moves back to `mstan/master` if it merges. Both debug-tool trees rebuilt.

## Symptom

Reported by the player 2026-09-03. During a battle on the field, the moment Rei
used a healing herb (薬草) the whole ground plane disappeared: only the sky /
water backdrop, trees, enemies and party sprites remained. The loss persisted
after fleeing the battle — the field itself had no ground — until the area was
left. Savestates: file `slot04` (in-game 5) reproduces it deterministically
about 35 frames after load; file `slot05` (in-game 6) is a few seconds earlier
and does *not* reproduce (different timing through the effect).

## What was established (evidence, in order)

1. **The ground polygons are still submitted.** GP0 ring capture of a glitched
   frame (`psxrecomp/tools/gpu_frame_capture.py`) shows the same 227 textured
   quads (tpage 151 = 8bpp page at VRAM (448,256), CLUT at (0,484)) with sane
   screen coordinates as a healthy frame. So this is not culling, GTE, or a
   dropped ordering table.
2. **The texture page is zero; the CLUT is intact.** `vram_peek` (448..511,
   256..383): 0/4096 non-zero halfwords in the glitched state vs 4096/4096 in
   the clean one; CLUT row y=484 identical in both. Texel 0 → CLUT entry 0 →
   0x0000 → transparent. That is exactly "ground draws as nothing".
3. **The savestate file itself is intact.** `tools/pst_tool.py diff` of the two
   `.pst` files: the (448,256) page is fully populated in *both*; the only
   VRAM differences are the framebuffers and the effect's own texture column at
   x 832..895. The thumbnail taken at save time shows the ground. So the wipe
   happens *after* the load, in emulated execution.
4. **Timed to the frame.** Polling `vram_peek` after a TCP load: the page is
   intact for ~0.55 s and goes to zero in one step (frame 141983 in the run
   that was traced).
5. **The GP0 stream at that frame contains one stray FILL** (op 0x02, colour
   0x010101 → 0x0000, at (246,140), size word `0x55555555` → 341×341) issued
   from the effect overlay (band `0x801EEC00`, pc `0x801EECF4`). That rectangle
   covers x 246..586, y 140..480 — the texture page inside it.
6. **The FILL is a mis-parse, not a game primitive.** Reading the packet's
   neighbours by RAM source address, the effect draws gouraud shaded polylines
   (`0x5A` = LINE_G polyline, semi-transparent) laid out as
   `5A010101 | 009600F3 | 52545454 | 009400EE | 00010101 | 009200E9 | 55555555`
   — C0 V0 C1 V1 C2 V2 terminator. Our parser tested **every** word against the
   terminator mask `(w & 0xF000F000) == 0x50005000` and `0x52545454` (Psy-Q
   junk in the top byte of a colour word, G byte `0x54`) matched. The polyline
   ended after one vertex; `009400EE`, `00010101`, `009200E9` were parsed as
   NOPs (opcode 0x00), the real terminator `55555555` as a 4-word LineG that
   swallowed the next polyline's header, and in the second polyline the colour
   word `02010101` landed in command position → FILL with `008C00F6` as XY and
   the terminator as its size.
7. **Hardware rule, from both oracles.** Beetle (`mednafen/psx/gpu.c`,
   `INCMD_PLINE`: consumes `command_len = 1 + shaded` words per vertex unit and
   peeks only the unit's first word for the terminator; the first two vertices
   are read by the line command itself, untested) and DuckStation (`gpu.cpp`
   `HandleRenderPolyLineCommand`: "always read the first two vertices, we test
   for the terminator after that"; `DrawingPolyLine` steps by `words_per_vertex`
   and tests "the first word for the vertex"). So: never test the first two
   vertices; afterwards test only the vertex word (mono) or the colour word
   (shaded); never test a shaded vertex word.

## Fix

`psxrecomp/runtime/src/gpu.c`, GP0 `POLYLINE_MONO` / `POLYLINE_SHADED` states:
the vertex count is folded into the existing `polyline_has_prev` int (mono
0..2; shaded 0 = need V0, 1 = need C1, 2 = need Vn, 3 = need Cn with n ≥ 2) so
the GPU savestate section keeps its byte size, and the terminator test runs only
in the positions hardware tests. Commit `402cada6` on fork branch
`fix/gpu-polyline-terminator` (off upstream `master` `d08d84a3`).

**Verified:** `build-relprof` rebuilt with the fix, launched headless with
`PSX_LOAD_SLOT=4`: the (448,256) page stays 4096/4096 over 6000+ frames and the
screenshot shows the terrain with the battle continuing (command ring open).
The unfixed `build-dbg` wiped it 35 frames after the same load, three times out
of three.

## Notes

- Any Psy-Q title using `LINE_G*` polylines with a junk `pad`/code byte is
  exposed; the symptom is whatever the de-phased words happen to decode to, so
  it can look like texture damage, stray fills, or a fatal "unknown GP0
  command".
- The earlier icon-strip damage ([`battle-icon-strip-rows.md`](battle-icon-strip-rows.md))
  is a zero band in a texture that appears later in a session. The player
  confirmed (2026-09-03) it first appeared right after a **heal spell** effect,
  the same style of shaded-polyline animation, so the same de-phasing is the
  probable cause. Retest once `build-dbg` is rebuilt with the fix.
- `tools/pst_tool.py` (new): parse `.pst` offline — `info`, `vram` (PNG),
  `ram`, `diff` (VRAM zero-map / diff-map / RAM ranges). Lets two states be
  compared without loading them into a running game.
- Reference frame dumps and VRAM renders are in `analysis/frames/ground/`
  (gitignored).
