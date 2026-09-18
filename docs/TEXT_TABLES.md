# Name tables straight from the `.EMI` — items, abilities, places, roster

**Status:** DONE 2026-09-05 (IDEAS I4 built; every id in the three card saves
resolves; ability types and equipment powers cross-check against the saves;
evening: the world-map place names found as painted plates and read out);
extended 2026-09-18 — the `ref` u16 is the **description id** into the
`0x80014000` system pool, resolved and verified for all 311 items and 227
abilities (*`ref` is the description id* below). Open items at the end.

The non-dialogue names do not live in the script blocks. They sit in
**fixed-stride record tables** inside three `.EMI` containers, and the record
index is the id the saves and the RAM hold. `tools/text_tables.py` reads them
off the disc (through the `.cue`, never modified) into four sidecars under
`names/`, and `tools/save_tool.py` reads those back so a save dumps as
`薬草(Healing Herb) x28` instead of `id3 x28`.

```bash
python tools/text_tables.py extract            # -> names/items.toml, abilities.toml, places.toml, characters.toml
python tools/text_tables.py show items --category weapon
python tools/save_tool.py dump saves/card1.mcd 2     # names on by default when names/ exists
python tools/save_tool.py verify saves/card1.mcd     # + the table cross-checks below
```

Inputs the tool takes from outside the repo (both overridable, both
optional — without them kanji print as `[13b3]` and the `en` column is empty):

| Input | Default | Used for |
|---|---|---|
| kanji table | `D:\BoFIII\bof3_character_table.json` (`BOF3_KANJI_TABLE`) | the two-byte `0x12xx`/`0x13xx` glyphs; 435 of them known |
| glossary | `D:\BoFIII\wiki_terms.tsv` (`BOF3_GLOSSARY`) | JP→official EN, 882 rows by wiki section; regenerate with `tools/wiki_terms.py` |
| disc | `game.toml` `[game].disc`, or `--bin-root <BIN dir>` | the bytes |

## The tables

Every start address was found by encoding one known name (薬草 = `13 1a 12 8b`)
and reading the neighbourhood; every stride by the repeat of the `なし` /
`0x40xx` pattern; every count by scanning until a name stops decoding, then
checking that the count times the stride lands exactly on the next table's
start. All five item tables do (`0x508 = 92×14`, `0xC0 = 16×12`,
`0x67C = 83×20`, `0x4C8 = 68×18`); the tool refuses to write if a count moves.

| Table | Where (RAM, section) | Record | Count | Fields read |
|---|---|---|---|---|
| **consumables** (inventory cat 0) | `GAME.EMI#0` `0x801C995C` | 14 B: `name[8]`, u16 flags, u16 ref, u16 price | 92 | price |
| **key items** (`0x80145448` list) | `0x801C9E64` | 12 B: `name[8]`, u16 ref, u16 | 16 | — |
| **weapons** (cat 1) | `0x801C9F24` | 20 B: `name[8]`, u16, u16, u16, **u16 power**, u16 ref, u16 price | 83 | power = ATK, price |
| **armour / shield / helm** (cat 2) | `0x801CA5A0` | 18 B: `name[8]`, u16, u16, **u16 power**, u16 ref, u16 price | 68 | power = DEF, price |
| **accessories** (cat 3) | `0x801CAA68` | 16 B: `name[8]`, u16, u16 effect?, u16 ref, u16 price | 52 | price |
| **abilities** | `0x801CB230` | 16 B: 8 param bytes, `name[8]` | 227 | type = `b1 & 3` |
| **places** (debug map select) | `MTEST.EMI#0` `0x801D0D94` | 10 B name; head `0x801D0C04` holds 2 bytes per entry | 200 | **id = AREA number**; joined to the area script's caption / dev label |
| **roster** | `COMMU02.EMI#8` `0x801DB214` | 5 B name | 7 | — |
| **new-game templates** | `START.EMI#8` `0x801EB4A4` | `0xA4` = the persistent character record | 8 | char_id, level, exp, hp, ap |

So the category question in IDEAS I4 is settled by the bytes: the four
inventory categories are **four separate tables with four different strides**,
plus a fifth for key items. The item id byte in the save is the index into the
table of its category; cat 1 id 3 is せいどうの剣 (Bronze Sword), Ryu's weapon
in the file-2/3 saves.

### `ref` is the description id — resolved 2026-09-18

