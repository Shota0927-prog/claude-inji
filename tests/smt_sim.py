"""SMT-1 — Stoch MTF Signal (1M) (StochMtfSignal.pine) local verification.

Evidence class: PINE_NOT_VERIFIED. TradingView's compiler / request.security are not run here. What is checked:
  1. mt5_stochastic(): a line-by-line port of the MetaQuotes Stochastic.mq5 OnCalculate loops (Low/High, Simple),
     including its 0-initialised buffers, its 1000000 / -1000000 min / max seeds, the `rates_total <= K+D+S` gate
     and the incremental `prev_calculated - 2` restart. Compared with pine_stoch() (the Pine f_mtStoch, mirrored
     statement by statement) on the same OHLC: exact float equality on every value Pine reports.
  2. Pine mirror (pine_run): f_mtStoch / f_htf / f_pick / the 1M / 5M / 15M conditions, mirrored from the Pine text.
     PT-xx static checks tie the mirror to the Pine source (the mirrored lines must be present verbatim).
     request.security(lookahead_on) is emulated as TradingView documents it: the value of the higher-timeframe bar
     that contains the chart bar — on history that bar's final value, in realtime its developing value at the tick.
  3. Spec oracle (oracle_run): written from the request text, independent of the Pine structure: the 5M / 15M bar is
     the one with the latest close time <= T (T = the 1M bar's close time), its K comes from the MT5 port on that
     timeframe's own OHLC. Compared with the Pine mirror on random data (history and realtime emulation).
  4. Boundary cases with injected K / D values (decide()).
"""
import math
import os
import random
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "StochMtfSignal.pine")
SRC = open(PINE, encoding="utf-8").read()
MIN = 60_000

RESULTS = []


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not info else "  -- " + str(info)[:400]))


# ============================================================================
# 1. MT5 Stochastic.mq5 (MetaQuotes) port — arrays are time-ascending (not series), as in the indicator
# ============================================================================
class MT5Stoch:
    def __init__(self, k, d, s):
        self.K, self.D, self.S = k, d, s
        self.lo, self.hi, self.main, self.sig = [], [], [], []

    def _grow(self, n):
        for b in (self.lo, self.hi, self.main, self.sig):
            while len(b) < n:
                b.append(0.0)       # (buffer content before the first write is irrelevant: every read index is written first)

    def on_calculate(self, rates_total, prev_calculated, high, low, close):
        K, D, S = self.K, self.D, self.S
        self._grow(rates_total)
        if rates_total <= K + D + S:
            return 0
        start = K - 1
        if start + 1 < prev_calculated:
            start = prev_calculated - 2
        else:
            for i in range(0, start):
                self.lo[i] = 0.0
                self.hi[i] = 0.0
        for i in range(start, rates_total):
            dmin, dmax = 1000000.0, -1000000.0
            for k in range(i - K + 1, i + 1):
                if dmin > low[k]:
                    dmin = low[k]
                if dmax < high[k]:
                    dmax = high[k]
            self.lo[i], self.hi[i] = dmin, dmax
        start = K - 1 + S - 1
        if start + 1 < prev_calculated:
            start = prev_calculated - 2
        else:
            for i in range(0, start):
                self.main[i] = 0.0
        for i in range(start, rates_total):
            sum_low = 0.0
            sum_high = 0.0
            for k in range(i - S + 1, i + 1):
                sum_low += (close[k] - self.lo[k])
                sum_high += (self.hi[k] - self.lo[k])
            if sum_high == 0.0:
                self.main[i] = 100.0
            else:
                self.main[i] = sum_low / sum_high * 100
        start = D - 1
        if start + 1 < prev_calculated:
            start = prev_calculated - 2
        else:
            for i in range(0, start):
                self.sig[i] = 0.0
        for i in range(start, rates_total):
            s = 0.0
            for k in range(0, D):
                s += self.main[i - k]
            self.sig[i] = s / D
        return rates_total


def mt5_full(bars, k, d, s):
    m = MT5Stoch(k, d, s)
    n = m.on_calculate(len(bars), 0, [b["h"] for b in bars], [b["l"] for b in bars], [b["c"] for b in bars])
    return m, n


def mt5_incremental(bars, k, d, s):
    """Bars arrive one by one (prev_calculated = previous return value), as on a live MT5 chart."""
    m = MT5Stoch(k, d, s)
    prev = 0
    for n in range(1, len(bars) + 1):
        sub = bars[:n]
        prev = m.on_calculate(n, prev, [b["h"] for b in sub], [b["l"] for b in sub], [b["c"] for b in sub])
    return m


# ============================================================================
# 2. Pine mirror
# ============================================================================
def pine_stoch(bars, kPer, dPer, slow):
    """f_mtStoch on every bar of `bars` -> (main, sig) lists, None = na."""
    n = len(bars)
    ll = [None] * n
    hh = [None] * n
    for i in range(n):        # ta.lowest / ta.highest (never read before kPer bars exist: see guard below)
        if i >= kPer - 1:
            ll[i] = min(b["l"] for b in bars[i - kPer + 1:i + 1])
            hh[i] = max(b["h"] for b in bars[i - kPer + 1:i + 1])
    main = [None] * n
    sig = [None] * n
    for i in range(n):
        main[i] = pine_main_at(bars, ll, hh, i, kPer, slow)
        if i >= kPer + slow + dPer - 3:
            s = 0.0
            for j in range(0, dPer):
                s += main[i - j]
            sig[i] = s / dPer
    return main, sig


def pine_main_at(bars, ll, hh, i, kPer, slow):
    if i >= kPer + slow - 2:
        sLow = 0.0
        sHigh = 0.0
        for j in range(slow - 1, -1, -1):        # for j = slow - 1 to 0
            sLow += bars[i - j]["c"] - ll[i - j]
            sHigh += hh[i - j] - ll[i - j]
        return 100.0 if sHigh == 0.0 else sLow / sHigh * 100
    return None


def aggregate(bars1, tf_min, session_end=None):
    """Higher-timeframe bars built from the 1M bars present (the feed's own OHLC for the test). Close time = open + tf
    (TradingView's nominal time_close), cut at the session end when given."""
    out = []
    for b in bars1:
        t0 = b["t"] - b["t"] % (tf_min * MIN)
        if not out or out[-1]["t"] != t0:
            tc = t0 + tf_min * MIN
            if session_end is not None:
                tc = min(tc, session_end(t0))
            out.append({"t": t0, "tc": tc, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "n1": []})
        x = out[-1]
        x["h"], x["l"], x["c"] = max(x["h"], b["h"]), min(x["l"], b["l"]), b["c"]
        x["n1"].append(b)
    return out


def htf_tuple(hbars, main, h):
    """f_htf evaluated on higher-timeframe bar h: [m, m[1], m[2], m[3], time, time_close, time_close[1]]."""
    g = lambda j: main[h - j] if h - j >= 0 else None
    return [g(0), g(1), g(2), g(3), hbars[h]["t"], hbars[h]["tc"], hbars[h - 1]["tc"] if h >= 1 else None]


