#!/usr/bin/env python
"""Area / overlay residency timeline from a LIVE session -- evidence for names/.

Two ways to gather, one output file (analysis/area_timeline.jsonl, append-only):

  watch    run DURING play. Polls the debug server; every time the resident
           area changes it appends a row and (optionally) takes a screenshot so
           the on-screen location can be read back later and typed into
           names/overlays.toml as the alias. Also drains the overlay native
           ring incrementally (which overlay bodies went native, at which frame).
  harvest  run ONCE at end of session (axis_b_loop.sh phase 2 does this).
           Snapshots the area resident right now + drains the whole native ring
           (16384 most recent activations). It cannot recover areas you walked
           through earlier if the ring has wrapped -- that is what `watch` is for.
  summarize
           offline: per AREA file, when it was seen and which screenshot shows
           it; `--apply` writes that as `evidence` into names/overlays.toml for
           every code overlay of that file (alias/status are left for a human --
           the alias is read off the screenshot, not guessed).

How the resident AREA is identified (no guessing, no band ambiguity): every
AREAnnn.EMI has exactly one section whose destination is 0x80010000 -- the area's
script block (docs/LOCALIZATION.md §4, 200 files, 200 sections). It arrives by
CD-ROM DMA when the area loads. Hashing live RAM at 0x80010000 for each known
section size and matching the md5 against analysis/emi_sections.json names the
file with certainty. Overlay bodies are identified by the runtime's own CRC
(overlay_native_ring -> crc -> analysis/overlay_captures_all.json crc32).

    python tools/area_poller.py watch [--port 4370] [--interval 0.5] [--no-shots]
    python tools/area_poller.py harvest [--port 4370]
    python tools/area_poller.py summarize [--apply]

Requires a debug-tools build with --debug-port (build-dbg / build-relprof).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "analysis")
TIMELINE = os.path.join(AN, "area_timeline.jsonl")
SHOT_DIR = os.path.join(AN, "area_shots")
SCRIPT_DEST = 0x80010000


def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=30.0)


def read_ram(port, addr, n):
    r = q("read_ram", port, addr="0x%08X" % addr, len=n)
    return bytes.fromhex(r["hex"]) if r.get("hex") else b""


# ---------------------------------------------------------------- inventories

def script_sections():
    """size -> [(md5, file, index)] for every 0x80010000 section on the disc."""
    secs = json.load(open(os.path.join(AN, "emi_sections.json"), encoding="utf-8"))["sections"]
    by_size = {}
    for s in secs:
        if s["dest"] == SCRIPT_DEST:
            by_size.setdefault(s["size"], []).append((s["md5"], s["file"], s["index"]))
    return by_size


def crc_index():
    """crc32 (int) -> (source_file, load_addr, source_md5) from the captures."""
    p = os.path.join(AN, "overlay_captures_all.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for c in json.load(open(p, encoding="utf-8")):
        out[int(c["crc32"], 16)] = (c["source_file"], c["load_addr"], c["source_md5"])
    return out


def resident_area(port, by_size):
    """(file, md5, size) of the script block resident at 0x80010000, or None."""
    max_size = max(by_size)
    ram = read_ram(port, SCRIPT_DEST, max_size)
    if len(ram) < max_size:
        return None
    for size in sorted(by_size):
        h = hashlib.md5(ram[:size]).hexdigest()
        for md5, f, i in by_size[size]:
            if md5 == h:
                return {"file": f, "index": i, "md5": md5, "size": size}
    return None


def native_ring(port):
    """Newest-first native CALL ring: {addr, crc, frame, seq, returned}. The
    server nests it: {"ok":true,"ring":{"native_exec":..,"recent":[...]}}.
    It is per dispatch (16384 slots, fills in well under a second when hot), so
    it is a WINDOW of what is native right now, not a session history."""
    r = q("overlay_native_ring", port)
    ring = r.get("ring", r) if isinstance(r, dict) else {}
    return ring.get("recent", []) if isinstance(ring, dict) else []


def frame(port):
    return int(q("frame", port).get("frame", -1))


# ---------------------------------------------------------------- output

def append(rows):
    os.makedirs(AN, exist_ok=True)
    with open(TIMELINE, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def shot(port, area_file, fr):
    os.makedirs(SHOT_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(area_file))[0]
    path = os.path.join(SHOT_DIR, f"{stem}_f{fr}.png")
    try:
        r = ps.send({"cmd": "screenshot_file", "path": path}, port=port, timeout=60.0)
        return r.get("path", path) if r.get("ok", True) else None
    except Exception as e:  # screenshot failure must never stop the timeline
        print(f"  (screenshot failed: {e})", file=sys.stderr)
        return None


def overlay_rows(entries, crcs, session, seen_seq, area_crcs=None, area_file=None):
    """Native-ring entries -> timeline rows. The ring is one entry per native
    CALL, so rows are compressed to one per overlay BODY (crc) per area: the
    first time a body is seen while `area_file` is resident, with the call
    count in the window and the entry addresses seen. `area_crcs` (a dict the
    caller keeps per area) suppresses repeats. Newest-first input."""
    per_crc = {}
    for e in reversed(entries):
        seq = int(e.get("seq", 0))
        if seq <= seen_seq:
            continue
        d = per_crc.setdefault(e["crc"], {"calls": 0, "first_frame": int(e["frame"]),
                                          "entries": set()})
        d["calls"] += 1
        d["entries"].add(e["addr"])
    rows = []
    for crc_s, d in per_crc.items():
        if area_crcs is not None:
            if crc_s in area_crcs:
                area_crcs[crc_s] += d["calls"]
                continue
            area_crcs[crc_s] = d["calls"]
        src = crcs.get(int(crc_s, 16))
        rows.append({"session": session, "event": "overlay", "frame": d["first_frame"],
                     "crc": crc_s, "calls": d["calls"],
                     "entries": sorted(d["entries"])[:32], "n_entries": len(d["entries"]),
                     "area": area_file,
                     "file": src[0] if src else None, "load": src[1] if src else None,
                     "md5": src[2] if src else None})
    return rows


# ---------------------------------------------------------------- commands

def cmd_watch(a):
    by_size = script_sections()
    crcs = crc_index()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"watching port {a.port} every {a.interval}s -> {TIMELINE} (session {session}); Ctrl-C to stop")
    print(f"screenshots {a.shot_delay}s after each area change (the script block lands during the fade)")
    last_area, seen_seq, n_rows = None, 0, 0
    area_crcs, area_file, pending_shot = {}, None, None
    try:
        while True:
            try:
                fr = frame(a.port)
                area = resident_area(a.port, by_size)
                ring = native_ring(a.port)
            except Exception as e:
                print(f"  server unreachable ({e}); retrying", file=sys.stderr)
                time.sleep(2.0)
                continue
            key = area["md5"] if area else None
            rows = []
            if key != last_area:
                area_crcs, area_file = {}, (area["file"] if area else None)
                row = {"session": session, "event": "area", "frame": fr,
                       "t": dt.datetime.now().isoformat(timespec="seconds"),
                       **(area or {"file": None, "md5": None})}
                rows.append(row)
                print(f"[f{fr}] area -> {area_file or '(none / not an AREA script)'}")
                pending_shot = (time.time() + a.shot_delay, key) if (area and not a.no_shots) else None
                last_area = key
            if pending_shot and time.time() >= pending_shot[0]:
                if pending_shot[1] == key:
                    path = shot(a.port, area["file"], fr)
                    rows.append({"session": session, "event": "shot", "frame": fr,
                                 "file": area["file"], "md5": area["md5"], "shot": path})
                    print(f"[f{fr}]   shot {path}")
                pending_shot = None
            rows += overlay_rows(ring, crcs, session, seen_seq, area_crcs, area_file)
            if ring:
                seen_seq = max(seen_seq, max(int(e.get("seq", 0)) for e in ring))
            if rows:
                append(rows)
                n_rows += len(rows)
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print(f"\nstopped: {n_rows} rows appended")
    return 0


def cmd_harvest(a):
    by_size = script_sections()
    crcs = crc_index()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    fr = frame(a.port)
    area = resident_area(a.port, by_size)
    ring = native_ring(a.port)
    rows = overlay_rows(ring, crcs, session, 0, {}, area["file"] if area else None)
    row = {"session": session, "event": "area", "frame": fr, "oneshot": True,
           "t": dt.datetime.now().isoformat(timespec="seconds"),
           **(area or {"file": None, "md5": None})}
    if area and not a.no_shots:
        row["shot"] = shot(a.port, area["file"], fr)
    rows.append(row)
    append(rows)
    known = sum(1 for r in rows if r["event"] == "overlay" and r["file"])
    print(f"harvest: frame {fr}, resident area {area['file'] if area else '(none)'}, "
          f"{len(ring)} native calls in the ring window -> {len(rows) - 1} overlay bodies "
          f"({known} matched to captures) -> {TIMELINE}")
    return 0


def cmd_summarize(a):
    if not os.path.exists(TIMELINE):
        sys.exit(f"no {TIMELINE} yet -- run watch/harvest against a live session")
    areas = {}
    for line in open(TIMELINE, encoding="utf-8"):
        r = json.loads(line)
        ev = r.get("event")
        if ev == "overlay" and r.get("area"):
            d = areas.setdefault(r["area"], {"md5": None, "sightings": [], "shots": [], "bodies": {}})
            k = r.get("file") or r["crc"]
            d["bodies"][k] = d["bodies"].get(k, 0) + int(r.get("calls", 0))
            continue
        if ev not in ("area", "shot") or not r.get("file"):
            continue
        d = areas.setdefault(r["file"], {"md5": r["md5"], "sightings": [], "shots": [], "bodies": {}})
        d["md5"] = d["md5"] or r["md5"]
        if ev == "area":
            d["sightings"].append((r["session"], r["frame"]))
        if r.get("shot") and (ev == "shot" or r.get("oneshot")):
            d["shots"].append(r["shot"])
    print(f"{len(areas)} distinct AREA scripts seen")
    for f, d in sorted(areas.items()):
        print(f"  {f:<32} x{len(d['sightings']):<3} shots {len(d['shots'])}"
              + (f"  e.g. {os.path.basename(d['shots'][0])}" if d["shots"] else ""))
        for body, calls in sorted(d["bodies"].items(), key=lambda kv: -kv[1])[:6]:
            print(f"      native body {body:<34} {calls} calls")
    if not a.apply:
        return 0
    import name_map as nm
    rows = nm._read(nm.OVERLAYS_TOML, "overlay")
    by_src = {}
    for r in rows:
        by_src.setdefault(r["source"].split("#")[0], []).append(r)
    n = 0
    for f, d in areas.items():
        if not d["sightings"]:
            continue
        s0 = d["sightings"][0]
        ev = (f"resident script block (dest 0x80010000, md5 {d['md5'][:12]}...) matched live "
              f"at frame {s0[1]} session {s0[0]}" + (f"; shot {d['shots'][0]}" if d["shots"] else ""))
        for r in by_src.get(f, []):
            if not r.get("evidence"):
                r["evidence"] = ev
                n += 1
    with open(nm.OVERLAYS_TOML, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(nm._emit_table("overlay", rows, nm.OVERLAYS_HEADER))
    print(f"applied evidence to {n} overlay entries (alias/status untouched -- read the shot, set alias, "
          f"then status = \"evidence\")")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("watch"); p.add_argument("--port", type=int, default=4370)
    p.add_argument("--interval", type=float, default=0.5); p.add_argument("--no-shots", action="store_true")
    p.add_argument("--shot-delay", type=float, default=4.0,
                   help="seconds after an area change before the screenshot (default 4)")
    p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("harvest"); p.add_argument("--port", type=int, default=4370)
    p.add_argument("--no-shots", action="store_true"); p.set_defaults(fn=cmd_harvest)
    p = sub.add_parser("summarize"); p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_summarize)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
