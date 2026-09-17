#!/usr/bin/env python
"""Sound-cue timeline: every SE_Play call, live, with its cue and caller.

`SE_Play(cue)` (0x8015E908, docs/SOUND_CUES.md) stores the cue's bank at
0x8018BD80 (sh at 0x8015E91C) and then its id at 0x8018BD7C (sh at
0x8015E93C) before it does anything else, and nothing else writes either
cell, so a write trace on those two halfwords is a function-entry hook with
no framework change and no plugin: each row carries the cue word, the store
PC, the caller's return address (a0..a3 / s0..s3 at the store) and the
frame. The two stores of one call are consecutive trace entries (only these
cells are armed), which is how they are paired -- NOT by decompiler order,
which had them backwards on 2026-09-17 and mislabelled the first session.
The caller resolves through symbols.toml, then names/functions.toml for
the overlays actually resident (tools/resident.py -- a swap-slot ra must
not get a BATTLE.EMI name while START.EMI is loaded), then the Ghidra
export's FUN_* boundaries for that overlay as a last resort.

    python tools/se_watch.py --port 4370                    # during play, Ctrl-C to stop
    python tools/se_watch.py --port 4370 --label            # ...and ask what you heard
    python tools/scene.py run --slot 2 -- python tools/se_watch.py --port {port} --seconds 30 --press circle

Appends one JSON row per cue to analysis/se_timeline.jsonl. With --label the
watcher pauses after each *new* cue (stdin must be a terminal), asks what the
sound was, and upserts the answer into names/se_cues.toml (status =
"evidence", the session and frame as the citation); Enter skips, and a cue
that already has a label is printed with it and not asked again. The bank 1
and bank 2 tables are swapped for battle (SOUND_CUES.md "Live contents"), so
the label is keyed by cue AND mode. Mode is NOT the resident overlay
(BATTLE.EMI stays in the swap slot after a fight, while the area's own code
is already playing field cues): it is the live bank 1+2 cue table at
0x80148718..0x80148810 hashed against the two tables the savestates hold
(slot00/02 = field, slot03 = battle; docs/SOUND_CUES.md "Live contents"),
which is what decides what a cue word sounds like. Anything else is
"unknown" and the row carries the hash so a third table can be added. Run it beside area_poller.py; both are read-only on the runtime
(this one arms write-trace ranges and puts the previous ones back on exit).

Requires a debug-tools build with --debug-port (build-dbg / build-relprof).
"""
import argparse
import datetime as dt
import glob
import hashlib
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

CELL_ID = 0x8018BD7C      # SE_Play: id   (u16), second store (0x8015E93C)
CELL_BANK = 0x8018BD80    # SE_Play: bank (u16), first store (0x8015E91C)
GHIDRA_DIR = os.path.join(ROOT, "analysis", "ghidra")
TABLES_LO, TABLES_HI = 0x80148718, 0x80148810     # bank 1 + bank 2 cue tables (2 x 31 x 4)
TABLE_MODES = {                                    # md5 of that span, from saves/openbios (2026-09-17)
    "79b02fe1aa36a99d5c6e6cd96ae6fe74": "field",   # slot00 title, slot02 AREA014 field
    "229197bba0c628f87fd4e2b7431dc09a": "battle",  # slot03 regular field battle
}


