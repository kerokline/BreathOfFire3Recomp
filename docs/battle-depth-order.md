# Battle sprite/scenery draw order diverges from Beetle

**Status:** RESOLVED as game behaviour (2026-09-02); see the oracle note below.

## Symptom

In the first-area battles with the house/wagon backdrop, Rei (back row, left)
is drawn *behind* the house's side wall, and his attack lunge passes behind the
door. Out of combat the field engine always draws him in front of the door.

**Oracle (2026-09-02):** in RetroArch (Beetle PSX), in a battle at the same
backdrop (party without Rei), the player first saw the door stay behind
everyone, then observed that some attacks *do* phase Ryu behind the door.
So the original game exhibits the same behaviour: battle uses a per-object
depth sort that can place a lunging sprite behind the doorway, while the field
engine uses tile priorities. Not a runtime defect on current evidence.

## What is established (evidence)

- Frame captures (`gpu_frame_capture.py`, frames 82062..82626 on the
  2026-09-02 savestate "in-game slot 4 / file slot03") show all battle objects
  — scenery quads (tpage 149), fence posts (tpage 27), character sprites
  (tpage 132..138) — in the **same** ordering-table bucket. Within it, the wall
  quad (bbox x −7..27, screen y 96..180) is issued *after* Rei's sprite parts
  (CLUT 31684, bbox x 25..75, y 122..178). Overlap while idle is 2 columns;
  during the lunge ~490 px.
- The GL renderer preserves issue order for opaque textured primitives (single
  ordered batch; semi-transparent prims are isolated), and the presented pixels
  match the list order (wall over Rei in columns 25..26).
- The ordering-table rank the runtime stamps is a count of empty linked-list
  nodes, so adjacent non-empty buckets are indistinguishable in the ring; the
  order is nevertheless the game's own list order as walked by DMA channel 2.

The runtime therefore draws exactly the list order the game builds, and the
oracle shows the game itself builds that order.

## If it is reopened

Only a like-for-like comparison would reopen this: the same party, the same
encounter position, the same attack, on Beetle and on the runtime. Then: take
the channel-2 linked-list start from `dma_trace_dump` (chcr 0x01000401), walk
it in guest RAM to recover the true OT index of each sprite vs the wall quad,
and compare the depth inputs in the BATTLE overlay's object sort (GTE
`gte_ring_dump` if the key comes from RTPS/AVSZ). `gpu_parity.py` against a
patched DuckStation would make it mechanical; none is installed here.
