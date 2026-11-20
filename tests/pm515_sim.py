"""B 5分・15分専用版（PM-A/B/C-515 → PM-DEC-515）の Python モデル確認。Pine 上の実行確認ではない。
  - PM-DEC-515 の f_v2BStep（内部 index 0 = 5M / 1 = 15M、5M の逆方向警戒のみ）を式のまま写し、
    1 分足あり版の B（tests/pmv2_sim.py の ModeB）と比較する
  - BUS : format 2 のみ受理、旧 format 1 / Source・TF 取り違え / 古い時刻 / na / 未接続 を無効
"""
import io
import contextlib
import math
import random
import sys

sys.path.insert(0, 'tests')
with contextlib.redirect_stdout(io.StringIO()):
    from pmv2_sim import ModeB, mkpts            # 1 分足あり版の B（基準）
    import pmv2_split_sim as SP                   # BUS / payload / merge（1 分足あり版）

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)


class ModeB515:
    """PM-DEC-515 の f_v2BStep を写したもの（2 枠: cur[(0|1, d)] 0 = 5M / 1 = 15M）"""
    def __init__(self, P=(2.0, 2.0, 2, 2)):
        self.P = P
        self.st = [dict(ep=False, cau=False, after=False, rec=0, basis=None, bstat=0) for _ in (0, 1)]
        self.lpl = self.lph = None
        self.lpln = self.lphn = False
        self.last_t = None

    def bar(self, t, close, cur, int_, fam, newPL=None, newPH=None):
        if self.last_t is not None and t <= self.last_t:
            return None
        self.last_t = t
        self.lpln = self.lpln or (self.lpl is not None and close < self.lpl)
        self.lphn = self.lphn or (self.lph is not None and close > self.lph)
        out = [self.step(di, close, cur, int_, fam, newPL, newPH) for di in (0, 1)]
        self.lpln = self.lpln if newPL is None else close < newPL
        self.lpl = self.lpl if newPL is None else newPL
        self.lphn = self.lphn if newPH is None else close > newPH
        self.lph = self.lph if newPH is None else newPH
        return out

    def step(self, di, close, cur, int_, fam, newPL, newPH):
        min_pts, warn_pts, warn_fams, N = self.P
        st = self.st[di]
        D = 1 if di == 0 else -1
        od = 1 - di
        own5, opp5, own15, opp15 = cur[(0, di)], cur[(0, od)], cur[(1, di)], cur[(1, od)]
        c5 = own5 >= min_pts and own5 > opp5
        c15 = own15 >= min_pts and own15 > opp15
        warn = int_[(0, od)] >= warn_pts and fam[(0, od)] >= warn_fams          # 5M の逆方向警戒のみ
        ep, cau, after, rec, basis, bstat = st['ep'], st['cau'], st['after'], st['rec'], st['basis'], st['bstat']
        lt = lambda a, b: a is not None and b is not None and a < b
        breach = ep and basis is not None and (lt(close, basis) if D == 1 else lt(basis, close))
        basisUp = (newPL if (newPL is not None and close > newPL and lt(basis, newPL)) else basis) if D == 1 else (newPH if (newPH is not None and close < newPH and lt(newPH, basis)) else basis)
        lastP = (newPL if newPL is not None else self.lpl) if D == 1 else (newPH if newPH is not None else self.lph)
        lastNeg = (False if newPL is not None else self.lpln) if D == 1 else (False if newPH is not None else self.lphn)
        startOk = lastP is not None and not lastNeg and (lastP < close if D == 1 else lastP > close)
        cand = c5 and c15 and (ep or startOk) and not warn
        rc = rec + 1
        inEp = ep and not breach
        startNow = (not ep) and cand and ((not after) or rc >= N)
        code = 3 if breach else ((1 if (not cau or rc >= N) else 2) if cand else 2) if inEp else ((1 if startNow else 2) if cand else (2 if warn else 0))
        epN = False if breach else True if inEp else startNow
        st.update(ep=epN,
                  cau=False if breach else ((cau and rc < N) if cand else True) if inEp else False,
                  after=True if breach else False if startNow else after,
                  rec=0 if breach else (((0 if rc >= N else rc) if cau else rec) if cand else 0) if inEp else ((0 if startNow else rc) if cand else 0),
                  basis=None if breach else basisUp if inEp else lastP if startNow else basis,
                  bstat=2 if breach else 1 if startNow else (0 if (not epN and bstat == 1) else bstat))
        return code


