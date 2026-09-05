#!/usr/bin/env python
"""Stratified coverage estimate for the observed interpreted-PC set.

Why this exists: the Axis B loop's stop condition used to be "play until a
session stops producing new entered PCs" (docs/HANDOFF.md section 1). That is
unfalsifiable -- zero new PCs is equally consistent with "the set is complete"
and with "the player walked the same three rooms twice". It also says nothing
about WHERE the gaps are, so there is no way to decide what to go play next.

This replaces it with a falsifiable number. Treating each play session as a
sampling unit and each PC as a species, the observed set is a species-incidence
matrix and the unseen remainder is estimable by Chao2:

    N = S_obs + ((m-1)/m) * Q1^2 / (2*Q2)          (Q2 > 0)
    N = S_obs + ((m-1)/m) * Q1*(Q1-1) / 2          (Q2 = 0, bias-corrected)

where Q1/Q2 are the PCs seen in exactly one / exactly two sessions and m is the
session count. Coverage is then S_obs / N.

Read the estimate as a LOWER BOUND on the true total, for a reason specific to
this game: sessions are not random draws from one pool. Which .EMI area is
resident decides which addresses can bucket to a band at all, so two sessions
are nearly disjoint (measured 2026-08-31: two sessions shared 323 of ~17,500
PCs). Under that much heterogeneity Chao2 systematically under-estimates. This
is exactly why the report stratifies -- inside one band or one area the
sampling is far closer to homogeneous, so the per-stratum estimates are sounder
than the global one, and summing them beats estimating the whole at once.

Two denominators appear in the report and they answer different questions:

  est. total   Chao2 on session incidence -- "how many interpreter-entry PCs
               remain to be FOUND here". This is the one the loop needs.
  fn starts    static count of function starts in the band's code (`jr ra`
               occurrences, fingerprint-deduped across sections that share
               library code). A hard ceiling, not a target: most of those
               functions are reached by static call edges and are already
               native, so they will never appear as an interpreted PC.

What the coverage column does NOT mean: it measures HARVEST completeness, not
nativeness. A band at 100% coverage can still be slow -- its PCs are known but
not yet compiled in. Those are separate axes; use harvest_interp_pcs.py's
interpreted/native ratio for the second one.

    python tools/pc_coverage.py                 # by band
    python tools/pc_coverage.py --by area       # by resident area
    python tools/pc_coverage.py --by none       # global only
    python tools/pc_coverage.py --json out.json
"""
import argparse
import base64
import collections
import hashlib
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AN = os.path.join(ROOT, "analysis")
OBSERVED = os.path.join(AN, "observed_interp_pcs.json")
CAPTURES = os.path.join(AN, "overlay_captures_all.json")

JR_RA = 0x03E00008
LEGACY = "legacy"          # session id stamped on rows predating incidence


# ------------------------------------------------------------------ chao2

def chao2(incidence, m):
    """Chao2 richness estimate from a list of per-PC session counts.

    `incidence` is one integer per observed PC: in how many DISTINCT sessions
    it was entered. `m` is the number of sessions. Returns a dict; `estimate`
    is None when there is not enough data (m < 2, or no singletons).

    The variance is the classic Chao approximate form; the confidence interval
    is the log-normal one (Chao 1987), which keeps the lower bound above S_obs
    instead of letting a symmetric interval run below the count already in
    hand.
    """
    s_obs = len(incidence)
    q1 = sum(1 for c in incidence if c == 1)
    q2 = sum(1 for c in incidence if c == 2)
    out = {"s_obs": s_obs, "q1": q1, "q2": q2, "sessions": m,
           "estimate": None, "unseen": None, "coverage": None,
           "ci_low": None, "ci_high": None}
    if s_obs == 0 or m < 2:
        return out
    corr = float(m - 1) / m
    if q2 > 0:
        f0 = corr * (q1 * q1) / (2.0 * q2)
        r = float(q1) / q2
        var = q2 * (0.5 * r ** 2 + r ** 3 + 0.25 * r ** 4)
    else:
        f0 = corr * q1 * (q1 - 1) / 2.0
        var = (0.25 * q1 * (2 * q1 - 1) ** 2 + 0.25 * q1 ** 4) if q1 else 0.0
    est = s_obs + f0
    out["estimate"] = est
    out["unseen"] = f0
    out["coverage"] = s_obs / est if est > 0 else None
    if f0 > 0 and var > 0:
        k = math.exp(1.96 * math.sqrt(math.log(1.0 + var / (f0 * f0))))
        out["ci_low"] = s_obs + f0 / k
        out["ci_high"] = s_obs + f0 * k
    else:
        out["ci_low"] = out["ci_high"] = est
    return out


