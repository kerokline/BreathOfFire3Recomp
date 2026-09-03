#!/usr/bin/env python
"""Build docs/subsystem_map.html — a self-contained, browsable map of the
title's code: bands → overlays → functions, plus the boot EXE, with human names
from names/*.toml and symbols.toml layered on top.

Offline join, no live game, no framework change. Sources:
  analysis/overlay_catalog.json       bands, overlays, heat (tools/overlay_catalog.py)
  analysis/overlay_captures_all.json  per-overlay bytes → function roots + in-overlay jal edges
  analysis/observed_interp_pcs.json   interp heat per PC (historical max)
  analysis/functions.tsv, edges.json  boot-EXE functions + call edges (ghidra seed)
  names/overlays.toml, names/functions.toml, symbols.toml   human names

The page embeds NO overlay bytes and NO disassembly — only addresses, sizes,
hashes, edge counts and names — so it is safe to commit (analysis/ is not).

Per-function fields, overlay side (derived from the resident image only):
  kind     jal | prologue | both | observed   (root provenance, as extract_overlays)
  span     bytes to the next root — an upper bound on the function's size
  callees  distinct in-overlay jal targets inside the span
  callers  distinct in-overlay functions whose span jal's this one
  insns    interp heat attributed to the span; ONLY for single-occupant bands
           (the catalog's band-attribution honesty rule), else band-level only

    python tools/subsystem_map.py                # → docs/subsystem_map.html
    python tools/subsystem_map.py --out x.html
"""
import argparse
import base64
import csv
import html
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_overlays import jal_targets, prologue_roots      # noqa: E402
from name_map import load_names                                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AN = os.path.join(ROOT, "analysis")


def hx(v):
    return int(v, 16) if isinstance(v, str) else int(v)


def load_observed():
    p = os.path.join(AN, "observed_interp_pcs.json")
    if not os.path.exists(p):
        return {}
    out = {}
    for r in json.load(open(p, encoding="utf-8")):
        out[hx(r["pc"]) & 0x1FFFFFFF] = (int(r.get("insns", 0)), int(r.get("entries", 0)))
    return out