def rand_inputs(rng, warn1):
    """1 分足あり版用の 6 枠入力と、5M15M 版用の 2 枠入力（5M / 15M は同じ値）"""
    l5, s5, l15, s15 = (rng.randint(0, 3) for _ in range(4))
    w5 = [rng.choice([0, 1.0, 2.0, 2.5]) for _ in range(2)]
    f5 = [rng.randint(0, 3) for _ in range(2)]
    w1 = [rng.choice([0, 1.0, 2.0, 2.5]) for _ in range(2)] if warn1 else [0, 0]
    f1 = [rng.randint(0, 3) for _ in range(2)] if warn1 else [0, 0]
    old = mkpts(l5, s5, l15, s15, w1[0], w1[1], f1[0], f1[1], w5[0], w5[1], f5[0], f5[1])
    cur = {(0, 0): float(l5), (0, 1): float(s5), (1, 0): float(l15), (1, 1): float(s15)}
    int_ = {(0, 0): w5[0], (0, 1): w5[1], (1, 0): 0.0, (1, 1): 0.0}
    fam = {(0, 0): f5[0], (0, 1): f5[1], (1, 0): 0, (1, 1): 0}
    return old, (cur, int_, fam)


def run_pair(seed, warn1, n=3000):
    rng = random.Random(seed)
    bo, bn = ModeB(), ModeB515()
    res = []
    for t in range(1, n):
        c = round(2000 + 25 * math.sin(t / 20) + rng.uniform(-4, 4), 2)
        old, new = rand_inputs(rng, warn1)
        npl = round(c - rng.uniform(0.5, 8), 2) if rng.random() < 0.15 else None
        nph = round(c + rng.uniform(0.5, 8), 2) if rng.random() < 0.15 else None
        r1 = bo.bar(t, c, *old, newPL=npl, newPH=nph)
        r2 = bn.bar(t, c, *new, newPL=npl, newPH=nph)
        res.append((r1, r2, list(bo.basis), [s['basis'] for s in bn.st], old, new))
    return res


# 9. 1 分の逆方向警戒が常に不成立なら、同じ開始状態・同じ 5M / 15M 入力で状態遷移が一致
res = run_pair(1, warn1=False)
check('no 1M warning ever -> identical codes and basis as the 1M version (3000 bars)', all(a == b and ba == bb for a, b, ba, bb, _, _ in res))

# 7. 1 分の逆方向警戒だけが成立するケースでは、新版の継続はそれを理由に妨げられない
b_old, b_new = ModeB(), ModeB515()
base_new = ({(0, 0): 2.0, (0, 1): 0.0, (1, 0): 2.0, (1, 1): 0.0}, {(0, 0): 0.0, (0, 1): 0.0, (1, 0): 0.0, (1, 1): 0.0}, {k: 0 for k in [(0, 0), (0, 1), (1, 0), (1, 1)]})
r_old = b_old.bar(1, 100, *mkpts(l5=2, l15=2, s1i=2.0, f1s=2), newPL=97)    # 1M の逆方向（SHORT）警戒だけ成立
r_new = b_new.bar(1, 100, *base_new, newPL=97)
check('1M-only opposite warning: old = caution (2), new = continuation (1)', r_old[0] == 2 and r_new[0] == 1)

