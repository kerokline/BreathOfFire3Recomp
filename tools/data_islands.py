#!/usr/bin/env python
"""Explain the compile's "data walked as code" rejections: what IS at the address.

Why this exists: overlay bands are shared address windows. An observed
interpreted PC is demanded for EVERY occupant of its band, and for most of
them it is code. For some it is a table or a string that merely sits at the
same address where a sibling occupant has a function, and the static walk
from that entry hits a non-R3000 opcode inside the data. compile_overlays.py
records those as deterministic rejections in generated/interior_fail_memo.txt
("generated-c-audit: 0 unknown_bad, N unsupported") and never retries them,
which is correct -- but the memo says only that the walk failed, not what the
bytes are. "unsupported" reads like a problem; a printf format string is not.

This tool joins each memo line back to the occupant(s) it can only be about,
classifies the bytes at the entry, and prints the kind with a sample:

  pointer table    most words are 0x8001xxxx..0x801Fxxxx addresses (handler /
                   dispatch tables; targets are labelled boot-EXE / same
                   overlay / other band)
  ascii            a run of printable ASCII (format strings, staff roll,
                   the memory-card file-name template)
  jp text          decodes through tools/text_tables.py's kana/kanji table
  halfword table   mostly small 16-bit values
  word table       mostly small 32-bit values (offsets, sizes, ids)
  zero fill        padding / bss
  mixed            none of the above dominates; look by hand

Join rule: the memo key hash cannot be recomputed here (it covers the
compiler's whole recipe), but a memo line for (band, entry) can only belong to
an occupant whose image spans the entry AND which has no compiled piece at it
in generated/overlays_static.c. N lines for N candidates is the healthy case
(every pieceless occupant failed, because the address is data for all of
them). MORE candidates than lines is not: "no piece starting here" is weaker
than "was rejected", so an occupant covered by a piece that starts earlier
inherits a sibling's failure. Those are broken by walk_outcome() -- a
candidate whose walk reaches a return with nothing refused would have emitted
a piece, so the line is not its. Anything still mismatched is reported.

Read docs/DATA_ISLANDS.md before trusting the "code" row: as first written
this classifier put 29 pairs there and the doc called them the compile-side
worklist; all 29 were zero fill, tables that decode as control flow, or one
misattributed line. Data decodes -- opcode validity alone proves nothing.

Every demand comes from an observed PC, so every memo line is "entered" by
construction; the useful default is the LATEST play session's PCs (the ones
the loop just raised). --session ID picks another, --all shows every memo
line. Known names come from names/data.toml (see docs/DATA_ISLANDS.md).

    python tools/data_islands.py                # latest session's entries
    python tools/data_islands.py --session ID   # one session's entries
    python tools/data_islands.py --all          # every memo line
    python tools/data_islands.py --json-out analysis/data_islands.json

axis_b_loop.sh runs it after phase 5a so the loop's own summary explains the
[audit] failures instead of just counting them.
"""
import argparse
import base64
import collections
import json
import os
import re
import string
import struct
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import text_tables as tt          # noqa: E402
import pc_coverage as cov         # noqa: E402

MEMO = os.path.join(ROOT, "generated", "interior_fail_memo.txt")
STATIC_C = os.path.join(ROOT, "generated", "overlays_static.c")
DATA_TOML = os.path.join(ROOT, "names", "data.toml")
KANJI_TABLE = "D:/BoFIII/bof3_character_table.json"
WINDOW = 128
# The classify window is deliberately short (a table runs into what follows
# it); a walk has to be able to reach a return, which the 128-byte window
# cannot -- the SCENA13 function that motivated the tiebreaker returns at +136.
WALK_WINDOW = 4096
PRINTABLE = set(bytes(string.printable, "ascii")) - set(b"\t\n\r\x0b\x0c")


# ---------------------------------------------------------------- inputs

def load_memo(path=MEMO):
    """[(band_phys, entry_phys, digest, reason)]"""
    out = []
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for ln in fh:
            m = re.match(r"\s*([0-9A-Fa-f]{8})_([0-9A-Fa-f]{8})_([0-9a-f]+)\s*(?:#\s*(.*))?$", ln)
            if m:
                out.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3),
                            (m.group(4) or "").strip()))
    return out


