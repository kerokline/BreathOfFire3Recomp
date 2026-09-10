#!/usr/bin/env python
"""Harvest observed interpreted entry PCs from a LIVE run.

Why this exists: `psxrecomp-analyze` is deliberately static-only (see
`psxrecomp/docs/FUNCTION_DISCOVERY.md` rule 1 — "no executed-PC feedback"), so
it cannot see that the game jumps into the *middle* of an oversized
low-confidence span, or into an overlay entry only reached through dynamic
dispatch. The recompiler registers the span's start, the game enters at an
interior address, that address has no dispatch entry, and every instruction
from there runs in the dirty-RAM interpreter.

The runtime knows exactly where it entered. `dirty_ram_stats.per_pc` records
each interpreted PC with an `entries` count; a PC with `entries > 0` is an
empirically proven function entry.

Downstream is the OVERLAY lane, not the seed lane. These are overlay addresses
reached by dynamic dispatch; feeding them to `seeds/ghidra_funcs.txt` (the
boot-EXE analyser) is a proven dead end (a byte-identical generate — see
docs/HANDOFF.md "Seeding is a dead end"). The load-bearing output is
`analysis/observed_interp_pcs.json`, which `tools/extract_overlays.py --observed`
reads to attribute entered PCs to overlay bands.

Coverage accumulates across sessions. Each play session enters a DIFFERENT set
of overlay addresses (which .EMI area is resident decides which PCs bucket to a
band), so two sessions are nearly disjoint — measured 2026-08-31, two sessions
shared only 323 of ~17,500 PCs. Overwriting the observed file would therefore
throw away every area you did not revisit this run. So this tool UNIONs into the
existing file, keeping one distinct row per PC (no duplicates), and reports how
many are newly seen. Run it after every session; the set only grows. `area_poller.py watch` also
calls harvest() on a timer (default every 15 min) so a session that dies early
keeps most of its coverage.

    python tools/harvest_interp_pcs.py            # query, report, union-save
    python tools/harvest_interp_pcs.py --port N   # non-default debug port

Then re-run extract_overlays.py --observed, recompile all bands, rebuild,
re-measure (docs/HANDOFF.md, "The next task").
"""
import argparse
import binascii
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playsession import send, need_ok      # noqa: E402
import pc_coverage as cov                  # noqa: E402


def norm_pc(pc_str):
    """Normalize a per_pc physical address to a stable hex key (see the
    HANDOFF trap: harvest writes PHYSICAL PCs, e.g. 0x001D7524)."""
    return "0x%08X" % (int(pc_str, 16) & 0x1FFFFFFF)


def load_existing(path):
    """Existing observed rows keyed by normalized PC. Missing/empty -> {}."""
    if not path or not os.path.exists(path):
        return {}
    try:
        rows = json.load(open(path))
    except (ValueError, OSError):
        return {}
    out = {}
    for r in rows:
        if "pc" in r:
            out[norm_pc(r["pc"])] = r
    return out


SESSION_STATE = "analysis/harvest_session.json"
# Repo root, anchored on this file so build_fingerprint() does not depend on cwd.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Previous pass's per-PC entry counts, per debug port, so a timed re-harvest
# can tell which PCs were entered SINCE the last pass and attribute those to
# the area resident across that interval. In-process only: a one-shot
# end-of-run harvest has no baseline and stamps newly-seen PCs, as before.
_PREV = {}


