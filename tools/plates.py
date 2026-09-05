#!/usr/bin/env python
"""plates.py -- the world-map place-name plates, read off the disc as images.

The names the player sees on the world map are not text: they are painted
name plates baked into each world map's texture page (docs/TEXT_TABLES.md,
"World-map plates").  This tool decodes those pages from the .EMI so the
plates can be read, measured and, later, replaced.

    python tools/plates.py pages  [--out analysis/plates]   # every world map's page + plate band, as PNG
    python tools/plates.py plates [--out analysis/plates]   # plate rectangles (JSON) + a contact sheet

Image section format (established 2026-09-05 by matching AREA033's sections
against the VRAM of a savestate taken on that map):

    dest u32 = (vram_x/32) << 24 | (vram_y/32) << 16 | (bytes/16K) << 8 | flag
    data     = 32x32-halfword tiles, left to right then top to bottom, the
               page being 512 halfwords (= 1024 8-bit texels) wide
    CLUTs    = the section with dest 0x8002BE00: 12 x 256 halfwords, uploaded
               to VRAM rows 483..494 at x = 0; the plates use CLUT 8

Reads the disc through tools/disc_ls.py (or --bin-root); never writes to it.
"""
import argparse
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import text_tables as tt  # noqa: E402
from emi import Emi  # noqa: E402

WORLD_MAPS = [16, 33, 45, 65, 87, 88, 115, 121, 151, 152]
PAGE_DEST = 0x0E001000       # the page that carries the plates on every map checked
CLUT_DEST = 0x8002BE00
PLATE_CLUT = 8
TILE = 32                    # halfwords per tile row, rows per tile
PAGE_W = 512                 # halfwords


def decode_dest(dest):
    return (dest >> 24) * 32, ((dest >> 16) & 0xFF) * 32, ((dest >> 8) & 0xFF) * 16384