class Namer:
    """ra -> nearest known function start at or below it, restricted to the
    boot EXE plus the overlays resident right now (by md5)."""

    # docs/OVERLAY_EXTRACTION.md ten-band map: each band ends where the next begins
    BAND_END = {0x80093800: 0x800B4004, 0x800C1800: 0x800C3600, 0x80196800: 0x801CE400,
                0x801CE000: 0x801D0C00, 0x801CE400: 0x801D0C00, 0x801D0C00: 0x801EEC00,
                0x801EEC00: 0x801F2C00, 0x801F2C00: 0x801F6C00, 0x801F6C00: 0x80200000}

    def __init__(self):
        self.boot = []
        p = os.path.join(ROOT, "symbols.toml")
        if os.path.exists(p):
            for f in tomllib.load(open(p, "rb")).get("func", []):
                self.boot.append((int(f["pc"]), f["name"]))
        self.boot.sort()
        self.by_md5 = {}            # md5 -> sorted [(pc, name)] from names/functions.toml
        for (md5, pc), e in name_map.load_function_names().items():
            self.by_md5.setdefault(md5, []).append((int(pc), e["name"]))
        for v in self.by_md5.values():
            v.sort()
        self.ghidra = {}            # md5 -> sorted [(pc, FUN_name)] from analysis/ghidra exports
        for meta in glob.glob(os.path.join(GHIDRA_DIR, "*.meta.json")):
            try:
                m = json.load(open(meta, encoding="utf-8"))
                md5 = m.get("source_md5") or m.get("md5")
                prog = os.path.basename(meta)[:-len(".meta.json")]
                ex = json.load(open(os.path.join(GHIDRA_DIR, prog + ".json"), encoding="utf-8"))
                self.ghidra[md5] = sorted((int(f["entry"], 16), f["name"]) for f in ex["functions"])
            except (OSError, ValueError, KeyError):
                continue

    @staticmethod
    def _nearest(pc, starts):
        lo, hi = 0, len(starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if starts[mid][0] <= pc:
                lo = mid + 1
            else:
                hi = mid
        if lo == 0:
            return None
        spc, name = starts[lo - 1]
        # nearest known start at or below ra -- a label, not proof the ra is inside it
        return (spc, name) if pc - spc < 0x4000 else None

    def name(self, ra, resident):
        """resident: {band: {md5, name, ...}} = resident.resident_ids()['bands'].
        Returns (label, overlay_name); label '' when nothing known covers ra."""
        for base, e in resident.items():
            md5 = e.get("md5")
            if not md5 or e.get("wrong_band"):
                continue
            if not (base <= ra < self.BAND_END.get(base, base + 0x4000)):
                continue
            hit = self._nearest(ra, self.by_md5.get(md5, []))
            if hit is None:
                hit = self._nearest(ra, self.ghidra.get(md5, []))
            return (hit[1] if hit else "", e.get("name", ""))
        hit = self._nearest(ra, self.boot)
        return (hit[1] if hit else "", "boot" if hit else "")


def pair_rows(rows):
    """Group the drained trace rows (seq order) into SE_Play calls: a bank
    store followed by the id store with the next seq. Yields
    (bank, id, id_entry, bank_entry); a missing half is -1 / None, never
    guessed from a neighbouring call."""
    pending = None   # bank entry waiting for its id
    for e in rows:
        phys = int(e["addr"], 16) & 0x1FFFFFFF
        seq = int(e["seq"])
        if phys == CELL_BANK & 0x1FFFFFFF:
            if pending is not None:
                yield (int(pending["new"], 16) & 0xF, -1, None, pending)
            pending = e
            continue
        if phys != CELL_ID & 0x1FFFFFFF:
            continue
        cue_id = int(e["new"], 16) & 0xFF
        if pending is not None and int(pending["seq"]) + 1 == seq:
            yield (int(pending["new"], 16) & 0xF, cue_id, e, pending)
        else:
            if pending is not None:
                yield (int(pending["new"], 16) & 0xF, -1, None, pending)
            yield (-1, cue_id, e, None)
        pending = None
    if pending is not None:
        yield (int(pending["new"], 16) & 0xF, -1, None, pending)


def resident_now(port):
    """{band: {...}} from tools/resident.py, {} when the debug server cannot say."""
    try:
        import resident
        return resident.resident_ids(port)["bands"]
    except Exception:
        return {}


def mode_of(port):
    """('field' | 'battle' | 'unknown', md5) from the live bank 1+2 cue tables."""
    try:
        import resident
        r = resident.q("read_ram", port, addr="0x%08X" % TABLES_LO, len=TABLES_HI - TABLES_LO)
        raw = bytes.fromhex(r["hex"]) if r.get("hex") else b""
    except Exception:
        return "unknown", ""
    if len(raw) != TABLES_HI - TABLES_LO:
        return "unknown", ""
    h = hashlib.md5(raw).hexdigest()
    return TABLE_MODES.get(h, "unknown"), h


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
    namer = Namer()
    labels = load_labels()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prev, armed = cd.wtrace_arm_ranges(a.port, [(CELL_ID, CELL_BANK + 4)])
    print("se_watch: armed 0x%08X-0x%08X (%s), session %s -> %s, %d label(s) known" % (
        CELL_ID, CELL_BANK + 4, armed, session, a.out, len(labels)), flush=True)
    t0 = time.time()
    last_frame = cd.cur_frame(a.port)
    n = 0
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
                bands = resident_now(a.port) if rows else {}
                mode, tables_md5 = mode_of(a.port) if rows else ("unknown", "")
                for bank, cue_id, e_id, e_bank in pair_rows(rows):
                    e = e_id or e_bank
                    cue = (bank << 8) | cue_id if bank >= 0 and cue_id >= 0 else -1
                    ra = int(e["ra"], 16)
                    caller, ovl = namer.name(ra, bands)
                    known = labels.get((cue, mode)) or labels.get((cue, "unknown"))
                    row = {"session": session, "frame": int(e["frame"]),
                           "t": dt.datetime.now().isoformat(timespec="seconds"),
                           "cue": "0x%04X" % cue if cue >= 0 else "?", "bank": bank,
                           "id": cue_id, "mode": mode, "tables_md5": tables_md5,
                           "store_pc_bank": e_bank["pc"] if e_bank else None,
                           "store_pc_id": e_id["pc"] if e_id else None,
                           "ra": e["ra"], "caller_nearest": caller, "caller_overlay": ovl,
                           "a": [e.get(k) for k in ("a0", "a1", "a2", "a3")],
                           "s": [e.get(k) for k in ("s0", "s1", "s2", "s3", "s4", "s5")],
                           "label": known["label"] if known else ""}
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    n += 1
                    print("[f%d] cue %s (%s) ra=%s %-30s %s" % (
                        row["frame"], row["cue"], mode, e["ra"],
                        ("%s:%s" % (ovl, caller)) if caller else "",
                        ("= " + known["label"]) if known else
                        ("(unlabelled)" if cue >= 0 else "(half a call: ring gap)")), flush=True)
                    if a.label and not known and cue >= 0:
                        try:
                            ans = input("   what was that sound? (Enter = skip) ").strip()
                        except EOFError:
                            ans = ""
                        if ans:
                            labels[(cue, mode)] = {
                                "cue": cue, "mode": mode, "label": ans, "status": "evidence",
                                "evidence": "se_watch %s f%d, ra %s %s%s" % (
                                    session, row["frame"], e["ra"], (ovl + ":") if caller else "", caller)}
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