def overlay_functions(cap, observed, attribute_heat):
    """Function table for one capture: roots, spans, in-overlay edges, heat."""
    data = base64.b64decode(cap["bytes_b64"])
    base = hx(cap["load_addr"])
    size = len(data)
    jal = jal_targets(data, base)
    pro = prologue_roots(data, base)
    obs_roots = {hx(p) for p in cap.get("static_discovery_entry_pcs", [])} | \
                {hx(p) for p in cap.get("dispatch_entry_pcs", [])}
    roots = sorted(jal | pro | obs_roots)
    if not roots:
        return []
    # per-word jal destinations, once
    words = [w for w, in struct.iter_unpack("<I", data[: size // 4 * 4])]
    calls_at = {}
    for i, w in enumerate(words):
        if (w >> 26) == 3:
            t = (base & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if base <= t < base + size:
                calls_at[base + i * 4] = t
    # heat per phys address, only inside this image
    heat = {}
    if attribute_heat:
        lo, hi = base & 0x1FFFFFFF, (base + size) & 0x1FFFFFFF
        for phys, (ins, ent) in observed.items():
            if lo <= phys < hi:
                heat[phys | 0x80000000] = (ins, ent)
    # spans
    idx = {r: i for i, r in enumerate(roots)}
    ends = roots[1:] + [base + size]
    callees = [set() for _ in roots]
    for pc, t in calls_at.items():
        # owner = last root <= pc
        i = _owner(roots, pc)
        if i is not None and t in idx:
            callees[i].add(t)
    callers = [set() for _ in roots]
    for i, cs in enumerate(callees):
        for t in cs:
            callers[idx[t]].add(roots[i])
    fins = [[0, 0] for _ in roots]
    for pc, (ins, ent) in heat.items():
        i = _owner(roots, pc)
        if i is not None:
            fins[i][0] += ins
            fins[i][1] += ent
    out = []
    for i, r in enumerate(roots):
        kind = ("both" if r in jal and r in pro else "jal" if r in jal
                else "prologue" if r in pro else "observed")
        out.append([r, kind, ends[i] - r, len(callees[i]), len(callers[i]),
                    fins[i][0], fins[i][1]])
    return out


def _owner(roots, pc):
    import bisect
    i = bisect.bisect_right(roots, pc) - 1
    return i if i >= 0 else None


def load_boot():
    funcs, edges = [], []
    p = os.path.join(AN, "functions.tsv")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                funcs.append([hx(r["addr"]), int(r["size"]), r["confidence"],
                              int(r["args"] or 0), r["ret"], int(r["callers"] or 0),
                              int(r["callees"] or 0), r["tags"]])
    p = os.path.join(AN, "edges.json")
    if os.path.exists(p):
        for e in json.load(open(p, encoding="utf-8")).get("edges", []):
            edges.append([e["from"], e["to"], e["kind"]])
    return funcs, edges


def build():
    cat = json.load(open(os.path.join(AN, "overlay_catalog.json"), encoding="utf-8"))
    caps = json.load(open(os.path.join(AN, "overlay_captures_all.json"), encoding="utf-8"))
    observed = load_observed()
    names = load_names()
    by_md5 = {c["source_md5"]: c for c in caps}

    overlays = []
    fn_names = {}
    for o in cat["overlays"]:
        cap = by_md5.get(o["content_md5"])
        funcs = overlay_functions(cap, observed, o["heat_attribution"] == "occupant") if cap else []
        nm = names["overlays"].get(o["content_md5"], {})
        for f in funcs:
            e = names["functions"].get((o["content_md5"], f[0]))
            if e:
                fn_names[f"{o['content_md5']}:{f[0]:08X}"] = {
                    "name": e.get("name"), "args": e.get("args", []),
                    "ret": e.get("ret"), "status": e.get("status", "unnamed")}
        overlays.append({
            "md5": o["content_md5"], "name": o["name"], "family": o["family"],
            "src": f"{o['source_file']}#{o['source_index']}",
            "load": o["load_addr"], "size": o["size"], "band": o["band_base"],
            "band_n": o["band_occupant_count"], "clean": o["band_clean"],
            "roots": o["roots"], "attr": o["heat_attribution"],
            "heat": o["heat"] or {"interp_insns": 0, "entries": 0, "entered_pcs": 0},
            "band_heat": o["band_interp_insns"],
            "alias": nm.get("alias", ""), "role": nm.get("role", ""),
            "status": nm.get("status", "unnamed"), "evidence": nm.get("evidence", ""),
            "funcs": funcs,
        })

    bands = []
    for base, b in cat["bands"].items():
        bands.append({"base": base, **b,
                      "occupants": [i for i, o in enumerate(overlays) if o["band"] == base]})
    bands.sort(key=lambda b: -b["interp_insns"])

    # Areas (places) from names/areas.toml, joined to any code overlay of the
    # same .EMI file. Most areas have none: they run on the field game-mode.
    areas = []
    by_src = {}
    for i, o in enumerate(overlays):
        by_src.setdefault(o["src"].split("#")[0], []).append(i)
    for f, a in sorted(names.get("areas", {}).items()):
        areas.append({"file": f, "name": os.path.splitext(os.path.basename(f))[0],
                      "world": f.split("/")[1] if "/" in f else "",
                      "script_md5": a.get("script_md5", ""), "alias": a.get("alias", ""),
                      "status": a.get("status", "unnamed"), "evidence": a.get("evidence", ""),
                      "sightings": a.get("sightings", []), "shots": a.get("shots", []),
                      "overlays": by_src.get(f, [])})

    bfuncs, bedges = load_boot()
    for f in bfuncs:
        e = names["functions"].get(("boot", f[0]))
        if e:
            fn_names[f"boot:{f[0]:08X}"] = {"name": e["name"], "args": e.get("args", []),
                                            "ret": e.get("ret"), "status": e.get("status")}
    return {
        "generated_from": {"catalog": cat.get("schema"), "overlays": len(overlays),
                           "bands": len(bands), "observed_pcs": len(observed),
                           "boot_funcs": len(bfuncs), "boot_edges": len(bedges)},
        "bands": bands, "overlays": overlays, "names": fn_names, "areas": areas,
        "boot": {"funcs": bfuncs, "edges": bedges},
    }


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BoF3 Subsystem Map</title>
<style>
:root{--bg:#fafaf8;--fg:#1c1c1a;--mute:#6b6b66;--line:#e2e1dc;--card:#fff;--acc:#2f5fa8;--warm:#b3551d;--ok:#2d7a4b;--hi:#fff6d6}
@media(prefers-color-scheme:dark){:root{--bg:#161615;--fg:#e8e6e0;--mute:#9a9891;--line:#2c2c2a;--card:#1e1e1c;--acc:#7fa6e6;--warm:#e8905a;--ok:#6cc08a;--hi:#3a3320}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:18px;margin:0}header .m{color:var(--mute);font-size:12px}
header input{margin-left:auto;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);min-width:280px}
main{display:grid;grid-template-columns:300px 1fr;min-height:calc(100vh - 52px)}
nav{border-right:1px solid var(--line);overflow:auto;padding:10px}
nav h3{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:10px 6px 4px}
.band{margin:4px 0;border:1px solid var(--line);border-radius:8px;background:var(--card)}
.band>summary{padding:6px 8px;cursor:pointer;font-family:ui-monospace,Consolas,monospace;font-size:12px;display:flex;gap:6px;align-items:center}
.band>summary .fam{color:var(--mute);font-family:system-ui;font-size:11px;flex:1;text-align:right}
.ov{display:block;padding:3px 10px 3px 18px;font-size:12px;cursor:pointer;color:var(--fg);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov:hover,.ov.sel{background:var(--hi)}.ov .a{color:var(--acc)}.ov .n{color:var(--mute)}
section{padding:18px 24px;overflow:auto}
.card{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:3px 14px;font-size:13px}.kv b{color:var(--mute);font-weight:500}.kv span{min-width:0;white-space:normal}.kv b{max-width:180px;white-space:normal}.links a{white-space:nowrap;margin-right:8px}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{cursor:pointer;color:var(--mute);font-weight:600;position:sticky;top:0;background:var(--card)}td.n{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,Consolas,monospace}.tag{display:inline-block;padding:0 6px;border-radius:10px;font-size:11px;border:1px solid var(--line);color:var(--mute)}
.tag.clean{color:var(--ok);border-color:var(--ok)}.tag.mixed{color:var(--warm);border-color:var(--warm)}
.tag.verified{color:var(--ok)}.tag.evidence{color:var(--acc)}.tag.hypothesis{color:var(--warm)}
.heat{display:inline-block;height:8px;background:var(--warm);border-radius:2px;vertical-align:middle}
.hint{color:var(--mute);font-size:12px}.hits mark{background:var(--hi);color:inherit}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0}.chip{padding:2px 8px;border:1px solid var(--line);border-radius:12px;font-size:12px;cursor:pointer;background:var(--card)}
.chip.on{background:var(--hi)}
</style></head><body>
<header><h1>BoF3 Subsystem Map</h1><span class="m" id="meta"></span>
<input id="q" placeholder="search name / alias / pc / md5 …  (e.g. Battle, 801D0C00, SCENA)"></header>
<main><nav id="nav"></nav><section id="view"></section></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const $=s=>document.querySelector(s);const h=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hex=v=>'0x'+(v>>>0).toString(16).toUpperCase().padStart(8,'0');
const fmt=n=>n.toLocaleString();
const nm=(k)=>D.names[k];
const label=(o)=>o.alias?`<span class="a">${h(o.alias)}</span> <span class="n">${h(o.name)}</span>`:h(o.name);
$('#meta').textContent=`${D.generated_from.overlays} overlays · ${D.generated_from.bands} bands · ${D.generated_from.boot_funcs} boot-EXE funcs · ${D.generated_from.observed_pcs} observed PCs`;
function nav(){
  let s='<h3>Boot EXE</h3><a class="ov" data-v="boot">SLPS_009.90 <span class="n">'+D.boot.funcs.length+' funcs</span></a>';
  if(D.areas.length){s+='<h3>Areas sighted (places)</h3><a class="ov" data-v="areas">all areas <span class="n">'+D.areas.length+'</span></a>';
    for(const a of D.areas)s+=`<a class="ov" data-v="area:${h(a.file)}">${a.alias?`<span class="a">${h(a.alias)}</span> <span class="n">${h(a.name)}</span>`:h(a.name)} <span class="n">${a.overlays.length?a.overlays.length+' code':'no code'}</span></a>`;}
  s+='<h3>Bands (by interp heat)</h3>';
  for(const b of D.bands){
    const fams=b.families.join(', ');
    s+=`<details class="band" open><summary><a class="ov" style="padding:0" data-v="band:${b.base}">${b.base}</a><span class="tag ${b.clean?'clean':'mixed'}">${b.clean?'clean':'mixed '+b.occupant_count}</span><span class="fam">${h(fams)}</span></summary>`;
    const occ=b.occupants.map(i=>D.overlays[i]).sort((a,b)=>(b.heat.interp_insns-a.heat.interp_insns)||a.name.localeCompare(b.name));
    for(const o of occ)s+=`<a class="ov" data-v="ov:${o.md5}" title="${h(o.src)}">${label(o)} <span class="n">${o.funcs.length}f</span></a>`;
    s+='</details>';
  }
  $('#nav').innerHTML=s;
}
const maxHeat=Math.max(1,...D.bands.map(b=>b.interp_insns));
function bar(v,max){return `<span class="heat" style="width:${Math.max(2,120*v/max)|0}px"></span>`}
function view(key){
  document.querySelectorAll('.ov.sel').forEach(e=>e.classList.remove('sel'));
  const a=document.querySelector(`.ov[data-v="${key}"]`);if(a)a.classList.add('sel');
  location.hash=key;
  if(key==='boot')return viewBoot();
  if(key==='areas')return viewAreas();
  if(key.startsWith('area:'))return viewArea(D.areas.find(a=>a.file===key.slice(5)));
  if(key.startsWith('band:'))return viewBand(key.slice(5));
  if(key.startsWith('ov:'))return viewOverlay(D.overlays.find(o=>o.md5===key.slice(3)));
  viewHome();
}
function viewHome(){
  let s=`<div class="card"><h2 style="margin:0 0 6px">Where the code is</h2><p class="hint">Bands are load addresses shared by every overlay that loads there. Heat is interpreted-instruction weight (historical max across sessions), attributed to a band; it reaches individual overlays and functions only in single-occupant bands. Names come from <span class="mono">names/*.toml</span> and <span class="mono">symbols.toml</span>.</p>
  <table><tr><th>band</th><th>occupants</th><th>families</th><th>interp insns</th><th></th><th>entered PCs</th></tr>`;
  for(const b of D.bands)s+=`<tr><td class="mono"><a href="#band:${b.base}">${b.base}</a></td><td class="n">${b.occupant_count}</td><td>${h(b.families.join(', '))}</td><td class="n">${fmt(b.interp_insns)}</td><td>${bar(b.interp_insns,maxHeat)}</td><td class="n">${b.entered_pcs}</td></tr>`;
  s+='</table></div>';
  const st={};for(const o of D.overlays)st[o.status]=(st[o.status]||0)+1;
  const fn=Object.values(D.names);const fs={};for(const f of fn)fs[f.status]=(fs[f.status]||0)+1;
  const as={};for(const a of D.areas)as[a.status]=(as[a.status]||0)+1;
  s+=`<div class="card"><h3 style="margin:0 0 6px">Naming coverage</h3><div class="kv"><b>overlays</b><span>${Object.entries(st).map(([k,v])=>`${k} ${v}`).join(' · ')}</span><b>areas</b><span>${D.areas.length} sighted (${Object.entries(as).map(([k,v])=>`${k} ${v}`).join(' · ')||'none'}), <a href="#areas">list</a></span><b>functions</b><span>${fn.length} named (${Object.entries(fs).map(([k,v])=>`${k} ${v}`).join(' · ')||'none'})</span></div></div>`;
  $('#view').innerHTML=s;
}
function viewBand(base){
  const b=D.bands.find(b=>b.base===base);
  let s=`<div class="card"><h2 style="margin:0" class="mono">${base} <span class="tag ${b.clean?'clean':'mixed'}">${b.clean?'single family':'mixed families'}</span></h2>
  <div class="kv" style="margin-top:8px"><b>span</b><span>${fmt(b.span)} bytes</span><b>occupants</b><span>${b.occupant_count}</span><b>families</b><span>${h(b.families.join(', '))}</span><b>interp insns</b><span>${fmt(b.interp_insns)} (${b.entries} entries, ${b.entered_pcs} PCs)</span></div>
  ${b.clean?'':'<p class="hint">Mixed band: an observed PC here cannot be attributed to one occupant offline. Per-overlay heat below is band-level only.</p>'}</div>
  <div class="card"><table><tr><th>overlay</th><th>family</th><th>size</th><th>funcs</th><th>jal/prologue/observed</th><th>heat</th><th>status</th></tr>`;
  const occ=b.occupants.map(i=>D.overlays[i]).sort((a,b)=>b.size-a.size);
  for(const o of occ)s+=`<tr><td><a href="#ov:${o.md5}">${label(o)}</a></td><td>${h(o.family)}</td><td class="n">${fmt(o.size)}</td><td class="n">${o.funcs.length}</td><td class="n">${o.roots.jal}/${o.roots.prologue}/${o.roots.observed_entries}</td><td>${o.attr==='occupant'?fmt(o.heat.interp_insns):'<span class="hint">band-shared</span>'}</td><td><span class="tag ${o.status}">${o.status}</span></td></tr>`;
  $('#view').innerHTML=s+'</table></div>';
}
let sortKey=5,sortDir=-1;
function viewOverlay(o){
  const cols=['pc','kind','span','callees','callers','interp insns','entries','name'];
  let s=`<div class="card"><h2 style="margin:0">${label(o)}</h2><div class="kv" style="margin-top:8px">
  <b>source</b><span class="mono">${h(o.src)}</span><b>md5</b><span class="mono">${o.md5}</span><b>load</b><span class="mono">${o.load} · ${fmt(o.size)} bytes · band ${o.band} (${o.band_n} occupant${o.band_n>1?'s':''})</span>
  <b>roots</b><span>${o.roots.jal} jal · ${o.roots.prologue} prologue · ${o.roots.both} both · ${o.roots.observed_entries} observed-only → ${o.funcs.length} functions</span>
  <b>heat</b><span>${o.attr==='occupant'?fmt(o.heat.interp_insns)+' interp insns, '+fmt(o.heat.entries)+' entries, '+o.heat.entered_pcs+' PCs':'band-shared ('+fmt(o.band_heat)+' insns on the band; not attributable to this occupant offline)'}</span>
  <b>role</b><span>${h(o.role)||'<span class="hint">—</span>'}</span><b>status</b><span><span class="tag ${o.status}">${o.status}</span> ${h(o.evidence)}</span></div></div>`;
  const hubs=[...o.funcs].sort((a,b)=>b[4]-a[4]).slice(0,5).filter(f=>f[4]>=3);
  const entries=o.funcs.filter(f=>f[4]===0&&f[3]>0);
  s+=`<div class="card"><div style="margin-bottom:6px"><span class="hint">hubs (most in-overlay callers):</span> <span class="links">${hubs.map(f=>fnLink(o,f)).join('')||'<span class="hint">none with ≥3 callers</span>'}</span></div><div><span class="hint">entry candidates (no in-overlay callers, has callees):</span> <span class="links">${entries.slice(0,12).map(f=>fnLink(o,f)).join('')}${entries.length>12?'<span class="hint">… +'+(entries.length-12)+'</span>':''}</span></div>
  <p class="hint">Edges are in-overlay jal only. Calls into the boot EXE / other bands and fn-pointer dispatch are not counted (see harvest_logo_handlers.py for the jalr-table case).</p></div>`;
  s+=`<div class="card"><table id="ft"><tr>${cols.map((c,i)=>`<th data-i="${i}">${c}${sortKey===i?(sortDir<0?' ▼':' ▲'):''}</th>`).join('')}</tr>`;
  const rows=o.funcs.map(f=>{const n=nm(o.md5+':'+f[0].toString(16).toUpperCase().padStart(8,'0'));return [...f,n]});
  rows.sort((a,b)=>{const x=sortKey===7?(a[7]?a[7].name:''):a[sortKey],y=sortKey===7?(b[7]?b[7].name:''):b[sortKey];return (x>y?1:x<y?-1:0)*sortDir});
  const mh=Math.max(1,...o.funcs.map(f=>f[5]));
  for(const r of rows)s+=`<tr id="f${r[0].toString(16)}"><td class="mono">${hex(r[0])}</td><td>${r[1]}</td><td class="n">${r[2]}</td><td class="n">${r[3]}</td><td class="n">${r[4]}</td><td class="n">${r[5]?fmt(r[5])+' '+bar(r[5],mh):''}</td><td class="n">${r[6]||''}</td><td>${r[7]?`<b>${h(r[7].name)}</b>(${(r[7].args||[]).map(h).join(', ')}) <span class="tag ${r[7].status}">${r[7].status}</span>`:''}</td></tr>`;
  $('#view').innerHTML=s+'</table></div>';
  $('#ft').querySelectorAll('th').forEach(t=>t.onclick=()=>{const i=+t.dataset.i;if(sortKey===i)sortDir*=-1;else{sortKey=i;sortDir=i<2||i===7?1:-1}viewOverlay(o)});
}
function fnLink(o,f){const n=nm(o.md5+':'+f[0].toString(16).toUpperCase().padStart(8,'0'));return `<a class="mono" href="#ov:${o.md5}" onclick="setTimeout(()=>document.getElementById('f${f[0].toString(16)}')?.scrollIntoView(),0)">${n?h(n.name):hex(f[0])}</a>`}
function viewAreas(){
  let s=`<div class="card"><h2 style="margin:0 0 6px">Areas sighted</h2><p class="hint">An area is a place, identified with certainty by the script block at 0x80010000 (tools/area_poller.py). Most areas ship no code section: they run on the field game-mode overlay plus data, so they live in <span class="mono">names/areas.toml</span>, not the overlay sidecar. The alias comes from reading the screenshot.</p>
  <table><tr><th>area</th><th>world</th><th>alias</th><th>status</th><th>sightings</th><th>shots</th><th>code overlays</th></tr>`;
  for(const a of D.areas)s+=`<tr><td><a href="#area:${h(a.file)}">${h(a.name)}</a></td><td>${h(a.world)}</td><td>${h(a.alias)}</td><td><span class="tag ${a.status}">${a.status}</span></td><td class="n">${a.sightings.length}</td><td class="n">${a.shots.length}</td><td>${a.overlays.map(i=>`<a href="#ov:${D.overlays[i].md5}">${label(D.overlays[i])}</a>`).join(', ')||'<span class="hint">none</span>'}</td></tr>`;
  $('#view').innerHTML=s+'</table></div>';
}
function viewArea(a){
  if(!a)return viewAreas();
  let s=`<div class="card"><h2 style="margin:0">${a.alias?h(a.alias)+' ':''}<span class="${a.alias?'n':''}">${h(a.name)}</span></h2><div class="kv" style="margin-top:8px">
  <b>file</b><span class="mono">${h(a.file)}</span><b>script md5</b><span class="mono">${h(a.script_md5)}</span>
  <b>status</b><span><span class="tag ${a.status}">${a.status}</span> ${h(a.evidence)}</span>
  <b>sightings</b><span>${a.sightings.map(h).join(', ')||'<span class="hint">none</span>'}</span>
  <b>screenshots</b><span>${a.shots.map(p=>`<span class="mono">${h(p)}</span>`).join('<br>')||'<span class="hint">none yet (the poller shoots 4 s after the area settles)</span>'}</span>
  <b>code overlays</b><span>${a.overlays.map(i=>`<a href="#ov:${D.overlays[i].md5}">${label(D.overlays[i])}</a>`).join(', ')||'<span class="hint">none: runs on the field game-mode overlay + data</span>'}</span></div>
  <p class="hint">Screenshots are local files under analysis/ (not committed); open one next to this page to read the location name, then set alias + status in names/areas.toml.</p></div>`;
  $('#view').innerHTML=s;
}
let bsort=0,bdir=1;
function viewBoot(){
  const cols=['addr','size','confidence','args','ret','callers','callees','tags','name'];
  let s=`<div class="card"><h2 style="margin:0">Boot EXE — SLPS_009.90</h2><p class="hint">From analysis/functions.tsv + edges.json (ghidra seed pass). Names from symbols.toml. ${D.boot.edges.length} call edges.</p></div><div class="card"><table id="bt"><tr>${cols.map((c,i)=>`<th data-i="${i}">${c}${bsort===i?(bdir<0?' ▼':' ▲'):''}</th>`).join('')}</tr>`;
  const rows=D.boot.funcs.map(f=>[...f,nm('boot:'+f[0].toString(16).toUpperCase().padStart(8,'0'))]);
  rows.sort((a,b)=>{const x=bsort===8?(a[8]?a[8].name:''):a[bsort],y=bsort===8?(b[8]?b[8].name:''):b[bsort];return (x>y?1:x<y?-1:0)*bdir});
  for(const r of rows)s+=`<tr><td class="mono">${hex(r[0])}</td><td class="n">${r[1]}</td><td>${r[2]}</td><td class="n">${r[3]}</td><td>${r[4]}</td><td class="n">${r[5]}</td><td class="n">${r[6]}</td><td class="hint">${h(r[7])}</td><td>${r[8]?`<b>${h(r[8].name)}</b> <span class="tag ${r[8].status}">${r[8].status}</span>`:''}</td></tr>`;
  $('#view').innerHTML=s+'</table></div>';
  $('#bt').querySelectorAll('th').forEach(t=>t.onclick=()=>{const i=+t.dataset.i;if(bsort===i)bdir*=-1;else{bsort=i;bdir=1}viewBoot()});
}
function search(q){
  q=q.trim().toLowerCase();if(!q)return viewHome();
  const qn=q.replace(/^0x/,'');const hits=[];
  for(const o of D.overlays){
    if(o.name.toLowerCase().includes(q)||o.alias.toLowerCase().includes(q)||o.md5.startsWith(qn)||o.load.toLowerCase().includes(qn)||o.family.toLowerCase().includes(q))hits.push(`<a href="#ov:${o.md5}">${label(o)}</a> <span class="hint">${h(o.family)} @ ${o.load}</span>`);
    if(/^[0-9a-f]{6,8}$/.test(qn)){const pc=((parseInt(qn,16)|0x80000000)>>>0);for(const f of o.funcs)if(f[0]===pc||(pc>=f[0]&&pc<f[0]+f[2]&&f[2]<=0x4000))hits.push(`<a href="#ov:${o.md5}">${label(o)}</a> <span class="mono">${hex(f[0])}</span> <span class="hint">${f[1]}, span ${f[2]}${f[0]!==pc?' (interior)':''}</span>`)}
  }
  for(const a of D.areas)if(a.name.toLowerCase().includes(q)||a.alias.toLowerCase().includes(q)||a.file.toLowerCase().includes(q))hits.push(`area <a href="#area:${h(a.file)}">${h(a.alias||a.name)}</a> <span class="hint">${h(a.file)}</span>`);
  for(const [k,v] of Object.entries(D.names))if(v.name.toLowerCase().includes(q)){const [ov,pc]=k.split(':');hits.push(`<b>${h(v.name)}</b> <span class="mono">0x${pc}</span> in <a href="#${ov==='boot'?'boot':'ov:'+ov}">${ov==='boot'?'boot EXE':h((D.overlays.find(o=>o.md5===ov)||{}).name||ov)}</a>`)}
  if(/^[0-9a-f]{6,8}$/.test(qn)){const pc=((parseInt(qn,16)|0x80000000)>>>0);for(const f of D.boot.funcs)if(pc>=f[0]&&pc<f[0]+f[1])hits.push(`<a href="#boot">boot EXE</a> <span class="mono">${hex(f[0])}</span> <span class="hint">${f[2]}${f[0]!==pc?' (interior)':''}</span>`)}
  $('#view').innerHTML=`<div class="card hits"><h3 style="margin:0 0 8px">${hits.length} hit${hits.length!==1?'s':''} for “${h(q)}”</h3>${hits.slice(0,200).map(x=>'<div>'+x+'</div>').join('')}</div>`;
}
nav();
document.addEventListener('click',e=>{const a=e.target.closest('a.ov');if(a){e.preventDefault();view(a.dataset.v)}});
window.addEventListener('hashchange',()=>view(decodeURIComponent(location.hash.slice(1))));
$('#q').addEventListener('input',e=>search(e.target.value));
view(decodeURIComponent(location.hash.slice(1)));
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "subsystem_map.html"))
    ap.add_argument("--json", help="also dump the joined data as JSON")
    a = ap.parse_args()
    data = build()
    if a.json:
        json.dump(data, open(a.json, "w", encoding="utf-8"))
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(PAGE.replace("__DATA__", blob))
    n_f = sum(len(o["funcs"]) for o in data["overlays"])
    print(f"{a.out}: {os.path.getsize(a.out)/1e6:.1f} MB, "
          f"{len(data['overlays'])} overlays, {n_f} overlay functions, "
          f"{len(data['boot']['funcs'])} boot functions, {len(data['names'])} names")


if __name__ == "__main__":
    main()
