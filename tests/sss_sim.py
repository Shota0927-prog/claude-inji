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

5. SSS-3 / 4 / 5: the Pine row / event code itself (wait functions, varip rows, matching, lost check, start + mid-bar STB
   processing) is run through tests/acc_pine.py and compared with the Python models: delivery delays, in-row start-time order,
   mid-bar STB cases (1m mid flip completing the chain, close-before-start at the same time, start-based 1m kept, no repeat
   in the same target, both-sides break -> blue, BUY mirror) and random series vs an independent sorted-event model.

Evidence class: PINE_NOT_VERIFIED (TradingView compiler, request.security delivery and drawing are not run here; no real
market data is reachable from the test environment).
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
    """SSS-6 direction wait: the latest event of each timeframe (15s / 30s / 1m) in any order. A slot expires when the event
    being processed is more than W after it. A signal fires when all three slots are filled and earliest..latest <= W;
    the three slots are then cleared and further same-direction events at the same time are consumed."""
    def __init__(self):
        self.slot = [None, None, None]
        self.last_sig = None

    def event(self, rank, t, m, W):
        for k in range(3):
            if self.slot[k] is not None and t - self.slot[k] > W:
                self.slot[k] = None
        if m > 0 and self.last_sig != t:
            self.slot[rank] = t
            if None not in self.slot and max(self.slot) - min(self.slot) <= W:
                r = tuple(self.slot)
                self.slot = [None, None, None]
                self.last_sig = t
                return r
        return None


class OSeq:
    """SSS-9 direction wait: the ON timeframes (stages, short to long) are matched in order. One candidate per number of
    completed stages; an event of stage s extends the valid candidate with s stages (s = 0 starts a new one). When two
    candidates reach the same stage the one with the newer start wins (same start: newer end). A candidate is valid while
    t - start <= W. Completing all stages fires, clears every candidate and consumes the remaining same-time events."""
    def __init__(self, stages):
        self.st = list(stages)
        self.n = len(self.st)
        self.cand = {k: None for k in range(1, 4)}
        self.last = None

    def valid(self, k, t, W):
        c = self.cand.get(k)
        if c is not None and t - c[0] <= W:
            return c
        self.cand[k] = None
        return None

    def event(self, tf, t, m, W):
        if tf not in self.st or m <= 0 or self.last == t:
            return None
        s = self.st.index(tf)
        if s == 0:
            base = []
        else:
            base = self.valid(s, t, W)
            if base is None:
                return None
        new = list(base) + [t]
        k = s + 1
        if k == self.n:
            self.cand = {k2: None for k2 in range(1, 4)}
            self.last = t
            return tuple(new)
        cur = self.valid(k, t, W)
        if cur is None or new[0] >= cur[0]:
            self.cand[k] = new
        return None

    def drop(self, tf):
        if tf in self.st:
            s = self.st.index(tf)
            for k in range(s + 1, 4):
                self.cand[k] = None


NONE, WAIT, RCV, LOST = 0, 1, 2, 3


