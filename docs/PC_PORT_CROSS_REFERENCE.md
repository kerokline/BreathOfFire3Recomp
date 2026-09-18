# The Chinese PC port as a cross-reference

**Status:** STABLE (surveyed 2026-09-18; the two `TEXT_ENGINE.md` corrections it
produced are proven by disc census + decompile, not by the port)

A second, independent reverse-engineering effort exists against a *different
binary of the same game*: **`bof3ext`**, a replacement `ddraw.dll` for the 2001
Chinese PC port (`BOF3.exe`, x86, ~2.58 MB, 2001-04-18). It hooks the shipped
executable with MinHook at hardcoded addresses to translate it to English, fix
bugs, and run it on modern hardware.

- Local clone: `C:\Users\kerok\Documents\GitHub\bof3ext`
- Upstream: `github.com/TheRealBiggs/bof3ext`; text/font/texture assets live in a
  separate repo, `TheRealBiggs/bof3ext_resources`, installed as `NewData/`
- **No `LICENSE` file.** Read it for reference; do not copy its code, tables or
  translated strings into this repo without asking the author.

This document records what is worth taking from it and what is not. The rule for
everything below: *the port is corroboration, never authority.* Where it and our
own work disagree, the disc and the boot-EXE decompile decide — which is exactly
what happened in §2.

## 1. Why it is worth reading at all

The port is not a rewrite. It kept the PlayStation original's data shapes and its
rendering model — it builds PSX GPU primitive packets and replays them through
DirectDraw. Two spot checks establish the degree of kinship:

| Thing | PSX (ours) | PC port (theirs) |
|---|---|---|
| Persistent character record stride | `0x80144964 + roster * 0xA4` ([`BATTLE_RAM.md`](BATTLE_RAM.md)) | `0x64B390 + 164 * n` — **the same 164 bytes** |
| Current area number | `0x80143F00` | byte at `0x904EFC` |
| Message open → box re-point | `Msg_OpenScript` → `MsgBox_Reset` ([`TEXT_ENGINE.md`](TEXT_ENGINE.md)) | `LoadDialogue` `0x4976D0` writes the string pointer to `0x7DEE4C`, then re-enters `0x497770` |

So their field-level findings are usable as *hypotheses about ours*, and their
control-code table is a genuinely independent derivation of a vocabulary we had
only read one way.

## 2. Control codes — corroboration, and two corrections to `TEXT_ENGINE.md`

Their table is `docs/translation.md` in that repo, expressed as `{{TAG}}` markup
that `TranslateEncodedText()` rewrites into bytes. Against our
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) map:

| Byte | Ours | Theirs | Verdict |
|---|---|---|---|
| `01` `02` `03` `05` `06` | newline / page break / character name / colour begin / colour end | same | agree |
| `07 nn` | insert from the 32-byte record table `0x801490D3 + 0x20·nn` | "insert parameter *n*" | agree |
| `0A hh` | `SE_Play(hh \| 0x200)` | play sound | agree |
| `0B` | in-line pause / beat | pause | agree — backs the 2026-09-12 correction that `0x0B` is a delay, not `y += 8` |
| `0D` / `0E 0F hh` | emphasis span open / close, then the `0x0F` preset | `{{EFCTS}}` / `{{EFCTE:hh}}` = `\x0E\x0F hh` | agree — they encode close-then-preset as one atom, which is exactly the "every `0x0F` follows a closed span" pattern our disc census found |
| `14` | choice: three argument bytes, then count NUL-separated options | same | agree |
| `16 nn` | timed page break, `nn` frames | `{{DURTN:n}}` duration | agree |
| **`10` / `11`** | "toggle flag `0x10` of `0x801490A0`" / not identified | **instant-print start / end** | **theirs is right — see 2.1** |
| **`0C nn`** | "(string head only) speaker/portrait id" | "textbox type" | **both were wrong about "head only" — see 2.2** |
| `04 nn` | insert named character, record `0x80144963 + 0xA4·nn` | not in their table | ours only |

### 2.1 `0x10` / `0x11` are instant-print start / end

Their label is confirmed twice over, without reference to their binary.

