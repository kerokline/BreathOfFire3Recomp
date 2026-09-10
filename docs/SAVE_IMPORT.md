# Importing US saves onto a JP card

**Status: evidence — verified statically 2026-09-08 (`tools/save_import.py`,
`tools/save_tool.py verify`). Not yet loaded in-game.**

Breath of Fire III (USA) `SLUS-00422` and Breath of Fire III (Japan)
`SLPS-00990` write the **same save block**. A US memory-card save is therefore
usable by the JP build after a rename of its card *directory entry* — nothing
inside the save is touched, so its checksum stays valid.

This matters for testing: a late-game US save reaches areas the JP playthrough
has not, without playing there first.

## The evidence

The finding was not assumed; it was measured against the US card in
`saves/Breath of Fire III (USA).1.mcr` (one file, `BASLUS-00422BOF300`,
42 h 37 m, Lv 38).

| Check | Result |
|---|---|
| Checksum offset + rule | The US block's u16 at file `+0x270` equals the byte-sum of the 0x10B0-byte block with that u16 excluded — **the JP rule at the JP offset**, matched exactly (`0xafc1`). A sweep over every 2-byte offset in `0..0x120` and every length in `0x1000..0x1200` found no other offset that works. |
| Block length | Consistent with JP's `0x10B0` (the tail is zero-fill, so lengths from `0x103c` up all sum alike). |
| Field map | Every field in `save_tool.A` decodes sanely: play time `42:37:13` and roster-0 level `38` both agree with the card *title frame* text, which is independent of the game block. |
| Cross-checks vs. the **JP disc tables** | `save_tool.py verify` runs 46 checks that join the save against `names/*.toml` (extracted from the JP `.EMI`). 43 pass — including all four inventory categories' ids, all eight ability lists' types, and 7 of 8 ATK / all 8 DEF equations resolving to named JP items (`グミオウの剣` +180, `ビーストスピア` +150, …). **Item, ability and equipment ids are shared between the two regions.** |

The three failures are not region drift:

- **title parse** — the title frame reads `Ｂｒｅａｔｈ ｏｆ Ｆｉｒｅ ３（１） ４２ｈ３７ｍ Ｌｖ．３８`, so
  the JP `時間/分/レベル` parse fails. Cosmetic; the in-game load screen reads the
  slot summary in the game block, not this frame.
- **key item ids** — the save holds 29 key items; `names/` only has 16 (ids
  0–15), because every JP save on hand holds *zero* key items and the table was
  never grown. Every id ≤ 15 in the US save resolves to a real JP key item in
  story order (Egg, Flier, Passport, Guild Badge, …). Our table is short, the
  save is not.
- **roster 5 ATK +5** — Momo's ATK exceeds base + weapon power by 5, with no
  accessory equipped (roster 4 shows the same +5 and *was* excused as an
  accessory effect — that excuse is wrong). Record offsets `0x30`/`0x50` hold 5
  for every roster, so they are not the source. This is an **unmodelled term in
  the tool's ATK equation** (Master bonuses are the likely candidate), exposed
  only because no JP save on hand is late enough to carry one. The save block is
  a byte-for-byte copy, so it cannot be a conversion artifact.

## The conversion

Only the 128-byte card directory frame changes: filename
`BASLUS-00422BOF3NN` → `BISLPS-00990BOF3NN` (the template the JP game builds at
`START.EMI 0x801D0ED4`, `names/data.toml` `SaveFile_NameTemplate`), with the
frame's trailing XOR byte and the header frame's XOR recomputed. The 8 KiB
block is copied verbatim.

```bash
python tools/save_import.py list "saves/Breath of Fire III (USA).1.mcr"
python tools/save_import.py import "saves/Breath of Fire III (USA).1.mcr" saves/card2.mcd
python tools/save_tool.py verify saves/card2.mcd
```

`import` copies every BoF3 save on the source card into the first free
directory slots, refuses to overwrite an occupied slot without `--force`, backs
the destination up to `DST.bak`, and refuses a source whose game-block checksum
does not verify. `--slot` picks one source save, `--into` picks the destination
directory slot, `--as` renumbers the `BOF3NN` suffix (the number the JP load
screen orders by).

`saves/card2.mcd` is the runtime's card 2 (`memcard_dir = "saves"` in
`game.toml`); Mednafen reads the same save as
`saves/Breath of Fire III (Japan).<md5>.1.mcr` — see [`MEDNAFEN.md`](MEDNAFEN.md).

## Area numbering is identical -- proven off the discs

The first live load came up in an unfamiliar place with a one-character party,
which looked like the predicted failure. It is not. Both discs were listed and
compared (`tools/disc_ls.py`, 890 entries each):

| Test | Result |
|---|---|
| Area file set | **200 `AREA<n>.EMI` on each disc, no JP-only or US-only numbers**, and every one sits in the same `BIN/WORLD<nn>/` directory on both. |
| Per-area size, aligned at shift 0 | **max delta 0.12 %** across all 200 (median 0.107 %) -- the signature of the same room with translated text. |
| Per-area size, shifted | Every offset is strictly worse: max delta 0.32 % at -1, 0.49 % at +1, 1.00 % / 1.17 % at -3 / +3. No shift explains the data; only alignment does. |

Area numbers are literally filenames on the disc (`AREA141.EMI` is 164,120 B on
JP, 164,297 B on US -- **+177 bytes of English text in the same room**), and the
loader reaches them as `u16[0x80143F00] + 0x2AB` (`OVERLAY_HEADERS.md`). So the
save's area `0x8d` means the same room in both builds, and the imported save
loaded exactly where it was saved.

The one-character party is likewise faithful, not damage: the block holds
formation 0 = `[7, 255, 255]` and formation 1 the same -- **solo adult Ryu**,
which the slot summary independently agrees with. The screenshot confirms the
engine agrees: blue spiky hair, olive tunic, pack and sword = char_id 7. The
rest of the roster is present and intact in the records (Lv 37, 22, 16, 37, 21,
23) -- not in the active formation, which is a story state, not a conversion
artifact.

## Open: the button config rides along

After the load the game used **US confirm/cancel**, so BoF3 persists its OPTION
config inside the save block and the JP build honoured the US value. That is
faithful behaviour, and harmless -- but it is confusing mid-test, and the option
bytes are not located yet. A byte-diff cannot isolate them, because the US save
differs from every JP save on hand almost everywhere simply by being 42 h
further along.

The cheap experiment: in the JP build change the button setting in OPTION, save
to a fresh slot on card 2, and diff that block against its parent. The option
bytes are the only thing that can move. With them located, `save_import.py`
grows a `--jp-options` flag that carries a JP save's config region across on
import, so a converted save plays with the controls the rest of the project uses.