def f_pick(t, conf, c0, c1, c2, c3, hOpen, hClose, hClosePrev):
    k0 = k1 = k2 = rt = None
    if t is not None and hOpen is not None and hClose is not None:
        if conf and t >= hClose:
            k0, k1, k2, rt = c0, c1, c2, hClose
        else:
            k0, k1, k2, rt = c1, c2, c3, hClosePrev
    return k0, k1, k2, rt


class Security:
    """request.security(tf, f_htf(), lookahead_on) for one timeframe. hist: containing bar's final values.
    realtime: the containing bar's developing values at the 1M bar's last tick (bars before it are final)."""

    def __init__(self, hbars, P):
        self.hb = hbars
        self.P = P
        self.main, _ = pine_stoch(hbars, P["k"], P["d"], P["s"])
        self.idx = {}
        for h, x in enumerate(hbars):
            for b in x["n1"]:
                self.idx[b["t"]] = h

    def at(self, b1, realtime):
        h = self.idx[b1["t"]]
        if not realtime:
            return htf_tuple(self.hb, self.main, h)
        # developing bar h: OHLC of its 1M bars up to and including b1
        part = [x for x in self.hb[h]["n1"] if x["t"] <= b1["t"]]
        dev = dict(self.hb[h])
        dev.update(o=part[0]["o"], h=max(x["h"] for x in part), l=min(x["l"] for x in part), c=part[-1]["c"])
        bars = self.hb[:h] + [dev]
        k, s = self.P["k"], self.P["s"]
        lo = max(0, h - (k + s + 4))
        ll = [None] * (h + 1)
        hh = [None] * (h + 1)
        for i in range(lo, h + 1):
            if i >= k - 1:
                ll[i] = min(x["l"] for x in bars[i - k + 1:i + 1])
                hh[i] = max(x["h"] for x in bars[i - k + 1:i + 1])
        m0 = pine_main_at(bars, ll, hh, h, k, s)
        tup = htf_tuple(self.hb, self.main, h)
        tup[0] = m0
        return tup


DEF = {"k": 21, "d": 3, "s": 3, "up": 90.0, "lo": 10.0, "n": 10, "mv": 3.0}
MID = 50.0


def decide(K1, D1, i, k5, k5p, k15, k15p, k15pp, P=DEF, chartOK=True, confirmed=True, mut=None):
    """1M / 5M / 15M conditions of the Pine logic section on bar i (K1 / D1 lists, None = na)."""
    mut = mut or set()
    g = lambda a, j: a[i - j] if i - j >= 0 else None
    d1Ok = None not in (g(K1, 0), g(K1, 1), g(D1, 0), g(D1, 1))
    winOk, kmax, kmin = True, None, None
    for j in range(0, P["n"] + (1 if "win11" in mut else 0)):
        v = g(K1, j)
        if v is None:
            winOk = False
            break
        kmax = v if kmax is None else max(kmax, v)
        kmin = v if kmin is None else min(kmin, v)
    data1 = d1Ok and winOk
    k, kp, d, dp = g(K1, 0), g(K1, 1), g(D1, 0), g(D1, 1)
    chg = k - kp if data1 else None
    if "eqcross" in mut:
        sC = data1 and kp >= dp and k <= d
        lC = data1 and kp <= dp and k >= d
    else:
        sC = data1 and kp >= dp and k < d
        lC = data1 and kp <= dp and k > d
    if "mvgt" in mut:
        sM = data1 and -chg > P["mv"]
        lM = data1 and chg > P["mv"]
    else:
        sM = data1 and -chg >= P["mv"]
        lM = data1 and chg >= P["mv"]
    if "reachgt" in mut:
        sR = data1 and kmax > P["up"]
        lR = data1 and kmin < P["lo"]
    elif "reachD" in mut:
        sR = data1 and max(kmax, max(x for x in D1[i - P["n"] + 1:i + 1])) >= P["up"]
        lR = data1 and min(kmin, min(x for x in D1[i - P["n"] + 1:i + 1])) <= P["lo"]
    else:
        sR = data1 and kmax >= P["up"]
        lR = data1 and kmin <= P["lo"]
    data5 = k5 is not None and k5p is not None
    if "mid5ge" in mut:
        s5 = data5 and k5 >= MID and k5 < k5p
        l5 = data5 and k5 <= MID and k5 > k5p
    else:
        s5 = data5 and k5 > MID and k5 < k5p
        l5 = data5 and k5 < MID and k5 > k5p
    data15 = None not in (k15, k15p, k15pp)
    dl0 = k15 - k15p if data15 else None
    dl1 = k15p - k15pp if data15 else None
    if "flat15" in mut:
        s15 = data15 and k15 > MID and (dl0 <= 0 or (0 < dl0 and dl0 < dl1))
        l15 = data15 and k15 < MID and (dl0 >= 0 or (dl1 < dl0 and dl0 < 0))
    elif "nodecel" in mut:
        s15 = data15 and k15 > MID and dl0 < 0
        l15 = data15 and k15 < MID and dl0 > 0
    else:
        s15 = data15 and k15 > MID and (dl0 < 0 or (0 < dl0 and dl0 < dl1))
        l15 = data15 and k15 < MID and (dl0 > 0 or (dl1 < dl0 and dl0 < 0))
    ev = chartOK and confirmed
    dataAll = data1 and data5 and data15
    S = bool(ev and dataAll and sC and sM and sR and s5 and s15)
    L = bool(ev and dataAll and lC and lM and lR and l5 and l15)
    return S, L, dict(sC=sC, lC=lC, sM=sM, lM=lM, sR=sR, lR=lR, s5=s5, l5=l5, s15=s15, l15=l15,
                      data1=data1, data5=data5, data15=data15, kmax=kmax, kmin=kmin, chg=chg, dl0=dl0, dl1=dl1)


def pine_run(bars1, sec5, sec15, P=DEF, realtime=False, mut=None):
    K1, D1 = pine_stoch(bars1, P["k"], P["d"], P["s"])
    out = []
    for i, b in enumerate(bars1):
        t = b["tc"]
        k5, k5p, k5pp, t5 = f_pick(t, True, *sec5.at(b, realtime))        # evaluated at the 1M bar's confirmed execution
        k15, k15p, k15pp, t15 = f_pick(t, True, *sec15.at(b, realtime))
        if mut and "late5" in mut:       # one extra higher-timeframe bar of delay ([1] + lookahead_on)
            tup = sec5.at(b, realtime)
            k5, k5p, t5 = tup[1], tup[2], tup[6]
        if mut and "forming" in mut:     # the containing (forming) 5M bar used
            tup = sec5.at(b, realtime)
            k5, k5p, t5 = tup[0], tup[1], tup[5]
        S, L, info = decide(K1, D1, i, k5, k5p, k15, k15p, k15pp, P, mut=mut)
        out.append(dict(S=S, L=L, t5=t5, t15=t15, k5=k5, k15=k15, info=info))
    return out


