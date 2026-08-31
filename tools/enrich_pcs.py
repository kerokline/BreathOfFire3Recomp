#!/usr/bin/env python
"""Enrich observed interpreted PCs with identity / reach / disassembly, joining:

  1. IDENTITY  — which .EMI occupant is resident (live RAM byte-match to captures)
  2. BOUNDARY  — function-start (prologue) vs interior; static root vs observed-only
  3. SEMANTICS — a disassembly window from the resident occupant's bytes
  4. REACH     — callers + args from the live dirty_block_log ring, transfer type

This is the OFFLINE slice (no framework change): it reads the captures we already
have and queries a LIVE build-dbg game over TCP for RAM bytes and the caller ring.
Reach data is only as deep as the ring (recent entries), so run it against a game
that just exercised the code you care about.

    python tools/enrich_pcs.py --port 4370 --top 15
    python tools/enrich_pcs.py --pc 0x801E6C60          # one address, verbose

Grouping (--group) clusters PCs by (band, resident occupant) and by shared caller
-- the first step toward "these calls are one subsystem".
"""
import argparse, json, os, sys, struct, binascii
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playsession as ps

REGS = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5',
        't6','t7','s0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1',
        'gp','sp','fp','ra']

def q(cmd, port, **kw):
    return ps.send(dict(cmd=cmd, **kw), port=port, timeout=30.0)

def read_ram(port, addr, n):
    r = q('read_ram', port, addr='0x%08X' % addr, len=n)
    return bytes.fromhex(r['hex']) if r.get('hex') else b''