def build_fingerprint(root=None):
    """A short id for the build a row was observed under.

    "This PC ran interpreted" is a statement ABOUT A BUILD, not about the game:
    compile the band it lives in and the same PC runs native and never appears
    again. So an observed row without a build id is a measurement with its
    units thrown away, and unioning rows from a three-band tree with rows from
    an all-bands tree silently mixes two different experiments.

    The static side has no such problem -- entry PCs come off the disc and no
    rebuild moves them -- which is why only the observed half needs stamping.

    Two things decide whether a given PC can fall to the interpreter: the
    codegen version, and WHICH BANDS were compiled in. Both are read from the
    local tree, so this is honest only when the running exe was built from it;
    `--build` overrides it when that is not true. The runtime exposes no build
    identity over TCP (checked 2026-09-07: no build_info / version /
    codegen_info command), so this is the best available and its limits are
    stated rather than hidden.
    """
    root = root or ROOT
    cg = "unknown"
    p = os.path.join(root, "psxrecomp", "runtime", "include",
                     "overlay_codegen_hash.h")
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("#define PSX_OVERLAY_CODEGEN_HASH"):
                cg = "%08X" % int(line.split()[2].rstrip("u"), 16)
                break
    except OSError:
        pass
    bands = set()
    p = os.path.join(root, "generated", "overlays_static.c")
    try:
        with open(p, "r", errors="replace") as fh:
            for line in fh:
                for m in re.finditer(r"\bov_([0-9A-Fa-f]{8})_", line):
                    bands.add(m.group(1).upper().lstrip("0"))
    except OSError:
        pass
    return "cg:%s;b:%s" % (cg, ",".join(sorted(bands)) if bands else "none")


def resolve_session(port, explicit=None, state_path=SESSION_STATE, quiet=False):
    """The session id to attribute this harvest to.

    A wall-clock timestamp is the WRONG identity: harvesting the same running
    game twice (the loop's end-of-run pass after the poller's timed one) would
    mint two ids over one play session, and since both see the same PCs, every
    PC becomes a doubleton, Q1 collapses to 0, and pc_coverage reports 100 %
    coverage of a set nobody finished exploring. That happened for real on
    2026-09-04 (sessions ...093558 and ...094409, 196 PCs, zero unique to
    either).

    So identity comes from the RUNNING PROCESS instead. The runtime's frame
    counter and interpreted-instruction count both start at 0 and only climb,
    so a reading below the last one means the game restarted -- a genuinely new
    sample. Anything else continues the stored session.

    `explicit` wins outright (area_poller.py passes its own id for every timed
    pass of one watch run).
    """
    if explicit:
        return explicit
    try:
        fr = int(need_ok(send({"cmd": "frame"}, port=port, timeout=30.0),
                         "frame").get("frame", -1))
    except Exception:
        fr = -1
    try:
        with open(state_path, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}

    prev = st.get("session")
    restarted = fr < 0 or fr < int(st.get("frame", -1))
    if prev and not restarted:
        session = prev
        if not quiet:
            print("session     : %s (continuing -- frame %d >= %d, same run)"
                  % (session, fr, int(st.get("frame", -1))))
    else:
        # A bare second-resolution timestamp is not a unique id: two runs
        # started within the same second would collide and silently merge into
        # one sampling unit -- the exact failure this function exists to stop.
        session = "%s-%s" % (dt.datetime.now().strftime("%Y%m%dT%H%M%S"),
                             binascii.hexlify(os.urandom(2)).decode())
        if not quiet and prev:
            print("session     : %s (NEW -- frame %d < %d, the game restarted)"
                  % (session, fr, int(st.get("frame", -1))))
    try:
        os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"session": session, "frame": fr,
                       "t": dt.datetime.now().isoformat(timespec="seconds")}, fh)
        os.replace(tmp, state_path)
    except OSError:
        pass                    # bookkeeping only; never cost a harvest
    return session


