#!/usr/bin/env python
"""Human-name sidecar for overlays and their functions (names/*.toml).

The generated C is `func_XXXXXXXX` / `<overlay>_func_XXXXXXXX` and is
regenerated on every Axis-B pass, so human names cannot live in it. They live
here, keyed so they survive re-extraction and band overlap:

  names/overlays.toml   [[overlay]]  md5 (content identity), name, family,
                                     alias, role, status, evidence
  names/functions.toml  [[func]]     overlay (md5 | "boot"), pc, name, args,
                                     ret, status, evidence
  names/areas.toml      [[area]]     file (BIN/WORLDnn/AREAnnn.EMI), script_md5,
                                     alias, status, evidence, shots, sightings
                                     -- an AREA is a place, not an overlay: most
                                     areas ship no code section, so they need
                                     their own key (tools/area_poller.py writes)

Boot-EXE names stay in the root symbols.toml (the framework's PSX_FN_* path);
functions.toml holds overlay-resident functions only. `load_names()` merges
both for tooling (tools/subsystem_map.py).

Why md5 and not PC: eleven bands share load addresses across 339 overlays, so
a PC alone names a slot, not a function. (md5, pc) names a function.

    python tools/name_map.py init     # seed/merge names/overlays.toml from the catalog
    python tools/name_map.py check    # every md5 in names/ exists in the catalog
    python tools/name_map.py stats    # coverage: named / hypothesis / unnamed

`init` is a MERGE: it adds overlays the catalog knows and names/ does not, and
never touches an entry a human has edited. Delete an entry to have it re-seeded.

Status vocabulary (mirrors symbols.toml):
  unnamed      seeded, nobody has looked
  hypothesis   name proposed from filename / pattern, no runtime evidence
  evidence     name backed by a trace, a rendered string, or a data-doc citation
  verified     evidence + confirmed by a second independent route
"""
import argparse
import json
import os
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES_DIR = os.path.join(ROOT, "names")
OVERLAYS_TOML = os.path.join(NAMES_DIR, "overlays.toml")
FUNCTIONS_TOML = os.path.join(NAMES_DIR, "functions.toml")
AREAS_TOML = os.path.join(NAMES_DIR, "areas.toml")
SYMBOLS_TOML = os.path.join(ROOT, "symbols.toml")
CATALOG = os.path.join(ROOT, "analysis", "overlay_catalog.json")

STATUSES = ("unnamed", "hypothesis", "evidence", "verified")


# ---------------------------------------------------------------- TOML I/O

def _q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _emit_table(kind, rows, header):
    out = [header.rstrip() + "\n"]
    for r in rows:
        out.append(f"\n[[{kind}]]\n")
        for k, v in r.items():
            if v is None:
                continue
            if isinstance(v, bool):
                out.append(f"{k} = {'true' if v else 'false'}\n")
            elif isinstance(v, int):
                out.append(f"{k} = 0x{v:08X}\n" if k == "pc" else f"{k} = {v}\n")
            elif isinstance(v, list):
                out.append(f"{k} = [{', '.join(_q(x) for x in v)}]\n")
            else:
                out.append(f"{k} = {_q(v)}\n")
    return "".join(out)


def _read(path, key):
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return tomllib.load(f).get(key, [])


OVERLAYS_HEADER = """\
# names/overlays.toml — human names for the .EMI overlays (see tools/name_map.py).
# Keyed by md5 of the section bytes, NOT by load address (bands overlap).
# Edit alias / role / status / evidence by hand. `name`, `family`, `source`
# are seeded from analysis/overlay_catalog.json and are informational.
#
#   status:   unnamed | hypothesis | evidence | verified
#   evidence: how the alias was established (trace, rendered string, data doc)
"""

FUNCTIONS_HEADER = """\
# names/functions.toml — human names for overlay-resident functions.
# Boot-EXE functions belong in ../symbols.toml (PSX_FN_* path), not here.
#
#   overlay:  md5 from names/overlays.toml  (or "boot" is REJECTED — use symbols.toml)
#   pc:       function entry inside that overlay's resident image
#   args:     parameter names in a0..a3 order, e.g. ["location", "actor"]
#   status:   unnamed | hypothesis | evidence | verified
#   evidence: which trace / string / data-doc citation backs the name
"""


AREAS_HEADER = """# names/areas.toml — human names for AREA files (places), written by
# tools/area_poller.py summarize --apply. Keyed by the area's script block
# (the section whose dest is 0x80010000; md5 from analysis/emi_sections.json).
# An area is a PLACE: most ship no code overlay, so they cannot live in
# overlays.toml. Edit alias / status by hand; sightings and shots are
# refreshed by the poller (never lost, never overwritten).
#
#   status:   unnamed | hypothesis | evidence | verified
#   evidence: how the alias was established (which screenshot / session)
"""


# ---------------------------------------------------------------- loaders