# 8. 5M の逆方向警戒・価格による基準突破・復帰・再開・重複防止は機能する
b = ModeB515()
z = {(0, 0): 0.0, (0, 1): 0.0, (1, 0): 0.0, (1, 1): 0.0}
zf = {k: 0 for k in z}
def P(l5, l15, s5i=0.0, f5s=0):
    return ({(0, 0): float(l5), (0, 1): 0.0, (1, 0): float(l15), (1, 1): 0.0}, {(0, 0): 0.0, (0, 1): s5i, (1, 0): 0.0, (1, 1): 0.0}, {(0, 0): 0, (0, 1): f5s, (1, 0): 0, (1, 1): 0})
seq = [b.bar(1, 100, *P(2, 2), newPL=97)[0],             # 1 開始（基準 97）
       b.bar(2, 100, *P(2, 2, 2.0, 2))[0],               # 2 5M 逆方向警戒
       b.bar(3, 100, *P(2, 2))[0],                       # 2 復帰 1/2
       b.bar(4, 100, *P(2, 2))[0],                       # 1 復帰完了
       b.bar(5, 96, *P(2, 2))[0],                        # 3 基準突破
       b.bar(6, 95, *P(2, 2))[0],                        # 0 基準なし
       b.bar(7, 96, *P(2, 2), newPL=94)[0],              # 2 再開 1/2
       b.bar(8, 96, *P(2, 2))[0]]                        # 1 再開
check('5M warning / breach / recovery / restart / exit once', seq == [1, 2, 2, 1, 3, 0, 2, 1] and seq.count(3) == 1)
check('5M warning needs total >= 2 and families >= 2', ModeB515().bar(1, 100, *P(2, 2, 1.9, 3), newPL=97)[0] == 1)
b = ModeB515()
b.bar(1, 100, *P(2, 2), newPL=97)
check('same confirmed bar is not re-evaluated', b.bar(1, 50, *P(0, 0)) is None and b.st[0]['ep'])
b = ModeB515()
b.bar(1, 100, *P(2, 2), newPL=97)
b.bar(2, 99, *P(1, 2), newPL=95)
check('caution keeps basis and never loosens', b.st[0]['basis'] == 97)
r = b.bar(3, 96.9, *P(2, 2), newPL=96.5)
check('breach is checked before a same-bar pivot update', r[0] == 3)

# 10. LONG / SHORT 対称
rng = random.Random(9)
bl, bs = ModeB515(), ModeB515()
sym = True
codes = set()
for t in range(1, 1500):
    c = round(2000 + 20 * math.sin(t / 15) + rng.uniform(-3, 3), 2)
    v = [rng.randint(0, 3) for _ in range(4)]
    w = [rng.choice([0, 1.0, 2.0, 2.5]) for _ in range(2)]
    f = [rng.randint(0, 3) for _ in range(2)]
    npl = round(c - rng.uniform(0.5, 8), 2) if rng.random() < 0.15 else None
    nph = round(c + rng.uniform(0.5, 8), 2) if rng.random() < 0.15 else None
    A = ({(0, 0): v[0], (0, 1): v[1], (1, 0): v[2], (1, 1): v[3]}, {(0, 0): w[0], (0, 1): w[1], (1, 0): 0, (1, 1): 0}, {(0, 0): f[0], (0, 1): f[1], (1, 0): 0, (1, 1): 0})
    Bm = ({(0, 0): v[1], (0, 1): v[0], (1, 0): v[3], (1, 1): v[2]}, {(0, 0): w[1], (0, 1): w[0], (1, 0): 0, (1, 1): 0}, {(0, 0): f[1], (0, 1): f[0], (1, 0): 0, (1, 1): 0})
    ra = bl.bar(t, c, *A, newPL=npl, newPH=nph)
    rb = bs.bar(t, 4000 - c, *Bm, newPL=None if nph is None else round(4000 - nph, 2), newPH=None if npl is None else round(4000 - npl, 2))
    sym = sym and ra == [rb[1], rb[0]]
    codes |= set(ra)
check('LONG / SHORT symmetric on mirrored prices (all codes exercised)', sym and codes == {0, 1, 2, 3})

# 6 / BUS. 同じ 5M / 15M の系統点は 1 分足あり版の対応 TF と同じ payload。BUS は format だけが 1 → 2
def bus515(sid, tf, pay, tclose):
    v = SP.bus(sid, tf, pay, tclose)
    return None if v is None else v + 1          # format 1 → 2（他のフィールドは同一）

