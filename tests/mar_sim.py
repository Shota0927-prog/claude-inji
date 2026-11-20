"""MAR-1 checks — MaReactionStatsXAU.pine.   python3 tests/mar_sim.py

Runs the "MAR Logic" section of the indicator itself (mechanical Pine-subset -> Python translation by tests/acc_pine.py,
unchanged) on synthetic confirmed 5m bars. The contact price of a bar is the feed maP1 / maP2 (= raw[1] in the Pine source);
bars may instead give maRaw1 / maRaw2 (the request / ta.ema value of that bar) and the runner supplies maP = the previous
confirmed bar's raw, as Pine's [1] does.

  S. static: the HL (79e8d2f) copy regions are byte-identical to HorizontalLineReactionStatsXAU.pine, the EMA expressions are
     the Lab's (ZoneComboLabXAU zbMa1 / zbMa2), maP = raw[1], inputs / table layout / notes, no orders / alerts / drawings
  A. the horizontal-line acceptance cases (first-come, possible-reach flag, overshoot, invalid bars, latest 5, denominator)
     on the MA logic, from above and mirrored from below
  M. MA cases 1-6 of the instruction (6 = reference timing on an EMA model; numeric agreement with TradingView's ta.ema
     is NOT verified), fixed-value checks of the EMA model
  C. random paths (moving MA, na stretches, invalid bars, equal MAs) vs an independent oracle (full record sequence)
  B. invariants: display switch / record keep, unconfirmed bar, re-run
  X. mutations of the judgement functions: only the cases that must fail are checked

Also the shared harness for tests/por_sim.py.  Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / replay here).
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
HL = os.path.join(ROOT, "HorizontalLineReactionStatsXAU.pine")
LAB = os.path.join(ROOT, "ZoneComboLabXAU.pine")
MA = os.path.join(ROOT, "MaReactionStatsXAU.pine")
M5 = 300_000
T0 = 1_767_574_800_000          # 2026-01-05 01:00 UTC
MT = 0.01
R, B, A = 1, 2, 3
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def read(p):
    return open(p, encoding="utf-8").read()


def section(s, tag):
    i = s.index(f"// ==== {tag} Logic (begin) ")
    return s[s.index("\n", i) + 1:s.index(f"// ==== {tag} Logic (end) ")]


def with_keep(s, n):
    old = "int HL_REC_KEEP = 5 "
    assert s.count(old) == 1, "HL_REC_KEEP declaration changed"
    return s.replace(old, f"int HL_REC_KEEP = {n} ")


class Runner:
    """generic runner of a '<tag> Logic' section. bars: dicts t, o, h, l, c (+ conf False = unconfirmed update) + feeds."""

    def __init__(self, path, tag, feeds, overrides=None, source=None, run=True, rollback=False):
        s = source if source is not None else read(path)
        self.code = compile(ap.Translator().translate(ap.logical_lines(section(s, tag))), f"<{tag} logic>", "exec")
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
                   array__new_float=lambda n=0, v=None: [v] * n,
                   syminfo__mintick=MT, hlRun=run, _VARS=set(), _VARIPS=set(), __first__=True)
        self.env, self.feeds, self.rollback = env, feeds, rollback
        self.bar_index, self.committed = -1, None
        self.raw_prev = {}

    def step(self, b):
        conf = b.get("conf", True)
        if self.rollback and self.committed is not None:
            self.env.update(copy.deepcopy(self.committed))
        idx = self.bar_index + 1
        if conf:
            self.bar_index = idx
        e = self.env
        e.update(open=b["o"], high=b["h"], low=b["l"], close=b["c"], time=b["t"], time_close=b["t"] + M5, bar_index=idx,
                 barstate__isconfirmed=conf)
        for f in self.feeds:
            e[f] = b.get(f)
        for k in (1, 2):             # Pine's maRaw[1]: the previous confirmed bar's final value
            if f"maRaw{k}" in b:
                e[f"maP{k}"] = self.raw_prev.get(k)
                if conf:
                    self.raw_prev[k] = b[f"maRaw{k}"]
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
        return {k: list(e[k]) for k in ("hcN", "hcR", "hcB", "hcA", "hcF", "hcS", "hxLo", "hxHi", "hlUnk")} | {"bad": e["hs"].nBad}

    def recs(self):
        return [(r.pf, r.tf, r.dr, r.cTime, r.j, r.res, r.exL, r.exH, r.dTime) for r in self.env["hlRec"]]


def bar(i, o, h, l, c, **kv):
    assert l <= min(o, c) and h >= max(o, c), (i, o, h, l, c)
    d = dict(t=T0 + i * M5, o=o, h=h, l=l, c=c)
    d.update(kv)
    return d


def badbar(i, o, h, l, c, **kv):
    d = dict(t=T0 + i * M5, o=o, h=h, l=l, c=c)
    d.update(kv)
    return d


def mirror(bars, axis=4300.0, price_keys=()):
    out = []
    for b in bars:
        m = dict(b)
        f = lambda x: None if x is None else round(2 * axis - x, 2)     # noqa: E731
        m.update(o=f(b["o"]), h=f(b["l"]), l=f(b["h"]), c=f(b["c"]))
        for a, z in price_keys:          # (low key, high key) pairs swap; single keys mirror
            if z is None:
                m[a] = f(b.get(a))
            else:
                m[a], m[z] = f(b.get(z)), f(b.get(a))
        out.append(m)
    return out


def results(r):
    out = {}
    for pf, tf, dr, ct, j, res, lo, hi, dt in r.recs():
        out.setdefault((dr, (5, 10, 20)[j]), []).append((res, None if lo is None else round(lo * MT, 2), None if hi is None else round(hi * MT, 2)))
    return out


# ----------------------------------------------------------------------------------------------------------------
# the horizontal-line acceptance cases, for any indicator: kit = dict(make(rows) -> bars with reference 4300 on series 0 from bar 0,
# runner(**kw) -> Runner, mirror(bars) -> bars mirrored around 4300, name)
def hl_cases(kit, prefix="A"):
    mk, run, mir, ref = kit["make"], kit["runner"], kit["mirror"], kit["ref"]

    def ex(b):           # a hand-built bar carries the reference feed like the bars of make()
        d = dict(ref)
        d.update(b)
        return d
    B5 = {"hlBreak": 5.0}       # the horizontal-line cases were written for B = $5

    def both(name, rows, expect, pend=(), flags=(), n=1, B=B5):
        for dr, bars in ((1, mk(rows)), (-1, mir(mk(rows)))):
            r = run(overrides=B, keep=1000).run(bars)
            got = results(r)
            det, ok = [], True
            for tgt, exp in expect.items():
                g = got.get((dr, tgt), [None])[0]
                if g != exp:
                    ok = False
                    det.append(f"${tgt}: got {g} want {exp}")
            po = list(r["hlPend"])
            for tgt in pend:
                if not po or po[0].st[(5, 10, 20).index(tgt)] != 0:
                    ok = False
                    det.append(f"${tgt} not pending")
            for tgt in flags:
                if not po or not po[0].fl[(5, 10, 20).index(tgt)]:
                    ok = False
                    det.append(f"${tgt} flag missing")
            nn = r["hcN"][0 if dr == 1 else 3]
            if nn != n:
                ok = False
                det.append(f"N={nn}")
            check(f"{prefix} {name} ({'上から' if dr == 1 else '下から'})", ok, "; ".join(det) + f" | {got}")

    both("1 $10 反発・行き過ぎ $3", [(4304, 4304.5, 4297, 4302), (4302, 4310, 4299, 4309)], {5: (R, 3.0, 3.0), 10: (R, 3.0, 3.0)}, pend=(20,))
    both("2 $5 反発後に安値ちょうど 4295", [(4302, 4303, 4299, 4301), (4301, 4306, 4300.5, 4305), (4304, 4305, 4295, 4296)],
         {5: (R, 1.0, 1.0), 10: (B, None, None), 20: (B, None, None)}, n=2)
    both("3a 可能性フラグのまま追跡", [(4312, 4313, 4299, 4301)], {}, pend=(5, 10, 20), flags=(5, 10))
    both("3b フラグ後に確実な反発", [(4312, 4313, 4299, 4301), (4301, 4311, 4300, 4310)], {5: (R, 0.0, 1.0), 10: (R, 0.0, 1.0)}, pend=(20,))
    both("3c フラグ後に先に突破", [(4312, 4313, 4299, 4301), (4301, 4302, 4295, 4296)], {5: (A, None, None), 10: (A, None, None), 20: (B, None, None)})
    both("4 接触足で両側", [(4312, 4313, 4295, 4301)], {5: (A, None, None), 10: (A, None, None), 20: (B, None, None)})
    both("5a 次足 始値 4308", [(4302, 4304, 4299, 4303), (4308, 4311, 4295, 4300)], {5: (R, 1.0, 1.0), 10: (A, None, None), 20: (B, None, None)})
    both("5b 次足 始値 4310", [(4302, 4304, 4299, 4303), (4310, 4311, 4295, 4300)], {5: (R, 1.0, 1.0), 10: (R, 1.0, 1.0), 20: (B, None, None)})
    both("6 行き過ぎ $1～$3", [(4302, 4304, 4299, 4303), (4303, 4310, 4297, 4309)], {5: (R, 1.0, 3.0), 10: (R, 1.0, 3.0)}, pend=(20,))
    both("6b 始値で突破 (B=$15 初期値)", [(4302, 4304, 4299, 4303), (4285, 4290, 4280, 4288)],
         {5: (B, None, None), 10: (B, None, None), 20: (B, None, None)}, B={})
    rows7 = [(4302, 4303, 4299, 4301), (4301, 4302, 4300, 4301.5), (4301.5, 4304, 4299.5, 4303), (4303, 4304, 4300.01, 4303.5),
             (4303.5, 4304, 4299, 4302)]
    for dr, bars in ((1, mk(rows7)), (-1, mir(mk(rows7)))):
        r = run(overrides=B5).run(bars)
        ids = [o.id for o in r["hlPend"]]
        check(f"{prefix} 7 連続ヒゲ接触は 1 件・離脱後に 2 件目 ({dr})", r["hcN"][0 if dr == 1 else 3] == 2 and len(ids) == 2 and ids[0] < ids[1]
              and all(o.st[2] == 0 for o in r["hlPend"]), f"N={r['hcN']} ids={ids}")
    r = run(overrides=B5).run(mk([(4302, 4303, 4299, 4301), (4301, 4304, 4299.5, 4304), (4304, 4305, 4299, 4302)]))
    check(f"{prefix} 7b 終値だけ離れた足では再開しない", r["hcN"][0] == 1, str(r["hcN"][:6]))
    r = run(overrides=B5, keep=1000).run(mk([(4302, 4303, 4299, 4301), (4301, 4306, 4300.5, 4305), (4301, 4302, 4295, 4296)]))
    rr = results(r)
    check(f"{prefix} 7c 再接触足で前回分が突破・今回分が開始", r["hcN"][0] == 2 and rr.get((1, 10)) == [(B, None, None)] * 2
          and rr.get((1, 5)) == [(R, 1.0, 1.0), (B, None, None)], str(rr))
    # same-bar order: observation id ascending, then $5 -> $10 -> $20
    r = run(overrides=B5, keep=1000).run(mk([(4302, 4303, 4299, 4301), (4301, 4304, 4300.5, 4303), (4301, 4302, 4299.5, 4301),
                                             (4301, 4302, 4280, 4285)]))
    seq = [(x[3], x[4], x[5]) for x in r.recs()]
    t1, t3 = T0 + M5, T0 + 3 * M5
    check(f"{prefix} 同じ足の確定は観測 ID 昇順・$5→$10→$20", seq == [(t1, 0, B), (t1, 1, B), (t1, 2, B), (t3, 0, B), (t3, 1, B), (t3, 2, B)], str(seq))
    r = run(overrides=B5).run(mk([(4304, 4305, 4301, 4303), (4298.5, 4299, 4297, 4298), (4298, 4300, 4297.5, 4299)]))
    check(f"{prefix} 9 ギャップは接触にしない", r["hcN"][0] == 0 and r["hcN"][3] == 1, str(r["hcN"][:6]))
    r = run(overrides=B5, keep=1000).run(mk([(4303, 4304, 4301, 4302), (4300, 4306, 4299, 4305)]))
    check(f"{prefix} 始値 = P・直前終値が上 → 上から・始値から観測", r["hcN"][0] == 1 and results(r).get((1, 5)) == [(R, 0.0, 1.0)], str(results(r)))
    r = run(overrides=B5).run(mk([(4303, 4304, 4301, 4302)]) + [ex(badbar(2, 4310, 4304, 4299, 4302)), ex(bar(3, 4300, 4301, 4299, 4300.5))])
    check(f"{prefix} 直前足が不正で始値 = P → 方向不明 (欄外)", r["hcN"][0] == 0 and r["hcN"][3] == 0 and r["hlUnk"][0] == 1, f"unk={r['hlUnk']}")
    r = run(overrides={"hlBreak": 5.003}).run(mk([(4302, 4303, 4295, 4296)]))
    r2 = run(overrides={"hlBreak": 5.003}).run(mk([(4302, 4303, 4294.99, 4296)]))
    check(f"{prefix} 刻みに乗らない突破幅は次のティックから", r["hcB"][2] == 0 and r2["hcB"][2] == 1)
    tk = {x: run(overrides={"hlBreak": x}).run(mk([(4330, 4331, 4329, 4330)]))["hlBT"] for x in (15.0, 5.0, 0.29, 0.001, 0.01)}
    check(f"{prefix} 突破幅のティック換算 (15→1500, 5→500, 0.29→29, 0.001→1, 0.01→1)", tk == {15.0: 1500, 5.0: 500, 0.29: 29, 0.001: 1, 0.01: 1}, str(tk))
    # invalid confirmed bars (the HLR-2 regressions)
    p3 = [(4302, 4303, 4299, 4301)]
    for dr, bars in ((1, mk(p3) + [ex(badbar(2, 4310, 4304, 4299, 4302))]), (-1, mir(mk(p3) + [ex(badbar(2, 4310, 4304, 4299, 4302))]))):
        r = run(overrides=B5, keep=1000).run(bars)
        b0 = 0 if dr == 1 else 3
        und = [r["hcN"][b0 + j] - r["hcR"][b0 + j] - r["hcB"][b0 + j] - r["hcA"][b0 + j] - r["hcF"][b0 + j] for j in range(3)]
        check(f"{prefix} 不正足で 3 目標とも順序不明・反発 0・未決着 0・不正足 1 ({dr})",
              [r["hcA"][b0 + j] for j in range(3)] == [1, 1, 1] and sum(r["hcR"]) == 0 and und == [0, 0, 0] and r["hs"].nBad == 1
              and len(r["hlPend"]) == 0, f"{r.counters()}")
    r = run(overrides=B5).run(mk(p3) + [ex(badbar(2, 4300.5, 4304, 4301, 4303)), ex(bar(3, 4302, 4303, 4299.5, 4302.5))])
    check(f"{prefix} 不正足は離脱扱いせず直後の有効な接触も数えない", [r["hcN"][j] for j in range(3)] == [1, 1, 1] and r["hs"].nBad == 1)
    r = run(overrides=B5).run(mk(p3) + [ex(badbar(2, 4300.5, 4304, 4301, 4303)), ex(bar(3, 4303, 4304, 4301, 4302)), ex(bar(4, 4302, 4303, 4299.5, 4302.5))])
    check(f"{prefix} 不正足の後でも有効な離脱足で再接触", r["hcN"][0] == 2)
    r = run(overrides=B5).run(mk([(4302, 4303, 4299, 4301), (4301, 4302, 4300.5, 4301)]) + [ex(dict(t=T0 + 3 * M5, o=4301, h=None, l=4299, c=4300))])
    check(f"{prefix} na の足は不正足 (確定済み目標は保持)", r["hs"].nBad == 1 and len(r["hlPend"]) == 0 and sum(r["hcA"][:3]) == 3)
    # latest 5 records, all 6 counted; denominator
    r = run(overrides=B5).run(mk([(4302, 4303, 4299, 4301), (4301, 4321, 4300.5, 4320), (4301, 4302, 4294, 4295)]))
    kept = [(x[4], x[5]) for x in r.recs()]
    check(f"{prefix} 6 件確定 → 記録は最新 5 件・集計は 6 件", kept == [(1, R), (2, R), (0, B), (1, B), (2, B)] and sum(r["hcR"]) == 3
          and sum(r["hcB"]) == 3 and r["hcN"][:3] == [2, 2, 2], str(kept))
    check(f"{prefix} 集計期間 = 最初の time ～ 最後の time_close", r["hs"].firstT == T0 and r["hs"].lastT == T0 + 4 * M5)


# ----------------------------------------------------------------------------------------------------------------
# independent oracle: observation engine written from the spec (its own state machine; records in decision order)
class Engine:
    def __init__(self, B, nser):
        self.Bt = max(1, math.ceil(B / MT - 1e-9))
        self.D = [max(1, math.ceil(x / MT - 1e-9)) for x in (5.0, 10.0, 20.0)]
        self.nser = nser
        self.obs, self.recs, self.unk, self.nbad = [], [], [0] * nser, 0
        self.prev = None          # (o, h, l, c) ticks of the previous VALID bar, None if the previous bar was invalid / none

    @staticmethod
    def bad(b):
        v = [b["o"], b["h"], b["l"], b["c"]]
        return any(x is None for x in v) or b["h"] < max(b["o"], b["c"]) or b["l"] > min(b["o"], b["c"])

    def tk(self, x):
        return int(math.floor(x / MT + 0.5)) if x >= 0 else -int(math.floor(-x / MT + 0.5))    # Pine math.round (half away from 0)

    def _dec(self, ob, j, res, t):
        ob["res"][j] = res
        ob["flag"][j] = False
        self.recs.append((ob["pf"], ob["k"], ob["dr"], ob["t"], j, res[0], res[1] if res[0] == 1 else None, res[2] if res[0] == 1 else None, t))

    def invalid(self, t):
        self.nbad += 1
        for ob in self.obs:
            for j in range(3):
                if ob["res"][j] is None:
                    self._dec(ob, j, (3,), t)
        self.obs = []
        self.prev = None

    def update(self, o, h, l, c, t):
        D, Bt = self.D, self.Bt
        for ob in self.obs:
            P, s = ob["p"], ob["dr"]
            on, hn, ln = (o - P, h - P, l - P) if s == 1 else (P - o, P - l, P - h)
            for j in range(3):
                if ob["res"][j] is not None:
                    continue
                f = ob["flag"][j]
                if on >= D[j]:
                    self._dec(ob, j, (1, 0 if f else ob["M"], ob["M"]), t)
                elif on <= -Bt:
                    self._dec(ob, j, (3,) if f else (2,), t)
                elif hn >= D[j] and ln <= -Bt:
                    self._dec(ob, j, (3,), t)
                elif hn >= D[j]:
                    lo = max(ob["M"], max(0, -on))
                    self._dec(ob, j, (1, 0 if f else lo, max(lo, -ln)), t)
                elif ln <= -Bt:
                    self._dec(ob, j, (3,) if f else (2,), t)
            ob["M"] = max(ob["M"], -ln)
        self.obs = [ob for ob in self.obs if any(x is None for x in ob["res"])]

    def contact(self, k, P, pf, o, h, l, c, t):
        s = 1 if o > P else -1 if o < P else (0 if self.prev is None else 1 if self.prev[3] > P else -1 if self.prev[3] < P else 0)
        if s == 0:
            self.unk[k] += 1
            return
        on, hn, ln, cn = (o - P, h - P, l - P, c - P) if s == 1 else (P - o, P - l, P - h, P - c)
        ob = dict(p=P, pf=pf, dr=s, k=k, res=[None] * 3, flag=[False] * 3, M=0, t=t)
        self.all.append(ob)
        for j in range(3):
            rr, bb = hn >= self.D[j], ln <= -self.Bt
            if rr and bb:
                self._dec(ob, j, (3,), t)
            elif bb:
                self._dec(ob, j, (2,), t)
            elif rr and (on == 0 or cn >= self.D[j]):
                self._dec(ob, j, (1, 0, max(0, -ln)), t)
            elif rr:
                ob["flag"][j] = True
        ob["M"] = max(0, -ln)
        if any(x is None for x in ob["res"]):
            self.obs.append(ob)

    all = None

    def start(self):
        self.all = []

    def agg(self):
        n = self.nser * 6
        g = dict(hcN=[0] * 24, hcR=[0] * 24, hcB=[0] * 24, hcA=[0] * 24, hcF=[0] * 24, hcS=[0] * 24, hxLo=[-1] * 24, hxHi=[-1] * 24)
        assert n <= 24
        for ob in self.all:
            for j in range(3):
                ix = (ob["k"] * 2 + (0 if ob["dr"] == 1 else 1)) * 3 + j
                g["hcN"][ix] += 1
                r = ob["res"][j]
                if r is None:
                    g["hcF"][ix] += 1 if ob["flag"][j] else 0
                elif r[0] == 1:
                    g["hcR"][ix] += 1
                    g["hxLo"][ix] = max(g["hxLo"][ix], r[1])
                    g["hxHi"][ix] = max(g["hxHi"][ix], r[2])
                    g["hcS"][ix] += 1 if r[1] == r[2] else 0
                elif r[0] == 2:
                    g["hcB"][ix] += 1
                else:
                    g["hcA"][ix] += 1
        g["hlUnk"] = self.unk
        g["bad"] = self.nbad
        return g


def irecs(r):
    return [(x.pf, x.tf, x.dr, x.cTime, x.j, x.res, x.exL, x.exH, x.dTime) for x in r["hlRec"]]


# ----------------------------------------------------------------------------------------------------------------
# mutations of the judgement functions: the named cases must fail (only those are checked)
def mutations(path, kit_for_source, muts, prefix):
    base = read(path)
    for desc, old, new, must_fail in muts:
        assert base.count(old) == 1, old
        global RESULTS
        saved, RESULTS = RESULTS, []
        hl_cases(kit_for_source(base.replace(old, new)), prefix="mut")
        failed = {n for n, ok, _ in RESULTS if not ok}
        RESULTS = saved
        miss = [m for m in must_fail if not any(n.startswith("mut " + m) for n in failed)]
        check(f"X {prefix} 改変「{desc}」で該当ケースが失敗する: {', '.join(must_fail)}", not miss, f"not failing: {miss}")


MUTS = [
    ("接触足: 始値が線の外・終値未達でも反発確定", "            if oN == 0 or cN >= d\n", "            if true\n", ["3a", "3c"]),     # 3b ends as rebound 0-$1 either way
    ("次足: 始値の反発判定を > に", "            if oN >= d\n", "            if oN > d\n", ["5b"]),
    ("次足: フラグ後の突破 (ヒゲ) を突破に", "                else if b\n                    f_hlDecide(ob, j, f ? 3 : 2, na, na)\n",
     "                else if b\n                    f_hlDecide(ob, j, 2, na, na)\n", ["3c"]),
    ("行き過ぎ上限に到達足のヒゲを入れない", "f_hlDecide(ob, j, 1, f ? 0 : lo, math.max(lo, adv))", "f_hlDecide(ob, j, 1, f ? 0 : lo, lo)", ["6 行き過ぎ"]),
    ("不正足で未確定目標を突破にする", "                if array.get(ob.st, j) == 0\n                    f_hlDecide(ob, j, 3, na, na)",
     "                if array.get(ob.st, j) == 0\n                    f_hlDecide(ob, j, 2, na, na)", ["不正足で 3 目標"]),
    ("記録を 5 件で切らない", "    if array.size(hlRec) > HL_REC_KEEP\n", "    if false\n", ["6 件確定"]),
]


# ================================================================================================ MA specific
MA_FEEDS = ["maP1", "maP2"]


def ma_runner(overrides=None, keep=None, source=None, **kw):
    s = source if source is not None else read(MA)
    if keep is not None:
        s = with_keep(s, keep)
    ov = {"maUse2": False}
    ov.update(overrides or {})
    return Runner(MA, "MAR", MA_FEEDS, ov, source=s, **kw)


def ma_kit(source=None):
    def make(rows):
        return [bar(0, 4330, 4332, 4328, 4330, maP1=4300.0)] + [bar(n, *r, maP1=4300.0) for n, r in enumerate(rows, start=1)]
    return dict(make=make, ref={"maP1": 4300.0}, runner=lambda overrides=None, keep=None: ma_runner(overrides, keep, source=source),
                mirror=lambda bars: mirror(bars, price_keys=[("maP1", None)]))


def static_common(s, tag, name):
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    hl = read(HL)
    regions = re.findall(r"// ==== HLR copy (\w+) \(begin\)[^\n]*\n(.*?)\n *// ==== HLR copy \1 \(end\)", s, re.S)
    check(f"S {tag} 水平線版の写し (型・集計・閾値・添字・判定関数・不正足と既存観測の更新) が 79e8d2f と同一",
          [n for n, _ in regions] == ["types", "counters", "ticks", "idx", "core", "bar"] and all(t in hl for _, t in regions),
          str([n for n, t in regions if t not in hl]))
    check(f"S {tag} indicator() 単体・strategy / alert / 描画なし",
          s.count("indicator(") == 1 and f'indicator("{name}"' in s and not re.search(r"\b(strategy|alert|alertcondition)\s*[.(]", code)
          and not re.search(r"\b(line|label|box|polyline)\.new\(|plotshape|fill\(", code))
    check(f"S {tag} 突破幅 初期 $15・最小 / 刻み $0.01・換算式、表示切替 集計 (初期) / 直近結果5件",
          'hlBreak = input.float(15.0, "突破幅 B ($)", minval = 0.01, step = 0.01,' in code
          and "math.max(1, math.ceil(usd / syminfo.mintick - 1e-9))" in code
          and 'input.string("集計", "表示", options = ["集計", "直近結果5件"]' in code)
    check(f"S {tag} 集計 10 列・直近結果 7 列・右上 1 表・Asia/Tokyo・format.mintick・time_close",
          'array.from("系列", "到達", "目標", "N (接触数)", "反発先着 件数 (%)", "突破先着 件数 (%)", "順序不明 (内 追跡中)", "未決着", "反発前の最大行き過ぎ (単一値件数)", "決着例内反発率")' in code
          and 'array.from("接触時刻 (JST)", "基準価格", "系列", "接触方向", "目標", "結果", "反発前の最大行き過ぎ")' in code
          and len(re.findall(r"table\.new\(", code)) == len(re.findall(r"table\.new\(position\.top_right,", code)) == 3
          and '"Asia/Tokyo"' in code and "format.mintick" in code and "hs.lastT := time_close" in code
          and "標準5分足で使用してください" in code and not re.search(r"syminfo\.timezone|\"#\.##\"", code))
    check(f"S {tag} 標準 5分チャートだけで実行・確定足だけ処理",
          "bool hlRun = timeframe.isminutes and timeframe.multiplier == 5 and chart.is_standard" in code
          and "if hlRun and barstate.isconfirmed" in code)
    bad = [ln for ln in s.split("\n") if ln.strip() and not ln.lstrip().startswith("//")
           and (len(ln) - len(ln.lstrip(" "))) % 4 and not ln.startswith("     ")]
    check(f"S {tag} インデント (継続行以外は 4 の倍数)", not bad, str(bad[:2]))


def ma_static():
    s = read(MA)
    static_common(s, "MA", "MaReactionStatsXAU")
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    lab = read(LAB)
    l1 = re.search(r'float zbMa1 = (request\.security\(syminfo\.tickerid, "1", ta\.ema\(close, )zbLen1(\), lookahead = barmerge\.lookahead_off\))', lab)
    l2 = re.search(r"float zbMa2 = (ta\.ema\(close, )zbLen2(\))", lab)
    check("S MA の式は Lab の zbMa1 / zbMa2 と同じ (request の中に [1] なし)、接触価格 = raw[1]",
          f"float maRaw1 = {l1.group(1)}maLen1{l1.group(2)}" in code and f"float maRaw2 = {l2.group(1)}maLen2{l2.group(2)}" in code
          and "float maP1 = maRaw1[1]" in code and "float maP2 = maRaw2[1]" in code
          and re.findall(r"\w+\[\d+\]", re.sub(r'"[^"\n]*"', '""', code)) == ["maRaw1[1]", "maRaw2[1]"])
    check("S MA 入力 (両方 ON・3000・最小 1)、欄外の説明・系列名に本数",
          'maUse1 = input.bool(true, "1分足 EMA"' in code and 'maLen1 = input.int(3000, "1分足 EMA 本数", minval = 1' in code
          and 'maUse2 = input.bool(true, "5分足 EMA"' in code and 'maLen2 = input.int(3000, "5分足 EMA 本数", minval = 1' in code
          and "MA接触は5分足開始時の確定値、接触後の基準価格は固定" in code
          and '"1分EMA" + str.tostring(maLen1) : "5分EMA" + str.tostring(maLen2)' in code and "MA 値欠落足" in code)


def ema_model(src, n):
    """EMA model (not TradingView's ta.ema itself): the first valid input is the initial EMA; afterwards
    EMA = alpha * x + (1 - alpha) * previous EMA with alpha = 2 / (n + 1); a missing input (None) does not update and keeps the
    previous EMA; None before the first valid input"""
    out, e = [], None
    a = 2.0 / (n + 1)
    for x in src:
        if x is not None:
            e = x if e is None else a * x + (1 - a) * e
        out.append(e)
    return out


def ema_model_cases():
    for src, n, want in (([100, 110, 120], 3, [100, 105, 112.5]), ([100, 110, 120], 1, [100, 110, 120]),
                         ([None, 100, 110, 120], 3, [None, 100, 105, 112.5]), ([100, None, 110], 3, [100, 100, 105])):
        got = ema_model(src, n)
        check(f"M EMA モデル {src}・期間 {n} → {want}", got == want, str(got))


def ma_cases():
    ema_model_cases()
    B5 = {"hlBreak": 5.0}
    # 1: the confirmed EMA of this bar is 4299 but the EMA known at its start is 4305 -> 0 contacts
    r = ma_runner(B5).run([bar(0, 4320, 4322, 4318, 4320, maRaw1=4305.0), bar(1, 4301, 4302, 4298, 4299, maRaw1=4299.0)])
    check("M 1 今回の確定 EMA 4299・開始時の EMA 4305 → 接触 0 件", sum(r["hcN"]) == 0 and r["maCur"][0] == 430500, f"P={r['maCur']}")
    # 2: the observation keeps P = 4300 after the MA moves to 4310
    bars = [bar(0, 4330, 4332, 4328, 4330, maP1=4300.0), bar(1, 4302, 4304, 4299, 4303, maP1=4300.0),
            bar(2, 4303, 4310, 4302, 4309, maP1=4310.0)]
    r = ma_runner(B5, keep=1000).run(bars)
    rr = results(r)
    po = list(r["hlPend"])
    check("M 2 MA が 4310 に動いても元の観測は 4300 基準 ($10 反発は 4310 で成立)",
          rr.get((1, 10)) == [(R, 1.0, 1.0)] and po and po[0].p == 430000 and sum(r["hcN"]) == 3, f"{rr} pend P={[o.p for o in po]}")
    bars2 = bars[:2] + [bar(2, 4303, 4306, 4302, 4305, maP1=4310.0), bar(3, 4305, 4306, 4295, 4296, maP1=4310.0)]
    r = ma_runner(B5, keep=1000).run(bars2)
    check("M 2b 突破も元の基準 4300 − B (MA 4310 に対してではない)", results(r).get((1, 10)) == [(B, None, None)] and results(r).get((1, 5)) == [(R, 1.0, 1.0)],
          str(results(r)))
    # 3: previous bar P 4300 with low 4301 / high 4303 = away; this bar's P 4302 touched -> 2nd contact
    base = [bar(0, 4330, 4332, 4328, 4330, maP1=4300.0), bar(1, 4302, 4303, 4299, 4301, maP1=4300.0)]
    r = ma_runner(B5).run(base + [bar(2, 4302, 4303, 4301, 4302.5, maP1=4300.0), bar(3, 4303, 4304, 4301.5, 4303.5, maP1=4302.0)])
    check("M 3 直前足 (P 4300・安値 4301・高値 4303) で離脱 → 今回 P 4302 への接触を受け付ける", r["hcN"][0] == 2, str(r["hcN"][:6]))
    # 4: previous bar P 4300 with low 4299 / high 4301 = not away -> no re-contact at P 4302
    r = ma_runner(B5).run(base + [bar(2, 4300, 4301, 4299, 4300.5, maP1=4300.0), bar(3, 4301, 4303, 4300.5, 4302.5, maP1=4302.0)])
    check("M 4 直前足 (P 4300・安値 4299・高値 4301) は離脱でない → P 4302 に接触しても数えない", r["hcN"][0] == 1, str(r["hcN"][:6]))
    r = ma_runner(B5).run(base + [bar(2, 4302.5, 4303, 4302.1, 4302.5, maP1=4300.0), bar(3, 4302.5, 4303, 4301.5, 4302, maP1=4302.0)])
    check("M 4b 直前足の高安と今回の MA を組み合わせない (直前足 4302.1-4303 は今回 P 4302 の上でも、直前 P 4300 からは離脱 → 受付)",
          r["hcN"][0] == 2)
    r = ma_runner(B5).run(base + [bar(2, 4301, 4302, 4299.5, 4301.5, maP1=4303.0), bar(3, 4301.5, 4303.5, 4301, 4303, maP1=4303.0)])
    check("M 4c 直前足の P が離脱を決める (直前足は P 4303 から見て下に離脱 → 今回 P 4303 で受付、下から)", r["hcN"][0] == 1 and r["hcN"][3] == 1)
    # 5: two MAs at the same price -> one contact each; direction-unknown first contact sets hit; MA updates do not reset it
    r = ma_runner({"maUse2": True, "hlBreak": 5.0}).run(
        [bar(0, 4330, 4332, 4328, 4330, maP1=4300.0, maP2=4300.0), bar(1, 4302, 4303, 4299, 4301, maP1=4300.0, maP2=4300.0)])
    check("M 5 2 本の MA が同価格 4300 → それぞれ 1 件", r["hcN"][0] == 1 and r["hcN"][6] == 1 and len(r["hlPend"]) == 2, str(r["hcN"][:12]))
    r = ma_runner(B5).run([bar(0, 4302, 4302, 4300, 4300), bar(1, 4300, 4301, 4299, 4300.5, maP1=4300.0),
                           bar(2, 4300.5, 4302, 4299, 4301, maP1=4300.0), bar(3, 4301, 4302, 4300, 4301.5, maP1=4301.0)])
    check("M 5b 初回の方向不明でも接触済み・MA 更新でリセットしない (以後の連続接触は 0 件)",
          r["hlUnk"][0] == 1 and sum(r["hcN"]) == 0 and r["maHit"][0], f"unk={r['hlUnk']} N={sum(r['hcN'])}")
    r = ma_runner(B5).run([bar(0, 4302, 4303, 4299, 4301), bar(1, 4301, 4302, 4299, 4300, maP1=4300.0)])
    check("M 5c raw[1] が初めて有効になった足から初回接触 (1 本待たせない)", r["hcN"][0] == 1)
    # MA na: new contacts paused, hit and observations kept, next bar's separation not usable
    r = ma_runner(B5).run(base + [bar(2, 4301, 4302, 4300.5, 4301.5, maP1=None), bar(3, 4301.5, 4302, 4299.5, 4301, maP1=4300.0)])
    check("M na MA の足は新規接触休止・欠落を数え、次足の離脱確認に使えない (観測は継続)",
          r["hcN"][0] == 1 and r["maMiss"][0] == 1 and len(r["hlPend"]) == 1 and r["maHit"][0], f"N={r['hcN'][:3]} miss={r['maMiss']}")
    r = ma_runner(B5).run(base + [bar(2, 4302, 4303, 4299.5, 4302.5, maP1=None)])
    check("M na MA の足でも接触していれば数えない", r["hcN"][0] == 1 and len(r["hlPend"]) == 1)
    # 6: timing: P of bar t = raw of bar t-1 (Lab's own expressions, modelled with ta.ema over the same closes)
    rnd = random.Random(3)
    c1 = [4300.0]
    for _ in range(6 * 5 * 40 - 1):
        c1.append(round(c1[-1] + rnd.gauss(0, 0.6), 2))
    one = ema_model(c1, 30)                          # 1-minute EMA(30)
    raw1 = [one[i * 5 + 4] for i in range(len(c1) // 5)]        # request.security("1", lookahead_off) on a 5m bar = its last 1m value
    rows = [(c1[i * 5], max(c1[i * 5:i * 5 + 5]), min(c1[i * 5:i * 5 + 5]), c1[i * 5 + 4]) for i in range(len(c1) // 5)]
    raw5 = ema_model([r_[3] for r_ in rows], 12)
    bars = [bar(i, *rows[i], maRaw1=raw1[i], maRaw2=raw5[i]) for i in range(len(rows))]
    r = ma_runner({"maUse2": True, "hlBreak": 5.0})
    curf = []
    for b in bars:
        r.step(b)
        curf.append(list(r["maCurF"]))
    ok = all(curf[i] == [raw1[i - 1] if i else None, raw5[i - 1] if i else None] for i in range(len(bars)))
    miss = r["maMiss"]
    check("M 6 モデル上での参照時刻の対応: Pcurr = 直前 5分足の raw (1分 EMA = 直前 5分足の最後の 1分値、5分 EMA = 直前足の値)、"
          "欠損なしデータでは raw[1] の欠落は両系列とも最初の 1 足だけ (miss = [1, 1])",
          ok and miss == [1, 1] and all(x is not None for x in raw1 + raw5) and sum(r["hcN"]) > 0,
          f"bars={len(bars)} miss={miss} N={sum(r['hcN'])}")


def ma_random(seeds):
    for seed in seeds:
        rnd = random.Random(seed)
        B = (15.0, 5.0, 7.5)[seed % 3]
        p, rows, mas = 4300.0, [], []
        m1 = m2 = 4300.0
        for i in range(2500):
            o = round(p + (rnd.uniform(-5, 5) if rnd.random() < 0.06 else 0), 2)
            c = round(o + rnd.gauss(0, 1.4), 2)
            h = round(max(o, c) + abs(rnd.gauss(0, 0.9)), 2)
            l = round(min(o, c) - abs(rnd.gauss(0, 0.9)), 2)
            if rnd.random() < 0.05:
                o = round(o)
                h, l = max(h, o), min(l, o)
            m1 = round(m1 + 0.15 * (c - m1), 2) if rnd.random() > 0.03 else m1
            m2 = round(m2 + 0.05 * (c - m2), 2)
            e1 = None if 300 < i < 340 or rnd.random() < 0.01 else m1
            e2 = None if i < 60 else (e1 if rnd.random() < 0.05 and e1 is not None else m2)    # equal MAs sometimes
            rows.append(dict(t=T0 + i * M5, o=o, h=h, l=l, c=c, maP1=e1, maP2=e2))
            p = c
        for i in range(10, len(rows)):
            if rnd.random() < 0.012:
                k = rnd.randrange(3)
                if k == 0:
                    rows[i][rnd.choice("ohlc")] = None
                elif k == 1:
                    rows[i]["h"] = round(max(rows[i]["o"], rows[i]["c"]) - 0.5, 2)
                else:
                    rows[i]["l"] = round(min(rows[i]["o"], rows[i]["c"]) + 0.5, 2)
        r = ma_runner({"maUse2": True, "hlBreak": B}, keep=10 ** 6).run(rows)
        # oracle
        en = Engine(B, 2)
        en.start()
        hit, prevP = [False, False], [None, None]
        for b in rows:
            t = b["t"]
            Ps = [None if b[f"maP{k + 1}"] is None else en.tk(b[f"maP{k + 1}"]) for k in range(2)]
            if Engine.bad(b):
                en.invalid(t)
            else:
                o, h, l, c = (en.tk(b[x]) for x in "ohlc")
                en.update(o, h, l, c, t)
                for k in range(2):
                    P = Ps[k]
                    if P is None or not (l <= P <= h):
                        continue
                    if hit[k] and not (en.prev is not None and prevP[k] is not None and (en.prev[2] > prevP[k] or en.prev[1] < prevP[k])):
                        continue
                    hit[k] = True
                    en.contact(k, P, b[f"maP{k + 1}"], o, h, l, c, t)
                en.prev = (o, h, l, c)
            prevP = Ps
        g, c = en.agg(), r.counters()
        same = all(c[k] == g[k] for k in g) and irecs(r) == en.recs
        nN = sum(g["hcN"]) // 3
        check(f"C MA random seed {seed} (B={B}) == oracle (集計・確定記録の全件と順序)", same and nN > 100 and g["bad"] > 15 and sum(g["hlUnk"]) >= 0,
              f"contacts={nN} unk={sum(g['hlUnk'])} bad={g['bad']} recs={len(en.recs)} pending={len(r['hlPend'])} "
              f"diff={[k for k in g if c[k] != g[k]]} recs_equal={irecs(r) == en.recs}")
        rows_ok = all(c["hcN"][x] - c["hcR"][x] - c["hcB"][x] - c["hcA"][x] >= c["hcF"][x] >= 0 for x in range(12)) \
            and all(c["hcN"][g_ * 3] == c["hcN"][g_ * 3 + 1] == c["hcN"][g_ * 3 + 2] for g_ in range(4))
        check(f"B MA seed {seed}: 未決着 >= 0・3 目標の N 一致", rows_ok)
    return rows


def invariants(runner, bars, prefix):
    a = runner().run(bars).counters()
    check(f"B {prefix} 同一確定履歴の再処理で一致", runner().run(bars).counters() == a)
    check(f"B {prefix} 表示切替・記録上限の変更で全件集計が不変",
          runner(overrides={"hlView": "直近結果5件"}, keep=1).run(bars).counters() == a == runner(keep=10 ** 6).run(bars).counters())
    base = runner(rollback=True).run(bars[:-1])
    c0 = base.counters()
    last = dict(bars[-1])
    last.update(conf=False)
    if last["h"] is not None and last["l"] is not None:
        last.update(h=last["h"] + 40, l=last["l"] - 40)
    base.step(last)
    check(f"B {prefix} 未確定足は集計に入らない", base.counters() == c0)
    check(f"B {prefix} 対象外チャートは集計しない", sum(runner(run=False).run(bars).counters()["hcN"]) == 0)


def report():
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok and not det.startswith(("contacts", "bars")) else "  " + det))
        bad += 0 if ok else 1
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    return bad


def main():
    ma_static()
    hl_cases(ma_kit())
    ma_cases()
    rows = ma_random([1, 2, 3, 4])
    invariants(lambda overrides=None, keep=None, **kw: ma_runner(dict({"maUse2": True}, **(overrides or {})), keep, **kw), rows, "MA")
    mutations(MA, ma_kit, MUTS, "MA")
    sys.exit(1 if report() else 0)


if __name__ == "__main__":
    main()
