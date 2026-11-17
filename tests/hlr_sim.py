"""HLR-1 checks — HorizontalLineReactionStatsXAU.pine.   python3 tests/hlr_sim.py [random-seeds]

Runs the "HLR Logic" section of the indicator itself (mechanical Pine-subset -> Python translation by tests/acc_pine.py,
unchanged) on synthetic confirmed 5m bars with the higher-TF pivot outputs given per bar as request.security would deliver them.

  A. acceptance cases of the instruction (section 7), each also mirrored (from below) around the line
  B. invariants: N = rebound + break + ambiguous + pending per row, the 3 targets share N, re-run / reload identical,
     unconfirmed last bar ignored, display / record limits do not change the counters
  C. random paths vs an independent brute-force oracle (scans every line on every bar, its own per-target state machine)
  D. registration cross-check against ZoneComboLabXAU.pine (0fec933) itself: same feeds -> its ZC members (mTf, mP, mT, mId)
     and the bar each member appeared on == this indicator's lines (tf, side, key, price, registration 5m bar)
  E. static: no strategy / alert / order calls, the copied pivot function == the Lab's byte for byte

Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / replay here).
"""
import copy
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "HorizontalLineReactionStatsXAU.pine")
LAB = os.path.join(ROOT, "ZoneComboLabXAU.pine")
BEGIN, END = "// ==== HLR Logic (begin) ", "// ==== HLR Logic (end) "
M5 = 300_000
T0 = 1_767_574_800_000          # 2026-01-05 01:00 UTC
MT = 0.01
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def src():
    return open(PINE, encoding="utf-8").read()


def logic(s):
    i = s.index(BEGIN)
    return s[s.index("\n", i) + 1:s.index(END)]


FEEDS = [f"p{k}{x}" for k in (1, 2, 3, 4) for x in ("h", "ht", "l", "lt")]


class Runner:
    """bars: dicts t, o, h, l, c (+ conf False = an unconfirmed realtime update) and pivot feeds p{k}h / p{k}ht / p{k}l / p{k}lt."""

    def __init__(self, overrides=None, source=None, run=True, rollback=False):
        s = source if source is not None else src()
        self.code = compile(ap.Translator().translate(ap.logical_lines(logic(s))), "<HLR logic>", "exec")
        inp = ap.inputs(s)
        for k in (overrides or {}):
            if k not in inp:
                raise KeyError(k)
        inp.update(overrides or {})
        env = ap.make_env(ap.Broker(), [])

        def _insert(arr, i, v):
            if i is None or i < 0 or i > len(arr):
                raise ap.PineRuntimeError("array.insert out of bounds")
            arr.insert(i, v)
        env.update(inp)
        env.update(array__new=lambda n=0, v=None: [v] * n, array__insert=_insert, math__ceil=math.ceil,
                   syminfo__mintick=MT, hlRun=run, _VARS=set(), _VARIPS=set(), __first__=True)
        self.env = env
        self.bar_index = -1
        self.committed = None
        self.rollback = rollback          # keep a committed copy of the var state (needed only for unconfirmed updates)

    def step(self, b):
        conf = b.get("conf", True)
        if self.rollback and self.committed is not None:
            self.env.update(copy.deepcopy(self.committed))
        idx = self.bar_index + 1          # an unconfirmed update is the next bar, not committed
        if conf:
            self.bar_index = idx
        e = self.env
        e.update(open=b["o"], high=b["h"], low=b["l"], close=b["c"], time=b["t"], bar_index=idx,
                 barstate__isconfirmed=conf)
        for f in FEEDS:
            e[f] = b.get(f)
        exec(self.code, e)
        e["__first__"] = False
        if conf and self.rollback:
            self.committed = copy.deepcopy({k: e[k] for k in e["_VARS"]})
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

    def counters(self):
        e = self.env
        return {k: list(e[k]) for k in ("hcN", "hcR", "hcB", "hcA", "hcF", "hcS", "hxLo", "hxHi", "hlUnk", "hlNLine")}

    def recs(self):
        return [(r.pf, r.tf, r.dr, r.cTime, r.j, r.res, r.exL, r.exH) for r in self.env["hlRec"]]


