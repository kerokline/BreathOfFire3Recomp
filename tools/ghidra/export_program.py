# export_program.py -- Ghidra script (PyGhidra): dump everything the offline
# tools can use about the current program into <outdir>/<program>.json.
#
# Run by tools/ghidra_run.py (headless, as a -postScript). Args:
#   getScriptArgs()[0]  output directory
#   getScriptArgs()[1]  optional decompile spec: "all" | "named" | "0x...,0x..."
#                       -> <outdir>/<program>_decomp/<addr>_<name>.c
#
# What comes out, per function: entry, size, name + source (DEFAULT means
# Ghidra made the name up), prototype, instruction / load / store counts,
# a cop2 flag (any GTE instruction: cop2, lwc2, swc2), callees (direct),
# jalr count, computed-jump targets (jump tables = interior entry points),
# data references split into in-program and external (outside the overlay's
# own blocks: the boot EXE -- mapped in as `boot_*` blocks but still reported
# as external -- or another band), and
# call sites with a constant a0 (message-index / mode-id anchors).
# Program-wide: globals {addr: reads, writes, functions}, jump_tables,
# call_sites, ext_targets.
#
# Addresses are written as 0x%08X strings. Nothing here modifies the program.
# @category PSXRecomp

import json
import os
import time

from ghidra.program.model.symbol import RefType, SourceType
from ghidra.app.decompiler import DecompInterface

args = list(getScriptArgs())
if not args:
    raise SystemExit("usage: export_program.py <outdir> [all|named|0x..,0x..]")
OUTDIR = args[0]
DECOMP = args[1] if len(args) > 1 else ""

prog = currentProgram
listing = prog.getListing()
fm = prog.getFunctionManager()
rm = prog.getReferenceManager()
mem = prog.getMemory()
name = str(prog.getName())

STORE_MN = {"sw", "sh", "sb", "swl", "swr", "swc2", "_sw", "_sh", "_sb"}
LOAD_MN = {"lw", "lh", "lb", "lhu", "lbu", "lwl", "lwr", "lwc2", "_lw", "_lh", "_lb", "_lhu", "_lbu"}


def hx(a):
    return "0x%08X" % (int(a.getOffset()) & 0xFFFFFFFF)


def hxi(v):
    return "0x%08X" % (int(v) & 0xFFFFFFFF)


# `boot_*` blocks are the boot EXE mapped in by seed_overlay.py so calls into
# it resolve; they are not part of the overlay. Everything the offline tools
# read from this export is scoped to the overlay's own blocks: functions,
# globals, and the in-program / external split (a boot-EXE call stays an
# ext_call, exactly as it was before the boot map existed).
OV_BLOCKS = [b for b in mem.getBlocks() if not str(b.getName()).startswith("boot_")]


def in_program(addr):
    return any(b.contains(addr) for b in OV_BLOCKS)


def raw_word(instr):
    b = instr.getBytes()
    if len(b) < 4:
        return 0
    return (b[0] & 0xFF) | ((b[1] & 0xFF) << 8) | ((b[2] & 0xFF) << 16) | ((b[3] & 0xFF) << 24)


def is_cop2(instr):
    op = (raw_word(instr) >> 26) & 0x3F
    return op in (0x12, 0x32, 0x3A)        # COP2, LWC2, SWC2


def const_reg(instr, regname):
    """If `instr` loads a constant into `regname` (li / addiu $r,$zero,imm /
    ori $r,$zero,imm), return the constant, else None."""
    mn = instr.getMnemonicString().lower().lstrip("_")
    if mn not in ("li", "addiu", "ori", "addi"):
        return None
    try:
        r0 = instr.getRegister(0)
    except Exception:
        return None
    if r0 is None or r0.getName() != regname:
        return None
    n = instr.getNumOperands()
    if mn == "li" and n >= 2:
        sc = instr.getScalar(1)
        return int(sc.getSignedValue()) if sc is not None else None
    if n >= 3:
        r1 = instr.getRegister(1)
        if r1 is None or r1.getName() != "zero":
            return None
        sc = instr.getScalar(2)
        return int(sc.getSignedValue()) if sc is not None else None
    return None


