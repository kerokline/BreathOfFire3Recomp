#!/usr/bin/env python
"""List (and optionally extract) the ISO9660 filesystem of a PSX data track.

The framework's probe_disc.py parses only the root directory, because that is
all it needs to find the boot EXE. Locating game script data needs the whole
tree, plus the ability to pull one file out for inspection.

    python tools/disc_ls.py "isos/Breath of Fire III (Japan).cue"
    python tools/disc_ls.py disc.cue --extract BIN/FILE.BIN --out /tmp/f.bin

Reads MODE2/2352 raw sectors (the Redump layout) and falls back to cooked
2048-byte sectors. Never writes to the dump.
"""
import argparse
import os
import re
import struct
import sys

DST_SEC = 2352          # raw sector
USER = 2048             # user data per sector
USER_OFF = 24           # Mode2 Form1 payload offset within a raw sector
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def resolve_cue(cue_path):
    """Return the path of the first BINARY file referenced by a .cue."""
    base = os.path.dirname(os.path.abspath(cue_path))
    with open(cue_path, "r", errors="replace") as fh:
        text = fh.read()
    m = re.search(r'FILE\s+"([^"]+)"\s+BINARY', text, re.I)
    if not m:
        raise SystemExit("no BINARY FILE line in %s" % cue_path)
    return os.path.join(base, m.group(1))


def make_reader(data):
    """Pick raw-2352 vs cooked-2048 by probing the PVD at LBA 16."""
    off = 16 * DST_SEC
    raw = off + DST_SEC <= len(data) and data[off:off + 12] == SYNC
    if raw:
        def read(lba):
            o = lba * DST_SEC
            if o + DST_SEC > len(data):
                raise KeyError(lba)
            return data[o + USER_OFF:o + USER_OFF + USER]
        return read, "MODE2/2352"

    def read(lba):
        o = lba * USER
        if o + USER > len(data):
            raise KeyError(lba)
        return data[o:o + USER]
    if data[16 * USER + 1:16 * USER + 6] != b"CD001":
        raise SystemExit("not an ISO9660 data track (no CD001 at LBA 16)")
    return read, "cooked/2048"


def read_extent(read, extent, size):
    out = bytearray()
    rem, lba = size, extent
    while rem > 0:
        out += read(lba)[:min(USER, rem)]
        rem -= min(USER, rem)
        lba += 1
    return bytes(out)


def parse_dir(blob):
    """Yield (name, extent, size, is_dir) for one directory extent."""
    i = 0
    while i < len(blob):
        reclen = blob[i]
        if reclen == 0:
            # Records never straddle a logical sector; skip to the next one.
            i = ((i // USER) + 1) * USER
            if i >= len(blob):
                break
            continue
        if i + reclen > len(blob):
            break
        extent = struct.unpack_from("<I", blob, i + 2)[0]
        size = struct.unpack_from("<I", blob, i + 10)[0]
        flags = blob[i + 25]
        namelen = blob[i + 32]
        name = blob[i + 33:i + 33 + namelen]
        if name not in (b"\x00", b"\x01"):
            if b";" in name:
                name = name.split(b";")[0]
            yield (name.decode("ascii", "replace"), extent, size,
                   bool(flags & 0x02))
        i += reclen


def walk(read, extent, size, prefix="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 8:
        return out
    for name, ext, sz, is_dir in parse_dir(read_extent(read, extent, size)):
        path = prefix + "/" + name if prefix else name
        if is_dir:
            out.append((path + "/", ext, sz, True))
            walk(read, ext, sz, path, depth + 1, out)
        else:
            out.append((path, ext, sz, False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--extract", help="path inside the disc to pull out")
    ap.add_argument("--out", help="destination for --extract")
    ap.add_argument("--sort", choices=("name", "size"), default="name")
    args = ap.parse_args()

    binpath = resolve_cue(args.cue) if args.cue.lower().endswith(".cue") else args.cue
    with open(binpath, "rb") as fh:
        data = fh.read()
    read, mode = make_reader(data)

    pvd = read(16)
    if pvd[1:6] != b"CD001":
        raise SystemExit("no CD001 signature in PVD")
    vol = pvd[40:72].decode("ascii", "replace").strip()
    root_extent = struct.unpack_from("<I", pvd, 158)[0]
    root_size = struct.unpack_from("<I", pvd, 166)[0]

    entries = walk(read, root_extent, root_size)
    files = [e for e in entries if not e[3]]

    if args.extract:
        want = args.extract.upper().lstrip("/")
        for path, ext, sz, is_dir in files:
            if path.upper() == want:
                blob = read_extent(read, ext, sz)
                dest = args.out or os.path.basename(path)
                with open(dest, "wb") as fh:
                    fh.write(blob)
                print("extracted %s (%d bytes, LBA %d) -> %s" % (path, sz, ext, dest))
                return 0
        raise SystemExit("not found on disc: %s" % args.extract)

    print("# %s" % binpath)
    print("# sectors=%s  volume=%r  files=%d  dirs=%d"
          % (mode, vol, len(files), len(entries) - len(files)))
    rows = sorted(files, key=(lambda e: -e[2]) if args.sort == "size" else (lambda e: e[0]))
    for path, ext, sz, _ in rows:
        print("%12d  %8d  %s" % (sz, ext, path))
    print("# total bytes in files: %d" % sum(e[2] for e in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