**Mechanism** (`MsgBox_Step` `0x8015096C`, decompile in
`analysis/ghidra/SLPS_009.90_decomp/`): the switch arm for `0x10 <= code < 0x12`
is a single `DAT_801490a0 ^= 0x10` — *both* bytes toggle the same bit. The
payoff is at the bottom of the same function: the per-glyph delay
(`0x801490A2`, from the pair table at `0x8017FF2C`) is only computed
`if ((DAT_801490a0 & 0x10) == 0)`. Bit set ⇒ no delay ⇒ the rest of the run
prints in one step. That is instant print, and the open/close framing follows
from it being a toggle used in pairs.

**Census** (`tools/page_rows.py codes --bin-root D:\BoFIII\BIN`, 6,696 distinct
messages over the 200 area script blocks): `0x10` appears **101** times and
`0x11` appears **101** times, and a per-message walk finds the running depth
returns to zero in **6,696 of 6,696** messages. A bare toggle would not balance;
a matched start/end pair does.

### 2.2 `0x0C nn` is not head-only, and the argument is not a speaker id

Our row claimed `0x0C` appears only at the head of a string and carries a
speaker/portrait id. The disc says otherwise:

- **2,419 uses**, of which **1,639** are the leading byte of a message and
  **780 are mid-message.** "String head only" is false.
- **Head arguments are concentrated:** 15 distinct values, and `05` (696) plus
  `06` (669) account for **83%**. A cast-of-characters portrait id would be flat
  across dozens of values; two values carrying five sixths of the uses is the
  shape of a *mode selector*. Their "textbox type" fits the distribution better
  than ours does.
- **Mid-message arguments are a wider set** (20 distinct, led by `02`, then
  `05`/`06`, with a tail through `0x12`–`0x14`, `0x24`–`0x26`, `0x80`+).

What the box path actually does with it, from the decompile:

- `MsgBox_Reset` `0x8015042C` eats a *leading* `0x0C` and stores its argument to
  `DAT_801490CA` (else stores `0`). Nothing in the boot EXE reads `0x801490CA` —
  so an overlay does, and that read is the thing that would name this code.
- `MsgBox_Step` shares one handler between `0x05` and `0x0C`: advance the
  pointer past the argument, do nothing else. So a **mid-message `0x0C` is
  consumed and ignored by the box** — our "never seen by the stepper" was right
  about the effect and wrong about the mechanism.

**Open.** Who reads `0x801490CA`. A `capture --watch 0x801490CA` across an NPC
line with a `05` head and one with a `06` head would settle "textbox type" vs
something portrait-shaped in one session. Until then the row in
`TEXT_ENGINE.md` says what is proven and no more.

**No pipeline impact.** `tools/build_script_xlate.py` already lists `0x0C` in
`ARG1` and carries every occurrence through byte for byte; only its comment and
the `head` docstring describe `0x0C` as a head-only speaker marker. The emitted
tables are unaffected.

## 3. Structures — field names for bytes we call gaps

Their `bof3ext/src/bof3/*.ixx` files are pure declarations of the PC binary: no
behaviour, just addresses and struct layouts. Useful as *named hypotheses* for
our tables, not as layouts — the port widened `name` from 8 to 16 bytes to fit
Chinese, so offsets shift even where field order does not.

| Their struct | Fields | Bears on |
|---|---|---|
| `SkillData` | `name[16]`, `targetFlags`, `category:4`, **`examineChance:4`**, `cost`, `power`, `element`, `descriptionId` | our 16-byte abilities table at GAME.EMI `0x801CB230` ([`TEXT_TABLES.md`](TEXT_TABLES.md)). `examineChance` is a nibble we have no name for and a concrete lead on the Examine / ability-learning path |
| `WeaponData` | `name`, `equipFlags`, `flags`, `iconId`, `element`, `weight`, `_`, `power`, `descriptionId`, `cost` | the weapon table; `element` and `weight` are unnamed in ours |
| `ArmorData` | `… weight, defense, descriptionId, cost` | the armour table |
| `ItemData` | `name`, `flags`, `iconId`, `descriptionId`, `cost` | our 14-byte item record `name[8] flags type 0x40 price` at `0x801C995C` — same field *order*, wider name |
| `Character` | `name[8]`, `id`, `level`, …, equipment ids ×6, `curHP`, …, `power`/`defence`/`agility`/`intelligence` | the 164-byte persistent record; equipment-id block ordering is worth checking against ours |
| `EnemyBattleData` @ `0x93B9E0` | `name[12]`, …, `hp`, …, `enemyId` | our enemy working records, stride `0x118` at `0x801EB620`. **Nothing about resistances** — `element` appears in their `WeaponData` and `SkillData` and nowhere else in the tree, so the port gave no help on the affinity grid we found at species `+0xC0..+0xC4` ([`BATTLE_RAM.md`](BATTLE_RAM.md) *The resistance grid*) |

