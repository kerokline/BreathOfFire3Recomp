#!/usr/bin/env python
"""Disassemble a range of the staged PS-X EXE.

The generated C in `generated/` carries the raw encoding of every instruction in
a trailing comment, but 2.5M lines of instrumented C is not a readable view of
control flow. This gives the same bytes back as MIPS.

    python tools/disasm_exe.py 8017E0E0:120
    python tools/disasm_exe.py 8017DD60:19 801751C0:39

Each argument is HEXADDR:COUNT (count in instructions). Addresses are guest
virtual addresses; KSEG0/KSEG1 are masked to the physical load address.

Defaults to `disc/SLPS_009.90` (load 0x80093800, per docs/INVENTORY.md); both
are overridable with --exe / --load for other titles or overlays.
"""
import argparse
import struct
import sys

REGS = ['zr', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3',
        't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
        's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7',
        't8', 't9', 'k0', 'k1', 'gp', 'sp', 'fp', 'ra']

SPECIAL = {
    0x00: 'sll', 0x02: 'srl', 0x03: 'sra', 0x04: 'sllv', 0x06: 'srlv',
    0x07: 'srav', 0x08: 'jr', 0x09: 'jalr', 0x0c: 'syscall', 0x0d: 'break',
    0x10: 'mfhi', 0x11: 'mthi', 0x12: 'mflo', 0x13: 'mtlo', 0x18: 'mult',
    0x19: 'multu', 0x1a: 'div', 0x1b: 'divu', 0x20: 'add', 0x21: 'addu',
    0x22: 'sub', 0x23: 'subu', 0x24: 'and', 0x25: 'or', 0x26: 'xor',
    0x27: 'nor', 0x2a: 'slt', 0x2b: 'sltu',
}

OPS = {
    4: 'beq', 5: 'bne', 6: 'blez', 7: 'bgtz', 8: 'addi', 9: 'addiu',
    10: 'slti', 11: 'sltiu', 12: 'andi', 13: 'ori', 14: 'xori', 15: 'lui',
    32: 'lb', 33: 'lh', 34: 'lwl', 35: 'lw', 36: 'lbu', 37: 'lhu', 38: 'lwr',
    40: 'sb', 41: 'sh', 42: 'swl', 43: 'sw', 46: 'swr',
    0x30: 'lwc0', 0x32: 'lwc2', 0x38: 'swc0', 0x3a: 'swc2',
}

# MMIO the PSX exposes, so a polling loop names its device instead of a number.
MMIO = [
    (0x1f801040, 0x1f80104f, 'SIO0 (controller/memcard)'),
    (0x1f801050, 0x1f80105f, 'SIO1 (serial)'),
    (0x1f801070, 0x1f801077, 'IRQ (I_STAT/I_MASK)'),
    (0x1f801080, 0x1f8010ff, 'DMA'),
    (0x1f801100, 0x1f80112f, 'Timers'),
    (0x1f801800, 0x1f801803, 'CD-ROM'),
    (0x1f801810, 0x1f801817, 'GPU (GP0/GP1)'),
    (0x1f801820, 0x1f801827, 'MDEC'),
    (0x1f801c00, 0x1f801fff, 'SPU'),
]


def r(n):
    return '$' + REGS[n]


def mmio_note(addr):
    phys = addr & 0x1fffffff
    for lo, hi, name in MMIO:
        if lo <= phys <= hi:
            return name
    return None