# ------------------------------------------------------- static denominator

def load_captures(path=CAPTURES):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def band_ranges(captures):
    """{band base (physical int): (lo, hi)} spanning every capture there."""
    spans = {}
    for c in captures:
        base = int(c["load_addr"], 16) & 0x1FFFFFFF
        lo, hi = base, base + int(c["size"])
        if base in spans:
            spans[base] = (min(spans[base][0], lo), max(spans[base][1], hi))
        else:
            spans[base] = (lo, hi)
    return spans


def static_per_band(captures):
    """Per band: distinct function starts and registered dispatch entries.

    Function starts are counted by `jr ra` and deduplicated by a 12-word
    fingerprint taken after the delay slot, because many .EMI files ship the
    same library routines at the same load address and a raw count would
    inflate a band by every copy.
    """
    fns = collections.defaultdict(set)
    entries = collections.defaultdict(set)
    for c in captures:
        base = int(c["load_addr"], 16) & 0x1FFFFFFF
        entries[base].update(c.get("dispatch_entry_pcs") or [])
        b = base64.b64decode(c["bytes_b64"])
        n = len(b) // 4
        w = struct.unpack("<%dI" % n, b[:n * 4])
        for i, x in enumerate(w):
            if x == JR_RA:
                fp = w[i + 2:i + 14]
                if len(fp) == 12:
                    fns[base].add(fp)
                else:
                    # Trailing return with no room for a fingerprint: key it by
                    # section so it counts once and never collides.
                    fns[base].add(("tail", i, hashlib.md5(b).hexdigest()))
    return ({k: len(v) for k, v in fns.items()},
            {k: len(v) for k, v in entries.items()})


# ------------------------------------------------------------------ loading

def load_observed(path=OBSERVED):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def entered_rows(rows):
    return [r for r in rows if int(r.get("entries", 0)) > 0]


def row_sessions(r):
    """Distinct real session ids for a row; legacy rows yield []."""
    s = r.get("sessions")
    if isinstance(s, list):
        return sorted({x for x in s if x and x != LEGACY})
    return []


def duplicate_sessions(rows):
    """[(kept_id, [redundant_ids])] for ids that provably sample one process.

    The runtime's per-PC table is cumulative and only grows within a process,
    so if session A's PC set is a subset of session B's, A cannot be a separate
    play session -- it is an earlier snapshot of the same one. Two ids over one
    process split a sampling unit in half, deflating Q1 and overstating
    coverage, so the report must not quietly count them as two.

    Equal sets are the degenerate case (two harvests seconds apart); the
    earlier id wins so the merged id keeps the session's real start time.
    """
    sets = {}
    for r in rows:
        for s in row_sessions(r):
            sets.setdefault(s, set()).add(r["pc"])
    ids = sorted(sets)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            A, B = sets[a], sets[b]
            if A and B and (A <= B or B <= A):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)   # earliest id survives
    groups = collections.defaultdict(list)
    for i in ids:
        groups[find(i)].append(i)
    return [(k, sorted(set(v) - {k})) for k, v in sorted(groups.items())
            if len(v) > 1]


def merge_duplicate_sessions(path, dups):
    """Rewrite the observed file collapsing each group to its surviving id."""
    rename = {}
    for keep, drop in dups:
        for d in drop:
            rename[d] = keep
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    # Back up BEFORE mutating: a backup written afterwards preserves the
    # merged data, which is not a backup of anything.
    bak = path + ".premerge.bak"
    if not os.path.exists(bak):
        with open(bak, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1)
    n = 0
    for r in rows:
        s = r.get("sessions")
        if not s:
            continue
        new = sorted({rename.get(x, x) for x in s})
        if new != s:
            r["sessions"] = new
            n += 1
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    os.replace(tmp, path)
    return n


def band_label(base):
    return "0x%08X" % (base | 0x80000000)