# ----------------------------------------------------------------------------------------------------------------
def bar(i, o, h, l, c, **kv):
    assert l <= min(o, c) and h >= max(o, c), (i, o, h, l, c)
    d = dict(t=T0 + i * M5, o=o, h=h, l=l, c=c)
    d.update(kv)
    return d


def line_feed(tf, side, price, key):
    k = tf + 1
    return {f"p{k}{'h' if side == 1 else 'l'}": price, f"p{k}{'ht' if side == 1 else 'lt'}": key}


def mirror_bars(bars, axis=4300.0):
    out = []
    for b in bars:
        m = dict(b)
        m.update(o=round(2 * axis - b["o"], 2), h=round(2 * axis - b["l"], 2), l=round(2 * axis - b["h"], 2), c=round(2 * axis - b["c"], 2))
        for k in (1, 2, 3, 4):
            if b.get(f"p{k}h") is not None or b.get(f"p{k}l") is not None:
                m[f"p{k}h"], m[f"p{k}ht"] = (None if b.get(f"p{k}l") is None else round(2 * axis - b[f"p{k}l"], 2)), b.get(f"p{k}lt")
                m[f"p{k}l"], m[f"p{k}lt"] = (None if b.get(f"p{k}h") is None else round(2 * axis - b[f"p{k}h"], 2)), b.get(f"p{k}ht")
        out.append(m)
    return out


KEY = T0 - 86_400_000


def scenario(rows, tf=2, side=1, price=4300.0):
    """bar 0 registers the line (far above it), rows = (o, h, l, c) of bars 1.."""
    bars = [bar(0, 4330, 4332, 4328, 4330, **line_feed(tf, side, price, KEY))]
    for n, r in enumerate(rows, start=1):
        bars.append(bar(n, *r))
    return bars


def results(r):
    """{(dr, target $): (result, exL$, exH$)} of the decided records, plus pending flags"""
    out = {}
    for pf, tf, dr, ct, j, res, lo, hi in r.recs():
        out.setdefault((dr, (5, 10, 20)[j]), []).append((res, None if lo is None else round(lo * MT, 2), None if hi is None else round(hi * MT, 2)))
    return out


R, B, A = 1, 2, 3


def both_ways(name, rows, expect, pend=(), flags=(), n_contacts=1):
    """expect: {target: (res, lo, hi)} for the first observation; pend: targets still pending; flags: pending with the flag"""
    for dr, bars in ((1, scenario(rows)), (-1, mirror_bars(scenario(rows)))):
        r = Runner().run(bars)
        got = results(r)
        ok = True
        det = []
        for tgt, exp in expect.items():
            g = got.get((dr, tgt), [None])[0]
            if g != exp:
                ok = False
                det.append(f"${tgt}: got {g} want {exp}")
        pobs = [o for o in r["hlPend"]]
        for tgt in pend:
            j = (5, 10, 20).index(tgt)
            if not pobs or pobs[0].st[j] != 0:
                ok = False
                det.append(f"${tgt} not pending")
        for tgt in flags:
            j = (5, 10, 20).index(tgt)
            if not pobs or not pobs[0].fl[j]:
                ok = False
                det.append(f"${tgt} flag missing")
        n = r["hcN"][12 if dr == 1 else 15]
        if n != n_contacts:
            ok = False
            det.append(f"N={n}")
        check(f"A {name} ({'上から' if dr == 1 else '下から'})", ok, "; ".join(det) + f" | got {got}")


