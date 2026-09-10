#!/usr/bin/env python
"""save_import.py -- copy Breath of Fire III saves from the US card onto a JP card.

BoF3 (USA) SLUS-00422 and BoF3 (Japan) SLPS-00990 write the *same* save block:
the 0x10B0-byte persistent game block at file +0x200, checksummed by the same
byte-sum into the u16 at +0x270 (docs/BATTLE_RAM.md, tools/save_tool.py).  A US
save therefore only needs its memory-card *directory entry* renamed from
`BASLUS-00422BOF3NN` to `BISLPS-00990BOF3NN` -- the name template the JP game
builds at START.EMI 0x801D0ED4 (names/data.toml SaveFile_NameTemplate) -- for
the JP build to find and load it.  The block itself is copied byte for byte,
so its checksum stays valid.

    python tools/save_import.py list   "saves/Breath of Fire III (USA).1.mcr"
    python tools/save_import.py import "saves/Breath of Fire III (USA).1.mcr" saves/card2.mcd
    python tools/save_import.py import SRC DST --slot 1 --as 0

`import` refuses to overwrite an occupied directory slot unless --force, and
backs the destination up to DST.bak first.  Verify the result with
`python tools/save_tool.py list DST`.
"""
import argparse
import functools
import os
import shutil
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):        # card titles are Shift-JIS
    sys.stdout.reconfigure(encoding="utf-8")

CARD_SIZE = 0x20000
FRAME = 128
BLOCK = 0x2000
GAME_OFF = 0x200
GAME_LEN = 0x10B0
CKSUM_OFF = 0x70               # inside the game block (RAM 0x80144944)

US_PREFIX = "BASLUS-00422BOF3"
JP_PREFIX = "BISLPS-00990BOF3"

STATE_FREE = 0xA0
STATE_FIRST = 0x51


def xor(buf):
    return functools.reduce(lambda a, b: a ^ b, buf, 0)


def load(path):
    d = bytearray(open(path, "rb").read())
    if len(d) != CARD_SIZE:
        raise SystemExit("%s: %d bytes, expected a raw 128 KiB card image" % (path, len(d)))
    if d[:2] != b"MC":
        raise SystemExit("%s: header frame does not start with 'MC'" % path)
    return d


def dirent(card, i):
    return card[i * FRAME:(i + 1) * FRAME]


def entry_name(card, i):
    return bytes(dirent(card, i)[10:31]).split(b"\0")[0].decode("ascii", "replace")


def entry_state(card, i):
    return card[i * FRAME]


def block_checksum(block):
    g = block[GAME_OFF:GAME_OFF + GAME_LEN]
    stored = struct.unpack_from("<H", g, CKSUM_OFF)[0]
    calc = (sum(g) - g[CKSUM_OFF] - g[CKSUM_OFF + 1]) & 0xFFFF
    return stored, calc


def bof3_slots(card):
    """1-based directory indices holding a BoF3 save, either region."""
    out = []
    for i in range(1, 16):
        if entry_state(card, i) & 0xF0 != 0x50 or entry_state(card, i) & 0x0F != 1:
            continue
        name = entry_name(card, i)
        if name.startswith(US_PREFIX) or name.startswith(JP_PREFIX):
            out.append(i)
    return out


def describe(card, i):
    name = entry_name(card, i)
    block = card[i * BLOCK:(i + 1) * BLOCK]
    stored, calc = block_checksum(block)
    title = bytes(block[4:0x44]).split(b"\0")[0].decode("shift_jis", "replace")
    h, m, s = block[GAME_OFF + 0x6E8:GAME_OFF + 0x6EB]   # 0x80144FBC play time
    return "%-2d %-20s cksum %s  %02d:%02d:%02d  %s" % (
        i, name, "OK " if stored == calc else "BAD", h, m, s, title)


