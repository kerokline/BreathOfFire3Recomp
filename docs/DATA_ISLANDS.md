# Data islands — what the compile's "data walked as code" rejections are

**Status:** evidence, 2026-09-07; the classifier and the join corrected
2026-09-08 (see *The code row was an artifact* below -- the 23 "real gaps"
this file used to list are 0). Tool: [`tools/data_islands.py`](../tools/data_islands.py);
names: [`names/data.toml`](../names/data.toml); runs as phase 5a' of
`tools/axis_b_loop.sh`.

## The finding

Overlay bands are shared address windows. Every interpreted PC the harvest
observes is demanded for *every* occupant of its band, because the tooling
does not yet know which occupant was resident (the resident-image stamp is
the open framework item in HANDOFF §1b). For most occupants the address is
code and the per-variant compile emits a fragment. For some it is a table or
a string that merely sits where a sibling occupant has a function, and the
static walk from that entry hits a non-R3000 opcode inside the data.
`compile_overlays.py` records those as deterministic rejections in
`generated/interior_fail_memo.txt` (`generated-c-audit: 0 unknown_bad, N
unsupported`) and never retries them. That is correct behaviour, and the
loop's `[audit]` failure list is that memo. But "unsupported" reads like a
problem and says nothing about the bytes.

The 2026-09-07 afternoon session raised 11 such pairs. Read by hand, then
by the tool, every one is identifiable data:

| entry | occupant | what it is |
|---|---|---|
| `0x800C1CC0` / `CC8` / `CD0` | BOSS021 | one table: flag header, `FF` padding, ~30 function pointers into the battle overlay and into BOSS021 itself. A per-boss behaviour dispatch table; the same shape recurs in BOSS015/017/023/029/030/031 |
| `0x801EF9E4` | MAGIC106 | halfword id sequence `01 05 0F 0B 04 07 0C 09 FF FF`, then zero fill |
| `0x801EF9E4` | MAGIC109 | word offset table `A8 5C 5C E4 5C`, then zero fill |
| `0x801EF9E4` | MAGIC146 | sparse flag words |
| `0x801EFAB8` | MAGIC050 | small structs holding pointers back into MAGIC050 code |
| `0x801F71FC` | SCENA17 | ASCII: `Sound Design`, `YOSHINO AOKI`, `AKARI KAIDA`, `TADASHI SANZEN`, `Magic Effect`, `Battle Program` — the ending staff roll. SCENA17 is the credits scenario |
| `0x801EEC50` | BATL_END | printf formats `%7d` and `*%2d` for the results-screen tally; the next function's prologue starts 12 bytes later |
| `0x801EEC50` | COMMU00 | a halfword lookup table |
| `0x801D0ED4` | START | a pointer, then `BISLPS-00990BOF3%02d` — the memory-card save file name template |

The named ones (save-name template, tally formats, staff roll, boss handler
table) are in `names/data.toml` with the bytes cited as evidence.

## How the tool joins a memo line to an occupant

The memo key's hash covers the compiler's whole recipe and cannot be
recomputed outside it. The join is by exclusion instead: a memo line for
(band, entry) can only belong to an occupant whose image spans the entry
*and* which has no compiled piece (fragment or whole function) at it in
`generated/overlays_static.c`.

**N lines for N candidates is the healthy outcome, not a fault.** Candidates
are only the occupants with no piece at that entry; occupants that have one
compiled fine and never enter the count. So N-for-N says "every occupant that
lacked a piece there also failed" -- which is what data at a shared address
looks like. It carries no claim about the band.

The unsound case is *more candidates than lines*, because exclusion tests "no
piece **starting** at this entry", which is weaker than "was rejected". An
occupant whose coverage there begins a few words earlier, or which was never
demanded, also lands in the candidate set -- and then inherits a sibling's
failure. On the 2026-09-07 build this happened at one address, `0x801F7568`
(1 line, 2 candidates), and the tool printed both SCENA13 and SCENA17 as
failures. One of those rows was fiction.

