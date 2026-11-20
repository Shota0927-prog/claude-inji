"""PointMasterFvgAbsReboundV2.pine §6 V2 有効根拠 / §12 モード A・B と PointMasterVerifierV2.pine のイベント抽出を
Python で写したモデルと、指示書 §14 の機能確認。Pine 上の実行確認ではない（モデルによる確認）。"""
import math

N_LOGIC, N_TF = 25, 6
RULE = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 3, 4]

def fam(li):
    return 0 if li <= 3 or li in (18, 19) else 1 if li <= 11 else 2 if li <= 17 else 3 if li <= 22 else 4 if li == 23 else 5


class Evidence:
    """§6 f_v2ApplyTf のモデル。key = (li, ti, d) d: 0 LONG / 1 SHORT"""
    def __init__(self, hold=6):
        self.v = {}
        self.hold = hold
        self.neg = {}

    def apply(self, ti, close, sigs, levels=None, slopes=None, ema=None, hi=None, lo=None, fib_inv=()):
        # sigs: {li: 'L' | 'S'} / levels: {(li, d): level}
        levels, slopes = levels or {}, slopes or {}
        for li in range(N_LOGIC):
            rule = RULE[li]
            sig = sigs.get(li)
            if rule == 3:
                self.v[(li, ti, 0)] = dict(valid=sig == 'L', price=True)
                self.v[(li, ti, 1)] = dict(valid=sig == 'S', price=True)
                continue
            for d in (0, 1):
                e = self.v.get((li, ti, d))
                if e and e['valid']:
                    e['age'] += 1
                    e['rem'] -= 1
                    if e['rem'] <= 0:
                        e['valid'] = False
                    elif rule != 2 and e['price']:
                        lv = ema if rule == 1 else e['lvl'] + e['slp'] * e['age']
                        if lv is not None and ((d == 0 and close < lv) or (d == 1 and close > lv)):
                            e['valid'] = False
                            self.neg[(ti, d)] = self.neg.get((ti, d), 0) + 1
            if sig:
                dn = 0 if sig == 'L' else 1
                lv = levels.get((li, dn))
                if rule == 4:
                    lv = lo if dn == 0 else hi
                pok = rule == 2 or (ema is not None if rule == 1 else lv is not None)
                self.v[(li, ti, dn)] = dict(valid=True, price=pok, rem=self.hold, age=0, lvl=lv, slp=slopes.get((li, dn), 0.0))
                o = self.v.get((li, ti, 1 - dn))
                if o:
                    o['valid'] = False
            if li in (20, 21, 22) and li in fib_inv:
                for d in (0, 1):
                    if (li, ti, d) in self.v:
                        self.v[(li, ti, d)]['valid'] = False

    def cur(self, li, ti, d):
        e = self.v.get((li, ti, d))
        return bool(e and e['valid'] and e['price'])


def points(ev, pre):
    """B 点数。pre = {(li, ti, d): factor}。戻り値 curT, intT, famT : dict[(ti, d)]"""
    bcur, bint = {}, {}
    for ti in range(N_TF):
        for li in range(N_LOGIC):
            for d in (0, 1):
                cv = ev.cur(li, ti, d)
                key = (fam(li), ti, d)
                if cv:
                    bcur[key] = 1.0
                bint[key] = max(bint.get(key, 0.0), max(1.0 if cv else 0.0, pre.get((li, ti, d), 0.0)))
    curT, intT, famT = {}, {}, {}
    for ti in range(N_TF):
        for d in (0, 1):
            curT[(ti, d)] = sum(bcur.get((f, ti, d), 0.0) for f in range(6))
            intT[(ti, d)] = sum(bint.get((f, ti, d), 0.0) for f in range(6))
            famT[(ti, d)] = sum(1 for f in range(6) if bint.get((f, ti, d), 0.0) > 0)
    return curT, intT, famT


