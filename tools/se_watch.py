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

Appends one JSON row per cue to analysis/se_timeline.jsonl. Every cue is
also RESOLVED to the sound it makes right now (tools/se_resolve.py: cue
entry -> VAB program/tone -> VAG -> the sample bytes in SPU RAM, hashed),
because a cue word is a slot, not a sound: spells, areas and party changes
put other samples behind the same words. With --label the watcher pauses
once the cues pause for --label-gap seconds (stdin must be a terminal),
asks what each *new sound* of the burst was, oldest first, and
upserts the answer into names/se_cues.toml keyed by the sample hash
(status = "evidence", the session, frame, cue and context as the citation);
Enter skips. A sound already labelled is printed with its label, and the
cue word + context it arrived through is added to that sound's `cues` list,
so the file accumulates which slots map to which sounds. The bank 1
and bank 2 tables are swapped for battle (SOUND_CUES.md "Live contents"), so
the label is keyed by cue AND mode. Mode is NOT the resident overlay
(BATTLE.EMI stays in the swap slot after a fight, while the area's own code
is already playing field cues): it is the live bank 1+2 cue table at
0x80148718..0x80148810 hashed against the two tables the savestates hold
(slot00/02 = field, slot03 = battle; docs/SOUND_CUES.md "Live contents"),
which is a useful column even though the sample hash is the identity: 80 of the 144 BMAGIC spell overlays carry a 32/64 KB
sample payload (a type-3 .EMI section) and trigger it as cue 0x100, and
the tables themselves are rewritten as areas and spells load (five hashes
in one 2026-09-17 session), so the same cue word is a different sound per
loaded spell. The label key is therefore (cue, context) where context is
the resident BMAGIC overlay's name (band 0x801EEC00, only when the
occupant is a MAGICnnn overlay -- SHOP.EMI#8 and BATL_END.EMI#0 share the
band and linger there until a spell overwrites them) when one is loaded,
else "field" / "battle" from the table hash, else "tables:<hash8>". Every
new table hash is dumped once to analysis/se_tables/<md5>.bin for decode. Run it beside area_poller.py; both are read-only on the runtime
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
import se_resolve             # noqa: E402

DISC_INDEX = os.path.join(ROOT, "names", "audio_banks.toml")


def disc_index():
    """sample md5 -> ['FILE.EMI#vagN', ...] from names/audio_banks.toml (tools/audio_banks.py index)."""
    if not os.path.exists(DISC_INDEX):
        return {}
    out = {}
    for b in tomllib.load(open(DISC_INDEX, "rb")).get("bank", []):
        base = b["file"].split("/")[-1]
        for v in b.get("vags", []):
            if v.get("md5"):
                out.setdefault(v["md5"], []).append("%s#vag%d" % (base, v["n"]))
    return out

CELL_ID = 0x8018BD7C      # SE_Play: id   (u16), second store (0x8015E93C)
CELL_BANK = 0x8018BD80    # SE_Play: bank (u16), first store (0x8015E91C)
GHIDRA_DIR = os.path.join(ROOT, "analysis", "ghidra")
TABLES_LO, TABLES_HI = 0x80148718, 0x80148810     # bank 1 + bank 2 cue tables (2 x 31 x 4)
TABLES_DIR = os.path.join(ROOT, "analysis", "se_tables")
MAGIC_BAND = 0x801EEC00                            # BMAGIC swap band
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


def tables_now(port):
    """(md5, raw) of the live bank 1+2 cue tables, ('', b'') when unreadable."""
    try:
        import resident
        r = resident.q("read_ram", port, addr="0x%08X" % TABLES_LO, len=TABLES_HI - TABLES_LO)
        raw = bytes.fromhex(r["hex"]) if r.get("hex") else b""
    except Exception:
        return "", b""
    if len(raw) != TABLES_HI - TABLES_LO:
        return "", b""
    return hashlib.md5(raw).hexdigest(), raw


