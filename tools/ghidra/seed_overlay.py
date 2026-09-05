# seed_overlay.py -- Ghidra script (PyGhidra): seed a freshly imported overlay
# program with the function starts the recompiler already knows, BEFORE
# auto-analysis runs (tools/ghidra_run.py passes it as -preScript).
#
# Args: getScriptArgs()[0] = JSON written by ghidra_run.py import:
#   {"name": ..., "starts": ["0x...", ...], "interior": ["0x...", ...],
#    "label_prefix": "ov"}
#
# starts   = static_discovery_entry_pcs (jal targets + prologues): disassemble
#            at each, then createFunction. On a Raw Binary import nothing is
#            disassembled yet, so createFunction alone returns None almost
#            everywhere (tools/ghidra_seed.py learned this on the boot EXE).
# interior = dispatch_entry_pcs the interpreter harvested (jump-table
#            interiors): disassembled and LABELLED, never made functions --
#            a function created at an interior point splits its owner.
# @category PSXRecomp

import json

from ghidra.program.model.symbol import SourceType
from ghidra.program.model.listing import FlowOverride

# Psy-Q libc/kernel entry points in the boot EXE are three-instruction thunks
# into the BIOS jump tables: `addiu t2,zr,0xA0|0xB0|0xC0 ; jr t2 ; addiu
# t1,zr,N`. Ghidra sees a `jr` to unmapped 0xA0 and marks the thunk
# no-return, which cuts every caller's decompile off at the call (this is
# what hid the whole damage formula after `rand()` on 2026-09-05). The `jr`
# becomes CALL_RETURN and the function is named from the psx-spx tables.
BIOS_NAMES = {
    0xA0: {0x13: "setjmp", 0x14: "longjmp", 0x17: "strcmp", 0x18: "strncmp", 0x19: "strcpy",
           0x1A: "strncpy", 0x1B: "strlen", 0x28: "bzero", 0x2A: "memcpy", 0x2B: "memset",
           0x2C: "memmove", 0x2D: "memcmp", 0x2E: "memchr", 0x2F: "rand", 0x30: "srand",
           0x33: "malloc", 0x34: "free", 0x39: "InitHeap", 0x3F: "printf", 0x44: "FlushCache",
           0x49: "GPU_cw", 0x70: "_bu_init", 0x71: "CdInit", 0x72: "CdRemove"},
    0xB0: {0x00: "alloc_kernel_memory", 0x07: "DeliverEvent", 0x08: "OpenEvent", 0x09: "CloseEvent",
           0x0A: "WaitEvent", 0x0B: "TestEvent", 0x0C: "EnableEvent", 0x0D: "DisableEvent",
           0x0E: "OpenThread", 0x0F: "CloseThread", 0x10: "ChangeThread", 0x12: "InitPad",
           0x13: "StartPad", 0x14: "StopPad", 0x17: "ReturnFromException",
           0x18: "SetDefaultExitFromException", 0x19: "SetCustomExitFromException",
           0x32: "FileOpen", 0x33: "FileSeek", 0x34: "FileRead", 0x35: "FileWrite", 0x36: "FileClose",
           0x3D: "std_out_putchar", 0x42: "firstfile", 0x43: "nextfile", 0x44: "FileRename",
           0x45: "FileDelete", 0x4A: "InitCard", 0x4B: "StartCard", 0x4C: "StopCard",
           0x5B: "ChangeClearPad", 0x5C: "get_card_status", 0x5D: "wait_card_status"},
    0xC0: {0x00: "EnqueueTimerAndVblankIrqs", 0x01: "EnqueueSyscallHandler", 0x02: "SysEnqIntRP",
           0x03: "SysDeqIntRP", 0x07: "InstallExceptionHandlers", 0x08: "SysInitMemory",
           0x0A: "ChangeClearRCnt", 0x12: "InstallDevices", 0x13: "FlushStdInOutPut"},
}