def dis(w, pc):
    """Compact R3000A disassembler — enough to read a code window."""
    if w == 0: return 'nop'
    op = w >> 26; rs = (w>>21)&31; rt = (w>>16)&31; rd = (w>>11)&31
    sa = (w>>6)&31; fn = w & 0x3F; imm = w & 0xFFFF
    simm = imm-0x10000 if imm & 0x8000 else imm
    jt = (pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
    R = lambda n: REGS[n]
    if op == 0:
        f = {0x20:'add',0x21:'addu',0x22:'sub',0x23:'subu',0x24:'and',0x25:'or',
             0x26:'xor',0x27:'nor',0x2A:'slt',0x2B:'sltu'}.get(fn)
        if f: return '%s %s,%s,%s' % (f,R(rd),R(rs),R(rt))
        if fn==0x00: return 'sll %s,%s,%d'%(R(rd),R(rt),sa)
        if fn==0x02: return 'srl %s,%s,%d'%(R(rd),R(rt),sa)
        if fn==0x03: return 'sra %s,%s,%d'%(R(rd),R(rt),sa)
        if fn==0x08: return 'jr %s'%R(rs)
        if fn==0x09: return 'jalr %s'%R(rd if rd else 31)+',%s'%R(rs)
        if fn==0x10: return 'mfhi %s'%R(rd)
        if fn==0x12: return 'mflo %s'%R(rd)
        if fn==0x18: return 'mult %s,%s'%(R(rs),R(rt))
        if fn==0x1A: return 'div %s,%s'%(R(rs),R(rt))
        if fn==0x0C: return 'syscall'
        return 'special fn=0x%02X'%fn
    j = {0x02:'j',0x03:'jal'}.get(op)
    if j: return '%s 0x%08X'%(j,jt)
    b = {0x04:'beq',0x05:'bne',0x06:'blez',0x07:'bgtz'}.get(op)
    if b: return '%s %s,%s,0x%08X'%(b,R(rs),R(rt),pc+4+(simm<<2))
    if op==0x01:
        return '%s %s,0x%08X'%('bltz' if rt==0 else 'bgez',R(rs),pc+4+(simm<<2))
    i = {0x08:'addi',0x09:'addiu',0x0A:'slti',0x0B:'sltiu',0x0C:'andi',
         0x0D:'ori',0x0E:'xori'}.get(op)
    if i: return '%s %s,%s,%d'%(i,R(rt),R(rs),simm)
    if op==0x0F: return 'lui %s,0x%04X'%(R(rt),imm)
    ld = {0x20:'lb',0x21:'lh',0x23:'lw',0x24:'lbu',0x25:'lhu',
          0x28:'sb',0x29:'sh',0x2B:'sw'}.get(op)
    if ld: return '%s %s,%d(%s)'%(ld,R(rt),simm,R(rs))
    if op==0x10: return 'cop0 0x%07X'%(w&0x1FFFFFF)
    if op==0x12: return 'cop2/gte 0x%07X'%(w&0x1FFFFFF)
    return 'op=0x%02X'%op

def is_prologue(word):
    # addiu sp,sp,-N  (op=0x09 rs=29 rt=29 imm<0)
    op=word>>26; rs=(word>>21)&31; rt=(word>>16)&31; imm=word&0xFFFF
    return op==0x09 and rs==29 and rt==29 and (imm & 0x8000)

def load_captures(path):
    caps = json.load(open(path))
    bands = defaultdict(list)
    for c in caps:
        bands[int(c['load_addr'],16)].append(c)
    return caps, bands

def resident_occupant(port, band_base, occupants):
    """Read a window at the band base and match it to one occupant by bytes."""
    win = read_ram(port, band_base, 512)
    if not win: return None
    best = None
    for c in occupants:
        import base64
        blob = base64.b64decode(c['bytes_b64'])[:len(win)]
        if blob == win[:len(blob)]:
            # exact prefix match; prefer the occupant whose size best fits
            if best is None or c['size'] < best['size']:
                best = c
    return best

def band_of(pc, bands):
    for base, occ in bands.items():
        maxsize = max(c['size'] for c in occ)
        if base <= pc < base + maxsize:
            return base, occ
    return None, None

def enrich_one(port, pc, bands, caps):
    base, occ = band_of(pc, bands)
    out = {'pc':'0x%08X'%pc}
    if base is None:
        out['band'] = None; return out
    out['band'] = '0x%08X'%base
    res = resident_occupant(port, base, occ)
    out['resident'] = res['source_file'] if res else '(unknown / not resident)'
    out['band_occupants'] = len(occ)
    # boundary: is pc a static root anywhere, or observed-only?
    tag = '0x%08X'%pc
    static_owners = [c['source_file'] for c in occ if tag in (c.get('static_discovery_entry_pcs') or [])]
    disp_owners   = [c['source_file'] for c in occ if tag in (c.get('dispatch_entry_pcs') or [])]
    out['is_static_root'] = len(static_owners)
    out['is_dispatch_entry'] = len(disp_owners)
    # disasm window from the resident occupant (or first occupant)
    import base64
    src = res or (occ[0] if occ else None)
    if src:
        blob = base64.b64decode(src['bytes_b64'])
        off = pc - base
        def word(o): return struct.unpack_from('<I',blob,o)[0] if 0<=o<=len(blob)-4 else None
        # FUNCTION-START if a prologue sits at/just after pc, OR pc is preceded by
        # `jr ra; nop` (the boundary the static walk would have honored had a call
        # edge pointed here). Otherwise it is a true interior resume point.
        prologue_near = any(is_prologue(w) for w in
                            (word(off), word(off+4), word(off+8)) if w is not None)
        prev1, prev2 = word(off-8), word(off-4)   # jr ra at -8, delay slot at -4
        after_jr = (prev1 is not None and (prev1>>26)==0 and (prev1&0x3F)==0x08
                    and ((prev1>>21)&31)==31)
        out['boundary'] = ('FUNCTION-START' if (prologue_near or after_jr)
                           else 'INTERIOR')
        out['prologue_here'] = prologue_near
        # the calls this code makes in the next ~16 insns = its linked subsystems
        calls=[]
        for o in range(off, min(len(blob)-3, off+64), 4):
            w=word(o)
            if w is None: continue
            op=w>>26
            if op==0x03:  # jal
                calls.append('0x%08X'%((pc & 0xF0000000)|((w&0x3FFFFFF)<<2)))
        out['calls'] = calls
        lines=[]
        for o in range(max(0,off-12), min(len(blob)-3, off+20), 4):
            w=word(o); a=base+o
            lines.append('%s0x%08X: %08X  %s'%('>' if a==pc else ' ',a,w,dis(w,a)))
        out['disasm']=lines
    # reach: callers from the ring
    r = q('dirty_block_log', port, target_lo='0x%08X'%pc, target_hi='0x%08X'%(pc+4), count=400)
    ents = r.get('entries') or []
    callers = defaultdict(int); frames=set()
    for e in ents:
        callers[e['ra']] += 1; frames.add(e.get('frame'))
    out['ring_hits'] = len(ents)
    out['distinct_callers'] = len(callers)
    out['top_callers'] = sorted(callers.items(), key=lambda kv:-kv[1])[:5]
    out['frame_span'] = (min(frames), max(frames)) if frames else None
    return out

def family(source_file):
    """.EMI path -> subsystem family. BIN/PLCHAR/PLP012.EMI -> PLCHAR,
    BIN/WORLD03/AREA142.EMI -> WORLD03."""
    p = source_file.split('/')
    return p[1] if len(p) > 1 else p[0]

def group_subsystems(bands, observed_path):
    """Offline: attribute each ENTERED observed PC to its band and print an
    interp-weighted subsystem breakdown. Weights are the historical-max insns
    in the observed file (max-merged across sessions), so read them as
    'subsystem scale / where the work was', not live current state. A band whose
    occupants are one family attributes cleanly; a MIXED band cannot be resolved
    to an occupant offline -- that is precisely what the runtime tier-1
    resident-CRC capture would disambiguate."""
    obs = json.load(open(observed_path))
    band_fams = {base: sorted({family(c['source_file']) for c in occ})
                 for base, occ in bands.items()}
    def band_of(pc):
        for base, occ in bands.items():
            if base <= pc < base + max(c['size'] for c in occ):
                return base
        return None
    agg = defaultdict(lambda: [0, 0]); unmapped = [0, 0]
    for r in obs:
        if int(r.get('entries', 0)) <= 0: continue
        pc = (int(r['pc'], 16) & 0x1FFFFFFF) | 0x80000000
        b = band_of(pc); ins = int(r.get('insns', 0))
        if b is None: unmapped[0] += ins; unmapped[1] += 1
        else: agg[b][0] += ins; agg[b][1] += 1
    print('%-12s %-30s %12s %5s  %s' % ('band', 'subsystem (family)', 'interp_ins*', '#PCs', 'attribution'))
    for b in sorted(agg, key=lambda k: -agg[k][0]):
        fams = band_fams[b]
        tag = 'CLEAN' if len(fams) == 1 else 'MIXED(%d)' % len(fams)
        print('0x%08X  %-30s %12d %5d  %s' % (b, ','.join(fams)[:28], agg[b][0], agg[b][1], tag))
    print('%-12s %-30s %12d %5d  %s' % ('(none)', 'KERNEL/BIOS + uncaptured', unmapped[0], unmapped[1], 'not overlay'))
    print('\n* interp_ins = historical-max from the observed file, i.e. subsystem'
          '\n  scale, NOT live state (a since-fixed PC keeps its old peak here).')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=4370)
    ap.add_argument('--captures', default='analysis/overlay_captures_all.json')
    ap.add_argument('--observed', default='analysis/observed_interp_pcs.json')
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--pc', help='enrich a single address, verbose')
    ap.add_argument('--group', action='store_true',
                    help='offline subsystem breakdown by band+family (no live game)')
    ap.add_argument('--json-out')
    args=ap.parse_args()
    caps,bands = load_captures(args.captures)
    if args.group:
        group_subsystems(bands, args.observed)
        return 0
    if args.pc:
        pcs=[int(args.pc,16) & 0x1FFFFFFF | 0x80000000]
    else:
        obs=json.load(open(args.observed))
        rows=[r for r in obs if int(r.get('entries',0))>0]
        rows.sort(key=lambda r:-int(r.get('insns',0)))
        pcs=[(int(r['pc'],16)&0x1FFFFFFF)|0x80000000 for r in rows[:args.top]]
    results=[]
    for pc in pcs:
        e=enrich_one(args.port, pc, bands, caps)
        results.append(e)
        print('\n=== %s  band %s  resident %s ==='%(e['pc'],e.get('band'),e.get('resident')))
        print('  boundary: %s | static_root_in=%d dispatch_entry_in=%d'%(
            e.get('boundary','?'), e.get('is_static_root',0), e.get('is_dispatch_entry',0)))
        if e.get('calls'):
            print('  linked calls: '+', '.join(e['calls'][:8]))
        print('  reach: %d ring hits, %d distinct callers, frames %s'%(
            e.get('ring_hits',0), e.get('distinct_callers',0), e.get('frame_span')))
        for ra,n in e.get('top_callers',[]):
            print('      caller %s x%d'%(ra,n))
        for ln in (e.get('disasm') or [])[:8]:
            print('   '+ln)
    if args.json_out:
        json.dump(results, open(args.json_out,'w'), indent=1)
        print('\nwrote', args.json_out)

if __name__=='__main__':
    raise SystemExit(main())