class ModeB:
    def __init__(self, min_pts=2.0, warn_pts=2.0, warn_fams=2, recover=2):
        self.p = (min_pts, warn_pts, warn_fams, recover)
        self.ep = [False, False]; self.cau = [False, False]; self.after = [False, False]
        self.rec = [0, 0]; self.basis = [None, None]
        self.lastPL = None; self.lastPLneg = False; self.lastPH = None; self.lastPHneg = False
        self.last_t = None

    def bar(self, t, close, curT, intT, famT, newPL=None, newPH=None, neg=None):
        if self.last_t is not None and t <= self.last_t:
            return None                          # 同じ確定足の再評価はしない
        self.last_t = t
        min_pts, warn_pts, warn_fams, recover = self.p
        neg = neg or {}
        if self.lastPL is not None and close < self.lastPL:
            self.lastPLneg = True
        if self.lastPH is not None and close > self.lastPH:
            self.lastPHneg = True
        codes = []
        for di in (0, 1):
            D = 1 if di == 0 else -1
            od = 1 - di
            own5, opp5, own15, opp15 = curT[(1, di)], curT[(1, od)], curT[(2, di)], curT[(2, od)]
            c5 = own5 >= min_pts and own5 > opp5
            c15 = own15 >= min_pts and own15 > opp15
            w1 = intT[(0, od)] >= warn_pts and famT[(0, od)] >= warn_fams
            w5 = intT[(1, od)] >= warn_pts and famT[(1, od)] >= warn_fams
            warn = w1 or w5
            ep, basis = self.ep[di], self.basis[di]
            if ep and basis is not None and (close < basis if D == 1 else close > basis):
                code = 3
                self.ep[di] = False; self.cau[di] = False; self.after[di] = True; self.rec[di] = 0; self.basis[di] = None
            else:
                if ep:
                    if D == 1 and newPL is not None and close > newPL and newPL > basis:
                        self.basis[di] = newPL
                    if D == -1 and newPH is not None and close < newPH and newPH < basis:
                        self.basis[di] = newPH
                if D == 1:
                    lastP = newPL if newPL is not None else self.lastPL
                    lastNeg = False if newPL is not None else self.lastPLneg
                else:
                    lastP = newPH if newPH is not None else self.lastPH
                    lastNeg = False if newPH is not None else self.lastPHneg
                startOk = lastP is not None and not lastNeg and (lastP < close if D == 1 else lastP > close)
                cand = c5 and c15 and (ep or startOk) and not warn
                if ep:
                    if cand:
                        if self.cau[di]:
                            rc = self.rec[di] + 1
                            if rc >= recover:
                                self.cau[di] = False; self.rec[di] = 0; code = 1
                            else:
                                self.rec[di] = rc; code = 2
                        else:
                            code = 1
                    else:
                        self.cau[di] = True; self.rec[di] = 0; code = 2
                else:
                    if cand:
                        rc = self.rec[di] + 1
                        if not self.after[di] or rc >= recover:
                            self.ep[di] = True; self.cau[di] = False; self.after[di] = False; self.rec[di] = 0
                            self.basis[di] = lastP; code = 1
                        else:
                            self.rec[di] = rc; code = 2
                    else:
                        self.rec[di] = 0
                        code = 2 if warn else 0
            codes.append(code)
        if newPL is not None:
            self.lastPL, self.lastPLneg = newPL, close < newPL
        if newPH is not None:
            self.lastPH, self.lastPHneg = newPH, close > newPH
        return codes


def mkpts(l5=0, s5=0, l15=0, s15=0, l1i=0, s1i=0, f1l=0, f1s=0, l5i=0, s5i=0, f5l=0, f5s=0):
    curT = {(ti, d): 0.0 for ti in range(N_TF) for d in (0, 1)}
    intT = dict(curT); famT = {k: 0 for k in curT}
    curT[(1, 0)], curT[(1, 1)], curT[(2, 0)], curT[(2, 1)] = l5, s5, l15, s15
    intT[(0, 0)], intT[(0, 1)], famT[(0, 0)], famT[(0, 1)] = l1i, s1i, f1l, f1s
    intT[(1, 0)], intT[(1, 1)], famT[(1, 0)], famT[(1, 1)] = l5i, s5i, f5l, f5s
    return curT, intT, famT


