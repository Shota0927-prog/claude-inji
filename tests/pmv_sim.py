"""PointMasterVerifier.pine (VERIFY V1) のイベント追跡を1対1で写したモデルと確認テスト。
Pine の処理順（① 追跡中イベント更新 → ② 新規イベント登録）・集計項目 index をそのまま再現する。"""
BAR = 300000
HB = [1, 3, 6]
NS = 16
TOL = 1e-6
TICK = 0.01

class Verify:
    def __init__(self, th1=5.0, th2=10.0, race=10.0, start=0):
        self.st = {}
        self.ev = []
        self.prev = None
        self.last = 0
        self.th1, self.th2, self.race, self.start = th1, th2, race, start

    def cell(self, tp, d, h):
        return self.st.setdefault((tp, 0 if d == 1 else 1, h), [0.0] * NS)

    def finalize(self, tp, d, h, p0, p1, hi, lo, race):
        c = self.cell(tp, d, h)
        eps = TICK * 0.5
        r = d * (p1 - p0)
        mfe = max(0, hi - p0) if d == 1 else max(0, p0 - lo)
        mae = max(0, p0 - lo) if d == 1 else max(0, hi - p0)
        c[0] += 1
        c[1 if r > eps else 2 if r < -eps else 3] += 1
        c[4] += r
        c[5] += r >= self.th1 - TOL
        c[6] += r >= self.th2 - TOL
        c[7] += r <= -self.th1 + TOL
        c[8] += r <= -self.th2 + TOL
        c[9] += mfe
        c[10] += mae
        c[14 if race == 0 else 10 + race] += 1

    def missing(self, tp, d, k):
        for h in range(3):
            if HB[h] > k:
                self.cell(tp, d, h)[15] += 1

    @staticmethod
    def code(v, lim):
        if v is None or abs(v - round(v)) >= 1e-6 or abs(v) > lim + 1e-6:
            return None
        return int(round(v))

    def bar(self, t, o, hi, lo, c, phase, vtcode=0):
        # phase / vtcode = 受信値（input.source）。不正値では集計しない
        if t <= self.last:
            return
        self.last = t
        for e in list(reversed(self.ev)):
            k = e['k'] + 1
            done = False
            if t != e['t0'] + k * BAR:
                self.missing(e['tp'], e['d'], e['k'])
                done = True
            else:
                e['hi'] = hi if e['k'] == 0 else max(e['hi'], hi)
                e['lo'] = lo if e['k'] == 0 else min(e['lo'], lo)
                if e['race'] == 0:
                    fx = hi - e['p0'] if e['d'] == 1 else e['p0'] - lo
                    ax = e['p0'] - lo if e['d'] == 1 else hi - e['p0']
                    fh, ah = fx >= self.race - TOL, ax >= self.race - TOL
                    e['race'] = 3 if fh and ah else 1 if fh else 2 if ah else 0
                e['k'] = k
                for h in range(3):
                    if HB[h] == k:
                        self.finalize(e['tp'], e['d'], h, e['p0'], c, e['hi'], e['lo'], e['race'])
                done = k >= 6
            if done:
                self.ev.remove(e)
        ph, vt = self.code(phase, 4), self.code(vtcode, 3)
        if ph is None or vt is None:
            self.prev = None          # 受信不正：集計せず基準を破棄
            return
        inr = t + BAR >= self.start
        if self.prev is not None and ph != self.prev and inr:
            tp = {1: 0, 3: 1, 4: 2}.get(abs(ph), -1)
            if tp >= 0:
                self.push(tp, 1 if ph > 0 else -1, t, c)
        self.prev = ph
        if abs(vt) == 2 and inr:
            self.push(3, 1 if vt > 0 else -1, t, c)

    def push(self, tp, d, t, c):
        self.ev.append(dict(tp=tp, d=d, p0=c, t0=t, k=0, hi=None, lo=None, race=0))

    def pending(self, tp, d, h):
        return sum(1 for e in self.ev if e['tp'] == tp and e['d'] == d and HB[h] > e['k'])


