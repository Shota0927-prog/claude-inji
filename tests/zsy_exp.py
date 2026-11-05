"""ZSY-0 experiment — does the Lab's current Zone / display state depend on history? (code verification only)

  python3 tests/zsy_exp.py

Runs the LOGIC section of ZoneComboLabXAU.pine itself (tests/lab_pine.py: mechanical translation, unchanged Lab source) on
synthetic 5m bars with causal higher-TF feeds (POC 1H / 4H, Swing 1H, FVG 1H, MA 1m / 5m), and compares the final state of
  * the internal valid Zones (type, TF, sub, bot, top, registered 5m bar time)
  * the display bands (lbDsG in order: bot, top, gone, members)
between
  E1  the same bars and feeds, with the accumulation starting at bar 0 vs at a later bar (start point)
  E2  the feeds delivered on every 5m bar (what the Lab sees on a 5m chart) vs only refreshed at the end of each
      1H / 4H / 1D chart bar (the only granularity an input.source series can have on such a chart)
  E3  the display bands vs the overlap groups of every valid Zone at the end (is "draw all valid Zones" the same?)

Evidence class: PINE_NOT_VERIFIED (the Lab logic runs in Python; request.security / input.source / TradingView are not run).
Purpose: decide the architecture of the multi-timeframe display (ZONE_SYNC_FEASIBILITY_ja.md). It does not test a new script.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_pine as lp     # noqa: E402

lp.LEGACY = {}            # current Lab defaults (common width 2, swing merge 5)
M5 = lp.M5
H1 = 3_600_000
T0 = 1_767_574_800_000    # 2026-01-05 01:00 UTC


def gen(seed, n):
    rnd = random.Random(seed)
    p = 2000.0
    rows = []
    for _ in range(n):
        o = p
        c = o + rnd.gauss(0, 2.4)
        h = max(o, c) + abs(rnd.gauss(0, 1.3))
        lo = min(o, c) - abs(rnd.gauss(0, 1.3))
        rows.append((round(o, 2), round(h, 2), round(lo, 2), round(c, 2)))
        p = c
    bars = [dict(t=T0 + i * M5, o=r[0], h=r[1], l=r[2], c=r[3]) for i, r in enumerate(rows)]
    e1 = e5 = None
    for i, b in enumerate(bars):
        c = rows[i][3]
        e5 = c if e5 is None else e5 + (c - e5) * 2 / 61.0        # stand-ins for the EMAs (moving every bar)
        e1 = c if e1 is None else e1 + (c - e1) * 2 / 121.0
        b.update(zbMa1=round(e1, 3), zbMa2=round(e5, 3))
        for k, blk in ((1, 12), (2, 48)):                          # POC 1H (k 1) / 4H (k 2): previous completed block only
            hb = i // blk
            if hb >= 1:
                seg = rows[(hb - 1) * blk: hb * blk]
                hi, lw = max(r[1] for r in seg), min(r[2] for r in seg)
                cc = round(lw + (hi - lw) * random.Random(seed * 100003 + hb * 7 + k).random(), 1)
                b.update({f"zdL{k}": cc - 0.25, f"zdU{k}": cc + 0.25, f"zdT{k}": float(T0 + (hb - 1) * blk * M5)})
        hb = i // 12                                               # 1H swing (every 3rd hour) and 1H FVG
        if hb >= 2:
            seg, prev = rows[(hb - 1) * 12: hb * 12], rows[(hb - 2) * 12: (hb - 1) * 12]
            tk = T0 + (hb - 1) * H1
            if hb % 3 == 0:
                b.update(s1h=max(r[1] for r in seg), s1ht=tk)
            if hb % 4 == 1:
                b.update(s1l=min(r[2] for r in seg), s1lt=tk)
            b.update(g1k=tk, g1kc=tk + H1, g1c=seg[-1][3], g1d=0)
            if min(r[2] for r in seg) > max(r[1] for r in prev) + 3:
                b.update(g1d=1, g1t=min(r[2] for r in seg), g1b=max(r[1] for r in prev))
            elif max(r[1] for r in seg) < min(r[2] for r in prev) - 3:
                b.update(g1d=-1, g1t=min(r[2] for r in prev), g1b=max(r[1] for r in seg))
    return bars


OV = dict(dsEnt=False, dsTbl=False, cTA=False, cTC=False)    # no entries: the Zone / display part only


def run(bars, **ov):
    return lp.Runner(overrides={**OV, **ov}).run(bars)


def zones(r):
    out = []
    for arr in ("lbZs", "lbFvgs"):
        for z in r[arr]:
            if not z.dead:
                out.append((z.typ, z.tf, z.sub, round(z.bot, 3), round(z.top, 3), z.aTime, z.inv))
    return sorted(out)


def bands(r):
    res = []
    for g in r["lbDsG"]:
        mem = sorted((z.typ, z.tf, z.sub, z.aTime) for z in g.mem)
        res.append((round(g.bot, 3), round(g.top, 3), g.gone, tuple(mem)))
    return res


def overlap_groups(r):
    """every valid non-FVG Zone (MA only when it touches another) grouped by actual overlap + every FVG alone"""
    zs = [z for z in r["lbZs"] if not z.dead]
    ma = [m for m in (r["lbMa1"], r["lbMa2"]) if m is not None]
    items = sorted([(z.bot, z.top, z.typ) for z in zs + ma])
    groups, cur = [], None
    for b, t, ty in items:
        if cur and b <= cur[1] + 1e-7:
            cur[1] = max(cur[1], t)
            cur[2].add(ty)
        else:
            if cur:
                groups.append(cur)
            cur = [b, t, {ty}]
    if cur:
        groups.append(cur)
    gs = [(round(b, 3), round(t, 3)) for b, t, tys in groups if tys != {1}]
    gs += [(round(z.bot, 3), round(z.top, 3)) for z in r["lbFvgs"] if not z.dead]
    return sorted(gs)


def sampled(bars, chart_bars):
    """input.source on a chart of `chart_bars` 5m bars: the external value can change only once per chart bar. Causal best case:
    5m bar i sees the value the external series had at the last 5m bar of the previous completed chart bar."""
    keys = [k for k in lp.FEED_DEFAULT if k.startswith("zd") and k != "zdProto"]
    out = []
    for i, b in enumerate(bars):
        nb = dict(b)
        j = (i // chart_bars) * chart_bars - 1
        for k in keys:
            nb.pop(k, None)
            if j >= 0 and k in bars[j]:
                nb[k] = bars[j][k]
        out.append(nb)
    return out


def diff(a, b):
    sa, sb = set(a), set(b)
    return len(sa - sb), len(sb - sa)


def main():
    rep = []
    for seed in range(3):
        bars = gen(seed, 1500)
        full = run(bars)
        zf, bf = zones(full), bands(full)
        # E1: start later (same bars / feeds after the start)
        for s in (300, 900):
            late = run(bars[s:])
            rep.append(("E1 start %4d" % s, seed, diff(zf, zones(late)), diff(bf, bands(late)), len(zf), len(bf)))
        # E2: feeds refreshed once per chart bar
        for name, cb in (("1H", 12), ("4H", 48), ("1D", 288)):
            sm = run(sampled(bars, cb))
            rep.append(("E2 POC per " + name, seed, diff(zf, zones(sm)), diff(bf, bands(sm)), len(zf), len(bf)))
        # E3: display cap (default 80 and a small one) vs "all valid Zones grouped by overlap"
        for cap in (80, 4):
            rc = full if cap == 80 else run(bars, dsZoneMax=cap)
            shown = sorted((b[0], b[1]) for b in bands(rc) if not b[2])
            rep.append(("E3 cap %3d" % cap, seed, diff(overlap_groups(rc), shown), (0, 0), len(overlap_groups(rc)), len(shown)))
    print("case               seed  zones(only A, only B)  bands(only A, only B)  nZonesA nBandsA")
    for name, seed, dz, db, nz, nb in rep:
        print(f"{name:18s} {seed:4d}  {str(dz):21s}  {str(db):21s}  {nz:7d} {nb:7d}")
    return rep


if __name__ == "__main__":
    main()