def mode_a(D, aIntL, aIntS, curDom, net5, net15, st, P):
    """モード A の1方向・1足（st = dict(cont, exit)）"""
    tot = sum(aIntL) + sum(aIntS)
    dom = (sum(aIntL) - sum(aIntS)) / tot if tot > 0 else 0.0
    oppTf = sum(1 for ti in range(4) if D * (aIntL[ti] - aIntS[ti]) < 0)
    mid = D * (aIntL[2] - aIntS[2]) < 0 and D * (aIntL[3] - aIntS[3]) < 0
    oDom, cDir, en = -D * dom, D * curDom, tot >= P['min']
    strong = en and ((oDom >= 0.40 and oppTf >= 3) or (cDir <= 0.05 and oDom >= 0.15 and oppTf >= 3))
    tp = en and ((oDom >= 0.25 and (oppTf >= 3 or mid)) or (cDir <= 0.15 and oDom >= 0.10 and oppTf >= 2))
    weak = en and oDom >= 0.10 and oppTf >= 2
    sup = D * net5 > 0 and D * net15 > 0
    if strong:
        if not st['exit']:
            st['exit'] = True; st['cont'] = False; return 3
        return 2
    if tp or weak:
        return 2
    if sup:
        st['cont'] = True; st['exit'] = False; return 1
    return 2 if st['cont'] else 0


def verifier_events(codes_seq, connected=True):
    """PointMasterVerifierV2 のイベント抽出。codes_seq = [(long_code, short_code)]（None = na）"""
    prevL = prevS = None
    out = []
    for i, (lc, sc) in enumerate(codes_seq):
        def ok(v):
            return v is not None and abs(v - round(v)) < 1e-6 and -1e-6 <= v <= 3 + 1e-6
        if connected and ok(lc) and ok(sc):
            lc, sc = int(round(lc)), int(round(sc))
            if prevL is not None:
                if lc == 1 and prevL != 1: out.append((i, 'L', 'cont'))
                if lc == 3: out.append((i, 'L', 'exit'))
            if prevS is not None:
                if sc == 1 and prevS != 1: out.append((i, 'S', 'cont'))
                if sc == 3: out.append((i, 'S', 'exit'))
            prevL, prevS = lc, sc
        else:
            prevL = prevS = None
    return out


ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print("OK ", name)

# ---- 2. NET の符号が変わっても評価方向・基準が入れ替わらない（B は NET を使わない / A は D 固定）
b = ModeB()
b.bar(1, 100, *mkpts(l5=2, l15=2), newPL=95)
b.bar(2, 101, *mkpts(l5=2, l15=2))          # ここで元版 NET が SHORT に変わっても入力は同じ
check("B LONG episode/basis unaffected by NET sign (no NET input)", b.ep == [True, False] and b.basis[0] == 95)
stL, stS = dict(cont=False, exit=False), dict(cont=False, exit=False)
P = dict(min=2.0)
c1 = mode_a(1, [0]*6, [0]*6, -0.3, 5, 3, stL, P)   # CURRENT DOM は SHORT 側でも 5M/15M NET が LONG
c2 = mode_a(-1, [0]*6, [0]*6, -0.3, 5, 3, stS, P)
check("A evaluates LONG/SHORT independently of total NET sign", c1 == 1 and c2 == 0)

# ---- 3. 根拠ゼロ・拮抗から継続が出ない
b = ModeB()
r = [b.bar(1, 100, *mkpts(), newPL=95), b.bar(2, 100, *mkpts(l5=2, s5=2, l15=2, s15=2)), b.bar(3, 100, *mkpts(l5=3, s5=1, l15=1, s15=0))]
check("zero / tie / below-min never continuation", all(c == [0, 0] for c in r))
check("A: no evidence -> 0 (not HOLD)", mode_a(1, [0]*6, [0]*6, 0.0, 0, 0, dict(cont=False, exit=False), P) == 0)

# ---- 4 / 5. PRE -> 同方向 CURRENT で反転根拠が減らない / 二重加点なし
ev = Evidence()
pre = {(15, 1, 1): 1.0}                       # H&S PRE SHORT（5M）
ev.apply(1, 100, {})
_, i1, _ = points(ev, pre)
pre2 = {}                                     # CURRENT 成立で PRE は消える
ev.apply(1, 99, {15: 'S'}, levels={(15, 1): 101.0})
_, i2, _ = points(ev, pre2)
check("PRE -> CURRENT carry-over keeps evidence (1 -> 1)", i1[(1, 1)] == 1.0 and i2[(1, 1)] == 1.0)
_, i3, _ = points(ev, {(15, 1, 1): 1.0})      # PRE と CURRENT が同時でも max
check("PRE + CURRENT not double counted", i3[(1, 1)] == 1.0)
pre_sat = {(23, 1, 0): 2 / 3}
_, i4, _ = points(Evidence(), pre_sat)
check("SAT fractional PRE strength kept (2/3)", abs(i4[(1, 0)] - 2 / 3) < 1e-9)
ev = Evidence()
ev.apply(1, 100, {15: 'S'}, levels={(15, 1): 101.0})
_, iO, _ = points(ev, {(17, 1, 0): 1.0})      # 反対方向 PRE と CURRENT の同時存在は許容
check("opposite-direction PRE and CURRENT coexist", iO[(1, 0)] == 1.0 and iO[(1, 1)] == 1.0)

