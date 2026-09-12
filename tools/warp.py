#!/usr/bin/env python
"""Warp harness: visit AREA overlays headlessly, without playing there.

The field engine's map transition is one function, `Field_ChangeArea`
(GAME.EMI 0x801A0A30, docs/loader_records/AREA.md section 4): it stashes the
destination in four cells and sets the game mode to 5, and the mode-5 handler
(0x801981E8) reads them back and calls the area loader `FUN_801a0aa8`, which
issues `File_LoadRequest(area + 0x2AB)`, spins on File_LoadDone, and enters
the new image through its descriptor. Nothing checks where the request came
from, so writing the same cells over the debug port from ANY field state is a
warp:

    u16 0x80143F10   pending area number
    u32 0x80143F14   pending x/z (16.16, high half = tile)
    u32 0x80143F18   pending y
    u8  0x80143F1C   pending flags (bit 0x80 = special entry; 0 here)
    u8  0x80143F1D   transition kind (1 normal; Field_ChangeArea derives it)
    u8  0x80143BB0   mode REQUEST := 5 (consumed by the advance FUN_80198378)

The active mode lives in u8 0x80143B90 and is what the advance drives; values
seen 2026-09-12: 2 = field walk (real play and the attract demo alike),
4 = message box / menu, 5 = battle, 8 = world map. Only warp from a field
mode, only write the request cell, never the active cell (a raw poke into a
mid-transition state desyncs the pair and the loader never runs again).

Proven 2026-09-12: a single poke worked from the attract demo, but the demo's
own scenario script (SCENA16) keeps re-issuing transitions and later warps
lose the race, so the harness needs a real in-game field state -- anchor one
with a savestate (`--slot`). From that anchor: 200/200 areas in 512 s, nine
anchor reloads for random battles the walk step tripped, zero failures.

Why: the Axis B harvest needs the game to *enter* an area's interior entry
points, and after the loader-record seeding (docs/LOADER_RECORDS.md) the
question per area is only "does anything still interpret here". Playing to
each of 200 areas is weeks; warping is seconds. The party may stand off-map
and story flags will be wrong, which does not matter for the harvest -- the
overlay loads, its init runs, its entity handlers run.

    python tools/warp.py --boot --areas 0-199 --harvest          # cold: boot, Start, warp every area
    python tools/warp.py --port 4392 --areas 10,11,150 --walk    # attach to a running headless game
    python tools/warp.py --boot --areas 0-199 --shots analysis/warp_shots

Each visit records the resident set (tools/resident.py) and whether the load
completed. `--harvest` unions the session's entered PCs into the observed file
under one session id and prints the seed gap: entered interior PCs that no
static seed (header / JAL / prologue / loader record) already covers -- the
number that should be near zero if the records are complete.
"""
import argparse
import datetime as dt
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps            # noqa: E402
import resident                     # noqa: E402
from callstack_diff import button_mask   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES = os.path.join(ROOT, "analysis", "overlay_captures_all.json")

PENDING_AREA = 0x80143F10
PENDING_XZ = 0x80143F14
PENDING_Y = 0x80143F18
PENDING_FLAGS = 0x80143F1C
TRANSITION_KIND = 0x80143F1D
MODE_REQUEST = 0x80143BB0        # Field_ChangeArea sets this to 5
ACTIVE_MODE = 0x80143B90         # FUN_80198378 drives this; 2 = field walk (real play and the demo alike)
FIELD_MODES = (1, 2)
AREA_NUMBER = 0x80143F00
LOADER_STATE = 0x80146490          # 3 = File_LoadDone
VSYNC = 0x8018603C
GAME_BAND = 0x80196800
AREA_BAND = 0x801F2C00
WORLD_MAP_AREAS = (30, 89, 129)


class Guest:
    def __init__(self, port):
        self.port = port

    def q(self, cmd, **kw):
        return ps.send(dict(cmd=cmd, **kw), port=self.port, timeout=30.0)

    def rd(self, addr, n):
        return bytes.fromhex(self.q("read_ram", addr="0x%08X" % addr, len=n)["hex"])

    def u8(self, a):
        return self.rd(a, 1)[0]

    def u16(self, a):
        return struct.unpack("<H", self.rd(a, 2))[0]

    def u32(self, a):
        return struct.unpack("<I", self.rd(a, 4))[0]

    def wr(self, addr, data):
        for i, b in enumerate(data):
            r = self.q("write_ram", addr="0x%08X" % (addr + i), val="0x%02X" % b)
            if not r.get("ok"):
                raise SystemExit("write_ram %#x failed: %s" % (addr + i, r))

    def vsync(self):
        return self.u32(VSYNC)

    def wait_frames(self, n, timeout=None):
        target = self.vsync() + n
        deadline = time.time() + (timeout or max(10.0, n / 20.0 + 5.0))
        while time.time() < deadline:
            if self.vsync() >= target:
                return True
            time.sleep(0.03)
        return False

    def press(self, spec, frames=4):
        self.q("press", buttons=0xFFFF & ~button_mask(spec), frames=frames)

    def resident(self):
        r = resident.resident_ids(self.port)
        return r

    def game_resident(self):
        r = self.resident()
        b = r["bands"].get("0x%08X" % GAME_BAND) or r["bands"].get(GAME_BAND)
        return bool(b and b.get("id") is not None and not b.get("wrong_band"))