def acceptance():
    # 1: contact low 4297, next bar reaches 4310 with low 4299 -> $10 rebound, overshoot $3 (single); $20 pending
    both_ways("1 $10 反発・行き過ぎ $3", [(4304, 4304.5, 4297, 4302), (4302, 4310, 4299, 4309)],
              {5: (R, 3.0, 3.0), 10: (R, 3.0, 3.0)}, pend=(20,))
    # 2: $5 rebound, then before $10 the low is exactly 4295 -> $10 / $20 break
    both_ways("2 $5 反発後に安値ちょうど 4295", [(4302, 4303, 4299, 4301), (4301, 4306, 4300.5, 4305), (4304, 4305, 4295, 4296)],
              {5: (R, 1.0, 1.0), 10: (B, None, None), 20: (B, None, None)}, n_contacts=2)   # bar 3 is also a re-contact
    # 3: contact bar o 4312 h 4313 l 4299 c 4301 -> $10 not decided on the bar (flag); later
    both_ways("3a 可能性フラグのまま追跡", [(4312, 4313, 4299, 4301)], {}, pend=(5, 10, 20), flags=(5, 10))
    both_ways("3b フラグ後に確実な反発", [(4312, 4313, 4299, 4301), (4301, 4311, 4300, 4310)],
              {5: (R, 0.0, 1.0), 10: (R, 0.0, 1.0)}, pend=(20,))
    both_ways("3c フラグ後に先に突破", [(4312, 4313, 4299, 4301), (4301, 4302, 4295, 4296)],
              {5: (A, None, None), 10: (A, None, None), 20: (B, None, None)})
    # 4: contact bar o 4312 h 4313 l 4295 c 4301 -> $10 ambiguous, $20 break
    both_ways("4 接触足で両側", [(4312, 4313, 4295, 4301)], {5: (A, None, None), 10: (A, None, None), 20: (B, None, None)})
    # 5: already contacted; next bar o 4308 h 4311 l 4295 -> $10 ambiguous; with o 4310 -> $10 rebound
    both_ways("5a 次足 始値 4308", [(4302, 4304, 4299, 4303), (4308, 4311, 4295, 4300)],
              {5: (R, 1.0, 1.0), 10: (A, None, None), 20: (B, None, None)})
    both_ways("5b 次足 始値 4310", [(4302, 4304, 4299, 4303), (4310, 4311, 4295, 4300)],
              {5: (R, 1.0, 1.0), 10: (R, 1.0, 1.0), 20: (B, None, None)})
    # 6: known overshoot $1, $10 bar o 4303 h 4310 l 4297 -> $10 rebound, overshoot $1-$3
    both_ways("6 行き過ぎ $1～$3", [(4302, 4304, 4299, 4303), (4303, 4310, 4297, 4309)],
              {5: (R, 1.0, 3.0), 10: (R, 1.0, 3.0)}, pend=(20,))
    # 7: wick contacts in a row count once; 'close away' and 'wick equal' bars do not re-arm; low > 4300 re-arms
    rows7 = [(4302, 4303, 4299, 4301),        # contact 1
             (4301, 4302, 4300, 4301.5),      # wick equal (low == P): no re-arm, no count
             (4301.5, 4304, 4299.5, 4303),    # touches again: no count
             (4303, 4304, 4300.01, 4303.5),   # fully above: re-arm
             (4303.5, 4304, 4299, 4302)]      # contact 2
    for dr, bars in ((1, scenario(rows7)), (-1, mirror_bars(scenario(rows7)))):
        r = Runner().run(bars)
        ix = (2 * 2 + (0 if dr == 1 else 1)) * 3
        ids = sorted(o.id for o in r["hlPend"])
        p20 = [o for o in r["hlPend"] if o.st[2] == 0]
        check(f"A 7 再接触 ({dr})", r["hcN"][ix] == 2 and len(ids) == 2 and ids[0] != ids[1] and len(p20) == 2, f"N={r['hcN'][ix]} pend={ids}")
    rows7b = [(4302, 4303, 4299, 4301), (4301, 4304, 4299.5, 4304), (4304, 4305, 4299, 4302)]   # close away only: no re-arm
    r = Runner().run(scenario(rows7b))
    check("A 7b 終値だけ離れた足では再開しない", r["hcN"][12] == 1, f"N={r['hcN'][12]}")
    # 7c: the earlier observation breaks on the re-contact bar and the new one starts on the same bar
    rows7c = [(4302, 4303, 4299, 4301), (4301, 4306, 4300.5, 4305), (4301, 4302, 4295, 4296)]
    r = Runner().run(scenario(rows7c))
    rr = results(r)
    check("A 7c 再接触足で前回分が突破・今回分が開始", r["hcN"][12] == 2 and rr.get((1, 10)) == [(B, None, None), (B, None, None)]
          and rr.get((1, 5)) == [(R, 1.0, 1.0), (B, None, None)], str(rr))
    # 8: registration bar touches (excluded); the next bar counts; same price from another TF / another pivot key = separate lines;
    #    the same event received on several bars registers once
    k2 = KEY + 3_600_000
    bars8 = [bar(0, 4301, 4302, 4299, 4301, **line_feed(2, 1, 4300.0, KEY), **line_feed(0, -1, 4300.0, KEY)),
             bar(1, 4301, 4302, 4299, 4301, **line_feed(2, 1, 4300.0, KEY), **line_feed(1, 1, 4300.0, k2)),    # repeat D, new 4H
             bar(2, 4301, 4302, 4299.5, 4301.5, **line_feed(2, 1, 4300.0, KEY), **line_feed(3, -1, 4300.0, KEY)),
             bar(3, 4301.5, 4303, 4300.5, 4302),          # away
             bar(4, 4302, 4303, 4299, 4302.5, **line_feed(2, 1, 4300.0, KEY + 7))]   # new D key, same price
    r = Runner().run(bars8)
    lines = [(l.tf, l.sub, l.key, l.regBar) for l in r["hlAll"]]
    nD, n1, n4, nW = r["hcN"][12], r["hcN"][0], r["hcN"][6], r["hcN"][18]
    check("A 8 登録足は対象外・次足から個別・同一イベントは 1 本", lines == [(0, -1, KEY, 0), (2, 1, KEY, 0), (1, 1, k2, 1), (3, -1, KEY, 2), (2, 1, KEY + 7, 4)]
          and (nD, n1, n4, nW) == (2, 2, 2, 1), f"lines={lines} N D/1H/4H/W={nD, n1, n4, nW}")
    # 9: gap over the line is not a contact; the bar after the gap touching from below = 1 contact (from below)
    bars9 = scenario([(4304, 4305, 4301, 4303), (4298.5, 4299, 4297, 4298), (4298, 4300, 4297.5, 4299)])
    r = Runner().run(bars9)
    check("A 9 ギャップは接触にしない", r["hcN"][12] == 0 and r["hcN"][15] == 1, f"above={r['hcN'][12]} below={r['hcN'][15]}")
    # open == P: side of the previous close; both on the line / no previous close -> direction unknown
    r = Runner().run([bar(0, 4302, 4302, 4300, 4300, **line_feed(2, 1, 4300.0, KEY)), bar(1, 4300, 4301, 4299, 4300.5)])
    check("A 始値 = 線 は前足終値の側 (前足終値 = 線 → 方向不明)", r["hcN"][12] == 0 and r["hcN"][15] == 0 and r["hlUnk"][2] == 1,
          f"{r['hcN'][12]} {r['hcN'][15]} unk={r['hlUnk']}")
    r = Runner().run(scenario([(4303, 4304, 4301, 4302), (4300, 4306, 4299, 4305)]))
    check("A 始値 = 線・前足終値が上 → 上から、始値から観測 ($5 反発)", r["hcN"][12] == 1 and results(r).get((1, 5)) == [(R, 0.0, 1.0)], str(results(r)))
    # thresholds with ticks: B = 5.003 needs 5.01 ($4294.99), 4295.00 is not a break
    r = Runner({"hlBreak": 5.003}).run(scenario([(4302, 4303, 4295, 4296)]))
    r2 = Runner({"hlBreak": 5.003}).run(scenario([(4302, 4303, 4294.99, 4296)]))
    check("A 刻みに乗らない突破幅は次のティックから", r["hcB"][14] == 0 and r2["hcB"][14] == 1, f"{r['hcB'][14]} {r2['hcB'][14]}")