def stratify(rows, by, spans):
    """{stratum label: [rows]} -- 'band', 'area', or 'none'.

    For 'band' every known band is seeded empty first. A band nobody has
    entered must show up as NEVER SAMPLED rather than vanish: the estimator
    cannot say anything about a stratum it has no draws from, and a table that
    silently omits those reads as far better news than it is."""
    if by == "none":
        return {"(all)": list(rows)}
    out = collections.defaultdict(list)
    if by == "band":
        for base in spans:
            out[band_label(base)] = []
    if by == "area":
        for r in rows:
            areas = r.get("areas") or []
            if not areas:
                out["(unattributed)"].append(r)
            for a in areas:
                out[a].append(r)
        return out
    for r in rows:
        pc = int(r["pc"], 16) & 0x1FFFFFFF
        label = "(outside every band)"
        for base, (lo, hi) in spans.items():
            if lo <= pc < hi:
                label = band_label(base)
                break
        out[label].append(r)
    return out


# ------------------------------------------------------------------- report

def build(rows, by="band", captures=None):
    captures = load_captures() if captures is None else captures
    spans = band_ranges(captures)
    ent = entered_rows(rows)

    all_sessions = set()
    legacy_only = 0
    for r in ent:
        s = row_sessions(r)
        all_sessions.update(s)
        if not s:
            legacy_only += 1

    fn_counts, entry_counts = static_per_band(captures)
    strata = stratify(ent, by, spans)

    table = []
    for label, group in sorted(strata.items()):
        # Sessions are counted WITHIN the stratum: a session that never entered
        # this band is not a sample of it, and counting it would deflate the
        # correction factor and understate what is still missing.
        local_sessions = set()
        for r in group:
            local_sessions.update(row_sessions(r))
        inc = [len(row_sessions(r)) for r in group if row_sessions(r)]
        est = chao2(inc, len(local_sessions))
        est["label"] = label
        est["rows"] = len(group)
        est["legacy_only"] = sum(1 for r in group if not row_sessions(r))
        if by == "band" and label.startswith("0x"):
            base = int(label, 16) & 0x1FFFFFFF
            est["fn_starts"] = fn_counts.get(base)
            est["registered"] = entry_counts.get(base)
        table.append(est)

    # Names are attached here, not at print time, so the harvest one-liner and
    # the --json report say "0x801F2C00 WORLD*5" too.
    names = band_names() if by == "band" else (area_aliases() if by == "area" else {})
    for e in table:
        e["name"] = names.get(e["label"], "")
        e["display"] = label_for(e["label"], names)

    glob = chao2([len(row_sessions(r)) for r in ent if row_sessions(r)],
                 len(all_sessions))
    glob["label"] = "(global)"
    glob["rows"] = len(ent)
    glob["legacy_only"] = legacy_only
    return {"by": by, "sessions": sorted(all_sessions), "global": glob, "duplicate_sessions": duplicate_sessions(ent),
            "strata": table,
            "static_fn_starts_total": sum(fn_counts.values()),
            "distinct_pcs": len(rows), "entered_pcs": len(ent)}


CATALOG = os.path.join(AN, "overlay_catalog.json")


def _collapse_families(fams):
    """['WORLD00'..'WORLD04'] -> 'WORLD*5'; unrelated families stay verbatim.

    Numbered siblings are one subsystem wearing five file names, and spelling
    them out crowds the real information (that this band is WORLD) off the row.
    """
    groups = collections.OrderedDict()
    for f in fams:
        stem = f.rstrip("0123456789") or f
        groups.setdefault(stem, []).append(f)
    parts = []
    for stem, members in groups.items():
        parts.append(members[0] if len(members) == 1 else "%s*%d" % (stem, len(members)))
    if len(parts) > 3:
        return "+".join(parts[:3]) + " +%d" % (len(parts) - 3)
    return "+".join(parts)