def chart_run(rows, wait_min=5, live=False):
    """Mirror of the SSS-3 Pine row queue. rows: one dict per chart update (normally one per 15s bar):
        t (15s bar time), e15=(ms, mb), need30 / need60 (start time if time("30S") / time("1") switched on this bar),
        r30 / r60 = (cur_t, cur_ms, cur_mb, prev_t, prev_ms, prev_mb) delivered by request.security (or None),
        now (optional live clock for the tooltip; only used when live=True).
    Returns (signals, lost): signals = [(mark_x = 1m start, 'SELL'|'BUY', (t15, t30, t60), chart_t_detected, live_t)],
    lost = [(tf, start_t, reason, chart_t)]."""
    W = wait_min * M
    sS, sB = OSeq((0, 1, 2)), OSeq((0, 1, 2))
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
                rs = sS.event(rank, t, ms, W)
                rb = sB.event(rank, t, mb, W)
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
    if "f_seqEvt(int p, int d, int j, int i" in src:
        # SSS-12: f_seqEvt(p, d, j, i, t, m, desc, liveT, b); the order log follows pattern 帯→フラット (p = 0)
        py = py.replace("def f_seqEvt(", "def _orig_f_seqEvt(", 1)
        py = ("def f_seqEvt(*a):\n    if a[0] == 0:\n        LOG.append(((15, 30, 60, 300)[a[3]], a[4], time, a[5]))\n"
              "    return _orig_f_seqEvt(*a)\n") + py
    elif "f_seqEvt(int p, int d, int i" in src:
        # SSS-10: f_seqEvt(p, d, i, t, m, desc, liveT); the order log follows pattern 帯→フラット (p = 0)
        py = py.replace("def f_seqEvt(", "def _orig_f_seqEvt(", 1)
        py = ("def f_seqEvt(*a):\n    if a[0] == 0:\n        LOG.append(((15, 30, 60, 300)[a[2]], a[3], time, a[4]))\n"
              "    return _orig_f_seqEvt(*a)\n") + py
    elif "f_seqEvt(int d, int i" in src:
        # SSS-9: f_seqEvt(d, i, t, m, desc, liveT)
        py = py.replace("def f_seqEvt(", "def _orig_f_seqEvt(", 1)
        py = ("def f_seqEvt(*a):\n    LOG.append(((15, 30, 60, 300)[a[1]], a[2], time, a[3]))\n"
              "    return _orig_f_seqEvt(*a)\n") + py
    elif "f_seqEvt(int p, int d" in src:
        # SSS-8: f_seqEvt(p, d, i, t, m, desc, liveT); the order log follows pattern '1分まで' (p = 1)
        py = py.replace("def f_seqEvt(", "def _orig_f_seqEvt(", 1)
        py = ("def f_seqEvt(*a):\n    if a[0] == 1:\n        LOG.append(((15, 30, 60, 300)[a[2]], a[3], time, a[4]))\n"
              "    return _orig_f_seqEvt(*a)\n") + py
    elif "def f_seqEvt(" in py:
        py = py.replace("def f_seqEvt(", "def _orig_f_seqEvt(", 1)
        py = ("def f_seqEvt(*a):\n    LOG.append(((15, 30, 60)[a[2]], a[3], time, a[4]))\n    return _orig_f_seqEvt(*a)\n") + py
    for f, tag in (("f_on15", 15), ("f_on30", 30), ("f_on60", 60)):
        if f"def {f}(" not in py:
            continue
        py = py.replace(f"def {f}(", f"def _orig_{f}(", 1)
        py = (f"def {f}(*a):\n    k = 2 if isinstance(a[1], list) else 1\n    LOG.append(({tag}, a[k], time, a[k + 1]))\n"
              f"    return _orig_{f}(*a)\n") + py
    code = compile(py, "SatsShortSignal.pine<rows>", "exec")

    class _NoBroker:
        def __getattr__(self, k):
            return lambda *a, **kw: None

    NP = (None,) * 13

    LABELS = []
    run_labels = LABELS

    dsrc = src[src.index("// ---- 印の描画"):src.index("// ---- 確認用の表")] if "// ---- 印の描画" in src else ""
    dcode = compile(ap.Translator().translate(ap.logical_lines(dsrc)), "draw", "exec") if "smDirty" in src else None

    def draw(env):
        """run the drawing section once (labels: env['LBL']; label.all = labels not deleted)"""
        env["label__all"] = [d for d in env["LBL"] if not d.deleted]
        exec(dcode, env)
    run_draw = draw

    def run(updates, live=False, show_evt=False, clr=(True, True, True, True), use=(True, True, True, False),
            useB=None, htf_sel=None, patA=None, patB=None, draw_labels=False):
        """updates: dicts with t, e15=(ms, mb), need30 / need60 (start time when time("30S") / time("1") switched),
        optional g30 / g60 (time("30S") / time("1") of this bar; default = the aligned start), p15 = 9-value pack of the chart's
        own 15s start data, r30 / r60 = (cur t, ms, mb, prev t, ms, mb) or the full 24-value form
        (t, ms, mb, *pack, prev t, prev ms, prev mb, *prev pack), hlc = (high, low, close) of this 15s bar, conf (default True)."""
        LBL = []
        env = ap.make_env(_NoBroker(), LBL)
        env.update(LBL=LBL, label__get_x=lambda l: l.args[0], label__get_text=lambda l: l.text,
                   yloc__abovebar="above", yloc__belowbar="below", sellCol="red", buyCol="teal", showSig=True, sigDet=False,
                   showLost=True, high=None, low=None, size__tiny="tiny")
        import types
        env["yloc"] = types.SimpleNamespace(abovebar="above", belowbar="below")
        env.update(_VARS=set(), _VARIPS=set(), LOG=[], syminfo__timezone="UTC", waitMin=5, showEvt=show_evt, chartOk=True,
                   clr15=clr[0], clr30=clr[1], clr60=clr[2], clr300=clr[3] if len(clr) > 3 else True,
                   use15=use[0], use30=use[1], use60=use[2], use300=use[3], patA=any(use),
                   patB=useB is not None and any(useB), useB15=bool(useB and useB[0]), useB30=bool(useB and useB[1]),
                   useB60=bool(useB and useB[2]), useB300=bool(useB and useB[3]),
                   str__contains=lambda a, b: b in a, math__pow=lambda a, b: a ** b,
                   array__insert=lambda arr, i, v: arr.insert(i, v), array__includes=lambda arr, v: v in arr,
                   htfOn=htf_sel is not None, htfTf="60",
                   timeframe__in_seconds=lambda *x: 15, array__new_string=lambda n=0, v=None: [v] * n,
                   array__new_bool=lambda n=0, v=None: [v] * n,
                   str__format_time=lambda t, f, tz: f.replace("HH", "%02d" % (t // 3600_000 % 24))
                   .replace("mm", "%02d" % (t // 60_000 % 60)).replace("ss", "%02d" % (t // 1000 % 60)))
        selv = htf_sel if htf_sel is not None else DEFAULT_SEL
        k = 0
        for pn in "AB":
            for bi in range(3):
                for dd in "SB":
                    for i in range(4):
                        env[f"x{pn}{bi}{dd}{i}"] = selv[k]
                        k += 1
        first = True
        prev_bar = (None, None, None, None)
        last_t = None
        for u in updates:
            T = u["t"]
            if last_t is not None and T != last_t:
                prev_bar = last_bar
            hlc = u.get("hlc", (None, None, None))
            g30 = u.get("need30") if u.get("need30") is not None else u.get("g30", T - T % 30_000)
            g60 = u.get("need60") if u.get("need60") is not None else u.get("g60", T - T % M)
            p15 = u.get("p15", NP)
            hv = u.get("htf") or (None,) * 8
            env.update(hTc1=hv[0], hB1=hv[1], hN1=hv[2], hTc2=hv[3], hB2=hv[4], hN2=hv[5], hCur=hv[6], hNc=hv[7])
            env.update(__first__=first, time=T, time_close=T + 15_000, barstate__isrealtime=live,
                       barstate__isconfirmed=u.get("conf", True), timenow=u.get("now", T),
                       high=hlc[0], low=hlc[1], close=hlc[2],
                       tc1=prev_bar[0], h1=prev_bar[1], lw1=prev_bar[2], c1=prev_bar[3],
                       ms15=u["e15"][0], mb15=u["e15"][1],
                       o15=p15[0], sp15=p15[1], dp15=p15[2], l1_15=p15[3], l2_15=p15[4], h20_15=p15[5], w20_15=p15[6],
                       h9_15=p15[7], w9_15=p15[8], tq15=p15[9], ss15=p15[10] if len(p15) > 10 else None,
                       ma15=p15[11] if len(p15) > 11 else 0, mz15=p15[12] if len(p15) > 12 else 0,
                       new30=u.get("need30") is not None, need30T=g30,
                       new60=u.get("need60") is not None, need60T=g60,
                       new300=u.get("need300") is not None,
                       need300T=u.get("need300") if u.get("need300") is not None else u.get("g300", T - T % (5 * M)))
            for tf in (30, 60, 300):
                r = u.get(f"r{tf}") or (None, 0, 0, None, 0, 0)
                if len(r) == 6:
                    r = (r[0], r[1], r[2], *NP, r[3], r[4], r[5], *NP)
                names = ["t", "ms", "mb", "o", "sp", "dp", "l1_", "l2_", "h20_", "w20_", "h9_", "w9_", "tq", "ss", "ma", "mz"]
                half = len(r) // 2
                for k, nm in enumerate(names):
                    env[f"{nm}{tf}"] = r[k] if k < half else (0 if nm in ("ma", "mz") else None)
                    env[f"{nm}{tf}p"] = r[half + k] if k < half else (0 if nm in ("ma", "mz") else None)
            if patA is not None:
                env["patA"] = patA
            if patB is not None:
                env["patB"] = patB
            exec(code, env)
            if draw_labels and dcode is not None:
                draw(env)
            first = False
            last_t = T
            last_bar = (T + 15_000, hlc[0], hlc[1], hlc[2])
        run.env = env
        marks = [(x, k, tip) for x, k, tip in zip(env["mkX"], env["mkK"], env["mkTip"]) if k in (0, 2)]
        if "smX" in env:
            marks += [(x, k, tip) for x, k, tip in zip(env["smX"], env["smK"], env["smTip"])]
            LABELS[:] = [(x, txt) for x, txt in zip(env["smX"], env["smTxt"])]
        else:
            marks += [(x, k, tip) for x, k, tip in zip(env["mkX"], env["mkK"], env["mkTip"]) if k in (1, -1)]
        return env["LOG"], marks
    run.labels = LABELS
    run.draw = run_draw
    run.env = None
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



# ---- SSS-5: start + mid-bar STB, independent model and Pine feeder ------------------------------------------------------------
def tf_packs(ks, bars, ser, step):
    """per target bar j: (t, ms, mb, o, stP, sdP, l1s, l2s, hh20, ll20, hh9, ll9, tcP) — start data from the previous confirmed
    bar; stP is that bar's f_satBand() bandState (na if a line is na), tcP its time_close."""
    out = []
    for j, k in enumerate(ks):
        pr = ser[j - 1]["prep"] if j else None
        if pr is None:
            out.append((k, 0, 0) + (None,) * 10 + (None, 0, 0))
            continue
        ms, mb, stS, sdS, _ = f_evt(bars[j]["o"], pr)
        P = ser[j - 1]
        ma, mz = edge_mask(P["l1"] if pr["okP"] else None, P["l2"], P["stb"], P["d1"], P["d2"], P["sd"], pr["d1s"], pr["d2s"], sdS)
        out.append((k, ms, mb, bars[j]["o"], pr["st"] if pr["okP"] else None, pr["sd"], pr["l1s"], pr["l2s"],
                    pr["hh20"], pr["ll20"], pr["hh9"], pr["ll9"], ks[j - 1] + step, stS, ma, mz))
    return out


PNAME = ("30秒まで", "1分まで", "5分まで")


def edge_mask(l1P, l2P, sbP, d1, d2, sd, d1s, d2s, sdS):
    """Python mirror of Pine f_edgeMask (used to build the packs; the Pine function itself is checked separately)."""
    ms = mb = 0
    if None not in (l1P, l2P, sbP, sdS):
        lo, hi = min(l1P, l2P, sbP), max(l1P, l2P, sbP)
        ms += (1 if l1P == lo and d1 == 1 and d1s == -1 else 0) + (2 if l2P == lo and d2 == 1 and d2s == -1 else 0) \
            + (4 if sbP == lo and sd == 1 and sdS == -1 else 0)
        mb += (1 if l1P == hi and d1 == -1 and d1s == 1 else 0) + (2 if l2P == hi and d2 == -1 and d2s == 1 else 0) \
            + (4 if sbP == hi and sd == -1 and sdS == 1 else 0)
    return ms, mb


def model_b(tfs, useB, wait_min=5, htf=None, sel=None):
    """Independent model of 'フラット→帯＋端の線転換'. Per timeframe the band observations (the previous bar's confirmed band at
    its time_close, then the new bar's start band) run a state machine: flat -> red arms SELL, flat -> blue arms BUY; flat or the
    opposite band disarms (and drops that timeframe's events from the candidates); while armed, the first start whose band is still
    the armed colour and whose edge-line mask is set is that timeframe's event. All events are then sorted (time, drops first,
    timeframe) and matched in short-to-long order with OSeq. Returns [(mark_x, dir, times)] and the events."""
    ev = []
    for rank, (ks, packs) in tfs.items():
        if not useB[rank]:
            continue
        last = None   # (useB here = the timeframes the pattern uses anywhere)
        arm = {1: None, -1: None}
        fired = {1: False, -1: False}
        had = {1: False, -1: False}
        for j, k in enumerate(ks):
            pk = packs[j]
            stP, tcP, stS, ma, mz = pk[4], pk[12], pk[13], pk[14], pk[15]
            for (t, b) in ((tcP, stP), (k, stS)):
                if t is None or b is None:
                    continue
                for col in (-1, 1):
                    if b == col:
                        if last == 0 and arm[col] is None:
                            arm[col], fired[col] = t, False
                    else:
                        arm[col], fired[col] = None, False
                        if had[col]:
                            ev.append((t, 0, rank, col, None))     # drop (col -1 = SELL drop, 1 = BUY drop)
                            had[col] = False
                last = b
            for col, m in ((-1, ma), (1, mz)):
                if stS == col and arm[col] is not None and not fired[col] and m:
                    fired[col], had[col] = True, True
                    ev.append((k, 1, rank, col, (m, arm[col])))
    ev.sort(key=lambda e: (e[0], e[1], e[2]))
    W = wait_min * M
    out = []
    for d, colD in ((0, -1), (1, 1)):
        evd = [(t, g, rank, 1, True if g == 0 else info[0], t) for (t, g, rank, col, info) in ev if col == colD]
        fn = (lambda b, d=d: sel_stages(sel, 1, d, b)) if htf is not None else (lambda b: tuple(i for i in range(4) if useB[i]))
        out += seq_dir(evd, d, fn, W, htf)
    return out, ev


def band_at(htf, t):
    """htf = sorted [(close_time, band)] of the reference higher timeframe; the band in effect at t (None if none yet)."""
    return seg_at(htf, t)[1]


MISS = "MISS"


def hband(bb):
    """band value of an htf entry: MISS (the bar's confirmed band is never delivered) -> unknown; ('LATE', b) -> b."""
    if isinstance(bb, tuple):
        return bb[1]
    return None if bb == MISS else bb


def seg_at(htf, t):
    """(segment start, band) in effect at t. A segment starts where the confirmed band's colour actually changes (red -> flat
    -> red gives three segments; consecutive bars of the same colour stay one segment; an unknown band, including a bar whose
    confirmed band never arrives, is its own colour and also breaks the segment)."""
    sg, b, prev = None, None, object()
    cur_seg = None
    for (tc, bb) in htf:
        v = hband(bb)
        key = ("U", tc) if v is None else v
        if key != prev:
            cur_seg = tc
        prev = key
        if tc <= t:
            sg, b = cur_seg, v
    return sg, b


def seq_dir(events, d, stage_fn, W, htf=None, clr=None):
    """SSS-11 per-direction sequencer shared by both models. events: sorted [(t, g, rank, sub, val, x)] already filtered to this
    direction (g 0 = drop / confirmed original band with val = True, g 1 = event with val = mask). stage_fn(band) -> stages.
    With htf, the band in effect at each event's time picks the stages; a different band than the previous event clears the
    waits (a candidate never spans a band change); an unknown band gives no signal. clr (pattern 帯→フラット only) enables the
    'last-15s mid STB + same-time return' suppression."""
    out = []
    seq = None
    key = object()
    last_sig = None
    conf = {}
    for (t, g, rank, sub, val, x) in events:
        sg, b = seg_at(htf, t) if htf is not None else (0, 0)
        k = (sg, 9 if b is None else b) if htf is not None else 0
        if k != key:
            if seq is not None:
                last_sig = seq.last
            seq = OSeq(stage_fn(b)) if not (htf is not None and b is None) else None
            if seq is not None:
                seq.last = last_sig
            key = k
        if seq is None:
            continue
        if g == 0:
            conf[rank] = t
            seq.drop(rank)
            continue
        m = val
        if clr is not None and sub == 0 and clr[rank] and conf.get(rank) == t:
            m = 0
        r = seq.event(rank, t, m, W)
        if r:
            out.append((x, ("SELL", "BUY")[d], r))
    return out


def sel_stages(sel, p, d, b):
    """stages of pattern p, direction d under band b from a 48-entry selection list (pattern x band x direction x timeframe)."""
    bi = 0 if b == -1 else 1 if b == 0 else 2
    return tuple(i for i in range(4) if sel[((p * 3 + bi) * 2 + d) * 4 + i])


DEFAULT_SEL = []
for _p in range(2):
    for _bi, cols in enumerate((((1, 1, 0, 0), (1, 1, 1, 1)), ((1, 1, 1, 0), (1, 1, 1, 0)), ((1, 1, 1, 1), (1, 1, 0, 0)))):
        for _d in range(2):
            DEFAULT_SEL += [bool(v) for v in cols[_d]]


class PSeq:
    """SSS-8 pattern wait: slots for timeframes 0..p+1, latest per timeframe, any order, earliest..latest <= W."""
    def __init__(self, p):
        self.n = p + 2
        self.slot = [None] * self.n
        self.last_sig = None

    def event(self, rank, t, m, W):
        for k in range(self.n):
            if self.slot[k] is not None and t - self.slot[k] > W:
                self.slot[k] = None
        if m > 0 and self.last_sig != t:
            self.slot[rank] = t
            if None not in self.slot and max(self.slot) - min(self.slot) <= W:
                r = tuple(self.slot)
                self.slot = [None] * self.n
                self.last_sig = t
                return r
        return None


def mid_model(T, b15, tfs, wait_min=5, clr=(True, True, True, True), use=(True, True, True, False), htf=None, sel=None):
    """Independent history model: every start event, mid-bar STB event and confirmed-band event of every target bar of every
    timeframe in tfs, built from the complete data and sorted by (time, confirmed band first, timeframe 15->30->1m->5m,
    closing bar before starting bar); each ON pattern reads the events of its own timeframes with its own waits.
    Returns signals [(mark_x, dir, times)] for '1分まで' only when detail is False (backwards compatible), else
    [(mark_x, dir, pattern, times)]."""
    clr = tuple(clr) + (True,) * (4 - len(clr))
    ev = []
    for rank, (ks, packs) in tfs.items():
        for j, k in enumerate(ks):
            pk = packs[j]
            t0, ms, mb, o, stP, sdP, l1s, l2s, hh20, ll20, hh9, ll9, tcP = pk[:13]
            ev.append((k, rank, 1, ms, mb, k))
            if stP is not None and tcP is not None:
                ev.append((tcP, rank, -1, stP, 0, None))     # confirmed band of the previous bar (sub -1 = before events)
            if o is None:
                continue
            sdLast = sdP
            if hh20 is not None and ll20 is not None:
                sdLast = 1 if o > hh20 else -1 if o < ll20 else sdP
            cumH = cumL = o
            doneS, doneB = ms > 0, mb > 0
            end = ks[j + 1] if j + 1 < len(ks) else float("inf")
            for i, t in enumerate(T):
                if not (k <= t < end):
                    continue
                cumH, cumL = max(cumH, b15[i]["h"]), min(cumL, b15[i]["l"])
                sd = sdP
                if hh20 is not None and ll20 is not None:
                    sd = 1 if cumH > hh20 else -1 if cumL < ll20 else sdP
                lim = ll9 if sd == 1 else hh9
                stb = None if lim is None else (min(cumL, lim) if sd == 1 else max(cumH, lim))
                c = b15[i]["c"]
                xs = xb = 0
                if sd != sdLast and None not in (stb, l1s, l2s, stP, sdLast):
                    band = 1 if (c > l1s and c > l2s and c > stb) else -1 if (c < l1s and c < l2s and c < stb) else 0
                    if band == 0 and stP == 1 and sdLast == 1 and sd == -1 and stb > c and not doneS:
                        xs, doneS = 4, True
                    if band == 0 and stP == -1 and sdLast == -1 and sd == 1 and stb < c and not doneB:
                        xb, doneB = 4, True
                sdLast = sd
                ev.append((t + S15, rank, 0, xs, xb, t))
    ev.sort(key=lambda e: (e[0], 0 if e[2] == -1 else 1, e[1], e[2]))
    W = wait_min * M
    out = []
    for d, col in ((0, 1), (1, -1)):
        evd = []
        for (t, rank, sub, ms, mb, x) in ev:
            if sub == -1:
                if clr[rank] and ms == col:
                    evd.append((t, 0, rank, sub, True, x))
            else:
                m = ms if d == 0 else mb
                if m:
                    evd.append((t, 1, rank, sub, m, x))
        fn = (lambda b, d=d: sel_stages(sel, 0, d, b)) if htf is not None else (lambda b: tuple(i for i in range(4) if use[i]))
        out += seq_dir(evd, d, fn, W, htf, clr)
    return out, ev


def merged(sig):
    """labels as the indicator shows them: one per (x, dir) with the pattern names in signal order."""
    d = {}
    for (x, dr, pn, tt) in sig:
        d.setdefault((x, dr), []).append(pn)
    return sorted((x, dr, "・".join(v)) for (x, dr), v in d.items())


def htf_deliver(htf, now, delay=0):
    """SSS-13: 8 values (time_close[1], band[1], bar_index[1], time_close[2], band[2], bar_index[2], time_close, bar_index);
    bar_index = position in htf. A MISS bar is never delivered as [1] / [2]; a ('LATE', b) bar is not delivered as [1] (only
    later as [2])."""
    r = _htf_deliver5(htf, now, delay)
    k = r[5]
    out = []
    for slot, j in ((1, k), (2, k - 1)):
        if j >= 0:
            bb = htf[j][1]
            if bb == MISS or (isinstance(bb, tuple) and slot == 1):
                out += [None, None, None]
            else:
                out += [htf[j][0], hband(bb), j]
        else:
            out += [None, None, None]
    out += [r[4], k + 1 if k + 1 < len(htf) else None]
    return tuple(out)


def _htf_deliver5(htf, now, delay=0):
    """request.security(htf, [time_close[1], band[1], time_close[2], band[2], time_close], lookahead_on) as seen at chart time
    `now`: htf = sorted [(close_time, band)] of consecutive HTF bars (bar k closes at htf[k][0]); a bar's switch to the next is
    visible `delay` ms after its close."""
    k = -1
    for j, (tc, b) in enumerate(htf):
        if tc + delay <= now:
            k = j
    # k = last closed bar visible; the current bar is k + 1 (closes at htf[k + 1][0] if listed)
    tc1, b1 = (htf[k][0], htf[k][1]) if k >= 0 else (None, None)
    tc2, b2 = (htf[k - 1][0], htf[k - 1][1]) if k >= 1 else (None, None)
    cur = htf[k + 1][0] if k + 1 < len(htf) else None
    return (tc1, b1, tc2, b2, cur, k)


def pine_updates(T, b15, tfs, delays=None, realtime=False, htf=None, htf_delay=0):
    """Chart updates for pine_rows_runner(): one confirmed update per 15s bar (history), or with realtime=True an opening
    update and a confirming update per bar. delays = {rank: {start: ms}} visibility delay of 30s / 1m bars."""
    import bisect
    feeds = {}
    for rank in [r for r in (1, 2, 3) if r in tfs]:
        ks, packs = tfs[rank]
        vis, mx = [], float("-inf")
        for k in ks:
            mx = max(mx, k + (delays or {}).get(rank, {}).get(k, 0))
            vis.append(mx)
        feeds[rank] = (ks, packs, vis)

    def deliver(rank, now):
        ks, packs, vis = feeds[rank]
        j = bisect.bisect_right(vis, now) - 1
        if j < 0:
            return None
        prev = packs[j - 1] if j else (None, 0, 0) + (None,) * 10 + (None, 0, 0)
        return tuple(packs[j]) + tuple(prev)
    ks15, p15 = tfs[0]
    ups = []
    for i, t in enumerate(T):
        base = dict(t=t, e15=(p15[i][1], p15[i][2]), p15=p15[i][3:], hlc=(b15[i]["h"], b15[i]["l"], b15[i]["c"]),
                    need30=t if t % 30_000 == 0 else None, need60=t if t % M == 0 else None,
                    need300=t if t % (5 * M) == 0 else None)
        moments = [(t, False), (t + S15 - 1, True)] if realtime else [(t, True)]
        for now, conf in moments:
            u = dict(base, conf=conf, now=now, r30=deliver(1, now), r60=deliver(2, now),
                     r300=deliver(3, now) if 3 in feeds else None)
            if htf is not None:
                u["htf"] = htf_deliver(htf, now, htf_delay)
            ups.append(u)
    return ups


def series_tfs(T, b15):
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
    out = {0: (T, tf_packs(T, b15, sat_series(b15), S15))}
    for rank, step in ((1, 30_000), (2, M), (3, 5 * M)):
        ks, bars = agg(step)
        out[rank] = (ks, tf_packs(ks, bars, sat_series(bars), step))
    return out


def hand_case(t0, n, packs, hlc, starts=None):
    """Hand-made series: n 15s bars from t0. packs = {(rank, start): 12-tuple pack}; other targets get a neutral pack (no band,
    so no event). hlc = {15s time: (h, l, c)} (default 100 / 100 / 100). starts = {(rank, start): (ms, mb)} start masks."""
    T = [t0 + i * S15 for i in range(n)]
    b15 = [dict(o=100.0, h=hlc.get(t, (100.0, 100.0, 100.0))[0], l=hlc.get(t, (100.0, 100.0, 100.0))[1],
                c=hlc.get(t, (100.0, 100.0, 100.0))[2], v=1) for t in T]
    tfs = {}
    for rank, step in ((0, S15), (1, 30_000), (2, M), (3, 5 * M)):
        ks = sorted({t - t % step for t in T})
        pk = []
        for k in ks:
            m = (starts or {}).get((rank, k), (0, 0))
            p = packs.get((rank, k), (k, 0, 0, 100.0, 0, 1, None, None, None, None, None, None, None, None, 0, 0))
            if len(p) == 12:
                p = tuple(p) + (None,)
            if len(p) == 13:
                p = tuple(p) + (None, 0, 0)
            pk.append((k, m[0], m[1]) + tuple(p[3:]))
        tfs[rank] = (ks, pk)
    return T, b15, tfs


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
          all(re.search(r"^varip array<(?:int|string)>\s+" + v + r"\s*=", code, re.M)
              for v in ("rT", "cC", "cdT", "eT", "mkBar", "smX")))

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
    check("SSS-9: 30s before 15s, then 1m -> no SELL (30s that skipped ahead of 15s is not used for its stage)", r == [])
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
    check("case 1: late 30s (10:00:30, arrives 10:00:45) extends the 10:00:00 15s; the new 15s 10:00:45 does not replace that pair",
          proj(sg) == [(T1 + M, "SELL", (T1, T1 + 30_000, T1 + M))] and not lost)
    rows = build_rows(12, {T1: "B", T1 + 45_000: "B"}, {T1 + 30_000: "B"}, {T1 + M: "B"}, T1, delay30={T1 + 30_000: 15_000})
    check("case 1 (BUY): same", proj(chart_run(rows)[0]) == [(T1 + M, "BUY", (T1, T1 + 30_000, T1 + M))])
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
    prev_src = subprocess.run(["git", "-C", ROOT, "show", "2207947:SatsShortSignal.pine"], capture_output=True, text=True).stdout
    run_prev = pine_rows_runner(prev_src) if prev_src else None
    run_old = pine_rows_runner(old_src) if old_src else None
    for d, nm in (("S", "SELL"), ("B", "BUY")):
        T, ups = gap_case(d)
        log, marks = run_new(ups)
        last = [(tf, t - T) for (tf, t, ct, _m) in log if ct == T + 105_000]
        # the 10:00:45 bar's own close (time_close 10:01:00) is processed in the same batch: 15 / 30 / 1m closes, then the
        # 1m start at 10:01:00 (close before start), then the 30s 10:01:30 start, then the 15s 10:01:45 start.
        sig = [(x - T, k, tip.split(chr(10))[3:6]) for (x, k, tip) in marks if k in (1, -1)]
        k = 1 if d == "S" else -1
        print(f"   Pine order on the 10:01:45 row ({nm}): {last}")
        check(f"SSS-4 ({nm}): Pine processes the 10:01:45 row as 1m 10:01:00 -> 30s 10:01:30 -> 15s 10:01:45 (x2: SELL+BUY waits)",
              last == [(60, 60_000), (30, 90_000)])   # SSS-11: each event goes only to the direction it carries
        check(f"SSS-4/9 ({nm}): one {nm} mark at 10:01:00 from the ordered chain 15s 10:00:00 -> 30s 10:00:30 -> 1m 10:01:00",
              [(x, kk) for (x, kk, _) in sig] == [(60_000, k)] and sig[0][2] == ["15s L2 10:00:00 (開始)", "30s L2 10:00:30 (開始)", "1m L2 10:01:00 (開始)"])
        sg, _ = chart_run(ups)
        check(f"SSS-4 ({nm}): Python model agrees (same mark and pair)",
              [(x[0] - T, x[1], tuple(t - T for t in x[2])) for x in sg] == [(60_000, nm, (0, 30_000, 60_000))])
        if run_old:
            log_o, marks_o = run_old(ups)
            last_o = [(tf, t - T) for (tf, t, ct, *_m) in log_o if ct == T + 105_000]
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

    # ---- 6. SSS-5: mid-bar STB (hand-made series, translated Pine vs independent model) -----------------------------------
    H = 3600_000

    def hm(h, mi, se=0):
        return h * H + mi * M + se * 1000

    def pine_and_model(T, b15, tfs, show_evt=True, realtime=False, delays=None):
        log, marks = run_new(pine_updates(T, b15, tfs, delays, realtime), live=realtime, show_evt=show_evt)
        msig, mev = mid_model(T, b15, tfs)
        return log, marks, msig, mev

    def sigmarks(marks):
        return sorted((x, "SELL" if k == 1 else "BUY") for (x, k, _) in marks if k in (1, -1))

    def tips(marks, k):
        return [tip for (x, kk, tip) in marks if kk == k]

    SELLPK = (0, 0, 0, 100.0, 1, 1, 90.0, 110.0, 120.0, 95.0, 118.0, 96.0)       # prev blue, STB blue, L2 above / L1 below
    BUYPK = (0, 0, 0, 100.0, -1, -1, 110.0, 90.0, 105.0, 80.0, 104.0, 82.0)      # mirror
    # A (09:27-like): 15s S 09:25:00, 30s S 09:25:30, 1m 09:27:00 STB turns red at the 15s bar 09:27:15 (close 09:27:30)
    for nm, pk, k, st, bar, later in (("SELL", SELLPK, 1, (2, 0), (100.2, 94.0, 99.0), (100.0, 90.0, 99.0)),
                                      ("BUY", BUYPK, -1, (0, 2), (106.0, 99.5, 101.0), (110.0, 99.5, 101.0))):
        T, b15, tfs = hand_case(hm(9, 24), 24, {(2, hm(9, 27)): pk},
                                {hm(9, 27): (100.5, 99.5, 100.0), hm(9, 27, 15): bar, hm(9, 27, 45): later},
                                {(0, hm(9, 25)): st, (1, hm(9, 25, 30)): st})
        log, marks, msig, mev = pine_and_model(T, b15, tfs)
        tp = tips(marks, k)
        check(f"SSS-5 A ({nm}): 1m mid STB at the 15s close 09:27:30 completes the chain -> one {nm} on the 15s bar 09:27:15",
              sigmarks(marks) == [(hm(9, 27, 15), nm)] and [(x, d) for (x, d, _) in msig] == [(hm(9, 27, 15), nm)])
        check(f"SSS-5 A ({nm}): tooltip shows the target 1m start and the confirming 15s close",
              len(tp) == 1 and "1m STB 09:27:30 (途中: 対象足の開始 09:27:00 / 15秒確定 09:27:30)" in tp[0]
              and "成立幅 2分30秒" in tp[0] and "成立順: 15s → 30s → 1m" in tp[0])
        ev1m = [(x, tip) for (x, kk, tip) in marks if kk == 0 and "1m STB" in tip]
        check(f"SSS-5 A ({nm}): single 1m event mark on the same 15s bar; the later lower/higher 15s bar adds nothing (no lookahead, no repeat)",
              [x for x, _ in ev1m] == [hm(9, 27, 15)])
    # B (10:43-like): flip on the last 15s bar of the 1m bar (close 10:44:00 = next 1m start, which also starts with S L2)
    T, b15, tfs = hand_case(hm(10, 40), 24, {(2, hm(10, 43)): SELLPK}, {hm(10, 43, 45): (100.2, 94.0, 99.0)},
                            {(0, hm(10, 41)): (2, 0), (1, hm(10, 42)): (2, 0), (2, hm(10, 44)): (2, 0)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    at = [(tf, m) for (tf, t, ct, m) in log if t == hm(10, 44) and tf == 60]
    check("SSS-5 B: 1m close (mid STB, mask 4) is processed before the 1m start at the same time 10:44:00 (mask 2)",
          at[:2] == [(60, 4), (60, 4)][:1] + [(60, 0)] or at.index((60, 4)) < at.index((60, 2)))
    check("SSS-5 B: one SELL on the 15s bar 10:43:45 (the following 1m start finds the waits reset)",
          sigmarks(marks) == [(hm(10, 43, 45), "SELL")] and [(x, d) for (x, d, _) in msig] == [(hm(10, 43, 45), "SELL")])
    # C (09:01-like, start-based 'S 1m L2'): kept; a later mid flip in the same 1m target does not re-trigger the 1m
    T, b15, tfs = hand_case(hm(8, 58), 24, {(2, hm(9, 1)): SELLPK}, {hm(9, 1, 15): (100.2, 94.0, 99.0)},
                            {(0, hm(8, 59)): (2, 0), (1, hm(9, 0)): (2, 0), (2, hm(9, 1)): (2, 0)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    tp = tips(marks, 1)
    check("SSS-5 C: start-based 1m L2 at 09:01:00 -> SELL at the 1m start, tooltip '1m L2 09:01:00 (開始)'",
          sigmarks(marks) == [(hm(9, 1), "SELL")] and "1m L2 09:01:00 (開始)" in tp[0] and "15s L2 08:59:00 (開始)" in tp[0])
    check("SSS-5 C: same target already started with SELL -> its mid STB flip is not recorded again",
          not [1 for (tf, t, ct, m) in log if tf == 60 and m == 4])
    # D: high and low both broken in one 15s bar -> STB blue (high side first): no SELL; on the mirrored setup -> BUY
    T, b15, tfs = hand_case(hm(9, 24), 24, {(2, hm(9, 27)): SELLPK}, {hm(9, 27, 15): (121.0, 94.0, 99.0)},
                            {(0, hm(9, 25)): (2, 0), (1, hm(9, 25, 30)): (2, 0)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    check("SSS-5 D: both 20-bar high and low broken in one 15s bar -> blue wins, no SELL", sigmarks(marks) == [] and msig == [])
    bp = (0, 0, 0, 100.0, -1, -1, 110.0, 90.0, 120.0, 95.0, 118.0, 82.0)
    T, b15, tfs = hand_case(hm(9, 24), 24, {(2, hm(9, 27)): bp}, {hm(9, 27, 15): (121.0, 94.0, 99.0)},
                            {(0, hm(9, 25)): (0, 2), (1, hm(9, 25, 30)): (0, 2)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    check("SSS-5 D: the same both-sides bar on a red-band / red-STB target -> red->blue -> BUY on that 15s bar",
          sigmarks(marks) == [(hm(9, 27, 15), "BUY")] and [(x, d) for (x, d, _) in msig] == [(hm(9, 27, 15), "BUY")])
    # E: a 30s mid STB at the 15s close 09:30:30 pairs with the 15s start event at 09:30:30 (15s start before 30s close)
    T, b15, tfs = hand_case(hm(9, 29), 16, {(1, hm(9, 30)): SELLPK}, {hm(9, 30, 15): (100.2, 94.0, 99.0)},
                            {(0, hm(9, 30, 30)): (2, 0), (2, hm(9, 31)): (2, 0)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    check("SSS-5 E: 15s start 09:30:30 + 30s mid 09:30:30 (same time, 15s first) + 1m start 09:31:00 -> SELL at 09:31:00",
          sigmarks(marks) == [(hm(9, 31), "SELL")] and [x[2] for x in msig] == [(hm(9, 30, 30), hm(9, 30, 30), hm(9, 31))])
    # F: realtime (open + confirm update per bar) with the 1m data 20 s late and 30s data 10 s late -> same marks as history
    T, b15, tfs = hand_case(hm(9, 24), 24, {(2, hm(9, 27)): SELLPK}, {hm(9, 27, 15): (100.2, 94.0, 99.0)},
                            {(0, hm(9, 25)): (2, 0), (1, hm(9, 25, 30)): (2, 0)})
    dl = {1: {k: 10_000 for k in tfs[1][0]}, 2: {k: 20_000 for k in tfs[2][0]}}
    _, mk_rt = run_new(pine_updates(T, b15, tfs, dl, realtime=True), live=True)
    _, mk_h = run_new(pine_updates(T, b15, tfs))
    check("SSS-5 F: realtime with late 30s / 1m data -> same SELL position as history, tooltip has the live detection time",
          sigmarks(mk_rt) == sigmarks(mk_h) == [(hm(9, 27, 15), "SELL")] and "ライブ検知" in tips(mk_rt, 1)[0]
          and "ライブ検知" not in tips(mk_h, 1)[0])

    # ---- 6b. SSS-9: ON timeframes in short-to-long order, staged candidates (model + translated Pine) -----------------------
    def both(events, n_bars=40, **kw):
        rows = scripted(events, n_bars=n_bars)
        mdl = [(x[0], x[1], x[2]) for x in chart_run(rows, **kw)[0]]
        _, mk = run_new(rows)
        return mdl, sigmarks(mk), mk
    mdl, pm, _ = both({(15, T0): "S", (60, T0 + M): "S", (30, T0 + 90_000): "S", (60, T0 + 2 * M): "S"})
    check("SSS-9: 15s -> 1m -> 30s: the early 1m (1:00) is skipped; the next 1m (2:00) after the 30s completes -> SELL at 2:00",
          mdl == [(T0 + 2 * M, "SELL", (T0, T0 + 90_000, T0 + 2 * M))] and pm == [(T0 + 2 * M, "SELL")])
    mdl, pm, _ = both({(60, T0): "S", (30, T0 + 30_000): "S", (15, T0 + 45_000): "S"})
    check("SSS-9: 1m -> 30s -> 15s (reverse order) -> nothing", mdl == [] and pm == [])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + 45_000): "S", (60, T0 + M): "S"})
    check("SSS-9: 15s -> 30s -> 15s again -> 1m: the original 15s/30s pair is kept and completes",
          mdl == [(T0 + M, "SELL", (T0, T0 + 30_000, T0 + M))] and pm == [(T0 + M, "SELL")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 30_000): "S", (15, T0 + 45_000): "S", (30, T0 + M): "S", (60, T0 + M): "S"})
    check("SSS-9: a newer 15s -> 30s pair (newer start) replaces the older pair at the same stage -> SELL uses 0:45 / 1:00",
          mdl == [(T0 + M, "SELL", (T0 + 45_000, T0 + M, T0 + M))] and pm == [(T0 + M, "SELL")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 30_000): "S", (30, T0 + 90_000): "S", (60, T0 + 2 * M): "S"})
    check("SSS-9: same start, newer end replaces (15s 0:00 + 30s 1:30) -> SELL 0:00 / 1:30 / 2:00",
          mdl == [(T0 + 2 * M, "SELL", (T0, T0 + 90_000, T0 + 2 * M))] and pm == [(T0 + 2 * M, "SELL")])
    mdl, pm, _ = both({(15, T0): "B", (30, T0): "B", (60, T0): "B"})
    check("SSS-9: 15s / 30s / 1m at the same time -> BUY (shorter timeframes first)", mdl == [(T0, "BUY", (T0, T0, T0))]
          and pm == [(T0, "BUY")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 2 * M): "S", (60, T0 + 5 * M): "S"})
    check("SSS-9: first..last exactly 5 min -> SELL", mdl == [(T0 + 5 * M, "SELL", (T0, T0 + 2 * M, T0 + 5 * M))]
          and pm == [(T0 + 5 * M, "SELL")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 2 * M): "S", (60, T0 + 5 * M + 30_000): "S", (15, T0 + 4 * M): "S",
                       (30, T0 + 4 * M + 30_000): "S", (60, T0 + 6 * M): "S"})
    check("SSS-9: the 0:00 chain expires at 5:30 (no SELL); the newer 4:00 chain completes at 6:00",
          mdl == [(T0 + 6 * M, "SELL", (T0 + 4 * M, T0 + 4 * M + 30_000, T0 + 6 * M))] and pm == [(T0 + 6 * M, "SELL")])
    mdl, pm, _ = both({(15, T0): "B", (30, T0 + 30_000): "B", (15, T0 + M): "S", (30, T0 + M): "S", (60, T0 + M): "SB"})
    check("SSS-9: SELL and BUY complete on the same 1m start independently",
          sorted(mdl) == [(T0 + M, "BUY", (T0, T0 + 30_000, T0 + M)), (T0 + M, "SELL", (T0 + M, T0 + M, T0 + M))]
          and pm == [(T0 + M, "BUY"), (T0 + M, "SELL")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + M): "S", (15, T0 + 2 * M): "B", (30, T0 + 2 * M): "B",
                       (60, T0 + 3 * M): "B"})
    check("SSS-9: a SELL clears only the SELL candidates; the BUY chain completes later", mdl == [
        (T0 + M, "SELL", (T0, T0 + 30_000, T0 + M)), (T0 + 3 * M, "BUY", (T0 + 2 * M, T0 + 2 * M, T0 + 3 * M))]
        and pm == [(T0 + M, "SELL"), (T0 + 3 * M, "BUY")])
    mdl, pm, _ = both({(15, T0): "S", (30, T0 + 30_000): "S", (60, T0 + M): "S", (60, T0 + 2 * M): "S"})
    check("SSS-9: after a SELL the candidates are cleared (the next 1m alone does nothing)", len(mdl) == 1 and len(pm) == 1)
    # mid-bar STB as a stage; label on the confirming 15s bar
    T, b15, tfs = hand_case(hm(9, 24), 24, {(1, hm(9, 27)): SELLPK}, {hm(9, 27, 15): (100.2, 94.0, 99.0)},
                            {(0, hm(9, 27)): (2, 0), (2, hm(9, 28)): (2, 0)})
    log, marks, msig, mev = pine_and_model(T, b15, tfs)
    tp = tips(marks, 1)
    check("SSS-9: 15s 9:27:00 -> 30s mid STB 9:27:30 -> 1m 9:28:00 -> SELL at 9:28:00, tooltip has the 30s mid-bar line",
          sigmarks(marks) == [(hm(9, 28), "SELL")] and [(x, d) for (x, d, _) in msig] == [(hm(9, 28), "SELL")]
          and "30s STB 09:27:30 (途中: 対象足の開始 09:27:00 / 15秒確定 09:27:30)" in tp[0])

    # ---- 6c. SSS-7/9: band-return clears; span in the tooltip ---------------------------------------------------------------
    def CONF(k, band):
        """neutral pack whose previous confirmed bar closed at k with bandState `band` (no lines -> no mid-bar STB)."""
        return (k, 0, 0, 100.0, band, 1, None, None, None, None, None, None, k)

    def run7(packs, hlc, starts, n=24, t0=None, clr=(True, True, True, True), use=(True, True, True, False)):
        T, b15, tfs = hand_case(t0 if t0 is not None else hm(9, 23), n, packs, hlc, starts)
        _, mk = run_new(pine_updates(T, b15, tfs), clr=clr, use=use)
        msig, _ = mid_model(T, b15, tfs, clr=clr, use=use)
        return sigmarks(mk), sorted((x, d) for (x, d, _) in msig), mk
    OFF = (False, False, False, False)
    st1 = {(0, hm(9, 25)): (2, 0), (1, hm(9, 25, 30)): (2, 0), (2, hm(9, 26)): (2, 0)}
    pk1 = {(0, hm(9, 25, 15)): CONF(hm(9, 25, 15), 1)}
    pm, md, _ = run7(pk1, {}, st1)
    check("SSS-9: 15s confirms blue after its SELL -> candidates with that 15s are dropped -> no SELL (Pine and model)", pm == md == [])
    pm, md, _ = run7(pk1, {}, st1, clr=OFF)
    check("SSS-9: same with the clear options OFF -> SELL at 9:26:00", pm == md == [(hm(9, 26), "SELL")])
    pm, md, _ = run7(pk1, {}, {**st1, (0, hm(9, 25, 15)): (2, 0)})
    check("SSS-9: a new 15s SELL at the same 9:25:15 (after the clear) starts a new chain -> SELL at 9:26:00",
          pm == md == [(hm(9, 26), "SELL")])
    st2 = {(0, hm(9, 24, 45)): (2, 0), (1, hm(9, 25)): (2, 0), (2, hm(9, 25)): (2, 0)}
    pk2 = {(0, hm(9, 25)): CONF(hm(9, 25), 1)}
    pm, md, _ = run7(pk2, {}, st2)
    check("SSS-9: 15s confirms blue at 9:25:00 while 30s / 1m SELL start at 9:25:00 -> clear first -> no SELL", pm == md == [])
    pm, md, _ = run7(pk2, {}, st2, clr=OFF)
    check("SSS-9: same with the options OFF -> SELL at 9:25:00", pm == md == [(hm(9, 25), "SELL")])
    st3 = {(0, hm(9, 24, 45)): (2, 0), (1, hm(9, 25)): (2, 0), (2, hm(9, 26)): (2, 0)}
    pk3 = {(1, hm(9, 25, 30)): CONF(hm(9, 25, 30), 1)}
    pm, md, _ = run7(pk3, {}, st3)
    pm2, md2, _ = run7(pk3, {}, {**st3, (1, hm(9, 25, 30)): (2, 0)})
    pm_off, md_off, _ = run7(pk3, {}, st3, clr=(True, False, True, True))
    check("SSS-9: 30s confirms blue -> the 15s+30s candidate is dropped but the 15s-only candidate stays (in time): "
          "no SELL; a new 30s at 9:25:30 completes from the kept 15s; 30s option OFF -> SELL",
          pm == md == [] and pm2 == md2 == [(hm(9, 26), "SELL")] and pm_off == md_off == [(hm(9, 26), "SELL")])
    ALL4 = (True, True, True, True)
    st4 = {(0, hm(9, 24)): (0, 2), (1, hm(9, 24, 30)): (0, 2), (2, hm(9, 25)): (0, 2), (3, hm(9, 25)): (0, 2)}
    pk4 = {(2, hm(9, 25)): CONF(hm(9, 25), -1)}
    st4b = {(0, hm(9, 23)): (0, 2), (1, hm(9, 23, 30)): (0, 2), (2, hm(9, 24)): (0, 2), (3, hm(9, 25)): (0, 2)}
    pm, md, _ = run7(pk4, {}, st4b, n=40, t0=hm(9, 20), use=ALL4)
    pm_off, md_off, _ = run7(pk4, {}, st4b, n=40, t0=hm(9, 20), use=ALL4, clr=(True, True, False, True))
    check("SSS-9: with 5m ON, 1m confirms red at 9:25:00 -> the BUY 15s+30s+1m candidate is dropped (no BUY); 1m option OFF "
          "-> BUY at 9:25:00", pm == md == [] and pm_off == md_off == [(hm(9, 25), "BUY")])
    pm, md, _ = run7({(2, hm(9, 25)): CONF(hm(9, 25), 1)}, {}, st4b, n=40, t0=hm(9, 20), use=ALL4)
    check("SSS-9: a blue confirm does not drop BUY candidates (BUY at 9:25:00)", pm == md == [(hm(9, 25), "BUY")])
    for nm, band in (("flat 0", 0), ("missing (na)", None)):
        pm, md, _ = run7({(0, hm(9, 25, 15)): CONF(hm(9, 25, 15), band)}, {}, st1)
        check(f"SSS-9: 15s confirm band {nm} -> no clear -> SELL at 9:26:00", pm == md == [(hm(9, 26), "SELL")])
    st6 = {(0, hm(9, 25)): (2, 0), (1, hm(9, 25, 30)): (2, 0)}
    hl6 = {hm(9, 27, 45): (100.2, 94.0, 99.0)}
    pk6 = {(2, hm(9, 27)): SELLPK, (2, hm(9, 28)): CONF(hm(9, 28), 1)}
    pm, md, _ = run7(pk6, hl6, st6)
    check("SSS-9: 1m mid STB at its last 15s close 9:28:00 + 1m confirms blue at 9:28:00 -> the STB is not registered", pm == md == [])
    pm, md, _ = run7(pk6, hl6, st6, clr=OFF)
    check("SSS-9: same with the options OFF -> SELL on the confirming 15s bar 9:27:45", pm == md == [(hm(9, 27, 45), "SELL")])
    pm, md, _ = run7(pk6, hl6, {**st6, (2, hm(9, 28)): (2, 0)})
    check("SSS-9: ... while a new 1m start SELL at 9:28:00 is registered normally -> SELL at 9:28:00", pm == md == [(hm(9, 28), "SELL")])
    for starts, span in (({(0, hm(9, 25)): (2, 0), (1, hm(9, 25, 30)): (2, 0), (2, hm(9, 26)): (2, 0)}, "成立幅 1分"),
                         ({(0, hm(9, 25, 15)): (2, 0), (1, hm(9, 25, 30)): (2, 0), (2, hm(9, 26)): (2, 0)}, "成立幅 45秒"),
                         ({(0, hm(9, 23, 30)): (2, 0), (1, hm(9, 25)): (2, 0), (2, hm(9, 28)): (2, 0)}, "成立幅 4分30秒"),
                         ({(0, hm(9, 23)): (2, 0), (1, hm(9, 25)): (2, 0), (2, hm(9, 28)): (2, 0)}, "成立幅 5分")):
        _, _, mk = run7({}, {}, starts, n=32, t0=hm(9, 22))
        tp = tips(mk, 1)
        check(f"SSS-9: tooltip shows '{span}'", len(tp) == 1 and (span + "\n") in tp[0])

    # ---- 6d. SSS-9: timeframe combinations ---------------------------------------------------------------------------------
    def run9(T, b15, tfs, use, clr=(True, True, True, True), delays=None, realtime=False):
        _, mk = run_new(pine_updates(T, b15, tfs, delays, realtime), live=realtime, use=use, clr=clr)
        sig, _ = mid_model(T, b15, tfs, clr=clr, use=use)
        return sigmarks(mk), sorted((x, d) for (x, d, _) in sig), mk
    T, b15, tfs = hand_case(hm(9, 20), 24, {}, {}, {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0)})
    pm, md, mk = run9(T, b15, tfs, (True, True, False, False))
    check("SSS-9: 15s + 30s only -> SELL at the 30s 9:21:30, tooltip '成立順: 15s → 30s'",
          pm == md == [(hm(9, 21, 30), "SELL")] and "成立順: 15s → 30s" in tips(mk, 1)[0])
    T, b15, tfs = hand_case(hm(9, 20), 24, {}, {}, {(1, hm(9, 21)): (0, 2), (1, hm(9, 22)): (0, 2)})
    pm, md, _ = run9(T, b15, tfs, (False, True, False, False))
    check("SSS-9: only 30s ON -> each single 30s event signals (BUY at 9:21:00 and 9:22:00)",
          pm == md == [(hm(9, 21), "BUY"), (hm(9, 22), "BUY")])
    pm, md, _ = run9(T, b15, tfs, (False, False, False, False))
    check("SSS-9: all OFF -> no signal", pm == md == [])
    T, b15, tfs = hand_case(hm(9, 20), 24, {}, {}, {(1, hm(9, 21)): (2, 0), (2, hm(9, 22)): (2, 0), (0, hm(9, 21, 15)): (2, 0)})
    pm, md, _ = run9(T, b15, tfs, (False, True, True, False))
    check("SSS-9: 15s OFF (30s -> 1m) -> SELL at 9:22:00; the 15s event is ignored", pm == md == [(hm(9, 22), "SELL")])
    T, b15, tfs = hand_case(hm(9, 15), 60, {}, {}, {(0, hm(9, 17)): (0, 2), (1, hm(9, 17, 30)): (0, 2), (2, hm(9, 18)): (0, 2),
                                                    (3, hm(9, 20)): (0, 2)})
    pm, md, _ = run9(T, b15, tfs, ALL4)
    check("SSS-9: 15s -> 30s -> 1m -> 5m (all ON) -> BUY at the 5m start 9:20:00", pm == md == [(hm(9, 20), "BUY")])
    T, b15, tfs = hand_case(hm(9, 20), 40, {(3, hm(9, 25)): SELLPK}, {hm(9, 26, 15): (100.2, 94.0, 99.0)},
                            {(0, hm(9, 24)): (2, 0), (1, hm(9, 24, 30)): (2, 0), (2, hm(9, 25)): (2, 0)})
    pm, md, mk = run9(T, b15, tfs, ALL4)
    check("SSS-9: 5m mid STB (target 9:25, flip at the 15s close 9:26:30) completes 15s->30s->1m->5m on the 15s bar 9:26:15",
          pm == md == [(hm(9, 26, 15), "SELL")]
          and "5m STB 09:26:30 (途中: 対象足の開始 09:25:00 / 15秒確定 09:26:30)" in tips(mk, 1)[0])
    # a late 5m feed does not hold a selection without 5m; with 5m ON the signal waits for the 5m data, then lands at its start
    T, b15, tfs = hand_case(hm(9, 20), 48, {}, {}, {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0), (2, hm(9, 22)): (2, 0),
                                                    (3, hm(9, 25)): (2, 0)})
    dl = {3: {hm(9, 20): 150_000, hm(9, 25): 60_000}}
    ups = pine_updates(T, b15, tfs, dl, realtime=True)
    i22 = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 22, 15)) + 1
    _, mk_a = run_new(ups[:i22], live=True, use=(True, True, True, False))
    _, mk_b = run_new(ups, live=True, use=ALL4)
    _, mk_h = run_new(pine_updates(T, b15, tfs), use=ALL4)
    check("SSS-9: 5m data late: 15s->30s->1m fires at 9:22:00 without waiting; with 5m ON the SELL comes at the 5m start "
          "9:25:00 once the data arrives (same as history)",
          sigmarks(mk_a) == [(hm(9, 22), "SELL")] and sigmarks(mk_b) == sigmarks(mk_h) == [(hm(9, 25), "SELL")])

    # ---- 6e. SSS-10: pattern 'フラット→帯＋端の線転換' -------------------------------------------------------------------------
    import acc_pine as ap
    fsrc = pine[pine.index("f_edgeMask(float l1P"):pine.index("//  新パターンの説明")]
    fenv = ap.make_env(type("NB", (), {"__getattr__": lambda self, k: (lambda *a, **kw: None)})(), [])
    exec(compile(ap.Translator().translate(ap.logical_lines(fsrc)), "f_edgeMask", "exec"), fenv)
    em = fenv["f_edgeMask"]
    check("SSS-10 f_edgeMask (Pine): lowest line LINE2 +1 -> -1 -> SELL mask L2", em(105.0, 95.0, 100.0, 1, 1, 1, 1, -1, 1) == (2, 0))
    check("SSS-10 f_edgeMask (Pine): a non-lowest line flipping does not count", em(105.0, 95.0, 100.0, -1, 1, 1, -1, 1, -1) == (0, 0))
    check("SSS-10 f_edgeMask (Pine): tie for lowest (L1 = STB), only STB flips -> STB", em(95.0, 100.0, 95.0, 1, 1, 1, 1, 1, -1) == (4, 0))
    check("SSS-10 f_edgeMask (Pine): tie, both flip -> L1+STB (one event per timeframe)", em(95.0, 100.0, 95.0, 1, 1, 1, -1, 1, -1) == (5, 0))
    check("SSS-10 f_edgeMask (Pine): highest line STB -1 -> +1 -> BUY mask STB", em(95.0, 100.0, 105.0, 1, 1, -1, 1, 1, 1) == (0, 4))
    check("SSS-10 f_edgeMask (Pine): a line na -> nothing", em(None, 100.0, 105.0, 1, 1, -1, 1, 1, 1) == (0, 0))

    def BP(k, stP, stS, ma=0, mz=0, tc=None):
        """pack whose previous bar confirmed with band stP at tc (default k) and whose start band is stS, edge masks ma / mz"""
        return (k, 0, 0, 100.0, stP, 1, None, None, None, None, None, None, k if tc is None else tc, stS, ma, mz)

    def runB(packs, useB, n=24, t0=None, use=(False, False, False, False), starts=None, delays=None, realtime=False):
        T, b15, tfs = hand_case(t0 if t0 is not None else hm(9, 20), n, packs, {}, starts or {})
        _, mk = run_new(pine_updates(T, b15, tfs, delays, realtime), live=realtime, use=use, useB=useB)
        sigB, _ = model_b(tfs, useB)
        return sigmarks(mk), sorted((x, d) for (x, d, _) in sigB), mk, list(run_new.labels)
    U15 = (True, False, False, False)
    pm, md, mk, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2)}, U15)
    check("SSS-10: 15s flat -> red at the start 9:21:00 with the lowest line flipping red at the same start -> SELL",
          pm == md == [(hm(9, 21), "SELL")] and "15s 帯点灯 09:21:00 / 線転換 09:21:00 L2" in tips(mk, 1)[0])
    pm, md, mk, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1), (0, hm(9, 21, 15)): BP(hm(9, 21, 15), -1, -1, ma=2)}, U15)
    check("SSS-10: red lights at 9:21:00, the edge line flips at the next start 9:21:15 -> SELL at 9:21:15",
          pm == md == [(hm(9, 21, 15), "SELL")] and "15s 帯点灯 09:21:00 / 線転換 09:21:15 L2" in tips(mk, 1)[0])
    pm, md, _, _ = runB({(0, hm(9, 20, 45)): BP(hm(9, 20, 45), 0, 1), (0, hm(9, 21)): BP(hm(9, 21), 1, -1, ma=2)}, U15)
    check("SSS-10: blue -> red directly (no flat) does not arm -> no SELL", pm == md == [])
    pm, md, _, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1), (0, hm(9, 21, 15)): BP(hm(9, 21, 15), -1, 0),
                         (0, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, -1, ma=1)}, U15)
    check("SSS-10: flat at 9:21:15 disarms, flat -> red again at 9:21:30 re-arms -> SELL at 9:21:30", pm == md == [(hm(9, 21, 30), "SELL")])
    pm, md, _, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2), (0, hm(9, 21, 15)): BP(hm(9, 21, 15), -1, -1, ma=2)}, U15)
    check("SSS-10: once per red section (a second edge flip in the same section is ignored)", pm == md == [(hm(9, 21), "SELL")])
    pm, md, _, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1), (0, hm(9, 21, 15)): BP(hm(9, 21, 15), None, None),
                         (0, hm(9, 21, 30)): BP(hm(9, 21, 30), -1, -1, ma=2)}, U15)
    check("SSS-10: a missing band value is not treated as flat (stays armed) -> SELL at 9:21:30", pm == md == [(hm(9, 21, 30), "SELL")])
    pm2, md2, _, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, 0), (0, hm(9, 21, 15)): BP(hm(9, 21, 15), -1, -1, ma=2)}, U15)
    check("SSS-10: confirmed band red (9:21:15) after a flat start arms at the confirm; the edge flip at the 9:21:15 start fires",
          pm2 == md2 == [(hm(9, 21, 15), "SELL")])
    UB = (True, True, True, False)
    chain = {(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2), (1, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, -1, ma=1),
             (2, hm(9, 22)): BP(hm(9, 22), 0, -1, ma=4)}
    pm, md, mk, _ = runB(chain, UB)
    tp = tips(mk, 1)
    check("SSS-10: 15s 9:21:00 -> 30s 9:21:30 -> 1m 9:22:00 -> 'SELL フラット→帯＋端の線転換' at 9:22:00 (Pine and model)",
          pm == md == [(hm(9, 22), "SELL")] and "成立幅 1分" in tp[0]
          and "30s 帯点灯 09:21:30 / 線転換 09:21:30 L1" in tp[0] and "1m 帯点灯 09:22:00 / 線転換 09:22:00 STB" in tp[0])
    pm, md, _, _ = runB({**chain, (0, hm(9, 21, 45)): BP(hm(9, 21, 45), -1, 0)}, UB)
    check("SSS-10: the 15s band turns flat at 9:21:45 -> candidates with that 15s event are dropped -> no SELL", pm == md == [])
    pm, md, _, _ = runB({**chain, (1, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, -1, ma=1), (0, hm(9, 21, 45)): BP(hm(9, 21, 45), -1, 1)}, UB)
    check("SSS-10: the 15s band turns to the opposite colour -> dropped as well -> no SELL", pm == md == [])
    chainB = {(0, hm(9, 21)): BP(hm(9, 21), 0, 1, mz=2), (1, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, 1, mz=1),
              (2, hm(9, 22)): BP(hm(9, 22), 0, 1, mz=4)}
    pm, md, _, _ = runB(chainB, UB)
    check("SSS-10: BUY mirror (flat -> blue, highest line red -> blue) -> BUY at 9:22:00", pm == md == [(hm(9, 22), "BUY")])
    pm, md, _, _ = runB({(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2), (2, hm(9, 22)): BP(hm(9, 22), 0, -1, ma=4),
                         (1, hm(9, 22, 30)): BP(hm(9, 22, 30), 0, -1, ma=1)}, UB)
    check("SSS-10: 15s -> 1m -> 30s: the early 1m is not used for its stage -> no SELL", pm == md == [])
    # both patterns ON: same position -> one label with both names
    stA = {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0), (2, hm(9, 22)): (2, 0)}
    _, _, mk, labels = runB(chain, UB, use=(True, True, True, False), starts=stA)
    check("SSS-10: both patterns complete at 9:22:00 -> one label 'SELL 帯→フラット・フラット→帯＋端の線転換'",
          sigmarks(mk) == [(hm(9, 22), "SELL")] and labels == [(hm(9, 22), "SELL 帯→フラット・フラット→帯＋端の線転換")])
    # data wait per pattern: 帯→フラット uses 5m (late), フラット→帯 uses 15s/30s only -> not held
    T, b15, tfs = hand_case(hm(9, 20), 48, {(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2), (1, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, -1, ma=1)},
                            {}, {})
    dl = {3: {hm(9, 20): 150_000, hm(9, 25): 150_000}}
    ups = pine_updates(T, b15, tfs, dl, realtime=True)
    i22 = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 21, 45)) + 1
    _, mk_a = run_new(ups[:i22], live=True, use=(True, True, True, True), useB=(True, True, False, False))
    check("SSS-10: with the 5m data late for 帯→フラット, フラット→帯 (15s+30s) still fires at 9:21:30",
          sigmarks(mk_a) == [(hm(9, 21, 30), "SELL")])

    # ---- 6f. SSS-11: switch the timeframes by the reference higher timeframe's band ----------------------------------------
    def mk_sel(over=None):
        sel = list(DEFAULT_SEL)
        for (pp, bi, dd), cols in (over or {}).items():
            for i in range(4):
                sel[((pp * 3 + bi) * 2 + dd) * 4 + i] = bool(cols[i])
        return sel

    def runH(htf, starts=None, packs=None, sel=None, n=32, t0=None, A=True, B=False, delays=None, realtime=False, htf_delay=0):
        sel = sel or mk_sel()
        T, b15, tfs = hand_case(t0 if t0 is not None else hm(9, 20), n, packs or {}, {}, starts or {})
        ups = pine_updates(T, b15, tfs, delays, realtime, htf=htf, htf_delay=htf_delay)
        _, mk = run_new(ups, live=realtime, htf_sel=sel, patA=A, patB=B, useB=(True, True, True, True) if B else None)
        md = []
        if A:
            md += [(x, d) for (x, d, _) in mid_model(T, b15, tfs, htf=htf, sel=sel)[0]]
        if B:
            useU = tuple(any(sel[((1 * 3 + bi) * 2 + dd) * 4 + i] for bi in range(3) for dd in range(2)) for i in range(4))
            md += [(x, d) for (x, d, _) in model_b(tfs, useU, htf=htf, sel=sel)[0]]
        return sigmarks(mk), sorted(set(md)), mk, ups
    RED = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 30), -1), (hm(9, 40), -1)]
    FLAT = [(hm(9, 18), 0), (hm(9, 20), 0), (hm(9, 30), 0), (hm(9, 40), 0)]
    stS2 = {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0)}
    stB2 = {(0, hm(9, 22)): (0, 2), (1, hm(9, 22, 30)): (0, 2)}
    pm, md, mk, _ = runH(RED, {**stS2, **stB2})
    check("SSS-11: HTF red: SELL uses 15s->30s -> SELL at 9:21:30; BUY needs 15s/30s/1m/5m -> no BUY (Pine and model)",
          pm == md == [(hm(9, 21, 30), "SELL")])
    tp = tips(mk, 1)[0]
    check("SSS-11: tooltip shows the HTF, its band and the order ('上位足 1時間 赤' / '成立順: 15s → 30s')",
          "上位足 1時間 赤" in tp and "成立順: 15s → 30s" in tp)
    st3 = {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0), (2, hm(9, 22)): (2, 0)}
    pm, md, _, _ = runH(FLAT, st3)
    check("SSS-11: HTF flat: SELL uses 15s->30s->1m -> SELL at 9:22:00", pm == md == [(hm(9, 22), "SELL")])
    pm, md, _, _ = runH(FLAT, st3, sel=mk_sel({(0, 1, 0): (0, 0, 0, 0)}))
    check("SSS-11: HTF flat with the flat-SELL column all OFF -> no SELL", pm == md == [])
    CHG = [(hm(9, 18), 0), (hm(9, 20), 0), (hm(9, 22), 1), (hm(9, 24), 1), (hm(9, 40), 1)]
    pm, md, _, _ = runH(CHG, st3)
    check("SSS-11: 15s/30s under flat, the HTF band turns blue at 9:22:00 -> waits cleared, the 9:22 1m uses blue (needs 5m) -> no SELL",
          pm == md == [])
    CHGR = [(hm(9, 18), 0), (hm(9, 20), 0), (hm(9, 22), -1), (hm(9, 24), -1), (hm(9, 40), -1)]
    pm, md, _, _ = runH(CHGR, {(0, hm(9, 22)): (2, 0), (1, hm(9, 22)): (2, 0)})
    check("SSS-11: HTF turns red at 9:22:00; 15s and 30s SELL at the same 9:22:00 use the new (red) column -> SELL at 9:22:00",
          pm == md == [(hm(9, 22), "SELL")])
    # a delayed 30s event uses the HTF band at its own time (red until 9:22, flat after)
    REDF = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), 0), (hm(9, 24), 0), (hm(9, 40), 0)]
    T, b15, tfs = hand_case(hm(9, 20), 32, {}, {}, stS2)
    pm_h, md_h, _, _ = runH(REDF, stS2)
    pm_rt, _, _, _ = runH(REDF, stS2, delays={1: {hm(9, 21, 30): 40_000}}, realtime=True)
    check("SSS-11: 30s 9:21:30 (red) arriving at 9:22:10 after the HTF turned flat still uses red -> SELL at 9:21:30 (= history)",
          pm_h == md_h == pm_rt == [(hm(9, 21, 30), "SELL")])
    pm_rt, _, _, _ = runH(CHGR, {(0, hm(9, 22)): (2, 0), (1, hm(9, 22)): (2, 0)}, realtime=True, htf_delay=45_000)
    check("SSS-11: the HTF switch at 9:22 arrives 45 s late -> the 9:22 events wait for it and still use red -> SELL at 9:22:00",
          pm_rt == [(hm(9, 22), "SELL")])
    LATE = [(hm(9, 23), -1), (hm(9, 25), -1), (hm(9, 40), -1)]
    pm, md, _, _ = runH(LATE, {**stS2, (0, hm(9, 23, 15)): (2, 0), (1, hm(9, 23, 30)): (2, 0)})
    check("SSS-11: no HTF band before 9:23 -> the 9:21 chain gives nothing; the 9:23 chain under red -> SELL at 9:23:30",
          pm == md == [(hm(9, 23, 30), "SELL")])
    # separate settings per pattern: A flat SELL = 15s only, B flat SELL = 15s + 30s
    def BP(k, stP, stS, ma=0, mz=0, tc=None):
        return (k, 0, 0, 100.0, stP, 1, None, None, None, None, None, None, k if tc is None else tc, stS, ma, mz)
    selAB = mk_sel({(0, 1, 0): (1, 0, 0, 0), (1, 1, 0): (1, 1, 0, 0)})
    pk = {(0, hm(9, 21)): BP(hm(9, 21), 0, -1, ma=2), (1, hm(9, 21, 30)): BP(hm(9, 21, 30), 0, -1, ma=1)}
    _, _, mk, _ = runH(FLAT, {(0, hm(9, 21)): (2, 0)}, packs=pk, sel=selAB, B=True)
    labs = list(run_new.labels)
    check("SSS-11: pattern settings are separate: 帯→フラット (flat SELL = 15s) fires at 9:21:00, フラット→帯 (15s+30s) at 9:21:30",
          labs == [(hm(9, 21), "SELL 帯→フラット"), (hm(9, 21, 30), "SELL フラット→帯＋端の線転換")])
    # data wait per column: under red, SELL (15s/30s) does not wait for late 1m data; BUY (all four) does
    T, b15, tfs = hand_case(hm(9, 20), 40, {}, {}, stS2)
    ups = pine_updates(T, b15, tfs, {2: {hm(9, 21): 150_000, hm(9, 22): 150_000}}, True, htf=RED)
    iX = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 21, 45)) + 1
    _, mk_a = run_new(ups[:iX], live=True, htf_sel=mk_sel(), patA=True)
    check("SSS-11: under red the SELL column (15s/30s) fires at 9:21:30 although the 1m data is 150 s late",
          sigmarks(mk_a) == [(hm(9, 21, 30), "SELL")])
    # ---- SSS-12: HTF segments by actual colour change, independent per segment, no 3-minute fill -----------------------
    RFR = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), 0), (hm(9, 24), -1), (hm(9, 26), -1), (hm(9, 40), -1)]
    RRR = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), -1), (hm(9, 24), -1), (hm(9, 26), -1), (hm(9, 40), -1)]
    stX = {(0, hm(9, 21, 30)): (2, 0), (1, hm(9, 24)): (2, 0)}
    pm, md, _, _ = runH(RFR, stX)
    pm2, md2, _, _ = runH(RRR, stX)
    check("SSS-12: red -> flat -> red (no events in the flat part): the 9:21:30 15s and the 9:24:00 30s are in different "
          "segments -> no SELL; with red throughout (same segment) -> SELL at 9:24:00",
          pm == md == [] and pm2 == md2 == [(hm(9, 24), "SELL")])
    # blue -> red at 9:22: red SELL (15s/30s) is processed although the 5m data used by the blue SELL column is late
    BR = [(hm(9, 18), 1), (hm(9, 20), 1), (hm(9, 22), -1), (hm(9, 24), -1), (hm(9, 40), -1)]
    T, b15, tfs = hand_case(hm(9, 20), 40, {}, {}, {(0, hm(9, 21)): (2, 0), (0, hm(9, 22)): (2, 0), (1, hm(9, 22, 30)): (2, 0)})
    ups = pine_updates(T, b15, tfs, {3: {hm(9, 20): 200_000}}, True, htf=BR)
    iX = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 22, 45)) + 1
    _, mk_a = run_new(ups[:iX], live=True, htf_sel=mk_sel(), patA=True)
    check("SSS-12: blue -> red at 9:22 (a blue 15s at 9:21 waits for the late 5m): the red segment is independent, red SELL "
          "(15s/30s) fires at 9:22:30 while the blue segment's 5m data is still missing",
          sigmarks(mk_a) == [(hm(9, 22, 30), "SELL")])
    # a late event of the old segment completes in its own segment at its original position
    selBR = mk_sel({(0, 2, 0): (1, 1, 0, 0), (0, 0, 0): (1, 1, 0, 0)})
    stY = {(0, hm(9, 21)): (2, 0), (1, hm(9, 21, 30)): (2, 0), (0, hm(9, 22)): (2, 0), (1, hm(9, 22, 30)): (2, 0)}
    pm_h, md_h, _, _ = runH(BR, stY, sel=selBR)
    pm_rt, _, _, _ = runH(BR, stY, sel=selBR, delays={1: {hm(9, 21, 30): 40_000}}, realtime=True)
    check("SSS-12: the blue 30s (9:21:30) arrives 40 s late (9:22:10) after the switch to red -> it completes in the blue segment at "
          "9:21:30, and the red chain gives 9:22:30 (= history, model)",
          pm_h == md_h == pm_rt == [(hm(9, 21, 30), "SELL"), (hm(9, 22, 30), "SELL")])
    # HTF data held for 5 minutes: no 3-minute fill; the events wait and resume in time order
    CH = [(hm(9, 18), 0), (hm(9, 20), 0), (hm(9, 22), -1), (hm(9, 24), -1), (hm(9, 40), -1)]
    stZ = {(0, hm(9, 22, 15)): (2, 0), (1, hm(9, 22, 30)): (2, 0)}
    pm_h, md_h, _, _ = runH(CH, stZ, n=48)
    T, b15, tfs = hand_case(hm(9, 20), 48, {}, {}, stZ)
    ups = pine_updates(T, b15, tfs, None, True, htf=CH, htf_delay=300_000)
    iW = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 26)) + 1
    _, mk_w = run_new(ups[:iW], live=True, htf_sel=mk_sel(), patA=True)
    env_w = run_new.env
    tsrc = pine[pine.index("//  方向 d の待機: 有効な成立順"):pine.index("var table tb = table.new")]
    exec(compile(ap.Translator().translate(ap.logical_lines(tsrc)), "table", "exec"), env_w)
    cell_wait = env_w["f_cellTxt"](0, 0)
    _, mk_r = run_new(ups, live=True, htf_sel=mk_sel(), patA=True)
    check("SSS-12: HTF data 5 min late: nothing is filled in (no SELL yet at 9:26, table '上位足データ待ち'); when it arrives the "
          "red 15s/30s chain fires at 9:22:30 (= history)",
          sigmarks(mk_w) == [] and cell_wait == "上位足データ待ち" and sigmarks(mk_r) == pm_h == md_h == [(hm(9, 22, 30), "SELL")])
    # table after a switch with no lower-timeframe events: the new segment's (empty) state is shown
    CF = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), 0), (hm(9, 24), 0), (hm(9, 40), 0)]
    T, b15, tfs = hand_case(hm(9, 20), 16, {}, {}, {(0, hm(9, 21)): (2, 0)})
    _, _ = run_new(pine_updates(T, b15, tfs, htf=CF), htf_sel=mk_sel(), patA=True)
    env_t = run_new.env
    exec(compile(ap.Translator().translate(ap.logical_lines(tsrc)), "table", "exec"), env_t)
    env_t["time"] = hm(9, 21, 45)
    env_t["time_close"] = hm(9, 22)
    in_red = env_t["f_cellTxt"](0, 0)
    env_t["time"] = hm(9, 23)
    env_t["time_close"] = hm(9, 23, 15)
    in_flat = env_t["f_cellTxt"](0, 0)
    check("SSS-12: table: in red it shows the 15s SELL waiting for 30s; after the switch to flat (no new events) it shows the "
          "flat segment's order with nothing collected yet",
          "順: 15s → 30s" in in_red and "15s 09:21:00" in in_red and "次: 30s" in in_red
          and in_flat == "順: 15s → 30s → 1m  待ち: 15s")

    # ---- SSS-13: late signals are always drawn; HTF bars counted by bar_index (missing bars = unknown band) ----------------
    def drawn(env):
        return sorted((d.args[0], d.text) for d in env["LBL"] if not d.deleted and d.kind == "label" and d.text not in ("•", "欠"))
    H10 = [(hm(9, 0), -1), (hm(9, 10), -1), (hm(9, 20), -1), (hm(9, 30), -1), (hm(9, 40), -1), (hm(9, 50), -1)]
    T, b15, tfs = hand_case(hm(9, 20), 90, {}, {}, stS2)
    _, mk = run_new(pine_updates(T, b15, tfs, htf=H10, htf_delay=20 * M), htf_sel=mk_sel(), patA=True, draw_labels=True)
    lab = drawn(run_new.env)
    check("SSS-13: HTF data 20 min late -> the SELL at 9:21:30 is registered at ~9:40 (18.5 min old) and still drawn on its bar",
          sigmarks(mk) == [(hm(9, 21, 30), "SELL")] and lab == [(hm(9, 21, 30), "SELL 帯→フラット")])
    if run_prev:
        _, mk_p = run_prev(pine_updates(T, b15, tfs, htf=H10, htf_delay=20 * M), htf_sel=mk_sel(), patA=True)
        check("SSS-13: (2207947 for comparison registers the same SELL; its drawing section drops records older than 15 min "
              "before drawing them, so that SELL never got a label)",
              sigmarks(mk_p) == [(hm(9, 21, 30), "SELL")])
    # merge: a second pattern at the same position registered on a later bar replaces the committed label with one merged label
    env = run_new.env
    env["time"] = hm(9, 41, 30)
    env["f_sigMark"](hm(9, 21, 30), 1, 1, "SELL フラット→帯＋端の線転換 (test)")
    run_new.draw(env)
    lab2 = drawn(env)
    check("SSS-13: a later フラット→帯 SELL at the same 9:21:30 deletes the committed label and draws one merged label",
          lab2 == [(hm(9, 21, 30), "SELL 帯→フラット・フラット→帯＋端の線転換")])
    # HTF bar missing (its confirmed band never arrives) -> unknown, no signal, no joining across it
    MS = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), MISS), (hm(9, 24), -1), (hm(9, 26), -1), (hm(9, 28), -1), (hm(9, 40), -1)]
    pm, md, _, _ = runH(MS, {(0, hm(9, 22, 15)): (2, 0), (1, hm(9, 22, 30)): (2, 0)}, n=48)
    check("SSS-13: the HTF bar closing 9:22 is missing -> 9:22:15 / 9:22:30 events are in an unknown band -> no SELL",
          pm == md == [])
    if run_prev:
        T, b15, tfs = hand_case(hm(9, 20), 48, {}, {}, {(0, hm(9, 22, 15)): (2, 0), (1, hm(9, 22, 30)): (2, 0)})
        ups_p = pine_updates(T, b15, tfs, htf=MS)
        _, mk_p = run_prev(ups_p, htf_sel=mk_sel(), patA=True)
        check("SSS-13: (2207947 carried the 9:20 red band into the missing bar's interval and gave a SELL)",
              sigmarks(mk_p) == [(hm(9, 22, 30), "SELL")])
    pm, md, _, _ = runH(MS, {(0, hm(9, 21, 30)): (2, 0), (1, hm(9, 24, 30)): (2, 0)}, n=48)
    pm2, md2, _, _ = runH(RRR, {(0, hm(9, 21, 30)): (2, 0), (1, hm(9, 24, 30)): (2, 0)}, n=48)
    check("SSS-13: red before and after the missing bar: 15s 9:21:30 and 30s 9:24:30 are not joined (no SELL); "
          "without the gap (red throughout) -> SELL at 9:24:30", pm == md == [] and pm2 == md2 == [(hm(9, 24, 30), "SELL")])
    # market-closed time gap with consecutive bar indices is not a gap
    WK = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 40), -1), (hm(9, 42), -1), (hm(9, 50), -1)]
    pm, md, _, _ = runH(WK, stS2)
    check("SSS-13: HTF time jumps 9:20 -> 9:40 with consecutive bar indices -> band known -> SELL at 9:21:30",
          pm == md == [(hm(9, 21, 30), "SELL")])
    # a bar whose [1] is lost but arrives later as [2]: the events wait, then are processed in time order (= history)
    LT = [(hm(9, 18), -1), (hm(9, 20), -1), (hm(9, 22), ("LATE", -1)), (hm(9, 24), -1), (hm(9, 26), -1), (hm(9, 40), -1)]
    stL = {(0, hm(9, 22, 15)): (2, 0), (1, hm(9, 22, 30)): (2, 0)}
    T, b15, tfs = hand_case(hm(9, 20), 48, {}, {}, stL)
    ups = pine_updates(T, b15, tfs, None, True, htf=LT)
    i23 = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 23, 45)) + 1
    _, mk_w = run_new(ups[:i23], live=True, htf_sel=mk_sel(), patA=True)
    _, mk_r = run_new(ups, live=True, htf_sel=mk_sel(), patA=True)
    pm_h, md_h, _, _ = runH(LT, stL, n=48)
    check("SSS-13: the 9:22 HTF bar's [1] is lost; until its [2] arrives (9:24) the 9:22:15 / 9:22:30 events wait (no SELL at "
          "9:23:45), then SELL at 9:22:30 (= history, model)",
          sigmarks(mk_w) == [] and sigmarks(mk_r) == pm_h == md_h == [(hm(9, 22, 30), "SELL")])
    # the segment after a missing bar proceeds on its own while the missing bar's events are still pending
    stN = {(0, hm(9, 22, 15)): (2, 0), (0, hm(9, 24, 15)): (2, 0), (1, hm(9, 24, 30)): (2, 0)}
    T, b15, tfs = hand_case(hm(9, 20), 48, {}, {}, stN)
    ups = pine_updates(T, b15, tfs, None, True, htf=MS)
    i24 = next(n for n, u in enumerate(ups) if u["t"] == hm(9, 24, 45)) + 1
    _, mk_a = run_new(ups[:i24], live=True, htf_sel=mk_sel(), patA=True)
    check("SSS-13: after the missing 9:22 bar, the 9:24 segment (red known) fires at 9:24:30 while the gap's events still wait",
          sigmarks(mk_a) == [(hm(9, 24, 30), "SELL")])

    # random: random HTF bands, both patterns, Pine == models; realtime with delays (incl. the HTF switch) == history
    agreeH = rtH = nH = 0
    for seed in (515, 522, 526, 503):
        rng7 = random.Random(seed)
        b15 = regime_bars(rng7, 1200, vol=rng7.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = series_tfs(T, b15)
        per = rng7.choice([3, 4, 7]) * M
        htf = [(T[0] - T[0] % per + k * per, rng7.choice([-1, 0, 1, 1, -1, None if k % 9 == 4 else 0])) for k in range(len(T) * S15 // per + 3)]
        htf = [(tc, MISS if k % 11 == 6 else ("LATE", bb) if k % 7 == 3 and bb is not None else bb) for k, (tc, bb) in enumerate(htf)]
        sel = [rng7.random() < 0.6 for _ in range(48)]
        _, mk = run_new(pine_updates(T, b15, tfs, htf=htf), htf_sel=sel, patA=True, patB=True, useB=(True, True, True, True))
        md = [(x, d) for (x, d, _) in mid_model(T, b15, tfs, htf=htf, sel=sel)[0]]
        useU = tuple(any(sel[((1 * 3 + bi) * 2 + dd) * 4 + i] for bi in range(3) for dd in range(2)) for i in range(4))
        md += [(x, d) for (x, d, _) in model_b(tfs, useU, htf=htf, sel=sel)[0]]
        nH += len(md)
        agreeH += sigmarks(mk) == sorted(set(md))
        if seed in (515, 526):
            dl = {1: {k: rng7.randint(0, 40_000) for k in tfs[1][0]}, 2: {k: rng7.randint(0, 40_000) for k in tfs[2][0]},
                  3: {k: rng7.randint(0, 120_000) for k in tfs[3][0]}}
            _, mk_rt = run_new(pine_updates(T, b15, tfs, dl, True, htf=htf, htf_delay=50_000), live=True, htf_sel=sel,
                               patA=True, patB=True, useB=(True, True, True, True))
            rtH += sigmarks(mk_rt) == sigmarks(mk)
    print(f"   SSS-11 random (HTF bands, both patterns): signals {nH}")
    check("SSS-11 random: translated Pine == models with random HTF bands and random columns (4 series)", agreeH == 4)
    check("SSS-11 random: realtime with 30s/1m/5m delays and a 50 s late HTF switch == history (2 runs)", rtH == 2)

    # ---- 7. SSS-5 random: translated Pine (history / realtime with delays) vs the independent model -------------------------
    agree = rt_agree = n_mid = n_sig = n_mid_sig = n_clr_diff = 0
    seeds = [500, 503, 515, 520, 522, 526, 554]   # 515 / 520 / 522 / 526 / 554 contain signals ending on a mid-bar 1m STB
    runs = len(seeds)
    for trial, seed in enumerate(seeds):
        rng4 = random.Random(seed)
        b15 = regime_bars(rng4, 1200, vol=rng4.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = series_tfs(T, b15)
        _, mk = run_new(pine_updates(T, b15, tfs))
        msig, mev = mid_model(T, b15, tfs)
        n_mid += sum(1 for e in mev if e[2] == 0 and (e[3] or e[4]))
        n_sig += len(msig)
        n_mid_sig += sum(1 for x in msig if x[0] % M != 0)
        agree += sigmarks(mk) == sorted((x, d) for (x, d, _) in msig)
        msig_off, _ = mid_model(T, b15, tfs, clr=(False, False, False))
        n_clr_diff += len(set((x, d) for (x, d, _) in msig) ^ set((x, d) for (x, d, _) in msig_off))
        if trial in (0, 2, 4):
            dl = {1: {k: rng4.randint(0, 40_000) for k in tfs[1][0]}, 2: {k: rng4.randint(0, 40_000) for k in tfs[2][0]}}
            _, mk_rt = run_new(pine_updates(T, b15, tfs, dl, realtime=True), live=True)
            rt_agree += sigmarks(mk_rt) == sigmarks(mk)
    print(f"   SSS-5 random: mid-bar STB events={n_mid}  signals={n_sig} (ending on a mid-bar 1m STB: {n_mid_sig})"
          f"  signals changed by the band-return clears: {n_clr_diff}")
    check(f"SSS-5 random: translated Pine (history) marks == independent model ({runs} runs)", agree == runs)
    check("SSS-5 random: realtime with delays <= 40 s gives the history marks (3 runs)", rt_agree == 3)
    check("SSS-5 random: mid-bar STB events occur and some signals end on a mid-bar 1m STB", n_mid > 0 and n_mid_sig > 0)
    agree9 = rt9 = 0
    cnt9 = {}
    for seed in (515, 520, 522, 526):
        rng5 = random.Random(seed)
        b15 = regime_bars(rng5, 1200, vol=rng5.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = series_tfs(T, b15)
        for use in ((True, True, False, False), (False, True, True, False), (True, True, True, True), (True, False, False, False)):
            _, mk = run_new(pine_updates(T, b15, tfs), use=use)
            sig, _ = mid_model(T, b15, tfs, use=use)
            cnt9[use] = cnt9.get(use, 0) + len(sig)
            agree9 += sigmarks(mk) == sorted((x, d) for (x, d, _) in sig)
        dl = {1: {k: rng5.randint(0, 40_000) for k in tfs[1][0]}, 2: {k: rng5.randint(0, 40_000) for k in tfs[2][0]},
              3: {k: rng5.randint(0, 120_000) for k in tfs[3][0]}}
        _, mk_rt = run_new(pine_updates(T, b15, tfs, dl, realtime=True), live=True, use=(True, True, True, True))
        _, mk_h = run_new(pine_updates(T, b15, tfs), use=(True, True, True, True))
        rt9 += sigmarks(mk_rt) == sigmarks(mk_h)
    print(f"   SSS-9 random signals per selection: { {''.join('1' if u else '0' for u in k): v for k, v in cnt9.items()} }")
    agreeB = rtB = nB = 0
    for seed in (515, 520, 522, 526, 500, 503):
        rng6 = random.Random(seed)
        b15 = regime_bars(rng6, 1200, vol=rng6.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = series_tfs(T, b15)
        for useB in ((True, True, True, False), (True, False, False, False), (True, True, False, False)):
            _, mk = run_new(pine_updates(T, b15, tfs), use=(False, False, False, False), useB=useB)
            sigB, _ = model_b(tfs, useB)
            nB += len(sigB)
            agreeB += sigmarks(mk) == sorted((x, d) for (x, d, _) in sigB)
        if seed in (515, 522):
            dl = {1: {k: rng6.randint(0, 40_000) for k in tfs[1][0]}, 2: {k: rng6.randint(0, 40_000) for k in tfs[2][0]},
                  3: {k: rng6.randint(0, 120_000) for k in tfs[3][0]}}
            _, mk_rt = run_new(pine_updates(T, b15, tfs, dl, realtime=True), live=True, useB=(True, True, True, True))
            _, mk_h = run_new(pine_updates(T, b15, tfs), useB=(True, True, True, True))
            rtB += sigmarks(mk_rt) == sigmarks(mk_h)
    print(f"   SSS-10 random フラット→帯 signals (3 selections x 6 series): {nB}")
    check("SSS-10 random: translated Pine == model_b (3 selections x 6 series)", agreeB == 18)
    check("SSS-10 random: both patterns ON (B all four), realtime with delays == history (2 runs)", rtB == 2)
    check("SSS-9 random: translated Pine == model for 4 selections x 4 series", agree9 == 16)
    check("SSS-9 random: all four ON, realtime with 30s/1m delays <= 40 s and 5m delays <= 2 min == history (4 runs)", rt9 == 4)

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
            ok = (max(a, b_, c) - min(a, b_, c) <= 5 * M and anc == max(a, b_, c) and det >= anc
                  and (15, a, k) in ev and (30, b_, k) in ev and (60, c, k) in ev)
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
    check("random end-to-end: every signal is one same-direction event per timeframe within 5 min, marked at the latest", bad == 0)
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