# ----------------------------------------------------------------------------------------------------------------
# C. independent oracle: every line on every bar, per-target classification written from the spec without ticks-index tricks
def oracle(bars, B=5.0, use=(True, True, True, True)):
    tk = lambda x: int(round(x / MT))   # noqa: E731
    Bt = math.ceil(B / MT - 1e-6)
    D = [500, 1000, 2000]
    lines, obs, last = [], [], {}
    cnt = {}
    unk = [0] * 4
    prev = None
    for i, b in enumerate(bars):
        o, h, l, c = tk(b["o"]), tk(b["h"]), tk(b["l"]), tk(b["c"])
        for ob in obs:
            if ob["done"]:
                continue
            s = ob["dr"]
            on, hn, ln = (o - ob["p"], h - ob["p"], l - ob["p"]) if s == 1 else (ob["p"] - o, ob["p"] - l, ob["p"] - h)
            for j in range(3):
                if ob["res"][j] is not None:
                    continue
                f = ob["flag"][j]
                if on >= D[j]:
                    ob["res"][j] = (1, 0 if f else ob["M"], ob["M"])
                elif on <= -Bt:
                    ob["res"][j] = (3 if f else 2,)
                elif hn >= D[j] and ln <= -Bt:
                    ob["res"][j] = (3,)
                elif hn >= D[j]:
                    lo = max(ob["M"], max(0, -on))
                    ob["res"][j] = (1, 0 if f else lo, max(lo, -ln))
                elif ln <= -Bt:
                    ob["res"][j] = (3 if f else 2,)
            ob["M"] = max(ob["M"], -ln)
            ob["done"] = all(x is not None for x in ob["res"])
        for L in lines:
            P = L["p"]
            if not (l <= P <= h) or L["reg"] >= i:
                continue
            if L["reg"] != i - 1 and prev[2] <= P <= prev[1]:
                continue
            s = 1 if o > P else -1 if o < P else (0 if prev is None else 1 if prev[3] > P else -1 if prev[3] < P else 0)
            if s == 0:
                unk[L["tf"]] += 1
                continue
            on, hn, ln, cn = (o - P, h - P, l - P, c - P) if s == 1 else (P - o, P - l, P - h, P - c)
            ob = dict(p=P, dr=s, tf=L["tf"], res=[None] * 3, flag=[False] * 3, M=0, done=False, t=b["t"], line=L["id"])
            for j in range(3):
                rr, bb = hn >= D[j], ln <= -Bt
                if rr and bb:
                    ob["res"][j] = (3,)
                elif bb:
                    ob["res"][j] = (2,)
                elif rr and (on == 0 or cn >= D[j]):
                    ob["res"][j] = (1, 0, max(0, -ln))
                elif rr:
                    ob["flag"][j] = True
            ob["M"] = max(0, -ln)
            ob["done"] = all(x is not None for x in ob["res"])
            obs.append(ob)
        for k in range(4):
            if not use[k]:
                continue
            for sd, (pk, tkk) in enumerate(((f"p{k + 1}h", f"p{k + 1}ht"), (f"p{k + 1}l", f"p{k + 1}lt"))):
                pv, pt = b.get(pk), b.get(tkk)
                if pv is not None and pt is not None and last.get((k, sd)) != pt:
                    last[(k, sd)] = pt
                    lines.append(dict(id=len(lines) + 1, p=tk(pv), tf=k, sub=1 if sd == 0 else -1, key=pt, reg=i))
        prev = (o, h, l, c)
    # aggregate like the indicator
    agg = dict(N=[0] * 24, R=[0] * 24, B=[0] * 24, A=[0] * 24, F=[0] * 24, S=[0] * 24, Lo=[-1] * 24, Hi=[-1] * 24)
    for ob in obs:
        for j in range(3):
            ix = (ob["tf"] * 2 + (0 if ob["dr"] == 1 else 1)) * 3 + j
            agg["N"][ix] += 1
            r = ob["res"][j]
            if r is None:
                agg["F"][ix] += 1 if ob["flag"][j] else 0
            elif r[0] == 1:
                agg["R"][ix] += 1
                agg["Lo"][ix] = max(agg["Lo"][ix], r[1])
                agg["Hi"][ix] = max(agg["Hi"][ix], r[2])
                agg["S"][ix] += 1 if r[1] == r[2] else 0
            elif r[0] == 2:
                agg["B"][ix] += 1
            else:
                agg["A"][ix] += 1
    return agg, unk, lines, obs


