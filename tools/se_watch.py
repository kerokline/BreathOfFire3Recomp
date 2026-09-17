#!/usr/bin/env python
"""Sound-cue timeline: every SE_Play call, live, with its cue and caller.

`SE_Play(cue)` (0x8015E908, docs/SOUND_CUES.md) stores the cue's id at
0x8018BD7C and its bank at 0x8018BD80 before it does anything else, so a
write trace on those two halfwords is a function-entry hook with no
framework change and no plugin: each row carries the cue word, the store PC,
the caller's return address (a0..a3 / s0..s3 at the store) and the frame.
The caller resolves through symbols.toml and names/functions.toml.

    python tools/se_watch.py --port 4370                    # during play, Ctrl-C to stop
    python tools/se_watch.py --port 4370 --label            # ...and ask what you heard
    python tools/scene.py run --slot 2 -- python tools/se_watch.py --port {port} --seconds 30 --press circle

Appends one JSON row per cue to analysis/se_timeline.jsonl. With --label the
watcher pauses after each *new* cue (stdin must be a terminal), asks what the
sound was, and upserts the answer into names/se_cues.toml (status =
"evidence", the session and frame as the citation); Enter skips, and a cue
that already has a label is printed with it and not asked again. The bank 1
and bank 2 tables are swapped for battle (SOUND_CUES.md "Live contents"), so
the label is keyed by cue AND mode: field vs battle is read off the
resident game-mode overlay when tools/resident.py can name it, else
"unknown". Run it beside area_poller.py; both are read-only on the runtime
(this one arms write-trace ranges and puts the previous ones back on exit).

Requires a debug-tools build with --debug-port (build-dbg / build-relprof).
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "se_timeline.jsonl")
CUES_TOML = os.path.join(ROOT, "names", "se_cues.toml")

import callstack_diff as cd   # noqa: E402
import name_map               # noqa: E402

CELL_ID = 0x8018BD7C      # SE_Play: id   (u16)
CELL_BANK = 0x8018BD80    # SE_Play: bank (u16), stored right after the id


def function_starts():
    """sorted [(pc, name)] over symbols.toml + names/functions.toml."""
    starts = []
    p = os.path.join(ROOT, "symbols.toml")
    if os.path.exists(p):
        for f in tomllib.load(open(p, "rb")).get("func", []):
            starts.append((int(f["pc"]), f["name"]))
    for (_md5, pc), e in name_map.load_function_names().items():
        starts.append((int(pc), e["name"]))
    return sorted(starts)


def name_for(pc, starts):
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid][0] <= pc:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return ""
    spc, name = starts[lo - 1]
    # nearest known start at or below ra -- a label, not proof the ra is inside it
    return name if pc - spc < 0x4000 else ""


def mode_of(port):
    """'battle' | 'field' | 'unknown' from the overlay resident in the game-mode
    swap slot 0x801D0C00 (BATTLE.EMI there = a fight; anything else = field)."""
    try:
        import resident
        r = resident.resident_ids(port)
    except Exception:
        return "unknown"
    e = r["bands"].get(0x801D0C00)
    if e is None or e.get("id") is None:
        return "unknown"
    return "battle" if "BATTLE" in str(e.get("file", "")).upper() else "field"


# ----------------------------------------------------------------- labels

def load_labels():
    if not os.path.exists(CUES_TOML):
        return {}
    d = tomllib.load(open(CUES_TOML, "rb"))
    return {(int(c["cue"]), c.get("mode", "unknown")): c for c in d.get("cue", [])}


def save_labels(labels):
    rows = ["# names/se_cues.toml -- what each SE_Play cue sounds like, heard in play.",
            "#   cue    bank<<8 | id as SE_Play receives it (docs/SOUND_CUES.md)",
            "#   mode   field | battle | unknown -- banks 1 and 2 are swapped for battle,",
            "#          so the same cue word is a different sound in a fight",
            "#   label  what was heard, in the player's words",
            "#   status evidence (heard live) | hypothesis",
            "#   evidence  se_watch session and frame of the hearing, nearest caller",
            ""]
    for (cue, mode), c in sorted(labels.items()):
        rows.append("[[cue]]")
        rows.append("cue = 0x%04X" % cue)
        rows.append('mode = "%s"' % mode)
        rows.append('label = "%s"' % c["label"].replace('"', "'"))
        rows.append('status = "%s"' % c.get("status", "evidence"))
        rows.append('evidence = "%s"' % c.get("evidence", "").replace('"', "'"))
        rows.append("")
    with open(CUES_TOML, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rows))


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--port", type=int, default=int(os.environ.get("PSX_SCENE_PORT", 4370)))
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = until Ctrl-C)")
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--press", action="append", default=[], help="press sequence injected after arming")
    ap.add_argument("--hold", action="append", default=[])
    ap.add_argument("--press-frames", type=int, default=2)
    ap.add_argument("--press-gap", type=int, default=20)
    ap.add_argument("--label", action="store_true", help="pause after each new cue and ask what it was")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.label and not sys.stdin.isatty():
        raise SystemExit("--label needs a terminal on stdin")
    starts = function_starts()
    labels = load_labels()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prev, armed = cd.wtrace_arm_ranges(a.port, [(CELL_ID, CELL_BANK + 4)])
    print("se_watch: armed 0x%08X-0x%08X (%s), session %s -> %s, %d label(s) known" % (
        CELL_ID, CELL_BANK + 4, armed, session, a.out, len(labels)), flush=True)
    t0 = time.time()
    last_frame = cd.cur_frame(a.port)
    n = 0
    pending_id = None   # (frame, id, entry) of the id store waiting for its bank store
    try:
        if a.press or a.hold:
            cd.press_buttons(a.port, a.press, a.press_frames, a.press_gap, hold=a.hold or None)
        while True:
            time.sleep(a.interval)
            fr = cd.cur_frame(a.port)
            if fr > last_frame:
                rows, trunc = cd.drain_writes(a.port, last_frame + 1, fr)
                if trunc:
                    print("se_watch: write ring truncated in frames %d-%d, cues may be missing" % (
                        last_frame + 1, fr), flush=True)
                for e in rows:
                    phys = int(e["addr"], 16) & 0x1FFFFFFF
                    if phys == CELL_ID & 0x1FFFFFFF:
                        pending_id = (int(e["frame"]), int(e["new"], 16) & 0xFF, e)
                        continue
                    if phys != CELL_BANK & 0x1FFFFFFF:
                        continue
                    bank = int(e["new"], 16) & 0xF
                    if pending_id is None or pending_id[0] != int(e["frame"]):
                        # a bank store without its id store in the same frame: SE_Play always
                        # writes both, so this is a ring gap -- record what we have
                        cue_id = -1
                    else:
                        cue_id = pending_id[1]
                    pending_id = None
                    cue = (bank << 8) | (cue_id & 0xFF) if cue_id >= 0 else -1
                    ra = int(e["ra"], 16)
                    mode = mode_of(a.port)
                    known = labels.get((cue, mode)) or labels.get((cue, "unknown"))
                    row = {"session": session, "frame": int(e["frame"]),
                           "t": dt.datetime.now().isoformat(timespec="seconds"),
                           "cue": "0x%04X" % cue if cue >= 0 else "?", "bank": bank,
                           "id": cue_id, "mode": mode,
                           "store_pc": e["pc"], "ra": e["ra"], "caller_nearest": name_for(ra, starts),
                           "args": e.get("args"), "s": e.get("s"),
                           "label": known["label"] if known else ""}
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    n += 1
                    print("[f%d] cue %s (%s) ra=%s %-28s %s" % (
                        row["frame"], row["cue"], mode, e["ra"], row["caller_nearest"],
                        ("= " + known["label"]) if known else "(unlabelled)"), flush=True)
                    if a.label and not known and cue >= 0:
                        try:
                            ans = input("   what was that sound? (Enter = skip) ").strip()
                        except EOFError:
                            ans = ""
                        if ans:
                            labels[(cue, mode)] = {
                                "cue": cue, "mode": mode, "label": ans, "status": "evidence",
                                "evidence": "se_watch %s f%d, ra %s %s" % (
                                    session, row["frame"], e["ra"], row["caller_nearest"])}
                            save_labels(labels)
                            print("   -> names/se_cues.toml: 0x%04X/%s = %s" % (cue, mode, ans), flush=True)
                last_frame = fr
            if a.seconds and time.time() - t0 >= a.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cd.wtrace_restore(a.port, prev)
    print("se_watch: %d cue(s) recorded" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