def load_area_names():
    """area file -> entry dict."""
    return {r["file"]: r for r in _read(AREAS_TOML, "area")}


def load_overlay_names():
    """md5 -> entry dict."""
    return {r["md5"]: r for r in _read(OVERLAYS_TOML, "overlay")}


def load_function_names():
    """(overlay_key, pc) -> entry dict, overlay_key = md5 or 'boot'.
    Merges symbols.toml (boot) and names/functions.toml (overlays)."""
    out = {}
    for r in _read(SYMBOLS_TOML, "func"):
        out[("boot", int(r["pc"]))] = {
            "name": r["name"], "args": r.get("args", []), "ret": r.get("ret"),
            "status": r.get("status", "unnamed"), "evidence": r.get("note", ""),
        }
    # the file documents `[[function]]`; an older tool revision wrote `[[func]]`
    for r in _read(FUNCTIONS_TOML, "function") + _read(FUNCTIONS_TOML, "func"):
        if r.get("overlay") == "boot":
            sys.exit("names/functions.toml: boot-EXE entries belong in symbols.toml")
        out[(r["overlay"], int(r["pc"]))] = r
    return out


def load_names():
    return {"overlays": load_overlay_names(), "functions": load_function_names(),
            "areas": load_area_names()}


# ---------------------------------------------------------------- commands

def cmd_init(args):
    cat = json.load(open(CATALOG, encoding="utf-8"))
    existing = load_overlay_names()
    rows, added = [], 0
    seen = set()
    for o in cat["overlays"]:
        md5 = o["content_md5"]
        if md5 in seen:
            continue
        seen.add(md5)
        if md5 in existing:
            rows.append(existing[md5])
            continue
        rows.append({
            "md5": md5,
            "name": o["name"],
            "family": o["family"],
            "source": f"{o['source_file']}#{o['source_index']}",
            "alias": "",
            "role": "",
            "status": "unnamed",
            "evidence": "",
        })
        added += 1
    # keep hand entries whose md5 the catalog no longer lists (re-extraction drift)
    orphans = [e for m, e in existing.items() if m not in seen]
    for e in orphans:
        e = dict(e)
        e["note"] = (e.get("note", "") + " [not in current catalog]").strip()
        rows.append(e)
    os.makedirs(NAMES_DIR, exist_ok=True)
    with open(OVERLAYS_TOML, "w", encoding="utf-8", newline="\n") as f:
        f.write(_emit_table("overlay", rows, OVERLAYS_HEADER))
    if not os.path.exists(FUNCTIONS_TOML):
        with open(FUNCTIONS_TOML, "w", encoding="utf-8", newline="\n") as f:
            f.write(FUNCTIONS_HEADER)
    print(f"overlays.toml: {len(rows)} entries ({added} added, "
          f"{len(existing) - len(orphans)} kept, {len(orphans)} orphaned)")


def cmd_check(args):
    cat = json.load(open(CATALOG, encoding="utf-8"))
    known = {o["content_md5"] for o in cat["overlays"]}
    bad = 0
    for md5, e in load_overlay_names().items():
        if md5 not in known:
            print(f"overlays.toml: {md5} ({e.get('name')}) not in catalog"); bad += 1
        if e.get("status") not in STATUSES:
            print(f"overlays.toml: {md5} bad status {e.get('status')!r}"); bad += 1
        if e.get("alias") and e.get("status") == "unnamed":
            print(f"overlays.toml: {md5} has alias but status=unnamed"); bad += 1
    names = load_overlay_names()
    for (ov, pc), e in load_function_names().items():
        if ov == "boot":
            continue
        if ov not in names:
            print(f"functions.toml: overlay {ov} unknown (pc 0x{pc:08X})"); bad += 1
        if e.get("status") not in STATUSES:
            print(f"functions.toml: 0x{pc:08X} bad status {e.get('status')!r}"); bad += 1
    for f, e in load_area_names().items():
        if e.get("status") not in STATUSES:
            print(f"areas.toml: {f} bad status {e.get('status')!r}"); bad += 1
        if e.get("alias") and e.get("status") == "unnamed":
            print(f"areas.toml: {f} has alias but status=unnamed"); bad += 1
    print("ok" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


def cmd_stats(args):
    ov = load_overlay_names()
    fn = load_function_names()
    from collections import Counter
    print("overlays:", dict(Counter(e.get("status", "unnamed") for e in ov.values())))
    print("functions:", dict(Counter(e.get("status", "unnamed") for e in fn.values())),
          f"({sum(1 for k in fn if k[0] == 'boot')} boot via symbols.toml)")
    ar = load_area_names()
    print("areas:", dict(Counter(e.get("status", "unnamed") for e in ar.values())),
          f"({len(ar)} sighted)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "check", "stats"])
    a = ap.parse_args()
    return {"init": cmd_init, "check": cmd_check, "stats": cmd_stats}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
