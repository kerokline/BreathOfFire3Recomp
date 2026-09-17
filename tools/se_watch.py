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

Enemies: a bank-6 cue names a creature slot (0x600 + 2*slot + tone) in the
area's ENEMYnnn group (SOUND_CUES.md "Enemies"). On every bank-6 cue the
watcher reads the current enemy object (*0x801EB458, its working record at
obj + 0x80: +0x60 species slot, +0x08 level, +0x20 max HP ...) and the
species' own name from the area table the game loaded at 0x800E4000
(slot*0x88 + 0x48, tools/enemy_table.py) -- so the Japanese name needs no
typing. With --label it asks once per species for the English name you
read off the screen and keeps it in names/enemy_gloss.toml (jp -> en),
which tools/enemy_table.py extract merges into names/enemies.toml.

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
GLOSS_TOML = os.path.join(ROOT, "names", "enemy_gloss.toml")
SPECIES_TABLE = 0x800E4000       # the area's 8 x 0x88 species records (tools/enemy_table.py)
CUR_OBJECT = 0x801EB458          # BATTLE.EMI: current actor object (docs/BATTLE_RAM.md)
ENEMY_REC0, ENEMY_STRIDE, ENEMY_MAX = 0x801EB620, 0x118, 8
OBJ_TO_REC = 0x80                # obj+0x84 is record+0x04 (zenny): record = obj + 0x80 (EXP_BOOST.md; slot03: obj 0x801EB5A0 -> record 0)


def read_enemy(read_ram):
    """The current enemy's record fields plus its species name from the area
    table, or None when the current object is not an enemy."""
    import struct
    try:
        obj = struct.unpack("<I", read_ram(CUR_OBJECT, 4))[0]
    except Exception:
        return None
    rec = obj + OBJ_TO_REC
    if not (ENEMY_REC0 <= rec < ENEMY_REC0 + ENEMY_MAX * ENEMY_STRIDE) or (rec - ENEMY_REC0) % ENEMY_STRIDE:
        return None
    try:
        b = read_ram(rec, 0x70)
    except Exception:
        return None
    if len(b) < 0x70:
        return None
    u16 = lambda o: struct.unpack_from("<H", b, o)[0]
    slot = b[0x60]
    jp = ""
    if slot < 8:
        try:
            import jptext
            jp = jptext.decode(read_ram(SPECIES_TABLE + slot * 0x88 + 0x48, 8).rstrip(b"\0"))
        except Exception:
            jp = ""
    return dict(n=(rec - ENEMY_REC0) // ENEMY_STRIDE, rec="0x%08X" % rec, slot=slot, jp=jp,
                level=u16(0x08), max_hp=u16(0x20), hp=u16(0x14), zenny=u16(0x04), exp=u16(0x06),
                atk=u16(0x24), df=u16(0x26), agi=u16(0x28), size=b[0x34])


def load_gloss():
    if not os.path.exists(GLOSS_TOML):
        return {}
    return {g["jp"]: g for g in tomllib.load(open(GLOSS_TOML, "rb")).get("gloss", [])}


def save_gloss(gl):
    rows = ["# names/enemy_gloss.toml -- English names for the enemy species, read off the screen",
            "# (se_watch --label) or typed by hand. Keyed by the Japanese name that names/enemies.toml",
            "# carries (tools/enemy_table.py extract merges these into its `en` column).",
            ""]
    for jp, g in sorted(gl.items()):
        rows.append("[[gloss]]")
        rows.append('jp = "%s"' % jp.replace('"', "'"))
        rows.append('en = "%s"' % g.get("en", "").replace('"', "'"))
        rows.append('evidence = "%s"' % g.get("evidence", "").replace('"', "'"))
        rows.append("")
    with open(GLOSS_TOML, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rows))


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
            "#   label     what was heard, in the player's words ('' until someone listens)",
            "#   auto      the deterministic name: owner file's ability/alias/stem + VAG number",
            "#             (tools/audio_banks.py names); readable code should use label, else auto",
            "#   status    evidence (heard live) | hypothesis | derived (auto name only)",
            "#   evidence  first hearing: se_watch session, frame, cue word, context, vab/prog/tone/vag",
            "#   cues      every 'cue@context' this sample was reached through, e.g. 0x0302@battle",
            "#   centre / shift / size   pitch and length of the sample as the VAB describes it",
            "#   disc      where the same bytes sit on the disc: FILE.EMI#vagN (tools/audio_banks.py join --apply)",
            ""]
    for sid, c in sorted(labels.items(), key=lambda kv: kv[0]):
        rows.append("[[sound]]")
        rows.append('id = "%s"' % sid)
        rows.append('label = "%s"' % c["label"].replace('"', "'"))
        if c.get("auto"):
            rows.append('auto = "%s"' % c["auto"].replace('"', "'"))
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
        if labels.get(row["sound"], {}).get("label"):
            continue
        try:
            ans = input("   [f%d] %s via %s (%s%s) vab%d p%d t%d%s: what was it? " % (
                row["frame"], row["sound"], q["via"], (q["ovl"] + ":") if q["caller"] else "", q["caller"],
                res["vab"], res["prog"], res["tone"],
                (" [Enter = '%s', - = skip]" % q["auto"]) if q.get("auto") else " [Enter = skip]")).strip()
        except EOFError:
            ans = ""
        if q.get("auto") and ans == "":
            ans = q["auto"]
        elif ans in ("", "-"):
            continue
        old = labels.get(row["sound"], {})
        labels[row["sound"]] = {
            "auto": old.get("auto", q.get("auto", "")), "disc": old.get("disc", []),
            "id": row["sound"], "label": ans, "status": "evidence",
            "evidence": "se_watch %s f%d via %s, ra %s %s%s, vab%d prog%d tone%d vag%d spu %s" % (
                session, row["frame"], q["via"], q["ra"], (q["ovl"] + ":") if q["caller"] else "", q["caller"],
                res["vab"], res["prog"], res["tone"], res["vag"], res["spu"]),
            "cues": [q["via"]], "centre": res["centre"], "shift": res["shift"], "size": res["size"]}
        save_labels(labels)
        print("   -> names/se_cues.toml: %s = %s" % (row["sound"], ans), flush=True)


