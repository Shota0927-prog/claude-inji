"""SSS-2 checks — SatsShortSignal.pine (15S SATS SELL / BUY start-of-bar detector, history + realtime).

1. f_satBand() in SatsShortSignal.pine is byte-identical to tests/sats_src/f_satBand.txt.
2. A Python port of f_satBand() (Pine ta semantics: vwma, atr = rma(tr(true)), highest / lowest with na warm-up) is run on random
   OHLCV. On every bar P the Pine helpers f_nextAnchor / f_satsPrep are mirrored and compared with the port's values on the
   next bar N:
     - LINE1 / LINE2 start anchor and direction == f_satBand() anchor / dir on N (they only depend on P's data);
     - start line price == N's anchor + P's common (the documented approximation; differs from the full-bar line only by common);
     - STB start direction / price == f_satBand() STB on N when N is a single-tick bar (high = low = close = open);
     - the start state does not change when N's high / low / close / volume are changed (only time / open of N are used).
3. The chart pipeline (15s chart, 30s / 1m request with [time, open, x[1]] + lookahead_on, processed on the first 15s bar where the
   requested time changes, 15s -> 30s -> 1m, SELL / BUY waits independent) is mirrored and run on scripted cases:
   both directions in history, 15s / 30s / 1m at the same start time, exactly 5 minutes, SELL and BUY intermediate events not
   mixing, a red line turning back blue, pair update / reset, 30s before 15s.
4. Random 15s data -> 30s / 1m aggregation -> full pipeline: SELL and BUY counts, and checks that every signal has
   t15 <= t30 <= t1m, t1m - t15 <= wait and all three events in the signal's direction.

Evidence class: PINE_NOT_VERIFIED (TradingView compiler, request.security delivery and drawing are not run here).
"""
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S15 = 15_000
M = 60_000
NA = None


# ---- Pine-like series helpers ----------------------------------------------------------------------------------------------
def sma(xs, n, i):
    if i + 1 < n or any(x is None for x in xs[i - n + 1:i + 1]):
        return None
    return sum(xs[i - n + 1:i + 1]) / n


def highest(xs, n, i):
    return None if i + 1 < n else max(xs[i - n + 1:i + 1])


def lowest(xs, n, i):
    return None if i + 1 < n else min(xs[i - n + 1:i + 1])


def sat_series(bars):
    """bars: list of dict(o,h,l,c,v). Returns per-bar f_satBand() outputs + Pine helper values (f_satsPrep) per bar."""
    n = len(bars)
    o = [b["o"] for b in bars]; h = [b["h"] for b in bars]; lo = [b["l"] for b in bars]
    c = [b["c"] for b in bars]; v = [b["v"] for b in bars]
    hlc3 = [(h[i] + lo[i] + c[i]) / 3 for i in range(n)]
    pv = [hlc3[i] * v[i] for i in range(n)]
    tr = [h[0] - lo[0]] + [max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1])) for i in range(1, n)]
    atr = [None] * n
    for i in range(n):
        if i + 1 == 50:
            atr[i] = sum(tr[:50]) / 50
        elif i + 1 > 50:
            atr[i] = (atr[i - 1] * 49 + tr[i]) / 50
    out = []
    st1 = {"a": None, "d": 1}; st2 = {"a": None, "d": 1}; sdir = 1
    for i in range(n):
        sv, s_v = sma(pv, 5, i), sma(v, 5, i)
        basis = None if sv is None or not s_v else sv / s_v
        common = None if basis is None else basis * 0.5
        a50 = atr[i - 1] if i >= 1 else None
        src = c[i - 1] * 0.5 if i >= 1 else None
        tl = lo[i - 1] * 0.5 if i >= 1 else None
        th = h[i - 1] * 0.5 if i >= 1 else None
        for stt, k in ((st1, 5.0), (st2, 2.5)):
            stt["a"], stt["d"] = next_anchor(stt["a"], stt["d"], k, src, tl, th, a50)
        l1 = None if common is None or st1["a"] is None else common + st1["a"]
        l2 = None if common is None or st2["a"] is None else common + st2["a"]
        up10, lw10 = highest(h, 10, i), lowest(lo, 10, i)
        p20h = highest(h, 20, i - 1) if i >= 1 else None
        p20l = lowest(lo, 20, i - 1) if i >= 1 else None
        if p20h is not None and p20l is not None:
            if h[i] > p20h:
                sdir = 1
            elif lo[i] < p20l:
                sdir = -1
        stb = lw10 if sdir == 1 else up10
        state = 0
        if None not in (l1, l2, stb):
            if c[i] > l1 and c[i] > l2 and c[i] > stb:
                state = 1
            elif c[i] < l1 and c[i] < l2 and c[i] < stb:
                state = -1
        # f_satsPrep on this bar (as P)
        a1n, d1n = next_anchor(st1["a"], st1["d"], 5.0, c[i] * 0.5, lo[i] * 0.5, h[i] * 0.5, atr[i])
        a2n, d2n = next_anchor(st2["a"], st2["d"], 2.5, c[i] * 0.5, lo[i] * 0.5, h[i] * 0.5, atr[i])
        out.append(dict(l1=l1, l2=l2, stb=stb, d1=st1["d"], d2=st2["d"], sd=sdir, st=state, common=common,
                        a1=st1["a"], a2=st2["a"],
                        prep=dict(okP=None not in (l1, l2, stb), st=state, d1=st1["d"], d2=st2["d"], sd=sdir,
                                  l1s=None if common is None or a1n is None else common + a1n,
                                  l2s=None if common is None or a2n is None else common + a2n,
                                  a1n=a1n, a2n=a2n, d1s=d1n, d2s=d2n,
                                  hh20=highest(h, 20, i), ll20=lowest(lo, 20, i),
                                  hh9=highest(h, 9, i), ll9=lowest(lo, 9, i))))
    return out