def run(bars, **kw):
    v = Verify(**kw)
    for b in bars:
        v.bar(*b)
    return v

def mk(rows, t0=1_700_000_100_000):
    # rows: (o, h, l, c, phase[, vt, cur])
    return [(t0 + i * BAR,) + tuple(r) for i, r in enumerate(rows)]

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print("OK ", name)

# 1) HOLD 継続中に件数が増えない / 初回の既存表示は数えない
rows = [(100, 101, 99, 100, 1)] * 3 + [(100, 101, 99, 100, 2)] + [(100, 101, 99, 100, 1)] * 10
v = run(mk(rows))
n = sum(v.cell(0, 1, 2)[0] + v.cell(0, 1, 2)[15] for _ in [0]) + v.pending(0, 1, 2)
check("baseline HOLD not counted, CAUTION->HOLD counted once, HOLD x10 no extra", n == 1)

# 2) 判定足のヒゲが MFE/MAE に入らない
rows = [(100, 100, 100, 100, 0), (100, 150, 50, 100, 1)] + [(100, 102, 99, 101, 1)] * 6
v = run(mk(rows))
c = v.cell(0, 1, 0)
check("event-bar wick excluded (MFE=2, MAE=1 at 5m)", c[9] == 2 and c[10] == 1)

# 3) LONG/SHORT 対称（価格を鏡映・高安入替・方向反転で同じ結果）
import random
random.seed(1)
rowsL, rowsS = [], []
p = 2000.0
for i in range(400):
    o = p; c = p + random.uniform(-6, 6); hi = max(o, c) + random.uniform(0, 5); lo = min(o, c) - random.uniform(0, 5)
    ph = random.choice([1, 1, 1, 2, 3, 4, 0])
    rowsL.append((o, hi, lo, round(c, 2), ph, random.choice([0, 0, 0, 1, 2, 3])))
    M = 4000.0
    rowsS.append((M - o, M - lo, M - hi, round(M - round(c, 2), 2), -ph, -rowsL[-1][5]))
    p = round(c, 2)
vL, vS = run(mk(rowsL)), run(mk(rowsS))
sym = all(abs(a - b) < 1e-6 for tp in range(4) for h in range(3)
          for a, b in zip(vL.cell(tp, 1, h), vS.cell(tp, -1, h)))
check("LONG/SHORT symmetric", sym and vL.cell(0, 1, 2)[0] > 0)

# 4) 観察中に CURRENT 方向が変わっても元の方向で評価
rows = [(100, 100, 100, 100, 0), (100, 100, 100, 100, -1), (100, 106, 99, 105, 1)] + [(105, 105, 105, 105, 1)] * 6
v = run(mk(rows))
c = v.cell(0, -1, 0)
check("SHORT HOLD keeps d=-1 after flip to LONG (R=-5 counted adverse)", c[0] == 1 and c[2] == 1 and c[7] == 1 and c[4] == -5)
check("LONG HOLD after flip is its own event", v.cell(0, 1, 0)[0] == 1)

# 5) 未完了は分母に入らない
rows = [(100, 100, 100, 100, 0), (100, 100, 100, 100, 1), (100, 101, 99, 100, 1), (100, 101, 99, 100, 1)]
v = run(mk(rows))
check("15m/30m pending, not evaluated", v.cell(0, 1, 0)[0] == 1 and v.cell(0, 1, 1)[0] == 0 and v.pending(0, 1, 1) == 1 and v.pending(0, 1, 2) == 1)