# ---- 6. 同じ系統の根拠が増えても系統点は 1 まで
ev = Evidence()
ev.apply(1, 100, {4: 'L', 5: 'L', 6: 'L', 7: 'L', 8: 'L'}, ema=99.0)
c, i, f = points(ev, {})
check("4 EMAs + break in MA family -> 1 point", c[(1, 0)] == 1.0 and f[(1, 0)] == 1)

# ---- 7. 価格否定された根拠は期限内でも解除、元 ST_STATE の残存では復活しない
ev = Evidence(hold=10)
ev.apply(2, 100, {2: 'L'}, levels={(2, 0): 98.0})   # Accum Reb LONG（箱下限 98）
ev.apply(2, 97.5, {})                               # 15M 確定終値が下限割れ → 解除（期限内）
ev.apply(2, 99, {})                                 # 元版 ST_STATE は保持中でも V2 は戻らない
check("price-negated evidence invalid within expiry and not revived", not ev.cur(2, 2, 0) and ev.neg.get((2, 0)) == 1)
ev = Evidence(hold=10)
ev.apply(2, 100, {13: 'L'}, levels={(13, 0): 99.0}, slopes={(13, 0): 0.5})   # TL Break（上向きライン）
ev.apply(2, 99.8, {})                               # ライン 99.5 > 99.8? no -> 有効
ok1 = ev.cur(13, 2, 0)
ev.apply(2, 99.9, {})                               # ライン 100.0 > 99.9 -> 解除
check("sloped line negation uses line value at that TF bar", ok1 and not ev.cur(13, 2, 0))
ev = Evidence(hold=3)
ev.apply(1, 100, {24: 'L'}, hi=101, lo=99)
ev.apply(1, 100, {}); ev.apply(1, 100, {})
ev.apply(1, 100, {})
check("expiry = original hold bars", not ev.cur(24, 1, 0))
ev = Evidence()
ev.apply(1, 100, {20: 'L'}); ev.apply(1, 100, {}, fib_inv=(20,))
ev.apply(1, 100, {})
check("Fib deep-level invalidation inherited, no revival", not ev.cur(20, 1, 0))
ev = Evidence()
ev.apply(1, 100, {0: 'L'})                          # 否定ラインが na → 価格基準なし（未対応）
check("missing price basis -> not counted", not ev.cur(0, 1, 0) and ev.v[(0, 1, 0)]['valid'])

# ---- 8. Pivot 確認前に基準が使われない（確定ピボットが来るまで継続開始しない）
b = ModeB()
r1 = b.bar(1, 100, *mkpts(l5=2, l15=2))
r2 = b.bar(2, 100, *mkpts(l5=2, l15=2), newPL=97)
check("no basis before pivot confirmation; starts on confirmation bar", r1[0] == 0 and r2[0] == 1 and b.basis[0] == 97)

# ---- 9 / 10. 警戒中も基準を維持・緩めない / 突破足の更新で手仕舞いを回避しない
b = ModeB()
b.bar(1, 100, *mkpts(l5=2, l15=2), newPL=97)
b.bar(2, 99, *mkpts(l5=0, l15=2), newPL=95)         # 警戒。より低い安値へは緩めない
check("caution keeps basis, never loosens (LONG)", b.cau[0] and b.basis[0] == 97)
b.bar(3, 101, *mkpts(l5=2, l15=2), newPL=98)        # 復帰確認 1/2、より高い安値へ更新
check("basis moves only to higher low", b.basis[0] == 98)
r = b.bar(4, 97.9, *mkpts(l5=2, l15=2), newPL=97.5)  # 突破足に新ピボット → 先に突破を判定
check("breach checked before same-bar pivot update -> exit", r[0] == 3 and b.basis[0] is None)
b2 = ModeB()
b2.bar(1, 100, *mkpts(l5=2, l15=2), newPL=97)
check("close == basis is not a breach", b2.bar(2, 97, *mkpts(l5=2, l15=2))[0] == 1)

