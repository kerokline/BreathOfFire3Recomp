#!/usr/bin/env python
"""The audio inside every .EMI: the (6, 8, 7) triplet is a miniature VAB.

    type 6   VAB header ("pBAV", 0xC20 bytes for one program) -- tone -> VAG map, pitch, volume
    type 8   the CUE TABLE ENTRIES the file installs at the head of bank `dest`'s
             31-entry table (0x8014869C + bank*0x7C): 4 bytes per cue word
             {flags, pan|prog, tone|priority, chord|voice}, so a 16-byte record
             defines cues bank<<8 | 0..3. Entries past the record are NOT
             cleared -- whatever the previous occupant left stays reachable
    type 7   the VAB body: the VAG samples, uploaded to the bank's SPU RAM slot

The TOC's +0x04 for these three is the bank id 0..6 (docs/EMI_TYPES.md), not
an address: 1 = spells / battle system, 2 = field & battle effects, 3..5 =
the party's voice slots (BPLCHAR), 6 = enemies (BENEMY, BOSS). A cue word is
therefore a slot, and the sound behind it is whichever file last loaded into
that bank (docs/SOUND_CUES.md). This tool reads the triplets straight off
the disc files and hashes each VAG the same way tools/se_resolve.py hashes
the live SPU RAM, so a catalogue label in names/se_cues.toml joins to a
disc file + VAG number with no guessing.

    python tools/audio_banks.py show MAGIC069            # one file's sheet
    python tools/audio_banks.py index                    # -> names/audio_banks.toml (every triplet)
    python tools/audio_banks.py join [--apply]           # catalogue sound id -> disc VAG(s); --apply writes `disc`

Needs analysis/emi_sections.json (tools/emi_survey.py) and the extracted
BIN/ tree (--bin-root, default D:\\BoFIII).
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS = os.path.join(ROOT, "analysis", "emi_sections.json")
OUT = os.path.join(ROOT, "names", "audio_banks.toml")
CUES = os.path.join(ROOT, "names", "se_cues.toml")
MAGIC = os.path.join(ROOT, "names", "magic.toml")
BIN_ROOT = os.environ.get("BOF3_BIN_ROOT", r"D:\BoFIII")


def triplets(bin_root=BIN_ROOT):
    """[{file, bank, header, cues, body}] for every (6, 8, 7) run sharing a dest."""
    secs = json.load(open(SECTIONS, encoding="utf-8"))["sections"]
    by_file = {}
    for s in secs:
        by_file.setdefault(s["file"], []).append(s)
    out = []
    for f, rows in sorted(by_file.items()):
        rows.sort(key=lambda s: s["index"])
        data = None
        for i in range(len(rows) - 2):
            a, b, c = rows[i], rows[i + 1], rows[i + 2]
            if (a["type"], b["type"], c["type"]) != (6, 8, 7) or not (a["dest"] == b["dest"] == c["dest"]):
                continue
            if data is None:
                p = os.path.join(bin_root, f.replace("/", os.sep))
                if not os.path.exists(p):
                    break
                data = open(p, "rb").read()
            out.append(dict(file=f, bank=a["dest"],
                            header=data[a["offset"]:a["offset"] + a["size"]],
                            cues=data[b["offset"]:b["offset"] + b["size"]],
                            body=data[c["offset"]:c["offset"] + c["size"]]))
    return out


def decode(t):
    """One triplet -> {file, bank, ps, vs, tones:[...], vags:[...], cues:[...]}."""
    h = t["header"]
    if h[:4] != b"pBAV":
        return None
    ver = struct.unpack_from("<I", h, 4)[0]
    ps = struct.unpack_from("<H", h, 0x12)[0]
    vs = struct.unpack_from("<H", h, 0x16)[0]
    nprog = 0x80 if (h[0] == 0x70 and ver > 4) else 0x40
    sizes = struct.unpack_from("<%dH" % (vs + 1), h, 0x20 + nprog * 0x10 + ps * 0x200)
    vags, off = [], 0
    for n in range(1, vs + 1):
        n_bytes = sizes[n] * 8
        smp = t["body"][off:off + n_bytes]
        vags.append(dict(n=n, size=n_bytes, md5=hashlib.md5(smp).hexdigest()[:12] if n_bytes else ""))
        off += n_bytes
    tones = []
    for p in range(ps):
        for tn in range(16):
            a = 0x20 + nprog * 0x10 + p * 0x200 + tn * 0x20
            attr = h[a:a + 0x20]
            vag = struct.unpack_from("<H", attr, 0x16)[0]
            if vag:
                tones.append(dict(prog=p, tone=tn, vag=vag, centre=attr[4], shift=attr[5], vol=attr[2], pan=attr[3]))
    tone_map = {(x["prog"], x["tone"]): x for x in tones}
    cues = []
    for i in range(len(t["cues"]) // 4):
        flags, pp, tp, cv = t["cues"][i * 4:i * 4 + 4]
        prog, tone = pp & 0x7F, tp >> 4
        tm = tone_map.get((prog, tone))
        cues.append(dict(cue="0x%X%02X" % (t["bank"], i), vab_override=flags & 7, prog=prog, tone=tone,
                         priority=tp & 0xF, voice=cv & 0x1F, chord=(cv >> 5) & 3, panned=bool(pp & 0x80),
                         vag=tm["vag"] if tm else 0, centre=tm["centre"] if tm else None))
    return dict(file=t["file"], bank=t["bank"], ps=ps, vs=vs, tones=tones, vags=vags, cues=cues)


def spell_names():
    """MAGICnnn.EMI -> 'jp / en' from names/magic.toml."""
    if not os.path.exists(MAGIC):
        return {}
    d = tomllib.load(open(MAGIC, "rb"))
    out = {}
    for r in d.get("ability", []):
        out.setdefault(r.get("file", ""), []).append("%s/%s" % (r.get("jp", ""), r.get("en", "")))
    return {k: " | ".join(sorted(set(v))) for k, v in out.items()}


def labels():
    if not os.path.exists(CUES):
        return {}
    return {c["id"]: c for c in tomllib.load(open(CUES, "rb")).get("sound", [])}


# ----------------------------------------------------------------- commands

def cmd_show(a):
    lab = labels()
    names = spell_names()
    hits = [decode(t) for t in triplets(a.bin_root) if a.file.upper() in t["file"].upper()]
    for d in hits:
        if d is None:
            continue
        base = d["file"].split("/")[-1]
        print("== %s  bank %d  %s" % (d["file"], d["bank"], names.get(base, "")))
        print("   VAB: %d program(s), %d VAG(s)" % (d["ps"], d["vs"]))
        for v in d["vags"]:
            print("   vag%-2d %6d bytes  %s  %s" % (v["n"], v["size"], v["md5"], lab.get(v["md5"], {}).get("label", "")))
        for c in d["cues"]:
            print("   cue %s -> prog %d tone %-2d -> vag%d  centre %s  pri %d voice %d%s%s" % (
                c["cue"], c["prog"], c["tone"], c["vag"], c["centre"], c["priority"], c["voice"],
                " +%d" % c["chord"] if c["chord"] else "", " panned" if c["panned"] else ""))
    if not hits:
        print("no audio triplet in a file matching %r" % a.file)
    return 0


def cmd_index(a):
    names = spell_names()
    rows = [decode(t) for t in triplets(a.bin_root)]
    rows = [r for r in rows if r]
    lines = ["# names/audio_banks.toml -- every (6, 8, 7) audio triplet on the disc, decoded",
             "# (tools/audio_banks.py index; do not hand-edit). One [[bank]] per triplet:",
             "#   file / bank   the .EMI and the bank id 0..6 its cue entries and VAB replace",
             "#   vags          n, size, md5 (12 hex) of each sample = the id names/se_cues.toml uses",
             "#   cues          cue word -> prog/tone -> vag n, as the type-8 record installs them",
             "", "[meta]", 'generator = "tools/audio_banks.py"', "triplets = %d" % len(rows), ""]
    for r in rows:
        base = r["file"].split("/")[-1]
        lines.append("[[bank]]")
        lines.append('file = "%s"' % r["file"])
        lines.append("bank = %d" % r["bank"])
        if base in names:
            lines.append('ability = "%s"' % names[base].replace('"', "'"))
        lines.append("vags = [%s]" % ", ".join('{ n = %d, size = %d, md5 = "%s" }' % (v["n"], v["size"], v["md5"]) for v in r["vags"]))
        lines.append("cues = [%s]" % ", ".join('{ cue = "%s", prog = %d, tone = %d, vag = %d }' % (c["cue"], c["prog"], c["tone"], c["vag"]) for c in r["cues"]))
        lines.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("%s: %d triplets" % (OUT, len(rows)))
    return 0


def cmd_join(a):
    lab = labels()
    by_md5 = {}
    for t in triplets(a.bin_root):
        d = decode(t)
        if not d:
            continue
        for v in d["vags"]:
            if v["md5"]:
                by_md5.setdefault(v["md5"], []).append("%s#vag%d" % (d["file"].split("/")[-1], v["n"]))
    matched = 0
    for sid, c in sorted(lab.items()):
        where = by_md5.get(sid, [])
        matched += bool(where)
        print("%s %-28s %s" % (sid, c["label"], ", ".join(where[:6]) + (" +%d" % (len(where) - 6) if len(where) > 6 else "") if where else "(not on disc as a triplet VAG)"))
    print("%d of %d catalogue sounds matched to disc VAGs" % (matched, len(lab)))
    if a.apply and lab:
        t = open(CUES, encoding="utf-8").read()
        for sid, c in lab.items():
            where = by_md5.get(sid)
            if not where:
                continue
            key = 'id = "%s"\n' % sid
            i = t.find(key)
            if i < 0:
                continue
            j = t.find("\n", t.find("cues = [", i))
            line = 'disc = [%s]' % ", ".join('"%s"' % w for w in where[:12])
            seg = t[i:j]
            if "disc = [" in seg:
                continue
            t = t[:j + 1] + line + "\n" + t[j + 1:]
        open(CUES, "w", encoding="utf-8", newline="\n").write(t)
        print("wrote disc = [...] into %s" % CUES)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--bin-root", default=BIN_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("file"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("index"); s.set_defaults(fn=cmd_index)
    s = sub.add_parser("join"); s.add_argument("--apply", action="store_true"); s.set_defaults(fn=cmd_join)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
