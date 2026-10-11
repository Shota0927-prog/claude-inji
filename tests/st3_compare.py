"""ST-3 step comparison on SYNTHETIC data (not market performance).

Zones: the Engine time-series model (rn1_engine_model, Swing max, RN on, ZONE-P bonus defaults) + the ZONE-P FVG
evaluation (st1_sim.st_zone_eval) on random-walk 1M data; orders: the st3_sim mirror; fills: the st2_sim broker emulator.
The numbers only show how each step changes the order flow on the same zones. Real results need the TradingView
Strategy Tester on XAUUSD 5M. Writes tests/st3_compare_results.md.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rn1_engine_model as em     # noqa: E402
import zp_overlap_sim as zs       # noqa: E402
import st1_sim as t1              # noqa: E402
import st3_sim as t3              # noqa: E402

SEEDS = (4, 5, 6, 7)
DAYS = 12


def zone_series(seed):
    C = em.C
    keep = (C.maClusterBonus, C.maClusterDirBonus, C.flipBonus)
    C.maClusterBonus, C.maClusterDirBonus, C.flipBonus = 0.0, 0.0, 0.0
    try:
        b1, chart, htf = em.build(seed, DAYS)
        F = em.Feeds(b1, chart, htf, "nr")
        E = em.Engine()
        E.rn_attach, E.swing_max = True, True
        bars, zones, tmins, m1s = [], [], [], []
        cfg = zs.Cfg(show={1: True, 2: True, 3: True, 4: True}, showState={0: True, 1: True, 2: True, 3: True}, maxZonesDraw=10 ** 6)
        for i in range(len(chart)):
            E.update(F.feed(i, len(chart[i]["subs"]) - 1, "hist"), i)
            S = zs.Slots([zs.fvg(s, E.fTop[s], E.fBot[s], E.fClose[s], True) for s in range(15) if E.fAlive[s]])
            zl = []
            for z in E.live:
                zd = dict(top=z["top"], bottom=z["bottom"], baseSum=z["baseSum"], catCount=z["catCount"], hasHtf=z["hasHtf"],
                          state=z["state"], touch=z["touch"], slopeBonus=z["slopeB"], maBonus=z["maB"],
                          flipBonus=z["flipBonus"], score=z["score"], strength=z["strength"])
                dS, dSt, best, boosted, bT, bB, _, _ = t1.st_zone_eval(cfg, zd, S, zs)
                zl.append(t3.Z(z["trackId"], z["state"], z["top"], z["bottom"], sZ=z["strength"], score=z["score"],
                               boosted=boosted, sB=dSt, dScore=dS, bTop=bT, bBot=bB))
            ch = chart[i]
            bars.append((ch["o"], ch["h"], ch["l"], ch["c"]))
            zones.append(zl)
            tmins.append(((ch["c_t"] // 60000) + 9 * 60) % 1440)
            m1s.append([(x[2], x[3], x[4]) for x in ch["subs"]])
        return bars, zones, tmins, m1s
    finally:
        C.maClusterBonus, C.maClusterDirBonus, C.flipBonus = keep


def stats(S, B):
    sl = {e["order"]["id"]: e["order"]["SL"] for e in S.log if "order" in e}
    rs, pnl = [], []
    for c in B.closed:
        risk = c["side"] * (c["price"] - sl[c["id"]])
        p = c["side"] * (c["exit"] - c["price"])
        pnl.append(p)
        rs.append(p / risk if risk > 0 else 0.0)
    skips = sum(1 for e in S.log if e.get("rr_skip"))
    pre = sum(1 for e in S.log if e.get("rr_skip_ref"))
    return rs, pnl, skips, pre


STEPS = [
    ("Base (A/B/C = ST-2)", dict(sess=False, tpzone=False, be=False)),
    ("+ Session", dict(sess=True, tpzone=False, be=False)),
    ("+ Session + Zone TP", dict(sess=True, tpzone=True, be=False)),
    ("+ Session + Zone TP + BE", dict(sess=True, tpzone=True, be=True)),
]


def main():
    data = [zone_series(s) for s in SEEDS]
    rows = []
    for mode in ("A", "B", "C", "D"):
        for name, kw in STEPS:
            R, P, sk, pre = [], [], 0, 0
            for bars, zones, tmins, m1s in data:
                S, B = t3.run3(bars, zones, tmins=tmins, m1s=m1s, mode=mode, **kw)
                r, p, a, b = stats(S, B)
                R += r
                P += p
                sk += a
                pre += b
            n = len(R)
            win = sum(1 for x in P if x > 0)
            gp, gl = sum(x for x in P if x > 0), -sum(x for x in P if x < 0)
            rows.append((mode, name, n, win / n * 100 if n else 0.0, gp / gl if gl else float("inf") if gp else 0.0,
                         sum(R) / n if n else 0.0, sum(R), pre, sk))
    out = ["# ST-3 step comparison — SYNTHETIC data (not market performance)", "",
           f"Engine model zones on random-walk 1M data, seeds {SEEDS}, {DAYS} days each; mirror orders + broker emulator.",
           "Shows only how each step changes the order flow on identical zones. Use the TradingView Strategy Tester for results.",
           "", "| Mode | Step | Trades | Win % | PF | Avg R | Total R | Pre-check skips | Post-fill RR exits |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.1f} | {r[4]:.2f} | {r[5]:.3f} | {r[6]:.2f} | {r[7]} | {r[8]} |")
    txt = "\n".join(out) + "\n"
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "st3_compare_results.md"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
