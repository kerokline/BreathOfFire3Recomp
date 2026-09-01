#!/usr/bin/env python
"""Build analysis/overlay_catalog.json — a browsable sidecar over the overlay
captures. Pure offline join; no live game, no framework change.

The capture file (overlay_captures_all.json) is the *compiler's input* — lean,
address-keyed, base64 bytes. This catalog is the *human/tooling view*: it joins
what we already have on disk into a self-describing, ranked inventory.

Sources joined:
  * analysis/overlay_captures_all.json — the captures (bytes, roots, entries)
  * analysis/emi_sections.json          — survey (section type / class)
  * analysis/observed_interp_pcs.json   — live interp weight per PC (the "heat")

What it adds per overlay (HANDOFF "make it easier to catalog"):
  #1 family/subsystem tag           — PLCHAR / BATTLE / SCENARIO / WORLDnn / ...
  #2 band membership + co-residency — which band, how many share it, who they are
  #3 root provenance                — JAL vs PROLOGUE vs OBSERVED, not one blob
  #6 interp heat                    — insns/entries, honestly attributed

Heat honesty: a band == a single load_addr shared by every occupant, so an
observed PC in that address range cannot be resolved to one occupant offline
(the documented band-level-attribution limit). So band heat is attached to the
BAND (accurate: a PC there ran, whichever tenant), and per-overlay occupant heat
is populated ONLY for single-occupant bands. Multi-occupant overlays are tagged
`band-shared` and point at the band total instead of double-claiming it. The
durable fix is the tier-1 resident-CRC runtime capture (see HANDOFF).

    python tools/overlay_catalog.py            # current on-disk slice
    python tools/overlay_catalog.py --top 20   # + print the hottest bands
"""
import argparse
import base64
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_overlays import jal_targets, prologue_roots   # noqa: E402
from enrich_pcs import family                               # noqa: E402


def load_observed(path):
    """phys_pc -> {insns, entries, hits}. Masked to physical (HANDOFF trap:
    the JSON stores physical addresses, the report prints kseg0)."""
    if not os.path.exists(path):
        return {}
    out = {}
    for r in json.load(open(path, encoding="utf-8")):
        phys = int(r["pc"], 16) & 0x1FFFFFFF
        out[phys] = {
            "insns": int(r.get("insns", 0)),
            "entries": int(r.get("entries", 0)),
            "hits": int(r.get("hits", 0)),
        }
    return out


def survey_index(path):
    """(FILE, index) -> {type, class} from the .EMI survey."""
    if not os.path.exists(path):
        return {}
    doc = json.load(open(path))
    out = {}
    for s in doc.get("sections", []):
        out[(s["file"].upper(), s["index"])] = {
            "type": s.get("type"),
            "class": s.get("class"),
        }
    return out