The `ref` u16 (`0x40xx`/`0x41xx`) that runs through all five item tables and the
ability table (`abilities.toml` `u16_6`) is a **message id in the system pool**,
resolved by `Msg_SystemPtr` `0x801503F8` exactly as any other system string
([`TEXT_ENGINE.md`](TEXT_ENGINE.md)):

```
base   = 0x80014000 + *(u32 *)(0x80014000 + ((ref >> 12) & 0xC))   # header word, id bits 14-15
string = base + *(u16 *)(base + 2 * (ref & 0x3FFF))
```

Every `ref` we hold has bits 14–15 = `01`, so they all select **header word 1**.
On the main pool (the `dest 0x80014000` section, 11,560 bytes, identical in 42
of the 44 `.EMI` files that carry one — `FIRST.EMI` and `AFLDKWA.EMI` hold the
other variant) word 0 addresses 176 messages and **word 1 addresses 455**, which
is the pool the 311 item refs and 227 ability refs index into.

Verified three ways, 2026-09-18:

- **Coverage.** All 311 item refs and all 227 ability refs land in range and
  resolve to a non-empty string. Nothing falls off the end of either table.
- **The text is the right text.** Consumable descriptions are the HP-restore
  line with the item's own amount; weapon and armour descriptions are the
  attack/defence and weight line; ability descriptions describe that ability's
  effect (the button-timing skills say so, the luck-based ones say so).
- **The numbers agree with a field we extracted separately.** Walking each
  description control-aware and taking its first standalone digit run: it equals
  our `power` for **81 of 82** weapons and **66 of 67** armour records. The two
  exceptions (あしゅらの剣, おとこふく) have flavour-text descriptions containing no
  digits at all, so there is nothing to disagree with. *Trap:* a naive
  `[0-9]` scan over the raw bytes scores near zero — `0x30`–`0x39` occur as the
  trailing byte of two-byte `0x12xx`/`0x13xx` kanji. Use the control-aware walk.

Only **12 of 227** ability descriptions contain any digit, so AP cost cannot be
cross-checked this way; `b2`/`b3` remain unread.

The Chinese PC port names this field `descriptionId` on every item and skill
record, which is what prompted the check
([`PC_PORT_CROSS_REFERENCE.md`](PC_PORT_CROSS_REFERENCE.md) §3). Its `GetText`
splits an id as `fileNum = index >> 14`, `index &= 0x3FFF` — the same two
selector bits, independently derived.

Ability refs run `0x40FB + id` for ids 1..57 and then drift (id 58 is `0x4134`,
one short), so the table is authored per record, not generated. Id 0 (`なし` /
the enemy-only row) points at `0x4000`, the shared empty string.

### Weapon `+0x0B` is the element mask — and the ability record has no such field

**Weapons: settled.** `Battle_CalcDamage` `0x801DC00C` loads the attacker's
element mask from `0x801C9F2F + weapon_id * 0x14`, i.e. **weapon record
`+0x0B`** — the high byte of the `u16_10` this sidecar keeps raw. Single bits
only, and every named weapon matches its bit (`0x01` fire, `0x02` ice, `0x04`
lightning, `0x08` earth, `0x10` wind, `0x20` **holy** — Holy Avenger,
Ghostbuster, Silver Knife, and the undead are weak to it). Table and evidence in [`BATTLE_RAM.md`](BATTLE_RAM.md)
*The element bits*. That also confirms what the PC port calls `element` on
`WeaponData` ([`PC_PORT_CROSS_REFERENCE.md`](PC_PORT_CROSS_REFERENCE.md) §3).

**Abilities: retracted.** An earlier revision of this section (written and
withdrawn the same day, 2026-09-18) claimed the ability record's `u16_4` low
byte was that element mask, on the strength of its value shapes — `0x01` on
Fireblast, `0x02` on Iceblast, `0x04` on Lightning, `0x08` on Simoon, `0x10` on
Quake. **It is not.** Against the bit order the weapon table proves, `0x08` is
earth and `0x10` is wind, which makes Simoon earth and Quake wind — backwards.
Frost sharing fire's bit was the other tell. Three coincidences out of five is
what a suggestive-looking byte gets you; the claim was inference from value
shapes and never from code, and the code says otherwise.

Where a spell's element actually comes from: the **effect handler**. Of the
BATTLE.EMI#15 handlers that call `0x801DC00C`, sixteen pass the `0xFFFF`
"use the weapon's element" sentinel and one passes a literal `4`. So the mask
is baked into the per-ability handler, and reaching it needs the ability →
handler index mapping that [`BATTLE_RAM.md`](BATTLE_RAM.md) still lists as
open, not another column of this table. `u16_4` remains what it was: flags read
by `Actor_SkillItemDone` (`& 0x800`) and the enemy-AI mask.

