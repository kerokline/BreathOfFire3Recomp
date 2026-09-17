# GFX_PACKETS.md — the frame packet arena, `Packet_Commit`, and the eight OT layers

**Status:** STABLE (established 2026-09-17 from the Ghidra decompile of the
boot EXE; the arena geometry is cross-checked against `Main_FrameLoop`'s
buffer flip and the constant-`a0` call sites in the game-mode overlay)

`0x8014E494` was the boot helper called between every primitive build —
`(1, 0xC)` / `(1, 0x10)` in `Window_DrawFrame`, `(1, 0x28)` per glyph in the
text renderer, 30 boot-EXE callers and 36 constant-`a0` sites in the
game-mode overlay — and the "packet-commit hook" the furigana plugin sits
on ([`FURIGANA.md`](FURIGANA.md)). It is now `Packet_Commit` in
`symbols.toml`, together with the three functions that give it meaning.
Decompiles: `analysis/ghidra/SLPS_009.90_decomp/8014E494_*.c`,
`8014AF98_*.c`, `8014B06C_*.c`, `8014AAC8_*.c`.

## The contract

```
Packet_Commit(layer, size)
```

The caller has already written a GPU primitive at the packet cursor
`*0x80145988`. `Packet_Commit` links it to the end of OT layer
`layer & 0xFF` and advances the cursor by `size & 0xFF`:

```
if (cursor + size < arena_end) {
    CatPrim(tail[layer], cursor);    // tail->next = cursor
    tail[layer] = cursor;
    cursor += size;
}
```

with `tail = 0x801459CC[8]` and `arena_end = 0x80020FCC + db * 0x9000`.
There is no return value: the caller reads the cursor before the call to
know where its primitive lives, and the next caller finds the cursor
already past it.

**Over budget the packet is dropped silently.** If the frame's arena is
within `0x34` bytes of full, nothing is linked and the cursor stays put; the
next caller then overwrites the same bytes. That is the whole overflow
policy, so a scene that draws too many primitives loses its *last*
primitives, not its first, and nothing logs it.

## The arena

Two `0x9000`-byte packet arenas, one per display buffer, at
`0x80018000` and `0x80021000`. `db` is the byte `0x80143D44` (0 or 1),
flipped once per frame by `Main_FrameLoop`. The bound `0x80020FCC` is
`0x80021000 - 0x34`: the end of arena 0 minus a 52-byte guard — `0x34` is
`sizeof(POLY_GT4)`, the largest Psy-Q polygon primitive, so one more of
anything always fits below the bound.

| Address | What | Set by |
|---|---|---|
| `0x80145988` | packet cursor | `Packet_FrameReset` to `0x80018000 + db*0x9000`; advanced by `Packet_Commit` |
| `0x8014598C` | 2 × 8 dummy list heads (`db*0x20 + layer*4`) | `Packet_FrameReset` |
| `0x801459CC` | 8 chain tails, one per layer | reset to the dummy heads each frame, advanced by `Packet_Commit` |
| `0x80143D44` | `db`, the display-buffer index | `Main_FrameLoop` `^= 1` |
| `0x80143E68` | pointer to the current frame's DB block (`0x80143D48 + db*0x90`: `DISPENV` +0, `DRAWENV` +0x14, 8-entry OT +0x70) | `Main_FrameLoop` |
| `0x80142CC0` | 56 sprite-slot records, stride `0x30`, `+0x20`/`+0x28` per `db` | zeroed by `Packet_FrameReset` |
| `0x801459F4` / `F8` | heap pointers `0x800E4800` / `0x800F5000` | `Packet_FrameReset` |

## The frame (`Main_FrameLoop`, 0x8014AAC8)

```
VSync(2); Rand();
PutDispEnv(db block); PutDrawEnv(db block + 0x14);
0x8014E120(); 0x8014E5C4();
DrawOTag(db block + 0x8C);          // entry 7 of the reverse OT
0x8014AF38(); SE_PollKeyStatus();
db ^= 1; db block = 0x80143D48 + db*0x90;
ClearOTagR(db block + 0x70, 8);
Packet_FrameReset();                // cursor, tails, sprite slots
0x8014B630(); 0x80163A00();         // the game's own per-frame work
0x80143EF8 = VSync(1); DrawSync(0);
Packet_FlushToOT();                 // chains -> OT entries
0x80143E6C++;
```

`Packet_FlushToOT` (`0x8014B06C`) does, for `layer = 0..7`,
`AddPrims(ot[layer], head[db][layer], tail[layer])`. The OT is built with
`ClearOTagR(…, 8)` and drawn from entry 7, so **layer 7 is drawn first and
layer 0 last**: lower layer number means nearer the viewer. Chains keep the
order in which their primitives were committed, so within a layer, later
commits draw on top.

Observed layer use in the boot EXE: text glyphs and the message-box
primitives commit to layer 1; `Window_DrawFrame` and its siblings to 6 and
7 (frame behind contents); one caller at `0x80168288` uses 3. The game-mode
overlay's 36 constant-`a0` sites are catalogued in the Ghidra export
(`call_sites` with `to = 0x8014E494`).

## Why the furigana hook filters on the return address

The plugin hooks `Packet_Commit` to re-point a reading glyph's `POLY_FT4`
at the small-font cell (FURIGANA.md "The 8 px font"). Everything that draws
goes through this one function, so the hook must recognise its caller: it
filters on the return address of the renderer path it wants (STATUS.md
2026-09-12), which is also what keeps the next-page arrow — a sprite through
the same blitter — untouched. A hook
that keyed on `layer == 1` alone would also catch every other layer-1
primitive in the frame.

## Open

- The names above cover the four functions; `0x8014E120` / `0x8014E5C4`
  (before the `DrawOTag`) and `0x8014B630` / `0x80163A00` (the per-frame
  game step) are still `FUN_*` in Ghidra.
- A frame that hits the arena guard has never been looked for. A plugin
  counter on the `cursor + size >= arena_end` path would say whether any
  scene ever loses packets.