def a0_at_call(instr):
    """Constant a0 at a call site: set in the delay slot or the instruction before."""
    nxt = instr.getNext()
    if nxt is not None:
        v = const_reg(nxt, "a0")
        if v is not None:
            return v
    prv = instr.getPrevious()
    if prv is not None:
        v = const_reg(prv, "a0")
        if v is not None:
            return v
    return None


def is_named(rec):
    """A name a person or a signature gave, not Ghidra's FUN_ default and not
    the ov_entry_ label seed_overlay.py plants on interpreter-harvested
    interior PCs (analysis turns some of those into functions)."""
    if rec["source"] == "DEFAULT":
        return False
    n = rec["name"]
    return not (n.startswith("FUN_") or n.startswith("thunk_FUN_") or n.startswith("ov_entry_")
                or n.startswith("func_"))


blocks = [{"name": str(b.getName()), "start": hx(b.getStart()), "end": hx(b.getEnd()),
           "size": int(b.getSize()), "exec": bool(b.isExecute())} for b in mem.getBlocks()]

globals_ = {}          # addr -> {"r": n, "w": n, "funcs": set()}
ext_targets = {}       # addr -> {"calls": n, "data": n, "funcs": set()}
jump_tables = []
call_sites = []
functions = []

t0 = time.time()
total = fm.getFunctionCount()
done = 0
for f in fm.getFunctions(True):
    done += 1
    if done % 100 == 0:
        monitor.setMessage("export %s: %d/%d" % (name, done, total))
    entry = f.getEntryPoint()
    if not in_program(entry):
        continue
    body = f.getBody()
    sym = f.getSymbol()
    rec = {
        "entry": hx(entry),
        "size": int(body.getNumAddresses()),
        "name": str(f.getName()),
        "source": str(sym.getSource()) if sym is not None else "DEFAULT",
        "proto": str(f.getSignature().getPrototypeString()),
        "params": int(f.getParameterCount()),
        "thunk": bool(f.isThunk()),
        "insns": 0, "loads": 0, "stores": 0, "cop2": False,
        "callees": set(), "jalr": 0, "callers": 0,
        "ext_calls": set(), "ext_data": set(), "jump_targets": set(),
    }
    try:
        rec["callers"] = len(list(f.getCallingFunctions(monitor)))
    except Exception:
        pass
    it = listing.getInstructions(body, True)
    while it.hasNext():
        instr = it.next()
        rec["insns"] += 1
        mn = instr.getMnemonicString().lower()
        if mn in STORE_MN:
            rec["stores"] += 1
        elif mn in LOAD_MN:
            rec["loads"] += 1
        if not rec["cop2"] and is_cop2(instr):
            rec["cop2"] = True
        ft = instr.getFlowType()
        if ft.isCall() and ft.isComputed():
            rec["jalr"] += 1
        for ref in rm.getReferencesFrom(instr.getAddress()):
            rt = ref.getReferenceType()
            to = ref.getToAddress()
            if not to.getAddressSpace().isMemorySpace():
                continue
            inside = in_program(to)
            if rt.isCall():
                if inside:
                    rec["callees"].add(hx(to))
                else:
                    rec["ext_calls"].add(hx(to))
                    e = ext_targets.setdefault(hx(to), {"calls": 0, "data": 0, "funcs": set()})
                    e["calls"] += 1
                    e["funcs"].add(hx(entry))
                a0 = a0_at_call(instr)
                if a0 is not None:
                    call_sites.append({"from": hx(instr.getAddress()), "func": hx(entry),
                                       "to": hx(to), "a0": a0})
            elif rt.isJump() and rt.isComputed():
                rec["jump_targets"].add(hx(to))
            elif rt.isData() or rt.isRead() or rt.isWrite():
                if inside:
                    g = globals_.setdefault(hx(to), {"r": 0, "w": 0, "funcs": set()})
                    if rt.isWrite():
                        g["w"] += 1
                    else:
                        g["r"] += 1
                    g["funcs"].add(hx(entry))
                else:
                    rec["ext_data"].add(hx(to))
                    e = ext_targets.setdefault(hx(to), {"calls": 0, "data": 0, "funcs": set()})
                    e["data"] += 1
                    e["funcs"].add(hx(entry))
        if ft.isJump() and ft.isComputed():
            tg = sorted(hx(r.getToAddress()) for r in rm.getReferencesFrom(instr.getAddress())
                        if r.getReferenceType().isJump())
            if tg:
                jump_tables.append({"at": hx(instr.getAddress()), "func": hx(entry), "targets": tg})
    for k in ("callees", "ext_calls", "ext_data", "jump_targets"):
        rec[k] = sorted(rec[k])
    functions.append(rec)