The other u16s (weapon `+8..+0x0A` and `+0x0C`, armour `+8..+10`, accessory
`+8..+10`) are kept raw in the sidecar and are still unread.

### Encoding notes learned from the names

Beyond the kana / kanji table in [`TEXT_ENGINE.md`](TEXT_ENGINE.md):

- `0xFB` = ヴ (the katakana run ends at `0xFA` ポ; ティルヴィング, weapon 23).
- `0x2D` renders as a long-vowel mark (シャーリィの研, スーパーコンボ); `0x3A` is
  the middle dot (ウルカン・タパ). Both are kept as ー / ・.
- **Digits and capitals are raw ASCII in name fields**: パーツA..H,
  アリーナ1..4, ぜんたいマップ1, カードキーB. This is the first confirmation of
  TEXT_ENGINE.md's open question 1 for menu text (the script pool is still
  unchecked).
- `0xFF` inside a name is a **word separator** (マクニールむら|S, つりば|みずうみ,
  てっとう|UPPER); the tool renders it as a space.

## Cross-checks against the saves (`save_tool.py verify`)

All three saves on `card1.mcd` (`card2.mcd` holds no BoF3 files) and the runtime `.mcr` cards, 2026-09-05:

- **Every id resolves.** Every inventory id in every category, every key
  item and every equipped item is a record of its category's table.
- **Ability list type.** `AbilityList_ForType` files an ability into
  `+0x5C` / `+0x66` / `+0x70` / `+0x7A` by `(0x801CB231 + id*16) & 3`. For all
  eight records in all saves, every learned ability's table type equals the
  list it sits in (Momo's アプリフ / リバル in type 0, ねらい撃ち / めいれい /
  ミカテクト / ダール in type 1, Teepo's パダーマ / レイギル / ドメガ in type 2,
  Rei's リリフ / 毒撃 in type 3). That is the code path, not a reading of names.
- **Weapon power = ATK bonus.** `rec+0x20` (effective ATK) = `rec+0x40` (base)
  + the equipped weapon's `power` for every record without an accessory
  (Bronze Sword 8, Dagger 4, Oaken Staff 6, Ballock Knife 6, Momo's Ammo 58,
  unequipped 0).
- **Armour power = DEF bonus.** `rec+0x22` = `rec+0x42` + the sum of the three
  cat-2 slots' `power` for every record (Ryu 10+6, Garr 44+21, Momo 25+15).
- The one line `verify` cannot close: Garr's ATK is base + Spear **+ 10** with
  勇気のベルト (Titan Belt) equipped. The accessory record carries `u16_10 = 5`,
  an effect code rather than a stat, so accessories are reported as
  `[--]` (unverified) instead of FAIL until that code is read.

`save_tool.py` also had a latent bug: a comment on the `char_id` row of
`REC_FIELDS` had swallowed the `level` and `unk_07` fields, so `dump` raised
`KeyError: 'level'`. Fixed in the same change.

## Glossary coverage

| Sidecar | Records | With `en` | Missing |
|---|---|---|---|
| items: consumable | 92 | 78 | 14 (火[13b3]ダコ, 木の研, シャーリィの研, パーツA..H …) |
| items: key | 16 | 12 | 4 |
| items: weapon | 83 | 79 | 4 (バゼラード, ハルバート …) |
| items: armour | 68 | 62 | 6 |
| items: accessory | 52 | 50 | 2 |
| abilities | 227 | 219 | 8 (ねらい撃ち, テンプテーション …) |
| places | 200 | 45 | 155 — see "Places" below: 11 areas draw a kanji banner, the rest have no in-game name |
| characters | 7 | 7 | 0 |

The `en` column is the wiki's official US name where the glossary has a row
for the exact JP string; the spell rows put the name in the literal column and
a history note in the official one, so the tool takes the short column and
keeps the note. Missing `en` is missing, not wrong: nothing is guessed.

## Places — the MTEST index is the AREA number

The 200 debug entries are AREA000..AREA199 in order (the disc has exactly 200
`BIN/WORLDnn/AREAnnn.EMI`; entry 2 さいくつげんば is AREA002, whose script's
first message is さいくつげんば; entry 23 グラウスさんふもと is AREA023, whose
entry banner is グラウス山; the ` S` / ` A` suffixes are the spring / autumn
variants of the same place, AREA000 / AREA007 for McNeil). So
`names/places.toml` now carries `area_file`, the key
[`names/areas.toml`](../names/areas.toml) uses, and `season`.

**Where the kanji is.** The debug list is kana because it is a debug list;
the in-game kanji strings live in each area's own script block (the
`0x80010000` section, message table at offset 0), in two forms:

