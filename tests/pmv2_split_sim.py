"""V2-B 分割版（Source A/B/C → BUS → Decision）の Python モデル確認。Pine 上の実行確認ではない。
  1. 分割前（25 ロジックを 1 本で集計する f_v2BPoints）と分割後（Source ごとの系統点 → BUS → Decision の統合）で
     確認済み点・統合点・寄与系統数・価格否定・価格基準なしが一致するか（ランダム状態）
  2. 同じ入力系列で B の判定コード・基準が一致するか
  3. BUS の全フィールド境界・最大値・時刻範囲・na・取り違え
  4. 価格帯（A の Logic01〜04 と C の Logic19〜20）は最大値で統合され、二重加点・二重カウントしないか
"""
import math
import random
import sys

sys.path.insert(0, 'tests')
from pmv2_sim import ModeB  # noqa: E402  分割前の B 状態遷移モデル（同じものを Decision も使う）

N_TF = 3
BASE = 1577836800000
SLOTS = 2 ** 22
BUS_MAX = 2 ** 49

# 25 ロジックの所属（分割前の番号 0〜24）
def fam_old(li):
    return 0 if li <= 3 or li in (18, 19) else 1 if li <= 11 else 2 if li <= 17 else 3 if li <= 22 else 4 if li == 23 else 5

SRC_OF = {**{li: ('A', li) for li in range(12)}, **{li: ('B', li - 12) for li in range(12, 18)}, **{li: ('C', li - 18) for li in range(18, 25)}}


def old_points(st):
    """分割前 f_v2BPoints（1M/5M/15M 分）。st[(li, ti, d)] = (valid, price, pre)"""
    bcur, bint = {}, {}
    neg = {}
    unp = False
    for (li, ti, d), (vld, pr, pre) in st.items():
        cv = vld and pr
        key = (fam_old(li), ti, d)
        if cv:
            bcur[key] = 1.0
        bint[key] = max(bint.get(key, 0.0), max(1.0 if cv else 0.0, pre))
        unp = unp or (vld and not pr)
    curT, intT, famT = [], [], []
    for x in range(6):
        ti, d = x // 2, x % 2
        sc = 0.0
        si = 0.0
        for f in range(6):          # Pine と同じ単純な += （Python の sum() は補正付き加算なので使わない）
            sc += bcur.get((f, ti, d), 0.0)
            si += bint.get((f, ti, d), 0.0)
        curT.append(sc)
        intT.append(si)
        famT.append(sum(1 for f in range(6) if bint.get((f, ti, d), 0.0) > 0))
    return curT, intT, famT, unp


# ---- Source 側（Pine の f_famPts / f_fam1 / f_satBits / f_payload / f_bus を写したもの）----
def fam_pts(st, src, ti, l0, l1):
    cL = cS = False; iL = iS = 0.0
    for gli, (s, li) in SRC_OF.items():
        if s != src or not (l0 <= li <= l1):
            continue
        vL = st[(gli, ti, 0)][0] and st[(gli, ti, 0)][1]
        vS = st[(gli, ti, 1)][0] and st[(gli, ti, 1)][1]
        cL = cL or vL; cS = cS or vS
        iL = max(iL, max(1.0 if vL else 0.0, st[(gli, ti, 0)][2]))
        iS = max(iS, max(1.0 if vS else 0.0, st[(gli, ti, 1)][2]))
    return int(cL), int(round(iL * 3)), int(cS), int(round(iS * 3))


def fam1(st, src, ti, l0, l1, off):
    cL, qL, cS, qS = fam_pts(st, src, ti, l0, l1)
    return (cL + 2 * (1 if qL >= 3 else 0) + 4 * cS + 8 * (1 if qS >= 3 else 0)) * 2 ** off


def payload(st, src, ti, negs):
    unp = any(st[(g, ti, d)][0] and not st[(g, ti, d)][1] for g, (s, _) in SRC_OF.items() if s == src for d in (0, 1))
    base = (1 if negs.get((src, ti, 0)) else 0) + (2 if negs.get((src, ti, 1)) else 0) + (4 if unp else 0)
    if src == 'A':
        return base + fam1(st, 'A', ti, 0, 3, 3) + fam1(st, 'A', ti, 4, 11, 7)
    if src == 'B':
        return base + fam1(st, 'B', ti, 0, 5, 3)
    cL, qL, cS, qS = fam_pts(st, 'C', ti, 5, 5)
    sat = (cL + 2 * qL + 8 * cS + 16 * qS) * 2 ** 11
    return base + fam1(st, 'C', ti, 0, 1, 3) + fam1(st, 'C', ti, 2, 4, 7) + sat + fam1(st, 'C', ti, 6, 6, 17)


