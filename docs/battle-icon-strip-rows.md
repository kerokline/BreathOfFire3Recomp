# Battle command icon: top rows of the enlarged icon missing

**Status:** IN PROGRESS (2026-09-03) — probable cause identified: the GP0
polyline de-phasing fixed in [`gpu-polyline-terminator.md`](gpu-polyline-terminator.md).
The player confirmed (2026-09-03) that the icon damage first appeared right
after a **heal spell** effect, the same style of shaded-polyline animation as
the herb effect that wiped the terrain texture. Awaiting a retest on a build
carrying the fix; the savestate-load theory below is superseded unless the
retest reproduces.

## Symptom

In battle, the selected (enlarged, 24×24) command icon in the attack ring loses
its top quarter. It reads as "clipped by the neighbouring icon" but is not.
Reported by the player 2026-09-02; reproducible in every battle.

## What is established (evidence)

1. **The renderer draws VRAM faithfully.** `vram_peek` (CPU mirror) and
   `gl_fbo_peek` (OpenGL framebuffer) agree byte-for-byte over the icon texture;
   `gl_vram_diff` reports 0 mismatches.
2. **The enlarged-icon strip texture is damaged in VRAM.** The strip lives at
   VRAM x 256..297, y 480..503 (4bpp, tpage 20, CLUT at (128,480)); the quad
   samples uv (0..24, 224..248). Rows 480..485 are zero for x 256..319; rows
   486..503 are intact. Established with `vram_peek` row scans and a pixel dump
   of the presented frame (background shows through the blank rows even where no
   small icon overlaps).
3. **The loss happens once, not per frame.** Rows 480..485 at x 128..255 (the
   neighbouring block, refreshed by a periodic 256×32 upload every ~12 frames)
   stay non-zero across 3 s of sampling, so no per-frame clear touches that band.
   A full scan of the GP0 ring (2 275 frames) found no fill/copy/upload/primitive
   touching x ≥ 256, y ≥ 480. A fresh battle start (watched with the DMA trace)
   does not re-upload the strip either.
4. **The source asset is complete.** The strip is section 6 of
   `BIN/ETC/FIRST.EMI` (file offset 0x2A000, disc LBA 61356; 16 sectors, each one
   32×32-halfword block, section `dest` word encodes (x/32, y/32) = (256, 480)).
   Diffing each VRAM block against the file: blocks 0 and 1 (x 256, 288) differ
   in exactly bytes 0..383 (six 64-byte rows, all zero in VRAM, non-zero on
   disc); every other byte matches. Blocks 2..15 are zero on disc, so they carry
   no information.
5. **Oracle:** the Beetle PSX savestates in `D:\BoFIII\*.state` (RetroArch RZIP;
   decompressed with zlib per chunk) contain VRAM with the same strip at the same
   address and **all 24 rows present**. So this is a runtime defect, not game
   behaviour.

6. **The boot-time load is fine.** Watched relaunch (2026-09-02, ~12:49 local):
   the strip probe (`vram_peek` 256..319 × 480..503) went from empty at frame 10
   to *all 24 rows present* at frame 1205, and stayed complete into a fresh
   battle (checked live at frame 22840; player confirmed the icon draws whole).
   So neither the CD read nor the boot upload drops the rows.

## What is not yet known

**Candidate cause added 2026-09-03:** the ground-texture wipe
([`gpu-polyline-terminator.md`](gpu-polyline-terminator.md)) was a de-phased GP0
stream — a gouraud polyline ended early on a junk-top-byte colour word and the
leftover words decoded as a FILL. The same de-phasing produces arbitrary
primitives from arbitrary data, so a stray fill or rectangle over
x 256..319 × y 480..485 is now a plausible source of this zero band. Retest on
a build carrying the polyline fix before pursuing the savestate-load theory.

What zeroes rows 480..485 for x 256..319 later in a session. The damaged
session had loaded savestates repeatedly (`savestate_status` generation 49,
last op `load`); a savestate load is the one path that rewrites all of VRAM
(`gl_renderer_restage_vram_after_savestate` → full-VRAM `up_add_transfer` +
`flush_cpu_upload`, `gpu_gl_renderer.c`), and the zero band's x extent
(exactly the 320-wide framebuffer column) hints at a display-band clear
(`depth24_mark_scanout_band` / `depth24_clear_skipped_fb`) rather than a
texture path. Test: save a fresh in-game state, load it, watch the probe.
`analysis/frames/watch_uploads.py` logs the probe transition with its frame.

## Tools used

`psxrecomp/tools/gpu_frame_capture.py`, `psx_gpu_frame.py` (ring capture and
decode), debug-server commands `vram_peek`, `gl_fbo_peek`, `gl_vram_diff`,
`dma_trace_dump`, `cdrom_sector_history`, `read_ram`; `tools/disc_ls.py`
(sector → file), `tools/emi.py list` (section table).