def htf_feeds(rows, blocks=(12, 48, 276, 1380), lens=(6, 6, 6, 6), offset=0):
    """per 5m bar the values request.security(tf, f_lbPivotConfirmed(len), lookahead_on) delivers: pivot of HTF bar n is
    confirmed at bar n + len and delivered during HTF bar n + len + 1 with key = start time of bar n + len"""
    n = len(rows)
    feeds = [dict() for _ in range(n)]
    for k, (L, ln) in enumerate(zip(blocks, lens)):
        hb = [(max(r[1] for r in rows[s:s + L]), min(r[2] for r in rows[s:s + L])) for s in range(0, n - L + 1, L)]
        for m in range(2 * ln, len(hb)):
            c = m - ln
            win = hb[c - ln:m + 1]
            dh = hb[c][0] if hb[c][0] == max(x[0] for x in win) and all(x[0] < hb[c][0] for x in hb[c + 1:m + 1]) else None
            dl = hb[c][1] if hb[c][1] == min(x[1] for x in win) and all(x[1] > hb[c][1] for x in hb[c + 1:m + 1]) else None
            key = T0 + offset + m * L * M5
            for i in range((m + 1) * L, min((m + 2) * L, n)):
                if dh is not None:
                    feeds[i][f"p{k + 1}h"], feeds[i][f"p{k + 1}ht"] = dh, key
                if dl is not None:
                    feeds[i][f"p{k + 1}l"], feeds[i][f"p{k + 1}lt"] = dl, key
    return feeds