def bus(sid, tf, pay, tclose):
    slot = (tclose - BASE) / 300000.0
    ok = slot >= 0 and slot < SLOTS and slot == math.floor(slot) and 0 <= pay < 2097152
    return 1 + 4 * sid + 16 * tf + 64 * slot + 268435456.0 * pay if ok else None


# ---- Decision 側（f_dec / f_merge）----
def dec(v, sid, tf, paymax, tclose):
    slotf = (tclose - BASE) / 300000.0
    slot_ok = 0 <= slotf < SLOTS and slotf == math.floor(slotf)
    if v is None:
        return 1, None
    num = v >= 0 and v < BUS_MAX and v == math.floor(v)
    if not num:
        return 5, None
    fmt, s, t = v % 4, math.floor(v / 4) % 4, math.floor(v / 16) % 4
    sl, pay = math.floor(v / 64) % SLOTS, math.floor(v / 268435456.0)
    if fmt != 1 or s != sid or t != tf or pay >= paymax:
        return 5, None
    if not slot_ok or sl != slotf:
        return 4, None
    return 0, pay


def bit(p, b):
    return math.floor(p / 2 ** b) % 2


def merge(pa, pb, pc):
    curT, intT, famT, negs = [], [], [], []
    unp = False
    for x in range(6):
        ti, d = x // 2, x % 2
        o = d * 2
        a, b, c = pa[ti], pb[ti], pc[ti]
        cP = max(bit(a, 3 + o), bit(c, 3 + o)); iP = max(bit(a, 4 + o), bit(c, 4 + o))
        cM, iM = bit(a, 7 + o), bit(a, 8 + o)
        cG, iG = bit(b, 3 + o), bit(b, 4 + o)
        cF, iF = bit(c, 7 + o), bit(c, 8 + o)
        cS = bit(c, 11 + d * 3); iS = (math.floor(c / 2 ** (12 + d * 3)) % 4) / 3.0
        cK, iK = bit(c, 17 + o), bit(c, 18 + o)
        curT.append(float(cP + cM + cG + cF + cS + cK))
        intT.append(iP + iM + iG + iF + iS + iK)
        famT.append(sum(1 for v in (iP, iM, iG, iF, iS, iK) if v > 0))
        negs.append(1 if bit(a, d) + bit(b, d) + bit(c, d) > 0 else 0)
        unp = unp or bit(a, 2) + bit(b, 2) + bit(c, 2) > 0
    return curT, intT, famT, negs, unp


def rand_state(rng):
    st = {}
    for li in range(25):
        for ti in range(3):
            for d in (0, 1):
                vld = rng.random() < 0.3
                pr = rng.random() < 0.9
                if li == 23:                       # SAT : 状態型（price 常に true）/ PRE 0, 1/3, 2/3
                    pr = True
                    pre = rng.choice([0.0, 0.0, 1 / 3.0, 2 / 3.0])
                elif li in (14, 15, 16, 17, 20, 21, 22, 24):   # PRE 対象（Logic15〜18 / 21〜23 / 25）
                    pre = rng.choice([0.0, 0.0, 1.0])
                else:
                    pre = 0.0
                if li in (20, 21, 22):            # Fib は価格基準を持たない（rule 2 = price true）
                    pr = True
                st[(li, ti, d)] = (vld, pr, pre)
    return st


ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)


# ---- 1 / 2. 分割前 = 分割後（点数・統合・系統数・否定・未対応）と B 判定
rng = random.Random(3)
t0 = BASE + 300000 * 500000
same_pts = True
bo, bn = ModeB(), ModeB()
codes_same = True
for i in range(4000):
    st = rand_state(rng)
    negs = {(s, ti, d): rng.random() < 0.1 for s in 'ABC' for ti in range(3) for d in (0, 1)}
    tclose = t0 + 300000 * (i + 1)
    oc, oi, of_, ou = old_points(st)
    on = [1 if any(negs[(s, ti, d)] for s in 'ABC') else 0 for ti in range(3) for d in (0, 1)]
    ps = {}
    for s, sid, mx in (('A', 1, 2048), ('B', 2, 128), ('C', 3, 2097152)):
        for tf in range(3):
            v = bus(sid, tf, payload(st, s, tf, negs), tclose)
            stc, pay = dec(v, sid, tf, mx, tclose)
            assert stc == 0
            ps[(s, tf)] = pay
    nc, ni, nf, nn, nu = merge([ps[('A', t)] for t in range(3)], [ps[('B', t)] for t in range(3)], [ps[('C', t)] for t in range(3)])
    same_pts = same_pts and oc == nc and oi == ni and of_ == nf and on == nn and ou == nu
    # B 判定（1M/5M/15M のみ使う。背景 TF は 0）
    def pts(c, it, f):
        curT = {(ti, d): (c[ti * 2 + d] if ti < 3 else 0.0) for ti in range(6) for d in (0, 1)}
        intT = {(ti, d): (it[ti * 2 + d] if ti < 3 else 0.0) for ti in range(6) for d in (0, 1)}
        famT = {(ti, d): (f[ti * 2 + d] if ti < 3 else 0) for ti in range(6) for d in (0, 1)}
        return curT, intT, famT
    c = round(2000 + 20 * math.sin(i / 30) + rng.uniform(-3, 3), 2)
    npl = round(c - rng.uniform(0.5, 6), 2) if rng.random() < 0.15 else None
    nph = round(c + rng.uniform(0.5, 6), 2) if rng.random() < 0.15 else None
    r1 = bo.bar(i + 1, c, *pts(oc, oi, of_), newPL=npl, newPH=nph)
    r2 = bn.bar(i + 1, c, *pts(nc, ni, nf), newPL=npl, newPH=nph)
    codes_same = codes_same and r1 == r2 and bo.basis == bn.basis