def context_of(bands, tables_md5, raw, seen):
    """The label context: the resident spell overlay's name if one is loaded
    (its sample payload decides what the cue sounds like), else field/battle
    by table hash, else the hash itself. Dumps each new table once."""
    if tables_md5 and tables_md5 not in seen:
        seen.add(tables_md5)
        try:
            os.makedirs(TABLES_DIR, exist_ok=True)
            with open(os.path.join(TABLES_DIR, tables_md5 + ".bin"), "wb") as fh:
                fh.write(raw)
        except OSError:
            pass
    m = bands.get(MAGIC_BAND)
    if m is not None and m.get("id") is not None and not m.get("wrong_band"):
        # the band is shared: SHOP.EMI#8 / BATL_END.EMI#0 also live here and stay
        # until a spell overwrites them, so only a BMAGIC occupant is a spell context
        src = str(m.get("file", "")) + " " + str(m.get("name", ""))
        if "MAGIC" in src.upper():
            return "magic:" + str(m.get("name", "?"))
    if tables_md5 in TABLE_MODES:
        return TABLE_MODES[tables_md5]
    return ("tables:" + tables_md5[:8]) if tables_md5 else "unknown"


# ----------------------------------------------------------------- labels

def load_labels():
    """{sound_id: {id, label, status, evidence, cues:[...]}} from names/se_cues.toml."""
    if not os.path.exists(CUES_TOML):
        return {}
    d = tomllib.load(open(CUES_TOML, "rb"))
    return {c["id"]: dict(c, cues=list(c.get("cues", []))) for c in d.get("sound", [])}


def save_labels(labels):
    rows = ["# names/se_cues.toml -- the sound catalogue, keyed by the SAMPLE, not the cue word.",
            "#   id        md5 (12 hex) of the VAG sample bytes in SPU RAM that the cue resolved to",
            "#             (tools/se_resolve.py); the same word plays other samples after a spell,",
            "#             an area or a party change, so the word is only a slot",
            "#   label     what was heard, in the player's words",
            "#   status    evidence (heard live) | hypothesis",
            "#   evidence  first hearing: se_watch session, frame, cue word, context, vab/prog/tone/vag",
            "#   cues      every 'cue@context' this sample was reached through, e.g. 0x0302@battle",
            "#   centre / shift / size   pitch and length of the sample as the VAB describes it",
            "#   disc      where the same bytes sit on the disc: FILE.EMI#vagN (tools/audio_banks.py join --apply)",
            ""]
    for sid, c in sorted(labels.items(), key=lambda kv: kv[0]):
        rows.append("[[sound]]")
        rows.append('id = "%s"' % sid)
        rows.append('label = "%s"' % c["label"].replace('"', "'"))
        rows.append('status = "%s"' % c.get("status", "evidence"))
        rows.append('evidence = "%s"' % c.get("evidence", "").replace('"', "'"))
        rows.append("cues = [%s]" % ", ".join('"%s"' % x for x in c.get("cues", [])))
        for k in ("centre", "shift", "size"):
            if k in c:
                rows.append("%s = %d" % (k, c[k]))
        if c.get("disc"):
            rows.append("disc = [%s]" % ", ".join('"%s"' % x for x in c["disc"]))
        rows.append("")
    with open(CUES_TOML, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rows))