def next_anchor(pa, pd, k, src, tl, th, atr):
    a, d = pa, pd
    if None not in (atr, src, tl, th):
        if pa is None:
            a, d = src - k * atr, 1
        elif pd == 1:
            if tl < pa:
                d, a = -1, src + k * atr
            else:
                d, a = 1, max(pa, src - k * atr)
        else:
            if th > pa:
                d, a = 1, src - k * atr
            else:
                d, a = -1, min(pa, src + k * atr)
    return a, d


def f_evt(o, p):
    """Mirror of Pine f_evt(o, prep[1]...). p = prep dict of the previous confirmed bar (or None)."""
    if p is None:
        return 0, 0, None, None, None
    sdS = p["sd"]
    if p["hh20"] is not None and p["ll20"] is not None:
        if o > p["hh20"]:
            sdS = 1
        elif o < p["ll20"]:
            sdS = -1
    lim = p["ll9"] if sdS == 1 else p["hh9"]
    sbS = None if lim is None else (min(o, lim) if sdS == 1 else max(o, lim))
    ms = mb = 0
    stS = None
    if p["okP"] and None not in (p["l1s"], p["l2s"], sbS):
        l1s, l2s = p["l1s"], p["l2s"]
        stS = 1 if (o > l1s and o > l2s and o > sbS) else -1 if (o < l1s and o < l2s and o < sbS) else 0
        if stS == 0 and p["st"] == 1:
            ms += 1 if p["d1"] == 1 and p["d1s"] == -1 and l1s > o else 0
            ms += 2 if p["d2"] == 1 and p["d2s"] == -1 and l2s > o else 0
            ms += 4 if p["sd"] == 1 and sdS == -1 and sbS > o else 0
        if stS == 0 and p["st"] == -1:
            mb += 1 if p["d1"] == -1 and p["d1s"] == 1 and l1s < o else 0
            mb += 2 if p["d2"] == -1 and p["d2s"] == 1 and l2s < o else 0
            mb += 4 if p["sd"] == -1 and sdS == 1 and sbS < o else 0
    return ms, mb, stS, sdS, sbS


# ---- sequencing (mirror of SeqState + the chart block) ------------------------------------------------------------------------
class Seq:
    def __init__(self):
        self.reset()

    def reset(self):
        self.w15T = self.p15T = self.p30T = None

    def expire(self, t, W):
        if self.w15T is not None and t - self.w15T > W:
            self.w15T = None
        if self.p15T is not None and t - self.p15T > W:
            self.p15T = self.p30T = None

    def on15(self, t, m, W):
        self.expire(t, W)
        if m > 0:
            self.w15T = t

    def on30(self, t, m, W):
        self.expire(t, W)
        if m > 0 and self.w15T is not None and self.w15T <= t and t - self.w15T <= W:
            self.p15T, self.p30T = self.w15T, t

    def on60(self, t, m, W):
        self.expire(t, W)
        if m > 0 and self.p15T is not None and self.p15T <= self.p30T <= t and t - self.p15T <= W:
            r = (self.p15T, self.p30T, t)
            self.reset()
            return r
        return None