# 6) 同一足で両方の閾値 → 順序不明。決定後は書き換えない
rows = [(100, 100, 100, 100, 0), (100, 100, 100, 100, 1), (100, 111, 89, 100, 1), (100, 125, 99, 120, 1)] + [(120, 121, 119, 120, 1)] * 5
v = run(mk(rows))
check("both thresholds same bar -> ambiguous for all horizons", all(v.cell(0, 1, h)[13] == 1 for h in range(3)))
rows = [(100, 100, 100, 100, 0), (100, 100, 100, 100, 1), (100, 103, 99, 101, 1), (100, 111, 99, 110, 1), (110, 111, 85, 90, 1)] + [(90, 91, 89, 90, 1)] * 4
v = run(mk(rows))
check("fav first not overwritten; 5m = not reached", v.cell(0, 1, 0)[14] == 1 and v.cell(0, 1, 1)[11] == 1 and v.cell(0, 1, 2)[11] == 1)

# 7) 時刻の途切れ → 未評価期間は欠損、評価済み期間は残る
b = mk([(100, 100, 100, 100, 0), (100, 100, 100, 100, 1), (100, 101, 99, 100, 1), (100, 101, 99, 100, 1)])
b.append((b[-1][0] + 10 * BAR, 100, 101, 99, 100, 1))
v = run(b)
check("gap -> 15m/30m missing, 5m kept", v.cell(0, 1, 0)[0] == 1 and v.cell(0, 1, 1)[15] == 1 and v.cell(0, 1, 2)[15] == 1 and not v.ev)

# 8) 同じ確定足の二重処理なし
b = mk([(100, 100, 100, 100, 0), (100, 100, 100, 100, 1)])
v = run(b + [b[-1]] + mk([(100, 101, 99, 100, 1)], b[-1][0] + BAR))
check("same bar not double counted", v.cell(0, 1, 0)[0] == 1)

# 9) VALID TP は PHASE と別。PARTIAL → FULL はそれぞれ1件
rows = [(100, 100, 100, 100, 0), (100, 100, 100, 100, 3), (100, 100, 100, 100, 4, 2)] + [(100, 100, 100, 100, 4)] * 7
v = run(mk(rows))
check("PARTIAL, FULL, VALID each 1", v.cell(1, 1, 2)[0] == 1 and v.cell(2, 1, 2)[0] == 1 and v.cell(3, 1, 2)[0] == 1 and v.cell(0, 1, 2)[0] == 0)

# 10) 先着の4区分合計 = 評価済み件数
tot = all(sum(vL.cell(tp, d, h)[11:15]) == vL.cell(tp, d, h)[0] for tp in range(4) for d in (1, -1) for h in range(3))
check("race buckets sum to evaluated count", tot)

# 11) 未接続（既定 close = 価格）/ 範囲外 / 非整数 → 集計しない
rows = [(2650, 2651, 2649, 2650, 2650.0, 2650.0)] * 3 + [(2650, 2651, 2649, 2650, 1.5, 0)] + [(2650, 2651, 2649, 2650, 5, 0)]
v = run(mk(rows))
check("unconnected / out-of-range / non-integer -> no events", not v.ev and not any(sum(c) for c in v.st.values()))

# 12) 不正値の後は基準を作り直す（復帰直後の HOLD は数えない）
rows = [(100, 100, 100, 100, 0, 0), (100, 100, 100, 100, 1, 0), (100, 100, 100, 100, 2650.0, 0), (100, 100, 100, 100, 1, 0)] + [(100, 100, 100, 100, 1, 0)] * 7
v = run(mk(rows))
check("invalid bar resets baseline; ongoing event keeps tracking", v.cell(0, 1, 2)[0] == 1)

# 13) VALID FULL TP の方向はコードの符号 / ±1, ±3 は対象外
rows = [(100, 100, 100, 100, 0, 0), (100, 100, 100, 100, 0, -2), (100, 100, 100, 100, 0, -3), (100, 100, 100, 100, 0, 1)] + [(100, 100, 100, 100, 0, 0)] * 7
v = run(mk(rows))
check("VALID sign -> SHORT, ARMED/DONE ignored", v.cell(3, -1, 2)[0] == 1 and v.cell(3, 1, 2)[0] == 0)
print(f"{ok} checks passed")