# ============================================================================
# 3. Spec oracle (from the request text; uses the MT5 port on each timeframe's own OHLC)
# ============================================================================
def oracle_run(bars1, h5, h15, P=DEF):
    def mt5_vals(bars):
        m, n = mt5_full(bars, P["k"], P["d"], P["s"])
        first_main = P["k"] + P["s"] - 2          # values before this are MT5's 0 initialisation
        first_sig = P["k"] + P["s"] + P["d"] - 3
        if n == 0:
            return [None] * len(bars), [None] * len(bars)
        return ([m.main[i] if i >= first_main else None for i in range(len(bars))],
                [m.sig[i] if i >= first_sig else None for i in range(len(bars))])
    K1, D1 = mt5_vals(bars1)
    K5, _ = mt5_vals(h5)
    K15, _ = mt5_vals(h15)

    def latest(hb, T):         # latest higher-timeframe bar with close time <= T
        idx = None
        for h, x in enumerate(hb):
            if x["tc"] <= T:
                idx = h
            else:
                break
        return idx
    out = []
    p5 = p15 = 0
    for i, b in enumerate(bars1):
        T = b["tc"]
        while p5 + 1 < len(h5) and h5[p5 + 1]["tc"] <= T:
            p5 += 1
        while p15 + 1 < len(h15) and h15[p15 + 1]["tc"] <= T:
            p15 += 1
        a = p5 if h5[p5]["tc"] <= T else None
        c = p15 if h15[p15]["tc"] <= T else None
        v = lambda arr, h, j: arr[h - j] if h is not None and h - j >= 0 else None
        k5, k5p = v(K5, a, 0), v(K5, a, 1)
        k15, k15p, k15pp = v(K15, c, 0), v(K15, c, 1), v(K15, c, 2)
        # 1M (spec wording)
        win = [K1[i - j] if i - j >= 0 else None for j in range(P["n"])]
        ok1 = i >= 1 and None not in win and None not in (K1[i - 1], D1[i], D1[i - 1])
        S = L = False
        if ok1 and None not in (k5, k5p, k15, k15p, k15pp):
            crossDn = K1[i - 1] >= D1[i - 1] and K1[i] < D1[i]
            crossUp = K1[i - 1] <= D1[i - 1] and K1[i] > D1[i]
            dlt0, dlt1 = k15 - k15p, k15p - k15pp
            S = (max(win) >= P["up"] and crossDn and K1[i - 1] - K1[i] >= P["mv"]
                 and k5 > 50 and k5 < k5p
                 and k15 > 50 and (dlt0 < 0 or 0 < dlt0 < dlt1))
            L = (min(win) <= P["lo"] and crossUp and K1[i] - K1[i - 1] >= P["mv"]
                 and k5 < 50 and k5 > k5p
                 and k15 < 50 and (dlt0 > 0 or dlt1 < dlt0 < 0))
        out.append(dict(S=S, L=L, t5=h5[a]["tc"] if a is not None else None, t15=h15[c]["tc"] if c is not None else None))
    return out


# ============================================================================
# data
# ============================================================================
T0 = 1767574800000          # 2026-01-05 01:00 UTC (Monday)