def ask_enemies(pending, gloss, session):
    """Ask the English (on-screen) name of every species heard for the first time."""
    items = sorted(pending.items(), key=lambda kv: kv[1]["frame"])
    pending.clear()
    print("   -- %d enemy species without an English name; Enter = skip --" % len(items), flush=True)
    for jp, q in items:
        en = q["en"]
        try:
            ans = input("   [f%d] %s slot %d %s  L%d HP%d EXP%d: English name? " % (
                q["frame"], q["area"] or "?", en["slot"], jp, en["level"], en["max_hp"], en["exp"])).strip()
        except EOFError:
            ans = ""
        if not ans:
            continue
        gloss[jp] = {"jp": jp, "en": ans,
                     "evidence": "se_watch %s f%d, %s slot %d, L%d HP%d EXP%d" % (
                         session, q["frame"], q["area"] or "?", en["slot"], en["level"], en["max_hp"], en["exp"])}
        save_gloss(gloss)
        print("   -> names/enemy_gloss.toml: %s = %s" % (jp, ans), flush=True)


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
    gloss = load_gloss()
    pending_enemies = {}    # jp name -> first sighting, asked for its English name
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
                    entry = labels.get(sound) if sound else None
                    known = entry if (entry and entry.get("label")) else None
                    auto = entry.get("auto", "") if entry else ""
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
                    en = read_enemy(read_ram) if bank == 6 else None
                    en_known = gloss.get(en["jp"]) if (en and en["jp"]) else None
                    if en:
                        row["enemy"] = en
                        if en["jp"] and not en_known and en["jp"] not in pending_enemies:
                            pending_enemies[en["jp"]] = dict(en=en, frame=int(e["frame"]), area=area)
                            last_cue_t = time.time()
                    if en:
                        desc += "  enemy slot %d %s L%d HP%d/%d%s" % (
                            en["slot"], en["jp"] or "?", en["level"], en["hp"], en["max_hp"],
                            (" = " + en_known["en"]) if en_known else "")
                    print("[f%d] cue %s (%s) %-34s ra=%s %-26s %s" % (
                        row["frame"], row["cue"], mode, desc, e["ra"],
                        ("%s:%s" % (ovl, caller)) if caller else "",
                        ("= " + known["label"]) if known else (("~ " + auto) if auto else ("(unlabelled)" if sound else ""))), flush=True)
                    if entry is not None and via not in entry["cues"]:
                        entry["cues"].append(via)
                        save_labels(labels)
                    if a.label and sound and not known and sound not in pending:
                        pending[sound] = dict(
                            row=row, via=via, ra=e["ra"], ovl=ovl, caller=caller, res=res, auto=auto)
                        last_cue_t = time.time()
                last_frame = fr
            if (pending or pending_enemies) and (a.label_gap <= 0 or time.time() - last_cue_t >= a.label_gap):
                if pending:
                    ask_pending(pending, labels, session)
                if pending_enemies and a.label:
                    ask_enemies(pending_enemies, gloss, session)
            if a.seconds and time.time() - t0 >= a.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if pending or pending_enemies:
            try:
                if pending:
                    ask_pending(pending, labels, session)
                if pending_enemies and a.label:
                    ask_enemies(pending_enemies, gloss, session)
            except (KeyboardInterrupt, EOFError):
                pass
        cd.wtrace_restore(a.port, prev)
    print("se_watch: %d cue(s) recorded" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
