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
import re
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


NONE, WAIT, RCV, LOST = 0, 1, 2, 3


def chart_run(rows, wait_min=5, live=False):
    """Mirror of the SSS-3 Pine row queue. rows: one dict per chart update (normally one per 15s bar):
        t (15s bar time), e15=(ms, mb), need30 / need60 (start time if time("30S") / time("1") switched on this bar),
        r30 / r60 = (cur_t, cur_ms, cur_mb, prev_t, prev_ms, prev_mb) delivered by request.security (or None),
        now (optional live clock for the tooltip; only used when live=True).
    Returns (signals, lost): signals = [(mark_x = 1m start, 'SELL'|'BUY', (t15, t30, t60), chart_t_detected, live_t)],
    lost = [(tf, start_t, reason, chart_t)]."""
    W = wait_min * M
    sS, sB = Seq(), Seq()
    Q = []  # rows: dict
    last_row = None
    sig, lost = [], []
    for r in rows:
        T = r["t"]
        live_t = r.get("now", T) if live else None
        # 1. add the row once per 15s time
        if last_row != T:
            last_row = T
            Q.append(dict(t=T, s15=r["e15"][0], b15=r["e15"][1],
                          c={30: [r.get("need30"), WAIT if r.get("need30") is not None else NONE, 0, 0],
                             60: [r.get("need60"), WAIT if r.get("need60") is not None else NONE, 0, 0]}))
        # 2. match current and previous bar data into WAIT cells with the same start time only
        for tf, key in ((30, "r30"), (60, "r60")):
            d = r.get(key)
            if not d:
                continue
            for (tt, ms, mb) in ((d[0], d[1], d[2]), (d[3], d[4], d[5])):
                if tt is None:
                    continue
                for row in Q:
                    c = row["c"][tf]
                    if c[1] == WAIT and c[0] == tt:
                        c[1], c[2], c[3] = RCV, ms, mb
        # 3. lost
        for tf, key in ((30, "r30"), (60, "r60")):
            d = r.get(key)
            prv = d[3] if d else None
            for row in Q:
                c = row["c"][tf]
                if c[1] == WAIT:
                    why = "prev" if (prv is not None and prv > c[0]) else "3min" if T - c[0] >= 180_000 else None
                    if why:
                        c[1] = LOST
                        lost.append((tf, c[0], why, T))
        # 4. process from the oldest row
        while Q and all(Q[0]["c"][tf][1] != WAIT for tf in (30, 60)):
            row = Q.pop(0)
            tr = row["t"]
            items = [(tr, 0, row["s15"], row["b15"])]
            for rank, tf in ((1, 30), (2, 60)):
                c = row["c"][tf]
                if c[1] != NONE:
                    items.append((c[0], rank, c[2] if c[1] == RCV else 0, c[3] if c[1] == RCV else 0))
            for (t, rank, ms, mb) in sorted(items, key=lambda x: (x[0], x[1])):
                if rank == 0:
                    sS.on15(t, ms, W); sB.on15(t, mb, W)
                elif rank == 1:
                    sS.on30(t, ms, W); sB.on30(t, mb, W)
                else:
                    rs = sS.on60(t, ms, W); rb = sB.on60(t, mb, W)
                    if rs:
                        sig.append((t, "SELL", rs, T, live_t))
                    if rb:
                        sig.append((t, "BUY", rb, T, live_t))
    return sig, lost