def merge_row(old, new, session=None, area=None, build=None, resident=None):
    """Union one PC's observations across sessions. Keep the DISTINCT PC once;
    take the max of the count fields so a hot PC stays visible and a PC is not
    double-counted if the same run is harvested twice.

    `session` and `area` build the incidence record tools/pc_coverage.py needs:
    `sessions` is the set of play sessions this PC was entered in (the sampling
    units Chao2 counts over), `areas` the resident areas it was first seen
    under. Both are sets stored as sorted lists, so the poller's every-15-min
    re-harvest inside one session adds nothing the second time.

    A row that predates this (the accumulated set as of 2026-09-04) simply has
    no `sessions` key; pc_coverage treats it as seen-but-uncountable rather
    than inventing incidence it never measured."""
    if old is None:
        out = dict(new)
    else:
        out = dict(old)
        for k in ("entries", "insns", "entry_hits", "hits"):
            if k in new or k in old:
                out[k] = max(int(new.get(k, 0)), int(old.get(k, 0)))
        # Enrichment (runtime occ_crc / ext_ra, psxrecomp feat/dirty-pc-enrichment):
        # not counts -- keep the newest non-zero observation, so a PC seen this
        # session with a resident occupant does not lose it to an older 0 row.
        for k in ("occ_crc", "ext_ra"):
            v = new.get(k) or old.get(k)
            if v and str(v) != "0x00000000":
                out[k] = v
        # occ_ok travels with occ_crc: take it from whichever row supplied the CRC.
        if new.get("occ_crc") and str(new.get("occ_crc")) != "0x00000000" and "occ_ok" in new:
            out["occ_ok"] = int(new["occ_ok"])
        elif "occ_ok" in old and "occ_ok" not in out:
            out["occ_ok"] = int(old["occ_ok"])
    if session:
        out["sessions"] = sorted(set(out.get("sessions") or []) | {session})
    if area:
        out["areas"] = sorted(set(out.get("areas") or []) | {area})
    if resident:
        # the registry ids resident when this PC was (first / again) entered,
        # from tools/resident.py -- the whole set, not just the AREA, so a PC
        # in a shared band can later be read against the occupant of the day
        out["resident"] = sorted(set(out.get("resident") or []) | set(resident))
    if build:
        # Unlike `area`, the build is constant for a whole session, so every row
        # this pass touches is honestly attributable to it -- no delta needed.
        out["builds"] = sorted(set(out.get("builds") or []) | {build})
    return out