def ask_pending(pending, labels, session):
    """Ask about every queued unlabelled sound, oldest first, then clear the queue.
    Deferred to a quiet moment so a burst of cues (a spell: cast voice, spell
    sample, effect) does not stall the game mid-burst."""
    items = sorted(pending.values(), key=lambda q: q["row"]["frame"])
    pending.clear()
    print("   -- %d new sound(s); Enter = skip --" % len(items), flush=True)
    for q in items:
        row, res = q["row"], q["res"]
        if row["sound"] in labels:
            continue
        try:
            ans = input("   [f%d] %s via %s (%s%s) vab%d p%d t%d: what was it? " % (
                row["frame"], row["sound"], q["via"], (q["ovl"] + ":") if q["caller"] else "", q["caller"],
                res["vab"], res["prog"], res["tone"])).strip()
        except EOFError:
            ans = ""
        if not ans:
            continue
        labels[row["sound"]] = {
            "id": row["sound"], "label": ans, "status": "evidence",
            "evidence": "se_watch %s f%d via %s, ra %s %s%s, vab%d prog%d tone%d vag%d spu %s" % (
                session, row["frame"], q["via"], q["ra"], (q["ovl"] + ":") if q["caller"] else "", q["caller"],
                res["vab"], res["prog"], res["tone"], res["vag"], res["spu"]),
            "cues": [q["via"]], "centre": res["centre"], "shift": res["shift"], "size": res["size"]}
        save_labels(labels)
        print("   -> names/se_cues.toml: %s = %s" % (row["sound"], ans), flush=True)


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
    ap.add_argument("--label", action="store_true", help="ask what each new sound was, once the cues pause")
    ap.add_argument("--label-gap", type=float, default=2.5,
                    help="seconds of silence before the queued questions are asked (0 = ask at once)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.label and not sys.stdin.isatty():
        raise SystemExit("--label needs a terminal on stdin")
    namer = Namer()
    labels = load_labels()
    read_ram, read_spu = se_resolve.live_readers(a.port)
    disc = disc_index()
    session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prev, armed = cd.wtrace_arm_ranges(a.port, [(CELL_ID, CELL_BANK + 4)])
    print("se_watch: armed 0x%08X-0x%08X (%s), session %s -> %s, %d label(s) known" % (
        CELL_ID, CELL_BANK + 4, armed, session, a.out, len(labels)), flush=True)
    t0 = time.time()
    last_frame = cd.cur_frame(a.port)
    n = 0
    seen_tables = set()
    pending = {}        # sound id -> first hearing, asked about once the cues pause
    last_cue_t = 0.0
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
                tables_md5, raw = tables_now(a.port) if rows else ("", b"")
                mode = context_of(bands, tables_md5, raw, seen_tables) if rows else "unknown"
                area = bands.get(0x801F2C00, {}).get("name", "")
                for bank, cue_id, e_id, e_bank in pair_rows(rows):
                    e = e_id or e_bank
                    cue = (bank << 8) | cue_id if bank >= 0 and cue_id >= 0 else -1
                    ra = int(e["ra"], 16)
                    caller, ovl = namer.name(ra, bands)
                    res, why = None, ""
                    if cue >= 0:
                        try:
                            res = se_resolve.resolve(read_ram, read_spu, cue)
                        except se_resolve.Unresolved as ex:
                            why = str(ex)
                        except Exception as ex:      # debug server hiccup: keep the row, lose the sound
                            why = "resolve failed: %s" % ex
                    sound = res["sound"] if res else None
                    known = labels.get(sound) if sound else None
                    via = "%s@%s" % ("0x%04X" % cue, mode)
                    row = {"session": session, "frame": int(e["frame"]),
                           "t": dt.datetime.now().isoformat(timespec="seconds"),
                           "cue": "0x%04X" % cue if cue >= 0 else "?", "bank": bank,
                           "id": cue_id, "mode": mode, "tables_md5": tables_md5, "area": area,
                           "sound": sound, "resolve": res if res else why,
                           "store_pc_bank": e_bank["pc"] if e_bank else None,
                           "store_pc_id": e_id["pc"] if e_id else None,
                           "ra": e["ra"], "caller_nearest": caller, "caller_overlay": ovl,
                           "a": [e.get(k) for k in ("a0", "a1", "a2", "a3")],
                           "s": [e.get(k) for k in ("s0", "s1", "s2", "s3", "s4", "s5")],
                           "label": known["label"] if known else ""}
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    n += 1
                    where = disc.get(sound, []) if sound else []
                    on_disc = (where[0] + (" +%d" % (len(where) - 1) if len(where) > 1 else "")) if where else ""
                    desc = ("snd %s vab%d p%d t%d c%d %s" % (sound, res["vab"], res["prog"], res["tone"], res["centre"], on_disc)
                            if res else ("(%s)" % why if why else "(half a call: ring gap)"))
                    if res:
                        row["disc"] = where[:12]
                    print("[f%d] cue %s (%s) %-34s ra=%s %-26s %s" % (
                        row["frame"], row["cue"], mode, desc, e["ra"],
                        ("%s:%s" % (ovl, caller)) if caller else "",
                        ("= " + known["label"]) if known else ("(unlabelled)" if sound else "")), flush=True)
                    if known and via not in known["cues"]:
                        known["cues"].append(via)
                        save_labels(labels)
                    if a.label and sound and not known and sound not in pending:
                        pending[sound] = dict(
                            row=row, via=via, ra=e["ra"], ovl=ovl, caller=caller, res=res)
                        last_cue_t = time.time()
                last_frame = fr
            if pending and (a.label_gap <= 0 or time.time() - last_cue_t >= a.label_gap):
                ask_pending(pending, labels, session)
            if a.seconds and time.time() - t0 >= a.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if pending:
            try:
                ask_pending(pending, labels, session)
            except (KeyboardInterrupt, EOFError):
                pass
        cd.wtrace_restore(a.port, prev)
    print("se_watch: %d cue(s) recorded" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