def build_rows(n_bars, ev15, ev30, ev60, t0=10 * M, delay30=None, delay60=None):
    """Chart rows for scripted cases. ev*: {start_t: 'S'|'B'|'SB'}. delay*: {start_t: ms} visibility delay of that HTF bar
    (float('inf') = never delivered). Visibility is made monotone (a later bar is never visible before an earlier one), and the
    request returns the latest visible bar as current and its predecessor as previous."""
    def mask(ev, t):
        e = ev.get(t, "")
        return (2 if "S" in e else 0, 1 if "B" in e else 0)
    ts = [t0 + i * S15 for i in range(n_bars)]

    def htf(step, ev, delay):
        starts = sorted({t - t % step for t in ts})
        vis, mx = [], float("-inf")
        for k in starts:
            v = k + (delay or {}).get(k, 0)
            mx = max(mx, v)
            vis.append(mx)
        return starts, vis, [mask(ev, k) for k in starts]
    h30, h60 = htf(30_000, ev30, delay30), htf(M, ev60, delay60)

    def deliver(h, T):
        starts, vis, m = h
        j = max([i for i, v in enumerate(vis) if v <= T], default=None)
        if j is None:
            return None
        pt, pm = (starts[j - 1], m[j - 1]) if j else (None, (0, 0))
        return (starts[j], m[j][0], m[j][1], pt, pm[0], pm[1])
    rows = []
    for i, T in enumerate(ts):
        rows.append(dict(t=T, e15=mask(ev15, T),
                         need30=T if T % 30_000 == 0 else None, need60=T if T % M == 0 else None,
                         r30=deliver(h30, T), r60=deliver(h60, T)))
    return rows


def fast_rows(ts, ev15, ev30, ev60, k30, k60, d30=None, d60=None):
    """build_rows() for long series (bisect delivery)."""
    import bisect

    def mask(ev, t):
        e = ev.get(t, "")
        return (2 if "S" in e else 0, 1 if "B" in e else 0)

    def htf(starts, ev, delay):
        vis, mx = [], float("-inf")
        for k in starts:
            mx = max(mx, k + (delay or {}).get(k, 0))
            vis.append(mx)
        return starts, vis, [mask(ev, k) for k in starts]

    def deliver(h, T):
        starts, vis, m = h
        j = bisect.bisect_right(vis, T) - 1
        if j < 0:
            return None
        pt, pm = (starts[j - 1], m[j - 1]) if j else (None, (0, 0))
        return (starts[j], m[j][0], m[j][1], pt, pm[0], pm[1])
    h30, h60 = htf(k30, ev30, d30), htf(k60, ev60, d60)
    return [dict(t=T, e15=mask(ev15, T), need30=T if T % 30_000 == 0 else None, need60=T if T % M == 0 else None,
                 r30=deliver(h30, T), r60=deliver(h60, T)) for T in ts]


def scripted(events, n_bars=60, t0=10 * M):
    """events: {(tf, t): 'S'|'B'|'SB'} -> rows without delays (history)."""
    ev = {15: {}, 30: {}, 60: {}}
    for (tf, t), e in events.items():
        ev[tf][t] = e
    return build_rows(n_bars, ev[15], ev[30], ev[60], t0)


