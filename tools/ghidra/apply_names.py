# apply_names.py -- Ghidra script (PyGhidra): push symbols.toml names onto an
# EXISTING program (tools/ghidra_run.py names ... runs it as a -postScript).
#
# Args: getScriptArgs()[0] = JSON {"names": {"0x8017BC2C": "GetGraphType", ...}}
#
# For every address the program's memory contains: make sure it is a function
# (disassemble + createFunction if needed -- a Psy-Q label can sit where the
# auto-analyser saw no call), then name it USER_DEFINED.  A name a person set
# in the GUI (USER_DEFINED and different) is kept and reported, everything
# else (FUN_*, ANALYSIS names such as the BIOS_* thunk names) is replaced.
# Works on the boot program and on the overlay programs' boot_* mapping alike.
# @category PSXRecomp

import json

from ghidra.program.model.symbol import SourceType

args = list(getScriptArgs())
if not args:
    raise SystemExit("usage: apply_names.py <names.json>")
spec = json.load(open(args[0]))
names = spec["names"]
OVERWRITE = bool(spec.get("overwrite"))   # replace hand names too (symbols.toml is authoritative)

prog = currentProgram
fm = prog.getFunctionManager()
mem = prog.getMemory()
af = prog.getAddressFactory().getDefaultAddressSpace()

n_set = n_same = n_kept = n_new = n_out = n_fail = 0
kept = []
for a_s in sorted(names, key=lambda x: -int(x, 0)):
    nm = names[a_s]
    a = af.getAddress(int(a_s, 0) & 0xFFFFFFFF)
    if not mem.contains(a):
        n_out += 1
        continue
    f = fm.getFunctionAt(a)
    if f is None:
        if getInstructionAt(a) is None and not disassemble(a):
            n_fail += 1
            continue
        f = createFunction(a, None)
        if f is None:
            n_fail += 1
            continue
        n_new += 1
    cur = str(f.getName())
    if cur == nm:
        n_same += 1
        continue
    if (not OVERWRITE and f.getSymbol().getSource() == SourceType.USER_DEFINED
            and not cur.startswith(("FUN_", "func_", "BIOS_", "bios_", "boot_"))):
        n_kept += 1
        kept.append("%s %s (symbols.toml says %s)" % (a_s, cur, nm))
        continue
    try:
        f.setName(nm, SourceType.USER_DEFINED)
        n_set += 1
    except Exception as ex:
        n_fail += 1
        print("NAMES %s %s: %s" % (a_s, nm, ex))

print("NAMES %s: %d renamed, %d already right, %d new functions, %d user names kept, %d outside memory, %d failed"
      % (prog.getName(), n_set, n_same, n_new, n_kept, n_out, n_fail))
for k in kept[:40]:
    print("NAMES kept " + k)