- **`caption`** — the banner the game draws on entry: a message of the form
  `<0c> <param> (<ff>|<01>)* TEXT [<11>] <16> <frames>`. グラウス山 (user-confirmed
  on screen), モーランジ山, ウインディア城, 春の牧場, シーダの森、春, 漢羅狂烈大武会.
  Only **11** areas have one; this is *the* in-game place name where it exists
  (status evidence).
- **`dev_label`** — message 0 when it is a bare short string with no dialogue
  codes: the developers' map name (鉱山の外, 港町, オウガー街道, 地奥墓地,
  まくにーるむら, ちかちーろ, 2と使いまわし …). 81 areas. Hypothesis-grade: it is
  a comment, not a display string.

The world-map scripts (AREA016 / 045 / 065 / 087 / 088 / 115 / 121 / 151 / 152)
hold the **region** names (ウールオル地方, ラパラ地方, 彼の地 …) and the spot
*descriptions* (the guide text of IDEAS I2). The spot **names** the player
sees on the world map are not text at all — they are painted plates in the
map's texture page (next section). So most interiors never show a name
in-game, and the wiki's kanji for them comes from dialogue. The English column is filled in this order, and `en_source` says
which step matched: caption (season words folded) → dev label → debug kana →
**romaji fold** (the wiki's romaji column is wāpuro-style, so マクニールむら =
`makuniirumura` = マクニール村 "Makuniiru Mura"; exact match only) → the S/A
sibling's label. Result: 45 of 200 with an `en` (6 caption, 2 sibling, 13 dev
label, 4 kana, 20 romaji). All 45 were read by eye and are right (いにしえのみやこ →
古の都 Caer Xhan, やみいち → Syn City, てっとう → Steel Tower).

The two `sel` bytes per entry are identical for the S and A variants of a
place, so they identify the place, not the variant (world-map cell is the
guess; unread).

## World-map plates — the names are paint

The user's check that AREA007's map label reads マクニール村 in kanji, while
no such string exists in any script, RAM dump or other encoding, led here.
On the world map the game draws each spot's name from a **pre-painted name
plate** baked into the map's texture page. Two independent proofs:

- the VRAM of the savestate on the autumn overworld (`slot07`, AREA033) holds a
  row of plate-shaped strips next to the map tiles, and the disc section they
  come from matches VRAM byte for byte;
- hashing every area's image sections across the JP and US discs, the pages
  that differ are exactly the nine world maps (both 256 KB pages each) plus
  three fishing spots and the Pompom dock — Capcom repainted them to localise.

