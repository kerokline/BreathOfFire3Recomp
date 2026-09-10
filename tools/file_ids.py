#!/usr/bin/env python
"""The game's disc-file id space.

The boot EXE's loader (`0x801629CC(file_id)`, docs/OVERLAY_HEADERS.md "The
loader") resolves its argument through a u32 LBA table at `0x80182DBC`, one
entry per file on the disc in directory-walk order. So a file id is an index
into that table, and every `jal 0x801629CC` with an immediate names a disc file
directly. This tool joins the table to the disc's own directory to produce the
id -> path map, and can resolve ids given on the command line.

    python tools/file_ids.py                       # write analysis/file_ids.json, print a summary
    python tools/file_ids.py 0x125 0x2AB 0x262     # resolve ids
    python tools/file_ids.py --name MAGIC001       # reverse: ids whose path contains NAME
"""
import argparse
import json
import mmap
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc_ls  # noqa: E402

EXE = "disc/SLPS_009.90"
EXE_LOAD = 0x80093800
TABLE = 0x80182DBC
CUE = "isos/Breath of Fire III (Japan).cue"


def lba_table(exe=EXE, limit=2048):
    d = open(exe, "rb").read()
    off = TABLE - (EXE_LOAD - 0x800)
    return [struct.unpack_from("<I", d, off + i * 4)[0] for i in range(limit)]


def disc_files(cue=CUE):
    binpath = disc_ls.resolve_cue(cue)
    fh = open(binpath, "rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    read, _ = disc_ls.make_reader(mm)
    pvd = read(16)
    tree = disc_ls.walk(read, struct.unpack_from("<I", pvd, 158)[0],
                        struct.unpack_from("<I", pvd, 166)[0])
    return {e: (p, sz) for p, e, sz, d in tree if not d}


def build(cue=CUE, exe=EXE):
    by_lba = disc_files(cue)
    vals = lba_table(exe)
    out = []
    for i, v in enumerate(vals):
        if v not in by_lba:
            break
        p, sz = by_lba[v]
        out.append({"id": "0x%03X" % i, "path": p, "lba": v, "size": sz})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ids", nargs="*", help="file ids to resolve (hex or decimal)")
    ap.add_argument("--name", help="reverse lookup: substring of the path")
    ap.add_argument("--cue", default=CUE)
    ap.add_argument("--out", default="analysis/file_ids.json")
    a = ap.parse_args()
    rows = build(a.cue)
    if a.ids or a.name:
        by_id = {int(r["id"], 16): r for r in rows}
        for s in a.ids:
            i = int(s, 0)
            r = by_id.get(i)
            print("%s  %s" % (s, ("%s  (lba %d, %d bytes)" % (r["path"], r["lba"], r["size"])) if r else "NOT A FILE ID"))
        if a.name:
            for r in rows:
                if a.name.upper() in r["path"].upper():
                    print("%s  %s" % (r["id"], r["path"]))
        return 0
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    n_disc = len(disc_files(a.cue))
    print("file ids: %d table entries resolve to disc files (disc has %d files) -> %s"
          % (len(rows), n_disc, a.out))
    print("first: %s %s" % (rows[0]["id"], rows[0]["path"]))
    print("last : %s %s" % (rows[-1]["id"], rows[-1]["path"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