def sigs(rows, **kw):
    """(bar index of the anchor, dir, times) — comparable with the pre-queue expectations."""
    sig, _ = chart_run(rows, **kw)
    t0 = rows[0]["t"]
    return [((a - t0) // S15, d, tt) for (a, d, tt, _, _) in sig]


# ---- the Pine row-processing code itself, run through the mechanical translator of tests/acc_pine.py ------------------------
def pine_rows_runner(src):
    """Transpile SatsShortSignal.pine from f_lines() to the start of the '取得' section and from '処理待ちの行' to '印の描画'
    (wait-state helpers, varip rows, matching, lost check, row processing). Returns run(updates, live) -> (log, marks), where
    log = [(tf, start_t, chart_t)] in the order Pine calls f_on15 / f_on30 / f_on60, marks = [(x, kind, tooltip)]."""
    import acc_pine as ap
    a = src.index("f_lines(int m) =>")
    b = src.index("// ---- 取得 (毎足")
    c = src.index("// ---- 処理待ちの行")
    d = src.index("// ---- 印の描画")
    py = ap.Translator().translate(ap.logical_lines(src[a:b] + src[c:d]))
    for f, tag in (("f_on15", 15), ("f_on30", 30), ("f_on60", 60)):
        py = py.replace(f"def {f}(", f"def _orig_{f}(", 1)
        py = f"def {f}(*a):\n    LOG.append(({tag}, a[1], time))\n    return _orig_{f}(*a)\n" + py
    code = compile(py, "SatsShortSignal.pine<rows>", "exec")

    class _NoBroker:
        def __getattr__(self, k):
            return lambda *a, **kw: None

    def run(updates, live=False):
        env = ap.make_env(_NoBroker(), [])
        env.update(_VARS=set(), _VARIPS=set(), LOG=[], syminfo__timezone="UTC", waitMin=5, showEvt=False, chartOk=True,
                   timeframe__in_seconds=lambda *x: 15, array__new_string=lambda n=0, v=None: [v] * n,
                   str__format_time=lambda t, f, tz: f.replace("HH", "%02d" % (t // 3600_000 % 24))
                   .replace("mm", "%02d" % (t // 60_000 % 60)).replace("ss", "%02d" % (t // 1000 % 60)))
        first = True
        for u in updates:
            env.update(__first__=first, time=u["t"], barstate__isrealtime=live, timenow=u.get("now", u["t"]),
                       ms15=u["e15"][0], mb15=u["e15"][1],
                       new30=u.get("need30") is not None, need30T=u.get("need30"),
                       new60=u.get("need60") is not None, need60T=u.get("need60"))
            for tf in (30, 60):
                r = u.get(f"r{tf}") or (None, 0, 0, None, 0, 0)
                env.update({f"t{tf}": r[0], f"ms{tf}": r[1], f"mb{tf}": r[2], f"t{tf}p": r[3], f"ms{tf}p": r[4], f"mb{tf}p": r[5]})
            exec(code, env)
            first = False
        marks = [(x, k, tip) for x, k, tip in zip(env["mkX"], env["mkK"], env["mkTip"])]
        return env["LOG"], marks
    return run


def gap_case(d):
    """SELL ('S') / BUY ('B') regression series: 15s 10:00:00 + 30s 10:00:30 pair, new 15s 10:00:45, next observed 15s bar
    10:01:45 whose row holds the 1m 10:01:00 and the 30s 10:01:30 (all same direction)."""
    T = 10 * 3600_000
    m = (2, 0) if d == "S" else (0, 2)
    z = (0, 0)
    u = []
    u.append(dict(t=T, e15=m, need30=T, need60=T, r30=(T, 0, 0, T - 30_000, 0, 0), r60=(T, 0, 0, T - M, 0, 0)))
    u.append(dict(t=T + 15_000, e15=z, r30=(T, 0, 0, T - 30_000, 0, 0), r60=(T, 0, 0, T - M, 0, 0)))
    u.append(dict(t=T + 30_000, e15=z, need30=T + 30_000, r30=(T + 30_000, *m, T, 0, 0), r60=(T, 0, 0, T - M, 0, 0)))
    u.append(dict(t=T + 45_000, e15=m, r30=(T + 30_000, *m, T, 0, 0), r60=(T, 0, 0, T - M, 0, 0)))
    u.append(dict(t=T + 105_000, e15=z, need30=T + 90_000, need60=T + M,
                  r30=(T + 90_000, *m, T + 30_000, *m), r60=(T + M, *m, T, 0, 0)))
    return T, u


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
    check("processing is not gated on realtime (barstate.isrealtime only selects the live detection time)",
          code.count("barstate.isrealtime") == 1 and "barstate.isrealtime ? timenow : na" in code)
    check("rows, wait state and mark reservations are varip (no rollback)",
          all(re.search(r"^varip array<int>\s+" + v + r"\s*=", code, re.M) for v in ("rT", "rC30", "rC60", "sqS", "sqB", "mkBar")))

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
    r = sigs(scripted({(15, T0): "S", (30, T0): "S", (60, T0): "S"}))
    check("SELL: 15s/30s/1m at the same start time -> one SELL on that 15s bar", r == [(0, "SELL", (T0, T0, T0))])
    r = sigs(scripted({(15, T0): "B", (30, T0): "B", (60, T0): "B"}))
    check("BUY: 15s/30s/1m at the same start time -> one BUY", r == [(0, "BUY", (T0, T0, T0))])
    r = sigs(scripted({(15, T0): "S", (30, T0 + 2 * M): "S", (60, T0 + 5 * M): "S"}))
    check("1m exactly 5 min after 15s -> SELL (on the 15s bar where the 1m bar starts)", r == [(20, "SELL", (T0, T0 + 2 * M, T0 + 5 * M))])
    r = sigs(scripted({(15, T0 + S15): "B", (30, T0 + M): "B", (60, T0 + 6 * M): "B"}, n_bars=30))
    check("1m 5m45s after 15s -> no BUY", r == [])
    r = sigs(scripted({(15, T0 + S15): "B", (30, T0 + M): "B", (60, T0 + 6 * M): "B"}, n_bars=30), wait_min=6)
    check("same with wait 6 -> BUY", len(r) == 1)
    r = sigs(scripted({(15, T0): "S", (30, T0 + M): "B", (60, T0 + 2 * M): "S"}))
    check("SELL 15s + BUY 30s + SELL 1m -> nothing (directions do not mix)", r == [])
    r = sigs(scripted({(15, T0): "B", (30, T0 + M): "S", (60, T0 + 2 * M): "B"}))
    check("BUY 15s + SELL 30s + BUY 1m -> nothing", r == [])
    r = sigs(scripted({(15, T0): "S", (15, T0 + S15): "B", (30, T0 + 30_000): "SB", (60, T0 + M): "SB"}))
    check("interleaved SELL and BUY chains -> one SELL and one BUY on the same bar",
          sorted(x[1] for x in r) == ["BUY", "SELL"] and all(x[0] == 4 for x in r))
    r = sigs(scripted({(30, T0): "S", (15, T0 + S15): "S", (60, T0 + M): "S"}))
    check("30s before 15s, no later 30s -> no SELL", r == [])
    r = sigs(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + M + S15): "S", (60, T0 + 6 * M): "S"}, n_bars=30))
    check("newer 15s does not move the pair's deadline (expires)", r == [])
    r = sigs(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + M + S15): "S", (30, T0 + 2 * M): "S",
                            (60, T0 + 6 * M): "S"}, n_bars=30))
    check("new 30s with newer valid 15s updates the pair -> SELL", r == [(24, "SELL", (T0 + M + S15, T0 + 2 * M, T0 + 6 * M))])
    r = sigs(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + M): "S", (60, T0 + 2 * M): "S"}))
    check("after a SELL the next 1m needs new 15s/30s", len(r) == 1)
    # a red line turning back blue later: the recorded event is history; nothing re-evaluates it (no event = no change)
    r = sigs(scripted({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + 3 * M): "S"}))
    check("intermediate bars without events (line back to blue) keep the record -> SELL", len(r) == 1)

    # ---- 4. delivery order (SSS-3): rows keyed by the 15s time, 30s / 1m cells matched by start time ---------------------------
    T1 = 10 * 3600_000   # 10:00:00 (UTC-free arithmetic; only differences matter)

    def proj(sg):
        return [(x[0], x[1], x[2]) for x in sg]
    # case 1: 15s at 10:00:00; the 30s bar starting 10:00:30 arrives at 10:00:45 with a new 15s event at 10:00:45
    rows = build_rows(12, {T1: "S", T1 + 45_000: "S"}, {T1 + 30_000: "S"}, {T1 + M: "S"}, T1, delay30={T1 + 30_000: 15_000})
    sg, lost = chart_run(rows)
    check("case 1: late 30s (10:00:30, arrives 10:00:45) pairs with the 10:00:00 15s; the 10:00:45 15s does not overwrite it",
          proj(sg) == [(T1 + M, "SELL", (T1, T1 + 30_000, T1 + M))] and not lost)
    rows = build_rows(12, {T1: "B", T1 + 45_000: "B"}, {T1 + 30_000: "B"}, {T1 + M: "B"}, T1, delay30={T1 + 30_000: 15_000})
    check("case 1 (BUY): same pairing", proj(chart_run(rows)[0]) == [(T1 + M, "BUY", (T1, T1 + 30_000, T1 + M))])
    # case 2: same start time; the 1m data arrives before the 30s data
    for d, nm in (("S", "SELL"), ("B", "BUY")):
        rows = build_rows(12, {T1: d}, {T1: d}, {T1: d}, T1, delay30={T1: 30_000})
        sg, lost = chart_run(rows)
        check(f"case 2 ({nm}): 1m before 30s at the same start -> one {nm} when the 30s arrives, marked at the 1m start",
              proj(sg) == [(T1, nm, (T1, T1, T1))] and sg[0][3] == T1 + 30_000 and not lost)
    # 30s arrives late with NO event: hold released (the following 15s rows are processed)
    rows = build_rows(12, {T1 + S15: "S"}, {}, {}, T1, delay30={T1: 30_000})
    Q_after = chart_run(rows)
    check("case 2: a late 30s without an event is still 'received' and releases the hold (nothing lost)", Q_after[1] == [])
    # case 3: 1m bar starting exactly 5 min after the 15s event, its data arriving 45 s late
    for d, nm in (("S", "SELL"), ("B", "BUY")):
        rows = build_rows(30, {T1: d}, {T1 + 2 * M: d}, {T1 + 5 * M: d}, T1, delay60={T1 + 5 * M: 45_000})
        for rw in rows:
            rw["now"] = rw["t"] + 3_000
        sg, lost = chart_run(rows, live=True)
        check(f"case 3 ({nm}): late 1m at exactly 5 min is judged by its start time -> {nm} marked at the 1m start, "
              "live detection 45 s later",
              proj(sg) == [(T1 + 5 * M, nm, (T1, T1 + 2 * M, T1 + 5 * M))] and sg[0][3] == T1 + 5 * M + 45_000 and not lost)
        sg_h, _ = chart_run(build_rows(30, {T1: d}, {T1 + 2 * M: d}, {T1 + 5 * M: d}, T1))
        check(f"case 3 ({nm}): reload (history, no delay) -> same mark at the 1m start, no live detection time",
              proj(sg_h) == proj(sg) and sg_h[0][4] is None)
    # case 4a: recovery from the previous-bar data (30s delay crossing the next 30s start)
    rows = build_rows(12, {T1: "S"}, {T1 + 30_000: "S"}, {T1 + M: "S"}, T1, delay30={T1 + 30_000: 35_000})
    sg, lost = chart_run(rows)
    check("case 4: 30s data recovered from the request's previous-bar slot", proj(sg) == [(T1 + M, "SELL", (T1, T1 + 30_000, T1 + M))]
          and not lost)
    # case 4b: lost because the previous-bar start strictly passed the waited start; processing resumes
    rows = build_rows(30, {T1: "S", T1 + 2 * M: "S"}, {T1 + 30_000: "S", T1 + 2 * M + 30_000: "S"}, {T1 + 3 * M: "S"}, T1,
                      delay30={T1 + 30_000: 60_000})
    sg, lost = chart_run(rows)
    check("case 4: request jumps two 30s bars -> 30s 10:00:30 lost by 'previous bar passed', later chain still signals",
          (30, T1 + 30_000, "prev") in [(x[0], x[1], x[2]) for x in lost]
          and proj(sg) == [(T1 + 3 * M, "SELL", (T1 + 2 * M, T1 + 2 * M + 30_000, T1 + 3 * M))])
    # case 4c: lost after 3 minutes of chart time (feed stalls), queue drains; data arriving after the loss is ignored
    rows = build_rows(40, {T1: "S"}, {T1 + 30_000: "S"}, {}, T1, delay30={T1 + 30_000: float("inf")})
    sg, lost = chart_run(rows)
    first = [x for x in lost if x[1] == T1 + 30_000]
    check("case 4: 30s feed stalls -> lost at exactly 3 min of chart time ('3min'), queue drains",
          first and first[0][2] == "3min" and first[0][3] - T1 - 30_000 == 180_000)
    rows = build_rows(40, {T1: "S"}, {T1 + 30_000: "S"}, {T1 + 5 * M: "S"}, T1, delay30={T1 + 30_000: float("inf")})
    late = dict(rows[20])  # 10:05:00: inject the long-lost 10:00:30 30s data (with an event) as 'previous bar'
    late["r30"] = (T1 + 5 * M, 0, 0, T1 + 30_000, 2, 0)
    rows[20] = late
    sg, lost = chart_run(rows)
    check("case 4: data for a cell already marked lost is not processed (no SELL from it)", sg == [])
    # case 4d: duplicate delivery (same start delivered again with different masks on later updates) does not overwrite
    rows = build_rows(12, {T1: "S"}, {T1 + 30_000: "S"}, {T1 + M: "S"}, T1)
    dup = dict(rows[3])
    dup["r30"] = (T1 + 30_000, 0, 1, T1, 0, 0)   # a second update of 10:00:45 claiming the 30s had no SELL
    rows.insert(4, dup)
    sg, _ = chart_run(rows)
    check("case 4: duplicate receipt of an already received 30s cell is ignored", proj(sg) == [(T1 + M, "SELL", (T1, T1 + 30_000, T1 + M))])
    # several rows processed in one update: all marks shown
    rows = build_rows(12, {T1: "SB"}, {T1: "S", T1 + 30_000: "B"}, {T1 + M: "SB"}, T1,
                      delay30={T1: 45_000, T1 + 30_000: 15_000}, delay60={T1: 45_000})
    sg, lost = chart_run(rows)
    check("several rows released by one update (10:00:45 brings 30s 10:00:00 / 10:00:30 and 1m 10:00:00) -> both the SELL and the BUY marks, at the 1m start",
          sorted(proj(sg)) == [(T1 + M, "BUY", (T1, T1 + 30_000, T1 + M)), (T1 + M, "SELL", (T1, T1, T1 + M))] and not lost)

    # ---- 4e. SSS-4: events inside one row in start-time order (Pine code itself via tests/acc_pine.py) ---------------------
    import subprocess
    old_src = subprocess.run(["git", "-C", ROOT, "show", "6b5e516:SatsShortSignal.pine"], capture_output=True, text=True).stdout
    run_new = pine_rows_runner(pine)
    run_old = pine_rows_runner(old_src) if old_src else None
    for d, nm in (("S", "SELL"), ("B", "BUY")):
        T, ups = gap_case(d)
        log, marks = run_new(ups)
        last = [(tf, t - T) for (tf, t, ct) in log if ct == T + 105_000]
        sig = [(x - T, k, tip.split(chr(10))[1:4]) for (x, k, tip) in marks if k in (1, -1)]
        k = 1 if d == "S" else -1
        print(f"   Pine order on the 10:01:45 row ({nm}): {last}")
        check(f"SSS-4 ({nm}): Pine processes the 10:01:45 row as 1m 10:01:00 -> 30s 10:01:30 -> 15s 10:01:45 (x2: SELL+BUY waits)",
              last == [(60, 60_000), (60, 60_000), (30, 90_000), (30, 90_000), (15, 105_000), (15, 105_000)])
        check(f"SSS-4 ({nm}): one {nm} mark at 10:01:00 from the original pair 10:00:00 / 10:00:30",
              [(x, kk) for (x, kk, _) in sig] == [(60_000, k)] and sig[0][2] == ["15s L2 10:00:00", "30s L2 10:00:30", "1m L2 10:01:00"])
        sg, _ = chart_run(ups)
        check(f"SSS-4 ({nm}): Python model agrees (same mark and pair)",
              [(x[0] - T, x[1], tuple(t - T for t in x[2])) for x in sg] == [(60_000, nm, (0, 30_000, 60_000))])
        if run_old:
            log_o, marks_o = run_old(ups)
            last_o = [(tf, t - T) for (tf, t, ct) in log_o if ct == T + 105_000]
            print(f"   6b5e516 order on that row ({nm}): {last_o}  marks: {[(x - T, kk) for (x, kk, _) in marks_o if kk in (1, -1)]}")
            check(f"SSS-4 ({nm}): regression reproduced on 6b5e516 (30s 10:01:30 before 1m 10:01:00, no mark)",
                  last_o[:2] == [(30, 90_000), (30, 90_000)] and not [m_ for m_ in marks_o if m_[1] in (1, -1)])
    # the translated Pine rows also reproduce the delivery cases above
    for nm, ups in (("case 1", build_rows(12, {T1: "S", T1 + 45_000: "S"}, {T1 + 30_000: "S"}, {T1 + M: "S"}, T1,
                                         delay30={T1 + 30_000: 15_000})),
                    ("case 2", build_rows(12, {T1: "B"}, {T1: "B"}, {T1: "B"}, T1, delay30={T1: 30_000})),
                    ("case 3", build_rows(30, {T1: "S"}, {T1 + 2 * M: "S"}, {T1 + 5 * M: "S"}, T1, delay60={T1 + 5 * M: 45_000})),
                    ("lost", build_rows(30, {T1: "S", T1 + 2 * M: "S"}, {T1 + 30_000: "S", T1 + 2 * M + 30_000: "S"},
                                        {T1 + 3 * M: "S"}, T1, delay30={T1 + 30_000: 60_000}))):
        _, marks = run_new(ups)
        sg, _ = chart_run(ups)
        check(f"translated Pine == Python model on {nm} (mark positions / direction)",
              sorted((x, kk) for (x, kk, _) in marks if kk in (1, -1)) == sorted((x[0], 1 if x[1] == "SELL" else -1) for x in sg) and sg)

    # ---- 5. random end-to-end (15s -> 30s / 1m aggregation, request [time, evt, time[1], evt[1]] + lookahead_on model) -------
    def e2e(b15, rng=None, max_delay=0):
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

        def evmap(ks, bars, ser):
            out = {}
            for j, k in enumerate(ks):
                e = f_evt(bars[j]["o"], ser[j - 1]["prep"] if j else None)[:2]
                out[k] = ("S" if e[0] else "") + ("B" if e[1] else "")
            return out
        k30, b30 = agg(30_000)
        k60, b60 = agg(M)
        ev15 = evmap(T, b15, sat_series(b15))
        ev30 = evmap(k30, b30, sat_series(b30))
        ev60 = evmap(k60, b60, sat_series(b60))
        d30 = {k: rng.randint(0, max_delay) for k in k30} if rng else None
        d60 = {k: rng.randint(0, max_delay) for k in k60} if rng else None
        rows = fast_rows(T, ev15, ev30, ev60, k30, k60, d30, d60)
        sig, lost = chart_run(rows)
        ev = {(tf, t, c) for tf, m in ((15, ev15), (30, ev30), (60, ev60)) for t, e in m.items() for c in e}
        bad = 0
        for (anc, d, (a, b_, c), det, _) in sig:
            k = "S" if d == "SELL" else "B"
            ok = a <= b_ <= c and c - a <= 5 * M and anc == c and det >= c and (15, a, k) in ev and (30, b_, k) in ev and (60, c, k) in ev
            bad += 0 if ok else 1
        return sig, lost, ev, bad

    tot = {"SELL": 0, "BUY": 0}
    evts = {"S": 0, "B": 0}
    bad = 0
    delay_bad = 0
    lossy_bad = 0
    n_lost = 0
    for trial in range(40):
        rng2 = random.Random(100 + trial)
        b15 = regime_bars(rng2, 2400, vol=rng2.choice([0.3, 0.8]))
        sig, lost, ev, bd = e2e(b15)
        bad += bd + len(lost)
        for (_, _, d) in ev:
            evts[d] += 1
        for x in sig:
            tot[x[1]] += 1
        key = sorted((x[0], x[1], x[2]) for x in sig)
        if trial < 15:
            # realtime with random delivery delays up to 45 s (always recoverable from current / previous bar)
            sd, ld, _, bd = e2e(b15, random.Random(900 + trial), 45_000)
            bad += bd
            if sorted((x[0], x[1], x[2]) for x in sd) != key or ld:
                delay_bad += 1
            # delays up to 75 s: some 30s bars become unrecoverable -> lost; remaining signals must be a subset
            sl, ll, _, bd = e2e(b15, random.Random(1900 + trial), 75_000)
            bad += bd
            n_lost += len(ll)
    print(f"   random: single-TF events S={evts['S']} B={evts['B']}  signals SELL={tot['SELL']} BUY={tot['BUY']}  lost(75s runs)={n_lost}")
    check("random end-to-end: every signal is a same-direction 15s<=30s<=1m chain within 5 min, marked at the 1m start", bad == 0)
    check("random end-to-end: both SELL and BUY signals appear in history", tot["SELL"] > 0 and tot["BUY"] > 0)
    check("random delays <= 45 s give exactly the history (reload) signals at the same 1m start bars, nothing lost (15 runs)",
          delay_bad == 0)
    check("random delays <= 75 s: unrecoverable items are reported as lost and the queue keeps draining", n_lost > 0)

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
