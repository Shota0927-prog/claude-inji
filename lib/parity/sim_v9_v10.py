"""ZoneEngine v9 vs v10 (F1+F2) parity simulation.

Faithful Python port of f_buildClusters / f_finalizeCluster(center, uids) /
f_findTrack / f_trackContinuous / f_uidOverlap / track loop (6.9-6.11).
Python float == IEEE754 binary64 == Pine float. Compares every bar:
cluster partitions, zone centers (bit-exact), memberUids (content+order),
track ids, track centers, trackSeq, track count.
"""
import random, struct, sys

CLUSTER_DIST, CONT, STALE = 20.0, 0.5, 500

class Raw:
    __slots__=("uid","center","base")
    def __init__(s,u,c,b): s.uid,s.center,s.base=u,c,b
def w_of(z): return max(z.base, 0.01)

def finalize(members):
    tw=ts=0.0; uids=[]
    for m in members:
        w=w_of(m); tw+=w; ts+=m.center*w; uids.append(m.uid)
    ctr = ts/tw if tw>0 else float("nan")
    return {"center":ctr,"uids":uids}

def sort_indices(centers):
    return sorted(range(len(centers)), key=lambda i:(centers[i], i))  # stable like array.sort_indices

def build_v9(src):
    out=[]; n=len(src)
    if n==0: return out
    ordr=sort_indices([z.center for z in src]); cur=[]
    for k in range(n):
        z=src[ordr[k]]
        if not cur: cur.append(z); continue
        tw=0.0; ts=0.0
        for m in cur:
            w=w_of(m); tw+=w; ts+=m.center*w
        wz=w_of(z); nc=(ts+z.center*wz)/(tw+wz)
        ok=abs(z.center-nc)<=CLUSTER_DIST
        if ok:
            for m in cur:
                if abs(m.center-nc)>CLUSTER_DIST: ok=False; break
        if ok: cur.append(z)
        else: out.append(finalize(cur)); cur=[z]
    if cur: out.append(finalize(cur))
    return out

def build_v10(src):
    out=[]; n=len(src)
    if n==0: return out
    ordr=sort_indices([z.center for z in src]); cur=[]; ctw=cts=0.0
    for k in range(n):
        z=src[ordr[k]]
        if not cur:
            cur.append(z); w0=w_of(z); ctw=0.0+w0; cts=0.0+z.center*w0; continue
        tw=ctw; ts=cts
        wz=w_of(z); nc=(ts+z.center*wz)/(tw+wz)
        ok=abs(z.center-nc)<=CLUSTER_DIST
        if ok:
            for m in cur:
                if abs(m.center-nc)>CLUSTER_DIST: ok=False; break
        if ok: cur.append(z); ctw=ctw+wz; cts=cts+z.center*wz
        else:
            out.append(finalize(cur)); cur=[z]; ctw=0.0+wz; cts=0.0+z.center*wz
    if cur: out.append(finalize(cur))
    return out

def overlap(a,b):
    return sum(1 for x in a if x in b) if a and b else 0
def continuous(t,z):
    ov=overlap(z["uids"],t["uids"]); mx=max(len(z["uids"]),len(t["uids"]))
    return ov>=1 and mx>0 and ov/mx>=CONT

class Eng:
    def __init__(s,v10): s.v10=v10; s.tracks=[]; s.seq=0
    def step(s,bar,raw):
        zones=(build_v10 if s.v10 else build_v9)(raw)
        for t in s.tracks: t["matched"]=False
        for z in zones:
            best=-1; bd=1e20
            for i,t in enumerate(s.tracks):
                if not t["matched"]:
                    d=abs(t["center"]-z["center"])
                    if d<=CLUSTER_DIST and d<bd and continuous(t,z): bd=d; best=i
            if best>=0: t=s.tracks[best]
            else:
                s.seq+=1
                t={"id":s.seq,"center":z["center"],
                   "uids": z["uids"] if s.v10 else list(z["uids"])}
                s.tracks.append(t)
            t["matched"]=True; t["center"]=z["center"]; t["last"]=bar
            t["uids"]= z["uids"] if s.v10 else list(z["uids"])   # F1 alias vs copy
            z["trackId"]=t["id"]
        for i in range(len(s.tracks)-1,-1,-1):
            if bar-s.tracks[i]["last"]>STALE: del s.tracks[i]
        return zones

def bits(x): return struct.pack("<d",x)

def run(seed,bars=6000):
    rnd=random.Random(seed)
    persist=[]; uid=0; price=2000.0; ema=price
    e9,e10=Eng(False),Eng(True)
    for bar in range(bars):
        price+=rnd.gauss(0,3); ema+= (price-ema)*2/(2001)*5
        if rnd.random()<0.08:
            uid+=1; persist.append(Raw(uid, price+rnd.uniform(-60,60), rnd.choice([1.0,2.0,3.0,4.0,5.0])))
        if len(persist)>200: persist.pop(0)
        raw=list(persist)
        mode=seed%3
        if mode>=1: raw.append(Raw(-1, ema if mode==1 else price, 2.0))   # MA1 (EMA-like or close-like)
        if mode==2: raw.append(Raw(-2, ema, 2.0))
        raw.append(Raw(10**6+bar//288, price+rnd.uniform(0,15), 3.0))     # Day High (uid per day)
        z9=e9.step(bar,raw); z10=e10.step(bar,raw)
        assert len(z9)==len(z10), (seed,bar,"zoneCount")
        for a,b in zip(z9,z10):
            assert bits(a["center"])==bits(b["center"]), (seed,bar,"center")
            assert a["uids"]==b["uids"], (seed,bar,"uids")
            assert a["trackId"]==b["trackId"], (seed,bar,"trackId")
        assert e9.seq==e10.seq and len(e9.tracks)==len(e10.tracks), (seed,bar,"tracks")
        for a,b in zip(e9.tracks,e10.tracks):
            assert a["id"]==b["id"] and bits(a["center"])==bits(b["center"]) and a["uids"]==b["uids"], (seed,bar,"track")
    return e9.seq, len(e9.tracks)

if __name__=="__main__":
    n=int(sys.argv[1]) if len(sys.argv)>1 else 30
    tot=0
    for sd in range(n):
        seq,nt=run(sd); tot+=1
        print(f"seed {sd:3d} mode {sd%3} : trackSeq={seq:6d} liveTracks={nt:5d}  PASS")
    print(f"ALL {tot} seeds x 6000 bars : 0 diffs")
