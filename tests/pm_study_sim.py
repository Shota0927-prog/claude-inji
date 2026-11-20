"""単体診断（Source の STUDY DATA / META BUS）と PointMasterLogicVerifier のイベント抽出の Python モデル確認。
Pine 上の実行確認ではない。Source 側は f_v2ApplyTf の 1 ロジック分（診断記録を含む）と f_study、
Verifier 側は受信分類と モード 1 / 2 / 3 の登録規則を写したもの。"""
import math

BASE = 1577836800000
SLOTS = 2 ** 22

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)


class OneLogic:
    """1 ロジック × 1 TF の V2 有効根拠 + 診断（rule 0 : ライン。価格否定は LONG: close < lvl / SHORT: close > lvl）"""
    def __init__(self, hold, rule=0):
        self.hold, self.rule = hold, rule
        self.v = [dict(valid=False, price=False, rem=0, age=0, lvl=None, raw=False, negf=False, expf=False, since=-1, pre=0.0) for _ in (0, 1)]
        self.newbar = False

    def apply(self, close, rawL, rawS, lvlL=None, lvlS=None, preL=0.0, preS=0.0, conflict='ignore'):
        self.newbar = True
        both = rawL and rawS
        sigL = (conflict == 'long') if both else rawL
        sigS = (conflict == 'short') if both else rawS
        for d in (0, 1):
            e = self.v[d]
            reg, opp = (sigL, sigS) if d == 0 else (sigS, sigL)
            aging = e['valid']
            age1 = e['age'] + (1 if aging else 0)
            rem1 = e['rem'] - (1 if aging else 0)
            lv = e['lvl']
            negd = aging and rem1 > 0 and e['price'] and lv is not None and ((d == 0 and close < lv) or (d == 1 and close > lv))
            alive = e['valid'] and rem1 > 0 and not negd
            lvN = lvlL if d == 0 else lvlS
            raw = rawL if d == 0 else rawS
            e.update(valid=True if reg else False if opp else alive, price=(lvN is not None) if reg else e['price'],
                     rem=self.hold if reg else rem1, age=0 if reg else age1, lvl=lvN if reg else e['lvl'],
                     pre=preL if d == 0 else preS, raw=raw, negf=negd, expf=aging and rem1 <= 0 and not reg,
                     since=0 if raw else (-1 if e['since'] < 0 else e['since'] + 1))


def cap6(v):
    return 63 if v < 0 else 62 if v >= 62 else v


def study(o, status, tclose, sid, tf, logic, adopted=True, na_combo=False):
    """Source の f_study（DATA, META）"""
    slot = (tclose - BASE) / 300000.0
    sok = 0 <= slot < SLOTS and slot == math.floor(slot)
    st = 6 if na_combo else status
    nb = o.newbar
    L, S = o.v
    cL = L['valid'] and L['price'] and adopted
    cS = S['valid'] and S['price'] and adopted
    ageL = L['age'] if cL else -1
    ageS = S['age'] if cS else -1
    data = ((1 if nb and L['raw'] else 0) + (2 if nb and S['raw'] else 0) + (4 if cL else 0) + (8 if cS else 0) +
            16 * round(L['pre'] * 3) + 64 * round(S['pre'] * 3) +
            (256 if nb and L['negf'] else 0) + (512 if nb and S['negf'] else 0) + (1024 if nb and L['expf'] else 0) + (2048 if nb and S['expf'] else 0) +
            4096 * cap6(L['since']) + 262144 * cap6(S['since']) + 16777216 * cap6(ageL) + 1073741824 * cap6(ageS) +
            (68719476736 if nb else 0) + 137438953472 * (slot % 16384))
    meta = 1 + 4 * sid + 16 * tf + 64 * logic + 2048 * st + 16384 * (1 if adopted else 0) + 32768 * slot
    return (data if sok and st == 0 else None), (meta if sok else None)


