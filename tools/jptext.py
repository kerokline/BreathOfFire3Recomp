#!/usr/bin/env python
r"""jptext.py -- the JP text encoding, from the in-tree tables.

    kana   0x5B-0xFC  gojuon order: 46 hiragana, 9 small, 25 dakuten, then the
                      same three groups in katakana from 0xAB; 0xFC = ー
    kanji  0x12xx / 0x13xx (two bytes)  names/kanji.toml
    0x15 nn           the symbol page     names/font.toml [page15]
    everything below 0x5B is a control code or a single-byte glyph
                      (names/font.toml [single]; docs/TEXT_ENGINE.md)

This replaces the prior decode work's `decode_text.py` (D:\BoFIII), which
the tools imported by path; the kanji table now lives in the repo so a
correction is a reviewed diff (names/kanji.toml carries them as comments).
`decode()` keeps that module's output shape -- kana and kanji as text,
anything else as `<hh>` -- because review files and the census compare
against it.
"""
import os
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

HIRA = list("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん")
SMALL = list("ぁぃぅぇぉっゃゅょ")
DAKU = list("がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ")
assert (len(HIRA), len(SMALL), len(DAKU)) == (46, 9, 25)


def _kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)


KANA = {}
_b = 0x5B
for _ch in HIRA + SMALL + DAKU:
    KANA[_b] = _ch
    _b += 1
assert _b == 0xAB
for _ch in _kata("".join(HIRA + SMALL + DAKU)):
    KANA[_b] = _ch
    _b += 1
KANA[0xFC] = "ー"


def _load(name):
    with open(os.path.join(ROOT, "names", name), "rb") as f:
        return tomllib.load(f)


KANJI = dict(_load("kanji.toml")["kanji"])            # "12xx"/"13xx" hex string -> char
_font = _load("font.toml")
SINGLE = {int(k, 16): v for k, v in _font["single"].items()}
PAGE15 = {int(k, 16): v for k, v in _font["page15"].items()}
KANJI_LAST = max(int(k, 16) for k in KANJI)


def decode(d):
    """Bytes -> text: kana and kanji as characters, everything else `<hh>`."""
    out, i = [], 0
    while i < len(d):
        b = d[i]
        if b in (0x12, 0x13) and i + 1 < len(d):
            c = "%02x%02x" % (b, d[i + 1])
            if 0x1200 <= int(c, 16) <= KANJI_LAST:
                out.append(KANJI.get(c, "[" + c + "]"))
                i += 2
                continue
        if b in KANA:
            out.append(KANA[b])
            i += 1
            continue
        out.append("<%02x>" % b)
        i += 1
    return "".join(out)


if __name__ == "__main__":
    import sys
    print("%d kanji codes (last %04x), %d kana, %d single, %d page15"
          % (len(KANJI), KANJI_LAST, len(KANA), len(SINGLE), len(PAGE15)))
    for arg in sys.argv[1:]:
        print(arg, "->", decode(bytes.fromhex(arg)))