def band_names(catalog_path=CATALOG):
    """{band label: human name} from analysis/overlay_catalog.json.

    A bare `0x801F2C00` says nothing about what playing would exercise. The
    catalog already knows which .EMI families load at each band (and
    axis_b_loop.py phase 3b refreshes it every run), so the name is derived
    evidence, not a label invented here. A single-occupant band with a human
    alias in names/overlays.toml uses the alias -- that is strictly more
    informative than its family, and it is where the readability track's work
    already landed.
    """
    try:
        with open(catalog_path, encoding="utf-8") as fh:
            cat = json.load(fh)
    except (OSError, ValueError):
        return {}
    aliases = {}
    try:
        sys.path.insert(0, HERE)
        import name_map as nm
        aliases = nm.load_overlay_names()
    except Exception:
        pass
    by_band = collections.defaultdict(list)
    for o in cat.get("overlays") or []:
        by_band[o.get("band_base")].append(o)
    out = {}
    for base, b in (cat.get("bands") or {}).items():
        occ = by_band.get(base) or []
        if b.get("occupant_count") == 1 and occ:
            alias = (aliases.get(occ[0].get("content_md5")) or {}).get("alias")
            if alias:
                out[base] = alias
                continue
        name = _collapse_families(b.get("families") or [])
        n = b.get("occupant_count") or 0
        if n > 1:
            name += " x%d" % n
        # "(mixed)" only where the name does not already show it. A rendered
        # "BATTLE+ETC+SCENARIO" says mixed on its face; a collapsed "WORLD*5"
        # does not, and that is the row where the warning earns its width.
        if not b.get("clean", True) and "+" not in name:
            name += " (mixed)"
        out[base] = name or "?"
    return out


def area_aliases():
    """{AREA file: human alias} from names/areas.toml, or {} if unavailable.

    A band address answers "where in the address space"; an alias answers
    "where in the game", which is the form the coverage table has to be in for
    "go play these next" to be actionable."""
    try:
        sys.path.insert(0, HERE)
        import name_map as nm
        return {k: (v.get("alias") or "") for k, v in nm.load_area_names().items()}
    except Exception:
        return {}


def label_for(label, names):
    """Stratum label plus its human name, keeping the raw key visible.

    The address / filename is what every other tool and doc uses, so it leads;
    the name rides along to say what playing it would exercise."""
    a = names.get(label)
    if not a:
        return label
    stem = (os.path.splitext(os.path.basename(label))[0]
            if label.upper().endswith(".EMI") else label)
    return "%s %s" % (stem, a)


def fmt_pct(x):
    return "  --  " if x is None else "%5.1f%%" % (100.0 * x)


def fmt_num(x):
    return "--" if x is None else "%.0f" % x


