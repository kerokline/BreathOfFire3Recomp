#!/usr/bin/env python
"""Enumerate LOGO.EXE's runtime function-pointer handlers — the general fix for
the interior-coverage "whack-a-mole".

Why this exists: LOGO.EXE dispatches per-frame effect handlers through a table of
function pointers that is ZERO in the disc image and populated at runtime
(`lw v0,0(sN); jalr ra,v0`). The static call-graph walk can never see those
targets — nothing `jal`s them, and the pointers don't exist until the program
installs them. So each rebuild pass makes the last-observed handler native and
the interpreter's entry point just shifts to the next unregistered `jalr` target.

This breaks the iteration by going to the source: it STATICALLY finds the
function-pointer dispatch sites in the compiled LOGO capture (a `lw rD,off(rB)`
feeding a nearby `jalr ra,rD`, with `rB` traced by forward constant-propagation
to a table base in the LOGO range), then reads those tables from a LIVE
LOGO-resident session and collects every non-null pointer that lands in LOGO
code. Those are the handlers. Output is the observed schema, so
`extract_logo_overlay.py --observed` registers them as dispatch entries and
`compile_overlays.py` re-validates each (a bad read is dropped, not fabricated).

    # with a headless build-dbg sitting on the Capcom logo (LOGO resident):
    python tools/harvest_logo_handlers.py --port 4370 \
        --merge analysis/logo_observed.json

Note the subtle rule this encodes: a compiled static ROOT is not automatically
reachable by `jalr` — a function pointer call needs the address registered as a
dispatch entry too, even when its body already compiled. Both kinds of handler
are emitted here.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps

LOGO_LO, LOGO_HI = 0x801CE000, 0x801EB800


def dispatch_tables(data, load):
    """Statically locate function-pointer dispatch tables in the LOGO image.

    Forward constant-propagation over the code: track each register's known
    constant across lui/ori/addiu/addu-move. When a `lw rD,off(rB)` with a known
    rB base feeds a `jalr ra,rD` within a short window, (base+off) is a candidate
    table address. Returns the set of candidate table base addresses.
    """
    n = len(data) // 4
    words = struct.unpack_from("<%dI" % n, data, 0)
    tables = set()
    # map rD -> (table_base, insn_index_of_lw) for a recent pointer load
    pending = {}
    regs = [None] * 32
    for i, w in enumerate(words):
        pc = load + i * 4
        op = w >> 26
        rs = (w >> 21) & 31
        rt = (w >> 16) & 31
        rd = (w >> 11) & 31
        fn = w & 0x3F
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 0x0F:                      # lui rt,imm
            regs[rt] = (imm << 16) & 0xFFFFFFFF
        elif op == 0x09:                    # addiu rt,rs,imm
            regs[rt] = ((regs[rs] + simm) & 0xFFFFFFFF) if regs[rs] is not None else None
        elif op == 0x0D:                    # ori rt,rs,imm
            regs[rt] = (regs[rs] | imm) if regs[rs] is not None else None
        elif op == 0x00 and fn == 0x21:     # addu rd,rs,rt
            if rt == 0:
                regs[rd] = regs[rs]
            elif rs == 0:
                regs[rd] = regs[rt]
            elif regs[rs] is not None and regs[rt] is not None:
                regs[rd] = (regs[rs] + regs[rt]) & 0xFFFFFFFF
            else:
                regs[rd] = None
        elif op == 0x23:                    # lw rt,off(rs)  -> pointer load
            base = regs[rs]
            if base is not None:
                addr = (base + simm) & 0xFFFFFFFF
                if LOGO_LO <= addr < LOGO_HI:
                    pending[rt] = (addr, i)
            regs[rt] = None                 # value now from memory
        elif op == 0x00 and fn == 0x09:     # jalr rd,rs  (rs holds target)
            got = pending.get(rs)
            if got is not None and (i - got[1]) <= 10:
                tables.add(got[0])
            regs[rd if rd else 31] = None
        elif op == 0x00 and fn == 0x08:     # jr rs -> function boundary, reset
            regs = [None] * 32
            pending.clear()
        # jal clobbers ra/caller-saved; keep it simple and just clear ra
        if op == 0x03:
            regs[31] = None
    return sorted(tables)


JR_RA = 0x03E00008


def word_at(data, load, addr):
    o = addr - load
    return struct.unpack_from("<I", data, o)[0] if 0 <= o <= len(data) - 4 else None


def is_callable_boundary(data, load, p):
    """A plausible function entry: a prologue (addiu sp,sp,-N) at/just after p,
    or p is immediately preceded by `jr ra` + delay slot. Mirrors the discovery
    in extract_overlays.prologue_roots / enrich_pcs, and cheaply rejects the
    data-array 'tables' whose values happen to land in the LOGO range (12-byte-
    spaced non-code). compile_overlays still does the authoritative validation."""
    def is_prologue(w):
        return w is not None and (w >> 16) == 0x27BD and (w & 0x8000)
    if any(is_prologue(word_at(data, load, p + k)) for k in (0, 4, 8)):
        return True
    return word_at(data, load, p - 8) == JR_RA


def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=15.0)


def read_table(port, base, entries):
    r = q("read_ram", port, addr="0x%08X" % base, len=entries * 4)
    hexs = r.get("hex")
    if not hexs:
        return []
    b = bytes.fromhex(hexs)
    return [struct.unpack_from("<I", b, k * 4)[0] for k in range(len(b) // 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--capture", default="analysis/logo_capture.json")
    ap.add_argument("--entries", type=int, default=32,
                    help="table slots to read from each discovered base")
    ap.add_argument("--merge",
                    help="union the handlers into this observed-schema file "
                         "(e.g. analysis/logo_observed.json) for "
                         "extract_logo_overlay.py --observed")
    args = ap.parse_args()

    import base64
    cap = json.load(open(args.capture))[0]
    load = int(cap["load_addr"], 16)
    data = base64.b64decode(cap["bytes_b64"])

    tables = dispatch_tables(data, load)
    print("static fn-ptr dispatch tables found: %d" % len(tables))
    for t in tables:
        print("  base 0x%08X" % t)

    # read each table live and collect LOGO-range handler pointers, keeping only
    # those that look like callable function entries (drops data-array false
    # tables). compile_overlays re-validates, so this is a pre-filter, not the
    # final gate.
    handlers = {}
    rejected = 0
    for t in tables:
        for p in read_table(args.port, t, args.entries):
            if LOGO_LO <= p < LOGO_HI:
                if is_callable_boundary(data, load, p):
                    handlers.setdefault(p, t)
                else:
                    rejected += 1
    print("\nlive handlers in LOGO range: %d  (rejected %d non-callable)"
          % (len(handlers), rejected))
    for p in sorted(handlers):
        print("  0x%08X  (from table 0x%08X)" % (p, handlers[p]))

    if args.merge and handlers:
        rows = []
        if os.path.exists(args.merge):
            rows = json.load(open(args.merge))
        have = {(int(r["pc"], 16) & 0x1FFFFFFF) for r in rows}
        added = 0
        for p in sorted(handlers):
            phys = p & 0x1FFFFFFF
            if phys in have:
                continue
            rows.append({"pc": "0x%08X" % phys, "entries": 1, "insns": 1})
            have.add(phys)
            added += 1
        json.dump(rows, open(args.merge, "w"), indent=1)
        print("\nmerged %d new handler(s) into %s (%d total rows)"
              % (added, args.merge, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
