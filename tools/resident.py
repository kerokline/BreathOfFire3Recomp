#!/usr/bin/env python
"""Which overlay is resident in each band, from the header word.

Every compiled .EMI overlay opens with a u32 registry id (docs/OVERLAY_HEADERS.md)
that CD_getsector writes with the section's first sector, so one read per band
base names the occupant without hashing the band. Two facts shape the read:

  * the id lands BEFORE the rest of the section, so `ready` (the loader's
    state byte 0x80146490 == 3, File_LoadDone) says whether the last load has
    finished; a band can carry a valid id while its code is still arriving;
  * a band base is not always an overlay: 0x800C1800 doubles as the memory-card
    staging buffer during a save, LOGO.EXE has no header, and a band the game
    has not used yet holds whatever was there. Every word is validated against
    the 405 known ids; anything else is reported as raw, never trusted.

Also read: the loader's file id cell 0x80146464 (what File_LoadRequest was
last asked for, tools/file_ids.py) and the current area number 0x80143F00.

    python tools/resident.py --port 4390            # one line
    python tools/resident.py --port 4390 --watch    # print on change

Library: resident_ids(port) -> dict, format_resident(r) -> str.
"""
import argparse
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps  # noqa: E402
import name_map  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES = os.path.join(ROOT, "analysis", "overlay_captures_all.json")
FILE_IDS = os.path.join(ROOT, "analysis", "file_ids.json")

LOADER_FILE_ID = 0x80146464
LOADER_STATE = 0x80146490
AREA_NUMBER = 0x80143F00
AREA_FILE_ID_BASE = 0x2AB           # File_LoadRequest(area + 0x2AB) = AREA<area>.EMI

_index = None


def _load_index():
    """Once: band bases from the captures, registry id -> overlay row."""
    global _index
    if _index is not None:
        return _index
    caps = json.load(open(CAPTURES, encoding="utf-8"))
    bands = sorted({int(c["load_addr"], 16) for c in caps if c.get("schema") == "static-emi-v1"})
    by_id = {}
    for c in caps:
        rid = c.get("registry_id")
        if rid:
            by_id[int(rid, 16)] = {"file": c["source_file"], "index": c["source_index"],
                                   "md5": c["source_md5"], "band": int(c["load_addr"], 16),
                                   "size": int(c["size"])}
    names = name_map.load_overlay_names()
    for row in by_id.values():
        n = names.get(row["md5"], {})
        row["name"] = n.get("name") or row["file"].split("/")[-1].split(".")[0]
        row["alias"] = n.get("alias", "")
        row["status"] = n.get("status", "unnamed")
    fids = {}
    if os.path.exists(FILE_IDS):
        fids = {int(r["id"], 16): r["path"] for r in json.load(open(FILE_IDS, encoding="utf-8"))}
    _index = {"bands": bands, "by_id": by_id, "file_ids": fids}
    return _index


def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=30.0)


def read_u32(port, addr):
    r = q("read_ram", port, addr="0x%08X" % addr, len=4)
    return struct.unpack("<I", bytes.fromhex(r["hex"]))[0]


def read_u16(port, addr):
    r = q("read_ram", port, addr="0x%08X" % addr, len=2)
    return struct.unpack("<H", bytes.fromhex(r["hex"]))[0]


def read_u8(port, addr):
    r = q("read_ram", port, addr="0x%08X" % addr, len=1)
    return bytes.fromhex(r["hex"])[0]


def resident_ids(port):
    """{'bands': {base: {...}}, 'file_id', 'file', 'ready', 'area'}.

    A band entry is either a matched overlay (id, name, md5, file, alias) or
    {'raw': word, 'id': None} when the word is not a known registry id."""
    ix = _load_index()
    out = {"bands": {}}
    for base in ix["bands"]:
        w = read_u32(port, base)
        row = ix["by_id"].get(w)
        if row is not None and row["band"] == base:
            out["bands"][base] = {"id": w, "name": row["name"], "md5": row["md5"],
                                  "file": row["file"], "alias": row["alias"]}
        elif row is not None:
            # a known id at the wrong band: stale copy or a shared-address twin
            out["bands"][base] = {"id": w, "name": row["name"], "md5": row["md5"],
                                  "file": row["file"], "alias": row["alias"],
                                  "wrong_band": "0x%08X" % row["band"]}
        else:
            out["bands"][base] = {"id": None, "raw": w}
    fid = read_u32(port, LOADER_FILE_ID)
    out["file_id"] = fid
    out["file"] = ix["file_ids"].get(fid, "")
    out["ready"] = read_u8(port, LOADER_STATE) == 3
    out["area"] = read_u16(port, AREA_NUMBER)
    return out


def resident_key(r):
    """Hashable summary for change detection: the matched ids per band."""
    return tuple((b, e.get("id")) for b, e in sorted(r["bands"].items()))


def resident_md5s(r):
    return sorted(e["md5"] for e in r["bands"].values() if e.get("md5") and not e.get("wrong_band"))


def format_resident(r, short=True):
    parts = []
    for base, e in sorted(r["bands"].items()):
        if e.get("id") is None:
            continue
        tag = "%s(0x%03X)" % (e["name"], e["id"])
        if e.get("wrong_band"):
            tag += "?"
        if not short and e.get("alias"):
            tag += " = " + e["alias"]
        parts.append(tag)
    head = "resident: " + (" | ".join(parts) if parts else "(no known overlay in any band)")
    tail = "  load %s%s  area %d" % (
        os.path.basename(r["file"]) if r["file"] else "0x%03X" % r["file_id"],
        "" if r["ready"] else " (in flight)", r["area"])
    return head + tail


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--port", type=int, default=int(os.environ.get("PSX_SCENE_PORT", 4370)))
    ap.add_argument("--watch", action="store_true", help="poll and print whenever the set changes")
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--long", action="store_true", help="include aliases")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    last = None
    while True:
        r = resident_ids(a.port)
        key = (resident_key(r), r["file_id"], r["ready"], r["area"])
        if key != last:
            fr = q("frame", a.port).get("frame", -1)
            if a.json:
                print(json.dumps({"frame": fr, **{("0x%08X" % b): e for b, e in r["bands"].items()},
                                  "file_id": "0x%03X" % r["file_id"], "file": r["file"],
                                  "ready": r["ready"], "area": r["area"]}))
            else:
                print("[f%s] %s" % (fr, format_resident(r, short=not a.long)), flush=True)
            last = key
        if not a.watch:
            break
        time.sleep(a.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
