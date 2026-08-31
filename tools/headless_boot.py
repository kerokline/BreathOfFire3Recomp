"""Boot-phase sampler: no savestate. Covers the Capcom logo and title -- the
screens where SS8 measured its all-bands regression and where static_hits is 0,
i.e. no overlay code runs and the dispatcher is pure overhead."""
import sys, time, csv, struct
sys.path.insert(0, "tools")
import playsession as ps
OUT, PORT, SECONDS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
K = ['static_checks','static_hits','static_variant_misses','static_address_misses',
     'static_rehashes','static_crc_misses']
def q(c, **kw): return ps.send(dict(cmd=c, **kw), port=PORT, timeout=15.0)
def vsync():
    return struct.unpack('<I', bytes.fromhex(q('read_ram', addr='0x8018603C', len=4)['hex']))[0]
for _ in range(90):
    try:
        if q('overlay_loader_status').get('ok'): break
    except Exception: pass
    time.sleep(1)
out = open(OUT,'w',newline=''); w = csv.writer(out)
w.writerow(['t','vsync','emu_fps'] + [k.replace('static_','') for k in K])
t0 = time.time(); pv, pt = 0, time.time()
while time.time()-t0 < SECONDS:
    time.sleep(2)
    try:
        d = q('overlay_loader_status'); v, now = vsync(), time.time()
        w.writerow([round(now-t0,1), v, round((v-pv)/(now-pt),1)] + [d[k] for k in K])
        out.flush(); pv, pt = v, now
    except Exception: pass
print('done', flush=True)
