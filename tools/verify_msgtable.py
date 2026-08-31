#!/usr/bin/env python
r"""Verify the BoF3 message-table formula against a LIVE run.

docs/TEXT_ENGINE.md derives, statically:

    W      = *(u32 *)0x80010004          # offset from 0x80010000
    base   = 0x80010000 + W
    string = base + *(u16 *)(base + 2 * index)

This reads the running game over the debug server (build-dbg, --debug-port),
walks the table, and decodes the first N messages with the D:BoFIII table.
If the decoded text matches what is on screen, the formula holds.

    python tools/verify_msgtable.py            # walk and decode
    python tools/verify_msgtable.py -n 40
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playsession import send, need_ok      # noqa: E402

TEXT_BASE = 0x80010000
DECODER_DIR = r"D:\BoFIII"


def load_decoder():
    """Reuse the prior decode work rather than rebuilding the table."""
    if DECODER_DIR not in sys.path:
        sys.path.insert(0, DECODER_DIR)
    import decode_text
    return decode_text.decode


def read_ram(addr, length, port=None):
    r = need_ok(send({"cmd": "read_ram", "addr": "0x%08X" % addr, "len": length},
                     port=port, timeout=60.0), "read_ram")
    hexs = r.get("data") or r.get("hex") or r.get("bytes")
    if hexs is None:
        raise SystemExit("read_ram gave no data field: %s" % json.dumps(r)[:300])
    if isinstance(hexs, list):
        return bytes(hexs)
    return bytes.fromhex(hexs.replace(" ", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--count", type=int, default=24,
                    help="how many message slots to decode")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--window", type=int, default=0x4000,
                    help="bytes of script buffer to pull")
    args = ap.parse_args()

    decode = load_decoder()

    blob = read_ram(TEXT_BASE, args.window, args.port)
    w, = struct.unpack_from("<I", blob, 4)
    print("*(u32 *)0x80010004 = 0x%08X  (W)" % w)

    if w == 0 or w >= args.window:
        raise SystemExit(
            "W = 0x%08X is outside the %d-byte window -- either no script is "
            "loaded (are we on a dialogue box?) or the formula is wrong." %
            (w, args.window))

    base_off = w                       # W is an offset from 0x80010000
    print("table base = 0x%08X  (0x80010000 + W)" % (TEXT_BASE + base_off))

    print("\n%-5s %-8s %-10s  %s" % ("idx", "u16 off", "addr", "text"))
    print("-" * 78)
    for i in range(args.count):
        eo = base_off + 2 * i
        if eo + 2 > len(blob):
            print("index %d: table entry past the window" % i)
            break
        off, = struct.unpack_from("<H", blob, eo)
        so = base_off + off
        if so >= len(blob):
            print("%-5d 0x%04X   %-10s  <past window>" % (i, off, "-"))
            continue
        end = blob.find(b"\x00", so)
        raw = blob[so:end if end != -1 else min(so + 160, len(blob))]
        print("%-5d 0x%04X   0x%08X  %s"
              % (i, off, TEXT_BASE + so, decode(raw)[:90]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
