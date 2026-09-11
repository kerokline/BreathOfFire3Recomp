"""Substitution audit for names/kanji.toml: for each kanji cell, take its script
contexts, substitute every common kanji into the cell's position and score how
well each candidate tokenizes (fewer tokens, no OOV, single-kanji tokens not
left dangling). Cells where some other kanji beats the label are suspects.

Result 2026-09-10 (run after the eight corrections): 80 cells ranked, ALL
noise -- the top rows are proper nouns and game vocabulary (ウルカン族,
烈火の闘場, 竜, 塔, 俺) where a dictionary surname or a commoner word scores
better, and every mid-list context read correctly by hand. The slips that were
found (賃/代, 探/冒, 泉/春, 奥/下, 凶/邪, 究/験, 研/実, 飛/忍) came from
reading lines in play and from the proof page (tools/font_sheet.py kanji),
not from this. Kept so nobody rebuilds it.

    python tools/kanji_subst_audit.py > analysis/kanji_subst_audit.txt   # ~4 min
"""
import sys, os, re, struct, collections, random, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools")); os.chdir(ROOT)
import build_ruby_script as b, ruby_fit, jptext
from text_tables import Disc
random.seed(1)
tok, mode = ruby_fit.tokenizer("full")
# candidate kanji: every CJK char in the SudachiDict system dictionary (UTF-16LE strings inside)
import sudachipy, glob
dic = None
for pat in (os.path.join(os.path.dirname(sudachipy.__file__), "resources", "system.dic"),
            os.path.join(sys.prefix, "Lib", "site-packages", "sudachidict_full", "resources", "system.dic"),
            os.path.join(sys.prefix, "Lib", "site-packages", "sudachidict_core", "resources", "system.dic")):
    if os.path.exists(pat): dic = pat; break
if not dic:
    hits = glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "sudachidict_*", "resources", "system.dic"))
    dic = hits[0] if hits else None
print("dic", dic, flush=True)
raw = open(dic, "rb").read()
cnt = collections.Counter()
for enc in ("utf-16-le", "utf-8"):
    txt = raw.decode(enc, errors="ignore")
    cnt.update(re.findall(r"[\u4e00-\u9fff]", txt))
cands = [k for k, _ in cnt.most_common(2600)]
print("candidates", len(cands), flush=True)
disc = Disc(cue=None, bin_root=r"D:\BoFIII\BIN")
single, page15, kd = b.load_maps()[1:]
texts = []
for path, data, base, slots in b.message_blocks(disc):
    for m in slots:
        off = base + struct.unpack_from("<H", data, base + 2 * m)[0]; ln = b.message_extent(data, off)
        if not ln: continue
        t = b.decode_jp(data[off:off + ln], single, page15)
        texts.append(re.sub(r"<[0-9a-f]{2,4}>|⏎|/", " ", t))
JP = r"[\u3040-\u30ff\u4e00-\u9fff々ー]"
ctx = collections.defaultdict(list)
for t in texts:
    for run in re.findall(JP + "+", t):
        for i, ch in enumerate(run):
            if "\u4e00" <= ch <= "\u9fff":
                ctx[ch].append((run[max(0, i - 5):i], run[i + 1:i + 6]))
def score(seq):
    toks = list(tok.tokenize(seq, mode))
    s = len(toks)
    for i, tk in enumerate(toks):
        if tk.is_oov(): s += 3
        sf = tk.surface()
        if len(sf) == 1 and "\u4e00" <= sf <= "\u9fff":
            s += 1                                   # a dangling single kanji
    return s
codes = list(range(0x1200, jptext.KANJI_LAST + 1))
t0 = time.time(); out = []
for n, code in enumerate(codes):
    label = jptext.KANJI["%04x" % code]
    cs = ctx.get(label, [])
    if len(cs) < 3: continue
    cs = list(dict.fromkeys(cs)); random.shuffle(cs)
    quick, full = cs[:6], cs[:24]
    def total(k, cc): return sum(score(a + k + z) for a, z in cc)
    pre = sorted(cands, key=lambda k: total(k, quick))[:40]
    if label not in pre: pre.append(label)
    fin = sorted(pre, key=lambda k: total(k, full))
    ls, bs = total(label, full), total(fin[0], full)
    if fin[0] != label and bs < ls:
        out.append((ls - bs, code, label, fin[:4], ls, bs, len(full)))
    if n % 40 == 0: print("  %d/%d  %.0fs" % (n, len(codes), time.time() - t0), flush=True)
out.sort(reverse=True)
print("cells where another kanji tokenizes better than the label (margin, code, label, top candidates, label score, best score, contexts):")
for row in out: print("  %3d  %04x %s -> %s  (%d vs %d over %d)" % row)