def load_pieces(path=STATIC_C):
    """{(band_phys, image_crc_hex, entry_phys)} for every fragment or whole
    function in the dispatch table. Entry is the piece's own start."""
    pieces = set()
    try:
        fh = open(path, errors="replace")
    except OSError:
        return pieces
    frag = re.compile(r"ov_frag_([0-9A-F]{8})_([0-9A-F]{8})_([0-9A-F]{8})_func_")
    whole = re.compile(r"\bov_([0-9A-F]{8})_([0-9A-F]{8})_[0-9A-F]{8}_func_([0-9A-F]{8})\b")
    with fh:
        for ln in fh:
            for m in frag.finditer(ln):
                pieces.add((int(m.group(1), 16), m.group(2), int(m.group(3), 16) & 0x1FFFFFFF))
            for m in whole.finditer(ln):
                pieces.add((int(m.group(1), 16), m.group(2), int(m.group(3), 16) & 0x1FFFFFFF))
    return pieces


def load_data_names(path=DATA_TOML):
    """{(overlay md5, pc_phys): entry}"""
    if tomllib is None or not os.path.exists(path):
        return {}
    with open(path, "rb") as fh:
        rows = tomllib.load(fh).get("data", [])
    return {(r["overlay"], int(r["pc"]) & 0x1FFFFFFF): r for r in rows}


def session_pcs(path=cov.OBSERVED, session=None):
    """Entered PCs stamped with `session` (default: the newest session id).
    Returns (session, set)."""
    try:
        rows = cov.load_observed(path)
    except OSError:
        return session, set()
    if session is None:
        ids = set()
        for r in rows:
            ids.update(r.get("sessions") or [])
        dated = sorted(i for i in ids if i[:4].isdigit())
        session = dated[-1] if dated else None
    pcs = {int(r["pc"], 16) & 0x1FFFFFFF for r in rows
           if int(r.get("entries", 0)) > 0 and session in (r.get("sessions") or [])}
    return session, pcs


# ---------------------------------------------------------------- classify

def _ascii_runs(d, min_len=6):
    runs, cur = [], bytearray()
    for b in d:
        if b in PRINTABLE:
            cur.append(b)
        else:
            if len(cur) >= min_len:
                runs.append(cur.decode("ascii"))
            cur = bytearray()
    if len(cur) >= min_len:
        runs.append(cur.decode("ascii"))
    return runs


def _cstrings(d, min_len=3):
    """NUL-terminated printable-ASCII strings in the window, in order."""
    out = []
    for chunk in d.split(b"\x00"):
        if len(chunk) >= min_len and all(b in PRINTABLE for b in chunk):
            out.append(chunk.decode("ascii"))
    return out


# Opcodes that open nearly every MIPS function or block: addiu sp, sw/lw,
# lui, jr ra, jal. If the first words decode as these the bytes ARE code and
# the walk failed somewhere downstream -- a different finding from "data".
def _looks_like_code(d):
    """Do the first words decode as R3000 code?

    Two rules, both learned from what the first version of this got wrong.

    Zero words are excluded from the ratio: a nop and zero fill are the same
    bytes, so crediting `w == 0` as a hit made every zero-filled window score
    100 %. 24 of the 29 "code" rows on the 2026-09-07 memo were zero fill or
    pointer words.

    And a FRAME is required -- `addiu sp,sp,-imm` or `jr ra` inside the window.
    Weaker signals do not survive contact with data: a pointer table is a
    column of 0x801Fxxxx words that all decode as `lb`; SHOP 0x801E5710 is
    3-byte records whose first word decodes as a `jal` into RAM; BATE
    0x801D8CD0 is packed halfwords that decode as a column of `beq`. Accepting
    any call or branch as the signal admits all three. A function prologue or
    return does not occur in those tables, and every real entry checked here
    (SCENA13 +0, MAGIC002 +16, COMMU00 +24) has one within a few words.
    """
    words = [struct.unpack_from("<I", d, i)[0] for i in range(0, min(len(d), 32) - 3, 4)]
    nz = [w for w in words if w]
    if len(nz) < 4:                                   # too little to judge
        return False
    # The frame may sit past the ratio window: an entry can land on a short
    # data pad in front of the prologue.
    frame = any(w == 0x03E00008 or (w & 0xFFFF0000) == 0x27BD0000
                for w in (struct.unpack_from("<I", d, i)[0]
                          for i in range(0, len(d) - 3, 4)))
    if not frame:
        return False
    hits = 0
    for w in nz:
        op = w >> 26
        if w == 0x03E00008:                           # jr ra
            hits += 1
        elif (w & 0xFFFF0000) == 0x27BD0000:          # addiu sp,sp,imm
            hits += 2
        elif op in (0x2B, 0x23, 0x0F, 0x03, 0x09, 0x04, 0x05):  # sw lw lui jal addiu beq bne
            hits += 1
    if len(set(w >> 26 for w in nz)) < 2:             # one opcode column = table
        return False
    return hits >= len(nz) * 3 // 4