# Boot-EXE functions still flagged no-return after analysis would truncate
# every caller's decompile at the call; say so instead of hiding it.
noret = [f for f in fm.getFunctions(True) if not in_program(f.getEntryPoint()) and f.hasNoReturn()]
if noret:
    print("EXPORT %s: %d boot-EXE functions flagged no-return: %s" % (
        name, len(noret), ", ".join("%s %s" % (hx(f.getEntryPoint()), f.getName()) for f in noret[:12])))

for g in globals_.values():
    g["funcs"] = sorted(g["funcs"])
for e in ext_targets.values():
    e["funcs"] = sorted(e["funcs"])

doc = {
    "schema": "ghidra-export-v1",
    "program": name,
    "image_base": hx(prog.getImageBase()),
    "language": str(prog.getLanguageID()),
    "blocks": blocks,
    "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "function_count": len(functions),
    "named_count": sum(1 for r in functions if is_named(r)),
    "functions": functions,
    "globals": globals_,
    "ext_targets": ext_targets,
    "jump_tables": jump_tables,
    "call_sites": call_sites,
}

if not os.path.isdir(OUTDIR):
    os.makedirs(OUTDIR)
out_path = os.path.join(OUTDIR, name + ".json")
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=1)
print("EXPORT %s: %d functions (%d named), %d globals, %d ext targets, %d jump tables, %d const-a0 call sites -> %s (%.1fs)"
      % (name, len(functions), doc["named_count"], len(globals_), len(ext_targets),
         len(jump_tables), len(call_sites), out_path, time.time() - t0))

# ---------------------------------------------------------------- decompile

if DECOMP:
    want = None
    if DECOMP == "all":
        want = None
    elif DECOMP == "named":
        want = {r["entry"] for r in functions if is_named(r)}
    else:
        want = {hxi(int(x, 0)) for x in DECOMP.split(",") if x.strip()}
    ddir = os.path.join(OUTDIR, name + "_decomp")
    if not os.path.isdir(ddir):
        os.makedirs(ddir)
    di = DecompInterface()
    di.openProgram(prog)
    n_ok = n_fail = 0
    t1 = time.time()
    for f in fm.getFunctions(True):
        e = hx(f.getEntryPoint())
        if want is not None and e not in want:
            continue
        if want is None and not in_program(f.getEntryPoint()):
            continue
        monitor.setMessage("decompile %s" % e)
        res = di.decompileFunction(f, 60, monitor)
        fn = os.path.join(ddir, "%s_%s.c" % (e[2:], f.getName()))
        if res is not None and res.decompileCompleted():
            with open(fn, "w", encoding="utf-8") as fh:
                fh.write("/* %s %s @ %s */\n" % (name, f.getName(), e))
                fh.write(str(res.getDecompiledFunction().getC()))
            n_ok += 1
        else:
            with open(fn + ".failed", "w", encoding="utf-8") as fh:
                fh.write(str(res.getErrorMessage()) if res is not None else "no result")
            n_fail += 1
    di.dispose()
    print("DECOMP %s: %d ok, %d failed -> %s (%.1fs)" % (name, n_ok, n_fail, ddir, time.time() - t1))