def print_report(rep):
    g = rep["global"]
    print("observed set : %d distinct PCs, %d with entries>0"
          % (rep["distinct_pcs"], rep["entered_pcs"]))
    print("sessions     : %d with incidence recorded" % len(rep["sessions"]))
    if g["legacy_only"]:
        print("               %d PCs are legacy rows (harvested before session ids "
              "existed);\n               they count as seen but cannot contribute "
              "Q1/Q2, so early estimates\n               will read pessimistically "
              "until they are re-observed." % g["legacy_only"])
    if len(rep["sessions"]) < 2:
        print("\nNOT ENOUGH DATA: Chao2 needs at least 2 sessions carrying session "
              "ids.\nharvest_interp_pcs.py stamps one automatically; after the "
              "second such\nsession this report becomes meaningful.")
        return

    print("\nglobal       : %d seen of an estimated %s  (95%% CI %s..%s)"
          % (g["s_obs"], fmt_num(g["estimate"]),
             fmt_num(g["ci_low"]), fmt_num(g["ci_high"])))
    print("               Q1=%d seen in exactly one session, Q2=%d in exactly two"
          % (g["q1"], g["q2"]))
    print("               a LOWER bound -- sessions are heterogeneous; trust the "
          "per-stratum\n               rows more than this one (see module "
          "docstring)")

    # Chao2's entire signal is singletons. Sessions covering the SAME content
    # drive Q1 to zero and the estimate to "you have everything" -- which is
    # indistinguishable, to the estimator, from actually having everything.
    # Say so, because a confident 100% off two identical runs is the one way
    # this report can mislead worse than the criterion it replaced.
    dups = rep.get("duplicate_sessions") or []
    if dups:
        # Provable same-process splits inflate m and deflate Q1, so every
        # number above is optimistic until these are merged.
        print("")
        print("DUPLICATE SESSIONS: %d id(s) provably sample a process already"
              % sum(len(d) for _, d in dups))
        for keep, drop in dups:
            print("         %s absorbs %s" % (keep, ", ".join(drop)))
        print("         Their PC sets are subsets, which only happens within one")
        print("         process. Counted separately they overstate coverage. Fix:")
        print("         python tools/pc_coverage.py --merge-duplicates")
    m = len(rep["sessions"])
    thin = g["s_obs"] and g["q1"] < 0.1 * g["s_obs"]
    confident_but_shallow = (g["coverage"] or 0) > 0.95 and m < 4
    if thin or confident_but_shallow:
        print("\nWARNING: %d of %d PCs seen in exactly one session, over %d session(s)."
              % (g["q1"], g["s_obs"], m))
        print("         A high number here means only that nothing looked unique to "
              "one run.\n         Sessions covering the SAME content produce exactly "
              "that, and Chao2 cannot\n         distinguish it from real saturation. "
              "Vary what you play, and read the\n         NEVER SAMPLED / legacy-only "
              "rows below as the honest gaps.")

    extra = rep["by"] == "band"
    width = 44
    head = "%-*s %6s %6s %6s %10s %9s" % (width, "stratum", "seen", "Q1", "Q2",
                                          "est.total", "coverage")
    if extra:
        head += " %10s %11s" % ("fn starts", "registered")
    print("\n" + head)
    print("-" * len(head))
    # A stratum holding only legacy rows has nothing to estimate from; it is
    # listed after the rest rather than dropped, so a gap in the bookkeeping
    # never masquerades as a gap in the game.
    for e in sorted(rep["strata"],
                    key=lambda x: (x["coverage"] is None, x["coverage"] or 0.0)):
        line = "%-*s %6d %6d %6d %10s %9s" % (
            width, e.get("display", e["label"])[:width],
            e["s_obs"], e["q1"], e["q2"],
            fmt_num(e["estimate"]), fmt_pct(e["coverage"]))
        if extra:
            line += " %10s %11s" % (
                e["fn_starts"] if e.get("fn_starts") is not None else "-",
                e["registered"] if e.get("registered") is not None else "-")
        if e["s_obs"] == 0:
            line += ("   (%d legacy-only)" % e["legacy_only"] if e["legacy_only"]
                     else "   NEVER SAMPLED")
        print(line)

    print("\ncoverage = harvest completeness, NOT nativeness. A band at 100% can "
          "still be\nslow until its PCs are compiled in -- use "
          "harvest_interp_pcs.py's interp/native\nratio for that axis.")
    if rep["by"] != "none":
        print("the strata sum above the global estimate; that gap IS the "
              "heterogeneity,\nand the stratified sum is the better total.")
    # A stratum with no draws is a bigger gap than a stratum at 40%, so the
    # unsampled ones lead. Recommending the well-covered bands because the
    # empty ones have no coverage number to sort by would be exactly backwards.
    unsampled = [e for e in rep["strata"] if e["s_obs"] == 0]
    partial = sorted((e for e in rep["strata"] if e["coverage"] is not None),
                     key=lambda e: e["coverage"])
    if rep["by"] != "none" and (unsampled or len(partial) > 1):
        picks = ["%s (%s)" % (e.get("display", e["label"]),
                              "legacy-only" if e["legacy_only"] else "never sampled")
                 for e in unsampled[:5]]
        picks += ["%s (%s)" % (e.get("display", e["label"]),
                               fmt_pct(e["coverage"]).strip())
                  for e in partial[:max(0, 5 - len(picks))]]
        print("\ngo play these next: " + ", ".join(picks))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--observed", default=OBSERVED)
    ap.add_argument("--captures", default=CAPTURES)
    ap.add_argument("--by", choices=("band", "area", "none"), default="band")
    ap.add_argument("--merge-duplicates", action="store_true",
                    help="rewrite the observed file collapsing session ids "
                         "that provably sample one process (backup: "
                         "<observed>.premerge.bak), then report")
    ap.add_argument("--json", dest="json_out",
                    help="also write the full report as JSON here")
    a = ap.parse_args()
    if not os.path.exists(a.observed):
        print("no observed file: %s" % a.observed, file=sys.stderr)
        return 1
    if a.merge_duplicates:
        dups = duplicate_sessions(entered_rows(load_observed(a.observed)))
        if not dups:
            print("no provable duplicate sessions -- nothing to merge")
        else:
            n = merge_duplicate_sessions(a.observed, dups)
            print("merged %d id(s) into %d session(s) across %d rows"
                  % (sum(len(d) for _, d in dups), len(dups), n))
            print("backup: %s.premerge.bak" % a.observed)
            print("")
    rep = build(load_observed(a.observed), by=a.by,
                captures=load_captures(a.captures))
    print_report(rep)
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
        print("\nwrote %s" % a.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
