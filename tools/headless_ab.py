"""Identical-protocol headless A/B for overlay dispatch.

Launch is done by the caller; this attaches, loads a savestate, and samples
VSync throughput (emulated frames per wall second -- uncapped in headless, so
it measures raw emulation speed) alongside the overlay dispatch counters.
"""
import sys, time, csv, struct
sys.path.insert(0, "tools")
import playsession as ps

OUT, PORT, SLOT, SECONDS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
K = ['static_checks','static_hits','static_variant_misses','static_address_misses',
     'static_rehashes','static_crc_misses']

def q(cmd, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=PORT, timeout=15.0)

def vsync():
    r = q('read_ram', addr='0x8018603C', len=4)
    return struct.unpack('<I', bytes.fromhex(r['hex']))[0]

# 1. wait for the debug server
for _ in range(60):
    try:
        if q('overlay_loader_status').get('ok'): break
    except Exception: pass
    time.sleep(2)
else:
    sys.exit('debug server never came up')

# 2. wait until the game is actually running frames
prev, stable = -1, 0
for _ in range(90):
    try:
        v = vsync()
        if v > prev: stable += 1
        else: stable = 0
        prev = v
        if stable >= 3: break
    except Exception: pass
    time.sleep(2)
print(f'booted, vsync={prev}', flush=True)

# 3. load the savestate, confirm it took
q('savestate', slot=SLOT, op='load')
for _ in range(30):
    s = q('savestate_status')
    if s['pending'] == 0 and s['last_ok'] == 1 and s['last_op'] == 'load':
        print(f'savestate slot {SLOT} loaded (generation {s["generation"]})', flush=True)
        break
    time.sleep(1)
else:
    sys.exit('savestate load did not complete')
time.sleep(5)   # settle

# 4. sample
out = open(OUT, 'w', newline='')
w = csv.writer(out)
w.writerow(['t','vsync','emu_fps'] + [k.replace('static_','') for k in K])
t0 = time.time()
pv, pt = vsync(), time.time()
while time.time() - t0 < SECONDS:
    time.sleep(2)
    try:
        d = q('overlay_loader_status')
        v, now = vsync(), time.time()
        w.writerow([round(now-t0,1), v, round((v-pv)/(now-pt),1)] + [d[k] for k in K])
        out.flush()
        pv, pt = v, now
    except Exception as e:
        print('sample error', type(e).__name__, flush=True)
print('done', flush=True)