def chart_run(rows, wait_min=5):
    """rows: per 15s chart bar: (t, (ms15, mb15), t30, (ms30, mb30), t60, (ms60, mb60)). Returns list of (bar, dir, times)."""
    W = wait_min * M
    sS, sB = Seq(), Seq()
    out = []
    prev30 = prev60 = None
    for i, (t, e15, t30, e30, t60, e60) in enumerate(rows):
        sS.on15(t, e15[0], W); sB.on15(t, e15[1], W)
        if t30 is not None and t30 != prev30:
            sS.on30(t30, e30[0], W); sB.on30(t30, e30[1], W)
        if t60 is not None and t60 != prev60:
            rs = sS.on60(t60, e60[0], W); rb = sB.on60(t60, e60[1], W)
            if rs:
                out.append((i, "SELL", rs))
            if rb:
                out.append((i, "BUY", rb))
        prev30, prev60 = t30, t60
    return out


def scripted(events, n_bars=60, t0=10 * M):
    """events: {(tf, t): 'S'|'B'|'SB'} -> rows with the event only on the requested time's first 15s bar."""
    rows = []
    for i in range(n_bars):
        t = t0 + i * S15
        t30 = t - t % 30_000
        t60 = t - t % M
        def m(tf, tt):
            e = events.get((tf, tt), "")
            return (2 if "S" in e else 0, 1 if "B" in e else 0)
        rows.append((t, m(15, t), t30, m(30, t30), t60, m(60, t60)))
    return rows


RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def rand_bars(rng, n, p0=2000.0, vol=1.0):
    bars, p = [], p0
    for _ in range(n):
        o = p + rng.gauss(0, vol * 0.2)
        cl = o + rng.gauss(0, vol)
        hi = max(o, cl) + abs(rng.gauss(0, vol * 0.5))
        lw = min(o, cl) - abs(rng.gauss(0, vol * 0.5))
        bars.append(dict(o=o, h=hi, l=lw, c=cl, v=rng.randint(1, 50)))
        p = cl
    return bars


def regime_bars(rng, n, p0=2000.0, vol=0.5):
    """trend legs with abrupt reversals, plus planted long-wick bars on the last 15s of a minute (wick against the trend, close
    back with the trend) so that a line can flip at the next 15s / 30s / 1m start while the band stays lit on the wick bar."""
    bars, p, drift, left = [], p0, 0.0, 0
    for i in range(n):
        gap = 0.0
        if left <= 0:
            nd = rng.choice([-1, 1]) * rng.uniform(0.3, 1.5) * vol
            if drift and (nd > 0) != (drift > 0):
                gap = -drift * rng.uniform(4, 25)
            drift, left = nd, rng.randint(20, 120)
        left -= 1
        o = p + gap + rng.gauss(0, vol * 0.1)
        cl = o + drift + rng.gauss(0, vol)
        hi = max(o, cl) + abs(rng.gauss(0, vol * 0.3))
        lw = min(o, cl) - abs(rng.gauss(0, vol * 0.3))
        if i % 4 == 3 and i > 400 and rng.random() < 0.08:
            w = vol * rng.uniform(10, 60)
            if drift > 0:
                lw = min(o, cl) - w
            else:
                hi = max(o, cl) + w
        bars.append(dict(o=o, h=hi, l=lw, c=cl, v=rng.randint(1, 50)))
        p = cl
    return bars