def band_entry(r, base):
    for k, v in r["bands"].items():
        kb = int(k, 16) if isinstance(k, str) else k
        if kb == base:
            return v
    return None


def ensure_field(g, say, timeout=90.0):
    """Get to a field state with GAME.EMI resident. From the title the attract
    demo is one Start away and is a real field scene."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if g.game_resident():
            return True
        say("  no field state (GAME.EMI not resident) -- pressing Start")
        g.press("start", 6)
        g.wait_frames(300, timeout=30)
    return False


def pc_snapshot(g):
    """{phys pc: (entries, insns)} for every interpreted PC with entries > 0."""
    d = g.q("dirty_ram_stats")
    out = {}
    for row in d.get("per_pc") or []:
        if row.get("entries", 0) > 0:
            out["0x%08X" % (int(row["pc"], 16) & 0x1FFFFFFF)] = (row["entries"], row.get("insns", 0))
    return out


def warp(g, area, say, xz=None, y=None, dwell=240, walk=False, timeout=25.0, snap=None):
    """One transition. Returns a result dict."""
    res = {"area": area, "ok": False}
    if not ensure_field(g, say):
        res["why"] = "no field state"
        return res
    # Warp only from a settled field-walk state (active mode 1). A raw poke into
    # a mid-transition state desyncs the two-cell handshake (mode request vs
    # active mode) and wedges the loader; wait for the game to be walking first.
    t_settle = time.time() + 8.0
    while g.u8(ACTIVE_MODE) not in FIELD_MODES and time.time() < t_settle:
        time.sleep(0.1)
    if g.u8(ACTIVE_MODE) not in FIELD_MODES:
        res["why"] = "active mode %d never settled to field-walk" % g.u8(ACTIVE_MODE)
        return res
    v0 = g.vsync()
    g.wr(PENDING_AREA, struct.pack("<H", area))
    if xz is not None:
        g.wr(PENDING_XZ, struct.pack("<I", xz))
    if y is not None:
        g.wr(PENDING_Y, struct.pack("<I", y))
    g.wr(PENDING_FLAGS, b"\x00")
    g.wr(TRANSITION_KIND, b"\x01")
    # Request the transition the way Field_ChangeArea does: set the REQUEST cell
    # and let the per-frame advance FUN_80198378 run the load. Never touch the
    # active-mode cell -- that is what desyncs it.
    g.wr(MODE_REQUEST, b"\x05")
    deadline = time.time() + timeout
    loaded = False
    while time.time() < deadline:
        time.sleep(0.1)
        # The area number changes only inside the loader, after File_LoadDone.
        if g.u16(AREA_NUMBER) == area and g.u8(LOADER_STATE) == 3:
            loaded = True
            break
    v1 = g.vsync()
    res["frames_to_load"] = v1 - v0
    if not loaded:
        res["why"] = "load did not complete (area=%d loader=%d req=%d active=%d, vsync %s)" % (
            g.u16(AREA_NUMBER), g.u8(LOADER_STATE), g.u8(MODE_REQUEST), g.u8(ACTIVE_MODE),
            "advancing" if v1 > v0 else "STUCK")
        return res
    # Let the init handler and the entity handlers run.
    if not g.wait_frames(dwell, timeout=dwell / 10.0 + 10):
        res["why"] = "guest stopped advancing after the load"
        return res
    if walk:
        # Directions only. A Circle press here opened a message/menu (active
        # mode 4) on the 2026-09-12 full sweep and every later warp waited on
        # it; talking is not needed to run the entity handlers.
        for d in ("up", "right", "down", "left"):
            g.press(d, 16)
            g.wait_frames(24)
        # If walking tripped a message or menu anyway, back out of it.
        for _ in range(6):
            if g.u8(ACTIVE_MODE) in FIELD_MODES:
                break
            g.press("cross", 4)
            g.wait_frames(20)
            g.press("circle", 4)
            g.wait_frames(20)
        res["mode_after_walk"] = g.u8(ACTIVE_MODE)
        if res["mode_after_walk"] == 5:
            res["battle_triggered"] = True     # mode 5 = battle (area 10, 2026-09-12)
    r = g.resident()
    res["resident"] = resident.format_resident(r)
    if snap is not None:
        # Per-area attribution: the dirty-PC rows whose entry count grew while
        # this area was resident. dirty_ram_stats is read-only on the runtime.
        cur = pc_snapshot(g)
        grew = []
        for pc, (e, i) in cur.items():
            e0, i0 = snap.get(pc, (0, 0))
            if e > e0:
                grew.append({"pc": pc, "entries": e - e0, "insns": i - i0})
        grew.sort(key=lambda x: -x["insns"])
        res["entered_pcs"] = grew
        snap.clear(); snap.update(cur)
    e = band_entry(r, AREA_BAND)
    res["area_band"] = (e or {}).get("name") or (e or {}).get("id")
    res["ok"] = True
    return res


def seed_sets(captures_path=CAPTURES):
    """{band: {phys pc}} of everything already seeded statically, and of the
    observed-only dispatch entries, so a harvested PC can be classified."""
    caps = json.load(open(captures_path))
    static, observed = {}, {}
    for c in caps:
        lo = int(c["load_addr"], 16) & 0x1FFFFFFF
        s = set()
        for k in ("header_entry_pcs", "static_discovery_entry_pcs",
                  "static_dispatch_entry_pcs", "engine_entry_pcs"):
            s |= {int(x, 16) & 0x1FFFFFFF for x in c.get(k, [])}
        static.setdefault(lo, set()).update(s)
        observed.setdefault(lo, set()).update(
            {int(x, 16) & 0x1FFFFFFF for x in c.get("dispatch_entry_pcs", [])} - s)
    return static, observed


def seed_gap(g, say):
    """Classify every entered interpreted PC against the static seeds."""
    d = g.q("dirty_ram_stats")
    if not d.get("ok"):
        raise SystemExit("dirty_ram_stats failed: %s" % d)
    static, observed = seed_sets()
    bands = sorted(static)
    out = {"static_seeded": [], "observed_only": [], "unseeded": [], "outside_bands": []}
    for row in d.get("per_pc") or []:
        if row.get("entries", 0) <= 0:
            continue
        pc = int(row["pc"], 16) & 0x1FFFFFFF
        band = None
        for b in bands:
            if b <= pc < b + 0x40000:
                band = b       # nearest band base below (bands do not nest)
        if band is None:
            out["outside_bands"].append(row); continue
        if pc in static[band]:
            out["static_seeded"].append(row)
        elif pc in observed[band]:
            out["observed_only"].append(row)
        else:
            out["unseeded"].append(row)
    say("seed gap    : %d entered interior PCs in overlay bands -- %d statically seeded "
        "(seed present but still interpreted: occupant mismatch or dropped by the compile), "
        "%d observed-only, %d UNSEEDED (new to everything), %d outside the bands"
        % (sum(len(v) for k, v in out.items() if k != "outside_bands"),
           len(out["static_seeded"]), len(out["observed_only"]), len(out["unseeded"]),
           len(out["outside_bands"])))
    top = sorted(out["unseeded"], key=lambda r: -r.get("insns", 0))[:15]
    for r in top:
        say("    unseeded %s entries %s insns %s" % (r["pc"], r.get("entries"), r.get("insns")))
    return out


def parse_areas(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out += list(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=4392)
    ap.add_argument("--boot", action="store_true",
                    help="launch build-relprof headless with the disc on --port first (else attach)")
    ap.add_argument("--tree", default="build-relprof")
    ap.add_argument("--areas", default="0-199", help='e.g. "0-19,150" (default all 200)')
    ap.add_argument("--skip-world-map", action="store_true",
                    help="skip areas 30/89/129 (world map; different descriptor type)")
    ap.add_argument("--dwell", type=int, default=240, help="frames to sit in each area")
    ap.add_argument("--walk", action="store_true", help="press each direction, Circle and Cross in each area")
    ap.add_argument("--xz", default=None, help="pending x/z word (hex) to write; default keep the previous")
    ap.add_argument("--y", default=None, help="pending y word (hex)")
    ap.add_argument("--shots", default=None, help="directory for one PNG per area")
    ap.add_argument("--harvest", action="store_true",
                    help="union entered PCs into analysis/observed_interp_pcs.json and print the seed gap")
    ap.add_argument("--no-save", action="store_true", help="with --harvest: seed gap only, no union")
    ap.add_argument("--out", default=None, help="results JSON (default analysis/warp_<ts>.json)")
    ap.add_argument("--quit", action="store_true", help="quit the runtime at the end (implied by --boot)")
    ap.add_argument("--attribute", action="store_true",
                    help="snapshot dirty-PC entries after every area and record which PCs "
                         "were entered while it was resident (entered_pcs per result)")
    ap.add_argument("--slot", type=int, default=None,
                    help="with --boot: load this savestate FILE number after boot instead of the "
                         "attract demo. Warp needs a real field-walk state (active mode 1); the "
                         "attract demo runs its own autopilot (mode 2) and cannot be warped. "
                         "Anchor one: park an in-game save in any field area, then save a slot.")
    a = ap.parse_args()

    os.chdir(ROOT)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = a.out or os.path.join("analysis", "warp_%s.json" % ts)

    def say(m):
        print(m, flush=True)

    sc = None
    if a.boot:
        import scene
        sc = scene.Scene(tree=a.tree, port=a.port, disc=True,
                         log=os.path.join("analysis", "warp_%s.log" % ts))
        if a.slot is not None:
            sc.enter(a.slot)          # launch + load savestate + verify resumed
        else:
            sc.launch()
    g = Guest(a.port)
    if a.slot is None and not ensure_field(g, say, timeout=120):
        raise SystemExit("could not reach a field state (title + Start should start the attract demo)")
    if g.u8(ACTIVE_MODE) not in FIELD_MODES:
        say("WARNING: active mode is %d, not a field mode. If this is the attract demo the "
            "sweep will fail; anchor a real in-game field save and pass --slot." % g.u8(ACTIVE_MODE))

    areas = parse_areas(a.areas)
    if a.skip_world_map:
        areas = [n for n in areas if n not in WORLD_MAP_AREAS]
    xz = int(a.xz, 16) if a.xz else None
    y = int(a.y, 16) if a.y else None
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)

    def reload_anchor():
        """Put the guest back on the anchor savestate. A walk can start a random
        battle (active mode 5) or a cutscene the harness cannot finish; the
        anchor is the known-good field state, and a restore is milliseconds."""
        if a.slot is None:
            return False
        g.q("savestate", slot=a.slot, op="load")
        dl = time.time() + 45
        while time.time() < dl:
            st = g.q("savestate_status")
            if st.get("pending") == 0 and st.get("last_op") == "load":
                break
            time.sleep(0.3)
        v0 = g.vsync(); time.sleep(1.0)
        ok = g.vsync() > v0 and st.get("last_ok") == 1
        say("  reloaded anchor slot %d: %s" % (a.slot, "ok" if ok else "FAILED %s" % st))
        return ok

    results = []
    t0 = time.time()
    reloads = 0
    snap = pc_snapshot(g) if a.attribute else None
    for n in areas:
        r = warp(g, n, say, xz=xz, y=y, dwell=a.dwell, walk=a.walk, snap=snap)
        if not r["ok"] and a.slot is not None and "STUCK" not in r.get("why", ""):
            say("area %3d  first try: %s" % (n, r.get("why")))
            if reload_anchor():
                reloads += 1
                r = warp(g, n, say, xz=xz, y=y, dwell=a.dwell, walk=a.walk, snap=snap)
                r["retried_after_reload"] = True
        if r["ok"] and a.shots:
            path = os.path.abspath(os.path.join(a.shots, "area%03d.png" % n))
            g.q("screenshot", path=path)
            r["shot"] = path
        say("area %3d  %s  %s" % (n, "ok " if r["ok"] else "FAIL",
                                  r.get("resident") or r.get("why")))
        results.append(r)
        if not r["ok"] and "STUCK" in r.get("why", ""):
            say("guest wedged; stopping the sweep here")
            break
    say("%d/%d areas loaded in %.0f s (%d anchor reloads)"
        % (sum(1 for r in results if r["ok"]), len(results), time.time() - t0, reloads))

    report = {"schema": "warp-v1", "when": ts, "port": a.port, "dwell": a.dwell,
              "walk": a.walk, "results": results}
    if a.harvest:
        import harvest_interp_pcs as hp
        gap = seed_gap(g, say)
        report["seed_gap"] = {k: len(v) for k, v in gap.items()}
        report["unseeded"] = gap["unseeded"]
        report["static_seeded_but_interpreted"] = gap["static_seeded"]
        if not a.no_save:
            h = hp.harvest(port=a.port, quiet=True, session="warp_%s" % ts,
                           coverage=False)
            report["harvest"] = {k: h.get(k) for k in ("before", "after", "new", "entered")}
            say("harvest     : observed file %s -> %s PCs (%s new)"
                % (h.get("before"), h.get("after"), h.get("new")))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(report, open(out_path, "w"), indent=1)
    say("wrote " + out_path)
    if sc is not None or a.quit:
        if sc is not None:
            sc.quit()
        else:
            try:
                g.q("quit")
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