def random_bars(seed, n, step=0.01, vol=1.6, gaps=True):
    rnd = random.Random(seed)
    p = 4300.0
    rows = []
    for i in range(n):
        o = p + (rnd.choice([0, 0, 0, 0, 1, -1]) * rnd.uniform(0, 6) if gaps and rnd.random() < 0.08 else 0)
        o = round(round(o / step) * step, 2)
        c = round(round((o + rnd.gauss(0, vol)) / step) * step, 2)
        h = round(round((max(o, c) + abs(rnd.gauss(0, vol * 0.7))) / step) * step, 2)
        lo = round(round((min(o, c) - abs(rnd.gauss(0, vol * 0.7))) / step) * step, 2)
        if rnd.random() < 0.05:      # exact touches / equal opens on round numbers
            o = round(o)
        h, lo = max(h, o, c), min(lo, o, c)
        rows.append((o, h, lo, c))
        p = c
    return rows


def random_vs_oracle(seeds):
    big = src().replace("int HL_REC_KEEP = 40", "int HL_REC_KEEP = 1000000")
    for seed in seeds:
        rows = random_bars(seed, 3000, step=1.0 if seed % 3 == 0 else 0.01)
        feeds = htf_feeds(rows, blocks=(12, 48, 120, 360), lens=(2, 2, 2, 2) if seed % 2 else (6, 3, 2, 1))
        # extra lines: duplicated prices with different keys / TFs, round numbers hit by equal opens
        for i in range(50, 3000, 97):
            p = round(rows[i][3])
            feeds[i].update({"p1h": float(p), "p1ht": T0 + i, "p3l": float(p), "p3lt": T0 + i})
        bars = [bar(i, *rows[i], **feeds[i]) for i in range(len(rows))]
        B = (5.0, 3.0, 7.5)[seed % 3]
        r = Runner({"hlBreak": B}, source=big).run(bars)
        agg, unk, lines, obs = oracle(bars, B)
        c = r.counters()
        mine = dict(N=c["hcN"], R=c["hcR"], B=c["hcB"], A=c["hcA"], F=c["hcF"], S=c["hcS"], Lo=c["hxLo"], Hi=c["hxHi"])
        same = mine == agg and c["hlUnk"] == unk and len(r["hlAll"]) == len(lines)
        # per observation: every decided (line, contact time, target) of the oracle == the indicator's records
        orec = sorted((ob["t"], ob["p"], ob["dr"], j, ob["res"][j]) for ob in obs for j in range(3) if ob["res"][j] is not None)
        irec = sorted((x.cTime, int(round(x.pf / MT)), x.dr, x.j, (x.res,) if x.res != 1 else (1, x.exL, x.exH)) for x in r["hlRec"])
        nN = sum(agg["N"]) // 3
        nonzero = sum(1 for x in agg["R"] if x) + sum(1 for x in agg["B"] if x)
        check(f"C random seed {seed} (B={B}) == oracle", same and orec == irec and nN > 50 and nonzero > 4,
              f"contacts={nN} lines={len(lines)} unk={sum(unk)} pending={len(r['hlPend'])} recs={len(irec)} diff_keys="
              f"{[k for k in agg if agg[k] != mine[k]]}")
        # sum rule per row
        pend_ok = all(c["hcN"][x] - c["hcR"][x] - c["hcB"][x] - c["hcA"][x] >= c["hcF"][x] >= 0 for x in range(24))
        same_n = all(c["hcN"][g * 3] == c["hcN"][g * 3 + 1] == c["hcN"][g * 3 + 2] for g in range(8))
        live = sum(3 - o.left for o in r["hlPend"]) + sum(c["hcR"]) + sum(c["hcB"]) + sum(c["hcA"])
        check(f"B seed {seed}: N = 反発 + 突破 + 順序不明 + 未決着、3 目標の N 一致、追跡中は未確定だけ",
              pend_ok and same_n and all(o.left > 0 for o in r["hlPend"]), f"decided={live}")
    return bars