**Format** (established by matching AREA033's sections against that VRAM):

| Thing | Where | Layout |
|---|---|---|
| texture page | the area section with `dest = 0x0E001000` (256 KB) | `dest = (vram_x/32) << 24 \| (vram_y/32) << 16 \| (bytes/16K) << 8 \| flag`; data in 32×32-halfword tiles, left to right then down, page 512 halfwords = **1024 8-bit texels** wide × 256 rows; lands at VRAM (448, 0) |
| palettes | the section with `dest = 0x8002BE00` (6144 B) | 12 × 256-entry CLUTs, uploaded to VRAM rows 483..494 at x = 0; the plates use **CLUT 8** on the Yraall maps (the only ones with a savestate to check) |
| plates | a strip inside the page, 16-row bands, wrapping at texel 256 | body 14 rows: rim (indices 7/9/10, corner 13), dark line (11), light line (1), 8 text rows, light, dark, shadow; then a 2-row pointer tail. Widths **44 / 60 / 76** texels (three, four, five glyph cells); text strokes are indices 12/14/15 on parchment 1..6; index 5 outlines an **empty plate cell** |

`tools/plates.py` decodes the pages (`pages` → PNG per map, `plates` →
rectangles in `analysis/plates/plates.json` and a contact sheet rendered with
a synthetic reading palette, `--clut N` for a real one). Plates are found by
their top-edge run, because neighbouring plates touch and connected
components merge them; a plate cut at texel 256 continues at the start of the
next band (ウールオル街|道) and the tool joins the two pieces.

**What the plates say** — [`names/plates.toml`](../names/plates.toml), 85
plates, 42 distinct names, transcribed by eye from the sheet (each map also
has a `?` plate and a つりポイント fishing plate, and the two Yraall maps and
the two Lost Shore / Desert maps carry identical sets):

| Map | Names |
|---|---|
| AREA016 / 033 (Yraall) | 牧場, シーダの森, やみ市, グラウス山, リヴェット山, ウールオル街道, オウガー街道, マクニール村 |
| AREA045 (Wyndia plains) | ウインディア, エッグノック街道, 山小屋, ボウモウ山, メーカース渓谷, モーランジ山, 関所 |
| AREA065 (mountains) | 塔, 茶屋, プラント, ボウモウ山, ゴミすて場 |
| AREA087 (peninsula) | 船着き場, ズブロ火山, ドック, ラパラ, 灯台, クリフ, タイドパレス |
| AREA088 (Urkan) | 船着き場, ズブロ火山, ドック, ウルカン・タパ, 遺跡, ジャンク村, 機械浜, 天使の塔 |
| AREA115 (Dauna) | ダウナ鉱山, 関所, やみ市, オウガー街道 |
| AREA121 (Middle Sea) | 船着き場, ズブロ火山, ドック, パーチ |
| AREA151 / 152 (Lost Shore, Desert) | 機械墓場, 古の都, ファクトリー, ドラグニール, コロニー, コンビナート, オアシス |

39 of the 42 have a wiki Locations row (`en`); 山小屋 (mountain hut), 遺跡
(ruins) and `?` do not. This is the pool that matches the wiki's kanji, which
is why the debug list could not.

**Are the plates slices?** Checked across the 71 whole plates (31 × 44,
33 × 60, 7 × 76): the *structure* is identical everywhere — the 14-texel end
caps have the same shape and index roles in every plate, the dark line (row 1)
is byte-identical in all 118 samples, and the widths are 28 + 16·n — but the
texels are not: the rim (row 0, 12, 13) and the parchment under the text are
per-plate dither noise, and the pointer notch (`121` / `dbd`) sits under the
plate's centre, so it drifts against a 16-texel grid. So a plate is not three
reusable texel tiles; it is a *procedure*: caps + N middles drawn with the same
row roles and index palette, noise re-rolled, notch centred. That procedure
makes any width, which is better than slices would have been.

**Pixel budget for an English plate.** Text area = plate width minus the rims,
about 36 / 52 / 68 texels for the three sizes, 8 rows tall. At the game
font's 12 px advance that is 3 / 4 / 5 glyphs; the US plates are hand-lettered
narrower than that. Any text-swap design (IDEAS: blank plate + rendered
string) has to fit those boxes or widen the plate, and an empty plate cell
already exists in the art.

## Where the sidecars are used

- `save_tool.py dump / verify` (above). `--names DIR` to point elsewhere;
  bare ids when the files are absent.
- `names/places.toml` → [`names/areas.toml`](../names/areas.toml): same key
  (`area_file`), so the poller's `summarize` can seed an alias from `caption`
  (evidence) or `dev_label` (hypothesis) instead of waiting for a screenshot.
  Not wired yet.
- Translation: the item / ability / place pools for the apply hook
  ([`LOCALIZATION.md`](LOCALIZATION.md)) now have their id order and their
  8-byte field widths, which is the constraint an English name must fit.

## The US names — the same table off the US disc (2026-09-17)

[`regional-builds.md`](regional-builds.md) had counted "a ~15 KB string table
inside `GAME.EMI` section 0" in the US build and left it as "nobody has read
what it contains". It is **this table**: the five item tables and the ability
table, in the same record order, with every `name[8]` widened to `name[12]`.
`text_tables.py --us-cue <US .cue> extract` reads it and adds a `us` column to
`items.toml` and `abilities.toml`.

| Table | JP `GAME.EMI#0` (dest `0x80196800`) | US `GAME.EMI#0` (dest `0x80195800`) | stride JP → US |
|---|---|---|---|
| consumables | `0x801C995C` | `0x801C8964` | 14 → 18 |
| key items | `0x801C9E64` | `0x801C8FDC` | 12 → 16 |
| weapons | `0x801C9F24` | `0x801C90DC` | 20 → 24 |
| armour | `0x801CA5A0` | `0x801C98A4` | 18 → 22 |
| accessories | `0x801CAA68` | `0x801C9E7C` | 16 → 20 |
| abilities | `0x801CB230` | `0x801CA718` | 16 → 20 |

**Evidence that it is the same table, not one that starts alike:** the tool
reads the US record at every JP index and compares *every numeric field* the
JP record carries (price, power, ref, flags, the ability param bytes) —
538 records, 0 mismatches — and refuses to write on any. The five US item
tables also chain `start + count × stride` exactly, as the JP ones do, and the
ability table follows the accessories after the same `0x48C` gap.

What the pairing changed:

- **33 rows gained an English name** the wiki glossary had no row for:
  `なし` = `Nothing` ×5, `パーツA..H` = `Part A..H`, `ホーンドマリーナ` =
  `Spearfish`, `IDカード` = `ID Card`, `カードキーA/B`, `バゼラード` =
  `Baselard`, `ハルバート` = `Halberd`, `バグナク` = `Tiger Claws`,
  `皮よろい` = `LeatherArmor`, `ノクトゴーグル` = `UV Glasses`,
  `マーチャントパス` = `Coupons`, `コシが痛い` = `Bad back`, `つぶらなひとみ`
  = `Hypnotize`, `ねらい撃ち` = `Target`, `パリア` = `Barrier`, and more.
- **Three glossary rows differ from the shipped string.** The `us` column
  records what Capcom shipped, not what is right: `とっこう薬` (特効薬, a
  specific remedy — the wiki's *Wonder Drug* is the literal reading) shipped
  as `Ginseng`, a localizer's choice; `シンカー` is `Sinker` (wiki: Sinkar);
  `ファイアブレス` / `アイスブレス` at ids 121/122 are `Flame Breath` /
  `Frost Breath` (the same JP names at ids 45/46 are `Firebreath` /
  `Icebreath` on the US disc too — the wiki collapsed the pair; the glossary
  cannot tell them apart because it joins on the JP string).
- **Eleven abilities the wiki names are `Noting` on the US disc** (sic — the
  placeholder is misspelt in all 12 rows that carry it): `しろはた`, `ラーク`,
  `ザワルド`, `サラニ` ×2, `ゴボウセイ`, `すみ`, `すみすみ`, `死の爆弾`,
  `ルーレット`, `ミヤクリ`. Cut or enemy-only content whose names the US
  build never shipped; the wiki's names for them are not from this table.
- **The US name alphabet is ASCII plus one code:** `0x8E` (16 uses, always
  where an apostrophe belongs — `Mage<8e>s Robes`, `Mind<8e>s Eye`). Two ASCII
  bytes are repurposed as glyphs: `=` where the wiki shows a hyphen
  (`Fish=head`, `Man=o<8e>=War`) and `>` where it shows a full stop
  (`Lgt>Clothing`). Consistent with the JP finding that `0x3E`/`0x3F`/`0x40`
  are symbols, not ASCII; the US atlas itself is still unread, so the tool
  keeps the raw bytes.

So the answer to the regional-builds question is: **yes, it needs translating**
— it is the item and ability names the menus draw — and the constraint is the
one already recorded: 8 bytes per name in the JP layout against 12 in the US.
Every `us` string longer than 8 bytes (most of them) does not fit the JP record
as stored, which is why the US build widened the field.

## Open

- **Masters.** `FIRST.EMI#11` (`0x80014000` band) is not a record table: it is
  a script-style message block (u16 offset table from `0x8001525C`) holding
  description / location pairs (神に仕える そうりょ / ウルカン・タパ …) with the
  master's name elsewhere. Read it through the message-table model, not this tool.
- The `ref` index, the accessory effect code, weapon `+8..+12` (element /
  who-can-equip bits by the look of `0x0101` / `0x0105` / `0x0201`), the ability
  param bytes past `type` (AP cost is a hypothesis for `b5`).
- The MTEST head bytes (`sel`) and the u32 `0x1C1` before them.
- Plates: which CLUT the game really uses on the seven non-Yraall maps
  (needs a savestate on each), the spot → destination-AREA link (in the
  world-map logic, not its strings), and the two 31-texel boxes the
  extractor clips (関所 on AREA115, 古の都 on AREA151/152 — the art is whole).
- The 155 places without an `en` are mostly interiors and encounter maps the
  wiki does not list at all; the kana→romaji fold already covers what it can.
  Wiring `places.toml` into `area_poller.py summarize` is the next step (I2).