def main():
    src = open(os.path.join(ROOT, "tests", "sats_src", "f_satBand.txt"), encoding="utf-8").read()
    pine = open(os.path.join(ROOT, "SatsShortSignal.pine"), encoding="utf-8").read()
    check("f_satBand() byte-identical to the SAT BAND Reconstruction Test source", src in pine)
    code = "\n".join(ln.split("//")[0] for ln in pine.splitlines())
    check("no realtime-only gate / varip left (code lines)", "barstate.isrealtime" not in code and "varip" not in code)

    # ---- 2. start-of-bar formulas vs the f_satBand() port ---------------------------------------------------------------
    rng = random.Random(7)
    bad_anchor = bad_line = bad_stb = bad_indep = 0
    n_cmp = 0
    for trial in range(30):
        bars = rand_bars(rng, 260, vol=rng.choice([0.3, 1.0, 3.0]))
        ser = sat_series(bars)
        for i in range(60, len(bars) - 1):
            p, nx = ser[i]["prep"], ser[i + 1]
            n_cmp += 1
            if (p["a1n"], p["d1s"], p["a2n"], p["d2s"]) != (nx["a1"], nx["d1"], nx["a2"], nx["d2"]):
                bad_anchor += 1
            if abs((p["l1s"] - ser[i]["common"]) - (nx["l1"] - nx["common"])) > 1e-9:
                bad_line += 1
            # single-tick N: f_satBand() STB on N == start STB
            o = bars[i + 1]["o"]
            tick = bars[:i + 1] + [dict(o=o, h=o, l=o, c=o, v=1)]
            ser_t = sat_series(tick)
            ms, mb, stS, sdS, sbS = f_evt(o, p)
            if (sdS, sbS) != (ser_t[-1]["sd"], ser_t[-1]["stb"]):
                bad_stb += 1
            # N's high / low / close / volume changed -> start state unchanged
            alt = bars[:i + 1] + [dict(o=o, h=o + 50, l=o - 50, c=o + 7, v=999)]
            p_alt = sat_series(alt)[i]["prep"]
            if f_evt(o, p_alt) != (ms, mb, stS, sdS, sbS):
                bad_indep += 1
            if i > 80:
                break  # the single-tick re-run is O(n); sample 20 bars per trial
    check(f"LINE1/LINE2 start anchor+dir == f_satBand() on N ({n_cmp} bars)", bad_anchor == 0)
    check("start line = N anchor + P common (differs from full-bar line only by common)", bad_line == 0)
    check("STB start dir/price == f_satBand() STB on a single-tick N", bad_stb == 0)
    check("start state independent of N's high/low/close/volume", bad_indep == 0)

    # ---- condition unit cases (hand-made prep) --------------------------------------------------------------------------
    base = dict(okP=True, hh20=200.0, ll20=0.0, hh9=150.0, ll9=50.0)
    o = 100.0
    # SELL: prev blue, LINE2 +1 -> -1 above open, LINE1 below open stays +1, STB +1 with ll9 50 (< open) -> band 0
    p = dict(base, st=1, d1=1, d2=1, sd=1, d1s=1, d2s=-1, l1s=90.0, l2s=110.0)
    check("SELL: prev blue, start no-band, LINE2 blue->red above open -> mask L2", f_evt(o, p)[:3] == (2, 0, 0))
    p2 = dict(p, l2s=95.0, l1s=105.0, d1s=1)  # L2 flips but is below open; L1 above open but did not flip
    check("SELL: flipped line below open, other line above -> no event", f_evt(o, p2)[0] == 0)
    p3 = dict(p, l2s=99.0, l1s=98.0, d2s=1, sd=1, hh20=200.0, ll20=100.5, hh9=120.0)  # open < ll20 -> STB -1 at max(o,hh9)=120
    check("SELL: only STB blue->red (open below prev 20 low) above open -> mask STB", f_evt(o, p3)[:3] == (4, 0, 0))
    p4 = dict(p, l1s=101.0, l2s=110.0)
    p4 = dict(p4, sd=-1, hh9=105.0)   # STB already red, at 105 above open -> all 3 above -> start band -1
    check("SELL: start band red (-1) -> no event", f_evt(o, p4)[0] == 0 and f_evt(o, p4)[2] == -1)
    p5 = dict(p, l2s=100.0)
    check("SELL: line price == open -> no event", f_evt(o, p5)[0] == 0)
    pb = dict(base, st=-1, d1=-1, d2=-1, sd=-1, d1s=1, d2s=-1, l1s=90.0, l2s=110.0)
    check("BUY: prev red, LINE1 red->blue below open, band 0 -> mask L1", f_evt(o, pb)[:3] == (0, 1, 0))
    check("BUY conditions do not trigger SELL on a blue prev bar", f_evt(o, dict(pb, st=1))[:2] == (0, 0))

    # ---- 3. sequencing ----------------------------------------------------------------------------------------------------
    T0 = 10 * M
    r = chart_run(scripted({(15, T0): "S", (30, T0): "S", (60, T0): "S"}))
    check("SELL: 15s/30s/1m at the same start time -> one SELL on that 15s bar", r == [(0, "SELL", (T0, T0, T0))])
    r = chart_run(scripted({(15, T0): "B", (30, T0): "B", (60, T0): "B"}))
    check("BUY: 15s/30s/1m at the same start time -> one BUY", r == [(0, "BUY", (T0, T0, T0))])
    r = chart_run(scripted({(15, T0): "S", (30, T0 + 2 * M): "S", (60, T0 + 5 * M): "S"}))
    check("1m exactly 5 min after 15s -> SELL (on the 15s bar where the 1m bar starts)", r == [(20, "SELL", (T0, T0 + 2 * M, T0 + 5 * M))])
    r = chart_run(scripted({(15, T0 + S15): "B", (30, T0 + M): "B", (60, T0 + 6 * M): "B"}, n_bars=30))
    check("1m 5m45s after 15s -> no BUY", r == [])
    r = chart_run(scripted({(15, T0 + S15): "B", (30, T0 + M): "B", (60, T0 + 6 * M): "B"}, n_bars=30), wait_min=6)
    check("same with wait 6 -> BUY", len(r) == 1)
    r = chart_run(scripted({(15, T0): "S", (30, T0 + M): "B", (60, T0 + 2 * M): "S"}))
    check("SELL 15s + BUY 30s + SELL 1m -> nothing (directions do not mix)", r == [])
    r = chart_run(scripted({(15, T0): "B", (30, T0 + M): "S", (60, T0 + 2 * M): "B"}))
    check("BUY 15s + SELL 30s + BUY 1m -> nothing", r == [])
    r = chart_run(scripted({(15, T0): "S", (15, T0 + S15): "B", (30, T0 + 30_000): "SB", (60, T0 + M): "SB"}))
    check("interleaved SELL and BUY chains -> one SELL and one BUY on the same bar",
          sorted(x[1] for x in r) == ["BUY", "SELL"] and all(x[0] == 4 for x in r))
    r = chart_run(scripted({(30, T0): "S", (15, T0 + S15): "S", (60, T0 + M): "S"}))
    check("30s before 15s, no later 30s -> no SELL", r == [])
    r = chart_run(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + M + S15): "S", (60, T0 + 6 * M): "S"}, n_bars=30))
    check("newer 15s does not move the pair's deadline (expires)", r == [])
    r = chart_run(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + M + S15): "S", (30, T0 + 2 * M): "S",
                            (60, T0 + 6 * M): "S"}, n_bars=30))
    check("new 30s with newer valid 15s updates the pair -> SELL", r == [(24, "SELL", (T0 + M + S15, T0 + 2 * M, T0 + 6 * M))])
    r = chart_run(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + M): "S", (60, T0 + 2 * M): "S"}))
    check("after a SELL the next 1m needs new 15s/30s", len(r) == 1)
    # a red line turning back blue later: the recorded event is history; nothing re-evaluates it (no event = no change)
    r = chart_run(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + 3 * M): "S"}))
    check("intermediate bars without events (line back to blue) keep the record -> SELL", len(r) == 1)

    # ---- 4. random end-to-end (15s -> 30s / 1m aggregation, request [1] + lookahead_on model) ----------------------------
    def e2e(b15):
        n = len(b15)
        T = [T0 + i * S15 for i in range(n)]

        def agg(step):
            g = {}
            for t, b in zip(T, b15):
                k = t - t % step
                if k not in g:
                    g[k] = dict(o=b["o"], h=b["h"], l=b["l"], c=b["c"], v=b["v"])
                else:
                    x = g[k]; x["h"] = max(x["h"], b["h"]); x["l"] = min(x["l"], b["l"]); x["c"] = b["c"]; x["v"] += b["v"]
            ks = sorted(g)
            return ks, [g[k] for k in ks]
        k30, b30 = agg(30_000)
        k60, b60 = agg(M)
        s15, s30, s60 = sat_series(b15), sat_series(b30), sat_series(b60)
        i30 = {k: j for j, k in enumerate(k30)}
        i60 = {k: j for j, k in enumerate(k60)}
        rows, ev = [], {}
        for i, t in enumerate(T):
            e15 = f_evt(b15[i]["o"], s15[i - 1]["prep"] if i else None)[:2]
            t30 = t - t % 30_000; j = i30[t30]
            e30 = f_evt(b30[j]["o"], s30[j - 1]["prep"] if j else None)[:2]
            t60 = t - t % M; q = i60[t60]
            e60 = f_evt(b60[q]["o"], s60[q - 1]["prep"] if q else None)[:2]
            rows.append((t, e15, t30, e30, t60, e60))
            for tf, tt, e in ((15, t, e15), (30, t30, e30), (60, t60, e60)):
                if e[0]:
                    ev[(tf, tt, "S")] = 1
                if e[1]:
                    ev[(tf, tt, "B")] = 1
        sig = chart_run(rows)
        bad = 0
        for (i, d, (a, b_, c)) in sig:
            k = "S" if d == "SELL" else "B"
            ok = a <= b_ <= c and c - a <= 5 * M and T[i] == c and (15, a, k) in ev and (30, b_, k) in ev and (60, c, k) in ev
            bad += 0 if ok else 1
        return sig, ev, bad

    tot = {"SELL": 0, "BUY": 0}
    evts = {"S": 0, "B": 0}
    bad = 0
    mir_bad = 0
    for trial in range(40):
        rng2 = random.Random(100 + trial)
        b15 = regime_bars(rng2, 2400, vol=rng2.choice([0.3, 0.8]))
        sig, ev, bd = e2e(b15)
        bad += bd
        for (_, _, d) in ev:
            evts[d] += 1
        for x in sig:
            tot[x[1]] += 1
    print(f"   random: single-TF events S={evts['S']} B={evts['B']}  signals SELL={tot['SELL']} BUY={tot['BUY']}")
    check("random end-to-end: every signal is a same-direction 15s<=30s<=1m chain within 5 min, on the 1m start bar", bad == 0)
    check("random end-to-end: both SELL and BUY signals appear in history", tot["SELL"] > 0 and tot["BUY"] > 0)

    # BUY is the exact mirror of SELL inside f_evt (random start states; price -> K - price, directions / states negated).
    # (Whole-series mirroring is not exact because f_satBand() itself is asymmetric: dirs start at +1 and STB favours +1 when
    #  a bar breaks both the 20-bar high and low — that is why the planted-wick data above yields far more SELL than BUY.)
    rng3 = random.Random(3)
    mir_bad = hits = 0
    K = 1000.0
    for _ in range(200_000):
        def r():
            return rng3.choice([90.0, 95.0, 99.0, 100.0, 101.0, 105.0, 110.0])
        pr = dict(okP=True, st=rng3.choice([1, 0, -1]), d1=rng3.choice([1, -1]), d2=rng3.choice([1, -1]), sd=rng3.choice([1, -1]),
                  d1s=rng3.choice([1, -1]), d2s=rng3.choice([1, -1]), l1s=r(), l2s=r(), hh20=r(), ll20=r(), hh9=r(), ll9=r())
        if pr["ll20"] > pr["hh20"] or pr["ll9"] > pr["hh9"]:
            continue
        o = 100.0
        mp = dict(okP=True, st=-pr["st"], d1=-pr["d1"], d2=-pr["d2"], sd=-pr["sd"], d1s=-pr["d1s"], d2s=-pr["d2s"],
                  l1s=K - pr["l1s"], l2s=K - pr["l2s"], hh20=K - pr["ll20"], ll20=K - pr["hh20"], hh9=K - pr["ll9"], ll9=K - pr["hh9"])
        e, em = f_evt(o, pr), f_evt(K - o, mp)
        hits += 1 if (e[0] or e[1]) else 0
        if (e[0], e[1], None if e[2] is None else -e[2]) != (em[1], em[0], em[2]):
            mir_bad += 1
    check(f"f_evt: mirrored start state swaps SELL/BUY masks and negates the start band ({hits} events)", mir_bad == 0 and hits > 0)

    badn = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(badn)}/{len(RESULTS)} passed")
    return 1 if badn else 0


if __name__ == "__main__":
    raise SystemExit(main())