def invariants(bars):
    a = Runner().run(bars).counters()
    b = Runner().run(bars).counters()
    check("B 再読み込み (同じ確定足を再実行) で集計一致", a == b)
    # unconfirmed last bar (realtime updates) changes nothing; the confirmed version is processed once
    base = Runner(rollback=True).run(bars[:-1])
    c0 = base.counters()
    rt = copy.deepcopy(bars[-1])
    upd = dict(rt, conf=False, h=rt["h"] + 30, l=rt["l"] - 30, c=rt["c"])
    base.step(upd)
    check("B 未確定の最後の足は集計しない", base.counters() == c0)
    # display / record limits do not change the counters
    s = src()
    small = Runner({"hlRecN": 0, "hlDrawMax": 1, "hlDraw": False}, source=s.replace("int HL_REC_KEEP = 40", "int HL_REC_KEEP = 1")).run(bars).counters()
    check("B 表示件数・描画上限・記録件数を変えても集計一致", small == a)
    # timeframe OFF: those lines are not registered, the others unchanged
    off = Runner({"hlUse1": False}).run(bars).counters()
    check("B 1H OFF は 1H の線だけ除く", off["hlNLine"][0] == 0 and off["hlNLine"][1:] == a["hlNLine"][1:]
          and off["hcN"][6:] == a["hcN"][6:] and sum(off["hcN"][:6]) == 0)
    # non-target chart: nothing is counted
    nr = Runner(run=False).run(bars).counters()
    check("B 対象外のチャートでは集計しない", sum(nr["hcN"]) == 0 and sum(nr["hlNLine"]) == 0)


