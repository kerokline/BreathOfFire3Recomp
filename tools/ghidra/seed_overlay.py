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