### `descriptionId` — checked, and it is our `ref` (2026-09-18)

Their layouts carry a **`descriptionId` u16 on every item and skill record**. We
had the same field and called it `ref`, guessing it "most likely" pointed at
descriptions ([`TEXT_TABLES.md`](TEXT_TABLES.md)). Their naming was the prompt to
go and prove it.

It resolves through `Msg_SystemPtr` `0x801503F8` into the `0x80014000` system
pool — id bits 14–15 pick one of the header words, the low 14 bits index that
word's message table. **All 311 item refs and all 227 ability refs land in range
and resolve**, the strings are the right descriptions, and the first number in
each weapon/armour description equals the `power` field we had extracted
separately for **147 of 149** records (the two exceptions carry no digits).
Numbers and method in [`TEXT_TABLES.md`](TEXT_TABLES.md) *`ref` is the
description id*.

Worth noting for its own sake: their `GetText` splits an id as
`fileNum = index >> 14`, `index &= 0x3FFF`, which is the **same two selector
bits** our `Msg_SystemPtr` uses on the header word. Two teams, two binaries, one
id layout.

This is the pattern to repeat with the rest of §3: their name is a hypothesis,
our disc is the proof.

## 4. What does not transfer

**The archives are repacked — there is no byte-level asset path.** `DAT/` holds
742 `.DAT` files (`AREA000`…, `BOSS001`–`BOSS055`, `BATTLE`, `FIRST`, …), and
the names line up with our `.EMI` families, but the containers do not. Parsed
`AREA000.DAT` 2026-09-18: a `(offset, size)` TOC at `0x198`, no `MATH_TBL`
magic, and subfile 0 at `0x380` is a **RIFF WAVE** — the port decompressed the
PSX audio and re-containered everything. `tools/emi.py` will not read these and
should not be taught to.

**The Chinese script is not economically harvestable.** A GBK scan of
`AREA000.DAT` returns 5,096 candidate runs, all noise from graphics and packed
data. The text is stored in the port's own encoding — their
`EncodeUnicodeCharacter` is `((c | 0x8000) >> 8) | ((c & 0xFF) << 8)`, i.e.
byte-swapped with the high bit set — and resolved at runtime through
`GetText` `0x497740` with a PC-only index split (`fileNum = index >> 14`,
`index &= 0x3FFF`) that has no PSX counterpart. Extracting it means writing both
a container parser and a decoder, to obtain a JP→ZH translation, when the
official US script is already aligned slot-for-slot
([`LOCALIZATION_APPLY.md`](LOCALIZATION_APPLY.md)). Not worth it.

**The rendering work is inapplicable.** Their OpenGL layer re-emulates PSX
texture pages and CLUT lookups in a fragment shader because the port replays GPU
packets through DirectDraw. We emulate the GPU properly; this is solved ground.

## 5. Leads worth keeping

1. **`0x801490CA`'s reader** — §2.2. The one experiment that would close the
   `0x0C` question.
2. **`examineChance`** — their name for the **high** nibble of the byte whose
   **low** nibble we already read as `type` (`abilities.toml` `b1 & 3`;
   `AbilityList_ForType` `0x80167514` files by it). Their `category:4` and our
   `type` agree without argument: over 227 records the low nibble only ever
   takes the values 0, 1, 2, 3 (14 / 18 / 55 / 140), so `& 3` and `& 0xF` are
   the same read. The high nibble is 0 (130 records), 3 (91), and 1, 5, 7 (two
   each) — a small graded set, consistent with a chance class and inconsistent
   with a continuation of `category`. Not proof; the proof is the Examine
   command's own code, which we have not decoded.
3. ~~**`descriptionId`**~~ — **done 2026-09-18**, it is our `ref`; see §3.
4. **`bof3ext_resources`** — 360 files: per-area dialogue plus flat
   line-indexed lists for item, weapon, armour, accessory and skill names, menu
   tabs and categories, all in the `{{TAG}}` markup above. As dialogue it is a
   translation of a translation and worse than the US script. As **menu and name
   text** it is an English corpus, unconstrained by the JP byte budget, for
   exactly the categories [`translation-scope-script-first`] deferred. Not
   checked out locally; licence unclear (§ header). Revisit if and when menu
   translation is scoped.
