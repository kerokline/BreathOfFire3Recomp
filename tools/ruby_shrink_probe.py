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
  bracket  readings inline in brackets, as the retired jp_ruby tables did
  span     `<0f><13>` shrink -6 forever at the head; each reading in
           `<0d>...<0e>` -> drawn through the quad path at 6 px, 6 px advance
  span3    same with `<0f><12>` shrink -3 (9 px), for comparison
  rows     true ruby: per authored row `text <01> <0d>ruby<0e>`, the ruby
           row laid out in half-cells with `--blank` bytes (09 = the gap
           code the plugin's BOF3_RUBY_GAP=9 turns into 6 px of advance);
           run with BOF3_RUBY_ROWY=8,1,29,22 so the plugin places the rows

Markup in --text: `<xx>` hex control bytes; `[reading]` marks a reading run;
everything else is glyphs encoded through names/font.toml and names/kanji.toml.
"""
import argparse
import io
import os
import re
import sys
import time

# The console here is cp1252; the decoded probe line is Japanese.
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

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


def parse_row(row, maps):
    """One authored row -> (text glyph bytes, [(cell, reading glyph bytes)]).
    Every glyph and <xx> control is one cell wide except <01>/<02>, which
    are not allowed inside a row. <ff> (the word separator) counts one cell."""
    kanji = maps[0]
    text = bytearray(); readings = []
    cells = 0; pos = 0; word_start = 0; word_width = 0
    for m in re.finditer(r"<([0-9a-fA-F]{2})>|\[([^\]]+)\]", row):
        chunk = row[pos:m.start()]
        if chunk:
            # A reading annotates the kanji run at the end of the chunk
            # before it (the stem), as the markup is written.
            stem = 0
            while stem < len(chunk) and chunk[-1 - stem] in kanji:
                stem += 1
            text += enc_glyphs(chunk, maps); cells += len(chunk)
            word_start, word_width = cells - stem, stem
        pos = m.end()
        if m.group(1):
            text.append(int(m.group(1), 16)); cells += 1
            word_start, word_width = cells, 0
        else:
            readings.append((word_start, word_width, enc_glyphs(m.group(2), maps)))
    chunk = row[pos:]; text += enc_glyphs(chunk, maps); cells += len(chunk)
    return bytes(text), cells, readings


def ruby_row(cells, readings, blank):
    """Half-cell layout: reading for the word at cell c starts at half-cell
    2c; a reading longer than its word steals a free half-cell on the left
    first. Blanks pad; the row is trimmed to the last reading."""
    half = [None] * (2 * cells + 8)
    for start, width, kana in readings:
        s = 2 * start
        if len(kana) > 2 * width and s > 0 and half[s - 1] is None:
            s -= 1
        for k, b in enumerate(kana):
            half[s + k] = bytes([b])
    while half and half[-1] is None:
        half.pop()
    return b"".join(h if h is not None else blank for h in half)


def build_rows(text, blank):
    """variant rows: <0f><13>, then per authored row: text <01> <0d>ruby<0e>."""
    maps = glyph_maps()
    out = bytearray(b"\x0f\x13")            # shrink -6 forever; ruby rows are spans
    rows = text.split("<01>")
    for i, row in enumerate(rows):
        tb, cells, readings = parse_row(row, maps)
        out += tb + b"\x01\x0d" + ruby_row(cells, readings, blank) + b"\x0e"
        if i + 1 < len(rows):
            out += b"\x01"
    out.append(0)
    return bytes(out)


def build(text, variant, blank=b"\xff"):
    maps = glyph_maps()
    out = bytearray()
    if variant == "rows":
        return build_rows(text, blank)
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
    ap.add_argument("--blank", default="ff",
                    help="rows: hex code of the half-cell blank in a ruby row")
    ap.add_argument("--log", default=None, help="write the runtime's console here")
    a = ap.parse_args()

    msg = build(a.text, a.variant, bytes.fromhex(a.blank))
    print("probe (%d bytes): %s" % (len(msg), msg.hex()))
    print("decodes as:", jptext.decode(msg))
    if a.dry:
        return
    if len(msg) > 0x200:
        raise SystemExit("probe too long for the scratch slot")

    sc = scene.Scene(a.tree, a.port, log=a.log)
    try:
        # Land on the slot and press Circle at once: scene.enter()'s settle
        # and verify take seconds of wall time, and the field state's idle
        # animation can walk the party off the NPC in that window (2026-09-12).
        sc.launch()
        st = sc.load(a.slot)
        if st.get("last_ok") != 1:
            raise SystemExit("savestate load failed: %r" % st)
        # The block must be an area script: the table entry for slot 0 is
        # non-zero and inside the 16 KiB window.
        r = sc.q("read_ram", addr=hex(AREA_BLOCK), len=4)
        head = bytes.fromhex(r["hex"])
        print("area block head:", head.hex())
        t0 = time.time()
        for i, b in enumerate(msg):
            sc.q("write_ram", addr="0x%08X" % (PROBE_AT + i), val="0x%02X" % b)
        for i in range(256):
            sc.q("write_ram", addr="0x%08X" % (AREA_BLOCK + 2 * i), val="0x00")
            sc.q("write_ram", addr="0x%08X" % (AREA_BLOCK + 2 * i + 1), val="0x02")
        back = bytes.fromhex(sc.q("read_ram", addr=hex(PROBE_AT), len=len(msg))["hex"])
        if back != msg:
            raise SystemExit("write-back mismatch: %s" % back.hex())
        print("probe written in %.2fs" % (time.time() - t0))
        sc.press(["circle"], frames=8)
        opened = False
        for _ in range(40):
            time.sleep(0.1)
            if int(sc.q("read_ram", addr="0x80143B90", len=1)["hex"], 16) == 4:
                opened = True
                break
        if not opened:
            raise SystemExit("Circle did not open a message box (mode never became 4)")
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