# ---- 11. 復帰の連続条件 / 手仕舞い後の再開 / 同一エピソードで重複なし
b = ModeB()
seq = []
seq.append(b.bar(1, 100, *mkpts(l5=2, l15=2), newPL=97)[0])   # 1 開始
seq.append(b.bar(2, 100, *mkpts(l5=1, l15=2))[0])             # 2 警戒
seq.append(b.bar(3, 100, *mkpts(l5=2, l15=2))[0])             # 2 復帰 1/2
seq.append(b.bar(4, 100, *mkpts(l5=1, l15=2))[0])             # 2 崩れてリセット
seq.append(b.bar(5, 100, *mkpts(l5=2, l15=2))[0])             # 2 復帰 1/2
seq.append(b.bar(6, 100, *mkpts(l5=2, l15=2))[0])             # 1 復帰完了
seq.append(b.bar(7, 96, *mkpts(l5=2, l15=2))[0])              # 3 突破
seq.append(b.bar(8, 95, *mkpts(l5=2, l15=2))[0])              # 0 基準なし（直近ピボット否定済み）
seq.append(b.bar(9, 96, *mkpts(l5=2, l15=2), newPL=94)[0])    # 2 手仕舞い後の再開 1/2
seq.append(b.bar(10, 96, *mkpts(l5=2, l15=2))[0])             # 1 再開
check("recovery 2-in-a-row, reset on break, exit once, restart needs 2 + basis", seq == [1, 2, 2, 2, 2, 1, 3, 0, 2, 1])
check("exit appears on one bar only", seq.count(3) == 1)
b = ModeB()
b.bar(1, 100, *mkpts(l5=2, l15=2), newPL=97)
r = b.bar(2, 100, *mkpts(l5=2, l15=2, s1i=2.0, f1s=2))
check("opposite 1M PRE (2 pts, 2 families) -> caution, not exit", r[0] == 2)
r = b.bar(3, 100, *mkpts(l5=2, l15=2, s5i=1.9, f5s=3))
check("warn needs total >= 2 (family count alone does not round up)", r[0] == 2 and b.rec[0] == 1)
stA = dict(cont=False, exit=False)
aL = [0, 0, 0, 0, 0, 0]; aS = [3, 3, 3, 3, 0, 0]
a1 = mode_a(1, aL, aS, 0.5, 1, 1, stA, P); a2 = mode_a(1, aL, aS, 0.5, 1, 1, stA, P)
a3 = mode_a(1, [0]*6, [0]*6, 0.5, 1, 1, stA, P); a4 = mode_a(1, aL, aS, 0.5, 1, 1, stA, P)
check("A exit not repeated while condition persists; new episode after continuation", [a1, a2, a3, a4] == [3, 2, 1, 3])

# ---- 12. 価格反転入力で対称
import random
random.seed(7)
bl, bs = ModeB(), ModeB()
outL, outS = [], []
M = 4000.0
pl = None
for t in range(1, 600):
    c = round(2000 + 20 * math.sin(t / 15) + random.uniform(-3, 3), 2)
    l5, s5, l15, s15 = (random.randint(0, 3) for _ in range(4))
    w = [random.choice([0, 0, 1.0, 2.0, 2.5]) for _ in range(4)]
    fm = [random.randint(0, 3) for _ in range(4)]
    npl = round(c - random.uniform(0.5, 8), 2) if random.random() < 0.15 else None
    nph = round(c + random.uniform(0.5, 8), 2) if random.random() < 0.15 else None
    outL.append(bl.bar(t, c, *mkpts(l5, s5, l15, s15, w[0], w[1], fm[0], fm[1], w[2], w[3], fm[2], fm[3]), newPL=npl, newPH=nph))
    outS.append(bs.bar(t, M - c, *mkpts(s5, l5, s15, l15, w[1], w[0], fm[1], fm[0], w[3], w[2], fm[3], fm[2]),
                       newPL=None if nph is None else round(M - nph, 2), newPH=None if npl is None else round(M - npl, 2)))