def dec515(v, sid, tf, paymax, tclose):
    """PM-DEC-515 の f_dec（format 2 のみ）"""
    slotf = (tclose - SP.BASE) / 300000.0
    slot_ok = 0 <= slotf < SP.SLOTS and slotf == math.floor(slotf)
    if v is None:
        return 1, None
    if not (v >= 0 and v < SP.BUS_MAX and v == math.floor(v)):
        return 5, None
    fmt, s, t = v % 4, math.floor(v / 4) % 4, math.floor(v / 16) % 4
    sl, pay = math.floor(v / 64) % SP.SLOTS, math.floor(v / 268435456.0)
    if fmt != 2 or s != sid or t != tf or pay >= paymax:
        return 5, None
    if not slot_ok or sl != slotf:
        return 4, None
    return 0, pay

rng = random.Random(4)
t0 = SP.BASE + 300000 * 600000
same = True
for i in range(2000):
    st = SP.rand_state(rng)
    negs = {(s, ti, d): rng.random() < 0.1 for s in 'ABC' for ti in range(3) for d in (0, 1)}
    tc = t0 + 300000 * (i + 1)
    ps_old, ps_new = {}, {}
    for s, sid, mx in (('A', 1, 2048), ('B', 2, 128), ('C', 3, 2097152)):
        for tf in (1, 2):
            pay = SP.payload(st, s, tf, negs)
            ps_old[(s, tf)] = SP.dec(SP.bus(sid, tf, pay, tc), sid, tf, mx, tc)[1]
            st_new, ps_new[(s, tf)] = dec515(bus515(sid, tf, pay, tc), sid, tf, mx, tc)
            same = same and st_new == 0
    oc, oi, of_, on, ou = SP.merge([0] + [ps_old[('A', t)] for t in (1, 2)], [0] + [ps_old[('B', t)] for t in (1, 2)], [0] + [ps_old[('C', t)] for t in (1, 2)])
    # 5M15M の f_merge（2 枠）= 1 分足あり版の TF 1 / 2 と同じ計算
    nc, ni, nf, nn, nu = SP.merge([ps_new[('A', t)] for t in (1, 2)] + [0], [ps_new[('B', t)] for t in (1, 2)] + [0], [ps_new[('C', t)] for t in (1, 2)] + [0])
    same = same and oc[2:6] == nc[0:4] and oi[2:6] == ni[0:4] and of_[2:6] == nf[0:4] and on[2:6] == nn[0:4]
check('same 5M / 15M state -> same family points / neg flags as the 1M version (2000 random states)', same)
v_old = SP.bus(1, 1, 5, t0)
v_new = bus515(1, 1, 5, t0)
check('old format-1 BUS (1M version Source) is rejected', dec515(v_old, 1, 1, 2048, t0)[0] == 5)
check('format-2 BUS accepted', dec515(v_new, 1, 1, 2048, t0) == (0, 5))
check('Source ID / TF ID mix-up rejected', dec515(v_new, 2, 1, 128, t0)[0] == 5 and dec515(v_new, 1, 2, 2048, t0)[0] == 5)
check('old 5m time -> 4 / na -> 1 / price -> 5', dec515(v_new, 1, 1, 2048, t0 + 300000)[0] == 4 and dec515(None, 1, 1, 2048, t0)[0] == 1 and dec515(2650.0, 1, 1, 2048, t0)[0] == 5)
check('max format-2 BUS still < 2^49 and reversible', bus515(3, 2, 2097151, SP.BASE + 300000 * (SP.SLOTS - 1)) < 2 ** 49 and dec515(bus515(3, 2, 2097151, SP.BASE + 300000 * (SP.SLOTS - 1)), 3, 2, 2097152, SP.BASE + 300000 * (SP.SLOTS - 1)) == (0, 2097151))
print(f'{ok} checks passed (model only; not a Pine run)')