class LogicVerifier:
    """PointMasterLogicVerifier の受信分類と登録規則（価格観察部分は既存 Verifier と同じなので除外）"""
    def __init__(self, mode, start=0, end=10 ** 15):
        self.mode, self.start, self.end = mode, start, end
        self.events = []          # (bar index, type, dir)
        self.both = 0
        self.prevL = self.prevS = -1
        self.lock = None
        self.seen = False
        self.pre = [0] * 6
        self.post = [0] * 6
        self.last_t = None

    def bar(self, i, tclose, data, meta):
        if self.last_t is not None and tclose <= self.last_t:
            return None
        self.last_t = tclose
        slot_now = (tclose - BASE) / 300000.0
        num = lambda v, lim: v is not None and 0 <= v < lim and v == math.floor(v)
        mnum = num(meta, 2 ** 37)
        if mnum:
            fmt, sid, tf, lg, st = meta % 4, (meta // 4) % 4, (meta // 16) % 4, (meta // 64) % 32, (meta // 2048) % 8
            mslot = meta // 32768
            shape = fmt == 1 and 1 <= sid <= 3 and 1 <= tf <= 2 and 1 <= lg <= 25
            mid = (sid * 16 + tf) * 32 + lg if shape else None
        else:
            shape, mid, st, mslot = False, None, None, None
        dsync = num(data, 2 ** 51) and shape and data // 137438953472 == mslot % 16384
        inper = self.start <= tclose <= self.end
        if not shape or (self.lock is not None and mid != self.lock):
            cat = 3
        elif mslot != slot_now:
            cat = 4
        elif st == 1:
            cat = 0
        elif st == 4:
            cat = 1
        elif st == 6:
            cat = 2
        elif st != 0 or not dsync:
            cat = 3
        elif not inper:
            cat = 5
        else:
            cat = -1
        data_ok = cat in (-1, 5)
        if data_ok:
            self.lock = mid if self.lock is None else self.lock
            self.seen = self.seen or cat == -1
        if cat >= 0:
            (self.post if self.seen else self.pre)[cat] += 1
        if data_ok:
            b = lambda k: (data // 2 ** k) % 2 == 1
            f = lambda k: (data // 2 ** k) % 64
            nb, rawL, rawS, curL, curS, ageL, ageS = b(36), b(0), b(1), b(2), b(3), f(24), f(30)
            if cat == -1 and nb:
                if self.mode == 1:
                    if rawL and rawS:
                        self.both += 1
                    elif rawL or rawS:
                        self.events.append((i, 0, 1 if rawL else -1))
                elif self.mode == 2:
                    if self.prevL == 0 and curL:
                        self.events.append((i, 0, 1))
                    if self.prevS == 0 and curS:
                        self.events.append((i, 0, -1))
                else:
                    bucket = lambda a: 0 if a <= 1 else 1 if a <= 3 else 2 if a <= 6 else 3
                    if curL and ageL < 63:
                        self.events.append((i, bucket(ageL), 1))
                    if curS and ageS < 63:
                        self.events.append((i, bucket(ageS), -1))
            self.prevL, self.prevS = (1 if curL else 0), (1 if curS else 0)
        else:
            self.prevL = self.prevS = -1
        return cat


def run_15m(events_15m, nbars, mode, hold=4, closes=None, lvl=None, status=None):
    """15M（TF ID 2）の 1 ロジック。15M 確定足は 5 分足 3 本ごとに処理（[1] 方式で 5 分足 3 本に 1 回 newbar）。
    events_15m : {15M 足番号: 'L' | 'S' | 'LS'}"""
    o = OneLogic(hold)
    v = LogicVerifier(mode)
    t0 = BASE + 300000 * 1000
    k15 = 0
    for i in range(nbars):
        tclose = t0 + 300000 * (i + 1)
        o.newbar = False
        if i % 3 == 0:                         # 新しい 15M 確定足を処理する 5 分足
            sig = events_15m.get(k15, '')
            c = closes[k15] if closes else 100.0
            o.apply(c, 'L' in sig, 'S' in sig, lvlL=(lvl if lvl is not None else 90.0), lvlS=110.0)
            k15 += 1
        data, meta = study(o, 0 if status is None else status(i), tclose, 3, 2, 21)
        v.bar(i, tclose, data, meta)
    return v, o


# ---- 15M の 1 本の生シグナルを 5 分足 3 本で重複登録しない / 別の 15M 足のシグナルは別件
v, _ = run_15m({2: 'L'}, 30, mode=1)
check('mode 1 : one 15M raw signal -> 1 event (not 3 for the 3 five-minute bars that see it)', v.events == [(6, 0, 1)])
v, _ = run_15m({2: 'L', 3: 'L', 5: 'L'}, 30, mode=1)
check('mode 1 : same-direction signals on separate 15M bars are separate events', [e[0] for e in v.events] == [6, 9, 15])
v, _ = run_15m({2: 'LS'}, 30, mode=1)
check('mode 1 : both directions at once -> "both" count only, not in direction stats', v.events == [] and v.both == 1)

# ---- モード 2 : 無効 → 有効 で 1 件。期限更新（同方向の再シグナル）や有効継続では増えない
v, o = run_15m({2: 'L', 4: 'L'}, 40, mode=2, hold=4)
check('mode 2 : activation once; renewal by same-direction signal does not add', v.events == [(6, 0, 1)])
v, o = run_15m({2: 'L', 9: 'L'}, 40, mode=2, hold=4)
check('mode 2 : re-activation after expiry is a new event', [e[0] for e in v.events] == [6, 27])
v, _ = run_15m({0: 'L'}, 12, mode=2, hold=4)
check('mode 2 : first readable bar is baseline only (already active at start -> no event)', v.events == [])

# ---- モード 3 : 有効な間、新しい 15M 確定足ごとに 1 観察点。区分は最後の登録からの本数、期限切れ後は観察しない
v, _ = run_15m({2: 'L', 4: 'L'}, 40, mode=3, hold=4)
ages = [(e[0], e[1]) for e in v.events]
# 15M 足 2 で登録（経過 0）→ 3（1）→ 4 で再登録（0）→ 5（1）→ 6（2）→ 7（3）→ 8 で期限切れ（hold 4）
check('mode 3 : observation per new 15M bar, age restarts on renewal, none after expiry',
      ages == [(6, 0), (9, 0), (12, 0), (15, 0), (18, 1), (21, 1)])
v, _ = run_15m({2: 'L'}, 60, mode=3, hold=20)
check('mode 3 : buckets 0-1 / 2-3 / 4-6 / 7+ by own-TF age', [e[1] for e in v.events][:10] == [0, 0, 1, 1, 2, 2, 2, 3, 3, 3])

# ---- 価格否定と期限の解除フラグ（DATA に出る）
o = OneLogic(hold=3)
o.apply(100, True, False, lvlL=95.0)
o.apply(94, False, False)
check('negation release flag set on the TF bar where close breaks the line', o.v[0]['negf'] and not o.v[0]['valid'])
o = OneLogic(hold=2)
o.apply(100, True, False, lvlL=95.0); o.apply(100, False, False); o.apply(100, False, False)
check('expiry release flag (not negation) when hold runs out', o.v[0]['expf'] and not o.v[0]['negf'] and not o.v[0]['valid'])
o = OneLogic(hold=1)
o.apply(100, True, False, lvlL=95.0); o.apply(100, True, False, lvlL=96.0)
check('same-bar re-registration is not counted as expiry', not o.v[0]['expf'] and o.v[0]['valid'] and o.v[0]['age'] == 0)

# ---- BUS 境界・丸めなし
o = OneLogic(hold=200)
o.apply(100, True, False, lvlL=50.0, preL=2 / 3.0, preS=1 / 3.0)
for _ in range(70):
    o.newbar = False
    o.apply(100, False, False, preL=2 / 3.0, preS=1 / 3.0)
data, meta = study(o, 0, BASE + 300000 * (SLOTS - 1), 3, 2, 25)
f = lambda k, w: (data // 2 ** k) % 2 ** w
check('PRE 1/3 and 2/3 kept exactly (q = 1 / 2)', f(4, 2) == 2 and f(6, 2) == 1)
check('since / age >= 62 shown as 62 (= 62 or more), not wrapped', f(12, 6) == 62 and f(24, 6) == 62)
check('never-signalled direction = 63 (none), invalid direction age = 63', f(18, 6) == 63 and f(30, 6) == 63)
check('DATA < 2^51, META < 2^37 at the last slot', data < 2 ** 51 and meta < 2 ** 37 and data <= 2 ** 53 - 1)
check('META fields reversible at maximum', (meta % 4, (meta // 4) % 4, (meta // 16) % 4, (meta // 64) % 32, (meta // 2048) % 8, (meta // 16384) % 2, meta // 32768) == (1, 3, 2, 25, 0, 1, SLOTS - 1))

# ---- 受信分類：準備中 / 不整合 / 対象外 / 接続不正 / 古い時刻 / 期間外、有効受信の前 / 後
st_seq = lambda i: 1 if i < 5 else 4 if i == 12 else 0
v, _ = run_15m({}, 20, mode=1, status=st_seq)
check('Source not ready before first valid -> pre[0]; Source inconsistent after -> post[1]', v.pre[0] == 5 and v.post[1] == 1 and v.seen)
o = OneLogic(4)
lv = LogicVerifier(1)
t = BASE + 300000 * 5000
d1, m1 = study(o, 0, t, 1, 1, 5)
lv.bar(0, t, d1, m1)
d2, m2 = study(o, 0, t + 300000, 1, 1, 6)        # 途中で別ロジックへ接続変更
check('connection target changed mid-history -> connection error (3)', lv.bar(1, t + 300000, d2, m2) == 3)
check('old time -> 4', LogicVerifier(1).bar(0, t + 300000, d1, m1) == 4)
check('EMA on 15M (not applicable) -> 2 and DATA na', study(o, 0, t, 1, 2, 5, na_combo=True)[0] is None and LogicVerifier(1).bar(0, t, *study(o, 0, t, 1, 2, 5, na_combo=True)) == 2)
check('price input / na -> connection error (3)', LogicVerifier(1).bar(0, t, None, 2650.0) == 3 and LogicVerifier(1).bar(0, t, None, None) == 3)
check('out of period -> 5 (data still read for baseline)', LogicVerifier(1, start=t + 1).bar(0, t, d1, m1) == 5)
dbad = d1 + 137438953472                          # DATA の時刻照合ずれ
check('DATA from a different 5m bar -> connection error (3)', LogicVerifier(1).bar(0, t, dbad, m1) == 3)
print(f'{ok} checks passed (model only; not a Pine run)')