def harvest(port=4370, save_json="analysis/observed_interp_pcs.json",
            no_save=False, min_insns=0, quiet=False, session=None, area=None,
            coverage=True, build=None, resident=None):
    """Query the live runtime and union its per-PC table into save_json.

    Read-only on the runtime side (dirty_ram_stats walks the PC table; nothing
    is reset), so this is safe to call repeatedly during play -- area_poller.py
    watch does exactly that on a timer so a session that dies before its
    end-of-run harvest (2026-09-02: a Windows Terminal crash took a 74-minute
    session) loses at most one interval of coverage.

    The observed file is written atomically (temp file + os.replace) so a kill
    mid-write can never leave a truncated JSON behind.

    `session` identifies the play session for incidence bookkeeping (one
    sampling unit for tools/pc_coverage.py). It defaults to a timestamp, which
    is correct for a one-shot end-of-run harvest but WRONG for the poller's
    timed re-harvest -- area_poller.py watch passes its own session id so all
    of its passes fold into one unit. `area` is the area resident right now;
    it is stamped only on PCs newly seen by THIS pass, since a session-wide
    per_pc snapshot cannot say which area the older ones came from. Across the
    poller's timed passes that constraint lifts for anything that MOVED: a PC
    whose entry count grew since the previous pass was entered in the interval
    just polled, so it is stamped too (see the merge loop).

    Returns a dict: interp, native, aborts, misses, before, after, new,
    entered, newly_seen (list of (pc, entries, insns)), coverage (the
    pc_coverage report, or None).
    """
    session = resolve_session(port, explicit=session, quiet=quiet)
    build = build or build_fingerprint()
    if not quiet:
        print("build       : %s" % build)
    d = need_ok(send({"cmd": "dirty_ram_stats"}, port=port, timeout=120.0),
                "dirty_ram_stats")
    s = need_ok(send({"cmd": "dispatch_stats"}, port=port, timeout=60.0),
                "dispatch_stats")
    interp, native = d["insns_run"], s["static_hits"]
    total = interp + native
    if not quiet:
        print("interpreted : {:>14,}  ({:.1f}%)".format(interp, 100.0 * interp / max(total, 1)))
        print("native      : {:>14,}  ({:.1f}%)".format(native, 100.0 * native / max(total, 1)))
        print("aborts      : %s   dispatch misses: %s" % (d["aborts"], s["miss_total"]))

    per_pc = d.get("per_pc") or []

    # Enrichment split (occ_crc / occ_ok, psxrecomp feat/dirty-pc-enrichment):
    # what KIND of gap each entered PC is, which decides what fixes it. The
    # classes are documented on occ_split(); the one that matters for "should
    # we keep playing" is attrib_new (self-heals through this very harvest)
    # versus attrib_residual (already demanded, still no resident piece).
    # Rows from a build without the enrichment carry no occ_crc key; report
    # nothing rather than an all-zero split that reads as "no gaps".
    occ = occ_split(per_pc)
    if occ is None and per_pc and not quiet:
        # Silence here used to look like "no gaps". It actually means the live
        # build predates the dirty-PC enrichment, so this session cannot answer
        # what KIND of gap each PC is -- the whole point of the harvest. Say so
        # loudly while the session is still up and can be re-harvested from a
        # tree that has it (build-relprof).
        print("WARNING     : this build carries NO dirty-PC enrichment "
              "(no occ_crc on any row).")
        print("              The PCs are still unioned, but the seedable / "
              "attribution / outside split")
        print("              cannot be computed. Play on build-relprof -- "
              "build-dbg predates it.")
    if occ and not quiet:
        print("enrichment  : %d seedable interior gaps, %d new interior entries "
              "(no piece from anyone yet), %d undemanded attribution gaps "
              "(self-heal next loop), %d RESIDUAL attribution gaps (demanded, "
              "resident still has no piece)"
              % (occ["seed"], occ["interior_new"], occ["attrib_new"],
                 occ["attrib_residual"]))
        print("              owned, not harvestable: %d kernel RAM (BIOS), "
              "%d boot-EXE dirty text (SLPS_009.90); %d outside any compiled piece"
              % (occ["kernel"], occ["bootexe"], occ["none"]))
        print("              [by entries: seed %s / interior-new %s / attrib-new %s / "
              "residual %s / kernel %s / boot-exe %s / none %s]"
              % tuple("{:,}".format(occ[k + "_entries"]) for k in OCC_CLASSES))
        if occ["residual_pcs"]:
            print("              residual PCs: " + ", ".join(occ["residual_pcs"][:12])
                  + (" ..." if len(occ["residual_pcs"]) > 12 else ""))

    # Union this session's rows into the accumulated distinct set.
    #
    # Area stamping is DELTA-based, not snapshot-based. `dirty_ram_stats.per_pc`
    # is cumulative for the whole session, so the area resident right now says
    # nothing about a PC last entered twenty minutes and three rooms ago --
    # stamping the current area on every row would manufacture false
    # attributions, which is why this used to stamp only PCs newly seen by the
    # pass. But between two passes of the poller's timed re-harvest, a PC whose
    # `entries` count GREW was necessarily entered in that interval, and the
    # area resident across it is known. So: stamp a PC that is new, or whose
    # entry count rose since the previous pass. `areas` is a set, so a PC
    # entered under several areas accumulates all of them honestly.
    prev = _PREV.get(port)
    prev_entries = prev["entries"] if prev and prev.get("session") == session else {}
    existing = load_existing(save_json)
    before = len(existing)
    newly_seen = []
    stamped = 0
    for e in per_pc:
        key = norm_pc(e["pc"])
        was_present = key in existing
        cur = int(e.get("entries", 0))
        grew = cur > int(prev_entries.get(key, 0))
        stamp = area if (area and (not was_present or grew)) else None
        if stamp:
            stamped += 1
        merged = merge_row(existing.get(key), e, session=session, area=stamp,
                           build=build, resident=(resident if stamp or (resident and (not was_present or grew)) else None))
        merged["pc"] = key
        existing[key] = merged
        if not was_present and cur > 0:
            newly_seen.append((key, cur, int(e.get("insns", 0))))
    # Remember this pass so the next one can compute its delta. Keyed by port
    # and guarded by session: a restart zeroes the runtime's counters and
    # resolve_session() hands back a new id, which discards the stale baseline.
    _PREV[port] = {"session": session,
                   "entries": {norm_pc(e["pc"]): int(e.get("entries", 0))
                               for e in per_pc}}
    if area and not quiet:
        print("area stamps : %d PC(s) attributed to %s this pass%s"
              % (stamped, area,
                 "" if prev_entries else " (first pass -- newly-seen PCs only)"))

    merged_rows = sorted(existing.values(),
                         key=lambda r: -int(r.get("insns", 0)))
    entered = sum(1 for r in merged_rows if int(r.get("entries", 0)) > 0)

    if not no_save and save_json:
        os.makedirs(os.path.dirname(save_json) or ".", exist_ok=True)
        tmp = save_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(merged_rows, fh, indent=1)
        os.replace(tmp, save_json)
        if not quiet:
            print("\nobserved set: %d distinct PCs (%d entered), %d new this session "
                  "-> %s" % (len(merged_rows), entered, len(existing) - before,
                             save_json))

    shown = [c for c in newly_seen if c[2] >= min_insns]
    shown.sort(key=lambda c: -c[2])
    if not quiet:
        # Report the hottest entries this session that were not already accumulated.
        print("\nnew proven entries this session: %d" % len(shown))
        for pc, ent, ins in shown[:20]:
            print("   %s  entries=%-8d insns=%d" % (pc, ent, ins))
        if len(shown) > 20:
            print("   ... and %d more" % (len(shown) - 20))

    # "0 new PCs" is not evidence of a complete set -- it is equally consistent
    # with having replayed the same rooms. Report estimated coverage instead,
    # stratified so the gaps are addressable (see pc_coverage.py).
    rep = None
    if coverage:
        try:
            rep = cov.build(merged_rows, by="band")
            if not quiet:
                g = rep["global"]
                print()
                if g["estimate"] is None:
                    print("coverage    : not estimable yet (%d session(s) with "
                          "incidence; Chao2 needs 2)" % len(rep["sessions"]))
                else:
                    print("coverage    : %d of an estimated %s PCs (%s), "
                          "%d session(s)"
                          % (g["s_obs"], cov.fmt_num(g["estimate"]),
                             cov.fmt_pct(g["coverage"]).strip(),
                             len(rep["sessions"])))
                    # The condensed line is where a bogus 100 % does the most
                    # damage -- it is the number read every run, by someone
                    # not looking for a caveat. Carry the caveat with it.
                    if (g["s_obs"] and g["q1"] < 0.1 * g["s_obs"]) or \
                       ((g["coverage"] or 0) > 0.95 and len(rep["sessions"]) < 4):
                        print("   WARNING  : only %d of %d PCs unique to one session "
                              "-- sessions covering the\n              same content "
                              "look identical to saturation. Vary what you play."
                              % (g["q1"], g["s_obs"]))
                    worst = sorted((e for e in rep["strata"]
                                    if e["coverage"] is not None),
                                   key=lambda e: e["coverage"])[:3]
                    if worst:
                        print("least covered: " + ", ".join(
                            "%s %s" % (e["label"], cov.fmt_pct(e["coverage"]).strip())
                            for e in worst))
                    print("              full table: python tools/pc_coverage.py "
                          "[--by area]")
        except (OSError, ValueError, KeyError) as exc:
            # A coverage estimate is a reporting nicety; never let it cost a
            # harvest that has already been saved.
            if not quiet:
                print("coverage    : unavailable (%s)" % exc)

    return {"interp": interp, "native": native, "aborts": d["aborts"],
            "misses": s["miss_total"], "before": before, "after": len(merged_rows),
            "new": len(existing) - before, "entered": entered,
            "newly_seen": shown, "session": session, "coverage": rep,
            "occ": occ, "stamped": stamped, "area": area, "build": build}


