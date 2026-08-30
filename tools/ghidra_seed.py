# ghidra_seed.py — second-pass function seeder for a raw-binary import.
#
# The framework's generated analysis/psxrecomp_import.py calls createFunction()
# directly, which returns None wherever the bytes are still undisassembled. On a
# Raw Binary import that is almost everywhere, so it seeds only the fraction of
# functions Ghidra's own analysis happened to reach (276 of 1026 for this title).
#
# This pass disassembles at each known entry first, then creates the function.
#
# Confidence policy — deliberately asymmetric, to avoid manufacturing code:
#   verified/high/medium : disassemble, then create.
#   low                  : create ONLY if already disassembled. Several 'low'
#                          entries are multi-KB leaf|orphan spans that are data
#                          misread as code; forcing flow through them fills the
#                          listing with garbage instructions.
#   data                 : skipped entirely.
#
# Usage (headless — note analyzeHeadless.bat CANNOT run .py, PyGhidra is required):
#   python -m pyghidra.ghidra_launch --install-dir <ghidra> \
#     ghidra.app.util.headless.AnalyzeHeadless <projdir> <proj> \
#     -process SLPS_009.90 -scriptPath <repo>/tools \
#     -preScript ghidra_seed.py <repo>/analysis/functions.tsv
#
# @category PSXRecomp

from ghidra.program.model.symbol import SourceType

FORCE = ("verified", "high", "medium")

args = getScriptArgs()
if not args:
    raise ValueError("ghidra_seed.py requires the path to analysis/functions.tsv")
tsv = args[0]

af = currentProgram.getAddressFactory().getDefaultAddressSpace()
fm = currentProgram.getFunctionManager()

rows = []
with open(tsv) as fh:
    header = fh.readline().rstrip("\n").split("\t")
    ai, ni, ci = header.index("addr"), header.index("name"), header.index("confidence")
    for line in fh:
        f = line.rstrip("\n").split("\t")
        if len(f) > ci:
            rows.append((int(f[ai], 16), f[ni], f[ci]))

created = existed = disasm = skipped = failed = 0
for value, name, conf in rows:
    if conf == "data":
        skipped += 1
        continue
    ea = af.getAddress(value)
    if fm.getFunctionAt(ea) is not None:
        existed += 1
        continue
    if getInstructionAt(ea) is None:
        if conf not in FORCE:
            skipped += 1
            continue
        disassemble(ea)
        disasm += 1
        if getInstructionAt(ea) is None:
            failed += 1
            continue
    if createFunction(ea, name) is not None:
        created += 1
    else:
        failed += 1

print("ghidra_seed: %d created, %d already present, %d disassembled, "
      "%d skipped (data/low-undisassembled), %d failed, %d total"
      % (created, existed, disasm, skipped, failed, len(rows)))
