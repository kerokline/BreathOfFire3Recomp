# Mednafen as an isolated oracle

**Status:** STABLE (verified 2026-09-03)

A stock Mednafen 1.32.1 install lives in `./mednafen/` (gitignored: binary
distribution, BIOS in `firmware/`, local config). Mednafen is the parent of
Beetle PSX, so it is the same PSX core the framework's `psx-beetle` tool
embeds, but running as a separate, untouched process. Use it to answer "what
does real hardware do here?" without building anything.

Driver: [`tools/mednafen_ctl.py`](../tools/mednafen_ctl.py).

## What crosses over from our runtime

| Artifact | Compatible? | Detail |
|---|---|---|
| Disc image | yes | Same `isos/Breath of Fire III (Japan).cue`. Mednafen warns about a missing `.sbi`; harmless for this title. |
| BIOS | yes | `mednafen/firmware/scph5500.bin` (JP). Never commit it. |
| Memory cards | **yes, byte for byte** | Both sides use raw 128 KiB images with the `MC` header. Only the filename differs. |
| Savestates | no | Our `.pst` is a native-state serialization; Mednafen's `.mcN` is its own zlib'd chunk format. Neither loads the other. |
| Input bindings | n/a | Mednafen's own keyboard map; the driver reads it from `mednafen.cfg`. |

### Memory card naming

`filesys.path_sav` in `mednafen.cfg` points at our `saves/` directory.
Mednafen resolves a card as `<disc base>.<slot>.mcr` first (the `%M` hash
field is empty on the first evaluation) and falls back to
`<disc base>.<md5>.<slot>.mcr`. `launch --card` writes both names so whichever
it picks is ours:

| psx-runtime | Mednafen (`saves/`) |
|---|---|
| `card1.mcd` | `Breath of Fire III (Japan).0.mcr` and `Breath of Fire III (Japan).79d72f3a…0.mcr` |
| `card2.mcd` | `…1.mcr` (not copied; Mednafen creates a blank one) |

Mednafen rewrites its copies on exit. It never touches `card1.mcd`; use
`card export` to bring a Mednafen save back (it backs up the old card first).

## Controlling it

There is no scripting surface: `-remote` is a bare flag in 1.32 with no stdin
command vocabulary (checked against the binary's strings), and the debugger is
keyboard-only. The driver therefore injects Windows scancodes into the
Mednafen window with `SendInput`, translating from the SDL scancodes bound in
`mednafen.cfg` (`psx.input.port1.gamepad.*`, `command.*`). Before every
injection it brings the window to the foreground and verifies the foreground
process is Mednafen; otherwise it refuses, so keys never land elsewhere.

```
python tools/mednafen_ctl.py launch --card        # boot from saves/card1.mcd
python tools/mednafen_ctl.py press start          # pad buttons: up down left right cross circle square triangle start select l1 l2 r1 r2
python tools/mednafen_ctl.py press down circle    # sequence; --chord to press together; hold X --hold 2 for a long press
python tools/mednafen_ctl.py snap --out shot.png  # F9 snapshot, copied out of mednafen/snaps/
python tools/mednafen_ctl.py state save 2 / load 2
python tools/mednafen_ctl.py frame 5              # frame-advance (leaves it paused; `key pause` resumes)
python tools/mednafen_ctl.py key fast_forward     # any command.* hotkey by name
python tools/mednafen_ctl.py log --tail 20        # mednafen/stdout.txt
python tools/mednafen_ctl.py quit
```

`launch --set key=val` passes any Mednafen setting override on the command
line (e.g. `--set nothrottle=1`, `--set psx.dbg_mask=cpu`).

### Traps paid

- **`MEDNAFEN_HOME` must point at `./mednafen`.** Without it the base
  directory is `~/.mednafen`, the BIOS is not found, and the process exits
  during boot with the window already open. Mednaffe sets it; the driver sets
  it too.
- **Circle confirms, Cross cancels.** This is the Japanese release; a
  `cross`-based menu script silently backs out.
- **Give the card check time.** Title → menu takes ~40 s from cold boot
  (PlayStation logo, Capcom logo, card scan). "ファイルのチェック中です" on the
  load screen needs ~4 s before the save list draws.
- Snapshots land in `mednafen/snaps/` as `<disc base>-NNNN.png` at the
  emulator's native output size (700×480 here, `psx.correct_aspect`).
- **The title cursor already sits on LOAD GAME when the card has saves.**
  Start, Start, Circle reaches the card picker; a `down` first wraps onto NEW
  GAME and Circle then opens the name-entry screen, **which cannot be
  cancelled** (Cross only deletes characters) — `quit` and relaunch, ~60 s
  (user, 2026-09-05). Then Circle on メモリーカード1 and ~8 s for the file check.

## Verified 2026-09-03

Launched with `--card`, injected Start ×2, Down, Circle, Circle: reached the
load screen and it listed the three saves from `card1.mcd` (Ryu Lv1 00:28,
02:35, 02:19). Savestate slot 2 saved on the load screen, backed out with
Cross, `state load 2` returned to the load screen. Clean exit via `quit`.

**2026-09-05:** used as the independent oracle for `tools/save_tool.py`: booted
from the re-mapped `card1.mcd` (Start, Start, Circle, Circle), the load screen
listed リュウ Lv 1 at 00:28 / 05:13 / 05:10 with one portrait for file 1 and
Teepo / Rei / Ryu for files 2 and 3 — the tool's `list` and slot-summary
output byte for byte (`analysis/mednafen_loadscreen_card1.png`).