OCC_CLASSES = ("seed", "interior_new", "attrib_new", "attrib_residual",
               "kernel", "bootexe", "none")


def occ_split(rows, captures=None):
    """Classify entered per_pc rows by their enrichment fields.

    Returns None when no row carries `occ_crc` (a build without the
    enrichment), else counts and entry sums per class:

      seed             occ_ok=1: interior gap inside live native code; this
                       harvest's alias seed makes it native next loop.
      interior_new     crc=0 but the PC lies inside a compiled band: a brand
                       new interior entry that NO occupant has a piece for
                       yet (nobody's function starts there either). First
                       sighting; the next extract demands it for every
                       occupant and the compile serves it. Same work as seed.
      attrib_new       occ_ok=0, foreign piece spans the PC, and NO capture
                       demanded the PC yet: a new interior point that happens
                       to be a function start in a sibling occupant. The
                       normal loop serves it (extract demands it for every
                       occupant, the per-variant compile gives the resident
                       its own fragment). Self-heals; do not stop playing.
      attrib_residual  occ_ok=0 and the PC WAS already demanded for every
                       occupant of its band, yet the resident still has no
                       validated piece: the demand was rejected (memo /
                       data-as-code), the bytes are rewritten at run time, or
                       the resident is an occupant the survey never compiled.
                       Cannot be played away; this is the real residual list.
      kernel           crc=0 and PC < 0x10000: the BIOS kernel copy in RAM.
      bootexe          crc=0 in SLPS_009.90 text outside every band: a boot
                       EXE page written at run time.
      none             crc=0 in no band and no owner: genuinely outside
                       compiled code (was mislabelled onto interior_new rows
                       until 2026-09-07 evening).

    Until 2026-09-07 attrib_new and attrib_residual were one class labelled
    "fixed on the compile side, not by harvesting more" -- true before
    psxrecomp #325, and wrong after it: 8 of the 9 rows so labelled that day
    were undemanded, i.e. ordinary harvest work."""
    if not any("occ_crc" in r for r in rows):
        return None
    if captures is None:
        captures = cov.load_captures()
    demanded = cov.demanded_pcs(captures)
    spans = cov.band_ranges(captures)
    exe_range = cov.exe_text_range()
    out = {k: 0 for k in OCC_CLASSES}
    out.update({k + "_entries": 0 for k in OCC_CLASSES})
    out["residual_pcs"] = []
    for r in rows:
        ent = int(r.get("entries", 0))
        if ent <= 0 or "occ_crc" not in r:
            # A row without the key is unenriched (legacy build), not
            # "nothing spans it"; counting it as `none` inflated that class
            # with 2,000 legacy rows when run over the accumulated file.
            continue
        pc = int(r["pc"], 16) & 0x1FFFFFFF
        crc = int(str(r.get("occ_crc") or "0"), 16)
        if crc == 0:
            owner = cov.owner_of(pc, spans, exe_range)
            if owner == cov.OWNER_KERNEL:
                k = "kernel"
            elif owner == cov.OWNER_BOOT_EXE:
                k = "bootexe"
            elif any(lo <= pc < hi for lo, hi in spans.values()):
                k = "interior_new"
            else:
                k = "none"
        elif int(r.get("occ_ok", 0)):
            k = "seed"
        elif pc in demanded:
            k = "attrib_residual"
            out["residual_pcs"].append("0x%08X" % (pc | 0x80000000))
        else:
            k = "attrib_new"
        out[k] += 1
        out[k + "_entries"] += ent
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-insns", type=int, default=0,
                    help="report filter only: hide entries with fewer "
                         "interpreted instructions (never affects what is saved)")
    ap.add_argument("--port", type=int, default=4370)
    ap.add_argument("--save-json", default="analysis/observed_interp_pcs.json")
    ap.add_argument("--no-save", action="store_true",
                    help="report only; do not touch the observed file")
    ap.add_argument("--session",
                    help="session id for incidence bookkeeping (default: a "
                         "timestamp). Pass the SAME id when harvesting the same "
                         "play session twice, or Chao2 counts it as two samples "
                         "and overstates coverage")
    ap.add_argument("--area",
                    help="area resident now (file or script md5); stamped on "
                         "PCs newly seen by this pass, and on any PC whose "
                         "entry count grew since the previous pass")
    ap.add_argument("--build",
                    help="build id to stamp on every row this pass. Defaults to "
                         "a fingerprint of the LOCAL tree (codegen hash + the "
                         "overlay bands in generated/); pass it explicitly when "
                         "the running exe was built from a different tree, or "
                         "the rows will be labelled with the wrong experiment")
    ap.add_argument("--no-coverage", action="store_true",
                    help="skip the Chao2 coverage estimate")
    args = ap.parse_args()
    harvest(port=args.port, save_json=args.save_json, no_save=args.no_save,
            min_insns=args.min_insns, session=args.session, area=args.area,
            coverage=not args.no_coverage, build=args.build)
    print("\nnext: tools/extract_overlays.py --observed  (reads %s),\n"
          "      then recompile all bands and rebuild." % args.save_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