check("mirrored price / swapped evidence -> LONG and SHORT codes swap exactly", all(a == [bb[1], bb[0]] for a, bb in zip(outL, outS)))
check("mirror test exercised all codes", {x for a in outL for x in a} == {0, 1, 2, 3})

# ---- 13. 同じ確定足の再評価で状態・件数が増えない
b = ModeB()
b.bar(1, 100, *mkpts(l5=2, l15=2), newPL=97)
check("same confirmed bar re-evaluation ignored", b.bar(1, 50, *mkpts()) is None and b.ep[0])

# ---- Verifier V2 : イベント抽出（継続 = 1 への切替 / 手仕舞い = 3 / 基準 / 不正 / 未接続）
seq = [(1, 0), (1, 0), (2, 0), (1, 1), (3, 1), (0, 1), (None, 1), (1, 1), (1, 3), (1, 0)]
ev = verifier_events(seq)
check("verifier: baseline not counted, cont on switch to 1, exit on 3, na resets baseline",
      ev == [(3, 'L', 'cont'), (3, 'S', 'cont'), (4, 'L', 'exit'), (8, 'S', 'exit')])
check("verifier: connected checkbox OFF -> no events", verifier_events(seq, connected=False) == [])
check("verifier: out-of-range / non-integer / price input -> no events", verifier_events([(2650.0, 1), (1.5, 1), (4, 1), (1, 1)]) == [])

# ---- データ準備 / 更新整合（§12 の時刻確認のモデル）
def readiness(bars, need=(10, 6, 4)):
    """bars: [(t, ltf_times, tt5, tt15, vals_ok)]。元版方式で期待される直前 TF 区間と受信時刻を照合。"""
    c5 = p5 = c15 = p15 = None
    warm = [0, 0, 0]; last1 = 0; out = []
    for t, lt, tt5, tt15, vok in bars:
        b5, b15 = t - t % 300000, t - t % 900000
        if c5 is None or b5 != c5: p5, c5 = c5, b5
        if c15 is None or b15 != c15: p15, c15 = c15, b15
        new1 = [x for x in lt if x > last1]
        if new1: last1 = new1[-1]
        warm[0] += len(new1)
        warm[1] += 1 if tt5 else 0      # TF 確定足の処理（簡略: 毎 5M 足で 5M / 15M 区間が変わった時）
        if tt15 and (not out or out[-1][1] != tt15): warm[2] += 1
        m1 = not lt; bad1 = any(x < t or x >= t + 300000 for x in lt) or lt != sorted(set(lt)) or (lt and last1 != lt[-1])
        m5, m15 = not tt5 or p5 is None, not tt15 or p15 is None
        bad5, bad15 = (not m5 and tt5 != p5), (not m15 and tt15 != p15)
        bad = bad1 or bad5 or bad15 or not vok
        st = 4 if bad else 1 if (m1 or m5 or m15 or warm[0] < need[0] or warm[1] < need[1] or warm[2] < need[2]) else 0
        if bad1 or m1 or not vok: warm[0] = 0
        if bad5 or m5 or not vok: warm[1] = 0
        if bad15 or m15 or not vok: warm[2] = 0
        out.append((st, tt15))
    return [o[0] for o in out]

M5, M15, M1 = 300000, 900000, 60000
T0 = 1_700_000_100_000 - (1_700_000_100_000 % M15)
def row(t, tt15_override=None, drop1=False, vok=True, tt5=None):
    lt = [t + i * M1 for i in range(5)][: 4 if drop1 else 5]
    b15 = t - t % M15
    return (t, lt, t - M5 if tt5 is None else tt5, b15 - M15 if tt15_override is None else tt15_override, vok)