def cmd_list(args):
    card = load(args.card)
    found = bof3_slots(card)
    if not found:
        print("%s: no BoF3 saves (US or JP)" % args.card)
        return
    for i in found:
        print(describe(card, i))


def cmd_import(args):
    src = load(args.src)
    dst = load(args.dst)

    todo = bof3_slots(src)
    if args.slot is not None:
        if args.slot not in todo:
            raise SystemExit("source slot %d holds no BoF3 save (have %s)" % (args.slot, todo))
        todo = [args.slot]
    if not todo:
        raise SystemExit("%s holds no BoF3 saves" % args.src)

    free = [i for i in range(1, 16) if entry_state(dst, i) == STATE_FREE]
    plan = []
    for n, si in enumerate(todo):
        block = src[si * BLOCK:(si + 1) * BLOCK]
        stored, calc = block_checksum(block)
        if stored != calc:
            raise SystemExit("source slot %d: game-block checksum %#06x != %#06x, refusing"
                             % (si, stored, calc))
        if args.into is not None:
            di = args.into + n
        else:
            if not free:
                raise SystemExit("destination card has no free directory slot")
            di = free.pop(0)
        if not 1 <= di <= 15:
            raise SystemExit("destination slot %d out of range 1..15" % di)
        if entry_state(dst, di) != STATE_FREE and not args.force:
            raise SystemExit("destination slot %d holds %r; pass --force to overwrite"
                             % (di, entry_name(dst, di)))
        num = args.as_num + n if args.as_num is not None else int(entry_name(src, si)[-2:])
        plan.append((si, di, num, block))

    names = set()
    for _, _, num, _ in plan:
        if num in names:
            raise SystemExit("two saves would both be BOF3%02d; use --as" % num)
        names.add(num)
    for i in range(1, 16):
        if entry_state(dst, i) != STATE_FREE and i not in [d for _, d, _, _ in plan]:
            n = entry_name(dst, i)
            if n.startswith(JP_PREFIX) and int(n[-2:]) in names:
                raise SystemExit("destination already has %s at slot %d; use --as" % (n, i))

    if not args.dry_run:
        shutil.copyfile(args.dst, args.dst + ".bak")

    for si, di, num, block in plan:
        name = ("%s%02d" % (JP_PREFIX, num)).encode("ascii")
        ent = bytearray(FRAME)
        ent[0] = STATE_FIRST                 # first (and only) block of a file
        struct.pack_into("<I", ent, 4, BLOCK)  # file length: one block
        struct.pack_into("<H", ent, 8, 0xFFFF)  # no next block
        ent[10:10 + len(name)] = name
        ent[0x7F] = xor(ent[:0x7F])
        dst[di * FRAME:(di + 1) * FRAME] = ent
        dst[di * BLOCK:(di + 1) * BLOCK] = block
        print("slot %d %-20s -> slot %d %s" % (si, entry_name(src, si), di, name.decode()))

    dst[0x7F] = xor(dst[:0x7F])

    if args.dry_run:
        print("(dry run: %s not written)" % args.dst)
        return
    with open(args.dst, "wb") as f:
        f.write(dst)
    print("wrote %s (backup at %s.bak)" % (args.dst, args.dst))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="show BoF3 saves on a card, either region")
    pl.add_argument("card")
    pl.set_defaults(func=cmd_list)

    pi = sub.add_parser("import", help="copy US saves onto a JP card, renamed")
    pi.add_argument("src")
    pi.add_argument("dst")
    pi.add_argument("--slot", type=int, help="source directory slot (default: every BoF3 save)")
    pi.add_argument("--into", type=int, help="first destination directory slot (default: first free)")
    pi.add_argument("--as", dest="as_num", type=int,
                    help="first BOF3NN number to write (default: keep the source's)")
    pi.add_argument("--force", action="store_true", help="overwrite an occupied destination slot")
    pi.add_argument("--dry-run", action="store_true")
    pi.set_defaults(func=cmd_import)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