check('pre-split points == Source->BUS->Decision points on 4000 random states (cur / int / families / neg / unpriced)', same_pts)
check('B codes and basis identical for the same input series (4000 bars)', codes_same)

# ---- 3. BUS の境界・最大値・時刻範囲・na・取り違え
lo_t = BASE                     # slot 0
hi_t = BASE + 300000 * (SLOTS - 1)
for sid, mx in ((1, 2047), (2, 127), (3, 2097151)):
    for tf in range(3):
        for t in (lo_t, hi_t):
            for pay in (0, mx):
                v = bus(sid, tf, pay, t)
                assert v is not None and v < BUS_MAX and v <= 2 ** 53 - 1 and v == math.floor(v)
                assert dec(v, sid, tf, mx + 1, t) == (0, pay)
check('all fields reversible at boundaries (slot 0 / max, payload 0 / max, every Source / TF)', True)
check('max BUS value < 2^49 <= 2^53 - 1', bus(3, 2, 2097151, hi_t) < 2 ** 49)
check('time before base / after 2^22 slots -> not encoded (na), not wrapped', bus(1, 0, 0, BASE - 300000) is None and bus(1, 0, 0, BASE + 300000 * SLOTS) is None)
v = bus(1, 1, 5, t0)
check('na input -> status 1', dec(None, 1, 1, 2048, t0)[0] == 1)
check('Source mix-up -> 5', dec(v, 2, 1, 128, t0)[0] == 5)
check('TF mix-up -> 5', dec(v, 1, 2, 2048, t0)[0] == 5)
check('old 5m bar time -> 4', dec(v, 1, 1, 2048, t0 + 300000)[0] == 4)
check('price input (unconnected default close) -> 5', dec(2650.12, 1, 0, 2048, t0)[0] == 5 and dec(2650.0, 1, 0, 2048, t0)[0] == 5)
check('payload out of range for the Source -> 5', dec(bus(3, 0, 4096, t0), 1, 0, 2048, t0)[0] == 5)
check('negative / >= 2^49 -> 5', dec(-5.0, 1, 0, 2048, t0)[0] == 5 and dec(float(2 ** 49), 1, 0, 2048, t0)[0] == 5)

# ---- 4. 価格帯 A / C は最大値（二重加点・二重カウントなし）
st = {(li, ti, d): (False, True, 0.0) for li in range(25) for ti in range(3) for d in (0, 1)}
st[(0, 1, 0)] = (True, True, 0.0)      # A : Logic01 LONG 5M
st[(18, 1, 0)] = (True, True, 0.0)     # C : Logic19 LONG 5M
pa = [payload(st, 'A', t, {}) for t in range(3)]
pb = [payload(st, 'B', t, {}) for t in range(3)]
pc = [payload(st, 'C', t, {}) for t in range(3)]
c_, i_, f_, _, _ = merge(pa, pb, pc)
check('price-band A + C on same TF/direction -> 1 point, 1 family (not 2)', c_[2] == 1.0 and i_[2] == 1.0 and f_[2] == 1)
st[(23, 1, 0)] = (False, True, 1 / 3.0)
c_, i_, f_, _, _ = merge(pa, pb, [payload(st, 'C', t, {}) for t in range(3)])
check('SAT 1/3 kept as 1/3 (not rounded up), counted as a family', abs(i_[2] - (1 + 1 / 3.0)) < 1e-12 and f_[2] == 2 and c_[2] == 1.0)
print(f'{ok} checks passed (model only; not a Pine run)')
