"""LAB-1 reference load run (Python emulation only — NOT TradingView's run time).

  python3 tests/lab_load.py [bars]

Synthetic 5m path with Zone feeds built from completed blocks (1H = 12 bars, 4H = 48, D = 276, W = 1380): a new POC value on every
completed block of every time frame (the worst case: the POC moves on every higher-TF bar), Swing pivots, 1H FVGs, a moving EMA.
Prints how many Zones are held (no Zone is ever pruned except invalidated FVGs) and how many Zones one bar scans, at points of the run.
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_pine as lp     # noqa: E402
import lab_sim as ls      # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
TFS = {1: 12, 2: 48, 3: 276, 4: 1380}
rnd = random.Random(7)
p = 2000.0
rows = []
for i in range(N):
    o = p
    c = o + rnd.gauss(0, 2.0)
    rows.append((round(o, 2), round(max(o, c) + abs(rnd.gauss(0, 1.0)), 2), round(min(o, c) - abs(rnd.gauss(0, 1.0)), 2), round(c, 2)))
    p = c
sc = ls.Sc(rows)
for i in range(N):
    b = sc.bars[i]
    for k, L in TFS.items():
        hb = i // L
        if hb >= 1:
            seg = rows[(hb - 1) * L: hb * L]
            hi, lo = max(r[1] for r in seg), min(r[2] for r in seg)
            vw = round(sum((r[1] + r[2]) / 2 for r in seg) / len(seg), 2)
            b.update(ls.pocv(k, vw - 0.2, vw + 0.2, ls.T0 + hb * 1000))
            if hb % 7 == 0:
                b.update({f"s{k}h": hi, f"s{k}ht": ls.T0 + hb * 1000 + k, f"s{k}l": lo, f"s{k}lt": ls.T0 + hb * 1000 + k})
    hb = i // 12
    if hb >= 2:
        seg, prev = rows[(hb - 1) * 12: hb * 12], rows[(hb - 2) * 12: (hb - 1) * 12]
        up = min(r[2] for r in seg) > max(r[1] for r in prev) + 3
        dn = max(r[1] for r in seg) < min(r[2] for r in prev) - 3
        b.update(g1k=ls.T0 + hb * 3600_000, g1c=seg[-1][3], g1d=1 if up else -1 if dn else 0,
                 g1t=min(r[2] for r in seg) if up else min(r[2] for r in prev) if dn else None,
                 g1b=max(r[1] for r in prev) if up else max(r[1] for r in seg) if dn else None)
    if i >= 1:
        b.update(labS1=round(rows[i - 1][3] + rnd.choice([-1.5, 1.5]), 2), zbMa1=round(sum(r[3] for r in rows[max(0, i - 600):i + 1]) / min(i + 1, 601), 2))
r = lp.Runner(overrides=dict(zbUse2=False, dsZone=False, dsEnt=False))
t0 = time.time()
mx = 0
for i, b in enumerate(sc.bars):
    r.step(b)
    mx = max(mx, r["st"].iter)
    if (i + 1) % (N // 6) == 0:
        print(f"bar {i + 1:6d}: Zones held ZA/ZB/ZC/ZD/ZF = {list(r['lbNZone'])}  scanned this bar {r['st'].iter:4d}  max so far {mx:4d}"
              f"  waits max {r['st'].maxWaits}  timings max {r['st'].maxTevs}  trades {r['st'].nTrades}  {(time.time() - t0) / (i + 1) * 1000:.1f} ms/bar (Python)")
