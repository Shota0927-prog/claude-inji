"""ACC-3 experiment (not a pass / fail fixture; about 30 min): how much tick-level breakeven could change the ACC-2 results.

Synthetic XAU-like 1M random walk (NOT TradingView data, NOT a TradingView result), aggregated to 5M; the HTF accum feed through
the NR-A1 delivery (tests/nr_a1_sim.py port). The logic section of AccumStrategyXAU.pine runs through tests/acc_pine.py in:
  A  normal history: one execution at each 5M close (the current backtest)
  B  ticks = the 4-point OHLC path of each 5M bar
  C  ticks = the 1M path (4 points per 1M bar, 20 per 5M bar) - the "high-resolution history" case
B and C ASSUME the final tick of a bar is identifiable (barstate.isconfirmed on the last tick only, realtime semantics) -
which the cited On history bar tick behaviour does NOT give (isconfirmed true on every tick): they are an upper bound of what
the setting could improve, not a design that can be built. Stops between two ticks fill at their own price.
Run: python3 tests/acc3_exp.py
"""
import os
import random
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap      # noqa: E402
import acc_sim as t        # noqa: E402
import nr_a1_sim as nas    # noqa: E402
M1, M5 = 60_000, 300_000

def market1m(seed, days):
    rnd = random.Random(seed); p = 2000.0; out = []; t0 = 1_790_000_000_000 // 86_400_000 * 86_400_000
    regime, left = 0.0, 0
    for d in range(days):
        if d % 7 in (5, 6): continue
        for s in range(23 * 60):
            tt = t0 + d * 86_400_000 - 3_600_000 + s * M1
            if left <= 0: regime, left = rnd.choice([0.0, 0.0, 0.6, -0.6]), rnd.randint(200, 1500)
            left -= 1
            q = p + regime + rnd.gauss(0, 1.5)
            out.append((tt, p, max(p, q) + abs(rnd.gauss(0, .6)), min(p, q) - abs(rnd.gauss(0, .6)), q)); p = q
    return out

def agg5(m1):
    g = {}
    for b in m1: g.setdefault(b[0] // M5, []).append(b)
    out = []
    for k in sorted(g):
        x = g[k]; out.append(((k * M5), x[0][1], max(y[2] for y in x), min(y[3] for y in x), x[-1][4], x))
    return out

def run(bars5, mode):
    b5 = [x[:5] for x in bars5]
    feeds = t.feeds_from_5m(nas, b5)
    r = ap.Runner(dict(t.ACC3_OV, seUse=False), tick_segments=(mode != "A"))     # ACC-4: the ACC-3 settings (same results)
    for i, (tt, o, h, l, c, subs) in enumerate(bars5):
        b = dict(t=tt, o=o, h=h, l=l, c=c, feed=feeds[i])
        if mode == "B":
            b["ticks"] = ap.Broker.bar_path(o, h, l, c)
        elif mode == "C":
            ticks = []
            for s in subs:
                ticks += ap.Broker.bar_path(s[1], s[2], s[3], s[4])
            b["ticks"] = ticks
        r.step(b)
    return r

def trades(r):
    out = []
    for c in r.broker.closed:
        out.append((c["id"], c["side"], c["bar_in"], round(c["price"], 2), c["exit_id"], c["bar_out"], round(c["exit_price"], 2),
                    round(c["side"] * (c["exit_price"] - c["price"]) * c["qty"], 2)))
    return out

for seed in (11, 12, 13, 14):
    bars = agg5(market1m(seed, 30))
    res = {m: run(bars, m) for m in "ABC"}
    for m, r in res.items():
        tr = trades(r)
        ent = [(o[0], o[2]) for o in t.orders(r)]
        print(f"seed {seed} {m}: trades {len(tr)} entries {len(ent)} BE {r['nBE']} PnL(USD) {sum(x[7] for x in tr):.2f} "
              f"win {sum(1 for x in tr if x[7] > 0)} beRevisit(hist) {r['nBeRevisit']} beSlConf(hist) {r['nBeSlConf']}")
    a, b, c = (trades(res[m]) for m in "ABC")
    ea, eb, ec = (t.orders(res[m]) for m in "ABC")
    def firstdiff(x, y):
        for i, (p, q) in enumerate(zip(x, y)):
            if p != q: return i, p, q
        return None if len(x) == len(y) else (min(len(x), len(y)), "len", (len(x), len(y)))
    print("  entries A==B", ea == eb, "A==C", ea == ec, "| first trade diff A/B", firstdiff(a, b), "A/C", firstdiff(a, c))