bars = [row(T0 + i * M5) for i in range(30)]
st = readiness(bars)
check("ready only after 1M/5M/15M warm-up (first bars = 1, later = 0)", st[0] == 1 and st[-1] == 0)
# 週末ギャップ：直前に足が存在した区間と比べるので不整合にしない
gap = T0 + 30 * M5 + 2 * 24 * 3600 * 1000
last_pre = T0 + 29 * M5
bars2 = bars + [(gap, [gap + i * M1 for i in range(5)], last_pre, last_pre - last_pre % M15, True)] + [row(gap + i * M5, tt15_override=(last_pre - last_pre % M15) if i < 3 else None) for i in range(1, 4)]
st2 = readiness(bars2)
check("weekend gap with expected previous TF bars -> stays ready", st2[30:] == [0, 0, 0, 0])
# 15M が遅れて古い確定足のまま → 不整合
bars3 = bars[:20] + [row(T0 + 20 * M5, tt15_override=T0 + 20 * M5 - (T0 + 20 * M5) % M15 - 2 * M15)] + bars[21:]
st3 = readiness(bars3)
check("stale 15M bar time -> 4 (not ready), then re-warm", st3[20] == 4 and st3[21] == 1)
check("missing last 1-minute bar tolerated, invalid value -> 4", readiness(bars[:25] + [row(T0 + 25 * M5, drop1=True)])[-1] == 0 and readiness(bars[:25] + [row(T0 + 25 * M5, vok=False)])[-1] == 4)
print(f"{ok} checks passed (model only; not a Pine run)")

# ---- 関数化・式化（スコープ削減版）が前版の if 版と同じ遷移になるか（ランダム比較）
def bstep_expr(st, di, close, curT, intT, famT, newPL, newPH, lastPL, lastPLneg, lastPH, lastPHneg, P=(2.0, 2.0, 2, 2)):
    """PointMasterFvgAbsReboundV2.pine f_v2BStep の式版をそのまま写したもの。st = dict(ep, cau, after, rec, basis, bstat)"""
    min_pts, warn_pts, warn_fams, N = P
    D = 1 if di == 0 else -1; od = 1 - di
    own5, opp5, own15, opp15 = curT[(1, di)], curT[(1, od)], curT[(2, di)], curT[(2, od)]
    c5 = own5 >= min_pts and own5 > opp5
    c15 = own15 >= min_pts and own15 > opp15
    warn = (intT[(0, od)] >= warn_pts and famT[(0, od)] >= warn_fams) or (intT[(1, od)] >= warn_pts and famT[(1, od)] >= warn_fams)
    ep, cau, after, rec, basis, bstat = st['ep'], st['cau'], st['after'], st['rec'], st['basis'], st['bstat']
    lt = lambda a, b: a is not None and b is not None and a < b
    breach = ep and basis is not None and (lt(close, basis) if D == 1 else lt(basis, close))
    basisUp = (newPL if (newPL is not None and close > newPL and lt(basis, newPL)) else basis) if D == 1 else (newPH if (newPH is not None and close < newPH and lt(newPH, basis)) else basis)
    lastP = (newPL if newPL is not None else lastPL) if D == 1 else (newPH if newPH is not None else lastPH)
    lastNeg = (False if newPL is not None else lastPLneg) if D == 1 else (False if newPH is not None else lastPHneg)
    startOk = lastP is not None and not lastNeg and (lastP < close if D == 1 else lastP > close)
    cand = c5 and c15 and (ep or startOk) and not warn
    rc = rec + 1
    inEp = ep and not breach
    startNow = (not ep) and cand and ((not after) or rc >= N)
    code = 3 if breach else ((1 if (not cau or rc >= N) else 2) if cand else 2) if inEp else ((1 if startNow else 2) if cand else (2 if warn else 0))
    epN = False if breach else True if inEp else startNow
    cauN = False if breach else ((cau and rc < N) if cand else True) if inEp else False
    afterN = True if breach else False if startNow else after
    recN = 0 if breach else (((0 if rc >= N else rc) if cau else rec) if cand else 0) if inEp else ((0 if startNow else rc) if cand else 0)
    basisN = None if breach else basisUp if inEp else lastP if startNow else basis
    bstatN = 2 if breach else 1 if startNow else (0 if (not epN and bstat == 1) else bstat)
    st.update(ep=epN, cau=cauN, after=afterN, rec=recN, basis=basisN, bstat=bstatN)
    return code