def name_of(source_file):
    """BIN/PLCHAR/PLP27A.EMI -> PLP27A."""
    base = source_file.rsplit("/", 1)[-1]
    return base[:-4] if base.upper().endswith(".EMI") else base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", default="analysis/overlay_captures_all.json")
    ap.add_argument("--survey", default="analysis/emi_sections.json")
    ap.add_argument("--observed", default="analysis/observed_interp_pcs.json")
    ap.add_argument("--out", default="analysis/overlay_catalog.json")
    ap.add_argument("--top", type=int, default=0,
                    help="also print the N hottest bands to stdout")
    args = ap.parse_args()

    caps = json.load(open(args.captures))
    observed = load_observed(args.observed)
    survey = survey_index(args.survey)

    # --- band membership: captures grouped by shared load_addr (== band base) -
    bands = defaultdict(list)
    for c in caps:
        bands[int(c["load_addr"], 16)].append(c)

    # --- band-level heat: sum observed PCs that fall in each band's address span
    band_meta = {}
    for base, occ in bands.items():
        phys = base & 0x1FFFFFFF
        span = max(c["size"] for c in occ)
        ins = ent = npc = 0
        for ppc, o in observed.items():
            if phys <= ppc < phys + span and o["entries"] > 0:
                ins += o["insns"]; ent += o["entries"]; npc += 1
        fams = sorted({family(c["source_file"]) for c in occ})
        band_meta[base] = {
            "occupant_count": len(occ),
            "span": span,
            "families": fams,
            "clean": len(fams) == 1,
            "interp_insns": ins,
            "entries": ent,
            "entered_pcs": npc,
        }

    # --- per-overlay records ------------------------------------------------
    overlays = []
    for c in caps:
        base = int(c["load_addr"], 16)
        bm = band_meta[base]
        data = base64.b64decode(c["bytes_b64"])
        jal = jal_targets(data, base)
        pro = prologue_roots(data, base)
        static = jal | pro
        siblings = sorted(name_of(o["source_file"]) + "#%d" % o["source_index"]
                          for o in bands[base]
                          if not (o["source_file"] == c["source_file"]
                                  and o["source_index"] == c["source_index"]))

        # Occupant-accurate heat only when the band has a single tenant.
        single = bm["occupant_count"] == 1
        if single:
            occ_heat = {"interp_insns": bm["interp_insns"],
                        "entries": bm["entries"],
                        "entered_pcs": bm["entered_pcs"]}
            attribution = "occupant"
        else:
            occ_heat = None
            attribution = "band-shared(%d)" % bm["occupant_count"]

        sv = survey.get((c["source_file"].upper(), c["source_index"]), {})
        overlays.append({
            "name": name_of(c["source_file"]),
            "content_md5": c["source_md5"],   # region-independent identity key
            "crc32": c["crc32"],
            "family": family(c["source_file"]),
            "source_file": c["source_file"],
            "source_index": c["source_index"],
            "source_type": sv.get("type"),
            "source_class": sv.get("class"),
            "load_addr": c["load_addr"],
            "size": c["size"],
            "band_base": "0x%08X" % base,
            "band_occupant_count": bm["occupant_count"],
            "band_families": bm["families"],
            "band_clean": bm["clean"],
            "siblings": siblings,
            "roots": {
                "jal": len(jal),
                "prologue": len(pro),
                "both": len(jal & pro),
                "static_total": len(static),
                "observed_entries": len(c["dispatch_entry_pcs"]),
            },
            "function_count": len(static),
            "heat_attribution": attribution,
            "heat": occ_heat,             # null unless single-occupant band
            "band_interp_insns": bm["interp_insns"],   # always the band total
            "band_entered_pcs": bm["entered_pcs"],
        })

    # Rank: hottest band first, then band base, then name — a catalog reads
    # top-down as "where the interpreted work is".
    overlays.sort(key=lambda o: (-o["band_interp_insns"],
                                 int(o["band_base"], 16), o["name"]))

    catalog = {
        "schema": "overlay-catalog-v1",
        "source_captures": os.path.basename(args.captures),
        "source_observed": os.path.basename(args.observed),
        "counts": {
            "overlays": len(overlays),
            "bands": len(bands),
            "observed_pcs": len(observed),
        },
        "bands": {"0x%08X" % b: band_meta[b] for b in sorted(band_meta)},
        "overlays": overlays,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(catalog, open(args.out, "w"), indent=1)
    print("catalog: %d overlays across %d bands -> %s"
          % (len(overlays), len(bands), args.out))

    if args.top:
        print("\n%-12s %5s %-26s %14s %5s  %s"
              % ("band", "occ", "families", "interp_ins", "PCs", "attribution"))
        for b in sorted(band_meta, key=lambda k: -band_meta[k]["interp_insns"])[:args.top]:
            m = band_meta[b]
            tag = "CLEAN" if m["clean"] else "MIXED(%d)" % len(m["families"])
            print("0x%08X %5d %-26s %14d %5d  %s"
                  % (b, m["occupant_count"], ",".join(m["families"])[:26],
                     m["interp_insns"], m["entered_pcs"], tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
