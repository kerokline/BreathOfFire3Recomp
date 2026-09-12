#!/usr/bin/env python
"""Put a synthetic message with shrunk-span readings on screen, headless.

The question (docs/FURIGANA.md, 2026-09-12): the box's scalable quad path
draws a glyph at 12 + P px AND advances the cursor by 12 + P, so a reading
wrapped in an emphasis span while a shrink preset is active should come out
as half-size kana with half advance, no plugin change. This script shows it.

    python tools/ruby_shrink_probe.py --slot 0 --variant span   --shot span.png
    python tools/ruby_shrink_probe.py --slot 0 --variant plain  --shot plain.png
    python tools/ruby_shrink_probe.py --slot 0 --variant bracket --shot bracket.png

`--slot` must be a field savestate where Circle opens an AREA-script message
(a talkable NPC or sign in front of the party). The script writes the test
bytes over message 0 of the loaded area block and points every one of the
256 offset-table entries at it, so whatever Circle opens shows the probe.
Nothing on disk is touched; the state is not re-saved.

Variants:
  plain    the sentence with no readings (baseline for row height / spacing)
  bracket  readings inline in brackets, as the shipped jp_ruby tables do
  span     `<0f><13>` shrink -6 forever at the head; each reading in
           `<0d>...<0e>` -> drawn through the quad path at 6 px, 6 px advance
  span3    same with `<0f><12>` shrink -3 (9 px), for comparison

Markup in --text: `<xx>` hex control bytes; `[reading]` marks a reading run;
everything else is glyphs encoded through names/font.toml and names/kanji.toml.
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jptext
import scene

AREA_BLOCK = 0x80010000
PROBE_AT = AREA_BLOCK + 0x200           # just past the 256-entry u16 table

DEFAULT_TEXT = "村[むら]の人[ひと]は<ff>夜[よる]の<01>砂漠[さばく]へ<ff>出[で]かけた"


def glyph_maps():
    kanji = {ch: bytes.fromhex(h) for h, ch in jptext.KANJI.items()}
    kana = {}
    for code, ch in jptext.KANA.items():
        kana.setdefault(ch, bytes([code]))
    single = {}
    for code, ch in jptext.SINGLE.items():
        single.setdefault(ch, bytes([code]))
    return kanji, kana, single


def enc_glyphs(s, maps):
    kanji, kana, single = maps
    out = bytearray()
    for ch in s:
        b = kanji.get(ch) or kana.get(ch) or single.get(ch)
        if b is None:
            raise SystemExit("no glyph code for %r" % ch)
        out += b
    return bytes(out)


def build(text, variant):
    maps = glyph_maps()
    out = bytearray()
    if variant == "span":
        out += b"\x0f\x13"                  # preset 19: type 3 shrink, P = -6, forever
    elif variant == "span3":
        out += b"\x0f\x12"                  # preset 18: type 3 shrink, P = -3, forever
    elif variant not in ("plain", "bracket"):
        raise SystemExit("unknown variant %s" % variant)
    pos = 0
    for m in re.finditer(r"<([0-9a-fA-F]{2})>|\[([^\]]+)\]", text):
        out += enc_glyphs(text[pos:m.start()], maps)
        pos = m.end()
        if m.group(1):
            out.append(int(m.group(1), 16))
            continue
        reading = enc_glyphs(m.group(2), maps)
        if variant == "plain":
            continue
        if variant == "bracket":
            out += b"\x28" + reading + b"\x29"
        else:
            out += b"\x0d" + reading + b"\x0e"
    out += enc_glyphs(text[pos:], maps)
    out.append(0)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, required=True)
    ap.add_argument("--variant", default="span")
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--shot", default=None)
    ap.add_argument("--reveal-frames", type=int, default=150,
                    help="frames to wait after Circle so the typewriter finishes")
    ap.add_argument("--tree", default=scene.DEFAULT_TREE)
    ap.add_argument("--port", type=int, default=scene.DEFAULT_PORT)
    ap.add_argument("--dry", action="store_true", help="print the bytes and exit")
    a = ap.parse_args()

    msg = build(a.text, a.variant)
    print("probe (%d bytes): %s" % (len(msg), msg.hex()))
    print("decodes as:", jptext.decode(msg))
    if a.dry:
        return
    if len(msg) > 0x200:
        raise SystemExit("probe too long for the scratch slot")

    sc = scene.Scene(a.tree, a.port)
    try:
        sc.enter(a.slot)
        # The block must be an area script: the table entry for slot 0 is
        # non-zero and inside the 16 KiB window.
        r = sc.q("read_ram", addr=hex(AREA_BLOCK), len=4)
        head = bytes.fromhex(r["hex"])
        print("area block head:", head.hex())
        for i, b in enumerate(msg):
            sc.q("write_ram", addr="0x%08X" % (PROBE_AT + i), val="0x%02X" % b)
        for i in range(256):
            sc.q("write_ram", addr="0x%08X" % (AREA_BLOCK + 2 * i), val="0x00")
            sc.q("write_ram", addr="0x%08X" % (AREA_BLOCK + 2 * i + 1), val="0x02")
        back = bytes.fromhex(sc.q("read_ram", addr=hex(PROBE_AT), len=len(msg))["hex"])
        if back != msg:
            raise SystemExit("write-back mismatch: %s" % back.hex())
        sc.press(["circle"])
        sc.wait_frames(a.reveal_frames)
        if a.shot:
            shot = a.shot if os.path.isabs(a.shot) else os.path.join(os.getcwd(), a.shot)
            before = os.path.getmtime(shot) if os.path.exists(shot) else 0
            reply = sc.q("screenshot", path=shot)
            deadline = time.time() + 10.0
            while time.time() < deadline:
                if os.path.exists(shot) and os.path.getmtime(shot) > before:
                    break
                time.sleep(0.25)
            else:
                raise SystemExit("screenshot never appeared at %s (%s)" % (shot, reply))
            print("wrote", shot)
        # What the renderer is holding: flags, P, cursor, origin.
        st = bytes.fromhex(sc.q("read_ram", addr="0x8014909C", len=0x30)["hex"])
        print("flags 0x801490A0 = %04x  P 0x801490C4 = %d  origin (%d,%d)" % (
            int.from_bytes(st[4:6], "little"),
            int.from_bytes(st[0x28:0x2A], "little", signed=True),
            int.from_bytes(st[0x20:0x22], "little"), int.from_bytes(st[0x22:0x24], "little")))
    finally:
        sc.quit()


if __name__ == "__main__":
    main()
