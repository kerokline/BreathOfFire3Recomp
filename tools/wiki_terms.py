#!/usr/bin/env python
"""The BoF Wiki's BoF III glossary, fetched and parsed into the TSV that
tools/text_tables.py joins its tables against (docs/TEXT_TABLES.md "glossary").

Source: https://bof.fandom.com/wiki/Breath_of_Fire_III_Translations, taken as
wikitext (`?action=raw`) rather than scraped from the rendered page.  34 tables,
882 term rows, five columns: Japanese, romaji, a fan literal English, the
official English by Bowne Global Solutions (who localized the game), and Notes.

Two wikitext shapes have to be honoured or the columns shift:

  colspan=2   41 rows, nearly all of them spells, merge the romaji and
              literal-English cells because the name is invented syllables with
              no literal meaning.  Read positionally they shift one column left,
              so the Bowne name lands in `english_literal` and the Notes text in
              `english_official` -- which is what the 2026-09-05 hand extraction
              did, and why Glossary._pick in tools/text_tables.py carries a
              "long strings are notes" fallback.
  colspan=5   one full-width banner row ("Overworld", inside Locations) that is
              a sub-heading, not a term.
  rowspan=N   10 cells are shared down 14 following rows (the three fly-fishing
              lure names, Emitai's golems, Ein/Zwei/Drei ...), so the trailing
              cell is absent there and has to be carried forward -- without its
              attributes, or it re-registers itself and leaks down the table.

Column count is not fixed either: Unused/dummy skills has four columns, having
no Bowne name to give, so columns are mapped by header text and not by position.

The `notes` column is new.  It is the part of the page that cannot be derived
from the disc: it records what the same Japanese term became in each other
title (Deis was Bleu in I and II, the Dragon God is Ladon here and Dragon Lord
in I), which is the spine of a cross-title terminology table.

Column order keeps the first five fields exactly as they were, so an existing
reader that does DictReader over the old file is unaffected by the sixth.

    python tools/wiki_terms.py                          # fetch -> analysis/wiki_terms.tsv
    python tools/wiki_terms.py --out D:\\BoFIII\\wiki_terms.tsv
    python tools/wiki_terms.py --diff D:\\BoFIII\\wiki_terms.tsv   # compare, write nothing
    python tools/wiki_terms.py --wikitext page.wiki     # parse a local copy

The page is CC-BY-SA.  The TSV stays a bare TSV (its reader hands the file
straight to csv.DictReader); the attribution goes in a .SOURCE.txt beside it.
"""
import argparse
import csv
import io
import os
import re
import subprocess
import sys

PAGE = "Breath_of_Fire_III_Translations"
URL = "https://bof.fandom.com/wiki/%s?action=raw" % PAGE
UA = "BreathOfFire3Recomp/1.0 (tools/wiki_terms.py)"
CREDIT = ("Breath of Fire Wiki, '%s', CC-BY-SA. https://bof.fandom.com/wiki/%s"
          % (PAGE.replace("_", " "), PAGE))
FIELDS = ["section", "japanese", "romaji", "english_literal", "english_official", "notes"]


# --- wikitext ----------------------------------------------------------------
def fetch(url=URL):
    """Fandom's edge refuses urllib with 403 whatever headers it sends (TLS
    fingerprint, not User-Agent), but answers curl -- which ships with Windows
    10+, git-for-windows and every Linux -- so shell out."""
    try:
        out = subprocess.run(["curl", "-sS", "-f", "-L", "-A", UA, url],
                             capture_output=True, timeout=120)
    except FileNotFoundError:
        sys.exit("curl not found; fetch the page yourself and pass --wikitext:\n  %s" % url)
    if out.returncode != 0:
        sys.exit("fetch failed: %s" % out.stderr.decode("utf-8", "replace").strip())
    return out.stdout.decode("utf-8")