def load_imm(ins, reg):
    """imm if ins is `addiu reg,zero,imm` (Ghidra prints it as the `li reg,imm`
    pseudo-op, so accept both spellings), else None."""
    mn = ins.getMnemonicString().lower().lstrip("_")
    if mn not in ("li", "addiu", "ori"):
        return None
    r0 = ins.getRegister(0)
    if r0 is None or r0.getName() != reg:
        return None
    if mn != "li":
        r1 = ins.getRegister(1)
        if r1 is None or r1.getName() != "zero":
            return None
    sc = ins.getScalar(ins.getNumOperands() - 1)
    return None if sc is None else int(sc.getUnsignedValue())


def bios_thunk(a):
    """(table, index, jr instruction) if the three instructions at a are a
    BIOS thunk, else None."""
    i0 = getInstructionAt(a)
    i1 = i0.getNext() if i0 is not None else None
    i2 = i1.getNext() if i1 is not None else None
    if i2 is None:
        return None
    table = load_imm(i0, "t2")
    idx = load_imm(i2, "t1")
    r = i1.getRegister(0)
    if (table not in (0xA0, 0xB0, 0xC0) or idx is None
            or i1.getMnemonicString().lower().lstrip("_") != "jr" or r is None or r.getName() != "t2"):
        return None
    return table, idx, i1

args = list(getScriptArgs())
if not args:
    raise SystemExit("usage: seed_overlay.py <seed.json>")
with open(args[0], "r", encoding="utf-8") as fh:
    seed = json.load(fh)

prog = currentProgram
fm = prog.getFunctionManager()
st = prog.getSymbolTable()
af = prog.getAddressFactory().getDefaultAddressSpace()
mem = prog.getMemory()


def addr(s):
    return af.getAddress(int(s, 0) & 0xFFFFFFFF)


new_name = seed.get("name")
if new_name and str(prog.getName()) != new_name:
    try:
        prog.setName(new_name)
    except Exception as ex:      # rename is cosmetic; the file name already carries it
        print("SEED rename failed: %s" % ex)

# Boot EXE as memory (seed["boot"], built by ghidra_run.boot_seed): one
# initialised, read+execute block per recompiler-proven code range, from the
# disc EXE's bytes, clipped around this overlay. Calls into the boot EXE then
# land on real code and the decompiler stops treating them as no-return.
# Named entries (symbols.toml) become functions with their names; the other
# entries become functions so the auto-analyser has bodies to follow.
boot = seed.get("boot")
n_bblk = n_bfn = n_bnamed = n_bthunk = 0
if boot:
    # The heuristic no-return discovery would re-flag the BIOS thunks after
    # this script (their `jr t2` leaves mapped memory); the thunks are made
    # returning explicitly below, so the heuristic is switched off.
    try:
        setAnalysisOption(prog, "Non-Returning Functions - Discovered", "false")
    except Exception as ex:
        print("SEED could not disable no-return discovery: %s" % ex)
    from ghidra.program.model.mem import MemoryConflictException
    with open(boot["exe"], "rb") as fh:
        img = fh.read()
    header, text = int(boot["header"]), int(boot["text"], 0)
    for start_s, ln in boot["ranges"]:
        start = int(start_s, 0)
        off = start - text + header
        data = img[off:off + ln]
        if len(data) != ln or not any(data):
            continue                        # outside the image, or zero-fill only
        a = addr(start_s)
        try:
            blk = mem.createInitializedBlock("boot_%08X" % (start & 0xFFFFFFFF), a,
                                             len(data), 0, monitor, False)
            mem.setBytes(a, data)
            blk.setRead(True)
            blk.setWrite(False)
            blk.setExecute(True)
            n_bblk += 1
        except MemoryConflictException as ex:
            print("SEED boot block %s conflicts: %s" % (start_s, ex))
    names = boot.get("names", {})
    for e in sorted(set(boot.get("entries", [])) | set(names), key=lambda x: -int(x, 0)):
        a = addr(e)
        if not mem.contains(a):
            continue
        if getInstructionAt(a) is None and not disassemble(a):
            continue
        f = fm.getFunctionAt(a) or createFunction(a, None)
        if f is None:
            continue
        n_bfn += 1
        th = bios_thunk(a)
        if th is not None:
            table, idx, jr = th
            jr.setFlowOverride(FlowOverride.CALL_RETURN)
            f.setNoReturn(False)
            nm = BIOS_NAMES.get(table, {}).get(idx)
            nm = "BIOS_%s" % nm if nm else "BIOS_%02X_%02X" % (table, idx)
            try:
                f.setName(nm, SourceType.ANALYSIS)
                n_bthunk += 1
            except Exception as ex:
                print("SEED thunk name %s %s: %s" % (e, nm, ex))
        if e in names:
            try:
                f.setName(names[e], SourceType.USER_DEFINED)
                n_bnamed += 1
            except Exception as ex:
                print("SEED boot name %s %s: %s" % (e, names[e], ex))
    print("SEED boot EXE: %d blocks, %d functions (%d named from symbols.toml, %d BIOS thunks made returning)"
          % (n_bblk, n_bfn, n_bnamed, n_bthunk))
    if n_bthunk == 0:
        probe = addr("0x8017ED4C")
        ins = getInstructionAt(probe) if mem.contains(probe) else None
        for _ in range(3):
            if ins is None:
                break
            print("SEED thunk probe %s: %s ops=%d regs=%s scalars=%s" % (
                ins.getAddress(), ins, ins.getNumOperands(),
                [str(ins.getRegister(i)) for i in range(ins.getNumOperands())],
                [str(ins.getScalar(i)) for i in range(ins.getNumOperands())]))
            ins = ins.getNext()

