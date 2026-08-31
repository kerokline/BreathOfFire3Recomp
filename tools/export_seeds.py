#!/usr/bin/env python
"""Merge analyser-discovered functions into seeds/ghidra_funcs.txt.

`seeds/ghidra_funcs.txt` started as 523 first-pass JAL targets scanned from the
boot EXE. `analysis/functions.tsv` (from `psxrecomp-analyze`) knows 1026
functions. The difference is code the recompiler never emitted, which the
runtime then has to interpret.

Confidence policy mirrors tools/ghidra_seed.py, and for the same reason:

    verified / high / medium : seed them.
    low                      : SKIPPED by default. Several 'low' rows are
                               multi-KB `leaf|orphan` spans that are data
                               misread as code; seeding those asks the
                               recompiler to emit garbage.
    data                     : never.

`--include-low` exists for experiments, but a `strict = true` generate is the
gate: if it stops being clean, the added seeds are wrong.

    python tools/export_seeds.py            # dry run, prints what would change
    python tools/export_seeds.py --write
"""
import argparse
import collections

TSV = "analysis/functions.tsv"
SEEDS = "seeds/ghidra_funcs.txt"
GOOD = ("verified", "high", "medium")


def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if not line.strip():
                continue
            rows.append(dict(zip(hdr, line.rstrip("\n").split("\t"))))
    return rows


def read_seeds(path):
    header, addrs = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("0x"):
                addrs.append(int(s, 16))
            elif s.startswith("#") and not addrs:
                header.append(line.rstrip("\n"))
    return header, addrs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--include-low", action="store_true")
    args = ap.parse_args()

    keep = GOOD + (("low",) if args.include_low else ())
    rows = read_tsv(TSV)
    header, existing = read_seeds(SEEDS)
    have = set(existing)

    add, skipped = [], collections.Counter()
    for r in rows:
        a = int(r["addr"], 16)
        if a in have:
            continue
        if r["confidence"] not in keep:
            skipped[r["confidence"]] += 1
            continue
        add.append((a, r["confidence"]))
    add.sort()

    print("existing seeds        : %d" % len(have))
    print("functions.tsv         : %d" % len(rows))
    print("would add             : %d" % len(add))
    for c, n in collections.Counter(c for _, c in add).most_common():
        print("     %-9s %d" % (c, n))
    print("skipped by confidence : %s" % dict(skipped))
    print("resulting seed count  : %d" % (len(have) + len(add)))

    if not args.write:
        print("\ndry run — pass --write to update %s" % SEEDS)
        return 0

    merged = sorted(have | {a for a, _ in add})
    with open(SEEDS, "w", encoding="utf-8") as fh:
        for h in header:
            fh.write(h + "\n")
        fh.write("# Extended %s: +%d analyser functions "
                 "(confidence %s) via tools/export_seeds.py\n"
                 % ("2026-08-30", len(add), "/".join(keep)))
        for a in merged:
            fh.write("0x%08X\n" % a)
    print("\nwrote %s (%d seeds)" % (SEEDS, len(merged)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