def gen_bars(n, seed, drop=0.0, flat_runs=False, gap_every=None, start=T0):
    rnd = random.Random(seed)
    bars, p, t = [], 2000.0, start
    for i in range(n):
        p += rnd.gauss(0, 0.6) + 0.8 * math.sin(i / 6.0) + 0.3 * math.sin(i / 40.0) + 0.1 * math.sin(i / 150.0)
        o = p
        c = p + rnd.gauss(0, 0.5)
        h = max(o, c) + abs(rnd.gauss(0, 0.3))
        l = min(o, c) - abs(rnd.gauss(0, 0.3))
        if flat_runs and (i // 40) % 7 == 3:
            o = h = l = c = round(p, 1)
        # quantise to 0.01 like a feed
        o, h, l, c = (round(x, 2) for x in (o, h, l, c))
        h, l = max(h, o, c), min(l, o, c)
        p = c
        if gap_every and i and i % gap_every == 0:
            t += 2 * 60 * MIN + 17 * MIN          # session gap of 2h17m (bars resume off the 5M grid? no: still minute grid)
        if not (drop and rnd.random() < drop):
            bars.append({"t": t, "tc": t + MIN, "o": o, "h": h, "l": l, "c": c})
        t += MIN
    return bars


def build(bars1, P=DEF):
    h5, h15 = aggregate(bars1, 5), aggregate(bars1, 15)
    return h5, h15, Security(h5, P), Security(h15, P)


# ============================================================================
# checks
# ============================================================================
def static_checks():
    lg = SRC[SRC.index("// ==== SMT Logic (begin)"):SRC.index("// ==== SMT Logic (end)")]
    code = "\n".join(l.split("//")[0].rstrip() for l in SRC.split("\n"))
    check("PT-01 Pine v5 (same version as every existing file), indicator() — no strategy / order / alert calls",
          "//@version=5" in SRC and re.search(r"^indicator\(", SRC, re.M) and not re.search(r"\bstrategy\b\s*[.(]", code)
          and "alert" not in code)
    exp_inputs = [('iKPer   = input.int(21, "%K期間"'), ('iDPer   = input.int(3,  "%D期間"'), ('iSlow   = input.int(3,  "スローイング"'),
                  ('iUpLv   = input.float(90.0, "上側到達レベル"'), ('iLoLv   = input.float(10.0, "下側到達レベル"'),
                  ('iReachN = input.int(10, "到達確認本数'), ('iMinMv  = input.float(3.0, "1分足クロス足の最低変化幅'),
                  ('iDebug  = input.bool(false, "検証表示"')]
    check("PT-02 inputs and defaults (K 21 / D 3 / slowing 3 / 90 / 10 / 10 bars / 3 points / validation OFF)",
          all(x in SRC for x in exp_inputs), [x for x in exp_inputs if x not in SRC])
    mirrored = [
        "    float ll = ta.lowest(low, kPer)", "    float hh = ta.highest(high, kPer)",
        "    if bar_index >= kPer + slow - 2", "        for j = slow - 1 to 0",
        "            sLow  += close[j] - ll[j]", "            sHigh += hh[j] - ll[j]",
        "        mainV := sHigh == 0.0 ? 100.0 : sLow / sHigh * 100",
        "    if bar_index >= kPer + slow + dPer - 3", "        for j = 0 to dPer - 1", "            s += mainV[j]",
        "        sigV := s / dPer",
        "    [m, m[1], m[2], m[3], time, time_close, time_close[1]]",
        "    if not na(t) and not na(hOpen) and not na(hClose)", "        if conf and t >= hClose",
        "[k5, k5p, k5pp, t5ref]      = f_pick(tNow, barstate.isconfirmed, a5c0, a5c1, a5c2, a5c3, a5o, a5cl, a5clp)",
        "[k15, k15p, k15pp, t15ref]  = f_pick(tNow, barstate.isconfirmed, a15c0, a15c1, a15c2, a15c3, a15o, a15cl, a15clp)",
        "            k0 := c0", "            k1 := c1", "            k2 := c2", "            rt := hClose",
        "            k0 := c1", "            k1 := c2", "            k2 := c3", "            rt := hClosePrev",
        "float tNow = time_close",
        "bool chartOK = timeframe.isminutes and timeframe.multiplier == 1 and chart.is_standard",
        "bool d1Ok = not na(k1m) and not na(k1m[1]) and not na(d1m) and not na(d1m[1])",
        "for j = 0 to iReachN - 1",
        "bool sCross1 = data1 and k1m[1] >= d1m[1] and k1m < d1m",
        "bool lCross1 = data1 and k1m[1] <= d1m[1] and k1m > d1m",
        "bool sMove1  = data1 and -k1Chg >= iMinMv", "bool lMove1  = data1 and k1Chg >= iMinMv",
        "bool sReach1 = data1 and k1Max >= iUpLv", "bool lReach1 = data1 and k1Min <= iLoLv",
        "bool data5 = not na(k5) and not na(k5p)",
        "bool s5 = data5 and k5 > MID and k5 < k5p", "bool l5 = data5 and k5 < MID and k5 > k5p",
        "bool data15 = not na(k15) and not na(k15p) and not na(k15pp)",
        "float dl0 = k15 - k15p", "float dl1 = k15p - k15pp",
        "bool s15 = data15 and k15 > MID and (dl0 < 0 or (0 < dl0 and dl0 < dl1))",
        "bool l15 = data15 and k15 < MID and (dl0 > 0 or (dl1 < dl0 and dl0 < 0))",
        "bool evalNow  = chartOK and barstate.isconfirmed",
        "bool dataAll  = data1 and data5 and data15",
        "bool shortSig = evalNow and dataAll and sCross1 and sMove1 and sReach1 and s5 and s15",
        "bool longSig  = evalNow and dataAll and lCross1 and lMove1 and lReach1 and l5 and l15",
    ]
    lg_lines = [l.split("//")[0].rstrip() for l in lg.split("\n")]
    miss = [x for x in mirrored if x not in lg_lines]
    check("PT-03 every statement the Python mirror implements is in the Pine logic section verbatim", not miss, miss)
    sec = re.findall(r"request\.security\(([^\n]*\n[^\n]*)", lg)
    check("PT-04 exactly two request.security calls: TF 5 / TF 15, f_htf (own OHLC), lookahead_on, gaps_off; the fixed TFs are '5' / '15'",
          len(sec) == 2 and all("f_htf(iKPer, iDPer, iSlow)" in s and "lookahead = barmerge.lookahead_on" in s
                                and "gaps = barmerge.gaps_off" in s for s in sec)
          and 'string TF5  = "5"' in SRC and 'string TF15 = "15"' in SRC and "float MID   = 50.0" in SRC
          and "TF5, f_htf" in sec[0] and "TF15, f_htf" in sec[1], sec)
    check("PT-05 the logic section keeps no state (no var / varip: no stored cross, no consumed reach history, no cooldown)",
          not re.search(r"^\s*(var|varip)\b", lg, re.M))
    check("PT-06 the containing-bar value (c0 / a5c0 / a15c0) is read only by f_pick's same-close branch",
          lg.count("c0") == lg.count("a5c0") + lg.count("a15c0") + 2
          and "bool conf, float c0, float c1" in lg and lg.count("k0 := c0") == 1 and lg.count("a5c0") == 2 and lg.count("a15c0") == 2,
          (lg.count("c0"), lg.count("a5c0"), lg.count("a15c0")))
    plots = re.findall(r"^plotshape\((\w+),", SRC, re.M)
    check("PT-07 arrows: only shortSig (down, above bar) / longSig (up, below bar), distinct colours",
          plots == ["shortSig", "longSig"] and "shape.arrowdown, location.abovebar, color.new(color.red" in SRC
          and "shape.arrowup,   location.belowbar, color.new(color.teal" in SRC)
    after = SRC[SRC.index("// ==== SMT Logic (end)"):]
    assigned = re.findall(r"^\s*(\w+)\s*:=", after, re.M)
    sig_names = {"shortSig", "longSig", "sCross1", "lCross1", "sMove1", "lMove1", "sReach1", "lReach1", "s5", "l5",
                 "s15", "l15", "data1", "data5", "data15", "k5", "k15", "k1m", "d1m"}
    check("PT-08 the display part (validation ON / OFF) never reassigns a decision variable",
          not (set(assigned) & sig_names) and "iDebug" not in lg, assigned)
    check("PT-09 off-chart notice: 1M standard candles only, otherwise a notice and evalNow false",
          "1分足の通常ローソク足チャート専用" in SRC and "if barstate.islast and not chartOK" in SRC)
    disp = "\n".join(l.split("//")[0] for l in SRC[SRC.index("// ==== SMT Logic (end)"):].split("\n"))
    raw = re.findall(r"\ba(?:5|15)(?:c\d|o|cl|clp)\b", disp)
    check("PT-10 arrows / labels / table / Data Window read only the selected values (k5, k5p, k15, dl0, dl1, t5ref, t15ref, "
          "shortSig / longSig ...): no raw request.security tuple element (a5c0 .. a15clp) after the logic section",
          not raw and all(x in disp for x in ("f_n(k5)", "f_n(k5p)", "f_n(k15)", "f_n(dl0)", "f_n(dl1)", "f_t(t5ref)", "f_t(t15ref)"))
          and "plot(k5," in disp and "plot(f_ymdhm(t5ref)" in disp, raw)
    lbl = re.findall(r"label\.new\(([^,]+),", disp)
    check("PT-11 nothing is drawn on an earlier bar: label.new only at bar_index (no offset), no label.set_x / set_xy, "
          "no plot / plotshape offset, labels only inside `if iDebug and evalNow` (confirmed bar) or the last-bar notice",
          lbl and set(lbl) == {"bar_index"} and "set_x" not in disp and "offset" not in disp
          and disp.count("label.new(") == 3 and "if iDebug and evalNow" in disp, lbl)
    tup = re.search(r"f_htf\(int kPer, int dPer, int slow\) =>\n    \[m, s\] = f_mtStoch\(kPer, dPer, slow\)\n    (\[.*\])", lg)
    check("PT-12 one request.security tuple per timeframe, evaluated on one higher-timeframe bar h: [K(h), K(h-1), K(h-2), K(h-3), "
          "time(h), time_close(h), time_close(h-1)]; unpacked in the same order (c0..c3, open, close, closePrev)",
          tup and tup.group(1) == "[m, m[1], m[2], m[3], time, time_close, time_close[1]]"
          and "[a5c0, a5c1, a5c2, a5c3, a5o, a5cl, a5clp] = request.security(" in lg
          and "[a15c0, a15c1, a15c2, a15c3, a15o, a15cl, a15clp] = request.security(" in lg
          and "f_pick(float t, bool conf, float c0, float c1, float c2, float c3, float hOpen, float hClose, float hClosePrev) =>" in lg)


def stoch_checks():
    for seed, kw in ((1, {}), (2, {"flat_runs": True}), (3, {"drop": 0.2})):
        bars = gen_bars(1500, seed, **kw)
        for (k, d, s) in ((21, 3, 3), (5, 3, 1), (14, 1, 5), (1, 1, 1), (8, 5, 2)):
            m, n = mt5_full(bars, k, d, s)
            inc = mt5_incremental(bars[:400], k, d, s)
            pm, ps = pine_stoch(bars, k, d, s)
            fm, fs = k + s - 2, k + s + d - 3
            exact_m = all(pm[i] == m.main[i] for i in range(fm, len(bars)))
            exact_s = all(ps[i] == m.sig[i] for i in range(fs, len(bars)))
            na_ok = all(pm[i] is None for i in range(fm)) and all(ps[i] is None for i in range(fs))
            inc_ok = all(inc.main[i] == m.main[i] and inc.sig[i] == m.sig[i] for i in range(0, 400))
            check(f"ST-01 seed {seed} {kw or ''} K{k} D{d} S{s}: Pine f_mtStoch == MT5 port (main & signal, exact float) on "
                  f"every Pine value; Pine na exactly where MT5 holds its 0 initialisation; MT5 incremental == full",
                  n == len(bars) and exact_m and exact_s and na_ok and inc_ok, (exact_m, exact_s, na_ok, inc_ok))
    bars = gen_bars(300, 4)
    m, _ = mt5_full(bars, 21, 3, 3)
    # MT5 signal at index D-1 .. first_sig-1 averages the 0 initialisation (not a valid value)
    zero_used = any(m.sig[i] != 0.0 and abs(m.sig[i] - sum(m.main[i - j] for j in range(3)) / 3) < 1e-12
                    and any(m.main[i - j] == 0.0 for j in range(3)) for i in range(2, 24))
    pm, ps = pine_stoch(bars, 21, 3, 3)
    check("ST-02 MT5's early signal mixes the 0-initialised Main (index 22..23); Pine reports na there (not a stoch value)",
          zero_used and ps[22] is None and ps[23] is None and ps[24] is not None)
    # slowing is sum-ratio, not SMA of the fast %K (TradingView ta.sma(ta.stoch, 3) differs)
    fast = []
    for i in range(len(bars)):
        if i >= 20:
            lo = min(b["l"] for b in bars[i - 20:i + 1]); hi = max(b["h"] for b in bars[i - 20:i + 1])
            fast.append(100 * (bars[i]["c"] - lo) / (hi - lo) if hi != lo else None)
        else:
            fast.append(None)
    sma = [sum(fast[i - 2:i + 1]) / 3 if i >= 22 else None for i in range(len(bars))]
    diffs = [abs(sma[i] - m.main[i]) for i in range(22, len(bars))]
    check("ST-03 MT5 slowing (Σ(C−LL)/Σ(HH−LL)) is not the SMA of TradingView's fast %K (max diff > 0.5 pt on this data)",
          max(diffs) > 0.5, max(diffs))
    flat = [{"t": T0 + i * MIN, "tc": T0 + (i + 1) * MIN, "o": 5.0, "h": 5.0, "l": 5.0, "c": 5.0} for i in range(60)]
    m, _ = mt5_full(flat, 21, 3, 3)
    pm, ps = pine_stoch(flat, 21, 3, 3)
    check("ST-04 zero range (Σ(HH−LL) == 0): MT5 sets Main 100; Pine the same (Signal 100)",
          all(m.main[i] == 100.0 and pm[i] == 100.0 for i in range(22, 60)) and all(ps[i] == 100.0 for i in range(24, 60)))
    big = [dict(b, o=b["o"] + 2e6, h=b["h"] + 2e6, l=b["l"] + 2e6, c=b["c"] + 2e6) for b in gen_bars(100, 5)]
    m, _ = mt5_full(big, 21, 3, 3)
    pm, _ = pine_stoch(big, 21, 3, 3)
    check("ST-05 documented difference: MT5's 1000000 min seed breaks LL above 1,000,000 (Pine uses the true minimum)",
          any(m.lo[i] == 1000000.0 for i in range(20, 100)) and pm[50] is not None)


def htf_checks():
    # contiguous minutes from 14:30 UTC on a Monday; check the reference bars at 5M / 15M boundaries
    start = T0 + 4 * 60 * MIN                   # 2026-01-05 05:00 UTC: 10 h (40 15M bars) before 14:59
    bars = gen_bars(800, 11, start=start)
    h5, h15, s5, s15 = build(bars)
    hm = lambda t: None if t is None else (t // MIN) % (24 * 60)
    want = {  # 1M close (minutes of day) -> (5M close, 15M close)
        14 * 60 + 59: (14 * 60 + 55, 14 * 60 + 45),
        15 * 60 + 0: (15 * 60 + 0, 15 * 60 + 0),
        15 * 60 + 1: (15 * 60 + 0, 15 * 60 + 0),
        15 * 60 + 4: (15 * 60 + 0, 15 * 60 + 0),
        15 * 60 + 5: (15 * 60 + 5, 15 * 60 + 0),
        15 * 60 + 14: (15 * 60 + 10, 15 * 60 + 0),
        15 * 60 + 15: (15 * 60 + 15, 15 * 60 + 15),
        15 * 60 + 16: (15 * 60 + 15, 15 * 60 + 15),
    }
    for rt in (False, True):
        res = pine_run(bars, s5, s15, realtime=rt)
        got = {hm(b["tc"]): (hm(r["t5"]), hm(r["t15"])) for b, r in zip(bars, res) if hm(b["tc"]) in want}
        check(f"TM-01 {'realtime' if rt else 'history'}: reference 5M / 15M close times at 14:59 / 15:00 / 15:01 / 15:04 / 15:05 / "
              f"15:14 / 15:15 / 15:16 (1M close) = 14:55·14:45 / 15:00·15:00 / 15:00·15:00 / 15:00 / 15:05 / 15:10 / 15:15 / 15:15",
              got == want, {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v})
        # the value used is that bar's own K (5M computed from 5M OHLC)
        ok = True
        for b, r in zip(bars, res):
            hs = [j for j, x in enumerate(h5) if x["tc"] <= b["tc"]]
            if not hs:
                ok &= r["t5"] is None and r["k5"] is None
                continue
            h = hs[-1]
            ok &= r["t5"] == h5[h]["tc"] and r["k5"] == s5.main[h]
        check(f"TM-02 {'realtime' if rt else 'history'}: every bar — K5 = K of the latest 5M bar with close <= T (5M own OHLC)", ok)
    # realtime on 14:59 close: the forming 5M bar (14:55-15:00) has a developing K != the confirmed one; it is not used
    b = next(x for x in bars if hm(x["tc"]) == 14 * 60 + 59)
    tup = s5.at(b, True)
    hist = s5.at(b, False)
    k5, *_ = f_pick(b["tc"], True, *tup)
    check("TM-03 forming 5M bar: developing K (realtime) differs from its final K (history), and neither is used at 14:59",
          tup[0] != hist[0] and k5 == tup[1] == hist[1])
    # realtime forming tick of the 1M bar that closes with the 5M bar (14:59-15:00 bar, close 15:00): not yet confirmed
    b = next(x for x in bars if hm(x["tc"]) == 15 * 60 + 0)
    tup = s5.at(b, True)
    fk0, _, _, frt = f_pick(b["tc"], False, *tup)
    ck0, _, _, crt = f_pick(b["tc"], True, *tup)
    h = next(j for j, x in enumerate(h5) if x["tc"] == b["tc"])
    check("TM-03b realtime forming tick of the 1M bar closing at 15:00: the 5M bar closing at 15:00 is not used yet (K / time = "
          "the 14:55 bar); at the confirmed execution it is used (K / time = the 15:00 bar)",
          fk0 == s5.main[h - 1] and hm(frt) == 14 * 60 + 55 and ck0 == s5.main[h] and hm(crt) == 15 * 60 + 0)
    # history vs realtime: same signals and reference times
    for seed, kw in ((21, {}), (22, {"drop": 0.15}), (23, {"gap_every": 1370})):
        bars = gen_bars(40000, seed, **kw)
        h5, h15, s5, s15 = build(bars)
        a = pine_run(bars, s5, s15, realtime=False)
        b_ = pine_run(bars, s5, s15, realtime=True)
        same = all((x["S"], x["L"], x["t5"], x["t15"], x["k5"], x["k15"]) == (y["S"], y["L"], y["t5"], y["t15"], y["k5"], y["k15"])
                   for x, y in zip(a, b_))
        orc = oracle_run(bars, h5, h15)
        eq = all((x["S"], x["L"], x["t5"], x["t15"]) == (y["S"], y["L"], y["t5"], y["t15"]) for x, y in zip(a, orc))
        nS, nL = sum(x["S"] for x in a), sum(x["L"] for x in a)
        # leak check: every used 5M / 15M bar closed at or before T
        noleak = all((x["t5"] is None or x["t5"] <= bb["tc"]) and (x["t15"] is None or x["t15"] <= bb["tc"]) for x, bb in zip(a, bars))
        check(f"TM-04 seed {seed} {kw or ''}: history == realtime emulation (signals, reference times, K5 / K15) on every bar; "
              f"Pine mirror == spec oracle (MT5 port, latest close <= T); no reference close after T; signals S {nS} / L {nL}",
              same and eq and noleak and nS > 0 and nL > 0,
              (same, eq, noleak, nS, nL, [i for i, (x, y) in enumerate(zip(a, orc)) if (x["S"], x["L"], x["t5"], x["t15"]) != (y["S"], y["L"], y["t5"], y["t15"])][:5]))
    # missing last 1M bar of a 5M period: the 5M bar (close 15:00) is not confirmed at 14:59 -> previous bar; next 1M bar uses it
    bars = gen_bars(800, 12, start=start)
    drop = [x for x in bars if hm(x["tc"]) != 15 * 60 + 0]     # the 14:59-15:00 bar missing
    h5, h15, s5, s15 = build(drop)
    res = pine_run(drop, s5, s15)
    m = {hm(b["tc"]): (hm(r["t5"]), hm(r["t15"])) for b, r in zip(drop, res)}
    check("TM-05 actual bar times: with the 14:59-15:00 1M bar missing, the 14:59 1M uses 5M 14:55 / 15M 14:45 and the "
          "15:01 1M uses 5M 15:00 / 15M 15:00 (no fixed-clock assumption)",
          m[14 * 60 + 59] == (14 * 60 + 55, 14 * 60 + 45) and m[15 * 60 + 1] == (15 * 60 + 0, 15 * 60 + 0), (m.get(899), m.get(901)))
    # mutations of the higher-timeframe pick are caught by the oracle
    bars = gen_bars(40000, 21)
    h5, h15, s5, s15 = build(bars)
    orc = oracle_run(bars, h5, h15)
    for mt, desc in (("late5", "[1] + lookahead_on (one extra 5M bar of delay on a same-close bar)"),
                     ("forming", "the forming 5M bar")):
        a = pine_run(bars, s5, s15, mut={mt})
        diff = sum((x["S"], x["L"], x["t5"]) != (y["S"], y["L"], y["t5"]) for x, y in zip(a, orc))
        check(f"TM-06 mutation caught: {desc} differs from the spec oracle ({diff} bars)", diff > 0)
    a = pine_run(bars, s5, s15, mut={"forming"}, realtime=True)
    b_ = pine_run(bars, s5, s15, mut={"forming"}, realtime=False)
    check("TM-07 using the forming 5M bar would make history != realtime (repaint) — the adopted pick does not",
          any((x["S"], x["L"], x["k5"]) != (y["S"], y["L"], y["k5"]) for x, y in zip(a, b_)))


def series(vals):
    return list(vals)


def case(K1, D1, k5=(60, 70), k15=(60, 70, 75), P=DEF, **kw):
    i = len(K1) - 1
    return decide(K1, D1, i, k5[0], k5[1], k15[0], k15[1], k15[2], P, **kw)


def boundary_checks():
    base_k = [50.0] * 30
    base_d = [50.0] * 30

    def short_k(peak_at_back, peak=90.0, prev=88.0, now=85.0, dprev=87.0, dnow=86.0):
        K, D = base_k[:], base_d[:]
        K[-1 - peak_at_back] = peak
        K[-2], K[-1] = (prev if peak_at_back != 1 else peak), now
        D[-2], D[-1] = dprev, dnow
        return K, D
    # reach
    K, D = short_k(5, peak=90.0)
    S, L, _ = case(K, D)
    K2, D2 = short_k(5, peak=89.99)
    S2, _, _ = case(K2, D2)
    check("BD-01 short reach: max K1 exactly 90 -> signal; 89.99 -> none", S and not S2)
    K, D = short_k(9, peak=95.0)
    S, _, _ = case(K, D)
    K2, D2 = short_k(10, peak=95.0)
    S2, _, _ = case(K2, D2)
    S3, _, _ = case(K2, D2, mut={"win11"})
    check("BD-02 10-bar window: reach on the oldest bar (9 back) -> signal; only on the 11th bar (10 back) -> none "
          "(mutation: 11-bar window would signal)", S and not S2 and S3)
    # move
    K, D = short_k(5, peak=95.0, prev=88.0, now=85.0)
    S, _, _ = case(K, D)
    K2, D2 = short_k(5, peak=95.0, prev=88.0, now=85.5)
    S2, _, _ = case(K2, D2)
    S3, _, _ = case(K, D, mut={"mvgt"})
    check("BD-03 1M drop exactly 3 (88 -> 85) -> signal; 2.5 -> none (mutation `> 3` would drop the exact 3)", S and not S2 and not S3)
    # cross at a K1 below 90, D not used for reach
    K, D = short_k(4, peak=91.0, prev=70.0, now=66.0, dprev=69.0, dnow=68.0)
    S, _, _ = case(K, D)
    check("BD-04 short: cross K1 66 (< 90) with the 90 reach 4 bars earlier -> signal", S)
    K = base_k[:]; D = base_d[:]
    D[-5] = 95.0
    K[-2], K[-1], D[-2], D[-1] = 88.0, 84.0, 87.0, 86.0
    S, _, _ = case(K, D)
    S2, _, _ = case(K, D, mut={"reachD"})
    check("BD-05 reach is K1 only: D1 at 95 with K1 max 88 -> none (mutation using D would signal)", not S and S2)
    # equality crosses
    K, D = short_k(5, peak=95.0, prev=87.0, now=84.0, dprev=87.0, dnow=86.0)
    S, _, _ = case(K, D)
    K2, D2 = short_k(5, peak=95.0, prev=89.0, now=86.0, dprev=87.0, dnow=86.0)
    S2, _, _ = case(K2, D2)
    S3, _, _ = case(K2, D2, mut={"eqcross"})
    check("BD-06 previous K1 == D1 then K1 < D1 -> cross; K1 == D1 on this bar -> no cross (mutation `<=` would cross)",
          S and not S2 and S3)
    # 5M
    K, D = short_k(5, peak=95.0)
    r = {x: case(K, D, k5=x)[0] for x in [(50.0, 60.0), (50.01, 60.0), (60.0, 60.0), (55.0, 58.0), (58.0, 55.0)]}
    check("BD-07 short 5M: K5 50 -> none, 50.01 falling -> signal, flat -> none, falling (continuing) -> signal, rising -> none "
          "(mutation `>= 50` takes the 50)",
          r == {(50.0, 60.0): False, (50.01, 60.0): True, (60.0, 60.0): False, (55.0, 58.0): True, (58.0, 55.0): False}
          and case(K, D, k5=(50.0, 60.0), mut={"mid5ge"})[0], r)
    # 15M: (K15, K15[1], K15[2]); Δ0 = K15 - K15[1], Δ1 = K15[1] - K15[2]
    t15 = {"normal Δ0<0": ((60.0, 65.0, 62.0), True), "decel 0<Δ0<Δ1": ((70.0, 68.0, 60.0), True),
           "flat Δ0=0": ((70.0, 70.0, 60.0), False), "accel Δ0>Δ1>0": ((70.0, 64.0, 62.0), False),
           "Δ0=Δ1>0": ((70.0, 65.0, 60.0), False), "Δ0>0, Δ1<0": ((70.0, 65.0, 68.0), False), "K15=50": ((50.0, 55.0, 52.0), False)}
    got = {n: case(K, D, k15=v)[0] for n, (v, _) in t15.items()}
    check("BD-08 short 15M: normal / deceleration -> signal; flat / acceleration / equal Δ / turn-up / K15 = 50 -> none",
          got == {n: e for n, (_, e) in t15.items()}, got)
    check("BD-09 15M mutations caught: Δ0 = 0 accepted (flat) / no deceleration branch",
          case(K, D, k15=(70.0, 70.0, 60.0), mut={"flat15"})[0] and not case(K, D, k15=(70.0, 68.0, 60.0), mut={"nodecel"})[0])

    # LONG mirror
    def long_k(trough_at_back, trough=10.0, prev=12.0, now=15.0, dprev=13.0, dnow=14.0):
        K, D = base_k[:], base_d[:]
        K[-1 - trough_at_back] = trough
        K[-2], K[-1] = prev, now
        D[-2], D[-1] = dprev, dnow
        return K, D
    L5 = (40.0, 30.0)
    L15 = (40.0, 35.0, 38.0)
    K, D = long_k(5, 10.0)
    K2, D2 = long_k(5, 10.01)
    check("BD-11 long reach: min K1 exactly 10 -> signal; 10.01 -> none",
          case(K, D, k5=L5, k15=L15)[1] and not case(K2, D2, k5=L5, k15=L15)[1])
    K, D = long_k(9, 5.0)
    K2, D2 = long_k(10, 5.0)
    check("BD-12 long 10-bar window: oldest bar in, 11th bar out",
          case(K, D, k5=L5, k15=L15)[1] and not case(K2, D2, k5=L5, k15=L15)[1])
    K, D = long_k(5, 5.0, prev=12.0, now=15.0)
    K2, D2 = long_k(5, 5.0, prev=12.0, now=14.5)
    check("BD-13 long rise exactly 3 -> signal; 2.5 -> none", case(K, D, k5=L5, k15=L15)[1] and not case(K2, D2, k5=L5, k15=L15)[1])
    K, D = long_k(5, 5.0, prev=13.0, now=16.0, dprev=13.0, dnow=14.0)
    K2, D2 = long_k(5, 5.0, prev=11.0, now=14.0, dprev=13.0, dnow=14.0)
    check("BD-14 long: previous K1 == D1 then K1 > D1 -> cross; K1 == D1 now -> none",
          case(K, D, k5=L5, k15=L15)[1] and not case(K2, D2, k5=L5, k15=L15)[1])
    K, D = long_k(4, 9.0, prev=30.0, now=34.0, dprev=31.0, dnow=32.0)
    check("BD-15 long: cross K1 34 (> 10) with the 10 reach 4 bars earlier -> signal", case(K, D, k5=L5, k15=L15)[1])
    K, D = long_k(5, 5.0)
    r = {x: case(K, D, k5=x, k15=L15)[1] for x in [(50.0, 40.0), (49.99, 40.0), (40.0, 40.0), (45.0, 42.0), (42.0, 45.0)]}
    check("BD-16 long 5M: K5 50 -> none, 49.99 rising -> signal, flat -> none, rising (continuing) -> signal, falling -> none",
          r == {(50.0, 40.0): False, (49.99, 40.0): True, (40.0, 40.0): False, (45.0, 42.0): True, (42.0, 45.0): False}, r)
    t15 = {"normal Δ0>0": ((40.0, 35.0, 38.0), True), "decel Δ1<Δ0<0": ((30.0, 32.0, 40.0), True),
           "flat Δ0=0": ((30.0, 30.0, 40.0), False), "accel Δ0<Δ1<0": ((30.0, 36.0, 38.0), False),
           "Δ0=Δ1<0": ((30.0, 35.0, 40.0), False), "Δ0<0, Δ1>0": ((30.0, 35.0, 32.0), False), "K15=50": ((50.0, 45.0, 48.0), False)}
    got = {n: case(K, D, k5=L5, k15=v)[1] for n, (v, _) in t15.items()}
    check("BD-17 long 15M: normal / deceleration -> signal; flat / acceleration / equal Δ / turn-down / K15 = 50 -> none",
          got == {n: e for n, (_, e) in t15.items()}, got)
    # 50 exactly excluded for both directions on 5M and 15M
    Ks, Ds = short_k(5, 95.0)
    Kl, Dl = long_k(5, 5.0)
    check("BD-18 K5 = 50 or K15 = 50 -> neither short nor long",
          not case(Ks, Ds, k5=(50.0, 60.0))[0] and not case(Kl, Dl, k5=(50.0, 40.0), k15=L15)[1]
          and not case(Ks, Ds, k15=(50.0, 55.0, 52.0))[0] and not case(Kl, Dl, k5=L5, k15=(50.0, 45.0, 48.0))[1])
    # data missing
    K, D = short_k(5, 95.0)
    Kn = K[:]; Kn[-8] = None
    Dn = D[:]; Dn[-2] = None
    check("BD-19 missing data -> no signal: na in the 10-bar K1 window / na previous D1 / na K5 / na K5[1] / na K15[2] / "
          "fewer than 10 K1 values",
          not case(Kn, D)[0] and not case(K, Dn)[0] and not decide(K, D, len(K) - 1, None, 60, 60, 70, 75)[0]
          and not decide(K, D, len(K) - 1, 55, None, 60, 70, 75)[0] and not decide(K, D, len(K) - 1, 55, 60, 60, 70, None)[0]
          and not case(K[-9:], D[-9:])[0] and case(K[-10:], D[-10:])[0])
    check("BD-20 not evaluated on a forming 1M bar (barstate.isconfirmed false) or on a non-1M chart",
          case(K, D)[0] and not case(K, D, confirmed=False)[0] and not case(K, D, chartOK=False)[0])


def sequence_checks():
    # no late signal: the cross bar fails on 5M; 5M becomes OK on the next bars without a new cross -> nothing
    K = [50.0] * 20 + [95.0, 93.0, 88.0, 85.0, 84.0, 83.0]
    D = [50.0] * 20 + [80.0, 86.0, 87.0, 86.0, 85.5, 85.0]
    i_cross = 23
    k5 = {23: (60.0, 58.0), 24: (57.0, 60.0), 25: (56.0, 57.0)}    # 5M rising at the cross, falling afterwards
    sig = [decide(K, D, i, *k5[i], 60.0, 70.0, 75.0)[0] for i in (23, 24, 25)]
    check("SQ-01 no late signal: cross at bar 23 with 5M not falling -> none; 5M falls at bars 24 / 25 (no new cross) -> none",
          sig == [False, False, False] and not decide(K, D, 24, *k5[24], 60.0, 70.0, 75.0)[2]["sC"])
    # several crosses share one reach: both signal
    K = [50.0] * 20 + [96.0, 92.0, 88.0, 85.0, 88.0, 92.0, 88.0, 84.0]
    D = [50.0] * 20 + [90.0, 91.0, 89.0, 87.0, 86.0, 87.0, 88.0, 87.0]
    sig = [decide(K, D, i, 60.0, 65.0, 60.0, 70.0, 75.0)[0] for i in range(len(K))]
    check("SQ-02 one 90 reach (bar 20) used by two later crosses (bars 22 and 27) -> both signal (no consumption / cooldown)",
          [i for i, s in enumerate(sig) if s] == [22, 27], [i for i, s in enumerate(sig) if s])
    # on real bars: the mirror marks the signal on the cross bar itself (never a later bar)
    bars = gen_bars(40000, 31)
    h5, h15, s5, s15 = build(bars)
    res = pine_run(bars, s5, s15)
    K1, D1 = pine_stoch(bars, 21, 3, 3)
    ok = all((not r["S"] or (K1[i - 1] >= D1[i - 1] and K1[i] < D1[i])) and (not r["L"] or (K1[i - 1] <= D1[i - 1] and K1[i] > D1[i]))
             for i, r in enumerate(res))
    check("SQ-03 every signal is on its own cross bar (random data, 40000 bars)", ok and any(r["S"] or r["L"] for r in res))
    # first signal only after all data exists
    first = min(i for i, r in enumerate(res) if r["S"] or r["L"])
    hb15 = next(h for h in range(len(h15)) if s15.main[h - 2 if h >= 2 else 0] is not None and h >= 2)
    check("SQ-04 no signal before the 15M K and its two previous values exist (needs >= 21+3-2+2+1 = 25 confirmed 15M bars)",
          bars[first]["tc"] >= h15[hb15]["tc"] and all(not (r["S"] or r["L"]) for r in res[:first]), (first, hb15))


BASE_REV = "35d2ee4"        # the branch head SMT-1 was added on


def smt_allowed():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import smt_build as sb
    return set(sb.NEW_FILES) | set(sb.TEST_EDITS)


def files_check():
    """Our own layer only: every commit after BASE_REV whose subject starts with "SMT-" and the uncommitted changes touch only
    the SMT files and the registration edits (smt_build.TEST_EDITS, each exactly: smt_build.unadapt gives the previous text).
    Commits of other layers (e.g. ZSY-0) are not ours and not judged here."""
    import smt_build as sb
    git = lambda *a: subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout
    allowed = smt_allowed()
    touched, bad = set(), []
    for line in git("log", "--format=%H %s", f"{BASE_REV}..HEAD").strip().split("\n"):
        if not line:
            continue
        h, subj = line.split(" ", 1)
        if subj.startswith("SMT-"):
            names = set(git("show", "--name-only", "--format=", h).split())
            touched |= names
            bad += sorted(names - allowed)
    st = git("status", "--porcelain").split("\n")
    wt = {l[3:] for l in st if l.strip()}
    bad += sorted(wt - allowed)
    # each registration edit: the current text minus exactly the SMT edit == the text before the SMT registration
    reg_bad = [p for p in sb.TEST_EDITS
               if sb.unadapt(p, open(os.path.join(ROOT, p), encoding="utf-8").read())
               != git("show", f"{sb.REG_BASE}:{p}")]
    check(f"FL-01 SMT commits after {BASE_REV} (+ uncommitted changes) touch only the SMT files and the registration edits; "
          "each registered older file differs from smt_build.REG_BASE by exactly its recorded SMT edit "
          "(no Pine / Strategy / Engine / Visual / Zone Combo Lab / order code changed)",
          not bad and not reg_bad and {"StochMtfSignal.pine", "tests/smt_sim.py"} <= touched | wt, (bad, reg_bad))


def registration_check():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import smt_build as sb
    acc = __import__("acc_build")
    cad = __import__("cad_adapt")
    git = lambda *a: subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout
    exact = all(sb.unadapt(p, open(os.path.join(ROOT, p), encoding="utf-8").read()) == git("show", f"{sb.REG_BASE}:{p}")
                and open(os.path.join(ROOT, p), encoding="utf-8").read() != git("show", f"{sb.REG_BASE}:{p}")
                for p in sb.TEST_EDITS)
    strays = ["StochMtfSignal2.pine", "Stoch.pine", "tests/smt_sim2.py", "STOCH_MTF_SIGNAL.md", "ZoneStrategyXAU.pine"]
    check("RG-01 registration (a layer above ZSY): tests/zsy_build.py / tests/cad_adapt.py / tests/zsy_sim.py differ from "
          "smt_build.REG_BASE by exactly the recorded edits; acc_build.ok() (through lab / fds / lfw / lab2 / lbs / zsy) accepts exactly the "
          "4 SMT files and no stray name; cad_adapt.LATER_NEW lists them",
          exact and all(acc.ok(f) and f in cad.LATER_NEW for f in sb.NEW_FILES) and len(sb.NEW_FILES) == 4
          and set(sb.TEST_EDITS) == {"tests/zsy_build.py", "tests/cad_adapt.py", "tests/zsy_sim.py"}
          and not any(acc.ok(f) for f in strays))
    old = git("show", "146f68f:StochMtfSignal.pine")
    cur = open(PINE, encoding="utf-8").read()
    one_more = cur.replace("bool evalNow  = chartOK and barstate.isconfirmed", "bool evalNow  = chartOK")
    check("RG-02 StochMtfSignal.pine == its SMT-1 text (146f68f) with exactly the recorded SMT-2 edits (smt_build.pine_unapply, used by "
          "zsy_sim ZS-02); any other change is not reverted (mutation: evalNow without isconfirmed -> no match)",
          sb.pine_unapply("StochMtfSignal.pine", cur) == old and cur != old
          and sb.pine_unapply("StochMtfSignal.pine", one_more) != old)


if __name__ == "__main__":
    static_checks()
    stoch_checks()
    htf_checks()
    boundary_checks()
    sequence_checks()
    files_check()
    registration_check()
    n_fail = sum(1 for _, ok in RESULTS if not ok)
    print(f"\n{len(RESULTS) - n_fail} / {len(RESULTS)} passed")
    sys.exit(1 if n_fail else 0)