def plain(s):
    """Wikitext -> the text a reader sees."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    # [[ns:target|label]] -> label; [[target]] -> target, minus any namespace
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", lambda m: m.group(1).split(":")[-1], s)
    s = re.sub(r"\[(?:https?|//)\S+\s+([^\]]*)\]", r"\1", s)   # [url label]
    s = re.sub(r"\[(?:https?|//)\S+\]", "", s)                  # bare [url]
    s = s.replace("'''", "").replace("''", "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", s).strip()


def split_cell(line):
    """`|attrs|content` -> (attrs, content).  Only a leading run that looks like
    HTML attributes is taken as attrs; a `|` inside a [[link]] is content."""
    body = line[1:] if line.startswith("|") else line
    i = body.find("|")
    if i == -1:
        return "", body
    head = body[:i]
    if "[[" in head or "[" in head or "=" not in head:
        return "", body
    return head, body[i + 1:]


def map_headers(heads):
    """The page's header row -> one of FIELDS per column.  Positional mapping is
    not safe: the Unused/dummy skills table has four columns, not five, because
    those skills never shipped and so have no Bowne name -- read positionally,
    its literal English lands in `english_official`."""
    out = []
    for h in heads:
        k = h.lower()
        if "japanese" in k:
            out.append("japanese")
        elif "romaji" in k:
            out.append("romaji")
        elif "note" in k:
            out.append("notes")
        elif "(" in h:                      # "English Translation (Bowne Global Solutions)"
            out.append("english_official")
        elif "english" in k:
            out.append("english_literal")
        else:
            out.append(None)
    return out


def parse(text):
    """-> [row dict].  Rows carry the level-3 heading they sit under (the level-2
    one where a section has no subsections)."""
    rows, heading, table = [], None, None
    heads = []
    pending = {}        # column index -> [rows still owed, content] for rowspan
    stats = {"colspan": 0, "rowspan": 0, "banner": 0}

    def flush(cells):
        if not cells or table is None:
            return
        # Replay any rowspan still in flight.  The carried cell is re-inserted
        # without its attributes: carrying the rowspan= with it would make the
        # cell re-register itself every row and leak down the rest of the table.
        full = list(cells)
        for col in sorted(pending):
            left, content = pending[col]
            if left <= 0:
                continue
            full.insert(min(col, len(full)), ("", content))
            pending[col] = [left - 1, content]
            stats["rowspan"] += 1
        cols = map_headers(heads)
        out, col = {}, 0
        for attrs, content in full:
            span = 1
            m = re.search(r"colspan\s*=\s*\"?(\d+)", attrs)
            if m:
                span = int(m.group(1))
                if span >= len(cols):   # a full-width banner ("Overworld"), not a row
                    stats["banner"] += 1
                    return
                stats["colspan"] += 1
            m = re.search(r"rowspan\s*=\s*\"?(\d+)", attrs)
            if m and int(m.group(1)) > 1:
                pending[col] = [int(m.group(1)) - 1, content]
            for k in range(span):                     # a merged cell fills every column it spans
                if col + k < len(cols) and cols[col + k]:
                    out[cols[col + k]] = plain(content)
            col += span
        if not out.get("japanese"):
            return
        rows.append({"section": heading, **{f: out.get(f, "") for f in FIELDS[1:]}})

    cells = []
    for line in text.split("\n"):
        m = re.match(r"^(=+)\s*(.*?)\s*\1\s*$", line)
        if m:
            heading = plain(m.group(2))
            continue
        if line.startswith("{|"):
            table, cells, pending, heads = True, [], {}, []
        elif line.startswith("|}"):
            flush(cells)
            table, cells = None, []
        elif table is None:
            continue
        elif line.startswith("!"):
            heads.append(plain(re.sub(r"^!.*?\|", "", line)))
            continue
        elif line.startswith("|-"):
            flush(cells)
            cells = []
        elif line.startswith("|"):
            cells.append(split_cell(line))
        elif cells:                                   # a cell's continuation line
            attrs, content = cells[-1]
            cells[-1] = (attrs, content + " " + line)
    flush(cells)
    return rows, stats


# --- output ------------------------------------------------------------------
def write_tsv(path, rows):
    """The TSV stays a bare TSV -- Glossary in tools/text_tables.py hands the
    file straight to csv.DictReader, which would read a leading comment line as
    the header -- so the attribution goes in a sidecar beside it."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    side = os.path.splitext(path)[0] + ".SOURCE.txt"
    with open(side, "w", encoding="utf-8", newline="") as f:
        f.write("%s\n\nRetrieved by tools/wiki_terms.py from %s\n" % (CREDIT, URL))
    return side


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(lines)), delimiter="\t"))


def diff(old, new):
    """Old rows keyed by (section, japanese) against the new parse."""
    key = lambda r: (r["section"], r["japanese"])
    o = {key(r): r for r in old}
    n = {key(r): r for r in new}
    changed = []
    for k in sorted(set(o) & set(n)):
        for f in FIELDS[2:5]:
            a, b = (o[k].get(f) or "").strip(), (n[k].get(f) or "").strip()
            if a != b:
                changed.append((k, f, a, b))
    return sorted(set(o) - set(n)), sorted(set(n) - set(o)), changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join("analysis", "wiki_terms.tsv"))
    ap.add_argument("--wikitext", help="parse this local file instead of fetching")
    ap.add_argument("--save-wikitext", help="also write the fetched wikitext here")
    ap.add_argument("--diff", metavar="TSV", help="compare against an existing TSV; write nothing")
    args = ap.parse_args()

    if args.wikitext:
        text = open(args.wikitext, encoding="utf-8").read()
    else:
        text = fetch()
        if args.save_wikitext:
            open(args.save_wikitext, "w", encoding="utf-8").write(text)
    rows, stats = parse(text)
    if not rows:
        sys.exit("no rows parsed -- the page layout changed")

    noted = sum(1 for r in rows if r["notes"])
    print("%d rows, %d sections, %d with notes; %d colspan cells, %d rowspan carries"
          % (len(rows), len({r["section"] for r in rows}), noted,
             stats["colspan"], stats["rowspan"]))
    print("skipped %d full-width banner rows" % stats["banner"])

    if args.diff:
        gone, added, changed = diff(read_tsv(args.diff), rows)
        print("\nvs %s: %d rows only there, %d only here, %d cells changed"
              % (args.diff, len(gone), len(added), len(changed)))
        for sec, jp in gone[:20]:
            print("  only in old: [%s] %s" % (sec, jp))
        for sec, jp in added[:20]:
            print("  only in new: [%s] %s" % (sec, jp))
        for (sec, jp), f, a, b in changed[:40]:
            print("  [%s] %s  %s: %r -> %r" % (sec, jp, f, a[:52], b[:52]))
        if len(changed) > 40:
            print("  ... %d more" % (len(changed) - 40))
        return

    side = write_tsv(args.out, rows)
    print("wrote %s (+ %s)" % (args.out, os.path.basename(side)))


if __name__ == "__main__":
    main()