random.seed(11)
bif = ModeB(); sts = [dict(ep=False, cau=False, after=False, rec=0, basis=None, bstat=0) for _ in (0, 1)]
lpl = lph = None; lpln = lphn = False
same = True
for t in range(1, 3000):
    c = round(2000 + 25 * math.sin(t / 20) + random.uniform(-4, 4), 2)
    pts = mkpts(*(random.randint(0, 3) for _ in range(4)), *(random.choice([0, 1.0, 2.0, 2.5]) for _ in range(2)), *(random.randint(0, 3) for _ in range(2)),
                *(random.choice([0, 1.0, 2.0, 2.5]) for _ in range(2)), *(random.randint(0, 3) for _ in range(2)))
    npl = round(c - random.uniform(0.5, 8), 2) if random.random() < 0.15 else None
    nph = round(c + random.uniform(0.5, 8), 2) if random.random() < 0.15 else None
    # 呼び出し側（Pine の確定足ブロック）と同じ順：直近ピボットの否定 → 判定 → 新ピボット記録
    lpln = lpln or (lpl is not None and c < lpl); lphn = lphn or (lph is not None and c > lph)
    e = [bstep_expr(sts[di], di, c, *pts, npl, nph, lpl, lpln, lph, lphn) for di in (0, 1)]
    lpln = lpln if npl is None else c < npl; lpl = lpl if npl is None else npl
    lphn = lphn if nph is None else c > nph; lph = lph if nph is None else nph
    r = bif.bar(t, c, *pts, newPL=npl, newPH=nph)
    same = same and r == e and all(sts[di]['ep'] == bif.ep[di] and sts[di]['basis'] == bif.basis[di] and sts[di]['rec'] == bif.rec[di] for di in (0, 1))
check("B expression form (f_v2BStep) == previous if form on 3000 random bars", same)

def apply_expr(v, ti, close, sigs, levels=None, slopes=None, ema=None, hi=None, lo=None, fib_inv=(), hold=6):
    """f_v2ApplyTf の式版（ロジック × 方向を index で分離）"""
    levels, slopes = levels or {}, slopes or {}
    for li in range(N_LOGIC):
        rule = RULE[li]; isSt = rule == 3
        sig = sigs.get(li); sigL, sigS = sig == 'L', sig == 'S'
        fibInv = li in (20, 21, 22) and li in fib_inv
        for d in (0, 1):
            e = v.setdefault((li, ti, d), dict(valid=False, price=False, rem=0, age=0, lvl=None, slp=0.0))
            reg, opp = (sigL, sigS) if d == 0 else (sigS, sigL)
            aging = e['valid'] and not isSt
            age1 = e['age'] + (1 if aging else 0); rem1 = e['rem'] - (1 if aging else 0)
            lv = ema if rule == 1 else (None if e['lvl'] is None else e['lvl'] + e['slp'] * age1)
            negd = aging and rem1 > 0 and rule != 2 and e['price'] and lv is not None and ((d == 0 and close < lv) or (d == 1 and close > lv))
            alive = e['valid'] and rem1 > 0 and not negd
            lvN = (lo if d == 0 else hi) if rule == 4 else levels.get((li, d))
            pOk = rule == 2 or (ema is not None if rule == 1 else lvN is not None)
            regNew = reg and not isSt
            e.update(valid=(reg if isSt else (True if reg else False if opp else alive)) and not fibInv,
                     price=True if isSt else pOk if regNew else e['price'], rem=hold if regNew else rem1, age=0 if regNew else age1,
                     lvl=lvN if regNew else e['lvl'], slp=slopes.get((li, d), 0.0) if regNew else e['slp'])

random.seed(5)
evA = Evidence(hold=6); vB = {}
same = True
for t in range(1500):
    c = 100 + random.uniform(-5, 5)
    sigs = {li: random.choice('LS') for li in random.sample(range(N_LOGIC), 3)}
    lv = {(li, 0 if s == 'L' else 1): c + (random.uniform(-3, 0) if s == 'L' else random.uniform(0, 3)) for li, s in sigs.items() if RULE[li] == 0 and random.random() < 0.9}
    sl = {k: random.uniform(-0.3, 0.3) for k in lv}
    ema = c + random.uniform(-2, 2)
    fi = tuple(li for li in (20, 21, 22) if random.random() < 0.05)
    evA.apply(1, c, sigs, lv, sl, ema, c + 1, c - 1, fi)
    apply_expr(vB, 1, c, sigs, lv, sl, ema, c + 1, c - 1, fi)
    same = same and all(evA.cur(li, 1, d) == (vB[(li, 1, d)]['valid'] and vB[(li, 1, d)]['price']) for li in range(N_LOGIC) for d in (0, 1))
check("evidence expression form (f_v2ApplyTf) == previous if form on 1500 random TF bars", same)
print(f"{ok} checks passed after refactor comparison (model only; not a Pine run)")