# ----------------------------------------------------------------------------------------------------------------
def lab_crosscheck(n=3000):
    """ZoneComboLabXAU.pine (0fec933) own ZC registration, executed: its (B1) ZC block (from "// ZC: 新しい Pivot" to the f_swAdd
    call) and its lbPivLastH / lbPivLastL declarations are cut from the Lab source and run through the same translator, with the same
    pivot feeds as s{k}h / s{k}ht / s{k}l / s{k}lt. f_swAdd is replaced by a recorder of its arguments (k, sub, pv, pt) and the bar;
    statically, the Lab's f_swAdd stores exactly those arguments as the member mTf / mP / mT with mId = ++swSeq (merge or not).
    (The whole LAB Logic no longer runs in tests/lab_pine.py since LAB-20's library types, so only this part is executed.)"""
    lab = open(LAB, encoding="utf-8").read()
    a = lab.index("    // ZC: 新しい Pivot")
    blk = lab[a:lab.index("f_swAdd(k, sub, pv, pt)", a) + len("f_swAdd(k, sub, pv, pt)")]
    decl = [ln for ln in lab.split("\n") if re.match(r"var array<int>\s+lbPivLast[HL] = array.new_int\(4, na\)", ln)]
    zcuse = lab[lab.index("f_zcUse(int k) =>"):]
    zcuse = zcuse[:zcuse.index("\n\n")]
    body = "\n".join(ln[4:] if ln.startswith("    ") else ln for ln in blk.split("\n"))
    code = "\n".join(decl) + "\n" + zcuse + "\nif true\n" + "\n".join("    " + ln for ln in body.split("\n")) + "\n"
    py = compile(ap.Translator().translate(ap.logical_lines(code)), "<Lab ZC block>", "exec")
    rec = []
    env = ap.make_env(ap.Broker(), [])
    env.update(dict(zcUse1=True, zcUse2=True, zcUse3=True, zcUse4=True, _VARS=set(), _VARIPS=set(), __first__=True,
                    array__new_int=lambda n=0, v=None: [v] * n))
    env["f_swAdd"] = lambda k, sub, pv, pt: rec.append((k, sub, pt, pv, env["bar_index"]))
    rows = random_bars(11, n, vol=2.5, gaps=False)
    feeds = htf_feeds(rows, blocks=(12, 48, 276, 690), lens=(6, 6, 2, 1))
    for i in range(n):
        env["bar_index"] = i
        for k in (1, 2, 3, 4):
            for x in ("h", "ht", "l", "lt"):
                env[f"s{k}{x}"] = feeds[i].get(f"p{k}{x}")
        exec(py, env)
        env["__first__"] = False
    sw = lab[lab.index("f_swAdd(int k, int sub, float pv, int pt) =>"):]
    sw = sw[:sw.index("\n\n")]
    stores = all(x in sw for x in ("st.swSeq += 1", "int pid = st.swSeq", "z.mP  := array.from(pv)", "z.mTf := array.from(k)",
                                   "z.mT  := array.from(pt)", "z.mId := array.from(pid)", "array.push(a.mP, pv)",
                                   "array.push(a.mTf, k)", "array.push(a.mT, pt)", "array.push(a.mId, pid)"))
    h = Runner().run([bar(i, *rows[i], **feeds[i]) for i in range(n)])
    mine = [(l.tf, l.sub, l.key, l.pf, l.regBar) for l in h["hlAll"]]
    ids_ok = [l.id for l in h["hlAll"]] == list(range(1, len(mine) + 1))
    check("D ZoneComboLabXAU (0fec933) の ZC 登録と一致 (時間足・高値/安値・時刻キー・価格・登録5分足・ID 順)",
          rec == mine and ids_ok and stores and len(mine) > 20 and all(sum(1 for x in mine if x[0] == k) for k in range(4)),
          f"lines={len(mine)} per TF={[sum(1 for x in mine if x[0] == k) for k in range(4)]} f_swAdd stores args={stores} "
          f"first diff={next(((a, b) for a, b in zip(rec, mine) if a != b), None)} lab={len(rec)}")
    return mine


# ----------------------------------------------------------------------------------------------------------------
def static():
    s = src()
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    check("E indicator() 単体・strategy / alert / 注文なし", s.count("indicator(") == 1 and not re.search(r"\b(strategy|alert|alertcondition)\s*[.(]", code))
    lab = open(LAB, encoding="utf-8").read()

    def fn(t):
        i = t.index("f_lbPivotConfirmed(simple int len) =>")
        return t[i:t.index("[_ph[1], _pt[1], _pl[1], _lt[1]]", i)]
    check("E Pivot 関数は Lab と同一", fn(s) == fn(lab))
    req = re.findall(r'request\.security\(syminfo\.tickerid, "(\w+)",\s*f_lbPivotConfirmed\(hlPiv(\d)\), lookahead = barmerge\.lookahead_on\)', s)
    check("E 上位足の取得 60 / 240 / D / W・lookahead_on", req == [("60", "1"), ("240", "2"), ("D", "3"), ("W", "4")], str(req))
    ind = [ln for ln in s.split("\n") if ln.strip() and not ln.lstrip().startswith("//")]
    bad = [ln for ln in ind if (len(ln) - len(ln.lstrip(" "))) % 4 not in (0, 1) and not ln.startswith("     ")]
    check("E 継続行以外のインデントは 4 の倍数", not bad, str(bad[:3]))


def main():
    seeds = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5, 6]
    static()
    acceptance()
    bars = random_vs_oracle(seeds)
    invariants(bars)
    lab_crosscheck()
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok and not det.startswith(("contacts", "lines", "decided")) else "  " + det))
        bad += 0 if ok else 1
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