# R3000A opcodes a linear walk accepts. Deliberately permissive: this is used
# to decide that a walk could NOT have failed, so over-accepting here would
# make that claim unsound, while under-accepting only costs a missed tiebreak.
_OPS_OK = frozenset([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18,
                     32, 33, 34, 35, 36, 37, 38, 40, 41, 42, 43, 46, 50, 58])
_SPEC_OK = frozenset([0, 2, 3, 4, 6, 7, 8, 9, 12, 13, 16, 17, 18, 19, 24, 25, 26,
                      27, 32, 33, 34, 35, 36, 37, 38, 39, 42, 43])


def _decodes(w):
    op = w >> 26
    return (w & 0x3F) in _SPEC_OK if op == 0 else op in _OPS_OK


def walk_outcome(d):
    """("clean"|"refused"|"open", byte offset) for a linear walk from the entry.

    "clean"   reached `jr ra` with every word before it decoding -- a walk that
              gets here emits a piece, so this occupant did NOT produce a memo
              line, whatever the compiler's own unsupported set contains.
    "refused" hit a word that does not decode, before any return.
    "open"    ran out of window without either.

    This is the join tiebreaker (see docs/DATA_ISLANDS.md). It deliberately
    does not try to match the memo's unsupported COUNT: that count comes from
    the compiler's own notion of "unsupported", which is not reproducible here,
    so a count comparison could eliminate the wrong candidate. Reaching a
    return with nothing refused along the way is decidable from the bytes.
    """
    for i in range(0, len(d) - 3, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if not _decodes(w):
            return "refused", i
        if w == 0x03E00008:                           # jr ra
            return "clean", i
    return "open", len(d)


def _clean(s):
    return "".join(ch if (ch.isprintable() and ord(ch) < 0xD800) else "." for ch in s)


def classify(d, load, size, exe_range, spans):
    """(kind, sample) for a byte window starting at the entry."""
    # Tables are judged on the first 64 bytes: a table is usually short and
    # the window runs into whatever follows it.
    t = d[:64]
    words = [struct.unpack_from("<I", t, i)[0] for i in range(0, len(t) - 3, 4)]
    n = max(len(words), 1)
    ptrs = [w for w in words if 0x80010000 <= w < 0x80200000]
    zero = sum(1 for w in words if w == 0)
    small_w = sum(1 for w in words if w < 0x10000 or w >= 0xFFFF0000)
    nz_w = sum(1 for w in words if w != 0 and (w < 0x10000 or w >= 0xFFFF0000))
    # Halves are signed: coordinate / animation tables are full of -8 (0xFFF8).
    halves = [struct.unpack_from("<h", t, i)[0] for i in range(0, len(t) - 1, 2)]
    small_h = sum(1 for h in halves if -0x400 < h < 0x400)
    nz_h = sum(1 for h in halves if h != 0 and -0x400 < h < 0x400)
    runs = _ascii_runs(d, min_len=3)     # "%7d" is a real string
    head = d[:48]
    kana = sum(1 for b in head if b in tt.KANA or b in (0x12, 0x13, 0x15))

    if _looks_like_code(d):
        return "code (walk failed downstream)", d[:16].hex(" ")
    # Strings: a printf pool ("%7d", "*%2d") is a few short runs, a staff roll
    # a few long ones, the save-name template one run behind a pointer.
    if runs and (len(runs) >= 2 or len(runs[0]) >= 8) and sum(map(len, runs)) >= 6:
        return "ascii strings", " | ".join(repr(s) for s in runs[:4])
    if len(ptrs) >= n // 2:
        lo, hi = load & 0x1FFFFFFF, (load & 0x1FFFFFFF) + size
        kinds = collections.Counter()
        for w in ptrs:
            p = w & 0x1FFFFFFF
            if lo <= p < hi:
                kinds["same overlay"] += 1
            elif any(l <= p < h for l, h in spans.values()):
                b = next(b for b, (l, h) in spans.items() if l <= p < h)
                kinds["band 0x%08X" % (b | 0x80000000)] += 1
            elif exe_range[0] <= p < exe_range[1]:
                kinds["boot EXE"] += 1
            else:
                kinds["?"] += 1
        tgt = ", ".join("%d %s" % (v, k) for k, v in kinds.most_common())
        return "pointer table", "%d ptrs (%s); first %s" % (
            len(ptrs), tgt, " ".join("%08X" % w for w in ptrs[:4]))
    if zero >= n * 3 // 4:
        return "zero fill", "%d/%d zero words" % (zero, n)
    if kana >= 18:
        try:
            return "jp text", _clean(tt.decode_script(head))[:48]
        except Exception:
            pass
    # Halfword table: every half small, a fair share of them non-zero, and
    # NOT explained as small words (a word table reads as halves too).
    if small_h >= len(halves) * 3 // 4 and nz_h >= len(halves) // 4 and small_w < n * 3 // 4:
        return "halfword table", " ".join("%04X" % h for h in halves[:12])
    if small_w >= n * 3 // 4 and nz_w >= n // 4:
        return "word table", " ".join("%08X" % w for w in words[:8])
    if small_h >= len(halves) * 3 // 4 and nz_h >= len(halves) // 4:
        return "halfword table", " ".join("%04X" % h for h in halves[:12])
    return "mixed", d[:24].hex(" ")


# ---------------------------------------------------------------- main

def explain(memo, captures, pieces, only=None, names=None, kanji=KANJI_TABLE):
    tt.load_kanji(kanji)
    spans = cov.band_ranges(captures)
    exe_range = cov.exe_text_range()
    names = names or {}
    by_key = collections.defaultdict(list)
    for band, entry, digest, reason in memo:
        by_key[(band, entry)].append((digest, reason))
    rows = []
    for (band, entry), lines in sorted(by_key.items()):
        if only is not None and entry not in only:
            continue
        cands = []
        for c in captures:
            lo = int(c["load_addr"], 16) & 0x1FFFFFFF
            if lo != band or not (lo <= entry < lo + int(c["size"])):
                continue
            crc = c["crc32"][2:].upper()
            if (band, crc, entry) in pieces:
                continue
            cands.append(c)
        # Tiebreaker. "No piece STARTING at this entry" is weaker than "was
        # rejected": an occupant whose coverage there begins earlier, or which
        # was never demanded, also lands in cands and then inherits a sibling's
        # failure. When there are more candidates than memo lines, drop the
        # ones whose walk reaches a return with nothing refused -- those would
        # have emitted a piece, so the line is not theirs. Never empty the set.
        raw = len(cands)
        if raw > len(lines):
            off = entry - band
            kept = [c for c in cands
                    if walk_outcome(base64.b64decode(c["bytes_b64"])[off:off + WALK_WINDOW])[0]
                    != "clean"]
            if kept:
                cands = kept
        for c in cands:
            crc = c["crc32"][2:].upper()
            blob = base64.b64decode(c["bytes_b64"])
            off = entry - band
            d = blob[off:off + WINDOW]
            kind, sample = classify(d, int(c["load_addr"], 16), int(c["size"]),
                                    exe_range, spans)
            outcome, where = walk_outcome(blob[off:off + WALK_WINDOW])
            known = names.get((c["source_md5"], entry))
            rows.append({
                "band": "0x%08X" % (band | 0x80000000),
                "entry": "0x%08X" % (entry | 0x80000000),
                "occupant": c["source_file"].split("/")[-1],
                "source": "%s#%d" % (c["source_file"], c["source_index"]),
                "md5": c["source_md5"], "crc32": c["crc32"],
                "kind": kind, "sample": sample,
                "name": known["name"] if known else "",
                "memo_lines": len(lines),
                "candidates": len(cands),
                "candidates_before_tiebreak": raw,
                "walk": "%s@+%d" % (outcome, where),
                # A refused entry is only a coverage LOSS if the code it points
                # at has no piece of its own. An entry sitting on a short data
                # pad in front of a function (MAGIC002 0x801EEC10, COMMU00
                # 0x801EEC9C) is refused, but the function behind the pad is
                # compiled at its own address and nothing is missing.
                "piece_downstream": next(
                    ("0x%08X" % (a | 0x80000000)
                     for a in range(entry + 4, entry + 68, 4)
                     if (band, crc, a) in pieces), ""),
                "reason": lines[0][1],
            })
    return rows


def print_table(rows):
    if not rows:
        print("data islands: nothing to explain (no memo lines match the filter)")
        return
    print("%-10s %-10s %-13s %-15s %-34s %s" % ("band", "entry", "occupant", "kind", "name", "sample"))
    print("-" * 120)
    mism = 0
    for r in rows:
        flag = ""
        if r["memo_lines"] != r["candidates"]:
            flag = "  [memo %d vs %d candidates]" % (r["memo_lines"], r["candidates"])
            mism += 1
        print("%-10s %-10s %-13s %-15s %-34s %s%s" % (
            r["band"], r["entry"], r["occupant"], r["kind"], _clean(r["name"])[:34],
            _clean(r["sample"])[:70], flag))
    kinds = collections.Counter(r["kind"] for r in rows)
    print("\n%d rejected (entry, occupant) pairs: %s" % (
        len(rows), ", ".join("%d %s" % (v, k) for k, v in kinds.most_common())))
    code = [r for r in rows if r["kind"].startswith("code")]
    gaps = [r for r in code if not r["piece_downstream"]]
    padded = [r for r in code if r["piece_downstream"]]
    if padded:
        # Refused, but nothing is lost: the entry is a data pad and the
        # function behind it is compiled at its own address.
        print("%d code rejection(s) are a data pad in front of a compiled "
              "function, not a gap: %s" % (
                  len(padded), ", ".join("%s@%s (piece at %s)" % (
                      r["occupant"], r["entry"], r["piece_downstream"]) for r in padded[:6])))
    if gaps:
        # The one kind that is NOT harmless: the bytes are code, the walk
        # failed further along, and no piece covers what it points at. If that
        # occupant is ever resident there, that is a coverage loss.
        print("%d of them are CODE whose walk failed downstream with no piece "
              "behind it (a real gap for that occupant if it is resident): %s" % (
                  len(gaps), ", ".join("%s@%s" % (r["occupant"], r["entry"]) for r in gaps[:10])
                  + (" ..." if len(gaps) > 10 else "")))
    if mism:
        print("%d row(s), across %d entry address(es), where memo lines != "
              "candidates even after the walk tiebreak -- check by hand" % (
                  mism, len(set(r["entry"] for r in rows
                                if r["memo_lines"] != r["candidates"]))))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="every memo line, not just the latest session's entries")
    ap.add_argument("--session", help="observed-set session id to filter on "
                                      "(default: the newest)")
    ap.add_argument("--memo", default=MEMO)
    ap.add_argument("--captures", default=cov.CAPTURES)
    ap.add_argument("--observed", default=cov.OBSERVED)
    ap.add_argument("--static-c", default=STATIC_C)
    ap.add_argument("--kanji", default=KANJI_TABLE)
    ap.add_argument("--json-out")
    a = ap.parse_args()
    memo = load_memo(a.memo)
    if not memo:
        print("data islands: no memo at %s (nothing rejected yet, or not compiled)" % a.memo)
        return 0
    captures = cov.load_captures(a.captures)
    pieces = load_pieces(a.static_c)
    only = None
    if not a.all:
        sid, only = session_pcs(a.observed, a.session)
        print("data islands for session %s (%d entered PCs); --all for every memo line"
              % (sid, len(only)))
        print()
    rows = explain(memo, captures, pieces, only=only, names=load_data_names(), kanji=a.kanji)
    print_table(rows)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, ensure_ascii=False)
        print("wrote %s" % a.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