def dis(pc, w):
    """Disassemble one word at `pc`. Returns (text, branch_target_or_None)."""
    op = (w >> 26) & 0x3f
    rs = (w >> 21) & 0x1f
    rt = (w >> 16) & 0x1f
    rd = (w >> 11) & 0x1f
    sh = (w >> 6) & 0x1f
    fn = w & 0x3f
    imm = w & 0xffff
    simm = imm - 0x10000 if imm & 0x8000 else imm
    tgt = (w & 0x3ffffff) << 2

    if w == 0:
        return 'nop', None

    if op == 0:
        name = SPECIAL.get(fn, 'special_%02x' % fn)
        if fn == 0x08:
            return 'jr %s' % r(rs), None
        if fn == 0x09:
            return 'jalr %s,%s' % (r(rd), r(rs)), None
        if fn in (0x00, 0x02, 0x03):
            return '%s %s,%s,%d' % (name, r(rd), r(rt), sh), None
        if fn in (0x10, 0x12):
            return '%s %s' % (name, r(rd)), None
        if fn in (0x11, 0x13):
            return '%s %s' % (name, r(rs)), None
        if fn in (0x18, 0x19, 0x1a, 0x1b):
            return '%s %s,%s' % (name, r(rs), r(rt)), None
        if fn in (0x0c, 0x0d):
            return name, None
        return '%s %s,%s,%s' % (name, r(rd), r(rs), r(rt)), None

    if op == 1:
        dest = (pc + 4 + (simm << 2)) & 0xffffffff
        name = ('bltz' if (rt & 1) == 0 else 'bgez') + ('al' if rt & 0x10 else '')
        return '%s %s,0x%08X' % (name, r(rs), dest), dest

    if op == 2:
        dest = (pc & 0xf0000000) | tgt
        return 'j 0x%08X' % dest, dest
    if op == 3:
        dest = (pc & 0xf0000000) | tgt
        return 'jal 0x%08X' % dest, dest

    if op == 0x10:  # COP0
        if rs == 0:
            return 'mfc0 %s,$%d' % (r(rt), rd), None
        if rs == 4:
            return 'mtc0 %s,$%d' % (r(rt), rd), None
        if fn == 0x10:
            return 'rfe', None
        return 'cop0 0x%07X' % (w & 0x1ffffff), None

    if op == 0x12:  # COP2 / GTE
        if rs == 0:
            return 'mfc2 %s,$%d' % (r(rt), rd), None
        if rs == 2:
            return 'cfc2 %s,$%d' % (r(rt), rd), None
        if rs == 4:
            return 'mtc2 %s,$%d' % (r(rt), rd), None
        if rs == 6:
            return 'ctc2 %s,$%d' % (r(rt), rd), None
        return 'gte 0x%07X' % (w & 0x1ffffff), None

    name = OPS.get(op)
    if name is None:
        return 'op%02x raw=0x%08X' % (op, w), None

    if op == 15:
        return 'lui %s,0x%04X' % (r(rt), imm), None
    if op in (4, 5):
        dest = (pc + 4 + (simm << 2)) & 0xffffffff
        return '%s %s,%s,0x%08X' % (name, r(rs), r(rt), dest), dest
    if op in (6, 7):
        dest = (pc + 4 + (simm << 2)) & 0xffffffff
        return '%s %s,0x%08X' % (name, r(rs), dest), dest
    if op in (8, 9, 10, 11, 12, 13, 14):
        return '%s %s,%s,0x%X' % (name, r(rt), r(rs), imm), None
    return '%s %s,%d(%s)' % (name, r(rt), simm, r(rs)), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ranges', nargs='+', metavar='HEXADDR:COUNT')
    ap.add_argument('--exe', default='disc/SLPS_009.90')
    ap.add_argument('--load', default='0x80093800')
    ap.add_argument('--header', default='0x800',
                    help='PS-X EXE header size skipped before .text')
    args = ap.parse_args()

    load = int(args.load, 16)
    header = int(args.header, 16)
    with open(args.exe, 'rb') as fh:
        image = fh.read()

    # Track lui values per register so a following lw/sw can be resolved to an
    # absolute address -- that is what turns a poll loop into a named device.
    for spec in args.ranges:
        addr_s, _, count_s = spec.partition(':')
        pc = int(addr_s, 16)
        count = int(count_s or '32')
        print('=== 0x%08X .. 0x%08X ===' % (pc, pc + count * 4 - 4))
        lui = {}
        for i in range(count):
            cur = pc + i * 4
            off = (cur & 0x1fffffff) - (load & 0x1fffffff) + header
            if off < 0 or off + 4 > len(image):
                print('0x%08X: <outside image>' % cur)
                continue
            w = struct.unpack('<I', image[off:off + 4])[0]
            text, _ = dis(cur, w)
            note = ''

            op = (w >> 26) & 0x3f
            rs = (w >> 21) & 0x1f
            rt = (w >> 16) & 0x1f
            imm = w & 0xffff
            simm = imm - 0x10000 if imm & 0x8000 else imm

            if op == 15:
                lui[rt] = imm << 16
            elif op in (9, 13) and rs in lui:  # addiu/ori off a known lui
                base = lui[rs] + (simm if op == 9 else imm)
                lui[rt] = base & 0xffffffff
                note = ' ; %s = 0x%08X' % (r(rt), lui[rt])
            elif op >= 32:  # load/store
                if rs in lui:
                    eff = (lui[rs] + simm) & 0xffffffff
                    dev = mmio_note(eff)
                    note = ' ; -> 0x%08X%s' % (eff, ' [%s]' % dev if dev else '')
                # A load's destination now holds memory contents, not a value we
                # can track. Failing to drop it makes later stores through that
                # register report the stale lui base as their target.
                if op < 40:
                    lui.pop(rt, None)
            elif op == 0 or op in (8, 10, 11, 12, 14):
                # Any other ALU write to a register invalidates what we knew.
                dest = ((w >> 11) & 0x1f) if op == 0 else rt
                if not (op == 0 and (w & 0x3f) in (0x08, 0x09, 0x0c, 0x0d)):
                    lui.pop(dest, None)

            print('0x%08X: %08X  %-34s%s' % (cur, w, text, note))
        print()


if __name__ == '__main__':
    sys.exit(main())