def untile(data, width_hw=PAGE_W):
    """Tiled section bytes -> (rows, width_hw) uint16 array."""
    hw = np.frombuffer(data, dtype="<u2")
    tiles_per_row = width_hw // TILE
    ntiles = len(hw) // (TILE * TILE)
    rows = (ntiles // tiles_per_row) * TILE
    out = np.zeros((rows, width_hw), dtype=np.uint16)
    for t in range(ntiles):
        ty, tx = divmod(t, tiles_per_row)
        blk = hw[t * TILE * TILE:(t + 1) * TILE * TILE].reshape(TILE, TILE)
        out[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = blk
    return out


def to_rgb(clut):
    return np.stack([((clut & 0x1F) << 3), (((clut >> 5) & 0x1F) << 3), (((clut >> 10) & 0x1F) << 3)], axis=-1).astype("u1")


def load_map(disc, area):
    path = disc_area_path(disc, area)
    emi = Emi(disc.read(path), path)
    page = [e for e in emi.entries if e["dest"] == PAGE_DEST]
    cl = [e for e in emi.entries if e["dest"] == CLUT_DEST]
    if not page or not cl:
        raise SystemExit("%s: no page %#x / CLUT %#x section" % (path, PAGE_DEST, CLUT_DEST))
    hw = untile(emi.data(page[0]["index"]))
    idx = np.stack([hw & 0xFF, hw >> 8], axis=-1).reshape(hw.shape[0], hw.shape[1] * 2)
    cluts = np.frombuffer(emi.data(cl[0]["index"]), dtype="<u2").reshape(-1, 256)
    return path, idx, cluts


def disc_area_path(disc, area):
    if disc.bin_root:
        import glob
        m = glob.glob(os.path.join(disc.bin_root, "WORLD*", "AREA%03d.EMI" % area))
        if not m:
            raise SystemExit("AREA%03d not under %s" % (area, disc.bin_root))
        return "BIN/" + os.path.relpath(m[0], disc.bin_root).replace(os.sep, "/")
    for key in disc._entries:
        if key.endswith("/AREA%03d.EMI" % area):
            return key
    raise SystemExit("AREA%03d not on the disc" % area)


GRID_INDEX = 5               # the 1-texel outline of an empty plate cell
EDGE = (7, 9, 10, 13)        # the plate's top edge: light rim (9/10), corner (7), shadow (13)
DARK = 11                    # the dark line under the rim
PLATE_H = 14                 # rim, dark, light, 8 text rows, light, dark, shadow


def find_plates(idx, min_w=20):
    """Plate rectangles anywhere on the page.  Plates sit in 16-row bands and
    touch their neighbours, so components merge; instead a plate is found by
    its top edge: a run of rim texels (EDGE) at least min_w long with the dark
    line (DARK) under most of it.  The rectangle is the 14-row body; the
    2-row pointer tail below it is left out."""
    h, w = idx.shape
    rects = []
    for y in range(h - PLATE_H):
        row = np.isin(idx[y], EDGE)
        below = idx[y + 1] == DARK
        x = 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            xe = x
            gap = 0
            while xe < w and gap <= 1:
                if row[xe]:
                    gap = 0
                else:
                    gap += 1
                xe += 1
            xe -= gap
            if xe - x >= min_w and below[x:xe].mean() > 0.6:
                rects.append((max(0, x - 1), y, min(w, xe + 1) - max(0, x - 1), PLATE_H))
            x = xe + 1
    rects.sort(key=lambda r: (r[1], r[0]))
    return rects


def _components(mask):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0, x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            xs, ys = [], []
            while stack:
                y, x = stack.pop()
                xs.append(x)
                ys.append(y)
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append((min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    return out


STRIP_W = 256                # the plate strip wraps at this texel column


def plate_images(idx, rects):
    """(label, texel array) per plate; a plate cut at the strip's right edge
    continues at the start of the next 16-row band (ウールオル街|道), so those
    two pieces are joined and the label carries '+N'."""
    out = []
    for x, y, w, h in rects:
        img = idx[y:y + h, x:x + w]
        label = "%d,%d %dx%d" % (x, y, w, h)
        if x + w >= STRIP_W:
            band = idx[y + 16:y + 16 + h]
            if band.shape[0] == h:
                top = np.isin(band[0], EDGE)
                n = 0
                while n < STRIP_W and (top[n] or (n + 1 < STRIP_W and top[n + 1])):
                    n += 1
                if n:
                    img = np.concatenate([idx[y:y + h, x:STRIP_W], band[:, 0:n + 1]], axis=1)
                    label = "%d,%d %d+%d" % (x, y, STRIP_W - x, n + 1)
        out.append((label, img))
    return out


def best_clut(idx, cluts, rects):
    """Palette with the most luminance contrast between plate fill and text."""
    import collections
    x, y, w, h = rects[0]
    body = idx[y + 3:y + 11, x + 3:x + w - 3]
    c = collections.Counter(body.ravel().tolist())
    fill = c.most_common(1)[0][0]
    text = [i for i, _ in c.most_common(6) if i != fill][:3]

    def lum(v):
        return 0.3 * ((v & 31) << 3) + 0.59 * (((v >> 5) & 31) << 3) + 0.11 * (((v >> 10) & 31) << 3)
    return max(range(len(cluts)), key=lambda k: abs(lum(int(cluts[k][fill])) - np.mean([lum(int(cluts[k][t])) for t in text])))


# A synthetic palette for READING plates: fill indices light, stroke indices
# dark, rim mid-grey.  Not what the game draws; use --clut N for a real CLUT.
READ_CLUT = np.zeros(256, dtype=np.uint16)
for _i in range(256):
    _g = 31 if _i in (1, 2, 3, 4, 5) else 20 if _i in (7, 9, 10, 13, 6) else 8 if _i == 11 else 0 if _i in (12, 14, 15) else 12
    READ_CLUT[_i] = _g | (_g << 5) | (_g << 10)
READ_CLUT[0] = 0


def pick_palette(args, idx, cluts, rects):
    """-> (label, clut halfwords)"""
    if args.clut == "read":
        return "read", READ_CLUT
    if args.clut == "auto":
        k = best_clut(idx, cluts, rects) if rects else PLATE_CLUT
        return str(k), cluts[k]
    return args.clut, cluts[int(args.clut)]


def cmd_pages(args, disc):
    os.makedirs(args.out, exist_ok=True)
    for area in args.areas:
        path, idx, cluts = load_map(disc, area)
        rects = find_plates(idx)
        rgb = to_rgb(pick_palette(args, idx, cluts, rects)[1])[idx]
        Image.fromarray(rgb).save(os.path.join(args.out, "AREA%03d_page.png" % area))
        if rects:
            y0 = min(r[1] for r in rects) - 2
            y1 = max(r[1] + r[3] for r in rects) + 2
            band = rgb[max(0, y0):y1, 0:256]
            Image.fromarray(band).resize((256 * 4, band.shape[0] * 4), Image.NEAREST).save(os.path.join(args.out, "AREA%03d_plates.png" % area))
        print("AREA%03d %s: page %dx%d, %d CLUTs -> %s" % (area, path, idx.shape[1], idx.shape[0], len(cluts), args.out))
    return 0


def cmd_plates(args, disc):
    os.makedirs(args.out, exist_ok=True)
    report = {}
    strips = []
    for area in args.areas:
        path, idx, cluts = load_map(disc, area)
        rects = find_plates(idx)
        clut, pal = pick_palette(args, idx, cluts, rects)
        rgb = to_rgb(pal)
        imgs = plate_images(idx, rects)
        report["AREA%03d" % area] = {"file": path, "page_dest": "0x%08X" % PAGE_DEST, "render_clut": clut,
                                     "plates": [{"x": x, "y": y, "w": w, "h": h, "span": lab.split(" ")[1]}
                                                for (x, y, w, h), (lab, _) in zip(rects, imgs)]}
        print("AREA%03d: %d plates (render CLUT %s)  %s" % (area, len(rects), clut, " ".join(lab.split(" ")[1] for lab, _ in imgs)))
        for lab, img in imgs:
            strips.append(("AREA%03d %s" % (area, lab), rgb[img]))
    with open(os.path.join(args.out, "plates.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    # contact sheet: one block per map, four plates per row, 3x zoom
    z, per_row = 3, 4
    blocks = []
    for area in args.areas:
        ps = [(lab, img) for lab, img in strips if lab.startswith("AREA%03d " % area)]
        rows = (len(ps) + per_row - 1) // per_row
        im = Image.new("RGB", (per_row * (80 * z + 6), 16 + rows * (14 * z + 16)), (30, 30, 30))
        d = ImageDraw.Draw(im)
        d.text((2, 2), "AREA%03d  %d plates" % (area, len(ps)), fill=(255, 255, 0))
        for k, (lab, img) in enumerate(ps):
            r, c = divmod(k, per_row)
            x, y = c * (80 * z + 6), 16 + r * (14 * z + 16)
            im.paste(Image.fromarray(img).resize((img.shape[1] * z, img.shape[0] * z), Image.NEAREST), (x, y + 12))
            d.text((x, y), lab.split(" ", 1)[1], fill=(180, 180, 255))
        blocks.append(im)
    sheet = Image.new("RGB", (max(b.width for b in blocks), sum(b.height for b in blocks)), (30, 30, 30))
    y = 0
    for b in blocks:
        sheet.paste(b, (0, y))
        y += b.height
    sheet.save(os.path.join(args.out, "plates_sheet.png"))
    print("wrote", os.path.join(args.out, "plates.json"), "and plates_sheet.png (%d plates)" % len(strips))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cue", default=tt.default_cue())
    ap.add_argument("--bin-root")
    ap.add_argument("--out", default=os.path.join(tt.ROOT, "analysis", "plates"))
    ap.add_argument("--clut", default="read", help="CLUT index to render with, auto (max text contrast), or read (synthetic, for transcribing)")
    ap.add_argument("--areas", type=int, nargs="*", default=WORLD_MAPS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pages").set_defaults(fn=cmd_pages)
    sub.add_parser("plates").set_defaults(fn=cmd_plates)
    args = ap.parse_args(argv)
    disc = tt.Disc(cue=args.cue, bin_root=args.bin_root)
    return args.fn(args, disc)


if __name__ == "__main__":
    sys.exit(main())