n_dis = n_fn = n_lab = n_skip = n_swallowed = 0
# Pass 1: disassemble every start (ascending). Pass 2: create functions in
# DESCENDING address order -- body creation follows flow and stops at an
# existing function entry, so creating the higher start first keeps a lower
# function from swallowing it. (2026-09-05, SHOP.EMI: 0x801D1E84, a traced
# entry and the shop's zenny writer, ended up +0x3FC inside 0x801D1A88 and
# createFunction on it returned None.)
starts_in = []
for s in seed.get("starts", []):
    a = addr(s)
    if not mem.contains(a):
        n_skip += 1
        continue
    if getInstructionAt(a) is None:
        if disassemble(a):
            n_dis += 1
    starts_in.append(a)
for a in sorted(starts_in, key=lambda x: int(x.getOffset()), reverse=True):
    if fm.getFunctionAt(a) is not None:
        continue
    f = createFunction(a, None)
    if f is not None:
        n_fn += 1
    else:
        n_swallowed += 1
        print("SEED could not create function at %s (inside %s)" % (
            a, fm.getFunctionContaining(a).getEntryPoint() if fm.getFunctionContaining(a) else "nothing"))

def looks_like_prologue(a):
    """`addiu sp, sp, -N` at a: the recompiler's dispatch list mixes real
    function starts (the fn-entry ring stamps them as `func`) with jump-table
    interiors; a stack-frame prologue separates the two well enough. The
    2026-09-04 first import labelled Attack_Action (0x801DFA04) as an
    interior and Ghidra swallowed it into the function before it."""
    ins = getInstructionAt(a)
    if ins is None:
        return False
    mn = ins.getMnemonicString().lower().lstrip("_")
    if mn != "addiu" or ins.getNumOperands() < 3:
        return False
    r0, r1 = ins.getRegister(0), ins.getRegister(1)
    sc = ins.getScalar(2)
    return (r0 is not None and r1 is not None and r0.getName() == "sp" and r1.getName() == "sp"
            and sc is not None and sc.getSignedValue() < 0)


prefix = seed.get("label_prefix", "ov")
n_fn2 = 0
for s in seed.get("interior", []):
    a = addr(s)
    if not mem.contains(a):
        n_skip += 1
        continue
    if getInstructionAt(a) is None:
        if disassemble(a):
            n_dis += 1
    if fm.getFunctionAt(a) is not None:
        continue
    if looks_like_prologue(a):
        f = createFunction(a, None)
        if f is not None:
            n_fn2 += 1
            continue
    try:
        st.createLabel(a, "%s_entry_%08X" % (prefix, int(a.getOffset())), SourceType.USER_DEFINED)
        n_lab += 1
    except Exception:
        pass

print("SEED %s: %d disassembled, %d functions from starts (%d not creatable), %d from dispatch PCs with a prologue, %d interior labels, %d outside memory"
      % (prog.getName(), n_dis, n_fn, n_swallowed, n_fn2, n_lab, n_skip))