**The tiebreaker (2026-09-08):** when candidates outnumber lines, drop the
ones whose linear walk from the entry reaches `jr ra` with every word
decoding. A walk that gets to a return emits a piece, so the line is not
theirs. This is decided from the bytes and does **not** compare the memo's
`N unsupported` count -- that count comes from the compiler's own notion of
unsupported, which is not reproducible here, so matching against it could
eliminate the wrong candidate. The set is never emptied.

At `0x801F7568` it is decisive. SCENA13 holds an ordinary function --
`addiu sp,sp,-0x20`, two `jal`s, `jr ra` at +136, zero words that fail to
decode in 4,700. SCENA17 holds the staff roll (`SANEZ`, `Magic Effect`), and
refuses at +12. The line reporting 51 unsupported is SCENA17's; SCENA13 was
never rejected at all. Its walk is clean, so the tiebreaker removes it and
the flag clears.

## What the whole memo is

Classifying all 4,073 rejected (entry, occupant) pairs of the 2026-09-07
build, as the corrected classifier reads them (2026-09-08):

| kind | pairs | reading |
|---|---|---|
| mixed (struct-like) | 2,400 | byte/halfword records: sprite, animation, coordinate tables; the heuristics do not name a stride |
| ascii strings | 826 | printf pools, menu labels (`PLAY  EXIT`, `MON...`), file-name templates |
| jp text | 345 | kana/kanji through the script decoder (`ウォーカバウト`, item and place strings) |
| pointer table | 330 | handler and dispatch tables |
| halfword / word tables | 154 | ids, offsets, sizes |
| zero fill | 16 | padding |
| **code** | **2** | MAGIC002 `0x801EEC10`, COMMU00 `0x801EEC9C` — and neither is a gap; see below |

**Every row is harmless.** The occupant cannot execute at the address, so it
needs no piece there. There is no list to carry into compile-side work.

### The code row was an artifact

This file used to report **23** pairs (29 by 2026-09-08) as "code, walk failed
downstream — the only kind that is an actual gap", and named them as the
compile-side worklist. Auditing all 29 against the capture bytes, none was a
gap. Three separate causes:

- **Zero fill scored as code (24 of 29).** `_looks_like_code` credited
  `w == 0` as a hit, reasoning that a nop is code. A nop and zero fill are the
  same four bytes, so a zero-filled window scored 100 %. Zero words are now
  excluded from the ratio.
- **Tables that decode as control flow (2 of 29).** SHOP `0x801E5710` is
  3-byte records whose first word decodes as a `jal` *into* RAM; BATE
  `0x801D8CD0` is packed halfwords that decode as a column of `beq`, one of
  them a plausible +256. Opcode validity cannot separate these from code. The
  classifier now requires a **frame** — `addiu sp,sp,-imm` or `jr ra` in the
  window — which no table produced and every real entry has.
- **A misattributed memo line (1 of 29).** SCENA13 `0x801F7568`, resolved by
  the tiebreaker above.

The 2 that survive are real code, and still not gaps: the entry sits on a
short data pad and the function behind it is compiled at its own address
(MAGIC002 has a piece at `0x801EEC14`, COMMU00 at `0x801EECA0`). The tool
checks that now and reports them as *data pad in front of a compiled
function*, keeping the "real gap" wording for a refused entry with no piece
behind it — currently none.

The general lesson, since the same shape will recur: an opcode-validity test
run over a shared address window has no negative evidence in it. Data decodes.
What separated code from tables here was structure the data does not imitate —
a stack frame, a return — and coverage the compile already emitted.

## Using it

```bash
python tools/data_islands.py                 # the latest session's entries
python tools/data_islands.py --session ID    # one session's entries
python tools/data_islands.py --all           # every memo line, with the code list
python tools/data_islands.py --json-out analysis/data_islands.json
```

Every demand originates in an observed PC, so every memo line is "entered"
by construction; the useful default is the newest session's PCs, which are
the ones the loop just raised. Add a name to `names/data.toml` and the tool
prints it beside the bytes on the next run.
